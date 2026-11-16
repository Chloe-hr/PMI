"""
Stage 3.7 - Cambridge activity graphs for GraphSAGE (development blocks only).

    python research/gnn/cambridge_graph.py          # verify frozen inputs, extract graphs + feasibility diagnostics

What this module does
    1. Verifies the raw Cambridge JSON and the frozen Stage 2.3D design artifacts against their checksums.
    2. Streams the raw JSON once and keeps ONLY development projects (every eligible row split == 'train').
       Projects owning locked test blocks are skipped before any of their activities are read into a graph.
    3. Writes data/processed/gnn_cambridge/{nodes.csv, edges.csv, graph_manifest.json, feasibility_diagnostics.json}.
    4. Builds one torch_geometric graph per development project with fold-fitted node features.

Relationship policy (see research/gnn/cambridge_graph_feasibility.md)
    * Edge predecessor -> successor from Activity_Relationships[*].Predecessor_ID, resolved INSIDE the project only.
    * All precedence types (FS/SS/FF/SF) are kept as one directed relation; Lag (unit unverified) and
      Predecessor_GMM_Classification (corpus-fit topic) are never read into the graph.
    * Self-loops are dropped; predecessor IDs that do not resolve inside the project are dropped (task IDs collide
      across projects, so cross-project resolution is not trustworthy).
    * Nodes = every exported activity of the project, regardless of completion status, so the graph is not selected
      on a post-execution outcome. Only frozen eligible development rows carry a label.
    * Node inputs = activity_description, project_type, uk_region (the frozen Stage 2.3E allowlist). Descriptions
      matching the Stage 2.3C explicit-outcome phrase rule are blanked on unlabelled nodes.
    Diagnostic-only fields (completion %, actual dates) are used to audit the edges and are never written to nodes.csv.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "data/processed/stage2/cambridge_experiment_design"
RAW_JSON = ROOT / "data/raw/cambridge/JPF_Anonymised_Project_Data.json"
OUT = ROOT / "data/processed/gnn_cambridge"
FEATURES = ("activity_description", "project_type", "uk_region")
TARGET = "reported_completed_activity_elapsed_calendar_days"
DEV_ROWS, TEST_ROWS, DEV_BLOCKS, TEST_BLOCKS = 144110, 36027, 70, 99
# identical to training/review_cambridge_feasibility.py (Stage 2.3C)
OUTCOME_TEXT = re.compile(r"\b(?:actual duration|completed on|finished on|as[ -]built|delay of)\b", re.I)
FROZEN_FILES = ("split_manifest_conservative.csv", "feature_matrix.csv", "exploratory_targets.csv")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_frozen_inputs(check_raw: bool = True) -> dict:
    """Raise unless the frozen Stage 2.3D artifacts (and optionally the raw JSON) match design_freeze.json."""
    freeze = json.loads((DESIGN / "design_freeze.json").read_text(encoding="utf-8"))
    hashes = {}
    for name in FROZEN_FILES:
        got = sha256(DESIGN / name)
        if got != freeze["outputs"][name]:
            raise RuntimeError(f"Frozen Stage 2.3D artifact changed: {name}")
        hashes[name] = got
    if check_raw:
        expected = freeze["protected_inputs"]["data/raw/cambridge/JPF_Anonymised_Project_Data.json"]
        got = sha256(RAW_JSON)
        if got != expected:
            raise RuntimeError("Raw Cambridge JSON does not match its frozen checksum")
        hashes["JPF_Anonymised_Project_Data.json"] = got
    return hashes


def load_labels() -> pd.DataFrame:
    """Frozen eligible rows: split, block, fold, features and target. Refuses drifted counts."""
    read = lambda n: pd.read_csv(DESIGN / n, dtype=str, keep_default_na=False)  # noqa: E731
    split, feats, tgt = read("split_manifest_conservative.csv"), read("feature_matrix.csv"), read("exploratory_targets.csv")
    keys = ["composite_activity_key", "project_key", "activity_key"]
    df = split.merge(feats, on=keys, validate="one_to_one").merge(tgt, on=keys, validate="one_to_one")
    if (df.split.eq("train").sum(), df.split.eq("test").sum()) != (DEV_ROWS, TEST_ROWS):
        raise RuntimeError("Frozen primary allocation counts changed")
    sides = df.groupby("conservative_block_id").split.nunique()
    if (sides > 1).any():
        raise RuntimeError("A conservative block crosses the frozen split")
    df[TARGET] = df[TARGET].astype(float)
    return df


def development_projects(labels: pd.DataFrame) -> set[str]:
    sides = labels.groupby("project_key").split.agg(set)
    if any(len(s) > 1 for s in sides):
        raise RuntimeError("A project has rows on both sides of the frozen split")
    dev = {p for p, s in sides.items() if s == {"train"}}
    test = {p for p, s in sides.items() if s == {"test"}}
    assert not dev & test
    return dev


def _date(s):
    try:
        return datetime.fromisoformat(str(s).strip())
    except (TypeError, ValueError):
        return None


def _complete(a) -> bool:
    return str(a.get("Physical_Percent_Complete", "")).strip() in ("100", "100.0")


def extract(out: Path = OUT, raw: Path = RAW_JSON) -> dict:
    """Stream the raw JSON; write nodes/edges for development projects and the feasibility diagnostics."""
    import ijson
    from scipy.stats import spearmanr

    labels = load_labels()
    dev_projects = development_projects(labels)
    dev_labels = labels[labels.split == "train"]
    lab_index = {(r.project_key, r.activity_key): r for r in dev_labels.itertuples()}
    block_of_project = dev_labels.groupby("project_key").conservative_block_id.agg(set)
    if (block_of_project.map(len) > 1).any():
        raise RuntimeError("A development project spans several conservative blocks")
    block_of_project = block_of_project.map(lambda s: next(iter(s))).to_dict()
    fold_of_block = dev_labels.groupby("conservative_block_id").development_validation_fold.agg(set)
    if (fold_of_block.map(len) > 1).any():
        raise RuntimeError("A block spans several development folds")
    fold_of_block = fold_of_block.map(lambda s: next(iter(s))).to_dict()

    nodes, edges, diag = [], [], Counter()
    by_completion = defaultdict(lambda: Counter())
    seen_projects, skipped_test = set(), 0
    with raw.open("rb") as f:
        for pk, proj in ijson.kvitems(f, "Projects", use_float=True):
            pk = str(pk).strip()
            if pk not in dev_projects:
                skipped_test += pk in set(labels.project_key)   # test project or ineligible: never materialised
                continue
            seen_projects.add(pk)
            acts = {str(k).strip(): a for k, a in proj["Activities"].items()}
            block = block_of_project[pk]
            pairs = set()
            for ak, a in acts.items():
                desc = a.get("Activity_Description")
                desc = "" if desc is None else str(desc)
                lab = lab_index.get((pk, ak))
                masked = lab is None and bool(OUTCOME_TEXT.search(desc))
                if lab is not None and lab.activity_description != desc:
                    raise RuntimeError(f"Raw description differs from frozen feature_matrix for {(pk, ak)}")
                nodes.append(dict(project_key=pk, activity_key=ak, conservative_block_id=block,
                                  development_validation_fold=fold_of_block[block],
                                  activity_description="" if masked else desc,
                                  project_type=str(proj.get("Project_Type") or ""), uk_region=str(proj.get("UK_Region") or ""),
                                  labelled=lab is not None, description_masked=masked))
                rel = a.get("Activity_Relationships")
                comp = "complete" if _complete(a) else "not_complete"
                by_completion[comp]["activities"] += 1
                by_completion[comp]["relationship_map_missing"] += not isinstance(rel, dict)
                if not isinstance(rel, dict):
                    diag["relationship_map_missing"] += 1
                    continue
                for r in rel.values():
                    diag["relationship_records"] += 1
                    pid, rtype = str(r.get("Predecessor_ID", "")).strip(), str(r.get("Relationship_Type", "")).strip()
                    diag[f"type_{rtype}"] += 1
                    if pid == ak:
                        diag["self_loops_dropped"] += 1
                        continue
                    if pid not in acts:
                        diag["unresolved_or_cross_project_dropped"] += 1
                        continue
                    if (pid, ak) in pairs:
                        diag["duplicate_pairs_dropped"] += 1
                        continue
                    pairs.add((pid, ak))
                    by_completion[comp]["intra_predecessors"] += 1
                    edges.append(dict(project_key=pk, predecessor_key=pid, successor_key=ak, relationship_type=rtype))
                    # audit only: is the logic an as-built reconstruction? (successor started before FS predecessor finished)
                    p = acts[pid]
                    pf, ss = _date(p.get("Actual_Finish_Date")), _date(a.get("Actual_Start_Date"))
                    if rtype == "PR_FS" and pf and ss and _complete(p):
                        diag["fs_pairs_with_actuals"] += 1
                        diag["fs_successor_started_before_predecessor_finished"] += ss < pf
                        diag["fs_successor_started_more_than_1d_early"] += (pf - ss).total_seconds() > 86400
            diag["intra_project_edges"] = len(edges)

    if seen_projects != dev_projects:
        raise RuntimeError(f"Development projects missing from raw JSON: {sorted(dev_projects - seen_projects)[:5]}")
    nodes, edges = pd.DataFrame(nodes), pd.DataFrame(edges)
    if nodes.duplicated(["project_key", "activity_key"]).any():
        raise RuntimeError("Duplicate node keys")
    if int(nodes.labelled.sum()) != DEV_ROWS:
        raise RuntimeError("Not every frozen development row became a labelled node")

    # topology diagnostics on labelled development rows (targets used only for this association check)
    indeg = edges.groupby(["project_key", "successor_key"]).size()
    outdeg = edges.groupby(["project_key", "predecessor_key"]).size()
    lab = nodes[nodes.labelled][["project_key", "activity_key"]].merge(
        dev_labels[["project_key", "activity_key", TARGET]], on=["project_key", "activity_key"], validate="one_to_one")
    k = list(zip(lab.project_key, lab.activity_key))
    lab["in_degree"] = [int(indeg.get(x, 0)) for x in k]
    lab["out_degree"] = [int(outdeg.get(x, 0)) for x in k]
    lab["isolated"] = (lab.in_degree == 0) & (lab.out_degree == 0)

    import networkx as nx
    cyc_projects, cyc_nodes = 0, 0
    for pk, e in edges.groupby("project_key"):
        g = nx.DiGraph(list(zip(e.predecessor_key, e.successor_key)))
        if not nx.is_directed_acyclic_graph(g):
            cyc_projects += 1
            cyc_nodes += sum(len(c) for c in nx.strongly_connected_components(g) if len(c) > 1)

    comp = {c: dict(v) | {"missing_map_rate": v["relationship_map_missing"] / v["activities"],
                          "mean_intra_predecessors": v["intra_predecessors"] / v["activities"]}
            for c, v in by_completion.items()}
    diagnostics = {
        "scope": "development projects only; locked test projects were skipped while streaming",
        "development_projects": len(dev_projects), "development_blocks": int(nodes.conservative_block_id.nunique()),
        "nodes": len(nodes), "labelled_nodes": int(nodes.labelled.sum()),
        "unlabelled_descriptions_masked_outcome_phrase": int(nodes.description_masked.sum()),
        "largest_project_nodes": int(nodes.groupby("project_key").size().max()),
        "counts": dict(diag),
        "fs_violation_rate": diag["fs_successor_started_before_predecessor_finished"] / max(1, diag["fs_pairs_with_actuals"]),
        "fs_violation_rate_gt_1d": diag["fs_successor_started_more_than_1d_early"] / max(1, diag["fs_pairs_with_actuals"]),
        "by_completion_status": comp,
        "labelled_with_predecessor": float((lab.in_degree > 0).mean()),
        "labelled_with_successor": float((lab.out_degree > 0).mean()),
        "labelled_isolated": float(lab.isolated.mean()),
        "spearman_in_degree_vs_target": float(spearmanr(lab.in_degree, lab[TARGET]).statistic),
        "spearman_out_degree_vs_target": float(spearmanr(lab.out_degree, lab[TARGET]).statistic),
        "median_target_isolated_vs_connected": [float(lab[lab.isolated][TARGET].median()),
                                                float(lab[~lab.isolated][TARGET].median())],
        "projects_with_cycles": cyc_projects, "nodes_in_cycles": cyc_nodes,
        "isolated_labelled_by_fold": lab.merge(dev_labels[["project_key", "activity_key", "development_validation_fold"]])
            .groupby("development_validation_fold").isolated.mean().round(4).to_dict(),
    }
    out.mkdir(parents=True, exist_ok=True)
    nodes.to_csv(out / "nodes.csv", index=False)
    edges.to_csv(out / "edges.csv", index=False)
    (out / "feasibility_diagnostics.json").write_text(json.dumps(diagnostics, indent=2, default=int) + "\n", encoding="utf-8")
    manifest = {
        "stage": "3.7", "inputs_sha256": verify_frozen_inputs(check_raw=True),
        "outputs_sha256": {n: sha256(out / n) for n in ("nodes.csv", "edges.csv")},
        "edge_policy": "intra-project Predecessor_ID -> activity; all relationship types; lag/GMM unused; self-loops, "
                       "duplicates and unresolved IDs dropped",
        "node_policy": "all exported activities of development projects; labels only on frozen eligible development rows",
        "test_projects_materialised": 0, "skipped_labelled_non_development_projects": skipped_test,
    }
    (out / "graph_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return diagnostics


def load_cached(out: Path = OUT) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """nodes, edges and frozen development labels; verifies the cache against its manifest."""
    manifest = json.loads((out / "graph_manifest.json").read_text(encoding="utf-8"))
    for n, h in manifest["outputs_sha256"].items():
        if sha256(out / n) != h:
            raise RuntimeError(f"Graph cache drifted: {n}")
    hashes = verify_frozen_inputs(check_raw=False)
    for n in FROZEN_FILES:
        if manifest["inputs_sha256"][n] != hashes[n]:
            raise RuntimeError("Graph cache was built from different frozen inputs")
    nodes = pd.read_csv(out / "nodes.csv", dtype=str, keep_default_na=False)
    nodes["labelled"] = nodes.labelled.eq("True")
    edges = pd.read_csv(out / "edges.csv", dtype=str, keep_default_na=False)
    labels = load_labels()
    dev = labels[labels.split == "train"].copy()
    test_projects = set(labels[labels.split == "test"].project_key)
    if set(nodes.project_key) & test_projects:
        raise RuntimeError("Locked test project found in graph cache")
    return nodes, edges, dev


# ----------------------------------------------------------------------------------------------- features + graphs
class FoldFeaturizer:
    """TF-IDF(description) -> SVD(128) -> standardise, plus one-hot project_type / uk_region.
    Fitted on the nodes of the fold's fitting projects only."""

    def __init__(self, seed: int, n_components: int = 128):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
        self.tfidf = TfidfVectorizer(max_features=50000, ngram_range=(1, 2), min_df=2, max_df=0.98,
                                     sublinear_tf=True, dtype=np.float32)
        self.svd = TruncatedSVD(n_components=n_components, random_state=seed, n_iter=5)
        self.scaler = StandardScaler()
        self.onehot = OneHotEncoder(handle_unknown="ignore", dtype=np.float32, sparse_output=False)

    def fit(self, df: pd.DataFrame):
        z = self.svd.fit_transform(self.tfidf.fit_transform(df.activity_description))
        self.scaler.fit(z)
        self.onehot.fit(df[["project_type", "uk_region"]])
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        z = self.scaler.transform(self.svd.transform(self.tfidf.transform(df.activity_description)))
        return np.hstack([z, self.onehot.transform(df[["project_type", "uk_region"]])]).astype(np.float32)


