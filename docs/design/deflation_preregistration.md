# Deflation pre-registration: removing the curl-free subspace before the eigensolve

Status: living document. This file records a solver change and the check that the change must pass. It is amended only by the dated entries described in section 5.

Every number carries one of two tags. [VERIFIED this session] means the number was recomputed from the repository this session, from `emfit/mode2d.py`, `tools/host/anchor/ladder.py`, `tools/host/anchor/anchor_reference.py`, `docs/design/d46_acceptance.md`, `docs/design/d45_anchor_results.md`, `tools/host/anchor/records/level1.json`, `tools/host/anchor/records/level2.json`, `tools/host/anchor/records/level3.json`, or by arithmetic on those. [RELAYED] means the number is carried from the dispatch and is not independently reproduced here.

## 1. The defect this pre-registration addresses

The driven mode solver computes the eigenpairs of

    A x = beta^2 B x,    A = k0*k0*m_eps - k_q,    B = m_mu,

nearest the shift `sigma` = 990434.5408581193 [VERIFIED this session], where k0*k0 = 1980869.0817162385 [VERIFIED this session]. It then normalises each candidate, computes a curl ratio, filters on effective permittivity and on separation, and selects the candidate of largest positive beta.

The curl-free subspace of the edge discretisation is an exact invariant subspace of that pencil, and every vector in it has Rayleigh quotient exactly k0*k0. It therefore appears as a degenerate cluster at beta = k0 = 1407.4335088082273 [VERIFIED this session], at distance k0*k0 - sigma = 990434.5408581193 [VERIFIED this session] from the shift, and it occupies solver slots that the physical modes need.

The measured extent, from `tools/host/anchor/records/level1.json`, `records/level2.json` and `records/level3.json` [VERIFIED this session]:

- Level 1: free degrees of freedom 78 [VERIFIED this session], 11 cluster states among the 16 requested [VERIFIED this session], 5 candidates retained [VERIFIED this session], fundamental present but matched at order 2 [VERIFIED this session].
- Level 2: free degrees of freedom 348 [VERIFIED this session], 14 cluster states among the 16 requested [VERIFIED this session], 2 candidates retained [VERIFIED this session], fundamental absent from the returned candidates [VERIFIED this session].
- Level 3: free degrees of freedom 1464 [VERIFIED this session], 14 cluster states among the 16 requested [VERIFIED this session], 2 candidates retained [VERIFIED this session], fundamental absent from the returned candidates [VERIFIED this session].
- Levels 4 and 5: no record file exists, so no number exists [VERIFIED this session, the records directory holds levels 1 to 3 only].

The consequence for identification is not only a shortage of candidates. At level 1 the largest-beta retained candidate was a non-gradient state at beta 1736.2570207158685 [VERIFIED this session], which was matched to mode 1 with relative deviation 5.998690e-02 [VERIFIED this session], while the fundamental at beta 1636.5986739978343 [VERIFIED this session] was matched to mode 2 and the third mode at beta 952.9911948312771 [VERIFIED this session] was filed as surplus [VERIFIED this session]. A cluster that eats slots also reorders what survives.

The defect does not shrink under refinement. The dimension of the curl-free subspace is m = (nx - 1)*(3*ny/4 - 1) [VERIFIED this session], which is 11, 69, 329, 1425 and 5921 at the five levels [VERIFIED this session], against free degrees of freedom 78, 348, 1464, 6000 and 24288 [VERIFIED this session]. The ratio is 0.141026, 0.198276, 0.224727, 0.237500 and 0.243783 [VERIFIED this session] and tends to 1/4 [VERIFIED this session, arithmetic on the two counts]. The multiplicity is unbounded, so neither raising the requested candidate count of 16 [VERIFIED this session] nor moving the shift removes the crowding; both only postpone it, and both were already ruled out in `docs/design/d45_anchor_results.md`.

This document pre-registers a solver change. It does not change the acceptance criterion, the ladder geometry, the material parameters, the candidate count, the classification rules or the selection rule.

## 2. The mathematical specification of the fix

The names used here are the names in the code. `emfit/mode2d.py` provides `assemble`, which returns `k_q`, `m_mu` and `m_eps` on the full edge list, `solve_modes`, which forms `c = (k0*k0*m_eps - k_q).tocsr()` and `b = m_mu.tocsr()`, restricts both to `free = flatnonzero(~pec_edge_mask)`, and calls

    vals, vecs = eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM"),

and `solve_modes_mixed`, which is not touched by this fix. `tools/host/anchor/ladder.py` supplies `build_mesh`, then `mode2d.solve_modes`, then `classify`, which is `candidate_rows` plus `apply_v2` plus `matched_by_order`.

### 2.a The subspace removed, its dimension, and its scaling

The removed object is `Z`, the oriented node-to-edge incidence matrix of the mesh, restricted in both directions:

- Columns are the nodes whose entire star lies in the region where eps_r = 1/mu_r, and which are not on a boundary carrying a PEC predicate.
- Rows are the free edges, that is the edges selected by `free` in `solve_modes`.

For the ladder, `eps_r` is the callable `where(y < t, EPS_R, 1.0)` with EPS_R = 2 [VERIFIED this session] and mu_r = 1, so the region is y > t. The interface height is t = 0.001953125 [VERIFIED this session] and equals B/4 while B is held fixed and ny doubles, so the interface sits on the node row j = ny/4 at every level and the strict inequality y > t selects the rows j = ny/4 + 1 to ny - 1, which are 3*ny/4 - 1 rows [VERIFIED this session]. The PEC predicates on x = 0 and x = A remove the two boundary columns, leaving nx - 1 columns [VERIFIED this session]. Hence

    m = (nx - 1)*(3*ny/4 - 1) = 11, 69, 329, 1425, 5921  [VERIFIED this session].

