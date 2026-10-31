# Pipeline map — stage-by-stage status, gates, and error bars

**Scope.** Every stage between "a job description" and "a quotable S-parameter", mapped
against the code that actually ships in `emfit/`, `tools/`, `schemas/` and `tests/`.
Evidence is grep- and source-derived from the working tree (searches exclude `.scratch/`).
Gate *states* below were read from test source, not from a test run in this pass; the
symbol-import probe in §4 is the only execution performed.

**Cross-reference.** Claim ids (C1…C26), evidence tiers (E1…E5, X, UNKNOWN) and the
ledger row ids (A02, B01, D08, …) refer to [`soundness.md`](soundness.md). Gate clause
ids (`T1_stab` … `T6_fit_route`) refer to [`m3c_gate_v2.md`](m3c_gate_v2.md) §9/§10.2.

---

## 1. Verdict

**4 of 12 stages are gated. 8 are not. 3 are absent.**

| | |
|---|---|
| **Gated (4)** | mode basis (beta vs closed PEC box, `SELF_TEST_BETA_TOL=0.02`); volume solve (FIT energy conservation, `tests/test_energy.py`); job schema (`tools/host/validate-job-schema.py`, exit 0/1/2); extraction to S (`T4_amp` / `T2_agree`) — **the last recorded as FAILING at 44.09 %** against an uncited ±10 % band. |
| **Ungated (8)** | mode profile, modal launch, PML/ABC, station projection, invariants, external cross-check, and the two absent stages below. |
| **Absent (3)** | job loader; absorbing port termination; external solver cross-check. |

Two consequences dominate everything else in this map:

1. **The tier ladder has no rung 2.** E2 (Verified — independent analytic reference,
   order demonstrated across ≥3 resolutions) is **0 of 143 rows**
   (`soundness.md:163`). The distribution is E1 37 / E2 0 / E3 58 / E4 3 / E5 28 /
   X 15 / UNKNOWN 2. Nothing in the pipeline has been demonstrated to converge at the
   right order against an independent reference.
2. **The end of the pipeline is not gated by anything that would stop a wrong number.**
   Extraction — the stage that produces the quotable quantity — is registered as a gate
   (`T4_amp`, `T2_agree`) and that gate is currently **red**: `T4_amp` extracts
   `R = 4.0489791163982565` against an analytic `2.810102138752` (44.09 % high, `Q=1.4409`),
   and five dense rungs plus five fresh meshes hold it at 15.7–44.1 % high, non-monotone.
   `T2_agree` scores 4.52 % against a 0.5 % tolerance (9.03×). A failing gate is a
   stronger statement than a missing one, but it only helps if someone reads it: the
   one live claim about quotability is `C4`, and `C4` is **E5 — asserted, not measured**.

Consequence level is recorded as MODERATE (`soundness.md:16`) with a single auditor and
no inter-rater check (`soundness.md:32-36`).

---

## 2. The twelve stages

Status vocabulary: **WORKING** (code ships, is imported by a live caller, and does the
thing its name says) · **PARTIAL** (code ships but the live path does not use it, or it
answers a strictly narrower question) · **SCHEMA-ONLY** (the artefact exists, nothing
reads it) · **DESIGNED-NOT-BUILT** (specified in prose, no implementation) ·
**DOES-NOT-EXIST** (grep-empty or the module says so itself).

