# Pre-registration: convergence order `p` of the sparse transverse eigen-solve

**Status: FROZEN.** Registered before any run of the study it governs. Bar first, number
second, verdict third. No slope is reported in this document: the study has not been run.

---

## A. Identity

| field | value |
|---|---|
| repository | `EE` |
| commit | `f92d36b41921bc9dbab1ce8bf8c2f20927c9529c` (MEASURED, `git rev-parse HEAD`) |
| date registered | 2026-10-29 (MEASURED, system clock) |
| subject | the transverse eigen-solve of `tools/host/sparse-probe/` (`rung4_routeC_probe.py`) |
| scored quantity of THIS document | the convergence **order** `p` of `eps_eff` on the five-rung ladder of §D — a mixed-knob ladder, hence a **composite** rate (§E.0), whose admissible interpretation is fixed by §F2 |
| not in scope | `T4_amp`'s scored ratio `Q`, its bar, its verdict; `docs/design/t4_amp_ratio.md`; any `emfit/` change |
| artefact budget | this file only. No code change, no probe run, no `decisions.md` edit, and **no new rung** (§E.0.1). |

`R_analytic = 2.8101021387524523` (MEASURED,
`tools/host/sparse-probe/evidence/ladder/summary_HIGHRES.txt:5`) is `T4_amp`'s
amplitude-ratio reference and is **not** the reference this study scores against. The two
numbers are different objects and are never interchanged below.

---

## B. Question and hypotheses

**H_p (primary).** `eps_eff(h_strip) = eps_inf + C h_strip^p` with `p` a positive order. The
study measures `p` and reports it. Nothing else is inferred from it.

**H1 (residual flag).** As stated in the tasking, H1 claims the reference-pencil residual
bounds the enlarged-pencil residual through `e2 = -r2/lam` and
`||r_ref|| <= ||r1|| + ||c|| ||r2||`.

**Verdict: H1 is REFUTED as written, and CONFIRMED-ANALYTIC once repaired. E3 is raised**
(§H.4). The algebra: with `r1 = A x1 - lam(m1 x1 - c x2)` and
`r2 = -lam(-c^T x1 + h x2)` and `e2 = x2 - h^-1 c^T x1`, substituting `x2 = e2 + h^-1 c^T x1`
into `r1` gives `r1 = r_ref + lam c e2`, and `r2 = -lam h e2`, hence
`e2 = -(1/lam) h^-1 r2` and

```
r_ref = r1 + c h^-1 r2          =>    ||r_ref|| <= ||r1|| + ||c h^-1|| ||r2||
```

The `lam` cancels. The tasking's form omits `h^-1`, so it is correct only in the special case
`h = I`. The repaired bound is still sparse-only: `h^-1` is the existing `splu(h)` factor
(`rung4_routeC_probe.py:583-618`, `bx(x) = m1@x - c@(lu_h.solve(c^T@x))`). No dense `B` is
required by the certificate. Additional caveat recorded as part of E3: the two residuals the
code prints are normalised **differently** — `||Ax - lam Bx|| / (||Ax|| + |lam| ||Bx||)`
(:583-618) against `||KC z - lam MC z|| / ((||K||_F + |lam| ||M||_F) ||z||)` (:731-745) — so
a certificate must be built on **absolute block residuals**, not on the two reported scalars.
This is a certification requirement, not an order measurement.

---

## C. What `analytic_reference` is, and what it is not

`tools/host/sparse-probe/rung4_routeC_probe.py:290-300` builds it:

```python
prof = microstrip_mode_profile(ctx["HSUB"], ctx["WSTRIP"], ctx["EPS_R"], n_sub=ctx["N_SUB"])
pana = M.plane_mode(prof, nyn=NY+1, nzn=NZ+1, k_strip=K_STRIP, iy_strip_centre=J_CENTRE, cell=CELL)
return {"e_y": ..., "e_z": ..., "eps_eff": float(getattr(prof, "eps_eff", nan)), ...}
```

The reported value `3.3500085193372136` (MEASURED,
`evidence/t4/rung4_routeC_report.json:/analytic_reference/eps_eff`) is `prof.eps_eff`, and
that attribute is a **quasi-static capacitance ratio on a separate, converged wide box**:

```python
# emfit/mode_profile.py:648-650
c_prime = float(phi_flat @ (K @ phi_flat)) / (v_scale ** 2 * length)
c_air   = capacitance_per_length(grid, 1.0, fixed)
eps_eff = c_prime / c_air
```

with the box fixed by `_DEFAULT_N_CLEAN = 200`, `_DEFAULT_N_AIR = 200` cells
(`emfit/mode_profile.py:139,144`) and the docstring's own figure "`eps_eff` is 3.35001 and
`Z0` 50.088 ohm" (`emfit/mode_profile.py:589`), matching the report to six digits (DERIVED
cross-check). It is **not** the Hammerstad–Jensen closed form of `emfit/microstrip.py:127-191`
— that returns `3.3254548131553996` for `u = 0.003/0.0016 = 1.875`, `eps_r = 4.4` (DERIVED,
`emfit.microstrip.z0_eps_eff(1.875, 4.4)[1]`); the docstring's "+0.74 % off the
Hammerstad–Jensen fit" (`mode_profile.py:589`) reproduces that split exactly
(3.35001/3.32545 = 1.00739).

