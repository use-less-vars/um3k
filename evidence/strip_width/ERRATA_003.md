# Erratum 003 — `evidence/strip_width/`

Append-only erratum to `evidence/strip_width/PREREG.md`, raised under the escape hatch the freeze itself
names [L, §12 L311-312]: *"A future edit to any of the three files above voids the freeze and requires an
append-only erratum, not a silent re-run."*

**Nothing in `PREREG.md` is changed by this file — not one byte.** Re-measured after this write:
`7a18473b2d65b76a1ff35fd83dde4a0e6622cd75de1a38683f2eeb80d3eea120`, **315 L / 23 921 B** [M]. No `W*.json`
was rewritten, no row was re-graded, no threshold was re-priced, and no new run was performed for this
erratum. Everything below is a reading of artefacts already on disk.

Marks: **[M]** measured against a file in this tree; **[L]** read from a named file/line and cited there;
**[R]** relayed, no artefact behind it.

This is the **third** erratum in this directory and it is scoped to what the other two could not have known:
`ERRATA_001` covers the two metadata-only `tools/host_ladder.py` edits (tasks C/D of `cleanups-cd`),
`ERRATA_002` covers the shift-ladder change itself, and this file covers **the moment the graded rows arrived**
— which is later than both.

---

## (a) `ERRATA_002` and `decisions.md` §151 describe a state that the next three runs superseded: **stale, not wrong**, and no appended entry said so

Timeline, from mtimes [M, `stat`]:

| artefact | mtime (UTC) | state it describes |
|---|---|---|
| `EIG_strip_width.json` | `03:07:24` | EIG witness for all five arms |
| `decisions.md` (`## 151.`) | `03:23:19` | *"`W12.json`, `W16.json`, `W20.json` exist but carry `"rungs": []`"* |
| `ERRATA_002.md` | `03:24:46` | *"Three arms have no `beta_fdtd` row"* (§4 L176) |
| `W12.json` | `03:31:42` | one `beta_fdtd` row, `meta.status == 'ok'` |
| `W16.json` | `03:32:40` | one `beta_fdtd` row, `meta.status == 'ok'` |
| `W20.json` | `03:33:38` | one `beta_fdtd` row, `meta.status == 'ok'` |

So both documents were **correct when written** and were overtaken **seven to ten minutes later**:

- `ERRATA_002` §3 L149-152: *"the verdict recorded under this directory — **INCONCLUSIVE by the missing-arm
  clause** — is the clause applied, not relaxed: `W12`/`W16`/`W20` carry no `beta_fdtd` row, so §4.1's
  'any arm aborted or missing' and §10 **G1** both fire…"* [L]. As of `03:31`-`03:33` the antecedent is
  false: all three carry a row, `meta.complete == True`, `meta.abort_reason is None` [M]. **G1 no longer
  fires and the missing-arm clause is discharged.**
