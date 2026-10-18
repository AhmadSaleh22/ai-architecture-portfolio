"""School adapter: expand a weekly course load into lesson requests for the services adapter.

Each lesson needs: its teacher (fixed), its class group (fixed) and a room of the right kind with
enough seats. Session i of a course with n sessions per week "prefers" day round(i * 5 / n), which
spreads the course over the week (soft: the solver may still move it).
"""
from datetime import datetime, timedelta

from . import services as sv


def requests(cfg, start):
    t0 = datetime.fromisoformat(start)
    cfg.setdefault("services", {})
    out = []
    for c in cfg["courses"]:
        for g in c["groups"]:
            key = f"{c['course']}_{g}"
            cfg["services"][key] = {"steps": [{
                "id": "lesson", "label": f"{c['course']} {g}", "duration": 45,
                "primary": {"type": "room", "attr": {"kind": c["room"]}, "min": {"seats": "size"}},
                "needs": [{"id": c["teacher"]}, {"id": g}]}]}
            size = cfg["resources"][g]["attrs"]["size"]
            for i in range(c["sessions"]):
                day = int(i * 5 / c["sessions"])
                d0 = t0.replace(hour=0, minute=0) + timedelta(days=day)
                out.append({"id": f"{c['course']}-{g}-{i + 1}", "class": "lesson", "service": key, "size": size,
                            "who": g, "release": start,
                            "pref_from": (d0 + timedelta(hours=8)).isoformat(),
                            "pref_to": (d0 + timedelta(hours=12, minutes=20)).isoformat()})
    return out


def build(cfg, start):
    return sv.build(cfg, requests(cfg, start), start)


def print_grid(prob, sched, who):
    """Timetable of one group or teacher: days x periods."""
    periods = prob.meta["cfg"]["meta"]["periods"]
    days = ["Sun", "Mon", "Tue", "Wed", "Thu"]
    cell = {}
    for tid, s in sched.items():
        if who in s["res"]:
            t = prob.t0 + timedelta(minutes=s["start"])
            label = prob.tasks[tid].info["label"].split()[0]
            other = [r for r in s["res"] if r != who and not r.startswith("R")]
            cell[(t.strftime("%a"), t.strftime("%H:%M"))] = f"{label}·{s['res'][0]}"
    print(f"\n  {who}")
    print("        " + "".join(f"{p:<16}" for p in periods))
    for d in days:
        print(f"  {d:<6}" + "".join(f"{cell.get((d, p), '-'):<16}" for p in periods))
