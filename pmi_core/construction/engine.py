"""Generate evidence-linked construction candidates from one IFC model version."""

from collections import defaultdict
from dataclasses import asdict
from math import isfinite

from pmi_core.construction.classification import classify
from pmi_core.construction.dependencies import dependency_issues, package_dependencies
from pmi_core.schemas.bim import stable_id
from pmi_core.validation.readiness import assess_readiness


# Quantity criteria are deliberately narrower than the library's engineering options.
OPERATIONS = {
    "rebar": ("REBAR", "productive", "reinforcement_mass", "kg", ("UI09",)),
    "form": ("FORM", "productive", "formwork_contact_area", "m2", ("UI10", "UI11")),
    "place": ("CONC", "productive", "material_concrete_volume", "m3", ("UI08", "UI17")),
    "cure": ("CURE", "elapsed_hold", None, None, ("UI12",)),
    "strip": ("FRM-STRIP", "productive", "formwork_contact_area", "m2", ("UI13",)),
}


def _measurement(operation, rows, single_material):
    _, _, basis, unit, _ = OPERATIONS[operation]
    if basis is None:
        return "not_required", []
    compatible = {basis}
    if operation == "place" and single_material:
        compatible.add("net_volume")
    allowed = {"user_provided"}
    if operation == "place":
        allowed.update(("ifc_quantity", "ifc_property_quantity"))
    candidates = [row for row in rows if row.basis in compatible and row.method in allowed
                  and (row.unit == unit or row.status == "disputed") and row.evidence_ids]
    if not candidates:
        return "missing", []
    if len(candidates) != 1 or candidates[0].status != "accepted":
        return "review_required", candidates
    value = candidates[0].value
    if value is None or not isfinite(value) or value <= 0:
        return "review_required", candidates
    return "available", candidates


def catalogue_selection(activity_codes, references):
    """Return blockers for a proposed set of distinct cost mappings in one element scope."""
    flags = {code: row for code, row in references}
    problems = []
    if len(flags) != len(references):
        problems.append("duplicate_catalogue_allocation")
    if "CURE" in activity_codes:
        problems.append("DC03")
    if "FRM-STRIP" in activity_codes and any(
        row["includes_stripping"] == "True" for code, row in flags.items() if code != "FRM-STRIP"
    ):
        problems.append("DC01")
    if "SLAB-COMPOSITE" in activity_codes and (
        {"SLAB-REBAR", "SLAB-FORM", "SLAB-CONC", "FRM-STRIP"} & set(activity_codes)
    ):
        problems.append("DC04")
    return problems


def validate_catalogue_choices(choices, offered):
    """Flag compatible reference choices for review without creating cost allocations."""
    selected = []
    for item, code in choices.items():
        if item == "CURE":
            raise ValueError("DC03: Curing is included in placement and has no standalone price.")
        if code not in offered.get(item, {}):
            raise ValueError(f"Catalogue reference {code} is unavailable for {item}.")
        selected.append((item, offered[item][code]))
    conflicts = catalogue_selection(choices, selected)
    if conflicts:
        raise ValueError("Conflicting catalogue choices: " + ", ".join(conflicts))
    for _, row in selected:
        row["allocation_status"] = "selected_for_review"