The entries of `Z` are in {-1, 0, +1}. The count 11 at level 1 agrees exactly with the observed cluster multiplicity of 11 [VERIFIED this session], which is the only direct confirmation available, since levels 2 and 3 were capped at the requested count of 16 and cannot show a multiplicity of 69 or 329.

Scaling. Against the free degrees of freedom, m/n_dof takes the values 0.141026, 0.198276, 0.224727, 0.237500, 0.243783 [VERIFIED this session] and tends to 1/4 [VERIFIED this session, arithmetic]. The cost of the removal is therefore linear in the free degree count and is not a coarse-mesh artefact. What does not scale is the physics: the number of physical modes the ladder needs is 3, and it does not grow.

Two extensions are not derivable from the code and are marked PROVISIONAL: the region condition for general mu_r, which is eps_r = 1/mu_r rather than eps_r = 1, and the dimension of the corresponding subspace on the mixed path, where the pencil matrix is not `m_mu` at all. The first is PROVISIONAL because the ladder only exercises mu_r = 1; the second is PROVISIONAL and is treated in section 6.

### 2.b The basis, and its relation to the discrete gradient

`Z` is a submatrix of the coboundary operator d0, the node-to-edge incidence operator of the mesh. Its i-th column is the coordinate representation, in the edge basis, of the Whitney gradient of the nodal hat function phi_i: the line integral of grad(phi_i) along an edge is exactly +1, -1 or 0, which is exactly the incidence entry. The relation to the discrete gradient is therefore an identity, not an approximation: the column is the gradient of a scalar nodal field, taken in the same edge basis that `k_q` acts on.

Two exact consequences follow, and both are needed in 2.d:

- `k_q Z = 0` exactly, because the curl operator is d1 and d1*d0 = 0 holds in integer arithmetic for every triangle, so no rounding is involved in the cancellation.
- `(m_eps - m_mu) Z = 0` whenever eps_r = 1/mu_r on every element in the star of every selected node, because the two mass matrices then have the same entries on the support of each column.

The observed curl ratios of the cluster are round-off and not zero, from 2.6791731109636385e-10 at level 1 [VERIFIED this session] to 6.61052631017697e-09 at level 3 [VERIFIED this session]. That is a property of the returned eigenvector, which is a linear combination of kernel vectors plus round-off, and it is the reason the checks in 2.d are stated relative to the norms of the matrices and not against zero.

### 2.c The projection, the pencil, and where it is applied

Let

    G = Z^T B Z            (m by m, sparse, symmetric positive definite)
    X = B Z G^{-1} Z^T B
    P = I - Z G^{-1} Z^T B (P*P = P, P^T = I - B Z G^{-1} Z^T)
    A_p = P^T A P = A - k0*k0*X
    B_p = P^T B P = B - X

with the two identities

    Z^T A Z = k0*k0*G        and        (A - sigma*B) Z = (k0*k0 - sigma) B Z,

which give

    A_p - sigma*B_p = (A - sigma*B) - (k0*k0 - sigma)*X,

a rank-m correction of the shifted matrix. On the B-orthogonal complement of `Z` the operator `X` acts as zero, so `A_p` and `B_p` agree with `A` and `B` there, entry by entry, in exact arithmetic.

The projection must be B-orthogonal and not Euclidean. Two identities force this. First, for z in `Z` and y with Z^T B y = 0,

    Z^T B (B^{-1} A y) = Z^T A y = (A Z)^T y = k0*k0*(B Z)^T y = 0,

so the B-orthogonal complement is invariant under `B^{-1} A`, which is the operator whose eigenproblem this is. Second, every eigenvector of an eigenvalue other than k0*k0 satisfies

    (k0*k0 - lambda) * z^T B x = z^T (A x) - k0*k0 * z^T B x = (A z)^T x - (k0*k0 B z)^T x = 0,

so it is B-orthogonal to `Z` automatically, and deflation removes nothing that the physics needs. A Euclidean projection (Z^T Z)^{-1} instead of `G` has neither property: it changes the operator off the removed subspace and moves the kept eigenvalues by an amount that is not round-off. That is the specific error section 3 is built to catch.

Composition with shift-invert, and the trap. The projected shifted matrix is singular for every sigma:

    (A_p - sigma*B_p) z = (k0*k0 - sigma) B z - (k0*k0 - sigma) X z = 0   for every z in Z,

with nullspace exactly `Z`, because d = k0*k0 - sigma is not zero. A sparse LU of `A_p - sigma*B_p` therefore cannot be formed, and a Woodbury correction applied to the unprojected shifted matrix collapses: the correction is (1/d)*G - Z^T B (A - sigma B)^{-1} B Z = G/d - G/d = 0. The deflated problem must instead be posed on a complement basis `R`, of size n_dof by (n_dof - m), satisfying

    Z^T B R = 0,    R of full column rank,    R sparse,

after which

    A_c = R^T A R = R^T A_p R,    B_c = R^T B R = R^T B_p R,    A_c - sigma*B_c = R^T (A - sigma*B) R

