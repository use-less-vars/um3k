# Physics Invariant Layer for the Mode-2D Solver

## Status

**New document.** 2026-10-28. Specifies a layer of physics invariants for
the mode-2d solver, the point of the pipeline at which each invariant
sits, and the derivation of each tolerance.

**Design only.** This document writes no test, injects no defect, runs no
solver and reports no number of its own. Every numeric below is either
read out of the tree with a stated route or marked to be measured.

**Depends on.** `docs/design/cpp_solver_arch.md` sections 5.9 and 9.1 for
the current gate table and its corrigenda; `docs/design/d44_acceptance.md`
for the acceptance of the port and the harness defect that document
records; `docs/design/d43b_extraction_audit.md` section 9 for the count of
comparisons able to distinguish a right answer from a wrong one;
`emfit/mode2d.py` for the pipeline under test.

**What it does not do.** It does not set a threshold on `beta^2` against
an analytic value. It does not move a threshold that
`cpp_solver_arch.md` 5.9 already states. It does not decide the
`normalization` mismatch that `d44_acceptance.md` section 9 leaves open;
it names the invariant that would flag it and stops there. It does not
authorise a run.

**Provenance.**

- `emfit/mode2d.py`, 1390 lines, 58509 bytes, sha256
  `9b74d83d7b2c6b0df5b362a391df39dd8940378195b5faef1efe14d84febe032`,
  read in full this session. Only these line numbers are cited below, each
  verified by direct read: 131, 150, 151, 354, 397, 469, 539, 571, 605,
  742, 795, 935, 1116, 1175. Everything else is cited by content phrase.
- `docs/design/d44_acceptance.md`, 117 lines, 16054 bytes, sha256
  `a5817c62a28cbc740585de6167e33ffc9f0e578b141a4bea00a043f4662e181e`.
- `docs/design/cpp_solver_arch.md`, sections 5.9 and 9.1, cited by content
  and heading.
- `docs/design/d43b_extraction_audit.md`, 715 lines, sections 9.1 to 9.4
  and the class table in 9.2, cited by content and heading.
- `decisions.md` was read and is not edited by this document.

## 1. What the invariants can and cannot see

**1.1 The rule this section is built on.**

An invariant computed from the same assembled operators that the solve
used is a self-consistency check. It asks whether the returned numbers
satisfy the identities of the operator that produced them. When the defect
is in the assembly, the identity moves with the defect and the check
passes. The layer therefore records, for every invariant, which of two
provenances it has.

| provenance | what the invariant multiplies | what it can catch |
|---|---|---|
| reused | the solver's own assembled blocks | defects introduced after assembly |
| reassembled | quantities rebuilt from the returned field, the mesh and the material, without calling the solver's assembly | assembly defects as well as later ones |

The rule has a second edge, and it matters more than the first. A
re-assembly written from the same weak form reproduces the same
conventions, because a sign convention is a property of the weak form and
not of the arithmetic that evaluates it. Re-assembly can catch an
arithmetic error in a block. It cannot arbitrate what the block's sign
should be. Only a value computed outside this weak form can do that, and
that is the job of the analytic anchor in section 4. Section 1.3 leans on
this once and the rest of the document cites it rather than repeating it.

The layer's own assembly is therefore mandatory, and it is not sufficient.
Both statements are load bearing.

**1.2 The defect matrix.**

The matrix below is the test the layer has to pass: for each defect, which
invariants fire. A cell reading silent is a claim, and the layer's accept
criterion in 1.10 turns on it. Reads: silent means the invariant does not
fire; fires means it does. Parentheses give the condition.

| defect | I1 recip | I2 pass | I3 energy | I4 mirror | I5 scale | I6 orth | I7 KK | anchor |
|---|---|---|---|---|---|---|---|---|
| 1a sign of curl-curl block | silent | silent | silent | silent | silent | silent | silent | fires |
| 1b sign of coupling block | silent | silent | fires (pairing) | silent | silent | silent | silent | fires |
| 1c sign of k0^2 mass block | silent (no mode) | silent (no mode) | silent (no mode) | silent (no mode) | silent (no mode) | silent (no mode) | silent (no mode) | fires |
| 2 coupling perturbed by 1e-3 | silent | silent | fires | silent | silent | silent | silent | fires |
| 3 two modes exchanged | silent | silent | fires (3a only) | silent | silent | silent | silent | fires (3b, if non-degenerate) |
| 4 basis changed | silent | silent | silent | silent | silent | silent | silent | fires (refinement only) |
| 5 B inner product dropped | silent | silent | silent | silent | silent | fires | silent | silent |

