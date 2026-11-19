# Stage 4.0B - consolidated evidence package and Stage 5.1 validation handover

Generated 2026-11-19 13:16 UTC. Consolidates `section_A/` (accepted) and `sections_B_E/` without modifying them. Stage 5.6 remains **NO-GO**.

## 1. Evidence categories
| master_id | dataset | evidence_category | acquisition_status | provenance | licence |
|---|---|---|---|---|---|
| BE-D1 | BCCA - Base de Costes de la Construccion de Andalucia, Dic-2023 V02 | catalogue reference | Downloaded | verified | Junta de Andalucia portal: CC BY 3.0-type reuse; mandatory attribution "Informacion obtenida del Portal de la Junta de Andalucia"; no endorsement implied |
| BE-D2 | CERP Banco de items de construccion v0.11.0 (Spain bundle) | catalogue reference (derivative) | Downloaded | verified | Repo LICENSE: prices reused from public bases under Ley 37/2007 (RISP); attribution "Informacion obtenida del Portal de la Junta de Andalucia"; curation by CERP Tech (no SPDX licence) |
| BE-D3 | OEKOBAUDAT release 2024-III (full data-stock CSV export) | LCA/EPD database | Downloaded | verified | BMWSB: provided free of charge without restriction; free distribution of unmodified data permitted when source is named |
| BE-D4 | Project Portfolio Dataset (Thiele et al. 2020) | real project-control dataset (civil) | Downloaded | verified | CC BY 4.0 (dataset and article) |
| BE-D6 | DSLIB v3.4 (Ghent OR&S), buildings subset | real project schedules (no BIM) | Already available locally | verified | as recorded in prior PMI inventory (not re-audited in 4.0B) |
| BE-D7 | Cambridge JPF anonymised project data | real project schedules (no BIM, locked test protected) | Already available locally (not opened) | verified | as recorded in prior PMI work |
| BE-D8 | CYPE Generador de Precios (Spain) | catalogue reference (not acquired) | Manual download required | not acquired | Aviso legal: content protected; downloads only for personal, non-commercial use, not transferable to third parties |
| BE-D9 | ITeC BEDEC (construction + environmental) | catalogue + environmental reference (not acquired) | Restricted | not acquired | Subscription (monthly/annual); free trial 15 queries/month after registration; free student licence via ITeC school agreements |
| BE-D10 | EC3 / Building Transparency | EPD database (not acquired) | Restricted | not acquired | API requires authentication (HTTP 401 verified); free tier: no caching or redistribution; paid licence or written consent |
| BE-D11 | DDC CWICR open construction cost database | catalogue norms (unsuitable licence) | Unsuitable | not acquired | CC BY-NC 4.0 data + separate commercial licence |
| BE-D12 | Estimated-vs-actual labour hours (Kalasapudi et al. 2025, Frontiers Built Env.) | unavailable | Unavailable | not acquired | Data "made available by the authors" on request; no repository |
| A-SCH | DataSetSchependomlaan (Nijmegen, built 2015) | real project (BIM + planned schedule) | Already available locally (verified) | verified | CC BY 4.0 (README); repo NOASSERTION |
| A-CERT | buildingSMART Certification datasets | certification fixture | Already available locally (verified) | verified | see repository |
| A-SPEC | buildingSMART IFC4.x specification models | specification fixture | Already available locally (verified) | verified | see repository |
| A-SYN | PMI synthetic IFC writer outputs | synthetic fixture | Already available locally (verified) | internal synthetic | internal |
| A-TEK | Models and algorithm for construction scheduling (Tekla frames) | structural test model | Already available locally (verified) | open (P3) | unconfirmed |
| A-RST | RestageIFC v1.0.0 (RWTH Aachen) | demonstrator (real site) | Already available locally (verified) | verified | CC BY 4.0 |
| A-MEN | Mendeley BIM Spatial Models (fm9myphk9g v1) | authored BIM models (2) + vendor sample (1), built status undocumented | Already available locally (verified) | verified | CC BY 4.0 |
| A-B4D | 4D benchmark model (loose file, source undocumented) | benchmark model (quarantined) | Already available locally (verified) | QUARANTINED (P1) | unknown |

