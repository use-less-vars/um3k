# Stage 1b — KB integrity gate: verification report

**Status: PARTIAL.** The two things Stage 1b exists to produce — a gate green on all ten
assertions and a five-red mutation transcript — **were not produced here, and could not be**.
This environment has no git binary that the gate can execute, and the gate's A2/A4/A10 are
git-dependent *by design*. Everything that does not need git **was** executed, and this
document records what it proved, what it did not, and the exact command sequence that has to
run on a git-capable host to close 1b.

Nothing under `docs/kb/` was written. No commits. Files written by this pass, and only these:
`artifacts/stage1b/PINS.before.json` and this report.

---

## 0. Bottom line

1. **The git-free half of the gate is green on the committed tree**: 7 of 10 assertions pass
   (A1, A3, A5, A6, A7, A8, A9). The 3 failures are exactly A2/A4/A10, and each fails with its
   own "git unavailable" message rather than skipping.
2. **The tree is pre-repin, and that is not only a git artefact**: all four `PINS.files[].sha256`
   are `null` and `newest_commit` is absent, so A2 and A10 would be red on a git-capable host
   too. `scripts/repin_kb.py` is mandatory before any 1b evidence exists.
3. **`kb_mutation_transcript.txt` at the repo root is invalid evidence** (it is the guard's
   `REFUSING: ... no git available` output). It must not be appended to
   `docs/kb/REGISTRY/decisions.md` and must not be committed. §5.1.
4. **`tests/COLLECTED.txt` cannot be regenerated in this container** (collection aborts on
   `tests/test_abc.py`), so A6's manifest freshness is unauditable here. §5.2.
5. Running `scripts/mutate_kb_gate.sh` here would be *worse* than not running it: on this host
   M2 and M5 would go "caught" for the wrong reason (git-unavailable red). The script's guard
   is what prevents that, and the guard correctly refused. That is the one thing the earlier
   failed run got right.

---

## 1. Environment: why the gate cannot run here

| Fact | Value | How established |
|---|---|---|
| git binary in the executor container | **absent** (`git: command not found`) | `command -v git python3 pytest` |
| host shell | **banned** (`host_bash:banned` by session grant) | tool call refused |
| python in container | 3.12.15 | `python3 -V` |
| pytest in container | 9.2.0 | `python3 -c "import pytest"` |
| repo HEAD | `c18d945ddea09130cb5ff0abba5fd929781b8933` — *kb: correct the bootstrap ritual, record KB-1* | `git_read rev_parse` (separate containerized git backend) |
| `docs/kb` working tree vs HEAD | clean (no `docs/kb` path in `git status --porcelain`) | `git_read status` |

Consequence: the gate's own design — `tests/test_kb_integrity.py`, module docstring — *"Git-free,
green anywhere: A1, A3, A5, A6, A7, A8, A9. Git-dependent, explicitly red without a repository:
A2, A4, A10"* — is exactly what was observed. The gate behaved as specified; the environment
cannot satisfy the remainder.

---

## 2. What was executed (verbatim results)

### 2.1 The gate

```
python3 -m pytest tests/test_kb_integrity.py -q
FAILED tests/test_kb_integrity.py::test_a2_self_pins   - Failed: A2 FAIL: git unavailable ...
FAILED tests/test_kb_integrity.py::test_a4_tree_clean  - Failed: A4 FAIL: git unavailable ...
FAILED tests/test_kb_integrity.py::test_a10_staleness  - Failed: A10 FAIL: git unavailable ...
3 failed, 7 passed
```

A10's message is precise about state, not just about git — the first thing it hits is
`A10 FAIL: git unavailable: cannot resolve commit ancestry ... the git binary could not be
executed (FileNotFoundError)`.

### 2.2 A4's git-free half is independently confirmed

A4's directory checks run *before* its git probe, and it reached the probe with an empty problem
list — so on the committed tree the five layer directories exist, each carries a tracked
`.gitkeep`, and none carries a `README.md` stub. Verified directly as well: `ARCHIVE/`, `CORE/`,
`REGISTRY/`, `REFERENCE/`, `WORK/` each hold `.gitkeep`; only `CORE/` and `REGISTRY/` hold content.

### 2.3 A1/A3 are non-vacuous today

A1 is doing real work on real headers (four markdown files, nine required keys each,
`layer:` must match the directory, `core_handoff_id` only on `layer: core` and equal to
`PINS.core_handoff_id` = `gen13->gen14`). A3 reports real byte totals against real caps.
A5 is green with zero tags found, so it too is currently content-free (§5.3).

### 2.4 Pin state before repin (see `PINS.before.json`)

```
docs/kb/PINS.json  643 B  sha256 de397952a479c4a4c182a99a7e85c38aacdbf1ed394ee2ceadab996e4fa79780
files[0..3].sha256 = null x4   newest_commit = absent   newest_commit_date = null   claims = []
```

`tests/test_kb_integrity.py` lists `newest_commit` in `PINS_OPTIONAL_KEYS` (A1 tolerates its
absence, A10 is what demands it), which matches the observed A1 green / A10 state.

