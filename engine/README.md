# Scheduling engine: one core, many domains

The engine does not know about coffee, patients, lessons or buses. A small **core** schedules
*tasks* on *resources* for *jobs*; a thin **adapter** per domain translates the domain's own world into
that vocabulary. The same solvers and the same independent checker run a roastery, a beverage plant,
an outpatient clinic, a school timetable and an Umrah ground operator.

```bash
uv sync                                          # once, from the repo root (pyproject.toml + uv.lock)
uv run python -m unittest discover engine/tests  # 23 tests: parity, checker, 5 domains (~15 s)

# factories
uv run python engine/plan.py engine/configs/coffee_roastery.yaml engine/samples/coffee_orders.csv \
    --start 2026-10-18T08:00 --solver cpsat      # or rules; prints the plan, KPIs, check result
uv run python engine/backtest.py engine/samples/factory_log_example.xlsx       # factory vs engine, day by day
uv run python engine/import_excel.py engine/samples/factory_log_example.xlsx   # read the factory log + calibration
uv run python engine/config_check.py             # validates the factory configs

# other domains: plan -> offer / disruption -> repair
uv run python engine/demos/clinic_day.py         # book a week, offer 3 slots on WhatsApp, doctor goes home sick
uv run python engine/demos/school_week.py        # weekly timetable, teacher absent on Tuesday
uv run python engine/demos/umrah_week.py         # pilgrim groups, buses, guides, a flight lands 5 h late
```

## Core + adapters

```
engine/
  core/                         knows nothing about any domain
    model.py      Resource · Requirement · Task · Job · Problem, setups, calendar helpers
    calendar.py   weekly calendars -> working windows
    greedy.py     fast list scheduler (any size), also the warm start and the fallback
    cpsat.py      OR-Tools CP-SAT: circuits for setups, NoOverlap / Cumulative, lexicographic objectives
    modes.py      plan · offer (k best options for a new request) · repair (replan, keep the old plan)
    check.py      independent release gate
    kpi.py        job-level KPIs, the same for every domain
  adapters/
    factory.py    orders -> recipe -> batches -> tasks   (domain logic stays in model.py)
    services.py   service catalogue in YAML: clinics, schools, travel, any "book people + rooms + equipment"
    school.py     weekly course load -> lesson requests
    travel.py     pilgrim groups + flights -> itinerary requests
```

| Core idea | Roastery | Clinic | School | Umrah operator |
|---|---|---|---|---|
| **Resource** (calendar + capacity) | roaster, grinder, packer | doctor, room, x-ray, nurses ×2 | teacher, room, **class group** | bus, drivers ×2, guide, group, site (×2 / ×1) |
| **Task needs several resources at once** | roaster + operator | room + doctor (+ nurse) | room + teacher + group | vehicle + driver + guide + site + group |
| **Skills / filters** | eligible line per format | `skill: cardio`, requested doctor | room kind + seats ≥ group size | seats ≥ group size, guide speaks `$lang` |
| **Sequence-dependent setup** | cardamom → plain: 30 min | infectious → anyone: 30 min cleaning | | 20 min bus turnaround between groups |
| **Lags** | rest ≥ 60 min | x-ray → consult ≤ 2 h | | tour ≥ 12 h after arrival |
| **Hard limits** | working hours | doctor's days | periods only | land + 4 h, airport 3 h before the flight, prayer closures |
| **Optional job (may be refused)** | | routine booking | (flagged if unplaceable) | group the fleet cannot serve |
| **Soft preference** | | patient's preferred time | spread each course over the week | tour in the morning |
| **Repair** | breakdown, rush order | doctor goes home sick, emergency | teacher absent | flight +5 h |

## Results of the demos (fictional data)

| Domain | Greedy | CP-SAT | Repair after the disruption |
|---|---|---|---|
| Roastery (10 orders) | 1 late, 60 min cleaning | 1 late, **30 min** cleaning | backtest: 26 vs 14 on time (see below) |
| Clinic (12 requests) | all booked, far from preferences | all booked, **0 min** from preferred times, infectious patient last (10 min cleaning, not 30) | sick doctor + emergency: emergency treated at 09:00, **4 appointments moved**, the rest untouched; a patient who asked for Dr Hana stays with Dr Hana (next day) |
| School (80 lessons/week) | 58 / 80 placed | **80 / 80** placed, courses spread over the week | teacher absent: **only her 4 lessons move** |
| Umrah (4 groups) | 2 / 4 served | **4 / 4** served | flight +5 h: 2–3 activities shift, check passes |

