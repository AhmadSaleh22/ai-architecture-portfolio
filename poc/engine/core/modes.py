"""Three ways to use the same core.

plan    the whole horizon at once (greedy or CP-SAT): see greedy.solve / cpsat.solve
offer   a new order arrives (a rush order): return the k best options in milliseconds,
        fitted around what is already booked, without moving anyone else
repair  something happened (breakdown, late material): freeze what already started
        or is about to, replan the rest, and prefer to keep the old plan (stability objective)
"""
from . import cpsat, greedy
from .check import check
from .model import setup_minutes  # noqa: F401


def _score(prob, job, opt):
    """Lower is better: distance from the preferred time, waiting, lateness, setup added."""
    t0 = opt["tasks"][opt["first"]]
    task = prob.tasks[opt["first"]]
    score = 0.0
    if task.preferred:
        a, b = task.preferred
        score += max(0, a - t0["start"], t0["start"] - b)
    else:
        score += max(0, t0["start"] - job.release) / 4          # sooner is a bit better
    end = max(v["end"] for v in opt["tasks"].values())
    if job.due is not None and end > job.due:
        score += 10 * (end - job.due)
    score += 2 * sum(v["setup"] for v in opt["tasks"].values())
    return score


def offer(prob, sched, job_id, k=3, spread=60, step=15, max_scan=400):
    """k options for job_id (its tasks must be in prob, not in sched). Nothing is changed."""
    job = prob.jobs[job_id]
    chain = sorted(prob.job_tasks(job_id), key=lambda t: (t.seq, t.id))
    first = chain[0]
    P = greedy.preds_of(prob)
    tl = greedy.Timeline(prob).load(sched)
    options, est = [], max(first.release, job.release)
    for _ in range(max_scan):
        best = tl.earliest(first.id, est, append_only=False)
        if best is None:
            break
        rid, start, end, su, picks = best
        snap = tl.snapshot()
        tl.commit(first.id, rid, start, end, su, picks)
        ok = True
        for t in chain[1:]:
            e0 = t.release
            for a, lo in P[t.id]:
                if a in tl.sched:
                    e0 = max(e0, tl.sched[a]["end"] + lo)
            b2 = tl.earliest(t.id, e0, append_only=False)
            if b2 is None:
                ok = False
                break
            tl.commit(t.id, *b2)
        if ok:
            opt = {"first": first.id, "tasks": {t.id: dict(tl.sched[t.id]) for t in chain}}
            ok = not [x for x in check(prob, {**sched, **opt["tasks"]}) if any(t.id in x for t in chain)
                      or "capacity" in x or "overlaps" in x]
            if ok:
                opt["score"] = _score(prob, job, opt)
                options.append(opt)
        tl.restore(snap)
        est = start + step
        if first.preferred and start > first.preferred[1] + 3 * 1440 and len(options) >= 3 * k:
            break
    options.sort(key=lambda o: (o["score"], o["tasks"][o["first"]]["start"]))
    picked = []
    for o in options:
        s0 = o["tasks"][o["first"]]["start"]
        if all(abs(s0 - p["tasks"][p["first"]]["start"]) >= spread or
               o["tasks"][o["first"]]["res"] != p["tasks"][p["first"]]["res"] for p in picked):
            picked.append(o)
        if len(picked) == k:
            break
    return picked


def accept(sched, option):
    """Book the chosen option."""
    new = dict(sched)
    new.update(option["tasks"])
    return new


def repair(prob, previous, now, freeze_min=120, solver="cpsat", seconds=10, stability_rank=1):
    """Replan after a disruption. Tasks that start before now + freeze_min stay where they were;
    the rest may move, but moving costs (plan_changes objective at position stability_rank)."""
    prob.frozen = {t: v for t, v in previous.items() if t in prob.tasks and v["start"] < now + freeze_min}
    prob.previous = {t: v for t, v in previous.items() if t in prob.tasks and t not in prob.frozen}
    for tid, t in prob.tasks.items():
        if tid not in prob.frozen:
            t.release = max(t.release, now + freeze_min)
    obj = [o for o in prob.objective if o["kpi"] != "plan_changes"]
    obj.insert(min(stability_rank, len(obj)), {"kpi": "plan_changes"})
    prob.objective = obj

    def old_order(j):
        starts = [previous[t.id]["start"] for t in prob.job_tasks(j.id) if t.id in previous]
        return (min(starts) if starts else 10 ** 9, j.priority, j.id)

    hint = _greedy_repair(prob, previous, old_order)
    if solver == "greedy":
        return hint
    return cpsat.solve(prob, seconds=seconds, hint=hint)


def _greedy_repair(prob, previous, order):
    """Keep every task where it was if it still fits; place the rest at the earliest feasible time."""
    tl = greedy.Timeline(prob)
    for tid, f in sorted(prob.frozen.items(), key=lambda kv: kv[1]["start"]):
        t = prob.tasks[tid]
        tl.commit(tid, f["res"][0], f["start"], f["start"] + t.duration[f["res"][0]], f.get("setup", 0), f["res"][1:])
    P = greedy.preds_of(prob)
    rejected = []
    jobs = sorted(prob.jobs.values(), key=order)
    # pass 1: everything that can stay exactly where it was
    for j in jobs:
        for t in sorted(prob.job_tasks(j.id), key=lambda t: (t.seq, t.id)):
            pv = previous.get(t.id)
            if t.id in tl.sched or not pv or pv["start"] < t.release:
                continue
            b = tl.earliest(t.id, pv["start"], append_only=False, prefer=pv["res"][0])
            if b and b[1] == pv["start"] and all(tl.sched.get(a, {}).get("end", 10 ** 9) + lo <= b[1] for a, lo in P[t.id]):
                tl.commit(t.id, *b)
    # pass 2: the rest, earliest feasible
    for j in jobs:
        snap = tl.snapshot()
        ok = True
        for t in sorted(prob.job_tasks(j.id), key=lambda t: (t.seq, t.id)):
            if t.id in tl.sched:
                continue
            est = t.release
            for a, lo in P[t.id]:
                if a not in tl.sched:
                    ok = False
                    break
                est = max(est, tl.sched[a]["end"] + lo)
            b = tl.earliest(t.id, est, append_only=False) if ok else None
            if b is None:
                ok = False
                break
            tl.commit(t.id, *b)
        if not ok:
            tl.restore(snap)
            if not j.optional:
                raise RuntimeError(f"repair: cannot place job {j.id}")
            rejected.append(j.id)
    # a job that lost some tasks but kept others: drop the leftovers if the job was rejected
    for jid in rejected:
        for t in prob.job_tasks(jid):
            tl.sched.pop(t.id, None)
    return tl.sched, sorted(rejected)


def diff(previous, new):
    """What moved: [(task, old_start, new_start, old_res, new_res)]."""
    out = []
    for t, v in new.items():
        p = previous.get(t)
        if p and (p["start"] != v["start"] or p["res"] != v["res"]):
            out.append((t, p["start"], v["start"], p["res"], v["res"]))
    return out
