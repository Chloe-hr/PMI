"""Cross-platform verification of FROZEN SHA-256 checksums (test helper only).

The Stage 2 freezes were recorded from a working copy with mixed line endings (some files CRLF,
some LF). Git's ``core.autocrlf`` rewrites line endings at checkout, so the same committed content
can have different bytes on different machines. See ``docs/test_failure_audit.md``.

Verification order
    1. EXACT: SHA-256 of the file bytes equals the frozen digest -> "exact".
    2. LINE-ENDING-EQUIVALENT (text files only): the file is converted to all-LF and to all-CRLF;
       if either form hashes to the frozen digest -> "line-ending-equivalent".
    3. Anything else fails.

IMPORTANT: outcome 2 is *line-ending-equivalent validation, not byte-for-byte identity*. It proves
the content is identical except for CRLF vs LF line terminators. Every other change still fails:
added, removed or edited characters, whitespace, blank lines, bare CR, and any change to a binary file.

Binary files (a NUL byte in the first 8000 bytes, git's own heuristic) are only ever compared exactly,
because rewriting CR/LF bytes inside them would be corruption, not a line-ending convention.

The frozen digests and manifests are never modified by this module.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

EXACT = "exact"
LINE_ENDING_EQUIVALENT = "line-ending-equivalent"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8000]


def frozen_match(path: Path, expected: str) -> str | None:
    """EXACT, LINE_ENDING_EQUIVALENT, or None (content differs / file missing)."""
    path = Path(path)
    if not path.is_file():
        return None
    data = path.read_bytes()
    if _sha256(data) == expected:
        return EXACT
    if is_binary(data):
        return None
    lf = data.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    if expected in (_sha256(lf), _sha256(crlf)):
        return LINE_ENDING_EQUIVALENT
    return None


def assert_frozen(testcase, path: Path, expected: str) -> str:
    """unittest assertion: the file matches its frozen digest exactly or line-ending-equivalently."""
    result = frozen_match(path, expected)
    if result is None:
        actual = _sha256(Path(path).read_bytes()) if Path(path).is_file() else "<missing file>"
        testcase.fail(f"{path}: content differs from the frozen checksum beyond line endings "
                      f"(got {actual}, frozen {expected})")
    return result
