# Stage 5.4B CP-SAT reference cases (Task 4)

This package gives the Stage 5.4B resource-constrained scheduler 22 reference cases with independently derived expected results. They cover the 11 requested categories plus the controlled-fixture regression at 15 and 5 minutes. Every expected value was computed by a reference solver written for this task. It uses neither `pmi_core` nor OR-Tools. All inputs are hypothetical software-test data and imply no engineering approval.

| File | Contents |
| --- | --- |
| [cpsat_reference_cases.json](cpsat_reference_cases.json) | Conventions, general acceptance criteria, and per case: machine-readable input, expected status, makespan, reference schedule, resource occupancy intervals, peak usage, a feasible-but-not-optimal example, proof record |
| [cpsat_expected_results.csv](cpsat_expected_results.csv) | One row per case: status, preflight code, optimal makespan, completion, uniqueness, enumeration counts, proof method |
| [scripts/build_cpsat_reference_cases.py](scripts/build_cpsat_reference_cases.py) | Generator and exhaustive reference solver (runs in under 1 s) |

## How optimality is established

- **Method A: all active schedules.** The serial schedule-generation scheme is run over every precedence-feasible activity order. Each activity is placed at its earliest tick that satisfies precedence, its calendar, capacity on every tick and open reservations. This enumerates every active schedule.
  - Take any feasible schedule and repeatedly move one activity to an earlier feasible position while holding the others fixed. No finish moves later, and the sum of starts strictly decreases, so the process ends at an active schedule.
  - Therefore an optimal schedule and every deadline-feasible schedule have active counterparts. This holds with time-varying capacity, resource calendars, elapsed lags and start-to-finish reservations.
  - The minimum over Method A is optimal. An empty deadline-feasible set proves INFEASIBLE.
- **Method B: time-indexed brute force.** Every start tick is tried for every activity, pruned only by precedence and the elapsed tail length. With the bound set to optimum − 1 tick, it must find **no** schedule. Where the search space is small enough, it is also run at the optimum to show attainment.
  - Method B ran on 11 cases: RC01–RC04, RC05b, RC06, RC07a–c and RC11a–b.
  - It was skipped where the search space exceeds 3 × 10⁶ start combinations (RC05a, RC09) or where an activity is split (RC10a, RC10c). Method A alone proves those.
- **R0, the controlled fixture.** With 21 activities, the list enumeration is impractical. The precedence- and calendar-only earliest finish is a lower bound, and a schedule that respects capacity attains it, so the result is optimal. The values (14,880 min at 15 min, 14,850 min at 5 min) equal the independently verified Stage 5.4A CPM results.

**Feasible versus optimal.** Each OPTIMAL case carries `feasible_not_optimal_example`. This is the worst active schedule, labelled `FEASIBLE (not optimal)`, where one exists. RC09, RC10a and RC10c have none, because every active schedule is optimal. A solver result that is merely FEASIBLE fails an OPTIMAL case, even when the objective is equal.

## Results

All new cases use a **5-minute tick**. R0-15 keeps the existing 15-minute regression. Raw durations are deliberately off-tick (for example 228 → 230 min) to exercise upward rounding. The project calendar is Monday–Friday 08:00–16:00 Europe/Madrid. Makespan is measured in minutes from `project_start`.

| Case | Category | Status | Makespan | Completion | Unique | Why |
| --- | --- | --- | ---: | --- | :---: | --- |
| RC01 | Crew competition | OPTIMAL | 1,610 | Tue 12 Jan 10:50 | no (2) | 230 + 200 + 170 min on one crew; any two fit Monday, and the shortest (C) must go to Tuesday. Shortest-first gives 1,670 (FEASIBLE). |
| RC02 | Shared equipment | OPTIMAL | 210 | Mon 11:30 | yes | Crane lower bound 90 + 120 is attained only with L1 lifting first, so L3 runs alongside L2. L2-first gives 270. |
| RC03 | Multi-trade | OPTIMAL | 150 | Mon 10:30 | no (2) | PEON 3 allows any two of X, Y and Z to overlap, never all three. Y+Z first then X gives 180. |
| RC04 | Inspector | OPTIMAL | 240 | Mon 12:00 | no (2) | The inspector is available only 10:00–12:00, so the two inspections run 10:00 and 10:30, followed by the pours on one concrete crew. |
| RC05a | Reusable formwork, 1 set | OPTIMAL | 3,120 | Wed 13 Jan 12:00 | no (2) | The set is held from FORM start to STRIP finish through curing, so E2-FORM waits for E1-STRIP. |
| RC05b | Reusable formwork, 2 sets | OPTIMAL | 1,620 | Tue 11:00 | no (2) | The two elements overlap; only the crews serialise. |
| RC06 | Resource calendars | OPTIMAL | 4,520 | Thu 14 Jan 11:20 | yes | Crane on hire Tue/Thu 08:00–12:00. M (200 min) cannot use the 90 min left on Tuesday. N (ferrallista, 07:00–15:00) starts Tue 07:00, before the project shift. |
| RC07a | Impossible deadline | INFEASIBLE | — | — | — | RC01 by Mon 16:00. The best possible is 1,610 min, and brute force confirms nothing finishes by 1,605. |
| RC07b | Tight deadline | OPTIMAL | 1,610 | Tue 10:50 | no (2) | The deadline equals the optimum. |
| RC07c | Activity deadline | OPTIMAL | 1,610 | Tue 10:50 | yes | B must finish by Mon 12:00, which forces the order B, A, C. |
| RC08a | Missing capacity | MODEL_INVALID | — | — | — | `MISSING_INPUT`: reject before solving. |
| RC08b | Zero capacity | INFEASIBLE | — | — | — | `IMPOSSIBLE_CREW`. Zero capacity must never be treated as unlimited. |
| RC08c | Insufficient capacity | INFEASIBLE | — | — | — | `IMPOSSIBLE_CREW`: demand 2 against capacity 1. |
| RC08d | Resource never on calendar | INFEASIBLE | — | — | — | `NO_FIT`: capacity is declared but the resource has no window in the horizon. |
| RC09 | Curing overlaps work | OPTIMAL | 5,850 | Mon 18 Jan 09:30 | no (2) | Curing holds no crew, so CREW_F forms E2 while E1 cures. Only one pour fits before Thursday's 14:00 cut-off, so one cure crosses the weekend and one strip lands on Monday. |
| RC10a | Authorized split | OPTIMAL | 4,680 | Mon 18 Jan 14:00 | yes | 600 min in two segments: Fri 12:00–16:00, then Mon 08:00–14:00. |
| RC10b | Split not authorized | INFEASIBLE | — | — | — | `NO_FIT`: 600 min exceeds the 480 min shift. It must not be split silently. |
| RC10c | Split, 300 min minimum segment | OPTIMAL | 6,060 | Tue 19 Jan 13:00 | yes | Friday's 240 min is too short. Starting Monday 08:00 leaves a 120 min tail, so the optimal start is **Mon 11:00**, giving Mon 11:00–16:00 and Tue 08:00–13:00. |
| RC11a | Concrete supply 6 m³/h | OPTIMAL | 1,485 | Tue 12 Jan 08:45 | yes | Both pours draw 6 m³/h and are ready at 12:00, leaving only 120 min of delivery window. P1 (90 min) goes Monday; P2 moves to Tuesday 08:00. P2-first gives 1,530. |
| RC11b | Supply 12 m³/h | OPTIMAL | 330 | Mon 13:30 | yes | Parallel delivery allows both pours to run together. |
| R0-15 | Fixture regression | OPTIMAL | 14,880 | Thu 14 Jan 16:00 | not enumerated | Equals the CPM result. Resources never bind. |
| R0-5 | Fixture at proposed default | OPTIMAL | 14,850 | Thu 14 Jan 15:30 | not enumerated | Equals the 5-min CPM result from Task 3. |

