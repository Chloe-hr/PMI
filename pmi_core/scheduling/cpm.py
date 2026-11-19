"""Calendar-aware CPM with resource diagnostics and an FS-only relation model."""

from collections import defaultdict
from heapq import heapify, heappop, heappush
from zoneinfo import ZoneInfo

from .calendar import SchedulingError, build_windows, display, fit_work, parse_minute, round_duration


def _order(ids, successors, incoming):
    counts = {key: len(incoming[key]) for key in ids}
    queue = [key for key in ids if not counts[key]]
    heapify(queue)
    order = []
    while queue:
        key = heappop(queue)
        order.append(key)
        for link in successors[key]:
            target = link["successor_id"]
            counts[target] -= 1
            if not counts[target]:
                heappush(queue, target)
    if len(order) != len(ids):
        unresolved = set(ids) - set(order)
        # Walk unresolved predecessors until a vertex repeats. These edges lead into a cycle.
        trail, indices = [], {}
        key = min(unresolved)
        while key not in indices:
            indices[key] = len(trail)
            trail.append(key)
            key = min(edge["predecessor_id"] for edge in incoming[key]
                      if edge["predecessor_id"] in unresolved)
        cycle = list(reversed(trail[indices[key]:] + [key]))
        raise SchedulingError("CYCLE", "Dependency graph contains a directed cycle.", activity_ids=cycle)
    return order


def _resource_report(tasks, slots, capacities, stamp):
    events = defaultdict(lambda: defaultdict(int))
    for key, segments in slots.items():
        for name, count in tasks[key].get("resources", {}).items():
            for start, end in segments:
                events[name][start] += count
                events[name][end] -= count
    conflicts = []
    for name, changes in sorted(events.items()):
        current = 0
        timestamps = sorted(changes)
        for a, b in zip(timestamps, timestamps[1:]):
            current += changes[a]
            if current > capacities[name]:
                ids = sorted(key for key, segments in slots.items() if tasks[key].get("resources", {}).get(name)
                             and any(lo <= a < hi for lo, hi in segments))
                conflicts.append({"resource": name, "capacity": capacities[name], "usage": current,
                                  "start": stamp(a), "finish": stamp(b), "activity_ids": ids})
    return conflicts


