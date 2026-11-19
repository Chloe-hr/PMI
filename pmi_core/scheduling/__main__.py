"""Calculate the Stage 5.4A fixture and export its calendar-aware Gantt."""

import argparse
import csv
from datetime import datetime, timedelta
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from .calendar import SchedulingError, build_windows, parse_minute
from .fixture import adapt, read_json, verify_reference


def write_csv(path, rows, headers):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def validate_schedule(schedule, reference_path):
    """Cross-check actual segments, release conditions and timestamps for the fixture."""
    rows = {row["id"]: row for row in schedule["activities"]}
    aliases = {row["reference_id"]: row for row in rows.values()}
    cal, tick = schedule["calendar"], schedule["tick_minutes"]
    zone = ZoneInfo(cal["timezone"])
    minute = lambda text: parse_minute(text, zone)
    start, finish = map(minute, (schedule["project_start"], schedule["project_completion"]))
    checks, comparisons = [], []
    for row in rows.values():
        key = row["reference_id"]
        segments = [(minute(a), minute(b)) for a, b in row["segments"]]
        if row["kind"] in {"productive", "inspection"}:
            normal = build_windows(cal, start, finish, tick)
            restricted = build_windows(cal, start, finish, tick, row["allowed_hours"])
            for label, windows in (("working_calendar", normal), ("activity_window", restricted)):
                ok = all(any(a <= lo < hi <= b for a, b in windows) for lo, hi in segments)
                ok &= sum(b - a for a, b in segments) == row["scheduled_minutes"]
                checks.append({"id": key, "check": label, "passed": ok})
        if row["kind"] in {"elapsed_hold", "strength_release"}:
            pour = aliases[key[0] + "-POUR"]
            a, b = segments[0]
            ok = (a == minute(pour["earliest_finish"])
                  and b - a == row["scheduled_minutes"] + row["release_wait_minutes"])
            if row["kind"] == "strength_release":
                ok &= bool(row["release_status"]) and row["release_status"] != "missing"
            checks.append({"id": key, "check": "elapsed_from_pour_finish", "passed": ok})
    for edge in schedule["dependencies"]:
        left, right = rows[edge["predecessor_id"]], rows[edge["successor_id"]]
        if edge["lag_basis"] != "elapsed":
            raise ValueError("The fixture validation expects elapsed edge lags.")
        ok = minute(right["earliest_start"]) >= minute(left["earliest_finish"]) + edge["lag_minutes"]
        checks.append({"id": f"{left['reference_id']}->{right['reference_id']}", "check": "dependency", "passed": ok})
    with reference_path.open(encoding="utf-8-sig", newline="") as stream:
        references = list(csv.DictReader(stream))
    if {row["id"] for row in references} != set(aliases):
        raise ValueError("Reference schedule has a different activity set.")
    for ref in references:
        row = aliases[ref["id"]]
        comparisons.append({
            "reference_id": ref["id"], "work_item": row["work_item"],
            "cpm_start": row["earliest_start"], "reference_start": ref["start_local"],
            "cpm_finish": row["earliest_finish"], "reference_finish": ref["finish_local"],
            "start_difference_minutes": minute(row["earliest_start"]) - minute(ref["start_local"]),
            "finish_difference_minutes": minute(row["earliest_finish"]) - minute(ref["finish_local"]),
            "original_engineering_minutes": row["duration_minutes"], "scheduled_minutes": row["scheduled_minutes"],
            "rounding_allowance_minutes": round(row["rounding_minutes"], 8),
            "duration_difference_to_reference_minutes": row["scheduled_minutes"] - int(ref["minutes"]),
        })
    reference_finish = max(minute(row["finish_local"]) for row in references)
    return checks, comparisons, finish - reference_finish


