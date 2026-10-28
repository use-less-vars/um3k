# Sparse eigenmode solve for the mixed formulation (design pass)

Design note only. No code is changed by this note; every recommendation below is
unanchored until it is implemented and gated.

> **ERRATUM (measured, see section 4.2).** The enlarged pencil of section 4,
> `K = [[A, -c], [-c^T, h]]`, `M = diag(m1_f, 0)`, does **not** condense to the
> code's pencil. Its `w`-elimination gives `(A - c D c^T) x = lambda m1_f x` — a
> different problem — and at `sigma = 1` it returns `lambda = 26953.0` instead of
> `9.78e4`. The corrected enlargement keeps the rank-one term on the **mass**
> side; it is derived, measured and benchmarked against a dense shift-invert in
> **section 4.2**, which supersedes section 4 as an implementation recipe.
> Section 4 is left standing as the record of the defect.
>
> **PRIMARY RECOMMENDED PATH — the mass-side enlargement of section 4.2 (route
> C).** What this note recommends is `K_C = [[A, 0], [0, 0]]`,
> `M_C = [[m1_f, -c], [-c^T, h]]`, shifted as
> `[[A - sigma m1_f, sigma c], [sigma c^T, -sigma h]]` and solved by shift-invert
> through an explicit `LinearOperator` for `(K_C - sigma M_C)^{-1} M_C` (section
> 6). Its `y`-elimination is `sigma`-free, so it condenses to the code's own
> `A x = lambda (m1_f - c D c^T) x`; it is **MEASURED** to reproduce the dense
> reference `beta^2` on both audit rungs (12.2 / 12.5 digits, section 4.2), and
> its factorisation is sparse and cheap.
>
> **DEMOTED — section 4's stiffness-side enlargement is a REJECTED VARIANT.**
> Its `w`-elimination lands the rank-one term on the stiffness side and condenses
> to `(A - c D c^T) x = lambda m1_f x`, which is not the code's pencil; measured,
> it returns `lambda = 26953.0` against a reference `97833.1` at `sigma = 1`, and
> is still `+0.54 %` off with the shift moved onto the target, at
> `abs(corr_ey) = 0.55` against `0.92`. It is kept as the record of the defect and
> as the cost reference in section 5.2, not as a recipe.
>
> **LABELS.** Three labels are used below and they are never interchangeable:
> **MEASURED** = produced by a run recorded in the evidence file;
> **EXTRAPOLATED** = a two-point power-law projection through the measured rungs
> `sc = 12, 16`, *not* a measurement; **ESTIMATED** = arithmetic or inherited. In
> particular the `0.0843 GB`, the `0.156 s` and the `n = 40021` in section 4.2 are
> **EXTRAPOLATED**: they were not measured at the target mesh, and not at ladder
> rung 4.

## 1. Scope, and what this note is not

`solve_modes_mixed` (`emfit/mode2d.py:935`) currently has exactly one working
path: assemble, condense the longitudinal block densely, and hand the resulting
`beta^2`-pencil to a dense QZ solve. The iterative path is a stub that raises
(`emfit/mode2d.py:1095-1099`). This note asks what a sparse path would have to
be, and what it would cost, on the meshes the audit actually wants.

This note **is**: a statement of the pencil the code builds (section 3), a
derivation of an equivalent *sparse symmetric* pencil (section 4) and of its
corrected **mass-side** form (section 4.2, route C), which is the note's primary
recommendation, measured factorisation statistics for **both** pencils on the
audit mesh and on the target 201x77 mesh (section 5), a reading of the documented
`scipy.sparse.linalg` contracts against those pencils (section 6), and the
consequences for result semantics (section 7).

This note **is not**: an implementation, an accuracy claim, a convergence study,
or a decision about which mode the audit should report. No `eig`/`eigsh`/`eigs`
call was made while producing it; every number below comes from assembly,
Cholesky, `splu` and triangular solves.

## 2. The problem, measured

The dense path is a `scipy.linalg.eig` (QZ) call on a `n_e x n_e` pair
(`emfit/mode2d.py:1120`), reached by explicitly densifying three matrices
(`emfit/mode2d.py:1114-1116`): `d_dense = lu_h.solve(np.eye(n_n))`,
`a_dense = k0*k0*m_eps_f.toarray() - k_q_f.toarray()`,
`b_dense = m1_f.toarray() - (c_f @ d_dense) @ c_f.toarray().T`. `_MIXED_DENSE_MAX
= 3000` (`emfit/mode2d.py:151`) exists because of this cost; `c1_audit.py:395-398`
turns the limit into a `SystemExit`.

Two meshes matter.

* **Audit mesh (banked).** `strip_cells = 12`, ZS `[8,4,4]`: 527 nodes, 960
  triangles, 1486 edges, `free_e = 1444`, `free_n = 483`. Runs today; this is the
  mesh the dense path has actually been exercised on. **MEASURED.**
* **Target mesh.** `strip_cells = 182`, ZS `[38,19,19]` = 201x77 nodes: 15477
  nodes, 30400 triangles, 45876 edges, `free_e = 45494`, `free_n = 15093`,
  `n_dof = 60587`, assembly 0.1 s. **MEASURED.**

The dense cost on the target mesh is disqualifying: one dense `float64` matrix
of order 45494 is 16.7 GB, and the QZ work scales as `n^3`, i.e.
`(45494/1444)^3 ~ 3.2e4` times the audit-mesh cost — of order 41 days. Both are
**ESTIMATED** (inherited from the prior-session note `.scratch/logs/s10118_d.py:11`;
they are arithmetic on the measured orders, not timings).

A useful scale check from the audit mesh itself: `max|A|` grows from 2.66e7
(`sc=4`) to 3.20e8 (`sc=48`) while `max|B|` stays 0.745 -> 1.82, so the `A/B`
scale ratio grows roughly like `h^-2`. Any residual or convergence test on this
pencil must be scale-aware, as the dense path already is
(`emfit/mode2d.py:1126-1148`, `denom_scale = norm_a + |lam|*norm_b`). **MEASURED.**

## 3. The pencil the code builds, and the two properties that block ARPACK

