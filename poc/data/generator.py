"""
Synthetic data for the Production Planning Copilot capstone.

A fictional beverage manufacturer ("Nahda Beverages") with plants in Saudi Arabia, Egypt and the UAE.
Everything here is invented. Do NOT put real customer, plant or employer data in this repo.

What it generates (data/generated/):
  master/       plants, lines, machines, products, changeover matrix, materials, BOM, shift calendar
  transactional/ work orders, baseline schedule, material deliveries, maintenance plan
  telemetry/    machine state events, hourly production counts
  unstructured/ SOPs and planning rules (markdown), shift handover notes (AR/EN, contain names = PII)
  labels/       disruptions (ground truth), planner decisions (what a human did), eval scenarios
  MANIFEST.json what was generated + the data-quality issues that were injected ON PURPOSE

Standard library only:
  python3 generator.py                 # 3 plants, 28 days (laptop-friendly)
  python3 generator.py --plants 10 --days 90 --seed 7
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "generated"
START = datetime(2026, 9, 1)
PLAN_EFF = 0.83  # planners assume 72% of nominal rate (buffer for stops)

PLANTS = [  # id, name, city, country, tz offset (h), weekend weekdays (Mon=0), shifts
    ("P01", "Nahda Riyadh 1", "Riyadh", "SA", 3, (4, 5), 3),
    ("P02", "Nahda Jeddah", "Jeddah", "SA", 3, (4, 5), 3),
    ("P03", "Nahda 10th of Ramadan", "10th of Ramadan City", "EG", 3, (4,), 2),
    ("P04", "Nahda Dammam", "Dammam", "SA", 3, (4, 5), 3),
    ("P05", "Nahda Alexandria", "Alexandria", "EG", 3, (4,), 2),
    ("P06", "Nahda Jebel Ali", "Dubai", "AE", 4, (5, 6), 3),
    ("P07", "Nahda Riyadh 2", "Riyadh", "SA", 3, (4, 5), 2),
    ("P08", "Nahda Sadat City", "Sadat City", "EG", 3, (4,), 3),
    ("P09", "Nahda Abu Dhabi", "Abu Dhabi", "AE", 4, (5, 6), 2),
    ("P10", "Nahda Madinah", "Madinah", "SA", 3, (4, 5), 2),
]
HOLIDAYS = {"SA": {date(2026, 9, 23): "Saudi National Day"},
            "EG": {date(2026, 10, 6): "Armed Forces Day"},
            "AE": {date(2026, 12, 2): "UAE National Day"}}

LINE_TYPES = {  # type: (formats, rate units/hour range)
    "PET": (["PET"], (18000, 30000)),
    "CAN": (["CAN"], (36000, 60000)),
    "GLASS": (["GLASS"], (12000, 20000)),
}
MACHINE_CHAIN = ["filler", "capper", "labeler", "packer", "palletizer"]
FAMILIES = ["cola", "orange", "lemon", "water", "energy"]
SIZES = {"PET": [330, 500, 1500], "CAN": [250, 330], "GLASS": [250]}
REASONS_BY_MACHINE = {  # machine-specific faults + reasons any machine can log
    "filler": ["FILLER_VALVE_FAULT", "FILL_LEVEL_LOW", "JAM_INFEED"],
    "capper": ["CAPPER_TORQUE", "CAP_FEED_JAM"],
    "labeler": ["LABEL_MISALIGN", "GLUE_SYSTEM"],
    "packer": ["CARTON_JAM", "SHRINK_TUNNEL_TEMP"],
    "palletizer": ["PALLETIZER_FAULT", "PALLET_SHORTAGE"],
}
REASONS_ANY = ["MATERIAL_SHORTAGE", "POWER_DIP", "QUALITY_HOLD", "NO_OPERATOR"]
FIRST = ["Ahmed", "Mohamed", "Khaled", "Omar", "Youssef", "Fahad", "Saad", "Mahmoud", "Hassan", "Ali"]
LAST = ["Al-Harbi", "Hassan", "El-Sayed", "Al-Qahtani", "Mostafa", "Al-Otaibi", "Fathy", "Al-Shehri"]


def w(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".jsonl":
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S")


class Calendar:
    """Working windows per plant. 3-shift plants run 24h, 2-shift plants 06:00-22:00. No work on weekends/holidays."""

    def __init__(self, plant: tuple, days: int):
        pid, _, _, country, _, weekend, shifts = plant
        self.windows: list[tuple[datetime, datetime]] = []
        self.rows: list[dict] = []
        for d in range(days + 14):  # +14 so late work orders can still be scheduled
            day = START + timedelta(days=d)
            hol = HOLIDAYS.get(country, {}).get(day.date())
            working = day.weekday() not in weekend and not hol
            spans = [(0, 8, "C"), (8, 16, "A"), (16, 24, "B")] if shifts == 3 else [(6, 14, "A"), (14, 22, "B")]
            for s, e, name in spans:
                a, b = day + timedelta(hours=s), day + timedelta(hours=e)
                if True:  # keep calendar for the whole simulated horizon
                    self.rows.append({"plant_id": pid, "date": day.date().isoformat(), "shift": name,
                                      "start": iso(a), "end": iso(b), "working": working,
                                      "note": hol or ("weekend" if not working else "")})
                if working:
                    if self.windows and self.windows[-1][1] == a:
                        self.windows[-1] = (self.windows[-1][0], b)
                    else:
                        self.windows.append((a, b))

    def add(self, t: datetime, minutes: float) -> datetime:
        """Advance t by `minutes` of WORKING time."""
        left = timedelta(minutes=minutes)
        for a, b in self.windows:
            if b <= t:
                continue
            t = max(t, a)
            if t + left <= b:
                return t + left
            left -= b - t
            t = b
        return t + left

    def next_working(self, t: datetime) -> datetime:
        for a, b in self.windows:
            if b > t:
                return max(t, a)
        return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plants", type=int, default=3)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    plants = PLANTS[: a.plants]
    issues: list[str] = []

    # ------------------------------------------------------------------ master data
    plant_rows, line_rows, machine_rows, cal_rows = [], [], [], []
    calendars: dict[str, Calendar] = {}
    for p in plants:
        pid, name, city, country, tz, weekend, shifts = p
        plant_rows.append({"plant_id": pid, "name": name, "city": city, "country": country, "utc_offset_h": tz,
                           "shifts_per_day": shifts, "connectivity": rnd.choice(["stable", "stable", "intermittent"])})
        calendars[pid] = Calendar(p, a.days)
        cal_rows += calendars[pid].rows
        for i in range(rnd.randint(3, 4)):
            lt = rnd.choice(list(LINE_TYPES))
            lid = f"{pid}-L{i + 1}"
            rate = rnd.randrange(*LINE_TYPES[lt][1], 1000)
            line_rows.append({"line_id": lid, "plant_id": pid, "line_type": lt, "nominal_rate_uph": rate,
                              "commissioned": rnd.randint(2008, 2024)})
            for m in MACHINE_CHAIN:
                machine_rows.append({"machine_id": f"{lid}-{m.upper()[:3]}", "line_id": lid, "machine_type": m,
                                     "nominal_rate_uph": int(rate * rnd.uniform(1.05, 1.25)),
                                     "mtbf_h": round(rnd.uniform(15, 70), 1),  # hidden truth, drives breakdowns
                                     "criticality": "A" if m == "filler" else rnd.choice(["B", "C"])})

    products = []
    for fmt, sizes in SIZES.items():
        for fam in FAMILIES:
            for ml in sizes:
                if fam == "energy" and fmt != "CAN":
                    continue
                products.append({"sku": f"{fam[:3].upper()}-{fmt}-{ml}", "name": f"Nahda {fam.title()} {ml}ml {fmt}",
                                 "family": fam, "format": fmt, "size_ml": ml, "units_per_case": 24 if ml <= 500 else 6})
    changeover = []
    for f1 in FAMILIES:
        for f2 in FAMILIES:
            base = 0 if f1 == f2 else (90 if "energy" in (f1, f2) or f1 == "cola" else 45)  # flavour -> CIP time
            changeover.append({"from_family": f1, "to_family": f2, "same_size_min": base, "size_change_extra_min": 40})

    materials, bom = [], []
    for fam in FAMILIES:
        materials.append({"material_id": f"CONC-{fam.upper()}", "name": f"{fam} concentrate", "type": "concentrate",
                          "supplier": rnd.choice(["Supplier A", "Supplier B"]), "lead_time_days": rnd.randint(5, 21), "uom": "L"})
    for fmt, sizes in SIZES.items():
        for ml in sizes:
            materials.append({"material_id": f"PKG-{fmt}-{ml}", "name": f"{fmt} {ml}ml container", "type": "packaging",
                              "supplier": rnd.choice(["Supplier C", "Supplier D", "Supplier E"]), "lead_time_days": rnd.randint(3, 30), "uom": "pcs"})
    materials += [{"material_id": "CO2", "name": "Food-grade CO2", "type": "gas", "supplier": "Supplier F", "lead_time_days": 2, "uom": "kg"},
                  {"material_id": "CARTON", "name": "Shipping carton", "type": "packaging", "supplier": "Supplier G", "lead_time_days": 7, "uom": "pcs"}]
    for p in products:
        bom += [{"sku": p["sku"], "material_id": f"CONC-{p['family'].upper()}", "qty_per_unit": round(p["size_ml"] / 1000 * 0.18, 4)},
                {"sku": p["sku"], "material_id": f"PKG-{p['format']}-{p['size_ml']}", "qty_per_unit": 1},
                {"sku": p["sku"], "material_id": "CARTON", "qty_per_unit": round(1 / p["units_per_case"], 4)}]
        if p["family"] in ("cola", "energy", "lemon"):
            bom.append({"sku": p["sku"], "material_id": "CO2", "qty_per_unit": round(p["size_ml"] / 1000 * 0.008, 5)})

    # ------------------------------------------------------------------ work orders + baseline schedule
    co_min = {(r["from_family"], r["to_family"]): r["same_size_min"] for r in changeover}
    prod_by_fmt = {f: [p for p in products if p["format"] == f] for f in SIZES}
    customers = ["Retail Chain North", "Retail Chain West", "Hypermarket Group", "Export Distributor", "HoReCa Distributor", "Key Account X"]
    wos, sched, actual_runs = [], [], []
    for p in plants:
        pid = p[0]
        cal = calendars[pid]
        lines = [l for l in line_rows if l["plant_id"] == pid]
        n = 0
        for line in lines:
            t = cal.next_working(START)
            end = START + timedelta(days=a.days)
            while t < end:
                prod = rnd.choice(prod_by_fmt[line["line_type"]])
                hours = rnd.uniform(4, 14)
                qty = int(line["nominal_rate_uph"] * hours * 0.85 / 1000) * 1000
                created = t - timedelta(days=rnd.randint(2, 6))
                n += 1
                wo = {"wo_id": f"WO-{pid}-{n:05d}", "plant_id": pid, "sku": prod["sku"], "qty": qty,
                      "customer": rnd.choice(customers), "priority": rnd.choices(["normal", "high", "critical"], [75, 20, 5])[0],
                      "created_at": iso(created), "due_at": "", "status": "released"}
                wos.append(wo)
                sched.append({"line_id": line["line_id"], "wo_id": wo["wo_id"], "family": prod["family"], "size_ml": prod["size_ml"],
                              "qty": qty, "rate": line["nominal_rate_uph"]})
                t = cal.add(t, hours * 60 + 60)  # rough cursor for creation pacing

    # proper baseline schedule per line: sequential, with changeovers, ideal rate * 0.85 planned efficiency
    schedule_rows = []
    by_line: dict[str, list[dict]] = {}
    for s in sched:
        by_line.setdefault(s["line_id"], []).append(s)
    wo_map = {w_["wo_id"]: w_ for w_ in wos}
    for lid, items in by_line.items():
        cal = calendars[lid[:3]]
        t = cal.next_working(START)
        prev = None
        for seq, s in enumerate(items, 1):
            co = 0
            if prev:
                co = co_min[(prev["family"], s["family"])] + (40 if prev["size_ml"] != s["size_ml"] else 0)
            start = cal.add(t, co)
            run_min = s["qty"] / (s["rate"] * PLAN_EFF) * 60
            fin = cal.add(start, run_min)
            schedule_rows.append({"line_id": lid, "sequence": seq, "wo_id": s["wo_id"], "planned_changeover_min": co,
                                  "planned_start": iso(start), "planned_end": iso(fin)})
            wo = wo_map[s["wo_id"]]
            slack = timedelta(hours=rnd.choice([4, 8, 12, 24, 48]) if wo["priority"] == "normal" else rnd.choice([2, 4, 8]))
            wo["due_at"] = iso(fin + slack)
            actual_runs.append((lid, s, start, fin, co))
            t, prev = fin, s

    # ------------------------------------------------------------------ telemetry: simulate execution with breakdowns
    machines_by_line: dict[str, list[dict]] = {}
    for m in machine_rows:
        machines_by_line.setdefault(m["line_id"], []).append(m)
    events, counts, disruptions = [], [], []
    for lid, items in by_line.items():
        cal = calendars[lid[:3]]
        rate = items[0]["rate"]
        t = cal.next_working(START)
        prev = None
        for s in items:
            if prev:
                co = co_min[(prev["family"], s["family"])] + (40 if prev["size_ml"] != s["size_ml"] else 0)
                co = int(co * rnd.uniform(0.9, 1.6))  # changeovers usually run long
                if co:
                    e = cal.add(t, co)
                    events.append({"machine_id": lid, "line_id": lid, "start_ts": iso(t), "end_ts": iso(e),
                                   "state": "CHANGEOVER", "reason_code": f"{prev['family']}->{s['family']}", "wo_id": s["wo_id"]})
                    t = e
            remaining = s["qty"] / (rate * rnd.uniform(0.86, 0.97)) * 60  # true running minutes at actual speed
            while remaining > 0:
                m = rnd.choice(machines_by_line[lid])
                ttf = rnd.expovariate(1 / (m["mtbf_h"] * 60)) * 0.25  # line has 5 machines in series
                run = min(remaining, ttf)
                e = cal.add(t, run)
                events.append({"machine_id": lid, "line_id": lid, "start_ts": iso(t), "end_ts": iso(e),
                               "state": "RUNNING", "reason_code": "", "wo_id": s["wo_id"]})
                t, remaining = e, remaining - run
                if remaining > 0:
                    dur = min(rnd.lognormvariate(3.0, 0.9), 600)  # minutes; median ~20, long tail
                    reason = rnd.choice(REASONS_BY_MACHINE[m["machine_type"]] * 3 + REASONS_ANY)
                    e = cal.add(t, dur)
                    ev = {"machine_id": m["machine_id"], "line_id": lid, "start_ts": iso(t), "end_ts": iso(e),
                          "state": "DOWN", "reason_code": reason, "wo_id": s["wo_id"]}
                    events.append(ev)
                    if dur >= 120:
                        disruptions.append({"disruption_id": f"D{len(disruptions) + 1:04d}", "type": "breakdown",
                                            "plant_id": lid[:3], "line_id": lid, "machine_id": m["machine_id"],
                                            "start_ts": iso(t), "duration_min": round(dur), "reason_code": reason,
                                            "affected_wo": s["wo_id"]})
                    t = e
            prev = s
    # split events at calendar boundaries so no event spans a weekend/holiday/off-shift gap
    split_events = []
    for ev in events:
        a_, b_ = datetime.fromisoformat(ev["start_ts"]), datetime.fromisoformat(ev["end_ts"])
        for wa, wb in calendars[ev["line_id"][:3]].windows:
            if wb <= a_ or wa >= b_:
                continue
            split_events.append(dict(ev, start_ts=iso(max(a_, wa)), end_ts=iso(min(b_, wb))))
    events = sorted(split_events, key=lambda x: (x["line_id"], x["start_ts"]))

    # hourly counts from RUNNING events
    scrap_base = {l["line_id"]: rnd.uniform(0.006, 0.03) for l in line_rows}
    for ev in events:
        if ev["state"] != "RUNNING":
            continue
        a_, b_ = datetime.fromisoformat(ev["start_ts"]), datetime.fromisoformat(ev["end_ts"])
        line_rate = next(l["nominal_rate_uph"] for l in line_rows if l["line_id"] == ev["line_id"])
        h = a_.replace(minute=0, second=0)
        while h < b_:
            seg = (min(b_, h + timedelta(hours=1)) - max(a_, h)).total_seconds() / 3600
            if seg > 0:
                total = int(line_rate * seg * rnd.uniform(0.86, 0.97))
                scrap = int(total * rnd.uniform(0.3, 1.7) * scrap_base[ev["line_id"]])
                counts.append({"line_id": ev["line_id"], "hour_ts": iso(h), "wo_id": ev["wo_id"],
                               "good_units": total - scrap, "scrap_units": scrap})
            h += timedelta(hours=1)
    agg: dict[tuple, dict] = {}
    for c in counts:
        k = (c["line_id"], c["hour_ts"], c["wo_id"])
        if k in agg:
            agg[k]["good_units"] += c["good_units"]
            agg[k]["scrap_units"] += c["scrap_units"]
        else:
            agg[k] = dict(c)
    counts = list(agg.values())

    # ------------------------------------------------------------------ deliveries, maintenance, rush orders
    deliveries = []
    for p in plants:
        for d in range(0, a.days, 2):
            for mat in rnd.sample(materials, 4):
                exp = START + timedelta(days=d, hours=rnd.randint(7, 15))
                late_h = rnd.choices([0, 0, 0, 2, 8, 30, 72], k=1)[0]
                deliveries.append({"delivery_id": f"DL-{p[0]}-{len(deliveries) + 1:05d}", "plant_id": p[0],
                                   "material_id": mat["material_id"], "qty": rnd.randint(5, 80) * 1000,
                                   "expected_at": iso(exp), "actual_at": iso(exp + timedelta(hours=late_h)),
                                   "status": "received"})
                if late_h >= 30:
                    disruptions.append({"disruption_id": f"D{len(disruptions) + 1:04d}", "type": "material_delay",
                                        "plant_id": p[0], "material_id": mat["material_id"], "start_ts": iso(exp),
                                        "duration_min": late_h * 60, "reason_code": "SUPPLIER_LATE"})
    maint = []
    for m in machine_rows:
        if m["criticality"] == "A" or rnd.random() < 0.3:
            st = START + timedelta(days=rnd.randint(3, a.days - 2), hours=rnd.choice([6, 14, 22]))
            maint.append({"machine_id": m["machine_id"], "start": iso(st), "end": iso(st + timedelta(hours=rnd.choice([4, 8]))),
                          "type": "preventive", "can_defer_days": rnd.choice([0, 3, 7])})
    for p in plants:
        for _ in range(max(1, a.days // 7)):
            t = START + timedelta(days=rnd.randint(1, a.days - 2), hours=rnd.randint(8, 18))
            fmt = rnd.choice([l["line_type"] for l in line_rows if l["plant_id"] == p[0]])
            prod = rnd.choice(prod_by_fmt[fmt])
            wid = f"WO-{p[0]}-R{len(disruptions):04d}"
            wos.append({"wo_id": wid, "plant_id": p[0], "sku": prod["sku"], "qty": rnd.randint(20, 80) * 1000,
                        "customer": "Key Account X", "priority": "critical", "created_at": iso(t),
                        "due_at": iso(t + timedelta(hours=rnd.choice([18, 24, 36]))), "status": "unscheduled"})
            disruptions.append({"disruption_id": f"D{len(disruptions) + 1:04d}", "type": "rush_order", "plant_id": p[0],
                                "start_ts": iso(t), "duration_min": 0, "reason_code": "CUSTOMER_RUSH", "affected_wo": wid})

    # ------------------------------------------------------------------ labels: planner decisions + eval scenarios
    action_for = {"breakdown": ["move_to_line", "resequence", "wait_for_repair", "split_order"],
                  "material_delay": ["resequence", "expedite_material", "substitute_supplier", "delay_order"],
                  "rush_order": ["insert_and_resequence", "overtime_shift", "move_to_line", "negotiate_due_date"]}
    why = {"move_to_line": ["Moved remaining qty to {alt}, same format, idle after current WO.",
                            "نقلنا الكمية المتبقية على {alt} لأنها نفس الفورمات وفاضية بعد الأوردر الحالي."],
           "resequence": ["Pulled forward next WO that does not need the missing material/machine.",
                          "قدمنا الأوردر اللي بعده لأنه مش محتاج نفس الخامة، ووفرنا تغيير نكهة."],
           "wait_for_repair": ["Maintenance ETA short, changeover to another line would cost more.",
                               "الصيانة قالت ساعتين، والتحويل لخط تاني هياخد وقت أكتر."],
           "split_order": ["Split WO: 60% stays, 40% moved to {alt} to protect due date.",
                           "قسمنا الأوردر نصين عشان نلحق الـ due date."],
           "expedite_material": ["Asked purchasing to expedite; air freight approved by plant manager.",
                                 "كلمنا المشتريات يستعجلوا الشحنة، ومدير المصنع وافق على التكلفة."],
           "substitute_supplier": ["Used approved alternate supplier stock from sister plant.",
                                   "أخدنا خامة من المصنع التاني بعد موافقة الجودة."],
           "delay_order": ["Customer accepted 1-day delay; no penalty for this account.",
                           "العميل وافق على تأخير يوم، مفيش غرامة."],
           "insert_and_resequence": ["Inserted rush WO after current run on {alt}; pushed two normal-priority WOs.",
                                     "دخلنا الأوردر المستعجل بعد التشغيلة الحالية وأخرنا اتنين normal."],
           "overtime_shift": ["Opened extra shift on weekend, approved by plant manager.",
                              "فتحنا شيفت إضافي يوم الجمعة بموافقة مدير المصنع."],
           "negotiate_due_date": ["Sales negotiated +12h; inserting it would delay 3 high-priority WOs.",
                                  "المبيعات اتفقت على 12 ساعة زيادة، لأن إدخاله كان هيأخر 3 أوردرات high."]}
    decisions, scenarios = [], []
    for d in disruptions:
        act = rnd.choice(action_for[d["type"]])
        alts = [l["line_id"] for l in line_rows if l["plant_id"] == d["plant_id"] and l["line_id"] != d.get("line_id")]
        txt = rnd.choice(why[act]).format(alt=rnd.choice(alts) if alts else "another line")
        decided = datetime.fromisoformat(d["start_ts"]) + timedelta(minutes=rnd.randint(10, 90))
        decisions.append({"disruption_id": d["disruption_id"], "planner_id": f"PL-{d['plant_id']}-{rnd.randint(1, 3)}",
                          "decided_at": iso(decided), "action": act, "rationale": txt,
                          "orders_late_after": rnd.choice([0, 0, 0, 1, 1, 2]),
                          "time_to_decision_min": int((decided - datetime.fromisoformat(d["start_ts"])).total_seconds() / 60)})
        scenarios.append({
            "scenario_id": f"S-{d['disruption_id']}", "as_of": d["start_ts"], "plant_id": d["plant_id"], "disruption": d,
            "question": {"breakdown": f"{d.get('machine_id')} is down ({d['reason_code']}). What should we do with the affected orders?",
                         "material_delay": f"Delivery of {d.get('material_id')} is late. Which orders are at risk and what are the options?",
                         "rush_order": f"Critical order {d.get('affected_wo')} just came in. Can we make it on time and what does it cost us?"}[d["type"]],
            "hard_constraints": ["no work scheduled on a machine during its DOWN or planned maintenance window",
                                 "product format must match line_type",
                                 "no work outside the plant's working calendar unless an overtime action is proposed and flagged for approval",
                                 "frozen horizon: do not change the currently running WO in its first 2 hours",
                                 "never write to MES/PLC: output is a proposal only"],
            "acceptable_actions": action_for[d["type"]],
            "human_reference_action": act,
            "kpis_to_report": ["orders_late", "total_tardiness_h", "changeover_min_added", "critical_orders_on_time"],
        })

    # shift handover notes: messy, bilingual, include operator names (PII) and some plain wrong info
    notes = []
    for ev in [e for e in events if e["state"] == "DOWN"][:: max(1, len(events) // 400)]:
        op = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
        notes.append({"note_id": f"N{len(notes) + 1:05d}", "line_id": ev["line_id"], "written_at": ev["end_ts"],
                      "author": op, "text": rnd.choice([
                          f"{ev['machine_id']} وقفت {ev['reason_code']}، الفني {op.split()[0]} صلحها بس محتاجة متابعة الشيفت الجاي",
                          f"Line stopped, {ev['reason_code'].lower().replace('_', ' ')}. {op.split()[0]} reset it. watch the valve on FIL!!",
                          f"shift B: problem f el labeler tany, el labels mesh mazbota. kalemna el maintenance.",
                          f"ماتريال ناقص على الخط، استنينا forklift ساعة تقريبا. {op} بلغ المخزن",
                          f"All good, ran {ev['wo_id']} . no issues (actually 2 short stops)",
                      ])})

    # ------------------------------------------------------------------ inject data-quality issues ON PURPOSE
    downs = [e for e in events if e["state"] == "DOWN"]
    for e in rnd.sample(downs, k=max(1, len(downs) // 12)):
        e["reason_code"] = rnd.choice(["", "OTHER"])
    issues.append("~8% of DOWN events have empty or 'OTHER' reason_code (operators skip the dropdown)")
    skew_line = rnd.choice(line_rows)["line_id"]
    for e in events:
        if e["line_id"] == skew_line:
            for k in ("start_ts", "end_ts"):
                e[k] = iso(datetime.fromisoformat(e[k]) + timedelta(minutes=7))
    issues.append(f"line {skew_line}: event clock is 7 minutes ahead (PLC clock not NTP-synced) -> overlaps with counts")
    dups = rnd.sample(events, k=max(1, len(events) // 200))
    events += [dict(d_) for d_ in dups]
    issues.append(f"{len(dups)} duplicated events (gateway retried after a network drop)")
    orphan = rnd.choice(schedule_rows)
    schedule_rows.append(dict(orphan, wo_id="WO-UNKNOWN-99999", sequence=999))
    issues.append("1 schedule row references a work order that does not exist (manual edit in planning tool)")
    neg = rnd.choice(counts)
    neg["scrap_units"] = -abs(neg["scrap_units"]) - 1
    issues.append("1 hourly count with negative scrap (counter reset)")

    # ------------------------------------------------------------------ write
    w(OUT / "master/plants.csv", plant_rows)
    w(OUT / "master/lines.csv", line_rows)
    w(OUT / "master/machines.csv", machine_rows)
    w(OUT / "master/products.csv", products)
    w(OUT / "master/changeover_matrix.csv", changeover)
    w(OUT / "master/materials.csv", materials)
    w(OUT / "master/bom.csv", bom)
    w(OUT / "master/shift_calendar.csv", cal_rows)
    w(OUT / "transactional/work_orders.csv", wos)
    w(OUT / "transactional/baseline_schedule.csv", schedule_rows)
    w(OUT / "transactional/material_deliveries.csv", deliveries)
    w(OUT / "transactional/maintenance_plan.csv", maint)
    w(OUT / "telemetry/machine_events.csv", events)
    w(OUT / "telemetry/production_counts.csv", counts)
    w(OUT / "unstructured/shift_notes.jsonl", notes)
    w(OUT / "labels/disruptions.jsonl", disruptions)
    w(OUT / "labels/planner_decisions.jsonl", decisions)
    w(OUT / "labels/eval_scenarios.jsonl", scenarios)
    write_docs(OUT / "unstructured/docs")
    manifest = {"seed": a.seed, "plants": a.plants, "days": a.days, "start": iso(START),
                "row_counts": {"plants": len(plant_rows), "lines": len(line_rows), "machines": len(machine_rows),
                               "products": len(products), "work_orders": len(wos), "schedule": len(schedule_rows),
                               "machine_events": len(events), "production_counts": len(counts),
                               "deliveries": len(deliveries), "disruptions": len(disruptions), "shift_notes": len(notes)},
                "hidden_truth": "machines.csv mtbf_h is the true reliability used by the simulator; a real system would have to estimate it",
                "injected_data_quality_issues": issues}
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest["row_counts"], indent=2))
    print("Injected issues:\n  - " + "\n  - ".join(issues))


def write_docs(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "planning_rules_en.md").write_text("""# Production planning rules (all plants)

