"""Import local IFC STEP files into deterministic PMI BIM records."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import re
from tempfile import TemporaryDirectory

import ifcopenshell

from pmi_core.bim.elements import extract_elements
from pmi_core.bim.materials import extract_materials
from pmi_core.bim.quantities import extract_quantities, reconcile_body_volume
from pmi_core.schemas.bim import ImportResult, Issue, ModelVersion, stable_id
from pmi_core.validation.bim import Evidence, validate_identity


SUPPORTED_SCHEMAS = frozenset({"IFC2X3", "IFC4"})


def _reject(code, message):
    return ImportResult(None, issues=(Issue("error", code, message),))


def import_ifc(
    path: str | Path, *, project_id: str, namespace: str | None = None, parent_id: str | None = None,
    policy: str = "strict", geometry: bool = False,
) -> ImportResult:
    """Read a single IFC source, preserving its bytes and original GlobalIds."""
    if policy not in ("strict", "exploratory"):
        return _reject("INVALID_IMPORT_CONTEXT", "Choose strict or exploratory import.")
    for name, value in (("project_id", project_id), ("namespace", namespace), ("parent_id", parent_id)):
        if value is None and name != "project_id":
            continue
        if not isinstance(value, str) or not value.strip():
            return _reject("INVALID_IMPORT_CONTEXT", f"{name} must be a nonempty identifier.")
    try:
        source = Path(path).resolve(strict=True)
        if not source.is_file():
            return _reject("SOURCE_NOT_FILE", "The IFC source must be a local regular file.")
    except FileNotFoundError:
        return _reject("SOURCE_NOT_FOUND", "The IFC source does not exist.")
    except (OSError, RuntimeError, ValueError):
        return _reject("SOURCE_UNREADABLE", "The IFC source path cannot be read.")
    if source.suffix.lower() != ".ifc":
        return _reject("UNSUPPORTED_FORMAT", "Supply an uncompressed IFC STEP file with an .ifc suffix.")

    # Hash and parse the same private byte copy, even if the source path is replaced.
    digest = sha256()
    terminator = b"END-ISO-10303-21;"
    tail = b""
    trailing_space = 0
    logger_type = ifcopenshell.ifcopenshell_wrapper.logger
    logger = logger_type()
    logger.verbosity(logger_type.LOG_WARNING)
    logger.output_format(logger_type.FMT_INMEMORY)
    try:
        with TemporaryDirectory(prefix="pmi-ifc-") as folder:
            snapshot = Path(folder) / "snapshot.ifc"
            with source.open("rb") as original, snapshot.open("wb") as copy:
                for chunk in iter(lambda: original.read(1024 * 1024), b""):
                    digest.update(chunk)
                    copy.write(chunk)
                    significant = chunk.rstrip()
                    if significant:
                        separator = b" " * trailing_space
                        tail = (tail + separator + significant[-len(terminator):])[-len(terminator):]
                        trailing_space = len(chunk) - len(significant)
                    else:
                        trailing_space += len(chunk)
                    trailing_space = min(trailing_space, len(terminator))
            if tail != terminator:
                return _reject("INVALID_IFC", "The IFC STEP file has no final END-ISO-10303-21 marker.")
            model = ifcopenshell.open(snapshot, format=".ifc", logger=logger)
    except ifcopenshell.SchemaError as exc:
        return _reject("UNSUPPORTED_SCHEMA", str(exc))
    except ifcopenshell.Error as exc:
        return _reject("INVALID_IFC", str(exc))
    except OSError:
        return _reject("SOURCE_UNREADABLE", "The source or its temporary snapshot cannot be read or written.")

    schema = model.schema_identifier
    if schema not in SUPPORTED_SCHEMAS:
        return _reject("UNSUPPORTED_SCHEMA", f"Unsupported IFC schema: {schema}.")
    issues = []
    for message in logger:
        duplicate = re.fullmatch(r"Overwriting instance with name #(\d+)", message.message)
        if duplicate:
            issues.append(Issue("error", "DUPLICATE_STEP_ID", message.message,
                                (int(duplicate[1]),), native_severity=message.severity_string))
        else:
            severity = "error" if message.severity == logger_type.LOG_ERROR else "warning"
            issues.append(Issue(severity, "IFC_PARSER_DIAGNOSTIC", message.message,
                                native_severity=message.severity_string))
    identity = validate_identity(model)
    recoverable = {"DUPLICATE_GLOBAL_ID"}
    issues.extend(replace(issue, severity="warning") if policy == "exploratory"
                  and issue.code in recoverable else issue for issue in identity)
    if any(issue.severity == "error" for issue in issues):
        return ImportResult(None, issues=tuple(issues))

    project = model.by_type("IfcProject")[0]
    namespace = namespace if namespace is not None else project.GlobalId
    checksum = digest.hexdigest()
    version_id = stable_id(project_id, namespace, checksum)
    if parent_id == version_id:
        return _reject("INVALID_IMPORT_CONTEXT", "A model version cannot be its own parent.")
    evidence = Evidence(version_id, source.as_uri(), checksum)
    version = ModelVersion(
        version_id, (evidence.source_id, evidence.entity(project.id())), project_id, checksum,
        source.as_uri(), namespace, schema, parent_id,
    )
    objects, spatial = extract_elements(model, version_id, evidence, issues, identity)
    if policy == "exploratory":
        issues = [replace(issue, severity="warning")
                  if issue.code == "AMBIGUOUS_CONTAINER" else issue for issue in issues]
    if not objects:
        issues.append(Issue("warning", "NO_SUPPORTED_ELEMENTS", "The IFC contains no supported element occurrences."))
    quantities, materials, geometries = [], [], []
    if geometry:
        from pmi_core.bim.geometry import extract_geometry
    for entity, record in objects:
        authored = extract_quantities(entity, record, project, evidence, issues)
        quantities.extend(authored)
        if geometry:
            assessment, quantity = extract_geometry(entity, record, project, evidence)
            geometries.append(assessment)
            if quantity is not None:
                quantities.append(quantity)
                issues.extend(reconcile_body_volume(authored, quantity, record))
        materials.extend(extract_materials(entity, record, evidence, issues))
    return ImportResult(
        model_version=version,
        elements=tuple(record for _, record in objects),
        spatial_elements=spatial,
        quantities=tuple(quantities),
        materials=tuple(materials),
        evidence=tuple(evidence.records.values()),
        issues=tuple(issues),
        policy=policy,
        geometry=tuple(geometries),
        source_project_global_id=project.GlobalId,
    )