**Consequence, frozen into the design.** `prof.eps_eff` is (i) quasi-static, hence
dispersion-free, while the ladder solves a full-wave eigenproblem at
`f0 = 7833566197.718491 Hz`; (ii) computed on a 20 mm-wall box, while the ladder's PEC wall
sits at 8.5 mm (`Y0 = 0.0085`) and the docstring states a plane-sized box "would be 4-5 %
high" (`mode_profile.py:591-592`). Therefore the measured gap between the ladder's `eps_eff`
and `3.3500085193372136` (relative errors 8.3434e-2, 7.7844e-2, 7.4752e-2, 7.2812e-2,
7.1468e-2; DERIVED from MEASURED `eps_eff`) **cannot** be read as mesh error. It is a
definitional gap, and no convergence order may be extracted by fitting that gap. Any `p`
derived from `log|eps_eff - 3.3500085193372136|` would be measuring box size, not
discretisation. This is the single most important constraint in this document.

---

## D. Ladder inventory (measured)

Geometry, common to every row (MEASURED, `evidence/t4/rung4_routeC_report.json:/geometry`):
`W = 0.02`, `H = 0.0076`, `HSUB = 0.0016`, `WSTRIP = 0.003`, `EPS_R = 4.4`, `CELL = 1e-4`,
`k0 = 164.17940719617263`, `Y0 = 0.0085`, `Y1 = 0.0115`, `ZZ1 = 0.0036`.

| rung | strip / y_air / z | nodes | free_edges | free_nodes | beta_sq | beta | eps_eff | R_extracted | wall | repro | source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 12 / 9 / 8,4,4 | 31x17 | 1444 | 483 | 97833.0578510 | 312.782764632 | 3.629512208 | 4.048979116395071 | 19.7 s | PASS | MEASURED, `evidence/ladder/` rung0 set |
| 1 | 16 / 12 / 10,5,5 | 41x21 | 2404 | 803 | 97328.3081094 | 311.974851726 | 3.610786479 | 3.780331990015745 | 106.2 s | FAIL | MEASURED, `evidence/ladder/summary_HIGHRES.txt:54-73` |
| 2 | 20 / 15 / 12,6,6 | 51x25 | 3604 | 1203 | 97049.1256062 | 311.527086473 | 3.600429077 | 3.567308340526389 | 405.4 s | FAIL | MEASURED, `evidence/ladder/` rung2 set |
| 3 | 24 / 18 / 14,7,7 | 61x29 | 5044 | 1683 | 96873.8886804 | 311.245704678 | 3.593927956 | 3.61271702928944 | 1277.6 s | FAIL | MEASURED, `evidence/ladder/` rung3 set |
| 4 | 36 / 22 / 20,10,10 | 81x41 | 9604 | 3203 | 96752.5197006 | 311.050670632 | 3.589425284 | 3.575412753195199 | 9784.9 s | FAIL | MEASURED, `evidence/t4/ladder_convergence.json` |

