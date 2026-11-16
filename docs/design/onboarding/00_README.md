# 00 — Start here

You are inheriting a working electromagnetic field solver with a browser front
end, a defect register that is taken seriously, and a set of documents that
mostly tell the truth and occasionally do not. This pack is the shortest path to
being useful in it without re-deriving what has already been paid for.

Four files, in this order:

| File | Read it when | What it gives you |
|---|---|---|
| `00_README.md` | now | The rules, the scale of the tree, how to run it. |
| `01_ARCHITECTURE.md` | before your first code change | Layers, the page data shapes, why the UI is shaped as it is. |
| `02_PHYSICS_ROADMAP.md` | before you touch the solver or the mesh | Where the physics actually is in code, and what is genuinely next. |
| `03_KNOWN_BUGS.md` | **before you trust any test** | DR-47 first. It changes what a green suite means. |
| `STATE.json` | when you want the facts as data | Commit, constants, schemas, defect table, what is verified. |

Total reading time is about an hour. The single most valuable item in the pack is
§2 of `03_KNOWN_BUGS.md` (DR-47), and it is the reason the pack exists.

---

## 1. How to read a citation in this pack

Every factual claim carries a `path:line` citation. That is the house style and
it is not decoration: a citation you can check is the difference between a
document and a rumour.

Three provenance tags are used, and nothing else:

- **no tag** — this pack read that line itself. Trust it as far as the line goes,
  and no further.
- **`[BRIEFING]`** — handed to this pack and not re-read. May be right; is not
  checked here. `STATE.json` lists every one of these under
  `verification.taken_from_briefing_not_re_read`.
- **`[INFERRED]`** — a conclusion drawn from cited lines. The lines are solid,
  the step between them is an argument, and you are allowed to disagree with it.

What this pack deliberately does **not** contain: any test count presented as a
number of *passing* tests, any measurement, and any generation date. It ran no
tests, ran no study, and ran no git write command — the only git it ran was the
read-only `rev-parse` / `log` / `status` needed to state the commit this pack is
based on. Where a count appears it is a count of definitions or of bytes, and it
says so.

If you find a claim here that is wrong, fix the claim in place. This pack is a
working document, not a monument.

---

## 2. The four rules

These are not style preferences. Each one exists because it was already violated
and the violation cost something recorded in `docs/design/defect_register.md`.

### Rule 1 — read before you write, and check `git status` for the path

Before writing to any path that already exists, ask whether that path is
**tracked**. If it is untracked, put a copy aside first.

This is DR-44 (`docs/design/defect_register.md:871`): 49,352 bytes of untracked
`docs/design/GEN12_HANDOFF.md` were replaced in place and are unrecoverable —
never in the object store, no copy, gone. The file you see there now (27,138 B)
is the replacement from commit `bd2d9b9`, not the draft.

An untracked file is a delete waiting for someone to be helpful. Scratch notes in
`docs/design/` are exactly the kind of file this destroys.

### Rule 2 — a claim without a `path:line` is not a claim

"The visualiser draws the coarser volume recording on the plane clock" is an
opinion. "`_volume_player_plan` at `server/poc_app.py:8851`, tests at
`tests/test_animation_volume.py:1287`" is a claim, and it can be checked in
thirty seconds by someone who does not believe you.

This matters more here than in most projects because a large fraction of this
tree is *prose about the code*. Handoffs, registers, session notes and plans all
describe behaviour, and they drift. When prose and `path:line` disagree, the line
wins.

### Rule 3 — silent failure is the default failure mode

Nothing in this application throws when it is wrong. It draws something
plausible.

The worked example is the `_start_watch` chain in DR-47: an edit deleted one
call, and `_start_watch` → `_watch_solve` → `_poll_solve` → `apply_page` became
unreachable. No exception. No failing test. A page that never refreshed. The only
thing that caught it was a test asserting a string occurred in a closure — which
tells you how thin the coverage was on that path.

The same rule applies to *finding* code. `_volume_quiver_mesh` is real:
defined at `server/poc_app.py:9315`, called at `server/poc_app.py:6116` and
`server/poc_app.py:9431`, exercised by `tests/test_poc_volume_arrows.py`, and
referenced at `server/um3k_context.py:98`. A prior handoff nonetheless carried
the claim that it does not exist. Before you believe any statement of the form
"there is no such function", grep for the definition *and* the call sites, in
the whole tree, and check the module you were not looking at.

