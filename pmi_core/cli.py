"""Export local IFC extraction evidence as JSON and CSV."""

import argparse
import csv
from dataclasses import asdict, fields
import json
from pathlib import Path

from pmi_core.adapters.ifc import import_ifc
from pmi_core.schemas.bim import BIMElement, EvidenceProvenance, GeometryAssessment, Issue, MaterialRecord, QuantityRecord
from pmi_core.validation.readiness import Readiness, assess_readiness


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("import-ifc", "build-construction"):
        command = commands.add_parser(name)
        command.add_argument("--input", required=True, type=Path)
        command.add_argument("--project-id", required=True)
        command.add_argument("--output", required=True, type=Path)
        command.add_argument("--policy", choices=("strict", "exploratory"), default="strict")
        command.add_argument("--geometry", action="store_true")
        if name == "build-construction":
            command.add_argument("--library", type=Path)
    args = parser.parse_args(argv)
    result = import_ifc(args.input, project_id=args.project_id, policy=args.policy, geometry=args.geometry)
    readiness = tuple(assess_readiness(result))
    if args.command == "build-construction":
        from pmi_core.construction.engine import build_construction
        from pmi_core.construction.export import export_construction
        from pmi_core.construction.library import DEFAULT_LIBRARY, load_library

        construction = build_construction(result, load_library(args.library or DEFAULT_LIBRARY))
    args.output.mkdir(parents=True, exist_ok=False)
    bundle = {"contract_version": "5.1.0", "is_valid": result.is_valid,
              **asdict(result), "readiness": [asdict(row) for row in readiness]}
    (args.output / "import.json").write_text(json.dumps(bundle, allow_nan=False, indent=2), encoding="utf8")
    for filename, record_type, rows in (
        ("elements", BIMElement, result.elements), ("spatial", BIMElement, result.spatial_elements),
        ("quantities", QuantityRecord, result.quantities), ("materials", MaterialRecord, result.materials),
        ("evidence", EvidenceProvenance, result.evidence), ("diagnostics", Issue, result.issues),
        ("geometry", GeometryAssessment, result.geometry), ("readiness", Readiness, readiness),
    ):
        with (args.output / f"{filename}.csv").open("w", newline="", encoding="utf8") as handle:
            writer = csv.DictWriter(handle, [field.name for field in fields(record_type)])
            writer.writeheader()
            for row in rows:
                writer.writerow({key: json.dumps(value) if isinstance(value, tuple) else value
                                 for key, value in asdict(row).items()})
    if args.command == "build-construction":
        export_construction(args.output, construction, result.elements)
    return 0 if result.is_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
