"""
Data contracts + baseline KPIs for the generated factory data.

Two jobs, both things an architect must own before any AI is built:
  1. CONTRACTS: is the data trustworthy enough to base decisions on? (referential integrity,
     time sanity, duplicates, missing reason codes ...). In production these run in the pipeline
     and block bad data from reaching the copilot.
  2. BASELINE: how does the factory perform *today* without AI? (OEE, downtime Pareto, late orders).
     Without a baseline you cannot prove the copilot helped.

    python3 validate.py            # exits 1 if any blocking contract fails (CI-friendly)
"""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

G = Path(__file__).parent / "generated"


def load(rel: str) -> list[dict]:
    with (G / rel).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def main() -> None:
    lines = {r["line_id"]: r for r in load("master/lines.csv")}
    machines = {r["machine_id"]: r for r in load("master/machines.csv")}
    products = {r["sku"]: r for r in load("master/products.csv")}
    wos = {r["wo_id"]: r for r in load("transactional/work_orders.csv")}
    sched = load("transactional/baseline_schedule.csv")
    events = load("telemetry/machine_events.csv")
    counts = load("telemetry/production_counts.csv")
    cal = [r for r in load("master/shift_calendar.csv") if r["working"] == "True"]

    windows: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    for r in sorted(cal, key=lambda r: (r["plant_id"], r["start"])):  # merge back-to-back shifts
        w_ = windows[r["plant_id"]]
        a, b = ts(r["start"]), ts(r["end"])
        if w_ and w_[-1][1] == a:
            w_[-1] = (w_[-1][0], b)
        else:
            w_.append((a, b))

    results: list[tuple[str, str, int, str]] = []  # (severity, contract, violations, example)

    def check(sev: str, name: str, bad: list) -> None:
        results.append((sev, name, len(bad), str(bad[0])[:110] if bad else ""))

    # ---------------------------------------------------------------- contracts
    check("BLOCK", "schedule.wo_id exists in work_orders", [s["wo_id"] for s in sched if s["wo_id"] not in wos])
    check("BLOCK", "work_order.sku exists in products", [w["wo_id"] for w in wos.values() if w["sku"] not in products])
    check("BLOCK", "scheduled product format matches line type",
          [s["wo_id"] for s in sched if s["wo_id"] in wos and products[wos[s["wo_id"]]["sku"]]["format"] != lines[s["line_id"]]["line_type"]])
    by_line = defaultdict(list)
    for s in sched:
        by_line[s["line_id"]].append(s)
    overlaps = []
    for lid, rows in by_line.items():
        rows = sorted((r for r in rows if r["wo_id"] in wos), key=lambda r: r["planned_start"])
        overlaps += [(lid, a["wo_id"], b["wo_id"]) for a, b in zip(rows, rows[1:]) if b["planned_start"] < a["planned_end"]]
    check("BLOCK", "no overlapping work orders on a line (schedule)", overlaps)
    check("BLOCK", "event end > start", [e for e in events if e["end_ts"] <= e["start_ts"]])
    check("BLOCK", "event machine/line exists",
          [e["machine_id"] for e in events if e["machine_id"] not in machines and e["machine_id"] not in lines])
    keys = Counter(tuple(e.values()) for e in events)
    check("WARN", "no duplicate events", [k[:4] for k, n in keys.items() if n > 1])
    outside = []
    for e in events:
        a, b = ts(e["start_ts"]), ts(e["end_ts"])
        if not any(wa <= a and b <= wb for wa, wb in windows[e["line_id"][:3]]):
            outside.append((e["line_id"], e["start_ts"], e["end_ts"]))
    check("WARN", "events fall inside working calendar (clock sync)", outside)
    downs = [e for e in events if e["state"] == "DOWN"]
    missing = [e for e in downs if e["reason_code"] in ("", "OTHER")]
    results.append(("WARN" if len(missing) / max(len(downs), 1) < 0.05 else "BLOCK",
                    f"DOWN reason_code filled (<5% missing; actual {len(missing) / max(len(downs), 1):.0%})",
                    len(missing), str(missing[0])[:110] if missing else ""))
    check("BLOCK", "production counts non-negative",
          [c for c in counts if int(c["good_units"]) < 0 or int(c["scrap_units"]) < 0])

    print("DATA CONTRACTS")
    for sev, name, n, ex in results:
        status = "PASS" if n == 0 else sev
        print(f"  [{status:5}] {name}  ({n})" + (f"\n          e.g. {ex}" if n else ""))

    # ---------------------------------------------------------------- baseline KPIs (on de-duplicated data)
    uniq = list({tuple(e.values()): e for e in events}.values())
    minutes = defaultdict(lambda: Counter())
    for e in uniq:
        minutes[e["line_id"]][e["state"]] += (ts(e["end_ts"]) - ts(e["start_ts"])).total_seconds() / 60
    good, total = Counter(), Counter()
    for c in counts:
        g, s_ = max(int(c["good_units"]), 0), max(int(c["scrap_units"]), 0)
        good[c["line_id"]] += g
        total[c["line_id"]] += g + s_
    first = min(e["start_ts"] for e in uniq)
    last = max(e["end_ts"] for e in uniq)
    print(f"\nBASELINE OEE  ({first[:10]} -> {last[:10]})")
    print(f"  {'line':<8}{'type':<7}{'avail':>7}{'perf':>7}{'qual':>7}{'OEE':>7}{'down h':>8}{'c/o h':>7}")
    for lid in sorted(minutes):
        m = minutes[lid]
        planned = m["RUNNING"] + m["DOWN"] + m["CHANGEOVER"]
        avail = m["RUNNING"] / planned if planned else 0
        rate = int(lines[lid]["nominal_rate_uph"])
        perf = total[lid] / (rate * m["RUNNING"] / 60) if m["RUNNING"] else 0
        qual = good[lid] / total[lid] if total[lid] else 0
        print(f"  {lid:<8}{lines[lid]['line_type']:<7}{avail:>7.0%}{perf:>7.0%}{qual:>7.1%}{avail * perf * qual:>7.0%}"
              f"{m['DOWN'] / 60:>8.1f}{m['CHANGEOVER'] / 60:>7.1f}")

    pareto = Counter()
    for e in uniq:
        if e["state"] == "DOWN":
            pareto[e["reason_code"] or "(missing)"] += (ts(e["end_ts"]) - ts(e["start_ts"])).total_seconds() / 3600
    tot = sum(pareto.values())
    print("\nDOWNTIME PARETO (hours)")
    cum = 0.0
    for r, h in pareto.most_common(8):
        cum += h
        print(f"  {r:<20}{h:>7.1f}   cum {cum / tot:>4.0%}")

    done = defaultdict(str)
    for e in uniq:
        if e["state"] == "RUNNING" and e["end_ts"] > done[e["wo_id"]]:
            done[e["wo_id"]] = e["end_ts"]
    late = Counter()
    n = Counter()
    for wid, fin in done.items():
        if wid in wos and wos[wid]["due_at"]:
            p = wos[wid]["priority"]
            n[p] += 1
            late[p] += fin > wos[wid]["due_at"]
    print("\nORDERS FINISHED LATE (baseline, no copilot)")
    for p in ("critical", "high", "normal"):
        if n[p]:
            print(f"  {p:<9}{late[p]:>4}/{n[p]:<4} {late[p] / n[p]:.0%}")
    unscheduled = [w for w in wos.values() if w["status"] == "unscheduled"]
    print(f"  rush orders not yet scheduled: {len(unscheduled)}")

    if any(sev == "BLOCK" and n_ for sev, _, n_, _ in results):
        print("\nRESULT: BLOCKING contract violations -> this data must not feed the copilot until fixed.")
        sys.exit(1)
    print("\nRESULT: contracts OK")


if __name__ == "__main__":
    main()
