# 57c — `Q` diagnosis: close-out

**Dispatch:** 57c. **Companion, frozen first:** `docs/design/57c_acceptance.md`, committed at `0bca5f6`, 116 lines, sha256 `7c3c4ef9024c71c752b79e7c4699cfa1b94707eadf091af5aeae5f6e0270ecfd`.
**Discipline:** this document does not restate the acceptance criteria as evidence (§0 R5). Every claim carries a provenance tag (§0 R3) and is located by symbol, not by line number (§0 R2).
**Verdict, one line:** **A** — but not in the shape the dispatch expected. The ruler is exact. What fails is the bed the ruler is laid against, and the arithmetic that connects the two gates. The bar cannot be satisfied by the operand the control gate insists on, so `T4_amp: FAIL` was decided before any rung ran.

## (a) `Q`'s definition, T1.1–T1.7

### T1.1 — the expression, its numerator, its denominator

`[ARTIFACT] tools/host/sparse-probe/high_res_run.py::rule_block`

```python
    last_rr, last = meas[-1]
    Q = last["R_extracted"] / R_ANALYTIC
```

```python
    inside = BAND_LO <= last["R_extracted"] <= BAND_HI
    L.append("     R_extracted %s the band [%.14g, %.14g]" %
             ("is INSIDE" if inside else "is OUTSIDE", BAND_LO, BAND_HI))
    L.append("     T4_amp: %s" % ("PASS" if inside else "FAIL"))
    if not inside:
        L.append("     Over the band by %.4fx the half-width (%.4f %% relative error against a 10 %% allowance)."
                 % (abs(Q - 1.0) / Q_BAND, 100.0 * abs(Q - 1.0)))
```

Three properties of this code that matter later:

1. `Q` is computed **once**, on `meas[-1]`, the last completed rung. There is no per-rung `Q` in the code. "`Q` at rung *k*" is a reconstruction — `R_extracted[rung k] / R_ANALYTIC` — that a tabulator performs by hand. Every "`Q` at rung *k*" in this document is that reconstruction, and is tagged accordingly.
2. `Q` appears in the executed path **only** inside the `if not inside:` branch, as a formatting argument. The deciding test is the comparison on `R_extracted`. This is not a defect: `BAND_LO/HI` are algebraically `R_ANALYTIC·(1 ∓ Q_BAND)`, so the two forms are the same predicate. It does mean that the expression which "computes `Q`" is a formatter, and the expression which decides is a comparison on the numerator.
3. The verdict is on `R_extracted`, not on `Q`; `Q` is display.

**Numerator.** `[ARTIFACT] tools/host/c1-audit/c1_audit.py`

```python
    energies.append((float(np.sum(e_y ** 2)), float(np.sum(e_z_vv ** 2))))
```

```python
R_by_col = (np.array([ez / ey for (ey, ez) in energies], dtype=float)
            if rows else np.zeros(0, dtype=float))
banked_col = int(rows[banked_idx][0]) if banked_idx >= 0 else -1
R_extracted = float(R_by_col[banked_idx]) if banked_idx >= 0 else float("nan")
```

So `R_extracted = sum(e_z_vv²) / sum(e_y²)` over the **solver's** field, and `Q`'s numerator is `sum(e_z_vv²)`.

**Denominator.** `Q`'s denominator is `R_ANALYTIC`, and in the code it is a literal.

`[ARTIFACT] tools/host/sparse-probe/high_res_run.py`

```python
# ---------------------------------------------------------------------------
# registered constants.  NONE of these may be edited after a rung has been run:
# the bar and the analytic reference were fixed before any refined-mesh number
# existed (decisions.md, "bar first, number second, verdict third").
# ---------------------------------------------------------------------------
R_ANALYTIC = 2.8101021387524523
R_REGISTERED = 4.0489791163982565      # rung-0 / banked operand; the control
Q_BAND = 0.10                          # |Q - 1| <= 0.10, locked
BAND_LO = R_ANALYTIC * (1.0 - Q_BAND)  # 2.52909192487721
BAND_HI = R_ANALYTIC * (1.0 + Q_BAND)  # 3.09111235262770
CONTROL_RTOL = 1e-6                     # rung-0 gate: |R - R_REGISTERED| / R <= this
```

Its stated origin, `[ARTIFACT] docs/design/t4_amp_ratio.md`:

> `Q = R_extracted / R_analytic`, scored as the inequality `|Q − 1| <= tol_rel`, with both operands read from the banks: `R_analytic = 2.810102138752` (§1, `sum(A_ez^2)/sum(A_ey^2)`, one number because the two arrays are array-identical across the captures) and `R_extracted = 4.0489791163982565` from the **PMC leg, column 738**, whose `ok` is `True` and whose capture's `bank_col` is 738.

> `Q` is dimensionless and both operands scale together with drive level, meshing bookkeeping and normalisation, so a relative band is scale-free and survives being carried to a re-meshed or re-scaled run, whereas ±0.2 absolute is a statement about `R_analytic = 2.810102138752` — a number set by a 201×76 vertical over a 200×77 in-plane cell count —

No code in the repository computes `R_ANALYTIC` from a profile. Every occurrence is the literal or an alias of it: `high_res_run.py`, `routeC_mesh_probe.py`, and `high_res_sweep.py::R_ANALYTIC = mp.R_ANALYTIC`. Exhaustive over `tools/host/**` `[ARTIFACT]`. Verdict on that search: **LITERAL ONLY**.

### T1.2 — every argument `Q` consumes, named at the call site, with its producer

