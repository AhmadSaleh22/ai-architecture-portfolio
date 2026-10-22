# Hesal – AI architecture capstone

My capstone for the [AI Architecture Design](https://academy.mlopsmena.com/en/courses/ai-architecture-design) course (MLOps MENA, Oct–Dec 2026).

> Hesal is a fictional company. Any similarity to a real product is a coincidence.

## Scenario

Hesal is a platform that companies use to pay salaries and look after their employees' money. Every month part of each salary goes into savings, at a rate the employee sets and can change at any time. Once their savings reach a set level, employees can apply for an interest-free loan (qard hasan) or get something on a lease-to-own plan (ijara muntahia bittamlik: Hesal buys it, and ownership passes to the employee after the last instalment). HR, finance and the CEO manage employees and company finances from the same platform.

Hesal also has a services page: insurance, instalment plans, cars and similar, from partner companies. The employer decides which services its employees can use, and the employee's contract type can limit it further. Partners all pay the same fee. There are no paid placements.

## The problem

Most employees have no savings. The salary comes in, it gets spent, and when something comes up they turn to the company: an advance on salary, a raise, or asking the company to buy something for them.

For the company this means a steady stream of advance requests, HR and finance time spent handling them, and pressure on cash.

## Goals

- 90% of employees still saving after 6 months
- Default savings rate of 10% of salary
- One month of expenses saved after 12 months
- Advance requests down by half within 6 months

Details and sources in [docs/01-framing.md](docs/01-framing.md).

## Where it runs

KSA first. Each country gets its own copy, and an employee's data stays in their company's country. Savings sit in an account in the employee's name at a partner bank, not with Hesal.

## What AI adds

- **Monthly money plan.** The employee can upload last month's bank statement. The assistant suggests a plan and shows what saving X% for N months adds up to. The numbers are calculated in code; the LLM explains them.
- **Money questions.** Monthly, quarterly and yearly plans, spending worth cutting, services they need, and ways to invest in themselves and their family (courses, education, health). Answers come from the employee's own numbers and from Hesal's documents: qard hasan and lease-to-own terms, their company's policy, and the details of each service.
- **Services that fit.** Services are suggested by what matters to the employee (interests, family situation, with their consent), and only those they are allowed to use and can afford.
- **Applying for a service (agent).** The agent checks eligibility, prepares the application and shows it to the employee. Once the employee confirms, it goes to their company for approval, then to the Hesal team, who submit it to the partner.

## Users

| Who | Uses Hesal to |
|---|---|
| Employee | Save, apply for loans, lease-to-own and services, plan their money |
| HR | Manage employees, approve requests |
| Finance | Salaries, company finances, approve requests |
| CEO | See the overall picture, approve requests |
| Hesal team | Add services, submit applications to partners |
| Partner companies | Receive applications the employee chose to send |
| Shariah board | Approve the terms of qard hasan and lease-to-own |

## Fixed rules

- Employee data stays with Hesal. Employers and partners only see totals, never an employee's spending or their chats with the assistant.
- A partner only gets an employee's details when the employee applies, and only what the application needs.
- The assistant only sees the data of the employee who is signed in. It has no way to read anyone else's salary or savings.
- Eligibility for loans, lease-to-own and services is decided by rules in code. The LLM explains, it doesn't decide.
- The agent can't withdraw savings and can't send anything without the employee confirming. It has no tools for either.
- Every application needs written approval from the company (CEO, HR or finance, depending on the request).
- Sharing a bank statement is the employee's choice. Statements are stored encrypted for one year, then deleted. Totals per category are kept: food, transport, instalments, purchases, university, health insurance, tax.
- No crypto, stocks or specific financial products. The assistant doesn't give religious rulings.

## Biggest risks

1. A bank statement with hidden text that gives the assistant instructions.
2. An employee tricking the assistant into revealing a colleague's salary or savings.
3. A wrong number in a money plan that the employee acts on.
4. A suggestion to put savings into crypto or an unsuitable investment.

## Assumptions

Assumed until there's a source.

| What | Value | Source |
|---|---|---|
| Employees with no savings | most | to find (public source) |
| Advance requests per 100 employees per month | ? | assumed |
| Companies on the platform / employees per company | ? | assumed |
| Employees who upload a statement each month | ? | assumed |
| Peak load | salary day, Ramadan, back to school | assumed |

## Out of scope (v1)

- A self-service portal for partners (the Hesal team adds services by hand)
- A Hesal payment card
- Direct bank connections (open banking)
- Investment products

## Open questions

- Does submitting insurance or financing applications for employees make Hesal a broker that needs a licence?
- Can stored statements be used to improve the model? If yes, it needs a separate consent from the employee.

## How to read this repo

```
docs/       one file per session: 01-framing.md, 02-building-blocks.md, ...
diagrams/   exported images; editable sources in diagrams/src/
adr/        architecture decisions, one per file
capstone/   the final submission
```

Start with `docs/01-framing.md`, then the diagrams, then `adr/`.

## Progress

- [x] Session 1 – Framing (18 Oct) · [notes](docs/01-framing.md)
- [ ] Session 2 – AI building blocks (25 Oct)
- [ ] Session 3 – LLM & RAG (1 Nov)
- [ ] Capstone part 1 (14 Nov)
- [ ] Session 4 – Agents (15 Nov)
- [ ] Session 5 – Security, governance, evals (22 Nov)
- [ ] Session 6 – Case studies (29 Nov)
- [ ] Final capstone (13 Dec)
