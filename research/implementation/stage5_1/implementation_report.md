# PMI Stage 5.1 IFC compatibility and quantity extraction

| Acceptance gate | Decision |
| --- | --- |
| Controlled implementation | Pass for the tested IFC2X3 and IFC4 scope. |
| Exploratory real-model extraction | Pass for SCHEPENDOMLAAN design and Mendeley residential. Synchro was evaluated for exporter interoperability. The RestageIFC software demonstrator passed its fixed protocol. |
| Independent engineering validation and planning release | Pending independent measurement and owner-approved tolerances. Zero work items were released. |

## Implementation

| Module | Functions and changes |
| --- | --- |
| `pmi_core/adapters/ifc.py` | `import_ifc` enforces the IFC2X3/IFC4 schema policy, records the detected schema, preserves native severity, and accepts explicit exploratory and geometry switches. It hashes and parses the same private source snapshot. |
| `pmi_core/bim/elements.py` | `extract_elements` resolves schema-specific spatial structure, retains STEP IDs and GlobalIds, and gives duplicate GlobalIds distinct version-scoped records. `type_relations` handles IFC2X3 `IsDefinedBy` and IFC4 `IsTypedBy`. `IfcMember` is included in the supported occurrence classes. |
| `pmi_core/bim/materials.py` | `extract_materials` shares the type lookup and preserves existing occurrence/type and member provenance. `classify_material_name` reports explicit source labels, with aerated and masonry labels taking precedence over cast-in-place terms. |
| `pmi_core/bim/quantities.py` | `extract_quantities` distinguishes authored entities, property quantities and flattened exporter properties. `reconcile_body_volume` compares accepted values only on the same explicit represented-body basis and normalized unit. |
| `pmi_core/bim/geometry.py` | `extract_geometry` and `_volume` provide opt-in IfcOpenShell tessellation and conservative volume validation. |
| `pmi_core/schemas/bim.py` | `canonical_bundle` supports an opt-in 5.1.0 contract. It retains the 5.0.0 default and gates canonical publication on strict import validity. |
| `pmi_core/validation/bim.py`, `pmi_core/validation/readiness.py` | Identity checks retain the original STEP evidence. `assess_readiness` tracks import, containment and identity, geometry, quantity and material evidence, engineering validation, and work-item eligibility. |
| `pmi_core/cli.py` | `main` exports the versioned import envelope as JSON plus CSV tables for elements, spatial structure, materials, quantities, evidence, diagnostics, geometry and readiness. |

Strict import rejects duplicate GlobalIds. Exploratory import retains them and preserves distinct STEP identifiers and warnings. Duplicate physical STEP labels are fatal in both policies because the native parser otherwise overwrites a declaration. The importer reports the affected label and native diagnostic without returning the collapsed model. Ambiguous containment is inspectable in exploratory mode. Affected occurrences and ancestry are blocked from identity eligibility. A successful exploratory import can be exported for inspection and has no canonical publication path.

## Geometry and quantities

The geometry component accepts a single supported convex Body item derived from an extrusion, tessellation or faceted B-rep. It checks the project length unit, the normalized placement matrix, finite coordinates, face indices, degeneracy, oriented edge incidence, manifold vertex links, shell topology and convex support planes. Missing, unsupported and invalid geometries retain individual diagnostic records. Mapped representations, concave solids, multiple items, Boolean/clipping representations and openings remain outside the measured domain. This is a conservative mesh check on the IfcOpenShell output. It provides approximate volume for meshed curved boundaries and is limited to the supported representation domain.

Controlled fixtures returned 6 m³ for an IFC2X3 analytical extrusion and 1/6 m³ for a closed IFC4 tetrahedron. An explicitly open tessellation returned a failure with no accepted volume. The IFC4 imperial certification column returned 0.12585265152 m³. The certification wall with an opening was reported as unsupported.

Authored gross and net quantities retain separate bases. An unqualified property named Volume retains an unspecified volume basis. Geometry uses represented-body volume and therefore compares only with an explicit quantity of that basis. A controlled mismatch produced a diagnostic and preserved both source rows. The software comparison uses relative tolerance 1e-6 and absolute tolerance 1e-9 m³. Engineering acceptance tolerances remain pending. Quantity and property overrides take precedence over the matching project unit. Geometry uses the independent project length unit and returns SI volume.

Flattened Synchro values carry `IfcReal` with no explicit dimensional unit in the samples inspected. The extractor preserves their numeric values, bases and source STEP evidence as disputed until an exporter measurement and unit rule is established. Composite material associations retain their source composition evidence. No volume was allocated from layer thickness ratios. Material-specific concrete volume requires direct evidence for that basis; engineered reinforcement, formwork, excavation and backfill remain unavailable. The contract defines separate user-provided and engineering-assumption methods for downstream values.

## Versioned records and readiness

The [5.1.0 schema](canonical_schemas_5_1.json) adds optional name, object type and predefined type on BIMElement, source project GlobalId on ModelVersion, measurement method and property/exporter/user/assumption provenance on QuantityRecord, and a source label classification on MaterialRecord. Spatial rows retain source class, STEP ID, composition classification where supplied, and container evidence. Original 5.0.0 consumers can keep using the default canonical serializer. The CLI JSON is an inspection envelope with additional diagnostics and readiness fields. The schema validates the canonical bundle generated by the Python API.

Readiness exposes record-level evidence even where complete planning data are unavailable. Candidate identity eligibility requires valid import, a unique source identity and resolved containment. Source material labels and accepted quantities remain available for review. Engineering approval is pending and work-item eligibility is false throughout this stage.