Greedy is instant and good for bookings one at a time; CP-SAT is what makes tight timetables feasible.
Every result above passes the same checker.

## Factory details

The factory configs are the first domain; their results are unchanged by the rewrite
(`tests/test_core.py::TestFactoryParity`). The old factory-only solvers are kept in `legacy/`.

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
| `core/greedy.py`, `core/cpsat.py`, `core/check.py` | The solvers and checker (were `solve_rules.py`, `solve_cpsat.py`, `check_schedule.py`, now in `legacy/`) |
| `adapters/factory.py` | Maps the factory model onto the core; adds batch size, no-mixing and coverage checks |
| `plan.py` | CLI: build → solve → check → KPIs (exit 1 if any violation) |
| `import_excel.py` | Reads the factory's daily log (Arabic Excel): orders → engine orders, batches → calibration of time and loss, events → downtime. Reports every unreadable row |
| `backtest.py` | Replays the log day by day: every morning the engine sees only the orders received so far and today's breakdowns, plans, executes today, replans tomorrow. Compares with what the factory did |
| `samples/` | Synthetic orders for both factories |

## First results (sample orders, 72 h)

| Factory | Solver | Late orders | Late qty, top priority | Weighted tardiness | Setup min | Check |
|---|---|---|---|---|---|---|
| Coffee (10 orders, 24 roast batches) | rules (due day, then priority) | 1 | 0 | 17.2 h | 60 | PASS |
| Coffee | CP-SAT (7 s) | 1 (toll roasting, lowest priority) | 0 | 17.2 h | **30** | PASS |
| Beverage (8 orders, 18 syrup batches) | rules | 0 | 0 | 0 | 470 | PASS |
| Beverage | CP-SAT (1 s) | 0 | 0 | 0 | **320** | PASS |

The coffee sample needs about 57 h of roasting before its due dates, but the roaster has about 44 h, so one
order must be late. CP-SAT chooses the toll-roasting order, which matches the owner's rule (own brands first),
and grinds the two plain (no-cardamom) orders back to back, so the grinder is cleaned once instead of twice. With pure "priority first" the rules plan had 3 late orders (83.6 h); ordering by due day, then priority, fixed
that, because pure priority starves low-priority orders. The rule-based plan is the
fallback and the warm start.

## Backtest on the example log (invented data, real parameters)

`samples/factory_log_example.xlsx` is two invented weeks (3–15 Oct) built with the roastery's real recipes,
batch sizes, times, losses and shifts. The "factory" side was simulated the way they work today: first come
first served, shops first in a crunch, each order roasted in its own batches, plus a one-day drum-roller breakdown.

| | Factory (log) | Engine, rules | Engine, CP-SAT |
|---|---|---|---|
| On time | 14 | 26 | 26 |
| Late, delivered | 12 | 3 | 3 |
| Open and past due at the end | 4 | 1 | 1 |
| Avg roast batch (kg green, max 14) | 10.4 | 12.0 | 12.1 |
| Roaster busy (h) | 158 | 175 | 176 |

What it shows: pooling the same origin across orders fills the drum (10.4 → 12 kg per batch), so the same
roaster serves more orders. Shops go from 5 late to 0. What it also shows: the engine plans just in time, so it
finished the export order later than the factory did, and the unannounced breakdown then pushed it past its due
date. A safety buffer before due dates is a parameter to add. These numbers prove the mechanism only; the saving
must be measured on the real log.

## Known limits (v1)

- Batches are formed before solving. The solver orders them but does not re-cut them.
- With alternative people pools (`people: [packer, roaster_operator]`) the first pool is used.
- `plan_changes` (stability against the previous plan) is skipped until there is a previous plan to compare.
- `during: start/end` keeps a person busy for 15 minutes.
- The rule-based solver does not look ahead, so it can break a max lag; the checker reports it.

## Next steps

- [x] `model.py`, `solve_rules.py`, `solve_cpsat.py`, `check_schedule.py`, `plan.py`
- [x] Domain-agnostic core; clinic, school and travel adapters; offer and repair modes
- [x] Replan after a disruption with a frozen horizon and a stability objective (`core/modes.py`)
- [x] Excel import + day-by-day backtest (`import_excel.py`, `backtest.py`)
- [ ] Run the backtest on the factory's real two weeks
- [ ] Safety buffer before due dates; use roasted stock left over from padding
- [ ] LLM explainer: turn KPIs, the binding constraints and the late orders into an Arabic explanation
