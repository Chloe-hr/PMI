"""
Stage 3.7 - Cambridge GraphSAGE vs matched no-graph model, development folds only.

    python research/gnn/cambridge_graph.py            # once: graph cache + feasibility diagnostics
    python research/gnn/train_cambridge.py            # full frozen run -> models/gnn_cambridge/
    python research/gnn/train_cambridge.py --smoke    # 2 epochs, 1 seed, fold 4 only, scratch output, no metrics

The frozen configuration is research/gnn/cambridge_protocol.json; its sha256 is recorded with the results.
The 99 locked Stage 2.3E test blocks are never loaded (cambridge_graph.load_cached refuses them).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "training"))
from cambridge_graph import TARGET, FoldFeaturizer, build_graphs, load_cached, sha256  # noqa: E402
from cambridge_model import CambridgeSAGE  # noqa: E402

PROTOCOL = HERE / "cambridge_protocol.json"
STAGE23E = ROOT / "data/processed/stage2/cambridge_experiment"
OUT = ROOT / "models/gnn_cambridge"
FIGS = HERE / "figures/cambridge"
MODELS = ("median", "ridge", "no_graph", "graphsage")
NEURAL = ("no_graph", "graphsage")


def seed_all(s: int):
    import random
    random.seed(s); np.random.seed(s); torch.manual_seed(s)


def inner_stop_blocks(blocks, seed: int = 23051) -> set:
    order = sorted(set(blocks), key=lambda g: hashlib.sha256((str(seed) + str(g)).encode()).hexdigest())
    return set(order[:max(1, len(order) // 10)])


def strip(g):
    from torch_geometric.data import Data
    return Data(x=g.x, edge_index=g.edge_index, y=g.y)


def l1_labelled(model, graphs):
    """Mean L1 on log1p over all labelled nodes of `graphs` (pooled)."""
    tot, n = 0.0, 0
    model.eval()
    with torch.no_grad():
        for g in graphs:
            m = torch.isfinite(g.y)
            if m.any():
                tot += float((model(g.x, g.edge_index)[m] - g.y[m]).abs().sum()); n += int(m.sum())
    return tot / max(n, 1)


def train_one(kind, cfg, fit, stop, val, seed, max_epochs):
    from torch_geometric.loader import DataLoader
    seed_all(seed)
    mc = cfg["models"]["graphsage"]
    model = CambridgeSAGE(fit[0].x.shape[1], hidden=mc["hidden"], layers=mc["graph_layers"], dropout=mc["dropout"],
                          use_graph=(kind == "graphsage"))
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["optimizer"]["lr"], weight_decay=cfg["optimizer"]["weight_decay"])
    gen = torch.Generator().manual_seed(seed)
    loader = DataLoader([strip(g) for g in fit], batch_size=cfg["batch_size_graphs"], shuffle=True, generator=gen)
    es = cfg["early_stopping"]
    best, best_state, best_ep, wait, curve = float("inf"), None, 0, 0, []
    for ep in range(1, max_epochs + 1):
        model.train()
        tot, n = 0.0, 0
        for b in loader:
            m = torch.isfinite(b.y)
            if not m.any():
                continue
            opt.zero_grad()
            loss = (model(b.x, b.edge_index)[m] - b.y[m]).abs().mean()
            loss.backward(); opt.step()
            tot += loss.item() * int(m.sum()); n += int(m.sum())
        s = l1_labelled(model, stop)
        v = l1_labelled(model, val)          # monitoring only - never used for any decision
        curve.append(dict(epoch=ep, train_l1_log=tot / max(n, 1), inner_stop_l1_log=s, outer_val_l1_log_monitor_only=v))
        if s < best - es["min_delta"]:
            best, best_state, best_ep, wait = s, copy.deepcopy(model.state_dict()), ep, 0
        else:
            wait += 1
            if wait >= es["patience"]:
                break
    model.load_state_dict(best_state)
    return model, best_ep, curve


def predict(model, graphs):
    model.eval()
    with torch.no_grad():
        return [model(g.x, g.edge_index).numpy() for g in graphs]


# ------------------------------------------------------------------------------------------------- metrics
def summarise(df: pd.DataFrame, col: str) -> dict:
    from sklearn.metrics import r2_score
    e = df[col] - df.actual_days
    blk = df.assign(ae=e.abs()).groupby("conservative_block_id").ae.mean()
    fold_macro = df.assign(ae=e.abs()).groupby(["fold", "conservative_block_id"]).ae.mean().groupby("fold").mean()
    return dict(n=len(df), blocks=int(blk.size), mean_block_mae_days=float(blk.mean()),
                activity_mae_days=float(e.abs().mean()), rmse_days=float(np.sqrt((e ** 2).mean())),
                r2=float(r2_score(df.actual_days, df[col])), median_absolute_error_days=float(e.abs().median()),
                mean_of_fold_macro_block_mae_days=float(fold_macro.mean()))


def block_bootstrap(df, cols, resamples, seed):
    per = pd.DataFrame({c: (df[c] - df.actual_days).abs() for c in cols}).assign(b=df.conservative_block_id) \
        .groupby("b").mean()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(per), size=(resamples, len(per)))
    vals = per.to_numpy()
    boots = vals[idx].mean(axis=1)                      # resamples x models
    out = {"models": {}, "paired_differences": {}}
    for j, c in enumerate(cols):
        out["models"][c] = dict(point=float(vals[:, j].mean()), ci95=[float(x) for x in np.percentile(boots[:, j], [2.5, 97.5])])
    g = cols.index("pred_graphsage")
    for j, c in enumerate(cols):
        if j == g:
            continue
        d = boots[:, g] - boots[:, j]
        out["paired_differences"][f"graphsage_minus_{c[5:]}"] = dict(
            point=float(vals[:, g].mean() - vals[:, j].mean()), ci95=[float(x) for x in np.percentile(d, [2.5, 97.5])],
            share_of_blocks_graphsage_better=float((vals[:, g] < vals[:, j]).mean()))
    return out


# ------------------------------------------------------------------------------------------------- provenance
def environment() -> dict:
    pk = ["torch", "torch_geometric", "scikit-learn", "numpy", "pandas", "scipy", "matplotlib", "ijson", "networkx"]
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    except OSError:
        commit, dirty = "unknown", True
    return dict(python=platform.python_version(), platform=platform.platform(), processor=platform.processor(),
                torch_threads=torch.get_num_threads(), git_commit=commit, git_working_tree_dirty=dirty,
                packages={p: metadata.version(p) for p in pk})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    cfg = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    out = a.out or OUT
    if not a.smoke and (out / "oof_predictions.csv").exists():
        raise SystemExit(f"{out} already holds results of the frozen run; choose a new --out for a new experiment")
    out.mkdir(parents=True, exist_ok=True)
    (out / "checkpoints").mkdir(exist_ok=True)
    torch.set_num_threads(cfg["torch_threads"])
    seeds = cfg["seeds"][:1] if a.smoke else cfg["seeds"]
    max_epochs = 2 if a.smoke else cfg["max_epochs"]
    log = open(out / "run_log.txt", "a", encoding="utf-8")
    say = lambda s: (print(s, flush=True), log.write(s + "\n"), log.flush())  # noqa: E731
    t0 = time.time()
    say(f"Stage 3.7 run start {time.strftime('%Y-%m-%dT%H:%M:%S%z')} protocol sha256 {sha256(PROTOCOL)} smoke={a.smoke}")

    nodes, edges, dev = load_cached()
    from train_cambridge_experiment import preprocessor, FEATURES as F23
    from sklearn.linear_model import Ridge
    alphas = json.loads((STAGE23E / "training_config.json").read_text(encoding="utf-8"))["ridge_alpha_by_fold"]
    dev = dev.reset_index(drop=True)
    dev["fold"] = dev.development_validation_fold.astype(int)
    folds = [3] if a.smoke else range(5)
    rows, curves, fold_meta = [], [], []
    for f in folds:
        val_blocks = set(dev[dev.fold == f].conservative_block_id)
        tr_blocks = set(dev[dev.fold != f].conservative_block_id)
        stop_blocks = inner_stop_blocks(tr_blocks)
        fit_blocks = tr_blocks - stop_blocks
        proj = lambda bl: set(nodes[nodes.conservative_block_id.isin(bl)].project_key)  # noqa: E731
        fit_p, stop_p, val_p = proj(fit_blocks), proj(stop_blocks), proj(val_blocks)
        assert not (fit_p & stop_p) and not (fit_p & val_p) and not (stop_p & val_p)
        feat = FoldFeaturizer(seed=cfg["seeds"][0] + f).fit(nodes[nodes.project_key.isin(fit_p)])
        graphs = build_graphs(nodes, edges, dev, feat, projects=fit_p | stop_p | val_p)
        G = {k: [g for g in graphs if g.project_key in ps] for k, ps in (("fit", fit_p), ("stop", stop_p), ("val", val_p))}
        import joblib
        joblib.dump(feat, out / "checkpoints" / f"featurizer_fold{f}.joblib", compress=3)

        # baselines on all labelled outer-training rows (Stage 2.3E definitions)
        tr_rows, va_rows = dev[dev.fold != f], dev[dev.fold == f]
        ytr = tr_rows[TARGET].to_numpy()
        base = {"median": np.full(len(va_rows), np.median(ytr))}
        if not a.smoke:
            prep = preprocessor()
            ridge = Ridge(alpha=alphas[f], solver="lsqr", max_iter=2000).fit(prep.fit_transform(tr_rows[list(F23)]), ytr)
            base["ridge"] = ridge.predict(prep.transform(va_rows[list(F23)]))
        else:
            base["ridge"] = base["median"]
        va = va_rows[["project_key", "activity_key", "conservative_block_id", "fold", TARGET, "project_type"]].rename(
            columns={TARGET: "actual_days"}).copy()
        for k, v in base.items():
            va[f"pred_{k}"] = v

        # neural arms
        logp = {}
        for kind in NEURAL:
            for s in seeds:
                m, best_ep, curve = train_one(kind, cfg, G["fit"], G["stop"], G["val"], s + f * 1000, max_epochs)
                torch.save({"state_dict": m.state_dict(), "kind": kind, "fold": f, "seed": s, "best_epoch": best_ep,
                            "n_in": G["fit"][0].x.shape[1], "protocol_sha256": sha256(PROTOCOL)},
                           out / "checkpoints" / f"{kind}_fold{f}_seed{s}.pt")
                curves += [c | dict(model=kind, fold=f, seed=s) for c in curve]
                fold_meta.append(dict(model=kind, fold=f, seed=s, best_epoch=best_ep, epochs_run=len(curve),
                                      best_inner_stop_l1_log=min(c["inner_stop_l1_log"] for c in curve)))
                preds = predict(m, G["val"])
                keyed = {}
                for g, p in zip(G["val"], preds):
                    lab = torch.isfinite(g.y).numpy()
                    keyed.update({(g.project_key, k): float(v) for k, v, l in zip(g.activity_keys, p, lab) if l})
                logp[(kind, s)] = np.array([keyed[(r.project_key, r.activity_key)] for r in va.itertuples()])
                say(f"fold {f} {kind:9s} seed {s}: best epoch {best_ep}/{len(curve)}  "
                    f"({time.time() - t0:.0f}s)")
        for kind in NEURAL:
            for s in seeds:
                va[f"pred_{kind}_seed{s}"] = np.clip(np.expm1(logp[(kind, s)]), 0, None)
            va[f"pred_{kind}"] = np.clip(np.expm1(np.mean([logp[(kind, s)] for s in seeds], axis=0)), 0, None)
        rows.append(va)
        say(f"fold {f}: fit {len(fit_p)} / stop {len(stop_p)} / val {len(val_p)} projects; "
            f"stop blocks {sorted(stop_blocks)}")

    oof = pd.concat(rows, ignore_index=True)
    pd.DataFrame(curves).to_csv(out / "loss_curves.csv", index=False)
    pd.DataFrame(fold_meta).to_csv(out / "training_runs.csv", index=False)
    if a.smoke:
        assert oof.notna().all().all() and len(oof) == (dev.fold == 3).sum()
        say(f"SMOKE OK: {len(oof)} validation rows predicted; no metrics computed")
        return
    oof.to_csv(out / "oof_predictions.csv", index=False)

    # connectivity per labelled node (for stratified reporting)
    indeg = edges.groupby(["project_key", "successor_key"]).size()
    outdeg = edges.groupby(["project_key", "predecessor_key"]).size()
    k = list(zip(oof.project_key, oof.activity_key))
    oof["degree"] = [int(indeg.get(x, 0)) + int(outdeg.get(x, 0)) for x in k]

    cols = [f"pred_{m}" for m in MODELS]
    comparison = pd.DataFrame([dict(model=m, **summarise(oof, f"pred_{m}")) for m in MODELS])
    comparison.to_csv(out / "model_comparison.csv", index=False)
    seed_rows = [dict(model=m, seed=s, **summarise(oof, f"pred_{m}_seed{s}")) for m in NEURAL for s in seeds]
    pd.DataFrame(seed_rows).to_csv(out / "seed_metrics.csv", index=False)
    fold_rows = [dict(fold=f, model=m, **summarise(oof[oof.fold == f], f"pred_{m}")) for f in range(5) for m in MODELS]
    pd.DataFrame(fold_rows).to_csv(out / "fold_metrics.csv", index=False)
    blk = []
    for b, d in oof.groupby("conservative_block_id"):
        r = dict(conservative_block_id=b, fold=int(d.fold.iloc[0]), n=len(d), projects=d.project_key.nunique(),
                 project_type=d.project_type.mode().iloc[0], median_actual_days=float(d.actual_days.median()))
        for m in MODELS:
            e = d[f"pred_{m}"] - d.actual_days
            r[f"mae_{m}"] = float(e.abs().mean()); r[f"rmse_{m}"] = float(np.sqrt((e ** 2).mean()))
        blk.append(r)
    pd.DataFrame(blk).to_csv(out / "block_metrics.csv", index=False)
    boot = block_bootstrap(oof, cols, cfg["uncertainty"]["resamples"], cfg["uncertainty"]["seed"])
    strata = []
    oof["connectivity"] = pd.cut(oof.degree, [-1, 0, 2, 5, 10**9], labels=["isolated (0)", "1-2", "3-5", "6+"])
    for c, d in oof.groupby("connectivity", observed=True):
        strata.append(dict(connectivity=str(c), n=len(d), **{f"mae_{m}": float((d[f"pred_{m}"] - d.actual_days).abs().mean()) for m in MODELS}))
    diff = oof.pred_graphsage - oof.pred_no_graph
    differences = dict(
        mean_days=float(diff.mean()), median_days=float(diff.median()), mean_abs_days=float(diff.abs().mean()),
        p05_p95_days=[float(x) for x in diff.quantile([.05, .95])],
        spearman_predictions=float(oof[["pred_graphsage", "pred_no_graph"]].corr("spearman").iloc[0, 1]),
        share_activities_graphsage_closer=float(((oof.pred_graphsage - oof.actual_days).abs() <
                                                 (oof.pred_no_graph - oof.actual_days).abs()).mean()),
        by_connectivity=strata)

    # Stage 2.3E reproduction check on the shared baselines
    ref = pd.read_csv(STAGE23E / "fold_metrics.csv")
    repro = []
    for m in ("median", "ridge"):
        for f in range(5):
            mine = summarise(oof[oof.fold == f], f"pred_{m}")["activity_mae_days"]
            theirs = float(ref[(ref.fold == f) & (ref.model == m)].mae_days.iloc[0])
            repro.append(dict(model=m, fold=f, stage37_mae=mine, stage23e_mae=theirs, abs_diff=abs(mine - theirs)))
    summary = dict(protocol_sha256=sha256(PROTOCOL), comparison=comparison.to_dict("records"), bootstrap=boot,
                   gnn_vs_no_graph=differences, stage23e_baseline_reproduction=repro,
                   success_criterion_met=bool(
                       boot["paired_differences"]["graphsage_minus_no_graph"]["ci95"][1] < 0
                       and boot["paired_differences"]["graphsage_minus_median"]["point"] < 0
                       and boot["paired_differences"]["graphsage_minus_ridge"]["point"] < 0),
                   runtime_seconds=round(time.time() - t0))
    (out / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / "training_config.json").write_text(json.dumps(cfg | {"protocol_sha256": sha256(PROTOCOL)}, indent=2) + "\n", encoding="utf-8")
    manifest = json.loads((ROOT / "data/processed/gnn_cambridge/graph_manifest.json").read_text(encoding="utf-8"))
    prov = dict(graph_manifest=manifest, stage23e_training_config_sha256=sha256(STAGE23E / "training_config.json"),
                locked_test_blocks_evaluated=0, development_rows=len(oof), development_blocks=int(oof.conservative_block_id.nunique()))
    (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    (out / "environment.json").write_text(json.dumps(environment(), indent=2) + "\n", encoding="utf-8")
    say(comparison.to_string(index=False))
    say(json.dumps(boot["paired_differences"], indent=1))
    say(f"success criterion met: {summary['success_criterion_met']}  runtime {summary['runtime_seconds']}s")
    import cambridge_figures
    cambridge_figures.make_all(out, FIGS)


if __name__ == "__main__":
    main()