Two rows deserve a warning before the detail. Row 1c's silences are not
credits: they record that no number was returned for the invariants to
test. Row 5's single firing cell is the only place in the matrix where an
invariant catches something the anchor cannot see, and it is also the cell
that would fire against the mixed path as the code stands today.

**1.3 Row 1a, the sign of the curl-curl block.**

The mutation flips the sign of `k_q` in `A = k0^2 m_eps - k_q`. It is
silent in all seven, for seven separate reasons, which is why it is worth
listing them rather than asserting blindness once.

Reciprocity is silent because `k_q` is symmetric with either sign, and so
is `-k_q`. Passivity is silent because the flipped pencil returns
`beta^2 = k0^2 m_eps + k_q`, which is larger than the correct value and
still positive for the lowest mode, so the passivity test of section 3.3
sees an admissible mode. Energy conservation is silent because the flipped
pencil has its own three-term identity and the solution satisfies it
exactly; the layer's reassembled `k_q` evaluates the same weak form and
arrives at the same sign, which is the second edge of 1.1. Mirror symmetry
is silent because the reflection commutes with `-k_q` as well as with
`k_q`, so the modes are still even or odd. Length scaling is silent
because the two terms of the pencil have the same scaling degree under a
geometry scaling, so the flip survives the scaling unchanged and the
comparison between the two runs is unaffected. Orthogonality is silent
because both operators are symmetric. Kramers-Kronig is silent because no
constitutive input enters the flip.

The anchor fires because the returned `beta^2` is wrong against the
transcendental root by an amount that grows with the mode's curl energy,
which is not small. This is the row that decides whether the anchor is
mandatory. It is.

**1.4 Row 1b, the sign of the coupling block.**

The mutation flips `c` to `-c`. The pencil is
`A = k0^2 m_eps - k_q` and `B = m1 - c D c^T` with
`D = (k_zz - k0^2 m_zz)^{-1}`. `A` contains no `c`, and `B` is even in
`c`. So the two matrices are unchanged entry by entry, not approximately:
the spectrum, the candidate list, every `beta^2`, every residual and every
eigenvector are identical. All beta-side invariants are blind by
construction rather than by margin, and no tolerance can change that.

What the flip damages is the longitudinal field. The reconstruction
`e_z[free_n] = 1j * beta * lu_h.solve(c_f.T @ x)` at line 1175 carries one
power of `c`, so the returned `e_z` changes sign while `e_t` does not. Any
test that reads `e_z` alone and takes a magnitude is blind too, which is
exactly the harness defect of section 2.4.

The catch belongs to I3 in its pairing form: assemble the coupling
independently, form both rows of the two-field block, and normalise. Under
`c -> -c` the second row of the block residual changes sign while the
first row does not, so the residual moves from its usual size to order
one. The mixed solve already builds such a block residual as a diagnostic
and documents it as order 1e-1 to 1, not as a pass or fail guard. The
layer converts it into a guard by pairing it with an independent assembly.
That is the whole difference between the diagnostic and the test.

**1.5 Row 1c, the sign of the `k0^2 m_eps` block.**

The mutation makes `A = -k0^2 m_eps - k_q`. Every eigenvalue of the pencil
is then negative, and the selection step takes the largest positive
`beta_sq` whose curl ratio clears `_CURL_RTOL` (line 131). Nothing clears
it, so the run returns no mode at all.

The seven invariants are still silent, and the reason is not that they
miss the defect. They are silent because there is no returned number for
them to test. The defect is loud, but it is loud through candidate
rejection, and candidate rejection is not a physics verdict: it says the
pencil had no admissible eigenvalue, not that the physics is wrong. A
layer that counted this silence as a pass would be counting an empty
result as evidence.

