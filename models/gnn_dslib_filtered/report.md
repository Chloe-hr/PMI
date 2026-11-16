# Duration GNN - dslib_filtered

40 projects in 15 independent groups, 2051 labelled activities, 5-fold project-grouped cross-validation (out-of-fold predictions).

| method | MAE days | MedAE days | MdAPE % | MAE log-ratio | mean project MAE |
|---|---|---|---|---|---|
| plan | 3.369 | 0.0 | 0.0 | 0.1685 | 6.004 |
| median | 3.369 | 0.0 | 0.0 | 0.1685 | 6.004 |
| category | 3.375 | 0.0 | 0.0 | 0.1689 | 6.01 |
| mlp | 3.624 | 0.557 | 11.11 | 0.2189 | 6.382 |
| gnn | 3.562 | 0.581 | 10.9 | 0.2186 | 6.8 |

GNN vs best non-graph method (`plan`): +0.796 days MAE per project, 95 % bootstrap CI [-0.247, 1.897] -> no significant improvement.