| argument | producer | terminates in |
|---|---|---|
| `last["R_extracted"]` | `c1_audit.py::R_extracted = float(R_by_col[banked_idx])` | a field read from a solve |
| `banked_idx` | `c1_audit.py` column-selection block: `_hits = [i for i, r in enumerate(rows) if float(r[1]) == _sel_bsq]` with `_sel_bsq = float(mode.beta_sq)` | a field read from a solve (the pencil eigenvalue) |
| `R_ANALYTIC` | module literal in `high_res_run.py`, `2.8101021387524523` | a literal constant |
| `Q_BAND` | module literal `0.10` | a literal constant |
| `BAND_LO`, `BAND_HI` | `R_ANALYTIC * (1.0 ∓ Q_BAND)` | a literal constant |
| `CONTROL_RTOL` | module literal `1e-6` | a literal constant |
| `R_REGISTERED` | module literal `4.0489791163982565` | a literal constant |
| `meas` (which rung is scored) | `[(e["rung"]["rung"], e["data"]) for e in results if e["data"]]` | the set of rungs that produced a capture this pass |

### T1.3 — transitive dependency list, one row per edge

1. `e_y` ← `MODE.e_at(_ey_pts).reshape(NYN - 1, NZN, 2)[:, :, 0] * CELL` ← `MODE`, the `Mode2D` carrier of the solved eigenvector. **Terminal: field from a solve.**
2. `e_z_vv` ← `MODE.e_at(_ezc_pts).reshape(NYN, NZN - 1, 2)[:, :, 1] * CELL`. **Terminal: field from a solve.**
3. `_ey_pts`, `_ezc_pts` ← `np.meshgrid` over `yn_node`/`zn_node`/`yc_mid`/`zc_mid` ← `NY, NZ, CELL = G["ny"], G["nz"], G["cell"]` ← the run's mesh descriptor. **Terminal: field from a solve (the run configuration).**
4. `R_extracted` ← `R_by_col[banked_idx]` ← `energies` ← rows 1–2. **Terminal: rows 1–2.**
5. `banked_idx` ← `_hits` ← `float(r[1]) == float(mode.beta_sq)` ← `mode.beta_sq`, the generalised eigenvalue λ of the pencil (`beta = sqrt(beta_sq)`, `eps_eff = beta_sq/(k0·k0)`). **Terminal: field from a solve.**
6. `R_ANALYTIC` ← the literal. **Terminal: literal constant.**
7. `A_ey`, `A_ez` (behind that literal) ← `M.plane_mode(prof, nyn=NYN, nzn=NZN, …)` on `NY, NZ, CELL = 200, 76, 1e-4` taken from `.scratch/tol/logs/TOLFLUX.json`, guarded by `_want_ez=(NYN, NZN-1)` / `_want_ey=(NYN-1, NZN)`. **Terminal: literal constant — the value is frozen; the call is not made on the `Q` path.**
8. `Q` ← row 4 ÷ row 6. **Terminal: rows 1–7.**

Every branch terminates in exactly one of the three permitted kinds. There is no undocumented edge. Note the asymmetry that becomes the whole finding: **row 4's lattice changes at every rung; row 6's does not.**

### T1.4 — the break point

There is no break inside `Q`'s arithmetic. `R_extracted` is one float64 division of two float64 sums; `R_ANALYTIC` is a frozen literal; `Q` is their quotient. The chain breaks in two places, both **outside** the quotient.

**Break 1 — the reference is frozen at one lattice while the operand moves.** `R_ANALYTIC` is a property of a discretisation: `t4_amp_ratio.md` describes it as "a number set by a 201×76 vertical over a 200×77 in-plane cell count". Row 7 shows that lattice is the TOLFLUX reference lattice; row 3 shows the ladder's lattice is `G["ny"], G["nz"], G["cell"]`, which is not that lattice and changes rung to rung (1444 → 9604 free edges). The ratio the ladder measures and the ratio the bar encodes are therefore computed on different lattices. Whether that matters depends on whether `sum(A_ez²)/sum(A_ey²)` is lattice-converged, which this dispatch did not test. **Residual `[INFERRED]` risk attached to the bar.** It does not rescue the bar and it does not account for 27 % by itself.

**Break 2 — the operand the project treats as known-good is a documented artefact of the pre-fix code.** `[ARTIFACT] c1_audit.py`, the comment block immediately above `ANCHOR_R_EXTRACTED = 4.0489791163982565`:

> … Gated only where that identity holds -- the resolved banked column has to BE the cached identified column (see the step-5 resolution); on any other mesh there is no anchor and the measured ratio is reported, not gated. The PEC box is such a mesh: its solver-selected column is 699, ratio 4.163656524825077.
> HISTORY, recorded rather than dropped: before the step-5 fix, `R_extracted` was formed from loop-scoped arrays, i.e. from the LAST SCANNED propagating column. On the PMC mesh that column happens to be the identified column, so 4.0489791163982565 is also what the defective code wrote. On the PEC box it wrote 70.63501855512833 -- column 704's ratio (the failing witness, second of the two propagating columns) -- while the mode the solver actually selects is column 699, whose ratio is 4.163656524825077. 70.63501855512833 is therefore a wrong-column artefact and must never be quoted as a measurement

Two consequences, and they are the crux of this close-out:

(i) The project's one "known-good" number is known-good because, on that mesh, the pre-fix code's last-scanned column happened to coincide with the identified column. Its correctness is an accident of column ordering, not a validation.

(ii) On the actual rung-0 capture the coincidence no longer holds. The solver resolves **column 732**; the cache identifies **738**; the run is accepted at 7.866e-13 relative anyway. The harness prints the mismatch itself and rules it out of scope:

`[ARTIFACT] high_res_run.py::rule_block`

