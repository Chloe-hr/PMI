"""PMI dashboard semantics and UI regression tests; no frozen artifacts are rewritten."""
import unittest
from pathlib import Path
from research.ifc4d import viewer_data as data
from research.ifc4d import dashboard_components as ui

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless((ROOT/"data/processed/ifc4d/stage3_8b_v1").is_dir(),"Stage 3.8B bundle unavailable")
class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=data.load_bundle(ROOT/"data/processed/ifc4d/stage3_8b_v1")

    def test_revision_impacts_are_source_snapshot_differences(self):
        for project in data.PROJECTS:
            base=data.select(self.bundle,project,"V0","as_provided")
            self.assertEqual(ui.comparison(base,base)["rows"],[])
            for version in ("V1","V2"):
                rev=data.select(self.bundle,project,version,"as_provided")
                result=ui.comparison(base,rev)
                a=base["tasks"].set_index("task_id");b=rev["tasks"].set_index("task_id")
                changed={tid for tid in a.index if any(a.loc[tid,k]!=b.loc[tid,k] for k in ("start","finish","duration"))}
                self.assertEqual(result["changed_tasks"],changed)
                self.assertEqual(result["changed_dependencies"],set())
                self.assertEqual(result["element_ids"],{gid for tid,gid in rev["links"] if tid in changed})
                self.assertTrue(all(d["predecessor_task_id"] in changed or d["successor_task_id"] in changed for d in result["affected_dependencies"]))

    def test_chart_preserves_all_dates_phase_names_and_selection(self):
        for project in data.PROJECTS:
            phases=ui.phase_map(self.bundle,project)
            for snapshot in data.SNAPSHOTS:
                for rep in data.REPRESENTATIONS:
                    selected=data.select(self.bundle,project,snapshot,rep)
                    tid=selected["tasks"].task_id.iloc[-1]
                    chart=ui.schedule_chart(selected,tid,phases)
                    bars=chart.data[0]
                    self.assertEqual(set(bars.y),set(selected["tasks"].task_id))
                    self.assertEqual(bars.marker.color[-1],ui.GOLD)
                    for row,details,width in zip(selected["tasks"].itertuples(),bars.customdata,bars.x):
                        self.assertEqual(tuple(details[2:5]),(row.start,row.finish,row.duration))
                        self.assertEqual(details[5],phases[row.task_id])
                        self.assertEqual(width,row.duration*86400000)
                    # Technical task identifiers remain in event data, not visible axis text.
                    self.assertFalse(any(project in label for label in chart.layout.yaxis.ticktext))

    def test_scenario_request_cannot_masquerade_as_generated_results(self):
        for priority in ui.PRIORITIES:
            request=ui.scenario_request("SYN-BRG-001","V1","derived",priority,"sha")
            self.assertIsNone(request["final_schedule"])
            self.assertIsNone(request["engine_run_id"])
            self.assertEqual(request["constraints"],{})
            self.assertEqual(request["status"],"awaiting_estimators_and_scenario_engine")
            self.assertNotIn("cost",request)
            self.assertNotIn("emissions",request)
        with self.assertRaises(ValueError):ui.scenario_request("p","v","r","unknown","sha")

    def test_dashboard_professional_controls_and_pending_final_programme(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(ROOT/"pages/2_PMI_Dashboard.py"),default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].options,["Bridge","Mid-rise Building"])
        self.assertEqual(app.selectbox[1].options,["Baseline","Revision 1","Revision 2"])
        self.assertEqual(app.selectbox[2].options,["Original Schedule","Recalculated Schedule"])
        app.selectbox[0].set_value("SYN-BLD-001").run()
        app.selectbox[1].set_value("V2").run()
        app.selectbox[2].set_value("derived").run()
        app.selectbox[3].set_value("SYN-BLD-001-T027").run()
        app.radio[0].set_value("Schedule changes").run()
        app.radio[1].set_value("Environmental priority").run()
        self.assertFalse(app.exception)
        self.assertTrue(next(b for b in app.button if b.label=="Generate final programme").disabled)
        self.assertIsNone(app.session_state.pmi_scenario_request["final_schedule"])
        self.assertTrue(any(e.label=="Technical Details" for e in app.expander))

    def test_original_frozen_entry_and_source_artifacts_unchanged(self):
        import json
        self.assertEqual(data.pipeline.digest(ROOT/"app.py"),"f741710249919c12b751e9fe9823665278d04b88b9e5a660f829b3325ad3842d")
        for file,expected in self.bundle["manifest"]["output_sha256"].items():
            self.assertEqual(data.pipeline.digest(self.bundle["folder"]/file),expected)
        for file,expected in self.bundle["manifest"]["implementation_sha256"].items():
            self.assertEqual(data.pipeline.digest(ROOT/"research/ifc4d"/file),expected)
