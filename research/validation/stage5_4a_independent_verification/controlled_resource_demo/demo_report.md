# Stage 5.4B controlled resource demonstration (Task 6)

> **Hypothetical scheduling fixture, not an IFC-validated construction case.** No IFC model supports these quantities. Geometry is declared in the builder and quantities follow stated rules. Every resource, calendar, hold and release value is a test input. All engineering approvals remain PENDING, and nothing here is eligible for real-project scheduling.

| Result | Value |
| --- | --- |
| CPM baseline, capacities ignored | Completes Fri 12 Feb 2027 15:50 (16,310 min). It is **infeasible**: 29 conflict intervals across all 11 constrained pools. |
| Capacity-feasible schedule | Completes **Mon 1 Mar 2027 10:05 Europe/Madrid** (40,445 min elapsed from Mon 1 Feb 08:00) |
| Lower bound | 40,445 min, so the gap is 0 and the schedule is **proven optimal for the declared model** |
| Direct reference cost | **€5,103.33** (€5,103.32664), identical for both schedules |
| Independent feasibility checks | 242 of 242 passed |
| Build time | About 4 s (`scripts/build_controlled_resource_demo.py`) |

The visual comparison is in [report.html](report.html). It shows two Gantt charts on one time axis and per-resource utilization bands for both schedules. It works in light and dark mode, has hover tooltips, and links to the data tables.

## Scope

The fixture has two zones, W and E: four columns, four beams and two slab sections, giving 10 work packages and 70 activities.

**Geometry.**
- **Columns:** 0.4 × 0.4 m at the corners of a 6.0 × 5.0 m grid, 0–3.5 m high.
- **Beams:** 0.3 × 0.5 m between column faces, at 3.0–3.5 m.
- **Slab:** 0.2 m thick on top. It is split by a construction joint at x = 3.0 m into S-W and S-E.

**Zones.** S-W, C1, C3 and B3 form zone W. S-E, C2, C4 and B4 form zone E. Edge beams B1 and B2 support both slab sections and belong to both zones (W+E). Four columns cannot form two independent bays, so this is the adjustment the brief allowed.

| Element | Concrete m³ | Formwork m² | Rebar kg (explicit BOQ) |
| --- | ---: | ---: | ---: |
| C1–C4 (each) | 0.56 | 4.80 | 75 |
| B1, B2 (each, 5.6 m clear) | 0.84 | 7.28 | 125 |
| B3, B4 (each, 4.6 m clear) | 0.69 | 5.98 | 105 |
| S-W, S-E (each) | 3.456 | 13.90 | 290 |

The rules match the Stage 5.3A fixture:
- Column forms cover four faces up to the beam soffit.
- Beam forms cover two sides plus the soffit.
- Slab forms cover the soffit, less the column and beam top footprints. Edge and joint stop-ends are excluded.
- The builder asserts that no two concrete bodies share positive volume.

## Durations and costs

Every productive duration and cost comes from the **unchanged Stage 5.3A `estimate_operation()`**. It uses the selected BCCA December 2023 V02 primary references (05HAC00015, 05HEM00001/51/101, 05HHP00003, 05HHJ00003, 05HHL00003 and 05HED00001) and the fixed crew modes from the resource contract:

- **HYP-FORM:** 2 encofradores and 1 peón.
- **HYP-REBAR:** 2 ferrallistas.
- **HYP-CONC:** 2 peones, 1 oficial and 1 vibrator.

Each pour also passes its drawn supply rate as the Stage 5.3A throughput bound. Durations are rounded up to the proposed **5-minute** tick; for example, S-W-FORM is 229.35 → 230 min.

The published unit price controls each cost line, exactly as in Stage 5.3A. Inspections, holds and reservations carry no cost. The total excludes tax, overhead and present-day Barcelona pricing. See [activities.csv](activities.csv) and [work_packages.csv](work_packages.csv).

## Resources and where they compete

All values follow the [resource contract](../resource_contract.json) and are hypothetical, explicit inputs.

