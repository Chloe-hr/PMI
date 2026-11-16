# Test failure audit — 12 Nov 2026

**Context.** Branch `feature/ifc-to-gantt`, compared against its parent `main` (1977a64). `main` was run in a clean temporary worktree with the same venv. No frozen hash or manifest was changed.

| Run | Tests | Result |
|---|---|---|
| Working copy (`feature/ifc-to-gantt`) | 68 (includes 11 new Stage 3 tests, all passing) | 18 failures, 1 error |
| Clean checkout of `main` | 57 | 6 failures, 1 error |

The branch changes only `.gitignore` and `requirements.txt` among tracked files. Neither appears in any manifest. The protected files were last modified on 3 Nov and 12 Nov 10:12 (the `git pull`), before this session started.

## Failures

| # | Test | Error | Expected artifact | On `main`? | Category |
|---|---|---|---|---|---|
| 1 | `test_audit_cambridge` … `test_generated_counts_candidates_and_preserved_artifacts` | `FileNotFoundError` | `data/processed/stage2/cambridge_audit/activity_label_audit.csv` (444,156 rows) | **Fails** (same error) | **Missing artifact.** The file is git-ignored (`.gitignore` line 6), so it never reaches a clone. Its source `data/raw/cambridge/JPF_Anonymised_Project_Data.json` is also ignored and missing here |
| 2 | `test_design_cambridge_experiment` … `test_full_manifests_preserve_population_no_overlap_and_frozen_protocol` | SHA-256 mismatch: got `b87c7a59…`, expected `f7417102…` | `app.py` in `cambridge_experiment_design/design_freeze.json` → `protected_inputs` | Passes | **Line endings only.** The freeze hashed `app.py` with CRLF; this working copy has LF. The content is identical once CRLF/LF is normalised |
| 3 | `test_review_cambridge_feasibility` … `test_full_review_counts_no_split_and_input_preservation` | SHA-256 mismatch: got `cd4e9ba5…`, expected `546206ee…` | `scripts/schedule_engine.py` in `cambridge_feasibility/input_review_manifest.json` → `source_files` | Passes | **Line endings only** (CRLF frozen, LF here) |
| 4–13 | `test_verify_ghent_evidence` … `test_raw_sources_existing_stage22_and_stage1_are_unchanged`, 10 subtests | SHA-256 mismatch | `verification_protected_hashes.json`: `app.py`, `scripts/{create_v2, create_v3, detect_changes, engineering_report, export_geometry, make_evidence, riba_risk, schedule_engine, validate}.py` | Pass | **Line endings only.** Frozen as CRLF (files from commit 1c24365); this copy is LF |
| 14–19 | same test, 6 subtests | SHA-256 mismatch | `data/raw/ghent/BUILDINGS_ONLY.md`, `data/raw/ghent/buildings/DSLIB 3.4/Readme.rtf`, `scripts/prepare_mendeley_data.py`, `scripts/prepare_training_data.py`, `training/train_model.py`, `training/prepare_ghent_delays.py` | **Fail** | **Line endings only.** Frozen as LF (files from commit fbf0413); every Windows checkout has CRLF |

**How "line endings only" was established.** For each mismatched file, the hash of the current bytes, converted to LF and then to CRLF, was compared with the frozen digest. In every case listed above, one of the two conversions matches **exactly**. So no protected content has changed in these files; only the end-of-line bytes differ.

**Root cause.** The freezes were taken from a working copy with *mixed* line endings: older files in CRLF, newer files in LF. With `core.autocrlf=true` and no `.gitattributes`, git decides which line endings each checkout gets. No single checkout reproduces the mixed state, which is why a clean `main` fails on a different subset (rows 14–19) than this working copy does.

## Manifest entries not covered by the tests (found by checking the full manifests)

- **`launch_app.py`: real content change, not line endings.** It is listed in `design_freeze.json`. The frozen digest matches the version in fbf0413. Merge 436cd91 ("Merge branch 'main' into main", 12 Nov) then added a line:
  ```python
  subprocess.run([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py")], cwd=ROOT)
  ```
  The line sits *before* the existing venv-aware launch, so the launcher starts Streamlit twice: once with the system Python, then again when that one exits. This looks like an accidental merge leftover. It is not fixed here; it needs a decision.
- **`data/raw/cambridge/JPF_Anonymised_Project_Data.json` and `cambridge_audit/activity_label_audit.csv`:** missing, by design (git-ignored).
- Every other manifest entry that differs does so only in line endings: the IFC models, `run_pipeline.py`, `training/*.py`, the `data/processed` READMEs.

## Options considered (decided and implemented: see "Resolution" below)

1. **Missing artifacts (row 1):** get both Cambridge files from whoever ran Stage 2.3, or regenerate them with `training/audit_cambridge.py` once the raw JSON is available. Alternatively, make the test skip when the file is absent, as the Ghent tests already do.
2. **Line endings (rows 2–19):** leave the frozen digests untouched and change only the *comparison*. Accept a file if its raw bytes, its LF form or its CRLF form matches the frozen digest. Any change beyond line endings still fails. A `.gitattributes` alone cannot fix this, because the frozen set is mixed.
3. **`launch_app.py`:** confirm with the teammate whether the added line was intended. If it wasn't, remove it. The file would then match its frozen hash again (modulo line endings).