After the PEC masks (`emfit/mode2d.py:1095-1101`) and the sub-blocks
(`emfit/mode2d.py:1105-1113`) the code forms, on the reduced pencil

```
A x = beta^2 B x,     A = k0^2 M_eps - K_q,     B = m1 - c D c^T,   D = h^{-1}
```

(`emfit/mode2d.py:1006-1008`, repeated at `:1115-1116`), with
`h = k_zz - k0^2 m_zz` factorised by `splu` (`emfit/mode2d.py:1113`).
`m1`, `m_eps`, `k_q` and `h` are `assemble`/`assemble_mixed` outputs
(`emfit/mode2d.py:397`, `:469`; blocks restricted at `:1105-1113`).

Two structural facts, both measured on every rung `sc = 4,12,24,48`:

1. **`B` is genuinely indefinite.** `cholesky(B)` raises `LinAlgError` on every
   rung. This is what the code already says in prose
   (`emfit/mode2d.py:144-149`: "B = m1 - C D C^T is strongly indefinite (565 of
   1592 eigenvalues negative on the parallel-plate mesh), so ||B x|| is not a
   valid denominator") and in the solver choice
   (`emfit/mode2d.py:1010-1016`: "`scipy.linalg.eigh` is not applicable; the
   dense path uses `scipy.linalg.eig` (QZ)"). `m1_f` and `h` are both SPD on all
   rungs; `A` is not SPD. **MEASURED.**
2. **There is no sparse `A - sigma B`.** `A - sigma B` is dense through
   `c D c^T` (`emfit/mode2d.py:1085-1090`), so the shift-invert route used by the
   single-component solver (`emfit/mode2d.py:868`,
   `eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")`) has nothing to
   factorise. The dense path materialises `D = lu_h.solve(np.eye(n_n))` — a dense
   `free_n x free_n` matrix — to get there (`emfit/mode2d.py:1114`).

A third fact is *good* news and is the hook the sparse path hangs on. Every
block is symmetric, exactly, in floating point:
`max|m1_f - m1_f^T| = max|m_eps_f - m_eps_f^T| = max|k_q_f - k_q_f^T| =
max|h - h^T| = 0.000e+00` on all rungs, and `max|A - A^T| = 0.0` exactly. The
only asymmetric ingredient is `c D c^T`, and even that is symmetric to
roundoff: `max|B_raw - B_raw^T| = 4.3e-15, 5.5e-15, 2.3e-14, 1.4e-13` for
`sc = 4,12,24,48`. So the existing `0.5*(X + X^T)` symmetrisation
(`emfit/mode2d.py:1117-1118`) is cleaning up roundoff, not an asymmetry of the
discretisation. **MEASURED.**

## 4. The enlarged sparse pencil — stiffness side: REJECTED

> **Status: REJECTED VARIANT.** The enlargement below is *not* the recommended
> pencil. It puts the rank-one term on the stiffness side, so it condenses to
> `(A - c D c^T) x = lambda m1_f x` rather than to the code's
> `A x = lambda (m1_f - c D c^T) x`, and measured it returns `lambda = 26953.0`
> where the reference is `97833.1`. The primary recommendation is the mass-side
> enlargement of **section 4.2** (route C). This section is kept as the record of
> the defect, and its matrix pattern is the cost reference used in section 5.2.

Eliminating the longitudinal block is what forces density. Do not eliminate it.
Reinstate the second unknown and keep both matrices sparse:

```
K = [[ A,      -c ],        M = [[ m1_f, 0 ],
     [ -c^T,    h ]]              [ 0,    0 ]]
```

acting on `v = [x; w]`. Then

```
(K - lambda M) [x; w] = [ A x - c w - lambda m1_f x ;  -c^T x + h w ] .
```

Row 2 reads `h w = c^T x`, i.e. `w = D c^T x` (`D = h^{-1}`, the same `splu(h)`
the code already builds at `emfit/mode2d.py:1113`). Substituting into row 1:

```
A x - c D c^T x = lambda m1_f x   <=>   (A - c D c^T) x = lambda m1_f x
                                          A x = lambda (m1_f - c D c^T) x = lambda B x
```

which is exactly the reduced pencil of `emfit/mode2d.py:1006-1008`. So the two
pencils share their finite spectrum, with `w = -y` if `y` is the sign convention
of the elimination. Sign bookkeeping is the only difference; the spectrum is not.

**Infinite eigenvalues.** `M = diag(m1_f, 0)` is singular with null space
exactly `{[0; w]}`: `nullity(M) = free_n`. Hence the enlarged pencil carries
`free_n` algebraically infinite eigenvalues in addition to the `free_e` finite
ones, and `n_dof = free_e + free_n` is accounted for. Measured certificate at
`sc = 12`: `M[x; y] = 0` for `x = -m1^{-1} c y` to `5.568e-18` relative
**MEASURED**; i.e. the null space is exactly the second block, not merely some
subspace.

**Equivalence, measured.** At `sc = 12` with `lambda = 9.7843e4`, random `x` and
`w = D c^T x`, at `sc = 12`:

```
|| (K - lambda M)[x; w] - [(A - lambda B) x ; 0] || / ||ref|| = 7.981e-16
|| h w - c^T x || / || c^T x ||                              = 3.998e-15
```

**MEASURED.** (Measured on the non-symmetric row scaling of section 4.1; algebra
identical.) The residual is at the level of the arithmetic, so the enlarged
pencil is *the same problem*, reshuffled — no approximation is introduced.

**Both matrices are symmetric.** `A`, `c`, `h`, `m1_f` are each exactly
symmetric (section 3), so `K = K^T` and `M = M^T` up to the zeros we insert.
`M` is symmetric **positive semi-definite** (SPD top block, zero bottom block).
Measured: `M v . v >= 0` and `M[0; w] = 0` for all `w`, i.e. the PSD certificate
is the Cholesky success of `m1_f`, which holds on all rungs **MEASURED**.

### 4.1 The shifted matrix

With a shift `sigma`,

```
K - sigma M = [[ A - sigma m1_f , -c ],
               [ -c^T           ,  h ]]
```

is *already symmetric* — no row or column scaling needed, unlike the
`diag(1, -sigma)` scaling that the non-symmetric assembly would require. The
previously measured statement `max|diag(1,-sigma) S - (diag(1,-sigma) S)^T| =
0.000e+00` on every rung and on the target mesh is the same fact viewed through
a diagonal similarity; the symmetric form above states it without the scaling.
`max|S - S^T|` on the *unscaled* non-symmetric assembly is 6.367 / 6.367 / 10.71
/ 21.35 / 44.45 / 88.89 / 29.92 for `sc = 4,12,24,48,100,200,182` — the size of
the asymmetry that row scaling removes. **MEASURED.**

Because `K - sigma M` is symmetric, a *symmetric* factorisation is admissible
(`splu` on the symmetric matrix; `scipy.sparse.linalg.factorized` will pick the
same LU), and — more importantly — `eigsh`'s documented contract becomes
satisfiable (section 6), which it is not for `(A, B)`.

### 4.2 PRIMARY RECOMMENDED PENCIL (measured): Route C, the auxiliary on the mass side

> **Status: PRIMARY RECOMMENDATION.** This subsection, not section 4, is the
> recommended path: route C, the mass-side enlargement, solved by shift-invert
> with an explicit `LinearOperator` (section 6). Note also that the factorisation
> numbers in section 5.2 were measured on section 4's rejected stiffness-side
> matrix, not on `(K_C, M_C)`; they are a cost reference, not this pencil's cost.

Section 4 is wrong as an implementation recipe, and the factorisation numbers in
section 5.2 were measured on the wrong matrix. The substitution there is
`sigma`-free but not *side*-free: eliminating `w` from `K - lambda M` with
`M = diag(m1_f, 0)` gives

```
h w = c^T x  =>  w = D c^T x,
A x - c w = lambda m1_f x  =>  (A - c D c^T) x = lambda m1_f x .
```

That is `(A - c D c^T) x = lambda m1_f x`: the mass matrix is `m1_f`, **not** the
code's `B = m1_f - c D c^T` (`emfit/mode2d.py:1006-1008`). The sentence "which is
exactly the reduced pencil" misreads its own substitution — the rank-one term
landed on the stiffness side. The two pencils do not share a spectrum.

**The defect is large, and it is measured.** Section 4 implemented as written
(`splu(K - M)` at `sigma = 1.0`, `eigsh(K, k=1, M=M, sigma=1, which="LM")`,
`maxiter=5000`, threads = 1, no row scaling), on both audit rungs:

| quantity | rung0 (`sc=12`, `s12_a9_z8-4-4`) | rung1 (`sc=16`, `s16_a12_z10-5-5`) | reference (dense QZ) |
|---|---|---|---|
| `lambda` of section 4's pencil at `sigma = 1` | 26953.009476 | 26953.002674 | 97833.057851 / 97328.308109 |
| `R` of that eigenvector | 1830.467943 | 1930.608798 | 4.048979116 / 3.780331990 |
| mode overlap with the reference mode, `abs(corr_ey)` | 0.363 | 0.369 | 0.921 / 0.938 |

The reference column is the banked `dense_targets` record. An earlier version of
this table printed `97833.057911` (that is route A's eigenvalue, not the
reference) and `R = 3.780331872` (wrong in its ninth digit); both are corrected
here, and the rung-by-rung table below quotes the same banked values.

`sigma = 1` is wrong by 5 orders of magnitude in the shift, and the returned
mode is not the wanted one. Moving the shift onto the target
(`sigma = 0.999 * beta_sq`) does not repair it, because the defect is the
pencil, not the shift: `lambda = 98360.714617 / 98375.319219` (+0.54 % / +1.08 %
off), `R = 5.860010 / 5.874036`, `abs(corr_ey) = 0.55`. **MEASURED.**

#### The corrected pencil

Keep the auxiliary unknown, but couple it on the **mass** side:

```
K_C = [[ A   , 0 ],        M_C = [[ m1_f, -c ],
       [ 0   , 0 ]]               [ -c^T ,  h ]]
```

acting on `z = [x; y]`. Block row 2 of `K_C z = lambda M_C z` reads

```
0 = lambda (-c^T x + h y)   =>   h y = c^T x   =>   y = D c^T x ,   (lambda != 0)
```

— the elimination is **lambda-free**, so it holds for the shifted system as
well. Block row 1 then reads

```
A x = lambda (m1_f x - c y) = lambda (m1_f - c D c^T) x = lambda B x ,
```

which is the code's pencil exactly, for every `sigma`. `K_C` and `M_C` are both
symmetric; `M_C` is symmetric but **indefinite** (it inherits the indefinite
`-c D c^T` block) and nonsingular (nonsingularity measured in section 6c), so the enlarged pencil has no infinite
eigenvalues to filter and `n_dof = free_e + free_n` counts only finite ones.
The shifted matrix

```
K_C - sigma M_C = [[ A - sigma m1_f ,  sigma c ],
                   [ sigma c^T      , -sigma h ]]
```

is **sparse** — it is the entire point of the correction — and has the same
block pattern as section 4.1's `S`, so its fill is the section-5.2 fill with a
better-behaved `A - sigma m1_f` diagonal block.

Consistency of the two unknowns is measurable, not assumed: `x_2 - D c^T x_1`,
relative on `[x; y]`, is `8.09e-12` (rung0) and `2.05e-13` (rung1); the residual
in the enlarged pencil is `2.59e-15` / `8.49e-18` and in the reference pencil
`2.67e-15` / `9.23e-18`, so the eigenvalue returned by `(K_C, M_C)` *is* the
reference `beta^2` (no Rayleigh-quotient detour is needed to compare it).
**MEASURED.**

One contract caveat, recorded rather than glossed: `eigsh`'s `M=` argument is
documented for a positive-definite `M`, and `M_C` is indefinite. It converged
anyway on both rungs (21 `OPinv` calls each, `t_eigsh = 0.01 s`), but the
portable route stays the one recommended in section 6 — an explicit
`LinearOperator` for `(K_C - sigma M_C)^{-1} M_C` built from a single
`splu(K_C - sigma M_C)`.

#### Per-route status, measured on both audit rungs

| route | pencil | reproduces reference | `lambda` digits rung0/rung1 | `R` digits rung0/rung1 | nnz(S) rung1 | fill/row rung0 -> rung1 |
|---|---|---|---|---|---|---|
| A | `eigsh(A, M=B)` on the dense `B` | yes | 9.2 / 12.5 | 11.4 / 7.5 | 5,779,216 (`= n^2`) | 1445 -> 2405 |
| B | `K = [[A,-c],[-c^T,h]]`, `M = diag(m1_f,0)`, `sigma = 1` | **no** | -0.1 / -0.1 | -2.7 / -2.7 | 35,351 | 56.5 -> 67.5 |
| B2 | as B, `sigma = 0.999 * beta_sq` | **no** | 2.3 / 2.0 | 0.3 / 0.3 | 35,351 | 55.7 -> 67.6 |
| **C** | **`K_C = [[A,0],[0,0]]`, `M_C = [[m1_f,-c],[-c^T,h]]`, `sigma = 0.999 * beta_sq`** | **yes** | **12.2 / 12.5** | **12.5 / 12.7** | **35,351** | **55.1 -> 66.9** |

Route C on rung1: `n = 3207 = 2404 + 803`, `nnz(K_C) = 11,716`,
`nnz(M_C) = nnz(S_C) = 35,351` (`0.00344 n^2`), `splu` `0.0076 s`,
`nnz(L+U) = 214,641` (fill/row 66.9, `6.07x` over `nnz(S)`), factor memory
`2.6e-3 GB`. Route A on the same rung: `nnz(S) = 5,779,216 = n^2` exactly,
`splu` `0.62-0.63 s`, `nnz(L+U) = 5,781,620`, fill/row 2405, i.e. dense.

#### Route C measured, rung by rung (the primary path's evidence)

`sigma = 0.999 * beta_sq`, `threads = 1`. Every cell in this table is
**MEASURED**.

| quantity | rung0 (`sc=12`, `s12_a9_z8-4-4`) | rung1 (`sc=16`, `s16_a12_z10-5-5`) |
|---|---|---|
| `free_e / free_n / n` | 1444 / 483 / 1927 | 2404 / 803 / 3207 |
| `beta^2` from `(K_C, M_C)` | 97833.0578509302 | 97328.3081094334 |
| reference `beta^2` (dense QZ) | 97833.0578509992 | 97328.3081094 |
| `R` from `(K_C, M_C)` | 4.048979116393649 | 3.780331990014912 |
| reference `R` (dense QZ) | 4.0489791163950715 | 3.780331990015745 |
| digits in `beta^2` / in `R` | 12.15 / 12.45 | 12.46 / 12.66 |
| `nnz(K_C)` | 6,988 | 11,716 |
| `nnz(M_C) = nnz(S_C)` | 20,991 (`0.00565 n^2`) | 35,351 (`0.00344 n^2`) |
| `splu(K_C - sigma M_C)` | 0.00411 s | 0.00756 s |
| `nnz(L+U)` / fill per row | 106,167 / 55.1 | 214,641 / 66.9 |
| factor memory | `1.27e-3 GB` | `2.58e-3 GB` |
| `eigsh` wall time / `OPinv` calls | 0.00567 s / 21 | 0.00901 s / 21 |
| `x_2 - D c^T x_1`, relative | 8.09e-12 | 2.05e-13 |
| residual, enlarged / reference | 2.59e-15 / 2.67e-15 | 8.49e-18 / 9.23e-18 |

The reference column is the banked `dense_targets` record (see the note under the
defect table above): rung0 `97833.0578509992` / `4.0489791163950715`, rung1
`97328.3081094` / `3.780331990015745`.

#### Extrapolated target architecture (`free_e = 30000`)

Everything in this subsection is **EXTRAPOLATED**: a two-point power law fitted
through the two measured rungs `sc = 12` (`s12_a9_z8-4-4`) and `sc = 16` (`s16_a12_z10-5-5`), evaluated at
`free_e = 30000`. Nothing here was measured at the target mesh, and nothing here
was measured at ladder rung 4.

| route | n | nnz(L+U) | factor memory | `splu` |
|---|---|---|---|---|
| A | 30000 | 8.99e8 | 10.8 GB | 343 s |
| C | 40021 (30000 transverse + 10021 auxiliary) | 7.03e6 | 0.0843 GB | 0.156 s |

**EXTRAPOLATED** fill/row growth exponents: 1.000 for route A (i.e. `O(n^2)`
fill, dense) against 0.382 for route C; `splu` against factor entries, 1.237 (A)
and 0.867 (C). Route A is **127.99x** larger than route C in factor entries and in
memory at the matched transverse count, and the gap widens with `n`.

That table is a target *architecture*, stated so that it cannot be mistaken for a
measurement: route C is projected at `7.03e6` factor entries and `0.0843 GB`
against `8.99e8` and `10.8 GB` for route A. Route C's **per-apply cost at the
target mesh is not measured and is not extrapolated here**; the only measured
per-apply figure for route C is about `0.43 ms` at rung1 (section 5.3).

Provenance: `tools/host/sparse-probe/sparse_solver_test.py` (routes A, B, B2, C
in one run, `threads = 1`), evidence in
`tools/host/sparse-probe/evidence/sparse/rung01_sparse_report.json` under
`rungs.*.route_C`, `extrapolation.route_C` and
`extrapolation.comparison_at_target`.

## 5. Measurements

### 5.1 Assembly blocks: the sparsity is fixed-stencil

Nonzeros per row, `sc = 12`, reduced blocks (`free_e = 1444`, `free_n = 483`):

| block | shape | nnz | nnz/row |
|---|---|---|---|
| `m1_f` | 1444x1444 | 6988 | 4.839 |
| `m_eps_f` | 1444x1444 | 6988 | 4.839 |
| `k_q_f` | 1444x1444 | 6988 | 4.839 |
| `c_f` | 1444x483 | 5431 | 3.761 |
| `h` | 483x483 | 3141 | 6.503 |

The same ratios recur on every rung (4.83-4.84, 3.67-3.80, 6.47-6.52), so they
are the stencil and not a mesh artefact. **MEASURED.**

### 5.2 Factorisation of `K - sigma M` (the REJECTED variant's matrix)

> **Label warning.** Every number in this subsection was measured on section 4's
> **rejected stiffness-side** matrix, `S = K - sigma M` with
> `K = [[A, -c], [-c^T, h]]` and `M = diag(m1_f, 0)` — not on route C's
> `K_C - sigma M_C`. Including the `n = 60587` target row, none of it may be
> quoted as the primary path's cost. Route C's own measured factorisation is in
> section 4.2 (`splu` `0.00756 s`, `nnz(L+U) = 214,641`, fill/row 66.9 at rung1).

`splu` on `S = K - sigma M` with `sigma = 1.0`, default COLAMD ordering. `n` is
the enlarged order `free_e + free_n`.

| rung | n | nnz(S) | nnz(L+U) | fill/row | splu (s) | solve (ms) |
|---|---|---|---|---|---|---|
| sc=4 | 1431 | - | 76,790 | 53.7 | - | 0.26 |
| sc=12 | 1927 | 20,991 | 108,906 | 56.5 | 0.008 | 0.38 |
| sc=24 | 2671 | - | 151,752 | 56.8 | - | 0.23 |
| sc=48 | 4159 | - | 242,893 | 58.4 | - | 0.35 |
| sc=100 | 7383 | - | 429,730 | 58.2 | 0.014 | 0.64 |
| sc=200 | 13583 | - | 796,999 | 58.7 | 0.028 | 1.26 |
| **target** | **60587** | **687,031** | **8,352,700** | **137.9** | **0.38** | **12.82** |

> **Note (ESTIMATED, inherited labelling).** The `sc` column above is the design
> note's own labelling and its meshes are its own: its `sc=24` row (`n = 2671`)
> is **not** our measured rung1, which is `sc=16` (`s16_a12_z10-5-5`,
> `n = 3207`, section 5.3). Do not read the `sc` column row-for-row across the
> two tables.

Target mesh detail: `nnz(K) = 508,240`, `nnz(M) = 404,429`. The fill is
**0.00228** of dense `n^2 = 3,670,784,569`, i.e. about **100.2 MB** at 12 B/nnz,
against 16.7 GB for a single dense matrix of the size the QZ path needs.
Numeric quality: `min|Uii|/max|Uii| = 3.840e-11` on the target mesh — no zero
pivots, but the largest dynamic range observed anywhere in this note; treat it
as a diagnostic to monitor, not as a failure. `splu(h)` itself costs 0.03 s with
1,051,864 nonzeros, and is needed anyway by the dense path
(`emfit/mode2d.py:1113`). **MEASURED** (single-run timings on one host; fine for
order-of-magnitude, not a benchmark).

The fill-per-row story is the important one. It *rises slowly*
(53.7 -> 58.7) while `n` grows by 9.5x, and then jumps to 137.9 exactly when the
transverse node count jumps from 17 to 77. Fill tracks nodes across the short
direction, i.e. the ordering is nearly banded. It is **not** `O(n^2)` and it is
**not** evidence of a badly chosen ordering. **MEASURED** (the fill/row values);
the interpretation is an inference from the ordering being COLAMD with a
grid-shaped graph.

### 5.3 Shift-invert cost per ARPACK iteration

For section 4's **rejected** stiffness-side matrix, one `splu(S)`-based
application is 12.82 ms on the target mesh (12.82 ms from the table), plus two
sparse mat-vecs with `K` and `M` and vector work — so of order `1e-2` s per
implicit restart step, and a `k = 8`, `ncv = 24` solve should land in the
seconds-to-tens-of-seconds range. That end-to-end figure is **ESTIMATED**, and the
12.82 ms single-apply figure is **MEASURED** but belongs to the rejected variant.

For the primary path, route C, the measured per-apply cost at rung1 is about
`0.43 ms`: `t_eigsh = 0.00901 s` over 21 `OPinv` applications, i.e. arithmetic on
**MEASURED** quantities, on top of a once-only `splu(K_C - sigma M_C)` of
`0.00756 s`. Route C's per-apply cost at the target mesh is **unmeasured**, and is
not extrapolated here.

## 6. Solver options against the documented contracts

Quoting `scipy` 1.18.1 docstrings verbatim, because the distinctions here are
contractual, not stylistic.

`scipy.sparse.linalg.eigsh` on `M`:

> "M must represent a real symmetric matrix if A is real ... - If sigma is None,
> M is symmetric positive definite. - If sigma is specified, M is symmetric
> positive semi-definite. - In buckling mode, M is symmetric indefinite."

and on `sigma`:

> "Find eigenvalues near sigma using shift-invert mode. This requires an
> operator to compute the solution of the linear system ``[A - sigma * M] x = b``
> ... computed internally via a (sparse) LU decomposition for explicit matrices
> A & M"

`scipy.sparse.linalg.eigs` on `M`:

> "M must represent a real symmetric matrix if A is real ... - If `sigma` is
> None, M is positive definite - If `sigma` is specified, M is positive
> semi-definite"

Three consequences.

**(a) The reduced pencil `(A, B)` is outside the contract.** `B` is indefinite
(section 3: Cholesky fails), and `sigma`-mode `eigsh` permits only *positive
semi-definite* `M`. Only buckling mode names an indefinite `M`, and buckling mode
is a different problem (`A x = lambda M x` with `M` indefinite and `A` fixed —
not our pencil). So `eigsh(A, k, M=B, sigma=...)` would be a documented-contract
violation, not a matter of taste. This is the real reason
`emfit/mode2d.py:1095-1099` is blocked: not just that `A - sigma B` is dense, but
that even with a sparse `A - sigma B` the driver would be out of contract.
**MEASURED** (Cholesky failure) + **documented** (quoted contract).

**(b) The REJECTED stiffness-side pencil `(K, M)` is inside the letter of the
contract, and that gap no longer blocks anything.** `M = diag(m1_f, 0)` *is*
"symmetric positive semi-definite", so `eigsh(K, k, M=M, sigma=sigma)` on it
would be contract-compliant by the letter, with one genuine gap: `M` is
*singular* (nullity `free_n`), and `ARPACK`'s shift-invert theory is written for a
non-degenerate `M`-inner product. `scipy` documents the *class* of `M` it
accepts, not the behaviour of the returned Ritz pairs when `M` is singular. That
gap is now moot: this pencil is rejected for returning the wrong mode (section
4.2), so no blocking decision rests on it. The contract question that *does*
matter is the one in (c).

**(c) The primary path, route C, is outside the `M=` form and inside the
operator form.** `M_C = [[m1_f, -c], [-c^T, h]]` is symmetric but *indefinite*,
while the `sigma` mode documents `M` as symmetric positive semi-definite; passing
`M=M_C` with `sigma` would therefore be a documented-contract violation, not a
matter of taste, and the buckling mode is a different problem altogether (its
indefinite `M` puts the wanted mode at the wrong end, below). The
`LinearOperator` form carries no such clause: we hand the driver
`(K_C - sigma M_C)^{-1} M_C` and the driver never sees `M_C` as an `M`. What
remains is mechanical — in shift-invert the driver solves
`(K_C - sigma M_C) y = M_C z` and returns `mu = 1/(lambda - sigma)` with
`lambda = sigma + 1/mu`, so a `mu = 0` *would* become `lambda = inf` — but `M_C`
is nonsingular (inertia measured in the paragraph below, this item), so the primary pencil has **no** infinite
eigenvalues to surface and a `mu = 0` return would be a numerical failure rather
than a legitimate eigenpair. Guards required are in section 8.

**The inertia, measured, and where the negativity actually sits.** A one-off
rung0 check (`M_C` at 1927x1927, rebuilt through
`tools/host/sparse-probe/sparse_solver_test.py`'s own assembly path and
eigendecomposed with a dense `scipy.linalg.eigh`, threads pinned to 1, at 1444
free edges — below the 2404 dense fence; the check is promoted as
`tools/host/sparse-probe/mc_inertia_check.py`) gives the inertia **MEASURED**:
1444 positive, 483 negative, 0 zero; `lambda_min = -1.856672362588098e-02`,
`lambda_max = 21.777039052800774`, smallest `|lambda| = 1.0293555296331769e-04`,
`numpy.linalg.cond = 211559.9365417365`, and a condition ratio of `|eig|` of
1172.9069431746586. So `M_C` is indefinite *and* nonsingular — 0 zero
eigenvalues and smallest `|lambda| > 0`, hence no infinite eigenvalues — which is
assertion (c) above confirmed by direct measurement rather than inherited by
analogy. The negativity is **not** in `h`: `h` is SPD (symmetric to round-off,
`||h - h^T||_max = 0.0`, `cholesky(h)` succeeds, `ldl` min
`diag(D) = 0.30610723225474`, 483 positive pivots and 0 negative, `cond_2(h) =
1738.382116837915`) and `m1_f` is SPD too (`cholesky(m1_f)` succeeds,
eigenvalues `0.11227346625652906 .. 3.1582388589222656`, 0 negative). All 483
negative directions sit in the Schur complement, because the congruence
`L M_C L^T = diag(m1_f, h - c^T m1_f^-1 c)` holds with
`L = [[I, 0], [c^T m1_f^-1, I]]` (unit lower triangular, so Sylvester's law
makes the inertias equal): they belong to `h - c^T m1_f^-1 c`, in a number
that equals the aux dimension `free_n = 483` exactly. The sign matters: it is
`h` **minus** `c^T m1_f^-1 c`, the sign-corrected form — the plus sign is the
route-B error, and no reading of `h + c^T m1_f^-1 c` is intended anywhere in
this note.

### Recommendation

Implement the iterative path as shift-invert on route C, the **mass-side enlarged
pencil** of section 4.2 — `K_C = [[A, 0], [0, 0]]`,
`M_C = [[m1_f, -c], [-c^T, h]]` — with an explicit `LinearOperator` for
`(K_C - sigma M_C)^{-1} M_C` built from one `splu(K_C - sigma M_C)`, and `sigma`
pre-registered in the result (`sigma = 0.999 * beta_sq`, the band convention of
section 7). This is not a preference between two equivalent routes; it is the
only route that solves the code's eigenproblem.

Reasons:

* **It is the code's pencil, exactly.** `M_C`'s block row 2 gives `h y = c^T x`,
  a `lambda`-free elimination, so substituting into block row 1 returns
  `A x = lambda (m1_f - c D c^T) x`, which is `emfit/mode2d.py:1006-1008`.
  Measured `beta^2` reproduces the dense reference to 12.15 / 12.46 digits on the
  two rungs (section 4.2).
* **`M_C` is nonsingular.** No infinite eigenvalues, nothing to filter, and the
  `mu = 0` / `lambda = inf` artefact belongs entirely to the rejected variant.
* **It is sparse and cheap, measured.** At rung1 `nnz(S_C) = 35,351`
  (`0.00344 n^2`), `splu` `0.00756 s`, `nnz(L+U) = 214,641`, fill/row 66.9,
  factor `2.58e-3 GB`; at the target mesh `0.0843 GB` and `0.156 s`
  (**EXTRAPOLATED**, section 4.2), against `10.8 GB` and `343 s` for the dense
  route.
* **It is symmetric**, so `eigsh` remains the right *driver family* and the wanted
  eigenvalues are real by construction. `eigs` (non-symmetric driver) is not
  needed for this pencil and would forfeit that guarantee.

The `LinearOperator` route is **mandatory** here, not merely preferred: it is what
keeps the primary pencil inside the documented contracts (paragraph c). The `M=`
form is retained only as a fallback *diagnostic* on the rejected stiffness-side
pencil, where it is compliant by the letter (paragraph b). It is not a licence to
drive the primary pencil through `M=M_C`, whose `M` is indefinite. That the
shortcut did converge on `(K_C, M_C)` in 21 `OPinv` calls (5.7 / 9.0 ms, measured)
is recorded as a diagnostic, not as a recommendation.

Rejected alternatives, with the reason:

* **Section 4's stiffness-side enlargement** (`K = [[A, -c], [-c^T, h]]`,
  `M = diag(m1_f, 0)`) — rejected as *the pencil*, not as an implementation. Its
  `w`-elimination is not `lambda`-free: it lands the rank-one term on the
  stiffness side and yields `(A - c D c^T) x = lambda m1_f x`, a different
  eigenvalue problem. Measured at `sigma = 1`: `lambda = 26953.0` against a
  reference `97833.1`; with the shift moved onto the target,
  `lambda = 98360.7 / 98375.3` (`+0.54 % / +1.08 %` off) at `abs(corr_ey) = 0.55`
  against `0.92`. A variant that is within a percent is **more** dangerous here
  than one that is nowhere near, because it looks like a convergence tolerance
  being met. The corrected pencil is exact, not approximate, so there is nothing
  to trade. **MEASURED.**
