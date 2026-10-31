# Erratum 002 — `evidence/strip_width/`

**Append-only erratum to the freeze declaration.** This file amends `evidence/strip_width/PREREG.md`,
frozen **2026-10-31T01:53Z** and committed as **`5af2756`**. `PREREG.md` is not modified — not one byte —
and nothing here restates, softens or re-opens a clause it froze. It discharges §12's own instruction:
*"A future edit to any of the three files above voids the freeze and requires an append-only erratum, not
a silent re-run."* `ERRATA_001.md` (this directory, 163 lines) is the first such erratum and covers the
metadata-only edits to `host_ladder.py`; this one covers the three run-definition facts a reader of the
frozen protocol would otherwise get wrong when re-running it.

Issued under the strip-width evidence pass `strip-width-docs-2026-10-31` (dated slug — no dispatch number
is verifiable in this tree).

**No FDTD run is performed, graded, re-graded, re-priced or extrapolated by this erratum.** One arm of
this directory is banked (`n_strip = 2`, `W08.json`); three (`W12.json`, `W16.json`, `W20.json`) exist as
files carrying `"rungs": []` and **no `beta_fdtd` row at all**. The Q1 verdict is **INCONCLUSIVE by the
missing-arm clause** (§4.1, §10 G1) and stays that way here; nothing in this file converts an
owner-asserted number into a measured one, and no `d_FDTD` is invented for the three missing arms.

## 1. What changed, and why

Three disclosures. None of them touches the grading rule, the thresholds, or a frozen number; all three
are about **what a run of this protocol actually is**. (1.1 is a mismatch between this directory's own §2
template and `tools/host_ladder.py`; 1.2 and 1.3 are properties of the tool as inherited —
`519365eb…0d57c`, 1261 lines → `0d719197…190c9b`, 1395 lines.)

### 1.1 The §2 command template is unexecutable as printed

`PREREG.md` §2 (L65-74) prints the arm invocation with **both** absorber flags:

```
--pml-mm 4.8 --npml 12
```

`tools/host_ladder.py` L1198-1202 makes those two flags mutually exclusive and calls `ap.error(...)`, so
the printed command exits **2** (argparse usage error) without meshing anything. The executed form is

```
--pml-mm 4.8
```

