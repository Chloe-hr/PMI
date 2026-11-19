"""Stage 4.0B (Sections B-E) - build manifest, inventory, matrices, markdown and HTML report.

Run from repository root AFTER extract_reference_coverage.py:
    .venv/Scripts/python.exe -I research/data_acquisition/stage4_0b/sections_B_E/scripts/build_stage4_0b_deliverables.py <baseline_sha256_file>

Reads data only. Writes only under research/data_acquisition/stage4_0b/sections_B_E/.
All statistics are computed from files on disk or quoted from cited sources; nothing is estimated.
"""
import csv, datetime as dt, gzip, hashlib, html, json, os, subprocess, sys, tarfile, zipfile

sys.stdout.reconfigure(encoding='utf-8')
OUT = 'research/data_acquisition/stage4_0b/sections_B_E'
BASELINE = sys.argv[1] if len(sys.argv) > 1 else None
SEVENZIP = r'C:\Program Files\7-Zip\7z.exe'
RAR_DIR = 'data/raw/candidates/productivity/bcca_andalucia/extracted/BCCA23_V02_301023_rar'
SECTION_A_FILES = sum(len(fs) for _, _, fs in os.walk('data/raw/candidates/bim_spatial'))
SECTION_A_STATUS = (f'checked {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}: data/raw/candidates/bim_spatial/ contains '
                    f'{SECTION_A_FILES} files; no Section A deliverables in research/data_acquisition/stage4_0b/')
NOW = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
TODAY = '2026-11-19'


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
    return p


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def integrity(p):
    """Detect HTML error pages, Git LFS pointers, empty or corrupt archives/workbooks."""
    size = os.path.getsize(p)
    if size == 0:
        return 'FAIL: empty file'
    head = open(p, 'rb').read(512)
    low = head.lstrip().lower()
    if head.startswith(b'version https://git-lfs'):
        return 'FAIL: Git LFS pointer'
    ext = os.path.splitext(p)[1].lower()
    if ext not in ('.html', '.htm', '.xml') and (low.startswith(b'<!doctype html') or low.startswith(b'<html')):
        return 'FAIL: HTML page instead of data'
    try:
        if ext == '.zip' or ext == '.xlsx':
            with zipfile.ZipFile(p) as z:
                bad = z.testzip()
            return 'OK: zip CRC verified' if bad is None else f'FAIL: corrupt member {bad}'
        if p.endswith('.tar.gz'):
            with tarfile.open(p, 'r:gz') as t:
                n = len(t.getmembers())
            return f'OK: tar.gz readable ({n} members)'
        if ext == '.pdf':
            tail = open(p, 'rb').read()[-1024:]
            return 'OK: PDF header and EOF marker' if head.startswith(b'%PDF') and b'%%EOF' in tail else 'WARN: PDF markers incomplete'
        if ext == '.rar':
            if not head.startswith(b'Rar!'):
                return 'FAIL: not a RAR'
            if os.path.exists(SEVENZIP):
                t = subprocess.run([SEVENZIP, 't', p], capture_output=True, text=True, errors='replace')
                return 'OK: 7-Zip test "Everything is Ok"' if 'Everything is Ok' in t.stdout else 'FAIL: 7-Zip test failed'
            return 'OK: RAR signature present (7-Zip unavailable for test)'
        if ext == '.presto':
            return 'OK: non-empty proprietary RIB Presto database (not decodable without Presto)'
        if ext == '.mpp':
            return 'OK: OLE2 signature' if head.startswith(bytes.fromhex('d0cf11e0a1b11ae1')) else 'WARN: unexpected signature'
        if ext == '.json':
            json.load(open(p, encoding='utf-8'))
            return 'OK: valid JSON'
    except Exception as e:  # noqa
        return f'FAIL: {type(e).__name__}: {e}'
    return 'OK: non-empty, no HTML/LFS signature'


# ------------------------------------------------------------------ dataset metadata
DS = {
    'bcca': dict(
        dataset='BCCA - Base de Costes de la Construccion de Andalucia, Dic-2023 V02', org='Junta de Andalucia (Consejeria de Fomento, Articulacion del Territorio y Vivienda)',
        url='https://www.juntadeandalucia.es/organismos/viviendajuventudyordenaciondelterritorio/areas/vivienda-rehabilitacion/planes-instrumentos/paginas/bcca-ene-2024.html',
        doi='', version='BCCA2023_V02 (FIEBDC-3/2020, Presto 22.01, file date 2023-11-01; published 2024-01)',
        licence='Junta de Andalucia portal: CC BY 3.0-type reuse; mandatory attribution "Informacion obtenida del Portal de la Junta de Andalucia"; no endorsement implied',
        genuine='Genuine published catalogue (estimated productivity and reference prices; not observed execution data)',
        use='E engineering productivity reference; F cost reference', limits='Andalucia, not Catalonia; catalogue estimates; no crew sizes; eCO2 attribute declared but empty (BC3 and Presto); inner RAR extracted 2026-11-19: BC3 + 3 PDFs byte-identical, Presto DB proprietary; price dates per concept 2008-2022'),
    'cerp': dict(
        dataset='CERP Banco de items de construccion v0.11.0 (Spain bundle)', org='CERP Tech (cerptech/cerp-items-data)',
        url='https://github.com/cerptech/cerp-items-data/tree/9db4fc929c15647431615d2fbf5a53b3ef4f9c3b', doi='',
        version='v0.11.0, commit 9db4fc929c15647431615d2fbf5a53b3ef4f9c3b (generated 2026-11-18)',
        licence='Repo LICENSE: prices reused from public bases under Ley 37/2007 (RISP); attribution "Informacion obtenida del Portal de la Junta de Andalucia"; curation by CERP Tech (no SPDX licence)',
        genuine='Derivative of BCCA edition 2024-01 (same source); not independent evidence',
        use='E/F cross-check only', limits='Re-publication of BCCA; 4,112 of 12,697 items flagged conflicted by CERP verification; encoding mojibake in some text fields; masonry BOM omits labour nested in mortar auxiliary'),
    'oekobaudat': dict(
        dataset='OEKOBAUDAT release 2024-III (full data-stock CSV export)', org='BMWSB / BBSR (Germany)',
        url='https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/bca3670a-8dcf-44d0-be1f-0633d9ba1a75/exportCSV', doi='',
        version='OBD_2024_III, release 13.11.2026 (soda4LCA data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75); exported 2026-11-19T11:58:42Z',
        licence='BMWSB: provided free of charge without restriction; free distribution of unmodified data permitted when source is named',
        genuine='Genuine LCA/EPD datasets (generic, average, specific, representative, template types)',
        use='G environmental evaluation', limits='Mostly German/European scope; only 2 Spanish concrete EPDs; no formwork-system or diesel-fuel datasets; A1 and A2 indicator sets must not be mixed; declared units vary (m3, kg, t, m2, MJ, t*km)'),
    'thiele': dict(
        dataset='Project Portfolio Dataset (Thiele et al. 2020)', org='Figshare / Data in Brief (B. Thiele, M. Ryan, A. Abbasi)',
        url='https://figshare.com/articles/dataset/Project_Portfolio_Dataset/12998822', doi='10.6084/m9.figshare.12998822.v2 (article 10.1016/j.dib.2020.106659)',
        version='Figshare v2 (published 2020-09-25)', licence='CC BY 4.0 (dataset and article)',
        genuine='Genuine completed projects (Queensland local-government civil works, 2011-2015)',
        use='C dependency examples (civil); E/F first-principles productivity and cost (civil); H not eligible; I partial', limits='Civil road/landfill/marina works, not RC buildings; AUD; no activity actual start/finish; actuals at cost-account level; no IFC; article describes 6 projects but v2 has 8 workbooks'),
    'restage': dict(
        dataset='RestageIFC v1.0.0 (Reference Construction Site Aachen)', org='RWTH Aachen / Zenodo',
        url='https://zenodo.org/records/21470658', doi='10.5281/zenodo.21470658', version='1.0.0 (2026-07-21)', licence='CC BY 4.0',
        genuine='Genuine IFC4 demonstrator model with phase tasks and actual finish dates',
        use='A BIM extraction; B/D partial (element-to-phase); I partial', limits='12 phase-level IfcTask, 11 ActualFinish only, no starts, no IfcRelSequence, no resources; single demonstrator; Section A domain (inventoried only)'),
    'dslib': dict(
        dataset='DSLIB v3.4 (Ghent OR&S), buildings subset', org='Ghent University, Operations Research & Scheduling group',
        url='https://github.com/MarioVanhoucke/DSLIB-Dynamic-Scheduling-Empirical-Project-Library/releases/tag/DSLIB_v3.4', doi='',
        version='DSLIB 3.4, local buildings-only subset (87 project codes)', licence='as recorded in prior PMI inventory (not re-audited in 4.0B)',
        genuine='Genuine project schedules with tracking periods (used in Stage 3.5 E5/E6)',
        use='C dependency examples; resource/calendar examples; I partial', limits='No physical quantities, no IFC linkage; Stage 4.0A: 17 independent groups, 71% of labelled activities on plan'),
    'cambridge': dict(
        dataset='Cambridge JPF anonymised project data', org='University of Cambridge repository (handle 1810/307046)',
        url='https://www.repository.cam.ac.uk/handle/1810/307046', doi='', version='as used in Stage 2.3-3.7', licence='as recorded in prior PMI work',
        genuine='Genuine exported schedules', use='C dependency examples (reported elapsed days)',
        limits='Not opened in 4.0B (locked-test protection). Stage 4.0A: target is reported elapsed calendar days; no quantities, crews or IFC'),
}

