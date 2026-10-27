# Sparse eigenmode solve for the mixed formulation (design pass)

Design note only. No code is changed by this note; every recommendation below is
unanchored until it is implemented and gated.

## 1. Scope, and what this note is not

`solve_modes_mixed` (`emfit/mode2d.py:935`) currently has exactly one working
path: assemble, condense the longitudinal block densely, and hand the resulting
`beta^2`-pencil to a dense QZ solve. The iterative path is a stub that raises
(`emfit/mode2d.py:1095-1099`). This note asks what a sparse path would have to
be, and what it would cost, on the meshes the audit actually wants.

This note **is**: a statement of the pencil the code builds (section 3), a
derivation of an equivalent *sparse symmetric* pencil (section 4), measured
factorisation statistics for that pencil on the audit mesh and on the target
201x77 mesh (section 5), a reading of the documented `scipy.sparse.linalg`
contracts against that pencil (section 6), and the consequences for result
semantics (section 7).

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

## 4. The enlarged sparse pencil

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

### 5.2 Factorisation of `K - sigma M`

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

One `splu(S)`-based application is 12.82 ms on the target mesh (12.82 ms from the
table), plus two sparse mat-vecs with `K` and `M` and vector work — so of order
`1e-2` s per implicit restart step, and a `k = 8`, `ncv = 24` solve should land in
the seconds-to-tens-of-seconds range. That end-to-end figure is **ESTIMATED**;
only the single-apply 12.82 ms is **MEASURED**.

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

**(b) The symmetric enlarged pencil `(K, M)` is inside the contract** — `M` is
"symmetric positive semi-definite" — with one genuine gap: `M` is *singular*
(nullity `free_n`), and `ARPACK`'s shift-invert theory is written for a
non-degenerate `M`-inner product. `scipy` documents the *class* of `M` it
accepts, not the behaviour of the returned Ritz pairs when `M` is singular. So
`eigsh(K, k, M=M, sigma=sigma)` is contract-compliant by the letter and
unverified by the documentation in the way that matters.

**(c) The mechanism is transparent, so the gap is closeable by guard.** In
shift-invert the driver solves `(K - sigma M) y = M x` and returns
`mu = 1/(lambda - sigma)`, with `lambda = sigma + 1/mu`. Every infinite
eigenvalue of the pencil maps to `mu = 0`; every finite `lambda` maps to a
non-zero `mu`. So a computation of `k` Ritz values with `which="LM"` (largest
`|mu|`, i.e. nearest `sigma`) *should* return finite `lambda` and never the
infinite set — but "should" is exactly the thing to check, not assume. Guards
required are in section 8.

### Recommendation

Implement the iterative path as shift-invert on the **symmetric enlarged pencil**
`(K, M) = ([[A, -c], [-c^T, h]], diag(m1_f, 0))` with an explicit
`LinearOperator` for `(K - sigma M)^{-1} M` built from one `splu(K - sigma M)`,
rather than by passing `M=` and letting the driver factorise. Reasons: the
operator route does not depend on `ARPACK`'s generalised-`M` path at all (so the
singular-`M` question in (b) never arises), it keeps the 12.82 ms per-apply cost
visible in our own code, and it lets us reject `mu = 0` before it becomes an
inf. The `M=` route is the fallback if the operator route shows restart
pathology.

`eigsh` remains the right *driver family* where `(K, M)` is used directly,
because `K` and `M` are real symmetric and the wanted eigenvalues of a symmetric
pencil are real by construction. `eigs` (non-symmetric driver) is not needed for
the pencil, and would forfeit that guarantee.

Rejected alternatives, with the reason:

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
* **Non-finite or `mu = 0` Ritz values** -> drop, and *count the drops*; an
  infinite eigenvalue surfacing as `lambda = inf` is the expected artefact of
  singular `M` (section 6c), not a bug, but it must never reach `chosen`.
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
2. **Infinite-eigenvalue accounting**: `nullity(M) = free_n` exactly (measured
   certificate in section 4), so a request for all `n_dof` eigenpairs from the
   enlarged pencil must return `free_e` finite and `free_n` infinite ones. Any
   other split means a discretisation or masking mistake.
3. **Determinism under `sigma`**: shifting `sigma` within the band must not
   change the reported mode when the band contains exactly one eligible
   candidate; if it does, the band is wrong or the eligibility rule is.

## 9. Risks, open questions, provenance

**Single biggest technical risk: the semantic break in section 7, not the
numerics.** The factorisation is measured, cheap and well-behaved — 0.38 s to
build, ~100 MB of fill, 12.82 ms per shift-invert application on the target
mesh, against 16.7 GB and ~41 days for the dense path — so nothing about the
linear algebra is the threat. The threat is that `chosen` comes from a global
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
* The ~41 day / 16.7 GB figures are inherited arithmetic, not timings.

Provenance. Every number in this note carries one of two labels:
**MEASURED** = produced in this session by assembling `emfit/mode2d.py`
(`assemble` `:397`, `assemble_mixed` `:469`, `structured_mesh` `:287`,
`pec_edge_mask` `:539`, `pec_node_mask` `:571`, `k0_from_freq` `:787`) on the
geometry in `.scratch/tol/logs/TOLFLUX.json` (`W = 0.02`, `H = 0.0076`,
`h = 0.0016`, `w = 0.003`, `eps_r = 4.4`, graded per `eps_of`; boundaries
`(ground, strip)`), with `k0 = 164.17940719617263`, `scipy` 1.18.1, `numpy`
2.5.4, and `Cholesky`/`splu`/`lu.solve` only — **no `eig`, `eigsh`, `eigs`,
`eigh` or `svd` anywhere**; scripts `/tmp/sp/measure2.py`, `/tmp/sp/measure3.py`.
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
