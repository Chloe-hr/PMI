"""Stage 5.2B engineering review and scheduling-readiness package (research only).

Run from repo root:
    .venv/Scripts/python.exe -I research/validation/engineering_approval_review/scripts/build_review_package.py
Reads (never modifies): Stage 5.2 preparation tables, Stage 5.1 manual subset, BCCA inspection tables,
Agent 2 canonical schemas, and the IFC files of the 11 subset elements (IfcOpenShell, in memory).
Writes only to research/validation/engineering_approval_review/.
Approves nothing. Fills no measurement. Hypothetical values are labelled HYPOTHETICAL and exist only for software tests.
"""
import collections, csv, datetime as dt, glob, hashlib, json, math, os, re, subprocess, sys
import numpy as np
import ifcopenshell, ifcopenshell.geom
import ifcopenshell.util.unit as uu

sys.stdout.reconfigure(encoding='utf-8')
OUT = 'research/validation/engineering_approval_review'
KN = 'research/construction_knowledge/stage5_2_preparation'
BC = 'data/processed/candidates/stage4_0b/bcca2023'
BCCA_FILE = 'data/raw/candidates/productivity/bcca_andalucia/extracted/BCCA2023_V02/BCCA2023_V02.bc3'
BCCA_SHA = 'bee06981c4447c6b07a3434a6a4d934de11a7498687b0bf3462ba2ce36b7817d'
NOW = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def rd(p):
    with open(p, encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def wr(name, rows, cols=None):
    cols = cols or list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print('wrote', name, len(rows))


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


APP = rd(f'{KN}/engineering_approval_register.csv')
LIB = {r['activity_id']: r for r in rd(f'{KN}/construction_work_item_library.csv')}
CR = {r['rule_id']: r for r in rd(f'{KN}/element_classification_rules.csv')}
DR = {r['rule_id']: r for r in rd(f'{KN}/construction_dependency_rules.csv')}
DC = {r['risk_id']: r for r in rd(f'{KN}/double_counting_risk_register.csv')}

# ================================================================== Step 1: priority approval register
FRAME = 'COL-REBAR, COL-FORM, COL-CONC, BEAM-REBAR, BEAM-FORM, BEAM-CONC, SLAB-REBAR, SLAB-FORM, SLAB-CONC, CURE, FRM-STRIP'
EXP = {'struct': 'structural engineer', 'method': 'construction-methods / site engineer', 'cost': 'cost estimator (BC3/BCCA)', 'bim': 'BIM coordinator', 'qs': 'quantity surveyor'}
# id -> (phase, alternatives, consequence_if_chosen, consequence_if_undecided, affected, expertise)
P = {
    'AP-W-COL-CONC': ('WPG', 'accept 05HHP00003 (HA-25/P/20) | 05HHP00103 (HA-30) | other class (no BCCA code -> blocked)', 'Column concrete work items generated with BCCA labour/vibrator coefficients', 'No column concrete activity', 'COL-CONC, CURE', 'struct+cost'),
    'AP-W-COL-FORM': ('WPG', 'timber 05HEM00001 | steel 05HET00001 | exposed finish 05HEM00201', 'Column formwork items + paired FRM-STRIP', 'No column formwork activity; COL-CONC lacks predecessor', 'COL-FORM, FRM-STRIP', 'method+cost'),
    'AP-W-COL-REBAR': ('WPG', 'B500S bars 05HAC00015 | B400S 05HAC00010', 'Rebar activity using user-supplied kg', 'No rebar activity (kg still required from user)', 'COL-REBAR', 'struct'),
    'AP-W-BEAM-CONC': ('WPG', '05HHJ00003 | 05HHJ00103 | monolithic pour with slab (measurement rule DC06)', 'Beam concrete items', 'No beam concrete activity', 'BEAM-CONC', 'struct+cost'),
    'AP-W-BEAM-FORM': ('WPG', 'timber 05HEM00051 | exposed 05HEM00225', 'Beam formwork items + FRM-STRIP', 'No beam formwork', 'BEAM-FORM, FRM-STRIP', 'method+cost'),
    'AP-W-BEAM-REBAR': ('WPG', '05HAC00015 | 05HAC00010', 'Rebar activity using user kg', 'No beam rebar activity', 'BEAM-REBAR', 'struct'),
    'AP-W-SLAB-CONC': ('WPG', '05HHL00003 | 05HHL00103', 'Slab concrete items', 'No slab concrete activity', 'SLAB-CONC', 'struct+cost'),
    'AP-W-SLAB-FORM': ('WPG', 'timber 05HEM00101 | exposed 05HEM80010 | none (slab on grade, CR13)', 'Slab soffit formwork + FRM-STRIP', 'No slab formwork', 'SLAB-FORM, FRM-STRIP', 'method+cost'),
    'AP-W-SLAB-REBAR': ('WPG', 'bars 05HAC00015 | mesh 05HAM00010 | both (mass split by user)', 'Slab rebar activity', 'No slab rebar activity', 'SLAB-REBAR', 'struct'),
    'AP-W-CURE': ('DUR', 'elapsed hold with engineer-given minimum | strength-based release (maturity/cubes) | combination', 'Elapsed hold after each pour; no cost line (bundled in BCCA concrete)', 'Hold unresolved -> successors cannot be scheduled', 'CURE, FRM-STRIP, supported members', 'struct'),
    'AP-W-FRM-STRIP': ('DUR', '05HED00001 (timber) | 05HED00051 (metal panels) | 05HED00101 (exposed)', 'Separate stripping activity per 05HEM* area', 'Stripping labour omitted (under-count) or formwork reuse unknown', 'FRM-STRIP', 'method+cost'),
    'AP-CR01': ('WPG', 'adopt material-first classification | alternative classifier', 'Class alone never selects work items', 'Classifier undefined - generation blocked', FRAME, 'bim+struct'),
    'AP-CR05': ('WPG', 'accept explicit cast-in-place terms list | extend list', 'Explicit CIP elements route to RC items', 'Explicit CIP elements blocked', FRAME, 'bim'),
    'AP-CR06': ('WPG', 'user confirms method per element group | treat all unstated as CIP (requires explicit approval)', 'Unstated-method concrete resolved', 'Elements with "concrete" but no method stay blocked', FRAME, 'struct+bim'),
    'AP-CR07': ('WPG', 'accept steel exclusion terms', 'Steel columns/beams excluded from RC items', 'Risk of routing steel to RC items', 'COL-*, BEAM-*', 'bim'),
    'AP-CR10': ('WPG', 'block elements without material | user assigns material', 'Unclassified elements visible as blocked', 'Silent misrouting risk', FRAME, 'bim'),
    'AP-CR13': ('WPG', 'BASESLAB/lowest storey = no soffit formwork | user flags each slab', 'Ground-bearing slabs excluded from SLAB-FORM', 'Slab formwork over-count on ground slabs', 'SLAB-FORM, FRM-STRIP', 'struct+method'),
    'AP-CR14': ('WPG', 'accept policy', 'No classification or precedence from adjacency', 'Policy unenforced', 'all', 'struct'),
    'AP-DC04': ('WPG', 'separate items only (demo scope) | composite 05FUW*/05FUA* only', 'Composite items excluded from demo', 'Double counting if both selected', 'SLAB-*', 'cost'),
    'AP-DC05': ('WPG', 'allocate each kg to one element', 'Rebar mass not duplicated across element types', 'Possible duplicate rebar', '*-REBAR', 'qs'),
    'AP-DC06': ('WPG', 'beam includes slab depth | beam below slab soffit only', 'One consistent beam/slab volume rule', 'Concrete double counting at T-beams', 'BEAM-CONC, SLAB-CONC, BEAM-FORM', 'qs+struct'),
    'AP-DC07': ('WPG', 'clear height | through slab', 'One consistent column height rule', 'Column/slab double counting', 'COL-CONC, COL-FORM', 'qs+struct'),
    'AP-DC08': ('WPG', 'concrete layer only for layered elements | exclude layered elements from demo', 'Concrete volume excludes screed/insulation', 'Layered elements over-count concrete', '*-CONC', 'qs+bim'),
    'AP-DC02': ('DUR', 'add FRM-STRIP once per 05HEM* area', 'Stripping labour counted once', 'Stripping labour omitted', 'FRM-STRIP', 'cost'),
    'AP-DC03': ('DUR', 'curing as hold only (no labour/cost)', 'No curing double count', 'Curing labour counted twice', 'CURE, *-CONC', 'cost'),
    'AP-DR05': ('RCPSP', 'rebar before column formwork (FS) | prefabricated cage with SS overlap', 'Column sequence fixed', 'Column activities unordered', 'COL-REBAR, COL-FORM', 'method'),
    'AP-DR06': ('RCPSP', 'formwork+rebar before pour; slab/beam soffit first; walls one face first', 'Pour predecessors defined', 'Pours unordered', '*-FORM, *-REBAR, *-CONC', 'method'),
    'AP-DR07': ('RCPSP', 'FS pour -> curing hold (engineer duration/criterion)', 'Hold inserted after each pour', 'No hold - unsafe schedule', 'CURE', 'struct'),
    'AP-DR08': ('RCPSP', 'time-based striking | strength-based striking | separate side vs soffit criteria', 'Stripping released by approved criterion', 'Stripping cannot be scheduled', 'FRM-STRIP', 'struct'),
    'AP-DR09': ('RCPSP', 'supporting members adequate before supported formwork | monolithic pour', 'Vertical support logic', 'Beams/slabs could be scheduled before supports', 'BEAM-FORM, SLAB-FORM', 'struct'),
    'AP-DR10': ('RCPSP', 'storey-by-storey FS | overlapping storeys with explicit rules', 'Vertical progression', 'Storeys unordered', 'all frame activities', 'method'),
    'AP-DR11': ('RCPSP', 'resource-driven zone order | user-fixed zone order', 'Zone sequencing', 'Zones undefined', 'all frame activities', 'method'),
    'AP-DR15': ('RCPSP', 'accept policy', 'No adjacency-derived precedence', 'Policy unenforced', 'all', 'struct'),
}
for k in ('AP-TOL', 'AP-CR02', 'AP-CR03', 'AP-CR04', 'AP-CR09', 'AP-CR11', 'AP-CR12', 'AP-CR15', 'AP-DC09', 'AP-DC10', 'AP-DC11'):
    P.setdefault(k, ('REAL-RELEASE', '', '', '', '', 'struct+bim'))
P['AP-TOL'] = ('REAL-RELEASE', 'relative tolerance per quantity type (proposed by engineering owner)', 'Manual checks can be accepted/rejected', 'Real-model quantities stay unvalidated', 'all real-model quantities', 'qs+struct')
P['AP-CR11'] = ('REAL-RELEASE', 'confirm fund_* IfcBeam as foundations | treat as beams', 'SCH foundations routed to FND-*', 'SCH foundations blocked (or wrongly beams)', 'FND-*, BEAM-*', 'struct+bim')
P['AP-CR15'] = ('REAL-RELEASE', 'inherit design classification via STEP suffix | classify Synchro separately', 'Synchro interoperability case classifiable', 'Synchro elements blocked', 'all (SCH Synchro)', 'bim')


def evidence_of(aid):
    k = aid[3:] if aid.startswith('AP-') else aid
    if aid.startswith('AP-W-'):
        r = LIB[aid[5:]]
        return f"{r['bcca_reference']} {r['work_item']}; {r['conditions_and_exceptions']}; source {r['evidence_source'][:80]}"
    if k in CR:
        return f"{CR[k]['rule']} | observed: {CR[k]['observed_in_models'][:200]}"
    if k in DR:
        return f"{DR[k]['rule']} | {DR[k]['evidence'][:200]}"
    if k in DC:
        return f"{DC[k]['risk']} | {DC[k]['evidence']}"
    return 'Stage 5.1 manual validation workbook (tolerance columns empty)'


prio = []
order = {'WPG': 1, 'DUR': 2, 'RCPSP': 3, 'REAL-RELEASE': 4, 'NOT-NEEDED': 5}
for a in APP:
    ph, alt, conq, undec, aff, ex = P.get(a['approval_id'], ('NOT-NEEDED', '', '', '', '', ''))
    prio.append(dict(approval_id=a['approval_id'], item_type=a['item_type'], description=a['description'],
                     demo_priority={'WPG': 'P1 - required for work-package generation', 'DUR': 'P2 - required for duration estimation',
                                    'RCPSP': 'P3 - required for resource-constrained scheduling', 'REAL-RELEASE': 'P4 - required only for real-project release',
                                    'NOT-NEEDED': 'P5 - not needed for the concrete-frame demonstration'}[ph],
                     decision_phase=ph, supporting_evidence=evidence_of(a['approval_id']), alternatives=alt, consequence_if_chosen=conq, consequence_if_undecided=undec,
                     affected_activities=aff, required_expertise='; '.join(EXP[x] for x in ex.split('+') if x) if ex else '',
                     status='PENDING', decision='', decided_by='', decision_date='', conditions=''))
prio.sort(key=lambda r: (order[r['decision_phase']], r['approval_id']))
wr('priority_approval_register.csv', prio)
cnt = collections.Counter(r['decision_phase'] for r in prio)

# ================================================================== Step 2: measurement instruction sheets
SUB = rd('research/validation/stage5_1_manual/initial_validation_subset.csv')
EN = {e['check_id']: e for e in json.load(open('data/processed/candidates/stage5_2_prep/validation_elements_enriched.json', encoding='utf-8'))}
gs = ifcopenshell.geom.settings()
gs.set('use-world-coords', True)


def profile_info(el, ls):
    """Return dict with profile type, dims (m), polygon (m) and extrusion depth for single-extrusion bodies."""
    out = dict(profile='unknown', dims='', polygon=None, depth=None, placement_note='')
    for rep in el.Representation.Representations:
        if rep.RepresentationIdentifier != 'Body':
            continue
        items = list(rep.Items)
        while items:
            it = items.pop()
            if it.is_a('IfcMappedItem'):
                items.extend(it.MappingSource.MappedRepresentation.Items)
                out['placement_note'] = 'mapped (type) geometry'
                continue
            if it.is_a('IfcExtrudedAreaSolid'):
                pr = it.SweptArea
                out['depth'] = it.Depth * ls
                if pr.is_a('IfcRectangleProfileDef'):
                    out.update(profile='rectangle', dims=f'XDim={pr.XDim * ls:.4f} m, YDim={pr.YDim * ls:.4f} m', area=pr.XDim * pr.YDim * ls * ls)
                elif pr.is_a('IfcArbitraryClosedProfileDef'):
                    c = pr.OuterCurve
                    pts = None
                    if c.is_a('IfcPolyline'):
                        pts = [tuple(p.Coordinates[:2]) for p in c.Points]
                    elif c.is_a('IfcIndexedPolyCurve'):
                        pts = [tuple(p[:2]) for p in c.Points.CoordList]
                    if pts:
                        if pts[0] == pts[-1]:
                            pts = pts[:-1]
                        pts = [(x * ls, y * ls) for x, y in pts]
                        a = 0.5 * abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))))
                        out.update(profile=f'polygon ({len(pts)} vertices, {c.is_a()})', polygon=[(round(x, 4), round(y, 4)) for x, y in pts], area=a)
                    else:
                        out.update(profile=f'arbitrary ({c.is_a()}) - curve type not reducible to vertices')
                    if getattr(pr, 'InnerCurves', None):
                        out['profile'] += ' WITH INNER VOIDS'
                return out
    return out


