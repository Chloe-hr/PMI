"""Task 7 addendum cases. Adds to (never edits) the 22 Task 4 cases and the Task 6 benchmark.

* RC06-D  default calendar policy (project AND activity AND resource calendars); RC06 stays the
          explicitly authorised resource-calendar exception.
* RC12a-d inspection pass events (hypothetical, missing, failed, recorded later).
* RC13a-b strength release: timestamped fixed pass versus a future activity-dependent test.
* DEMO-H1 larger benchmark with 2027-03-01 declared non-working (sensitivity only), written to
          controlled_resource_demo_holiday_sensitivity/ by the unchanged Task 6 builder.
"""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import build_cpsat_reference_cases as t4  # noqa: E402

DEFAULT_POLICY = "intersect_project_activity_resources"
EXCEPTION_POLICY = "resource_calendars_only (authorised exception)"
_prepare = t4.prepare


def prepare_with_policy(case):
    model = _prepare(case)
    if case.get("calendar_policy", DEFAULT_POLICY) == DEFAULT_POLICY:
        pm = t4.calendar_mask(case["project_calendar"], model["anchor"], model["n"], model["tick"], model["zone"])
        for k in model["avail"]:
            model["avail"][k] = bytearray(a & b for a, b in zip(model["avail"][k], pm))
    return model


t4.prepare = prepare_with_policy


def by_id(cases, cid):
    return next(c for c in cases if c["case_id"] == cid)


def summary(exp):
    keep = ("expected_status", "optimal_makespan_minutes", "completion_local", "unique_optimal_schedule",
            "preflight_code", "brute_force_check", "proof")
    return {k: exp[k] for k in keep if k in exp} | {
        "schedule": [{k: r[k] for k in ("id", "start", "finish")} for r in exp.get("reference_schedule", [])]}


