# Stage 4.0B - Dataset acquisition and evidence audit (Sections B-E)

Generated 2026-11-19 12:23 UTC. Section A (BIM/spatial) is a separate task; checked 2026-11-19 12:23 UTC: data/raw/candidates/bim_spatial/ contains 0 files; no Section A deliverables in research/data_acquisition/stage4_0b/. Its outputs were not yet present, so this report covers Sections B-E and is stored in `research/data_acquisition/stage4_0b/sections_B_E/` for later consolidation.

## Executive summary
- **Downloaded:** BCCA Dic-2023 (Andalucia, BC3 + PDFs), CERP v0.11.0 (BCCA derivative), OEKOBAUDAT 2024-III full CSV, Thiele et al. 2020 project portfolio (8 workbooks, CC BY). 41 files hashed, 0 integrity failures.
- **Not acquired:** CYPE (licence: personal use; login for export), BEDEC (subscription), EC3 (authenticated API, no-caching terms) - see `manual_download_required.md`.
- **Productivity:** catalogue person-hours and equipment-hours per unit for 17 of 18 RC target items (curing bundled into concreting). These are **catalogue estimates**, not observed field productivity. No source gives crew sizes.
- **Cost:** BCCA direct unit costs reproduce from their decompositions to within +/-0.02 EUR.
- **Environment:** OEKOBAUDAT gives lifecycle-module-separated GWP for concrete, rebar, structural steel, timber, plywood, transport, electricity, site processes and waste; no formwork systems or diesel fuel; BCCA's eCO2 field is empty.
- **Project control:** Thiele 2020 is genuine and rich (plan network, production rates, planned vs actual cost accounts) but civil works, AUD, without activity actual dates or IFC linkage.
- **ML:** no dataset yields linked records for `log(actual/engineering)`. Stage 5.6 = NO-GO.

## Update: BCCA inner RAR (resumed)
The RAR passed the 7-Zip integrity test and was extracted to `data/raw/candidates/productivity/bcca_andalucia/extracted/BCCA23_V02_301023_rar/`. Four of five files are byte-identical duplicates of files already audited. The only new file, `BCCA2023_V02.Presto`, is a proprietary database of the same edition; a read-only byte scan found no environmental values or extra productivity/cost fields. **Readiness decisions are unchanged.** See `bcca_inner_rar_audit.csv`.

## Readiness decisions
| stage | decision | evidence |
|---|---|---|
| 5.0 Hybrid architecture design | GO | Evidence defines every module boundary: IFC input (D5), work-item catalogue with units and resource lines (D1), lifecycle-separated GWP (D3), planned networks and calendars as structural examples (D4, D6). The gaps (crew, calendars, revisions, ML labels) are known and can be represented as user inputs and optional modules. |
| 5.1 BIM quantity extraction | CONDITIONAL GO | D5 is a genuine IFC4 with 886 IfcElementQuantity sets, but extraction reliability has not been audited and Section A results are not yet available. Condition: Section A audit of quantity completeness and units across several independent IFCs. |
| 5.2 BIM-to-task generation | CONDITIONAL GO | D1 supplies RC work items with units (m3/m2/kg) matching IFC quantity types; D5 shows element-to-phase assignment. No source supplies element-level task mappings or RC dependency rules, so generation must be rule-based and engineer-approved. Condition: documented rule set reviewed by a PMI user. |
| 5.3 Engineering duration estimation | CONDITIONAL GO | Person-h/unit for 17 of 18 targets (D1, catalogue estimates, Andalucia). Missing: crew sizes, daily working hours, productivity adjustments, curing/striking times. Condition: these values entered and approved by a PMI user per project; outputs labelled as catalogue-based estimates. |
| 5.4 Resource-constrained IFC4D scheduling | CONDITIONAL GO | OR-Tools 9.15.6755 is installed in .venv-planning (Python 3.12.14). Dependency, calendar and resource data exist only as foreign examples (D4 Qld, D6 BE). Condition: user-supplied calendar, crew availability and RC sequencing rules; no learned dependencies. |
| 5.6 Supervised machine learning | NO-GO | No acquired dataset contains, for the same activity, an actual duration and the quantity + productivity + crew inputs required to compute an engineering duration in compatible units. D4 actuals are cost-account level and civil; D6/D7 lack quantities; D5 lacks durations. Target y=log(actual/engineering) cannot be computed without unlinked merging. |
| 5.7 Scenario optimization | CONDITIONAL GO | Cost coefficients: D1 direct unit costs reproduce exactly (Andalucia, EUR, mixed concept dates). Environmental: D3 A1-A3/A4/A5 GWP for concrete, steel, timber, transport, electricity, site processes. Condition: keep modules and A1/A2 standards separate, fill formwork/diesel gaps or exclude them, and report geographic mismatch. |

