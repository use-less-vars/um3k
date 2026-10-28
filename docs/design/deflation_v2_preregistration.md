# Deflation v2 pre-registration: extending `Z` to the slab region, and a by-order rule that can fail

Dated 2026-10-28. Frozen on commit: the commit that first contains this file is the freeze. From that moment nothing in it is editable in place. The extension of section 1, the preservation check of section 2, the by-order rule of section 3, the level-3 expectation of section 4, the frozen numbers of section 5 and the record of section 6 are all fixed before any v2 solve exists, and the readings they govern are the ones that run produces.

This document pre-registers a second solver change. It does not change the acceptance criterion of `docs/design/d46_acceptance.md`, the ladder geometry, the material parameters, the candidate count, the level set or the selection rule. It extends the subspace removed by deflation v1 and it replaces the implementation of by-order matching. Both changes are recorded as an amendment in section 6 before the run they govern.

Provenance tags, as in `docs/design/deflation_preregistration.md`: [VERIFIED this session] means the claim was read out of the tree this session by direct read of the cited `file:line` or recomputed by arithmetic on such reads. [RELAYED] means the number is carried from an earlier dispatch or from the d48 Task 1 report and is not reproduced here.

## 0. Inputs, with hashes

Read at the freeze. A later difference in any hash means this document is being read against a different tree than the one it was written against, and the readings below do not carry over.

| artefact | sha256 |
| --- | --- |
| `docs/design/deflation_preregistration.md` (296 lines, includes Amendment 2) | `9fbfaf67030fb25724b0f271436e3122bae9f02bc9651e1aaf8f573dc1b979b2` |
| `docs/design/d48_acceptance.md` | `41cb1ee16b9058514d2fda9719530e5d1f9443993eb4834b3df5b59dfa905b52` |
| `.scratch/d48/classification.md` (Task 1 result) | `631944493fd5d91e76abd7d6dee76a695b4d5866daf7a3fbbfccd5302b662589` |
| `docs/design/d47_results.md` | `718d0dc67360ba9b94158732d0d03938f11423173b6427928a5b2d6af076eb78` |
| `docs/design/d47_acceptance.md` | `7000971eaca167e9cf5380c878d203c7965fb74c33ade4889ad3761c856544d0` |
| `docs/design/d46_acceptance.md` | `53515e67358120b4714ef74492903e8ff4f89a918186fcd2d480b39b1425cd22` |
| `docs/design/anchor_preregistration.md` | `9461e5c4c631cb934d37b7b69b50ebff7ed9eadffe9740b6b3e50c353f0648f2` |
| `emfit/mode2d.py` (1813 lines) | `0d0c9695d99c996ffa48cffa0eb58cb7bba93064bd5f2828bcd7c807fccdebdb` |
| `tools/host/anchor/ladder.py` (794 lines) | `210ab59c2a668798629a95bb4ef74590412a57be9b5cc48b391eedac5b39aebd` |
| `tools/host/anchor/records/level1.json` | `4824369de524d916e0744ac2ed6d28a158841c8dc6ef024c6b98a6c3ff670af9` |
| `tools/host/anchor/records/level2.json` | `ab592077ab235f8fa079d9df5392502195c2cf9586670bf559597dc4564a064f` |
| `tools/host/anchor/records/level3.json` | `7a10ef3b9ba7aab9619fdbb0b6d26971ec2dab6eefa79ea44cdf0cde91fca129` |
| `.scratch/d47/run_deflated.py` (190 lines) | `e278cc6c3eebcaacb66cc1b627e11cd72cb2b41973c1d9c237f8ead6b957cd66` |
| `.scratch/d47/out/deflated_level1.json` | `d4e956d99dd14977767acccdc7d114e1621da91217ea8dc35059bd069ddfea56` |
| `.scratch/d47/out/deflated_level2.json` | `84315b3214de4ee3c26c1cfaaa28684d7f53644bd7a35a94e59bb5ce74dd1eef` |

Every hash above is [VERIFIED this session]. The v1 pre-registration hash is the one this document is an extension of, and the copy it hashes is the post-append copy: it carries Amendment 2, the section 5.b entry that records this extension and was written before the run it governs. The Task 1 hash is the evidence this document rests on and is not re-litigated here.

## 1. The extension

### 1.a What is being extended, in the names the code uses

The v1 object is `Z`, built inside `solve_modes_deflated` at `emfit/mode2d.py:1296-1297` from two calls:

    cols = _gradient_columns(mesh, eps_t, mu_t, pec_node_mask(mesh, boundaries))
    z    = _incidence(mesh, free, cols)

`_gradient_columns` (`emfit/mode2d.py:1014`) selects the nodes whose whole star passes one predicate, at `:1044`:

    on_region = np.abs(eps_t - 1.0 / mu_t) <= float(region_tol)

