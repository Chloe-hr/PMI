"""Regression and preservation tests for the synthetic IFC4D pipeline."""
import copy
from collections import Counter
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/ifc4d"))
import pipeline as p


def row(task, start="2025-01-01", finish="2025-01-01", duration=1):
    return dict(project_id="P", version_id="V0", task_id=task, task_name=task,
                start=start, finish=finish, duration=duration)


def dep(a, b, lag=0, identity=None):
    return dict(project_id="P", dependency_id=identity or a+"-"+b,
                predecessor_task_id=a, successor_task_id=b, relationship_type="FS", lag_days=lag)


class SchedulingTests(unittest.TestCase):
    def test_diamond_earliest_schedule_is_order_independent_and_preserves_inputs(self):
        rows = [row("A", "2025-01-01", "2025-01-02", 2), row("B", "2025-01-20", "2025-01-22", 3),
                row("C"), row("D")]
        deps = [dep("A", "B"), dep("A", "C", 2), dep("B", "D"), dep("C", "D")]
        frozen = copy.deepcopy((rows, deps))
        result = p.derive(rows, deps, date(2025,1,1))
        self.assertEqual((rows, deps), frozen)
        self.assertEqual(result, p.derive(list(reversed(rows)), list(reversed(deps)), date(2025,1,1)))
        byid = {r["task_id"]: r for r in result}
        self.assertEqual(byid["D"]["start"], "2025-01-06")
        self.assertEqual(byid["B"]["start_shift_days"], -17)
        self.assertEqual([r["duration"] for r in result], [2,3,1,1])
        self.assertEqual(p.validate(result, deps), [])

    def test_negative_lag_allows_overlap_and_anchor_bounds_all_tasks(self):
        rows = [row("A", "2025-01-01", "2025-01-05", 5), row("B")]
        result = p.derive(rows, [dep("A", "B", -2)], "2025-01-01")
        self.assertEqual(result[1]["start"], "2025-01-04")
        result = p.derive(rows, [dep("A", "B", -20)], "2025-01-01")
        self.assertEqual(result[1]["start"], "2025-01-01")

    def test_inclusive_finish_and_conflict_details(self):
        rows = [row("A"), row("B")]
        issues = p.validate(rows, [dep("A", "B")])
        self.assertEqual(len(issues), 1)
        self.assertEqual((issues[0]["project_id"], issues[0]["version_id"], issues[0]["task_id"], issues[0]["dependency_id"]), ("P", "V0", "B", "A-B"))
        self.assertEqual(issues[0]["required_start"], "2025-01-02")
        self.assertEqual(issues[0]["shortfall_days"], 1)

    def test_structural_and_duration_errors_block_derivation(self):
        cases = [([row("A"),row("A")], []),
                 ([row("A")], [dep("missing", "A")]),
                 ([row("A"),row("B")], [dep("A","B"),dep("B","A")]),
                 ([row("A", duration=0)], []),
                 ([row("A", duration=2)], []),
                 ([row("A", start="invalid")], []),
                 ([row("A"),row("B")], [dep("A","B",0.5)]),
                 ([row("A"),row("B")], [dict(dep("A","B"),relationship_type="SS")]),
                 ([row("A"),row("B")], [dep("A","B"),dep("A","B")]),
                 ([row("A"),dict(row("B"),project_id="other")], [])]
        for rows, deps in cases:
            with self.subTest(rows=rows,deps=deps), self.assertRaises(ValueError):
                p.derive(rows,deps,"2025-01-01")