Corollary for tests: a test that passes tells you the code did not raise. In this
repo, that is sometimes all it tells you.

### Rule 4 — keep four claims apart

The register is disciplined about this and you should be too:

1. **VERIFIED-BY-RUN** — someone ran it and looked at the output.
2. **FIXED-TESTED** — a test in the tree fails if the behaviour returns.
3. **closed** — a gate was named and met.
4. **measured** — a number with a record, a window and a tolerance.

A fixed bug is not a repaired artefact. DR-43 is fixed and pinned by a test, and
the pre-fix files in the tree still lack the key the fix introduced — which is
correct, because you cannot retroactively repair data that was already written.
When you write your own status line, say which of the four you mean.

---

## 3. The tree at a glance

Nothing here is a claim about quality; it is a claim about size, which is the
first thing a new engineer needs.

| Where | Size | What it is |
|---|---|---|
| `emfit/` | 43 modules, 1,423,908 B | The solver library. Pure Python plus an optional C++ extension. |
| `emfit/studies.py` | 335,308 B | The largest module by an order of magnitude; the study layer. |
| `emfit/spice.py` | 66,405 B | Circuit co-simulation. Wired in, not prominent. |
| `server/` | 3 files, 644,501 B | The application. No package — bare modules, no `__init__.py`. |
| `server/poc_app.py` | 611,825 B | The app: trame UI, CLI, page model, dump readers, all in one file. |
| `server/um3k_context.py` | 10,372 B | `PageContext` — the page data shape, constructible with no dump. |
| `server/um3k_panels.py` | 22,304 B | `build_left_panel`, `build_center_panel`, `build_right_panel`. |
| `tests/` | 93 files, 1,146 `def test_` | `[BRIEFING]` for both counts. A definition count, never a pass count. |
| `docs/design/` | 160 files, 5,702,497 B | `[BRIEFING]`. Where the register and the plans live. |

The shape to internalise immediately: **one enormous application file** (611 kB)
next to a genuinely modular library. `server/poc_app.py` is not a monolith
because nobody cared; it is a monolith because the page model, the CLI and the
UI are three views of one data shape, and splitting it has been repeatedly
deferred. Plan your work with that in mind — a change to the page dict touches
everything.

---

## 4. How to run it

**The app.** `server/poc_app.py` is both the web app and an argparse CLI. It
binds `127.0.0.1:8080` by default (`DEFAULT_HOST` at `server/poc_app.py:140`,
`DEFAULT_PORT` at `server/poc_app.py:143`) and does **not** auto-open a browser
(`open_browser=False` at `server/poc_app.py:4497` and `:7885`). The exact
invocation is not restated here because this pack did not run it; read the
argparse block at the end of the file.

**The browser dependency trap.** `server/poc_app.py:3739` tries
`trame.ui.vuetify3` first and falls back to `trame.ui.vuetify2`. If you install
`trame` without a vuetify package, you get a failure that reads like a bug in
this app and is not.

**The study harness.** `evidence/termination/run_build_A.py` is what produces the
visualisation dumps. `--vis-dump` at `:3332`, `--dump-stride` at `:3344`, and the
two record frequencies at `:560-561` (`VIS_F_PULSE_HZ = 15.0e9`,
`VIS_F_REF_HZ = 5827786408.327286`). Dump cadence likewise has a library-side
default: `DEFAULT_VOLUME_STRIDE = 100` at `emfit/config.py:79`, carried on
`RunConfig.volume_stride` at `emfit/config.py:122`.

**The tests.** pytest is 9.2.0. Expect this first:

```
pytest --collect-only          # ABORTS on tests/test_abc.py
pytest --ignore=tests/test_abc.py
```

The abort is not your environment being wrong in an interesting way — it is a
stray compiled `emfit_core` extension shadowing the Python reference, and
`emfit/evolve.py:260` raising `RuntimeError` with the explanation. Full chain and
caveats in `03_KNOWN_BUGS.md` §8. Note that the trailing claim in that section is
**UNVERIFIED**: the five `.so` paths were briefed, and a glob for them returned
nothing.

---

## 5. Where the truth lives

- `docs/design/defect_register.md` — 947 lines. The defects. Authoritative over
  every summary, including `03_KNOWN_BUGS.md`.
