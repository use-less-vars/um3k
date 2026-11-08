# Upstream Extraction (2026-11-08)

## 1. Question

Why must the s11 extraction plane sit at or upstream of the load, what does the code now
report when it does not, and what reflection magnitude does the upstream data support?
Every number below is already in the tree. This dispatch ran no FDTD, regenerated no
artefact and changed no numerics.

## 2. What the code now reports

`emfit/studies.py`:3706-3711 sets `s11_at_plane_valid = False` and
`s11_at_plane_invalid_reason = "plane_beyond_load"` when `int(ix_extract) > int(ix_load)`
(the comparison is at `:3708-3709`), warns a `RuntimeWarning` naming both columns, and
leaves `gamma_plane` at `nan`. The ratio itself is gated at `:3748`
(`if a_cut != 0.0 and s11_at_plane_valid:`), so one column past the load no number is
formed at all. Both keys are written into the record's `geometry` at `:4028-4029` on every
named plane, true or false, and `ix_load` is resolved from the load's own position at
`:2910`. `evidence/termination/run_build_A.py` surfaces the same decision: its
`s11_at_plane` block carries `valid` and `invalid_reason` (`:1969-1970`) beside the `basis`
string (`:1952`), which says that a plane strictly beyond the load column reports no
reflection and that at the load's own column the ratio is still the element's reflection.

## 3. The load column and the plane index

The record names its own load:
`geometry.loads = [{column: 50, kind: 'series_r', n_edges: 9, value: 50.0, x: 0.02}]`
with `cell_m = 0.0004`, so the element sits on node column 50 at x = 20.0 mm. The nine
station columns are 26, 29, ... 50 (x = 10.4 mm to 20.0 mm), so the outermost station
shares the load's column and the other eight are upstream of the element. That is why the
test is an inequality and not a bound check: column 50 is a legitimate extraction plane,
column 51 is not.

## 4. The plane table

