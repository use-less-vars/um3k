# DR-43 S21 extraction: scoping document

**Status.** Scoping only. No code was written, no host run was performed, no solver file was modified to produce this document. Every claim below is either read out of a file at the cited line, or arithmetic over values read out of a file, and is tagged accordingly. No recommendation is made and no branch is selected.

**Labels used.** [READ] = the statement is the content of the cited file:line. [MEASURED] = a number produced by a banked run or artifact and quoted from a repository file. [ARITHMETIC] = derived by me from numbered inputs, shown. [INFERRED] = my argument over [READ] facts, with the premises named. [OPEN] = unknown from the files I opened.

**Why this document exists.** The operator pointed at `emfit/studies.py:4146` as the siting of the S21 extraction plane. That line is not that. A scoping pass was requested to establish, from the files, (a) where the extraction plane is actually placed, (b) why the plane-adjacent `s11_at_plane` is null in loaded artefacts, and (c) what stands between the current default behaviour and a defensible S21 on the load side. This document records the answer to those three questions and the questions it raised that I could not close from the files.

## 1. The answer in one paragraph

The S21 extraction plane is not chosen anywhere in `emfit/studies.py`. It is chosen in the driver, `evidence/termination/run_build_A.py:1829-1830`, which defaults it to one column downstream of the load (`ix_load + 1`). The library accepts that column — it refuses only planes *upstream* of the load (`emfit/studies.py:3219-3229`) — and then invalidates it by name further down: `emfit/studies.py:4059-4076` sets `s11_at_plane_valid = False`, `s11_at_plane_invalid_reason = "plane_beyond_load"` and leaves `gamma_plane` at the `nan` seeded at `:4029`, because `:4101-4103` computes it only `if a_cut != 0.0 and s11_at_plane_valid` [READ]. The published `|S21|` is unaffected by that invalidation — it is an amplitude ratio on the same plane, and the de-embedding step is phase-only — but the *reflection* on that plane is not a reflection coefficient at all, because one column past the load the "backward" wave is the far end's return, not the element's reflection [READ at `:4059-4076`]. The blocker for actually repairing extraction is not the plane index: it is that **a loaded run today carries no reference run at all** unless `--with-twin` is passed, so there is nothing in the default path to normalise away the far-end contribution (`run_build_A.py:9-11`, `:39-45`, `:1882-1919`) [READ], and the only test that touches this behaviour currently *pins* the `nan` (`tests/test_studies.py:1577-1635`) [READ].

## 2. The pointer at `studies.py:4146` is not the plane placement

`emfit/studies.py` is 6288 lines. Line 4146 sits inside the DR-43 station-span fallback comment block at `emfit/studies.py:4137-4153`, and its text is

> `1.021737 on a span whose cut plane gives 0.761705, i.e. a passivity`

[READ]. That is a comment about the *station-span* estimator and the passivity failure it produced; it is a symptom of DR-43, not the siting of the plane.

The plane placement is a driver default:

```
col = (int(args.s21_plane_col) if args.s21_plane_col is not None else ix_load + 1)
```

at `evidence/termination/run_build_A.py:1829-1830`, with the load index itself resolved at `:1815-1819` as `ix_load = int(floor(position / cell + 0.5))`, and the same policy restated in help text at `run_build_A.py:3062-3064` ("Absent (the default): the default policy, load column + 1") [READ].

A second citation in the driver is also stale: the upstream-refusal error message points at `emfit/studies.py:2979`, but `:2979` is geometry coercion (`n_sub, n_air, n_strip = ...`), not the refusal test [READ]. The refusal test lives at `emfit/studies.py:3219-3229`.

## 3. What the library does with the plane index it is given

1. `emfit/studies.py:3195-3224`: `s21_plane=None` by default; the string `"cut"` resolves `ix_extract = cut_index = loads_used[0]["column"]` (`:3194`, `:3216`); an integer resolves `ix_extract = int(s21_plane)` (`:3218`) [READ].
2. The only refusal is directional: `ix_extract < cut_index` raises, with the words "UPSTREAM ... never one upstream" (`:3219-3229`) [READ].
3. Therefore `ix_load + 1` — the driver default — **is accepted by the library** [READ]. The library and the driver disagree about nothing here; the library simply marks the result invalid later.

