# PMI Stage 2.3E — Cambridge supervised model training

## Execution status

**Training and evaluation were not run.** The available PowerShell environment has no `python`, `py`, or `python3` executable, and this repository has no local virtual environment. The frozen data and split were audited before adding this training entry point, but no model was fitted and no held-out prediction was made. Consequently, this report contains no performance results and makes no model-quality claim.

## Pre-training checks completed

- Read the Stage 2.3C feasibility report, Stage 2.3D design report, feature contract, frozen holdout protocol, and conservative split manifest.
- Recomputed every Stage 2.3D frozen output checksum: all matched.
- Confirmed the conservative manifest contains 180,137 unique composite activity keys. Feature, target, and split tables each contain 180,137 unique keys and their key sets match exactly.
- Confirmed 144,110 development activities and 36,027 held-out activities.
- Confirmed zero conservative blocks cross the split. The dominant block `C-5f73906a8795` has all 99,636 activities in development.
- Confirmed the approved allowlist is exactly `activity_description`, `project_type`, and `uk_region`.
- The Stage 2.3D reports 169 conservative blocks represented among eligible activities, zero independently verified labels, and an evaluation population with severe project-type shift. It explicitly allows this limited retrospective holdout while ruling out a representative estimate for the dominant history.

These checks establish a structurally valid, limited grouped holdout. They do not establish representative generalization or verified historical ground truth.

## Planned experiment implementation

`training/train_cambridge_experiment.py` implements a median baseline, TF-IDF plus one-hot Ridge, a Random Forest on a 128-component sparse projection, and a modest PyTorch MLP on the same three fields. The fixed five development folds keep conservative groups intact. Preprocessing is fitted within each fold; Ridge regularization is selected within development-only groups; MLP stopping uses grouped validation drawn only from the corresponding development training portion. The final models are configured before evaluating the conservative held-out groups.

The target is the unchanged reported elapsed calendar-day value for activities meeting Stage 2.3C eligibility. It is not imputed or clipped. It represents reported historical elapsed time, not verified working duration, IFC-caused delay, or an independently verified label. Feature timing provenance remains uncertain.

## Outstanding work

Install the dependencies from `training/requirements-cambridge-experiment.txt` in the project's Python environment, then run:

```powershell
python training/train_cambridge_experiment.py
python -m unittest discover -s tests -p test_train_cambridge_experiment.py -v
```

The training entry point writes the requested metrics, predictions, diagnostics, metadata, model artifacts, and figures only after it completes successfully. None of those result artifacts or trained models are claimed to exist yet. Review runtime and memory use before running the full 180,137-row experiment; the controlled dense projections are 128-dimensional, while sparse TF-IDF and model fitting still require substantial memory and CPU time.

## Interpretation and next steps

Once executable in a Python environment, report all predeclared models against the median baseline, include activity-weighted and group-level errors, and inspect large-error cases. Keep the severe distribution shift and dominant training block visible in any interpretation. Do not describe R² as prediction accuracy or a percentage of correctly predicted days. Do not claim verified construction-delay prediction, IFC-change-to-delay prediction, working-day prediction, or generalization to all construction projects. There are currently zero independently verified Cambridge labels.
