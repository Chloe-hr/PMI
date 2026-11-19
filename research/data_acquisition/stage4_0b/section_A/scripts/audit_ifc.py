"""Stage 4.0B Section A - read-only IFC evidence audit of ONE file.

Usage (repo root):
    .venv/Scripts/python.exe -I research/data_acquisition/stage4_0b/section_A/scripts/audit_ifc.py <ifc_path> <out_json>

Opens the model with IfcOpenShell in memory only; never writes to the IFC.
Records what is *authored* in the file (entities, quantities, properties, relationships).
Geometry is NOT evaluated here (see geometry_check.py for sampled checks).
"""
import collections, json, os, re, sys, time, hashlib
import ifcopenshell
import ifcopenshell.util.element as ue
import ifcopenshell.util.unit as uu

path, out = sys.argv[1], sys.argv[2]
t0 = time.time()
h = hashlib.sha256()
with open(path, 'rb') as fh:
    for b in iter(lambda: fh.read(1 << 20), b''):
        h.update(b)
f = ifcopenshell.open(path)
R = dict(path=path.replace('\\', '/'), bytes=os.path.getsize(path), sha256=h.hexdigest(), schema=f.schema)

# ---------------- header / application
hdr = f.header
try:
    fn = hdr.file_name
    R['header_originating_system'] = fn.originating_system
    R['header_preprocessor'] = fn.preprocessor_version
    R['header_timestamp'] = fn.time_stamp
    R['header_author'] = list(fn.author) if fn.author else []
    R['header_organization'] = list(fn.organization) if fn.organization else []
except Exception as e:  # noqa
    R['header_error'] = str(e)
try:
    R['header_description'] = list(hdr.file_description.description)
except Exception:
    pass
R['applications'] = sorted({f'{a.ApplicationFullName} {a.Version}' for a in f.by_type('IfcApplication')})

proj = f.by_type('IfcProject')
R['project_name'] = [p.Name for p in proj]
R['project_longname'] = [getattr(p, 'LongName', None) for p in proj]
sites = f.by_type('IfcSite')
R['site_names'] = [s.Name for s in sites]
R['site_refs'] = [[list(s.RefLatitude) if s.RefLatitude else None, list(s.RefLongitude) if s.RefLongitude else None] for s in sites]
R['site_address'] = [str(s.SiteAddress.AddressLines) if getattr(s, 'SiteAddress', None) else None for s in sites]
R['building_names'] = [b.Name for b in f.by_type('IfcBuilding')]
storeys = f.by_type('IfcBuildingStorey')
R['storeys'] = [dict(name=s.Name, elevation=s.Elevation) for s in storeys]

# ---------------- units
units = []
for ua in f.by_type('IfcUnitAssignment'):
    for u in ua.Units:
        if u.is_a('IfcSIUnit'):
            units.append(dict(type=u.UnitType, kind='SI', prefix=u.Prefix, name=u.Name))
        elif u.is_a('IfcConversionBasedUnit'):
            cf = u.ConversionFactor
            units.append(dict(type=u.UnitType, kind='conversion', name=u.Name,
                              factor=cf.ValueComponent.wrappedValue if cf else None,
                              base=(cf.UnitComponent.Name if cf and cf.UnitComponent.is_a('IfcSIUnit') else None)))
        elif u.is_a('IfcNamedUnit'):
            units.append(dict(type=getattr(u, 'UnitType', None), kind=u.is_a()))
R['units'] = units
try:
    R['length_unit_scale_to_m'] = uu.calculate_unit_scale(f)
except Exception as e:  # noqa
    R['length_unit_scale_to_m'] = f'error {e}'
for ut in ('AREAUNIT', 'VOLUMEUNIT', 'MASSUNIT'):
    try:
        R[f'{ut.lower()}_scale_to_si'] = uu.calculate_unit_scale(f, ut)
    except Exception as e:  # noqa
        R[f'{ut.lower()}_scale_to_si'] = f'error {e}'

