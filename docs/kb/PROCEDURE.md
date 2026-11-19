---
status: current
layer: root
pinned_commit: c6195cfb33e94a289ccabd8d5675bd7ff41d03c9
pinned_at: 2026-11-19
byte_budget: 20480
last_verified: 2026-11-19
reads_when: when you are about to add, move, cite or re-pin any file under docs/kb
supersedes: null
superseded_by: null
---

# docs/kb/PROCEDURE.md — how to add a file without lying

`docs/kb/README.md` tells you what this tree is. This file is the authority for
how to change it: budgets, header syntax, the tag grammar, the two rituals, the
escape hatches, and the one command that decides whether any of it is true.

The gate is `python -m pytest tests/test_kb_integrity.py -q`. Ten assertions,
A1..A10, one test each. Nothing in this file is a preference; each rule below is
implemented by a line of that test module.

## 1. The layers

Five content layers, each with a fixed directory name, plus the root entry
files. The directory *is* the layer: `layer` in the header must equal the
lowercased directory name, and root files declare `layer: root`.

| layer | directory | belongs here | must never appear here |
|---|---|---|---|
| `core` | `docs/kb/CORE/` | the few files every session reads before touching code | an in-flight note |
| `registry` | `docs/kb/REGISTRY/` | indexes whose rows point at authority elsewhere | a second copy of that authority |
| `work` | `docs/kb/WORK/` | dated, in-flight work notes | anything another session depends on |
| `archive` | `docs/kb/ARCHIVE/` | superseded text kept so citations keep resolving | the only copy of anything |
| `reference` | `docs/kb/REFERENCE/` | external material, copied not linked | a rewritten source |

Root files, all directly in `docs/kb/`: `README.md` and `PROCEDURE.md`, each
with the nine-key header below, and `PINS.json`, which carries **no** header
because it is not markdown. There is no `docs/kb/ROOT/` directory: the layer is the
absence of a directory, not one named "root".

Every layer directory stays in git even when empty: an empty layer keeps a
`.gitkeep`, and a layer must never carry a `README.md` stub, because entry text
lives in the single root `README.md`. A4 checks both facts before it looks at
git at all.

## 2. Budgets

Caps are set once, in `PINS.json.budgets`, and quoted here in both units because
a human reads KiB and the gate counts bytes.

| cap | KiB | bytes | behaviour |
|---|---|---|---|
| `core` | 45 KiB | 46,080 B | hard fail past it |
| `core_warn` | 38 KiB | 38,912 B | prints `WARN:` |
| `per_file_core_default` | 9 KiB | 9,216 B | per-file cap for a core file with no `byte_budget` |
| `registry` | 30 KiB | 30,720 B | hard fail |
| `work` | 20 KiB | 20,480 B | hard fail |
| `test_manifest` | 150 KiB | 153,600 B | hard fail; `tests/COLLECTED.txt` only |
| `test_manifest_warn` | 120 KiB | 122,880 B | prints `WARN:` |
| `total_ingest` | — | 100,000 B | hard fail; `warn_at` = 0.85 |
| `archive`, `reference` | — | — | deliberately unbudgeted |

`warn_at` is a fraction, so `PINS.budgets` holds exactly one float; every other
value there is an integer. A3 reads a file's **own** `byte_budget` header as its
per-file cap — the header is the source of truth — and falls back to
`per_file_core_default` only for a core file that omits one. `archive` and
`reference` are unbudgeted on purpose: they are read rarely and may be large,
and a cap nobody enforces is worse than no cap, so no `ROOT`, `ARCHIVE` or
`REFERENCE` block may exist in `budgets` at all. `test_manifest` caps the one
pinned file outside `docs/kb/`, never part of ingest: A6 reads it, not a session.

Total ingest is "what a session actually ingests": `docs/kb/README.md`,
`docs/kb/PROCEDURE.md`, `docs/kb/PINS.json`, everything under `CORE/`, and
everything under `REGISTRY/`. `ARCHIVE/`, `REFERENCE/` and `WORK/` are excluded
from that sum even though `WORK/` has its own layer cap: work notes are read by
the session that wrote them, not by every session.

