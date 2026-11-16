"""
Stage 3.3b - Write the PMI schedule into the IFC model (IFC4D)
=============================================================
Adds to a COPY of the source model:
    IfcWorkPlan > IfcWorkSchedule "PMI baseline"
      IfcTask per PMI task (Identification = task id, Name, PredefinedType CONSTRUCTION)
        - task time: ScheduleStart / ScheduleFinish / ScheduleDuration from PMI's CPM
        - outputs: assign_product(task -> every linked building element)   (IfcRelAssignsToProcess)
      IfcRelSequence FINISH_START for every dependency

Dates are written from PMI's CPM; IfcOpenShell's cascade is NOT used, so PMI stays the single source
of schedule logic. The original IFC file is never modified.

    python research/ifc_to_gantt/write_ifc4d.py models/original.ifc outputs/v1 outputs/v1/scheduled_v1.ifc
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def write_schedule(src_ifc: Path, folder: Path, out_ifc: Path, name: str = "PMI baseline") -> dict:
    import ifcopenshell
    import ifcopenshell.api

    folder = Path(folder)
    sched = pd.read_csv(folder / "schedule.csv", parse_dates=["start_date", "finish_date"])
    links = pd.read_csv(folder / "task_element_links.csv")
    deps = pd.read_csv(folder / "dependencies.csv")

    f = ifcopenshell.open(str(src_ifc))
    migrated = ""
    if f.schema == "IFC2X3":
        # IFC2x3 IfcTask lacks Identification / PredefinedType / TaskTime and 4D tools expect IFC4.
        # Migrate the COPY; GlobalIds are preserved, so task-element links still hold.
        import contextlib
        import io
        import ifcpatch
        migrated = f.schema
        with contextlib.redirect_stdout(io.StringIO()):   # silence per-attribute migration notes
            f = ifcpatch.execute({"input": str(src_ifc), "file": f, "recipe": "Migrate", "arguments": ["IFC4"]})
    api = ifcopenshell.api.run
    plan = api("sequence.add_work_plan", f, name="PMI work plan")
    ws = api("sequence.add_work_schedule", f, name=name, work_plan=plan)

    tasks, missing = {}, 0
    for r in sched.itertuples():
        t = api("sequence.add_task", f, work_schedule=ws, name=r.activity, identification=r.id,
                predefined_type="CONSTRUCTION")
        tasks[r.id] = t
        products = []
        for gid in links.loc[links.task_id == r.id, "source_id"]:
            try:
                products.append(f.by_guid(gid))
            except RuntimeError:
                missing += 1
        for p in products:
            api("sequence.assign_product", f, relating_product=p, related_object=t)

    for d in deps.itertuples():
        if d.predecessor in tasks and d.successor in tasks:
            api("sequence.assign_sequence", f, relating_process=tasks[d.predecessor],
                related_process=tasks[d.successor], sequence_type="FINISH_START")

    # Times LAST and set directly on IfcTaskTime: the API's edit_task_time / assign_sequence cascade dates
    # on calendar days (no IfcWorkCalendar), which would overwrite PMI's Mon-Fri CPM dates.
    for r in sched.itertuples():
        tt = api("sequence.add_task_time", f, task=tasks[r.id])
        tt.ScheduleStart = r.start_date.strftime("%Y-%m-%dT08:00:00")
        tt.ScheduleFinish = r.finish_date.strftime("%Y-%m-%dT17:00:00")
        tt.ScheduleDuration = f"P{int(r.duration)}D"
        tt.DurationType = "WORKTIME"
        tt.IsCritical = bool(r.critical)
        tt.TotalFloat = f"P{int(r.float)}D"

    out_ifc = Path(out_ifc)
    out_ifc.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(out_ifc))
    return {"schema": f.schema, "migrated_from": migrated, "tasks": len(tasks), "sequences": len(f.by_type("IfcRelSequence")),
            "product_links": len(links) - missing, "missing_elements": missing, "file": str(out_ifc)}


def read_back(path: Path) -> pd.DataFrame:
    """Independent check: reopen the written IFC and list each task with its linked element count."""
    import ifcopenshell
    import ifcopenshell.util.sequence as us

    f = ifcopenshell.open(str(path))
    rows = []
    for t in f.by_type("IfcTask"):
        rows.append({"id": t.Identification if hasattr(t, "Identification") else t.Name, "name": t.Name,
                     "outputs": len(us.get_task_outputs(t)),
                     "predecessors": len(us.get_sequence_assignment(t, "predecessor"))})
    return pd.DataFrame(rows)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 3:
        print(__doc__)
        return 1
    info = write_schedule(Path(argv[0]), Path(argv[1]), Path(argv[2]))
    print(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
