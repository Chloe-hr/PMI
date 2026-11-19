# PMI Stage 5.2A construction knowledge engine

| Gate | Result |
| --- | --- |
| Controlled software implementation | Passed. The synthetic IFC4 frame generated three element-scoped packages and 15 candidate activities. |
| Exploratory model extraction | Completed for manifest-listed SCHEPENDOMLAAN design and Mendeley residential IFC2X3 inputs. |
| Engineering and scheduling release | Pending. All 75 source approvals remain pending and every candidate reports its blockers. |

## Implementation

- [Library provider](../../../pmi_core/construction/library.py) — load_library validates the eight source CSVs, including table sizes, unique keys, approval links, catalogue references, flags and absence of universal durations. It versions the release by the ordered source hashes. The provider retains 29 work items, 61 reference rows, 15 classification rules, 16 dependency rules, 14 double-counting controls, 22 project inputs, 75 approvals and 11 quantity requirements.
- [Classification](../../../pmi_core/construction/classification.py) — classify applies the preparation material labels in precedence order and checks IFC class, name and actual storey ancestry. Foundation candidates are excluded from beam/slab construction. Precast, masonry, AAC, steel, timber and other cases remain classified for review. Explicit cast-in-place columns, beams and slabs are the activity generation scope.
- [Engine](../../../pmi_core/construction/engine.py) — build_construction creates stable element-scoped packages and candidate activities linked to Stage 5.1 element, material, quantity and evidence IDs and to the research rules and approvals. It accepts positive, explicitly sourced user quantities in the Python API. Unqualified volumes, generic reinforcement ratios and gross surface areas are excluded from placed concrete, reinforcement and formwork demand respectively. Competing measurement evidence remains under review. Curing is an elapsed hold, and striking is a productive activity with a separate release criterion.
- [Dependencies](../../../pmi_core/construction/dependencies.py) — package_dependencies emits conditional alternatives for column cage/formwork and beam/slab soffit-first methods. It retains the pre-pour inspection, curing and striking conditions. dependency_issues checks endpoint validity, conflicting relation types and cycles in the proposed graph. Alternative edges are retained as conditional until a method is selected. The engine uses no spatial adjacency precedence and assigns no lags.
- [Catalogue handling](../../../pmi_core/construction/engine.py) — work items expose unit-compatible BCCA options with source code, December 2023 V02 edition, Andalusia region, measurement text, trade, equipment and material coefficients, unit cost and bundle flags. validate_catalogue_choices checks proposed choices for review and keeps them separate from physical activities and priced allocations. Bundled stripping and composite conflicts are checked by catalogue_selection. A curing-only price is rejected. The engine does not divide bundled coefficients. Concrete volume overlap at beam/slab and column/slab junctions remains an engineering measurement gate.
- [CLI](../../../pmi_core/cli.py) and [export](../../../pmi_core/construction/export.py) — build-construction invokes Stage 5.1 and exports the original BIM inventory and evidence plus construction tables, eligibility, dependency edges and HTML. The original import-ifc path remains covered by the Stage 5.1 tests.

## Actual demonstrations

| Model | Elements | Packages | Activities | Proposed / conditional edges | Quantity available / review / missing / not required | BCCA options | Schedulable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Controlled IFC4 frame | 3 | 3 | 15 | 10 / 6 | 3 / 0 / 9 / 3 | 28 | 0 |
| SCHEPENDOMLAAN design | 1,419 | 6 | 30 | 12 / 18 | 0 / 6 / 18 / 6 | 54 | 0 |
| Mendeley residential | 4,272 | 1,352 | 6,760 | 4,946 / 2,580 | 0 / 0 / 5,408 / 1,352 | 12,934 | 0 |

The controlled quantities were 0.48, 0.80 and 2.40 m³ for column, beam and slab. Reinforcement and formwork requirements stayed missing. SCHEPENDOMLAAN's six packages were slabs. Its cast-in-place beams were foundation candidates and stayed outside demonstration activity generation. Mendeley produced 766 column, 355 beam and 231 slab packages. Its represented-body geometry was retained in the BIM evidence and did not qualify as net placed concrete. All three graphs returned zero graph issues. End-to-end times including extract and export were 0.08 s, 16.56 s and 12.53 s respectively on this run.

- Controlled [HTML](demonstrations/controlled/report.html), [construction JSON](demonstrations/controlled/construction.json), [BIM inventory](demonstrations/controlled/elements.csv) and [fixture IFC](controlled_frame.ifc).
- SCHEPENDOMLAAN [HTML](demonstrations/schependomlaan/report.html) and [JSON/CSV archive](demonstrations/schependomlaan/data.zip).
- Mendeley [HTML](demonstrations/mendeley/report.html) and [JSON/CSV archive](demonstrations/mendeley/data.zip).
- [Machine-readable counts and source digests](demonstration_results.json) and [test results](test_results.json).

## Reproduce from the repository root

Choose fresh output paths for each invocation. The included controlled IFC can be used directly. create_frame.py generates the same synthetic model if given a fresh path.

~~~powershell
$py = '.\.venv\Scripts\python.exe'
& $py -B -m unittest discover -s tests -p 'test_stage5_*.py' -v
& $py -B -m pmi_core.cli build-construction --input 'research/implementation/stage5_2/controlled_frame.ifc' --project-id PMI-CONTROLLED --geometry --output 'outputs/stage5_2/controlled'
& $py -B -m pmi_core.cli build-construction --input 'data/raw/SCHEPENDOMLAAN/Design model IFC/IFC Schependomlaan.ifc' --project-id PMI-SCHEPENDOMLAAN --policy exploratory --geometry --output 'outputs/stage5_2/schependomlaan'
& $py -B -m pmi_core.cli build-construction --input 'data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc' --project-id PMI-MENDELEY --policy exploratory --geometry --output 'outputs/stage5_2/mendeley'
~~~

## Verification and preservation

All 12 Stage 5.1 tests and all five Stage 5.2A tests passed. The latter cover provider counts and evidence, classifications, quantities and traceability, missing and user-supplied data, conditional methods, conflicts and cycles, BCCA options and selection, double counting, approval gates and CLI export. IfcOpenShell 0.9.0.post1 imported in the existing Python 3.14.7 environment. OR-Tools 9.15.6755 imported and created an empty CP model in the existing Python 3.12.14 planning environment. Each runtime lacks the other dependency. No package changes were made.

The resumed pass started at c1dd5e4b517bce6e1d42713247b66983747fbc15. The acceptance baseline records exact working-tree hashes, including pre-existing working copies of approval review files. The volatile Excel lock file is outside byte verification. The earlier baselines are retained. Comparison against this baseline permits only the Stage 5.2A engine change to a tracked path. Both real inputs matched the accepted manifest before and after extraction. The archived outputs were re-read and compared byte-for-byte to their loose copies before cleanup. [Preservation verification](preservation_verification.json)

## Remaining limitations and Stage 5.3 prerequisites

The demonstration groups by element and reports storey hierarchy. It has no approved grouping across pours or zones, and it does not apply cross-package support or logistics dependencies. The full library is available for reference. The executable work and dependency subset is the controlled frame scope. An authored quantity with compatible basis is evidence for review, and catalogue choices remain provisional. No engineering approval is granted to the fixture or to either real project.

Stage 5.3 requires independently validated, operation-specific quantities and agreed tolerances, approved scopes and sequence choices, explicit formwork and reinforcement evidence, inspection and strength-release criteria, reviewed bundled catalogue and demand selections, and project crews and productive working hours. These inputs remain prerequisites for duration estimation. Stage 5.2A stops at the acceptance gate.
