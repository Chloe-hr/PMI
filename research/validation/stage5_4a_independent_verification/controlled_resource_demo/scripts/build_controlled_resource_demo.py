"""Build the Stage 5.4B larger controlled resource demonstration (Task 6).

HYPOTHETICAL SCHEDULING FIXTURE - not an IFC-validated construction case. No IFC model
supports these quantities; geometry is declared below and quantities follow explicit rules.

Reuses (unchanged) Stage 5.3A pmi_core.estimation.engine.estimate_operation and
pmi_core.estimation.references.load_references for every duration and cost. The CPM,
the capacity-feasible scheduler, the lower bound and the feasibility checker are
independent code in this file; pmi_core.scheduling is not used.
"""

import csv
import json
import random
import sys
import time as clock
from bisect import bisect_left
from datetime import datetime, timedelta
from html import escape
from itertools import permutations
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO))
from pmi_core.estimation.engine import estimate_operation  # noqa: E402
from pmi_core.estimation.references import load_references  # noqa: E402

TICK = 5
TZ = "Europe/Madrid"
ZONE = ZoneInfo(TZ)
START = "2027-02-01T08:00"
HORIZON = "2027-04-30T16:00"
HYP = "hypothetical_fixture"
INF = 10 ** 9

# --------------------------------------------------------------------------- inputs
WEEK = range(1, 6)
CALENDARS = {
    "PROJECT": {"windows": [("08:00", "16:00")], "note": "Hypothetical site shift Mon-Fri 08:00-16:00."},
    "INSPECTOR": {"windows": [("10:00", "12:00")], "note": "Hypothetical inspector attendance Mon-Fri 10:00-12:00."},
    "DELIVERY": {"windows": [("08:00", "14:00")], "note": "Hypothetical plant delivery window Mon-Fri 08:00-14:00."},
}
DATE_EXCEPTIONS = []  # explicit: none declared; regional holidays are user input

# resource_id: (class, unit, capacity, availability, calendar, explicit_none, note)
RESOURCES = {
    "OF1_ENCOFRADOR": ("labour_trade", "worker", 2, "calendar", "PROJECT", False, "One formwork crew."),
    "OF1_FERRALLISTA": ("labour_trade", "worker", 2, "calendar", "PROJECT", False, "One reinforcement crew."),
    "PEON_ESPECIAL": ("labour_trade", "worker", 5, "calendar", "PROJECT", False, "Shared labourer pool."),
    "OFICIAL_1": ("labour_trade", "worker", 2, "calendar", "PROJECT", False, "Two concreting chargehands."),
    "VIBRADOR": ("equipment", "machine", 2, "calendar", "PROJECT", False, "Two internal vibrators."),
    "CRANE": ("equipment", "machine", 0, "calendar", "PROJECT", True, "Explicit none: manual handling."),
    "CONCRETE_PUMP": ("equipment", "machine", 0, "calendar", "PROJECT", True, "Explicit none: direct chute discharge."),
    "INSPECTOR": ("inspector", "inspector", 1, "calendar", "INSPECTOR", False, "One inspector."),
    "CONCRETE_SUPPLY": ("supply_source", "m3/h", 6, "calendar", "DELIVERY", False, "Shared plant rate 6 m3/h."),
    "COL_FORM_SET": ("reusable_asset", "set", 2, "continuous", None, False, "Two column formwork sets."),
    "BEAM_FORM_SET": ("reusable_asset", "set", 3, "continuous", None, False, "Three beam side+soffit panel sets."),
    "SLAB_PANEL_SET": ("reusable_asset", "set", 2, "continuous", None, False, "Two slab soffit panel sets."),
    "BEAM_PROP": ("reusable_asset", "piece", 9, "continuous", None, False, "Beam soffit prop pool."),
    "SLAB_PROP": ("reusable_asset", "piece", 10, "continuous", None, False, "Slab prop pool (separate)."),
}
MODES = {
    "HYP-FORM": {"OF1_ENCOFRADOR": 2, "PEON_ESPECIAL": 1},
    "HYP-REBAR": {"OF1_FERRALLISTA": 2},
    "HYP-CONC": {"PEON_ESPECIAL": 2, "OFICIAL_1": 1, "VIBRADOR": 1},
}
REF_KEYS = {"COL-REBAR": "05HAC00015", "BEAM-REBAR": "05HAC00015", "SLAB-REBAR": "05HAC00015",
            "COL-FORM": "05HEM00001", "BEAM-FORM": "05HEM00051", "SLAB-FORM": "05HEM00101",
            "COL-CONC": "05HHP00003", "BEAM-CONC": "05HHJ00003", "SLAB-CONC": "05HHL00003",
            "FRM-STRIP": "05HED00001"}
CONCRETE = "HA-25/P/20/XC2"
DRAW = {"COL": 3, "BEAM": 3, "SLAB": 6}          # m3/h drawn from CONCRETE_SUPPLY per pour
CURE_H = {"COL": 24, "BEAM": 24, "SLAB": 24}       # hypothetical curing gates
STRIKE_H = {"COL": 24, "BEAM": 168, "SLAB": 168}   # hypothetical striking minimum from pour finish
REBAR_KG = {"C1": 75, "C2": 75, "C3": 75, "C4": 75, "B1": 125, "B2": 125, "B3": 105, "B4": 105,
            "S-W": 290, "S-E": 290}
INSPECTION_MIN = 30

# Geometry (m). Columns 0.4x0.4 at the corners of a 6.0 x 5.0 grid, 0-3.5 m.
# Beams 0.3 wide x 0.5 deep between column faces, 3.0-3.5 m. Slab 0.2 m on top, split at x = 3.0.
GEOM = {
    "C1": ("COL", "W", [[-0.2, -0.2, 0.0], [0.2, 0.2, 3.5]]),
    "C3": ("COL", "W", [[-0.2, 4.8, 0.0], [0.2, 5.2, 3.5]]),
    "C2": ("COL", "E", [[5.8, -0.2, 0.0], [6.2, 0.2, 3.5]]),
    "C4": ("COL", "E", [[5.8, 4.8, 0.0], [6.2, 5.2, 3.5]]),
    "B1": ("BEAM", "W+E", [[0.2, -0.15, 3.0], [5.8, 0.15, 3.5]]),
    "B2": ("BEAM", "W+E", [[0.2, 4.85, 3.0], [5.8, 5.15, 3.5]]),
    "B3": ("BEAM", "W", [[-0.15, 0.2, 3.0], [0.15, 4.8, 3.5]]),
    "B4": ("BEAM", "E", [[5.85, 0.2, 3.0], [6.15, 4.8, 3.5]]),
    "S-W": ("SLAB", "W", [[-0.2, -0.2, 3.5], [3.0, 5.2, 3.7]]),
    "S-E": ("SLAB", "E", [[3.0, -0.2, 3.5], [6.2, 5.2, 3.7]]),
}
SUPPORTS = {"B1": ["C1", "C2"], "B2": ["C3", "C4"], "B3": ["C1", "C3"], "B4": ["C2", "C4"],
            "S-W": ["B1", "B2", "B3"], "S-E": ["B1", "B2", "B4"]}
BEAM_PROPS = {"B1": 3, "B2": 3, "B3": 2, "B4": 2}
SLAB_PROPS = {"S-W": 6, "S-E": 6}


def overlap(a, b, axes):
    out = 1.0
    for k in axes:
        out *= max(0.0, min(a[1][k], b[1][k]) - max(a[0][k], b[0][k]))
    return out


