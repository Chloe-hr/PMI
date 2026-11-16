"""
Shared graph schema for the PMI duration GNN
============================================
Every data source (DSLIB/Ghent real projects, PMI-generated schedules from IFC, future company data)
is first turned into the SAME generic activity table, then into the SAME graph:

    activity table columns
        activity_id   unique within the project
        name          free text (used only to derive `category`)
        planned_days  baseline / rule-based duration (> 0 for work activities)
        predecessors  ';'-joined activity_ids (finish-to-start)
        category      trade category from CATEGORIES (derived from name if missing)
        actual_days   real duration - the LABEL (NaN when unknown, e.g. PMI predictions)

    graph
        nodes  = activities with planned_days > 0 (milestones / summaries removed, links bridged)
        edges  = precedence, both directions, edge_attr = [is_forward, is_backward]
        x      = node features (FEATURES below) - only information available BEFORE construction
        y      = log(actual_days / planned_days)   -> the model learns the deviation from plan
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from schedule_engine import Network, cpm  # noqa: E402

# Trade vocabulary shared by all sources. Keywords: English + Dutch + French (DSLIB projects are Belgian).
CATEGORIES = {
    "preliminaries": ["mobilis", "site setup", "werfinrichting", "werfinstallatie", "installation de chantier",
                      "preparat", "voorbereid", "permit", "vergunning", "werfkeet", "bouwplaats", "stelling", "scaffold", "kraan", "crane", "design", "ontwerp", "studie", "study"],
    "earthworks":    ["excavat", "earthwork", "grondwerk", "uitgraving", "terrassement", "demoli", "afbraak",
                      "sloop", "backfill", "grond", "aanvulling", "nivellering"],
    "foundations":   ["foundation", "footing", "fundering", "funder", "pile", "paal", "palen", "fondation",
                      "sous-sol", "basement", "kelder", "kelderwand", "sokkel", "drainage"],
    "structure":     ["concrete", "beton", "béton", "structur", "ruwbouw", "skeleton", "column", "kolom",
                      "beam", "balk", "slab", "vloerplaat", "welfsel", "floor structure", "steel", "staal",
                      "timber frame", "houtskelet", "gros oeuvre", "stair", "trap", "bekist", "storten", "wapening", "reinforc", "formwork", "plaat ", "kolommen", "ligger", "prefab", "breedplaat", "koker", "dragende"],
    "masonry":       ["masonry", "metselwerk", "brick", "baksteen", "block", "blok", "maçonnerie", "wall", "muur",
                      "gevel", "facade", "façade", "cladding", "bekleding", "wanden", "parement", "snelbouw", "isolatie", "insulation", "spouw", "voeg"],
    "roofing":       ["roof", "dak", "toiture", "zinc", "zink", "gutter", "goot", "dakdicht", "roofing", "pannen", "tiles roof", "epdm", "bitumen"],
    "openings":      ["window", "raam", "ramen", "schrijnwerk", "joinery", "door", "deur", "glazing",
                      "beglazing", "menuiserie", "curtain wall", "vliesgevel", "buitenschrijnwerk", "poort", "gate", "chassis"],
    "services":      ["hvac", "mep", "electric", "elektri", "plumb", "sanitair", "sanitary", "heating",
                      "verwarming", "ventilat", "lift", "elevator", "technieken", "installaties", "chauffage",
                      "techniques", "sprinkler", "fire protection", "elektr", " bad ", "douche", " wc ", "toilet", "convector", "radiator", "brandmeld", "sirene", "alarm", "verlicht", "lighting", "data", "leiding", "piping", "afvoer", "water", " gas ", "ketel", "boiler", "warmtepomp", "kabel", "cable", "zonnepan", "solar", "domotica"],
    "interiors":     ["partition", "scheidingswand", "plaster", "pleister", "drywall", "gyproc", "ceiling",
                      "plafond", "screed", "chape", "dekvloer", "tiling", "tegel", "floor finish", "vloer",
                      "paint", "schilder", "peinture", "finish", "afwerking", "parket", "parquet", "carpentry",
                      "kitchen", "keuken", "fit-out", "furnish", "inricht", "binnenschrijnwerk", "chape", "bezetting", "gyproc", "trapleuning", "binnendeur", "vloerbekleding", "faience", "plinten", "silicon"],
    "external":      ["landscap", "external work", "omgevingswerk", "paving", "riolering", "sewer", "road",
                      "parking", "garden", "tuin", "abords"],
    "handover":      ["handover", "oplevering", "réception", "inspection", "keuring", "commission", "cleaning",
                      "opkuis", "snag"],
}
CATEGORY_LIST = list(CATEGORIES) + ["other"]

# PMI work packages (research/ifc_to_gantt/task_rules.json) -> shared categories
PMI_PACKAGE_CATEGORY = {
    "MOB": "preliminaries", "FTG": "foundations", "FWL": "foundations", "GSL": "structure",
    "STL": "structure", "TFL": "structure", "STR": "structure", "EXW": "masonry", "IBW": "masonry",
    "ROF": "roofing", "WIN": "openings", "DOR": "openings", "PRT": "interiors", "CLG": "interiors",
    "FLF": "interiors", "FIT": "interiors", "HND": "handover",
}

FEATURES = (
    ["log_planned_days", "planned_share", "rel_early_start", "rel_total_float", "is_critical",
     "log_in_degree", "log_out_degree", "rel_depth", "log_project_activities", "log_project_days"]
    + [f"cat_{c}" for c in CATEGORY_LIST]
)


def categorize(name: str) -> str:
    """First category whose keyword appears in the activity name; 'other' otherwise."""
    n = f" {str(name).lower()} "
    for cat, words in CATEGORIES.items():
        if any(w in n for w in words):
            return cat
    return "other"


def bridge_zero_duration(acts: pd.DataFrame) -> pd.DataFrame:
    """Drop milestones / zero-duration rows but keep their precedence: A -> M -> B becomes A -> B."""
    acts = acts.copy()
    preds = {r.activity_id: [p for p in str(r.predecessors or "").split(";") if p] for r in acts.itertuples()}
    keep = set(acts.loc[acts["planned_days"] > 0, "activity_id"])
    ids = set(preds)

    def resolve(p, seen):
        if p in keep:
            return {p}
        if p not in ids or p in seen:
            return set()
        seen.add(p)
        out = set()
        for q in preds[p]:
            out |= resolve(q, seen)
        return out

    acts = acts[acts["activity_id"].isin(keep)].copy()
    acts["predecessors"] = [";".join(sorted(set().union(*[resolve(p, set()) for p in preds[a]]) - {a}))
                            if preds[a] else "" for a in acts["activity_id"]]
    return acts


def node_features(acts: pd.DataFrame) -> pd.DataFrame:
    """Features known at planning time, computed with PMI's own CPM on the PLANNED durations."""
    acts = bridge_zero_duration(acts.reset_index(drop=True))
    if "category" not in acts or acts["category"].isna().any():
        cats = acts["name"].map(categorize)
        acts["category"] = acts["category"].fillna(cats) if "category" in acts else cats
    net = pd.DataFrame({
        "id": acts["activity_id"], "activity": acts["name"], "phase": acts["category"],
        "duration_days": np.maximum(1, np.round(acts["planned_days"])).astype(int),
        "predecessors": [[p for p in s.split(";") if p] for s in acts["predecessors"]],
    })
    s = cpm(Network(activities=net)).set_index("id").loc[acts["activity_id"]]
    total = max(1, int(s["EF"].max()))
    indeg = net["predecessors"].map(len).to_numpy()
    succ = {i: 0 for i in net["id"]}
    for ps in net["predecessors"]:
        for p in ps:
            succ[p] += 1
    depth = {}                                          # longest chain of predecessors (cpm checked acyclicity)
    order = list(s.sort_values(["ES", "EF"]).index)     # zero-lag FS: predecessors always have smaller ES
    pmap = dict(zip(net["id"], net["predecessors"]))
    for i in order:
        depth[i] = 1 + max((depth[p] for p in pmap[i] if p in depth), default=0)
    maxdepth = max(depth.values())

    f = pd.DataFrame(index=acts.index)
    f["log_planned_days"] = np.log1p(acts["planned_days"].to_numpy())
    f["planned_share"] = acts["planned_days"].to_numpy() / total
    f["rel_early_start"] = s["ES"].to_numpy() / total
    f["rel_total_float"] = s["float"].to_numpy() / total
    f["is_critical"] = s["critical"].astype(float).to_numpy()
    f["log_in_degree"] = np.log1p(indeg)
    f["log_out_degree"] = np.log1p([succ[i] for i in net["id"]])
    f["rel_depth"] = [depth[i] / maxdepth for i in net["id"]]
    f["log_project_activities"] = math.log(len(acts))
    f["log_project_days"] = math.log(total)
    for c in CATEGORY_LIST:
        f[f"cat_{c}"] = (acts["category"] == c).astype(float).to_numpy()
    acts = acts.reset_index(drop=True)
    f = f.reset_index(drop=True)
    return acts, f[FEATURES]


