# Synthetic factory data

All data is **invented** for a fictional manufacturer, *Nahda Beverages*. No real plant, customer or employer data belongs in this repo.

```bash
cd data
python3 generator.py                          # 3 plants, 28 days, about 1 second
python3 generator.py --plants 10 --days 90    # full scale
python3 validate.py                           # data contracts + baseline KPIs (exits 1 on blocking issues)
```

Python 3.9+, standard library only. Output goes to `generated/` (git-ignored, so regenerate it from the seed).

## What's generated

| Folder | Files | Notes |
|---|---|---|
| `master/` | plants, lines, machines, products, changeover_matrix, materials, bom, shift_calendar | Saudi/Egyptian/UAE weekends and national holidays; 2- and 3-shift plants |
| `transactional/` | work_orders, baseline_schedule, material_deliveries, maintenance_plan | Schedule built with changeovers and planned efficiency; rush orders left unscheduled |
| `telemetry/` | machine_events, production_counts | Execution simulated with machine reliability (MTBF) and long-tail repair times |
| `unstructured/` | docs/ (planning rules, SOP, escalation matrix in AR/EN), shift_notes.jsonl | Notes are messy: Arabic, English, Franco-Arabic, names (PII), occasional wrong info |
| `labels/` | disruptions, planner_decisions, eval_scenarios | Ground truth for evaluating the copilot |
| `MANIFEST.json` | row counts + **injected data-quality issues** | Your pipeline should catch every one of them |

## Deliberately injected problems

- Missing or "OTHER" downtime reason codes (~8%)
- One line's PLC clock is 7 minutes ahead
- Duplicated events from gateway retries
- A schedule row pointing to a non-existent work order
- A negative scrap count (counter reset)

`validate.py` detects all five. When you add a new contract, add a matching injected issue so you know it works.

## Ideas to extend

- Add a second industry line type (e.g. dairy with shelf-life constraints)
- Make repair time depend on shift (night shift has fewer technicians)
- Simulate the *effect* of a planner decision so eval can compare copilot vs. human outcomes
