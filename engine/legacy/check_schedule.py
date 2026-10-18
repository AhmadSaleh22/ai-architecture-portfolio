"""Independent constraint checker. A schedule is released only with 0 violations.

It re-derives everything from the config and the problem; it trusts nothing the solver says
except (resource, start, end) per task.
"""
from collections import defaultdict

from model import busy_span, duration, people_need, setup_minutes, setup_people


def check_schedule(prob, sched):
    v = []
    res, cfg = prob.cfg["resources"], prob.cfg
    # 1. every task scheduled once, on an eligible resource, with the right duration
    for tid, t in prob.tasks.items():
        s = sched.get(tid)
        if not s:
            v.append(f"{tid}: not scheduled")
            continue
        if s["resource"] not in t.eligible:
            v.append(f"{tid}: resource {s['resource']} not eligible")
        d = duration(res[s["resource"]], t.qty)
        if s["end"] - s["start"] != d:
            v.append(f"{tid}: duration {s['end'] - s['start']} != {d}")
        if s["start"] < t.release:
            v.append(f"{tid}: starts before the order is released")
    if v:
        return v
    # 2. calendar: task (and its setup) inside one working window
    by_res = defaultdict(list)
    for tid, s in sched.items():
        by_res[s["resource"]].append((s["start"], s["end"], tid))
    real_setup = {}
    for rid, rows in by_res.items():
        rows.sort()
        prev_attrs, prev_end = None, None
        for a, b, tid in rows:
            su = setup_minutes(res[rid], prev_attrs, prob.tasks[tid].attrs)
            real_setup[tid] = su
            if prev_end is not None and a - su < prev_end:
                v.append(f"{rid}: {tid} overlaps the previous task or its {su} min setup")
            if not any(w0 <= a - su and b <= w1 for w0, w1 in prob.windows[rid]):
                v.append(f"{rid}: {tid} ({a}-{b}, setup {su}) is outside the working calendar")
            prev_attrs, prev_end = prob.tasks[tid].attrs, b
    # 3. people: never more busy than on duty, and only inside their calendar
    use = defaultdict(list)
    for rid, rows in by_res.items():
        prev = None
        for a, b, tid in sorted(rows):
            for pool, q, during in people_need(res[rid]):
                ps, pe = busy_span(a, b, during)
                use[pool].append((ps, pe, q, tid))
            sp = setup_people(res[rid], prev, prob.tasks[tid].attrs)
            if sp:
                use[sp].append((a - real_setup[tid], a, 1, tid + ":setup"))
            prev = prob.tasks[tid].attrs
    for pool, rows in use.items():
        cap = cfg["people"][pool]["count"]
        for a, b, q, tid in rows:
            if not any(w0 <= a and b <= w1 for w0, w1 in prob.people_windows[pool]):
                v.append(f"people {pool}: {tid} outside their working hours")
        for p in sorted({a for a, *_ in rows}):
            n = sum(q for a, b, q, _ in rows if a <= p < b)
            if n > cap:
                who = [t for a, b, q, t in rows if a <= p < b]
                v.append(f"people {pool}: {n} needed at t={p}, only {cap} on duty ({', '.join(who)})")
    # 4. precedence and lags
    for a, b, lo, hi in prob.preds:
        gap = sched[b]["start"] - sched[a]["end"]
        if gap < lo:
            v.append(f"{b} starts {gap} min after {a}; minimum is {lo}")
        if hi is not None and gap > hi:
            v.append(f"{b} starts {gap} min after {a}; maximum is {hi}")
    # 5. batches: capacity, one key per batch, demand covered
    need = defaultdict(float)
    for tid, t in prob.tasks.items():
        if t.kind != "batch":
            continue
        cap = res[sched[tid]["resource"]]["capacity"]
        if not cap["min"] - 1e-6 <= t.qty <= cap["max"] + 1e-6:
            v.append(f"{tid}: batch size {t.qty} outside [{cap['min']}, {cap['max']}]")
        if sum(q for _, _, q in t.loads) > t.qty + 1e-3:
            v.append(f"{tid}: loads exceed batch size")
        owners = {prob.orders[o].customer if cfg["order_classes"][prob.orders[o].cls]["owner"] == "customer" else "own"
                  for o, _, _ in t.loads}
        if len(owners) > 1:
            v.append(f"{tid}: mixes material of different owners {sorted(owners)}")
        for o, m, q in t.loads:
            need[(o, t.stage, m)] += q
    from model import _loads
    for o in prob.orders.values():
        for s in cfg["stages"]:
            if s.get("batching") and s["id"] in cfg["products"][o.product]["route"] and not prob.progress:
                for m, q, _ in _loads(cfg, s["id"], o):
                    if need[(o.id, s["id"], m)] < q - 1e-2:
                        v.append(f"{o.id}: {m} covered {need[(o.id, s['id'], m)]:.2f} of {q:.2f}")
    return v
