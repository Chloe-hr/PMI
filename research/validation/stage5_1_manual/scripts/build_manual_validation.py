"""Build the Stage 5.1 manual quantity validation workbook (independent fields left EMPTY).

Run from repo root after enrich_validation_elements.py:
    .venv/Scripts/python.exe -I research/validation/stage5_1_manual/scripts/build_manual_validation.py
Writes: research/validation/stage5_1_manual/{manual_quantity_validation.xlsx, initial_validation_subset.csv, measurement_guide.md}
"""
import csv, json, os, sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.stdout.reconfigure(encoding='utf-8')
OUT = 'research/validation/stage5_1_manual'
E = json.load(open('data/processed/candidates/stage5_2_prep/validation_elements_enriched.json', encoding='utf-8'))
MAN = {r['ifc_path']: r for r in csv.DictReader(open('research/data_acquisition/stage4_0b/consolidated/stage5_1_validation_manifest.csv', encoding='utf-8'))}

# Initial subset: straightforward category-A elements across classes/models (auditor proposal, not an approval)
SUBSET = {
    'QV01': 'SCH strip foundation (IfcBeam "fund_strook"), single extrusion, authored NetVolume: tests foundation-as-beam handling',
    'QV09': 'RestageIFC footing, single extrusion, authored NetVolume, C35/45: independent demonstrator',
    'QV18': 'MEN-RES L-shaped column, single extrusion, no openings',
    'QV21': 'MEN-RES rectangular beam 250x400, single extrusion',
    'QV22': 'MEN-RES rectangular beam 200x400, single extrusion',
    'QV23': 'MEN-RES rectangular beam 200x500, single extrusion',
    'QV27': 'MEN-RES rectangular slab 100 mm, single extrusion',
    'QV28': 'MEN-RES rectangular slab 130 mm, single extrusion',
    'QV29': 'MEN-RES rectangular wall 250 mm, single extrusion, no openings',
    'QV30': 'MEN-RES rectangular wall 200 mm, single extrusion, no openings',
    'QV32': 'MEN-RES rectangular wall 250 mm, single extrusion, no openings',
}
CAT_ORDER = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
E.sort(key=lambda e: (CAT_ORDER[e['geometry_category'][0]], e['model_key'], e['check_id']))


def method_of(e):
    m = e['material_classification']
    if 'prefab' in m.lower():
        return 'precast concrete (material name "prefab")'
    if 'ihw' in m or '现场浇注' in m:
        return 'cast-in-place concrete (material name)'
    if not json.loads(m or '[]'):
        return 'not exported (Synchro) - take from linked design element'
    return 'concrete, construction method not stated - confirm'


def suggested_method(e):
    c, g = e['ifc_class'], e['geometry_category'][0]
    base = {
        'A': 'Measure the extrusion profile (section dimensions or polygon area) and extrusion depth with an independent BIM measuring tool; volume = profile area x depth.',
        'B': 'Measure outline area and each layer thickness; compute concrete-layer volume separately from total element volume.',
        'C': 'Decompose into prisms/slices measured with an independent tool (sections at changes of shape); sum parts and subtract voids.',
        'D': 'Do not rely on mesh volume. Measure from the linked design element (design_model_link) or from drawings; record why the mesh is open.',
    }[g]
    extra = {'IfcBeam': ' Confirm whether the element is a beam or a strip/upstand foundation.', 'IfcSlab': ' Confirm precast vs cast-in-place.',
             'IfcWall': ' Confirm cast concrete vs block masonry.', 'IfcFooting': ' Record underside level (excavation input) but do not compute excavation.',
             'IfcColumn': ' Record clear height between structural levels.'}.get(c, '')
    return base + extra


