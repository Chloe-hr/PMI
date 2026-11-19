"""Adapt the frozen Stage 5.3A fixture to the Stage 5.4A scheduling contract."""

import csv
from hashlib import sha256
from math import isclose
import json

from .cpm import calculate


ROOT_GUIDS = {
    "24tlOXIsvMQfyRLiqh6fZt": ("C", "COL"),
    "1jDfy2_jTRueAw6f5fc3Ev": ("B", "BEAM"),
    "3wOB$MtWLSz8SJNgW3VJvy": ("S", "SLAB"),
}
FIXTURE_SHA = "8932ed0e043a1fb1252e51b223166c5c15b81f4969018a7e18c49e2802282c2c"
CROSS_SUPPORT = {("C-CURE", "B-FORM"), ("C-STRIP", "B-FORM"),
                 ("B-CURE", "S-FORM"), ("S-STRIP", "B-STRIP")}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify_reference(handover, prep, fixture_input):
    reference = read_json(prep / "reference_calculation.json")
    proof = reference["fixture_B_agent1_stage5_3A"]
    digest = sha256(fixture_input.read_bytes()).hexdigest()
    if digest != reference["_meta"]["sources"]["agent1_fixture_sha256"]:
        raise ValueError("Agent 2's fixture input hash does not match current Stage 5.3A.")
    actual = {(r["global_id"], r["work_item"]): r for r in handover["activities"] if r["kind"] == "productive"}
    with (prep / "agent1_stage5_3A_comparison.csv").open(encoding="utf-8-sig", newline="") as stream:
        comparison = list(csv.DictReader(stream))
    reference_keys = {(r["global_id"], r["activity"]) for r in proof["activities"]}
    if len(actual) != 12 or set(actual) != reference_keys or len(comparison) != 12:
        raise ValueError("The independent fixture reference covers a different activity set.")
    for expected in proof["activities"]:
        row = actual[expected["global_id"], expected["activity"]]
        if (row["reference"]["code"] != expected["bcca_code"] or row["unit"] != expected["unit"]
                or any(not isclose(row[name], expected[other], abs_tol=1e-9)
                       for name, other in (("quantity", "quantity"), ("productive_hours", "productive_hours"),
                                           ("reference_cost_eur", "direct_cost_eur")))
                or any(row[key].keys() != expected[key].keys()
                       or any(not isclose(val, expected[key][name], abs_tol=1e-9) for name, val in row[key].items())
                       for key in ("worker_hours_by_trade", "machine_hours_by_class"))):
            raise ValueError(f"Independent fixture evidence differs for {row['work_item']}.")
    for expected in comparison:
        row = actual[expected["global_id"], expected["work_item"]]
        if (row["reference"]["code"] != expected["bcca_code"] or
                not isclose(row["productive_hours"], float(expected["independent_productive_h"]), abs_tol=1e-9)
                or not isclose(row["reference_cost_eur"], float(expected["independent_cost_eur"]), abs_tol=1e-9)):
            raise ValueError("Agent 2 comparison CSV differs from the handover.")
    cost = handover["cost"]["total_direct_reference_eur"]
    if cost != proof["totals"]["direct_cost_eur"]:
        raise ValueError("Independent total differs from the frozen handover cost.")
    return {"fixture_input_sha256": digest, "checked_productive_activities": len(actual),
            "independent_reference_cost_eur": cost}


def _alias(item, prefix):
    if item == "INSPECTION-HOLD":
        return f"{prefix}-INSP"
    if item == "STRIKING-RELEASE":
        return f"{prefix}-STRIKE"
    if item == "FRM-STRIP":
        return f"{prefix}-STRIP"
    suffix = item.split("-")[-1]
    return f"{prefix}-{'POUR' if suffix == 'CONC' else suffix}"


