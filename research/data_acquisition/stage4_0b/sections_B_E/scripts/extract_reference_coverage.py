"""Stage 4.0B - build productivity / cost / environmental reference coverage tables.

Read-only on data/raw. Writes inspection tables under data/processed/candidates/stage4_0b/
and coverage CSVs under research/data_acquisition/stage4_0b/.

Run from the repository root:
    .venv/Scripts/python.exe -I research/data_acquisition/stage4_0b/sections_B_E/scripts/extract_reference_coverage.py

No values are invented: every number is copied or recomputed from the source rows
named in the output, and the transformation is written next to it.
The choice of one representative BCCA code per target work item is an auditor's
selection that a PMI user must review and approve; alternatives are listed.
"""
import csv, json, os, re, sys
from collections import Counter, defaultdict

ROOT = os.getcwd()
P_BCCA = 'data/processed/candidates/stage4_0b/bcca2023'
OUT_PROC = 'data/processed/candidates/stage4_0b'
OUT_REP = 'research/data_acquisition/stage4_0b/sections_B_E'
CERP_DIR = 'data/raw/candidates/productivity/cerp/extracted/cerp-items-data-9db4fc929c15647431615d2fbf5a53b3ef4f9c3b'
OBD_CSV = 'data/raw/candidates/environmental/oekobaudat/original/OBD_2024_III_exportCSV.csv'
BCCA_URL = 'https://www.juntadeandalucia.es/sites/default/files/inline-files/2024/01/BCCA2023_V02.zip'
BCCA_LIC = 'Junta de Andalucia portal reuse terms (CC BY 3.0-type; attribution "Informacion obtenida del Portal de la Junta de Andalucia")'
BCCA_FILE = 'data/raw/candidates/productivity/bcca_andalucia/extracted/BCCA2023_V02/BCCA2023_V02.bc3'

sys.stdout.reconfigure(encoding='utf-8')


