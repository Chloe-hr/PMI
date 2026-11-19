# Stage 5.1 manual quantity validation: measurement guide

*Research only. These are instructions for reviewers. Nothing here is a measurement.*

The workbook `manual_quantity_validation.xlsx` holds 40 concrete elements proposed in Stage 4.0B (`research/data_acquisition/stage4_0b/consolidated/quantity_validation_plan.csv`). Reviewers fill only the **yellow** columns. Start with the 11 elements in `initial_validation_subset.csv`.

## 1. What "independent" means here

The grey columns hold two kinds of value, and neither is independent of the IFC export:

- **Authored values** come from the exporting software's IfcElementQuantity.
- **`*_DERIVED` values** were computed with IfcOpenShell tessellation.

An independent value must come from a **separate measurement**. Two routes qualify:

- **Dimension route (preferred).** Read the section dimensions, lengths and thicknesses with a distance or measurement tool, then calculate the volume by hand or in the workbook.
- **Second geometry engine.** Use a viewer whose geometry kernel is not IfcOpenShell. Record the tool name and version.

These routes do **not** qualify:

- Bonsai/BlenderBIM and FreeCAD use IfcOpenShell. They can locate elements, but their volumes are not independent of the DERIVED values.
- Copying the authored NetVolume shown in a property panel is not a measurement.
- The PMI importer's output is not a measurement either.

## 2. Locating an element

1. Open the IFC file named in `source_ifc_file`. The files in `data/raw/` are read-only, so open a copy if your tool writes caches next to the file.
2. Search for the **GlobalId**. Most viewers can search properties or use a "find by GUID" function. If the GUID search fails, use `element_name` plus `storey`, or the **STEP id** (the `#number` in the IFC text).
3. Check that the element's class, name, storey and material match the grey columns before measuring.
4. SCHEPENDOMLAAN Synchro rows (`SCH-synchro`) have regenerated GUIDs and no materials. Their name ends with `_(#STEP id)`, and that STEP id is the matching element in the **design** model. The `design_model_link` column gives it. Measure the design element and record which file you used.
5. Watch the units. SCHEPENDOMLAAN and MEN-RES use millimetres; RestageIFC and MEN-MTG use metres. The workbook expects **m3**.

## 3. Measuring by geometry category

| Category | Method | Record in `measured_dimensions` | Typical deductions |
|---|---|---|---|
| A: simple homogeneous | Profile dimensions (or polygon vertex distances) × extrusion depth | e.g. `b=0.25 h=0.40 L=1.50` | none expected (no openings in IFC); note any notches |
| B: layered | Outline area × each layer thickness; compute the concrete layer separately | layer list with thicknesses | openings > 0 |
| C: irregular (B-rep, boolean, polygon sets) | Split into prisms at changes of shape; sum the parts | dimensions per part | voids, chamfers, pockets |
| D: invalid mesh | Measure the linked design element, or use drawings; never the mesh volume | source used + dimensions | as category C |

Things to watch for:

- **Foundations as beams.** SCHEPENDOMLAAN `fund_strook` and `fund_opstort` are strip and upstand foundations modelled as IfcBeam. Measure them as foundations, and confirm their function in `reviewer_notes`.
- **Columns.** Record whether the measured height is the clear height or runs through the slab. The measurement rule must be stated, because it decides double counting at joints.
- **Precast or cast-in-place.** Where the material says "prefab", the element is precast. Record this, because it changes which work items apply.
- **Masonry is not concrete.** Aerated-concrete blocks (cellenbeton, 加气) are masonry. None are in this sample, but flag any you find.
- **Mesh quality.** QV37 has 3 open or non-manifold mesh edges. Its own geometry volume is not reliable.

## 4. Recording results

1. Fill these columns: `independent_measurement_method_used`, `measurement_tool_and_version`, `measured_dimensions`, `deductions`, `independent_calculated_volume_m3`.
2. The discrepancy columns calculate against the authored NetVolume (where one exists) and against the DERIVED geometry volume.
3. Tolerances: the engineering owner enters `proposed_tolerance_rel`, then `approved_tolerance_rel`. Until both exist, `within_approved_tolerance` stays blank.
4. Set `validation_status`. If information is missing, choose **Blocked - insufficient information**. Never enter 0 for an unknown value.
5. Store evidence (screenshots, measurement exports, drawing references) in `research/validation/stage5_1_manual/evidence/` and cite the file names in `supporting_evidence`.
6. Fill `reviewer` and `review_date`. A second reviewer should check at least the initial subset.

## 5. Interpreting results

- **Agreement with the authored value** shows that the exporter's quantity matches an independent measurement of the modelled geometry. It does **not** validate the modelled geometry against the built structure.
- **Disagreement** may come from the measurement rule (gross or net, joint deductions), the model, or the measurement. Record which one in `reviewer_notes`.
- **Real-project claims:** results on MEN-RES are geometry-robustness evidence only. Only SCH-design and RestageIFC rows may support real-project claims.
