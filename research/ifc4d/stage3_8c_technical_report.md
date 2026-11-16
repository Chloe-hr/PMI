# Stage 3.8C technical report: interactive IFC4D Gantt visualization

Completed 2026-11-16. The native PMI Streamlit page reads the preserved Stage 3.8B artifact bundle; it never runs the reconciliation/conversion pipeline, trains a model or writes source data. All data and derived computations remain explicitly synthetic.

## Application integration and launch

Inspected app.py, launch_app.py, the Plotly mesh section of the existing application, scripts/export_geometry.py, research/ifc4d/pipeline.py and Stage 3.8B manifests/validation records. Reused Plotly, Streamlit and the existing IfcOpenShell world-coordinate geometry settings. No new web framework, hosting or application rewrite.

The existing app.py is protected by earlier frozen checksum tests. The final integration is therefore a native Streamlit multipage addition, `pages/1_IFC4D_Synthetic.py`; app.py and launch_app.py retain their existing behavior. app.py has its exact historical frozen SHA-256 f741710249919c12b751e9fe9823665278d04b88b9e5a660f829b3325ad3842d; no checksum baselines or existing tests were relaxed.

Run the application normally:

```powershell
.venv/Scripts/python.exe launch_app.py
# Or:
.venv/Scripts/python.exe -m streamlit run app.py
```

Choose **IFC4D Synthetic** in the native sidebar. Direct route: `/IFC4D_Synthetic`. If a server was already running before the new pages directory existed, restart it once for page discovery. The verification server was run on localhost:8511.

## Read-only data contract

`viewer_data.py` requires manifest.complete and round_trip_passed to be exactly true. Every load hashes all manifest-listed files, rejects missing required entries/files and unsafe paths, and checks the complete 12-way project/version/representation matrix before rendering any project. Parsed data are not retained across reruns without these integrity checks. Geometry caching includes the verified selected IFC SHA-256 in its key.

The loader cross-checks source snapshots, task identifiers and GlobalIds, names, source provenance, inclusive dates and durations, derived shifts, all element assignments, geometry GlobalIds, FS endpoints/types/lags, schedule project/version/representation/input hashes, and source/selected validation results. Round-trip records must be successful, unique and complete, with expected counts. Source conflicts are independently checked against the stored snapshot/dependencies without deriving or changing schedules. Corruption or incompleteness produces an explicit rejection before charts render. This detects accidental artifact corruption and structural mismatches; the local manifest is not a cryptographic authenticity service against an adversary replacing the entire bundle.

Authoritative artifacts: `data/processed/ifc4d/stage3_8b_v1/`. Neither the original workbook nor original IFC models are needed to render the page; their recorded hashes remain part of displayed provenance. Source files were separately checked unchanged during final verification.

## Gantt, task selection and geometry

Controls select SYN-BRG-001 or SYN-BLD-001, V0/V1/V2, as_provided/derived, any task, and an optional synthetic progress layer. All 20 bridge tasks or 27 building tasks are shown, with full IDs and names. A comparison toggle overlays grouped source and derived bars; the selected representation is opaque and the comparison representation translucent. Source conflict endpoints are red, selected tasks gold, source bars blue and derived bars green.

Bars run from the start midnight to the exclusive midnight after the inclusive finish. Width is duration times 86,400,000 milliseconds, preserving calendar-day lengths including one-day tasks. Hover labels convert the IFC exclusive finish back to the inclusive last date and show task ID/name, source/derived dates, signed shifts, project, version and source as_of_date. No source dates are corrected.

A real Gantt pointer click updates task selection and highlights exactly the task's assigned IFC GlobalIds. A task dropdown offers the same selection path. The GlobalId dropdown selects an element, displays its metadata and linked task, and updates the Gantt/task highlight. This is tested control-based two-way inspection. **Direct click-to-select on the 3D mesh is not supported or claimed**; the viewer explicitly says to use the GlobalId selector. Meshes support orbit/zoom and element-GlobalId hover. The original IFC GlobalIds identify all rendered geometry.

The existing application uses Plotly Mesh3d with IfcOpenShell triangulation. These source models have inherited schema/topology issues: the geometry kernel rejected all 93 supplied proxy extrusions. A narrow, disclosed fallback reads each single IfcExtrudedAreaSolid/IfcRectangleProfileDef directly, applies its IFC profile/solid/product placements and extrusion direction, and triangulates its actual dimensions. The supplied 2D profile positions include a redundant zero Z coordinate; only strictly planar XY coordinates with zero extra Z are accepted. Nonzero Z, unsupported shape kinds and invalid dimensions are rejected. This is not a guessed bounding box, a reclassification of the proxies, or an IFC rewrite. Vertex/triangle and volume checks verify the current boxes. The existing scene's synthetic grid layout is preserved; it is not rearranged into a realistic bridge/building.