## 3. The header

Copy this block, change the values, keep the key set exactly these nine and in
this order. Nothing else is recognised.

```
---
status: current
layer: core
pinned_commit: null
pinned_at: 2026-11-17
byte_budget: 9216
last_verified: 2026-11-17
reads_when: before you touch src/emfit_core/state.py
supersedes: null
superseded_by: null
---
```

`pinned_commit: null` in this example is the pre-repin state. A null pin is legal
**only in the bootstrap state**: nothing is pinned yet (`PINS.newest_commit_date` is
`null`) *and* the header's own `status` is `current`. After `repin_kb.py` sets
`PINS.newest_commit`, a null pin is a failed header (section 6); a header that is
`superseded` or `stale` may never carry `null` — an erased pin on a retired header is a
fabrication. The null-tolerance is a bootstrap state, not a fallback.

The parser is a dumb line parser, and that is a feature: it cannot silently
accept something you did not mean. The rules it enforces:

- **LF only.** A single carriage return anywhere in the file fails the header.
- **One `key: value` per line**, split on the *first* colon; blank lines inside
  the block are ignored.
- **Bare scalars only.** No quotes (a value starting with a quote fails), no
  inline `#` comment (any `#` in a value fails), no `{...}` or `[...]` (a value
  starting with either fails): this is not YAML and there is no nesting.
- **`null` means absent**, lowercased, exactly four characters.
- **No duplicate keys**, and **no unknown keys** — one extra key is a failed
  header, not a harmless annotation.
- **`status`** is one of `current`, `stale`, `superseded`, `draft`.
- **`layer`** equals the lowercased directory name, or `root` for the two root
  files.
- **`pinned_commit`** is 40 lowercase hex — the commit whose bytes this file
  describes — or the literal `null` on **any** layer, which is legal only until
  the first `repin_kb.py` run (section 6).
- **`byte_budget`** is a positive integer, in bytes.
- **`pinned_at`, `last_verified`** are `null` or ISO dates (`2026-11-17`).
- **`reads_when`** is non-empty prose: say when a session must open the file.
- **`supersedes`, `superseded_by`** are a path or `null`.

The one optional key is `core_handoff_id`, allowed on `layer: core` only, where
it is mandatory and must equal `PINS.core_handoff_id`. On any other layer it is
an unknown key and fails.

## 4. Tags

A claim about the code that is worth checking is a **bracketed** token:
`[NAME body]`. The bracket is part of the syntax on purpose. English sentences
use the words measured, closed and cited as ordinary verbs; if those words were
the trigger, half of this tree would be a claim. The bracket makes a claim
opt-in, visible in review, and cheap for a scanner to find.

| tag | body | checked by | resolves against |
|---|---|---|---|
| `[VERIFIED-BY-RUN <commit> <command>]` | 7-40 hex, then the command | A5 only | a re-run on a git-capable host |
| `[FIXED-TESTED <path>::<test>]` | a node id | A6 | membership in `tests/COLLECTED.txt` |
| `[measured <path> <sha256 prefix>]` | tracked path, 12-64 hex | A7 | sha256 of that path's HEAD blob |
| `[CITED <path>:<line>]` | tracked path, line number | A7 | that line exists in the HEAD blob |
| `[closed <gate>]` | a gate name | A5 only | a human re-reading the gate |
| `[UNCITED]` | nothing at all | A9 | the `uncited_baseline` counter |

Examples, shown inside a fence so that they make no claim:

```
[VERIFIED-BY-RUN 3f7c1a2 python -m pytest tests/test_kb_integrity.py -q]
[FIXED-TESTED tests/test_kb_integrity.py::test_a6_fixed_tested_resolves]
[measured src/emfit_core/state.py 9f2c1a7b3d5e]
[closed gate-A10-staleness]
[CITED src/emfit_core/state.py:2062]
```

