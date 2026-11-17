#!/usr/bin/env python3
"""Re-pin ``docs/kb`` after a content commit.

Default mode rewrites ``docs/kb/PINS.json``: ``files[]`` (path, layer and the
sha256 of that path's **canonical HEAD blob** - ``git show HEAD:<path>`` with
the three provenance values masked by ``scripts/kb_canonical.py``) plus
``newest_commit`` (the full 40-character HEAD sha the pin was taken at) and
``newest_commit_date`` (``git log -1 --format=%cI HEAD``, informational: the
gate ratchets on ``newest_commit`` and no longer asserts this string).  Every
other key - ``schema``, ``core_handoff_id``, ``uncited_baseline``, ``budgets``,
``claims`` - is preserved, and the eight keys are written in the fixed order
the gate expects.

``--check`` reports drift and writes nothing.  ``--patch-headers`` rewrites only
the front-matter ``pinned_commit``, ``pinned_at`` and ``last_verified`` of every
markdown file under ``docs/kb``, root files included; a plain run does the same
after writing ``PINS.json``, so one command re-pins the tree.  That is what turns
a ``pinned_commit: null`` header into HEAD and today: null is the pre-repin state
and the gate refuses it once ``newest_commit_date`` names a date.

``docs/kb/PINS.json`` is never pinned: its own bytes change every time it is
written, so a self-pin inside it could never be true.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

#: a pin covers the canonical form, so the gate has to hash through this very
#: module; run as a script, this file's own directory makes it importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_canonical import canonical_sha256  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
KB = "docs/kb"
KB_DIR = REPO / KB
PINS_PATH = KB_DIR / "PINS.json"
PINS_ITSELF = KB + "/PINS.json"
KEY_ORDER = ("schema", "core_handoff_id", "newest_commit", "newest_commit_date", "uncited_baseline", "budgets", "files", "claims")
#: the root entry files declare layer root, like every file directly under docs/kb.
ROOT_KINDS = {"docs/kb/README.md": "root", "docs/kb/PROCEDURE.md": "root"}
EXTRA_PINNED = ("tests/COLLECTED.txt",)


def git(*args: str) -> bytes:
    proc = subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=False)
    if proc.returncode != 0:
        raise SystemExit("repin: `git %s` failed: %s" % (" ".join(args), proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout


def head() -> str:
    return git("rev-parse", "HEAD").decode().strip()


def head_date() -> str:
    return git("log", "-1", "--format=%cI", "HEAD").decode().strip()


def layer_for(path: str) -> str:
    if path in ROOT_KINDS:
        return ROOT_KINDS[path]
    if path.startswith("tests/"):
        return "test-manifest"
    parts = path.split("/")
    return parts[2].lower() if len(parts) > 3 else "root"


def pinned_paths(pin: dict) -> list:
    """Every markdown file under docs/kb plus the manifest, minus PINS.json."""
    paths = sorted(p.relative_to(REPO).as_posix() for p in KB_DIR.rglob("*.md") if p.is_file())
    for extra in EXTRA_PINNED:
        if (REPO / extra).is_file():
            paths.append(extra)
    paths = [p for p in paths if p != PINS_ITSELF]
    known = {e.get("path") for e in pin.get("files") or [] if isinstance(e, dict)}
    # keep whatever an earlier PINS.json pinned, so a pin is never dropped silently
    paths += sorted(p for p in known if p and p != PINS_ITSELF and p not in paths and (REPO / p).is_file())
    return paths


def build_files(pin: dict, check_only: bool) -> list:
    out = []
    for path in pinned_paths(pin):
        try:
            digest = canonical_sha256(git("show", "HEAD:%s" % path))
        except SystemExit:
            if check_only:
                raise
            print("repin: %s is not at HEAD yet - pinned as null" % path, file=sys.stderr)
            digest = None
        out.append({"path": path, "sha256": digest, "layer": layer_for(path)})
    return out


def ordered(pin: dict) -> dict:
    data = dict(pin)
    return {key: data.get(key) for key in KEY_ORDER}


def dirty_docs() -> str:
    return git("status", "--porcelain", "--", KB).decode("utf-8", "replace")


def write_pins(force: bool) -> int:
    pin = json.loads(PINS_PATH.read_text(encoding="utf-8"))
    dirty = dirty_docs().strip()
    if dirty and not force:
        print("repin: docs/kb is dirty; commit the content first (or pass --force):\n%s" % dirty, file=sys.stderr)
        return 2
    pin["files"] = build_files(pin, check_only=False)
    pin["newest_commit"] = head()
    pin["newest_commit_date"] = head_date()
    PINS_PATH.write_text(json.dumps(ordered(pin), indent=2) + "\n", encoding="utf-8")
    print(
        "repin: wrote %s (%d pins, newest_commit %s at %s)"
        % (PINS_ITSELF, len(pin["files"]), pin["newest_commit"][:12], pin["newest_commit_date"])
    )
    # newest_commit is set from here on, so no header may keep a null pin:
    # patch them in the same run rather than leaving a half-pinned tree behind.
    return patch_headers(apply=True)


def check() -> int:
    pin = json.loads(PINS_PATH.read_text(encoding="utf-8"))
    drift = []
    expected = build_files(pin, check_only=True)
    current = {entry.get("path"): entry for entry in pin.get("files") or []}
    for entry in expected:
        old = current.get(entry["path"]) or {}
        if old.get("sha256") != entry["sha256"]:
            drift.append("%s: pinned %r, HEAD blob %r" % (entry["path"], old.get("sha256"), entry["sha256"]))
        if old.get("layer") != entry["layer"]:
            drift.append("%s: layer %r != %r" % (entry["path"], old.get("layer"), entry["layer"]))
    for path in sorted(set(current) - {e["path"] for e in expected}):
        drift.append("%s: pinned but no longer pinnable" % path)
    newest = head()
    # newest_commit is what the gate ratchets on; newest_commit_date is
    # informational, so a stale date on its own is not drift.
    if pin.get("newest_commit") != newest:
        drift.append("newest_commit %r != HEAD %r" % (pin.get("newest_commit"), newest))
    if drift:
        print("repin --check: PINS.json is stale:\n  " + "\n  ".join(drift), file=sys.stderr)
        return 1
    print("repin --check: no drift (%d pins, newest_commit %s)" % (len(expected), newest[:12]))
    return 0


FM_FIELDS = ("pinned_commit", "pinned_at", "last_verified")


def patch_headers(apply: bool) -> int:
    commit = head()
    today = dt.date.today().isoformat()
    changed = 0
    for path in sorted(p for p in KB_DIR.rglob("*.md") if p.is_file()):
        raw = path.read_bytes()
        if b"\r" in raw:
            raise SystemExit("repin: %s has CRLF: the header parser requires LF" % path.relative_to(REPO).as_posix())
        lines = raw.decode("utf-8").split("\n")
        if not lines or lines[0].strip() != "---":
            continue
        try:
            end = lines.index("---", 1)
        except ValueError:
            continue
        block = lines[1:end]
        new_block, touched = [], False
        for line in block:
            key = line.split(":", 1)[0].strip()
            if key == "pinned_commit":
                touched = touched or line != "pinned_commit: %s" % commit
                new_block.append("pinned_commit: %s" % commit)
            elif key in ("pinned_at", "last_verified"):
                touched = touched or line != "%s: %s" % (key, today)
                new_block.append("%s: %s" % (key, today))
            else:
                new_block.append(line)
        if not touched:
            continue
        changed += 1
        if apply:
            path.write_text("\n".join([lines[0], *new_block, *lines[end:]]) , encoding="utf-8")
            print("repin: patched %s" % path.relative_to(REPO).as_posix())
    verb = "patched" if apply else "would patch"
    print("repin --patch-headers: %s %d header(s) to HEAD %s at %s" % (verb, changed, commit[:12], today))
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="Re-pin docs/kb at HEAD.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="report drift, write nothing")
    group.add_argument("--patch-headers", action="store_true", help="rewrite header pinned_commit/pinned_at/last_verified")
    parser.add_argument("--force", action="store_true", help="pin even when docs/kb is dirty")
    args = parser.parse_args(argv)
    if args.check:
        return check()
    if args.patch_headers:
        return patch_headers(apply=not args.check)
    return write_pins(args.force)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