| stage | implements | status | gate | evidence tier | error bar | what would promote it |
|---|---|---|---|---|---|---|
| **job.v1 schema** | `schemas/emfit.job.v1.schema.json` (13.3 kB) + `schemas/examples/microstrip_stub.job.json` (506 B) + `microstrip_stub.job.note.md`; validator `tools/host/validate-job-schema.py` (~470 lines, stdlib only; jsonschema optional cross-check) | SCHEMA-ONLY | **YES** — validator exits 0 valid / 1 invalid or cross-check disagreement / 2 usage; rejects malformed input, closes unknown nodes (`C10`, E1) | E1 (validator logic) / E4 (shipped example agrees with an independent `jsonschema` validator, `C12`) | none needed (decision procedure) | a loader in `emfit/` so the schema gates a run rather than a file; note `C11` (E1): the schema's own example does not reproduce `demo_microstrip_stub` |
| **job loader** | *nothing* — `grep 'schema\|job\.json\|load_job'` over `emfit/*.py` returns exactly one hit, a docstring about a KiCad schematic (`emfit/kicad.py:664`). `grep 'emfit\.job\.v1'` over all `*.py` hits only the validator itself | DOES-NOT-EXIST | no | — | — | any `emfit` entry point that parses a job through the schema; until then the schema is documentation with a test |
| **mode basis** | `emfit/mode2d.py` (2246 lines): `Mesh2D`:200, `assemble`:431, `assemble_mixed`:503, `solve_modes`:906, `solve_modes_mixed`, `candidate_records`:833, `_guarded_choice`:1010, `_select_and_pack`:1048, `Mode2D`:639 (`.beta_imag`, `.is_propagating`, `.e_at`); dense pencil route in `emfit/eigen.py` | WORKING | **YES** — `SELF_TEST_BETA_TOL=0.02` against the analytic closed PEC box, over `eps_r ∈ [1.5, 3.5]` and levels 1–3 (`C1`, E3) | E3 (characterised), plus E1 for the pencil's structural properties (B indefinite, symmetric blocks, `h` SPD, Schur negativity) — but that E1 covers `mode2d.py` + `c1_audit.py` only (`C6`) | vacuum anchor 1.022e-4 at **one** mesh; route spread +0.90 / +0.64 / +0.48 % | refine the vacuum anchor across ≥3 meshes and show the order (the `B13` anchor protocol was **never run**); that is what would make this E2 |
| **mode profile** | `emfit/mode_profile.py` (742 lines): `microstrip_mode_profile`:535, `ModeProfile`:229 (`.node_shape`, `.plane_window`:316, `.iy_strip_centre`, `.strip_nodes`), `PlaneWindow`:178, `SelfConsistencyError`:165, `_require_close`:487 (`_RTOL`), `_modal_power`:520 | PARTIAL | no | E3 — the profile is self-consistent under `_RTOL`, but there is **no analytic mode-shape check**; `C21` (E3) establishes *the same mode at every mesh size* by overlap, which is identity, not correctness | overlap-based, so no external error bar exists | compare `.node_shape` against a closed-form microstrip mode shape (or a mode from an independent solver) and report the deviation across ≥3 resolutions |
| **modal launch** | **two paths.** (a) `emfit/modalport.py` (377 lines): `ModalPort`:128, `from_mode2d`:194-296, `amplitude`:299, `inject`:316, `forward_backward`:335, module `s11`:363 — **`from_mode2d` has zero call sites** repo-wide. (b) `emfit/modal_harness.py`: imports `modal.modal_station_phasors`/`plane_mode`:51, `mode_profile.microstrip_mode_profile`, `ports.travelling_waves`; exposes `build_mode_plane`, `ModalStationCapture`, `station_amplitude`, `split_forward_backward`, `_project`:116 — callers are only `tools/d585_sweep.py:70`, `tools/modal_beta_probe.py:42`, `tools/modal_splitfix.py:37`, `tools/d584_widebox.py:25`, `tests/test_d583_harness.py:23` | PARTIAL | no | E3 | none — no launch is exercised on the live `emfit/studies.py` path, so no error bar attaches | wire one of the two paths into `studies.py` (`grep 'import modal\|modalport\|ModalPort'` in `studies.py` = **0 matches**) and gate the injected amplitude against a known incident wave |
| **volume solve** | `emfit/evolve.py` (326 lines): `FITStepper`:83 (`__init__(cc, m_eps, m_mu, dt, pec, pml, m_sigma)`:122, `step`:186, `energy`:210, `energy_components`:220, `run`:234), `RickerSource`:272, `Leapfrog`:304, `cfl_dt`:68, `ricker`:58; `emfit/maxwell.py` (103 lines) `FITSystem`:30 (construction + `cfl_dt`/`check_dt` only); consumed by `emfit/scatter.py:87` | WORKING | **YES, but only in a closed box** — `tests/test_energy.py` (244 lines): `test_energy_exact_conservation`:111, `test_pec_conservation`:128, `test_cfl_bound_is_sharp`:160, `test_wave_propagates_at_c`:209; `studies._run_cavity`:455 plots drift against exact `f_mnp` | E1/E3 — the conservation result is exact and the CFL bound is sharp (both decision-like), but see the gate column | `test_cfl_bound_is_sharp` pins the timestep; no error bar exists for the stepper *with a PML attached* — and that is the configuration the pipeline actually runs | an energy or impedance-conservation test in the **open** configuration (PML present), which is where `C2`/`C3` place their deflation hypotheses (above `eps_r` 3.5) |
| **PML / ABC** | `emfit/pml.py` (808 lines): `PML`:402 (`thickness_cells=20, order=2, target=1e-4, axes=('x','y')`), `AbsorbedWork`:211 (`record`/`fractions`/`total_work`/`bind_materials`), `multipliers`:662, `sigma_for_walls`:633, `cells_for_wavelength`:774; `emfit/abc.py` `Mur1Boundary` (first-order). Tests: `tests/test_pml.py`, `tests/test_pml_audit.py`, `tests/test_abc.py` | WORKING | **YES** (pytest suite over both absorbers) | E3 | an **adequate** absorber still adds **+0.27 pp** to the beta gap; boundary choice accounts for **0.75 pp of the 0.895 pp** FEM–FDTD gap (`decisions.md` §134, §142-143) — i.e. the absorber is not the residual | show `AbsorbedWork` reflected fraction < target on a case with a known reflection, across ≥3 thicknesses |
| **absorbing port** | *nothing.* `emfit/ports.py:3-13` states it: "The obvious way to terminate a gap port is a series resistor … FITStepper only knows how to pin PEC constraints — there is no resistive edge in the discrete model to divide by … So this module does not terminate anything. Instead it splits the standing [wave]." | DOES-NOT-EXIST | no | — | — | a resistive edge (or an equivalent current source) in `FITStepper`'s PEC-only constraint set; without it, every port number is a **standing-wave decomposition**, not a measurement of a terminated line |
| **station projection** | `emfit/ports.py` (1918 lines): `Probe`:134, `LumpedPort`:180, `DftAccumulator`:564, `BetaFit`:772, `LineFit`:980, **`StationFit`:1290**, `edge_path_voltage`:79, `column_path`:253, `row_path`:314, `plate_current`:395, `station_poynting`:470, `travelling_waves`:681, `reflection`:727, `transmission`:745, `fit_beta`:861, `fit_line`:1058, **`fit_station_impedance`**, `deembed_reflection`, `deembed_transmission`, `power_current_check`, `sigma_beta_from_curvature`, `suggest_probe_spacing`:1267 — **all imported into the live path at `emfit/studies.py:62-77`**; surfaced on `MicrostripWave` (`station_fit`:1606, `station_fit_lossy`:1621, `loss_fit` (a `LineFit`):1619, `s21`/`s21_raw`/`s21_planes`:1609-1611, `gamma_port`, `deembed_distance`, `z0_model`, `eps_eff`, `power_balance`:1623, `station_fit_ok`:1624, `bins`:1626) | WORKING | no — no test asserts a station-fit value against an independent one | E3, with the one-wave fit's **own bias** measured: 1.4618 rad/m = 0.3767 % = 2.278° over the 9.6 mm arm; the FEM–FDTD gap is 0.3838 % = 1.4893 rad/m = 2.321° over `L_box` = 27.2 mm ⇒ **ratio 1.019**, so the comparison cannot resolve anything below its own bias (extrapolated limit 0.443–0.447 %) | an *independent* station reference (analytic `Steinmetz`-style Z0 or a second solver) rather than a second fit of the same fields |
| **extraction to S** | `emfit/studies.py`: `line_s21`:1242, `_wave_amplitude`:1281, `forward_wave_amplitude`:1296, `backward_wave_amplitude`:1353, `BinMetric`:1824-1872 (`beta`, `sigma_beta`, `s11_measured`, `s11_port`, `s21`, `passivity`, `s21_power`, `passivity_power`, `eps_eff`, `residual`, `refusal`), `_bin_metrics`:1888, `_bin_row`:2019, `_dump_bins`:2089, `_broadband_rows`:2192; constants `_BIN_PASSIVITY_SLACK=1e-6`:1820, `_BIN_DRIVE_DB=-20`:1817, `_BIN_SPAN_PHASE_MIN=2π/5`:1813. Second, **unused** path: `emfit/modal.py` `modal_sparams`:685 / `ModalSparams`:596 | PARTIAL | **YES, and it is RED** — `T4_amp` and `T2_agree` are live gate clauses (`m3c_gate_v2.md` §9/§10.2). `T4_amp`: `R = 4.0489791163982565` vs analytic `2.810102138752` = **44.09 % high**, `Q = 1.4409`; five dense rungs + five fresh meshes keep it 15.7–44.1 % high, **non-monotone** (`C19`, E3). `T2_agree` = **4.52 % vs 0.5 % tol = 9.03×** | E3 (measured, fails, and the failure is stable under refinement). The pass-band is *not* the problem: |Γ| = 0.00701664 (−43.08 dB), VSWR 1.01413, ripple ±0.0607 dB, mismatch loss −0.000214 dB | the ±10 % band that `T4_amp` is judged against is **uncited** — `F04` calls it "the standard engineering target" with no source. Citing it (or deriving it) is a prerequisite for reading the 44 % as a verdict rather than a preference |
| **invariants** | `studies.py:2012`: `passivity = s11_measured**2 + s21**2`, `:2014 passivity_power`, flagged at `:2043` ("BUG: passivity exceeds 1, not clamped"), and explicitly **not** averaged across the band (`:2223-2227`). `grep 'reciprocit'` in `emfit/` = **0 hits**. Energy conservation is gated only by the closed-box pytest (§volume solve) | DESIGNED-NOT-BUILT | **NO** — seven invariants I1–I7 are specified and **none tested** (`B01`, E5). `emfit/studies.py:2012` computes one of them per bin and *reports* the violation rather than gating on it | E5 (design) | none — and one recorded figure labelled "passivity" reads **2.0013807961296104** (`B09`) with no provenance | turn I1–I7 into assertions with thresholds and land them in `m3c_gate_v2.md`; note `C7` (E1) already proves the seven invariants are **blind** to a curl-curl sign flip, and that coupling detection is conditional on modal share `s_c` — so the set needs an eighth, not just a test harness |
| **external cross-check** | **solver: nothing.** `grep 'openems'` = **0 matches across 439 `*.py` files and 0 in `docs/`**. **Analytic: substantial and in-tree** — `emfit/mie.py` ("Analytic 2-D Mie scattering by a perfectly conducting circular cylinder (TM_z) … Reference solution, not a solver … It is exact"), the closed PEC box `f_mnp`, and `emfit/microstrip.py` closed-form (Hammerstad–Jensen; `Z0_QS=95.453370 Ω`, `eps_eff_QS=3.049914164`, `u=W/H=0.5`, `t=0`; `Z0=92.698533` at `t=35 µm`) | DOES-NOT-EXIST (solver) / PARTIAL (analytic) | no | E4 for the one analytic comparison that exists: `C23` puts the analytic reference within **0.74 %** of Hammerstad–Jensen — but on **one geometry**, with no internal error analysis (`decisions.md` §144 notes both solvers sit ~+1 % above H–J in the *same* direction, which is a correlated-bias warning, not a confirmation) | the 0.74 % is a single-point agreement, which is exactly the definition of E4 | any second solver, or H–J swept over `W/H` and `eps_r` with the deviation reported as a curve — either one moves this toward E2 |

