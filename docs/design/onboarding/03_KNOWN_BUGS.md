# 03 — Known bugs, and claims that turn out to be ghosts

This file is a *digest with deep dives*. The source of truth is
`docs/design/defect_register.md` (947 lines). When this file and the register
disagree, the register wins and this file is wrong — fix it.

The register is not a list of "things that are broken so we can feel bad". It is
the record of what has already cost someone a day. Read the deep dives in the
order given: **DR-47 first**, because it changes how much you may believe every
other green test in the repo.

Severity and status below are copied from the register headers. Nothing in this
file closes a defect. Only the register closes a defect, and only with the gate
it names satisfied.

---

## 1. Map of the register

| Id | Register line | Severity | State | One line |
|---|---|---|---|---|
| DR-40 | :725 | MEDIUM, latent | OPEN | The load-station filter un-filters itself. |
| DR-41 | :760 | see register | fixed with tests | — |
| DR-42 | :783 | see register | fixed with tests | — |
| DR-43 | :826 (amendment :863) | see register | FIXED-TESTED, residual gap | A pulse-writer artefact lacked `s21.measured`. |
| DR-44 | :871 | MEDIUM | OPEN | An untracked file was overwritten in place and is unrecoverable. |
| DR-45 | :891 | MEDIUM | OPEN, partly corrected | Document dates later than the newest commit. |
| DR-46 | :913 | MEDIUM–HIGH | OPEN | Bare `NaN` written into `gamma_plane` in six in-tree artefacts. |
| DR-47 | :931 | **HIGH** | OPEN | No `@state.change` listener anywhere is executed by the suite. |

DR-41 and DR-42 are fixed and tested; their headers are worth reading once for
the *shape* of a closed entry (what evidence was accepted) rather than for the
bugs.

---

## 2. DR-47 — the suite never runs a single UI listener

**Register line 931. Opened 2026-11-13. OPEN, HIGH. This is the most dangerous
entry in the tree.**

### The mechanism

`tests/test_poc_playback.py` has a `_boot_app` fixture that replaces
`server.start`. Because `server.start` is the thing that calls
`protocol.port_callback`, that callback never runs. `state.is_ready` therefore
stays `false`, and trame's `State.flush()` **refuses to dispatch** while the
state is not ready.

The consequence is not "some tests are weak". It is: no `@state.change`
listener, anywhere in the application, is ever executed by the test suite. Not
the solve button. Not the mode picker. Not the frame slider. Not the plane
selector.

### The two pieces of evidence that make it undeniable

1. `tests/test_poc_mode_picker.py` calls `srv.state.ready()` **explicitly** —
   i.e. some author already discovered that the state has to be declared ready
   before anything dispatches, and patched it locally instead of in the shared
   fixture.
2. `tests/test_poc_playback.py::test_solve_button_reloads_the_page` asserts that
   the *string* `_start_watch` occurs inside the solve press closure. That is a
   source-text assertion, not a behavioural one. It is the honest admission that
   the test cannot observe the effect, so it reads the code instead.

### Do not conclude from this that the source-text assertion was worthless

It caught a real regression. An edit deleted the `_start_watch()` call, and
because the chain `_start_watch` → `_watch_solve` → `_poll_solve` →
`apply_page` became unreachable, a solving page never refreshed. A source-text
assertion caught what no behavioural test in the suite could, precisely because
the behavioural tests cannot dispatch. That is the point: the weak test is
load-bearing *because* the strong ones are silently inert.

### The fix, and the gates that close it

Fix = call `state.ready()` in the **shared** fixture (not per-test), add a
listener registry, and record the re-baselined test count in the commit body.

Gate 1. The fixture must produce a state in which `flush()` actually
dispatches, and the resulting change in test count must be recorded in the
commit body. A fix that silently makes forty tests fail is a fix that gets
reverted at 2 a.m.; a recorded re-baseline is auditable.

Gate 2. At least one test per interactive control must assert that the listener
**fired**, demonstrated by an observable effect — not by the presence of a
string in a closure. "Observable effect" means a changed field, a changed page,
a captured call. Not `assert "_start_watch" in inspect.getsource(...)`.

Until both gates are met, treat any claim of the form "the UI is tested" as
unverified.

---

## 3. DR-46 — bare NaN in six artefacts

**Register line 913. OPEN, MEDIUM–HIGH. No closure.**

