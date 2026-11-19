"""Estimate the closed, hypothetical Stage 5.3A fixture."""

from collections import defaultdict
from datetime import time
from itertools import combinations
from math import isclose, prod

from pmi_core.construction.dependencies import dependency_issues
from pmi_core.construction.engine import catalogue_selection
from pmi_core.estimation.references import number
from pmi_core.schemas.bim import stable_id


FIXTURE_SHA = "8932ed0e043a1fb1252e51b223166c5c15b81f4969018a7e18c49e2802282c2c"
FIXTURE_ELEMENTS = {
    "24tlOXIsvMQfyRLiqh6fZt": ("IfcColumn", 0.48),
    "1jDfy2_jTRueAw6f5fc3Ev": ("IfcBeam", 0.80),
    "3wOB$MtWLSz8SJNgW3VJvy": ("IfcSlab", 2.40),
}
INPUT_STATES = ("missing", "hypothetical_fixture", "user_provided_project",
                "independently_measured", "engineer_approved")
GROUP_FIELDS = ("storey", "zone", "classification", "method", "batch")


def estimate_operation(quantity, unit, ref, crew, machines, process_minimum=0, *,
                       execution_mode="simultaneous_fixed_crew", concurrent_throughput=None):
    """Use bottleneck productive hours for simultaneous, fixed capacities."""
    if execution_mode != "simultaneous_fixed_crew":
        raise ValueError("Insufficient phase evidence for a sequential or unrecognized execution method.")
    number(quantity, "quantity", positive=True)
    if unit != ref["unit"]:
        raise ValueError(f"Incompatible quantity unit {unit}; expected {ref['unit']}.")
    labor = {key: quantity * rate for key, rate in ref["labor_per_unit"].items()}
    equipment = {key: quantity * rate for key, rate in ref["equipment_per_unit"].items()}
    minimum = number(process_minimum, "process minimum")
    bounds = {"process_minimum": minimum}
    for label, demand, capacity in (("labor", labor, crew), ("equipment", equipment, machines)):
        for key, hours in demand.items():
            if hours:
                available = capacity.get(key)
                if type(available) is not int or available <= 0:
                    raise ValueError(f"Missing or invalid {label} capacity: {key}.")
                bounds[f"{label}:{key}"] = hours / available
    throughput = concurrent_throughput or {}
    for key, rate in throughput.items():
        bounds[f"throughput:{key}"] = quantity / number(rate, f"{key} throughput", positive=True)
    duration = max(bounds.values())
    components = {key: value * quantity for key, value in ref["component_eur_per_unit"].items()}
    published = quantity * ref["published_eur_per_unit"]
    labor_cost = {key: hours * ref["labor_rate_eur_per_hour"][key] for key, hours in labor.items()}
    equipment_cost = {key: components["equipment"] for key in equipment} if len(equipment) == 1 else {}
    materials = [{**row, "quantity": quantity * row["per_unit"],
                  "cost_eur_from_line": quantity * row["per_unit"] * row["reference_rate_eur"]}
                 for row in ref["materials"]]

    return {
        "worker_hours_by_trade": labor, "machine_hours_by_class": equipment,
        "materials": materials, "labor_cost_eur_by_trade": labor_cost,
        "equipment_cost_eur_by_class": equipment_cost,
        "worker_capacity_by_trade": {key: crew[key] for key in labor if labor[key]},
        "equipment_capacity_by_class": {key: machines[key] for key in equipment if equipment[key]},
        "concurrent_throughput_per_hour": throughput, "execution_mode": execution_mode,
        "productive_hours": duration, "elapsed_hours": None, "capacity_bounds_hours": bounds,
        "reserved_worker_hours": {key: duration * crew[key] for key in labor if labor[key] > 0},
        "reserved_machine_hours": {key: duration * machines[key] for key in equipment if equipment[key] > 0},
        "cost_components_eur": components, "reference_cost_eur": published,
        "rounding_residual_eur": published - sum(components.values()), "reference": ref,
    }