def adapt(handover, prepared, config):
    approvals = handover["pending_approvals"]
    if (handover.get("version") != "5.3A" or handover.get("scope") != "hypothetical_fixture_only"
            or handover.get("source_sha256") != FIXTURE_SHA or handover.get("eligible_for_real_scheduling") is not False
            or handover.get("eligible_for_controlled_scheduling_input") is not True
            or config.get("scope") != "hypothetical_fixture_only" or config.get("version") != "5.4A"
            or len({row["approval_id"] for row in approvals}) != 75
            or len(approvals) != 75 or any(row["status"] != "PENDING" for row in approvals)):
        raise ValueError("Scheduling is restricted to the controlled Stage 5.3A fixture with pending approvals.")
    calendar = prepared["calendar"]
    baselines = {row["id"]: row for row in prepared["activities"]}
    inspectors = {row["id"]: row for row in prepared["inspection_milestones"]}
    elements = {row["global_id"]: row for row in handover["model_elements"]}
    alias_ids, uid_aliases, tasks = {}, {}, []
    for row in handover["activities"]:
        guid, item, uid = (row[key] for key in ("global_id", "work_item", "id"))
        prefix, family = ROOT_GUIDS[guid]
        alias = _alias(item, prefix)
        if alias in alias_ids or uid in uid_aliases:
            raise ValueError("Duplicate fixture activity identity.")
        alias_ids[alias], uid_aliases[uid] = uid, alias
        oracle = baselines[alias]
        kind = row["kind"]
        note = "Stage 5.3A activity retained"
        if item == "INSPECTION-HOLD":
            kind = "inspection"
            minutes = inspectors[alias]["duration_min"]
            if not isclose(minutes, row["elapsed_hours"] * 60):
                raise ValueError("Fixture inspection duration differs from the Stage 5.3A assumption.")
            note = "Former elapsed inspection converted to a working shift and one inspector."
        elif item == "STRIKING-RELEASE":
            kind = "strength_release"
            minutes = prepared["striking"][family]["elapsed_hours_from_pour"] * 60
            note = "Absolute elapsed minimum from pour finish. Strength pass is a separate condition."
        elif item == "CURE":
            minutes = prepared["curing"][family]["elapsed_hours"] * 60
            if not isclose(minutes, row["elapsed_hours"] * 60):
                raise ValueError("Active handover and scheduling preparation curing values differ.")
        else:
            minutes = row["productive_hours"] * 60
        crew_mode = row.get("crew_id")
        crew = handover["fixture_inputs"]["crews"].get(crew_mode, {})
        if crew_mode and crew != prepared["crew_modes"][crew_mode]:
            raise ValueError(f"Prepared full crew differs for {alias}.")
        capacities = {**crew, **row.get("equipment_capacity_by_class", {})}
        if kind == "inspection":
            capacities = {inspectors[alias]["resource"]: 1}
        if capacities != oracle.get("resources", {}):
            raise ValueError(f"Prepared resource mode differs for {alias}.")
        tasks.append({
            "id": uid, "reference_id": alias, "global_id": guid, "element_id": elements[guid]["id"],
            "package_id": row["package_id"], "family": family, "work_item": item, "kind": kind,
            "duration_minutes": minutes, "source_productive_hours": row.get("productive_hours"),
            "source_elapsed_hours": row.get("elapsed_hours"), "resources": capacities,
            "allowed_hours": oracle.get("window"), "interruption": "non_interruptible",
            "release_event_id": alias if kind == "strength_release" else None,
            "release_condition": oracle.get("condition") or row.get("criterion"),
            "reference_cost_eur": row.get("reference_cost_eur"),
            "pending_approval_ids": row["pending_approval_ids"], "assumption_ref": row.get("assumption_ref"),
            "transformation": note,
        })
    if set(alias_ids) != set(baselines):
        raise ValueError("Scheduling preparation and fixture activity sets differ.")

    original = handover["dependencies"]
    if len(original) != 21:
        raise ValueError("Expected the 21 frozen Stage 5.3A dependency records.")
    links, changes = [], []

    def add(left, right, rule, note, *, lag_minutes=0, relation="FS", source="fixture_extension"):
        links.append({"predecessor_id": alias_ids[left], "successor_id": alias_ids[right],
                      "predecessor_alias": left, "successor_alias": right,
                      "relation": relation, "rule_id": rule, "lag_minutes": lag_minutes,
                      "lag_basis": "elapsed", "source": source, "condition": note})

    for row in original:
        a, b = (uid_aliases[row[field]] for field in ("predecessor_id", "successor_id"))
        if a.endswith("-CURE") and b.endswith("-STRIKE"):
            changes.append({"original": row, "reason": "Striking minimum re-anchored to pour finish."})
            continue
        add(a, b, row["rule_id"], None, relation=row["relation"], lag_minutes=row["lag_hours"] * 60, source="5.3A")
    for prefix, _ in ROOT_GUIDS.values():
        add(f"{prefix}-POUR", f"{prefix}-STRIKE", "DR08", "Minimum elapsed time from pour completion.")
        add(f"{prefix}-CURE", f"{prefix}-STRIP", "DR08", "Curing completed independently of strength release.")
    prepared_cross = {(pred["id"], row["id"])
                      for row in prepared["activities"] if row.get("cross_package")
                      for pred in row["predecessors"] if not pred["id"].startswith(row["id"][0] + "-")}
    if prepared_cross != CROSS_SUPPORT:
        raise ValueError("Explicit cross-package support endpoints are incomplete or differ from preparation.")
    for a, b in sorted(prepared_cross):
        add(a, b, "DR09", baselines[b]["cross_package"])
    events = config.get("hypothetical_strength_events", {})
    if set(events) - {task["release_event_id"] for task in tasks if task["release_event_id"]}:
        raise ValueError("Unknown strength-release event.")
    if any(event.get("status") not in {"hypothetical_pass_at_minimum", "hypothetical_recorded_pass", "failed"}
           for event in events.values()):
        raise ValueError("The fixture accepts hypothetical strength events only.")
    result = calculate(tasks, links, calendar, start=prepared["project"]["start_local"],
                       horizon=config["horizon_local"], tick=config.get("tick_minutes", calendar["tick_minutes"]),
                       capacities=prepared["resource_capacity_by_trade"], release_events=events)
    return {
        **result, "version": "5.4A", "scope": "hypothetical_fixture_only", "real_project_eligible": False,
        "calendar": calendar, "dependencies": links, "original_stage5_3_dependencies": original,
        "dependency_transformations": changes, "conditional_source_dependencies": handover["conditional_dependencies"],
        "model_version_id": handover["model_version_id"], "source_sha256": handover["source_sha256"],
        "cost": handover["cost"], "element_quantities": handover["element_quantities"],
        "packages": handover["packages"], "pending_approvals": approvals,
        "capacity_basis": "Diagnostic only. Fixed crew and machine pools are not levelled by CPM.",
        "hypothetical_strength_events": events,
    }
