"""Compare the independent verifier with production, check every claim, run tick sensitivity."""

import csv
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import independent_cpm as ind  # noqa: E402

OUT = HERE.parent
OUT.mkdir(exist_ok=True)
S54 = REPO / "research/implementation/stage5_4a"
PREP = REPO / "research/planning/stage5_4_preparation"


def mins(text, zone):
    return int(datetime.fromisoformat(text).astimezone(zone).timestamp() // 60)


def write(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)


prod = ind.load(S54 / "schedule.json")
h, prep, acts, edges_a, edges_b = ind.build_model(15)
E = ind.final_edges(edges_a)
mine = ind.schedule(15, E)
zone = mine["cal"].zone
P = {r["reference_id"]: r for r in prod["activities"]}
findings = []

# ---- activities ----
act_rows = []
expected = {r["id"]: r for r in csv.DictReader((PREP / "fixture_expected_schedule.csv").open(encoding="utf-8-sig"))}
for a in mine["order"]:
    p = P[a]
    row = {
        "activity": a, "kind_independent": acts[a]["kind"], "kind_production": p["kind"],
        "raw_minutes": round(acts[a]["raw"], 6), "scheduled_minutes": acts[a]["dur"],
        "es": mine["cal"].fmt(mine["ES"][a]), "ef": mine["cal"].fmt(mine["EF"][a]),
        "ls": mine["cal"].fmt(mine["LS"][a]), "lf": mine["cal"].fmt(mine["LF"][a]),
        "total_float": mine["LS"][a] - mine["ES"][a], "free_float": mine["FF"][a],
        "critical": mine["LS"][a] == mine["ES"][a],
    }
    checks = {
        "scheduled_minutes": acts[a]["dur"] == p["scheduled_minutes"],
        "es": mine["ES"][a] == mins(p["earliest_start"], zone),
        "ef": mine["EF"][a] == mins(p["earliest_finish"], zone),
        "ls": mine["LS"][a] == mins(p["latest_start"], zone),
        "lf": mine["LF"][a] == mins(p["latest_finish"], zone),
        "total_float": row["total_float"] == p["total_float_minutes"],
        "free_float": row["free_float"] == p["free_float_minutes"],
        "critical": row["critical"] == p["critical"],
        "agent2_start": mine["cal"].fmt(mine["ES"][a]).replace("T", " ")[:16] == expected[a]["start_local"],
        "agent2_finish": mine["cal"].fmt(mine["EF"][a]).replace("T", " ")[:16] == expected[a]["finish_local"],
    }
    row.update({f"match_{k}": v for k, v in checks.items()})
    row["all_match"] = all(checks.values())
    act_rows.append(row)
write("activity_verification.csv", act_rows)

# ---- dependencies ----
prod_edges = {(d["predecessor_alias"], d["successor_alias"]): d for d in prod["dependencies"]}
dep_rows = []
for e in sorted(E | set(prod_edges) | edges_b):
    d = prod_edges.get(e)
    ok_time = mine["ES"][e[1]] >= mine["EF"][e[0]]
    # transitive redundancy relative to the other edges
    others = (E | set(prod_edges)) - {e}
    stack, seen, redundant = [e[0]], set(), False
    while stack:
        n = stack.pop()
        for x, y in others:
            if x == n and y not in seen:
                if y == e[1]:
                    redundant = True
                seen.add(y); stack.append(y)
    dep_rows.append({
        "predecessor": e[0], "successor": e[1], "in_production": d is not None,
        "in_independent_derivation": e in E, "in_agent2_preparation": e in edges_b,
        "relation": d["relation"] if d else "", "lag_minutes": d["lag_minutes"] if d else "",
        "lag_basis": d["lag_basis"] if d else "", "rule_id": d["rule_id"] if d else "",
        "source": d["source"] if d else "", "satisfied": ok_time, "transitively_redundant": redundant,
    })
write("dependency_verification.csv", dep_rows)

# ---- calendar / delivery / holds / release / resources ----
cal = mine["cal"]
cal_rows = []
for a in mine["order"]:
    r = acts[a]
    s, f = mine["ES"][a], mine["EF"][a]
    if r["kind"] == "elapsed":
        pour = f"{a[0]}-POUR"
        cal_rows.append({"activity": a, "check": "elapsed_from_pour_finish",
                         "passed": s == mine["EF"][pour] and f - s == r["dur"], "detail": f"{r['dur']} elapsed min"})
        if a.endswith("STRIKE"):
            st = P[a]["release_status"]
            cal_rows.append({"activity": a, "check": "strength_release_explicit_event",
                             "passed": st == "hypothetical_pass_at_minimum" and not P[a]["conditional"],
                             "detail": st})
            strip = f"{a[0]}-STRIP"
            cal_rows.append({"activity": strip, "check": "strip_after_strike_and_cure",
                             "passed": mine["ES"][strip] >= max(f, mine["EF"][f"{a[0]}-CURE"]),
                             "detail": cal.fmt(mine["ES"][strip])})
        continue
    days = {datetime.fromtimestamp(m * 60, zone).date().isoformat() for m in range(s, f)}
    cal_rows.append({"activity": a, "check": "working_minutes_only", "passed": cal.ok(s, f - s, False),
                     "detail": ",".join(sorted(days))})
    cal_rows.append({"activity": a, "check": "no_weekend_or_holiday",
                     "passed": all(datetime.fromisoformat(d).isoweekday() <= 5 and d != "2027-01-06" for d in days),
                     "detail": ""})
    if r["pour"]:
        cal_rows.append({"activity": a, "check": "inside_delivery_window_0800_1400",
                         "passed": cal.ok(s, f - s, True), "detail": f"{cal.fmt(s)}..{cal.fmt(f)}"})
    if r["kind"] == "inspection":
        cal_rows.append({"activity": a, "check": "inspection_30_working_min_one_inspector",
                         "passed": f - s == 30 and r["res"] == {"INSPECTOR": 1} == P[a]["resources"],
                         "detail": ""})
write("calendar_constraint_verification.csv", cal_rows)

res_rows = [{"resource": n, "capacity": mine["caps"].get(n), "peak_usage": mine["peaks"][n],
             "over_capacity": mine["peaks"][n] > mine["caps"].get(n, 0)} for n in sorted(mine["peaks"])]
write("resource_profile_verification.csv", res_rows)

cost_sum = round(sum(r["cost"] or 0 for r in acts.values()), 6)
summary = {
    "completion_independent": cal.fmt(mine["done"]), "completion_production": prod["project_completion"],
    "makespan_independent": mine["makespan"], "makespan_production": prod["makespan_elapsed_minutes"],
    "critical_independent": mine["critical"], "critical_production": [{r["id"]: r["reference_id"] for r in prod["activities"]}[u] for u in prod["critical_activity_ids"]],
    "activities": len(act_rows), "activities_all_fields_match": sum(r["all_match"] for r in act_rows),
    "edges_production": len(prod_edges), "edges_independent": len(E),
    "edges_equal": set(prod_edges) == E,
    "edges_agent2": len(edges_b), "edges_in_production_not_agent2": sorted(map(list, set(prod_edges) - edges_b)),
    "edges_in_agent2_not_production": sorted(map(list, edges_b - set(prod_edges))),
    "all_edges_satisfied": all(r["satisfied"] for r in dep_rows),
    "calendar_checks": len(cal_rows), "calendar_checks_passed": sum(r["passed"] for r in cal_rows),
    "resource_over_capacity": mine["over"], "resource_conflicts_production": prod["resource_conflicts"],
    "cost_handover_total": h["cost"]["total_direct_reference_eur"], "cost_schedule_total": prod["cost"]["total_direct_reference_eur"],
    "cost_sum_of_activity_lines": cost_sum,
    "timezone_production": prod["calendar"]["timezone"], "holidays": prod["calendar"]["date_exceptions"],
    "pending_approvals": sum(1 for a in prod["pending_approvals"] if a["status"] == "PENDING"),
    "real_project_eligible": prod["real_project_eligible"],
}

# ---- tick sensitivity using the existing production interfaces ----
sys.path.insert(0, str(REPO))
import os
os.chdir(REPO)
from pmi_core.scheduling.fixture import adapt, read_json  # noqa: E402
from pmi_core.scheduling.__main__ import validate_schedule  # noqa: E402

handover = read_json(REPO / "research/implementation/stage5_3/scheduling_handover.json")
prepared = read_json(PREP / "controlled_scheduling_inputs.json")
base_cfg = read_json(S54 / "controlled_schedule_inputs.json")
sens = []
for tick in (1, 5, 15, 7, 45, 60):
    cfg = {**base_cfg, "tick_minutes": tick}
    try:
        runs = []
        for _ in range(15):
            t = time.perf_counter(); sch = adapt(handover, prepared, cfg); runs.append(time.perf_counter() - t)
        checks, _, _ = validate_schedule(sch, PREP / "fixture_expected_schedule.csv")
        prodrows = [r for r in sch["activities"] if r["kind"] == "productive"]
        inspect_rows = [r for r in sch["activities"] if r["kind"] == "inspection"]
        indep = ind.schedule(tick, E)
        agree = (indep["done"] == mins(sch["project_completion"], zone)
                 and indep["critical"] == [{r["id"]: r["reference_id"] for r in sch["activities"]}[u] for u in sch["critical_activity_ids"]]
                 and all(indep["ES"][r["reference_id"]] == mins(r["earliest_start"], zone)
                         and indep["LS"][r["reference_id"]] == mins(r["latest_start"], zone)
                         and indep["FF"][r["reference_id"]] == r["free_float_minutes"] for r in sch["activities"]))
        sens.append({
            "tick_minutes": tick, "status": sch["status"],
            "original_productive_minutes": round(sum(r["duration_minutes"] for r in prodrows), 6),
            "scheduled_productive_minutes": sum(r["scheduled_minutes"] for r in prodrows),
            "rounding_allowance_minutes": round(sum(r["rounding_minutes"] for r in prodrows), 6),
            "inspection_minutes": sum(r["scheduled_minutes"] for r in inspect_rows),
            "project_completion": sch["project_completion"], "makespan_elapsed_minutes": sch["makespan_elapsed_minutes"],
            "critical_activities": " ".join(r["reference_id"] for r in sch["activities"] if r["critical"]),
            "calendar_checks_passed": f"{sum(c['passed'] for c in checks)}/{len(checks)}",
            "resource_conflicts": len(sch["resource_conflicts"]),
            "independent_agreement": agree,
            "grid_aligned_to_shift_and_delivery_boundaries": all(((mins(f"2027-01-04T{hh}:00+01:00", zone)) % tick) == 0 for hh in ("08", "14", "16")),
            "median_runtime_ms": round(statistics.median(runs) * 1000, 2),
            "max_runtime_ms": round(max(runs) * 1000, 2), "note": "",
        })
    except Exception as exc:  # report unsupported resolutions
        sens.append({"tick_minutes": tick, "status": "error", "note": f"{type(exc).__name__}: {exc}"})
keys = list(sens[0])
for row in sens:
    for k in keys:
        row.setdefault(k, "")
write("resolution_sensitivity.csv", sens)
(OUT / "verification_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary, indent=1, ensure_ascii=False))
for r in sens:
    print(r)
for r in act_rows:
    if not r["all_match"]:
        print("MISMATCH", r)
for r in dep_rows:
    if not (r["in_production"] and r["in_independent_derivation"] and r["in_agent2_preparation"]) or r["transitively_redundant"]:
        print("EDGE", r)
