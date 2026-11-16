"""
PMI Stage 3 research pipeline - IFC -> elements -> tasks -> CPM -> Gantt -> IFC4D (-> V1/V2 comparison)
=====================================================================================================
    python research/ifc_to_gantt/run.py                                  # V1 = models/original.ifc only
    python research/ifc_to_gantt/run.py --v2 models/revised.ifc          # + version comparison
    python research/ifc_to_gantt/run.py --v1 a.ifc --v2 b.ifc --start 2027-01-11 --out outputs/myproject

Writes (per version folder):  elements.csv · tasks.csv · task_element_links.csv · dependencies.csv ·
unclassified.csv · schedule.csv · gantt.html · scheduled_<v>.ifc     and, with --v2, compare/*.
Durations use ASSUMED productivity rates (task_rules.json) - preliminary, not validated.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from extract_elements import extract_ifc
from generate_tasks import generate, write
from schedule_tasks import gantt, schedule
from write_ifc4d import write_schedule

ROOT = Path(__file__).resolve().parents[2]


def run_version(ifc: Path, folder: Path, start: date, label: str, ifc4d: bool = True) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    el = extract_ifc(ifc)
    el.to_csv(folder / "elements.csv", index=False)
    tasks, links, deps, unc = generate(el)
    write(folder, tasks, links, deps, unc)
    s = schedule(tasks, start)
    s.to_csv(folder / "schedule.csv", index=False)
    days = int(s["EF"].max())
    gantt(s, f"PMI {label} - generated schedule: {days} working days "
             f"(ASSUMED productivity; black outline = critical)").write_html(folder / "gantt.html",
                                                                            include_plotlyjs="cdn")
    info = {"version": label, "ifc": str(ifc), "model_version": el["model_version"].iat[0], "elements": len(el),
            "unclassified": len(unc), "tasks": len(tasks), "dependencies": len(deps), "working_days": days,
            "finish": str(s["finish_date"].max().date())}
    if ifc4d:
        info["ifc4d"] = write_schedule(ifc, folder, folder / f"scheduled_{label.lower()}.ifc")
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--v1", type=Path, default=ROOT / "models" / "original.ifc")
    ap.add_argument("--v2", type=Path)
    ap.add_argument("--start", default="2026-11-16")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs")
    ap.add_argument("--no-ifc4d", action="store_true", help="skip writing scheduled IFC files")
    a = ap.parse_args(argv)
    start = date.fromisoformat(a.start)

    summary = {"v1": run_version(a.v1, a.out / "v1", start, "V1", not a.no_ifc4d)}
    if a.v2:
        from compare_versions import compare
        summary["v2"] = run_version(a.v2, a.out / "v2", start, "V2", not a.no_ifc4d)
        summary["compare"] = compare(a.out / "v1", a.out / "v2", a.out / "compare")
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
