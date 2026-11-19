"""Assess whether extracted evidence can support downstream use."""

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Readiness:
    element_id: str
    import_valid: bool
    identity_eligible: bool
    containment_resolved: bool
    geometry_status: str
    quantity_status: str
    material_evidence_available: bool
    material_classification_status: str = "unvalidated"
    engineering_validation: str = "pending"
    work_item_eligible: bool = False


def assess_readiness(result):
    duplicates = {step for issue in result.issues if issue.code == "DUPLICATE_GLOBAL_ID"
                  for step in issue.step_ids}
    ambiguous = {issue.element_id for issue in result.issues
                 if issue.code in {"AMBIGUOUS_CONTAINER", "SPATIAL_CYCLE"}}
    spatial = {row.id: row for row in result.spatial_elements}
    ambiguous.update(row.id for row in result.spatial_elements if row.source_step_id in duplicates)
    geometry = {row.element_id: row.status for row in result.geometry}
    quantities = defaultdict(set)
    for row in result.quantities:
        quantities[row.element_id].add(row.status)
    materials = defaultdict(list)
    for row in result.materials:
        materials[row.element_id].append(row.classification)
    mismatches = {issue.element_id for issue in result.issues if issue.code == "GEOMETRY_QUANTITY_MISMATCH"}
    valid = result.is_valid
    for row in result.elements:
        container = row.container_id
        resolved = container is not None and row.id not in ambiguous
        seen = set()
        while resolved and container is not None:
            if container in ambiguous or container in seen or container not in spatial:
                resolved = False
                break
            seen.add(container)
            container = spatial[container].container_id
        statuses = quantities[row.id]
        yield Readiness(
            row.id, valid, valid and row.source_step_id not in duplicates and resolved,
            resolved, geometry.get(row.id, "not_assessed"),
            "disputed" if "disputed" in statuses or row.id in mismatches else "available" if "accepted" in statuses else "missing",
            bool(materials[row.id]),
            "source_label_available" if any(materials[row.id]) else
            "unclassified" if materials[row.id] else "missing",
        )
