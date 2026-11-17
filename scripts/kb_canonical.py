"""The canonical form a ``docs/kb`` pin is taken over.

A pin cannot be a hash of a file's bytes.  ``scripts/repin_kb.py`` reads each
file's HEAD blob and then patches the front matter - ``pinned_commit``,
``pinned_at``, ``last_verified`` - in the working tree, so the pinned bytes and
the bytes on disk differ by exactly those three values and can never agree
again: dirty tree fails the working-side check, committed tree moves the HEAD
blob.  A pin therefore covers the *canonical* form: the file's bytes with the
VALUES of those three front-matter keys replaced by :data:`CANONICAL_VALUE`, and
nothing else touched.  Both ``scripts/repin_kb.py`` and
``tests/test_kb_integrity.py`` (A2) hash through :func:`canonical_sha256`, so a
pin is one number that both sides can satisfy.

The substitution is line-level and restricted to the leading ``---`` ...
``---`` fence.  There is no YAML round-trip, so encoding, line endings, key
order and the trailing newline survive byte for byte.  A file with no front
matter canonicalises to its raw bytes.
"""
from __future__ import annotations

import hashlib

#: the front-matter fence, as bytes: the whole helper never decodes its input.
FENCE = b"---"
#: the keys whose VALUES are provenance, not content: ``repin_kb.py`` rewrites
#: exactly these three in every header, so a pin must not see them.
CANONICAL_FIELDS = (b"pinned_commit", b"pinned_at", b"last_verified")
#: what those three values are replaced with; it is not a legal value for any of
#: them, so it cannot collide with a real header.
CANONICAL_VALUE = b"<canonical>"


def canonical_bytes(raw: bytes) -> bytes:
    """``raw`` with the three provenance values replaced by ``<canonical>``.

    Only ``key: value`` lines inside the leading ``---`` ... ``---`` fence whose
    key is one of :data:`CANONICAL_FIELDS` are rewritten; every other byte -
    including each line's own ``\\r`` if the file is CRLF - is carried through
    unchanged.  A file without a closed front-matter fence is returned as is.
    """
    lines = raw.split(b"\n")
    if not lines or lines[0].strip() != FENCE:
        return raw
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == FENCE:
            end = index
            break
    if end is None:
        return raw
    out = list(lines)
    for index in range(1, end):
        line = lines[index]
        key = line.split(b":", 1)[0].strip()
        if key in CANONICAL_FIELDS:
            eol = b"\r" if line.endswith(b"\r") else b""
            out[index] = key + b": " + CANONICAL_VALUE + eol
    return b"\n".join(out)


def canonical_sha256(raw: bytes) -> str:
    """The 64-lowercase-hex digest that ``PINS.files[].sha256`` holds."""
    return hashlib.sha256(canonical_bytes(raw)).hexdigest()
