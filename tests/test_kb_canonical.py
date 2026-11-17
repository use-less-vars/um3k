"""Git-free proof of the canonical form the KB pins are taken over (A2's fix).

Every assertion runs on ``tmp_path`` bytes: no repository, no git binary, no
edit to ``docs/kb``.  The last two tests are the regression tests for the
defect - pin a blob, let ``scripts/repin_kb.py``'s header patch rewrite its
three provenance fields, and check the pin still holds - and the proof that the
writer and the gate hash through one single helper.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

from scripts import kb_canonical
from scripts.kb_canonical import CANONICAL_FIELDS, CANONICAL_VALUE, canonical_bytes, canonical_sha256

HEADER = b"""---
status: current
layer: core
pinned_commit: aaaabbbbccccddddeeeeffff0000111122223333
pinned_at: 2026-11-17
byte_budget: 2560
last_verified: 2026-11-17
reads_when: every session
supersedes: null
superseded_by: null
---
# body

item one.
"""


def written(tmp_path: Path, name: str, raw: bytes) -> Path:
    """Put ``raw`` on disk and hand back the path: the pin is over file bytes."""
    path = tmp_path / name
    path.write_bytes(raw)
    return path


def test_provenance_values_do_not_move_the_digest(tmp_path: Path) -> None:
    """The three fields repin rewrites are provenance: their values are invisible."""
    path = written(tmp_path, "page.md", HEADER)
    pinned = canonical_sha256(path.read_bytes())
    for old, new in (
        (b"pinned_commit: aaaabbbbccccddddeeeeffff0000111122223333", b"pinned_commit: " + b"9" * 40),
        (b"pinned_at: 2026-11-17", b"pinned_at: 2026-12-01"),
        (b"last_verified: 2026-11-17", b"last_verified: 2027-01-02"),
    ):
        assert old in HEADER
        patched = HEADER.replace(old, new, 1)
        assert patched != HEADER
        assert canonical_sha256(written(tmp_path, "patched.md", patched).read_bytes()) == pinned
    # null -> a commit is the transition repin actually performs on a first run.
    nulled = HEADER.replace(b"pinned_commit: aaaabbbbccccddddeeeeffff0000111122223333", b"pinned_commit: null", 1)
    assert canonical_sha256(written(tmp_path, "nulled.md", nulled).read_bytes()) == pinned
    # ... and every value now sits at the placeholder, not merely "masked somehow".
    assert b"pinned_commit: " + CANONICAL_VALUE in canonical_bytes(nulled)


def test_other_bytes_do_move_the_digest(tmp_path: Path) -> None:
    """Everything that is not provenance is still pinned: one byte is enough."""
    path = written(tmp_path, "page.md", HEADER)
    pinned = canonical_sha256(path.read_bytes())
    for old, new, why in (
        (b"byte_budget: 2560", b"byte_budget: 2561", "another front-matter key"),
        (b"reads_when: every session", b"reads_when: every session.", "another front-matter key"),
        (b"item one.", b"item two.", "a body byte"),
        (b"# body", b"# bodX", "a heading byte"),
    ):
        assert old in HEADER, why
        moved = HEADER.replace(old, new, 1)
        assert canonical_sha256(written(tmp_path, "moved.md", moved).read_bytes()) != pinned, why


def test_no_front_matter_canonicalises_to_raw_bytes(tmp_path: Path) -> None:
    """Without a closed ``---`` fence there is nothing to strip: raw bytes, raw digest."""
    raw = b"# just a file\n\nno front matter here\n"
    path = written(tmp_path, "plain.md", raw)
    assert canonical_bytes(path.read_bytes()) == raw
    assert canonical_sha256(path.read_bytes()) == hashlib.sha256(raw).hexdigest()
    # an opened-but-never-closed fence is not front matter either.
    unterminated = b"---\npinned_commit: null\nno closing fence\n"
    assert canonical_bytes(unterminated) == unterminated


def test_crlf_and_missing_trailing_newline(tmp_path: Path) -> None:
    """Neither line endings nor the trailing newline crash it or merge two files."""
    lf = written(tmp_path, "lf.md", HEADER).read_bytes()
    crlf = written(tmp_path, "crlf.md", HEADER.replace(b"\n", b"\r\n")).read_bytes()
    canon_crlf = canonical_bytes(crlf)
    assert canon_crlf.count(b"\r\n") == crlf.count(b"\r\n")
    assert b"pinned_commit: " + CANONICAL_VALUE + b"\r\n" in canon_crlf
    assert canonical_sha256(crlf) != canonical_sha256(lf)
    trimmed = written(tmp_path, "trimmed.md", HEADER.rstrip(b"\n")).read_bytes()
    assert canonical_bytes(lf).endswith(b"\n")
    assert not canonical_bytes(trimmed).endswith(b"\n")
    assert canonical_sha256(trimmed) != canonical_sha256(lf)


def test_a_pin_survives_the_header_patch(tmp_path: Path) -> None:
    """The A2 regression: pin the bytes, patch the three fields, the pin still holds."""
    pinned = canonical_sha256(written(tmp_path, "before.md", HEADER).read_bytes())
    head_sha = b"0123456789abcdef0123456789abcdef01234567"
    today = b"2026-11-18"
    replacements = {b"pinned_commit": head_sha, b"pinned_at": today, b"last_verified": today}
    assert set(replacements) == set(CANONICAL_FIELDS)
    patched = HEADER
    for line in HEADER.split(b"\n"):
        key = line.split(b":", 1)[0].strip()
        if key in replacements:
            patched = patched.replace(line, key + b": " + replacements[key], 1)
    assert patched != HEADER
    # the defect: a raw-bytes pin disagrees with the file the operator now holds.
    assert hashlib.sha256(patched).hexdigest() != pinned
    # the fix: the canonical pin is the same number on both sides.
    assert canonical_sha256(written(tmp_path, "after.md", patched).read_bytes()) == pinned


def test_writer_and_gate_share_one_helper() -> None:
    """repin and A2 must hash through the same module, not through two copies."""
    root = Path(__file__).resolve().parents[1]
    saved = list(sys.path)
    try:
        import scripts.repin_kb as repin
    finally:
        sys.path[:] = saved
    shared = sys.modules["kb_canonical"]
    assert Path(shared.__file__).resolve() == Path(kb_canonical.__file__).resolve()
    assert repin.canonical_sha256 is shared.canonical_sha256

    spec = importlib.util.spec_from_file_location("kb_gate_under_test", root / "tests" / "test_kb_integrity.py")
    gate = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(gate)
    assert gate.canonical_bytes is canonical_bytes
