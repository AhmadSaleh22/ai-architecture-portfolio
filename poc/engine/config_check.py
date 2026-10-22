"""Load a factory config and check that it is complete and consistent.

    python3 engine/config_check.py engine/configs/*.yaml

Needs PyYAML (pip install pyyaml). Exits 1 if any config has errors.
The checks are semantic (every reference resolves, recipes add up, every stage
can run somewhere). They are what a JSON Schema cannot express, and they run
before any solver sees the config.
"""
import sys
from pathlib import Path

import yaml

DAYS = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]
KPIS = {"late_qty", "weighted_tardiness", "plan_changes", "batch_count", "setup_minutes", "makespan", "cost"}
DURING = {"whole_run", "start", "end", "setup"}
REQUIRED = ["schema_version", "meta", "calendars", "attributes", "people", "stages", "resources",
            "products", "order_classes", "objective"]


def minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def window_len(a, b):
    d = minutes(b) - minutes(a)
    return d if d > 0 else d + 1440        # end <= start means it crosses midnight


def weekly_minutes(cal):
    return sum(window_len(a, b) for d in cal.get("weekly", {}).values() for a, b in d)


def expand_recipe(p, variant=None):
    """Parts per basis for a product (and optional variant). 'balance' fills up to the basis."""
    basis = p["recipe_basis"]
    items = {x["material"]: x.get("parts") for x in p["recipe"]}
    bal = [m for m, v in items.items() if v == "balance"]
    if len(bal) > 1:
        raise ValueError("more than one 'balance' item")
    fixed = sum(v for v in items.values() if isinstance(v, (int, float)))
    if bal:
        items[bal[0]] = basis - fixed
        if items[bal[0]] <= 0:
            raise ValueError(f"balance item {bal[0]} would be {items[bal[0]]}")
    elif abs(fixed - basis) > 1e-6 and None not in items.values():
        raise ValueError(f"recipe parts add up to {fixed}, basis is {basis}")
    if variant:
        v = p["variants"][variant]
        share = items.pop(v["remove"]) / len(v["split_to"])
        for m in v["split_to"]:
            items[m] += share
    return items


