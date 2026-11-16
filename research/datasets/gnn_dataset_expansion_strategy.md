# GNN dataset expansion strategy

*Builds on [`../gnn/training_recommendation.md`](../gnn/training_recommendation.md) (the frozen Cambridge protocol) and on the 12 Nov 2026 dataset search.*

## Options evaluated

| # | Option | Assessment | Verdict |
|---|---|---|---|
| 1 | **Train on Cambridge alone** | 169 independent blocks; frozen split and protocol already exist; leakage controls designed. The label is reported (not verified) elapsed calendar days. | **Primary. Do this.** |
| 2 | Train on a new dataset alone | The only accessible candidate (e-verse P6) has ≲30 labelled independent jobs after grouping, with unclear rights. That is about Ghent's scale, which already gave a null result. | Not defensible as the main experiment |
| 3 | Pool compatible datasets | No candidate is *directly* compatible (A). e-verse differs in region, era, sector mix, label semantics (P6 status dates vs exported timestamps) and calendars. Ghent uses working time and genuine baselines. Pooling would mix label definitions and inflate apparent sample size. | **Rejected** for the primary analysis |
| 4 | Pretrain on Cambridge, fine-tune on a smaller higher-quality set | Defensible only if the fine-tuning set has enough independent projects for its own grouped held-out test (at least about 20 jobs). e-verse *might* qualify after grouping; that is unconfirmed. Fine-tuning and testing on the same few jobs would be uninformative. | **Optional, later.** Pre-register it only if the grouping count allows |
| 5 | Train on one dataset, validate externally on another | Cambridge-trained model applied to e-verse (and Ghent), each reported separately with a unit-aligned target. This tests transfer across countries, eras and recording practices without mixing labels. | **Recommended secondary** |

## Recommendation

**Option 1 + Option 5:**
1. Train and select models only on Cambridge, under the frozen Stage 2.3D protocol.
2. Report the locked Cambridge test blocks once.
3. Then evaluate the frozen model, unchanged, on:
   - the **e-verse P6** progressed schedules, after deduplication, grouping and a rights check;
   - optionally, **Ghent**.

Each is a separate external-validation table. No numbers are pooled.

**Alignment needed for external validation:**
- **Target:** compute e-verse elapsed **calendar** days as `act_end − act_start`, to match the Cambridge target. Report working days from the CALENDAR tables as a secondary check.
- **Features:** use only features available in both datasets: text, structure-only graph features, and a coarse project type mapped by hand and documented. No planned dates in the primary model, the same rule as for Cambridge.
- **Edges:** use predecessor → successor in both directions, as now. The e-verse relationship types and lags support a *later* edge-typed model variant, and it could be tested there first.

This does not guarantee better performance. What it adds is an honest test of whether anything learned from Cambridge transfers to independently sourced schedules with genuine dependency data.

## Answers to the research questions

1. **Best publicly accessible alternative to Cambridge:** the **e-verse `Buildings.Historical.Data`** P6 collection. It is real and downloadable, with genuine typed predecessors, lags, calendars and actual dates in about 30 progressed schedules. It has smaller scale and unclear rights. No public dataset matches Cambridge's size.
2. **Largest number of independent construction projects:**
   - At **activity level and accessible:** Cambridge itself (169 blocks).
   - **On request:** Montana DOT daily work reports (730 highway projects).
   - **Project or contract level:** NYC SCA (about 14,000 phase rows) and DoD FPDS (about 132,000 contracts). Neither supports the activity target.
3. **Most reliable actual-duration labels:** the **Montana DOT daily work reports**, which are daily inspector-recorded work-item records (restricted). Among accessible data, e-verse P6 status dates and Ghent tracking actuals are planner-reported. Cambridge's are reported and unverified.
4. **Genuine predecessor relationships:**
   - **e-verse P6:** `TASKPRED` with FS/SS/FF/SF and lags, verified.
   - Nodes & Links (P6, unverified fields) and UNSW (MS Project program links, 6 projects).
   - Ghent and Cambridge, as exported.
   - SCHEPENDOMLAAN: sparse.
5. **Can any be combined with Cambridge?** None directly (category A).
   - e-verse and Nodes & Links: **B/C**, external validation or later transfer learning.
   - Ghent and UNSW: **C**.
   - NYC, DoD and the transportation-department daily reports: **D** for the activity-level GNN target.
6. **Can new data improve scientific validity?** Yes, through **external validation** on independently sourced schedules with genuine dependencies. That shows whether results generalise beyond one UK source. It cannot be claimed to improve accuracy, and pooling would *reduce* validity by mixing label definitions.
7. **Three datasets to prioritise obtaining:**
   1. **e-verse P6:** the full 222 MB download, plus rights clarification (contact e-verse and the blog owner; or limit use to internal research).
   2. **Nodes & Links / Vazquez–Ellinas:** a formal academic data request (77 projects, P6 networks).
   3. **Montana DOT daily work reports:** a request to MDT Research Programs, as a label-quality comparison study.
8. **Exact next steps before training:**
   1. **Approve the full e-verse download** (222 MB) to `data/raw/everse_p6/`, outside any frozen manifests, and record its SHA-256.
   2. **Rights check:** document the provenance gap and decide on internal-only use. Ask e-verse about the source permissions.
   3. **Build an e-verse loader** with tests. It should parse TASK, TASKPRED, CALENDAR and PROJECT, compute calendar and working elapsed days for completed tasks, and flag the `target_*` revision risk.
   4. **Deduplicate and group:** cluster the 70 folders into independent jobs (baseline / update / recovery / copy share a group) by name, project code, dates and task-name overlap. Report the count of independent labelled jobs. If it is below about 20, use e-verse for external validation only (option 4 is off).
   5. **Overlap check against Cambridge and Ghent:** compare task-name sets, project codes and dates. They are expected to be disjoint (UK and BE vs Egypt/ME), but this must be confirmed.
   6. **Restore and verify the Cambridge raw JSON** against its frozen digest, and write the Cambridge loader. These are the existing Stage 3.7B gates.
   7. **Pre-register** the primary Cambridge experiment and the e-verse/Ghent external-validation protocol, with the target alignment and success criteria, **before** any training.
   8. Send the Nodes & Links and Montana data requests in parallel. They are not on the critical path.

**If the rights check fails or grouping leaves too few jobs:** proceed with **Cambridge alone** under its existing limitations, keeping Ghent as the external comparison.
