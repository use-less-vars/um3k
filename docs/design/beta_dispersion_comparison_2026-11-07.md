# Beta dispersion comparison — 2026-11-07

Dispatch `beta-dispersion-comparison-2026-11-07`. Read-only analysis of beta values already banked on
disk. No FDTD run, no openEMS, no edit under `evidence/`, `emfit/` or `tools/`.

## 1. Question and provenance

Both arms' fitted beta exceeded the **static** Hammerstad model by 3.08–4.29 % (twin) and 3.28–4.47 %
(loaded). The static model carries no dispersion, so part of that gap is a wrong reference rather than a
wrong fit. This dispatch replaces the static reference with the dispersive Kirschning–Jansen effective
permittivity and restates the residual against it.

Provenance: `beta_static` from `line.beta_model` in the per-bin artefacts under `evidence/termination/`
(loaded) and `evidence/termination/twin_multifreq/` (twin); `beta_twin` / `beta_loaded` from the same
artefacts' `beta_fit`; `eps_eff_qs` = 3.3439383100189377 from `line.eps_eff_model`. k0 = 2*pi*f/c using
each artefact's stored `f_hz_used` (k8 = 5827786408.327286 Hz gives k0 = 122.14137132890411 rad/m).

## 2. Gates

Three gates ran before any table was built. All passed.

| gate | check | measured | result |
|---|---|---|---|
| 1 | `line.beta_model` identical on both arms, 5 bins, matches recorded values | max deviation 0.0e+00 | PASS |
| 2 | in-tree Kirschning–Jansen at k8 vs an independent implementation (228.68 rad/m) | 228.62882383816375, 0.0224 % | PASS |
| 3 | `emfit.microstrip.eps_eff(2.0, 4.4)` = 3.3439383100189377 and (beta_model/k0)^2 reproduces it | deviation 0.0e+00 | PASS |

Gate 3 closes only if k0 uses the artefact's exact `f_hz_used`; the rounded bin frequency 5.827786e9
introduces a spurious 4.7e-7 discrepancy. Recorded so it is not later mistaken for a model error.
The model is the in-tree Kirschning–Jansen (MTT-32 no. 1, 1984). At k8 it gives
eps_eff_f = 3.503776369008842 against eps_eff_qs = 3.3439383 — a +4.78 % permittivity increment and
+2.36 % on beta.

## 3. Table A — residuals against both references

Betas in rad/m; residuals in % of the reference, signed.

| bin | f (GHz) | beta_static | beta_KJ | beta_twin | r_static (twin) | r_KJ (twin) | beta_loaded | r_static (loaded) | r_KJ (loaded) |
|---|---|---|---|---|---|---|---|---|---|
| k5 | 3.642367 | 139.5957 | 141.4232 | 143.8948 | +3.080 | +1.748 | 145.1977 | +4.013 | +2.669 |
| k7 | 5.099313 | 195.4339 | 199.3458 | 201.5786 | +3.144 | +1.120 | 201.8351 | +3.275 | +1.249 |
| k8 | 5.827786 | 223.3531 | 228.6288 | 230.8671 | +3.364 | +0.979 | 231.5533 | +3.671 | +1.279 |
| k10 | 7.284733 | 279.1913 | 287.8323 | 289.5938 | +3.726 | +0.612 | 291.6583 | +4.465 | +1.329 |
| k12 | 8.741680 | 335.0296 | 347.8431 | 349.3893 | +4.286 | +0.445 | 349.0433 | +4.183 | +0.345 |

Residual = (beta_fit - beta_ref) / beta_ref * 100.

The Kirschning–Jansen increment over static runs +1.309 % at k5 to +3.825 % at k12, and removes between
half and five-sixths of the gap: mean r_KJ is +0.981 % (twin) and +1.374 % (loaded), against +3.520 %
and +3.922 % before the correction.

The shape matters more than the magnitude. r_KJ is uniformly **positive** and decays with frequency,
+1.748 % to +0.445 % in the twin arm. A residual caused purely by a wrong reference would be absorbed
exactly by the correction and would not leave a one-sided, frequency-dependent remainder. The remainder
is therefore a systematic on the fit itself, or Kirschning–Jansen under-predicting at the low end, or
both. This dispatch does not separate them.

## 4. Table B — attributed external values, k8 only

