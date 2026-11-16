"""The frozen-checksum fallback accepts ONLY line-ending differences; every real change must fail."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from checksum_utils import EXACT, LINE_ENDING_EQUIVALENT, assert_frozen, frozen_match  # noqa: E402

TEXT_LF = b'ROOT = "pmi"\nsubprocess.run([python, "app.py"])\n\nprint("done")\n'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FrozenChecksumTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "frozen.py"

    def tearDown(self):
        self.dir.cleanup()

    def check(self, frozen_bytes: bytes, current_bytes: bytes):
        self.path.write_bytes(current_bytes)
        return frozen_match(self.path, digest(frozen_bytes))

    # --- accepted ---------------------------------------------------------------------------
    def test_identical_bytes_are_exact(self):
        self.assertEqual(self.check(TEXT_LF, TEXT_LF), EXACT)

    def test_lf_frozen_crlf_checkout_is_line_ending_equivalent(self):
        self.assertEqual(self.check(TEXT_LF, TEXT_LF.replace(b"\n", b"\r\n")), LINE_ENDING_EQUIVALENT)

    def test_crlf_frozen_lf_checkout_is_line_ending_equivalent(self):
        self.assertEqual(self.check(TEXT_LF.replace(b"\n", b"\r\n"), TEXT_LF), LINE_ENDING_EQUIVALENT)

    # --- rejected: real content changes ----------------------------------------------------
    def test_code_change_fails_even_after_normalisation(self):
        changed = TEXT_LF.replace(b"python", b"sys.executable")
        self.assertIsNone(self.check(TEXT_LF, changed))
        self.assertIsNone(self.check(TEXT_LF, changed.replace(b"\n", b"\r\n")))

    def test_added_line_fails(self):   # e.g. the duplicated launcher line from merge 436cd91
        added = TEXT_LF.replace(b'print("done")\n', b'subprocess.run([python, "app.py"])\nprint("done")\n')
        self.assertIsNone(self.check(TEXT_LF.replace(b"\n", b"\r\n"), added.replace(b"\n", b"\r\n")))

    def test_whitespace_and_blank_line_changes_fail(self):
        self.assertIsNone(self.check(TEXT_LF, TEXT_LF.replace(b"\n\n", b"\n")))         # removed blank line
        self.assertIsNone(self.check(TEXT_LF, TEXT_LF.replace(b"app.py\"])", b"app.py\"]) ")))  # trailing space
        self.assertIsNone(self.check(TEXT_LF, TEXT_LF + b"\n"))                       # extra final newline
        self.assertIsNone(self.check(TEXT_LF, b"    " + TEXT_LF))                     # indentation

    def test_bare_carriage_return_is_not_a_line_ending_equivalent(self):
        self.assertIsNone(self.check(TEXT_LF, TEXT_LF.replace(b"\n", b"\r")))

    def test_mixed_frozen_file_cannot_be_reproduced_by_uniform_endings(self):
        mixed = b"a\r\nb\nc\r\n"
        self.assertIsNone(self.check(mixed, b"a\nb\nc\n"))       # conservative: fails rather than guesses
        self.assertEqual(self.check(mixed, mixed), EXACT)

    def test_binary_files_are_exact_only(self):
        binary = b"\x00\x01PK\r\n\x02model-weights\r\n"
        self.assertEqual(self.check(binary, binary), EXACT)
        self.assertIsNone(self.check(binary, binary.replace(b"\r\n", b"\n")))  # CR/LF rewrite = corruption

    def test_missing_file_fails(self):
        self.assertIsNone(frozen_match(Path(self.dir.name) / "absent.py", digest(TEXT_LF)))

    def test_assert_frozen_reports_both_digests_on_failure(self):
        self.path.write_bytes(TEXT_LF + b"# edit\n")
        with self.assertRaises(AssertionError) as ctx:
            assert_frozen(self, self.path, digest(TEXT_LF))
        self.assertIn("beyond line endings", str(ctx.exception))
        self.assertIn(digest(TEXT_LF), str(ctx.exception))


class RealManifestBaselineTests(unittest.TestCase):
    """On the real repository: every protected file is accepted, and a one-byte edit is rejected."""
    MANIFEST = ROOT / "data/processed/stage2/verification_protected_hashes.json"

    @unittest.skipUnless(MANIFEST.is_file(), "Stage 2.3A outputs not present")
    def test_tampered_copy_of_a_protected_file_is_rejected(self):
        hashes = json.loads(self.MANIFEST.read_text())
        path = "scripts/schedule_engine.py"
        self.assertIsNotNone(frozen_match(ROOT / path, hashes[path]))
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "schedule_engine.py"
            copy.write_bytes((ROOT / path).read_bytes().replace(b"Critical Path", b"Critical Pathx", 1))
            self.assertIsNone(frozen_match(copy, hashes[path]))


if __name__ == "__main__":
    unittest.main()
