# Scheduling engine: one config format for many factories

The engine is not written for coffee or for beverages. A factory is described in a **config file**; the
same model builder, solver and checker run on any config. This folder holds step 1: the config format,
two filled examples, and a checker.

```bash
uv sync                                          # once, from the repo root (pyproject.toml + uv.lock)
uv run python engine/config_check.py             # checks every file in configs/, exits 1 on errors
uv run python engine/plan.py engine/configs/coffee_roastery.yaml engine/samples/coffee_orders.csv \
    --start 2026-10-18T08:00 --solver rules      # or --solver cpsat; prints the plan, KPIs, check result
uv run python -m unittest discover engine/tests  # model + checker tests
```

| Config | Industry | Shape of the problem |
|---|---|---|
| [`configs/coffee_roastery.yaml`](configs/coffee_roastery.yaml) | Coffee roasting | Hybrid flow shop with batching, customer-owned material that must not mix, asymmetric grinder cleaning, operator always present, shelf life by season |
| [`configs/nahda_riyadh.yaml`](configs/nahda_riyadh.yaml) | Beverage bottling | Syrup batching + parallel filling lines (`Rm \| r_j, s_jk, M_j \| Σ w_j T_j`), CIP changeovers, QA release, max hold time |

The coffee config is calibrated from interviews with a real roastery, but the name is fictional and no
customer, order or price list is stored. The beverage config matches [`../data/generator.py`](../data/generator.py).

## Pipeline

```
config.yaml ──► config_check ──► model builder ──► solver ──► constraint checker ──► LLM explainer
                (this folder)     (next)           rule-based     (code, not LLM)      (AR/EN, cites
                                                   or CP-SAT                            the violated or
                                                                                        binding rule)
```

## How config fields map to the formulation

Sets: orders `o`, products `p`, materials `m`, batches `b`, resources `r`, stages `s`, people pools `h`.
Decisions: `x(o,b)` quantity of order `o` in batch `b`, `z(b,r)` batch `b` runs on `r`, start time `S_b`.

| # | Constraint | Config field | Coffee | Beverage |
|---|---|---|---|---|
| ① | Every order is covered, through recipe and loss | `products.*.recipe`, `additives`, `yield_loss`, `stage_conversion` | 25 kg of blend 190 → 15 kg roasted Brazil + 8 kg robusta + 2 kg cardamom → 16.7 + 8.9 kg green | 30,000 × 500 ml → 15,000 L syrup |
| ② | Batch size between min and max | `resources.*.capacity` | 8–14 kg green | 5,000–20,000 L |
| ③ | Only compatible items share a batch / resource | `stages.*.batch_key`, `compatibility`, `resources.*.eligible` | one origin per batch; never mix owners | one flavour per syrup batch; PET only on PET line |
| ④ | One job at a time per resource, plus sequence-dependent setup | `resources.*.duration` (α + β·w), `setups` | grinder: cardamom → plain = 30 min, reverse = 0 | cola/energy → other = 90 min CIP, size change +40 |
| ⑤ | People used ≤ people available | `people`, `resources.*.needs` | roaster needs an operator the whole run | QA tech at end of syrup batch |
| ⑥ | Min / max time between stages | `stages.*.after` | rest ≥ 60 min before grinding | QA ≥ 30 min, fill within 24 h |
| ⑦ | Work only inside calendars; breakdowns remove time | `calendars`, `failure_modes` | 08:00–02:00; drum motor = 4 days | 24/5; filler valve 2 h |
| ⑧ | Consumables tracked; alert before running out | `consumables`, `resources.*.consumes` | gas: 250 kg (180 dark) per cylinder | CO₂ per unit |
| ⑨ | Stock older than shelf life is not used | `shelf_life_days`, `seasons` | winter 14–30 d, summer 7 d | not binding |

**Objective** (`objective`): lexicographic. Optimise the first KPI, then the next one without making the
first worse. Both factories use the same list: late quantity of top-priority orders → weighted tardiness
(`order_classes.*.weight`) → plan changes outside the frozen horizon → batches → setup minutes.

