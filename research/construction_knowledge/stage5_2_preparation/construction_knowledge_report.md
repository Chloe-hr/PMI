# Stage 5.2 preparation - reinforced concrete construction knowledge (research only)

Generated 2026-11-19 17:05 UTC. **Not a Stage 5.2 production module.** Every rule, mapping and assumption is **PENDING engineering approval** (`engineering_approval_register.csv`, 75 items). Work stops at the approval gate.

## Evidence vocabulary
| Status | Meaning |
|---|---|
| VERIFIED_REFERENCE | Copied/recomputed from a cited file (BCCA 2023 BC3, IFC models) |
| OBSERVED | Seen in one real project plan (SCHEPENDOMLAAN Synchro export) - an example, not a rule |
| PROPOSED_RULE | Auditor proposal - pending approval |
| ASSUMPTION | Explicit assumption - pending approval, never applied automatically |
| UNAVAILABLE | No evidence located - dependent activity blocked |

## Task A - manual quantity validation
- Workbook `research/validation/stage5_1_manual/manual_quantity_validation.xlsx`: 40 elements, sheets Instructions / Validation_40 / Initial_subset / Categories / Lists. Independent measurement, tolerance and approval fields are empty.
- Geometry categories: A simple homogeneous 17, B layered 2, C irregular 20, D invalid mesh 1.
- Initial subset: 11 category-A elements (`initial_validation_subset.csv`) covering SCH strip foundation, RestageIFC footing, and MEN-RES column/beams/slabs/walls.
- Measurement workflow: `measurement_guide.md` (Bonsai/FreeCAD share IfcOpenShell geometry and are not independent of the DERIVED values).