is nonsingular whenever sigma is not a retained eigenvalue, which is the same hypothesis the undeflated solve already relies on. The `eigsh` call keeps its shape:

    eigsh(A_c, k=n_k, M=B_c, sigma=sigma, which="LM"),

with `n_k` and `sigma` unchanged. Reconstruction is x = R y, on the full free-edge vector, after which the existing loop runs exactly as before. The construction of `R` is not derivable from the code and is PROVISIONAL: the requirement stated above is binding, and whichever construction is used must be recorded with the run, together with the measured ||Z^T B R|| relative to ||Z^T B|| ||R|| and the conditioning of the m by m block used to build it.

Where the change lands. In `emfit/mode2d.py`, inside `solve_modes`, between forming `c_free` and `b_free` and the `eigsh` call: matrix arguments only. Nothing in `tools/host/anchor/ladder.py` changes. `build_mesh`, the call `mode2d.solve_modes(mesh, K0, SIGMA, eps_r=eps_call, boundaries=boundaries, k=K_CAND)`, `classify`, `apply_v2`, `matched_by_order` and the surplus and above-endpoint notes stay as they are, and the shift `SIGMA`, the level set and the candidate count of 16 [VERIFIED this session] are untouched.

### 2.d Why the physical spectrum is unchanged

Hypotheses, all of which must be checked and none of which is assumed silently:

- H1. `B` = `m_mu` is symmetric positive definite. This requires mu_r > 0 almost everywhere; the ladder uses mu_r = 1 [VERIFIED this session].
- H2. `Z` is an exact kernel of `A - k0*k0*B`: `k_q Z = 0` exactly, and `(m_eps - m_mu) Z = 0` because eps_r = 1/mu_r on the star of every selected node, as in 2.b.
- H3. sigma is not a retained eigenvalue, and d = k0*k0 - sigma is not zero. Here sigma = k0*k0/2 [VERIFIED this session], so d = 990434.5408581193 [VERIFIED this session] and the shift sits strictly between the third mode and the second.
- H4. No retained eigenvector lies in `Z`, that is no physical mode is a vacuum gradient. Observed effective permittivities at level 1 are 0.8491915816227373 and 0.4584816966495742 [VERIFIED this session], both far from 1.

Given H1 to H4, for every eigenpair with lambda not equal to k0*k0 the eigenvector satisfies Z^T B x = 0 by the second identity of 2.c, so x lies in the complement and the Rayleigh quotient of x for the pair (A, B) equals the Rayleigh quotient of x for the pair (A_p, B_p) exactly, because A and A_p and B and B_p agree there. The eigenvalues with lambda not equal to k0*k0 are therefore unchanged, as a set, and the ones the ladder cares about are unchanged as individual numbers. In exact arithmetic the statement is an equality; nothing is bounded, nothing is approximate.

What that argument does not give, and what must therefore be measured rather than asserted: how far the computed numbers can move in floating point. That distance is controlled by the two residuals of H2, both of which are round-off and neither of which is zero, so the run must report

    ||k_q Z|| / (||k_q|| * ||Z||),
    ||(m_eps - m_mu) Z|| / ((||m_eps|| + ||m_mu||) * ||Z||),
    ||A Z - k0*k0*B Z|| / ((||A|| + k0*k0*||B||) * ||Z||),

and the built dimension of `Z` against the structural count of 2.a. If `Z` is not the exact kernel, the equality above is false and the eigenvalues move by something other than round-off, which is exactly the reading section 3 supplies.

### 2.e Normalisation, and the ruling

The container contract wins. `Mode2D` documents e_t on the full edge list, normalised so that e^T B e = 1, and zero on PEC edges; `solve_modes` enforces it by dividing each candidate by sqrt(v @ (b_free @ v)). Deflation does not add a normalisation step and does not change that contract:

- `B_c = R^T B R`, so for x = R y the quadratic form is y^T B_c y = x^T B x. The existing division by sqrt(x^T B x) is therefore still the division by sqrt(x^T B x), and e^T B e = 1 still holds after the projection.
- A basis `R` that were Euclidean-orthonormal would break this silently, because y^T y would no longer equal x^T B x. That is why B-orthogonality of `R` is a requirement and not a convenience.
- No re-normalisation after the projection is added, because none is needed; adding one would be a second, unregistered change to the instrument.
- The ruling is unchanged. The classification reads the padded full vector, its curl ratio and its effective permittivity; it does not read the basis, does not read `Z`, and does not know that a projection happened.

## 3. The consistency check that comes free

Deflation removes an exact invariant subspace. No physical eigenvector lies in that subspace, so removing it leaves every physical eigenvalue where it was, and that statement can be tested without any reference solution: the pre-deflation run already wrote the numbers down.

The frozen set is the kernel-free part of the spectrum reported by the anchor run at levels 1, 2 and 3, read from `tools/host/anchor/records/level1.json`, `tools/host/anchor/records/level2.json` and `tools/host/anchor/records/level3.json` [VERIFIED this session]. Nine entries are frozen: five at level 1, two at level 2, two at level 3.