# files to hash (everything new under the candidate folders)
ROOTS = [('data/raw/candidates/productivity/bcca_andalucia', 'bcca'), ('data/raw/candidates/productivity/cerp', 'cerp'),
         ('data/raw/candidates/environmental/oekobaudat', 'oekobaudat'), ('data/raw/candidates/project_control/real_project_control', 'thiele')]
manifest = []
for root, key in ROOTS:
    m = DS[key]
    for dp, _, fs in os.walk(root):
        for fn in sorted(fs):
            p = os.path.join(dp, fn).replace('\\', '/')
            extracted = '/extracted/' in p
            if key == 'cerp' and extracted and not fn.endswith(('LICENSE', 'README.md', 'SHA256SUMS', 'catalog.json', 'basicos.json', 'index.json', 'VERSION')):
                continue  # 525 bundle files are verified as a set by SHA256SUMS; list key files only
            st = 'Downloaded' if not extracted else 'Downloaded (extracted from archive)'
            chk = integrity(p)
            if RAR_DIR in p:
                st = 'Downloaded (extracted from inner RAR with 7-Zip)'
            manifest.append(dict(dataset_name=m['dataset'], source_organization=m['org'], source_url=m['url'], doi=m['doi'], dataset_version=m['version'],
                                 original_filename=fn, local_file_path=p, download_date=TODAY, file_size_bytes=os.path.getsize(p), sha256=sha256(p),
                                 licence=m['licence'], download_status=st, integrity_check=chk, genuine_or_synthetic=m['genuine'],
                                 intended_pmi_application=m['use'], known_limitations=m['limits']))
# publisher checksum verifications
VERIFY = {
    'cerp': 'All 525 bundle files verified OK against publisher SHA256SUMS (sha256sum -c).',
    'thiele': 'All 9 Figshare files verified OK against Figshare computed_md5.',
    'restage': 'Local file MD5 45b7223611d7a07e748c608bcbb1767b equals Zenodo checksum.',
}
for r in manifest:
    for k, v in VERIFY.items():
        if DS[k]['dataset'] == r['dataset_name']:
            r['publisher_checksum_verification'] = v
# already-local and not-acquired entries
manifest.append(dict(dataset_name=DS['restage']['dataset'], source_organization=DS['restage']['org'], source_url=DS['restage']['url'], doi=DS['restage']['doi'],
                     dataset_version=DS['restage']['version'], original_filename='Restage_IP_ALL_MULTI_001.ifc', local_file_path='data/raw/Restage_IP_ALL_MULTI_001.ifc',
                     download_date='pre-existing (2026-11-16 mtime)', file_size_bytes=os.path.getsize('data/raw/Restage_IP_ALL_MULTI_001.ifc'),
                     sha256=sha256('data/raw/Restage_IP_ALL_MULTI_001.ifc'), licence=DS['restage']['licence'], download_status='Already available locally',
                     integrity_check='OK: IFC4 header', publisher_checksum_verification=VERIFY['restage'], genuine_or_synthetic=DS['restage']['genuine'],
                     intended_pmi_application=DS['restage']['use'], known_limitations=DS['restage']['limits']))
for k, path in [('dslib', 'data/raw/ghent/'), ('cambridge', 'data/raw/cambridge/')]:
    m = DS[k]
    manifest.append(dict(dataset_name=m['dataset'], source_organization=m['org'], source_url=m['url'], dataset_version=m['version'], local_file_path=path,
                         download_date='pre-existing', download_status='Already available locally', licence=m['licence'],
                         integrity_check='covered by preservation baseline hashes', genuine_or_synthetic=m['genuine'],
                         intended_pmi_application=m['use'], known_limitations=m['limits']))
NOT_ACQ = [
    ('CYPE Generador de Precios (Spain)', 'CYPE Ingenieros S.A.', 'https://generadordeprecios.info/obra_nueva', 'Manual download required',
     'Aviso legal: content protected; downloads only for personal, non-commercial use, not transferable to third parties', 'Publicly visible breakdowns incl. labour h/unit; BC3/XLSX/PDF export requires login (verified on EHS010 page)'),
    ('ITeC BEDEC (construction + environmental)', 'ITeC - Institut de Tecnologia de la Construccio de Catalunya', 'https://itec.es/servicios/bedec/', 'Restricted',
     'Subscription (monthly/annual); free trial 15 queries/month after registration; free student licence via ITeC school agreements', 'Catalonia prices + 5-13 environmental indicators; not acquired'),
    ('EC3 / Building Transparency', 'Building Transparency', 'https://buildingtransparency.org/', 'Restricted',
     'API requires authentication (HTTP 401 verified); free tier: no caching or redistribution; paid licence or written consent', 'EPD-level A1-A3 GWP; not acquired'),
    ('DDC CWICR open construction cost database', 'DataDrivenConstruction', 'https://github.com/datadrivenconstruction/OpenConstructionEstimate-DDC-CWICR', 'Unsuitable',
     'CC BY-NC 4.0 data + separate commercial licence', 'Labour norms derived from Russian GESN/FER/TER; non-Spanish; non-commercial'),
    ('Estimated-vs-actual labour hours (Kalasapudi et al. 2025, Frontiers Built Env.)', 'Frontiers / authors', 'https://www.frontiersin.org/journals/built-environment/articles/10.3389/fbuil.2025.1678156/full', 'Unavailable',
     'Data "made available by the authors" on request; no repository', 'Single US civil contractor; no public data'),
]
for n, org, url, st, lic, lim in NOT_ACQ:
    manifest.append(dict(dataset_name=n, source_organization=org, source_url=url, download_date=TODAY, download_status=st, licence=lic,
                         genuine_or_synthetic='n/a (not acquired)' if st != 'Partially downloaded' else 'Genuine', known_limitations=lim))
# Duplicate detection: files acquired earlier (outside the inner-RAR folder) are the reference copies.
first_by_hash = {}
for r in sorted((r for r in manifest if r.get('sha256')), key=lambda r: RAR_DIR in r['local_file_path']):
    p = r['local_file_path']
    r['duplicate_of'] = first_by_hash.get(r['sha256'], '')
    first_by_hash.setdefault(r['sha256'], p)
# BCCA inner RAR content audit (byte comparison with files already held)
rar_audit = []
for r in manifest:
    if RAR_DIR in r.get('local_file_path', ''):
        new = not r['duplicate_of']
        fn = r['original_filename']
        finding = ('Byte-identical duplicate of ' + r['duplicate_of']) if not new else (
            'NEW: proprietary RIB Presto database of the same edition. Read-only byte scan: concept codes stored as plain text (e.g. TP00100 x2,588); '
            'the only "eCO2" string is the attribute definition "Emision de CO2 / kg" (same as BC3 ~X header); all 31 "CO2" strings are product names '
            '(extinguishers, CO2 cylinders, air-quality sensors) or ID fragments. No evidence of emission values, productivity or cost fields beyond the BC3. '
            'Full decoding requires RIB Presto (licensed software); not attempted.')
        rar_audit.append(dict(file=r['local_file_path'], bytes=r['file_size_bytes'], sha256=r['sha256'], new_content=new, finding=finding))
wr('bcca_inner_rar_audit.csv', rar_audit)
MAN_COLS = ['dataset_name', 'source_organization', 'source_url', 'doi', 'dataset_version', 'original_filename', 'local_file_path', 'download_date', 'file_size_bytes',
            'sha256', 'duplicate_of', 'licence', 'download_status', 'integrity_check', 'publisher_checksum_verification', 'genuine_or_synthetic', 'intended_pmi_application', 'known_limitations']
wr('download_manifest.csv', manifest, MAN_COLS)
n_fail = sum(1 for r in manifest if str(r.get('integrity_check', '')).startswith('FAIL'))

