# AI Architecture Portfolio

**Author:** Ahmad Saleh
**Course:** [AI Architecture Design](https://academy.mlopsmena.com/en/courses/ai-architecture-design), MLOps MENA Academy (18 Oct – 13 Dec 2026)

This repo holds one end-to-end architecture, built session by session, that becomes my capstone: an enterprise AI system designed for real traffic, security reviews, budgets and regulators.

## Scenario (draft, to be confirmed in Session 1)

**Domain:** Manufacturing: multi-plant production planning (own domain, needs instructor approval)
**System:** *Production Planning Copilot* for **Nahda Beverages**, a fictional beverage manufacturer with 10 plants in Saudi Arabia, Egypt and the UAE.

> Inspired by my experience leading frontend architecture for a production-planning platform used by 10 manufacturing plants. The company, data and numbers here are **fictional and synthetic**; no employer or customer information is used.

**Business problem.** When a line breaks down, a material delivery is late or a rush order arrives, planners rebuild the plan by hand across several systems. That takes 10–90 minutes per disruption. In the synthetic baseline, **20% of critical orders and 19% of high-priority orders finish late**, and changeovers eat 33–80 hours per line per month.

**What the copilot does**

1. **Detects** disruptions from machine events, deliveries and new orders, and identifies affected orders.
2. **Generates options** with a scheduler/optimiser (not the LLM), and **checks feasibility** in code: capacity, calendar, format, maintenance, frozen horizon.
3. **Explains** each option in Arabic or English: impact on late orders, extra changeovers, which rules apply (cited), and what the shift notes say.
4. **Planner decides**: approve, edit or reject. The decision and its reason are recorded. Nothing is written to MES/PLC.
5. **Answers questions** like "Why is line 3 behind?" or "Can we fit this rush order?"

**Why it's a strong capstone:** an agent whose suggestions have physical and commercial consequences; a clear split between LLM and deterministic optimisation; OT/IT security boundaries; edge vs. cloud for plants with weak connectivity; messy multilingual data; and evaluation without a single "right answer".

Before designing, read [`docs/00-capstone-considerations.md`](docs/00-capstone-considerations.md) and [`docs/data-plan.md`](docs/data-plan.md).

## Assumptions (to be validated)

| # | Assumption | Source |
|---|---|---|
| A1 | 10 plants, ~40 lines, ~200 machines | Inspired by experience (generalised) |
| A2 | Existing ERP, MES, APS/planning tool and CMMS; OT data leaves via a one-way DMZ gateway | Typical industrial setup, assumed |
| A3 | 10–30 significant disruptions per day across all plants | Synthetic data |
| A4 | Planners accept the copilot only if every proposal is feasible and explainable | Assumed, to validate with users |
| A5 | Past planner decisions are **not** recorded today | Assumed (common in practice) |
| A6 | Some plants have intermittent connectivity | Assumed |

## How to read this repo

| Folder | What's inside |
|---|---|
| [`docs/`](docs/) | One file per session, e.g. `01-framing.md`, `02-building-blocks.md` |
| [`diagrams/`](diagrams/) | Exported PNG/SVG in the root, editable sources in `src/` |
| [`adr/`](adr/) | Architecture Decision Records, one per decision (`0001-...md`) |
| [`capstone/`](capstone/) | Final architecture PDF + slides |
| [`data/`](data/) | Synthetic factory data generator + data contracts/baseline KPIs |
| [`engine/`](engine/) | Industry-agnostic scheduling engine: factory config format, coffee + beverage configs, config checker |
| [`archive/`](archive/) | Earlier scenario (ERP/HR copilot) kept as a fallback and practice lab |

## Progress

- [x] Repo created
- [x] Capstone considerations + data plan + synthetic data
- [ ] Session 1: Architecture views, steps & process (18 Oct)
- [ ] Session 2: AI system building blocks (25 Oct)
- [ ] Session 3: LLM & RAG architecture (1 Nov)
- [ ] Midpoint quiz + Capstone Part 1 (due 14 Nov)
- [ ] Session 4: Agentic AI architecture (15 Nov)
- [ ] Session 5: Security, governance, evals (22 Nov)
- [ ] Session 6: Enterprise case studies (29 Nov)
- [ ] Capstone submitted (due 13 Dec, pass ≥ 70/100)
