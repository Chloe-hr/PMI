# Stage 5.4B resource contract (Task 5)

This contract tells the Stage 5.4B scheduler which resources exist, how much of each is available and when, what each activity occupies, and when reusable formwork and props are released. Every field maps to an existing Stage 5.3A or Stage 5.4A field, or is marked as new.

**Status:** proposed for Agent 1. It sets no engineering values and approves nothing. All 75 register approvals remain PENDING.

| File | Contents |
| --- | --- |
| [resource_contract.json](resource_contract.json) | Principles, enumerations, 13 entities with field rules, preflight capacity policy, 11 validation rules, CP-SAT semantics, the controlled fixture expressed in the contract, open items |
| [resource_contract_mapping.csv](resource_contract_mapping.csv) | 76 rows mapping every contract field to its Stage 5.3A, Stage 5.4A and Agent 2 preparation source |
| [scripts/check_resource_mapping.py](scripts/check_resource_mapping.py) | Checks that all 121 cited source paths and code tokens exist in the current files. It passes, and a negative probe confirmed it fails on a bad path. |

## The two occupancy bases

| | `working_time` | `continuous_elapsed` |
| --- | --- | --- |
| Used by | Trades, equipment, inspectors, supply draw | Reusable formwork panels, props, shoring |
| Occupied | Only on the ticks of an activity's working segments | Every tick from the start event to the satisfied release condition |
| Calendar | The resource's own calendar; capacity is 0 off-calendar | None. Nights, weekends, holidays and curing all count. |
| Stage 5.4A equivalent | `resources` on productive and inspection tasks | None. 5.4A elapsed holds carry no resources. |
| CP-SAT | One interval per segment in a cumulative constraint | One span interval in a cumulative constraint (Task 4, RC05a/b) |

A formwork panel set or prop is reserved from its start event, normally the FORM `activity_start`. It is released only when **all** events in `release_condition.all_of` have occurred, plus an explicit `return_lead_minutes`. For panels the release event is their own STRIP finish. For beam soffit props it is B-STRIP finish, which the Agent 2 hypothetical rule orders after S-STRIP. Validation rule V8 requires the reservation to contain every working segment of the covered activities, so it necessarily spans the pour, the curing hold, the strength release and stripping. Reshoring is `not_permitted` unless separately approved and modelled, because the selected item 05HED00001 excludes re-propping.

## Decisions the contract makes

- **No engineering defaults (P1).** Every value is explicit and carries one of the five Stage 5.3A input states. These values have no defaults:
  - capacity;
  - calendar, including the use of the project calendar, which must be stated;
  - crew mode units;
  - reservation quantity;
  - release condition;
  - return lead time;
  - supply rate;
  - every split parameter.

  A missing value is `MISSING_INPUT`. It is never 0, never unlimited and never a library value.
- **Reusable assets versus consumables (P4, P5).**
  - BCCA prices formwork timber and steel props as amortised material coefficients. For example, CE00200 prop is 0.009 u/m² on the beam and 0.01 u/m² on the slab, which gives 0.104 props for the 10.4 m² slab.
  - These are cost fractions, not piece counts. The contract forbids sizing reservations from them.
  - Reservations produce no cost, so the €1,172.5136 boundary is unchanged.
  - Consumables (concrete, steel, release agent) stay as Stage 5.3A material lines with no 5.4B stock constraint.
- **Crew modes and simultaneous occupancy.**
  - A mode is a fixed set of trade and equipment units, all occupied for every working segment. This is the Stage 5.3A `simultaneous_fixed_crew` mode; `sequential_phases` remains unsupported.
  - Durations belong to Stage 5.3A per mode (P3). Multi-mode scheduling therefore needs one 5.3A estimate per mode, and 5.4B must never rescale a duration itself.
  - Rule V4 checks that units × scheduled hours ≥ the 5.3A worker and machine hours.
- **Inspectors.**
  - An inspection is a working-time activity on the inspector's own calendar, as in 5.4A `kind=inspection`. It has an explicit unit count, which 5.4A hard-codes to 1.
  - It emits a pass event. A `missing` pass gives a conditional schedule, mirroring the 5.4A strength release; `failed` blocks successors.
