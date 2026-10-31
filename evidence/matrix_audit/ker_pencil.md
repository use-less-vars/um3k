# `ker(K)` in the full 2x2 block pencil: ZERO or INFINITE?

Task C of the audit follow-up. The question: in the pencil `K x = lambda M x`
that `tools/host_ladder.route_c` forms, does `ker(K)` produce ZERO
eigenvalues, or INFINITE ones (i.e. does it also lie in `ker(M)`)? And is
`ker(M)` trivial?

**Answer, in one line: ZERO, with multiplicity `n_n` (= 429 at `h = 0.4` mm,
110 at `h = 0.8` mm), and `ker(M) = {0}` — the pencil is regular.**

Harness: `evidence/matrix_audit/ker_pencil_harness.py` (new, self-contained,
re-runnable from the tree; cache under `.scratch/kerpencil`, no `/tmp`, no host
paths).

```sh
python3 evidence/matrix_audit/ker_pencil_harness.py --h 0.4 --stage struct  # 121 s
python3 evidence/matrix_audit/ker_pencil_harness.py --h 0.4 --stage qz      # 206 s
python3 evidence/matrix_audit/ker_pencil_harness.py --h 0.8 --stage probe   #  88 s
python3 evidence/matrix_audit/ker_pencil_harness.py --h 0.8 --stage struct  #  21 s
python3 evidence/matrix_audit/ker_pencil_harness.py --h 0.8 --stage qz      #  35 s
```

## Method

The pencil is not re-derived. The blocks are `build_modal`'s own, and `K`, `M`
are assembled exactly as `tools/host_ladder.py:556-558` does it:

```python
KC = sp.block_diag([pb["A"], sp.csc_matrix((n_n, n_n))], format="csc")
MC = sp.bmat([[pb["m1_f"], (-pb["c_f"]).tocsc()],
              [(-pb["c_f"].T).tocsc(), pb["h"]]], format="csc")
```

with `A = 0.5*(a + a^T)`, `a = k0^2 m_eps - k_q`, and `h = k_zz - k0^2 m_zz`.
Dense `K`, `M` are then `KC.toarray()`, `MC.toarray()`; the harness asserts the
sparse and dense pencils agree to round-off (the two differ only in summation
order — `dK = 1.4e-13`, `dM = 0` absolute on the column/row sums).

Three stages, deliberately separated so no expensive step can block a cheap
one:

- `probe` — build the sparse blocks only; smallest singular values via
  `scipy.sparse.linalg.svds(..., which='SM')`, with a dense cross-check where
  the block is small enough (<= 500).
- `struct` — `rank`/`sigma_min` of `A` and `h` by `svdvals`; `rank`,
  zero-pivot count, pivot ratio and `slogdet` of `M` by `lu_factor`; the exact
  zero block of `K`; then cache `K, M, A, c, m1, h` as `.npy`.
- `qz` — dense QZ (`scipy.linalg.eig(K, M, homogeneous_eigvals=True)` →
  LAPACK `dggev`) on the **unreduced** pencil, per-eigenpair normalised
  residuals, the condensed-pencil cross-check, the quasi-TEM locate and the
  shift-invert separation sweep.

Why `lu_factor` and not `svdvals` for `M`: a dense SVD of the 1691^2 pencil
costs ~90 s in this container (measured: `svdvals` on 1262^2 = 90.8 s) and `K`
is singular by construction, so its `sigma_min` is exactly 0 and says nothing.
`svds(which='SM')` on the full pencil did **not** converge (verbatim:
`ArpackNoConvergence: ARPACK error -1: No convergence (20001 iterations, 0/1
eigenvectors converged)` for `A`, `M_full`, `K_full` at `h = 0.8`), so the
smallest singular value of `M` is reported from the dense SVD at the small mesh
(429^2, affordable) and from LU pivots at both meshes.

## Exact build calls

