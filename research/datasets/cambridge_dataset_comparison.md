# Cambridge vs Ghent vs new candidates

*Cambridge and Ghent figures come from repository evidence (`data/processed/external_inventory/`, the Stage 2.3C/2.3D outputs, and `research/gnn/`). Candidate figures come from the verified sources in [`cambridge_alternative_shortlist.md`](cambridge_alternative_shortlist.md).*

## Cambridge, verified from the repository

| Characteristic | Value | Evidence |
|---|---|---|
| Source | Brilakis, Fitzsimmons, Lu (Cambridge), DOI 10.17863/CAM.53890, CC BY 4.0 | `external_inventory/cambridge_inventory.json` |
| Audited activities | 444,156 | `cambridge_audit/audit_summary.json` |
| Eligible for exploratory supervised learning | 180,137 | `cambridge_feasibility/feasibility_summary.json` |
| Source project IDs (eligible) | 268 (299 in total) | same |
| Conservative independent blocks | 169 (70 train / 99 test) | `cambridge_experiment_design/block_assignments.csv` |
| Target | reported completed-activity elapsed **calendar** days, `(Actual_Finish − Actual_Start)/86400`, *not* verified | `holdout_protocol.json` |
| Predecessors | `Activity_Relationships` present for 404,358 activities | `cambridge_audit/data_dictionary.csv` |
| Planned dates | present on all activities, **possibly revised** | same |
| Calendars | referenced by ID; no working hours or holidays supplied | same |

All the characteristics stated in the brief match the repository.

## Side-by-side

| | **Cambridge** | **Ghent DSLIB** | **e-verse P6** (C01) | **Nodes & Links** (C02) | **Montana DWR** (C04) | **NYC SCA** (C07) | **SCHEPENDOMLAAN** (local) |
|---|---|---|---|---|---|---|---|
| Access | public, CC BY 4.0 | public, licence unclear | public, **rights unclear** | on request | on request | public | public, CC BY 4.0 |
| Independent projects | 169 blocks | 17 groups | ≤59 names; ~30 progressed; grouping pending | 77 | 730 | thousands (phase rows) | 1 |
| Activity level | yes | yes | yes | yes | work items | no (phases) | yes |
| Genuine predecessors | as exported (91%) | yes | **yes: typed + lags** | yes | inferred | no | sparse (48 links) |
| Calendars | IDs only | 8 h assumed | **explicit tables** | ? | daily records | n/a | 8 h, Mon–Fri |
| Actual dates | reported timestamps | tracking actuals (71% exactly = plan) | P6 status dates in updates | ? | **daily inspector records** | phase actuals | **none** |
| Baseline genuine? | possibly revised | yes | `target_*` = current plan | multiple versions | n/a | original planned end | yes |
| Text / trade | anonymised descriptions | trade names (NL/EN/FR) | real task names, WBS, codes | ? | standard work items | phase names | trade names (NL) |
| BIM link | no | no | no | no | no | no | **yes** |
| Domain | UK, mixed | BE buildings | Egypt/ME buildings + industrial + infrastructure | ? | MT highways | NYC schools | NL residential |

## Which datasets genuinely improve training possibilities?

1. **None replaces Cambridge as the training set.** No accessible dataset matches its 169 independent blocks of activity-level schedules with reported actual dates.
2. **e-verse P6 is the only accessible addition with real value.**
   - It brings genuine typed dependencies with lags and explicit calendars, so working-day labels become possible.
   - Its domain, region and era differ from Cambridge's. That makes it a meaningful **out-of-distribution test**.
   - Its size (≲30 labelled independent jobs) and unclear rights limit it to **external validation**, not pooled training.
3. **Montana DWR** would add the most *independently recorded* actuals, but it is restricted, about highways, and has no genuine network. It's a separate study, not GNN training data.
4. **Nodes & Links** is the most Cambridge-like candidate (P6 networks, 77 projects), but it requires a data agreement.
5. **Ghent** remains a documented negative result and a possible external test set. **SCHEPENDOMLAAN** remains the only BIM-linked case study, with no labels.
