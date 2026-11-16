"""
Train + evaluate the PMI duration GNN with project-grouped cross-validation.

    python research/gnn/train.py --source synthetic            # pipeline smoke test (NOT a result)
    python research/gnn/train.py --source dslib                # real Ghent/DSLIB building projects

Protocol
    * K folds over PROJECTS (never activities): a project's activities are never split between train/test.
    * Inside each training fold, 15 % of projects are held out for early stopping only.
    * Feature scaling fitted on training-fold nodes only.
    * Target y = log(actual / planned); predictions are converted back to days for reporting.
    * Every fold compares, on the same test activities:
        plan        actual = planned (no correction)
        median      one global correction ratio learned from training projects
        category    median correction per trade category
        mlp         neural network, same features, NO graph
        gnn         DurationGNN (graph)
Outputs -> models/gnn_<source>/ : metrics.json, oof_predictions.csv, report.md, model.pt (refit on all).
"""
from __future__ import annotations

import argparse
import copy
import json
import platform
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from graph_schema import CATEGORY_LIST, FEATURES  # noqa: E402
from model import make  # noqa: E402


def seed_all(s: int):
    random.seed(s); np.random.seed(s); torch.manual_seed(s)


def labelled(g):
    return torch.isfinite(g.y)


def fit_scaler(graphs):
    x = torch.cat([g.x for g in graphs])
    mu, sd = x.mean(0), x.std(0)
    sd[sd < 1e-6] = 1.0
    return mu, sd


def scaled(graphs, mu, sd):
    out = []
    for g in graphs:
        h = copy.copy(g)
        h.x = (g.x - mu) / sd
        out.append(h)
    return out


def train_net(kind, tr, va, epochs, lr, hidden, layers, patience, seed):
    seed_all(seed)
    kw = {"hidden": hidden} | ({"layers": layers} if kind == "gnn" else {})
    m = make(kind, len(FEATURES), **kw)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=1e-4)
    loss_fn = torch.nn.HuberLoss(delta=0.5)

    def val_loss():
        m.eval()
        with torch.no_grad():
            ls = [loss_fn(m(g)[labelled(g)], g.y[labelled(g)]).item() for g in va if labelled(g).any()]
        return float(np.mean(ls)) if ls else 0.0

    best, best_state, best_ep, wait = float("inf"), None, 0, 0
    for ep in range(epochs):
        m.train()
        for i in np.random.permutation(len(tr)):
            g = tr[i]
            mask = labelled(g)
            if not mask.any():
                continue
            opt.zero_grad()
            loss = loss_fn(m(g)[mask], g.y[mask])
            loss.backward()
            opt.step()
        v = val_loss()
        if v < best - 1e-5:
            best, best_state, best_ep, wait = v, copy.deepcopy(m.state_dict()), ep + 1, 0
        else:
            wait += 1
            if wait >= patience:
                break
    m.load_state_dict(best_state)
    return m, best_ep


def predict(m, graphs):
    m.eval()
    with torch.no_grad():
        return [m(g) for g in graphs]


def metrics(df: pd.DataFrame, col: str) -> dict:
    err = df[col] - df["actual_days"]
    ape = (err.abs() / df["actual_days"]).replace(np.inf, np.nan)
    lr = np.log(df[col] / df["actual_days"])
    proj = df.assign(e=err.abs()).groupby("project_id")["e"].mean()
    return {"MAE_days": round(float(err.abs().mean()), 3), "MedAE_days": round(float(err.abs().median()), 3),
            "MdAPE_pct": round(float(ape.median() * 100), 2), "MAE_log_ratio": round(float(lr.abs().mean()), 4),
            "mean_project_MAE_days": round(float(proj.mean()), 3)}


