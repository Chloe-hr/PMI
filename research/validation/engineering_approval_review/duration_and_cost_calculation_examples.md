# Stage 5.3 engineering estimation method and worked examples

Generated 2026-11-19 17:55 UTC. Research only - not production code. Method follows Agent 2's `research/architecture/stage5_0/engineering_estimation_specification.md`.

## 1. Method
For an activity with allocated physical quantity Q (in the BCCA declared unit) and BCCA coefficients c[t] (worker-hours per unit, trade t) and k[e] (machine-hours per unit, class e):

1. **Labour requirement:** H[t] = Q x c[t] (summed over every allocated quantity of the activity).
2. **Equipment requirement:** E[e] = Q x k[e]. An equipment class that the activity needs but BCCA does not list (crane, pump, concrete delivery) is **unresolved**: the user must declare capacity or an explicit none; otherwise the activity is blocked.
3. **Productive duration (lower bound, fixed simultaneous crew):** D_prod = max( H[t] / n[t] for each trade, E[e] / m[e] for each machine class, approved process minimum ). The largest term is the bottleneck. A trade with positive demand and zero crew makes the mode invalid (blocked, not infinite). Different trades work simultaneously in the same crew; the slowest trade sets the duration. Crew members may be reserved for the whole duration even when their own demand finishes earlier - report reserved hours (n[t] x D_prod) separately from demanded hours H[t].
4. **Waiting and strength development:** curing and striking are `elapsed_hold` activities (canonical `ConstructionActivity.kind`) whose duration comes from the engineer (AP-W-CURE, AP-DR07, AP-DR08). They consume calendar time, not crew. BCCA has no coefficient for them - curing labour is already inside the concrete coefficient and must not be added again (DC03).
5. **Calendar conversion:** productive working hours are mapped onto the project calendar's working windows; elapsed holds run in elapsed (24 h) time unless the engineer specifies working time (`ActivityDependency.lag_basis`).
6. **Direct cost:** Cost = Q x BCCA unit price. The labour/equipment/material split is the arithmetic sum of the decomposition lines (stage5_3_reference_selection.csv; split sums equal the published price to rounding). Bundled operations (vibration, curing labour, cleaning, release agent, tying) are counted once because they are inside one coefficient; the only separate stripping line is FRM-STRIP for 05HEM* formwork (DC02).
7. **Not allowed:** allocation percentages to split a bundled coefficient into sub-activities; generic reinforcement ratios; default curing/striking times; zero for unknown quantities.

## 2. Worked example - HYPOTHETICAL fixture (software test only)
**All inputs below are HYPOTHETICAL** (`controlled_demo_input_template.json` -> `hypothetical_test_fixture`): 4 columns 0.30x0.30x3.00 m; 4 beams 0.30x0.50x5.00 m; 1 slab 5.30x5.30x0.20 m; no openings. Formwork face rule: HYPOTHETICAL: formwork faces = 4 column faces full height; beam soffit + 2 sides full depth; slab soffit full area (no deduction of beam tops). Rebar kg are stated test values, NOT ratios.. Crews: [{"id": "HYP-FORM", "workers_by_trade": {"OF. 1ª ENCOFRADOR": 2, "PEÓN ESPECIAL": 1}}, {"id": "HYP-REBAR", "workers_by_trade": {"OF. 1ª FERRALLISTA": 2}}, {"id": "HYP-CONC", "workers_by_trade": {"PEÓN ESPECIAL": 2, "OFICIAL 1ª": 1}}]. Equipment: {"VIBRADOR": 1, "CRANE": 0, "CONCRETE_PUMP": 0, "note": "HYPOTHETICAL explicit none for crane/pump (hand placement assumed for the test)"}. Calendar 8 h/day Mon-Fri. BCCA coefficients: stage5_3_reference_selection.csv.

