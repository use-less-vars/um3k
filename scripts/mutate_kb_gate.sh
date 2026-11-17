#!/usr/bin/env bash
# Prove the KB gate is not vacuous: five mutations, five reds, five greens again.
#
# Each mutation targets exactly one assertion, runs exactly that node id, prints
# the result, restores the file from a backup and re-runs the same node id to
# prove the tree is green again before the next mutation.  Nothing here commits.
#
# Exit codes: 0 = all five mutations were caught and every restore was green;
#             3 = the gate was not green to begin with (nothing is mutated);
#             1 = a mutation went uncaught, or a restore left the gate red.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY="${PYTHON:-python3}"
GATE_TEST="tests/test_kb_integrity.py"
M1_NODE="$GATE_TEST::test_a1_header_completeness"
M2_NODE="$GATE_TEST::test_a2_self_pins"
M3_NODE="$GATE_TEST::test_a6_fixed_tested_resolves"
M4_NODE="$GATE_TEST::test_a9_uncited_baseline"
M5_NODE="$GATE_TEST::test_a10_staleness"

BACKUP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mutate_kb_gate.XXXXXX")"
trap 'restore_all; rm -rf "$BACKUP_DIR"' EXIT

restore_all() {
    if [[ -f "$BACKUP_DIR/README.md" ]]; then cp -p "$BACKUP_DIR/README.md" docs/kb/README.md; fi
    if [[ -f "$BACKUP_DIR/decisions.md" ]]; then cp -p "$BACKUP_DIR/decisions.md" docs/kb/REGISTRY/decisions.md; fi
    if [[ -f "$BACKUP_DIR/PINS.json" ]]; then cp -p "$BACKUP_DIR/PINS.json" docs/kb/PINS.json; fi
}

green() { "$PY" -m pytest "$GATE_TEST" -q >/dev/null 2>&1; }

say() { printf '%s\n' "$*"; }

# ---------------------------------------------------------------- guard
if ! green; then
    say "REFUSING: the gate is not currently green; a mutation proves nothing on a red tree."
    say "Fix the gate first (A2/A4/A10 must be red only for a missing git, on a pristine checkout)."
    exit 3
fi
say "gate is green: starting five mutations"

cp -p docs/kb/README.md              "$BACKUP_DIR/README.md"
cp -p docs/kb/REGISTRY/decisions.md  "$BACKUP_DIR/decisions.md"
cp -p docs/kb/PINS.json              "$BACKUP_DIR/PINS.json"

# ---------------------------------------------------------------- helpers
expect_red() { # $1 node id, $2 mutation name
    if "$PY" -m pytest "$1" -q >"$BACKUP_DIR/out.txt" 2>&1; then
        say "MUTATION $2 NOT CAUGHT: $1 stayed green"
        return 1
    fi
    say "  $2 caught: $1 red"
    return 0
}

expect_green() { # $1 node id, $2 mutation name
    if "$PY" -m pytest "$1" -q >"$BACKUP_DIR/out.txt" 2>&1; then
        say "  $2 restored: $1 green"
        return 0
    fi
    say "RESTORE FAILED: $1 is still red after restoring $2"
    cat "$BACKUP_DIR/out.txt"
    return 1
}

cycle() { # $1 label, $2 node id, $3 mutation command
    say "--- $1"
    eval "$3"
    expect_red "$2" "$1"
    restore_all
    expect_green "$2" "$1"
}

# ---------------------------------------------------------------- M1 .. M5
# M1: delete the `reads_when:` line from the registry index -> A1 (required key).
cycle "M1 drop reads_when" "$M1_NODE" \
  "\"$PY\" - <<'EOF'
from pathlib import Path
p = Path('docs/kb/REGISTRY/decisions.md')
lines = [l for l in p.read_text().split(chr(10)) if not l.startswith('reads_when:')]
p.write_text(chr(10).join(lines))
EOF"

# M2: append to the README body only, header untouched -> A2 (working-tree pin).
cycle "M2 append to README" "$M2_NODE" \
  "printf '\n<!-- x -->\n' >> docs/kb/README.md"

# M3: a [FIXED-TESTED] node id that cannot be collected -> A6 (manifest membership).
cycle "M3 fake FIXED-TESTED" "$M3_NODE" \
  "printf '\n[FIXED-TESTED tests/test_deleted.py::nonexistent_test]\n' >> docs/kb/README.md"

# M4: one live [UNCITED] over the baseline of zero -> A9.
cycle "M4 uncited over baseline" "$M4_NODE" \
  "printf '\n[UNCITED]\nwhy: mutation M4, no evidence recorded\n' >> docs/kb/README.md"

# M5: a claim whose pin_commit is forty zeros -> A10 (ancestry).
cycle "M5 forty-zero pin_commit" "$M5_NODE" \
  "\"$PY\" - <<'EOF'
import json
from pathlib import Path
p = Path('docs/kb/PINS.json')
pin = json.loads(p.read_text())
pin['claims'].append({
    'id': 'M5-mutation',
    'text': 'a claim that names a commit which cannot exist',
    'tag': 'measured',
    'source_path': 'docs/kb/README.md',
    'pin_commit': '0' * 40,
    'required_token': 'docs/kb',
})
p.write_text(json.dumps(pin, indent=2) + chr(10))
EOF"

# ---------------------------------------------------------------- done
restore_all
if ! green; then
    say "FAIL: the gate is not green after all five restores"
    exit 1
fi
say "ok: five mutations, five reds, five restores green"