---

## 3. Hypotheses: confirmed and corrected

Each entry states the prior belief, the verdict, and the evidence that settles it.

- **(i) Station projection is inline-only, with no standalone API.** — **CORRECTED.**
  A standalone API exists and is *used*: `emfit/ports.py` defines `StationFit`:1290,
  `fit_station_impedance` and `fit_line`:1058, and `emfit/studies.py:62-77` imports all of
  them. What is genuinely local is narrower: `fit_one`/`fit_two` (`studies.py:2887-2891` —
  `fit_two.beta` exists but is **not** banked in the ladder JSON) and a nested
  `lossy_station_fit()` (`:2987`). This is exactly ambiguity (a) in §4, and it is what
  made the "inline" reading plausible.
- **(ii) Termination does not exist.** — **CORRECTED.** PML (`emfit/pml.py:402`, 808 lines,
  three test files) and `Mur1Boundary` (`emfit/abc.py`) both exist and are tested. The
  *port* is what is absent, and `emfit/ports.py:3-13` says so in its own words. Naming
  the gap "termination" bundles a working stage with a missing one.
- **(iii) There is no external cross-check.** — **CORRECTED (partly).** True for a second
  *solver*: `openems` is grep-empty over 439 `*.py` files and all of `docs/`. But three
  analytic references are in-tree — `mie.py` (exact), the closed PEC box, and
  Hammerstad–Jensen with a **0.74 %** agreement (`C23`, **E4**). The pipeline is not
  unanchored; it is anchored once, on one geometry.
