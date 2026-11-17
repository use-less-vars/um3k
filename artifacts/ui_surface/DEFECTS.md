# UI defects — poc_app.py / um3k_panels.py

Severity-ordered. Line numbers are file line numbers at survey time. Every claim below was
verified by reading the code (and, for the NPZ claims, by measuring the actual key sets).
Nothing in the source was modified — this is an analysis artefact.

---

## A. Confirmed defects

### A-1 (worst) — Left-column page-source header goes stale after a live solve

**Symptom.** After the user solves (or loads a different page/dump) the header in the left
column keeps naming the *previous* file. It is the first text a user reads, so it is the
most visible wrongness in the app.

**Evidence.**
- `state.page_source_text` is written **exactly once** in the whole program, at boot:
  `poc_app.py:10309`. A grep for the name returns two hits only — the definition
  `_page_source_text` at `882` and that single assignment at `10309`.
- The refresh block that runs after a solve, `_rebuild_sheets` `poc_app.py:11440-11444`,
  re-assigns `structure_readout`, `velocity_label`, `scale_label`, `velocity_note`
  (and `11448-11449` `mode_view_label`/`mode_view_caption`, `11455-11456`
  `mode_choice_items`/`mode_choice`, `11437` `frame_max`) — but **not** `page_source_text`.
- The template reads the stale value at `um3k_panels.py:38`.

**Class.** Stale-output: a template-bound key refreshed on some paths but not on the
post-solve path.

**Fix (1 line).** Insert after `poc_app.py:11444`:

```python
state.page_source_text = _page_source_text(live, nt)
```

---

### A-2 — `ctx.available` is never rebuilt after the page is swapped, so `solve_disabled` / `solve_label` can lie

**Symptom.** On a page whose capability flags differ from the boot page, the Solve button
can be shown enabled when the current page cannot be solved (or disabled when it can), and
the button caption can describe the previous page's capability.

**Evidence.**
- `ctx = um3k_context.PageContext(...)` is constructed **once** at `poc_app.py:10324` and
  never rebuilt, even though `_poll_solve` swaps the page in via `apply_page` at
  `poc_app.py:12741`.
- `_poll_solve` then computes
  `solve_disabled = _solve_refused_page(nt, ctx.available)` at `poc_app.py:12811`,
  combining the **new** timeline (`nt`) with the **old** capability flags.
- `state.solve_label` is written once at `poc_app.py:12666` from `_solve_refused_page` and
  is never recomputed.

**Class.** Mechanism defect underneath A-1: the same "refresh everything except X" pattern,
but at the object-lifetime level rather than the state-key level.

**Fix (~5 lines).** Rebuild `ctx` inside `_poll_solve` (near `12735-12815`) after
`apply_page`, before recomputing `solve_disabled`, and recompute `solve_label` from the
fresh context.

---

### A-3 — "Far Field" tab cannot render on any shipped artefact (permanently blank)

**Symptom.** Clicking the second DATA tab shows an empty panel on every example in the repo.

**Evidence.** Measured key sets of the six shipped NPZ files (see INVENTORY.md §8): none
carries a far-field surface-dump archive. The richest (`artifacts/live_run.npz`, 43 keys)
has plane/volume/j-cut fields only; `vis_dump_*` have cut-plane and port-plane geometry
only. The tab has no content gate (`visible_right_tabs` shows it unconditionally), so it is
offered and then renders nothing.

**Fix (either).**
- (a) ship one `--surface-dump` example artefact so the tab has data on first run
  (~data only), **or**
- (b) give the tab a caption mirroring the other blankness messages
  (`"no far-field surface dump in this artefact — re-run with --surface-dump"`),
  at `poc_app.py:12516-12532` (~10 lines).

Preference: both — (b) is the cheap immediate improvement, (a) makes the tab honest.

---

## B. Dead surface (verified, with one important negative result)

### B-1 — "Mesh size" selector is disabled, unbound and handler-less

`VSelect` at `poc_app.py:12270-12290`: `disabled=True`,
`v_model=("mesh_size_placeholder","fixed (0.5 mm)")`, no `@change`. **Deliberate** — the
adjacent comment says so. It is a read-only display dressed as a control; not a bug, but it
is the only control in the reachable page that can never act.

### B-2 — The entire legacy `run_web` page is orphaned (853 lines)

`poc_app.py:5922-6774`. `main()` (`poc_app.py:13290`) dispatches *every* schema entry to
`run_web_vis`; `tests/test_poc_dispatch.py:108-155` asserts that. Its controls — structure
select `6490`, station `6623/6711`, view toggle `6610/6611` — are therefore unreachable.
State keys templated **only** on the dead page: `structure_note` (`6094/6727/6730`),
`station_label` (`6088/6745`), `view_label` (`5757/5855/6229`), `dump_freq_label`
(`6117`), `structure` (`6093/6725`). They are written/read only by dead code.

### B-3 (negative result) — there is **no** written-and-never-read state key in the live shell

