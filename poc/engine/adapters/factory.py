"""Factory adapter: orders -> recipe -> green kg -> roast/syrup batches + order tasks -> core.Problem.

The domain logic (recipes, loss, batching, stage lags) stays in model.py. This file only maps it
onto the core vocabulary and adds the factory-only checks (batch size, no mixed owners, coverage).
"""
from collections import defaultdict

from core import Job, Problem, Requirement, Resource, Task
import model as fm


def to_core(fp):
    """fp = model.Problem (factory). Returns a core.Problem with the same meaning."""
    cfg = fp.cfg
    R = {}
    for rid, r in cfg["resources"].items():
        R[rid] = Resource(rid, 1, fp.windows[rid], {"stage": r["stage"]}, r.get("setups"), "machine")
    for pid, p in cfg["people"].items():
        R[pid] = Resource(pid, p["count"], fp.people_windows[pid], {"skills": p.get("skills", [])}, None, "people")

    stage_idx = {s["id"]: i for i, s in enumerate(cfg["stages"])}
    T = {}
    for tid, t in fp.tasks.items():
        first = cfg["resources"][t.eligible[0]]
        reqs = [Requirement(list(t.eligible))]
        for i, (pool, q, during) in enumerate(fm.people_need(first)):
            reqs.append(Requirement([pool], q, during, setup_qty=1 if i == 0 else 0))
        T[tid] = Task(id=tid, jobs=list(t.orders), requirements=reqs,
                      duration={r: fm.duration(cfg["resources"][r], t.qty) for r in t.eligible},
                      attrs=dict(t.attrs), release=t.release, seq=stage_idx[t.stage], qty=t.qty,
                      info={"kind": t.kind, "stage": t.stage, "loads": t.loads, "padding": t.padding})
    J = {}
    for o in fp.orders.values():
        last = fp.order_last.get(o.id)
        last = [] if last is None else (last if isinstance(last, list) else [last])
        J[o.id] = Job(o.id, o.due, o.priority, o.weight, o.qty, o.release, last,
                      info={"class": o.cls, "product": o.product, "customer": o.customer})
    prob = Problem(R, T, J, list(fp.preds), fp.horizon, cfg["objective"], fp.t0,
                   meta={"domain": "factory", "name": cfg["meta"]["name"], "factory": fp})
    prob.extra_checks.append(batch_checks)
    return prob


def batch_checks(prob, sched):
    """Factory-only rules: batch size, never mix owners, every order's material is covered."""
    fp = prob.meta["factory"]
    cfg = fp.cfg
    v, need = [], defaultdict(float)
    for tid, t in fp.tasks.items():
        if t.kind != "batch" or tid not in sched:
            continue
        cap = cfg["resources"][sched[tid]["res"][0]]["capacity"]
        if not cap["min"] - 1e-6 <= t.qty <= cap["max"] + 1e-6:
            v.append(f"{tid}: batch size {t.qty} outside [{cap['min']}, {cap['max']}]")
        if sum(q for _, _, q in t.loads) > t.qty + 1e-3:
            v.append(f"{tid}: loads exceed batch size")
        owners = {fp.orders[o].customer if cfg["order_classes"][fp.orders[o].cls]["owner"] == "customer" else "own"
                  for o, _, _ in t.loads}
        if len(owners) > 1:
            v.append(f"{tid}: mixes material of different owners {sorted(owners)}")
        for o, m, q in t.loads:
            need[(o, t.stage, m)] += q
    if not fp.progress:
        for o in fp.orders.values():
            for s in cfg["stages"]:
                if s.get("batching") and s["id"] in cfg["products"][o.product]["route"]:
                    for m, q, _ in fm._loads(cfg, s["id"], o):
                        if need[(o.id, s["id"], m)] < q - 1e-2:
                            v.append(f"{o.id}: {m} covered {need[(o.id, s['id'], m)]:.2f} of {q:.2f}")
    return v


def build(config_path, orders_csv, start, **kw):
    fp = fm.build(fm.load_config(config_path), orders_csv, start, **kw)
    return to_core(fp)


def kpis(prob, sched, rejected=()):
    from core.kpi import kpis as core_kpis
    k = core_kpis(prob, sched, rejected)
    fp = prob.meta["factory"]
    k["batches"] = sum(1 for t in fp.tasks.values() if t.kind == "batch")
    k["padding_qty"] = round(sum(t.padding for t in fp.tasks.values()), 1)
    return k