- **(iv) The volume solve is E1.** — **CORRECTED.** It is gated only by a **closed-box**
  pytest (`tests/test_energy.py`). There is no gate with a PML attached, and the PML
  configuration is what the pipeline runs. The E1 applies to conservation and the CFL
  bound; it does not transfer to the open problem.
- **(v) Extraction is never gated.** — **CORRECTED.** It *is* gated, by `T4_amp` and
  `T2_agree`, and the gate is **recorded as failing** (`R` 44.09 % high, non-monotone over
  five dense rungs and five fresh meshes; `T2_agree` 9.03× tolerance). "Ungated" was the
  wrong word for the most interesting fact in the pipeline.
- **(vi) Modal launch is *the* named gap.** — **CORRECTED.** The code exists **twice** and
  neither copy is wired: `ModalPort.from_mode2d` (`modalport.py:194-296`) has **zero call
  sites**, and `modal_harness` is reachable only from `tools/` and `tests/`
  (`grep 'import modal\|modalport\|ModalPort'` in `studies.py` = **0 matches**). The gap
  is *unwired*, not *unbuilt* — which makes it a much cheaper fix than the prior framing
  implied, and makes "we have no modal launch" an overstatement of the problem.
- **(vii) Finding — `soundness.md` claim `C26` is stale.** `C26` is recorded at **E1** and
  states "`emfit/modal.py` is absent from the repository; the only copy is in
  `.scratch/`". In the shipping tree `emfit/modal.py` is **committed, 935 lines**, with
  `plane_mode`:267, `modal_station_phasors`:372, `modal_line_quantities`:538,
  `modal_sparams`:685, `ModalSparams`:596, `ModalLine`:472, `ResidualGate`:763,
  `residual_gates`:912 — and it is imported at `modal_harness.py:51`,
  `tests/test_d583_harness.py:15`, `tools/host/attribution/attribution.py` and
  `tools/host/phaselag-subsets/phaselag_subsets.py:155`. An E1 claim is contradicted by
  the tree. This is a ledger-vs-code contradiction and should be corrected at the row,
  not silently refreshed.

