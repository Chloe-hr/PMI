"""Stage 5.1 compatibility and geometry regressions."""

from datetime import UTC, datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import ifcopenshell
import ifcopenshell.api
from jsonschema import Draft202012Validator

from pmi_core.adapters.ifc import import_ifc
from pmi_core.cli import main
from pmi_core.validation.readiness import assess_readiness


def api(operation, model, **kwargs):
    return ifcopenshell.api.run(operation, model, **kwargs)


class CompatibilityTests(unittest.TestCase):
    def fixture(self, schema):
        model = ifcopenshell.file(schema=schema)
        if schema == "IFC2X3":
            person = api("owner.add_person", model)
            organisation = api("owner.add_organisation", model)
            user = api("owner.add_person_and_organisation", model, person=person, organisation=organisation)
            application = api("owner.add_application", model)
            import ifcopenshell.api.owner.settings as settings
            for name, value in (("get_user", user), ("get_application", application)):
                self.addCleanup(setattr, settings, name, getattr(settings, name))
                setattr(settings, name, lambda _, value=value: value)
        project = api("root.create_entity", model, ifc_class="IfcProject")
        api("unit.assign_unit", model)
        context = api("context.add_context", model, context_type="Model")
        body = api("context.add_context", model, context_type="Model",
                   context_identifier="Body", target_view="MODEL_VIEW", parent=context)
        storey = api("root.create_entity", model, ifc_class="IfcBuildingStorey")
        api("aggregate.assign_object", model, products=[storey], relating_object=project)
        wall = api("root.create_entity", model, ifc_class="IfcWall", name="Controlled wall")
        api("spatial.assign_container", model, products=[wall], relating_structure=storey)
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return model, body, wall, Path(directory.name) / "sample.ifc"

    def test_ifc2x3_type_material_quantities_and_analytical_geometry(self):
        model, body, wall, path = self.fixture("IFC2X3")
        wall_type = api("root.create_entity", model, ifc_class="IfcWallType", predefined_type="STANDARD")
        api("type.assign_type", model, related_objects=[wall], relating_type=wall_type)
        material = api("material.add_material", model, name="Aerated concrete")
        api("material.assign_material", model, products=[wall_type], material=material)
        qto = api("pset.add_qto", model, product=wall, name="BaseQuantities")
        api("pset.edit_qto", model, qto=qto, properties={"NetVolume": 6.0})
        shape = api("geometry.add_wall_representation", model, context=body, length=3, height=2, thickness=1)
        api("geometry.assign_representation", model, product=wall, representation=shape)
        model.write(path)
        result = import_ifc(path, project_id="controlled", geometry=True)
        self.assertTrue(result.is_valid, result.issues)
        self.assertEqual(result.model_version.ifc_schema, "IFC2X3")
        self.assertIsNotNone(result.elements[0].container_id)
        self.assertEqual(result.materials[0].basis, "type_single")
        self.assertEqual(result.materials[0].classification, "masonry_or_aerated")
        self.assertEqual({(row.basis, row.method, round(row.value, 8)) for row in result.quantities},
                         {("net_volume", "ifc_quantity", 6), ("represented_body_volume", "geometry", 6)})
        ready, = assess_readiness(result)
        self.assertEqual(ready.geometry_status, "valid")
        self.assertFalse(ready.work_item_eligible)
        schema = json.loads(Path("research/implementation/stage5_1/canonical_schemas_5_1.json").read_text())
        bundle = result.canonical_bundle(imported_at=datetime.now(UTC), contract_version="5.1.0")
        Draft202012Validator(schema).validate(bundle)
        self.assertEqual(bundle["BIMElement"][0]["name"], "Controlled wall")

    def test_tessellated_closed_open_and_duplicate_identity(self):
        model, body, wall, path = self.fixture("IFC4")
        other = api("root.create_entity", model, ifc_class="IfcWall")
        other.GlobalId = wall.GlobalId
        points = model.create_entity("IfcCartesianPointList3D",
                                     CoordList=((0., 0., 0.), (1000., 0., 0.), (0., 1000., 0.), (0., 0., 1000.)))
        mesh = model.create_entity("IfcTriangulatedFaceSet", Coordinates=points, Closed=True,
                                   CoordIndex=((1, 3, 2), (1, 2, 4), (1, 4, 3), (2, 3, 4)))
        shape = model.create_entity("IfcShapeRepresentation", ContextOfItems=body,
                                    RepresentationIdentifier="Body", RepresentationType="Tessellation", Items=(mesh,))
        api("geometry.assign_representation", model, product=wall, representation=shape)
        model.write(path)
        self.assertFalse(import_ifc(path, project_id="controlled").is_valid)
        result = import_ifc(path, project_id="controlled", policy="exploratory", geometry=True)
        self.assertTrue(result.is_valid, result.issues)
        self.assertEqual(len({row.id for row in result.elements}), 2)
        self.assertEqual({row.source_step_id for row in result.elements}, {wall.id(), other.id()})
        self.assertTrue(all(not row.identity_eligible for row in assess_readiness(result)))
        self.assertAlmostEqual(result.quantities[0].value, 1 / 6)
        mesh.Closed = False
        model.write(path)
        output = path.parent / "export"
        self.assertEqual(main(["import-ifc", "--input", str(path), "--project-id", "controlled",
                               "--policy", "exploratory", "--geometry", "--output", str(output)]), 0)
        exported = json.loads((output / "import.json").read_text(encoding="utf8"))
        self.assertEqual(exported["geometry"][0]["status"], "invalid")
        self.assertEqual(exported["quantities"], [])


    def test_native_duplicate_step_is_fatal_even_in_exploratory_mode(self):
        model, _, wall, path = self.fixture("IFC4")
        step = model.to_string()
        line = next(line for line in step.splitlines() if line.startswith(f"#{wall.id()}="))
        path.write_text(step.replace(line, f"{line}\n{line}"), encoding="ascii")
        result = import_ifc(path, project_id="controlled", policy="exploratory")
        issue, = [issue for issue in result.issues if issue.code == "DUPLICATE_STEP_ID"]
        self.assertEqual(issue.step_ids, (wall.id(),))
        self.assertEqual(issue.native_severity, "WARNING")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.elements, ())

    def test_property_and_geometry_reconciliation_retains_each_record(self):
        model, body, wall, path = self.fixture("IFC4")
        shape = api("geometry.add_wall_representation", model, context=body, length=3, height=2, thickness=1)
        api("geometry.assign_representation", model, product=wall, representation=shape)
        pset = api("pset.add_pset", model, product=wall, name="ControlledPset")
        api("pset.edit_pset", model, pset=pset, properties={
            "RepresentedBodyVolume": model.create_entity("IfcVolumeMeasure", 5.0),
            "NetVolume": model.create_entity("IfcVolumeMeasure", 6.0),
            "[BaseQuantities[IfcElementQuantity/Exporter]]NetVolume": 6.0,
        })
        model.write(path)
        result = import_ifc(path, project_id="controlled", geometry=True)
        self.assertTrue(result.is_valid, result.issues)
        self.assertEqual({(q.method, q.basis, q.status) for q in result.quantities}, {
            ("geometry", "represented_body_volume", "accepted"),
            ("ifc_property_quantity", "represented_body_volume", "accepted"),
            ("ifc_property_quantity", "net_volume", "accepted"),
            ("ifc_flattened_quantity", "net_volume", "disputed"),
        })
        self.assertEqual(sum(i.code == "GEOMETRY_QUANTITY_MISMATCH" for i in result.issues), 1)