## 4. Why `s11_at_plane` is null in the artifact

The chain, all [READ]:

1. `emfit/studies.py:4029` seeds `gamma_plane = complex(np.nan, np.nan)`.
2. `:4049-4058` carries the block's own rationale, including "it is what put s11_at_plane = 0.049 into a record beside s11 = 0.326 (DR-19)".
3. `:4059-4076` computes `s11_at_plane_valid = True` then, when `ix_load is not None and ix_extract is not None and int(ix_extract) > int(ix_load)`, sets `s11_at_plane_valid = False` and `s11_at_plane_invalid_reason = "plane_beyond_load"`, and emits a `RuntimeWarning` naming both node columns. The warning states the physical reason directly: "One column past the load the element is behind the probe, so the two travelling waves are the transmitted wave and what the far end returns -- neither is the element's reflection, and b_cut/a_cut there is not a reflection coefficient, so gamma_plane is left nan.  The S21 measured on this plane, and every s11 quantity referred to the port, are unaffected."
4. `:4101-4103` computes `gamma_plane = complex(b_cut)/complex(a_cut)` only `if a_cut != 0.0 and s11_at_plane_valid`. On the default policy that guard is false, so the `nan` from `:4029` stands.
5. The writer copies it through: `run_build_A.py:3610` `s11_at_plane = complex(res.gamma_plane)`; `:3872-3874` converts magnitude and phase via `finite_or_none` (defined `:186-194`, "None for a non-finite number"); `:3893-3894` copies `valid` / `invalid_reason` out of `res.geometry`.

Net effect: the artifact shows `s11_at_plane.magnitude = null`, `valid = false`, `invalid_reason = "plane_beyond_load"` — which is exactly what the code intends, not a defect in the writer.

The trace, as a table of hand-offs (each cell a [READ] file:line):

| step | where | what it decides |
| --- | --- | --- |
| CLI flag | `run_build_A.py:3062-3064` | `--s21-plane-col`; absent means the default policy |
| plane index | `run_build_A.py:1829-1830` | `ix_load + 1` when the flag is absent |
| load index | `run_build_A.py:1815-1819` | `ix_load = int(floor(position / cell + 0.5))` |
| library intake | `studies.py:3195-3224` | `"cut"` -> `loads_used[0]["column"]`; int -> `int(s21_plane)` |
| library refusal | `studies.py:3219-3229` | only `ix_extract < cut_index`; downstream passes |
| seed | `studies.py:4029` | `gamma_plane = complex(np.nan, np.nan)` |
| validity | `studies.py:4059-4076` | `plane_beyond_load` when `ix_extract > ix_load` |
| computation | `studies.py:4101-4103` | guarded by `a_cut != 0.0 and s11_at_plane_valid` |
| provenance | `studies.py:4109-4120` | the cut branch is the only writer of `cut_plane@...`; fallbacks write nulls (per `defect_register.md:824-866`) |
| artifact field | `run_build_A.py:3610`, `:3872-3874`, `:3893-3894` | `complex(res.gamma_plane)`; `finite_or_none`; copied `valid` / `invalid_reason` |

The `b_cut`/`a_cut` pair are a single-plane V/I split, not a travelling-wave decomposition; `forward_wave_amplitude` (`emfit/studies.py:1318-1334`) defines v(x) = A e^-gx + B e^+gx and i(x) = (A e^-gx - B e^+gx)/zc so that A e^-gx = (v + zc i)/2, and the docstring there names both components [READ]. Splitting at one plane cannot separate the far end's return from the element's reflection.

## 5. Why the `nan` cannot be repaired on the phase side

`line_s21` (`emfit/studies.py:1264-1278`) hands the ratio to `emfit.ports.deembed_transmission`, which removes a factor `exp(-1j beta d)`; the docstring records that "With a real beta the factor has unit modulus, so the de-embedding cannot change the magnitude: this is a pure amplitude ratio, and the phase it removes is only a reference." [READ]. A phase-only correction therefore cannot turn a `nan` into a number, and cannot change a published `|S21|` at all.

