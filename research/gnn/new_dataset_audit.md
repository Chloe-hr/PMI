# Stage 3.7A: audit of the new BIM and scheduling datasets

*12 Nov 2026. Read-only audit: nothing in `data/raw/` was modified, and no model was trained. File-level details and measured sizes are in [`new_dataset_inventory.csv`](new_dataset_inventory.csv).*

## Summary

| Dataset | Independent projects | BIM ↔ activity link | Actual dates | Usable GNN label |
|---|---|---|---|---|
| **SCHEPENDOMLAAN** | **1 building** | **Yes**: 3,505 elements ↔ 73 tasks | **No** | Planned duration only; a weak binary "too late" flag for 8 tasks |
| Models and algorithm for construction scheduling | 0 projects (4 structural test frames + one algorithm) | No tasks | No | None (the precedence input file is missing) |
| 4D benchmark (`4DBenchmarkBim.ifc` + `Schedules.xlsx`, loose) | 1 benchmark building | Yes (151/151 GUIDs) | No | None (68 *planned* alternatives) |
| RWTH Restage (`Restage_IP_ALL_MULTI_001.ifc`, loose) | 1 | Yes (phase level) | Finish dates only | None (no start dates) |
| Cambridge (existing, Stage 2) | 299 project IDs in **169 conservative blocks** | No BIM | Reported on 258,352 activities | Exploratory elapsed days (0 verified) |
| Ghent (existing, Stage 3.5) | 53 projects in 17 groups | No BIM | Yes | Used; negative result |

**Bottom line:**
- SCHEPENDOMLAAN is the only dataset with a real link between BIM elements and activities, but it is **one building with no actual activity dates**. It cannot provide supervised duration or delay labels.
- The only dataset with enough independent projects for supervised GNN training is **Cambridge**, which has no BIM.

---

## 1. SCHEPENDOMLAAN

