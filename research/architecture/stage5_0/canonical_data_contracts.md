# Canonical data contracts

Draft 2020-12, version 5.0.0. Each record has an opaque primary identifier unique across the project bundle. Persist references by ID. IFC entity lookup uses model version and namespace plus IFC GlobalId. STEP IDs locate entities within a specific source only. Scope allocations preserve many-to-many element/operation relationships through quantity allocations, work packages and activity work-item membership. One item may serve multiple distinct phases. Deduplicate measurement consumption by operation scope. Allocate no more than the accepted physical quantity in the same scope; full allocations must reconcile. Milestones and holds may have no direct physical measurement.

Canonical units are SI m, m², m³ and kg, calendar minutes, productive worker-hours and machine-hours, ISO dates and timezone-bearing timestamps. Store original source units, dimensional conversions and scope in provenance. Calendar windows are disjoint, half-open and within their range. Validate time order, nonnegative counts, project consistency, dimension/basis equality, relationship cardinality and release/schedule state in the domain validator. Omit unknown optional values and include an issue where consumed. Evidence links resolve to provenance records that form an acyclic graph back to immutable snapshots or documented approvals. Derived facts list inputs, formula/rule version and assumptions. Budget or carbon deltas must identify compatible basis and coverage.

## Project

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| name | string | Required |
| country | string | Required |
| region | string | Required |
| timezone | string | Required |
| start_date | date | Required |
| preferred_completion | date | Optional or conditional |

## ModelVersion

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| project_id | string | Required |
| sha256 | string | Required |
| source_uri | string | Required |
| namespace | string | Required |
| ifc_schema | string | Required |
| imported_at | date-time | Required |
| parent_id | string | Optional or conditional |

## BIMElement

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| model_version_id | string | Required |
| global_id | string | Required |
| ifc_class | string | Required |
| source_step_id | integer | Required |
| container_id | string | Optional or conditional |
| geometry_digest | string | Optional or conditional |
| classification | string | Optional or conditional |

## QuantityRecord

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| element_id | string | Required |
| kind | length/area/volume/mass/count | Required |
| basis | string | Required |
| method | ifc_quantity/geometry/manual | Required |
| status | accepted/missing/disputed | Required |
| value | number | Optional or conditional |
| unit | m/m2/m3/kg/each | Optional or conditional |
| raw_value | number | Optional or conditional |
| raw_unit | string | Optional or conditional |
| reason | string | Optional or conditional |

## MaterialRecord

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| element_id | string | Required |
| name | string | Required |
| basis | string | Required |
| grade | string | Optional or conditional |
| fraction | number | Optional or conditional |
| quantity_ids | array of string | Optional or conditional |
| density_kg_m3 | number | Optional or conditional |

## QuantityAllocation

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| quantity_id | string | Required |
| work_item_id | string | Required |
| amount | number | Required |
| unit | m/m2/m3/kg/each | Required |
| operation_scope | string | Required |

## WorkItem

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| model_version_id | string | Required |
| operation | string | Required |
| scope_key | string | Required |
| quantity_unit | m/m2/m3/kg/each/none | Required |
| approval | proposed/approved/blocked | Required |
| catalogue_code | string | Optional or conditional |
| bundle_group | string | Optional or conditional |

## WorkPackage

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| model_version_id | string | Required |
| zone_id | string | Required |
| work_item_ids | array of string | Required |
| method_id | string | Required |
| pour_id | string | Optional or conditional |

## ConstructionActivity

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| work_package_id | string | Required |
| work_item_ids | array of string | Required |
| kind | productive/elapsed_hold/milestone | Required |
| status | planned/ongoing/completed | Required |
| actual_start | date-time | Optional or conditional |
| actual_finish | date-time | Optional or conditional |
| release_rule_id | string | Optional or conditional |

## ActivityDependency

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| predecessor_id | string | Required |
| successor_id | string | Required |
| relation | FS/SS/FF/SF | Required |
| lag_minutes | integer | Required |
| lag_basis | elapsed/working | Required |
| approval_id | string | Required |