- `docs/design/graded_meshing_plan.md` — 650 lines. The current front of work.
  **DESIGN ONLY**: no `emfit/` file was edited, no graded grid was built or run,
  and the throwaway test module `tests/test_graded_meshing.py` was written, run
  and then **deleted**, so that no red test is left in the tree. Details in
  `02_PHYSICS_ROADMAP.md`.
- `docs/design/UM3K_UI_ARCHITECTURE.md` — 604 lines. The UI structure.
- `docs/design/GEN13_HANDOFF.md` (4,691 B) and `docs/design/GEN12_HANDOFF.md`
  (27,138 B) — the immediate predecessors. Read by path; do not paraphrase them
  into the register.
- `docs/design/roadmap-next-2026-11-08.md` — **partly stale**. Sections 2
  (`:136`) and 6 (`:456`) read as though work that has since started has not.
  Do not take a "not started" from that document at face value.

The code is the last word: `server/poc_app.py` for the app, `emfit/` for the
solver. Everything above is commentary on those two.

---

## 6. Three ghosts from earlier handoffs

Prior handoffs carried three claims that are false. They are recorded in full,
with evidence, in `03_KNOWN_BUGS.md` §9. Summary:

1. *"`_volume_quiver_mesh` does not exist."* — It does
   (`server/poc_app.py:9315`).
2. *"`tests/test_animation_volume.py` has an `xfail`/`finalizer` teardown
   bug."* — It has neither; only three `importorskip` guards at `:50-54`.
3. *"Something uses `vi.Plane`."* — Nothing does; zero matches repo-wide.

The pattern worth noticing: all three are statements of **absence**, and
absences are the cheapest claims to make and the most expensive to act on.
Nothing gets deleted because of a claim that a thing exists.

---

## 7. The naming rules you can break the build with

Two conventions in this tree are load-bearing, and both are about stored data.

**Schema strings are data, not identifiers.** `VIS_SCHEMA = "emfit.vis/2"`
(`server/poc_app.py:149`) sits next to `VIS_LEGACY_SCHEMAS =
("emfit.wavedude/1", "emfit.wavedude/2")` (`:158`). The comment there is the
policy: *these literals are STORED DATA, not identifiers ... none of them is
renamed and every one still opens.* The accepted set is
`VIS_SCHEMAS = (VIS_SCHEMA,) + VIS_LEGACY_SCHEMAS` (`:159`). Renaming a legacy
literal to tidy the naming orphans every dump on disk.

**Old states do not get new keys.** `STATE_SCHEMA_VIS = "emfit.poc-state/3"`
(`server/poc_app.py:167`) adds `load_series` and `load_series_reason`. The older
`emfit.poc-state/1` (`server/poc_app.py:2062`) stays byte-for-byte identical and
must never gain those keys. An upgraded *reader* fills them in; the old *writer*
does not.

The same idea appears in the format name: `VIS_FORMAT = "um3k"` (`:160`) with
`VIS_FORMATS = (VIS_FORMAT, "wavedude")` (`:161`) — new name, old name, both
open.

---

## 8. Your first day

1. Read §2 of `03_KNOWN_BUGS.md`. Understand DR-47 before you run anything.
2. Get the suite to collect: `pytest --collect-only --ignore=tests/test_abc.py`.
   Read `03_KNOWN_BUGS.md` §8 for why, and do not "fix" it by deleting `.so`
   files until you have confirmed which one is on the import path.
3. Start the app with no dump at all and click everything. You are the first
   person in several generations whose clicking is worth anything, because the
   suite does not click (DR-47).
4. Open `docs/design/graded_meshing_plan.md` and read §1 and §8. §1 is the
   question; §8 is what the plan explicitly did not decide. Everything between is
   a ruling you may still argue with.
5. Write down one thing in this pack that is wrong, and correct it. There will be
   at least one.

---

## 9. What this pack is not

- Not a tutorial on FIT, transmission lines, or S-parameters. The book chapters
  under `docs/report/` are that, and `docs/design/latex_structure.md` inventories
  them.
- Not a substitute for the register, the handoffs, or the code. It is a map, and
  a map that disagrees with the ground is worth exactly nothing. When this pack
  and a cited line disagree, the line wins.
- Not dated. See DR-45: no file in this tree may carry a date later than the
  newest commit. Quote a commit hash and a subject line instead.
