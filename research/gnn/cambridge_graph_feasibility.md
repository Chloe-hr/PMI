# Stage 3.7: Cambridge graph feasibility

**Decision: CONDITIONAL GO** for a development-only, retrospective GraphSAGE experiment. The graph is built from exported precedence relationships, which are an explicit extension of the frozen Stage 2.3C feature policy (details in §5). No result from this stage may be described as a pre-execution forecast.

All numbers below come from `python research/gnn/cambridge_graph.py`, which writes `data/processed/gnn_cambridge/feasibility_diagnostics.json`. The diagnostics cover **development projects only**. Projects that own the 99 locked test blocks are skipped while the raw JSON is streamed, so their activities are never placed in a graph.

## 1. Experiment readiness

| Check | Result |
|---|---|
| Raw JSON `JPF_Anonymised_Project_Data.json` | sha256 `e32f311e…8f47`, which matches `design_freeze.json` (checked on every extraction) |
| Frozen split `split_manifest_conservative.csv` | sha256 `549e6e70…3714`, which matches the freeze. 144,110 development rows in 70 blocks; 36,027 test rows in 99 blocks; no block or project crosses the split |
| `feature_matrix.csv`, `exploratory_targets.csv` | Match the freeze |
| Permitted features | `activity_description`, `project_type`, `uk_region` (Stage 2.3E `feature_manifest.json`) |
| Target | `reported_completed_activity_elapsed_calendar_days` = (Actual_Finish − Actual_Start)/86400. These are **reported elapsed calendar days, not verified construction or working durations**. `verified_ground_truth = False` on every row |
| Development folds | The 5 frozen folds, with 99,636 / 19,001 / 8,818 / 8,328 / 8,327 rows and 1 / 1 / 1 / 32 / 35 blocks. Fold 0 is the dominant block `C-5f73906a8795` |
| Stage 3.5 Ghent implementation | `research/gnn/{model,train,graph_schema}.py`: direction-separated GraphSAGE with a matched MLP and grouped CV. This stage reuses the design and leaves those files unchanged |
| Environment | `.venv`: Python 3.14.7, torch 2.15.0+cpu, torch_geometric 2.8.1, scikit-learn 1.9.1 |

## 2. Are there explicit dependency relationships?

Yes. Each activity carries `Activity_Relationships`, which maps predecessor IDs to records with `Predecessor_ID`, `Relationship_Type` and `Lag` (plus a corpus-fit `Predecessor_GMM_Classification` topic).

Development projects (163 projects, 70 blocks, 305,681 exported activities):

| Quantity | Value |
|---|---:|
| Relationship records | 502,318 |
| Resolved inside the same project (edges kept) | 494,853 (98.5%) |
| Unresolved or pointing outside the project (dropped) | 7,465 |
| Self-loops / duplicate pairs | 0 / 0 |
| Activities whose relationship map is missing (`null`) | 30,770 (10.1%) |
| Types | FS 412,679 · SS 43,657 · FF 43,534 · SF 2,447 · `PR_FF1` 1 |
| Labelled development activities with ≥1 predecessor / ≥1 successor | 91.7% / 92.1% |
| Labelled activities with no edge at all | 4.8% (by fold: 6.0, 1.0, 2.2, 4.7, 1.8%) |
| Projects containing a precedence cycle | 34 (2,651 nodes in cycles) |

The graph is dense enough for message passing to matter for almost every labelled activity.

## 3. Can edges be built without post-execution information?

**Construction inputs.** Edges use only `Predecessor_ID` (resolved inside the project) and the edge direction. The following are **not read** into the graph: actual or planned dates, durations, progress, float, lag (its unit is unverified, and the headers mix hours and days), `Predecessor_GMM_Classification` (fit on the whole corpus) and the target. Edge construction therefore uses no completion date or target duration.