* **Woodbury on the reduced pencil.** `(A - sigma B)^{-1} = (A - sigma m1 +
  sigma c D c^T)^{-1}` reduces to one `splu(A - sigma m1_f)` plus a dense
  `free_n x free_n` capacitance solve (15093x15093 at 1.82 GB on the target
  mesh). Cheaper per apply than nothing, but it reintroduces a dense
  `free_n`-sized object and a second factorisation, and the numerical condition
  of the Woodbury correction through an indefinite `B` is unattractive at
  `min|Uii|/max|Uii| = 1.8e-4` for `A` and `1.3e-3` for `B` (measured at
  `sc = 12`). **MEASURED** pivot ratios; the conditioning judgement is an
  inference.
* **Dense `D` but sparse `A`.** Materialising `D` at the target mesh costs
  `free_n^2 * 8 = 1.82 GB` and `c D c^T` is a dense `free_e x free_e` product —
  this is the current path and is what section 2 rules out.
* **Buckling-mode `eigsh`.** `M` indefinite is documented for buckling mode, but
  buckling solves `A x = lambda M x` for indefinite `M`; our pencil is
  `A x = lambda B x` with `B` indefinite and `A` the stiffness-like block. The
  spectra are reciprocals-with-shift of each other, so a mapping exists — but it
  maps the *wanted* largest `beta^2` to the *smallest* transformed eigenvalue,
  which is the wrong end for `which="LM"` and needs a different selection story
  than section 7.

