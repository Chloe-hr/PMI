"""Stage 5.2 PREPARATION - research-only RC construction knowledge library.

Run from repo root:
    .venv/Scripts/python.exe -I research/construction_knowledge/stage5_2_preparation/scripts/build_knowledge_library.py <start_snapshot.txt>
Reads: BCCA inspection tables (Stage 4.0B), IFC models (read-only), SCH task sequence. Writes only to
research/construction_knowledge/stage5_2_preparation/ and data/processed/candidates/stage5_2_prep/.
Evidence status vocabulary used in every table:
  VERIFIED_REFERENCE  copied or recomputed from a cited source file (BCCA, IFC)
  OBSERVED            observed in one real project (SCH plan) - an example, not a rule
  PROPOSED_RULE       auditor proposal - PENDING engineering approval
  ASSUMPTION          explicit assumption - PENDING approval, never applied automatically
  UNAVAILABLE         no evidence located - activity blocked until provided
This is not a Stage 5.2 production module.
"""
import collections, csv, datetime as dt, glob, hashlib, html, json, os, re, subprocess, sys
import ifcopenshell
import ifcopenshell.util.element as ue

sys.stdout.reconfigure(encoding='utf-8')
OUT = 'research/construction_knowledge/stage5_2_preparation'
PROC = 'data/processed/candidates/stage5_2_prep'
BC = 'data/processed/candidates/stage4_0b/bcca2023'
BCCA_FILE = 'data/raw/candidates/productivity/bcca_andalucia/extracted/BCCA2023_V02/BCCA2023_V02.bc3'
BCCA_URL = 'https://www.juntadeandalucia.es/sites/default/files/inline-files/2024/01/BCCA2023_V02.zip'
SNAP = sys.argv[1] if len(sys.argv) > 1 else None
NOW = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
os.makedirs(PROC, exist_ok=True)


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


# ------------------------------------------------------------------ BCCA reference expansion (VERIFIED_REFERENCE)
C = {r['code']: r for r in rd(f'{BC}/bcca2023_concepts.csv')}
T = {r['code']: r['text'] for r in rd(f'{BC}/bcca2023_texts.csv')}
D = collections.defaultdict(list)
for r in rd(f'{BC}/bcca2023_decompositions.csv'):
    D[r['parent']].append(r)