def build_construction(result, library, *, sequences=None, slab_on_grade=None, provided_quantities=(),
                       catalogue_choices=None):
    """Return candidate records. The source approvals are pending for every project."""
    sequences, slab_on_grade = sequences or {}, slab_on_grade or {}
    data = {
        "version": "5.2A", "library_version": library.version, "library_hashes": dict(library.hashes),
        "import_valid": result.is_valid, "model_version_id": result.model_version.id if result.model_version else None,
        "policy": result.policy, "release_status": "engineering_review_required",
        **{key: [] for key in ("classifications", "packages", "activities", "dependencies",
                              "quantity_requirements", "catalogue_options", "graph_issues")},
    }
    data["approval_register"] = [dict(row) for row in library.tables["approvals"].values()]
    data["input_register"] = [dict(row) for row in library.tables["inputs"].values()]
    data["double_counting_controls"] = [dict(row) for row in library.tables["controls"].values()]
    data["dependency_library"] = [dict(row) for row in library.tables["dependencies"].values()]
    data["classification_library"] = [dict(row) for row in library.tables["classification"].values()]
    data["provided_quantities"] = []
    if not result.is_valid:
        return data

    remaining_choices = dict(catalogue_choices or {})

    materials, quantities, refs, approvals = (defaultdict(list) for _ in range(4))
    spatial = {element.id: element for element in result.spatial_elements}
    identity = {row.element_id: row.identity_eligible for row in assess_readiness(result)}
    for row in result.materials:
        materials[row.element_id].append(row)
    for row in result.quantities:
        quantities[row.element_id].append(row)
    quantity_ids = {row.id for row in result.quantities}
    for row in provided_quantities:
        if (row.element_id not in identity or row.id in quantity_ids or row.method != "user_provided"
                or not row.evidence_ids or row.status != "accepted" or row.value is None
                or not isfinite(row.value) or row.value <= 0):
            raise ValueError("Provided quantities must be unique positive user evidence for this model.")
        quantity_ids.add(row.id)
        quantities[row.element_id].append(row)
        data["provided_quantities"].append(asdict(row))
    for element_id, method in sequences.items():
        if element_id not in identity or method not in {"cage_first", "overlap", "formwork_first"}:
            raise ValueError("Invalid element sequence selection.")
    for element_id, on_grade in slab_on_grade.items():
        if element_id not in identity or type(on_grade) is not bool:
            raise ValueError("Invalid slab-on-grade selection.")
    for (activity_code, _), row in library.tables["catalogue"].items():
        refs[activity_code].append(row)
    for approval_id, row in library.tables["approvals"].items():
        approvals[row["item"]].append(approval_id)

    for element in result.elements:
        members = materials[element.id]
        classification = classify(element, members, spatial)
        classification["element_evidence_ids"] = list(element.evidence_ids)
        classification["material_evidence_ids"] = list(dict.fromkeys(
            evidence for member in members for evidence in member.evidence_ids))
        classification["approval_ids"] = [
            approval for rule in classification["rule_ids"] for approval in approvals[rule]]
        classification["review_input_ids"] = (
            ["UI07"] if "CR11" in classification["rule_ids"] else
            ["UI06"] if classification["category"] in {"concrete_method_unstated", "no_material",
                                                       "mixed_material_cast_in_place_candidate"} else [])
        data["classifications"].append(classification)
        if classification["scope"] != "candidate":
            continue
        family = classification["family"]
        choices = remaining_choices.pop(element.id, {})
        package_id = stable_id(element.id, "stage5.2", family)
        on_grade = slab_on_grade.get(element.id) if family == "SLAB" else False
        active = [op for op in OPERATIONS if on_grade is not True or op not in {"form", "strip"}]
        activity_ids = {op: stable_id(package_id, op) for op in active}
        data["packages"].append({
            "id": package_id, "element_ids": [element.id], "storey_id": classification["storey_id"],
            "family": family, "activity_ids": list(activity_ids.values()), "status": "candidate",
            "independent_pour_scope": None,
        })
        edges = package_dependencies(activity_ids, family, library, sequences.get(element.id), on_grade)
        data["dependencies"].extend(edges)
        offered = {}
        for op in active:
            suffix, kind, basis, unit, input_ids = OPERATIONS[op]
            work_id = suffix if op in {"cure", "strip"} else f"{family}-{suffix}"
            work = library.tables["work"][work_id]
            activity_id = activity_ids[op]
            if family == "SLAB" and on_grade is None and op in {"form", "strip"}:
                input_ids += ("UI21",)
            if work_id == "COL-CONC":
                input_ids += ("UI22",)
            single = len(members) == 1 and members[0].basis.endswith("_single")
            status, candidates = _measurement(op, quantities[element.id], single)
            quantity_refs = [row.id for row in candidates]
            quantity_record = {
                "activity_id": activity_id, "element_id": element.id, "work_item": work_id,
                "requirement": work["required_quantity"], "basis": basis, "unit": unit,
                "status": status, "quantity_ids": quantity_refs,
                "evidence_ids": list(dict.fromkeys(e for row in candidates for e in row.evidence_ids)),
                "value": candidates[0].value if status == "available" else None,
            }
            data["quantity_requirements"].append(quantity_record)
            related = [edge for edge in edges if activity_id in (edge["predecessor_id"], edge["successor_id"])]
            dependency_ids = sorted({edge["rule_id"] for edge in related})
            control_ids = {
                "rebar": ["DC05"], "form": ["DC02"], "place": ["DC03", "DC08"],
                "cure": ["DC03"], "strip": ["DC01", "DC02"],
            }[op]
            if family == "SLAB":
                control_ids.append("DC04")
            if work_id in {"BEAM-CONC", "SLAB-CONC"}:
                control_ids.append("DC06")
            if work_id in {"COL-CONC", "SLAB-CONC"}:
                control_ids.append("DC07")
            pending = classification["approval_ids"] + [
                approval for key in [work_id, *dependency_ids, *control_ids] for approval in approvals[key]]
            if op == "place":
                pending.append("AP-TOL")
            blockers = ["engineering_approval_pending", *input_ids]
            if status not in {"available", "not_required"}:
                blockers.append("quantity_" + status)
            if any(edge["option"] for edge in related) and not any(
                edge["option"] and edge["state"] == "proposed" for edge in related
            ):
                blockers.append("construction_sequence_pending")
            if not identity[element.id]:
                blockers.append("bim_identity_or_containment_unresolved")
            if result.policy == "exploratory":
                blockers.append("exploratory_import")
            data["activities"].append({
                "id": activity_id, "package_id": package_id, "element_ids": [element.id],
                "work_item": work_id, "name": work["work_item"], "kind": kind,
                "quantity_ids": quantity_refs, "dependency_rule_ids": dependency_ids,
                "classification_rule_ids": classification["rule_ids"], "control_ids": control_ids,
                "required_input_ids": list(input_ids), "pending_approval_ids": sorted(set(pending)),
                "schedulable": False, "blockers": blockers, "duration": None,
                "cost_treatment": "included_in_placement" if op == "cure" else "reference_candidates_only",
            })
            options = [{
                **dict(row), "activity_id": activity_id, "work_item": work_id,
                "edition": "BCCA2023_V02", "region": "Andalucia", "currency": "EUR",
                "allocation_status": "pending_variant_and_measurement_approval",
            } for row in refs[work_id] if row["bcca_unit"].replace("²", "2") == unit]
            offered[work_id] = {row["bcca_code"]: row for row in options}
            data["catalogue_options"].extend(options)

        if choices:
            validate_catalogue_choices(choices, offered)

    if remaining_choices:
        raise ValueError("Catalogue choice refers to an element without a candidate package.")

    data["graph_issues"] = dependency_issues(
        (row["id"] for row in data["activities"]), data["dependencies"])
    return data
