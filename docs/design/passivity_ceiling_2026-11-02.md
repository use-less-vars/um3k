# The passivity ceiling: |s21| <= 1 for a series resistance in a shorted line

**Status:** established by arithmetic on committed artefacts. No solve, no fit, no tuning.
**Date:** 2026-11-02
**Arms:** `evidence/termination/build_A_50ohm_v3b_c51.json` (D), `build_A_50ohm_v3c.json` (A), `build_B_100ohm_v3d.json` (B), `build_E_50ohm_v3d.json` (E).

Tags: [M] read from a stored artefact field, [L] literal arithmetic on [M] values, [R] read from source in this tree, [UNVERIFIED] inferred or judged.

## 1. The ceiling

The closed form for a series impedance R in a line of impedance Z0, shorted a distance L downstream, is

    b2/a1 = t / (1 + r * exp(-2j * beta * L)),   t = 2*Z0/(2*Z0 + R),   r = R/(2*Z0 + R)

with `t = 1 - r` identically, because 2Z0/(2Z0+R) + R/(2Z0+R) = 1. [L]

For any real beta the denominator is 1 plus a vector of fixed modulus r, so

    |1 + r*exp(-2j*beta*L)| >= 1 - r,   with equality iff exp(-2j*beta*L) = -1

and therefore

    |b2/a1| <= t/(1 - r) = (1 - r)/(1 - r) = 1.     [L]

The bound is attained, not merely approached: a half-wave stub, 2*beta*L = pi, gives exactly 1. So 1.0 is the maximum of this whole family over beta, Z0, R and L.

## 2. Why it is physical, not a modelling assumption

A series resistance in a length of line is a passive, reciprocal structure. Passivity forbids |s21| > 1 for any beta, any Z0, any L, any extraction plane and any reference convention. The derivation above is the ideal-circuit statement of that bound; the physics does not depend on the closed form being the correct model of this particular structure.

## 3. Observation: two arms sit above it

| arm | s21.magnitude | s21.raw_magnitude | ceiling |
|---|---|---|---|
| A | 0.7675575 | 0.8074301 | 1.0 |
| D | 0.7600910 | 0.7600910 | 1.0 |
| B | 1.1650275 | 1.1688893 | 1.0 |
| E | 1.0152299 | 1.0196007 | 1.0 |

A and D are below the ceiling. B is 16.9 per cent above it and E is 1.96 per cent above it, on both the referenced and the raw field, so the excess is not introduced by the twin normalisation.

## 4. Consequence

No value of beta reproduces B or E. The best this family can reach is 0.9748 for B and 0.7912 for E, both at their own fitted `line.beta` [L]. Therefore:

  * a failure of B and E to match the closed form is NOT evidence against the closed form, and must not be reported as such;
  * B's and E's |s21| are not passive transmission magnitudes - whatever they are, they are not the quantity the model predicts; and
  * the argument uses no beta, no Z0, no L, no plane convention and no load-kind assumption, which makes it the most robust single statement this investigation has produced.

It corroborates the plane-50 / plane-51 non-passivity finding from an independent direction. Plane 50 reads 1.1051854 against 0.7600910 at plane 51 on the same mesh, a ratio of 1.454, reproduced at 1.465-1.491 on four further plane-50/plane-51 pairs.

## 5. What this does NOT settle

  * It does not identify the mechanism. The contaminated-cut-probe reading - `emfit/studies.py:2964-2968` averages columns ix_extract-1 and ix_extract, and the load is a sigma stamp on one of those columns - is [UNVERIFIED] as the cause.
  * It says nothing about whether the shorted-stub explanation is correct for D or A. D's agreement is conditional on a substituted Z0; see dispatch row `s21-shorted-stub-verification-2026-11-02`.
  * It bounds transmission only. It says nothing about |s11|.
  * It does not establish that any other recorded |s21| in this directory is trustworthy. It establishes only that two of them cannot be.

## 6. Relation to the shorted-strip finding

All of the above is arithmetic on recorded fields and needs no structural claim. The structural claim it complements is separate: `emfit/studies.py:2704-2712` builds six PEC walls from `cc.pec_edge_mask()` and then sets the strip mask PEC-true from the port column to node nx, with the xmax PML BEHIND that wall. The line is therefore never terminated - the load sits inside a shorted stub - so the series-R anchor T = 2Z0/(2Z0+R) never applied to any of these runs, and |s21|/T is a ratio between two unrelated quantities. Load-to-wall is 22 cells (8.8 mm) for A and 12 cells (4.8 mm) for B, D and E; load-to-PML is 16, 6, 6 and 6. Open question, [UNVERIFIED]: the PEC wall sits behind the absorber in every arm, and L = load-to-wall is what reproduces D's 0.7601 - L = load-to-PML-front (6 cells) would predict about 0.535 - so the far wall is the governing reflector despite a six-cell absorber in front of it, which is not explained.
