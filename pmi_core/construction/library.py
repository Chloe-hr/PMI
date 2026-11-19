"""Read the approved research handover without rewriting its source tables."""

import csv
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from math import isfinite
from pathlib import Path
from types import MappingProxyType


DEFAULT_LIBRARY = Path(__file__).resolve().parents[2] / "research/construction_knowledge/stage5_2_preparation"
TABLES = {
    "work": ("construction_work_item_library", "activity_id", 29),
    "catalogue": ("bcca_reference_mapping", None, 61),
    "classification": ("element_classification_rules", "rule_id", 15),
    "dependencies": ("construction_dependency_rules", "rule_id", 16),
    "controls": ("double_counting_risk_register", "risk_id", 14),
    "inputs": ("required_user_inputs", "input_id", 22),
    "approvals": ("engineering_approval_register", "approval_id", 75),
    "quantities": ("quantity_requirement_matrix", "quantity", 11),
}


@dataclass(frozen=True)
class KnowledgeLibrary:
    version: str
    hashes: dict
    tables: dict


def load_library(root=DEFAULT_LIBRARY):
    tables, hashes = {}, {}
    for name, (filename, key, count) in TABLES.items():
        path = Path(root) / f"{filename}.csv"
        raw = path.read_bytes()
        hashes[path.name] = sha256(raw).hexdigest()
        reader = csv.DictReader(StringIO(raw.decode("utf-8-sig"), newline=""))
        rows = list(reader)
        if (len(rows) != count or len(set(reader.fieldnames or ())) != len(reader.fieldnames or ())
                or any(None in row or None in row.values() for row in rows)):
            raise ValueError(f"Invalid size or CSV structure: {path}")
        keys = [row.get(key) if key else (row.get("activity_id"), row.get("bcca_code")) for row in rows]
        if any(not value for value in keys) or len(set(keys)) != count:
            raise ValueError(f"Missing or duplicate key in {path}")
        tables[name] = MappingProxyType(dict(zip(keys, map(MappingProxyType, rows))))

    work, approvals = tables["work"], tables["approvals"]
    expected = set(work).union(*(tables[name] for name in ("classification", "dependencies", "controls")))
    linked = {row["item"] for row in approvals.values()}
    if (not expected <= linked or "AP-TOL" not in approvals or
            any(row["status"] != "PENDING" for row in approvals.values())):
        raise ValueError("The Stage 5.2A source approval register is inconsistent.")
    for (activity_id, code), row in tables["catalogue"].items():
        if (activity_id not in work or not code or row["role"] not in {"primary", "alternative"}
                or not row["bcca_unit"] or not row["measurement_rule_text"]
                or len(row["source_sha256"]) != 64
                or any(value not in {"True", "False"} for key, value in row.items() if key.startswith("includes_"))):
            raise ValueError(f"Invalid catalogue reference {activity_id}/{code}")
        cost = row["direct_unit_cost_eur"]
        if cost and (not isfinite(float(cost)) or float(cost) < 0):
            raise ValueError(f"Invalid catalogue cost {activity_id}/{code}")
    if any(row["universal_default_duration"] != "NONE" for row in tables["dependencies"].values()):
        raise ValueError("Unexpected universal duration in dependency source.")
    version = "5.2A/" + sha256("".join(hashes.values()).encode()).hexdigest()
    return KnowledgeLibrary(version, MappingProxyType(hashes), MappingProxyType(tables))
