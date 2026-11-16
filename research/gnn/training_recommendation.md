# Stage 3.7B: recommended GNN training experiment

*Proposal only; nothing has been trained. It builds on [`new_dataset_audit.md`](new_dataset_audit.md) and reuses the existing PyTorch Geometric code in `research/gnn/` (`graph_schema.py`, `model.py`, `train.py`, `evaluate_overrun.py`).*

## Decision

| Role | Dataset | Independent groups |
|---|---|---|
| **Supervised training and evaluation** | **Cambridge**, frozen Stage 2.3D protocol (`PMI-Cambridge-retrospective-v1`) | **169 conservative blocks**: 70 train / 99 locked test |
| External test (secondary model only, reported separately) | Ghent DSLIB, G/G | 17 groups |
| **Case study / demonstration (no training)** | **SCHEPENDOMLAAN** | **1 building** |

SCHEPENDOMLAAN has only one independent project and no actual activity dates. It is used as an **external case study**: the BIM-to-activity graph, validation of PMI's task generation, and an inference demo. It is not used for supervised training, and its numbers must not be presented as evidence of generalisation.

---

## Primary experiment: Cambridge, activity elapsed time, graph vs no graph

**Question:** with the same planning-time features, does message passing over the project's precedence network reduce error compared with a model that sees each activity alone?

| Item | Specification |
|---|---|
| **Dataset** | Cambridge JPF export, eligible population frozen by Stage 2.3C/2.3D: 180,137 labelled activities, 268 project IDs. All 444,156 activities stay in the graphs as nodes for message passing; only the eligible activities in the current split are labelled. |
| **Target** | The frozen target: `reported_completed_activity_elapsed_calendar_days = (Actual_Finish − Actual_Start)/86400`. Train on `log1p(days)`; report in days. These are *exploratory reported timestamps, not verified ground truth* (frozen label provenance). |
| **Node features** | (1) The frozen 2.3D features: `activity_description` as a 256-dim **HashingVectorizer** (stateless, so no vocabulary is fitted on held-out data), and `project_type` and `uk_region` one-hot with an "unknown" bucket fitted inside each training fold. (2) **Structure-only** graph features: log in-degree and log out-degree, relative depth in the precedence DAG, log project activity count. **No planned dates or durations** in the primary model: the audit flags them as possibly revised, which would leak the outcome into the input. |
| **Edges** | Predecessor → successor from `Activity_Relationships`, added in both directions. `edge_attr = [is_forward, is_backward]`, which is what `DurationGNN` uses today. Relationship type (FS/SS/FF/SF) and lag are parsed and stored but **not used in v1**, because using them requires an edge-typed convolution, a model change to evaluate separately. Missing or `null` relationships give isolated nodes, never invented edges. |
| **Independent groups** | Conservative scenario: **70 training blocks** (163 project IDs, 144,110 labelled activities) and **99 test blocks** (105 project IDs, 36,027 activities). The dominant block holds 92 projects and 99,636 rows (55%). |
| **Train/test strategy** | The frozen split, unchanged. Model selection uses the frozen 5 development folds **within the training blocks only**. The dominant block is reported separately as its own fold, as the protocol requires, and is never split. The test blocks are opened **once**, after the configuration is locked. Then, without feedback into the primary choices, the predeclared sensitivity scenarios (`content_supported`, `task_id_only`) are run. |
| **Architecture** | The existing `DurationGNN`: input MLP (n_in → 64) → **3 × [SAGEConv(predecessors) + SAGEConv(successors), mean aggregation, residual, LayerNorm, dropout 0.1]** → 2-layer head → 1 output. One graph per project, full batch. |
| **Training** | AdamW (lr 3e-3, weight decay 1e-4), Huber loss (δ = 0.5) on labelled nodes. At most 200 epochs, with early stopping (patience 30) on the development validation fold only. **Hyperparameters are fixed now, not tuned.** 5 seeds (42–46) to report the spread. |
| **Baselines** (same folds) | (1) Training median. (2) Median per `project_type`. (3) Text + categorical **Ridge** on the same hashed features (the classic non-graph model). (4) **`NodeMLP`**: identical features and head, no message passing. This is the control that isolates the graph's contribution. |
| **Metrics** | The frozen metrics: MAE and RMSE in elapsed calendar days, **macro-block MAE**, per-block errors. Plus median absolute error, and a paired bootstrap over **blocks** (2,000 resamples) for GNN vs NodeMLP and GNN vs the best baseline. Results are reported both with and without the dominant block. |
| **Success criterion (declared now)** | The GNN beats NodeMLP **and** the best baseline on macro-block MAE in the locked test, with the bootstrap 95% CI excluding 0. Anything else is reported as a null result, just as the Ghent result was. |

