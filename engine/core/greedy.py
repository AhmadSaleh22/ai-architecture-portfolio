"""Greedy list scheduler: fast, any size, and the warm start for CP-SAT.

Rules:
  1. Jobs by due DAY, then priority, then due time (pure priority starves low-priority jobs).
     Frozen tasks (repair mode) are placed first, exactly where they were.
  2. A job pulls its tasks in order (and their predecessors first, e.g. the batches it needs).
  3. Each task goes to the primary candidate where it can START earliest: after its predecessors
     (+ min lag), after the previous task on that resource (+ setup), inside working windows,
     on an allowed start, and when its other requirements (people, groups, rooms) are free.
  4. A task of an optional job that cannot be placed rejects the whole job (rolled back).
In plan mode primaries are filled forward in time; in insert mode (offer) gaps are used.
"""
import bisect
import copy
from collections import defaultdict

from .model import inside, setup_minutes, span

BIG = 10 ** 9


class Timeline:
    """What is already booked: per-resource usage and the sequence on each resource."""

    def __init__(self, prob):
        self.p = prob
        self.busy = defaultdict(list)      # resource -> [(a, b, qty, task)]
        self.seq = defaultdict(list)       # resource -> [(start, end, task)] tasks it was primary for
        self.sched = {}

    # ---- queries -------------------------------------------------------------------------
    def used(self, rid, a, b):
        """Max units in use on rid over [a, b) and the earliest time something there ends."""
        rows = [r for r in self.busy[rid] if r[0] < b and a < r[1]]
        if not rows:
            return 0, None
        pts = sorted({a} | {r[0] for r in rows if a < r[0] < b})
        peak = 0
        for p in pts:
            peak = max(peak, sum(r[2] for r in rows if r[0] <= p < r[1]))
        return peak, min(r[1] for r in rows)

    def fits(self, rid, a, b, q):
        if a >= b:
            return True, None
        res = self.p.resources[rid]
        if not inside(res.windows, a, b):
            return False, a + 15
        used, nxt = self.used(rid, a, b)
        if used + q > res.capacity:
            return False, nxt
        return True, None

    def neighbours(self, rid, start):
        rows = sorted(self.seq[rid])
        i = bisect.bisect_left([r[0] for r in rows], start)
        prev = rows[i - 1] if i > 0 else None
        nxt = rows[i] if i < len(rows) else None
        return prev, nxt

    def secondaries(self, t, start, end, su):
        """Pick a candidate for each non-primary requirement, or say when to try again."""
        chosen = []
        for req in t.requirements[1:]:
            ps, pe = span(start, end, req.during)
            bump, pick = None, None
            for c in req.candidates:
                ok, nb = self.fits(c, ps, pe, req.qty)
                if ok and req.setup_qty and su:
                    ok, nb = self.fits(c, start - su, start, req.setup_qty)
                if ok:
                    pick = c
                    break
                if nb is not None:
                    bump = nb if bump is None else min(bump, nb)
            if pick is None:
                return None, bump
            chosen.append(pick)
        return chosen, None

    # ---- placement -----------------------------------------------------------------------
    def earliest(self, tid, est, append_only=True, only_at=None, prefer=None):
        """Earliest feasible (primary, start, end, setup, secondaries) for a task, or None.
        On a tie the first candidate wins; prefer puts one candidate first (repair keeps the old room)."""
        t = self.p.tasks[tid]
        best = None
        cands = list(t.requirements[0].candidates)
        if prefer in cands:
            cands.remove(prefer)
            cands.insert(0, prefer)
        for rid in cands:
            res = self.p.resources[rid]
            d = t.duration[rid]
            rows = sorted(self.seq[rid])
            last_end = rows[-1][1] if rows else 0
            last_attrs = self.p.tasks[rows[-1][2]].attrs if rows else None
            s0 = max(est, 0)
            if append_only:
                su0 = setup_minutes(res, last_attrs, t.attrs)
                s0 = max(est - su0, last_end)
            if only_at is not None:
                s0 = only_at
            for _ in range(20000):
                if append_only:
                    prev_attrs, su, nxt = last_attrs, setup_minutes(res, last_attrs, t.attrs), None
                else:
                    prev, nxt = self.neighbours(rid, s0)
                    prev_attrs = self.p.tasks[prev[2]].attrs if prev else None
                    su = setup_minutes(res, prev_attrs, t.attrs)
                    if prev and s0 < prev[1]:
                        if only_at is not None:
                            break
                        s0 = prev[1]
                        continue
                w = next(((a, b) for a, b in res.windows if b > s0), None)
                if w is None:
                    break
                s0 = max(s0, w[0])
                if only_at is not None and s0 != only_at:
                    break
                start, end = s0 + su, s0 + su + d
                if start < est:
                    s0 = est - su
                    continue
                if end > w[1]:
                    if only_at is not None:
                        break
                    s0 = w[1]
                    continue
                if t.allowed_starts:
                    i = bisect.bisect_left(t.allowed_starts, start)
                    if i == len(t.allowed_starts):
                        break
                    if t.allowed_starts[i] != start:
                        if only_at is not None:
                            break
                        s0 = t.allowed_starts[i] - su
                        continue
                if t.deadline is not None and end > t.deadline:
                    break
                if not append_only and nxt is not None:
                    # the next task on this resource must still get its setup after us
                    if end + setup_minutes(res, t.attrs, self.p.tasks[nxt[2]].attrs) > nxt[0]:
                        if only_at is not None:
                            break
                        s0 = nxt[1]
                        continue
                ok, bump = self.fits(rid, s0, end, 1)
                if ok:
                    picks, bump = self.secondaries(t, start, end, su)
                    ok = picks is not None
                if ok:
                    if best is None or start < best[1]:
                        best = (rid, start, end, su, picks)
                    break
                if only_at is not None:
                    break
                s0 = max((bump if bump is not None else s0 + 15), s0 + 1)
        return best

    def commit(self, tid, rid, start, end, su, picks):
        t = self.p.tasks[tid]
        self.sched[tid] = {"resource": rid, "res": [rid] + list(picks), "start": start, "end": end, "setup": su}
        self.seq[rid].append((start, end, tid))
        self.busy[rid].append((start - su, end, 1, tid))
        for req, c in zip(t.requirements[1:], picks):
            ps, pe = span(start, end, req.during)
            self.busy[c].append((ps, pe, req.qty, tid))
            if req.setup_qty and su:
                self.busy[c].append((start - su, start, req.setup_qty, tid + ":setup"))

    def load(self, sched):
        """Book an existing schedule (in time order) so new work can be fitted around it."""
        for tid, v in sorted(sched.items(), key=lambda kv: kv[1]["start"]):
            self.commit(tid, v["res"][0], v["start"], v["end"], v.get("setup", 0), v["res"][1:])
        return self

    def snapshot(self):
        return copy.deepcopy((dict(self.busy), dict(self.seq), self.sched))

    def restore(self, snap):
        b, s, sc = copy.deepcopy(snap)
        self.busy, self.seq, self.sched = defaultdict(list, b), defaultdict(list, s), sc