| `h` (mm) | call |
|---|---|
| 0.4 | `hl.build_modal(h_m=0.0004, clearance=3.0, n_strip=2, w_m=0.0008, k0=209.78570331727553)` |
| 0.8 | `hl.build_modal(h_m=0.0008, clearance=3.0, n_strip=1, w_m=0.0008, k0=209.78570331727553)` |

`k0 = 209.78570331727553` is §158.5's value (`evidence/matrix_audit/h040.json`),
kept fixed so the two meshes differ only in `h`.

## Table 1 — meshes

| `h` mm | `nz_sub` | `cell` m | `n_strip` | ny x nz | fingerprint | `n_e` | `n_n` | `n_dof` | `t_build` | `fp`, shape-free (`mesh_ladder.md:26`) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.4 | 4 | 4.0e-4 | 2 | 26 x 16 | `6114305c100a54e7` | 1262 | 429 | 1691 | 0.006 s | `2531f1bd3b2d0c89` |
| 0.8 | 2 | 8.0e-4 | 1 | 13 x 8 | `5ec7a255dbe7bd68` | 319 | 110 | 429 | 0.060 s | `ac9eaef3f69c5d10` |

Fingerprint = sha1 over `nodes|edges|tris` (shapes included), first 16 hex
chars — the B3 convention. That convention is **not** comparable with the
shape-free digest defined at `evidence/matrix_audit/mesh_ladder.md:26` (first
16 hex of `sha1(nodes.tobytes() + edges.tobytes() + tris.tobytes())`, no shape
prefix). The last column is that ladder definition *recomputed* on these two
meshes: `2531f1bd3b2d0c89` at `h = 0.4` and `ac9eaef3f69c5d10` at `h = 0.8`,
which are the ladder's own values at `mesh_ladder.md:99` and `:86`, on meshes
whose `n_nodes`/`n_tris` are 459/832 and 126/208 as those rows record — the
meshes here are byte-identical to the ladder's, and only the digest definition
differs. `build_modal` itself is milliseconds; the cost of this whole exercise
is dense linear algebra, not assembly.

## Table 2 — the block facts (Step 1)

| quantity | `h = 0.4` | `h = 0.8` |
|---|---|---|
| `rank(A)` / `A.shape` | 1262 / 1262 | 319 / 319 |
| `sigma_max(A)` | 7.4746e7 | 1.8512e7 |
| `sigma_min(A)` | 12890.306 | 12890.629 |
| `cond(A)` | 5798.6 | 1436.1 |
| `h` shape / `rank` | 429 / 429 | 110 / 110 |
| `sigma_max(h)` | 7.9337 | 7.7419 |
| **`sigma_min(h)`** | **3.6838e-3** | **1.4130e-2** |
| `cond(h)` | 2153.7 | 547.9 |
| bottom `n_n` rows of `K` exactly zero | yes (`nnz = 0`) | yes (`nnz = 0`) |
| `rank(K)` | 1262 | 319 |
| **`dim ker K`** | **429** | **110** |
| `M` shape | 1691 | 429 |
| `rank_lu(M)` / zero pivots | 1691 / **0** | 429 / **0** |
| `min|pivot|` / `max|pivot|` | 4.5445e-4 / 0.84851 | 1.8178e-3 / 0.84530 |
| pivot ratio | 5.356e-4 | 2.150e-3 |
| `slogdet(M)` sign / `log|det|` | −1 / −3254.463 | +1 / −702.952 |
| **`sigma_min(M)`** (dense SVD) | not measured (90 s) — see limit | **4.7024e-4** |
| `sigma_min(K)` (dense SVD) | 0 by construction | **0.0** (measured) |
| `nnz(K)` / `nnz(M)` | — | 1507 / 4499 |

`dim ker K == n_n` is not an estimate: the harness asserts the bottom `n_n`
rows of `K` are exactly zero, so `rank(K) = rank(A) = n_e` and
`dim ker K = n_dof - n_e = n_n` exactly.

