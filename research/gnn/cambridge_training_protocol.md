# Stage 3.7: Cambridge GNN training protocol (frozen)

**Protocol** `PMI-Stage3.7-cambridge-gnn-v1`, frozen on 2026-11-16 **before any model fitting**.
The machine-readable version is [`cambridge_protocol.json`](cambridge_protocol.json), sha256 `ca2ae92ee8a65b82033daf6831fbcd8f056bd0507a277448598a5ad1e97993a1`. Every checkpoint and result file records that hash. Any change after validation results have been seen requires a new `protocol_version`, labelled as a new exploratory experiment.

The prerequisite graph policy and its conditional GO are in [`cambridge_graph_feasibility.md`](cambridge_graph_feasibility.md).

## Data and target

| Item | Setting |
|---|---|
| Rows | Frozen conservative split, `split == 'train'` only: 144,110 labelled activities in 70 blocks |
| Locked test blocks (99) | Never loaded. `cambridge_graph.load_cached` refuses any test project |
| Graphs | One per development `project_key`: 163 graphs, 305,681 nodes (all exported activities), 494,853 directed edges |
| Target | `reported_completed_activity_elapsed_calendar_days`. These are **reported elapsed calendar days** from exported actual timestamps. They are not verified, not working days and not active construction time. The model trains on `log1p(days)`; predictions are `expm1(output)`, clipped at 0 |
| Node inputs | `activity_description` (TF-IDF 50k, 1–2-grams → SVD 128 → standardised), `project_type` and `uk_region` (one-hot). The featurizer is fit inside each fold on the fitting projects' nodes only |

## Models

| | GraphSAGE | Matched no-graph model |
|---|---|---|
| Class | `CambridgeSAGE(use_graph=True)` | `CambridgeSAGE(use_graph=False)` |
| Encoder | Linear(n_in → 64) + ReLU + Dropout(0.2) | same |
| Graph layers | 2 × [SAGEConv(64, 64, mean) over pred→succ **+** SAGEConv(64, 64, mean) over succ→pred, ReLU, dropout, residual, LayerNorm] | same modules; the edge set is emptied, so each SAGEConv reduces to its root linear map plus bias |
| Head | Linear(64 → 64) + ReLU + Linear(64 → 1) | same |
| Parameters | 46,657 (n_in = 142) | 46,657 |
| Inputs, batches, seeds, stopping | identical | identical |

Because the two arms are the same network, any difference in error is attributable to message passing over the exported precedence logic.

## Optimisation

| Setting | Value |
|---|---|
| Loss | L1 on log1p(days), averaged over the labelled nodes in the batch. Its minimiser is the conditional median, which matches the MAE metric |
| Optimiser | AdamW, lr 3e-3, weight decay 1e-4 |
| Batch | 8 project graphs (full graphs, shuffled each epoch) |
| Maximum epochs | 150 |
| Early stopping | Monitor L1 on the inner-stopping blocks (Stage 2.3E rule: outer-training blocks sorted by sha256('23051' + block), first ⌊n/10⌋, minimum 1). Patience 15, min Δ 1e-4, restore the best epoch |
| Validation-fold loss | Logged every epoch **for the curves only**. It is never used for stopping, selection or tuning |
| Seeds | 23051, 23052, 23053 (plus 1000 × fold). The primary prediction per model is the mean of the three seeds' log1p outputs |
| Threads | `torch.set_num_threads(16)`, CPU |

## Cross-validation

The five frozen `development_validation_fold` values are used. For each fold *f*, models are trained on folds ≠ *f* (fitting blocks plus inner-stopping blocks) and predict fold *f*. Each development block is therefore predicted out-of-fold exactly once.

| Fold | Rows | Blocks | Note |
|---|---:|---:|---|
| 0 | 99,636 | 1 | Dominant block `C-5f73906a8795`; when it is validated, training has only 44,474 rows |
| 1 | 19,001 | 1 | |
| 2 | 8,818 | 1 | |
| 3 | 8,328 | 32 | |
| 4 | 8,327 | 35 | |

## Baselines

1. **Median**: the median of all labelled outer-training rows.
2. **Ridge**: the Stage 2.3E preprocessor (TF-IDF 50k 1–2-grams plus one-hot) and `Ridge(lsqr)` on raw days. Alpha per fold is reused from Stage 2.3E `ridge_alpha_by_fold` = [10, 10, 10, 10, 1]; it was development-selected and is not re-tuned. These two baselines must reproduce Stage 2.3E `fold_metrics.csv`, which checks the pipeline.
3. **Matched no-graph neural network** (above).
4. **GraphSAGE** (above).

## Metrics and success criterion

- **Primary metric:** mean block MAE (days), the mean over the 70 development blocks of each block's out-of-fold activity MAE.
- **Secondary metrics:** activity-level MAE, RMSE, R², median AE, the Stage 2.3E statistic (mean over folds of the per-fold macro block MAE), per-fold and per-block metrics, and results by connectivity.
- **Uncertainty:** paired block bootstrap over the 70 blocks, 2,000 resamples, seed 23051, 95% percentile intervals.
- **Success criterion (pre-registered):** GraphSAGE adds value only if
  - (a) the paired 95% CI of *mean block MAE(GraphSAGE) − mean block MAE(no-graph)* lies entirely below 0, **and**
  - (b) GraphSAGE's mean block MAE is below both the median and ridge baselines.

  Otherwise, the conclusion is *no evidence that exported schedule logic improves prediction*.

## Outputs

| Location | Contents |
|---|---|
| `models/gnn_cambridge/checkpoints/` | `{graphsage,no_graph}_fold{f}_seed{s}.pt` (30 files) and `featurizer_fold{f}.joblib` |
| `models/gnn_cambridge/` | `oof_predictions.csv`, `loss_curves.csv`, `training_runs.csv`, `fold_metrics.csv`, `block_metrics.csv`, `seed_metrics.csv`, `model_comparison.csv`, `metrics.json`, `training_config.json`, `provenance.json`, `environment.json`, `run_log.txt` |
| `research/gnn/figures/cambridge/` | Charts used in the results reports |

The script refuses to overwrite an existing `oof_predictions.csv`. Stage 2.3E outputs (`data/processed/stage2/cambridge_experiment/`, `models/cambridge_duration_v1/`) are only read.

## Reproduce

```powershell
.venv\Scripts\python.exe research\gnn\cambridge_graph.py      # verifies checksums, builds graph cache
.venv\Scripts\python.exe -m unittest tests.test_gnn_cambridge
.venv\Scripts\python.exe research\gnn\train_cambridge.py      # frozen run
.venv\Scripts\python.exe research\gnn\cambridge_figures.py    # figures from saved outputs
```