## 7. Mode selection and result semantics

This is the part that does not survive the change, and it is more important than
the numerics.

The dense path returns the **complete spectrum** and then picks one candidate
(`emfit/mode2d.py:1150-1167`):

* `:1150` `order = np.argsort(-beta_sq)` — sort the whole candidate set;
* `:1156-1160` `eligible = (np.isfinite(beta_sq) & (beta_sq > 0.0) &
  (residuals < _MIXED_RESIDUAL_TOL))`, with `_MIXED_RESIDUAL_TOL = 1.0e-3`
  (`emfit/mode2d.py:150`);
* `:1161-1166` raise if nothing is eligible;
* `:1167` `chosen = int(np.flatnonzero(eligible)[np.argmax(beta_sq[eligible])])`
  — a **global argmax of `beta^2` over the eligible candidates**, i.e. over the
  entire discrete spectrum.

Three properties of that line are load-bearing and all three are lost by an
iterative solve:

1. **"Global" is not available.** A shift-invert `eigsh` returns `k` Ritz pairs
   near a pre-registered `sigma`; it cannot certify that no larger eligible
   `beta^2` exists elsewhere in the spectrum. `candidates` shrinks from the whole
   spectrum to `k`.
2. **`k` starts truncating.** The current docstring states
   (`emfit/mode2d.py:1010-1016`) that the dense path returns everything and
   therefore `k` "truncates nothing"; an iterative path makes `k` a real
   truncation. A `result` field that means "all candidates" today would mean
   "the top `k` near `sigma`" afterwards.