## Modelling conventions the cases fix

These are stated in `conventions` in the JSON. Each is a test decision, not an engineering approval.

- **Time:** integer ticks from `project_start`. Durations and lags are rounded **up** to whole ticks. Every calendar boundary must be a multiple of the tick; otherwise the model is rejected as `MODEL_INVALID` with `TICK_MISALIGNED` (Task 3 finding N3).
- **Activity calendar:** the intersection of the calendars of every renewable resource the activity uses, or the project calendar when it uses none, further intersected with `allowed_hours`. Capacity is 0 outside a resource's calendar.
- **Elapsed holds:** no resources and no calendar.
- **Reservations** (`kind: reservation`, calendar `continuous`): one interval per reservation, from `from_activity` start to `to_activity` finish. In CP-SAT this is a span interval in a cumulative constraint, not the sum of the two activities' own intervals.
- **Concrete supply:** a renewable rate resource in m³/h on its own delivery calendar. Each pour demands its drawn rate, and duration = volume / min(placement rate, supply rate).
- **Split work:** allowed only when `interruption: split_allowed`, within `max_segments` and `min_segment_minutes`. Resources are held only during segments.
  - The reference solver works every available tick from the start and does not pause voluntarily.
  - A solver that allows voluntary pauses can only match or improve the objective. In RC10a and RC10c this was checked by hand: no paused segmentation does better.
- **Statuses:** OPTIMAL, FEASIBLE (not optimal), INFEASIBLE, MODEL_INVALID. Preflight diagnostics (`MISSING_INPUT`, `IMPOSSIBLE_CREW`, `NO_FIT`, `INFEASIBLE_DEADLINE`) follow the Stage 5.4A codes.

## Acceptance criteria

The full list is `general_acceptance_criteria` in the JSON, and each case also has its own `acceptance_criteria`. In summary:

1. The status matches. INFEASIBLE must never come back as UNKNOWN or as a relaxed schedule, and MODEL_INVALID must be rejected before the solver is invoked.
2. The makespan equals `optimal_makespan_minutes` exactly.
3. When `unique_optimal_schedule` is true, every activity start, finish and segment matches `reference_schedule`. Otherwise any optimal schedule is accepted if it passes independent validation.
4. Independent validation of the returned schedule:
   - durations in ticks;
   - every occupied tick on the calendar of each resource used;
   - per-tick capacity, including continuous reservations;
   - FS precedence;
   - deadlines;
   - segment rules.
5. CP-SAT should prove OPTIMAL or INFEASIBLE within a stated time limit. A 10 s limit is suggested, since all cases are tiny.

## Limits and open decisions

- **Unconfirmed conventions:** the reservation span, the supply-as-rate model, intersection calendars and no-voluntary-pause splits all need confirmation from Agent 1 and the engineer before production use.
- **R0 optimality:** proven by bound equality, not by enumeration. The number of alternative optimal fixture schedules is not counted.
- **Not covered:** multi-mode crews, release-event semantics (Task 3 finding N2), SS/FF/SF relations and objectives other than makespan.
- **Fixture data:** no real-project data are used. All 75 approvals remain pending.

## Reproduce

~~~powershell
& .\.venv\Scripts\python.exe -B 'research/validation/stage5_4a_independent_verification/scripts/build_cpsat_reference_cases.py'
~~~

This regenerates `cpsat_reference_cases.json` and `cpsat_expected_results.csv` deterministically. Python standard library only, plus `scripts/independent_cpm.py` for R0.