- `ERRATA_002` §4 L176-179: *"Three arms have no `beta_fdtd` row. Their `d_FDTD` values (`0.702 / 0.504 /
  0.333`) are owner-asserted…"* [L] — those three values are now **measured** rows
  (`+0.702075 / +0.503802 / +0.333030` pp [M]) and the `[RELAYED]` mark they carry in §151 is retired by the
  artefacts, not by argument.

`ERRATA_002` §4 L180-182 also declines to check one thing it could not check: *"It does not claim the
executed runs *were* executed with the corrected flag form … per-arm confirmation is in
`meta.npml_per_rung`, which the reader must check rather than assume."* Checked here, for all five arms:
`meta.npml_per_rung == [12]` [M, `W08.json`:56-58, `W08n.json`:56-58, `W12.json`:54-56, `W16.json`:54-56,
`W20.json`:54-56]. The executed form is confirmed. **Corrected here:** `meta.npml` is **`null` on every
arm**, not `12` [M, `meta."npml"`, `W08`:54, `W08n`:54, `W12`:52, `W16`:52, `W20`:52] — the count is
emitted per rung, and `meta.npml_note` states why (`:55`, `:55`, `:53`, `:53`, `:53`): *"--pml-mm holds
the absorber's physical thickness fixed, so npml is re-derived per rung and varies across the ladder;
npml_per_rung is the count actually used."* The earlier citation pointed at the per-rung `"npml": 12`
keys (`:140`, `:140`, `:173`, `:181`, `:189`), which is where the `12` lives; neither those keys nor
`npml_per_rung` is `meta.npml`.

**The defect this item records is procedural, not factual.** `PREREG.md` §12 L311-312 does not only demand an
erratum for a file edit; it demands that the freeze not be amended *silently*. Three graded rows appeared
under a freeze whose own record said those rows did not exist, and **no appended entry said the earlier text
had gone stale** until this one. The fix is this file; the earlier texts stay as written, because rewriting
them is exactly what append-only forbids.

---

## (b) The three graded rows were produced by the **edited** tool. The freeze is engaged; this erratum is the named remedy

`PREREG.md` §12 pins `tools/host_ladder.py` at `1cd1a3e…beb9` / **1106 lines** [L, §12 L304]. The current file
is `0d7191973fe7babf53463205a1da968befcca205e725027ed83dc0267b190c9b` / **1395 lines** [M, `sha256sum`,
`wc -l`]. The chain is:

| step | hash | lines | covered by |
|---|---|---|---|
| frozen at §12 | `1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` | 1106 | `PREREG.md` §12 |
| metadata-only (tasks C/D) | `519365eb4623bd6a1456258565d23dea5aba94af464d02d4d2f8e8752910d57c` | 1261 | `ERRATA_001.md` |
| shift ladder, ascending | `0d7191973fe7babf53463205a1da968befcca205e725027ed83dc0267b190c9b` | 1395 | `ERRATA_002.md` §1.3, §2 — **and this file**, for the rows |

Two things must be said separately, because they are different claims:

1. **The rows prove they came from the edited tool.** They carry schema the frozen tool could not emit:
   `meta.sigma_attempts` [`W12`:70, `W16`:70, `W20`:70], `meta.sigma_retries` ([`[1]`/`[2]`/`[3]`,
   `W12`:104, `W16`:112, `W20`:120]), `meta.sigma_used_per_rung` [155795.91267879284 /
   158811.31744031786 / 161826.7222018429, `W12`:107, `W16`:115, `W20`:123] and `meta.sigma_ladder`
   [`[0.76, 0.775, 0.79, 0.805, 0.82, 0.85]`, `W12`:90, `W16`:98, `W20`:106] [M]. `W08`/`W08n` predate the
   schema and carry **none** of these keys [M] — see (h).
2. **The edit cannot move a pass/fail line.** `SIGMA_MULT = 0.76` is unchanged and is still tried first
   [M, `tools/host_ladder.py`:110]; `TOL_RESID = 1e-8`, `CURL_FLOOR = 1e-6`, `ER = 4.4` are untouched
   [M, L130-131]; the ladder is a search over *where to put the shift*, and the accepted pairs are accepted
   only on the pre-existing residual gate. And the rung the freeze can check twice behaves identically on
   both sides of the edit: `n_strip = 2` gives `beta_eig 389.7256713378306`, residual
   `3.2771050989170236e-14` [M, `EIG_strip_width.json`:35-36] and the same residual in `W08.json`:146 [M].
   §151(i) states this as *"the `n_strip = 2` path is bit-identical across the ladder edit itself"*; the
   numbers above are that claim's evidence and nothing here contradicts it.

Field-reading corrections for anyone re-deriving this from the JSONs [M]:

- **`meta.sigma_mult_used` does not exist.** The key is absent at meta level on all five arms; the accepted
  multiplier is recorded **per rung**, at `rungs[0].sigma_mult_used` = `0.775` (`W12`:201), `0.79`
  (`W16`:217), `0.805` (`W20`:233), and per attempt inside `sigma_attempts`. A report that cites
  `meta.sigma_mult_used` for these rows is citing a key the files do not have.
- `meta.sigma_retries` is the **list** `[1]`/`[2]`/`[3]` (`W12`:104, `W16`:112, `W20`:120); the scalar
  `sigma_retries` (1/2/3) is per rung (`W12`:202, `W16`:218, `W20`:234).
- `meta.sigma_attempts` is a **list per rung** (`:70` on all three); the rung's own attempt list is at
  `W12`:183, `W16`:191, `W20`:199.
- `meta.sigma_used_per_rung` is the **absolute shift**, not a multiplier (see (c)).

---

## (c) §151(f)'s "nine attempts" is the old ladder's **nine entries**, not the banked attempt count, and the residual band it quotes excludes one of the six

`decisions.md` §151(f) reads: *"Its nine attempts are exactly the non-converged attempts banked in
`W12`/`W16`/`W20`, residual `0.93`-`0.99` [M]."* [L, line 9428]. Against the artefacts as they now stand:

- The **nine** is the old descending ladder's multiplier list — `0.760, 0.757, 0.754, 0.751, 0.748, 0.745,
  0.700, 0.600, 0.900` — quoted in that same bullet and in the tool's own comment block [L,
  `tools/host_ladder.py` L116-121]. It is a *ladder length*, available at most once per arm; it is not, and
  cannot be, a count of rows banked across three arms.
- The **banked** non-converged attempts are **six**: 1 in `W12`, 2 in `W16`, 3 in `W20` [M,
  `meta.sigma_attempts[*][*].accepted == false`]. Residuals, in order: `0.9559803168921627` (`W12`);
  `0.9374781042952944`, `0.9523820823233484` (`W16`); `0.9327792913828687`, `0.9650183697692649`,
  `0.9221065847163377` (`W20`) [M]. Each was followed by an accepted attempt at residual `~3e-14`, and each
  arm terminated with `meta.status == 'ok'`, `meta.abort_reason is None` [M]. Nothing was hidden: the
  rejected attempts are in the files.
- The quoted band **`0.93`-`0.99` does not contain `0.9221065847163377`** — `W20`'s third and last rejected
  attempt sits below the band. The band is therefore too narrow as printed, by `0.008`.

Also in `W20`:114 and §151(f): *"The ladder searches over where to put the shift; it is not a threshold"*
[L]. That stands unchanged; the arithmetic is in (g) of the decisions block, not here.

**One stale pointer, substance intact.** `EIG_strip_width.json`:25 (`cross_warrant`) says the junk residuals
*"are the numbers printed in `W12`/`W16`/`W20` `meta.failure`"* [M]. After the re-runs, **`meta.failure` no
longer exists** on any of the three arms [M, `meta` key listing]. The three numbers it quotes survive
bit-identically, as the first rejected attempt of each arm: `0.9559803168921627` / `0.9374781042952944` /
`0.9327792913828687` [M, `sigma_attempts[0][0].best_residual`]. The cross-warrant therefore still holds —
the citation target moved, the values did not. The witness file is **not** edited; `PREREG.md` §4.1 needs no
reading of it, and rewriting a banked witness to fix a pointer is not this dispatch's business.

---

## (d) G5: the flag and the container were **not** as prescribed. Three deviations, stated as deviations

`PREREG.md` §10 **G5** [L, L278-279]:

> *"**G5 resources** — `--mem-ceiling-mb 4000`, one arm at a time, cgroup >= `6144 MB` **verified before the
> first launch** (§5). A run started in a smaller cgroup is void, not graded."*

And §12 L310-311 declares the run environment: *"Container of record for the runs: 6144 MB cgroup"* [L].

What the rows show [M]:

| deviation | measured | prescribed |
|---|---|---|
| memory ceiling | `meta.mem_ceiling_mb == 2000.0` on all five (`W08`:53, `W08n`:53, `W12`:51, `W16`:51, `W20`:51) | `4000` |
| cgroup | `meta.cgroup_limit_mb is None` on all five (`W08`:31, `W08n`:31, `W12`:29, `W16`:29, `W20`:29) | `>= 6144 MB`, **verified before the first launch** |
| environment | `meta.cwd == "/home/jojo/PycharmProjects/EE"` on all five (`W08`:36, `W08n`:36, `W12`:34, `W16`:34, `W20`:34) | the declared `6144 MB` container |

**Disposition of record: G5 is ruled NOT to fire.** The ruling and the objection it overrules are recorded in
`evidence/strip_width/SUMMARY.md` §5, verbatim, together with the three legs a reader can re-check without
trusting the prose (the `null` sentinel, the absence of any comparison against `6144`, the `platform` value
proving `/sys/fs/cgroup` was readable). Two honest limits of that ruling belong here too:

- It is a **ruling**, i.e. an argument over the guard's text and the tool's code
  [L, `tools/host_ladder.py` L182-199], not a measurement. `cgroup_limit_mb()` returns `None` both for
  `"max"` (no finite limit, L190-191) and for a missing/unreadable file, so `None` alone does not distinguish
  "unbounded" from "unreadable"; the platform string and the code path are what carry that distinction.
- The `6144 MB` environment demonstrably **existed and recorded its number** on this tree:
  `evidence/h_refine/h040.json`:27 records `cgroup_limit_mb: 6144.0` and `:48` `mem_ceiling_mb: 4000.0`
  [M]. So none of the three deviations above was a necessity of the machine; each is a divergence from the
  freeze, disclosed rather than absorbed — the same treatment `box_sweep` and `h_refine` gave their own
  post-hoc items.

`ERRATA_002` §3 L166-167 listed G5 among the guards *"untouched"* [L]. That remains literally true — no gate
was re-priced — but it was written when no row existed to carry a flag, so it could not disclose this. This
item is that disclosure.

---

## (e) The arms span **two** git revisions, and G2 is satisfied **on evidence** rather than by assumption

| arms | `meta.git_rev` | line |
|---|---|---|
| `W08`, `W08n` | `1bfd47d75065928ba403efe8333fbe172905969c` | `W08`:48, `W08n`:48 |
| `W12`, `W16`, `W20` | `8b1bab3078f847ea2fe3dbde55c392b57c09dbbd` | `W12`:46, `W16`:46, `W20`:46 |

`PREREG.md` G2 [L, L271-273] requires `W08` to reproduce `evidence/h_refine/h040.json` in `beta_fdtd` **and**
`beta_eig` to `1e-9` relative, and adds that if it does not, *"the other three arms are then not on the same
instrument"*. A reader comparing the two revisions on the rows above would conclude the arms ran on different
instruments. **Check it rather than assume it:**

`W08.json` gives `beta_eig 389.7256713378306` (`:99`) and `beta_fdtd 388.21946125247325` (`:100`);
`h040.json` gives `beta_eig 389.7256713378306` (`:94`) and `beta_fdtd 388.21946125247325` (`:95`) [M]. Both
relative differences are **`0.0`**. G2 passes, and the two-revision split is a `git_rev` string difference,
not a numerical one.

`h040`'s own provenance is worth naming while it is being cited as the instrument reference [M]:
`meta.git_rev` there is the string `unavailable: FileNotFoundError…'git'` (`:44`) — the pre-`cleanups-cd`
resolver, so `h040` cannot name its revision at all — while its `cgroup_limit_mb` (`6144.0`, `:27`) and
`mem_ceiling_mb` (`4000.0`, `:48`) are exactly the G5-prescribed values that (d) records as not met here.

---

## (f) Two Q2 corrections: the digit, and the mechanism

1. **The number is `0.062761` pp, not `0.0622` pp.** `|d_wide − d_narrow| = |0.902013 − 0.839252| =
   0.062761` pp [M], against `0.2202` pp required [L, §4.2 L165-166] — `0.285x` the threshold, i.e.
   **DOES-NOT-MOVE**. `0.0622` is `0.0006` pp away from the recomputation and is not reproducible from the
   rows; §151(e)'s `0.062` pp stands as the rounded form. The verdict is unaffected at this magnitude.
2. **`W08n` is the box-lever arm at `npml 12`, not an `npml 6` variant.** `--npml`/`npml_per_rung` is `12` in
   **both** arms [M, `W08`:54/140, `W08n`:54/140], and the two `meta.command_line` strings differ in exactly
   one flag — `--box-lateral-mult 8` (`W08`:33) against `--box-lateral-mult 1` (`W08n`:33), with
   `box_lateral_mult` `8.0` at `W08`:107 and `1.0` at `W08n`:107 [M]. `W08n` **is** §4.2's `W08-N`
   [L, L151-155]. Any sentence that attributes Q2 to "closing the `npml 6` hole" is wrong about the
   mechanism: the hole was closed for the *other* question (`box_sweep`'s comparator), and Q2 holds the
   absorber fixed and moves the box. The verdict does not depend on this; the explanation does.

---

## (g) `rel_gap`: two different quantities have been printed under one name

§151(a) quotes `rel_gap 0.3914786472678067` for `n_strip = 2`, and the EIG companion prints the same value
[L]. The graded row's own field is `rel_gap_pct = 0.38797902621831604` [M, `W08.json`:145]. They are not the
same quantity:

- `1.293491594615559 − 0.9020129473477523 = 0.3914786472678067` — the **first-order** difference of the two
  solver deltas, both taken against their own per-arm references.
- `0.38797902621831604` — the row's `rel_gap_pct`, which differences the two *relative* deviations
  (`beta/ref − 1`) rather than the absolute `pp` falls.

The two differ by `0.0034996` pp. Neither is wrong; quoting one while computing with the other is. The value
to cite from a row is `rel_gap_pct`; the value to cite from a first-order argument over `d`'s is the
difference of the deltas, labelled as such. The `rel_gap` **trend** (widening, `+0.050 / +0.053 / +0.047`,
total `0.1507` pp) is unaffected — the same sign and the same order under either convention.

---

## (h) Schema gaps that are **not** to be retro-fitted

- `W08` and `W08n` are pre-ladder JSONs: they carry no `sigma_attempts`, `sigma_retries`, `sigma_used_per_rung`
  or `sigma_ladder` at all [M]. §151(g) says the authoritative per-arm shift is `sigma_used_per_rung`; for two
  of five arms that key **does not exist**, and `meta.sigma_mult == 0.76` is the only record. **No field is
  added to those two files and neither file is rewritten by this erratum.**
- The run log prints the retired quasi-static model, `beta_quasistatic_retired 373.2885327644756`
  [M, `W08n`:105 and `W08`:105], while the graded reference is `beta_hj_kj_graded 384.74897567707814`
  [M, `W08`:103]. A reader grading off the console text alone would use the wrong number by `11.46` rad/m.
  Disclosed; the print site is not changed.

---

## (i) What a reader can re-apply without trusting this file

- **The freeze's own reporting policy** [L, §8 L248]: *"Rows are reported even when they would not be
  graded, so the record shows what was measured."* The six rejected sigma attempts in (c) are reported under
  that rule, not as a concession.
- **A10** [L, §9 L265]: this pass reviews its own pre-registration, which is weaker than independent review;
  the mitigation is that every rule in §4/§8 is mechanical over the row keys named in §3, so each number
  above can be recomputed from `evidence/strip_width/*.json` without trusting this prose. Every number in
  this erratum was recomputed that way.
- **The frozen byte count**: `PREREG.md` is `315 L / 23 921 B`,
  `7a18473b2d65b76a1ff35fd83dde4a0e6622cd75de1a38683f2eeb80d3eea120` [M], before and after this write.

## What this erratum does not do

It does not grade anything, convert `decisions.md` §151 in place (that file is append-only and
single-writer), repair the ladder, re-run an arm in the prescribed `6144 MB` environment, add schema to the
two pre-ladder JSONs, or edit `EIG_strip_width.json` to fix the `meta.failure` pointer in (c). Items (a)-(h)
are disclosures; the only artefact they change is this file.
