# D58.13 — strip-width sweep, SUMMARY of record

Marks: **[M]** measured this pass against a committed artefact (a JSON, a line count, a hash); **[L]** read
from a named file/ledger and cited there rather than re-measured; **[R]** relayed (console text only, no
banked artefact); **[UNVERIFIED]** asserted here but not checkable from the tree.

Fence: this file grades and documents only. No run was performed for it, `PREREG.md` was not edited, and
no `W*.json` was rewritten or retro-fitted. Every number below is recomputed from
`evidence/strip_width/W08.json`, `W08n.json`, `W12.json`, `W16.json`, `W20.json` [M].

---

## 0. Read this first: these are FOUR LINES, NOT ONE

The design says so itself, before any number existed — `PREREG.md` §0, L35-38 [L]:

> *"**The honest framing, stated before the numbers exist:** these are four *different lines*, not one
> line meshed four ways. A wider strip is a lower-impedance line with a different `eps_eff`, so both the
> reference *and* the physics move between arms. Only the per-arm ratio `d_W` is comparable across arms
> (§3, §6.1). This is the single largest limitation of the design and it is not repairable within it."*

That is not a hedge bolted on afterwards; it is the first thing the frozen protocol says about its own
design. Three clauses carry it, and the clause numbers a reader will be told to check are the right ones:

1. **§0 (L35-38)** — the four-lines framing, quoted above [L].
2. **§3 (L84-108)** — the reference is *recomputed per arm*, at that arm's own realised tone, because
   *"Both the tone and the width enter, so the reference is recomputed per arm"* (L89-90) [L]. And the
   reference is **not** W-independent: it rises `+1.37706 / +2.59789 / +3.67464` pp across W12 / W16 / W20
   [L, L99-100; arithmetic re-checked against `beta_hj_kj_graded` in each JSON, M]. Grading `d_W` instead
   of `beta` is what makes the arms comparable, and §3 states the limit of that move in the same breath:
   *"the reference's own W-dependent *error* is not cancelled by this and is not measured here"*
   (L102-103) [L].
3. **§6.1 (L197-199)** — the first declared confound: *"**A different line at every arm.** `W` sets
   `eps_eff`, `Z0` and the reference (3.67 pp across the sweep, §3). The comparison is `d_W` vs `W/cell`,
   *not* `beta` vs `beta`. HJ+KJ's W-dependent error does not cancel and is not bounded here."* [L]

The pre-freeze adversarial review reached the same place and left it standing: attack **A1**
(*"Four arms of four *different lines* is not a meshing study …"*) is dispositioned
**"Disclosed, not repaired"** [L, §9, L256].

**Consequence that governs everything below.** `d_W` falling across the sweep is evidence that a
strip-meshing error of order `0.2 pp` is *present* at `n_strip = 2`; it is **not** evidence that the
reference is right, and no arm in this design can supply that evidence. §4.1 declares this in advance
(L143-147) [L] and §11 repeats it: the sweep *"does not bound HJ+KJ's own accuracy at any `W`"* [L, L290-291].

---

## 1. The banked arms, and the row-count resolution

**All five files are listed on this page. There are FOUR Q1 arms and ONE Q2 arm — not five, not six.**

Resolution of the count an earlier brief carried: it asked for a *six-row* table, which double-lists
`W08n` as if it were a sixth Q1 arm. It is not one. `W08n` has `n_strip = 2` — the same strip width
(0.8 mm), the same `h`, the same `npml 12`, the same 4.8 mm absorber — and differs from `W08` in exactly
**one** flag, `--box-lateral-mult 1` instead of `8` [M, `meta.command_line` in both files; `box_lateral_mult`
1.0 at `W08n.json:107` vs 8.0 at `W08.json` rung]. It is `PREREG.md` §4.2's `W08-N`, the box-lever arm
[L, §4.2 L151-155], so it belongs to Q2 and is reported **once**, there. The Q1 table therefore has four
rows (`n_strip = 2,3,4,5`) and the Q2 block has two arms that share an `n_strip`.

### 1.1 Q1 — the four strip-width arms (graded column = `d_W`)

