"""Read-only Stage 3.8B artifact contract for the Streamlit IFC4D workspace."""
from __future__ import annotations
import csv
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
import ifcopenshell
import pandas as pd
from research.ifc4d import pipeline

PROJECTS = ("SYN-BRG-001", "SYN-BLD-001")
SNAPSHOTS = ("V0", "V1", "V2")
REPRESENTATIONS = ("as_provided", "derived")
COUNTS = {"SYN-BRG-001": (20,39,19), "SYN-BLD-001": (27,54,26)}

class ArtifactError(ValueError):
    """An artifact cannot be trusted for visualization."""


def require(condition, message):
    if not condition:
        raise ArtifactError(message)


def inclusive_finish(value):
    boundary = datetime.fromisoformat(value)
    require(boundary.time() == datetime.min.time(), "IFC finish must be a midnight exclusive boundary")
    return (boundary-timedelta(days=1)).date().isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_bundle(folder):
    """Verify every manifest-listed byte on EVERY load, before parsing or caching meshes."""
    folder = Path(folder).resolve()
    try:
        manifest = read_json(folder/"manifest.json")
        require(manifest.get("complete") is True and manifest.get("round_trip_passed") is True,
                "Stage 3.8B manifest is incomplete or round-trip validation failed")
        required = {"source_records.json", "task_ifc_mapping.csv", "round_trip_validation.json",
                    "schedule_validation.json", "schedule_conflicts.json", "schedule_conflicts.csv"}
        required |= {f"{p}-{s}/{name}" for p in PROJECTS for s in SNAPSHOTS
                     for name in ("as_provided.ifc", "derived.ifc", "derived_schedule.csv", "dependencies.csv")}
        hashes = manifest["output_sha256"]
        require(required <= set(hashes), "Manifest is missing required artifact hashes")
        for name, expected in hashes.items():
            target = (folder/name).resolve()
            require(target.is_relative_to(folder) and target.is_file(), f"Missing or unsafe artifact: {name}")
            require(hashlib.sha256(target.read_bytes()).hexdigest() == expected, f"Artifact SHA-256 mismatch: {name}")
        records = read_json(folder/"source_records.json")
        require({r["project_id"] for r in records["Projects"]} == set(PROJECTS), "Unexpected projects")
        mapping = pd.read_csv(folder/"task_ifc_mapping.csv",dtype=str)
        require(not mapping.duplicated(["project_id","version_id","representation","task_id"]).any(), "Duplicate task mappings")
        require(mapping.ifc_task_global_id.is_unique, "IFC task GlobalIds are not unique")
        trips = read_json(folder/"round_trip_validation.json")
        validations = read_json(folder/"schedule_validation.json")
        combos = {(p,p+"-"+s,r) for p in PROJECTS for s in SNAPSHOTS for r in REPRESENTATIONS}
        for name, rows in (("round-trip",trips),("schedule",validations)):
            keys = [(r["project_id"],r["version_id"],r["representation"]) for r in rows]
            require(len(keys)==len(combos) and set(keys)==combos, f"Incomplete or duplicate {name} combinations")
        require(set(zip(mapping.project_id,mapping.version_id,mapping.representation))==combos,
                "Invalid mapping combinations")
        for row in trips:
            require(row["passed"] is True and row["original_entities_unchanged"] is True,
                    "Unsuccessful round-trip preservation record")
            require((row["tasks"],row["associations"],row["dependencies"])==COUNTS[row["project_id"]],
                    "Round-trip record counts disagree with project contract")
        bundle = dict(folder=folder,manifest=manifest,records=records,mapping=mapping,
                      trips=trips,validations=validations,conflicts=read_json(folder/"schedule_conflicts.json"))
        # Validate the entire 12-way selector matrix before displaying any project.
        bundle["selections"] = {key:_load_selection(bundle,*key) for key in sorted(combos)}
        return bundle
    except ArtifactError:
        raise
    except Exception as exc:
        raise ArtifactError(f"Incomplete or invalid IFC4D artifacts: {exc}") from exc


