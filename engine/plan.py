"""Plan a factory: config + orders -> schedule -> independent check -> KPIs.

    python3 engine/plan.py engine/configs/coffee_roastery.yaml engine/samples/coffee_orders.csv \\
        --start 2026-10-18T08:00 --solver rules|cpsat [--out schedule.json] [--quiet]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from adapters import factory as fa  # noqa: E402
from core import cpsat, greedy  # noqa: E402
from core.check import check  # noqa: E402
from core.kpi import completion  # noqa: E402
from model import build, clock, load_config, print_schedule  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("orders")
    ap.add_argument("--start", required=True)
    ap.add_argument("--solver", default="rules", choices=["rules", "cpsat"])
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--out")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    fp = build(load_config(a.config), a.orders, a.start)
    prob = fa.to_core(fp)
    t = time.time()
    sched, rej = greedy.solve(prob) if a.solver == "rules" else cpsat.solve(prob, seconds=a.seconds)
    dt = time.time() - t

    print(f"== {fp.cfg['meta']['name']} | {a.solver} | {len(fp.orders)} orders, {len(fp.tasks)} tasks | {dt:.1f}s")
    if not a.quiet:
        print_schedule(fp, sched)
    viol = check(prob, sched, rej)
    k = fa.kpis(prob, sched, rej)
    print("\n  KPIs:", json.dumps({x: y for x, y in k.items() if x != "late"}, ensure_ascii=False))
    for oid in k["late"]:
        o = fp.orders[oid]
        c = completion(prob, sched, oid)
        print(f"    late: {oid} ({o.cls}, prio {o.priority}) due {clock(fp, o.due)}, done {clock(fp, c)}, +{(c - o.due) / 60:.1f} h")
    print(f"  Check: {'PASS, 0 violations' if not viol else f'FAIL, {len(viol)} violations'}")
    for x in viol[:15]:
        print("    -", x)
    if a.out:
        Path(a.out).write_text(json.dumps({"start": a.start, "solver": a.solver, "kpis": k, "violations": viol,
                                           "tasks": sched}, indent=1))
    sys.exit(1 if viol else 0)


if __name__ == "__main__":
    main()