### What happens

`evidence/termination/run_build_A.py:3896-3901` writes
`gamma_plane.{re,im,abs,arg_deg}` **unconditionally**, from
`gp = complex(res.gamma_plane)` at `:3608`. When there is no gamma plane, that
expression yields `NaN` for every component and the file gets the `NaN` anyway.

This contradicts the comment recorded at `:2626-2630`, which says the value is
"left out rather than written as nan". The comment describes the intent of the
author of that block; the writer at `:3896-3901` does not implement it.

The acceptance-criterion side is already strict and already disagrees with the
file: AC-6 sets `gamma_plane_recorded` to `False` (`:2846-2849`) and
`"pass": False` (`:2853-2856`). So the code knows the plane was not recorded, and
writes `NaN` anyway.

### The six in-tree artefacts that carry it

- `build_A_50ohm.json`
- `build_A_50ohm_nsub6_p76.json`
- `build_A_n_default_p51.json`
- `build_A_p51_n4800.json`
- `build_A_p51_n9600.json`
- `gate_gate_build_A_p51.json`

### Why it is dangerous

A bare `NaN` is a **value that looks like a value**. `json.load` succeeds.
`float("nan")` is a float. A downstream comparison does not raise, it returns
`False`, and a `False` in a pass/fail field reads like a failed measurement
rather than like a missing one. The distinction between "we measured it and it
was bad" and "we never measured it" is exactly the distinction this project
insists on everywhere else.

### What closing it needs

1. A stated convention: absent means key absent, or key present with `null`.
   Not `NaN`. Pick one and write it where artefact consumers will see it.
2. A schema-version key, so old artefacts can be read under the old convention
   instead of silently reinterpreted.
3. Then a sweep of the six files, or a stated decision to leave them and mark
   them legacy.

Do not "fix" this by having consumers test `isfinite` and move on. That is
already what the *draw* sites do, and it is why the defect survived: every
consumer that happened to check hid the bug from the next one that did not.

---

## 4. DR-45 — dates later than the newest commit

**Register line 891. OPEN, MEDIUM. Partially corrected.**

The register's argument: documents in this tree carried dates of 2026-11-14
while the newest commit was 2026-11-12. A two-day gap on a project whose whole
method is provenance is not cosmetic — a date that is later than the last commit
is a date that describes something that was never committed.

### Already corrected

- `EM_SOLVER_LEDGER.md:28`, `EM_SOLVER_LEDGER.md:30`
- `session_open_gen11.md:3`

### Still wrong in the tree

- `docs/design/visualizer_architecture.md:7`
- `docs/design/lessons_learned_emfit_addendum.md:28`

### Corroborating evidence in the register

Commit `be803fd` was an *earlier, identical* correction — this class of error has
now been fixed twice, which means it is a process failure and will recur. And
`artifacts/ladder_engine_scaling.json` carries
`assembled_utc: 2026-11-12T14:53:20Z`, which is consistent with the
2026-11-12 commit date and not with a 2026-11-14 authorship.

### A caution this pack adds

File mtimes in `emfit/` and `server/` reach 2026-11-16. Those are checkout
timestamps, not authorship, so nobody should close DR-45 by comparing them.
This pack ran git instead of trusting the premise, and the premise fails at
the head it read: the newest commit is dated 2026-11-16, four days past the
2026-11-12 the register calls newest. Every date DR-45 lists is now in the
past — the item is history now, and the register must restate it.

### The rule this defect produced

**No file in this tree may carry a date later than the newest commit date.**
This pack obeys it by carrying no generation date at all. When you write a
document, quote a commit hash and a subject line; those cannot drift.

---

## 5. DR-44 — the untracked file that was overwritten and lost

**Register line 871. OPEN, MEDIUM.**

49,352 bytes of untracked `docs/design/GEN12_HANDOFF.md` were replaced in place.
The content was never in the object store, so it is **unrecoverable** — not
"hard to find", gone. The current `docs/design/GEN12_HANDOFF.md` (27,138 B) is
the replacement introduced by commit `bd2d9b9`, not the destroyed draft.

This is the cheapest defect in the register to prevent and the most expensive to
have. The rule it produced:

> Before writing to any path that already exists, check `git status` for that
> path. If it is **untracked**, rename or copy it aside first. An untracked file
> has no copy anywhere. Overwriting it is a delete with no undo.