COLS = [
    # (header, key/func, editable, width, number_format)
    ('check_id', 'check_id', False, 9, None), ('initial_subset', lambda e: 'YES' if e['check_id'] in SUBSET else '', False, 8, None),
    ('geometry_category', 'geometry_category', False, 26, None), ('model_key', 'model_key', False, 11, None), ('model_role', 'validation_role', False, 26, None),
    ('eligible_for_real_project_claims', lambda e: MAN.get(e['ifc_path'], {}).get('eligible_for_real_project_claims', ''), False, 14, None),
    ('source_ifc_file', 'ifc_path', False, 40, None), ('ifc_schema', 'schema', False, 8, None), ('global_id', 'global_id', False, 24, None),
    ('step_id', 'step_id', False, 9, '0'), ('ifc_class', 'ifc_class', False, 11, None), ('predefined_type', 'predefined_type', False, 12, None),
    ('element_name', 'element_name', False, 26, None), ('type_name', 'type_name', False, 20, None), ('building', 'building', False, 12, None),
    ('storey', 'storey_resolved', False, 16, None), ('storey_elevation_m', 'storey_elevation_m', False, 9, '0.000'),
    ('material_association', 'material_association', False, 16, None), ('material_composition', 'material_classification', False, 30, None),
    ('construction_method_evidence', method_of, False, 26, None), ('concrete_layer_thickness_fraction', 'concrete_layer_thickness_fraction', False, 9, '0.0000'),
    ('geometry_representation', 'geometry_representation', False, 34, None), ('world_bbox_extent_m', 'world_bbox_extent_m', False, 18, None),
    ('geometry_valid_closed_mesh', 'edge_manifold_closed', False, 9, None), ('openings_in_ifc', lambda e: len(e['openings']), False, 7, '0'),
    ('authored_quantity_source', 'authored_quantity_source', False, 16, None), ('authored_net_volume_m3', 'authored_net_volume_m3', False, 11, '0.000000'),
    ('authored_gross_volume_m3', 'authored_gross_volume_m3', False, 11, '0.000000'),
    ('other_authored_quantities', lambda e: json.dumps({k.split('.', 1)[-1]: round(v, 6) for k, v in list(e['authored_quantities'].items())[:12]} or {k: v for k, v in list(e['flattened_quantities'].items())[:10]}, ensure_ascii=False), False, 30, None),
    ('geometry_volume_m3_DERIVED', 'geometry_volume_m3_DERIVED', False, 11, '0.000000'),
    ('layer_based_concrete_volume_m3_DERIVED', 'layer_based_concrete_volume_m3_DERIVED', False, 11, '0.000000'),
    ('design_model_link', 'design_model_link', False, 18, None), ('required_manual_calculation', 'required_independent_manual_calculation', False, 40, None),
    ('suggested_measurement_method', suggested_method, False, 40, None), ('known_limitations', 'known_limitations', False, 40, None),
    # ---- reviewer fields (EMPTY by design)
    ('independent_measurement_method_used', None, True, 28, None), ('measurement_tool_and_version', None, True, 18, None),
    ('measured_dimensions', None, True, 28, None), ('deductions', None, True, 22, None),
    ('independent_calculated_volume_m3', None, True, 12, '0.000000'),
    ('abs_discrepancy_vs_authored_m3', 'F_ABS_A', False, 12, '0.000000'), ('rel_discrepancy_vs_authored', 'F_REL_A', False, 10, '0.00%'),
    ('abs_discrepancy_vs_geometry_m3', 'F_ABS_G', False, 12, '0.000000'), ('rel_discrepancy_vs_geometry', 'F_REL_G', False, 10, '0.00%'),
    ('proposed_tolerance_rel', None, True, 10, '0.00%'), ('approved_tolerance_rel', None, True, 10, '0.00%'),
    ('within_approved_tolerance', 'F_TOL', False, 10, None), ('reviewer', None, True, 14, None), ('review_date', None, True, 11, 'yyyy-mm-dd'),
    ('validation_status', 'STATUS', True, 16, None), ('supporting_evidence', None, True, 30, None), ('reviewer_notes', None, True, 30, None),
]
H = {c[0]: i + 1 for i, c in enumerate(COLS)}
L = {k: get_column_letter(v) for k, v in H.items()}

