"""Read-only IFC4D viewer acceptance tests against the authoritative Stage 3.8B artifacts."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
from research.ifc4d import viewer_data as d
from research.ifc4d.viewer_ui import gantt_figure,geometry_figure

ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS=ROOT/"data/processed/ifc4d/stage3_8b_v1"

@unittest.skipUnless(ARTIFACTS.is_dir(),"Stage 3.8B artifacts missing")
class IFC4DViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=d.load_bundle(ARTIFACTS)

    def test_all_twelve_combinations_47_tasks_93_assignments_and_conflict_counts(self):
        all_tasks=set();all_elements=set()
        expected={"SYN-BRG-001":[2,4,7],"SYN-BLD-001":[18,15,15]}
        for project in d.PROJECTS:
            for index,snapshot in enumerate(d.SNAPSHOTS):
                for rep in d.REPRESENTATIONS:
                    with self.subTest(project=project,snapshot=snapshot,representation=rep):
                        selected=d.select(self.bundle,project,snapshot,rep)
                        count,elements,deps=d.COUNTS[project]
                        self.assertEqual(len(selected["tasks"]),count)
                        self.assertEqual(len(selected["links"]),elements)
                        self.assertEqual(len(selected["dependencies"]),deps)
                        self.assertEqual(len(selected["source_conflicts"]),expected[project][index])
                        self.assertEqual(len(selected["selected_conflicts"]),0 if rep=="derived" else expected[project][index])
                        self.assertEqual(selected["compliant"],rep=="derived")
                        fig=gantt_figure(selected,selected["tasks"].task_id.iloc[0])
                        self.assertEqual(set(row[0] for row in fig.data[0].customdata),set(selected["tasks"].task_id))
                        self.assertEqual(len(fig.data[0].y),count)
                        all_tasks.update(selected["tasks"].task_id)
                        all_elements.update(selected["elements"].ifc_global_id)
                        for task in selected["tasks"].task_id:
                            wanted={g for tid,g in selected["links"] if tid==task}
                            self.assertEqual(set(d.task_elements(selected,task)),wanted)
                            self.assertTrue(wanted)
        self.assertEqual(len(all_tasks),47)
        self.assertEqual(len(all_elements),93)

    def test_exclusive_finish_to_inclusive_labels_and_exact_bar_duration(self):
        self.assertEqual(d.inclusive_finish("2025-01-01T00:00:00"),"2024-12-31")
        self.assertEqual(d.inclusive_finish("2024-03-01T00:00:00"),"2024-02-29")
        with self.assertRaises(d.ArtifactError):
            d.inclusive_finish("2025-01-01T17:00:00")
        for s in self.bundle["selections"].values():
            for row in s["tasks"].itertuples():
                self.assertEqual((datetime.fromisoformat(row.finish)-datetime.fromisoformat(row.start)).days+1,row.duration)
            chart=gantt_figure(s,s["tasks"].task_id.iloc[0],compare=False)
            self.assertEqual(list(chart.data[0].x),[n*86400000 for n in s["tasks"].duration])
            for custom in chart.data[0].customdata:
                self.assertEqual(custom[3],s["tasks"].set_index("task_id").loc[custom[0],"finish"])

    def test_exact_geometry_and_highlighted_task_globalids(self):
        for project in d.PROJECTS:
            selected=d.select(self.bundle,project,"V0","derived")
            meshes=d.meshes(selected["path"])
            self.assertEqual({m["global_id"] for m in meshes},set(selected["elements"].ifc_global_id))
            import ifcopenshell
            model=ifcopenshell.open(str(selected["path"]))
            for mesh in meshes:
                self.assertEqual(len(mesh["vertices"]),8)
                self.assertEqual(len(mesh["faces"]),12)
                self.assertTrue(np.isfinite(mesh["vertices"]).all())
                vertices=np.asarray(mesh["vertices"])
                volume=abs(sum(np.dot(vertices[a],np.cross(vertices[b],vertices[c])) for a,b,c in mesh["faces"])/6)
                solid=model.by_guid(mesh["global_id"]).Representation.Representations[0].Items[0]
                self.assertAlmostEqual(volume,float(solid.SweptArea.XDim)*float(solid.SweptArea.YDim)*float(solid.Depth),places=7)
            tid=selected["tasks"].task_id.iloc[-1]
            highlights=set(d.task_elements(selected,tid))
            fig=geometry_figure(meshes,highlights)
            self.assertEqual({row[0] for row in fig.data[-1].customdata},highlights)
            # Nonzero Z in a 2D profile is not silently discarded by the fallback.
            e=model.by_type("IfcBuildingElementProxy")[0]
            e.Representation.Representations[0].Items[0].SweptArea.Position.Location.Coordinates=(0.,0.,5.)
            with self.assertRaises(d.ArtifactError):
                d.rectangle_extrusion_mesh(e,"test")

    def test_incomplete_corrupt_unsafe_and_semantically_inconsistent_artifacts_rejected(self):
        def modify_manifest(folder,change):
            file=folder/"manifest.json";m=json.loads(file.read_text());change(m);file.write_text(json.dumps(m))
        def broken_bytes(folder):
            with (folder/"SYN-BRG-001-V0/derived.ifc").open("a") as f:f.write("CORRUPT")
        def bad_trip(folder):
            f=folder/"round_trip_validation.json";rows=json.loads(f.read_text());rows[0]["passed"]=False;f.write_text(json.dumps(rows))
            modify_manifest(folder,lambda m:m["output_sha256"].update({f.name:hashlib.sha256(f.read_bytes()).hexdigest()}))
        def bad_mapping(folder):
            f=folder/"task_ifc_mapping.csv";f.write_text(f.read_text().replace("SYN-BRG-001-T001","NONEXISTENT",1))
            modify_manifest(folder,lambda m:m["output_sha256"].update({f.name:hashlib.sha256(f.read_bytes()).hexdigest()}))
        cases=[lambda f:modify_manifest(f,lambda m:m.update(complete=False)),
               lambda f:modify_manifest(f,lambda m:m["output_sha256"].pop("SYN-BRG-001-V0/derived.ifc")),
               lambda f:modify_manifest(f,lambda m:m["output_sha256"].update({"../outside":"bad"})),
               broken_bytes,bad_trip,bad_mapping,
               lambda f:(f/"schedule_validation.json").unlink()]
        for action in cases:
            with self.subTest(case=action),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)/"artifacts";shutil.copytree(ARTIFACTS,folder);action(folder)
                with self.assertRaises(d.ArtifactError):d.load_bundle(folder)
        for args in [("wrong","V0","derived"),(d.PROJECTS[0],"V9","derived"),(d.PROJECTS[0],"V0","actual")]:
            with self.assertRaises(d.ArtifactError):d.select(self.bundle,*args)

    def test_loading_and_rendering_preserve_sources_and_all_stage3_8b_files(self):
        raw=ROOT/"data/raw/beam bridge-texas midrise"
        manifest=self.bundle["manifest"]
        expected=manifest["input_sha256"]
        self.assertEqual({p.name:d.pipeline.digest(p) for p in raw.iterdir() if p.name in expected},expected)
        before={p:d.pipeline.digest(p) for p in ARTIFACTS.rglob("*") if p.is_file()}
        b=d.load_bundle(ARTIFACTS)
        for selected in b["selections"].values():
            geometry_figure(d.meshes(selected["path"]),d.task_elements(selected,selected["tasks"].task_id.iloc[0]))
        self.assertEqual(before,{p:d.pipeline.digest(p) for p in before})
        self.assertEqual({p.name:d.pipeline.digest(p) for p in raw.iterdir() if p.name in expected},expected)

    def test_streamlit_workspace_controls_and_project_switch(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(ROOT/"pages/1_IFC4D_Synthetic.py"),default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual([s.label for s in app.selectbox], ["Project","Snapshot","Representation","Selected task","Inspect IFC element (GlobalId)"])
        app.selectbox[0].set_value("SYN-BLD-001").run()
        app.selectbox[1].set_value("V2").run()
        app.selectbox[2].set_value("derived").run()
        app.selectbox[3].set_value("SYN-BLD-001-T027").run()
        app.checkbox[1].check().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[3].value,"SYN-BLD-001-T027")
        self.assertTrue(any(m.value=="Compliant" for m in app.metric))

    def test_artifact_rejection_is_visible_before_charts_render(self):
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        with patch("research.ifc4d.viewer_ui.data.load_bundle",side_effect=d.ArtifactError("test SHA-256 mismatch")):
            app=AppTest.from_string("from pathlib import Path\nfrom research.ifc4d.viewer_ui import render\nrender(Path('.'))",default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.error),1)
            self.assertIn("IFC4D artifacts rejected",app.error[0].value)
            self.assertEqual(len(app.get("plotly_chart")),0)