| level | beta | beta^2 | what it is |
| --- | --- | --- | --- |
| 1 | 1736.2570207158685 | 3014588.4419851443 | non-gradient state, the largest beta retained previously |
| 1 | 1636.5986739978343 | 2678455.2197314696 | fundamental |
| 1 | 1296.9723776897456 | 1682137.3484901919 | second mode |
| 1 | 952.9911948312771 | 908192.2174259451 | third mode, filed as surplus |
| 1 | none | -179735.7274530737 | negative eigenvalue in slot 16 |
| 2 | 1296.4632008496378 | 1680816.8311572883 | larger of the two, nearest the analytic second mode |
| 2 | 946.6516295409791 | 896149.3077125911 | smaller of the two, nearest the analytic third mode |
| 3 | 1296.3400089040304 | 1680497.4186853017 | larger of the two, nearest the analytic second mode |
| 3 | 945.1123879493056 | 893237.4258552386 | smaller of the two, nearest the analytic third mode |

Every tabulated value is [VERIFIED this session]. The analytic values, used here only to name the entries, are [RELAYED]: 1637.9985692980779 for the fundamental, 1296.2992799512633 for the second mode and 944.6029788248537 for the third. The run under this pre-registration must reproduce the tabulated values, not the analytic ones. The analytic values say what each tabulated value is; they are not a comparison target here.

### 3.a Why the frozen list is complete at each level

The window is the 16 eigenpairs nearest `sigma`. A non-kernel state nearer the shift than the farthest frozen entry would have occupied one of those 16 slots, and so would be in the records.

At level 1, 11 of the 16 slots are the cluster at beta^2 = k0*k0 exactly and the remaining five are the five level-1 entries above. Their distances from the shift are 82242.323432 (third mode), 691702.807632 (second mode), 990434.540858 (the cluster itself), 1170170.268311 (the negative eigenvalue) and 1688020.678873 (fundamental), with the non-gradient state farthest at 2024153.901127 [VERIFIED this session]. Nothing non-kernel closer to the shift than 2024153.901127 is unrecorded, so all five must reappear.

At levels 2 and 3 the cluster fills 14 of the 16 slots and the two frozen entries at each level are the two nearest non-kernel states, at distances 94285.233146 and 690382.290299 at level 2 and 97197.115003 and 690062.877827 at level 3 [VERIFIED this session].

### 3.b The rule

Each frozen value must reappear among the returned eigenpairs after deflation, satisfying

    |beta^2_def - beta^2_frozen| / max(1, |beta^2_frozen|) <= 1e-12,

and the same inequality written on beta. The value 1e-12 is fixed here, before the run, and is not adjustable afterwards: about 4500 times the double-precision unit round-off 2.2e-16 [RELAYED] and about nine orders of magnitude below the 2.0e-3 bound of section 4. It separates "nothing moved" from "something moved" without competing with the acceptance criterion.

### 3.c How a failure is read

Three readings.

- Present and within the bound: the projection is consistent with the recorded spectrum. This is an instrument result and not a verdict; the criterion of section 4 still has to be applied.
- Present but attached to a different reference order: membership is intact and the delta is of the order of the level-1 mode spacing, 339.626296 between the fundamental and the second mode and 343.981183 between the second and the third [VERIFIED this session]. That is the identification defect, which deflation does not touch (section 6).
- Absent from the list while other values moved: the projection is wrong. Read the size and the direction of the shift through codimension-m interlacing. A value that moved up lost content that lay above it in the spectrum, a value that moved down lost content that lay below, and the magnitude is bounded by the m-th gap. The mapping from a node of the interlacing pattern to "above" or "below" is PROVISIONAL, and is stated here as a reading order, not as a measured law.

One blind spot is recorded now. If `Z` is a strict subspace of the exact kernel then the removal is an under-removal: nothing physical moves, every frozen value reproduces, and the check above passes while the cluster has not been removed in full. The check never therefore stands alone. Two further numbers are reported with it: the built dimension of `Z` against the structural count of 2.a, and the residual ratios of 2.d, which vanish only if `Z` spans the kernel.

## 4. The acceptance criterion, inherited and unchanged

The criterion is not written here. It is transcribed from `docs/design/d46_acceptance.md` [VERIFIED this session], which froze it before this pre-registration and before any implementation, and which itself quotes the numeric thresholds from `docs/design/d45_anchor_results.md` as that file was committed in `61bd071`.

From section A of that file, unchanged in word and number:

- the order band 1.7 to 2.3;
- the absolute error bound at the finest mesh;
- by-order matching across all five levels;
- the fundamental must be present at every level;
- the two obligations deferred from v1 and never run, the mixed-path gate and the negative control;
- PASS / FAIL / FAILED-TO-MEASURE as the verdict vocabulary, with FAILED-TO-MEASURE meaning that the apparatus could not resolve the modes and requiring the same diagnostic treatment this one received.

From section B, the inherited numeric thresholds [VERIFIED this session]: the absolute bound 2.0e-3 at the finest level, monotonicity, and the requested candidate count of 16.

The configuration the criterion is applied to is unchanged: `EPS_R` = 2 [VERIFIED this session], `SIGMA` = 990434.5408581193 [VERIFIED this session], `LEVEL_NY` = {1: 16, 2: 32, 3: 64, 4: 128, 5: 256} [VERIFIED this session], `K_CAND` = 16 candidates requested per level [VERIFIED this session], the `EPS_EFF_TOL` filter on |eps_eff - 1| <= 1e-8 [VERIFIED this session], and the selection of the candidate of largest positive beta^2 among those the filter leaves [VERIFIED this session]. Deflation changes what is fed to those rules and nothing about the rules.

### 4.1 The criterion is not altered

Five statements.