def quantities():
    rows = {}
    for eid, (fam, zone, box) in GEOM.items():
        dx, dy, dz = (box[1][k] - box[0][k] for k in range(3))
        vol = round(dx * dy * dz, 9)
        if fam == "COL":
            form = round(2 * (dx + dy) * 3.0, 9)
            rule = "Four vertical faces from 0.0 to 3.0 m (beam soffit). The 3.0-3.5 m node is closed by the beam forms."
        elif fam == "BEAM":
            length = max(dx, dy)
            width = min(dx, dy)
            form = round(2 * dz * length + width * length, 9)
            rule = "Two sides (depth x clear length) plus soffit (width x clear length) between column faces."
        else:
            plan = dx * dy
            under = sum(overlap(box, GEOM[o][2], (0, 1)) for o in GEOM
                        if GEOM[o][0] in ("COL", "BEAM") and abs(GEOM[o][2][1][2] - box[0][2]) < 1e-9)
            form = round(plan - under, 9)
            rule = "Soffit plan area less column and beam top footprints under the section. Edge and joint stop-ends are outside the fixture rule."
        rows[eid] = {"element_id": f"HYP-{eid}", "family": fam, "zone": zone, "bounds_m": box,
                     "placed_concrete_m3": vol, "formwork_m2": form, "formwork_rule": rule,
                     "reinforcement_kg": REBAR_KG[eid],
                     "reinforcement_boq": f"HYP-{eid}-BOQ: explicit {REBAR_KG[eid]} kg net B500S software-test line.",
                     "ifc_global_id": None, "input_state": HYP}
    names = list(GEOM)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert overlap(GEOM[a][2], GEOM[b][2], (0, 1, 2)) < 1e-9, (a, b)
    return rows


# --------------------------------------------------------------------------- estimation
def trade_names(refs):
    names = {}
    for ref in refs.values():
        for key in ref["labor_per_unit"]:
            rid = ("OF1_ENCOFRADOR" if "ENCOFRADOR" in key else "OF1_FERRALLISTA" if "FERRALLISTA" in key
                   else "PEON_ESPECIAL" if "ESPECIAL" in key else "OFICIAL_1" if key.startswith("OFICIAL") else None)
            assert rid, key
            names[rid] = key
    names["VIBRADOR"] = "VIBRADOR"
    return names


def build_activities(q, refs, display):
    acts, deps, approvals = [], [], {}
    method = {"COL": ["REBAR", "FORM"], "BEAM": ["FORM", "REBAR"], "SLAB": ["FORM", "REBAR"]}
    method_name = {"COL": "cage_first", "BEAM": "formwork_first", "SLAB": "formwork_first"}

    def dep(a, b, rule, source, note=""):
        deps.append({"predecessor": a, "successor": b, "relation": "FS", "lag_minutes": 0,
                     "lag_basis": "elapsed", "rule_id": rule, "source": source, "condition": note})

    for eid, row in q.items():
        fam = row["family"]
        pref = {"COL": "COL", "BEAM": "BEAM", "SLAB": "SLAB"}[fam]
        ops = {"REBAR": (f"{pref}-REBAR", row["reinforcement_kg"], "kg", "HYP-REBAR"),
               "FORM": (f"{pref}-FORM", row["formwork_m2"], "m2", "HYP-FORM"),
               "POUR": (f"{pref}-CONC", row["placed_concrete_m3"], "m3", "HYP-CONC"),
               "STRIP": ("FRM-STRIP", row["formwork_m2"], "m2", "HYP-FORM")}
        for op, (item, qty, unit, mode) in ops.items():
            ref = refs[item, REF_KEYS[item]]
            units = MODES[mode]
            crew = {display[r]: n for r, n in units.items() if r != "VIBRADOR"}
            machines = {"VIBRADOR": units["VIBRADOR"]} if "VIBRADOR" in units else {}
            thr = {"CONCRETE_DELIVERY": DRAW[fam]} if op == "POUR" else None
            est = estimate_operation(qty, unit, ref, crew, machines, concurrent_throughput=thr)
            demands = dict(units)
            if op == "POUR":
                demands["CONCRETE_SUPPLY"] = DRAW[fam]
            acts.append({
                "id": f"{eid}-{op}", "element": eid, "package_id": f"WP-{eid}", "zone": row["zone"],
                "work_item": item, "kind": "productive", "mode": mode, "bcca_code": ref["code"],
                "quantity": qty, "unit": unit, "productive_hours": est["productive_hours"],
                "duration_minutes": round(est["productive_hours"] * 60, 9), "demands": demands,
                "worker_hours_by_trade": {k: round(v, 9) for k, v in est["worker_hours_by_trade"].items()},
                "machine_hours_by_class": {k: round(v, 9) for k, v in est["machine_hours_by_class"].items()},
                "capacity_bounds_hours": {k: round(v, 9) for k, v in est["capacity_bounds_hours"].items()},
                "cost_eur": round(est["reference_cost_eur"], 6),
                "cost_components_eur": {k: round(v, 6) for k, v in est["cost_components_eur"].items()},
                "calendars": sorted({"PROJECT"} | {RESOURCES[r][4] for r in demands}),
                "interruption": "non_interruptible", "approval_ids": [ref["approval_id"]], "input_state": HYP,
                "reference_edition": ref["edition"], "concept_price_date_ddmmyy": ref["concept_price_date_ddmmyy"],
            })
        acts.append({"id": f"{eid}-INSP", "element": eid, "package_id": f"WP-{eid}", "zone": row["zone"],
                     "work_item": "INSPECTION", "kind": "inspection", "mode": None, "bcca_code": None,
                     "quantity": None, "unit": None, "productive_hours": INSPECTION_MIN / 60,
                     "duration_minutes": INSPECTION_MIN, "demands": {"INSPECTOR": 1}, "cost_eur": 0.0,
                     "calendars": ["INSPECTOR", "PROJECT"], "interruption": "non_interruptible",
                     "pass_event": {"id": f"EV-{eid}-INSP", "status": "hypothetical_pass"},
                     "approval_ids": ["AP-DR06"], "input_state": HYP})
        for op, hours, rule in (("CURE", CURE_H[fam], "AP-DR07"), ("STRIKE", STRIKE_H[fam], "AP-DR08")):
            acts.append({"id": f"{eid}-{op}", "element": eid, "package_id": f"WP-{eid}", "zone": row["zone"],
                         "work_item": "CURE" if op == "CURE" else "STRIKING-RELEASE", "kind": "elapsed_hold",
                         "mode": None, "bcca_code": None, "quantity": None, "unit": None, "productive_hours": 0,
                         "duration_minutes": hours * 60, "demands": {}, "cost_eur": 0.0, "calendars": [],
                         "interruption": None, "approval_ids": [rule], "input_state": HYP,
                         **({"release_event": {"id": f"EV-{eid}-STRENGTH", "status": "hypothetical_pass_at_minimum",
                                               "anchor": f"{eid}-POUR finish"}} if op == "STRIKE" else {})})
        first, second = method[fam]
        dep(f"{eid}-{first}", f"{eid}-{second}", "AP-DR05" if fam == "COL" else "AP-DR06", "element method",
            method_name[fam])
        dep(f"{eid}-{second}", f"{eid}-INSP", "AP-DR06", "element method")
        dep(f"{eid}-INSP", f"{eid}-POUR", "AP-DR06", "element method", "inspection pass")
        dep(f"{eid}-POUR", f"{eid}-CURE", "AP-DR07", "element method")
        dep(f"{eid}-POUR", f"{eid}-STRIKE", "AP-DR08", "element method", "striking minimum from pour finish")
        dep(f"{eid}-CURE", f"{eid}-STRIP", "AP-DR08", "element method")
        dep(f"{eid}-STRIKE", f"{eid}-STRIP", "AP-DR08", "element method", "strength release")
    for member, supports in SUPPORTS.items():
        for s in supports:
            if q[member]["family"] == "BEAM":
                dep(f"{s}-CURE", f"{member}-FORM", "AP-DR09", "support", "beam formwork bears on cured column")
                dep(f"{s}-STRIP", f"{member}-FORM", "AP-DR09", "support", "column forms off before beam forms (fixture rule)")
            else:
                dep(f"{s}-CURE", f"{member}-FORM", "AP-DR09", "support", "slab soffit forms after supporting beam curing gate")
                dep(f"{member}-STRIP", f"{s}-STRIP", "AP-DR09", "support",
                    "beam soffit and props retained until every supported slab section is stripped")
    return acts, deps