| activity | code | quantity | worker_hours | machine_hours | crew | bound | productive_h | working_days_at_8h | direct_cost_eur |
|---|---|---|---|---|---|---|---|---|---|
| COL-REBAR | 05HAC00015 | 150 kg | OF. 1ª FERRALLISTA 3.00 h | - | HYP-REBAR {"OF. 1ª FERRALLISTA": 2} | OF. 1ª FERRALLISTA 1.50 h | 1.50 | 0.19 | 228.00 |
| COL-FORM | 05HEM00001 | 14.4 m2 | OF. 1ª ENCOFRADOR 3.60 h, PEÓN ESPECIAL 1.44 h | - | HYP-FORM {"OF. 1ª ENCOFRADOR": 2, "PEÓN ESPECIAL": 1} | OF. 1ª ENCOFRADOR 1.80 h, PEÓN ESPECIAL 1.44 h | 1.80 | 0.23 | 232.70 |
| COL-CONC | 05HHP00003 | 1.08 m3 | PEÓN ESPECIAL 0.65 h | VIBRADOR [h] 0.22 h | HYP-CONC {"PEÓN ESPECIAL": 2, "OFICIAL 1ª": 1} | PEÓN ESPECIAL 0.32 h, VIBRADOR [h] 0.22 h | 0.32 | 0.04 | 122.67 |
| BEAM-FORM | 05HEM00051 | 26 m2 | OF. 1ª ENCOFRADOR 9.10 h, PEÓN ESPECIAL 3.90 h | - | HYP-FORM {"OF. 1ª ENCOFRADOR": 2, "PEÓN ESPECIAL": 1} | OF. 1ª ENCOFRADOR 4.55 h, PEÓN ESPECIAL 3.90 h | 4.55 | 0.57 | 421.98 |
| SLAB-FORM | 05HEM00101 | 28.09 m2 | OF. 1ª ENCOFRADOR 15.45 h, PEÓN ESPECIAL 5.62 h | - | HYP-FORM {"OF. 1ª ENCOFRADOR": 2, "PEÓN ESPECIAL": 1} | OF. 1ª ENCOFRADOR 7.72 h, PEÓN ESPECIAL 5.62 h | 7.72 | 0.97 | 601.69 |
| BEAM-REBAR | 05HAC00015 | 300 kg | OF. 1ª FERRALLISTA 6.00 h | - | HYP-REBAR {"OF. 1ª FERRALLISTA": 2} | OF. 1ª FERRALLISTA 3.00 h | 3.00 | 0.38 | 456.00 |
| SLAB-REBAR | 05HAC00015 | 400 kg | OF. 1ª FERRALLISTA 8.00 h | - | HYP-REBAR {"OF. 1ª FERRALLISTA": 2} | OF. 1ª FERRALLISTA 4.00 h | 4.00 | 0.50 | 608.00 |
| BEAM-CONC | 05HHJ00003 | 3 m3 | OFICIAL 1ª 0.60 h, PEÓN ESPECIAL 1.80 h | VIBRADOR [h] 0.90 h | HYP-CONC {"PEÓN ESPECIAL": 2, "OFICIAL 1ª": 1} | OFICIAL 1ª 0.60 h, PEÓN ESPECIAL 0.90 h, VIBRADOR [h] 0.90 h | 0.90 | 0.11 | 355.20 |
| SLAB-CONC | 05HHL00003 | 5.618 m3 | OFICIAL 1ª 1.12 h, PEÓN ESPECIAL 3.37 h | VIBRADOR [h] 1.69 h | HYP-CONC {"PEÓN ESPECIAL": 2, "OFICIAL 1ª": 1} | OFICIAL 1ª 1.12 h, PEÓN ESPECIAL 1.69 h, VIBRADOR [h] 1.69 h | 1.69 | 0.21 | 666.13 |
| FRM-STRIP (cols) | 05HED00001 | 14.4 m2 | OF. 1ª ENCOFRADOR 0.43 h, PEÓN ESPECIAL 2.16 h | - | HYP-FORM {"OF. 1ª ENCOFRADOR": 2, "PEÓN ESPECIAL": 1} | OF. 1ª ENCOFRADOR 0.22 h, PEÓN ESPECIAL 2.16 h | 2.16 | 0.27 | 57.60 |
| FRM-STRIP (beams+slab) | 05HED00001 | 54.09 m2 | OF. 1ª ENCOFRADOR 1.62 h, PEÓN ESPECIAL 8.11 h | - | HYP-FORM {"OF. 1ª ENCOFRADOR": 2, "PEÓN ESPECIAL": 1} | OF. 1ª ENCOFRADOR 0.81 h, PEÓN ESPECIAL 8.11 h | 8.11 | 1.01 | 216.36 |

Direct cost total (hypothetical quantities): 3966.32 EUR, of which labour 1729.03, equipment 5.10, material 2226.48 (split recomputed from decomposition lines).

### Reading the example
- COL-FORM: the carpenter term (2 carpenters) and the helper term (1 helper) are compared; the larger is the productive duration. Adding a second helper would not shorten it if the carpenter term is the bottleneck.
- CONC activities: the vibrator term is computed from BCCA machine-hours. The hypothetical fixture declares crane = 0 and pump = 0 explicitly; with `null` instead the concrete activities would be **blocked** (unresolved equipment).
- Curing: no row - it is an `elapsed_hold` of HYPOTHETICAL 24 h after each pour, and striking holds of {'columns_sides': 24, 'beams_slab_soffit': 168} h (arbitrary test values). No curing labour or cost is added (bundled in the concrete coefficient).
- FRM-STRIP appears twice because column-side and beam/slab-soffit striking are released by different criteria; the area is the same as the corresponding formwork item, so stripping is counted once per formwork area.

## 3. Bundled coefficients that cannot be allocated to separate scheduling activities
| code | activity | bundled |
|---|---|---|
| 05HAC00015 | COL-REBAR | cutting/bending/tying inside ferrallista hours |
| 05HAC00015 | BEAM-REBAR | cutting/bending/tying inside ferrallista hours |
| 05HAC00015 | SLAB-REBAR | cutting/bending/tying inside ferrallista hours |
| 05HEM00001 | COL-FORM | release agent and cleaning inside formwork labour |
| 05HEM00051 | BEAM-FORM | release agent and cleaning inside formwork labour |
| 05HEM00101 | SLAB-FORM | release agent and cleaning inside formwork labour |
| 05HHP00003 | COL-CONC | curing labour and bottom cleaning inside concrete labour - cannot be split into a separate curing activity |
| 05HHJ00003 | BEAM-CONC | curing labour and bottom cleaning inside concrete labour - cannot be split into a separate curing activity |
| 05HHL00003 | SLAB-CONC | curing labour and bottom cleaning inside concrete labour - cannot be split into a separate curing activity |
| 05HED00001 | FRM-STRIP | cleaning and repair inside stripping labour |

If the schedule needs curing, cleaning or release-agent application as separate activities, their labour must come from a different, approved source; BCCA cannot be split without inventing percentages.
