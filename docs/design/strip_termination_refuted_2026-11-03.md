# Strip termination design — refuted 2026-11-03

**Status: negative result.** The D1 change was applied, exercised and reverted before commit. `emfit/studies.py` is byte-identical to its Phase 0 state: sha256 `254076bc72edefee7901293e95d9da8365e0b5ec70b660dff97d085c8551648f`, 5425 lines, zero occurrences of `nx_clean`, and `git diff emfit/studies.py` is empty. No solve was run, no committed artefact was edited, no criterion was re-priced. This file is the refutation of record for `strip_termination_design_2026-11-02.md`, whose head now carries a `PREMISE REFUTED` line pointing here.

## 1. What was attempted

The D1 diff and nothing else: `nx_clean = nx - n_pml`, with the strip mask (`emfit/studies.py:2706`, `:2709`), the load-column guard and the `s21_plane` guard re-pointed at it. Three hunks, +13/−4, all inside the fence `emfit/studies.py:2701-2810`; net +9 lines (5425 → 5434); no signature change, no new parameter, `py_compile` exit 0. The intent was to end the strip sheet at node `nx - n_pml` rather than node `nx` — to pull the line's end face out of the xmax absorber.

## 2. What broke, and why

Same command, baseline then post-edit, `pytest tests/test_studies.py -k "station or s21 or plane or strip"`: baseline `..........` (10 dots, no `F`); post-edit `........FF`. Both new failures are in the **default, load-free** study and both are design intent, not stale baselines:

* `tests/test_studies.py:503` `assert result.beta == pytest.approx(232.5, rel=0.01)` → obtained `326.8366386149376`, **+40.58 %**.
* `tests/test_studies.py:422` `test_microstrip_wave_refused_station_fit_is_flagged_not_quoted` pins that the station fit **refuses** on a deliberately under-resolved open cut (`pytest.warns(RuntimeWarning, match="loss-aware station-impedance fit")`, then `station_fit_ok is False`, `station_fit_lossy is None`). The changed end condition moved that run's phase-constant standard error, and the test now fails on its own assertions — the dispatch logged the failure as an assertion, not a DID-NOT-WARN, so `station_fit_ok` / `station_fit_lossy` no longer carry the refused values and the pinned refusal no longer describes the run. That is the opposite of a numerical baseline drift.

**The two quantities are different fits.** `result.beta` is the *one-wave* fit (`emfit/studies.py:3086-3088`, assigned `:3639`). `result.gamma` is the *two-wave* `B / A` (`:3643`), and at `emfit/ports.py:960-965` that is literally `gamma = (backward / forward) if forward != 0.0 else complex(0.0, 0.0)` under `if n_wave == 2`. So `tests/test_studies.py:507 assert abs(result.gamma) < 0.02` is a **measured** sub-2 % match on the default run, and `:506`'s own comment — "the standing wave and the misfit that make that believable" — states that as the intent. There was no two-wave check in the diff to catch what the one-wave estimator was reporting.

**Why the baseline is matched.** The strip's x-extent is ex cells `[ix_port, nx-1]` / ey nodes `[ix_port, nx]` (`studies.py:2706`, `:2709`); the xmax absorber's sigma is nonzero on `x ∈ [nx - n_pml, nx]` (`studies.py:2805` puts `"xmax"` in `pml_walls`, `:2814` builds `PML(..., thickness_cells=n_pml, order=2, target=1e-4)`; sigma from `emfit/pml.py:557-562`); and `operators.py:302-307` fixes `i == nx` PEC under that same `"xmax"` wallset. **The strip and the absorber overlap by `n_pml` cells and share node `nx`.** The wave therefore attenuates on the way out *and the reflection attenuates on the way back*: a PEC floor inside the absorber cannot return a strong reflection, whatever its own reflection coefficient is. Threading-into-PML is a CPML-matched end that happens to have a PEC floor behind it — not a shorted stub in front of the line.

**Why +40.58 %.** Shortening the strip to `nx_clean` removes the outbound damping and leaves the wave to hit an open end at `nx_clean`, which is a genuine open-circuit reflection. +40.58 % sits at, or just beyond, the documented +27–36 % one-wave-versus-two-wave bias band for reflective lines (`s11_one_wave_vs_two_wave`); an open end (`|Γ| ≈ 1`) is the extreme of that band's family, not a contradiction of it.

**Scope, not bad luck.** The fence `2701-2810` excluded `PML(...)` at `:2814`, so shortening the strip was the only operation available — and shortening a strip cannot produce an absorbing end. A deliberate termination is a different study, not a retry of this one; it needs the absorber in scope.

## 3. What survives

**Survives.** `passivity_ceiling_2026-11-02.md` §§1–5: the `|s21| <= 1` arithmetic uses no β, no Z₀, no L and no far-end hypothesis, so §3's two arms above the ceiling still stand and the probe at the load column is still contaminated for B and E. Also survives: `closed_form_with_two_wave_beta_2026-11-02.md` §4's L-independence finding.

**Does not survive.**

1. `passivity_ceiling_2026-11-02.md:61` — "... sets the strip mask PEC-true from the port column to node nx, with the xmax PML BEHIND that wall. The line is therefore never terminated — the load sits inside a shorted stub". The ordering is a narrative inference the code does not support: the absorber is *inside* the domain, straddling the strip's own cells, and the wall is behind *it*. There is no shorted stub.
2. The companion claim that the series-R anchor `T = 2Z₀/(2Z₀+R)` never applied. `Z0_SERIES_ANCHOR` is defined at `evidence/termination/run_build_A.py:140` and consumed at `:1263` as `/(2.0 * Z0_SERIES_ANCHOR + args.load_ohm)`, so the anchor is in the harness path. With a PML-terminated line it may well apply, and the gap between the measured `|s21|` at plane 51 (0.7628) and the anchor (0.6553) is then a residual-contamination question, not a structural one.
3. The closed-form document's wall-versus-PML-front framing is moot rather than wrong: it argued about which of the two was in front, and the answer is that the absorber terminates the line.

## 4. Forward reference

Dispatch 4, `gap-analysis-2026-11-03`, owns the next move — read-only, existing artefacts only, no code, no host run, `emfit/studies.py` untouched throughout. It enumerates four hypotheses (evanescent residue at plane 51; PML residual reflection; Z₀ mismatch; quasi-TEM correction to the anchor) and this document does not pre-empt its verdict. The arithmetic it must not have to re-derive:

> At the substituted `Z0_SERIES_ANCHOR = 47.53662` (`evidence/termination/run_build_A.py:140`) the anchor predicts `T = 0.6553`; at the p51 arm's own `station_fit.z0 = 44.21 + 0.38j` it predicts `0.6388`; the two differ by 2.5 %, and the measured `|s21|` at plane 51 is 0.7628. Z₀ mismatch can therefore account for at most **2.5 of the 16 percentage points** — one contributor, not the explanation.
