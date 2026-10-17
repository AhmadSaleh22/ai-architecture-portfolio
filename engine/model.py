"""Build a scheduling problem from a factory config + an orders CSV.

The model is industry-agnostic. It turns orders into:
  * batch tasks  for stages with batching: true  (loads grouped by the stage's batch_key)
  * order tasks  for the other stages            (one task per order and stage)
Both solvers (solve_rules.py, solve_cpsat.py) and the checker (check_schedule.py) use it.

Times are integer minutes from t0 (the start of the plan).
"""
import csv
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from config_check import check, expand_recipe

DAYNAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


# ---------------------------------------------------------------- data ----
@dataclass
class Order:
    id: str
    cls: str
    product: str
    qty: float
    due: int                 # minutes from t0
    release: int = 0
    variant: str = ""
    customer: str = ""
    priority: int = 9
    weight: float = 1.0
    attrs: dict = field(default_factory=dict)


@dataclass
class Task:
    id: str
    stage: str
    kind: str                # "batch" | "order"
    qty: float               # in the stage's unit (kg green, litres, units...)
    attrs: dict              # used for setups and eligibility
    eligible: list           # resource ids
    orders: list             # order ids served
    loads: list = field(default_factory=list)   # batch: [(order_id, material, qty)]
    key: tuple = ()
    release: int = 0
    padding: float = 0.0     # batch: qty added to reach min capacity (goes to stock)


@dataclass
class Problem:
    cfg: dict
    t0: datetime
    horizon: int             # minutes the calendars are built for (plan horizon x 2, for late work)
    orders: dict
    tasks: dict
    preds: list              # (pred_task, succ_task, min_lag, max_lag or None)
    windows: dict            # resource -> [(start, end)]
    people_windows: dict     # pool -> [(start, end)]
    order_last: dict         # order -> its last task id