## Task B - construction work item library
29 work items; automatic work-package eligibility: {'BLOCKED': 18, 'CONDITIONAL': 11}. No item is automatically eligible without approval.
| activity_id | work_item | bcca | unit | labour_h | cost | eligibility |
|---|---|---|---|---|---|---|
| EXC-BULK | Bulk excavation (vaciado), mechanical | 02AVV00002 | m3, BCCA "medido el volumen en perfil natural" | 0.016 | 1.39 | BLOCKED - no excavation geometry in any real IFC |
| EXC-TRENCH | Trench excavation for strip foundations, mechanical | 02ZMM00002 | m3, perfil natural | 0.11 | 6.59 | BLOCKED until site inputs and approved width rule exist |
| EXC-PIT | Pit excavation for pad footings, mechanical | 02PMM00002 | m3, perfil natural | 0.12 | 9.41 | BLOCKED until site inputs exist |
| BLD | Blinding concrete (hormigon de limpieza) 10 cm min. | 03WSS80000 | m2 at 10 cm minimum thickness (BCCA measures area, not volume) | 0.125 | 13.04 | CONDITIONAL - area derivable from validated footprint; requires approval |
| FND-REBAR | Foundation reinforcement B500S | 03ACC00011 | kg nominal weight | 0.02 | 1.52 | BLOCKED - no reinforcement data in any real model |
| FND-FORM | Foundation formwork, timber (includes stripping) | 03ERM00001 | m2 of formed surface | 0.64 | 20.01 | BLOCKED until formwork face rules are approved (category C) |
| FND-CONC-PAD | Pad footing concrete HA-25 (includes vibration and curing) | 03HAZ80020 | m3 theoretical volume | 0.45 | 110.18 | CONDITIONAL - volume from authored or validated geometry |
| FND-CONC-STRIP | Strip foundation / grade beam concrete HA-25 (includes vibration and curing) | 03HAA00010 | m3 | 0.5 | 111.38 | CONDITIONAL - only after foundation classification is approved |
| COL-REBAR | Column reinforcement B500S | 05HAC00015 | kg | 0.02 | 1.52 | BLOCKED - no reinforcement data |
| COL-FORM | Column formwork, timber (stripping separate) | 05HEM00001 | m2 | 0.35 | 16.16 | BLOCKED until face rules approved |
| COL-CONC | Column concrete HA-25 (includes vibration and curing) | 05HHP00003 | m3 | 0.6 | 113.58 | CONDITIONAL - volume available/derivable |
| BEAM-REBAR | Beam reinforcement B500S | 05HAC00015 | kg | 0.02 | 1.52 | BLOCKED - no reinforcement data |
| BEAM-FORM | Beam formwork, timber (stripping separate) | 05HEM00051 | m2 | 0.5 | 16.23 | BLOCKED until face rules approved |
| BEAM-CONC | Beam concrete HA-25 (includes vibration and curing) | 05HHJ00003 | m3 | 0.8 | 118.4 | CONDITIONAL |
| SLAB-REBAR | Slab reinforcement bars / mesh | 05HAC00015 | kg | 0.02 | 1.52 | BLOCKED - no reinforcement data |
| SLAB-FORM | Slab formwork, timber (stripping separate) | 05HEM00101 | m2 | 0.75 | 21.42 | BLOCKED until face rules approved |
| SLAB-CONC | Slab concrete HA-25 (includes vibration, curing, service openings) | 05HHL00003 | m3 | 0.8 | 118.57 | CONDITIONAL |
| SLAB-COMPOSITE | Composite one-way floor system (joists + blocks + topping; all-in m2 item) | 05FUW80040 | m2 | 1.24 | 62.17 | BLOCKED unless system type is user-confirmed |
| SLAB-PRECAST | Precast floor units (hollow-core "kanaalplaat", filigree "breedplaat") + topping | UNAVAILABLE | m2 / m3 |  |  | BLOCKED - no catalogue reference (UNAVAILABLE) |
| WALL-FORM | RC wall formwork, timber (stripping separate) | 05HEM00151 | m2 | 0.5 | 15.65 | BLOCKED until face rules approved |
| WALL-CONC | RC wall concrete HA-25 | 05HHM00003 | m3 | 0.55 | 112.72 | CONDITIONAL |
| CURE | Concrete curing and strength development | UNAVAILABLE | time + technical conditions |  |  | CONDITIONAL - schedule constraint requires approved duration/criterion |
| FRM-STRIP | Formwork removal (desencofrado) for 05HEM* formwork | 05HED00001 | m2 of useful formwork | 0.18 | 4.0 | BLOCKED until striking criteria approved |
| BACKFILL | Backfill with excavated soil, mechanical, compacted | 02RRM00001 | m3, BCCA "medido el volumen en perfil compactado" | 0 | 1.36 | BLOCKED - excavation not available |
| MAS-BRICK | Hollow brick masonry (1 pie) | 06LHM00005 | m2 "medida deduciendo huecos" | 1.09635 | 43.91 | CONDITIONAL - area authored in SCH; derivable elsewhere with face rule |
| MAS-BLOCK | Hollow concrete block masonry 15 cm | 06BHH00020 | m2 | 0.60721 | 24.42 | CONDITIONAL |
| MAS-SANDLIME | Sand-lime (silico-calcareous) brick masonry, face work | 06LEC80100 | m2 | 0.90869 | 34.34 | CONDITIONAL - reference applicability requires approval |
| MAS-AAC | Aerated-concrete block masonry (cellenbeton / 加气混凝土砌块) | UNAVAILABLE | m2 |  |  | BLOCKED - no catalogue reference (UNAVAILABLE) |
| STEEL-COL | Structural steel columns (out of RC scope) | 05ACS00000 | kg | 0.04 | 2.11 | BLOCKED for RC work packages |

BCCA coefficients are catalogue estimates (Andalucia, Dic-2023), not observed productivity. Trades only - no crew sizes.

