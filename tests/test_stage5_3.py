"""Regression tests for the controlled engineering estimation contract."""

from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pmi_core.estimation.__main__ import main
from pmi_core.estimation.comparison import compare_review
from pmi_core.estimation.engine import estimate_frame, estimate_operation, group_packages
from pmi_core.estimation.references import load_references


ROOT = Path(__file__).resolve().parents[1]
STAGE2 = ROOT / "research/implementation/stage5_2/demonstrations/controlled"
STAGE3 = ROOT / "research/implementation/stage5_3"


class EstimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bim, cls.construction, cls.config = [
            json.loads(path.read_text(encoding="utf8")) for path in
            (STAGE2 / "import.json", STAGE2 / "construction.json", STAGE3 / "fixture_inputs.json")
        ]
        cls.refs, cls.digest = load_references()

    def run_fixture(self, config=None, bim=None, construction=None):
        return estimate_frame(bim or self.bim, construction or self.construction, config or self.config,
                              self.refs, self.digest)

    def test_unit_demand_and_bottleneck(self):
        ref = self.refs["BEAM-CONC", "05HHJ00003"]
        row = estimate_operation(3, "m3", ref, {"OFICIAL 1ª": 1, "PEÓN ESPECIAL": 2}, {"VIBRADOR": 1})
        self.assertAlmostEqual(row["worker_hours_by_trade"]["PEÓN ESPECIAL"], 1.8)
        self.assertAlmostEqual(row["machine_hours_by_class"]["VIBRADOR"], 0.9)
        self.assertAlmostEqual(row["productive_hours"], 0.9)
        self.assertAlmostEqual(row["reserved_worker_hours"]["OFICIAL 1ª"], 0.9)
        self.assertAlmostEqual(row["materials"][0]["quantity"], 3.09)
        with self.assertRaisesRegex(ValueError, "Incompatible quantity unit"):
            estimate_operation(3, "kg", ref, {}, {})
        for quantity in (0, -1, float("nan"), True):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                estimate_operation(quantity, "m3", ref, {}, {})

    def test_missing_and_invalid_resources_block_affected_estimates(self):
        for value in (None, 0, True, -1, 0.5):
            config = deepcopy(self.config)
            config["equipment"]["VIBRADOR"] = value
            with self.subTest(value=value):
                result = self.run_fixture(config)
                self.assertFalse(result["eligible_for_controlled_scheduling_input"])
                self.assertIsNone(result["cost"]["total_direct_reference_eur"])
                self.assertEqual(sum(bool(row["blockers"]) for row in result["activities"]), 3)
        config = deepcopy(self.config)
        del config["equipment"]["CONCRETE_DELIVERY"]
        config["crews"]["HYP-REBAR"] = {}
        result = self.run_fixture(config)
        self.assertEqual(sum(bool(row["blockers"]) for row in result["activities"]), 6)

    def test_cost_reconciles_and_bundle_is_counted_once(self):
        result = self.run_fixture()
        cost = result["cost"]
        self.assertAlmostEqual(cost["total_direct_reference_eur"], 1172.5136)
        self.assertAlmostEqual(cost["total_direct_reference_eur"],
                               sum(cost["components_eur"].values()) + cost["rounding_residual_eur"])
        self.assertEqual(sum(row.get("reference_cost_eur") is not None for row in result["activities"]), 12)
        self.assertEqual(sum(row["work_item"] == "FRM-STRIP" for row in result["activities"]), 3)
        self.assertTrue(all("curing labour" in row["reference"]["bundled_operations"]
                            for row in result["activities"] if row["work_item"].endswith("-CONC")))
        config = deepcopy(self.config)
        config["catalogue"]["CURE"] = "invalid_separate_reference"
        with self.assertRaisesRegex(ValueError, "DC03"):
            self.run_fixture(config)
        construction = deepcopy(self.construction)
        for choice in construction["catalogue_options"]:
            if choice["work_item"] == "COL-FORM":
                choice["includes_stripping"] = "True"
        with self.assertRaisesRegex(ValueError, "DC01"):
            self.run_fixture(construction=construction)

    def test_holds_have_no_crew_and_do_not_repeat_curing_elapsed_time(self):
        result = self.run_fixture()
        self.assertEqual(len(result["activities"]), 21)
        self.assertEqual(len(result["dependencies"]), 21)
        self.assertEqual(result["graph_issues"], [])
        for package in result["packages"]:
            rows = [row for row in result["activities"] if row["package_id"] == package["id"]]
            holds = {row["work_item"]: row for row in rows if row["kind"] == "elapsed_hold"}
            self.assertEqual(holds["CURE"]["elapsed_hours"] + holds["STRIKING-RELEASE"]["elapsed_hours"],
                             24 if package["family"] == "COL" else 168)
            self.assertTrue(all(not row["worker_hours_by_trade"] and not row["machine_hours_by_class"]
                                and row["productive_hours"] is None and row["reference_cost_eur"] is None
                                for row in holds.values()))

    def test_fixture_isolation_and_deterministic_results(self):
        self.assertEqual(self.run_fixture(), self.run_fixture())
        result = self.run_fixture()
        self.assertTrue(result["eligible_for_controlled_scheduling_input"])
        self.assertFalse(result["eligible_for_real_scheduling"])
        self.assertTrue(all(not row["eligible_for_real_scheduling"] and row["pending_approval_ids"]
                            for row in result["activities"]))
        for patch in ({"policy": "exploratory"},
                      {"model_version": {**self.bim["model_version"], "sha256": "real-model"}}):
            with self.assertRaisesRegex(ValueError, "Fixture scope only"):
                self.run_fixture(bim={**self.bim, **patch})
        changed = deepcopy(self.config)
        guid = next(iter(changed["elements"]))
        lo, hi = changed["elements"][guid]["bounds_m"]
        changed["elements"][guid]["bounds_m"] = [[lo[0], lo[1], lo[2] + 0.2], [hi[0], hi[1], hi[2] + 0.2]]
        with self.assertRaisesRegex(ValueError, "intersection"):
            self.run_fixture(changed)

    def test_explicit_grouping_preserves_global_ids(self):
        assignments = {key: {"storey": "S1", "zone": "Z", "classification": "column",
                             "method": "cage_first", "batch": "P1"} for key in ("a", "b")}
        packages = [{"id": "p1", "global_ids": ["a"]}, {"id": "p2", "global_ids": ["b"]}]
        group, = group_packages(packages, assignments)
        self.assertEqual(group["global_ids"], ["a", "b"])
        self.assertEqual(group["package_ids"], ["p1", "p2"])
        self.assertEqual(group_packages(packages, {}), [])
        with self.assertRaises(ValueError):
            group_packages(packages, {**assignments, "unknown": assignments["a"]})

    def test_cli_exports(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "result"
            self.assertEqual(main(["--bim", str(STAGE2 / "import.json"), "--construction",
                                   str(STAGE2 / "construction.json"), "--config",
                                   str(STAGE3 / "fixture_inputs.json"), "--output", str(folder)]), 0)
            self.assertTrue((folder / "activities.csv").is_file())
            self.assertIn("1,172.51", (folder / "report.html").read_text(encoding="utf8"))
            recorded = STAGE3 / "demonstration/estimate.json"
            if recorded.exists():
                self.assertEqual(sha256(recorded.read_bytes()).digest(),
                                 sha256((folder / "estimate.json").read_bytes()).digest())


    def test_review_reference_comparison_independent(self):
        rows = compare_review()
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[-1]["recomputed_exact_eur"], Decimal("3966.32446"))
        self.assertTrue(all(row["difference_eur"] == 0 for row in rows))

    def test_throughput_and_sequential_methods(self):
        config = deepcopy(self.config)
        config["equipment"]["CONCRETE_PUMP"] = {
            "capacity": 0.5, "unit": "m3/h", "concurrent_with_placement": True,
        }
        result = self.run_fixture(config)
        beam = next(row for row in result["activities"] if row["work_item"] == "BEAM-CONC")
        self.assertEqual(beam["productive_hours"], 1.6)
        self.assertEqual(beam["capacity_bounds_hours"]["throughput:CONCRETE_PUMP"], 1.6)
        guid = next(iter(config["elements"]))
        config["elements"][guid]["execution_mode"] = "sequential"
        blocked = self.run_fixture(config)
        self.assertFalse(blocked["eligible_for_controlled_scheduling_input"])
        self.assertTrue(any("Insufficient phase evidence" in reason for row in blocked["activities"]
                            for reason in row["blockers"]))

    def test_pending_approvals_and_handover_evidence(self):
        result = self.run_fixture()
        self.assertEqual(len(result["pending_approvals"]), 75)
        self.assertEqual(len(result["conditional_dependencies"]), 6)
        self.assertIn("hypothetical_fixture", result["input_states"])
        self.assertIn("independently_measured", result["input_states"])
        construction = deepcopy(self.construction)
        construction["approval_register"][0]["status"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "75 engineering approvals"):
            self.run_fixture(construction=construction)