The anchor is again the only instrument that yields a number, and here it
yields none either, because there is no mode to compare. The honest
reading of the row is that this defect is caught before the layer starts,
and that the layer's silence is not a claim about it.

**1.6 Row 2, the coupling perturbed by one part in a thousand.**

A relative perturbation of the coupling by `eps = 1e-3` enters the pencil
through `B` only, and `B` contains `c` quadratically, so the first-order
change is `-2 eps c D c^T`. Writing `s_c` for the modal share of the
eliminated longitudinal energy,
`s_c = (c^T x)^T D (c^T x) / (x^T B x)`, the relative change in `beta^2` is
order `2 eps s_c`.

That factor is the whole design point of the rows. Detection of a
perturbation of the coupling is conditional on `s_c`. In a geometry where
the longitudinal energy is a small share of the total the perturbation is
invisible at any tolerance the arithmetic can support, and no amount of
tightening will help. The layer therefore reports `s_c` beside every I3
result and does not claim row 2 unconditionally. Reciprocity, mirror,
scaling, orthogonality and Kramers-Kronig are all silent here, and
passivity is silent as well because a shift of `beta^2` that does not
change its sign leaves passivity satisfied.

**1.7 Row 3, two modes exchanged.**

Two forms of the defect, with different answers.

Form 3a exchanges fields between slots while the `beta^2` values stay with
the slots. This is a bookkeeping error and the pairing form of I3 catches
it: read the returned field for slot `i`, compute
`x^T A x / x^T B x` with the layer's own `A` and `B`, and compare against
the `beta_sq` returned for slot `i`. A swapped field returns the other
mode's Rayleigh quotient.

Form 3b exchanges complete pairs, field and scalar together. Every
single-mode invariant then passes, because each pair is internally
consistent: passivity, reciprocity, mirror, scaling and energy
conservation each test one mode at a time and each sees a valid mode.
Orthogonality is invariant under any permutation of the returned set.
What remains is the anchor, and only when the two analytic values differ;
if the modes are degenerate the exchange is not a defect at all.
Continuity of a tracked branch in `k0` would also catch 3b, and that is
not one of the seven. The row's point is that mode identity is not a
property the seven can certify, and the layer says so instead of implying
otherwise.

**1.8 Row 4, a change of basis.**

A change of basis inside one discrete space is a similarity transform. It
leaves the spectrum, the Rayleigh quotients and the orthogonality
relations intact, so all seven are silent, and correctly so, because
nothing physical has changed. This is the strongest single argument that
the anchor is not optional: the one defect class that a reader is most
likely to suspect, a reshuffled representation, is precisely the class
that the invariants are constructed to be indifferent to.

The damaging case is not a change of basis. It is a change of
discretisation, and the s10118 experiment of section 2 is an instance:
the two sides there are different finite element spaces, not two labels
for one space. What sees a change of discretisation is the observed-order
test of section 4.5 together with refinement, because two spaces converge
to the same value at different rates and a fixed-mesh gap between them is
a statement about the mesh, not about correctness. Refinement alone still
cannot say which side is right. Only the closed form can.

**1.9 Row 5, the `B` inner product dropped.**

If the eigenvectors are normalised in the 2-norm instead of the `B` norm,
the eigenvalues are unchanged, so the anchor is blind, and passivity,
reciprocity, energy conservation, mirror, scaling and Kramers-Kronig are
all silent. I6 fires, because vectors normalised in the 2-norm do not
satisfy `e_i^T B e_j = delta_ij` when `B` is not the identity.

The finding to record: the mixed path already normalises with the plain
2-norm, while the mode container's own documentation states that the
transverse field is normalised so that `e^T B e = 1`. The mixed path is
therefore the case the invariant flags today. This document records the
mismatch and does not resolve it; `d44_acceptance.md` section 9 leaves the
same decision open.

**1.10 What the layer is allowed to claim.**

The layer fails if any invariant stays silent on a defect it is claimed to
catch. Nothing weaker than injection discharges that: the claim is
discharged by actually introducing each defect, running the layer, and
showing that the named invariant fires. It is discharged in the negative
direction by showing that the silent cells above are the only silent ones,
which is what makes the silence informative rather than decorative.