## ProductivityReference

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| provider | string | Required |
| release | string | Required |
| code | string | Required |
| region | string | Required |
| declared_unit | string | Required |
| declared_amount | number | Required |
| allowance_basis | string | Required |
| worker_hours_by_trade | map of number | Required |
| machine_hours_by_class | map of number | Required |
| demand_coverage | complete/partial | Required |
| concept_date | date | Optional or conditional |

## CostReference

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| provider | string | Required |
| release | string | Required |
| code | string | Required |
| region | string | Required |
| currency | string | Required |
| price_date | date | Required |
| declared_unit | string | Required |
| declared_amount | number | Required |
| amount | number | Required |
| category | material/labor/equipment/overhead/scenario/bundle | Required |

## EnvironmentalReference

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| provider | string | Required |
| release | string | Required |
| dataset_uuid | uuid | Required |
| dataset_version | string | Required |
| stock_id | string | Required |
| region | string | Required |
| declared_unit | string | Required |
| declared_amount | number | Required |
| standard | string | Required |
| indicator | string | Required |
| indicator_unit | string | Required |
| characterization_basis | string | Required |
| modules | array of string | Required |
| value | number | Required |

## Crew

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| project_id | string | Required |
| workers_by_trade | map of integer | Required |
| calendar_id | string | Required |

## EquipmentResource

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| project_id | string | Required |
| equipment_class | string | Required |
| units | integer | Required |
| calendar_id | string | Required |
| asset_ids | array of string | Optional or conditional |

## ProjectCalendar

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| project_id | string | Required |
| timezone | string | Required |
| working_windows | array of object | Required |
| window_start | date-time | Required |
| window_end | date-time | Required |

## DurationEstimate

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| activity_id | string | Required |
| productive_hours | number | Required |
| elapsed_hold_minutes | integer | Required |
| worker_hours_by_trade | map of number | Required |
| machine_hours_by_class | map of number | Required |
| method | engineering/approved_correction | Required |
| assumption_ids | array of string | Required |
| quantity_allocation_ids | array of string | Required |
| productivity_reference_ids | array of string | Required |
| crew_id | string | Optional or conditional |
| baseline_estimate_id | string | Optional or conditional |
| release_rule_id | string | Optional or conditional |

## Schedule

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| scenario_id | string | Required |
| calendar_id | string | Required |
| method | CPM/CP-SAT | Required |
| status | optimal/feasible/infeasible/unknown/invalid/blocked | Required |
| tick_minutes | integer | Required |
| horizon_end | date-time | Required |
| entries | array of object | Required |
| diagnostics | array of string | Required |
| parent_id | string | Optional or conditional |

## DesignChange

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| old_version_id | string | Required |
| new_version_id | string | Required |
| kind | added/removed/modified/unresolved | Required |
| old_element_ids | array of string | Required |
| new_element_ids | array of string | Required |
| changed_fields | array of string | Required |
| quantity_deltas | array of object | Required |
| match_approval_id | string | Optional or conditional |

## ImpactAssessment

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| change_ids | array of string | Required |
| work_package_ids | array of string | Required |
| activity_ids | array of string | Required |
| coverage | complete/partial/blocked | Required |
| deltas | array of object | Required |
| issues | array of string | Required |
| baseline_schedule_id | string | Optional or conditional |
| revised_schedule_id | string | Optional or conditional |

## PlanningScenario

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| evidence_ids | array of string | Required |
| project_id | string | Required |
| model_version_id | string | Required |
| input_digest | string | Required |
| objective | baseline/economic/environmental/feasibility | Required |
| state | draft/solved/selected/blocked | Required |
| objective_scope | string | Required |
| parent_id | string | Optional or conditional |
| approval_id | string | Optional or conditional |

## EvidenceProvenance

| Field | Type | Presence |
|---|---|---|
| id | string | Required |
| kind | source/derivation/assumption/approval | Required |
| locator | string | Required |
| version | string | Required |
| input_ids | array of string | Required |
| sha256 | string | Optional or conditional |
| formula | string | Optional or conditional |
| actor | string | Optional or conditional |
| timestamp | date-time | Optional or conditional |

