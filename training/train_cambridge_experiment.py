"""Stage 2.3E controlled Cambridge retrospective duration experiment.

Uses only the frozen Stage 2.3D conservative split. All learned transforms are
refit inside each development fold; the held-out groups are touched once after
model configurations have been locked from development results.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import torch
from matplotlib import pyplot as plt
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import (mean_absolute_error, mean_squared_error, median_absolute_error, r2_score)
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "data/processed/stage2/cambridge_experiment_design"
OUT = ROOT / "data/processed/stage2/cambridge_experiment"
MODELS = ROOT / "models/cambridge_duration_v1"
FEATURES = ["activity_description", "project_type", "uk_region"]
TARGET = "reported_completed_activity_elapsed_calendar_days"
SEED = 23051
ALPHAS = [0.1, 1.0, 10.0]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_frozen_data():
    freeze = json.loads((DESIGN / "design_freeze.json").read_text(encoding="utf-8"))
    for name, expected in freeze["outputs"].items():
        if sha(DESIGN / name) != expected:
            raise RuntimeError(f"Frozen Stage 2.3D artifact changed: {name}")
    features = pd.read_csv(DESIGN / "feature_matrix.csv", dtype=str, keep_default_na=False)
    labels = pd.read_csv(DESIGN / "exploratory_targets.csv", dtype=str, keep_default_na=False)
    split = pd.read_csv(DESIGN / "split_manifest_conservative.csv", dtype=str, keep_default_na=False)
    if any(df.composite_activity_key.duplicated().any() for df in (features, labels, split)):
        raise ValueError("Duplicate composite activity keys; refusing joins")
    if set(features.composite_activity_key) != set(labels.composite_activity_key) or set(labels.composite_activity_key) != set(split.composite_activity_key):
        raise ValueError("Feature, target and split key sets differ")
    if set(features.columns) != {"composite_activity_key", "project_key", "activity_key", *FEATURES}:
        raise ValueError("Feature allowlist drift")
    data = features.merge(labels, on=["composite_activity_key", "project_key", "activity_key"], validate="one_to_one")
    data = data.merge(split, on=["composite_activity_key", "project_key", "activity_key"], validate="one_to_one")
    if data.split.eq("train").sum() != 144110 or data.split.eq("test").sum() != 36027:
        raise ValueError("Frozen primary allocation counts changed")
    y = pd.to_numeric(data[TARGET], errors="raise").to_numpy(dtype=np.float64)
    if not np.isfinite(y).all() or (y <= 0).any():
        raise ValueError("Invalid or missing target")
    if not (data.verified_ground_truth.astype(str).str.lower() == "false").all():
        raise ValueError("Expected exploratory, unverified targets only")
    return data, y


def metric_row(name, y, pred, groups):
    # Accept Python lists as well as NumPy arrays; all arithmetic is explicit.
    y = np.asarray(y, dtype=np.float64).reshape(-1)
    pred = np.asarray(pred, dtype=np.float64).reshape(-1)
    groups = np.asarray(groups).reshape(-1)
    if not (len(y) == len(pred) == len(groups)):
        raise ValueError("y, pred and groups must contain the same number of rows")
    if len(y) == 0:
        raise ValueError("Metrics cannot be calculated for an empty evaluation set")
    if not (np.isfinite(y).all() and np.isfinite(pred).all()):
        raise ValueError("y and pred must contain only finite values")

    residual = pred - y
    absolute_error = np.abs(residual)
    group_mae = (
        pd.DataFrame({"group_id": groups, "ae": absolute_error})
        .groupby("group_id", dropna=False)["ae"]
        .mean()
    )
    return dict(
        model=name,
        n=len(y),
        groups=len(group_mae),
        mae_days=float(np.mean(absolute_error)),
        rmse_days=float(np.sqrt(np.mean(residual ** 2))),
        r2=float(r2_score(y, pred)) if len(y) >= 2 else float("nan"),
        median_absolute_error_days=float(median_absolute_error(y, pred)),
        activity_weighted_mae_days=float(np.mean(absolute_error)),
        macro_group_mae_days=float(group_mae.mean()),
    )


def preprocessor():
    return ColumnTransformer([
        ("text", TfidfVectorizer(max_features=50000, ngram_range=(1, 2), min_df=2, max_df=0.98,
                                  sublinear_tf=True, dtype=np.float32), "activity_description"),
        ("context", OneHotEncoder(handle_unknown="ignore", dtype=np.float32), ["project_type", "uk_region"]),
    ], sparse_threshold=1.0)


def as_frame(data, indices):
    return data.iloc[indices][FEATURES]


def dense_projection(transformer, train_x, other_x, seed=SEED):
    # Fixed 128-component reduction bounds RF/MLP dense memory to about 64 MiB
    # for the full 144k-row training matrix at float32, plus transformer state.
    svd = TruncatedSVD(n_components=128, random_state=seed, n_iter=5)
    a = svd.fit_transform(train_x).astype(np.float32, copy=False)
    b = svd.transform(other_x).astype(np.float32, copy=False)
    scaler = StandardScaler()
    return svd, scaler, scaler.fit_transform(a).astype(np.float32), scaler.transform(b).astype(np.float32)


class SmallMLP(nn.Module):
    def __init__(self, n_in):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_in, 64), nn.ReLU(), nn.Dropout(.25),
                                 nn.Linear(64, 32), nn.ReLU(), nn.Dropout(.15), nn.Linear(32, 1))
    def forward(self, x): return self.net(x).squeeze(-1)


def fit_mlp(x, y, xv, seed=SEED, max_epochs=100, patience=10):
    torch.manual_seed(seed); np.random.seed(seed); random.seed(seed)
    model = SmallMLP(x.shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-3)
    target_mean, target_std = float(np.mean(y)), float(np.std(y))
    if not np.isfinite(target_std) or target_std == 0: target_std = 1.0
    xt = torch.from_numpy(np.asarray(x, dtype=np.float32)); yt = torch.from_numpy(((np.asarray(y)-target_mean)/target_std).astype(np.float32))
    # The supplied validation subset is selected only from development groups.
    # During CV caller passes development-only inner validation rows.
    xvt, yvt = torch.from_numpy(np.asarray(xv[0], dtype=np.float32)), torch.from_numpy(((np.asarray(xv[1])-target_mean)/target_std).astype(np.float32))
    best, best_loss, stale = None, float("inf"), 0
    rng = np.random.default_rng(seed)
    for _ in range(max_epochs):
        model.train()
        for ids in np.array_split(rng.permutation(len(xt)), max(1, (len(xt) + 2047) // 2048)):
            xb, yb = xt[ids], yt[ids]
            optimizer.zero_grad(); loss = nn.functional.mse_loss(model(xb), yb); loss.backward(); optimizer.step()
        model.eval()
        with torch.no_grad(): loss = float(nn.functional.l1_loss(model(xvt), yvt))
        if loss < best_loss - 1e-5:
            best_loss, stale, best = loss, 0, {k: v.detach().clone() for k, v in model.state_dict().items()}
        else: stale += 1
        if stale >= patience: break
    model.load_state_dict(best); model.eval()
    return model, (target_mean, target_std)


def _predict_mlp(model, x, target_scaler):
    with torch.no_grad():
        z = model(torch.from_numpy(np.asarray(x, dtype=np.float32))).cpu().numpy()
    return z * target_scaler[1] + target_scaler[0]


def grouped_folds(data):
    rows = data[data.split == "train"]
    groups = rows.groupby("development_validation_fold").indices
    return [(rows.index.to_numpy(), rows.iloc[list(v)].index.to_numpy()) for _, v in sorted(groups.items())]


def write_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


RAW_JSON = ROOT / "data/raw/cambridge/JPF_Anonymised_Project_Data.json"


def preflight():
    """Fail BEFORE any fitting if an input or dependency needed later is missing, or if the
    held-out groups were already evaluated. Everything checked here is otherwise only used after
    held-out predictions are written, where a crash would leave a half-finished single-use run."""
    problems = []
    if (OUT / "heldout_predictions.csv").exists() or (OUT / "model_comparison.csv").exists():
        problems.append("held-out results already exist in data/processed/stage2/cambridge_experiment/; "
                        "the frozen protocol allows one held-out evaluation - move them aside deliberately to rerun")
    freeze = json.loads((DESIGN / "design_freeze.json").read_text(encoding="utf-8"))
    expected = freeze["protected_inputs"].get("data/raw/cambridge/JPF_Anonymised_Project_Data.json")
    if not RAW_JSON.is_file():
        problems.append(f"{RAW_JSON} is missing (git-ignored); extract it from the tracked .zip "
                        "and verify it against design_freeze.json")
    elif expected and sha(RAW_JSON) != expected:
        problems.append("raw Cambridge JSON does not match its frozen design_freeze.json digest")
    for module in ("tabulate", "scipy", "joblib", "matplotlib"):
        try:
            __import__(module)
        except ImportError:
            problems.append(f"missing dependency '{module}' (see training/requirements-cambridge-experiment.txt)")
    if problems:
        raise SystemExit("Pre-flight failed; nothing was fitted or evaluated:\n- " + "\n- ".join(problems))


def main():
    preflight()
    OUT.mkdir(parents=True, exist_ok=True); MODELS.mkdir(parents=True, exist_ok=True); (OUT / "figures").mkdir(exist_ok=True)
    data, y = load_frozen_data()
    folds = grouped_folds(data)
    development = np.flatnonzero(data.split.to_numpy() == "train")
    test = np.flatnonzero(data.split.to_numpy() == "test")
    # Models are compared on the exact five frozen grouped folds. Every fold
    # fits a fresh vectorizer/encoder. Alpha selection uses fold-only subfolds
    # represented by the frozen grouped folds; choose mean validation MAE.
    fold_rows, fold_predictions, ridge_alphas = [], {m: {} for m in ("median", "ridge", "random_forest", "mlp")}, []
    for fold_id, (_, val_ids) in enumerate(folds):
        train_ids = np.setdiff1d(development, val_ids, assume_unique=False)
        prep = preprocessor(); tr = prep.fit_transform(as_frame(data, train_ids)); va = prep.transform(as_frame(data, val_ids))
        yt, yv = y[train_ids], y[val_ids]
        preds = {"median": np.full(len(val_ids), np.median(yt))}
        # Development-only regularization selection on the fold's training rows.
        inner_groups = sorted(data.iloc[train_ids].conservative_block_id.unique(), key=lambda g: hashlib.sha256((str(SEED)+str(g)).encode()).hexdigest())
        tune_groups = set(inner_groups[:max(1, len(inner_groups)//10)])
        inner_mask = data.iloc[train_ids].conservative_block_id.isin(tune_groups).to_numpy()
        tune_ids, tune_val_ids = train_ids[~inner_mask], train_ids[inner_mask]
        tune_prep = preprocessor(); tune_x = tune_prep.fit_transform(as_frame(data, tune_ids)); tune_v = tune_prep.transform(as_frame(data, tune_val_ids))
        alpha_scores = []
        for alpha in ALPHAS:
            model = Ridge(alpha=alpha, solver="lsqr", max_iter=2000).fit(tune_x, y[tune_ids])
            alpha_scores.append((mean_absolute_error(y[tune_val_ids], model.predict(tune_v)), alpha))
        _, alpha = min(alpha_scores, key=lambda x: (x[0], x[1]))
        ridge_alphas.append(alpha)
        ridge = Ridge(alpha=alpha, solver="lsqr", max_iter=2000).fit(tr, yt); preds["ridge"] = ridge.predict(va)
        svd, scaler, dtr, dva = dense_projection(prep, tr, va)
        rf = RandomForestRegressor(n_estimators=120, max_depth=24, min_samples_leaf=4, max_features=.6,
                                   n_jobs=-1, random_state=SEED + fold_id).fit(dtr, yt)
        preds["random_forest"] = rf.predict(dva)
        # Deterministic grouped inner validation by group hash; reserve the
        # last 10% of training groups, while keeping every validation group intact.
        inner_groups = sorted(data.iloc[train_ids].conservative_block_id.unique(), key=lambda g: hashlib.sha256((str(SEED)+str(g)).encode()).hexdigest())
        val_groups = set(inner_groups[:max(1, len(inner_groups)//10)])
        inner_mask = data.iloc[train_ids].conservative_block_id.isin(val_groups).to_numpy()
        inner_tr, inner_va = np.flatnonzero(~inner_mask), np.flatnonzero(inner_mask)
        # Refit the fold transform after selecting the inner MLP stopping epoch.
        p2 = preprocessor(); a = p2.fit_transform(as_frame(data, train_ids[inner_tr])); b = p2.transform(as_frame(data, train_ids[inner_va]))
        xouter = p2.transform(as_frame(data, val_ids)); svd2 = TruncatedSVD(n_components=128, random_state=SEED + fold_id, n_iter=5)
        aa = svd2.fit_transform(a).astype(np.float32); bb = svd2.transform(b).astype(np.float32); outer = svd2.transform(xouter).astype(np.float32)
        scale2 = StandardScaler(); aa = scale2.fit_transform(aa).astype(np.float32); bb = scale2.transform(bb).astype(np.float32); outer = scale2.transform(outer).astype(np.float32)
        imodel, inner_target_scaler = fit_mlp(aa, y[train_ids[inner_tr]], (bb, y[train_ids[inner_va]]), seed=SEED+fold_id)
        preds["mlp"] = _predict_mlp(imodel, outer, inner_target_scaler)
        for name, pred in preds.items():
            fold_predictions[name].update({int(i): float(v) for i, v in zip(val_ids, pred)})
            # metric_row already returns model=name; passing it twice raised TypeError on the first fold.
            fold_rows.append(dict(fold=fold_id, **metric_row(name, y[val_ids], pred, data.iloc[val_ids].conservative_block_id.to_numpy())))
    fold_df = pd.DataFrame(fold_rows); write_csv(OUT / "fold_metrics.csv", fold_rows)
    summary = fold_df.groupby("model").macro_group_mae_days.mean().sort_values()
    selected_model = str(summary.index[0])
    # Lock winner/configurations before a single prediction call on held-out data.
    chosen_alpha = Counter(ridge_alphas).most_common(1)[0][0]
    locked = {"ridge_alpha": float(chosen_alpha), "ridge_alpha_by_fold": ridge_alphas, "rf": dict(n_estimators=120, max_depth=24, min_samples_leaf=4, max_features=.6),
              "mlp": dict(hidden=[64, 32], dropout=[.25, .15], weight_decay=.001, patience=10, max_epochs=100),
              "selection_metric": "mean five-fold development macro_group_mae_days", "development_macro_group_mae_order": summary.to_dict(),
              "primary_residual_diagnostic_model": selected_model}
    (OUT / "training_config.json").write_text(json.dumps(locked, indent=2)+"\n", encoding="utf-8")
    # Final models refit on all primary development rows. No held-out values are
    # read until the selected models and all preprocessing are fully fitted.
    prep = preprocessor(); xd = prep.fit_transform(as_frame(data, development)); xe = prep.transform(as_frame(data, test))
    ydev = y[development]
    med = float(np.median(ydev)); ridge = Ridge(alpha=chosen_alpha, solver="lsqr", max_iter=2000).fit(xd, ydev)
    svd, scaler, dd, de = dense_projection(prep, xd, xe)
    rf = RandomForestRegressor(n_estimators=120, max_depth=24, min_samples_leaf=4, max_features=.6, n_jobs=-1, random_state=SEED).fit(dd, ydev)
    # Final MLP early stop uses only a deterministic 10% group subset of development.
    groups = sorted(data.iloc[development].conservative_block_id.unique(), key=lambda g: hashlib.sha256((str(SEED)+str(g)).encode()).hexdigest())
    vg = set(groups[:max(1, len(groups)//10)]); mask = data.iloc[development].conservative_block_id.isin(vg).to_numpy()
    p_mlp = preprocessor(); xa = p_mlp.fit_transform(as_frame(data, development[~mask])); xv = p_mlp.transform(as_frame(data, development[mask])); xm = p_mlp.transform(as_frame(data, test))
    svd_mlp = TruncatedSVD(n_components=128, random_state=SEED, n_iter=5); xa = svd_mlp.fit_transform(xa).astype(np.float32); xv = svd_mlp.transform(xv).astype(np.float32); xm = svd_mlp.transform(xm).astype(np.float32)
    scale_mlp = StandardScaler(); xa = scale_mlp.fit_transform(xa).astype(np.float32); xv = scale_mlp.transform(xv).astype(np.float32); xm = scale_mlp.transform(xm).astype(np.float32)
    mlp, mlp_target_scaler = fit_mlp(xa, y[development[~mask]], (xv, y[development[mask]]), seed=SEED)
    # MLP is fitted on the grouped fitting portion; its stopping groups remain
    # excluded from gradient updates as required for honest early stopping.
    predictions = {"median": np.full(len(test), med), "ridge": ridge.predict(xe), "random_forest": rf.predict(de), "mlp": _predict_mlp(mlp, xm, mlp_target_scaler)}
    groups_test = data.iloc[test].conservative_block_id.to_numpy()
    comparison = [metric_row(name, y[test], pred, groups_test) for name, pred in predictions.items()]
    write_csv(OUT / "model_comparison.csv", comparison)
    pred_rows = data.iloc[test][["composite_activity_key", "project_key", "activity_key", "conservative_block_id", *FEATURES]].copy()
    pred_rows["actual_days"] = y[test]
    for k, v in predictions.items(): pred_rows[f"predicted_{k}_days"] = v
    pred_rows.to_csv(OUT / "heldout_predictions.csv", index=False)
    # Group and residual tables, including row-weighted and macro group metrics.
    diagnostic_model = selected_model
    pred_rows["prediction"] = predictions[diagnostic_model]; pred_rows["residual_days"] = pred_rows.prediction - pred_rows.actual_days
    group_rows = []
    for name, pred in predictions.items():
        temp = pd.DataFrame({"group": groups_test, "actual": y[test], "pred": pred})
        for group, g in temp.groupby("group"):
            err = g.pred.to_numpy() - g.actual.to_numpy()
            group_rows.append(dict(model=name, conservative_block_id=group, n=len(g), mae_days=float(np.mean(np.abs(err))), rmse_days=float(np.sqrt(np.mean(err**2))), median_absolute_error_days=float(np.median(np.abs(err)))))
    pd.DataFrame(group_rows).to_csv(OUT / "group_level_metrics.csv", index=False)
    gm = pd.DataFrame([r for r in group_rows if r["model"] == diagnostic_model])
    pred_rows["absolute_error_days"] = np.abs(pred_rows.residual_days)
    pred_rows.sort_values("absolute_error_days", ascending=False).head(100).to_csv(OUT / "residual_analysis.csv", index=False)
    # Charts are all in calendar-day units; axes are not clipped in tabular outputs.
    figdir = OUT / "figures"
    for name, pred in predictions.items():
        fig, ax = plt.subplots(figsize=(7, 6)); ax.scatter(y[test], pred, s=5, alpha=.2); ax.set(xlabel="Actual elapsed calendar days", ylabel="Predicted elapsed calendar days", title=f"{name}: held-out groups"); fig.tight_layout(); fig.savefig(figdir / f"actual_vs_predicted_{name}.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5)); ax.hist(pred_rows.residual_days, bins=80); ax.set(xlabel="Residual (predicted - actual), calendar days", ylabel="Activities", title=f"Held-out residuals ({diagnostic_model})"); fig.tight_layout(); fig.savefig(figdir / "residual_distribution.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5)); ax.hist(pred_rows.absolute_error_days, bins=80); ax.set(xlabel="Absolute error, calendar days", ylabel="Activities", title=f"Held-out absolute errors ({diagnostic_model})"); fig.tight_layout(); fig.savefig(figdir / "absolute_error_distribution.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5)); ax.bar([r["model"] for r in comparison], [r["mae_days"] for r in comparison]); ax.set(ylabel="MAE (calendar days)", title="Held-out MAE by frozen model"); fig.tight_layout(); fig.savefig(figdir / "mae_comparison.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 6)); ax.bar(gm.conservative_block_id, gm.mae_days); ax.tick_params(axis="x", labelrotation=90); ax.set(ylabel="Group MAE (calendar days)", title=f"Held-out conservative group performance ({diagnostic_model})"); fig.tight_layout(); fig.savefig(figdir / "group_performance.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5)); ax.scatter(pred_rows.actual_days, pred_rows.residual_days, s=5, alpha=.2); ax.axhline(0, color="black"); ax.set(xlabel="Actual elapsed calendar days", ylabel="Residual (calendar days)", title="Prediction error against actual duration"); fig.tight_layout(); fig.savefig(figdir / "error_vs_actual.png", dpi=150); plt.close(fig)
    feature_manifest = dict(allowed_features=FEATURES, target=TARGET, target_unit="naive elapsed calendar days", excluded_predictors="all identifiers, dates, duration/progress/outcome fields, WBS, topics, embeddings, float, concurrency, weather, market data", provenance="exported features; original prediction-time availability unverified")
    (OUT / "feature_manifest.json").write_text(json.dumps(feature_manifest, indent=2)+"\n", encoding="utf-8")
    inventory = json.loads((ROOT / "data/processed/external_inventory/cambridge_inventory.json").read_text(encoding="utf-8"))
    metadata = dict(seed=SEED, split_manifest="split_manifest_conservative.csv", split_manifest_sha256=sha(DESIGN / "split_manifest_conservative.csv"), source_dataset=dict(archive_sha256=inventory["archive_sha256"], raw_json_sha256=sha(RAW_JSON)), source_hashes={p.name: sha(p) for p in [DESIGN / "feature_matrix.csv", DESIGN / "exploratory_targets.csv"]}, python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, scikit_learn=sklearn.__version__, pytorch=torch.__version__, scipy=__import__("scipy").__version__, hardware="CPU", model_selection="grouped five fold development only", heldout_evaluations=1)
    (OUT / "model_metadata.json").write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")
    import joblib
    joblib.dump({"classical_preprocessor": prep, "classical_svd": svd, "classical_scaler": scaler,
                 "mlp_preprocessor": p_mlp, "mlp_svd": svd_mlp, "mlp_scaler": scale_mlp}, MODELS / "preprocessing.joblib")
    joblib.dump({"median": med, "ridge": ridge, "random_forest": rf,
                 "mlp_target_mean_std": mlp_target_scaler}, MODELS / "classical_models.joblib")
    torch.save(mlp.state_dict(), MODELS / "mlp_state.pt")
    yt = pd.Series(y[test])
    target_summary = yt.describe(percentiles=[.05, .25, .5, .75, .95]).to_frame("calendar_days").to_markdown()
    project_dist = data.iloc[test].project_type.value_counts(dropna=False).rename_axis("project_type").reset_index(name="activities").to_markdown(index=False)
    region_dist = data.iloc[test].uk_region.value_counts(dropna=False).rename_axis("uk_region").reset_index(name="activities").to_markdown(index=False)
    report = ["# Cambridge Stage 2.3E experiment", "", "Exploratory retrospective estimates of reported completed-activity elapsed calendar days. No labels are independently verified; no prediction-time feature provenance is established.", "", "## Held-out results", "", pd.DataFrame(comparison).to_markdown(index=False), "", f"Evaluation: {len(test):,} activities across {len(set(groups_test))} conservative groups. The dominant conservative block remains wholly in development. The evaluation is distribution-shifted and not representative of the dominant history.", "", f"The primary residual and large-error analysis uses {diagnostic_model}, selected from development folds by mean macro-group MAE before the held-out results were calculated. The table compares every predeclared model on the same frozen evaluation population.", "", "### Target distribution (calendar days)", "", target_summary, "", "### Project type distribution", "", project_dist, "", "### Regional distribution", "", region_dist, "", "### Group results", "", gm.to_markdown(index=False), "", "## Limits and next steps", "", "R² is a fit statistic, not prediction accuracy or a percentage of correctly predicted days. Results do not validate working-day durations, IFC-caused delay, verified ground truth or generalization to all construction projects. Inspect the largest errors and the per-group spread before proposing any follow-up. Independent label and baseline provenance verification is still required. Large-error cases are listed in residual_analysis.csv."]
    (OUT / "experiment_report.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    print(pd.DataFrame(comparison).to_string(index=False))


if __name__ == "__main__": main()