def group_packages(packages, assignments):
    """Create optional explicit reporting groups without altering activities or graph."""
    groups = defaultdict(list)
    seen = set()
    for package in packages:
        for guid in package["global_ids"]:
            if guid in seen:
                raise ValueError("A GlobalId occurs in multiple package scopes.")
            seen.add(guid)
            values = assignments.get(guid)
            if values is None:
                continue
            keys = tuple(values.get(field) for field in GROUP_FIELDS)
            if any(not isinstance(value, str) or not value.strip() for value in keys):
                raise ValueError("A grouping needs a storey, zone, classification, method and batch.")
            groups[keys].append((package["id"], guid))
    if set(assignments) - seen:
        raise ValueError("Grouping refers to an unknown GlobalId.")
    return [{"id": stable_id("stage5.3", *key), **dict(zip(GROUP_FIELDS, key)),
             "package_ids": list(dict.fromkeys(package for package, _ in rows)),
             "global_ids": [guid for _, guid in rows]} for key, rows in sorted(groups.items())]


def _calendar(config):
    windows = config["working_windows"]
    totals = defaultdict(list)
    for window in windows:
        day = window["weekday"]
        if type(day) is not int or not 1 <= day <= 7:
            raise ValueError("Invalid ISO calendar weekday.")
        times = [time.fromisoformat(window[key]) for key in ("start", "end")]
        if any(value.tzinfo or value.second or value.microsecond for value in times):
            raise ValueError("Use local hour/minute calendar windows.")
        start, end = [value.hour * 60 + value.minute for value in times]
        if end <= start:
            raise ValueError("Invalid calendar window.")
        totals[day].append((start, end))
    expected = number(config["productive_hours_per_workday"], "productive workday", positive=True)
    if not totals:
        raise ValueError("Missing calendar windows.")
    for intervals in totals.values():
        intervals.sort()
        if any(first[1] > second[0] for first, second in zip(intervals, intervals[1:])):
            raise ValueError("Overlapping calendar windows.")
        if sum(end - start for start, end in intervals) / 60 != expected:
            raise ValueError("Calendar hours do not match productive hours per workday.")
    return expected


def _fixture_measurements(bim, config):
    by_guid = {row["global_id"]: row for row in bim["elements"]}
    if len(bim["elements"]) != 3 or set(by_guid) != set(FIXTURE_ELEMENTS) or set(by_guid) != set(config["elements"]):
        raise ValueError("Fixture evidence must contain the three configured GlobalIds.")
    quantities = defaultdict(list)
    for q in bim["quantities"]:
        if q["status"] == "accepted" and q["kind"] == "volume" and q["unit"] == "m3":
            quantities[q["element_id"], q["basis"]].append(q)
    result, boxes = {}, []
    for guid, spec in config["elements"].items():
        element = by_guid[guid]
        lo, hi = spec["bounds_m"]
        if len(lo) != 3 or len(hi) != 3:
            raise ValueError("Expected three-dimensional fixture bounds.")
        dimensions = [number(b - a, "fixture span", positive=True) for a, b in zip(lo, hi)]
        authored, body = (quantities[element["id"], basis] for basis in ("net_volume", "represented_body_volume"))
        volume = prod(dimensions)
        ifc_class, fixture_volume = FIXTURE_ELEMENTS[guid]
        if element["ifc_class"] != ifc_class or not isclose(volume, fixture_volume, abs_tol=1e-9):
            raise ValueError(f"Unexpected fixture class or volume for {guid}.")
        if (len(authored) != 1 or len(body) != 1 or authored[0]["method"] != "ifc_quantity"
                or body[0]["method"] != "geometry" or not all(isclose(row["value"], volume, abs_tol=1e-9)
                                                             for row in [*authored, *body])):
            raise ValueError(f"Unreconciled authored and geometry volumes for {guid}.")
        boxes.append((lo, hi))
        measurement = {
            "element_id": element["id"], "global_id": guid, "ifc_class": element["ifc_class"],
            "placed_concrete_m3": round(volume, 9), "concrete_quantity_ids": [authored[0]["id"], body[0]["id"]],
            "concrete_evidence_ids": [e for row in [*authored, *body] for e in row["evidence_ids"]],
            "formwork_m2": spec["formwork_m2"], "formwork_rule": spec["formwork_rule"],
            "reinforcement_kg": spec["reinforcement_kg"], "reinforcement_boq": spec["reinforcement_boq"],
            "bounds_m": spec["bounds_m"], "fixture_input_id": guid,
            "estimation_input_state": "hypothetical_fixture",
            "concrete_quantity_origin": "model_authored_cross_checked_with_ifc_geometry",
        }
        result[element["id"]] = measurement
    for (lo, hi), (other_lo, other_hi) in combinations(boxes, 2):
        if all(min(b, d) - max(a, c) > 1e-9 for a, b, c, d in zip(lo, hi, other_lo, other_hi)):
            raise ValueError("Fixture concrete bodies have an unreconciled positive-volume intersection.")
    return result


