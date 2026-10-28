# Dispatch 48: acceptance criteria

Frozen before measurement. Written and committed before any candidate set was
classified in this dispatch, so that the classification below cannot be read
back onto the rules that produced it. It decides nothing that the documents it
cites already decide, and it relaxes no threshold.

Provenance tags, used as the brief requires:

- `[USER]` the supervisor's brief, transcribed without alteration.
- `[VERIFIED]` read out of the tree during this dispatch by direct read of the
  cited `file:line`, through my sub-agent. The citation is given so the claim
  can be re-checked; verification by agent against a citation is verification,
  but it is not independent of the agent.
- `[RELAYED]` carried from an earlier dispatch or from recollection and not
  re-verified here. A number carrying no tag is `[RELAYED]`.

## 1. The question this dispatch answers

The deflated ladder of dispatch 47 returned a family of candidates
clustered at beta = 1990.411556294948, which is sqrt(eps_r) * k0 for
eps_r = 2 and k0 = 1407.4335088082273 `[VERIFIED]`. Positional by-order
matching paired all three analytic modes against members of that
family, and the resulting relative errors, 0.21514853163021364,
0.5354568093023866 and 1.1071408844921768, are mesh-locked across
levels 1 and 2 `[VERIFIED]`.

One spurious family is already known: the gradient family, which sits at
beta = k0 and is curl-free by construction `[VERIFIED]`. Whether the family
at sqrt(eps_r) * k0 is a second structural artefact of the same kind or a
genuine propagation state of the dielectric slab decides whether the
deflation subspace may be extended to remove it. It is not assumed either way
here, and no classification is recorded in this document.

## 2. The criteria, verbatim from the brief

### 2.1 Task 1, decisive and read-only

> 1. Take the slab-family members from the level-1 and level-2 runs - the
>    states whose beta clusters at sqrt(eps_r)*k0, which positional matching
>    paired against analytic modes.
> 2. For each, report the curl ratio using the same measure `_CURL_RTOL` uses,
>    and the gradient-residual measure used for the first cluster.
> 3. Report the corresponding measures for (i) a known-analytic mode and
>    (ii) a known gradient-cluster member, as calibrated endpoints. Without
>    those two reference values, a curl ratio near 1e-12 is not interpretable.
> 4. Verdict, one of three: `SPURIOUS-CURL-FREE`, `PHYSICAL`, or `MIXED`
>    (members of both characters - which would be its own finding and its own
>    problem).
> 5. Show how the classification would have been called had the calibration
>    endpoints been absent, so we know whether the endpoints were necessary or
>    the result was self-evident.

### 2.2 The hard stops

> If the verdict is `PHYSICAL`, stop. Report and end the dispatch. Do not
> pre-register a deflation of it. The next dispatch will address the pairing
> rule instead.

> If `MIXED`, stop. Report and end. A family containing both characters means
> the pairing rule and the deflation are both wrong in ways that interact, and
> that needs its own design pass.

### 2.3 The fences

> no edits under `emfit/` in Task 1. No levels 4 or 5. No second ARPACK budget
> for level 3. `decisions.md` append-only. Task 2 ends the dispatch - do not
> implement the fix in this dispatch.

### 2.4 Task 2, conditional on a verdict of `SPURIOUS-CURL-FREE`

Task 2 authors `docs/design/deflation_v2_preregistration.md`, frozen and
committed before any implementation, containing the six items the brief
enumerates: the mathematical extension of `Z` to the slab region with the
argument that it removes no physical mode; the preservation check over the
existing seven frozen rows at 1e-12; the by-order criterion restated in a form
that can fail; level 3 as a pre-registered, falsifiable expectation about
whether it converges at the existing 40 * n budget; the standing of section
5.a; and a dated amendment to the anchor pre-registration recording the
by-order failure in the open, before the run it governs.

No part of Task 2 is started in this dispatch unless the verdict of section 3
is `SPURIOUS-CURL-FREE`.

## 3. The measure, as the tree defines it

This section records what the tree's instrument actually computes, because the
brief and the tree differ in a way that bears on the verdict.

The per-candidate quantity is `curl_ratio`, defined in `emfit/mode2d.py` at
:940 as `ratios[i] = float(v @ (k_q[free][:, free] @ v))`, which is
`e^T K_q e / e^T B e` on the B-normalised candidate `e` `[VERIFIED]`.

The tolerance is `_CURL_RTOL = 1.0e-10` at `emfit/mode2d.py:135`, with the
comment that a value below this fraction of the largest one in the set is
curl-free to working precision `[VERIFIED]`.

The comparison, at `emfit/mode2d.py:950-952`, is

    acceptable = np.abs(ratios) >= _CURL_RTOL * r_max

with `r_max` the largest absolute ratio in the candidate set `[VERIFIED]`.
That is a test relative to the set maximum.

The pre-registration states the same threshold in absolute form,
`docs/design/anchor_preregistration.md:604`, "Drop every candidate whose
`Mode2D.curl_ratio <= 1e-10`" `[VERIFIED]`. The two forms are not the same
test, and on this candidate set they do not agree: the slab family spans
absolute values from about 4.7e-23 to 1.37e-9 `[VERIFIED]`, which straddles an
absolute floor of 1e-10 and does not straddle a relative one.

