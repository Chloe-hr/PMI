# Scheduling engine usage for the controlled frame (delta to Agent 2 specification)

Generated 2026-11-19 18:37 UTC. This document **adds** fixture-level detail to `research/architecture/stage5_0/scheduling_engine_specification.md`; it does not restate it and does not implement a scheduler.

## 1. Inputs -> model elements
| Input (controlled_scheduling_inputs.json) | CPM | OR-Tools CP-SAT |
|---|---|---|
| productive activity, minutes (ceil 15) | duration on working-time calendar | interval var per mode; start restricted to precomputed window-fit start slots (AddAllowedAssignments / domain), end = start + minutes |
| elapsed_hold (curing, striking minimum) | lag in elapsed minutes | fixed-size interval (or pure precedence with elapsed lag) not consuming resources, allowed to span nights/weekends |
| inspection (working time, INSPECTOR) | working-time activity | interval + cumulative on INSPECTOR |
| resource_capacity_by_trade, crew_modes | ignored (CPM is resource-free) | AddCumulative per trade/equipment; crew mode demand = workers_by_trade |
| concrete_delivery window | not in CPM (report separately) | start domain of pour intervals limited to slots whose end <= 14:00 |
| calendar + date_exceptions | working-time map | expanded to absolute UTC minute windows; no productive slot on exceptions |
| predecessors FS + lag_basis elapsed | forward/backward pass | end(pred) + lag <= start(succ) |
| strength condition | not representable -> flag | release literal: start(strip) >= max(min elapsed, approval time); without approval event the solution is labelled CONDITIONAL |

## 2. Conditional dependencies
- Method choices (DR05 cage_first vs formwork_first) are resolved **before** solving from approved method IDs; the solver never chooses an unapproved method.
- Alternative modes (e.g. split allowed) are optional intervals with exactly-one constraints only when the alternative is approved.
- Holds with an approval event: model the event time as a fixed lower bound when recorded; as a projected bound (status CONDITIONAL) when not.

## 3. Infeasibility diagnostics expected by the test cases
| Case | Stage | Diagnostic |
|---|---|---|
| TC4 10 h phase | preflight | NO_FIT (phase longer than any window; split not approved) |
| TC7 deadline | preflight serial bound / CP-SAT assumptions | INFEASIBLE, implicates deadline literal and controlling chain |
| TC8 capacity | preflight | MISSING_INPUT / IMPOSSIBLE_CREW / NO_ELIGIBLE_MODE |
| TC9 cycle | preflight | MODEL_INVALID: CYCLE [A,B,C,A] |
| fixture without DR09 edges | preflight warning | UNSUPPORTED_SEQUENCE: supported member formwork without support predecessor |

## 4. Mapping back to BIM elements and IFC4D
| PMI record | IFC4 entity | Notes |
|---|---|---|
| Schedule | IfcWorkSchedule (PredefinedType PLANNED) + IfcRelAssignsToControl -> tasks | one per scenario/version |
| WorkPackage | IfcTask (summary) + IfcRelNests -> activity tasks | zone/pour batch |
| productive ConstructionActivity | IfcTask (PredefinedType CONSTRUCTION; FRM-STRIP DISMANTLE) with IfcTaskTime ScheduleStart/ScheduleFinish, ScheduleDuration, DurationType WORKTIME | ISO 8601 local times with offset |
| elapsed_hold (curing, striking) | IfcTask PredefinedType USERDEFINED, ObjectType CURING_HOLD / STRIKING_HOLD, IfcTaskTime DurationType ELAPSEDTIME | alternatively IfcRelSequence.TimeLag (IfcLagTime, DurationType ELAPSEDTIME) when no task row is wanted |
| inspection | IfcTask USERDEFINED ObjectType INSPECTION | IsMilestone false (0.5 h working time) |
| ActivityDependency | IfcRelSequence SequenceType FINISH_START, TimeLag IfcLagTime | lag_basis -> DurationType |
| element allocation | IfcRelAssignsToProcess (RelatingProcess = IfcTask, RelatedObjects = IfcProduct by GlobalId) | via WorkItem -> QuantityAllocation -> BIMElement.global_id; version-scoped IDs resolved to the source model's GlobalIds |
| Crew / EquipmentResource | IfcLaborResource / IfcConstructionEquipmentResource + IfcRelAssignsToResource | resource usage per task |
| ProjectCalendar | IfcWorkCalendar (WorkingTimes IfcWorkTime + IfcRecurrencePattern, ExceptionTimes) | holidays as exceptions |

Round-trip test (per Agent 2): re-read the exported IFC, compare task times, sequence edges, lag types and product assignments with the schedule; source model bytes must be unchanged (write a new file).
