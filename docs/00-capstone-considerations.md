# 00 · Before designing: considerations for the Production Planning Copilot

Things to settle **before** drawing boxes. Each one changes the architecture.

## 1. Confidentiality (settle first) ⚠️

The idea comes from my experience as Frontend Lead on a production-planning platform used by 10 plants. That work is covered by my employer's and customers' confidentiality.

- [ ] No real plant names, customer names, screenshots, code, data, KPIs or architecture from that job
- [ ] Use the fictional company **Nahda Beverages** and synthetic data only
- [ ] Describe my experience in general terms ("production planning for multi-plant manufacturing")
- [ ] When unsure, leave it out

## 2. Capstone approval

Manufacturing is not one of the course's default domains (telecom, e-commerce, government).

- [ ] Ask in Session 1: *"Is a manufacturing production-planning copilot an approved capstone domain?"*
- [ ] Fallback if not approved: multi-company ERP AI platform (previous scenario, in `archive/`)

## 3. What the AI does vs. what it must not do

The most important design decision, and the first ADR.

| Job | Who does it | Why |
|---|---|---|
| Detect the disruption, collect context (which orders, which lines are free, repair ETA) | Deterministic code + data pipeline | Must be exact |
| Generate candidate schedules | **Scheduler / optimiser** (heuristic or OR-Tools), *not* the LLM | LLMs are bad at combinatorial constraints |
| Check feasibility (capacity, calendar, format, maintenance, frozen horizon) | **Constraint checker** in code | Hard rules need guarantees, not probabilities |
| Explain trade-offs in plain language (AR/EN), answer "why", cite rules | **LLM** | This is where it adds value |
| Read messy shift notes, flag relevant context | **LLM** | Unstructured, multilingual |
| Approve and apply the change | **Human planner** | Accountability; physical and commercial impact |
| Write to MES/PLC | **Never** | Safety boundary |

> "If the LLM disappeared tomorrow, the planner would still get correct options, just without the explanation." That sentence is a good test of the design.

## 4. Stakeholders

| Who | Wants | Fears |
|---|---|---|
| Production planner (primary user) | Faster, defensible decisions | Losing control, being blamed for AI mistakes |
| Shift supervisor | Fewer surprise changes mid-shift | Plans that ignore floor reality |
| Plant manager | On-time delivery, OEE | Overtime cost, safety incidents |
| Maintenance | Realistic repair windows | Being pressured by "AI says 30 minutes" |
| Sales / key accounts | Early warning on late orders | Hearing it from the customer first |
| OT / cybersecurity | Isolated OT network | A new path from internet into the plant |
| IT / platform team | Supportable system | Another unmanaged AI tool |

## 5. Safety & authority

- Human-in-the-loop for **every** change in v1. Automation (if ever) only after measured acceptance rate and on low-risk actions.
- Respect the **frozen horizon** (running order, first 2 hours) and the escalation matrix (>2h stop → plant manager).
- Proposals that need overtime or customer due-date changes are flagged for approval by the role that owns them.
- Full audit: who saw which proposal, what data `as_of`, what was chosen, outcome.

## 6. OT/IT architecture constraints

- Plants follow a layered network model (the Purdue model): machines and SCADA live in protected OT zones.
- Data leaves OT **one-way** through a DMZ gateway (historian or MQTT broker). The copilot lives in IT/cloud and **cannot** reach back.
- Some plants have **intermittent connectivity**: decide what works locally at the plant (edge) vs. centrally.

## 7. Evaluation: how do we know a proposal is good?

There's no single "correct" answer, so evaluation is layered:

1. **Feasibility** (hard): 0 constraint violations, checked by code. Release gate.
2. **KPI impact** (simulated): orders late, total tardiness, extra changeover minutes vs. the human reference action (`labels/planner_decisions.jsonl`).
3. **Grounding**: every rule the explanation cites exists in the planning rules.
4. **Human acceptance** (online): % of proposals accepted or edited, and time-to-decision.
5. **Safety**: 0 proposals touching the frozen horizon or writing outside the proposal channel.

Eval scenarios: `data/generated/labels/eval_scenarios.jsonl` (one per disruption).

## 8. Latency & scale

- Disruption response is **asynchronous**: < 2 min to first proposal is fine. No need for the fastest model.
- Interactive Q&A must feel live (p95 < 6 s).
- Load is small (tens of disruptions/day across 10 plants), so **cost is driven by integration and data work, not LLM tokens**. Prove it with numbers in Session 2.

## 9. Compliance & data residency

- Mostly **commercial** confidentiality, not personal data, except shift notes and operator IDs (PII → redact).
- Customers or governments may require data to stay in-country (KSA, Egypt, UAE). Check data residency per plant before choosing an LLM hosting option (ADR).
- Don't use AI outputs to evaluate individual operators. Say so explicitly in the governance section.

## 10. Data readiness

See [`data-plan.md`](data-plan.md). Key risks: missing reason codes, clock drift, stale master data, and **no record of past planner decisions**. Plan a data-readiness phase before the AI phase.

## 11. Scope for v1 (proposal)

**In:** breakdown + material-delay disruptions, one plant type (beverage lines), proposals + explanations, planner approval, decision capture, Q&A over rules.
**Out:** automatic execution, cross-plant transfers, workforce scheduling, demand forecasting, rush-order negotiation with customers.

## 12. Open questions for Session 1

- Domain approval (above)
- How much of the optimiser must the capstone design vs. treat as an existing system?
- Expected depth of the OT/IT security section
