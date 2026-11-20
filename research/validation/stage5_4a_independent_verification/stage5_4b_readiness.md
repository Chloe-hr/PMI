# Stage 5.4B readiness: controlled CP-SAT implementation

## Decision

**CONDITIONAL GO** for implementing CP-SAT scheduling on the **controlled hypothetical fixtures only**.

**NO-GO** for real-project scheduling.

The conditions are the mandatory requirements MR-01 to MR-12 below. A solver result may be used only after it passes every criterion marked mandatory in [acceptance_criteria.csv](acceptance_criteria.csv). None of these conditions blocks starting the implementation. All of them block accepting it.

Nothing in this package grants engineering approval. The 75 original approvals and the 13 addendum approvals are PENDING.

## Agent 1's corrections, independently verified

| Claim | Independent result at HEAD `b3e4acc` |
| --- | --- |
| 43 regression tests pass | 43 ran, OK (`test_stage5_*.py`, `.venv`) |
| Eight frozen exports reproduce byte-for-byte | 8 of 8 identical in a fresh temporary directory |
| Tick alignment validation | `round_duration` rejects ticks that do not divide 60. `build_windows` rejects off-grid local and UTC boundaries with `TICK_MISALIGNED`. Tested with ticks 7 and 45 and a 14:05 window. |
| Timestamped strength release | A recorded pass is a fixed not-before on release finish, and `release_event_id` is limited to strength-release activities. The regression checks the 1,530-minute release wait and zero float on STRIP. |
| Paris-to-Madrid override | `adapt()` requires a Stage 5.3 calendar in Europe/Paris, a preparation calendar in Europe/Madrid, and equal recurring windows. The regression rejects a changed window. |

These changes resolve Task 3 findings N2, N3 and N4 for the CPM. No production code was changed in Task 7.

## Contract issues resolved

The resolutions are in [resource_contract_R2_addendum.json](resource_contract_R2_addendum.json). The R1 contract file is unchanged; R2 takes precedence for the sections it names. The new cases are in [task7_reference_cases.json](task7_reference_cases.json). The 22 original cases are unchanged.

1. **Default calendar policy (R2-1).**
   - An activity may occupy a tick only where all three of these are open: the project calendar, the activity's `allowed_hours`, and the calendar of every resource it uses.
   - Exceptions must be registered with an authorization reference. They are never inferred from a resource calendar.
   - **RC06** is preserved unchanged as registered exception `CAL-EXC-RC06`, with N on Tuesday at 07:00. The builder confirms it reproduces the original exactly.
   - The new **RC06-D** uses the same inputs under the default policy. N moves to Tuesday 08:00–10:30, and the makespan stays 4,520 min because M controls it.
   - This answers Agent 1's concern: the project calendar is part of the default, and RC06's early start is a declared exception rather than an accident.
2. **Crew-mode occupancy versus BCCA demand (R2-2).**
   - The selected mode stays fully occupied, and durations and costs are unchanged.
   - Units without positive BCCA demand must be declared in `reserved_without_bcca_demand`, with a reason. V5 becomes an exact equality: mode units = positive-demand capacities + declared reservations.
   - Exactly one pattern exists in both fixtures. The HYP-CONC *oficial* on column pours (05HHP00003 has only peón hours) appears on the R0 COL-CONC activity and on demo C1–C4 POUR. It is covered by AP-X-CREW-01.
3. **Strength releases (R2-3).**
   - A **timestamped fixed pass** (`recorded_pass` with `at`) sets the release finish to max(pour finish + minimum, `at`). The timestamp does not move with the pour. RC13a: 5,970 min.
   - A **future activity-dependent test** (`planned`, with a test age) is a projection measured from the pour, which moves with it. It is always CONDITIONAL, never OPTIMAL or releasable. RC13b: projected 5,880 min.