`sigma_min(M) = 4.7e-4 > 0` and 429 (1691) LU pivots all exceed
`max|pivot| * n * eps` by a factor ~1e9, and `log|det| = -3254.46` (i.e.
`|det| ~ 10^-1414`, non-zero) — so **`M` is nonsingular at both meshes and
`ker(M) = {0}`**.

## Step 2 — the algebra, stated before the measurement

For `x in ker K` (i.e. `x = [0; y]`, `y in R^n_n`) the pencil `K x = lambda M x`
reads `0 = lambda M x`. Hence for each such `x` exactly one of two things is
true: if `M x != 0` then `lambda = 0`; if `M x = 0` then the pair is `0/0` — an
*indeterminate*, not an eigenvalue, and the pencil is **singular** (every
`lambda` solves it).

`M [0; y] = [-c_f y; h y]`. So `M x = 0` requires both `c_f y = 0` and
`h y = 0`, i.e. `y in ker(h) ∩ ker(c_f)`. With `sigma_min(h) > 0` (`h`
nonsingular: 3.68e-3 at `h = 0.4`, 1.41e-2 at `h = 0.8`), `ker(h) = {0}` and
therefore `ker K ∩ ker M = {0}`.

Prediction, before measuring: **`lambda = 0` with multiplicity exactly `n_n`
(429 / 110), zero INFINITE eigenvalues, zero `0/0` pairs, `ker(M) = {0}`, and
the pencil is regular** (a pencil is singular iff `det(K - lambda M)` vanishes
identically; `ker K ∩ ker M = {0}` plus `ker M = {0}` rules out the only route
to that, and `det(M) != 0` makes it a standard eigenproblem `M^-1 K`).
Counting: `n_n` zeros plus the `n_e` other eigenvalues `= n_dof`, so the
remaining `n_e` eigenvalues must be the `n_e` eigenvalues of the condensed
pencil `(A, m1_ff - c_f h^-1 c_f^T)` — which is what `mode2d`'s dense path
solves.

## Table 3 — the QZ counts (Step 3), unreduced pencil

| quantity | `h = 0.4` (1691) | `h = 0.8` (429) |
|---|---|---|
| `t_dggev` | 126.1 s | 13.1 s |
| `n` | 1691 | 429 |
| **ZERO** (`|lambda| <= 1e-10*max|lambda_finite|`) | **429** | **110** |
| finite non-zero | 1262 | 319 |
| **INFINITE** (`beta == 0`, `alpha != 0`) | **0** | **0** |
| **`0/0` / singular** (`beta == alpha == 0`) | **0** | **0** |
| other non-finite | 0 | 0 |
| `scale = max|lambda_finite|` | 2.247952164e8 | 5.604773025e7 |
| `tol_abs` at `1e-10 * scale` | 2.24795e-2 | 5.60477e-3 |
| zero count at `1e-8 / 1e-10 / 1e-12 * scale` | 429 / 429 / 429 | 110 / 110 / 110 |
| `max|lambda|` among zeros | 6.5221e-7 | 2.8108e-8 |
| `median|lambda|` among zeros | 1.7516e-9 | 2.4433e-10 |
| finite: `|lambda|` min / median / max | 34830.2 / 7.2208e7 / 2.24795e8 | 36734.3 / 1.8136e7 / 5.60477e7 |
| `max` relative imaginary part among finite | 0.0171 | 0.0288 |

The separation is not a tolerance artefact: the largest zero is `6.5e-7` and
the smallest non-zero is `3.5e4` — **11 orders of magnitude**, at every
tolerance from `1e-8` to `1e-12` of the scale, and 429/110 is exactly `n_n`.

## Table 4 — residual classification (absolute threshold `t = 1e-10`)

Residuals are per-eigenvector: `rK = |K v| / (|K|_F |v|)`,
`rM = |M v| / (|M|_F |v|)`; class "tiny" means `<= t`. No median-relative rule
anywhere.