| plane index | `s11_at_plane` magnitude | `gamma_plane` magnitude | `s11` magnitude |
|---|---|---|---|
| 50 (the load's column) | 0.318356 | 0.318356 | 0.325863 |
| 51 | 0.043908 | 0.043908 | 0.325863 |
| 52 | 0.032255 | 0.032255 | 0.325863 |
| 53 | 0.025473 | 0.025473 | 0.325863 |
| 54 | 0.022006 | 0.022006 | 0.325863 |

Each row is its own artefact (`build_A_50ohm_p5N_plane.json`, N = 0..4), each records a
`geometry.s21_plane_index` matching its name, and all five carry the same port numbers:
`s11.magnitude = 0.32586326001662264` and
`s11.magnitude_one_wave_station_fit = 0.3261349242788359`. The port quantity is invariant
under the plane choice; only the plane ratio moves.

## 5. Why downstream planes read low

One column past the load the element is behind the probe. The two travelling waves the
split produces there are the transmitted wave and whatever the far end sends back, so
`b_cut/a_cut` is not a reflection coefficient of the component. The table shows the
collapse at the first column past the load (0.318356 to 0.043908, a factor of 7.3) and then
a slow decay (0.043908, 0.032255, 0.025473, 0.022006) that is numerical junk from beyond
the element. It is the same category error that put `s11_at_plane` = 0.049 beside
`s11` = 0.326 (DR-19); the code now refuses the number instead of quoting it.

## 6. The reflection magnitude upstream

Four readings agree on about 0.32.

| reading | value | source |
|---|---|---|
| field `Z = v/i` | 0.3071 - 0.3575, mean 0.324, spread 0.050 | `direct_vi_forensics_2026-11-08.md`:49 |
| port | `s11.magnitude` = 0.325863 | every `build_A_50ohm*` record |
| one-wave station fit | `s11.magnitude_one_wave_station_fit` = 0.326135 | same records |
| plane ratio on the load's own column | `s11_at_plane` = 0.318356 | `build_A_50ohm_p50_plane.json` |

The station spread is why the field number is a band: `abs(Z)` runs from 24.174 ohm to
85.627 ohm over the nine stations, max/min = 3.542. The load-column plane ratio sits 2.3
percent below the port, which is a normal difference between a split this near the element
and a port quantity, and not the 5.6x understatement the downstream sweep reported.

## 7. Constrained fits and Z0

`evidence/termination/constrained_fit_p51.json` holds five fits on the nine station
phasors of the load-column record. Its name says p51 while its `input` is
`build_A_50ohm_p50_plane.json`; the numbers are the p50 record's.

| fit | constraint | beta rad/m | eps_eff | `abs(Gamma)` |
|---|---|---|---|---|
| F1 | Z0 = 47.305815 ohm, real | 228.254 | 3.4923 | 0.323916 |
| F2 | Z0 = 47.305815 + 1.5582j | 228.233 | 3.4917 | 0.326840 |
| F3 | Z0 real and free (control) | 227.839 | 3.4796 | 0.324563 |
| F4 | Z0 = 47.305815, 3 near stations | 216.091 | 3.1300 | 0.309414 |
| F4b | Z0 = 47.305815, 4 near stations | 220.105 | 3.2474 | 0.309141 |

F3 lands on Z0 = 47.648466 ohm, within 0.7 percent of the TE anchor 47.305815, so the free
fit is not degenerate over the 9.6 mm station span. The residual fixes Z0: minimised over
beta, SSR(Z0) is 8.665e8 at the optimum, 1.153e10 at 40 ohm and 2.772e10 at 60 ohm. Over
beta = 200-260 rad/m at Z0 = 47.305815 the fitted `abs(Gamma)` moves only between 0.323459
and 0.324376, so the magnitude is not a beta artefact.

## 8. The 0.245 and its provenance

The station fit's 0.245 was read as a biased estimate of the load reflection. It is
neither biased nor an estimate of that quantity: it is the same fit with an attenuation
imposed. `ghost_wave_analysis_2026-11-08.md`:158 inverts alpha = 11.255 Np/m from `|s11|`
and `|s21|`, and `voltage_integration_and_reflection_2026-11-08.md`:82-85 tabulates the
fit at that alpha beside the alternatives:

| alpha Np/m | beta rad/m | abs(Gamma) | rel. residual |
|---|---|---|---|
| 11.255 | 232.79891853803187 | 0.245108 | 1.78e-2 |
| 11.255 | 223.35306683909533 | 0.256488 | 2.30e-2 |
| 0 | 232.79891853803187 | 0.325863 | 1.44e-3 |
| 0.4344 | 232.79891853803187 | 0.322297 | 1.25e-3 |

At alpha = 0 the fit returns 0.325863260016623, identical to `/s11/magnitude` =
0.32586326001662264 to fifteen digits (`:106-108`), so s11 and the station fit are the same
estimator. The data prefer about 0.43 Np/m, where the residual is roughly twelve times
smaller and the reflection is 0.322297. Three scripts still bake 0.245 in as a reference:
`read_s21_plane_sweep.py`:34 (`REF_S11 = 0.245108`), `analyze_vi_forensics.py`:36
(`GAMMA_LIST = (0.245, 0.326)`) and `analyze_constrained_fit.py`:70
(`GAMMA_FREE_REFERENCE = 0.245`).

## 9. Cross-family check

The same two keys exist outside the A arm. In every record below the plane ratio stays
within about 20 percent of that record's own s11, and nowhere near the 0.02-0.04 seen
downstream in build A.

| record | plane index | `gamma_plane` | `s11.magnitude` | ratio |
|---|---|---|---|---|
| `build_A_50ohm_cal` | none | 0.339282 | 0.339282 | 1.000 |
| `build_A_50ohm` | none | 0.219615 | 0.219615 | 1.000 |
| `build_B_100ohm_v3c` | 50 | 0.492312 | 0.473884 | 1.039 |
| `build_B_100ohm_v3d` | 50 | 0.426643 | 0.473884 | 0.900 |
| `build_E_50ohm_v3c` | 75 | 0.354909 | 0.296951 | 1.195 |
| `build_E_50ohm_v3d` | 75 | 0.313180 | 0.296951 | 1.055 |

When no plane is named, `gamma_plane` is the record's own s11 and the two agree to six
digits. The B and E rows are different loads, so they check that the plane ratio tracks its
own port number across builds; they do not exercise the load-column test, which no record
in the tree has yet been run through.

## 10. What is not established

- No artefact exercises the new gate. Of the 74 JSON records under
  `evidence/termination/`, 59 carry a `gamma_plane` key, 32 carry an `s11_at_plane` block,
  and none carries `s11_at_plane_valid`. All 32 blocks still have exactly the four keys
  `basis`, `magnitude`, `phase_deg`, `plane_index`, so the keys are live but unbanked.
- No test asserts on the gate. `grep -rn s11_at_plane tests/` returns nothing, and no test
  names `s11_at_plane_valid`. One test does walk the branch without looking at it:
  `tests/test_studies.py`:2126
  (`TestFluxProjectionCurrentReference::test_the_flag_matches_the_plain_path_when_the_projection_is_not_trivial`)
  names a plane on node column 6 while its load sits on column 5, so the gate fires there and
  the suite now carries the `RuntimeWarning`. The code path is executed; nothing is checked.
- The 0.245 correction rests on one record and one load; no second load carries a measured
  `z_eff` with which to check the attenuation chain.
- The two-wave fit prefers beta = 228.25 rad/m while the record's own `line.beta` is
  232.7989 and the de-embedding uses the latter; about 2 percent apart, unresolved here.
- Z0 is not identified: 47.648466 (free fit) and 47.305815 (TE anchor) differ by 0.7
  percent, and the ambient 47.54 quoted elsewhere lies between them.
- The suite is not green, and the figure carried in the earlier rows is not this tree's
  figure. The full suite was re-run after the `>` relaxation on python3 3.12.15 / pytest
  9.2.0, and it reports **four** failures, not two.
  - `tests/test_studies.py::test_s21_plane_may_sit_downstream_of_the_cut_never_upstream`,
    `:1607`, `Failed: DID NOT RAISE ValueError`. The case that stops is `s21_plane="cut"`
    (`:1607-1609`), which is a guard about the CUT, not about the load column; this dispatch
    did not touch it.
  - `tests/test_studies.py::test_gamma_port_and_gamma_plane_are_different_quantities`,
    `:1653`, `assert 0.1520918610341127 == 0.118088 +/- 1.2e-05`.
  - `tests/test_host_ladder_partial.py::test_ladder_error_on_rung_two_keeps_the_rungs_that_finished`
    and `::test_memory_ceiling_abort_keeps_its_partial_payload`, both `KeyError: 'sigma'` at
    `tools/host_ladder.py`:1324. Neither is new and neither is related: `git blame` puts
    `sigma_used_per_rung=[float(r["sigma"]) for r in rows]` in commit `88e7498`
    (2026-10-31), while `tests/test_host_ladder_partial.py` was last touched at `911b38f`,
    older, and its monkeypatched fake row carries no `sigma` key. That test imports
    `tools.host_ladder` only and never `emfit`, so no edit to `emfit/studies.py` can cause or
    cure it.
  - The suite has therefore been red in those two places since 2026-10-31, and the 392 / 2 / 1
    figure in the earlier rows and in the message of `069a4f1` predates that break; it is
    withdrawn here as a statement about this tree.
  - No passed total is quoted for the new run either: pytest wrote no count line (the log ends
    on the four `FAILED` lines), 553 tests collect today, and the 584 progress characters in
    the finished log do not reconcile with 553. Four failures, one skip and one xfail are
    what the run states; its own tally is missing. That is a defect of the reporting, and it
    is recorded rather than papered over.
  - The `>` relaxation changed no outcome: both `test_studies.py` failures carry the same text
    before and after it.

## 11. Consequences and next steps

1. Extract s11 at or upstream of the load and de-embed to the load plane, rather than
   reading a plane downstream; the downstream reading measures nothing of the component.
2. Re-run the station two-wave fit constrained to Z0 = 47.305815 ohm. F1 already does
   exactly that and returns 0.323916.
3. Regenerate one artefact so that `s11_at_plane_valid` is banked, and add a test that a
   plane one column past the load yields `valid = False` with reason `plane_beyond_load`.
   `tests/test_studies.py`:2126 already drives exactly that case, so the test is an
   assertion away rather than a fixture away.
4. Replace the three hard-coded 0.245 references with the alpha-explicit fit or delete
   them; as written they invite the same diagnosis error back in.