# ------------------------------------------------------------ calendar ----
def _hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def calendar_windows(cal, t0, horizon, startup=0):
    """Working windows of a calendar as [start, end) minutes from t0, merged when contiguous."""
    closed = {date.fromisoformat(str(d)) for d in cal.get("closed_dates", []) or []}
    raw = []
    day = t0.date() - timedelta(days=1)
    while True:
        base = datetime.combine(day, datetime.min.time())
        if (base - t0).total_seconds() / 60 > horizon:
            break
        if day not in closed:
            for a, b in cal.get("weekly", {}).get(DAYNAMES[day.weekday()], []):
                s, e = _hhmm(a), _hhmm(b)
                if e <= s:
                    e += 1440
                start = int((base - t0).total_seconds() // 60) + s
                raw.append([start, start + e - s])
        day += timedelta(days=1)
    raw.sort()
    merged = []
    for s, e in raw:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out = []
    for s, e in merged:
        s = max(s + startup, 0)              # warm-up at the opening of each window
        if e > s:
            out.append((s, min(e, horizon)))
    return [w for w in out if w[1] > w[0]]


# -------------------------------------------------------------- config ----
def load_config(path):
    cfg = yaml.safe_load(Path(path).read_text())
    cfg["_path"] = str(path)
    err, _ = check(cfg)
    if err:
        raise SystemExit("config has errors:\n  " + "\n  ".join(err))
    return cfg


def duration(res, qty):
    d = res["duration"]
    return int(math.ceil(d.get("fixed_min", 0) + d.get("per_unit_min", 0) * qty))


def setup_minutes(res, prev_attrs, next_attrs):
    """Sequence-dependent setup on a resource (0 if it has no setups or nothing ran before).

    Rules compare the FIRST setup key (e.g. flavor or family): matching rules -> the largest one,
    no match -> default_min, same value -> 0. extra_if_changed adds minutes for other keys (e.g. size).
    """
    st = res.get("setups")
    if not st or prev_attrs is None:
        return 0
    keys = st["by"] if isinstance(st["by"], list) else [st["by"]]
    a, b = prev_attrs.get(keys[0]), next_attrs.get(keys[0])
    total = 0
    if a != b:
        hits = [r["min"] for r in st.get("rules", [])
                if "same" not in (r["from"], r["to"])
                and r["from"] in ("*", a) and r["to"] in ("*", b)]
        total = max(hits) if hits else st.get("default_min", 0)
    for k, extra in (st.get("extra_if_changed") or {}).items():
        if prev_attrs.get(k) != next_attrs.get(k):
            total += extra
    return total


def setup_people(res, prev_attrs, next_attrs):
    """People pool busy during the setup (first pool of the resource's needs)."""
    if setup_minutes(res, prev_attrs, next_attrs) == 0:
        return None
    for n in res.get("needs", []):
        pools = n["people"] if isinstance(n["people"], list) else [n["people"]]
        return pools[0]
    return None


SLOT = 15   # minutes a person is needed when needs.during is "start" or "end" (e.g. a QA release sample)


def people_need(res):
    """[(pool, qty, during)]. v1: with alternative pools, the first one is used."""
    out = []
    for n in res.get("needs", []):
        pools = n["people"] if isinstance(n["people"], list) else [n["people"]]
        out.append((pools[0], n.get("qty", 1), n.get("during", "whole_run")))
    return out


def busy_span(start, end, during):
    """The part of a task when its people are busy."""
    if during == "start":
        return start, min(end, start + SLOT)
    if during == "end":
        return max(start, end - SLOT), end
    return start, end


# --------------------------------------------------------------- build ----
def _ts(s, t0):
    return int((datetime.fromisoformat(s) - t0).total_seconds() // 60)


def load_orders(path, cfg, t0):
    orders = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            oc = cfg["order_classes"][row["class"]]
            p = cfg["products"][row["product"]]
            attrs = dict(p.get("attributes", {}))
            v = row.get("variant") or ""
            if v:
                attrs.update(p["variants"][v].get("attributes", {}))
            o = Order(id=row["order_id"], cls=row["class"], product=row["product"], qty=float(row["qty"]),
                      due=_ts(row["due"], t0), release=max(0, _ts(row["release"], t0)) if row.get("release") else 0,
                      variant=v, customer=row.get("customer", ""), priority=oc["priority"],
                      weight=oc["weight"], attrs=attrs)
            if oc.get("min_qty") and o.qty < oc["min_qty"]:
                print(f"  note: {o.id} qty {o.qty} below class minimum {oc['min_qty']}")
            orders[o.id] = o
    return orders


def _loss(cfg, stage, attrs):
    y = (cfg.get("yield_loss") or {}).get(stage)
    if not y:
        return 0.0
    if not y.get("by"):
        return list(y["values"].values())[0]
    return y["values"].get(attrs.get(y["by"]), 0.0)


def _loads(cfg, stage, o):
    """What one order puts into a batching stage: [(material, qty, extra_attrs)]."""
    p = cfg["products"][o.product]
    conv = (cfg.get("stage_conversion") or {}).get(stage)
    if conv:                                   # e.g. litres of syrup = units x size_ml / 1000
        return [(stage, o.qty * o.attrs[conv["per_unit_from"]] * conv["factor"], {})]
    mats = cfg.get("materials", {})
    if "recipe_basis" in p:
        parts = expand_recipe(p, o.variant or None)
        basis = p["recipe_basis"]
        items = [(m, q / basis) for m, q in parts.items() if q is not None]
    else:
        items = [(x["material"], x["share"]) for x in p["recipe"]]
    added = {x["material"] for x in p["recipe"] if x.get("added_at")}
    out = []
    # qty_is: input -> the order quantity is what goes INTO the stage (toll roasting: kg green brought)
    loss = 0.0 if p.get("qty_is") == "input" else _loss(cfg, stage, o.attrs)
    for m, share in items:
        if m in added or mats.get(m, {}).get("kind") in ("additive",):
            continue
        out.append((m, o.qty * share / (1 - loss), {k: v for k, v in mats.get(m, {}).items() if k in cfg["attributes"]}))
    return out


def build(cfg, orders_csv, t0):
    t0 = datetime.fromisoformat(t0) if isinstance(t0, str) else t0
    horizon = cfg["meta"].get("horizon_days", 3) * 1440 * 2
    orders = load_orders(orders_csv, cfg, t0)
    stages = {s["id"]: s for s in cfg["stages"]}
    res = cfg["resources"]
    tasks, preds, order_last = {}, [], {}

    def eligible(stage, attrs):
        return [rid for rid, r in res.items() if r["stage"] == stage and
                all(attrs.get(k) in v for k, v in (r.get("eligible") or {}).items())]

    # 1. batching stages: group loads by key, then cut into batches
    batch_of_order = defaultdict(list)          # (order, stage) -> batch task ids
    for s in cfg["stages"]:
        if not s.get("batching"):
            continue
        groups = defaultdict(list)
        for o in orders.values():
            if s["id"] not in cfg["products"][o.product]["route"]:
                continue
            for m, q, mattrs in _loads(cfg, s["id"], o):
                attrs = {**o.attrs, **mattrs, "owner_id": o.customer if cfg["order_classes"][o.cls]["owner"] == "customer" else "own"}
                key = tuple(attrs.get(k) for k in s.get("batch_key", []))
                groups[key].append((o, m, q, attrs))
        for key, loads in groups.items():
            # fill full batches in due-date order; if the last one is under the minimum,
            # share the last two equally (or pad the only one up to the minimum, extra goes to stock)
            loads.sort(key=lambda x: (x[0].due, x[0].priority))
            cap = res[eligible(s["id"], loads[0][3])[0]]["capacity"]
            total = sum(q for _, _, q, _ in loads)
            n = max(1, math.ceil(total / cap["max"] - 1e-9))
            sizes = [cap["max"]] * (n - 1) + [total - cap["max"] * (n - 1)]
            if sizes[-1] < cap["min"] and n >= 2 and sizes[-1] + sizes[-2] >= 2 * cap["min"]:
                both = sizes[-1] + sizes[-2]
                sizes[-2:] = [both / 2, both / 2]
            queue = [[o, m, q] for o, m, q, _ in loads]
            for b_i, size in enumerate(sizes, 1):
                bid = f"{s['id']}-{'-'.join(str(k) for k in key)}-{b_i}"
                room, bl = size, []
                while queue and room > 1e-6:
                    o, m, q = queue[0]
                    take = min(q, room)
                    bl.append((o.id, m, round(take, 3)))
                    room -= take
                    queue[0][2] -= take
                    if queue[0][2] <= 1e-6:
                        queue.pop(0)
                pad = max(0.0, cap["min"] - size)
                oids = sorted({x[0] for x in bl})
                t = Task(id=bid, stage=s["id"], kind="batch", qty=round(size + pad, 3), attrs=dict(loads[0][3]),
                         eligible=eligible(s["id"], loads[0][3]), orders=oids, loads=bl, key=key,
                         release=max(orders[i].release for i in oids), padding=round(pad, 3))
                tasks[bid] = t
                for i in oids:
                    batch_of_order[(i, s["id"])].append(bid)

    # 2. order tasks for non-batching stages, chained along the route
    for o in orders.values():
        route = cfg["products"][o.product]["route"]
        prev = []                                  # task ids the next stage waits for
        prev_stage = None
        for st in route:
            if stages[st].get("batching"):
                cur = batch_of_order[(o.id, st)]
            else:
                tid = f"{o.id}-{st}"
                qty = o.qty
                if cfg["products"][o.product].get("qty_is") == "input":   # downstream sees the output weight
                    qty = round(o.qty * (1 - sum(_loss(cfg, x, o.attrs) for x in route[:route.index(st)])), 3)
                tasks[tid] = Task(id=tid, stage=st, kind="order", qty=qty, attrs=dict(o.attrs),
                                  eligible=eligible(st, o.attrs), orders=[o.id], release=o.release)
                cur = [tid]
            if prev_stage:
                lag = stages[prev_stage].get("after", {}) or {}
                for a in prev:
                    for b in cur:
                        if (a, b, lag.get("min_lag_min") or 0, lag.get("max_lag_min")) not in preds:
                            preds.append((a, b, lag.get("min_lag_min") or 0, lag.get("max_lag_min")))
            prev, prev_stage = cur, st
        order_last[o.id] = prev[-1] if len(prev) == 1 else prev   # list if the route ends in batches

    windows = {rid: calendar_windows(cfg["calendars"][r["calendar"]], t0, horizon, r.get("startup_min", 0))
               for rid, r in res.items()}
    pw = {pid: calendar_windows(cfg["calendars"][p["calendar"]], t0, horizon) for pid, p in cfg["people"].items()}
    return Problem(cfg, t0, horizon, orders, tasks, preds, windows, pw, order_last)


def order_completion(prob, sched, oid):
    last = prob.order_last[oid]
    ids = last if isinstance(last, list) else [last]
    return max(sched[i]["end"] for i in ids)


def kpis(prob, sched):
    late, wt, lateq1 = [], 0.0, 0.0
    for o in prob.orders.values():
        c = order_completion(prob, sched, o.id)
        t = max(0, c - o.due)
        if t > 0:
            late.append(o.id)
            if o.priority == 1:
                lateq1 += o.qty
        wt += o.weight * t / 60
    setup = sum(s.get("setup", 0) for s in sched.values())
    return {"orders": len(prob.orders), "late_orders": len(late), "late": late,
            "late_qty_priority1": round(lateq1, 1), "weighted_tardiness_h": round(wt, 1),
            "setup_minutes": setup, "batches": sum(1 for t in prob.tasks.values() if t.kind == "batch"),
            "padding_qty": round(sum(t.padding for t in prob.tasks.values()), 1),
            "makespan_h": round(max(s["end"] for s in sched.values()) / 60, 1)}


def clock(prob, minutes):
    return (prob.t0 + timedelta(minutes=minutes)).strftime("%a %H:%M")


def print_schedule(prob, sched):
    by_res = defaultdict(list)
    for tid, s in sched.items():
        by_res[s["resource"]].append((s["start"], s["end"], s.get("setup", 0), tid))
    for rid in prob.cfg["resources"]:
        rows = sorted(by_res.get(rid, []))
        if not rows:
            continue
        print(f"\n  {rid}")
        for a, b, su, tid in rows:
            t = prob.tasks[tid]
            extra = f"  (+{su} min setup)" if su else ""
            who = ",".join(t.orders) if t.kind == "batch" else ""
            print(f"    {clock(prob, a)} - {clock(prob, b)}  {tid:<34} {t.qty:>8g}  {who}{extra}")