`d_W = 100*(beta_fdtd/ref(W, f_hz) - 1)` pp, `ref = beta_hj_kj_graded`, recomputed per arm [L, §3-§4;
every cell [M] from the JSONs].

| arm | `n_strip` | W mm | `beta_fdtd` | ref (HJ+KJ) | `d_W` pp | `beta_eig` | `d_EIG` pp | `rel_gap` pp | `n_cells` | `peak_rss_mb` | `wall_fdtd_s` | residual |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| W08 | 2 | 0.8 | 388.21946125247325 | 384.74897567707814 | **+0.902013** | 389.7256713378306 | +1.293492 | 0.387979 | 415 072 | 385.359375 | 54.371671 | 3.2771050989170236e-14 |
| W12 | 3 | 1.2 | 392.78566209964987 | 390.0472372151286 | **+0.702075** | 394.5069378715431 | +1.143375 | 0.438223 | 416 976 | 390.246094 | 53.787209 | 3.134813785874957e-14 |
| W16 | 4 | 1.6 | 396.73324115721647 | 394.7445116131979 | **+0.503802** | 398.68271603684286 | +0.997659 | 0.491382 | 418 880 | 406.207031 | 55.248981 | 3.3010964892506367e-14 |
| W20 | 5 | 2.0 | 400.2154609833936 | 398.88704687479526 | **+0.333030** | 402.37133087951725 | +0.873501 | 0.538677 | 420 784 | 435.328125 | 54.597534 | 2.977090364577061e-14 |

Status of all four: `meta.status == "ok"`, `meta.complete == true`, `meta.abort_reason == null`, one row
each [M]. Residuals are ~6 orders inside `TOL_RESID = 1e-8` (`1e-6` is `CURL_FLOOR`, a different constant)
[M, `meta.residual_limit` = 1e-08 in every file; `tools/host_ladder.py` L130-131].

Reading the table without any rule: `|d_W|` falls 0.902013 → 0.702075 → 0.503802 → 0.333030 pp across a
strip that widens from 2 to 5 cells [M].

### 1.2 Q2 — the box-lever pair (separate reading, same `n_strip`)

| arm | `--box-lateral-mult` | `--box-lid-mult` | `npml` | `beta_fdtd` | `d_W` pp | `beta_eig` | `d_EIG` pp | `rel_gap` pp | `n_cells` | `peak_rss_mb` | `wall_fdtd_s` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| W08 (wide) | 8.0 | 1.0 | 12 | 388.21946125247325 | +0.902013 | 389.7256713378306 | +1.293492 | 0.387979 | 415 072 | 385.359375 | 54.371671 |
| W08n (unit) | 1.0 | 1.0 | 12 | 387.9779902994508 | +0.839252 | 392.5024902740328 | +2.015214 | 1.166174 | 95 200 | 162.207031 | 10.785673 |

`beta_fdtd`/`beta_eig`/`ref`/`rel_gap` cited from `W08.json:100,99,103,145` and `W08n.json:100,99,103,145`
[M]. `W08n`'s `beta_hj_kj_graded` is the *same* `384.74897567707814` [M, `W08n.json:103`], because the
reference depends on `W` and tone only, and both are identical.

---

## 2. The two readings, kept separate and labelled

They answer different questions and must never be merged into one sentence without the other.

### Reading A — the pre-registered verdict form (graded)

`PREREG.md` §4.1 requires all of (1)-(5) on the **FDTD** column [L, L120-130]:

| leg | requirement | measured | verdict |
|---|---|---|---|
| 1 | each of the three steps falls by more than `Delta_min = 0.0734` pp | 0.199938 / 0.198273 / 0.170772 pp [M] | **PASS** |
| 2 | total fall `> 3*Delta_min = 0.2202` pp | 0.902013 − 0.333030 = 0.568983 pp [M] | **PASS** |
| 3 | `|d_W(5)| <= 0.5*|d_W(2)|` | 0.333030 / 0.902013 = 0.369208 [M] | **PASS** |
| 4 | the two solvers' total falls differ by `<= 0.2202` pp | \|0.568983 − 0.419990\| = 0.148993 pp **[derived; one input relayed (†)]** | **PASS** |
| 5 | *"no guard in §10 fired"* [L, L130] | G1-G4, G6, G7 pass; **G5 ruled not to fire** (§5 below) | **PASS** |

