# PMI Stage 5.4A independent verification

| Gate | Result |
| --- | --- |
| Stage 5.4A controlled CPM | **Verified.** No blocking discrepancies. Six nonblocking findings ([discrepancy_register.csv](discrepancy_register.csv)). |
| Stage 5.4B authorization (software-only, controlled fixture) | **Recommended**, subject to Tasks 4 onward of the authorization brief. That part of the brief was truncated and has not been carried out. |
| Real-project scheduling | Still disabled. 75 of 75 approvals PENDING; `real_project_eligible=false`. |

Verified at Git HEAD `db5c07d0adf2b8c83981d3d7df540405dd4bbe6a` with a clean working tree. This package is the only new path. No production code, frozen dataset or existing deliverable was modified. Nothing was committed or pushed.

## What was checked and how

1. **Regression tests.** `test_stage5_*.py` ran 40 tests in `.venv`: 12 Stage 5.1, 5 Stage 5.2, 10 Stage 5.3 and 13 Stage 5.4A. All passed.
2. **Reproduction.** `python -m pmi_core.scheduling` was run into a fresh scratch directory. All eight outputs, including `schedule.json` (SHA-256 `53849aa9…`), are byte-identical to `research/implementation/stage5_4a/`.
3. **Independent recalculation.** [scripts/independent_cpm.py](scripts/independent_cpm.py) does not import `pmi_core.scheduling`. It:
   - rebuilds the durations from the Stage 5.3A handover and the Agent 2 curing and striking inputs;
   - derives the 28 edges from the 21 Stage 5.3A edges plus the documented D3 and D5 transformations, and cross-checks them against Agent 2's predecessor lists;
   - schedules on a per-minute working-time predicate, with an exhaustive search for the earliest and latest start;
   - recomputes total and free float by brute force;
   - profiles each resource minute by minute.
4. **Comparison.** [scripts/compare_and_sensitivity.py](scripts/compare_and_sensitivity.py) compares every field with production and runs the tick sensitivity through the existing `fixture.adapt` and `validate_schedule` interfaces.

## Results

| Claim | Independent result |
| --- | --- |
| 21 activity start and finish dates | 21/21 match production **and** Agent 2's `fixture_expected_schedule.csv` |
| Earliest/latest dates, total and free float | 21/21 match on all fields ([activity_verification.csv](activity_verification.csv)) |
| 28 normalized dependencies | Same edge set, all FS, lag 0, elapsed basis, all satisfied ([dependency_verification.csv](dependency_verification.csv)) |
| Completion | 2027-01-14T16:00+01:00, Europe/Madrid |
| Elapsed makespan | 14,880 min |
| Critical activities | S-FORM, S-REBAR, S-INSP, S-POUR, S-STRIKE, S-STRIP, B-STRIP. This 7-activity chain is governed by the 168 h slab striking minimum. |
| Calendar, weekends, 2027-01-06 holiday | 48/48 independent checks passed ([calendar_constraint_verification.csv](calendar_constraint_verification.csv)) |
| Concrete delivery 08:00–14:00 | All three pours inside the window. B-POUR's latest start, 13:45, is bounded by the window. |
| Inspections | 30 working minutes each, one inspector, peak usage 1 of 1 |
| Curing | 1,440 elapsed min from each pour finish; spans non-working time |
| Striking | Measured from pour finish: C 1,440, B 10,080, S 10,080 elapsed min. Not chained to curing. |
| Strength release | Explicit `hypothetical_pass_at_minimum` event on all three. A missing event yields `conditional` (TC6). |
| Shared-resource capacity | Peak ≤ capacity for all six pools; zero conflicts ([resource_profile_verification.csv](resource_profile_verification.csv)) |
| Direct reference cost | €1,172.5136 in the handover, in `schedule.json`, and as the sum of the activity lines |

The beam-to-slab hand-off explains the float pattern. B-CURE ends on the 6 January holiday at 13:15, so S-FORM cannot start before 7 January 08:00. B-CURE therefore carries 1,125 min of float, and the column and beam chains carry 45 min, limited by the 14:00 delivery cut-off for B-POUR on 5 January.

## Deficiencies D1–D11