This dispatch reports both forms for every row and does not choose between
them. Where the two forms classify a member differently, the disagreement is
reported as a result and not resolved by preference.

The second measure the brief names, the gradient residual used for the first
cluster, is a subspace-level quantity and not a per-candidate one. It is

    info["residual_grad"] = _ratio(_frob_norm(kq_f @ z), _frob_norm(kq_f) * z_norm)

at `emfit/mode2d.py:1331`, that is `||K_q Z||_F / (||K_q||_F ||Z||_F)`,
documented at :1260-1264 as 0 meaning exactly in the null space `[VERIFIED]`.
At levels 1 and 2 it is 0.0, and it is 0.0 by construction, since `Z` is
built from the gradient space `[VERIFIED]`. It therefore cannot separate one
candidate from another, and the per-candidate analogue used below is
`curl_ratio`. This is recorded as a fact about the instrument, not as a
criticism of the brief.

## 4. Calibration endpoints and decision rule, fixed before measurement

Both endpoints are reported numerically before any slab member is classified,
and the classification then follows this rule and nothing else.

Endpoint G, the curl-free reference: the members of the gradient family at
beta = k0 in the undeflated level-1 record,
`tools/host/anchor/records/level1.json`. That family is absent from the d47
records by construction, because deflation removed it: no d47 file holds a
candidate within 1 per cent of k0 `[VERIFIED]`. If the undeflated record does
not carry per-candidate curl ratios, Endpoint G is recorded ABSENT, the
classification is reported as uncalibrated on that leg, and no substitute is
invented.

Endpoint A, the physical reference: the candidates in the d47 level-1 and
level-2 records that reproduce the frozen analytic values of rows 0 to 3 and
rows 5 and 6 of `docs/design/d47_results.md` section 3 `[VERIFIED]`.

Let `g` be the largest absolute curl ratio among the Endpoint G members, and
let `m` be the smallest absolute curl ratio among the Endpoint A members.

For each slab member with absolute curl ratio `c`:

- `curl-free` if `c <= 10 * g`;
- `physical` if `c >= m / 10`;
- `intermediate` if it satisfies neither.

If `g` is exactly 0.0, the first test is degenerate; it is then reported as
degenerate and only the second test is applied.

The verdict follows mechanically from the member classes:

- `SPURIOUS-CURL-FREE` if every slab member is `curl-free`;
- `PHYSICAL` if every slab member is `physical`;
- `MIXED` if members fall in both classes;
- `UNDETERMINED` if any member is `intermediate` and the members do not split
  across both outer classes.

`UNDETERMINED` is my addition to the brief's three-way vocabulary, and it is a
stop: it means the instrument cannot separate this family from either
reference at the resolution the stored data affords, and a verdict would be an
assumption. It carries the same consequences as `MIXED`.

The decade factors of 10 are fixed here, before the numbers are seen, and are
not adjustable afterwards.

## 5. Where the tree differs from the brief's framing

Recorded before measurement so that the result cannot be read as confirming a
framing that the tree does not support.

1. The family sits at `eps_eff` = 2, which is eps_r, and at
   `beta_sq` = 3961738.16343248 = 2 * k0^2 `[VERIFIED]`. It is therefore not
   the same defect under the same filter: the frozen drop rule is
   `|eps_eff - 1| <= 1e-8` at `tools/host/anchor/ladder.py:144`, constant at
   :63 `[VERIFIED]`, and it keys on `eps_eff = 1`. For a family at
   `eps_eff` = 2 that rule is inert, which is why the d47 runs record
   `n_dropped = 0` and a vacuous separation test `[VERIFIED]`.

2. The tree documents the curl ratios of the first cluster as round-off and
   not zero: `docs/design/deflation_preregistration.md:64` gives
   2.6791731109636385e-10 at level 1 through 6.61052631017697e-09 at level 3,
   and `docs/design/d45_anchor_results.md:67` gives a cluster span of 1.1e-12
   to 4.0e-10 that straddles the frozen 1e-10 cut `[VERIFIED]`. A curl-free
   family in this codebase therefore does not have a curl ratio of zero; it
   has a small one, and the cut already sits inside that spread. That is the
   calibration problem the brief anticipates, and it is real rather than
   hypothetical.

3. `decisions.md:6086-6092` already records that a 1e-10 relative curl floor
   admits the whole near-gradient spectrum `[VERIFIED]`. Nothing here
   overrules that entry.

## 6. What this dispatch does not do

It forms no verdict on levels 4 or 5 and reports no number from them. It takes
no second ARPACK budget and makes no further attempt at level 3. It edits
nothing under `emfit/`. It does not implement any fix. It appends to
`decisions.md` and rewrites no entry there. It alters no threshold in
`docs/design/d47_acceptance.md`, in `docs/design/deflation_preregistration.md`
or in the anchor pre-registration.
