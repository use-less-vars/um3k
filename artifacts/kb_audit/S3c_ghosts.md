# S3c — Ghost audit: do any docs still assert a refuted claim as fact?

**Verdict: ZERO of 170 text files assert any of the three refuted claims as
present fact.** The ghost class is, right now, clean. That is a real finding and
not a failure to look — the search surface is small and fully enumerated below.

## The three ghosts, as STATE.json records them

Source of authority: `docs/design/onboarding/STATE.json`, `ghosts_rejected`
(:193-210), file mtime **2026-11-16T23:06**.

| # | Claim as originally made | Verdict | Refuting evidence in STATE.json |
|---|---|---|---|
| G-1 | "`_volume_quiver_mesh` does not exist / is a phantom symbol" | FALSE | `def _volume_quiver_mesh(...)` at `server/poc_app.py:9315`; called `:6116`, `:9431`; used by `tests/test_poc_volume_arrows.py`, `server/um3k_context.py:98` |
| G-2 | "`tests/test_animation_volume.py` has an xfail / finalizer teardown bug" | FALSE as stated | zero `xfail`, zero `finalizer` in the file; only three module-level `pytest.importorskip` guards at `:50`, `:51`, `:52-54`. A *different* teardown bug did exist and was repaired at `:264-273` in commit a588603 |
| G-3 | "Something in the tree uses `vi.Plane`" | FALSE | zero matches repo-wide for `vi\.Plane` |

## The whole search surface (every file mentioning the tokens)

| Ghost | Files containing the token | Files asserting it as fact | What those files actually say |
|---|---|---:|---|
| G-1 `quiver` | 5 (`00_README`, `03_KNOWN_BUGS`, `STATE.json`, `UM3K_UI_ARCHITECTURE` 18×, `GEN13_HANDOFF` 1×) | **0** | `00_README`:92 "`_volume_quiver_mesh` is real:", `:213` refutation; `03_KNOWN_BUGS`:300-314 G-1 entry; `UM3K_UI_ARCHITECTURE`:11,119-121,482 cite the symbol as existing (consistent with the refutation); `GEN13_HANDOFF`:40 mentions quiver plots as a *want* |
| G-2 `xfail`/`finalizer` on `test_animation_volume` | 6 (`00_README`, `01_ARCHITECTURE`, `02_PHYSICS_ROADMAP`, `03_KNOWN_BUGS`, `STATE.json`, `TRAME_HAZARDS`) | **0** | `01_ARCHITECTURE`:335 "There are no `xfail` markers and no `finalizer` teardowns in that file"; `03_KNOWN_BUGS`:316-350 G-2 entry; `TRAME_HAZARDS`:44,66 cite test *line numbers*, no xfail claim |
| G-3 `vi.Plane` | 3 (`00_README`, `03_KNOWN_BUGS`, `STATE.json`) | **0** | all three are the refutation itself (`00_README`:217 "Nothing does; zero matches repo-wide") |

Nothing anywhere else on disk touches these tokens: a second sweep for
alternate wordings (`phantom`, `does not exist`, `no such symbol`, `undefined
name`, `never used`, `doesn't exist`) across all `*.md`/`*.json` returned 30 hits
and **not one** is a ghost assertion — they are unrelated statements about
other things (e.g. `t4_amp_ratio`:375 "the sparse solver does not exist",
`e3_phase2_scope`:60 a "## 3. What does not exist" section listing genuine gaps).

**Dates.** No file in the tree postdates the refutation: the newest mtimes are
`00_README` 2026-11-16T23:08, `STATE.json` 23:06, `graded_meshing_plan` 22:03,
`TRAME_HAZARDS` 21:38. So there is no window in which an older doc could have
been written after the ghost was killed and still carry it. The answer to "does
the file date later than the refutation?" is: for the three ghost classes, **no
file asserts them at all, at any date**.

## Why this is a negative result with a positive cause

The three refutations were *pre-emptive*: they sit in `03_KNOWN_BUGS.md`
("Known bugs, and claims that turn out to be ghosts") as G-1/G-2/G-3, each with a
"damage if believed" note (`:349` "someone 'fixes' a teardown that does not
exist"). The pack was written *after* the ghosts had been circulating in session
briefings rather than in documents, so the ghosts never landed in a file. There
is therefore nothing to sweep and no stale assertion to mark.

## The real phantom class this audit did find

The ghost hunt for *symbol* phantoms came up empty, but the same question asked
of *documents* does not: **the KB's most-cited pointer aims at a file that does
not exist.**

| Target | References | Exists? |
|---|---:|---|
| `decisions.md` | **585 occurrences across 63 files** | **NO** — `find . -iname "*decision*"` returns only `d58_13_strip_width_decisions_block.md` |
| `PREREG.md` / `NOTE.md` | 86 | NO |
| `EM_SOLVER_LEDGER.md`, `defect_register.md`, `figures/README.md` | (high) | yes |

`decisions.md` is not a stray typo: S3b shows it named as the *successor* in
supersession banners (`normalization_scheme` "SUPERSEDED 2026-10-26 →
decisions.md 2026-10-27 supersession pass", `corr_ez_vv_threshold`,
`component_map`, `absorbing_termination_scope`, `d52b_claim_inventory`,
`zfree_shape`:3, `dispatch_log_archive_2026-Q4`). So 585 pointers tell a reader
"the surviving version of this is in decisions.md", and there is no such file.
That is the same failure mode as a ghost — a reader is sent to fix or consult
something that is not there — except a ghost claims a symbol is absent when it
exists, and this claims a document exists when it does not. **It is strictly
worse**, because a dangling successor makes the supersession banner useless
precisely where it matters, and it cannot be detected by reading the doc that
carries it.

**Consequence for the target structure:** `REGISTRY/decisions.md` is not a
nice-to-have ADR file to be started from scratch. It is the *reconstruction of a
file 585 existing pointers already assume*, and until it exists every
"superseded by decisions.md" banner in the KB is an instruction to nowhere.

<!-- generated by KB audit chunk 3; sources: STATE.json ghosts_rejected block + exhaustive token sweeps over all *.md/*.json in docs/ + find(1) for decision*; mtime used as date proxy; no git history available -->