The corresponding implementation task owns that discharge. This document
supplies the table it has to reproduce.

## 2. The case that motivates the layer

**2.1 Two bases, one geometry, one disagreement.**

The s10118 experiment solved the same structure twice, once with the
transverse-only pencil and once with the two-field mixed pencil, and read
a set of diagnostics off both. The recorded result is
`.scratch/s10118_result.txt`; note that `.scratch/` is not tracked by git,
so a reader may not have the file. The mesh had 1444 free edges and 483 free
nodes, with the dense cutoff `_MIXED_DENSE_MAX` (line 151) reporting 3000,
so the mixed eigenvalue problem was solved densely. The two `beta` values
were 309.9818636706751 and 326.9107654423116, a difference of
16.928901771636447, or +5.46 per cent.

Everything else in the pair of readings moves the same way. The figure
labelled passivity is 1.0142899588259895 on one side and 2.0013807961296104
on the other. Mode purity is 0.013875 against 0.206827. The mode residual
is 4.849473685711963e-18 on one side. The field correlations are
`corr_e_z = 0.11916043239134175` and `corr_e_y = 0.9207707848111418`.

**2.2 Why the larger figure is inadmissible.**

A value labelled passivity above one on a passive structure is impossible.
The structure is a closed box with lossless material, so no mode can
deliver more power than it stores. Either the label is wrong or the
computation behind it is wrong, and this document does not need to know
which. Either way that basis is inadmissible as evidence, and the number
is not a reading of passivity.

**2.3 What the record does not contain.**

The result file contains no `s11` or `s21` key: a search for those
tokens returns no matches. There is therefore no S-parameter in the
record, no derivable source key from which the passivity figure could have
been formed, and no way to trace it to a computation. The figure exists
under that label and has no traceable origin. It is a reminder that a
diagnostic printed under a name is not a measurement of the quantity that
name denotes.

The layer's first duty follows directly: every number it emits carries its
own source key, naming the invariant, the field or block it was formed
from, and the mesh it was formed on. That is exactly what this experiment
did not do, and the cost of the omission is that a physically impossible
figure sat in a result file with nothing able to contradict it.

**2.4 The harness that mirrored the reference.**

The comparison harness `.scratch/logs/s10118_basis.py` called
`assemble_mixed`, then
rebuilt the Schur complement by hand, factorised it, applied `np.abs` to
the solved node values and stored the result as the longitudinal field.
The code path keeps `1j` and multiplies by `beta`; the harness dropped the
`1j` and took a modulus. The compared field was therefore not the
solver's `e_z` at all, it was a second hand-written implementation of the
same reduction, written by the same hand from the same conventions, with
one term changed.

`.scratch` is not tracked by git, so the finding is stated here in this
document's own words and the path is cited only as a location in the
record.

The rule the defect produces: a reference implementation must be called,
not mirrored. A mirrored reference bounds agreement between two copies of
one set of conventions and cannot adjudicate a difference between two sets
of conventions, which is the only thing a comparison between discretisations
is for. Repairing that harness is a separate task and is not this one.

## 3. The seven invariants

**3.1 Arithmetic, and what a tolerance is.**

Nothing under `emfit/` uses a single-precision or half-precision dtype;
there is no `float32` and no `complex64` on this path. The arithmetic is
IEEE double throughout, with fields in complex double, so the unit roundoff
is `u = 2^-53 = 1.1102230246251565e-16`. The float32 round trip named in
the commit message has no stage on this path to occur at.

Two consequences are used repeatedly below.

For `n` floating-point sums, the forward error is bounded by
`gamma_n = n u / (1 - n u)` times the sum of the magnitudes, with
`gamma_100 = 1.1102230246251688e-14`. That is the tolerance for any
quantity the layer forms by accumulating terms, and it is stated once here
rather than re-derived in each invariant.

For an eigenpair the layer does not need an a-priori bound at all, because
the quantity it can actually measure is already one. Let `B` be symmetric
positive definite, let `x` be `B`-normalised, put
`r = A x - lambda B x`, and let `C = B^{-1/2} A B^{-1/2}`. Then `C` is
symmetric, `||C y - lambda y|| = ||r||_{B^{-1}}` with
`||v||_{B^{-1}} = sqrt(v^T B^{-1} v)`, and some eigenvalue `mu` of `C`
satisfies

