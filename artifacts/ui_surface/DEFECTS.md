# UI defects — poc_app.py / um3k_panels.py

Severity-ordered; line numbers are survey-time. Every claim was verified by reading the
code (NPZ claims by measuring the actual key sets). Nothing was modified to write this.

---

## A. Confirmed defects

### A-1 (worst) — Left-column page-source header goes stale after a live solve

**Symptom.** After a solve (or a page/dump load) the left-column header keeps naming the
*previous* file — the first text a user reads, so the most visible wrongness in the app.

**Evidence.**
- `state.page_source_text` is written **once**, at boot: `poc_app.py:10309` (otherwise
  only its definition, `_page_source_text` `882`).
- The post-solve refresh block, `_rebuild_sheets` (`poc_app.py:11437-11456`), re-assigns
  `structure_readout`, `velocity_label`, `scale_label`, `velocity_note`, `frame_max`,
  `mode_view_*`, `mode_choice*` — but **not** `page_source_text`.
- The template reads the stale value at `um3k_panels.py:38`.

**Class.** Stale-output: a template-bound key refreshed on some paths but not on the
post-solve path.

**Fix (1 line).** Insert after `poc_app.py:11444`:
`state.page_source_text = _page_source_text(live, nt)`.

---

### A-2 — `ctx.available` is never rebuilt after the page is swapped, so `solve_disabled` / `solve_label` can lie

**Symptom.** On a page whose capability flags differ from the boot page, the Solve button
can be shown enabled when the current page cannot be solved (or disabled when it can), and
the button caption can describe the previous page's capability.

**Evidence.**
- `ctx = um3k_context.PageContext(...)` is built **once** at `poc_app.py:10324` and never
  rebuilt, though `_poll_solve` swaps the page in via `apply_page` (`12741`).
- It then computes `solve_disabled = _solve_refused_page(nt, ctx.available)` (`12811`):
  **new** timeline, **old** capability flags.
- `state.solve_label` is written once at `poc_app.py:12666` from `_solve_refused_page` and
  is never recomputed.

**Class.** Mechanism defect under A-1: the same "refresh everything except X" pattern, at
object-lifetime rather than state-key level.

**Fix (~5 lines).** Refresh `ctx` in `_poll_solve` (near `12735-12815`) after `apply_page`,
then recompute `solve_disabled` and `solve_label`.

---

### A-3 — "Far Field" tab cannot render on any shipped artefact (permanently blank)

**Symptom.** Clicking the second DATA tab shows an empty panel on every example in the repo.

**Evidence.** The six shipped NPZ key sets (INVENTORY.md §8) carry no far-field surface
archive: `artifacts/live_run.npz` (richest, 43 keys) has plane/volume/j-cut fields,
`vis_dump_*` cut- and port-plane geometry. No content gate (`visible_right_tabs` shows it
unconditionally): offered, and renders nothing.

**Fix (either).** (a) ship one `--surface-dump` example artefact, **or** (b) give the tab a
caption mirroring the other blankness messages, at `poc_app.py:12516-12532` (~10 lines).
Preference: both — (b) is cheap, (a) makes the tab honest.

### A-4 (post-survey) — a ×100-decimated volume was played as continuous motion

**Symptom.** The reference dump stores every 100th step (24 frames of 2,400); the player
showed them as a smooth clip labelled `frame 3 / 24`, the 200 skipped steps per click
unsaid.