## 2. Stage 5 readiness
| stage | decision | change |
|---|---|---|
| 5.0 Hybrid architecture design | GO | unchanged |
| 5.1 BIM quantity extraction | CONDITIONAL GO | confirmed (Section A accepted) |
| 5.2 BIM-to-task generation | CONDITIONAL GO | evidence added; decision unchanged |
| 5.3 Engineering duration estimation | CONDITIONAL GO | unchanged |
| 5.4 Resource-constrained IFC4D scheduling | CONDITIONAL GO | evidence added; decision unchanged |
| 5.6 Supervised machine learning | NO-GO | maintained NO-GO |
| 5.7 Scenario optimization | CONDITIONAL GO | unchanged |

Full evidence: `stage5_readiness_matrix.csv`.

## 3. Master evidence coverage
| required_evidence | status | sections_B_E_status | changed_by_section_A | evidence |
|---|---|---|---|---|
| Genuine IFC geometry | Available | Available | evidence updated | SCH (real, built 2015) and RST (demonstrator) IFC geometry; Mendeley models (authored, build status undocumented); tessellation 862/862 sampled elements. |
| Element classifications | Available | Available | evidence updated | IFC classes audited in 160 files; caveat: SCH strip foundations are modelled as IfcBeam ("fund_strook"/"fund_opstort"); only RST has IfcFooting among real models. |
| Physical quantities | Partial | Partial | evidence updated | Authored NetVolume in SCH design (beams 174/174, slabs 278/279, walls 883/934), RST (footings 11/13, beams 22/191, walls 22/92); geometry-derived in Mendeley; reinforcement absent; formwork/excavation need assumptions. |
| Work-package definitions | Partial | Partial | no | D1 BCCA chapter/work-item structure provides RC work-item definitions with units; not a project WBS |
| Element-to-task mapping | Partial | Partial | evidence updated | SCH Synchro: 3,505 elements assigned to 125 planned tasks (one project); RST: 12 phase tasks (hierarchical, duplicated phases) with element assignment; no element-level task mapping in other real models. |
| Construction dependencies | Partial | Partial | evidence updated | SCH Synchro 42 IfcRelSequence + MS Project 48 links (planner-authored, one project); Thiele/DSLIB/Cambridge networks unlinked to IFC; Mendeley relations are geometric only. |
| Planned activity durations | Partial | Partial | evidence updated | SCH Synchro 125 tasks with planned start/finish (working-day calendar); B-E sources unlinked to IFC. |
| Actual activity durations | Missing | Partial | yes | No source has activity actual start and finish linked to IFC. RST: ActualFinish only, entered in an ACTUAL work schedule created 2026-07-01 during dataset compilation (all at 18:00) - not independently verified activity records. |
| Labor productivity | Partial | Partial | no | D1 catalogue person-h per unit for 17 of 18 targets (estimates); D4 civil production rates; no observed RC field productivity |
| Equipment productivity | Partial | Partial | no | D1 equipment-h per unit (vibrator, backhoe, loader, roller); D4 civil plant |
| Crew composition | Missing | Missing | no | No source states crew headcount for RC items; D1 lists trades only; D6 resource availability is project-specific |
| Resource constraints | Partial | Partial | no | D6 renewable resource availability; D4 resources sheet; none for Spanish RC projects |
| Construction calendars | Partial | Partial | no | D4 Queensland non-work calendar 2011-2015; D6 Agenda sheets; no Spanish/Catalan calendar acquired |
| Material unit costs | Available | Available | no | D1 5,631 material prices (EUR, Andalucia, dated per concept) |
| Labor and equipment costs | Available | Available | no | D1 36 labour rates (e.g. Of.1a 23.17 EUR/h, peon esp. 22.01 EUR/h) and 71 machinery prices |
| Environmental coefficients | Partial | Partial | no | D3 GWP per module for 10 of 13 target groups; no formwork systems, diesel fuel; 2 Spanish concrete EPDs only; BEDEC/EC3 not acquired |
| Genuine design revisions | Missing | Missing | evidence updated | SCH weekly snapshots carry the identical 125 tasks and planned dates as the full model; their elements are subsets (854 -> 3,505) - progressive model states of one plan, not design or schedule revisions. SCH subcontractor versions (e.g. GEELEN Breedplaat V1-V3) exist but are not aligned revision pairs. |
| Corresponding schedule revisions | Missing | Missing | evidence updated | Single baseline per project (SCH 18-02-2015); no revision pairs. |
| Independent validation projects | Partial | Partial | evidence updated | Real-project validation: SCH (development) and RST (independent demonstrator). Mendeley models are robustness cases; 4D benchmark quarantined. |
| Reinforcement quantities | Missing | (not assessed) | new row | No IfcReinforcingBar/Mesh or reinforcement weights in any real model; only fixtures (35 bars) and one SCH subcontractor model (6 bars). |
| Material-specific concrete volume | Partial | (not assessed) | new row | Element volume available/derivable; concrete share requires material-layer split (e.g. SCH prefab floor layer set: concrete 0.20 m of 0.333 m = 0.6006). Aerated-concrete masonry (cellenbeton, 蒸压加气混凝土砌块) must be excluded from cast concrete. |