| class | `h = 0.4` | `h = 0.8` |
|---|---|---|
| both tiny (`0/0` candidate) | **0** | **0** |
| `|Kv| ~ 0` only (ZERO) | **429** | **110** |
| `|Mv| ~ 0` only (INFINITE) | **0** | **0** |
| neither (regular finite) | **1262** | **319** |
| `max rK` among `|Kv|`-tiny | 1.8600e-16 | 1.6511e-16 |
| `min rM` among `|Kv|`-tiny | 9.4644e-4 | 4.7951e-3 |
| `min max(rK, rM)` among regular | 2.0968e-5 | 1.5047e-4 |
| `max rK` among regular | 5.9017e-2 | 1.1595e-1 |
| `|lambda|` max / median among `|Kv|`-tiny | 6.52e-7 / 1.75e-9 | 2.81e-8 / 2.44e-10 |

The two rules agree exactly: of the 429 (110) pairs the pencil rule calls ZERO,
429 (110) have `|Kv| <= 1e-10` and `|Mv| >> 1e-10`; **none** of them has both
residuals tiny, and **none** is classified infinite. The 16-digit `rK` and the
4-3-digit `rM` are a gap of 12+ orders — the kernel vectors are annihilated by
`K` to machine precision and emphatically *not* by `M`.

## Table 5 — the finite spectrum is the condensed pencil, and where the mode sits

| quantity | `h = 0.4` | `h = 0.8` |
|---|---|---|
| full finite count vs condensed count | 1262 vs 1262 | 319 vs 319 |
| `max` relative difference | 3.4951e-11 | 5.4335e-13 |
| median relative difference | 8.6726e-15 | 4.9165e-15 |
| pairs above `1e-8` | 0 | 0 |
| quasi-TEM index | 573 | 145 |
| quasi-TEM `lambda` | 148241.5356984517 | 151598.91501195726 |
| quasi-TEM `beta = sqrt(lambda)` | 385.02147433416195 | 389.3570533738374 |
| rel. difference vs §158.5's `h040` `lambda` | 7.83e-14 | 2.26e-2 |
| `rK` / `rM` of the mode | 6.06e-5 / 4.90e-3 | 5.57e-4 / 1.13e-2 |
| residual class | regular | regular |
| nearest *other* finite eigenvalue gap | 183072 | 188333 |

So the quasi-TEM mode is a **regular finite** eigenpair in the unreduced
pencil, `385.0215` against Hammerstad `377.3434` (+2.03%) at `h = 0.4`, and it
sits `1.8e5` away in `lambda` from anything else — it is not near the kernel
family (distance to the zeros: `1.48e5`).

## Table 6 — separability under a shift-invert search (Step 4)

Shift-invert `LM` at `sigma = m * lambda_TEM` ranks eigenpairs by
`|1/(lambda - sigma)|`; the kernel family sits at `lambda = 0`, so its
magnitude is `1/sigma` and the mode's is `1/|lambda_TEM - sigma|`. Both meshes
give the same table (the shift is defined from the `h040` value):

| `m` | `sigma` | kernel / mode magnitude | kernel vectors in top-16 | rank of the mode |
|---|---|---|---|---|
| 0.30 | 44472.5 | **2.333** | **16 / 16** | 430 (`h040`) / 111 (`h080`) |
| 0.70 | 103769.1 | 0.429 | 15 / 16 | 0 |
| 0.76 | 112663.6 | 0.316 | 15 / 16 | 0 |
| 0.90 | 133417.4 | 0.111 | 15 / 16 | 0 |

Read plainly: **below the mode** (`sigma < lambda_TEM`) the 429 (110) kernel
directions are *louder* than the mode — they are the strongest 16 vectors the
search can return, and the mode is pushed to rank 430 (111). Above the mode
the mode wins, but 15 of the 16 returned vectors are still kernel junk. The
kernel family is therefore **not** separable from the mode by an eigenvalue
magnitude criterion in a shift-invert search on the unreduced pencil: deflation
(or the condensed form, which has no kernel at all) is mandatory. The mode is
separable *from the zeros themselves* (`1.5e5` vs `<= 6.5e-7`), which is why a
correct `lambda != 0` filter recovers it perfectly — the danger is only the
`LM` ranking, which picks `1/sigma` junk.

