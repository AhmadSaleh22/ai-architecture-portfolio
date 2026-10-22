"""CP-SAT solver (OR-Tools) for any core Problem.

Per task t: presence p (false only if its optional job is rejected), primary choice x[t,r],
start/end, window choice, and a choice among candidates for every other requirement.
Primaries with setups are sequenced with AddCircuit (arc i->j forces e_i + setup(i,j) <= s_j);
every resource gets NoOverlap (capacity 1) or Cumulative (capacity k) over all its uses,
setup intervals included. Precedences carry min/max lags. Objectives are optimised
lexicographically, warm-started from the greedy plan, which is also the fallback.
"""
from collections import defaultdict

from ortools.sat.python import cp_model

from . import greedy
from .kpi import completion  # noqa: F401  (re-exported for adapters)
from .model import SLOT, intersect, setup_minutes

KPIS = ("late_qty", "weighted_tardiness", "rejected", "preference", "setup_minutes", "plan_changes", "makespan")


def solve(prob, seconds=20, verbose=False, hint=None):
    """Returns (schedule, rejected_jobs)."""
    if hint is None:
        hint = greedy.solve(prob)
    T, R, H = prob.tasks, prob.resources, prob.horizon
    m = cp_model.CpModel()

    pj = {}
    for j in prob.jobs.values():
        pj[j.id] = m.NewBoolVar(f"p_{j.id}") if j.optional else m.NewConstant(1)
    pres = {}
    for tid, t in T.items():
        opt = [j for j in t.jobs if prob.jobs[j].optional]
        pres[tid] = pj[opt[0]] if (len(t.jobs) == 1 and opt) else m.NewConstant(1)

    s, e, x, su_tr, sec = {}, {}, {}, {}, {}
    uses = defaultdict(list)                       # resource -> [(interval, demand)]
    for tid, t in T.items():
        lo = t.release
        if tid in prob.frozen:
            f = prob.frozen[tid]
            s[tid] = m.NewConstant(f["start"])
            m.Add(pres[tid] == 1)
        elif t.allowed_starts:
            s[tid] = m.NewIntVarFromDomain(cp_model.Domain.FromValues([a for a in t.allowed_starts if a >= lo]), f"s_{tid}")
        else:
            s[tid] = m.NewIntVar(lo, H, f"s_{tid}")
        e[tid] = m.NewIntVar(0, H, f"e_{tid}")
        prim = t.requirements[0].candidates
        if tid in prob.frozen:
            prim = [prob.frozen[tid]["res"][0]]
        lits = []
        for r in t.requirements[0].candidates:
            x[tid, r] = m.NewBoolVar(f"x_{tid}_{r}")
            if r not in prim:
                m.Add(x[tid, r] == 0)
            m.Add(e[tid] == s[tid] + t.duration[r]).OnlyEnforceIf(x[tid, r])
            lits.append(x[tid, r])
        m.Add(sum(lits) == pres[tid])
        if t.deadline is not None:
            m.Add(e[tid] <= t.deadline).OnlyEnforceIf(pres[tid])

    # sequencing and setups on primaries
    on = defaultdict(list)
    for tid, t in T.items():
        for r in t.requirements[0].candidates:
            on[r].append(tid)
    setup_total = []
    for rid, tids in on.items():
        res = R[rid]
        if not res.setups or res.capacity > 1:
            for t in tids:
                su_tr[t, rid] = 0
            continue
        arcs, into = [], defaultdict(list)
        idx = {t: i + 1 for i, t in enumerate(tids)}
        for t in tids:
            arcs += [(0, idx[t], m.NewBoolVar("")), (idx[t], 0, m.NewBoolVar("")), (idx[t], idx[t], x[t, rid].Not())]
        for a in tids:
            for b in tids:
                if a == b:
                    continue
                lit = m.NewBoolVar(f"arc_{a}_{b}")
                st = setup_minutes(res, T[a].attrs, T[b].attrs)
                m.Add(s[b] >= e[a] + st).OnlyEnforceIf(lit)
                arcs.append((idx[a], idx[b], lit))
                if st:
                    into[b].append((lit, st))
        m.AddCircuit(arcs)
        for t in tids:
            su = m.NewIntVar(0, 1000, f"su_{t}_{rid}")
            m.Add(su == sum(l * st for l, st in into[t]))
            su_tr[t, rid] = su
            setup_total.append(su)

    # usage intervals, windows, secondary choices
    for tid, t in T.items():
        su_vars = [su_tr[tid, r] for r in t.requirements[0].candidates if not isinstance(su_tr[tid, r], int)]
        has_su = bool(su_vars)
        if len(su_vars) > 1:
            su_t = m.NewIntVar(0, 1000, f"sut_{tid}")
            m.Add(su_t == sum(su_vars))
        else:
            su_t = su_vars[0] if su_vars else 0
        ss = m.NewIntVar(-1000, H, f"ss_{tid}")
        m.Add(ss == s[tid] - su_t)
        for r in t.requirements[0].candidates:
            W = R[r].windows
            for req in t.requirements[1:]:
                if len(req.candidates) == 1:
                    W = intersect(W, R[req.candidates[0]].windows)
            W = [w for w in W if w[1] - w[0] >= t.duration[r]]
            ys = [m.NewBoolVar("") for _ in W]
            m.Add(sum(ys) == x[tid, r])
            for (w0, w1), y in zip(W, ys):
                m.Add(ss >= w0).OnlyEnforceIf(y)
                m.Add(e[tid] <= w1).OnlyEnforceIf(y)
            full = m.NewIntVar(0, H + 1000, f"len_{tid}_{r}")
            m.Add(full == t.duration[r] + su_t)
            uses[r].append((m.NewOptionalIntervalVar(ss, full, e[tid], x[tid, r], f"u_{tid}_{r}"), 1))
        for k, req in enumerate(t.requirements[1:], 1):
            d0 = min(t.duration.values())
            sl = min(SLOT, d0)
            if req.during == "start":
                a_, size, b_ = s[tid], sl, None
            elif req.during == "end":
                a_ = m.NewIntVar(0, H, "")
                m.Add(a_ == e[tid] - sl)
                size = sl
            else:
                a_, size = s[tid], None
            ys = []
            for c in req.candidates:
                y = pres[tid] if len(req.candidates) == 1 else m.NewBoolVar(f"y_{tid}_{k}_{c}")
                sec[tid, k, c] = y
                ys.append(y)
                if size is None:
                    dur = m.NewIntVar(0, H, "")
                    m.Add(dur == e[tid] - s[tid])
                    iv = m.NewOptionalIntervalVar(s[tid], dur, e[tid], y, "")
                else:
                    iv = m.NewOptionalFixedSizeIntervalVar(a_, size, y, "")
                uses[c].append((iv, req.qty))
                if req.setup_qty and has_su:
                    uses[c].append((m.NewOptionalIntervalVar(ss, su_t, s[tid], y, ""), req.setup_qty))
                if len(req.candidates) > 1:
                    W = R[c].windows
                    zs = [m.NewBoolVar("") for _ in W]
                    m.Add(sum(zs) == y)
                    for (w0, w1), z in zip(W, zs):
                        m.Add(s[tid] >= w0).OnlyEnforceIf(z)
                        m.Add(e[tid] <= w1).OnlyEnforceIf(z)
            if len(req.candidates) > 1:
                m.Add(sum(ys) == pres[tid])
                f = prob.frozen.get(tid)
                if f:
                    m.Add(sec[tid, k, f["res"][k]] == 1)

    for rid, lst in uses.items():
        cap = R[rid].capacity
        if cap == 1:
            m.AddNoOverlap([iv for iv, _ in lst])
        else:
            m.AddCumulative([iv for iv, _ in lst], [q for _, q in lst], cap)

    for a, b, lo, hi in prob.preds:
        both = [pres[a], pres[b]]
        m.Add(s[b] >= e[a] + lo).OnlyEnforceIf(both)
        if hi is not None:
            m.Add(s[b] <= e[a] + hi).OnlyEnforceIf(both)

    tard, late = {}, {}
    for j in prob.jobs.values():
        if j.due is None or not j.last:
            continue
        c = m.NewIntVar(0, H, f"c_{j.id}")
        m.AddMaxEquality(c, [e[t] for t in j.last])
        tard[j.id] = m.NewIntVar(0, H, f"T_{j.id}")
        m.Add(tard[j.id] >= c - j.due).OnlyEnforceIf(pj[j.id])
        m.Add(tard[j.id] == 0).OnlyEnforceIf(pj[j.id].Not())
        late[j.id] = m.NewBoolVar(f"late_{j.id}")
        m.Add(tard[j.id] == 0).OnlyEnforceIf(late[j.id].Not())

    def expr(obj):
        k, f = obj["kpi"], obj.get("filter", {}) or {}
        sel = [j for j in prob.jobs.values() if "priority" not in f or j.priority == f["priority"]]
        if k == "late_qty":
            terms = [int(round(j.qty)) * late[j.id] for j in sel if j.id in late]
            return sum(terms) if terms else None
        if k == "weighted_tardiness":
            terms = [int(round(j.weight * 10)) * tard[j.id] for j in sel if j.id in tard]
            return sum(terms) if terms else None
        if k == "rejected":
            terms = [int(round(j.reject_penalty or 1)) * (1 - pj[j.id]) for j in sel if j.optional]
            return sum(terms) if terms else None
        if k == "preference":
            devs = []
            for tid, t in T.items():
                if t.preferred:
                    d = m.NewIntVar(0, H, "")
                    m.Add(d >= t.preferred[0] - s[tid])
                    m.Add(d >= s[tid] - t.preferred[1])
                    devs.append(d)
            return sum(devs) if devs else None
        if k == "setup_minutes":
            return sum(setup_total) if setup_total else None
        if k == "plan_changes":
            terms = []
            for tid, pv in prob.previous.items():
                if tid not in T or tid in prob.frozen:
                    continue
                d = m.NewIntVar(0, H, "")
                m.Add(d >= s[tid] - pv["start"])
                m.Add(d >= pv["start"] - s[tid])
                terms.append(d)
                r0 = pv["res"][0]
                if (tid, r0) in x:
                    terms.append(240 * (1 - x[tid, r0]))     # a resource change costs like 4 hours
            return sum(terms) if terms else None
        if k == "makespan":
            mk = m.NewIntVar(0, H, "makespan")
            m.AddMaxEquality(mk, list(e.values()))
            return mk
        return None

    def add_hint(sched, rej):
        m.ClearHints()
        for j in prob.jobs.values():
            if j.optional:
                m.AddHint(pj[j.id], 0 if j.id in rej else 1)
        for tid, v in sched.items():
            m.AddHint(s[tid], v["start"])
            for r in T[tid].requirements[0].candidates:
                m.AddHint(x[tid, r], 1 if r == v["res"][0] else 0)
            for k, c in enumerate(v["res"][1:], 1):
                for cc in T[tid].requirements[k].candidates:
                    if len(T[tid].requirements[k].candidates) > 1:
                        m.AddHint(sec[tid, k, cc], 1 if cc == c else 0)

    best, best_rej = hint
    add_hint(best, best_rej)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = 7
    objs = [(o, expr(o)) for o in prob.objective]
    objs = [(o, ex) for o, ex in objs if ex is not None]
    for o, ex in objs:
        m.Minimize(ex)
        solver.parameters.max_time_in_seconds = seconds / max(1, len(objs))
        st = solver.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if verbose:
                print(f"  [{o['kpi']}] {solver.StatusName(st)}: keeping the previous plan")
            break
        val = int(solver.ObjectiveValue())
        if verbose:
            print(f"  [{o['kpi']}] {solver.StatusName(st)} = {val}")
        best_rej = sorted(j for j in prob.jobs if prob.jobs[j].optional and not solver.Value(pj[j]))
        best = {}
        for tid, t in T.items():
            if not solver.Value(pres[tid]):
                continue
            r0 = next(r for r in t.requirements[0].candidates if solver.Value(x[tid, r]))
            picks = [next(c for c in req.candidates if solver.Value(sec[tid, k, c]))
                     for k, req in enumerate(t.requirements[1:], 1)]
            su = su_tr[tid, r0]
            best[tid] = {"resource": r0, "res": [r0] + picks, "start": solver.Value(s[tid]),
                         "end": solver.Value(e[tid]), "setup": 0 if isinstance(su, int) else solver.Value(su)}
        m.Add(ex <= val)
        add_hint(best, best_rej)
    return best, best_rej