## Extraction results

| Input | Role and schema | Occurrences | Geometry valid / unsupported / invalid / missing | Seconds |
| --- | --- | ---: | ---: | ---: |
| SCHEPENDOMLAAN design | Development, IFC2X3 | 1,419 | 784 / 597 / 34 / 4 | 11.954 |
| Mendeley residential | Robustness, IFC2X3 | 4,272 | 1,601 / 2,665 / 6 / 0 | 9.739 |
| SCHEPENDOMLAAN Synchro | Exporter interoperability, IFC2X3 | 1,365 | 783 / 532 / 50 / 0 | 7.094 |
| Certification column and wall | Compatibility, IFC4 | 2 | 1 / 1 / 0 / 0 | 0.026 / 0.009 |
| RestageIFC | Independent software demonstrator, IFC4 | 390 | 123 / 206 / 59 / 2 | 5.361 |

Design extraction yielded 66,990 accepted and 7,723 disputed authored rows and retained the duplicate relationship GlobalId diagnostic. Mendeley yielded 1,601 accepted geometry records and no supported authored quantity records. Synchro yielded 8,255 disputed flattened rows and no material associations. The fixed RestageIFC sample resolved 8 of 8 GlobalIds and returned 850 accepted authored rows across the full model. Separate results include source hashes, class counts, issue counts and diagnostic coverage. Timings are single serial wall-clock observations for snapshot, import and extraction. CLI export time and peak memory were outside the timings. The per-face convexity validation scales with both face and vertex count.

[Development and certification results](extraction_results.json) · [RestageIFC protocol](restage_demonstrator_protocol.md) · [RestageIFC results](restage_demonstrator_results.json)

## Reproduce the CLI demonstration

From the repository root, run with a fresh output directory. Strict is the default. Add `--policy exploratory` for a development inspection. The process exits 1 on invalid import and writes diagnostics to the requested directory.

```powershell
& .venv/Scripts/python.exe -B -m pmi_core.cli import-ifc --input 'data/raw/Certification-datasets-main/IFC 4.0.2.1 (IFC 4 ADD2 TC1)/ISO Spec - ReferenceView_V1.2/column-straight-rectangle-tessellation.ifc' --project-id PMI-DEMO --geometry --output 'outputs/stage5_1/demo'
& .venv/Scripts/python.exe -B -m pmi_core.cli import-ifc --input 'data/raw/SCHEPENDOMLAAN/Design model IFC/IFC Schependomlaan.ifc' --project-id PMI-DEMO --policy exploratory --geometry --output 'outputs/stage5_1/sch-design'
& .venv/Scripts/python.exe -B -m pmi_core.cli import-ifc --input 'data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc' --project-id PMI-DEMO --policy exploratory --geometry --output 'outputs/stage5_1/mendeley-residential'
```

The certification command was executed with `research/implementation/stage5_1/demo` as the output directory. [Demonstration JSON](demo/import.json)

## Runtime

The existing IFC environment is Windows x64 Python 3.14.7 with IfcOpenShell 0.9.0.post1 and NumPy 2.5.4. The planning environment is Windows x64 Python 3.12.14 with OR-Tools 9.15.6755, NumPy 2.5.5, pandas 3.1.1 and protobuf 6.33.6. IfcOpenShell is absent from the planning environment. Its installed metadata declares Python >=3.10,<3.16, and PyPI publishes a Windows x64 Python 3.12 wheel for the tested release. Geometry uses native binaries and NumPy. A unified Python 3.12 runtime is a candidate after an approved clean environment verifies wheel loading, transitive dependency resolution, schema availability, fixture parity and solver integration. Use the versioned JSON record boundary for current cross-process exchange. Installed environments were inspected without package changes. [IfcOpenShell wheel metadata](https://pypi.org/project/ifcopenshell/0.9.0.post1/) · [IfcOpenShell installation matrix](https://docs.ifcopenshell.org/ifcopenshell-python/installation.html)

## Tests and preservation

- Stage 5.1 controlled suite passed 12 of 12. Existing regressions covered SI powers, imperial conversion, explicit units, authored conflicts, scoped materials, malformed input and 5.0 serialization. New regressions covered the IFC2X3 type and spatial paths, analytical and tessellated volume, native duplicate STEP diagnostics, exploratory GlobalIds, property provenance, reconciliation and CLI export.
- Legacy IFC-to-Gantt passed 6 of 6. IFC4D passed 8 of 8. The IFC4D viewer passed 6 of 7. The failing preservation assertion compared two CRLF raw IFCs against manifest hashes for the LF versions. Removing CR bytes from CRLF sequences in memory reproduced both expected hashes. Their actual byte hashes differ from the manifest, and all 34 legacy inputs and artifacts retained their before/after byte hashes. The test, expected hashes and IFC files were preserved.
- The five manifest-listed development/interoperability/certification inputs and the RestageIFC source matched their Section A hashes before and after extraction. The protected paths for this pass included `models/`, `data/`, `outputs/`, `evidence/`, the accepted consolidated audit, `research/architecture/stage5_0/`, and the legacy preservation tests and manifests. Staged and tracked working-tree diffs were empty. Exact byte verification covers the cited input and artifact sets. The broader tracked diff is a separate Git status check.
- Starting and ending HEAD was `0c0a5160051520aa1a83f7baa573fff7d3785ce9`. The previous fixture pass recorded an earlier concurrent change. Additional untracked paths appeared outside this pass's scope while HEAD stayed fixed.

Benchmark quarantine exclusions were applied. The work stops at Stage 5.1. Independent engineering measurements and planning release remain pending.
