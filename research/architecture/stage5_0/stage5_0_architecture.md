# PMI Stage 5.0 | Independent construction planning

**Decision requested** Approve the architecture and the bounded Stage 5.1 proposal. Production implementation requires approval. Direct local IFC import is the first supported route. The system uses an engineering baseline, with optional learning gated on future evidence.

## Evidence and limits

[Stage 4.0A](../../evaluation/stage4_0a/stage4_0a_evaluation_report.md) records repeated duration validation with mean MAE of 6.25 days for ridge and 6.48 for MLP, with negative mean R². Cambridge development GraphSAGE improved macro-block MAE over its no-graph ablation, with a much smaller activity-level gain and near-zero R². This evidence motivates research and does not validate transfer to the planned correction target. The locked records remain outside Stage 5.0.

[Stage 4.0B Sections B–E](../../data_acquisition/stage4_0b/sections_B_E/stage4_0b_report.md) provides BCCA labour breakdowns and direct cost checks plus ÖKOBAUDAT environmental coverage. The data gap is linked and comparable actual/engineering activity pairs. Thiele is civil and provides cost-account actuals, D5 RestageIFC has IFC4 geometry and 886 quantity sets but no durations, and D6/D7 lack quantities. IFC4D synthetic building snapshots SYN-BLD-001 V0–V2 and bridge snapshots SYN-BRG-001 V0–V2 include as-provided and derived representations and support round-trip and revision regression. Bridge tasks exercise interoperability beyond the initial building work template. Real file inventory includes Restage, Schependomlaan, 4DBenchmarkBim and other IFC model sets. Quantity completeness, verified construction quantities, stable identity, licensing and geospatial alignment across real exports remain Section A gates.

## Module boundaries

| Module | Input → output and dependencies | Failure behavior |
|---|---|---|
| adapters | Local IFC bytes → source snapshot and parse report via IfcOpenShell | Quarantine unreadable/schema-unsupported input and duplicate identities |
| bim | Snapshot → elements, spatial graph, material/quantity records, optional meshes via adapter and schema | Preserve unknown values, property conflicts, mesh errors and missing units |
| knowledge | BIM quantities + approved templates/references → allocations and work packages | Surface unsupported methods, work-basis ambiguity and bundled overlap |
| estimation | Work scopes + rates + approved modes → trade and equipment demands, productive hours and holds | Block incomplete modes and quantities, preserve partial diagnostics |
| planning | Activities + calendars + constraints → graph, CPM and CP-SAT schedule | Distinguish bad data, infeasibility and timeout |
| revisions | Two snapshots + accepted mappings + actuals → impact assessment using downstream modules | Block disputed lineage and changes to installed work until disposition |
| intelligence | Validated feature snapshot + engineering estimate → optional correction or abstention | Disabled at Stage 5.6 gate |
| optimization | Approved alternatives and objective scope → evaluated feasible scenarios via planning and evaluation | Explain unsupported objectives and infeasible alternatives |
| evaluation | Allocations + schedules + cost/EPD snapshots → scoped ledgers and coverage | Block incompatible totals and unsupported comparisons |
| export | Snapshot + selected verified schedule → derived IFC4D and manifest | Fail atomically on mapping or round-trip errors |
| schemas | Versioned local data contracts → typed records | Reject invalid values and schema versions |
| validation | Typed records + project context → actionable issues and release decisions | Report entity, source, severity and required resolution |

Core orchestration uses local immutable run bundles, content hashes and explicit IDs. Preserve IFC input bytes and reference snapshots. A temporary run directory becomes visible only after validation and an atomic commit. Key jobs by input digest and settings and isolate concurrent runs. Keep research and legacy Streamlit routes available under existing entry points. Use the migration matrix to choose isolated helpers and regression oracles. Create each package when its first approved implementation needs it.

## Local application

A project workspace owns local file storage and metadata. A future FastAPI service can expose project, import, run/status, comparison, scenario selection and export endpoints. Long IFC and solver work runs in a local worker with progress, cancellation and bounded resource use. A React/TypeScript UI can consume generated OpenAPI types, present a 3D view with element IDs tied to quantity/work-package review and link selection to baseline and scenario Gantts. A revision screen shows baseline/revised geometry, deltas and unresolved matches. Provide a planner input editor, scenario cards with coverage and feasibility, selected schedule Gantt and export actions. Every numerical panel links to evidence and assumptions. Local browser and assets should work offline; packaging, GPU performance and large file memory use need a prototype before adopting this stack. Streamlit remains a useful reference for interaction and data views. The backend owns approvals, validation, and export preconditions. Future Rhino/Revit adapters supply local snapshots through the same contract, with host APIs isolated behind an adapter boundary.

## Optional correction interface

Proposed request includes activity and model version, approved estimate ID, positive productive hours, operation, quantity, crew mode, and planning-time feature and evidence versions. Response is abstention with reason or a log-ratio estimate with calibrated uncertainty, scope and model version. For eligible predictions apply engineering hours × exp(correction) only within reviewed bounds; use the uncorrected baseline on abstention. Never change mandatory waits or hard releases through correction. Record both estimates and decision provenance. Stage 5.6 is **NO-GO**. Require joined actual and engineering productive durations on identical activity scope, crews, calendars and methods; reliable observation provenance and unknown/censored cases; independent project-level holdouts with split-before-feature construction; comparison to uncorrected engineering and simple calibrated baselines; pre-registered uplift and calibration criteria, subgroup and out-of-distribution checks, operation-level and schedule-level utility, and engineering approval. Keep retrospective outcomes out of prediction inputs.

See the companion specifications, CSV audits, Mermaid diagrams and the [implementation roadmap](implementation_roadmap.md).