def rd(p):
    with open(p, encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def wr(p, rows, cols=None):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    cols = cols or list(dict.fromkeys(k for r in rows for k in r))
    with open(p, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print('wrote', p, len(rows))


C = {r['code']: r for r in rd(f'{P_BCCA}/bcca2023_concepts.csv')}
T = {r['code']: r['text'] for r in rd(f'{P_BCCA}/bcca2023_texts.csv')}
D = defaultdict(list)
for r in rd(f'{P_BCCA}/bcca2023_decompositions.csv'):
    D[r['parent']].append(r)


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def expand(code, mult=1.0, depth=0, path=''):
    """Yield leaf resource lines with quantity per 1 unit of `code`."""
    for d in D.get(code, []):
        ch = d['child']
        q = mult * (f(d['factor']) or 1.0) * (f(d['yield_per_unit']) or 0.0)
        c = C.get(ch, {})
        if c.get('bc3_type') == '0' and ch in D and depth < 6:
            yield from expand(ch, q, depth + 1, path + ch + '>')
        else:
            yield dict(child=ch, qty=q, via=path.rstrip('>'), unit=c.get('unit', ''),
                       type=c.get('bc3_type_label', 'unknown'), price=f(c.get('price')),
                       summary=c.get('summary', ''))


# ---- target work items (Section B 4). Representative code = auditor selection, must be approved.
TARGETS = [
    ('T01', 'Mechanical excavation', 'm3', ['02AVV00002', '02PMM00002'], ['02AVV00001', '02AVV00003', '02PMM00001']),
    ('T02', 'Blinding concrete', 'm3', ['03WSS80000'], ['03WSS80020']),
    ('T03', 'Foundation reinforcement', 'kg', ['03ACC00011'], ['03ACC00010']),
    ('T04', 'Foundation formwork', 'm2', ['03ERM00001'], ['03ERT00001', '03EPF00001']),
    ('T05', 'Foundation concreting', 'm3', ['03HAZ80020', '03HAA00010'], ['03HAZ00002', '03HAL00006']),
    ('T06', 'Column reinforcement', 'kg', ['05HAC00015'], ['05HAC00010']),
    ('T07', 'Column formwork', 'm2', ['05HEM00001'], ['05HET00001', '05HEM00201']),
    ('T08', 'Column concreting', 'm3', ['05HHP00003'], ['05HHP00103']),
    ('T09', 'Beam reinforcement', 'kg', ['05HAC00015'], ['05HAC00010']),
    ('T10', 'Beam formwork', 'm2', ['05HEM00051'], ['05HEM00225']),
    ('T11', 'Beam concreting', 'm3', ['05HHJ00003'], ['05HHJ00103']),
    ('T12', 'Slab reinforcement', 'kg', ['05HAC00015', '05HAM00010'], ['05HAM00011']),
    ('T13', 'Slab formwork', 'm2', ['05HEM00101'], ['05HEM80010']),
    ('T14', 'Slab concreting', 'm3', ['05HHL00003'], ['05HHL00103']),
    ('T15', 'Formwork removal', 'm2', ['05HED00001'], ['05HED00051', '05HED00101']),
    ('T16', 'Concrete curing', 'time + technical conditions', [], []),
    ('T17', 'Backfilling', 'm3', ['02RRM00001'], ['02RRB00001']),
    ('T18', 'Masonry installation', 'm2', ['06LHM00005', '06BHH00020'], ['06LHM00001', '06BHA00110']),
]

# ---- CERP cross-check index (same BCCA edition re-published; NOT independent evidence)
cerp_by_code = {}
cat = json.load(open(f'{CERP_DIR}/catalog.json', encoding='utf-8'))
for it in (cat['items'] if isinstance(cat, dict) else cat):
    for s in it.get('sources', []):
        if s.get('source') == 'bcca':
            cerp_by_code.setdefault(s['code'], it)
basic_ids = {}
for it in (cat['items'] if isinstance(cat, dict) else cat):
    basic_ids[it['id']] = it

prod_rows, cost_rows, line_rows = [], [], []
for tid, name, tunit, codes, alts in TARGETS:
    if not codes:
        # curing: search the source for any stand-alone item and report what the texts say
        bundled = [k for k, v in T.items() if re.search(r'curado', v, re.I) and C.get(k, {}).get('unit') == 'm3']
        prod_rows.append(dict(target_id=tid, work_item=name, required_unit=tunit, source='BCCA 2023 V02 (Junta de Andalucia)',
                              source_code='', status='No stand-alone work item',
                              evidence=f'{len(bundled)} m3 concreting items state "incluso ... vibrado y curado" in their specification text (curing bundled into concreting labour). No curing duration, strength-gain or striking-time value is given.',
                              productivity_category='none', labour_h_per_unit_total='', source_url=BCCA_URL, licence=BCCA_LIC))
        cost_rows.append(dict(target_id=tid, work_item=name, status='No stand-alone cost item; bundled in concreting', source_url=BCCA_URL))
        continue
    for code in codes:
        c = C[code]
        top = D.get(code, [])
        top_sum = sum((f(d['factor']) or 1) * (f(d['yield_per_unit']) or 0) * (f(C.get(d['child'], {}).get('price')) or 0) for d in top)
        leaves = list(expand(code))
        lab = defaultdict(float)
        lab_rate = {}
        mach_h, mach_other, mat_lines = defaultdict(float), [], []
        for L in leaves:
            line_rows.append(dict(target_id=tid, work_item=name, bcca_code=code, child_code=L['child'], via_auxiliary=L['via'],
                                  resource_type=L['type'], resource_unit=L['unit'], qty_per_unit_of_parent=round(L['qty'], 6),
                                  resource_price_eur=L['price'], resource_summary=L['summary'],
                                  transformation='qty = product of factor x yield along BC3 ~D path (auxiliaries expanded)',
                                  source_file='BCCA2023_V02.bc3'))
            if L['type'] == 'labor' and L['unit'] == 'h':
                lab[L['summary']] += L['qty']
                lab_rate[L['summary']] = L['price']
            elif L['type'] == 'machinery':
                if L['unit'] == 'h':
                    mach_h[L['summary']] += L['qty']
                else:
                    mach_other.append(f"{L['summary']} {round(L['qty'],4)} {L['unit']}")
            elif L['type'] == 'material':
                mat_lines.append(f"{L['summary']} {round(L['qty'],4)} {L['unit']} @ {L['price']}")
        labour_total = sum(lab.values())
        cerp = cerp_by_code.get(code)
        cerp_lab = None
        if cerp:
            cerp_lab = sum(b['quantity'] * b.get('factor', 1) for b in cerp.get('bom', []) if b.get('role') == 'labor')
        stated = f(c['price'])
        unit_match = (c['unit'] == tunit)
        note = ''
        if tid == 'T02':
            note = 'BCCA measures blinding per m2 at 10 cm minimum thickness; target unit is m3. Not converted (thickness is a minimum, not a fixed value).'
        if tid in ('T06', 'T09', 'T12') and code == '05HAC00015':
            note = 'Generic structural rebar item; BCCA does not distinguish column/beam/slab reinforcement productivity.'
        if tid == 'T15':
            note = 'Separate stripping item exists; BCCA formwork items (05HEM*) also include formwork work; check for double counting before use.'
        if tid == 'T01' and code == '02PMM00002' and code not in C:
            note = 'code not present'
        prod_rows.append(dict(
            target_id=tid, work_item=name, required_unit=tunit, source='BCCA 2023 V02 (Junta de Andalucia)', source_code=code,
            description=c['summary'], specification_text=T.get(code, '')[:400], source_unit=c['unit'], unit_matches_target=unit_match,
            status='Catalogue reference found',
            productivity_category='Estimated catalogue productivity: person-hours and equipment-hours per physical unit (not observed field productivity)',
            labour_h_per_unit_total=round(labour_total, 6),
            labour_h_per_unit_by_trade='; '.join(f'{k}={round(v,6)}' for k, v in lab.items()),
            labour_rates_eur_per_h='; '.join(f'{k}={v}' for k, v in lab_rate.items()),
            equipment_h_per_unit='; '.join(f'{k}={round(v,6)}' for k, v in mach_h.items()) or 'none',
            equipment_non_hour_lines='; '.join(mach_other) or 'none',
            crew_composition_in_source='not specified (individual trades listed; crew size and simultaneity not given)',
            alternatives_in_source='|'.join(alts),
            cerp_crosscheck_labour_h=cerp_lab if cerp_lab is not None else 'not found',
            cerp_crosscheck_note='CERP v0.11.0 republishes the same BCCA edition 2024-01; agreement is a consistency check, not independent evidence',
            geography='Andalucia, Spain (not Catalonia/Barcelona)', currency='EUR',
            reference_date_concept_ddmmyy=c['price_date_ddmmyy'],
            notes=note, source_url=BCCA_URL, source_file=BCCA_FILE, licence=BCCA_LIC))
        cost_rows.append(dict(
            target_id=tid, work_item=name, source_code=code, description=c['summary'], source_unit=c['unit'],
            stated_direct_unit_cost_eur=stated, recomputed_from_top_level_lines_eur=round(top_sum, 4),
            recompute_difference_eur=round((stated or 0) - top_sum, 4),
            material_lines='; '.join(mat_lines)[:900],
            cost_category='Reference unit price (catalogue, direct cost; excludes overheads, general expenses, industrial profit, VAT)',
            currency='EUR', geography='Andalucia, Spain', reference_date_concept_ddmmyy=c['price_date_ddmmyy'],
            edition='BCCA Dic-2023 V02 (file dated 2023-11-01, published 2024-01)', source_url=BCCA_URL, licence=BCCA_LIC,
            status='Downloaded; recomputed'))

wr(f'{OUT_PROC}/bcca2023/bcca2023_target_item_resource_lines.csv', line_rows)

# append CYPE / BEDEC status rows (not downloaded)
for src, st, why in [
    ('CYPE Generador de Precios', 'Manual download required / licence restricts reuse',
     'Item pages publicly show breakdowns incl. labour h per unit (e.g. EHS010 composite m3 column item); BC3 export needs login; legal notice limits copies to personal non-commercial use without transfer to third parties.'),
    ('ITeC BEDEC', 'Restricted (subscription) / Manual',
     'Subscription product; free trial 15 queries/month after registration; free student licence via ITeC school agreements. Catalonia-specific prices would satisfy the Barcelona priority.')]:
    prod_rows.append(dict(target_id='ALL', work_item='all targets', source=src, status=st, evidence=why, productivity_category='not acquired'))
    cost_rows.append(dict(target_id='ALL', work_item='all targets', source_code='', description=src, status=st, material_lines=why))

wr(f'{OUT_REP}/productivity_reference_coverage.csv', prod_rows)
wr(f'{OUT_REP}/cost_reference_coverage.csv', cost_rows)

# ---- Environmental (OKOBAUDAT 2024-III) ----
with open(OBD_CSV, encoding='iso-8859-1', newline='') as fh:
    obd = list(csv.DictReader(fh, delimiter=';'))
by_uuid = defaultdict(list)
for r in obd:
    by_uuid[r['UUID']].append(r)

ENV_TARGETS = [
    ('E01', 'Ready-mixed concrete by strength class', r"Ready mixed concrete", None),
    ('E02', 'Reinforcement steel (bar)', r"Steel reinforcing bar", None),
    ('E03', 'Reinforcement steel (mesh)', r"Steel reinforcement mesh", None),
    ('E04', 'Structural steel', r"Structural steel profile", None),
    ('E05', 'Timber formwork (solid/structural timber)', r"'Solid wood' / '(Structural timber|Solid structural timber)", None),
    ('E06', 'Plywood / multi-ply formwork panels', r"'(Plywood|3- and 5-ply wood)'", None),
    # 'schal' alone matched Schall/Schale/Schalter (11 false positives) -> word-anchored rule
    ('E07', 'Reusable formwork systems', None, r"\bschalung|\bformwork"),
    ('E08', 'Construction-site processes (excavation, concrete pumping)', r"'Processes at building site'", None),
    ('E09', 'Material transportation (truck t*km)', r"Transport of goods \[t km\]' / 'Truck", None),
    ('E10', 'Construction electricity', r"Energy carrier - delivery free user' / 'Electricity", None),
    # 'diesel' alone only matched passenger cars (PKW Diesel EURO 3/4) -> fuel-specific rule
    ('E11', 'Diesel consumption (fuel)', None, r"dieselkraftstoff|diesel fuel"),
    ('E12', 'Construction waste (end of life)', r"End of Life' / 'Generic' / 'Construction waste", None),
    ('E13', 'Masonry mortar', r"Mortar \(masonry\)", None),
]
env_rows, env_detail = [], []
for eid, label, cat_re, name_re in ENV_TARGETS:
    hits = []
    for u, rs in by_uuid.items():
        r0 = rs[0]
        if cat_re and re.search(cat_re, r0['Kategorie (en)']):
            hits.append(u)
        elif name_re and re.search(name_re, (r0['Name (en)'] + ' ' + r0['Name (de)']), re.I):
            hits.append(u)
    mods = Counter(r['Modul'] for u in hits for r in by_uuid[u])
    units = Counter(f"{by_uuid[u][0]['Bezugsgroesse']} {by_uuid[u][0]['Bezugseinheit']}" for u in hits)
    std = Counter('A2' if 'A2' in by_uuid[u][0]['Konformitaet'] else ('A1' if 'A1' in by_uuid[u][0]['Konformitaet'] else 'other') for u in hits)
    geo = Counter(by_uuid[u][0]['Laenderkennung'] for u in hits)
    typ = Counter(by_uuid[u][0]['Typ'] for u in hits)
    gwp_a2 = sum(1 for u in hits for r in by_uuid[u] if r['Modul'] == 'A1-A3' and r['GWPtotal (A2)'].strip())
    gwp_a1 = sum(1 for u in hits for r in by_uuid[u] if r['Modul'] == 'A1-A3' and r['GWP'].strip())
    years = sorted({by_uuid[u][0]['Referenzjahr'] for u in hits if by_uuid[u][0]['Referenzjahr']})
    valid = sorted({by_uuid[u][0]['Gueltig bis'] for u in hits if by_uuid[u][0]['Gueltig bis']})
    env_rows.append(dict(
        target_id=eid, material_or_process=label, source='OEKOBAUDAT release 2024-III (data stock bca3670a-8dcf-44d0-be1f-0633d9ba1a75)',
        selection_rule=f"category regex: {cat_re}" if cat_re else f"name regex (case-insensitive): {name_re}",
        datasets_found=len(hits), status='Available' if hits else 'Not found in release',
        declared_units='; '.join(f'{k} ({v})' for k, v in units.most_common(6)),
        lifecycle_modules_rows='; '.join(f'{k}={v}' for k, v in sorted(mods.items())),
        datasets_with_A1A3_GWPtotal_EN15804A2=gwp_a2, datasets_with_A1A3_GWP_EN15804A1=gwp_a1,
        standard_split='; '.join(f'{k}={v}' for k, v in std.items()),
        geography='; '.join(f'{k}={v}' for k, v in geo.most_common(6)),
        dataset_types='; '.join(f'{k}={v}' for k, v in typ.items()),
        reference_years=f"{years[0]}-{years[-1]}" if years else '', valid_until_range=f"{valid[0]}-{valid[-1]}" if valid else '',
        gwp_unit='kg CO2-eq per declared unit',
        spain_specific=('yes' if any(g in ('ES',) for g in geo) else 'no'),
        licence='BMWSB: free of charge; free distribution of unmodified data permitted with source named',
        source_url='https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/bca3670a-8dcf-44d0-be1f-0633d9ba1a75/exportCSV',
        local_file=OBD_CSV))
    for u in hits:
        for r in by_uuid[u]:
            env_detail.append(dict(target_id=eid, uuid=u, version=r['Version'], name_en=r['Name (en)'], name_de=r['Name (de)'],
                                   category_en=r['Kategorie (en)'], conformity=r['Konformitaet'], geo=r['Laenderkennung'], type=r['Typ'],
                                   ref_year=r['Referenzjahr'], valid_until=r['Gueltig bis'], declared_quantity=r['Bezugsgroesse'],
                                   declared_unit=r['Bezugseinheit'], module=r['Modul'], scenario=r['Szenario'],
                                   GWP_EN15804A1=r['GWP'], GWPtotal_EN15804A2=r['GWPtotal (A2)'], GWPfossil_A2=r['GWPfossil (A2)'],
                                   GWPbiogenic_A2=r['GWPbiogenic (A2)'], conversion_to_1kg=r['Umrechungsfaktor auf 1kg'],
                                   gross_density_kg_m3=r['Rohdichte (kg/m3)'], url=r['URL'],
                                   source_file='OBD_2024_III_exportCSV.csv', transformation='row copied; decimal commas kept as in source'))

for src, st, why in [
    ('BCCA 2023 V02 (BC3 ~X)', 'Schema only - no values', 'Header declares eCO2 (kg), ce (MJ), m (kg), v (m3), LER code; 0 concepts carry ~X values in this file.'),
    ('EC3 / Building Transparency', 'Restricted / Manual', 'API returns HTTP 401 without credentials; free tier forbids caching/redistribution; paid licence or written consent needed.'),
    ('ITeC BEDEC environmental indicators', 'Restricted (subscription)', '5 basic indicators in BEDEC Proyecto y obra; 13 in BEDEC Sostenibilidad; not in free/consulta tier.'),
    ('CYPE Generador de Precios environmental tab', 'Manual / licence restricted', 'Item pages show waste (LER) tables; impact indicators tab described in documentation; personal-use licence.')]:
    env_rows.append(dict(target_id='ALL', material_or_process='all', source=src, status=st, selection_rule=why, datasets_found=0))

wr(f'{OUT_REP}/environmental_reference_coverage.csv', env_rows)
wr(f'{OUT_PROC}/oekobaudat/oekobaudat_2024III_target_records.csv', env_detail)
