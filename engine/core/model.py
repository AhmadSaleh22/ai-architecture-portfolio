"""Core data model. Times are integer minutes from the problem's t0."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional


@dataclass
class Resource:
    id: str
    capacity: int = 1                 # 1 = one task at a time; k = pool or site with k places
    windows: list = field(default_factory=list)     # working windows [(start, end)]
    attrs: dict = field(default_factory=dict)       # skills, size, language, ...
    setups: Optional[dict] = None     # sequence-dependent setups (see setup_minutes)
    kind: str = ""


@dataclass
class Requirement:
    candidates: list                  # resource ids, any one of them
    qty: int = 1                      # units of capacity used (people from a pool)
    during: str = "whole"             # whole | start | end (a 15-min slot at the start or end)
    setup_qty: int = 0                # units also busy during the primary's setup (the crew cleans)


@dataclass
class Task:
    id: str
    jobs: list                        # jobs this task serves (a batch can serve many)
    requirements: list                # requirements[0] is the primary: duration and setups live there
    duration: dict                    # primary candidate -> minutes
    attrs: dict = field(default_factory=dict)       # used by setup rules
    release: int = 0
    deadline: Optional[int] = None    # hard: must end by
    allowed_starts: Optional[list] = None           # e.g. a slot grid or school periods
    preferred: Optional[tuple] = None # soft: (earliest, latest) start the customer would like
    seq: int = 0                      # position inside its job (used by the greedy solver)
    qty: float = 0.0
    info: dict = field(default_factory=dict)        # adapter data (batch loads, labels, ...)


@dataclass
class Job:
    id: str
    due: Optional[int] = None
    priority: int = 9                 # 1 = most important
    weight: float = 1.0
    qty: float = 0.0
    release: int = 0
    last: list = field(default_factory=list)        # task ids whose end is the job's completion
    optional: bool = False            # may be rejected (booking refused, session not placed)
    reject_penalty: float = 0.0
    info: dict = field(default_factory=dict)


@dataclass
class Problem:
    resources: dict
    tasks: dict
    jobs: dict
    preds: list                       # (task_a, task_b, min_lag, max_lag or None)
    horizon: int
    objective: list = field(default_factory=lambda: [{"kpi": "weighted_tardiness"}])
    t0: Optional[datetime] = None
    frozen: dict = field(default_factory=dict)      # task -> {"start", "res"}: must stay as is
    previous: dict = field(default_factory=dict)    # last plan, for the stability objective
    extra_checks: list = field(default_factory=list)  # adapter checks: f(problem, schedule) -> [str]
    meta: dict = field(default_factory=dict)

    def clock(self, m):
        if self.t0 is None:
            return f"{m // 1440}d {m % 1440 // 60:02d}:{m % 60:02d}"
        return (self.t0 + timedelta(minutes=m)).strftime("%a %H:%M")

    def job_tasks(self, jid):
        return [t for t in self.tasks.values() if jid in t.jobs]


SLOT = 15   # minutes a "start" or "end" requirement keeps its resource busy


def span(start, end, during):
    if during == "start":
        return start, min(end, start + SLOT)
    if during == "end":
        return max(start, end - SLOT), end
    return start, end


def setup_minutes(res, prev_attrs, next_attrs):
    """Sequence-dependent setup on a resource.

    setups: {by: key or [keys], default_min, rules: [{from, to, min}], extra_if_changed: {key: min}}
    Rules compare the first key: matching rules -> the largest, no match -> default_min,
    same value -> 0. extra_if_changed adds minutes when another key changes (e.g. bottle size).
    """
    st = res.setups if isinstance(res, Resource) else res.get("setups")
    if not st or prev_attrs is None:
        return 0
    keys = st["by"] if isinstance(st["by"], list) else [st["by"]]
    a, b = prev_attrs.get(keys[0]), next_attrs.get(keys[0])
    total = 0
    if a != b:
        hits = [r["min"] for r in st.get("rules", [])
                if "same" not in (r["from"], r["to"]) and r["from"] in ("*", a) and r["to"] in ("*", b)]
        total = max(hits) if hits else st.get("default_min", 0)
    for k, extra in (st.get("extra_if_changed") or {}).items():
        if prev_attrs.get(k) != next_attrs.get(k):
            total += extra
    return total


def intersect(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        s, e = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if s < e:
            out.append((s, e))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def subtract(windows, blocks):
    out = list(windows)
    for b0, b1 in blocks:
        nxt = []
        for s, e in out:
            if b1 <= s or b0 >= e:
                nxt.append((s, e))
                continue
            if s < b0:
                nxt.append((s, b0))
            if b1 < e:
                nxt.append((b1, e))
        out = nxt
    return out


def inside(windows, a, b):
    return a >= b or any(w0 <= a and b <= w1 for w0, w1 in windows)
