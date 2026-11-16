# Stage 3 — IFC → tasks → Gantt → IFC4D

Research pipeline on branch `feature/ifc-to-gantt`. It doesn't touch `app.py` or the midterm pipeline, and it reuses `scripts/schedule_engine.py` for CPM.

```powershell
python research\ifc_to_gantt\first_gantt.py                         # P0: illustrative Gantt
python research\ifc_to_gantt\run.py                                 # V1 = models\original.ifc
python research\ifc_to_gantt\run.py --v2 models\revised.ifc         # + V1 vs V2 comparison
python research\ifc_to_gantt\run.py --v1 a.ifc --v2 b.ifc --start 2027-01-11 --out outputs\proj
python -m unittest tests.test_ifc_to_gantt
```

| Stage | File | Output |
|---|---|---|
| 3.1 | `extract_elements.py` | `elements.csv`, with a source-independent schema (IFC now, Speckle next) and `model_version` = file hash |
| 3.2 | `generate_tasks.py` + `task_rules.json` | `tasks.csv`, `task_element_links.csv`, `dependencies.csv`, `unclassified.csv` |
| 3.3 | `schedule_tasks.py` | `schedule.csv` (CPM, Mon–Fri) and `gantt.html` (by phase; black outline = critical) |
| 3.3 | `write_ifc4d.py` | `scheduled_v1.ifc` (IFC4: work schedule, tasks, task→element outputs, FINISH_START sequences) |
| 3.4 | `compare_versions.py` | `compare/element_changes.csv`, `task_changes.csv`, `gantt_compare.html` |

## How tasks are generated

1. **Classify** each element by IFC class, material keywords and whether it has a parent element. Material keywords matter: in the test model, `IfcSlab` covers the concrete ground slab, the timber floor structure *and* the tile or wood floor finishes. The first matching rule wins. Unmatched elements go to `unclassified.csv`; they are never guessed.
2. **Group** the elements into one task per work package and storey. Storeys are resolved through spaces and aggregates, so furniture inside rooms still lands on its storey.
3. **Duration** = `max(min_days, ceil(Σ quantity_i / rate_i))`. Aggregated parts such as stair flights and stringers are linked to the task without adding work.
4. **Dependencies** (finish-to-start) come from package templates:
   - `same`: same storey.
   - `below`: the same package on the nearest lower storey.
   - `global`: every task of that package, e.g. partitions after the roof is watertight.
   - Mobilisation comes first and handover last.

## Known limitations (be explicit about these in the report)

- **Productivity rates in `task_rules.json` are ASSUMED placeholders.** The Gantt is a preliminary, explainable schedule, not a validated forecast.
- The calendar is Mon–Fri with no holidays and a single crew per task. There is no resource levelling yet; that is the OR-Tools stage.
- IFC2x3 inputs are migrated to IFC4 (via `ifcpatch`) **in the output copy only**, because IFC2x3 `IfcTask` has no Identification, PredefinedType or TaskTime. GlobalIds are preserved.
- Task times are set directly, not through the IfcOpenShell cascade. Without an `IfcWorkCalendar` the cascade counts calendar days and overwrote PMI's working-day dates; this was caught by validating with `ifc4d-gantt`.
- The V1/V2 comparison only reports changes that drive the schedule (class, storey, materials, quantities). Property-only changes, such as fire rating or U-value, don't move the generated schedule; `scripts/detect_changes.py` still reports them.
- Classification depends on what the authoring tool exports. These rules fit this Revit IFC. A Rhino model needs layer → category rules first.

## Validation

`pip install git+https://github.com/brunopostle/ifc4d-gantt` reads `scheduled_v1.ifc` independently. All 28 task dates and all 56 dependencies match PMI's `schedule.csv`.
