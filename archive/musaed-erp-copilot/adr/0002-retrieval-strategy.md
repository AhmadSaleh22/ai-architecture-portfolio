# 0002. Retrieval strategy for Arabic/English policies

- **Status:** Proposed
- **Date:** 2026-10-17
- **Deciders:** Ahmad Saleh

## Context

Policies are ~50% Arabic, ~50% English; employees ask in either language (and in dialect). In the lab, lexical BM25 with Arabic normalisation scores `retrieval_hit@3 = 0.88`: it misses English questions about Arabic documents (q02). Target: ≥ 0.95 with p95 retrieval latency < ___ ms.

## Options considered

### Option A: BM25 only (baseline)
- Evidence: hit@3 0.88 · latency ___ · extra cost $0

### Option B: Hybrid BM25 + multilingual embeddings (RRF)
- Evidence: hit@3 ___ · latency ___ · extra cost ___

### Option C: Translate query to the other language, then BM25
- Evidence: hit@3 ___ · latency ___ · extra cost ___ (one extra LLM call)

### Option D: English summary of each Arabic doc at ingestion
- Evidence: hit@3 ___ · ingestion cost ___

## Decision

We will ... because ...

## Consequences

- **Positive:**
- **Negative / trade-offs:**
- **What we'll monitor:**
- **Revisit if:**