**(†) Leg 4's `0.148993` is derived, not a field in any artefact.** Both sides of it are themselves total
falls — `d(2) − d(5)` on each solver's column, where `d` is that solver's deviation from the per-arm HJ+KJ
reference in pp — so the row is a difference of four derived numbers, and it is marked *derived* rather than
`[M]` for that reason alone. The FDTD side is `[M]` end to end: `W08.json`:99-103 gives `beta_fdtd
388.21946125247325` against `beta_hj_kj_graded 384.74897567707814` (`d_FDTD(2) = 0.902013` pp), and
`W20.json`:148-152 gives `400.2154609833936` against `398.88704687479526` (`d_FDTD(5) = 0.333030` pp). The
EIG side is `[M]` at `n_strip = 2` (`W08.json`:99, `beta_eig 389.7256713378306`, `d_EIG(2) = 1.293492` pp)
but **not** at `n_strip = 5`, where the number used is `d_EIG(5) = 0.873501`: `decisions.md` §151(c) (L9425)
still carries that fifth point as **`[RELAYED]`** — *"[M for 2/3/4; `0.8735` is [RELAYED]]"* — and it is the
same single relayed item that Reading B's leg-3 failure rests on. `W20.json`:148 now holds a banked
`beta_eig 402.37133087951725` (`meta.status` `ok`, `complete` `true`, `abort_reason` `null`), from which
`d_EIG(5)` follows by the same one-line subtraction, and `EIG_strip_width.json`:212 carries the full digit
(`"d_EIG_pp": 0.8735014165089261`) — so the ledger's relay is **stale**, and the mark on the row above says
so rather than pretending otherwise. Retiring that relay is a `decisions.md` edit and **none is claimed
here.** The printed comparison stands as written (`0.148993 <= 0.2202`, PASS); no further arithmetic is
offered.

**Verdict of record: CONFIRMED** on the pre-registered `d_W` column, with the qualifier in Reading B
attached in the same breath. §4.1's precedence line (*"guards first, then the rule"*, L141) is respected:
the guard question was settled before the legs were read, and it was settled by the ruling in §5, not by
looking at the answer.

The declaration at L143-147 stays attached to this verdict: *"`CONFIRMED` is **not** evidence that the
reference is right — it is evidence that a strip-meshing error of order `0.2 pp` or more is present at
`n_strip = 2`"* [L]. That is exactly what is being claimed and nothing more.

### Reading B — the mandatory qualifier (not graded, travels with A)

The EIG companion column fails the *analogue* of leg 3 [M, computed here]:

- EIG leg 1 passes: steps 0.150117 / 0.145715 / 0.124158 pp, each `> 0.0734` [M];
- EIG leg 2 passes: total fall `1.293492 − 0.873501 = 0.419990` pp `> 0.2202` **[derived; one input relayed (†, note above)]**;
- EIG leg 4 passes: it is leg 4, see above;
- **EIG leg 3 fails**: `0.873501 / 1.293492 = 0.675305 > 0.5`; allowed `0.5*1.293492 = 0.646746` pp, and
  `0.873501` pp is still standing at `n_strip = 5` [M];
- `rel_gap` widens monotonically: `0.387979 → 0.438223 → 0.491382 → 0.538677` pp, `+0.150698` pp over the
  sweep [M] — the opposite of what a shared width mechanism predicts.

The EIG legs are **not** part of the pre-registered Q1 rule; §4.1 uses the EIG side only as leg 4's
consistency check [L, L126-129]. The EIG leg-3 failure is therefore a **qualifier on the claim, not a veto
of it**, and must not be reported as a Q1 failure. But a "CONFIRMED" written without this paragraph is a
different claim wearing the same name. The owner's own sentence is the one to carry, verbatim
[L, `decisions.md` §151(c), line 9425]:

> *"strip meshing accounts for half the FDTD residual and a third of the EIG residual; only the FDTD half
> is pre-registered."*

---