# ---------------- GlobalIds
roots = f.by_type('IfcRoot')
gids = [r.GlobalId for r in roots]
rx = re.compile(r'^[0-3][0-9A-Za-z_$]{21}$')
R['ifcroot_count'] = len(gids)
R['globalid_duplicates'] = len(gids) - len(set(gids))
R['globalid_invalid_format'] = sum(1 for g in gids if not g or not rx.match(g))

# ---------------- entity counts
CLASSES = ['IfcFooting', 'IfcPile', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall', 'IfcCurtainWall', 'IfcMember', 'IfcPlate', 'IfcStair', 'IfcStairFlight',
           'IfcRamp', 'IfcRoof', 'IfcCovering', 'IfcDoor', 'IfcWindow', 'IfcRailing', 'IfcBuildingElementProxy', 'IfcReinforcingBar', 'IfcReinforcingMesh',
           'IfcTendon', 'IfcSpace', 'IfcOpeningElement', 'IfcBuildingStorey', 'IfcElementAssembly']
cnt = {}
for c in CLASSES:
    try:
        cnt[c] = len(f.by_type(c))
    except Exception:
        cnt[c] = 'n/a in schema'
cnt['IfcWallStandardCase'] = len(f.by_type('IfcWallStandardCase')) if f.schema in ('IFC2X3', 'IFC4') else 'n/a'
cnt['IfcElement_total'] = len(f.by_type('IfcElement'))
R['entity_counts'] = cnt

# ---------------- relationships
REL = ['IfcRelContainedInSpatialStructure', 'IfcRelAggregates', 'IfcRelAssociatesMaterial', 'IfcRelDefinesByType', 'IfcRelDefinesByProperties',
       'IfcRelConnectsElements', 'IfcRelConnectsPathElements', 'IfcRelConnectsWithRealizingElements', 'IfcRelSpaceBoundary', 'IfcRelVoidsElement',
       'IfcRelFillsElement', 'IfcRelNests', 'IfcRelAssignsToProduct', 'IfcRelAssignsToProcess', 'IfcRelAssignsToControl', 'IfcRelAssignsToResource',
       'IfcRelAssignsToGroup', 'IfcRelSequence', 'IfcRelAssociatesClassification', 'IfcRelInterferesElements']
rel = {}
for c in REL:
    try:
        rel[c] = len(f.by_type(c))
    except Exception:
        rel[c] = 'n/a in schema'
R['relationship_counts'] = rel
R['classification_systems'] = sorted({(c.Name or '') + ' ' + str(getattr(c, 'Edition', '') or '') for c in f.by_type('IfcClassification')})

# ---------------- schedule entities
def safe(c):
    try:
        return f.by_type(c)
    except Exception:
        return []

tasks = safe('IfcTask')
tt = safe('IfcTaskTime')
S = dict(IfcTask=len(tasks), IfcTaskTime=len(tt), IfcWorkSchedule=len(safe('IfcWorkSchedule')), IfcWorkPlan=len(safe('IfcWorkPlan')),
         IfcScheduleTimeControl=len(safe('IfcScheduleTimeControl')), IfcLaborResource=len(safe('IfcLaborResource')),
         IfcConstructionEquipmentResource=len(safe('IfcConstructionEquipmentResource')), IfcCrewResource=len(safe('IfcCrewResource')),
         IfcConstructionMaterialResource=len(safe('IfcConstructionMaterialResource')), IfcLagTime=len(safe('IfcLagTime')))
for a in ('ScheduleStart', 'ScheduleFinish', 'ScheduleDuration', 'ActualStart', 'ActualFinish', 'ActualDuration'):
    S[f'TaskTime_with_{a}'] = sum(1 for x in tt if getattr(x, a, None))
