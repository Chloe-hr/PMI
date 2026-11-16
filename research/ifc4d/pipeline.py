"""Traceable synthetic calendar-day schedule validation and IFC4D conversion."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
import networkx as nx
import openpyxl

POLICY = "reconciliation-v1"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data/raw/beam bridge-texas midrise/construction_dataset_v1.xlsx"
DEFAULT_OUTPUT = ROOT / "data/processed/ifc4d/stage3_8b_v1"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def integer(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise ValueError(f"Expected integral day count, got {value!r}")
    return int(value)


def load_workbook(path):
    book = openpyxl.load_workbook(path, data_only=True, read_only=True)
    result = {}
    for sheet in book:
        rows = iter(sheet.values)
        header = next(rows)
        result[sheet.title] = [dict(zip(header, row)) for row in rows if any(x is not None for x in row)]
    book.close()
    return result


def project_snapshots(data, project_id):
    activities = [r for r in data["Activities"] if r["project_id"] == project_id]
    if not activities or len({r["task_id"] for r in activities}) != len(activities):
        raise ValueError("Missing or duplicate activities")
    names = {r["task_id"]: r for r in activities}
    snapshots = {}
    versions = [r for r in data["ScheduleVersions"] if r["project_id"] == project_id]
    expected_versions = {project_id + "-" + v for v in ("V0", "V1", "V2")}
    if {r["version_id"] for r in versions} != expected_versions:
        raise ValueError("Expected distinct V0, V1, V2 snapshots")
    for version in sorted(expected_versions):
        records = [r for r in versions if r["version_id"] == version]
        if len(records) != len(names) or {r["task_id"] for r in records} != set(names):
            raise ValueError(f"Incomplete or duplicate task/version references: {version}")
        if len({r["as_of_date"] for r in records}) != 1:
            raise ValueError("Inconsistent snapshot as_of_date")
        rows = []
        for r in records:
            a = names[r["task_id"]]
            row = dict(project_id=project_id, version_id=version, task_id=r["task_id"],
                       task_name=a["task_name"], start=r["planned_start_in_version"],
                       finish=r["planned_finish_in_version"], duration=r["planned_duration_days_in_version"],
                       as_of_date=r["as_of_date"], source_activity=dict(a), source_version=dict(r))
            if version.endswith("V0") and (row["start"], row["finish"], row["duration"]) != (a["planned_start"], a["planned_finish"], a["planned_duration_days"]):
                raise ValueError("Activities baseline differs from V0")
            rows.append(row)
        snapshots[version] = rows
    return snapshots


def validate(rows, dependencies):
    """Return conflicts without changing rows or dependencies; structural errors block derivation."""
    issues = []
    project = rows[0]["project_id"] if rows else ""
    version = rows[0]["version_id"] if rows else ""
    def issue(code, task="", dep="", **detail):
        issues.append(dict(project_id=project, version_id=version, task_id=task,
                           dependency_id=dep, code=code, **detail))
    tasks = {r["task_id"]: r for r in rows}
    valid = {}
    if not rows:
        issue("empty_schedule")
    for task, n in Counter(r["task_id"] for r in rows).items():
        if n != 1:
            issue("duplicate_task", task)
    for r in rows:
        if r["project_id"] != project or r["version_id"] != version:
            issue("mixed_schedule", r["task_id"])
        try:
            start, finish, duration = day(r["start"]), day(r["finish"]), integer(r["duration"])
            if duration <= 0 or (finish-start).days + 1 != duration:
                raise ValueError("Dates do not match positive inclusive duration")
            valid[r["task_id"]] = (start, finish, duration)
        except (ValueError, TypeError):
            issue("duration_or_date", r["task_id"], original=dict(r))
    graph = nx.DiGraph()
    graph.add_nodes_from(tasks)
    for depid, n in Counter(d["dependency_id"] for d in dependencies).items():
        if n != 1:
            issue("duplicate_dependency", dep=depid)
    for d in dependencies:
        p, q, depid = d["predecessor_task_id"], d["successor_task_id"], d["dependency_id"]
        if d["project_id"] != project or p not in tasks or q not in tasks:
            issue("unresolved_reference", q, depid, original=dict(d))
            continue
        graph.add_edge(p, q)
        try:
            lag = integer(d["lag_days"])
        except (ValueError, TypeError):
            issue("invalid_lag", q, depid, original=dict(d))
            continue
        if d["relationship_type"] != "FS":
            issue("unsupported_relationship", q, depid, original=dict(d))
            continue
        if p in valid and q in valid:
            required = valid[p][1] + timedelta(days=1+lag)
            if valid[q][0] < required:
                issue("finish_to_start", q, depid, predecessor_task_id=p,
                      predecessor_finish=tasks[p]["finish"], successor_start=tasks[q]["start"],
                      lag_days=d["lag_days"], required_start=required.isoformat(),
                      shortfall_days=(required-valid[q][0]).days, original_dependency=dict(d))
    if not nx.is_directed_acyclic_graph(graph):
        edges = nx.find_cycle(graph)
        issue("cycle", cycle_edges=edges)
    return issues


def derive(rows, dependencies, anchor):
    errors = [i for i in validate(rows, dependencies) if i["code"] != "finish_to_start"]
    if errors:
        raise ValueError(json.dumps(errors, default=str))
    graph = nx.DiGraph()
    graph.add_nodes_from(r["task_id"] for r in rows)
    graph.add_edges_from((d["predecessor_task_id"], d["successor_task_id"]) for d in dependencies)
    source = {r["task_id"]: r for r in rows}
    result = {}
    for task in nx.lexicographical_topological_sort(graph):
        r = source[task]
        bounds = [day(anchor)] + [day(result[d["predecessor_task_id"]]["finish"]) + timedelta(days=1+integer(d["lag_days"])) for d in dependencies if d["successor_task_id"] == task]
        start = max(bounds)
        finish = start + timedelta(days=integer(r["duration"])-1)
        result[task] = dict(r, original_start=r["start"], original_finish=r["finish"],
                           start=start.isoformat(), finish=finish.isoformat(), anchor=day(anchor).isoformat(),
                           start_shift_days=(start-day(r["start"])).days,
                           finish_shift_days=(finish-day(r["finish"])).days,
                           representation="derived_synthetic_computed", policy=POLICY)
    output = [result[t] for t in sorted(result)]
    if validate(output, dependencies):
        raise ValueError("Derived schedule failed validation")
    return output


def guid(*parts):
    import ifcopenshell.guid
    return ifcopenshell.guid.compress(uuid.uuid5(uuid.NAMESPACE_URL, "pmi-ifc4d/" + "/".join(parts)).hex)


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, sort_keys=True, default=str) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows)


def convert(src, dest, rows, deps, links, elements, representation, provenance):
    import ifcopenshell
    model = ifcopenshell.open(str(src))
    if model.schema != "IFC4":
        raise ValueError("This pipeline requires IFC4 inputs")
    project, version = rows[0]["project_id"], rows[0]["version_id"]
    key = (project, version, representation)
    def g(kind, value):
        return guid(*key, kind, value)
    ws = model.create_entity("IfcWorkSchedule", GlobalId=g("schedule", version),
        Name=f"{version} {representation} ? synthetic", Identification=version,
        Description=json.dumps(dict(provenance, representation=representation), sort_keys=True),
        CreationDate="2026-11-16T00:00:00", StartTime=min(day(r["start"]) for r in rows).isoformat()+"T00:00:00",
        PredefinedType="USERDEFINED", ObjectType="PMI_SYNTHETIC_"+representation.upper())
    tasks = {}
    mappings = []
    for r in rows:
        tt = model.create_entity("IfcTaskTime", Name="Inclusive calendar days encoded as half-open interval",
            DataOrigin="USERDEFINED", UserDefinedDataOrigin="Synthetic source / computed schedule",
            DurationType="ELAPSEDTIME", ScheduleStart=day(r["start"]).isoformat()+"T00:00:00",
            ScheduleFinish=(day(r["finish"])+timedelta(days=1)).isoformat()+"T00:00:00",
            ScheduleDuration=f"P{integer(r['duration'])}D")
        task = model.create_entity("IfcTask", GlobalId=g("task", r["task_id"]), Name=r["task_name"],
            Identification=r["task_id"], Description=json.dumps(dict(r, representation=representation), sort_keys=True, default=str),
            IsMilestone=False, TaskTime=tt, PredefinedType="CONSTRUCTION")
        tasks[r["task_id"]] = task
        mappings.append(dict(project_id=project, version_id=version, representation=representation,
                             task_id=r["task_id"], ifc_task_global_id=task.GlobalId))
    model.create_entity("IfcRelAssignsToControl", GlobalId=g("control", version), RelatedObjects=list(tasks.values()), RelatingControl=ws)
    element_map = {r["element_id"]: r["ifc_global_id"] for r in elements}
    for r in links:
        product = model.by_guid(element_map[r["element_id"]])
        model.create_entity("IfcRelAssignsToProcess", GlobalId=g("link", r["element_id"]+"/"+r["task_id"]),
            RelatedObjects=[product], RelatingProcess=tasks[r["task_id"]])
    for d in deps:
        lag = integer(d["lag_days"])
        value = ("-" if lag < 0 else "") + f"P{abs(lag)}D"
        lt = model.create_entity("IfcLagTime", LagValue=model.create_entity("IfcDuration", value), DurationType="ELAPSEDTIME")
        model.create_entity("IfcRelSequence", GlobalId=g("dependency", d["dependency_id"]), Name=d["dependency_id"],
            Description=json.dumps(d, sort_keys=True), RelatingProcess=tasks[d["predecessor_task_id"]],
            RelatedProcess=tasks[d["successor_task_id"]], TimeLag=lt, SequenceType="FINISH_START")
    model.write(str(dest))
    return mappings


def round_trip(src, dest, rows, deps, links, elements, mappings, representation, provenance):
    import ifcopenshell
    original, model = ifcopenshell.open(str(src)), ifcopenshell.open(str(dest))
    def require(condition, message):
        if not condition:
            raise ValueError(f"Round-trip failed: {message}")
    require(all(model.by_id(e.id()).to_string() == e.to_string() for e in original), "original entity changed")
    tasks = {t.Identification: t for t in model.by_type("IfcTask")}
    require(len(model.by_type("IfcTask")) == len(rows) == len(tasks), "task count")
    require({t.GlobalId for t in tasks.values()} == {r["ifc_task_global_id"] for r in mappings}, "task GlobalIds")
    require(all(tasks[r["task_id"]].GlobalId == r["ifc_task_global_id"] for r in mappings), "task identity mapping")
    for r in rows:
        t = tasks[r["task_id"]]
        tt = t.TaskTime
        require(tt.ScheduleStart == day(r["start"]).isoformat()+"T00:00:00", "start")
        require(tt.ScheduleFinish == (day(r["finish"])+timedelta(days=1)).isoformat()+"T00:00:00", "exclusive finish")
        require(tt.ScheduleDuration == f"P{integer(r['duration'])}D" and tt.DurationType == "ELAPSEDTIME", "duration")
        require((datetime.fromisoformat(tt.ScheduleFinish)-datetime.fromisoformat(tt.ScheduleStart)).days == r["duration"], "inclusive-day interval")
        require(json.loads(t.Description) == dict(r, representation=representation), "source task provenance")
        require(tt.ActualStart is None and tt.ActualFinish is None and tt.Completion is None, "actual values leaked into planned schedule")
    sequences = model.by_type("IfcRelSequence")
    actual = {(r.Name, r.RelatingProcess.Identification, r.RelatedProcess.Identification, r.SequenceType, r.TimeLag.LagValue.wrappedValue, r.TimeLag.DurationType) for r in sequences}
    expected = {(d["dependency_id"], d["predecessor_task_id"], d["successor_task_id"], "FINISH_START", ("-" if d["lag_days"] < 0 else "")+f"P{abs(integer(d['lag_days']))}D", "ELAPSEDTIME") for d in deps}
    require(len(sequences) == len(deps) and actual == expected, "dependency types/endpoints/lags")
    element_map = {r["element_id"]: r["ifc_global_id"] for r in elements}
    associations = model.by_type("IfcRelAssignsToProcess")
    actual_links = {(r.RelatingProcess.Identification, e.GlobalId) for r in associations for e in r.RelatedObjects}
    expected_links = {(r["task_id"], element_map[r["element_id"]]) for r in links}
    require(actual_links == expected_links and len(associations) == len(links), "element associations")
    schedules = model.by_type("IfcWorkSchedule")
    require(len(schedules) == 1 and schedules[0].Identification == rows[0]["version_id"], "schedule version")
    require(json.loads(schedules[0].Description) == dict(provenance, representation=representation), "schedule provenance")
    controls = model.by_type("IfcRelAssignsToControl")
    require(len(controls) == 1 and controls[0].RelatingControl == schedules[0] and {t.GlobalId for t in controls[0].RelatedObjects} == {t.GlobalId for t in tasks.values()}, "schedule membership")
    return dict(file=Path(dest).name, representation=representation, project_id=rows[0]["project_id"],
                version_id=rows[0]["version_id"], tasks=len(tasks), associations=len(actual_links),
                dependencies=len(sequences), original_entities_unchanged=True, passed=True,
                precedence_conflicts=len(validate(rows, deps)))


def run(workbook=DEFAULT_INPUT, output=DEFAULT_OUTPUT):
    workbook, output = Path(workbook), Path(output)
    if output.exists():
        raise FileExistsError("Choose a new versioned output directory; outputs are never overwritten")
    data = load_workbook(workbook)
    projects = [r["project_id"] for r in data["Projects"]]
    if len(set(projects)) != len(projects):
        raise ValueError("Duplicate projects")
    inputs = {workbook.name: digest(workbook)}
    models = {}
    for pid in projects:
        model_rows = [r for r in data["IFCModels"] if r["project_id"] == pid]
        if len(model_rows) != 1:
            raise ValueError("Expected one source model per project")
        models[pid] = workbook.parent / model_rows[0]["file_name"]
        inputs[models[pid].name] = digest(models[pid])
    for sheet in ("Activities", "Dependencies", "ScheduleVersions", "Elements", "ElementTask", "Progress"):
        if any(r["project_id"] not in projects for r in data[sheet]):
            raise ValueError(f"Unknown project in {sheet}")
    output.mkdir(parents=True)
    (output/"source_records.json").write_text(json.dumps(data, indent=2, default=str)+"\n", encoding="utf-8")
    conflicts, validations, roundtrips, mapping = [], [], [], []
    for pid in projects:
        snapshots = project_snapshots(data, pid)
        deps = [dict(r) for r in data["Dependencies"] if r["project_id"] == pid]
        links = [dict(r) for r in data["ElementTask"] if r["project_id"] == pid]
        elements = [dict(r) for r in data["Elements"] if r["project_id"] == pid]
        taskids = {r["task_id"] for r in next(iter(snapshots.values()))}
        elementids = {r["element_id"] for r in elements}
        if len(elementids) != len(elements) or len({r["ifc_global_id"] for r in elements}) != len(elements):
            raise ValueError("Duplicate element identifiers")
        if {r["task_id"] for r in links} != taskids or {r["element_id"] for r in links} != elementids or len(links) != len(elements):
            raise ValueError("Incomplete or duplicate element/task mappings")
        if any(r["task_id"] not in taskids for r in data["Progress"] if r["project_id"] == pid):
            raise ValueError("Unresolved progress task")
        anchor = min(day(r["start"]) for rows in snapshots.values() for r in rows)
        actual = [dict(project_id=pid, version_id="synthetic_actual", task_id=r["task_id"], start=r["actual_start_synthetic"], finish=r["actual_finish_synthetic"], duration=r["actual_duration_days_synthetic"]) for r in data["Activities"] if r["project_id"] == pid]
        conflicts += [dict(i, representation="synthetic_actual") for i in validate(actual, deps)]
        for version, rows in snapshots.items():
            source_issues = validate(rows, deps)
            derived = derive(rows, deps, anchor)
            folder = output / version
            folder.mkdir()
            write_csv(folder/"derived_schedule.csv", derived)
            write_csv(folder/"dependencies.csv", deps)
            for representation, selected in (("as_provided", rows), ("derived", derived)):
                issues = validate(selected, deps)
                conflicts += [dict(i, representation=representation) for i in issues]
                validations.append(dict(project_id=pid, version_id=version, representation=representation,
                                        structurally_valid=not any(i["code"]!="finish_to_start" for i in issues),
                                        dependency_compliant=not issues, conflict_count=len(issues)))
                provenance = dict(project_id=pid, version_id=version, as_of_date=rows[0]["as_of_date"],
                                  anchor=anchor.isoformat(), policy=POLICY, input_sha256=inputs)
                dest = folder / (representation+".ifc")
                maps = convert(models[pid], dest, selected, deps, links, elements, representation, provenance)
                mapping += maps
                roundtrips.append(round_trip(models[pid], dest, selected, deps, links, elements, maps, representation, provenance))
    write_csv(output/"task_ifc_mapping.csv", mapping)
    write_csv(output/"schedule_conflicts.csv", conflicts)
    for name, value in (("schedule_conflicts.json",conflicts),("schedule_validation.json",validations),("round_trip_validation.json",roundtrips)):
        (output/name).write_text(json.dumps(value, indent=2, default=str)+"\n",encoding="utf-8")
    if any(digest(p)!=inputs[p.name] for p in [workbook,*models.values()]):
        raise ValueError("Original inputs changed during conversion")
    manifest = dict(policy=POLICY, input_sha256=inputs,
        implementation_sha256={p.name:digest(p) for p in [Path(__file__),Path(__file__).with_name("schedule_semantics.md")]},
        output_sha256={p.relative_to(output).as_posix():digest(p) for p in sorted(output.rglob("*")) if p.is_file()},
        complete=True, round_trip_passed=all(r["passed"] for r in roundtrips))
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return dict(output=str(output), files=len(roundtrips), round_trip_passed=manifest["round_trip_passed"], validations=validations)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.workbook,args.out),indent=2))
