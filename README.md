# AI Architecture Portfolio

Ahmad Saleh · [AI Architecture Design](https://academy.mlopsmena.com/en/courses/ai-architecture-design), MLOps MENA, Oct–Dec 2026

My work for the course. The session notes and assignments use the course's example system, ShopCo. My capstone is a different system, Hesal, in [capstone/](capstone/).

## Scenario

ShopCo is an online store whose marketing is all done by hand: fixed offers on the home page, discounts added manually, campaigns sent from the admin panel. Everyone sees the same offers.

What goes wrong today:
- Offers are the same for every customer, and often miss their own target (sales, clearing stock, or traffic).
- Some offers lose money on products with a small margin.
- Customers fill the cart and leave, or stay a long time on a product page and leave.
- Too many emails and pop-ups, which customers ignore or close.
- New customers buy once and don't come back.

The target adds AI around the existing systems: customer segments, product recommendations, next-best action for abandoned carts and customers likely to leave, and campaigns prepared by agents. An admin still approves anything risky.

Who uses it: the marketing team and store admin (offers, campaigns, approvals) and customers (see offers and recommendations on the site, by email and in the app).

Goals, principles and decisions: [docs/01-governance-pack.md](docs/01-governance-pack.md).

## Assumptions

| What | Value | Source |
|---|---|---|
| Concurrent users | 50 normally, 100 at peaks (Ramadan, holidays) | class example, last 6 months |
| Products | 80 | my estimate |
| Sales per month | 100 | my estimate |
| Customer satisfaction (ratings) | 60% | class example |
| New customers who buy again | 4% (about 2 of 50) | my estimate |
| Data | stays in the country, in transit and at rest; personal data under PDPL | class example |
| Internal systems | behind a VPN; anything external uses authentication and HTTPS | class example |

## How to read this repo

```
README.md   ShopCo scenario, assumptions, how to read the repo
docs/       one file per session: 01-framing.md, 02-building-blocks.md, ...
diagrams/   exported PNG/SVG; draw.io sources in diagrams/src/
adr/        ShopCo decisions, one per file
capstone/   Hesal, my capstone (its own README, docs, diagrams, adr)
```

## Progress

| Session | Notes | Assignment | Capstone |
|---|---|---|---|
| 1 – Framing (18 Oct) | [notes](docs/01-framing.md) | [governance pack](docs/01-governance-pack.md) (due 28 Oct) | [Hesal framing](capstone/docs/01-framing.md) |
| 2 – AI building blocks (25 Oct) | | | |
| 3 – LLM & RAG (1 Nov) | | | |
| Capstone part 1 (14 Nov) | | | |
| 4 – Agents (15 Nov) | | | |
| 5 – Security, governance, evals (22 Nov) | | | |
| 6 – Case studies (29 Nov) | | | |
| Final capstone (13 Dec) | | | |
