"""Apply the Stage 5.2 preparation material and foundation rules."""

import re


# Ordered labels from the preparation library's classification observations.
MATERIAL_RULES = (
    ("aerated_concrete_block", "CR02", r"cellenbeton|gasbeton|ytong|aerated|加气"),
    ("concrete_block_masonry", "CR03", r"concrete masonry|\bcmu\b|bloque|block|砌块"),
    ("precast_concrete", "CR04", r"prefab|precast|prefabricad|kanaalplaat|breedplaat|预制"),
    ("cast_in_place_concrete", "CR05", r"\bihw\b|in het werk|in[- ]situ|cast[- ]in[- ]place|现场浇注|ter plaatse"),
    ("concrete_method_unstated", "CR06", r"beton|concrete|hormig|混凝土|砼|\bC\d{2}/\d{2}\b|\bHA-\d"),
    ("finish_or_tile_layer", "CR09", r"地砖|瓷砖|铺地|tegel|\btile|baldosa|azulejo"),
    ("masonry", "CR09", r"metselwerk|\bmw-|baksteen|kalkzandsteen|brick|ladrillo|mauerwerk|砖|砌体"),
    ("steel", "CR07", r"staal|steel|stahl|acero|\bS2[3-7]5|\bS355|\bHE[ABM]\b|\bIPE\b|^钢|型钢"),
    ("timber", "CR08", r"\bhout\b|timber|holz|madera|\bGL\d\dh|\bKVH\b|\bCLT\b|\bBSP\b|木"),
)
FAMILIES = {"IfcColumn": "COL", "IfcBeam": "BEAM", "IfcSlab": "SLAB"}
FOUNDATION = re.compile(r"^fund|fundering|foundation|footing|zapata|cimentaci|基础|承台|地梁|Fundament", re.I)


def classify(element, materials, spatial):
    zone = None
    seen = set()
    container = element.container_id
    while container in spatial and container not in seen:
        seen.add(container)
        parent = spatial[container]
        if parent.ifc_class == "IfcBuildingStorey":
            zone = parent
            break
        container = parent.container_id

    labels = [(category, rule) for category, rule, pattern in MATERIAL_RULES
              if any(re.search(pattern, material.name, re.I) for material in materials)]
    category, rule = labels[0] if labels else (
        ("other_material", "CR01") if materials else ("no_material", "CR10"))
    # Generic concrete and steel terms can also appear in reinforced-concrete names.
    # Refuse RC routing when another member has an independently classified material.
    if category == "cast_in_place_concrete" and any(
        not re.search(MATERIAL_RULES[3][2], row.name, re.I) for row in materials
    ):
        category = "mixed_material_cast_in_place_candidate"

    rules = list(dict.fromkeys(("CR01", rule, "CR14")))
    family = FAMILIES.get(element.ifc_class)
    if element.ifc_class == "IfcFooting":
        rules.append("CR12")
        family = "FND"
    elif element.ifc_class in {"IfcBeam", "IfcSlab", "IfcWall", "IfcWallStandardCase"} and (
        FOUNDATION.search(element.name or "") or (zone and FOUNDATION.search(zone.name or ""))
    ):
        rules.append("CR11")
        family = "FND"

    if category == "cast_in_place_concrete" and family == "SLAB":
        rules.append("CR13")

    candidate = None
    if category in {"concrete_block_masonry", "aerated_concrete_block", "precast_concrete", "steel", "masonry"}:
        candidate = {
            "concrete_block_masonry": "MAS-BLOCK", "aerated_concrete_block": "MAS-AAC",
            "precast_concrete": "SLAB-PRECAST" if family == "SLAB" else None,
            "steel": "STEEL-COL" if family == "COL" else None,
            "masonry": "MAS-SANDLIME" if any("kalkzandsteen" in m.name.casefold() for m in materials) else "MAS-BRICK",
        }[category]
    return {
        "element_id": element.id, "category": category, "family": family,
        "storey_id": zone.id if zone else None, "storey": zone.name if zone else None,
        "rule_ids": rules, "material_ids": [row.id for row in materials],
        "candidate_library_item": candidate,
        "scope": "candidate" if category == "cast_in_place_concrete" and family in FAMILIES.values()
                 else "classification_only",
    }