4. **Inspection pass events (R2-4).**
   - Each event has an id, its inspection, the activities it gates, a status and a timestamp.
   - RC12a, `hypothetical_pass`: 195 min.
   - RC12b, `missing`: the same dates, but CONDITIONAL.
   - RC12c, `failed`: the gated pour is BLOCKED.
   - RC12d, `recorded_pass` at 11:40: a fixed not-before, giving 265 min.
   - RC12e, a pass recorded before the inspection can finish: MODEL_INVALID.
   - The controlled-fixture exceptions FX-R0-01 to 06 and FX-DEMO-01 to 02 are listed explicitly. For example, R0 reservations are excluded and reported unenforced, and R0 inspections are declared `hypothetical_pass`.
5. **The larger benchmark and the 1 March 2027 holiday.**
   - The benchmark is **preserved**: 40,445 min, completing Monday 1 March 2027 at 10:05, proven optimal. Its files are byte-identical to HEAD.
   - The separate sensitivity case **DEMO-H1** declares 2027-03-01 non-working, using the unchanged builder with `PYTHONHASHSEED=0`. Its optimum is 41,885 min, completing Tuesday 2 March 10:05. The proven lower bound equals the schedule, all 242 checks pass, and the cost is unchanged at €5,103.33.
   - It is stored in [controlled_resource_demo_holiday_sensitivity/](controlled_resource_demo_holiday_sensitivity/). Whether the date is really a holiday is left to AP-X-CAL-02.
6. **Consolidated acceptance criteria.** [acceptance_criteria.csv](acceptance_criteria.csv) has 84 criteria:
   - 11 general;
   - 22 Task 4 cases;
   - 9 Task 7 cases;
   - 32 contract rules: principles, validations with V5-R2, diagnostics, and the R2 sections;
   - 5 for the larger benchmark;
   - 5 for preservation.
7. **Engineering approval addendum.** [engineering_approval_addendum.csv](engineering_approval_addendum.csv) adds 13 PENDING items, AP-X-CAL-01 to AP-X-SEQ-01:
   - calendar exceptions and holidays;
   - crew occupancy;
   - inspection;
   - two strength-evidence forms;
   - formwork sets, props, release and lead times, and reshoring;
   - concrete supply;
   - split work;
   - multi-element sequencing.

   `priority_approval_register.csv` is unchanged: 75 rows, all PENDING, with the same SHA-256.

## Mandatory implementation requirements

| ID | Requirement | Evidence that must pass |
| --- | --- | --- |
| MR-01 | Integer ticks from `project_start`. The default is 5 minutes, and 15 minutes reproduces R0-15. Durations and lags are rounded up. Reject misaligned ticks or boundaries. | AC-G01 to G11, R0-15, R0-5 |
| MR-02 | Default calendar policy plus a registered exception list (R2-1). Capacity is 0 when a resource is off its calendar. | RC04, RC06, RC06-D, RC08d, RC11 |
| MR-03 | One cumulative constraint per working-time resource, using fixed single-mode units, including declared `reserved_without_bcca_demand` (R2-2, V5-R2). Durations and costs come unchanged from Stage 5.3A. | RC01 to RC03, larger demo |
| MR-04 | Continuous reservations as span intervals from the start event to max(release events) plus return lead, with no calendar, in one cumulative constraint per asset. | RC05a/b, larger demo (including deadlock-prone orders) |
| MR-05 | A shared concrete supply rate pool on its own delivery calendar, with integer drawn rates. Distinguish explicit none from missing. | RC11a/b, larger demo |
| MR-06 | Inspection pass events and strength-release semantics, producing CONDITIONAL, BLOCKED and MODEL_INVALID outcomes (R2-3, R2-4). | RC12a–e, RC13a–b |
| MR-07 | A split policy with authorization, segment limits, retention and restart rules, or explicit rejection of unsupported choices. Unauthorized splits are never silent. | RC10a–c |
| MR-08 | A preflight that diagnoses MISSING_INPUT, IMPOSSIBLE_CREW, NO_FIT, INFEASIBLE_DEADLINE, TICK_MISALIGNED, SPLIT_NOT_AUTHORIZED, RESERVATION_UNRELEASED and EXPLICIT_NONE_REQUIRED **before** solving. Never relax an input. | RC07a, RC08a–d, RC10b |
| MR-09 | Report status as OPTIMAL, FEASIBLE, INFEASIBLE, MODEL_INVALID or CONDITIONAL. A FEASIBLE result without proof fails an OPTIMAL case. | All cases |
| MR-10 | Validate every solver schedule independently against the acceptance checks: calendars, precedence, per-minute capacity, reservations and segments. | AC-D02, `feasibility_checks.csv` semantics |
| MR-11 | Stable `resource_id` values, with BCCA `display_name` kept. Preserve every input_state, approval id and `real_project_eligible = false`. | AC-C-P1 to P7, AC-P05 |
| MR-12 | Keep CPM as the baseline and lower bound. Never change BCCA costs: €1,172.5136 for R0 and €5,103.32664 for the demo. | AC-P02 to P04, AC-D04 |