Supporting MEASURED columns: `n_edges / n_pec` = 1486/42, 2460/56, 3674/70, 5128/84,
9720/116; `n_eligible = 1` on every rung; `free_e = n_edges - n_pec` holds on every rung
(`summary_HIGHRES.txt:61`). Rung 0 is the **gate, not a data point**
(`summary_HIGHRES.txt:39-46`): registered `R = 4.0489791163982565`, gate
`rtol = 1e-6`, achieved `7.866e-13` — PASS. Rungs 1-4 set `C1_ALLOW_REMESH=1`; rungs 2-4
also set `C1_ALLOW_DENSE_ABOVE_MAX=1` (MEASURED, each rung's `env.json`).

Declared discrepancy, recorded rather than smoothed: `summary_HIGHRES.txt:54` labels rung 4
"joint, 2.67x", but the per-knob ratios from rung 0 are strip `36/12 = 3.00`, y_air
`22/9 = 2.4444`, z `20/8 = 2.5` (DERIVED). 2.67 is the mean of the three, not any single
knob. The ladder is mixed-knob: strip, first-axis air and the z triple move together, on
every rung. **It is the data of record for this study** (§E.0); the consequence of that
co-refinement is that any single exponent read from it is a **composite** rate, and §F2
fixes what such a rate may and may not be claimed to prove.

Per-knob mesh spacings and their ratios (DERIVED, from the MEASURED cell counts):
`h_strip = 0.003/strip` = 2.5e-4, 1.875e-4, 1.5e-4, 1.25e-4, 8.333333e-5 → ratios 1.3333,
1.25, 1.20, 1.50; `h_y_air = 0.0085/y_air` → ratios 1.3333, 1.25, 1.20, 1.2222;
`h_z` band-wise (1.6 mm / 2.0 mm / 4.0 mm over the z triple) → ratios 1.25, 1.20, 1.1667,
1.4286. `free_e` ratios: 1.6648, 1.4992, 1.3996, 1.9040; `max/min = 6.65097`; the whole
range spans `9604 - 1444 = 8160` free edges.

### D.1 What the `repro` column means, and why rungs 1-4 read FAIL

The column is the `repro=` field of each rung's own `run.log.txt`, parsed by the driver at
`high_res_run.py:461` (`DONE_REPRO = re.compile(r"repro=(\w+)")`) and used at `:465-479`;
the driver notes that `repro` "live[s] only in the log" (`high_res_run.py:410`). It is
**emitted by the mesh audit** `tools/host/c1-audit/c1_audit.py`, the child process each rung
executes: `c1_audit.py:1014` prints
`f"repro={'PASS' if _repro_ok else 'FAIL'} repro_rtol={REPRO_RTOL:g}"` into the `DONE` line,
and `_repro_ok = all(_repro)` at `c1_audit.py:1000`.

What `_repro` collects (`c1_audit.py:960-1001`):

1. **Two mode-shape comparisons against fixed banked anchors.** The run's own `|corr_e_y|`
   and `|corr_e_z|` are compared with `0.9207707848111418` and `0.11916043239134175`
   respectively, at `REPRO_RTOL = 1e-6` relative (`c1_audit.py:979-985`). Those anchors are
   constants of the **rung-0 31x17 control mesh**, taken from the banked capture
   `BANKED = .scratch/s10118_mixed_mode.npz` (`c1_audit.py:180`).
2. **One exact `R_extracted` comparison, only where an anchor exists** — i.e. only when the
   column this run resolved is the same column the cache identified
   (`if bank_col >= 0 and banked_col == int(bank_col)`, `c1_audit.py:990-995`, tolerance 0).
   On rungs 1-4 the cache column is `-1`, that branch is skipped, and the log prints
   `REPRO R  R_extracted = ... (no anchor: ... )` instead (e.g.
   `evidence/rung1_.../run.log.txt:53`, `out/rung4_.../run.log:68`).

**So the column is a reproducibility self-check of the run's mode-shape scalars against the
rung-0 anchors. It is not a reference-agreement verdict, and it carries no information about
whether a dense reference exists at that rung.** Measured values (`run.log.txt` / `run.log`,
REPRO e_y and REPRO e_z lines): rung 0 `1.956e-13` / `2.755e-11` → PASS; rung 1 `1.872e-2` /
`9.652e-4`; rung 2 `2.832e-2` / `1.123e-3`; rung 3 `3.930e-2` / `1.556e-3`; rung 4 `5.339e-2`
/ `1.219e-3` → FAIL. The shape scalars are mesh-dependent, so on a different mesh the check
*must* return FAIL: it is a control-mesh replay, and only the control mesh can replay it.
A FAIL here is therefore not an error, not a defect of rungs 1-4, and not evidence about the
eigenpair; it is the check behaving as designed, and it is reported as measured rather than
suppressed or reinterpreted.

Rung 4 does now have a banked dense anchor, and the FAIL above is unrelated to it.
`evidence/t4/rung4_dense_anchor.json` (schema `t4_rung4_dense_anchor/1`, values read from
the finished dense run `tools/host/sparse-probe/out/rung4_s36_a22_z20-10-10/`) banks
`beta_sq = 96752.51970055024`, `R = 3.575412753195199`, `eps_eff = 3.5894252835292333`,
`corr_ey = -0.9699299418483792`, `corr_ez_vv = -0.9665079165493766`. Supplied through
`--dense-anchor`, `evidence/t4/rung4_routeC_report.json:/verdict/route_C/rung4/agreement`
records `status = "REPRODUCES_REFERENCE"` with `digits_beta_sq = 11.492308060949373`
(`rel_err_beta_sq = 3.218784779622725e-12`), `digits_R = 11.750793344542036`
(`rel_err_R = 1.77503391525794e-12`), `rel_err_eps_eff = 3.218739483580933e-12`,
`abs_diff_corr_ey = 1.999511667349907e-13`, `abs_diff_corr_ez_vv = 1.318944953254686e-13`,
`meets_thresholds = true` against `min_digits_beta_sq = 6.0`, `min_digits_R = 4.0`,
`max_rel_residual = 1e-8`. The same file records `residual = 9.379388877240471e-13`,
`residual_in_enlarged_pencil = 2.328122901161473e-18`, `x2_matches_DcTx1_rel =
3.016493594052664e-13`, `eigenvalue = 96752.51970086167`, `rayleigh_true_pencil =
96752.51970085397`.

Consequently the §D `FAIL` and the report's `REPRODUCES_REFERENCE` are not in conflict and
neither revises the other: the §D column answers "did this run replay the rung-0 control
anchors?", the report answers "does this run's eigenvalue, `R` and `eps_eff` agree with rung
4's own dense run?". Any statement that rung 4 has no reference available is **false** and
appears nowhere in this document.

---

## E. Target, observable and estimator (decisions)

### E.0 Registered target: the five measured rungs of §D

**The five rungs of §D are the data of record of this study.** They are what `p` is computed
from; no other data set exists or will be created (§E.0.1). Their knobs co-refine — strip,
first-axis air and the z triple all move between rungs, by the ratios recorded in §D — and
that is a property of the data, not a defect to be argued away: it costs nothing in
admissibility and it costs exactly one thing in interpretation, which is that a single
exponent fitted to them is a **composite rate** (mesh refinement plus strip discretisation
plus domain-height refinement plus the z-triple refinement, all moving at once) rather than a
pure mesh-refinement order. §F2 states, item by item and before the number is read, what
such a composite can and cannot prove. That bound is the price of using this data; the band
of §F.3 and the estimators of §E.2 are not softened by it, and no additional rung is
purchased to remove it.

### E.0.1 What a clean single-knob ladder would require, and why it is not available

A clean ladder — one knob moving, the other two frozen, a uniform ratio `r` between
consecutive rungs, at least four rungs — **does not exist on disk**, and it is **not the
target of this document**. No rung of such a ladder will be run under this registration.

The reason is budget, stated with the scaling assumption exposed. The only large-rung cost
that has actually been paid is rung 4's: `9784.9 s` wall and an npz of `738,560,423 B`
(MEASURED, §D, §G). Scaling that forward on the observed last-step behaviour — `7.66x` wall
for a `1.9040x` free-edge increase (§G) — the *next* rung costs at least `9784.9 s = 2.72 h`
wall and at least `738.56 MB x 1.44 = 1.06 GB` of npz (DERIVED, §G), **per rung**, and three
more rungs to reach four from a standing start is at least `8.2 h` and `3.2 GB`. The
assumption is that a clean-ladder rung is no cheaper than rung 4; it is a **lower** bound
only, because wall clock here is machine-dependent and non-portable (§H.6) and because a
single-knob ladder at `r = 1.20` in strip alone places its last rung near or above rung 4's
free-edge count. No upper bound is claimed and none is needed: a lower bound of `>= 2.72 h`
and `>= 1.06 GB` per rung already exceeds this document's artefact budget (which allows no
run at all).

