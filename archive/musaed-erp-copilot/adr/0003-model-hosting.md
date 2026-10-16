# 0003. LLM hosting and data residency

- **Status:** Proposed
- **Date:** 2026-10-17
- **Deciders:** Ahmad Saleh

## Context

Prompts can contain personal data (names, leave, salaries via tool output). Employees and data are in Saudi Arabia (Saudi PDPL: check the rules on cross-border transfer). Expected volume from `cost.py`: ___ questions/month, peak ___ questions/min.

## Options considered

### Option A: Global API provider
- Cost/month: ___ · Data location: ___ · Quality on golden set: ___

### Option B: API provider with an in-region (KSA/GCC) endpoint
- Cost/month: ___ · Availability of models in region: ___

### Option C: Self-hosted open-weight model in-region
- Monthly GPU cost: ___ · Break-even volume vs Option A: ___ · Team ops burden: ___

## Decision

We will ... because ...

## Consequences

- **Revisit if:**
