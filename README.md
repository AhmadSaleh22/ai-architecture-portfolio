# AI Architecture Portfolio

Ahmad Saleh · [AI Architecture Design](https://academy.mlopsmena.com/en/courses/ai-architecture-design), MLOps MENA, Oct–Dec 2026

My work for the course. I'm building one architecture across the sessions, and it ends up as my capstone.

## Scenario

An assistant for production planners in a manufacturing company.

When something goes wrong on the floor (a machine breaks, materials arrive late, a rush order comes in), the planner has to rebuild the plan by hand. That takes 30–90 minutes, across several systems and phone calls. The assistant suggests a new plan, explains it in Arabic or English, and the planner decides.

The LLM doesn't build the schedule. A scheduling solver does that, and normal code checks the result against the factory's rules. The LLM explains the result and answers the planner's questions.

Still a draft. I'm confirming the domain with the instructor in Session 1.

## Assumptions

- A mid-size food and beverage manufacturer with several plants in KSA, Egypt and the UAE (fictional company, made-up data)
- Machine data comes from the plants' OT networks, one-way only. The assistant never writes back to machines.
- The data has to stay in the region (KSA / Egypt data protection laws)
- A human approves every change in the first version

## Repo layout

```
README.md       scenario, assumptions, how to read the repo
docs/           one file per session: 01-framing.md, 02-building-blocks.md ...
diagrams/       exported PNG/SVG + source files
adr/            one file per decision: 0001-model-hosting.md ...
capstone/       final architecture PDF + slides
```

## Progress

- [x] Repo
- [x] Session 1 – Architecture views, steps and process (18 Oct) · [notes](docs/01-framing.md)
- [ ] Session 2 – AI system building blocks (25 Oct)
- [ ] Session 3 – LLM and RAG architecture (1 Nov)
- [ ] Midpoint quiz + capstone part 1 (14 Nov)
- [ ] Session 4 – Agentic AI (15 Nov)
- [ ] Session 5 – Security, governance, evals (22 Nov)
- [ ] Session 6 – Case studies (29 Nov)
- [ ] Capstone (13 Dec)

Next: Session 1 quiz, then Session 2 on 25 Oct.