## What the checker guarantees (before any solver runs)

- Every reference resolves: calendars, people pools, consumables, materials, attributes, stages.
- Recipe shares add up to 1, or parts add up to the basis (grams per 250 g bag). A `balance` item fills the bag (the roastery tops up with cardamom), and variants such as `no_cardamom` are expanded and printed; batch min ≤ max; max lag ≥ min lag.
- Every product route follows stage order and has an eligible resource at each stage.
- Every objective KPI is known; a priority filter points to a real order class.
- Values marked `ASSUMPTION` are counted, so the open questions for the factory stay visible.

It also prints nominal weekly capacity per resource. Roaster: 105 h/week → about 588 kg green, which matches
the capacity table from the interview (the roaster is the bottleneck, grinder and packing are not).

## Adding a new factory

1. Copy the closest config. 2. Fill attributes first: they decide batching, setups and compatibility.
3. Mark unknown numbers `# ASSUMPTION`. 4. Run the checker until it is clean.
If a factory needs a constraint that no field can express, that is a schema change: add the field, a checker
rule, and a negative test, and record it in an ADR.

## Files

| File | Job |
|---|---|
| `config_check.py` | Validates a factory config before anything else runs |
| `model.py` | Config + orders CSV → tasks. Batching stages: loads grouped by `batch_key`, cut into full batches (last two shared equally if the last is under the minimum). Other stages: one task per order. Calendars → working windows |
| `solve_rules.py` | Greedy list scheduler: priority, then due date; each order pulls its chain; earliest feasible start on the best resource |
| `solve_cpsat.py` | OR-Tools CP-SAT: optional intervals, `AddCircuit` for sequence-dependent setups, cumulative people, window choice, lexicographic objective, warm-started from the rules plan |
| `check_schedule.py` | Independent release gate: eligibility, durations, calendars, overlaps + setups, people, lags, batch size, no mixed owners, demand covered |
| `plan.py` | CLI: build → solve → check → KPIs (exit 1 if any violation) |
| `samples/` | Synthetic orders for both factories |

## First results (sample orders, 72 h)

| Factory | Solver | Late orders | Late qty, top priority | Weighted tardiness | Setup min | Check |
|---|---|---|---|---|---|---|
| Coffee (10 orders, 24 roast batches) | rules | 3 | 0 | 83.6 h | 60 | PASS |
| Coffee | CP-SAT (8 s) | **1** (toll roasting, lowest priority) | 0 | **17.2 h** | **30** | PASS |
| Beverage (8 orders, 18 syrup batches) | rules | 0 | 0 | 0 | 470 | PASS |
| Beverage | CP-SAT (1 s) | 0 | 0 | 0 | **320** | PASS |

The coffee sample needs about 57 h of roasting before its due dates, but the roaster has about 44 h, so one
order must be late. CP-SAT chooses the toll-roasting order, which matches the owner's rule (own brands first),
and grinds the two plain (no-cardamom) orders back to back, so the grinder is cleaned once instead of twice. The rule-based plan is still useful: it is the
fallback and the warm start.

## Known limits (v1)

- Batches are formed before solving. The solver orders them but does not re-cut them.
- With alternative people pools (`people: [packer, roaster_operator]`) the first pool is used.
- `plan_changes` (stability against the previous plan) is skipped until there is a previous plan to compare.
- `during: start/end` keeps a person busy for 15 minutes.
- The rule-based solver does not look ahead, so it can break a max lag; the checker reports it.

## Next steps

- [x] `model.py`, `solve_rules.py`, `solve_cpsat.py`, `check_schedule.py`, `plan.py`
- [ ] Replan after a disruption (breakdown, rush order) with a frozen horizon and a stability objective
- [ ] Feed the factory's real orders log (two weeks) and compare with what they actually did
- [ ] LLM explainer: turn KPIs, the binding constraints and the late orders into an Arabic explanation