### Secondary experiment (predeclared, separate, run after the primary is locked)

- **Change:** add `log1p(planned elapsed calendar days)` as a feature. The target becomes `log(actual elapsed / planned elapsed)`, and an **"actual = planned"** baseline is added.
- **Leakage warning:** the planned dates may be revised. Any gain is labelled *possibly leakage-driven*.
- **Metrics:** the overrun AUC per block and per fold (`evaluate_overrun.py`).
- **External test:** apply the model to Ghent. Ghent's ratio uses working time while Cambridge's uses calendar time; the ratio cancels most of that, but not all, so it is reported separately and never pooled.

---

## SCHEPENDOMLAAN case study (Stage 3.7C, no training)

1. **BIM-to-activity graph.**
   - Source: the Synchro IFC plus the as-planned event log.
   - Nodes: 3,505 elements and 73 tasks, joined on the Synchro GUIDs.
   - Element features: class, NL-SfB code, material and quantities from `SynchroResourceProperty`.
   - Task edges: the 42 IFC sequences, or 48 from the XML.
2. **Validate PMI's Stage 3.2 task generation against a human plan.** This needs no labels.
   - Run `research/ifc_to_gantt` on the design IFC.
   - Map elements to the Synchro export by element name.
   - Compare PMI's element → work-package grouping with Synchro's element → task grouping (purity / adjusted Rand index), and PMI's precedence with the planner's.
3. **Inference demo.**
   - Apply the trained model to the 114-task network and show the predicted versus planned durations.
   - The 8 tasks flagged "too late" by the point-cloud comparison may be shown as an **illustration only**: they are one project, 5 scan weeks, and "on time" is a default value.
   - Cambridge predicts calendar days; convert using the plan's own 8 h, Mon–Fri calendar.

Never use the `Eventlog with actors FAKE` files.

---

## Prerequisites (in order; each is a gate)

1. **Restore the Cambridge raw JSON** by extracting the tracked `data/raw/cambridge/JPF_Anonymised_Project_Data.json.zip` to its git-ignored path.
   - Verify its SHA-256 against the digest frozen in `design_freeze.json` / `input_review_manifest.json`.
   - **Stop if it doesn't match.** Nothing is regenerated or fabricated.
2. Write `research/gnn/cambridge.py`. It loads activities, parses `Activity_Relationships`, and joins to `split_manifest_conservative.csv` on the frozen composite keys (the expected result is 0 unmatched eligible keys). Add tests for it.
3. **Commit a protocol extension (pre-registration) before any training.** It records:
   - the graph-feature addition to the frozen feature list;
   - the fixed hyperparameters;
   - the success criterion above.
4. Only then train. Open the test blocks once.

## What this will and won't show

- **Will show:** whether precedence-network context improves retrospective prediction of reported elapsed activity time across 99 unseen project blocks, a far stronger test than Ghent's 17 groups.
- **Won't show:** prospective forecasting accuracy, verified ground truth, working-time durations, or IFC change-induced delay. These are exclusions the frozen protocol already declares.
- **BIM-linked GNN:** SCHEPENDOMLAAN shows the data structure such a model needs, but training one still requires multiple projects with element ↔ activity links **and** actual dates. The data request in [`README.md`](README.md#data-that-would-be-needed) still applies.
