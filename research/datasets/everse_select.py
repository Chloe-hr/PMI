"""
Select the usable e-verse Primavera P6 schedules and copy only what PMI uses into data/raw/everse_p6/.

Source : https://github.com/EverseDevelopment/Buildings.Historical.Data (commit 862936fe, 2024-06-14)
         P6 schedules converted to CSV tables by e-verse from a 2019 blog post; original owners unknown.
Usage  : git clone --depth 1 https://github.com/EverseDevelopment/Buildings.Historical.Data.git <clone>
         python research/datasets/everse_select.py <clone>

Selection rule (declared before any modelling):
  1. A schedule is LABELLED if it has >= MIN_COMPLETED non-milestone, non-WBS/LOE tasks with both
     act_start_date and act_end_date. Baseline-only schedules (0 actuals) are not used.
  2. Revisions of the same job form one GROUP (JOB_GROUPS, assigned from shared project codes, folder
     names and task-name overlap measured in the profiling step - see README in the output folder).
     Per group, keep the single schedule with the most completed tasks (ties: latest data date).
     Revisions are never counted as independent projects.
  3. Exclusions: test files (EXCLUDE).
Kept tables: the ones PMI needs for graphs, labels, calendars and trade context. Everything else
(resources, costs, memos, issues, rates) is not copied.
Outputs in data/raw/everse_p6/: <job>/<TABLE>.csv, manifest.csv (sha256 of every kept file),
selection.csv (all 70 schedules with decision and reason), SOURCE_README.md / SOURCE_LICENSE (from source).
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "everse_p6"
MIN_COMPLETED = 10
KEEP_TABLES = ["TASK", "TASKPRED", "CALENDAR", "PROJECT", "PROJWBS", "ACTVTYPE", "ACTVCODE", "TASKACTV"]

# Revisions of one job -> one group. Evidence: same proj_short_name/code, folder names, task-name overlap.
JOB_GROUPS = {
    "4229-enppi-helal": ["hela-2l", "helal", "MERGE PROJECTS", "Enppi", "PJ"],          # code 4229 / Master Rev.F-N-4; 82-99% shared names
    "R29BT": ["129 trial", "130 TRIAL"],                                                   # R29BT-modefied-10 / -7
    "jungle": ["update of jungle 20-07-2010", "baseline of jungle", "jungle recovery plan"],
    "medor": ["Update 01-09-2010", "medor_003", "schedule of Medor"],                       # M.D / M.D_final; 90-100% shared names
    "jumaira": ["jumaira", "jumaira2"],                                                    # folder names; different P6 codes - conservative
    "rehab": ["rehab-2", "phase 8", "V30", "v 30"],                                        # R111 / RHAB / V30, unnamed tasks - conservative
}
EXCLUDE = {"trial for me": "test file named 'trial', no task names"}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def profile(folder: Path) -> dict:
    t = pd.read_csv(folder / "TASK.csv", low_memory=False, encoding_errors="replace")
    p = pd.read_csv(folder / "PROJECT.csv", low_memory=False, encoding_errors="replace")
    work = t[~t["task_type"].isin(["TT_WBS", "TT_LOE", "TT_Mile", "TT_FinMile"])]
    done = work[work["act_start_date"].notna() & work["act_end_date"].notna()]
    named = work["task_name"].dropna().astype(str).str.strip()
    return {"folder": folder.name, "proj_short_name": p["proj_short_name"].iloc[0] if len(p) else "",
            "data_date": str(p["last_recalc_date"].iloc[0])[:10] if len(p) else "",
            "work_tasks": len(work), "completed": len(done),
            "named_share": round(float((named.str.len() > 2).mean()) if len(named) else 0.0, 3)}


def main(clone: Path) -> int:
    data = clone / "Buildings Data"
    commit = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    folders = sorted(p for p in data.iterdir() if p.is_dir() and (p / "TASK.csv").is_file())
    prof = pd.DataFrame([profile(f) for f in folders])
    group_of = {f: g for g, fs in JOB_GROUPS.items() for f in fs}
    prof["group"] = prof["folder"].map(lambda f: group_of.get(f, f))

    prof["decision"], prof["reason"] = "removed", ""
    for i, r in prof.iterrows():
        if r.folder in EXCLUDE:
            prof.loc[i, "reason"] = EXCLUDE[r.folder]
        elif r.completed < MIN_COMPLETED:
            prof.loc[i, "reason"] = f"{r.completed} completed tasks (< {MIN_COMPLETED}): baseline/unprogressed"
    cand = prof[prof.reason == ""]
    for g, sub in cand.groupby("group"):
        best = sub.sort_values(["completed", "data_date"], ascending=False).index[0]
        prof.loc[best, "decision"] = "kept"
        for i in sub.index.drop(best):
            prof.loc[i, "reason"] = f"revision of job '{g}' - kept '{prof.loc[best, 'folder']}' (more actuals)"
    prof.loc[prof.decision == "kept", "reason"] = "labelled; one schedule per job"

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    manifest = []
    for r in prof[prof.decision == "kept"].itertuples():
        dest = OUT / r.group
        dest.mkdir()
        for t in KEEP_TABLES:
            src = data / r.folder / f"{t}.csv"
            if src.is_file():
                shutil.copy2(src, dest / src.name)
                manifest.append({"job": r.group, "source_folder": r.folder, "file": f"{r.group}/{src.name}",
                                 "bytes": src.stat().st_size, "sha256": sha256(src), "source_commit": commit})
    for name, target in (("README.md", "SOURCE_README.md"), ("LICENSE", "SOURCE_LICENSE")):
        if (clone / name).is_file():
            shutil.copy2(clone / name, OUT / target)
    pd.DataFrame(manifest).to_csv(OUT / "manifest.csv", index=False)
    prof.assign(source_commit=commit).to_csv(OUT / "selection.csv", index=False)

    kept = prof[prof.decision == "kept"]
    print(kept[["group", "folder", "proj_short_name", "work_tasks", "completed", "named_share"]].to_string(index=False))
    print(f"\nkept {len(kept)} independent labelled jobs / {len(prof)} schedules; "
          f"{int(kept.completed.sum())} completed tasks; {len(manifest)} files, "
          f"{sum(m['bytes'] for m in manifest) / 1e6:.1f} MB -> {OUT}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    raise SystemExit(main(Path(sys.argv[1])))
