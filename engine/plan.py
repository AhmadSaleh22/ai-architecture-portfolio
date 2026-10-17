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
from check_schedule import check_schedule  # noqa: E402
from model import build, clock, kpis, load_config, print_schedule  # noqa: E402


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

    prob = build(load_config(a.config), a.orders, a.start)
    t = time.time()
    if a.solver == "rules":
        from solve_rules import solve
        sched = solve(prob)
    else:
        from solve_cpsat import solve
        sched = solve(prob, seconds=a.seconds)
    dt = time.time() - t

    print(f"== {prob.cfg['meta']['name']} | {a.solver} | {len(prob.orders)} orders, {len(prob.tasks)} tasks | {dt:.1f}s")
    if not a.quiet:
        print_schedule(prob, sched)
    viol = check_schedule(prob, sched)
    k = kpis(prob, sched)
    print("\n  KPIs:", json.dumps({x: y for x, y in k.items() if x != "late"}, ensure_ascii=False))
    for oid in k["late"]:
        o = prob.orders[oid]
        from model import order_completion
        c = order_completion(prob, sched, oid)
        print(f"    late: {oid} ({o.cls}, prio {o.priority}) due {clock(prob, o.due)}, done {clock(prob, c)}, +{(c - o.due) / 60:.1f} h")
    print(f"  Check: {'PASS, 0 violations' if not viol else f'FAIL, {len(viol)} violations'}")
    for x in viol[:15]:
        print("    -", x)
    if a.out:
        Path(a.out).write_text(json.dumps({"start": a.start, "solver": a.solver, "kpis": k, "violations": viol,
                                           "tasks": sched}, indent=1))
    sys.exit(1 if viol else 0)


if __name__ == "__main__":
    main()
