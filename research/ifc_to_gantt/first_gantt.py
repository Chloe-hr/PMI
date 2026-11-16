"""
P0 - First Gantt (illustrative activities, not model data)
==========================================================
Proves the scheduling + visualisation layer works end to end:
    task list -> dependency graph (DAG check) -> forward pass -> CSV + interactive Gantt

Calendar days, finish-exclusive intervals, finish-to-start dependencies.
The real pipeline (run.py) replaces this hard-coded list with tasks generated from IFC.

    python research/ifc_to_gantt/first_gantt.py
"""
from datetime import datetime, timedelta
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.express as px

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"

# Example activities; later generated from IFC work packages
tasks = [
    {"id": "T1", "task": "Foundations", "duration": 10, "depends": []},
    {"id": "T2", "task": "Columns", "duration": 6, "depends": ["T1"]},
    {"id": "T3", "task": "Slabs", "duration": 8, "depends": ["T2"]},
    {"id": "T4", "task": "Masonry", "duration": 9, "depends": ["T3"]},
    {"id": "T5", "task": "Windows", "duration": 5, "depends": ["T4"]},
    {"id": "T6", "task": "Finishes", "duration": 12, "depends": ["T4", "T5"]},
]
project_start = datetime(2026, 11, 16)


def schedule(tasks, project_start):
    graph = nx.DiGraph()
    task_map = {t["id"]: t for t in tasks}
    for t in tasks:
        graph.add_node(t["id"])
        for p in t["depends"]:
            if p not in task_map:
                raise ValueError(f"Unknown predecessor: {p}")
            graph.add_edge(p, t["id"])
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("Circular task dependencies detected")

    results = {}
    for task_id in nx.topological_sort(graph):
        t = task_map[task_id]
        start = max((results[p]["finish"] for p in t["depends"]), default=project_start)
        results[task_id] = {"id": task_id, "task": t["task"], "duration": t["duration"],
                            "depends": ";".join(t["depends"]),
                            "start": start, "finish": start + timedelta(days=t["duration"])}
    return pd.DataFrame([results[t["id"]] for t in tasks])


def main():
    OUT.mkdir(exist_ok=True)
    df = schedule(tasks, project_start)
    df.to_csv(OUT / "first_schedule.csv", index=False)
    fig = px.timeline(df, x_start="start", x_end="finish", y="task", hover_data=["id", "duration", "depends"],
                      title="PMI - first Gantt (illustrative activities and durations)")
    fig.update_yaxes(autorange="reversed")
    fig.write_html(OUT / "first_gantt.html", include_plotlyjs="cdn")
    print(df.to_string(index=False))
    print(f"\nProject finish: {df['finish'].max():%Y-%m-%d}  ({(df['finish'].max() - project_start).days} calendar days)")
    print(f"Saved {OUT / 'first_schedule.csv'} and {OUT / 'first_gantt.html'}")


if __name__ == "__main__":
    main()
