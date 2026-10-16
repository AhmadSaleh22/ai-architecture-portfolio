# AI Architecture Portfolio

**Author:** Ahmad Saleh
**Course:** [AI Architecture Design](https://academy.mlopsmena.com/en/courses/ai-architecture-design), MLOps MENA Academy (18 Oct – 13 Dec 2026)

This repo holds one end-to-end architecture, built session by session, that becomes my capstone: an enterprise AI system designed for real traffic, security reviews, budgets and regulators.

## Scenario (draft, to be confirmed in Session 1)

**Domain:** Telecom
**System:** *"Wasel"*, a bilingual (Arabic/English) customer-care assistant for a MENA mobile operator, used on WhatsApp, the mobile app and by call-centre agents.

**Business problem.** The operator's contact centre handles ~1.2M conversations/month. ~60% are repetitive (billing questions, bundle info, SIM/eSIM issues, roaming). Average handling time is high and Arabic-dialect self-service is weak.

**What the system does**

1. Answers policy/product questions from internal docs (RAG over Arabic + English PDFs, wikis, tariff sheets).
2. Looks up the customer's own account (bill, balance, active bundles) through existing APIs.
3. Performs a small set of *approved* actions (e.g. activate a roaming bundle) with confirmation and limits.
4. Hands off to a human agent with a summary when confidence is low or the customer asks.

**Why it's a good capstone:** it touches every module: RAG with Arabic, model hosting choice, agents with real tool risk, PII + data-residency rules (Egypt PDPL / Saudi PDPL / UAE PDPL), cost at scale, and measurable quality targets.

## Assumptions (to be validated)

| # | Assumption | Status |
|---|---|---|
| A1 | Peak load ~150 concurrent conversations, ~40K/day | Assumed |
| A2 | Customer data must stay in-region (no cross-border transfer without basis) | Assumed |
| A3 | Existing CRM/billing exposes REST APIs with OAuth2 | Assumed |
| A4 | Knowledge base: ~5K documents, ~60% Arabic, updated weekly | Assumed |
| A5 | Budget target: < $0.02 per resolved conversation in LLM cost | Assumed |

## How to read this repo

| Folder | What's inside |
|---|---|
| [`docs/`](docs/) | One file per session, e.g. `01-framing.md`, `02-building-blocks.md` |
| [`diagrams/`](diagrams/) | Exported PNG/SVG in the root, editable sources in `src/` |
| [`adr/`](adr/) | Architecture Decision Records, one per decision (`0001-...md`) |
| [`capstone/`](capstone/) | Final architecture PDF + slides |

## Progress

- [x] Repo created
- [ ] Session 1: Architecture views, steps & process (18 Oct)
- [ ] Session 2: AI system building blocks (25 Oct)
- [ ] Session 3: LLM & RAG architecture (1 Nov)
- [ ] Midpoint quiz + Capstone Part 1 (due 14 Nov)
- [ ] Session 4: Agentic AI architecture (15 Nov)
- [ ] Session 5: Security, governance, evals (22 Nov)
- [ ] Session 6: Enterprise case studies (29 Nov)
- [ ] Capstone submitted (due 13 Dec, pass ≥ 70/100)