### Classification rules (IFC class never decides alone)
| rule_id | rule | observed |
|---|---|---|
| CR01 | Material category is the first discriminator; IFC class alone never selects a work item | MEN-RES Beam cast_in_place_concrete=355; MEN-RES Beam other_material=218; MEN-RES Column cast_in_place_concrete=766; MEN-RES Column other_material=242; MEN-RES  |
| CR02 | Aerated-concrete blocks are masonry (MAS-AAC), never cast concrete | MEN-RES Wall=534; SCH-design Wall=6 |
| CR03 | Concrete block / CMU is masonry | none observed |
| CR04 | Precast concrete routes to precast installation, not cast-in-place items | SCH-design Beam=4; SCH-design Slab=102 |
| CR05 | Explicit cast-in-place concrete routes to RC rebar/formwork/concrete items | MEN-RES Beam=355; MEN-RES Column=766; MEN-RES Slab=232; MEN-RES Wall=536; SCH-design Beam=82; SCH-design Slab=7 |
| CR06 | Concrete with unstated method requires user confirmation before routing | RST Footing=11; RST Wall=5; SCH-design Slab=6 |
| CR07 | Steel elements are excluded from RC work packages | RST Beam=169; SCH-design Beam=88; SCH-design Column=23 |
| CR08 | Timber elements are excluded from RC work packages | MEN-RES Slab=120; RST Beam=22; RST Slab=10; RST Wall=4; SCH-design Wall=51 |
| CR09 | Masonry (brick, sand-lime) routes to masonry items by material | SCH-design Wall=549 |
| CR10 | Elements without material are blocked from work-package generation | RST Footing=2; RST Slab=2; RST Wall=60; SCH-design Wall=4 |
| CR11 | Foundation detection is NOT class-based: IfcBeam/IfcSlab/IfcWall with foundation name or foundation storey are foundation CANDIDATES | MEN-RES Slab (name, cast_in_place_concrete)=1; SCH-design Beam (name, cast_in_place_concrete)=71; SCH-design Beam (storey only, cast_in_place_concrete)=11; SCH- |
| CR12 | IfcFooting is a foundation but its type (pad/strip/pile cap) needs PredefinedType or geometry confirmation | RST Footing concrete_method_unstated=11; RST Footing no_material=2 |
| CR13 | Slab on grade vs suspended slab decides whether slab formwork applies | not evaluated |
| CR14 | Spatial adjacency (IfcRelConnects*, Mendeley spatial relations) never creates a classification or precedence | n/a |
| CR15 | Exporter-specific: SCH Synchro elements are classified through their design-model element (name suffix "_(#STEP id)") | Stage 4.0B consolidation |

Foundation candidates observed (CR11): | model | ifc_class | foundation_evidence | material_category | elements | example |
|---|---|---|---|---|---|
| MEN-RES | IfcSlab | name | cast_in_place_concrete | 1 | 基础底板:500mm 基础底板:809773 @ B02-9.450 |
| SCH-design | IfcBeam | name | cast_in_place_concrete | 71 | liftputwand @ -1 fundering |
| SCH-design | IfcBeam | storey only | cast_in_place_concrete | 11 | liftputwand @ -1 fundering |
| SCH-design | IfcSlab | storey only | cast_in_place_concrete | 1 | liftputvloer @ -1 fundering |
| SCH-design | IfcWall | storey only | masonry | 50 | opgaand werk @ -1 fundering |


### Double counting
| risk_id | risk | control | severity |
|---|---|---|---|
| DC01 | Foundation formwork 03ERM00001 already includes stripping ("aplicacion del desencofrante, desencofrado") | Never add 05HED00001 to 03ERM*/03ERT* items | High |
| DC02 | Column/beam/slab/wall formwork 05HEM* mention only release agent ("desencofrante") - stripping is a separate item | Add FRM-STRIP exactly once per 05HEM* area | High (under-count risk) |
| DC03 | All concrete items include vibration and curing ("vibrado y curado") | Curing is a schedule constraint only; no cost/labour line | High |
| DC04 | Composite floor items (05FUA*, 05FUW*, 05FWW*) include concrete, reinforcement, mesh, formwork, props, stripping, vibration and curing | Mutually exclusive per slab | Critical |
| DC05 | Generic rebar item 05HAC00015 is shared by column, beam and slab reinforcement | Allocate each kg of reinforcement to exactly one element | Medium |
| DC06 | Beam/slab overlap: beam volume may include slab depth | Approved measurement rule (deduct at T-beams or not); check IFC geometry overlap | High |
| DC07 | Column height through slab | Approved rule (clear height vs through) | High |
| DC08 | Layered elements: element volume includes insulation/screed | Use concrete layer only (e.g. SCH prefab floor fraction 0.6006) | High |
| DC09 | SCH design and Synchro models describe the same elements | Use one model per project version; link via STEP-id suffix | Critical |
| DC10 | Weekly snapshot models contain subsets of the same elements | Never aggregate snapshots | Critical |
| DC11 | Strip foundations as IfcBeam could be counted as both beam and foundation | Foundation classification (CR11) excludes element from BEAM-* items | High |
| DC12 | Excavation (bank) and backfill (compacted) on different bases | Convert only with approved factors | Medium |
| DC13 | Blinding bottom cleaning: concrete items include "limpieza de fondos" | No separate cleaning item | Low |
| DC14 | Masonry measured net of openings ("deduciendo huecos") | Use NetSideArea or deduct openings | Medium |