I specifically looked for the classic dead-state defect and did not find one. The only dead
state *name* in the reachable page is `mesh_size_placeholder`, which is a client-side
`v_model` placeholder and never appears in `state_keys.tsv`. Every other
`state.<name>` with `n_reads == 0` in Python is in fact read by the Trame template
(listed in INVENTORY.md §6). Recording this as a negative result so the next reviewer does
not re-spend the effort.

---

## C. Checked and cleared (not defects — recorded to prevent re-investigation)

### C-1 — `station_readout` being static is correct

Written once at `10380`, template `13136`, `_emit_station_readout` `13105`. It looks like
another A-1 instance, but `state.station` is itself set once at `10375` and the live page
never changes station, so there is nothing to refresh. (If a future change lets the live
page re-station, this becomes an A-1-class defect.)

### C-2 — `_poll_solve` does refresh the other solve keys

`solve_status` and `run_config_visible`/`solve_disabled` **are** reassigned at
`12811-12812`, and the `s_params` / `confidence` / `far_field` caches are popped and
refilled at `12746-12760`. So A-1 is a genuine omission, not the tip of a page-wide failure.

### C-3 — Tab selection is correctly wired

`VTabs`/`VTab` set `value=` explicitly on both sides (`um3k_panels.py:423-453`, with a fix
comment noting the earlier bug); a stacked-panel fallback exists at `476-499`.

---

## D. Documentation complaints (thin — stated honestly)

A broad grep for UI complaints ("broken", "missing", "placeholder", "doesn't work", …)
across `docs/decisions.md`, `docs/RESUME.md`, `Intro.txt` and the report returned **no
further UI complaints**. Only two findings:

1. `docs/design/GEN12_HANDOFF.md:72` (repeated at `:132`) — notes that the docstring at
   `poc_app.py:49-55` still declares the Trame web path **UNTESTED**, which is stale
   relative to the operator run. Doc/comment staleness, not a UI defect.
2. `docs/report/sec_impl.tex:202` — observes the page is built whole before headers; a
   performance remark, not a defect.
   (`docs/kb/PROCEDURE.md:111,295-296` matched on "stale-status header" but concern a
   status-header convention, not the UI.)

So this section is genuinely thin; it is reported as thin rather than padded.

---

## Top-3 fixes for first impression

1. **A-1** — refresh `page_source_text` after `poc_app.py:11444` (1 line). The header is the
   first thing a user reads; it currently names the wrong file.
2. **A-2** — rebuild `PageContext` in `_poll_solve` around `12735-12815` (~5 lines) so
   `solve_disabled` / `solve_label` describe the page actually on screen.
3. **A-3** — give "Far Field" either a shipped example artefact or a caption
   (`12516-12532`, ~10 lines); a tab that is silently empty reads as a broken app.

Total: ~16 lines of change, three files' worth of behaviour, no architecture work.

---

## E. Fix log (code changed after the survey above)

Line numbers in sections A-C are SURVEY-TIME numbers; the insertion points below are where
the fixes actually landed. Verified for all three rows: `python3 -c "ast.parse(...)"` clean,
the KB gate unchanged at 3 failed / 7 passed / 1 xfailed (the three failures are the absent
git binary, A2/A4/A10), and `--dump-state` identical before vs after except `generated_utc`
(15 keys, same key set, same values).

- **A-1 fixed** - `server/poc_app.py:11455` (inside `_rebuild_sheets`, after `velocity_note`):
  `state.page_source_text = _page_source_text(live, nt)`. The swap now prints the dump line
  from the same pure helper boot uses, with the page's own `nt` (synced at `:11401`).
  Tag: fixed in code, not exercised in a browser.
- **A-2 fixed** - `server/poc_app.py:12770-12781` (in `_poll_solve`, straight after
  `apply_page`) plus `:12837-12844`. The fix is NOT a new `PageContext`: `ctx.dump` is
  replaced and the documented reload path `ctx.recompute_available()`
  (`server/um3k_context.py:179-189`) is called, so the handles and callbacks registered on
  this context at build time survive. `solve_disabled` AND `solve_label` are then both
  recomputed from the fresh snapshot, the label with the boot expression
  (`"Solve (static field snapshot)" if refused else "Solve"`, cf. `:12675-12677`).
  Tag: fixed in code, not exercised in a browser.
- **A-3 fixed via (b) only** - `server/poc_app.py:9839-9842`: the empty-panel caption now
  reads "this tab needs a Huygens surface dump: pass --surface-dump PATH to plot a
  far-field pattern, and no shipped evidence file carries a surface record, so it stays
  empty on all of them". Option (a), shipping a `--surface-dump` example artefact, was NOT
  taken: no such artefact exists in the repo and inventing one would be a fabricated
  example. Tag: fixed in code, not exercised in a browser.

Stale cross-reference noticed, left alone: `artifacts/ui_surface/INVENTORY.md:105` points at
"DEFECTS A-4", but the far-field row is **A-3** (there is no A-4).
