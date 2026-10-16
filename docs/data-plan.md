# Data plan · Production Planning Copilot

> What data the copilot needs, where it comes from, how fresh and trustworthy it must be, and who may see it.
> All data in this repo is **synthetic** (see [`../data/`](../data/)). No real plant, customer or employer data.

## 1. The decision we support (start here, not with the data)

**Decision:** *"A disruption just happened (breakdown, late material, rush order). What should we do with the affected orders in the next 24–72 hours?"*

Today a planner answers this by opening 4–6 screens, calling maintenance and the warehouse, and rebuilding the plan by hand (often 30–90 minutes). Every data source below exists because this decision needs it. Data that doesn't serve the decision is out of scope for v1.

## 2. Data sources

| # | Domain | Example fields | Source system (real world) | Type | Freshness needed | Volume (10 plants) |
|---|---|---|---|---|---|---|
| D1 | Plants, lines, machines | line type, nominal rate, criticality | ERP / MES master data | Master | Daily | ~40 lines, ~200 machines |
| D2 | Products, BOM, changeover matrix | family, format, CIP minutes | ERP / PLM | Master | Daily | ~30–300 SKUs |
| D3 | Shift calendar | working shifts, holidays, weekends | HR / MES | Master | Daily | small |
| D4 | Work orders | qty, due date, priority, customer | ERP | Transactional | **≤ 5 min** | ~150/day |
| D5 | Current schedule | sequence, planned start/end per line | APS / planning tool | Transactional | **≤ 1 min** | ~600 active rows |
| D6 | Machine state events | RUNNING / DOWN / CHANGEOVER + reason code | MES / SCADA (via OT gateway) | Event stream | **≤ 1 min** | ~50–150k/month |
| D7 | Production counts | good / scrap per hour | MES | Time series | ≤ 15 min | ~300k rows/month |
| D8 | Material deliveries | expected vs actual arrival | ERP / WMS | Transactional | ≤ 15 min | ~1–2k/month |
| D9 | Maintenance plan + work orders | PM windows, repair ETA | CMMS | Transactional | ≤ 15 min | ~1k/month |
| D10 | Planning rules, SOPs, escalation matrix | free text (EN + AR) | SharePoint / QMS | Documents | On change | ~50–500 docs |
| D11 | Shift handover notes | messy text, AR/EN/Franco-Arabic, names | MES notes / WhatsApp groups (!) | Unstructured | ≤ 1 shift | ~100/day |
| D12 | Past planner decisions + outcome | action, rationale, orders late after | Not captured today ⚠️ | Labels | Batch | ~5–20/day |

**Observation:** D12 doesn't exist in most factories. Planners decide and nobody records *why*. Without it, we can't evaluate the copilot or learn from history. **Capturing decisions is a v1 requirement**, not a nice-to-have.

## 3. How each kind of data is used (and why it matters architecturally)

| Kind | Used for | Stored in | NOT used for |
|---|---|---|---|
| Master + transactional (D1–D5, D8, D9) | Feasibility checks, schedule simulation, "what orders are affected" | Relational DB / read replica | Never embedded into a vector index: numbers must be exact and current |
| Events + counts (D6, D7) | Current line state, OEE, repair-time estimates (MTTR by reason) | Time-series store | Not sent raw to the LLM; aggregated first |
| Documents (D10) | Planning rules and constraints the copilot must respect and cite | Search index (hybrid) | Not the source of truth for numbers |
| Notes (D11) | Context ("valve still leaking"), early warning | Search index **after PII redaction** | Never shown across plants without redaction |
| Decisions (D12) | Evaluation set, few-shot examples, KPI on acceptance rate | Relational DB | Not for automatic action |

**Principle:** *the LLM explains and proposes; deterministic code checks feasibility and computes KPIs.* A schedule proposal is accepted only if a constraint checker (not the model) says it is feasible.

## 4. Data contracts (enforced before data reaches the copilot)

Implemented in [`../data/validate.py`](../data/validate.py). The **BLOCK** level stops the pipeline; **WARN** is logged and monitored.

| Contract | Level | Why |
|---|---|---|
| Every scheduled WO exists in ERP | BLOCK | A proposal about a phantom order destroys trust |
| Product format matches line type | BLOCK | Physically impossible schedules |
| No overlapping WOs on a line | BLOCK | Same |
| Event end > start; machine exists | BLOCK | Broken telemetry |
| Counts non-negative | BLOCK | Counter resets corrupt OEE |
| DOWN reason code filled ≥ 95% | BLOCK | Without reasons there's no MTTR estimate, and "how long will it be down?" is the key question |
| No duplicate events | WARN | Inflates downtime; dedupe in pipeline |
| Events inside working calendar | WARN | Detects PLC clocks not synced to NTP |

The generator injects one example of each problem on purpose. A good pipeline must catch all of them.

## 5. Freshness & latency budget

A proposal is only as good as the state it was based on. Every proposal carries an **`as_of` timestamp per source**, and the UI shows it. If D5 or D6 is older than its freshness target, the copilot must say so instead of proposing.

| Path | Target |
|---|---|
| Machine event → available to copilot | < 60 s |
| Disruption detected → first proposal shown | < 2 min (not interactive, can run async) |
| Interactive question ("why is L3 behind?") → answer | p95 < 6 s |

## 6. Access & sensitivity

| Data | Sensitivity | Rule |
|---|---|---|
| Schedules, OEE, orders | Commercially confidential | Plant users see their plant; regional planners see their region |
| Customer names on orders | Confidential | Shown to planners; masked in logs and in LLM prompts where not needed |
| Shift notes | **Personal data** (names, sometimes blame) | Redact names before indexing; do not use for individual performance evaluation |
| Planning rules / SOPs | Internal | All planning users |
| OT network data | Safety-critical zone | One-way flow OT → IT through a DMZ gateway; **nothing** from the copilot writes back to MES/PLC |

## 7. Data quality reality (expect this in any real factory)

- Reason codes are skipped or set to "OTHER" when operators are busy.
- PLC clocks drift; time zones and daylight-saving handling differ by system.
- Master data is stale: nominal rates were set at commissioning years ago.
- Changeovers are logged as downtime, or not logged at all.
- The real schedule lives in an Excel file, not in the planning system.

**Architectural consequence:** budget time for a data-readiness phase *before* the AI phase, and make data quality a monitored KPI, not a one-off cleanup.

## 8. Baseline (from synthetic data, `validate.py`)

| Metric | Baseline (no copilot) |
|---|---|
| OEE | 72–79% per line |
| Changeover hours / line / month | 33–80 h |
| Critical orders finished late | 20% (5/25) |
| High-priority orders late | 19% |
| Rush orders waiting to be scheduled | 12 |
| Planner time-to-decision after a disruption | 10–90 min (labels) |

These are the numbers the copilot must improve. Targets go in [`01-framing.md`](01-framing.md).