## Task C - dependency rules (all PENDING, no universal durations)
| rule_id | predecessor | successor | rule | alternatives | evidence |
|---|---|---|---|---|---|
| DR01 | EXC-BULK/EXC-TRENCH/EXC-PIT | BLD/FND-* | Excavation of the same zone before blinding/foundation work | Staged excavation per zone; piled foundations (piling before excavation) not covered | OBSERVED SCH: 2015-02-20 Grondwerk; 2015-02-26 Uitzetten grondwerk |
| DR02 | BLD | FND-REBAR/FND-FORM | Blinding before foundation reinforcement/formwork where blinding is specified | No blinding (e.g. formwork on lean fill) -> rule inactive | OBSERVED SCH: 2015-03-03 Werkvloer liftput |
| DR03a | FND-FORM | FND-REBAR | Method A (formwork first): shutter, then place cage inside | Applicable to boxed strip foundations and pits | OBSERVED SCH: 2015-03-04 Bekisten liftvloer; 2015-03-04 Wapening liftvloer; 2015-03-06 Bekisten liftwanden; 2015-03-09 Wapening liftwanden; 2015-03-12 Stellen f |
| DR03b | FND-REBAR | FND-FORM | Method B (reinforcement first): prefabricated cages, then formwork | Alternative to DR03a - exactly one of DR03a/DR03b per element group | PROPOSED_RULE (common practice; no dataset evidence) |
| DR04 | FND-REBAR & FND-FORM | FND-CONC-* | Reinforcement and formwork complete (and inspected) before foundation concrete | Earth-formed footings: formwork predecessor absent | OBSERVED SCH: 2015-03-05 Stort liftvloer; 2015-03-10 Stort liftwanden; 2015-03-25 Stort; 2015-03-26 Opstorten fundering; 2015-04-03 Stort; 2015-05-19 Stort; 201 |
| DR05 | COL-REBAR | COL-FORM | Column cage before column formwork (typical) | Prefabricated cage + system formwork may overlap (SS) | PROPOSED_RULE |
| DR06 | COL-FORM/BEAM-FORM/SLAB-FORM/WALL-FORM + respective REBAR | COL-/BEAM-/SLAB-/WALL-CONC | Reinforcement and formwork before placement where the method requires both | Slab/beam: formwork usually precedes reinforcement (soffit first); walls: one face, rebar, second face | PROPOSED_RULE; SCH lift walls observed as Bekisten -> Wapening -> Stort |
| DR07 | any *-CONC | CURE | Placement before curing/strength development | Cold-weather, cement type and admixtures change durations | PROPOSED_RULE; BCCA texts include curing labour in concrete items |
| DR08 | CURE | FRM-STRIP | Formwork removal only after the approved striking criterion (strength or time) is met | Side formwork vs soffit/props differ; re-propping strategies | PROPOSED_RULE - pending approval |
| DR09 | COL-CONC (+CURE criterion) | BEAM-FORM/SLAB-FORM (storey above) | Supporting columns/walls cast and adequate before loading formwork of supported members | Monolithic column-beam-slab pours; steel columns (SCH) placed before floors | OBSERVED SCH: 2015-04-13 Kanaalplaatvloer leggen (lev. week 16); 2015-04-16 Afstorten kanaalplaat; 2015-04-20 Plaatsen stalen kolommen; 2015-05-01 Leggen breedp |
| DR10 | storey n structure | storey n+1 structure | Vertical progression storey by storey for supported structure | Zones may overlap horizontally; no inference from spatial adjacency | PROPOSED_RULE; storey evidence from IfcBuildingStorey (flattened in SCH Synchro) |
| DR11 | zone k activity | zone k+1 same activity | Zone progression by crew availability, not by precedence | Zones must be user-defined (IfcZone not audited) | PROPOSED_RULE |
| DR12 | FND-CONC-* (+inspection, waterproofing if any) | BACKFILL | Backfill after foundation completion and inspection | Partial backfill per zone | OBSERVED SCH: 2015-03-11 Aanvullen liftput |
| DR13 | supporting slab | MAS-* | Masonry after its supporting slab/foundation | Load-bearing masonry may PRECEDE the floor it supports (SCH sand-lime walls before breedplaat) | OBSERVED SCH: 2015-04-07 Stelwerk metselwerk onder peil; 2015-04-08 Metselwerk onderpeil (buitenblad); 2015-04-21 Stelwerk kalkzandsteen; 2015-04-22 Lijmwerk ka |
| DR14 | SLAB-PRECAST units | topping pour | Precast floor units before topping concrete | Only for precast systems | OBSERVED SCH: 2015-04-13 Kanaalplaatvloer leggen (lev. week 16); 2015-04-16 Afstorten kanaalplaat |
| DR15 | - | - | Spatial adjacency, contact or containment alone NEVER creates a dependency | - | Mandatory policy |

