"""
Ghent DSLIB building projects -> generic activity tables with REAL activity-level labels.

Source: data/raw/ghent/construction_excel/*.xlsx (Vanhoucke & Servranckx, DSLIB v3.4), read-only.

Per project
    nodes/edges   'Baseline Schedule' sheet: leaf activities (WBS summaries removed), Predecessors column
    planned_days  baseline 'Duration'  ("22d 4h" -> 22.5 at 8 h/day)
    actual_days   'Actual Duration' in the LAST tracking-period sheet (TPn), only where Remaining Duration = 0

Inclusion (same rule as the Stage 2 audit): Project AND Tracking authenticity both 'G' in
DSLIB_Analysis_Sheet.xlsx, at least one TP sheet, and >= 5 labelled activities.

Simplifications (documented, see README): all relation types (FS/SS/FF/SF) are kept as graph edges but
the planning-time CPM features treat them as finish-to-start; lags are ignored. Hours/day assumed 8 -
the label is a RATIO of actual to planned in the same unit, so this assumption mostly cancels.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from graph_schema import ROOT, to_graph

SRC = ROOT / "data" / "raw" / "ghent" / "construction_excel"
CACHE = ROOT / "data" / "processed" / "gnn_dslib"
HOURS_PER_DAY = 8.0
_PRED = re.compile(r"^\s*(\d+)\s*(FS|SS|FF|SF)?", re.I)


def parse_duration(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower()
    if s in ("", "0"):
        return 0.0
    total, found = 0.0, False
    for num, unit in re.findall(r"([\d.,]+)\s*(w|d|h|m)", s):
        n = float(num.replace(",", "."))
        total += {"w": 5.0, "d": 1.0, "h": 1 / HOURS_PER_DAY, "m": 1 / (60 * HOURS_PER_DAY)}[unit] * n
        found = True
    return total if found else None


def _table(ws) -> pd.DataFrame:
    rows = list(ws.iter_rows(values_only=True))
    h = next(i for i, r in enumerate(rows) if r and r[0] == "ID")
    hdr = [str(c).strip() if c is not None else f"col{j}" for j, c in enumerate(rows[h])]
    return pd.DataFrame([r[:len(hdr)] for r in rows[h + 1:] if r and r[0] is not None], columns=hdr)


def authenticity() -> dict:
    from openpyxl import load_workbook
    wb = load_workbook(SRC / "DSLIB_Analysis_Sheet.xlsx", read_only=True, data_only=True)
    rows = list(wb["DSLIB"].iter_rows(values_only=True))
    h = next(i for i, r in enumerate(rows) if r and "Code" in r)
    hdr = list(rows[h])
    c, p, t, s = (hdr.index(k) for k in ("Code", "Project", "Tracking", "Sector"))
    return {str(r[c]).strip(): {"project": r[p], "tracking": r[t], "sector": r[s]}
            for r in rows[h + 1:] if r and r[c]}


def read_project(path: Path) -> tuple[pd.DataFrame, dict]:
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    base = _table(wb["Baseline Schedule"])
    tps = sorted((int(m.group(1)), n) for n in wb.sheetnames if (m := re.fullmatch(r"TP\s*(\d+)\s*", n)))
    info = {"file": path.name, "tracking_periods": len(tps)}
    if not tps:
        return pd.DataFrame(), info | {"skip": "no tracking periods"}
    last = _table(wb[tps[-1][1]])

    base["ID"] = base["ID"].astype(int).astype(str)
    base["WBS"] = base["WBS"].map(lambda v: "" if pd.isna(v) else str(v).strip())
    wbs = {w for w in base["WBS"] if w}
    is_summary = base["WBS"].map(lambda w: bool(w) and any(o.startswith(w + ".") for o in wbs))
    acts = base[~is_summary].copy()
    acts["planned_days"] = acts["Duration"].map(parse_duration)
    acts["predecessors"] = acts["Predecessors"].fillna("").map(
        lambda s: ";".join(m.group(1) for part in str(s).split(";") if (m := _PRED.match(part))))

    last["ID"] = last["ID"].astype(int).astype(str)
    last["actual"] = last["Actual Duration"].map(parse_duration)
    last["remaining"] = last["Remaining Duration"].map(parse_duration)
    done = last[(last["remaining"] == 0) & (last["actual"] > 0)].set_index("ID")["actual"]
    acts["actual_days"] = acts["ID"].map(done)
    acts.loc[acts["planned_days"].fillna(0) <= 0, "actual_days"] = np.nan

    keep = set(acts["ID"])                   # predecessors pointing at summaries are dropped
    acts["predecessors"] = acts["predecessors"].map(lambda s: ";".join(p for p in s.split(";") if p in keep))
    out = pd.DataFrame({"activity_id": acts["ID"], "name": acts["Name"].astype(str),
                        "planned_days": acts["planned_days"].fillna(0.0), "predecessors": acts["predecessors"],
                        "actual_days": acts["actual_days"]})
    info |= {"activities": int((out.planned_days > 0).sum()), "labelled": int(out.actual_days.notna().sum())}
    return out, info


def build_cache(min_labelled: int = 5) -> pd.DataFrame:
    auth = authenticity()
    CACHE.mkdir(parents=True, exist_ok=True)
    manifest, tables = [], []
    for f in sorted(SRC.glob("C20*.xlsx")):
        code = f.name[:8]
        a = auth.get(code, {})
        row = {"project_id": code, "name": f.stem[9:], "sector": a.get("sector"),
               "auth_project": a.get("project"), "auth_tracking": a.get("tracking")}
        if not (a.get("project") == "G" and a.get("tracking") == "G"):
            manifest.append(row | {"included": False, "reason": "authenticity not G/G"})
            continue
        try:
            t, info = read_project(f)
        except Exception as e:  # noqa: BLE001 - report and continue; never silently include
            manifest.append(row | {"included": False, "reason": f"parse error: {e}"})
            continue
        row |= info
        if info.get("skip") or info.get("labelled", 0) < min_labelled:
            manifest.append(row | {"included": False, "reason": info.get("skip") or "too few labelled activities"})
            continue
        manifest.append(row | {"included": True, "reason": ""})
        tables.append(t.assign(project_id=code))
    pd.concat(tables).to_csv(CACHE / "activities.csv", index=False)
    m = pd.DataFrame(manifest)
    m.to_csv(CACHE / "manifest.csv", index=False)
    return m


RELATED = ROOT / "data" / "processed" / "stage2" / "ghent_related_projects_review.csv"


def project_groups() -> dict:
    """Stage 2 audit's conservative grouping: projects with related names stay in the same CV fold."""
    groups = {}
    if RELATED.is_file():
        for r in pd.read_csv(RELATED).itertuples():
            for pid in str(r.project_ids).split(";"):
                groups[pid.strip()] = r.review_group_id
    return groups