`LineReference.forward_ratio` (`emfit/studies.py:1812-1826`) does the span rescaling: `a+(x2)/a+(x1)`, with the residual rescaled as `ratio ** (run_span / station_span)` [READ]. That path requires a `LineReference`, which is the subject of §6.

## 6. The real blocker for a repaired extraction: no reference run in the default path

- `run_build_A.py:9-11` (module docstring): "is deliberately **no reference run** -- unless `--with-twin` is passed, which supplies one from a load-free twin of the same mesh (off by default)" [READ].
- `:39-45`: the twin is ONE extra FDTD run with the load removed, producing an `emfit.studies.LineReference` via `LineReference.from_wave(twin)` [READ].
- `:1882-1919`: `twin_kwargs_from(kwargs)` drops `loads` and `load_netlist` and sets `s21_plane=None`, `reference=None` [READ]; `:2001-2002` restates this in a comment; `:2452-2468` (`reference_block`) writes `run.twin` into the loaded artifact [READ].
- In the library, when `reference is None` the split is local: `emfit/studies.py:4089-4094` sets `gamma_split = 0j`, `zc_split = zc`, i.e. no propagation at all [READ].

[INFERRED] from the five readings above: a loaded run produced today, without `--with-twin`, contains no reference wave. The far-end contribution that makes `b_cut/a_cut` "not a reflection coefficient" (`:4059-4076`) is precisely what a reference run would let one subtract or normalise. So moving the plane, widening the tolerance, or accepting the invalidated ratio would each change the *number* without addressing the *reason the number is not a reflection coefficient*. That is the blocker, and it is a run-configuration blocker, not a plane-index blocker.

## 7. Grading machinery that already exists

These are the instruments a future change would have to satisfy; none of them is being changed here.

- **Passivity gate.** `run_build_A.py:2148` `PASSIVITY_TOL = 4.0e-9`; `:2154` `PASSIVITY_NOT_ASSESSABLE = "NOT_ASSESSABLE"`; `:2160` `passivity_guard(s11_mag, s21_mag)` returns status `"FAIL_PASSIVITY"` when the sum exceeds `1 + PASSIVITY_TOL`, with a basis string saying the tolerance is "the float64 sum's own roundoff plus the 9-decimal ... not a physical allowance" [READ].
- **The decision chain.** `run_build_A.py:2216-2314`: `s21_measurement` → `published_s21_magnitude` (`:2251` `if not decision["measured"]: return None`) → `passivity_record` (`:2256`, returns `NOT_ASSESSABLE` with null `power_sum`) → `published_s21_block` [READ].
- **Writer-side tests.** `tests/test_writer_station_phasors.py:289` `test_a_station_span_ratio_is_never_published_as_s21`; `:300` `test_an_unmeasured_s21_makes_passivity_not_assessable_not_ok`; the file holds 13 tests, all passing; the revert-detectors are enumerated in the register entry's "What closes it" (g) [READ].
- **Grade.** `evidence/termination/grade_2b.py:136-138` requires `s21.magnitude`, `s21.phase_rad`, `s21.raw_phase_rad`; `:180-194` treats a null `s21` as a warning only when `s21.measured` is `False`, else a problem; `:201` requires `s21.planes_m` [READ].
- **Independent referee.** `docs/design/EM_SOLVER_LEDGER.md:37` (E12): `evidence/referee/s11_extraction.json` gives |S11| = 0.3271645531273824, angle -38.000423 deg, f_ref 5827786408.327286 Hz, declared 50 ohm; in-house 0.3255648664110912 differs by +0.4914 percent; the bias floor |gamma0| is 5.363610948678204e-4 (the 5.4e-4 MSLPort floor), so the disagreement is 2.98x floor. The same row states "S21 is out of scope, explicitly: port 2 is a lumped load to ground" [MEASURED + READ].

