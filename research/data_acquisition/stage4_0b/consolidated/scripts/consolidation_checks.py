"""Stage 4.0B consolidation - read-only checks that resolve evidence ambiguities.

Run from repo root:
    .venv/Scripts/python.exe -I research/data_acquisition/stage4_0b/consolidated/scripts/consolidation_checks.py
Writes JSON/CSV under data/processed/candidates/stage4_0b/consolidated/. Never writes to an IFC.
Produces NO ground truth: geometry values are derivations, authored values are copies.
"""
import collections, csv, json, os, re, sys
import numpy as np
import ifcopenshell, ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.unit as uu

sys.stdout.reconfigure(encoding='utf-8')
csv.field_size_limit(10 ** 9)
OUT = 'data/processed/candidates/stage4_0b/consolidated'
os.makedirs(OUT, exist_ok=True)
MEN = 'data/raw/BIM Spatial Models for Construction Dependency Inf'
SCH_AP = 'data/raw/SCHEPENDOMLAAN/As Planned models'
MODELS = {
    'SCH-design': 'data/raw/SCHEPENDOMLAAN/Design model IFC/IFC Schependomlaan.ifc',
    'SCH-synchro': f'{SCH_AP}/IFC Schependomlaan incl planningsdata.ifc',
    'RST': 'data/raw/Restage_IP_ALL_MULTI_001.ifc',
    'MEN-RES': f'{MEN}/BIM_residential_building_data/BIM_residential_building.ifc',
    'MEN-RAC': f'{MEN}/rac_advanced_sample_project_data/rac_advanced_sample_project.ifc',
    'MEN-MTG': f'{MEN}/BIM_meeting_room_data/BIM_meeting_room.ifc',
    'B4D': 'data/raw/4DBenchmarkBim.ifc',
}
R = {}

# ---------------------------------------------------------------- (a) Mendeley linkage, exact / unique / ambiguous
link = []
for proj, ifc in [('BIM_meeting_room_data', 'BIM_meeting_room.ifc'), ('BIM_residential_building_data', 'BIM_residential_building.ifc'),
                  ('rac_advanced_sample_project_data', 'rac_advanced_sample_project.ifc')]:
    f = ifcopenshell.open(os.path.join(MEN, proj, ifc))
    el = collections.Counter(e.Name for e in f.by_type('IfcElement'))
    prod = collections.Counter(e.Name for e in f.by_type('IfcProduct'))
    for fn, cols in [('ifc_space_centroids_data.csv', ['Element Name']), ('spatial_relationships_detailed.csv', ['name1', 'name2'])]:
        with open(os.path.join(MEN, proj, fn), encoding='utf-8-sig', errors='replace', newline='') as fh:
            rows = list(csv.DictReader(fh))
        names = {r[c].strip() for r in rows for c in cols}
        exact = {n for n in names if n in el}
        uniq = {n for n in exact if el[n] == 1}
        amb = exact - uniq
        other_product = {n for n in names - exact if n in prod}
        link.append(dict(project=proj, csv=fn, csv_rows=len(rows), distinct_csv_names=len(names),
                         exact_ifcelement_name_match=len(exact), exact_pct=round(100 * len(exact) / len(names), 1),
                         unique_match=len(uniq), unique_pct=round(100 * len(uniq) / len(names), 1),
                         ambiguous_match=len(amb), ambiguous_ifc_elements_behind=sum(el[n] for n in amb),
                         matches_non_element_product=len(other_product), unmatched=len(names - exact - other_product),
                         unmatched_examples='; '.join(sorted(names - exact - other_product)[:5]),
                         ambiguous_examples='; '.join(sorted(amb)[:3])))
