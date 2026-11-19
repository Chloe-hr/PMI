"""Controlled fixture coverage for the Stage 5.1 importer."""

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import ifcopenshell
import ifcopenshell.guid
from jsonschema import Draft202012Validator, FormatChecker

from pmi_core.adapters.ifc import import_ifc


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data/processed/ifc4d/stage3_8b_v1/SYN-BLD-001-V0/as_provided.ifc"


class ImportTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "sample.ifc"
        self.model = ifcopenshell.file(schema="IFC4")
        self.project = self.root("IfcProject", "Controlled project")
        self.storey = self.root("IfcBuildingStorey", "Ground")
        self.aggregate(self.project, self.storey)
        self.wall = self.root("IfcWallStandardCase", "Wall")
        self.wall.ObjectType = "Cast in place"
        self.wall.PredefinedType = "SOLIDWALL"
        self.root(
            "IfcRelContainedInSpatialStructure", "Location",
            RelatedElements=[self.wall], RelatingStructure=self.storey,
        )
        self.project.UnitsInContext = self.model.create_entity("IfcUnitAssignment", Units=[
            self.si("LENGTHUNIT", "METRE", "MILLI"),
            self.si("AREAUNIT", "SQUARE_METRE", "MILLI"),
            self.si("VOLUMEUNIT", "CUBIC_METRE", "MILLI"),
            self.si("MASSUNIT", "GRAM", "KILO"),
        ])

    def root(self, class_name, name, **attrs):
        return self.model.create_entity(class_name, GlobalId=ifcopenshell.guid.new(), Name=name, **attrs)

    def si(self, dimension, name, prefix=None):
        return self.model.create_entity("IfcSIUnit", UnitType=dimension, Name=name, Prefix=prefix)

    def aggregate(self, parent, child):
        self.root("IfcRelAggregates", "Parts", RelatingObject=parent, RelatedObjects=[child])

    def quantity_set(self, entity, *quantities, method=None):
        qset = self.root("IfcElementQuantity", "Qto_TestBaseQuantities", Quantities=quantities, MethodOfMeasurement=method)
        self.root("IfcRelDefinesByProperties", "Quantities", RelatedObjects=[entity], RelatingPropertyDefinition=qset)

    def load(self, **context):
        self.model.write(self.path)
        return import_ifc(self.path, project_id="controlled", **context)

    def test_controlled_ifc_is_immutable_and_canonical(self):
        path = SYNTHETIC
        expected = sha256(path.read_bytes()).hexdigest()
        result = import_ifc(path, project_id="fixture")
        self.assertTrue(result.is_valid, result.issues)
        self.assertFalse(result.elements)  # This legacy fixture models its objects as proxies.
        self.assertIn("NO_SUPPORTED_ELEMENTS", {issue.code for issue in result.issues})
        self.assertEqual(result.model_version.sha256, expected)
        self.assertEqual(result, import_ifc(path, project_id="fixture"))
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), expected)
        schema_path = ROOT / "research/architecture/stage5_0/canonical_schemas.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        validator.check_schema(schema)
        bundle = result.canonical_bundle(imported_at=datetime(2026, 11, 19, tzinfo=UTC))
        validator.validate(bundle)
        controlled_bundle = self.load().canonical_bundle(imported_at=datetime(2026, 11, 19, tzinfo=UTC))
        validator.validate(controlled_bundle)
        evidence = {row.id for row in result.evidence}
        for row in (*result.elements, *result.spatial_elements, *result.quantities, *result.materials):
            self.assertLessEqual(set(row.evidence_ids), evidence)
        spatial = {row.id for row in result.spatial_elements}
        self.assertLessEqual({row.container_id for row in result.elements if row.container_id}, spatial)
        with self.assertRaises(ValueError):
            result.canonical_bundle(imported_at=datetime(2026, 11, 19))

    def test_subtypes_nested_spatial_context_and_version_scope(self):
        child = self.root("IfcReinforcingBar", "Explicit rebar")
        self.aggregate(self.wall, child)
        for class_name in ("IfcFooting", "IfcColumn", "IfcBeam", "IfcSlab"):
            self.root(class_name, class_name)
        first = self.load(namespace="main")
        self.assertEqual(first.source_project_global_id, self.project.GlobalId)
        by_guid = {row.global_id: row for row in first.elements}
        self.assertEqual(len(by_guid), 6)
        wall = by_guid[self.wall.GlobalId]
        rebar = by_guid[child.GlobalId]
        self.assertEqual(wall.ifc_class, "IfcWallStandardCase")
        self.assertEqual(wall.name, "Wall")
        self.assertEqual(wall.object_type, "Cast in place")
        self.assertEqual(wall.predefined_type, "SOLIDWALL")
        self.assertEqual(wall.container_id, first.spatial_elements[0].id)
        self.assertEqual(rebar.container_id, wall.container_id)
        self.wall.Name = "Revised wall"
        revised = self.load(namespace="main", parent_id=first.model_version.id)
        new_wall = next(row for row in revised.elements if row.global_id == wall.global_id)
        self.assertNotEqual(new_wall.id, wall.id)
        self.assertEqual(revised.model_version.parent_id, first.model_version.id)

    def test_squared_cubed_units_and_imperial_override(self):
        cubic_foot = self.model.create_entity(
            "IfcConversionBasedUnit", UnitType="VOLUMEUNIT", Name="cubic foot",
            Dimensions=self.model.create_entity("IfcDimensionalExponents", 3, 0, 0, 0, 0, 0, 0),
            ConversionFactor=self.model.create_entity(
                "IfcMeasureWithUnit", self.model.create_entity("IfcVolumeMeasure", 0.028316846592),
                self.si("VOLUMEUNIT", "CUBIC_METRE"),
            ),
        )
        self.quantity_set(
            self.wall,
            self.model.create_entity("IfcQuantityLength", Name="Length", LengthValue=1000.0),
            self.model.create_entity("IfcQuantityArea", Name="NetSideArea", AreaValue=2500000.0),
            self.model.create_entity("IfcQuantityVolume", Name="GrossVolume", VolumeValue=2000000000.0),
            self.model.create_entity("IfcQuantityVolume", Name="NetVolume", Unit=cubic_foot, VolumeValue=10.0),
            self.model.create_entity("IfcQuantityWeight", Name="NetWeight", WeightValue=0.0),
        )
        result = self.load()
        self.assertTrue(result.is_valid, result.issues)
        quantities = {row.basis: row for row in result.quantities}
        self.assertAlmostEqual(quantities["Length"].value, 1.0)
        self.assertAlmostEqual(quantities["net_side_area"].value, 2.5)
        self.assertAlmostEqual(quantities["gross_volume"].value, 2.0)
        self.assertAlmostEqual(quantities["net_volume"].value, 0.28316846592)
        self.assertEqual(quantities["net_volume"].raw_unit, "cubic foot")
        self.assertEqual(quantities["net_mass"].value, 0.0)
        self.assertEqual(quantities["net_mass"].unit, "kg")

    def test_equivalent_and_disputed_candidates(self):
        for value in (1e9, 2e9):
            self.quantity_set(self.wall, self.model.create_entity("IfcQuantityVolume", Name="NetVolume", VolumeValue=value))
        for _ in range(2):
            self.quantity_set(self.wall, self.model.create_entity("IfcQuantityArea", Name="NetArea", AreaValue=1e6))
        self.quantity_set(self.wall, self.model.create_entity(
            "IfcQuantityVolume", Name="GrossVolume", Unit=self.si("AREAUNIT", "SQUARE_METRE"), VolumeValue=20.0,
        ))
        result = self.load()
        self.assertTrue(result.is_valid)
        self.assertEqual(sum(q.status == "accepted" for q in result.quantities), 1)
        self.assertEqual(sum(q.status == "disputed" for q in result.quantities), 3)
        self.assertEqual(sum(i.code == "DISPUTED_QUANTITY" for i in result.issues), 3)

    def test_missing_units_and_incompatible_measurement_methods(self):
        assignment = self.project.UnitsInContext
        assignment.Units = [unit for unit in assignment.Units if unit.UnitType != "VOLUMEUNIT"]
        self.quantity_set(self.wall, self.model.create_entity(
            "IfcQuantityVolume", Name="NetVolume", VolumeValue=1e9,
        ))
        for method in ("Measured to face", "Measured to centerline"):
            self.quantity_set(self.wall, self.model.create_entity(
                "IfcQuantityArea", Name="NetArea", AreaValue=1e6,
            ), method=method)
        result = self.load()
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.quantities), 3)
        self.assertTrue(all(row.status == "disputed" for row in result.quantities))
        volume = next(row for row in result.quantities if row.kind == "volume")
        self.assertIsNone(volume.value)
        self.assertIn("Project unit", volume.reason)

    def test_material_layer_scope_and_missing_values(self):
        layers = [
            self.model.create_entity(
                "IfcMaterialLayer", Material=self.model.create_entity("IfcMaterial", Name=name), LayerThickness=thickness,
            )
            for name, thickness in (("Concrete", 200.0), ("Insulation", 80.0))
        ]
        selection = self.model.create_entity("IfcMaterialLayerSet", MaterialLayers=layers)
        wall_type = self.root("IfcWallType", "Type", PredefinedType="SOLIDWALL")
        self.root("IfcRelDefinesByType", "Type", RelatedObjects=[self.wall], RelatingType=wall_type)
        self.root("IfcRelAssociatesMaterial", "Material", RelatedObjects=[wall_type], RelatingMaterial=selection)
        result = self.load()
        self.assertEqual([row.name for row in result.materials], ["Concrete", "Insulation"])
        self.assertTrue(all(row.basis == "type_layer" and row.fraction is None for row in result.materials))
        self.assertIn("MISSING_QUANTITIES", {issue.code for issue in result.issues})
        self.assertEqual(result.quantities, ())

    def test_duplicate_and_invalid_id_rejected(self):
        second = self.root("IfcColumn", "Duplicate")
        second.GlobalId = self.wall.GlobalId
        invalid = self.root("IfcBeam", "Invalid ID")
        invalid.GlobalId = "bad"
        result = self.load()
        self.assertFalse(result.is_valid)
        self.assertEqual(result.elements, ())
        codes = {issue.code for issue in result.issues}
        self.assertTrue({"DUPLICATE_GLOBAL_ID", "INVALID_GLOBAL_ID"} <= codes)

    def test_missing_invalid_and_unsupported_inputs(self):
        self.assertEqual(import_ifc(self.path, project_id="fixture").issues[0].code, "SOURCE_NOT_FOUND")
        self.assertEqual(import_ifc(self.path.parent, project_id="fixture").issues[0].code, "SOURCE_NOT_FILE")
        self.path.write_text("not IFC", encoding="ascii")
        self.assertEqual(import_ifc(self.path, project_id="fixture").issues[0].code, "INVALID_IFC")
        self.assertEqual(import_ifc(self.path, project_id="").issues[0].code, "INVALID_IMPORT_CONTEXT")
        self.model.write(self.path)
        complete = self.path.read_bytes()
        self.path.write_bytes(complete.split(b"END-ISO-10303-21;")[0])
        self.assertEqual(import_ifc(self.path, project_id="fixture").issues[0].code, "INVALID_IFC")
        malformed = complete.rsplit(b"ENDSEC;", 1)
        self.path.write_bytes(b"#99999=IFCINVALID();\nENDSEC;".join(malformed))
        self.assertFalse(import_ifc(self.path, project_id="fixture").is_valid)
        ifcopenshell.file(schema="IFC4X3_ADD2").write(self.path)
        self.assertEqual(import_ifc(self.path, project_id="fixture").issues[0].code, "UNSUPPORTED_SCHEMA")


if __name__ == "__main__":
    unittest.main()
