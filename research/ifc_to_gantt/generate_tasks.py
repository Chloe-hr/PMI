"""
Stage 3.2 - Elements -> construction tasks + dependencies   (deterministic, rule-based)
======================================================================================
    elements.csv  --(task_rules.json: classification)-->  one task per (work package, storey)
                  --(task_rules.json: packages)------->   finish-to-start dependencies
                  --(rate per element)---------------->   duration = max(min_days, ceil(sum qty/rate))

Outputs (same folder as --out):
    tasks.csv               id, package, name, phase, storey, n_elements, work_days, duration_days, rule, flags
    task_element_links.csv  task_id, source_id, ifc_class, basis, quantity, work_days, flag
    dependencies.csv        predecessor, successor, type (FS), lag_days, reason
    unclassified.csv        elements no rule matched (review these - they are NOT scheduled)

The durations are ASSUMED productivity rates; this stage's job is a correct, explainable task
network. The GNN (Stage 3.5) will later replace `work_days` with learned estimates.

    python research/ifc_to_gantt/generate_tasks.py outputs/v1/elements.csv outputs/v1
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RULES = HERE / "task_rules.json"


def load_rules(path: Path = RULES) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(s)).upper() or "NOSTOREY"


def _has(v) -> bool:
    return isinstance(v, str) and v != "" or (v is not None and not (isinstance(v, float) and math.isnan(v)) and v != "")


def classify(el: dict, rules: list) -> dict | None:
    """First matching classification rule, or None."""
    mats = str(el.get("materials") or "").lower()
    for r in rules:
        if "ifc_class" in r and el["ifc_class"] not in r["ifc_class"]:
            continue
        if "materials_any" in r and not any(m.lower() in mats for m in r["materials_any"]):
            continue
        if "materials_none" in r and any(m.lower() in mats for m in r["materials_none"]):
            continue
        if "has_parent" in r and _has(el.get("parent_id")) != r["has_parent"]:
            continue
        return r
    return None


def element_work(el: dict, rule: dict, missing_days: float) -> tuple[float, float, str]:
    """(quantity, crew-days, flag) for one element."""
    basis = rule["basis"]
    if basis == "none":
        return 0.0, 0.0, "component"
    if basis == "count":
        return 1.0, 1.0 / rule["rate"], ""
    q = el.get(basis)
    if q is None or (isinstance(q, float) and math.isnan(q)) or q <= 0:
        return 0.0, missing_days, f"missing {basis} -> {missing_days} d assumed"
    return float(q), float(q) / rule["rate"], ""


def generate(elements: pd.DataFrame, rules: dict | None = None):
    rules = rules or load_rules()
    pk = rules["packages"]
    missing = float(rules.get("missing_quantity_days", 0.5))

    # storey order by elevation (lowest first)
    st = (elements.groupby("storey")["storey_elevation"].min().sort_values())
    storeys = list(st.index)

    links, unclassified = [], []
    for el in elements.to_dict("records"):
        r = classify(el, rules["classification"])
        if r is None:
            unclassified.append(el)
            continue
        q, wd, flag = element_work(el, r, missing)
        links.append({"task_id": f"{r['package']}-{slug(el['storey'])}", "package": r["package"],
                      "storey": el["storey"], "source_id": el["source_id"], "ifc_class": el["ifc_class"],
                      "name": el["name"], "basis": r["basis"], "quantity": round(q, 3),
                      "rate": r.get("rate"), "work_days": round(wd, 3), "flag": flag})
    links = pd.DataFrame(links)

    # ---- tasks ---------------------------------------------------------------
    tasks = []
    if not links.empty:
        for (tid, p, s), g in links.groupby(["task_id", "package", "storey"], sort=False):
            spec = pk[p]
            wd = g["work_days"].sum()
            d = max(int(spec.get("min_days", 1)), math.ceil(round(wd, 6)))
            qty = "; ".join(f"{g.loc[g.basis == b, 'quantity'].sum():.1f} {b}" if b != "count"
                            else f"{int((g.basis == b).sum())} pcs" for b in g["basis"].unique() if b != "none")
            flags = "; ".join(sorted(set(f for f in g["flag"] if f and f != "component")))
            tasks.append({"id": tid, "package": p, "name": f"{spec['name']} - {s}", "phase": spec["phase"],
                          "storey": s, "storey_rank": storeys.index(s), "n_elements": len(g),
                          "quantities": qty, "work_days": round(wd, 2), "duration_days": d,
                          "rule": f"max({spec.get('min_days', 1)}, ceil({wd:.2f} crew-days))", "flags": flags})
    for p, spec in pk.items():
        if "fixed_days" in spec:
            tasks.append({"id": p, "package": p, "name": spec["name"], "phase": spec["phase"], "storey": "",
                          "storey_rank": -1 if not spec.get("after_all") else len(storeys), "n_elements": 0,
                          "quantities": "", "work_days": spec["fixed_days"], "duration_days": spec["fixed_days"],
                          "rule": f"fixed {spec['fixed_days']}", "flags": ""})
    tasks = pd.DataFrame(tasks)

    # ---- dependencies --------------------------------------------------------
    by_key = {(t.package, t.storey): t.id for t in tasks.itertuples() if t.storey}
    deps = []

    def add(pred, succ, reason):
        if pred != succ and not any(d["predecessor"] == pred and d["successor"] == succ for d in deps):
            deps.append({"predecessor": pred, "successor": succ, "type": "FS", "lag_days": 0, "reason": reason})

    for t in tasks.itertuples():
        spec = pk[t.package]
        for q in spec.get("global", []):
            for o in tasks.itertuples():
                if o.package == q:
                    add(o.id, t.id, f"{pk[q]['name']} must be complete first")
        if not t.storey:
            continue
        k = storeys.index(t.storey)
        for q in spec.get("same", []):
            if (q, t.storey) in by_key:
                add(by_key[(q, t.storey)], t.id, f"same storey: {pk[q]['name']} before {spec['name']}")
        for q in spec.get("below", []):
            for j in range(k - 1, -1, -1):
                if (q, storeys[j]) in by_key:
                    add(by_key[(q, storeys[j])], t.id, f"storey below ({storeys[j]}): {pk[q]['name']}")
                    break
    # tasks with no predecessor start after mobilisation; handover after every sink
    if "MOB" in set(tasks["id"]):
        succ_set = {d["successor"] for d in deps}
        for t in tasks.itertuples():
            if t.id not in ("MOB",) and not pk[t.package].get("after_all") and t.id not in succ_set:
                add("MOB", t.id, "start after site mobilisation")
    for p, spec in pk.items():
        if spec.get("after_all") and p in set(tasks["id"]):
            pred_set = {d["predecessor"] for d in deps}
            for t in tasks.itertuples():
                if t.id != p and t.id not in pred_set:
                    add(t.id, p, "all construction complete before handover")
    deps = pd.DataFrame(deps, columns=["predecessor", "successor", "type", "lag_days", "reason"])

    preds = deps.groupby("successor")["predecessor"].apply(lambda s: ";".join(s))
    tasks["predecessors"] = tasks["id"].map(preds).fillna("")
    tasks = tasks.sort_values(["storey_rank", "id"]).reset_index(drop=True)
    return tasks, links, deps, pd.DataFrame(unclassified)


def write(out: Path, tasks, links, deps, unclassified):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tasks.to_csv(out / "tasks.csv", index=False)
    links.to_csv(out / "task_element_links.csv", index=False)
    deps.to_csv(out / "dependencies.csv", index=False)
    unclassified.to_csv(out / "unclassified.csv", index=False)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print(__doc__)
        return 1
    el = pd.read_csv(argv[0])
    tasks, links, deps, unc = generate(el)
    write(Path(argv[1]), tasks, links, deps, unc)
    print(tasks[["id", "name", "n_elements", "quantities", "duration_days", "predecessors"]].to_string(index=False))
    print(f"\n{len(tasks)} tasks, {len(links)} element links, {len(deps)} dependencies, {len(unc)} unclassified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
