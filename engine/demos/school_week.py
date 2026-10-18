"""School demo: build the weekly timetable, then repair it when a teacher is absent on Tuesday.

    uv run python engine/demos/school_week.py
"""
import sys
import time
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))

from adapters import school  # noqa: E402
from adapters import services as sv  # noqa: E402
from core import cpsat, greedy, modes  # noqa: E402
from core.check import check  # noqa: E402
from core.kpi import kpis  # noqa: E402
from core.model import subtract  # noqa: E402

START = "2026-10-18T07:00"
cfg = sv.load_config(ENGINE / "configs/school.yaml")
prob = school.build(cfg, START)
print(f"== {prob.meta['name']}: {len(prob.jobs)} lessons, {len(prob.resources)} resources")
for name in ("greedy", "cpsat"):
    t = time.time()
    s, r = greedy.solve(prob) if name == "greedy" else cpsat.solve(prob, seconds=20)
    k = kpis(prob, s, r)
    print(f"  {name:<6} {time.time() - t:4.1f}s  placed {k['scheduled']}/{k['jobs']}  "
          f"avg days off the spread target {k['avg_pref_deviation_min'] / 1440:.2f}  "
          f"check: {'PASS' if not check(prob, s, r) else check(prob, s, r)[:3]}")
plan, rej = s, r
for who in ("G10A", "T_cs"):
    school.print_grid(prob, plan, who)

# The English teacher is absent on Tuesday. Monday is over (it is Tuesday 07:00 now).
now = 2 * 1440                                   # Tue 07:00 (t0 is Sun 07:00)
p2 = school.build(sv.load_config(ENGINE / "configs/school.yaml"), START)
tue = [(now, now + 1440)]
p2.resources["T_eng"].windows = subtract(p2.resources["T_eng"].windows, tue)
previous = {t: v for t, v in plan.items() if not ("T_eng" in v["res"] and tue[0][0] <= v["start"] < tue[0][1])}
fixed, rej2 = modes.repair(p2, previous, now, freeze_min=0, seconds=20, stability_rank=1)
moved = modes.diff(plan, fixed)
print(f"\n== English teacher absent on Tuesday -> repair: {len(moved)} lessons moved, "
      f"placed {len(p2.jobs) - len(rej2)}/{len(p2.jobs)}, check: {'PASS' if not check(p2, fixed, rej2) else 'FAIL'}")
for t, a, b, ra, rb in moved:
    print(f"    {t:<24} {p2.clock(a)} {ra[0]:<7} -> {p2.clock(b)} {rb[0]}")