Because that ladder is unavailable, the study does not pretend to have it. It scores the
mixed-knob rungs as they are (§E.0), with the composite-rate caveat carried openly into
§F2 — rather than scoring nothing and calling the absence a result.

### E.1 Primary observable (decision)

**Decision. Primary observable: `eps_eff = beta_sq / k0^2`.**

**Reason.** Three grounds, all from recorded evidence. First, `beta_sq` is the one quantity
the ladder already shows monotone and smooth: MEASURED steps -504.75, -279.183, -175.237,
-121.369, flagged "beta_sq smooth = YES" (`summary_HIGHRES.txt` verdict block), whereas
`R_extracted` is flagged "NO" with steps -0.268647, -0.213024, **+0.0454087**, -0.0373043 —
a sign change at the third step, so a difference-ratio estimator on `R` is ill-defined and
would return a different sign depending on which pair is used. Second, `eps_eff` is the
eigenvalue itself, `beta_sq / k0^2` with `k0` fixed by geometry and frequency: no extraction,
no matched reference, no column selection, hence no estimator-side degrees of freedom to
argue about. `R_extracted` is the `T4_amp` amplitude ratio, `Q = R_extracted / R_analytic`
(`summary_HIGHRES.txt:5-12`) — it carries `R_analytic = 2.8101021387524523`, a separate
reference with its own history, and using it here would couple this study to `T4_amp`'s bar
for no gain. Third, the eigenvalue is what the discrete operator's order governs; the mode
shape converges at its own order and is not scored. The competing observable is explicitly
**excluded**: `log|R_extracted - R_analytic|` was previously fitted with `p = -0.2508`,
`c = +1.9373`, rms 0.0959 (MEASURED, `summary_HIGHRES.txt`), which is not an order at all
(a negative exponent on a residual that the reference's own box definition already offsets —
§C) and is retained only as a diagnostic.

### E.2 Estimator: one primary, one secondary, both always reported (decision)

The registered ladder's ratios are **not** uniform (§D: `h_strip` ratios 1.3333, 1.25, 1.20,
1.50). The estimator is therefore not `p = ln D / ln r`, which is exact only for equal
ratios, but the exact two-level relation for unequal ratios.

**Primary estimator (registered).** Take any three consecutive rungs with
`h_1 > h_2 > h_3` and define the two h ratios of the triplet — the two coarser members and
the two finer members —

```
r_1 = h_1 / h_2            r_2 = h_2 / h_3            (both > 1)
D   = (eps_eff(h_1) - eps_eff(h_2)) / (eps_eff(h_2) - eps_eff(h_3))
```

With `eps_eff(h) = eps_inf + C h^p` the differences are `C h_2^p (r_1^p - 1)` and
`C h_3^p (r_2^p - 1)`, so `D = r_2^p (r_1^p - 1) / (r_2^p - 1)`, and after cancelling the
`r_2^p` factor against `r_1^p - 1 = r_1^p (1 - r_1^-p)` and
`r_2^p - 1 = r_2^p (1 - r_2^-p)` the relation becomes