def run(graphs, args, out: Path):
    graphs = [g for g in graphs if labelled(g).any()]
    # folds are built over GROUPS of related projects (e.g. phases of one building) to avoid leakage
    groups = np.array([getattr(g, "group", g.project_id) for g in graphs])
    rng = np.random.default_rng(args.seed)
    ug = rng.permutation(np.unique(groups))
    k = min(args.folds, len(ug))
    # balance folds by labelled-activity count: assign largest groups first to the lightest fold
    size = {u: sum(int(labelled(g).sum()) for g, gg in zip(graphs, groups) if gg == u) for u in ug}
    fold_groups, load = [[] for _ in range(k)], [0] * k
    for u in sorted(ug, key=lambda u: -size[u]):
        j = int(np.argmin(load)); fold_groups[j].append(u); load[j] += size[u]
    folds = [np.where(np.isin(groups, fg))[0] for fg in fold_groups]
    rows, best_epochs = [], {"gnn": [], "mlp": []}

    for f, test_idx in enumerate(folds):
        rest_groups = rng.permutation([u for u in ug if u not in set(fold_groups[f])])
        n_val = max(1, int(round(0.15 * len(rest_groups))))
        val_idx = np.where(np.isin(groups, rest_groups[:n_val]))[0]
        tr_idx = np.where(np.isin(groups, rest_groups[n_val:]))[0]
        tr, va, te = ([graphs[i] for i in ix] for ix in (tr_idx, val_idx, test_idx))
        mu, sd = fit_scaler(tr)
        trs, vas, tes = scaled(tr, mu, sd), scaled(va, mu, sd), scaled(te, mu, sd)

        y_tr = torch.cat([g.y[labelled(g)] for g in tr]).numpy()
        cat_tr = sum(([c for c, ok in zip(g.categories, labelled(g)) if ok] for g in tr), [])
        global_med = float(np.median(y_tr))
        cat_med = pd.Series(y_tr).groupby(pd.Series(cat_tr)).median().to_dict()

        preds = {}
        for kind in ("mlp", "gnn"):
            m, ep = train_net(kind, trs, vas, args.epochs, args.lr, args.hidden, args.layers, args.patience,
                              args.seed + f)
            best_epochs[kind].append(ep)
            preds[kind] = predict(m, tes)

        for gi, g in enumerate(te):
            mask = labelled(g).numpy()
            planned = g.planned.numpy()
            base = pd.DataFrame({
                "fold": f, "project_id": g.project_id, "activity_id": g.activity_ids, "name": g.names,
                "category": g.categories, "planned_days": planned, "actual_days": np.exp(g.y.numpy()) * planned,
                "pred_plan": planned, "pred_median": planned * np.exp(global_med),
                "pred_category": planned * np.exp([cat_med.get(c, global_med) for c in g.categories]),
                "pred_mlp": planned * np.exp(preds["mlp"][gi].numpy()),
                "pred_gnn": planned * np.exp(preds["gnn"][gi].numpy()),
            })[mask]
            rows.append(base)
        print(f"fold {f + 1}/{k}: train {len(tr)} / val {len(va)} / test {len(te)} projects, "
              f"best epochs mlp {best_epochs['mlp'][-1]} gnn {best_epochs['gnn'][-1]}")

    oof = pd.concat(rows, ignore_index=True)
    out.mkdir(parents=True, exist_ok=True)
    oof.to_csv(out / "oof_predictions.csv", index=False)
    res = {m: metrics(oof, f"pred_{m}") for m in ("plan", "median", "category", "mlp", "gnn")}

    # paired bootstrap over projects: is GNN better than the best non-graph method?
    ref = min(("plan", "median", "category", "mlp"), key=lambda m: res[m]["MAE_days"])
    per = oof.assign(dg=(oof.pred_gnn - oof.actual_days).abs(), dr=(oof[f"pred_{ref}"] - oof.actual_days).abs()) \
        .groupby("project_id")[["dg", "dr"]].mean()
    diffs = [per.sample(len(per), replace=True, random_state=b).pipe(lambda p: (p.dg - p.dr).mean())
             for b in range(2000)]
    ci = np.percentile(diffs, [2.5, 97.5])

    # final model: refit on all projects with a fixed epoch count (median of CV best epochs)
    mu, sd = fit_scaler(graphs)
    ep = int(np.median(best_epochs["gnn"]))
    final, _ = train_net("gnn", scaled(graphs, mu, sd), scaled(graphs[:1], mu, sd), ep, args.lr, args.hidden,
                         args.layers, patience=10 ** 9, seed=args.seed)
    torch.save({"state_dict": final.state_dict(), "features": FEATURES, "categories": CATEGORY_LIST,
                "mu": mu, "sd": sd, "hidden": args.hidden, "layers": args.layers, "source": args.source},
               out / "model.pt")

    summary = {"source": args.source, "projects": len(graphs), "independent_groups": int(len(ug)),
               "labelled_activities": int(len(oof)),
               "folds": k, "metrics": res, "gnn_vs_best_baseline": {
                   "baseline": ref, "mean_diff_MAE_days_per_project": round(float(per.dg.mean() - per.dr.mean()), 3),
                   "bootstrap_95ci": [round(float(c), 3) for c in ci],
                   "gnn_better": bool(ci[1] < 0)},
               "args": vars(args) | {"source": args.source},
               "versions": {"python": platform.python_version(), "torch": torch.__version__}}
    (out / "metrics.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    write_report(summary, out)
    return summary


def write_report(s, out):
    lines = [f"# Duration GNN - {s['source']}", "",
             f"{s['projects']} projects in {s['independent_groups']} independent groups, {s['labelled_activities']} labelled activities, {s['folds']}-fold "
             "project-grouped cross-validation (out-of-fold predictions).", "",
             "| method | MAE days | MedAE days | MdAPE % | MAE log-ratio | mean project MAE |", "|---|---|---|---|---|---|"]
    for m, r in s["metrics"].items():
        lines.append(f"| {m} | {r['MAE_days']} | {r['MedAE_days']} | {r['MdAPE_pct']} | {r['MAE_log_ratio']} | "
                     f"{r['mean_project_MAE_days']} |")
    c = s["gnn_vs_best_baseline"]
    lines += ["", f"GNN vs best non-graph method (`{c['baseline']}`): {c['mean_diff_MAE_days_per_project']:+} days "
                  f"MAE per project, 95 % bootstrap CI {c['bootstrap_95ci']} -> "
                  f"{'GNN significantly better' if c['gnn_better'] else 'no significant improvement'}."]
    if s["source"] == "synthetic":
        lines += ["", "**SYNTHETIC DATA - pipeline test only.** Labels were generated by known rules; this shows the "
                      "code can learn a graph-dependent effect, not real-world accuracy."]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["synthetic", "dslib", "dslib_filtered"], default="synthetic")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--patience", type=int, default=30)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--layers", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    import datasets
    graphs = datasets.load(a.source)
    out = a.out or ROOT / "models" / f"gnn_{a.source}"
    s = run(graphs, a, out)
    print(json.dumps(s["metrics"], indent=2))
    print(json.dumps(s["gnn_vs_best_baseline"], indent=2))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
