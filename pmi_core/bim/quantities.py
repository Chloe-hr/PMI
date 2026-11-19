"""Read authored occurrence quantities and normalize supported units to SI."""

from collections import defaultdict
from dataclasses import dataclass
from math import isclose, isfinite
import re

from pmi_core.schemas.bim import Issue, QuantityRecord, stable_id


# IFC measure attribute, dimension, IFC unit type, SI name, PMI unit, power.
MEASURES = {
    "IfcQuantityLength": ("LengthValue", "length", "LENGTHUNIT", "METRE", "m", 1),
    "IfcQuantityArea": ("AreaValue", "area", "AREAUNIT", "SQUARE_METRE", "m2", 2),
    "IfcQuantityVolume": ("VolumeValue", "volume", "VOLUMEUNIT", "CUBIC_METRE", "m3", 3),
    "IfcQuantityWeight": ("WeightValue", "mass", "MASSUNIT", "GRAM", "kg", 1),
    "IfcQuantityCount": ("CountValue", "count", None, None, "each", 0),
}
PREFIX = {
    None: 1, "EXA": 1e18, "PETA": 1e15, "TERA": 1e12, "GIGA": 1e9, "MEGA": 1e6,
    "KILO": 1e3, "HECTO": 1e2, "DECA": 1e1, "DECI": 1e-1,
    "CENTI": 1e-2, "MILLI": 1e-3, "MICRO": 1e-6, "NANO": 1e-9,
    "PICO": 1e-12, "FEMTO": 1e-15, "ATTO": 1e-18,
}
COMMON_BASIS = {
    "volume": "unspecified_volume",
    "area": "unspecified_area",
    "representedbodyvolume": "represented_body_volume",
    "materialconcretevolume": "material_concrete_volume",
    "netvolume": "net_volume",
    "grossvolume": "gross_volume",
    "netsidearea": "net_side_area",
    "grosssidearea": "gross_side_area",
    "netsurfacearea": "net_surface_area",
    "grosssurfacearea": "gross_surface_area",
    "netarea": "net_area",
    "grossarea": "gross_area",
    "netweight": "net_mass",
    "grossweight": "gross_mass",
    "netmass": "net_mass",
    "grossmass": "gross_mass",
    "formworkcontactarea": "formwork_contact_area",
}


@dataclass(frozen=True, slots=True)
class _Candidate:
    step_id: int
    evidence_ids: tuple[str, ...]
    raw: float | None
    raw_unit: str | None
    value: float | None
    factor: float | None
    reason: str | None
    canonical_unit: str
    measurement_method: str


def _label(unit):
    prefix = getattr(unit, "Prefix", None)
    return " ".join(value for value in (prefix, getattr(unit, "Name", None)) if value) or unit.is_a()


def _factor(unit, kind, type_name, si_name, power, visited=frozenset()):
    if unit.id() in visited or getattr(unit, "UnitType", None) != type_name:
        raise ValueError("Unit chain is cyclic or dimensionally incompatible.")
    if unit.is_a("IfcSIUnit") and unit.Name == si_name and unit.Prefix in PREFIX:
        return PREFIX[unit.Prefix] ** power / (1000 if kind == "mass" else 1), (unit.id(),)
    if unit.is_a() == "IfcConversionBasedUnit":
        dimensions = unit.Dimensions
        expected = (power, 0, 0, 0, 0, 0, 0) if kind != "mass" else (0, 1, 0, 0, 0, 0, 0)
        if not dimensions or tuple(dimensions) != expected:
            raise ValueError("Conversion unit has incompatible dimensional exponents.")
        conversion = unit.ConversionFactor
        if conversion is None or conversion.ValueComponent is None or conversion.UnitComponent is None:
            raise ValueError("Conversion factor is incomplete.")
        if conversion.ValueComponent.is_a() != {
            "length": "IfcLengthMeasure", "area": "IfcAreaMeasure",
            "volume": "IfcVolumeMeasure", "mass": "IfcMassMeasure",
        }[kind] and conversion.ValueComponent.is_a() not in ("IfcReal", "IfcPositiveRatioMeasure", "IfcRatioMeasure"):
            raise ValueError("Conversion factor measure is incompatible.")
        multiplier = conversion.ValueComponent.wrappedValue
        if not isinstance(multiplier, (int, float)) or not isfinite(multiplier) or multiplier <= 0:
            raise ValueError("Conversion factor is invalid.")
        factor, step_ids = _factor(conversion.UnitComponent, kind, type_name, si_name, power, visited | {unit.id()})
        return multiplier * factor, (unit.id(), dimensions.id(), conversion.id(), *step_ids)
    raise ValueError("Unsupported IFC unit.")


