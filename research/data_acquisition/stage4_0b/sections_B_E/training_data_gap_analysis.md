# Training-data gap analysis (Sections B-E)

## Question
Can any acquired dataset support `y = log(actual_duration / engineering_duration)` (research hypothesis, not an approved protocol)?

## Requirements for one valid record
1. Actual activity duration with known calendar semantics (working vs calendar days).
2. For the same activity: physical quantity, unit, productivity basis and crew assumptions, so that `engineering_duration = quantity x h_per_unit / (crew x hours_per_day)` can be computed in compatible units.
3. Planning-time features recorded before execution (quantity, work type, method, crew, predecessors, lags, resource limits).
4. Project grouping for leakage-safe validation (many independent projects).

## Findings per dataset
| Dataset | 1 actual duration | 2 engineering inputs | 3 planning-time features | 4 groups | Eligible |
|---|---|---|---|---|---|
| D4 Thiele 2020 | No activity actuals (monthly cost-account progress + dated invoices only) | Planned quantity and production rate per estimate line; crews named but no daily headcount | Plan network + estimate are pre-execution | 8 projects, one contractor | No |
| D6 DSLIB buildings | Tracking periods (Stage 3.5: 53 projects / 17 groups labelled) | No quantities | Baseline network, resources | 17 independent groups | No (no engineering duration) |
| D7 Cambridge | Reported elapsed calendar days | No quantities | Activity text, type, region | 70 dev blocks (locked set protected) | No |
| D5 RestageIFC | Phase ActualFinish only (11 of 12) | IFC quantities exist; no starts/crews | Phase assignment | 1 project | No |
| D1/D2 BCCA/CERP | n/a (catalogue) | Person-h per unit (estimate) | n/a | n/a | Not training data |

## Leakage risks identified
- D4 `Final Qty`, `Final Cost`, `Final Rate`, monthly AQ/AC/EV and `%C Claim` columns are post-execution: must never be features.
- D4 `Budget & Revenue` contract quantities after variations are post-award changes.
- D7 precedence may contain execution-period edits (Stage 4.0A).
- Catalogue productivity (D1) must not be presented as observed productivity; using it both to build the engineering estimate and as a feature is allowed only as the baseline term.

## What would close the gap
- RC building projects (preferably Spanish) where the same activity has: IFC-linked quantities, planned crew and calendar, and recorded actual start/finish (e.g. daily site reports or P6/MS Project progress updates), across many independent projects.
- Until then: Stage 5.6 is NO-GO; engineering-based planning (5.1-5.4, 5.7) does not depend on it.

## Values a PMI user must enter or approve
Crew size per trade; working hours per day and calendar (Catalan holidays); productivity adjustment factors; equipment availability; concrete curing and formwork striking times / strength criteria; site resource limits; which BCCA/BEDEC/CYPE item variant applies (e.g. soil consistency, concrete class, formwork material); formwork reuse count; transport distances.