def main():
    original = json.loads((PKG / "cpsat_reference_cases.json").read_text(encoding="utf-8"))
    rc06 = by_id(original["cases"], "RC06")
    cases = []

    # --- calendar policy -------------------------------------------------------
    exc = {k: v for k, v in rc06.items() if k != "expected"} | {"calendar_policy": EXCEPTION_POLICY}
    exc_exp = t4.solve_case(exc)
    assert exc_exp["optimal_makespan_minutes"] == rc06["expected"]["optimal_makespan_minutes"]
    assert summary(exc_exp)["schedule"] == summary(rc06["expected"])["schedule"], "RC06 must reproduce unchanged"
    cases.append({"case_id": "RC06", "status": "UNCHANGED - reclassified as authorised calendar exception",
                  "calendar_policy": EXCEPTION_POLICY,
                  "exception": {"id": "CAL-EXC-RC06", "scope": "FERRALLISTA activity N may work on the ferrallista "
                                "calendar (07:00-15:00) outside the project shift",
                                "authorisation": "HYPOTHETICAL test authorisation; engineering approval AP-X-CAL-01 PENDING"},
                  "expected": summary(exc_exp), "source": "cpsat_reference_cases.json#RC06 (not modified)"})
    dflt = copy.deepcopy({k: v for k, v in rc06.items() if k != "expected"})
    dflt.update({"case_id": "RC06-D", "calendar_policy": DEFAULT_POLICY,
                 "title": "RC06 inputs under the default policy: project AND activity AND resource calendars",
                 "notes": "N (150 min) cannot use 07:00-08:00 or 15:00-16:00; after P ends Mon 13:00 only 120 min "
                          "remain to 15:00, so N moves to Tue 08:00-10:30. Makespan is still set by M."})
    cases.append(dflt | {"expected": summary(t4.solve_case(dflt))})

    # --- inspection pass events ------------------------------------------------
    base = t4.case("RC12", 4, "", [t4.act("R", 57, {"CREW": 1}),
                                   t4.act("I", 30, {"INSPECTOR": 1}, kind="inspection"),
                                   t4.act("P", 43, {"CREW_C": 1}, allowed_hours=[["08:00", "14:00"]])],
                   {"CREW": t4.CREW(1), "CREW_C": t4.CREW(1), "INSPECTOR": t4.CREW(1, calendar=t4.INSP_CAL)},
                   [t4.dep("R", "I"), t4.dep("I", "P")])
    base["calendar_policy"] = DEFAULT_POLICY
    scheduled = summary(t4.solve_case(base))
    events = {
        "RC12a": ("hypothetical_pass", None, "OPTIMAL", "Pass at inspection finish; P follows immediately."),
        "RC12b": ("missing", None, "CONDITIONAL", "Projected dates equal RC12a but P is flagged conditional and not releasable."),
        "RC12c": ("failed", None, "BLOCKED", "P and every successor are blocked (INSPECTION_FAILED); R and I keep their dates."),
        "RC12d": ("recorded_pass", "2027-01-11T11:40", "OPTIMAL", "Recorded pass after inspection finish is a fixed not-before on P."),
    }
    for cid, (status, at, solver_status, note) in events.items():
        c = copy.deepcopy(base)
        c.update({"case_id": cid, "title": f"Inspection pass event: {status}",
                  "inspection_pass_events": [{"event_id": "EV-I", "inspection_activity": "I", "status": status,
                                              **({"at": at} if at else {}), "gates": ["P"]}]})
        if at:
            c["activities"][2]["not_before"] = at
            exp = summary(t4.solve_case(c))
        else:
            exp = copy.deepcopy(scheduled)
        if status == "failed":
            exp = {"expected_status": "BLOCKED", "preflight_code": "INSPECTION_FAILED",
                   "schedule": [r for r in scheduled["schedule"] if r["id"] != "P"], "blocked_activities": ["P"]}
        elif status == "missing":
            exp = exp | {"expected_status": "CONDITIONAL", "conditional_activities": ["P"]}
        exp["note"] = note
        exp["required_solver_status"] = solver_status
        cases.append(c | {"expected": exp})
    invalid = copy.deepcopy(base)
    invalid.update({"case_id": "RC12e", "title": "Recorded pass timestamp before inspection finish",
                    "inspection_pass_events": [{"event_id": "EV-I", "inspection_activity": "I",
                                                "status": "recorded_pass", "at": "2027-01-11T09:30", "gates": ["P"]}]})
    cases.append(invalid | {"expected": {"expected_status": "MODEL_INVALID", "preflight_code": "EVENT_BEFORE_ACTIVITY_FINISH",
                                         "note": "A pass cannot be recorded before the inspection can finish (10:30 at the earliest)."}})

    # --- strength release: fixed timestamp vs future activity-dependent test ----
    chain = t4.case("RC13", 9, "", [t4.act("POUR", 57, {"CREW_C": 1}, allowed_hours=[["08:00", "14:00"]]),
                                    t4.act("RELEASE", 4320, kind="elapsed_hold"),
                                    t4.act("STRIP", 57, {"CREW_F": 1})],
                    {"CREW_C": t4.CREW(1), "CREW_F": t4.CREW(1)}, [t4.dep("POUR", "RELEASE"), t4.dep("RELEASE", "STRIP")])
    chain["calendar_policy"] = DEFAULT_POLICY
    a = copy.deepcopy(chain)
    a["case_id"], a["title"] = "RC13a", "Timestamped fixed strength pass after the elapsed minimum"
    a["strength_events"] = [{"event_id": "EV-S", "kind": "fixed_timestamp", "status": "recorded_pass",
                             "at": "2027-01-15T10:30", "release_activity": "RELEASE"}]
    a["activities"][2]["not_before"] = "2027-01-15T10:30"
    exp_a = summary(t4.solve_case(a))
    exp_a["note"] = ("Release finish = max(pour finish + 72 h, recorded timestamp) = Fri 10:30. The timestamp is a fixed "
                     "absolute bound; it does not move with the pour (Agent 1 N2 semantics).")
    cases.append(a | {"expected": exp_a})
    b = copy.deepcopy(chain)
    b.update({"case_id": "RC13b", "title": "Future activity-dependent strength test (planned, not recorded)",
              "strength_events": [{"event_id": "EV-T", "kind": "activity_dependent_test", "status": "planned",
                                   "test_age_hours_after_pour": 96, "release_activity": "RELEASE"}]})
    b["activities"][1]["duration_minutes"] = 96 * 60
    exp_b = summary(t4.solve_case(b))
    exp_b.update({"expected_status": "CONDITIONAL", "required_solver_status": "CONDITIONAL (projection only)",
                  "note": "Projection uses max(72 h minimum, 96 h test age) measured from the pour finish, so it moves "
                          "with the pour. It must never be reported as OPTIMAL or releasable and must not be converted "
                          "into a fixed timestamp."})
    cases.append(b | {"expected": exp_b})

    # --- holiday sensitivity of the larger benchmark (separate folder) -------------
    out = PKG / "controlled_resource_demo_holiday_sensitivity"
    out.mkdir(exist_ok=True)
    runner = (
        "import sys, json; from pathlib import Path; "
        f"sys.path.insert(0, r'{PKG / 'controlled_resource_demo' / 'scripts'}'); "
        "import build_controlled_resource_demo as d; "
        f"d.DEMO = Path(r'{out}'); d.DATE_EXCEPTIONS = ['2027-03-01']; d.main()")
    env = dict(os.environ, PYTHONHASHSEED="0")
    subprocess.run([sys.executable, "-B", "-c", runner], check=True, env=env, cwd=REPO, stdout=subprocess.DEVNULL)
    fx = json.loads((out / "fixture_inputs.json").read_text(encoding="utf-8"))
    fx["_meta"]["sensitivity"] = ("DEMO-H1: identical to controlled_resource_demo/fixture_inputs.json except that "
                                  "2027-03-01 is a date exception on every calendar. Sensitivity only; the 40,445-minute "
                                  "benchmark is unchanged.")
    (out / "fixture_inputs.json").write_text(json.dumps(fx, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    h = json.loads((out / "expected_results.json").read_text(encoding="utf-8"))
    cases.append({"case_id": "DEMO-H1", "title": "Larger benchmark with 2027-03-01 non-working (sensitivity)",
                  "inputs": "controlled_resource_demo_holiday_sensitivity/fixture_inputs.json",
                  "builder": "controlled_resource_demo/scripts/build_controlled_resource_demo.py (unchanged), "
                             "DATE_EXCEPTIONS=['2027-03-01'], PYTHONHASHSEED=0",
                  "expected": {"expected_status": "OPTIMAL" if h["lower_bound"]["gap_minutes"] == 0 else "FEASIBLE",
                               "optimal_makespan_minutes": h["capacity_feasible"]["makespan_minutes"],
                               "completion_local": h["capacity_feasible"]["completion_local"],
                               "lower_bound_minutes": h["lower_bound"]["makespan_minutes"],
                               "cpm_completion_local": h["cpm"]["completion_local"],
                               "direct_reference_cost_eur": h["direct_reference_cost_eur"],
                               "independent_checks_passed": h["capacity_feasible"]["independent_checks_passed"]}})

    doc = {"_meta": {"task": "Stage 5.4B Task 7 addendum to cpsat_reference_cases.json (22 cases, unchanged)",
                     "default_calendar_policy": DEFAULT_POLICY,
                     "generator": "scripts/build_task7_cases.py", "status": "HYPOTHETICAL software test inputs"},
           "cases": cases}
    (PKG / "task7_reference_cases.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for c in cases:
        e = c["expected"]
        print(c["case_id"], e.get("expected_status"), e.get("optimal_makespan_minutes"), e.get("completion_local"),
              [(r["id"], r["start"][5:16], r["finish"][11:16]) for r in e.get("schedule", [])][:5])


if __name__ == "__main__":
    main()