@unittest.skipUnless(p.DEFAULT_INPUT.is_file(), "Synthetic workbook is not available")
class WorkbookRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = p.load_workbook(p.DEFAULT_INPUT)

    def test_audited_conflicts_all_snapshots_and_actuals(self):
        building_v0 = {4,5,6,8,9,10,11,14,15,17,18,19,20,21,23,24,25,26}
        expected = {
            "SYN-BRG-001": [{12,13},{2,6,13,16},{2,6,12,13,16,17,19}],
            "SYN-BLD-001": [building_v0,{1,5,8,9,10,12,14,16,17,18,19,20,21,23,26},
                            {1,4,5,8,9,11,12,15,16,17,18,19,21,23,26}],
        }
        actual_expected = {"SYN-BRG-001":{2,6,11,12,13,16,17,19},
                           "SYN-BLD-001":{1,4,5,8,9,11,12,14,15,16,17,18,19,20,21,23,25,26}}
        for pid, sets in expected.items():
            deps = [r for r in self.data["Dependencies"] if r["project_id"] == pid]
            snapshots = p.project_snapshots(self.data,pid)
            anchor = min(p.day(r["start"]) for rows in snapshots.values() for r in rows)
            for rows, conflicts in zip(snapshots.values(),sets):
                with self.subTest(project=pid,version=rows[0]["version_id"]):
                    frozen=copy.deepcopy(rows)
                    issues=p.validate(rows,deps)
                    self.assertEqual({i["code"] for i in issues},{"finish_to_start"})
                    self.assertEqual({i["dependency_id"] for i in issues},{f"{pid}-D{n:03d}" for n in conflicts})
                    derived=p.derive(rows,deps,anchor)
                    self.assertEqual(p.validate(derived,deps),[])
                    self.assertEqual(rows,frozen)
            actual=[dict(project_id=pid,version_id="synthetic_actual",task_id=r["task_id"],start=r["actual_start_synthetic"],finish=r["actual_finish_synthetic"],duration=r["actual_duration_days_synthetic"]) for r in self.data["Activities"] if r["project_id"]==pid]
            self.assertEqual({i["dependency_id"] for i in p.validate(actual,deps)},{f"{pid}-D{n:03d}" for n in actual_expected[pid]})

    def test_incomplete_snapshots_and_changed_baseline_rejected(self):
        for mutate in (lambda d:d["ScheduleVersions"].pop(), lambda d:d["Activities"][0].update(planned_start="2020-01-01")):
            data=copy.deepcopy(self.data)
            mutate(data)
            with self.assertRaises(ValueError):
                for project in data["Projects"]:
                    p.project_snapshots(data,project["project_id"])

    def test_all_ifc_outputs_roundtrip_schema_integrity_and_reproducibility(self):
        import ifcopenshell
        import ifcopenshell.validate
        rawfiles=[p.DEFAULT_INPUT,*p.DEFAULT_INPUT.parent.glob("*.ifc")]
        before={str(f):p.digest(f) for f in rawfiles}
        with tempfile.TemporaryDirectory() as tmp:
            first,second=Path(tmp)/"first",Path(tmp)/"second"
            result=p.run(output=first)
            self.assertTrue(result["round_trip_passed"])
            self.assertEqual(result["files"],12)
            checks=json.loads((first/"round_trip_validation.json").read_text())
            self.assertEqual(sum(r["associations"] for r in checks),93*6)
            self.assertEqual(sum(r["dependencies"] for r in checks),45*6)
            self.assertTrue(all(r["precedence_conflicts"]==0 for r in checks if r["representation"]=="derived"))
            for f in first.rglob("*.ifc"):
                logger=ifcopenshell.validate.json_logger()
                ifcopenshell.validate.validate(str(f),logger,express_rules=False)
                source=p.DEFAULT_INPUT.parent/("PMI_"+f.parent.name.rsplit("-V",1)[0]+".ifc")
                baseline=ifcopenshell.validate.json_logger()
                ifcopenshell.validate.validate(str(source),baseline,express_rules=False)
                def signature(records):
                    return Counter((r["type"],r.get("attribute"),r["instance"].id(),r["message"]) for r in records)
                self.assertEqual(signature(logger.statements),signature(baseline.statements),str(f))
            p.run(output=second)
            self.assertEqual({f.relative_to(first).as_posix():p.digest(f) for f in first.rglob("*") if f.is_file()},
                             {f.relative_to(second).as_posix():p.digest(f) for f in second.rglob("*") if f.is_file()})
            with self.assertRaises(FileExistsError):
                p.run(output=first)
            manifest=json.loads((first/"manifest.json").read_text())
            self.assertTrue(all(p.digest(first/name)==value for name,value in manifest["output_sha256"].items()))
            # A corrupted round-trip must be rejected, rather than merely counted.
            pid="SYN-BRG-001";version=pid+"-V0"
            rows=p.project_snapshots(self.data,pid)[version]
            deps=[r for r in self.data["Dependencies"] if r["project_id"]==pid]
            links=[r for r in self.data["ElementTask"] if r["project_id"]==pid]
            elements=[r for r in self.data["Elements"] if r["project_id"]==pid]
            provenance=dict(test="tamper")
            dest=Path(tmp)/"tampered.ifc";src=p.DEFAULT_INPUT.parent/("PMI_"+pid+".ifc")
            maps=p.convert(src,dest,rows,deps,links,elements,"as_provided",provenance)
            m=ifcopenshell.open(str(dest));m.by_type("IfcRelSequence")[0].TimeLag.LagValue=m.create_entity("IfcDuration","P9D");m.write(str(dest))
            with self.assertRaisesRegex(ValueError,"dependency"):
                p.round_trip(src,dest,rows,deps,links,elements,maps,"as_provided",provenance)
        self.assertEqual(before,{str(f):p.digest(f) for f in rawfiles})

    def test_negative_lag_ifc_roundtrip(self):
        pid="SYN-BRG-001";version=pid+"-V0"
        rows=p.project_snapshots(self.data,pid)[version]
        deps=copy.deepcopy([r for r in self.data["Dependencies"] if r["project_id"]==pid])
        deps[0]["lag_days"]=-2
        links=[r for r in self.data["ElementTask"] if r["project_id"]==pid]
        elements=[r for r in self.data["Elements"] if r["project_id"]==pid]
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"lead.ifc";src=p.DEFAULT_INPUT.parent/("PMI_"+pid+".ifc")
            maps=p.convert(src,dest,rows,deps,links,elements,"as_provided",{})
            self.assertTrue(p.round_trip(src,dest,rows,deps,links,elements,maps,"as_provided",{})["passed"])


if __name__=="__main__":
    unittest.main()