# ------------------------------------------------------------------ dataset inventory
prof = rd('data/processed/candidates/stage4_0b/thiele2020/thiele2020_workbook_profile.csv')
INV = [
    dict(dataset_id='D1', **{k: DS['bcca'][k] for k in ('dataset', 'org', 'url', 'version', 'licence', 'genuine')}, status='Downloaded',
         local_path='data/raw/candidates/productivity/bcca_andalucia/', processed_path='data/processed/candidates/stage4_0b/bcca2023/',
         content='15,514 concepts (36 labour, 71 machinery, 5,631 material); 8,426 decomposition records (46,068 lines); 11,532 texts; ~X env attribute schema only',
         granularity='work-item (unit of measure)', geography='Andalucia, ES', section='B'),
    dict(dataset_id='D2', **{k: DS['cerp'][k] for k in ('dataset', 'org', 'url', 'version', 'licence', 'genuine')}, status='Downloaded',
         local_path='data/raw/candidates/productivity/cerp/', processed_path='(used for cross-check only)',
         content='12,697 items (6,566 work items, 5,714 materials, 108 labour/machinery); BOM with quantities; 8,585 auto_ok / 4,112 conflicted',
         granularity='work-item', geography='Andalucia, ES (+ Argentina sub-bundle)', section='B'),
    dict(dataset_id='D3', **{k: DS['oekobaudat'][k] for k in ('dataset', 'org', 'url', 'version', 'licence', 'genuine')}, status='Downloaded',
         local_path='data/raw/candidates/environmental/oekobaudat/', processed_path='data/processed/candidates/stage4_0b/oekobaudat/',
         content='4,325 datasets; 45,078 dataset x module rows; modules A1-A3 ... D kept per row', granularity='product/process per declared unit', geography='mainly DE/EU', section='C'),
    dict(dataset_id='D4', **{k: DS['thiele'][k] for k in ('dataset', 'org', 'url', 'version', 'licence', 'genuine')}, status='Downloaded',
         local_path='data/raw/candidates/project_control/real_project_control/', processed_path='data/processed/candidates/stage4_0b/thiele2020/',
         content=f"8 project workbooks: {sum(int(r['program_tasks']) for r in prof)} programme tasks, {sum(int(r['program_predecessor_links']) for r in prof)} predecessor links, "
                 f"{sum(int(r['estimate_resource_lines']) for r in prof)} estimate resource lines, {sum(int(r['portfolio_wbs_accounts']) for r in prof)} cost accounts, "
                 f"{sum(int(r['actual_cost_lines_dated']) for r in prof)} dated actual-cost lines",
         granularity='task (plan) / cost account (actuals) / dated cost line', geography='Queensland, AU', section='D'),
    dict(dataset_id='D5', **{k: DS['restage'][k] for k in ('dataset', 'org', 'url', 'version', 'licence', 'genuine')}, status='Already available locally',
         local_path='data/raw/Restage_IP_ALL_MULTI_001.ifc', processed_path='(entity counts only)',
         content='IFC4; 12 IfcTask, 12 IfcTaskTime (11 with ActualFinish), 1 IfcWorkSchedule, 4,262 IfcRelAssignsToProduct, 0 IfcRelSequence, 886 IfcElementQuantity; 191 IfcBeam, 92 IfcWall, 12 IfcSlab, 13 IfcFooting, 0 IfcColumn',
         granularity='element + construction phase', geography='Aachen, DE', section='E (A overlap)'),
    dict(dataset_id='D6', **{k: DS['dslib'][k] for k in ('dataset', 'org', 'url', 'version', 'licence', 'genuine')}, status='Already available locally',
         local_path='data/raw/ghent/', processed_path='(prior stages)', content='87 building project codes; sheets: Baseline Schedule (relations, resource demand, costs), Resources (renewable, availability), Agenda (calendar), Tracking periods',
         granularity='activity', geography='Belgium', section='D (prior)'),
    dict(dataset_id='D7', **{k: DS['cambridge'][k] for k in ('dataset', 'org', 'url', 'version', 'licence', 'genuine')}, status='Already available locally (not opened)',
         local_path='data/raw/cambridge/', processed_path='(prior stages)', content='Stage 4.0A: 144,110 development rows / 70 blocks; 36,027 locked rows (protected)',
         granularity='activity', geography='UK', section='D (prior)'),
]
for i, (n, org, url, st, lic, lim) in enumerate(NOT_ACQ[:5], start=8):
    INV.append(dict(dataset_id=f'D{i}', dataset=n, org=org, url=url, version='', licence=lic, genuine='not acquired', status=st, local_path='', processed_path='', content=lim,
                    granularity='', geography='', section='B/C/E'))
wr('dataset_inventory.csv', INV)

# ------------------------------------------------------------------ eligibility matrix
CATS = ['A_bim_extraction', 'B_bim_to_task', 'C_dependency_inference', 'D_ifc4d_export_verification', 'E_productivity_reference', 'F_cost_reference',
        'G_environmental', 'H_supervised_learning', 'I_independent_validation', 'J_unsuitable']
EL = {
    'D1': ('N', 'N', 'N', 'N', 'Y', 'Y', 'N', 'N', 'N', 'N', 'Catalogue person-h and equipment-h per unit for all target RC items except curing; direct unit costs reproduce to +/-0.02 EUR. Estimates, not observations; no crew sizes.'),
    'D2': ('N', 'N', 'N', 'N', 'Partial', 'Partial', 'N', 'N', 'N', 'N', 'Same source as D1; cross-check only.'),
    'D3': ('N', 'N', 'N', 'N', 'N', 'N', 'Y', 'N', 'N', 'N', 'GWP per declared unit with explicit modules for concrete, rebar, steel, timber, plywood, transport, electricity, site processes. No formwork systems or diesel fuel.'),
    'D4': ('N', 'N', 'Partial', 'N', 'Partial', 'Partial', 'N', 'N', 'Partial', 'N', 'Real planned networks, production rates and planned vs actual cost accounts, but civil works (not RC buildings), AUD, no activity actual durations, no IFC. Not eligible for H: target cannot be computed per activity.'),
    'D5': ('Y', 'Partial', 'N', 'Partial', 'N', 'N', 'N', 'N', 'Partial', 'N', 'Genuine IFC4 with element-to-phase assignment and phase actual finish dates; no sequence, starts or durations.'),
    'D6': ('N', 'N', 'Partial', 'N', 'N', 'Partial', 'N', 'N', 'Partial', 'N', 'Real building networks with resources, calendars and tracking; no quantities or IFC; Stage 3.5 showed no model beat plan.'),
    'D7': ('N', 'N', 'Partial', 'N', 'N', 'N', 'N', 'N', 'N', 'N', 'Locked-test protected; reported elapsed calendar days; precedence may include execution edits (Stage 4.0A).'),
    'D8': ('N', 'N', 'N', 'N', 'Pending', 'Pending', 'Pending', 'N', 'N', 'N', 'CYPE not acquired; licence must be cleared before use.'),
    'D9': ('N', 'N', 'N', 'N', 'Pending', 'Pending', 'Pending', 'N', 'N', 'N', 'BEDEC not acquired; subscription or student licence needed.'),
    'D10': ('N', 'N', 'N', 'N', 'N', 'N', 'Pending', 'N', 'N', 'N', 'EC3 not acquired; API licence needed.'),
    'D11': ('N', 'N', 'N', 'N', 'N', 'N', 'N', 'N', 'N', 'Y', 'Non-commercial licence; non-Spanish norms.'),
    'D12': ('N', 'N', 'N', 'N', 'N', 'N', 'N', 'N', 'N', 'Y', 'No public data.'),
}
el_rows = []
for r in INV:
    v = EL[r['dataset_id']]
    el_rows.append(dict(dataset_id=r['dataset_id'], dataset=r['dataset'], status=r['status'], **dict(zip(CATS, v[:10])), rationale=v[10]))
wr('dataset_eligibility_matrix.csv', el_rows)

# ------------------------------------------------------------------ project-control coverage
PCF = [
    ('Project identifiers', 'Y: 8 workbooks P01-P06, P17, P18', 'Y', 'Y', 'Y (single project)'),
    ('Activity identifiers', 'Y: Program Links WBS ids', 'Y', 'Y', 'Partial: 12 phase tasks'),
    ('Construction work-package classification', 'Partial: Portfolio WBS cost codes (civil)', 'Partial: WBS names', 'Partial: free-text description', 'Partial: CON/TIM/STL naming'),
    ('Planned start and finish dates', 'N at activity level (Program Links has duration only; MS Project template not part of dataset)', 'Y: Baseline Start/End', 'Not re-checked (locked protection)', 'N'),
    ('Actual start and finish dates', 'N: none found in any sheet', 'Partial: tracking periods', 'Partial: reported elapsed days only', 'Partial: ActualFinish on 11/12 phases, no ActualStart'),
    ('Planned durations', 'Y: Program Links Duration (unit not stated; Qld non-work calendar provided)', 'Y', 'N/unverified', 'N'),
    ('Actual durations', 'N', 'Partial (tracking)', 'Partial (elapsed calendar days, Stage 4.0A)', 'N'),
    ('Physical construction quantities', 'Y: Model Inputs + Portfolio WBS planned qty (SQ) and final qty (AQ)', 'N', 'N', 'Y: 886 IfcElementQuantity'),
    ('Labour hours', 'Partial: estimate labour lines with Prodn; actual hours only via cost lines with hr units', 'Partial: resource demand', 'N', 'N'),
    ('Equipment hours', 'Partial: plant lines (P) with Prodn; actual plant cost lines', 'Partial', 'N', 'N'),
    ('Crew information', 'Partial: named crews in Estimate (e.g. Stabilising Crew); no headcount per day', 'Partial: renewable resource availability', 'N', 'N'),
    ('Planned costs', 'Y: BAC per cost account; tender budget', 'Y', 'N', 'N'),
    ('Actual costs', 'Y: dated invoice/cost lines + final cost per account', 'Y (tracking AC)', 'N', 'N'),
    ('Productivity measurements', 'Partial: planned production rates (estimate); actual rate derivable only per cost account (Final Rate)', 'N', 'N', 'N'),
    ('Project characteristics', 'Y: article Table 1 (value, duration, type)', 'Y: project cards', 'Partial: project_type, uk_region', 'Partial'),
    ('Progress records', 'Y: monthly %complete claims and monthly AQ/AC/EV/PV', 'Y: EVM tracking periods', 'N', 'N'),
    ('Schedule revisions', 'N: single baseline per project; scope variations only in revenue', 'N', 'N', 'N'),
    ('Granularity', 'Task (plan); cost account (actuals); dated cost line', 'Activity', 'Activity', 'Element + phase'),
    ('Independent IFC/BIM linkage', 'N', 'N', 'N', 'Y (internal to the IFC)'),
]
pc_rows = [dict(field=f, thiele2020_D4=a, dslib_D6=b, cambridge_D7=c, restage_ifc_D5=d,
                evidence='D4: thiele2020_workbook_profile.csv + sheet headers; D5: entity counts in RestageIFC; D6: local DSLIB sheet headers; D7: Stage 4.0A report only (records not opened)') for f, a, b, c, d in PCF]
pc_rows.append(dict(field='Supervised-learning target y=log(actual/engineering)', thiele2020_D4='Not computable per activity: no actual activity durations; engineering duration requires matching quantity and crew per task, which are only at cost-account level',
                    dslib_D6='Actual vs planned durations exist but no quantities -> no engineering duration', cambridge_D7='No quantities -> no engineering duration',
                    restage_ifc_D5='No durations', evidence='Section D 13'))
wr('project_control_coverage.csv', pc_rows)