## 3. What the two columns together suggest — a HYPOTHESIS, not a measurement

FDTD and EIG both approach HJ+KJ as `W` increases; **FDTD approaches faster**. The gap between them widens
from `0.388` to `0.539` pp across the sweep [M]. Reading: this is what it looks like when two independent
solvers are converging on the same reference from different walls — the reference is *corroborated by two
independent solvers*, and each solver is capped by its own remaining error. EIG's approach is capped by
its own transverse-box error (~`0.72` pp at clearance `3.0`, [L, §151(d), `evidence/box_sweep/`]; the box
was held fixed at `lat 8 / lid 1` throughout, so nothing in this sweep reduced it), and FDTD's by
`h`-discretisation (`h` was pinned at 0.4 mm by design, [L, §11 L288-289]). Two different walls, not a
wrong solver.

**This is a hypothesis and it is not measured here.** Phrased as the falsifiable form the record should
carry: *EIG's box residual is larger than its strip residual at this clearance, so a strip-only sweep
cannot drive EIG to the pre-registered convergence threshold.* Nothing in this dispatch tests it. The
follow-up that would is an EIG box-floor measurement at these strip widths — a separate dispatch.

---

## 4. Q2 — the box lever does not move; the secondary reading does fire

Rule [L, §4.2 L165-166]: `MOVES` iff `|d_wide − d_narrow| > 0.2202` pp, `DOES-NOT-MOVE` otherwise.

- **PRIMARY: DOES NOT MOVE.** `|0.902013 − 0.839252| = 0.062761` pp [M], i.e. `0.285x` the `0.2202` pp
  threshold, `4x` inside it. The box lever is inert at the pinned 4.8 mm absorber. (A brief figure of
  `0.0622` pp is `0.0006` pp from this and is not reproducible from the rows; see `ERRATA_003.md` §(f). It
  changes nothing at this magnitude — `0.0622` is also `DOES-NOT-MOVE`.)
- **SECONDARY: FIRES, reported and not graded.** §4.2 declares: *"Secondary reading, reported but not
  graded: `|d_narrow|` itself, against the `0.2202 pp` threshold. If it also moves, the box lever is live
  *at the pinned absorber* and the `h`-ladder's bridge geometry is questioned — which would be a finding
  about `h_refine`, not about `h`."* [L, L168-170]. It moves: `|d_narrow| = 0.839252` pp `>> 0.2202` pp
  [M]. That is the pre-registered consequence, stated before the run: the `h_refine` bridge geometry is
  questioned by its own arm. It does **not** touch Q1 (which grades `W08`, the wide arm, not `W08n`).
- **The price was wrong on memory, and it is recorded rather than absorbed.** `PREREG.md` priced the
  narrow arm at `53.2 s` and `<= 89.1 MB` by ratio to rung A [L, L159-161]; measured `10.79 s` and
  `162.20703125 MB` [M, `wall_fdtd_s`, `peak_rss_mb`]. Time came in `4.9x` *better*, memory `1.8x`
  *worse* — the priced ceiling was low by `1.8x`. No grading consequence (`162 MB` is `12x` inside the
  `2000 MB` ceiling actually used and `25x` inside the pre-registered `4000 MB`), but a `[L]` ratio price
  that is wrong by `1.8x` on one of its two axes is worth one sentence in the record.
- This is **not** a re-run of `box_sweep`: `npml` is `12` in **both** arms here and `12` never appears in
  the `npml 6` `box_sweep` narrow arm [M, `npml 12` in both JSONs; L, §4.2 L172-176]. Any sentence that
  attributes Q2 to "closing the `npml 6` hole" is wrong about the mechanism; see `ERRATA_003.md` §(f).

---

## 5. G5 — ruled NOT to fire; two deviations recorded instead

`PREREG.md` §10 **G5** [L, L278-279]:

> *"**G5 resources** — `--mem-ceiling-mb 4000`, one arm at a time, cgroup >= `6144 MB` **verified before the
> first launch** (§5). A run started in a smaller cgroup is void, not graded."*

