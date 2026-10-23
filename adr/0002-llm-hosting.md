# ADR 0002 – Where the LLM runs

Status: accepted · Oct 2026

## Context

The AI reads customer data (purchases, interests, ratings) to suggest offers and recommendations. ShopCo's data has to stay in the country, in transit and at rest, and personal data falls under PDPL. ShopCo is a small store: about 100 sales a month and 50 users at a time.

## Options

| | A. API, hosted in the country | B. Open model on our own servers in the country | C. API abroad, personal data removed |
|---|---|---|---|
| Data leaves the country | No | No | Yes – interests and purchases are still personal |
| Cost | Pay per use | Fixed and high (GPU servers run all day, used or not) | Pay per use |
| Who runs it | The provider | Us | The provider |
| Model quality | Strongest models available | Open models only | Strongest models available |

## Decision

A – an LLM API from a provider with servers in the country.

C breaks the data rule. Between A and B, A keeps the data in the country, costs only what we use, and someone else runs it, which fits a store this size.

## Consequences

- We depend on one provider's prices and on it keeping servers in the country.
- Every call goes through our own code first, so the rules in P1 and P3 apply whatever model we use.

## Revisit if

- ShopCo grows a lot, or becomes a platform for many stores, and the monthly API bill gets close to what our own servers would cost.
- The provider raises prices a lot or stops offering servers in the country.
