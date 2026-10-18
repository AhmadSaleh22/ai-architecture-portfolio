"""Rule-based scheduler (greedy list scheduling). Good enough for a small factory.

Rules, in order:
  1. Orders by due day, then priority. Each order pulls its whole chain (its batches first).
  2. Each task goes to the eligible resource where it can START earliest, after its predecessors
     (+ min lag), the resource's previous task (+ sequence-dependent setup), inside a working window,
     and when the people it needs are free.
  3. Resources are filled forward in time (no inserting into gaps), people can be used in any gap.
It does not look ahead, so it can break max lags or make avoidable setups: the checker will say so.
"""
from collections import defaultdict

from model import busy_span, duration, people_need, setup_minutes, setup_people


def _window_at(windows, t):
    for s, e in windows:
        if e > t:
            return (max(s, t), e)
    return None


def _people_free(busy, pool, cap, s, e, q):
    """True if q more people of the pool fit in [s, e)."""
    if s >= e:
        return True, None
    pts = sorted({s} | {a for a, b, _ in busy[pool] if s < a < e})
    for p in pts:
        used = sum(n for a, b, n in busy[pool] if a <= p < b)
        if used + q > cap:
            nxt = min(b for a, b, n in busy[pool] if a <= p < b)
            return False, nxt
    return True, None


def _in_people_calendar(pw, pool, s, e):
    return s >= e or any(a <= s and e <= b for a, b in pw[pool])


def solve(prob):
    cfg, res = prob.cfg, prob.cfg["resources"]
    people = {p: v["count"] for p, v in cfg["people"].items()}
    preds_of = defaultdict(list)
    for a, b, lo, hi in prob.preds:
        preds_of[b].append((a, lo))
    sched, busy = {}, defaultdict(list)
    last = {r: (0, None) for r in res}               # resource -> (end, attrs of last task)

    def place(tid):
        t = prob.tasks[tid]
        est = t.release
        for a, lo in preds_of[tid]:
            est = max(est, sched[a]["end"] + lo)
        best = None
        for rid in t.eligible:
            r = res[rid]
            d = duration(r, t.qty)
            su = setup_minutes(r, last[rid][1], t.attrs)
            su_pool = setup_people(r, last[rid][1], t.attrs)
            needs = people_need(r)
            s0 = max(est - su, last[rid][0])
            for _ in range(10000):
                w = _window_at(prob.windows[rid], s0)
                if w is None:
                    break
                s0 = w[0]
                if s0 + su + d > w[1]:
                    s0 = w[1]
                    continue
                start, end = s0 + su, s0 + su + d
                ok, bump = True, None
                for pool, q in ([(su_pool, 1)] if su_pool else []):
                    if not _in_people_calendar(prob.people_windows, pool, s0, start):
                        ok, bump = False, s0 + 15
                        break
                    f, nb = _people_free(busy, pool, people[pool], s0, start, q)
                    if not f:
                        ok, bump = False, nb
                        break
                if ok:
                    for pool, q, during in needs:
                        ps, pe = busy_span(start, end, during)
                        if not _in_people_calendar(prob.people_windows, pool, ps, pe):
                            ok, bump = False, s0 + 15
                            break
                        f, nb = _people_free(busy, pool, people[pool], ps, pe, q)
                        if not f:
                            ok, bump = False, nb - su if nb - su > s0 else nb
                            break
                if ok:
                    if best is None or start < best[1]:
                        best = (rid, start, end, su, su_pool, needs)
                    break
                s0 = max(bump, s0 + 1)
        if best is None:
            raise RuntimeError(f"cannot place {tid} inside the calendar horizon")
        rid, start, end, su, su_pool, needs = best
        sched[tid] = {"resource": rid, "start": start, "end": end, "setup": su}
        last[rid] = (end, t.attrs)
        if su_pool:
            busy[su_pool].append((start - su, start, 1))
        for pool, q, during in needs:
            ps, pe = busy_span(start, end, during)
            busy[pool].append((ps, pe, q))

    def pull(tid):
        if tid in sched:
            return
        for a, _ in preds_of[tid]:
            pull(a)
        place(tid)

    # due DAY first, priority breaks ties inside the same day (pure priority starves low-priority orders)
    for o in sorted(prob.orders.values(), key=lambda o: (o.due // 1440, o.priority, o.due, o.id)):
        chain = [tid for tid, t in prob.tasks.items() if o.id in t.orders]
        # batches first (in key order), then the order's own tasks along the route
        route = prob.cfg["products"][o.product]["route"]
        chain.sort(key=lambda tid: (route.index(prob.tasks[tid].stage), tid))
        for tid in chain:
            pull(tid)
    return sched