wb = Workbook()
ws0 = wb.active
ws0.title = 'Instructions'
ws = wb.create_sheet('Validation_40')
wsS = wb.create_sheet('Initial_subset')
wsC = wb.create_sheet('Categories')
wsL = wb.create_sheet('Lists')
GREY = PatternFill('solid', fgColor='EDEDED')
EDIT = PatternFill('solid', fgColor='FFF7D6')
CALC = PatternFill('solid', fgColor='E3EEFA')
HEAD = PatternFill('solid', fgColor='2A78D6')
CATF = {'A': 'E7F4EC', 'B': 'FFF6E5', 'C': 'F3E8FB', 'D': 'FDECEC'}
thin = Border(bottom=Side(style='thin', color='CCCCCC'))

STATUSES = ['Not started', 'In progress', 'Measured - awaiting review', 'Accepted within tolerance', 'Rejected - discrepancy', 'Blocked - insufficient information', 'Excluded']
for i, s in enumerate(STATUSES, 1):
    wsL.cell(i, 1, s)
wsL.cell(1, 3, 'Geometry categories')
for i, s in enumerate(['A simple homogeneous', 'B layered element', 'C irregular geometry', 'D invalid mesh'], 2):
    wsL.cell(i, 3, s)

for j, (h, *_rest) in enumerate(COLS, 1):
    c = ws.cell(1, j, h)
    c.font = Font(bold=True, color='FFFFFF')
    c.fill = HEAD
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.column_dimensions[get_column_letter(j)].width = COLS[j - 1][3]
ws.row_dimensions[1].height = 48
for i, e in enumerate(E, 2):
    for j, (h, key, editable, w, fmt) in enumerate(COLS, 1):
        cell = ws.cell(i, j)
        r = i
        if key == 'F_ABS_A':
            cell.value = f'=IF(OR({L["independent_calculated_volume_m3"]}{r}="",{L["authored_net_volume_m3"]}{r}=""),"",{L["independent_calculated_volume_m3"]}{r}-{L["authored_net_volume_m3"]}{r})'
        elif key == 'F_REL_A':
            cell.value = f'=IF({L["abs_discrepancy_vs_authored_m3"]}{r}="","",{L["abs_discrepancy_vs_authored_m3"]}{r}/{L["authored_net_volume_m3"]}{r})'
        elif key == 'F_ABS_G':
            cell.value = f'=IF(OR({L["independent_calculated_volume_m3"]}{r}="",{L["geometry_volume_m3_DERIVED"]}{r}=""),"",{L["independent_calculated_volume_m3"]}{r}-{L["geometry_volume_m3_DERIVED"]}{r})'
        elif key == 'F_REL_G':
            cell.value = f'=IF({L["abs_discrepancy_vs_geometry_m3"]}{r}="","",{L["abs_discrepancy_vs_geometry_m3"]}{r}/{L["geometry_volume_m3_DERIVED"]}{r})'
        elif key == 'F_TOL':
            ref = f'IF({L["rel_discrepancy_vs_authored"]}{r}<>"",{L["rel_discrepancy_vs_authored"]}{r},{L["rel_discrepancy_vs_geometry"]}{r})'
            cell.value = f'=IF(OR({L["approved_tolerance_rel"]}{r}="",{ref}=""),"",IF(ABS({ref})<={L["approved_tolerance_rel"]}{r},"YES","NO"))'
        elif key == 'STATUS':
            cell.value = 'Not started'
        elif key is None:
            cell.value = None
        else:
            v = key(e) if callable(key) else e.get(key)
            if v in ('', None):
                v = None
            elif isinstance(v, str):
                try:
                    if h in ('authored_net_volume_m3', 'authored_gross_volume_m3', 'geometry_volume_m3_DERIVED', 'layer_based_concrete_volume_m3_DERIVED', 'concrete_layer_thickness_fraction'):
                        v = float(v)
                except ValueError:
                    pass
            cell.value = v
        if fmt:
            cell.number_format = fmt
        cell.fill = EDIT if editable else (CALC if isinstance(key, str) and key.startswith('F_') else (PatternFill('solid', fgColor=CATF[e['geometry_category'][0]]) if h == 'geometry_category' else GREY))
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        cell.border = thin
ws.freeze_panes = 'C2'
ws.auto_filter.ref = f'A1:{get_column_letter(len(COLS))}{len(E) + 1}'
dv = DataValidation(type='list', formula1=f'=Lists!$A$1:$A${len(STATUSES)}', allow_blank=False)
ws.add_data_validation(dv)
dv.add(f'{L["validation_status"]}2:{L["validation_status"]}{len(E) + 1}')
for k in ('independent_calculated_volume_m3', 'proposed_tolerance_rel', 'approved_tolerance_rel'):
    dvn = DataValidation(type='decimal', operator='greaterThanOrEqual', formula1='0', allow_blank=True)
    ws.add_data_validation(dvn)
    dvn.add(f'{L[k]}2:{L[k]}{len(E) + 1}')

