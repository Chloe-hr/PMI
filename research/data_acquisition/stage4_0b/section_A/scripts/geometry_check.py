"""Sampled geometry-vs-authored quantity check (read-only).

Usage: python -I geometry_check.py <ifc_path> <out_csv> [max_per_class=60]
For a deterministic sample of elements per class, tessellate the Body geometry with
IfcOpenShell (world coordinates, SI metres) and compute closed-mesh volume and total
surface area. Where the file also authors NetVolume / GrossVolume (any IfcElementQuantity),
the ratio geometry/authored is recorded. Surface area is TOTAL area, never formwork area.
Authored values are converted to SI using the project VOLUMEUNIT scale.
"""
import csv, os, sys, time
import ifcopenshell, ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.shape as us
import ifcopenshell.util.unit as uu

path, out = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 60
f = ifcopenshell.open(path)
vscale = uu.calculate_unit_scale(f, 'VOLUMEUNIT')
s = ifcopenshell.geom.settings()
s.set('use-world-coords', True)
rows = []
for cls in ('IfcFooting', 'IfcColumn', 'IfcBeam', 'IfcSlab', 'IfcWall'):
    els = sorted(f.by_type(cls), key=lambda e: e.GlobalId)
    step = max(1, len(els) // N)
    for el in els[::step][:N]:
        t0 = time.time()
        r = dict(file=path.replace('\\', '/'), ifc_class=cls, global_id=el.GlobalId, name=el.Name)
        q = ue.get_psets(el, qtos_only=True)
        nv = next((v.get('NetVolume') for v in q.values() if v.get('NetVolume')), None)
        gv = next((v.get('GrossVolume') for v in q.values() if v.get('GrossVolume')), None)
        r['authored_net_volume_m3'] = nv * vscale if nv else ''
        r['authored_gross_volume_m3'] = gv * vscale if gv else ''
        try:
            sh = ifcopenshell.geom.create_shape(s, el)
            g = sh.geometry
            r['geom_volume_m3'] = round(us.get_volume(g), 6)
            r['geom_total_surface_m2'] = round(us.get_area(g), 6)
            r['geom_closed_mesh'] = us.is_manifold(g) if hasattr(us, 'is_manifold') else ''
            r['geom_status'] = 'ok'
        except Exception as e:  # noqa
            r['geom_status'] = f'fail: {type(e).__name__}'
        ref = nv or gv
        if ref and r.get('geom_volume_m3') not in (None, ''):
            r['ratio_geom_to_authored'] = round(r['geom_volume_m3'] / (ref * vscale), 4) if ref else ''
            r['authored_reference'] = 'NetVolume' if nv else 'GrossVolume'
        r['seconds'] = round(time.time() - t0, 2)
        rows.append(r)
cols = ['file', 'ifc_class', 'global_id', 'name', 'authored_net_volume_m3', 'authored_gross_volume_m3', 'authored_reference', 'geom_volume_m3',
        'geom_total_surface_m2', 'geom_closed_mesh', 'ratio_geom_to_authored', 'geom_status', 'seconds']
exists = os.path.exists(out)
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'a', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
    if not exists:
        w.writeheader()
    w.writerows(rows)
print('ok', path, len(rows))
