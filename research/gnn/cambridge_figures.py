"""Figures for the Stage 3.7 Cambridge GNN report, regenerated from saved outputs only:

    python research/gnn/cambridge_figures.py       # reads models/gnn_cambridge -> research/gnn/figures/cambridge
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# reference categorical palette, fixed order: entity -> colour never changes between charts
COLOR = {"graphsage": "#2a78d6", "no_graph": "#eb6834", "ridge": "#1baf7a", "median": "#eda100"}
LABEL = {"graphsage": "GraphSAGE", "no_graph": "No-graph (matched)", "ridge": "Ridge", "median": "Median"}
ORDER = ["median", "ridge", "no_graph", "graphsage"]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def style():
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
                         "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
                         "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
                         "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
                         "savefig.dpi": 150, "savefig.bbox": "tight"})


def loss_curves(out, figs):
    c = pd.read_csv(out / "loss_curves.csv")
    s0 = c.seed.min()
    fig, axes = plt.subplots(2, 5, figsize=(17, 6.2), sharey="row")
    for i, kind in enumerate(["graphsage", "no_graph"]):
        for f in range(5):
            ax = axes[i, f]
            d = c[(c.model == kind) & (c.fold == f) & (c.seed == s0)]
            ax.plot(d.epoch, d.train_l1_log, color=COLOR[kind], lw=2, label="training (fitting blocks)")
            ax.plot(d.epoch, d.inner_stop_l1_log, color=INK, lw=1.5, ls="--", label="inner stopping blocks")
            ax.plot(d.epoch, d.outer_val_l1_log_monitor_only, color=INK2, lw=1.5, ls=":", label="validation fold (monitor only)")
            best = d.loc[d.inner_stop_l1_log.idxmin(), "epoch"]
            ax.axvline(best, color=GRID, lw=1.5)
            ax.set_title(f"{LABEL[kind]} · fold {f}", fontsize=10)
            if f == 0:
                ax.set_ylabel("L1 loss on log1p(days)")
            if i == 1:
                ax.set_xlabel("epoch")
    axes[0, 0].legend(loc="upper right", fontsize=8)
    fig.suptitle(f"Training vs validation loss (seed {s0}); vertical line = restored epoch", fontweight="bold")
    fig.tight_layout(); fig.savefig(figs / "loss_curves.png"); plt.close(fig)


def block_mae_ci(m, figs):
    b = m["bootstrap"]["models"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    for i, k in enumerate(ORDER):
        r = b[f"pred_{k}"]
        ax.barh(i, r["point"], color=COLOR[k], height=0.55)
        ax.errorbar(r["point"], i, xerr=[[r["point"] - r["ci95"][0]], [r["ci95"][1] - r["point"]]],
                    color=INK, capsize=4, lw=1.2)
        ax.text(r["ci95"][1] + 0.6, i, f"{r['point']:.1f}  [{r['ci95'][0]:.1f}, {r['ci95'][1]:.1f}]",
                va="center", fontsize=9, color=INK)
    ax.set_yticks(range(len(ORDER)), [LABEL[k] for k in ORDER])
    ax.set_xlabel("Mean block MAE, reported elapsed calendar days (95% block-bootstrap CI)")
    ax.set_xlim(0, max(b[f"pred_{k}"]["ci95"][1] for k in ORDER) * 1.35)
    ax.grid(axis="y", visible=False)
    ax.set_title("Development folds: mean block MAE (70 blocks)")
    fig.tight_layout(); fig.savefig(figs / "mean_block_mae_ci.png"); plt.close(fig)


def block_scatter(out, figs):
    b = pd.read_csv(out / "block_metrics.csv")
    fig, ax = plt.subplots(figsize=(6, 5.6))
    ax.scatter(b.mae_no_graph, b.mae_graphsage, s=np.clip(np.sqrt(b.n) * 3, 12, 300), color=COLOR["graphsage"],
               alpha=0.75, edgecolor=SURFACE, linewidth=1.5)
    lim = [min(b.mae_no_graph.min(), b.mae_graphsage.min()) * 0.8, max(b.mae_no_graph.max(), b.mae_graphsage.max()) * 1.2]
    ax.plot(lim, lim, color=INK2, lw=1, ls="--")
    ax.set(xscale="log", yscale="log", xlim=lim, ylim=lim, xlabel="No-graph block MAE (days)",
           ylabel="GraphSAGE block MAE (days)")
    better = (b.mae_graphsage < b.mae_no_graph).sum()
    ax.set_title(f"Per-block MAE: below the line = GraphSAGE better ({better}/{len(b)} blocks)")
    dom = b.loc[b.n.idxmax()]
    ax.annotate(f"dominant block ({int(dom.n):,} rows)", (dom.mae_no_graph, dom.mae_graphsage), xytext=(10, -18),
                textcoords="offset points", fontsize=8, color=INK2, arrowprops=dict(arrowstyle="-", color=INK2))
    fig.tight_layout(); fig.savefig(figs / "block_mae_graphsage_vs_no_graph.png"); plt.close(fig)


def actual_vs_pred(oof, figs):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    for ax, k in zip(axes, ["no_graph", "graphsage"]):
        hb = ax.hexbin(np.log10(oof.actual_days), np.log10(oof[f"pred_{k}"].clip(lower=0.01)), gridsize=60,
                       cmap="Blues", mincnt=1, bins="log")
        lo, hi = -2, 3.5
        ax.plot([lo, hi], [lo, hi], color=INK2, lw=1, ls="--")
        ax.set(xlim=(lo, hi), ylim=(lo, hi), xlabel="log10 actual reported elapsed days", title=LABEL[k])
    axes[0].set_ylabel("log10 predicted days")
    fig.colorbar(hb, ax=axes, label="activities (log count)")
    fig.suptitle("Out-of-fold predictions vs reported elapsed calendar days (all 5 development folds)", fontweight="bold")
    fig.savefig(figs / "actual_vs_predicted.png"); plt.close(fig)


def pred_difference(oof, m, figs):
    d = oof.pred_graphsage - oof.pred_no_graph
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    q = d.quantile([0.005, 0.995])
    axes[0].hist(d.clip(*q), bins=80, color=COLOR["graphsage"], edgecolor=SURFACE, linewidth=0.5)
    axes[0].axvline(0, color=INK2, lw=1)
    axes[0].set(xlabel="GraphSAGE − no-graph prediction (days; clipped to 0.5–99.5th pct)", ylabel="activities",
                title="How far the graph moves each prediction")
    s = pd.DataFrame(m["gnn_vs_no_graph"]["by_connectivity"])
    x = np.arange(len(s)); w = 0.2
    for j, k in enumerate(ORDER):
        axes[1].bar(x + (j - 1.5) * w, s[f"mae_{k}"], width=w - 0.02, color=COLOR[k], label=LABEL[k])
    axes[1].set_xticks(x, [f"{c}\nn={n:,}" for c, n in zip(s.connectivity, s.n)])
    axes[1].set(ylabel="Activity MAE (days)", xlabel="Activity degree (in + out edges)", title="Error by connectivity")
    axes[1].grid(axis="x", visible=False)
    axes[1].legend(fontsize=8, ncol=2)
    fig.tight_layout(); fig.savefig(figs / "graphsage_vs_no_graph_differences.png"); plt.close(fig)


def fold_mae(out, figs):
    f = pd.read_csv(out / "fold_metrics.csv")
    fig, ax = plt.subplots(figsize=(9, 3.8))
    x = np.arange(5); w = 0.2
    for j, k in enumerate(ORDER):
        d = f[f.model == k].sort_values("fold")
        ax.bar(x + (j - 1.5) * w, d.mean_block_mae_days, width=w - 0.02, color=COLOR[k], label=LABEL[k])
    meta = f[f.model == "median"].sort_values("fold")
    ax.set_xticks(x, [f"fold {i}\n{int(n):,} rows\n{int(b)} block{'s' if b > 1 else ''}"
                      for i, n, b in zip(meta.fold, meta.n, meta.blocks)], fontsize=8.5)
    ax.set(ylabel="Mean block MAE (days)", title="Mean block MAE by development fold")
    ax.set_ylim(0, f.mean_block_mae_days.max() * 1.25)
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=8, ncol=4, loc="upper center")
    fig.tight_layout(); fig.savefig(figs / "fold_mean_block_mae.png"); plt.close(fig)


def make_all(out: Path = ROOT / "models/gnn_cambridge", figs: Path = HERE / "figures/cambridge"):
    style()
    figs.mkdir(parents=True, exist_ok=True)
    m = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    oof = pd.read_csv(out / "oof_predictions.csv", dtype={"project_key": str, "activity_key": str})
    loss_curves(out, figs); block_mae_ci(m, figs); block_scatter(out, figs)
    actual_vs_pred(oof, figs); pred_difference(oof, m, figs); fold_mae(out, figs)


if __name__ == "__main__":
    make_all()