# ------------------------------------------------------------------ combined evidence matrix
CE = [
    ('Genuine IFC geometry', 'Available', 'RestageIFC IFC4 (D5); other local IFCs belong to Section A', 'data/raw/Restage_IP_ALL_MULTI_001.ifc'),
    ('Element classifications', 'Available', 'IFC entity classes in D5 (IfcBeam 191, IfcWall 92, IfcSlab 12, IfcFooting 13; IfcColumn 0)', 'data/raw/Restage_IP_ALL_MULTI_001.ifc'),
    ('Physical quantities', 'Partial', 'D5: 886 IfcElementQuantity (extraction quality not yet audited; Section A); D4 civil quantities', 'data/raw/Restage_IP_ALL_MULTI_001.ifc'),
    ('Work-package definitions', 'Partial', 'D1 BCCA chapter/work-item structure provides RC work-item definitions with units; not a project WBS', 'data/processed/candidates/stage4_0b/bcca2023/bcca2023_concepts.csv'),
    ('Element-to-task mapping', 'Partial', 'D5: element-to-phase via 4,262 IfcRelAssignsToProduct (phase level only)', 'data/raw/Restage_IP_ALL_MULTI_001.ifc'),
    ('Construction dependencies', 'Partial', 'D4 (civil, 6-345 links per project), D6 (buildings), D7; none linked to IFC elements', 'data/processed/candidates/stage4_0b/thiele2020/thiele2020_workbook_profile.csv'),
    ('Planned activity durations', 'Partial', 'D4 Program Links durations (unit not stated), D6 baseline durations; no RC-building plan linked to IFC', 'data/raw/candidates/project_control/real_project_control/original/'),
    ('Actual activity durations', 'Partial', 'D6 tracking; D7 elapsed days (unverified unit semantics); D4 none; D5 finish dates only', 'data/raw/ghent/; data/raw/Restage_IP_ALL_MULTI_001.ifc'),
    ('Labor productivity', 'Partial', 'D1 catalogue person-h per unit for 17 of 18 targets (estimates); D4 civil production rates; no observed RC field productivity', 'research/data_acquisition/stage4_0b/sections_B_E/productivity_reference_coverage.csv'),
    ('Equipment productivity', 'Partial', 'D1 equipment-h per unit (vibrator, backhoe, loader, roller); D4 civil plant', 'data/processed/candidates/stage4_0b/bcca2023/bcca2023_target_item_resource_lines.csv'),
    ('Crew composition', 'Missing', 'No source states crew headcount for RC items; D1 lists trades only; D6 resource availability is project-specific', '-'),
    ('Resource constraints', 'Partial', 'D6 renewable resource availability; D4 resources sheet; none for Spanish RC projects', 'data/raw/ghent/'),
    ('Construction calendars', 'Partial', 'D4 Queensland non-work calendar 2011-2015; D6 Agenda sheets; no Spanish/Catalan calendar acquired', 'data/raw/candidates/project_control/real_project_control/original/'),
    ('Material unit costs', 'Available', 'D1 5,631 material prices (EUR, Andalucia, dated per concept)', 'data/processed/candidates/stage4_0b/bcca2023/bcca2023_concepts.csv'),
    ('Labor and equipment costs', 'Available', 'D1 36 labour rates (e.g. Of.1a 23.17 EUR/h, peon esp. 22.01 EUR/h) and 71 machinery prices', 'data/processed/candidates/stage4_0b/bcca2023/bcca2023_concepts.csv'),
    ('Environmental coefficients', 'Partial', 'D3 GWP per module for 10 of 13 target groups; no formwork systems, diesel fuel; 2 Spanish concrete EPDs only; BEDEC/EC3 not acquired', 'research/data_acquisition/stage4_0b/sections_B_E/environmental_reference_coverage.csv'),
    ('Genuine design revisions', 'Missing', 'No dataset with genuine model revisions found in Sections B-E', '-'),
    ('Corresponding schedule revisions', 'Missing', 'D4/D6 single baselines; no revision pairs', '-'),
    ('Independent validation projects', 'Partial', 'D4 8 civil projects (different domain); D6 buildings (no quantities); no independent RC-building project with IFC + actual schedule', '-'),
]
ce_rows = [dict(required_evidence=a, status=b, Available='X' if b == 'Available' else '', Partial='X' if b == 'Partial' else '', Missing='X' if b == 'Missing' else '',
                supporting_evidence=c, local_paths=d, section_A_included='No - ' + SECTION_A_STATUS) for a, b, c, d in CE]
wr('combined_evidence_matrix.csv', ce_rows)

# ------------------------------------------------------------------ Stage 4.0A limitation resolution
LIM = [
    ('Mendeley MLP overfitting', 'Cannot be resolved through data acquisition alone', 'New data does not extend the 40-row Mendeley set; the architecture move away from project-level MLP is a design decision.'),
    ('Unverified historical duration units', 'Unresolved', 'Mendeley and Cambridge units are not clarified by any acquired source; D4 Program Links duration unit is also not stated.'),
    ('Lack of physical construction quantities in Cambridge GraphSAGE', 'Unresolved', 'No acquired dataset links quantities to Cambridge activities; merging unrelated data is not defensible.'),
    ('Lack of crew and productivity features', 'Partially addressed', 'D1 supplies catalogue person-h/equipment-h per unit for RC items; crew sizes remain missing everywhere.'),
    ('Weak generalization', 'Cannot be resolved through data acquisition alone', 'No new linked training records were found; generalization needs more independent projects with comparable targets.'),
    ('Lack of independently verified actual duration labels', 'Unresolved', 'D4 has no activity actuals; D5 has phase finish dates only.'),
    ('Limited independent project validation', 'Partially addressed', 'D4 adds 8 real projects (civil, not RC buildings); D5 one IFC demonstrator with phase finishes.'),
    ('Missing relationships between BIM elements and construction activities', 'Partially addressed', 'D5 contains element-to-phase assignments (phase level only).'),
    ('Limited evidence supporting cost predictions', 'Partially addressed', 'D1 gives reproducible reference unit costs (Andalucia); D4 gives planned vs actual cost accounts (civil, AUD). Reference prices are not outcomes.'),
    ('Missing environmental evaluation data', 'Partially addressed', 'D3 provides GWP per lifecycle module for most target materials; formwork systems, diesel and Spanish-specific data gaps remain.'),
    ('Missing resource-constrained scheduling information', 'Partially addressed', 'Calendars and resource availability examples exist (D4, D6), not for Spanish RC projects; crew sizes and site capacity must come from PMI users.'),
]
wr('stage4_0a_limitation_resolution.csv', [dict(stage4_0a_limitation=a, resolution=b, evidence=c) for a, b, c in LIM])

# ------------------------------------------------------------------ decisions
DEC = [
    ('5.0 Hybrid architecture design', 'GO', 'Evidence defines every module boundary: IFC input (D5), work-item catalogue with units and resource lines (D1), lifecycle-separated GWP (D3), planned networks and calendars as structural examples (D4, D6). The gaps (crew, calendars, revisions, ML labels) are known and can be represented as user inputs and optional modules.'),
    ('5.1 BIM quantity extraction', 'CONDITIONAL GO', 'D5 is a genuine IFC4 with 886 IfcElementQuantity sets, but extraction reliability has not been audited and Section A results are not yet available. Condition: Section A audit of quantity completeness and units across several independent IFCs.'),
    ('5.2 BIM-to-task generation', 'CONDITIONAL GO', 'D1 supplies RC work items with units (m3/m2/kg) matching IFC quantity types; D5 shows element-to-phase assignment. No source supplies element-level task mappings or RC dependency rules, so generation must be rule-based and engineer-approved. Condition: documented rule set reviewed by a PMI user.'),
    ('5.3 Engineering duration estimation', 'CONDITIONAL GO', 'Person-h/unit for 17 of 18 targets (D1, catalogue estimates, Andalucia). Missing: crew sizes, daily working hours, productivity adjustments, curing/striking times. Condition: these values entered and approved by a PMI user per project; outputs labelled as catalogue-based estimates.'),
    ('5.4 Resource-constrained IFC4D scheduling', 'CONDITIONAL GO', 'OR-Tools 9.15.6755 is installed in .venv-planning (Python 3.12.14). Dependency, calendar and resource data exist only as foreign examples (D4 Qld, D6 BE). Condition: user-supplied calendar, crew availability and RC sequencing rules; no learned dependencies.'),
    ('5.6 Supervised machine learning', 'NO-GO', 'No acquired dataset contains, for the same activity, an actual duration and the quantity + productivity + crew inputs required to compute an engineering duration in compatible units. D4 actuals are cost-account level and civil; D6/D7 lack quantities; D5 lacks durations. Target y=log(actual/engineering) cannot be computed without unlinked merging.'),
    ('5.7 Scenario optimization', 'CONDITIONAL GO', 'Cost coefficients: D1 direct unit costs reproduce exactly (Andalucia, EUR, mixed concept dates). Environmental: D3 A1-A3/A4/A5 GWP for concrete, steel, timber, transport, electricity, site processes. Condition: keep modules and A1/A2 standards separate, fill formwork/diesel gaps or exclude them, and report geographic mismatch.'),
]
wr('readiness_decisions.csv', [dict(stage=a, decision=b, evidence=c) for a, b, c in DEC])

# ------------------------------------------------------------------ markdown documents
prod = rd(f'{OUT}/productivity_reference_coverage.csv')
cost = rd(f'{OUT}/cost_reference_coverage.csv')
env = rd(f'{OUT}/environmental_reference_coverage.csv')


def md_table(rows, cols, heads=None):
    heads = heads or cols
    s = '| ' + ' | '.join(heads) + ' |\n|' + '---|' * len(cols) + '\n'
    for r in rows:
        s += '| ' + ' | '.join(str(r.get(c, '')).replace('|', '/').replace('\n', ' ') for c in cols) + ' |\n'
    return s