`[UNCITED]` is the only tag that must be accompanied. The line that follows it
(its next non-empty line) must contain `why:` with the reason the claim is not
yet backed by anything. A claim whose only support is a `@state.change` listener test is `[UNCITED]` until DR-47 closes.

Tags are scanned span-aware: a tag inside an inline `` `code span` `` or inside a
fenced block (three backticks, or three tildes) is invisible to the scanner.
That is the whole reason
this file can document the grammar without accidentally asserting anything —
every example above is inside a fence, and the ones in prose are backticked.
A5 runs a self-test on that masking before it looks at the tree, and reports an
opening `[NAME` with no closing `]` as a broken tag rather than ignoring it.

## 5. The ten assertions

| id | one line | why it exists |
|---|---|---|
| A1 | every markdown file has the nine-key header, a matching layer, a valid status, and `PINS.json` has exactly its eight keys (`newest_commit` arrives with the first re-pin; the gate accepts seven until then) | a file with no header is a file with no provenance |
| A2 | `PINS.files[].sha256` equals the sha256 of that path's **canonical form**, computed once from the HEAD blob and once from the working tree | a pin names committed content, not a promise |
| A3 | per-file caps from headers, core/registry/work layer sums, total ingest and the `tests/COLLECTED.txt` manifest against `PINS.budgets` | a knowledge base that only grows stops being read |
| A4 | the five layer dirs exist with `.gitkeep` and no `README.md` stub, `git status --porcelain docs/kb` is empty, everything walked is tracked | a pin is only meaningful over a clean tree |
| A5 | every tag body matches its documented shape, `[UNCITED]` carries `why:`, masking self-test passes | a malformed tag is an unverifiable claim |
| A6 | every `[FIXED-TESTED]` node id is a **member of `tests/COLLECTED.txt`** | membership, never a grep for `def test_`: a deleted or uncollected test cannot be cited |
| A7 | every `[measured]` matches the HEAD blob sha256 and every `[CITED]` line exists in it | evidence must be read from the commit, not from memory |
| A8 | every `PINS.claims[]` entry names an ancestor commit and a `required_token` present in the source blob at that commit | a registered claim is a query, not a note |
| A9 | the number of live `[UNCITED]` tags never exceeds `PINS.uncited_baseline` | debt is allowed; growing debt silently is not |
| A10 | every source pin is still an ancestor of HEAD, no non-root header keeps `pinned_commit: null` once `PINS.newest_commit` is set, that commit is inside 14 days on its own committer date, pin..HEAD distance warns at 20 and fails at 50 | pins age; a stale pin is a lie with a date on it |

A2, A4, A7, A8 and A10 touch git; of those, A2, A4 and A10 are the three that
cannot be evaluated at all without a repository, and where there is no `git`
binary they fail with their own `git unavailable` message rather than skipping.
A7 and A8 pass trivially when there is nothing to evaluate — zero
`[measured]`/`[CITED]` tags and an empty `claims[]` — and say so: they print
`0 claims evaluated, 0 pinned`, not a green light that means nothing.

## 6. Bootstrap, self-pins and source pins

The ordering is not optional:

1. commit the content;
2. run `python3 scripts/repin_kb.py` — it writes the self-pins and patches the
   header pins;
3. commit the pins and the header patch it produced;
4. run the gate.

Two commits, not one. Step 2 rewrites three front-matter values in every header
and rewrites every self-pin, so between steps 2 and 3 `docs/kb` is dirty and A4
is red. After step 3 both sides of A2 and A4 hold at the same time. Step 2 also
refuses to run at all over a dirty `docs/kb`.

`PINS.json` can never pin itself. Its bytes change every time it is written, so
a sha256 of itself inside itself could not be true for even one commit — the
gate rejects a `files[]` entry that names `docs/kb/PINS.json`.