```python
        L.append("     rung 0 columns, DIAGNOSTIC ONLY and not part of the gate: identified_col %d,"
                 % ctrl["identified_col"])
        L.append("       chosen_col %d, bank_col %d, eligible %s.  A QZ column index is this"
                 % (ctrl["chosen_col"], ctrl["bank_col"], ctrl["eligible_cols"]))
        L.append("       run's ordering on this machine: on this identical mesh the solver picks 732")
        L.append("       while the banked cache holds 738, for the same mode, with R agreeing to")
        L.append("       8e-13.  So it is never a mode identifier and never a gate.")
```

The control therefore compares a freshly resolved column against a value the defective code produced from a *different* column index. The two agree because the mode is near-degenerate there. That is a coincidence check, not a correctness check.

### T1.5 — denominator failure modes

- **Can it be zero?** No. `R_ANALYTIC` is the literal `2.8101021387524523`. It cannot be zero, cannot change sign, and is never recomputed at run time. Division safety is not a risk here.
- **Is it a function of something unvalidated?** At run time it is a function of nothing, which is the problem. It is a *provenance* problem, not an arithmetic one: the value was computed once by hand from `M.plane_mode`, and no test in the suite recomputes it.
- **Dimension.** `R` is an energy ratio and dimensionless; `Q` is dimensionless. The ratio is meaningful as a ratio. `Q` carries no absolute meaning and the relative band is the right shape.
- **The failure mode actually present** is not the denominator but the *pair* `BAND_LO/HI` and `R_REGISTERED`: the band derived from the denominator is arithmetically incompatible with the value the control gate demands. Shown in §(f); it is the decisive argument.

### T1.6 — disposition of the station-fit lead

**NOT ON PATH.** Deciding artifacts in §(d).

### T1.7 — `Q` defined per rung

`Q`'s *definition* is identical at every rung: the same literal `R_ANALYTIC`, the same `Q_BAND`, the same `CONTROL_RTOL`, the same column-selection rule. What changes rung to rung is everything on the numerator's side `[MEASURED]`:

| rung | free edges | chosen column | `beta_sq` | `R_extracted` |
|---|---|---|---|---|
| 0 | 1444 | 732 | 97833.057851 | 4.0489791163950715 |
| 1 | 2404 | 1224 | 97328.308109 | 3.7803319900157453 |
| 2 | 3604 | 1826 | 97049.125606 | 3.5673083405263886 |
| 3 | 5044 | 2561 | 96873.888680 | 3.6127170292894397 |
| 4 | 9604 | 5133 | 96752.519701 | 3.5754127531951991 |

The honest statement is therefore: `Q` is defined like-for-like across the ladder, and it is applied across lattices that its own denominator does not track. That is a T1.7 finding, not a T1.7 failure.

## (b) The dependency chain, and where it breaks

`Q` is a quotient of two numbers that arrive by two independent routes. Neither route is long, and the break is not where the brief put it.

**Route 1 -- the reference (denominator).**

profile -> `M.plane_mode(prof, nyn=201, nzn=77, ...)` -> `A_ey (200, 77)`, `A_ez (201, 76)` -> `S_ey = sum(A_ey**2)`, `S_ez = sum(A_ez**2)` -> `R_ANALYTIC = S_ez / S_ey`.

This route terminates in a registered literal. `R_ANALYTIC = 2.8101021387524523` is written by hand in `high_res_run.py`; no code on `Q`'s path recomputes it from a profile. `[ARTIFACT]` Three occurrences exist in the tree -- `high_res_run.py`, `routeC_mesh_probe.py`, and `high_res_sweep.py::R_ANALYTIC = mp.R_ANALYTIC` -- and all three are literal or a direct alias. It is a frozen constant, and it was frozen before any rung existed, per the header comment over the constant block:

```
# registered constants.  NONE of these may be edited after a rung has been run:
# the bar and the analytic reference were fixed before any refined-mesh number
# existed (decisions.md, "bar first, number second, verdict third").
```

**Route 2 -- the measurement (numerator).**

mesh (`ny=200, nz=76, cell=1e-4`) -> generalised pencil -> dense QZ -> lambda = `beta_sq` -> column selected by exact `beta_sq` match -> eigenvector -> `MODE.e_at(_ey_pts)` and `MODE.e_at(_ezc_pts)` -> `e_y`, `e_z_vv` -> per-column `(sum(e_y**2), sum(e_z_vv**2))` -> `R_by_col` -> `R_extracted = R_by_col[banked_idx]` -> `Q = R_extracted / R_ANALYTIC` -> `inside = BAND_LO <= R_extracted <= BAND_HI`.

The column selection is exact, not tolerance-based, and is labelled as such:

```
_sel_bsq = float(mode.beta_sq)
_hits = [i for i, r in enumerate(rows) if float(r[1]) == _sel_bsq]
banked_src = "solver selection (matched by mode.beta_sq)"
```

**Where it breaks.** The vertical arithmetic is clean: `R` is one float64 division of two float64 sums, each a single `np.sum` over a float64 array. The audit's own anchor comment says so -- the quantity "is one float64 division of two float64 sums over one fixed deposited field, so on the mesh that reproduces the banked column it comes back bit-identical". A break in that arithmetic would have to be a lattice or component mis-pairing, and Measurement 1 below closes both. The breaks are on the two **horizontal joins** -- the two places where each route is handed a number instead of deriving it:

