# Stage 5.4 scheduling preparation and independent verification

Generated 2026-11-19 18:37 UTC. Research only; all inputs HYPOTHETICAL; no approvals; no scheduler implemented.

## 1. Numerical reference (Task 1) - `reference_calculation.json`
- **Fixture A** (review package, 4 columns / 4 beams / 1 slab): EUR 3966.32 direct cost = sum of quantity x BCCA unit price over 11 activities; boundary: direct catalogue cost only (no overheads, VAT, crane/pump/delivery, curing labour bundled in concrete, no waiting cost).
- **Fixture B** (Agent 1 Stage 5.3A `fixture_inputs.json`, 1 column / 1 beam / 1 slab): independent recomputation EUR 1172.5136; Agent 1 reports EUR 1172.5136 -> MATCH. Productive hours match 12/12, costs match 12/12 (`agent1_stage5_3A_comparison.csv`).
- **Agent 1 did not implement fixture A**; its estimate cannot be compared with EUR 3,966.32 (deficiency D1).

## 2. Controlled scheduling inputs (Task 2) - `controlled_scheduling_inputs.json`
Fixture B with: start Mon 2027-01-04 08:00 Europe/Madrid; Mon-Fri 08:00-16:00; HYPOTHETICAL holiday 2027-01-06; capacities by trade {"OF. 1ª ENCOFRADOR": 2, "PEÓN ESPECIAL": 3, "OF. 1ª FERRALLISTA": 2, "OFICIAL 1ª": 1, "VIBRADOR": 1, "INSPECTOR": 1}; 0.5 h inspections in working time; curing 24 h elapsed; striking 24 h (column) / 168 h (beam, slab) elapsed from pour with assumed strength pass; pours inside a 08:00-14:00 delivery window; three HYPOTHETICAL cross-package support dependencies (column -> beam formwork, beam -> slab formwork, slab strip -> beam strip).
Expected schedule (`fixture_expected_schedule.csv`): finish **2027-01-14 16:00**; resource check: no over-use.

## 3. Verification cases (Task 3) - `scheduling_test_cases.json`, `expected_results.csv`
10 cases: FS chain with shift fit, parallel without conflict, shared crew (unique makespan, order free), weekend + approved split + NO_FIT, elapsed curing over a weekend, strength release (conditional / approved / early approval), impossible deadline, missing capacity (null / 0 / insufficient), cycle, and the controlled frame end-to-end. Expected values come from a calendar-arithmetic test oracle (no optimisation).

## 4. Engine usage and IFC4D mapping (Task 4) - `scheduling_engine_usage.md`
Delta to Agent 2's specification: input -> CPM/CP-SAT mapping, conditional dependencies, expected diagnostics, and PMI -> IFC4 (IfcTask, IfcTaskTime WORKTIME/ELAPSEDTIME, IfcRelSequence + IfcLagTime, IfcRelAssignsToProcess, IfcWorkCalendar, resources).

## 5. Engineering gates (Task 5) - `engineering_gate_matrix.csv`, `contract_deficiencies.csv`
- Of the 8 P3 decisions, 6 are needed for the controlled fixture (DR05, DR06, DR07, DR08, DR09, DR15) and used only as HYPOTHETICAL selections; DR10 and DR11 are not needed (single storey, single zone). All 8 require engineering approval for a real project; all remain PENDING.
- 11 contract deficiencies, most important: D3 missing support dependencies in the 5.3A output, D4 inspections as elapsed holds, D5 striking measured from the wrong reference point, D7 lag fields not canonical.

## Preservation
See `preservation_verification.json`.
