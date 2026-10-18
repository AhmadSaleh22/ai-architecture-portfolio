"""Job-level KPIs, the same for every domain."""


def completion(prob, sched, jid):
    ends = [sched[t]["end"] for t in prob.jobs[jid].last if t in sched]
    return max(ends) if ends else None


def kpis(prob, sched, rejected=()):
    rejected = set(rejected)
    late, wt, lateq1, pref = [], 0.0, 0.0, []
    for j in prob.jobs.values():
        if j.id in rejected:
            continue
        c = completion(prob, sched, j.id)
        if c is None or j.due is None:
            continue
        t = max(0, c - j.due)
        if t > 0:
            late.append(j.id)
            if j.priority == 1:
                lateq1 += j.qty
        wt += j.weight * t / 60
    for tid, s in sched.items():
        p = prob.tasks[tid].preferred
        if p:
            pref.append(max(0, p[0] - s["start"], s["start"] - p[1]))
    changed = sum(1 for tid, s in sched.items() if tid in prob.previous and
                  (prob.previous[tid]["start"] != s["start"] or prob.previous[tid]["res"] != s["res"]))
    return {"jobs": len(prob.jobs), "scheduled": len(prob.jobs) - len(rejected), "rejected": sorted(rejected),
            "late_jobs": len(late), "late": late, "late_qty_priority1": round(lateq1, 1),
            "weighted_tardiness_h": round(wt, 1), "setup_minutes": sum(s.get("setup", 0) for s in sched.values()),
            "avg_pref_deviation_min": round(sum(pref) / len(pref), 1) if pref else 0,
            "moved_vs_previous": changed}