**Source.** The [openBIMstandards DataSetSchependomlaan](https://github.com/openBIMstandards/DataSetSchependomlaan) (README in the folder): a residential building in Nijmegen (NL), built in 2015. The data was collected for a TU Eindhoven master thesis (S. van Schaijk) with Hendriks Bouw en Ontwikkeling, ROOT, TNO and RAAMAC. Licence: CC BY 4.0. The README warns that *"some files contain some errors and therefore have to be treated carefully"*.

**Size.** 435 files, 4.8 GB. Most of the volume is point clouds (2.1 GB), subcontractor/coordination models (1.5 GB) and RDF duplicates of the IFCs.

### 1.1 Number of independent projects: **1**

Everything describes the same building:
- the design model;
- the Synchro as-planned model and its 6 weekly snapshots;
- subcontractor models, including revisions such as `GEELEN-Breedplaat V1/V2/V3`;
- the event logs and the point clouds.

Revisions and weekly states are **not** independent samples.

### 1.2 IFC/BIM models and element metadata

| Model | Schema | Elements | Metadata |
|---|---|---|---|
| `Design model IFC/IFC Schependomlaan.ifc` (ArchiCAD, ROOT) | IFC2X3 | 3,714 | 6 storeys (`-1 fundering` to `04 dak`), `BaseQuantities`, `ArchiCADQuantities`, materials, `Pset_*Common` |
| `As Planned models/IFC Schependomlaan incl planningsdata.ifc` (Synchro export) | IFC2X3 | 3,505 | 125 `IfcTask`, 1 `IfcWorkSchedule`, 73 `IfcRelAssignsToProcess`, 42 `IfcRelSequence` |
| 6 weekly snapshots (weeks 26, 27, 28, 29, 30, 37) | IFC2X3 | 854 → 3,505 | Same 125 tasks; the plan filtered by date |

The Synchro export changed the model structure, as the README documents:
- **Storeys** are flattened to a single `Storey-1`.
- **Property sets** are merged into one `SynchroResourceProperty`. Quantities and the ArchiCAD `Home Story` survive as flattened keys such as `[BaseQuantities[...]]GrossSideArea`.
- **GUIDs** were re-generated: none of the event-log GUIDs exist in the design IFC (0/3,505), while all of them exist in the Synchro export (3,505/3,505). Linking therefore has to go through the Synchro model. Design-model metadata can only be joined by element name (`liftputvloer_(#5715)`).

### 1.3 Planning files and formats
- `Planning/XML/Uitvoering Schependomlaan 18-02-2015.xml`: MS Project XML, the baseline dated 18 Feb 2015.
- `Planning/PDF/...pdf`: a printout of the same plan.
- `As Planned models/Synchro/*.sp`: the native Synchro project (proprietary, not parsed).

### 1.4 Activity identifiers and predecessor relationships
- **Size:** 157 XML tasks, of which 114 are named work tasks with duration > 0. The plan is flat, with no summary tasks.
- **Links:** only **48 predecessor links** (44 finish-to-start, 4 start-to-start). Only 68 of the 114 work tasks appear in any link.
- **Dates are mostly fixed by hand:** 103 tasks carry a "start no earlier than" constraint, so most dates are set directly rather than derived from logic. The network is sparse and partly disconnected.
- **IFC version:** the Synchro IFC has 42 sequences (41 FS, 1 SS).
- **Identifiers:** task IDs in the event logs and IFC have the form `ST00060` (Synchro `TaskId`).

### 1.5 Planned start and finish
- **Present** in the XML (start, finish, duration; 1–20 working days, median 2; 18 Feb – 17 Dec 2015; 8 h/day calendar).
- **Present** in the IFC `IfcScheduleTimeControl` (`ScheduleStart`/`ScheduleFinish` on all 125 tasks; early/late start on about 39).
- **Present** in the event logs (day resolution).

### 1.6 Actual start and finish: **absent**
- **XML:** no `ActualStart`/`ActualFinish`, and 0% complete on every task.
- **IFC:** no `Actual*` attributes in any `IfcScheduleTimeControl`.
- **"As-built" event log:** its `TaskStart`/`TaskFinish` are **identical** to the as-planned log on every matched row (100%).

### 1.7 As-planned / as-built comparison
`Comparison As Planned As Built/comparison_all weeks.xlsx` holds one sheet per scan week. Each lists the **elements planned but not observed** in that week's drone point cloud:

| Week | 26 | 27 | 28 | 29 | 30 |
|---|---|---|---|---|---|
| Elements missing | 9 | 50 | 89 | 18 | 4 |

That is 170 rows for 121 unique elements.
- **No dates:** the workbook gives presence/absence at five scan dates, not completion dates.
- **GUIDs don't match** the event logs (0/170 under either GUID column); matching works only by element name.
- **84 of the 121 elements are missing in only one scan.**
- **54 were flagged two weeks before their planned finish week.** "Missing" means "absent compared with Synchro's weekly snapshot", not "task finished late".

### 1.8 Event logs and progress records

| Log | Rows | Elements | Tasks | Content |
|---|---|---|---|---|
| As planned | 7,166 | 3,505 | 73 | element × task, planned start/finish |
| With as-built information | 3,661 real (+3,505 empty padding rows) | 2,358 | 72 | same dates + `Element on time or not` |
| With actors **FAKE** | 3,661 | 2,358 | 72 | + `Company`, `Actor`: **fabricated** per README → **exclude** |

`Element on time or not`: **On time 3,467 / Too late 194.** The "too late" rows cover **119 elements in only 8 tasks**:
- *Stelwerk buitengevel*
- *Plaatsen kozijnen* (×2)
- *Prefab betonband*
- *Metselwerk* (×2)
- *Lijmwerk kalkzandsteen*
- *Plaatsen scharnierkap*

**Provenance:** 191 of 194 "too late" rows match by name an element missing in the point-cloud comparison. The flag is therefore derived from the 5 weekly scans. "On time" is the default for everything not seen missing, including tasks planned in February–May and August–October, when no scan exists. It is **not** an observed on-time completion.

### 1.9 Can activities be linked to IFC elements? **Yes, this is the dataset's main asset.**
- **Two link sources:** the event log (GUID ↔ TaskID) and the Synchro IFC (`IfcRelAssignsToProcess`). Both are complete within the Synchro GUID space.
- **Element features** are available through the flattened Synchro property set: IFC class, NL-SfB code, material, quantities, home storey.

### 1.10 Can actual durations be reliably derived? **No.**
- There are no actual start or finish dates anywhere.
- The only as-built evidence is presence/absence at 5 weekly scans (weeks 26–30) for 121 elements.
- At most this gives interval-censored, week-resolution completion bounds for those elements. Even then, the snapshots compare against the planned model state, not task completion.

---

## 2. GNN feasibility on SCHEPENDOMLAAN

| Task | Verdict | Reason |
|---|---|---|
| **A. Activity duration prediction** | **Only as "reproduce the planner's estimate"** | The only target is the *planned* duration of 114 tasks (73 linked to elements) in one project. Predicting it from quantities is a plan-reproduction exercise, not a forecast of real durations. With n = 1 project it cannot be evaluated for generalisation. |
| **B. Planned vs actual deviation** | **Unsupported** | No actual dates. The binary flag covers 8 late tasks out of 72, comes from 5 scans, treats unobserved elements as "on time" by default, and comes from a single project. |
| **C. BIM element → activity graph** | **Supported** | A complete bipartite graph: 3,505 elements ↔ 73 tasks, plus a sparse task precedence network (42–48 links), with element quantities, classes and materials. This is a **real, human-made BIM-to-schedule mapping**, which PMI has never had. |
| **D. Progress / change-impact prediction** | **Unsupported for training** | Progress: weekly presence/absence for 121 elements in one project. Change impact: the subcontractor model revisions (V1–V3) are undated and not linked to schedule changes. Usable only as a qualitative illustration. |

**Independence:** 1 project. The weekly snapshots, model revisions and event-log variants are views of the same building. Treating them as separate samples would be pseudo-replication.

---

## 3. "Models and algorithm for construction scheduling"

**Exact directory name:** `data/raw/Models and algorithm for construction scheduling/`. The files don't state a publication title. The script name `GA_mendeley.py` suggests a Mendeley Data deposit with the same title as the folder, but the dataset's own landing page and DOI aren't included, so the source should be confirmed before citing it.

**Contents** (5 files, 540 KB):
- **`GA_mendeley.py`** (read, not executed): a genetic algorithm that assigns each structural component to a day so that each comes after its predecessors.
  - Its fitness is the percentage of precedence constraints satisfied.
  - The input `fuza_mocc.csv`, a component precedence matrix ("matrix of component constraints"), is **not included**.
  - The outputs are Excel files of fitness-per-generation and day assignments.
- **4 Tekla Structures 2022 IFC2X3 steel frames:**
  - `out-simple`: 84 elements (42 assemblies, 24 beams, 18 columns)
  - `out-moderate`: 100
  - `out-complicated`: 264
  - `out-ultra complicated`: 40 elements (despite the name)

  None contains tasks, dates or properties beyond the Tekla defaults.

**Projects / labels:** 0 construction projects; these are 4 test geometries. There are no durations, dates or actuals. The only "label" the algorithm could produce is a synthetic feasible assembly order, and the precedence matrices needed to define it are missing.

**Relevance to the PMI GNN:** low for duration learning. A possible later use would be as test inputs for **element-level precedence / assembly-sequence** generation, if the precedence matrices can be obtained from the authors.

### Loose files found in `data/raw/` (arrived with the new data)
- **`4DBenchmarkBim.ifc` + `Schedules.xlsx`:** a 4D scheduling benchmark.
  - One 8-level building: 63 columns, 56 walls, 32 slabs.
  - **68 alternative planned schedules** (`Plan_S_0–5`, `Plan_D_*`), each with 151 element-level tasks and level, zone (A–D), contractor, crew and planned start/end. All GUIDs resolve in the IFC.
  - Durations are fixed by element type (column 1 d, wall 2 d, slab 5 d). No actuals.
  - **Useful as:** a sequencing/optimisation benchmark, or for testing PMI's task generator. **Not useful as:** duration labels.
- **`Restage_IP_ALL_MULTI_001.ifc`** (RWTH Aachen, Bonsai, IFC4, 190 MB): 4,346 elements linked to 12 phase-level tasks.
  - It has `ActualFinish` on 10 of the 12 tasks, but no start or planned dates, so durations can't be derived.
  - Useful only as a 4D visualisation example.

---

## 4. Compatibility with Ghent

| Aspect | SCHEPENDOMLAAN | Cambridge | Ghent |
|---|---|---|---|
| Activity definition | Trade tasks in Dutch (e.g. *Metselwerk*, *Stort*) | Anonymised WBS/activity text (UK) | Trade tasks in Dutch/English/French |
| Duration unit | Working days (8 h) | Naive elapsed **calendar** days; calendars referenced but not defined | Working time (8 h assumed) |
| Precedence | Sparse FS/SS; mostly date constraints | Exported `Activity_Relationships` (91% of activities) | FS/SS/FF/SF, ignored lags |
| Baseline | Genuine baseline (Feb 2015) | Planned dates **possibly revised** (Stage 2 audit) | Genuine baseline |
| Actual label | **None** | Reported timestamps, unverified | Tracking-period actual durations |

**Conclusions:**
- **SCHEPENDOMLAAN + Ghent:** the activity vocabulary and calendar are compatible: Dutch trade names, which `graph_schema.CATEGORIES` already covers, and working days. But there is **no label to combine**. The project can only be used for *inference* with a Ghent-trained model.
- **Cambridge + Ghent:** **do not pool training labels.**
  1. The units differ: calendar elapsed versus working time.
  2. Cambridge planned dates may already absorb delays, which leaks the target into the input; Ghent uses genuine baselines.
  3. The countries, eras and relationship encodings differ.

  A unit-free ratio (actual ÷ planned) roughly cancels the unit difference, but not the baseline-revision issue. Ghent can serve only as a **separate external test set**, reported on its own.
- **4D benchmark / Tekla frames / Restage:** synthetic or planned-only data. **Never** pool them as labels.

---

## 5. Recommendation

1. **Next supervised training dataset: Cambridge**, under the frozen Stage 2.3D protocol. It is the only option with enough independent groups (169 conservative blocks), predecessor relations and reported actuals. See [`training_recommendation.md`](training_recommendation.md).
2. **SCHEPENDOMLAAN: external case study, not training data.** Use it to:
   - (a) build PMI's first **real BIM-element → activity graph**;
   - (b) **validate PMI's rule-based task generation** (Stage 3.2) against a human-made Synchro plan;
   - (c) demonstrate inference with a trained model, clearly labelled as having no ground truth.
3. **Ghent:** keep it as the documented negative result and an optional external test set.
4. **Models/GA, 4D benchmark, Restage:** optional demonstration and benchmark material only.
