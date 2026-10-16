# Pre-course bootcamp (Fri 16 → Sun 18 Oct)

**Goal:** walk into Session 1 able to do what the course teaches *before* it teaches it. By Sunday 19:00 you should have:

1. A **working PoC** of Musaed with an eval harness and release gates ([`lab/`](lab/))
2. **Numbers**: retrieval hit rate, leakage count, latency, cost per question, monthly cost
3. **C1 + C2 diagrams**
4. **3 ADRs** backed by measurements, not opinions
5. A **threat model draft**
6. A **2-minute pitch** of the system, and answers to the architect drills below

Total: ~12–14 hours. Each block has a "done when" so you know when to stop.

---

## Block 0 · Setup (Fri, 30m)

- [ ] Commit and push everything; repo is **public**
- [ ] Post the repo link in the course study group
- [ ] `python3 prep/lab/eval.py` runs on your Mac

**Done when:** the repo link is posted and the eval prints two result tables.

## Block 1 · Hands-on lab (Fri night + Sat morning, ~4.5h)

Work through exercises **L1–L7** in [`lab/README.md`](lab/README.md). This is the most important block: it gives you first-hand evidence for every module of the course.

**Done when:** SECURE passes all gates (or you can explain exactly why it can't yet), and ADR-0002/0003/0004 each contain at least one real measurement.

## Block 2 · Architecture artifacts (Sat afternoon, ~3h)

**A1. Framing (45m)** → [`docs/01-framing.md`](../docs/01-framing.md)
Fill in the quality-targets table with numbers. Use the lab results as your baseline. Example targets to argue for or against:

| Attribute | Example target |
|---|---|
| Cross-tenant leakage | 0 on a 200-question adversarial set (hard gate) |
| Policy answer correctness | ≥ 90% on golden set, judged by HR |
| Latency | p95 < 4s end-to-end, first token < 1.5s |
| Cost | < $X per active user per month (from `cost.py`) |
| Handoff to HR | 10–20%; lower may mean overconfidence |

**A2. C2 container diagram (1h)** → `diagrams/src/c2-containers.mmd`
Draw the containers inside Musaed. Suggested list; decide which you need and justify the ones you merge:

- Web/mobile client · API gateway (auth, rate limits)
- **Orchestrator** (routing, prompt assembly, guardrails)
- **Retrieval service** + keyword index + vector index (tenant-partitioned?)
- **Ingestion pipeline** (parse, chunk, translate/summarise, embed, ACL metadata)
- **ERP adapter / tools** (calls payroll APIs with the *user's* token, not a service super-user)
- SSO / identity provider · **LLM gateway** (provider routing, caching, quotas, PII redaction)
- **Audit log** · **Eval & monitoring** (offline gates + online signals)

Label every arrow with *what* and *protocol*. Mark which boxes hold personal data.

**A3. ADR review (45m):** reread your three ADRs. Each must have ≥ 2 real options, a measured trade-off, and a "revisit if" line.

**Done when:** a colleague could read C1 → C2 → ADRs and explain your system back to you.

## Block 3 · Threat model (Sat evening, 1.5h)

→ [`docs/threat-model-draft.md`](../docs/threat-model-draft.md), already seeded with 6 threats. Add at least 4 more, including one from exercise L4. For each threat: what's attacked, how likely, how bad, and which control stops it.

**Done when:** every threat has a control *and* a way to test that the control works (ideally a golden-set case).

## Block 4 · Targeted reading (spread across the weekend, ~2h)

Read for *decisions*, not for coverage. After each, write one line in the matching file.

| Read | Why for you | Write to |
|---|---|---|
| c4model.com: the "Diagrams" pages for levels 1–2 | You'll draw these all course | `diagrams/` |
| MADR (Markdown ADR) template and examples | Your ADR format | `adr/` |
| OWASP Top 10 for LLM Applications (latest version) | Session 5 language; your threat model's checklist | threat model |
| Anthropic, "Building effective agents" | Session 4: when *not* to build an agent | `docs/00-...` |
| Saudi PDPL overview from SDAIA (official) | Data residency + cross-border transfer for ADR-0003 | ADR-0003 |
| Any guide on hybrid search + reranking | Session 3; backs ADR-0002 | ADR-0002 |

## Block 5 · Sunday morning: rehearse (1.5h)

**2-minute pitch.** Say it out loud, then record it:
*problem → users → what Musaed does → the one design decision that matters most (tenant-scoped retrieval + tools for payroll) → how you know it's safe (gates) → what it costs.*

**Architect drills.** Answer each out loud in under 90 seconds, with a number where possible:

1. Why not just put the employees table into the vector database?
2. Where exactly is authorisation enforced, and what happens if the LLM is jailbroken?
3. API model or self-hosted? What would change your answer?
4. How do you handle an English question about an Arabic document?
5. A manager asks "who on my team is underpaid?" What do you build, and what do you refuse?
6. What's your p95 latency budget, and how is it split across retrieval, LLM and tools?
7. What's in your release gate, and who can override it?
8. How do you detect quality drift after launch without reading every conversation (privacy)?
9. A policy changes on the 1st of the month. How fast does Musaed reflect it, and how do you know?
10. When is an agent justified here, and what can it *never* do without a human?
11. What do you log, for how long, and where (PDPL)?
12. What's the simplest version you could ship in 4 weeks, and what did you cut?

**Done when:** you can do the pitch without notes and answer 10 of 12 drills confidently.

## Block 6 · During Session 1

Questions to ask the instructor (pick 2):

- Is an ERP/HR copilot an approved capstone domain?
- In your experience, where do enterprise RAG systems most often fail security review?
- How do you set quality targets *before* you have any production data?
- For Arabic-first systems, what's your default retrieval stack?

Take notes directly into `docs/01-framing.md`, and commit the same night.
