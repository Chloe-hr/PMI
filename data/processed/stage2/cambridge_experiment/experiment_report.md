# Cambridge Stage 2.3E experiment

Exploratory retrospective estimates of reported completed-activity elapsed calendar days. No labels are independently verified; no prediction-time feature provenance is established.

## Held-out results

| model         |     n |   groups |   mae_days |   rmse_days |         r2 |   median_absolute_error_days |   activity_weighted_mae_days |   macro_group_mae_days |
|:--------------|------:|---------:|-----------:|------------:|-----------:|-----------------------------:|-----------------------------:|-----------------------:|
| median        | 36027 |       99 |    49.3132 |     123.651 | -0.145538  |                       8      |                      49.3132 |                33.3009 |
| ridge         | 36027 |       99 |    50.0789 |     106.324 |  0.153022  |                      24.02   |                      50.0789 |                29.5462 |
| random_forest | 36027 |       99 |    62.4357 |     114.757 |  0.0133384 |                      42.6291 |                      62.4357 |                25.8032 |
| mlp           | 36027 |       99 |    53.0931 |     117.22  | -0.0294674 |                      24.1953 |                      53.0931 |                33.1918 |

Evaluation: 36,027 activities across 99 conservative groups. The dominant conservative block remains wholly in development. The evaluation is distribution-shifted and not representative of the dominant history.

The primary residual and large-error analysis uses median, selected from development folds by mean macro-group MAE before the held-out results were calculated. The table compares every predeclared model on the same frozen evaluation population.

### Target distribution (calendar days)

|       |   calendar_days |
|:------|----------------:|
| count |   36027         |
| mean  |      52.4489    |
| std   |     115.531     |
| min   |       0.0166667 |
| 5%    |       0.333333  |
| 25%   |       2.33333   |
| 50%   |      11.3333    |
| 75%   |      47.3333    |
| 95%   |     256         |
| max   |    2019.67      |

### Project type distribution

| project_type                                 |   activities |
|:---------------------------------------------|-------------:|
| Marine Projects - Ports/Coastal Defence etc. |        14578 |
| Light Rail - Underground (exc. Tunnelling)   |         5926 |
| Clean Water Networks                         |         4046 |
| Electical Networks                           |         3930 |
| Airports                                     |         3335 |
| Rail                                         |         2289 |
| Highways                                     |         1156 |
| Light Rail - Overground                      |          767 |

### Regional distribution

| uk_region                                    |   activities |
|:---------------------------------------------|-------------:|
| South East England and South Central England |        17748 |
| North West England/North Wales               |        11098 |
| Midlands                                     |         6290 |
| East & North East England                    |          891 |

### Group results

