# Twin-load multifrequency check --- 2026-11-07

**Question.** The loaded sweep (build_A_50ohm, 5 bins, 3.64--8.74 GHz) put `beta_fit` about 3.9 % above `beta_model` on average. Is that bias a property of the fit, or of the loaded termination? A twin build of the same geometry measured with no termination separates the two.

## 1. What was run

    run_multifreq.py --reference evidence/termination/build_A_50ohm_twin_p51_twin.json --unloaded --no-cross-check

Operator run, on host, not re-run during this dispatch. Started 2026-11-07T03:05:55Z, summary generated 03:09:11Z, 0 failures, wall 39.56 / 39.25 / 39.16 / 39.27 / 39.25 s. Same five bins and the same solver settings as the loaded arm; only the load was removed.

Did `--unloaded` take effect? Twin |S11| is 0.0025--0.0112 at every bin against roughly 0.31--0.33 loaded, and twin |S21| is 0.99--1.00. Yes.

## 2. Brackets, frozen before the numbers were read

- **T1** --- twin mean within 0.5 pp of loaded mean: bias is fit-inherent.
- **T2** --- more than 1.5 pp apart: bias is load-specific.
- **T3** --- between 0.5 and 1.5 pp: both, and the split must be stated.
- **T4** --- opposite trend, or three or more bins failed: escalate.

Here delta is `mean(loaded delta_beta) - mean(twin delta_beta)`, in percentage points.

## 3. Per-bin result

| k | f (GHz) | twin dbeta % | loaded dbeta % | delta (pp) | twin \|S11\| | note |
|---|---|---|---|---|---|---|
| 5 | 3.642367 | +3.0797 | +4.0130 | +0.9333 | 0.0025 | |
| 7 | 5.099313 | +3.1441 | +3.2753 | +0.1313 | 0.0075 | |
| 8 | 5.827786 | +3.3642 | +3.6714 | +0.3072 | 0.0112 | |
| 10 | 7.284733 | +3.7259 | +4.4654 | +0.7394 | 0.0108 | |
| 12 | 8.741680 | +4.2861 | +4.1828 | -0.1033 | 0.0077 | beta_ambiguous, excluded from both arms |
| **n=4 mean** | 3.64--7.28 | **+3.3285** | **+3.8563** | **+0.5278** | | |

With k12 included (n=5): twin +3.5200 %, loaded +3.9216 %, delta +0.4016 pp. Every figure above was re-derived from the artefact JSON, and n is stated on each one.

## 4. Verdict

At n=4 the arms differ by 0.53 pp. By the letter of the brackets that is **T3**, outside T1 by 0.03 pp. At n=5 the difference is 0.40 pp and reads **T1**. The 0.5 pp limb is straddled by the choice of n, so both readings are recorded. Nothing turns on the crossover: both deltas sit inside one standard deviation of either arm's scatter (loaded sd 0.51 % at n=4, 0.46 % at n=5).

The substantive result is unambiguous. A build with no load, reflecting below 1 %, reproduces essentially the whole bias: +3.33 % against the loaded arm's +3.86 %. The bias is **fit-inherent, not load-specific**; the termination contributes at most about half a percentage point. k12 is ambiguous in *both* arms, so excluding it is symmetric and costs nothing in fairness.

## 5. What we did not predict

F1 expected the loaded arm to be *more* frequency-dependent, on the argument that load evanescent content grows with frequency. The data say the opposite. The twin's bias climbs monotonically 3.08 -> 3.14 -> 3.36 -> 3.73 % across 3.64--7.28 GHz (n=4, Spearman 1.0, Pearson 0.948). The loaded arm does not: Pearson 0.421 at n=4.

Candidate explanation, offered as a hypothesis and not a conclusion (n=4): the fit's forward model assumes pure TEM, and a real microstrip is not TEM. Longitudinal field components, hybrid-mode content, grow with frequency, so the share of the measured response the model cannot represent grows with frequency, and a fitted beta absorbs it. On the twin this shows up cleanly because nothing else contaminates the data. This sweep does not establish the mechanism.

One correction of record: the twin correlation is 0.948 at n=4. The 0.963 figure is the n=5 value.

## 6. Why this matters more than the number

The bracketed question was whose bias it is. The answer relocates the question. The loaded report `multifreq_beta_test_2026-11-07.md` records that the reflection-optimal and phase-optimal beta for the same records land in intervals that do not overlap (about 222 against 238 rad/m). A fit forced to settle between two mutually exclusive optimal values is missing a term, not mis-calibrated by a load. The 3.9 % beta bias is the symptom; the model form is the disease. Under that reading no amount of load correction removes it --- the twin proves the load is not the source, and the interval disagreement says where to look.

## 7. Provenance and file layout

`run_multifreq.py` builds output names from a fixed prefix with no arm token and no `--out` option: `build_A_50ohm_multifreq_k<k>_<f>GHz.json` in the script's own directory. The twin run therefore wrote to the same seven paths the loaded arm occupied, and overwrote them.

To keep both arms as evidence, the seven twin files were moved --- basenames unchanged --- into `evidence/termination/twin_multifreq/`. The `artefact` fields inside the twin `summary.json` still carry the script's original basenames and resolve inside that directory. The loaded arm is restored at the canonical paths from commit a6ba7f6.

Consequence for the loaded report: `multifreq_beta_test_2026-11-07.md` describes the canonical files as the loaded run left them (started 01:03:26Z, sizes 2855--2862 B, `meta.argv` null, cross-check present). Those descriptions are correct for the files as restored from git; they do not describe what sat on disk between 03:09Z and this bank.

Follow-up, out of scope here: give the script an `--out` argument or an arm token in the prefix.

## 8. Files

- `docs/design/multifreq_twin_2026-11-07.md` --- this document.
- `evidence/termination/twin_multifreq/` --- 7 twin artefacts, bytes verified by md5 across the move.
- `docs/design/dispatch_log.md` --- one row.
