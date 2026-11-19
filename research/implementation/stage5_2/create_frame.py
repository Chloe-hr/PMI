"""Generate the Stage 5.2A synthetic concrete frame IFC."""

import argparse
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import ifcopenshell
from ifcopenshell.api import run
from ifcopenshell import guid


def create_frame(path):
    model = ifcopenshell.file(schema="IFC4")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="Controlled frame")
    run("unit.assign_unit", model)
    context = run("context.add_context", model, context_type="Model")
    body = run("context.add_context", model, context_type="Model", parent=context,
               context_identifier="Body", target_view="MODEL_VIEW")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Frame level")
    run("aggregate.assign_object", model, products=[storey], relating_object=project)
    material = run("material.add_material", model, name="Cast-in-place concrete")
    for label, dims, origin in (
        ("Column", (0.4, 0.4, 3.0), (0.0, 0.0, 0.0)),
        ("Beam", (4.0, 0.4, 0.5), (0.0, 0.0, 3.0)),
        ("Slab", (4.0, 3.0, 0.2), (0.0, 0.0, 3.5)),
    ):
        element = run("root.create_entity", model, ifc_class=f"Ifc{label}", name=label)
        run("spatial.assign_container", model, products=[element], relating_structure=storey)
        run("material.assign_material", model, products=[element], material=material)
        length, width, height = dims
        shape = run("geometry.add_wall_representation", model, context=body,
                    length=length, thickness=width, height=height)
        run("geometry.assign_representation", model, product=element, representation=shape)
        placement = model.create_entity("IfcAxis2Placement3D", Location=model.create_entity(
            "IfcCartesianPoint", Coordinates=tuple(v * 1000 for v in origin)))
        element.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=placement)
        quantities = run("pset.add_qto", model, product=element, name=f"Qto_{label}BaseQuantities")
        run("pset.edit_qto", model, qto=quantities, properties={
            "NetVolume": length * width * height,
            "GrossSurfaceArea": 2 * (length * width + length * height + width * height),
        })
    for entity in model.by_type("IfcRoot"):
        entity.GlobalId = guid.compress(uuid5(NAMESPACE_URL, f"pmi-stage52-frame/{entity.id()}").hex)
    model.header.file_name.time_stamp = "2026-11-19T00:00:00"
    model.header.file_name.name = "controlled_frame.ifc"
    model.write(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a fresh fixture path.")
    create_frame(args.output)
