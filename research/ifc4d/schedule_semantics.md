# PMI Stage 3.8B schedule semantics ? reconciliation-v1

All data are explicitly synthetic. Original workbook and IFC files are immutable inputs; generated artifacts go in data/processed/ifc4d/stage3_8b_v1. Existing output directories are never overwritten.

## Calendar and relationships

Dates are timezone-free calendar dates. Duration D = (inclusive finish - start).days + 1, a positive integer; weekends and holidays count. No resource calendar or levelling is implied. Zero-duration milestones are outside this dataset's supported contract and rejected.

For FS dependency p -> q with integral calendar-day lag L: start(q) >= inclusive_finish(p) + 1 + L days. Negative L is an explicit lead, retained as signed lag; it allows overlap under this equation. No negative lags occur in the current inputs. Nonintegral lag, unsupported relationship types, unresolved references and cycles block derivation and conversion; they are never coerced into FS or silently dropped.

IFC encodes start at 00:00 on the start date and finish at 00:00 on the day AFTER the inclusive finish. This half-open interval has elapsed length D calendar days. IfcTaskTime.DurationType and IfcLagTime.DurationType are ELAPSEDTIME; ScheduleDuration is P{D}D. Thus FS zero lag permits successor start equal to predecessor IFC finish timestamp. Negative lag uses -P{abs(L)}D. Source inclusive dates and conversion semantics remain in task descriptions and CSV tables. A viewer must subtract one day from the IFC finish boundary to label the inclusive last day; it must not interpret it as an additional day of work.

## Source values and synthetic actuals

Planned duration belongs to the selected schedule snapshot. Synthetic actual duration describes generated actual start/finish and is never used for planning or dependency inference. delay_days_synthetic is finish-date variance: synthetic actual finish minus baseline planned finish. It differs from actual duration minus planned duration when starts shift.

Out-of-sequence synthetic actual work is preserved and reported in a separate synthetic_actual validation scope, not repaired. It is not independently observed execution. Progress is retained in the source-record export; no actual progress or actual dates are loaded into planned IFC TaskTime.Actual* or Completion fields.

## Snapshots and deterministic derivation

Activities baseline dates and ScheduleVersions V0 must agree. V0 (baseline), V1 and V2 are independent snapshots, including their source as_of_date and duration values. V1/V2 are not overrides of V0, not iterations in the reconciliation algorithm, and not predictions. Each produces separate as_provided and derived IFC files and a derived table; task GlobalIds are namespaced by project, version and representation, with an explicit mapping table.

For each project, the anchor is the earliest planned start across its three source snapshots. This preserves the source project calendar origin. Use lexicographically deterministic topological order. For every task, derived start is max(anchor, each derived predecessor inclusive finish + 1 + lag); derived finish = derived start + D - 1. Every root starts at the anchor. Original task starts are NOT release-date constraints, so starts can move earlier or later. This is an earliest feasible precedence-only schedule, not a minimal-change repair or an achievable resource plan. Version as_of_date is provenance, not a release constraint. No execution state constrains these synthetic derived schedules.

Preserve duration, all dependency IDs/endpoints/types/lags and source records. Record signed derived-minus-original start and finish shifts. Fail on structural or duration errors, but allow original FS conflicts as explicitly reported input conditions. Validate derived schedules separately; they must have zero FS violations. Never describe derived dates as actual construction observations.

## IFC provenance and integrity

Write new IFC4 copies with IfcWorkSchedule, IfcTask, IfcTaskTime, IfcRelSequence, IfcRelAssignsToProcess and schedule-control assignments. Existing geometry, property sets and GlobalIds remain byte-identical at entity serialization level. UUID5-based compressed IFC GlobalIds identify added objects deterministically. Each dependency carries its workbook dependency ID and an explicit IfcLagTime, including zero lag. Every task description carries its source record, original dates and selected representation. WorkSchedule descriptions carry project/version/as-of/anchor/policy and input hashes.

Reopen every output to verify exact task mappings, dates, elapsed durations, links, dependency IDs/endpoints/types/lags, schedule provenance and all source entity serializations. As-provided round-trip success does not imply precedence compliance. Derived validation success does not establish real-world accuracy. Output hashes and input hashes are recorded separately; no training, commit or push occurs.
