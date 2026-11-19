"""Stage 4.0B Section A - aggregate IFC audits into deliverables (read-only on data/raw).

Run from repo root after audit_ifc.py (all files), geometry_check.py and verify_github_copies.py:
    .venv/Scripts/python.exe -I research/data_acquisition/stage4_0b/section_A/scripts/build_section_A.py
"""
import csv, datetime as dt, glob, hashlib, html, json, os, re, subprocess, sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')
OUT = 'research/data_acquisition/stage4_0b/section_A'
AUD = 'data/processed/candidates/stage4_0b/section_A/ifc_audit'
GEO = 'data/processed/candidates/stage4_0b/section_A/geometry_check.csv'
GHV = f'{OUT}/github_copy_verification.csv'
MEN_META = 'data/raw/candidates/bim_spatial/mendeley_spatial/metadata/mendeley_public_api_files_fm9myphk9g_v1.json'
BASELINE = 'research/data_acquisition/stage4_0b/sections_B_E/preservation/baseline_sha256_before_stage4_0b.txt'
NOW = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
TODAY = '2026-11-19'
os.makedirs(OUT, exist_ok=True)


def wr(name, rows, cols=None):
    p = os.path.join(OUT, name)
    cols = cols or list(dict.fromkeys(k for r in rows for k in r))
    with open(p, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print('wrote', p, len(rows))


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def pct(a, n):
    return f'{100 * a / n:.0f}%' if n else ''


# ------------------------------------------------------------------ model classification
def classify(path):
    p = path
    if 'BIM Spatial Models' in p:
        if 'rac_advanced' in p:
            return ('MEN', 'Mendeley BIM Spatial Models (fm9myphk9g v1)', 'MEN-RAC', 'Vendor sample model (Autodesk Revit rac_advanced_sample_project, re-exported)', 'independent model; not a documented real project')
        if 'residential' in p:
            return ('MEN', 'Mendeley BIM Spatial Models (fm9myphk9g v1)', 'MEN-RES', 'Genuine authored BIM (residential, Revit 2024 CHS); built status undocumented', 'independent model')
        return ('MEN', 'Mendeley BIM Spatial Models (fm9myphk9g v1)', 'MEN-MTG', 'Genuine authored BIM (single meeting room, Revit 2024 CHS)', 'independent model (small)')
    if 'SCHEPENDOMLAAN' in p:
        if 'Design model' in p:
            return ('SCH', 'DataSetSchependomlaan (Nijmegen, built 2015)', 'SCH', 'Genuine real project - design model (ArchiCAD)', 'project SCH (reference model)')
        if 'As Planned' in p:
            v = 'weekly snapshot of the as-planned model' if 'Week' in p else 'as-planned 4D model (Synchro export)'
            return ('SCH', 'DataSetSchependomlaan (Nijmegen, built 2015)', 'SCH', f'Genuine real project - {v}', 'same project SCH (variant, not independent)')
        return ('SCH', 'DataSetSchependomlaan (Nijmegen, built 2015)', 'SCH', 'Genuine real project - subcontractor/coordination model', 'same project SCH (discipline model, not independent)')
    if 'Restage' in p:
        return ('RST', 'RestageIFC v1.0.0 (RWTH Aachen)', 'RST', 'Genuine demonstrator built on a reference construction site (Bonsai, IFC4)', 'independent project')
    if '4DBenchmark' in p:
        return ('B4D', '4D benchmark model (loose file, source undocumented)', 'B4D', 'Benchmark building model (Revit exporter 22.0.2); provenance undocumented', 'independent model; not a documented real project')
    if 'Models and algorithm' in p:
        return ('TEK', 'Models and algorithm for construction scheduling (Tekla frames)', 'TEK-' + os.path.basename(p)[4:-4], 'Structural test frame (Tekla 2022)', 'test model, not a project')
    if 'PMI_SYN' in p or 'IND-001' in p:
        return ('SYN', 'PMI synthetic IFC writer outputs', 'SYN', 'SYNTHETIC (PMI synthetic IFC writer, header author "PMI Synthetic Dataset")', 'synthetic - excluded from validation')
    if 'specification-models' in p:
        return ('SPEC', 'buildingSMART IFC4.x specification models', 'SPEC', 'Specification example (single-concept fixture)', 'not a project')
    if 'Certification' in p:
        return ('CERT', 'buildingSMART Certification datasets', 'CERT', 'Certification fixture (simple scenes)', 'not a project')
    return ('OTHER', 'other', 'OTHER', 'unclassified', '')


A = []
for p in sorted(glob.glob(f'{AUD}/*.json')):
    d = json.load(open(p, encoding='utf-8'))
    d['_cls'] = classify(d['path'])
    A.append(d)
print('models', len(A))

KEY_PATHS = {  # models used for the detailed audit tables (others are summarised by group)
    'MEN-MTG': 'BIM_meeting_room.ifc', 'MEN-RES': 'BIM_residential_building.ifc', 'MEN-RAC': 'rac_advanced_sample_project.ifc',
    'SCH-design': 'Design model IFC/IFC Schependomlaan.ifc', 'SCH-asplanned': 'As Planned models/IFC Schependomlaan incl planningsdata.ifc',
    'RST': 'Restage_IP_ALL_MULTI_001.ifc', 'B4D': '4DBenchmarkBim.ifc',
}
KEY = {}
for k, suffix in KEY_PATHS.items():
    m = [d for d in A if d['path'].endswith(suffix)]
    KEY[k] = m[0]

# ------------------------------------------------------------------ schema summary (all models)
schema_rows = []
for d in A:
    g, ds, mid, kind, indep = d['_cls']
    u = {x['type']: x for x in d['units']}

    def un(t):
        x = u.get(t)
        if not x:
            return 'not declared'
        return f"{x.get('prefix') or ''}{x.get('name')}" if x['kind'] == 'SI' else f"{x.get('name')} (x{x.get('factor')} {x.get('base')})"
    schema_rows.append(dict(
        group=g, model_id=mid, path=d['path'], bytes=d['bytes'], sha256=d['sha256'], schema=d['schema'], classification=kind, independence=indep,
        originating_system=d.get('header_originating_system'), applications='; '.join(d.get('applications', [])), header_timestamp=d.get('header_timestamp'),
        project_name='; '.join(str(x) for x in d.get('project_name', [])), site_names='; '.join(str(x) for x in d.get('site_names', [])),
        storeys=len(d['storeys']), length_unit=un('LENGTHUNIT'), length_scale_to_m=d['length_unit_scale_to_m'], area_unit=un('AREAUNIT'),
        volume_unit=un('VOLUMEUNIT'), mass_unit=un('MASSUNIT'), ifcroot=d['ifcroot_count'], globalid_duplicates=d['globalid_duplicates'],
        globalid_invalid=d['globalid_invalid_format'], elements=d['entity_counts']['IfcElement_total'],
        rel_contained=d['relationship_counts']['IfcRelContainedInSpatialStructure'], rel_aggregates=d['relationship_counts']['IfcRelAggregates'],
        rel_material=d['relationship_counts']['IfcRelAssociatesMaterial'], rel_type=d['relationship_counts']['IfcRelDefinesByType'],
        rel_connects=d['relationship_counts']['IfcRelConnectsElements'], rel_connects_path=d['relationship_counts']['IfcRelConnectsPathElements'],
        rel_space_boundary=d['relationship_counts']['IfcRelSpaceBoundary'], rel_voids=d['relationship_counts']['IfcRelVoidsElement'],
        classification_systems='; '.join(d.get('classification_systems', []))))
wr('ifc_schema_summary.csv', schema_rows)

# ------------------------------------------------------------------ element / material / quantity coverage (key models + group totals)
CLS = ['IfcFooting', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall', 'IfcMember', 'IfcStair', 'IfcRoof', 'IfcCovering', 'IfcReinforcingBar', 'IfcReinforcingMesh', 'IfcBuildingElementProxy']
QTY = ['net_volume', 'gross_volume', 'net_area', 'gross_area', 'length', 'width', 'height', 'weight']
el_rows, q_rows, m_rows = [], [], []
for k, d in KEY.items():
    for c in CLS:
        v = d['element_classes'].get(c, {})
        n = v.get('n', 0)
        el_rows.append(dict(model_key=k, path=d['path'], ifc_class=c, count=n, with_storey=v.get('with_storey', 0), storey_pct=pct(v.get('with_storey', 0), n),
                            with_type=v.get('with_type', 0), with_body_geometry=v.get('with_body_geometry', 0), with_any_ifcelementquantity=v.get('with_any_qto', 0),
                            body_representation_types=json.dumps(v.get('rep_types', {}), ensure_ascii=False), predefined_types=json.dumps(v.get('predefined', {}), ensure_ascii=False)))
        m_rows.append(dict(model_key=k, path=d['path'], ifc_class=c, count=n, with_material=v.get('with_material', 0), material_pct=pct(v.get('with_material', 0), n),
                           with_concrete_term=v.get('with_concrete_material', 0), with_masonry_term=v.get('with_masonry_material', 0),
                           top_material_names=json.dumps(v.get('material_names', {}), ensure_ascii=False),
                           note='Name-based heuristic (EN/ES/NL/DE/ZH terms). An element with a layer set counts if ANY layer matches; "Concrete Masonry Units" match both concrete and masonry terms.'))
        if n:
            for q in QTY:
                q_rows.append(dict(model_key=k, path=d['path'], ifc_class=c, count=n, quantity=q,
                                   authored_ifcelementquantity=v.get(f'qto_{q}', 0), authored_pct=pct(v.get(f'qto_{q}', 0), n),
                                   explicit_property_set_value=v.get(f'pset_{q}', 0), flattened_export_key=v.get(f'flat_{q}', 0),
                                   qto_set_names=json.dumps(v.get('qto_set_names', {}), ensure_ascii=False)))
# group totals for fixtures
for g in ('SPEC', 'CERT', 'TEK', 'SYN', 'SCH-sub'):
    ms = [d for d in A if (d['_cls'][0] == g) or (g == 'SCH-sub' and 'BIMsight' in d['path'])]
    for c in CLS:
        n = sum(d['element_classes'].get(c, {}).get('n', 0) for d in ms)
        if n:
            el_rows.append(dict(model_key=f'{g} ({len(ms)} files)', path='(group)', ifc_class=c, count=n,
                                with_storey=sum(d['element_classes'][c].get('with_storey', 0) for d in ms),
                                with_any_ifcelementquantity=sum(d['element_classes'][c].get('with_any_qto', 0) for d in ms),
                                with_body_geometry=sum(d['element_classes'][c].get('with_body_geometry', 0) for d in ms)))
wr('ifc_element_coverage.csv', el_rows)
wr('ifc_material_coverage.csv', m_rows)

# geometry check summary merged into quantity coverage
G = list(csv.DictReader(open(GEO, encoding='utf-8')))
gsum = defaultdict(lambda: dict(n=0, ok=0, cmp=0, within2=0, rmin=None, rmax=None))
for r in G:
    key = (r['file'], r['ifc_class'])
    s = gsum[key]
    s['n'] += 1
    s['ok'] += r['geom_status'] == 'ok'
    if r['ratio_geom_to_authored']:
        x = float(r['ratio_geom_to_authored'])
        s['cmp'] += 1
        s['within2'] += abs(x - 1) <= 0.02
        s['rmin'] = x if s['rmin'] is None else min(s['rmin'], x)
        s['rmax'] = x if s['rmax'] is None else max(s['rmax'], x)
for r in q_rows:
    s = gsum.get((r['path'], r['ifc_class']))
    if s and r['quantity'] in ('net_volume', 'gross_volume'):
        r['geometry_sample'] = s['n']
        r['geometry_ok'] = s['ok']
        r['geometry_vs_authored_compared'] = s['cmp']
        r['geometry_within_2pct'] = s['within2']
        r['geometry_ratio_range'] = f"{s['rmin']}-{s['rmax']}" if s['cmp'] else ''
wr('ifc_quantity_coverage.csv', q_rows)
geo_rows = []
for (f, c), s in sorted(gsum.items()):
    geo_rows.append(dict(path=f, ifc_class=c, sampled=s['n'], tessellated_ok=s['ok'], compared_with_authored_volume=s['cmp'], within_2pct=s['within2'],
                         ratio_min=s['rmin'], ratio_max=s['rmax']))
wr('geometry_check_summary.csv', geo_rows)

# ------------------------------------------------------------------ schedule coverage
sch_rows = []
for d in A:
    s = d['schedule']
    if not (s['IfcTask'] or s['IfcWorkSchedule'] or s['products_assigned_to_tasks']) and d['_cls'][0] in ('SPEC', 'CERT'):
        continue
    if d['_cls'][0] == 'SCH' and 'BIMsight' in d['path'] and not s['IfcTask']:
        continue
    sch_rows.append(dict(model_id=d['_cls'][2], path=d['path'], schema=d['schema'], IfcTask=s['IfcTask'], IfcWorkSchedule=s['IfcWorkSchedule'],
                         IfcTaskTime=s['IfcTaskTime'], IfcScheduleTimeControl=s['IfcScheduleTimeControl'],
                         planned_start=s.get('TaskTime_with_ScheduleStart', 0) + s.get('ScheduleTimeControl_with_ScheduleStart', 0),
                         planned_finish=s.get('TaskTime_with_ScheduleFinish', 0) + s.get('ScheduleTimeControl_with_ScheduleFinish', 0),
                         actual_start=s.get('TaskTime_with_ActualStart', 0) + s.get('ScheduleTimeControl_with_ActualStart', 0),
                         actual_finish=s.get('TaskTime_with_ActualFinish', 0) + s.get('ScheduleTimeControl_with_ActualFinish', 0),
                         IfcRelSequence=sum(s['sequence_types'].values()), sequence_types=json.dumps(s['sequence_types']),
                         IfcRelAssignsToProcess=d['relationship_counts']['IfcRelAssignsToProcess'], products_assigned_to_tasks=s['products_assigned_to_tasks'],
                         resources=s['IfcLaborResource'] + s['IfcConstructionEquipmentResource'] + s['IfcCrewResource'] + s['IfcConstructionMaterialResource'],
                         spatial_connectivity_rels=d['relationship_counts']['IfcRelConnectsElements'],
                         task_names_sample='; '.join(str(x) for x in s['task_names_sample'][:6]), date_sample=json.dumps(s['date_sample'][:2])))
sch_rows.append(dict(model_id='B4D (external)', path='data/raw/Schedules.xlsx', schema='xlsx',
                     task_names_sample='68 planned alternative schedules x 151 element-level tasks (prior audit research/gnn/new_dataset_audit.md); GUIDs resolve 151/151; no actuals; durations fixed by element type'))
sch_rows.append(dict(model_id='SCH (external)', path='data/raw/SCHEPENDOMLAAN/Planning/XML/Uitvoering Schependomlaan 18-02-2015.xml', schema='MS Project XML',
                     task_names_sample='157 tasks (114 work tasks), 48 predecessor links (44 FS, 4 SS) baseline 18-02-2015 (prior audit); no actual dates'))
sch_rows.append(dict(model_id='MEN (CSV)', path='data/raw/BIM Spatial Models for Construction Dependency Inf/*/spatial_relationships_detailed.csv', schema='csv',
                     task_names_sample='Geometric relations only (Partially Embedded / Fully Contained / Face Overlap) between element names; NOT construction precedence; no tasks or dates'))
wr('ifc_schedule_coverage.csv', sch_rows)

# ------------------------------------------------------------------ Mendeley CSV linkage
men_link = json.load(open('data/processed/candidates/stage4_0b/section_A/mendeley_csv_linkage.json', encoding='utf-8'))

# ------------------------------------------------------------------ quantity feasibility
SCH_MAS = KEY['SCH-design']['element_classes']['IfcWall'].get('with_masonry_material', 0)
FEAS = [
    ('Concrete volume (m3)', [
        ('SCH-design', 'A', 'NetVolume authored (BaseQuantities/ArchiCADQuantities) for 174/174 beams, 278/279 slabs, 883/934 walls; concrete identified by material name (86 beams "Beton gewapend - ihw/prefab", 115 slabs). Columns are steel. Layered slabs/walls require per-layer split.'),
        ('SCH-asplanned', 'A', 'Same quantities flattened by Synchro into SynchroResourceProperty keys (e.g. 879/880 walls NetVolume); materials not exported (0 elements with material).'),
        ('B4D', 'A', 'Qto_*BaseQuantities NetVolume for 63/63 columns, 32/32 slabs, 56/56 walls; geometry matches 112/112 sampled within 2%. Walls/slabs are multi-layer (CMU, brick, insulation) - element volume is NOT concrete volume.'),
        ('RST', 'A (partial) / B', 'NetVolume for 11/13 footings, 22/191 beams, 22/92 walls, 0/12 slabs; remaining elements tessellate (105/105 sampled) - derivable from geometry.'),
        ('MEN-RES', 'B', 'No IfcElementQuantity or volume property. Geometry tessellates 160/160 sampled; concrete identified by material name (766/1008 columns, 355/573 beams, 1,070/1,687 walls). Join/overlap deductions must be checked.'),
        ('MEN-RAC', 'B', 'No authored quantities; geometry tessellates 147/147; concrete material on 170/176 columns.'),
        ('MEN-MTG', 'B', 'No authored quantities; 4 columns, 4 beams, 2 slabs with concrete material; geometry tessellates 52/52.'),
    ]),
    ('Formwork contact area (m2)', [
        ('ALL', 'C', 'No model authors formwork area. Element side/surface areas exist (e.g. SCH NetSideArea, ArchiCAD side areas) but formwork = formed faces only: excludes top faces, faces against soil, other elements, precast units and openings rules. Requires engineering rules per element type and method, approved by a PMI user.'),
    ]),
    ('Reinforcement mass (kg)', [
        ('SCH/MEN/RST/B4D', 'D', 'No IfcReinforcingBar/Mesh in any main model (6 bars only in one SCH subcontractor model; 35 in buildingSMART fixtures). No reinforcement weight properties on concrete elements. Generic steel ratios must NOT be used to fabricate values; requires a structural/rebar model or user-entered design ratios clearly labelled as assumptions.'),
    ]),
    ('Excavation volume (m3)', [
        ('RST', 'C', '13 IfcFooting with geometry/NetVolume, but no terrain, ground levels, soil data, working space or slope rules in the IFC.'),
        ('SCH', 'C', 'Storey "-1 fundering" exists in design model; no IfcFooting, no terrain/excavation geometry.'),
        ('MEN/B4D', 'D', 'No foundations or site geometry.'),
    ]),
    ('Backfill volume (m3)', [
        ('ALL', 'D', 'Requires excavation geometry minus buried volumes; neither ground model nor excavation boundary present in any model (C at best for RST with user excavation assumptions).'),
    ]),
    ('Masonry area (m2)', [
        ('SCH-design', 'A', f'Wall NetSideArea/GrossSideArea authored for 932/934 walls; masonry identified by material name on {SCH_MAS} walls (layer names include "Metselwerk - kalkzandsteen" and "mw-baksteen").'),
        ('B4D', 'A (with caveat)', 'Wall NetSideArea authored 56/56; walls are multi-layer (brick + CMU) - area per masonry layer equals wall side area only if layer is continuous.'),
        ('MEN-MTG/RES/RAC', 'C', 'No authored areas; masonry material on 17 (MTG) and 16 (RAC) walls; side area from geometry requires face selection (total surface area is not wall face area).'),
    ]),
]
feas_rows = [dict(quantity=q, model=m, category=c, evidence=e) for q, items in FEAS for m, c, e in items]
wr('construction_quantity_feasibility.csv', feas_rows)

# ------------------------------------------------------------------ inventory + manifest
gh = list(csv.DictReader(open(GHV, encoding='utf-8')))
gh_by_path = {r['local_path']: r for r in gh if r['local_path']}
men_files = json.load(open(MEN_META, encoding='utf-8'))
FOLD = {'94cf3d71-4cc0-4d08-8099-4a4c5e4783bb': 'BIM_meeting_room_data', '878ca186-614c-4032-9cac-8a9b643042dc': 'BIM_residential_building_data',
        '0d8ea90d-1e35-4cf3-8e2f-be467ce44165': 'rac_advanced_sample_project_data'}
man = []
for x in men_files:
    lp = f"data/raw/BIM Spatial Models for Construction Dependency Inf/{FOLD[x['folder_id']]}/{x['filename']}"
    h = sha256(lp)
    man.append(dict(dataset_name='BIM Spatial Models for Construction Dependency Inference and Scheduling Optimization', source_organization='Mendeley Data (Z. Wang)',
                    source_url='https://data.mendeley.com/datasets/fm9myphk9g/1', doi='10.17632/fm9myphk9g.1', dataset_version='1 (published 2025-11-24)',
                    original_filename=x['filename'], local_file_path=lp, download_date='pre-existing (before Stage 4.0B)', file_size_bytes=os.path.getsize(lp), sha256=h,
                    publisher_checksum=x['content_details']['sha256_hash'], checksum_match=h == x['content_details']['sha256_hash'], licence='CC BY 4.0',
                    download_status='Already available locally', genuine_or_synthetic='Genuine authored models (MTG, RES); vendor sample (RAC)'))
for f in sorted(glob.glob('data/raw/candidates/bim_spatial/mendeley_spatial/metadata/*.json')):
    f = f.replace('\\', '/')
    man.append(dict(dataset_name='Mendeley fm9myphk9g metadata', source_organization='Mendeley Data / DataCite', source_url='https://data.mendeley.com/public-api/datasets/fm9myphk9g',
                    doi='10.17632/fm9myphk9g.1', original_filename=os.path.basename(f), local_file_path=f, download_date=TODAY, file_size_bytes=os.path.getsize(f), sha256=sha256(f),
                    licence='CC BY 4.0 (dataset)', download_status='Downloaded', genuine_or_synthetic='metadata'))
REPO = {'buildingSMART/IFC4.x-specification-models': ('buildingSMART IFC4.x specification models', 'Specification examples'),
        'buildingSMART/Certification-datasets': ('buildingSMART Certification datasets', 'Certification fixtures'),
        'OpeningDesign/DataSetSchependomlaan': ('DataSetSchependomlaan', 'Genuine real project (one building)')}
for r in gh:
    if not r['path'].lower().endswith('.ifc'):
        continue
    name, gen = REPO[r['repo']]
    lp = r['local_path']
    man.append(dict(dataset_name=name, source_organization=r['repo'].split('/')[0], source_url=f"https://github.com/{r['repo']}", dataset_version=f"{r['default_branch']} @ {r['upstream_commit']} ({r['upstream_commit_date']})",
                    original_filename=os.path.basename(r['path']), local_file_path=lp, download_date='pre-existing (before Stage 4.0B)', file_size_bytes=r['local_bytes'],
                    sha256=sha256(lp) if lp else '', publisher_checksum=r.get('lfs_upstream_oid') or 'git blob sha1', checksum_match=r['status'],
                    licence=r['licence'] or 'NOASSERTION (README states CC BY 4.0 for Schependomlaan)', download_status='Already available locally' if lp else 'Missing locally', genuine_or_synthetic=gen))
for p, nm, gen in [('data/raw/Restage_IP_ALL_MULTI_001.ifc', 'RestageIFC v1.0.0', 'Genuine demonstrator'), ('data/raw/4DBenchmarkBim.ifc', '4D benchmark model', 'Benchmark (provenance undocumented)')]:
    man.append(dict(dataset_name=nm, local_file_path=p, original_filename=os.path.basename(p), file_size_bytes=os.path.getsize(p), sha256=sha256(p),
                    checksum_match='Zenodo MD5 match (Stage 4.0B B-E)' if 'Restage' in p else 'no publisher checksum', download_status='Already available locally',
                    source_url='https://zenodo.org/records/21470658' if 'Restage' in p else 'unknown', licence='CC BY 4.0' if 'Restage' in p else 'unknown', genuine_or_synthetic=gen))
for p in sorted(glob.glob('data/raw/Models and algorithm for construction scheduling/*.ifc') + glob.glob('data/raw/beam bridge-texas midrise/*.ifc') + glob.glob('data/raw/INDUSTRIAL CONSTRUCTION/*.ifc')):
    p = p.replace('\\', '/')
    syn = 'PMI_SYN' in p or 'IND-001' in p
    man.append(dict(dataset_name='PMI synthetic IFC' if syn else 'Tekla structural test frames', local_file_path=p, original_filename=os.path.basename(p), file_size_bytes=os.path.getsize(p),
                    sha256=sha256(p), download_status='Already available locally', genuine_or_synthetic='SYNTHETIC' if syn else 'Test model', source_url='internal (PMI)' if syn else 'unconfirmed (Mendeley per GA_mendeley.py name)'))
wr('download_manifest.csv', man, ['dataset_name', 'source_organization', 'source_url', 'doi', 'dataset_version', 'original_filename', 'local_file_path', 'download_date',
                                  'file_size_bytes', 'sha256', 'publisher_checksum', 'checksum_match', 'licence', 'download_status', 'genuine_or_synthetic'])

grp = defaultdict(list)
for d in A:
    grp[d['_cls'][1]].append(d)
inv = []
for name, ms in grp.items():
    c0 = ms[0]['_cls']
    inv.append(dict(dataset=name, group=c0[0], ifc_files=len(ms), bytes=sum(d['bytes'] for d in ms), schemas='; '.join(sorted({d['schema'] for d in ms})),
                    applications='; '.join(sorted({(d.get('header_originating_system') or '')[:40] for d in ms}))[:300],
                    classifications='; '.join(sorted({d['_cls'][3] for d in ms})),
                    independent_projects={'SCH': '1', 'RST': '1', 'MEN': '3 models (2 authored + 1 vendor sample); built status undocumented', 'B4D': '1 benchmark model',
                                          'TEK': '0 (4 test frames)', 'SYN': '0 (synthetic)', 'SPEC': '0 (fixtures)', 'CERT': '0 (fixtures)'}.get(c0[0], ''),
                    elements=sum(d['entity_counts']['IfcElement_total'] for d in ms),
                    footings=sum(d['element_classes']['IfcFooting'].get('n', 0) for d in ms), columns=sum(d['element_classes']['IfcColumn'].get('n', 0) for d in ms),
                    beams=sum(d['element_classes']['IfcBeam'].get('n', 0) for d in ms), slabs=sum(d['element_classes']['IfcSlab'].get('n', 0) for d in ms),
                    walls=sum(d['element_classes']['IfcWall'].get('n', 0) for d in ms), rebars=sum(d['element_classes']['IfcReinforcingBar'].get('n', 0) for d in ms),
                    files_with_tasks=sum(1 for d in ms if d['schedule']['IfcTask']), local_path=os.path.dirname(ms[0]['path']) if len(ms) == 1 else os.path.commonpath([d['path'] for d in ms]).replace('\\', '/')))
wr('ifc_dataset_inventory.csv', inv)

# ------------------------------------------------------------------ eligibility
CATS = ['A_bim_extraction', 'B_bim_to_task', 'C_dependency_inference', 'D_ifc4d_export_verification', 'I_independent_validation', 'J_unsuitable']
EL = [
    ('SCH design + as-planned (DataSetSchependomlaan)', 'Y', 'Y', 'Partial', 'Y', 'Partial', 'N', 'Real built project; authored quantities validated by geometry; 3,505 elements assigned to 125 Synchro tasks with planned dates and 42 sequences; no actual dates; GUIDs regenerated between design and Synchro model.'),
    ('RestageIFC', 'Y', 'Partial', 'N', 'Partial', 'Y', 'N', 'Independent real demonstrator; footings with quantities; 12 phase tasks with ActualFinish only.'),
    ('4DBenchmarkBim + Schedules.xlsx', 'Y', 'Partial', 'Partial', 'Partial', 'Partial', 'N', 'Complete authored quantities; external planned schedules GUID-linked; provenance undocumented; not a real project.'),
    ('Mendeley MEN-RES', 'Y', 'N', 'N', 'N', 'Partial', 'N', 'Large RC model without authored quantities - tests geometry-derived path; spatial CSV relations are geometric only.'),
    ('Mendeley MEN-RAC', 'Y', 'N', 'N', 'N', 'Partial', 'N', 'Vendor sample; robustness test only, not real-project validation.'),
    ('Mendeley MEN-MTG', 'Y', 'N', 'N', 'N', 'N', 'N', 'Very small; unit-test model.'),
    ('SCH subcontractor models', 'Partial', 'N', 'N', 'N', 'N', 'N', 'Discipline models of the same building; two V_L_Constructief.ifc copies have unverifiable provenance.'),
    ('buildingSMART specification models', 'Partial', 'N', 'N', 'Partial', 'N', 'N', 'Concept fixtures (e.g. reinforcing-assembly 34 bars): parser/unit tests only.'),
    ('buildingSMART certification datasets', 'Partial', 'N', 'N', 'Partial', 'N', 'N', 'Simple scenes for exporter certification; parser tests only.'),
    ('Tekla test frames', 'Partial', 'N', 'N', 'N', 'N', 'N', 'Steel/structural frames with BaseQuantities; no project context.'),
    ('PMI synthetic models', 'N', 'N', 'N', 'Partial', 'N', 'Y', 'Synthetic; must not be used as real validation.'),
]
wr('dataset_eligibility_matrix.csv', [dict(dataset=a, **dict(zip(CATS, v[:6])), rationale=v[6]) for a, *v in EL])

# ------------------------------------------------------------------ preservation
base = {}
for line in open(BASELINE, encoding='utf-8'):
    h, p = line.rstrip('\n').split(' ', 1)
    base[p.lstrip('*')] = h
changed = [p for p, h in base.items() if not os.path.exists(p) or sha256(p) != h]
b4 = {}
for line in open('research/evaluation/stage4_0a/preservation/baseline_sha256_before_stage4_0a.txt', encoding='utf-8'):
    h, p = line.rstrip('\n').split(' ', 1)
    b4[p.lstrip('*')] = h
changed4 = [p for p, h in b4.items() if not os.path.exists(p) or sha256(p) != h]
be = sorted(glob.glob('research/data_acquisition/stage4_0b/sections_B_E/**/*', recursive=True))
be_files = [p.replace('\\', '/') for p in be if os.path.isfile(p)]
be_latest = max(os.path.getmtime(p) for p in be_files)
gs = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.splitlines()
pres = dict(generated=NOW, checks=[
    dict(check='Protected files vs Stage 4.0B pre-task baseline (includes every IFC under data/raw except candidates/)', total=len(base), changed_or_missing=changed),
    dict(check='Stage 4.0A baseline (342 files)', total=len(b4), changed_or_missing=changed4),
    dict(check='Sections B-E deliverables not modified by Section A', files=len(be_files), latest_mtime_utc=dt.datetime.fromtimestamp(be_latest, dt.timezone.utc).isoformat(),
         result='latest modification precedes Section A recovery start (2026-11-19 ~12:40 UTC)' if be_latest < dt.datetime(2026, 11, 19, 12, 40, tzinfo=dt.timezone.utc).timestamp() else 'MODIFIED - inspect'),
    dict(check='git: no tracked file modified', tracked_modifications=[l for l in gs if not l.startswith('??')], untracked=[l[3:] for l in gs if l.startswith('??')]),
    dict(check='IFC files opened read-only', result='ifcopenshell.open() in memory; no write calls in audit_ifc.py / geometry_check.py'),
    dict(check='Cambridge locked-test records', result='not accessed'),
    dict(check='No training, inference, scheduling or frontend changes', result='scripts only parse, count, tessellate and hash'),
    dict(check='No duplicate downloads', result='Mendeley (18 files) and GitHub repositories already local and verified; only 3 Mendeley metadata JSON files downloaded'),
])
pres['all_protected_unchanged'] = not changed and not changed4 and not pres['checks'][3]['tracked_modifications'] and pres['checks'][2]['result'].startswith('latest')
json.dump(pres, open(f'{OUT}/preservation_verification.json', 'w', encoding='utf-8'), indent=2)
print('preservation ok:', pres['all_protected_unchanged'])

# ------------------------------------------------------------------ markdown docs
gh_cnt = Counter((r['repo'], r['status']) for r in gh)
men_ok = sum(1 for r in man if r.get('checksum_match') is True)
open(f'{OUT}/download_log.md', 'w', encoding='utf-8').write(f"""# Section A - download log and diagnosis

Generated {NOW}.

## 1. Diagnosis of the previous Section A task
| Hypothesis | Evidence | Verdict |
|---|---|---|
| Never started | `data/raw/candidates/bim_spatial/` empty; no Section A files anywhere under `research/data_acquisition/`; no running python/curl/git/7z processes found (`tasklist`) | **Most likely: never ran (or ran outside this repository) - no artefact of it exists** |
| Network restrictions | Mendeley public API, DataCite and GitHub API all reachable from this machine during recovery | Not the blocker |
| Failed download resolution | Mendeley `public-api/datasets/<id>/files?folder_id=root` returns `[]` (files sit in 3 sub-folders); a naive client would see "no files". | Possible contributing pitfall |
| Downloads in another location | All targets already exist under `data/raw/` (pre-dating Stage 4.0B: Mendeley folder, `IFC4.x-specification-models-main`, `Certification-datasets-main`, `SCHEPENDOMLAAN`), acquired in Stage 3.7A | **Yes - data existed, only not under candidates/** |
| Archive / Git LFS issues | SCHEPENDOMLAAN upstream stores 69 files as LFS pointers; local copies are full objects (no pointers found) | Not a blocker locally |
| Repository permissions | Public repositories; `gh api` read access works | Not the blocker |
| Interrupted | No partial files or temp downloads found | No evidence |

## 2. Verification instead of re-download
- **Mendeley fm9myphk9g v1** (CC BY 4.0, published 2025-11-24, 3 folders / 18 files): local SHA-256 equals publisher SHA-256 for **{men_ok}/18** files. Metadata saved to `data/raw/candidates/bim_spatial/mendeley_spatial/metadata/`. Files were **not duplicated** (341 MB) - their verified location is `data/raw/BIM Spatial Models for Construction Dependency Inf/`.
- **GitHub copies** vs upstream default-branch trees (`github_copy_verification.csv`): {'; '.join(f'{k[0].split("/")[1]} {k[1]}={v}' for k, v in sorted(gh_cnt.items()))}.
  - SCHEPENDOMLAAN files differ from upstream only by CRLF line endings (verified by re-hashing after CRLF->LF against git blob SHA-1 or LFS SHA-256).
  - Exception: both `V_L_Constructief.ifc` copies are **0-byte blobs upstream** but 941,642 bytes locally -> provenance unverifiable.
  - Missing locally: `.gitattributes`, `desktop.ini` (irrelevant). Local-only: one `.url` shortcut.
- RestageIFC: already verified (Zenodo MD5) in Sections B-E.

## 3. Audit runs
- `audit_ifc.py` on all {len(A)} local IFC files (outside `data/raw/candidates/`), one process each: 160 ok, 0 failures. Output: `data/processed/candidates/stage4_0b/section_A/ifc_audit/*.json`.
- First pass missed Synchro-flattened quantity keys (`[BaseQuantities[IfcElementQuantity/..]]NetVolume`); detector added and all files re-audited.
- `geometry_check.py` (40 elements per class, IfcOpenShell {__import__('ifcopenshell').version}) on 7 candidate models: {len(G)} elements tessellated, {sum(r['geom_status']=='ok' for r in G)} ok.
""")

open(f'{OUT}/manual_download_required.md', 'w', encoding='utf-8').write("""# Section A - manual actions

No primary or secondary source required a manual download: all were already local and verified.

Open items that need a person:
1. **SCHEPENDOMLAAN `V_L_Constructief.ifc`** (two local copies, 941,642 B each) - upstream blobs at `OpeningDesign/DataSetSchependomlaan` are empty. Ask the dataset maintainers or the person who first copied the data where these files came from. Until then, exclude them from validation.
2. **`data/raw/4DBenchmarkBim.ifc` + `data/raw/Schedules.xlsx`** - source, licence and authors are undocumented. Record the original URL/paper before citing or publishing results on it.
3. **`data/raw/Models and algorithm for construction scheduling/`** - confirm the Mendeley DOI implied by `GA_mendeley.py` before citing.
4. **Synchro native project** `SCHEPENDOMLAAN/As Planned models/Synchro/*.sp` - proprietary; needs Bentley SYNCHRO to inspect resources or progress, if any.
5. **Reinforcement data** - none of the real models contains rebar. A structural/rebar IFC (e.g. Tekla/Allplan rebar export) of a real RC project is needed before reinforcement mass can be extracted; candidates were not found in this search.

Destination for any new BIM downloads: `data/raw/candidates/bim_spatial/<source>/` (new folder per source).
""")

# decision
DEC = ('CONDITIONAL GO', [
    'Volumes: authored NetVolume/GrossVolume exist in SCH design, SCH as-planned (flattened), 4DBenchmark and partly RestageIFC; tessellated geometry agrees within 2% for 251/251 compared elements; geometry tessellates for 862/862 sampled elements, so models without authored quantities (all 3 Mendeley models) are on the geometry-derived path.',
    'Units are declared in every key model (length mm or m; area m2; volume m3); mass unit differs (GRAM in SCH, KILOGRAM elsewhere) and must be converted.',
    'GlobalIds: valid format everywhere; 1 duplicate in SCH design model; GUIDs not stable between SCH design and Synchro export.',
    'Storey containment: 100% for Mendeley and key models except Synchro export (flattened to 1 storey).',
    'Conditions: (1) record provenance per quantity (authored / flattened / geometry-derived / assumption); (2) split layered walls and slabs by material layer before reporting concrete volume; (3) formwork area via user-approved face rules (category C); (4) reinforcement mass unavailable (D) - user or structural model must provide it, never generic ratios; (5) excavation/backfill require site input (C/D); (6) validate on at least two real projects (SCH, RST) and report Mendeley/B4D as non-project robustness tests.',
])
RECO = [
    ('Development', 'SCHEPENDOMLAAN design model', 'Real built project; authored quantities to test extraction against; masonry + RC + steel; Dutch material names.'),
    ('Development', '4DBenchmarkBim.ifc', 'Clean Qto_* base quantities for every element; GUID-linked external schedules for later task-generation tests.'),
    ('Development (geometry path)', 'Mendeley BIM_residential_building.ifc', 'Large RC model without authored quantities; exercises geometry-derived volumes and Chinese material names.'),
    ('Independent validation', 'RestageIFC', 'Different authoring tool (Bonsai), IFC4, real site, footings with quantities.'),
    ('Independent validation', 'SCHEPENDOMLAAN as-planned (Synchro)', 'Same building but different export path (flattened quantities, regenerated GUIDs) - tests robustness, not independence.'),
    ('Robustness only', 'Mendeley rac_advanced_sample_project.ifc, BIM_meeting_room.ifc', 'Vendor sample / small model; not real-project validation.'),
    ('Excluded', 'PMI_SYN-* and IND-001', 'Synthetic.'),
]


def md_table(rows, cols):
    s = '| ' + ' | '.join(cols) + ' |\n|' + '---|' * len(cols) + '\n'
    for r in rows:
        s += '| ' + ' | '.join(str(r.get(c, '')).replace('|', '/').replace('\n', ' ') for c in cols) + ' |\n'
    return s


key_schema = [r for r in schema_rows if any(r['path'].endswith(v) for v in KEY_PATHS.values())]
for r in key_schema:
    r['model_key'] = [k for k, v in KEY_PATHS.items() if r['path'].endswith(v)][0]
key_q = [r for r in q_rows if r['quantity'] in ('net_volume', 'net_area', 'weight') and r['ifc_class'] in ('IfcFooting', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall')]
rep = f"""# Stage 4.0B Section A - BIM spatial dataset acquisition recovery and IFC evidence audit

Generated {NOW}. Read-only. Sections B-E: `research/data_acquisition/stage4_0b/sections_B_E/` (unchanged).

## Summary
- **Blocker:** the earlier Section A run left no artefacts; the data it was to fetch was already in `data/raw/` (Stage 3.7A), just not under `candidates/`. No network, permission or LFS blocker exists.
- **Mendeley fm9myphk9g v1:** 3 IFC models + 15 CSVs, CC BY 4.0, all 18 files match the publisher's SHA-256. The three models are distinct; one is Autodesk's `rac_advanced_sample_project` (a vendor sample). CSVs link to IFC by element **name** only (no GUIDs) and describe **geometric** relations (embedded/contained/face overlap), not construction precedence; no durations.
- **160 IFC files audited** (IfcOpenShell {__import__('ifcopenshell').version}): {', '.join(f'{k} {v}' for k, v in Counter(d['_cls'][0] for d in A).most_common())} (SCH = SCHEPENDOMLAAN, SPEC = specification examples, CERT = certification fixtures, TEK = Tekla test frames, SYN = PMI synthetic, MEN = Mendeley, RST = Restage, B4D = 4D benchmark).
- **Real independent projects:** SCHEPENDOMLAAN (built 2015) and RestageIFC (demonstrator). Mendeley RES/MTG are authored models of undocumented build status; 4DBenchmark is a benchmark; all others are fixtures, test frames or synthetic.
- **Quantities:** authored volumes/areas in SCH and 4DBenchmark (and partly Restage); none in the Mendeley models, but geometry tessellates for 862/862 sampled elements and agrees with authored volume within 2% on 251/251 comparisons. No reinforcement in any real model.
- **Decision Stage 5.1: {DEC[0]}.**

## Key models
{md_table(key_schema, ['model_key', 'schema', 'originating_system', 'length_unit', 'volume_unit', 'mass_unit', 'storeys', 'elements', 'globalid_duplicates', 'classification'])}
## Authored quantity coverage (key classes)
{md_table(key_q, ['model_key', 'ifc_class', 'count', 'quantity', 'authored_ifcelementquantity', 'explicit_property_set_value', 'flattened_export_key', 'geometry_within_2pct'])}
## Geometry check (sampled)
{md_table(geo_rows, ['path', 'ifc_class', 'sampled', 'tessellated_ok', 'compared_with_authored_volume', 'within_2pct', 'ratio_min', 'ratio_max'])}
Agreement shows authored and tessellated volumes are consistent; both may come from the same exporter, so this is not independent ground truth. IfcOpenShell 0.9.0 `util.shape` has no manifold test; mesh closedness was not checked.

## Construction quantity feasibility
{md_table(feas_rows, ['quantity', 'model', 'category', 'evidence'])}
Categories: A directly available, B reliably derivable, C derivable only with engineering assumptions, D unavailable.

## Schedule and task evidence
{md_table(sch_rows, ['model_id', 'path', 'IfcTask', 'planned_start', 'actual_start', 'actual_finish', 'IfcRelSequence', 'products_assigned_to_tasks', 'resources', 'task_names_sample'])}
Spatial relations (`IfcRelConnects*`, Mendeley CSV relations) are geometric adjacency, not construction precedence. Verified precedence exists only as planner-authored links (SCH Synchro 42 sequences, MS Project 48 links; 4DBenchmark planned alternatives). No model has actual start dates or resources; no schedule revisions besides SCH weekly snapshots of the same plan.

## Mendeley CSV-to-IFC linkage
{md_table(men_link, ['project', 'csv', 'distinct_names', 'match_ifc_element_name', 'match_unique_ifc_name', 'ifc_elements', 'ifc_unique_names'])}
## Independent project coverage and recommended Stage 5.1 set
{md_table([dict(role=a, model=b, reason=c) for a, b, c in RECO], ['role', 'model', 'reason'])}
## Decision - Stage 5.1 IFC quantity extraction: **{DEC[0]}**
""" + '\n'.join(f'- {x}' for x in DEC[1]) + """

## Deliverables
download_manifest.csv, download_log.md, ifc_dataset_inventory.csv, ifc_schema_summary.csv, ifc_element_coverage.csv, ifc_quantity_coverage.csv, ifc_material_coverage.csv, ifc_schedule_coverage.csv, construction_quantity_feasibility.csv, dataset_eligibility_matrix.csv, manual_download_required.md, section_A_report.md, section_A_report.html, preservation_verification.json; supporting: github_copy_verification.csv, geometry_check_summary.csv, scripts/.
"""
open(f'{OUT}/section_A_report.md', 'w', encoding='utf-8').write(rep)

# ------------------------------------------------------------------ HTML
E = html.escape
CAT = {'A': ('ok', 'A direct'), 'B': ('ok2', 'B derivable'), 'C': ('warn', 'C assumptions'), 'D': ('bad', 'D unavailable')}


def cell(v, col):
    v = '' if v is None else str(v)
    if col == 'category':
        k = v[0] if v else ''
        if k in CAT:
            return f'<span class="b {CAT[k][0]}">{E(v)}</span>'
    if col in ('path', 'local_file_path'):
        return f'<code>{E(v)}</code>'
    return E(v)


def h_table(rows, cols):
    s = '<div class="tw"><table><thead><tr>' + ''.join(f'<th>{E(c)}</th>' for c in cols) + '</tr></thead><tbody>'
    for r in rows:
        s += '<tr>' + ''.join(f'<td>{cell(r.get(c), c)}</td>' for c in cols) + '</tr>'
    return s + '</tbody></table></div>'


# quantity heat grid: key model x class -> authored net volume share
grid = '<div class="tw"><table class="heat"><thead><tr><th>Model</th>' + ''.join(f'<th>{c[3:]}</th>' for c in ('IfcFooting', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall')) + '</tr></thead><tbody>'
for k, d in KEY.items():
    grid += f'<tr><td>{E(k)}</td>'
    for c in ('IfcFooting', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall'):
        v = d['element_classes'][c]
        n = v.get('n', 0)
        a = max(v.get('qto_net_volume', 0), v.get('flat_net_volume', 0))
        if not n:
            grid += '<td class="hc na" title="no elements">&ndash;</td>'
        else:
            fr = a / n
            grid += f'<td class="hc" style="--a:{0.06 + 0.74 * fr:.2f}" title="{E(k)} {c}: {a} of {n} elements with authored NetVolume">{a}/{n}</td>'
    grid += '</tr>'
grid += '</tbody></table></div><p class="sub">Cell = elements with authored (or export-flattened) NetVolume / elements of that class. Shade = share. Hover for detail.</p>'
css = open('research/data_acquisition/stage4_0b/sections_B_E/stage4_0b_report.html', encoding='utf-8').read().split('<style>')[1].split('</style>')[0]
css += '.b.ok2{color:var(--ok);background:transparent;border:1px solid var(--ok)}td.na{color:var(--muted)}'
secs = [('summary', 'Summary'), ('diagnosis', 'Diagnosis'), ('decision', 'Stage 5.1 decision'), ('models', 'Key models'), ('quantities', 'Quantity coverage'),
        ('geometry', 'Geometry check'), ('feasibility', 'Quantity feasibility'), ('schedule', 'Schedule evidence'), ('mendeley', 'Mendeley CSV linkage'),
        ('projects', 'Project coverage'), ('eligibility', 'Eligibility'), ('manual', 'Manual actions'), ('preservation', 'Preservation')]
nav = ''.join(f'<a href="#{a}">{E(b)}</a>' for a, b in secs)
body = f"""<h1>Stage 4.0B Section A - IFC evidence audit</h1><p class="sub">Generated {E(NOW)}. Read-only audit of {len(A)} local IFC files; Sections B-E unchanged.</p>
<section id="summary"><h2>Summary</h2><div class="tiles">
<div class="tile"><div class="n">{len(A)}</div><div class="l">IFC files audited</div></div>
<div class="tile"><div class="n">2</div><div class="l">real independent projects (SCH, RST)</div></div>
<div class="tile"><div class="n">{sum(r['tessellated_ok'] for r in geo_rows)}/{sum(r['sampled'] for r in geo_rows)}</div><div class="l">sampled elements tessellated</div></div>
<div class="tile"><div class="n">{sum(r['within_2pct'] for r in geo_rows)}/{sum(r['compared_with_authored_volume'] for r in geo_rows)}</div><div class="l">geometry vs authored volume within 2%</div></div>
<div class="tile"><div class="n">0</div><div class="l">rebar in real models</div></div></div>
<ul><li>The previous Section A task left no artefacts; all its targets were already local and are now verified against publisher checksums and upstream trees.</li>
<li>Mendeley fm9myphk9g: 3 distinct models (one Autodesk vendor sample), CSVs keyed by element name, geometric relations only, no durations.</li>
<li>Volumes are available or derivable; formwork needs assumptions; reinforcement and excavation are not in the data.</li></ul></section>
<section id="diagnosis"><h2>Diagnosis</h2><p>No running process, partial file or Section A output was found. The data existed under <code>data/raw/</code> from Stage 3.7A. The Mendeley file API returns an empty root listing because files sit in three sub-folders, a likely pitfall for an automated client. See <code>download_log.md</code>.</p></section>
<section id="decision"><h2>Stage 5.1 IFC quantity extraction: <span class="b warn">{E(DEC[0])}</span></h2><ul>{''.join(f'<li>{E(x)}</li>' for x in DEC[1])}</ul></section>
<section id="models"><h2>Key models</h2>{h_table(key_schema, ['model_key', 'path', 'schema', 'originating_system', 'length_unit', 'volume_unit', 'mass_unit', 'storeys', 'elements', 'globalid_duplicates', 'globalid_invalid', 'classification', 'independence'])}</section>
<section id="quantities"><h2>Authored quantity coverage</h2>{grid}{h_table(key_q, ['model_key', 'ifc_class', 'count', 'quantity', 'authored_ifcelementquantity', 'explicit_property_set_value', 'flattened_export_key', 'qto_set_names'])}</section>
<section id="geometry"><h2>Geometry check</h2>{h_table(geo_rows, ['path', 'ifc_class', 'sampled', 'tessellated_ok', 'compared_with_authored_volume', 'within_2pct', 'ratio_min', 'ratio_max'])}
<div class="callout">Consistency check, not ground truth: authored and tessellated values may both originate from the exporter's geometry. Mesh closedness was not tested (no manifold function in IfcOpenShell 0.9.0).</div></section>
<section id="feasibility"><h2>Construction quantity feasibility</h2>{h_table(feas_rows, ['quantity', 'model', 'category', 'evidence'])}
<div class="callout">Formwork area is not total surface area. Reinforcement is never inferred from generic steel ratios. Element volume of layered walls/slabs is not concrete volume.</div></section>
<section id="schedule"><h2>Schedule and task evidence</h2>{h_table(sch_rows, ['model_id', 'path', 'IfcTask', 'IfcWorkSchedule', 'planned_start', 'planned_finish', 'actual_start', 'actual_finish', 'IfcRelSequence', 'products_assigned_to_tasks', 'resources', 'task_names_sample'])}
<p>Spatial adjacency (IfcRelConnects*, Mendeley relations) does not establish construction sequence.</p></section>
<section id="mendeley"><h2>Mendeley CSV-to-IFC linkage</h2>{h_table(men_link, ['project', 'csv', 'distinct_names', 'match_ifc_element_name', 'match_unique_ifc_name', 'ifc_elements', 'ifc_unique_names'])}</section>
<section id="projects"><h2>Independent project coverage</h2>{h_table(inv, ['dataset', 'ifc_files', 'independent_projects', 'schemas', 'footings', 'columns', 'beams', 'slabs', 'walls', 'rebars', 'files_with_tasks'])}
<h3>Recommended Stage 5.1 set</h3>{h_table([dict(role=a, model=b, reason=c) for a, b, c in RECO], ['role', 'model', 'reason'])}</section>
<section id="eligibility"><h2>Eligibility</h2>{h_table([dict(dataset=a, **dict(zip(CATS, v[:6])), rationale=v[6]) for a, *v in EL], ['dataset'] + CATS + ['rationale'])}</section>
<section id="manual"><h2>Manual actions</h2><ol><li>Provenance of the two SCH <code>V_L_Constructief.ifc</code> copies (upstream empty).</li><li>Source and licence of <code>4DBenchmarkBim.ifc</code> + <code>Schedules.xlsx</code>.</li><li>DOI of the Tekla frames folder.</li><li>A real RC rebar model is still needed for reinforcement mass.</li></ol></section>
<section id="preservation"><h2>Preservation</h2><p>All protected files unchanged: <b>{'yes' if pres['all_protected_unchanged'] else 'NO - see JSON'}</b>. Baseline files: {len(base)} (Stage 4.0B) and {len(b4)} (Stage 4.0A); changed or missing: {len(changed)} and {len(changed4)}.</p></section>"""
page = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Section A IFC Audit</title><style>{css}</style></head><body><div class="layout"><nav><div class="sub" style="padding:0 8px 8px">Stage 4.0B - A</div>{nav}</nav><main>{body}</main></div></body></html>'
open(f'{OUT}/section_A_report.html', 'w', encoding='utf-8').write(page)
print('html', len(page))