PROPERTY_MEASURES = {
    "IfcLengthMeasure": "IfcQuantityLength",
    "IfcAreaMeasure": "IfcQuantityArea",
    "IfcVolumeMeasure": "IfcQuantityVolume",
    "IfcMassMeasure": "IfcQuantityWeight",
    "IfcCountMeasure": "IfcQuantityCount",
}
FLATTENED = re.compile(r"^\[.*\[IfcElementQuantity/[^\]]+\]\](.+)$", re.IGNORECASE)


def _quantity_sets(entity):
    for relation in sorted(entity.IsDefinedBy, key=lambda row: row.id()):
        if not relation.is_a("IfcRelDefinesByProperties"):
            continue
        definition = relation.RelatingPropertyDefinition
        definitions = definition if isinstance(definition, (tuple, list)) else (definition,)
        for qset in definitions:
            if not qset:
                continue
            if qset.is_a("IfcElementQuantity"):
                for row in sorted(qset.Quantities or (), key=lambda item: item.id()):
                    yield relation, qset, row, row.Name, row.is_a(), "ifc_quantity"
            elif qset.is_a("IfcPropertySet"):
                for row in sorted(qset.HasProperties or (), key=lambda item: item.id()):
                    if not row.is_a("IfcPropertySingleValue") or not row.Name:
                        continue
                    match = FLATTENED.fullmatch(row.Name)
                    label = match[1] if match else row.Name
                    if re.sub(r"[ _-]", "", label).casefold() not in COMMON_BASIS and label != "RepresentedBodyVolume":
                        continue
                    measure = row.NominalValue
                    quantity_class = PROPERTY_MEASURES.get(measure.is_a()) if measure is not None else None
                    method = "ifc_flattened_quantity" if match else "ifc_property_quantity"
                    if quantity_class is None:
                        normalized = re.sub(r"[ _-]", "", label).casefold()
                        basis = COMMON_BASIS.get(normalized, label)
                        dimension = next((kind for kind in ("volume", "area", "mass") if basis.endswith(kind)), None)
                        quantity_class = next((key for key, spec in MEASURES.items() if spec[1] == dimension), None)
                    yield relation, qset, row, label, quantity_class, method


