"""Controlled regression coverage for Stage 5.2A."""

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pmi_core.adapters.ifc import import_ifc
from pmi_core.cli import main
from pmi_core.construction.classification import classify
from pmi_core.construction.dependencies import dependency_issues
from pmi_core.construction.engine import build_construction, catalogue_selection
from pmi_core.construction.library import load_library
from pmi_core.schemas.bim import QuantityRecord

from research.implementation.stage5_2.create_frame import create_frame


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "frame.ifc"
        create_frame(self.path)
        self.result = import_ifc(self.path, project_id="test", geometry=True)
        self.library = load_library()

    def test_library_inventory_and_reference_provenance(self):
        self.assertEqual({name: len(rows) for name, rows in self.library.tables.items()}, {
            "work": 29, "catalogue": 61, "classification": 15, "dependencies": 16,
            "controls": 14, "inputs": 22, "approvals": 75, "quantities": 11,
        })
        data = build_construction(self.result, self.library)
        row = next(row for row in data["catalogue_options"] if row["bcca_code"] == "05HHP00003")
        self.assertEqual(row["work_item"], "COL-CONC")
        self.assertEqual(row["edition"], "BCCA2023_V02")
        self.assertTrue(row["measurement_rule_text"] and row["labour_h_per_unit_by_trade"])
        self.assertFalse(any(row["work_item"] == "CURE" for row in data["catalogue_options"]))

    def test_scope_and_traceability(self):
        self.assertTrue(self.result.is_valid, self.result.issues)
        data = build_construction(self.result, self.library)
        self.assertEqual(len(data["packages"]), 3)
        self.assertEqual(len(data["activities"]), 15)
        self.assertEqual({row["family"] for row in data["packages"]}, {"COL", "BEAM", "SLAB"})
        ids = {row.id for row in self.result.quantities}
        self.assertTrue(all(set(row["quantity_ids"]) <= ids for row in data["activities"]))
        volumes = [row for row in data["quantity_requirements"] if row["basis"] == "material_concrete_volume"]
        self.assertEqual(sorted(round(row["value"], 4) for row in volumes), [0.48, 0.8, 2.4])
        self.assertTrue(all(row["evidence_ids"] for row in volumes))
        self.assertTrue(all(row["status"] == "missing" and row["value"] is None
                            for row in data["quantity_requirements"] if row["unit"] in {"m2", "kg"}))
        self.assertTrue(all(not row["schedulable"] and row["pending_approval_ids"] and row["duration"] is None
                            for row in data["activities"]))
        spatial = {row.id: row for row in self.result.spatial_elements}
        beam = next(row for row in self.result.elements if row.ifc_class == "IfcBeam")
        member = next(row for row in self.result.materials if row.element_id == beam.id)
        self.assertEqual(classify(beam, [replace(member, name="Aerated concrete block")], spatial)["scope"],
                         "classification_only")
        self.assertEqual(classify(replace(beam, name="fund_strook"), [member], spatial)["family"], "FND")
        self.assertEqual(classify(beam, [replace(member, name="C25/30")], spatial)["category"],
                         "concrete_method_unstated")

    def test_conditional_method_and_release_edges(self):
        column = next(row for row in self.result.elements if row.ifc_class == "IfcColumn")
        slab = next(row for row in self.result.elements if row.ifc_class == "IfcSlab")
        data = build_construction(self.result, self.library, sequences={column.id: "overlap"},
                                  slab_on_grade={slab.id: True})
        by_option = {e["option"]: e for e in data["dependencies"] if e["rule_id"] == "DR05"}
        self.assertEqual((by_option["overlap"]["relation"], by_option["overlap"]["state"]), ("SS", "proposed"))
        self.assertEqual(by_option["cage_first"]["state"], "conditional")
        self.assertFalse(any(slab.id in row["element_ids"] and row["work_item"] in {"SLAB-FORM", "FRM-STRIP"}
                             for row in data["activities"]))
        self.assertEqual(data["graph_issues"], [])
        self.assertTrue(all(row["lag"] is None for row in data["dependencies"]))
        edge = {"predecessor_id": "a", "successor_id": "b", "relation": "FS", "state": "proposed"}
        reversed_edge = {**edge, "predecessor_id": "b", "successor_id": "a"}
        self.assertEqual({row["code"] for row in dependency_issues(["a", "b"], [
            edge, reversed_edge, {**edge, "relation": "SS"},
        ])}, {"DEPENDENCY_CYCLE", "CONFLICTING_RELATIONSHIPS"})

    def test_double_counting_and_user_evidence(self):
        refs = self.library.tables["catalogue"]
        self.assertIn("DC04", catalogue_selection(
            ["SLAB-COMPOSITE", "SLAB-CONC"], [("SLAB-COMPOSITE", refs["SLAB-COMPOSITE", "05FUW80040"])]))
        self.assertIn("DC01", catalogue_selection(
            ["FND-FORM", "FRM-STRIP"], [("FND-FORM", refs["FND-FORM", "03ERM00001"])]))
        self.assertIn("DC03", catalogue_selection(["CURE"], []))
        column = next(row for row in self.result.elements if row.ifc_class == "IfcColumn")
        mass = QuantityRecord("bar-schedule", ("fixture-schedule",), column.id, "mass",
                              "reinforcement_mass", "user_provided", "accepted", 42, "kg")
        data = build_construction(self.result, self.library, provided_quantities=[mass])
        rebar = next(row for row in data["activities"] if row["work_item"] == "COL-REBAR")
        self.assertEqual(rebar["quantity_ids"], [mass.id])
        self.assertFalse(rebar["schedulable"])
        selected = build_construction(self.result, self.library, catalogue_choices={
            column.id: {"COL-CONC": "05HHP00003"},
        })
        self.assertEqual([row["bcca_code"] for row in selected["catalogue_options"]
                          if row["allocation_status"] == "selected_for_review"], ["05HHP00003"])
        with self.assertRaisesRegex(ValueError, "DC03"):
            build_construction(self.result, self.library, catalogue_choices={column.id: {"CURE": "CURE"}})


    def test_cli_exports_and_exploratory_gate(self):
        folder = self.path.parent / "export"
        self.assertEqual(main(["build-construction", "--input", str(self.path), "--project-id", "test",
                               "--policy", "exploratory", "--output", str(folder)]), 0)
        data = json.loads((folder / "construction.json").read_text(encoding="utf8"))
        self.assertTrue(all("exploratory_import" in row["blockers"] for row in data["activities"]))
        self.assertTrue((folder / "elements.csv").is_file())
        self.assertIn("Dependency graph", (folder / "report.html").read_text(encoding="utf8"))