## Priorities
1. Critical customer orders (Key Accounts) must ship on time. Escalate to the plant manager if at risk.
2. High priority before normal. Within the same priority: earliest due date first.

## Frozen horizon
The running work order cannot be changed during its first 2 hours. The next 24 hours of the schedule may only be changed by the shift planner, not automatically.

## Changeovers
Group by flavour family to minimise CIP cleaning. Cola or energy to any other flavour requires full CIP (about 90 minutes). Size changes add about 40 minutes.
Maximum one format/size change per shift on GLASS lines.

## Overtime
Weekend or holiday shifts require plant manager approval and at least 24 hours notice to the workforce.

## Maintenance
Preventive maintenance on criticality-A machines cannot be deferred. Other preventive maintenance can be deferred up to the number of days in the maintenance plan.
""", encoding="utf-8")
    (d / "changeover_sop_filler_en.md").write_text("""# SOP: Flavour changeover on filler

1. Drain product from bowl and lines.
2. Rinse with potable water, 10 minutes.
3. Caustic CIP at 75C, 30 minutes (full CIP only).
4. Acid rinse, 10 minutes; final rinse.
5. Quality takes a swab sample; line released only after QA sign-off in the system.
Typical durations: same family 0 min, light flavour change 45 min, full CIP 90 min. Actual changeovers often run 10-60% longer when QA is not available on the shift.
""", encoding="utf-8")
    (d / "escalation_matrix_ar.md").write_text("""# مصفوفة التصعيد عند توقف الإنتاج

| مدة التوقف | من يُبلَّغ | الإجراء |
|---|---|---|
| أقل من 30 دقيقة | مشرف الوردية | تسجيل سبب التوقف في النظام |
| 30 دقيقة إلى ساعتين | مخطط الإنتاج + الصيانة | تقييم إعادة الجدولة |
| أكثر من ساعتين | مدير المصنع | قرار نقل الطلبات لخط آخر أو مصنع آخر |
| أي تأثير على طلب عميل حرج | مدير المصنع + المبيعات | إبلاغ العميل خلال ساعة |

ملاحظة: لا يجوز لأي نظام آلي تعديل أوامر التشغيل في نظام MES مباشرة، ويجب أن تمر أي تغييرات بموافقة المخطط.
""", encoding="utf-8")
    (d / "cip_quality_ar.md").write_text("""# متطلبات الجودة بعد التنظيف (CIP)

بعد أي تغيير نكهة يتطلب تنظيفاً كاملاً، لا يُسمح بتشغيل الخط إلا بعد اعتماد عينة المسحة من قسم الجودة.
في الوردية الليلية قد لا يتوفر مسؤول الجودة، لذلك يُفضّل جدولة التغييرات الكبيرة في الوردية A أو B.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