For the record, the hypotheses that came back **CONFIRMED**: the job schema is
schema-only with no loader (grep: one unrelated hit in `kicad.py:664`; `emfit.job.v1`
appears only in the validator); passivity is computed per bin and *not* gated
(`studies.py:2012`, `:2043`, `:2223-2227`); reciprocity is grep-empty; and the mode basis
is the pipeline's best-tested stage.

---

## 4. Verification performed

One execution, to confirm the corrected symbol names are real and importable rather than
inferred from grep:

```
PYTHONPATH=/workspace python3 -c "import emfit.ports as p; print(p.StationFit, p.fit_station_impedance); \
  import emfit.mode2d as m; print(m.assemble_mixed); from emfit.modalport import ModalPort; print(ModalPort.from_mode2d)"
```

Result — exit 0:

```
StationFit <class 'emfit.ports.StationFit'>
fit_station_impedance <function fit_station_impedance at 0x…>
assemble_mixed <function assemble_mixed at 0x…>
from_mode2d <bound method ModalPort.from_mode2d of <class 'emfit.modalport.ModalPort'>>
```

**No test suite was run.** Every gate state in §2 is read from test *source* — the presence
of an assertion, its threshold, and its constant — not from a green or red run. Where a
gate is called RED (`T4_amp`, `T2_agree`) that reading comes from the recorded result
values, which is what the ledger cites; it should be re-run before being relied on.

