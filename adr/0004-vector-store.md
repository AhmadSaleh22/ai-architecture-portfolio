# ADR 0004 – Where we store vectors for recommendations

Status: accepted · Oct 2026

## Context

P4 says recommendations start from what the customer is interested in. To match interests with products, the AI turns product descriptions and customer interests into vectors (lists of numbers where similar meanings are close) and looks for the closest ones. Those vectors need a home. ShopCo has 80 products, and the data has to stay in the country.

## Options

| | A. pgvector in our existing PostgreSQL | B. A separate vector database on our servers | C. A managed vector database service abroad |
|---|---|---|---|
| Data leaves the country | No | No | Usually yes |
| New system to run | No | Yes | No, the provider runs it |
| Scale | Fine up to millions of vectors, slower at the top end | Built for large scale | Built for large scale |
| Fit for 80 products | More than enough | Too much | Too much |

## Decision

A – pgvector in the PostgreSQL database we already have.

C breaks the data rule. Between A and B, 80 products don't justify a second database to run and pay for.

## Consequences

- One database to back up and look after.
- Vector search shares the database with orders; at this size that's fine.
- Product vectors are rebuilt in the nightly job when products or descriptions change (ADR 0003). The vectors are made with the in-country API (ADR 0002).

## Revisit if

- The catalogue grows to many thousands of products, or ShopCo becomes a platform for many stores, and searches get slow.
- Vector searches start slowing down orders.
