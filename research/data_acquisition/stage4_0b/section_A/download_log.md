# Section A - download log and diagnosis

Generated 2026-11-19 12:56 UTC.

## 1. Diagnosis of the previous Section A task
| Hypothesis | Evidence | Verdict |
|---|---|---|
| Never started | `data/raw/candidates/bim_spatial/` empty; no Section A files anywhere under `research/data_acquisition/`; no running python/curl/git/7z processes found (`tasklist`) | **Most likely: never ran (or ran outside this repository) - no artefact of it exists** |
| Network restrictions | Mendeley public API, DataCite and GitHub API all reachable from this machine during recovery | Not the blocker |
| Failed download resolution | Mendeley `public-api/datasets/<id>/files?folder_id=root` returns `[]` (files sit in 3 sub-folders); a naive client would see "no files". | Possible contributing pitfall |
| Downloads in another location | All targets already exist under `data/raw/` (pre-dating Stage 4.0B: Mendeley folder, `IFC4.x-specification-models-main`, `Certification-datasets-main`, `SCHEPENDOMLAAN`), acquired in Stage 3.7A | **Yes - data existed, only not under candidates/** |
| Archive / Git LFS issues | SCHEPENDOMLAAN upstream stores 69 files as LFS pointers; local copies are full objects (no pointers found) | Not a blocker locally |
| Repository permissions | Public repositories; `gh api` read access works | Not the blocker |
| Interrupted | No partial files or temp downloads found | No evidence |

## 2. Verification instead of re-download
- **Mendeley fm9myphk9g v1** (CC BY 4.0, published 2025-11-24, 3 folders / 18 files): local SHA-256 equals publisher SHA-256 for **18/18** files. Metadata saved to `data/raw/candidates/bim_spatial/mendeley_spatial/metadata/`. Files were **not duplicated** (341 MB) - their verified location is `data/raw/BIM Spatial Models for Construction Dependency Inf/`.
- **GitHub copies** vs upstream default-branch trees (`github_copy_verification.csv`): DataSetSchependomlaan identical after CRLF->LF=244; DataSetSchependomlaan identical to upstream=2; DataSetSchependomlaan identical to upstream LFS object (sha256+size)=7; DataSetSchependomlaan identical to upstream LFS object after CRLF->LF=60; DataSetSchependomlaan local only=1; DataSetSchependomlaan missing locally=2; DataSetSchependomlaan upstream blob is not an LFS pointer; local differs (see note)=2; Certification-datasets identical to upstream=35; IFC4.x-specification-models identical to upstream=46.
  - SCHEPENDOMLAAN files differ from upstream only by CRLF line endings (verified by re-hashing after CRLF->LF against git blob SHA-1 or LFS SHA-256).
  - Exception: both `V_L_Constructief.ifc` copies are **0-byte blobs upstream** but 941,642 bytes locally -> provenance unverifiable.
  - Missing locally: `.gitattributes`, `desktop.ini` (irrelevant). Local-only: one `.url` shortcut.
- RestageIFC: already verified (Zenodo MD5) in Sections B-E.

## 3. Audit runs
- `audit_ifc.py` on all 160 local IFC files (outside `data/raw/candidates/`), one process each: 160 ok, 0 failures. Output: `data/processed/candidates/stage4_0b/section_A/ifc_audit/*.json`.
- First pass missed Synchro-flattened quantity keys (`[BaseQuantities[IfcElementQuantity/..]]NetVolume`); detector added and all files re-audited.
- `geometry_check.py` (40 elements per class, IfcOpenShell 0.9.0.post1) on 7 candidate models: 862 elements tessellated, 862 ok.