with `region_tol = 0.0` by default (`:1019`), i.e. exact equality, and with the PEC nodes removed at `:1049`. `_incidence` (`:1052`) then puts `+1`/`-1` on the edges running into or out of each selected node, which is the edge-DOF pattern of the P1 nodal gradient (`:1055-1060`). The rows are the `free` edges of `solve_modes`.

The predicate is written as a comparison against the constant `1`. That constant is the ratio `eps_t/mu_t` of the *vacuum* region, and the whole of v1's algebra rests on the single number `k0*k0` because that ratio is 1. The slab of the ladder has `eps_r = 2`, `mu_r = 1`, so its ratio is 2, the predicate at `:1044` is false on every slab triangle, and no slab node is selected. That is the entire reason v1 does not remove the family at `beta = sqrt(eps_r)*k0` — not a threshold, not a filter: the subspace was never built there. The frozen drop rule at `tools/host/anchor/ladder.py:144` is a separate matter and is untouched by this document; the family is not a dropped candidate and this document does not call it one.

### 1.b The extension

Replace the constant `1` by the ratio itself, per column. For node `i`, let `r_i = eps_t[T]/mu_t[T]` for one triangle `T` in the star of `i`, and require every triangle in the star to satisfy `|eps_t - r_i*mu_t| <= region_tol` with `region_tol = 0.0`. The predicate at `:1044` is the special case `mu_t = 1`, `r_i = 1`; the air block is unchanged, bit for bit, and the new block is the same construction at `r_i = 2`.

On the ladder the two values are exactly the two constants of the material callable: `1.0` above `y = t`, `EPS_R = 2` below. The callable is `lambda c: np.where(c[:, 1] < t, EPS_R, 1.0)` at `tools/host/anchor/ladder.py:113`, the permittivity is `EPS_R = 2.0` at `tools/host/anchor/anchor_reference.py:26`, and the thickness is `T = B / 4.0` at `tools/host/anchor/anchor_reference.py:25`, which is `t = 0.001953125`. The y-grid is `ys = B * np.arange(ny + 1) / ny` at `tools/host/anchor/ladder.py:109`, and `build_mesh` refuses a mesh on which `y = t` is not a node line (`tools/host/anchor/ladder.py:111-112`). It is one whenever `ny` is a multiple of 4, and `LEVEL_NY = {1: 16, 2: 32, 3: 64, 4: 128, 5: 256}` at `tools/host/anchor/ladder.py:57` is. The stored level-1 log confirms it on the built mesh: `node line at y = t exactly: indices [4]` at `tools/host/anchor/records/level1.log:46-47`, and `4 = ny/4` there. Hence `t` lies on the node row `j = ny/4` at every level, no triangle straddles the interface, and `r_i` is constant within each block.

**The quarter is code-derived, not assumed, and the distinction is drawn here rather than left to be inferred.** The chain is `T = B/4` (`anchor_reference.py:25`), the uniform y-grid (`ladder.py:109`), the exactness assertion (`ladder.py:111-112`) and the slab predicate `y < t` (`ladder.py:113`); v1 used the same chain on the air side to get its `3*ny/4 - 1` rows (`docs/design/deflation_preregistration.md:45`). What is *not* read off a line of code is the count: `(nx - 1)*(ny/4 - 1)` is my arithmetic on `nx = ny//8` (`ladder.py:106`) and on the row set below. That arithmetic is exact given those lines and is not PROVISIONAL in the sense of 1.f, but it is a derivation that closes only if the run's built `z_dim` equals it, which is what §2.b requires; the count is therefore tested by the run and not merely asserted here.

The added columns are the nodes with `y < t` that are not on a PEC predicate: rows `j = 1 .. ny/4 - 1` and columns `i = 1 .. nx - 1`. Row `j = 0` is the PEC boundary `y = 0` and row `j = ny` is `y = B` (`ladder.py:115-116`); the row `j = ny/4` lies on the interface, its star straddles both regions, and neither block selects it — that exclusion is P2 in 1.f. Columns `i = 0` and `i = nx` are the PEC boundaries `x = 0` and `x = A` (`ladder.py:117-118`). The count is

    (nx - 1)*(ny/4 - 1) = 3, 21, 105, 465, 1953   levels 1 to 5

against the air block's `(nx - 1)*(3*ny/4 - 1) = 11, 69, 329, 1425, 5921`, so the built total is

    z_dim = 14, 90, 434, 1890, 7874   levels 1 to 5

