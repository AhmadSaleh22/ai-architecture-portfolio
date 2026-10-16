# 00 · Before Session 1: primer & prep

Personal prep notes before Session 1 (Sun 18 Oct, 19:00 Cairo).

## 1. Pre-course checklist

- [x] Push this repo to GitHub as **public** `ai-architecture-portfolio`
- [ ] Post the repo link in the course study group **before Sun 18 Oct**
- [ ] Confirm or change the capstone domain (see §4)
- [ ] Skim §2 (C4) and §3 (ADRs) and bring one question about each

## 2. C4 model: four zoom levels

C4 (Simon Brown) describes software at four levels, like zooming in on a map. Each diagram answers a question for a specific audience.

| Level | Question it answers | Audience | Shows |
|---|---|---|---|
| **1. System Context** | What is the system and who/what does it talk to? | Everyone, incl. business | The system as one box, users (people), external systems |
| **2. Container** | What are the deployable/runnable parts and how do they talk? | Engineers, ops, security | Apps, APIs, databases, queues, model servers + protocols |
| **3. Component** | What's inside one container? | Developers of that container | Major modules (e.g. retriever, reranker, prompt builder) |
| **4. Code** | How is a component implemented? | Rarely drawn | Classes; usually skip it |

**Rules that make C4 diagrams good**

- Every box has a **name, type, technology and one-line responsibility**.
- Every arrow has a **label** (what + how, e.g. "Sends query [HTTPS/JSON]"). Prefer one-directional arrows.
- Include a **title, legend and scope**. A diagram must make sense without a speaker.
- In AI systems, draw the **LLM provider, vector store, eval/monitoring and guardrails** as explicit boxes. They are where cost, latency and risk live.
- Supplementary views worth knowing: **dynamic** (numbered request flow), **deployment** (where it runs: region, VPC, GPU nodes).

Draft context diagram for the scenario: [`../diagrams/src/c4-context.mmd`](../diagrams/src/c4-context.mmd). Also read [`00-capstone-considerations.md`](00-capstone-considerations.md) and [`data-plan.md`](data-plan.md).

## 3. Architecture Decision Records (ADRs)

An ADR captures **one significant decision**, why it was made, and what it costs. ADRs are append-only: you don't edit an old decision, you write a new one that *supersedes* it.

**When to write one:** the decision is hard to reverse, costly, contested, or affects quality attributes (security, latency, cost, compliance). E.g. API vs self-hosted LLM, vector DB choice, data residency approach, whether to use an agent at all.

**Structure (MADR-style, see [`../adr/0000-template.md`](../adr/0000-template.md))**

1. **Context:** the forces: requirements, constraints, numbers.
2. **Options considered:** at least 2 real options (including "do nothing" when relevant).
3. **Decision:** the chosen option, in one sentence.
4. **Consequences:** good, bad, and what we now need to monitor.

**Good ADR habits:** quantify (latency, $/month, accuracy on *your* eval set), name what would make you revisit, keep it to one page.

## 4. Capstone domain options

| Option | Pros | Cons |
|---|---|---|
| **Manufacturing production-planning copilot (current)** | Closest to my latest role (multi-plant planning); agent with physical/commercial consequences; LLM vs optimiser split; OT/IT security; edge vs cloud | Needs instructor approval; must stay clear of employer-confidential details |
| ERP / HR & finance copilot (fallback, in `archive/`) | Built on my ERP experience; access-controlled RAG; Saudi PDPL | More common "assistant" pattern |
| Government citizen-services agent | Strongest regulatory story | No first-hand experience |

## 5. Framing questions to answer during/after Session 1

1. Who are the users and what job are they trying to get done?
2. What does "good" mean, in numbers? (resolution rate, latency p95, cost/conversation, hallucination rate)
3. What's in scope for v1, and what is explicitly **out**?
4. What are the hard constraints? (data residency, existing systems, budget, team skills)
5. What's the non-AI baseline, and why isn't it enough?
6. What's the worst thing this system could do, and who would notice?
