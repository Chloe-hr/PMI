"""Measure conservatively validated single convex Body representations."""

from collections import Counter

import ifcopenshell.geom
from ifcopenshell.util.shape import get_shape_matrix
import numpy as np

from pmi_core.bim.quantities import _factor
from pmi_core.schemas.bim import GeometryAssessment, QuantityRecord, stable_id


class UnsupportedGeometry(ValueError):
    pass


def _volume(mesh):
    vertices = np.asarray(mesh.verts).reshape(-1, 3)
    faces = np.asarray(mesh.faces, dtype=int).reshape(-1, 3)
    if len(vertices) < 4 or len(faces) < 4 or not np.isfinite(vertices).all():
        raise ValueError("Mesh has insufficient or nonfinite coordinates.")
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError("Mesh has invalid face indices.")
    vertices, remap = np.unique(vertices, axis=0, return_inverse=True)
    faces = remap[faces]
    edges = Counter((int(a), int(b)) for face in faces for a, b in zip(face, np.roll(face, -1)))
    if any(a == b or count != 1 or edges[b, a] != 1 for (a, b), count in edges.items()):
        raise ValueError("Mesh is open, nonmanifold or inconsistently oriented.")
    if len(set(faces.flat)) != len(vertices) or len(vertices) - len(edges) // 2 + len(faces) != 2:
        raise ValueError("Mesh must describe one closed shell.")
    # Validate the vertex links as well as edge incidence.
    links = [dict() for _ in vertices]
    for a, b, c in faces:
        for center, start, end in ((a, b, c), (b, c, a), (c, a, b)):
            links[center][start] = end
    for link in links:
        first = current = next(iter(link))
        visited = set()
        while current not in visited:
            visited.add(current)
            current = link[current]
        if current != first or len(visited) != len(link):
            raise ValueError("Mesh contains a nonmanifold vertex.")
    points = vertices - vertices.mean(axis=0)
    triangles = points[faces]
    a, b, c = triangles.transpose(1, 0, 2)
    normals = np.cross(b - a, c - a)
    lengths = np.linalg.norm(normals, axis=1)
    scale = float(np.ptp(points, axis=0).max())
    if (lengths <= scale ** 2 * 1e-14).any():
        raise ValueError("Mesh contains degenerate triangles.")
    signed_volume = float(np.einsum("ij,ij->", a, normals).sum() / 6)
    if not np.isfinite(signed_volume) or abs(signed_volume) <= scale ** 3 * 1e-14:
        raise ValueError("Mesh has no measurable enclosed volume.")
    # A convex support-plane check excludes unsupported intersecting or concave solids.
    for point, normal in zip(a, normals / lengths[:, None] * np.sign(signed_volume)):
        if np.max((points - point) @ normal) > scale * 1e-8:
            raise UnsupportedGeometry("Mesh is outside the supported convex solid domain.")
    return abs(signed_volume)


def extract_geometry(entity, record, project, evidence):
    representation = entity.Representation
    bodies = [row for row in (representation.Representations if representation else ())
              if row.RepresentationIdentifier == "Body"]
    if not bodies:
        return GeometryAssessment(record.id, "missing", "No Body representation."), None
    if len(bodies) != 1 or len(bodies[0].Items) != 1 or getattr(entity, "HasOpenings", ()):
        return GeometryAssessment(record.id, "unsupported", "Multiple bodies, multiple items or openings."), None
    body = bodies[0]
    item = body.Items[0]
    if not (item.is_a("IfcExtrudedAreaSolid") or item.is_a("IfcTessellatedFaceSet") or item.is_a("IfcFacetedBrep")):
        return GeometryAssessment(record.id, "unsupported", item.is_a()), None
    if getattr(item, "Closed", None) is False:
        return GeometryAssessment(record.id, "invalid", "Source declares an open mesh."), None
    try:
        assignment = project.UnitsInContext
        units = [u for u in (assignment.Units if assignment else ())
                 if getattr(u, "UnitType", None) == "LENGTHUNIT"]
        if len(units) != 1:
            raise ValueError("Geometry requires one project length unit.")
        factor, unit_steps = _factor(units[0], "length", "LENGTHUNIT", "METRE", 1)
        if not np.isfinite(factor) or factor <= 0:
            raise ValueError("Invalid project length scale.")
        settings = ifcopenshell.geom.settings()
        settings.set("convert-back-units", False)
        settings.set("use-world-coords", False)
        settings.set("context-ids", [body.ContextOfItems.id()])
        shape = ifcopenshell.geom.create_shape(settings, entity)
        matrix = get_shape_matrix(shape)
        axes = matrix[:3, :3]
        if (not np.isfinite(matrix).all() or
                not np.allclose(axes.T @ axes, np.eye(3), atol=1e-8) or
                not np.isclose(np.linalg.det(axes), 1.0, atol=1e-8)):
            raise ValueError("Placement is not a finite rigid transform.")
        volume = _volume(shape.geometry)
    except UnsupportedGeometry as exc:
        return GeometryAssessment(record.id, "unsupported", str(exc)), None
    except (RuntimeError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        return GeometryAssessment(record.id, "invalid", str(exc) or type(exc).__name__), None
    key = stable_id(record.id, "geometry", "body_volume")
    sources = (entity.id(), body.id(), item.id(), assignment.id(), *unit_steps)
    derivation = evidence.derive(key, "Oriented triangle volume of the convex IFC Body in SI metres",
                                 tuple(evidence.entity(step) for step in sources))
    return (GeometryAssessment(record.id, "valid"),
            QuantityRecord(key, (derivation,), record.id, "volume", "represented_body_volume",
                           "geometry", "accepted", volume, "m3"))