def build_graphs(nodes: pd.DataFrame, edges: pd.DataFrame, dev: pd.DataFrame, featurizer: FoldFeaturizer,
                 projects=None) -> list:
    """One torch_geometric Data per project. y = log1p(days) on labelled nodes, NaN elsewhere."""
    import torch
    from torch_geometric.data import Data
    target = dict(zip(zip(dev.project_key, dev.activity_key), dev[TARGET].astype(float)))
    sel = nodes if projects is None else nodes[nodes.project_key.isin(projects)]
    e_by = dict(tuple(edges.groupby("project_key")))
    graphs = []
    for pk, n in sel.groupby("project_key", sort=True):
        n = n.reset_index(drop=True)
        idx = {a: i for i, a in enumerate(n.activity_key)}
        e = e_by.get(pk)
        if e is not None and len(e):
            ei = np.array([[idx[p] for p in e.predecessor_key], [idx[s] for s in e.successor_key]], dtype=np.int64)
        else:
            ei = np.zeros((2, 0), dtype=np.int64)
        y = np.array([np.log1p(target[(pk, a)]) if l else np.nan for a, l in zip(n.activity_key, n.labelled)],
                     dtype=np.float32)
        g = Data(x=torch.from_numpy(featurizer.transform(n)), edge_index=torch.from_numpy(ei), y=torch.from_numpy(y))
        g.project_key = pk
        g.block_id = n.conservative_block_id.iloc[0]
        g.fold = int(n.development_validation_fold.iloc[0])
        g.activity_keys = list(n.activity_key)
        graphs.append(g)
    return graphs


if __name__ == "__main__":
    d = extract()
    print(json.dumps(d, indent=2, default=int))