R['mendeley_linkage'] = link
with open(f'{OUT}/mendeley_name_linkage_detail.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(link[0])); w.writeheader(); w.writerows(link)

# ---------------------------------------------------------------- (b) SCH weekly snapshots vs full as-planned model
def _dt(x):
    if x is None:
        return None
    if isinstance(x, str):
        return x
    if x.is_a('IfcDateAndTime'):  # IFC2X3 dates are entity instances: compare their values, not entity ids
        d, t = x.DateComponent, x.TimeComponent
        return f'{d.YearComponent:04d}-{d.MonthComponent:02d}-{d.DayComponent:02d}T{t.HourComponent:02d}:{t.MinuteComponent:02d}'
    return str(x)


snap = []
for fn in sorted(os.listdir(SCH_AP)):
    if not fn.lower().endswith('.ifc'):
        continue
    f = ifcopenshell.open(os.path.join(SCH_AP, fn))
    tasks = collections.Counter()
    for rel in f.by_type('IfcRelAssignsTasks'):
        tc = rel.TimeForTask
        for t in rel.RelatedObjects:
            if t.is_a('IfcTask'):
                tasks[(t.Name, _dt(tc.ScheduleStart), _dt(tc.ScheduleFinish), _dt(tc.ActualStart), _dt(tc.ActualFinish))] += 1
    names = collections.Counter(e.Name for e in f.by_type('IfcElement'))
    task_guids = {t.GlobalId for t in f.by_type('IfcTask')}
    snap.append(dict(file=fn, tasks=tasks, names=names, task_guids=task_guids))
full = [s for s in snap if s['file'].startswith('IFC ')][0]
snap_rows = []
for s in snap:
    snap_rows.append(dict(file=s['file'], tasks=sum(s['tasks'].values()),
                          identical_task_names_and_planned_dates_to_full_model=(s['tasks'] == full['tasks']),
                          tasks_not_in_full_model=sum((s['tasks'] - full['tasks']).values()),
                          task_guids_shared_with_full_model=len(s['task_guids'] & full['task_guids']),
                          elements=sum(s['names'].values()),
                          element_names_subset_of_full=all(full['names'][k] >= v for k, v in s['names'].items()),
                          tasks_with_actual_dates=sum(c for k, c in s['tasks'].items() if k[3] or k[4])))
R['sch_snapshots'] = snap_rows
print('snapshots', [(r['file'][:14], r['identical_task_names_and_planned_dates_to_full_model'], r['elements']) for r in snap_rows])

# ---------------------------------------------------------------- (c) Restage task semantics
f = ifcopenshell.open(MODELS['RST'])
rt = []
for t in f.by_type('IfcTask'):
    tt = t.TaskTime
    rt.append(dict(global_id=t.GlobalId, name=t.Name, identification=t.Identification, predefined=str(t.PredefinedType), is_milestone=t.IsMilestone,
                   status=t.Status, work_method=t.WorkMethod, description=t.Description,
                   task_time={a: str(getattr(tt, a)) for a in tt.get_info() if a not in ('id', 'type') and getattr(tt, a) is not None} if tt else None,
                   assigned_products=sum(1 for r in f.by_type('IfcRelAssignsToProduct') if t in r.RelatedObjects),
                   psets=ue.get_psets(t)))
R['restage_tasks'] = rt
R['restage_work_schedule'] = [{k: str(v) for k, v in w.get_info().items() if v is not None and k not in ('OwnerHistory',)} for w in f.by_type('IfcWorkSchedule')]
R['restage_nests'] = [(r.RelatingObject.is_a(), r.RelatingObject.Name, [o.Name for o in r.RelatedObjects]) for r in f.by_type('IfcRelNests')]
del f

# ---------------------------------------------------------------- (d)(e) duplicate GUIDs and explicit quantity units per model
dup, qunits = {}, {}
for k, p in MODELS.items():
    f = ifcopenshell.open(p)
    c = collections.Counter(r.GlobalId for r in f.by_type('IfcRoot'))
    dup[k] = [dict(global_id=g, entities=[f'{e.is_a()}#{e.id()} {getattr(e, "Name", "")}' for e in f.by_type('IfcRoot') if e.GlobalId == g]) for g, n in c.items() if n > 1]
    q = f.by_type('IfcPhysicalSimpleQuantity')
    over = [x for x in q if x.Unit is not None]
    qunits[k] = dict(physical_quantities=len(q), with_explicit_unit=len(over),
                     explicit_units=dict(collections.Counter(f'{x.is_a()}:{getattr(x.Unit, "Prefix", "") or ""}{getattr(x.Unit, "Name", x.Unit.is_a())}' for x in over).most_common(6)),
                     project_length_scale=uu.calculate_unit_scale(f), project_area_scale=uu.calculate_unit_scale(f, 'AREAUNIT'),
                     project_volume_scale=uu.calculate_unit_scale(f, 'VOLUMEUNIT'), project_mass_scale=uu.calculate_unit_scale(f, 'MASSUNIT'))
    del f
R['duplicate_globalids'] = dup
R['quantity_units'] = qunits
print('dups', {k: len(v) for k, v in dup.items()})

# ---------------------------------------------------------------- (f) quantity validation sample
# cast concrete terms incl. strength classes (Restage names materials 'C35/45', described 'Betonguete')
CONC = __import__('re').compile(r'beton|concrete|hormig|混凝土|砼|\bC\d{2}/\d{2}\b|\bHA-\d', __import__('re').I)
# masonry / aerated-concrete blocks and panels are NOT cast concrete (cellenbeton, 砌块 block, 加气 aerated, 条板 panel)
CMU = __import__('re').compile(r'masonry|block|mw-|metsel|cellenbeton|gasbeton|砌块|加气|条板|\bcmu\b', __import__('re').I)
s = ifcopenshell.geom.settings()
s.set('use-world-coords', True)


def materials(el, lscale):
    m = ue.get_material(el, should_skip_usage=False)
    if m is None:
        return 'none', [], None
    kind = m.is_a()
    lay = []
    if m.is_a('IfcMaterialLayerSetUsage'):
        m2 = m.ForLayerSet
    else:
        m2 = m
    if m2.is_a('IfcMaterialLayerSet'):
        for l in m2.MaterialLayers:
            lay.append((l.Material.Name if l.Material else '?', round(l.LayerThickness * lscale, 5)))
        tot = sum(t for _, t in lay)
        conc = sum(t for n, t in lay if CONC.search(n) and not CMU.search(n))
        return kind, lay, (round(conc / tot, 4) if tot else None)
    if m2.is_a('IfcMaterial'):
        return kind, [(m2.Name, None)], None
    if m2.is_a('IfcMaterialList'):
        return kind, [(x.Name, None) for x in m2.Materials], None
    if m2.is_a('IfcMaterialConstituentSet'):
        return kind, [(c.Material.Name if c.Material else '?', None) for c in (m2.MaterialConstituents or [])], None
    if m2.is_a('IfcMaterialProfileSetUsage') or m2.is_a('IfcMaterialProfileSet'):
        ps = m2.ForProfileSet if m2.is_a('IfcMaterialProfileSetUsage') else m2
        return kind, [(p.Material.Name if p.Material else '?', None) for p in ps.MaterialProfiles], None
    return kind, [], None


def edge_manifold(g):
    v = np.asarray(g.verts, dtype=float).reshape(-1, 3)
    fcs = np.asarray(g.faces, dtype=int).reshape(-1, 3)
    if len(fcs) == 0:
        return False, 0
    key = np.round(v / 1e-6).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    t = inv[fcs]
    e = np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    bad = int((cnt != 2).sum())
    return bad == 0, bad


def extrusion(el, lscale):
    out = []
    if not el.Representation:
        return ''
    for rep in el.Representation.Representations:
        if rep.RepresentationIdentifier != 'Body':
            continue
        items = list(rep.Items)
        while items:
            it = items.pop()
            if it.is_a('IfcMappedItem'):
                items.extend(it.MappingSource.MappedRepresentation.Items)
            elif it.is_a('IfcBooleanResult'):
                out.append('boolean(clipping/opening)')
                items.append(it.FirstOperand)
            elif it.is_a('IfcExtrudedAreaSolid'):
                pr = it.SweptArea
                dims = ''
                if pr.is_a('IfcRectangleProfileDef'):
                    dims = f' {pr.XDim * lscale:.4g}x{pr.YDim * lscale:.4g} m'
                elif pr.is_a('IfcCircleProfileDef'):
                    dims = f' r={pr.Radius * lscale:.4g} m'
                out.append(f'extrusion {pr.is_a()}{dims} depth {it.Depth * lscale:.4g} m')
            else:
                out.append(it.is_a())
    return '; '.join(out[:4])


ROLES = {'SCH-design': 'development', 'RST': 'independent demonstrator validation', 'MEN-RES': 'geometry robustness', 'SCH-synchro': 'interoperability (same project)'}
PER = 4
sample = []
SCH_NAMES = set()
SCH_IDS = set()
for k in ('SCH-design', 'RST', 'MEN-RES', 'SCH-synchro'):
    f = ifcopenshell.open(MODELS[k])
    ls = uu.calculate_unit_scale(f)
    vs = uu.calculate_unit_scale(f, 'VOLUMEUNIT')
    for cls in ('IfcFooting', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall'):
        cand = []
        for el in sorted(f.by_type(cls), key=lambda e: e.GlobalId):
            kind, lay, frac = materials(el, ls)
            names = ' | '.join(n for n, _ in lay)
            if k == 'SCH-synchro':
                # Synchro export drops materials and regenerates GUIDs: pick the same-named elements as the design-model sample
                mm = re.match(r'^(.*)_\(#(\d+)\)$', el.Name or '')
                if mm and int(mm.group(2)) in SCH_IDS:
                    cand.append((el, kind, lay, frac))
            elif CONC.search(names) and not CMU.search(names):
                cand.append((el, kind, lay, frac))
        if not cand:
            continue
        # deterministic spread: prefer one layered element if present, then evenly spaced picks
        lay_first = [c for c in cand if len(c[2]) > 1][:1]
        step = max(1, len(cand) // PER)
        picks = lay_first + [c for c in cand[::step] if c not in lay_first]
        for el, kind, lay, frac in picks[:PER]:
            q = ue.get_psets(el, qtos_only=True)
            flat = {kk.split(']]')[-1].replace(' ', ''): vv for p in ue.get_psets(el, psets_only=True).values() for kk, vv in p.items() if ']]' in kk}
            nv = next((v.get('NetVolume') for v in q.values() if v.get('NetVolume')), None) or flat.get('NetVolume')
            gv = next((v.get('GrossVolume') for v in q.values() if v.get('GrossVolume')), None) or flat.get('GrossVolume')
            src = 'IfcElementQuantity' if any(v.get('NetVolume') or v.get('GrossVolume') for v in q.values()) else ('flattened export key' if (flat.get('NetVolume') or flat.get('GrossVolume')) else 'none')
            row = dict(model_key=k, design_model_link=(f'design STEP #{re.match(r"^.*_\(#(\d+)\)$", el.Name).group(1)} via name suffix' if k == 'SCH-synchro' else ''), role=ROLES[k], ifc_path=MODELS[k], global_id=el.GlobalId, name=el.Name, ifc_class=cls,
                       predefined_type=str(getattr(el, 'PredefinedType', None)),
                       storey=(lambda st: st.Name if st else None)(ue.get_container(el)),
                       material_association=kind, material_layers=json.dumps(lay, ensure_ascii=False),
                       concrete_layer_thickness_fraction=frac,
                       authored_volume_source=src, authored_net_volume_m3=round(nv * vs, 6) if nv else '', authored_gross_volume_m3=round(gv * vs, 6) if gv else '',
                       body_geometry=extrusion(el, ls))
            try:
                sh = ifcopenshell.geom.create_shape(s, el)
                g = sh.geometry
                import ifcopenshell.util.shape as us
                v = np.asarray(g.verts).reshape(-1, 3)
                row['geometry_volume_m3'] = round(us.get_volume(g), 6)
                row['geometry_total_surface_m2'] = round(us.get_area(g), 6)
                ext = v.max(0) - v.min(0)
                row['world_bbox_extent_m'] = f'{ext[0]:.3f} x {ext[1]:.3f} x {ext[2]:.3f}'
                closed, bad = edge_manifold(g)
                row['edge_manifold_closed'] = closed
                row['non_manifold_or_open_edges'] = bad
                ref = nv or gv
                row['ratio_geometry_to_authored'] = round(row['geometry_volume_m3'] / (ref * vs), 4) if ref else ''
                if frac is not None:
                    row['layer_based_concrete_volume_m3_DERIVED'] = round(row['geometry_volume_m3'] * frac, 6)
            except Exception as e:  # noqa
                row['geometry_status'] = f'fail {type(e).__name__}'
            sample.append(row)
            if k == 'SCH-design':
                SCH_NAMES.add(el.Name)
                SCH_IDS.add(el.id())
    del f
R['sample_size'] = len(sample)
cols = list(dict.fromkeys(c for r in sample for c in r))
with open(f'{OUT}/quantity_validation_sample_raw.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(sample)
for sr in R['sch_snapshots']:
    pass
json.dump(R, open(f'{OUT}/consolidation_checks.json', 'w', encoding='utf-8'), indent=1, default=str, ensure_ascii=False)
print('sample', len(sample), 'closed', sum(1 for r in sample if r.get('edge_manifold_closed') is True))