Corollary: a directory being "not part of the project" is not protection.
`docs/design/` is exactly where a scratch draft lives, and exactly where this
happened.

This pack wrote into a new directory, `docs/design/onboarding/`, and created no
path that already existed, so the rule did not need to fire — but check before
you add to it, because a successor pack will.

---

## 6. DR-40 — the load-station filter un-filters itself

**Register line 725. OPEN, MEDIUM, latent.**

The load station's filter re-enables itself, so a filtered view silently becomes
unfiltered. "Latent" is the register's word and it is the right one: nothing in
the current test suite catches it, and the drift is visible only to someone who
knows what the filtered list is supposed to look like.

Do not treat this as cosmetic because the severity is MEDIUM. A filter that
turns itself off produces a screen that looks correct and a number that is
computed over the wrong set.

---

## 7. DR-43 residual, and how "fixed" is recorded here

**Register line 826, amendment block at :863.**

DR-43 is marked FIXED-TESTED because `tests/test_dr43_pulse_writer.py` pins the
behaviour, taking 41.87 s. Read the amendment block once — it is the best
example in the register of the three different claims this project keeps
separate:

- **VERIFIED-BY-RUN** — someone ran it and looked at the output.
- **FIXED-TESTED** — a test in the tree fails if the behaviour returns.
- closed.

They are not the same, and DR-43 is VERIFIED-BY-RUN *and* FIXED-TESTED while
still carrying an open gap: the pre-fix artefacts in the tree still lack the
`s21.measured` key. A fix does not retroactively repair data that was already
written.

---

## 8. B-5 — the test suite cannot even collect one file

Not in the register as a DR entry, but it is the first thing that will stop a
new engineer, so it is recorded here.

`pytest --collect-only` **aborts** on `tests/test_abc.py`. Running with
`--ignore=tests/test_abc.py` fixes it. pytest is 9.2.0.

### The chain

1. `tests/test_abc.py:48` does `from emfit.evolve import FITStepper`.
2. `emfit/evolve.py:255` defines `_probe_kernel_files()`, and `:260` raises
   `RuntimeError` with the text *"emfit_core exists on disk but could not be
   imported"*.
3. The message lists the extension files it found, and says the process
   *"would have run the Python reference and recorded step_engine='python'"* —
   i.e. the code knows it has a reference path and refuses to take it silently.

So a stray compiled `emfit_core` extension shadows the pure-Python reference and
the import of `emfit.evolve` fails at collection time.

### Status of the five stray copies

The briefing for this pack listed five: `.venv/lib/python3.12/site-packages/`,
`build/cpp/`, and `build/phase2/{o2,o2lto,o3}/`, each
`emfit_core.cpython-312-x86_64-linux-gnu.so`.

**UNVERIFIED.** A glob for `**/emfit_core*.so` in this repo returned zero
results, which is more likely a limitation of the glob than proof of absence —
the `RuntimeError` above is raised by code that *found* such a file. Treat the
five paths as the briefing's, not as confirmed, and confirm them yourself before
deleting anything. Deleting the wrong one changes which engine a study runs on,
and `step_engine` is recorded in artefacts.

`tests/test_abc.py` itself is 326 lines, with a module docstring about the Mur1
absorbing boundary; it imports `emfit.abc`, `emfit.evolve`, `emfit.grid`,
`emfit.materials`, `emfit.operators`, `emfit.pml`.

---

## 9. Ghosts — three claims that are false

Prior handoffs carried three claims about this tree that are not true. They were
checked directly; each verdict below is a search result, not an impression.
Recording them is not point-scoring — each ghost, if believed, causes a specific
piece of wasted work.

### G-1 — "*`_volume_quiver_mesh` does not exist; it is a phantom symbol*"

**False.** It exists and is live:

- definition: `def _volume_quiver_mesh(info, *, stride=VOLUME_QUIVER_STRIDE)` at
  `server/poc_app.py:9315`
- called at `server/poc_app.py:6116` and `server/poc_app.py:9431`
- referenced in `tests/test_poc_volume_arrows.py` (`:440`, `:506`, `:508`,
  `:543`, `:557`, `:569`, `:952`, `:991`, `:1023`, `:1061`) and in
  `server/um3k_context.py:98`

Damage if believed: someone "removes dead code" that two call sites and a test
module depend on. This function is also this pack's worked example of a silent
failure (see `00_README.md`, rule 3), which is presumably where the rumour came
from — it is easy to *miss* it by searching the wrong module.

