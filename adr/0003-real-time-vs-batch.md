# ADR 0003 – Real-time or batch

Status: accepted · Oct 2026

## Context

Some parts of the system need to react the moment something happens; others can wait for a nightly run. Real-time costs more and is harder to build and run, so it should only be used where a delay breaks something.

## Options

| | A. Everything batch (once a night) | B. Everything real-time | C. Real-time only where a delay breaks something |
|---|---|---|---|
| Cost and effort | Lowest | Highest | In between |
| Message limit (P3) | Breaks: messages sent since last night aren't counted | Works | Works |
| Abandoned-cart reminder | Arrives the next day, fewer customers come back | Arrives within the hour | Arrives within the hour |
| Profit check (P1) | New offers wait until night | Works | Works |
| Churn and segments | Fine | Works, but costs more for no gain | Fine |

## Decision

C. The question for each part: if it's a day late, what breaks?

| Part | Mode | Why |
|---|---|---|
| Message count (P3) | Real-time | If it's late, a customer gets more than the limit |
| Abandoned-cart reminder | Real-time, after an hour without activity | The customer still remembers the cart; it reuses the events already needed for the message count |
| Profit check (P1) | Real-time, when an offer is created | Offers shouldn't wait, and prices may have just changed |
| Churn model | Batch, nightly | Customers drift away over weeks; a day changes nothing |
| Customer segments | Batch, nightly | Interests change slowly; segments are ready for the next day's offers |

Rule of thumb: a part doesn't need to be fresher than the part that reads it.

## Consequences

- We need an event stream from the site (cart, purchases, messages sent) for the real-time parts, plus a nightly job for the rest.
- Two ways of running things to look after instead of one.

## Revisit if

- Churn or segments turn out to change within hours (for example during flash sales), or
- the reminder sent within the hour doesn't bring back more carts than a next-day one.