status_counts = {}
for r in manifest:
    status_counts[r['download_status']] = status_counts.get(r['download_status'], 0) + 1
n_files = sum(1 for r in manifest if r.get('sha256') and r['download_status'].startswith(('Downloaded', 'Partially')))
bytes_dl = sum(int(r['file_size_bytes']) for r in manifest if r.get('sha256') and r['download_status'].startswith(('Downloaded', 'Partially')))

open(f'{OUT}/download_log.md', 'w', encoding='utf-8').write(f"""# Stage 4.0B (Sections B-E) - download log

Generated {NOW}. All downloads on {TODAY} from public URLs; no logins, CAPTCHAs or paywalls were bypassed.

## Environment at start
- `git status`: clean, branch `research/pmi-hybrid-planning` (HEAD 35be0f8).
- Disk: C: 925G total, 569G free.
- `.venv`: Python 3.14.7 (not modified). `.venv-planning`: Python 3.12.14, OR-Tools 9.15.6755 installed (not modified).
- Section A: `data/raw/candidates/bim_spatial/` empty; no Section A deliverables present.

## Chronological log
1. **CERP** - `codeload.github.com/cerptech/cerp-items-data/tar.gz/9db4fc9...` -> 5,250,749 bytes. Extracted; `sha256sum -c SHA256SUMS`: 525/525 OK.
2. **CYPE** - Public pages inspected (Estructuras > Hormigon armado > Pilares > EHS010). Breakdown visible; BC3 export requires login; legal notice restricts reuse. Not downloaded.
3. **BCCA (upstream of CERP)** - 5 files from `juntadeandalucia.es/.../2024/01/`: BCCA2023_V02.zip (624,785 B), 5.- BCCA23_V02_301023.rar_.zip (10,761,466 B), three PDF listings. Local filenames first saved with `x20` instead of spaces by a decoding bug in the download loop; renamed to the server names (content untouched, hashes recorded after rename). ZIPs extracted; inner `.rar` could not be extracted (no unrar/7-Zip).
4. **BCCA parse** - BC3 decoded as cp1252 (header `ANSI`); 35,476 records -> inspection CSVs. `~X` declares eCO2/ce/m/v/ler but no concept carries values.
5. **BEDEC** - itec.es pages read: subscription; 15 free queries/month after registration; student licences. Not downloaded.
6. **OEKOBAUDAT** - soda4LCA data-stock list; current release OBD_2024_III (13.11.2026). Official `exportCSV` endpoint -> 52,179,438 bytes, ISO-8859-1, `;`-separated. Response headers saved.
7. **EC3** - `buildingtransparency.org/api/materials` -> HTTP 401. Terms: free tier no caching/redistribution. Not downloaded.
8. **PMC7770534** - pmc.ncbi.nlm.nih.gov returned a browser check; full text taken from Europe PMC REST (`PMC7770534/fullTextXML`, CC BY). Data availability: Figshare 10.6084/m9.figshare.12998822.v2.
9. **Figshare 12998822 v2** - metadata JSON + 9 files; MD5 9/9 OK (an initial shell comparison falsely reported mismatches because of a trailing CR; re-verified in Python).
10. **Section E** - searches for linked IFC+schedule, RC productivity, XER, BoQ-vs-actual, revision datasets. RestageIFC (Zenodo 21470658) found to be byte-identical to local `data/raw/Restage_IP_ALL_MULTI_001.ifc` (MD5) - not re-downloaded. DDC CWICR (CC BY-NC) and Frontiers 2025 (on request) not downloaded.

11. **BCCA inner RAR (resumed session)** - 7-Zip 26.06 installed by user. `7z t`: Everything is Ok (5 files, 26,253,092 B). Extracted to new folder `extracted/BCCA23_V02_301023_rar/` (original RAR kept). BC3 and 3 PDFs byte-identical to earlier copies; one new file `BCCA2023_V02.Presto` (13,648,337 B, proprietary). Audit: `bcca_inner_rar_audit.csv`.
12. **Section A check** - {SECTION_A_STATUS}.

## Totals
- Files downloaded/extracted and hashed: {n_files} ({bytes_dl:,} bytes), integrity failures: {n_fail}.
- Status counts in `download_manifest.csv`: {', '.join(f'{k}={v}' for k, v in status_counts.items())}.
""")

open(f'{OUT}/manual_download_required.md', 'w', encoding='utf-8').write("""# Manual actions required (Sections B-E)

None of these were attempted with credentials. Destination folders already exist or must be created by the user.

## 1. ITeC BEDEC - Catalonia prices, productivity justifications and environmental indicators
- **Website:** https://itec.es/servicios/bedec/ (metabase), shop: https://tienda.itec.es/categoria-producto/bedec-es/
- **Access:** paid subscription (monthly/annual: "BEDEC Proyecto y obra", "BEDEC Sostenibilidad"); free community registration gives 15 queries/month; free student licence via https://itec.es/servicios/licencias/ (requires school agreement, professor approval and enrolment PDF).
- **Relevant content:** "Justificaciones de partidas de obra" (labour/machinery/material breakdown), Catalonia/Barcelona prices; environmental indicators (CO2, energy, waste, recycled content, water; 13 indicators in Sostenibilidad tier).
- **Steps:** (1) obtain licence (student route recommended for research); (2) log in to the BEDEC web; (3) select Barcelona territory and current edition; (4) build a selection of structural chapters (foundations, RC structure, earthworks, masonry) matching the 18 target items in `productivity_reference_coverage.csv`; (5) export as FIEBDC-3 (BC3) - BEDEC states compatibility with TCQ, Presto, Arquimedes and any BC3 program; (6) also export environmental fields if the tier includes them.
- **Export formats verified:** BC3 interoperability stated by ITeC; direct download path not verified (behind login).
- **Destination:** `data/raw/candidates/productivity/bedec/` and `data/raw/candidates/environmental/bedec/`.
- **Check first:** licence terms on redistribution and on use inside PMI.
- **Still missing without it:** Catalonia-specific rates; Spanish environmental indicators per work item.

## 2. CYPE Generador de Precios
- **Website:** https://generadordeprecios.info/obra_nueva (structures: .../Estructuras/Hormigon_armado.html; codes e.g. EHS010 pilar, EHV vigas, EHL losas; C cimentaciones; A acondicionamiento del terreno).
- **Access:** free registration ("Registrate gratis"); BC3 export requires login ("Para poder utilizar esta caracteristica ... es necesario iniciar sesion"). Legal notice (https://shop.cype.com/es/aviso-legal/): copies for personal, non-commercial use only, not transferable to third parties.
- **Steps:** (1) register; (2) select Spain > province Barcelona; (3) open each target item, set parameters (concrete class, formwork type); (4) export (BC3/XLSX/PDF per CYPE documentation); (5) store with the parameter selection recorded.
- **Destination:** `data/raw/candidates/productivity/cype/`.
- **Caution:** CYPE RC items such as EHS010 are composite (formwork + rebar + concrete per m3) - not directly comparable with BCCA's separated items. Confirm with CYPE whether research/derived use is allowed before integrating into PMI.

## 3. EC3 / Building Transparency
- **Website:** https://buildingtransparency.org/ ; API pricing/terms: https://www.buildingtransparency.org/api-access-pricing/
- **Access:** free account; API key; free tier 500 requests/day, no caching or redistribution, no commercial use. Paid order form or fee-waiver (https://www.buildingtransparency.org/wp-content/uploads/2026/05/EC3_API_Fee_Waiver_Application_fillable_final.pdf) for storage/reuse. Notify support before integrating.
- **Steps:** (1) create account; (2) request fee waiver for academic use; (3) after written permission, export Ready-Mix Concrete, Rebar, Structural steel, Plywood EPDs filtered to Spain/Europe.
- **Destination:** `data/raw/candidates/environmental/ec3/`.

## 4. BCCA Presto database (optional)
- RESOLVED 2026-11-19: inner RAR tested and extracted with 7-Zip into `data/raw/candidates/productivity/bcca_andalucia/extracted/BCCA23_V02_301023_rar/`.
- Remaining optional action: `BCCA2023_V02.Presto` is a proprietary RIB Presto database. Opening it requires a RIB Presto licence; the byte scan found no data beyond the BC3, so this is low priority.

## 5. Spanish environmental and calendar inputs not available as open data in this search
- Catalan construction labour calendar (convenio provincial de la construccion de Barcelona) - working hours/holidays must be entered by PMI user.
""")