def _load_selection(bundle, project, version, representation):
    path = bundle["folder"]/version/(representation+".ifc")
    model = ifcopenshell.open(str(path))
    records = bundle["records"]
    elements = [r for r in records["Elements"] if r["project_id"]==project]
    links = [r for r in records["ElementTask"] if r["project_id"]==project]
    dependencies = [r for r in records["Dependencies"] if r["project_id"]==project]
    sources = pipeline.project_snapshots(records,project)[version]
    originals = {r["task_id"]:r for r in sources}
    with (bundle["folder"]/version/"derived_schedule.csv").open(encoding="utf-8",newline="") as f:
        derived = {r["task_id"]:r for r in csv.DictReader(f)}
    expected_ids = set(originals)
    require(all(r["task_id"] in expected_ids for r in records["Progress"] if r["project_id"]==project),"Unresolved synthetic progress task")
    require(set(derived)==expected_ids,"Derived schedule task IDs do not match snapshot")
    selected_map = bundle["mapping"]
    selected_map = selected_map[(selected_map.project_id==project)&(selected_map.version_id==version)&(selected_map.representation==representation)]
    expected_guids = dict(zip(selected_map.task_id,selected_map.ifc_task_global_id))
    require(set(expected_guids)==expected_ids, "Task mappings do not match source activities")
    tasks = model.by_type("IfcTask")
    require(len(tasks)==len(expected_ids) and {t.Identification for t in tasks}==expected_ids, "IFC task identifiers do not match source")
    rows = []
    for t in sorted(tasks,key=lambda t:t.Identification):
        tid=t.Identification;tt=t.TaskTime;source=originals[tid];computed=derived[tid]
        require(t.GlobalId==expected_guids[tid],"Task GlobalId mapping mismatch")
        require(t.Name==source["task_name"],"Task name differs from source")
        start=datetime.fromisoformat(tt.ScheduleStart).date().isoformat()
        finish=inclusive_finish(tt.ScheduleFinish)
        d=int(computed["duration"])
        require(d==source["duration"],"Derived/source duration mismatch")
        require(tt.DurationType=="ELAPSEDTIME" and tt.ScheduleDuration==f"P{d}D", "Invalid IFC calendar-day duration")
        require((datetime.fromisoformat(tt.ScheduleFinish)-datetime.fromisoformat(tt.ScheduleStart)).days==d,"Date/duration mismatch")
        expected = source if representation=="as_provided" else computed
        require((start,finish)==(expected["start"],expected["finish"]),"IFC dates disagree with schedule representation")
        description=json.loads(t.Description)
        require(description["source_activity"]==source["source_activity"] and description["source_version"]==source["source_version"],"Source provenance mismatch")
        require(int(computed["start_shift_days"])==(pipeline.day(computed["start"])-pipeline.day(source["start"])).days,"Start shift mismatch")
        require(int(computed["finish_shift_days"])==(pipeline.day(computed["finish"])-pipeline.day(source["finish"])).days,"Finish shift mismatch")
        rows.append(dict(task_id=tid,task_name=t.Name,project_id=project,version_id=version,
                         representation=representation,start=start,finish=finish,duration=d,
                         original_start=source["start"],original_finish=source["finish"],
                         derived_start=computed["start"],derived_finish=computed["finish"],
                         start_shift_days=int(computed["start_shift_days"]),finish_shift_days=int(computed["finish_shift_days"]),
                         as_of_date=source["as_of_date"],ifc_task_global_id=t.GlobalId))
    element_map = {r["element_id"]:r["ifc_global_id"] for r in elements}
    require(len(element_map)==len(elements) and len(set(element_map.values()))==len(elements),"Duplicate elements")
    expected_links={(r["task_id"],element_map[r["element_id"]]) for r in links}
    require({t for t,g in expected_links}==expected_ids,"Tasks without element assignments")
    actual_links={(r.RelatingProcess.Identification,e.GlobalId) for r in model.by_type("IfcRelAssignsToProcess") for e in r.RelatedObjects}
    require(actual_links==expected_links,"IFC element assignments mismatch")
    require({e.GlobalId for e in model.by_type("IfcBuildingElementProxy")}==set(element_map.values()),"Geometry identifiers mismatch")
    expected_deps={(d["dependency_id"],d["predecessor_task_id"],d["successor_task_id"],"FINISH_START",("-" if d["lag_days"]<0 else "")+f"P{abs(d['lag_days'])}D") for d in dependencies}
    actual_deps={(d.Name,d.RelatingProcess.Identification,d.RelatedProcess.Identification,d.SequenceType,d.TimeLag.LagValue.wrappedValue) for d in model.by_type("IfcRelSequence")}
    require(actual_deps==expected_deps,"IFC dependencies mismatch")
    schedules=model.by_type("IfcWorkSchedule")
    require(len(schedules)==1 and schedules[0].Identification==version,"IFC schedule version mismatch")
    provenance=json.loads(schedules[0].Description)
    require((provenance["project_id"],provenance["version_id"],provenance["representation"])==(project,version,representation),"Schedule provenance mismatch")
    require(provenance["input_sha256"]==bundle["manifest"]["input_sha256"],"Schedule input hashes mismatch")
    source_conflicts=[r for r in bundle["conflicts"] if r["project_id"]==project and r["version_id"]==version and r["representation"]=="as_provided"]
    actual_conflicts=pipeline.validate(rows,dependencies)
    recomputed_source=pipeline.validate(sources,dependencies)
    require({r["dependency_id"] for r in source_conflicts}=={r["dependency_id"] for r in recomputed_source},"Source conflict IDs mismatch")
    for conflict in source_conflicts:
        require(conflict in [dict(r,representation="as_provided") for r in recomputed_source],"Source conflict details mismatch")
    validation=next(r for r in bundle["validations"] if (r["project_id"],r["version_id"],r["representation"])==(project,version,representation))
    require(validation["structurally_valid"] is True and validation["conflict_count"]==len(actual_conflicts) and validation["dependency_compliant"]==(not actual_conflicts),"Schedule validation record mismatch")
    trip=next(r for r in bundle["trips"] if (r["project_id"],r["version_id"],r["representation"])==(project,version,representation))
    require(trip["precedence_conflicts"]==len(actual_conflicts),"Round-trip conflict count mismatch")
    return dict(path=path,sha256=bundle["manifest"]["output_sha256"][version+"/"+representation+".ifc"],
                tasks=pd.DataFrame(rows),elements=pd.DataFrame(elements),links=sorted(expected_links),
                dependencies=dependencies,source_conflicts=source_conflicts,selected_conflicts=actual_conflicts,
                compliant=not actual_conflicts,provenance=provenance)