- Deflation changes the instrument, not the bar. The band, the bound, the matching rule, the presence requirement, the candidate count and the level set are the ones d46 froze.
- 1e-12 in section 3 is an instrument check on the projection. It is not a term of the criterion, and passing it is not a partial pass of the criterion.
- The candidate count of 16 is not raised. Raising it would change how much of the window the filter sees and how many cluster states can fill it, and the measurements of section 1 are defined at 16.
- The two deferred obligations are not discharged here and are not declared unnecessary. They remain owed.
- No level is dropped and none is added. The criterion is applied at levels 1 to 5 as frozen.

## 5. Verdict vocabulary

Three verdicts, named before the run. There is no fourth.

- PASS. All five levels return the required numbers, every term of the criterion in section 4 is met, and the two deferred obligations are met. Passing section 3 is necessary for this and is not sufficient: section 3 says that the instrument did not move the physical spectrum, not that the spectrum matches the reference.
- FAIL. The numbers are present and at least one term of the criterion in section 4 is not met.
- FAILED-TO-MEASURE. The required numbers are absent, or a section 3 instrument check fails. This is d46's "the apparatus could not resolve the modes". It is not a softer FAIL and it is not a provisional FAIL: it costs the same diagnostic treatment the anchor run received. In the report that means the failed check named, every moved value with its size and its direction, the built dimension of `Z` against the structural count of 2.a, and the residual ratios of 2.d set beside the largest dropped curl ratios already measured, 2.6791731109636385e-10 at level 1 and 6.61052631017697e-09 at level 3 [VERIFIED this session].

### 5.a No relaxation

- No threshold is lowered, no band is widened, no candidate count is changed, no level is dropped and no level is added.
- The verdict is not deferred to a later dispatch and is not stated as a direction of travel.
- A reading that needs an exception to this section is at best FAILED-TO-MEASURE. Naming the exception in prose does not convert it into a PASS.
- Section 4 is not amendable from this file. The criterion belongs to `docs/design/d46_acceptance.md` and is applied as transcribed.

### 5.b Amendment rule

An amendment is a dated entry appended to this section. Each entry states the date, states what it replaces, and is written before the run whose reading it affects. No entry is written after a run whose numbers it would change. The frozen values of section 3, the 1e-12 bound, and section 4, are outside what an entry may alter.

### 5.b Amendment 1 (2026-10-28). ARPACK iteration budget for the deflated ladder

Dated 2026-10-28 and written before the run whose reading it affects. It replaces nothing in section 3, nothing in section 4, and it does not touch the 1e-12 bound.

The measurement that forces it. The deflated ladder was run at levels 1, 2 and 3. Levels 1 and 2 completed. Level 3 aborted inside the solve with

    ArpackNoConvergence: ARPACK error -1: No convergence
    (11351 iterations, 12/16 eigenvectors converged)

after 550.8 s of wall clock at 1.00 core, and wrote no record. The iteration count is not a property of the problem: 11351 = 10 * 1135 + 1, and 1135 is the deflated dimension at level 3, being 1464 free degrees of freedom less 329 gradient columns. The budget that was exhausted is ARPACK's default, maxiter = 10 * n, which the solve inherited from the library because the call in `emfit/mode2d.py` passes four keywords and no tuning arguments. No iteration budget was ever chosen by this pre-registration. A library default was inherited by it, and an inherited default is not a criterion.

What the entry adds. Levels 1, 2 and 3 are measured with an explicit ARPACK iteration budget of maxiter = 40 * n, where n is the deflated dimension of the level in question. ncv and tol stay at their SciPy defaults, so the Krylov space built per restart is unchanged and the only quantity that moves is how many restarts ARPACK may take before it gives up. For any run that converged below the old default the iteration sequence is identical, which is what makes the change inert at levels 1 and 2 rather than merely harmless: both levels finished well inside 10 * n.

It is not a relaxation. No threshold is lowered, no band is widened, no candidate count is changed, no level is dropped and no level is added. The frozen values of section 3, the 1e-12 bound, and the criterion of section 4 are applied exactly as transcribed, and the level 3 readings are judged by them unchanged. An iteration budget is not a verdict quantity. It is the cost of asking the question, and the question is asked once.

Where the change lives. The budget is injected by rebinding `emfit.mode2d.eigsh` inside the scratch driver `.scratch/d47/run_deflated.py`, the same way that driver already rebinds `emfit.mode2d.solve_modes`. `emfit/mode2d.py` is not edited and remains byte-identical. The rebind is process-local and restored in a finally block.

Inertness, to be shown and not asserted. Levels 1 and 2 are re-measured under the rebind and the seven check 1 rows of the acceptance document are re-applied to the same 1e-12 bound. Any movement there voids this entry and the reading that depends on it.

If 40 * n is also exhausted at level 3, the level 3 reading is FAILED-TO-MEASURE under section 5.a and is recorded as such, with no second budget and no further attempt without a new dated entry.

### 5.b Amendment 2 (2026-10-28). Pairing rule for the deflated ladder: slab-region extension of Z, and a criterion that can fail

Dated 2026-10-28 and written before the run whose reading it affects, under dispatch 48. It replaces nothing in section 3, nothing in the 1e-12 bound, and nothing in section 4. The text it points at is frozen in `docs/design/deflation_v2_preregistration.md`, sections 1 and 3, committed before any run that uses it.