A previous pass read `meta.cgroup_limit_mb: null` on all five arms [M] as an unverified-or-small cgroup
and flipped the verdict to INCONCLUSIVE. **That objection is overruled, and the ruling is named so that it
can be argued with rather than inherited:**

> *"the objection that `cgroup_limit_mb: null` means an unverified or smaller cgroup is overruled: null is
> the tool's no-finite-limit sentinel (`tools/host_ladder.py`:183, 190-191), and an unbounded host
> satisfies the `6144 MB` requirement a fortiori. What remains on the record is a deviation in the
> prescribed flags and the declared container, disclosed here, with no grading consequence."*

The three legs of that ruling, so a reader can check them without trusting the prose:

1. G5 attaches one remedy (*"void"*) to one antecedent (*"a run started in a smaller cgroup"*). `null` is
   not that antecedent. `tools/host_ladder.py` L182-199 `def cgroup_limit_mb()`: docstring L183 *"The
   cgroup memory limit in MB, or None when there is no finite limit"*; L190-191 `if not raw or raw ==
   "max": return None`; L196-197 an implausibility sentinel against `CGROUP_IMPLAUSIBLE_MB = 1e9`
   (L177-179). [L] A 512 MB or a 6144 MB cgroup records *its number* — `evidence/h_refine/h040.json:27`
   records `6144.0` [M].
2. **No code compares the field to `6144`.** The only readers are L1206-1214 (a `WARN` when `cg_mb` is
   not `None` and `cg_mb < mem_ceiling_mb`) and L1348 (store it into `meta`); `emfit/` has no occurrence
   [L]. The field is produced and recorded, never gated on — and that `WARN` **could not fire**, because
   `cg_mb` was `None`.
3. `meta.platform == "Linux-7.0.0-38-generic-x86_64-with-glibc2.39"` on all five arms [M], so
   `/sys/fs/cgroup` was present and `null` is the `"max"` branch, not the unreadable-file fallthrough.

**The two deviations that remain, stated as deviations:**

- **(i) Flag.** `--mem-ceiling-mb 2000` was passed, not the prescribed `4000`; `meta.mem_ceiling_mb ==
  2000.0` on all five [M, e.g. `W08.json:53`]. `2000` is the tool default [L, `host_ladder.py` L1159-1163]
  and the abort it arms (`MemoryCeilingError`, L1024-1028) sat at `4.6x` the largest observed peak
  (`435.33 MB`) [M], so the harm G5 exists to prevent — a silent OOM truncation graded as a row — could
  not occur. Formal non-compliance with G5's first limb; no grading consequence.
- **(ii) Container of record.** `PREREG.md` §12 L310-311 declares *"Container of record for the runs:
  6144 MB cgroup (not the 512 MB container this file was written in — §5)"*. **These are host runs, not
  container runs**: `meta.cwd == "/home/jojo/PycharmProjects/EE"` [M, W08/W08n:36, W12/W16/W20:34] and a
  real `git_rev` (see §6) where the container of record emits `"unavailable: FileNotFoundError: [Errno 2]
  No such file or directory: 'git'"` [M, `evidence/h_refine/h040.json:44`]. This is the substantive
  deviation, and it runs in the **benign** direction: an unbounded host satisfies *"cgroup >= 6144 MB"* a
  fortiori. It is also why the host `git_rev` exists to be disclosed at all.

**What would flip this ruling:** a finite `meta.cgroup_limit_mb` below `6144`, or a `peak_rss_mb` at the
ceiling. Neither is in any arm [M: all five `null`; max peak `435.33 MB`].

G5's non-firing is what makes leg 5 pass. That is the whole of its effect on the verdict.

---

## 6. Provenance disclosures (disclose, fix nothing)

1. **Two `git_rev`s.** `W08`/`W08n` carry `1bfd47d75065928ba403efe8333fbe172905969c` (`git_rev_source`
   `"head-loose"`); `W12`/`W16`/`W20` carry `8b1bab3078f847ea2fe3dbde55c392b57c09dbbd` (`"head-loose"`)
   [M, `meta.git_rev` at :48 and :46 respectively]. The arms therefore span two revisions, and G2's fear —
   *"A mismatch means the instrument moved, and the other three arms are then not on the same instrument"*
   [L, §10 G2, L271-273] — is answered **on evidence, not by assumption**: `W08`'s pair is
   `beta_eig 389.7256713378306` / `beta_fdtd 388.21946125247325`, bit-identical to
   `evidence/h_refine/h040.json:94-95`, relative difference `0.0` on both columns [M]. G2 is satisfied.
   A reader comparing the two revision strings would otherwise conclude the arms ran on different
   instruments; they did not, as far as any measurement in the tree can show.