stc = safe('IfcScheduleTimeControl')  # IFC2X3
for a in ('ScheduleStart', 'ScheduleFinish', 'ActualStart', 'ActualFinish', 'ScheduleDuration', 'ActualDuration'):
    if stc:
        S[f'ScheduleTimeControl_with_{a}'] = sum(1 for x in stc if getattr(x, a, None))
seq = safe('IfcRelSequence')
S['sequence_types'] = dict(collections.Counter(str(getattr(s, 'SequenceType', None)) for s in seq))
S['sequence_with_lag'] = sum(1 for s in seq if getattr(s, 'TimeLag', None) or getattr(s, 'TimeLag', None) == 0)
# products assigned to tasks
assigned = set()
for r in safe('IfcRelAssignsToProcess'):
    if r.RelatingProcess and r.RelatingProcess.is_a('IfcTask'):
        for o in r.RelatedObjects:
            if o.is_a('IfcProduct'):
                assigned.add(o.id())
for r in safe('IfcRelAssignsToProduct'):  # task -> product direction
    if r.RelatingProduct is not None:
        for o in r.RelatedObjects:
            if o.is_a('IfcTask'):
                assigned.add(r.RelatingProduct.id())
S['products_assigned_to_tasks'] = len(assigned)
S['task_names_sample'] = [t.Name for t in tasks[:15]]
# date sample (IFC4 TaskTime or IFC2X3 ScheduleTimeControl)
ds = []
for x in (tt or stc)[:5]:
    ds.append({a: str(getattr(x, a, None)) for a in ('ScheduleStart', 'ScheduleFinish', 'ActualStart', 'ActualFinish') if getattr(x, a, None)})
S['date_sample'] = ds
R['schedule'] = S

# ---------------- per element class: containment, material, type, geometry, quantities
QK = {
    'net_volume': {'NetVolume'}, 'gross_volume': {'GrossVolume'},
    'net_area': {'NetArea', 'NetSideArea', 'NetSurfaceArea', 'NetFootprintArea', 'NetSectionArea'},
    'gross_area': {'GrossArea', 'GrossSideArea', 'GrossSurfaceArea', 'GrossFootprintArea', 'CrossSectionArea', 'OuterSurfaceArea'},
    'length': {'Length'}, 'width': {'Width'}, 'height': {'Height', 'Depth'},
    'weight': {'NetWeight', 'GrossWeight', 'Weight', 'Mass'},
}
PK = {  # explicit values carried in ordinary property sets (e.g. Revit 'Dimensions')
    'net_volume': {'volume'}, 'gross_volume': set(), 'net_area': {'area'}, 'gross_area': set(), 'length': {'length'},
    'width': {'width', 'thickness'}, 'height': {'height', 'depth', 'unconnected height'}, 'weight': {'mass', 'weight'},
}
# concrete terms in EN/ES/NL/DE/ZH (混凝土 = concrete; 钢筋混凝土 = reinforced concrete)
CONC = re.compile(r'beton|concrete|hormig|\bC\d{2}/\d{2}\b|\bHA-\d|cast[- ]in[- ]place|in situ|in-situ|混凝土|砼', re.I)
# masonry terms (砌体 = masonry, 砖 = brick; kalkzandsteen = sand-lime brick)
MASON = re.compile(r'masonry|brick|block|ladrillo|f[aá]brica|metsel|kalkzandsteen|baksteen|kzs|mauerwerk|ziegel|砌体|砖', re.I)


def storey_of(el):
    seen = 0
    cur = el
    while cur is not None and seen < 12:
        seen += 1
        c = ue.get_container(cur)
        if c is None:
            c = ue.get_aggregate(cur)
        if c is None:
            return None
        if c.is_a('IfcBuildingStorey'):
            return c
        cur = c
    return None