## Exact input files

The paths are also listed in [deliverable_manifest.json](deliverable_manifest.json), with SHA-256 hashes.

| Purpose | File |
| --- | --- |
| Reference cases (22, unchanged) | `research/validation/stage5_4a_independent_verification/cpsat_reference_cases.json` |
| Task 7 cases (RC06-D, RC12a–e, RC13a–b, DEMO-H1) | `research/validation/stage5_4a_independent_verification/task7_reference_cases.json` |
| Resource contract | `resource_contract.json` (R1), amended by `resource_contract_R2_addendum.json`, same folder |
| Larger benchmark | `controlled_resource_demo/fixture_inputs.json` and `controlled_resource_demo/expected_results.json` |
| Holiday sensitivity | `controlled_resource_demo_holiday_sensitivity/fixture_inputs.json` and its `expected_results.json` |
| R0 regression | `research/implementation/stage5_4a/controlled_schedule_inputs.json`, `research/implementation/stage5_3/scheduling_handover.json`, `research/implementation/stage5_3/fixture_inputs.json`, `research/planning/stage5_4_preparation/controlled_scheduling_inputs.json` |
| Acceptance criteria | `research/validation/stage5_4a_independent_verification/acceptance_criteria.csv` |

## Remaining deficiencies

[remaining_deficiencies.csv](remaining_deficiencies.csv) lists 15. **None blocks controlled implementation.**

- **Mandatory implementation work (7):** RD03 to RD09, which correspond to MR-02 to MR-07 and MR-11.
- **Blocking for real projects only:** RD13, the pending approvals and the lack of independent measurements.
- **Nonblocking and out of scope (7).** Two correct my own earlier deliverables:
  - **RD01:** the larger-demo builder's representative schedule depends on Python hash randomization. Across 10 seeds, the inputs, the 40,445-minute optimum, the CPM result, the conflicts and the cost were identical, but the dates of alternative optima differ. Task 6 called the build deterministic; that holds for the results, not for the representative dates. Acceptance therefore never compares dates for that benchmark (AC-D05).
  - **RD02:** `scripts/out/` holds stale duplicates of the Task 1–3 CSVs. The top-level files are authoritative.

## Preservation

See [preservation_verification.json](preservation_verification.json).

- No tracked file was modified at HEAD `b3e4acc`.
- The engineering register, the Stage 5.3A handover, the Stage 5.4A schedule and every Task 4–6 deliverable are byte-identical to HEAD.
- Task 7 added only new files to this folder: the six requested deliverables, the R2 addendum, the Task 7 cases, two generators and the holiday sensitivity folder.
- No dependencies were installed, no models trained, and nothing committed or pushed.

## Reproduce

~~~powershell
& .\.venv\Scripts\python.exe -B 'research/validation/stage5_4a_independent_verification/scripts/build_task7_cases.py'
& .\.venv\Scripts\python.exe -B 'research/validation/stage5_4a_independent_verification/scripts/build_task7_package.py'
~~~

The first command regenerates `task7_reference_cases.json` and the holiday sensitivity folder. The second regenerates the CSVs, the R2 addendum, the manifest and the preservation record. It reruns the 43 tests and the 8-export reproduction itself.