- **Join 1 (reference side, lattice tracking).** The denominator is evaluated on one fixed lattice pair -- `(NYN-1, NZN) = (200, 77)` for `E_y` and `(NYN, NZN-1) = (201, 76)` for `E_z`, from `NY, NZ, CELL = 200, 76, 1e-4`. The numerator is evaluated on whatever lattice the rung's own mesh implies, which at rung 4 is finer. So the denominator is a fixed point and the numerator moves. §(a) T1.7 records this as a definitional fact; here it is a structural one: the two routes were only ever coincident at rung 0.
- **Join 2 (numerical side, the control operand).** The numerator is certified, not against `R_ANALYTIC`, but against `R_REGISTERED = 4.0489791163982565`, and the audit's ANCHOR comment identifies exactly that number as what the pre-fix defective code wrote on this mesh: before the step-5 fix `R_extracted` came from loop-scoped arrays, i.e. "from the LAST SCANNED propagating column", and "on the PMC mesh that column happens to be the identified column, so 4.0489791163982565 is also what the defective code wrote". The PEC witness makes the defect visible -- the old code wrote `70.63501855512833`, "column 704's ratio", while the solver selects column 699, "whose ratio is 4.163656524825077" -- and the comment ends "70.63501855512833 is therefore a wrong-column artefact and must never be quoted as a measurement". On the PMC mesh the artefact and the measurement coincide, so the artefact was banked as the anchor.

The consequence is arithmetic rather than physical, and it is developed in §(f). It is stated here because it is a property of the *chain*, not of any single rung: the two constants the chain compares are `R_REGISTERED` and `R_ANALYTIC`.

```
R_REGISTERED / R_ANALYTIC = 4.0489791163982565 / 2.8101021387524523 = 1.440865461991
```

The control gate requires `|R - R_REGISTERED| / R_REGISTERED <= 1e-6`; the band gate requires `R` in `[2.52909192487721, 3.09111235262770]`. Those two conditions have disjoint solutions. No value of `R` satisfies both, at any rung, ever. A passing control and a failing band are therefore not two observations that happen to co-occur; they are one observation, entailed by the two registered literals before any solve runs.

### Measurement 1 -- the ruler is exact `[MEASURED]`

The denominator was rebuilt from the deposited profile on the coarse mesh and compared to the literal.

Source of the mesh: `NY, NZ, CELL = 200, 76, 1e-4` from `.scratch/tol/logs/TOLFLUX.json`. Lattices built with `M.plane_mode(prof, nyn=NYN, nzn=NZN, ...)` where `NYN, NZN = 201, 77`, and guarded by `_want_ez = (NYN, NZN-1)` / `_want_ey = (NYN-1, NZN)`.

- `A_ey` shape `(200, 77)`, float64, 15400 points
- `A_ez` shape `(201, 76)`, float64, 15276 points
- `S_ey = 108.04408322227596`
- `S_ez = 303.61490934246564`
- `S_ez / S_ey = 2.8101021387524523`
- `R_ANALYTIC = 2.8101021387524523`
- difference: **0.0**

The ratio is reproduced to the last bit. The two lattices just built are the same two lattices the audit samples -- `_ey_pts` on `(yc_mid, zn_node) = (NYN-1, NZN) = (200, 77)` and `_ezc_pts` on `(yn_node, zc_mid) = (NYN, NZN-1) = (201, 76)` -- at the same `CELL`, with the same component pairing. The audit is explicit that this pairing is deliberate and that the alternative is wrong:

```
cz_vv = corr(A_ez, e_z_vv)         # PRIMARY: vertical vs vertical
cz = corr(A_ez, e_z)               # SUPERSEDED
```

and the sampling block carries a comment explaining that `_ez_pts` stacks in `(z, y)` order and would raise `ValueError: point ... lies outside the mesh`, which is why `_ezc_pts = np.stack([iyy.ravel(), izz.ravel()], axis=1)` re-stacks the SAME `E_z` lattice into `e_at`'s `(x, y) = (XS, ZS)` order.

So: same lattice, same cell size, same component pairing, exact reproduction. The reference is like-for-like, and the entire `+27% ... +44%` offset sits on the **solved** side of the quotient. Three candidate excuses are closed by this one measurement: support mismatch, point-count mismatch, and normalisation mismatch.

### Measurement 2 -- every rung that produces `Q` is a dense solve `[ARTIFACT] + [MEASURED]`

`emfit/mode2d.py::solve_modes_mixed` selects its algorithm by size and has no sparse fallback:

```
use_dense = (n_e <= _MIXED_DENSE_MAX) if dense is None else bool(dense)
if not use_dense:
    raise NotImplementedError("iterative path pending: A - sigma*B is dense through C D C^T; dense QZ only")
```

with `_MIXED_DENSE_MAX = 3000`.

Rungs 0 and 1 have 1444 and 2404 free edges, both `<= 3000`, so they are dense by default. Rungs 2, 3 and 4 have 3604, 5044 and 9604 free edges and are pushed onto the same dense path from two directions: `high_res_run.py::build_env` sets `C1_ALLOW_DENSE_ABOVE_MAX=1` for every rung with `free_e > MIXED_DENSE_MAX`, and `c1_audit.py` raises the cap in-process with `m2._MIXED_DENSE_MAX = max(_dense_max, int(free_e.size))`. The module announces it:

```
say("DENSE ABOVE MAX: C1_ALLOW_DENSE_ABOVE_MAX is set -- the _MIXED_DENSE_MAX")
say("  guard is lifted for THIS RUN ONLY.  This is the SAME dense QZ path, not a")
say("  sparse solver (docs/design/sparse_eigenmode.md is a design note only).")
```

under the header comment `# ---- dense-above-max opt-in (refinement ladders; no sparse solver here) ----`.

`[MEASURED]` corroboration: `out/rung2_*/env.json`, `out/rung3_*/env.json` and `out/rung4_*/env.json` each contain `"C1_ALLOW_DENSE_ABOVE_MAX": "1"`; `evidence/t4/ladder_convergence.json` records `null` for rungs 0-1 and `1` for rungs 2-4.

A correction to an overreach made earlier in this dispatch: it is **not** true that the codebase has no sparse eigensolver. `eigsh` is imported and used in `solve_modes` and `solve_modes_deflated`. The narrow and correct statement is that there is **no sparse path in the mixed formulation this ladder uses**, and that all Route C work lives in `tools/host/sparse-probe/`. Every rung that produces a `Q` value is a dense QZ solve.

