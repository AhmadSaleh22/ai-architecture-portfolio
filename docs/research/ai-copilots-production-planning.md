# Research: AI Copilots for Production Planning

Ahmad Saleh · 16 Oct 2026 · Living version (with diagram and comments): https://claude.ai/code/artifact/6e4253ca-da5f-42be-a498-e01fa6cc3a81

## Summary

The Production Planning Copilot should let a solver propose, code verify and the LLM explain; buy the commodity layers and build the copilot; and stay one-way from OT. This research backs the capstone for *Nahda Beverages* (fictional, synthetic data).

| Question | Answer | Main evidence |
| --- | --- | --- |
| Can an LLM produce the schedule? | No. Use it to gather context, explain and answer; a solver proposes and code checks | Frontier models average 15% feasibility on scheduling benchmarks |
| Build or buy? | Hybrid: keep APS/MES, build the copilot layer | Vendor copilots focus on engineering inside one ecosystem |
| Re-plan fully or repair? | Repair by default; show full re-plan with its stability cost | Full re-plans cut tardiness ~50% but churn the plan |
| How do we know it works? | Gates: 0 violations, beat the human reference, stability budget, shadow mode first | Explanations raise adoption more than understanding |
| How does it touch the plant? | Read from the DMZ, one-way; only write is an approved draft to APS | IEC 62443 conduits; Saudi NCA OTCC |
| Where does the model run? | Redact names; in-region or self-hosted per plant | Saudi and Egyptian transfer rules |

## 1. LLMs and optimization for scheduling

The evidence says LLMs should not produce schedules on their own: they should frame, explain and gather context, while a solver or heuristic produces options and code verifies them.

**What the research shows**

