"""Build and check proposed dependency graphs without computing durations."""

from collections import defaultdict, deque


def dependency_issues(activity_ids, edges):
    """Return invalid endpoints, competing relationships and directed cycles."""
    nodes = set(activity_ids)
    successors = defaultdict(set)
    indegree = dict.fromkeys(nodes, 0)
    relations = defaultdict(set)
    issues = []
    for edge in edges:
        if edge["state"] == "conditional":
            continue
        start, finish, relation = edge["predecessor_id"], edge["successor_id"], edge["relation"]
        if start not in nodes or finish not in nodes or relation not in {"FS", "SS", "FF", "SF"}:
            issues.append({"code": "INVALID_DEPENDENCY", "activity_ids": [start, finish]})
            continue
        relations[start, finish].add(relation)
        if finish not in successors[start]:
            successors[start].add(finish)
            indegree[finish] += 1
    for pair, modes in sorted(relations.items()):
        if len(modes) > 1:
            issues.append({"code": "CONFLICTING_RELATIONSHIPS", "activity_ids": list(pair)})
    ready = deque(sorted(node for node, count in indegree.items() if count == 0))
    while ready:
        for successor in sorted(successors[ready.popleft()]):
            indegree[successor] -= 1
            if not indegree[successor]:
                ready.append(successor)
    unresolved = sorted(node for node, count in indegree.items() if count)
    if unresolved:
        issues.append({"code": "DEPENDENCY_CYCLE", "activity_ids": unresolved})
    return issues


def package_dependencies(activities, family, library, sequence, slab_on_grade):
    """Materialize the library's local precedence rules for one work package."""
    edges = []

    def add(start, finish, rule_id, *, relation="FS", state="proposed", condition=None, option=None):
        rule = library.tables["dependencies"][rule_id]
        edges.append({
            "predecessor_id": activities[start], "successor_id": activities[finish],
            "relation": relation, "rule_id": rule_id, "state": state, "option": option,
            "condition": condition or rule["lag_or_condition"], "lag": None,
        })

    if family == "COL":
        alternatives = (("cage_first", "FS"), ("overlap", "SS"))
        for option, relation in alternatives:
            add("rebar", "form", "DR05", relation=relation, option=option,
                state="proposed" if sequence == option else "conditional",
                condition="Approved column cage and formwork sequence")
    elif slab_on_grade is not True:
        add("form", "rebar", "DR06", option="formwork_first",
            state="proposed" if sequence == "formwork_first" else "conditional",
            condition="Approved soffit-first method")
    add("rebar", "place", "DR06")
    if slab_on_grade is not True:
        add("form", "place", "DR06", state="conditional" if family == "SLAB" and slab_on_grade is None else "proposed",
            condition="Formwork applies and inspection is complete")
    add("place", "cure", "DR07")
    if slab_on_grade is not True:
        add("cure", "strip", "DR08", state="conditional" if family == "SLAB" and slab_on_grade is None else "proposed")
    return edges