```
D = r_1^p (1 - r_1^-p) / (1 - r_2^-p)
```

which is the equation solved for `p`. **Inversion is numerical, by a bracketing root-find.**
The function `f(p) = r_1^p (1 - r_1^-p) / (1 - r_2^-p)` is evaluated at the declared bracket
ends `p_lo = 0`, `p_hi = 8`; it tends to `ln r_1 / ln r_2` as `p -> 0+` (both numerator and
denominator vanish linearly) and grows without bound as `p` increases (numerator `-> r_1^p`,
denominator `-> 1`). If the measured `D` exceeds `ln r_1 / ln r_2` the bracket is
sign-changing and the unique root on it is found by bisection to `|f(p) - D| / D <= 1e-12` or
200 iterations, whichever comes first. If the measured `D` is **below** `ln r_1 / ln r_2` the
root lies at `p < 0`, outside the bracket and outside the band; that is reported as measured
— the triplet yields a negative exponent — and it is a finding, **not** an occasion to switch
estimator, widen a bracket or drop the triplet. The bracket ends, the iteration count and the
final relative residual are reported with every `p`, so the inversion is auditable and not a
black box.

**Secondary estimator (registered cross-check, always reported alongside).** The unweighted
least-squares slope of `log|delta|` on `log h` across the ladder: the four consecutive
differences `delta_i = eps_eff(h_i) - eps_eff(h_{i+1})` (`i = 1..4`) against the abscissa
`log sqrt(h_i h_{i+1})` (the geometric mean of the pair that produced the difference — the
choice of abscissa is declared here, before any number, rather than after seeing which choice
looks nicer). Four points, unweighted, no intercept reported as an order.

**Precedence.** The primary is the two-level unequal-ratio root-find; the secondary is a
cross-check and is **always** printed next to it, never instead of it. A disagreement between
them that survives inspection is itself **a finding** and is reported as such; it is not
grounds for choosing whichever is more convenient, re-fitting, or moving the band. Both
estimators are computed under **both** mesh parameterisations of §E.3, giving four numbers,
all of which are reported.

**Uncertainty.** `sigma_p = sigma_D / (D ln r)`, with `r = sqrt(r_1 r_2)` for the triplet (the
geometric-mean ratio) and `sigma_D` propagated from the differences; the noise floor implied
by this formula at various `r` is in §G. It is first-order and is reported, not used to
widen the band.

`D` values already visible in the MEASURED sequence (1.8080, 1.5932, 1.4438; DERIVED) are
recorded here as inputs to §G and are **not** converted into a `p` in this document.

### E.3 Two mesh parameters, both reported (decision)

The ladder has no single unambiguous mesh spacing, because strip, air and z move together.
`p` is therefore pre-registered to be reported under **two** parameterisations, and neither
may be presented alone:

* **`h_strip = WSTRIP / strip_cells`.** `WSTRIP` is read from the geometry record, not
  assumed: `tools/host/sparse-probe/rung4_routeC_probe.py:276`
  (`WSTRIP, EPS_R = float(g["w"]), float(g["eps_r"])`), with the record located at
  `TOLFLUX = ROOT / ".scratch/tol/logs/TOLFLUX.json"` (`:126`); the record itself carries
  `"w": 0.003` (`.scratch/tol/logs/TOLFLUX.json:56`), and that is the value the probe copies
  into its report at `:994`. So `h_strip` = 2.5e-4, 1.875e-4, 1.5e-4, 1.25e-4, 8.333333e-5
  over rungs 0-4 (§D), ratios 1.3333, 1.25, 1.20, 1.50.
* **`h = free_e^(-1/2)`,** the free-edge count's own scale, from the MEASURED counts
  1444, 2404, 3604, 5044, 9604 (§D): ratios `sqrt(free_e_{i+1}/free_e_i)` = 1.290, 1.224,
  1.183, 1.380 (DERIVED). This parameterisation uses the quantity the document actually
  resolves (`free_e`), and is the one under which the ladder's *effective* refinement is
  least favourable: it is roughly quadratic in strip cells, so a uniform strip ratio is not a
  uniform `free_e` ratio.

**Both exponents are reported, always, side by side.** A disagreement between the `h_strip`
exponent and the `free_e^(-1/2)` exponent is itself a finding, and is reported as one; it is
not resolved by preferring one parameterisation after the fact. The co-refinement caveat
stands over both: neither number is a pure mesh-refinement order, and §F2 governs what either
may be claimed to prove.

---

## F. Acceptance criteria (locked before the run)

### F.1 Ladder shape and the rung-0 gate

At least four usable rungs with strictly decreasing `eps_eff` (monotone consecutive
differences, so `D > 0` in §E.2); every rung reports `n_eligible = 1`; rung 0 reproduces
`4.0489791163982565` at `rtol = 1e-6`. **All five rungs of §D are already in hand and satisfy
the shape requirement** (MEASURED: `n_eligible = 1` everywhere; gate achieved `7.866e-13`,
§D). This criterion asks for no new rung.

