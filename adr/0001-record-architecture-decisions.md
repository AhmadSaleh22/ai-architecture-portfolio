# 0001. Record architecture decisions as ADRs

- **Status:** Accepted
- **Date:** 2026-10-16
- **Deciders:** Ahmad Saleh

## Context

The capstone needs a traceable record of *why* the architecture looks the way it does, not just *what* it is. Decisions will be made session by session over 7 weeks and some will be revised as later modules (security, evals) expose new constraints.

## Options considered

### Option A: Decisions inline in each session doc
- Pros: less files
- Cons: hard to find, no status/supersession, reasons get lost in notes

### Option B: One ADR per significant decision (MADR-style)
- Pros: searchable, reviewable in PRs, shows how thinking evolved; industry standard
- Cons: small overhead per decision

## Decision

We will use one Markdown ADR per significant decision in `adr/`, numbered sequentially, using `0000-template.md`.

## Consequences

- **Positive:** reviewers can follow the reasoning; the commit history doubles as a decision log.
- **Negative:** must discipline myself to write the ADR when the decision is made, not at the end.
- **Revisit if:** the course requires a different format.
