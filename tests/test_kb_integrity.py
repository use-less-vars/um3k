"""KB ingestion gate: the ten assertions A1..A10 over ``docs/kb/``.

Authority is ``docs/kb/PROCEDURE.md``; machine-readable pins live in
``docs/kb/PINS.json``; ``[FIXED-TESTED ...]`` resolves only against the pinned
``tests/COLLECTED.txt`` manifest.  This module never writes, never greps a
``def`` to resolve a tag, and never skips a check because its inputs look
unfinished.

Git-free, green anywhere: A1, A3, A5, A6, A7, A8, A9.
Git-dependent, explicitly red without a repository: A2, A4, A10 - each fails
with its own "git unavailable" message rather than skipping.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from scripts.kb_canonical import canonical_bytes

REPO = Path(__file__).resolve().parents[1]
KB = "docs/kb"
KB_DIR = REPO / KB
PINS_PATH = KB_DIR / "PINS.json"
COLLECTED_PATH = REPO / "tests" / "COLLECTED.txt"

#: five content layers, plus the root entry files (README.md, PROCEDURE.md).
CONTENT_LAYERS = ("core", "registry", "work", "archive", "reference")
ALL_LAYERS = CONTENT_LAYERS + ("root",)
STATUSES = ("current", "stale", "superseded", "draft")
HEADER_KEYS = (
    "status",
    "layer",
    "pinned_commit",
    "pinned_at",
    "byte_budget",
    "last_verified",
    "reads_when",
    "supersedes",
    "superseded_by",
)
#: allowed on ``layer: core`` only, and then it must equal PINS.core_handoff_id.
CORE_ONLY_KEYS = ("core_handoff_id",)
PINS_KEYS = (
    "schema",
    "core_handoff_id",
    "newest_commit_date",
    "uncited_baseline",
    "budgets",
    "files",
    "claims",
)
#: keys ``scripts/repin_kb.py`` writes that a pre-repin PINS.json does not carry
#: yet: A1 tolerates their presence, A10 is what requires ``newest_commit``.
PINS_OPTIONAL_KEYS = ("newest_commit",)
#: A1's layer enum governs markdown headers, and PINS.files[].layer reuses it
#: verbatim - the two root entry files are "root" - plus exactly one kind for the
#: manifest that lives outside docs/kb/.
PINS_FILE_LAYERS = ALL_LAYERS + ("test-manifest",)
BUDGET_KEYS = (
    "core",
    "core_warn",
    "per_file_core_default",
    "registry",
    "work",
    "test_manifest",
    "test_manifest_warn",
    "total_ingest",
    "warn_at",
)
SCHEMA = "kb-pins/1"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEADER_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})?)?$")
FLOAT_TOKEN = re.compile(r"^[0-9]+\.[0-9]+$")

STALE_DAYS = 14
STALE_WARN_AHEAD = 20
STALE_FAIL_AHEAD = 50

#: A tag is a bracketed token: ``[NAME body]``.  The bracket is part of the
#: syntax, which is what keeps the English words "measured" and "closed" out of
#: the grammar.  Tags parse anywhere in a line except inside inline code spans
#: and fenced blocks (see ``mask_code``).
TAG_NAMES = ("VERIFIED-BY-RUN", "FIXED-TESTED", "measured", "closed", "CITED", "UNCITED")
TAG_CLOSED = re.compile(r"\[(VERIFIED-BY-RUN|FIXED-TESTED|measured|closed|CITED|UNCITED)\b([^\]]*)\]")
TAG_OPEN = re.compile(r"\[(VERIFIED-BY-RUN|FIXED-TESTED|measured|closed|CITED|UNCITED)\b")
TAG_BODIES = {
    "VERIFIED-BY-RUN": re.compile(r"^\s+[0-9a-f]{7,40}\s+\S.*$"),
    "FIXED-TESTED": re.compile(r"^\s+\S+?::\S+$"),
    "measured": re.compile(r"^\s+\S+\s+[0-9a-f]{12,64}$"),
    "closed": re.compile(r"^\s+\S+$"),
    "CITED": re.compile(r"^\s+\S+:\d+$"),
    "UNCITED": re.compile(r"^\s*$"),
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def walked() -> list[Path]:
    """Every markdown file under docs/kb - PINS.json is not markdown and is
    therefore the one file in the tree that carries no front matter."""
    return sorted(p for p in KB_DIR.rglob("*.md") if p.is_file())


def pins() -> dict:
    return json.loads(PINS_PATH.read_text(encoding="utf-8"))


def front_matter(path: Path) -> tuple[dict, list]:
    """Parse the ``---`` delimited block that must open ``path``.

    Dumb line parser, exactly as PROCEDURE.md specifies: one ``key: value`` per
    line, bare scalars, ``null`` for absence, no quotes, no inline comments, no
    nested objects, LF only.
    """
    problems: list = []
    raw = path.read_bytes()
    where = rel(path)
    if b"\r" in raw:
        problems.append("%s: CRLF line endings: the header parser is a dumb line parser and requires LF" % where)
    lines = raw.decode("utf-8").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, problems + ["%s: does not open with a `---` front-matter fence" % where]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, problems + ["%s: the front-matter fence opened on line 1 and never closed" % where]
    values: dict = {}
    for offset, line in enumerate(lines[1:end], start=2):
        if not line.strip():
            continue
        if ":" not in line:
            problems.append("%s:%d front-matter line is not `key: value`: %r" % (where, offset, line[:60]))
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key in values:
            problems.append("%s:%d duplicate front-matter key %r" % (where, offset, key))
        if value[:1] in ("'", '"'):
            problems.append("%s:%d %r is quoted; front matter takes bare scalars" % (where, offset, value[:40]))
        if "#" in value:
            problems.append("%s:%d %r carries an inline comment; front matter takes one bare scalar per line" % (where, offset, value[:40]))
        if value[:1] in ("{", "["):
            problems.append("%s:%d %r looks nested; front matter takes one bare scalar per line" % (where, offset, value[:40]))
        values[key] = None if value == "null" else value
    return values, problems


def layer_of(path: Path) -> str:
    if path.parent == KB_DIR:
        return "root"
    return path.parent.name.lower()


# ---------------------------------------------------------------------------
# git, and the difference between "git is missing" and "verification disagreed"
# ---------------------------------------------------------------------------
def git_probe() -> tuple[bool, str]:
    """(available, why-not).  Never raises."""
    try:
        proc = subprocess.run(["git", "--version"], cwd=REPO, capture_output=True, text=True, check=False)
    except OSError as exc:
        return False, "the git binary could not be executed (%s)" % exc.__class__.__name__
    if proc.returncode != 0:
        return False, "git --version exited %d" % proc.returncode
    try:
        proc = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=REPO, capture_output=True, text=True, check=False)
    except OSError as exc:
        return False, "the git binary could not be executed (%s)" % exc.__class__.__name__
    if proc.returncode != 0:
        return False, "there is no git repository at %s" % REPO
    return True, ""


def git_run(args: list[str], purpose: str) -> tuple[bool, bytes, str]:
    """(ok, stdout, why-not) - git errors are data here, not exceptions."""
    try:
        proc = subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=False)
    except OSError as exc:
        return False, b"", "git unavailable: %s (%s)" % (purpose, exc.__class__.__name__)
    if proc.returncode != 0:
        return False, b"", "git %s failed (%d) while trying to %s: %s" % (
            " ".join(args),
            proc.returncode,
            purpose,
            proc.stderr.decode("utf-8", "replace").strip()[:200],
        )
    return True, proc.stdout, ""


def is_ancestor(commit: str, head: str) -> bool:
    if not commit or not SHA1.match(commit):
        return False
    if commit == head:
        return True
    ok, _out, _why = git_run(["merge-base", "--is-ancestor", commit, "HEAD"], "test ancestry of %s" % commit[:12])
    return ok


# ---------------------------------------------------------------------------
# span-aware tag scanning (C6)
# ---------------------------------------------------------------------------
def mask_inline(line: str) -> str:
    """Blank out inline code spans, preserving every offset."""
    out = list(line)
    index, length = 0, len(line)
    while index < length:
        if line[index] != "`":
            index += 1
            continue
        run = index
        while run < length and line[run] == "`":
            run += 1
        ticks = line[index:run]
        close = line.find(ticks, run)
        if close == -1:
            index = run
            continue
        for position in range(index, close + len(ticks)):
            out[position] = " "
        index = close + len(ticks)
    return "".join(out)


def mask_code(lines: list[str]) -> list[str]:
    """Blank out fenced blocks (``` or ~~~) and inline code spans, preserving
    offsets so a masked line and its source line share column numbers."""
    masked: list[str] = []
    fence = None
    for line in lines:
        stripped = line.lstrip()
        if fence is None and (stripped.startswith("```") or stripped.startswith("~~~")):
            fence = stripped[:3]
            masked.append(" " * len(line))
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            masked.append(" " * len(line))
            continue
        masked.append(mask_inline(line))
    return masked


def scan_tags(text: str, where: str = "<text>") -> tuple[list, list]:
    """[(name, body, line_number)], problems.  Tags parse anywhere in a line
    that is not a fenced block and not an inline code span."""
    lines = text.split("\n")
    masked = mask_code(lines)
    tags: list = []
    problems: list = []
    for number, masked_line in enumerate(masked, start=1):
        covered: list = []
        for match in TAG_CLOSED.finditer(masked_line):
            covered.append((match.start(), match.end()))
            tags.append((match.group(1), match.group(2), number))
        for match in TAG_OPEN.finditer(masked_line):
            if any(start <= match.start() < end for start, end in covered):
                continue
            problems.append("%s:%d unterminated [%s tag: no closing ']'" % (where, number, match.group(1)))
    return tags, problems


def masking_selftest() -> list:
    """The same tag must be found in prose and ignored inside a code span or a
    fenced block; an unterminated tag must be reported."""
    problems = []
    tag = "[measured src/emfit_core/state.py abcdef012345]"
    if len(scan_tags("the blob was %s at that commit" % tag)[0]) != 1:
        problems.append("A5 selftest: a tag standing in prose was not parsed")
    if scan_tags("write it as `%s` instead" % tag)[0]:
        problems.append("A5 selftest: a tag inside an inline code span was parsed")
    if scan_tags("```\n%s\n```" % tag)[0]:
        problems.append("A5 selftest: a tag inside a ``` fence was parsed")
    if scan_tags("~~~\n%s\n~~~" % tag)[0]:
        problems.append("A5 selftest: a tag inside a ~~~ fence was parsed")
    if not scan_tags("[measured src/x.py abcdef012345")[1]:
        problems.append("A5 selftest: an unterminated tag was not reported")
    return problems


def manifest() -> set:
    """The pinned test-id manifest: node ids only, ``#`` lines are the header."""
    if not COLLECTED_PATH.is_file():
        return set()
    out = set()
    for line in COLLECTED_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def tags_in_tree():
    for path in walked():
        found, problems = scan_tags(path.read_text(encoding="utf-8"), rel(path))
        for name, body, number in found:
            yield rel(path), number, name, body
        for problem in problems:
            yield rel(path), 0, "!", problem


def pins_shape_problems(pin: dict) -> list:
    problems = []
    if sorted(pin) not in (sorted(PINS_KEYS), sorted(PINS_KEYS + PINS_OPTIONAL_KEYS)):
        problems.append(
            "PINS.json keys %s != exactly %s (optionally plus %s)"
            % (sorted(pin), sorted(PINS_KEYS), list(PINS_OPTIONAL_KEYS))
        )
    if pin.get("schema") != SCHEMA:
        problems.append("PINS.schema %r is not the string %r" % (pin.get("schema"), SCHEMA))
    handoff = pin.get("core_handoff_id")
    if not isinstance(handoff, str) or not handoff:
        problems.append("PINS.core_handoff_id must be a non-empty string, got %r" % (handoff,))
    newest = pin.get("newest_commit_date")
    if newest is not None and not HEADER_DATE.match(str(newest)):
        problems.append("PINS.newest_commit_date %r is neither null nor an ISO date" % (newest,))
    baseline = pin.get("uncited_baseline")
    if not isinstance(baseline, int) or isinstance(baseline, bool):
        problems.append("PINS.uncited_baseline must be an integer, got %r" % (baseline,))
    entries = pin.get("files")
    if not isinstance(entries, list):
        problems.append("PINS.files must be a list of {path, sha256, layer} objects")
    else:
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                problems.append("PINS.files carries a non-object entry: %r" % (entry,))
                continue
            if sorted(entry) != ["layer", "path", "sha256"]:
                problems.append("PINS.files entry keys %s != ['layer', 'path', 'sha256']" % sorted(entry))
            path = entry.get("path")
            if not isinstance(path, str) or not path:
                problems.append("PINS.files entry without a path: %r" % (entry,))
                continue
            if path in seen:
                problems.append("PINS.files lists %r twice" % path)
            seen.add(path)
            if path == KB + "/PINS.json":
                problems.append("PINS.json pins itself; it cannot - its own bytes change when it is written")
            if entry.get("layer") not in PINS_FILE_LAYERS:
                problems.append("PINS.files[%r].layer %r is not one of %s" % (path, entry.get("layer"), PINS_FILE_LAYERS))
            digest = entry.get("sha256")
            if digest is not None and not SHA256.match(str(digest)):
                problems.append("PINS.files[%r].sha256 %r is neither null nor 64 lowercase hex" % (path, digest))
    if not isinstance(pin.get("claims"), list):
        problems.append("PINS.claims must be a list")
    return problems


# ---------------------------------------------------------------------------
# A1 .. A10
# ---------------------------------------------------------------------------
def test_a1_header_completeness():
    """Every markdown file under docs/kb opens with the nine-key `---` front
    matter (five content layers plus the root entry files), and PINS.json
    carries exactly its seven documented keys.  `pinned_commit` is either 40
    lowercase hex or the literal `null`, and `null` is tolerated on one state
    only: nothing pinned yet (`PINS.newest_commit_date` is null) on a header
    whose status is `current`.  A10 still stops a null pin surviving the first
    repin_kb.py run; A1 stops one being manufactured while it lasts."""
    problems: list = []
    pin = pins()
    problems += pins_shape_problems(pin)
    files = walked()
    if not files:
        problems.append("there is no markdown under docs/kb: the tree has nothing to gate")
    for path in files:
        where = rel(path)
        head, probs = front_matter(path)
        problems += probs
        if not head:
            continue
        for key in HEADER_KEYS:
            if key not in head:
                problems.append("%s: front matter is missing the required key %r" % (where, key))
        for key in head:
            if key in CORE_ONLY_KEYS or key in HEADER_KEYS:
                continue
            problems.append("%s: front matter carries the undocumented key %r" % (where, key))
        expected = layer_of(path)
        layer = head.get("layer")
        if expected not in ALL_LAYERS:
            problems.append("%s: sits under docs/kb/%s/, which is not one of the six layers %s" % (where, expected, ALL_LAYERS))
        elif layer is not None and layer != expected:
            problems.append("%s: layer %r != the directory it sits in (%r)" % (where, layer, expected))
        status = head.get("status")
        if status is not None and status not in STATUSES:
            problems.append("%s: status %r is not one of %s" % (where, status, STATUSES))
        commit = head.get("pinned_commit", "missing")
        if commit == "missing":
            pass
        elif commit is not None and not SHA1.match(str(commit)):
            problems.append("%s: pinned_commit %r is neither 40 lowercase hex nor null; a header names the commit its bytes were pinned at, and null is legal only until the first repin_kb.py run" % (where, commit))
        else:
            # the null-tolerance is a status-keyed bootstrap, not a fallback: only a
            # `current` header may ride the window in which nothing is pinned yet.
            tolerates_null = {"current": pin.get("newest_commit_date") is None}
            if commit is None and not tolerates_null.get(status, False):
                problems.append(
                    "%s: pinned_commit null is a fabrication on a status %r header with "
                    "PINS.newest_commit_date %r - null is legal only in the bootstrap state "
                    "(nothing pinned yet, status current), never as a fallback"
                    % (where, status, pin.get("newest_commit_date"))
                )
        budget = head.get("byte_budget")
        if budget is not None and (not str(budget).isdigit() or int(budget) <= 0):
            problems.append("%s: byte_budget %r is not a positive integer" % (where, budget))
        for key in ("pinned_at", "last_verified"):
            value = head.get(key, "missing")
            if value not in ("missing", None) and not HEADER_DATE.match(str(value)):
                problems.append("%s: %s %r is neither null nor an ISO date" % (where, key, value))
        if head.get("reads_when") == "":
            problems.append("%s: reads_when is empty; say when a session must read this" % where)
        handoff = head.get("core_handoff_id")
        if layer == "core":
            if handoff is None:
                problems.append("%s: layer core must carry core_handoff_id" % where)
            elif handoff != pin.get("core_handoff_id"):
                problems.append("%s: core_handoff_id %r != PINS.core_handoff_id %r" % (where, handoff, pin.get("core_handoff_id")))
        elif handoff is not None:
            problems.append("%s: core_handoff_id is allowed on layer: core only, not on %r" % (where, layer))
    assert not problems, "A1 FAIL: header problems:\n  " + "\n  ".join(problems)


def test_a2_self_pins():
    """PINS.files[].sha256 is the sha256 of the **canonical** HEAD blob and of the
    **canonical** working file: ``scripts/kb_canonical.py`` masks the three
    front-matter provenance values and touches nothing else.  A pin names the
    content at a commit - not the header ``scripts/repin_kb.py`` itself rewrites -
    so an unpinned or silently edited file is red, and a freshly re-pinned tree is
    not.  The sub-case is coverage: a file that exists under ``docs/kb`` (or the
    manifest) but was never listed in ``PINS.files[]`` is red too - iterating the
    entries cannot see a file nobody added, which is how one escapes pinning."""
    available, why = git_probe()
    if not available:
        pytest.fail(
            "A2 FAIL: git unavailable: cannot verify self-pin sha256 - %s. A2 compares "
            "PINS.files[].sha256 against `git show HEAD:<path>`; run this gate on a "
            "git-capable host." % why
        )
    pin = pins()
    problems: list = []
    entries = pin.get("files") or []
    if not entries:
        problems.append("PINS.files is empty: nothing is pinned, so nothing is guarded")
    verified = 0
    for entry in entries:
        path = entry.get("path", "<no path>")
        digest = entry.get("sha256")
        if not digest:
            problems.append("%s: unpinned (sha256 null) - run scripts/repin_kb.py after the content commit" % path)
            continue
        ok, blob, why = git_run(["show", "HEAD:%s" % path], "read the HEAD blob of %s" % path)
        if not ok:
            problems.append("%s: %s" % (path, why))
            continue
        actual = hashlib.sha256(canonical_bytes(blob)).hexdigest()
        if actual != digest:
            problems.append(
                "%s: HEAD blob canonical sha256 %s != pinned %s - the content committed at "
                "HEAD is not what PINS.json pinned; run scripts/repin_kb.py after the "
                "content commit" % (path, actual[:16], digest[:16])
            )
            continue
        target = REPO / path
        if not target.is_file():
            problems.append("%s: pinned but absent from the working tree" % path)
            continue
        working = hashlib.sha256(canonical_bytes(target.read_bytes())).hexdigest()
        if working != digest:
            problems.append(
                "%s: working-tree canonical sha256 %s != pinned %s - the file on disk is not "
                "what PINS.json pinned (edited without re-pinning, or the tree is dirty: A4)"
                % (path, working[:16], digest[:16])
            )
            continue
        verified += 1
    # Sub-case: coverage.  ``scripts/repin_kb.py`` pins every markdown file under
    # docs/kb plus tests/COLLECTED.txt; the loop above can only see the entries
    # that exist, so a file nobody listed is unpinned and green.  Compare the pin
    # set against what has to be pinned.
    pinned = {entry.get("path") for entry in entries if isinstance(entry, dict)}
    expected = {rel(path) for path in walked()} | {rel(COLLECTED_PATH)}
    for missing in sorted(expected - pinned):
        problems.append(
            "%s: exists but is not in PINS.files - an unlisted file is unpinned, and a pin that "
            "was never written is not a pin; run scripts/repin_kb.py" % missing
        )
    assert not problems, "A2 FAIL: self-pin verification ran and disagreed with PINS.json:\n  " + "\n  ".join(problems)
    print("A2 ok: %d self-pins match HEAD and the working tree (canonical form)" % verified)


def test_a3_budgets():
    """Per-file caps come from each file's own header (the single source of
    truth); per-layer and total caps come from PINS.budgets, with archive and
    reference deliberately unbudgeted, plus the `test_manifest` tier for the
    manifest that lives outside docs/kb/ and feeds A6: the same fail/warn pair
    shape `core`/`core_warn` uses, so a growing manifest warns before it fails."""
    pin = pins()
    budgets = pin.get("budgets") or {}
    problems: list = []
    warnings: list = []
    if sorted(budgets) != sorted(BUDGET_KEYS):
        problems.append(
            "PINS.budgets keys %s != %s: archive and reference are unbudgeted, so no "
            "ROOT/ARCHIVE/REFERENCE block may exist" % (sorted(budgets), sorted(BUDGET_KEYS))
        )
    layer_sum = {layer: 0 for layer in CONTENT_LAYERS}
    ingest = {KB + "/README.md", KB + "/PROCEDURE.md", KB + "/PINS.json"}
    for path in walked():
        size = len(path.read_bytes())
        layer = layer_of(path)
        if layer in layer_sum:
            layer_sum[layer] += size
        if layer in ("core", "registry"):
            ingest.add(rel(path))
        head, _probs = front_matter(path)
        cap = head.get("byte_budget")
        if cap is not None and str(cap).isdigit():
            if size > int(cap):
                problems.append("%s: %d B over its own header byte_budget of %d B" % (rel(path), size, int(cap)))
        elif layer == "core":
            default = int(budgets.get("per_file_core_default") or 0)
            if default and size > default:
                problems.append("%s: %d B over the %d B per-file core default" % (rel(path), size, default))
    manifest_cap = int(budgets.get("test_manifest") or 0)
    manifest_warn = int(budgets.get("test_manifest_warn") or 0)
    if manifest_cap:
        if not COLLECTED_PATH.is_file():
            problems.append("tests/COLLECTED.txt is missing: A6 resolves every [FIXED-TESTED] against it")
        else:
            manifest_size = len(COLLECTED_PATH.read_bytes())
            if manifest_size > manifest_cap:
                problems.append(
                    "tests/COLLECTED.txt: %d B over the %d B test_manifest cap - a manifest nobody "
                    "reads is not worth its bytes; regenerate it in the same commit that cites it"
                    % (manifest_size, manifest_cap)
                )
            elif manifest_warn and manifest_size > manifest_warn:
                warnings.append(
                    "tests/COLLECTED.txt is %d B, past the %d B warning line"
                    % (manifest_size, manifest_warn)
                )
    total = sum(len((REPO / name).read_bytes()) for name in sorted(ingest))
    for layer, cap_name in (("core", "core"), ("registry", "registry"), ("work", "work")):
        cap = int(budgets.get(cap_name) or 0)
        if cap and layer_sum[layer] > cap:
            problems.append("layer %s: %d B over its %d B cap" % (layer, layer_sum[layer], cap))
    core_warn = int(budgets.get("core_warn") or 0)
    if core_warn and layer_sum["core"] > core_warn:
        warnings.append("core is %d B, past the %d B warning line" % (layer_sum["core"], core_warn))
    total_cap = int(budgets.get("total_ingest") or 0)
    warn_at = float(budgets.get("warn_at") or 0.85)
    if total_cap and total > total_cap:
        problems.append("ingest is %d B over the %d B total cap" % (total, total_cap))
    elif total_cap and total > total_cap * warn_at:
        warnings.append("ingest is %d B, past %d%% of the %d B cap" % (total, int(100 * warn_at), total_cap))
    assert not problems, "A3 FAIL: budget problems:\n  " + "\n  ".join(problems)
    if warnings:
        print("WARN: " + "; ".join(warnings))
    print(
        "A3 ok: ingest %d/%d B, core %d/%d B, registry %d/%d B, work %d/%d B"
        % (total, total_cap, layer_sum["core"], int(budgets.get("core") or 0),
           layer_sum["registry"], int(budgets.get("registry") or 0),
           layer_sum["work"], int(budgets.get("work") or 0))
    )


def test_a4_tree_clean():
    """docs/kb is exactly its tracked files: `git status --porcelain docs/kb` is
    strictly empty, everything walked is tracked, and the five content
    directories exist carrying a .gitkeep and no README stub."""
    problems: list = []
    for layer in CONTENT_LAYERS:
        # the directory name is the layer's uppercase spelling; ``layer`` in the
        # header is that name lowercased, which is what A1 compares.
        name = layer.upper()
        directory = KB_DIR / name
        if not directory.is_dir():
            problems.append("docs/kb/%s/ is missing: the five content layers are fixed" % name)
            continue
        if not (directory / ".gitkeep").is_file():
            problems.append("docs/kb/%s/.gitkeep is missing: an empty layer must still exist in git" % name)
        if (directory / "README.md").exists():
            problems.append("docs/kb/%s/README.md is a stub; entry text belongs in docs/kb/README.md" % name)
    available, why = git_probe()
    if not available:
        if problems:
            raise AssertionError("A4 FAIL: tree problems:\n  " + "\n  ".join(problems))
        pytest.fail(
            "A4 FAIL: git unavailable: cannot check that `git status --porcelain docs/kb` is "
            "empty - %s. A4 is what makes a HEAD-blob pin mean 'the bytes you are reading "
            "are the bytes that were pinned'; run this gate on a git-capable host." % why
        )
    ok, out, why = git_run(["status", "--porcelain", "--", KB], "check that docs/kb is clean")
    if not ok:
        problems.append(why)
    else:
        dirty = [line for line in out.decode("utf-8", "replace").splitlines() if line.strip()]
        if dirty:
            problems.append("git status --porcelain docs/kb is not strictly empty: %s" % dirty[:10])
    ok, out, why = git_run(["ls-files", "--", KB], "list the files tracked under docs/kb")
    if not ok:
        problems.append(why)
    else:
        listed = set(out.decode("utf-8", "replace").splitlines())
        for path in walked():
            if rel(path) not in listed:
                problems.append("%s: walked but not tracked" % rel(path))
        for layer in CONTENT_LAYERS:
            keep = "%s/%s/.gitkeep" % (KB, layer.upper())
            if (KB_DIR / layer.upper() / ".gitkeep").is_file() and keep not in listed:
                problems.append("%s: present but not tracked" % keep)
    assert not problems, "A4 FAIL: tree problems:\n  " + "\n  ".join(problems)
    print("A4 ok: docs/kb is clean and fully tracked")


def test_a5_tag_grammar():
    """Bracketed tags parse anywhere except inside inline code spans and fenced
    blocks, each body matches its documented shape, and [UNCITED] carries the
    why: line that makes it a recorded debt."""
    problems: list = masking_selftest()
    tags = 0
    for path in walked():
        text = path.read_text(encoding="utf-8")
        found, probs = scan_tags(text, rel(path))
        problems += probs
        lines = text.split("\n")
        for name, body, number in found:
            tags += 1
            pattern = TAG_BODIES[name]
            if not pattern.match(body):
                problems.append(
                    "%s:%d malformed [%s%s]: the body must match %s" % (rel(path), number, name, body[:48], pattern.pattern)
                )
                continue
            if name == "UNCITED":
                follow = [line for line in lines[number:number + 3] if line.strip()]
                if not follow or "why:" not in follow[0]:
                    problems.append("%s:%d [UNCITED] without a why: line on the line that follows it" % (rel(path), number))
    assert not problems, "A5 FAIL: tag problems:\n  " + "\n  ".join(problems)
    print("A5 ok: %d tags parsed, masking self-test passed" % tags)


def test_a6_fixed_tested_resolves():
    """[FIXED-TESTED <path>::<name>] resolves by MEMBERSHIP in the pinned
    tests/COLLECTED.txt manifest, never by a grep for `def`."""
    pinned = manifest()
    problems: list = []
    if not pinned:
        problems.append("tests/COLLECTED.txt is missing or holds no node ids: A6 would be vacuous")
    cited = 0
    for path in walked():
        found, probs = scan_tags(path.read_text(encoding="utf-8"), rel(path))
        problems += probs
        for name, body, number in found:
            if name != "FIXED-TESTED":
                continue
            cited += 1
            node = body.strip()
            if node not in pinned:
                problems.append("%s:%d [FIXED-TESTED %s] is not a node id in tests/COLLECTED.txt" % (rel(path), number, node))
    assert not problems, "A6 FAIL: unresolved [FIXED-TESTED] citations:\n  " + "\n  ".join(problems)
    print("A6 ok: %d [FIXED-TESTED] citations resolved against %d manifest node ids" % (cited, len(pinned)))


def test_a7_measured_resolves():
    """[measured <tracked path> <12+ hex>] must match the sha256 of that path's
    HEAD blob and [CITED <tracked path>:<line>] must land inside it; with no
    such tags the evaluation is empty and still real."""
    entries: list = []
    problems: list = []
    for path in walked():
        found, probs = scan_tags(path.read_text(encoding="utf-8"), rel(path))
        problems += probs
        for name, body, number in found:
            if name in ("measured", "CITED"):
                entries.append((rel(path), number, name, body))
    if not entries:
        print("A7 ok: 0 claims evaluated, 0 pinned")
        assert not problems, "A7 FAIL: tag problems:\n  " + "\n  ".join(problems)
        return
    available, why = git_probe()
    if not available:
        pytest.fail(
            "A7 FAIL: git unavailable: cannot resolve %d [measured]/[CITED] tags against HEAD "
            "blobs - %s. A7 reads blobs with `git show HEAD:<path>`; run this gate on a "
            "git-capable host." % (len(entries), why)
        )
    ok, out, why = git_run(["ls-tree", "-r", "--name-only", "HEAD"], "list the files tracked at HEAD")
    tracked = set(out.decode("utf-8", "replace").splitlines()) if ok else set()
    if not ok:
        problems.append(why)
    resolved = 0
    for where, number, name, body in entries:
        if name == "measured":
            target, digest = body.split()
        else:
            target, _, line_no = body.strip().partition(":")
        if target not in tracked:
            problems.append("%s:%d [%s] %s is not tracked at HEAD" % (where, number, name, target))
            continue
        ok, blob, why = git_run(["show", "HEAD:%s" % target], "read the HEAD blob of %s" % target)
        if not ok:
            problems.append("%s:%d %s" % (where, number, why))
            continue
        if name == "measured":
            actual = hashlib.sha256(blob).hexdigest()
            if not actual.startswith(digest):
                problems.append("%s:%d [measured %s %s] but the HEAD blob's sha256 is %s" % (where, number, target, digest, actual[:12]))
                continue
        else:
            total = len(blob.splitlines())
            if not 1 <= int(line_no) <= total:
                problems.append("%s:%d [CITED %s:%s] but the HEAD blob has %d lines" % (where, number, target, line_no, total))
                continue
        resolved += 1
    assert not problems, "A7 FAIL: evidence tags did not resolve:\n  " + "\n  ".join(problems)
    print("A7 ok: %d claims evaluated, %d pinned" % (len(entries), resolved))


def test_a8_claims_resolve():
    """Each PINS.claims entry names a commit that is still an ancestor of HEAD
    and a required_token that is an exact substring of the source blob at that
    commit; a printed float is refused as a token."""
    pin = pins()
    claims = pin.get("claims") or []
    if not claims:
        print("A8 ok: 0 claims evaluated, 0 pinned")
        return
    available, why = git_probe()
    if not available:
        pytest.fail(
            "A8 FAIL: git unavailable: cannot resolve %d registered claims - %s. A8 reads "
            "`git show <pin_commit>:<source_path>`; run this gate on a git-capable host."
            % (len(claims), why)
        )
    ok, out, why = git_run(["rev-parse", "HEAD"], "resolve HEAD")
    if not ok:
        pytest.fail("A8 FAIL: git ran but could not resolve HEAD: %s" % why)
    head = out.decode().strip()
    problems: list = []
    for claim in claims:
        cid = claim.get("id") or "<no id>"
        missing = [key for key in ("id", "text", "tag", "source_path", "pin_commit", "required_token") if not claim.get(key)]
        if missing:
            problems.append("%s: missing %s" % (cid, ", ".join(missing)))
            continue
        token = claim["required_token"]
        if FLOAT_TOKEN.match(token):
            problems.append("%s: float-print token %r refused: a printed float is not evidence" % (cid, token))
            continue
        commit = claim["pin_commit"]
        if not is_ancestor(commit, head):
            problems.append("%s: %s is not an ancestor of HEAD" % (cid, commit[:12]))
            continue
        ok, blob, why = git_run(["show", "%s:%s" % (commit, claim["source_path"])], "read %s at %s" % (claim["source_path"], commit[:12]))
        if not ok:
            problems.append("%s: %s" % (cid, why))
            continue
        if token.encode() not in blob:
            problems.append("%s: %r is absent from %s at %s" % (cid, token, claim["source_path"], commit[:12]))
    assert not problems, "A8 FAIL: claims did not resolve:\n  " + "\n  ".join(problems)
    print("A8 ok: %d claims evaluated, %d pinned" % (len(claims), len(claims)))


def test_a9_uncited_baseline():
    """The number of live [UNCITED] tags never exceeds PINS.uncited_baseline:
    an uncited claim is a counted debt, not a free pass."""
    pin = pins()
    baseline = int(pin.get("uncited_baseline") or 0)
    count = 0
    where: list = []
    for path in walked():
        found, _probs = scan_tags(path.read_text(encoding="utf-8"), rel(path))
        for name, _body, number in found:
            if name == "UNCITED":
                count += 1
                where.append("%s:%d" % (rel(path), number))
    assert count <= baseline, (
        "A9 FAIL: %d [UNCITED] tags over the PINS.uncited_baseline of %d (%s). Close the "
        "claim, or raise the baseline in a reviewed PINS.json change." % (count, baseline, ", ".join(where))
    )
    print("A9 ok: %d [UNCITED] tags, baseline %d" % (count, baseline))


def test_a10_staleness():
    """A10 is the staleness assertion and the pin ratchet, keyed on a commit.

    Once ``PINS.newest_commit`` names a commit, no non-root header may keep
    ``pinned_commit: null`` - a surviving null is a hard failure naming the
    path - and every source pin (``PINS.newest_commit``, ``claims[].pin_commit``
    and each non-root header's ``pinned_commit``) must be an ancestor of HEAD,
    inside the 14-day window measured on that commit's own committer date, with
    pin..HEAD distance warning at 20 and failing at 50 - so a distance of 1 is a
    normal, green state.  ``PINS.newest_commit_date`` is informational only:
    asserting a ``%cI`` string would be unsatisfiable together with A4, since
    re-pinning happens before the commit that makes the tree clean.  While
    ``newest_commit`` is absent or null the pins have simply not been generated
    yet: A10 says exactly that and names the command that generates them,
    instead of reporting a stale tree."""
    available, why = git_probe()
    if not available:
        pytest.fail(
            "A10 FAIL: git unavailable: cannot resolve commit ancestry or the newest-commit "
            "date - %s. A10 is the staleness assertion and needs history; run this gate on a "
            "git-capable host." % why
        )
    pin = pins()
    stamped = pin.get("newest_commit")
    if stamped is None:
        pytest.fail(
            "A10 FAIL: pins have not been generated yet (PINS.newest_commit is %r) - run "
            "python3 scripts/repin_kb.py on a git-capable host" % (stamped,)
        )
    if not SHA1.match(str(stamped)):
        pytest.fail(
            "A10 FAIL: PINS.newest_commit %r is not a 40-character lowercase hex sha - run "
            "python3 scripts/repin_kb.py on a git-capable host" % (stamped,)
        )
    stamped = str(stamped)
    problems: list = []
    warnings: list = []
    ok, out, why = git_run(["rev-parse", "HEAD"], "resolve HEAD")
    if not ok:
        pytest.fail("A10 FAIL: git ran but could not resolve HEAD: %s" % why)
    head = out.decode().strip()
    bases: list = []
    if is_ancestor(stamped, head):
        bases.append(stamped)
    else:
        problems.append(
            "PINS.newest_commit %s is not an ancestor of HEAD: the pin names a commit this "
            "history does not contain (rewritten history, or commits landed without "
            "scripts/repin_kb.py)" % stamped[:12]
        )
    for claim in pin.get("claims") or []:
        cid = claim.get("id") or "<no id>"
        commit = claim.get("pin_commit") or ""
        if is_ancestor(commit, head):
            bases.append(commit)
        else:
            problems.append("claim %s: pin_commit %r is not an ancestor of HEAD (rewritten history or absent commit)" % (cid, commit))
    for path in walked():
        head_fm, _probs = front_matter(path)
        commit = head_fm.get("pinned_commit")
        if commit is None:
            if head_fm.get("layer") != "root":
                problems.append(
                    "%s: header pinned_commit is null although PINS.newest_commit is %s; a null pin is "
                    "legal only before the first scripts/repin_kb.py run, and that run has happened "
                    "(scripts/repin_kb.py --patch-headers fixes it)" % (rel(path), stamped[:12])
                )
            continue
        if is_ancestor(commit, head):
            bases.append(commit)
        else:
            problems.append("%s: header pinned_commit %r is not an ancestor of HEAD; the header names a commit this history does not contain (scripts/repin_kb.py --patch-headers fixes it)" % (rel(path), commit))
    ok, out, why = git_run(
        ["log", "-1", "--format=%cI", stamped],
        "read the committer date of PINS.newest_commit %s" % stamped[:12],
    )
    age = None
    if not ok:
        problems.append(why)
    else:
        pinned_date = out.decode().strip()
        try:
            age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(pinned_date)).days
        except ValueError:
            problems.append(
                "the committer date %r of PINS.newest_commit %s is not ISO 8601" % (pinned_date, stamped[:12])
            )
        if age is not None and age > STALE_DAYS:
            problems.append(
                "PINS.newest_commit %s was committed %d days ago (%s), past the %d-day freshness "
                "window: re-verify the KB against the code, then re-pin"
                % (stamped[:12], age, pinned_date, STALE_DAYS)
            )
    for commit in sorted(set(bases)):
        ok, out, why = git_run(["rev-list", "--count", "%s..HEAD" % commit], "measure the pin..HEAD distance from %s" % commit[:12])
        if not ok:
            problems.append(why)
            continue
        ahead = int(out.decode().strip() or 0)
        if ahead >= STALE_FAIL_AHEAD:
            problems.append("pin..HEAD distance from %s is %d, at or past %d: the pins describe history this tree has left behind" % (commit[:12], ahead, STALE_FAIL_AHEAD))
        elif ahead >= STALE_WARN_AHEAD:
            warnings.append("pin..HEAD distance from %s is %d (warn at %d): re-pin" % (commit[:12], ahead, STALE_WARN_AHEAD))
    assert not problems, "A10 FAIL: staleness problems:\n  " + "\n  ".join(problems)
    if warnings:
        print("WARN: " + "; ".join(warnings))
    print("A10 ok: %d source pins audited, newest_commit %s is %s days old" % (len(set(bases)), stamped[:12], age if age is not None else "?"))