def calculate(tasks, dependencies, calendar, *, start, horizon, tick=15,
              capacities=None, deadlines=None, release_events=None):
    """Return deterministic early and late bounds for a bounded set of FS activities."""
    capacities, deadlines, release_events = capacities or {}, deadlines or {}, release_events or {}
    zone = ZoneInfo(calendar["timezone"])
    round_duration(0, tick)
    anchor = parse_minute(start, zone, tick)
    limit = parse_minute(horizon, zone, tick, upper=True)
    if limit <= anchor or not tasks:
        raise ValueError("Provide activities and a horizon after project start.")
    indexed = {row["id"]: row for row in tasks}
    if len(indexed) != len(tasks) or not all(indexed):
        raise ValueError("Activity identifiers must be unique and nonempty.")
    unknown = deadlines.keys() - indexed.keys()
    if unknown:
        raise ValueError(f"Unknown deadline endpoints: {sorted(unknown)}")
    durations, windows, calendar_cache = {}, {}, {}
    incoming, successors = defaultdict(list), defaultdict(list)
    for key, row in indexed.items():
        duration = round_duration(row["duration_minutes"], tick)
        kind = row["kind"]
        if kind not in {"productive", "inspection", "elapsed_hold", "strength_release", "milestone"}:
            raise ValueError(f"Unsupported activity kind: {kind}")
        if (kind == "milestone" and duration != 0) or (kind != "milestone" and duration == 0):
            raise ValueError(f"Invalid duration for {key} ({kind}).")
        durations[key] = duration
        if kind in {"productive", "inspection"}:
            if row.get("interruption", "non_interruptible") not in {"non_interruptible", "split_allowed"}:
                raise ValueError(f"Unsupported interruption policy for {key}.")
            allowed = row.get("allowed_hours")
            pattern = tuple(tuple(pair) for pair in allowed) if allowed is not None else None
            if pattern not in calendar_cache:
                calendar_cache[pattern] = build_windows(calendar, anchor, limit, tick, allowed)
            windows[key] = calendar_cache[pattern]
        elif row.get("resources"):
            raise ValueError(f"Elapsed activities and milestones cannot reserve resources: {key}.")
        for name, demand in row.get("resources", {}).items():
            capacity = capacities.get(name)
            if type(demand) is not int or demand <= 0:
                raise ValueError(f"Invalid resource demand for {key}: {name}.")
            if capacity is None:
                raise SchedulingError("MISSING_INPUT", f"Missing capacity for {name}.", activity_id=key)
            if type(capacity) is not int or capacity < demand:
                raise SchedulingError("IMPOSSIBLE_CREW", f"Capacity for {name} cannot cover {key}.", activity_id=key)

    edge_keys = set()
    for edge in dependencies:
        left, right = edge["predecessor_id"], edge["successor_id"]
        if left not in indexed or right not in indexed:
            raise SchedulingError("MISSING_ENDPOINT", "Dependency has an unknown endpoint.", endpoints=[left, right])
        if (left, right) in edge_keys:
            raise SchedulingError("CONFLICTING_RELATIONSHIPS", "Multiple edges connect the same endpoints.",
                                  endpoints=[left, right])
        if edge["relation"] != "FS" or edge["lag_basis"] not in {"working", "elapsed"}:
            raise SchedulingError("UNSUPPORTED_RELATION", "CPM supports FS with explicit working or elapsed lag bases.")
        edge_keys.add((left, right))
        link = {**edge, "scheduled_lag_minutes": round_duration(edge["lag_minutes"], tick)}
        incoming[right].append(link)
        successors[left].append(link)
    order = _order(indexed, successors, incoming)
    base_windows = calendar_cache.get(None)
    if base_windows is None:
        base_windows = build_windows(calendar, anchor, limit, tick)

    def lag(bound, link, backward=False):
        minutes = link["scheduled_lag_minutes"]
        if not minutes or link["lag_basis"] == "elapsed":
            return bound + (-minutes if backward else minutes)
        fit = fit_work(base_windows, bound, minutes, split=True, backward=backward)
        return fit[0][0] if backward else fit[-1][1]

    def fit(key, bound, backward=False):
        duration = durations[key]
        if key not in windows:
            return [(bound - duration, bound)] if backward else [(bound, bound + duration)]
        return fit_work(windows[key], bound, duration, backward=backward,
                        split=indexed[key].get("interruption") == "split_allowed")

    early, late, slots, ready, conditions, conditional = {}, {}, {}, {}, {}, set()
    stamp = lambda minute: display(minute, zone)
    for key in order:
        links = incoming[key]
        bound = max([anchor, *(lag(early[edge["predecessor_id"]][1], edge) for edge in links)])
        row = indexed[key]
        if row.get("not_before"):
            bound = max(bound, parse_minute(row["not_before"], zone, tick))
        if any(edge["predecessor_id"] in conditional for edge in links):
            conditional.add(key)
        release_minute = None
        event_id = row.get("release_event_id")
        if event_id:
            event = release_events.get(event_id, {})
            event_status = event.get("status")
            if event_status == "hypothetical_pass_at_minimum":
                conditions[key] = event_status
            elif event_status in {"recorded_pass", "hypothetical_recorded_pass"} and event.get("at"):
                release_minute = parse_minute(event["at"], zone, tick)
                conditions[key] = event_status
            elif event_status == "failed":
                raise SchedulingError("RELEASE_FAILED", f"Strength release failed: {event_id}.", activity_id=key)
            else:
                conditions[key] = "missing"
                conditional.add(key)
        ready[key] = bound
        try:
            segments = fit(key, bound)
        except SchedulingError as exc:
            exc.details.setdefault("activity_id", key)
            raise
        early[key] = segments[0][0], segments[-1][1]
        if release_minute is not None:
            early[key] = early[key][0], max(early[key][1], release_minute)
        if early[key][1] > limit:
            raise SchedulingError("HORIZON_EXHAUSTED", "Activity exceeds scheduling horizon.", activity_id=key)
        if key in deadlines and early[key][1] > parse_minute(deadlines[key], zone, tick, upper=True):
            ancestor, pending = set(), [key]
            while pending:
                node = pending.pop()
                if node not in ancestor:
                    ancestor.add(node)
                    pending.extend(edge["predecessor_id"] for edge in incoming[node])
            raise SchedulingError("INFEASIBLE_DEADLINE", f"Earliest finish exceeds deadline for {key}.",
                                  activity_id=key, earliest_finish=stamp(early[key][1]), deadline=deadlines[key],
                                  ancestor_ids=sorted(ancestor))
        if key in windows:
            slots[key] = segments

    completion = max(finish for _, finish in early.values())
    free = {}
    for key in reversed(order):
        finish_limit = min([completion, *(lag(late[edge["successor_id"]][0], edge, True)
                                          for edge in successors[key])])
        if key in deadlines:
            finish_limit = min(finish_limit, parse_minute(deadlines[key], zone, tick, upper=True))
        segments = fit(key, finish_limit, True)
        late[key] = segments[0][0], segments[-1][1]
        free_limit = min([finish_limit, *(lag(early[edge["successor_id"]][0], edge, True)
                                          for edge in successors[key])])
        free[key] = fit(key, free_limit, True)[0][0] - early[key][0]
        if late[key][0] < early[key][0] or free[key] < 0:
            raise RuntimeError(f"Inconsistent calendar backward bound for {key}.")

    rows = []
    for key in order:
        a, b = early[key]
        c, d = late[key]
        rows.append({
            **indexed[key], "scheduled_minutes": durations[key], "rounding_minutes": durations[key] - indexed[key]["duration_minutes"],
            "earliest_start": stamp(a), "earliest_finish": stamp(b),
            "latest_start": stamp(c), "latest_finish": stamp(d), "total_float_minutes": c - a,
            "free_float_minutes": free[key], "critical": c == a,
            "calendar_delay_minutes": (a - ready[key] + b - a - durations[key]) if key in slots else 0,
            "segments": [[stamp(x), stamp(y)] for x, y in slots.get(key, [(a, b)])],
            "release_status": conditions.get(key), "conditional": key in conditional,
            "release_wait_minutes": b - a - durations[key] if key in conditions else 0,
        })
    critical = {row["id"] for row in rows if row["critical"]}
    critical_edges = []
    for links in successors.values():
        for edge in links:
            a, b = edge["predecessor_id"], edge["successor_id"]
            if a not in critical or b not in critical:
                continue
            arrival = lag(early[a][1], edge)
            if arrival == ready[b]:
                critical_edges.append({**edge, "calendar_gap_minutes": early[b][0] - arrival})
    return {
        "status": "conditional" if conditional else "calculated",
        "project_start": stamp(anchor), "project_completion": stamp(completion),
        "makespan_elapsed_minutes": completion - anchor, "tick_minutes": tick, "activities": rows,
        "critical_activity_ids": [key for key in order if key in critical], "critical_edges": critical_edges,
        "resource_conflicts": _resource_report(indexed, slots, capacities, stamp),
        "resource_constraints_enforced": False,
    }