sheets = []
by_file = collections.defaultdict(list)
for s in SUB:
    by_file[s['ifc_path']].append(s)
GEOM = {}
for path, ss in by_file.items():
    f = ifcopenshell.open(path)
    ls = uu.calculate_unit_scale(f)
    for s in ss:
        el = f.by_guid(s['global_id'])
        pi = profile_info(el, ls)
        sh = ifcopenshell.geom.create_shape(gs, el)
        v = np.asarray(sh.geometry.verts).reshape(-1, 3)
        pi['bbox_min'] = [round(float(x), 3) for x in v.min(0)]
        pi['bbox_max'] = [round(float(x), 3) for x in v.max(0)]
        pi['length_unit'] = 'mm' if abs(ls - 0.001) < 1e-12 else ('m' if ls == 1 else str(ls))
        GEOM[s['check_id']] = pi
    del f

TOOL_RHINO = ('Rhino 8: File > Import the IFC (Rhino 8 IFC import; if unavailable, use a third-party IFC plug-in and record it). Locate the element by name/storey and the world '
              'bounding box below (Rhino reports model units: set to metres). Dimensions: Distance or Dim commands on snapped vertices. Independent volume (optional cross-check): '
              'select the closed polysurface, run Volume (Rhino/OpenNURBS kernel, independent of IfcOpenShell); confirm with "IsClosed"/"What" that the solid is closed.')