| Resource | Capacity | Basis | Competition created |
| --- | ---: | --- | --- |
| OF1_ENCOFRADOR | 2 workers | Working time, project calendar | One formwork crew serves all 10 FORM and 10 STRIP activities |
| OF1_FERRALLISTA | 2 workers | Working time | One rebar crew serves all 10 REBAR activities |
| PEON_ESPECIAL / OFICIAL_1 | 5 / 2 | Working time | Shared by the form and concrete crews |
| VIBRADOR | 2 machines | Working time | At most two simultaneous pours |
| INSPECTOR | 1 | Working time, **10:00–12:00** | 10 pre-pour inspections, 30 min each |
| CONCRETE_SUPPLY | 6 m³/h | Rate, **08:00–14:00 delivery** | Column and beam pours draw 3, slab pours draw 6, so a slab pour excludes every other pour |
| COL_FORM_SET | 2 sets | Continuous reservation | Four columns |
| BEAM_FORM_SET | 3 sets | Continuous reservation | Four beams |
| SLAB_PANEL_SET | 2 sets | Continuous reservation | Never binds |
| BEAM_PROP | 9 pieces (B1/B2 3 each, B3/B4 2 each) | Continuous reservation | A separate prop pool |
| SLAB_PROP | 10 pieces (6 per section) | Continuous reservation | A separate prop pool |
| CRANE, CONCRETE_PUMP | 0 | Explicit none | Direct chute discharge and manual placement (declared method) |

Each activity's calendar is the intersection of the project calendar (Mon–Fri 08:00–16:00) and the calendars of every resource it uses. There are no exceptions. **No date exceptions are declared.** Regional holidays are user input: if Monday 1 March 2027 is declared non-working in Andalusia, the completion date moves.

## Dependencies and reservations

There are 98 FS dependencies with zero elapsed lag ([dependencies.csv](dependencies.csv)).

- **Within each element:**
  - Columns are cage-first (REBAR → FORM).
  - Beams and slabs are formwork-first (FORM → REBAR).
  - Then come INSP → POUR → CURE (24 h).
  - POUR → STRIKE: 24 h for columns, 168 h for beams and slabs, measured from pour finish, with an explicit `hypothetical_pass_at_minimum` strength event.
  - STRIP follows both CURE and STRIKE.
- **Support rules (hypothetical DR09):**
  - A beam is formed only after both supporting columns are cured and stripped.
  - A slab section is formed only after its three supporting beams are cured.
  - A beam is stripped only after every slab section it supports is stripped. B1 and B2 therefore wait for both sections.

There are 16 continuous reservations ([reservations.csv](reservations.csv)). Each runs from the element's FORM start to its STRIP finish, with `return_lead_minutes` stated explicitly as 0 and reshoring not permitted. This holds every set and prop through nights, weekends, curing and the 168 h striking period.

## CPM baseline and conflicts

Without capacities, all four columns start together and both slab sections run in parallel. [cpm_resource_conflicts.csv](cpm_resource_conflicts.csv) lists 29 over-capacity intervals:

- **Crews:** 8 on encofradores (peak 8 of 2), 5 on ferrallistas.
- **Inspector:** 3 (peak 4 of 1).
- **Concrete supply:** 3 (peak 12 of 6 m³/h).
- **Shared labour and vibrators:** 2 each on peones, oficiales and vibrators.
- **Reservation pools:** 1 each on column sets, beam sets, beam props (10 of 9) and slab props (12 of 10).

## Capacity-feasible schedule

The schedule is [resource_feasible_schedule.csv](resource_feasible_schedule.csv), with occupancy intervals in [resource_occupancy.csv](resource_occupancy.csv) and utilization in [resource_utilization.csv](resource_utilization.csv).

1. **Columns:** C1 and C3 on Monday 1 Feb, then C2 and C4 on Tuesday 2 Feb, once the first two column sets are stripped.
2. **Beams:** B3 on 2 Feb, B1 and B2 on 4 Feb.
3. **Zone W slab:** S-W formed 8 Feb, poured 9 Feb 10:30–11:35.
4. **Zone E:** B4 cannot be formed until B3 releases its beam set and props. That happens after S-W is stripped, following 168 h striking, so B4 is formed on 16 Feb. S-E is formed on 18 Feb and poured on 19 Feb.
5. **Tail:** S-W and then B3 are stripped on 16 Feb, which releases B3's set and props for B4. After the S-E striking minimum, the single formwork crew strips S-E (Fri 26 Feb 12:30–14:40) and B1 (14:40–15:50). B2 and B4 do not fit in Friday's remaining 10 minutes, so they are stripped on Monday 1 March 08:00–10:05.

