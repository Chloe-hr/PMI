# Stage 5.4A independent review follow-up

The independent CPM verification found no blocking correctness discrepancy for the three-element fixture. This follow-up reviews the Task 4 cases and Task 5 proposed resource contract. It does not authorize or implement production CP-SAT.

## CPM corrections and disposition

| Finding | Disposition |
| --- | --- |
| N1 | Preserve the 28 normalized edges. Three redundant edges carry useful original or explicit curing prerequisites. |
| N2 | Treat a timestamped recorded strength pass as a fixed absolute lower bound on release finish. The earliest elapsed minimum still starts at pour finish. The backward pass can move the predecessor and minimum toward that date. A regression checks the distinct early and late spans. Test-age-dependent approval events remain outside CPM. |
| N3 | Reject ticks that do not divide 60 and recurring, exception or activity-specific window boundaries that fall off the local grid. Also check UTC alignment after local expansion. Diagnose TICK_MISALIGNED. |
| N4 | Require the Stage 5.3 Europe/Paris and Stage 5.4A Europe/Madrid lineage and equal recurring windows. The Stage 5.4A holiday exception remains a deliberate fixture override. |
| N5 | Existing input and reference hash gates retained. |
| N6 | Keep 15 minutes for baseline reproduction and 5 minutes as the candidate optimization resolution. Coarser aligned ticks can miss delivery windows and produce large date jumps. |

The eight published Stage 5.4A schedule exports reproduced byte-for-byte. All 43 stage tests passed. The finished baseline remains 2027-01-14 16:00 Europe/Madrid with 21 activities, 28 dependencies and the unchanged EUR 1,172.5136 direct reference cost.

## Resource contract fit

| Area | Current implementation and compatibility work for a future authorized implementation |
| --- | --- |
| Calendar intersection | CPM uses the project shift and intersects it with a local activity restriction, such as the pour window. It has neither named resource calendars nor date-specific capacity. Task 4 convention uses the intersection of demanded resource calendars, falling back to the project calendar only when none are used. Adding the project calendar unconditionally would incorrectly prevent RC06's 07:00 start. Explicit project restrictions can be modeled separately where specified. Capacity is unavailable off a resource's calendar. |
| Identity, units and fixed modes | CPM uses BCCA display names and integer headcounts. The contract needs stable IDs, display names, resource classes, units and explicit calendar references. The original fixture's column pour reserves the full HYP-CONC crew, including an official with no modeled BCCA demand. Stage 5.3 stores positive-demand capacity separately. Contract V5 needs an explicit mapping between the selected mode's reservations and the demand-bearing estimate, or a reviewed contract clarification. Do not silently change the duration or strip the extra reservation. |
| Reusable assets | CPM has no physical reusable-asset quantities, reusable capacity, release conditions or lead times. BCCA formwork and prop coefficients are amortized cost data and cannot size a reservation. A future model must preserve a distinct continuous interval through nights, weekends, curing and all release conditions, including covered segments and explicit return lead. Multiple events in all_of are separate from productive demand. |
| Split work | CPM's approved split is greedy, consumes the next available window, releases working resources between segments and has no restart overhead. Task 5 requires explicit authorization, segment count, minimum length, retention, restart overhead, same mode and voluntary pause policy. RC10c requires a later start to meet both minimum lengths. An eventual optimization must use segment-specific working occupancy and apply or explicitly reject unsupported retention and restart choices. Pour splits require a separate cold-joint authorization. |
| Shared concrete supply | CPM enforces 08:00?14:00 pour windows only. The Stage 5.3 per-pour throughput bound does not enforce shared rate. RC11 needs a separate rate pool in compatible m3/h units with declared supply calendar and per-pour draw and a fixed estimate for that mode. Explicit none for delivery equipment is distinct from a supply window or rate. No supply rate is assumed. |
| Inspections and conditions | CPM retains one working inspector and a criterion; it has no distinct machine-readable inspection pass. The new contract requires explicit inspector calendar and pass event. A missing pass must stay conditional and a failed pass blocks successors. Strength releases in the original fixture remain explicitly hypothetical. |
| Costs and pending approvals | CPM carries the frozen reference cost and preserves all 75 pending approvals. Future occupancy, inspection capacity and supply-rate checks must not add BCCA prices or grant approval. |

## Three-element regression scope

The original R0-15 and R0-5 fixture remains a regression for the stated labor, vibrator, inspector occupancy and delivery-window scope. **Continuous formwork panel and prop reservations are excluded and unenforced.** Physical counts, pool capacities, release/return conditions and lead times were not supplied. Shared delivery rate and stock constraints are also outside this fixture. The historical inspector assumption uses the project calendar and models occupancy only; an independent inspection pass is missing for the new contract. The original result is therefore not a complete contract-conformant scheduling input without a documented fixture exception or additional explicit hypothetical inputs. No replacement values are introduced.

The 22 independent cases were reviewed as test-oracle inputs. Production CP-SAT remains on hold pending Task 6 and final Task 7 authorization.
