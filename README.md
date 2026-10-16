# AI Architecture Portfolio

**Author:** Ahmad Saleh
**Course:** [AI Architecture Design](https://academy.mlopsmena.com/en/courses/ai-architecture-design), MLOps MENA Academy (18 Oct – 13 Dec 2026)

This repo holds one end-to-end architecture, built session by session, that becomes my capstone: an enterprise AI system designed for real traffic, security reviews, budgets and regulators.

## Scenario (draft, to be confirmed in Session 1)

**Domain:** Enterprise HR, payroll & finance (own domain, needs instructor approval)
**System:** *"Musaed"*, a bilingual (Arabic/English) AI copilot on top of an in-house ERP for a Saudi holding group.

> Inspired by an ERP I built and led (team of 5) for **1,400 employees across 5 companies** in Saudi Arabia: payroll, finance and treasury, with org/payroll/finance data modelled in Neo4j behind REST APIs. Company details are generalised; numbers marked *Assumed* are mine to validate.

**Business problem.** HR and finance teams spend much of their time answering repetitive questions ("How many leave days do I have?", "Why did my salary change this month?", "What's the travel allowance policy?") and producing ad-hoc reports. Policies differ per company, exist in Arabic and English, and the data is highly sensitive (salaries, IDs, bank details).

**What the system does**

1. **Policy Q&A:** answers HR/finance policy questions from Arabic + English documents (RAG), scoped to the employee's own company.
2. **Personal data lookup:** "my payslip", "my leave balance", read only through existing ERP APIs, never by putting raw payroll tables into the prompt.
3. **Approved actions (agent):** draft a leave request or expense claim; the employee confirms, and the normal manager approval flow still applies.
4. **Manager & finance analytics:** natural-language questions over the org/payroll graph ("headcount cost by department in Company C, Q3"), limited by role.
5. **Handoff:** escalates to HR with a summary when unsure or when the topic is sensitive (disputes, terminations).

**Why it's a strong capstone:** it hits every module: access-controlled RAG across 5 tenants, Arabic/English retrieval, LLM hosting under data-residency rules (Saudi PDPL), an agent touching money and HR records (approvals, guardrails), prompt-injection and data-leakage threats (one employee seeing another's salary), and measurable quality and cost targets.

## Assumptions (to be validated)

| # | Assumption | Source |
|---|---|---|
| A1 | 1,400 employees, 5 companies, each with its own policies | From my experience |
| A2 | Org, payroll and finance data in Neo4j behind REST APIs; hosting on AWS/GCP | From my experience |
| A3 | Employee and payroll data must stay in Saudi Arabia (Saudi PDPL) | Assumed, to verify in Session 5 |
| A4 | ~300 policy/procedure documents, ~50% Arabic, updated monthly | Assumed |
| A5 | ~30% of employees use it weekly; peak ~50 concurrent users at month-end payroll | Assumed |
| A6 | Existing SSO with roles: employee, manager, HR, finance, admin | Assumed |
| A7 | LLM cost target < $1,000/month at full adoption | Assumed |

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
