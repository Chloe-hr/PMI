"""Build independent resource-constrained reference cases for the Stage 5.4B CP-SAT scheduler.

Independent of pmi_core. Every expected result is produced by an exhaustive reference
solver written here, not by CP-SAT:

* Method A (all cases with <= 9 schedulable activities): serial schedule generation over
  EVERY precedence-feasible activity list. This enumerates every active schedule; for a
  regular objective (makespan) with time-varying capacities, activity windows, elapsed
  lags and start-to-finish reservations, an optimal schedule exists among active ones.
* Method B (small non-split cases): brute-force time-indexed enumeration of every start
  tick with finish <= bound. With bound = optimum - 1 tick it must find no schedule
  (proves the lower bound); with bound = optimum it must find at least one.
* The controlled-fixture regression (21 activities) is proven by CPM lower bound equality:
  the precedence/calendar-only optimum is reproduced by a resource-feasible schedule.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from fractions import Fraction
from itertools import product
import csv
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(HERE))
import independent_cpm as ind  # noqa: E402

ZONE = "Europe/Madrid"
WEEKDAYS = [{"weekday": d, "start": "08:00", "end": "16:00"} for d in range(1, 6)]
BASE_CAL = {"timezone": ZONE, "working_windows": WEEKDAYS, "date_exceptions": []}


class Blocked(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


# --------------------------------------------------------------------------- calendars
def epoch_min(local_iso, zone):
    return int(datetime.fromisoformat(local_iso).replace(tzinfo=zone).timestamp() // 60)


def calendar_mask(cal, anchor, n_ticks, tick, zone, allowed=None):
    """Tick i is available iff the whole interval [i, i+1) lies inside a window."""
    mask = bytearray(n_ticks)
    first = datetime.fromtimestamp(anchor * 60, zone).date()
    if cal == "continuous":
        return bytearray(b"\x01" * n_ticks)
    overrides = dict(cal.get("date_overrides", {}))
    for d in cal.get("date_exceptions", []):
        overrides[d] = []
    for k in range(n_ticks * tick // 1440 + 2):
        day = first + timedelta(days=k)
        pattern = overrides.get(day.isoformat())
        if pattern is None:
            pattern = [w for w in cal["working_windows"] if w["weekday"] == day.isoweekday()]
        for w in pattern:
            spans = [(w["start"], w["end"])]
            if allowed is not None:
                spans = [(max(w["start"], a), min(w["end"], b)) for a, b in allowed]
            for a, b in spans:
                if a >= b:
                    continue
                lo = epoch_min(f"{day.isoformat()}T{a}", zone) - anchor
                hi = epoch_min(f"{day.isoformat()}T{b}", zone) - anchor
                if lo % tick or hi % tick:
                    raise Blocked("MODEL_INVALID", "TICK_MISALIGNED",
                                  f"Window {a}-{b} is not aligned to a {tick}-minute tick.")
                for i in range(max(0, lo // tick), min(n_ticks, hi // tick)):
                    mask[i] = 1
    return mask


def ceil_ticks(minutes, tick):
    return -(-Fraction(str(minutes)) // tick)


# --------------------------------------------------------------------------- model
def prepare(case):
    tick = case["tick_minutes"]
    if 60 % tick:
        raise Blocked("MODEL_INVALID", "TICK_MISALIGNED", "Tick must divide 60.")
    zone = ZoneInfo(case["timezone"])
    anchor = epoch_min(case["project_start"], zone)
    end = epoch_min(case["horizon_end"], zone)
    n = (end - anchor) // tick
    resources = case["resources"]
    acts = {a["id"]: a for a in case["activities"]}
    # ---- preflight (before any search) ----
    for a in acts.values():
        if a["kind"] == "elapsed_hold" and a.get("resources"):
            raise Blocked("MODEL_INVALID", "HOLD_WITH_RESOURCES", a["id"])
        for r, q in a.get("resources", {}).items():
            if r not in resources or resources[r].get("capacity") is None:
                raise Blocked("MODEL_INVALID", "MISSING_INPUT", f"No capacity declared for {r} ({a['id']}).")
            cap = resources[r]["capacity"]
            if type(q) is not int or q <= 0:
                raise Blocked("MODEL_INVALID", "INVALID_DEMAND", f"{a['id']} demand for {r}.")
            if cap < q:
                raise Blocked("INFEASIBLE", "IMPOSSIBLE_CREW",
                              f"{a['id']} needs {q} {r}; capacity is {cap}.")
    for rv in case.get("reservations", []):
        if resources.get(rv["resource"], {}).get("capacity") is None:
            raise Blocked("MODEL_INVALID", "MISSING_INPUT", f"No capacity for {rv['resource']}.")
        if resources[rv["resource"]]["capacity"] < rv["demand"]:
            raise Blocked("INFEASIBLE", "IMPOSSIBLE_RESERVATION", rv["id"])
    preds = defaultdict(list)
    for d in case["dependencies"]:
        assert d["relation"] == "FS" and d["lag_basis"] == "elapsed"
        preds[d["successor"]].append((d["predecessor"], int(ceil_ticks(d["lag_minutes"], tick))))
    # resource capacity arrays (0 outside resource calendar)
    project_cal = case["project_calendar"]
    cap, cal_of = {}, {}
    for r, spec in resources.items():
        c = spec.get("calendar", "project")
        mask = calendar_mask(project_cal if c == "project" else c, anchor, n, tick, zone)
        cal_of[r] = mask
        cap[r] = [spec["capacity"] if m else 0 for m in mask]
    model = {"tick": tick, "zone": zone, "anchor": anchor, "n": n, "acts": acts, "preds": preds,
             "cap": cap, "res_by_act": {}, "avail": {}, "dur": {}, "split": {}, "not_before": {}}
    pmask = calendar_mask(project_cal, anchor, n, tick, zone)
    for k, a in acts.items():
        model["dur"][k] = int(ceil_ticks(a["duration_minutes"], tick))
        if model["dur"][k] <= 0:
            raise Blocked("MODEL_INVALID", "ZERO_DURATION", k)
        model["res_by_act"][k] = a.get("resources", {})
        nb = a.get("not_before")
        model["not_before"][k] = 0 if not nb else -(-(epoch_min(nb, zone) - anchor) // tick)
        if a["kind"] == "elapsed_hold":
            continue
        renew = [r for r in a.get("resources", {}) if resources[r].get("kind", "renewable") != "reservation"]
        base = [all(cal_of[r][i] for r in renew) for i in range(n)] if renew else list(pmask)
        if a.get("allowed_hours"):
            hours = a["allowed_hours"]
            w = bytearray(n)
            for i in range(n):
                loc = datetime.fromtimestamp((anchor + i * tick) * 60, zone)
                hm = f"{loc.hour:02d}:{loc.minute:02d}"
                loc2 = datetime.fromtimestamp((anchor + (i + 1) * tick - 1) * 60, zone)
                hm2 = f"{loc2.hour:02d}:{loc2.minute:02d}"
                w[i] = any(lo <= hm and hm2 < hi for lo, hi in hours)
            base = [b and w[i] for i, b in enumerate(base)]
        model["avail"][k] = bytearray(1 if b else 0 for b in base)
        if a.get("interruption", "non_interruptible") == "split_allowed":
            sp = a["split"]
            model["split"][k] = (int(ceil_ticks(sp["min_segment_minutes"], tick)), sp["max_segments"])
        elif not any(sum(model["avail"][k][i:i + model["dur"][k]]) == model["dur"][k]
                     for i in range(0, n - model["dur"][k] + 1)):
            raise Blocked("INFEASIBLE", "NO_FIT",
                          f"{k}: {a['duration_minutes']} min exceeds every available uninterrupted window.")
    model["reservations"] = case.get("reservations", [])
    # A finish at or before latest_finish: floor to the tick grid.
    model["deadlines"] = {d["activity"]: (epoch_min(d["latest_finish"], zone) - anchor) // tick
                          for d in case.get("deadlines", [])}
    for rv in model["reservations"]:
        reach, stack = set(), [rv["to_activity"]]
        while stack:
            x = stack.pop()
            for p, _ in preds[x]:
                if p not in reach:
                    reach.add(p); stack.append(p)
        assert rv["from_activity"] in reach, "reservation end must follow its start"
    return model


def segments_for(model, k, t):
    """Return segments (start, end) in ticks or None if the activity cannot start at t."""
    d, av, n = model["dur"][k], model["avail"][k], model["n"]
    if k not in model["split"]:
        if t + d > n or sum(av[t:t + d]) != d:
            return None
        return [(t, t + d)]
    mn, mx = model["split"][k]
    if t >= n or not av[t]:
        return None
    segs, left, i = [], d, t
    while left:
        if i >= n:
            return None
        if av[i]:
            if segs and segs[-1][1] == i:
                segs[-1] = (segs[-1][0], i + 1)
            else:
                segs.append((i, i + 1))
            left -= 1
        i += 1
    if len(segs) > mx or any(b - a < mn for a, b in segs):
        return None
    return segs


def fits(model, usage, k, segs):
    for r, q in model["res_by_act"][k].items():
        if r in model["res_kind_reservation"]:
            continue
        u, c = usage[r], model["cap"][r]
        for a, b in segs:
            for i in range(a, b):
                if u[i] + q > c[i]:
                    return False
    return True


def apply(model, usage, k, segs, sign):
    for r, q in model["res_by_act"][k].items():
        if r in model["res_kind_reservation"]:
            continue
        u = usage[r]
        for a, b in segs:
            for i in range(a, b):
                u[i] += sign * q


def earliest_bound(model, k, finish):
    return max([model["not_before"][k]] + [finish[p] + lag for p, lag in model["preds"][k]])


# --------------------------------------------------------------------------- Method A
def enumerate_active(model, limit=2_000_000):
    acts, preds, n = model["acts"], model["preds"], model["n"]
    usage = {r: [0] * n for r in model["cap"]}
    rv_from = defaultdict(list)
    rv_to = defaultdict(list)
    for rv in model["reservations"]:
        rv_from[rv["from_activity"]].append(rv)
        rv_to[rv["to_activity"]].append(rv)
    start, finish, segs_of, results = {}, {}, {}, {}
    nodes = [0]

    def place(k):
        lo = earliest_bound(model, k, finish)
        if acts[k]["kind"] == "elapsed_hold":
            return lo, [(lo, lo + model["dur"][k])]
        for t in range(lo, n):
            segs = segments_for(model, k, t)
            if segs is None or not fits(model, usage, k, segs):
                continue
            ok = True
            for rv in rv_from[k]:  # reservation opens at t, end unknown -> check [t, n)
                u, c = usage[rv["resource"]], model["cap"][rv["resource"]]
                if any(u[i] + rv["demand"] > c[i] for i in range(t, n)):
                    ok = False
                    break
            if ok:
                return t, segs
        return None

    def dfs(done):
        nodes[0] += 1
        if len(done) == len(acts):
            key = tuple(sorted((k, tuple(segs_of[k])) for k in acts))
            results[key] = max(finish.values())
            return
        for k in sorted(acts):
            if k in done or any(p not in done for p, _ in preds[k]):
                continue
            got = place(k)
            if got is None:
                continue
            t, segs = got
            start[k], finish[k], segs_of[k] = t, segs[-1][1], segs
            apply(model, usage, k, segs, +1)
            for rv in rv_from[k]:
                u = usage[rv["resource"]]
                for i in range(t, n):
                    u[i] += rv["demand"]
            for rv in rv_to[k]:
                u = usage[rv["resource"]]
                for i in range(finish[k], n):
                    u[i] -= rv["demand"]
            done.add(k)
            dfs(done)
            done.discard(k)
            for rv in rv_to[k]:
                u = usage[rv["resource"]]
                for i in range(finish[k], n):
                    u[i] += rv["demand"]
            for rv in rv_from[k]:
                u = usage[rv["resource"]]
                for i in range(t, n):
                    u[i] -= rv["demand"]
            apply(model, usage, k, segs, -1)
            del start[k], finish[k], segs_of[k]

    dfs(set())
    return results, nodes[0]


# --------------------------------------------------------------------------- Method B
def brute_force_count(model, bound, cap_count=1, max_space=3_000_000):
    """Count schedules (up to cap_count) whose makespan <= bound ticks, by trying every start tick."""
    acts, preds, n = model["acts"], model["preds"], model["n"]
    order, seen = [], set()
    while len(order) < len(acts):
        for k in sorted(acts):
            if k not in seen and all(p in seen for p, _ in preds[k]):
                order.append(k); seen.add(k)
    succs = defaultdict(list)
    for k in acts:
        for p, lag in preds[k]:
            succs[p].append((k, lag))
    tail = {}
    for k in reversed(order):  # longest elapsed path from k's start to the project end (lower bound)
        tail[k] = model["dur"][k] + max([lag + tail[s] for s, lag in succs[k]] + [0])
    head = {}
    for k in order:
        head[k] = max([model["not_before"][k]] + [head[p] + model["dur"][p] + lag for p, lag in preds[k]])
    space = 1
    for k in order:
        if acts[k]["kind"] != "elapsed_hold":
            space *= max(1, sum(1 for t in range(head[k], max(head[k], bound - tail[k] + 1))
                                if segments_for(model, k, t)))
    if space > max_space:
        return None
    usage = {r: [0] * n for r in model["cap"]}
    start, finish, found = {}, {}, [0]

    def dfs(idx):
        if found[0] >= cap_count:
            return
        if idx == len(order):
            # reservations checked exactly on the complete assignment
            ru = defaultdict(lambda: [0] * n)
            for rv in model["reservations"]:
                for i in range(start[rv["from_activity"]], finish[rv["to_activity"]]):
                    ru[rv["resource"]][i] += rv["demand"]
                    if ru[rv["resource"]][i] > model["cap"][rv["resource"]][i]:
                        return
            found[0] += 1
            return
        k = order[idx]
        lo = earliest_bound(model, k, finish)
        d = model["dur"][k]
        if acts[k]["kind"] == "elapsed_hold":
            cands = [lo] if lo + tail[k] <= bound else []   # earliest start is w.l.o.g. for a hold
        else:
            cands = range(lo, bound - tail[k] + 1)
        for t in cands:
            segs = [(t, t + d)] if acts[k]["kind"] == "elapsed_hold" else segments_for(model, k, t)
            if segs is None or segs[-1][1] > bound or not fits(model, usage, k, segs):
                continue
            start[k], finish[k] = t, segs[-1][1]
            apply(model, usage, k, segs, +1)
            dfs(idx + 1)
            apply(model, usage, k, segs, -1)
            del start[k], finish[k]

    dfs(0)
    return found[0]


# --------------------------------------------------------------------------- reporting
def stamp(model, ticks):
    return datetime.fromtimestamp((model["anchor"] + ticks * model["tick"]) * 60, model["zone"]).isoformat(
        timespec="minutes")


def describe(model, key):
    segs = dict(key)
    tick = model["tick"]
    rows, occ = [], []
    for k in sorted(segs, key=lambda x: (segs[x][0][0], x)):
        a = model["acts"][k]
        s = segs[k]
        rows.append({"id": k, "kind": a["kind"], "start": stamp(model, s[0][0]), "finish": stamp(model, s[-1][1]),
                     "segments": [[stamp(model, x), stamp(model, y)] for x, y in s],
                     "raw_minutes": a["duration_minutes"], "scheduled_minutes": model["dur"][k] * tick})
        for r, q in a.get("resources", {}).items():
            if r in model["res_kind_reservation"]:
                continue
            for x, y in s:
                occ.append({"resource": r, "holder": k, "units": q, "start": stamp(model, x), "finish": stamp(model, y)})
    for rv in model["reservations"]:
        occ.append({"resource": rv["resource"], "holder": rv["id"], "units": rv["demand"],
                    "start": stamp(model, segs[rv["from_activity"]][0][0]),
                    "finish": stamp(model, segs[rv["to_activity"]][-1][1]),
                    "continuous_from": f"{rv['from_activity']}.start", "continuous_to": f"{rv['to_activity']}.finish"})
    # peak usage per resource
    n = model["n"]
    peak = {}
    for r in model["cap"]:
        u = [0] * n
        for k, s in segs.items():
            q = model["acts"][k].get("resources", {}).get(r)
            if q and r not in model["res_kind_reservation"]:
                for x, y in s:
                    for i in range(x, y):
                        u[i] += q
        for rv in model["reservations"]:
            if rv["resource"] == r:
                for i in range(segs[rv["from_activity"]][0][0], segs[rv["to_activity"]][-1][1]):
                    u[i] += rv["demand"]
        over = [i for i in range(n) if u[i] > model["cap"][r][i]]
        assert not over, f"reference schedule violates {r}"
        peak[r] = {"peak_units": max(u), "declared_capacity": max(model["cap"][r])}
    return rows, occ, peak


def solve_case(case, brute=True):
    exp = {"tick_minutes": case["tick_minutes"]}
    try:
        model = prepare(case)
    except Blocked as b:
        exp.update({"expected_status": b.status, "preflight_code": b.code, "diagnostic": str(b),
                    "solver_invocation": "must not be invoked" if b.status == "MODEL_INVALID"
                    else "preflight may reject; if invoked CP-SAT must return INFEASIBLE",
                    "proof": "Preflight rule: the declared input cannot satisfy the stated constraint.",
                    "optimal_makespan_minutes": None})
        return exp
    model["res_kind_reservation"] = {r for r, s in case["resources"].items() if s.get("kind") == "reservation"}
    tick = model["tick"]
    results, nodes = enumerate_active(model)
    exp["active_schedules_enumerated"] = len(results)
    exp["search_nodes"] = nodes
    if not results:
        exp.update({"expected_status": "INFEASIBLE", "preflight_code": "HORIZON_EXHAUSTED",
                    "diagnostic": "No active schedule exists inside the horizon.",
                    "proof": "Method A found no placement for at least one activity in any list.",
                    "optimal_makespan_minutes": None})
        return exp

    def meets(key):
        segs = dict(key)
        return all(segs[a][-1][1] <= lim for a, lim in model["deadlines"].items() if a != "PROJECT") and \
            ("PROJECT" not in model["deadlines"] or max(s[-1][1] for s in segs.values()) <= model["deadlines"]["PROJECT"])

    best_all = min(results.values())
    ok = {k: v for k, v in results.items() if meets(k)}
    if not ok:
        exp.update({"expected_status": "INFEASIBLE", "preflight_code": "INFEASIBLE_DEADLINE",
                    "diagnostic": f"Best makespan without deadlines is {best_all * tick} min ({stamp(model, best_all)}).",
                    "proof": "Method A: no active schedule meets the deadlines; left shifts never delay a finish, "
                             "so no feasible schedule meets them.",
                    "optimal_makespan_minutes": None,
                    "unconstrained_optimal_makespan_minutes": best_all * tick})
        found = brute_force_count(model, best_all - 1) if brute else None
        exp["brute_force_check"] = ({"skipped": "search space above limit"} if found is None else
                                    {"no_schedule_with_makespan_minutes_at_most": best_all * tick - tick,
                                     "schedules_found_below_optimum": found})
        return exp
    best = min(ok.values())
    optimal = sorted(k for k, v in ok.items() if v == best)
    worst = max(ok, key=lambda k: (ok[k], k))
    rows, occ, peak = describe(model, optimal[0])
    exp.update({
        "expected_status": "OPTIMAL", "optimal_makespan_minutes": best * tick,
        "completion_local": stamp(model, best),
        "distinct_optimal_active_schedules": len(optimal), "unique_optimal_schedule": len(optimal) == 1,
        "reference_schedule": rows, "resource_occupancy": occ, "peak_usage": peak,
        "feasible_not_optimal_example": None if ok[worst] == best else {
            "status": "FEASIBLE (not optimal)", "makespan_minutes": ok[worst] * tick,
            "completion_local": stamp(model, ok[worst]),
            "schedule": describe(model, worst)[0]},
        "proof": "Method A: exhaustive serial SGS over all precedence-feasible activity lists.",
    })
    lower = brute_force_count(model, best - 1) if brute and not model["split"] else None
    if lower is None:
        exp["brute_force_check"] = {"skipped": "split activity or time-indexed search space above 3e6 start "
                                               "combinations; Method A alone proves optimality"}
    else:
        hit = brute_force_count(model, best)
        assert lower == 0 and hit != 0, (case["case_id"], lower, hit)
        exp["brute_force_check"] = {"no_schedule_with_makespan_minutes_at_most": (best - 1) * tick,
                                    "schedules_found_below_optimum": lower,
                                    "optimum_attained": True if hit else "by Method A (attainment search above limit)"}
        exp["proof"] += " Method B: time-indexed brute force finds no schedule one tick shorter."
    return exp


# --------------------------------------------------------------------------- cases
def act(i, minutes, res=None, kind="productive", **kw):
    return {"id": i, "kind": kind, "duration_minutes": minutes, "resources": res or {}, **kw}


def dep(a, b, lag=0):
    return {"predecessor": a, "successor": b, "relation": "FS", "lag_minutes": lag, "lag_basis": "elapsed"}


def case(cid, category, title, activities, resources, deps=(), start="2027-01-11T08:00",
         horizon="2027-01-22T16:00", tick=5, **kw):
    return {"case_id": cid, "category": category, "title": title, "tick_minutes": tick, "timezone": ZONE,
            "project_start": start, "horizon_end": horizon, "project_calendar": BASE_CAL,
            "resources": resources, "activities": activities, "dependencies": list(deps),
            "objective": "minimize_makespan", **kw}


CREW = lambda c, **kw: {"capacity": c, "kind": "renewable", "calendar": "project", **kw}
INSP_CAL = {"working_windows": [{"weekday": d, "start": "10:00", "end": "12:00"} for d in range(1, 6)]}
SUPPLY_CAL = {"working_windows": [{"weekday": d, "start": "08:00", "end": "14:00"} for d in range(1, 6)]}
CRANE_CAL = {"working_windows": [{"weekday": d, "start": "08:00", "end": "12:00"} for d in (2, 4)]}
FERR_CAL = {"working_windows": [{"weekday": d, "start": "07:00", "end": "15:00"} for d in range(1, 6)]}

A3 = [act("A", 228, {"CREW_F": 1}), act("B", 196, {"CREW_F": 1}), act("C", 167, {"CREW_F": 1})]


def element(p, form, pour, strip, cure=1440, supply=None):
    return [act(f"{p}-FORM", form, {"CREW_F": 1}),
            act(f"{p}-POUR", pour, {"CREW_C": 1, **({"SUPPLY": supply} if supply else {})},
                allowed_hours=[["08:00", "14:00"]]),
            act(f"{p}-CURE", cure, kind="elapsed_hold"),
            act(f"{p}-STRIP", strip, {"CREW_F": 1})]


def element_deps(p):
    return [dep(f"{p}-FORM", f"{p}-POUR"), dep(f"{p}-POUR", f"{p}-CURE"), dep(f"{p}-CURE", f"{p}-STRIP")]


CASES = [
    case("RC01", 1, "Three parallel activities compete for one formwork crew across a shift boundary",
         A3, {"CREW_F": CREW(1)},
         notes="Sum 600 scheduled min > 480 min shift. Non-interruptible. The shortest activity must "
               "go to day 2. Longest-first and shortest-first heuristics differ."),
    case("RC02", 2, "Shared crane capacity with a dependent follow-on task",
         [act("L1", 88, {"CREW_R1": 1, "CRANE": 1}), act("L2", 117, {"CREW_R2": 1, "CRANE": 1}),
          act("L3", 58, {"CREW_R1": 1})],
         {"CREW_R1": CREW(1), "CREW_R2": CREW(1), "CRANE": CREW(1)}, [dep("L1", "L3")],
         notes="Crane lower bound 90+120 = 210 min is attained only if L1 lifts first."),
    case("RC03", 3, "Simultaneous multi-trade demand on a shared labourer pool",
         [act("X", 118, {"ENCOFRADOR": 2, "PEON": 1}), act("Y", 88, {"PEON": 2, "OFICIAL": 1}),
          act("Z", 57, {"FERRALLISTA": 2, "PEON": 1})],
         {"ENCOFRADOR": CREW(2), "PEON": CREW(3), "OFICIAL": CREW(1), "FERRALLISTA": CREW(2)},
         notes="Any two of X, Y, Z may overlap (PEON 3) but not all three (PEON 4 > 3). All trade demands "
               "of one activity are held simultaneously for its whole duration."),
    case("RC04", 4, "Two pre-pour inspections share one inspector available 10:00-12:00",
         [act("R1", 117, {"CREW_A": 1}), act("R2", 108, {"CREW_B": 1}),
          act("I1", 30, {"INSPECTOR": 1}, kind="inspection"), act("I2", 30, {"INSPECTOR": 1}, kind="inspection"),
          act("P1", 43, {"CREW_C": 1}, allowed_hours=[["08:00", "14:00"]]),
          act("P2", 43, {"CREW_C": 1}, allowed_hours=[["08:00", "14:00"]])],
         {"CREW_A": CREW(1), "CREW_B": CREW(1), "CREW_C": CREW(1),
          "INSPECTOR": CREW(1, calendar=INSP_CAL)},
         [dep("R1", "I1"), dep("I1", "P1"), dep("R2", "I2"), dep("I2", "P2")],
         notes="Inspections are working-time activities on the inspector's own calendar. They cannot "
               "start before 10:00 although the rebar finishes earlier."),
    case("RC05a", 5, "Reusable formwork: one set reserved from FORM start to STRIP finish",
         element("E1", 57, 28, 28) + element("E2", 57, 28, 28),
         {"CREW_F": CREW(1), "CREW_C": CREW(1), "FORMWORK_SET": {"capacity": 1, "kind": "reservation",
                                                                  "calendar": "continuous"}},
         element_deps("E1") + element_deps("E2"),
         reservations=[{"id": "SET-E1", "resource": "FORMWORK_SET", "demand": 1, "from_activity": "E1-FORM",
                        "to_activity": "E1-STRIP"},
                       {"id": "SET-E2", "resource": "FORMWORK_SET", "demand": 1, "from_activity": "E2-FORM",
                        "to_activity": "E2-STRIP"}],
         notes="The set stays occupied through curing, nights and weekends; it is released only when "
               "stripping finishes. One set forces E2-FORM after E1-STRIP."),
    None,  # RC05b filled below (two sets)
    case("RC06", 6, "Resource-specific calendars: crane hire Tue/Thu mornings, ferrallista 07:00-15:00",
         [act("P", 297, {"CREW_F": 1}), act("L", 148, {"CREW_F": 1, "CRANE": 1}), act("M", 197, {"CRANE": 1}),
          act("N", 148, {"FERRALLISTA": 1})],
         {"CREW_F": CREW(1), "CRANE": CREW(1, calendar=CRANE_CAL), "FERRALLISTA": CREW(1, calendar=FERR_CAL)},
         [dep("P", "L"), dep("L", "M"), dep("P", "N")],
         notes="An activity may only run when every resource it uses is on calendar. N works 07:00 on "
               "Tuesday, before the project shift starts. M cannot use the 90 min left on Tuesday's "
               "crane window and waits for Thursday."),
    case("RC07a", 7, "Impossible project deadline (RC01 by Monday 16:00)", A3, {"CREW_F": CREW(1)},
         deadlines=[{"activity": "PROJECT", "latest_finish": "2027-01-11T16:00"}]),
    case("RC07b", 7, "Tight but feasible deadline equal to the RC01 optimum", A3, {"CREW_F": CREW(1)},
         deadlines=[{"activity": "PROJECT", "latest_finish": "2027-01-12T10:50"}]),
    case("RC07c", 7, "Activity deadline forces a unique order (B by Monday 12:00)", A3, {"CREW_F": CREW(1)},
         deadlines=[{"activity": "B", "latest_finish": "2027-01-11T12:00"}]),
    case("RC08a", 8, "Missing capacity for a demanded trade", [act("A", 60, {"FERRALLISTA": 1})], {}),
    case("RC08b", 8, "Zero capacity for a demanded trade", [act("A", 60, {"FERRALLISTA": 1})],
         {"FERRALLISTA": CREW(0)}),
    case("RC08c", 8, "Demand exceeds capacity in the only mode", [act("A", 60, {"FERRALLISTA": 2})],
         {"FERRALLISTA": CREW(1)}),
    case("RC08d", 8, "Capacity declared but resource never on calendar within the horizon",
         [act("A", 30, {"INSPECTOR": 1}, kind="inspection")],
         {"INSPECTOR": CREW(1, calendar={"working_windows": [], "note": "inspector unavailable"})},
         horizon="2027-01-15T16:00"),
    case("RC09", 9, "Elapsed curing overlaps productive work and crosses a weekend",
         element("E1", 118, 57, 88) + element("E2", 237, 57, 88),
         {"CREW_F": CREW(1), "CREW_C": CREW(1)}, element_deps("E1") + element_deps("E2"),
         start="2027-01-14T08:00", horizon="2027-01-22T16:00",
         notes="Curing reserves no crew; CREW_F forms E2 while E1 cures. Only one pour can fit before the "
               "Thursday 14:00 cut-off, so one strip lands on Monday."),
    case("RC10a", 10, "600 min activity, interruption authorized (max 2 segments, min 120 min)",
         [act("PREP", 240, {"CREW_F": 1}), act("S", 597, {"CREW_F": 1}, interruption="split_allowed",
                                                   split={"min_segment_minutes": 120, "max_segments": 2,
                                                          "authorization": "HYPOTHETICAL test authorization"})],
         {"CREW_F": CREW(1)}, [dep("PREP", "S")], start="2027-01-15T08:00", horizon="2027-01-22T16:00"),
    case("RC10b", 10, "Same 600 min activity without interruption authorization",
         [act("PREP", 240, {"CREW_F": 1}), act("S", 597, {"CREW_F": 1})],
         {"CREW_F": CREW(1)}, [dep("PREP", "S")], start="2027-01-15T08:00", horizon="2027-01-22T16:00"),
    case("RC10c", 10, "Authorized split rejected by minimum segment length (min 300 min)",
         [act("PREP", 240, {"CREW_F": 1}), act("S", 597, {"CREW_F": 1}, interruption="split_allowed",
                                                   split={"min_segment_minutes": 300, "max_segments": 2,
                                                          "authorization": "HYPOTHETICAL test authorization"})],
         {"CREW_F": CREW(1)}, [dep("PREP", "S")], start="2027-01-15T08:00", horizon="2027-01-22T16:00"),
    case("RC11a", 11, "Concrete supply 6 m3/h shared by two pours, delivery window 08:00-14:00",
         [act("P1", 90, {"CREW_C1": 1, "SUPPLY": 6}, not_before="2027-01-11T12:00",
              derivation="9.0 m3 / min(placement 10 m3/h, supply 6 m3/h) = 90 min"),
          act("P2", 45, {"CREW_C2": 1, "SUPPLY": 6}, not_before="2027-01-11T12:00",
              derivation="4.5 m3 / min(10, 6) m3/h = 45 min")],
         {"CREW_C1": CREW(1), "CREW_C2": CREW(1),
          "SUPPLY": {"capacity": 6, "unit": "m3/h", "kind": "renewable", "calendar": SUPPLY_CAL}},
         notes="Supply is a cumulative rate resource on its own delivery calendar. Both pours draw "
               "6 m3/h, so they are serial. Only 120 min of delivery remain after 12:00."),
    case("RC11b", 11, "Same pours with 12 m3/h supply (two trucks in parallel)",
         [act("P1", 90, {"CREW_C1": 1, "SUPPLY": 6}, not_before="2027-01-11T12:00"),
          act("P2", 45, {"CREW_C2": 1, "SUPPLY": 6}, not_before="2027-01-11T12:00")],
         {"CREW_C1": CREW(1), "CREW_C2": CREW(1),
          "SUPPLY": {"capacity": 12, "unit": "m3/h", "kind": "renewable", "calendar": SUPPLY_CAL}}),
]
CASES[5] = {**json.loads(json.dumps(CASES[4])), "case_id": "RC05b",
            "title": "Reusable formwork: two sets allow overlap during curing"}
CASES[5]["resources"]["FORMWORK_SET"]["capacity"] = 2
CASES[5]["notes"] = "Same as RC05a with two formwork sets."


def fixture_case(tick):
    """Encode the controlled Stage 5.4A fixture (21 activities) in the same case format."""
    h, prep, acts, edges_a, _ = ind.build_model(tick)
    edges = ind.final_edges(edges_a)
    caps = prep["resource_capacity_by_trade"]
    activities = []
    for k, a in sorted(acts.items()):
        kind = "elapsed_hold" if a["kind"] == "elapsed" else a["kind"]
        row = act(k, round(a["raw"], 6), a["res"], kind=kind)
        if a["pour"]:
            row["allowed_hours"] = [["08:00", "14:00"]]
        activities.append(row)
    return {"case_id": f"R0-{tick}", "category": 0,
            "title": f"Controlled Stage 5.4A fixture with resource constraints enforced ({tick}-min tick)",
            "tick_minutes": tick, "timezone": ZONE, "project_start": "2027-01-04T08:00",
            "horizon_end": "2027-03-01T16:00",
            "project_calendar": {"timezone": ZONE, "working_windows": WEEKDAYS,
                                 "date_exceptions": prep["calendar"]["date_exceptions"]},
            "resources": {r: CREW(c) for r, c in caps.items()},
            "activities": activities, "dependencies": [dep(a, b) for a, b in sorted(edges)],
            "objective": "minimize_makespan", "brute_force": False,
            "source": "research/implementation/stage5_3/scheduling_handover.json + "
                      "research/planning/stage5_4_preparation/controlled_scheduling_inputs.json",
            "notes": "Existing regression at 15 min; proposed default at 5 min."}


def solve_fixture(c):
    model = prepare(c)
    model["res_kind_reservation"] = set()
    # CPM lower bound: same placement with unlimited capacity, any topological list.
    order = []
    seen = set()
    while len(order) < len(model["acts"]):
        for k in sorted(model["acts"]):
            if k not in seen and all(p in seen for p, _ in model["preds"][k]):
                order.append(k); seen.add(k)

    def run(capacitated):
        usage = {r: [0] * model["n"] for r in model["cap"]}
        fin, segs_of = {}, {}
        for k in order:
            lo = earliest_bound(model, k, fin)
            if model["acts"][k]["kind"] == "elapsed_hold":
                segs = [(lo, lo + model["dur"][k])]
            else:
                t = lo
                while True:
                    segs = segments_for(model, k, t)
                    if segs and (not capacitated or fits(model, usage, k, segs)):
                        break
                    t += 1
                apply(model, usage, k, segs, +1)
            fin[k], segs_of[k] = segs[-1][1], segs
        return max(fin.values()), tuple(sorted((k, tuple(v)) for k, v in segs_of.items()))

    lb, _ = run(False)
    best, key = run(True)
    assert best == lb
    rows, occ, peak = describe(model, key)
    return {"tick_minutes": c["tick_minutes"], "expected_status": "OPTIMAL",
            "optimal_makespan_minutes": best * model["tick"], "completion_local": stamp(model, best),
            "unique_optimal_schedule": False, "distinct_optimal_active_schedules": "not enumerated",
            "reference_schedule": rows, "resource_occupancy": occ, "peak_usage": peak,
            "feasible_not_optimal_example": None,
            "proof": "Lower bound: precedence- and calendar-only earliest finish (resources relaxed). "
                     "A resource-feasible schedule attains it, so it is optimal. Matches the independently "
                     "verified Stage 5.4A CPM completion."}


GENERAL_ACCEPTANCE = [
    "Expected status: OPTIMAL cases must return OPTIMAL (FEASIBLE with the same objective is reported as "
    "'feasible, optimality not proven' and fails the case). INFEASIBLE cases must return INFEASIBLE or a "
    "preflight rejection with the stated code, never UNKNOWN or a relaxed schedule. MODEL_INVALID cases must "
    "be rejected before the solver is invoked.",
    "Objective: makespan in minutes from project_start equals optimal_makespan_minutes exactly.",
    "Schedule: dates may differ from reference_schedule only where unique_optimal_schedule is false. Any "
    "returned schedule must be validated independently against all constraints below.",
    "Durations: every productive or inspection activity occupies exactly ceil(duration_minutes / tick) ticks "
    "of working time; elapsed holds occupy exactly ceil(duration_minutes / tick) ticks of elapsed time.",
    "Calendars: every occupied tick lies inside the calendar of every resource the activity uses (or the "
    "project calendar when it uses none) and inside allowed_hours where declared.",
    "Capacity: at every tick, the sum of demands on each resource is at most its capacity on that tick "
    "(capacity is 0 outside the resource calendar). Reservations count from from_activity start to "
    "to_activity finish, continuously.",
    "Precedence: successor start >= predecessor finish + lag (FS, elapsed).",
    "Deadlines: every finish is at or before its latest_finish.",
    "Interruption: only split_allowed activities may have more than one segment, with at most max_segments "
    "segments each of at least min_segment_minutes; resources are held only during segments.",
]

CONVENTIONS = {
    "time_axis": "Integer ticks from project_start (local Europe/Madrid, +01:00 in the horizon). "
                 "Tick i covers [start + i*tick, start + (i+1)*tick).",
    "resolution": "5-minute tick is the proposed default for new cases; R0-15 retains the existing 15-minute "
                  "regression. Every calendar boundary is a multiple of the tick.",
    "rounding": "Durations and lags are rounded UP to whole ticks; raw minutes are kept in duration_minutes.",
    "activity_calendar": "Intersection of the calendars of all renewable resources the activity uses; the "
                         "project calendar when it uses none; then intersected with allowed_hours.",
    "elapsed_hold": "No resources, no calendar. Runs through nights, weekends and holidays.",
    "reservation": "kind=reservation resources are occupied continuously (calendar 'continuous') from "
                   "from_activity start to to_activity finish, including holds and non-working time.",
    "supply": "Concrete supply is a renewable rate resource (m3/h) on its own delivery calendar; each pour "
              "demands its drawn rate for its whole duration. Duration = volume / min(placement, supply rate).",
    "split": "split_allowed activities work every available tick of their calendar from their start until "
             "complete (no voluntary pause inside an available window); segment rules then accept or "
             "reject the start. A solver that additionally permits voluntary pauses may only match or "
             "improve the objective; none of these cases has contention that would benefit from it.",
    "statuses": {"OPTIMAL": "Feasible and proven optimal by the stated method.",
                 "FEASIBLE (not optimal)": "Satisfies every constraint but a better schedule exists.",
                 "INFEASIBLE": "Proven that no schedule satisfies the constraints.",
                 "MODEL_INVALID": "Input incomplete or inconsistent; reject before solving."},
}


def main():
    cases = CASES + [fixture_case(15), fixture_case(5)]
    out, rows = [], []
    for c in cases:
        exp = solve_fixture(c) if c["case_id"].startswith("R0") else solve_case(c)
        if exp["expected_status"] != "OPTIMAL":
            detail = f"; status {exp['expected_status']} with diagnostic {exp.get('preflight_code')}; no schedule returned"
        elif exp.get("unique_optimal_schedule"):
            detail = "; schedule is unique and must match reference_schedule exactly"
        else:
            detail = "; status and makespan must match; any constraint-valid optimal schedule is accepted"
        exp["acceptance_criteria"] = "general_acceptance_criteria apply" + detail
        out.append({**c, "expected": exp})
        bf = exp.get("brute_force_check", {})
        feas = exp.get("feasible_not_optimal_example") or {}
        rows.append({
            "case_id": c["case_id"], "category": c["category"], "title": c["title"],
            "tick_minutes": c["tick_minutes"], "expected_status": exp["expected_status"],
            "preflight_code": exp.get("preflight_code", ""),
            "optimal_makespan_minutes": exp.get("optimal_makespan_minutes") or "",
            "completion_local": exp.get("completion_local", ""),
            "unique_optimal_schedule": exp.get("unique_optimal_schedule", ""),
            "distinct_optimal_active_schedules": exp.get("distinct_optimal_active_schedules", ""),
            "active_schedules_enumerated": exp.get("active_schedules_enumerated", ""),
            "feasible_not_optimal_makespan_minutes": feas.get("makespan_minutes", ""),
            "unconstrained_optimal_makespan_minutes": exp.get("unconstrained_optimal_makespan_minutes", ""),
            "brute_force_lower_bound_proven": (bf.get("schedules_found_below_optimum") == 0
                                               if "schedules_found_below_optimum" in bf else
                                               (bf.get("schedules_found") == 0 if bf else "")),
            "proof_method": exp["proof"], "diagnostic": exp.get("diagnostic", ""),
        })
        print(c["case_id"], exp["expected_status"], exp.get("optimal_makespan_minutes"),
              exp.get("completion_local", exp.get("preflight_code")), exp.get("distinct_optimal_active_schedules", ""),
              bf)
    doc = {"_meta": {"stage": "5.4B reference cases (Task 4)", "status": "HYPOTHETICAL software test inputs; "
                     "no engineering approval implied", "generator": "scripts/build_cpsat_reference_cases.py",
                     "independent_of": "pmi_core and OR-Tools"},
           "conventions": CONVENTIONS, "general_acceptance_criteria": GENERAL_ACCEPTANCE, "cases": out}
    (PKG / "cpsat_reference_cases.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (PKG / "cpsat_expected_results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