`|mu - lambda| <= ||r||_{B^{-1}} = sqrt(r^T B^{-1} r)`.

The measured residual in the `B^{-1}` norm is the tolerance. Any threshold
tighter than it is a claim the arithmetic cannot support, and any
threshold looser than it needs a reason.

The mixed path does not have this bound. Its `B` matrix is indefinite, so
`B^{-1/2}` does not exist as a real transform and the reduction above
cannot be performed. The bound then needs the eigenvector condition number
of the pencil, which comes out of the QZ factorisation and is to be
measured rather than assumed. That is the honest reason the mixed path's
existing residual, gated at `_MIXED_RESIDUAL_TOL = 1.0e-3` (line 150), is
a diagnostic and not a gate, and this document keeps it that way.

**3.2 I1, reciprocity.**

Statement: `A` and `B` are symmetric. On this path there is no scattering
matrix, so the reciprocity theorem has no direct statement to make; the
discrete consequence is symmetry of the two matrices that define the
pencil.

Pipeline position: immediately after assembly and before any
symmetrisation. The mixed path forms `a_dense` and `b_dense` and then
applies `0.5 * (A + A^T)`; evaluating after that call averages the
evidence away, so the invariant must read the unsymmetrised arrays.

Tolerance: `||A - A^T||_F <= gamma_nnz ||A||_F` with `nnz` the number of
stored entries, counted per case.

Provenance: reused. There is no independent assembly of symmetry.

Does not catch: any defect that is applied symmetrically, which is rows
1a, 1b and 1c of section 1.

**3.3 I2, passivity.**

Statement: on a closed PEC box with lossless material no power leaves the
domain and none is generated, so every admissible mode has
`Re(beta^2) >= 0` and a propagating mode has `e_z` purely imaginary with
the phase relation that ties it to `e_t`. The solver forms no S-parameter
anywhere, which is the deeper reason the s10118 record has no `s11` or
`s21` key: there was no S-parameter to record.

Pipeline position: on the returned mode, at the extraction boundary.

Tolerance: `Re(beta^2) / |beta^2| >= -gamma_N kappa_P`, with `kappa_P` the
condition number of the passivity functional, defined as the ratio of the
largest to the smallest term in the energy split of 3.4, to be measured
per case. The phase relation is tested at the same tolerance.

Provenance: reused for `beta^2`, reassembled for the phase relation.

Does not catch: the sign of the curl-curl block, because the flipped
pencil's lowest mode still has positive `beta^2` (row 1a).

**3.4 I3, energy conservation, and its pairing form.**

Statement, in the eigenvalue form: `x^T A x = beta^2 x^T B x`, expanded

`x^T (k0^2 m_eps - k_q) x = beta^2 [ x^T m1 x - (c^T x)^T D (c^T x) ]`,
with `D = (k_zz - k0^2 m_zz)^{-1}`.

The three groups are the electric energy, the magnetic or curl energy, and
the eliminated longitudinal energy. Each is reported separately, because a
single residual hides which one moved.

Statement, in the pairing form: given the returned `e_t`, `e_z` and
`beta`, form both rows of the two-field block against a coupling assembled
independently of the solver's, and normalise the two-field residual by the
Frobenius norm of the block and the norm of the field.

Pipeline position: on the returned mode for the eigenvalue form; on the
returned mode for the pairing form, which requires both a transverse and a
longitudinal field and is therefore available only where `e_z` is not
None.

Tolerance: `gamma_n` times the sum of the absolute values of the three
groups, for the identity. For the pairing form the same construction on
the block. Detection of a perturbation of the coupling is conditional:
the response is order `2 eps s_c` with `s_c` as defined in section 1.6, so
the layer reports `s_c` beside every I3 result and the reported value is
part of the result, not a footnote.

Provenance: reassembled. This is the invariant the reassembly requirement
exists for.

Fires: rows 1b (pairing form), 2, and 3a. Does not fire: rows 1a, 1c, 3b,
4, 5.