## Productivity reference coverage (BCCA, catalogue estimates)
| target_id | work_item | required_unit | source_code | source_unit | labour_h_per_unit_total | labour_h_per_unit_by_trade | equipment_h_per_unit | notes |
|---|---|---|---|---|---|---|---|---|
| T01 | Mechanical excavation | m3 | 02AVV00002 | m3 | 0.016 | PEÓN ESPECIAL=0.016 | RETROEXCAVADORA=0.02 |  |
| T01 | Mechanical excavation | m3 | 02PMM00002 | m3 | 0.12 | PEÓN ESPECIAL=0.12 | RETROEXCAVADORA=0.13 |  |
| T02 | Blinding concrete | m3 | 03WSS80000 | m2 | 0.125 | OFICIAL 2ª=0.05; PEÓN ESPECIAL=0.075 | none | BCCA measures blinding per m2 at 10 cm minimum thickness; target unit is m3. Not converted (thickness is a minimum, not a fixed value). |
| T03 | Foundation reinforcement | kg | 03ACC00011 | kg | 0.02 | OF. 1ª FERRALLISTA=0.02 | none |  |
| T04 | Foundation formwork | m2 | 03ERM00001 | m2 | 0.64 | OF. 1ª ENCOFRADOR=0.32; PEÓN ESPECIAL=0.32 | none |  |
| T05 | Foundation concreting | m3 | 03HAZ80020 | m3 | 0.45 | OFICIAL 2ª=0.05; PEÓN ESPECIAL=0.4 | VIBRADOR=0.13 |  |
| T05 | Foundation concreting | m3 | 03HAA00010 | m3 | 0.5 | PEÓN ESPECIAL=0.5 | VIBRADOR=0.2 |  |
| T06 | Column reinforcement | kg | 05HAC00015 | kg | 0.02 | OF. 1ª FERRALLISTA=0.02 | none | Generic structural rebar item; BCCA does not distinguish column/beam/slab reinforcement productivity. |
| T07 | Column formwork | m2 | 05HEM00001 | m2 | 0.35 | OF. 1ª ENCOFRADOR=0.25; PEÓN ESPECIAL=0.1 | none |  |
| T08 | Column concreting | m3 | 05HHP00003 | m3 | 0.6 | PEÓN ESPECIAL=0.6 | VIBRADOR=0.2 |  |
| T09 | Beam reinforcement | kg | 05HAC00015 | kg | 0.02 | OF. 1ª FERRALLISTA=0.02 | none | Generic structural rebar item; BCCA does not distinguish column/beam/slab reinforcement productivity. |
| T10 | Beam formwork | m2 | 05HEM00051 | m2 | 0.5 | OF. 1ª ENCOFRADOR=0.35; PEÓN ESPECIAL=0.15 | none |  |
| T11 | Beam concreting | m3 | 05HHJ00003 | m3 | 0.8 | OFICIAL 1ª=0.2; PEÓN ESPECIAL=0.6 | VIBRADOR=0.3 |  |
| T12 | Slab reinforcement | kg | 05HAC00015 | kg | 0.02 | OF. 1ª FERRALLISTA=0.02 | none | Generic structural rebar item; BCCA does not distinguish column/beam/slab reinforcement productivity. |
| T12 | Slab reinforcement | kg | 05HAM00010 | kg | 0.01 | OF. 1ª FERRALLISTA=0.01 | none |  |
| T13 | Slab formwork | m2 | 05HEM00101 | m2 | 0.75 | OF. 1ª ENCOFRADOR=0.55; PEÓN ESPECIAL=0.2 | none |  |
| T14 | Slab concreting | m3 | 05HHL00003 | m3 | 0.8 | OFICIAL 1ª=0.2; PEÓN ESPECIAL=0.6 | VIBRADOR=0.3 |  |
| T15 | Formwork removal | m2 | 05HED00001 | m2 | 0.18 | OF. 1ª ENCOFRADOR=0.03; PEÓN ESPECIAL=0.15 | none | Separate stripping item exists; BCCA formwork items (05HEM*) also include formwork work; check for double counting before use. |
| T16 | Concrete curing | time + technical conditions |  |  |  |  |  |  |
| T17 | Backfilling | m3 | 02RRM00001 | m3 | 0 |  | PALA CARGADORA=0.01; CAMIÓN CISTERNA=0.005; RULO VIBRATORIO=0.012 |  |
| T18 | Masonry installation | m2 | 06LHM00005 | m2 | 1.09635 | OF. 1ª ALBAÑILERÍA=0.7; PEÓN ESPECIAL=0.39635 | none |  |
| T18 | Masonry installation | m2 | 06BHH00020 | m2 | 0.60721 | OF. 1ª ALBAÑILERÍA=0.4; PEÓN ESPECIAL=0.20721 | none |  |