**Evidence.** `e_abs_volume_stride=100`, `e_abs_volume_step_index[:4] = [1,101,201,301]`;
`_frame_label` (`poc_app.py:599`) printed only `frame {i+1} / {frames}`. It now takes the
loader's `TimeAxis` (`:12059-12061`) and prints `Step 301 / 2400 (Frame 4 of 24, Volume
Decimated ×100)` — the clause only when `stride > 1`, `frame k / n` for another clock, a
zero-based record or no axis.

**Class.** Recorded fact not rendered. **Fix (1 line).** Pass `info[TIME_AXIS_KEY]` in.

Tag: fixed in code and pinned by a test, never looked at in a browser. Pinned by
`test_playback_honesty.py::test_the_label_names_the_step_the_picture_was_taken_at` and
`::test_one_step_per_frame_when_the_dump_records_no_stride`.

### A-5 (post-survey) — the temporal aliasing was measured and never shown

**Symptom.** The reference field turns 411.820° between stored frames, so neighbouring
frames are unrelated samples of the wave; the page played them as a continuation.

**Evidence.** `_volume_aliasing` (`:874`) measures the advance per stored frame (probe phase
scaled by `stride`, else `2π·f·dt·stride`) and grades it: past a full period
`discontinuous`, past a quarter period `undersampled`, else `none`.
`_aliasing_sentence` (`:658`) returns `Temporal Aliasing: Volume is decimated ×100. Wave
motion is not continuous between frames.`; `_emit_aliasing_banner` (`:7037`) draws it only
when `aliased and stride > 1`, and an undecidable recording reports
`phase_per_frame_rad=None` and no banner rather than a guess.

**Class.** Measured property of the data held back (A-4's family). **Fix (1 line).**
Compute the report at draw time and emit the banner.

Tag: fixed in code and pinned by a test, never looked at in a browser. Pinned by
`test_playback_honesty.py::test_the_reference_volume_reports_the_alias_it_really_shows`
(the exact ×100 sentence) and `::test_a_reference_frequency_fires_the_quarter_period_rule`.
NOT pinned: the html_div reaching the layout — no test builds the page and looks.

### A-6 (post-survey) — the colour window was neither named nor scoped

**Symptom.** Frames were painted on one whole-recording range (the right default) but
nothing said so, nor that the cut sheets keep ranges of their own, and the per-frame mode
that hides the decay was unoffered or unwarned.

**Evidence.** Run Config carries a `Color Scale:` select (`:13142`) over `Global
(Comparable)` / `Per-Frame (Max Contrast)`; `VOLUME_CLIM_CAPTION` (`:9858`) scopes the
claim to "this volume" and excepts the |Ez| sheets, "so colors are not comparable between
them and the volume". Per-frame raises `VOLUME_CLIM_PER_FRAME_WARNING` (`:9820`):
"Warning: Per-Frame (Max Contrast) re-references the color scale to each frame's own peak,
so the amplitude decay between frames is not visible." The bar title names the window
(`_volume_bar_title` → `|E| (Log) - Global (Comparable)`).

**Class.** Unstated default. **Fix (1 line).** One select, caption, gated warning, title.

Tag: fixed in code and pinned by a test, never looked at in a browser. Pinned by
`test_playback_honesty.py::test_the_select_items_literal_carries_both_tokens_and_both_window_titles`,
`::test_the_caption_bounds_what_comparable_is_allowed_to_mean`, and
`test_poc_run_config_panel.py::test_the_clim_select_offers_readable_labels_bound_to_tokens`,
`::test_the_warning_banner_is_gated_on_the_state_flag`. NOT pinned: the caption reaching
the card, or a browser accepting the select.

---

## B. Dead surface (verified, with one important negative result)

### B-1 — "Mesh size" selector is disabled, unbound and handler-less

`VSelect` at `poc_app.py:12270-12290`: `disabled=True`,
`v_model=("mesh_size_placeholder","fixed (0.5 mm)")`, no `@change`. **Deliberate** — the
adjacent comment says so — a read-only display dressed as a control, and the only
reachable control that can never act.

### B-2 — The entire legacy `run_web` page is orphaned (853 lines)

`poc_app.py:5922-6774`. `main()` (`poc_app.py:13290`) dispatches *every* schema entry to
`run_web_vis`; `tests/test_poc_dispatch.py:108-155` asserts that. Its controls — structure
select `6490`, station `6623/6711`, view toggle `6610/6611` — are therefore unreachable.
Keys templated **only** there: `structure_note` (`6094/6727/6730`), `station_label`
(`6088/6745`), `view_label` (`5757/5855/6229`), `dump_freq_label` (`6117`), `structure`
(`6093/6725`) — written and read by dead code only.

### B-3 (negative result) — there is **no** written-and-never-read state key in the live shell

Looked for the classic dead-state defect; none. The only dead state *name* in the
reachable page is `mesh_size_placeholder`, a client-side `v_model` placeholder absent from
`state_keys.tsv`; every other `state.<name>` with `n_reads == 0` in Python is read by the
Trame template (INVENTORY.md §6). Recorded so the next reviewer does not re-spend it.

---

## C. Checked and cleared (not defects — recorded to prevent re-investigation)

### C-1 — `station_readout` being static is correct

Written once at `10380`, template `13136`, `_emit_station_readout` `13105` — an A-1 look
but not one: `state.station` is itself set once at `10375` and the live page never
re-stations. (If it ever does, this becomes an A-1-class defect.)

### C-2 — `_poll_solve` does refresh the other solve keys

`solve_status` and `run_config_visible`/`solve_disabled` **are** reassigned at
`12811-12812`, and the `s_params` / `confidence` / `far_field` caches are popped and
refilled at `12746-12760` — A-1 is a genuine omission, not a page-wide failure.

### C-3 — Tab selection is correctly wired

`VTabs`/`VTab` set `value=` explicitly on both sides (`um3k_panels.py:423-453`, fix comment
noting the earlier bug); a stacked-panel fallback exists at `476-499`.

---

## D. Documentation complaints (thin — stated honestly)

A grep for UI complaints ("broken", "missing", "placeholder", "doesn't work", …) across
`docs/decisions.md`, `docs/RESUME.md`, `Intro.txt` and the report found **none beyond the
above**. Two findings only: `docs/design/GEN12_HANDOFF.md:72` (`:132` too) notes the
`poc_app.py:49-55` docstring calls the Trame path **UNTESTED** (doc staleness), and
`docs/report/sec_impl.tex:202` remarks the page is built whole before headers.
`docs/kb/PROCEDURE.md:111,295-296` matched "stale-status header" but is a header
convention. Genuinely thin, reported as thin rather than padded.

---

## Top-3 fixes for first impression

1. **A-1** — refresh `page_source_text` after `poc_app.py:11444` (1 line): the first text a
   user reads names the wrong file.
2. **A-2** — refresh `ctx` in `_poll_solve` (`12735-12815`, ~5 lines): `solve_disabled` /
   `solve_label` can describe the previous page.
3. **A-3** — ship a far-field artefact or caption the empty tab (`12516-12532`, ~10 lines).

Total: ~16 lines of change, no architecture work. (A-4..A-6 are honesty fixes, not
first-impression ones: the page was wrong about numbers the file already contained.)

---

## E. Fix log (code changed after the survey above)

Line numbers in sections A-C are SURVEY-TIME; the insertion points below are where the
fixes landed. Verified for all three rows: `ast.parse` clean, the KB gate unchanged at
3 failed / 7 passed / 1 xfailed (A2/A4/A10: no git binary), and `--dump-state` identical
before vs after except `generated_utc` — 17 keys in both, same key set, same values.
All three rows carry the same tag: fixed in code, not exercised in a browser.

- **A-1 fixed** - `server/poc_app.py:11455` (inside `_rebuild_sheets`, after `velocity_note`):
  `state.page_source_text = _page_source_text(live, nt)`. The swap now prints the dump line
  from the same pure helper boot uses, with the page's own `nt` (synced at `:11401`).
- **A-2 fixed** - `server/poc_app.py:12770-12781` (in `_poll_solve`, after `apply_page`)
  plus `:12837-12844`. NOT a new `PageContext`: `ctx.dump` is replaced and the documented
  reload path `ctx.recompute_available()` (`server/um3k_context.py:179-189`) re-scopes it,
  so the build-time handles and callbacks survive; `solve_disabled` / `solve_label` are then
  recomputed from the fresh snapshot (label as at `:12675`).
- **A-3 fixed via (b) only** - `server/poc_app.py:9839-9842`: the empty-panel caption now
  reads "this tab needs a Huygens surface dump: pass --surface-dump PATH to plot a
  far-field pattern, and no shipped evidence file carries a surface record, so it stays
  empty on all of them". Option (a) not taken: no such artefact exists, and inventing one
  would be fabrication.

Stale cross-reference noticed, left alone: `artifacts/ui_surface/INVENTORY.md:105` points at
"DEFECTS A-4", but the far-field row is **A-3**; A-4 is now the decimated-volume row.