---

# Resolution — 12 Nov 2026 (uncommitted, awaiting review)

## Root cause (confirmed)

1. **Line endings.** The Stage 2 freezes hashed a working copy with *mixed* line endings. `core.autocrlf=true` rewrites line endings at checkout, so no single checkout reproduces those bytes. The *content* of every affected file is unchanged.
2. **Untracked data.** `cambridge_audit/activity_label_audit.csv` and the extracted Cambridge JSON are git-ignored on purpose, so they are absent from any clone that did not run Stage 2.3.
3. **Merge leftover in `launch_app.py`.** Commit fbf0413 *replaced* the `sys.executable` launch line with a venv-aware launch. Merge 436cd91 then kept both sides, so Streamlit started twice.

## Exact files modified

| File | Change |
|---|---|
| `tests/checksum_utils.py` (new) | `frozen_match()` / `assert_frozen()`: compare the exact bytes first; if that fails, accept only a text file whose all-LF or all-CRLF form reproduces the frozen digest. Binary files are compared exactly only |
| `tests/test_checksum_utils.py` (new) | 12 tests. Exact and both line-ending directions are accepted. Rejected: code edits, an added line, removed blank lines, trailing spaces, an extra final newline, indentation, bare CR, mixed-ending reconstruction, CR/LF rewrites inside binary files, missing files. Plus a check on the real repository: a one-word edit to a copy of `scripts/schedule_engine.py` is rejected |
| `tests/test_verify_ghent_evidence.py` | `assertEqual(sha(...), expected)` → `assert_frozen(...)`; the unused `sha` import is dropped |
| `tests/test_design_cambridge_experiment.py` | Both frozen-hash loops (`outputs`, `protected_inputs`) → `assert_frozen(...)` |
| `tests/test_review_cambridge_feasibility.py` | Frozen-hash loop → `assert_frozen(...)` |
| `tests/test_audit_cambridge.py` | Added `skipUnless(activity_label_audit.csv exists)` with an explicit reason; frozen-hash loop → `assert_frozen(...)`. All other assertions are unchanged and run when the file exists |
| `launch_app.py` | Removed the line reintroduced by the merge. The file now matches its frozen digest in `design_freeze.json` **byte for byte**, and its content is identical to fbf0413 |

**Not modified:** any frozen checksum, manifest or JSON freeze; any file under `data/`, `models/` (except the new untracked GNN outputs from Stage 3.5) or `training/`; `scripts/`, including the scheduling engine; `app.py`. The `training/*.py` hash functions were left untouched because those files are themselves protected inputs. The new logic lives only in `tests/`.

## Resolution semantics

`assert_frozen` reports a match as **exact** (byte-for-byte identity) or as **line-ending-equivalent**. Line-ending-equivalent means the content is identical *except* for CRLF vs LF terminators. It is **not** byte-for-byte identity. Any other difference fails, and the failure message shows both digests.

Coverage on this working copy (all four manifests):

| Manifest | Entries | Exact | Line-ending-equivalent | Not accepted |
|---|---|---|---|---|
| `verification_protected_hashes.json` | 380 | 364 | 16 | 0 |
| `design_freeze.json` → `protected_inputs` | 676 | 643 | 31 | 2 (untracked Cambridge files) |
| `input_review_manifest.json` → `source_files` | 432 | 403 | 27 | 2 (same) |
| `cambridge_audit/protected_hashes.json` | 420 | 392 | 27 | 1 (extracted Cambridge JSON) |

## Final test results

| Run | Tests | Passed | Failed | Skipped |
|---|---|---|---|---|
| Before (working copy, audit above) | 68 | 49 | 19 | 0 |
| **After, working copy** (`feature/ifc-to-gantt`) | 80 | **79** | **0** | 1 |
| **After, clean `main` checkout + the same repaired files** | 69 | **68** | **0** | 1 |

- The single skip is `test_audit_cambridge` … `test_generated_counts_candidates_and_preserved_artifacts`: the untracked `activity_label_audit.csv` is absent.
- There are no new failures. The two checkouts have opposite line-ending mixes, and both now pass, which confirms the fix doesn't depend on one machine's checkout.
- Compared with the previous audit: all 18 checksum failures are resolved as line-ending-equivalent, and the 1 error has become a documented skip.

## Remaining limitations

- **Cambridge full-audit validation does not run on this machine.** Its 444,156-row checks resume automatically once `activity_label_audit.csv` is restored. The audit never fabricates or regenerates the file.
- The two untracked Cambridge files are still listed in the design and review manifests, but no current test asserts on them. They remain unverifiable here until restored.
- The fallback can't validate a file whose frozen bytes had *mixed* endings *within* the file, unless the file is byte-identical. It fails conservatively. No such case occurs today.
- Normalisation covers CRLF↔LF only. Other platform rewrites, such as Unicode normalisation or a BOM, still fail.
- Longer term, a `.gitattributes` with explicit `eol` rules, followed by a deliberate, documented re-freeze, would restore byte-for-byte verification. That is a research-governance decision and was not taken here.