# Initial subset sheet (references, so edits stay in one place)
sub_rows = [e for e in E if e['check_id'] in SUBSET]
hdr = ['check_id', 'why_selected', 'model_key', 'ifc_class', 'global_id', 'step_id', 'element_name', 'storey', 'authored_net_volume_m3', 'geometry_volume_m3_DERIVED',
       'independent_calculated_volume_m3 (from Validation_40)', 'validation_status (from Validation_40)']
for j, h in enumerate(hdr, 1):
    c = wsS.cell(1, j, h)
    c.font = Font(bold=True, color='FFFFFF')
    c.fill = HEAD
    wsS.column_dimensions[get_column_letter(j)].width = [9, 50, 11, 11, 24, 9, 26, 16, 12, 12, 16, 22][j - 1]
for i, e in enumerate(sub_rows, 2):
    row_main = E.index(e) + 2
    vals = [e['check_id'], SUBSET[e['check_id']], e['model_key'], e['ifc_class'], e['global_id'], e['step_id'], e['element_name'], e['storey_resolved'],
            float(e['authored_net_volume_m3']) if e['authored_net_volume_m3'] else None, float(e['geometry_volume_m3_DERIVED']),
            f"=IF(Validation_40!{L['independent_calculated_volume_m3']}{row_main}=\"\",\"\",Validation_40!{L['independent_calculated_volume_m3']}{row_main})",
            f"=Validation_40!{L['validation_status']}{row_main}"]
    for j, v in enumerate(vals, 1):
        wsS.cell(i, j, v).alignment = Alignment(wrap_text=True, vertical='top')
wsS.freeze_panes = 'B2'

CATS = [
    ('A simple homogeneous', 'Single material, single extrusion (rectangular or polygon profile), closed mesh, no openings in the IFC.', 'Profile area x extrusion depth.', sum(1 for e in E if e['geometry_category'][0] == 'A')),
    ('B layered element', 'IfcMaterialLayerSetUsage with several layers or concrete fraction < 1.', 'Outline area x each layer thickness; report concrete layer separately.', sum(1 for e in E if e['geometry_category'][0] == 'B')),
    ('C irregular geometry', 'Faceted/polygonal B-rep, boolean clipping or openings.', 'Decompose into measurable parts; subtract voids.', sum(1 for e in E if e['geometry_category'][0] == 'C')),
    ('D invalid mesh', 'Tessellated mesh not closed (open or non-manifold edges).', 'Do not use mesh volume; measure from linked design element or drawings.', sum(1 for e in E if e['geometry_category'][0] == 'D')),
]
for j, h in enumerate(['category', 'definition', 'measurement approach', 'elements'], 1):
    c = wsC.cell(1, j, h)
    c.font = Font(bold=True, color='FFFFFF')
    c.fill = HEAD