def to_graph(acts: pd.DataFrame, project_id: str):
    """-> torch_geometric.data.Data with x, edge_index, edge_attr, y (NaN where unlabelled), planned, ids."""
    import torch
    from torch_geometric.data import Data

    acts, f = node_features(acts)
    idx = {a: i for i, a in enumerate(acts["activity_id"])}
    src, dst = [], []
    for a, ps in zip(acts["activity_id"], acts["predecessors"]):
        for p in filter(None, ps.split(";")):
            src.append(idx[p]); dst.append(idx[a])
    ei = torch.tensor([src + dst, dst + src], dtype=torch.long)
    ea = torch.tensor([[1.0, 0.0]] * len(src) + [[0.0, 1.0]] * len(src), dtype=torch.float)
    planned = torch.tensor(acts["planned_days"].to_numpy(), dtype=torch.float)
    actual = torch.tensor(pd.to_numeric(acts.get("actual_days", np.nan), errors="coerce")
                          .reindex(acts.index).to_numpy(dtype=float), dtype=torch.float)
    y = torch.log(actual / planned)
    y[~torch.isfinite(y)] = float("nan")
    return Data(x=torch.tensor(f.to_numpy(), dtype=torch.float), edge_index=ei.reshape(2, -1), edge_attr=ea,
                y=y, planned=planned, project_id=project_id, activity_ids=list(acts["activity_id"]),
                names=list(acts["name"]), categories=list(acts["category"]))


def from_pmi_folder(folder: Path) -> pd.DataFrame:
    """PMI pipeline output (tasks.csv from research/ifc_to_gantt) -> generic activity table (no labels)."""
    t = pd.read_csv(Path(folder) / "tasks.csv").fillna({"predecessors": ""})
    return pd.DataFrame({"activity_id": t["id"], "name": t["name"], "planned_days": t["duration_days"].astype(float),
                         "predecessors": t["predecessors"], "category": t["package"].map(PMI_PACKAGE_CATEGORY),
                         "actual_days": np.nan})