| model   | conservative_block_id   |     n |   mae_days |   rmse_days |   median_absolute_error_days |
|:--------|:------------------------|------:|-----------:|------------:|-----------------------------:|
| median  | C-02191bb6e9d7          |    86 |   45.4184  |    91.6082  |                     12.9583  |
| median  | C-0bc4489995ba          |    68 |   21.7298  |    54.7967  |                      8       |
| median  | C-0c73081c7b5f          |    73 |   21.2317  |    52.4496  |                      8       |
| median  | C-0fe68eea4fbc          |   435 |   20.9311  |    30.9822  |                      9.95833 |
| median  | C-11612d520321          |    25 |   35.04    |   134.337   |                      8       |
| median  | C-126aee064486          |   408 |   58.1648  |   110.098   |                      7.70833 |
| median  | C-1446490ff649          |    20 |   52       |   138.476   |                      7.5     |
| median  | C-160f6ba1383c          |   597 |   74.4934  |   118.092   |                     31.2917  |
| median  | C-1776e1429d80          |    74 |   21.9003  |    65.9054  |                      7       |
| median  | C-19831e6a2354          |    79 |   22.8563  |    58.6421  |                      8       |
| median  | C-1cee335aac7d          |    21 |   44.4286  |   119.656   |                      8       |
| median  | C-29572f19e097          |    15 |   47.2     |   122.307   |                      8       |
| median  | C-2b884665b49d          |    17 |   41.3529  |   103.251   |                      8       |
| median  | C-2cff9f391670          |    17 |   48.3529  |   121.243   |                      8       |
| median  | C-2ebe855f43ec          |    70 |   20.3375  |    52.2557  |                      8       |
| median  | C-38e43c5aa16b          |    69 |   23.2699  |    58.6464  |                      8       |
| median  | C-3a1e5609b007          |    78 |   22.9952  |    57.6019  |                      8       |
| median  | C-3c94e3ccde56          |    17 |   53.2353  |   163.529   |                      8       |
| median  | C-3d0105d4b59f          |    81 |   23.9954  |    59.0401  |                      8       |
| median  | C-4414383ac483          |    16 |   40.1641  |   100.364   |                      8       |
| median  | C-47a268534ddf          |    76 |   21.3454  |    52.5473  |                      8       |
| median  | C-4992aa4804ad          |    16 |   46.0625  |   102.683   |                      8       |
| median  | C-4c0a21840538          |    17 |   43.5074  |   110.041   |                      8       |
| median  | C-4c1ac5e08a6c          |    21 |   56.6667  |   135.894   |                      8       |
| median  | C-54187358f639          |   417 |   26.2367  |    80.1775  |                      8.04167 |
| median  | C-5e1f09d89da8          |    25 |   47.52    |   123.604   |                     10       |
| median  | C-5eb0e85c30f9          |    72 |   21.5226  |    53.7983  |                      8       |
| median  | C-60c8e25446b7          |    72 |   21.7448  |    53.6507  |                      8       |
| median  | C-6182fe83e778          |    22 |   34.4848  |   118.041   |                      6       |
| median  | C-625f87222c20          |    70 |   20.8107  |    53.624   |                      8       |
| median  | C-67a8d890ae35          |    88 |   20.6889  |    52.1393  |                      7       |
| median  | C-6b9c01add4ac          |    19 |   39.7171  |    98.6129  |                      8       |
| median  | C-6cb25de4c42c          |    70 |   21.0744  |    53.3036  |                      8       |
| median  | C-6cda23b4de80          |    16 |   39.4375  |   103.128   |                      6       |
| median  | C-6ee9ab981677          |    62 |   24.8387  |    74.3605  |                      8       |
| median  | C-7300f78b2210          |    17 |   39.625   |    99.1161  |                      8       |
| median  | C-77e936c01dc7          |    71 |   23.9102  |    64.2069  |                      8       |
| median  | C-7b0b6a2a518e          |    15 |   41.9333  |   119.905   |                      8       |
| median  | C-7cfc9695b159          |    73 |   23.4658  |    59.608   |                      8       |
| median  | C-7f6ad488cf7a          |    15 |   47.1333  |   121.713   |                      8       |
| median  | C-7f7a70e48539          |    96 |   21.3537  |    56.7581  |                      7       |
| median  | C-8674fe12b24c          |    57 |   23.7018  |    73.3628  |                      8       |
| median  | C-86de8fed9244          |    42 |   27.4762  |    97.0319  |                      8       |
| median  | C-8b237aca42cd          |    78 |   21.2003  |    52.2543  |                      8       |
| median  | C-8c71c15134d7          |   326 |   19.3265  |    68.1702  |                      7.95833 |
| median  | C-8d2671f5814b          |    45 |   19.7148  |    52.9043  |                      5.625   |
| median  | C-8d48b1e8deed          |    68 |   24.6795  |    62.0218  |                      8       |
| median  | C-92eebc2cc4e2          |    75 |   22.115   |    53.4819  |                      8       |
| median  | C-943ea3b1ffe3          |    90 |   22.8574  |    58.914   |                      8       |
| median  | C-9519286825bf          |    74 |   21.2157  |    53.6123  |                      8       |
| median  | C-95b327c9e953          |    18 |   63.3176  |   114.125   |                      8       |
| median  | C-9bd12eb83436          |    15 |   44.5083  |   103.4     |                      8       |
| median  | C-a2fb1264e406          |    72 |   21.7963  |    56.8315  |                      8       |
| median  | C-a38c916a97cf          |    81 |   22.5586  |    57.4067  |                      7       |
| median  | C-a45a4d8ca8f3          |    75 |   23.1017  |    57.6384  |                      8       |
| median  | C-b07e64798fd2          |    21 |   12.2857  |    22.8139  |                      6       |
| median  | C-b12be84b18e7          |    73 |   21.1678  |    55.2309  |                      8       |
| median  | C-b17ec3e83978          |    25 |   13.0283  |    18.0671  |                      8.04167 |
| median  | C-b1aaeba3e13f          |    67 |   24.5572  |    69.7111  |                      8       |
| median  | C-b1f015922ea2          |    76 |   23.6398  |    61.6574  |                      8       |
| median  | C-b240617d9b45          |   245 |   63.2199  |   104.574   |                     15.9583  |
| median  | C-b54736126fbc          |    23 |   44.5054  |    95.2694  |                      8       |
| median  | C-b842f841cb22          |  4465 |   43.0617  |   131.164   |                      8.04167 |
| median  | C-b97b908ae542          |    14 |   44.7143  |   125.58    |                      8       |
| median  | C-b9e969090ba5          |    55 |   24.2     |    70.4834  |                      8       |
| median  | C-bb70375b423f          |   103 |   22.2407  |    59.8067  |                      7       |
| median  | C-bc13d7eb496d          |    67 |   23.9851  |    65.6584  |                      8       |
| median  | C-bc1e9bc4dd29          |    37 |   51.2601  |    60.2412  |                     50.625   |
| median  | C-bd2125a1b8a7          |    13 |   60.8462  |   134.763   |                      8       |
| median  | C-be88fc44571e          |   152 |   12.7327  |    36.9608  |                      8       |
| median  | C-c6ff3bdcd643          |    16 |   26.0208  |    34.2721  |                     16       |
| median  | C-c8e7c5b236eb          |    68 |   21.3971  |    54.223   |                      8       |
| median  | C-c90fa6854132          |    90 |   23.5514  |    59.6285  |                      8       |
| median  | C-cd2657cc3256          |    72 |   20.1701  |    54.385   |                      8       |
| median  | C-cda6ec7d6b0c          |   891 |   19.5722  |    41.061   |                      7       |
| median  | C-cff75109d691          |    71 |   21.4137  |    53.1106  |                      8       |
| median  | C-d02ea237a24f          |    92 |   22.0285  |    56.974   |                      7       |
| median  | C-d23db2f18ebe          |    72 |   23.1204  |    58.9509  |                      8       |
| median  | C-d35980cd3fa9          |    13 |   34.6154  |    70.8292  |                      8       |
| median  | C-d37ce26af4b7          |    48 |   36.7069  |    73.9916  |                     13.9917  |
| median  | C-d78052df8643          |    71 |   22.4343  |    55.3136  |                      8       |
| median  | C-da83ec442b2c          |  9834 |   47.7967  |   120.486   |                      8       |
| median  | C-dcb1e263df20          |    20 |   36.2812  |    91.6061  |                      8       |
| median  | C-df2a6f860794          |    25 |   36.36    |   104.238   |                      7       |
| median  | C-e1b35534f367          | 10066 |   73.5961  |   155.715   |                     19.625   |
| median  | C-e2289a1b07a1          |   134 |  135.591   |   175.373   |                    110.625   |
| median  | C-e2a363ae7234          |    23 |   32.5489  |    87.281   |                      8       |
| median  | C-e7648ad11bfc          |    61 |   10.8689  |    15.4235  |                      8       |
| median  | C-e9280d46e595          |   332 |    7.08208 |     9.61973 |                      5.14583 |
| median  | C-f09d8c7cb40c          |    47 |   15.2908  |    32.2087  |                      8       |
| median  | C-f1b5fccbc3cd          |    99 |   59.4265  |   107.28    |                      8.04167 |
| median  | C-f1c250601758          |    23 |   41.2174  |   116.021   |                      8       |
| median  | C-f1ea61c56fd9          |    17 |   23.7647  |    42.718   |                      8       |
| median  | C-f5f722fd87a7          |    19 |   52.0197  |   114.001   |                      8       |
| median  | C-f683c8ca5844          |    72 |   21.7581  |    54.4445  |                      8       |
| median  | C-fa7445fc568a          |    76 |   23.4501  |    58.7066  |                      8       |
| median  | C-fc82488c9954          |  3335 |   30.6609  |   107.516   |                      7       |
| median  | C-fd71069e73e8          |   154 |   55.0741  |    94.0617  |                      9.95833 |
| median  | C-fe48d582a8a6          |    18 |   37.7778  |   100.104   |                      8       |

## Limits and next steps

R² is a fit statistic, not prediction accuracy or a percentage of correctly predicted days. Results do not validate working-day durations, IFC-caused delay, verified ground truth or generalization to all construction projects. Inspect the largest errors and the per-group spread before proposing any follow-up. Independent label and baseline provenance verification is still required. Large-error cases are listed in residual_analysis.csv.