2. **`n_strip = 2` is bit-identical across the ladder edit.** `evidence/strip_width/EIG_strip_width.json:35`
   (`beta_eig 389.7256713378306`) and `:36` (`residual 3.2771050989170236e-14`) reproduce `W08.json:99,146`
   bit for bit [M], which is the cross-warrant behind `decisions.md` §151(f)'s "disclosed, not fixed"
   claim about the shift ladder.
3. **The run log prints the retired reference.** The console prints `HJ_model = 373.2885`, the retired
   quasi-static value (`beta_quasistatic_retired = 373.2885327644756`, [M, `W08n.json:105`]), not the
   graded reference `beta_hj_kj_graded` (`384.74897567707814 / 390.0472372151286 / 394.7445116131979 /
   398.88704687479526`) [M]. A reader grading from the log alone would grade against the wrong number —
   and `373.2885` would make `d` read `+4.0 pp`, roughly `4x` the graded figure. The print site was not
   changed (§151(f) renamed the field; it did not repoint the console line).
4. **Two schema generations.** `W08`/`W08n` predate the ascending-ladder fields: **no**
   `sigma_used_per_rung`, `sigma_retries`, `sigma_attempts`, `sigma_ladder` (they carry only
   `meta.sigma_mult = 0.76` and `sigma_per_rung = [152780.50791726782]`) [M]. `W12`/`W16`/`W20` carry the
   full trace (`W12.json:183-200`, `W16.json:191-216`, `W20.json:199-232`; `sigma_retries` `[1]/[2]/[3]` at
   `W12:202`, `W16:218`, `W20:234`; `sigma_used_per_rung` 155795.91267879284 / 158811.31744031786 /
   161826.7222018429) [M]. The two `n_strip = 2` arms were **not** retro-fitted and must not be: §151(g)
   points at `sigma_used_per_rung` as the authoritative per-arm value, and that key **does not exist** on
   two of five arms.
5. **`sigma_used_per_rung` is an absolute shift, not a multiplier.** It is `k0²·ER·mult`, e.g.
   `155795.91267879284` = `k0²·4.4·0.775` [M; `sigma_formula_check` in `EIG_strip_width.json`]. Calling it
   a multiplier inflates it by five orders.
6. **A third, minor run-definition difference.** `W08`/`W08n` `argv` include `--max-rungs 1`
   (`W08.json:33`); `W12`/`W16`/`W20` `command_line` do **not** [M]. `--max-rungs` is inert under `--h`
   anyway (`ERRATA_002.md` §1.2, `host_ladder.py` L1216-1218) and `meta.max_rungs` reads `3` on the three
   re-runs against one realised rung each [M], so this is a cosmetic difference in the recorded command,
   not a different run. Disclosed for completeness of the run-definition diff.
7. **A divergence between two committed artefacts on the same quantity.** `rel_gap` at `n_strip = 2` is
   `0.38797902621831604` in `W08.json:145` (the exact `100*(beta_eig/beta_fdtd − 1)`) but
   `0.3914786472678067` in `decisions.md` §151(a) and in `EIG_strip_width.json` — the latter is the
   first-order difference `d_EIG − d_FDTD`, which overstates the exact value by the second-order term
   (`0.0035` pp here, `0.0098` pp at `W08n`). Both forms widen monotonically and neither is anywhere near
   `0.2202` pp, so no conclusion changes; but the two artefacts **do not print the same number for the
   same quantity**, and this file now uses the exact form throughout.

---

## 7. Ladder arithmetic (Task A) — the defect in quantitative form

