# PMI Stage 5.4A calendar-aware CPM

The controlled baseline finishes on **14 January 2027 at 16:00 Europe/Madrid**. Elapsed makespan is **14,880 minutes** from 4 January at 08:00. All 21 activity starts and finishes match the independently prepared feasible reference. The calculated baseline uses precedence and calendar constraints. A separate check found zero overlapping resource claims above the declared capacities. All 75 engineering approvals remain pending, and the controlled result has no real-project release authority.

[Calculated Gantt chart](report.html) · [Schedule JSON](schedule.json) · [Reference comparison](reference_schedule_comparison.csv)

## Verified inputs and results

The adapter verified Agent 2's input SHA-256 against the current Stage 5.3A fixture configuration, then compared all 12 productive records by IFC GlobalId, work item, BCCA code, unit, quantity, trade and equipment demand, duration and cost against the independent calculation. The total direct reference cost matches exactly at **€1,172.5136**. The 21 historical dependencies, original element quantity and cost records, approval register, and conditional source edges are carried into the new output. The Stage 5.3A files were preserved byte-for-byte. The [resolution matrix](contract_resolution_matrix.csv) accounts for all 11 deficiencies.

| Measure | Calculated result |
| --- | ---: |
| Baseline activity dates with any difference to reference | 0 of 21 |
| Makespan difference | 0 min |
| Productive work before tick conversion | 622.32 min |
| Scheduled productive work | 705 min |
| Added working time from upward rounding | 82.68 min |
| Calendar-bound inspection time | 90 min |
| Calendar, release and dependency checks passed | 64 of 64 |
| Shared capacity violations | 0 |

Upward rounding uses 15-minute ticks. Near-integer floating-point artifacts are neutralized before the ceiling. The 82.68 minutes are total scheduled allowance across tasks. The independently prepared reference applies the same tick and therefore has zero scheduled-duration differences. Curing consumes elapsed calendar time even during closures. The three curing durations are 1,440 minutes each. The striking minimums are 1,440, 10,080 and 10,080 minutes from their respective pours. They overlap other activities and are not additive to each other or to curing when calculating makespan.

## Scheduling transformations

The adapter keeps each Stage 5.3A activity identifier and links it to its package, IFC GlobalId and version-scoped BIM element ID. It turns the three hypothetical half-hour inspection holds into working-time activities, each reserving one inspector. No inspection price was added. Productive formwork removal uses the retained BCCA activity and price.

The normalized graph retains 18 of the original edges as explicit elapsed FS lags and supersedes the three curing-to-striking edges. It adds pour-to-striking-minimum and curing-to-strip edges for each package. Three documented cross-package conditions supply four explicit edges: column cure and column strip both precede beam formwork, beam cure precedes slab formwork, and slab strip precedes beam strip. The resulting graph contains 28 edges. The extra curing-to-strip edges for beam and the preserved formwork-to-inspection prerequisites are redundant for the dates and preserve the applicable gates. Structural adequacy remains a hypothetical assumption explicitly tied to the preparation record.

The strength-release minimum is anchored to pour finish. A late timestamped check extends waiting to the check time, while an earlier check leaves the minimum unchanged. A missing pass produces a projected conditional schedule and propagates the condition downstream. For this run, Agent 2's documented hypothetical pass is represented as a test event at each elapsed minimum. Real strength approval is excluded from fixture configuration.

Resource diagnostics use the full declared crew mode. For example, column placement reserves the general skilled worker included in HYP-CONC even though its specific BCCA demand for that trade is zero. This preserves Agent 2's occupancy assumption. The original engineering demand and cost remain unchanged.

## Calendar and CPM behavior

The calendar expands local Europe/Madrid dates into UTC minute intervals. Monday–Friday working windows run 08:00–16:00. Pours must fit inside the intersection with the 08:00–14:00 delivery window. The 6 January holiday removes the whole working window. The calendar also supports explicit replacement windows. The 18 h 45 min gap before slab formwork follows the holiday closure after beam cure, so formwork begins on 7 January at 08:00.

Activity durations and minimum lags round up. Availability rounds inward and hard deadlines round down. Timestamps carry a UTC offset. Ambiguous or nonexistent local boundary times require resolution rather than silent guessing. Work is noninterruptible unless explicitly marked split-allowed. An uninterrupted activity longer than any available window reports NO_FIT. Insufficient work within the finite horizon reports HORIZON_EXHAUSTED.

The forward pass finds earliest times in topological order. The backward pass inverts nonnegative FS lags and fits each activity against the same calendar in reverse, including the delivery restriction. Working lags use the base project calendar. Total float is the elapsed difference between latest and earliest feasible start. Free float uses successor earliest starts with the same reverse fitting and applicable deadlines. The critical subgraph includes zero-total-float nodes and controlling links between them. Early column and beam activities have float before the holiday boundary. The seven zero-float activities are slab formwork, rebar, inspection, pour, striking release and stripping, followed by beam stripping. Other relation types and negative lags are outside the supported CPM subset. Conditional float describes the projection while an unresolved event remains conditional.

## Verification and usage

All 40 regression tests passed, including the previous 27 and 13 Stage 5.4A tests. The 10 Agent 2 cases exercise chains, parallel work, shared-pool overlap reporting, weekends and holidays, split authorization, elapsed curing, release events, hard deadlines, insufficient capacities, cycles, and the full frame. In TC3 the unlevelled CPM finishes Monday 15:00 and reports an over-capacity interval. Agent 2's capacity-feasible Tuesday 10:00 result is the future resource-constrained target. The fixture dates, quantities and prices were tested for determinism and preservation.

Run from the repository root and choose a fresh output path.

~~~powershell
& .\.venv-planning\Scripts\python.exe -B -m pmi_core.scheduling --config 'research/implementation/stage5_4a/controlled_schedule_inputs.json' --output 'outputs/stage5_4a/controlled'
~~~

Test command.

~~~powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_stage5_*.py' -v
~~~

The calendar and CPM code use the standard library and local IANA timezone data. No solver is invoked. The scheduling contract and CLI adapter live in pmi_core/scheduling. The [preservation record](preservation_verification.json) includes starting HEAD and verified tracked and untracked protected artifacts. No Stage 5.3A or Agent 2 preparation files were modified.

## Stage 5.4B requirements

Reuse the normalized FS graph, feasible calendar start domains, fixed duration/occupancy modes and eligibility gates. Add CP-SAT cumulative constraints per trade, equipment, inspector and reusable formwork/prop pool, with explicit capacity calendars and unambiguous restart rules for split work. Specify supply throughput and capacity limits where the project needs more than a time window. Add solver statuses, bounded horizons, objectives, infeasibility provenance, independent resource/calendar validation, and comparisons to both the CPM baseline and the Agent 2 resource cases. Preserve original quantities, cost scope and pending engineering approvals. No optimization or real-project schedule was implemented in Stage 5.4A.