FILTER_RULES = {  # sensitivity variant - declared before looking at model results
    "drop_project_if_exact_on_plan_share_at_least": 0.9,   # tracking likely mirrors the baseline
    "unlabel_activity_if_planned_days_below": 1.0,         # hour-scale activities give extreme ratios
    "clip_ratio": [0.2, 5.0],
}


def load_dslib(rebuild: bool = False, filtered: bool = False):
    if rebuild or not (CACHE / "activities.csv").is_file():
        build_cache()
    df = pd.read_csv(CACHE / "activities.csv", dtype={"activity_id": str, "predecessors": str}) \
        .fillna({"predecessors": ""})
    if filtered:
        r = df.actual_days / df.planned_days
        exact = pd.Series(np.isclose(r, 1.0, atol=1e-6), index=df.index).groupby(df.project_id).mean()
        df = df[df.project_id.isin(exact[exact < FILTER_RULES["drop_project_if_exact_on_plan_share_at_least"]].index)]
        df = df.copy()
        df.loc[df.planned_days < FILTER_RULES["unlabel_activity_if_planned_days_below"], "actual_days"] = np.nan
        lo, hi = FILTER_RULES["clip_ratio"]
        df["actual_days"] = np.clip(df.actual_days, lo * df.planned_days, hi * df.planned_days)
    groups = project_groups()
    graphs = []
    for pid, g in df.groupby("project_id"):
        d = to_graph(g.drop(columns="project_id").reset_index(drop=True), pid)
        d.group = groups.get(pid, pid)
        graphs.append(d)
    return graphs


if __name__ == "__main__":
    m = build_cache()
    print(m[["project_id", "name", "auth_project", "auth_tracking", "included", "reason",
             "activities", "labelled"]].to_string(index=False))
    inc = m[m.included]
    print(f"\nincluded {len(inc)} projects, {int(inc.activities.sum())} activities, "
          f"{int(inc.labelled.sum())} labelled")