alone. **This is a documentation defect and not a run defect.** `--pml-mm` holds the absorber's *physical*
thickness fixed; the tool re-derives the layer count per rung (`npml = round(4.8 / 0.4) = 12` at
`h = 0.4 mm`), which is exactly the `npml 12` the template intended, and `meta` records both
`npml_per_rung` and a `npml_note` saying so in as many words (*"--pml-mm holds the absorber's physical
thickness fixed, so npml is re-derived per rung"*). The realised grid is therefore the grid the template
meant, and the banked arm is gradeable as-is.

**Disclosed rather than repaired:** the template text is not edited. `PREREG.md` is frozen, and an erratum
that quietly rewrites the command would leave two documents disagreeing about what was frozen while
looking like one document. A reader re-running an arm should drop `--npml 12` and read `npml_per_rung` out
of the row instead of assuming the flag was accepted.

### 1.2 `--max-rungs` is silently inert under `--h`, so `meta.max_rungs` is not the authority

L1216-1218 read

```python
rungs = RUNGS_MM if args.max_rungs == 0 else ...
if args.h is not None:
    rungs = (args.h,)
```

so a single-rung invocation (`--h 0.4`) **overwrites** whatever `--max-rungs` produced. The flag is
accepted, echoed into `meta.max_rungs`, and then has no effect. The authoritative record of what ran is
the single-element `meta.rungs_mm` (with `meta.rungs_requested` showing what was asked for). A reader
auditing "how many rungs did this arm request" from `meta.max_rungs` is reading an uninformative field.

**Disclosed rather than repaired.** Making a silently-ignored flag loud changes CLI semantics under a
freeze; that is a tool dispatch with its own regression, not a line to slip into a documentation pass. The
correct reader behaviour today is: **`meta.rungs_mm` is authoritative, `meta.max_rungs` is not.**

### 1.3 The shift policy is part of the run definition, and the ladder ascends

`solve_ladder()` searches a ladder of shift multipliers for the one that makes the eigensolve return a
*physical* pair at the arm's width; the shipped ladder is

```python
SIGMA_LADDER = (SIGMA_MULT, 0.775, 0.79, 0.805, 0.82, 0.85)     # SIGMA_MULT = 0.76
```

and it **ascends**. The reason is measured, not stylistic: the previous search walked *down*
(`0.760, 0.757, 0.754, 0.751, 0.748, 0.745, 0.700, 0.600, 0.900`) and at `n_strip = 3` it recovered
**zero** real pairs, with the shift drifting from `894` to `9123` below the mode it exists to sharpen.
Those nine attempts are precisely the non-converged attempts banked in `W12`/`W16`/`W20`, whose
`meta.failure` residuals are `0.9559803168921627`, `0.9374781042952944`, `0.9327792913828687`.

Three consequences belong in the record, because a reader diffing this directory against the tool will
otherwise read a re-tune where there is none:

- **The first shift is unchanged.** `SIGMA_MULT = 0.76` is tried first, exactly as before, and the arms
  that were accepted at `0.76` (`n_strip = 2`) are bit-identical under the new code — `beta
  389.7256713378306`, residual `3.2771050989170236e-14`, `lam 151886.09889972274`, `sigma
  152780.5079172678`. The ladder only changes what happens *after* `0.76` fails.
- **The accepted per-arm multipliers differ by width**, and the authority is the row, not the constant:
  `n_strip 2 → 0.76`, `3 → 0.775`, `4 → 0.79`, `5 → 0.805` (with `0.82` and `0.85` available and
  unaccepted). `meta.sigma_used_per_rung` carries these; `meta.sigma_mult` is the *first* attempt and must
  not be read as "the shift used". The tool says so itself in `sigma_ladder_note` (*"can differ from the
  constant sigma_mult on a wider strip"*), which is the point: `sigma` is `k0²·ER·0.76 =
  152780.5079172678` at every width while `beta²` walks `151886 → 155636 → 158948 → 161903 (rad/m)²`, so
  a single constant multiplier stops being a defensible silent default as the strip widens.
- **No threshold moved.** `TOL_RESID = 1e-8`, `CURL_FLOOR = 1e-6` and `ER = 4.4` are untouched, and
  `meta.residual_limit` still emits `1e-8`. *The ladder searches over where to put the shift; it is not a
  threshold.* No pass/fail line in §4.1 or §10 can move because of it, which is what makes this a
  disclosable run-definition fact rather than an amendment to the test.

## 2. Hashes, before and after

[M, `sha256sum` in this dispatch; the two "before" values are the states this pass inherited and are also
recorded in the preceding dispatch report `reports/2026-10-31_04-09-18_Dispatch_report__sigma_ladder___strip-width_EIG_co.md`.]

| file | sha256 before | sha256 after | size after |
|---|---|---|---|
| `tools/host_ladder.py` | `519365eb4623bd6a1456258565d23dea5aba94af464d02d4d2f8e8752910d57c` (1261 L) | `0d7191973fe7babf53463205a1da968befcca205e725027ed83dc0267b190c9b` (**1395 L**) | 69 495 B |
| `evidence/strip_width/PREREG.md` | `7a18473b2d65b76a1ff35fd83dde4a0e6622cd75de1a38683f2eeb80d3eea120` (315 L, frozen) | **unchanged** — `7a18473b…d3eea120` | 23 921 B / 315 L |
| `evidence/strip_width/EIG_strip_width.json` | — (new) | `213800762cb242ee531e2cb14f25fb72b12d70dbc833a484ac421182c7580f0e` | 421 L / 18 902 B |
| `evidence/strip_width/_make_EIG_strip_width.py` | — (new, generator) | `36d1538699f509fcc325e158b0317408a31c13834d0ff9f51a96c688c232a789` | 246 L / 18 589 B |
| `decisions.md` | `9d64054fc3b6e6caaf81596ae5c641830b3fa7c5eaa6c22faa2bdbc3a2f3c975` (9415 L) | `8de4528587378ccb2c7ec2206b975b73b2cf437704d002b99abf791529511622` (9434 L, +19) | `## 151.` appended at EOF |
| `docs/design/dispatch_log.md` | `2604eb20de55c5886a00d3da98d6c086a47ba2a10d78f1b7bd86f637df187df4` (76 L) | `cc955a6de099b50c2cc1c3488894312fdeb7245cb44e0b3947435eb9386c3615` (89 L, +13) | one row + one section |

**The frozen artefacts of this directory did not move.** `PREREG.md` is byte-identical to its frozen
state, `W08.json` / `W12.json` / `W16.json` / `W20.json` are untouched, and `EIG_strip_width.json` is a
**new** witness that neither replaces nor re-grades any of them.

Protected files, re-verified unchanged at the end of this pass [M]:

- `tools/d585_modal.py` `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6`
- `emfit/studies.py` `578650bc59b1dbaa09832ec3dde2c0058fa69e0dcee56c2e8a4cc7ff37e802ac`
- `emfit/mode2d.py` `b820a3fd4acbfd425e440910685da81c03c8a8ee7b3988e5bdb7a6a7f199c534`

The graded reference (`hammerstad_beta` + `kirschning_jansen_peff`) lives in `tools/d585_modal.py`, which
did not move; no number in this directory can have changed because of anything in this erratum.

## 3. Why the freeze is not voided — clause by clause

The freeze's object is the **grading rule and the artefacts**, and neither was touched. Each clause that
could plausibly be argued to bite:

- **§1 (arms, `W → n_strip`).** Unchanged. No arm is added, removed or redefined; 2/3/4/5 still map to
  `0.8/1.2/1.6/2.0 mm`.
- **§2 (command template).** The *text* is unchanged and is wrong as printed (§1.1). What this erratum
  amends is the reading, not the file: the executed invocation omits `--npml 12`, re-derives it as `12`,
  and produces the intended grid. §2's intent — absorber thickness `4.8 mm` — is exactly what the executed
  form enforces.
- **§3 (keys).** Unchanged. `meta.npml_per_rung` and `meta.rungs_mm` exist to carry the realised values;
  this erratum tells the reader which field to believe, and adds none.
- **§4 (`d_W`, `Delta_min = 0.0734` pp, `3·Delta_min = 0.2202` pp).** Unchanged, unrecomputed. Nothing here
  re-derives `Delta_min` and the §7 circularity disclosure stands exactly as disclosed.
- **§4.1 (the five criteria, the three verdicts, "guards first, then the rule").** Unchanged. In particular
  the verdict recorded under this directory — **INCONCLUSIVE by the missing-arm clause** — is the clause
  applied, not relaxed: `W12`/`W16`/`W20` carry no `beta_fdtd` row, so §4.1's "any arm aborted or missing"
  and §10 **G1** both fire and the two solver sides cannot be compared at all.
- **§5 (sizing gate).** Unchanged. No run is priced here.
- **§6 (confounds).** Unchanged, and §6's own statement that the EIG half is *"not an independent
  measurement of `h`"* is the reason §1.3's per-arm shift matters: the eigen leg is a consistency witness
  under a documented shift policy, not a second measurement of the mesher.
- **§7 (`Delta_min` provenance).** Unchanged; the disclosed circularity is neither amplified nor reduced by
  disclosing a shift policy.
- **§8 (three-outcome table; Q2 at `0.2202` pp).** Unchanged. The Q2 statement — **LEVER DOES NOT MOVE** —
  is a measurement against that threshold, not a threshold adjusted to a measurement.
- **§9 (A1-A10).** Unchanged.
- **§10 guards.** **G1** (completeness) is what produces the INCONCLUSIVE, above. **G2** (W08 must reproduce
  `evidence/h_refine/h040.json` in `beta_fdtd` *and* `beta_eig` to `1e-9` relative) is strengthened rather
  than weakened by the evidence that the instrument is bit-exact across containers: this dispatch shows a
  relative difference of **`0.0`** on **both** columns [M]. **G3** (tone record), **G4** (reference
  reachability), **G5** (resources), **G6** (geometry ±5 %) and **G7** (mode identity in `[1/3, 3]`) are
  untouched — and note that §1.3's ascending ladder is what makes G7 satisfiable at all on a wider strip;
  under the descending ladder no pair reached the identity test because none was physical.
- **§11.** Unchanged; no arm is added to the sequence.
- **§12 (this file).** The freeze's own escape hatch is the append-only erratum, and that is what this is.
  `PREREG.md` remains the single statement of the protocol; this file is the second, and where the two
  differ the difference is named above in numbered subsections, not woven into the frozen text.

## 4. What this erratum does not establish

- **It does not grade Q1, and it does not make Q1 gradeable.** Three arms have no `beta_fdtd` row. Their
  `d_FDTD` values (`0.702 / 0.504 / 0.333`) are owner-asserted and are treated in `decisions.md` §151 as
  `[RELAYED]`: not graded, not extrapolated, not quietly promoted. Booking those three rows (or re-running
  the three arms) is the one action that converts the status, and it is not taken here.
- **It does not claim the executed runs *were* executed with the corrected flag form.** It states that the
  form printed in §2 cannot execute and that the form which does execute reproduces the intended grid;
  per-arm confirmation is in `meta.npml_per_rung`, which the reader must check rather than assume.
- **It does not repair either tool defect.** `--max-rungs` is still silent (§1.2) and the descending ladder
  is still in the git history (§1.3). Both are disclosed so that a future dispatch can fix them under its
  own regression, not smuggled in under a documentation change.
- **It does not re-open the box question.** Box loading is frozen at `lat 8 / lid 1` by the declaration and
  stays frozen; `decisions.md` §151(d) records why the transverse-box error is not separable from strip
  meshing at two cells, which is a reading of existing evidence, not a new sweep.
- **It does not rehabilitate the descending ladder's numbers as a negative result.** Nine multipliers
  returning zero physical pairs says the *search* was in the wrong place; it does not say the mode does not
  exist at those widths. The ascending ladder finding pairs at `0.775 / 0.79 / 0.805` with residuals
  `~3e-14` is the demonstration that the mode existed all along.
- **It does not touch `grid_for(0.3)`.** The `20 %` silent narrowing (`n_sub 5`, cell `0.32 mm`, meshed
  `0.64 mm` against `0.8 mm`, banker's rounding `2.5 → 2`) is real and **dormant**: `h = 0.26667` and all
  five frozen rungs report a realised/pinned ratio of `1.000000`, so no frozen row is affected. Repairing
  the mesher under committed artefacts is a dispatch of its own.

## 5. Recovering the pre-edit file

Nothing here has to be taken on trust. The frozen, pre-edit file remains recoverable:

- `git show 5af2756:tools/host_ladder.py` reproduces
  `1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` (1106 lines) exactly — the state
  `PREREG.md` §12 pinned.
- The state this pass inherited is `519365eb4623bd6a1456258565d23dea5aba94af464d02d4d2f8e8752910d57c`
  (1261 lines), the metadata-only edit `ERRATA_001.md` describes.
- `git diff 5af2756 -- tools/host_ladder.py` is the whole code edit; the three disclosures above account
  for every behaviour difference between the frozen and the shipped file, and the `--help` text is
  byte-identical across all three states, so no flag was added or removed along the way.

`PREREG.md` itself needs no recovery step: it was never written to.
