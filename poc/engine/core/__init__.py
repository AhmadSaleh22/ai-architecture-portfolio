"""Domain-agnostic scheduling core.

Nothing in here knows about a specific factory. The factory adapter turns orders, recipes and
batches into the objects below, and gets back a schedule that the core's checker has verified.

    Resource     anything with a calendar and a capacity: machine, line, tank, crew
    Requirement  "one of these resources, this many units": the first one of a task is its primary
    Task         one piece of work: duration per primary candidate, time limits, attributes for setups
    Job          what the customer sees: an order. Lateness is measured per job.
                 A task can serve several jobs (a roast batch).
    Problem      resources + tasks + jobs + precedences (with min/max lags) + objective list

Solvers: greedy (fast, any size) and cpsat (OR-Tools). Modes: plan, offer (best k options for a
new order), repair (replan after a disruption, keeping the old plan where possible).
"""
from .model import Job, Problem, Requirement, Resource, Task  # noqa: F401