## Source validity, preservation and progress

The validation panel reports source conflict IDs, predecessor/successor tasks, original predecessor finish and successor start, required successor start, signed lag and calendar-day shortfall. Metrics distinguish source conflicts from compliance of the selected representation. Bridge source counts V0/V1/V2 are 2/4/7; building counts are 18/15/15. All six derived schedules are dependency-compliant; the original six remain unchanged and inconsistent. Successful IFC round-trip preservation is displayed separately and never substituted for schedule validity.

The progress layer shows purple diamonds at the latest generated observation per task on or before the selected date. It does not interpolate, use future observations or move observations onto derived dates. Tasks without a record receive no marker. The records are explicitly labelled synthetic, never independently observed execution; the underlying source progress remains separate from computed schedules.

Inherited IFC schema issues remain: bridge 118 and building 167, with zero newly introduced errors reported by Stage 3.8B. No claim of schema-clean production interchange, resource-feasible scheduling or real-world predictive accuracy is made.

## Tests and browser evidence

Full suite: **118 tests in 36.140 seconds; OK (skipped=1)**. The skip remains the existing generated Cambridge audit CSV test because its ignored activity_label_audit.csv is absent. Existing Torch/PyG Python 3.14 and bare-mode Streamlit test warnings remain. Seven new viewer tests verify:

- The full 12-way selector matrix, all 47 task IDs and all 93 element assignments, exact source conflict counts and selected compliance.
- Inclusive finish labels, leap-day/year boundaries and exact Gantt bar widths.
- Task-to-element GlobalIds, geometry IDs, finite box vertices, extrusion volumes and highlighted mesh IDs; unsupported nonplanar fallback rejection.
- Rejection of incomplete manifests, missing files/hashes, unsafe paths, changed bytes, failed round-trip records and inconsistent task mappings, including semantic checks when hashes are updated.
- Original source and all Stage 3.8B file hashes unchanged by loading/rendering.
- Streamlit project/snapshot/representation/task/progress controls and an explicit rejection screen before chart rendering.

Browser acceptance used installed Microsoft Edge with Playwright, not generated mock screenshots. A physical pointer click through Plotly's overlay selected bridge task T013 and matched its highlighted GlobalIds. The browser then switched projects/representations, selected building task T027 via a linked element GlobalId, enabled progress and switched to V2. All assertions passed. No direct mesh selection was tested or claimed.

Screenshots:

- [Bridge V0 as provided, selected T013](screenshots/stage3_8c/bridge_v0_as_provided.png)
- [Building V0 derived, selected T027](screenshots/stage3_8c/building_v0_derived.png)
- [Building synthetic progress layer](screenshots/stage3_8c/building_synthetic_progress.png)
- [Building V2 source-conflict inspection](screenshots/stage3_8c/building_v2_conflicts.png)

Machine-readable checks are in `stage3_8c_validation.json` and `screenshots/stage3_8c/browser_validation.json`. Screenshot SHA-256 values and installed package versions are recorded. Browser tooling is optional and separate from runtime requirements:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_ifc4d_viewer.py -v
.venv/Scripts/python.exe -m unittest discover -s tests -v
# Optional, to reproduce browser captures using installed Edge:
.venv/Scripts/python.exe -m pip install -r research/ifc4d/requirements-browser.txt
.venv/Scripts/python.exe -m streamlit run app.py --server.port 8511
# In a second terminal:
.venv/Scripts/python.exe -m research.ifc4d.capture_stage3_8c --url http://localhost:8511
```

## Preservation and deliverables

Added native Streamlit page, reusable read-only loader, Plotly/Streamlit view module, seven viewer tests, optional browser-capture script/dependency file, four screenshots, machine-readable validation and this report. All Stage 3.8B artifact hashes and implementation/policy hashes still match their manifest. The three original input hashes match the Stage 3.8 audit; every file in the Stage 3.7 GNN preservation manifest also retains its recorded hash. Existing app.py matches its exact frozen hash. No frozen protocol, IFC model, spreadsheet, experiment output or prediction file was changed or regenerated. No GNN inference/training, cost optimization, commit, staging or push was performed.

## Stage 3.8D recommendation

**GO for Stage 3.8D exploratory prediction-interface integration work.** The UI now has tested project/version/representation keys, task/element mappings, provenance, separate date representations and explicit error handling to attach a separately labelled prediction layer.

This GO establishes software integration readiness only. Before attaching any actual predictor, define its feature/target compatibility, model/version provenance, inference protocol, uncertainty and failure behavior separately. The two generated projects provide no independently observed labels, and the preserved Cambridge development result does not establish usable construction-duration prediction. Do not train on these fixtures, reuse locked evaluation blocks, overwrite preserved schedules, or present an experimental output as validated construction forecasting. Production predictive validity remains unestablished.
