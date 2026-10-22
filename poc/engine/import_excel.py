"""Read the factory's daily log (سجل_المصنع.xlsx) into the engine's language.

    uv run python engine/import_excel.py engine/samples/factory_log_example.xlsx --out orders.csv

What it does:
  * Orders tab   -> orders CSV for plan.py / backtest.py (Arabic labels -> product, variant, class)
  * Batches tab  -> calibration: real batch time and loss vs. the numbers in the config
  * Events tab   -> downtime (breakdowns, gas ran out) for the backtest
  * Every row it cannot read is reported with its row number, nothing is silently dropped.
"""
import argparse
import csv
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).parent))
from model import load_config  # noqa: E402

# Arabic labels in the sheet -> engine ids (coffee roastery). Another factory gets its own mapping.
CLASS = {"محل": "shop", "سوبر ماركت": "supermarket", "كافيه": "cafe", "أونلاين": "online",
         "تصدير": "export", "تحميص لحساب الغير": "toll_roasting"}
PRODUCT = {"190": "blend_190", "250": "blend_250", "300": "blend_300", "سعودي": "saudi_green",
           "بن العميل": "toll_roast"}
ROAST = {"أشقر": "light", "وسط": "medium", "غامق": "dark"}
FORM = {"مطحون": "ground", "حب": "bean"}
ORIGIN = {"روبستا": "robusta", "برازيلي": "brazil", "كولومبي": "colombia", "هندي": "india",
          "سعودي": "saudi_green", "بن العميل": "customer_own"}
FIRST_ROW = 4            # row 3 is the example row
DUE_HOUR = time(22, 0)   # "due on the 14th" = delivered before 22:00 that day
RELEASE_HOUR = time(8, 0)


def _d(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v.strip():
        return date.fromisoformat(v.strip()[:10])
    return None


def _t(v):
    if isinstance(v, time):
        return v
    if isinstance(v, datetime):
        return v.time()
    return None


def _rows(ws, ncols):
    for r in range(FIRST_ROW, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, ncols + 1)]
        if all(v in (None, "") for v in vals):
            continue
        yield r, vals


def read_orders(wb, cfg):
    orders, problems = [], []
    for r, v in _rows(wb["الطلبات"], 13):
        day, name, ctype, blend, card, form, roast, qty, due, delivered, status, _, note = v
        where = f"orders row {r}"
        if status == "اترفض":
            orders.append({"row": r, "rejected": True, "qty": qty, "class": CLASS.get(ctype), "note": note})
            continue
        bad = [x for x, ok in (("order date", _d(day)), ("customer type", ctype in CLASS), ("blend", str(blend) in PRODUCT),
                               ("qty", isinstance(qty, (int, float)) and qty > 0), ("due date", _d(due))) if not ok]
        if bad:
            problems.append(f"{where}: missing or unknown {', '.join(bad)} -> skipped")
            continue
        product = PRODUCT[str(blend)]
        variant = "no_cardamom" if card == "لأ" and product in ("blend_190", "blend_250", "blend_300") else ""
        if _d(due) < _d(day):
            problems.append(f"{where}: due date before order date")
        o = {"row": r, "order_id": f"R{r:03d}", "class": CLASS[ctype], "customer": name or f"row{r}",
             "product": product, "variant": variant, "qty": float(qty),
             "roast_level": ROAST.get(roast, ""), "form": FORM.get(form, ""),
             "release": datetime.combine(_d(day), RELEASE_HOUR).isoformat(timespec="minutes"),
             "due": datetime.combine(_d(due), DUE_HOUR).isoformat(timespec="minutes"),
             "delivered": _d(delivered).isoformat() if _d(delivered) else "", "status": status or "", "rejected": False}
        oc = cfg["order_classes"][o["class"]]
        if oc.get("min_qty") and o["qty"] < oc["min_qty"]:
            problems.append(f"{where}: {o['qty']:g} kg is below the {o['class']} minimum ({oc['min_qty']})")
        orders.append(o)
    return orders, problems


def read_batches(wb):
    out, problems = [], []
    for r, v in _rows(wb["الدفعات"], 14):
        day, t0, t1, roaster, origin, roast, w_in, w_out = v[:8]
        if not (_d(day) and _t(t0) and _t(t1) and isinstance(w_in, (int, float))):
            problems.append(f"batches row {r}: date, times or weight missing -> skipped")
            continue
        s = datetime.combine(_d(day), _t(t0))
        e = datetime.combine(_d(day), _t(t1))
        if e <= s:
            e += timedelta(days=1)
        out.append({"start": s, "end": e, "minutes": (e - s).total_seconds() / 60, "origin": ORIGIN.get(origin, origin),
                    "roast_level": ROAST.get(roast, roast), "kg_in": float(w_in),
                    "kg_out": float(w_out) if isinstance(w_out, (int, float)) else None, "for": v[12]})
    return out, problems


def read_events(wb):
    """Downtime per machine as (start datetime, hours)."""
    out = []
    for r, v in _rows(wb["الأعطال والغاز"], 7):
        day, t, what, machine, hours = v[:5]
        if _d(day) and isinstance(hours, (int, float)) and hours > 0:
            s = datetime.combine(_d(day), _t(t) or time(8, 0))
            out.append({"start": s, "hours": float(hours), "what": what, "machine": machine})
    return out


MACHINE = {"المحمصة": "roaster_1", "المطحنة": "grinder_1", "التغليف": "packing_bench"}


def calibration(batches, cfg):
    r = cfg["resources"]["roaster_1"]
    d = r["duration"]
    print("\n  Calibration: roaster (sheet vs config)")
    if not batches:
        print("    no batches")
        return
    full = [b for b in batches if b["kg_in"] >= 13]
    if full:
        avg = sum(b["minutes"] for b in full) / len(full)
        print(f"    full batch time   {avg:6.0f} min   config {d['fixed_min'] + d['per_unit_min'] * 14:.0f} min ({len(full)} batches)")
    print(f"    avg batch load    {sum(b['kg_in'] for b in batches) / len(batches):6.1f} kg    capacity {r['capacity']['max']} kg")
    loss = defaultdict(list)
    for b in batches:
        if b["kg_out"]:
            loss[b["roast_level"]].append(1 - b["kg_out"] / b["kg_in"])
    conf = cfg["yield_loss"]["roast"]["values"]
    for lvl, xs in loss.items():
        avg = sum(xs) / len(xs)
        flag = "  <- check" if abs(avg - conf.get(lvl, avg)) > 0.015 else ""
        print(f"    loss {lvl:<7}      {avg:6.1%}       config {conf.get(lvl, 0):.0%} ({len(xs)} batches){flag}")


def write_csv(orders, path):
    cols = ["order_id", "class", "customer", "product", "variant", "qty", "release", "due", "roast_level", "form"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for o in orders:
            if not o["rejected"]:
                w.writerow(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--config", default=str(Path(__file__).parent / "configs/coffee_roastery.yaml"))
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = load_config(a.config)
    wb = load_workbook(a.xlsx, data_only=True)
    orders, p1 = read_orders(wb, cfg)
    batches, p2 = read_batches(wb)
    events = read_events(wb)
    ok = [o for o in orders if not o["rejected"]]
    print(f"== {Path(a.xlsx).name}: {len(ok)} orders, {len(orders) - len(ok)} rejected, "
          f"{len(batches)} batches, {len(events)} downtime events")
    for p in p1 + p2:
        print("   warn ", p)
    calibration(batches, cfg)
    if a.out:
        write_csv(orders, a.out)
        print(f"\n  orders written to {a.out}")


if __name__ == "__main__":
    main()
