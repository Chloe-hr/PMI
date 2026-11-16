import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from prepare_ghent_delays import OUT, SOURCE, load_verification, process_records, read_source
from verify_ghent_evidence import duration_match, field_counts, investigate_ratios, parse_duration, sha

TEXT_SUFFIXES = {
    ".bat", ".cfg", ".css", ".csv", ".html", ".ini", ".js", ".json", ".jsonl",
    ".md", ".p2x", ".ps1", ".py", ".rtf", ".sh", ".toml", ".txt", ".xml",
    ".yaml", ".yml",
}


def byte_sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def normalized_text_sha(content: bytes) -> str:
    """Return a diagnostic hash with CRLF normalized, without changing the file."""
    return byte_sha(content.replace(b"\r\n", b"\n"))


def preservation_result(path: Path, expected: str, frozen_content: bytes | None = None) -> str:
    """Classify exact preservation, verified line-ending drift, or a real mismatch."""
    path = Path(path)
    current = path.read_bytes()

    # This byte-exact comparison against the unchanged manifest hash is authoritative.
    if byte_sha(current) == expected:
        return "exact"

    if path.suffix.lower() not in TEXT_SUFFIXES or frozen_content is None:
        return "mismatch"

    # Only trust a normalization baseline whose exact bytes match the frozen hash. Git stores text
    # with LF but the freeze may have hashed a CRLF checkout, so the stored blob's CRLF and LF forms
    # are tried too - a form is accepted only if it reproduces the frozen hash byte for byte.
    lf_form = frozen_content.replace(b"\r\n", b"\n")
    candidates = (frozen_content, lf_form, lf_form.replace(b"\n", b"\r\n"))
    verified = next((c for c in candidates if byte_sha(c) == expected), None)
    if verified is None:
        return "mismatch"
    if normalized_text_sha(current) == normalized_text_sha(verified):
        return "line-ending-only"
    return "mismatch"


def frozen_git_content(path: Path) -> bytes | None:
    """Return HEAD's blob only when it independently matches the frozen hash later."""
    relative = Path(path).resolve().relative_to(ROOT).as_posix()
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:{relative}"], cwd=ROOT, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, ValueError):
        return None


