"""Domain-agnostic scheduling core.

Nothing in here knows about coffee, clinics, schools or buses. A domain adapter turns its own
world (orders, appointments, courses, tour groups) into the objects below, and gets back a
schedule that the core's checker has verified.

    Resource     anything with a calendar and a capacity: machine, doctor, room, class group, bus, site
    Requirement  "one of these resources, this many units": the first one of a task is its primary
    Task         one piece of work: duration per primary candidate, time limits, attributes for setups
    Job          what the customer sees: an order, an appointment, a course, a tour. Lateness and
                 rejection are measured per job. A task can serve several jobs (a roast batch).
    Problem      resources + tasks + jobs + precedences (with min/max lags) + objective list

Solvers: greedy (fast, any size) and cpsat (OR-Tools). Modes: plan, offer (best k slots for a
new request), repair (replan after a disruption, keeping the old plan where possible).
"""
from .model import Job, Problem, Requirement, Resource, Task  # noqa: F401