These are **not** computed in this repository. They are attributed to the reviewer's independent
implementation and are reproduced for context.

| model | beta at 5.827786 GHz (rad/m) | residual vs this project's fit |
|---|---|---|
| static Hammerstad | 223.39 | +3.7 % |
| Kirschning–Jansen | 228.68 | +1.3 % |
| Kobayashi | 228.89 | +1.2 % |
| Yamashita | 229.90 | +0.7 % |
| this project's fit | 231.5533 | — |

**Declaration.** Kobayashi and Yamashita have no implementation anywhere in this tree, and
`.scratch/r1_writeup.md:41-43` records a standing refusal to quote them, since quoting a number would
mean quoting from memory. They appear above at k8 only, attributed, recomputed nowhere, and no
arithmetic in this document depends on them. Our own Kirschning–Jansen value at k8 agrees with the
reviewer's 228.68 to 0.022 %, which is the reason their column is worth printing at all.

## 5. Bracket verdict

Pre-registered: r = (beta_fit - beta_KJ)/beta_KJ * 100; M = max |r| over the ten (bin, arm) cells;
n_over3 = the number of bins at which either arm exceeds 3 %.

**M = 2.669 % (k5, loaded arm). n_over3 = 0. D2 fires: "partial correction; bank with an explicit error
bar."**

D2 was written as: 2–3 % at some bins, partial, bank with an error bar. That is what happened, and the
error bar is not a formality — it is the entire content of D2. Dropping the k12 bin, where beta is
ambiguous in both arms, leaves M unchanged; D2 stands on four bins as well as five.

## 6. Does the reviewer's residual reproduce?

Two claims were made. At 3.64 GHz the residual is +1.748 % (twin) and +2.669 % (loaded). The quoted band
was +1.5 to +1.7 %, so the claim reproduces for the twin arm — marginally above the band's upper edge —
and does not reproduce for the loaded arm.

At 7.28 GHz the residual is +0.612 % (twin) and +1.329 % (loaded). **The claimed ~0 % does not
reproduce.** The residual does not fall to zero anywhere in the band; the smallest value reached is
+0.345 % at k12 in the loaded arm. The reviewer computed against Yamashita, which is not available
in-tree, so the difference cannot be attributed to a like-for-like comparison. It is reported as a
discrepancy and left open.

## 7. Point optima versus acceptance windows

`docs/design/beta_refit_test_2026-11-05.md` section 9.2 contains two different objects that are easy to
conflate, and the confusion changes the story.

*Point optima* are single betas: |Gamma_port| = 0.34465 at beta = 222.321546277827; arg Gamma_port =
-107.68 deg at beta = 237.926169033850; the residual minimum at beta = 231.046199503169.

*Acceptance windows* are intervals, an arbitrary pre-registered test band and not optima:
|Gamma_port| in [0.32, 0.34] if and only if beta in [224.575706, 234.529283]; s11 residual below 2 deg
if and only if beta in [236.146125, 239.710245].

The fit at 231.5533 sits **between** the two point optima — +4.15 % above the magnitude-optimal beta and
-2.68 % below the phase-optimal beta. It is the residual minimiser, not a deliberate split of the
difference between two targets; no mechanism in the fit knows where the optima are. The two acceptance
windows do not overlap, 234.529 < 236.146, and that non-overlap — not the position of the fit — is the
sharp statement that no single beta satisfies the phases and either anchor together.

## 8. Limitations

1. The reference is now a closed form carrying its own error of order 1–2 %. Kirschning–Jansen is a
   quasi-static fit to full-wave data, not an exact solution. At the residual now reported, 0.3–2.7 %,
   reference-model error is comparable to or larger than the signal, so r_KJ bounds the fit error only
   from above and cannot confirm it from below.
2. Five bins, and no uncertainty on beta_fit is quoted here. No significance is claimed on M, on the
   mean residual, or on the frequency trend in section 3.
3. Kobayashi and Yamashita are absent in-tree, per section 4. Two of the four reference models that
   motivated this comparison could not be computed in this repository.
4. The one-sided offset and its decay with frequency are described, not explained. Separating fit bias
   from reference bias at this precision needs either an uncertainty on beta_fit or a model the repo
   does not have.
5. The loaded arm carries a load-plane |S11| residual of its own, tracked separately. Nothing in Table A
   corrects for it, so the loaded column inherits that error undivided.