## Verbatim key output (`h = 0.4`)

```json
"counts": {"n": 1691, "zero": 429, "finite_nonzero": 1262, "infinite": 0,
           "zero_over_zero_singular": 0, "nonfinite": 0,
           "max_rel_imag_of_finite": 0.01708447152414642},
"residual_classes": {"both_tiny_0_0": 0, "k_only_zero_eigenvalue": 429,
                     "m_only_infinite_eigenvalue": 0,
                     "neither_finite_regular": 1262,
                     "max_rK_among_k_only": 1.8599896729624086e-16,
                     "min_rM_among_k_only": 0.0009464422373026602},
"M_LU": {"shape": [1691, 1691], "rank_lu": 1691, "n_zero_pivots": 0,
         "pivot_ratio": 0.0005355855439227237, "det_sign": -1.0,
         "log_abs_det": -3254.4629619168018},
```

and `h = 0.8`:

```json
"counts": {"n": 429, "zero": 110, "finite_nonzero": 319, "infinite": 0,
           "zero_over_zero_singular": 0, "nonfinite": 0,
           "max_rel_imag_of_finite": 0.028768014245677227},
"M_full": {"which": "SM",
           "error": "ArpackNoConvergence: ARPACK error -1: No convergence (20001 iterations, 0/1 eigenvectors converged)",
           "sigma_min_dense": 0.00047023652236079244},
```

## What this does not establish

It does not measure `sigma_min(M)` at `h = 0.4` directly: a dense SVD of the
1691^2 `M` is ~90 s here and ARPACK's `which='SM'` failed to converge on it, so
`ker(M) = {0}` at the big mesh rests on the 1691 LU pivots (all non-zero, ratio
5.36e-4, `|det| ~ 10^-1414`), which is a nonsingularity *certificate* but not a
condition number; the small mesh (429) does have the dense number, `4.7024e-4`,
and both meshes agree in kind. It says nothing about meshes other than
`h = 0.4` and `h = 0.8` mm with this `k0`, this clearance (3.0) and this strip
(`w_m = 8e-4`, `n_strip = 2` and `1`) — the two `n_strip` values differ, so the
two columns are two different meshes, not a refinement of one, and the
`+2.26%` shift of the mode between them is a discretisation effect that this
entry does not attribute. It does not prove that `h` stays nonsingular at
*every* mesh: the argument only needs `sigma_min(h) > 0`, which is measured,
not guaranteed. It does not run a shift-invert `eigsh` on the sparse pencil —
the separation table is computed from the exact dense spectrum, so it is a
statement about the criterion `|1/(lambda - sigma)|`, not about what any
particular solver returns in practice (iteration counts, deflation
thresholds, restart policy are all absent). It does not touch `mode2d`: that
`mode2d` never forms this pencil is a reading of `emfit/mode2d.py:1940-1966`
and `_MIXED_DENSE_MAX` at `:185`, and no `mode2d` run is executed here. Nor is
§158.5's `ZERO 0` evidence about the unreduced pencil: that `dggev` run
(`evidence/matrix_audit/h040.json` — its `t_sym` `17.49 s` entry and its
`classes` counts) was over the *condensed* 1262 pencil, and a 1262-dimensional
problem cannot contain the 429 zeros by construction, so its zero count was
fixed at 0 before it ran and it agrees with Table 3 only on the finite
spectrum (the `3.5e-11` match of Table 5).
The `dggev` eigenvalues are what LAPACK returns for a backward-stable reduction;
the 429 (110) zeros are exact to `6.5e-7 / 2.2e8 = 3e-15` relative, but the
`1262` finite ones carry ordinary QZ error (`max rK` among regular `5.9e-2`,
which is measurement noise on a heavily non-normal pencil, not a claim that
those eigenpairs are wrong).
