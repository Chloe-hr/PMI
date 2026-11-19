"""Read supported IFC occurrences and their spatial containment."""

from pmi_core.schemas.bim import BIMElement, Issue, stable_id


SUPPORTED_CLASSES = ("IfcFooting", "IfcColumn", "IfcBeam", "IfcSlab", "IfcWall", "IfcMember", "IfcReinforcingBar")


def _is_spatial(entity):
    return entity.is_a("IfcSpatialElement") or entity.is_a("IfcSpatialStructureElement")


def type_relations(entity):
    return sorted(
        (*getattr(entity, "IsTypedBy", ()),
         *(rel for rel in getattr(entity, "IsDefinedBy", ()) if rel.is_a("IfcRelDefinesByType"))),
        key=lambda rel: rel.id(),
    )


def _parents(entity):
    for relation in getattr(entity, "ContainedInStructure", ()):
        yield relation.RelatingStructure
    for relation in getattr(entity, "Decomposes", ()):
        yield relation.RelatingObject
    for relation in getattr(entity, "Nests", ()):
        yield relation.RelatingObject


def _containers(entity, trail):
    if entity.id() in trail:
        raise ValueError("Cyclic spatial or decomposition relationship.")
    if _is_spatial(entity):
        return {entity}
    result = set()
    for parent in _parents(entity):
        result.update(_containers(parent, trail | {entity.id()}))
    return result


def extract_elements(model, version_id, evidence, issues, identity):
    spatial_class = "IfcSpatialStructureElement" if model.schema == "IFC2X3" else "IfcSpatialElement"
    spatial = sorted(model.by_type(spatial_class), key=lambda row: row.id())
    ambiguous = {step for issue in identity if issue.code == "DUPLICATE_GLOBAL_ID" for step in issue.step_ids}

    def element_id(entity):
        parts = (version_id, "element", entity.GlobalId)
        if entity.id() in ambiguous:
            parts += (str(entity.id()),)
        return stable_id(*parts)
    objects = sorted(
        {row for name in SUPPORTED_CLASSES for row in model.by_type(name)},
        key=lambda row: row.id(),
    )

    def record(entity):
        identifier = element_id(entity)
        parents = set()
        try:
            for parent in _parents(entity):
                parents.update(_containers(parent, {entity.id()}))
        except (ValueError, RecursionError):
            issues.append(Issue("error", "SPATIAL_CYCLE", "Cannot resolve spatial ancestry.", (entity.id(),), identifier))
            parents.clear()
        if len(parents) > 1:
            issues.append(Issue(
                "error", "AMBIGUOUS_CONTAINER", "Multiple spatial containers found.",
                (entity.id(), *sorted(p.id() for p in parents)), identifier,
            ))
        if not parents and not _is_spatial(entity):
            issues.append(Issue("warning", "MISSING_CONTAINER", "No spatial container found.", (entity.id(),), identifier))
        container = next(iter(parents)) if len(parents) == 1 else None
        types = type_relations(entity)
        assigned_type = types[0].RelatingType if len(types) == 1 else None
        predefined = getattr(entity, "PredefinedType", None)
        if predefined in (None, "NOTDEFINED") and assigned_type is not None:
            predefined = getattr(assigned_type, "PredefinedType", None) or predefined
        sources = [entity]
        if assigned_type is not None:
            sources.extend((types[0], assigned_type))
        sources.extend(sorted(parents, key=lambda parent: parent.id()))
        return BIMElement(
            id=identifier,
            evidence_ids=tuple(evidence.entity(source.id()) for source in sources),
            model_version_id=version_id,
            global_id=entity.GlobalId,
            ifc_class=entity.is_a(),
            source_step_id=entity.id(),
            container_id=element_id(container) if container else None,
            name=entity.Name,
            object_type=getattr(entity, "ObjectType", None),
            predefined_type=predefined,
            classification=getattr(entity, "CompositionType", None) if _is_spatial(entity) else None,
        )

    pairs = tuple((row, record(row)) for row in objects)
    spatial_records = tuple(record(row) for row in spatial)
    spatial_by_id = {row.id: row for row in spatial_records}
    for row in spatial_records:
        seen = {row.id}
        parent_id = row.container_id
        while parent_id in spatial_by_id:
            if parent_id in seen:
                issues.append(Issue("error", "SPATIAL_CYCLE", "Spatial hierarchy contains a cycle.", (row.source_step_id,), row.id))
                break
            seen.add(parent_id)
            parent_id = spatial_by_id[parent_id].container_id
    return pairs, spatial_records