[ARITHMETIC] 0.3271645531273824 / 0.3255648664110912 = 1.004914…, consistent with the "+0.4914 percent" in the same row; 0.4914 % against a 0.1648 % floor (5.363610948678204e-4 / 0.3255648664110912) is the 2.98x quoted. This gives no target for S21, only a demonstration that the referee artifact deliberately does not carry one.

## 8. What the record says about the load-adjacent measurement

- `docs/design/EM_SOLVER_LEDGER.md:27` (E2, marked UNVERIFIED) records plane 51: |S11| = 0.32586326001662264, |S21| = 0.7617054231929281, and power sums 0.6863820159501787 (2400 steps), 0.6896931129625421 (4800), 0.6884889931044529 (9600) [MEASURED]. The load-adjacent triple 1.344803 appears in no banked artifact [READ].
- The same row carries the TE answer that the load-adjacent passivity failure is a near-field artefact — the scalar V/I split includes evanescent components — and that plane 51 is the well-posed measurement [READ].

[ARITHMETIC] 0.32586326001662264² + 0.7617054231929281² = 0.106187 + 0.580195 = 0.686382…, matching the quoted 0.6863820159501787 to the digits shown; the step-to-step spread across 2400/4800/9600 is 0.686382 → 0.689693 → 0.688489, i.e. ~3.3e-3, four orders wider than `PASSIVITY_TOL = 4.0e-9`. That spread is a convergence observation, not a tolerance argument, and I am not using it as one.

## 9. Consumers that would see any change

Any change to the S21 number or its provenance reaches these readers:

- `server/poc_app.py:770` — comment: "stores one geometry.f_hz, one s11.magnitude, one s21.magnitude" [READ]; `:1224-1234` builds a point requiring both and skips the point when either is `None` [READ]; `:1356-1380` the same from a stored record [READ]; `:1608-1653` plots the s11/s21 series [READ]; `:2706-2721` writes CSV rows `[point["f_ghz"], s11, s21]` [READ]; `:2171-2185` extracts `s21_magnitude` [READ].
- `evidence/termination/grade_2b.py` — §7 above [READ].
- `docs/design/TE_query_s2p_convolution.md:9` ("a device known only by its two-port S-parameters"), `:26` ("(iii) the existing |S11|^2 + |S21|^2 gate (§7) can grade the result"), `:71` (the `s21_provenance` description), `:165-199` (power_sum and the three estimators) [READ].
- The register itself: `docs/design/defect_register.md:824-866` records DR-43 as FIXED-TESTED for the *publication* defect — the cut branch at `emfit/studies.py:4109-4120` is the only branch that writes a `cut_plane@...` `s21_provenance`, the fallbacks write nulls, `PASSIVITY_TOL` stays 4.0e-9, and the measured contrast is 1.021737 (station-span) against 0.761705 (cut plane) [READ]. DR-19's heading at `:302` reads "the graded `s11` and the load-plane `s11_at_plane` describe incompatible reflections in the same artefact" [READ].

`SPAN_S21_UNMEASURED` is the constant that carries the unmeasured state, `emfit/studies.py:129-135` [READ].

### 9.1 The two estimators, and the contrast between them

Two numbers exist for the same loaded run and they are not the same quantity: the station-span ratio `1.021737` and the cut-plane ratio `0.761705` (both as recorded at `defect_register.md:824-866`) [MEASURED]. The station-span number is the one that fails the passivity gate; the artefact carries the cut-plane number because the cut branch is the only branch that writes a `s21_provenance` [READ].

[ARITHMETIC] 0.761705 / 1.021737 ≈ 0.745, i.e. the station-span estimator reads roughly a third higher than the cut-plane estimator on the same run. I record the ratio only because the two numbers are otherwise easy to misread as one number measured twice; I do not use it to argue for either estimator.

`run_build_A.py:2148` fixes `PASSIVITY_TOL = 4.0e-9` and `:2160`'s basis string says that is "the float64 sum's own roundoff plus the 9-decimal ... not a physical allowance" [READ]. Against that tolerance the cut-plane pair is comfortable (§8's arithmetic) and the station-span pair is not.

## 10. The single test that gates any change here

`tests/test_studies.py:1577`

```
def test_s21_plane_may_sit_downstream_of_the_cut_never_upstream():
```