### Measurement 3 -- the ladder, read off the banked spectra `[MEASURED]`

All five rungs re-read from `tools/host/sparse-probe/out/rung{0..4}_*/c1_spectrum.npz`. No solves were run for this dispatch.

| rung | free_e | `R_extracted` | `Q` | abs(Q-1) | abs(R - R_ANALYTIC) | step |
|---|---|---|---|---|---|---|
| 0 | 1444 | 4.0489791163950715 | 1.440865461991 | 0.440865462 | 1.238876978 | -- |
| 1 | 2404 | 3.7803319900157453 | 1.345264977341 | 0.345264977 | 0.970229851 | -0.268647126 |
| 2 | 3604 | 3.5673083405263886 | 1.269458604843 | 0.269458605 | 0.757206202 | -0.213023649 |
| 3 | 5044 | 3.6127170292894397 | 1.285617693204 | 0.285617693 | 0.802614891 | +0.045408689 |
| 4 | 9604 | 3.5754127531951991 | 1.272342632636 | 0.272342633 | 0.765310614 | -0.037304276 |

`n_eligible = 1` at every rung, so the control's second limb is satisfied everywhere.

Three facts about this table, all of them against the refinement story:

1. **The offset is 2.72x to 4.41x the 0.10 half-width.** The smallest violation is rung 2, not rung 4.
2. **Rung 4 is worse than rung 2** -- 0.2723 against 0.2695 -- while carrying 2.67x the free edges. Refinement is not converging on the analytic reference; it is oscillating around a point that is not the reference.
3. **The residual is flat.** A `1/free_e` extrapolant `R = a/free_e + R_inf` gives `a = +855.593184995` and `R_inf = 3.428043018445367` with rms `5.305597e-02`, i.e. **+21.990% above analytic and still outside the band**. Restricting to subsets: rungs 1-4 give `3.4810`, rungs 2-4 give `3.5915`, rungs 3-4 give `3.5341`, a quadratic fit gives `3.5543`. Every one of them lands at least `0.34` above `BAND_HI`. The log-log slope of `abs(R - R_ANALYTIC)` against `free_e` is **`p = -0.2508`**: essentially flat, against the `-1` or `-2` that a convergent discretisation would show.

Against that, the eigenvalue converges cleanly from the same solves: `beta_sq` falls strictly monotonically `97833.057851 -> 96752.519701` across the ladder, `eps_eff` `3.629512208 -> 3.589425284`. So the solves themselves are behaving; it is the amplitude ratio that will not settle. This is why the report's branch `(d2)` -- "the mesh is NOT the mechanism: refinement has been eliminated" -- is true as an observation about `R` and false as an inference about the physics. The rule block computes it as `mono = all(devs[i][1] >= devs[i+1][1] ...)` over `devs = [(rr, abs(d["R_extracted"] - R_ANALYTIC)) for rr, d in meas]`, i.e. from the same frozen comparison; non-monotonicity of a distance to a frozen wrong target does not eliminate meshing as a mechanism.

### What the break leaves open `[INFERRED]`

The ruler is exact, so the numerator is wrong. But *why* the solved amplitude ratio sits 27-44% above the deposited one is not established by anything above, and this dispatch did not test it. One candidate is recorded here only so that it is not mistaken for a finding: `z` is the vertical axis and the substrate interface lies at constant `z` (`nz*cell = 0.0076` is the height; `ny*cell = 0.02` is the width). `E_z` is normal to that interface and `E_z` jumps across it by roughly `eps_r ~ 3.6`. A surface sum of `E_z**2` is therefore dominated by a field discontinuity, sampled on a lattice of `15276` points at rung 0 -- and on `3321` points at rung 4, where `nz` is finer in the lateral direction but the vertical quadrature over the jump is coarser relative to the lateral refinement. If that is the mechanism, the numerator is measuring a quadrature of a discontinuity and no amount of lateral refinement fixes it. **This is a hypothesis. It is not asserted, and it was not tested.**

## (c) `beta` and `sigma_beta` per rung, and what each number is

Two different objects in this repository are called `beta`, and the brief's question depends on which one is meant. They are unrelated.

**The station fit's `beta`** is a *fitted* propagation constant, from `emfit/ports.py::fit_beta`: a least-squares fit of `v(z) = A * exp(-j*beta*z)` over stations, with a coarse scan of `beta` over `(0, pi/dz_min]` followed by refinement. Its `sigma_beta` is a Gauss-Newton curvature estimate: with `C(b) = ||v - Phi(b) a(b)||**2`, `s**2 = C/dof`, `dof = 2*n_stations - 2*n_wave`, and `sigma = sqrt(2*s**2 / C'')`, where `C''` is a central second difference taken at 2% and 1% of the natural width `1/span` and the estimate is rejected when the two disagree by more than a factor of 2.

**The ladder's `beta`** is not fitted at all. It is `sqrt(beta_sq)`, where `beta_sq` is the raw generalised eigenvalue of the pencil, and `eps_eff = beta_sq / (k0*k0)`. `k0 = 164.17940719617263` at every rung.

Per-rung values, `[MEASURED]`, agreeing across three independent files per rung (`out/rung*/c1_table.txt`, `out/rung*/run.log`, `out/summary_HIGHRES.txt`):

