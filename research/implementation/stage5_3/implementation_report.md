# PMI Stage 5.3A engineering duration and cost estimation

| Acceptance gate | Result |
| --- | --- |
| Controlled implementation | Passed. The frozen three-element frame produced 12 productive estimates, 9 elapsed holds and 21 dependency edges across 3 packages. All 27 regression tests passed. |
| Real-project engineering and scheduling release | Disabled. The estimator accepts the identified fixture only. All engineering approval IDs remain pending. |

[HTML demonstration](demonstration/report.html) · [Computed JSON](demonstration/estimate.json) · [Fixture inputs](controlled_fixture_inputs.json) · [Test results](test_results.json)

## Quantities and measured geometry

| IFC element | Authored and geometry cross-check, m³ | Formwork contact, m² | Hypothetical B500S BOQ, kg |
| --- | ---: | ---: | ---: |
| Column | 0.48 | 4.80 | 32 |
| Beam | 0.80 | 5.44 | 58 |
| Slab | 2.40 | 10.40 | 86 |

The Stage 5.1 authored net quantity and independent tessellated Body result agree with the rectangular dimensions on each element. A fresh IfcOpenShell extraction confirmed eight vertices per Body, no openings and the configured world-coordinate bounds. The vertical extents are 0–3.0 m, 3.0–3.5 m and 3.5–3.7 m. Column and beam share a 0.16 m² bearing face. Beam and slab share 1.60 m². No pair shares positive volume. Column formwork uses the four vertical faces. Beam measurement uses two long sides plus soffit less the column bearing. Slab measurement uses soffit less the beam footprint. End or edge shutters are outside these fixture rules and selected reference scope. Stripping uses each formwork area exactly once. The three reinforcement masses are explicit software-test BOQ lines. [Geometry verification](measurement_verification.json)

The configuration adapts the Agent 2 review template’s input types, crew capacities, hand-placement equipment mode, and 24/168 elapsed-hour examples to the existing three-element fixture. It declares HA-25/P/20/XC2, pre-staged concrete supply, no crane, pump or delivery occupancy within the selected operations, one vibrator, and local Monday–Friday eight-hour windows. Placement follows formwork, reinforcement and a 0.5-hour hypothetical inspection hold. Curing holds for 24 elapsed hours. Striking is eligible for the fixture after 24 elapsed hours from placement for the column and 168 for beam and slab. The graph therefore adds zero or 144 further hours after curing. The fixture assumes hypothetical strength checks pass at those thresholds. No project start or finish dates are assigned.

## Computed results

- Demand totals are 3.520 ferrallista hours, 9.4432 encofrador hours, 8.680 specialist helper hours, 0.640 general skilled worker hours, and 1.056 vibrator machine-hours.
- Concrete material consumption is 3.7904 m³ from the 1.03 m³/m³ catalogue coefficient. The priced placed-concrete quantity is 3.68 m³. Material, labor and equipment rows retain their original codes, units and source references.
- The 12 productive bounds sum to 10.372 hours. This is an arithmetic total of activity estimates. Resource contention, task overlap and project makespan remain for scheduling.
- All fixture activities have the required test inputs. The selected graph has zero relationship conflicts or cycles.

| Direct catalogue cost component | EUR |
| --- | ---: |
| Labour decomposition | 506.232944 |
| Equipment decomposition | 1.921920 |
| Material decomposition | 663.167296 |
| Published price less decomposition | 1.191440 |
| Published compatible reference total | **1,172.513600** |

The published unit price controls each line total. The decomposition is a separate reconciliation whose source per-unit rounding differences are carried through by quantity. Costs are counted once. The totals use BCCA December 2023 V02 Andalusia, in EUR, with the concept dates retained per record. They exclude tax, overhead, profit and indirect costs and remain historical reference estimates. Present-day Barcelona pricing is outside this cost boundary.

## Engineering preparation handover

The priority register still contains 75 pending approvals. The measurement instructions require independent measurements and retained source evidence. The fixture's authored and mesh cross-check is recorded as such. The input-state vocabulary distinguishes missing, hypothetical fixture, user-provided project, independently measured, and engineer-approved inputs. Only missing and hypothetical states arise on this fixture path. Real-model estimation and scheduling release remain disabled.

The existing three-element model remains the pipeline input. The separate Agent 2 worked example was recalculated directly from the template's original quantities and the primary BCCA selection rows using decimal arithmetic, independent of the production estimate formula. All 11 displayed line prices matched. The exact total is €3,966.32446 and rounds to the documented €3,966.32. The exact component amounts are €1,729.034229 labour, €5.098548 equipment and €2,226.482170 material. The €5.709513 difference between the exact published total and the exact decomposition sum comes from the selected source unit prices and their component rounding. The retained three-element estimate remains €1,172.51 because it uses a different model and BOQ. [Reference calculation comparison](reference_calculation_comparison.csv)

For the selected simultaneous mode, the controlling resource may be a trade, a machine or a compatible declared placement throughput for delivery, pumping or lifting in m³/h. Supplemental throughput imposes a production bound. It has no synthesized machine-hours or cost line when the reference excludes it. Sequential methods report insufficient phase evidence unless such a method is modeled in a future release. The concrete fixture explicitly declares pre-staged supply and manual handling with no outside crane, pump or delivery occupancy. Labor costs are available by trade, material costs by source line and machine cost by class where the source identifies a single class. Published prices remain the total authority.

Use a fresh output directory for this single PowerShell pipeline command, which invokes IFC extraction with the existing IFC interpreter and estimates from the versioned JSON boundary in the planning interpreter.

~~~powershell
& .\.venv-planning\Scripts\python.exe -B -m pmi_core.estimation --ifc-python '.\.venv\Scripts\python.exe' --ifc 'research/implementation/stage5_2/controlled_frame.ifc' --config 'research/implementation/stage5_3/controlled_fixture_inputs.json' --output 'outputs/stage5_3/controlled'
~~~

