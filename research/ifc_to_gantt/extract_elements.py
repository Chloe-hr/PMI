"""
Stage 3.1 - BIM element extraction  ->  elements table (source-agnostic schema)
===============================================================================
Every source adapter (IFC today, Speckle next) must return the SAME columns, so task
generation, scheduling and the GNN never depend on where the model came from.

Columns
    source_id      stable identifier (IFC GlobalId / Revit UniqueId / Speckle applicationId)
    ifc_class      base IFC class (IfcWallStandardCase -> IfcWall)
    name, type_name
    storey, storey_elevation   resolved through spaces / aggregates up to the building storey
    materials      ';'-joined material names (layer sets included)
    length_m, area_m2, volume_m3   from IFC base quantities (Qto_*) or Revit dimension psets
    quantity_source  which property set the quantities came from ('' = none found)
    is_external, load_bearing   from Pset_*Common when present
    parent_id      GlobalId of the aggregating element (e.g. stair flight -> stair), '' otherwise
    model_version  short SHA-256 of the source file - ties every row to one model version

    python research/ifc_to_gantt/extract_elements.py models/original.ifc outputs/v1/elements.csv
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

COLUMNS = ["source_id", "ifc_class", "name", "type_name", "storey", "storey_elevation", "materials",
           "length_m", "area_m2", "volume_m3", "quantity_source", "is_external", "load_bearing",
           "parent_id", "model_version"]

# Elements that are not built work (voids, spatial helpers)
SKIP_CLASSES = ("IfcOpeningElement", "IfcVirtualElement", "IfcSpace", "IfcAnnotation", "IfcGrid")

# Where to look for quantities, in order of preference
_QTY_KEYS = {
    "length_m": ("Length", "NetLength", "GrossLength"),
    "area_m2": ("NetSideArea", "GrossSideArea", "NetArea", "GrossArea", "Area", "NetSurfaceArea"),
    "volume_m3": ("NetVolume", "GrossVolume", "Volume"),
}


def base_class(ifc_class: str) -> str:
    for suf in ("StandardCase", "ElementedCase"):
        if ifc_class.endswith(suf):
            return ifc_class[: -len(suf)]
    return ifc_class


def file_version(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def _storey(element, ue):
    """Walk container -> aggregate parents until an IfcBuildingStorey is found."""
    node = ue.get_container(element) or ue.get_aggregate(element)
    seen = 0
    while node is not None and not node.is_a("IfcBuildingStorey") and seen < 20:
        node = ue.get_container(node) or ue.get_aggregate(node)
        seen += 1
    if node is None or not node.is_a("IfcBuildingStorey"):
        return "", None
    return node.Name or "", float(node.Elevation) if node.Elevation is not None else None


def _quantities(psets: dict) -> tuple[dict, str]:
    """Prefer official base quantities (Qto_*), then the Revit dimensions pset."""
    candidates = [k for k in psets if k.startswith("Qto_") or k.startswith("BaseQuantities")]
    candidates += [k for k in psets if k == "PSet_Revit_Dimensions"]
    out, used = {}, []
    for pset in candidates:
        for col, keys in _QTY_KEYS.items():
            if col in out:
                continue
            for k in keys:
                v = psets[pset].get(k)
                if isinstance(v, (int, float)) and v > 0:
                    out[col] = float(v)
                    used.append(pset)
                    break
    return out, ";".join(dict.fromkeys(used))


def _common(psets: dict, key: str):
    for name, props in psets.items():
        if name.startswith("Pset_") and name.endswith("Common") and key in props:
            return props[key]
    return None


def extract_ifc(path: Path) -> pd.DataFrame:
    import ifcopenshell
    import ifcopenshell.util.element as ue

    path = Path(path)
    model = ifcopenshell.open(str(path))
    version = file_version(path)
    rows = []
    for e in model.by_type("IfcElement"):
        if e.is_a() in SKIP_CLASSES or any(e.is_a(c) for c in SKIP_CLASSES):
            continue
        psets = ue.get_psets(e)
        qty, qsrc = _quantities(psets)
        storey, elev = _storey(e, ue)
        etype = ue.get_type(e)
        parent = ue.get_aggregate(e)
        rows.append({
            "source_id": e.GlobalId,
            "ifc_class": base_class(e.is_a()),
            "name": e.Name or "",
            "type_name": (etype.Name if etype is not None else "") or "",
            "storey": storey,
            "storey_elevation": elev,
            "materials": ";".join(sorted({m.Name for m in ue.get_materials(e) if getattr(m, "Name", None)})),
            "length_m": qty.get("length_m"),
            "area_m2": qty.get("area_m2"),
            "volume_m3": qty.get("volume_m3"),
            "quantity_source": qsrc,
            "is_external": _common(psets, "IsExternal"),
            "load_bearing": _common(psets, "LoadBearing"),
            "parent_id": parent.GlobalId if parent is not None and parent.is_a("IfcElement") else "",
            "model_version": version,
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def extract_speckle(*_args, **_kwargs) -> pd.DataFrame:
    """Placeholder for Stage 3.1b: receive a Speckle version with specklepy and map it onto COLUMNS.
    Which properties are reliable depends on the authoring tool (Revit vs Rhino) - see README."""
    raise NotImplementedError("Speckle adapter not built yet - waiting for the first test model on Speckle.")


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print(__doc__)
        return 1
    df = extract_ifc(Path(argv[0]))
    out = Path(argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"{len(df)} elements, model_version {df['model_version'].iat[0] if len(df) else '-'} -> {out}")
    print(df.groupby(["storey", "ifc_class"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