### F.2 AC-2.1 resolution

"A ladder spanning 9604 free edges" is read as *the largest rung has 9604 free edges*
(reading (a)). Under reading (a) all five existing rungs qualify and the three-or-more-
resolutions requirement is satisfied trivially at 6.65097x — the target is the existing strip
ladder, exactly as AC-2.1 states. Reading (b) — a 9604-wide *interval* of free-edge counts —
is **arithmetically impossible**: the total available span is 8160 (DERIVED, §D), so no
sub-selection can satisfy it. Reading (b) is recorded as unsatisfiable by construction and is
not the reading in force.

### F.3 Order band (AC-2.2) — one band, no grey zone

`p` in `[1.70, 2.30]` → H_p **CONFIRMED**. **Any** `p` outside `[1.70, 2.30]` → H_p
**REFUTED**, and that out-of-band value **is the finding**: AC-2.2 says so in its own words
("A measured order outside the band is the finding, not a failure to be explained away").

There is no intermediate zone. v1 of this document carried a "WEAK" band
`[1.40, 1.70) u (2.30, 2.60]` and a sentence reserving the name "the finding" for values
outside `[1.40, 2.60]`; **both are withdrawn here** and no graded or deferred verdict
exists. A purely descriptive label may accompany an out-of-band value (for example
"near-miss" for a value within 0.10 of an edge, "gross" otherwise), but a label carries no
verdict weight: the verdict is REFUTED at the moment the value lands outside the band, with
no repair named, no refit, no second bracket, no relabelling of the band and no deferral to
another section. In particular, an out-of-band `p` is **a result, not a failed study** — the
phrase "the refinement study is declared to have failed" does not belong to this criterion
and has been removed. Study-level failure is a separate, gate-only condition (§F.6).

### F.4 Reference coupling

`p` is estimated from differences of `eps_eff` only. No fit against `3.3500085193372136` is
admissible for scoring (§C). Any submission that reports a slope against that value is
rejected on sight.

### F.5 Residual certificate (AC-2.3 / E3)

Every rung must satisfy the repaired H1 bound on absolute block residuals,
`||r_ref|| <= ||r1|| + ||c h^-1|| ||r2||`, with `h^-1` supplied by the existing `splu(h)`
factor. A rung failing it has its numbers withheld pending harness repair: the failure is
recorded, not smoothed, and not counted as a usable rung in §F.1.

The AC-2.3 flag hypothesis is answered in §B and its two halves must be kept apart. *Is the
enlarged-pencil residual computable without forming dense `B`?* Yes — Route C is the sparse
route and its own report carries
`residual_in_enlarged_pencil = 2.328122901161473e-18` (MEASURED,
`evidence/t4/rung4_routeC_report.json:207`). *Does it certify the Schur-complement
eigenpair?* **No, not as the tasking states it** — the tasking's inequality drops `h^-1`
(§B). Hence E3 is raised, and §G carries the measured memory bound that motivates refusing
dense `B` in the first place (`n_e = 9604` → `737,894,528 B = 0.68722 GiB`, with `~3.78 GiB`
for a QZ path holding ~5.5 copies).

### F.6 Study-level failure — a separate, gate-only condition

The study is declared **failed as a study** only if one of these four pre-registered GATES
fails. Nothing else — in particular no out-of-band `p` — can trigger this condition:

* **G1 insufficient rungs:** fewer than four usable rungs (§F.5 withholdings reduce the
  count).
* **G2 non-monotone differences:** a sign change among the four consecutive `delta_i`, which
  makes `D > 0` undefined and the §E.2 primary estimator inapplicable.
* **G3 gate-1 noise-floor breach:** rung 0 fails to reproduce `4.0489791163982565` at
  `rtol = 1e-6`, so the harness rather than the physics is in question.
* **G4 unresolved reproducibility:** the primary and the secondary estimator, or the two
  mesh parameterisations of §E.3, disagree beyond what §E.2's `sigma_p` allows **and** the
  disagreement cannot be attributed to a stated cause, so that no single `p` is reportable at
  all.

If none of G1-G4 fails, the study has produced a number, whatever that number is, and §F.3
delivers the verdict on it.

### F.7 Where each AC-2.x criterion is discharged

All five criteria were located verbatim in `docs/design/d57_acceptance.md:59-68`; none is
invented here, and none is paraphrased in place of the source text.

| criterion | verbatim text (source) | discharged in |
|---|---|---|
| AC-2.1 | "Target is the existing strip ladder: at least three resolutions spanning 9604 free edges." (`d57_acceptance.md:59`) | §E.0 (target), §F.2 (the "spanning 9604" reading) |
| AC-2.2 | "The band **[1.7, 2.3]** is pre-registered. A measured order outside the band is the finding, not a failure to be explained away." (`:60-61`) | §F.3 |
| AC-2.3 | "The residual question is pre-registered as a *flag hypothesis*: is the enlarged-pencil residual (2.33e-18) computable **without forming dense B**, and does it certify the Schur-complement eigenpair? ... If it does not, E3 is pre-registered with a measured memory bound." (`:62-65`) | §B (H1/E3), §F.5 (certificate + both halves of the flag), §G (memory bound) |
| AC-2.4 | "A feasibility argument is mandatory: attainable precision at these resolutions versus the width of the band." (`:66-67`) | §G (noise floor: `sigma_p = sigma_D/(D ln r)` at `r` = 1.3333 / 1.20 / 1.50) and §E.2 (the `sigma_p` formula) |
| AC-2.5 | "The document states what one strip geometry cannot prove." (`:68`) | §F2 |