def mat_names(el):
    m = ue.get_material(el, should_skip_usage=True)
    if m is None:
        return []
    names = []
    if m.is_a('IfcMaterial'):
        names = [m.Name]
    elif m.is_a('IfcMaterialLayerSet'):
        names = [l.Material.Name for l in m.MaterialLayers if l.Material]
    elif m.is_a('IfcMaterialList'):
        names = [x.Name for x in m.Materials]
    elif m.is_a('IfcMaterialConstituentSet'):
        names = [c.Material.Name for c in (m.MaterialConstituents or []) if c.Material]
    elif m.is_a('IfcMaterialProfileSet'):
        names = [p.Material.Name for p in m.MaterialProfiles if p.Material]
    return [n for n in names if n]


EC = {}
ELEM_CLASSES = ['IfcFooting', 'IfcPile', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall', 'IfcMember', 'IfcStair', 'IfcRoof', 'IfcCovering',
                'IfcBuildingElementProxy', 'IfcReinforcingBar', 'IfcReinforcingMesh', 'IfcPlate']
for c in ELEM_CLASSES:
    els = safe(c)
    if not els:
        EC[c] = dict(n=0)
        continue
    st = dict(n=len(els), with_storey=0, with_material=0, with_concrete_material=0, with_masonry_material=0, with_type=0, with_body_geometry=0, with_any_qto=0,
              qto_set_names=collections.Counter(), rep_types=collections.Counter(), predefined=collections.Counter(), material_names=collections.Counter())
    for k in QK:
        st[f'qto_{k}'] = 0
        st[f'pset_{k}'] = 0
        st[f'flat_{k}'] = 0  # quantity flattened into a pset key '[QtoSet[IfcElementQuantity/..]]Name' (e.g. Synchro export)
    for el in els:
        if storey_of(el) is not None:
            st['with_storey'] += 1
        try:
            mn = mat_names(el)
        except Exception:
            mn = []
        if mn:
            st['with_material'] += 1
            st['material_names'].update(mn)
            if any(CONC.search(n) for n in mn):
                st['with_concrete_material'] += 1
            if any(MASON.search(n) for n in mn):
                st['with_masonry_material'] += 1
        if ue.get_type(el) is not None:
            st['with_type'] += 1
        st['predefined'][str(getattr(el, 'PredefinedType', None))] += 1
        rep = el.Representation
        if rep:
            body = [r for r in rep.Representations if (r.RepresentationIdentifier or '') in ('Body', '') or r.RepresentationType in ('SweptSolid', 'Brep', 'MappedRepresentation', 'Tessellation', 'Clipping', 'CSG', 'AdvancedBrep', 'AdvancedSweptSolid')]
            if body:
                st['with_body_geometry'] += 1
            for r in rep.Representations:
                if (r.RepresentationIdentifier or '') == 'Body':
                    st['rep_types'][str(r.RepresentationType)] += 1
        qtos = ue.get_psets(el, qtos_only=True)
        psets = ue.get_psets(el, psets_only=True)
        if qtos:
            st['with_any_qto'] += 1
            st['qto_set_names'].update(qtos.keys())
        qnames = {k.replace(' ', '') for q in qtos.values() for k, v in q.items() if k != 'id' and v not in (None, 0, 0.0)}
        pitems = [(k, v) for p in psets.values() for k, v in p.items() if k != 'id' and isinstance(v, (int, float)) and v]
        pnames = {k.lower() for k, v in pitems if ']]' not in k}
        fnames = {k.split(']]')[-1].replace(' ', '') for k, v in pitems if ']]' in k and 'IfcElementQuantity' in k}
        for k in QK:
            if qnames & QK[k]:
                st[f'qto_{k}'] += 1
            if pnames & PK[k]:
                st[f'pset_{k}'] += 1
            if fnames & QK[k]:
                st[f'flat_{k}'] += 1
    for k in ('qto_set_names', 'rep_types', 'predefined', 'material_names'):
        st[k] = dict(st[k].most_common(8))
    EC[c] = st
R['element_classes'] = EC
R['audit_seconds'] = round(time.time() - t0, 1)
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(R, open(out, 'w', encoding='utf-8'), indent=1, default=str)
print('ok', path, R['schema'], R['audit_seconds'])
