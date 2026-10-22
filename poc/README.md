# Proof of concept

A small working version of the scheduling part of the planning assistant. It is not the product,
it's there to check that the main architecture decision holds: the solver builds the plan and
code checks it ([ADR 0002](../adr/0002-solver-not-llm-for-scheduling.md)). No LLM in here yet.

All data is made up. The coffee roastery numbers come from talking to a real roastery, but the
name and orders are invented.

## What's here

```
engine/
  core/          scheduling core: greedy solver, CP-SAT solver, checker, replanning
  adapters/      factory -> core (orders, recipes, batches)
  model.py       factory model: recipes, losses, batching, stages
  configs/       two example factories: a coffee roastery and a beverage plant
  samples/       example orders and a two-week factory log (Excel)
  plan.py        plan one set of orders and check it
  backtest.py    replay a factory log day by day: what the factory did vs. the engine
  tests/
data/
  generator.py   synthetic data for 10 beverage plants (with data-quality problems on purpose)
  validate.py    data checks + baseline numbers
```

## Run it

Needs [uv](https://docs.astral.sh/uv/). From this folder:

```bash
uv sync
uv run python -m unittest discover engine/tests
uv run python engine/plan.py engine/configs/coffee_roastery.yaml engine/samples/coffee_orders.csv --start 2026-10-18T08:00 --solver cpsat
uv run python engine/backtest.py engine/samples/factory_log_example.xlsx
uv run python data/generator.py && uv run python data/validate.py
```

## What it shows so far

On the example log (two weeks, made up), replanning every morning with only the orders known
that day:

| | Factory as it works today | Engine |
|---|---|---|
| Orders on time | 14 | 26 |
| Orders late | 12 | 3 |
| Average roast batch (kg, max 14) | 10.4 | 12.0 |

Every plan passes the checker. These numbers only show the idea works; real numbers need a real log.