| rung | free_e | `beta_sq` | `beta` (rad/m) | `eps_eff` | `sigma_beta` | `station_fit` | chosen column |
|---|---|---|---|---|---|---|---|
| 0 | 1444 | 97833.057851 | 312.782764632 | 3.629512208 | `[ABSENT]` | `[ABSENT]` | 732 |
| 1 | 2404 | 97328.308109 | 311.974851726 | 3.610786479 | `[ABSENT]` | `[ABSENT]` | 1224 |
| 2 | 3604 | 97049.125606 | 311.527086473 | 3.600429077 | `[ABSENT]` | `[ABSENT]` | 1826 |
| 3 | 5044 | 96873.888680 | 311.245704678 | 3.593927956 | `[ABSENT]` | `[ABSENT]` | 2561 |
| 4 | 9604 | 96752.519701 | 311.050670632 | 3.589425284 | `[ABSENT]` | `[ABSENT]` | 5133 |

**Provenance of the `[ABSENT]` entries.** A grep for `sigma_beta` and for `station_fit` across every text file under `tools/host/sparse-probe/out/` -- 30 files, with the 9 `.npz` binaries skipped by size -- returns zero occurrences. The bare token `station` returns zero as well. This is a searched absence, not an untested one, and its shape is informative: a refused fit raises `ValueError` in `fit_beta`, which would have aborted the run rather than quietly recorded a missing column, and no rung's `run.log` shows an abort. The ladder did not call the fit; it did not call it and fail.

**T2.3 -- what is `sigma_beta` per rung?** Answered with the values that exist: `sigma_beta` is 312.78, 311.97, 311.53, 311.25, 311.05 rad/m if and only if the question means the ladder's `beta`, which is exact and is not a fit. The fitted `sigma_beta` does not exist for any rung of this ladder.

**T2.6 -- does the refusal apply to this ladder?** **No.** The `1.7098484335215227e-15` that the brief quotes as `beta` is not this ladder's `beta`; this ladder's `beta` is 311-313 rad/m and moves only 0.55% monotonically downward from rung 0 to rung 4, tracking `beta_sq` exactly as `sqrt` of it must. The quoted near-zero value belongs to a different run. Nothing in the ladder's output bears on the refusal.

**T2.4 -- is the value propagating?** Yes, and consistently. `eps_eff` runs `3.589425284` to `3.629512208`, so `beta/k0` is `1.895` to `1.905` -- a quasi-TEM mode on `eps_r ~ 3.6`, with a real eigenvalue. `eps_eff` is the eigenvalue divided by `k0**2` and is monotone, and it is corroborated independently by P1.

**T2.5 -- which reading of the refusal warning applies?** Reading (b), a positivity guard. The guard is `if sigma_beta >= beta: raise ValueError(... "the trial at beta - sigma_beta would go negative")`, plus `if step >= beta: return None` inside the curvature estimator. Both quantities are in rad/m, so the comparison is between an uncertainty and a value and tests whether the relative uncertainty has reached 100%. It is a numerical-health guard, not a dispersion relation and not a physical assertion. In particular a fitted-coefficient finding does **not** make outcome C true; per §3 of the acceptance document it could at most remove the null-mode explanation, and here it does not even do that, because the fit is not on `Q`'s path -- see (d).

## (d) Is the T1.6 station fit on `Q`'s path?

**No. `[ARTIFACT]` It is not on the path, on any of three independent grounds.**

1. **No `reference=` on the `Q` path.** Nothing in the chain of (b) passes a reference to the fit. `R_ANALYTIC` comes from `M.plane_mode`, which is a pure index-shift over the deposited profile, not a curve fit to a port response.
2. **The module is loaded but never invoked.** `c1_audit.py` reaches `emfit/ports.py` transitively -- `c1_audit.py` -> `import emfit.modal` -> `from .ports import ...` -- so the names are in scope and a naive import-graph reading would say the fit is involved. It is not: the audit uses exactly one modal symbol, `M.plane_mode`.
3. **The ladder never called the fit at all.** This is the grep result in (c): zero occurrences of `sigma_beta`, `station_fit`, or even bare `station` across all 30 text files under `tools/host/sparse-probe/out/`.

The only reachable route by which the fit could influence `Q` would be through `zc` when `station_fit is None`; but with no `reference=` supplied, a missing `zc` raises rather than substituting a fitted value. The route is not merely unused, it is closed.

Consequence for the close-out: the brief's lead item -- that the station-fit refusal was the most important thing to explain -- cannot be an explanation of `Q`, because the fit does not touch the computation of `Q`. It is a real observation about some run, and §(e) records it as such, but it is not an input to this failure.

## (e) Disagreements: what the dispatch said and what the artifacts say

Nine items. Each is a place where the brief and the record diverge. Where the brief is right in substance and wrong only in number, that is said; where the brief's lead cannot hold, that is said too.

**1. The rung-4 figure, and which rung is actually worst.**

*Dispatch said:* `Q = 1.272` against a `0.10` bar at rung 4, i.e. twelve times the bar; and rungs 0 and 1 sit at `0.441` and `0.345`.

*Artifact says:* those are two different columns. `0.441` and `0.345` are `abs(Q - 1)` at rungs 0 and 1. Rung 4's `Q` is `1.272342632636`, and its `abs(Q - 1)` is `0.272342633`. The brief compared a `Q` value against `abs(Q - 1)` values. Rung 4 exceeds the half-width by **2.72x**, not 12.7x.

The correction inverts the brief's framing. Rung 4 is not the bad rung; it is one of the *better* ones. The worst rung is **rung 0**, at `0.440865462`, `4.41x` the half-width -- and rung 0 is the control rung, the one the project treats as known-correct and the one whose `R_extracted` is the registered anchor. The ladder's worst point and its control point are the same point. That single fact is what decides (f).

**2. The station-fit refusal is `[RELAYED]`, and belongs to a different run.**

*Dispatch said:* `sigma_beta = 65.80604052737668` against `beta = 1.7098484335215227e-15`, `station_fit_ok False` -- presented as a finding about this ladder.