open(f'{OUT}/training_data_gap_analysis.md', 'w', encoding='utf-8').write(f"""# Training-data gap analysis (Sections B-E)

## Question
Can any acquired dataset support `y = log(actual_duration / engineering_duration)` (research hypothesis, not an approved protocol)?

## Requirements for one valid record
1. Actual activity duration with known calendar semantics (working vs calendar days).
2. For the same activity: physical quantity, unit, productivity basis and crew assumptions, so that `engineering_duration = quantity x h_per_unit / (crew x hours_per_day)` can be computed in compatible units.
3. Planning-time features recorded before execution (quantity, work type, method, crew, predecessors, lags, resource limits).
4. Project grouping for leakage-safe validation (many independent projects).

## Findings per dataset
| Dataset | 1 actual duration | 2 engineering inputs | 3 planning-time features | 4 groups | Eligible |
|---|---|---|---|---|---|
| D4 Thiele 2020 | No activity actuals (monthly cost-account progress + dated invoices only) | Planned quantity and production rate per estimate line; crews named but no daily headcount | Plan network + estimate are pre-execution | 8 projects, one contractor | No |
| D6 DSLIB buildings | Tracking periods (Stage 3.5: 53 projects / 17 groups labelled) | No quantities | Baseline network, resources | 17 independent groups | No (no engineering duration) |
| D7 Cambridge | Reported elapsed calendar days | No quantities | Activity text, type, region | 70 dev blocks (locked set protected) | No |
| D5 RestageIFC | Phase ActualFinish only (11 of 12) | IFC quantities exist; no starts/crews | Phase assignment | 1 project | No |
| D1/D2 BCCA/CERP | n/a (catalogue) | Person-h per unit (estimate) | n/a | n/a | Not training data |

## Leakage risks identified
- D4 `Final Qty`, `Final Cost`, `Final Rate`, monthly AQ/AC/EV and `%C Claim` columns are post-execution: must never be features.
- D4 `Budget & Revenue` contract quantities after variations are post-award changes.
- D7 precedence may contain execution-period edits (Stage 4.0A).
- Catalogue productivity (D1) must not be presented as observed productivity; using it both to build the engineering estimate and as a feature is allowed only as the baseline term.

## What would close the gap
- RC building projects (preferably Spanish) where the same activity has: IFC-linked quantities, planned crew and calendar, and recorded actual start/finish (e.g. daily site reports or P6/MS Project progress updates), across many independent projects.
- Until then: Stage 5.6 is NO-GO; engineering-based planning (5.1-5.4, 5.7) does not depend on it.

## Values a PMI user must enter or approve
Crew size per trade; working hours per day and calendar (Catalan holidays); productivity adjustment factors; equipment availability; concrete curing and formwork striking times / strength criteria; site resource limits; which BCCA/BEDEC/CYPE item variant applies (e.g. soil consistency, concrete class, formwork material); formwork reuse count; transport distances.
""")

# report markdown
def status_word(s):
    return s
prod_t = [r for r in prod if r['target_id'] != 'ALL']
rep = f"""# Stage 4.0B - Dataset acquisition and evidence audit (Sections B-E)

Generated {NOW}. Section A (BIM/spatial) is a separate task; {SECTION_A_STATUS}. Its outputs were not yet present, so this report covers Sections B-E and is stored in `research/data_acquisition/stage4_0b/sections_B_E/` for later consolidation.

## Executive summary
- **Downloaded:** BCCA Dic-2023 (Andalucia, BC3 + PDFs), CERP v0.11.0 (BCCA derivative), OEKOBAUDAT 2024-III full CSV, Thiele et al. 2020 project portfolio (8 workbooks, CC BY). {n_files} files hashed, {n_fail} integrity failures.
- **Not acquired:** CYPE (licence: personal use; login for export), BEDEC (subscription), EC3 (authenticated API, no-caching terms) - see `manual_download_required.md`.
- **Productivity:** catalogue person-hours and equipment-hours per unit for 17 of 18 RC target items (curing bundled into concreting). These are **catalogue estimates**, not observed field productivity. No source gives crew sizes.
- **Cost:** BCCA direct unit costs reproduce from their decompositions to within +/-0.02 EUR.
- **Environment:** OEKOBAUDAT gives lifecycle-module-separated GWP for concrete, rebar, structural steel, timber, plywood, transport, electricity, site processes and waste; no formwork systems or diesel fuel; BCCA's eCO2 field is empty.
- **Project control:** Thiele 2020 is genuine and rich (plan network, production rates, planned vs actual cost accounts) but civil works, AUD, without activity actual dates or IFC linkage.
- **ML:** no dataset yields linked records for `log(actual/engineering)`. Stage 5.6 = NO-GO.

## Update: BCCA inner RAR (resumed)
The RAR passed the 7-Zip integrity test and was extracted to `data/raw/candidates/productivity/bcca_andalucia/extracted/BCCA23_V02_301023_rar/`. Four of five files are byte-identical duplicates of files already audited. The only new file, `BCCA2023_V02.Presto`, is a proprietary database of the same edition; a read-only byte scan found no environmental values or extra productivity/cost fields. **Readiness decisions are unchanged.** See `bcca_inner_rar_audit.csv`.

## Readiness decisions
{md_table([dict(stage=a, decision=b, evidence=c) for a, b, c in DEC], ['stage', 'decision', 'evidence'])}
## Productivity reference coverage (BCCA, catalogue estimates)
{md_table(prod_t, ['target_id', 'work_item', 'required_unit', 'source_code', 'source_unit', 'labour_h_per_unit_total', 'labour_h_per_unit_by_trade', 'equipment_h_per_unit', 'notes'])}
## Environmental coverage (OEKOBAUDAT 2024-III)
{md_table(env, ['target_id', 'material_or_process', 'source', 'datasets_found', 'declared_units', 'standard_split', 'spain_specific', 'status'])}
### Lifecycle boundaries and what PMI can influence
- A1-A3 (production) changes with **design revisions, quantity increases and material substitution** (concrete class, rebar content, timber vs steel formwork).
- A4 (transport) changes with **supplier distance, mode and additional deliveries**.
- A5 (construction/installation) changes with **construction method, equipment usage (excavators, pumps), site energy and waste**; this is the module a schedule can influence (e.g. equipment idle hours, site electricity, formwork reuse cycles).
- B and C/D are largely independent of the construction schedule.
- Shorter duration does **not** automatically reduce embodied carbon: acceleration can add equipment, formwork sets or high-early-strength cement (higher A1-A3).
- EN 15804+A1 `GWP` and +A2 `GWPtotal` are different indicator definitions and are kept in separate columns.

## Project-control assessment
{md_table(pc_rows, ['field', 'thiele2020_D4', 'dslib_D6', 'restage_ifc_D5'])}
## Stage 4.0A limitation resolution
{md_table([dict(stage4_0a_limitation=a, resolution=b, evidence=c) for a, b, c in LIM], ['stage4_0a_limitation', 'resolution', 'evidence'])}
## Combined evidence (Sections B-E; Section A pending)
{md_table(ce_rows, ['required_evidence', 'status', 'supporting_evidence'])}
## Productivity feasibility
`Labour hours = quantity x labour h per unit` is supported for the targets above, with the IFC quantity unit matching the BCCA unit except blinding (m2 vs m3). `Productive duration = labour hours / effective crew-hours per day` needs crew size and working hours, which no acquired source provides. Parallel activities, curing and striking waits, equipment availability and calendars must come from PMI users or approved rules. Nothing was implemented in this stage.

## Recommended next steps
1. Wait for Section A, then consolidate into a single `research/data_acquisition/stage4_0b/` set.
2. Obtain a BEDEC student licence for Barcelona prices and environmental indicators; seek CYPE written permission.
3. Define the PMI user-input schema (crew, calendar, adjustment factors, curing/striking) before Stage 5.3.
4. Keep Stage 5.6 closed until linked RC records with actual activity dates are found or collected.

## Deliverables
All in `research/data_acquisition/stage4_0b/sections_B_E/`: download_manifest.csv, download_log.md, dataset_inventory.csv, dataset_eligibility_matrix.csv, manual_download_required.md, productivity_reference_coverage.csv, cost_reference_coverage.csv, environmental_reference_coverage.csv, project_control_coverage.csv, combined_evidence_matrix.csv, training_data_gap_analysis.md, stage4_0a_limitation_resolution.csv, readiness_decisions.csv, stage4_0b_report.md, stage4_0b_report.html, preservation_verification.json. Scripts in `scripts/`.
"""
open(f'{OUT}/stage4_0b_report.md', 'w', encoding='utf-8').write(rep)

# ------------------------------------------------------------------ preservation verification
pres = dict(generated=NOW, baseline_file=BASELINE, checks=[])
if BASELINE:
    base = {}
    for line in open(BASELINE, encoding='utf-8'):
        h, p = line.rstrip('\n').split(' ', 1)
        base[p.lstrip('*')] = h
    changed, missing = [], []
    for p, h in base.items():
        if not os.path.exists(p):
            missing.append(p)
        elif sha256(p) != h:
            changed.append(p)
    pres['checks'].append(dict(check='protected files vs pre-task SHA-256 baseline (models/, data/processed/ excl. candidates, research/evaluation, research/gnn, data/raw excl. candidates, data/*.csv|json)',
                               total=len(base), unchanged=len(base) - len(changed) - len(missing), changed=changed, missing=missing))
s4a = 'research/evaluation/stage4_0a/preservation/baseline_sha256_before_stage4_0a.txt'
b4 = {}
for line in open(s4a, encoding='utf-8'):
    h, p = line.rstrip('\n').split(' ', 1)
    b4[p.lstrip('*')] = h
bad4 = [p for p, h in b4.items() if not os.path.exists(p) or sha256(p) != h]
pres['checks'].append(dict(check='Stage 4.0A baseline (342 files) still identical', total=len(b4), unchanged=len(b4) - len(bad4), changed_or_missing=bad4))
gs = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.splitlines()
tracked_mod = [l for l in gs if not l.startswith('??')]
pres['checks'].append(dict(check='git: no tracked file modified', tracked_modifications=tracked_mod, untracked_new=[l[3:] for l in gs if l.startswith('??')]))
pres['checks'].append(dict(check='Cambridge locked-test records not parsed', result='data/raw/cambridge/ only hashed byte-wise in baseline; no JSON parse in 4.0B scripts'))
pres['checks'].append(dict(check='No training/inference/fitting', result='scripts contain parsing, counting and arithmetic recomputation only'))
pres['checks'].append(dict(check='Download integrity', files_checked=n_files, failures=n_fail))
pres['discrepancies'] = [
    'Thiele article describes 6 projects; Figshare v2 contains 8 project workbooks (P17, P18 added).',
    'BCCA local filenames initially saved with "x20" in place of spaces (download-loop decoding bug); renamed to server names before hashing; content unchanged.',
    'Figshare MD5 first reported as mismatching in shell (CR in TSV); re-verified 9/9 OK in Python.',
    'BCCA inner RAR: 4 of 5 extracted files are byte-identical duplicates of earlier downloads (recorded in duplicate_of column).',
    'CERP masonry BOM labour (1.05 h/m2) omits labour nested in mortar auxiliary that BCCA expansion includes (1.096 h/m2).',
]
pres['all_protected_unchanged'] = all((not c.get('changed') and not c.get('missing') and not c.get('changed_or_missing') and not c.get('tracked_modifications')) for c in pres['checks'])
json.dump(pres, open(f'{OUT}/preservation_verification.json', 'w', encoding='utf-8'), indent=2)
print('preservation all unchanged:', pres['all_protected_unchanged'])

