"""Write Stage 5.3A estimates from local versioned JSON exports."""

import argparse
import csv
from html import escape
import json
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

from pmi_core.estimation.engine import estimate_frame
from pmi_core.estimation.references import DEFAULT_REFERENCES, load_references


def _table(headers, rows):
    def cells(values, tag):
        return "".join(f"<{tag}>{escape(str(value if value is not None else ''))}</{tag}>" for value in values)

    return ("<table><thead><tr>" + cells(headers, "th") + "</tr></thead><tbody>" +
            "".join("<tr>" + cells(row, "td") + "</tr>" for row in rows) + "</tbody></table>")


def render_html(result):
    names = {row["global_id"]: row["ifc_class"] for row in result["element_quantities"]}
    labels = {row["id"]: names[row["global_id"]] + " / " + row["work_item"] for row in result["activities"]}
    cost = result["cost"]
    money = lambda value: f"€{value:,.2f}" if value is not None else "Unavailable"
    def hours(value):
        return f"{value:.3f}" if value is not None else ""

    return "\n".join([
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PMI Stage 5.3A controlled engineering estimate</title>
<style>body{font:16px system-ui;color:#172d37;background:#eef3f4;margin:2rem auto;padding:0 1rem;max-width:78rem}
table{width:100%;border-collapse:collapse;background:white;margin:1rem 0 2rem}
td,th{border-bottom:1px solid #c4d0d5;text-align:left;padding:.5rem;vertical-align:top}
small{color:#414e52}h1,h2{line-height:1.2}</style>
<h1>Controlled concrete frame estimate</h1>
<p>Hypothetical fixture inputs. Productive activity bounds and elapsed release conditions are reported separately. No project dates are assigned.</p>""",
        "<h2>Direct reference costs</h2>",
        "<p>" + escape(cost["boundary"]) + "</p>",
        _table(("Labour", "Equipment", "Material", "Rounding reconciliation", "Published reference total"),
               [tuple(money(cost["components_eur"][key]) for key in ("labor", "equipment", "material")) +
                (money(cost["rounding_residual_eur"]), money(cost["total_direct_reference_eur"]))]),
        "<h2>Measured fixture quantities</h2>",
        _table(("Element", "IFC GlobalId", "Placed concrete m³", "Formwork m²", "Reinforcement kg"),
               [(row["ifc_class"], row["global_id"], row["placed_concrete_m3"], row["formwork_m2"],
                 row["reinforcement_kg"]) for row in result["element_quantities"]]),
        "<h2>Activities and estimates</h2>",
        _table(("Activity", "BCCA code", "Productive hours", "Elapsed hours", "Direct cost", "Criterion or blockers"),
               [(labels[row["id"]], row.get("reference", {}).get("code"), hours(row.get("productive_hours")),
                 hours(row.get("elapsed_hours")), money(row["reference_cost_eur"]) if row.get("reference_cost_eur") is not None else "",
                 "; ".join(row["blockers"]) or row.get("criterion")) for row in result["activities"]]),
        f"<p>Eligible as future controlled scheduling input: {result['eligible_for_controlled_scheduling_input']}. Real-project eligibility: false.</p>",
        "<h2>Dependencies</h2>",
        _table(("Predecessor", "Successor", "Relation", "Source rule"),
               [(labels[row["predecessor_id"]], labels[row["successor_id"]], row["relation"], row["rule_id"])
                for row in result["dependencies"]]),
        "</html>",
    ])


def _csv(path, rows, headers):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key in headers for value in [row.get(key)]])


def export_result(folder, result):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "estimate.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                                          encoding="utf8")
    fields = {
        "element_quantities": ("element_id", "global_id", "ifc_class", "placed_concrete_m3", "concrete_quantity_ids",
                               "formwork_m2", "reinforcement_kg", "formwork_rule", "reinforcement_boq"),
        "packages": ("id", "global_ids", "family", "storey_id", "activity_ids", "fixture_sequence"),
        "dependencies": ("predecessor_id", "successor_id", "relation", "rule_id", "state", "lag_hours"),
        "activities": ("id", "package_id", "global_id", "work_item", "kind", "quantity", "unit", "crew_id",
                       "worker_hours_by_trade", "machine_hours_by_class", "materials", "productive_hours",
                       "elapsed_hours", "reserved_worker_hours", "reserved_machine_hours", "reference_cost_eur",
                       "cost_components_eur", "rounding_residual_eur", "criterion", "blockers",
                       "pending_approval_ids", "eligible_for_real_scheduling"),
    }
    for key, headers in fields.items():
        _csv(folder / f"{key}.csv", result[key], headers)
    payload = (folder / "estimate.json").read_text(encoding="utf8")
    (folder / "scheduling_handover.json").write_text(payload, encoding="utf8")
    activities = result["activities"]
    _csv(folder / "duration_estimates.csv", activities, (
        "id", "package_id", "global_id", "work_item", "kind", "productive_hours", "elapsed_hours",
        "execution_mode", "capacity_bounds_hours", "criterion", "input_state", "assumption_ref", "blockers",
        "eligible_for_controlled_scheduling_input", "eligible_for_real_scheduling",
    ))
    _csv(folder / "cost_estimates.csv", activities, (
        "id", "package_id", "global_id", "work_item", "quantity", "unit", "reference_cost_eur",
        "cost_components_eur", "labor_cost_eur_by_trade", "equipment_cost_eur_by_class",
        "rounding_residual_eur", "cost_treatment", "reference",
    ))
    resources = []
    for row in activities:
        identity = {"activity_id": row["id"], "global_id": row["global_id"], "work_item": row["work_item"]}
        for kind, demand_key, capacity_key, cost_key in (
            ("labor", "worker_hours_by_trade", "worker_capacity_by_trade", "labor_cost_eur_by_trade"),
            ("equipment", "machine_hours_by_class", "equipment_capacity_by_class", "equipment_cost_eur_by_class"),
        ):
            resources.extend({**identity, "type": kind, "resource": key, "demand": value, "unit": "h",
                              "capacity": row.get(capacity_key, {}).get(key), "cost_eur": row.get(cost_key, {}).get(key)}
                             for key, value in row.get(demand_key, {}).items())
        resources.extend({**identity, "type": "material", "resource": material["code"],
                          "demand": material["quantity"], "unit": material["unit"],
                          "cost_eur": material["cost_eur_from_line"]} for material in row.get("materials", []))
        resources.extend({**identity, "type": "throughput", "resource": key, "demand": row["quantity"],
                          "unit": row["unit"], "capacity": rate}
                         for key, rate in row.get("concurrent_throughput_per_hour", {}).items())
    _csv(folder / "resource_demands.csv", resources,
         ("activity_id", "global_id", "work_item", "type", "resource", "demand", "unit", "capacity", "cost_eur"))
    (folder / "report.html").write_text(render_html(result), encoding="utf8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("ifc", "bim", "construction"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--ifc-python", default=sys.executable,
                        help="IFC extraction interpreter when running with --ifc.")
    parser.add_argument("--project-id", default="PMI-CONTROLLED")
    parser.add_argument("--references", type=Path, default=DEFAULT_REFERENCES)
    args = parser.parse_args(argv)
    if args.ifc and (args.bim or args.construction) or not args.ifc and not (args.bim and args.construction):
        parser.error("Supply --ifc or the pair --bim and --construction.")
    try:
        refs, digest = load_references(args.references)
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        with TemporaryDirectory(prefix="pmi-estimation-") as tmp:
            if args.ifc:
                from hashlib import file_digest
                from pmi_core.estimation.engine import FIXTURE_SHA

                with args.ifc.open("rb") as source:
                    if file_digest(source, "sha256").hexdigest() != FIXTURE_SHA:
                        raise ValueError("Fixture scope only. Real-project estimation and release are disabled.")
                folder = Path(tmp) / "construction"
                subprocess.run([args.ifc_python, "-B", "-m", "pmi_core.cli", "build-construction",
                                "--input", str(args.ifc), "--project-id", args.project_id,
                                "--geometry", "--output", str(folder)], check=True)
                args.bim, args.construction = folder / "import.json", folder / "construction.json"
            inputs = [json.loads(path.read_text(encoding="utf-8-sig"))
                      for path in (args.bim, args.construction)] + [config]
        result = estimate_frame(*inputs, refs, digest)
        export_result(args.output, result)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    return 0 if result["eligible_for_controlled_scheduling_input"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