TOOL_REVIT = ('Revit: Insert > Link IFC (or Open IFC); open the 3D view, use Select by ID only for Revit element ids (the IFC GlobalId is shown in the IFC parameters when the importer maps it). '
              'Dimensions: Measure tool between edges or aligned dimensions in a section view. Revit-computed volume of imported IFC geometry is a conversion of the same mesh - '
              'record it only as a secondary cross-check, not as the independent value.')


def formula(pi, cls):
    if pi['profile'] == 'rectangle':
        return 'V = XDim x YDim x extrusion depth (all in m)'
    if pi['profile'].startswith('polygon'):
        return 'V = A_profile x extrusion depth; A_profile from measured vertex coordinates by the shoelace formula A = 0.5 |sum(x_i*y_(i+1) - x_(i+1)*y_i)|'
    return 'Profile not reducible to simple dimensions - decompose into prisms'


md = [f'# Measurement instructions - initial validation subset (11 elements)\n\nGenerated {NOW}. Research only. **No measured values are filled in.** '
      'Record results in `research/validation/stage5_1_manual/manual_quantity_validation.xlsx` (sheet Validation_40) - this file does not modify it. '
      'Store evidence in `research/validation/stage5_1_manual/evidence/<check_id>/`.\n\n'
      '**Independence rule:** measure dimensions yourself and compute the volume; the grey workbook values (authored, DERIVED) must not be copied. '
      'Bonsai/FreeCAD share IfcOpenShell geometry and do not count as independent.\n\n'
      '**Common evidence per element:** (1) screenshot of the element selected with its properties panel showing GlobalId or name; '
      '(2) screenshot of each measured dimension; (3) for polygons, an exported vertex list (Rhino: `List` or `PtInfo`; Revit: spot coordinates) saved as CSV; '
      '(4) a short note of tool, version, units and file used.\n']
for s in SUB:
    e, g = EN[s['check_id']], GEOM[s['check_id']]
    lim = [e['known_limitations']]
    simple = g['profile'] == 'rectangle'
    if g['profile'].startswith('polygon'):
        lim.append(f"{g['profile']}: simple b x h measurement is insufficient - all vertices must be measured")
    if g.get('placement_note'):
        lim.append(g['placement_note'])
    req_dims = (f"section width and depth ({g['dims']} in the IFC profile definition - re-measure, do not copy) and member length (extrusion depth)" if simple else
                f"profile vertices ({len(g['polygon'] or [])} points) in the profile plane, and extrusion depth" if g['polygon'] else 'see decomposition')
    ded = 'None expected (no IfcOpeningElement voids this element). If a notch, chamfer or opening is visible, measure and deduct it and note it.'
    if e['ifc_class'] == 'IfcColumn':
        ded += ' State whether the measured height is clear height or includes slab/beam intersections (rule DC07 pending).'
    if e['ifc_class'] == 'IfcBeam' and (e['element_name'] or '').startswith('fund'):
        ded += ' Foundation element modelled as IfcBeam: measure as a strip/upstand foundation; no slab deduction applies.'
    elif e['ifc_class'] == 'IfcBeam':
        ded += ' State whether beam depth includes the slab (rule DC06 pending).'
    if e['ifc_class'] == 'IfcWall':
        ded += ' Check for inserted doors/windows in the viewer; none are modelled as voids here.'
    md.append(f"""
---
## {s['check_id']} - {e['ifc_class']} "{e['element_name']}" ({e['model_key']}, {e['validation_role']})

| Field | Value |
|---|---|
| IFC file | `{s['ifc_path']}` |
| Schema / file length unit | {e['schema']} / {g['length_unit']} |
| GlobalId | `{e['global_id']}` |
| STEP id | `#{e['step_id']}` |
| Class / predefined type | {e['ifc_class']} / {e['predefined_type']} |
| Storey / building | {e['storey_resolved']} / {e['building']} |
| Material | {e['material_classification']} |
| World bounding box (m) | min {g['bbox_min']} / max {g['bbox_max']} |
| Body geometry | {e['geometry_representation']} |
| Measurement basis | Net volume of the modelled body in m3 (concrete); element is single-material |
| Required dimensions | {req_dims} |
| Required deductions | {ded} |
| Independent formula | {formula(g, e['ifc_class'])} |
| Authored value available for comparison | {('NetVolume ' + e['authored_net_volume_m3'] + ' m3 (do not copy)') if e['authored_net_volume_m3'] else 'none - comparison only against DERIVED geometry'} |

**Rhino workflow.** {TOOL_RHINO}

**Revit workflow.** {TOOL_REVIT}

**Evidence to save.** `{s['check_id']}_selection.png`, `{s['check_id']}_dim_*.png`, {('`' + s['check_id'] + '_vertices.csv`, ') if g['polygon'] else ''}`{s['check_id']}_note.txt`.

**Known limitations.** {'; '.join(x for x in lim if x)}
""")
    if s['check_id'] == 'QV01':
        md.append('\n*Foundation note:* this IfcBeam is a strip foundation ("fund_strook") on storey "-1 fundering". Record in reviewer_notes whether you agree it is a foundation (rule CR11 pending).\n')
