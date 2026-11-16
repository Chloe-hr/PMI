# Stage 3.7 final preservation and Stage 3.8 handover

Audited 2026-11-16. No experiment rerun, protocol edit, raw-data modification, commit or push.

## Completeness

PASS: 30 unique training runs: two arms x five folds x three seeds. All 30 checkpoints load, have finite state tensors and matching arm/fold/seed/best-epoch metadata and frozen protocol hash. Five nonempty fitted featurizers are present (35 checkpoint-directory artifacts). All 984 epoch-history rows form complete per-run sequences matching epochs_run. OOF predictions contain 144,110 unique project/activity pairs, with finite numeric columns; membership, fold and block match exactly the frozen development split (70 blocks). No locked-test rows are present. All 20 fold metric rows reproduce their activity and mean-block MAEs from saved OOF predictions. Six seed metric rows, 70 block metric rows and four comparison rows are retained.

The frozen protocol averages raw log predictions before expm1 and clipping. Saved per-seed day predictions are already clipped at zero, so they cannot always reconstruct the exact ensemble; no new inference was performed. Completeness checks establish artifact integrity, not an independent retraining replication.

`models/gnn_cambridge/preservation_manifest.json` records byte sizes and SHA-256 of every preserved result, checkpoint, featurizer, graph-cache artifact and both protocol files. It includes large ignored artifacts so future storage/copy integrity can be checked without rerunning training. Ignoring files does not back them up; retain these local artifacts or copy them to an artifact store for durable recovery.

## Frozen hashes

Machine-readable protocol SHA-256: `ca2ae92ee8a65b82033daf6831fbcd8f056bd0507a277448598a5ad1e97993a1` (matches training_config and every checkpoint).

Protocol Markdown SHA-256: `1a6ca331b12299d390634d03db2601457ddead2042af7e458cdbd8141e18c1be`.

All following current dataset/cache byte hashes match the recorded graph manifest:

| File | SHA-256 |
|---|---|
| split_manifest_conservative.csv | `549e6e701413ee1f4c0e0799b0a4c601e948defbab6b71707a13328e437a3714` |
| feature_matrix.csv | `4ccdfdb66134cf3d9d3696f5473ce14cbc5276acab71b33a3a5fe41293ae7325` |
| exploratory_targets.csv | `51b0d2d68a482792e6933108378005496958e18c6ae606b533ee97a59b3f616a` |
| JPF_Anonymised_Project_Data.json | `e32f311e05c73b8b891b25149d85c95f27536d739f97d17bc52624fbc5ef8f47` |
| nodes.csv | `7f9d976efe48daa2e58989435c4bbb8400a26355e9c85921f2d2034e9639d7aa` |
| edges.csv | `355f60116c9fe53ac09c87a90b3fc1b128f9508c3a4f2785fe53f76b73922717` |

## Preserved comparison and limitations

GraphSAGE mean block MAE 41.59 days versus 44.38 for the matched no-graph arm; paired difference -2.79 days, 95% paired block-bootstrap CI [-4.21, -1.76]. Ridge 47.01; median 50.84. The preregistered development criterion was met. Activity MAE improves only 0.55 days (38.13 to 37.58); R-squared remains near zero and RMSE near 100 days. This does not establish a usable construction-duration predictor.

The result is development-only; 99 locked test blocks were not evaluated in this stage and must not be reused to confirm it. Targets are reported elapsed calendar days, not verified working construction durations. Gains concentrate in small equally weighted blocks; seed variation is comparable to the effect and the block bootstrap excludes seed uncertainty. Small stopping sets are noisy. Exported precedence topology could include execution-period edits; planning-time provenance is unverified. Relationship types were merged, lags omitted and cycles retained. Preserve the full caveats and figures in cambridge_training_results.md, cambridge_validation_results.md and cambridge_graph_feasibility.md; this handover does not supersede them.

## Git disposition (review and commit manually)

Commit candidates:

- `.gitignore` with existing user changes retained and the preservation exclusions added.
- `research/gnn/{cambridge_graph.py,cambridge_model.py,train_cambridge.py,cambridge_figures.py}`.
- Both frozen protocol files, `tests/test_gnn_cambridge.py`, the feasibility/training/validation reports, this handover, and `research/gnn/figures/cambridge/` report figures.
- Small reproducibility evidence under `models/gnn_cambridge/`: training_runs, loss_curves, fold_metrics, block_metrics, seed_metrics, model_comparison CSVs; metrics, environment, provenance, training_config JSONs; run_log.txt and preservation_manifest.json.
- `data/processed/gnn_cambridge/graph_manifest.json` and other small cache metadata (review filenames individually).
- `research/ifc4d/stage3_8_dataset_audit.md` as the new dataset audit. The three raw synthetic inputs may be committed separately as fixtures after reviewing their provenance/size; their synthetic status must remain explicit. Do not blindly stage unrelated raw data.

Exclude from ordinary Git and retain on disk: the entire Cambridge checkpoints directory, model checkpoints/fitted featurizers, 33 MB OOF CSV, 42 MB node CSV and 14 MB edge CSV. The SHA manifest preserves their identities. No files were deleted or staged.

## Full test suite

`.venv/Scripts/python.exe -m unittest discover -s tests -v`: **103 tests in 47.779 seconds; OK (skipped=1)**. One generated-output Cambridge audit test skipped because activity_label_audit.csv is absent; it was not regenerated. Torch/PyG emitted Python 3.14 compatibility/deprecation warnings. Unit tests exercise small fixtures; the frozen experiment was not rerun.
