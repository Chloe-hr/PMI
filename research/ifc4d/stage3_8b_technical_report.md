# Stage 3.8B technical report ? schedule reconciliation and IFC4D

Audited and generated 2026-11-16. Policy: `reconciliation-v1`. Stage 3.8B is complete for the two explicitly synthetic projects. Original spreadsheet and IFC files are unchanged, with SHA-256 values matching the Stage 3.8 audit. No Cambridge experiment, training, fine-tuning, commit or push was performed.

## Implementation and schedule policy

`pipeline.py` exposes load_workbook, project_snapshots, validate, derive, convert, round_trip and run for reuse. `schedule_semantics.md` defines the calendar, lag, snapshot, synthetic-actual and derived-date rules. The older working-day IFC-to-Gantt pipeline is unchanged.

V0 is checked against the Activities baseline; V0/V1/V2 are treated as separate snapshots. The earliest source planned start across snapshots anchors each project: bridge 2025-02-03 and building 2025-04-07. Lexicographically deterministic topological scheduling preserves snapshot durations and dependency IDs/endpoints/types/lags. Root tasks start at the anchor, and successors start at the maximum of the anchor and all lag-adjusted derived predecessor finish boundaries. Original task starts are not release constraints, so this is earliest-feasible scheduling rather than minimum-change repair. Resource feasibility is not modelled.

All schedules use inclusive calendar days. IFC starts are midnight on the first day; IFC finishes are midnight AFTER the inclusive last day. Therefore ELAPSEDTIME PnD equals the interval length. A Gantt label must convert the exclusive finish boundary back to the inclusive last day. Negative lag is explicitly supported by the validator, scheduler and signed IfcDuration; the present workbook contains only FS zero-lag links. Unsupported relationship types and nonintegral lags fail rather than being changed.

Synthetic actual dates and progress are preserved, not reconciled and never used to infer planned relationships. Their 26 out-of-sequence dependency conflicts remain in a separate synthetic_actual scope. delay_days_synthetic equals actual-finish minus baseline planned-finish, not necessarily duration variance. Derived dates are synthetic computed dates, never observed construction dates.

## Source conflicts versus derived schedules

| Snapshot | As-provided FS conflicts | Derived FS conflicts | Tasks shifted | Start shift range (days) | Derived inclusive finish |
|---|---:|---:|---:|---|---|
| SYN-BLD-001-V0 | 18 | 0 | 23 | -5 to 20 | 2025-09-19 |
| SYN-BLD-001-V1 | 15 | 0 | 26 | -5 to 23 | 2025-09-24 |
| SYN-BLD-001-V2 | 15 | 0 | 27 | -7 to 30 | 2025-10-04 |
| SYN-BRG-001-V0 | 2 | 0 | 16 | -14 to 0 | 2025-05-07 |
| SYN-BRG-001-V1 | 4 | 0 | 18 | -13 to 1 | 2025-05-10 |
| SYN-BRG-001-V2 | 7 | 0 | 17 | -15 to 3 | 2025-05-15 |

The six source snapshots contain 61 FS conflicts, including the previously audited 20 baseline conflicts. Every derived schedule has zero FS violations and unchanged task durations. Original and derived dates, signed start/finish shifts, anchor, source activity record and source snapshot record are retained in each derived CSV. Dependency relationships are exported unchanged. As-provided files deliberately remain precedence-inconsistent; passing round-trip checks means preservation, not schedule validity.

## IFC4D outputs and round-trip checks

Twelve IFC4 files: two projects ? three snapshots ? two representations (`as_provided.ifc`, `derived.ifc`). Each contains IfcWorkSchedule, IfcTask, IfcTaskTime, IfcRelSequence with explicit IfcLagTime (including zero), IfcRelAssignsToProcess element links and IfcRelAssignsToControl schedule membership. Added GlobalIds are deterministic UUID5-derived identifiers namespaced by project, version and representation. Workbook task IDs remain IfcTask.Identification; task_ifc_mapping.csv provides the explicit task/GlobalId mapping.