What failed, and what did not. The by-order criterion of section 1 failed at dispatch 47. Eleven candidates appeared above the physical roots: level 1 at indices 0, 1 and 2, level 2 at indices 0 through 7, at eps_eff = 2 and beta^2 = 3961738.16343248 = 2 * k0^2 [VERIFIED this session]. The position shift is 3 at level 1 and 8 at level 2, and positional pairing paired the analytic ladder against members of that family. The solver did not fail: the seven frozen rows reproduced within the 1e-12 bound, worst residual 1.0525169405629708e-14 [VERIFIED this session]. The criterion failed and the arithmetic did not.

Why it failed. Positional matching presumes that the candidate count and the candidate ordering track the analytic ladder. Any additional family breaks the first premise, and on this pass three extra members appeared at level 1 and eight at level 2, upstream of every physical root, so the second premise went with it. The ladder is in any case not a clean bijection with the candidate list, because one frozen row has no beta at all: the frozen table of section 3 records the level 1 slot 16 row as `none`, with a negative beta^2 of -179735.7274530737, an evanescent branch rather than a propagating root. No index arithmetic recovers a pairing across that. A pairing rule that cannot mis-pair is not a rule, it is an assumption.

What the entry adds. Two things, both frozen in the v2 document. First, `Z` is extended from the interface line to the whole slab region, so the projection removes the family that this dispatch is measuring and not only the vertical-gradient family it was built for (v2 section 1). Second, the by-order pairing rule of section 1 is replaced by one that can fail: a candidate is paired with an analytic mode only when it satisfies a stated, falsifiable test, and a candidate satisfying no test is recorded as unpaired instead of being assigned to the nearest free slot (v2 section 3). Both are written before the run and neither may be adjusted after it.

It is not a relaxation. Section 5.a stands unaltered: no threshold is lowered, no band is widened, no candidate count is changed, no floor is relaxed anywhere, and no level is dropped or added. The seven frozen rows keep their 1e-12 bound. The level 3 ARPACK budget stays at 40 * n under Amendment 1, with n = 1135 = 1464 - 329, and no increase to that budget is authorised by this entry. Levels 4 and 5 remain out of scope.

What this entry does not do. It does not validate the dispatch 47 pass retroactively. That pass stays recorded as having failed the by-order criterion, and its numbers are not read as a measurement of the analytic modes. This entry changes what the next run is judged by; it does not change what the last run did.

The sha256 of this document immediately before this entry was appended: `9ea938f520ae89593219dfdbd8fc8f109e6d6616aef45e14a29d60d6f3fe2308` (280 lines, 30426 bytes).

## 6. What this fix does not fix

- The mixed path. `solve_modes_mixed` is unchanged and does not pass through the projection. It solves a different pencil, `A x_t = beta^2 B x_t` with `A = k0^2 m_eps - k_q` and `B = m1 - c D c^T`, and its normalisation cannot be the edge-only `e^T B e = 1`, because that `B` is indefinite [RELAYED]. A transverse gradient field is not a null vector of the block system there: it carries an `e_z` partner and the coupling does not annihilate it, since `c^T Z = k_zz phi` is nonzero. The mixed-path kernel, and so its dimension, is PROVISIONAL, and no number for it is frozen here.
- Identification. The level-1 non-gradient state at beta = 1736.2570207158685 is not in the kernel and survives deflation. The order-1 mismatch recorded in section 1 therefore persists, with relative deviation 5.998690e-02 [VERIFIED this session]. A correct projection does not by itself make order 1 correct.
- Accuracy. The physical eigenvalues are unchanged, so the accuracy of a correctly identified mode is unchanged. Deflation buys window slots, not digits.
- Levels 4 and 5. No prior numbers exist at those levels, so section 3 constrains levels 1 to 3 only. A failure at levels 4 and 5 is visible through the criterion of section 4 and not through the frozen set.
- Cost. `m` rises to about a quarter of the free DOF, 0.243783 at level 5 against the limit 1/4 [VERIFIED this session], and the complement basis `R` adds setup work that the unmodified code does not pay.
- The d45 erratum. The sign of `log10(D/R)` in the d45 results file is untouched here and remains to be corrected on its own terms.
- The filter. `EPS_EFF_TOL` = 1e-8 stays in the code, even though by section 7 it will have nothing to drop at levels 1 to 3.

## 7. Predictions the run will test

Made before any run of the modified solver. Each one is falsifiable by a number the run reports.

1. All nine frozen values of section 3 reappear, each within the 1e-12 bound, on beta and on beta^2.
2. No candidate at levels 1 to 3 has |eps_eff - 1| <= 1e-8, so the effective-permittivity filter drops nothing there.
3. The built dimension of `Z` is 11, 69, 329, 1425 and 5921 at levels 1 to 5 respectively.
4. The residual ratios of 2.d are round-off relative, of the same order as the largest dropped curl ratios already measured, 2.6791731109636385e-10 at level 1 and 6.61052631017697e-09 at level 3 [VERIFIED this session].
5. The fundamental appears among the returned candidates at levels 2 and 3, and at least three states are retained at each of those levels, against 2 of 16 today.
6. The level-1 order-1 mismatch persists, and the largest beta retained at level 1 is still 1736.2570207158685.
7. Levels 4 and 5 produce numbers, or the verdict is FAILED-TO-MEASURE.
8. The mixed-path numbers are unchanged, because that path is untouched.

A run that contradicts one of these eight statements is a result and is reported as one. It is not grounds to adjust section 3, section 4 or this list.

### 5.b Amendment 3 (2026-10-28). The task 1 analytic census, frozen, and the widened preservation set