A **self-pin** is the sha256 of a file's **canonical form**, recorded in
`PINS.files[].sha256`; its `layer` reuses the same six layer names a header uses
(the two root files are `root`), plus one extra kind, `test-manifest`, for
`tests/COLLECTED.txt`, which lives outside `docs/kb/`. The canonical form is the
file's bytes with the *values* of exactly three front-matter keys —
`pinned_commit`, `pinned_at`, `last_verified` — replaced by `<canonical>`; every
other byte, body and header alike, is hashed as written. One side is read with
`git show HEAD:<path>` and the other from the working tree, which makes the pin
bootstrap-free (the content commit exists before the pin does) and CRLF-immune.
A2 requires both sides to equal the pin, so an edit without a re-pin is red
immediately rather than at the next commit, and a body byte, a heading or any
other header value still breaks the pin. The writer and the gate both import
that rewrite from `scripts/kb_canonical.py`, so they cannot drift apart.

The three masked values are provenance, not content, and A10 authenticates them
instead by reading `PINS.newest_commit` and checking that commit for ancestry
and freshness. Masking them is what gives the ritual a fixed point: re-pinning
rewrites all three on every header, so a pin taken over raw bytes could match
the working tree (A4 red) or the HEAD blob (A2 red), never both.

A **source pin** is `claims[].pin_commit`: an immutable commit hash naming where
a claim's evidence lives. It never moves. A10 walks every `claims[].pin_commit`
and every non-root header's `pinned_commit` and asks whether it is still an
ancestor of HEAD; rewritten history, a rebase that dropped the commit, or a
pinned commit from another branch all fail there.

`python3 scripts/repin_kb.py --patch-headers` is the only supported way to move
a header's `pinned_commit`, `pinned_at` and `last_verified`: it rewrites those
three values to HEAD and today on every header, root files included, and touches
nothing else (a plain `python3 scripts/repin_kb.py` run patches the headers too,
so one command re-pins the tree, after which only the pin commit makes the tree
clean again). Before the first run every header may carry
`pinned_commit: null` and `PINS.newest_commit` is `null`; that is the only state
in which a null pin is legal.

`PINS.json` carries the eight keys `schema`, `core_handoff_id`, `newest_commit`,
`newest_commit_date`, `uncited_baseline`, `budgets`, `files`, `claims`.
`newest_commit` is the ratchet: the full 40-character HEAD sha at re-pin time.
`newest_commit_date` records that commit's committer date for a human, and
nothing asserts it.

**The ratchet.** The moment `PINS.newest_commit` names a commit, a null
`pinned_commit` on any non-root header is a failed header and A10 fails hard
naming the path; every remaining pin must be an ancestor of HEAD and inside the
14-day window measured on that commit's own committer date. A pin..HEAD distance
of 1 is the normal green state — the pin names the content commit that the pin
commit sits on — with a warning at 20 and a failure at 50. There is no
placeholder commit hash: a pin is either the real commit its bytes were pinned
at, or `null` before the first re-pin. The forty-zeros value is not a
placeholder either: it is a commit hash that cannot exist, and M5 in
`scripts/mutate_kb_gate.sh` uses exactly that to prove A10 notices.

## 7. The entry ritual

Five commands, in this order, before you write a single line of a KB file:

```
python -m pytest tests/test_kb_integrity.py -q
git log --oneline -5
git status --porcelain docs/kb
python3 scripts/repin_kb.py --check
head -20 docs/kb/PINS.json
```

If the gate is red before you start, say so and stop: you cannot tell your
change from the one that was already broken.

## 8. The exit ritual

Six items, all of them, before you claim the work is done:

1. the gate is green (or A2/A4/A10 are red *only* with the three git-unavailable
   messages, and you have said so in the same breath);
2. `python3 scripts/repin_kb.py --check` reports no drift;
3. every file you touched is inside its own `byte_budget`;
4. every new claim carries a tag, and every tag resolves;
5. `bash -n scripts/mutate_kb_gate.sh` still parses if you touched it;
6. you have written down what you did **not** verify.

## 9. Regeneration cadence