def extract_quantities(entity, record, project, evidence, issues):
    groups = defaultdict(list)
    assignment = project.UnitsInContext
    for relation, qset, quantity, name, class_name, method in _quantity_sets(entity):
        spec = MEASURES.get(class_name)
        if not spec:
            issues.append(Issue(
                "warning", "UNSUPPORTED_QUANTITY", f"Unsupported quantity class {quantity.is_a()}.",
                (qset.id(), quantity.id()), record.id,
            ))
            continue
        attribute, kind, type_name, si, canonical_unit, power = spec
        if not name or not name.strip():
            issues.append(Issue("warning", "UNNAMED_QUANTITY", "Quantity has no measurement name.", (quantity.id(),), record.id))
            continue
        basis = COMMON_BASIS.get(re.sub(r"[ _-]", "", name).casefold(), name.strip())
        if method == "ifc_quantity":
            raw = getattr(quantity, attribute)
            typed = True
        else:
            nominal = quantity.NominalValue
            raw = nominal.wrappedValue if nominal is not None else None
            typed = nominal is not None and PROPERTY_MEASURES.get(nominal.is_a()) == class_name
        valid_raw = isinstance(raw, (int, float)) and isfinite(raw) and raw >= 0
        unit = quantity.Unit
        source_unit = _label(unit) if unit else None
        inputs = [evidence.entity(relation.id()), evidence.entity(qset.id()), evidence.entity(quantity.id())]
        factor, value, reason = None, None, None
        try:
            expected_kind = next((dimension for dimension in ("volume", "area", "mass")
                                  if basis.endswith("_" + dimension)), None)
            if expected_kind and kind != expected_kind:
                raise ValueError("Quantity dimension conflicts with its measurement name.")
            if not typed and (unit is None or (nominal is not None and nominal.is_a() not in {
                    "IfcReal", "IfcInteger", "IfcNumericMeasure"
                })):
                raise ValueError("Property has no typed measure or explicit dimensional unit.")
            if not valid_raw:
                raise ValueError("Quantity value is missing, negative or nonfinite.")
            if type_name:
                if unit is None:
                    units = [
                        candidate for candidate in (assignment.Units if assignment else ())
                        if getattr(candidate, "UnitType", None) == type_name
                    ]
                    if len(units) != 1:
                        raise ValueError("Project unit is missing or ambiguous.")
                    unit = units[0]
                    inputs.append(evidence.entity(assignment.id()))
                source_unit = _label(unit)
                inputs.append(evidence.entity(unit.id()))
                factor, unit_steps = _factor(unit, kind, type_name, si, power)
                inputs.extend(evidence.entity(step) for step in unit_steps[1:])
            elif unit is None:
                factor, source_unit = 1, "each"
            else:
                raise ValueError("An IFC quantity count must be dimensionless in this adapter.")
            if not isfinite(factor) or factor <= 0:
                raise ValueError("Unit conversion factor is nonfinite or nonpositive.")
            value = raw * factor
            if not isfinite(value):
                raise ValueError("Normalized value is nonfinite.")
        except (ValueError, RecursionError) as exc:
            reason = str(exc)
            value = None
        groups[kind, basis, method].append(_Candidate(
            quantity.id(), tuple(inputs), raw if valid_raw else None, source_unit, value, factor,
            reason, canonical_unit, (getattr(qset, "MethodOfMeasurement", None) or "").strip(),
        ))

    rows = []
    if not groups:
        issues.append(Issue("warning", "MISSING_QUANTITIES", "No supported occurrence quantity entities or properties.", (entity.id(),), record.id))
    for (kind, basis, method), candidates in sorted(groups.items()):
        key = stable_id(record.id, "quantity", kind, basis,
                        *(() if method == "ifc_quantity" else (method,)))
        valid = [row for row in candidates if row.value is not None]
        if valid:
            first = valid[0]
            conflict = len(valid) != len(candidates) or any(
                row.measurement_method != first.measurement_method
                or not isclose(row.value, first.value, rel_tol=1e-9, abs_tol=1e-12)
                for row in valid
            )
        else:
            conflict = False
        if conflict or not valid:
            for row in candidates:
                message = (
                    "Conflicting authored candidates on the same measurement basis."
                    if conflict else row.reason or "Invalid authored quantity."
                )
                identifier = stable_id(key, str(row.step_id), *row.evidence_ids)
                issues.append(Issue("warning", "DISPUTED_QUANTITY", message, (row.step_id,), record.id))
                rows.append(QuantityRecord(
                    identifier, row.evidence_ids, record.id, kind, basis, method, "disputed",
                    row.value, row.canonical_unit if row.value is not None else None,
                    row.raw, row.raw_unit, message, row.measurement_method or None,
                ))
            continue
        inputs = tuple(dict.fromkeys(item for candidate in valid for item in candidate.evidence_ids))
        formula = (
            f"First equivalent authored candidate × {first.factor:.17g}; "
            f"basis={basis}; measurement method={first.measurement_method or 'unspecified'}"
        )
        derivation = evidence.derive(key, formula, inputs)
        rows.append(QuantityRecord(
            key, (derivation,), record.id, kind, basis, method, "accepted",
            first.value, first.canonical_unit, first.raw, first.raw_unit,
            measurement_method=first.measurement_method or None,
        ))
    return rows


def reconcile_body_volume(authored, geometry, element):
    """Compare only quantities explicitly authored on the represented-body basis."""
    issues = []
    for row in authored:
        if (row.kind, row.basis, row.unit, row.status) != (
            geometry.kind, geometry.basis, geometry.unit, "accepted"
        ):
            continue
        agrees = isclose(row.value, geometry.value, rel_tol=1e-6, abs_tol=1e-9)
        issues.append(Issue(
            "info" if agrees else "warning",
            "GEOMETRY_QUANTITY_AGREEMENT" if agrees else "GEOMETRY_QUANTITY_MISMATCH",
            f"Compared {row.id} ({row.value:.9g}) and {geometry.id} ({geometry.value:.9g}) in {row.unit}.",
            (element.source_step_id,), element.id,
        ))
    return issues