### 2.5 Predicted `PINS.json` after `scripts/repin_kb.py` (computed, not written)

`repin_kb.pinned_paths()` = `sorted(docs/kb/**/*.md)` + `tests/COLLECTED.txt`, so the set grows
from 4 to **5** entries — `docs/kb/CORE/00_invariants.md` is missing from the current list and
will be picked up. Canonical digests below were computed with `scripts/kb_canonical.py` over the
working-tree bytes, which equal the HEAD blobs because `docs/kb` is clean:

| order | path | layer | canonical sha256 |
|---|---|---|---|
| 1 | `docs/kb/CORE/00_invariants.md` | core | `3d1c80e1684a712f7fdb244c1e1db5f71c1aa05cdb3e579e170be8c1a668b50a` |
| 2 | `docs/kb/PROCEDURE.md` | root | `221e8aaa61a1c58db5af61620b5bd8c38e8568ecd7cb2f658dd38d868e480802` |
| 3 | `docs/kb/README.md` | root | `e358f5c3a057f095d44a4c213be48c2415c3851162935266c03a73f2708514dd` |
| 4 | `docs/kb/REGISTRY/decisions.md` | registry | `b4493f5d888c61e9279b3a4e67d812baa8ddb6e1c488fe28800de4826d155fd7` |
| 5 | `tests/COLLECTED.txt` | test-manifest | `19000c4429abe9f9bacd38be5d2118a87c2c09f6a3b8ae24b86cdde990dc78ea` |

`newest_commit` should come out as `c18d945ddea09130cb5ff0abba5fd929781b8933`. Header patching
will set `pinned_commit: <HEAD>` on all four files and `pinned_at`/`last_verified` to today;
`README.md`, `PROCEDURE.md` and `CORE/00_invariants.md` currently carry `pinned_at: null`.
Those three keys are precisely what `kb_canonical` masks, so **the patch cannot invalidate the
digests above** — that is the whole point of the canonical form, and it checks out by reading
`scripts/kb_canonical.py` (line-level substitution inside the leading fence, nothing else touched).

---

## 3. Static review of the 1b machinery (what will run on the host)

- `scripts/mutate_kb_gate.sh` — guard (`green` on the whole file) then five cycles, each:
  mutate → expect the one node red → restore from `$BACKUP_DIR` → expect the same node green.
  Backups are `cp -p` of `README.md`, `REGISTRY/decisions.md`, `PINS.json`; `trap restore_all EXIT`
  covers an abort. It never commits.
- All five targeted node ids exist and collect (the file collects 10 tests):
  `test_a1_header_completeness`, `test_a2_self_pins`, `test_a6_fixed_tested_resolves`,
  `test_a9_uncited_baseline`, `test_a10_staleness`.
- Mutation → assertion mapping checks out against the assertion bodies:
  M1 (drop `reads_when:` from the registry index) → A1 required-key; M2 (append a comment to
  `README.md`) → A2 working-tree canonical mismatch; M3 (`[FIXED-TESTED tests/test_deleted.py::nonexistent_test]`)
  → A6 manifest membership; M4 (`[UNCITED]` + `why:` line) → A9 count over baseline 0 (A5 passes,
  the `why:` line is on the next non-empty line, so the red is A9's and not A5's);
  M5 (claim with `pin_commit` = 40 zeros) → A10 ancestry.
- One real ordering trap, from `repin_kb.write_pins()`: it **refuses a dirty `docs/kb`** (exit 2)
  unless `--force`. Appending the transcript row to `REGISTRY/decisions.md` is content, so the
  append has to be *committed* before the repin that pins it. Otherwise the sequence in the
  approved Stage 1 plan ("append → repin → commit") stops at exit 2. §6 has the amended order.

---

## 4. What this pass did **not** do

- Did not run `scripts/repin_kb.py` (needs git; and it writes `docs/kb`, outside this pass's
  footprint).
- Did not run `scripts/mutate_kb_gate.sh` (its guard refuses on a red tree — correctly — and a
  mutation "caught" by a git-unavailable red would be false evidence).
- Did not commit, stage, or modify any tracked file; did not touch `docs/kb/**`.

---

## 5. Defects found (all three block a truthful 1b record)

### 5.1 `kb_mutation_transcript.txt` (repo root, untracked) is not evidence

```
repo:   /workspace
commit: no git available
FAILED tests/test_kb_integrity.py::test_a4_tree_clean - AssertionError: git i...
FAILED tests/test_kb_integrity.py::test_a10_staleness - AssertionError: git i...
REFUSING: the unmutated gate is not green.
```

This is the mutation script's *guard* output from a run in a git-less container. Zero mutations
were applied. It must be deleted (or moved under `artifacts/`), never appended to
`REGISTRY/decisions.md` and never committed — a transcript whose sha256 goes into the registry is
a permanence claim about five reds that never happened.

### 5.2 `tests/COLLECTED.txt` is a frozen snapshot that cannot be refreshed here

