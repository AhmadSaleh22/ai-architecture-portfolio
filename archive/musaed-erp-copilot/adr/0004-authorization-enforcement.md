# 0004. Where authorisation is enforced

- **Status:** Proposed
- **Date:** 2026-10-17
- **Deciders:** Ahmad Saleh

## Context

Five companies share one assistant. An employee must only see their company's policies and their own payroll data; HR sees payroll for their assigned company; managers see their team's leave. The LLM can be manipulated (prompt injection), so it must never be the component deciding access. Lab evidence: with the tenant filter off, 2 of 2 leakage tests leak.

## Options considered

### Option A: Filter retrieved chunks *after* ranking
### Option B: Filter *before* ranking (tenant/ACL metadata in the index query)
### Option C: Separate index per company
### Option D: Ask the LLM to ignore documents from other companies (anti-pattern: include it to show why)

For payroll data: tools call the ERP **with the end user's token** vs. a service account with full access.

## Decision

We will ... because ...

## Consequences

- **Revisit if:**
