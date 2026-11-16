"""
Stage 3.4 - Model version comparison  (V1 baseline is preserved, never overwritten)
==================================================================================
Inputs: two pipeline folders (each with elements.csv, task_element_links.csv, tasks.csv, schedule.csv).

Outputs (in --out):
    element_changes.csv   ADDED / REMOVED / MODIFIED elements (by source_id) with what changed
    task_changes.csv      per task: V1 vs V2 duration, element count, dates, delta, which elements drove it
    gantt_compare.html    V2 bars over V1 outlines

Element-level detail here covers what drives the generated schedule (class, storey, materials,
quantities). scripts/detect_changes.py remains the richer 5-channel detector for property changes.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from schedule_tasks import gantt

FIELDS = ["ifc_class", "storey", "materials", "length_m", "area_m2", "volume_m3"]


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
    if pd.isna(a) and pd.isna(b):
        return True
    return a == b


def element_changes(e1: pd.DataFrame, e2: pd.DataFrame, l1: pd.DataFrame, l2: pd.DataFrame) -> pd.DataFrame:
    a, b = e1.set_index("source_id"), e2.set_index("source_id")
    t1, t2 = l1.set_index("source_id")["task_id"], l2.set_index("source_id")["task_id"]
    rows = []
    for gid in sorted(set(a.index) | set(b.index)):
        if gid not in b.index:
            rows.append({"source_id": gid, "status": "REMOVED", "ifc_class": a.at[gid, "ifc_class"],
                         "name": a.at[gid, "name"], "changed": "", "task_v1": t1.get(gid, ""), "task_v2": ""})
            continue
        if gid not in a.index:
            rows.append({"source_id": gid, "status": "ADDED", "ifc_class": b.at[gid, "ifc_class"],
                         "name": b.at[gid, "name"], "changed": "", "task_v1": "", "task_v2": t2.get(gid, "")})
            continue
        diffs = [f"{c}: {a.at[gid, c]} -> {b.at[gid, c]}" for c in FIELDS if not _same(a.at[gid, c], b.at[gid, c])]
        if diffs or t1.get(gid, "") != t2.get(gid, ""):
            rows.append({"source_id": gid, "status": "MODIFIED", "ifc_class": b.at[gid, "ifc_class"],
                         "name": b.at[gid, "name"], "changed": "; ".join(diffs),
                         "task_v1": t1.get(gid, ""), "task_v2": t2.get(gid, "")})
    return pd.DataFrame(rows, columns=["source_id", "status", "ifc_class", "name", "changed", "task_v1", "task_v2"])


def task_changes(s1: pd.DataFrame, s2: pd.DataFrame, ec: pd.DataFrame) -> pd.DataFrame:
    cols = ["id", "activity", "duration", "n_elements", "start_date", "finish_date", "float", "critical"]
    m = s1[cols].merge(s2[cols], on="id", how="outer", suffixes=("_v1", "_v2"))
    m["activity"] = m["activity_v2"].fillna(m["activity_v1"])
    m["duration_delta"] = m["duration_v2"].fillna(0) - m["duration_v1"].fillna(0)
    m["finish_shift_cal_days"] = (pd.to_datetime(m["finish_date_v2"]) - pd.to_datetime(m["finish_date_v1"])).dt.days
    drivers = {}
    for r in ec.itertuples():
        for t in {r.task_v1, r.task_v2} - {""}:
            drivers.setdefault(t, []).append(f"{r.status} {r.ifc_class}")
    m["changed_elements"] = m["id"].map(lambda t: "; ".join(f"{n}x {k}" for k, n in
                                                            pd.Series(drivers.get(t, [])).value_counts().items()))
    m["status"] = m.apply(lambda r: "NEW TASK" if pd.isna(r.duration_v1) else "REMOVED TASK" if pd.isna(r.duration_v2)
                          else "LONGER" if r.duration_delta > 0 else "SHORTER" if r.duration_delta < 0
                          else "MOVED" if r.finish_shift_cal_days else "CHANGED SCOPE" if r.changed_elements else "", axis=1)
    return m[["id", "activity", "status", "duration_v1", "duration_v2", "duration_delta", "n_elements_v1",
              "n_elements_v2", "finish_date_v1", "finish_date_v2", "finish_shift_cal_days", "critical_v1",
              "critical_v2", "changed_elements"]].sort_values("finish_date_v2")


def compare(d1: Path, d2: Path, out: Path) -> dict:
    d1, d2, out = Path(d1), Path(d2), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rd = lambda d, n: pd.read_csv(d / n)
    ec = element_changes(rd(d1, "elements.csv"), rd(d2, "elements.csv"),
                         rd(d1, "task_element_links.csv"), rd(d2, "task_element_links.csv"))
    dates = ["start_date", "finish_date", "end_exclusive"]
    s1 = pd.read_csv(d1 / "schedule.csv", parse_dates=dates)
    s2 = pd.read_csv(d2 / "schedule.csv", parse_dates=dates)
    tc = task_changes(s1, s2, ec)
    ec.to_csv(out / "element_changes.csv", index=False)
    tc.to_csv(out / "task_changes.csv", index=False)
    v1, v2 = int(s1["EF"].max()), int(s2["EF"].max())
    fig = gantt(s2, f"PMI - V2 schedule ({v2} wd) over V1 baseline outlines ({v1} wd): {v2 - v1:+d} working days",
                ghost=s1)
    fig.write_html(out / "gantt_compare.html", include_plotlyjs="cdn")
    return {"v1_days": v1, "v2_days": v2, "delta_days": v2 - v1,
            "v1_finish": str(s1["finish_date"].max().date()), "v2_finish": str(s2["finish_date"].max().date()),
            "elements": ec["status"].value_counts().to_dict(),
            "tasks_affected": int((tc["status"] != "").sum())}