**3.5 I4, geometric mirror symmetry.**

Statement: when the mesh is symmetric about a mid-plane the discrete
operator commutes with the reflection `R` that maps the mesh to itself, so
a non-degenerate mode is even or odd:
`||P_s x|| / ||x|| >= 1 - tol` for `s = +1` or `s = -1`, with
`P_s = (I + s R) / 2`.

Pipeline position: on the returned field, which needs the field on the
symmetric mesh; the interpolation already exposed on the mode container is
sufficient for the transverse part.

Tolerance: from the eigenvector perturbation bound `sin theta <= ||r|| /
gap`, with `gap` the distance from the mode's `beta^2` to the nearest other
candidate in the returned candidate list. The numeric is therefore
measured per case from the candidate list rather than fixed here, and when
the gap is not resolved, meaning two candidates sit inside the noise, the
invariant abstains instead of passing.

Provenance: reassembled, since `R` acts on fields and not on blocks.

Does not catch: rows 1a and 3b.

**3.6 I5, length scaling.**

Statement: scaling the geometry by `s` and `k0` by `1/s` leaves
`eps_eff = beta^2 / k0^2` invariant and sends `beta` to `beta / s`.

Pipeline position: two runs, compared at the extraction boundary.

Tolerance: the two runs are related by a diagonal scaling of the edge
lengths, so the amplification of any relative error is the mesh aspect
ratio. The tolerance is `gamma_nnz * aspect * kappa_spectral` with
`aspect = max_edge / min_edge` on the mesh and `kappa_spectral` the
spectral condition number of the scaled pencil. The aspect ratio is read
per case; `kappa_spectral` and the resulting numerics are to be measured.

Provenance: reused; it compares two solves and has no field-level
substitute.

Does not catch: row 1a, because both terms of the pencil share the scaling
degree, and row 3b.

**3.7 I6, mode orthogonality in the `B` inner product.**

Statement: `e_i^T B e_j = delta_ij`, with `B = m_mu` on the
transverse-only path, and with the block form of `B` where a longitudinal
field exists.

Pipeline position: across the returned candidate set, at the extraction
boundary.

Tolerance: `max_{i,j} |e_i^T B e_j - delta_ij| <= gamma_N kappa_B`, with
`kappa_B` the condition number of the layer's reassembled `B`, to be
measured.

Provenance: reassembled. The layer multiplies its own `B`, not the
solver's, which is what makes the row 5 catch possible at all.

Does not catch: anything that changes the eigenvalues, which is every
other row.

Finding: the mixed path normalises in the 2-norm, so as specified this
invariant reports a failure on the mixed path as the code stands today.
The mismatch between the container's documented `e^T B e = 1` and the
mixed solve's plain 2-norm normalisation is recorded here and not fixed.

**3.8 I7, Kramers-Kronig.**

Statement: the relative permittivity fed to the per-triangle assembly is a
causal function of frequency, so its real and imaginary parts are a
Hilbert pair.

Pipeline position: at the material feed, before assembly, where the
per-triangle routine accepts a scalar, an array or a callable of the
centroid as the permittivity; and again as analyticity of a `k0` sweep,
since a non-causal permittivity gives a sweep that the dispersion relation
cannot follow.

Tolerance: for a permittivity behaving as `eps - 1 ~ A / omega^2` at large
frequency, the principal-value tail beyond a truncation `Omega` is bounded
by `(2 / pi) A / Omega`, and the total tolerance is that tail plus
`gamma_N` times the quadrature contribution.

Provenance: reassembled; it tests the input and never touches the operator.

Does not catch: any error in the discrete operator, which is rows 1, 2, 3
and 5. It also passes trivially for the lossless and frequency-independent
materials currently exercised, so on today's cases it is a guard against
future material models rather than a test of the current ones. The layer
says that rather than counting a trivial pass as evidence.

**3.9 Summary.**