*Artifact says:* `[RELAYED]`, and `[ABSENT]` from the ladder. Neither number appears anywhere in the ladder's output; `sigma_beta` and `station_fit` have zero occurrences across all 30 text files under `tools/host/sparse-probe/out/`, and bare `station` has zero as well. The ladder's `beta` is `311.05` to `312.78` rad/m, not `1.71e-15`. The refusal is real, or at least it is quoted from something real, but it is not a measurement of this ladder and must not be tier-marked as one.

**3. The brief's "most important thing" cannot be an explanation of `Q`.**

*Dispatch said:* the station-fit refusal was the single most important thing to explain.

*Artifact says:* the fit is not on `Q`'s path -- see (d), on three independent grounds. It cannot explain a number it does not touch. This does not make the refusal unimportant; it makes it a separate open item, and the close-out declines to fold it into this one.

**4. `sigma_beta < beta` is a positivity guard, not a dispersion relation.**

*Dispatch said:* read the refusal warning as characterising the mode.

*Artifact says:* the code is `if sigma_beta >= beta: raise ValueError(... "the trial at beta - sigma_beta would go negative")`, plus `if step >= beta: return None` in the curvature estimator. Both operands are in rad/m, so the test is on relative uncertainty reaching 100%. It is a numerical-health assertion, not a physical one.

**5. "Bent ruler" is the wrong shape for outcome A.**

*Dispatch said:* if the failure is in the reference rather than the solves, the ruler is bent.

*Artifact says:* the ruler is not bent -- it is exact. The denominator was rebuilt from the deposited profile and reproduced `2.8101021387524523` with a difference of `0.0` (Measurement 1). The whole `+27% ... +44%` offset is on the solved side. Outcome A therefore does not take the "bent ruler" form; it takes the form developed in (f), where the ruler is exact and the number held against it is a documented artefact.

**6. "The sparse route fails", and the `2.3e-18` residual.**

*Dispatch said:* the sparse route fails, citing a residual of `2.3e-18`.

*Artifact says:* two problems. First, the ladder runs no sparse solve at all -- all five rungs are dense QZ (Measurement 2), so no rung's output can be evidence about a sparse path. Second, the ladder's own reported residual at rung 0 is `3.606e-16`, not `2.3e-18`; the `2.3e-18` figure is `[RELAYED]` with unverified provenance and is not reproduced by anything in the ladder's output. This is the exact false close that §5 of the acceptance document forbids: outcome B asserted from a residual that the artifacts do not contain.

**7. `docs/design/t4_amp_ratio.md` §9 is contradicted by the code.**

*That document says:* "Registered, not implemented ... no .py file compares R_extracted against tol_rel".

*The code says:* the comparison is implemented in two places. `high_res_run.py::rule_block` computes `inside = BAND_LO <= last["R_extracted"] <= BAND_HI` and prints `T4_amp: PASS` or `T4_amp: FAIL`; `routeC_mesh_probe.py` computes `abs(q - 1.0) <= Q_BAR`. The band test is live, and it is the test that this whole close-out is about.

This is **reported, not repaired**. `docs/design/t4_amp_ratio.md` is inside the frozen surface (R4) and is not edited by this dispatch. The discrepancy is recorded here because a future reader of that §9 would otherwise conclude the bar was never applied.

**8. A quoting drift of `6.3e-12` in the decision log.**

*`decisions.md:8767` records:* rung-4 `R = 3.5754127532015456`.
*The banked spectrum records:* `R_extracted = 3.5754127531951991`.

Difference `6.3e-12`, which is larger than the printed precision of neither number and therefore not obviously attributable to rounding. It changes nothing -- both are ~27% above the reference, and no conclusion here depends on the twelfth digit -- but it is a real divergence between the log and the bank, and it is recorded so that it is not rediscovered as a discrepancy later.

**9. My own overreach, corrected.**

Earlier in this dispatch I wrote that there is no sparse eigensolver in the codebase. That is false: `eigsh` is imported and used in `solve_modes` and `solve_modes_deflated`. The defensible statement, and the one used in (b), is narrower: there is no sparse path in the **mixed** formulation this ladder calls, and all Route C work is confined to `tools/host/sparse-probe/`. The correction is recorded rather than silently applied, because it changes what (g) can claim.

## (f) Outcome

**A.**

The reasoning runs in three steps and does not require any further measurement.

**Step 1 -- the failure is present at the anchored configuration, before any refinement question exists.** Rung 0 is not a special case; it is the dense route at the configuration the project treats as known-correct. It has 1444 free edges, comfortably under the 3000 dense threshold, so it runs dense by default with no environment override. Its `R_extracted` is `4.0489791163950715` -- the registered anchor, reproduced to `1e-15` relative. Its `n_eligible` is 1. And its `Q` is `1.440865461991`, so `abs(Q - 1) = 0.440865462`, **`4.41x` the `0.10` half-width**. The ladder therefore fails at the one configuration where it is simultaneously certified as correct.

**Step 2 -- the two gates are mutually unsatisfiable, and this is arithmetic from two registered literals.**

```
R_REGISTERED / R_ANALYTIC = 4.0489791163982565 / 2.8101021387524523 = 1.440865461991
abs(R_REGISTERED - R_ANALYTIC) / R_ANALYTIC = 0.440865462
```

The control gate demands `abs(R - R_REGISTERED) / R_REGISTERED <= 1e-6`. The band gate demands `abs(R / R_ANALYTIC - 1) <= 0.10`, i.e. `R` in `[2.52909192487721, 3.09111235262770]`. The first pins `R` to within `4.05e-6` of `4.0489791163982565`; the second excludes everything above `3.09111235262770`. No value of `R` satisfies both. **The two gates cannot both pass at any rung, ever, and no solve of any quality could make them.**