`meta.sigma_used_per_rung` gives `155795.91267879284` (3), `158811.31744031786` (4), `161826.7222018429`
(5); the increment between consecutive widths is **constant at `3015.4047615`** [M], which is
`0.015 x (152780.5079172678/0.76)`. With `sigma = sigma_mult · k0²·ER` and `sigma(0.76) =
152780.5079172678` [M, §151(g)], the accepted multipliers are

    sigma_mult = 0.76 + 0.015*(n_strip - 2)      exactly, for n_strip = 2,3,4,5
    sigma_retries = n_strip - 2                  ([1],[2],[3] measured)   [M]

**The defect is that the relation is exact and the tool does not encode it.** `SIGMA_MULT = 0.76`
[L, `tools/host_ladder.py` L110] and `SIGMA_LADDER = (SIGMA_MULT, 0.775, 0.79, 0.805, 0.82, 0.85)`
[L, L128] is a fixed six-entry tuple. Consequences, recorded as CLEANUP CANDIDATES, not fixes:

- the last step is **`0.03`** (`0.82 → 0.85`) after four steps of `0.015`, so the ladder cannot be
  described as "`0.015` per retry" in its own terms;
- it is **exhausted at five retries** (largest servable `n_strip` is the one needing `0.805`); an
  `n_strip = 7` arm would need `0.835`, absent from the tuple, and the next entry `0.85` skips it;
  `n_strip = 8` needs `0.850`, which *is* the tuple's last entry but is reachable only by a `0.045`
  jump — three times the ladder's own `0.015` spacing; whether it finds the pairs there is not known
  and is not claimed (`docs/design/d58_13_strip_width_decisions_block.md` §11);
- `W08`/`W08n` carry no ladder fields at all (§6.4).

The **rejected** attempts are banked, not hidden: `W12` rejects 1 (`best_residual 0.95598`), `W16`
rejects 2 (`0.93748`, `0.95238`), `W20` rejects 3 (`0.93278`, `0.96502`, `0.92211` — `W20.json:199-232`),
six in total across the three re-run arms, every one before the accepted residual lands at `~3e-14` [M].
That trace is the evidence that the ascending search is doing what §151(f) says it does and that the
graded rows are the first converged pair, not the only attempt.

---

## 8. How to re-check this file without trusting it

`PREREG.md` §9 A10 [L, L265]: *"every rule in §4/§8 is mechanical over the row keys named in §3, so a
reader can re-apply it to the JSONs in `evidence/strip_width/` without trusting this prose."* The keys are
`rungs[0].beta_fdtd`, `.beta_eig`, `.beta_hj_kj_graded`, `.rel_gap_pct`, `.n_cells`, `.n_strip`,
`.residual`, `.wall_fdtd_s`, `.peak_rss_mb`; the constants are `Delta_min 0.0734`, `3*Delta_min 0.2202`,
`TOL_RESID 1e-8`, `CURL_FLOOR 1e-6`, `ER 4.4` [L, §4, §10]. §8 (L248) states the reporting policy this
file follows: *"Rows are reported even when they would not be graded, so the record shows what was
measured."*

## 9. What this SUMMARY does not claim

- It does not claim the reference is right (§0, §11): a falling `d_W` shows a strip-meshing error is
  present at `n_strip = 2`, not that HJ+KJ is accurate at any `W`.
- It does not claim the box is resolved: Q2 says the *lever* is inert at `npml 12`, while its secondary
  reading says `d_narrow` itself is `0.84` pp — a statement about `W08n`, not about the box error at the
  wide arm, which `decisions.md` §151(d) leaves at ~`0.72` pp and **not separable** from strip meshing.
- It does not claim `n_strip >= 5` suffices [L, §11 L296-297]; the trend is still falling at `n_strip = 5`.
- It does not grade anything from the console. Every number here is from a banked row, and where a number
  is relayed it is marked `[R]` — there are none in the tables above.
- It does not touch `PREREG.md`, any `W*.json`, `decisions.md`, or `ERRATA_002.md`. The stale-status
  correction is carried in `evidence/strip_width/ERRATA_003.md` (append-only), and the decisions text in
  `docs/design/d58_13_strip_width_decisions_block.md` for Agent A to merge.
