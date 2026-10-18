"""CP-SAT scheduler (OR-Tools). Same problem, same checker, better answers on harder instances.

Model, per task t and eligible resource r:
  x[t,r]      t runs on r                  (exactly one r)
  s[t], e[t]  start / end                  (e = s + duration on r)
  y[t,r,w]    t runs inside working window w of r (and of the people it needs)
  arc[i,j,r]  j directly follows i on r    (AddCircuit) -> e[i] + setup(i,j) <= s[j]
  su[t,r]     setup minutes before t on r  (= setup of the chosen arc into t)
People are cumulative resources (run intervals + setup intervals). Precedences carry min/max lags.
The objective list from the config is optimised lexicographically, warm-started from the rule-based plan.
"""
from collections import defaultdict

from ortools.sat.python import cp_model

import solve_rules
from model import SLOT, duration, people_need, setup_minutes, setup_people


def _intersect(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        s, e = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if s < e:
            out.append((s, e))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def solve(prob, seconds=20, verbose=False):
    cfg, res = prob.cfg, prob.cfg["resources"]
    H = prob.horizon
    T = prob.tasks
    m = cp_model.CpModel()

    hint = solve_rules.solve(prob)                     # warm start + fallback

    s, e, x, su_tr, d_tr = {}, {}, {}, {}, {}
    for tid, t in T.items():
        s[tid] = m.NewIntVar(t.release, H, f"s_{tid}")
        e[tid] = m.NewIntVar(0, H, f"e_{tid}")
        lits = []
        for rid in t.eligible:
            x[tid, rid] = m.NewBoolVar(f"x_{tid}_{rid}")
            d_tr[tid, rid] = duration(res[rid], t.qty)
            m.Add(e[tid] == s[tid] + d_tr[tid, rid]).OnlyEnforceIf(x[tid, rid])
            lits.append(x[tid, rid])
        m.AddExactlyOne(lits)

    # sequencing + setups per resource
    on_res = defaultdict(list)
    for tid, t in T.items():
        for rid in t.eligible:
            on_res[rid].append(tid)
    setup_total = []
    setup_iv = defaultdict(list)                       # pool -> intervals
    for rid, tids in on_res.items():
        r = res[rid]
        has_setups = bool(r.get("setups"))
        if not has_setups:
            ivs = [m.NewOptionalIntervalVar(s[t], d_tr[t, rid], e[t], x[t, rid], f"iv_{t}_{rid}") for t in tids]
            m.AddNoOverlap(ivs)
            for t in tids:
                su_tr[t, rid] = 0
            continue
        arcs, into = [], defaultdict(list)
        idx = {t: i + 1 for i, t in enumerate(tids)}
        for t in tids:
            first = m.NewBoolVar(f"first_{t}_{rid}")
            last = m.NewBoolVar(f"last_{t}_{rid}")
            arcs += [(0, idx[t], first), (idx[t], 0, last), (idx[t], idx[t], x[t, rid].Not())]
        for a in tids:
            for b in tids:
                if a == b:
                    continue
                lit = m.NewBoolVar(f"arc_{a}_{b}_{rid}")
                st = setup_minutes(r, T[a].attrs, T[b].attrs)
                m.Add(s[b] >= e[a] + st).OnlyEnforceIf(lit)
                arcs.append((idx[a], idx[b], lit))
                if st:
                    into[b].append((lit, st, a))
        m.AddCircuit(arcs)
        for t in tids:
            su = m.NewIntVar(0, 600, f"su_{t}_{rid}")
            m.Add(su == sum(l * st for l, st, _ in into[t]))
            su_tr[t, rid] = su
            setup_total.append(su)
            pools = {setup_people(r, T[a].attrs, T[t].attrs) for _, _, a in into[t]} - {None}
            if pools:
                ss = m.NewIntVar(-600, H, f"ss_{t}_{rid}")
                m.Add(ss == s[t] - su)
                iv = m.NewOptionalIntervalVar(ss, su, s[t], x[t, rid], f"siv_{t}_{rid}")
                for p in pools:
                    setup_iv[p].append(iv)

    # working windows (resource calendar intersected with the calendars of the people it needs)
    for tid, t in T.items():
        for rid in t.eligible:
            W = prob.windows[rid]
            for pool, _, _ in people_need(res[rid]):
                W = _intersect(W, prob.people_windows[pool])
            W = [w for w in W if w[1] - w[0] >= d_tr[tid, rid]]
            ys = [m.NewBoolVar(f"y_{tid}_{rid}_{k}") for k in range(len(W))]
            m.Add(sum(ys) == 1).OnlyEnforceIf(x[tid, rid])
            m.Add(sum(ys) == 0).OnlyEnforceIf(x[tid, rid].Not())
            for (w0, w1), y in zip(W, ys):
                m.Add(s[tid] - su_tr[tid, rid] >= w0).OnlyEnforceIf(y)
                m.Add(e[tid] <= w1).OnlyEnforceIf(y)

    # people
    people_iv = defaultdict(list)
    for tid, t in T.items():
        for rid in t.eligible:
            for pool, q, during in people_need(res[rid]):
                if during == "start":
                    iv = m.NewOptionalFixedSizeIntervalVar(s[tid], min(SLOT, d_tr[tid, rid]), x[tid, rid], f"p_{tid}")
                elif during == "end":
                    st = m.NewIntVar(0, H, f"pe_{tid}")
                    m.Add(st == e[tid] - min(SLOT, d_tr[tid, rid]))
                    iv = m.NewOptionalFixedSizeIntervalVar(st, min(SLOT, d_tr[tid, rid]), x[tid, rid], f"p_{tid}")
                else:
                    iv = m.NewOptionalIntervalVar(s[tid], d_tr[tid, rid], e[tid], x[tid, rid], f"p_{tid}_{rid}")
                people_iv[pool].append((iv, q))
    for pool, cap in ((p, v["count"]) for p, v in cfg["people"].items()):
        ivs = [iv for iv, _ in people_iv[pool]] + setup_iv[pool]
        dem = [q for _, q in people_iv[pool]] + [1] * len(setup_iv[pool])
        if ivs:
            m.AddCumulative(ivs, dem, cap)

    # precedences with lags
    for a, b, lo, hi in prob.preds:
        m.Add(s[b] >= e[a] + lo)
        if hi is not None:
            m.Add(s[b] <= e[a] + hi)

    # order completion and tardiness
    tard, late = {}, {}
    for o in prob.orders.values():
        last = prob.order_last[o.id]
        last = last if isinstance(last, list) else [last]
        c = m.NewIntVar(0, H, f"c_{o.id}")
        m.AddMaxEquality(c, [e[t] for t in last])
        tard[o.id] = m.NewIntVar(0, H, f"T_{o.id}")
        m.Add(tard[o.id] >= c - o.due)
        late[o.id] = m.NewBoolVar(f"late_{o.id}")
        m.Add(tard[o.id] == 0).OnlyEnforceIf(late[o.id].Not())

    def expr(obj):
        k, f = obj["kpi"], obj.get("filter", {}) or {}
        sel = [o for o in prob.orders.values() if "priority" not in f or o.priority == f["priority"]]
        if k == "late_qty":
            return sum(int(round(o.qty)) * late[o.id] for o in sel)
        if k == "weighted_tardiness":
            return sum(int(round(o.weight * 10)) * tard[o.id] for o in sel)
        if k == "setup_minutes":
            return sum(setup_total) if setup_total else None
        if k == "makespan":
            mk = m.NewIntVar(0, H, "makespan")
            m.AddMaxEquality(mk, list(e.values()))
            return mk
        return None        # plan_changes (needs a previous plan), batch_count (fixed by the model): skipped

    # warm start from the rule-based plan
    for tid, v in hint.items():
        m.AddHint(s[tid], v["start"])
        for rid in T[tid].eligible:
            m.AddHint(x[tid, rid], 1 if rid == v["resource"] else 0)

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = 7
    objs = [(o, expr(o)) for o in cfg["objective"]]
    objs = [(o, ex) for o, ex in objs if ex is not None]
    best = None
    for i, (o, ex) in enumerate(objs):
        m.Minimize(ex)
        solver.parameters.max_time_in_seconds = seconds / len(objs)
        st = solver.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        val = int(solver.ObjectiveValue())
        if verbose:
            print(f"  [{o['kpi']}] {solver.StatusName(st)} = {val}")
        best = {tid: {"resource": next(r for r in T[tid].eligible if solver.Value(x[tid, r])),
                      "start": solver.Value(s[tid]), "end": solver.Value(e[tid])} for tid in T}
        for tid, v in best.items():
            v["setup"] = solver.Value(su_tr[tid, v["resource"]]) if not isinstance(su_tr[tid, v["resource"]], int) else 0
        m.Add(ex <= val)                                  # keep this level, go to the next
        m.ClearHints()
        for tid, v in best.items():
            m.AddHint(s[tid], v["start"])
            for rid in T[tid].eligible:
                m.AddHint(x[tid, rid], 1 if rid == v["resource"] else 0)
    return best if best is not None else hint