def check(cfg):
    err, warn = [], []
    for k in REQUIRED:
        if k not in cfg:
            err.append(f"missing section '{k}'")
    if err:
        return err, warn

    cals, attrs, people = cfg["calendars"], cfg["attributes"], cfg["people"]
    cons, mats = cfg.get("consumables", {}), cfg.get("materials", {})
    stage_ids = [s["id"] for s in cfg["stages"]]

    for cid, cal in cals.items():
        for day, wins in cal.get("weekly", {}).items():
            if day not in DAYS:
                err.append(f"calendar {cid}: unknown day '{day}'")
            for w in wins:
                if len(w) != 2:
                    err.append(f"calendar {cid}/{day}: window must be [start, end]")

    for pid, p in people.items():
        if p.get("calendar") not in cals:
            err.append(f"people {pid}: unknown calendar '{p.get('calendar')}'")
        if p.get("count", 0) < 1:
            err.append(f"people {pid}: count must be >= 1")

    for s in cfg["stages"]:
        for k in s.get("batch_key", []):
            if k not in attrs and not k.endswith("_id"):
                err.append(f"stage {s['id']}: batch_key '{k}' is not an attribute")
        lag = s.get("after", {})
        lo, hi = lag.get("min_lag_min") or 0, lag.get("max_lag_min")
        if hi is not None and hi < lo:
            err.append(f"stage {s['id']}: max_lag < min_lag")

    res_by_stage = {s: [] for s in stage_ids}
    for rid, r in cfg["resources"].items():
        if r.get("stage") not in res_by_stage:
            err.append(f"resource {rid}: unknown stage '{r.get('stage')}'")
            continue
        res_by_stage[r["stage"]].append(rid)
        if r.get("calendar") not in cals:
            err.append(f"resource {rid}: unknown calendar '{r.get('calendar')}'")
        cap = r.get("capacity")
        if cap and cap.get("min", 0) > cap.get("max", 0):
            err.append(f"resource {rid}: capacity min > max")
        stage = next(s for s in cfg["stages"] if s["id"] == r["stage"])
        if stage.get("batching") and not cap:
            err.append(f"resource {rid}: stage '{stage['id']}' batches but resource has no capacity")
        d = r.get("duration", {})
        if d.get("fixed_min", 0) + d.get("per_unit_min", 0) <= 0:
            err.append(f"resource {rid}: duration is zero")
        for n in r.get("needs", []):
            pools = n["people"] if isinstance(n["people"], list) else [n["people"]]
            for p in pools:
                if p not in people:
                    err.append(f"resource {rid}: needs unknown people pool '{p}'")
            if n.get("during") not in DURING:
                err.append(f"resource {rid}: needs.during must be one of {sorted(DURING)}")
        for c in r.get("consumes", []):
            if c["consumable"] not in cons:
                err.append(f"resource {rid}: unknown consumable '{c['consumable']}'")
            by = c.get("per_unit_by")
            if by and set(c["values"]) - set(attrs.get(by, [])):
                err.append(f"resource {rid}: consumption values not in attribute '{by}'")
        st = r.get("setups")
        if st:
            keys = st["by"] if isinstance(st["by"], list) else [st["by"]]
            for k in keys:
                if k not in attrs:
                    err.append(f"resource {rid}: setups.by '{k}' is not an attribute")
            allowed = {"same", "*"} | {v for k in keys for v in attrs.get(k, [])}
            for rule in st.get("rules", []):
                for side in ("from", "to"):
                    if rule[side] not in allowed:
                        err.append(f"resource {rid}: setup rule {side}='{rule[side]}' unknown")
                if rule.get("crew") and rule["crew"] not in people:
                    err.append(f"resource {rid}: setup crew '{rule['crew']}' unknown")
        for k, vals in (r.get("eligible") or {}).items():
            if k not in attrs or set(vals) - set(attrs[k]):
                err.append(f"resource {rid}: eligible {k}={vals} invalid")

    used_stages = set()
    for pid, p in cfg["products"].items():
        for st in p["route"]:
            if st not in res_by_stage:
                err.append(f"product {pid}: route stage '{st}' unknown")
            used_stages.add(st)
        if [s for s in stage_ids if s in p["route"]] != p["route"]:
            err.append(f"product {pid}: route is not in stage order")
        for k, v in p.get("attributes", {}).items():
            if k not in attrs or v not in attrs[k]:
                err.append(f"product {pid}: attribute {k}={v} invalid")
        if "recipe_basis" in p:                     # parts, e.g. grams per 250 g bag
            try:
                expand_recipe(p)
            except ValueError as e:
                err.append(f"product {pid}: {e}")
            unknown = [x["material"] for x in p["recipe"] if x.get("parts") is None]
            if unknown:
                warn.append(f"product {pid}: unknown amount for {unknown}")
            for vid, v in (p.get("variants") or {}).items():
                mats_in = {x["material"] for x in p["recipe"]}
                if v["remove"] not in mats_in or set(v["split_to"]) - mats_in:
                    err.append(f"product {pid}: variant {vid} names a material not in the recipe")
                for k, val in v.get("attributes", {}).items():
                    if val not in attrs.get(k, []):
                        err.append(f"product {pid}: variant {vid} attribute {k}={val} invalid")
        else:
            total = sum(x["share"] for x in p["recipe"])
            if abs(total - 1) > 1e-6:
                err.append(f"product {pid}: recipe shares add up to {total}, not 1")
        for x in p["recipe"] + p.get("additives", []):
            if x["material"] not in mats:
                err.append(f"product {pid}: unknown material '{x['material']}'")
            if x.get("added_at") and x["added_at"] not in p["route"]:
                err.append(f"product {pid}: {x['material']} added at '{x['added_at']}', not in route")
        # can some resource of each stage run this product?
        for st in p["route"]:
            ok = [rid for rid in res_by_stage.get(st, [])
                  if all(p["attributes"].get(k) in v for k, v in (cfg["resources"][rid].get("eligible") or {}).items())]
            if not ok:
                err.append(f"product {pid}: no eligible resource for stage '{st}'")

    for s in stage_ids:
        if s not in used_stages:
            warn.append(f"stage {s} is not used by any product")
        if not res_by_stage[s]:
            err.append(f"stage {s} has no resource")

    prios = set()
    for oid, o in cfg["order_classes"].items():
        if o.get("weight", 0) <= 0:
            err.append(f"order class {oid}: weight must be > 0")
        prios.add(o["priority"])
    for i, ob in enumerate(cfg["objective"], 1):
        if ob["kpi"] not in KPIS:
            err.append(f"objective {i}: unknown kpi '{ob['kpi']}'")
        f = ob.get("filter", {})
        if "priority" in f and f["priority"] not in prios:
            err.append(f"objective {i}: no order class has priority {f['priority']}")

    n_assume = sum(1 for line in Path(cfg["_path"]).read_text().splitlines()
                   if "#" in line and "ASSUMPTION" in line.split("#", 1)[1])
    if n_assume:
        warn.append(f"{n_assume} values are marked ASSUMPTION: confirm with the factory")
    return err, warn


