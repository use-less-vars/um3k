# Is there a beta^2 = eps_r k0^2 family in the §158.5 dense spectrum?

Status: measured. Verdict: **the family is not in the spectrum at the audited box** — zero
eigenvalues within 10 % of 193644.18 at either mesh, at h = 0.4 mm (1262 DOF) and h = 0.8 mm (319 DOF).

## Method (and why anything had to be redone)

`evidence/matrix_audit/h040.json` records the *classification* of the spectrum but neither the
eigenvalue array nor the `Z` basis, so the spectrum was recomputed with the same blocks:
`A = k0^2 M_eps,ff - K_q,ff`, `B = M1,ff - C_f (K_zz - k0^2 M_zz)^-1 C_f^T` (`splu` solve, 5.39 s),
`scipy.linalg.eig` = LAPACK `dggev` on the dense condensed pencil. `k0 = 209.78570331727553`
(§158.5's value), `k0^2 = 44010.04131632395`, `eps_r k0^2 = 193644.1817918254`.

| mesh | n_e | n_n | dense QZ | t / s | lam_min | lam_max | n(lam<0) | n with abs(Im)/abs(Re) > 1e-6 |
|---|---|---|---|---|---|---|---|---|
| h = 0.4 mm | 1262 | 429 | 1262 x 1262 | 91.42 | -224795216.424405 | 148241.535699 | 1261 | 98 |
| h = 0.8 mm | 319 | 110 | 319 x 319 | 7.71 | -56047730.248834 | 151598.915012 | 318 | 30 |

`span(Z)` was rebuilt, not read: `_per_triangle` -> `_gradient_columns` -> `_incidence`, giving
**324 air-block columns (rank 324), 81 substrate-block columns (rank 81), union 405 (rank 405)** at
h = 0.4, and **84 / 14 / 98** at h = 0.8 — reproducing `h040.json` `gradient.info` exactly
(`columns_v1 324, columns_added 81, z_dim_v2 405`).

## A. Where is 193644.18?

Counts of eigenvalues within a relative window of `eps_r k0^2 = 193644.181792`:

| window | 1e-6 | 1e-4 | 1e-3 | 1e-2 | 0.05 | 0.10 | 0.25 | 0.50 |
|---|---|---|---|---|---|---|---|---|
| h = 0.4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **1** |
| h = 0.8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **1** |

Against `k0^2 = 44010.041316` the counts are 0 / 0 / 0 at 1e-6 / 1e-3 / 1e-2. **Neither family
exists**: not at eps_r k0^2, not at k0^2, not at eps_r^2 k0^2 (a factor-eps_r test at 1e-3 gives 0
at both meshes). The eight nearest to 193644.18 at h = 0.4 (`g_grad` = squared cosine with
`span(Z)`, `g_sub` = with the 81 substrate-gradient columns, `g_node` = `||z||^2/(||e||^2+||z||^2)`,
`z = h^-1 c^T e`):

| i | lambda | rel to eps_r k0^2 | lambda/k0^2 | g_grad | g_sub | g_node | cos^2 with TEM |
|---|---|---|---|---|---|---|---|
| 531 | 148241.5356985919 | 2.344643e-01 | 3.368357 | 0.046745 | 0.032447 | 2.298e-01 | 1.0000 |
| 536 | -34830.2002913125 | 1.179867e+00 | -0.791415 | 0.954995 | 0.001983 | 9.967e-01 | 0.0009 |
| 537 | -96702.5426861205 | 1.499383e+00 | -2.197284 | 0.403122 | 0.002553 | 9.574e-01 | 0.0048 |
| 538 | -116077.8271298417 | 1.599439e+00 | -2.637531 | 0.782588 | 0.001856 | 9.755e-01 | 0.0001 |
| 542 | -348123.2205029128 | 2.797747e+00 | -7.910086 | 0.350062 | 0.003601 | 7.979e-01 | 0.0015 |
| 543 | -412753.3528290354 | 3.131504e+00 | -9.378618 | 0.967653 | 0.001228 | 9.065e-01 | 0.0002 |
| 553 | -528811.3075335941 | 3.730840e+00 | -12.015697 | 0.176770 | 0.011159 | 2.698e-01 | 0.0135 |
| 555 | -644717.2577679961 | 4.329391e+00 | -14.649322 | 0.810124 | 0.022160 | 8.725e-01 | 0.0058 |

At h = 0.8 the same pattern holds (nearest 151598.9150119515, rel 2.171264e-01, g_grad 0.040956).

## B. Overlaps and multiplicity

The only eigenvalue within a factor 2 of 193644.18 is the quasi-TEM mode itself
(148241.5356985919 at h = 0.4; 151598.9150119515 at h = 0.8). Its squared cosines: `span(Z)`
(gradient range) 0.046745 -> projection norm **0.2162** (which is exactly `h040.json physical.projZ`),
`span(Z_sub)` 0.032447 -> 0.1801, node block 0.2298 -> 0.4793; `cos^2` with the TEM mode 1.0000.

Two-point multiplicity check: the count is **0 at both meshes**, so the ratio to `dim span(Z)`
(324 -> 84, ratio 3.857) and to `n_e` (1262 -> 319, ratio 3.956) is **0 : 0 — undefined**. There is
no eigenspace to dimension. Answer to the classification question: **none** — not gradient range,
not solenoidal complement, not the node block; the object does not exist in this spectrum.

## Scope, and why the same state turns up in another artefact

`eps_r k0^2` *is* an eigenvalue in the record, five times over, and it does not contradict the audit
above: it is a state of the **transverse** pencil, which is a different operator. The transverse pencil
is `emfit/mode2d.py:981-989` — `c = (k0 * k0 * m_eps - k_q).tocsr()`, `b = m_mu.tocsr()`, free
blocks at `:983-984`, `eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")`, residual at `:1086`
`be = b_free @ v` — the edge block alone, with no node block and no Schur complement. The mixed
pencil is `:1951-1966` — `h = k_zz - k0^2 m_zz` on the free nodes, `splu`, `d_dense`, `a_dense`,
`b_dense = m1_f - (c_f @ d_dense) @ c_f.T`, `_dense_eig`. In the transverse pencil a gradient field
`g` has `K_q g = 0` exactly, so the pencil collapses to `k0^2 m_eps g = beta^2 m_mu g` and with
`eps = eps_r = 4.4`, `mu = 1` the eigenvalue is `beta^2 = eps_r k0^2` with no reference to the box
closure; a `curl_ratio` of `1e-10` is that statement measured.

The two occurrences are two boxes and two engines, neither a refinement of the other.
`evidence/matrix_audit/d585_clearance1.0_modal.json` (246 DOF, 10 x 8 cells, `clearance 1.0`,
`engine deflated`, `sigma 197517.0654276619` = `1.02 * eps_r k0^2`, `n_candidates 16`, `chosen 1` ->
`beta 364.2590740103016`, `curl_ratio 3544.4`) carries the state once, as mode 0:
`beta 440.050203717505`, `beta_sq 193644.18179181765`, `curl_ratio 1.44e-22`,
`eps_eff 4.3999999999998245`, `is_builtin_pick False`. The clearance-3.0 arpack run (1262 DOF,
26 x 16, `sigma 178152.6472484794` = `0.92 * eps_r k0^2`, `n_candidates 6`) carries it five times. The
multiplicity tracks the size of the discrete gradient range at each box — one direction at 246 DOF,
at least five at 1262 DOF — and the five is capped by `k = 6`. The shift is deliberate rather than
coincidental: `solve_arpack` takes `shifts = (1.02, 1.06, 0.92)` (`tools/d585_modal.py:254`,
`ER_DEF = 4.4` at `:61`) times `eps_r k0^2`. `.scratch/` is scratch and uncommitted, so
`.scratch/d5854a/modal.json` is a working artefact, not durable evidence: regenerate it with
`tools/d585_modal.py` at `h = 0.4` mm, `clearance = 3.0`, `sigma_mult 0.92`.

## The five modes in `.scratch/d5854a/modal.json` are the transverse cluster, not a contradiction

Five, not one, because the discrete gradient range in an ungauged edge space is not a single direction:
the five `beta^2` agree to `3e-11` relative, so they are one degenerate cluster and `eigsh` returns as
many of them as the requested subspace allows [M]. The shift `178152.6472` sits `35491.53` away in
`lambda` from `193644.1818` and `29911.11` away from the condensed quasi-TEM mode at `148241.5357`, so
the two are only a factor `1.19` apart in `|1/(lambda - sigma)|`: with six slots and five degenerate
cluster members, five slots go to the cluster and one to the mode [M].

The solver's own guard already refuses the cluster. `emfit/mode2d.py:1034` is
`passes = (np.abs(curl) >= _CURL_RATIO_MIN) & (eps_eff < eps_max - _EPS_EFF_RTOL)` with
`_CURL_RATIO_MIN = 1.0e-6` (`:164`) and `_EPS_EFF_RTOL = 1.0e-6` (`:165`), and
`eps_eff = beta_sq / (k0 * k0)` at `:1141`: a `curl_ratio` of `3e-10` is four orders below that floor,
and `eps_eff` within `1.5e-13` of `eps_r` is *above* `eps_max - 1e-6`, so both limbs fail. That is why
`physical` is `True` (the `1.0 < e_eff < er` test at `tools/d585_modal.py:247` cannot resolve the
difference at that tolerance) while `is_builtin_pick` is `False`; the guard docstring at `:1027-1031`
says as much outright, that the caller should be able to see "whether the shift returned gradient
states only".

In the mixed pencil the same content is not free: `b_dense = m1_f - c_f h^-1 c_f^T` adds a term on
`range(C_f^T)` that the transverse pencil does not have, and the measured consequence is the
condensed pencil rebuilt and re-solved densely with `dggev`
(`evidence/matrix_audit/stage3_k0sq_classify.py`): 1262 eigenvalues in 91.42 s at `h = 0.4` and 319
in 7.71 s at `h = 0.8`; 0 within `1e-2`, 0 within 5 % and 0 within 10 % of `193644.18` at both
meshes, the nearest being the quasi-TEM mode `148241.5356985919` and `151598.9150119515` (relative
`2.34e-1` and `2.17e-1`) [M]. Absent from the condensed pencil, present by construction in the
transverse one.

**What the overlaps say, and one number that reconciles.** The quasi-TEM eigenvector's squared
cosine with `span(Z)` is `0.046745`, so its projection norm is `0.2162` — exactly `h040.json`
`physical.projZ` — while `projZperp 0.9763` is `sin(theta) = sqrt(1 - 0.046745) = 0.97635`:
`projZ` is a projection *norm*, not a squared cosine, so the two are not required to sum to 1. The
same eigenvector has squared cosine `0.032447` with the 81 substrate-gradient columns and `0.2298`
with the node block: the three decompositions are of one state and none of them makes it a gradient
state. That check used a `span(Z)` rebuilt rather than read — 324 air columns (rank 324) plus 81
substrate columns (rank 81), union 405 — reproducing `h040.json` `gradient.info` (`columns_v1 324`,
`columns_added 81`, `z_dim_v2 405`) and the `84 / 14 / 98` of the same field at `h = 0.8`. One
correction to the earlier "gradient subspace is not invariant" statement: that measurement covered
the 324 air columns only, while an `eps_r k0^2` state is a gradient field living in the substrate
block where `eps = eps_r`; it was measured anyway, `g_sub <= 0.032` for every candidate, so the
omission did not hide the family [M].

## One thing this does not settle

`.scratch/d5854a/modal.json` entry 2 is a `validate` record and it does not agree:
`beta_dense 385.021474334043` against `beta_arpack 408.9721637956313`,
`rel_diff 0.06220611331618553`, `agree False`. The dense number is the quasi-TEM mode and is confirmed
twice over — this file's `148241.5356985919` -> `385.021474334`, and §160's unreduced-pencil
`148241.5356984517` -> `385.021474334` — while the arpack number (`eps_eff 3.800456`,
`curl_ratio 10751.1`) is the candidate the `0.92` shift actually picks, `6.22 %` high [M]. Nothing here
decides which is right for that box. The subspace budget explains the *silence* rather than the
number: with five of six slots spent on the degenerate cluster, `385.02` is not among the six
candidates at all, so the `validate` failure is a statement about `k = 6` at a shift parked between the
two values, not about the discretisation [M].

## 213.747 is the FDTD wavenumber

`213.74739982558222` is not the modal k0. `tools/host_ladder.py:1060` states the pair verbatim
(`k0_actual/k0_requested = 213.747400/209.785703 = 1.0188875`); `evidence/box_sweep/SUMMARY.md:58`
records it as the FDTD invariant, and older *modal* evidence reused it as `K0`
(`evidence/strip_width/_make_EIG_strip_width.py:16`, `evidence/h_refine/h040.json:121`,
`evidence/rung_c/h020.json:151`, `evidence/stations_n18.json:153`). `4.4 * 213.74739982558222^2 =
201164.3` — the owner draft's number is the FDTD k0 fed into a modal identity.

## Reconciles with §160 only if "ker" is read correctly

`ker A = {0}` (A nonsingular, `sigma_min 12890.3`), so no family can be "in ker A". The 429 (110)
ZERO eigenvalues are the **node block** of `K = block_diag([A, 0])` at lambda = 0, not a gradient
nullspace. A gradient-nullspace family at `k0^2` would have to appear as *finite* eigenvalues;
none does (0 within 1e-2 of 44010.04).

## What this does not establish

It does not show that eps_r k0^2 states are absent from the *continuous* problem, nor from other
boxes (they demonstrably exist at clearance 1.0), nor that the deflation predicate is wrong for
those boxes. The 5 clearance-3.0 entries in `.scratch/d5854a/modal.json` are identified in
`## The five modes` above: they are the gradient cluster of the transverse pencil,
`curl_ratio <= 6.5e-10` and `eps_eff = eps_r` to 13 digits, rejected by the
mode-eligibility guard at `emfit/mode2d.py:1034`. It does not touch `residual_eps_mu ~0.0216`, the FDTD half, or the C++/T4 paths. Complex
eigenvalues (98 of 1262 with `abs(Im)/abs(Re) > 1e-6`, max 2.46e-4) mean "exact" must be read as
"within QZ noise"; every count above is far outside that noise. Overlap metrics are Euclidean and
the node metric is not orthogonal to the edge metric, so `g_grad + g_node` need not equal 1.