## 4. Stage 5.1 validation handover
`stage5_1_validation_manifest.csv` lists all 160 local IFC files with role, provenance, SHA-256, schema, classes, units, overrides, authored and geometry coverage, layer limitations, GlobalId issues and exporter restrictions. Key models:
| model_key | validation_role | eligible_for_real_project_claims | ifc_schema | length_unit | mass_unit | explicit_quantity_unit_overrides | duplicate_globalids | provenance_status |
|---|---|---|---|---|---|---|---|---|
| B4D | QUARANTINED - internal software testing only | no | IFC4 | MILLIMETRE | KILOGRAM | 0 of 961 IfcPhysicalSimpleQuantity | 0 | QUARANTINED (P1) |
| MEN-MTG | geometry extraction and robustness (not a verified construction project) | no | IFC2X3 | METRE | KILOGRAM | 0 of 0 IfcPhysicalSimpleQuantity | 0 | verified |
| MEN-RES | geometry extraction and robustness (not a verified construction project) | no | IFC2X3 | MILLIMETRE | KILOGRAM | 0 of 0 IfcPhysicalSimpleQuantity | 0 | verified |
| MEN-RAC | geometry robustness - vendor sample (not a project) | no | IFC2X3 | MILLIMETRE | KILOGRAM | 0 of 0 IfcPhysicalSimpleQuantity | 0 | verified; third-party |
| RST | independent demonstrator validation | yes (demonstrator) | IFC4 | METRE | KILOGRAM | 0 of 1737 IfcPhysicalSimpleQuantity | 0 | verified |
| SCH-synchro | interoperability test - same project as SCH-design (NOT independent) | no (same project) | IFC2X3 | MILLIMETRE | GRAM | 0 of 0 IfcPhysicalSimpleQuantity | 0 | verified |
| SCH-design | development | yes (one real project) | IFC2X3 | MILLIMETRE | GRAM | 0 of 153815 IfcPhysicalSimpleQuantity | 1 | verified |
| SYN | controlled software testing only - synthetic | no (excluded from real-project claims) | IFC4 | METRE | not declared | not checked | 0 | internal |
| SYN | controlled software testing only - synthetic | no (excluded from real-project claims) | IFC4 | METRE | not declared | not checked | 0 | internal |
| SYN | controlled software testing only - synthetic | no (excluded from real-project claims) | IFC4 | METRE | not declared | not checked | 0 | internal |