def render_gantt(schedule):
    rows = schedule["activities"]
    start = datetime.fromisoformat(schedule["project_start"])
    end = datetime.fromisoformat(schedule["project_completion"])
    span = max(1, end.timestamp() - start.timestamp())
    zone = ZoneInfo(schedule["calendar"]["timezone"])
    first = start.date()
    last = end.date()
    epoch = start.timestamp()
    pct = lambda value: 100 * (value.timestamp() - epoch) / span
    exceptions = set(schedule["calendar"]["date_exceptions"])
    days = []
    for n in range((last - first).days + 1):
        day = first + timedelta(days=n)
        left = max(0, pct(datetime.combine(day, datetime.min.time(), zone)))
        right = min(100, pct(datetime.combine(day + timedelta(days=1), datetime.min.time(), zone)))
        cls = "closed" if day.isoweekday() >= 6 or day.isoformat() in exceptions else "open"
        days.append((left, right, day, cls))
    header = "".join(f'<span style="left:{a:.5f}%;width:{b-a:.5f}%">{day:%d %b}</span>' for a, b, day, _ in days)
    grid = "".join(f'<i class="{cls}" style="left:{a:.5f}%;width:{b-a:.5f}%"></i>' for a, b, _, cls in days)
    parts = ["""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PMI controlled baseline Gantt</title>
<style>
body{margin:2rem auto;padding:0 1rem;max-width:88rem;font:15px system-ui;color:#142c3c;background:#f0f5f7}
.scroller{overflow:auto}.chart{min-width:980px;background:white;border:1px solid #c9d8e0}
.row{display:grid;grid-template-columns:23rem 1fr;border-bottom:1px solid #dbe5eb}
.label{padding:.4rem .8rem}.label small{display:block;color:#415769}.track{position:relative;min-height:2.1rem}
.track i,.track span,.bar{position:absolute;height:100%;border-left:1px solid #dbe5eb;box-sizing:border-box}
.track span{font-size:.72rem;text-align:center;padding-top:.38rem;white-space:nowrap}
.closed{background:#e6e9ed}.bar{height:1rem;top:50%;transform:translateY(-50%);border:1px solid #233f55;border-radius:3px;min-width:3px}
.productive{background:#3b91b5}.inspection{background:#885ac3}.elapsed_hold{background:#e4aa4c}
.strength_release{background:#75a77c}.milestone{background:#263a4a}.critical{outline:2px solid #bd363b}
h2{margin:.25rem;padding:.45rem;color:#14384b;background:#edf4f8}summary{cursor:pointer}
</style>
<h1>Controlled concrete frame baseline</h1>"""]
    parts.append(f"<p>Completion <strong>{escape(schedule['project_completion'])}</strong> Europe/Madrid. "
                 f"Elapsed makespan {schedule['makespan_elapsed_minutes']} minutes. "
                 f"Direct BCCA reference cost €{schedule['cost']['total_direct_reference_eur']:,.2f}.</p>")
    parts.append(f"<p>{len(schedule['resource_conflicts'])} detected resource conflicts. CPM calculates "
                 "precedence and calendar bounds. Crew and equipment pools are checked after the calculation.</p>")
    parts.append("<p>Blue productive · purple inspection · amber curing · green strength release · "
                 "red outline zero float · grey nonworking date. Holiday: " + escape(", ".join(sorted(exceptions))) + ".</p>")
    parts.append('<div class="scroller"><div class="chart"><div class="row"><div class="label">'
                 'Activity and actual baseline time</div><div class="track">' + header + '</div></div>')
    for family, name in (("COL", "Column"), ("BEAM", "Beam"), ("SLAB", "Slab")):
        parts.append(f"<h2>{name} work package</h2>")
        for row in rows:
            if row["family"] != family:
                continue
            bars = []
            for a, b in row["segments"]:
                left, right = [pct(datetime.fromisoformat(value)) for value in (a, b)]
                cls = row["kind"] + (" critical" if row["critical"] else "")
                title = escape(f"{row['reference_id']} {a} to {b} | IFC {row['global_id']}", quote=True)
                bars.append(f'<b class="bar {cls}" style="left:{left:.6f}%;width:{right-left:.6f}%" title="{title}"></b>')
            text = escape(f"{row['reference_id']} · {row['work_item']}")
            times = escape(f"{row['earliest_start']} to {row['earliest_finish']}")
            parts.append(f'<div class="row"><div class="label">{text}<small>{times}</small></div>'
                         f'<div class="track">{grid}{"".join(bars)}</div></div>')
    parts.append("</div></div><h2>Resource warnings</h2>")
    if schedule["resource_conflicts"]:
        parts.append("<ul>" + "".join(f"<li>{escape(str(row))}</li>" for row in schedule["resource_conflicts"]) + "</ul>")
    else:
        parts.append("<p>No overlaps exceeded the declared pools in the calculated fixture.</p>")
    parts.append("<p>Hypothetical input only. All 75 engineering approvals remain pending.</p></html>")
    return "\n".join(parts)


def export(folder, schedule, checks, comparisons):
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / "schedule.json"
    if marker.exists():
        raise FileExistsError("Choose a fresh schedule output directory.")
    marker.write_text(json.dumps(schedule, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf8")
    csvs = {
        "activities": (schedule["activities"], (
            "id", "reference_id", "work_item", "global_id", "element_id", "package_id", "kind", "duration_minutes",
            "scheduled_minutes", "rounding_minutes", "earliest_start", "earliest_finish", "latest_start", "latest_finish",
            "total_float_minutes", "free_float_minutes", "critical", "calendar_delay_minutes", "segments", "resources",
            "release_condition", "release_status", "conditional", "reference_cost_eur")),
        "dependencies": (schedule["dependencies"], (
            "predecessor_id", "successor_id", "predecessor_alias", "successor_alias", "relation",
            "rule_id", "lag_minutes", "lag_basis", "source", "condition")),
        "critical_path": (schedule["critical_edges"], (
            "predecessor_id", "successor_id", "predecessor_alias", "successor_alias", "rule_id", "calendar_gap_minutes")),
        "calendar_validation": (checks, ("id", "check", "passed")),
        "reference_schedule_comparison": (comparisons, tuple(comparisons[0])),
        "resource_conflicts": (schedule["resource_conflicts"],
                               ("resource", "capacity", "usage", "start", "finish", "activity_ids")),
    }
    for name, (rows, fields) in csvs.items():
        write_csv(folder / (name + ".csv"), rows, fields)
    (folder / "report.html").write_text(render_gantt(schedule), encoding="utf8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        config = read_json(args.config)
        prep = Path(config["preparation_directory"])
        handover_path = Path(config["handover"])
        handover = read_json(handover_path)
        verification = verify_reference(handover, prep, Path(config["fixture_inputs"]))
        schedule = adapt(handover, read_json(prep / "controlled_scheduling_inputs.json"), config)
        calendar_checks, comparisons, finish_difference = validate_schedule(schedule, prep / "fixture_expected_schedule.csv")
        schedule.update({"stage5_3_reference_verification": verification,
                         "handover_sha256": sha256(handover_path.read_bytes()).hexdigest(),
                         "reference_completion_difference_minutes": finish_difference,
                         "validation_checks": calendar_checks})
        export(args.output, schedule, calendar_checks, comparisons)
        print(f"{schedule['status']}: {schedule['project_completion']}")
        return 0 if schedule["status"] == "calculated" and all(r["passed"] for r in calendar_checks) else 1
    except SchedulingError as exc:
        parser.exit(2, json.dumps({"code": exc.code, "message": str(exc), **exc.details}) + "\n")
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