### G-2 — "*`tests/test_animation_volume.py` has an `xfail` / `finalizer` teardown bug*"

**False.** The file (1,385 lines) contains **zero** occurrences of `xfail` and
**zero** of `finalizer`. The only `skip` hits are three module-level import
guards:

- `:50` `pytest.importorskip("pyvista")`
- `:51` `pytest.importorskip("trame.app")`
- `:52-54` `pytest.importorskip("trame.ui.vuetify3")`

Those are import guards, not test skips, and they are not a teardown bug. If
pyvista or trame is missing the whole module is skipped with a reason, which is
the correct behaviour for a rendering test. Nor is the claim rescued by the
masking story — that a skip or an `xfail` is concealing a real teardown failure —
because the guards fire on a missing dependency at module import and never on a
failing teardown, so there is nothing there to conceal.

**True, adjacent, and now fixed.** A real teardown fault did live in this same
file, and it is a *different* bug from the one claimed here, so the ghost is not
evidence for it in either direction. `_boot` installed its `start` double on the
**class** first (`patch.setattr(trame_server.Server, "start", _no_start)`), and
then doubled the instance as well; `MonkeyPatch` records an instance patch with
`getattr`, i.e. through the MRO, so what it recorded for `srv` was the class
double it had just installed — and its undo wrote that double back onto the
instance once the class was restored, leaving `srv.start` doubled for the rest of
the session. The repair restores the instance by hand from a value saved before
the patch (`shadow = vars(srv).get("start")`, `:238`): `vars(srv).pop("start",
None)` when there was no instance attribute, `srv.start = shadow` otherwise
(`:264-273`, with the mechanism spelled out in the comment at `:264-269`). Commit
`a588603` *"fix(tests): restore the shared trame server in animation volume
teardown"* carries it, and that commit touches **only** this test file, so no
other code citation in this pack moved with it.

Damage if believed: someone "fixes" a teardown that does not exist, and possibly
removes the import guards, turning a clean skip into a hard collection error.

### G-3 — "*something in the tree uses `vi.Plane`*"

**False.** Zero matches repo-wide for `vi\.Plane` across the `.py` files
searched (569 files).

Damage if believed: you go looking for a call that is not there instead of at
the code that is.

---

## 10. What looks broken and is not

Three things read like defects and are design decisions. Do not "fix" them.

1. **The legacy schema literals** — `"emfit.wavedude/1"` and
   `"emfit.wavedude/2"` in `VIS_LEGACY_SCHEMAS` (`server/poc_app.py:158`)
   alongside `"emfit.vis/2"` (`:149`). The comment above them is the policy:
   *these literals are STORED DATA, not identifiers; none of them is renamed and
   every one still opens.* Renaming one to tidy the naming would orphan every
   dump on disk.

2. **`emfit.poc-state/1` not gaining the new keys** — `STATE_SCHEMA_VIS` is
   `"emfit.poc-state/3"` (`server/poc_app.py:167`) and it adds `load_series` and
   `load_series_reason`. The older `emfit.poc-state/1` (`server/poc_app.py:2062`)
   must stay byte-for-byte identical and must *never* gain those keys. An
   upgraded reader fills them in; the old writer does not.

3. **The "bare board" page with `NaN` everywhere** — see `01_ARCHITECTURE.md` §6.
   `_bare_board_page` writes `NaN` for every unknown field *on purpose*, because
   the draw sites test `isfinite()` and a constant would draw a
   plausible-looking wrong board. This is the opposite of DR-46: there, `NaN`
   reaches a *file that claims to be a record*; here it stays inside a page that
   claims nothing.

---

## 11. How to add an entry

Follow the register's own shape, because a reader scanning it needs a predictable
one:

1. Numbered `DR-NN` header with date opened, severity, and state.
2. The mechanism, with file:line for both the cause and the contradicting
   comment or acceptance criterion, if one exists.
3. The evidence — what you ran, what you read, and what it said.
4. Gates. Explicit, checkable conditions under which the entry may be closed.
   "Looks fine now" is not a gate.
5. Status line at the bottom, and if a gate is only partly met, say which part.

And the standing rule from DR-44: **check `git status` for a path before you
overwrite it; if it is untracked, put a copy somewhere first.**