with its body at `:1586-1635` [READ]. It builds `Load(2.6e-3, "series_r", 50.0)` through the cheap strip kwargs, establishes that the load quantises to column 6, asserts that `"cut"` and `6` both give `s21_plane_index == 6`, and then, for downstream planes `(7, 12)`, asserts the *current* behaviour: `pytest.warns(RuntimeWarning)`, `s11_at_plane_valid is False`, `invalid_reason == "plane_beyond_load"`, `math.isnan(gamma_plane.real)`, plus message substrings.

This is the gating test because it is the only test that asserts what happens on a downstream plane, and it asserts the negative outcome. Any future extraction that produces a number there must **replace** this expectation; it cannot be added alongside it. Adjacent, `tests/test_studies.py:1532` (`test_load_station_is_excluded_from_the_fit`) pins the fit's station set and would be the second thing to move if station selection changed [READ].

## 11. What this document does not say

- It does not say the current `|S21| = 0.761705` is wrong. §8 records it as UNVERIFIED in the ledger, which is not the same as wrong.
- It does not say the plane should move. §2 says only that the driver, not the library, places it.
- It does not say `--with-twin` is the answer. §6 says a reference run is what the invalidation reason refers to; whether the twin is sufficient, sufficient-after-change, or too costly is not established here.
- It does not assess `docs/design/d43b_extraction_audit.md` or `docs/design/d43b_acceptance.md`. Both files exist in `docs/design/`; neither was opened for this document, so nothing in them is cited or contradicted here [OPEN].

## 12. Files opened for this document

`emfit/studies.py`; `emfit/board.py`; `evidence/termination/run_build_A.py`; `evidence/termination/grade_2b.py`; `tests/test_studies.py`; `tests/test_writer_station_phasors.py`; `server/poc_app.py`; `docs/design/EM_SOLVER_LEDGER.md`; `docs/design/defect_register.md`; `docs/design/TE_query_s2p_convolution.md`; `docs/design/absorbing_termination_scope.md` (for the house scoping-document form only). Not opened, therefore not cited: `docs/design/d43b_extraction_audit.md`, `docs/design/d43b_acceptance.md`. No file outside this document was modified, and no command that runs the solver or the test suite was issued for it.

## OPEN QUESTIONS

1. **Reference run.** Is a load-free twin of the same mesh sufficient to normalise away the far-end contribution that `emfit/studies.py:4059-4076` names, or does the split itself have to change? The files establish what the reason says; they do not establish what removes it [OPEN].
2. **Cost.** `run_build_A.py:39-45` prices the twin as one extra FDTD run. Whether that is acceptable for the banked termination set, and whether existing artifacts could be re-derived without re-running, is not in the files I opened [OPEN].
3. **Test replacement.** Replacing `tests/test_studies.py:1577-1635` removes the only guard on the upstream/downstream distinction. Whether that distinction survives in another form is a design question this document does not answer [OPEN].
4. **Provenance.** If extraction moves off `"cut"`, `emfit/studies.py:4109-4120` is (per the register) the only branch writing a `cut_plane@...` `s21_provenance`. What a new branch would write, and whether `grade_2b.py:201`'s `s21.planes_m` requirement is satisfied by it, is [OPEN].
5. **The stale citations.** The driver's error message cites `emfit/studies.py:2979` for a refusal that lives at `:3219-3229` [READ]. Whether that message is user-visible in banked logs is [OPEN].
6. **`short` termination.** `emfit/board.py:74-103` defines `Load(position, kind, value)` over `LOAD_KINDS`, with `series_r` in ohms and `shunt_c` in farads, and `value = float("inf")` giving a bare open cut (`:92`) [READ]. No `"short"` kind appears in the kinds I read; whether a short is expressible without a code change is [OPEN].
7. **Whether `S21` is in scope at all for this bench.** `EM_SOLVER_LEDGER.md:37` explicitly excludes it for the referee artifact ("port 2 is a lumped load to ground") [READ]. Whether the termination set needs a graded S21, or only needs `s11_at_plane` to stop being null, is not answered in the files opened here [OPEN].
