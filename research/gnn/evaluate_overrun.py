"""
Overrun-risk ranking from saved out-of-fold predictions (no retraining).

Question: does a model rank activities by their risk of overrunning better than chance?
    overrun  = actual_days > 1.05 x planned_days
    score    = predicted log(actual / planned) of each method
    metric   = ROC AUC per cross-validation fold (0.5 = chance) and pooled

    python research/gnn/evaluate_overrun.py                # all models/gnn_*/oof_predictions.csv
    python research/gnn/evaluate_overrun.py dslib          # one source

Writes models/gnn_<source>/overrun_auc.json. Per-fold values are the ones to read: the pooled AUC
mixes folds whose predictions are calibrated differently and can look better than any single fold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
METHODS = ("category", "mlp", "gnn")
OVERRUN_FACTOR = 1.05


def overrun_auc(oof: pd.DataFrame) -> dict:
    over = (oof["actual_days"] > OVERRUN_FACTOR * oof["planned_days"]).astype(int)
    out = {"activities": int(len(oof)), "overrun_share": round(float(over.mean()), 3),
           "overrun_definition": f"actual_days > {OVERRUN_FACTOR} x planned_days", "methods": {}}
    for m in METHODS:
        score = np.log(oof[f"pred_{m}"] / oof["planned_days"])
        folds = {}
        for f, g in oof.groupby("fold"):
            y = over.loc[g.index]
            folds[int(f)] = round(float(roc_auc_score(y, score.loc[g.index])), 3) if y.nunique() == 2 else None
        vals = [v for v in folds.values() if v is not None]
        out["methods"][m] = {"per_fold": folds, "min_fold": min(vals), "max_fold": max(vals),
                             "pooled": round(float(roc_auc_score(over, score)), 3)}
    return out


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    folders = [ROOT / "models" / f"gnn_{s}" for s in argv] or sorted((ROOT / "models").glob("gnn_*"))
    for d in folders:
        if not (d / "oof_predictions.csv").is_file():
            continue
        res = overrun_auc(pd.read_csv(d / "oof_predictions.csv"))
        (d / "overrun_auc.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"{d.name}: overrun share {res['overrun_share']}")
        for m, r in res["methods"].items():
            print(f"  {m:8s} per fold {list(r['per_fold'].values())}  range {r['min_fold']}-{r['max_fold']}"
                  f"  pooled {r['pooled']}")


if __name__ == "__main__":
    main()