3. **`sigma` stops being inert.** `solve_modes_mixed` records `sigma` on the
   result only, and says so (`emfit/mode2d.py:1085-1090`: "Recorded on the result
   only ... there is no shift to choose"). Under shift-invert `sigma` *is* the
   query — it decides which modes are reachable — so it becomes an input with
   physical meaning (a target `beta`), and it must be chosen and registered
   rather than defaulted.

Since `c1_audit.py:478` consumes the result and the audit's assertions depend on
which mode `chosen` is, **re-registration is mandatory**: the sparse path needs
its own documented selection rule (e.g. largest eligible `beta^2` within a
pre-registered band `[sigma_lo, sigma_hi]`, with the band width an input and the
number of modes found reported), and the audit's banked numbers must be
re-taken under the new rule rather than assumed unchanged.

An honest observation about the *current* rule that this design work turned up,
and which should be settled before either path is trusted: a global argmax of
`beta^2` over everything eligible prefers the **most oscillatory** admissible
discrete mode, not the fundamental. Whether that is what the audit currently
scores is not something this note measured, and it must not be assumed. Flagged
as an open question in section 9, not resolved here.

## 8. Guards, acceptance tests, failure modes

Guards to implement with the sparse path:

* **`splu(K - sigma M)` failure** -> `ValueError` naming `sigma`, mirroring the
  existing longitudinal-block guard (`emfit/mode2d.py:1113`, which converts
  `RuntimeError` into "the longitudinal block `k_zz - k0^2 m_zz` is singular at
  `k0 = ...`; nudge `k0` off the nodal Dirichlet eigenvalue").
* **Non-finite or `mu = 0` Ritz values** -> drop, and *count the drops*. On the
  primary path this is defence in depth, not an expected artefact: `M_C` is
  nonsingular (section 6c), so `(K_C, M_C)` has no infinite eigenvalues and a
  `mu = 0` return is a numerical failure. The expected-artefact reading belongs
  to section 4's rejected stiffness-side pencil, whose `M` is singular. Either
  way no such value may reach `chosen`.
* **Empty eligibility set** -> the existing `raise` semantics
  (`emfit/mode2d.py:1161-1166`), not a silent fallback.
* **Residual gate.** The same scale-aware backward error already used by the
  dense path (`emfit/mode2d.py:1126-1148`,
  `denom_scale = norm_a + |lam|*norm_b`) and the same `_MIXED_RESIDUAL_TOL =
  1.0e-3`. The block residual guard added after selection
  (`emfit/mode2d.py:1176-1190`) should be reused unchanged on the Ritz vector.
* **`e_z` reconstruction stays as is.** `e_z[free_n] = 1j*beta*lu_h.solve(c_f.T @
  x)` (`emfit/mode2d.py:1173`) needs only `x` and the existing `splu(h)`;
  nothing in the sparse path changes it.
* **`min|Uii|/max|Uii|` budget.** Observed 3.840e-11 on the target mesh. Record
  it on the result and warn below a floor; do not gate on it silently.

Acceptance tests, in the order they can be run cheaply:

1. **Equivalence on the audit mesh** (`31x17`, `free_e = 1444`): sparse and dense
   must return the same `chosen` mode, `beta^2` agreeing to the dense path's own
   backward-error level, with the band set wide enough to contain the answer.
   This is the only mesh where both paths run, so it is the only honest
   cross-check, and it must run every time the sparse path changes.
2. **No infinite eigenvalues on the primary path**: `M_C` is nonsingular
   (section 6c), so a request for all `n_dof = free_e + free_n` eigenpairs from
   `(K_C, M_C)` must return `free_e + free_n` **finite** values and zero
   `inf`/`nan`. The `nullity(M) = free_n` accounting — `free_e` finite and
   `free_n` infinite — applies only to section 4's rejected stiffness-side
   pencil, and is kept as the regression that proves the two pencils are
   different problems, not as a gate on the primary path.
3. **Determinism under `sigma`**: shifting `sigma` within the band must not
   change the reported mode when the band contains exactly one eligible
   candidate; if it does, the band is wrong or the eligibility rule is.

## 9. Risks, open questions, provenance

**Single biggest technical risk: the semantic break in section 7, not the
numerics.** Route C's factorisation is measured, cheap and well-behaved: at rung1
`splu` is `0.00756 s`, the fill is `2.58e-3 GB`, and fill/row rises only 55.1 ->
66.9 from rung0 to rung1; at the target mesh it is `0.156 s` and `0.0843 GB` at
`n = 40021` (**EXTRAPOLATED**), against 16.7 GB and ~41 days (**ESTIMATED**) for
the dense path — so nothing about the linear algebra is the threat. The threat is that `chosen` comes from a global
argmax over the complete spectrum (`emfit/mode2d.py:1167`), that an iterative
solve cannot reproduce a global argmax, and that `c1_audit.py:478` consumes
`chosen`. A fast solver that silently returns a *different mode* than the dense
path would be worse than no solver, because it would look like a speed-up.

Open questions:

* Whether the global `argmax(beta^2)` at `emfit/mode2d.py:1167` currently
  selects the intended physical mode at all (section 7, last paragraph). Needs a
  measurement, not an argument.
* Whether `ARPACK` returns sane Ritz pairs for a singular `M` in the `M=`
  driver route (section 6b). The operator route in section 6 sidesteps the
  question rather than answering it.
* The fill/row jump 58.7 -> 137.9 at the target mesh is unexplained beyond "more
  transverse nodes"; a reordering study (RCM, nested dissection) could halve it,
  and is not attempted here.
* **Route C's fill/row exponent `0.382` rests on exactly two rungs** (`sc = 12`
  and `16`), so every **EXTRAPOLATED** figure in section 4.2 that depends on it
  (`7.03e6` factor entries, `0.0843 GB`, `0.156 s`, `n = 40021`) is unverified at
  ladder rung 4 and at `free_e = 30000`. A third rung would either confirm the
  exponent or move the whole target column.
* The ~41 day / 16.7 GB figures are inherited arithmetic, not timings.

Provenance. Every number in this note carries one of three labels:
**MEASURED** = produced by a run recorded in the evidence file, i.e. the section-5
assembly measurements, which come from assembling `emfit/mode2d.py`
(`assemble` `:397`, `assemble_mixed` `:469`, `structured_mesh` `:287`,
`pec_edge_mask` `:539`, `pec_node_mask` `:571`, `k0_from_freq` `:787`) on the
geometry in `.scratch/tol/logs/TOLFLUX.json` (`W = 0.02`, `H = 0.0076`,
`h = 0.0016`, `w = 0.003`, `eps_r = 4.4`, graded per `eps_of`; boundaries
`(ground, strip)`), with `k0 = 164.17940719617263`, `scipy` 1.18.1, `numpy`
2.5.4, and `Cholesky`/`splu`/`lu.solve` only — for *those* numbers **no `eig`,
`eigsh`, `eigs`, `eigh` or `svd` call was made anywhere**; scripts
`/tmp/sp/measure2.py`, `/tmp/sp/measure3.py`. That restriction is scoped to the
assembly measurements only: section 4.2's **MEASURED** `eigsh` figures (the 21
`OPinv` calls, the reproduced `beta^2`, the consistency and residual columns)
come from `tools/host/sparse-probe/sparse_solver_test.py`, which *does* call
`eigsh`, filed under `rungs.*.route_C` in the same evidence file.
**EXTRAPOLATED** = a two-point power-law projection through the two measured
rungs `sc = 12` (`s12_a9_z8-4-4`) and `sc = 16` (`s16_a12_z10-5-5`), evaluated at `free_e = 30000`: the target table in
section 4.2 (`n`, `nnz(L+U)`, factor memory, `splu`), its fill/row exponents
`0.382` (route C) and `1.000` (route A), the `splu`-versus-entries exponents
`0.867` and `1.237`, the `127.99x` route A / route C ratio, and the
`0.0843 GB` / `0.156 s` / `n = 40021` target architecture. No extrapolated number
is a measurement: none was taken at the target mesh, none was taken at ladder
rung 4, and none may be quoted as measured.
**ESTIMATED** = arithmetic or inherited: the ~3.2e4 QZ cost ratio, the ~41 day
dense runtime, the 16.7 GB dense matrix size, the `O(1e-2)` s per shift-invert
iteration, and the "seconds-to-tens-of-seconds" end-to-end prediction.
Contract quotes are **documented** (verbatim `scipy` 1.18.1 docstrings, section
6). The symmetric-variant identity in section 4 marked *measured* was measured on
the row-scaled assembly; the unscaled symmetric form `[[A - sigma m1, -c],
[-c^T, h]]` was **verified algebraically** (its symmetry follows from the exactly
symmetric blocks, measured) after an attempt to factorise it at the target mesh
was aborted: `cholesky(m1_f.toarray())` needs 16.5 GB at `free_e = 45494`, which
the sandbox cannot hold. That is a limitation of the check, not of the pencil.