The scheduling handover links activity and package IDs, IFC element IDs, quantities and evidence, capacity and demand, cost, calendar, inspection and release conditions, and both the selected and original conditional edges. Future solvers should consume the selected edges and retain conditional edges for method review. Software-only eligibility applies to the controlled graph. The three package chains still need explicit inter-package support and access decisions for a structural schedule. [Scheduling handover](scheduling_handover.json) · [Duration estimates](duration_estimates.csv) · [Resource demands](resource_demands.csv) · [Cost estimates](cost_estimates.csv) · [HTML report](report.html)

## Method and source files

- [references.py](../../../pmi_core/estimation/references.py) loads the 14 reviewed reference rows, parses labor, machine and material coefficients, validates composition and reconciles the review decomposition to the unit price within €0.01 per unit. Results carry the selection CSV hash, source BC3 hash, BCCA code, edition, region, individual concept price date and pending approval ID.
- [engine.py](../../../pmi_core/estimation/engine.py) estimates a simultaneous fixed-crew lower bound using the largest worker-hours divided by assigned workers, machine-hours divided by assigned machines, or declared process minimum. Demand, reserved resource-hours and elapsed holds are separate. Capacity must be a positive integer for positive modeled demand. The engine uses compatible units and validates the Stage 5.1 and Stage 5.2 versions and matching model ID, IFC source hash and fixed fixture identities.
- Catalogue labor and machine demand remain on their original operation bundle. The reference books inseparable curing labor with concrete placement. Separate curing and striking-release holds carry no additional crew or price. Stripping uses the separate selected BCCA item only for the fixture formwork items whose source flags exclude removal. Catalogue conflicts reject a second stripping or curing allocation. Serial subprocesses and separate time-phasing of bundled labor require additional evidence.
- The optional grouping contract records storey, zone, classification, method and batch plus package IDs and every IFC GlobalId. A regression groups two controlled assignments and verifies traceability. No zones or pours are inferred. The fixture keeps its three classes in separate groups and retains element packages and original activities.
- [Estimation CLI](../../../pmi_core/estimation/__main__.py) reads the Stage 5.1 BIM and Stage 5.2 construction evidence envelopes and emits version 5.3A JSON, activity, dependency, package and quantity CSVs, and HTML. Missing model resources or quantities block those estimates and prevent a full cost total. No real-project approval path exists in this stage.

## Exact PowerShell commands

From the repository root, use fresh output directories.

~~~powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_stage5_*.py' -v
& .\.venv\Scripts\python.exe -B -m pmi_core.cli build-construction --input 'research/implementation/stage5_2/controlled_frame.ifc' --project-id PMI-CONTROLLED --geometry --output 'outputs/stage5_3/construction'
& .\.venv-planning\Scripts\python.exe -B -m pmi_core.estimation --bim 'outputs/stage5_3/construction/import.json' --construction 'outputs/stage5_3/construction/construction.json' --config 'research/implementation/stage5_3/fixture_inputs.json' --output 'outputs/stage5_3/estimate'
~~~

The fresh workflow reproduced the saved demonstration output byte-for-byte. The CLI returns 1 if controlled records export with blockers, and 2 for an invalid input envelope or output path.

## Runtime compatibility

The existing Python 3.14.7 environment ran IfcOpenShell 0.9.0.post1 for import and construction generation. The Python 3.12.14 planning interpreter, which contains OR-Tools 9.15.6755, ran the standard-library estimation CLI against those exports. The estimation process imports neither native IFC nor solver dependencies. Keep the versioned JSON boundary for the current integration. Both releases publish Windows x86-64 wheels for Python 3.12. Common-runtime compatibility remains a candidate until a clean install checks transitive dependencies, native loading and fixture parity. [IfcOpenShell wheel](https://pypi.org/project/ifcopenshell/0.9.0.post1/) · [OR-Tools wheel](https://pypi.org/project/ortools/9.15.6755/)

Future isolated environment commands for an approved installation, with a fresh environment path.

~~~powershell
py -3.12 -m venv .venv-pmi312-validation
& .\.venv-pmi312-validation\Scripts\python.exe -m pip install --only-binary=:all: 'ifcopenshell==0.9.0.post1' 'ortools==9.15.6755' numpy jsonschema
& .\.venv-pmi312-validation\Scripts\python.exe -m pip check
& .\.venv-pmi312-validation\Scripts\python.exe -c "import ifcopenshell, ortools; from ortools.sat.python import cp_model; print(ifcopenshell.version, ortools.__version__, type(cp_model.CpModel()).__name__)"
& .\.venv-pmi312-validation\Scripts\python.exe -B -m unittest discover -s tests -p 'test_stage5_*.py' -v
~~~

No environments were modified.

## Verification and next gate

The 12 Stage 5.1, five Stage 5.2A and ten Stage 5.3A tests passed. Git HEAD stayed at 0933719457af29750c31d58f181486010a8b5d14 during the pass. The baseline-covered tracked files matched their byte hashes. The baseline and verification record state the scope. No commit or push was made. [Baseline](baseline.json) · [Preservation verification](preservation_verification.json)

Before Stage 5.4 CPM and CP-SAT, define the scheduling time unit, integer rounding, working-time versus elapsed-time mapping and a controlled anchor date. Resolve inter-package structural and access dependencies using explicit evidence, including support and strength-release rules. Define occupancy and capacity pools per selected execution mode, the crew and equipment calendar semantics, and feasibility and objective rules. Real-project use also requires independently measured quantities, approved crew and method inputs, and signed applicability, sequencing and engineering release decisions. No scheduler or real-project release was implemented.