---

## F2. What a single strip geometry cannot prove (AC-2.5)

This section is required by AC-2.5 and is a standing bound on the verdict of §F.3. It lists
**limitations, not excuses**: nothing here may be used to defer a verdict, to move the band,
to re-open an estimator choice, or to soften an out-of-band `p`. It says what will *not* be
claimed, before any number exists.

1. **It cannot generalise past one geometry at one frequency.** Every rung shares a single
   `WSTRIP/HSUB` ratio (`0.003 / 0.0016`) and a single `EPS_R = 4.4` and a single
   `f0 = 7833566197.718491 Hz` (§D). Whatever order is found is the order *of this strip
   geometry at this frequency*; no statement about other strip widths, other substrate
   heights, other permittivities, other frequencies, or about asymptotic behaviour as
   `h -> 0` beyond this range follows from it.
2. **It cannot separate mesh-refinement order from strip-discretisation error.** Strip
   cells, first-axis air cells and the z triple co-refine on every rung (§D), so the exponent
   fitted in §E.2 mixes at least three refinement effects plus whatever error the strip
   discretisation itself contributes as the strip is resolved more finely. The clean
   single-knob experiment that would separate them does not exist and will not be run
   (§E.0.1). The two parameterisations of §E.3 do not separate them either; they only show
   how much the answer depends on which mesh scale is called `h`. This is why the number is
   called a composite rate (§E.0) and why an exponent in-band is evidence *about this
   ladder*, not a certificate of a second-order discretisation.
3. **It cannot certify that the extracted quantities agree with the eigenvalue's own
   convergence.** `eps_eff = beta_sq/k0^2` is the eigenvalue; `R_extracted` is a separate
   post-processed amplitude ratio with its own history (a measured sign flip between steps 3
   and 4, §E.1, §H.5) and its own non-convergence. An order on `eps_eff` says nothing about
   the order of `R`, and no joint certificate binding the two is offered here. They are
   separate compositions and are reported separately.
4. **It proves nothing for general quadrilateral meshes.** The operator is assembled on a
   structured rectangular grid (`emfit.mode2d.structured_mesh`, `NX x NY x NZ`). Any order
   measured is the order of *this* discretisation on *this* grid family; it transfers to
   unstructured or skewed quadrilateral meshes only by argument, and no such argument is made
   here.

Corollary, fixed now: an in-band `p` (§F.3) is reported as H_p CONFIRMED **for the five-rung
mixed-knob ladder of §D**, subject to all four items above. It is never reported as "the
solver is second order", and an out-of-band `p` is likewise never explained away by an item
from this list.

---

## G. Feasibility arithmetic (brief; all DERIVED, no measured slope)

* **Memory, dense `B`.** `n_e = 9604` → `9604^2 * 8 = 737,894,528 B = 738 MB = 0.68722 GiB`
  (the code prints "0.69 GiB -- never formed"). A QZ path holding ~5.5 copies would need
  ~3.78 GiB. MEASURED peak RSS for the sparse Route C run: 237.9 MB (243,648 KiB,
  `evidence/t4/rung4_routeC_peak_rss.json`); `factor_memory_gb = 0.016431108` (MEASURED,
  report). The sparse route is what makes rung 4 solvable at all; dense is not funded.
* **Cost of one more rung.** The last measured step cost `9784.9 / 1277.6 = 7.66x` wall for
  a `1.9040x` free-edge increase. A further rung at 1.2x linear in all three knobs is
  `1.728x` free edges; the wall clock of that rung is **UNMEASURED**, and the only hard
  bound is `>= 9784.9 s = 2.72 h`. Its npz is `>= 738.56 MB * 1.44 = 1.06 GB` (DERIVED,
  from the MEASURED rung-4 npz 738,560,423 B).
* **Noise floor for `p`.** `sigma_p = sigma_D / (D ln r)`. To resolve `p` to `+-0.15`:
  at `r = 1.3333` need `sigma_D/D <= 0.15 * ln 1.3333 = 0.0432` (4.3 %);
  at `r = 1.20` need `<= 0.0274` (2.7 %); at `r = 1.50` need `<= 0.0609` (6.1 %).
  Larger `r` is more noise-tolerant but less asymptotic; the registered `r ∈ {1.20, 1.25}`
  is the compromise, and at `r = 1.20` the estimator demands `eps_eff` differences good to
  2.7 % — affordable, since `beta_sq` reproduces the dense reference to 3.218784779622725e-12
  (MEASURED, report).
