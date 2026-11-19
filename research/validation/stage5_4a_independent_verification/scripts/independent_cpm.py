"""Independent Stage 5.4A verifier.

Does NOT import pmi_core.scheduling. Rebuilds durations and edges from the Stage 5.3A
handover and the Agent 2 preparation inputs, schedules on a brute-force minute
calendar (per-minute working predicate, exhaustive start search), recomputes
early/late dates and floats, and profiles resource use minute by minute.
"""

import csv
import json
from datetime import datetime, timedelta, timezone
from math import ceil
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[4]
PREP = REPO / "research/planning/stage5_4_preparation"
HANDOVER = REPO / "research/implementation/stage5_3/scheduling_handover.json"
PREFIX = {"24tlOXIsvMQfyRLiqh6fZt": ("C", "COL"), "1jDfy2_jTRueAw6f5fc3Ev": ("B", "BEAM"),
          "3wOB$MtWLSz8SJNgW3VJvy": ("S", "SLAB")}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def alias(item, p):
    special = {"INSPECTION-HOLD": "INSP", "STRIKING-RELEASE": "STRIKE", "FRM-STRIP": "STRIP", "CURE": "CURE"}
    if item in special:
        return f"{p}-{special[item]}"
    return f"{p}-{'POUR' if item.endswith('CONC') else item.split('-')[-1]}"


