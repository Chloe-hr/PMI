# Stage 5.3 readiness - controlled concrete-frame demonstration

Generated 2026-11-19 17:55 UTC. Research only. Nothing is approved; all 75 items remain PENDING.

## Readiness by phase
| Phase | Decisions required | Status | Blocking inputs |
|---|---|---|---|
| Work-package generation | 21 | NOT READY - pending approvals | construction method per element group (AP-CR06), measurement rules DC06/DC07/DC08, formwork applicability (CR13) |
| Duration estimation | 4 | NOT READY | crew composition, rebar kg, formwork face rules, crane/pump declaration, curing/striking decisions |
| Resource-constrained scheduling | 8 | NOT READY | calendar, zones, sequence choices DR05/DR06/DR09/DR10/DR11, hold criteria DR07/DR08 |
| Real-project release | 11 | NOT READY | manual quantity validation + tolerance (AP-TOL), foundation classification (CR11), Synchro handling (CR15) |

Software can be exercised now on the **hypothetical_test_fixture** only; its results are not evidence of real-project accuracy.

## Reference evidence available
- 10 primary + 4 alternative BCCA references (stage5_3_reference_selection.csv); cost split reconciles to published price (max |difference| 0.0066 EUR).
- BCCA gives trades, not crews; no crane, pump or delivery capacity; no curing or striking durations.

## Data contracts for Agent 1 (Stage 5.2A) - no Agent 1 file was edited
| this_package | canonical_field |
|---|---|
| stage5_3_reference_selection.csv bcca_code, quantity_unit | ProductivityReference.code, declared_unit (declared_amount = 1) |
| labour_h_per_unit_by_trade | ProductivityReference.worker_hours_by_trade (trade key = BCCA labour concept summary) |
| equipment_h_per_unit | ProductivityReference.machine_hours_by_class |
| unresolved_equipment non-empty | ProductivityReference.demand_coverage = partial |
| unit_cost_eur, concept_price_date_ddmmyy | CostReference.amount (category = bundle), price_date |
| cost_labour/equipment/material_eur | CostReference rows with category labor/equipment/material (derived; provenance = decomposition sum) |
| template.required_user_inputs.calendar | ProjectCalendar.working_windows / window_start / window_end |
| template.required_user_inputs.crews | Crew.workers_by_trade, calendar_id |
| template.required_user_inputs.equipment | EquipmentResource.equipment_class, units |
| curing / striking | ConstructionActivity(kind=elapsed_hold) + ActivityDependency(lag_basis) |
| priority_approval_register.csv approval_id | WorkItem.approval / ActivityDependency.approval_id |

Observations for Agent 1:
- Trade keys are the Spanish BCCA labour concept names (e.g. "OF. 1ª ENCOFRADOR"); keep them as source keys and map to display names separately.
- `05HAC00015` is shared by column, beam and slab reinforcement: one ProductivityReference, three WorkItems (DC05).
- Concrete items need an EquipmentResource declaration for crane/pump even when the answer is none; otherwise `demand_coverage=partial` must block release.
- FRM-STRIP is a separate WorkItem only for 05HEM* formwork; never for 03ERM* (foundation, out of demo scope).

## What you must measure, choose or obtain
See `one_page_summary.md`.
