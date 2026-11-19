"""Agent 2 scheduling cases and Stage 5.4A contract regression tests."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pmi_core.scheduling.__main__ import main, validate_schedule
from pmi_core.scheduling.calendar import SchedulingError, round_duration
from pmi_core.scheduling.cpm import calculate
from pmi_core.scheduling.fixture import adapt, read_json, verify_reference


ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / "research/planning/stage5_4_preparation"
OUT = ROOT / "research/implementation/stage5_4a"
CONFIG = read_json(OUT / "controlled_schedule_inputs.json")
HANDOVER = read_json(ROOT / CONFIG["handover"])
PREPARED = read_json(PREP / "controlled_scheduling_inputs.json")
CASES = {case["case_id"]: case["expected"] for case in read_json(PREP / "scheduling_test_cases.json")["cases"]}


def task(key, duration, **fields):
    return {"id": key, "kind": "productive", "duration_minutes": duration, **fields}


def link(start, finish, basis="elapsed", minutes=0):
    return {"predecessor_id": start, "successor_id": finish, "relation": "FS",
            "lag_minutes": minutes, "lag_basis": basis}


def run(tasks, edges=(), **kwargs):
    calendar = {**PREPARED["calendar"], "date_exceptions": kwargs.pop("exceptions", [])}
    return calculate(tasks, edges, calendar, start="2027-01-04T08:00", horizon="2027-02-15T16:00", **kwargs)


def stamp(value):
    return value[:16].replace("T", " ")


def actual(result):
    return {row["id"]: [stamp(row["earliest_start"]), stamp(row["earliest_finish"])]
            for row in result["activities"]}


class CalendarCPMTests(unittest.TestCase):
    def test_tc1_chain_and_holiday(self):
        tasks = [task("A", 180), task("B", 150), task("C", 240)]
        edges = [link("A", "B"), link("B", "C")]
        result = run(tasks, edges)
        self.assertEqual(actual(result), {k: CASES["TC1"][k] for k in "ABC"})
        self.assertEqual(stamp(result["project_completion"]), CASES["TC1"]["makespan"])
        holiday = run(tasks, edges, exceptions=["2027-01-05"])
        self.assertEqual(actual(holiday)["C"], ["2027-01-06 08:00", "2027-01-06 12:00"])

    def parallel(self, same_pool):
        return run([task("A", 180, resources={"X": 1}),
                    task("B", 300, resources={"X" if same_pool else "Y": 1}),
                    task("C", 120, resources={"X": 1})], [link("A", "C"), link("B", "C")],
                   capacities={"X": 1, "Y": 1})

    def test_tc2_parallel_backward_float(self):
        result = self.parallel(False)
        self.assertEqual(actual(result), {k: CASES["TC2"][k] for k in "ABC"})
        self.assertEqual(result["resource_conflicts"], [])
        rows = {row["id"]: row for row in result["activities"]}
        self.assertEqual(rows["A"]["total_float_minutes"], 120)
        self.assertEqual(rows["A"]["free_float_minutes"], 120)
        self.assertEqual(rows["B"]["total_float_minutes"], 0)
        self.assertEqual(result["critical_activity_ids"], ["B", "C"])

    def test_tc3_shared_pool_cpm_does_not_level(self):
        result = self.parallel(True)
        self.assertEqual(stamp(result["project_completion"]), CASES["TC3"]["cpm_unconstrained_finish"])
        self.assertFalse(result["resource_constraints_enforced"])
        conflict, = result["resource_conflicts"]
        self.assertEqual((conflict["resource"], conflict["usage"], conflict["capacity"]), ("X", 2, 1))

    def test_tc4_fit_split_and_weekend(self):
        fields = {"not_before": "2027-01-08T12:00"}
        self.assertEqual(actual(run([task("A", 360, **fields)]))["A"], CASES["TC4"]["non_interruptible"])
        result = run([task("A", 360, interruption="split_allowed", **fields)])
        row, = result["activities"]
        self.assertEqual([[stamp(a), stamp(b)] for a, b in row["segments"]], CASES["TC4"]["approved_split"])
        self.assertEqual(row["total_float_minutes"], 0)
        with self.assertRaises(SchedulingError) as caught:
            run([task("A", 600, **fields)])
        self.assertEqual(caught.exception.code, "NO_FIT")

    def test_tc5_elapsed_curing(self):
        result = run([task("POUR", 60, not_before="2027-01-08T14:00"),
                      task("CURE", 2880, kind="elapsed_hold"), task("STRIP", 60)],
                     [link("POUR", "CURE"), link("CURE", "STRIP")])
        self.assertEqual(actual(result), {k: CASES["TC5"][k] for k in ("POUR", "CURE", "STRIP")})

    def test_tc6_strength_condition(self):
        tasks = [task("POUR", 60), task("RELEASE", 4320, kind="strength_release", release_event_id="check"),
                 task("STRIP", 60)]
        links = [link("POUR", "RELEASE"), link("RELEASE", "STRIP")]
        missing = run(tasks, links)
        self.assertEqual(missing["status"], "conditional")
        expected = CASES["TC6"]
        self.assertEqual(actual(missing)["STRIP"], expected["no_approval_event"]["strip_projected"])
        for time, key in (("2027-01-08T10:30", "approval_2027_01_08_1030"),
                          ("2027-01-05T09:00", "approval_before_minimum_2027_01_05_0900")):
            result = run(tasks, links, release_events={"check": {"status": "recorded_pass", "at": time}})
            self.assertEqual(actual(result)["STRIP"], expected[key]["strip"])
            self.assertEqual(actual(result)["RELEASE"][0], "2027-01-04 09:00")
        without = adapt(HANDOVER, PREPARED, {**CONFIG, "hypothetical_strength_events": {}})
        self.assertEqual(without["status"], "conditional")
        self.assertTrue(all(row["conditional"] for row in without["activities"] if row["work_item"] == "FRM-STRIP"))

    def test_tc7_impossible_deadline(self):
        with self.assertRaises(SchedulingError) as caught:
            run([task("A", 480), task("B", 480)], [link("A", "B")],
                deadlines={"B": "2027-01-04T16:00"})
        exc = caught.exception
        self.assertEqual(exc.code, "INFEASIBLE_DEADLINE")
        self.assertEqual(stamp(exc.details["earliest_finish"]), CASES["TC7"]["earliest_B_finish"])
        self.assertEqual(exc.details["ancestor_ids"], ["A", "B"])

    def test_tc8_capacity_preflight(self):
        for capacity, code in ((None, "MISSING_INPUT"), (0, "IMPOSSIBLE_CREW"), (1, "IMPOSSIBLE_CREW")):
            with self.subTest(capacity=capacity), self.assertRaises(SchedulingError) as caught:
                run([task("REBAR", 30, resources={"X": 2})], capacities={"X": capacity})
            self.assertEqual(caught.exception.code, code)

    def test_tc9_cycle_and_invalid_endpoints(self):
        tasks = [task(key, 15) for key in "ABC"]
        for edges, code in (([link("A", "B"), link("B", "C"), link("C", "A")], "CYCLE"),
                            ([link("A", "X")], "MISSING_ENDPOINT"),
                            ([link("A", "B"), link("A", "B", minutes=15)], "CONFLICTING_RELATIONSHIPS")):
            with self.assertRaises(SchedulingError) as caught:
                run(tasks, edges)
            self.assertEqual(caught.exception.code, code)
            if code == "CYCLE":
                cycle = caught.exception.details["activity_ids"]
                self.assertEqual(set(cycle[:-1]), set(CASES["TC9"]["cycle"][:-1]))
                self.assertEqual(cycle[0], cycle[-1])

    def test_tc10_controlled_fixture_and_cost_preservation(self):
        source = deepcopy(HANDOVER)
        reference = verify_reference(source, PREP, ROOT / CONFIG["fixture_inputs"])
        result = adapt(source, PREPARED, CONFIG)
        self.assertEqual(result, adapt(source, PREPARED, CONFIG))
        self.assertEqual(source, HANDOVER)
        self.assertEqual(stamp(result["project_completion"]), CASES["TC10"]["makespan"])
        checks, compare, delta = validate_schedule(result, PREP / "fixture_expected_schedule.csv")
        self.assertTrue(all(row["passed"] for row in checks))
        self.assertTrue(all(row["start_difference_minutes"] == row["finish_difference_minutes"] == 0 for row in compare))
        self.assertEqual(delta, 0)
        self.assertEqual(result["resource_conflicts"], [])
        self.assertEqual(result["cost"], HANDOVER["cost"])
        self.assertEqual(result["element_quantities"], HANDOVER["element_quantities"])
        self.assertEqual(result["cost"]["total_direct_reference_eur"], reference["independent_reference_cost_eur"])
        self.assertEqual(result["original_stage5_3_dependencies"], HANDOVER["dependencies"])
        self.assertEqual(len(result["critical_activity_ids"]), 7)
        self.assertFalse(result["real_project_eligible"])
        self.assertTrue(all(row["status"] == "PENDING" for row in result["pending_approvals"]))

    def test_independent_striking_minimum_and_delivery(self):
        prep, source = deepcopy(PREPARED), deepcopy(HANDOVER)
        prep["curing"]["SLAB"]["elapsed_hours"] = 30
        for row in source["activities"]:
            if row["work_item"] == "CURE" and row["global_id"].startswith("3wOB"):
                row["elapsed_hours"] = 30
        original, changed = (adapt(a, b, CONFIG) for a, b in ((HANDOVER, PREPARED), (source, prep)))
        stamp_by_alias = lambda result: {r["reference_id"]: r["earliest_finish"] for r in result["activities"]}
        self.assertEqual(stamp_by_alias(original)["S-STRIKE"], stamp_by_alias(changed)["S-STRIKE"])
        result = run([task("POUR", 45, not_before="2027-01-04T13:30", allowed_hours=[["08:00", "14:00"]])])
        self.assertEqual(actual(result)["POUR"], ["2027-01-05 08:00", "2027-01-05 08:45"])

    def test_rounding_working_lags_milestones_and_timezone(self):
        self.assertEqual(round_duration(15.000000000000002, 15), 15)
        self.assertEqual(round_duration(15.1, 15), 30)
        result = run([task("A", 465), task("B", 0, kind="milestone")],
                     [link("A", "B", "working", 30)])
        self.assertEqual(actual(result)["B"], ["2027-01-05 08:15", "2027-01-05 08:15"])
        self.assertTrue(result["project_completion"].endswith("+01:00"))
        self.assertEqual(result["critical_activity_ids"], ["A", "B"])

    def test_cli_export(self):
        with TemporaryDirectory() as temp:
            p = Path(temp)
            config = {**CONFIG, **{key: str(ROOT / CONFIG[key])
                                  for key in ("preparation_directory", "fixture_inputs", "handover")}}
            cfg = p / "config.json"
            cfg.write_text(json.dumps(config), encoding="utf8")
            self.assertEqual(main(["--config", str(cfg), "--output", str(p / "result")]), 0)
            html = (p / "result/report.html").read_text(encoding="utf8")
            self.assertIn("Column work package", html)
            self.assertIn("2027-01-14T16:00+01:00", html)