All twelve files were reopened and passed exact checks of task sets and GlobalIds, identifiers, source descriptions, schedule identity and provenance, dates, elapsed durations, inclusive-day interval length, element associations, dependency IDs/endpoints/types/lags and schedule membership. Source entity serializations, including every existing geometry entity, property set and GlobalId, are unchanged. No synthetic actual data are written into planned TaskTime actual/completion fields. Each project/snapshot/representation pair retains all its associations and dependencies: 39 elements/19 dependencies for bridge; 54/26 for building. Thus each paired representation/snapshot contains all 93 associations and 45 dependencies; across twelve files there are 282 tasks, 558 associations and 270 dependency instances.

`round_trip_validation.json` and `schedule_validation.json` keep preservation results separate from schedule compliance. `manifest.json` records source hashes, implementation/policy hashes, output hashes and completion state. All hashes were checked after generation. Original file hashes also match the earlier Stage 3.8 audit, not just the start of this run.

## Schema limitations

IfcOpenShell attribute/schema validation reports 118 pre-existing source-model errors in the bridge and 167 in the building. They concern Coordinates, DirectionRatios and, for the bridge, YDim and NominalValue, mainly integral literals in real-valued attributes. Every output has exactly the same error signatures (entity ID, attribute and message) as its source; **zero new schema errors** were introduced. See stage3_8b_schema_validation.json for per-file counts. Geometry/property values were not normalized because source preservation was required. These files are not represented as schema-clean exchange deliverables. Optional EXPRESS-rule execution was not available because its pytest dependency is absent; it was not substituted for a passing check.

## Artifact layout and reproduction

All pipeline outputs are under `data/processed/ifc4d/stage3_8b_v1/`:

- Six project-version directories, each with derived_schedule.csv, dependencies.csv and both IFC representations.
- source_records.json retains the workbook rows, including Activities, Elements, ElementTask, Progress and version provenance.
- schedule_conflicts.csv/json report project, version, successor task, dependency, original values, required start and shortfall for FS conflicts; synthetic actual conflicts have their own scope.
- task_ifc_mapping.csv, schedule_validation.json, round_trip_validation.json and manifest.json provide traceability and checks.

Run from the repository root:

```powershell
.venv/Scripts/python.exe research/ifc4d/pipeline.py
# The default output already exists; to reproduce, select a fresh directory:
.venv/Scripts/python.exe research/ifc4d/pipeline.py --out outputs/ifc4d/reconciliation-v1-check
.venv/Scripts/python.exe -m unittest discover -s tests -p test_ifc4d.py -v
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

The pipeline refuses to overwrite an existing output directory. A consumer must require manifest.complete and successful round-trip records; an interrupted generation directory without a completed manifest is not an accepted artifact. No source model changes or migration are performed.

## Automated tests

Eight new tests pass, covering exact historical conflicts for all six snapshots and synthetic actuals; duration and inclusive-FS semantics; deterministic diamond scheduling and negative shifts; negative lag scheduling and IFC round-trip; rejection of invalid references, duplicate tasks/dependencies, cycles, dates/durations, unsupported relationship types and fractional lags; incomplete/mismatched snapshots; twelve-file round-trip and schema comparison; unchanged original hashes; corruption detection; refusal to overwrite; and byte-identical artifacts from independent fresh-directory regenerations.

Full repository suite: **111 tests in 37.347 seconds; OK (skipped=1)**. The skip is the existing Cambridge generated-audit CSV test because its ignored activity_label_audit.csv is absent. Existing Torch/PyG Python 3.14 warnings remain. No experiment was rerun.

## Stage 3.8C recommendation

**GO for Stage 3.8C Gantt visualization of these synthetic fixtures.** Use explicit project/snapshot/representation selection; label computed dates as derived synthetic schedules, retain access to originals and date shifts, show source FS conflict warnings, and render the IFC exclusive-finish boundary correctly. Keep synthetic actual progress in a separate layer. Validate the selected viewer against CSV dates, lengths and FS/lag semantics before accepting its rendering.

This GO covers visualization and controlled pipeline validation only. The inherited source schema issues remain visible limitations for strict IFC consumers; no claim of observed execution, real-world forecast accuracy, resource feasibility or schema-clean production exchange is justified.
