"""
Dataset loaders -> list of torch_geometric graphs (see graph_schema.py).

    synthetic  random building-like schedules with KNOWN label rules - a pipeline test, never a result
    dslib      real Belgian building projects (Ghent DSLIB, data/raw/ghent): planned vs actual per activity
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from graph_schema import ROOT, to_graph

# typical trade order for synthetic projects
_SEQ = ["preliminaries", "earthworks", "foundations", "structure", "masonry", "roofing", "openings",
        "services", "interiors", "external", "handover"]
_CAT_EFFECT = {"preliminaries": 0.0, "earthworks": 0.10, "foundations": 0.15, "structure": 0.10, "masonry": 0.05,
               "roofing": 0.08, "openings": 0.20, "services": 0.25, "interiors": 0.12, "external": 0.05,
               "handover": 0.0}


def synthetic_project(rng: np.random.Generator, pid: str) -> pd.DataFrame:
    """Storey-wise trade chains with cross links. Label rule (hidden from the model):
        log(actual/planned) = trade effect
                            + 0.25 * (mean log planned duration of predecessors - 2)        (needs neighbours)
                            + 0.25 * (max planned duration of successors > 15 days)        (needs neighbours)
                            + noise
    Predecessor / successor durations are random and NOT visible in a node's own features, so only
    message passing can recover them: the GNN should beat the MLP here, or the graph layers are broken."""
    storeys = int(rng.integers(1, 6))
    rows, prev_by_cat, last = [], {}, None
    aid = 0

    def add(name, cat, days, preds):
        nonlocal aid
        aid += 1
        rows.append({"activity_id": f"A{aid}", "name": name, "category": cat, "planned_days": float(days),
                     "predecessors": ";".join(sorted(set(p for p in preds if p)))})
        return f"A{aid}"

    start = add("Site set-up", "preliminaries", rng.integers(3, 10), [])
    exc = add("Excavation", "earthworks", rng.integers(3, 15), [start])
    fnd = add("Foundations", "foundations", rng.integers(5, 25), [exc])
    below = {"structure": fnd}
    finishes = []
    for s in range(storeys):
        st = add(f"Structure L{s}", "structure", rng.integers(5, 20), [below["structure"]])
        ms = add(f"Masonry L{s}", "masonry", rng.integers(5, 25), [st, below.get("masonry")])
        op = add(f"Windows L{s}", "openings", rng.integers(2, 10), [ms])
        sv = add(f"Services L{s}", "services", rng.integers(5, 20), [st] + ([op] if rng.random() < 0.5 else []))
        it = add(f"Interiors L{s}", "interiors", rng.integers(5, 25), [sv, ms] + ([op] if rng.random() < 0.6 else []))
        below = {"structure": st, "masonry": ms}
        finishes.append(it)
    rf = add("Roof", "roofing", rng.integers(5, 15), [below["structure"], below["masonry"]])
    ext = add("External works", "external", rng.integers(5, 20), [rf])
    add("Handover", "handover", rng.integers(3, 8), finishes + [ext, rf])
    df = pd.DataFrame(rows)

    preds = {r.activity_id: [p for p in r.predecessors.split(";") if p] for r in df.itertuples()}
    succs = {a: [b for b, ps in preds.items() if a in ps] for a in df.activity_id}
    plan = dict(zip(df.activity_id, df.planned_days))
    logr = []
    for r in df.itertuples():
        ps, ss = preds[r.activity_id], succs[r.activity_id]
        pred_term = (np.mean([np.log(plan[p]) for p in ps]) - 2.0) if ps else 0.0
        succ_term = float(max((plan[s] for s in ss), default=0) > 15)
        logr.append(_CAT_EFFECT[r.category] + 0.25 * pred_term + 0.25 * succ_term + rng.normal(0, 0.05))
    df["actual_days"] = df.planned_days * np.exp(logr)
    return df


def load_synthetic(n: int = 120, seed: int = 0):
    rng = np.random.default_rng(seed)
    return [to_graph(synthetic_project(rng, f"SYN{i:03d}"), f"SYN{i:03d}") for i in range(n)]


def load(source: str):
    if source == "synthetic":
        return load_synthetic()
    if source == "dslib":
        from dslib import load_dslib
        return load_dslib()
    if source == "dslib_filtered":
        from dslib import load_dslib
        return load_dslib(filtered=True)
    raise ValueError(source)
