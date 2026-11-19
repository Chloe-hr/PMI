"""Read IFC material associations without inferring quantities or grades."""

from math import isfinite
import re

from pmi_core.bim.elements import type_relations
from pmi_core.schemas.bim import Issue, MaterialRecord, stable_id


def classify_material_name(name):
    """Identify explicit material labels, keeping construction method unvalidated."""
    if re.search(r"aerat|masonry|concrete block|AAC\b|ytong|kalkzandsteen|\u52a0\u6c14|\u7816", name, re.IGNORECASE):
        return "masonry_or_aerated"
    if re.search(r"cast[- ]in[- ](?:place|situ)|in[- ]situ concrete", name, re.IGNORECASE):
        return "cast_in_place_label"
    return None


def _members(selection):
    if selection.is_a("IfcMaterial"):
        yield selection, selection, "single", None, ()
    elif selection.is_a("IfcMaterialList"):
        for material in selection.Materials:
            yield material, selection, "list", None, ()
    elif selection.is_a("IfcMaterialLayerSetUsage"):
        for material, member, basis, fraction, parents in _members(selection.ForLayerSet):
            yield material, member, basis, fraction, (selection, *parents)
    elif selection.is_a("IfcMaterialProfileSetUsage"):
        for material, member, basis, fraction, parents in _members(selection.ForProfileSet):
            yield material, member, basis, fraction, (selection, *parents)
    elif selection.is_a("IfcMaterialLayerSet"):
        for member in selection.MaterialLayers:
            yield member.Material, member, "layer", None, (selection,)
    elif selection.is_a("IfcMaterialProfileSet"):
        for member in selection.MaterialProfiles:
            yield member.Material, member, "profile", None, (selection,)
    elif selection.is_a("IfcMaterialConstituentSet"):
        for member in sorted(selection.MaterialConstituents or (), key=lambda row: row.id()):
            yield member.Material, member, "constituent", member.Fraction, (selection,)


def _relations(entity):
    return sorted(
        (rel for rel in entity.HasAssociations if rel.is_a("IfcRelAssociatesMaterial")),
        key=lambda rel: rel.id(),
    )


def extract_materials(entity, record, evidence, issues):
    relations = _relations(entity)
    basis_scope = "occurrence"
    type_relation = None
    if not relations:
        assignments = type_relations(entity)
        if len(assignments) > 1:
            issues.append(Issue("warning", "AMBIGUOUS_MATERIAL", "Multiple element type assignments.", (entity.id(),), record.id))
            return []
        if assignments:
            type_relation = assignments[0]
            relations = _relations(type_relation.RelatingType)
            basis_scope = "type"
    if not relations:
        issues.append(Issue("warning", "MISSING_MATERIAL", "No occurrence or type material association.", (entity.id(),), record.id))
        return []
    if len(relations) != 1:
        issues.append(Issue(
            "warning", "AMBIGUOUS_MATERIAL", "Multiple material associations at the same scope.",
            tuple(rel.id() for rel in relations), record.id,
        ))
        return []

    relation = relations[0]
    selection = relation.RelatingMaterial
    rows = []
    members = list(_members(selection)) if selection else []
    if not members:
        issues.append(Issue("warning", "UNSUPPORTED_MATERIAL", "Material association has no supported members.", (relation.id(),), record.id))
    for index, (material, member, basis, fraction, parents) in enumerate(members):
        if material is None or not material.Name or not material.Name.strip():
            issues.append(Issue("warning", "MISSING_MATERIAL_MEMBER", "Material member has no name.", (member.id(),), record.id))
            continue
        if fraction is not None and (not isfinite(fraction) or not 0 <= fraction <= 1):
            issues.append(Issue("warning", "INVALID_MATERIAL_FRACTION", "Material fraction is outside [0, 1].", (member.id(),), record.id))
            fraction = None
        identifier = stable_id(record.id, "material", str(relation.id()), str(index))
        sources = [relation, selection, *parents, member, material]
        if type_relation is not None:
            sources.extend((type_relation, type_relation.RelatingType))
        rows.append(MaterialRecord(
            identifier,
            tuple(dict.fromkeys(evidence.entity(item.id()) for item in sources)),
            record.id, material.Name.strip(), f"{basis_scope}_{basis}", fraction=fraction,
            classification=classify_material_name(material.Name),
        ))
    return rows