---

## 5. What this map cannot see

**(a) Negative claims and how they were established.** Every "does not exist" here is a
grep result, which is only as good as the query. Specifically: `emfit/*.py` searched for
`schema|job\.json|load_job` (1 unrelated hit); all `*.py` for `emfit\.job\.v1` (validator
only); all `*.py` for `from_mode2d` (definition, its own error strings, one `.scratch`
comment); `emfit/studies.py` for `import modal|modalport|ModalPort` (0); `emfit/` for
`reciprocit` (0); 439 `*.py` files and `docs/` for `openems` (0). A negative found this way
is falsifiable by a different spelling — `import_module`, a string-built name, an
entry-point table, or a dynamic `getattr` would each be invisible. None was found, but
none was systematically excluded either.

**(b) Ambiguities — the tree contains two of several things, and the ledger speaks as if
it contains one.**

1. **Two station fits.** `ports.StationFit`:1290 / `fit_station_impedance` / `fit_line`:1058
   (imported, live) versus `studies.py`'s nested `lossy_station_fit()`:2987 and
   `fit_one`/`fit_two`:2887-2891. Which one a quoted number came from is not recorded, and
   `fit_two.beta` is computed but never banked.
2. **Two launch paths.** `ModalPort.from_mode2d` (zero callers) versus `modal_harness`
   (callers only in `tools/` and `tests/`). A reader who greps one will conclude the
   opposite of a reader who greps the other.
3. **Two S-extractions.** `studies.BinMetric`/`_bin_metrics` (live) versus
   `modal.modal_sparams`:685 (implemented, unused). Only the first is exercised; only the
   second has a `passive`:651 property and an `impedance_mismatch`:664 diagnostic.
4. **Two terminations.** PML (`pml.py:402`) and `Mur1Boundary` (`abc.py`). Which one
   produced a given result appears only in `.scratch/pml_sweep.py`, which contrasts "mur"
   vs "pml" — a driver that is not committed.

**(c) Ledger-versus-tree contradictions.** `C26` (E1) asserts `emfit/modal.py` is absent;
it is committed at 935 lines and imported in four places. An E1 row contradicted by a
`grep` is a defect in the ledger, and it means the ledger has not been refreshed against
the current tree. This map should be assumed to have the same failure mode for any stage
not explicitly probed in §4.

**(d) `.scratch`-only drivers make quoted numbers unreproducible.** Several results cited
above — the `mur` vs `pml` contrast, the anchor sweep — live in `.scratch/`, which is
excluded from every search here and is not part of the shippable tree. `C26`'s own text is
evidence that the boundary between "committed" and "scratch" has moved at least once
without the ledger following. Until the quoted numbers have committed drivers, the error
bars in §2 are *reported* figures, not *reproducible* ones.

**(e) The one number that matters most is judged against an uncited band.** `T4_amp`'s
44.09 % is a failure only relative to a ±10 % target that `F04` attributes to "the standard
engineering target" with no citation. If the band is wrong, the gate's meaning changes —
and nothing in the tree adjudicates it. That is a question about the gate, not the code,
and this map can only flag it.
