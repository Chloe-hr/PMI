"""Identity checks and import-scoped evidence collection."""

from collections import defaultdict
import re

from pmi_core.schemas.bim import EvidenceProvenance, Issue, stable_id


GLOBAL_ID = re.compile(r"[0-3][0-9A-Za-z_$]{21}")


def validate_identity(model) -> tuple[Issue, ...]:
    issues = []
    by_guid = defaultdict(list)
    for entity in sorted(model.by_type("IfcRoot"), key=lambda item: item.id()):
        guid = entity.GlobalId
        if not isinstance(guid, str) or not GLOBAL_ID.fullmatch(guid):
            issues.append(Issue("error", "INVALID_GLOBAL_ID", "IfcRoot has an invalid GlobalId.", (entity.id(),)))
        else:
            by_guid[guid].append(entity.id())
    for guid, step_ids in sorted(by_guid.items()):
        if len(step_ids) > 1:
            issues.append(Issue("error", "DUPLICATE_GLOBAL_ID", f"GlobalId {guid} is reused.", tuple(step_ids)))
    projects = model.by_type("IfcProject")
    if len(projects) != 1:
        issues.append(Issue(
            "error", "PROJECT_CARDINALITY", "Expected exactly one IfcProject.",
            tuple(sorted(project.id() for project in projects)),
        ))
    return tuple(issues)


class Evidence:
    """Deduplicate provenance nodes within one imported snapshot."""

    def __init__(self, version_id: str, source_uri: str, digest: str):
        self.version_id = version_id
        self.source_uri = source_uri
        self.records: dict[str, EvidenceProvenance] = {}
        self.source_id = stable_id(version_id, "source", source_uri)
        self.records[self.source_id] = EvidenceProvenance(
            self.source_id, "source", source_uri, "pmi-ifc-extraction-5.1", sha256=digest,
        )

    def entity(self, step_id: int) -> str:
        identifier = stable_id(self.source_id, str(step_id))
        self.records[identifier] = EvidenceProvenance(
            identifier, "source", f"{self.source_uri}#step-{step_id}", "pmi-ifc-extraction-5.1", (self.source_id,),
        )
        return identifier

    def derive(self, identifier: str, formula: str, inputs: tuple[str, ...]) -> str:
        key = stable_id(identifier, "derivation", *inputs)
        self.records[key] = EvidenceProvenance(
            key, "derivation", f"pmi:{identifier}", "pmi-ifc-extraction-5.1", inputs, formula=formula,
        )
        return key