Dated 2026-10-28 and written before any line of the extension is written, under dispatch 49 of `docs/design/d49_acceptance.md`, criterion AC2.1. It replaces nothing in section 3, nothing in the 1e-12 bound, nothing in section 4 and nothing in section 5.a. It adds one licence and one widened preservation set, and it removes no check.

What was measured, and what was not. The census is read-only and asks the analytic side one question. It calls the validated reference routine `tools/host/anchor/anchor_reference.py` at geometry A, `t = b/4` with `eps_r = 2`, and it calls no solver: nothing under `emfit/`, `tests/` or `tools/` is written or edited by it. Every value below is [VERIFIED this session] by that run and is re-derivable from the driver `.scratch/d49_task1_census.py` and its log `.scratch/d49_task1_census.txt`. The band `T1`, the factor of 10 and the budget `40 * n` are [RELAYED] from the entries that set them and are not recomputed here.

    k0              = 1407.4335088082273
    b, t, L2        = 0.0078125, 0.001953125, 0.005859375
    eps_r           = 2.0
    2 * k0^2        = 3961738.163432477    (the target)
    sqrt(eps_r)*k0  = 1990.411556294948    (domain endpoint, and the square root of the target)
    window          = [0, 2985.617334442422] = 1.5 * sqrt(eps_r) * k0

The window, and why it is wide enough. The target `beta^2 = 2*k0^2` sits at `beta = sqrt(2)*k0` = 1990.411556294948 [VERIFIED this session], which at `eps_r = 2` is the domain endpoint `sqrt(eps_r)*k0` itself, so a window that stopped there would put the target on its own edge. This one runs to 2985.617334442422, which is 995.20577814747389 beta units past the target [VERIFIED this session], and the region past the endpoint is proved root-free below by an exact argument rather than by a scan. Below the target the window contains the whole pole structure, at cut points 911.5793030029113, 1172.382440722014, 1301.305505138204 and 1407.4335088082273 [VERIFIED this session], and it contains roots on both sides of the last pole. The edge is not doing any of the work.

The census result, as frozen numbers. Three roots exist in the window [VERIFIED this session]. Each carries the achieved precision AC1.2 requires, `|f|/|f'|` at the root:

    idx  beta                   beta^2                eps_eff                |f|/|f'|
      0  944.60297882485338      892274.78760478646    0.45044611773722776    2.177e-13
      1  1296.2992799512631      1680391.8232021632    0.8483103899760305     1.501e-13
      2  1637.9985692980779      2683039.3130225502    1.3544758398156966     1.424e-14

The effective permittivity there is `beta^2 / k0^2` with `k0^2` = 1980869.0817162385 [VERIFIED this session by arithmetic on the two columns], so roots 0 and 1 sit below `eps_eff = 1`, root 2 sits at 1.3544758398156966, and none of the three sits at the target's `eps_eff = 2`.

What is not a root, and how that was decided. Three sign changes of the dispersion function are pole artefacts and are rejected: 911.5793030029113, 1172.382440722014 and 1301.305505138204, where the term scale reaches 7.002162e+17, 1.329552e+18 and 6.447989e+16 [VERIFIED this session], against a rejection threshold of 1e9. The scan is invariant across a density ladder of 20, 50, 100, 500 and 5000 points per beta unit, returning three accepted roots and three rejected pole candidates at every density [VERIFIED this session]. An independent complex-form evaluation of the relation agrees with the dispersion form to 9.095e-13, maximum difference over 4001 points [VERIFIED this session].