| invariant | statement in brief | pipeline position | tolerance in derived form | numeric |
|---|---|---|---|---|
| I1 reciprocity | `A` and `B` symmetric | after assembly, before symmetrisation | `gamma_nnz ||A||_F` | `u` located; `nnz` per case |
| I2 passivity | `Re(beta^2) >= 0`, `e_z` phase relation | extraction boundary | `gamma_N kappa_P` | `kappa_P` to be measured |
| I3 energy | three-term identity, plus pairing against an independent coupling | extraction boundary | `gamma_n` times the sum of magnitudes; response `2 eps s_c` | `s_c` measured per case |
| I4 mirror | mode even or odd about the mid-plane | returned field | `||r|| / gap` from the candidate list | measured per case |
| I5 scaling | `eps_eff` invariant, `beta` proportional to `1/s` | two runs | `gamma_nnz * aspect * kappa_spectral` | numerics to be measured |
| I6 orthogonality | `e_i^T B e_j = delta_ij` with the layer's own `B` | candidate set | `gamma_N kappa_B` | `kappa_B` to be measured |
| I7 Kramers-Kronig | causal permittivity at the feed | material feed | `(2/pi) A / Omega + gamma_N * quadrature` | to be measured |

Every entry in the last column is either a constant derived from `u` and
located in this document or an item this document declines to invent.

## 4. The analytic anchor

**4.1 Geometry.**

A closed PEC box `0 <= x <= a`, `0 <= y <= b`, uniform in `y`, with a slab
`0 <= x <= t` carrying `eps_r = eps1` and the remainder carrying
`eps_r = 1`. The interface at `x = t` is placed on a mesh line. Uniform in
`y` means the problem is one dimensional in the transverse variable and
the exact solution is a transcendental root, not a series.

This geometry is chosen because it is the cheapest one that exercises the
interface, and because its exact solution can be computed in the test from
a formula rather than read from a table.

**4.2 The TE family.**

Take `e = e_y y-hat`. The tangential component is continuous across the
interface, so the exact eigenfunction is continuously differentiable and
the discrete solution can converge at the full rate. The dispersion
relation is

`sin(kappa1 t) kappa2 cos(kappa2 (a - t)) + kappa1 cos(kappa1 t) sin(kappa2 (a - t)) = 0`

with `kappa_i^2 = k0^2 eps_i - beta^2`. For a uniform fill it degenerates
to `sin(kappa a) = 0`, which is the check that the relation has been
transcribed correctly.

This family exercises the curl-curl block and the interface treatment. It
is the primary order-of-accuracy test for that reason: the exact solution
is smooth in the sense the discretisation needs, so an observed slope below
the expected one is an error and not a property of the problem.

**4.3 The TM family.**

Take `h_y` with a Neumann condition at the PEC walls. The relation is

`cos(kappa1 t) (kappa2 / eps2) sin(kappa2 (a - t)) - (kappa1 / eps1) sin(kappa1 t) cos(kappa2 (a - t)) = 0`

and the fields follow from `e_x = (beta / (omega eps)) h_y` and
`e_z = -(1j / (omega eps)) h_y'`. This family exercises the coupling block
and the longitudinal reconstruction, which is the half of the pencil that
section 1.4 shows is otherwise unguarded.

The normalisation is stated as `INT eps_r e . e dA` matched to the
solver's `e^T B e = 1`, so the anchor compares a value in the same gauge
as the returned one rather than a value in a gauge of its own choosing.

**4.4 Independence.**

The reference value is obtained by bisection on the relation inside the
test, at the geometry and `k0` under examination, and never from a stored
table. The anti-pattern is on record: the existing slab reference stores
project values verbatim in a table produced by an earlier version of the
same calculation, and its residuals are all of one sign, which
`d43b_extraction_audit.md` section 9.1 treats as a systematic offset
rather than convergence. A table the solver produced cannot test the
solver, and the sign pattern is the tell.

No numeric `beta` is asserted in this document. The anchor's numbers exist
only when the test runs.

**4.5 Observed order.**

Refine the mesh by halving the element size: `h`, `h/2`, `h/4`, `h/8`, at
fixed `k0` and fixed geometry. Four points give three slopes, which is the
minimum that can show a slope at all; fit `log error` against `log h` on
log axes, and read the slope. The expected slope is `p = 2`: linear
edge elements and piecewise-linear nodal elements are first order in the
energy norm and the eigenvalue inherits second order from the standard
doubling.