Nine are resolved. D10 (capacity enforcement) and D11 (supply rate) are only partially resolved, exactly as the implementation claims. Both are diagnostics-only by design and form mandatory Stage 5.4B scope. Evidence for each item is in [deficiency_resolution_verification.csv](deficiency_resolution_verification.csv).

## Discrepancies

None is blocking. In summary:

- **N1.** Three extra edges relative to Agent 2's lists; all are transitively redundant.
- **N2.** A release recorded after the minimum behaves as a fixed absolute date in the backward pass. The fixture does not use this path.
- **N3.** Ticks that do not divide 60 are accepted silently and misalign with the shift boundaries.
- **N4.** The Paris-to-Madrid calendar override is not asserted.
- **N5.** Fixture-hash provenance changed during Agent 2's preparation window. The final artifacts are consistent.
- **N6.** Coarse ticks cause a completion cliff against the delivery window.

## Scheduling resolution sensitivity

All runs use the existing interfaces without code changes ([resolution_sensitivity.csv](resolution_sensitivity.csv)). Runtime is the median of 15 `adapt` calls on this machine.

| Tick | Productive min, scheduled | Rounding allowance | Completion | Makespan | Critical set | Calendar checks | Independent agreement | Runtime |
| ---: | ---: | ---: | --- | ---: | --- | --- | --- | ---: |
| 1 | 628 | 5.68 | 2027-01-14 15:21 | 14,841 | same 7 | 64/64 | yes | ~1.8 ms |
| 5 | 645 | 22.68 | 2027-01-14 15:30 | 14,850 | same 7 | 64/64 | yes | ~1.7 ms |
| **15** | 705 | **82.68** | 2027-01-14 16:00 | 14,880 | same 7 | 64/64 | yes | ~1.7 ms |
| 7 † | 672 | 49.68 | 2027-01-14 15:42 | 14,861 | same 7 | 64/64 | no (grid-origin dependent) | ~1.7 ms |
| 45 † | 900 | 277.68 | 2027-01-18 13:00 | 20,430 | 4 | 64/64 | no (grid-origin dependent) | ~1.7 ms |
| 60 | 900 | 277.68 | 2027-01-18 12:00 | 20,400 | 4 | 64/64 | yes | ~1.7 ms |

The original productive duration is 622.32 min at every tick. † marks probes outside the requested 1/5/15 set, used to locate the unsupported range.

**Effect of the 15-minute tick.** The 82.68 min allowance inflates productive time by 13.3%. Only 41.04 min of it sits on the critical chain. Of that, 39 min reaches completion relative to a 1-minute tick. The 168 h slab striking hold dominates the 14,880 min makespan, so resolution changes completion by only 0.26%. Above 15 min the interaction with the 14:00 delivery cut-off and the holiday produces a cliff of +5,520 min at 60 min.

**Supported values.** Any divisor of 60 that also divides every calendar and supply boundary: 1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30 or 60. Non-divisors run without error but are not valid (N3). No production code was changed to handle them.

**Recommendation.** Keep the tick configurable. Default Stage 5.4B to **5 min**, which cuts the rounding allowance to 3.6% while keeping CP-SAT domains small (2,976 ticks for this fixture's makespan). Retain 15 min as the regression configuration that reproduces Agent 2's expected schedule. Add a preflight that rejects ticks that do not divide the calendar boundaries. Execution time does not discriminate between resolutions for CPM. Re-measure it under CP-SAT.

## Reproduce

From the repository root in PowerShell:

~~~powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_stage5_*.py' -v
& .\.venv-planning\Scripts\python.exe -B -m pmi_core.scheduling --config 'research/implementation/stage5_4a/controlled_schedule_inputs.json' --output 'outputs/stage5_4a/verification_rerun'
& .\.venv\Scripts\python.exe -B 'research/validation/stage5_4a_independent_verification/scripts/independent_cpm.py' 15
& .\.venv\Scripts\python.exe -B 'research/validation/stage5_4a_independent_verification/scripts/compare_and_sensitivity.py'
~~~

The second command needs a fresh output directory. The last command regenerates every CSV and `verification_summary.json` in this folder. Runtimes vary by machine.

## Not done

The authorization brief was truncated at "Task 4 — Prepare independent CP-SAT reference cases". No CP-SAT reference cases were prepared, and no other later tasks were carried out.