class VerifyGhentEvidenceTests(unittest.TestCase):
    def test_exact_hashes_and_diagnostic_line_ending_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            text_file = Path(folder) / "notes.txt"
            lf_content = b"first line\nsecond line\n"
            crlf_content = b"first line\r\nsecond line\r\n"
            text_file.write_bytes(crlf_content)
            crlf_expected = byte_sha(crlf_content)
            self.assertEqual(preservation_result(text_file, crlf_expected), "exact")
            text_file.write_bytes(lf_content)
            lf_expected = byte_sha(lf_content)
            self.assertEqual(preservation_result(text_file, lf_expected), "exact")

            # A verified frozen LF blob permits a diagnostic equivalence result.
            self.assertEqual(
                preservation_result(text_file, crlf_expected, frozen_content=crlf_content),
                "line-ending-only",
            )
            # Git keeps the LF blob while the freeze hashed CRLF: the CRLF form of the blob is verified.
            self.assertEqual(
                preservation_result(text_file, crlf_expected, frozen_content=lf_content),
                "line-ending-only",
            )
            modified_content = b"first line\nchanged line\n"
            text_file.write_bytes(modified_content)
            self.assertEqual(
                preservation_result(text_file, crlf_expected, frozen_content=crlf_content),
                "mismatch",
            )

            binary_file = Path(folder) / "payload.bin"
            binary_file.write_bytes(b"first line\nsecond line\n")
            binary_lf_hash = byte_sha(binary_file.read_bytes())
            binary_file.write_bytes(b"first line\r\nsecond line\r\n")
            self.assertEqual(
                preservation_result(
                    binary_file,
                    binary_lf_hash,
                    frozen_content=b"first line\nsecond line\n",
                ),
                "mismatch",
            )

    def test_duration_parser_requires_explicit_units_and_conversion(self):
        self.assertIsNone(parse_duration("8h", None))
        self.assertIsNone(parse_duration(8, 8))
        self.assertIsNone(parse_duration("8 months", 8))
        self.assertIsNone(parse_duration("", 8))
        self.assertEqual(parse_duration("194d 6h", 8), 194.75)
        self.assertEqual(parse_duration("8h", 4), 2)
        self.assertEqual(duration_match("194d 6h", 195, 8), "within_half_day_rounding_only")
        self.assertEqual(duration_match("196d", 196, 8), "exact")
        self.assertEqual(duration_match("196d", 197, 8), "mismatch")

    def test_ratio_hypotheses_do_not_approve_or_correct(self):
        candidates = [dict(project_id="C2020-01", source_excel_row=4, early_late_check="mismatch",
            planned_duration_source=131, real_duration_source=89, planned_duration_days=131,
            real_duration_days=89, early_late_source=-.47, audit_computed_duration_ratio=89/131-1)]
        matrix = [dict(project_id="C2020-01", baseline_root_value=None, last_tracking_value=None,
            explicit_hours_per_day=8, workbook="source.xlsx", baseline_root_ref="H3", last_tracking_ref="M5",
            project_card="", update_notes="")]
        details = {"C2020-01": {"project_card": {}}}
        result = investigate_ratios(candidates, matrix, details)[0]
        self.assertIn("real rather than planned", result["hypothesis"])
        self.assertEqual(result["resolution_status"], "unresolved_manual_review")
        self.assertEqual(result["source_issue_reviewed"], "")
        self.assertEqual(result["proposed_value_correction"], "")

    @unittest.skipUnless((OUT / "verification_summary.json").is_file(), "Generate Stage 2.3A outputs first")
    def test_all_68_have_sources_and_no_proposal_bypasses_release_gate(self):
        records, docs = read_source(SOURCE)
        proposals = load_verification(OUT / "duration_verification_evidence_proposal.csv")
        included, _, _ = process_records(records, docs, proposals)
        self.assertEqual(len(proposals), 68)
        self.assertTrue(all(r["duration_deviation_days"] is None for r in included))
        self.assertTrue(all(not r["independently_usable"] for r in included))
        for row in proposals.values():
            for field in ("calendar_comparable", "original_baseline_verified", "verified_by",
                          "source_issue_reviewed", "independence_verified"):
                self.assertEqual(row[field], "")
        with (OUT / "verification_matrix.csv").open(encoding="utf-8", newline="") as file:
            matrix = list(csv.DictReader(file))
        self.assertEqual(len({r["project_id"] for r in matrix}), 68)
        self.assertEqual(set(proposals), {r["project_id"] for r in matrix})
        self.assertTrue(all((ROOT / r["workbook"]).is_file() and (ROOT / r["project_card"]).is_file() for r in matrix))
        with (OUT / "duration_ratio_investigation.csv").open(encoding="utf-8", newline="") as file:
            issues = list(csv.DictReader(file))
        self.assertEqual(len(issues), 10)
        self.assertTrue(all(r["resolution_status"] == "unresolved_manual_review" for r in issues))
        with (OUT / "verification_field_counts.csv").open(encoding="utf-8", newline="") as file:
            counts = {r["field"]: r for r in csv.DictReader(file)}
        self.assertEqual(int(counts["source_issue_reviewed"]["applicable_projects"]), 10)
        self.assertEqual(int(counts["verified_by"]["populated_from_observations"]), 0)
        summary = json.loads((OUT / "verification_summary.json").read_text())
        self.assertEqual(summary["released_labels"], 0)

    @unittest.skipUnless((OUT / "verification_protected_hashes.json").is_file(), "Generate Stage 2.3A outputs first")
    def test_raw_sources_existing_stage22_and_stage1_are_unchanged(self):
        hashes = json.loads((OUT / "verification_protected_hashes.json").read_text())
        self.assertGreater(len(hashes), 300)
        for path, expected in hashes.items():
            with self.subTest(path=path):
                file_path = ROOT / path
                result = preservation_result(
                    file_path, expected, frozen_content=frozen_git_content(file_path)
                )
                self.assertIn(result, {"exact", "line-ending-only"})


if __name__ == "__main__":
    unittest.main()
