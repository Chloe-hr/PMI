# Datasets comparable to Cambridge: ranked shortlist

*Research date: 12 Nov 2026. All candidates are listed in [`cambridge_alternative_inventory.csv`](cambridge_alternative_inventory.csv): 26 rows, comprising 2 references, 10 shortlisted candidates and 14 excluded items, with per-criterion scores. Nothing was trained and no repository data was modified.*

**Scoring:** reliable duration labels 25, independent projects 20, explicit dependencies 20, descriptions/trades 15, compatibility with Cambridge 10, accessibility 10. Each criterion was rated from 0 to 1 and multiplied by its weight.

**Reference points** (not new candidates): Cambridge **83** · Ghent/DSLIB **64**.

> **Headline:** no publicly downloadable dataset matches Cambridge's scale of activity-level schedules with actual dates.
> - The two candidates that score above Ghent (nPlan, Nodes & Links) are **not openly accessible**.
> - The best **public** find, the e-verse P6 collection (65), is smaller and has unclear rights. Its value is what Cambridge lacks: genuine typed dependencies, lags and calendars.

The ranking is by score. The restrictions in the brief still apply: datasets with no activity-level labels or no access can't be recommended for the current supervised target, whatever their score.

---

### 1. nPlan schedule corpus: 76.5 (Verified, access restricted, commercial)
- **Source:** [nplan.io](https://www.nplan.io/); Zachares et al., *On Forecasting Project Activity Durations with Neural Networks*, EANN 2022. **Download:** none.
- **Projects / activities:** the company claims 750,000–780,000+ schedules; activity counts are not published.
- **Features / labels / graph:** real schedules with networks, according to the company. Fields are not publicly documented.
- **Cambridge compatibility:** B (in principle).
- **Limitations:** proprietary, with no academic release programme found. Context only; not obtainable.

### 2. Nodes & Links / Vazquez–Ellinas collection: 67.5 (Verified, access on request)
- **Source:** [arXiv 2207.04688](https://arxiv.org/abs/2207.04688) (77 projects, 323 schedule versions); [arXiv 2304.10304](https://arxiv.org/abs/2304.10304) (180 schedules); arXiv 2312.12906 (118 projects with ≥1,000 activities). **Download:** none; raw data reportedly *"provided upon consultation"*. That availability wording comes from a search summary; the arXiv abstract pages have no statement.
- **Features:** Oracle Primavera P6 schedules with multiple updates per project.
- **Labels:** unknown until accessed. **Graph:** genuine P6 activity networks.
- **Cambridge compatibility:** B.
- **Limitations:** the papers probably share one database, so count it once. Country, sector and fields are undocumented. Worth a **formal data request**.

### 3. e-verse `Buildings.Historical.Data`, 70 P6 schedules: 65.2 (Verified and downloadable) ← best public option
- **Source / download:** <https://github.com/EverseDevelopment/Buildings.Historical.Data>, 222 MB uncompressed. Primavera tables exported to CSV per project: TASK, TASKPRED, CALENDAR, PROJWBS, TASKRSRC, ACTVCODE and others.
- **Projects:**
  - 70 folders hold 75 project records with 59 distinct short names. Many are **revisions of the same job** (baseline / update / recovery plan / copy).
  - About **30 are progressed schedules** whose data date is after their plan start.
  - The independent-project count after grouping has **not yet been established**; it is likely 20–35.
  - Plan starts range from 2005 to 2014, mostly in Egypt and the Middle East.
- **Activities:** not totalled. The 6 sampled schedules range from 33 to 4,648 tasks.
- **Features:** real task names, WBS, activity codes, resources, calendars, constraints, float.
- **Labels (verified on the 6-project sample):**
  - P6 `act_start_date`/`act_end_date` exist only in progressed updates. EBCF-4 has 3,272 of 4,648 tasks complete; hela-2l has 660 of 1,053. Baseline files have 0.
  - These are planner-reported status dates, not independently verified records.
  - `target_*` dates are the *current* plan, which may have been revised, so there is a leakage risk as with Cambridge.
- **Graph:** **genuine** `TASKPRED` links typed `PR_FS/SS/FF/SF`, with `lag_hr_cnt`. With CALENDAR tables, both working-day and calendar-day durations can be derived.
- **Cambridge compatibility:** **B/C**. Use it as external validation first.
- **Limitations:**
  - **Provenance and rights.** The e-verse README says the files came from a blog post ([engineeringmanagement.info](https://www.engineeringmanagement.info/2019/10/70-schedules-for-various-construction.html)). That post names no owners and gives no licence or consent, only a DMCA notice.
  - e-verse applied an MIT licence to data it did not create.
  - Company and project names are identifiable.
  - **Use for internal research only until the rights are clarified.** Also flag the uncertain provenance in any publication.

### 4. Montana DOT Daily Work Reports (AASHTOWare SiteManager): 60 (Verified, access restricted)
- **Source:** [ROSA P 54671](https://rosap.ntl.bts.gov/view/dot/54671) (Jeong & Alikhani, FHWA/MT-20-003, doi 10.21949/1518308). **Download:** only the report and a "Construction Activity Sequence Logics" PDF; the raw data must be requested from MDT.
- **Projects:** **730 highway projects.** Activities: 48 controlling work items cover more than 90% of the activities.
- **Labels:** **daily inspector-recorded quantities and work-item start/end dates.** These are the most independently recorded actuals found in this search.
- **Graph:** no explicit network; the study *inferred* sequencing logic.
- **Cambridge compatibility:** C (a different domain: highway work items).
- **Limitations:** restricted access, infrastructure rather than buildings, and no genuine predecessors.

### 5. Texas DOT DWR production-rate database: 57 (Publication identified, dataset unavailable)
- **Source:** found through a search summary only (6,538 highway projects, 2014–2026). **Unverified;** the source report wasn't opened.
- **Cambridge compatibility:** C/D. **Limitations:** counts and access are unconfirmed, and there is no network.

### 6. UNSW Canberra portfolio of six civil projects: 52.5 (Verified and downloadable)
- **Source:** Thiele, Ryan & Abbasi, *Data in Brief* 34:106659 (2020) ([article](https://pmc.ncbi.nlm.nih.gov/articles/PMC7770534)). **Download:** <https://doi.org/10.6084/m9.figshare.12998822.v2>. The files were **not opened**; details come from the article.
- **Projects:** 6 (12 more mentioned but unreleased), Queensland, 2011–2012.
- **Features:** network logic (an MS Project-importable "Program Links" worksheet), EVM, 12,139 cost records.
- **Labels:** baseline and actual dates are not clearly separated in the article.
- **Cambridge compatibility:** C (a case study only).
- **Limitations:** far too few projects to train on.

### 7. NYC School Construction Authority: Capital Project Schedules and Budgets: 49 (Verified and downloadable)
- **Source:** [NYC Open Data 2xh6-psuq](https://data.cityofnewyork.us/Housing-Development/Capital-Project-Schedules-and-Budgets/2xh6-psuq). **Download:** `.../api/views/2xh6-psuq/rows.csv?accessType=DOWNLOAD`.
- **Size:** about 14,069 project-phase rows (scope / design / construction).
- **Fields:** phase actual start, *original* planned end, actual end, budgets. Placeholder codes ("PNS", "FTK") appear in the date fields.
- **Graph:** none. **Cambridge compatibility:** **D** for the activity-level target.
- **Limitations:** phase-level only. It could support a separate project-phase delay baseline, not the GNN.

### 8. El-Dash, Ramadan & Youssef: Middle East activity durations (~84,000 activities): 44 (Publication identified, dataset unavailable)
- **Source:** [Zenodo 2647778](https://zenodo.org/records/2647778) (ETASR 2019). **Download:** the paper PDF only.
- **Coverage:** EPC activities in Egypt, Kuwait and Saudi Arabia, described as actual durations. **Limitations:** no data released. It might overlap the region of the e-verse collection.

### 9. NYC Capital Projects Dashboard: Schedule History and Variance: 41.5 (Unverified)
- **Source:** [data.gov catalog](https://catalog.data.gov/dataset/capital-projects-dashboard-citywide-schedule-history-and-variance).
- **Content:** project completion-date snapshots, flagged as forecast or actual. **Cambridge compatibility:** D. Project level only; the catalog page wasn't opened.

### 10. US DoD construction contract data 2009–2020 (FPDS-NG): 39.5 (Verified and downloadable)
- **Source:** Stout et al., *Data in Brief* 32:106128 (2020) ([article](https://pmc.ncbi.nlm.nih.gov/articles/PMC7452689/)). **Download:** <https://data.mendeley.com/datasets/yk4s7pdsvk/1>.
- **Size:** 132,652 (or 132,662; the article is inconsistent) contract actions with completion dates.
- **Cambridge compatibility:** D. **Limitations:** contract level, with no activities and no actual-completion field.

---

## Excluded after verification (details in the inventory)

| Excluded | Reason |
|---|---|
| Virginia Tech "Primavera P6 Schedules" (142 networks) | **Synthetic.** Generated for testing scheduling heuristics |
| Ballesteros-Pérez et al. "101 projects" | **Duplicate of Ghent/DSLIB** (Batselier & Vanhoucke source) |
| Cambridge Hong et al. (27 schedules, two records) | Code and ontology only; probably the same source as Cambridge |
| Mendeley Sanyal 2025 | Only a 76 KB PDF |
| Figshare Fong 2026, Mendeley Francis 2017 | Simulation outputs or figures only |
| Hugging Face `JohnVans123/ProjectManagement` | Synthetic placeholders |
| GAT 25-project study, Constructa, LightGBM study | Proprietary, not released |
| arXiv 2511.15003 | Synthetic + unnamed benchmark datasets |

## What genuinely improves PMI's training possibilities
- **Accessible now:** only the **e-verse P6 collection**. It adds the one thing Cambridge and SCHEPENDOMLAAN lack in combination: *real typed dependencies with lags and calendars, plus actual dates in progressed updates*. It is suitable for **external validation** after deduplication and a rights check.
- **Worth requesting:** the Nodes & Links collection (P6 networks, 77 projects) and the Montana DOT daily work reports (730 projects with daily-recorded actuals, although for highway work).
- **Everything else** is project-level, synthetic, duplicated or unavailable.