def _external_resources(ref, equipment, spec):
    if ref["unresolved_equipment"] == "none":
        return [], {}
    required = ["CRANE"]
    if ref["work_item"].endswith("-CONC"):
        required += ["CONCRETE_PUMP", "CONCRETE_DELIVERY"]
    declared_none, throughput = [], {}
    for key in required:
        declared = equipment.get(key)
        if type(declared) is int and declared == 0:
            declared_none.append(key)
        elif (ref["work_item"].endswith("-CONC") and isinstance(declared, dict)
              and declared.get("unit") == "m3/h" and declared.get("concurrent_with_placement") is True):
            throughput[key] = number(declared.get("capacity"), f"{key} throughput", positive=True)
        else:
            raise ValueError(f"Missing compatible {key} supply or explicit none for this operation.")
    if declared_none and not spec.get("manual_handling_and_staged_supply"):
        raise ValueError("Declare the manual handling and pre-staged supply method.")
    return declared_none, throughput


def estimate_frame(bim, construction, config, references, reference_digest):
    """Produce fixture-only estimates from matching Stage 5.1 and 5.2 envelopes."""
    model = bim.get("model_version") or {}
    if (bim.get("contract_version"), construction.get("version"), config.get("version")) != (
        "5.1.0", "5.2A", "5.3A-fixture"
    ):
        raise ValueError("Incompatible estimation input contract versions.")
    if (not bim.get("is_valid") or not construction.get("import_valid") or bim.get("policy") != "strict"
            or construction.get("policy") != "strict" or model.get("sha256") != FIXTURE_SHA
            or config.get("source_sha256") != FIXTURE_SHA or model.get("id") != construction.get("model_version_id")
            or config.get("hypothetical_only") is not True):
        raise ValueError("Fixture scope only. Real-project estimation and release are disabled.")
    approvals = construction["approval_register"]
    if (len(approvals) != 75 or len({row["approval_id"] for row in approvals}) != 75
            or any(row["status"] != "PENDING" for row in approvals)):
        raise ValueError("The controlled pipeline requires all 75 engineering approvals to remain pending.")
    measurements = _fixture_measurements(bim, config)
    workday = _calendar(config["calendar"])
    options = {(row["activity_id"], row["bcca_code"]): row for row in construction["catalogue_options"]}
    activity_lookup = {row["id"]: row for row in construction["activities"]}
    activities, packages, edges = [], [], []
    for package in construction["packages"]:
        element_id, = package["element_ids"]
        measurement = measurements[element_id]
        guid = measurement["global_id"]
        inputs = config["elements"][guid]
        source = {activity_lookup[key]["work_item"]: activity_lookup[key] for key in package["activity_ids"]}
        if len(source) != 5 or any(row["schedulable"] for row in source.values()):
            raise ValueError("Expected five unreleased Stage 5.2 fixture activities per package.")
        selected = [(item, options.get((row["id"], config["catalogue"].get(item))))
                    for item, row in source.items() if item != "CURE"]
        known = [(item, row) for item, row in selected if row is not None]
        conflicts = catalogue_selection(config["catalogue"].keys() & source.keys(), known)
        if conflicts:
            raise ValueError("Conflicting fixture catalogue selections: " + ", ".join(conflicts))

        family = package["family"]
        form, bars, place = (source[f"{family}-{suffix}"]["id"] for suffix in ("FORM", "REBAR", "CONC"))
        cure, strip = (source[item]["id"] for item in ("CURE", "FRM-STRIP"))
        inspect = stable_id(package["id"], "fixture-inspection")
        release = stable_id(package["id"], "fixture-striking-release")
        seq = inputs["sequence"]
        if seq not in ({"cage_first", "overlap"} if family == "COL" else {"formwork_first"}):
            raise ValueError(f"Incompatible construction sequence for {guid}.")
        source_ids = {row["id"] for row in source.values()}
        proposed = [edge for edge in construction["dependencies"]
                    if edge["predecessor_id"] in source_ids and edge["successor_id"] in source_ids]
        expected_rule = "DR05" if family == "COL" else "DR06"
        if not any(edge["rule_id"] == expected_rule and edge["option"] == seq for edge in proposed):
            raise ValueError("Selected construction sequence is absent from Stage 5.2 evidence.")
        rules = {edge["rule_id"] for edge in proposed}
        if not {"DR06", "DR07", "DR08"} <= rules:
            raise ValueError("Missing required source dependencies.")
        edge_specs = [(bars, form, "SS" if seq == "overlap" else "FS", "DR05")] if family == "COL" else [
            (form, bars, "FS", "DR06")]
        edge_specs += [(form, inspect, "FS", "DR06"), (bars, inspect, "FS", "DR06"),
                       (inspect, place, "FS", "DR06"), (place, cure, "FS", "DR07"),
                       (cure, release, "FS", "DR08"), (release, strip, "FS", "DR08")]
        edges.extend({"predecessor_id": a, "successor_id": b, "relation": relation, "rule_id": rule,
                      "state": "fixture_selected", "lag_hours": 0} for a, b, relation, rule in edge_specs)

        for item, choice in selected:
            row = source[item]
            record = {"id": row["id"], "package_id": package["id"], "global_id": guid, "work_item": item,
                      "kind": "productive", "eligible_for_real_scheduling": False,
                      "pending_approval_ids": row["pending_approval_ids"], "blockers": []}
            try:
                if choice is None:
                    raise ValueError("Missing compatible catalogue selection.")
                ref = references.get((item, choice["bcca_code"]))
                if ref is None or choice["source_sha256"] != ref["bc3_sha256"]:
                    raise ValueError("Missing matching engineering decomposition.")
                if not isclose(float(choice["direct_unit_cost_eur"]), ref["published_eur_per_unit"], abs_tol=1e-9):
                    raise ValueError("Catalogue price differs from the engineering reference.")
                unit, key = ("m3", "placed_concrete_m3") if item.endswith("-CONC") else (
                    ("kg", "reinforcement_kg") if item.endswith("-REBAR") else ("m2", "formwork_m2"))
                if unit == "m3" and config.get("concrete_specification") != "HA-25/P/20/XC2":
                    raise ValueError("Missing matching fixture concrete specification.")
                record.update({"quantity": measurement[key], "unit": unit,
                               "quantity_ids": measurement["concrete_quantity_ids"] if unit == "m3" else [],
                               "fixture_quantity_key": key if unit != "m3" else None})
                declared, throughput = _external_resources(ref, config["equipment"], inputs)
                crew_name = config["crew_by_operation"].get("STRIP" if item == "FRM-STRIP" else item.rsplit("-", 1)[1])
                mode = config["crews"].get(crew_name, {})
                # Supplemental throughput constrains production. Its separate costs are outside BCCA.
                record.update(estimate_operation(measurement[key], unit, ref, mode, config["equipment"],
                                                 execution_mode=inputs.get("execution_mode"),
                                                 concurrent_throughput=throughput))
                record.update({"crew_id": crew_name, "explicit_none_equipment": declared,
                               "productive_workdays_equivalent": record["productive_hours"] / workday,
                               "duration_basis": "simultaneous resource bottleneck, booked bundle"})
            except (ValueError, KeyError) as exc:
                record["blockers"].append(str(exc))
            activities.append(record)

        try:
            curing = number(inputs["curing_elapsed_hours"], "curing hold")
            striking = number(inputs["striking_elapsed_hours_from_pour"], "striking criterion")
            elapsed_holds = (number(inputs["inspection_elapsed_hours"], "inspection hold"), curing,
                             max(0, striking - curing))
            hold_blockers = [[], [], []]
        except (ValueError, KeyError) as exc:
            elapsed_holds, hold_blockers = (None, None, None), [[str(exc)]] * 3
        for uid, item, hours, criterion, blockers in zip(
            (inspect, cure, release), ("INSPECTION-HOLD", "CURE", "STRIKING-RELEASE"),
            elapsed_holds, (inputs.get("inspection_condition"), inputs.get("curing_condition"),
                            inputs.get("striking_condition")), hold_blockers,
        ):
            activities.append({"id": uid, "package_id": package["id"], "global_id": guid, "work_item": item,
                               "kind": "elapsed_hold", "elapsed_hours": hours, "productive_hours": None,
                               "worker_hours_by_trade": {}, "machine_hours_by_class": {}, "materials": [],
                               "criterion": criterion, "reference_cost_eur": None,
                               "cost_treatment": "included_in_placement" if item == "CURE" else "unpriced_release",
                               "eligible_for_real_scheduling": False,
                               "pending_approval_ids": sorted(set(source["CURE"]["pending_approval_ids"] if item == "CURE"
                                                                  else source["FRM-STRIP"]["pending_approval_ids"]
                                                                  if item == "STRIKING-RELEASE" else ["AP-DR06"])),
                               "blockers": blockers if criterion else [*blockers, "Missing hold criterion."]})
        packages.append({**package, "global_ids": [guid], "fixture_sequence": seq,
                         "activity_ids": [*package["activity_ids"], inspect, release]})

    graph_issues = dependency_issues((row["id"] for row in activities), edges)
    if len(packages) != len(measurements) or {p["element_ids"][0] for p in packages} != set(measurements):
        raise ValueError("Construction package coverage differs from the controlled frame.")
    rows = [row for row in activities if row["kind"] == "productive"]
    for row in activities:
        row["input_state"] = "missing" if row["blockers"] else "hypothetical_fixture"
        row["assumption_ref"] = f"controlled_fixture_inputs.json#/elements/{row['global_id']}"
        row["eligible_for_controlled_scheduling_input"] = not row["blockers"] and not graph_issues
    priced = [row for row in rows if row.get("reference_cost_eur") is not None]
    complete = len(rows) == len(priced)
    ready = not graph_issues and not any(row["blockers"] for row in activities)
    covered_cost = sum(row["reference_cost_eur"] for row in priced)
    return {
        "version": "5.3A", "scope": "hypothetical_fixture_only", "source_sha256": FIXTURE_SHA,
        "model_version_id": model["id"], "reference_selection_sha256": reference_digest,
        "construction_library_version": construction["library_version"],
        "eligible_for_controlled_scheduling_input": ready, "eligible_for_real_scheduling": False,
        "input_states": INPUT_STATES, "engineering_approval_status": "pending",
        "calendar": config["calendar"], "fixture_inputs": config, "element_quantities": list(measurements.values()),
        "packages": packages, "activities": activities, "dependencies": edges, "graph_issues": graph_issues,
        "conditional_dependencies": [row for row in construction["dependencies"] if row["state"] == "conditional"],
        "model_elements": bim["elements"], "evidence": bim["evidence"],
        "pending_approvals": approvals,
        "groups": group_packages(packages, config.get("group_assignments", {})),
        "cost": {"currency": "EUR", "covered_direct_reference_eur": covered_cost,
                 "total_direct_reference_eur": covered_cost if complete else None,
                 "components_eur": {key: sum(row["cost_components_eur"][key] for row in priced)
                                    for key in ("labor", "equipment", "material")},
                 "rounding_residual_eur": sum(row["rounding_residual_eur"] for row in priced),
                 "boundary": "BCCA Dec-2023 V02 Andalusia direct catalogue costs, excluding tax, overhead, profit and indirects."},
    }
