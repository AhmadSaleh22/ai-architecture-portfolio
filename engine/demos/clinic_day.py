"""Clinic demo: plan the week, offer slots to a new WhatsApp request, then repair after a disruption.

    uv run python engine/demos/clinic_day.py
"""
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))

from adapters import services as sv  # noqa: E402
from core import cpsat, modes  # noqa: E402
from core.check import check  # noqa: E402
from core.kpi import kpis  # noqa: E402
from core.model import subtract  # noqa: E402

START = "2026-10-18T07:00"
cfg = sv.load_config(ENGINE / "configs/clinic.yaml")
reqs = sv.read_requests(ENGINE / "samples/clinic_requests.csv")


def show_kpis(label, prob, sched, rej):
    k = kpis(prob, sched, rej)
    print(f"  {label}: {k['scheduled']}/{k['jobs']} booked, late {k['late_jobs']}, "
          f"avg distance from preferred time {k['avg_pref_deviation_min']} min, cleaning {k['setup_minutes']} min, "
          f"check: {'PASS' if not check(prob, sched, rej) else check(prob, sched, rej)}")


# 1. plan the week ---------------------------------------------------------------------------
prob = sv.build(cfg, reqs, START)
plan, rej = cpsat.solve(prob, seconds=10)
print("== 1. Weekly plan (CP-SAT)")
show_kpis("plan", prob, plan, rej)

# 2. a new request arrives on WhatsApp: offer 3 options without moving anyone ------------------
new = {"id": "N01", "class": "routine", "service": "cardio_visit", "who": "new patient (WhatsApp)",
       "release": START, "pref_from": "2026-10-20T09:00", "pref_to": "2026-10-20T11:00"}
prob2 = sv.build(cfg, reqs + [new], START)
opts = modes.offer(prob2, plan, "N01", k=3)
print("\n== 2. New request N01: cardiology, prefers Tuesday 09:00-11:00. Options:")
for i, o in enumerate(opts, 1):
    print(f"  {i}. " + " -> ".join(f"{prob2.tasks[t].info['label']} {prob2.clock(v['start'])} "
                                    f"({', '.join(v['res'])})" for t, v in o["tasks"].items()))
plan2 = modes.accept(plan, opts[0])
show_kpis("after booking option 1", prob2, plan2, rej)

# 3. disruption: Dr Hana calls in sick on Sunday and an emergency walks in at 09:00 -------------
emergency = {"id": "E01", "class": "emergency", "service": "minor_procedure", "who": "walk-in, deep cut",
             "release": "2026-10-18T09:00", "attr_hygiene": "infectious"}
prob3 = sv.build(cfg, reqs + [new, emergency], START)
now = 120                                                       # 09:00
sick = (now, prob3.resources["dr_hana"].windows[0][1])           # she goes home at 09:00
prob3.resources["dr_hana"].windows = subtract(prob3.resources["dr_hana"].windows, [sick])
before = {t: v for t, v in plan2.items()}
# tasks that already ran or are running stay; Dr Hana's Sunday tasks that have not started must move
broken = {t for t, v in before.items() if "dr_hana" in v["res"] and v["start"] >= now and v["start"] < sick[1]}
previous = {t: v for t, v in before.items() if t not in broken}
repaired, rej3 = modes.repair(prob3, previous, now, freeze_min=0, seconds=10)
print("\n== 3. Dr Hana is sick on Sunday, emergency E01 at 09:00 -> repair")
show_kpis("repaired", prob3, repaired, rej3)
e = repaired["E01:procedure"]
print(f"  emergency E01 treated at {prob3.clock(e['start'])} by {e['res'][1]} in {e['res'][0]}")
moved = modes.diff(before, repaired)
print(f"  {len(moved)} appointments moved (patients get a WhatsApp message):")
for t, a, b, ra, rb in moved:
    print(f"    {t:<16} {prob3.clock(a)} {ra[1] if len(ra) > 1 else ra[0]:<9} -> {prob3.clock(b)} {rb[1] if len(rb) > 1 else rb[0]}")
moved_jobs = {prob3.tasks[m[0]].jobs[0] for m in moved}
print(f"  {len({prob3.tasks[t].jobs[0] for t in before}) - len(moved_jobs)} appointments unchanged"
      + (f", not placed: {', '.join(rej3)}" if rej3 else ""))