def build_reservations():
    res = []

    def add(rid, asset, qty, eid):
        res.append({"reservation_id": rid, "resource_id": asset, "quantity": qty, "element_ids": [f"HYP-{eid}"],
                    "start_event": {"kind": "activity_start", "activity_id": f"{eid}-FORM"},
                    "release_condition": {"all_of": [{"kind": "activity_finish", "activity_id": f"{eid}-STRIP"}],
                                          "return_lead_minutes": 0, "reshoring": "not_permitted",
                                          "input_state": HYP},
                    "occupancy_basis": "continuous_elapsed",
                    "covers_activities": [f"{eid}-{op}" for op in ("FORM", "REBAR", "INSP", "POUR", "CURE", "STRIKE", "STRIP")],
                    "input_state": HYP, "approval_required": True})

    for c in ("C1", "C2", "C3", "C4"):
        add(f"R-COLSET-{c}", "COL_FORM_SET", 1, c)
    for b, props in BEAM_PROPS.items():
        add(f"R-BEAMSET-{b}", "BEAM_FORM_SET", 1, b)
        add(f"R-BEAMPROP-{b}", "BEAM_PROP", props, b)
    for s, props in SLAB_PROPS.items():
        add(f"R-SLABSET-{s}", "SLAB_PANEL_SET", 1, s)
        add(f"R-SLABPROP-{s}", "SLAB_PROP", props, s)
    return res