## 5. Resolved ambiguities
| topic | resolution |
|---|---|
| Mendeley name linkage | Earlier statement "99-100%" was overstated. Exact IfcElement name matches 92.9-100%; unique matches 91.8-98.8%; ambiguous names 19-81 per CSV (standing for 57-580 IFC elements); remaining names match IfcSpace/other products. Only unique matches may serve as element identities. |
| Element vs concrete volume | Element volume includes every material layer; concrete volume = concrete-layer share (e.g. SCH prefab floor 0.6006) and excludes aerated-concrete masonry. Values in the plan are labelled DERIVED. |
| Tessellation vs closed geometry | Tessellation succeeded for all sampled elements, but an edge-manifold test found open/non-manifold meshes (in this plan: 1 of 40; Synchro export elements with 3-28 bad edges in the earlier sample). Tessellation does not establish closed geometry or correct construction quantities. |
| Authored-volume agreement vs independent validation | 251/251 geometry-vs-authored agreement within 2% shows internal consistency of exporter output; both values may derive from the same geometry. Independent validation requires the manual calculations in quantity_validation_plan.csv. |
| SCH weekly snapshots | All six weekly files carry the identical 125 tasks with identical planned dates as the full Synchro model (task GUIDs regenerated per export) and element subsets of it (854-3,505). They are progressive model states of one baseline, not design or schedule revisions. |
| Restage finish dates | IfcTaskTime.ActualFinish on 11/12 tasks in an IfcWorkSchedule of PredefinedType ACTUAL created 2026-07-01 by "unknown user" during dataset compilation; all at 18:00; no ActualStart; hierarchical phases with duplicates. Dataset text calls them "actual completion times"; they are retrospectively entered phase completion dates, not independently verified activity records. |
| SCH design <-> Synchro identity | GUIDs not preserved; 3,228/3,505 Synchro elements resolve to a same-named design element through the name suffix "_(#STEP id)"; 73 change IFC class; 277 have no suffix. Export-specific key, not a persistent identifier. |

### Mendeley linkage detail
| project | csv | distinct_csv_names | exact_ifcelement_name_match | exact_pct | unique_match | unique_pct | ambiguous_match | ambiguous_ifc_elements_behind | matches_non_element_product |
|---|---|---|---|---|---|---|---|---|---|
| BIM_meeting_room_data | ifc_space_centroids_data.csv | 1770 | 1644 | 92.9 | 1625 | 91.8 | 19 | 57 | 126 |
| BIM_meeting_room_data | spatial_relationships_detailed.csv | 1596 | 1594 | 99.9 | 1575 | 98.7 | 19 | 57 | 2 |
| BIM_residential_building_data | ifc_space_centroids_data.csv | 6715 | 6715 | 100.0 | 6634 | 98.8 | 81 | 580 | 0 |
| BIM_residential_building_data | spatial_relationships_detailed.csv | 6714 | 6714 | 100.0 | 6633 | 98.8 | 81 | 580 | 0 |
| rac_advanced_sample_project_data | ifc_space_centroids_data.csv | 5789 | 5643 | 97.5 | 5600 | 96.7 | 43 | 124 | 146 |
| rac_advanced_sample_project_data | spatial_relationships_detailed.csv | 5656 | 5540 | 97.9 | 5502 | 97.3 | 38 | 114 | 116 |

### SCH weekly snapshots
| file | tasks | identical_task_names_and_planned_dates_to_full_model | task_guids_shared_with_full_model | elements | element_names_subset_of_full | tasks_with_actual_dates |
|---|---|---|---|---|---|---|
| IFC Schependomlaan incl planningsdata.ifc | 125 | True | 125 | 3505 | True | 0 |
| Week 26 26 june IFC Schependomlaan incl planningsdata.ifc | 125 | True | 0 | 854 | True | 0 |
| Week 27 3 july IFC Schependomlaan incl planningsdata.ifc | 125 | True | 0 | 1025 | True | 0 |
| Week 28 10 july IFC Schependomlaan incl planningsdata.ifc | 125 | True | 0 | 1552 | True | 0 |
| Week 29 17 july IFC Schependomlaan incl planningsdata.ifc | 125 | True | 0 | 1690 | True | 0 |
| Week 30 24 july IFC Schependomlaan incl planningsdata.ifc | 125 | True | 0 | 1722 | True | 0 |
| Week 37 11 sept IFC Schependomlaan incl planningsdata.ifc | 125 | True | 0 | 3505 | True | 0 |