## Environmental coverage (OEKOBAUDAT 2024-III)
| target_id | material_or_process | source | datasets_found | declared_units | standard_split | spain_specific | status |
|---|---|---|---|---|---|---|---|
| E01 | Ready-mixed concrete by strength class | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 100 | 1 m3 (85); 1 qm (9); 1 kg (3); 1 m (2); 1000 kg (1) | A2=100 | yes | Available |
| E02 | Reinforcement steel (bar) | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 20 | 1 kg (19); 1000 kg (1) | A2=20 | no | Available |
| E03 | Reinforcement steel (mesh) | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 7 | 1 kg (5); 1000 kg (2) | A2=7 | no | Available |
| E04 | Structural steel | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 73 | 1000 kg (26); 1 m (24); 1 kg (19); 1 pcs. (3); 1 qm (1) | A2=73 | no | Available |
| E05 | Timber formwork (solid/structural timber) | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 21 | 1 m3 (21) | A2=21 | no | Available |
| E06 | Plywood / multi-ply formwork panels | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 7 | 1 m3 (7) | A2=7 | no | Available |
| E07 | Reusable formwork systems | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 0 |  |  | no | Not found in release |
| E08 | Construction-site processes (excavation, concrete pumping) | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 3 | 1 m3 (3) | A2=3 | no | Available |
| E09 | Material transportation (truck t*km) | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 4 | 1000 kgkm (4) | A2=4 | no | Available |
| E10 | Construction electricity | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 25 | 3.6 MJ (21); 1 qm (4) | A2=25 | no | Available |
| E11 | Diesel consumption (fuel) | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 0 |  |  | no | Not found in release |
| E12 | Construction waste (end of life) | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 3 | 1 kg (3) | A2=3 | no | Available |
| E13 | Masonry mortar | OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75) | 14 | 1000 kg (7); 1 kg (5); 1 m3 (2) | A2=14 | no | Available |
| ALL | all | BCCA 2023 V02 (BC3 ~X) | 0 |  |  |  | Schema only - no values |
| ALL | all | EC3 / Building Transparency | 0 |  |  |  | Restricted / Manual |
| ALL | all | ITeC BEDEC environmental indicators | 0 |  |  |  | Restricted (subscription) |
| ALL | all | CYPE Generador de Precios environmental tab | 0 |  |  |  | Manual / licence restricted |

### Lifecycle boundaries and what PMI can influence
- A1-A3 (production) changes with **design revisions, quantity increases and material substitution** (concrete class, rebar content, timber vs steel formwork).
- A4 (transport) changes with **supplier distance, mode and additional deliveries**.
- A5 (construction/installation) changes with **construction method, equipment usage (excavators, pumps), site energy and waste**; this is the module a schedule can influence (e.g. equipment idle hours, site electricity, formwork reuse cycles).
- B and C/D are largely independent of the construction schedule.
- Shorter duration does **not** automatically reduce embodied carbon: acceleration can add equipment, formwork sets or high-early-strength cement (higher A1-A3).
- EN 15804+A1 `GWP` and +A2 `GWPtotal` are different indicator definitions and are kept in separate columns.

