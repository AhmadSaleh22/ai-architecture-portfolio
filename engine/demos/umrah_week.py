"""Travel demo: plan an Umrah operator's week, then repair after a flight delay.

    uv run python engine/demos/umrah_week.py
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))

from adapters import services as sv  # noqa: E402
from adapters import travel  # noqa: E402
from core import cpsat, greedy, modes  # noqa: E402
from core.check import check  # noqa: E402
from core.kpi import kpis  # noqa: E402

START = "2026-11-01T00:00"
cfg = sv.load_config(ENGINE / "configs/umrah.yaml")
groups = travel.read_groups(ENGINE / "samples/umrah_groups.csv")
prob = travel.build(cfg, groups, START)

for name in ("greedy", "cpsat"):
    s, r = greedy.solve(prob) if name == "greedy" else cpsat.solve(prob, seconds=15)
    k = kpis(prob, s, r)
    print(f"== {name:<6} groups {k['scheduled']}/{k['jobs']}, late {k['late_jobs']}, "
          f"avg distance from preferred time {k['avg_pref_deviation_min']:.0f} min, turnaround {k['setup_minutes']} min, "
          f"check: {'PASS' if not check(prob, s, r) else check(prob, s, r)[:3]}")
plan = s


def show(p, sched):
    for tid, v in sorted(sched.items(), key=lambda kv: kv[1]["start"]):
        t = p.tasks[tid]
        guide = next((x for x in v["res"] if x.startswith("G_")), "")
        print(f"    {p.clock(v['start'])}-{p.clock(v['end'])[-5:]}  {t.jobs[0]:<6} {t.info['label']:<16} "
              f"{v['res'][0]:<6} {guide}")


show(prob, plan)

# GR_ID's flight lands 5 hours late. It is Sunday 03:00; nothing has started yet for GR_ID.
delayed = [dict(g) for g in groups]
for g in delayed:
    if g["group"] == "GR_ID":
        g["arrive"] = (datetime.fromisoformat(g["arrive"]) + timedelta(hours=5)).isoformat(timespec="minutes")
p2 = travel.build(cfg, delayed, START)
now = 180
previous = {t: v for t, v in plan.items() if not (t.startswith("GR_ID") and v["start"] >= now)}
fixed, rej = modes.repair(p2, previous, now, freeze_min=0, seconds=15)
moved = modes.diff(plan, fixed)
print(f"\n== GR_ID flight +5 h -> repair: {len(moved)} activities moved, "
      f"check: {'PASS' if not check(p2, fixed, rej) else check(p2, fixed, rej)[:3]}")
for t, a, b, ra, rb in moved:
    what = ", ".join(f"{x} -> {y}" for x, y in zip(ra, rb) if x != y) or "same resources"
    print(f"    {t:<18} {p2.clock(a)} -> {p2.clock(b)}   ({what})")