# ------------------------------------------------------------------ HTML report
E = html.escape


def h_table(rows, cols, heads=None, cls=''):
    heads = heads or cols
    s = f'<div class="tw"><table class="{cls}"><thead><tr>' + ''.join(f'<th>{E(h)}</th>' for h in heads) + '</tr></thead><tbody>'
    for r in rows:
        s += '<tr>' + ''.join(f'<td>{fmt(r.get(c, ""), c)}</td>' for c in cols) + '</tr>'
    return s + '</tbody></table></div>'


BADGE = {'GO': ('ok', 'GO'), 'CONDITIONAL GO': ('warn', 'CONDITIONAL'), 'NO-GO': ('bad', 'NO-GO'), 'Available': ('ok', 'Available'), 'Partial': ('warn', 'Partial'),
         'Missing': ('bad', 'Missing'), 'Y': ('ok', 'Yes'), 'N': ('mute', 'No'), 'Pending': ('warn', 'Pending')}
SYM = {'ok': '&#10003;', 'warn': '&#9680;', 'bad': '&#10007;', 'mute': '&middot;'}


def fmt(v, col=''):
    v = '' if v is None else str(v)
    if v in BADGE and col in ('decision', 'status') + tuple(CATS):
        k, lab = BADGE[v]
        return f'<span class="b {k}">{SYM[k]} {E(lab)}</span>'
    if v.startswith('http'):
        return f'<a href="{E(v)}">{E(v)}</a>'
    if col in ('local_file_path', 'local_path', 'local_paths', 'processed_path', 'local_file'):
        return f'<code>{E(v)}</code>'
    return E(v)


bars = ''
mx = max(float(r['labour_h_per_unit_total']) for r in prod_t if r.get('labour_h_per_unit_total') not in ('', None))
for r in prod_t:
    v = r.get('labour_h_per_unit_total')
    if v in ('', None):
        bars += f'<div class="bar"><span class="bl">{E(r["target_id"])} {E(r["work_item"])}</span><span class="bt none">no stand-alone item (bundled in concreting)</span></div>'
        continue
    w = 100 * float(v) / mx
    tip = f'{r["work_item"]} | {r["source_code"]} | {v} person-h per {r["source_unit"]} | {r["labour_h_per_unit_by_trade"]}'
    bars += (f'<div class="bar" title="{E(tip)}"><span class="bl">{E(r["target_id"])} {E(r["work_item"])} <small>{E(r["source_code"])}</small></span>'
             f'<span class="bt"><span class="bf" style="width:{w:.1f}%"></span><span class="bv">{float(v):g} h/{E(r["source_unit"])}</span></span></div>')

MODS = ['A1-A3', 'A4', 'A5', 'B1', 'B6', 'C1', 'C2', 'C3', 'C4', 'D']
heat = '<div class="tw"><table class="heat"><thead><tr><th>Target</th>' + ''.join(f'<th>{m}</th>' for m in MODS) + '</tr></thead><tbody>'
for r in env:
    if r['target_id'] == 'ALL':
        continue
    mods = dict(x.split('=') for x in r['lifecycle_modules_rows'].split('; ') if '=' in x)
    tot = int(r['datasets_found'] or 0)
    heat += f'<tr><td>{E(r["target_id"])} {E(r["material_or_process"])} <small>({tot} datasets)</small></td>'
    for m in MODS:
        n = int(mods.get(m, 0))
        frac = min(1.0, n / tot) if tot else 0
        heat += f'<td class="hc" style="--a:{0.08 + 0.72 * frac:.2f}" title="{E(r["material_or_process"])} {m}: {n} dataset-module rows of {tot} datasets">{n or "&ndash;"}</td>'
    heat += '</tr>'
heat += '</tbody></table></div><p class="sub">Cell = number of dataset-module rows in OEKOBAUDAT 2024-III for that module (shade = share of the group\'s datasets; a dataset can contribute several scenario rows to C/D). A1, A2, A3 reported separately for some datasets are not shown.</p>'

ce_cnt = {s: sum(1 for r in ce_rows if r['status'] == s) for s in ('Available', 'Partial', 'Missing')}
dec_rows = [dict(stage=a, decision=b, evidence=c) for a, b, c in DEC]
css = """:root{--surface:#fcfcfb;--panel:#fff;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--rule:#e4e3df;--accent:#2a78d6;--code:#f4f3f0;
--ok:#1d7a3a;--ok-bg:#e7f4ec;--warn:#8a5a00;--warn-bg:#fff6e5;--bad:#a12a2a;--bad-bg:#fdecec;--bar:#2a78d6}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--surface:#1a1a19;--panel:#222220;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e86;--rule:#3a3936;--accent:#3987e5;--code:#2b2a28;
--ok:#6fd08f;--ok-bg:#1c3324;--warn:#f2c46b;--warn-bg:#3a2e12;--bad:#f29b9b;--bad-bg:#3d1d1d;--bar:#3987e5}}
:root[data-theme="dark"]{--surface:#1a1a19;--panel:#222220;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e86;--rule:#3a3936;--accent:#3987e5;--code:#2b2a28;
--ok:#6fd08f;--ok-bg:#1c3324;--warn:#f2c46b;--warn-bg:#3a2e12;--bad:#f29b9b;--bad-bg:#3d1d1d;--bar:#3987e5}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,-apple-system,sans-serif}
.layout{display:grid;grid-template-columns:240px minmax(0,1fr);max-width:1400px;margin:0 auto}
nav{position:sticky;top:0;height:100vh;overflow:auto;padding:20px 14px;border-right:1px solid var(--rule)}
nav a{display:block;color:var(--ink2);text-decoration:none;padding:4px 8px;border-radius:6px;font-size:13.5px}nav a:hover{background:var(--code);color:var(--ink)}
main{padding:28px 32px 80px;min-width:0}h1{font-size:26px;margin:0 0 6px}h2{font-size:21px;margin:40px 0 10px;padding-top:10px;border-top:1px solid var(--rule)}
p,li{max-width:90ch}.sub{color:var(--ink2);font-size:13.5px}a{color:var(--accent)}code{background:var(--code);padding:0 4px;border-radius:4px;font-size:12.5px;word-break:break-all}
.callout{border-left:4px solid var(--warn);background:var(--warn-bg);padding:10px 14px;border-radius:6px;margin:12px 0;max-width:95ch}
.tw{overflow-x:auto;margin:8px 0 14px}table{border-collapse:collapse;font-size:13px;min-width:50%}
th,td{border-bottom:1px solid var(--rule);padding:5px 10px;text-align:left;vertical-align:top}th{color:var(--ink2);font-weight:600;white-space:nowrap;background:var(--surface)}
.b{display:inline-block;white-space:nowrap;font-size:12px;font-weight:600;padding:1px 8px;border-radius:999px}
.b.ok{color:var(--ok);background:var(--ok-bg)}.b.warn{color:var(--warn);background:var(--warn-bg)}.b.bad{color:var(--bad);background:var(--bad-bg)}.b.mute{color:var(--muted)}
.tiles{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}.tile{border:1px solid var(--rule);border-radius:10px;padding:10px 16px;background:var(--panel);min-width:150px}
.tile .n{font-size:26px;font-weight:600;font-variant-numeric:tabular-nums}.tile .l{color:var(--ink2);font-size:12.5px}
.bars{max-width:900px}.bar{display:grid;grid-template-columns:minmax(150px,300px) 1fr;gap:10px;align-items:center;padding:3px 0}
.bl{font-size:13px}.bl small{color:var(--muted)}.bt{position:relative;height:18px}.bt.none{color:var(--muted);font-size:12.5px;height:auto}
.bf{position:absolute;left:0;top:3px;height:12px;background:var(--bar);border-radius:0 4px 4px 0}.bv{position:absolute;left:calc(100% + 6px);top:0;font-size:12px;color:var(--ink2);white-space:nowrap}
.bar:hover .bf{filter:brightness(1.15)}.bt .bv{left:auto;right:0}
table.heat td.hc{text-align:center;font-variant-numeric:tabular-nums;background:color-mix(in srgb,var(--bar) calc(var(--a)*100%),transparent)}
table.heat td.hc:hover{outline:2px solid var(--ink)}
@media (max-width:820px){.layout{grid-template-columns:1fr}nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--rule)}main{padding:16px}.bar{grid-template-columns:1fr}}"""
sections = [('summary', 'Executive summary'), ('decisions', 'Readiness decisions'), ('stats', 'Acquisition statistics'), ('inventory', 'Dataset inventory'),
            ('manifest', 'Files and locations'), ('coverage', 'Evidence coverage'), ('productivity', 'Productivity reference'), ('cost', 'Cost reference'),
            ('environment', 'Environmental lifecycle'), ('control', 'Project control'), ('ml', 'Supervised-learning eligibility'), ('limits', 'Stage 4.0A limitations'),
            ('manual', 'Manual actions'), ('next', 'Next steps'), ('preservation', 'Preservation')]