## Project-control assessment
| field | thiele2020_D4 | dslib_D6 | restage_ifc_D5 |
|---|---|---|---|
| Project identifiers | Y: 8 workbooks P01-P06, P17, P18 | Y | Y (single project) |
| Activity identifiers | Y: Program Links WBS ids | Y | Partial: 12 phase tasks |
| Construction work-package classification | Partial: Portfolio WBS cost codes (civil) | Partial: WBS names | Partial: CON/TIM/STL naming |
| Planned start and finish dates | N at activity level (Program Links has duration only; MS Project template not part of dataset) | Y: Baseline Start/End | N |
| Actual start and finish dates | N: none found in any sheet | Partial: tracking periods | Partial: ActualFinish on 11/12 phases, no ActualStart |
| Planned durations | Y: Program Links Duration (unit not stated; Qld non-work calendar provided) | Y | N |
| Actual durations | N | Partial (tracking) | N |
| Physical construction quantities | Y: Model Inputs + Portfolio WBS planned qty (SQ) and final qty (AQ) | N | Y: 886 IfcElementQuantity |
| Labour hours | Partial: estimate labour lines with Prodn; actual hours only via cost lines with hr units | Partial: resource demand | N |
| Equipment hours | Partial: plant lines (P) with Prodn; actual plant cost lines | Partial | N |
| Crew information | Partial: named crews in Estimate (e.g. Stabilising Crew); no headcount per day | Partial: renewable resource availability | N |
| Planned costs | Y: BAC per cost account; tender budget | Y | N |
| Actual costs | Y: dated invoice/cost lines + final cost per account | Y (tracking AC) | N |
| Productivity measurements | Partial: planned production rates (estimate); actual rate derivable only per cost account (Final Rate) | N | N |
| Project characteristics | Y: article Table 1 (value, duration, type) | Y: project cards | Partial |
| Progress records | Y: monthly %complete claims and monthly AQ/AC/EV/PV | Y: EVM tracking periods | N |
| Schedule revisions | N: single baseline per project; scope variations only in revenue | N | N |
| Granularity | Task (plan); cost account (actuals); dated cost line | Activity | Element + phase |
| Independent IFC/BIM linkage | N | N | Y (internal to the IFC) |
| Supervised-learning target y=log(actual/engineering) | Not computable per activity: no actual activity durations; engineering duration requires matching quantity and crew per task, which are only at cost-account level | Actual vs planned durations exist but no quantities -> no engineering duration | No durations |

## Stage 4.0A limitation resolution
| stage4_0a_limitation | resolution | evidence |
|---|---|---|
| Mendeley MLP overfitting | Cannot be resolved through data acquisition alone | New data does not extend the 40-row Mendeley set; the architecture move away from project-level MLP is a design decision. |
| Unverified historical duration units | Unresolved | Mendeley and Cambridge units are not clarified by any acquired source; D4 Program Links duration unit is also not stated. |
| Lack of physical construction quantities in Cambridge GraphSAGE | Unresolved | No acquired dataset links quantities to Cambridge activities; merging unrelated data is not defensible. |
| Lack of crew and productivity features | Partially addressed | D1 supplies catalogue person-h/equipment-h per unit for RC items; crew sizes remain missing everywhere. |
| Weak generalization | Cannot be resolved through data acquisition alone | No new linked training records were found; generalization needs more independent projects with comparable targets. |
| Lack of independently verified actual duration labels | Unresolved | D4 has no activity actuals; D5 has phase finish dates only. |
| Limited independent project validation | Partially addressed | D4 adds 8 real projects (civil, not RC buildings); D5 one IFC demonstrator with phase finishes. |
| Missing relationships between BIM elements and construction activities | Partially addressed | D5 contains element-to-phase assignments (phase level only). |
| Limited evidence supporting cost predictions | Partially addressed | D1 gives reproducible reference unit costs (Andalucia); D4 gives planned vs actual cost accounts (civil, AUD). Reference prices are not outcomes. |
| Missing environmental evaluation data | Partially addressed | D3 provides GWP per lifecycle module for most target materials; formwork systems, diesel and Spanish-specific data gaps remain. |
| Missing resource-constrained scheduling information | Partially addressed | Calendars and resource availability examples exist (D4, D6), not for Spanish RC projects; crew sizes and site capacity must come from PMI users. |