The band is taken from the fit itself, but only after the bar on each
individual error value is named, because a slope band built on error bars
nobody has stated is decoration. Each `e_i` is measured against a
reference that has its own error, so the bar on `e_i` is the larger of two
measured quantities: the mode's eigenvalue residual in the norm of section
3.1, and the convergence tolerance of the bisection on the transcendental
root. The bisection tolerance is chosen at least two orders below the
smallest error in the sequence; when it is not, the reference sets the
slope rather than the discretisation and the run is void.

With `x_i = log h_i` and `s_r` the bar just described, the standard error
of the slope is `s_p = s_r / sqrt(sum (x_i - xbar)^2)` over the log
points, and the band is that error widened by the curvature observed
between the last two slopes. The numerics are to be measured; the band is
not fixed here.

TE is the primary order test because its eigenfunction is `C1`. TM has a
kink in the field at the interface and is scored under the same band with
that caveat recorded rather than with a band of its own.

**4.6 An unfitted interface.**

If the interface does not fall on a mesh line, the observed order is
capped in a way that depends on where the interface falls inside the
element. That is recorded as a separate run, scored only for monotone
decrease of the error under refinement. It is never scored as an
explanation of a failed order test on a fitted mesh, and it is never an
excuse for lowering `p`.

**4.7 The secondary anchor.**

A PEC rectangular waveguide has
`beta = sqrt(k0^2 - (m pi / a)^2 - (n pi / b)^2)`, which is exact, cheap
and has no interface. It is secondary because it tests the boundary
treatment and the interior only. It cannot say anything about the
interface, and the interface is where section 1.4 shows the layer is
weakest.

## 5. What this changes about the existing gates

**5.1 The layer catches wrongness, not inaccuracy.**

The `1e-8` gate of `cpp_solver_arch.md` 5.9 asks whether two
implementations agree on the same pencil. It cannot ask whether the pencil
is right, and section 9.1 of that document says so. The layer asks the
second question. The two questions are different in kind, and neither
substitutes for the other.

**5.2 The layer gates the gates.**

Read the two together and each outcome has a meaning.

| port gate | layer | reading |
|---|---|---|
| `1e-8` PASS | PASS | the port is faithful to a reference that is not visibly wrong |
| `1e-8` PASS | FAIL | faithful reproduction of an error, which is the case a port gate cannot see |
| `1e-8` FAIL | PASS | the port differs from a reference that passes the physics checks; the port is the suspect |
| `1e-8` FAIL | FAIL | both sides are wrong or the port is wrong and the reference is wrong; uninformative |

The second row is the one the current table has no entry for, and it is
the reason the layer exists rather than being a refinement of the port
gate.

**5.3 The thresholds do not move.**

`1e-8` stays binding and stays scoped to port fidelity on the same pencil
and nothing beyond it. `1e-11` stays reported and non-binding, citable for
nothing. The `1e-6` residual stays a residual and not a result. The
environment block keeps its power to void a comparison. This document is
not an argument for loosening any of them, and it adds no threshold on
`beta^2` against an analytic value.

## 6. Where the layer sits

**6.1 The extraction boundary.**

The layer sits at the mode container returned by the solve, which is where
`beta`, `eps_eff` and `e_z` first exist as outputs. Placing it there has
one practical consequence: the returned object is already sufficient for
the field invariants, because the transverse field can be interpolated at
arbitrary points and the longitudinal field is carried where it exists. No
new interface is needed for I4, I6 or the pairing form of I3.

The invariants that need the assembled blocks, I1 and I5, read them at the
point the solve built them, which is the same boundary with one step of
lookback. The material invariant I7 runs earlier, at the feed.

**6.2 Why not after the port.**

A layer written against the port is calibrated on the port: its expected
values come from the port, its tolerances are fitted to the port's
arithmetic, and any error the port shares with the Python cancels exactly
in the comparison. That cancellation is the same structural cancellation
that limits the `1e-8` gate to fidelity, arriving a second time under a
different name. Retrofitting the layer after the port is complete would
reproduce the defect it is meant to catch.

The layer is therefore specified against the Python path and against the
closed form, and it is written before the port is accepted, not after.