This is the deciding discriminator. `control PASS` and `T4_amp: FAIL` are not two observations that happen to co-occur; they are one observation, fixed by two constants that were registered before the first rung ran. And because they are fixed, the ladder is structurally incapable of distinguishing "Route C is wrong" from "`Q` was mis-specified": it can only ever return the second. A test that cannot pass carries no information when it fails.

The report's branch `(d2)` conclusion -- "the mesh is NOT the mechanism: refinement has been eliminated" -- follows mechanically from this. `rule_block` compares `abs(R - R_ANALYTIC)` across rungs and finds it non-monotone; a distance to a frozen target that is itself `0.4409` away from the control operand will of course be non-monotone. The conclusion is true as a statement about the residuals and false as an inference about the physics.

**Step 3 -- the alternatives to A do not survive, and the inference is labelled as one.**

`B` -- a separate route whose operator is wrong -- is not merely unsupported, it is **inapplicable**. B would need a second route that runs and fails. No such route appears in this ladder: every rung is a dense QZ solve of the same mixed pencil. "The sparse route fails" describes a path that does not run, and the `2.3e-18` residual that was offered as its signature is not in the ladder's output (disagreement 6).

`C` -- a broken input on `Q`'s path -- is **not reachable**. The denominator is exact to `0.0` (Measurement 1); the eigenvalue path reproduces `beta_sq` by exact match; the column selection is exact; the component pairing is the one the audit marks PRIMARY. The only wrong input anywhere on the path is `R_REGISTERED` itself, and its wrongness is documented in the audit's own ANCHOR comment as a pre-fix artefact -- which is not an input error to be repaired, it is the mis-specification itself. Independently, T1.6 is not on the path (d), so the null-mode explanation that C would have leaned on is not available either.

A therefore dominates, and B and C are suspended rather than refuted. That is the correct status: they are not excluded by evidence here, they are excluded as descriptions of what this ladder did.

**What A says, stated more precisely than the dispatch stated it.**

The dispatch's consequence for A was "retire `Q`, specify a replacement". The direction is right; the content needs one correction and one addition.

- **Correction.** The defect is *not* in the denominator's arithmetic. The ruler is exact. Any replacement that begins by re-deriving the analytic ratio has fixed nothing.
- **Addition (i).** The defect is in the **certification operand**. The control compares `R_extracted` against `R_REGISTERED`, and `R_REGISTERED` is, by the audit's own account, what the pre-fix defective code wrote on the mesh where the defective and correct code paths happened to agree. A gate built this way certifies self-consistency with the historical artefact; it cannot certify correctness, and -- because the artefact sits `4.41x` outside the band -- it guarantees that the correctness gate fails. A replacement must certify against an independently computed reference.
- **Addition (ii).** The defect is also in the **choice of scored quantity**. `Q` scores one surface-integral amplitude ratio at one configuration. Route C's claim is that a sparse solver reproduces the dense spectrum. No measured comparison of the two exists anywhere in the tree -- `docs/design/sparse_eigenmode.md` is called "a design note only" by the audit's own banner. A quantity that does not compare the two routes cannot validate the route, however precisely it is measured.

**Limits of this outcome, stated so they are not read as more than they are.** A is an inference from two things: the measured `Q` at the anchored configuration, and the arithmetic unsatisfiability of the two gates. It is not an inference from a re-run, and no re-run was performed. The reason the solved amplitude ratio sits 27-44% above the deposited one remains unexplained, and the interface-discontinuity candidate in (b) remains `[INFERRED]` and untested. What A establishes is that the bar could not have been passed and that the ladder therefore never probed Route C; it does not establish what a correctly specified bar would have shown.

## (g) Route C

**Route C remains unvalidated -- and more strongly, it was not executed by this probe:** all five rungs are dense QZ solves of the same mixed pencil (Measurement 2), so the ladder never exercised a sparse route and its results carry no information about one, in either direction.

**The sparse route is not a candidate for landing on this evidence:** no measured comparison between a sparse and a dense spectrum exists anywhere in the tree, and the only design document for the sparse path is described by the audit's own banner as "a design note only".

## 5. Self-check against the six false closes

- **Asserting A from the refusal warning alone -- avoided.** A rests on the measured `Q` at the anchored rung and on the arithmetic unsatisfiability of the two gates. The refusal warning appears only in (e) item 2, tiered `[RELAYED]`, and is explicitly not on `Q`'s path.
- **Asserting C without T1.6 -- avoided.** C is excluded, and (d) establishes T1.6 off the path on three independent grounds -- no `reference=`, module loaded but never invoked, and a searched absence across all 30 ladder text files.
- **Asserting B from the `2.3e-18` residual -- avoided.** B is called inapplicable because no sparse route runs; the `2.3e-18` is `[RELAYED]`, contradicted by the ladder's own `3.606e-16` at rung 0, and disagreement 6 says so.
- **Quoting `[RELAYED]` as `[MEASURED]` -- avoided.** Every number carries a tier. The five-rung table, the ruler test, the dense-only proof and the `n_eligible` counts are `[MEASURED]` from banked artifacts; the station-fit values and the `2.3e-18` residual are `[RELAYED]`; the fitted `sigma_beta` on this ladder is `[ABSENT]` and is marked as a searched absence, not an omission.
- **UNDETERMINED without naming the blocked discriminator -- not applicable, and the falsifier is named anyway.** The outcome is determined. What would overturn it is a control gate that compares against the independently computed reference rather than against the banked artefact, combined with a scored quantity that compares a sparse spectrum to a dense one; neither exists.
- **A close that omits the Route C sentence -- avoided.** Both sentences are in (g): Route C is unvalidated and was not executed by this probe, and the sparse route is not a landing candidate on this evidence.
