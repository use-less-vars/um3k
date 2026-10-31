# Matrix audit: asymmetry (Task D) + spectrum classification (Task C)

Case: 2D FEM d585 anchor, clearance 3.0 mm, eps_r 4.4, W 10.4 mm, H 6.4 mm, k0 = 209.78570331727553 1/m.
Pencil: A = k0^2 M_eps,ff - K_q,ff ; B = M1,ff - C_f (K_zz,ff - k0^2 M_zz,ff)^-1 C_f^T, B assembled exactly as
solve_modes_mixed does (dense splu solve, no approximation). A and B are REAL (QZ = dggev).
Container d54a2, scipy 1.18.1, numpy 2.5.4.

## What was run
- `python3 /tmp/run_d.py` - Task D asymmetry table, h = 0.8 mm and 0.4 mm.
- `python3 /tmp/run_c2.py h080 0.8` - Task C: QZ 319x319 in 0.69 s.
- `python3 /tmp/run_c2.py h040 0.4` - Task C: QZ 1262x1262 in 17.49 s.
- `python3 -c '<splu(h).solve(I) asymmetry check>'` - locates the source of the only asymmetry seen.

## Headline
- Every assembled block (M1, M_eps, K_q, M_mu, M_eps(assemble), K_zz, M_zz) and A is EXACTLY
  symmetric on both meshes: ||X-X^T||_F/||X||_F = 0.000e+00, max|asym| = 0.0, 0 entries > 1e-12.
- B's asymmetry is pure round-off: 3.6e-15 (h080) / 8.6e-15 (h040) relative, largest single
  element 8.95e-16 / 1.39e-15, zero entries above 1e-12. Source: D = splu(h).solve(I) is symmetric
  only to 2.8e-16 / 3.5e-16 and C D C^T inherits exactly that.
- Therefore explicit symmetrisation of A,B before QZ is a no-op for A and masks only round-off for B.
- Spectrum, both meshes: 0 ZERO, 0 INFINITE-LIKE, 0 NONFINITE eigenvalues (h080 319/319 and h040
  1262/1262 FINITE); ker(B) = {0} (sigma_min 6.0e-4 / 1.5e-4), so no infinite family from ker B.
- span(Z) (gradient/deflation columns: 84 cols h080, 324 cols h040) is not an eigen-invariant
  subspace of the reduced pencil: Rayleigh quotients median -4.55e6 / -1.51e7 against k0^2 = 4.40e4,
  residual median 0.83 / 0.89, and 0/84 and 0/324 below 1e-6.
- Physical quasi-TEM mode: beta = 389.36 (h080) / 385.02 (h040) vs HJ+KJ 377.34 (+3.18% / +2.03%),
  FINITE, residual 4.9e-8 / 3.9e-7, projZ = 0.202 / 0.216 - i.e. NOT orthogonal to span(Z).
- Verdict: NEITHER - the classification is not clean.

## Files
- h080.json, h040.json: asymmetry rows (incl. D), thresholds, class statistics, log10|lambda| bins,
  gradient Rayleigh data, ker(B), physical mode, commands, environment, verdict.

## Not attempted
- Unsym-vs-sym QZ arm comparison at h = 0.4 mm (h080 only, from the earlier run_c1).
- Meshes beyond these two; a scale-aware ZERO/INFINITE rule instead of the median-relative one.