**Levels 4 and 5 in those two lines are formula evaluation only — not computed, not run, outside dispatch 48 scope.** They are what the closed forms give at `ny = 128` and `ny = 256`; no mesh was built, no deflation was attempted and no record exists at those levels, and the deflated dense route is capped at `_DEFLATED_DENSE_MAX = 6000` (`emfit/mode2d.py:1000`) against level 4's 6000 free DOFs and level 5's 24288 (`docs/design/deflation_preregistration.md:26`), so neither level can be attempted by the current implementation at all. v1 already froze `1425` and `5921` as a prediction at those levels (`docs/design/deflation_preregistration.md:273`); this document re-evaluates the same formula for arithmetic continuity and adds no claim about levels 4 or 5 anywhere. Every number in this document that is frozen, tested or predicted is at levels 1 to 3.

[VERIFIED this session by arithmetic on `nx = ny//8` at `tools/host/anchor/ladder.py:106` and `LEVEL_NY` at `:57`, and on v1's count `m = (nx-1)*(3*ny/4 - 1)` at `docs/design/deflation_preregistration.md:47`]. At level 1 the count 3 is the number of members of the family the d47 level-1 record holds, three of them [RELAYED]; the agreement is a consistency, not a proof, and it does not repeat at level 2, where the added block has 21 columns and the record shows 8 members [RELAYED] because the window is 16 slots wide and the slab cluster sits furthest from the shift.

### 1.c The kernel identity, and why it is exact here

For a column `z_i` of either block:

- `k_q z_i = 0` exactly. `z_i` is an incidence column and `k_q` is assembled from the curl of Whitney forms, so this is `d1*d0 = 0` in integer arithmetic, exactly as in v1 (`docs/design/deflation_preregistration.md:61`).
- `m_eps z_i = r_i * m_mu z_i` exactly. Both mass matrices are scattered from the same per-triangle local mass at `emfit/mode2d.py:459-467`, differing only by the factors `eps_t` and `1/mu_t`. On the star of a selected node those factors are the constants `2.0` and `1.0`, and multiplication by `2.0` is exact in binary floating point, so the entries of `m_eps - 2*m_mu` on those triangles are exactly `0.0`, not round-off.

Hence `(A - r_i*k0*k0*B) z_i = 0` exactly, with `A = k0*k0*m_eps - k_q` and `B = m_mu` as in `solve_modes_deflated:1291-1292`. Each added column is an exact eigenvector direction of the pencil with Rayleigh quotient exactly `r_i*k0*k0`, which for `r_i = 2` is `3961738.16343248 = 2*k0*k0` — the value the record reports for the family [RELAYED]. This is why the extension is the right object and not a filter: the family's eigenvalue is not approximately `eps_r*k0*k0`, it is exactly the pencil's value on the added columns.

### 1.d Two blocks, one scalar each

Let `Z = [Z_a, Z_s]` with `r_a = 1`, `r_s = EPS_R`. Write `G = Z^T B Z`, `X_b = B Z_b G_b^{-1} Z_b^T B`. Three hypotheses, all of which must be checked and none assumed silently:

- K1: `k_q Z = 0` exactly (1.c).
- K2: `(A - r_b*k0*k0*B) Z_b = 0` exactly for each block (1.c).
- K3: `Z_a^T B Z_s = 0` exactly. This holds structurally: an edge incident to an air-interior node and an edge incident to a slab-interior node are never in the same triangle, because the two node sets are separated by the interface row `j = ny/4` and no triangle straddles it. It is nevertheless to be measured (§2), because a structural argument that is not checked is an assumption.

Given K1 to K3, `G = diag(G_a, G_s)` and v1's algebra at `docs/design/deflation_preregistration.md:68-84` carries over with one scalar per block:

    Z^T A Z = k0*k0 * diag(r_a*G_a, r_s*G_s)
    A_p = A - k0*k0*(r_a*X_a + r_s*X_s),    B_p = B - X_a - X_s
    A_p - sigma*B_p = (A - sigma*B) - (r_a*k0*k0 - sigma)*X_a - (r_s*k0*k0 - sigma)*X_s

[VERIFIED this session: the derivation is the v1 one with `R = diag(r_a*I, r_s*I)` commuting with `G^{-1}`, which is what K3 buys]. The shifted projected matrix is singular on each block for every `sigma`, since `k0*k0 = 1980869.0817162385` and `r_s*k0*k0 = 3961738.16343248` are both different from `sigma = 990434.5408581193` [VERIFIED this session]. The complement basis `R` is built exactly as in v1 and exactly as `_complement_basis` already builds it (`emfit/mode2d.py:1143-1217`): Cholesky `B = L L^T`, full QR of `L^T Z`, `Q` the trailing `n - m` columns, `R = L^{-T} Q`, which gives `Z^T B R = 0` and `R^T B R = I` for the concatenated `Z` without any knowledge of the block split. The `eigsh` call keeps its shape (`:1319`), `n_k = 16` and `sigma` unchanged.

One consequence for the implementation, recorded so it cannot be discovered later: `_complement_basis` takes `Z` whole and needs no change; `_gradient_columns` must return the per-column ratio as well as the column index, because the diagnostic residuals at `:1331-1339` currently subtract the single scalar `k0*k0` and would be wrong for the slab block. They must be computed per block against `r_b*k0*k0`. Nothing else in `solve_modes_deflated` moves.

### 1.e The argument that no physical mode is removed

For any eigenpair `(lambda, x)` of `(A, B)` with `lambda` not equal to `k0*k0` and not equal to `EPS_R*k0*k0`, and for any column `z_i` of either block:

    z_i^T A x - lambda * z_i^T B x = 0
    z_i^T A x = (A z_i)^T x = r_i*k0*k0*(B z_i)^T x
    =>  (r_i*k0*k0 - lambda) * z_i^T B x = 0
    =>  z_i^T B x = 0

so such an eigenvector lies in the `B`-orthogonal complement of both blocks, where `A_p = A` and `B_p = B` entry by entry, and its Rayleigh quotient is unchanged exactly. This is v1's argument (`docs/design/deflation_preregistration.md:86-94`) applied twice. It is an equality in exact arithmetic, not a bound. The eigenvalues other than `k0*k0` and `2*k0*k0` are unchanged as a set, and the ones the ladder reads are unchanged as individual numbers.

What the argument does not give is how far the computed numbers move in floating point; that is measured, not asserted, by the three residuals of v1 §2.d computed per block, plus `||Z_a^T B Z_s||_F / (||Z_a^T B||_F ||Z_s||_F)` for K3.

### 1.f The step that is not rigorous

Two steps are not rigorous, and both are marked PROVISIONAL here rather than absorbed into 1.e.

**P1 — membership is inferred, not proved.** 1.e removes exactly the states at `lambda = k0*k0` and `lambda = EPS_R*k0*k0`. That the *observed* family is in the second class is not established by 1.c. Task 1 established that the family members are curl-free at round-off — absolute curl ratios from `4.704e-23` to `8.849983581104381e-10`, all below the calibrated band `T1 = 2.679e-9` built from the 11-member `k0` gradient family, `g = 2.6791731109636385e-10` [RELAYED] — and that their effective permittivity is `2`, which is `eps_r` [RELAYED]. A curl test is a test on the range of the curl operator; it does not test the range of `Z_s`. The measurement that would close the gap is the `B`-projection fraction of each candidate onto `Z_s`, `||Z_s G_s^{-1} Z_s^T B x||_B / ||x||_B`, which no run in this tree has reported and which this document does not claim exists. The precise non-rigorous step is therefore: from "curl-free to round-off and `eps_eff = 2`" to "in the column span of the added block".

The consequence is asymmetric and must be stated with it. If P1 is false in the harmless direction, the extension removes nothing new: the family survives, section 2.b fails, and the by-order rule of section 3 and the level-3 expectation of section 4 remain untested but not contradicted. If P1 is false in the harmful direction — a physical mode sitting at `beta^2 = 2*k0*k0` — the projection annihilates it, and the preservation check of section 2 cannot see it, because every frozen value is at `beta <= 1736.2570207158685 < 1990.411556294948`. That failure mode is visible only through the criterion of section 4 and the by-order rule of section 3, at whatever level it bites. This is why section 2 is not permitted to stand alone.

**P2 — `Z_s` does not span the whole discrete gradient space.** The discrete gradient subspace also contains the nodal functions of the interface row `j = ny/4`, whose stars straddle both regions and which satisfy neither K2 condition. Those columns are in neither block. If the observed family carries any interface-node content, the removal is an under-removal: nothing physical moves, every frozen value reproduces, and the family survives at reduced multiplicity. This is v1's blind spot (`docs/design/deflation_preregistration.md:188`) restated for the new block, and it is the reason the built dimension is reported against the closed form rather than trusted.

**What PROVISIONAL covers, exactly.** It covers the claim that the extension removes this family *in full*. It does not cover the claim that whatever the extension removes is removed without moving any eigenvalue other than those at `k0*k0` and `EPS_R*k0*k0` — that part is 1.e and is exact given K1 to K4. A run that shows a partial removal is not a refutation of 1.e; it is a refutation of P1 or P2, and it is recorded as such.

### 1.g Scope: what this section does not generalise to

- Values that differ per column. If `r_i` is not constant within a block, `Z^T A Z` is not a scaled `G` and the two-scalar algebra of 1.d does not hold; the case is outside this pre-registration. The implementation must assert constancy per block and report a failure rather than proceed with a wrong projection.
- Anything other than `mu_r = 1`. The predicate proposed in 1.b compares `eps_t` against `r_i*mu_t`, which covers a constant ratio; it is not claimed for a graded region or for a star that is not region-pure.
- The mixed path. `solve_modes_mixed` (`emfit/mode2d.py:1358`) does not pass through any of this, exactly as recorded at `docs/design/deflation_preregistration.md:259`.

## 2. The preservation check

Three readings, all of which must hold. Each is stated as a comparison with a number, and each names the outcome that is failure rather than pass, so that no reading can be recorded as a pass by describing it favourably.

### 2.a The seven frozen rows still reproduce

The frozen set is the nine entries of `docs/design/deflation_preregistration.md:150-160`. Seven of them are measurable: the five level-1 entries and the two level-2 entries. The two level-3 entries are not measurable under v1 because that run wrote no level-3 record, and they are not measurable here either unless the level-3 solve completes; if it does not, they remain unmeasured and the level-3 reading is FAILED-TO-MEASURE under v1 §5.a, not a pass.

The rule is v1's, unchanged in word, number and form (`docs/design/deflation_preregistration.md:176`):

    |beta^2_v2 - beta^2_frozen| / max(1, |beta^2_frozen|) <= 1e-12

and the same inequality written on `beta`. For the level-1 entry whose `beta` is `none` (`beta^2 = -179735.7274530737`) only the `beta^2` form exists and only it is applied.

Failure, not pass: any one of the seven absent from the returned eigenpairs; or present and outside the bound; or present inside the bound but at a value that is inside the bound of a *different* frozen entry as well, which makes the reading ambiguous and is reported as ambiguous rather than resolved by preference. The bound is not adjustable after the run. The worst value achieved by the v1 run was `1.0525169405629708e-14` [RELAYED]; that number is a reference for scale only and is not a target.

### 2.b The extension removes strictly more than v1

Two counts, both exact, both reported by the run.

1. Built dimension. `z_dim` must be exactly `14, 90, 434` at levels 1, 2, 3 — the sum of the two closed forms of 1.b — against v1's `11, 69, 329`. **The provenance of those six numbers, per level, so that none is mistaken for something it is not.** `11` and `69` are v1 built values written by a run, in the `deflation.z_dim` field of `.scratch/d47/out/deflated_level1.json` and `deflated_level2.json`, and each equals that record's `z_dim_closed_form` [VERIFIED this session]; `14` and `90` are therefore arithmetic on a stored value plus the added block of 1.b, `11 + 3` and `69 + 21`. Level 3 is the different case: no deflated level-3 record exists, because that solve aborted (v1 Amendment 1), so `329` is v1's closed form (`docs/design/deflation_preregistration.md:47`) and `434 = 329 + 105` is closed form plus closed form — a prediction about the next run, not an arithmetic restatement of a measurement. Equality, not "at least": a larger number means a node was selected whose star is not region-pure, which breaks K2 and voids 1.e for that column.
2. Candidates in the family band. Zero returned candidates at any level may satisfy

        |beta - 1990.411556294948| / 1990.411556294948 <= 0.01

    against 3 at level 1 and 8 at level 2 in the d47 records [RELAYED]. The 1 per cent band is the band `docs/design/d48_acceptance.md:138` already used to say the `k0` cluster is absent from the d47 records; it is reused here rather than invented.

Failure, not pass: a built dimension different from the closed form; or any candidate inside the family band at any level. Either one makes the extension leg FAILED-TO-MEASURE — not FAIL of the criterion, which is section 4's business, and not a pass.

### 2.c Everything v1 preserved is still preserved

The rows of 2.a are the frozen spine. Beyond them, the v1 run kept a set of candidates that are in neither kernel class, and those must not move. The comparison is against the d47 records, which are the v1 output:

- Take every v1 candidate at levels 1 and 2 whose `beta` is outside the 1 per cent band of `1990.411556294948` and outside the 1 per cent band of `k0 = 1407.4335088082273` (that is, outside both kernel levels). Each must have a v2 partner satisfying the 1e-12 rule of 2.a, on `beta` and on `beta^2`.
- Take every v2 candidate outside both bands at the same levels. Each must have a v1 partner under the same rule, unless it is a state that v1 could not return because a slot was occupied by the family. The count of such new states is reported; it is a number, not an expectation.
- Two v1 candidates mapping to one v2 candidate is a failure of bijectivity and is reported as such, not summed.

Failure, not pass: any v1 non-kernel candidate with no v2 partner inside 1e-12; or a v2 candidate inside the frozen span `944.6029788248537 < beta < 1990.411556294948` that has a v1 partner but at a distance above 1e-12. A run that satisfies 2.a and fails 2.c has moved something physical and is a stop, whatever section 4 would have said.

## 3. The by-order criterion, restated so that it can fail

### 3.a What is in force, and why it cannot fail

By-order matching in the tree is positional. In `classify`, at `tools/host/anchor/ladder.py:180-201`:

    matched = []
    for i in range(3):
        if i < len(retained):
            r = retained[i]
            beta = r["beta"]
            e = abs(beta - beta_ref[i]) / beta_ref[i]

with `retained` in descending `beta_sq` order (`candidate_rows`, `tools/host/anchor/ladder.py:127`, `pairs.sort(key=lambda p: (-p[0][0], p[1]))`). Order `i+1` is the `i`-th largest retained candidate. Nothing branches on `e` except the >50 per cent contamination flag at `:195` (`CONTAMINATION = 0.5`, `:67`), which records and does not decide.

The rule therefore cannot fail as a matching rule. Provided three candidates survive, it always returns three pairs, and it returns them whether or not any candidate is a mode. That is exactly what happened in d47: three members of the family at `1990.411556294948` were paired against the analytic values, giving the relative errors `0.21514853163021364`, `0.5354568093023866` and `1.1071408844921768` [VERIFIED this session in `docs/design/d48_acceptance.md:24-26`]. A pairing rule that cannot mis-pair is not a rule, it is an assumption. The assumption here was that position in the beta ordering carries identity, and it does not.

### 3.b What replaces it

Six clauses. The tolerance `0.02` is `PAIR_TOL` at `tools/host/anchor/ladder.py:86`, the value the tree already uses for value pairing in `pair_by_value` (`:426-447`); it is not a new number.

- **B1 Band.** A candidate may be paired with reference order `k` only if `|beta - beta_ref[k]| / beta_ref[k] <= 0.02`.
- **B2 Nearest.** Among eligible candidates, order `k` takes the one with the smallest relative distance. An exact tie at the reported precision is recorded as a tie and resolved toward the lower order; the record states that it was a tie.
- **B3 Bijectivity.** A candidate is consumed by at most one order. If the nearest eligible candidate for order `k` is already consumed, order `k` takes the next-nearest eligible unconsumed candidate, and the record shows both the first choice and the taken one.
- **B4 Order preservation, recorded and not enforced.** The pairing is monotone (`beta_1 > beta_2 > beta_3`) or the record says it is not. Non-monotone pairing is permitted and reported, because nothing guarantees that the discrete ordering of retained candidates matches the analytic ordering at a coarse mesh, and enforcing monotonicity by fiat would be a second unregistered assumption.
- **B5 Unpaired.** A reference order with no eligible candidate is UNPAIRED. An unpaired order is a term of the criterion — the fundamental must be present at every level — and it is never filled by extrapolation from the next lower or higher order.
- **B6 Surplus.** Every retained candidate not consumed by a pair is surplus, recorded with its relative distance to the nearest reference order. The count and the list are numbers the run reports. A surplus candidate closer to a reference value than the paired one is recorded as a surplus that beat a pair, and that is a reading in its own right.

The candidate set that B1-B6 operates on is the retained set, which still comes from the frozen filter: `|eps_eff - 1| <= 1e-8` at `tools/host/anchor/ladder.py:144` with the constant at `:63`, and `K_CAND = 16` at `:62`. The rule changes the pairing only. It does not change what is retained, the band `1.7` to `2.3`, the `2.0e-3` bound, the level set, the endpoint `1990.411556294948` or the selection of the largest positive `beta^2`.

### 3.c When the new rule still mis-pairs

The rule can still return the wrong answer, in five ways, all of which are visible in the record and none of which is excluded by B1-B6:

1. **A spurious state inside the band.** If a non-physical candidate lands within 2 per cent of a reference value and nearer than the true mode, B2 takes it, B3 consumes it, and the true mode becomes surplus under B6. The rule is protected against a family at 0.215 relative distance; it is not protected against a spurious state at 0.02. The d47 failure, one decade deeper.
2. **Two candidates inside one order's band.** B3 prevents double use but cannot decide which of two candidates within 2 per cent is the mode of that order. The nearer one is taken and the other is surplus. If they are equidistant the tie is recorded as a tie, which is the honest outcome and still not an identification.
3. **Two orders inside one candidate's band.** If two reference values are close enough that a single candidate lies within 2 per cent of both, the greedy assignment can satisfy order `k` with the candidate that belongs to `k+1`. The condition to report is the smallest relative spacing of the reference values, `min_k |beta_ref[k] - beta_ref[k+1]| / beta_ref[k+1]`, against `2*0.02`; where that spacing exceeds `0.04` the swap cannot happen by this route, and where it does not, B4 and B6 are the only signals that it did.
4. **A systematically biased discrete value.** If a discrete value converges to its analytic limit from outside the band at the coarse levels, B5 fires and the order is UNPAIRED — a correct reading of a real disagreement, but not an identification. If two bands begin to touch as the reference spacing shrinks, clause 3 applies at that level and not at the others; the rule must be applied per level and the report must not carry a pairing forward from a coarser level.
5. **A degenerate candidate set.** If fewer than three candidates survive the filter, B1-B6 return fewer than three pairs; two orders are UNPAIRED and the reading is FAILED-TO-MEASURE under v1 §5, not a FAIL of accuracy. Fewer than three retained is already a note in the code (`tools/host/anchor/ladder.py:176-178`).

Two further prohibitions, registered now so that neither can be introduced as a refinement later: the pairing may not consult a candidate's `curl_ratio` or `eps_eff` to break a tie (that would use the classification to decide the pairing that feeds the classification), and it may not use the pairing of another level (which would make the levels dependent and void the per-level reading).

## 4. Level 3, as a pre-registered falsifiable expectation

**The prediction, in one sentence.** Removing the slab-gradient block at `beta^2 = eps_r*k0^2` takes the level-3 deflated dimension from `1135 = 1464 - 329` to `n = 1464 - 329 - 105 = 1030`, and level 3 then converges all 16 requested vectors inside the existing budget `maxiter = 40*n = 41200` iterations, with no change to the budget and no second attempt.

The arithmetic of that sentence [VERIFIED this session by arithmetic]: `1464` free DOFs, `329` air columns and `105` slab columns at level 3 (§1.b), so `n_columns = 1030` and `40*1030 = 41200`. For comparison, the v1 level-3 solve exhausted `40*1135 = 45400` and aborted at `45401` iterations with 15 of 16 converged after 1632.8 s, and an earlier attempt exhausted the library default `10*1135 = 11350` and aborted at `11351` with 12 of 16 after 550.8 s [RELAYED].

**What each outcome means.**

- **Converges inside 41200.** The diagnosis is supported: the residual multiplicity near `2*k0^2` inside the requested window was the cause of the v1 abort, and the removal of the block is what the level-3 failure required. The level-3 reading is then issued under v1 §4 unchanged, from the returned candidates, by the by-order rule of section 3.
- **Exhausts 41200.** The diagnosis is falsified. It is a finding about the diagnosis and not an invitation to raise the budget: the cause of the v1 abort lies elsewhere, the level-3 reading is FAILED-TO-MEASURE under v1 §5.a, and it is recorded as such with no third budget, no change of `ncv`, no change of `tol`, and no further attempt without a new dated amendment written before that attempt. Any sentence in the report that begins "the budget was too small" is a claim about the diagnosis and must be defended as one.
- **Fails before the solve.** If section 2.b fails, the family was not removed, the level-3 expectation is untested rather than falsified, and the reading is FAILED-TO-MEASURE with the cause named as under-removal (P1 or P2), not as non-convergence.

Two things this prediction deliberately does not do. It does not compare iteration counts with `45401` as if they were commensurable: the dimension changes from `1135` to `1030`, so the only claim is convergence versus non-convergence inside `41200`. And it does not predict anything about the level-3 *values*: whether the fundamental is present at level 3 is section 3's reading on whatever comes back, and a converged solve with the wrong pairing is a different failure from a non-converged one.

## 5. No threshold relaxation

Section 5.a of `docs/design/deflation_preregistration.md:227-230` stands unchanged and applies to every reading of this document. In its words: no threshold is lowered, no band is widened, no candidate count is changed, no level is dropped and no level is added; the verdict is not deferred; a reading that needs an exception is at best FAILED-TO-MEASURE, and naming the exception in prose does not convert it into a PASS. Nothing in this document may be read as amending that section, and no number below was set after seeing a v2 measurement.

The numbers frozen in this document, with their standing:

| number | value | what it governs | status |
| --- | --- | --- | --- |
| preservation bound | `1e-12` | §2.a, §2.c | v1's, reused unchanged (`deflation_preregistration.md:176`) |
| by-order tolerance | `0.02` | §3.b B1 | `PAIR_TOL`, `ladder.py:86`, existing |
| family band | `1e-2` relative in beta | §2.b, §2.c | `d48_acceptance.md:138`, existing |
| band | `1.7` to `2.3` | criterion | `d46_acceptance.md`, untouched |
| absolute error bound at finest mesh | `2.0e-3` | criterion | `d46_acceptance.md`, untouched |
| candidate count | `16` | window | `ladder.py:62`, untouched |
| effective-permittivity filter | `1e-8` | retention | `ladder.py:63,144`, untouched |
| separation guard | `6.0` decades | retention | `ladder.py:64`, untouched |
| contamination flag | `0.5` | reporting | `ladder.py:67`, untouched |
| eps_eff band | `0.02` | negative control | `ladder.py:88`, untouched |
| ARPACK budget | `40*n` | level 3 | v1 Amendment 1 (`deflation_preregistration.md:236-255`), untouched |
| endpoint | `1990.411556294948` | §2.b, §3.b | `ladder.py:65`, untouched |
| shift | `990434.5408581193` | solve | `ladder.py:61`, untouched |

Three statements that this section exists to make explicit.

1. The only number whose standing changes is `PAIR_TOL = 0.02`, from a tolerance used by the negative control to the tolerance of by-order matching. This is a restriction, not a widening: positional matching had no tolerance at all and accepted a 0.215 error as a pair. A candidate that the old rule paired is not entitled to a pair under the new one.
2. The band of `1e-2` in §2.b is a *presence* test for a spurious family, not an accuracy bound. It is not compared with the `2.0e-3` bound and cannot substitute for it.
3. No floor, band, bound, budget or count in the table may be widened, relaxed or re-tuned after the run, and a reading that needs one is FAILED-TO-MEASURE. The prior expectation about level 3 in section 4 is a prediction and therefore falsifiable; the numbers in this table are not predictions and therefore not.

## 6. Dated amendment record

Dated 2026-10-28. Written before the run whose reading it governs, under the amendment rule at `docs/design/deflation_preregistration.md:232-234`.

**The failure being recorded, in the open.** By-order matching in d47 paired all three analytic modes against members of a candidate family at `beta = sqrt(eps_r)*k0 = 1990.411556294948`, producing relative errors `0.21514853163021364`, `0.5354568093023866` and `1.1071408844921768`, mesh-locked across levels 1 and 2 [VERIFIED this session, `docs/design/d48_acceptance.md:20-26`]. The pairing was not an accident of that run: it is what the code at `tools/host/anchor/ladder.py:180-201` does by construction.

**Why it happened.** Two causes, both required. The matching rule is positional — the `i`-th largest retained candidate is order `i+1` — with no tolerance and no bijectivity, so it cannot refuse a candidate and cannot mis-pair in any way that its own output would show. And the candidate set contained spurious states at a value that is neither the shift nor the cluster the instrument was built to remove: states at `beta^2 = 2*k0^2 = 3961738.16343248`, curl-free to `8.849983581104381e-10` against a calibrated band `T1 = 2.679e-9` [RELAYED], which v1's `Z` did not touch because its region predicate accepts only the ratio `1` (`emfit/mode2d.py:1044`). A positional rule over a set containing a spurious family is a rule that reports the family as modes.

**What is being added.**

- The extension of section 1: one further block of columns, selected by the ratio of `eps_r` to `mu_r` rather than by its equality to `1`, with one scalar per block in v1's algebra, and the two PROVISIONAL steps of 1.f named rather than hidden.
- The three-part preservation check of section 2, which is the only instrument that can show the extension did not move the physical spectrum, together with the statement of what it cannot see.
- The by-order rule B1-B6 of section 3, which replaces positional matching and which is specified together with the conditions under which it still mis-pairs.
- The level-3 expectation of section 4, falsifiable, with the consequence of its failure fixed in advance.

**Where the normative text lives.** The normative amendment is appended to `docs/design/deflation_preregistration.md` as **Amendment 2**, dated 2026-10-28, under §5.b of that file. This section summarises it and does not duplicate it; where the two differ, the appended text governs. Amendment 2 replaces nothing in that file's section 3, nothing in its section 4, and nothing in its section 5.a, and it does not touch the `1e-12` bound or the nine frozen values. Amendment 1 (the `40*n` ARPACK budget) stands as written and is not superseded: this document predicts convergence inside `41200` and pre-authorises no second budget.

**What the amendment does not do.** It does not implement the extension (Task 2 ends the dispatch without an implementation), it does not discharge the two obligations deferred from v1, it does not change the mixed path, it does not correct the d45 erratum, and it does not fix identification in the sense of `docs/design/deflation_preregistration.md:260`. It records a failure of the instrument and adds the instrument changes that the failure requires, in the open, before the run.

## What this document does not claim

- It does not claim the family at `sqrt(eps_r)*k0` is a continuum artefact. It claims it is curl-free at round-off in the discrete operator and that the extension removes whatever lies in the span of the added block. The membership itself is P1, and P1 is PROVISIONAL.
- It does not claim the extension removes the family in full. P2 states the opposite possibility and section 2.b is the test that would show it.
- It does not claim the preservation check is sufficient. It cannot see a physical mode at `beta^2 = 2*k0*k0`, and section 2 says so.
- It does not claim the by-order rule is correct. It claims the rule can fail, and it lists five ways it can still mis-pair.
- It does not claim level 3 converges. It predicts it, at `41200` iterations, and section 4 states what a failure of that prediction means.
- It does not claim any number at levels 4 or 5, where no record exists and the deflated dense route is capped at 6000 free DOFs (`emfit/mode2d.py:1000`), so levels 4 and 5 are outside what the current implementation can even attempt.
- It does not claim to have implemented anything, run anything, or measured anything new. Every number here is either read from the tree, carried from v1 or from the d48 Task 1 report, or arithmetic on those.
