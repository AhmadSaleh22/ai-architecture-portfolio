"""Independent checker: the release gate. It trusts only (resources, start, end) per task and
re-derives setups, calendars, capacities and lags from the problem itself."""
from collections import defaultdict

from .model import inside, setup_minutes, span


def check(prob, sched, rejected=()):
    v = []
    rejected = set(rejected)
    for jid in rejected:
        if not prob.jobs[jid].optional:
            v.append(f"job {jid} was dropped but is not optional")
    for tid, t in prob.tasks.items():
        dropped = t.jobs and all(j in rejected for j in t.jobs)
        s = sched.get(tid)
        if s is None:
            if not dropped:
                v.append(f"{tid}: not scheduled")
            continue
        if dropped:
            v.append(f"{tid}: scheduled although its job was rejected")
        res = s["res"]
        if len(res) != len(t.requirements):
            v.append(f"{tid}: {len(res)} resources for {len(t.requirements)} requirements")
            continue
        for req, r in zip(t.requirements, res):
            if r not in req.candidates:
                v.append(f"{tid}: {r} is not a candidate")
        if s["end"] - s["start"] != t.duration.get(res[0]):
            v.append(f"{tid}: duration {s['end'] - s['start']} != {t.duration.get(res[0])}")
        if s["start"] < t.release:
            v.append(f"{tid}: starts before its release")
        if t.deadline is not None and s["end"] > t.deadline:
            v.append(f"{tid}: ends after its deadline")
        if t.allowed_starts and s["start"] not in set(t.allowed_starts):
            v.append(f"{tid}: start {s['start']} is not an allowed start")
        f = prob.frozen.get(tid)
        if f and (f["start"] != s["start"] or f["res"] != s["res"]):
            v.append(f"{tid}: frozen task was moved")
    if v:
        return v

    # sequence on each primary: setups, overlaps, calendar
    seq = defaultdict(list)
    for tid, s in sched.items():
        seq[s["res"][0]].append((s["start"], s["end"], tid))
    real_su = {}
    for rid, rows in seq.items():
        res = prob.resources[rid]
        rows.sort()
        prev_attrs, prev_end = None, None
        for a, b, tid in rows:
            su = setup_minutes(res, prev_attrs, prob.tasks[tid].attrs)
            real_su[tid] = su
            if res.capacity == 1 and prev_end is not None and a - su < prev_end:
                v.append(f"{rid}: {tid} overlaps the previous task or its {su} min setup")
            if not inside(res.windows, a - su, b):
                v.append(f"{rid}: {tid} ({prob.clock(a)}, setup {su}) is outside working hours")
            prev_attrs, prev_end = prob.tasks[tid].attrs, b

    # every resource: capacity and calendar for all its uses
    use = defaultdict(list)
    for tid, s in sched.items():
        t = prob.tasks[tid]
        a, b, r0 = s["start"], s["end"], s["res"][0]
        use[r0].append((a - real_su.get(tid, 0), b, 1, tid))
        for req, r in zip(t.requirements[1:], s["res"][1:]):
            ps, pe = span(a, b, req.during)
            use[r].append((ps, pe, req.qty, tid))
            if not inside(prob.resources[r].windows, ps, pe):
                v.append(f"{r}: {tid} outside its working hours")
            su = real_su.get(tid, 0)
            if req.setup_qty and su:
                use[r].append((a - su, a, req.setup_qty, tid + ":setup"))
                if not inside(prob.resources[r].windows, a - su, a):
                    v.append(f"{r}: setup before {tid} outside its working hours")
    for rid, rows in use.items():
        cap = prob.resources[rid].capacity
        for p in sorted({r[0] for r in rows}):
            n = sum(q for a, b, q, _ in rows if a <= p < b)
            if n > cap:
                who = [x for a, b, q, x in rows if a <= p < b]
                v.append(f"{rid}: {n} in use at {prob.clock(p)}, capacity {cap} ({', '.join(who)})")
                break

    for a, b, lo, hi in prob.preds:
        if a not in sched or b not in sched:
            continue
        gap = sched[b]["start"] - sched[a]["end"]
        if gap < lo:
            v.append(f"{b} starts {gap} min after {a}; minimum is {lo}")
        if hi is not None and gap > hi:
            v.append(f"{b} starts {gap} min after {a}; maximum is {hi}")
    for f in prob.extra_checks:
        v += f(prob, sched)
    return v