for i, row in enumerate(CATS, 2):
    for j, v in enumerate(row, 1):
        wsC.cell(i, j, v).alignment = Alignment(wrap_text=True, vertical='top')
for j, w in enumerate([22, 60, 60, 10], 1):
    wsC.column_dimensions[get_column_letter(j)].width = w

INSTR = [
    'PMI Stage 5.1 - manual quantity validation workbook (research only)',
    '',
    'Purpose: record INDEPENDENT engineering measurements for 40 concrete elements proposed in Stage 4.0B (quantity_validation_plan.csv).',
    'Nothing in this workbook is ground truth until a reviewer fills the yellow columns. Grey columns are copied from IFC audits; *_DERIVED values come from IfcOpenShell tessellation.',
    '',
    'Colour key: grey = source data (do not edit) | yellow = reviewer input | blue = formula | category cell colour = geometry category.',
    '',
    'Workflow:',
    '1. Start with the Initial_subset sheet (11 straightforward elements). Measure them in Validation_40 (the subset sheet only mirrors values).',
    '2. Locate each element by GlobalId (or STEP id) in an independent BIM viewer - see measurement_guide.md. Do NOT copy values from the PMI importer or this workbook.',
    '3. Record method, tool/version, measured dimensions and deductions, then the independent volume in m3.',
    '4. Discrepancy columns compute automatically against the authored NetVolume and the derived geometry volume.',
    '5. Tolerances: the engineering owner proposes and approves tolerances (relative). Leave blank until agreed; within_approved_tolerance stays blank until then.',
    '6. Set validation_status from the list. Use "Blocked - insufficient information" rather than guessing; never enter 0 for an unknown quantity.',
    '7. Attach supporting evidence (screenshots, measurement exports, drawing references) and cite the file names in supporting_evidence.',
    '',
    'Rules: element volume is not concrete volume for layered elements; foundations in SCHEPENDOMLAAN are modelled as IfcBeam ("fund_*"); Synchro elements link to design elements via the "_(#STEP id)" name suffix; QV37 has an open mesh.',
    'Generated from research/validation/stage5_1_manual/scripts/build_manual_validation.py. Do not regenerate after reviewers start editing (it would overwrite entries).',
]
for i, t in enumerate(INSTR, 1):
    c = ws0.cell(i, 1, t)
    c.alignment = Alignment(wrap_text=True)
    if i == 1:
        c.font = Font(bold=True, size=14)
ws0.column_dimensions['A'].width = 150
path = f'{OUT}/manual_quantity_validation.xlsx'
if os.path.exists(path):
    raise SystemExit(f'{path} exists - refusing to overwrite a workbook that may contain reviewer entries')
wb.save(path)
print('saved', path, len(E), 'rows; subset', len(sub_rows))

with open(f'{OUT}/initial_validation_subset.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['check_id', 'why_selected', 'geometry_category', 'model_key', 'model_role', 'ifc_path', 'global_id', 'step_id', 'ifc_class', 'element_name', 'storey',
                'authored_net_volume_m3', 'geometry_volume_m3_DERIVED', 'suggested_measurement_method', 'independent_calculated_volume_m3', 'validation_status'])
    for e in sub_rows:
        w.writerow([e['check_id'], SUBSET[e['check_id']], e['geometry_category'], e['model_key'], e['validation_role'], e['ifc_path'], e['global_id'], e['step_id'],
                    e['ifc_class'], e['element_name'], e['storey_resolved'], e['authored_net_volume_m3'], e['geometry_volume_m3_DERIVED'], suggested_method(e), '', 'Not started'])
print('subset csv', len(sub_rows))
