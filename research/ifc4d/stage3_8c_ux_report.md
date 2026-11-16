# Stage 3.8C-UX: PMI decision dashboard

Completed 2026-11-16. The redesigned page shifts the emphasis from artifact inspection to a visual construction-management workspace, while keeping the verified Stage 3.8B schedules authoritative and read-only.

## Open the dashboard

Run PMI normally with launch_app.py and select **PMI Dashboard** in the native Streamlit navigation, or use `/PMI_Dashboard`. A local viewer-mode instance is running at http://127.0.0.1:8512/PMI_Dashboard.

```powershell
.venv/Scripts/python.exe -m streamlit run app.py --client.toolbarMode viewer
```

The existing midterm app and IFC4D technical page remain available. app.py was not edited in this redesign and retains its exact frozen SHA-256: `f741710249919c12b751e9fe9823665278d04b88b9e5a660f829b3325ad3842d`.

## Visual hierarchy and reuse

Inspected the midterm guide, app.py/launch_app.py, existing Streamlit/Plotly implementation, PMI PNG/SVG logo and Stage 3.8C views. Reused the existing logo, navy/blue/teal/coral/gold palette, validated loader, geometry meshes, task-element associations and Plotly selection mechanism. The new page uses locally available Segoe UI/Arial typography rather than requiring a network font.

The page follows the requested sequence: project overview; model and baseline/revision programme side by side; selected activity; change-impact explanation; scenario priorities; final-programme workspace. The overview keeps project, version, schedule and activity selection visible in a sticky toolbar. Dates and finish information precede technical data. Phase colours, readable two-line activity labels, gold selection, red sequence-alert outlines and padded orthographic model framing support visual inspection.

New files are `pages/2_PMI_Dashboard.py`, `dashboard.py`, `dashboard_components.py`, `capture_dashboard_ux.py` and `tests/test_pmi_dashboard.py`. Shared components cover branding, phase legends, schedule charts, geometry presentation, snapshot comparison, scenario cards and scenario request state. The existing research viewer and its tests were preserved.

## Before and after

Compared the preserved [Stage 3.8C building view](screenshots/stage3_8c/building_v0_derived.png) and [bridge view](screenshots/stage3_8c/bridge_v0_as_provided.png) with the accepted new desktop captures:

| Previous interface | Redesigned interface |
|---|---|
| Raw project IDs, V0/V1/V2, as_provided/derived | Bridge / Mid-rise Building; Baseline / Revision 1 / Revision 2; Original / Recalculated Schedule |
| Validation banners and metadata dominate the view | Branded project overview, programme finish and activity/sequence indicators |
| Gantt leads; narrower model with technical captions | Large side-by-side model and phase-coloured Gantt workspace |
| Long identifiers in chart labels | Activity names with zone labels; raw identifiers remain in event data and Technical Details |
| Source conflicts presented primarily as research output | Plain-language sequence alerts and named previous/next activities, dates and shortfalls |
| No decision-flow continuation | Clearly planned priority cards and a disabled final-programme handover |

Technical identifiers, SHA hashes, schema caveats, manifest status, raw conflicts, source provenance and the GlobalId inspector are retained inside **Technical Details**, rather than removed.

## Change impacts and honest scenario boundaries

Revision comparison uses original snapshot dates and durations against the original Baseline. It reports changed activities, signed date/duration shifts, links touching those activities and changed dependency definitions. In the current fixtures dependency definitions do not change. Bridge revisions change 11/17 activities and finish 2/3 calendar days later; building revisions change 15/23 activities and finish 2/5 days later. These are differences between stored snapshots, not inferred causal effects.

The model can highlight either the selected activity's elements or all elements linked to revision-affected activities. No geometry change is claimed: the snapshots share a source model. Sequence inspection separates original issues from the selected schedule's compliance. Original and recalculated dates, inclusive calendar-day labels, comparison overlays and the optional synthetic progress layer retain their established semantics.

Economic, Feasibility and Environmental priority cards are explicitly **Planned capability**. Selecting a priority records only a session-scoped request containing project/version/representation, the source schedule hash and an empty constraints container. It has no engine run or final schedule. The final-programme panel states that no scenario has been evaluated, and generation is disabled. A recalculated dependency-compliant schedule is never relabelled as an economic or environmental optimum. No costs, emissions, AI predictions or optimized numerical results were invented.

## Browser acceptance and tests

Microsoft Edge / Playwright acceptance passed at **1920 x 1400**. Browser assertions cover project/version/schedule selection, exact displayed original/recalculated dates, a real Gantt pointer click, exact task-to-model highlights, revision-affected highlights, progress, three-way schedule overlays, the 15 building Revision 2 source conflicts, visible sticky controls, priority/placeholder consistency, disabled final generation and accessible technical details. Both chart widths exceed 650 px, occupy separate columns, and produce no horizontal page overflow. Manual screenshot review checked legible labels, spacing, complete model framing and absence of chart overlap. Long programmes remain vertically scrollable; this is a desktop acceptance pass, not a mobile usability claim.

Direct mesh-click selection is **not implemented**. Task dropdown/Gantt selection and the technical GlobalId inspector remain the supported interaction paths. The model is still the supplied synthetic proxy geometry, not a reconstructed real bridge/building.

Accepted screenshots:

- [Bridge workspace](screenshots/stage3_8c_ux/bridge_workspace.png)
- [Building revision workspace](screenshots/stage3_8c_ux/building_revision_workspace.png)
- [Revision impact explanation](screenshots/stage3_8c_ux/revision_impacts.png)
- [Sequence issues](screenshots/stage3_8c_ux/sequence_issues.png)
- [Recalculated schedule and progress](screenshots/stage3_8c_ux/recalculated_progress.png)
- [Scenario priorities and final-programme placeholder](screenshots/stage3_8c_ux/scenario_and_final_programme.png)

Full repository suite: **123 tests in 43.935 seconds; OK (skipped=1)**. Five new tests cover snapshot comparisons, chart dates/phases/selection, scenario request boundaries, professional controls and preserved artifacts. The existing skipped test needs the ignored Cambridge generated audit CSV; it was not regenerated. Existing Torch/PyG and bare-mode Streamlit warnings remain.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
# Optional browser tool from Stage 3.8C; Edge must be installed:
.venv/Scripts/python.exe -m research.ifc4d.capture_dashboard_ux --url http://127.0.0.1:8512
```

Machine-readable evidence: `screenshots/stage3_8c_ux/ui_acceptance.json` and `stage3_8c_ux_validation.json`. Original IFC/workbook hashes, Stage 3.8B artifact and implementation hashes, all 53 files in the GNN preservation manifest, the frozen app hash and previous accepted Stage 3.8C screenshot hashes were checked unchanged. No scheduling algorithms, trained models or validated IFC4D files were overwritten. No retraining, commit or push occurred.

## Implemented and pending

**Implemented:** branded dashboard; professional persistent selectors; model/Gantt workspace; phase colours and selected-activity detail; verified element highlighting; baseline/revision and original/recalculated comparisons; plain-language impact and sequence inspection; synthetic progress; technical disclosure; priority-selection and final-programme interface contracts; automated and real-browser acceptance.

**Still pending for the complete Speckle-to-decision workflow:** live Speckle version ingestion and identity matching; geometry/property change detection from actual model versions and its task-impact mapping; verified cost/resource/environmental estimators; scenario constraints and multi-criteria decision engine; scheduling-engine generation and validation of a selected scenario's final Gantt; validated prediction integration; direct mesh-click task selection. These remain development work, not capabilities implied by the dashboard's presentation.
