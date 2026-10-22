"""Backtest: what would the engine have done with the same orders, day by day?

    uv run python engine/backtest.py engine/samples/factory_log_example.xlsx [--solver rules|cpsat]

Fair comparison (no peeking at the future):
  * Every morning at 08:00 the engine sees only the orders received up to that day.
  * It plans the next days, but only today's work is executed (tasks that start before tomorrow 08:00).
  * Breakdowns and gas outages from the log are applied when they happened, unknown in advance.
  * Tomorrow it replans from what is really done (roasted material is credited to each order).
Then: the factory (what the log says happened) vs. the engine, on the same orders.
"""
import argparse
import sys
from collections import defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).parent))
import import_excel as ix  # noqa: E402
from adapters import factory as fa  # noqa: E402
from core import cpsat, greedy  # noqa: E402
from model import build, load_config, order_from_row, route_of  # noqa: E402

DELIVER_BY = 22   # an order finished after 22:00 goes out the next morning


def delivered_date(dt):
    d = dt.date() if 6 <= dt.hour < DELIVER_BY else (dt + timedelta(hours=10)).date()
    while d.weekday() == 4:          # no deliveries on Friday
        d += timedelta(days=1)
    return d


def run(cfg, rows, events, start, end, solver_name, seconds):
    if solver_name == "rules":
        solve = greedy.solve
    else:
        solve = lambda p: cpsat.solve(p, seconds=seconds)  # noqa: E731
    progress = defaultdict(lambda: {"covered": defaultdict(float), "done": set()})
    done_at, batches = {}, []
    day = start
    while day < end:
        t0 = datetime.combine(day, time(8, 0))
        open_rows = [r for r in rows if r["order_id"] not in done_at
                     and datetime.fromisoformat(r["release"]) <= t0]
        if open_rows:
            orders = {r["order_id"]: order_from_row(r, cfg, t0) for r in open_rows}
            down = defaultdict(list)
            for ev in events:
                rid = ix.MACHINE.get(ev["machine"])
                a = int((ev["start"] - t0).total_seconds() // 60)
                b = a + int(ev["hours"] * 60)
                if rid and b > 0 and a < 1440:          # only today's events are known today
                    down[rid].append((max(a, 0), b))
            prob = build(cfg, None, t0, progress={k: v for k, v in progress.items()}, downtime=down, orders=orders)
            sched, _ = solve(fa.to_core(prob))
            for tid, s in sched.items():
                if s["start"] >= 1440:
                    continue                          # tomorrow's work: replanned tomorrow
                t = prob.tasks[tid]
                if t.kind == "batch":
                    for oid, m, q in t.loads:
                        progress[oid]["covered"][(t.stage, m)] += q
                    batches.append({"kg": t.qty, "minutes": s["end"] - s["start"], "orders": t.orders})
                else:
                    oid = t.orders[0]
                    progress[oid]["done"].add(t.stage)
                    o = orders[oid]
                    if set(route_of(cfg, o)) - {x["id"] for x in cfg["stages"] if x.get("batching")} <= progress[oid]["done"]:
                        done_at[oid] = t0 + timedelta(minutes=s["end"])
        day += timedelta(days=1)
    return done_at, batches


def summary(label, rows, delivered, batches, end):
    on_time = late = open_late = open_ok = 0
    days_late = []
    for r in rows:
        due = datetime.fromisoformat(r["due"]).date()
        d = delivered.get(r["order_id"])
        if d:
            if d > due:
                late += 1
                days_late.append((d - due).days)
            else:
                on_time += 1
        elif due < end:
            open_late += 1
        else:
            open_ok += 1
    kg = [b["kg"] for b in batches]
    return {"label": label, "on_time": on_time, "late": late, "avg_days_late": sum(days_late) / len(days_late) if days_late else 0,
            "open_past_due": open_late, "open_not_due": open_ok, "batches": len(kg),
            "avg_batch_kg": sum(kg) / len(kg) if kg else 0, "roaster_h": sum(b["minutes"] for b in batches) / 60,
            "green_kg": sum(kg)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--config", default=str(Path(__file__).parent / "configs/coffee_roastery.yaml"))
    ap.add_argument("--solver", default="rules", choices=["rules", "cpsat"])
    ap.add_argument("--seconds", type=float, default=4, help="CP-SAT time per day")
    a = ap.parse_args()

    cfg = load_config(a.config)
    wb = load_workbook(a.xlsx, data_only=True)
    orders, _ = ix.read_orders(wb, cfg)
    sheet_batches, _ = ix.read_batches(wb)
    events = ix.read_events(wb)
    rows = [o for o in orders if not o["rejected"]]
    start = min(datetime.fromisoformat(r["release"]).date() for r in rows)
    end = max(b["start"].date() for b in sheet_batches) + timedelta(days=1)   # the log's last day

    human_deliv = {r["order_id"]: datetime.fromisoformat(r["delivered"]).date() for r in rows if r["delivered"]}
    human_b = [{"kg": b["kg_in"], "minutes": b["minutes"]} for b in sheet_batches]
    done_at, eng_b = run(cfg, rows, events, start, end, a.solver, a.seconds)
    eng_deliv = {k: delivered_date(v) for k, v in done_at.items()}

    H = summary("factory (log)", rows, human_deliv, human_b, end)
    E = summary(f"engine ({a.solver})", rows, eng_deliv, eng_b, end)
    print(f"== Backtest {start} -> {end - timedelta(days=1)} | {len(rows)} orders "
          f"({sum(1 for o in orders if o['rejected'])} rejected, not replayed) | replanned every morning")
    fmt = [("on time", "on_time", "{:.0f}"), ("late", "late", "{:.0f}"), ("avg days late", "avg_days_late", "{:.1f}"),
           ("open, past due", "open_past_due", "{:.0f}"), ("open, not due yet", "open_not_due", "{:.0f}"),
           ("roast batches", "batches", "{:.0f}"), ("avg batch (kg green)", "avg_batch_kg", "{:.1f}"),
           ("green roasted (kg)", "green_kg", "{:.0f}"), ("roaster busy (h)", "roaster_h", "{:.0f}")]
    print(f"\n  {'':<22}{H['label']:>16}{E['label']:>18}")
    for name, k, f in fmt:
        print(f"  {name:<22}{f.format(H[k]):>16}{f.format(E[k]):>18}")
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        due = datetime.fromisoformat(r["due"]).date()
        for i, dl in enumerate((human_deliv, eng_deliv)):
            d = dl.get(r["order_id"])
            if (d and d > due) or (not d and due < end):
                by[r["class"]][i] += 1
    print("\n  late or past due, by customer type:  factory / engine")
    for c, (h, e) in sorted(by.items()):
        print(f"    {c:<16} {h:>3} / {e}")
    print("\n  Note: invented log, so this proves the mechanism, not the saving. Real numbers need the real log.")


if __name__ == "__main__":
    main()
