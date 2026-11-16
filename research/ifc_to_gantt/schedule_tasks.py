"""
Stage 3.3a - Tasks -> CPM schedule -> interactive Gantt
=======================================================
Reuses the tested CPM from scripts/schedule_engine.py (forward + backward pass, working days
Mon-Fri, finish-exclusive) so the research pipeline and the midterm app share one engine.

    python research/ifc_to_gantt/schedule_tasks.py outputs/v1 --start 2026-11-16
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from schedule_engine import Network, add_dates, cpm  # noqa: E402

PHASE_COLOURS = {  # one hue per phase, ordered roughly by construction sequence
    "Preliminaries": "#8c8c8c", "Substructure": "#8a5a44", "Superstructure": "#c0504d",
    "Envelope": "#2e75b6", "Interiors": "#70ad47", "Handover": "#7f6084",
}


def schedule(tasks: pd.DataFrame, start: date) -> pd.DataFrame:
    acts = tasks.rename(columns={"name": "activity"}).copy()
    acts["predecessors"] = acts["predecessors"].fillna("").apply(lambda s: [p for p in str(s).split(";") if p])
    s = add_dates(cpm(Network(activities=acts[["id", "activity", "duration_days", "predecessors", "phase"]])), start)
    keep = ["id", "package", "storey", "n_elements", "quantities", "work_days", "rule", "flags", "predecessors"]
    s = s.merge(tasks[keep], on="id", how="left")
    s["end_exclusive"] = s["finish_date"] + timedelta(days=1)   # bar ends at close of the finish day
    return s


def gantt(s: pd.DataFrame, title: str, ghost: pd.DataFrame | None = None) -> go.Figure:
    """Horizontal bars per task, coloured by phase; critical tasks outlined.
    `ghost` (optional) = an earlier schedule drawn as grey outlines behind, for V1-vs-V2 comparison."""
    order = s.sort_values(["ES", "id"])["activity"].tolist()
    if ghost is not None:
        order += [a for a in ghost.sort_values("ES")["activity"] if a not in order]
    fig = go.Figure()
    if ghost is not None:
        fig.add_trace(go.Bar(
            y=ghost["activity"], x=(ghost["end_exclusive"] - ghost["start_date"]).dt.days * 86400000,
            base=ghost["start_date"], orientation="h", name="V1 baseline",
            marker=dict(color="rgba(0,0,0,0)", line=dict(color="#555", width=1.5)),
            hovertemplate="%{y}<br>V1: %{base|%d %b %Y}<extra>baseline</extra>"))
    for phase, g in s.groupby("phase", sort=False):
        fig.add_trace(go.Bar(
            y=g["activity"], x=(g["end_exclusive"] - g["start_date"]).dt.days * 86400000,
            base=g["start_date"], orientation="h", name=phase,
            marker=dict(color=PHASE_COLOURS.get(phase, "#999"),
                        line=dict(color=["#000" if c else "rgba(0,0,0,0)" for c in g["critical"]], width=2)),
            customdata=g[["id", "duration", "float", "n_elements", "quantities", "rule", "finish_date"]].astype(str),
            hovertemplate=("<b>%{y}</b> (%{customdata[0]})<br>%{base|%d %b %Y} -> %{customdata[6]}"
                           "<br>%{customdata[1]} working days · float %{customdata[2]}"
                           "<br>%{customdata[3]} elements · %{customdata[4]}<br>%{customdata[5]}<extra>%{fullData.name}</extra>")))
    fig.update_layout(title=title, barmode="overlay", xaxis_type="date", height=max(420, 26 * len(order) + 140),
                      yaxis=dict(categoryorder="array", categoryarray=order[::-1]),
                      legend=dict(orientation="h", y=-0.08), margin=dict(l=10, r=10, t=60, b=40))
    return fig


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--start", default="2026-11-16")
    a = ap.parse_args(argv)
    tasks = pd.read_csv(a.folder / "tasks.csv")
    s = schedule(tasks, date.fromisoformat(a.start))
    s.to_csv(a.folder / "schedule.csv", index=False)
    days = int(s["EF"].max())
    fig = gantt(s, f"PMI - generated schedule: {days} working days (ASSUMED productivity rates; black outline = critical)")
    fig.write_html(a.folder / "gantt.html", include_plotlyjs="cdn")
    print(s[["id", "activity", "duration", "start_date", "finish_date", "float", "critical"]].to_string(index=False))
    print(f"\n{days} working days, finish {s['finish_date'].max().date()} -> {a.folder / 'gantt.html'}")


if __name__ == "__main__":
    main()