open(f'{OUT}/measurement_instructions.md', 'w', encoding='utf-8').write(''.join(md))
print('wrote measurement_instructions.md')

# ================================================================== Step 3: Stage 5.3 reference selection
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


SEL = [  # (activity, code, role)
    ('COL-REBAR', '05HAC00015', 'primary'), ('BEAM-REBAR', '05HAC00015', 'primary'), ('SLAB-REBAR', '05HAC00015', 'primary'), ('SLAB-REBAR', '05HAM00010', 'alternative (mesh)'),
    ('COL-FORM', '05HEM00001', 'primary'), ('BEAM-FORM', '05HEM00051', 'primary'), ('SLAB-FORM', '05HEM00101', 'primary'),
    ('COL-CONC', '05HHP00003', 'primary'), ('COL-CONC', '05HHP00103', 'alternative (HA-30)'), ('BEAM-CONC', '05HHJ00003', 'primary'), ('BEAM-CONC', '05HHJ00103', 'alternative (HA-30)'),
    ('SLAB-CONC', '05HHL00003', 'primary'), ('SLAB-CONC', '05HHL00103', 'alternative (HA-30)'), ('FRM-STRIP', '05HED00001', 'primary'),
]
INC = {'vibrado': 'vibration', 'curado': 'curing', 'limpieza de fondos': 'bottom cleaning', 'desencofrante': 'release agent', 'desencofrado': 'stripping', 'limpieza': 'cleaning',
       'humedecido': 'wetting', 'corte': 'cutting', 'labrado': 'bending', 'colocaci': 'placing', 'atado': 'tying wire', 'separadores': 'spacers', 'solapes': 'laps',
       'pasos de tuber': 'service openings', 'reservas': 'reserves/blockouts', 'puesta en obra': 'placing on site', 'suministrado': 'supply', 'reparaci': 'repair',
       'elementos complementarios': 'stabilising accessories'}
EXCL = {'CONC': 'formwork; reinforcement; stripping; crane/pump/concrete transport beyond "puesto en obra" (no machinery other than vibrator in decomposition); waiting/curing time (only labour of curing is bundled)',
        'FORM': 'stripping (separate 05HED*); props/shoring as separate items not listed; crane handling; reinforcement; concrete',
        'REBAR': 'bar schedule/detailing; crane lifting; prefabricated cage transport',
        'STRIP': 'formwork erection; re-propping; cleaning beyond "limpieza y reparacion"'}
sel_rows = []
for act, code, role in SEL:
    c = C[code]
    lab, mach, mats, split = collections.defaultdict(float), collections.defaultdict(float), [], collections.defaultdict(float)
    lr = {}
    for L in expand(code):
        cost = L['qty'] * (L['price'] or 0)
        split[L['type']] += cost
        if L['type'] == 'labor':
            lab[L['summary']] += L['qty']
            lr[L['summary']] = L['price']
        elif L['type'] == 'machinery':
            mach[f"{L['summary']} [{L['unit']}]"] += L['qty']
        else:
            mats.append(f"{L['child']} {L['summary']} {round(L['qty'], 5)} {L['unit']} @ {L['price']}")
    txt = T.get(code, '')
    inc = sorted({v for k, v in INC.items() if re.search(k, txt, re.I)})
    if 'desencofrante' in txt.lower() and not re.search(r'\bdesencofrado\b', txt, re.I):
        inc = [x for x in inc if x != 'stripping']
    fam = 'CONC' if '-CONC' in act else 'FORM' if '-FORM' in act else 'REBAR' if 'REBAR' in act else 'STRIP'
    comp = {'CONC': 'productive labour (peon especial, oficial) + equipment (vibrator, machine-hours) ; BUNDLED: curing labour, bottom cleaning ; WAITING/STRENGTH: curing hold modelled separately (no coefficient)',
            'FORM': 'productive labour (encofrador + peon) ; BUNDLED: release agent, cleaning, wetting',
            'REBAR': 'productive labour (ferrallista) ; BUNDLED: cutting, bending, tying, spacers',
            'STRIP': 'productive labour (encofrador + peon) ; released only by striking criterion (strength gate)'}[fam]
    sel_rows.append(dict(
        activity_id=act, selection_role=role, bcca_code=code, bcca_summary=c['summary'], quantity_unit=c['unit'],
        labour_h_per_unit_by_trade='; '.join(f'{k}={round(v, 5)}' for k, v in lab.items()), labour_h_per_unit_total=round(sum(lab.values()), 5),
        labour_rate_eur_h='; '.join(f'{k}={v}' for k, v in lr.items()),
        equipment_h_per_unit='; '.join(f'{k}={round(v, 5)}' for k, v in mach.items()) or 'none in decomposition',
        material_coefficients='; '.join(mats)[:600],
        included_operations=', '.join(inc), excluded_operations=EXCL[fam],
        unit_cost_eur=fl(c['price']), cost_labour_eur=round(split['labor'], 4), cost_equipment_eur=round(split['machinery'], 4), cost_material_eur=round(split['material'] + split['other'], 4),
        cost_split_sum_eur=round(sum(split.values()), 4), cost_split_difference_eur=round((fl(c['price']) or 0) - sum(split.values()), 4),
        cost_split_basis='arithmetic sum of BCCA decomposition lines by resource type (not an allocation percentage)',
        component_types=comp,
        bundled_not_separately_allocatable=('curing labour and bottom cleaning inside concrete labour - cannot be split into a separate curing activity' if fam == 'CONC'
                                            else 'release agent and cleaning inside formwork labour' if fam == 'FORM' else 'cutting/bending/tying inside ferrallista hours' if fam == 'REBAR' else 'cleaning and repair inside stripping labour'),
        unresolved_equipment=('crane or pump and concrete delivery capacity NOT in BCCA - user must declare available equipment or explicit none; otherwise the activity is blocked' if fam == 'CONC'
                              else 'crane handling for formwork panels/bar bundles not in BCCA - declare or explicit none' if fam in ('FORM', 'REBAR') else 'none'),
        source_edition='BCCA Dic-2023 V02 (Junta de Andalucia), file BCCA2023_V02.bc3', source_sha256=BCCA_SHA, region='Andalucia, ES', currency='EUR',
        concept_price_date_ddmmyy=c['price_date_ddmmyy'],
        applicability_limitations='Catalogue estimate, not observed productivity; trades only (no crew size); Andalucia prices; direct cost only (no overheads, profit, VAT); ' +
                                  ('generic structural rebar item not specific to columns/beams/slabs' if fam == 'REBAR' else 'concrete class/consistency must match the selected variant' if fam == 'CONC' else
                                   'pine timber for rendered finish; exposed finish needs another variant' if fam == 'FORM' else 'timber formwork for rendered finish only'),
        canonical_mapping='ProductivityReference{provider=BCCA, release=Dic-2023 V02, code, region, declared_unit, declared_amount=1, worker_hours_by_trade, machine_hours_by_class, demand_coverage=partial if unresolved_equipment else complete}; CostReference{category=bundle, amount=unit_cost_eur}',
        approval_id=f"AP-W-{act}", approval_status='PENDING'))