### Restage tasks
| name | identification | task_time | assigned_products |
|---|---|---|---|
| ConstructionPhase_01 | 1 | {"ActualFinish": "2024-08-26T18:00:00"} | 2931 |
| ConstructionPhase_02 | 2 | {} | 0 |
| ConstructionPhase_03 | 3 | {"ActualFinish": "2025-05-05T18:00:00"} | 679 |
| SolarPanel | 3.1 | {"ActualFinish": "2025-05-09T18:00:00"} | 4 |
| Green Facade | 2.3 | {"ActualFinish": "2025-06-04T18:00:00"} | 135 |
| 3D-Printed Concrete Wall | 2.4 | {"ActualFinish": "2025-08-25T18:00:00"} | 67 |
| Underground Water Tank | 2.2 | {"ActualFinish": "2025-06-03T18:00:00"} | 6 |
| Concrete Slab Floor | 2.1 | {"ActualFinish": "2025-05-16T18:00:00"} | 2 |
| Bauabschnitt_02 | Module3 | {"ActualFinish": "2025-05-05T18:00:00"} | 679 |
| SolarPanel | Module3.1 | {"ActualFinish": "2025-05-09T18:00:00"} | 4 |
| Bauabschnitt_01 | Module1 | {"ActualFinish": "2024-08-26T18:00:00"} | 2931 |
| ConstructionPhase_04 | 4 | {"ActualFinish": "2025-08-08T18:00:00"} | 438 |

Work schedule: {"id": "2245748", "type": "IfcWorkSchedule", "GlobalId": "3pJefmWdb1yP0aCsXgEPcL", "Name": "Restage", "CreationDate": "2026-07-01T10:24:12.085341", "Creators": "(#2=IfcPerson($,'unknown','user',$,$,$,$,$),)", "StartTime": "2026-07-01T10:24:12.084954", "PredefinedType": "ACTUAL"}

## 6. Source provenance
| issue_id | record | status | action |
|---|---|---|---|
| P1 | data/raw/4DBenchmarkBim.ifc + data/raw/Schedules.xlsx | QUARANTINED (approved validation and redistribution) | Ask the authors / check the article data-availability section for the official repository and licence. Until then: internal software testing only, no validation claims, no redistribution. |
| P2 | SCHEPENDOMLAAN .../BIMsight Projectdata1/V_L_Constructief.ifc and .../ProjectData/V_L_Constructief.ifc | RESOLVED - provenance verified | Cite openBIMstandards/Archive-DataSetSchependomlaan as the source. No quarantine. |
| P3 | data/raw/Models and algorithm for construction scheduling/ (Tekla frames) | OPEN - citation unconfirmed | Fixture use only; confirm DOI before citing. |
| P4 | SCHEPENDOMLAAN licence | OPEN - minor | Cite README licence statement with attribution. |
| P5 | Mendeley rac_advanced_sample_project.ifc | OPEN - third-party content | Robustness testing only; do not redistribute the IFC. |

## 7. Independent quantity checks (proposed, not performed)
`quantity_validation_plan.csv`: 40 concrete elements (SCH-design 8, RST 8, MEN-RES 16, SCH-synchro 8). Each row gives identifiers, material classification, geometry representation, authored and DERIVED geometry quantities, measurement basis, the required manual calculation and limitations. `independent_manual_value_m3` is blank by design.

## 8. Remaining blockers
See `remaining_blockers.md` (includes Agent 2 coordination table).

## Deliverables
stage4_0b_consolidated_report.md / .html, master_dataset_inventory.csv, master_evidence_coverage_matrix.csv, stage5_1_validation_manifest.csv, quantity_validation_plan.csv, source_provenance_issues.csv, remaining_blockers.md, stage5_readiness_matrix.csv, preservation_verification.json; scripts/. Supporting data: data/processed/candidates/stage4_0b/consolidated/.
