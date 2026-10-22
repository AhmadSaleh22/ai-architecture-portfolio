"""Core tests: factory parity and the independent checker.

    uv run python -m unittest discover engine/tests
"""
import copy
import sys
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))

from adapters import factory as fa  # noqa: E402
from core import Job, Problem, Requirement, Resource, Task, cpsat, greedy  # noqa: E402,F401
from core.check import check  # noqa: E402

C = ENGINE / "configs"
S = ENGINE / "samples"


class TestFactoryParity(unittest.TestCase):
    """The rewrite must give the factory exactly what the old factory-only solvers gave."""

    def test_greedy_matches_old_rules(self):
        for cfg, orders, start, want in [
            ("coffee_roastery.yaml", "coffee_orders.csv", "2026-10-18T08:00", (1, 17.2, 60)),
            ("nahda_riyadh.yaml", "nahda_orders.csv", "2026-10-18T06:00", (0, 0.0, 470)),
        ]:
            p = fa.build(C / cfg, S / orders, start)
            s, r = greedy.solve(p)
            k = fa.kpis(p, s, r)
            self.assertEqual((k["late_jobs"], k["weighted_tardiness_h"], k["setup_minutes"]), want, cfg)
            self.assertEqual(check(p, s, r), [])

    def test_cpsat_at_least_as_good(self):
        p = fa.build(C / "coffee_roastery.yaml", S / "coffee_orders.csv", "2026-10-18T08:00")
        s, r = cpsat.solve(p, seconds=10)
        k = fa.kpis(p, s, r)
        self.assertEqual(check(p, s, r), [])
        self.assertLessEqual(k["weighted_tardiness_h"], 17.2)
        self.assertLessEqual(k["setup_minutes"], 60)


class TestCoreChecker(unittest.TestCase):
    """A tiny hand-made problem: two tasks, one machine, a pool of 1 person."""

    def setUp(self):
        R = {"m": Resource("m", 1, [(0, 600)], setups={"by": "c", "default_min": 30}),
             "people": Resource("people", 1, [(0, 600)])}
        T = {"a": Task("a", ["J"], [Requirement(["m"]), Requirement(["people"])], {"m": 60}, {"c": "red"}),
             "b": Task("b", ["J"], [Requirement(["m"]), Requirement(["people"])], {"m": 60}, {"c": "blue"}, seq=1)}
        J = {"J": Job("J", due=300, last=["b"])}
        self.p = Problem(R, T, J, [("a", "b", 10, 120)], 600)
        self.s, self.r = greedy.solve(self.p)

    def test_greedy_respects_setup_and_lag(self):
        self.assertEqual(check(self.p, self.s, self.r), [])
        self.assertEqual(self.s["b"]["start"], 60 + 30)        # 30 min setup >= 10 min lag

    def _broken(self, f):
        s = copy.deepcopy(self.s)
        f(s)
        return check(self.p, s, self.r)

    def test_catches_missing_setup(self):
        def f(s):
            s["b"]["start"], s["b"]["end"] = 70, 130
        self.assertTrue(any("setup" in v for v in self._broken(f)))

    def test_catches_max_lag(self):
        def f(s):
            s["b"]["start"], s["b"]["end"] = 400, 460
        self.assertTrue(any("maximum is 120" in v for v in self._broken(f)))

    def test_catches_closed_hours(self):
        def f(s):
            s["b"]["start"], s["b"]["end"] = 560, 620
        self.assertTrue(any("working hours" in v for v in self._broken(f)))

    def test_cpsat_same_problem(self):
        s, r = cpsat.solve(self.p, seconds=2)
        self.assertEqual(check(self.p, s, r), [])


if __name__ == "__main__":
    unittest.main()
