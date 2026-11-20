"""Assemble the Stage 5.4B Task 7 authorization package from the existing evidence.

Reads (never writes) every Task 1-6 deliverable, the engineering register and the Stage 5.3A/5.4A
frozen exports. Writes only new Task 7 files in this package directory.
"""

import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = HERE.parents[3]
PY = REPO / ".venv/Scripts/python.exe"
PY_PLAN = REPO / ".venv-planning/Scripts/python.exe"
REGISTER = REPO / "research/validation/engineering_approval_review/priority_approval_register.csv"
S54A = REPO / "research/implementation/stage5_4a"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(name, rows):
    with (PKG / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


# --------------------------------------------------------------------------- contract R2
CONTRACT_R2 = {
    "_meta": {"contract": "PMI Stage 5.4B resource contract", "version": "5.4B-R2-addendum",
              "amends": "resource_contract.json 5.4B-R1-draft (file unchanged; this addendum takes precedence "
                        "for the sections it names)", "status": "PROPOSED; not an engineering approval"},
    "R2-1_calendar_policy": {
        "default": "intersect_project_activity_resources",
        "rule": "An activity may occupy a tick only if the tick is inside (a) the project calendar, (b) the "
                "activity's allowed_hours when declared, and (c) the calendar of every working-time resource it "
                "demands. Elapsed holds and continuous reservations ignore calendars.",
        "exception": {
            "field": "calendar_exceptions[]",
            "required_fields": ["exception_id", "activity_ids or resource_id", "replaces: project_calendar",
                                "authorization_ref", "input_state"],
            "effect": "For the named activities, (a) is replaced by the calendars named in the exception; (b) and (c) still apply.",
            "registered": [{"exception_id": "CAL-EXC-RC06", "case": "RC06", "activity_ids": ["N"],
                            "replaces": "project_calendar", "with": "FERRALLISTA calendar 07:00-15:00",
                            "authorization_ref": "HYPOTHETICAL test authorisation; AP-X-CAL-01 PENDING"}],
            "on_missing_authorization": "Apply the default policy; never infer an exception from a resource calendar."},
        "cases": ["RC06 (exception, unchanged)", "RC06-D (default policy)"],
        "supersedes": "R1 ActivityResourceRequirement.allowed_hours note and Task 4 convention 'activity_calendar'"},
    "R2-2_mode_occupancy": {
        "rule": "The selected crew mode is occupied in full for every working segment. Units without positive "
                "Stage 5.3A demand are kept as declared reservations; they are never removed silently.",
        "fields": {"reserved_without_bcca_demand": "object resource_id -> units, required whenever a mode unit has "
                                                   "zero worker_hours_by_trade / machine_hours_by_class",
                   "reason": "string, required", "approval_ref": "AP-X-CREW-01 (PENDING)"},
        "duration": "Unchanged: Stage 5.3A productive_hours from positive-demand bounds only.",
        "cost": "Unchanged: no cost line for reserved-without-demand units (BCCA price governs).",
        "validation_V5_R2": "mode units == worker_capacity_by_trade + equipment_capacity_by_class + "
                            "reserved_without_bcca_demand, exactly; anything else is MODEL_INVALID (MODE_MISMATCH).",
        "known_instances": ["R0 COL-CONC: OFICIAL 1ª x1 (HYP-CONC)",
                            "Larger demo C1-POUR..C4-POUR: OFICIAL_1 x1 (HYP-CONC)"]},
    "R2-3_strength_release": {
        "fixed_timestamp": {"status": ["recorded_pass", "hypothetical_recorded_pass"], "requires": "at",
                            "semantics": "Release finish = max(pour finish + elapsed minimum, at). 'at' is an absolute "
                                         "bound that does not move with the pour (Agent 1 N2).", "case": "RC13a"},
        "at_minimum": {"status": "hypothetical_pass_at_minimum",
                       "semantics": "Release finish = pour finish + elapsed minimum (fixture only)."},
        "activity_dependent_test": {"status": ["planned", "pending_result"],
                                    "requires": ["test_age_hours_after_pour", "acceptance_criterion_ref"],
                                    "semantics": "Projection only: max(minimum, test age) measured from the pour, "
                                                 "moving with the pour. Schedule status CONDITIONAL; never OPTIMAL, "
                                                 "never releasable, never converted to a timestamp.", "case": "RC13b"},
        "failed": "Successors blocked (RELEASE_FAILED).", "missing": "CONDITIONAL (RELEASE_CONDITIONAL)."},
    "R2-4_inspection_pass": {
        "event": {"event_id": "string", "inspection_activity": "activity_id", "gates": "successor activity_ids",
                  "status": ["hypothetical_pass", "recorded_pass", "failed", "missing"], "at": "required for recorded_pass",
                  "input_state": "enum"},
        "semantics": {"hypothetical_pass": "Pass at inspection finish (fixture only).",
                      "recorded_pass": "Fixed not-before on every gated successor; at < inspection earliest finish is "
                                       "MODEL_INVALID (EVENT_BEFORE_ACTIVITY_FINISH).",
                      "missing": "Projected as at finish; gated successors CONDITIONAL.",
                      "failed": "Gated successors and descendants BLOCKED (INSPECTION_FAILED)."},
        "cases": ["RC12a", "RC12b", "RC12c", "RC12d", "RC12e"]},
    "R2-5_controlled_fixture_exceptions": [
        {"id": "FX-R0-01", "fixture": "R0 (Stage 5.4A three-element)", "item": "Formwork panel and prop reservations",
         "treatment": "Excluded and reported unenforced; no counts introduced."},
        {"id": "FX-R0-02", "fixture": "R0", "item": "Inspection pass events absent in Stage 5.3A/5.4A sources",
         "treatment": "Declared hypothetical_pass for C/B/S-INSP (test only)."},
        {"id": "FX-R0-03", "fixture": "R0", "item": "Inspector calendar not declared",
         "treatment": "PROJECT calendar declared explicitly, as applied by Stage 5.4A."},
        {"id": "FX-R0-04", "fixture": "R0", "item": "Shared concrete supply rate",
         "treatment": "Not modelled: CONCRETE_DELIVERY explicit none; 08:00-14:00 window only."},
        {"id": "FX-R0-05", "fixture": "R0", "item": "Strength releases",
         "treatment": "hypothetical_pass_at_minimum (unchanged)."},
        {"id": "FX-R0-06", "fixture": "R0", "item": "Europe/Paris to Europe/Madrid calendar and 2027-01-06 holiday",
         "treatment": "Deliberate override verified by Agent 1 (equal recurring windows)."},
        {"id": "FX-DEMO-01", "fixture": "Larger demo", "item": "No date exceptions declared",
         "treatment": "Benchmark keeps none (40,445 min); DEMO-H1 tests 2027-03-01 non-working (41,885 min)."},
        {"id": "FX-DEMO-02", "fixture": "Larger demo", "item": "return_lead_minutes = 0, reshoring not permitted",
         "treatment": "Explicit hypothetical inputs; AP-X-FW-03/04 PENDING."}],
}

# --------------------------------------------------------------------------- approval addendum
ADDENDUM = [
    ("AP-X-CAL-01", "calendar exception", "Authorise named activities to work on a resource calendar outside the project shift (for example ferrallista 07:00-15:00).", "RC06 / CAL-EXC-RC06", "R2-1"),
    ("AP-X-CAL-02", "calendar exceptions", "Confirm declared project holidays and regional date exceptions, including whether 2027-03-01 is non-working in Andalusia.", "FX-DEMO-01, DEMO-H1", "ResourceCalendar.date_exceptions"),
    ("AP-X-CREW-01", "crew mode", "Approve fixed crew modes that reserve units without positive BCCA demand (HYP-CONC oficial on 05HHP00003 column pours).", "R0 COL-CONC; demo C1-C4 POUR", "R2-2"),
    ("AP-X-INSP-01", "inspection", "Approve inspection criteria, inspector authority and calendar, inspection duration and how pass and fail events are recorded.", "RC04, RC12a-e, FX-R0-02/03", "R2-4"),
    ("AP-X-STR-01", "strength release", "Approve the evidence form for a timestamped recorded strength pass used as a fixed release bound.", "RC13a", "R2-3 fixed_timestamp"),
    ("AP-X-STR-02", "strength release", "Approve planned strength-test ages and acceptance criteria for activity-dependent tests (projection only).", "RC13b", "R2-3 activity_dependent_test"),
    ("AP-X-FW-01", "reusable formwork", "Approve formwork panel set counts on site and per-element set demand.", "RC05a/b; demo COL/BEAM/SLAB sets", "Reservation.quantity; Resource.capacity"),
    ("AP-X-FW-02", "props and shoring", "Approve prop and shoring pool sizes and per-element prop counts (not derivable from BCCA amortisation coefficients).", "demo BEAM_PROP, SLAB_PROP", "Reservation.quantity (P5)"),
    ("AP-X-FW-03", "reservation release", "Approve reservation start and release events (FORM start to STRIP finish; beam props retained until supported slab sections are stripped) and return lead times.", "RC05a/b; demo; FX-DEMO-02", "ReleaseCondition"),
    ("AP-X-FW-04", "reshoring", "Decide whether back-propping or reshoring is permitted and how it is modelled (excluded from 05HED00001).", "FX-DEMO-02", "ReleaseCondition.reshoring"),
    ("AP-X-SUP-01", "concrete supply", "Approve plant rate, delivery window, per-pour drawn rate and the placement method without crane or pump.", "RC11a/b; demo CONCRETE_SUPPLY", "SupplySource; PourSupplyDemand"),
    ("AP-X-SPL-01", "split work", "Approve split-work authorisation rules, minimum segments, retention, restart overhead and pour cold joints.", "RC10a-c", "SplitPolicy"),
    ("AP-X-SEQ-01", "sequencing", "Approve the multi-element support and prop-retention sequence used by the larger demo. This extends AP-DR09 without modifying it.", "demo dependencies (98)", "Dependency rules"),
]

# --------------------------------------------------------------------------- remaining deficiencies
DEFICIENCIES = [
    ("RD01", "nonblocking", "Larger demo builder", "The representative optimal schedule depends on Python hash randomisation (set iteration in the lower-bound enumeration). Across 10 seeds the inputs, the 40,445-minute proven optimum, CPM, 29 conflicts and cost were identical; dates differ between alternative optima. demo_report.md's 'deterministic' statement is therefore inaccurate for schedule dates.", "Acceptance compares status, makespan, cost and feasibility only (AC-D series). Rerun sensitivity with PYTHONHASHSEED=0. The committed files are preserved unchanged.", "Task 6 verifier"),
    ("RD02", "nonblocking", "Package housekeeping", "scripts/out/ holds stale duplicates of the Task 1-3 verification CSVs, created before the output path was fixed and since committed.", "Ignore; the top-level CSVs are authoritative (manifest marks them superseded).", "Task 1-3 verifier"),
    ("RD03", "mandatory requirement", "Calendars", "Stage 5.4A CPM has no named resource calendars or exception register.", "CP-SAT must implement R2-1 (default intersection plus registered exceptions); RC06 and RC06-D must both pass.", "Agent 1"),
    ("RD04", "mandatory requirement", "Reservations", "No production code models continuous reusable-asset reservations.", "Span intervals from start event to release plus return lead, in a cumulative constraint per asset; RC05a/b and the larger demo must pass.", "Agent 1"),
    ("RD05", "mandatory requirement", "Concrete supply", "Stage 5.3A uses throughput only as a per-pour duration bound; there is no shared rate pool.", "Rate cumulative on the supply calendar with integer drawn rates; RC11a/b and the demo must pass. Durations stay from 5.3A.", "Agent 1"),
    ("RD06", "mandatory requirement", "Events", "Inspection pass events and activity-dependent strength tests are not in production data structures.", "Implement R2-3 and R2-4 statuses, including CONDITIONAL, BLOCKED and MODEL_INVALID outcomes (RC12a-e, RC13a-b).", "Agent 1"),
    ("RD07", "mandatory requirement", "Mode occupancy", "Contract V5 (R1) did not cover reserved units without BCCA demand.", "Use V5-R2 with reserved_without_bcca_demand; keep durations and costs unchanged (R2-2).", "Agent 1"),
    ("RD08", "mandatory requirement", "Identity", "Stage 5.4A uses non-ASCII BCCA display names as resource ids (contract O3).", "Stable resource_id with display_name retained.", "Agent 1"),
    ("RD09", "mandatory requirement", "Split work", "Stage 5.4A greedy split has no authorisation, retention, overhead or pause policy.", "Implement SplitPolicy, or reject unsupported choices with SPLIT_NOT_AUTHORIZED / MODEL_INVALID; RC10a-c must pass.", "Agent 1"),
    ("RD10", "nonblocking", "Multi-mode", "Stage 5.3A emits one mode per activity (O4).", "Keep single-mode for controlled CP-SAT; multi-mode needs per-mode 5.3A estimates first.", "future"),
    ("RD11", "nonblocking", "R0 fixture scope", "R0 has no reservations, pass events or supply rate in its sources.", "Run under fixture exceptions FX-R0-01..06; report reservations as unenforced.", "Agent 1"),
    ("RD12", "out of scope", "Relations", "SS, FF and SF relations and negative lags are unsupported.", "Reject with UNSUPPORTED_RELATION.", "future"),
    ("RD13", "blocking for real projects only", "Engineering approvals", "75 original approvals plus 13 addendum approvals are PENDING; quantities are not independently measured.", "No real-project scheduling release.", "engineer / register owner"),
    ("RD14", "nonblocking", "Holiday data", "Whether 2027-03-01 is non-working in Andalusia was not verified.", "Benchmark unchanged; DEMO-H1 bounds the effect (+1,440 min). Decide via AP-X-CAL-02.", "user"),
    ("RD15", "nonblocking", "Chart palette", "The dataviz palette validator (Node) could not run; the documented pre-validated reference slots were used.", "None for scheduling.", "Task 6 report"),
]


def acceptance_rows():
    rows = []

    def add(cid, cat, scope, req, cond, src, mandatory="yes", note=""):
        rows.append({"criterion_id": cid, "category": cat, "scope": scope, "requirement": req, "pass_condition": cond,
                     "source": src, "mandatory_for_controlled_cpsat": mandatory, "notes": note})

    ref = load(PKG / "cpsat_reference_cases.json")
    for i, text in enumerate(ref["general_acceptance_criteria"], 1):
        add(f"AC-G{i:02d}", "general", "all cases", text.split(":")[0], text, "cpsat_reference_cases.json#general_acceptance_criteria")
    add("AC-G10", "general", "all cases", "Resolution", "5-minute tick for new cases; 15-minute tick retained for R0-15 regression; ticks must divide 60 and every boundary (TICK_MISALIGNED otherwise)", "Task 3; Agent 1 N3")
    add("AC-G11", "general", "all cases", "Default calendar policy", "Every occupied tick lies in project AND allowed_hours AND every demanded resource calendar unless a registered exception names the activity", "resource_contract_R2_addendum.json#R2-1")
    for c in ref["cases"]:
        e = c["expected"]
        cond = f"status {e['expected_status']}"
        if e.get("optimal_makespan_minutes") is not None:
            cond += f"; makespan {e['optimal_makespan_minutes']} min; completion {e['completion_local']}"
        if e.get("preflight_code"):
            cond += f"; diagnostic {e['preflight_code']}"
        cond += "; schedule must equal reference_schedule" if e.get("unique_optimal_schedule") is True else ""
        note = "authorised calendar exception CAL-EXC-RC06" if c["case_id"] == "RC06" else ""
        add(f"AC-{c['case_id']}", "reference case", c["case_id"], c["title"], cond, "cpsat_reference_cases.json", note=note)
    t7 = load(PKG / "task7_reference_cases.json")
    for c in t7["cases"]:
        if c["case_id"] == "RC06":
            continue
        e = c["expected"]
        cond = f"status {e['expected_status']}"
        if e.get("optimal_makespan_minutes") is not None:
            cond += f"; makespan {e['optimal_makespan_minutes']} min; completion {e['completion_local']}"
        if e.get("preflight_code"):
            cond += f"; diagnostic {e['preflight_code']}"
        if e.get("schedule") and c["case_id"] != "DEMO-H1":
            # RELEASE is excluded: R2-3 reports release finish as max(minimum, timestamp), which the
            # reference encodes as a not-before on STRIP. Compare the productive activities only.
            cond += "; dates " + ", ".join(f"{r['id']} {r['start'][5:16]} to {r['finish'][5:16]}"
                                           for r in e["schedule"] if r["id"] != "RELEASE")
        add(f"AC-{c['case_id']}", "Task 7 case", c["case_id"], c["title"], cond, "task7_reference_cases.json",
            mandatory="yes" if c["case_id"] != "DEMO-H1" else "no", note=e.get("note", ""))
    contract = load(PKG / "resource_contract.json")
    for p in contract["principles"]:
        pid = p.split(" ")[0]
        add(f"AC-C-{pid}", "contract principle", "all inputs", p.split(".")[0], p, "resource_contract.json#principles")
    for v in contract["validation_rules"]:
        rule = v["rule"]
        if v["id"] == "V5":
            rule = CONTRACT_R2["R2-2_mode_occupancy"]["validation_V5_R2"]
        add(f"AC-C-{v['id']}", "contract validation", "all inputs", v["id"], f"{rule} -> {v['code']}",
            "resource_contract.json#validation_rules" + (" (V5 replaced by R2)" if v["id"] == "V5" else ""))
    for r in contract["entities"]["CapacityPolicy"]["rules"]:
        add(f"AC-C-{r['code']}", "contract diagnostic", "preflight", r["code"], f"When {r['when']} -> {r['status']}; {r['action']}",
            "resource_contract.json#CapacityPolicy")
    for k in ("R2-1_calendar_policy", "R2-2_mode_occupancy", "R2-3_strength_release", "R2-4_inspection_pass"):
        add(f"AC-{k.split('_')[0]}", "contract R2", "all inputs", k, "Implemented exactly as specified", "resource_contract_R2_addendum.json")
    demo = load(PKG / "controlled_resource_demo/expected_results.json")
    cf = demo["capacity_feasible"]
    add("AC-D01", "larger demo", "controlled_resource_demo", "Objective",
        f"status OPTIMAL; makespan {cf['makespan_minutes']} min; completion {cf['completion_local']}",
        "controlled_resource_demo/expected_results.json")
    add("AC-D02", "larger demo", "controlled_resource_demo", "Feasibility", "Returned schedule passes every check type in feasibility_checks.csv (calendars, precedence, strike from pour, per-minute capacity, continuous reservations)", "controlled_resource_demo/feasibility_checks.csv")
    add("AC-D03", "larger demo", "controlled_resource_demo", "CPM baseline", f"completion {demo['cpm']['completion_local']}; {demo['cpm']['resource_conflicts']} conflict intervals on {len(demo['cpm']['resources_over_capacity'])} pools", "controlled_resource_demo/cpm_resource_conflicts.csv")
    add("AC-D04", "larger demo", "controlled_resource_demo", "Cost", f"direct reference cost {demo['direct_reference_cost_eur']} EUR identical for CPM and capacity-feasible", "controlled_resource_demo/expected_results.json")
    add("AC-D05", "larger demo", "controlled_resource_demo", "Schedule dates", "Not compared: alternative optima exist (RD01)", "remaining_deficiencies.csv#RD01", mandatory="no")
    add("AC-P01", "preservation", "engineering register", "Original approvals", "75 approvals in priority_approval_register.csv unchanged and PENDING", "preservation_verification.json")
    add("AC-P02", "preservation", "Stage 5.4A", "R0-15 regression", "completion 2027-01-14T16:00+01:00; 14,880 min; 8 exports byte-identical", "research/implementation/stage5_4a")
    add("AC-P03", "preservation", "Stage 5.4A", "R0-5", "completion 2027-01-14T15:30+01:00; 14,850 min", "cpsat_reference_cases.json#R0-5")
    add("AC-P04", "preservation", "Stage 5.3A", "Cost", "1,172.5136 EUR unchanged", "scheduling_handover.json")
    add("AC-P05", "preservation", "release", "Real-project gate", "real_project_eligible = false for every output", "all")
    return rows


def run_checks():
    tests = subprocess.run([str(PY), "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_stage5_*.py"],
                           cwd=REPO, capture_output=True, text=True)
    ran = re.search(r"Ran (\d+) tests", tests.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "repro"
        rep = subprocess.run([str(PY_PLAN), "-B", "-m", "pmi_core.scheduling", "--config",
                              "research/implementation/stage5_4a/controlled_schedule_inputs.json", "--output", str(out)],
                             cwd=REPO, capture_output=True, text=True)
        files = sorted(p.name for p in out.iterdir())
        same = [f for f in files if (S54A / f).read_bytes() == (out / f).read_bytes()]
    return {"tests_ran": int(ran.group(1)) if ran else None, "tests_ok": tests.returncode == 0 and "OK" in tests.stderr,
            "cpm_reproduction_exit": rep.returncode, "cpm_exports": len(files), "cpm_exports_byte_identical": len(same)}


def main():
    (PKG / "resource_contract_R2_addendum.json").write_text(json.dumps(CONTRACT_R2, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv("engineering_approval_addendum.csv", [
        {"approval_id": a, "category": c, "description": d, "affected_cases_or_fixtures": s, "contract_field": f,
         "required_for_controlled_cpsat": "no (hypothetical inputs declared)", "required_for_real_project": "yes",
         "status": "PENDING", "decision": "", "decision_date": "",
         "note": "Addendum only. The original 75 approvals in priority_approval_register.csv are unchanged."}
        for a, c, d, s, f in ADDENDUM])
    write_csv("remaining_deficiencies.csv", [
        {"id": i, "classification": k, "area": a, "deficiency": d, "required_action": r, "owner": o}
        for i, k, a, d, r, o in DEFICIENCIES])
    write_csv("acceptance_criteria.csv", acceptance_rows())

    checks = run_checks()
    with REGISTER.open(encoding="utf-8-sig", newline="") as f:
        register = list(csv.DictReader(f))
    status = git("status", "--porcelain").splitlines()
    tracked_modified = [s for s in status if not s.startswith("??")]
    head = git("rev-parse", "HEAD").strip()
    protected = {
        "engineering register": REGISTER,
        "Stage 5.3A handover": REPO / "research/implementation/stage5_3/scheduling_handover.json",
        "Stage 5.4A schedule": S54A / "schedule.json",
        "Task 4 reference cases": PKG / "cpsat_reference_cases.json",
        "Task 5 resource contract": PKG / "resource_contract.json",
        "Task 6 benchmark inputs": PKG / "controlled_resource_demo/fixture_inputs.json",
        "Task 6 benchmark results": PKG / "controlled_resource_demo/expected_results.json",
    }
    preservation = {
        "verified_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head": head, "tracked_files_modified": tracked_modified,
        "untracked_new_files": [s[3:] for s in status if s.startswith("??")],
        "original_approvals": {"rows": len(register), "pending": sum(r["status"] == "PENDING" for r in register),
                               "sha256": sha(REGISTER)},
        "protected_file_sha256": {k: sha(p) for k, p in protected.items()},
        "protected_files_equal_head": all(not any(s.endswith(p.relative_to(REPO).as_posix()) for s in tracked_modified)
                                          for p in protected.values()),
        **checks,
        "benchmark": {"makespan_minutes": load(PKG / "controlled_resource_demo/expected_results.json")["capacity_feasible"]["makespan_minutes"],
                      "status": "unchanged (40,445 min proven); holiday variant written to a separate folder"},
        "production_code_modified": any("pmi_core/" in s for s in tracked_modified),
        "notes": ["No dependencies installed; no commit or push.",
                  "Agent 1 claims verified: 43 tests, 8 byte-identical exports, tick alignment, timestamped release regression, Paris-to-Madrid check."],
    }
    (PKG / "preservation_verification.json").write_text(json.dumps(preservation, indent=2) + "\n", encoding="utf-8")

    roles = {
        "verification_report.md": ("Task 1-3", "report"), "discrepancy_register.csv": ("Task 1-3", "findings"),
        "cpsat_reference_cases.json": ("Task 4", "acceptance input (22 cases)"),
        "cpsat_expected_results.csv": ("Task 4", "acceptance summary"), "cpsat_reference_report.md": ("Task 4", "report"),
        "resource_contract.json": ("Task 5", "contract R1 (amended by R2 addendum)"),
        "resource_contract_mapping.csv": ("Task 5", "contract mapping"), "resource_contract_report.md": ("Task 5", "report"),
        "task7_reference_cases.json": ("Task 7", "acceptance input addendum"),
        "resource_contract_R2_addendum.json": ("Task 7", "contract R2 addendum"),
        "stage5_4b_readiness.md": ("Task 7", "authorization decision"),
        "acceptance_criteria.csv": ("Task 7", "consolidated acceptance criteria"),
        "remaining_deficiencies.csv": ("Task 7", "deficiency register"),
        "engineering_approval_addendum.csv": ("Task 7", "pending approval addendum"),
        "preservation_verification.json": ("Task 7", "preservation record"),
    }
    tracked = set(git("ls-files", PKG.relative_to(REPO).as_posix()).splitlines())
    entries = []
    for p in sorted(PKG.rglob("*")):
        if p.is_dir() or "__pycache__" in p.parts or p.name == "deliverable_manifest.json":
            continue
        rel = p.relative_to(PKG).as_posix()
        task, role = roles.get(rel, (None, None))
        if task is None:
            task = ("Task 6" if rel.startswith("controlled_resource_demo/") else
                    "Task 7" if rel.startswith("controlled_resource_demo_holiday_sensitivity/") or "task7" in rel else
                    "Task 1-3" if rel.startswith("scripts/out/") or rel.endswith("_verification.csv")
                    or rel in ("resolution_sensitivity.csv", "verification_summary.json") else "scripts")
            role = ("superseded duplicate (RD02)" if rel.startswith("scripts/out/") else
                    "sensitivity case DEMO-H1" if "holiday_sensitivity" in rel else
                    "benchmark (preserved)" if rel.startswith("controlled_resource_demo/") else
                    "generator" if rel.endswith(".py") else "evidence")
        entries.append({"path": rel, "task": task, "role": role, "bytes": p.stat().st_size, "sha256": sha(p),
                        "tracked_in_head": p.relative_to(REPO).as_posix() in tracked})
    manifest = {
        "package": "research/validation/stage5_4a_independent_verification", "git_head": head,
        "decision": "CONDITIONAL GO for controlled CP-SAT implementation; NO-GO for real-project scheduling",
        "exact_input_files": {
            "acceptance_cases": ["research/validation/stage5_4a_independent_verification/cpsat_reference_cases.json",
                                 "research/validation/stage5_4a_independent_verification/task7_reference_cases.json"],
            "contract": ["research/validation/stage5_4a_independent_verification/resource_contract.json",
                         "research/validation/stage5_4a_independent_verification/resource_contract_R2_addendum.json"],
            "larger_benchmark": ["research/validation/stage5_4a_independent_verification/controlled_resource_demo/fixture_inputs.json",
                                 "research/validation/stage5_4a_independent_verification/controlled_resource_demo/expected_results.json"],
            "holiday_sensitivity": ["research/validation/stage5_4a_independent_verification/controlled_resource_demo_holiday_sensitivity/fixture_inputs.json",
                                    "research/validation/stage5_4a_independent_verification/controlled_resource_demo_holiday_sensitivity/expected_results.json"],
            "r0_regression": ["research/implementation/stage5_4a/controlled_schedule_inputs.json",
                              "research/implementation/stage5_3/scheduling_handover.json",
                              "research/implementation/stage5_3/fixture_inputs.json",
                              "research/planning/stage5_4_preparation/controlled_scheduling_inputs.json"],
            "acceptance_criteria": ["research/validation/stage5_4a_independent_verification/acceptance_criteria.csv"],
        },
        "files": entries,
    }
    (PKG / "deliverable_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: preservation[k] for k in ("git_head", "tracked_files_modified", "original_approvals", "tests_ran",
                                                    "tests_ok", "cpm_exports", "cpm_exports_byte_identical",
                                                    "protected_files_equal_head")}, indent=1))
    print(len(acceptance_rows()), "acceptance criteria;", len(entries), "files in manifest")


if __name__ == "__main__":
    main()