- **Concrete supply.**
  - `CONCRETE_DELIVERY` becomes a `supply_source`: a rate pool in m³/h on a delivery calendar, shared by every pour.
  - The pump is equipment.
  - The pour duration remains a Stage 5.3A calculation: the `throughput:` bound, which requires `concurrent_with_placement`.
  - Pouring may split only with an explicit cold-joint authorization.
- **Split work and restart.** `split_allowed` requires all of the following, each stated explicitly:
  - an authorization reference;
  - `max_segments` and `min_segment_minutes`;
  - whether resources are released or retained during gaps;
  - a restart overhead, stated even when it is 0;
  - same-mode restart;
  - whether voluntary pauses are allowed.

  5.4A `fit_work` implicitly releases resources, adds no overhead and fills slots greedily. Those become declared choices.
- **Missing and insufficient capacity.** The preflight codes are:
  - from Stage 5.4A: `MISSING_INPUT`, `IMPOSSIBLE_CREW`, `NO_FIT`, `INFEASIBLE_DEADLINE`;
  - from Stage 5.3A, now as a code: `EXPLICIT_NONE_REQUIRED`;
  - new: `NO_ELIGIBLE_MODE`, `SPLIT_NOT_AUTHORIZED`, `RESERVATION_UNRELEASED`, `TICK_MISALIGNED`, `RELEASE_CONDITIONAL`.

  An affected activity and all its successors are blocked, and the solver never receives relaxed values (P7). An explicit none (capacity 0, `explicit_none=true`) is distinct from missing (P6), matching Stage 5.3A.

## Mapping summary

Of 76 mapped fields:

| Status | Count | Meaning |
| --- | ---: | --- |
| direct | 33 | Same value and meaning in an existing source |
| derived | 15 | Computed from existing fields, for example mode units = 5.3A crew + `equipment_capacity_by_class` |
| renamed | 5 | Same content, new name, for example stable `resource_id` versus the BCCA display name |
| split | 1 | Labour capacity: per-operation crews in 5.3A, shared pool only in Agent 2 preparation |
| conflict | 1 | Calendar timezone: Europe/Paris in 5.3A versus Europe/Madrid in preparation (Task 3 N4) |
| new_required | 19 | No source exists: reservations, release lead time, split parameters, inspection pass events, resource calendars and their ids, new preflight codes |
| new_optional | 2 | Date-specific capacity, daily supply volume cap |

## The controlled fixture under the contract

`controlled_fixture_inputs.json` and `controlled_scheduling_inputs.json` hold the fixture's values. `controlled_fixture_instance` in the contract copies them without adding any:

- **Trades:** four labour pools: encofrador 2, peón especial 3, ferrallista 2, oficial 1.
- **Equipment:** VIBRADOR 1. CRANE, CONCRETE_PUMP and CONCRETE_DELIVERY are explicit none.
- **Inspector:** INSPECTOR 1.
- **Crew modes:** the three modes HYP-FORM, HYP-REBAR and HYP-CONC, where HYP-CONC includes the vibrator.
- **Delivery window:** Agent 2's 08:00–14:00, with no rate.

Three items have **no source** and are therefore `missing`:

1. **Formwork panel sets and props:** capacities, per-element quantities, release conditions and return lead times.
2. **Inspection pass events:** only criterion text exists.
3. **An explicit inspector calendar:** 5.4A applies the project calendar implicitly. The instance records that as the declared choice.

For real projects, item 1 blocks scheduling until supplied. For the hypothetical fixture, Agent 1 may declare the reservations as excluded from the fixture model, stating the reason, so that R0-15 and R0-5 keep their Task 4 results. The output must then report reservations as unenforced.

## Open items for Agent 1 and the register owner

1. **O1:** the engineering register has no approval ids for formwork or prop reservations, return lead time or reshoring. They must be added before real release; this contract assigns none.
2. **O2:** inspection pass events are absent from the 5.3A and 5.4A data.
3. **O3:** 5.4A resource ids are non-ASCII BCCA names. The contract proposes stable ids, shown in the fixture instance.
4. **O4:** 5.3A emits one mode per activity, so multi-mode scheduling needs per-mode estimates first.
5. **O5:** a shared supply-rate pool across pours is new. 5.3A uses supply only as a per-pour placement bound.

## Reproduce the mapping check

~~~powershell
& .\.venv\Scripts\python.exe -B 'research/validation/stage5_4a_independent_verification/scripts/check_resource_mapping.py'
~~~

Expected output: `76 mapping rows, 121 source references checked` with exit code 0.