Observed sequences come from one project plan (SCHEPENDOMLAAN, planned dates 2015; no actual dates). Spatial adjacency never creates precedence (DR15, CR14).

## Task D - missing information policy
| quantity | from_authored_ifc | from_validated_geometry | from_user | from_assumption | otherwise |
|---|---|---|---|---|---|
| Excavation volume | N | N | Y | Y (e.g. approved working-space rule + user ground levels) | BLOCKED |
| Blinding area | Y (footprint area if authored) | Y (footprint of validated foundation geometry) | Y | Y (thickness if not 10 cm) | BLOCKED |
| Concrete volume (net, concrete layer only) | Y (NetVolume; single-material elements) | Y (after manual validation of the model; layer split required) | Y | N | BLOCKED |
| Formwork contact area | N (no model authors formwork area) | N (surface area is not formwork area) | Y | Y (approved face rules per element type/method) | BLOCKED |
| Reinforcement mass | Y only if IfcReinforcingBar/weight exists (none in real models) | N | Y (bar schedule/design value) | N - generic ratios prohibited unless explicitly approved and labelled as assumption by the engineer | BLOCKED |
| Composite floor area | Y (NetArea of slab) | Y | Y | N | BLOCKED |
| Precast unit count/area | Y (slab area) | Y | Y | N | BLOCKED (also no BCCA reference) |
| Masonry net face area | Y (NetSideArea, SCH) | Y (with approved face rule) | Y | N | BLOCKED |
| Backfill volume | N | N | Y | Y (approved bulking/compaction factors) | BLOCKED |
| Curing duration / strength criterion | N | N | Y | Y (engineer-approved) | BLOCKED (schedule constraint unavailable) |
| Steel mass | Y if Weight authored | N (density x volume requires approved density) | Y | Y | BLOCKED (out of RC scope) |

- Unknown quantities are never replaced by zero; the work item is BLOCKED and reported.
- Reinforcement mass is never generated from an unapproved generic ratio.
- 22 required user inputs have no default (`required_user_inputs.csv`).

## Unavailable evidence
- No BCCA reference for aerated-concrete block masonry, hollow-core/filigree precast floors or separate curing.
- No reinforcement, excavation, terrain or formwork-area data in any real model.
- No crew sizes, calendars, curing or striking criteria.
- Sand-lime masonry reference (06LEC80100, face brick) is a weak match for SCH glued sand-lime elements.

## Preservation
Protected files unchanged by this task: **yes**. Files changed since task start: 8 (8 content changes, all by Agent 1 in its own implementation area: 25 paths incl. additions); files added by others: 17.