The reservation chain, not the crews, explains why the feasible schedule is 24,135 min longer than CPM. The zone order is a genuine choice: the mirrored E-first schedule has the same makespan.

## Proof of optimality

[lower_bound_proof.json](lower_bound_proof.json) gives the full argument. In summary:

1. **Relax** the working-time capacities but keep precedence, calendars and **every reservation constraint exactly**, encoded as disjunctions:
   - Two column sets for four unit intervals holds exactly when the intervals split into two chains.
   - Three beam sets, and the 9-piece beam prop pool (3+3+2+2 = 10, while any three need at most 8), each hold exactly when not all four beam intervals share a point. For intervals, that means some ordered pair is disjoint.
   - Slab props (6+6 > 10) hold exactly when the two slab intervals are disjoint.
2. **Enumerate** the choices: 60 column chain structures × 12 beam pairs × 2 slab orders = 1,440. Of these, 1,320 create cycles. For each of the other 120, the earliest-start CPM is the exact relaxed optimum.
3. **Strengthen** each choice with single-resource bounds for activities that occupy a whole pool: the formwork crew, the rebar crew and the inspector. For tail sets of up to seven activities, the bound is exact and non-preemptive: every order is tried, each activity on its own calendar.
4. **Bound.** The minimum over choices is 40,445 min, set by the formwork-crew tail after the last slab is stripped. The independent scheduler (serial schedule generation, 1,200 runs) attains 40,445. Therefore the schedule is **optimal for this declared model**.

**Scope of the claim.** It holds for the 5-minute tick, non-interruptible activities, zero return lead time and these exact inputs. It says nothing about real construction.

[feasibility_checks.csv](feasibility_checks.csv) re-verifies the schedule using minute timestamps only, without the scheduler's tick masks:
- durations;
- each calendar of each activity;
- 98 precedences;
- strike-from-pour;
- per-minute capacity of every pool, including continuous reservations.

**Deadlock-prone orders.** Forming B3, B4 and one edge beam first uses all three beam sets and 7 of the 9 beam props. The other edge beam then needs a set and 3 props, but neither slab can be formed without it, so no beam can ever be stripped to release them. A greedy scheduler can walk into this; a CP-SAT model with the reservations expressed as span intervals rules it out.

## Acceptance criteria for the Stage 5.4B solver

The full list is in [expected_results.json](expected_results.json). In summary:

1. **Input:** consume [fixture_inputs.json](fixture_inputs.json) unchanged, with a 5-minute tick and durations of ceil(duration_minutes / 5) ticks.
2. **Feasibility:** every check in `feasibility_checks.csv` holds, covering calendars, FS precedence, strike-from-pour, per-minute capacity, and continuous reservations from FORM start to STRIP finish.
3. **Objective:** the makespan equals **40,445 min**, with completion at **2027-03-01T10:05+01:00**, and the solver status is OPTIMAL. Anything lower indicates a modelling error. Anything higher, or FEASIBLE without proof, fails.
4. **Baseline:** CPM completes at 2027-02-12T15:50+01:00 and reproduces conflicts on all 11 constrained pools.
5. **Cost:** €5,103.32664, unchanged between schedules.
6. **Approvals:** all stay PENDING, and `real_project_eligible` stays false.

## Open points

- Several values are hypothetical choices that need engineering review before any real use:
  - support and prop-retention rules;
  - zero return lead time;
  - direct chute discharge with no crane or pump;
  - the 10:00–12:00 inspector window;
  - the 6 m³/h supply rate;
  - all quantities.
- As noted in Task 5 (O1), the register has no approval ids for reservations.
- The Task 4 reference cases remain the small-case optimality tests. This fixture is the scale test.

## Reproduce

~~~powershell
& .\.venv\Scripts\python.exe -B 'research/validation/stage5_4a_independent_verification/controlled_resource_demo/scripts/build_controlled_resource_demo.py'
~~~

The build uses `.venv`, because the Stage 5.3A estimator imports the construction package. It regenerates every file in this folder deterministically, apart from `runtime_seconds`.
