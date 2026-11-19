"""Recalculate the engineering review's separate hypothetical worked example."""

import csv
from decimal import Decimal
import json
from pathlib import Path

from pmi_core.estimation.references import DEFAULT_REFERENCES


def compare_review():
    """Multiply the original review inputs using decimal arithmetic."""
    folder = DEFAULT_REFERENCES.parent
    template = json.loads((folder / "controlled_demo_input_template.json").read_text(encoding="utf-8-sig"),
                          parse_float=Decimal)
    quantities = template["hypothetical_test_fixture"]["quantities"]
    with DEFAULT_REFERENCES.open(encoding="utf-8-sig", newline="") as stream:
        refs = {row["activity_id"]: row for row in csv.DictReader(stream) if row["selection_role"] == "primary"}
    examples = [
        ("COL-REBAR", "COL-REBAR", quantities["COL_REBAR_kg"], "228.00"),
        ("COL-FORM", "COL-FORM", quantities["COL_FORM_m2"], "232.70"),
        ("COL-CONC", "COL-CONC", quantities["COL_CONC_m3"], "122.67"),
        ("BEAM-FORM", "BEAM-FORM", quantities["BEAM_FORM_m2"], "421.98"),
        ("SLAB-FORM", "SLAB-FORM", quantities["SLAB_FORM_m2"], "601.69"),
        ("BEAM-REBAR", "BEAM-REBAR", quantities["BEAM_REBAR_kg"], "456.00"),
        ("SLAB-REBAR", "SLAB-REBAR", quantities["SLAB_REBAR_kg"], "608.00"),
        ("BEAM-CONC", "BEAM-CONC", quantities["BEAM_CONC_m3"], "355.20"),
        ("SLAB-CONC", "SLAB-CONC", quantities["SLAB_CONC_m3"], "666.13"),
        ("FRM-STRIP (cols)", "FRM-STRIP", quantities["COL_FORM_m2"], "57.60"),
        ("FRM-STRIP (beams+slab)", "FRM-STRIP", quantities["BEAM_FORM_m2"] + quantities["SLAB_FORM_m2"], "216.36"),
    ]
    rows = []
    amounts = ("labour", "equipment", "material")
    cent = Decimal("0.01")
    for label, item, quantity, published in examples:
        ref = refs[item]
        amount = quantity * Decimal(ref["unit_cost_eur"])
        rows.append({
            "activity": label, "bcca_code": ref["bcca_code"], "quantity": quantity,
            "unit": ref["quantity_unit"], "unit_price_eur": ref["unit_cost_eur"],
            **{f"{key}_eur": quantity * Decimal(ref[f"cost_{key}_eur"]) for key in amounts},
            "recomputed_exact_eur": amount, "recomputed_display_eur": amount.quantize(cent),
            "review_display_eur": Decimal(published), "difference_eur": amount.quantize(cent) - Decimal(published),
        })
    exact = sum(row["recomputed_exact_eur"] for row in rows)
    rows.append({
        "activity": "TOTAL", "bcca_code": "", "quantity": "", "unit": "", "unit_price_eur": "",
        **{f"{key}_eur": sum(row[f"{key}_eur"] for row in rows) for key in amounts},
        "recomputed_exact_eur": exact, "recomputed_display_eur": exact.quantize(cent),
        "review_display_eur": Decimal("3966.32"), "difference_eur": exact.quantize(cent) - Decimal("3966.32"),
    })
    return rows