nav = ''.join(f'<a href="#{a}">{E(b)}</a>' for a, b in sections)
files_rows = [r for r in manifest if r.get('local_file_path')]
body = f"""
<h1>Stage 4.0B - Dataset acquisition and evidence audit</h1>
<p class="sub">Sections B-E (productivity and cost, environmental, project control, targeted search). Generated {E(NOW)}. Section A (BIM/spatial) runs separately; its outputs were not present, so the evidence matrix marks it as pending.</p>
<section id="summary"><h2>Executive summary</h2>
<ul>
<li><b>Downloaded and verified:</b> BCCA Dic-2023 (Junta de Andalucia), CERP v0.11.0 (BCCA derivative, cross-check only), OEKOBAUDAT 2024-III, Thiele et al. 2020 project portfolio. {n_files} files hashed; {n_fail} integrity failures.</li>
<li><b>Restricted or manual:</b> CYPE (personal-use licence; export needs login), BEDEC (subscription), EC3 (authenticated API, no-caching terms).</li>
<li><b>Productivity:</b> catalogue person-hours per unit for 17 of 18 RC target items. These are estimates, not observed field productivity. No source gives crew sizes.</li>
<li><b>Environment:</b> lifecycle-module GWP for concrete, rebar, steel, timber, plywood, transport, electricity and site processes; no formwork systems or diesel fuel; BCCA eCO2 field is empty.</li>
<li><b>Machine learning:</b> no linked records exist for <code>log(actual/engineering)</code>. Stage 5.6 is NO-GO; engineering-based planning can proceed under conditions.</li>
</ul></section>
<div class="callout"><b>Update (resumed session):</b> BCCA inner RAR tested OK and extracted to <code>{E(RAR_DIR)}/</code>. Four of five files are byte-identical to earlier copies; the new Presto database adds no evidence found by byte scan. Readiness decisions unchanged. Section A: {E(SECTION_A_STATUS)}.</div>
{h_table(rar_audit, ['file', 'bytes', 'new_content', 'finding'])}
<section id="decisions"><h2>Readiness decisions</h2>{h_table(dec_rows, ['stage', 'decision', 'evidence'])}
<p class="sub">A NO-GO for machine learning does not block engineering-based planning.</p></section>
<section id="stats"><h2>Acquisition statistics</h2>
<div class="tiles">{''.join(f'<div class="tile"><div class="n">{v}</div><div class="l">{E(k)}</div></div>' for k, v in status_counts.items())}
<div class="tile"><div class="n">{bytes_dl / 1e6:.1f} MB</div><div class="l">bytes hashed (downloads + extracted)</div></div></div>
<p class="sub">Counts are manifest rows: individual files for downloaded datasets, one row per dataset otherwise.</p></section>
<section id="inventory"><h2>Dataset inventory</h2>{h_table(INV, ['dataset_id', 'dataset', 'status', 'org', 'url', 'licence', 'genuine', 'content', 'granularity', 'geography', 'local_path'])}
<h3>Eligibility matrix</h3>{h_table(el_rows, ['dataset_id', 'dataset'] + CATS + ['rationale'], ['ID', 'Dataset', 'A BIM', 'B task', 'C dep.', 'D IFC4D', 'E prod.', 'F cost', 'G env.', 'H ML', 'I valid.', 'J unsuit.', 'Rationale'])}</section>
<section id="manifest"><h2>Files and exact local locations</h2><details><summary>{len(files_rows)} file rows with SHA-256</summary>
{h_table(files_rows, ['local_file_path', 'file_size_bytes', 'sha256', 'download_status', 'integrity_check', 'publisher_checksum_verification', 'source_url'])}</details></section>
<section id="coverage"><h2>Combined evidence coverage</h2>
<div class="tiles"><div class="tile"><div class="n">{ce_cnt['Available']}</div><div class="l">Available</div></div><div class="tile"><div class="n">{ce_cnt['Partial']}</div><div class="l">Partial</div></div><div class="tile"><div class="n">{ce_cnt['Missing']}</div><div class="l">Missing</div></div></div>
{h_table(ce_rows, ['required_evidence', 'status', 'supporting_evidence', 'local_paths'])}
<div class="callout">Complementary datasets are not linked records. No relationship between BCCA items, OEKOBAUDAT datasets, Thiele projects and the IFC models has been established, and none was merged.</div></section>
<section id="productivity"><h2>Productivity reference coverage</h2>
<p>Person-hours per measurement unit from BCCA decompositions (auxiliaries expanded). Hover a bar for the trade split. Bars compare across items that share a unit only; units differ (m3, m2, kg).</p>
<div class="bars">{bars}</div>
{h_table(prod_t, ['target_id', 'work_item', 'required_unit', 'source_code', 'description', 'source_unit', 'unit_matches_target', 'labour_h_per_unit_by_trade', 'labour_rates_eur_per_h', 'equipment_h_per_unit', 'cerp_crosscheck_labour_h', 'notes'])}
<div class="callout">Category: estimated catalogue productivity. Not observed field productivity and not a verified historical execution outcome.</div></section>
<section id="cost"><h2>Cost reference coverage</h2>{h_table([r for r in cost if r['target_id'] != 'ALL'], ['target_id', 'work_item', 'source_code', 'source_unit', 'stated_direct_unit_cost_eur', 'recomputed_from_top_level_lines_eur', 'recompute_difference_eur', 'reference_date_concept_ddmmyy'])}
<p class="sub">Direct costs only (no overheads, general expenses, profit or VAT). Concept dates are DDMMYY in the BC3.</p></section>
<section id="environment"><h2>Environmental lifecycle coverage</h2>{heat}
{h_table(env, ['target_id', 'material_or_process', 'source', 'status', 'datasets_found', 'declared_units', 'standard_split', 'geography', 'spain_specific', 'selection_rule'])}
<ul><li>A1-A3 changes with design revisions, quantities and material substitution. A4 changes with transport. A5 changes with construction method, equipment and site energy, the part a schedule can influence.</li>
<li>Shorter duration does not automatically lower embodied carbon. Acceleration can add equipment, formwork sets or high-early-strength cement.</li>
<li>EN 15804+A1 <code>GWP</code> and +A2 <code>GWPtotal</code> are separate indicators and are not combined.</li></ul></section>
<section id="control"><h2>Project-control data assessment</h2>
{h_table(prof, ['file', 'program_tasks', 'program_predecessor_links', 'estimate_resource_lines', 'estimate_labour_lines', 'estimate_plant_lines', 'portfolio_wbs_accounts', 'accounts_with_final_qty', 'actual_cost_lines_dated', 'actual_cost_first_date', 'actual_cost_last_date', 'activity_actual_start_finish_fields'])}
{h_table(pc_rows, ['field', 'thiele2020_D4', 'dslib_D6', 'cambridge_D7', 'restage_ifc_D5'])}</section>
<section id="ml"><h2>Supervised-learning eligibility</h2>
<p>No dataset provides, for the same activity, a verified actual duration and the quantity, productivity and crew inputs needed for an engineering duration. The target <code>y = log(actual/engineering)</code> cannot be computed without merging unrelated sources, which this stage forbids.</p>
<div class="callout">Leakage: Thiele <code>Final Qty</code>, <code>Final Cost</code>, <code>Final Rate</code>, monthly AQ/AC/EV and <code>%C</code> claims are post-execution and must never be features.</div>
<p>Details: <code>training_data_gap_analysis.md</code>.</p></section>
<section id="limits"><h2>Stage 4.0A limitation resolution</h2>{h_table([dict(stage4_0a_limitation=a, resolution=b, evidence=c) for a, b, c in LIM], ['stage4_0a_limitation', 'resolution', 'evidence'])}</section>
<section id="manual"><h2>Manual actions required</h2>
<ol><li><b>BEDEC</b> (Catalonia prices, environmental indicators): student or paid licence, then BC3 export to <code>data/raw/candidates/productivity/bedec/</code> and <code>.../environmental/bedec/</code>.</li>
<li><b>CYPE</b>: registration, Barcelona province, BC3 export to <code>data/raw/candidates/productivity/cype/</code>. Clear the licence first.</li>
<li><b>EC3</b>: fee-waiver application and written permission before storing data in <code>data/raw/candidates/environmental/ec3/</code>.</li>
<li><b>BCCA inner RAR</b>: extract with 7-Zip into a new folder.</li></ol>
<p>Step-by-step: <code>manual_download_required.md</code>.</p></section>
<section id="next"><h2>Recommended next steps</h2><ol>
<li>Consolidate with Section A once it finishes.</li><li>Define the PMI user-input schema (crew per trade, hours per day, calendar, adjustment factors, curing and striking times) before Stage 5.3.</li>
<li>Audit IFC quantity extraction on several independent IFCs (Section A) before Stage 5.1 is unconditional.</li><li>Keep Stage 5.6 closed until linked RC records with actual activity dates exist.</li></ol></section>
<section id="preservation"><h2>Preservation verification</h2>
<p>All protected files unchanged: <b>{'yes' if pres['all_protected_unchanged'] else 'NO - see JSON'}</b>.</p>
{h_table([dict(check=c['check'], total=c.get('total', c.get('files_checked', '')), unchanged=c.get('unchanged', ''), issues=len(c.get('changed', []) or []) + len(c.get('missing', []) or []) + len(c.get('changed_or_missing', []) or []) + len(c.get('tracked_modifications', []) or []) + int(c.get('failures', 0) or 0)) for c in pres['checks']], ['check', 'total', 'unchanged', 'issues'])}
<h3>Recorded discrepancies</h3><ul>{''.join(f'<li>{E(d)}</li>' for d in pres['discrepancies'])}</ul></section>
"""
page = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stage 4.0B Evidence Audit</title><style>{css}</style></head><body><div class="layout"><nav><div class="sub" style="padding:0 8px 8px">Stage 4.0B</div>{nav}</nav><main>{body}</main></div></body></html>'
open(f'{OUT}/stage4_0b_report.html', 'w', encoding='utf-8').write(page)
print('wrote html', len(page))
