# Preservation gate: geometry A-1.5, frozen

**Status: FROZEN.** This file, together with the commit that introduces
`tools/host/anchor/preservation_gate.py`, precedes every discrete solve of this
geometry. The commit hash is the only admissible reference; a later version
governs nothing already run.

## 1 The geometry

`eps_r = 1.5`, `t = T = B/4 = 0.001953125`, `b = B = 0.0078125`, `mu_r = 1`,
`a = A = B/8`, `k0 = K0 = 1407.4335088082273`, `sigma` unchanged from the
d49 instrument (990434.5408581193). Thickness is unchanged from geometry A.

The contrast `eps_r - 1/mu_r` falls from 1.0 to 0.5. The deflation removes
rows with `y < t`, i.e. slab-interior rows. Lower contrast weakens guidance,
so the physical mode spreads further into the region the deflation removes.
This is the tightest available stress on over-removal specifically, and it
leaves `t` on a node line at every level.

## 2 The analytic set (established before, and independently of, any discrete solve)

Exact call:

    solve_ref(t=T, eps_r=1.5, b=B, k0=K0)

returns, in ascending order:

    (874.2142025845457, 1259.419736217716, 1433.426694521395)

`solve_ref` returns ascending; `BETA_REF_DOC` is descending. The gate indexes
roots in descending order with one-based `order`. The frozen set is:

| order | beta_ref |
| --- | --- |
| 1 | 1433.426694521395 |
| 2 | 1259.419736217716 |
| 3 | 874.214202584546 |

A reader that indexes `solve_ref` output without reversing shifts every row by
one. `ENDPOINT = sqrt(1.5)*K0 = 1723.7469717375452`. The census window is
`[0, 1.5*ENDPOINT] = [0, 2585.6204576063178]`. Roots above `ENDPOINT` remain in
the set; there are none here. Three roots lie in the window and there are three
roots in total.

## 3 Pairing feasibility

The route-3 separation, computed as in the gate document with the set in
descending order and the denominator the smaller root:

| pair | separation |
| --- | --- |
| (1, 2) | 0.1381643889639651 |
| (2, 3) | 0.4406306057420944 |

The minimum is `0.1381643889639651`, against a threshold of `0.04`, a margin of
3.45x. Route 3 passes. This figure is recomputed for this geometry and is not
inherited from geometry A; geometry A's 0.2636 and 0.3723 say nothing here.

Note for the record: computed instead on the ascending list, the same quantity
appears as `0.121392`, the denominator being the larger root. That number is an
artefact of the ascending convention and is not the registered figure.

## 4 The mesh

`nx = ny//8`, `h = B/ny`, `ys = B*arange(ny+1)/ny`, levels `ny = 16, 32, 64`.
`t/h` is 4, 8 and 16, integer at every level, so the interface is a node line
at every level; `build_mesh` raises `SystemExit` if it is not. Permittivity is
supplied by `build_mesh(ny, T, eps_r=1.5)`.

## 5 The instrument

The solver, its deflation, its sigma and its arguments are the d49 instrument
unchanged in every respect except the permittivity:

    res = mode2d.solve_modes_deflated_v2(mesh, ar.K0, ladder.SIGMA,
                                         eps_r=eps_call,
                                         boundaries=boundaries,
                                         k=ladder.K_CAND)

Nothing else about the instrument is varied. `PAIR_TOL = 2e-2` is inherited
unchanged, as are B1-B6 and both prohibitions.

## 6 What is registered as output

Per root over levels 1 to 3: the relative error measured on `beta`, the two
orders `p_k`, and the verdict from P1, P2 and P3. Per level: `residual_eps_mu`
with its level-to-level ratio, reported and not gated; `curl_ratio` as context
only; the stored mode count. The e_k tables are the record.

## 7 The stop rule

If after B1-B6 exhaustion any reference root at any level is unpaired, the run
stops: no further level is solved, no verdict is issued, and the supervisor is
told immediately. An unpaired-at-every-level root is a stop even if its nearest
candidate is inside `PAIR_TOL`.

## 8 What this geography does not change

Every non-claim of the gate document stands unmodified. This freeze adds a
geometry; it relaxes nothing.

## 9 The only admissible response to an explained failure

If a pass condition fails and the failure is explained by a defect in this
freeze rather than by the solver, the verdict is `FAILED_TO_MEASURE`. It is not
`PASS`, and there is no fourth verdict.