def ceil_tick(minutes, tick):
    # Exact decimal-safe ceiling: work in micro-minutes to avoid float noise such as 0.6*60.
    micro = round(minutes * 1_000_000)
    unit = tick * 1_000_000
    return -(-micro // unit) * tick


def build_model(tick):
    h = load(HANDOVER)
    prep = load(PREP / "controlled_scheduling_inputs.json")
    by_uid, acts = {}, {}
    for r in h["activities"]:
        p, fam = PREFIX[r["global_id"]]
        a = alias(r["work_item"], p)
        by_uid[r["id"]] = a
        if r["work_item"] == "INSPECTION-HOLD":
            raw, kind, res = r["elapsed_hours"] * 60, "inspection", {"INSPECTOR": 1}
        elif r["work_item"] == "CURE":
            raw, kind, res = prep["curing"][fam]["elapsed_hours"] * 60, "elapsed", {}
        elif r["work_item"] == "STRIKING-RELEASE":
            raw, kind, res = prep["striking"][fam]["elapsed_hours_from_pour"] * 60, "elapsed", {}
        else:
            raw, kind = r["productive_hours"] * 60, "productive"
            res = {**h["fixture_inputs"]["crews"][r["crew_id"]], **r.get("equipment_capacity_by_class", {})}
        acts[a] = {"uid": r["id"], "raw": raw, "kind": kind, "res": res,
                   "dur": raw if kind == "elapsed" else ceil_tick(raw, tick),
                   "pour": a.endswith("-POUR"), "cost": r.get("reference_cost_eur")}
    # Source A: Stage 5.3A edges, transformed per documented D5 and D3 resolutions.
    edges_a = set()
    for e in h["dependencies"]:
        assert e["relation"] == "FS" and e["lag_hours"] == 0
        x, y = by_uid[e["predecessor_id"]], by_uid[e["successor_id"]]
        if not (x.endswith("CURE") and y.endswith("STRIKE")):
            edges_a.add((x, y))
    # Source B: Agent 2 preparation predecessor lists.
    edges_b = {(p["id"], r["id"]) for r in prep["activities"] for p in r["predecessors"]}
    assert all(p["lag_minutes"] == 0 and p["relation"] == "FS" for r in prep["activities"] for p in r["predecessors"])
    return h, prep, acts, edges_a, edges_b


class Calendar:
    def __init__(self, prep, start_local, horizon_local):
        self.zone = ZoneInfo(prep["calendar"]["timezone"])
        self.holidays = set(prep["calendar"]["date_exceptions"])
        self.t0 = int(datetime.fromisoformat(start_local).replace(tzinfo=self.zone).timestamp() // 60)
        self.t1 = int(datetime.fromisoformat(horizon_local).replace(tzinfo=self.zone).timestamp() // 60)
        n = self.t1 - self.t0
        self.work = bytearray(n)
        self.pour = bytearray(n)
        for i in range(n):
            loc = datetime.fromtimestamp((self.t0 + i) * 60, self.zone)
            if loc.isoweekday() <= 5 and loc.date().isoformat() not in self.holidays:
                hm = loc.hour * 60 + loc.minute
                self.work[i] = 480 <= hm < 960
                self.pour[i] = 480 <= hm < 840
        # prefix sums for O(1) "all minutes available" checks
        self.pw, self.pp = [0], [0]
        for i in range(n):
            self.pw.append(self.pw[-1] + self.work[i])
            self.pp.append(self.pp[-1] + self.pour[i])

    def ok(self, start, dur, pour):
        i = start - self.t0
        if i < 0 or i + dur > len(self.work):
            return False
        p = self.pp if pour else self.pw
        return p[i + dur] - p[i] == dur

    def fmt(self, m):
        return datetime.fromtimestamp(m * 60, self.zone).isoformat(timespec="minutes")


def schedule(tick, edges, start_local="2027-01-04T08:00", horizon_local="2027-03-01T16:00"):
    h, prep, acts, _, _ = build_model(tick)
    cal = Calendar(prep, start_local, horizon_local)
    preds = {a: [x for x, y in edges if y == a] for a in acts}
    succs = {a: [y for x, y in edges if x == a] for a in acts}
    order, seen = [], set()
    while len(order) < len(acts):
        progress = False
        for a in sorted(acts):
            if a not in seen and all(p in seen for p in preds[a]):
                order.append(a); seen.add(a); progress = True
        assert progress, "cycle"
    ES, EF, ready = {}, {}, {}
    for a in order:
        r = acts[a]
        t = max([cal.t0] + [EF[p] for p in preds[a]])
        ready[a] = t
        if r["kind"] != "elapsed":
            t = -(-(t - cal.t0) // tick) * tick + cal.t0
            while not cal.ok(t, r["dur"], r["pour"]):
                t += tick
                assert t < cal.t1
        ES[a], EF[a] = t, t + r["dur"]
    done = max(EF.values())

    def latest_start(a, limit):
        r = acts[a]
        if r["kind"] == "elapsed":
            return limit - r["dur"]
        t = limit - r["dur"]
        t -= (t - cal.t0) % tick
        while not cal.ok(t, r["dur"], r["pour"]):
            t -= tick
        return t

    LS, LF, FF = {}, {}, {}
    for a in reversed(order):
        lim = min([done] + [LS[s] for s in succs[a]])
        LS[a] = latest_start(a, lim)
        LF[a] = LS[a] + acts[a]["dur"]
        FF[a] = latest_start(a, min([done] + [ES[s] for s in succs[a]])) - ES[a]
    # resource profile
    caps = prep["resource_capacity_by_trade"]
    usage = {}
    for a, r in acts.items():
        for name, q in r["res"].items():
            for m in range(ES[a], EF[a]):
                usage.setdefault(name, {}).setdefault(m, 0)
                usage[name][m] += q
    peaks = {n: max(v.values()) for n, v in usage.items()}
    over = {n: peaks[n] for n in peaks if peaks[n] > caps.get(n, 0)}
    return {"cal": cal, "acts": acts, "order": order, "ES": ES, "EF": EF, "LS": LS, "LF": LF, "FF": FF,
            "done": done, "makespan": done - cal.t0, "peaks": peaks, "caps": caps, "over": over,
            "critical": [a for a in order if LS[a] == ES[a]], "ready": ready}


def final_edges(edges_a):
    added = {(f"{p}-POUR", f"{p}-STRIKE") for p in "CBS"} | {(f"{p}-CURE", f"{p}-STRIP") for p in "CBS"}
    cross = {("C-CURE", "B-FORM"), ("C-STRIP", "B-FORM"), ("B-CURE", "S-FORM"), ("S-STRIP", "B-STRIP")}
    return edges_a | added | cross


if __name__ == "__main__":
    import sys
    tick = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    h, prep, acts, ea, eb = build_model(tick)
    E = final_edges(ea)
    res = schedule(tick, E)
    for a in res["order"]:
        print(a, res["cal"].fmt(res["ES"][a]), res["cal"].fmt(res["EF"][a]), res["LS"][a] - res["ES"][a], res["FF"][a])
    print("done", res["cal"].fmt(res["done"]), res["makespan"], res["critical"], res["over"])