| file | regenerate when | command |
|---|---|---|
| `docs/kb/PINS.json` | after any content commit | `python3 scripts/repin_kb.py` |
| headers' `pinned_commit` | at the same moment | `python3 scripts/repin_kb.py --patch-headers` |
| `tests/COLLECTED.txt` | any test is added, renamed, deleted or becomes uncollectable | `python -m pytest --collect-only -q` |
| `docs/kb/REGISTRY/decisions.md` | the decision register gains or supersedes a row | hand-edited index, per that file's own rules |
| `docs/kb/CORE/*` | the code it describes changes shape, not just lines | hand-edited, then re-pinned |

`tests/COLLECTED.txt` is a manifest of node ids, refreshed by one command. Its
`#` header records when it was generated and what could not be collected; the
node ids below that header are the only thing `[FIXED-TESTED]` resolves against.

## 10. Sequencing

Five stages, and they are ordered because each one's evidence is the previous
one's output:

1. **content** — write the files, nine-key headers, tags that resolve;
2. **commit** — the content lands, so HEAD exists to be pinned;
3. **pin** — `repin_kb.py` writes the self-pins and patches the header pins;
   `docs/kb` is now dirty, and it has to be, because the pins describe the bytes
   committed in stage 2;
4. **commit the pin** — the pins and the header patch land, so the tree is clean
   and a pin is a committed artefact rather than a pending edit;
5. **gate** — the ten assertions run against that clean tree, and only there.

One commit cannot carry stages 2 and 4 together. The pin has to be computed from
a commit that already exists, and the bytes it describes have to be committed
before the tree is clean. That is why the ritual has two of them.

Nothing moves until the gate is green. Not a directory, not a file, not a
citation, not an "obvious" renumbering. The whole point of an ordered ritual is
that the failure is cheap and the claim is expensive.

## 11. Escape hatches

Three, and each of them is a written admission rather than a bypass:

- **Raise `PINS.uncited_baseline`.** When a claim genuinely cannot be backed
  yet, `[UNCITED]` plus a `why:` line plus one increment in a reviewed
  `PINS.json` change. The number is the debt; A9 only forbids it growing
  silently.
- **`supersedes` / `superseded_by`.** A replaced file keeps its bytes, sets
  `status: superseded` and names its successor. Deleting it instead breaks every
  citation that pointed at it.
- **`status: stale`.** When the code moved and the prose has not caught up, say
  so in the header. A stale file that admits it is worth more than a current
  file that lies, and A10 is what eventually forces the question.

What is *not* an escape hatch: editing `PINS.json` by hand to match a hash you
computed yourself, adding a node id to `tests/COLLECTED.txt` to make a citation
resolve, or widening a `byte_budget` in the same commit that overran it. Each of
those makes the gate green and the claim false.

## 12. The citation corollary

Line numbers are valid only against a pinned commit, never against a dirty
working tree. This is not theoretical: `src/emfit_core/state.py` carried
`STATE_SCHEMA` at line 2062 in the committed blob while a sibling edit had it at
2076 in the live tree — same file, same symbol, fourteen lines apart, and a
`[CITED src/emfit_core/state.py:2076]` written against the tree would have been
wrong the moment it was committed. A7 reads the HEAD blob for exactly this
reason, and A4 refuses a dirty `docs/kb` so that "the bytes I read" and "the
bytes that are pinned" stay the same bytes.

The corollary for prose: if a claim needs a line number, pin the commit first,
then cite. If you cannot name the commit, the claim is `[UNCITED]`.

## 13. Running the gate on a git-capable host

The five commands, in order, are in `docs/kb/RUNBOOK.md`; this section says
what each of them is for.

Seven of the ten assertions — A1, A3, A5, A6, A7, A8, A9 — need only the tree
and pass anywhere. The other three are the git-dependent trio: A2
(canonical-form sha256 against HEAD blobs), A4 (`git status --porcelain docs/kb`
strictly empty) and A10 (commit ancestry, the 14-day window on
`PINS.newest_commit`, pin..HEAD distance).
Without a repository they **fail**, each with its own "git unavailable" message
naming what it could not check, and never skip: an unrun assertion that reports
as green is how a knowledge base rots.
