---
status: current
layer: root
pinned_commit: c6195cfb33e94a289ccabd8d5675bd7ff41d03c9
pinned_at: 2026-11-19
byte_budget: 6144
last_verified: 2026-11-19
reads_when: before you run the gate or scripts/repin_kb.py, or commit anything under docs/kb, on a host that has git
supersedes: null
superseded_by: null
---

# docs/kb/RUNBOOK.md — the five host commands, in order

`docs/kb/PROCEDURE.md` is the authority for what the gate checks and why; this
file is only the order of operations on a host that has git and a repository.
Read them the other way round and the order looks arbitrary; the procedure is
what makes it mandatory.

## The five commands

Run them from the repository root, in this order, and do not reorder them:

1. `git status --porcelain docs/kb` — must be **empty** before anything else.
   Every pin below describes committed bytes, so uncommitted content has to land
   first; a dirty `docs/kb` is not pinnable.
2. `git add -A && git commit -m "kb: content"` — the content commit. It is the
   commit the pins are computed from, and there is nothing to pin before it
   exists.
3. `python3 scripts/repin_kb.py` — writes `docs/kb/PINS.json` and patches
   `pinned_commit`, `pinned_at` and `last_verified` to HEAD and today in every
   header, root files included. Afterwards `docs/kb` is dirty **on purpose**: the
   pins describe the commit from step 2, not the tree step 3 just changed.
4. `git add -A && git commit -m "kb: pins"` — the pin commit. Two commits, not
   one: a pin has to be computed from a commit that already exists, and the bytes
   it describes have to be committed before the tree is clean again.
5. `python -m pytest tests/test_kb_integrity.py -q` — the gate, run only here,
   against the tree step 4 made clean. A run before that answers a different
   question than the one you are asking.

`python3 scripts/repin_kb.py --check` reports drift and writes nothing; it is the
safe way to ask "am I still pinned?" between steps.

## TRAP: `repin_kb.write_pins()` exits 2 on a dirty `docs/kb`

`scripts/repin_kb.py` refuses to write pins while `git status --porcelain docs/kb`
is non-empty: `write_pins()` prints `docs/kb is dirty; commit the content first`
to stderr and returns **2**, so the shell sees `$?` = 2 and `set -e` stops the
run there. That status is step 1 enforced by the tool, not an error to work
around:

- Do **not** reach for `--force`. It pins the HEAD blobs while the working tree
  still differs, so A2's working-tree side goes red on the next run and the pin
  describes bytes nobody committed.
- Do **not** run a plain `repin_kb.py` before the content commit to "see what
  changes". `--check` is that command, and it writes nothing.
- If step 3 changed a header you never touched, that is the header patch doing
  its job. Commit it in step 4; reverting it leaves A10 reporting the null pin it
  was fixing.

None of this is a bypass: the escape hatches are PROCEDURE section 11, and step 5
is still the only command here that decides anything.