# --------------------------------------------------------------------------- time model
def epoch_min(local):
    return int(datetime.fromisoformat(local).replace(tzinfo=ZONE).timestamp() // 60)


ANCHOR = epoch_min(START)
N = (epoch_min(HORIZON) - ANCHOR) // TICK


def stamp(tick):
    return datetime.fromtimestamp((ANCHOR + tick * TICK) * 60, ZONE).isoformat(timespec="minutes")


def cal_mask(cid):
    mask = bytearray(N)
    day0 = datetime.fromisoformat(START).date()
    for k in range(N * TICK // 1440 + 2):
        day = day0 + timedelta(days=k)
        if day.isoweekday() not in WEEK or day.isoformat() in DATE_EXCEPTIONS:
            continue
        for a, b in CALENDARS[cid]["windows"]:
            lo, hi = epoch_min(f"{day}T{a}") - ANCHOR, epoch_min(f"{day}T{b}") - ANCHOR
            assert lo % TICK == 0 and hi % TICK == 0, "TICK_MISALIGNED"
            for i in range(max(0, lo // TICK), min(N, hi // TICK)):
                mask[i] = 1
    return mask


class Model:
    def __init__(self, acts, deps, reservations):
        self.acts = {a["id"]: a for a in acts}
        self.ids = sorted(self.acts)
        self.preds = {a: [] for a in self.ids}
        self.succs = {a: [] for a in self.ids}
        for d in deps:
            self.preds[d["successor"]].append(d["predecessor"])
            self.succs[d["predecessor"]].append(d["successor"])
        self.masks = {c: cal_mask(c) for c in CALENDARS}
        self.dur, self.nf, self.lt, self.hold = {}, {}, {}, {}
        cache = {}
        for k, a in self.acts.items():
            self.dur[k] = -(-round(a["duration_minutes"] * 1000) // (TICK * 1000))
            self.hold[k] = a["kind"] == "elapsed_hold"
            if self.hold[k]:
                continue
            key = (tuple(a["calendars"]), self.dur[k])
            if key not in cache:
                m = bytearray(b"\x01" * N)
                for c in a["calendars"]:
                    m = bytearray(x & y for x, y in zip(m, self.masks[c]))
                d = self.dur[k]
                run = [0] * (N + 1)
                for i in range(N - 1, -1, -1):
                    run[i] = run[i + 1] + 1 if m[i] else 0
                nf = [INF] * (N + 1)
                for i in range(N - 1, -1, -1):
                    nf[i] = i if run[i] >= d else nf[i + 1]
                lt, last = [-1] * (N + 1), -1
                for i in range(N + 1):
                    if i < N and run[i] >= d:
                        last = i
                    lt[i] = last
                cache[key] = (nf, lt)
            self.nf[k], self.lt[k] = cache[key]
        self.res = reservations
        self.res_from = {a: [r for r in reservations if r["start_event"]["activity_id"] == a] for a in self.ids}
        self.res_to = {a: [r for r in reservations if r["release_condition"]["all_of"][0]["activity_id"] == a]
                       for a in self.ids}

    def topo(self, extra=()):
        preds = {a: list(p) for a, p in self.preds.items()}
        for a, b in extra:
            preds[b].append(a)
        indeg = {a: len(p) for a, p in preds.items()}
        succ = {a: [] for a in self.ids}
        for b, ps in preds.items():
            for a in ps:
                succ[a].append(b)
        ready = sorted(a for a in self.ids if not indeg[a])
        order = []
        while ready:
            a = ready.pop()
            order.append(a)
            for b in succ[a]:
                indeg[b] -= 1
                if not indeg[b]:
                    ready.append(b)
        return (order, preds, succ) if len(order) == len(self.ids) else None

    def cpm(self, extra=()):
        topo = self.topo(extra)
        if topo is None:
            return None
        order, preds, succ = topo
        es, ef = {}, {}
        for a in order:
            b = max([0] + [ef[p] for p in preds[a]])
            s = b if self.hold[a] else (self.nf[a][b] if b < N else INF)
            if s >= INF:
                return None
            es[a], ef[a] = s, s + self.dur[a]
        span = max(ef.values())
        ls, lf = {}, {}
        for a in reversed(order):
            lf[a] = min([span] + [ls[s] for s in succ[a]])
            ls[a] = lf[a] - self.dur[a] if self.hold[a] else self.lt[a][lf[a] - self.dur[a]]
        return {"es": es, "ef": ef, "ls": ls, "lf": lf, "span": span, "order": order}


# --------------------------------------------------------------------------- lower bound
def group_bound(model, es, members, cal):
    mask = model.masks[cal] if cal != "INSPECTOR+PROJECT" else bytearray(
        x & y for x, y in zip(model.masks["INSPECTOR"], model.masks["PROJECT"]))
    cum = [0]
    for v in mask:
        cum.append(cum[-1] + v)
    best = 0
    for t in sorted({es[a] for a in members}):
        tail = [a for a in members if es[a] >= t]
        target = cum[t] + sum(model.dur[a] for a in tail)
        best = max(best, bisect_left(cum, target))   # preemptive: earliest tick by which the work fits
        if len(tail) <= 7:
            # Exact non-preemptive single-resource bound: every order, each activity on its own calendar
            # (nf) and released at its relaxed earliest start.
            exact = INF
            for order in permutations(tail):
                f = t
                for a in order:
                    s = model.nf[a][max(f, es[a])] if max(f, es[a]) < N else INF
                    if s >= INF:
                        f = INF
                        break
                    f = s + model.dur[a]
                exact = min(exact, f)
            best = max(best, exact)
    return best


def lower_bound(model):
    groups = {
        "formwork crew (HYP-FORM uses both encofradores)": ([a for a, x in model.acts.items() if x["mode"] == "HYP-FORM"], "PROJECT"),
        "reinforcement crew (HYP-REBAR uses both ferrallistas)": ([a for a, x in model.acts.items() if x["mode"] == "HYP-REBAR"], "PROJECT"),
        "inspector (capacity 1)": ([a for a, x in model.acts.items() if x["kind"] == "inspection"], "INSPECTOR+PROJECT"),
    }
    # Reservation disjunctions (exact for the reservation constraints, see report).
    assert RESOURCES["COL_FORM_SET"][2] == 2 and all(r["quantity"] == 1 for r in model.res if r["resource_id"] == "COL_FORM_SET")
    assert RESOURCES["BEAM_FORM_SET"][2] == 3 and sum(BEAM_PROPS.values()) > RESOURCES["BEAM_PROP"][2] >= \
        max(sum(BEAM_PROPS[b] for b in t) for t in (("B1", "B2", "B3"), ("B1", "B2", "B4"), ("B1", "B3", "B4"), ("B2", "B3", "B4")))
    assert sum(SLAB_PROPS.values()) > RESOURCES["SLAB_PROP"][2] and RESOURCES["SLAB_PANEL_SET"][2] >= 2
    cols = ["C1", "C2", "C3", "C4"]
    col_structs = set()
    for p in permutations(cols):
        for k in range(5):
            chains = [p[:k], p[k:]]
            col_structs.add(frozenset((f"{a}-STRIP", f"{b}-FORM") for ch in chains for a, b in zip(ch, ch[1:])))
    beam_pairs = [frozenset({(f"{a}-STRIP", f"{b}-FORM")}) for a in BEAM_PROPS for b in BEAM_PROPS if a != b]
    slab_orders = [frozenset({("S-W-STRIP", "S-E-FORM")}), frozenset({("S-E-STRIP", "S-W-FORM")})]
    best, evaluated, cyclic = None, 0, 0
    for cs in col_structs:
        for bp in beam_pairs:
            for so in slab_orders:
                evaluated += 1
                extra = cs | bp | so
                r = model.cpm(extra)
                if r is None:
                    cyclic += 1
                    continue
                parts = {"precedence + calendars + reservation choice (CPM)": r["span"]}
                for name, (members, cal) in groups.items():
                    parts[name] = group_bound(model, r["es"], members, cal)
                value = max(parts.values())
                if best is None or value < best["value"]:
                    best = {"value": value, "parts": parts, "extra": sorted(extra), "cpm": r}
    return best, {"choices_evaluated": evaluated, "choices_cyclic_or_infeasible": cyclic,
                  "column_chain_structures": len(col_structs), "beam_ordered_pairs": len(beam_pairs),
                  "slab_orders": len(slab_orders)}


# --------------------------------------------------------------------------- scheduler
def sgs(model, priority, rng=None, noise=0, rule="earliest"):
    usage = {r: [0] * N for r, v in RESOURCES.items() if v[0] != "reusable_asset"}
    caps = {r: v[2] for r, v in RESOURCES.items()}
    intervals = {r: [] for r, v in RESOURCES.items() if v[0] == "reusable_asset"}
    open_iv = {}
    es, ef = {}, {}
    left = set(model.ids)

    def coverage_ok(asset, t, qty):
        ivs = intervals[asset]
        points = [t] + [s for s, e, q, _ in ivs if s > t]
        for p in points:
            cov = sum(q for s, e, q, _ in ivs if s <= p and (e is None or p < e))
            if cov + qty > caps[asset]:
                return False
        return True

    def earliest(a):
        t = max([0] + [ef[p] for p in model.preds[a]])
        if model.hold[a]:
            return t
        d = model.dur[a]
        dem = model.acts[a]["demands"]
        while True:
            if t >= N:
                return None
            t = model.nf[a][t]
            if t >= INF:
                return None
            bad = None
            for r, qn in dem.items():
                u = usage[r]
                for i in range(t, t + d):
                    if u[i] + qn > caps[r]:
                        bad = i
                        break
                if bad is not None:
                    break
            if bad is not None:
                t = bad + 1
                continue
            blocked = False
            for rv in model.res_from[a]:
                if not coverage_ok(rv["resource_id"], t, rv["quantity"]):
                    ends = [e for s, e, q, _ in intervals[rv["resource_id"]] if e is not None and e > t]
                    if not ends:
                        return None
                    t = min(ends)
                    blocked = True
                    break
            if not blocked:
                return t

    while left:
        best = None
        for a in sorted(left):
            if any(p in left for p in model.preds[a]):
                continue
            t = earliest(a)
            if t is None:
                continue
            p = priority[a] + (rng.uniform(0, noise) if rng else 0)
            key = (t, p, a) if rule == "earliest" else (p, t, a)
            if best is None or key < best[0]:
                best = (key, a, t)
        if best is None:
            return None
        _, a, t = best
        es[a], ef[a] = t, t + model.dur[a]
        for r, qn in model.acts[a]["demands"].items():
            for i in range(t, ef[a]):
                usage[r][i] += qn
        for rv in model.res_from[a]:
            iv = [t, None, rv["quantity"], rv["reservation_id"]]
            intervals[rv["resource_id"]].append(iv)
            open_iv[rv["reservation_id"]] = iv
        for rv in model.res_to[a]:
            open_iv[rv["reservation_id"]][1] = ef[a]
        left.discard(a)
    return {"es": es, "ef": ef, "span": max(ef.values())}


# --------------------------------------------------------------------------- independent checker
def in_calendar(cid, minute_epoch):
    loc = datetime.fromtimestamp(minute_epoch * 60, ZONE)
    if loc.isoweekday() not in WEEK or loc.date().isoformat() in DATE_EXCEPTIONS:
        return False
    hm = loc.strftime("%H:%M")
    return any(a <= hm < b for a, b in CALENDARS[cid]["windows"])


def check_schedule(fixture, sched):
    """Recheck a schedule from its minute timestamps only (no tick masks, no scheduler state)."""
    acts = {a["id"]: a for a in fixture["activities"]}
    start = {k: epoch_min(v[0][:16]) for k, v in sched.items()}
    finish = {k: epoch_min(v[1][:16]) for k, v in sched.items()}
    rows = []

    def add(check, subject, ok, detail=""):
        rows.append({"check": check, "subject": subject, "passed": bool(ok), "detail": detail})

    for k, a in acts.items():
        dur = finish[k] - start[k]
        expected = -(-round(a["duration_minutes"] * 1000) // (TICK * 1000)) * TICK
        add("duration_exact_ticks", k, dur == expected, f"{dur} vs {expected}")
        if a["kind"] != "elapsed_hold":
            ok = all(in_calendar(c, m) for m in range(start[k], finish[k]) for c in a["calendars"])
            add("inside_project_and_resource_calendars", k, ok, "+".join(a["calendars"]))
    for d in fixture["dependencies"]:
        add("precedence_FS", f"{d['predecessor']}->{d['successor']}", start[d["successor"]] >= finish[d["predecessor"]])
    for k, a in acts.items():
        if a["work_item"] == "STRIKING-RELEASE":
            add("strike_from_pour_finish", k, start[k] == finish[k.replace("STRIKE", "POUR")])
    conflicts = []
    res = {r["resource_id"]: r for r in fixture["resources"]}
    for rid, spec in res.items():
        events = {}
        holders = []
        if spec["resource_class"] == "reusable_asset":
            for rv in fixture["reservations"]:
                if rv["resource_id"] == rid:
                    s = start[rv["start_event"]["activity_id"]]
                    e = max(finish[x["activity_id"]] for x in rv["release_condition"]["all_of"]) + \
                        rv["release_condition"]["return_lead_minutes"]
                    holders.append((s, e, rv["quantity"], rv["reservation_id"]))
        else:
            for k, a in acts.items():
                q = a["demands"].get(rid)
                if q:
                    holders.append((start[k], finish[k], q, k))
        for s, e, q, _ in holders:
            events[s] = events.get(s, 0) + q
            events[e] = events.get(e, 0) - q
        cur, peak, times = 0, 0, sorted(events)
        for t0, t1 in zip(times, times[1:]):
            cur += events[t0]
            peak = max(peak, cur)
            if cur > (spec["capacity"] or 0):
                who = sorted(h for s, e, q, h in holders if s <= t0 < e)
                if conflicts and conflicts[-1]["resource"] == rid and conflicts[-1]["_end"] == t0 \
                        and conflicts[-1]["holders"] == who:
                    conflicts[-1]["_end"] = t1
                    conflicts[-1]["peak_usage"] = max(conflicts[-1]["peak_usage"], cur)
                else:
                    conflicts.append({"resource": rid, "capacity": spec["capacity"], "peak_usage": cur,
                                      "_start": t0, "_end": t1, "holders": who})
        add("capacity", rid, peak <= (spec["capacity"] or 0), f"peak {peak} / capacity {spec['capacity']}")
    for c in conflicts:
        c["start"] = datetime.fromtimestamp(c.pop("_start") * 60, ZONE).isoformat(timespec="minutes")
        c["finish"] = datetime.fromtimestamp(c.pop("_end") * 60, ZONE).isoformat(timespec="minutes")
        c["holders"] = " ".join(c["holders"])
    return rows, conflicts


# --------------------------------------------------------------------------- outputs
def write_csv(name, rows, fields=None):
    fields = fields or list(rows[0])
    with (DEMO / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()})


def as_rows(model, sched_ticks, label):
    rows = []
    for a in sorted(model.ids, key=lambda k: (sched_ticks["es"][k], k)):
        x = model.acts[a]
        rows.append({"schedule": label, "activity_id": a, "element": x["element"], "zone": x["zone"],
                     "work_item": x["work_item"], "kind": x["kind"], "mode": x["mode"],
                     "start": stamp(sched_ticks["es"][a]), "finish": stamp(sched_ticks["ef"][a]),
                     "raw_minutes": x["duration_minutes"], "scheduled_minutes": model.dur[a] * TICK,
                     "cost_eur": x["cost_eur"]})
    return rows


def occupancy(model, sch):
    out = []
    for a in model.ids:
        for r, q in model.acts[a]["demands"].items():
            out.append({"resource": r, "basis": "working_time", "holder": a, "units": q,
                        "start": stamp(sch["es"][a]), "finish": stamp(sch["ef"][a])})
    for rv in model.res:
        out.append({"resource": rv["resource_id"], "basis": "continuous_elapsed", "holder": rv["reservation_id"],
                    "units": rv["quantity"], "start": stamp(sch["es"][rv["start_event"]["activity_id"]]),
                    "finish": stamp(sch["ef"][rv["release_condition"]["all_of"][0]["activity_id"]])})
    return sorted(out, key=lambda r: (r["resource"], r["start"], r["holder"]))


def profiles(model, sch):
    prof = {r: [0] * (sch["span"] + 1) for r in RESOURCES}
    for a in model.ids:
        for r, q in model.acts[a]["demands"].items():
            for i in range(sch["es"][a], sch["ef"][a]):
                prof[r][i] += q
    for rv in model.res:
        s = sch["es"][rv["start_event"]["activity_id"]]
        e = sch["ef"][rv["release_condition"]["all_of"][0]["activity_id"]]
        for i in range(s, e):
            prof[rv["resource_id"]][i] += rv["quantity"]
    return prof


def utilization(model, sch, label):
    prof = profiles(model, sch)
    rows = []
    for r, (cls, unit, cap, avail, cal, none, _) in RESOURCES.items():
        if none:
            continue
        span = sch["span"]
        if avail == "continuous":
            avail_ticks = span
        else:
            m = bytearray(x & y for x, y in zip(model.masks[cal], model.masks["PROJECT"])) if cal != "PROJECT" else model.masks["PROJECT"]
            avail_ticks = sum(m[:span])
        used = sum(prof[r][:span])
        rows.append({"schedule": label, "resource": r, "class": cls, "unit": unit, "capacity": cap,
                     "basis": "continuous_elapsed" if avail == "continuous" else "working_time",
                     "peak_usage": max(prof[r]), "over_capacity_ticks": sum(1 for v in prof[r] if v > cap),
                     "unit_minutes_used": used * TICK, "unit_minutes_available": cap * avail_ticks * TICK,
                     "utilization_pct": round(100 * used / (cap * avail_ticks), 2) if avail_ticks else 0})
    return rows


def main():
    t0 = clock.perf_counter()
    refs, refs_sha = load_references()
    display = trade_names(refs)
    q = quantities()
    acts, deps = build_activities(q, refs, display)
    reservations = build_reservations()
    resources = [{"resource_id": r, "display_name": display.get(r, r), "resource_class": v[0], "unit": v[1],
                  "capacity": v[2], "explicit_none": v[5], "availability": v[3], "calendar_ref": v[4],
                  "input_state": HYP, "evidence_ref": "Task 6 hypothetical demonstration input",
                  "approval_required": True, "note": v[6]} for r, v in RESOURCES.items()]
    fixture = {
        "_meta": {"title": "PMI Stage 5.4B controlled resource demonstration",
                  "status": "HYPOTHETICAL SCHEDULING FIXTURE - not an IFC-validated construction case. "
                            "No IFC model supports these quantities. All engineering approvals remain PENDING.",
                  "contract": "resource_contract.json 5.4B-R1-draft", "tick_minutes": TICK,
                  "reference_selection_sha256": refs_sha,
                  "estimation": "pmi_core.estimation.engine.estimate_operation (Stage 5.3A, unchanged)"},
        "project": {"id": "HYP-DEMO-2Z", "start_local": START, "horizon_local": HORIZON, "timezone": TZ,
                    "concrete_specification": CONCRETE},
        "calendars": [{"calendar_id": c, "timezone": TZ,
                       "working_windows": [{"weekday": d, "start": a, "end": b} for d in WEEK for a, b in v["windows"]],
                       "date_exceptions": DATE_EXCEPTIONS, "input_state": HYP, "note": v["note"]}
                      for c, v in CALENDARS.items()],
        "activity_calendar_rule": "Intersection of PROJECT and the calendar of every resource the activity uses. No exceptions.",
        "resources": resources,
        "crew_modes": [{"mode_id": m, "units": u, "execution_mode": "simultaneous_fixed_crew", "input_state": HYP}
                       for m, u in MODES.items()],
        "supply": {"resource_id": "CONCRETE_SUPPLY", "product": CONCRETE, "rate_capacity_m3_h": 6,
                   "calendar_ref": "DELIVERY", "concurrent_with_placement": True,
                   "drawn_rate_m3_h_by_family": DRAW, "pump": "explicit none", "crane": "explicit none",
                   "placement_method": "Hypothetical direct chute discharge and manual placement."},
        "elements": q,
        "supports": SUPPORTS,
        "work_packages": [{"package_id": f"WP-{e}", "element_id": f"HYP-{e}", "family": r["family"],
                           "zone": r["zone"], "activities": [a["id"] for a in acts if a["element"] == e]}
                          for e, r in q.items()],
        "activities": acts, "dependencies": deps, "reservations": reservations,
        "split_policy": "All activities non_interruptible.",
        "holds": {"curing_hours": CURE_H, "striking_hours_from_pour": STRIKE_H,
                  "release_events": "hypothetical_pass_at_minimum (explicit, test only)"},
    }
    (DEMO / "fixture_inputs.json").write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    model = Model(acts, deps, reservations)
    cpm = model.cpm()
    lb, lb_stats = lower_bound(model)
    priority = lb["cpm"]["ls"]
    best, runs, deadlocks = None, 0, 0
    for seed in range(1200):
        rng = random.Random(seed) if seed else None
        rule = "earliest" if seed % 2 == 0 else "latest_start"
        out = sgs(model, priority, rng, noise=0 if seed < 2 else (60 if seed < 600 else 600), rule=rule)
        runs += 1
        if out is None:
            deadlocks += 1
            continue
        if best is None or out["span"] < best["span"]:
            best = dict(out, seed=seed, rule=rule)
    sched_cpm = {a: (stamp(cpm["es"][a]), stamp(cpm["ef"][a])) for a in model.ids}
    sched_rc = {a: (stamp(best["es"][a]), stamp(best["ef"][a])) for a in model.ids}
    checks_rc, conflicts_rc = check_schedule(fixture, sched_rc)
    checks_cpm, conflicts_cpm = check_schedule(fixture, sched_cpm)
    assert all(r["passed"] for r in checks_rc), [r for r in checks_rc if not r["passed"]][:5]
    assert not conflicts_rc

    cost = round(sum(a["cost_eur"] for a in acts), 6)
    cost_rows = sorted({(a["element"], a["work_item"], a["cost_eur"]) for a in acts if a["cost_eur"]})
    proven = best["span"] == lb["value"]
    write_csv("work_packages.csv", [{"package_id": p["package_id"], "element_id": p["element_id"], "family": p["family"],
                                     "zone": p["zone"], "activities": " ".join(p["activities"]),
                                     "cost_eur": round(sum(model.acts[a]["cost_eur"] for a in p["activities"]), 6)}
                                    for p in fixture["work_packages"]])
    write_csv("element_quantities.csv", [{"element": e, **{k: v for k, v in r.items() if k != "bounds_m"},
                                          "bounds_m": r["bounds_m"]} for e, r in q.items()])
    write_csv("activities.csv", [{k: a.get(k) for k in (
        "id", "package_id", "element", "zone", "work_item", "kind", "mode", "bcca_code", "quantity", "unit",
        "productive_hours", "duration_minutes", "demands", "worker_hours_by_trade", "machine_hours_by_class",
        "capacity_bounds_hours", "cost_eur", "calendars", "approval_ids", "input_state")}
        | {"scheduled_minutes": model.dur[a["id"]] * TICK} for a in acts])
    write_csv("dependencies.csv", deps)
    write_csv("reservations.csv", [{"reservation_id": r["reservation_id"], "resource_id": r["resource_id"],
                                    "quantity": r["quantity"], "element_ids": r["element_ids"],
                                    "start_event": f"{r['start_event']['activity_id']}.start",
                                    "release": f"{r['release_condition']['all_of'][0]['activity_id']}.finish",
                                    "return_lead_minutes": 0, "reshoring": "not_permitted",
                                    "occupancy_basis": r["occupancy_basis"]} for r in reservations])
    write_csv("cpm_schedule.csv", as_rows(model, cpm, "CPM (resources unconstrained)"))
    write_csv("resource_feasible_schedule.csv", as_rows(model, best, "capacity-feasible"))
    write_csv("cpm_resource_conflicts.csv", conflicts_cpm or [{"resource": "", "capacity": "", "peak_usage": "",
                                                                "holders": "", "start": "", "finish": ""}],
              ["resource", "capacity", "peak_usage", "start", "finish", "holders"])
    write_csv("resource_occupancy.csv", occupancy(model, best))
    write_csv("resource_utilization.csv", utilization(model, cpm, "CPM") + utilization(model, best, "capacity-feasible"))
    write_csv("feasibility_checks.csv", [dict(r, schedule="capacity-feasible") for r in checks_rc] +
              [dict(r, schedule="CPM") for r in checks_cpm if r["check"] == "capacity"])

    span_min = best["span"] * TICK
    expected = {
        "fixture": "HYPOTHETICAL SCHEDULING FIXTURE - not IFC-validated", "tick_minutes": TICK,
        "activities": len(acts), "dependencies": len(deps), "reservations": len(reservations),
        "work_packages": len(fixture["work_packages"]), "direct_reference_cost_eur": cost,
        "cost_identical_cpm_vs_capacity_feasible": True,
        "cpm": {"completion_local": stamp(cpm["span"]), "makespan_minutes": cpm["span"] * TICK,
                "resource_conflicts": len(conflicts_cpm),
                "resources_over_capacity": sorted({c["resource"] for c in conflicts_cpm}),
                "status": "precedence-and-calendar bound only; infeasible for declared capacities"},
        "capacity_feasible": {"completion_local": stamp(best["span"]), "makespan_minutes": span_min,
                              "status": "OPTIMAL (proven: equals lower bound)" if proven else
                                        "FEASIBLE (optimality not proven)",
                              "scheduler": "serial schedule generation, 1200 runs (earliest-start and latest-start priority rules, seeded noise)", "best_rule": best["rule"],
                              "runs": runs, "deadlocked_runs": deadlocks, "best_seed": best["seed"],
                              "independent_checks_passed": f"{sum(r['passed'] for r in checks_rc)}/{len(checks_rc)}"},
        "lower_bound": {"completion_local": stamp(lb["value"]), "makespan_minutes": lb["value"] * TICK,
                        "components_minutes": {k: v * TICK for k, v in lb["parts"].items()},
                        "binding_reservation_choice": lb["extra"], **lb_stats,
                        "gap_minutes": span_min - lb["value"] * TICK},
        "acceptance_criteria": [
            "Inputs: a solver consumes fixture_inputs.json unchanged; durations are ceil(duration_minutes / 5) ticks.",
            f"Feasibility: the returned schedule passes every check in feasibility_checks.csv semantics: calendars "
            f"(PROJECT intersected with each resource calendar), FS precedence, strike from pour finish, per-minute "
            f"capacity for working-time resources, continuous reservations from FORM start to STRIP finish.",
            f"Objective: makespan <= {span_min} min (completion <= {stamp(best['span'])}) and >= the lower bound "
            f"{lb['value'] * TICK} min.",
            ("The makespan must equal " + str(span_min) + " min; a solver must report OPTIMAL.") if proven else
            ("A solver reporting OPTIMAL must return a makespan in [" + str(lb["value"] * TICK) + ", " + str(span_min) +
             "] min; any lower value than the bound indicates a modelling error."),
            "CPM baseline: completion " + stamp(cpm["span"]) + " with conflicts on " +
            ", ".join(sorted({c['resource'] for c in conflicts_cpm})) + ".",
            f"Cost: total direct reference cost {cost} EUR is identical for CPM and capacity-feasible schedules.",
            "Approvals: every approval stays PENDING; real_project_eligible = false.",
        ],
        "runtime_seconds": None,
    }
    (DEMO / "lower_bound_proof.json").write_text(json.dumps({
        "method": "Relaxation that drops working-time capacities but keeps precedence, calendars and all reservation "
                  "constraints exactly. Reservation constraints are encoded as disjunctions: COL_FORM_SET (cap 2, "
                  "4 unit intervals) holds iff the intervals split into two chains; BEAM_FORM_SET (cap 3) and "
                  "BEAM_PROP (cap 9, demands 3+3+2+2) hold iff not all four beam intervals share a point, which for "
                  "intervals means some ordered pair is disjoint; SLAB_PROP (cap 10, 6+6) holds iff the slab intervals "
                  "are disjoint; SLAB_PANEL_SET (cap 2) never binds. For each choice the earliest-start CPM is the "
                  "exact relaxed optimum; it is strengthened by preemptive single-resource bounds for activities "
                  "that use the whole formwork crew, the whole reinforcement crew or the single inspector. The "
                  "lower bound is the minimum over all choices.",
        "best": {"value_minutes": lb["value"] * TICK, "completion_local": stamp(lb["value"]),
                 "components_minutes": {k: v * TICK for k, v in lb["parts"].items()},
                 "reservation_edges": lb["extra"]},
        **lb_stats, "upper_bound_minutes": span_min, "proven_optimal": proven}, indent=2) + "\n", encoding="utf-8")
    expected["runtime_seconds"] = round(clock.perf_counter() - t0, 2)
    (DEMO / "expected_results.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DEMO / "report.html").write_text(render_html(model, fixture, cpm, best, conflicts_cpm, expected), encoding="utf-8")
    print(json.dumps({k: expected[k] for k in ("cpm", "capacity_feasible", "lower_bound", "direct_reference_cost_eur",
                                                "runtime_seconds")}, indent=1, ensure_ascii=False))


# --------------------------------------------------------------------------- HTML
def render_html(model, fixture, cpm, best, conflicts, exp):
    span = max(cpm["span"], best["span"])
    # The axis starts at local midnight of the start date, so day gridlines and weekend shading
    # fall on calendar days, not on the 08:00 project start.
    day0 = datetime.fromisoformat(START[:10]).replace(tzinfo=ZONE)
    offset = ANCHOR - int(day0.timestamp() // 60)
    days = (offset + span * TICK) // 1440 + 2
    px_day, left, row_h = 150, 150, 30
    width = left + days * px_day
    x = lambda tick: left + (offset + tick * TICK) / 1440 * px_day
    elements = list(GEOM)
    kinds = {"productive": "var(--series-1)", "inspection": "var(--series-2)", "elapsed_hold": "var(--series-3)"}

    def grid(height):
        out = []
        for d in range(days):
            day = day0 + timedelta(days=d)
            if day.isoweekday() > 5:
                out.append(f'<rect x="{left + d * px_day}" y="0" width="{px_day}" height="{height}" fill="var(--surface-2)"/>')
            out.append(f'<line x1="{left + d * px_day}" x2="{left + d * px_day}" y1="0" y2="{height}" stroke="var(--grid)"/>')
        return "".join(out)

    def axis():
        cells = "".join(f'<text x="{left + d * px_day + 4}" y="14" class="ax">{(day0 + timedelta(days=d)):%a %d %b}</text>'
                        for d in range(days))
        return f'<svg width="{width}" height="20" role="presentation">{cells}</svg>'

    def gantt(sch, title):
        h = len(elements) * row_h + 6
        parts = [grid(h)]
        for i, e in enumerate(elements):
            y = i * row_h + 4
            parts.append(f'<text x="8" y="{y + 15}" class="lbl">{escape(e)} · {escape(GEOM[e][1])}</text>')
            for rv in model.res:
                if rv["element_ids"] == [f"HYP-{e}"] and rv["resource_id"].endswith("SET"):
                    s = sch["es"][rv["start_event"]["activity_id"]]
                    f = sch["ef"][rv["release_condition"]["all_of"][0]["activity_id"]]
                    tip = f"{rv['reservation_id']} {rv['resource_id']} reserved {stamp(s)} to {stamp(f)}"
                    parts.append(f'<rect class="hit" x="{x(s):.1f}" y="{y + 22}" width="{max(2, x(f) - x(s)):.1f}" height="3" '
                                 f'rx="1.5" fill="var(--text-muted)" data-tip="{escape(tip, True)}"/>')
            for a in model.ids:
                act = model.acts[a]
                if act["element"] != e:
                    continue
                s, f = sch["es"][a], sch["ef"][a]
                tip = f"{a} ({act['work_item']}) {stamp(s)} to {stamp(f)}"
                if act["kind"] == "elapsed_hold":
                    yy = y + (14 if a.endswith("CURE") else 18)
                    parts.append(f'<rect class="hit" x="{x(s):.1f}" y="{yy}" width="{max(2, x(f) - x(s)):.1f}" height="2" '
                                 f'fill="{kinds["elapsed_hold"]}" data-tip="{escape(tip, True)}"/>')
                else:
                    parts.append(f'<rect class="hit" x="{x(s):.1f}" y="{y + 2}" width="{max(3, x(f) - x(s)):.1f}" height="10" '
                                 f'rx="2" fill="{kinds[act["kind"]]}" stroke="var(--surface-1)" stroke-width="1" '
                                 f'data-tip="{escape(tip, True)}"/>')
        return (f'<h3>{escape(title)}</h3><svg width="{width}" height="{h}" role="img" '
                f'aria-label="{escape(title, True)}">{"".join(parts)}</svg>')

    def util(sch, label, overload):
        prof = profiles(model, sch)
        h_each, gap = 34, 8
        shown = [r for r, v in RESOURCES.items() if not v[5]]
        h = len(shown) * (h_each + gap)
        parts = [grid(h)]
        for i, r in enumerate(shown):
            cap = RESOURCES[r][2]
            top = i * (h_each + gap) + 4
            peak = max(max(prof[r]), cap)
            yv = lambda v: top + h_each - (v / peak) * (h_each - 4)
            pts, prev = [], None
            for t, v in enumerate(prof[r]):
                if v != prev:
                    pts.append((t, v))
                    prev = v
            path = f"M{x(0):.1f},{yv(0):.1f} " + " ".join(
                f"L{x(t):.1f},{yv(pv):.1f} L{x(t):.1f},{yv(v):.1f}" for (t, v), (_, pv) in zip(pts, [(0, 0)] + pts[:-1]))
            path += f" L{x(len(prof[r])):.1f},{yv(pts[-1][1]):.1f}"
            parts.append(f'<text x="8" y="{top + 14}" class="lbl">{escape(r)}</text>'
                         f'<text x="8" y="{top + 28}" class="sub">cap {cap} {escape(RESOURCES[r][1])}</text>')
            parts.append(f'<path d="{path} L{x(len(prof[r])):.1f},{yv(0):.1f} Z" fill="var(--series-1)" opacity="0.25"/>'
                         f'<path d="{path}" fill="none" stroke="var(--series-1)" stroke-width="1.5"/>')
            parts.append(f'<line x1="{left}" x2="{width}" y1="{yv(cap):.1f}" y2="{yv(cap):.1f}" stroke="var(--text-secondary)" '
                         f'stroke-dasharray="4 3"/>')
            if overload:
                run = None
                for t, v in enumerate(prof[r] + [0]):
                    if v > cap and run is None:
                        run = t
                    elif v <= cap and run is not None:
                        tip = f"{r}: over capacity {stamp(run)} to {stamp(t)}"
                        parts.append(f'<rect class="hit" x="{x(run):.1f}" y="{top}" width="{max(3, x(t) - x(run)):.1f}" '
                                     f'height="{h_each}" fill="var(--critical)" opacity="0.35" data-tip="{escape(tip, True)}"/>')
                        run = None
        return (f'<h3>{escape(label)}</h3><svg width="{width}" height="{h}" role="img" '
                f'aria-label="{escape(label, True)}">{"".join(parts)}</svg>')

    cf, cp, lbx = exp["capacity_feasible"], exp["cpm"], exp["lower_bound"]
    tiles = [("CPM completion", cp["completion_local"].replace("T", " ")[:16], f"{cp['makespan_minutes']:,} min, "
              f"{cp['resource_conflicts']} capacity conflicts"),
             ("Capacity-feasible completion", cf["completion_local"].replace("T", " ")[:16],
              f"{cf['makespan_minutes']:,} min · {cf['status']}"),
             ("Lower bound", lbx["completion_local"].replace("T", " ")[:16],
              f"{lbx['makespan_minutes']:,} min · gap {lbx['gap_minutes']:,} min"),
             ("Direct reference cost", f"€{exp['direct_reference_cost_eur']:,.2f}", "Identical in both schedules")]
    tile_html = "".join(f'<div class="tile"><div class="k">{escape(a)}</div><div class="v">{escape(b)}</div>'
                        f'<div class="s">{escape(c)}</div></div>' for a, b, c in tiles)
    legend = ('<div class="legend"><span><i style="background:var(--series-1)"></i>Productive</span>'
              '<span><i style="background:var(--series-2)"></i>Inspection</span>'
              '<span><i class="thin" style="background:var(--series-3)"></i>Curing (upper) / striking hold (lower)</span>'
              '<span><i class="thin" style="background:var(--text-muted)"></i>Formwork set reservation</span>'
              '<span><i style="background:var(--critical);opacity:.5"></i>Over capacity (CPM only)</span>'
              '<span><i class="dash"></i>Capacity</span><span><i style="background:var(--surface-2)"></i>Weekend</span></div>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Controlled resource demo</title>
<style>
:root{{color-scheme:light;--surface-1:#fcfcfb;--surface-2:#f0efec;--grid:#e4e3df;--text-primary:#0b0b0b;--text-secondary:#52514e;--text-muted:#8a8984;
--series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;--critical:#d03b3b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface-1:#1a1a19;--surface-2:#262624;--grid:#33332f;
--text-primary:#f0efec;--text-secondary:#c3c2b7;--text-muted:#8f8e86;--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--critical:#d03b3b}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface-1:#1a1a19;--surface-2:#262624;--grid:#33332f;--text-primary:#f0efec;--text-secondary:#c3c2b7;
--text-muted:#8f8e86;--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--critical:#d03b3b}}
body{{margin:0;padding:24px 16px;background:var(--surface-1);color:var(--text-primary);font:14px/1.45 system-ui,sans-serif}}
main{{max-width:1200px;margin:0 auto}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:28px 0 6px}} h3{{font-size:14px;margin:16px 0 4px;color:var(--text-secondary)}}
.note{{color:var(--text-secondary);max-width:70ch}} .tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:16px 0}}
.tile{{border:1px solid var(--grid);border-radius:8px;padding:12px}} .k{{color:var(--text-secondary);font-size:12px}} .v{{font-size:20px;font-weight:600;margin:2px 0}} .s{{color:var(--text-secondary);font-size:12px}}
.scroll{{overflow-x:auto;border:1px solid var(--grid);border-radius:8px;padding:4px 0}} svg text.lbl{{fill:var(--text-primary);font-size:12px}} svg text.sub,svg text.ax{{fill:var(--text-secondary);font-size:11px}}
.legend{{display:flex;flex-wrap:wrap;gap:14px;margin:8px 0;color:var(--text-secondary);font-size:12px}} .legend i{{display:inline-block;width:14px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}}
.legend i.thin{{height:3px}} .legend i.dash{{height:0;border-top:2px dashed var(--text-secondary);border-radius:0}}
#tip{{position:fixed;pointer-events:none;background:var(--surface-1);color:var(--text-primary);border:1px solid var(--grid);border-radius:6px;padding:6px 8px;font-size:12px;display:none;max-width:360px;box-shadow:0 2px 8px #0003}}
.hit{{cursor:default}} a{{color:var(--series-1)}}
</style></head><body><main>
<h1>Controlled resource demonstration</h1>
<p class="note">Hypothetical scheduling fixture, not an IFC-validated construction case: two zones, four columns, four beams and two slab sections. Durations and costs come from the Stage 5.3A estimator and the BCCA December 2023 references. Resource values are test inputs. All engineering approvals remain pending.</p>
<div class="tiles">{tile_html}</div>
<h2>Gantt comparison</h2>
<p class="note">Rows are elements, each with its zone. Both charts share one time axis; scroll sideways. Hover over a bar for its times. The CPM ignores capacities, so all four columns start together.</p>
{legend}
<div class="scroll">{axis()}{gantt(cpm, "CPM baseline (capacities not enforced)")}{gantt(best, "Capacity-feasible schedule")}</div>
<h2>Resource utilization</h2>
<p class="note">Each band shows units in use over time against the dashed capacity line. Reusable assets count continuously from FORM start to STRIP finish. Red shading marks CPM over-capacity.</p>
<div class="scroll">{axis()}{util(cpm, "CPM baseline", True)}{util(best, "Capacity-feasible schedule", False)}</div>
<h2>Tables</h2>
<p class="note">The data behind these charts: <a href="resource_feasible_schedule.csv">capacity-feasible schedule</a>, <a href="cpm_schedule.csv">CPM schedule</a>,
<a href="cpm_resource_conflicts.csv">CPM conflicts</a>, <a href="resource_occupancy.csv">occupancy intervals</a>, <a href="resource_utilization.csv">utilization</a>.</p>
</main><div id="tip" role="tooltip"></div>
<script>
const tip=document.getElementById('tip');
document.addEventListener('mousemove',e=>{{const t=e.target.closest('[data-tip]');if(!t){{tip.style.display='none';return}}
tip.textContent=t.getAttribute('data-tip');tip.style.display='block';tip.style.left=Math.min(e.clientX+12,innerWidth-370)+'px';tip.style.top=(e.clientY+12)+'px'}});
</script></body></html>
"""


if __name__ == "__main__":
    main()
