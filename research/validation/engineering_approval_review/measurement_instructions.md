# Measurement instructions - initial validation subset (11 elements)

Generated 2026-11-19 17:59 UTC. Research only. **No measured values are filled in.** Record results in `research/validation/stage5_1_manual/manual_quantity_validation.xlsx` (sheet Validation_40) - this file does not modify it. Store evidence in `research/validation/stage5_1_manual/evidence/<check_id>/`.

**Independence rule:** measure dimensions yourself and compute the volume; the grey workbook values (authored, DERIVED) must not be copied. Bonsai/FreeCAD share IfcOpenShell geometry and do not count as independent.

**Common evidence per element:** (1) screenshot of the element selected with its properties panel showing GlobalId or name; (2) screenshot of each measured dimension; (3) for polygons, an exported vertex list (Rhino: `List` or `PtInfo`; Revit: spot coordinates) saved as CSV; (4) a short note of tool, version, units and file used.

---
## QV18 - IfcColumn "L形柱:GBZ1d-500X500:667621" (MEN-RES, geometry robustness)

| Field | Value |
|---|---|
| IFC file | `data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `0CQnC65I52bQtPZXPSNgQt` |
| STEP id | `#551041` |
| Class / predefined type | IfcColumn / None |
| Storey / building | F06-13.900 /  |
| Material | [["混凝土 - 现场浇注混凝土", null]] |
| World bounding box (m) | min [632.674, 431.621, 13.9] / max [633.199, 432.13, 16.7] |
| Body geometry | extrusion IfcArbitraryClosedProfileDef depth 2.8 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | profile vertices (6 points) in the profile plane, and extrusion depth |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. State whether the measured height is clear height or includes slab/beam intersections (rule DC07 pending). |
| Independent formula | V = A_profile x extrusion depth; A_profile from measured vertex coordinates by the shoelace formula A = 0.5 |sum(x_i*y_(i+1) - x_(i+1)*y_i)| |
| Authored value available for comparison | none - comparison only against DERIVED geometry |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV18_selection.png`, `QV18_dim_*.png`, `QV18_vertices.csv`, `QV18_note.txt`.

**Known limitations.** no authored volume; model of undocumented build status - robustness only; polygon (6 vertices, IfcPolyline): simple b x h measurement is insufficient - all vertices must be measured; mapped (type) geometry

---
## QV21 - IfcBeam "混凝土 - 矩形梁:LL1-250X400:835065" (MEN-RES, geometry robustness)

| Field | Value |
|---|---|
| IFC file | `data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `04Z2pDbq59gubXi5cneOpX` |
| STEP id | `#1901187` |
| Class / predefined type | IfcBeam / None |
| Storey / building | B01-5.850 /  |
| Material | [["混凝土，现场浇注 - C40", null]] |
| World bounding box (m) | min [654.845, 436.278, -6.25] / max [656.355, 436.604, -5.85] |
| Body geometry | extrusion IfcRectangleProfileDef 0.4x0.25 m depth 1.5 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | section width and depth (XDim=0.4000 m, YDim=0.2500 m in the IFC profile definition - re-measure, do not copy) and member length (extrusion depth) |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. State whether beam depth includes the slab (rule DC06 pending). |
| Independent formula | V = XDim x YDim x extrusion depth (all in m) |
| Authored value available for comparison | none - comparison only against DERIVED geometry |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV21_selection.png`, `QV21_dim_*.png`, `QV21_note.txt`.

**Known limitations.** no authored volume; model of undocumented build status - robustness only

---
## QV22 - IfcBeam "混凝土 - 矩形梁:LL3-200X400:667039" (MEN-RES, geometry robustness)

| Field | Value |
|---|---|
| IFC file | `data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `0CQnC65I52bQtPZXPSNgJD` |
| STEP id | `#549228` |
| Class / predefined type | IfcBeam / None |
| Storey / building | F05-11.100 /  |
| Material | [["混凝土，现场浇注 - C40", null]] |
| World bounding box (m) | min [622.29, 437.993, 13.5] / max [623.798, 438.269, 13.9] |
| Body geometry | extrusion IfcRectangleProfileDef 0.4x0.2 m depth 1.5 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | section width and depth (XDim=0.4000 m, YDim=0.2000 m in the IFC profile definition - re-measure, do not copy) and member length (extrusion depth) |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. State whether beam depth includes the slab (rule DC06 pending). |
| Independent formula | V = XDim x YDim x extrusion depth (all in m) |
| Authored value available for comparison | none - comparison only against DERIVED geometry |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV22_selection.png`, `QV22_dim_*.png`, `QV22_note.txt`.

**Known limitations.** no authored volume; model of undocumented build status - robustness only

---
## QV23 - IfcBeam "混凝土 - 矩形梁:LL7-200X500:668813" (MEN-RES, geometry robustness)

| Field | Value |
|---|---|
| IFC file | `data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `0CQnC65I52bQtPZXPSNhtV` |
| STEP id | `#957223` |
| Class / predefined type | IfcBeam / None |
| Storey / building | F07-16.700 /  |
| Material | [["混凝土，现场浇注 - C40", null]] |
| World bounding box (m) | min [617.11, 432.651, 19.0] / max [618.618, 432.927, 19.5] |
| Body geometry | extrusion IfcRectangleProfileDef 0.5x0.2 m depth 1.5 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | section width and depth (XDim=0.5000 m, YDim=0.2000 m in the IFC profile definition - re-measure, do not copy) and member length (extrusion depth) |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. State whether beam depth includes the slab (rule DC06 pending). |
| Independent formula | V = XDim x YDim x extrusion depth (all in m) |
| Authored value available for comparison | none - comparison only against DERIVED geometry |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV23_selection.png`, `QV23_dim_*.png`, `QV23_note.txt`.

**Known limitations.** no authored volume; model of undocumented build status - robustness only

---
## QV27 - IfcSlab "楼板:结构-100:1101494" (MEN-RES, geometry robustness)

| Field | Value |
|---|---|
| IFC file | `data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `1ZYJGfcOv35fKozx6g84Vm` |
| STEP id | `#2014534` |
| Class / predefined type | IfcSlab / FLOOR |
| Storey / building | F03-5.500 /  |
| Material | [["混凝土，现场浇注 - C30", 0.1]] |
| World bounding box (m) | min [645.548, 433.1, 5.4] / max [648.016, 433.755, 5.5] |
| Body geometry | extrusion IfcRectangleProfileDef 0.53x2.445 m depth 0.1 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | section width and depth (XDim=0.5300 m, YDim=2.4450 m in the IFC profile definition - re-measure, do not copy) and member length (extrusion depth) |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. |
| Independent formula | V = XDim x YDim x extrusion depth (all in m) |
| Authored value available for comparison | none - comparison only against DERIVED geometry |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV27_selection.png`, `QV27_dim_*.png`, `QV27_note.txt`.

**Known limitations.** no authored volume; single concrete layer; model of undocumented build status - robustness only

---
## QV28 - IfcSlab "楼板:结构-130mm:613127" (MEN-RES, geometry robustness)

| Field | Value |
|---|---|
| IFC file | `data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `26QRM2wU50HgKXlvA7A1hN` |
| STEP id | `#19296` |
| Class / predefined type | IfcSlab / FLOOR |
| Storey / building | F03-5.500 /  |
| Material | [["混凝土，现场浇注 - C30", 0.13]] |
| World bounding box (m) | min [623.502, 430.404, 5.32] / max [624.45, 432.395, 5.45] |
| Body geometry | extrusion IfcRectangleProfileDef 1.95x0.85 m depth 0.13 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | section width and depth (XDim=1.9500 m, YDim=0.8500 m in the IFC profile definition - re-measure, do not copy) and member length (extrusion depth) |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. |
| Independent formula | V = XDim x YDim x extrusion depth (all in m) |
| Authored value available for comparison | none - comparison only against DERIVED geometry |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV28_selection.png`, `QV28_dim_*.png`, `QV28_note.txt`.

**Known limitations.** no authored volume; single concrete layer; model of undocumented build status - robustness only

---
## QV29 - IfcWall "基本墙:Q1-250mm:835047" (MEN-RES, geometry robustness)

| Field | Value |
|---|---|
| IFC file | `data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `04Z2pDbq59gubXi5cneOp$` |
| STEP id | `#1900988` |
| Class / predefined type | IfcWall / None |
| Storey / building | B02-9.450 /  |
| Material | [["混凝土，现场浇注 - C40", 0.25]] |
| World bounding box (m) | min [653.3, 428.16, -9.45] / max [653.671, 430.545, -5.85] |
| Body geometry | extrusion IfcRectangleProfileDef 2.375x0.25 m depth 3.6 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | section width and depth (XDim=2.3750 m, YDim=0.2500 m in the IFC profile definition - re-measure, do not copy) and member length (extrusion depth) |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. Check for inserted doors/windows in the viewer; none are modelled as voids here. |
| Independent formula | V = XDim x YDim x extrusion depth (all in m) |
| Authored value available for comparison | none - comparison only against DERIVED geometry |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV29_selection.png`, `QV29_dim_*.png`, `QV29_note.txt`.

**Known limitations.** no authored volume; single concrete layer; model of undocumented build status - robustness only

---
## QV30 - IfcWall "基本墙:Q1-200mm:667729" (MEN-RES, geometry robustness)

| Field | Value |
|---|---|
| IFC file | `data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `0CQnC65I52bQtPZXPSNha3` |
| STEP id | `#622980` |
| Class / predefined type | IfcWall / None |
| Storey / building | F06-13.900 /  |
| Material | [["混凝土，现场浇注 - C40", 0.2]] |
| World bounding box (m) | min [623.241, 434.115, 13.9] / max [624.25, 434.366, 16.7] |
| Body geometry | extrusion IfcRectangleProfileDef 1x0.2 m depth 2.8 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | section width and depth (XDim=1.0000 m, YDim=0.2000 m in the IFC profile definition - re-measure, do not copy) and member length (extrusion depth) |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. Check for inserted doors/windows in the viewer; none are modelled as voids here. |
| Independent formula | V = XDim x YDim x extrusion depth (all in m) |
| Authored value available for comparison | none - comparison only against DERIVED geometry |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV30_selection.png`, `QV30_dim_*.png`, `QV30_note.txt`.

**Known limitations.** no authored volume; single concrete layer; model of undocumented build status - robustness only

---
## QV32 - IfcWall "基本墙:Q1-250mm:833736" (MEN-RES, geometry robustness)

| Field | Value |
|---|---|
| IFC file | `data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `2cXeH1oUL3_RnPwCiVXH_c` |
| STEP id | `#1898730` |
| Class / predefined type | IfcWall / None |
| Storey / building | B02-9.450 /  |
| Material | [["混凝土，现场浇注 - C40", 0.25]] |
| World bounding box (m) | min [628.096, 430.2, -9.45] / max [628.429, 431.836, -5.85] |
| Body geometry | extrusion IfcRectangleProfileDef 1.625x0.25 m depth 3.6 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | section width and depth (XDim=1.6250 m, YDim=0.2500 m in the IFC profile definition - re-measure, do not copy) and member length (extrusion depth) |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. Check for inserted doors/windows in the viewer; none are modelled as voids here. |
| Independent formula | V = XDim x YDim x extrusion depth (all in m) |
| Authored value available for comparison | none - comparison only against DERIVED geometry |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV32_selection.png`, `QV32_dim_*.png`, `QV32_note.txt`.

**Known limitations.** no authored volume; single concrete layer; model of undocumented build status - robustness only

---
## QV09 - IfcFooting "CONC-FD01-01" (RST, independent demonstrator validation)

| Field | Value |
|---|---|
| IFC file | `data/raw/Restage_IP_ALL_MULTI_001.ifc` |
| Schema / file length unit | IFC4 / m |
| GlobalId | `05hYJfrx99v$KeaCnnTUNB` |
| STEP id | `#1076898` |
| Class / predefined type | IfcFooting / USERDEFINED |
| Storey / building | Concrete_-01 / Restage |
| Material | [["C35/45", null]] |
| World bounding box (m) | min [6.95, -4.01, -0.41] / max [7.45, 0.7, -0.11] |
| Body geometry | extrusion IfcArbitraryClosedProfileDef depth 0.3 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | profile vertices (4 points) in the profile plane, and extrusion depth |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. |
| Independent formula | V = A_profile x extrusion depth; A_profile from measured vertex coordinates by the shoelace formula A = 0.5 |sum(x_i*y_(i+1) - x_(i+1)*y_i)| |
| Authored value available for comparison | NetVolume 0.7065 m3 (do not copy) |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV09_selection.png`, `QV09_dim_*.png`, `QV09_vertices.csv`, `QV09_note.txt`.

**Known limitations.** agreement with authored value is a consistency check (same exporter geometry), not independent validation; polygon (4 vertices, IfcIndexedPolyCurve): simple b x h measurement is insufficient - all vertices must be measured

---
## QV01 - IfcBeam "fund_strook" (SCH-design, development)

| Field | Value |
|---|---|
| IFC file | `data/raw/SCHEPENDOMLAAN/Design model IFC/IFC Schependomlaan.ifc` |
| Schema / file length unit | IFC2X3 / mm |
| GlobalId | `00IbOoI7nFSxfp71ZyLBPm` |
| STEP id | `#5991` |
| Class / predefined type | IfcBeam / None |
| Storey / building | -1 fundering / Building |
| Material | [["02 Beton gewapend - ihw", null]] |
| World bounding box (m) | min [8.872, 10.0, -1.0] / max [9.872, 11.465, -0.75] |
| Body geometry | extrusion IfcArbitraryClosedProfileDef depth 1.465 m |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | profile vertices (4 points) in the profile plane, and extrusion depth |
| Required deductions | None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it. Foundation element modelled as IfcBeam: measure as a strip/upstand foundation; no slab deduction applies. |
| Independent formula | V = A_profile x extrusion depth; A_profile from measured vertex coordinates by the shoelace formula A = 0.5 |sum(x_i*y_(i+1) - x_(i+1)*y_i)| |
| Authored value available for comparison | NetVolume 0.36625 m3 (do not copy) |

**Rhino workflow.** Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.

**Revit workflow.** Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - record it only as a secondary cross-check, not as the independent value.

**Evidence to save.** `QV01_selection.png`, `QV01_dim_*.png`, `QV01_vertices.csv`, `QV01_note.txt`.

**Known limitations.** foundation element modelled as IfcBeam; agreement with authored value is a consistency check (same exporter geometry), not independent validation; polygon (4 vertices, IfcPolyline): simple b x h measurement is insufficient - all vertices must be measured

*Foundation note:* this IfcBeam is a strip foundation ("fund_strook") on storey "-1 fundering". Record in reviewer_notes whether you agree it is a foundation (rule CR11 pending).
