# 0002. The solver builds the schedule, not the LLM

Status: accepted
Date: 2026-10-18

## Context

After a disruption (machine breakdown, late material, rush order) the planner
needs a new plan for the next 1–3 days. The plan must respect hard rules:
machine capacity, working hours, changeover times, due dates.
A plan that breaks one rule is useless on the floor.

## Options

1. **LLM writes the schedule directly.** Simple to build. But in published tests
   (SCHEDBench) only about 15% of LLM schedules were feasible.
2. **Optimization solver (OR-Tools CP-SAT) builds it, LLM explains it.**
   Feasible by construction, and a code checker can verify every plan.
   More work to model the factory rules.
3. **LLM writes the solver model from the rules, solver runs it.**
   Flexible, but hard to test and debug in production.

## Decision

Option 2. The solver proposes, code checks, the LLM explains, the planner decides.
No plan reaches the planner if the checker finds a single violation.

## Consequences

- Plans are always valid, and every rule the LLM mentions can be traced to the config.
- Factory rules have to be written down (config file per plant). That's extra work,
  but it's work the plants need anyway.
- If the LLM is down, planners still get correct plans, just without explanations.
- Revisit if: LLM feasibility on our test scenarios goes above 95%, or a plant
  has rules we can't express in the solver.
