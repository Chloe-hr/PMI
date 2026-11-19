"""Verify that every source reference in resource_contract_mapping.csv resolves in the real files,
and that every mapped contract field exists in resource_contract.json."""

import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = HERE.parents[3]
FILES = {
    "scheduling_handover.json": "research/implementation/stage5_3/scheduling_handover.json",
    "controlled_fixture_inputs.json": "research/implementation/stage5_3/controlled_fixture_inputs.json",
    "controlled_scheduling_inputs.json": "research/planning/stage5_4_preparation/controlled_scheduling_inputs.json",
    "scheduling_contract.json": "research/implementation/stage5_4a/scheduling_contract.json",
    "scheduling_test_cases.json": "research/planning/stage5_4_preparation/scheduling_test_cases.json",
    "engineering_gate_matrix.csv": "research/planning/stage5_4_preparation/engineering_gate_matrix.csv",
}
CODE = {"fixture.py": "pmi_core/scheduling/fixture.py", "cpm.py": "pmi_core/scheduling/cpm.py",
        "calendar.py": "pmi_core/scheduling/calendar.py", "engine.py": "pmi_core/estimation/engine.py"}


def resolve(node, parts):
    if not parts:
        return True
    head, rest = parts[0], parts[1:]
    if head == "*":
        return isinstance(node, dict) and any(resolve(v, rest) for v in node.values())
    if head.endswith("[]"):
        key = head[:-2]
        items = node.get(key) if isinstance(node, dict) else None
        return isinstance(items, list) and any(resolve(i, rest) for i in items)
    return isinstance(node, dict) and head in node and resolve(node[head], rest)


def check_ref(ref):
    ref = re.sub(r"\s*\([^)]*\)\s*$", "", ref.strip())
    if ref in ("", "none"):
        return True, "none"
    if "::" in ref:
        name, path = ref.split("::", 1)
        data = json.loads((REPO / FILES[name]).read_text(encoding="utf-8-sig"))
        return resolve(data, path.strip().split(".")), ref
    if "#" in ref:
        name, token = ref.split("#", 1)
        return token in (REPO / CODE[name]).read_text(encoding="utf-8"), ref
    name = ref.split(" ")[0]
    return (REPO / FILES[name]).exists(), ref


contract = json.loads((PKG / "resource_contract.json").read_text(encoding="utf-8"))
entities = contract["entities"]
failures, checked = [], 0
with (PKG / "resource_contract_mapping.csv").open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
for row in rows:
    ent = row["contract_entity"]
    if ent not in entities:
        failures.append(f"unknown entity {ent}")
        continue
    spec = entities[ent]
    names = [re.sub(r"\s*\(.*\)$", "", n.strip()).split("[]")[0] for n in row["contract_field"].split("/")]
    for n in names:
        known = set(spec.get("fields", {}))
        if ent == "ActivityResourceRequirement":
            known |= set(spec["fields"]["modes"]["items"])
        if ent == "CapacityPolicy":
            known = {r["code"] for r in spec["rules"]}
        if ent == "Event":
            known |= set(contract["enumerations"]["event_kind"])
        if n not in known and n.split(".")[-1] not in known:
            failures.append(f"{ent}.{n} not in contract")
    for col in ("stage5_3A_source", "stage5_4A_source", "agent2_preparation_source"):
        prefix = None
        for ref in row[col].split(" | "):
            if "::" in ref:
                prefix = ref.split("::", 1)[0]
            elif prefix and "#" not in ref and ref.strip() not in ("", "none"):
                ref = f"{prefix}::{ref.strip()}"  # continuation of the same file
            ok, label = check_ref(ref)
            checked += label != "none"
            if not ok:
                failures.append(f"{col}: {label}")
print(f"{len(rows)} mapping rows, {checked} source references checked")
for x in failures:
    print("FAIL", x)
sys.exit(1 if failures else 0)
