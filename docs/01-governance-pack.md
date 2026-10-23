# Governance pack – ShopCo marketing automation

Session 1 mini project.

## Context

ShopCo is an online store whose marketing is done by hand: the same offers for everyone, discounts added manually, campaigns sent from the admin panel. The target system adds AI that suggests offers, recommends products and prepares campaigns. This page sets the rules that system has to follow. Scenario: [README](../README.md).

## Business goals

Measured from launch. Starting numbers are estimates, to be measured just before launch.

| # | Goal | From | To | Within |
|---|---|---|---|---|
| G1 | Customer satisfaction from product ratings | 60% | 80% | 3 months |
| G2 | Sales per month | 100 | 300 | 6 months |
| G3 | New customers who buy again | 4% | 10% | 3 months |
| G4 | Products sold at a loss in offers | 5 of 80 | 0 | 3 months |

- G2 is a stretch goal: offers that fit each customer instead of one offer for everyone.
- G4 can be zero because it's our decision, not customer behaviour.
- Non-goals: fewer returns; faster delivery (outside what a marketing system controls).

## Architecture principles

The AI suggests. Code and people decide.

| # | Principle | Goal | In practice |
|---|---|---|---|
| P1 | **Every offer is checked for profit before it goes live.** Profitable offers go out automatically; offers that lose money go to an admin. | G4 | The AI suggests products, customer group, discount type and size. Code reads cost and selling price and works out the profit per product. Losing offers wait for an admin to approve or reject. |
| P2 | **Every prediction or advice from the AI is based on store data and shows the numbers behind it.** If there isn't enough data, it says so instead of guessing. | G2 | The admin describes an offer idea. The AI reads visits, purchases, clicks, time on page, items removed from the cart (and why, when the customer says), ratings by type (delivery, price, quality), profit and stock, and answers with the numbers it used. The admin decides. |
| P3 | **Every customer has a monthly limit on messages across all channels.** Code blocks anything above it, even if the AI suggested it. | G3 | Limit: 2 messages a month. Code counts what each customer received and stops the rest. |
| P4 | **Recommendations start from what the customer is interested in,** then discount and stock. Any text or image the AI writes must match the real product. | G1 | The AI doesn't push a product to everyone because it's discounted or overstocked. Offer text is checked against the product's own photo and description before it goes out. |

## ADRs

| ADR | Decision | Principle |
|---|---|---|
| [0002 – Where the LLM runs](../adr/0002-llm-hosting.md) | LLM API hosted in the country | data stays in the country (PDPL) |
| [0003 – Real-time or batch](../adr/0003-real-time-vs-batch.md) | Real-time only for the message count, cart reminders and the profit check; churn and segments nightly | P1, P3 |
| [0004 – Where we store vectors](../adr/0004-vector-store.md) | pgvector in our existing PostgreSQL | P4, data stays in the country |

## ARB checklist

Every change to the system (a new campaign type, a new model, a new feature) goes through these questions before release. Any "no" means it doesn't ship until it's fixed.

**Security**
- [ ] Does the AI only reach the data this task needs, through our own API and never straight into the database?
- [ ] Is text from customers and suppliers (reviews, product descriptions) treated as data, never as instructions to the AI?
- [ ] Are internal services behind the VPN, and anything external on authentication and HTTPS?

**Privacy (PDPL)**
- [ ] Does all customer data stay in the country, including what's sent to the LLM and the vectors? (ADR 0002, 0004)
- [ ] Is personal data used only for marketing the customer agreed to, and can they opt out?
- [ ] Can a customer's data be deleted on request, vectors included?

**Evals**
- [ ] Is there a test set and a pass mark, agreed before launch?
- [ ] Does AI-written offer text match the real product's photo and description? (P4)
- [ ] Is there a before/after or A/B test against the goal this change serves (G1–G4)?

**Cost**
- [ ] Is there a monthly spending cap on the LLM API, with an alert before it's reached?
- [ ] Is the cost per offer or message estimated, and lower than what it's expected to bring in?
- [ ] Does it use real-time only where a delay breaks something? (ADR 0003)

**Human oversight**
- [ ] Do offers that lose money go to an admin before they go live? (P1)
- [ ] Is the monthly message limit enforced in code, whatever the AI suggests? (P3)
- [ ] Does AI advice to admins show the numbers it's based on? (P2)
- [ ] Can an admin pause a campaign, or the AI as a whole, with one switch?

## Automated guardrail

A CI check runs on every push and pull request ([workflow](../.github/workflows/guardrail.yml), [script](../checks/check_principles.py)). It reads the system settings in [config/shopco.json](../config/shopco.json) and fails the build if:

- the profit check is off, or losing offers don't go to an admin (P1)
- the message limit is above 2 a month, or isn't enforced in code (P3)
- the LLM or the vectors are outside the country (ADR 0002, 0004)
- an ADR is missing its options, decision or revisit condition

So a change that breaks a principle can't be merged without someone noticing.

## Diagram

[![Governance](../diagrams/governance.png)](../diagrams/governance.png)

[Open in draw.io](https://app.diagrams.net/#Uhttps%3A%2F%2Fraw.githubusercontent.com%2FAhmadSaleh22%2Fai-architecture-portfolio%2Fmain%2Fdiagrams%2Fsrc%2Fgovernance.drawio) · Source file: [governance.drawio](../diagrams/src/governance.drawio) · First sketch: [governance-sketch.png](../diagrams/src/governance-sketch.png)