def select(bundle,project,snapshot,representation):
    require(project in PROJECTS and snapshot in SNAPSHOTS and representation in REPRESENTATIONS,
            "Invalid project/snapshot/representation selection")
    return bundle["selections"][(project,project+"-"+snapshot,representation)]


def task_elements(selected,task_id):
    require(task_id in set(selected["tasks"].task_id),"Unknown selected task")
    return [gid for tid,gid in selected["links"] if tid==task_id]


def meshes(path):
    """Reuse PMI's world-coordinate triangulation settings; never export or rewrite IFC."""
    import ifcopenshell.geom
    from scripts.export_geometry import make_settings
    model=ifcopenshell.open(str(path));settings=make_settings();result=[]
    for e in model.by_type("IfcBuildingElementProxy"):
        try:
            shape=ifcopenshell.geom.create_shape(settings,e)
            v=shape.geometry.verts;f=shape.geometry.faces
            result.append(dict(global_id=e.GlobalId,name=e.Name,ifc_type=e.is_a(),
                               vertices=[v[i:i+3] for i in range(0,len(v),3)],faces=[f[i:i+3] for i in range(0,len(f),3)]))
        except Exception as exc:
            try:
                result.append(rectangle_extrusion_mesh(e, str(exc)))
            except Exception as fallback:
                raise ArtifactError(f"Cannot triangulate IFC element {e.GlobalId}: {exc}; rectangle-extrusion fallback: {fallback}") from fallback
    return result


def rectangle_extrusion_mesh(element, kernel_error):
    """Exact tessellation of a single IFC rectangular extrusion, not a guessed bounding box."""
    import numpy as np
    from ifcopenshell.util.placement import get_local_placement, get_axis2placement
    representations=element.Representation.Representations
    require(len(representations)==1 and len(representations[0].Items)==1,"Only a single exact extrusion can use the fallback")
    solid=representations[0].Items[0]
    require(solid.is_a("IfcExtrudedAreaSolid") and solid.SweptArea.is_a("IfcRectangleProfileDef"),"Unsupported fallback geometry")
    profile=solid.SweptArea
    x,y,depth=float(profile.XDim),float(profile.YDim),float(solid.Depth)
    require(x>0 and y>0 and depth>0,"Invalid extrusion dimensions")
    matrix=get_local_placement(element.ObjectPlacement) @ get_axis2placement(solid.Position)
    pm=np.eye(4)
    if profile.Position:
        # The supplied 2D profile positions contain a redundant zero Z coordinate.
        # Interpret only strictly planar XY positions; never discard nonzero geometry.
        coords=tuple(profile.Position.Location.Coordinates)
        require(len(coords) in (2,3) and (len(coords)==2 or coords[2]==0),"Nonplanar 2D profile position")
        pm[:2,3]=coords[:2]
        if profile.Position.RefDirection:
            ratios=tuple(profile.Position.RefDirection.DirectionRatios)
            require(len(ratios) in (2,3) and (len(ratios)==2 or ratios[2]==0),"Nonplanar profile direction")
            axis=np.asarray(ratios[:2],dtype=float)
            require(np.linalg.norm(axis)>0,"Invalid profile axis")
            axis=axis/np.linalg.norm(axis)
            pm[:2,0]=axis;pm[:2,1]=[-axis[1],axis[0]]
    direction=np.asarray(solid.ExtrudedDirection.DirectionRatios,dtype=float)
    require(np.linalg.norm(direction)>0,"Invalid extrusion direction")
    direction=direction/np.linalg.norm(direction)*depth
    bottom=[(pm @ np.array([a,b,0,1]))[:3] for a,b in [(-x/2,-y/2),(x/2,-y/2),(x/2,y/2),(-x/2,y/2)]]
    vertices=[(matrix @ np.r_[point+offset,1])[:3].tolist() for offset in [np.zeros(3),direction] for point in bottom]
    require(np.isfinite(vertices).all(),"Nonfinite extrusion coordinates")
    faces=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
           [1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]]
    return dict(global_id=element.GlobalId,name=element.Name,ifc_type=element.is_a(),
                vertices=vertices,faces=faces,render_method="exact rectangle extrusion fallback",kernel_error=kernel_error)
