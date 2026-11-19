"""Read-only enrichment of the 40 Stage 4.0B quantity-validation elements.

Run from repo root:
    .venv/Scripts/python.exe -I research/validation/stage5_1_manual/scripts/enrich_validation_elements.py
Input : research/data_acquisition/stage4_0b/consolidated/quantity_validation_plan.csv (not modified)
Output: data/processed/candidates/stage5_2_prep/validation_elements_enriched.json
        data/processed/candidates/stage5_2_prep/sch_synchro_task_sequence.csv
No value here is an independent measurement. Geometry values are re-read from the plan (DERIVED).
"""
import csv, json, os, sys
import ifcopenshell
import ifcopenshell.util.element as ue
import ifcopenshell.util.unit as uu

sys.stdout.reconfigure(encoding='utf-8')
PLAN = 'research/data_acquisition/stage4_0b/consolidated/quantity_validation_plan.csv'
OUT = 'data/processed/candidates/stage5_2_prep'
os.makedirs(OUT, exist_ok=True)
rows = list(csv.DictReader(open(PLAN, encoding='utf-8', newline='')))


def chain(el):
    """Nearest storey and building through containment/aggregation."""
    st = bd = None
    cur, n = el, 0
    while cur is not None and n < 15:
        n += 1
        c = ue.get_container(cur) or ue.get_aggregate(cur)
        if c is None:
            break
        if c.is_a('IfcBuildingStorey') and st is None:
            st = c
        if c.is_a('IfcBuilding'):
            bd = c
            break
        cur = c
    return st, bd


out = []
by_file = {}
for r in rows:
    by_file.setdefault(r['ifc_path'], []).append(r)
for path, rs in by_file.items():
    f = ifcopenshell.open(path)
    ls = uu.calculate_unit_scale(f)
    for r in rs:
        el = f.by_guid(r['global_id'])
        st, bd = chain(el)
        qtos = ue.get_psets(el, qtos_only=True)
        flat = {k.split(']]')[-1]: v for p in ue.get_psets(el, psets_only=True).values() for k, v in p.items() if ']]' in k and 'IfcElementQuantity' in k}
        q = {}
        for qn, qs in qtos.items():
            for k, v in qs.items():
                if k != 'id' and isinstance(v, (int, float)):
                    q[f'{qn}.{k}'] = v
        rep = []
        if el.Representation:
            for x in el.Representation.Representations:
                rep.append(f'{x.RepresentationIdentifier}:{x.RepresentationType}')
        openings = [v.RelatedOpeningElement.GlobalId for v in getattr(el, 'HasOpenings', []) or []]
        lay = json.loads(r['material_classification']) if r['material_classification'] else []
        closed = r['edge_manifold_closed'] == 'True'
        body = r['geometry_representation']
        if not closed:
            cat = 'D invalid mesh'
        elif len(lay) > 1 or (r['concrete_layer_thickness_fraction'] not in ('', None) and float(r['concrete_layer_thickness_fraction']) < 1):
            cat = 'B layered element'
        elif 'IfcRectangleProfileDef' in body and 'boolean' not in body and not openings:
            cat = 'A simple homogeneous (rectangular extrusion)'
        elif body.startswith('extrusion') and 'boolean' not in body and not openings:
            cat = 'A simple homogeneous (profile extrusion)'
        else:
            cat = 'C irregular geometry (Brep / boolean / openings)'
        out.append(dict(r, step_id=el.id(), schema=f.schema, building=(bd.Name if bd else None), storey_resolved=(st.Name if st else None),
                        storey_elevation_m=(st.Elevation * ls if st is not None and st.Elevation is not None else None),
                        object_type=getattr(el, 'ObjectType', None), type_name=(ue.get_type(el).Name if ue.get_type(el) else None),
                        authored_quantities=q, flattened_quantities=flat, representations=rep, openings=openings, geometry_category=cat,
                        length_unit_scale_to_m=ls))
    del f
json.dump(out, open(f'{OUT}/validation_elements_enriched.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
print('enriched', len(out), {c: sum(1 for o in out if o['geometry_category'] == c) for c in sorted({o['geometry_category'] for o in out})})

# SCH Synchro task sequence (planned, one real project) - dependency evidence only
f = ifcopenshell.open('data/raw/SCHEPENDOMLAAN/As Planned models/IFC Schependomlaan incl planningsdata.ifc')


def dtv(x):
    if x is None:
        return None
    d, t = x.DateComponent, x.TimeComponent
    return f'{d.YearComponent:04d}-{d.MonthComponent:02d}-{d.DayComponent:02d}T{t.HourComponent:02d}:{t.MinuteComponent:02d}'


tasks = {}
for rel in f.by_type('IfcRelAssignsTasks'):
    for t in rel.RelatedObjects:
        tasks[t.id()] = dict(task=t.Name, start=dtv(rel.TimeForTask.ScheduleStart), finish=dtv(rel.TimeForTask.ScheduleFinish), global_id=t.GlobalId)
nprod = {}
for rel in f.by_type('IfcRelAssignsToProcess'):
    nprod[rel.RelatingProcess.id()] = nprod.get(rel.RelatingProcess.id(), 0) + len(rel.RelatedObjects)
seq = []
for s in f.by_type('IfcRelSequence'):
    seq.append((s.RelatingProcess.id(), s.RelatedProcess.id(), str(s.SequenceType), s.TimeLag))
for k, v in tasks.items():
    v['assigned_products'] = nprod.get(k, 0)
    v['predecessors'] = '; '.join(f"{tasks[a]['task']} ({t})" for a, b, t, _ in seq if b == k and a in tasks)
rows = sorted(tasks.values(), key=lambda v: (v['start'] or '', v['task'] or ''))
with open(f'{OUT}/sch_synchro_task_sequence.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=['start', 'finish', 'task', 'assigned_products', 'predecessors', 'global_id'])
    w.writeheader()
    w.writerows(rows)
print('tasks', len(rows), 'sequences', len(seq))
for v in rows[:60]:
    print((v['start'] or '')[:10], (v['finish'] or '')[:10], v['assigned_products'], v['task'], '<-', v['predecessors'][:80])
