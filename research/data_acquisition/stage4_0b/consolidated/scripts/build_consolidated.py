"""Stage 4.0B - consolidated evidence package and Stage 5.1 validation handover.

Run from repo root after consolidation_checks.py:
    .venv/Scripts/python.exe -I research/data_acquisition/stage4_0b/consolidated/scripts/build_consolidated.py <start_snapshot_sha256.txt>
Reads Section A and Sections B-E deliverables (never modifies them) and writes only to
research/data_acquisition/stage4_0b/consolidated/.
"""
import csv, datetime as dt, glob, hashlib, html, json, os, subprocess, sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')
ROOT = 'research/data_acquisition/stage4_0b'
OUT = f'{ROOT}/consolidated'
BE, SA = f'{ROOT}/sections_B_E', f'{ROOT}/section_A'
PROC = 'data/processed/candidates/stage4_0b'
SNAP = sys.argv[1] if len(sys.argv) > 1 else None
NOW = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def rd(p):
    with open(p, encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


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


CHK = json.load(open(f'{PROC}/consolidated/consolidation_checks.json', encoding='utf-8'))
SAMPLE = rd(f'{PROC}/consolidated/quantity_validation_sample_raw.csv')
AUD = {json.load(open(p, encoding='utf-8'))['path']: json.load(open(p, encoding='utf-8')) for p in glob.glob(f'{PROC}/section_A/ifc_audit/*.json')}
GEO = rd(f'{SA}/geometry_check_summary.csv')
BE_INV, BE_EV, BE_DEC = rd(f'{BE}/dataset_inventory.csv'), rd(f'{BE}/combined_evidence_matrix.csv'), rd(f'{BE}/readiness_decisions.csv')
SA_INV = rd(f'{SA}/ifc_dataset_inventory.csv')

# ------------------------------------------------------------------ provenance issues
PROV = [
    dict(issue_id='P1', record='data/raw/4DBenchmarkBim.ifc + data/raw/Schedules.xlsx', status='QUARANTINED (approved validation and redistribution)',
         evidence='Not in git history beyond commit references (data/raw is git-ignored). IFC header: EDM host user "au516160", created 2022-06-09, Revit exporter 22.0.2. Schedules.xlsx core properties: lastModifiedBy "Karsten Winther Johansen", created 2022-06-22, 69 sheets (WorkCrew + 68 plans). These match Johansen, Schultz & Teizer (2023) "Hazard ontology and 4D benchmark model for facilitation of automated construction safety requirement analysis", Computer-Aided Civil and Infrastructure Engineering 38(15), DOI 10.1111/mice.12988, which describes "a freely available 4D BIM-based benchmark model (3D Building Information Model and 68 schedules)".',
         unresolved='Original download location and licence for the model/schedules not found (DTU Orbit lists only the article PDF, CC BY-NC-ND). Authorship is probable, not proven.',
         action='Ask the authors / check the article data-availability section for the official repository and licence. Until then: internal software testing only, no validation claims, no redistribution.'),
    dict(issue_id='P2', record='SCHEPENDOMLAAN .../BIMsight Projectdata1/V_L_Constructief.ifc and .../ProjectData/V_L_Constructief.ifc', status='RESOLVED - provenance verified',
         evidence='Both local copies are byte-identical (SHA-256 b780050d...7836b7817d? see manifest). The OpeningDesign fork stores 0-byte blobs, but the canonical parent openBIMstandards/Archive-DataSetSchependomlaan stores a Git LFS pointer with oid sha256:b780050d03e072b89e76e541e5d795f26d1a144dbe1e4718264b6f291820be3b, size 941642 - identical to the local files. Header: simplebim 5.2 Evaluation edit of a Revit 2014 export, 2015-03-02.',
         unresolved='Repository licence field is NOASSERTION; dataset README (per Stage 3.7A audit) states CC BY 4.0.', action='Cite openBIMstandards/Archive-DataSetSchependomlaan as the source. No quarantine.'),
    dict(issue_id='P3', record='data/raw/Models and algorithm for construction scheduling/ (Tekla frames)', status='OPEN - citation unconfirmed',
         evidence='Only GA_mendeley.py name suggests a Mendeley deposit; no DOI in folder.', unresolved='Source DOI/licence.', action='Fixture use only; confirm DOI before citing.'),
    dict(issue_id='P4', record='SCHEPENDOMLAAN licence', status='OPEN - minor',
         evidence='GitHub licence NOASSERTION for both repos; dataset README states CC BY 4.0 (Stage 3.7A audit).', unresolved='Machine-readable licence absent.', action='Cite README licence statement with attribution.'),
    dict(issue_id='P5', record='Mendeley rac_advanced_sample_project.ifc', status='OPEN - third-party content',
         evidence='Mendeley CC BY 4.0 notes that "further permission may be required for any content within the dataset that is identified as belonging to a third party"; the model is an Autodesk Revit sample.', unresolved='Autodesk sample terms.', action='Robustness testing only; do not redistribute the IFC.'),
]
PROV[1]['evidence'] = PROV[1]['evidence'].replace('b780050d...7836b7817d? see manifest', 'b780050d03e072b89e76e541e5d795f26d1a144dbe1e4718264b6f291820be3b')
wr('source_provenance_issues.csv', PROV)

# ------------------------------------------------------------------ master dataset inventory
CAT_BE = {'D1': 'catalogue reference', 'D2': 'catalogue reference (derivative)', 'D3': 'LCA/EPD database', 'D4': 'real project-control dataset (civil)',
          'D5': 'demonstrator (real site)', 'D6': 'real project schedules (no BIM)', 'D7': 'real project schedules (no BIM, locked test protected)',
          'D8': 'catalogue reference (not acquired)', 'D9': 'catalogue + environmental reference (not acquired)', 'D10': 'EPD database (not acquired)',
          'D11': 'catalogue norms (unsuitable licence)', 'D12': 'unavailable'}
CAT_SA = {'SCH': 'real project (BIM + planned schedule)', 'SPEC': 'specification fixture', 'CERT': 'certification fixture', 'TEK': 'structural test model',
          'SYN': 'synthetic fixture', 'MEN': 'authored BIM models (2) + vendor sample (1), built status undocumented', 'RST': 'demonstrator (real site)',
          'B4D': 'benchmark model (quarantined)'}
master_inv = []
for r in BE_INV:
    if r['dataset_id'] == 'D5':
        continue  # RestageIFC reported once, from Section A
    master_inv.append(dict(master_id=f"BE-{r['dataset_id']}", dataset=r['dataset'], source_section='B-E', evidence_category=CAT_BE.get(r['dataset_id'], ''),
                           acquisition_status=r['status'], licence=r['licence'], provenance='verified' if r['status'].startswith(('Downloaded', 'Already')) else 'not acquired',
                           local_path=r['local_path'], content=r['content'], geography=r['geography'], source_url=r['url'], source_deliverable=f'{BE}/dataset_inventory.csv'))
for r in SA_INV:
    g = r['group']
    master_inv.append(dict(master_id=f'A-{g}', dataset=r['dataset'], source_section='A', evidence_category=CAT_SA.get(g, ''),
                           acquisition_status='Already available locally (verified)', licence={'MEN': 'CC BY 4.0', 'RST': 'CC BY 4.0', 'SCH': 'CC BY 4.0 (README); repo NOASSERTION',
                                                                                              'SPEC': 'see repository', 'CERT': 'see repository', 'SYN': 'internal', 'TEK': 'unconfirmed', 'B4D': 'unknown'}.get(g, ''),
                           provenance={'B4D': 'QUARANTINED (P1)', 'TEK': 'open (P3)', 'SYN': 'internal synthetic'}.get(g, 'verified'),
                           local_path=r['local_path'], content=f"{r['ifc_files']} IFC; {r['elements']} elements; independent projects: {r['independent_projects']}",
                           source_deliverable=f'{SA}/ifc_dataset_inventory.csv'))
wr('master_dataset_inventory.csv', master_inv)

# ------------------------------------------------------------------ master evidence coverage
UPD = {  # Section A updates to the B-E combined evidence matrix
    'Genuine IFC geometry': ('Available', 'SCH (real, built 2015) and RST (demonstrator) IFC geometry; Mendeley models (authored, build status undocumented); tessellation 862/862 sampled elements.'),
    'Element classifications': ('Available', 'IFC classes audited in 160 files; caveat: SCH strip foundations are modelled as IfcBeam ("fund_strook"/"fund_opstort"); only RST has IfcFooting among real models.'),
    'Physical quantities': ('Partial', 'Authored NetVolume in SCH design (beams 174/174, slabs 278/279, walls 883/934), RST (footings 11/13, beams 22/191, walls 22/92); geometry-derived in Mendeley; reinforcement absent; formwork/excavation need assumptions.'),
    'Element-to-task mapping': ('Partial', 'SCH Synchro: 3,505 elements assigned to 125 planned tasks (one project); RST: 12 phase tasks (hierarchical, duplicated phases) with element assignment; no element-level task mapping in other real models.'),
    'Construction dependencies': ('Partial', 'SCH Synchro 42 IfcRelSequence + MS Project 48 links (planner-authored, one project); Thiele/DSLIB/Cambridge networks unlinked to IFC; Mendeley relations are geometric only.'),
    'Planned activity durations': ('Partial', 'SCH Synchro 125 tasks with planned start/finish (working-day calendar); B-E sources unlinked to IFC.'),
    'Actual activity durations': ('Missing', 'No source has activity actual start and finish linked to IFC. RST: ActualFinish only, entered in an ACTUAL work schedule created 2026-07-01 during dataset compilation (all at 18:00) - not independently verified activity records.'),
    'Genuine design revisions': ('Missing', 'SCH weekly snapshots carry the identical 125 tasks and planned dates as the full model; their elements are subsets (854 -> 3,505) - progressive model states of one plan, not design or schedule revisions. SCH subcontractor versions (e.g. GEELEN Breedplaat V1-V3) exist but are not aligned revision pairs.'),
    'Corresponding schedule revisions': ('Missing', 'Single baseline per project (SCH 18-02-2015); no revision pairs.'),
    'Independent validation projects': ('Partial', 'Real-project validation: SCH (development) and RST (independent demonstrator). Mendeley models are robustness cases; 4D benchmark quarantined.'),
}
master_ev = []
for r in BE_EV:
    k = r['required_evidence']
    st, ev = UPD.get(k, (r['status'], r['supporting_evidence']))
    master_ev.append(dict(required_evidence=k, status=st, Available='X' if st == 'Available' else '', Partial='X' if st == 'Partial' else '', Missing='X' if st == 'Missing' else '',
                          sections_B_E_status=r['status'], changed_by_section_A='yes' if k in UPD and UPD[k][0] != r['status'] else ('evidence updated' if k in UPD else 'no'),
                          evidence=ev if k in UPD else r['supporting_evidence'], b_e_evidence=r['supporting_evidence'], local_paths=r['local_paths']))
master_ev.append(dict(required_evidence='Reinforcement quantities', status='Missing', Missing='X', sections_B_E_status='(not assessed)', changed_by_section_A='new row',
                      evidence='No IfcReinforcingBar/Mesh or reinforcement weights in any real model; only fixtures (35 bars) and one SCH subcontractor model (6 bars).'))
master_ev.append(dict(required_evidence='Material-specific concrete volume', status='Partial', Partial='X', sections_B_E_status='(not assessed)', changed_by_section_A='new row',
                      evidence='Element volume available/derivable; concrete share requires material-layer split (e.g. SCH prefab floor layer set: concrete 0.20 m of 0.333 m = 0.6006). Aerated-concrete masonry (cellenbeton, 蒸压加气混凝土砌块) must be excluded from cast concrete.'))
wr('master_evidence_coverage_matrix.csv', master_ev)

# ------------------------------------------------------------------ readiness matrix
DEC = {r['stage']: r for r in BE_DEC}
READY = [
    ('5.0 Hybrid architecture design', 'GO', DEC['5.0 Hybrid architecture design']['evidence'] + ' Section A adds verified IFC inputs; Agent 2 architecture package exists (research/architecture/stage5_0/).', 'B-E + A', 'unchanged'),
    ('5.1 BIM quantity extraction', 'CONDITIONAL GO', 'Section A: authored volumes/areas in SCH design and RST; geometry agrees with authored volume on 251/251 elements; units declared in all key models (0 explicit quantity unit overrides); mass in GRAM in SCH. Missing: reinforcement (D), formwork rules (C), excavation/backfill site data (C/D), independent manual quantity checks (plan issued, not executed).', 'A', 'confirmed (Section A accepted)'),
    ('5.2 BIM-to-task generation', 'CONDITIONAL GO', DEC['5.2 BIM-to-task generation']['evidence'] + ' Section A: one real element-to-task reference (SCH Synchro, 3,505 elements / 125 tasks) for checking generated packages; not a training set.', 'B-E + A', 'evidence added; decision unchanged'),
    ('5.3 Engineering duration estimation', 'CONDITIONAL GO', DEC['5.3 Engineering duration estimation']['evidence'], 'B-E', 'unchanged'),
    ('5.4 Resource-constrained IFC4D scheduling', 'CONDITIONAL GO', DEC['5.4 Resource-constrained IFC4D scheduling']['evidence'] + ' Section A: SCH Synchro IFC2X3 export gives an IFC4D read-back reference (tasks, IfcRelSequence, assignments); no resources in any IFC.', 'B-E + A', 'evidence added; decision unchanged'),
    ('5.6 Supervised machine learning', 'NO-GO', DEC['5.6 Supervised machine learning']['evidence'] + ' Section A: no IFC-linked actual activity durations (RST finish-only, retrospectively entered; SCH none).', 'B-E + A', 'maintained NO-GO'),
    ('5.7 Scenario optimization', 'CONDITIONAL GO', DEC['5.7 Scenario optimization']['evidence'], 'B-E', 'unchanged'),
]
wr('stage5_readiness_matrix.csv', [dict(stage=a, decision=b, evidence=c, evidence_sections=d, change=e) for a, b, c, d, e in READY])

# ------------------------------------------------------------------ Stage 5.1 validation manifest
ROLE = {
    'SCH-design': ('development', 'yes (one real project)', 'DataSetSchependomlaan (openBIMstandards/Archive-DataSetSchependomlaan)', 'CC BY 4.0 (README)', 'verified'),
    'SCH-synchro': ('interoperability test - same project as SCH-design (NOT independent)', 'no (same project)', 'DataSetSchependomlaan', 'CC BY 4.0 (README)', 'verified'),
    'SCH-weekly': ('interoperability/fixture - weekly model state of the same plan (NOT a revision)', 'no', 'DataSetSchependomlaan', 'CC BY 4.0 (README)', 'verified'),
    'SCH-sub': ('development support - discipline model of the same project', 'no (same project)', 'DataSetSchependomlaan', 'CC BY 4.0 (README)', 'verified'),
    'RST': ('independent demonstrator validation', 'yes (demonstrator)', 'Zenodo 10.5281/zenodo.21470658', 'CC BY 4.0', 'verified'),
    'MEN-RES': ('geometry extraction and robustness (not a verified construction project)', 'no', 'Mendeley 10.17632/fm9myphk9g.1', 'CC BY 4.0', 'verified'),
    'MEN-MTG': ('geometry extraction and robustness (not a verified construction project)', 'no', 'Mendeley 10.17632/fm9myphk9g.1', 'CC BY 4.0', 'verified'),
    'MEN-RAC': ('geometry robustness - vendor sample (not a project)', 'no', 'Mendeley 10.17632/fm9myphk9g.1 (Autodesk sample content)', 'CC BY 4.0 + third-party terms (P5)', 'verified; third-party'),
    'B4D': ('QUARANTINED - internal software testing only', 'no', 'probable: Johansen et al. 2023 (DOI 10.1111/mice.12988)', 'unknown', 'QUARANTINED (P1)'),
    'SYN': ('controlled software testing only - synthetic', 'no (excluded from real-project claims)', 'PMI synthetic IFC writer', 'internal', 'internal'),
    'TEK': ('fixture - structural test frame', 'no', 'unconfirmed (P3)', 'unconfirmed', 'open (P3)'),
    'SPEC': ('fixture - parser/schema test', 'no', 'buildingSMART IFC4.x-specification-models', 'see repository', 'verified'),
    'CERT': ('fixture - parser/schema test', 'no', 'buildingSMART Certification-datasets', 'see repository', 'verified'),
}
QUIRK = {
    'SCH-design': 'ArchiCAD (Graphisoft) IFC2X3; mm length, GRAM mass (x0.001 to kg); strip foundations modelled as IfcBeam; layered slabs/walls; 1 duplicate GlobalId shared by two IfcRelConnectsPathElements (not elements); generic non-unique element names; GUIDs not preserved in Synchro export.',
    'SCH-synchro': 'Synchro IFC2X3 re-export: GUIDs regenerated; storeys flattened to one; materials dropped; quantities flattened into SynchroResourceProperty keys "[QtoSet[IfcElementQuantity/..]]Name"; link to design element only via name suffix "_(#STEP id)" (3,228/3,505 resolve; 73 change class; 277 no suffix); some meshes open/non-manifold.',
    'SCH-weekly': 'As SCH-synchro; identical 125 tasks and planned dates; element subsets.',
    'SCH-sub': 'Subcontractor exports (various tools); simplebim-edited copies; same building.',
    'RST': 'Bonsai 0.8.5 IFC4; m length; concrete named by strength class only (C25/30, C35/45); quantity coverage partial (footings 11/13, beams 22/191, walls 22/92, slabs 0/12); tasks hierarchical with duplicated phases.',
    'MEN-RES': 'Revit 2024 (CHS) IFC2X3 without BaseQuantities; Chinese material names; aerated-concrete blocks (蒸压加气混凝土砌块) must not be counted as cast concrete; CSVs join by name only (unique match 98.8%).',
    'MEN-MTG': 'Revit 2024 (CHS) IFC2X3 without BaseQuantities; m length; 1,364 IfcBuildingElementProxy; CSV unique name match 91.8-98.7%.',
    'MEN-RAC': 'Autodesk sample re-exported by Revit 2024 (CHS) IFC2X3 without quantities; CSV unique name match 96.7-97.3%.',
    'B4D': 'Revit exporter 22.0.2 IFC4 via EDM; complete Qto_*BaseQuantities; multi-layer walls (brick + CMU) - element volume is not concrete volume.',
}


def mkey(path):
    if path.endswith('Design model IFC/IFC Schependomlaan.ifc'): return 'SCH-design'
    if path.endswith('As Planned models/IFC Schependomlaan incl planningsdata.ifc'): return 'SCH-synchro'
    if 'As Planned models/Week' in path: return 'SCH-weekly'
    if 'SCHEPENDOMLAAN' in path: return 'SCH-sub'
    if 'Restage' in path: return 'RST'
    if 'BIM_residential' in path: return 'MEN-RES'
    if 'BIM_meeting' in path: return 'MEN-MTG'
    if 'rac_advanced' in path: return 'MEN-RAC'
    if '4DBenchmark' in path: return 'B4D'
    if 'PMI_SYN' in path or 'IND-001' in path: return 'SYN'
    if 'Models and algorithm' in path: return 'TEK'
    if 'specification-models' in path: return 'SPEC'
    return 'CERT'


gsum = defaultdict(lambda: [0, 0, 0, 0])
for g in GEO:
    s = gsum[g['path']]
    s[0] += int(g['sampled']); s[1] += int(g['tessellated_ok']); s[2] += int(g['compared_with_authored_volume']); s[3] += int(g['within_2pct'])
QU = CHK['quantity_units']
QKEY = {'SCH-design': 'SCH-design', 'SCH-synchro': 'SCH-synchro', 'RST': 'RST', 'MEN-RES': 'MEN-RES', 'MEN-RAC': 'MEN-RAC', 'MEN-MTG': 'MEN-MTG', 'B4D': 'B4D'}
man = []
for path, d in sorted(AUD.items()):
    k = mkey(path)
    role, real, src, lic, prov = ROLE[k]
    ec = d['element_classes']
    u = {x['type']: x for x in d['units']}

    def un(t):
        x = u.get(t)
        return 'not declared' if not x else (f"{x.get('prefix') or ''}{x.get('name')}" if x['kind'] == 'SI' else f"{x.get('name')}")
    mass = un('MASSUNIT')
    to_kg = {'GRAM': 0.001, 'KILOGRAM': 1.0}.get(mass, '')
    classes = [c for c in ('IfcFooting', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall', 'IfcMember', 'IfcReinforcingBar') if ec.get(c, {}).get('n')]
    auth = '; '.join(f"{c[3:]} NetVol {max(ec[c].get('qto_net_volume', 0), ec[c].get('flat_net_volume', 0))}/{ec[c]['n']} NetArea {max(ec[c].get('qto_net_area', 0), ec[c].get('flat_net_area', 0))}/{ec[c]['n']}"
                     for c in classes if c != 'IfcReinforcingBar')
    gs = gsum.get(path)
    geo = f'sampled {gs[0]}, tessellated {gs[1]}, compared {gs[2]}, within 2% {gs[3]}' if gs else 'not sampled'
    q = QU.get(QKEY.get(k, ''), {}) if k in QKEY and path.endswith(os.path.basename(path)) and (k not in ('SCH-weekly', 'SCH-sub')) else {}
    layer_note = {'SCH-design': 'Layer sets on slabs/walls (e.g. prefab floor: 0.20 m concrete of 0.333 m)', 'B4D': 'Multi-layer walls and slabs (brick, CMU, insulation)',
                  'MEN-RES': 'Single-layer layer sets on slabs/walls; aerated-concrete blocks present', 'SCH-synchro': 'Materials not exported',
                  'RST': 'Single IfcMaterial per element; many walls/slabs timber or without material'}.get(k, 'not assessed')
    man.append(dict(
        ifc_path=path, model_key=k, validation_role=role, eligible_for_real_project_claims=real, quarantined='yes' if k == 'B4D' else 'no',
        source=src, licence_status=lic, provenance_status=prov, sha256=d['sha256'], bytes=d['bytes'], ifc_schema=d['schema'],
        exporter=(d.get('header_originating_system') or '')[:80], supported_element_classes='; '.join(f"{c}={ec[c]['n']}" for c in classes),
        length_unit=un('LENGTHUNIT'), length_scale_to_m=d['length_unit_scale_to_m'], area_unit=un('AREAUNIT'), volume_unit=un('VOLUMEUNIT'),
        mass_unit=mass, mass_factor_to_kg=to_kg,
        explicit_quantity_unit_overrides=(f"{q['with_explicit_unit']} of {q['physical_quantities']} IfcPhysicalSimpleQuantity" if q else 'not checked'),
        authored_quantity_coverage=auth or 'none', geometry_derived_coverage=geo, material_layer_limitations=layer_note,
        duplicate_globalids=d['globalid_duplicates'], invalid_globalids=d['globalid_invalid_format'],
        storeys=len(d['storeys']), exporter_restrictions=QUIRK.get(k, '')))
wr('stage5_1_validation_manifest.csv', man)

# ------------------------------------------------------------------ quantity validation plan
MANUAL = {
    'IfcFooting': 'Compute plan dimensions x depth from the profile/extrusion (or drawings), subtract pockets/openings; compare with authored NetVolume and geometry volume. Record excavation-relevant underside level separately.',
    'IfcColumn': 'Cross-section area from profile x clear height between structural levels; decide and record whether beam/slab intersections are deducted (measurement rule).',
    'IfcBeam': 'Section b x h x length; record whether slab depth is deducted at T-beams and whether length is clear span or overall; for SCH "fund_*" beams confirm they are strip foundations.',
    'IfcSlab': 'Outline area minus openings x thickness; for layer sets compute concrete-layer thickness x area separately from total element volume; confirm precast vs cast-in-place.',
    'IfcWall': 'Length x height x thickness minus openings (IfcRelVoidsElement); for layered walls compute the concrete layer only; confirm cast concrete vs masonry block.',
}
plan = []
for i, r in enumerate(SAMPLE, 1):
    limits = []
    if r.get('edge_manifold_closed') == 'False':
        limits.append(f"mesh not closed ({r.get('non_manifold_or_open_edges')} open/non-manifold edges): geometry volume unreliable")
    if r['authored_volume_source'] == 'none':
        limits.append('no authored volume')
    if r['authored_volume_source'] == 'flattened export key':
        limits.append('authored value copied by Synchro export, not authored in this file')
    if r.get('concrete_layer_thickness_fraction') not in ('', None):
        limits.append('element volume includes non-concrete layers' if float(r['concrete_layer_thickness_fraction']) < 1 else 'single concrete layer')
    if r['model_key'] == 'SCH-design' and r['ifc_class'] == 'IfcBeam' and (r['name'] or '').startswith('fund'):
        limits.append('foundation element modelled as IfcBeam')
    if r['model_key'].startswith('MEN'):
        limits.append('model of undocumented build status - robustness only')
    if r.get('ratio_geometry_to_authored'):
        limits.append('agreement with authored value is a consistency check (same exporter geometry), not independent validation')
    plan.append(dict(
        check_id=f'QV{i:02d}', model_key=r['model_key'], validation_role=r['role'], ifc_path=r['ifc_path'], global_id=r['global_id'], element_name=r['name'],
        ifc_class=r['ifc_class'], predefined_type=r['predefined_type'], storey=r['storey'], material_classification=r['material_layers'],
        material_association=r['material_association'], concrete_layer_thickness_fraction=r.get('concrete_layer_thickness_fraction', ''),
        geometry_representation=r['body_geometry'], world_bbox_extent_m=r.get('world_bbox_extent_m', ''), edge_manifold_closed=r.get('edge_manifold_closed', ''),
        authored_quantity_source=r['authored_volume_source'], authored_net_volume_m3=r['authored_net_volume_m3'], authored_gross_volume_m3=r['authored_gross_volume_m3'],
        geometry_volume_m3_DERIVED=r.get('geometry_volume_m3', ''), geometry_total_surface_m2_DERIVED=r.get('geometry_total_surface_m2', ''),
        layer_based_concrete_volume_m3_DERIVED=r.get('layer_based_concrete_volume_m3_DERIVED', ''), ratio_geometry_to_authored=r.get('ratio_geometry_to_authored', ''),
        design_model_link=r.get('design_model_link', ''),
        measurement_basis='Net volume of the element body as modelled (m3); concrete share by material layer where a layer set exists. Tolerance to be set with the engineering owner.',
        agent2_quantity_record_mapping=('method=ifc_quantity, basis="IfcElementQuantity NetVolume"' if r['authored_volume_source'] == 'IfcElementQuantity'
                                        else 'method=ifc_quantity, basis="flattened SynchroResourceProperty key" (no enum value exists for flattened keys)' if r['authored_volume_source'] == 'flattened export key'
                                        else 'method=geometry, basis="IfcOpenShell tessellated Body volume"'),
        required_independent_manual_calculation=MANUAL[r['ifc_class']],
        independent_manual_value_m3='', reviewer='', review_date='', review_status='PENDING - not performed (no ground truth generated)',
        known_limitations='; '.join(limits)))
wr('quantity_validation_plan.csv', plan)

# ------------------------------------------------------------------ preservation
snap = {}
if SNAP:
    for line in open(SNAP, encoding='utf-8'):
        h, p = line.rstrip('\n').split(' ', 1)
        snap[p.lstrip('*')] = h
snap_changed = [p for p, h in snap.items() if not os.path.exists(p) or sha256(p) != h]


def eol_only(p, h):
    """True if the file differs from the snapshot only by CRLF/LF line endings."""
    d = open(p, 'rb').read()
    return hashlib.sha256(d.replace(b'\r\n', b'\n')).hexdigest() == h or hashlib.sha256(d.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest() == h


snap_detail = [dict(path=p, owner='Agent 2 (research/architecture)' if p.startswith('research/architecture') else 'Stage 4.0B deliverable',
                    mtime_utc=dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc).isoformat() if os.path.exists(p) else 'missing',
                    change='line endings only (LF<->CRLF); content identical' if os.path.exists(p) and eol_only(p, snap[p]) else 'CONTENT CHANGED')
               for p in snap_changed]
s4b_content_changed = [d['path'] for d in snap_detail if d['owner'].startswith('Stage 4.0B') and d['change'] == 'CONTENT CHANGED']
arch_now = sorted(p.replace('\\', '/') for p in glob.glob('research/architecture/**/*', recursive=True) if os.path.isfile(p))
arch_new = [p for p in arch_now if p not in snap]
base = {}
for line in open(f'{BE}/preservation/baseline_sha256_before_stage4_0b.txt', encoding='utf-8'):
    h, p = line.rstrip('\n').split(' ', 1)
    base[p.lstrip('*')] = h
base_changed = [p for p, h in base.items() if not os.path.exists(p) or sha256(p) != h]
b4 = {}
for line in open('research/evaluation/stage4_0a/preservation/baseline_sha256_before_stage4_0a.txt', encoding='utf-8'):
    h, p = line.rstrip('\n').split(' ', 1)
    b4[p.lstrip('*')] = h
b4_changed = [p for p, h in b4.items() if not os.path.exists(p) or sha256(p) != h]
gs = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.splitlines()
pres = dict(generated=NOW, checks=[
    dict(check='Stage 4.0B pre-task baseline (models, processed, evaluation, gnn, raw excl. candidates, data/*.csv|json)', total=len(base), changed_or_missing=base_changed),
    dict(check='Stage 4.0A baseline', total=len(b4), changed_or_missing=b4_changed),
    dict(check='Section A, Sections B-E and Agent 2 (research/architecture) files vs consolidation-start snapshot (2026-11-19 13:01:51 UTC)', total=len(snap),
         changed=len(snap_changed), detail=snap_detail, stage4_0b_content_changes=s4b_content_changed, agent2_files_added_since_snapshot=arch_new,
         note=('All changes carry mtime 2026-11-19T13:04:19Z, the moment Agent 2 rewrote research/architecture/stage5_0. This consolidation only READ those paths '
               'and never wrote outside research/data_acquisition/stage4_0b/consolidated/ and data/processed/candidates/stage4_0b/consolidated/. '
               'Stage 4.0B files changed only in line endings (external normalisation); they were NOT reverted, per instruction to report rather than rewrite.')),
    dict(check='git: no tracked file modified', tracked_modifications=[l for l in gs if not l.startswith('??')], untracked=[l[3:] for l in gs if l.startswith('??')]),
    dict(check='No duplicate downloads', result='Only a 131-byte Git LFS pointer fetched into the session scratchpad (not data/raw) to verify V_L_Constructief provenance'),
    dict(check='No training, inference, production modules, environment changes, commit or push', result='scripts read, count, tessellate and hash only'),
    dict(check='Cambridge locked-test records', result='not accessed'),
])
pres['all_protected_unchanged'] = not (base_changed or b4_changed or s4b_content_changed or pres['checks'][3]['tracked_modifications'])
pres['discrepancies'] = [
    f'{sum(1 for d in snap_detail if d["owner"].startswith("Stage 4.0B"))} Stage 4.0B script/baseline files were converted LF->CRLF at 13:04:19Z by an external process (coinciding with Agent 2); content unchanged; not reverted.',
    f'{sum(1 for d in snap_detail if d["owner"].startswith("Agent 2"))} Agent 2 files were rewritten by Agent 2 at 13:04:19Z ({sum(1 for d in snap_detail if d["owner"].startswith("Agent 2") and d["change"] == "CONTENT CHANGED")} with content changes); read only by this task.',
]
json.dump(pres, open(f'{OUT}/preservation_verification.json', 'w', encoding='utf-8'), indent=2)
print('preservation ok:', pres['all_protected_unchanged'], 'snapshot files', len(snap), 'changed', len(snap_changed))

# ------------------------------------------------------------------ remaining blockers
link = CHK['mendeley_linkage']
AG2 = [
    ('Multiple independent authorised models', 'Partial', 'Two real projects (SCH development, RST independent demonstrator), both CC BY 4.0; Mendeley adds robustness cases only; 4D benchmark quarantined.'),
    ('Audited IFC versions', 'Met', '160 files: schema, exporter, application recorded (section_A/ifc_schema_summary.csv).'),
    ('Unit assignment and overrides', 'Met', 'Units declared in all key models; 0 explicit IfcPhysicalSimpleQuantity unit overrides in the 7 key models; SCH mass in GRAM.'),
    ('Class / zone / material coverage', 'Partial', 'Class and material coverage audited; IfcZone/work-zone assignment NOT audited; storeys flattened in Synchro export.'),
    ('Manually checked gross/net volume, area and mass', 'Not met', f'quantity_validation_plan.csv lists {len(plan)} elements; no manual calculation performed yet.'),
    ('Known missing data', 'Met', 'Reinforcement, formwork rules, excavation/backfill, actual durations documented.'),
    ('Geometry/quantity agreement', 'Met (consistency only)', '251/251 within 2%; open/non-manifold meshes found in Synchro export.'),
    ('Documented exporter quirks', 'Met', 'exporter_restrictions column of stage5_1_validation_manifest.csv.'),
    ('Unit-test cases: explicit quantity-unit override, imperial units (roadmap step 4)', 'Fixture needed', 'No explicit IfcPhysicalSimpleQuantity unit override and no imperial project units in the 7 key real models; these cases must come from synthetic or specification fixtures.'),
    ('Aligned revision pair and GlobalId persistence', 'Not met', 'No genuine revision pair. SCH design->Synchro GUIDs not persistent (linkable only via name suffix "_(#STEP id)"); weekly snapshots are not revisions.'),
]
open(f'{OUT}/remaining_blockers.md', 'w', encoding='utf-8').write(f"""# Stage 4.0B - remaining blockers

Generated {NOW}. Stage 5.6 remains **NO-GO**.

## Blocking Stage 5.1 release on real models
1. **Independent manual quantity checks not performed.** `quantity_validation_plan.csv` ({len(plan)} concrete elements from SCH design, RestageIFC, MEN-RES and the SCH Synchro export) needs an engineer's independent calculations and agreed tolerances. No ground truth was generated.
2. **Reinforcement mass unavailable** in every real model (category D). Needs a structural/rebar model or user-entered design values labelled as assumptions.
3. **Formwork contact area** requires approved face rules per element type and construction method (category C).
4. **Excavation and backfill** require site/ground data (category C/D).
5. **Material-specific concrete volume** requires layer splitting and exclusion of aerated-concrete masonry; element volume must not be reported as concrete volume.
6. **Only two real projects** (SCH, RST); RST quantity coverage is partial (slabs 0/12, beams 22/191).

## Blocking later stages
- **Revision release (5.5):** no aligned revision pair; GlobalIds not persistent across SCH exports.
- **Stage 5.6 ML:** no IFC-linked actual activity durations; RST ActualFinish values were entered in an ACTUAL work schedule created 2026-07-01 during dataset compilation (all 18:00), phases duplicated (Bauabschnitt_01 = ConstructionPhase_01; Bauabschnitt_02 = ConstructionPhase_03) - not verified activity records.
- **Catalogue/licensing (from B-E):** BEDEC subscription, CYPE licence, EC3 API terms; crew sizes, calendars, curing/striking times must come from users.

## Provenance
See `source_provenance_issues.csv`: 4DBenchmark + Schedules.xlsx **quarantined** (P1); V_L_Constructief **resolved** (P2); Tekla frames, SCH licence, Autodesk sample terms open (P3-P5).

## Coordination notes for Agent 2 (research/architecture/stage5_0 - read only, not modified)
| Agent 2 release requirement (implementation_roadmap.md step 3) | Status | Evidence |
|---|---|---|
""" + '\n'.join(f'| {a} | {b} | {c} |' for a, b, c in AG2) + """

- `QuantityRecord.method` has no value for quantities flattened into property keys by an exporter (SCH Synchro); suggested mapping: `ifc_quantity` with `basis` naming the flattened key, or a new enum value - Agent 2 to decide.
- `risk_and_assumption_register.csv` R01 "Section A pending" can be updated by Agent 2 to reference `research/data_acquisition/stage4_0b/consolidated/`.
- Release thresholds: manual-check tolerances are still to be agreed with the engineering owner (as Agent 2's validation_strategy.md requires).
""")

# ------------------------------------------------------------------ report md + html
def md_table(rows, cols):
    s = '| ' + ' | '.join(cols) + ' |\n|' + '---|' * len(cols) + '\n'
    for r in rows:
        s += '| ' + ' | '.join(str(r.get(c, '')).replace('|', '/').replace('\n', ' ') for c in cols) + ' |\n'
    return s


snap_rows = CHK['sch_snapshots']
rst = CHK['restage_tasks']
closed = sum(1 for r in plan if r['edge_manifold_closed'] == 'True')
key_man = [r for r in man if r['model_key'] in ('SCH-design', 'SCH-synchro', 'RST', 'MEN-RES', 'MEN-MTG', 'MEN-RAC', 'B4D')] + [r for r in man if r['model_key'] == 'SYN']
AMB = [
    ('Mendeley name linkage', 'Earlier statement "99-100%" was overstated. Exact IfcElement name matches 92.9-100%; unique matches 91.8-98.8%; ambiguous names 19-81 per CSV (standing for 57-580 IFC elements); remaining names match IfcSpace/other products. Only unique matches may serve as element identities.'),
    ('Element vs concrete volume', 'Element volume includes every material layer; concrete volume = concrete-layer share (e.g. SCH prefab floor 0.6006) and excludes aerated-concrete masonry. Values in the plan are labelled DERIVED.'),
    ('Tessellation vs closed geometry', f'Tessellation succeeded for all sampled elements, but an edge-manifold test found open/non-manifold meshes (in this plan: {len(plan) - closed} of {len(plan)}; Synchro export elements with 3-28 bad edges in the earlier sample). Tessellation does not establish closed geometry or correct construction quantities.'),
    ('Authored-volume agreement vs independent validation', '251/251 geometry-vs-authored agreement within 2% shows internal consistency of exporter output; both values may derive from the same geometry. Independent validation requires the manual calculations in quantity_validation_plan.csv.'),
    ('SCH weekly snapshots', 'All six weekly files carry the identical 125 tasks with identical planned dates as the full Synchro model (task GUIDs regenerated per export) and element subsets of it (854-3,505). They are progressive model states of one baseline, not design or schedule revisions.'),
    ('Restage finish dates', 'IfcTaskTime.ActualFinish on 11/12 tasks in an IfcWorkSchedule of PredefinedType ACTUAL created 2026-07-01 by "unknown user" during dataset compilation; all at 18:00; no ActualStart; hierarchical phases with duplicates. Dataset text calls them "actual completion times"; they are retrospectively entered phase completion dates, not independently verified activity records.'),
    ('SCH design <-> Synchro identity', 'GUIDs not preserved; 3,228/3,505 Synchro elements resolve to a same-named design element through the name suffix "_(#STEP id)"; 73 change IFC class; 277 have no suffix. Export-specific key, not a persistent identifier.'),
]
rep = f"""# Stage 4.0B - consolidated evidence package and Stage 5.1 validation handover

Generated {NOW}. Consolidates `section_A/` (accepted) and `sections_B_E/` without modifying them. Stage 5.6 remains **NO-GO**.

## 1. Evidence categories
{md_table(master_inv, ['master_id', 'dataset', 'evidence_category', 'acquisition_status', 'provenance', 'licence'])}
## 2. Stage 5 readiness
{md_table([dict(stage=a, decision=b, change=e) for a, b, c, d, e in READY], ['stage', 'decision', 'change'])}
Full evidence: `stage5_readiness_matrix.csv`.

## 3. Master evidence coverage
{md_table(master_ev, ['required_evidence', 'status', 'sections_B_E_status', 'changed_by_section_A', 'evidence'])}
## 4. Stage 5.1 validation handover
`stage5_1_validation_manifest.csv` lists all {len(man)} local IFC files with role, provenance, SHA-256, schema, classes, units, overrides, authored and geometry coverage, layer limitations, GlobalId issues and exporter restrictions. Key models:
{md_table(key_man, ['model_key', 'validation_role', 'eligible_for_real_project_claims', 'ifc_schema', 'length_unit', 'mass_unit', 'explicit_quantity_unit_overrides', 'duplicate_globalids', 'provenance_status'])}
## 5. Resolved ambiguities
{md_table([dict(topic=a, resolution=b) for a, b in AMB], ['topic', 'resolution'])}
### Mendeley linkage detail
{md_table(link, ['project', 'csv', 'distinct_csv_names', 'exact_ifcelement_name_match', 'exact_pct', 'unique_match', 'unique_pct', 'ambiguous_match', 'ambiguous_ifc_elements_behind', 'matches_non_element_product'])}
### SCH weekly snapshots
{md_table(snap_rows, ['file', 'tasks', 'identical_task_names_and_planned_dates_to_full_model', 'task_guids_shared_with_full_model', 'elements', 'element_names_subset_of_full', 'tasks_with_actual_dates'])}
### Restage tasks
{md_table([dict(name=t['name'], identification=t['identification'], task_time=json.dumps(t['task_time']), assigned_products=t['assigned_products']) for t in rst], ['name', 'identification', 'task_time', 'assigned_products'])}
Work schedule: {json.dumps(CHK['restage_work_schedule'][0])}

## 6. Source provenance
{md_table(PROV, ['issue_id', 'record', 'status', 'action'])}
## 7. Independent quantity checks (proposed, not performed)
`quantity_validation_plan.csv`: {len(plan)} concrete elements ({', '.join(f'{k} {v}' for k, v in Counter(r['model_key'] for r in plan).items())}). Each row gives identifiers, material classification, geometry representation, authored and DERIVED geometry quantities, measurement basis, the required manual calculation and limitations. `independent_manual_value_m3` is blank by design.

## 8. Remaining blockers
See `remaining_blockers.md` (includes Agent 2 coordination table).

## Deliverables
stage4_0b_consolidated_report.md / .html, master_dataset_inventory.csv, master_evidence_coverage_matrix.csv, stage5_1_validation_manifest.csv, quantity_validation_plan.csv, source_provenance_issues.csv, remaining_blockers.md, stage5_readiness_matrix.csv, preservation_verification.json; scripts/. Supporting data: data/processed/candidates/stage4_0b/consolidated/.
"""
open(f'{OUT}/stage4_0b_consolidated_report.md', 'w', encoding='utf-8').write(rep)

E = html.escape
BADGE = {'GO': 'ok', 'CONDITIONAL GO': 'warn', 'NO-GO': 'bad', 'Available': 'ok', 'Partial': 'warn', 'Missing': 'bad', 'Met': 'ok', 'Not met': 'bad'}


def cell(v, c):
    v = '' if v is None else str(v)
    if c in ('decision', 'status') and v in BADGE:
        return f'<span class="b {BADGE[v]}">{E(v)}</span>'
    if c in ('status',) and v.startswith(('QUARANTINED', 'RESOLVED', 'OPEN')):
        return f'<span class="b {"bad" if v.startswith("QUAR") else "ok" if v.startswith("RES") else "warn"}">{E(v)}</span>'
    if c in ('ifc_path', 'local_path', 'record'):
        return f'<code>{E(v)}</code>'
    return E(v)


def h_table(rows, cols):
    s = '<div class="tw"><table><thead><tr>' + ''.join(f'<th>{E(c)}</th>' for c in cols) + '</tr></thead><tbody>'
    for r in rows:
        s += '<tr>' + ''.join(f'<td>{cell(r.get(c), c)}</td>' for c in cols) + '</tr>'
    return s + '</tbody></table></div>'


css = open(f'{BE}/stage4_0b_report.html', encoding='utf-8').read().split('<style>')[1].split('</style>')[0]
cnt = Counter(r['status'] for r in master_ev)
secs = [('categories', 'Evidence categories'), ('readiness', 'Stage 5 readiness'), ('coverage', 'Evidence coverage'), ('handover', 'Stage 5.1 handover'),
        ('ambiguities', 'Resolved ambiguities'), ('provenance', 'Provenance'), ('qcheck', 'Quantity checks'), ('agent2', 'Agent 2 coordination'), ('preservation', 'Preservation')]
body = f"""<h1>Stage 4.0B - consolidated evidence package</h1><p class="sub">Generated {E(NOW)}. Section A (accepted) + Sections B-E. Stage 5.6 remains NO-GO.</p>
<div class="tiles"><div class="tile"><div class="n">{len(master_inv)}</div><div class="l">datasets in master inventory</div></div>
<div class="tile"><div class="n">{cnt['Available']} / {cnt['Partial']} / {cnt['Missing']}</div><div class="l">evidence available / partial / missing</div></div>
<div class="tile"><div class="n">{len(man)}</div><div class="l">IFC files in validation manifest</div></div>
<div class="tile"><div class="n">2</div><div class="l">real projects for validation (SCH dev, RST independent)</div></div>
<div class="tile"><div class="n">{len(plan)}</div><div class="l">elements proposed for manual checks (pending)</div></div></div>
<section id="categories"><h2>Evidence categories</h2>{h_table(master_inv, ['master_id', 'dataset', 'evidence_category', 'acquisition_status', 'provenance', 'licence', 'local_path'])}</section>
<section id="readiness"><h2>Stage 5 readiness</h2>{h_table([dict(stage=a, decision=b, evidence=c, change=e) for a, b, c, d, e in READY], ['stage', 'decision', 'change', 'evidence'])}</section>
<section id="coverage"><h2>Master evidence coverage</h2>{h_table(master_ev, ['required_evidence', 'status', 'sections_B_E_status', 'changed_by_section_A', 'evidence'])}</section>
<section id="handover"><h2>Stage 5.1 validation handover</h2><p>Full manifest: <code>stage5_1_validation_manifest.csv</code> ({len(man)} files).</p>{h_table(key_man, ['model_key', 'ifc_path', 'validation_role', 'eligible_for_real_project_claims', 'ifc_schema', 'exporter', 'length_unit', 'mass_unit', 'mass_factor_to_kg', 'explicit_quantity_unit_overrides', 'authored_quantity_coverage', 'geometry_derived_coverage', 'material_layer_limitations', 'duplicate_globalids', 'exporter_restrictions'])}</section>
<section id="ambiguities"><h2>Resolved ambiguities</h2>{h_table([dict(topic=a, resolution=b) for a, b in AMB], ['topic', 'resolution'])}
<h3>Mendeley linkage</h3>{h_table(link, ['project', 'csv', 'distinct_csv_names', 'exact_ifcelement_name_match', 'exact_pct', 'unique_match', 'unique_pct', 'ambiguous_match', 'ambiguous_ifc_elements_behind', 'matches_non_element_product'])}
<h3>SCH weekly snapshots</h3>{h_table(snap_rows, ['file', 'tasks', 'identical_task_names_and_planned_dates_to_full_model', 'task_guids_shared_with_full_model', 'elements', 'element_names_subset_of_full', 'tasks_with_actual_dates'])}
<h3>Restage tasks</h3>{h_table([dict(name=t['name'], identification=t['identification'], task_time=json.dumps(t['task_time']), assigned_products=t['assigned_products']) for t in rst], ['name', 'identification', 'task_time', 'assigned_products'])}</section>
<section id="provenance"><h2>Source provenance</h2>{h_table(PROV, ['issue_id', 'record', 'status', 'evidence', 'unresolved', 'action'])}</section>
<section id="qcheck"><h2>Independent quantity checks (proposed)</h2><div class="callout">No ground truth was generated. Geometry and layer-based values are DERIVED; the independent manual value column is blank until an engineer completes it.</div>
{h_table(plan, ['check_id', 'model_key', 'global_id', 'element_name', 'ifc_class', 'material_classification', 'authored_quantity_source', 'authored_net_volume_m3', 'geometry_volume_m3_DERIVED', 'layer_based_concrete_volume_m3_DERIVED', 'edge_manifold_closed', 'required_independent_manual_calculation', 'known_limitations', 'review_status'])}</section>
<section id="agent2"><h2>Agent 2 coordination (read only)</h2>{h_table([dict(requirement=a, status=b, evidence=c) for a, b, c in AG2], ['requirement', 'status', 'evidence'])}
<p class="sub">No file in <code>research/architecture/</code> was modified. Suggested schema decision for flattened export quantities is listed in <code>remaining_blockers.md</code>.</p></section>
<section id="preservation"><h2>Preservation</h2><p>All protected files unchanged: <b>{'yes' if pres['all_protected_unchanged'] else 'NO - see JSON'}</b> ({len(base)} + {len(b4)} baseline files; {len(snap)} Stage 4.0B / Agent 2 files vs consolidation-start snapshot, {len(snap_changed)} changed).</p></section>"""
nav = ''.join(f'<a href="#{a}">{E(b)}</a>' for a, b in secs)
page = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stage 4.0B Consolidated</title><style>{css}</style></head><body><div class="layout"><nav><div class="sub" style="padding:0 8px 8px">Stage 4.0B</div>{nav}</nav><main>{body}</main></div></body></html>'
open(f'{OUT}/stage4_0b_consolidated_report.html', 'w', encoding='utf-8').write(page)
print('html', len(page))
