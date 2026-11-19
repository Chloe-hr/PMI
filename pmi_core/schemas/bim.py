"""Canonical BIM records and the Stage 5.1 import envelope."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
import json
from typing import Literal
from uuid import NAMESPACE_URL, uuid5


def stable_id(*parts: str) -> str:
    """Build an unambiguous ID from a sequence of namespaced keys."""
    return str(uuid5(NAMESPACE_URL, "".join(f"{len(part)}:{part}" for part in ("pmi", *parts))))


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    id: str
    kind: Literal["source", "derivation"]
    locator: str
    version: str
    input_ids: tuple[str, ...] = ()
    sha256: str | None = None
    formula: str | None = None


@dataclass(frozen=True, slots=True)
class ModelVersion:
    id: str
    evidence_ids: tuple[str, ...]
    project_id: str
    sha256: str
    source_uri: str
    namespace: str
    ifc_schema: str
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class BIMElement:
    id: str
    evidence_ids: tuple[str, ...]
    model_version_id: str
    global_id: str
    ifc_class: str
    source_step_id: int
    container_id: str | None = None
    classification: str | None = None
    name: str | None = None
    object_type: str | None = None
    predefined_type: str | None = None


@dataclass(frozen=True, slots=True)
class QuantityRecord:
    id: str
    evidence_ids: tuple[str, ...]
    element_id: str
    kind: str
    basis: str
    method: str
    status: Literal["accepted", "missing", "disputed"]
    value: float | None = None
    unit: str | None = None
    raw_value: float | None = None
    raw_unit: str | None = None
    reason: str | None = None
    measurement_method: str | None = None


@dataclass(frozen=True, slots=True)
class MaterialRecord:
    id: str
    evidence_ids: tuple[str, ...]
    element_id: str
    name: str
    basis: str
    grade: str | None = None
    fraction: float | None = None
    classification: str | None = None


@dataclass(frozen=True, slots=True)
class Issue:
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    step_ids: tuple[int, ...] = ()
    element_id: str | None = None
    native_severity: str | None = None


@dataclass(frozen=True, slots=True)
class GeometryAssessment:
    element_id: str
    status: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ImportResult:
    model_version: ModelVersion | None
    elements: tuple[BIMElement, ...] = ()
    spatial_elements: tuple[BIMElement, ...] = ()
    quantities: tuple[QuantityRecord, ...] = ()
    materials: tuple[MaterialRecord, ...] = ()
    evidence: tuple[EvidenceProvenance, ...] = ()
    issues: tuple[Issue, ...] = ()
    source_project_global_id: str | None = None

    policy: str = "strict"
    geometry: tuple[GeometryAssessment, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Whether the IFC was importable. Check record coverage separately."""
        return self.model_version is not None and not any(i.severity == "error" for i in self.issues)

    def canonical_bundle(self, *, imported_at: datetime, contract_version: str = "5.0.0") -> dict:
        """Serialize the approved contract subset using a caller-supplied import time."""
        if not self.is_valid or self.model_version is None or self.policy != "strict":
            raise ValueError("An invalid import cannot be published as a canonical bundle.")
        if contract_version not in ("5.0.0", "5.1.0"):
            raise ValueError("Unsupported canonical contract version.")
        legacy = contract_version == "5.0.0"
        if imported_at.utcoffset() is None:
            raise ValueError("imported_at must include a timezone.")

        def record(row, exclude=()):
            return {
                field.name: getattr(row, field.name)
                for field in fields(row)
                if field.name not in exclude and getattr(row, field.name) is not None
            }

        bundle = {
            "contract_version": contract_version,
            "ModelVersion": [{**record(self.model_version), "imported_at": imported_at.isoformat()}],
            "BIMElement": [
                record(element, ("name", "object_type", "predefined_type") if legacy else ())
                for element in (*self.elements, *self.spatial_elements)
            ],
            "QuantityRecord": [record(row, ("measurement_method",) if legacy else ()) for row in self.quantities
                               if not legacy or row.method in {"ifc_quantity", "geometry", "manual"}],
            "MaterialRecord": [record(row, ("classification",) if legacy else ()) for row in self.materials],
            "EvidenceProvenance": [record(row) for row in self.evidence],
        }

        if not legacy and self.source_project_global_id:
            bundle["ModelVersion"][0]["source_project_global_id"] = self.source_project_global_id
        return json.loads(json.dumps(bundle, allow_nan=False))