def preds_of(prob):
    out = defaultdict(list)
    for a, b, lo, hi in prob.preds:
        out[b].append((a, lo))
    return out


def solve(prob, append_only=True, job_key=None):
    """Returns (schedule, rejected_jobs). job_key overrides the job order (repair keeps the old order)."""
    tl = Timeline(prob)
    P = preds_of(prob)
    rejected = set()

    for tid, f in sorted(prob.frozen.items(), key=lambda kv: kv[1]["start"]):
        t = prob.tasks[tid]
        rid = f["res"][0]
        tl.commit(tid, rid, f["start"], f["start"] + t.duration[rid], f.get("setup", 0), f["res"][1:])

    min_start = {}                           # raised when a max lag was broken (retry later)

    def pull(tid, stack):
        if tid in tl.sched:
            return True
        for a, _ in P[tid]:
            if not pull(a, stack):
                return False
        t = prob.tasks[tid]
        est = max(t.release, min_start.get(tid, 0), t.preferred[0] if t.preferred else 0)
        for a, lo in P[tid]:
            est = max(est, tl.sched[a]["end"] + lo)
        best = tl.earliest(tid, est, append_only)
        if best is None:
            return False
        tl.commit(tid, *best)
        return True

    def key(j):
        due = j.due if j.due is not None else BIG
        return (due // 1440, j.priority, due, j.id)

    maxlag = [(a, b, hi) for a, b, lo, hi in prob.preds if hi is not None]
    for j in sorted(prob.jobs.values(), key=job_key or key):
        chain = sorted(prob.job_tasks(j.id), key=lambda t: (t.seq, t.id))
        snap = tl.snapshot()
        ids = {t.id for t in chain}
        for _ in range(25):
            ok = all(pull(t.id, None) for t in chain)
            broken = [(a, b, hi) for a, b, hi in maxlag if ok and a in ids and b in ids and a not in prob.frozen
                      and tl.sched[b]["start"] - tl.sched[a]["end"] > hi]
            if not broken:
                break
            # start the earlier step later so the next one follows within its max lag, and retry
            for a, b, hi in broken:
                d = tl.sched[a]["end"] - tl.sched[a]["start"]
                min_start[a] = max(min_start.get(a, 0), tl.sched[b]["start"] - hi - d)
            tl.restore(snap)
        if not ok:
            if j.optional:
                tl.restore(snap)
                rejected.add(j.id)
                continue
            else:
                bad = next(t.id for t in chain if t.id not in tl.sched)
                raise RuntimeError(f"cannot place {bad} (job {j.id}) inside the calendar horizon")
    return tl.sched, sorted(rejected)
