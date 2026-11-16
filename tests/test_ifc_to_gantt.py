import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "ifc_to_gantt"))
from extract_elements import extract_ifc  # noqa: E402
from generate_tasks import classify, generate, load_rules  # noqa: E402
from schedule_tasks import schedule  # noqa: E402

V1 = ROOT / "models" / "test_case" / "original.ifc"


def el(**kw):
    base = dict(source_id="x", ifc_class="IfcWall", name="", storey="Level 1", storey_elevation=0.0,
                materials="", length_m=None, area_m2=None, volume_m3=None, parent_id="")
    base.update(kw)
    return base


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_rules()["classification"]

    def test_walls_are_split_by_material_not_just_class(self):
        self.assertEqual(classify(el(materials="Metal - Stud Layer;Plasterboard"), self.rules)["package"], "PRT")
        self.assertEqual(classify(el(materials="Masonry - Brick;Masonry - Concrete Block"), self.rules)["package"], "EXW")
        self.assertEqual(classify(el(materials="Concrete - Cast In Situ"), self.rules)["package"], "FWL")

    def test_aggregated_parts_link_without_double_counting(self):
        r = classify(el(ifc_class="IfcStairFlight", parent_id="stair"), self.rules)
        self.assertEqual((r["package"], r["basis"]), ("STR", "none"))

    def test_unknown_element_is_reported_not_guessed(self):
        self.assertIsNone(classify(el(ifc_class="IfcTendon"), self.rules))


class GenerationTests(unittest.TestCase):
    def test_small_building_sequence(self):
        els = pd.DataFrame([
            el(source_id="f", ifc_class="IfcFooting", storey="FDN", storey_elevation=-1, volume_m3=8.0),
            el(source_id="s", ifc_class="IfcSlab", materials="Concrete", volume_m3=16.0),
            el(source_id="w", materials="Masonry - Brick", area_m2=60.0),
            el(source_id="p", materials="Metal - Stud", area_m2=40.0),
            el(source_id="r", ifc_class="IfcRoof", storey="Roof", storey_elevation=6, area_m2=90.0),
        ])
        tasks, links, deps, unc = generate(els)
        self.assertTrue(unc.empty)
        self.assertEqual(len(links), 5)
        d = tasks.set_index("id")["duration_days"]
        self.assertEqual(d["FTG-FDN"], 2)          # 8 m3 / 4 = 2
        self.assertEqual(d["EXW-LEVEL1"], 10)      # 60 m2 / 6 = 10
        pairs = set(zip(deps.predecessor, deps.successor))
        self.assertIn(("FTG-FDN", "GSL-LEVEL1"), pairs)   # slab after footings on storey below
        self.assertIn(("ROF-ROOF", "PRT-LEVEL1"), pairs)  # partitions after watertight roof
        s = schedule(tasks, date(2026, 11, 16)).set_index("id")
        self.assertEqual(s.at["HND", "ES"], s.drop("HND")["EF"].max())   # handover is last
        for p, q in pairs:
            self.assertLessEqual(s.at[p, "EF"], s.at[q, "ES"])


@unittest.skipUnless(V1.is_file(), "test model missing")
class ModelPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.elements = extract_ifc(V1)
        cls.tasks, cls.links, cls.deps, cls.unc = generate(cls.elements)

    def test_every_element_is_scheduled_exactly_once(self):
        self.assertTrue(self.unc.empty)
        self.assertEqual(sorted(self.links.source_id), sorted(self.elements.source_id))

    def test_scheduled_ifc_round_trip_matches_cpm(self):
        import ifcopenshell
        from write_ifc4d import write_schedule

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.tasks.to_csv(d / "tasks.csv", index=False)
            self.links.to_csv(d / "task_element_links.csv", index=False)
            self.deps.to_csv(d / "dependencies.csv", index=False)
            s = schedule(self.tasks, date(2026, 11, 16))
            s.to_csv(d / "schedule.csv", index=False)
            info = write_schedule(V1, d, d / "out.ifc")
            self.assertEqual(info["schema"], "IFC4")
            self.assertEqual(info["missing_elements"], 0)
            f = ifcopenshell.open(str(d / "out.ifc"))
            self.assertEqual(len(f.by_type("IfcRelSequence")), len(self.deps))
            got = {t.Identification: t.TaskTime.ScheduleStart[:10] for t in f.by_type("IfcTask")}
            want = {r.id: r.start_date.strftime("%Y-%m-%d") for r in s.itertuples()}
            self.assertEqual(got, want)


if __name__ == "__main__":
    unittest.main()
