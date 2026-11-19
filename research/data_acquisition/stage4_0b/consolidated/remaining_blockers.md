# Stage 4.0B - remaining blockers

Generated 2026-11-19 13:16 UTC. Stage 5.6 remains **NO-GO**.

## Blocking Stage 5.1 release on real models
1. **Independent manual quantity checks not performed.** `quantity_validation_plan.csv` (40 concrete elements from SCH design, RestageIFC, MEN-RES and the SCH Synchro export) needs an engineer's independent calculations and agreed tolerances. No ground truth was generated.
2. **Reinforcement mass unavailable** in every real model (category D). Needs a structural/rebar model or user-entered design values labelled as assumptions.
3. **Formwork contact area** requires approved face rules per element type and construction method (category C).
4. **Excavation and backfill** require site/ground data (category C/D).
5. **Material-specific concrete volume** requires layer splitting and exclusion of aerated-concrete masonry; element volume must not be reported as concrete volume.
6. **Only two real projects** (SCH, RST); RST quantity coverage is partial (slabs 0/12, beams 22/191).

## Blocking later stages
- **Revision release (5.5):** no aligned revision pair; GlobalIds not persistent across SCH exports.
- **Stage 5.6 ML:** no IFC-linked actual activity durations; RST ActualFinish values were entered in an ACTUAL work schedule created 2026-07-01 during dataset compilation (all 18:00), phases duplicated (Bauabschnitt_01 = ConstructionPhase_01; Bauabschnitt_02 = ConstructionPhase_03) - not verified activity records.
- **Catalogue/licensing (from B-E):** BEDEC subscription, CYPE licence, EC3 API terms; crew sizes, calendars, curing/striking times must come from users.

## Provenance
See `source_provenance_issues.csv`: 4DBenchmark + Schedules.xlsx **quarantined** (P1); V_L_Constructief **resolved** (P2); Tekla frames, SCH licence, Autodesk sample terms open (P3-P5).

## Coordination notes for Agent 2 (research/architecture/stage5_0 - read only, not modified)
| Agent 2 release requirement (implementation_roadmap.md step 3) | Status | Evidence |
|---|---|---|
| Multiple independent authorised models | Partial | Two real projects (SCH development, RST independent demonstrator), both CC BY 4.0; Mendeley adds robustness cases only; 4D benchmark quarantined. |
| Audited IFC versions | Met | 160 files: schema, exporter, application recorded (section_A/ifc_schema_summary.csv). |
| Unit assignment and overrides | Met | Units declared in all key models; 0 explicit IfcPhysicalSimpleQuantity unit overrides in the 7 key models; SCH mass in GRAM. |
| Class / zone / material coverage | Partial | Class and material coverage audited; IfcZone/work-zone assignment NOT audited; storeys flattened in Synchro export. |
| Manually checked gross/net volume, area and mass | Not met | quantity_validation_plan.csv lists 40 elements; no manual calculation performed yet. |
| Known missing data | Met | Reinforcement, formwork rules, excavation/backfill, actual durations documented. |
| Geometry/quantity agreement | Met (consistency only) | 251/251 within 2%; open/non-manifold meshes found in Synchro export. |
| Documented exporter quirks | Met | exporter_restrictions column of stage5_1_validation_manifest.csv. |
| Unit-test cases: explicit quantity-unit override, imperial units (roadmap step 4) | Fixture needed | No explicit IfcPhysicalSimpleQuantity unit override and no imperial project units in the 7 key real models; these cases must come from synthetic or specification fixtures. |
| Aligned revision pair and GlobalId persistence | Not met | No genuine revision pair. SCH design->Synchro GUIDs not persistent (linkable only via name suffix "_(#STEP id)"); weekly snapshots are not revisions. |

- `QuantityRecord.method` has no value for quantities flattened into property keys by an exporter (SCH Synchro); suggested mapping: `ifc_quantity` with `basis` naming the flattened key, or a new enum value - Agent 2 to decide.
- `risk_and_assumption_register.csv` R01 "Section A pending" can be updated by Agent 2 to reference `research/data_acquisition/stage4_0b/consolidated/`.
- Release thresholds: manual-check tolerances are still to be agreed with the engineering owner (as Agent 2's validation_strategy.md requires).