## Combined evidence (Sections B-E; Section A pending)
| required_evidence | status | supporting_evidence |
|---|---|---|
| Genuine IFC geometry | Available | RestageIFC IFC4 (D5); other local IFCs belong to Section A |
| Element classifications | Available | IFC entity classes in D5 (IfcBeam 191, IfcWall 92, IfcSlab 12, IfcFooting 13; IfcColumn 0) |
| Physical quantities | Partial | D5: 886 IfcElementQuantity (extraction quality not yet audited; Section A); D4 civil quantities |
| Work-package definitions | Partial | D1 BCCA chapter/work-item structure provides RC work-item definitions with units; not a project WBS |
| Element-to-task mapping | Partial | D5: element-to-phase via 4,262 IfcRelAssignsToProduct (phase level only) |
| Construction dependencies | Partial | D4 (civil, 6-345 links per project), D6 (buildings), D7; none linked to IFC elements |
| Planned activity durations | Partial | D4 Program Links durations (unit not stated), D6 baseline durations; no RC-building plan linked to IFC |
| Actual activity durations | Partial | D6 tracking; D7 elapsed days (unverified unit semantics); D4 none; D5 finish dates only |
| Labor productivity | Partial | D1 catalogue person-h per unit for 17 of 18 targets (estimates); D4 civil production rates; no observed RC field productivity |
| Equipment productivity | Partial | D1 equipment-h per unit (vibrator, backhoe, loader, roller); D4 civil plant |
| Crew composition | Missing | No source states crew headcount for RC items; D1 lists trades only; D6 resource availability is project-specific |
| Resource constraints | Partial | D6 renewable resource availability; D4 resources sheet; none for Spanish RC projects |
| Construction calendars | Partial | D4 Queensland non-work calendar 2011-2015; D6 Agenda sheets; no Spanish/Catalan calendar acquired |
| Material unit costs | Available | D1 5,631 material prices (EUR, Andalucia, dated per concept) |
| Labor and equipment costs | Available | D1 36 labour rates (e.g. Of.1a 23.17 EUR/h, peon esp. 22.01 EUR/h) and 71 machinery prices |
| Environmental coefficients | Partial | D3 GWP per module for 10 of 13 target groups; no formwork systems, diesel fuel; 2 Spanish concrete EPDs only; BEDEC/EC3 not acquired |
| Genuine design revisions | Missing | No dataset with genuine model revisions found in Sections B-E |
| Corresponding schedule revisions | Missing | D4/D6 single baselines; no revision pairs |
| Independent validation projects | Partial | D4 8 civil projects (different domain); D6 buildings (no quantities); no independent RC-building project with IFC + actual schedule |

## Productivity feasibility
`Labour hours = quantity x labour h per unit` is supported for the targets above, with the IFC quantity unit matching the BCCA unit except blinding (m2 vs m3). `Productive duration = labour hours / effective crew-hours per day` needs crew size and working hours, which no acquired source provides. Parallel activities, curing and striking waits, equipment availability and calendars must come from PMI users or approved rules. Nothing was implemented in this stage.

## Recommended next steps
1. Wait for Section A, then consolidate into a single `research/data_acquisition/stage4_0b/` set.
2. Obtain a BEDEC student licence for Barcelona prices and environmental indicators; seek CYPE written permission.
3. Define the PMI user-input schema (crew, calendar, adjustment factors, curing/striking) before Stage 5.3.
4. Keep Stage 5.6 closed until linked RC records with actual activity dates are found or collected.

## Deliverables
All in `research/data_acquisition/stage4_0b/sections_B_E/`: download_manifest.csv, download_log.md, dataset_inventory.csv, dataset_eligibility_matrix.csv, manual_download_required.md, productivity_reference_coverage.csv, cost_reference_coverage.csv, environmental_reference_coverage.csv, project_control_coverage.csv, combined_evidence_matrix.csv, training_data_gap_analysis.md, stage4_0a_limitation_resolution.csv, readiness_decisions.csv, stage4_0b_report.md, stage4_0b_report.html, preservation_verification.json. Scripts in `scripts/`.