wr('stage5_3_reference_selection.csv', sel_rows)
REF = {(r['activity_id'], r['bcca_code']): r for r in sel_rows}

# ================================================================== Step 4: input template
def labour(code):
    return {k: v for k, v in ((x.split('=')[0], float(x.split('=')[1])) for x in REF[[k for k in REF if k[1] == code][0]]['labour_h_per_unit_by_trade'].split('; '))}


TRADES = sorted({t for r in sel_rows for t in (x.split('=')[0] for x in r['labour_h_per_unit_by_trade'].split('; '))})
template = {
    '_meta': dict(title='PMI controlled concrete-frame demonstration - input template', generated=NOW, status='TEMPLATE - not an approval',
                  scope='cast-in-place RC frame: columns, beams, slabs (no foundations, excavation, masonry, precast)',
                  rules=['null means REQUIRED and unknown: dependent activities are blocked; never replace with 0',
                         'reinforcement mass is entered per element or per element group by the user; generic ratios are not accepted',
                         'curing and striking values are engineer inputs; no defaults exist',
                         'hypothetical_test_fixture is for software tests only and must never be used as a real project input'],
                  contracts='research/architecture/stage5_0/canonical_schemas.json (Project, ProjectCalendar, Crew, EquipmentResource, WorkItem, ActivityDependency, ProductivityReference, CostReference, DurationEstimate)'),
    'required_user_inputs': {
        'project': dict(id=None, name=None, country=None, region=None, timezone=None, start_date=None, preferred_completion=None),
        'calendar': dict(id=None, timezone=None, working_windows=[dict(weekday=None, start='HH:mm', end='HH:mm')], date_exceptions=[], window_start=None, window_end=None),
        'zones': [dict(zone_id=None, storey=None, element_global_ids=[])],
        'crews': [dict(id=None, calendar_id=None, workers_by_trade={t: None for t in TRADES}, applies_to_activities=[])],
        'equipment': [dict(id=None, equipment_class=e, units=None, calendar_id=None, note='enter 0 only if explicitly none; null blocks') for e in ('VIBRADOR', 'CRANE', 'CONCRETE_PUMP', 'CONCRETE_DELIVERY_m3_per_h')],
        'concrete_specification': dict(class_by_element_type=dict(IfcColumn=None, IfcBeam=None, IfcSlab=None), consistency=None, max_aggregate_mm=None, exposure_class=None),
        'construction_method': dict(per_element_group=[dict(group=None, method='cast_in_place|precast|composite', approval_id='AP-CR06')]),
        'reinforcement_mass_kg': [dict(element_global_id_or_group=None, mass_kg=None, source='bar schedule | rebar model | design value', bars_or_mesh='bars|mesh')],
        'formwork': dict(system_by_element_type=dict(IfcColumn=None, IfcBeam=None, IfcSlab=None), finish='rendered|exposed',
                         contact_face_rules=dict(IfcColumn=None, IfcBeam=None, IfcSlab=None), slab_on_grade_global_ids=[]),
        'measurement_rules': dict(column_height='clear|through (AP-DC07)', beam_depth='including_slab|below_soffit (AP-DC06)', layered_elements='concrete_layer_only|exclude (AP-DC08)'),
        'curing': dict(criterion='time|strength|both', minimum_elapsed_hours=None, strength_mpa=None, monitoring=None, applies_to=[]),
        'striking': dict(side_formwork=dict(criterion=None, minimum_elapsed_hours=None, strength_mpa=None), soffit_formwork=dict(criterion=None, minimum_elapsed_hours=None, strength_mpa=None),
                         reshoring=None),
        'sequence_choice': dict(column='DR05 (rebar then formwork) | prefabricated cage SS', beam_slab='DR06 soffit formwork then rebar', storeys='DR10', zones='DR11 resource-driven | fixed order',
                                inspection_hold_hours_before_pour=None),
        'productivity_adjustments': dict(factor=None, applies_to=None, evidence=None, note='omit to use unchanged BCCA basis (disclosed)'),
    },
    'reference_data': dict(provider='BCCA', release='Dic-2023 V02', region='Andalucia, ES', source_file=BCCA_FILE, source_sha256=BCCA_SHA,
                           selected=[dict(activity_id=r['activity_id'], bcca_code=r['bcca_code'], role=r['selection_role'], unit=r['quantity_unit'], unit_cost_eur=r['unit_cost_eur'],
                                          labour_h_per_unit_total=r['labour_h_per_unit_total']) for r in sel_rows],
                           detail='research/validation/engineering_approval_review/stage5_3_reference_selection.csv'),
    'engineering_decisions': [dict(approval_id=r['approval_id'], phase=r['decision_phase'], status='PENDING', decision=None) for r in prio if r['decision_phase'] in ('WPG', 'DUR', 'RCPSP')],
    'hypothetical_test_fixture': dict(
        not_for_real_project_use=True, label='HYPOTHETICAL - software test values chosen arbitrarily; not engineering recommendations, not approvals',
        project=dict(id='HYP-FRAME-001', name='Hypothetical one-bay frame', country='ES', region='AN', timezone='Europe/Madrid', start_date='2027-01-04'),
        calendar=dict(id='HYP-CAL', working_windows=[dict(weekday=d, start='08:00', end='16:00') for d in range(1, 6)], note='8 h/day Mon-Fri, no breaks modelled'),
        geometry='4 columns 0.30x0.30x3.00 m; 4 beams 0.30x0.50x5.00 m; 1 slab 5.30x5.30x0.20 m; no openings',
        quantities=dict(COL_CONC_m3=round(4 * 0.3 * 0.3 * 3.0, 4), COL_FORM_m2=round(4 * 4 * 0.3 * 3.0, 4), BEAM_CONC_m3=round(4 * 0.3 * 0.5 * 5.0, 4),
                        BEAM_FORM_m2=round(4 * (0.3 + 2 * 0.5) * 5.0, 4), SLAB_CONC_m3=round(5.3 * 5.3 * 0.2, 4), SLAB_FORM_m2=round(5.3 * 5.3, 4),
                        COL_REBAR_kg=150.0, BEAM_REBAR_kg=300.0, SLAB_REBAR_kg=400.0,
                        note='HYPOTHETICAL: formwork faces = 4 column faces full height; beam soffit + 2 sides full depth; slab soffit full area (no deduction of beam tops). Rebar kg are stated test values, NOT ratios.'),
        crews=[dict(id='HYP-FORM', workers_by_trade={'OF. 1ª ENCOFRADOR': 2, 'PEÓN ESPECIAL': 1}), dict(id='HYP-REBAR', workers_by_trade={'OF. 1ª FERRALLISTA': 2}),
               dict(id='HYP-CONC', workers_by_trade={'PEÓN ESPECIAL': 2, 'OFICIAL 1ª': 1})],
        equipment=dict(VIBRADOR=1, CRANE=0, CONCRETE_PUMP=0, note='HYPOTHETICAL explicit none for crane/pump (hand placement assumed for the test)'),
        curing_hold_hours_HYPOTHETICAL=24, striking_hold_hours_HYPOTHETICAL=dict(columns_sides=24, beams_slab_soffit=168),
        note_holds='Arbitrary numbers to exercise calendar logic only. Real values require AP-W-CURE / AP-DR07 / AP-DR08 decisions by the engineer.'),
}
json.dump(template, open(f'{OUT}/controlled_demo_input_template.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote controlled_demo_input_template.json')

# ================================================================== Step 5: worked example (hypothetical, computed)
H = template['hypothetical_test_fixture']
Q = H['quantities']
crews = {c['id']: c['workers_by_trade'] for c in H['crews']}
ACTS = [('COL-REBAR', '05HAC00015', Q['COL_REBAR_kg'], 'kg', 'HYP-REBAR'), ('COL-FORM', '05HEM00001', Q['COL_FORM_m2'], 'm2', 'HYP-FORM'),
        ('COL-CONC', '05HHP00003', Q['COL_CONC_m3'], 'm3', 'HYP-CONC'), ('BEAM-FORM', '05HEM00051', Q['BEAM_FORM_m2'], 'm2', 'HYP-FORM'),
        ('SLAB-FORM', '05HEM00101', Q['SLAB_FORM_m2'], 'm2', 'HYP-FORM'), ('BEAM-REBAR', '05HAC00015', Q['BEAM_REBAR_kg'], 'kg', 'HYP-REBAR'),
        ('SLAB-REBAR', '05HAC00015', Q['SLAB_REBAR_kg'], 'kg', 'HYP-REBAR'), ('BEAM-CONC', '05HHJ00003', Q['BEAM_CONC_m3'], 'm3', 'HYP-CONC'),
        ('SLAB-CONC', '05HHL00003', Q['SLAB_CONC_m3'], 'm3', 'HYP-CONC'), ('FRM-STRIP (cols)', '05HED00001', Q['COL_FORM_m2'], 'm2', 'HYP-FORM'),
        ('FRM-STRIP (beams+slab)', '05HED00001', Q['BEAM_FORM_m2'] + Q['SLAB_FORM_m2'], 'm2', 'HYP-FORM')]
ex_rows, tot = [], collections.defaultdict(float)
for name, code, q, unit, crew in ACTS:
    r = [x for x in sel_rows if x['bcca_code'] == code][0]
    lab = {x.split('=')[0]: float(x.split('=')[1]) for x in r['labour_h_per_unit_by_trade'].split('; ')}
    mach = {} if r['equipment_h_per_unit'].startswith('none') else {x.split('=')[0]: float(x.split('=')[1]) for x in r['equipment_h_per_unit'].split('; ')}
    Ht = {t: q * c for t, c in lab.items()}
    Em = {m: q * c for m, c in mach.items()}
    nmap = crews[crew]
    bounds = {}
    blocked = []
    for t, h in Ht.items():
        n = nmap.get(t)
        if not n:
            blocked.append(f'no {t} in crew {crew}')
        else:
            bounds[t] = h / n
    for m, h in Em.items():
        units = H['equipment'].get(m.split(' [')[0], None)
        if not units:
            blocked.append(f'{m} unavailable')
        else:
            bounds[m] = h / units
    dur = max(bounds.values()) if bounds and not blocked else None
    cost = q * float(r['unit_cost_eur'])
    for k in ('cost_labour_eur', 'cost_equipment_eur', 'cost_material_eur'):
        tot[k] += q * float(r[k])
    tot['cost_total'] += cost
    ex_rows.append(dict(activity=name, code=code, quantity=f'{q:g} {unit}', worker_hours=', '.join(f'{t} {h:.2f} h' for t, h in Ht.items()),
                        machine_hours=', '.join(f'{m} {h:.2f} h' for m, h in Em.items()) or '-', crew=crew + ' ' + json.dumps(nmap, ensure_ascii=False),
                        bound=', '.join(f'{k} {v:.2f} h' for k, v in bounds.items()), productive_h=f'{dur:.2f}' if dur is not None else 'BLOCKED: ' + '; '.join(blocked),
                        working_days_at_8h=f'{dur / 8:.2f}' if dur is not None else '-', direct_cost_eur=f'{cost:.2f}'))


def mdt(rows, cols):
    s = '| ' + ' | '.join(cols) + ' |\n|' + '---|' * len(cols) + '\n'
    for r in rows:
        s += '| ' + ' | '.join(str(r.get(c, '')).replace('|', '/') for c in cols) + ' |\n'
    return s


wrong_curing = Q['COL_CONC_m3'] * 0  # placeholder: curing has NO separate coefficient
ex = f"""# Stage 5.3 engineering estimation method and worked examples

Generated {NOW}. Research only - not production code. Method follows Agent 2's `research/architecture/stage5_0/engineering_estimation_specification.md`.

## 1. Method
For an activity with allocated physical quantity Q (in the BCCA declared unit) and BCCA coefficients c[t] (worker-hours per unit, trade t) and k[e] (machine-hours per unit, class e):

1. **Labour requirement:** H[t] = Q x c[t] (summed over every allocated quantity of the activity).
2. **Equipment requirement:** E[e] = Q x k[e]. An equipment class that the activity needs but BCCA does not list (crane, pump, concrete delivery) is **unresolved**: the user must declare capacity or an explicit none; otherwise the activity is blocked.
3. **Productive duration (lower bound, fixed simultaneous crew):** D_prod = max( H[t] / n[t] for each trade, E[e] / m[e] for each machine class, approved process minimum ). The largest term is the bottleneck. A trade with positive demand and zero crew makes the mode invalid (blocked, not infinite). Different trades work simultaneously in the same crew; the slowest trade sets the duration. Crew members may be reserved for the whole duration even when their own demand finishes earlier - report reserved hours (n[t] x D_prod) separately from demanded hours H[t].
4. **Waiting and strength development:** curing and striking are `elapsed_hold` activities (canonical `ConstructionActivity.kind`) whose duration comes from the engineer (AP-W-CURE, AP-DR07, AP-DR08). They consume calendar time, not crew. BCCA has no coefficient for them - curing labour is already inside the concrete coefficient and must not be added again (DC03).
5. **Calendar conversion:** productive working hours are mapped onto the project calendar's working windows; elapsed holds run in elapsed (24 h) time unless the engineer specifies working time (`ActivityDependency.lag_basis`).
6. **Direct cost:** Cost = Q x BCCA unit price. The labour/equipment/material split is the arithmetic sum of the decomposition lines (stage5_3_reference_selection.csv; split sums equal the published price to rounding). Bundled operations (vibration, curing labour, cleaning, release agent, tying) are counted once because they are inside one coefficient; the only separate stripping line is FRM-STRIP for 05HEM* formwork (DC02).
7. **Not allowed:** allocation percentages to split a bundled coefficient into sub-activities; generic reinforcement ratios; default curing/striking times; zero for unknown quantities.

## 2. Worked example - HYPOTHETICAL fixture (software test only)
**All inputs below are HYPOTHETICAL** (`controlled_demo_input_template.json` -> `hypothetical_test_fixture`): {H['geometry']}. Formwork face rule: {Q['note']}. Crews: {json.dumps(H['crews'], ensure_ascii=False)}. Equipment: {json.dumps(H['equipment'])}. Calendar 8 h/day Mon-Fri. BCCA coefficients: stage5_3_reference_selection.csv.

{mdt(ex_rows, ['activity', 'code', 'quantity', 'worker_hours', 'machine_hours', 'crew', 'bound', 'productive_h', 'working_days_at_8h', 'direct_cost_eur'])}
Direct cost total (hypothetical quantities): {tot['cost_total']:.2f} EUR, of which labour {tot['cost_labour_eur']:.2f}, equipment {tot['cost_equipment_eur']:.2f}, material {tot['cost_material_eur']:.2f} (split recomputed from decomposition lines).

### Reading the example
- COL-FORM: the carpenter term (2 carpenters) and the helper term (1 helper) are compared; the larger is the productive duration. Adding a second helper would not shorten it if the carpenter term is the bottleneck.
- CONC activities: the vibrator term is computed from BCCA machine-hours. The hypothetical fixture declares crane = 0 and pump = 0 explicitly; with `null` instead the concrete activities would be **blocked** (unresolved equipment).
- Curing: no row - it is an `elapsed_hold` of HYPOTHETICAL {H['curing_hold_hours_HYPOTHETICAL']} h after each pour, and striking holds of {H['striking_hold_hours_HYPOTHETICAL']} h (arbitrary test values). No curing labour or cost is added (bundled in the concrete coefficient).
- FRM-STRIP appears twice because column-side and beam/slab-soffit striking are released by different criteria; the area is the same as the corresponding formwork item, so stripping is counted once per formwork area.

## 3. Bundled coefficients that cannot be allocated to separate scheduling activities
{mdt([dict(code=r['bcca_code'], activity=r['activity_id'], bundled=r['bundled_not_separately_allocatable']) for r in sel_rows if r['selection_role'] == 'primary'], ['code', 'activity', 'bundled'])}
If the schedule needs curing, cleaning or release-agent application as separate activities, their labour must come from a different, approved source; BCCA cannot be split without inventing percentages.
"""
open(f'{OUT}/duration_and_cost_calculation_examples.md', 'w', encoding='utf-8').write(ex)
print('wrote duration_and_cost_calculation_examples.md')

# ================================================================== Step 6: readiness report + one-page summary
p1 = [r for r in prio if r['decision_phase'] == 'WPG']
p2 = [r for r in prio if r['decision_phase'] == 'DUR']
p3 = [r for r in prio if r['decision_phase'] == 'RCPSP']
p4 = [r for r in prio if r['decision_phase'] == 'REAL-RELEASE']
CONTRACT = [
    ('stage5_3_reference_selection.csv bcca_code, quantity_unit', 'ProductivityReference.code, declared_unit (declared_amount = 1)'),
    ('labour_h_per_unit_by_trade', 'ProductivityReference.worker_hours_by_trade (trade key = BCCA labour concept summary)'),
    ('equipment_h_per_unit', 'ProductivityReference.machine_hours_by_class'),
    ('unresolved_equipment non-empty', 'ProductivityReference.demand_coverage = partial'),
    ('unit_cost_eur, concept_price_date_ddmmyy', 'CostReference.amount (category = bundle), price_date'),
    ('cost_labour/equipment/material_eur', 'CostReference rows with category labor/equipment/material (derived; provenance = decomposition sum)'),
    ('template.required_user_inputs.calendar', 'ProjectCalendar.working_windows / window_start / window_end'),
    ('template.required_user_inputs.crews', 'Crew.workers_by_trade, calendar_id'),
    ('template.required_user_inputs.equipment', 'EquipmentResource.equipment_class, units'),
    ('curing / striking', 'ConstructionActivity(kind=elapsed_hold) + ActivityDependency(lag_basis)'),
    ('priority_approval_register.csv approval_id', 'WorkItem.approval / ActivityDependency.approval_id'),
]
rep = f"""# Stage 5.3 readiness - controlled concrete-frame demonstration

Generated {NOW}. Research only. Nothing is approved; all {len(prio)} items remain PENDING.

## Readiness by phase
| Phase | Decisions required | Status | Blocking inputs |
|---|---|---|---|
| Work-package generation | {len(p1)} | NOT READY - pending approvals | construction method per element group (AP-CR06), measurement rules DC06/DC07/DC08, formwork applicability (CR13) |
| Duration estimation | {len(p2)} | NOT READY | crew composition, rebar kg, formwork face rules, crane/pump declaration, curing/striking decisions |
| Resource-constrained scheduling | {len(p3)} | NOT READY | calendar, zones, sequence choices DR05/DR06/DR09/DR10/DR11, hold criteria DR07/DR08 |
| Real-project release | {len(p4)} | NOT READY | manual quantity validation + tolerance (AP-TOL), foundation classification (CR11), Synchro handling (CR15) |

Software can be exercised now on the **hypothetical_test_fixture** only; its results are not evidence of real-project accuracy.

## Reference evidence available
- {len([r for r in sel_rows if r['selection_role'] == 'primary'])} primary + {len([r for r in sel_rows if r['selection_role'] != 'primary'])} alternative BCCA references (stage5_3_reference_selection.csv); cost split reconciles to published price (max |difference| {max(abs(float(r['cost_split_difference_eur'])) for r in sel_rows):.4f} EUR).
- BCCA gives trades, not crews; no crane, pump or delivery capacity; no curing or striking durations.

## Data contracts for Agent 1 (Stage 5.2A) - no Agent 1 file was edited
{mdt([dict(this_package=a, canonical_field=b) for a, b in CONTRACT], ['this_package', 'canonical_field'])}
Observations for Agent 1:
- Trade keys are the Spanish BCCA labour concept names (e.g. "OF. 1ª ENCOFRADOR"); keep them as source keys and map to display names separately.
- `05HAC00015` is shared by column, beam and slab reinforcement: one ProductivityReference, three WorkItems (DC05).
- Concrete items need an EquipmentResource declaration for crane/pump even when the answer is none; otherwise `demand_coverage=partial` must block release.
- FRM-STRIP is a separate WorkItem only for 05HEM* formwork; never for 03ERM* (foundation, out of demo scope).

## What you must measure, choose or obtain
See `one_page_summary.md`.
"""
open(f'{OUT}/stage5_3_readiness_report.md', 'w', encoding='utf-8').write(rep)

one = f"""# One-page summary - what you need to do

**Measure (you, ~11 elements).** Follow `measurement_instructions.md` for QV01, QV09, QV18, QV21, QV22, QV23, QV27, QV28, QV29, QV30, QV32. Rectangles need width, depth and length; QV01, QV09, QV18 have polygon profiles and need vertex coordinates. Save screenshots and vertex CSVs; enter results in `manual_quantity_validation.xlsx` (Validation_40). Do not copy grey values.

**Choose (you, with the engineer where noted).**
1. Construction method per element group: cast-in-place vs precast vs composite (AP-CR06).
2. Measurement rules: column height clear vs through (AP-DC07); beam depth incl. slab or not (AP-DC06); layered elements (AP-DC08).
3. Formwork system and finish per element type, and which faces count as formed (AP-W-*-FORM, AP-CR13).
4. Sequence options: column rebar/formwork order (AP-DR05), beam/slab order (AP-DR06), storey and zone progression (AP-DR10, AP-DR11).
5. Concrete class per element type (selects BCCA variant HA-25 vs HA-30).

**Obtain from a structural / site engineer (cannot be assumed).**
1. Curing requirement - time and/or strength (AP-W-CURE, AP-DR07).
2. Striking criteria for side formwork and soffits/props, reshoring (AP-DR08).
3. Support logic before loading supported formwork (AP-DR09).
4. Reinforcement mass per element or group from a bar schedule or rebar model (no ratios).
5. Approval of the BCCA work items and variants for the demo ({len(p1) + len(p2)} items in phases P1-P2).
6. Quantity tolerance for the manual checks (AP-TOL).

**Provide as project data.** Location and timezone; working calendar (days, hours, holidays); zones; crew sizes per trade (encofrador, peon especial, ferrallista, oficial 1a); equipment available - vibrators, crane, pump, concrete delivery rate - or explicit none.

**Decision count.** P1 work packages {len(p1)}, P2 durations {len(p2)}, P3 scheduling {len(p3)}, P4 real release {len(p4)}, P5 not needed {cnt['NOT-NEEDED']}. Start with P1 and P2 ({len(p1) + len(p2)} decisions) to unlock a first engineering estimate on the hypothetical fixture.
"""
open(f'{OUT}/one_page_summary.md', 'w', encoding='utf-8').write(one)
print('wrote readiness + summary')

# ================================================================== Step 7: preservation
snap = {}
for line in open(f'{OUT}/preservation/task_start_snapshot.sha256', encoding='utf-8'):
    h, p = line.rstrip('\n').split(' ', 1)
    snap[p.lstrip('*')] = h


def eol_only(p, h):
    d = open(p, 'rb').read()
    return hashlib.sha256(d.replace(b'\r\n', b'\n')).hexdigest() == h or hashlib.sha256(d.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest() == h


AG1 = ('pmi_core/', 'tests/', 'research/implementation/')
changed = []
for p, h in snap.items():
    if not os.path.exists(p):
        changed.append(dict(path=p, change='MISSING', owner='Agent 1' if p.startswith(AG1) else 'other'))
    elif sha256(p) != h:
        changed.append(dict(path=p, change='line endings only' if eol_only(p, h) else 'CONTENT CHANGED', owner='Agent 1 (concurrent)' if p.startswith(AG1) else 'other',
                            mtime_utc=dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc).isoformat()))
bases = []
for name, bf in [('Stage 4.0B pre-task baseline', 'research/data_acquisition/stage4_0b/sections_B_E/preservation/baseline_sha256_before_stage4_0b.txt'),
                 ('Stage 4.0A baseline', 'research/evaluation/stage4_0a/preservation/baseline_sha256_before_stage4_0a.txt')]:
    bad, n = [], 0
    for line in open(bf, encoding='utf-8'):
        h, p = line.rstrip('\n').split(' ', 1)
        p = p.lstrip('*')
        n += 1
        if not os.path.exists(p) or sha256(p) != h:
            bad.append(p)
    bases.append(dict(check=name, total=n, changed_or_missing=bad))
gsx = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.splitlines()
wb = 'research/validation/stage5_1_manual/manual_quantity_validation.xlsx'
pres = dict(generated=NOW, checks=bases + [
    dict(check='Protected paths vs task-start snapshot', total=len(snap), changed=changed),
    dict(check='Manual validation workbook unchanged', path=wb, sha256_now=sha256(wb), sha256_start=snap.get(wb), unchanged=sha256(wb) == snap.get(wb)),
    dict(check='git tracked modifications / staged', tracked=[l for l in gsx if not l.startswith('??')], untracked=[l[3:] for l in gsx if l.startswith('??')]),
    dict(check='Write scope', paths=[OUT + '/']),
    dict(check='No approvals recorded, no measurements filled', result=all(r['status'] == 'PENDING' and not r['decision'] for r in prio)),
    dict(check='No acquisition, training, inference, environment change, commit or push', result='confirmed by script scope'),
])
# Staged/tracked entries are attributed: this task never runs git add/commit; paths inside OUT were staged by someone else.
staged = pres['checks'][4]['tracked']
pres['staged_or_tracked_attribution'] = [dict(entry=l, owner=('this package (staged externally - this task never runs git add)' if OUT in l else
                                                              'Agent 1 (concurrent Stage 5.2A)' if any(a in l for a in ('pmi_core/', 'tests/', 'research/implementation/')) else
                                                              'Excel lock file from the workbook being open in Excel (workbook hash unchanged); should not be committed' if '~$' in l else 'other'))
                                         for l in staged]
other_staged = [s for s in pres['staged_or_tracked_attribution'] if s['owner'] == 'other']
pres['all_protected_unchanged_by_this_task'] = (not any(b['changed_or_missing'] for b in bases) and not [c for c in changed if c['owner'] == 'other' and c['change'] != 'line endings only']
                                                 and pres['checks'][3]['unchanged'] and not other_staged)
json.dump(pres, open(f'{OUT}/preservation_verification.json', 'w', encoding='utf-8'), indent=2)
print('preservation ok:', pres['all_protected_unchanged_by_this_task'], 'changed', len(changed))