**Node selection.** Every exported activity of a project becomes a node, including incomplete ones. Restricting the graph to completed activities would select nodes on an execution outcome. Only the frozen eligible development rows carry labels. Unlabelled nodes contribute their description, project type and region. On 339 unlabelled nodes the description matches the Stage 2.3C explicit-outcome phrase rule and is blanked.

**Cross-project links.** Of the 96 project pairs that share task IDs (`project_relationships.csv`), the shared IDs carry different descriptions in 7,839 of 7,840 cases. They are identifier collisions, not snapshots of one schedule. A predecessor ID that does not resolve inside its own project therefore cannot be trusted, and it is dropped. Within a project, keys are unique, so resolution is unambiguous.

**Provenance of the topology itself.** The relationships were exported at each project's `Status_Data_Date`. They may have been edited during execution. That is why Stage 2.3C set `predecessor_count_as_exported` to `exclude_until_baseline_review`. The evidence available for that review:

| Test | Result | Reading |
|---|---|---|
| FS links where both ends have actual dates: successor started before the predecessor finished | **20.1%** (14.7% by more than 1 day) of 242,668 | The logic was **not rebuilt from as-built dates**. An as-built reconstruction would show close to 0% violations |
| Missing relationship map: completed vs. not-complete activities | 11.4% vs. 7.5% | Completed activities lose logic slightly more often. This is consistent with progress-period edits, or with early or administrative activities. It cannot be resolved here |
| Mean intra-project predecessors: completed vs. not-complete | 1.47 vs. 1.91 | Same caveat |
| Spearman ρ between degree and target (labelled development rows) | in-degree 0.035, out-degree 0.077 | Topology alone carries very little information about elapsed duration, so its capacity to act as an outcome proxy is small |
| Median target: isolated vs. connected | 7.4 vs. 8.4 days | Small difference |
| Earlier snapshot of the same schedule | **None available** | The shared-ID pairs are collisions, so relationship stability over time **cannot be tested** |

## 4. Prediction-time availability of graph features

| Input | Available at the intended prediction time? |
|---|---|
| Activity description, project type, region | As-exported and unverified (unchanged Stage 2.3E status) |
| Edge existence and direction | Conceptually a planning-time artifact. The exported version may include execution-period edits, and no original issue is available to compare against |
| Neighbour descriptions | Same status as the node's own description |
| Neighbour labels or durations | **Never used**. Labels are not node inputs, and message passing carries only `x` |

All graph inputs therefore sit in the same "as-exported, unverified" provenance class as the features Stage 2.3E already permits. None is drawn from the excluded post-execution fields (actual dates, progress, float, growth, weather, at-completion duration).

## 5. Decision and conditions

**CONDITIONAL GO**, on these conditions:

1. **Recorded policy extension.** Exported topology moves from `exclude_until_baseline_review` to an *exploratory retrospective input*. This document is the baseline review, and its finding is that the review is **inconclusive, not passed**. Results describe what exported schedule logic adds retrospectively, not what a pre-construction network would add.
2. **No explicit degree or CPM features.** Node inputs remain the frozen three. Float, task position and concurrency remain excluded, because they are derived from progressed dates.
3. **Matched control.** The no-graph model is the same network with the edge set emptied. Any difference is attributable to message passing over the exported logic.
4. **Development-only.** Locked test projects are never materialised, so they cannot enter selection, tuning, early stopping or reporting.
5. **Reporting.** Results stratified by connectivity (isolated vs. connected) are reported, so a gain that comes only from topology acting as a proxy would be visible.

**If the condition in (1) is unacceptable**, the defensible alternatives are:
- (a) a text-only model, which is Stage 2.3E's MLP and has already been run;
- (b) a graph built from WBS hierarchy, which is also `sensitivity_only` under Stage 2.3C because it may encode parent identity;
- (c) a similarity or kNN graph over description embeddings fit inside each fold, which avoids exported topology but encodes no schedule dependency;
- (d) obtaining baseline-versioned P6 exports (XER at the first issue) to verify the original logic.
