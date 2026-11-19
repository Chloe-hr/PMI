"""Export the inspection envelope and an offline HTML construction report."""

import csv
from collections import Counter, defaultdict
from html import escape
import json


CSV_FIELDS = {
    "classifications": ("element_id", "category", "scope"),
    "packages": ("id", "element_ids", "storey_id"),
    "activities": ("id", "work_item", "schedulable", "blockers"),
    "dependencies": ("predecessor_id", "successor_id", "rule_id"),
    "quantity_requirements": ("activity_id", "status", "basis"),
    "catalogue_options": ("activity_id", "bcca_code", "allocation_status"),
    "graph_issues": ("code", "activity_ids"),
}


def _table(headers, rows):
    def cells(values, tag):
        return "".join(f"<{tag}>{escape(str(value if value is not None else ''))}</{tag}>" for value in values)

    return ("<table><thead><tr>" + cells(headers, "th") + "</tr></thead><tbody>" +
            "".join("<tr>" + cells(row, "td") + "</tr>" for row in rows) + "</tbody></table>")


def render_report(data, elements):
    """Render real counts and package-local dependency diagrams."""
    names = {e.id: e.name or f"STEP #{e.source_step_id}" for e in elements}
    activities = {row["id"]: row for row in data["activities"]}
    quantities = {row["activity_id"]: row for row in data["quantity_requirements"]}
    refs, links, packages = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in data["catalogue_options"]:
        refs[row["activity_id"]].append(row["bcca_code"])
    for row in data["dependencies"]:
        links[activities[row["predecessor_id"]]["package_id"]].append(row)
    for row in data["packages"]:
        packages[row["storey_id"]].append(row)
    locations = {row["storey_id"]: row["storey"] for row in data["classifications"]}
    inputs = {row["input_id"]: row["input"] for row in data["input_register"]}
    parts = ["""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PMI Stage 5.2A construction evidence</title>
<style>body{font:16px system-ui;color:#152b37;background:#edf2f4;margin:2rem auto;padding:0 1rem;max-width:78rem}
table{border-collapse:collapse;width:100%;background:white;margin:.6rem 0 1.2rem}
td,th{text-align:left;border-bottom:1px solid #becbd1;padding:.4rem .6rem}
details{margin:.65rem 0;padding:.65rem;border:1px solid #b4c3ca;background:#fafcfd}
summary{cursor:pointer;font-weight:600}code{font-size:.9rem}</style>
<h1>Construction evidence</h1><p>Stage 5.2A candidate generation. Engineering approvals remain pending.</p>"""]
    parts.append(_table(("Import policy", "Elements", "Packages", "Activities", "Eligible", "Reference options"),
                        [(data["policy"], len(elements), len(data["packages"]), len(activities),
                          sum(row["schedulable"] for row in activities.values()), len(data["catalogue_options"]))]))
    parts.append("<h2>Quantity coverage</h2>" + _table(
        ("State", "Requirements"), sorted(Counter(row["status"] for row in quantities.values()).items())))
    parts.append("<h2>Catalogue coverage</h2>" + _table(
        ("Work item", "Activities", "Activities with reference options"),
        [(code, count, sum(bool(refs[row["id"]]) for row in activities.values() if row["work_item"] == code))
         for code, count in sorted(Counter(row["work_item"] for row in activities.values()).items())]))
    parts.append("<h2>Element classifications</h2><details><summary>View inventory</summary>" + _table(
        ("Element", "Storey", "Material classification", "Rule", "Scope", "Review inputs"),
        [(names[row["element_id"]], row["storey"], row["category"], ", ".join(row["rule_ids"]), row["scope"],
          ", ".join(inputs[key] for key in row["review_input_ids"])) for row in data["classifications"]]) + "</details>")
    parts.append("<h2>Work packages and dependency graphs</h2>")
    for storey_id, group in packages.items():
        parts.append(f"<details><summary>{escape(locations[storey_id] or 'Storey unresolved')} ({len(group)})</summary>")
        for package in group:
            parts.append(f"<details><summary>{escape(names[package['element_ids'][0]])} · {escape(package['family'])}</summary>")
            rows = []
            for activity_id in package["activity_ids"]:
                row, quantity = activities[activity_id], quantities[activity_id]
                value = f"{quantity['value']:.6g} {quantity['unit']}" if quantity["value"] is not None else quantity["status"]
                rows.append((row["work_item"], row["kind"], value, ", ".join(refs[activity_id]),
                             "; ".join(inputs.get(key, key.replace("_", " ")) for key in row["blockers"])))
            parts.append(_table(("Activity", "Kind", "Quantity", "BCCA candidates", "Scheduling blockers"), rows))
            parts.append("<h3>Dependency graph</h3>" + _table(
                ("Directed edge", "Relationship", "State", "Rule and condition"),
                [(f"{activities[row['predecessor_id']]['work_item']} → {activities[row['successor_id']]['work_item']}",
                  row["relation"], row["state"], row["rule_id"] + " · " + row["condition"])
                 for row in links[package["id"]]]) + "</details>")
        parts.append("</details>")
    parts.append("</html>")
    return "\n".join(parts)


def export_construction(folder, data, elements):
    (folder / "construction.json").write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2),
                                              encoding="utf8")
    for key, headers in CSV_FIELDS.items():
        rows = data[key]
        with (folder / f"{key}.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, list(rows[0]) if rows else headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({name: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list))
                                 else value for name, value in row.items()})
    (folder / "report.html").write_text(render_report(data, elements), encoding="utf8")