* **Discrimination check.** For `p` in `[1.7, 2.3]`, `D` would be `r^p` = 1.6307-1.9379 at
  `r = 1.3333`; 1.4613-1.6707 at 1.25; 1.3634-1.5210 at 1.20; 1.9923-2.5410 at 1.50. The
  bands from adjacent `r` overlap, so `r` must be *declared and uniform* for the reading to
  be single-valued. This is the arithmetic justification for the declared noise floor of §E.2.

---

## H. What could not be established

1. **The order is UNMEASURED.** No rung of a uniform-ratio ladder exists. Every `D` in §G is
   an input, not a result; no `p` is claimed.
2. **`eps_eff`'s asymptote is UNMEASURED.** `R_extracted` was previously given the form
   `a/free_e + R_inf` with `a = 855.5932`, `R_inf = 3.428043018445`, rms 5.3056e-02
   (MEASURED fit, `summary_HIGHRES.txt`) — an `R`-form, not an `eps_eff` form. No equivalent
   extrapolation exists for `eps_eff`, so the estimator's `eps_inf` is unknown and `p` must be
   read from *ratios of differences*, never from a two-point fit.
3. **A purely full-wave reference does not exist.** Only the quasi-static wide-box value
   (§C) is available, and it is definitionally offset. Whether the ladder's limit is the
   quasi-static value plus dispersion, or something else, is **UNMEASURED**. Consequently no
   absolute error of the ladder is quotable, only its order.
4. **E3 (erratum raised).** H1 as stated in the tasking is dimensionally wrong: it drops
   `h^-1`, valid only for scalar `h = 1`. Repaired statement in §B; the repair costs nothing
   (existing `splu(h)`), but any certificate built on the tasking's literal inequality would
   be unsound, and any comparison of the two printed residuals is invalid because their
   normalisations differ. Recorded as E3 rather than silently corrected.
5. **`R_extracted`'s non-smoothness is unexplained.** A sign flip between steps 3 and 4
   (MEASURED) is not a mesh artefact and is not investigated here. It is the reason `R` is
   excluded as primary, not a claim about its cause.
6. **Machine-dependent columns.** `summary_HIGHRES.txt:991-993` states rung 4's timings are
   this machine's; QZ column indices are not reproducible (`732` vs banked `738` for the same
   mode, `R` agreeing to `8e-13`). Wall clocks in §D are therefore MEASURED on one host and
   are not a portable cost model.
7. **The ladder is not blind.** Its five rungs predate this document, so anyone running the
   study has seen the `D` values in §G. The defence is structural, not conscientious: the
   bar (§F.3), the estimators (§E.2), the two mesh parameterisations (§E.3) and the AC-2.5
   limitation section (§F2) are all fixed before the five rungs are read as data of record,
   and the composite-rate bound of §F2 is part of that fix, not a concession made afterwards.
   The rungs themselves are the data (§E.0); none of them is scored against a bar chosen
   after seeing them. That is stated here so it is on the record.

---

## I. Freeze declaration

Registered before the first rung of *this* study's reading. The five rungs of §D already
exist and are named here as the data of record (§E.0); **no further rung will be run** under
this registration, uniform-ratio or otherwise (§E.0.1). The bar (§F.3), the observable
(§E.1), the primary and secondary estimators with their precedence (§E.2), the two mesh
parameterisations (§E.3), the AC-2.1 reading (§F.2), the gate-only failure condition (§F.6)
and the AC-2.5 limitations (§F2) are fixed from here on. Post-hoc use of a number from the
ladder to move the band is a breach, not a correction. No knob moves anywhere: geometry,
`f0 = 7833566197.718491 Hz`, `k0`, the `eps_eff = beta_sq/k0^2` definition and the
`n_eligible = 1` rule are fixed. Reading order: F.1 shape and gate, then F.5 certificate,
then both estimators under both mesh parameterisations, then F.3 verdict, with §F2 standing
over the verdict as the bound on what it may be claimed to mean. Any failure of G1-G4
(§F.6) is reported before any number.

Reproduction of the inputs quoted above:
`tools/host/sparse-probe/evidence/ladder/summary_HIGHRES.txt`,
`tools/host/sparse-probe/evidence/ladder/rung{0,1,2,3}/` (`c1_table.txt`, `env.json`,
`npz.sha256`, `run.log.txt`), `evidence/t4/rung4_routeC_report.json`,
`evidence/t4/rung4_routeC_peak_rss.json`, `evidence/t4/rung4_dense_anchor.json`,
`evidence/t4/ladder_convergence.json`, `docs/design/d57_acceptance.md:59-68`,
`emfit/mode_profile.py:139-144,535-650`, `emfit/microstrip.py:127-191`,
`tools/host/sparse-probe/rung4_routeC_probe.py:126,276,290-300,583-618,652-660,731-753,994`,
`tools/host/sparse-probe/high_res_run.py:410,461-479`,
`tools/host/c1-audit/c1_audit.py:180,960-1014`, `.scratch/tol/logs/TOLFLUX.json:56`.
