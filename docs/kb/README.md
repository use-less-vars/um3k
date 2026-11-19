---
status: current
layer: root
pinned_commit: 36c71d3eaaecf9ee04857dac2d68b04ba5ab97ef
pinned_at: 2026-11-18
byte_budget: 8192
last_verified: 2026-11-18
reads_when: always - the first file any session reads before it opens a single kb file
supersedes: null
superseded_by: null
---

# docs/kb — the knowledge base, and the gate that keeps it honest

This is not a folder of notes. It is six layers, a machine-readable pin
file, and one command that decides whether the whole thing is trustworthy:

```
python -m pytest tests/test_kb_integrity.py -q
```

Everything below answers one question: *which bytes may I rely on, and as of
which commit?*

## What this tree is working on now

Phase 1, the truthful UI: DR-47 re-baseline, so that a Trame `@state.change`
handler actually fires under `_boot_app` and a slider move provably redraws
instead of silently changing nothing. The order of what follows is in
`docs/design/defect_register.md` and `docs/kb/REGISTRY/decisions.md`; this
paragraph is the pointer, not the plan.

## The six layers

Five content layers, each a fixed directory name, plus the root entry files.

| layer | directory | holds | budget |
|---|---|---|---|
| `core` | `docs/kb/CORE/` | the few files every session must read before touching code | 45 KiB (46,080 B) hard, 38 KiB (38,912 B) warn, 9 KiB (9,216 B) per file |
| `registry` | `docs/kb/REGISTRY/` | indexes whose rows point at authority that lives elsewhere | 30 KiB (30,720 B) |
| `work` | `docs/kb/WORK/` | in-flight, dated work notes | 20 KiB (20,480 B) |
| `archive` | `docs/kb/ARCHIVE/` | superseded text kept only so citations keep resolving | unbudgeted |
| `reference` | `docs/kb/REFERENCE/` | external material, copied rather than linked | unbudgeted |
| `root` | `docs/kb/*.md` | this file and `PROCEDURE.md` | each file's own header |

`archive` and `reference` are deliberately unbudgeted: they are read rarely and
may be large. The three budgeted layers are capped per layer *and*
per file: a layer cap alone lets one file eat the layer.

The directory name is the layer: `docs/kb/CORE/x.md` must declare
`layer: core`, and a root file must declare `layer: root`. A1 checks the
equality; nothing here is decided by a registry inside a script.

## The three root files

| file | what it is | who writes it |
|---|---|---|
| `docs/kb/README.md` | this orientation; the layer map and the tag rule | a human, rarely |
| `docs/kb/PROCEDURE.md` | the authoritative procedure: budgets, header syntax, tags, rituals, escape hatches | a human, deliberately |
| `docs/kb/PINS.json` | the machine-readable pins: budgets, self-pin sha256s, registered claims | `scripts/repin_kb.py`, never by hand |

`PINS.json` is the one file in the tree that carries **no front matter**. It is
not markdown and it is never pinned by itself — its own bytes change every time
it is written, so a self-pin inside it could never be true.

## Tags: bracketed, resolvable, or counted

A claim about the code that is worth checking is written as a bracketed token,
`[NAME body]`. The bracket is part of the syntax, which is exactly what keeps
the ordinary English words "measured" and "closed" out of the grammar: prose
may use them freely, and only a bracketed token is a claim.

| tag | body | resolves against |
|---|---|---|
| `[VERIFIED-BY-RUN <commit> <command>]` | 7-40 hex commit, then the command | a re-run on a git-capable host |
| `[FIXED-TESTED <path>::<test>]` | a node id | membership in `tests/COLLECTED.txt` |
| `[measured <path> <sha256 prefix>]` | tracked path, 12+ hex | the sha256 of that path's HEAD blob |
| `[closed <gate>]` | a gate name | a human re-reading the gate |
| `[CITED <path>:<line>]` | tracked path and line | that line number inside the HEAD blob |
| `[UNCITED]` | nothing | nothing — it is a recorded debt, counting against `PINS.uncited_baseline` |

Tags parse in prose, but **not** inside an inline `` `code span` `` and not
inside a fenced block. That is how this file can spell the grammar out without
claiming anything: a tag shown as an example is backticked, and a backticked
tag is invisible to the scanner.

Here is a live one, on its own line, resolving through the manifest:

[FIXED-TESTED tests/test_kb_integrity.py::test_a6_fixed_tested_resolves]

An `[UNCITED]` is the only tag that must carry a companion line, and the line
after it must contain `why:` — an uncited claim with no reason recorded is not
a debt, it is an omission.

## Where the gate lives

| file | role |
|---|---|
| `docs/kb/PROCEDURE.md` | the authority; this file only orients |
| `docs/kb/PINS.json` | budgets, `newest_commit`, `files[]`, `claims[]`, `uncited_baseline` |
| `tests/test_kb_integrity.py` | assertions A1..A10, one test each |
| `tests/COLLECTED.txt` | the pinned node-id manifest that `[FIXED-TESTED]` resolves against |
| `scripts/repin_kb.py` | writes `PINS.json` and patches headers; never hand-edited |
| `scripts/mutate_kb_gate.sh` | proves the gate is not vacuous: five mutations, five reds |

Two properties matter more than the rest. `[FIXED-TESTED]` resolves by
**membership** in `tests/COLLECTED.txt`, never by grepping for `def test_` in
the file it names — a test that does not appear in the manifest cannot be
cited, whatever the source says. And A10 is the staleness assertion: pins age,
and a pin whose commit is fifty commits behind HEAD describes history this tree
has left behind.

## This commit is a bootstrap

The four entries in `PINS.files[]` currently carry `sha256: null`. That is not
an oversight, it is the bootstrap: a file cannot contain the hash of itself plus
its neighbours before those bytes are committed. In this state A2, A4 and A10
are **red by construction** — they fail with a git message rather than skipping,
because "not checked" and "checked and fine" must never look alike. The fix is
one command between two commits:

```
git add -A && git commit -m "kb: content"
python3 scripts/repin_kb.py
git add -A && git commit -m "kb: pins"
python -m pytest tests/test_kb_integrity.py -q
```

A pin covers a **canonical form** of its file: the bytes with the *values* of
`pinned_commit`, `pinned_at` and `last_verified` replaced by `<canonical>`.
Every other byte is pinned as written, so editing a sentence, a heading or any
other header value still moves the hash; the three masked values are
authenticated instead by A10's ancestry check. That is what makes the second
commit both necessary and sufficient. `repin_kb.py` rewrites those three values
in every header, so until the pin commit lands `docs/kb` is dirty and A4 is red,
and a pin taken over raw bytes could never match the HEAD blob and the working
tree at the same time.

A1, A3, A5, A6, A7, A8 and A9 are green here and green anywhere: they need the
tree, not the history.

## What is never moved

`docs/design/*` stays the authority. This tree **indexes** it — the decision
register, the dispatch log, the defect register and the state schema are cited
by path from here and are not copied, renumbered or relocated into `docs/kb/`.
`docs/kb/REGISTRY/decisions.md` is an index whose rows point at that authority;
when the two disagree, `docs/design/` wins and this file is stale, and `status:
stale` is an honest header value rather than a failure.