- 1,305 lines, **1,287 node ids**. Its own header says it was generated *"in this workspace's
  executor container (python 3.12.15, pytest 9.2.0, no network, no git binary)"*.
- Regenerating it **fails** in the same container today:

  ```
  python3 -m pytest tests --collect-only -q
  ERROR tests/test_abc.py - RuntimeError: emfit_core exists on disk but could n...
  !!!!! Interrupted: 1 error during collection !!!!!
  ```

  `--continue-on-collection-errors` does not help (pytest 9 interrupts the session; 0 ids
  reported). The raise is at `emfit/evolve.py:260` — *"emfit_core exists on disk but could not be
  imported"*. A `.so` does exist (`build/cpp/emfit_core.cpython-312-x86_64-linux-gnu.so`,
  `build/phase2/o2|o3|o2lto/...`, `artifacts/cpp_build_e3/...`) but the in-tree one is parked as
  `build/emfit_core.cpython-312-x86_64-linux-gnu.so.pre_abi`, i.e. an ABI-incompatible build.
- Why it matters for 1b: A6 resolves `[FIXED-TESTED <path>::<name>]` **only** by membership in
  this frozen file (A6 explicitly refuses to grep for `def`). If the manifest and the live test
  tree drift, A6 keeps approving node ids that no longer exist. Nothing in the gate compares the
  two, and this pass could not compare them either. Recommend an explicit note in
  `REGISTRY/decisions.md` recording how and when `COLLECTED.txt` was generated, and regenerating
  it on a host where `emfit_core` imports before the first citation is added.

### 5.3 The gate is currently green partly because there is nothing to check

A7 (`[measured]` / `[CITED]` against HEAD blobs) and A8 (`PINS.claims` against `pin_commit`
blobs) are green with **0 entries each** — they print `0 claims evaluated, 0 pinned` and return.
That is honest by construction (they say so), but it means Stage 1b proves nothing at all about
evidence resolution: there is no measured tag and no claim in the tree yet. Likewise the five
mutations cover A1, A2, A6, A9, A10 only — A3, A4, A5, A7, A8 have no mutation, so
"the gate is not vacuous" is proven for exactly half of it. Worth stating in the registry row
rather than implying ten-of-ten coverage.

---

## 6. Exact sequence to close 1b (git-capable host, from `git status` clean)

```bash
cd <repo>

# 0. invalid evidence out of the way (never commit it)
rm -f kb_mutation_transcript.txt

# 1. generate the pins at the content commit c18d945
python3 scripts/repin_kb.py                 # writes PINS.json + patches 4 headers
python3 scripts/repin_kb.py --check         # expect: no drift (5 pins)

# 2. commit the pins; A2/A4 can only be green on a committed tree
git add docs/kb/PINS.json docs/kb/README.md docs/kb/PROCEDURE.md \
        docs/kb/CORE/00_invariants.md docs/kb/REGISTRY/decisions.md
git commit -m "kb: generate pins at c18d945"

# 3. gate must be 10/10 here — this is the 1b acceptance point
python3 -m pytest tests/test_kb_integrity.py -q

# 4. mutations: five reds, five restores green, deterministic transcript
bash scripts/mutate_kb_gate.sh | tee artifacts/stage1b/transcript.txt
sha256sum artifacts/stage1b/transcript.txt   # this digest goes in the registry row

# 5. append the transcript row to docs/kb/REGISTRY/decisions.md, COMMIT IT FIRST
#    (repin_kb.py refuses a dirty docs/kb: exit 2), then re-pin, then commit
git add docs/kb/REGISTRY/decisions.md && git commit -m "kb: record the 1b mutation transcript"
python3 scripts/repin_kb.py
git add docs/kb docs/kb/PINS.json && git commit -m "kb: re-pin after the transcript row"

# 6. final state
python3 -m pytest tests/test_kb_integrity.py -q   # expect 10 passed
git status --porcelain -- docs/kb                 # expect empty
```

Notes that make step 3/6 honest rather than lucky:
A10 ratchets on `newest_commit`'s **ancestry and distance**, so after step 2 the pin sits one
commit behind HEAD — the test's own docstring says *"a distance of 1 is a normal, green state"*,
and `newest_commit_date` is informational only (asserting a `%cI` string would be unsatisfiable
together with A4, since re-pinning precedes the commit that cleans the tree).
After step 5 the pin is again one commit behind; the 14-day window is measured on the pinned
commit's committer date.

---

## 7. Open questions for the owner

1. Should `COLLECTED.txt` be regenerated (and re-pinned) *before* the first `[FIXED-TESTED]`
   citation is written, given it cannot be regenerated in the executor container (§5.2)?
2. Is a five-of-ten mutation set the intended end state, or is a follow-up mutation for
   A3/A4/A5/A7/A8 in scope for Stage 2? (§5.3)
3. Disposition of `artifacts/stage1b/transcript.txt` — committed under `artifacts/`, or left
   untracked and only its sha256 recorded in the registry row?