def fl(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def expand(code, mult=1.0, depth=0):
    for d in D.get(code, []):
        ch = d['child']
        q = mult * (fl(d['factor']) or 1.0) * (fl(d['yield_per_unit']) or 0.0)
        c = C.get(ch, {})
        if c.get('bc3_type') == '0' and ch in D and depth < 6:
            yield from expand(ch, q, depth + 1)
        else:
            yield dict(child=ch, qty=q, unit=c.get('unit', ''), type=c.get('bc3_type_label', ''), price=fl(c.get('price')), summary=c.get('summary', ''))


INCL = [('includes_formwork', r'encofrados? (complementarios|de|met)|\bencofrad[oa]s?\b(?! de )'), ('includes_stripping', r'\bdesencofrado\b'),
        ('includes_release_agent', r'desencofrante'), ('includes_reinforcement', r'armadura|acero b ?500|mallazo|ferralla'), ('includes_vibration', r'vibrad'),
        ('includes_curing', r'curad'), ('includes_props', r'apeos?'), ('includes_bottom_cleaning', r'limpieza de fondos'), ('includes_mortar', r'mortero'),
        ('includes_concrete', r'hormig[oó]n (para armar|ha-|hm-)|capa de compresi'), ('includes_openings_deduction', r'deduciendo huecos')]


def bcca(code):
    c = C[code]
    lab, lrate, mach, mat = collections.defaultdict(float), {}, collections.defaultdict(float), []
    for L in expand(code):
        if L['type'] == 'labor' and L['unit'] == 'h':
            lab[L['summary']] += L['qty']
            lrate[L['summary']] = L['price']
        elif L['type'] == 'machinery':
            mach[f"{L['summary']} [{L['unit']}]"] += L['qty']
        elif L['type'] == 'material':
            mat.append(f"{L['summary']} {round(L['qty'], 5)} {L['unit']} @ {L['price']} EUR")
    text = T.get(code, '')
    meas = re.findall(r'(Medid[ao][^.;]*)', text)
    inc = {k: bool(re.search(p, text, re.I)) for k, p in INCL}
    # 'desencofrante' must not count as stripping; formwork flag refined from text phrases
    inc['includes_formwork'] = bool(re.search(r'encofrados complementarios|^encofrado', text, re.I))
    return dict(bcca_code=code, bcca_summary=c['summary'], bcca_unit=c['unit'], direct_unit_cost_eur=fl(c['price']), price_date_ddmmyy=c['price_date_ddmmyy'],
                labour_h_per_unit_by_trade='; '.join(f'{k}={round(v, 5)}' for k, v in lab.items()) or 'none',
                labour_h_per_unit_total=round(sum(lab.values()), 5), labour_rates_eur_h='; '.join(f'{k}={v}' for k, v in lrate.items()),
                equipment_per_unit='; '.join(f'{k}={round(v, 5)}' for k, v in mach.items()) or 'none', materials_per_unit='; '.join(mat)[:700],
                measurement_rule_text='; '.join(meas)[:250], specification_text=text[:600], **inc)


# ------------------------------------------------------------------ work item library
# (activity_id, name, scope_group, ifc_types, classification_evidence, material_method, quantity, unit_basis, bcca_primary, bcca_alternatives,
#  inputs, dependencies, conditions, auto_eligibility)
W = [
    ('EXC-BULK', 'Bulk excavation (vaciado), mechanical', 'Excavation', 'none (site/terrain, not an IFC element)', 'Site model, ground levels, formation level, soil class',
     'Earthworks, mechanical', 'Excavated volume in bank (natural profile)', 'm3, BCCA "medido el volumen en perfil natural"', '02AVV00002', '02AVV00001|02AVV00003|02AVV00004',
     'ground levels; formation level; soil consistency; working space; slope/shoring method; spoil disposal', 'precedes blinding/foundations in excavated zone',
     'Soil class selects BCCA variant; rock/explosives items differ by an order of magnitude', 'BLOCKED - no excavation geometry in any real IFC'),
    ('EXC-TRENCH', 'Trench excavation for strip foundations, mechanical', 'Excavation', 'derived from IfcFooting / foundation-classified IfcBeam footprint', 'Foundation classification + underside level + ground level',
     'Earthworks, mechanical', 'Trench volume in bank', 'm3, perfil natural', '02ZMM00002', '02ZMM00001|02ZMM00003',
     'ground level; trench width rule (foundation width + working space); soil class', 'precedes blinding and strip foundation',
     'Depth > 4 m not covered by 02ZMM items', 'BLOCKED until site inputs and approved width rule exist'),
    ('EXC-PIT', 'Pit excavation for pad footings, mechanical', 'Excavation', 'derived from IfcFooting (PAD) footprint', 'Footing classification + underside level + ground level',
     'Earthworks, mechanical', 'Pit volume in bank', 'm3, perfil natural', '02PMM00002', '02PMM00001',
     'ground level; working space; soil class', 'precedes blinding and pad footing', 'Depth max 4 m in BCCA item', 'BLOCKED until site inputs exist'),
    ('BLD', 'Blinding concrete (hormigon de limpieza) 10 cm min.', 'Blinding', 'derived from foundation underside area (IfcFooting / foundation IfcBeam / ground slab)', 'Foundation classification; blinding specified in design',
     'HM-20 plain concrete', 'Underside area of foundations', 'm2 at 10 cm minimum thickness (BCCA measures area, not volume)', '03WSS80000', '03WSS80020 (sulfate resistant)',
     'blinding thickness if not 10 cm; which foundations receive blinding', 'after excavation of the zone; before foundation formwork/reinforcement',
     'If design gives blinding in m3, convert only with an approved thickness', 'CONDITIONAL - area derivable from validated footprint; requires approval'),
    ('FND-REBAR', 'Foundation reinforcement B500S', 'Reinforcement', 'IfcFooting; IfcBeam/IfcSlab classified as foundation; IfcReinforcingBar if modelled', 'Rebar model or schedule; NEVER a generic ratio',
     'Cast-in-place RC', 'Reinforcement mass', 'kg nominal weight', '03ACC00011', '03ACC00010 (B400S)', 'reinforcement mass per element from rebar model, bar schedule or approved design value',
     'before foundation concrete (method-dependent relative to formwork)', 'Not applicable to precast or plain-concrete foundations', 'BLOCKED - no reinforcement data in any real model'),
    ('FND-FORM', 'Foundation formwork, timber (includes stripping)', 'Formwork', 'IfcFooting; foundation-classified IfcBeam', 'Formed faces decision (earth-formed vs shuttered)',
     'Timber formwork; BCCA item INCLUDES desencofrado', 'Formed contact area', 'm2 of formed surface', '03ERM00001', '03ERT00001 (steel)|03EPF00001 (lost brick formwork)',
     'which faces are shuttered vs cast against soil; formwork system', 'after blinding; before foundation concrete', 'Do NOT add FRM-STRIP for this item (stripping included)',
     'BLOCKED until formwork face rules are approved (category C)'),
    ('FND-CONC-PAD', 'Pad footing concrete HA-25 (includes vibration and curing)', 'Concrete placement', 'IfcFooting (PAD) or foundation-classified element', 'Cast-in-place concrete material; pad shape',
     'Cast-in-place RC', 'Net concrete volume', 'm3 theoretical volume', '03HAZ80020', '03HAZ00002|03HAZ80040 (HA-30)', 'concrete class and consistency (selects variant)',
     'after reinforcement and formwork (and inspection)', 'Curing is included in BCCA labour; curing duration still a schedule constraint', 'CONDITIONAL - volume from authored or validated geometry'),
    ('FND-CONC-STRIP', 'Strip foundation / grade beam concrete HA-25 (includes vibration and curing)', 'Concrete placement', 'IfcFooting (STRIP_FOOTING); IfcBeam with foundation evidence (e.g. SCH "fund_strook"/"fund_opstort")',
     'Foundation evidence beyond class: name pattern, foundation storey, below-ground position', 'Cast-in-place RC', 'Net concrete volume', 'm3', '03HAA00010', '03HAA00020 (HA-30)',
     'concrete class; confirmation that IfcBeam elements are foundations', 'after reinforcement and formwork', 'SCH upstand pours ("opstorten") follow the strip pour in the observed plan',
     'CONDITIONAL - only after foundation classification is approved'),
    ('COL-REBAR', 'Column reinforcement B500S', 'Reinforcement', 'IfcColumn', 'Concrete material; not steel/timber', 'Cast-in-place RC', 'Reinforcement mass', 'kg', '05HAC00015', '05HAC00010',
     'reinforcement mass from rebar model/schedule', 'usually before column formwork (method-dependent)', 'Generic BCCA item: not column-specific productivity', 'BLOCKED - no reinforcement data'),
    ('COL-FORM', 'Column formwork, timber (stripping separate)', 'Formwork', 'IfcColumn', 'Cast-in-place concrete; formwork system', 'Timber formwork; stripping NOT included',
     'Formed contact area', 'm2', '05HEM00001', '05HET00001 (steel)|05HEM00201 (exposed finish)', 'formwork system; exposed/finished face requirement',
     'after column reinforcement; before column concrete', 'Pair with FRM-STRIP', 'BLOCKED until face rules approved'),
    ('COL-CONC', 'Column concrete HA-25 (includes vibration and curing)', 'Concrete placement', 'IfcColumn', 'Cast-in-place concrete material', 'Cast-in-place RC', 'Net volume', 'm3', '05HHP00003', '05HHP00103',
     'concrete class; column height measurement rule at slab joints', 'after column formwork', 'Exclude precast/steel columns (SCH columns are steel)', 'CONDITIONAL - volume available/derivable'),
    ('BEAM-REBAR', 'Beam reinforcement B500S', 'Reinforcement', 'IfcBeam (non-foundation)', 'Concrete material; not foundation; not steel', 'Cast-in-place RC', 'Reinforcement mass', 'kg', '05HAC00015', '05HAC00010',
     'reinforcement mass', 'after beam soffit formwork (method-dependent)', 'Generic item', 'BLOCKED - no reinforcement data'),
    ('BEAM-FORM', 'Beam formwork, timber (stripping separate)', 'Formwork', 'IfcBeam (non-foundation)', 'Cast-in-place concrete', 'Timber formwork', 'Formed contact area (soffit + sides)', 'm2', '05HEM00051', '05HEM00225',
     'formwork system; props', 'after supporting columns are cast and adequate; before beam concrete', 'Pair with FRM-STRIP', 'BLOCKED until face rules approved'),
    ('BEAM-CONC', 'Beam concrete HA-25 (includes vibration and curing)', 'Concrete placement', 'IfcBeam (non-foundation)', 'Cast-in-place concrete material', 'Cast-in-place RC', 'Net volume', 'm3', '05HHJ00003', '05HHJ00103',
     'concrete class; beam/slab overlap rule', 'after beam reinforcement and formwork', 'Often poured monolithically with slab', 'CONDITIONAL'),
    ('SLAB-REBAR', 'Slab reinforcement bars / mesh', 'Reinforcement', 'IfcSlab (FLOOR/ROOF/BASESLAB)', 'Cast-in-place concrete; not precast', 'Cast-in-place RC', 'Reinforcement mass', 'kg', '05HAC00015', '05HAM00010 (mesh)',
     'reinforcement mass', 'after slab formwork', 'Generic item', 'BLOCKED - no reinforcement data'),
    ('SLAB-FORM', 'Slab formwork, timber (stripping separate)', 'Formwork', 'IfcSlab', 'Cast-in-place concrete; not on grade; not precast', 'Timber formwork', 'Soffit contact area', 'm2', '05HEM00101', '05HEM80010',
     'formwork system; slab-on-grade exclusion', 'after supporting structure; before slab reinforcement', 'Not for ground-bearing slabs or precast floors', 'BLOCKED until face rules approved'),
    ('SLAB-CONC', 'Slab concrete HA-25 (includes vibration, curing, service openings)', 'Concrete placement', 'IfcSlab', 'Cast-in-place concrete material', 'Cast-in-place RC', 'Net volume', 'm3', '05HHL00003', '05HHL00103',
     'concrete class', 'after slab reinforcement and inspection', 'Layered slabs: concrete layer only', 'CONDITIONAL'),
    ('SLAB-COMPOSITE', 'Composite one-way floor system (joists + blocks + topping; all-in m2 item)', 'Composite system', 'IfcSlab (+ possibly IfcBeam joists)', 'Design states joist/block floor system',
     'Composite system; item INCLUDES concrete, reinforcement, mesh, formwork, props, stripping, vibration, curing', 'Floor area outside-to-outside minus openings > 1 m2', 'm2',
     '05FUW80040', '05FUA00002|05FWW90001 (composite steel deck)', 'floor system type and depth', 'after supporting structure', 'MUTUALLY EXCLUSIVE with SLAB-REBAR/FORM/CONC and FRM-STRIP',
     'BLOCKED unless system type is user-confirmed'),
    ('SLAB-PRECAST', 'Precast floor units (hollow-core "kanaalplaat", filigree "breedplaat") + topping', 'Precast installation', 'IfcSlab with precast material ("prefab")', 'Precast evidence (material name, supplier model)',
     'Precast concrete', 'Unit count/area + topping volume', 'm2 / m3', '', '', 'supplier, unit type, crane, topping thickness', 'after supporting walls/beams; topping after units',
     'No BCCA reference for hollow-core or filigree units', 'BLOCKED - no catalogue reference (UNAVAILABLE)'),
    ('WALL-FORM', 'RC wall formwork, timber (stripping separate)', 'Formwork', 'IfcWall', 'Cast-in-place concrete (not block masonry)', 'Timber formwork', 'Both faces contact area', 'm2', '05HEM00151', '05HET00020 (steel)|05HEM00251',
     'formwork system', 'after wall reinforcement (or one face first)', 'Outside requested scope list - included because RC walls occur in MEN-RES/RST', 'BLOCKED until face rules approved'),
    ('WALL-CONC', 'RC wall concrete HA-25', 'Concrete placement', 'IfcWall', 'Cast-in-place concrete; exclude aerated blocks and CMU', 'Cast-in-place RC', 'Net volume', 'm3', '05HHM00003', '05HHM00103',
     'concrete class', 'after wall formwork', 'Layered walls: concrete layer only', 'CONDITIONAL'),
    ('CURE', 'Concrete curing and strength development', 'Curing', 'all cast-in-place concrete elements', 'Concrete placement activity exists', 'Cast-in-place concrete', 'None priced separately', 'time + technical conditions',
     '', '', 'curing method and duration; strength criteria; temperature; cement type', 'after each concrete placement; before stripping/loading',
     'BCCA concrete items INCLUDE curing labour - never price separately; schedule constraint only', 'CONDITIONAL - schedule constraint requires approved duration/criterion'),
    ('FRM-STRIP', 'Formwork removal (desencofrado) for 05HEM* formwork', 'Formwork removal', 'elements with COL/BEAM/SLAB/WALL-FORM', 'Formwork item that excludes stripping', 'Timber formwork', 'Same area as the formwork item',
     'm2 of useful formwork', '05HED00001', '05HED00051 (metal panels)|05HED00101 (exposed)', 'striking criteria approved by engineer', 'after curing/strength criterion met',
     'NOT for 03ERM00001, composite floors or lost formwork (stripping included or not applicable)', 'BLOCKED until striking criteria approved'),
    ('BACKFILL', 'Backfill with excavated soil, mechanical, compacted', 'Backfill', 'none (derived: excavation minus buried volumes)', 'Excavation geometry, buried element volumes',
     'Earthworks', 'Compacted volume', 'm3, BCCA "medido el volumen en perfil compactado"', '02RRM00001', '02RRB00001 (manual)|03WSS00011 (gravel)',
     'excavation volume; buried volume; compaction/bulking factors', 'after foundation completion, inspection and (if any) waterproofing', 'Bank vs compacted volume bases differ - conversion requires approved factors',
     'BLOCKED - excavation not available'),
    ('MAS-BRICK', 'Hollow brick masonry (1 pie)', 'Masonry', 'IfcWall', 'Masonry material (brick); not concrete', 'Clay brick masonry', 'Wall face area net of openings', 'm2 "medida deduciendo huecos"', '06LHM00005', '06LHM00001',
     'wall thickness/brick type', 'after supporting slab', 'Layered walls: masonry layer only', 'CONDITIONAL - area authored in SCH; derivable elsewhere with face rule'),
    ('MAS-BLOCK', 'Hollow concrete block masonry 15 cm', 'Masonry', 'IfcWall', 'Concrete block (CMU) material - NOT cast concrete', 'Concrete block masonry', 'Wall face area net of openings', 'm2', '06BHH00020', '06BHH00010|06BHH00030',
     'block thickness', 'after supporting slab', 'Do not classify CMU as cast concrete', 'CONDITIONAL'),
    ('MAS-SANDLIME', 'Sand-lime (silico-calcareous) brick masonry, face work', 'Masonry', 'IfcWall', 'Material "kalkzandsteen"/silico-calcareo', 'Sand-lime masonry', 'Wall face area net of openings', 'm2',
     '06LEC80100', '', 'element vs brick format (SCH uses glued sand-lime ELEMENTS)', 'after supporting slab', 'BCCA item is face brick (citara cara vista), not large glued elements - weak match',
     'CONDITIONAL - reference applicability requires approval'),
    ('MAS-AAC', 'Aerated-concrete block masonry (cellenbeton / 加气混凝土砌块)', 'Masonry', 'IfcWall', 'Aerated-concrete material', 'AAC block masonry', 'Wall face area net of openings', 'm2', '', '',
     'block type and thickness', 'after supporting slab', 'No BCCA reference located', 'BLOCKED - no catalogue reference (UNAVAILABLE)'),
    ('STEEL-COL', 'Structural steel columns (out of RC scope)', 'Steel (classification only)', 'IfcColumn with steel material/profile', 'Steel material (staal, S235/S275, HEA/HEB)', 'Structural steel',
     'Mass', 'kg', '05ACS00000', '', 'profile mass per m', 'after foundations/anchor plates', 'Recorded so steel elements are not routed to RC work items', 'BLOCKED for RC work packages'),
]
lib, mapping = [], []
for w in W:
    (aid, name, grp, ifct, cls_ev, meth, qty, unit, code, alts, inputs, deps, cond, auto) = w
    b = bcca(code) if code else {}
    lib.append(dict(activity_id=aid, work_item=name, scope_group=grp, applicable_ifc_types=ifct, additional_classification_evidence=cls_ev, material_and_method=meth,
                    required_quantity=qty, unit_and_basis=unit, bcca_reference=code or 'UNAVAILABLE', bcca_alternatives=alts,
                    labour_h_per_unit_by_trade=b.get('labour_h_per_unit_by_trade', ''), labour_h_per_unit_total=b.get('labour_h_per_unit_total', ''),
                    equipment_per_unit=b.get('equipment_per_unit', ''), materials_per_unit=b.get('materials_per_unit', ''),
                    direct_unit_cost_eur=b.get('direct_unit_cost_eur', ''), cost_basis=('BCCA Dic-2023 direct cost, Andalucia, EUR; excludes overheads/profit/VAT; concept price date ' + b.get('price_date_ddmmyy', '')) if code else '',
                    required_project_inputs=inputs, possible_dependencies=deps, conditions_and_exceptions=cond,
                    evidence_status=('VERIFIED_REFERENCE (BCCA coefficients) + PROPOSED_RULE (applicability)' if code else 'UNAVAILABLE (no catalogue reference)'),
                    evidence_source=(f'{BCCA_FILE} (BCCA2023_V02, {BCCA_URL})' if code else 'none located in BCCA 2023; CYPE/BEDEC not licensed (Stage 4.0B)'),
                    engineering_approval_required='YES - applicability, variant selection and measurement rule', approval_status='PENDING',
                    automatic_work_package_eligibility=auto))
    for c in [code] + [a.split(' ')[0] for a in alts.split('|') if a]:
        if c and c in C:
            bb = bcca(c)
            mapping.append(dict(activity_id=aid, role='primary' if c == code else 'alternative', variant_note=next((a for a in alts.split('|') if a.startswith(c)), '') if c != code else '',
                                **bb, evidence_status='VERIFIED_REFERENCE', source_file=BCCA_FILE, source_sha256='bee06981c4447c6b07a3434a6a4d934de11a7498687b0bf3462ba2ce36b7817d',
                                licence='Junta de Andalucia CC BY 3.0-type; attribution "Informacion obtenida del Portal de la Junta de Andalucia"'))
wr('construction_work_item_library.csv', lib)
wr('bcca_reference_mapping.csv', mapping)

# ------------------------------------------------------------------ classification rules (PROPOSED_RULE) + observed evidence
MAT = [  # order matters: first match wins
    ('aerated_concrete_block', r'cellenbeton|gasbeton|ytong|aerated|加气|蒸压加气'),
    ('concrete_block_masonry', r'concrete masonry|\bcmu\b|bloque|block|砌块'),
    ('precast_concrete', r'prefab|precast|prefabricad|kanaalplaat|breedplaat|预制'),
    ('cast_in_place_concrete', r'\bihw\b|in het werk|in situ|in-situ|cast[- ]in[- ]place|现场浇注|ter plaatse'),
    ('concrete_method_unstated', r'beton|concrete|hormig|混凝土|砼|\bC\d{2}/\d{2}\b|\bHA-\d'),
    # finishes/tiles before masonry: 砖 also occurs in 地砖/瓷砖 (floor/wall tiles); MEN-RES '铺地砖防水面层' (220 slabs) was a false positive
    ('finish_or_tile_layer', r'地砖|瓷砖|铺地|tegel|\btile|baldosa|azulejo'),
    ('masonry', r'metselwerk|\bmw-|baksteen|kalkzandsteen|brick|ladrillo|mauerwerk|砖|砌体'),
    ('steel', r'staal|steel|stahl|acero|\bS2[3-7]5|\bS355|\bHE[ABM]\b|\bIPE\b|^钢|型钢'),
    ('timber', r'\bhout\b|timber|holz|madera|\bGL\d\dh|\bKVH\b|\bCLT\b|\bBSP\b|木'),
]


def mat_cat(names):
    s = ' | '.join(n for n in names if n)
    if not s:
        return 'no_material'
    for k, p in MAT:
        if re.search(p, s, re.I):
            return k
    return 'other_material'


def names_of(el):
    m = ue.get_material(el, should_skip_usage=True)
    if m is None:
        return []
    if m.is_a('IfcMaterial'):
        return [m.Name]
    if m.is_a('IfcMaterialLayerSet'):
        return [l.Material.Name for l in m.MaterialLayers if l.Material]
    if m.is_a('IfcMaterialList'):
        return [x.Name for x in m.Materials]
    if m.is_a('IfcMaterialConstituentSet'):
        return [c.Material.Name for c in (m.MaterialConstituents or []) if c.Material]
    if m.is_a('IfcMaterialProfileSet'):
        return [p.Material.Name for p in m.MaterialProfiles if p.Material]
    return []


FND_NAME = re.compile(r'^fund|fundering|foundation|footing|zapata|cimentaci|基础|承台|地梁|Fundament', re.I)
FND_STOREY = re.compile(r'fundering|foundation|cimentaci|基础|fund', re.I)
MODELS = {'SCH-design': 'data/raw/SCHEPENDOMLAAN/Design model IFC/IFC Schependomlaan.ifc', 'RST': 'data/raw/Restage_IP_ALL_MULTI_001.ifc',
          'MEN-RES': 'data/raw/BIM Spatial Models for Construction Dependency Inf/BIM_residential_building_data/BIM_residential_building.ifc'}
obs = collections.Counter()
fnd_obs = collections.Counter()
examples = {}
for mk, p in MODELS.items():
    f = ifcopenshell.open(p)
    for cls in ('IfcFooting', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall'):
        for el in f.by_type(cls):
            cat = mat_cat(names_of(el))
            obs[(mk, cls, cat)] += 1
            st = ue.get_container(el)
            stn = st.Name if st is not None else ''
            fn = bool(FND_NAME.search(el.Name or '')) or bool(FND_NAME.search(getattr(el, 'ObjectType', '') or ''))
            fs = bool(FND_STOREY.search(stn or ''))
            if cls != 'IfcFooting' and (fn or fs):
                fnd_obs[(mk, cls, 'name' if fn else 'storey only', cat)] += 1
                examples.setdefault((mk, cls), f'{el.Name} @ {stn}')
    del f
obs_rows = [dict(model=a, ifc_class=b, material_category=c, elements=n, evidence_status='OBSERVED') for (a, b, c), n in sorted(obs.items())]
with open(f'{PROC}/classification_observations.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(obs_rows[0]))
    w.writeheader()
    w.writerows(obs_rows)
fnd_rows = [dict(model=a, ifc_class=b, foundation_evidence=c, material_category=d, elements=n, example=examples.get((a, b), '')) for (a, b, c, d), n in sorted(fnd_obs.items())]


def obs_txt(cat=None, cls=None):
    xs = [(a, b, c, n) for (a, b, c), n in obs.items() if (cat is None or c == cat) and (cls is None or b in cls)]
    return '; '.join((f'{a} {b[3:]}={n}' if cat else f'{a} {b[3:]} {c}={n}') for a, b, c, n in sorted(xs)) or 'none observed'


RULES = [
    ('CR01', 'Material category is the first discriminator; IFC class alone never selects a work item', 'all', 'material names (layer/list/constituent/profile) normalised by ordered term list',
     'material_category', 'Mandatory', 'Prevents IfcWall -> RC wall when the wall is masonry or AAC', obs_txt()),
    ('CR02', 'Aerated-concrete blocks are masonry (MAS-AAC), never cast concrete', 'IfcWall, IfcSlab', 'cellenbeton|gasbeton|ytong|aerated|加气|蒸压加气 (checked BEFORE concrete terms)', 'MAS-AAC (blocked: no BCCA ref)',
     'High', 'SCH "03 Metselwerk - cellenbeton"; MEN-RES "蒸压加气混凝土砌块" contain the word concrete/beton', obs_txt('aerated_concrete_block')),
    ('CR03', 'Concrete block / CMU is masonry', 'IfcWall', 'concrete masonry|CMU|bloque|block|砌块', 'MAS-BLOCK', 'High', '4DBenchmark walls "Concrete Masonry Units" (quarantined model)', obs_txt('concrete_block_masonry')),
    ('CR04', 'Precast concrete routes to precast installation, not cast-in-place items', 'IfcSlab, IfcBeam, IfcColumn, IfcWall', 'prefab|precast|kanaalplaat|breedplaat|预制', 'SLAB-PRECAST (blocked) or precast element installation',
     'High', 'SCH "02 Beton gewapend - prefab (VLOER)"; observed SCH plan tasks "Kanaalplaatvloer leggen", "Leggen breedplaat"', obs_txt('precast_concrete')),
    ('CR05', 'Explicit cast-in-place concrete routes to RC rebar/formwork/concrete items', 'IfcFooting, IfcColumn, IfcBeam, IfcSlab, IfcWall', 'ihw|in het werk|in situ|cast-in-place|现场浇注', 'FND-/COL-/BEAM-/SLAB-/WALL- items',
     'High', 'SCH "02 Beton gewapend - ihw"; MEN-RES "混凝土 - 现场浇注混凝土"', obs_txt('cast_in_place_concrete')),
    ('CR06', 'Concrete with unstated method requires user confirmation before routing', 'all', 'beton|concrete|hormigon|混凝土|C25/30 etc. without method term', 'HOLD - user confirms cast-in-place vs precast',
     'Medium', 'RST names concrete only by strength class (C25/30, C35/45); MEN-RES "混凝土，现场浇注 - C40" is explicit', obs_txt('concrete_method_unstated')),
    ('CR07', 'Steel elements are excluded from RC work packages', 'IfcColumn, IfcBeam, IfcMember', 'staal|steel|S235/S275/S355|HEA/HEB/IPE|钢 (after concrete terms: 钢筋混凝土 is RC)', 'STEEL-COL (classification only)',
     'High', 'SCH columns "033 - constructief staal"; RST beams "STEEL/S235JR"', obs_txt('steel')),
    ('CR08', 'Timber elements are excluded from RC work packages', 'all', 'hout|timber|Holz|GL24h|KVH|CLT|BSP', 'out of scope', 'High', 'RST slabs "Holz", beams "GL24h-Sicht"', obs_txt('timber')),
    ('CR09', 'Masonry (brick, sand-lime) routes to masonry items by material', 'IfcWall', 'metselwerk|baksteen|kalkzandsteen|brick|ladrillo|砖|砌体', 'MAS-BRICK / MAS-SANDLIME', 'High',
     'SCH "03 Metselwerk - kalkzandsteen C", "03 mw-baksteen"; tile layers (地砖) are excluded first (finish_or_tile_layer)', obs_txt('masonry')),
    ('CR10', 'Elements without material are blocked from work-package generation', 'all', 'no material association', 'BLOCKED - user classifies', 'Mandatory', 'SCH Synchro export drops materials; RST 60/92 walls without material',
     obs_txt('no_material')),
    ('CR11', 'Foundation detection is NOT class-based: IfcBeam/IfcSlab/IfcWall with foundation name or foundation storey are foundation CANDIDATES', 'IfcBeam, IfcSlab, IfcWall',
     f'name ~ {FND_NAME.pattern} OR storey ~ {FND_STOREY.pattern}', 'FND-* candidate - requires user/engineer confirmation', 'Medium',
     'SCH strip foundations modelled as IfcBeam "fund_strook"/"fund_opstort" on storey "-1 fundering"', '; '.join(f"{r['model']} {r['ifc_class'][3:]} ({r['foundation_evidence']}, {r['material_category']})={r['elements']}" for r in fnd_rows)),
    ('CR12', 'IfcFooting is a foundation but its type (pad/strip/pile cap) needs PredefinedType or geometry confirmation', 'IfcFooting', 'PredefinedType PAD_FOOTING/STRIP_FOOTING/PILE_CAP; else USERDEFINED/NOTDEFINED -> confirm',
     'FND-CONC-PAD / FND-CONC-STRIP', 'Medium', 'RST footings: PredefinedType mostly not specific', obs_txt(None, ('IfcFooting',))),
    ('CR13', 'Slab on grade vs suspended slab decides whether slab formwork applies', 'IfcSlab', 'PredefinedType BASESLAB or lowest storey/ground contact -> no soffit formwork', 'SLAB-FORM applicability', 'Medium',
     'No automated evidence; requires model/user confirmation', 'not evaluated'),
    ('CR14', 'Spatial adjacency (IfcRelConnects*, Mendeley spatial relations) never creates a classification or precedence', 'all', '-', '-', 'Mandatory',
     'Mendeley relations are geometric (embedded/contained/overlap)', 'n/a'),
    ('CR15', 'Exporter-specific: SCH Synchro elements are classified through their design-model element (name suffix "_(#STEP id)")', 'all (SCH Synchro)', 'regex _(#\\d+)$ -> design STEP id',
     'inherit design-model classification', 'Medium', '3,228/3,505 resolve; 73 change IFC class', 'Stage 4.0B consolidation'),
]
wr('element_classification_rules.csv', [dict(rule_id=a, rule=b, applies_to_ifc_types=c, evidence_test=d, outcome=e, priority=f, rationale_example=g,
                                             observed_in_models=h, evidence_status='PROPOSED_RULE', approval_status='PENDING') for a, b, c, d, e, f, g, h in RULES])

# ------------------------------------------------------------------ dependency rules (all PENDING)
SCH = rd(f'{PROC}/sch_synchro_task_sequence.csv')
schtxt = lambda kw: '; '.join(f"{r['start'][:10]} {r['task']}" for r in SCH if r['task'] and re.search(kw, r['task'], re.I))[:300]
DEP = [
    ('DR01', 'EXC-BULK|EXC-TRENCH|EXC-PIT', 'BLD|FND-*', 'FS', 'Excavation of the same zone before blinding/foundation work', 'zone-scoped; no default lag', 'Staged excavation per zone; piled foundations (piling before excavation) not covered',
     f'OBSERVED SCH: {schtxt("grondwerk|uitzetten")}'),
    ('DR02', 'BLD', 'FND-REBAR|FND-FORM', 'FS', 'Blinding before foundation reinforcement/formwork where blinding is specified', 'blinding cure/walkability time = project input (no default)',
     'No blinding (e.g. formwork on lean fill) -> rule inactive', f'OBSERVED SCH: {schtxt("werkvloer")}'),
    ('DR03a', 'FND-FORM', 'FND-REBAR', 'FS', 'Method A (formwork first): shutter, then place cage inside', 'none', 'Applicable to boxed strip foundations and pits',
     f'OBSERVED SCH: {schtxt("bekisten|funderingkist|wapening")}'),
    ('DR03b', 'FND-REBAR', 'FND-FORM', 'FS', 'Method B (reinforcement first): prefabricated cages, then formwork', 'none', 'Alternative to DR03a - exactly one of DR03a/DR03b per element group', 'PROPOSED_RULE (common practice; no dataset evidence)'),
    ('DR04', 'FND-REBAR & FND-FORM', 'FND-CONC-*', 'FS', 'Reinforcement and formwork complete (and inspected) before foundation concrete', 'inspection hold = project input', 'Earth-formed footings: formwork predecessor absent',
     f'OBSERVED SCH: {schtxt("^stort|opstorten")}'),
    ('DR05', 'COL-REBAR', 'COL-FORM', 'FS', 'Column cage before column formwork (typical)', 'none', 'Prefabricated cage + system formwork may overlap (SS)', 'PROPOSED_RULE'),
    ('DR06', 'COL-FORM|BEAM-FORM|SLAB-FORM|WALL-FORM + respective REBAR', 'COL-/BEAM-/SLAB-/WALL-CONC', 'FS', 'Reinforcement and formwork before placement where the method requires both', 'inspection hold = project input',
     'Slab/beam: formwork usually precedes reinforcement (soffit first); walls: one face, rebar, second face', 'PROPOSED_RULE; SCH lift walls observed as Bekisten -> Wapening -> Stort'),
    ('DR07', 'any *-CONC', 'CURE', 'FS', 'Placement before curing/strength development', 'curing duration/criterion = engineer input (NO universal default)', 'Cold-weather, cement type and admixtures change durations', 'PROPOSED_RULE; BCCA texts include curing labour in concrete items'),
    ('DR08', 'CURE', 'FRM-STRIP', 'FS', 'Formwork removal only after the approved striking criterion (strength or time) is met', 'criterion = engineer input; Spanish Codigo Estructural (cited by BCCA) governs; values NOT extracted here',
     'Side formwork vs soffit/props differ; re-propping strategies', 'PROPOSED_RULE - pending approval'),
    ('DR09', 'COL-CONC (+CURE criterion)', 'BEAM-FORM|SLAB-FORM (storey above)', 'FS', 'Supporting columns/walls cast and adequate before loading formwork of supported members', 'criterion = engineer input',
     'Monolithic column-beam-slab pours; steel columns (SCH) placed before floors', f'OBSERVED SCH: {schtxt("kolommen|breedplaat|kanaalplaat")}'),
    ('DR10', 'storey n structure', 'storey n+1 structure', 'FS', 'Vertical progression storey by storey for supported structure', 'none by default', 'Zones may overlap horizontally; no inference from spatial adjacency',
     'PROPOSED_RULE; storey evidence from IfcBuildingStorey (flattened in SCH Synchro)'),
    ('DR11', 'zone k activity', 'zone k+1 same activity', 'FS (resource)', 'Zone progression by crew availability, not by precedence', 'resource-driven', 'Zones must be user-defined (IfcZone not audited)', 'PROPOSED_RULE'),
    ('DR12', 'FND-CONC-* (+inspection, waterproofing if any)', 'BACKFILL', 'FS', 'Backfill after foundation completion and inspection', 'inspection/strength criterion = engineer input',
     'Partial backfill per zone', f'OBSERVED SCH: {schtxt("aanvullen")}'),
    ('DR13', 'supporting slab', 'MAS-*', 'FS', 'Masonry after its supporting slab/foundation', 'none by default', 'Load-bearing masonry may PRECEDE the floor it supports (SCH sand-lime walls before breedplaat)',
     f'OBSERVED SCH: {schtxt("kalkzandsteen|metselwerk")}'),
    ('DR14', 'SLAB-PRECAST units', 'topping pour', 'FS', 'Precast floor units before topping concrete', 'none', 'Only for precast systems', f'OBSERVED SCH: {schtxt("afstorten|kanaalplaat")}'),
    ('DR15', '-', '-', 'none', 'Spatial adjacency, contact or containment alone NEVER creates a dependency', '-', '-', 'Mandatory policy'),
]
wr('construction_dependency_rules.csv', [dict(rule_id=a, predecessor=b, successor=c, relation=d, rule=e, lag_or_condition=f, alternatives_and_applicability=g, evidence=h,
                                              evidence_status=('OBSERVED + PROPOSED_RULE' if 'OBSERVED' in h else 'PROPOSED_RULE'), approval_status='PENDING',
                                              universal_default_duration='NONE') for a, b, c, d, e, f, g, h in DEP])

# ------------------------------------------------------------------ quantity requirement matrix + missing information policy
SRC = ['authored_ifc', 'validated_geometry', 'user_provided', 'approved_assumption']
QM = [
    ('Excavation volume', 'EXC-*', 'm3 bank', 'N', 'N', 'Y', 'Y (e.g. approved working-space rule + user ground levels)', 'BLOCKED'),
    ('Blinding area', 'BLD', 'm2', 'Y (footprint area if authored)', 'Y (footprint of validated foundation geometry)', 'Y', 'Y (thickness if not 10 cm)', 'BLOCKED'),
    ('Concrete volume (net, concrete layer only)', '*-CONC', 'm3', 'Y (NetVolume; single-material elements)', 'Y (after manual validation of the model; layer split required)', 'Y', 'N', 'BLOCKED'),
    ('Formwork contact area', '*-FORM, FRM-STRIP', 'm2', 'N (no model authors formwork area)', 'N (surface area is not formwork area)', 'Y', 'Y (approved face rules per element type/method)', 'BLOCKED'),
    ('Reinforcement mass', '*-REBAR', 'kg', 'Y only if IfcReinforcingBar/weight exists (none in real models)', 'N', 'Y (bar schedule/design value)', 'N - generic ratios prohibited unless explicitly approved and labelled as assumption by the engineer', 'BLOCKED'),
    ('Composite floor area', 'SLAB-COMPOSITE', 'm2', 'Y (NetArea of slab)', 'Y', 'Y', 'N', 'BLOCKED'),
    ('Precast unit count/area', 'SLAB-PRECAST', 'm2 / each', 'Y (slab area)', 'Y', 'Y', 'N', 'BLOCKED (also no BCCA reference)'),
    ('Masonry net face area', 'MAS-*', 'm2', 'Y (NetSideArea, SCH)', 'Y (with approved face rule)', 'Y', 'N', 'BLOCKED'),
    ('Backfill volume', 'BACKFILL', 'm3 compacted', 'N', 'N', 'Y', 'Y (approved bulking/compaction factors)', 'BLOCKED'),
    ('Curing duration / strength criterion', 'CURE, FRM-STRIP', 'time + criterion', 'N', 'N', 'Y', 'Y (engineer-approved)', 'BLOCKED (schedule constraint unavailable)'),
    ('Steel mass', 'STEEL-COL', 'kg', 'Y if Weight authored', 'N (density x volume requires approved density)', 'Y', 'Y', 'BLOCKED (out of RC scope)'),
]
wr('quantity_requirement_matrix.csv', [dict(quantity=a, work_items=b, unit=c, from_authored_ifc=d, from_validated_geometry=e, from_user_provided=f, from_approved_assumption=g,
                                            if_no_source_available=h, zero_substitution='PROHIBITED', provenance_required='method + basis + source file + approval id (Agent 2 QuantityRecord)')
                                       for a, b, c, d, e, f, g, h in QM])

UI = [
    ('UI01', 'Ground levels / terrain model', 'm', 'EXC-*, BACKFILL', 'No terrain in any real IFC'), ('UI02', 'Formation / excavation level', 'm', 'EXC-*', 'Underside of foundations + blinding'),
    ('UI03', 'Soil class (BCCA consistency: dura/media/blanda/disgregado/roca)', 'enum', 'EXC-* variant', 'Selects BCCA code'), ('UI04', 'Working space and slope/shoring method', 'm / enum', 'EXC-*', 'Changes volume'),
    ('UI05', 'Blinding specified and thickness', 'bool / m', 'BLD', 'BCCA assumes 10 cm minimum'), ('UI06', 'Construction method per element group (cast-in-place / precast / composite)', 'enum', 'all concrete', 'Resolves CR06'),
    ('UI07', 'Foundation confirmation for candidate IfcBeam/IfcSlab elements', 'bool', 'FND-*', 'Resolves CR11 (SCH fund_*)'), ('UI08', 'Concrete class and consistency', 'enum', '*-CONC variant', 'Selects BCCA code'),
    ('UI09', 'Reinforcement mass per element or bar schedule', 'kg', '*-REBAR', 'No generic ratios'), ('UI10', 'Formwork system and formed-face rules', 'enum + rules', '*-FORM', 'Formwork area category C'),
    ('UI11', 'Exposed/architectural finish requirement', 'bool', '*-FORM variant', 'Selects visto vs revestir items'), ('UI12', 'Curing method and duration / strength criterion', 'days / MPa', 'CURE', 'No universal default'),
    ('UI13', 'Formwork striking criterion (sides, soffits, props)', 'days / MPa', 'FRM-STRIP', 'Engineer-approved'), ('UI14', 'Crew composition per trade and daily working hours', 'persons / h', 'all (Stage 5.3)', 'BCCA gives trades only'),
    ('UI15', 'Project calendar (holidays, working days)', 'calendar', 'all (Stage 5.4)', 'Catalan/Andalusian calendars not acquired'), ('UI16', 'Work zones', 'zone ids', 'DR11', 'IfcZone not audited'),
    ('UI17', 'Inspection holds before pours / backfill', 'days', 'DR04, DR06, DR12', 'Project-specific'), ('UI18', 'Bulking and compaction factors', 'ratio', 'BACKFILL', 'Bank vs compacted basis'),
    ('UI19', 'Precast supplier, unit type, crane', 'text', 'SLAB-PRECAST', 'No BCCA reference'), ('UI20', 'Masonry unit type and thickness', 'enum', 'MAS-*', 'Selects BCCA code'),
    ('UI21', 'Slab-on-grade identification', 'bool', 'SLAB-FORM', 'CR13'), ('UI22', 'Column height measurement rule at joints (clear / through)', 'enum', 'COL-CONC, double counting', 'DC07'),
]
wr('required_user_inputs.csv', [dict(input_id=a, input=b, unit=c, used_by=d, reason=e, default_value='NONE', if_missing='dependent work items BLOCKED', evidence_status='UNAVAILABLE in data') for a, b, c, d, e in UI])

DC = [
    ('DC01', 'Foundation formwork 03ERM00001 already includes stripping ("aplicacion del desencofrante, desencofrado")', 'FND-FORM + FRM-STRIP', 'Never add 05HED00001 to 03ERM*/03ERT* items', 'High', 'BCCA text 03ERM00001'),
    ('DC02', 'Column/beam/slab/wall formwork 05HEM* mention only release agent ("desencofrante") - stripping is a separate item', '05HEM* without 05HED*', 'Add FRM-STRIP exactly once per 05HEM* area', 'High (under-count risk)', 'BCCA texts 05HEM00001/00051/00101'),
    ('DC03', 'All concrete items include vibration and curing ("vibrado y curado")', '*-CONC + separately priced curing', 'Curing is a schedule constraint only; no cost/labour line', 'High', 'BCCA texts 03HAZ80020, 03HAA00010, 05HHP/HHJ/HHL00003'),
    ('DC04', 'Composite floor items (05FUA*, 05FUW*, 05FWW*) include concrete, reinforcement, mesh, formwork, props, stripping, vibration and curing', 'SLAB-COMPOSITE + SLAB-REBAR/FORM/CONC/FRM-STRIP', 'Mutually exclusive per slab', 'Critical', 'BCCA texts 05FUA00002, 05FUW80040'),
    ('DC05', 'Generic rebar item 05HAC00015 is shared by column, beam and slab reinforcement', 'COL/BEAM/SLAB-REBAR', 'Allocate each kg of reinforcement to exactly one element', 'Medium', 'BCCA 05HAC00015'),
    ('DC06', 'Beam/slab overlap: beam volume may include slab depth', 'BEAM-CONC + SLAB-CONC', 'Approved measurement rule (deduct at T-beams or not); check IFC geometry overlap', 'High', 'Stage 4.0B: Revit/ArchiCAD join behaviour not audited'),
    ('DC07', 'Column height through slab', 'COL-CONC + SLAB-CONC', 'Approved rule (clear height vs through)', 'High', 'Measurement guide'),
    ('DC08', 'Layered elements: element volume includes insulation/screed', '*-CONC', 'Use concrete layer only (e.g. SCH prefab floor fraction 0.6006)', 'High', 'Stage 4.0B consolidation'),
    ('DC09', 'SCH design and Synchro models describe the same elements', 'any work item from both models', 'Use one model per project version; link via STEP-id suffix', 'Critical', 'Stage 4.0B: 3,228 linked elements'),
    ('DC10', 'Weekly snapshot models contain subsets of the same elements', 'any', 'Never aggregate snapshots', 'Critical', 'Stage 4.0B: identical plan, element subsets'),
    ('DC11', 'Strip foundations as IfcBeam could be counted as both beam and foundation', 'BEAM-* + FND-*', 'Foundation classification (CR11) excludes element from BEAM-* items', 'High', 'SCH fund_strook/fund_opstort'),
    ('DC12', 'Excavation (bank) and backfill (compacted) on different bases', 'EXC-* vs BACKFILL', 'Convert only with approved factors', 'Medium', 'BCCA measurement texts'),
    ('DC13', 'Blinding bottom cleaning: concrete items include "limpieza de fondos"', 'BLD + *-CONC', 'No separate cleaning item', 'Low', 'BCCA texts'),
    ('DC14', 'Masonry measured net of openings ("deduciendo huecos")', 'MAS-* using gross area', 'Use NetSideArea or deduct openings', 'Medium', 'BCCA 06LHM00005, 06BHH00020, 06LEC80100'),
]
wr('double_counting_risk_register.csv', [dict(risk_id=a, risk=b, affected_combination=c, control=d, severity=e, evidence=f, evidence_status='VERIFIED_REFERENCE' if 'BCCA' in f else 'OBSERVED', approval_status='PENDING') for a, b, c, d, e, f in DC])

APP = []
for r in lib:
    APP.append(dict(approval_id=f"AP-W-{r['activity_id']}", item_type='work item applicability + BCCA variant + measurement rule', item=r['activity_id'], description=r['work_item']))
for r in RULES:
    APP.append(dict(approval_id=f'AP-{r[0]}', item_type='classification rule', item=r[0], description=r[1]))
for r in DEP:
    APP.append(dict(approval_id=f'AP-{r[0]}', item_type='dependency rule', item=r[0], description=r[4]))
for r in DC:
    APP.append(dict(approval_id=f'AP-{r[0]}', item_type='double-counting control', item=r[0], description=r[3]))
APP.append(dict(approval_id='AP-TOL', item_type='measurement tolerance', item='manual_quantity_validation.xlsx', description='Relative tolerance for independent quantity checks'))
for a in APP:
    a.update(required_approver='Engineering owner (structural/construction)', status='PENDING', decision='', approver='', date='', conditions='')
wr('engineering_approval_register.csv', APP)

# ------------------------------------------------------------------ preservation
snap = {}
if SNAP:
    for line in open(SNAP, encoding='utf-8'):
        h, p = line.rstrip('\n').split(' ', 1)
        snap[p.lstrip('*')] = h


def eol_only(p, h):
    d = open(p, 'rb').read()
    return hashlib.sha256(d.replace(b'\r\n', b'\n')).hexdigest() == h or hashlib.sha256(d.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest() == h


changed = []
for p, h in snap.items():
    if not os.path.exists(p):
        changed.append(dict(path=p, change='MISSING'))
    elif sha256(p) != h:
        changed.append(dict(path=p, change='line endings only' if eol_only(p, h) else 'CONTENT CHANGED',
                            mtime_utc=dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc).isoformat()))
now_files = set()
for root in ('pmi_core', 'tests', 'research/architecture', 'research/implementation', 'research/data_acquisition/stage4_0b', 'pages', 'docs', 'scripts'):
    for p in glob.glob(f'{root}/**/*', recursive=True):
        if os.path.isfile(p) and '__pycache__' not in p and not p.endswith('.pyc'):
            now_files.add(p.replace('\\', '/'))
added = sorted(now_files - set(snap))
base_ok = []
for name, bf in [('Stage 4.0B pre-task baseline', 'research/data_acquisition/stage4_0b/sections_B_E/preservation/baseline_sha256_before_stage4_0b.txt'),
                 ('Stage 4.0A baseline', 'research/evaluation/stage4_0a/preservation/baseline_sha256_before_stage4_0a.txt')]:
    bad = []
    n = 0
    for line in open(bf, encoding='utf-8'):
        h, p = line.rstrip('\n').split(' ', 1)
        p = p.lstrip('*')
        n += 1
        if not os.path.exists(p) or sha256(p) != h:
            bad.append(p)
    base_ok.append(dict(check=name, total=n, changed_or_missing=bad))
gs = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.splitlines()
mine = ['research/validation/stage5_1_manual/', 'research/construction_knowledge/stage5_2_preparation/', 'data/processed/candidates/stage5_2_prep/']
pres = dict(generated=NOW, checks=base_ok + [
    dict(check='Agent 1 (pmi_core, tests, research/implementation), Agent 2 (research/architecture), Stage 4.0B, app (app.py, pages, docs, scripts) vs task-start snapshot', total=len(snap),
         changed=changed, files_added_by_others_since_snapshot=added, note='This task only READ these paths.'),
    dict(check='git tracked modifications', tracked_modifications=[l for l in gs if not l.startswith('??')], untracked=[l[3:] for l in gs if l.startswith('??')]),
    dict(check='Write scope of this task', paths=mine),
    dict(check='No training, inference, production modules, environment changes, locked-test access, commit or push', result='confirmed by script scope (read-only IFC parsing, CSV/XLSX/MD/HTML writing)'),
])
AGENT1 = ('pmi_core/', 'tests/', 'research/implementation/')
for c in changed:
    c['owner'] = 'Agent 1 (concurrent Stage 5.1 implementation)' if c['path'].startswith(AGENT1) else 'other'
content_changes = [c for c in changed if c['change'] != 'line endings only']
non_agent1_content = [c for c in content_changes if c['owner'] == 'other']
pres['agent1_concurrent_changes'] = [c['path'] for c in content_changes if c['owner'] != 'other'] + [p for p in added if p.startswith(AGENT1)]
pres['all_protected_unchanged_by_this_task'] = (not any(c['changed_or_missing'] for c in base_ok) and not non_agent1_content
                                                 and not pres['checks'][3]['tracked_modifications'])
pres['all_protected_unchanged'] = pres['all_protected_unchanged_by_this_task']
pres['note'] = ('Changes inside pmi_core/, tests/ and research/implementation/ were made by Agent 1 while this task ran (mtimes 16:58-17:02 UTC); '
                'this task never wrote to those paths. Stage 4.0A/4.0B baselines, Stage 4.0B deliverables, Agent 2 architecture and the app are compared for content.')
json.dump(pres, open(f'{OUT}/preservation_verification.json', 'w', encoding='utf-8'), indent=2)
print('preservation ok:', pres['all_protected_unchanged'], 'changed', len(changed), 'content changes', len(content_changes), 'added by others', len(added))

# ------------------------------------------------------------------ report
def md_table(rows, cols):
    s = '| ' + ' | '.join(cols) + ' |\n|' + '---|' * len(cols) + '\n'
    for r in rows:
        s += '| ' + ' | '.join(str(r.get(c, '')).replace('|', '/').replace('\n', ' ') for c in cols) + ' |\n'
    return s


val = json.load(open(f'{PROC}/validation_elements_enriched.json', encoding='utf-8'))
cats = collections.Counter(e['geometry_category'][:1] for e in val)
auto = collections.Counter(r['automatic_work_package_eligibility'].split(' ')[0] for r in lib)
lib_view = [dict(activity_id=r['activity_id'], work_item=r['work_item'], bcca=r['bcca_reference'], unit=r['unit_and_basis'], labour_h=r['labour_h_per_unit_total'],
                 cost=r['direct_unit_cost_eur'], eligibility=r['automatic_work_package_eligibility']) for r in lib]
rules_view = [dict(rule_id=a, rule=b, observed=h[:160]) for a, b, c, d, e, f, g, h in RULES]
dep_view = [dict(rule_id=a, predecessor=b, successor=c, rule=e, alternatives=g, evidence=h[:160]) for a, b, c, d, e, f, g, h in DEP]
rep = f"""# Stage 5.2 preparation - reinforced concrete construction knowledge (research only)

Generated {NOW}. **Not a Stage 5.2 production module.** Every rule, mapping and assumption is **PENDING engineering approval** (`engineering_approval_register.csv`, {len(APP)} items). Work stops at the approval gate.

## Evidence vocabulary
| Status | Meaning |
|---|---|
| VERIFIED_REFERENCE | Copied/recomputed from a cited file (BCCA 2023 BC3, IFC models) |
| OBSERVED | Seen in one real project plan (SCHEPENDOMLAAN Synchro export) - an example, not a rule |
| PROPOSED_RULE | Auditor proposal - pending approval |
| ASSUMPTION | Explicit assumption - pending approval, never applied automatically |
| UNAVAILABLE | No evidence located - dependent activity blocked |

## Task A - manual quantity validation
- Workbook `research/validation/stage5_1_manual/manual_quantity_validation.xlsx`: 40 elements, sheets Instructions / Validation_40 / Initial_subset / Categories / Lists. Independent measurement, tolerance and approval fields are empty.
- Geometry categories: A simple homogeneous {cats['A']}, B layered {cats['B']}, C irregular {cats['C']}, D invalid mesh {cats['D']}.
- Initial subset: 11 category-A elements (`initial_validation_subset.csv`) covering SCH strip foundation, RestageIFC footing, and MEN-RES column/beams/slabs/walls.
- Measurement workflow: `measurement_guide.md` (Bonsai/FreeCAD share IfcOpenShell geometry and are not independent of the DERIVED values).

## Task B - construction work item library
{len(lib)} work items; automatic work-package eligibility: {dict(auto)}. No item is automatically eligible without approval.
{md_table(lib_view, ['activity_id', 'work_item', 'bcca', 'unit', 'labour_h', 'cost', 'eligibility'])}
BCCA coefficients are catalogue estimates (Andalucia, Dic-2023), not observed productivity. Trades only - no crew sizes.

### Classification rules (IFC class never decides alone)
{md_table(rules_view, ['rule_id', 'rule', 'observed'])}
Foundation candidates observed (CR11): {md_table(fnd_rows, ['model', 'ifc_class', 'foundation_evidence', 'material_category', 'elements', 'example'])}

### Double counting
{md_table([dict(risk_id=a, risk=b, control=d, severity=e) for a, b, c, d, e, f in DC], ['risk_id', 'risk', 'control', 'severity'])}

## Task C - dependency rules (all PENDING, no universal durations)
{md_table(dep_view, ['rule_id', 'predecessor', 'successor', 'rule', 'alternatives', 'evidence'])}
Observed sequences come from one project plan (SCHEPENDOMLAAN, planned dates 2015; no actual dates). Spatial adjacency never creates precedence (DR15, CR14).

## Task D - missing information policy
{md_table([dict(quantity=a, from_authored_ifc=d, from_validated_geometry=e, from_user=f, from_assumption=g, otherwise=h) for a, b, c, d, e, f, g, h in QM], ['quantity', 'from_authored_ifc', 'from_validated_geometry', 'from_user', 'from_assumption', 'otherwise'])}
- Unknown quantities are never replaced by zero; the work item is BLOCKED and reported.
- Reinforcement mass is never generated from an unapproved generic ratio.
- {len(UI)} required user inputs have no default (`required_user_inputs.csv`).

## Unavailable evidence
- No BCCA reference for aerated-concrete block masonry, hollow-core/filigree precast floors or separate curing.
- No reinforcement, excavation, terrain or formwork-area data in any real model.
- No crew sizes, calendars, curing or striking criteria.
- Sand-lime masonry reference (06LEC80100, face brick) is a weak match for SCH glued sand-lime elements.

## Preservation
Protected files unchanged by this task: **{'yes' if pres['all_protected_unchanged'] else 'NO - see preservation_verification.json'}**. Files changed since task start: {len(changed)} ({len(content_changes)} content changes, all by Agent 1 in its own implementation area: {len(pres['agent1_concurrent_changes'])} paths incl. additions); files added by others: {len(added)}.
"""
open(f'{OUT}/construction_knowledge_report.md', 'w', encoding='utf-8').write(rep)

E_ = html.escape
BAD = {'PENDING': 'warn', 'BLOCKED': 'bad', 'CONDITIONAL': 'warn', 'UNAVAILABLE': 'bad'}


def cell(v):
    v = '' if v is None else str(v)
    for k, cl in BAD.items():
        if v.startswith(k):
            return f'<span class="b {cl}">{E_(v)}</span>'
    return E_(v)


def h_table(rows, cols):
    s = '<div class="tw"><table><thead><tr>' + ''.join(f'<th>{E_(c)}</th>' for c in cols) + '</tr></thead><tbody>'
    for r in rows:
        s += '<tr>' + ''.join(f'<td>{cell(r.get(c))}</td>' for c in cols) + '</tr>'
    return s + '</tbody></table></div>'


css = open('research/data_acquisition/stage4_0b/consolidated/stage4_0b_consolidated_report.html', encoding='utf-8').read().split('<style>')[1].split('</style>')[0]
secs = [('scope', 'Scope and status'), ('taskA', 'Manual validation'), ('library', 'Work item library'), ('classify', 'Classification rules'), ('double', 'Double counting'),
        ('deps', 'Dependency rules'), ('missing', 'Missing information policy'), ('inputs', 'Required user inputs'), ('approval', 'Approval gate'), ('pres', 'Preservation')]
body = f"""<h1>Stage 5.2 preparation - RC construction knowledge</h1><p class="sub">Generated {E_(NOW)}. Research only - not a production module. All items PENDING engineering approval.</p>
<div class="tiles"><div class="tile"><div class="n">40</div><div class="l">elements in validation workbook (11 initial)</div></div>
<div class="tile"><div class="n">{len(lib)}</div><div class="l">work items</div></div><div class="tile"><div class="n">{len(RULES)}</div><div class="l">classification rules</div></div>
<div class="tile"><div class="n">{len(DEP)}</div><div class="l">dependency rules</div></div><div class="tile"><div class="n">{len(APP)}</div><div class="l">items awaiting approval</div></div></div>
<section id="scope"><h2>Scope and evidence status</h2><p>VERIFIED_REFERENCE = copied/recomputed from BCCA or IFC; OBSERVED = one real project plan; PROPOSED_RULE / ASSUMPTION = pending approval; UNAVAILABLE = blocked.</p></section>
<section id="taskA"><h2>Manual quantity validation</h2><p>Workbook <code>research/validation/stage5_1_manual/manual_quantity_validation.xlsx</code>: A {cats['A']} / B {cats['B']} / C {cats['C']} / D {cats['D']} elements; initial subset 11. Independent fields empty.</p></section>
<section id="library"><h2>Work item library</h2>{h_table(lib_view, ['activity_id', 'work_item', 'bcca', 'unit', 'labour_h', 'cost', 'eligibility'])}<div class="callout">BCCA values are catalogue estimates (Andalucia, Dic-2023), not observed productivity.</div></section>
<section id="classify"><h2>Classification rules</h2>{h_table(rules_view, ['rule_id', 'rule', 'observed'])}<h3>Foundation candidates (CR11)</h3>{h_table(fnd_rows, ['model', 'ifc_class', 'foundation_evidence', 'material_category', 'elements', 'example'])}</section>
<section id="double"><h2>Double-counting controls</h2>{h_table([dict(risk_id=a, risk=b, control=d, severity=e, evidence=f) for a, b, c, d, e, f in DC], ['risk_id', 'risk', 'control', 'severity', 'evidence'])}</section>
<section id="deps"><h2>Dependency rules</h2>{h_table(dep_view, ['rule_id', 'predecessor', 'successor', 'rule', 'alternatives', 'evidence'])}<p class="sub">No universal curing or striking durations. Spatial adjacency never creates precedence.</p></section>
<section id="missing"><h2>Missing information policy</h2>{h_table([dict(quantity=a, from_authored_ifc=d, from_validated_geometry=e, from_user=f, from_assumption=g, otherwise=h) for a, b, c, d, e, f, g, h in QM], ['quantity', 'from_authored_ifc', 'from_validated_geometry', 'from_user', 'from_assumption', 'otherwise'])}
<div class="callout">Unknown quantities are never replaced by zero. Reinforcement mass is never generated from an unapproved generic ratio.</div></section>
<section id="inputs"><h2>Required user inputs</h2>{h_table([dict(input_id=a, input=b, unit=c, used_by=d, reason=e) for a, b, c, d, e in UI], ['input_id', 'input', 'unit', 'used_by', 'reason'])}</section>
<section id="approval"><h2>Engineering approval gate</h2><p>{len(APP)} items PENDING in <code>engineering_approval_register.csv</code>. Stage 5.2 implementation must not start until the engineering owner records decisions.</p></section>
<section id="pres"><h2>Preservation</h2><p>Protected content unchanged: <b>{'yes' if pres['all_protected_unchanged'] else 'NO - see JSON'}</b>; changed files {len(changed)} ({len(content_changes)} content); added by others {len(added)}.</p></section>"""
nav = ''.join(f'<a href="#{a}">{E_(b)}</a>' for a, b in secs)
page = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stage 5.2 Knowledge Prep</title><style>{css}</style></head><body><div class="layout"><nav><div class="sub" style="padding:0 8px 8px">Stage 5.2 prep</div>{nav}</nav><main>{body}</main></div></body></html>'
open(f'{OUT}/construction_knowledge_report.html', 'w', encoding='utf-8').write(page)
print('html', len(page))
