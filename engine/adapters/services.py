"""Service-catalogue adapter: one adapter for every "book people, rooms and equipment" domain.

A domain is described entirely in YAML:
  resources   doctors, rooms, devices, teachers, class groups, buses, guides, sites ...
              each with a type, a calendar, a capacity, skills/attributes and optional setups
  services    what a customer can ask for, as a chain of steps; each step names its primary
              resource (it holds the duration and the setups) and what else it needs
  classes     urgency / priority classes: priority, weight, due, can it be refused?
A request (CSV row or dict) asks for one service, with times, preferences and fixed choices
("doctor=dr_layla", "group=G1"). Clinics, schools and tour operators differ only in their YAML
plus, for schools and travel, a few lines that expand a timetable or an itinerary into requests.

Selectors pick candidate resources:
  {type: doctor, skill: cardio}      {id: room_3}      {type: bus, min: {seats: size}}
  {type: room, attr: {kind: lab}}    "size" (or any request field) is read from the request.
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from core import Job, Problem, Requirement, Resource, Task
from core.calendar import windows as cal_windows

DAYNAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def load_config(path):
    cfg = yaml.safe_load(Path(path).read_text())
    cfg["_path"] = str(path)
    return cfg


def _ts(v, t0):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    return int((datetime.fromisoformat(str(v)) - t0).total_seconds() // 60)


def select(cfg, sel, req, fixed):
    """Candidate resource ids for a selector, honouring fixed choices in the request."""
    out = []
    for rid, r in cfg["resources"].items():
        if "id" in sel and rid != sel["id"]:
            continue
        if "type" in sel and r.get("type") != sel["type"]:
            continue
        if "skill" in sel:
            want = req.get(sel["skill"][1:], "") if str(sel["skill"]).startswith("$") else sel["skill"]
            if want not in (r.get("skills") or []):
                continue
        if any((r.get("attrs") or {}).get(k) != v for k, v in (sel.get("attr") or {}).items()):
            continue
        if any(float((r.get("attrs") or {}).get(k, 0)) < float(req.get(f, f) if isinstance(f, str) else f)
               for k, f in (sel.get("min") or {}).items()):
            continue
        out.append(rid)
    if "id_from" in sel:                         # e.g. the group's own resource: {type: group, id_from: group}
        out = [r for r in out if r == req.get(sel["id_from"])]
    t = sel.get("type")
    if t and t in fixed:
        out = [r for r in out if r == fixed[t]]
    return out


def allowed_starts(cfg, t0, horizon):
    """Start grid: every slot_min minutes, or fixed daily periods (schools)."""
    m = cfg["meta"]
    if m.get("periods"):
        out = []
        days = (horizon // 1440) + 2
        for d in range(-1, days):
            day = (t0 + timedelta(days=d)).date()
            for p in m["periods"]:
                h, mi = p.split(":")
                st = int((datetime.combine(day, datetime.min.time()) + timedelta(hours=int(h), minutes=int(mi)) - t0)
                         .total_seconds() // 60)
                if 0 <= st < horizon:
                    out.append(st)
        return sorted(out)
    g = m.get("slot_min")
    return list(range(0, horizon, g)) if g else None


def build(cfg, requests, start, now=None):
    """requests: list of dicts (see module doc). Returns a core.Problem."""
    t0 = datetime.fromisoformat(start) if isinstance(start, str) else start
    H = cfg["meta"].get("horizon_days", 5) * 1440
    R = {}
    for rid, r in cfg["resources"].items():
        W = cal_windows(cfg["calendars"][r["calendar"]], t0, H)
        R[rid] = Resource(rid, r.get("capacity", 1), W, {**(r.get("attrs") or {}), "type": r.get("type"),
                          "skills": r.get("skills", [])}, r.get("setups"), r.get("type", ""))
    grid = allowed_starts(cfg, t0, H)
    T, J, preds = {}, {}, []
    for q in requests:
        cls = cfg["classes"][q["class"]]
        svc = cfg["services"][q["service"]]
        fixed = dict(x.split("=") for x in (q.get("fixed") or "").split(";") if "=" in x)
        release = max(_ts(q.get("release"), t0) or 0, _ts(now, t0) or 0) if now else (_ts(q.get("release"), t0) or 0)
        due = _ts(q.get("due"), t0)
        if due is None and cls.get("due_after_min") is not None:
            due = release + cls["due_after_min"]
        jid = q["id"]
        prev, tids = None, []
        for i, st in enumerate(svc["steps"]):
            tid = f"{jid}:{st['id']}"
            over = (q.get("steps") or {}).get(st["id"], {})
            prim = select(cfg, st["primary"], q, fixed)
            reqs = [Requirement(prim)]
            for n in st.get("needs", []):
                reqs.append(Requirement(select(cfg, n, q, fixed), n.get("qty", 1), n.get("during", "whole"),
                                        n.get("setup_qty", 0)))
            if any(not r.candidates for r in reqs):
                raise ValueError(f"request {jid} step {st['id']}: no resource matches {st}")
            d = st["duration"]
            dur = {r: int(d.get(cfg["resources"][r].get("type"), d.get("default")) if isinstance(d, dict) else d)
                   for r in prim}
            attrs = {**(st.get("attrs") or {}), **({k[5:]: v for k, v in q.items() if k.startswith("attr_") and v})}
            pref = None
            pf, pt = _ts(over.get("pref_from", q.get("pref_from") if i == 0 else None), t0), \
                _ts(over.get("pref_to", q.get("pref_to") if i == 0 else None), t0)
            if pf is not None or pt is not None:
                pref = (pf if pf is not None else 0, pt if pt is not None else H)
            T[tid] = Task(id=tid, jobs=[jid], requirements=reqs, duration=dur, attrs=attrs,
                          release=max(release, _ts(over.get("release"), t0) or 0),
                          deadline=_ts(over.get("deadline"), t0) if over.get("deadline") else None,
                          allowed_starts=grid if st.get("on_grid", True) else None,
                          preferred=pref, seq=i, info={"step": st["id"], "label": st.get("label", st["id"])})
            if prev:
                lag = svc["steps"][i - 1].get("then", {})
                preds.append((prev, tid, lag.get("min", 0), lag.get("max")))
            prev = tid
            tids.append(tid)
        J[jid] = Job(jid, due, cls["priority"], cls.get("weight", 1), float(q.get("qty") or 1), release, [prev],
                     optional=cls.get("optional", False), reject_penalty=cls.get("reject_penalty", 1),
                     info={"class": q["class"], "service": q["service"], "who": q.get("who", "")})
    return Problem(R, T, J, preds, H, cfg.get("objective", [{"kpi": "weighted_tardiness"}]), t0,
                   meta={"domain": cfg["meta"].get("domain"), "name": cfg["meta"]["name"], "cfg": cfg})


def read_requests(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def print_plan(prob, sched, rejected=(), by="type"):
    """Agenda per resource (people and rooms), readable in a terminal."""
    rows = {}
    for tid, s in sched.items():
        for r in s["res"]:
            rows.setdefault(r, []).append((s["start"], s["end"], tid, s.get("setup", 0) if r == s["res"][0] else 0))
    for rid in prob.resources:
        if rid not in rows:
            continue
        res = prob.resources[rid]
        print(f"\n  {rid} ({res.kind}{', x' + str(res.capacity) if res.capacity > 1 else ''})")
        for a, b, tid, su in sorted(rows[rid]):
            j = prob.jobs[prob.tasks[tid].jobs[0]]
            extra = f"  +{su} min setup" if su else ""
            print(f"    {prob.clock(a)}-{prob.clock(b)[-5:]}  {tid:<24} {j.info.get('class', '')}{extra}")
    if rejected:
        print(f"\n  not placed: {', '.join(rejected)}")