AC1.2, answered. No root exists at or near `beta^2 = 2*k0^2`. The nearest is index 2:

    beta^2 - 2*k0^2       = 1278698.8504099268   (|delta|, absolute)
    relative              = 0.32276208009215163
    in beta units         = 352.41298699687013   (|beta - sqrt(2)*k0|)
    root precision        = 1.424e-14            (|f|/|f'| at idx 2)
    distance / precision  = 2.475e+16
    relative test 2e-2    : NO root
    relative test 1e-3    : NO root
    relative test 1e-6    : NO root
    smallest relative distance over all roots = 0.32276208009215163

AC1.3, answered, with a defect in the criterion stated rather than absorbed. AC1.3 as worded asks whether any analytic root lies within the calibrated band the curl test used, `T1` = 2.6791731109636385e-09 [RELAYED], itself carried with `g` unresolved. `T1` is a threshold on a dimensionless curl ratio: it is neither a `beta` tolerance nor a `beta^2` tolerance, and it cannot be applied to a census of roots. The criterion as literally worded is therefore unevaluable, and this entry records that instead of substituting one quantity for another.

The gate was instead evaluated as pure relative `beta^2` tests at 2e-2, 1e-3 and 1e-6, and the curl band was not borrowed as a `beta` tolerance [VERIFIED this session]. The answer does not depend on the choice of reading. The nearest root is 0.32276208009215163 of `2*k0^2` away, a factor of 16.13810400460758 outside the loosest of the three tests, and even reading `T1` as a relative `beta^2` tolerance - the strictest and least defensible reading available - that distance is 120470782.11234412 times outside it. No reading of AC1.3 reverses the verdict, so the defect does not change the outcome of this dispatch. It must still be repaired before AC1.3 is cited as evaluated by anything other than a relative `beta^2` test.

Even multiplicity is excluded separately, because a sign-change scan cannot see a tangential root:

    interval                       roots  min|f_norm|        at beta
    [    0.000000,   911.579303]   0      no interior local minimum
    [  911.579303,  1172.382441]   1      no interior local minimum
    [ 1172.382441,  1301.305505]   1      no interior local minimum
    [ 1301.305505,  1407.433509]   0      9.497721575e-01     1407.4334722557753
    [ 1407.433509,  1990.411556]   1      no interior local minimum
    [ 1990.411556,  2985.617334]   0      1.363782751e+00     1990.411606304026

The global floor is `min |f_norm|` = 9.497722e-01 at `beta` = 1407.4334722557753 [VERIFIED this session], which is not near zero on any scale that would read as a tangency, and four of the six intervals have no interior local minimum at all. Even-multiplicity roots are excluded to the resolution stated here, and not absolutely, and the limits the exclusion inherits are recorded rather than repaired. Local minima within 5e-3 of an accepted root were masked by the detector, so a tangency that close to a simple root is masked and not refuted. The scan cell is 4.6e-3 to 5.0e-3 in `beta` on the wide intervals, against a feature scale of the relation of about `1/k0` = 7.1e-4, so a tangency narrower than one cell could in principle pass between samples. Neither limit is a plausible competitor to a floor of 0.9497722. The census also covers real `beta >= 0` only: complex roots were not enumerated, and the solver candidates under test are real, which is what makes the comparison apt. Complete, where this entry uses the word, means numerical plus analytic and not theorem, and the word is not used to claim more than that.

The endpoint degeneracy, reported and not resolved. At the target itself the relation is `0/0`: `d1 = eps_r*k0^2 - beta^2` vanishes at `beta = sqrt(eps_r)*k0`, so `s1/tan(s1*t)` is `0/0` there and the dispersion form returns `nan`. The singularity is removable, with limit

    1/t                     = 512.0
    k0*coth(k0*L2)          = 1407.4337022196212
    limit                   = 1919.4337022196212

A delta ladder from `delta = 1e-1 * k0` down to `1e-12 * k0` approaches that limit from below with `f` positive at all seven steps, largest `|f - limit|` = 6.194620e+02 at the coarsest step [VERIFIED this session]. The eleven spurious solver candidates of dispatch 48 sit at exactly this `beta`. No claim is made here that the degeneracy causes them; it is recorded because the analytic relation is undefined at the single point where the target sits, and a root there would be degenerate rather than simple. The census result at the target is therefore a statement about a removable 0/0, not about a simple root that fails to exist, and it is read that way in what follows.

Above the endpoint, no root exists for any beta. For `beta > sqrt(eps_r)*k0` both arguments are imaginary and the relation is a sum of two strictly positive terms:

    term1 = s1*coth(s1*t)    min = 5.120129e+02   (> 0)
    term2 = s2*coth(s2*L2)   min = 1.407441e+03   (> 0)
    sum over the scanned range: min = 1.919454e+03, max = 4.859162e+03, sign changes = 0

This is an exact argument about the sign of both terms and not a sampling result, so the window's upper edge truncates nothing and no root can be missed above the endpoint.

The widened preservation set. AC1.4 asks how many analytic roots the window contains, and the count is 3 [VERIFIED this session]. Every one of them must reappear after extended deflation within the existing 1e-12 bound, reported root by root with its frozen value, its returned value and its deviation:

    idx  frozen beta^2            frozen beta            eps_eff
      0  892274.78760478646       944.60297882485338     0.45044611773722776
      1  1680391.8232021632       1296.2992799512631     0.8483103899760305
      2  2683039.3130225502       1637.9985692980779     1.3544758398156966

The seven frozen rows of section 3 are not a substitute for this set. Whether those rows are a subset of it is a question about the rows, and it is not asserted here. A preservation claim narrower than all three roots - whether it stops at the seven rows, or at the rows plus whichever roots happened to reproduce - is a failure of this section and is not a partial success.

The licence, and how narrow it is. The extension of `Z` contemplated by dispatch 49 is licensed by this census and by nothing else, and only for geometry A at `t = b/4` and `eps_r = 2`. It says nothing about any other geometry, aspect ratio, permittivity, mesh or level set. No other geometry may inherit it: each requires its own census and its own dated entry before any line of an extension touching it is written.

The licence is void, and section 1 returns to provisional, on any one of four events: a change to the geometry; a later census that finds a fourth root in the window; a later census that finds a tangential root; or a disagreement with this census on re-running it. They are listed so that they cannot be quietly ignored.

It is not a relaxation. No threshold is lowered, no band is widened, no candidate count is changed, no floor is relaxed anywhere, and no level is dropped or added. The 1e-12 preservation bound is unchanged and is now applied to a larger set. The band factor of 10 stands, `T1` stands with `g` unresolved, the level 3 budget stays at `40 * n` under Amendment 1, and levels 4 and 5 remain out of scope. The census adds a check and removes none.

What this entry does not do. It does not show that the extension works: that is Task 2 and the level 1, level 2 and level 3 runs, and this entry is written before any line of it exists. It does not validate the dispatch 47 or dispatch 48 passes retroactively, and their numbers are not re-read as measurements of the analytic modes. It does not resolve `g`, which stays disputed between two documents and non-blocking. It does not convert the endpoint degeneracy into an explanation of the spurious family. And it does not make the census a formality: a geometry that fails it stops the dispatch, as section 7 of the acceptance document requires.

The sha256 of this document immediately before this entry was appended: `9fbfaf67030fb25724b0f271436e3122bae9f02bc9651e1aaf8f573dc1b979b2` (296 lines, 33785 bytes).
