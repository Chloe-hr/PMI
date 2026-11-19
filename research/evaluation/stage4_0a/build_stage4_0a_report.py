"""
Stage 4.0A - expanded experiment inventory and evaluation report (read-only audit).

    .venv/Scripts/python.exe research/evaluation/stage4_0a/build_stage4_0a_report.py

What this script does
    * reads saved metadata, metrics, loss histories, out-of-fold (OOF) predictions and checkpoints;
    * recomputes summary metrics from SAVED predictions only (no model is called, nothing is retrained);
    * writes CSV summaries, plots, architecture diagrams, a Markdown report and an interactive HTML report
      to research/evaluation/stage4_0a/ only.

What it never does
    * train, run inference, regenerate predictions, or write outside research/evaluation/stage4_0a/;
    * parse any file derived from the Cambridge locked test blocks (see LOCKED_TEST_DENYLIST).
      Those files are only byte-hashed for the preservation check.
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CSV_DIR = HERE / "csv"
FIG_DIR = HERE / "figures"
ARCH_DIR = FIG_DIR / "architecture"
PRES_DIR = HERE / "preservation"
BASELINE = PRES_DIR / "baseline_sha256_before_stage4_0a.txt"

# ---------------------------------------------------------------- locked-test guard
STAGE2 = "data/processed/stage2/cambridge_experiment"
LOCKED_TEST_DENYLIST = {
    f"{STAGE2}/heldout_predictions.csv",
    f"{STAGE2}/residual_analysis.csv",
    f"{STAGE2}/group_level_metrics.csv",
    "data/processed/stage2/cambridge_experiment_design/split_manifest_conservative.csv",
}
LOCKED_TEST_DENY_PREFIXES = (f"{STAGE2}/figures/", "data/raw/cambridge/")
_READ_LOG: list[str] = []


def _rel(p) -> str:
    return Path(p).resolve().relative_to(ROOT).as_posix()


def guard(path) -> Path:
    rel = _rel(ROOT / path)
    if rel in LOCKED_TEST_DENYLIST or rel.startswith(LOCKED_TEST_DENY_PREFIXES):
        raise PermissionError(f"Stage 4.0A must not parse locked-test-derived file: {rel}")
    _READ_LOG.append(rel)
    return ROOT / rel


def rjson(path):
    return json.loads(guard(path).read_text(encoding="utf-8"))


def rcsv(path, **kw):
    return pd.read_csv(guard(path), **kw)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- palette (dataviz reference, light)
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
GREY, INK, INK2, GRID, SURF = "#8a8984", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "legend.frameon": False, "lines.linewidth": 1.4,
})
FIGS: dict[str, Path] = {}


def savefig(fig, name, caption):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    p = FIG_DIR / f"{name}.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    FIGS[name] = p
    CAPTIONS[name] = caption
    return p


CAPTIONS: dict[str, str] = {}


def git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:  # pragma: no cover
        return ""


def first_commit(path: str) -> str:
    out = git("log", "--diff-filter=A", "--format=%h %ad", "--date=short", "--", path)
    return out.splitlines()[-1] if out else "untracked"


# ================================================================= experiment registry
EXPERIMENTS = [
    dict(id="E1", stage="Stage 1 (duration v1)", name="Mendeley tabular MLP - single held-out split",
         folder="models/duration_v1", family="Tabular total-project-duration",
         dataset="Mendeley project table: 40 training rows + 10-row test file (50 projects)",
         target="ProjDura (total project duration, unit unverified), StandardScaler on fitting rows",
         loss="MSE on standardized ProjDura (train_mse_scaled / validation_mse_scaled)",
         partition="Inner validation = 8 rows (GroupShuffleSplit seed 42); final metric on 10-row test file"),
    dict(id="E2", stage="Stage 1 development validation (1 repeat)", name="Mendeley grouped 5-fold CV, 1 repeat",
         folder="data/processed/duration_validation", family="Tabular total-project-duration",
         dataset="Mendeley 40 development rows only (test file not loaded)",
         target="ProjDura, StandardScaler on each fold's fitting rows",
         loss="MSE on standardized ProjDura (train_mse_scaled / validation_mse_scaled)",
         partition="Outer grouped 5-fold evaluation folds; inner grouped validation for stopping"),
    dict(id="E3", stage="Stage 1 development validation (3 repeats)", name="Mendeley grouped 5-fold CV, 3 repeats",
         folder="data/processed/duration_validation_repeated", family="Tabular total-project-duration",
         dataset="Mendeley 40 development rows only (test file not loaded)",
         target="ProjDura, StandardScaler on each fold's fitting rows",
         loss="MSE on standardized ProjDura (train_mse_scaled / validation_mse_scaled)",
         partition="Outer grouped 5-fold evaluation folds x 3 repeats (seeds 42/43/44)"),
    dict(id="E4", stage="Stage 3.5", name="Duration GNN - synthetic schedules",
         folder="models/gnn_synthetic", family="Activity log(actual/planned) - graph",
         dataset="120 generated projects, 2,510 labelled activities, labels from a known rule",
         target="log(actual_days / planned_days); reported in days via planned x exp(pred)",
         loss="Huber (delta 0.5) on log ratio - per-epoch values NOT saved",
         partition="5-fold project-grouped OOF; 15% of training groups for early stopping"),
    dict(id="E5", stage="Stage 3.5", name="Duration GNN - DSLIB all G/G projects",
         folder="models/gnn_dslib", family="Activity log(actual/planned) - graph",
         dataset="Ghent DSLIB: 53 projects in 17 independent groups, 2,712 labelled activities",
         target="log(actual_days / planned_days); reported in days",
         loss="Huber (delta 0.5) on log ratio - per-epoch values NOT saved",
         partition="5-fold group OOF; 15% of training groups for early stopping"),
    dict(id="E6", stage="Stage 3.5", name="Duration GNN - DSLIB filtered (sensitivity)",
         folder="models/gnn_dslib_filtered", family="Activity log(actual/planned) - graph",
         dataset="Ghent DSLIB filtered: 40 projects in 15 groups, 2,051 labelled activities",
         target="log(actual_days / planned_days); reported in days",
         loss="Huber (delta 0.5) on log ratio - per-epoch values NOT saved",
         partition="5-fold group OOF; 15% of training groups for early stopping"),
    dict(id="E7", stage="Stage 2.3E", name="Cambridge classical models (median, ridge, random forest, MLP)",
         folder="data/processed/stage2/cambridge_experiment (+ models/cambridge_duration_v1)",
         family="Activity elapsed calendar days - no graph",
         dataset="Cambridge JPF export, frozen Stage 2.3D split: 144,110 development rows / 70 blocks",
         target="Raw reported elapsed calendar days (no log); MLP target standardized",
         loss="MLP: MSE on standardized days (train), L1 on standardized days (stopping) - NOT saved",
         partition="5 frozen development folds; historical held-out summary on 99 locked blocks kept separate"),
    dict(id="E8", stage="Stage 3.7", name="Cambridge GraphSAGE vs matched no-graph network",
         folder="models/gnn_cambridge", family="Activity elapsed calendar days - graph",
         dataset="Same 144,110 development rows / 70 blocks / 163 project graphs; locked test not materialised",
         target="log1p(days); predictions expm1 and clipped at 0; 3-seed mean of log predictions",
         loss="L1 on log1p(days) (train_l1_log, inner_stop_l1_log, outer_val_l1_log_monitor_only)",
         partition="5 frozen development folds x 3 seeds; inner stopping blocks; outer fold monitor only"),
]
EXP = {e["id"]: e for e in EXPERIMENTS}


# ================================================================= loaders
def load_all():
    D = {}
    # ---- E1
    D["E1_metrics"] = rjson("models/duration_v1/metrics.json")
    D["E1_loss"] = rcsv("models/duration_v1/loss_history.csv")
    D["E1_pred"] = rcsv("models/duration_v1/test_predictions.csv")
    # ---- E2/E3
    for eid, folder, reps in (("E2", "data/processed/duration_validation", 1),
                              ("E3", "data/processed/duration_validation_repeated", 3)):
        D[f"{eid}_cv"] = rcsv(f"{folder}/cross_validation.csv")
        D[f"{eid}_manifest"] = rjson(f"{folder}/fold_manifest.json")
        D[f"{eid}_oof"] = rcsv(f"{folder}/out_of_fold_predictions.csv")
        D[f"{eid}_loss"] = {(r, f): rcsv(f"{folder}/repeat_{r}_fold_{f}/loss_history.csv")
                            for r in range(1, reps + 1) for f in range(1, 6)}
    # ---- E4-E6
    for eid, src in (("E4", "gnn_synthetic"), ("E5", "gnn_dslib"), ("E6", "gnn_dslib_filtered")):
        D[f"{eid}_metrics"] = rjson(f"models/{src}/metrics.json")
        D[f"{eid}_auc"] = rjson(f"models/{src}/overrun_auc.json")
        D[f"{eid}_oof"] = rcsv(f"models/{src}/oof_predictions.csv")
    # ---- E7 (development artefacts + stored aggregate only)
    D["E7_config"] = rjson(f"{STAGE2}/training_config.json")
    D["E7_meta"] = rjson(f"{STAGE2}/model_metadata.json")
    D["E7_features"] = rjson(f"{STAGE2}/feature_manifest.json")
    D["E7_folds"] = rcsv(f"{STAGE2}/fold_metrics.csv")
    D["E7_heldout_hist"] = rcsv(f"{STAGE2}/model_comparison.csv")  # stored aggregate, never re-derived
    # ---- E8
    G = "models/gnn_cambridge"
    D["E8_config"] = rjson(f"{G}/training_config.json")
    D["E8_metrics"] = rjson(f"{G}/metrics.json")
    D["E8_cmp"] = rcsv(f"{G}/model_comparison.csv")
    D["E8_folds"] = rcsv(f"{G}/fold_metrics.csv")
    D["E8_seeds"] = rcsv(f"{G}/seed_metrics.csv")
    D["E8_runs"] = rcsv(f"{G}/training_runs.csv")
    D["E8_loss"] = rcsv(f"{G}/loss_curves.csv")
    D["E8_oof"] = rcsv(f"{G}/oof_predictions.csv")
    D["E8_env"] = rjson(f"{G}/environment.json")
    D["E8_prov"] = rjson(f"{G}/provenance.json")
    D["E8_manifest"] = rjson(f"{G}/preservation_manifest.json")
    return D


# ================================================================= metric recomputation from saved predictions
def gnn_metrics(df, col):
    """Same formulas as research/gnn/train.py::metrics (recomputed from saved OOF predictions)."""
    err = df[col] - df["actual_days"]
    ape = (err.abs() / df["actual_days"]).replace(np.inf, np.nan)
    lr = np.log(df[col] / df["actual_days"])
    proj = df.assign(e=err.abs()).groupby("project_id")["e"].mean()
    return {"MAE_days": float(err.abs().mean()), "MedAE_days": float(err.abs().median()),
            "MdAPE_pct": float(ape.median() * 100), "MAE_log_ratio": float(lr.abs().mean()),
            "mean_project_MAE_days": float(proj.mean())}


def mean_block_mae(df, col):
    return float(df.assign(e=(df[col] - df.actual_days).abs()).groupby("conservative_block_id").e.mean().mean())


# ================================================================= analyses
def analyse(D):
    A = {}
    # ---------- E1 convergence
    l1 = D["E1_loss"]; m1 = D["E1_metrics"]["experiment"]
    be = m1["best_epoch"]
    A["E1_conv"] = dict(
        best_epoch=be, epochs_run=m1["epochs_run"], max_epochs=m1["max_epochs"], patience=m1["patience"],
        stopped_by_patience=m1["epochs_run"] < m1["max_epochs"],
        train_at_best=float(l1.loc[l1.epoch == be, "train_mse_scaled"].iloc[0]),
        val_at_best=float(l1.loc[l1.epoch == be, "validation_mse_scaled"].iloc[0]),
        val_first=float(l1.validation_mse_scaled.iloc[0]), train_first=float(l1.train_mse_scaled.iloc[0]),
        val_last=float(l1.validation_mse_scaled.iloc[-1]), train_last=float(l1.train_mse_scaled.iloc[-1]),
        val_drop_last_200=float(l1.validation_mse_scaled.iloc[-201] - l1.validation_mse_scaled.iloc[-1]),
    )
    # ---------- E2 vs E3 identity (hash-based, never size-based)
    ident = []
    for f in range(1, 6):
        for fn in ("loss_history.csv", "model.pt", "test_predictions.csv", "development.csv", "evaluation.csv",
                   "preprocessing.joblib", "baselines.joblib"):
            a = ROOT / f"data/processed/duration_validation/repeat_1_fold_{f}/{fn}"
            b = ROOT / f"data/processed/duration_validation_repeated/repeat_1_fold_{f}/{fn}"
            ident.append(dict(fold=f, file=fn, sha256_E2=sha256(a), sha256_E3_repeat1=sha256(b),
                              identical=sha256(a) == sha256(b)))
    A["E2_E3_identity"] = pd.DataFrame(ident)
    e2 = D["E2_cv"].sort_values(["fold", "model"]).reset_index(drop=True)
    e3r1 = D["E3_cv"][D["E3_cv"].repeat == 1].sort_values(["fold", "model"]).reset_index(drop=True)
    A["E2_metrics_equal_E3r1"] = bool(np.allclose(e2.MAE, e3r1.MAE) and np.allclose(e2.R2, e3r1.R2))
    # ---------- E3 per-run convergence
    rows = []
    for (r, f), h in D["E3_loss"].items():
        man = next(x for x in D["E3_manifest"] if x["repeat"] == r and x["fold"] == f)
        b = man["best_epoch"]
        at = h[h.epoch == b].iloc[0]
        rows.append(dict(experiment="E3", run=f"r{r}f{f}", repeat=r, fold=f, seed=man["seed"], best_epoch=b,
                         epochs_run=man["epochs_run"], max_epochs=man["max_epochs"], patience=man["patience"],
                         stopped_by_patience=man["epochs_run"] < man["max_epochs"],
                         train_mse_scaled_at_best=float(at.train_mse_scaled),
                         val_mse_scaled_at_best=float(at.validation_mse_scaled),
                         train_mse_scaled_last=float(h.train_mse_scaled.iloc[-1]),
                         val_mse_scaled_last=float(h.validation_mse_scaled.iloc[-1]),
                         val_rise_after_best=float(h.validation_mse_scaled.iloc[-1] - at.validation_mse_scaled),
                         train_drop_after_best=float(at.train_mse_scaled - h.train_mse_scaled.iloc[-1]),
                         rows_fit=man["rows_fit"], rows_inner_validation=man["rows_validation"],
                         rows_outer_eval=man["rows_test"]))
    A["E3_conv"] = pd.DataFrame(rows).sort_values(["repeat", "fold"])
    # E3 summary recomputed from per-fold rows
    s = D["E3_cv"].groupby("model")[["MAE", "RMSE", "R2"]].agg(["mean", "std"])
    s.columns = [f"{a}_{b}" for a, b in s.columns]
    A["E3_summary"] = s.reset_index()
    # ---------- E4-E6: recompute stored metrics from OOF + per-fold
    for eid in ("E4", "E5", "E6"):
        oof = D[f"{eid}_oof"]; stored = D[f"{eid}_metrics"]["metrics"]
        rows, fold_rows = [], []
        for m in ("plan", "median", "category", "mlp", "gnn"):
            rec = gnn_metrics(oof, f"pred_{m}")
            for k, v in rec.items():
                rows.append(dict(experiment=eid, method=m, metric=k, stored=stored[m][k], recomputed_from_oof=v,
                                 matches_to_stored_precision=abs(round(v, 4 if k == "MAE_log_ratio" else 3 if k != "MdAPE_pct" else 2) - stored[m][k]) < 1e-9))
            for f, g in oof.groupby("fold"):
                fold_rows.append(dict(experiment=eid, method=m, fold=int(f), activities=len(g),
                                      projects=g.project_id.nunique(),
                                      MAE_days=float((g[f"pred_{m}"] - g.actual_days).abs().mean()),
                                      MAE_log_ratio=float(np.log(g[f"pred_{m}"] / g.actual_days).abs().mean())))
        A[f"{eid}_check"] = pd.DataFrame(rows)
        A[f"{eid}_folds"] = pd.DataFrame(fold_rows)
        A[f"{eid}_on_plan_share"] = float(np.isclose(oof.actual_days, oof.planned_days, rtol=1e-6).mean())
    # ---------- E7
    f7 = D["E7_folds"]
    A["E7_dev_summary"] = f7.groupby("model")[["macro_group_mae_days", "mae_days", "rmse_days", "r2"]].mean().reset_index() \
        .rename(columns={"macro_group_mae_days": "mean_of_fold_macro_group_mae_days", "mae_days": "mean_of_fold_mae_days",
                         "rmse_days": "mean_of_fold_rmse_days", "r2": "mean_of_fold_r2"}).sort_values("mean_of_fold_macro_group_mae_days")
    # ---------- E8 recomputation from OOF (development only)
    oof = D["E8_oof"]
    assert oof.conservative_block_id.nunique() == 70 and len(oof) == 144110
    rec = []
    for m in ("median", "ridge", "no_graph", "graphsage"):
        stored = D["E8_cmp"].set_index("model").loc[m]
        rec.append(dict(model=m, stored_mean_block_mae=stored.mean_block_mae_days,
                        recomputed_mean_block_mae=mean_block_mae(oof, f"pred_{m}"),
                        stored_activity_mae=stored.activity_mae_days,
                        recomputed_activity_mae=float((oof[f"pred_{m}"] - oof.actual_days).abs().mean())))
    r = pd.DataFrame(rec)
    r["match"] = np.isclose(r.stored_mean_block_mae, r.recomputed_mean_block_mae, atol=1e-6) & \
        np.isclose(r.stored_activity_mae, r.recomputed_activity_mae, atol=1e-6)
    A["E8_check"] = r
    # E8 convergence per run
    L = D["E8_loss"]; rows = []
    for (m, f, s), g in L.groupby(["model", "fold", "seed"]):
        run = D["E8_runs"].query("model == @m and fold == @f and seed == @s").iloc[0]
        b = int(run.best_epoch); at = g[g.epoch == b].iloc[0]
        rows.append(dict(experiment="E8", model=m, fold=int(f), seed=int(s), best_epoch=b, epochs_run=int(run.epochs_run),
                         max_epochs=150, patience=15, stopped_by_patience=int(run.epochs_run) < 150,
                         train_l1_log_at_best=float(at.train_l1_log), inner_stop_l1_log_at_best=float(at.inner_stop_l1_log),
                         outer_val_l1_log_at_best=float(at.outer_val_l1_log_monitor_only),
                         train_l1_log_last=float(g.train_l1_log.iloc[-1]),
                         inner_stop_l1_log_last=float(g.inner_stop_l1_log.iloc[-1]),
                         outer_val_l1_log_last=float(g.outer_val_l1_log_monitor_only.iloc[-1]),
                         outer_minus_train_at_best=float(at.outer_val_l1_log_monitor_only - at.train_l1_log),
                         restored_epoch_le_4=b <= 4))
    A["E8_conv"] = pd.DataFrame(rows)
    return A


# ================================================================= checkpoints & preservation
def checkpoint_inventory():
    import torch
    targets = []
    for p in sorted((ROOT / "models").glob("gnn_synthetic/model.pt")) + sorted((ROOT / "models").glob("gnn_dslib*/model.pt")):
        targets.append((p, {"gnn_synthetic": "E4", "gnn_dslib": "E5", "gnn_dslib_filtered": "E6"}[p.parent.name],
                        "Final DurationGNN refit on ALL projects for median CV best epoch; NOT the fold models behind the OOF metrics"))
    targets.append((ROOT / "models/duration_v1/model.pt", "E1", "Best-validation MLP checkpoint (restored epoch)"))
    for d in ("duration_validation", "duration_validation_repeated"):
        eid = "E2" if d == "duration_validation" else "E3"
        for p in sorted((ROOT / "data/processed" / d).glob("repeat_*_fold_*/model.pt")):
            targets.append((p, eid, f"Fold MLP checkpoint {p.parent.name} (restored inner-validation epoch)"))
    targets.append((ROOT / "models/cambridge_duration_v1/mlp_state.pt", "E7", "Final SmallMLP state_dict refit on development (stopping on 10% dev blocks)"))
    for p in sorted((ROOT / "models/gnn_cambridge/checkpoints").glob("*.pt")):
        targets.append((p, "E8", "Fold/seed CambridgeSAGE checkpoint"))
    rows = []
    for p, eid, role in targets:
        meta = {}
        try:
            ck = torch.load(p, map_location="cpu", weights_only=True)
            sd = ck.get("state_dict", ck) if isinstance(ck, dict) else ck
            meta["n_parameters"] = int(sum(v.numel() for v in sd.values() if hasattr(v, "numel")))
            first = next(iter(sd.items()))
            meta["first_tensor"] = f"{first[0]} {tuple(first[1].shape)}"
            if isinstance(ck, dict):
                for k in ("kind", "fold", "seed", "best_epoch", "n_in", "protocol_sha256", "source", "hidden", "layers",
                          "architecture", "target", "duration_unit"):
                    if k in ck:
                        meta[k] = ck[k] if not isinstance(ck[k], list) else "-".join(map(str, ck[k]))
                if "features" in ck:
                    meta["n_features"] = len(ck["features"])
            meta["load"] = "ok (weights_only=True)"
        except Exception as e:  # noqa: BLE001
            meta["load"] = f"FAILED: {e}"
        rows.append(dict(experiment=eid, path=_rel(p), bytes=p.stat().st_size, sha256=sha256(p), role=role,
                         metadata=json.dumps(meta, default=str)))
    # joblib artefacts: hash + size only (unpickling is not needed for the audit)
    for p in sorted((ROOT / "models/cambridge_duration_v1").glob("*.joblib")) + \
            sorted((ROOT / "models/gnn_cambridge/checkpoints").glob("*.joblib")):
        eid = "E7" if "cambridge_duration_v1" in str(p) else "E8"
        rows.append(dict(experiment=eid, path=_rel(p), bytes=p.stat().st_size, sha256=sha256(p),
                         role="Fitted preprocessing / classical estimators (pickle; hashed, not unpickled)",
                         metadata=json.dumps({"load": "not unpickled by design"})))
    df = pd.DataFrame(rows)
    # same-size-but-different-content check and genuine duplicates
    dup = df.groupby("sha256").path.transform(lambda s: ";".join(s) if len(s) > 1 else "")
    df["identical_content_group"] = dup
    same_size = df.groupby("bytes").sha256.transform("nunique")
    df["same_size_distinct_hashes"] = (df.groupby("bytes").path.transform("count") > 1) & (same_size > 1)
    return df


def preservation_check(D):
    rows = []
    base = {}
    if BASELINE.exists():
        for line in BASELINE.read_text(encoding="utf-8").splitlines():
            h, p = line.split(" ", 1)
            base[p.lstrip("*").strip()] = h
    for p, h in sorted(base.items()):
        cur = ROOT / p
        now = sha256(cur) if cur.exists() else "MISSING"
        rows.append(dict(check="before_vs_after_stage4_0a", path=p, expected_sha256=h, current_sha256=now,
                         status="PASS" if now == h else "FAIL"))
    for p, rec in D["E8_manifest"]["files"].items():
        cur = ROOT / p
        now = sha256(cur) if cur.exists() else "MISSING"
        status = "PASS" if (now == rec["sha256"] and cur.stat().st_size == rec["bytes"]) else "FAIL"
        if status == "FAIL" and cur.exists():
            lf = hashlib.sha256(cur.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            if lf == rec["sha256"]:
                status = "PASS_EOL_EQUIVALENT"  # git core.autocrlf checkout; LF content identical
        rows.append(dict(check="gnn_cambridge_preservation_manifest", path=p, expected_sha256=rec["sha256"],
                         current_sha256=now, status=status))
    for x in D["E3_manifest"]:
        for p, h in x["input_sha256"].items():
            rel = p.replace("\\", "/")
            cur = ROOT / rel
            now = sha256(cur) if cur.exists() else "MISSING"
            rows.append(dict(check="E3_fold_manifest_input_sha256", path=rel, expected_sha256=h, current_sha256=now,
                             status="PASS" if now == h else "FAIL"))
    for p, h in D["E1_metrics"]["experiment"]["input_sha256"].items():
        rel = "data/processed/" + p.replace("\\", "/").split("/data/processed/")[-1]
        cur = ROOT / rel
        now = sha256(cur) if cur.exists() else "MISSING"
        rows.append(dict(check="E1_metrics_input_sha256 (recorded on another machine path)", path=rel,
                         expected_sha256=h, current_sha256=now, status="PASS" if now == h else "FAIL"))
    for name, h in D["E7_meta"]["source_hashes"].items():
        rows.append(dict(check="E7_source_hash_vs_E8_provenance", path=name, expected_sha256=h,
                         current_sha256=D["E8_prov"]["graph_manifest"]["inputs_sha256"].get(name, "n/a"),
                         status="PASS" if D["E8_prov"]["graph_manifest"]["inputs_sha256"].get(name) == h else "FAIL"))
    rows.append(dict(check="E8_protocol_sha256 config vs metrics", path="models/gnn_cambridge/training_config.json",
                     expected_sha256=D["E8_config"]["protocol_sha256"], current_sha256=D["E8_metrics"]["protocol_sha256"],
                     status="PASS" if D["E8_config"]["protocol_sha256"] == D["E8_metrics"]["protocol_sha256"] else "FAIL"))
    tracked = git("status", "--porcelain", "--", "models", "data", "research/gnn", "training")
    rows.append(dict(check="git status of tracked protected paths", path="models data research/gnn training",
                     expected_sha256="clean", current_sha256=tracked or "clean",
                     status="PASS" if not tracked else "FAIL"))
    return pd.DataFrame(rows)


# ================================================================= figures
def fig_E1(D, A):
    l = D["E1_loss"]; c = A["E1_conv"]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.plot(l.epoch, l.train_mse_scaled, color=C1, label="Train (fitting rows, n=32)")
    ax.plot(l.epoch, l.validation_mse_scaled, color=C2, label="Inner validation (n=8)")
    ax.axvline(c["best_epoch"], color=GREY, ls="--", lw=1)
    ax.text(c["best_epoch"], ax.get_ylim()[1] * 0.9, f" restored epoch {c['best_epoch']}", color=INK2, ha="right")
    ax.set_yscale("log"); ax.set_xlabel("Epoch (max 2,000; patience 150)"); ax.set_ylabel("MSE on standardized ProjDura (log)")
    ax.set_title("E1  Mendeley MLP - single split: actual learning curve"); ax.legend(loc="upper right")
    savefig(fig, "E1_loss_curve", "E1 learning curve from models/duration_v1/loss_history.csv. The restored epoch is 1,957 of 2,000: patience never triggered.")


def fig_E3(D, A):
    fig, axes = plt.subplots(3, 5, figsize=(12, 6.4), sharey=True)
    conv = A["E3_conv"].set_index("run")
    for (r, f), h in D["E3_loss"].items():
        ax = axes[r - 1, f - 1]
        ax.plot(h.epoch, h.train_mse_scaled, color=C1, lw=1.1)
        ax.plot(h.epoch, h.validation_mse_scaled, color=C2, lw=1.1)
        b = conv.loc[f"r{r}f{f}", "best_epoch"]
        ax.axvline(b, color=GREY, ls="--", lw=0.9)
        ax.set_yscale("log"); ax.set_title(f"repeat {r} fold {f}  (best {b})", fontsize=8.5)
        if f == 1: ax.set_ylabel("scaled MSE (log)")
        if r == 3: ax.set_xlabel("epoch")
    axes[0, 0].plot([], [], color=C1, label="train"); axes[0, 0].plot([], [], color=C2, label="inner validation")
    axes[0, 0].legend(loc="lower left", fontsize=7.5)
    fig.suptitle("E3  Mendeley MLP - repeated grouped CV: all 15 actual learning curves", fontweight="bold", color=INK)
    fig.tight_layout()
    savefig(fig, "E3_loss_curves", "E3: the 15 saved loss histories (train vs inner-validation, standardized ProjDura MSE). Dashed line = restored epoch. Repeat 1 is byte-identical to E2.")

    cv = D["E3_cv"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for i, (m, col) in enumerate((("mean", GREY), ("ridge", C1), ("mlp", C2))):
        g = cv[cv.model == m]
        y = np.full(len(g), i) + np.linspace(-0.18, 0.18, len(g))
        ax.scatter(g.MAE, y, s=26, color=col, edgecolor=SURF, linewidth=1, zorder=3)
        ax.plot([g.MAE.mean()] * 2, [i - 0.3, i + 0.3], color=INK, lw=2)
        ax.text(g.MAE.mean(), i + 0.34, f"mean {g.MAE.mean():.2f}", ha="center", color=INK2, fontsize=8)
    ax.set_yticks([0, 1, 2], ["mean baseline", "ridge", "MLP"]); ax.set_ylim(-0.6, 2.7)
    ax.set_xlabel("Outer-fold MAE (ProjDura source units, unverified)")
    ax.set_title("E3  Outer-fold MAE across 15 folds (3 repeats x 5)")
    savefig(fig, "E3_fold_mae", "E3 per-fold outer MAE from cross_validation.csv. Folds share training records, so spread is variation, not a confidence interval.")


def fig_gnn(eid, D, A):
    oof = D[f"{eid}_oof"]; fm = A[f"{eid}_folds"]; auc = D[f"{eid}_auc"]["methods"]
    title = {"E4": "synthetic", "E5": "DSLIB all G/G", "E6": "DSLIB filtered"}[eid]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    ax = axes[0]
    for m, col in (("plan", GREY), ("mlp", C1), ("gnn", C2)):
        g = fm[fm.method == m].sort_values("fold")
        ax.plot(g.fold, g.MAE_days, "o-", color=col, label=m, markersize=5)
    ax.set_xticks(range(5)); ax.set_xlabel("fold"); ax.set_ylabel("MAE (days)")
    ax.set_title("Out-of-fold MAE per fold"); ax.legend()
    ax = axes[1]
    lim = [max(0.05, oof[["actual_days", "pred_gnn"]].min().min()), oof[["actual_days", "pred_gnn"]].max().max() * 1.2]
    ax.scatter(oof.actual_days, oof.pred_gnn, s=6, alpha=0.35, color=C2, edgecolor="none")
    ax.plot(lim, lim, color=GREY, lw=1, ls="--")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("actual days"); ax.set_ylabel("GNN OOF prediction (days)"); ax.set_title("GNN: actual vs predicted")
    ax = axes[2]
    for i, (m, col) in enumerate((("category", GREY), ("mlp", C1), ("gnn", C2))):
        vals = [v for v in auc[m]["per_fold"].values() if v is not None]
        ax.scatter(vals, [i] * len(vals), color=col, s=30, edgecolor=SURF, zorder=3)
    ax.axvline(0.5, color=INK2, lw=1, ls=":"); ax.text(0.5, 2.45, " chance", color=INK2, fontsize=8)
    ax.set_yticks([0, 1, 2], ["category", "MLP", "GNN"]); ax.set_xlim(0.3, 1.0); ax.set_ylim(-0.5, 2.7)
    ax.set_xlabel("ROC AUC per fold (overrun > 1.05 x plan)"); ax.set_title("Overrun ranking AUC per fold")
    fig.suptitle(f"{eid}  Duration GNN - {title}: evidence from saved OOF predictions", fontweight="bold", color=INK)
    fig.tight_layout()
    cap = {"E4": "E4 synthetic: labels come from a planted rule; these numbers test the pipeline only and are NOT evidence of real-world accuracy.",
           "E5": "E5 DSLIB all G/G: per-fold MAE, actual vs predicted and overrun AUC recomputed from saved OOF predictions.",
           "E6": "E6 DSLIB filtered sensitivity variant: same views as E5."}[eid]
    savefig(fig, f"{eid}_oof_evidence", cap)


def fig_E7(D, A):
    f7 = D["E7_folds"]
    fig, axes = plt.subplots(1, 5, figsize=(12, 3.0), sharex=True)
    order = ["median", "ridge", "random_forest", "mlp"]
    for f, ax in enumerate(axes):
        g = f7[f7.fold == f].set_index("model").loc[order]
        ax.barh(range(4), g.macro_group_mae_days, color=[GREY, C1, C1, C1], height=0.6)
        for i, v in enumerate(g.macro_group_mae_days):
            ax.text(v, i, f" {v:.1f}", va="center", fontsize=7.5, color=INK2)
        ax.set_yticks(range(4), order if f == 0 else [""] * 4); ax.invert_yaxis()
        ax.set_title(f"fold {f} ({int(g.groups.iloc[0])} block{'s' if g.groups.iloc[0] > 1 else ''})", fontsize=8.5)
        ax.set_xlabel("macro-block MAE (days)")
    fig.suptitle("E7  Cambridge classical models - development folds only (Stage 2.3E fold_metrics.csv)", fontweight="bold", color=INK)
    fig.tight_layout()
    savefig(fig, "E7_dev_folds", "E7 development-fold macro-block MAE. Held-out results on the 99 locked blocks are listed as a historical table only and are not plotted.")


def fig_E8(D, A):
    L = D["E8_loss"]; runs = D["E8_runs"]
    fig, axes = plt.subplots(2, 5, figsize=(13, 5.4), sharey=True)
    for i, m in enumerate(("graphsage", "no_graph")):
        for f in range(5):
            ax = axes[i, f]
            for s in (23051, 23052, 23053):
                g = L[(L.model == m) & (L.fold == f) & (L.seed == s)]
                ax.plot(g.epoch, g.train_l1_log, color=C1, lw=1)
                ax.plot(g.epoch, g.inner_stop_l1_log, color=C2, lw=1)
                ax.plot(g.epoch, g.outer_val_l1_log_monitor_only, color=C3, lw=1)
                b = runs.query("model == @m and fold == @f and seed == @s").best_epoch.iloc[0]
                ax.axvline(b, color=GREY, ls="--", lw=0.7)
            ax.set_title(f"{'GraphSAGE' if m == 'graphsage' else 'No-graph'} fold {f}", fontsize=8.5)
            if f == 0: ax.set_ylabel("L1 on log1p(days)")
            if i == 1: ax.set_xlabel("epoch (max 150, patience 15)")
    for lab, col in (("train (fitting blocks)", C1), ("inner stopping blocks", C2), ("outer fold (monitor only)", C3)):
        axes[0, 0].plot([], [], color=col, label=lab)
    axes[0, 0].legend(fontsize=7, loc="upper right")
    fig.suptitle("E8  Cambridge GraphSAGE vs matched no-graph: all 30 actual learning curves (3 seeds per panel)", fontweight="bold", color=INK)
    fig.tight_layout()
    savefig(fig, "E8_loss_curves", "E8 learning curves from models/gnn_cambridge/loss_curves.csv. Dashed lines = restored epoch per seed. Units are L1 on log1p(days) and are not comparable with E1-E3 scaled MSE.")

    cmp_ = D["E8_cmp"].set_index("model"); boot = D["E8_metrics"]["bootstrap"]["models"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.4))
    ax = axes[0]
    order = ["median", "ridge", "no_graph", "graphsage"]
    for i, m in enumerate(order):
        p = cmp_.loc[m, "mean_block_mae_days"]; lo, hi = boot[f"pred_{m}"]["ci95"]
        col = C2 if m == "graphsage" else C1 if m == "no_graph" else GREY
        ax.plot([lo, hi], [i, i], color=col, lw=2); ax.scatter([p], [i], color=col, s=40, zorder=3, edgecolor=SURF)
        ax.text(p, i + 0.25, f"{p:.2f}", ha="center", fontsize=8, color=INK2)
    ax.set_yticks(range(4), order); ax.set_xlabel("mean block MAE, days (95% block bootstrap)")
    ax.set_title("Development OOF: primary metric")
    ax = axes[1]
    F = D["E8_folds"]
    for m, col in (("median", GREY), ("no_graph", C1), ("graphsage", C2)):
        g = F[F.model == m].sort_values("fold")
        ax.plot(g.fold, g.mean_block_mae_days, "o-", color=col, label=m, markersize=5)
    ax.set_xticks(range(5)); ax.set_xlabel("fold"); ax.set_ylabel("mean block MAE (days)"); ax.legend()
    ax.set_title("Per fold")
    fig.suptitle("E8  Development-only comparison (locked test never evaluated)", fontweight="bold", color=INK)
    fig.tight_layout()
    savefig(fig, "E8_comparison", "E8 primary metric with stored block-bootstrap intervals, and per-fold mean block MAE.")

    S = D["E8_seeds"]
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    for i, (m, col) in enumerate((("no_graph", C1), ("graphsage", C2))):
        g = S[S.model == m]
        ax.scatter(g.mean_block_mae_days, [i] * 3, color=col, s=40, edgecolor=SURF, zorder=3)
        for _, r in g.iterrows():
            ax.text(r.mean_block_mae_days, i + 0.18, str(int(r.seed)), fontsize=7, ha="center", color=INK2)
        ens = cmp_.loc[m, "mean_block_mae_days"]
        ax.plot([ens, ens], [i - 0.25, i + 0.25], color=INK, lw=2)
    ax.set_yticks([0, 1], ["no-graph", "GraphSAGE"]); ax.set_ylim(-0.6, 1.6)
    ax.set_xlabel("mean block MAE, days (dots = single seeds, bar = 3-seed ensemble)")
    ax.set_title("E8  Seed spread is comparable to the GraphSAGE gain")
    savefig(fig, "E8_seed_spread", "E8 single-seed results versus the 3-seed ensemble (seed_metrics.csv).")


def fig_chronology():
    items = [("E1", "Stage 1", "Mendeley MLP\nsingle split", C1), ("E2/E3", "Stage 1 dev", "Mendeley grouped\nCV (1 & 3 repeats)", C1),
             ("E7", "Stage 2.3E", "Cambridge classical\nmedian/ridge/RF/MLP", GREY),
             ("E4", "Stage 3.5", "GNN synthetic\n(pipeline test)", C2), ("E5/E6", "Stage 3.5", "GNN DSLIB\nall / filtered", C2),
             ("E8", "Stage 3.7", "Cambridge GraphSAGE\nvs no-graph", C3)]
    fig, ax = plt.subplots(figsize=(12, 2.4))
    ax.axis("off"); ax.set_xlim(-0.5, len(items) - 0.5); ax.set_ylim(-1.3, 1.1)
    ax.plot([0, len(items) - 1], [0, 0], color=GRID, lw=3, zorder=1)
    for i, (eid, st, lab, col) in enumerate(items):
        ax.scatter([i], [0], s=160, color=col, zorder=3, edgecolor=SURF, linewidth=2)
        ax.text(i, 0.35, eid, ha="center", fontweight="bold", color=INK)
        ax.text(i, 0.72, st, ha="center", color=INK2, fontsize=8)
        ax.text(i, -0.45, lab, ha="center", va="top", color=INK2, fontsize=8)
    ax.set_title("Chronology by documented stage label (file timestamps are not reliable; see chronology.csv)", loc="left")
    savefig(fig, "chronology", "Experiment chronology by documented stage label. The Stage 3.5 checkpoints carry earlier file timestamps than the Stage 2.3E run log; the stage order is used.")


# ================================================================= architecture diagrams (SVG)
def _svg(title, boxes, arrows, w=880, h=None, notes=()):
    h = h or (max(b[1] + b[3] for b in boxes) + 40 + 18 * len(notes))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{html.escape(title)}" font-family="Segoe UI, Arial, sans-serif">',
           '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#52514e"/></marker></defs>',
           f'<rect width="{w}" height="{h}" fill="#fcfcfb"/>',
           f'<text x="16" y="24" font-size="15" font-weight="700" fill="#0b0b0b">{html.escape(title)}</text>']
    for x1, y1, x2, y2, *lab in arrows:
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#52514e" stroke-width="1.5" marker-end="url(#ah)"/>')
        if lab:
            out.append(f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 5}" font-size="10.5" text-anchor="middle" fill="#52514e">{html.escape(lab[0])}</text>')
    for x, y, bw, bh, text, kind in boxes:
        fill = {"in": "#eef4fc", "layer": "#ffffff", "graph": "#fdeee6", "out": "#e8f7f1", "note": "#f4f3f0"}[kind]
        stroke = {"in": C1, "layer": "#b9b8b2", "graph": C2, "out": C3, "note": "#d6d5d0"}[kind]
        out.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
        lines = text.split("\n")
        for i, t in enumerate(lines):
            yy = y + bh / 2 + (i - (len(lines) - 1) / 2) * 14 + 4
            out.append(f'<text x="{x + bw / 2}" y="{yy}" font-size="11.5" text-anchor="middle" fill="#0b0b0b">{html.escape(t)}</text>')
    base = max(b[1] + b[3] for b in boxes) + 26
    for i, n in enumerate(notes):
        out.append(f'<text x="16" y="{base + 18 * i}" font-size="11" fill="#52514e">{html.escape(n)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def architecture_svgs():
    ARCH_DIR.mkdir(parents=True, exist_ok=True)
    S = {}
    S["A1_mendeley_mlp"] = _svg("E1-E3  Mendeley tabular MLP (9-16-8-1, 305 parameters)", [
        (16, 50, 170, 60, "9 numeric features\nmedian impute + scale", "in"),
        (230, 50, 130, 60, "Linear 9->16\nReLU", "layer"),
        (400, 50, 130, 60, "Linear 16->8\nReLU", "layer"),
        (570, 50, 120, 60, "Linear 8->1", "layer"),
        (730, 50, 134, 60, "ProjDura\n(inverse scaled)", "out")],
        [(186, 80, 228, 80), (360, 80, 398, 80), (530, 80, 568, 80), (690, 80, 728, 80)],
        notes=["Adam lr 1e-3, weight decay 1e-3, full batch, MSE on standardized target; max 2,000 epochs, patience 150, best checkpoint restored.",
               "Baselines on the same fitting rows: training mean, Ridge(alpha=1)."])
    S["A2_duration_gnn"] = _svg("E4-E6  DurationGNN (55,617 parameters) and NodeMLP control", [
        (16, 50, 190, 64, "22 node features\nCPM, degree, depth,\n12 trade one-hot", "in"),
        (240, 50, 140, 64, "Encoder\nLinear 22->64, ReLU", "layer"),
        (414, 40, 230, 84, "x3 layers:\nSAGEConv(pred->succ)\n+ SAGEConv(succ->pred)\nReLU, dropout 0.1, +skip, LayerNorm", "graph"),
        (678, 50, 186, 64, "Head 64->64->1\nlog(actual/planned)", "out"),
        (240, 150, 404, 50, "NodeMLP control: Linear 22->64, ReLU, dropout, Linear 64->64, ReLU, Linear 64->1 (no message passing)", "note")],
        [(206, 82, 238, 82), (380, 82, 412, 82), (644, 82, 676, 82)],
        notes=["AdamW lr 3e-3, weight decay 1e-4, Huber(delta 0.5), one graph per step; epochs 150 (synthetic) / 200 (DSLIB), patience 30, seed 42+fold.",
               "Saved model.pt = refit on all projects for median CV best epoch (not the fold models that produced the OOF metrics)."])
    S["A3_cambridge_classical"] = _svg("E7  Cambridge classical pipeline (Stage 2.3E)", [
        (16, 50, 200, 64, "activity_description\nproject_type, uk_region", "in"),
        (250, 50, 220, 64, "TF-IDF 50k (1,2)-gram\n+ one-hot (sparse)", "layer"),
        (510, 34, 160, 40, "Ridge (lsqr), alpha per fold", "layer"),
        (510, 84, 160, 40, "Median of training target", "layer"),
        (250, 150, 220, 52, "TruncatedSVD 128\n+ StandardScaler", "layer"),
        (510, 140, 160, 40, "RandomForest 120 trees", "layer"),
        (510, 190, 160, 52, "SmallMLP 128-64-32-1\ndropout .25/.15", "layer"),
        (712, 100, 152, 64, "raw elapsed\ncalendar days", "out")],
        [(216, 82, 248, 82), (470, 60, 508, 54), (360, 114, 360, 148), (470, 170, 508, 160), (470, 185, 508, 214),
         (670, 54, 710, 120), (670, 104, 710, 130), (670, 160, 710, 140), (670, 214, 710, 150)],
        notes=["SmallMLP: AdamW lr 1e-3, wd 1e-3, batch 2048, MSE on standardized days, stop on L1 (10% inner blocks), max 100 epochs, patience 10."])
    S["A4_cambridge_sage"] = _svg("E8  CambridgeSAGE (46,465 parameters; identical no-graph arm with empty edge set)", [
        (16, 50, 200, 76, "TF-IDF -> SVD128 -> scaler\n+ one-hot type/region\n= 139 node inputs", "in"),
        (250, 56, 150, 64, "Encoder\nLinear 139->64\nReLU, dropout 0.2", "layer"),
        (434, 40, 236, 96, "x2 layers:\nSAGEConv mean (pred->succ)\n+ SAGEConv mean (succ->pred)\nReLU, dropout, residual,\nLayerNorm", "graph"),
        (704, 56, 160, 64, "Head 64->64->1\nlog1p(days)", "out")],
        [(216, 88, 248, 88), (400, 88, 432, 88), (670, 88, 702, 88)],
        notes=["AdamW lr 3e-3, wd 1e-4, L1 on log1p(days), batch 8 graphs; max 150 epochs, patience 15 on inner-stopping blocks, best restored.",
               "Seeds 23051-23053 per fold; primary prediction = mean of log predictions over seeds, expm1, clip at 0."])
    for k, v in S.items():
        (ARCH_DIR / f"{k}.svg").write_text(v, encoding="utf-8")
    return S


# ================================================================= narrative per experiment
def narratives(D, A):
    c1 = A["E1_conv"]; e1 = D["E1_metrics"]["test_metrics"]
    e3 = A["E3_summary"].set_index("model"); conv3 = A["E3_conv"]
    c8 = A["E8_conv"]; cmp8 = D["E8_cmp"].set_index("model")
    m = {k: D[f"{k}_metrics"] for k in ("E4", "E5", "E6")}
    auc = {k: D[f"{k}_auc"]["methods"] for k in ("E4", "E5", "E6")}
    f7 = A["E7_dev_summary"].set_index("model")
    N = {}
    N["E1"] = dict(
        objective="Predict total project duration (ProjDura) from nine physical project descriptors with a small MLP, as the first PMI duration model.",
        data="Mendeley tabular dataset. 40 training rows (32 fitting, 8 inner validation, grouped by project name) and a separate 10-row test file. Features: AreaSite, BuiltArea, TowerNum, TowerHgt, TowerFlr, BasementNum, AreaBase, UnitNum, AreaUnit. Cost columns excluded. Two different records named Pr29 remain grouped. Duration unit unverified.",
        method="One grouped fitting/validation split (seed 42). Imputer, feature scaler and target scaler fitted on the 32 fitting rows only. Best inner-validation epoch restored; no refit on all 40 rows. The 10 test rows were used once for final evaluation.",
        hyper=[("optimizer", "Adam"), ("learning rate", "0.001"), ("weight decay", "0.001"), ("batch", "full batch (32 rows)"),
               ("loss", "MSE on standardized ProjDura"), ("max epochs", "2000"), ("patience", "150"), ("seed", "42"),
               ("architecture", "9-16-8-1 ReLU"), ("ridge alpha (baseline)", "1.0")],
        epochs=f"Maximum 2,000. Executed {c1['epochs_run']}. Restored epoch {c1['best_epoch']}.",
        stopping=f"Lowest inner-validation scaled MSE ({D['E1_metrics']['experiment']['best_validation_mse_scaled']:.4f}) at epoch {c1['best_epoch']}. Patience did not trigger; the run hit the epoch cap.",
        metrics_md=pd.DataFrame([dict(model=k, MAE=v["MAE"], RMSE=v["RMSE"], R2=v["R2"]) for k, v in e1.items()]),
        metrics_note="10-row test file, ProjDura source units. Not comparable to any other experiment.",
        conv=f"Inner-validation loss fell from {c1['val_first']:.3f} to {c1['val_at_best']:.3f} and was still falling at the cap (drop over the last 200 epochs {c1['val_drop_last_200']:.4f}). Training loss ended at {c1['train_last']:.3f}, about a tenth of the validation loss, so the 305-parameter network fits its 32 rows far more closely than unseen rows. Validation loss never turned upward, so there is no classic overfitting turn within budget, but convergence was not reached: the stopping rule never fired.",
        limits=["Only 8 validation rows and 10 test rows; R2 of 0.866 on 10 rows is weak evidence.",
                "Later grouped CV (E3) gave mean MLP R2 of -0.28, so the single-split result did not generalise.",
                "Input hashes in metrics.json were recorded under another machine path; current files still match.",
                "Total-project duration; not an activity-level or IFC-change delay estimate."],
        next="A single 10-row test cannot separate model quality from split luck. Grouped repeated CV on the development rows (E2/E3) was the next step.")
    N["E2"] = dict(
        objective="First grouped 5-fold development validation of the E1 recipe, without loading the 10-row test file.",
        data="Same 40 Mendeley development rows and nine features as E1.",
        method="GroupKFold(5, shuffle, seed 42) by project name. Each outer fold calls the E1 trainer, which makes its own grouped inner validation split.",
        hyper=[("as E1", "all MLP and ridge settings identical"), ("repeats", "1 (seed 42)")],
        epochs="Per fold, identical to E3 repeat 1 (see E3).",
        stopping="As E3 repeat 1.",
        metrics_md=D["E2_cv"][["fold", "model", "MAE", "RMSE", "R2"]],
        metrics_note="Outer development folds. These five folds are byte-identical to E3 repeat 1 and must not be counted twice.",
        conv="Loss histories, checkpoints, fold CSVs and predictions are SHA-256 identical to E3 repeat 1 (verified file by file, not by size). Convergence is assessed under E3.",
        limits=["Duplicate evidence: E2 adds no independent information beyond E3 repeat 1.",
                "fold_manifest.json input hashes were recorded on another machine path."],
        next="One repeat gives a single grouping of 40 rows. E3 added two further shuffles to show grouping variance.")
    N["E3"] = dict(
        objective="Measure how stable the Mendeley MLP, ridge and mean baselines are across three different project groupings.",
        data="40 Mendeley development rows, nine features; 10-row test file never loaded. 24-26 fitting, 7-8 inner validation and 7-9 evaluation rows per fold.",
        method="3 repeats x GroupKFold(5) with seeds 42, 43, 44. Inner grouped validation chooses the MLP epoch; outer rows never select anything. Preprocessing and baselines fitted on inner fitting rows only.",
        hyper=[("as E1", "Adam lr 1e-3, wd 1e-3, MSE scaled, max 2000, patience 150"), ("repeats", "3"), ("seeds", "42, 43, 44")],
        epochs=f"Maximum 2,000 per fold. Executed {conv3.epochs_run.min()}-{conv3.epochs_run.max()}. Restored epochs {conv3.best_epoch.min()}-{conv3.best_epoch.max()} (median {int(conv3.best_epoch.median())}).",
        stopping="Patience 150 triggered in all 15 runs (executed = restored + 150). Lowest inner-validation scaled MSE restored.",
        metrics_md=A["E3_summary"].round(3),
        metrics_note="Mean and SD over 15 outer folds. Ridge has the lowest mean MAE; all three have negative mean R2.",
        conv=(f"All 15 runs stopped by patience. In {int((conv3.val_rise_after_best > 0).sum())} of 15 runs the inner-validation loss rose after the restored epoch while training loss kept falling (median further train drop {conv3.train_drop_after_best.median():.3f}), the classic overfitting signature on 7-8 validation rows. "
              f"Inner-validation MSE at the restored epoch ranges {conv3.val_mse_scaled_at_best.min():.2f}-{conv3.val_mse_scaled_at_best.max():.2f} (scaled units), so stopping is driven by very small, noisy validation sets."),
        limits=["40 records; folds share training rows, so SDs are variation, not confidence intervals.",
                "MLP mean MAE 6.48 vs ridge 6.25 vs mean 7.26: no model explains variance (R2 < 0).",
                "Unit and source licence unverified; repeated Pr29 identity unresolved."],
        next="Project-level tabular data was too small to support a neural model. Work moved to activity-level schedule data (Cambridge, DSLIB) with many more labelled rows.")
    for eid, label in (("E4", "synthetic"), ("E5", "DSLIB all G/G"), ("E6", "DSLIB filtered")):
        mm = m[eid]; a = mm["args"]; g = mm["gnn_vs_best_baseline"]
        N[eid] = dict(
            objective={"E4": "Check that the graph pipeline can learn a neighbour-dependent effect when one is planted. A pipeline test, not a result.",
                       "E5": "Test whether precedence-network message passing predicts real activity deviation from plan on Ghent DSLIB building projects.",
                       "E6": "Sensitivity variant of E5 after removing projects flagged by dslib.FILTER_RULES (for example tracking that mirrors the baseline)."}[eid],
            data=f"{mm['projects']} projects in {mm['independent_groups']} independent groups, {mm['labelled_activities']:,} labelled activities. 22 planning-time node features (CPM start/float, critical flag, degree, depth, project size, 12 trade one-hot)." +
                 (" Labels follow a known synthetic rule." if eid == "E4" else f" {A[f'{eid}_on_plan_share']:.0%} of labelled activities finished exactly on plan."),
            method="5-fold cross-validation over project groups; 15% of training groups held out for early stopping; scaling fitted on training nodes. Baselines: plan, global median ratio, per-category median ratio, NodeMLP. Paired bootstrap (2,000) over projects against the best non-graph method.",
            hyper=[("optimizer", "AdamW"), ("learning rate", str(a["lr"])), ("weight decay", "1e-4"), ("loss", "Huber delta 0.5 on log(actual/planned)"),
                   ("hidden", str(a["hidden"])), ("layers", str(a["layers"])), ("dropout", "0.1"), ("max epochs", str(a["epochs"])),
                   ("patience", str(a["patience"])), ("seed", f"{a['seed']} + fold"), ("folds", str(a["folds"]))],
            epochs=f"Maximum {a['epochs']} per fold. Executed and per-fold best epochs were printed to the console only and not saved.",
            stopping=f"Lowest early-stopping Huber loss, patience {a['patience']}, best state restored. The saved model.pt is a separate refit on all projects for the median CV best epoch.",
            metrics_md=pd.DataFrame([dict(method=k, **v) for k, v in mm["metrics"].items()]),
            metrics_note=f"Activity OOF metrics in days on {label}. GNN vs {g['baseline']}: {g['mean_diff_MAE_days_per_project']:+.3f} days per project, 95% CI {g['bootstrap_95ci']}. Overrun AUC per fold GNN {auc[eid]['gnn']['min_fold']}-{auc[eid]['gnn']['max_fold']}, MLP {auc[eid]['mlp']['min_fold']}-{auc[eid]['mlp']['max_fold']}. All stored values reproduced from oof_predictions.csv.",
            conv="No per-epoch history was saved, so convergence, overfitting and underfitting cannot be assessed from curves. " +
                 {"E4": "Out-of-fold error is low and consistent across folds, which shows the model fits the planted rule without obvious overfitting.",
                  "E5": "Out-of-fold, both neural models are worse than 'actual = planned'. With most labels exactly on plan, this is consistent with fitting noise rather than signal.",
                  "E6": "Same pattern as E5; per-project MAE is worse for GNN than MLP (6.80 vs 6.38)."}[eid],
            limits={"E4": ["Synthetic labels are generated by known rules. This is NOT evidence of real-world predictive accuracy.",
                           "No learning curves or per-fold best epochs saved."],
                    "E5": ["Only 17 independent groups; labels dominated by on-plan values.",
                           "22% of activity names match no trade; FS/SS/FF/SF treated as FS in CPM features; lags ignored.",
                           "No learning curves or per-fold best epochs saved; model.pt is not the fold model."],
                    "E6": ["Only 15 groups; bootstrap CI crosses 0 but point estimate favours plan.",
                           "Filtering rules chosen after inspecting E5 data; sensitivity only.",
                           "No learning curves saved."]}[eid],
            next={"E4": "The pipeline learned a planted graph effect, so it was applied to real DSLIB projects (E5).",
                  "E5": "No model beat the plan. A filtered sensitivity run (E6) checked whether tracking artefacts explained this.",
                  "E6": "Filtering did not change the conclusion. Too few independent groups; the larger Cambridge dataset with a frozen protocol became the main test bed (E8, building on E7)."}[eid])
    N["E7"] = dict(
        objective="Exploratory retrospective estimates of reported completed-activity elapsed calendar days on Cambridge JPF data with non-graph models, under the frozen Stage 2.3D protocol.",
        data="Cambridge JPF export. Features: activity_description, project_type, uk_region only. 144,110 development rows in 70 conservative blocks; 36,027 locked test rows in 99 blocks (not opened by this audit).",
        method="Five frozen development folds (fold 0 = the dominant 99,636-row block). Ridge alpha selected per fold on a 10% inner block subset. Model order by mean development macro-group MAE, locked before the single held-out evaluation in Stage 2.3E.",
        hyper=[("ridge", "lsqr, max_iter 2000, alpha by fold [10,10,10,10,1]"), ("random forest", "120 trees, max_depth 24, min_samples_leaf 4, max_features 0.6"),
               ("MLP", "128-64-32-1, dropout .25/.15, AdamW lr 1e-3, wd 1e-3, batch 2048"), ("MLP loss", "MSE on standardized days; stop on L1"),
               ("MLP max epochs / patience", "100 / 10"), ("text", "TF-IDF 50k (1,2)-gram, min_df 2, max_df .98, sublinear"),
               ("dense projection", "TruncatedSVD 128 + StandardScaler"), ("seed", str(D["E7_meta"]["seed"]))],
        epochs="MLP maximum 100 per fold. Executed and best epochs were not saved.",
        stopping="MLP: lowest L1 on standardized days over inner 10% development blocks, patience 10.",
        metrics_md=A["E7_dev_summary"].round(3),
        metrics_note="Development folds only (mean over folds). The median wins on this statistic (44.54). The stored historical held-out table is shown separately below and is not used for any ranking.",
        conv="No learning curves were saved for the MLP, so convergence cannot be assessed. RF and ridge are non-iterative in this sense.",
        limits=["Target is reported elapsed calendar days, not verified working durations.",
                "Development folds are highly unequal; fold 0 is one block of 99,636 rows.",
                "The 99 locked blocks were already evaluated once in Stage 2.3E and must not be reused for confirmation.",
                "Prediction-time provenance of features is unverified."],
        next="No non-graph model clearly beat the median. The next question was whether precedence-network context adds signal, under a matched-arm protocol on development folds only (E8).")
    N["E8"] = dict(
        objective="Test, under a frozen pre-registered protocol, whether GraphSAGE message passing over the exported precedence network reduces error versus an identical network with no edges.",
        data="Same 144,110 development rows / 70 blocks as E7, as 163 project graphs (all exported activities are nodes; only eligible development rows labelled). 139 node inputs. Locked test projects never materialised.",
        method="5 frozen development folds x 3 seeds per arm. Inner stopping blocks chosen by the Stage 2.3E hash rule. Outer fold loss logged for curves only. Primary metric mean block MAE over 70 blocks; paired 2,000-sample block bootstrap.",
        hyper=[("optimizer", "AdamW"), ("learning rate", "0.003"), ("weight decay", "1e-4"), ("loss", "L1 on log1p(days)"),
               ("batch", "8 graphs"), ("hidden", "64"), ("graph layers", "2"), ("dropout", "0.2"), ("max epochs", "150"),
               ("patience / min_delta", "15 / 1e-4"), ("seeds", "23051, 23052, 23053"), ("protocol sha256", D["E8_config"]["protocol_sha256"][:16] + "...")],
        epochs=f"Maximum 150 per run. Executed {c8.epochs_run.min()}-{c8.epochs_run.max()}; restored {c8.best_epoch.min()}-{c8.best_epoch.max()}. GraphSAGE total {int(c8[c8.model == 'graphsage'].epochs_run.sum())} epochs, no-graph {int(c8[c8.model == 'no_graph'].epochs_run.sum())}.",
        stopping=f"Lowest inner-stopping L1, patience 15, best restored. All 30 runs stopped by patience. {int(c8.restored_epoch_le_4.sum())} runs restored epoch 1-4.",
        metrics_md=D["E8_cmp"].round(3),
        metrics_note=f"Development OOF only. GraphSAGE - no-graph mean block MAE {D['E8_metrics']['bootstrap']['paired_differences']['graphsage_minus_no_graph']['point']:.2f} days, 95% CI {[round(x, 2) for x in D['E8_metrics']['bootstrap']['paired_differences']['graphsage_minus_no_graph']['ci95']]}. Pre-registered criterion met. Stored values reproduced from oof_predictions.csv.",
        conv=f"Training L1 keeps falling while inner-stopping L1 plateaus within roughly 5-15 epochs; at the restored epoch the outer-fold L1 exceeds training L1 by a median {c8.outer_minus_train_at_best.median():.3f}. This indicates weak between-block signal and mild overfitting after early epochs, controlled by early stopping. The outer-fold monitor curve is nearly flat after the first epochs.",
        limits=["Development-only; the 99 locked blocks were not evaluated and must not be used to confirm this result.",
                "Gain is concentrated in small blocks; activity MAE improves only 0.55 days; R2 about 0; RMSE about 100 days.",
                "Seed spread is comparable to the effect; the bootstrap excludes seed uncertainty.",
                f"training_runs.csv shows {int(c8.restored_epoch_le_4.sum())} runs restoring epoch 1-4; cambridge_training_results.md says four and lists five. The saved run table is authoritative.",
                "Executed protocol differs from the Stage 3.7B proposal (TF-IDF/SVD not hashing, 2 layers not 3, L1 on log1p not Huber, 150/15 not 200/30, 3 seeds not 5).",
                "Exported precedence may include execution-period edits; relation types merged, lags omitted, cycles retained."],
        next="The development criterion was met with a small effect. The next stage needs a confirmatory design that does not reuse the already-used locked blocks, plus verified labels and planning-time edge provenance.")
    return N


# ================================================================= tables
def write_csvs(D, A, ck, pres):
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    inv = []
    for e in EXPERIMENTS:
        inv.append({k: e[k] for k in ("id", "stage", "name", "folder", "family", "dataset", "target", "loss", "partition")})
    inv = pd.DataFrame(inv)
    inv["comparable_group"] = inv.id.map({"E1": "G1 Mendeley 10-row test", "E2": "G2 Mendeley dev CV (duplicate of E3 r1)",
                                         "E3": "G2 Mendeley dev CV", "E4": "G3 synthetic only", "E5": "G4 DSLIB all",
                                         "E6": "G5 DSLIB filtered", "E7": "G6 Cambridge dev raw days", "E8": "G7 Cambridge dev log1p-trained"})
    inv.to_csv(CSV_DIR / "experiment_inventory.csv", index=False)

    chron = pd.DataFrame([
        dict(order=1, id="E1", stage="Stage 1", evidence_first_commit=first_commit("models/duration_v1/metrics.json"), file_mtime_note="all artefacts 2026-11-12 10:12:50 (copy time, not training time)"),
        dict(order=2, id="E2", stage="Stage 1 dev validation", evidence_first_commit=first_commit("data/processed/duration_validation/cross_validation.csv"), file_mtime_note="2026-11-12 10:12 (copy time)"),
        dict(order=3, id="E3", stage="Stage 1 dev validation", evidence_first_commit=first_commit("data/processed/duration_validation_repeated/cross_validation.csv"), file_mtime_note="2026-11-12 10:12 (copy time)"),
        dict(order=4, id="E7", stage="Stage 2.3E", evidence_first_commit=first_commit(f"{STAGE2}/run_log.txt"), file_mtime_note="run_log.txt: 2026-11-12T18:38:43 to 18:59:12 +01:00"),
        dict(order=5, id="E4", stage="Stage 3.5", evidence_first_commit=first_commit("models/gnn_synthetic/metrics.json"), file_mtime_note="model.pt mtime 2026-11-12 15:31 (earlier than the E7 run log; conflict unresolved)"),
        dict(order=6, id="E5", stage="Stage 3.5", evidence_first_commit=first_commit("models/gnn_dslib/metrics.json"), file_mtime_note="model.pt mtime 2026-11-12 15:36"),
        dict(order=7, id="E6", stage="Stage 3.5", evidence_first_commit=first_commit("models/gnn_dslib_filtered/metrics.json"), file_mtime_note="model.pt mtime 2026-11-12 15:37"),
        dict(order=8, id="E8", stage="Stage 3.7", evidence_first_commit=first_commit("models/gnn_cambridge/metrics.json"), file_mtime_note="run started 2026-11-16T18:26:10 +01:00 at commit cc38083 (dirty tree)"),
    ])
    chron.to_csv(CSV_DIR / "chronology.csv", index=False)

    reg = []
    def add_loss(path, eid, run, loss_def, transform, partition):
        p = ROOT / path; df = pd.read_csv(guard(path))
        reg.append(dict(path=path, experiment=eid, run=run, columns="|".join(df.columns), rows=len(df), sha256=sha256(p),
                        loss_definition=loss_def, target_transform=transform, partitions=partition))
    add_loss("models/duration_v1/loss_history.csv", "E1", "single", "MSE (nn.MSELoss), full batch", "StandardScaler(ProjDura) on 32 fitting rows", "train=fitting rows; validation=inner grouped 8 rows")
    for d, eid, reps in (("data/processed/duration_validation", "E2", 1), ("data/processed/duration_validation_repeated", "E3", 3)):
        for r in range(1, reps + 1):
            for f in range(1, 6):
                add_loss(f"{d}/repeat_{r}_fold_{f}/loss_history.csv", eid, f"r{r}f{f}", "MSE (nn.MSELoss), full batch",
                         "StandardScaler(ProjDura) on fold fitting rows", "train=inner fitting rows; validation=inner grouped validation rows")
    add_loss("models/gnn_cambridge/loss_curves.csv", "E8", "30 runs (model x fold x seed)", "L1 on log1p(days), batch of 8 graphs",
             "log1p(reported elapsed calendar days)", "train=fitting blocks; inner_stop=stopping blocks; outer=validation fold (monitor only)")
    reg = pd.DataFrame(reg)
    reg["identical_to"] = reg.groupby("sha256").path.transform(lambda s: ";".join(s) if len(s) > 1 else "")
    reg.to_csv(CSV_DIR / "loss_history_registry.csv", index=False)

    ck.to_csv(CSV_DIR / "checkpoint_inventory.csv", index=False)
    pres.to_csv(CSV_DIR / "preservation_verification.csv", index=False)
    A["E2_E3_identity"].to_csv(CSV_DIR / "E2_vs_E3_repeat1_identity.csv", index=False)

    pd.DataFrame([dict(model=k, **v) for k, v in D["E1_metrics"]["test_metrics"].items()]) \
        .to_csv(CSV_DIR / "metrics_E1_mendeley_10row_test.csv", index=False)
    D["E1_pred"].to_csv(CSV_DIR / "predictions_E1_copy_of_saved_10row_test.csv", index=False)
    D["E3_cv"].to_csv(CSV_DIR / "metrics_E3_outer_folds.csv", index=False)
    A["E3_summary"].to_csv(CSV_DIR / "metrics_E3_summary.csv", index=False)
    for eid in ("E4", "E5", "E6"):
        A[f"{eid}_check"].to_csv(CSV_DIR / f"metrics_{eid}_oof_stored_vs_recomputed.csv", index=False)
        A[f"{eid}_folds"].to_csv(CSV_DIR / f"metrics_{eid}_per_fold.csv", index=False)
        rows = []
        for mth, r in D[f"{eid}_auc"]["methods"].items():
            for f, v in r["per_fold"].items():
                rows.append(dict(method=mth, fold=f, auc=v))
            rows.append(dict(method=mth, fold="pooled", auc=r["pooled"]))
        pd.DataFrame(rows).to_csv(CSV_DIR / f"metrics_{eid}_overrun_auc.csv", index=False)
    D["E7_folds"].to_csv(CSV_DIR / "metrics_E7_development_folds.csv", index=False)
    A["E7_dev_summary"].to_csv(CSV_DIR / "metrics_E7_development_summary.csv", index=False)
    h = D["E7_heldout_hist"].copy()
    h.insert(0, "WARNING", "Historical Stage 2.3E held-out aggregate on the 99 locked blocks; copied from model_comparison.csv; not recomputed; never compare with development metrics")
    h.to_csv(CSV_DIR / "metrics_E7_HISTORICAL_heldout_aggregate.csv", index=False)
    D["E8_cmp"].to_csv(CSV_DIR / "metrics_E8_development_comparison.csv", index=False)
    D["E8_folds"].to_csv(CSV_DIR / "metrics_E8_development_folds.csv", index=False)
    D["E8_seeds"].to_csv(CSV_DIR / "metrics_E8_seeds.csv", index=False)
    D["E8_runs"].to_csv(CSV_DIR / "E8_training_runs.csv", index=False)
    A["E8_check"].to_csv(CSV_DIR / "metrics_E8_stored_vs_recomputed.csv", index=False)
    pd.concat([pd.DataFrame([dict(experiment="E1", run="single", **A["E1_conv"])]), A["E3_conv"], A["E8_conv"]], ignore_index=True) \
        .to_csv(CSV_DIR / "convergence_diagnostics.csv", index=False)

    hp = []
    for eid, n in NARR.items():
        for k, v in n["hyper"]:
            hp.append(dict(experiment=eid, parameter=k, value=v))
    pd.DataFrame(hp).to_csv(CSV_DIR / "hyperparameters.csv", index=False)
    UNAVAILABLE.to_csv(CSV_DIR / "unavailable_evidence.csv", index=False)
    pd.DataFrame({"file_read_by_generator": sorted(set(_READ_LOG))}).to_csv(CSV_DIR / "files_read.csv", index=False)


UNAVAILABLE = pd.DataFrame([
    ("E4-E6", "Per-epoch training/validation loss histories", "train.py keeps losses in memory only; nothing saved"),
    ("E4-E6", "Per-fold best and executed epochs", "printed to console only; not in metrics.json"),
    ("E4-E6", "Fold-level checkpoints behind the OOF metrics", "only a refit-on-all model.pt was saved"),
    ("E4-E6", "Paired GNN vs MLP significance test", "bootstrap compares GNN only with the best non-graph method"),
    ("E4-E6", "Run log, environment beyond python/torch versions, git commit", "not written by train.py"),
    ("E7", "MLP loss history, executed and best epochs (CV and final)", "fit_mlp does not record them"),
    ("E7", "Development OOF predictions file", "only fold-level metrics were saved"),
    ("E7", "Hashes of models/cambridge_duration_v1 at creation time", "no manifest written; current hashes recorded here"),
    ("E7", "Row-level held-out evidence", "deliberately not opened: locked-test derived"),
    ("E1-E3", "Verified duration unit and source licence for Mendeley data", "flagged as unverified by the original pipeline"),
    ("E1-E3", "Original-machine input files at the recorded paths", "metrics.json paths point to another user's machine"),
    ("E8", "Locked-test performance", "protocol forbids evaluating the 99 locked blocks in this stage"),
    ("E8", "Exact ensemble reconstruction from saved per-seed day predictions", "per-seed predictions were clipped before saving"),
    ("All", "Reliable training timestamps for E1-E6", "file times reflect copy/checkout; only E7 and E8 have run logs"),
], columns=["experiment", "missing_evidence", "reason"])
NARR: dict = {}


# ================================================================= Markdown report
def md_table(df):
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].map(lambda v: f"{v:.4g}" if abs(v) < 1e4 else f"{v:,.0f}")
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in df.astype(str).values) + "\n"


def write_md(D, A, ck, pres, svgs):
    N = NARR
    L = [f"# Stage 4.0A - Expanded experiment inventory and evaluation", "",
         f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `build_stage4_0a_report.py`. Read-only audit: no training, inference, prediction regeneration, protected-file edits, locked-test access, commit or push.", "",
         "## Rules applied", "",
         "- Every metric stays inside its own evaluation partition and target transformation. No cross-experiment ranking is made.",
         "- Loss histories with `train_mse_scaled` / `validation_mse_scaled` come from the Mendeley tabular MLP (E1, E2, E3). Cambridge GraphSAGE losses (E8) are L1 on log1p(days). They are never plotted on shared axes.",
         "- Synthetic results (E4) are a pipeline test, never evidence of real-world accuracy.",
         "- Stage 2.3E held-out numbers are historical, on the same 99 locked blocks that Stage 3.7 protects. They are reproduced from the stored aggregate only.", "",
         "## Chronological overview", "", "![chronology](figures/chronology.png)", "",
         md_table(pd.read_csv(CSV_DIR / "chronology.csv")), "",
         "Stage labels define the order. The Stage 3.5 GNN checkpoints have file times earlier than the Stage 2.3E run log, so file times are not used.", "",
         "## Experiment inventory", "", md_table(pd.read_csv(CSV_DIR / "experiment_inventory.csv")[["id", "stage", "name", "target", "loss", "comparable_group"]]), "",
         "## Loss-history provenance", "",
         md_table(pd.read_csv(CSV_DIR / "loss_history_registry.csv")[["path", "experiment", "run", "columns", "rows"]]), ""]
    figmap = {"E1": ["E1_loss_curve"], "E2": [], "E3": ["E3_loss_curves", "E3_fold_mae"], "E4": ["E4_oof_evidence"],
              "E5": ["E5_oof_evidence"], "E6": ["E6_oof_evidence"], "E7": ["E7_dev_folds"], "E8": ["E8_loss_curves", "E8_comparison", "E8_seed_spread"]}
    archmap = {"E1": "A1_mendeley_mlp", "E3": "A1_mendeley_mlp", "E2": "A1_mendeley_mlp", "E4": "A2_duration_gnn", "E5": "A2_duration_gnn",
               "E6": "A2_duration_gnn", "E7": "A3_cambridge_classical", "E8": "A4_cambridge_sage"}
    for e in EXPERIMENTS:
        n = N[e["id"]]
        L += [f"## {e['id']} - {e['name']}", "", f"*{e['stage']} - `{e['folder']}`*", "",
              f"**Research objective.** {n['objective']}", "", f"**Dataset and features.** {n['data']}", "",
              f"**Model architecture.** See `figures/architecture/{archmap[e['id']]}.svg`.", "", f"![arch](figures/architecture/{archmap[e['id']]}.svg)", "",
              f"**Training and validation methodology.** {n['method']}", "",
              "**Hyperparameters.**", "", md_table(pd.DataFrame(n["hyper"], columns=["parameter", "value"])), "",
              f"**Maximum and executed epochs.** {n['epochs']}", "", f"**Best checkpoint and stopping criterion.** {n['stopping']}", ""]
        for fname in figmap[e["id"]]:
            L += [f"![{fname}](figures/{fname}.png)", "", f"*{CAPTIONS[fname]}*", ""]
        if not figmap[e["id"]]:
            L += ["**Actual learning curves.** Identical to E3 repeat 1; see the E3 figure.", ""]
        L += ["**Performance metrics.**", "", md_table(n["metrics_md"]), "", n["metrics_note"], ""]
        if e["id"] == "E7":
            L += ["**Historical held-out aggregate (Stage 2.3E, 99 locked blocks; not recomputed, not ranked against anything).**", "",
                  md_table(D["E7_heldout_hist"]), ""]
        L += [f"**Convergence, overfitting or underfitting.** {n['conv']}", "", "**Research limitations.**", ""]
        L += [f"- {x}" for x in n["limits"]]
        L += ["", f"**Reason for moving to the next experiment.** {n['next']}", ""]
    nfail = int((pres.status == "FAIL").sum())
    L += ["## Checkpoint metadata and hashes", "",
          "Hashes, not file sizes, decide identity. The three Stage 3.5 `model.pt` files share a size of 232,503 bytes but have distinct SHA-256 values and distinct `source` metadata.", "",
          md_table(ck[["experiment", "path", "bytes", "sha256"]].assign(sha256=lambda d: d.sha256.str[:16] + "...")), "",
          "## Preservation verification", "",
          md_table(pres.groupby("check").status.agg(total="count", passed=lambda s: int(s.str.startswith("PASS").sum())).reset_index()), "",
          f"Failures: {nfail}. Full list in `csv/preservation_verification.csv`.", "",
          "## Unavailable evidence", "", md_table(UNAVAILABLE), ""]
    (HERE / "stage4_0a_evaluation_report.md").write_text("\n".join(L), encoding="utf-8")


# ================================================================= HTML report
def b64(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def html_table(df, cls="sortable"):
    df = df.copy()
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = []
    for r in df.itertuples(index=False):
        cells = []
        for v in r:
            if isinstance(v, (float, np.floating)):
                s = f"{v:.4g}" if abs(v) < 1e4 else f"{v:,.0f}"
                cells.append(f'<td class="num" data-v="{v}">{s}</td>')
            elif isinstance(v, (int, np.integer)) and not isinstance(v, bool):
                cells.append(f'<td class="num" data-v="{v}">{v}</td>')
            else:
                cells.append(f"<td>{html.escape(str(v))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="tw"><table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def loss_payload(D):
    """Per-experiment loss data for the interactive explorer. Each experiment keeps its own axis and units."""
    P = {}
    l = D["E1_loss"]
    P["E1"] = {"units": "MSE on standardized ProjDura", "series": ["train_mse_scaled", "validation_mse_scaled"],
               "runs": {"single split": {"epoch": l.epoch.tolist()[::4], "train_mse_scaled": l.train_mse_scaled.round(5).tolist()[::4],
                                          "validation_mse_scaled": l.validation_mse_scaled.round(5).tolist()[::4],
                                          "best": int(D["E1_metrics"]["experiment"]["best_epoch"])}}}
    runs = {}
    for (r, f), h in D["E3_loss"].items():
        man = next(x for x in D["E3_manifest"] if x["repeat"] == r and x["fold"] == f)
        step = max(1, len(h) // 400)
        runs[f"repeat {r} fold {f}"] = {"epoch": h.epoch.tolist()[::step], "train_mse_scaled": h.train_mse_scaled.round(5).tolist()[::step],
                                        "validation_mse_scaled": h.validation_mse_scaled.round(5).tolist()[::step], "best": int(man["best_epoch"])}
    P["E3"] = {"units": "MSE on standardized ProjDura", "series": ["train_mse_scaled", "validation_mse_scaled"], "runs": runs}
    runs = {}
    for (m, f, s), g in D["E8_loss"].groupby(["model", "fold", "seed"]):
        b = int(D["E8_runs"].query("model == @m and fold == @f and seed == @s").best_epoch.iloc[0])
        runs[f"{m} fold {f} seed {s}"] = {"epoch": g.epoch.tolist(), "train_l1_log": g.train_l1_log.round(5).tolist(),
                                          "inner_stop_l1_log": g.inner_stop_l1_log.round(5).tolist(),
                                          "outer_val_l1_log_monitor_only": g.outer_val_l1_log_monitor_only.round(5).tolist(), "best": b}
    P["E8"] = {"units": "L1 on log1p(days)", "series": ["train_l1_log", "inner_stop_l1_log", "outer_val_l1_log_monitor_only"], "runs": runs}
    return P


CSS = """
:root{--surface:#fcfcfb;--panel:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--rule:#e4e3df;--accent:#2a78d6;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--warn-bg:#fff6e5;--warn:#8a5a00;--bad-bg:#fdecec;--bad:#a12a2a;--ok:#1d7a3a;--code:#f4f3f0}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--surface:#1a1a19;--panel:#222220;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e86;
--rule:#3a3936;--accent:#3987e5;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--warn-bg:#3a2e12;--warn:#f2c46b;--bad-bg:#3d1d1d;--bad:#f29b9b;--ok:#6fd08f;--code:#2b2a28}}
:root[data-theme="dark"]{--surface:#1a1a19;--panel:#222220;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e86;--rule:#3a3936;--accent:#3987e5;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--warn-bg:#3a2e12;--warn:#f2c46b;--bad-bg:#3d1d1d;--bad:#f29b9b;--ok:#6fd08f;--code:#2b2a28}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,-apple-system,sans-serif}
.layout{display:grid;grid-template-columns:250px minmax(0,1fr);max-width:1400px;margin:0 auto}
nav{position:sticky;top:0;height:100vh;overflow:auto;padding:20px 14px;border-right:1px solid var(--rule)}
nav a{display:block;color:var(--ink2);text-decoration:none;padding:4px 8px;border-radius:6px;font-size:13.5px}
nav a:hover,nav a.on{background:var(--code);color:var(--ink)}nav .grp{margin:14px 8px 4px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
main{padding:28px 32px 80px;min-width:0}h1{font-size:26px;margin:0 0 6px}h2{font-size:21px;margin:40px 0 10px;padding-top:10px;border-top:1px solid var(--rule)}
h3{font-size:16px;margin:22px 0 6px}p{max-width:80ch}.sub{color:var(--ink2)}
.callout{border-left:4px solid var(--warn);background:var(--warn-bg);padding:10px 14px;border-radius:6px;margin:12px 0;max-width:95ch}
.callout.bad{border-color:var(--bad);background:var(--bad-bg)}.tag{display:inline-block;font-size:12px;padding:1px 8px;border-radius:999px;background:var(--code);color:var(--ink2);margin-right:6px}
.tw{overflow-x:auto;margin:8px 0 14px}table{border-collapse:collapse;font-size:13px;min-width:50%}
th,td{border-bottom:1px solid var(--rule);padding:5px 10px;text-align:left;vertical-align:top}th{color:var(--ink2);font-weight:600;cursor:pointer;white-space:nowrap;position:sticky;top:0;background:var(--surface)}
td.num{text-align:right;font-variant-numeric:tabular-nums}.pass{color:var(--ok);font-weight:600}.fail{color:var(--bad);font-weight:600}
img.fig{max-width:100%;border:1px solid var(--rule);border-radius:8px;background:#fcfcfb}figure{margin:12px 0 18px}figcaption{color:var(--ink2);font-size:13px;max-width:95ch}
.arch{overflow-x:auto;border:1px solid var(--rule);border-radius:8px;background:#fcfcfb;margin:10px 0}.arch svg{display:block;max-width:100%;height:auto}
details{border:1px solid var(--rule);border-radius:8px;padding:6px 12px;margin:8px 0;background:var(--panel)}summary{cursor:pointer;font-weight:600}
dl.facts{display:grid;grid-template-columns:220px minmax(0,1fr);gap:6px 16px;margin:10px 0}dl.facts dt{color:var(--ink2);font-weight:600}dl.facts dd{margin:0}
.explorer{border:1px solid var(--rule);border-radius:8px;padding:12px;background:var(--panel);margin:12px 0}
.explorer .ctl{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:8px;font-size:13px}
select,button{font:inherit;font-size:13px;padding:4px 8px;border:1px solid var(--rule);border-radius:6px;background:var(--surface);color:var(--ink)}
.chart{position:relative}.chart svg{width:100%;height:300px;display:block}.tip{position:absolute;pointer-events:none;background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:6px 8px;font-size:12px;display:none;box-shadow:0 2px 8px rgba(0,0,0,.12);white-space:nowrap}
.legend{display:flex;gap:14px;font-size:12.5px;color:var(--ink2);flex-wrap:wrap}.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:5px;vertical-align:middle}
.timeline{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.tl{border:1px solid var(--rule);border-radius:8px;padding:10px;background:var(--panel)}.tl b{display:block}.tl small{color:var(--ink2)}
.theme{position:fixed;top:12px;right:14px;z-index:5}
@media (max-width:860px){.layout{grid-template-columns:1fr}nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--rule)}main{padding:16px}dl.facts{grid-template-columns:1fr}}
"""

JS = r"""
const LOSS = __LOSS__;
document.querySelectorAll('table.sortable').forEach(t=>{t.querySelectorAll('th').forEach((th,i)=>{th.title='Sort';th.addEventListener('click',()=>{
 const tb=t.tBodies[0],rows=[...tb.rows],asc=th.dataset.s!=='a';t.querySelectorAll('th').forEach(x=>delete x.dataset.s);th.dataset.s=asc?'a':'d';
 rows.sort((a,b)=>{const A=a.cells[i],B=b.cells[i];const x=A.dataset.v!==undefined?+A.dataset.v:A.textContent,y=B.dataset.v!==undefined?+B.dataset.v:B.textContent;
 return (x>y?1:x<y?-1:0)*(asc?1:-1)});rows.forEach(r=>tb.appendChild(r));});});});
const COLORS=['--s1','--s2','--s3'];const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
function draw(box){const exp=box.dataset.exp,D=LOSS[exp],sel=box.querySelector('select.run'),logy=box.querySelector('input.logy').checked;
 const run=D.runs[sel.value],svg=box.querySelector('svg'),W=svg.clientWidth||800,H=300,m={l:58,r:16,t:12,b:34};
 const xs=run.epoch,ser=D.series;let lo=Infinity,hi=-Infinity;ser.forEach(s=>run[s].forEach(v=>{if(v>0||!logy){lo=Math.min(lo,v);hi=Math.max(hi,v)}}));
 const ty=v=>logy?Math.log10(Math.max(v,1e-9)):v;const y0=ty(lo),y1=ty(hi)+(ty(hi)-ty(lo))*0.05||1;const x0=xs[0],x1=xs[xs.length-1];
 const X=v=>m.l+(v-x0)/(x1-x0||1)*(W-m.l-m.r),Y=v=>H-m.b-(ty(v)-y0)/(y1-y0||1)*(H-m.t-m.b);
 let g=`<rect width="${W}" height="${H}" fill="none"/>`;for(let k=0;k<=4;k++){const yy=m.t+k*(H-m.t-m.b)/4;const val=y1-(y1-y0)*k/4;const lab=logy?Math.pow(10,val):val;
 g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${yy}" y2="${yy}" stroke="${css('--rule')}"/><text x="${m.l-6}" y="${yy+4}" font-size="11" text-anchor="end" fill="${css('--ink2')}">${lab.toPrecision(3)}</text>`}
 for(let k=0;k<=5;k++){const ev=x0+(x1-x0)*k/5;g+=`<text x="${X(ev)}" y="${H-12}" font-size="11" text-anchor="middle" fill="${css('--ink2')}">${Math.round(ev)}</text>`}
 g+=`<line x1="${X(run.best)}" x2="${X(run.best)}" y1="${m.t}" y2="${H-m.b}" stroke="${css('--muted')}" stroke-dasharray="4 3"/><text x="${X(run.best)+4}" y="${m.t+12}" font-size="11" fill="${css('--ink2')}">restored epoch ${run.best}</text>`;
 ser.forEach((s,i)=>{g+=`<polyline fill="none" stroke="${css(COLORS[i])}" stroke-width="2" points="${xs.map((e,j)=>X(e).toFixed(1)+','+Y(run[s][j]).toFixed(1)).join(' ')}"/>`});
 g+=`<line class="cross" y1="${m.t}" y2="${H-m.b}" stroke="${css('--ink2')}" visibility="hidden"/>`;svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.innerHTML=g;
 const tip=box.querySelector('.tip'),cross=svg.querySelector('.cross');
 svg.onmousemove=ev=>{const r=svg.getBoundingClientRect(),px=(ev.clientX-r.left)*W/r.width;let j=0,bd=1e18;xs.forEach((e,k)=>{const d=Math.abs(X(e)-px);if(d<bd){bd=d;j=k}});
  cross.setAttribute('x1',X(xs[j]));cross.setAttribute('x2',X(xs[j]));cross.setAttribute('visibility','visible');
  tip.innerHTML=`<b>epoch ${xs[j]}</b><br>`+ser.map((s,i)=>`<i style="display:inline-block;width:10px;height:3px;background:${css(COLORS[i])};margin-right:4px;vertical-align:middle"></i>${s}: ${run[s][j].toPrecision(4)}`).join('<br>');
  tip.style.display='block';tip.style.left=Math.min(r.width-230,(ev.clientX-r.left)+12)+'px';tip.style.top='10px'};
 svg.onmouseleave=()=>{tip.style.display='none';cross.setAttribute('visibility','hidden')};}
document.querySelectorAll('.explorer').forEach(box=>{const D=LOSS[box.dataset.exp],sel=box.querySelector('select.run');
 Object.keys(D.runs).forEach(k=>{const o=document.createElement('option');o.textContent=k;sel.appendChild(o)});
 box.querySelector('.legend').innerHTML=D.series.map((s,i)=>`<span><i style="background:var(${COLORS[i]})"></i>${s}</span>`).join('')+`<span>units: ${D.units}</span>`;
 sel.onchange=()=>draw(box);box.querySelector('input.logy').onchange=()=>draw(box);draw(box);});
window.addEventListener('resize',()=>document.querySelectorAll('.explorer').forEach(draw));
const links=[...document.querySelectorAll('nav a')];const obs=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){links.forEach(a=>a.classList.toggle('on',a.getAttribute('href')==='#'+e.target.id))}}),{rootMargin:'-20% 0px -70% 0px'});
document.querySelectorAll('section[id]').forEach(s=>obs.observe(s));
document.getElementById('theme').onclick=()=>{const r=document.documentElement,cur=r.dataset.theme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');r.dataset.theme=cur==='dark'?'light':'dark';document.querySelectorAll('.explorer').forEach(draw)};
"""


def explorer(eid, title):
    return (f'<div class="explorer" data-exp="{eid}"><div class="ctl"><b>{html.escape(title)}</b><label>Run <select class="run"></select></label>'
            f'<label><input type="checkbox" class="logy" checked> log scale</label></div><div class="legend"></div>'
            f'<div class="chart"><svg></svg><div class="tip"></div></div></div>')


def write_html(D, A, ck, pres, svgs):
    N = NARR
    archmap = {"E1": "A1_mendeley_mlp", "E2": "A1_mendeley_mlp", "E3": "A1_mendeley_mlp", "E4": "A2_duration_gnn", "E5": "A2_duration_gnn",
               "E6": "A2_duration_gnn", "E7": "A3_cambridge_classical", "E8": "A4_cambridge_sage"}
    figmap = {"E1": ["E1_loss_curve"], "E2": [], "E3": ["E3_loss_curves", "E3_fold_mae"], "E4": ["E4_oof_evidence"],
              "E5": ["E5_oof_evidence"], "E6": ["E6_oof_evidence"], "E7": ["E7_dev_folds"], "E8": ["E8_loss_curves", "E8_comparison", "E8_seed_spread"]}
    exp_ex = {"E1": ("E1", "Interactive learning curve - E1 (scaled MSE)"), "E3": ("E3", "Interactive learning curves - E3 (scaled MSE, pick a fold)"),
              "E8": ("E8", "Interactive learning curves - E8 (L1 on log1p days, pick a run)")}
    nav = ['<div class="grp">Overview</div>', '<a href="#rules">Rules applied</a>', '<a href="#chrono">Chronology</a>',
           '<a href="#inventory">Inventory</a>', '<a href="#losses">Loss provenance</a>', '<div class="grp">Experiments</div>']
    nav += [f'<a href="#{e["id"]}">{e["id"]} {html.escape(e["name"][:30])}</a>' for e in EXPERIMENTS]
    nav += ['<div class="grp">Integrity</div>', '<a href="#checkpoints">Checkpoints</a>', '<a href="#preservation">Preservation</a>',
            '<a href="#unavailable">Unavailable evidence</a>']
    chron = pd.read_csv(CSV_DIR / "chronology.csv")
    tl = "".join(f'<div class="tl"><span class="tag">{r.stage}</span><b>{r.id} {html.escape(EXP[r.id]["name"])}</b><small>{html.escape(r.file_mtime_note)}</small></div>'
                 for r in chron.itertuples())
    body = [f'<h1>Stage 4.0A - Expanded experiment evaluation</h1><p class="sub">Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}. Read-only audit of eight experiments. No training, inference, regenerated predictions, protected-file edits or locked-test access.</p>',
            '<section id="rules"><h2>Rules applied</h2>',
            '<div class="callout">Metrics stay inside their own evaluation partition and target transformation. There is <b>no cross-experiment ranking</b>: each section has its own tables and axes.</div>',
            '<div class="callout">The <code>train_mse_scaled</code> / <code>validation_mse_scaled</code> histories belong to the Mendeley tabular MLP (E1, E2, E3): MSE on a standardized total-project duration. Cambridge GraphSAGE histories (E8) are L1 on log1p(activity days). The two are never merged.</div>',
            '<div class="callout bad">Synthetic results (E4) come from labels generated by a known rule. They test the pipeline and are <b>not evidence of real-world predictive accuracy</b>.</div>',
            '<div class="callout bad">Stage 2.3E held-out numbers were computed on the same 99 locked blocks that Stage 3.7 protects. This audit shows only the stored aggregate, never re-derives it, and never compares it with development results.</div></section>',
            f'<section id="chrono"><h2>Chronological overview</h2><p>Order follows the documented stage labels: Mendeley tabular models, Cambridge classical models, the synthetic and DSLIB graph experiments, then Cambridge GraphSAGE. File timestamps conflict with this order for the Stage 3.5 checkpoints, so they are listed but not used.</p><div class="timeline">{tl}</div>',
            f'<figure><img class="fig" src="{b64(FIGS["chronology"])}" alt="chronology"><figcaption>{html.escape(CAPTIONS["chronology"])}</figcaption></figure>',
            html_table(chron) + "</section>",
            '<section id="inventory"><h2>Experiment inventory</h2>' + html_table(pd.read_csv(CSV_DIR / "experiment_inventory.csv")) + "</section>",
            '<section id="losses"><h2>Loss-history provenance</h2><p>Every loss file in the repository, hashed and attributed by content. E2 files are SHA-256 identical to E3 repeat 1. Experiments E4-E7 saved no per-epoch history.</p>'
            + html_table(pd.read_csv(CSV_DIR / "loss_history_registry.csv").assign(sha256=lambda d: d.sha256.str[:16] + "...")) + "</section>"]
    for e in EXPERIMENTS:
        eid = e["id"]; n = N[eid]
        s = [f'<section id="{eid}"><h2>{eid} - {html.escape(e["name"])}</h2><p><span class="tag">{html.escape(e["stage"])}</span><span class="tag">{html.escape(e["folder"])}</span></p>']
        if eid == "E4":
            s.append('<div class="callout bad">Synthetic data. Pipeline test only. Not evidence of real-world accuracy.</div>')
        if eid == "E2":
            s.append('<div class="callout">Duplicate evidence: every E2 artefact is byte-identical to E3 repeat 1. Do not count it twice.</div>')
        facts = [("Research objective", n["objective"]), ("Dataset and features", n["data"]), ("Target transformation", e["target"]),
                 ("Loss", e["loss"]), ("Evaluation partition", e["partition"]), ("Training and validation", n["method"]),
                 ("Maximum and executed epochs", n["epochs"]), ("Best checkpoint and stopping", n["stopping"])]
        s.append('<dl class="facts">' + "".join(f"<dt>{k}</dt><dd>{html.escape(v)}</dd>" for k, v in facts) + "</dl>")
        s.append(f'<h3>Model architecture</h3><div class="arch">{svgs[archmap[eid]].split("?>")[-1]}</div>')
        s.append("<h3>Hyperparameters</h3>" + html_table(pd.DataFrame(n["hyper"], columns=["parameter", "value"])))
        s.append("<h3>Actual learning curves and evidence plots</h3>")
        if eid in exp_ex:
            s.append(explorer(*exp_ex[eid]))
        if eid == "E2":
            s.append("<p>Identical to E3 repeat 1. Use the E3 explorer and select repeat 1.</p>")
        if eid in ("E4", "E5", "E6", "E7"):
            s.append('<div class="callout">No per-epoch loss history was saved for this experiment. Plots below come from saved out-of-fold predictions or fold metrics.</div>')
        for f in figmap[eid]:
            s.append(f'<figure><img class="fig" src="{b64(FIGS[f])}" alt="{f}"><figcaption>{html.escape(CAPTIONS[f])}</figcaption></figure>')
        s.append("<h3>Performance metrics</h3>" + html_table(n["metrics_md"]) + f"<p>{html.escape(n['metrics_note'])}</p>")
        if eid in ("E4", "E5", "E6"):
            s.append("<details><summary>Stored vs recomputed metrics (from oof_predictions.csv)</summary>" + html_table(A[f"{eid}_check"]) + "</details>")
            s.append("<details><summary>Per-fold OOF metrics</summary>" + html_table(A[f"{eid}_folds"]) + "</details>")
        if eid == "E7":
            s.append('<details><summary>Historical held-out aggregate (Stage 2.3E, 99 locked blocks) - not recomputed, not ranked</summary><div class="callout bad">Shown for completeness only. These blocks are the Stage 3.7 locked test and must not be used to confirm any later model.</div>'
                     + html_table(D["E7_heldout_hist"]) + "</details>")
            s.append("<details><summary>Development fold metrics</summary>" + html_table(D["E7_folds"]) + "</details>")
        if eid == "E8":
            s.append("<details><summary>Stored vs recomputed (development OOF)</summary>" + html_table(A["E8_check"]) + "</details>")
            s.append("<details><summary>Per-fold and per-seed metrics</summary>" + html_table(D["E8_folds"]) + html_table(D["E8_seeds"]) + "</details>")
            s.append("<details><summary>Convergence diagnostics per run</summary>" + html_table(A["E8_conv"]) + "</details>")
        if eid == "E3":
            s.append("<details><summary>Convergence diagnostics per fold</summary>" + html_table(A["E3_conv"]) + "</details>")
            s.append("<details><summary>All outer-fold metrics</summary>" + html_table(D["E3_cv"]) + "</details>")
        if eid == "E2":
            s.append("<details><summary>File-by-file SHA-256 comparison with E3 repeat 1</summary>" + html_table(A["E2_E3_identity"].assign(sha256_E2=lambda d: d.sha256_E2.str[:16], sha256_E3_repeat1=lambda d: d.sha256_E3_repeat1.str[:16])) + "</details>")
        s.append(f"<h3>Convergence, overfitting or underfitting</h3><p>{html.escape(n['conv'])}</p>")
        s.append("<h3>Research limitations</h3><ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in n["limits"]) + "</ul>")
        s.append(f"<h3>Reason for moving to the next experiment</h3><p>{html.escape(n['next'])}</p></section>")
        body += s
    passes = int(pres.status.str.startswith("PASS").sum()); fails = int((pres.status == "FAIL").sum())
    body += ['<section id="checkpoints"><h2>Checkpoint metadata and hashes</h2><p>Identity is decided by SHA-256, never by size. The three Stage 3.5 <code>model.pt</code> files are all 232,503 bytes but have different hashes and different <code>source</code> metadata. PyTorch files were loaded with <code>weights_only=True</code>; joblib files were hashed but not unpickled.</p>'
             + html_table(ck.assign(sha256=lambda d: d.sha256.str[:16] + "...")) + "</section>",
             f'<section id="preservation"><h2>Preservation verification</h2><p><span class="{"pass" if fails == 0 else "fail"}">{passes} checks passed, {fails} failed.</span> Locked-test-derived files were byte-hashed only, never parsed.</p>'
             + html_table(pres.groupby("check").status.agg(total="count", passed=lambda s: int(s.str.startswith("PASS").sum())).reset_index())
             + "<details><summary>All checks</summary>" + html_table(pres.assign(expected_sha256=lambda d: d.expected_sha256.str[:16], current_sha256=lambda d: d.current_sha256.str[:16])) + "</details></section>",
             '<section id="unavailable"><h2>Unavailable evidence</h2>' + html_table(UNAVAILABLE) + "</section>"]
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Stage 4.0A Evaluation</title><style>{CSS}</style></head><body><button id="theme" class="theme">Toggle theme</button>'
            f'<div class="layout"><nav>{"".join(nav)}</nav><main>{"".join(body)}</main></div>'
            f'<script>{JS.replace("__LOSS__", json.dumps(loss_payload(D)))}</script></body></html>')
    (HERE / "stage4_0a_evaluation_report.html").write_text(page, encoding="utf-8")


# ================================================================= main
def main():
    D = load_all()
    A = analyse(D)
    global NARR
    NARR = narratives(D, A)
    fig_chronology(); fig_E1(D, A); fig_E3(D, A)
    for eid in ("E4", "E5", "E6"):
        fig_gnn(eid, D, A)
    fig_E7(D, A); fig_E8(D, A)
    svgs = architecture_svgs()
    ck = checkpoint_inventory()
    pres = preservation_check(D)
    write_csvs(D, A, ck, pres)
    write_md(D, A, ck, pres, svgs)
    write_html(D, A, ck, pres, svgs)
    print(f"preservation: {int(pres.status.str.startswith('PASS').sum())} PASS, {int((pres.status == 'FAIL').sum())} FAIL")
    print(f"E8 recomputation match: {bool(A['E8_check'].match.all())}; E2==E3r1 metrics: {A['E2_metrics_equal_E3r1']}")
    for eid in ("E4", "E5", "E6"):
        print(f"{eid} stored metrics reproduced: {bool(A[f'{eid}_check'].matches_to_stored_precision.all())}")
    print(f"-> {HERE / 'stage4_0a_evaluation_report.html'}")


if __name__ == "__main__":
    main()
