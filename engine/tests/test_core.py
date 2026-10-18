"""Core tests: the same core runs a roastery, a beverage plant, a clinic, a school and a tour operator.

    uv run python -m unittest discover engine/tests
"""
import copy
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))

from adapters import factory as fa, school, services as sv, travel  # noqa: E402
from core import Job, Problem, Requirement, Resource, Task, cpsat, greedy, modes  # noqa: E402,F401
from core.check import check  # noqa: E402
from core.kpi import kpis  # noqa: E402
from core.model import subtract  # noqa: E402

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


class TestClinic(unittest.TestCase):
    START = "2026-10-18T07:00"

    def setUp(self):
        self.cfg = sv.load_config(C / "clinic.yaml")
        self.reqs = sv.read_requests(S / "clinic_requests.csv")
        self.p = sv.build(self.cfg, self.reqs, self.START)
        self.plan, self.rej = cpsat.solve(self.p, seconds=5)

    def test_plan_books_everyone_inside_preferences(self):
        k = kpis(self.p, self.plan, self.rej)
        self.assertEqual(check(self.p, self.plan, self.rej), [])
        self.assertEqual(k["scheduled"], 12)
        self.assertEqual(k["avg_pref_deviation_min"], 0)

    def test_requested_doctor_is_respected(self):
        for j in ("A07", "A08", "A09"):
            self.assertIn("dr_hana", self.plan[f"{j}:consult"]["res"])

    def test_offer_three_slots_without_moving_anyone(self):
        new = {"id": "N01", "class": "routine", "service": "cardio_visit", "release": self.START,
               "pref_from": "2026-10-20T09:00", "pref_to": "2026-10-20T11:00"}
        p2 = sv.build(self.cfg, self.reqs + [new], self.START)
        opts = modes.offer(p2, self.plan, "N01", k=3)
        self.assertEqual(len(opts), 3)
        for o in opts:
            booked = modes.accept(self.plan, o)
            self.assertEqual(check(p2, booked, self.rej), [])
            for t, v in self.plan.items():
                self.assertEqual(booked[t], v)                 # nobody else moved

    def test_repair_when_a_doctor_goes_home(self):
        p3 = sv.build(self.cfg, self.reqs, self.START)
        now = 120
        hana = p3.resources["dr_hana"].windows
        p3.resources["dr_hana"].windows = subtract(hana, [(now, hana[0][1])])
        prev = {t: v for t, v in self.plan.items()
                if not ("dr_hana" in v["res"] and now <= v["start"] < hana[0][1])}
        fixed, rej = modes.repair(p3, prev, now, freeze_min=0, seconds=5)
        self.assertEqual(check(p3, fixed, rej), [])
        for t, v in self.plan.items():
            if v["start"] < now:
                self.assertEqual(fixed[t], v)                  # what already happened stays


class TestSchool(unittest.TestCase):
    def test_timetable_and_absence(self):
        cfg = sv.load_config(C / "school.yaml")
        start = "2026-10-18T07:00"
        p = school.build(cfg, start)
        plan, rej = cpsat.solve(p, seconds=15)
        self.assertEqual(check(p, plan, rej), [])
        self.assertEqual(len(rej), 0)
        for t, v in plan.items():                               # CS lab is too small for the grade-10 groups
            if v["res"][0] == "LAB_CS":
                self.assertTrue(any(g in v["res"] for g in ("G11A", "G11B")))
        now = 2 * 1440
        p2 = school.build(sv.load_config(C / "school.yaml"), start)
        p2.resources["T_eng"].windows = subtract(p2.resources["T_eng"].windows, [(now, now + 1440)])
        prev = {t: v for t, v in plan.items() if not ("T_eng" in v["res"] and now <= v["start"] < now + 1440)}
        fixed, rej2 = modes.repair(p2, prev, now, freeze_min=0, seconds=15)
        self.assertEqual(check(p2, fixed, rej2), [])
        self.assertEqual(rej2, [])
        moved = modes.diff(plan, fixed)
        self.assertLessEqual(len(moved), 8)                     # only the absent teacher's lessons (and a few)


class TestTravel(unittest.TestCase):
    def test_week_and_flight_delay(self):
        cfg = sv.load_config(C / "umrah.yaml")
        groups = travel.read_groups(S / "umrah_groups.csv")
        start = "2026-11-01T00:00"
        p = travel.build(cfg, groups, start)
        plan, rej = cpsat.solve(p, seconds=10)
        self.assertEqual(check(p, plan, rej), [])
        self.assertEqual(rej, [])
        for t, v in plan.items():                               # the right guide language
            g = next((x for x in v["res"] if x.startswith("G_")), None)
            if g:
                lang = next(x["lang"] for x in groups if x["group"] == t.split(":")[0])
                self.assertIn(lang, cfg["resources"][g]["skills"])
        delayed = [dict(g) for g in groups]
        delayed[0]["arrive"] = (datetime.fromisoformat(delayed[0]["arrive"]) + timedelta(hours=5)).isoformat()
        p2 = travel.build(cfg, delayed, start)
        prev = {t: v for t, v in plan.items() if not t.startswith(delayed[0]["group"])}
        fixed, rej2 = modes.repair(p2, prev, 180, freeze_min=0, seconds=10)
        self.assertEqual(check(p2, fixed, rej2), [])
        landed = 150 + 5 * 60                                   # 02:30 + 5 h, minutes from Sun 00:00
        self.assertGreaterEqual(fixed[f"{delayed[0]['group']}:arrival"]["start"], landed + 60)


if __name__ == "__main__":
    unittest.main()
