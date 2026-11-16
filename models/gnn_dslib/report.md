# Duration GNN - dslib

53 projects in 17 independent groups, 2712 labelled activities, 5-fold project-grouped cross-validation (out-of-fold predictions).

| method | MAE days | MedAE days | MdAPE % | MAE log-ratio | mean project MAE |
|---|---|---|---|---|---|
| plan | 2.69 | 0.0 | 0.0 | 0.1589 | 4.78 |
| median | 2.69 | 0.0 | 0.0 | 0.1589 | 4.78 |
| category | 2.69 | 0.0 | 0.0 | 0.1589 | 4.78 |
| mlp | 3.092 | 0.297 | 6.81 | 0.2149 | 5.164 |
| gnn | 3.013 | 0.279 | 5.32 | 0.2026 | 5.247 |

GNN vs best non-graph method (`plan`): +0.467 days MAE per project, 95 % bootstrap CI [0.288, 0.636] -> no significant improvement.