def summary(cfg):
    out = []
    for rid, r in cfg["resources"].items():
        cal = cfg["calendars"][r["calendar"]]
        n_windows = sum(len(w) for w in cal.get("weekly", {}).values())
        wk = weekly_minutes(cal) - n_windows * r.get("startup_min", 0)
        d = r["duration"]
        cap = r.get("capacity")
        if cap:
            per_batch = d["fixed_min"] + d["per_unit_min"] * cap["max"]
            qty = wk / per_batch * cap["max"]
            unit = cap.get("unit", cfg["meta"]["units"]["qty"])
            out.append(f"  {rid:<14} {r['stage']:<6} {wk/60:>5.0f} h/wk  ~{qty:>12,.0f} {unit}/wk (full batches)")
        else:
            qty = wk / d["per_unit_min"] if d["per_unit_min"] else float("inf")
            out.append(f"  {rid:<14} {r['stage']:<6} {wk/60:>5.0f} h/wk  ~{qty:>12,.0f} {cfg['meta']['units']['qty']}/wk (no setups)")
    return "\n".join(out)


def main(paths):
    bad = 0
    for p in paths:
        cfg = yaml.safe_load(Path(p).read_text())
        cfg["_path"] = p
        err, warn = check(cfg)
        print(f"\n== {cfg.get('meta', {}).get('name', p)}  [{Path(p).name}]")
        print(f"   {len(cfg['resources'])} resources, {len(cfg['people'])} people pools, "
              f"{len(cfg['stages'])} stages, {len(cfg['products'])} products, {len(cfg['order_classes'])} order classes")
        for e in err:
            print("   ERROR ", e)
        for w in warn:
            print("   warn  ", w)
        if not err:
            print("   OK. Nominal capacity per resource:")
            print(summary(cfg))
            rec = [(pid, p) for pid, p in cfg["products"].items() if "recipe_basis" in p]
            if rec:
                print("   Recipes (parts per basis):")
                for pid, p in rec:
                    for var in [None] + list(p.get("variants") or {}):
                        parts = expand_recipe(p, var)
                        txt = ", ".join(f"{m.replace('green_', '')} {v:g}" if v is not None else f"{m} ?" for m, v in parts.items())
                        print(f"     {pid + (' / ' + var if var else ''):<28} {txt}")
        bad += bool(err)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:] or sorted(str(p) for p in Path(__file__).parent.glob("configs/*.yaml")))
