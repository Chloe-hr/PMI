"""Load demand and cost decomposition selected by the engineering review."""

import csv
from hashlib import sha256
from io import StringIO
from math import isfinite
from pathlib import Path
import re


DEFAULT_REFERENCES = Path(__file__).resolve().parents[2] / (
    "research/validation/engineering_approval_review/stage5_3_reference_selection.csv"
)


def number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric.")
    if not isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{label} must be finite and {'positive' if positive else 'nonnegative'}.")
    return value


def _coefficients(text, *, equipment=False):
    if not text or text == "none in decomposition":
        return {}
    result = {}
    for entry in text.split(";"):
        name, value = entry.strip().rsplit("=", 1)
        if equipment:
            if not name.endswith(" [h]"):
                raise ValueError(f"Equipment coefficient lacks an hour unit: {name}")
            name = name[:-4]
        if not name or name in result:
            raise ValueError(f"Invalid or duplicate resource: {name}")
        result[name] = number(float(value), name)
    return result


def _materials(text):
    result = []
    for entry in filter(None, text.split(";")):
        match = re.fullmatch(r"(\w+)\s+(.+?)\s+([\d.]+)\s+(\S+)\s+@\s+([\d.]+)", entry.strip())
        if not match:
            raise ValueError(f"Malformed material coefficient: {entry}")
        code, name, amount, unit, rate = match.groups()
        result.append({"code": code, "name": name, "unit": unit, "per_unit": number(float(amount), code),
                       "reference_rate_eur": number(float(rate), code)})
    return result


def load_references(path=DEFAULT_REFERENCES):
    path = Path(path)
    payload = path.read_bytes()
    records = {}
    for row in csv.DictReader(StringIO(payload.decode("utf-8-sig"), newline="")):
        key = row["activity_id"], row["bcca_code"]
        if key in records or not all(key) or row["currency"] != "EUR" or row["approval_status"] != "PENDING":
            raise ValueError(f"Invalid reference selection: {key}")
        components = {label: number(float(row[field]), field) for label, field in (
            ("labor", "cost_labour_eur"), ("equipment", "cost_equipment_eur"),
            ("material", "cost_material_eur"),
        )}
        price = number(float(row["unit_cost_eur"]), "published unit price")
        difference = price - sum(components.values())
        if abs(difference) > 0.010000001:
            raise ValueError(f"Reference cost components do not reconcile within EUR 0.01: {key}")
        records[key] = {
            "work_item": key[0], "code": key[1], "unit": row["quantity_unit"].replace("²", "2"),
            "labor_per_unit": _coefficients(row["labour_h_per_unit_by_trade"]),
            "labor_rate_eur_per_hour": _coefficients(row["labour_rate_eur_h"]),
            "equipment_per_unit": _coefficients(row["equipment_h_per_unit"], equipment=True),
            "materials": _materials(row["material_coefficients"]), "component_eur_per_unit": components,
            "published_eur_per_unit": price, "unresolved_equipment": row["unresolved_equipment"],
            "included_operations": row["included_operations"], "excluded_operations": row["excluded_operations"],
            "bundled_operations": row["bundled_not_separately_allocatable"], "approval_id": row["approval_id"],
            "edition": row["source_edition"], "region": row["region"], "currency": row["currency"],
            "concept_price_date_ddmmyy": row["concept_price_date_ddmmyy"],
            "bc3_sha256": row["source_sha256"], "applicability": row["applicability_limitations"],
        }
    if not records:
        raise ValueError("The engineering reference selection is empty.")
    return records, sha256(payload).hexdigest()