- **LLMs solving scheduling directly fail on feasibility.** [SCHEDBench](https://arxiv.org/pdf/2608.00991) (Aug 2026) tested 13 frontier and open models zero-shot on 1,132 scheduling instances. The best model produced feasible schedules 55.9% of the time under rewording; the cross-model average was 15.2%, and hard tiers were near 0%. Reordering the constraints alone changed violation rates.
- **When they are feasible, the tail is dangerous.** For the best model, the median optimality gap was 4.3% but the mean was 747%: a few very bad schedules dominate. A planner can't tell which output is the bad one without a checker.
- **Fine-tuning helps, but still needs a verifier.** [Starjob](https://arxiv.org/html/2503.01877v2) fine-tuned Llama 3.1 8B on ~130k job-shop instances. With 20 samples per instance and a feasibility filter, it reached a 21.7% gap on Taillard benchmarks vs 46.8% for the best dispatching rule. The largest instance took ~217 s per sample, and the infeasible rate is not reported.
- **LLM as modeler works better than LLM as solver.** In a [real production-scheduling case](https://arxiv.org/pdf/2309.13218) (an embroidery producer, flexible job shop), a fine-tuned code model translated natural-language descriptions into constraint-programming models that OR-Tools solved. Formulation success was above 95%, but the paper reports no business KPI improvement and used synthetic orders.

**Four integration patterns**

| Pattern | LLM's job | Who guarantees feasibility | Evidence | Fit for the copilot |
| --- | --- | --- | --- | --- |
| A. LLM writes the schedule | Everything | Nobody | SCHEDBench: 15% avg feasible | Reject |
| B. LLM samples + verifier filters | Generate candidates | External checker | Starjob: 21.7% gap, slow, GPU-heavy | Research only |
| C. LLM writes the optimization model | Translate rules into constraints | Solver + model validation | Embroidery case: >95% formulation success | Later: what-if questions with new constraints |
| D. Solver proposes, LLM explains | Context, explanation, Q&A, notes | Solver + constraint checker in code | Follows from A–C | **v1 choice** |

**Failure modes to design for**

- Silent constraint violations that look plausible (frozen horizon, maintenance window, format mismatch).
- Sensitivity to how the problem is written: same plant state, different wording, different answer.
- Explanations that cite rules not in the planning rules, or numbers not in the data.
- Long-tail bad proposals that average metrics hide; report worst-case and percentiles, not means.

## 2. Market landscape and build vs buy

In the material reviewed, vendor GenAI copilots target engineering (PLC code) and operator guidance inside one vendor's ecosystem; none covered explainable disruption re-planning across a mixed-vendor plant estate. That gap is the copilot's reason to exist.

| Layer | Example | GenAI / AI capability | Limits noted | Relevance |
| --- | --- | --- | --- | --- |
| Control & engineering | [Siemens Industrial Copilot](https://www.arcweb.com/blog/siemens-industrial-copilot-empowers-manufacturers) | PLC code generation and explanation in TIA Portal; operations copilot reads live machine data and guides alarm diagnosis; Planning Copilot in Teamcenter Easy Plan | Works only within the Siemens ecosystem; claims not independently validated | Integrate with, don't replace |
| Control & engineering | [Rockwell FactoryTalk Design Studio copilot](https://www.healthcarepackaging.com/home/article/22927841/rockwell-automations-factorytalk-design-studio-adds-generative-ai-copilot) | Built on Azure OpenAI; generates and explains controller code; separate Optix F&B model (Phi-3) guides packaging operators | Engineering focus; no scheduling mentioned | Integrate with, don't replace |
| Planning & scheduling (APS) | [Siemens Opcenter APS](https://blogs.sw.siemens.com/opcenter/opcenter-takes-center-stage-at-realize-live-2026-transform-your-manufacturing-operations-with-ai-powered-planning-and-execution/) | "AI-powered algorithms" that optimize sequences and reduce changeovers | No copilot, agents or natural language mentioned | The solver layer the copilot calls |
| Industrial data & agents | [Cognite Atlas AI](https://www.arcweb.com/blog/cognite-atlas-ai-industrial-agent-workbench-low-code-tool-announced-cognite) | Low-code agent builder on an industrial knowledge graph; agents deployable into Microsoft Copilot | Asset-heavy focus; no scheduling logic | Possible data foundation |

Other names worth knowing by layer: ABB, Schneider Electric, Emerson, Honeywell (control); Rockwell Plex, Dassault DELMIA, SAP Digital Manufacturing (MES); Kinaxis, o9, Blue Yonder (supply-chain planning); AVEVA PI (historian). Check each product's current status before naming it in an ADR.

| Option | What you get | Gaps for Nahda | Verdict |
| --- | --- | --- | --- |
| Buy a vendor copilot | Fast start inside one vendor's tools | Plants run mixed vendors; Arabic support and in-region hosting unconfirmed; engineering focus, not re-planning | No, as the core |
| Buy an industrial data + agent platform | Data model, connectors, agent tooling | Platform cost; scheduling logic still needed | Maybe, as the data layer at 10+ plants |
| Build everything, including the solver | Full control | Reinvents APS; years of edge cases | No |
| **Hybrid: keep APS/MES, build the copilot layer** | Context assembly, constraint checker, explanations (AR/EN), decision capture, evaluation | Integration work per plant | **Yes**: buy the commodity, build the differentiator |

For the capstone PoC, an open-source solver (OR-Tools CP-SAT, the reference solver in Starjob and SCHEDBench) stands in for the plant's APS.

## 3. Evaluating scheduling recommendations

A proposal is good only if it is feasible, improves delivery without churning the plan, and leads planners to *correct* decisions; explanations raise adoption faster than they raise understanding, so trust must be measured, not assumed.

- **Efficiency vs stability is a real trade-off.** A [2025 rescheduling study](https://www.mdpi.com/2076-3417/15/5/2483/html) found complete rescheduling cut total weighted tardiness by about 50% and tardy jobs by 27%, but worsened stability (start-time deviation) and *nervousness* (jobs moved to other machines). Partial repair kept plans steadier.
- **Explanations drive adoption, not necessarily understanding.** In a [job-shop experiment with 253 professionals and engineers](https://www.guidelinecentral.com/pubmed/41811355/) (Ergonomics, 2026), natural-language rationales increased reliance on an AI scheduler through *perceived ability*. The authors recommend pairing rationales with uncertainty and limitations.
- **Correctness is what earns trust.** In a [small study (n=30)](https://arxiv.org/html/2502.20284v1), explanations improved people's ability to spot wrong plans (1.52 to 1.76 of 2), while LLM self-refinement raised trust without raising accuracy, a sign of over-trust.

| Layer | Metric | Proposed gate | How measured |
| --- | --- | --- | --- |
| Feasibility | Hard-constraint violations per proposal | 0 (block release) | Constraint checker over every proposal in `eval_scenarios.jsonl` |
| Delivery | Orders late, total tardiness (h), critical orders on time | Better than or equal to the human reference action on ≥ 70% of scenarios | Simulate proposal vs `planner_decisions.jsonl` |
| Stability | Start-time deviation, jobs moved to another line (nervousness) | Within an agreed budget per disruption | Compare to the baseline schedule |
| Cost of change | Extra changeover minutes, overtime hours | Reported on every option | Simulation |
| Grounding | Cited rules exist; numbers match data | 100% | Automatic check against rules and data |
| Robustness | Same answer when the scenario is reworded or reordered | Stable top option | Paraphrase and reorder each scenario (as in SCHEDBench) |
| Human use (online) | Acceptance, edit and override rate with reasons; time to decision | Rising acceptance *and* no rise in late orders | Decision log in the UI |

**Rollout stages**

1. Offline replay on historical and synthetic disruptions.
2. Shadow mode: the copilot proposes silently; planners decide as today; compare outcomes.
3. Assisted pilot in one plant: proposals visible, planner decides, every decision logged with a reason.
4. Scale plant by plant, with the same gates and a rollback switch per plant.

## 4. OT security and compliance

The copilot lives in the IT zone, reads OT data only through a designed one-way conduit, and has no path back to machines; personal-data law touches only a small part of the data (operator names in notes, planner IDs), while OT security rules shape the whole architecture.

- **IEC 62443 zones and conduits.** Assets are grouped into [zones by risk](https://www.trout.software/blog/iec-62443-zones-and-conduits-explained), and every path between zones is a designed *conduit* with a stated purpose, protocols and controls. A conduit must meet the security level (SL 1–4) of the more sensitive zone it touches.
- **Saudi Arabia: NCA OTCC.** The [Operational Technology Cybersecurity Controls (OTCC-1:2022)](https://nca.gov.sa/en/pages/otcc.html) extend the NCA's Essential Cybersecurity Controls to industrial control systems. Check scope for Nahda's Saudi plants.
- **Design rules:** read from a DMZ replica (historian or broker), never PLCs/SCADA; one direction only, enforced by the network; the only write is an approved draft to APS; treat shift notes and documents as untrusted input (prompt injection); LLM tools are read-only plus one "propose" tool.

| Country | Status | What it means for the copilot |
| --- | --- | --- |
| Saudi Arabia | PDPL in force; transfers abroad need an adequate country or safeguards (SCCs, BCRs); [transfer risk assessment](https://www.clydeco.com/en/insights/2025/03/update-on-saudi-arabia-risk-assessment-guidelines) required when relying on safeguards | Redact operator names before any LLM call outside the Kingdom, or host the model in-region |
| Egypt | Law 151/2020; Executive Regulations issued Nov 2025, [full enforcement expected Oct 2026](https://www.kennedyslaw.com/en/thought-leadership/article/2026/egypt-s-personal-data-protection-law-the-compliance-countdown-has-begun); transfers abroad need PDPC approval, explicit consent or an adequate destination | Same redaction; confirm whether a PDPC transfer permit is needed |
| UAE | Federal PDPL (not reviewed in this pass) | Open question |

## 5. Architecture implications

| ADR | Decision | Evidence | Revisit if |
| --- | --- | --- | --- |
| 0002 LLM role | Solver/heuristic proposes; code checks feasibility; LLM gathers context, explains, answers questions (pattern D) | Direct LLM scheduling: 15% average feasibility, 747% mean gap tail (SCHEDBench) | A model passes the feasibility gate on our scenarios with rewording, at acceptable cost |
| 0003 Build vs buy | Keep APS/MES; build the copilot layer; optional data platform at 10+ plants | Vendor copilots are engineering-focused and ecosystem-bound | A vendor ships cross-vendor re-planning with Arabic and in-region hosting |
| 0004 Re-planning strategy | Default to partial repair; offer full re-plan as a second option with its stability cost shown | Full rescheduling: about −50% tardiness but worse stability and nervousness | Planners consistently pick full re-plans |
| 0005 OT integration | Read from DMZ replica, one-way; only write is an approved draft to APS | IEC 62443 conduits; NCA OTCC | Never for writes to OT |
| 0006 Evaluation gates | 0 constraint violations; ≥ human reference on 70% of scenarios; stability budget; shadow mode before any pilot | Section 3 | Shadow-mode results disagree with offline replay |
| 0007 Model hosting | Redact names before any LLM call; in-region or self-hosted per plant; async path tolerates a slower model | KSA and Egypt transfer rules | A plant's contracts forbid any external processing |
| 0008 Decision capture | Recording planner decisions and reasons is a v1 requirement | No labels means no evaluation and no learning | — |

## 6. Next experiments (on `data/generated/`)

- [ ] **E1. Direct LLM vs solver** on 20 breakdown scenarios; run the constraint checker.
- [ ] **E2. Partial repair vs full re-plan** with OR-Tools CP-SAT; measure late orders, tardiness, deviation, jobs moved.
- [ ] **E3. Robustness to wording**: reword/reorder each scenario 3 times.
- [ ] **E4. Explanation grounding**: auto-check every cited rule and number.
- [ ] **E5. Injection via shift notes**: plant an instruction; confirm it is treated as data.

Open: domain approval; UAE PDPL; OTCC scope for a private manufacturer; solver depth in the capstone; OptiMUS (LLM-to-MILP) not yet reviewed.
