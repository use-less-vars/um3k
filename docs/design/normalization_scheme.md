# Normalization scheme for comparing the E_z and E_y components

Design note. No implementation, no changes to `emfit/`, no new solves. Every number below is
reproduced on the cached 31x17 mode (`.scratch/s10118_mixed_mode.npz`, beta = 312.7827646322591,
f = 7.8336e9, eps_eff = 3.6295121) and, where stated, on the cached 41x22 / 51x19 modes.

**Note on units, added after the fact.** Every `V/m` in this document is a DIMENSIONAL INFERENCE, not a
string the code carries. The code's own docstrings state the edge representation as `e_t[i] =
INT_edge E . dl` (**volts**) and `e_at` as "the continuous field", and the literal string `V/m` appears
nowhere in `emfit/`. The unit is inferred because the Whitney basis carries a 1/length factor. Wherever the
argument below turns on a unit it therefore turns on that inference, and should be read as doing so. The
arithmetic conclusions are unaffected: they follow from the `* CELL` applied to the `e_y` side alone, which
is a factor present in the code and not an inference.


---

## 1. Provenance of the reported `sum(e_z^2)/sum(e_y^2) = 2.72e6`

The number is produced by `python3 .scratch/logs/s10118_split_check.py`. The exact chain:

**Sample lattices** (`s10118_split_check.py:4-9`). Note `basis.NY = 200`, `basis.NZ = 76`,
`CELL = 1e-4` are *FDTD-plane* constants, not mesh constants (the mesh is 31x17 nodes, the
sampling lattice is 201x77 nodes over the whole 20 mm x 7.6 mm box):

```python
NYN, NZN, CELL = basis.NY + 1, basis.NZ + 1, basis.CELL
yc_mid  = (np.arange(NYN - 1) + 0.5) * CELL      # 200 y-cell centres
zn_node = np.arange(NZN) * CELL                  # 77  z-nodes (incl. z=0 and z=H)
yy, zz   = np.meshgrid(yc_mid, zn_node, indexing="ij")
iyy, izz = np.meshgrid(np.arange(NYN) * CELL, (np.arange(NZN - 1) + 0.5) * CELL, indexing="ij")
```

**Denominator** (`s10118_split_check.py:24`) — continuous field via `Mode2D.e_at`, in V/m (by inference — see the note at the head),
then multiplied by the *uniform* FDTD cell 1e-4:

```python
e_y = MODE.e_at(np.stack([yy.ravel(), zz.ravel()], axis=1)).reshape(NYN - 1, NZN, 2)[:, :, 0] * CELL
```

**Numerator** (`s10118_split_check.py:25-26`) — the *nodal* longitudinal field, interpolated
from the graded mesh to the uniform lattice, **no** `* CELL`:

```python
itp = basis.RegularGridInterpolator((ZS, XS), np.asarray(d["e_z_node"], float).reshape(nz, nx))
e_z = -itp(np.stack([izz.ravel(), iyy.ravel()], axis=1)).reshape(NYN, NZN - 1)
```

**The ratio** (`s10118_split_check.py:27-29`), no weights of any kind:

```python
ry, rz = float(np.sqrt(np.mean(e_y**2))), float(np.sqrt(np.mean(e_z**2)))
print("... sum_e_z^2/sum_e_y^2=%.6f" % (tag, ry, rz, ry / rz, float(np.sum(e_z**2) / np.sum(e_y**2))))
```

**Verbatim output of that script on this tree (re-run today):**

```
31x17  rms_e_y=0.002414  rms_e_z=3.999873  rms ratio y/z=0.000604  sum_e_z^2/sum_e_y^2=2722397.314568
41x22  rms_e_y=0.002447  rms_e_z=3.994369  rms ratio y/z=0.000613  sum(e_z^2)/sum(e_y^2)=2642977.869550
51x19  rms_e_y=0.002408  rms_e_z=3.850799  rms ratio y/z=0.000625  sum(e_z^2)/sum(e_y^2)=2536572.286604
```

So the reported `2.72e6` is `2722397.314568` on the 31x17 mesh: **provenance closed**.

**What the two sides actually are** (units chain, all verified in `emfit/mode2d.py`):

* `e_at` returns the continuous field, **V/m by inference** (`mode2d.py:647-649`: "e_t is the *edge*
  representation: e_t[i] is INT_edge E . dl in volts ... e_at is the continuous field";
  `mode2d.py:742-781` builds it as `sum_s w_s (lam_a grad lam_b - lam_b grad lam_a)`).
* `e_z` is the **nodal field, V/m by inference** (`mode2d.py:637-643`: "nodal longitudinal field ...
  ``-i beta (k_zz - k0^2 m_zz)^{-1} c^T e_t``; purely imaginary for a propagating mode, so
  abs(e_z) is the physical amplitude"), and `.scratch/logs/s10118_basis.py:219-226` stores it as
  `e_z_node[free_n] = np.abs(beta * z_free)`.

Therefore line 24 multiplies a **V/m field** by a length, turning the denominator into an
edge-integral-like quantity **[V]**, while the numerator stays **[V/m]**. The ratio is
dimensionally inhomogeneous: it carries an implicit factor 1/CELL^2 = **1e8** and an implicit
factor 1/[length] in the numerator's own units.

**Consequence (the decisive arithmetic):**

| quantity | 31x17 | 41x22 | 51x19 |
|---|---|---|---|
| R as printed by the script | 2.722397e6 | 2.642978e6 | 2.536572e6 |
| R with both sides in V/m (drop `* CELL`) | 0.0272240 | 0.0264298 | 0.0253657 |
| rms E_y [V/m] | 24.14 | 24.47 | 24.08 |
| rms E_z [V/m] | 3.9999 | 3.9944 | 3.8508 |

`2.722397e6 / 1e8 = 0.0272240` exactly: **the printed number is 1/CELL^2 times a physically
sensible O(1e-2) quantity.** The unit mismatch is exactly a factor 1e8 — one factor of `1/CELL^2`, on
one side only: 2722397.314568 / 1e8 = 0.0272. Whatever else is wrong, that factor is 1e8 and no more than 1e8.

---

## 2. Why no global eigenvector scale can fix this (foreclosing "pick a better constant")

Let the solver return a transverse eigenvector `x_t` and the algebraically slaved nodal vector
`x_z = beta * (k_zz - k0^2 m_zz)^{-1} c^T x_t` (`mode2d.py:995-1003`; realised at
`mode2d.py:1104-1118` and `.scratch/logs/s10118_basis.py:219-226`). The block system makes
`x_z` **linear and homogeneous** in `x_t`, so any amplitude `a` applied to the eigenvector
scales both components identically: `x_t -> a x_t`, `x_z -> a x_z`.

Every candidate observable in the pencil is homogeneous of degree 0 in `a`:

* the printed ratio: `sum(c_z e_z)^2 / sum(c_y e_y)^2 -> a^2/a^2 = 1`, unchanged;
* the mass-matrix ratio: `x_z^T M_zz x_z / (x_t^T M1 x_t) -> a^2/a^2 = 1`, unchanged;
* the Rayleigh quotient `beta^2 = x_t^T A x_t / x_t^T B x_t` (`mode2d.py:995-1013`) -> unchanged;
* `v_mode/i_mode`, `eps_eff`, `mode_purity`, `corr_e_y/corr_e_z` -> unchanged.

Moreover the stored vector is *already* normalised in the only way the code does it:
`mode2d.py:1127-1130` divides by the plain 2-norm, and the cache confirms
`sum(e_t**2) = 1` to machine precision. (Caveat worth fixing separately: `mode2d.py:636`
claims the normalisation is `e^T B e = 1`; the code normalises the Euclidean 2-norm instead.
That docstring is wrong either way and does not affect the argument.)

Conclusion: the ratio is **scale-invariant by construction**. No choice of normalisation
constant — unit power, unit 2-norm, `e^T B e = 1`, `v_mode = 1`, `V_strip = 1` — can move
`2.72e6`. Amplitude-pinning (class (i)) is *provably* not the defect; only a change of the
**relative** weighting between the two components can change the number. This is exactly why
the defect is class (ii).

---

## 3. Candidate schemes for "how are components compared", with numeric predictions

All predictions are for the 31x17 mesh unless stated. `R = sum(E_z^2)/sum(E_y^2)` on a
component-wise consistent definition.

### Scheme A — unit repair only ("same representation on both sides")

**Derivation.** A ratio of two quadratic functionals is invariant under a *common* factor but
not under a *differential* one. Either put both on the field footing (drop `* CELL`) or both on
the edge-voltage footing (multiply `e_z` by `CELL`); the two give the same number. Note that
neither choice is the ratio the code thinks it is: `e_t` is an *edge integral* `INT E.dl` on the
graded mesh (`mode2d.py:647-649`), so the honest edge-voltage partner of `E_z*CELL` is
`E_y * (local edge length)`, not `E_y * 1e-4` — on this mesh the local lateral edge length is
0.25 mm inside the strip but 0.944 mm outside, i.e. the script's uniform `CELL` is up to 9.4x
wrong per edge.

**Prediction:** `R_A = 0.0272240` (31x17), `0.0264298` (41x22), `0.0253657` (51x19)
= the printed numbers / 1e8.

### Scheme B — single co-located lattice with dual-cell weights

**Derivation.** Give each sample point the measure of its dual cell: `E_y` at
(y-cell centre, z-node) gets `dy_i * (dz_{j+1}+dz_{j-1})/2`; `E_z` at (y-node, z-cell centre)
gets `((dy_{i+1}+dy_{i-1})/2) * dz_j`. This is a partition of unity, so for a smooth field the
weighted ratio converges to `INT|E_z|^2 dA / INT|E_y|^2 dA` independently of the mesh grading.

**Prediction on this script, and an important negative result:** the sampling lattice used by
`s10118_split_check.py` is *uniform* (`yc_mid`, `zn_node` are multiples of the same `CELL`), so
**every area weight is identical** and the area-weighted ratio collapses exactly onto Scheme A:
`R_B = 0.0272240`. Scheme B therefore fixes nothing here. The residual disagreement with
Scheme C (factor 2.86, below) is *not* a weighting error — it is a **staggering** error (`E_y`
sampled at z-*nodes*, `E_z` at z-*cell-centres*), which no choice of weights can remove. The
real repair in this family is co-location (sample both components at the same points, or
de-stagger one of them), not re-weighting.

### Scheme C — mesh-exact discrete ratio (mass matrices)

**Derivation.** Use the pencil's own metrics. The discrete L2 inner product of a tangential
field is `m1[e,f] = INT (1/mu_r) W_e . W_f` and of the nodal field is
`m_zz[i,j] = INT eps_r phi_i phi_j` (`mode2d.py:469-533`), restricted to free DOFs:

```
R_C = x_z^T M_zz x_z / (x_t^T M1 x_t),   x_z = beta * z_free
```

This is the only definition that is (a) dimensionally homogeneous (both sides are energies per
unit length, up to the `eps` weight), (b) independent of any sampling lattice, and (c) exactly
the quantity the variational problem itself uses.

**Prediction:** `R_C = 0.00951415` (31x17), i.e. `rms E_z / rms E_y = 0.09753`,
`L = sqrt(R_C)/beta = 0.312 mm`, `beta L = 0.0977`. (Note `m_zz` carries `eps_r`, so
`R_C` is the *stored-electric-energy* ratio, not the free-space one; it is larger than the
bare-field ratio by up to `max eps_r = 4.4` in the substrate.)

### Scheme D — analytic quasi-TEM closed form (independent cross-check)

**Derivation.** With `E_z = -i beta phi` and `E_t = -grad_t phi`,
`INT|E_z|^2 dA = beta^2 INT|phi|^2 dA` and `INT|E_t|^2 dA = INT|grad_t phi|^2 dA
= INT|phi|^2 dA / <L^2>`, where `L` is the transverse decay length of the potential. Hence

```
R ≈ beta^2 <L^2>          (quasi-TEM, isotropic-scaling estimate)
```

**Prediction.** With `beta = 312.7828`, `beta^2 = 97833.06`:
`L = 0.2 mm` (thinnest substrate cell) -> `R = 0.0039`; `L = h = 1.6 mm` -> `R = 0.2505`;
`L = h/2` -> `R = 0.0626`. The physical bracket is therefore
**`R in [3.9e-3, 2.5e-1]`**, and `L = 0.312 mm` (from Scheme C) sits inside it at
`R = 0.0095`. Scheme D never predicts anything within 7 orders of magnitude of `2.72e6`.

### Summary of predictions, all schemes

| scheme | R (31x17) | comment |
|---|---|---|
| as printed | 2.722397e6 | = 1e8 x Scheme A; dimensionally inhomogeneous |
| A unit repair | 0.0272240 | removes the 1e8 exactly; still staggered + no metric |
| B dual-cell weights | 0.0272240 | identical to A on a uniform lattice (weights all equal) |
| C mesh-exact | 0.00951415 | the variational problem's own norm |
| D quasi-TEM | 0.0039 ... 0.2505 | bracket; `L = 0.312 mm` -> 0.0095 |

A and C disagree by 2.86x, and both are within the D bracket. **The spread across all
legitimate schemes is a factor 2.9; the printed number is a factor 2.9e5 above the largest of
them.** That is the whole finding.

---

## 4. Singularity / convergence check (actual numbers)

**(a) No singular concentration.** The failing hypothesis was "one cell near the strip edge
dominates the numerator". It does not: on the sampling lattice used by the script the `E_z`
energy is broadly distributed (top-1 cell < 1% of `sum E_z^2`, ~99 of 15276 cells carry 50%,
peak/rms ~ 2.1), and `E_y` is comparably graded (peak/rms ~ 2.5). An edge singularity of the
`r^-1/3`-type would show peak/rms ~ 30+ and a strong mesh dependence of the *numerator* alone;
neither is present.

**(b) Mesh convergence of the ratio.** Three nested meshes, same script, same lattice:

| mesh | rms_e_y (the printed, xCELL quantity) | rms_e_z | R as printed | step |
|---|---|---|---|---|
| 31x17 | 0.002414 | 3.999873 | 2.722397e6 | - |
| 41x22 | 0.002447 | 3.994369 | 2.642978e6 | -2.92% |
| 51x19 | 0.002408 | 3.850799 | 2.536572e6 | -4.02% |

Read this carefully, because it is the strongest single piece of evidence:

* `rms_e_y` is mesh-stable to 1.6% (0.002414 / 0.002447 / 0.002408) — the transverse field is
  converged;
* `rms_e_z` drifts monotonically down (3.9999 -> 3.9944 -> 3.8508, -3.7% over the series);
* consequently `R` drifts down by ~7% overall and is **not converged** — it is still falling at
  the finest mesh tested;
* but the drift is entirely inside `rms_e_z`: it is *not* the 1e8 unit factor (which is exactly
  mesh-independent, `R_field = R/1e8` reproduces the same -2.92%/-4.02% steps), and *not* the
  `e_y` sampling (stable).

Interpretation: the printed ratio inherits a ~7% mesh-sensitivity from the interpolated nodal
`E_z` (`RegularGridInterpolator` of a graded 0.2 mm/1.0 mm mesh onto a uniform 0.1 mm lattice in
the direction of the substrate grading). That is a *normal* interpolation error on a graded
mesh, of the same order as the 4.52% beta discrepancy seen in T1_stab — i.e. **the ratio is
too noisy at this mesh density to distinguish schemes B/C/D at the 10% level, and this noise is
a second, independent reason not to read `2.72e6` as a physical statement.** It is not evidence
of an edge singularity.

**(c) The two fields do not even correlate.** The basis run prints, over the whole box,
`mixed-vs-analytic overlap {'corr_e_y': 0.9208, 'corr_e_z': 0.1192}`. `E_y` agrees with the
analytic profile at the 92% level; `E_z` at 12%. A component-wise ratio of two arrays that
correlate with the reference at 0.92 and 0.12 respectively is not a like-for-like comparison of
two components of one field, no matter how it is normalised.

---

## 5. VERDICT

**The defect is class (ii): incommensurable-component-comparison.** The reported
`sum(e_z^2)/sum(e_y^2) = 2.72e6` is the product of (a) an exact unit-mismatch factor
`1/CELL^2 = 1e8`, introduced by `* CELL` on the `e_y` side alone
(`s10118_split_check.py:24`, where `e_at` and `e_z_node` are both V/m by inference), and (b) a genuine,
physically unremarkable O(1e-2) ratio — `0.0272` in field units, `0.0095` in the pencil's own
mass-matrix norm, `~0.009` from the quasi-TEM estimate `beta^2 <L^2>` at `L = 0.31 mm`. Class
(i), amplitude-pinning, is **provably excluded**: the ratio is homogeneous of degree 0 in the
eigenvector scale (Section 2), and the stored vector is already exactly unit 2-norm. Class
(iii), a singularity artifact, is **excluded by the numbers**: neither component shows singular
concentration (top cell < 1%), and the ratio's mesh drift is a smooth ~7% interpolation error in
the *interpolated nodal* `E_z`, not a divergent edge term. Moreover, all three legitimate
schemes agree with each other to within a factor 2.9 while sitting 5-9 orders of magnitude below
the printed value, so the fault is **not** upstream in the pencil: the pencil's `beta`, `eps_eff`
and eigenvector are self-consistent; the fault is entirely in the comparison script (and in the
same unit policy wherever else it is applied).

**Does `2.72e6` share a root cause with the mixed-basis window sensitivity (T1_stab: fitted
beta 326.9107654423116 vs eigenvalue 312.7827646322591, +4.52%; mixed-span 6.24% vs
0.164%)?** **Yes at the policy level, no at the arithmetic level — and the doc must keep those
separate.**

* Shared root cause: the mixed basis (`s10118_basis.py:314-315` and `370-383`) has **no unit or
  metric contract** between the edge representation and the nodal representation. It builds
  `e_y = E_y * CELL` (an [V]-like edge voltage on a *uniform 0.1 mm* plane) and `e_z = -E_z`
  ([V/m] by inference, from the *graded* mesh), then hands both to `PlaneMode` together with
  `v_mode = -sum(e_z[J_CENTRE, :N_SUB])` — a **plain sum of 16 nodal values, not `INT E_z dz`**
  — and `i_mode = 2/v_mode` (a normalisation hack, `s10118_basis.py:371-380`). That is the same
  sin as Section 1: mixing a field and an edge-integral without saying so. The symptoms it
  produces are exactly the "wrong amplitude" signature: `z0_power = 0.001989` against
  `discrete_power = 1.0` (503x), `mode_purity = 0.207`, `amplitude_mismatch_max = 2.37e4`
  (mixed) vs `1.49e4` (analytic), `v_ratio = 2.12`, `i_ratio = 1.45`, `power_ratio = 3.19`.
* Separate arithmetic: the `* CELL` factor does **not** produce the +4.52% error in the fitted
  beta. Beta is fitted from the longitudinal phase slope of the V/I pair, which is blind to a
  constant factor on `E_y`; the 4.52% and the 6.24% window span come from the `v_mode`/`i_mode`
  *integral definitions* (plain sum over 16 nodes, sample window extending outside the mesh
  where the interpolator extrapolates, `corr_e_z = 0.12`) and from the 4.52%-consistent
  interpolation error of the nodal `E_z` on the graded mesh (Section 4b). Conversely, the 2.72e6
  is *pure* unit mismatch times a small ratio and is insensitive to the window.

So: one policy failure, two distinct numerical consequences. Fixing the unit contract
(Section 3, Scheme A/B/C) will **not** by itself fix the 4.52% beta bias; fixing the integrals
and the illumination window will **not** move `2.72e6` at all. Both must be fixed, and any
regression test must assert on Scheme A/B/C-style ratios, never on the printed one.

---

## 6. What would falsify this

1. **Falsifies the unit-mismatch diagnosis:** any demonstration that `e_z` in
   `s10118_split_check.py` is *also* implicitly multiplied by a length. If `e_z_node` were
   stored already in [V] (i.e. `INT E_z dz`), the 1e8 would be legitimate. Verified false:
   `mode2d.py:637-643` and `s10118_basis.py:219-226` give `e_z = |beta * z_free|` with no length
   factor, and `sum(e_t^2) = 1` shows the two sides are in the same vector of DOFs.
2. **Falsifies "scale cannot change the ratio":** exhibit a code path where `x_z` is *not*
   slaved linearly to `x_t` — e.g. `z_free` recomputed with a *nonlinear* constraint, a
   renormalisation applied to `x_z` only, or `e_z_node` rescaled by its own norm. Grep target:
   any `z_free /=` or `e_z_node *=` after `s10118_basis.py:226`.
3. **Falsifies the quasi-TEM bracket:** a scheme-D-style measurement where
   `INT|E_z|^2 dA / INT|E_t|^2 dA > 1` on a *converged* mesh. That would mean the mode is not
   quasi-TEM (`beta h >> 1` or a genuine TM/hybrid resonance), and a large `E_z/E_y` would be
   physical. On this geometry `beta h = 2.38` and every scheme gives <= 0.027, so this is far
   from happening — but it is the correct falsifier, not "the number looks big".
4. **Falsifies the singularity exclusion:** a mesh series in which `rms_e_z` *grows* with
   refinement (here it shrinks: 3.9999 -> 3.9944 -> 3.8508) or a peak/rms ratio that increases
   with refinement (here ~2.1 and stable). Equivalently: `max|E_z|` located at a corner with
   `r^-1/3` scaling. Currently `E_z` peaks mid-substrate near the strip edge
   (y = 3.0 mm, z = 1.55 mm), not at a corner.
5. **Falsifies "the pencil is not the culprit":** show that `x_z = beta D c^T x_t` fails the
   second block row of the pencil (`mode2d.py:995-1003`) on the stored data, or that the
   `eps_eff`/`beta` pair is inconsistent with the `E_strip_t` used in the capture. Currently
   `residual` and `curl_ratio_raw` in the cache are the code's own checks and are small.
6. **Falsifies the shared-root-cause claim:** find a mixed-basis variant in which the *only*
   change is the removal of `* CELL` (everything else identical, including `v_mode`/`i_mode`
   definitions) and the fitted beta still moves by ~4.5%. Under the analysis above it should
   barely move; if it moves, the "separate arithmetic" half of Section 5 is wrong.
7. **Falsifies Scheme C as the reference:** show that `m_zz` is assembled without the `eps_r`
   weight on this mesh (then `R_C` is a free-space ratio and must be compared with `R_A`, and
   the 2.86x gap becomes an eps-weighting artifact rather than a staggering artifact).
8. **Falsifies the staggering explanation of the 2.86x gap (A vs C):** a de-staggered sampling
   (both components at the same points, exact same weights) that still disagrees with `R_C` by
   more than the ~7% mesh-drift band. *Open item: I ran out of budget before measuring the
   de-staggered variants and `R_C` on the 41x22/51x19 caches, so item 8 is currently the
   weakest link in this note — it should be measured before any implementation decision.*

---

### Reproduce

```
python3 .scratch/logs/s10118_split_check.py            # prints 2.72e6, 2.64e6, 2.54e6
```
`R_C` from the cache: `x_z = beta * d["z_free"]`, `R_C = x_z @ m_zz[free_n,free_n] @ x_z /
(e_t[free_e] @ m1[free_e,free_e] @ e_t[free_e])` = 0.00951415.
