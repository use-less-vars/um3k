# D58.13 — decisions block for Agent A to merge (do not append to `decisions.md` directly)

Per `evidence/strip_width/PREREG.md` §12 (L314-315): *"No `decisions.md` write is claimed by this
dispatch; any decisions text goes to `docs/design/<dispatch>_decisions_block.md` for Agent A to merge
(standing rule 2)."* This file is that text. It is **not** merged, and `decisions.md` is **not**
modified by this pass.

Marks: **[M]** measured this pass against an artefact; **[L]** read from a named file and cited there;
**[RELAYED]** an owner assertion with no artefact behind it.

> **EXTENDED — later pass, same dispatch. §1 and §7 below are SUPERSEDED and must not be merged as written.**
> §1's verdict (*INCONCLUSIVE by G5*) was overturned by a ruling recorded in **§8**, and its closing claim that
> *"recording the argument without acting on it is the only move available to a docs pass"* was falsified by
> that same ruling. The live verdict is **§9: CONFIRMED, with a mandatory qualifier**. §7's non-conversion
> bullets are superseded by §9-§13. §2-§6 stand unchanged and their numbers were re-verified for this pass.
> New sections use the same `[M]`/`[L]` discipline as `PREREG.md` and cite artefacts rather than prose.

## 1. Status of §151(a): the missing-arm clause is discharged, and the verdict it converts to is NOT CONFIRMED — **SUPERSEDED by §8-§9; do not merge this verdict**

`decisions.md` §151(a) records Q1 as **INCONCLUSIVE by the missing-arm clause**, and names its own
conversion condition: *"bank the three missing `d_FDTD` values as rows (or re-run the three arms), then
§4.1(1)-(5) is decidable in one pass and the verdict follows without argument."*

**The conversion condition has been met.** `W12.json`, `W16.json`, `W20.json` were re-run and carry a
`beta_fdtd` row each [M: file mtimes `03:31`, `03:32`, `03:33`; §151 was written at `03:23`, i.e. the
arm table in §151(a) was correct when written and is now stale]. All five arms report
`meta.status == 'ok'`, `meta.complete == True`, `meta.abort_reason is None`, one row each, and residuals
`3.28e-14 / 3.70e-14 / 3.13e-14 / 3.30e-14 / 2.98e-14` (W08, W08n, W12, W16, W20) [M]. **G1 is
therefore satisfied and no longer fires.**

**The verdict does not follow as CONFIRMED, because §4.1(5) is not satisfied.** The pre-registered
requirement for CONFIRMED is *"no guard in §10 fired"* [L, `PREREG.md` §4.1(5)], and §4.1's precedence
line is *"**guards first**, then the rule"* [L, L141]. **G5 fires:**

- `PREREG.md` §10 **G5** requires `--mem-ceiling-mb 4000`, one arm at a time, **cgroup >= `6144 MB`
  verified before the first launch**, and adds: *"A run started in a smaller cgroup is **void, not
  graded**."* [L, §10 G5]
- All five arms ran `--mem-ceiling-mb 2000`: `meta.mem_ceiling_mb == 2000.0` on every arm [M].
- The cgroup was **never recorded**: `meta.cgroup_limit_mb is None` on all five arms [M]. The key
  exists in the schema and is unset, so "verified before the first launch" is **unevidenced by the
  artefacts**, and no reading of them can supply it.

> **[DELETED AS A VERDICT — the overturned reading, retained only so that the reversal is auditable.]**
> The earlier pass wrote: *"the verdict of record is therefore INCONCLUSIVE — but by G5's evidence
> requirement, not by a missing arm"*, on the reading that `meta.cgroup_limit_mb is None` means an
> unverified or smaller cgroup. **That reading is overruled (§8), so this verdict is withdrawn rather than
> merely qualified.** The live verdict is §9's **CONFIRMED, with a mandatory qualifier**. What survives from
> the paragraph is one observation only: §4.1's INCONCLUSIVE enumeration does not name G5, which is why the
> G5 question had to be settled by a ruling rather than by the rule's own text.

**This is not a re-negotiation, and the distinction is the whole point.** §150(h)(iv) fixes the
principle: *"a gate that is re-negotiated after seeing the data is not a gate."* G5's failure mode as
written is a ceiling **too high to reach** (*"an arm run at `--mem-ceiling-mb 4000` inside a 512 MB
cgroup would be graded against a ceiling it can never reach"* [L, §5]). The measured `peak_rss_mb` is
`385.36 / 162.21 / 390.25 / 406.21 / 435.33` [M] — a *stricter* self-imposed ceiling of `2000` was used
and was never approached, so the memory pressure G5 exists to prevent **demonstrably did not occur**.
That argument is recorded here **and is explicitly not used to grade the run**, because G5 is a
validity guard whose stated remedy is *"void, not graded"* [L], and a validity guard that is satisfied
in substance but not in evidence does not become a pass on the strength of the substance.
**[SUPERSEDED at this sentence: §8 does act — it rules, with the overruled objection named, and it states
what follows if a reader rejects the ruling.]**

## 2. What the banked rows do establish: legs 1-4 pass on the pre-registered `d_W`

Per arm `d_W = 100*(beta_fdtd/ref(W, f_hz) - 1)`, the reference recomputed at each arm's own tone
[L, §4]. All values below are [M] from the five JSONs:

| arm | `beta_fdtd` | `d_W` pp | `beta_eig` | `d_EIG` pp | `rel_gap` pp |
|---|---|---|---|---|---|
| W08  | 388.21946125247325 | +0.902013 | 389.7256713378306 | +1.293492 | 0.387979 |
| W08n | 387.9779902994508  | +0.839252 | 392.5024902740328 | +2.015214 | — |
| W12  | 392.78566209964987 | +0.702075 | 394.5069378715431 | +1.143375 | 0.438223 |
| W16  | 396.73324115721647 | +0.503802 | 398.68271603684286 | +0.997659 | 0.491382 |
| W20  | 400.2154609833936  | +0.333030 | 402.37133087951725 | +0.873501 | 0.538677 |

- **Leg 1 passes**: steps `0.199938 / 0.198273 / 0.170772` pp, each `> Delta_min = 0.0734` [M].
- **Leg 2 passes**: total fall `0.568983` pp `> 0.2202` pp [M].
- **Leg 3 passes**: `|d_W(5)| / |d_W(2)| = 0.369208 <= 0.5` [M].
- **Leg 4 passes**: the two solvers' total falls differ by `|0.568983 - 0.419990| = 0.148993` pp
  `<= 0.2202` pp [M].

**The three `d_FDTD` values that §151(a) carried as `[RELAYED]` are now `[M]`**, and they reproduce the
relayed figures `0.702 / 0.504 / 0.333` to every printed digit [M]. That is a cross-warrant on the owner
assertion: the relayed numbers were right, and they are now rows rather than assertions.

## 3. §151(c)'s qualifier is unchanged and is now fully measured — EIG leg 3 still fails

§151(c) is the sentence that must travel with any Q1 claim. Its `[RELAYED]` fifth point
(`d_EIG(5) = 0.8735`) is now `[M] = +0.873501` [M], so the qualifier no longer rests on any relay:

- EIG leg 1 passes: `0.150117 / 0.145715 / 0.124158` pp, each `> 0.0734` [M].
- EIG leg 2 passes: `0.419990 > 0.2202` [M].
- EIG leg 4 passes: as above.
- **EIG leg 3 fails**: `|d_EIG(5)| / |d_EIG(2)| = 0.675305 > 0.5` [M]. More than half the eigen residual
  is standing at four times the strip width.
- The divergence is visible without any rule: `rel_gap` walks `0.387979 -> 0.438223 -> 0.491382 ->
  0.538677` pp, monotonically **wider** [M] — the opposite of a shared width mechanism.

Note the EIG legs are **not** part of the pre-registered Q1 rule; §4.1 requires legs 1-4 on `d_W` only,
and uses the EIG side as leg 4's consistency check. The EIG leg-3 failure is therefore a **qualifier on
the claim, not a veto of it**, and it must not be reported as a Q1 failure.

## 4. Q2 is unchanged: the lever does not move, and the number is `0.0628` pp on recomputation

`W08` vs `W08n` differs in one flag only: `--box-lateral-mult 8` against `--box-lateral-mult 1`
[L, `meta.command_line`; `--box-lid-mult 1`, `--pml-mm 4.8`, `--strip-width-mm 0.8`, `--h 0.4`,
`--clearance 3.0` and `npml_per_rung [12]` identical]. So `W08n` **is** §4.2's `W08-N`, the box-lever
arm, and it is not a PML variant.

|0.902013 - 0.839252| = **`0.062761` pp** [M], against `0.2202` pp required [L, §4.2]. **LEVER DOES NOT
MOVE.** §151(e)'s `0.062` pp stands. A brief figure of `0.0622` pp is `0.0006` pp from the recomputation
and is not reproducible from the artefacts; the verdict is unaffected at this magnitude. The `npml 6`
comparator of `0.042` pp remains [L] from `evidence/box_sweep/` and is not recomputed here.

## 5. Ladder arithmetic — the accepted multipliers are an exact function of `n_strip`, which the ladder does not encode

`meta.sigma_used_per_rung` is the absolute shift, not the multiplier [M]. The banked values are
`155795.91267879284` (`n_strip 3`), `158811.31744031786` (4), `161826.7222018429` (5), with constant
increment `3015.4047615` between consecutive widths [M]. Against `sigma(0.76) = 152780.5079172678`
[M, §151(g)] this gives `sigma_mult = 0.76 + 0.015*(n_strip - 2)` **exactly**, i.e. the observed
multipliers are `2 -> 0.76`, `3 -> 0.775`, `4 -> 0.79`, `5 -> 0.805` and `sigma_retries == n_strip - 2`
(`[1]`, `[2]`, `[3]`) [M].

**The defect is that the relation is exact and the tool does not encode it.** `SIGMA_LADDER =
(SIGMA_MULT, 0.775, 0.79, 0.805, 0.82, 0.85)` is a fixed six-entry tuple whose steps are absolute
`0.015` four times and then **`0.03`** (`0.82 -> 0.85`) [L, `tools/host_ladder.py` L128]. Consequences
worth stating plainly:

- It is **exhausted at five retries**, so the largest strip the ladder can serve is the one needing
  `0.805`. A seven-rung arm (`n_strip 8`) would need `0.835`, which the ladder does not contain; its
  next entry is `0.85`, a `0.045` jump that skips the arithmetic entirely.
- The `0.03` final step is **inconsistent** with the `0.015` spacing of the preceding four, so the
  ladder cannot be described as "`0.015` per retry" in its own terms.
- **`W08` and `W08n` predate the ladder schema and carry no `sigma_used_per_rung` at all** [M]. §151(g)
  says the authoritative per-arm value is `sigma_used_per_rung`; for the two `n_strip = 2` arms that
  value **does not exist**, and `meta.sigma_mult == 0.76` is the only record. This is a real gap in
  §151(g)'s rule, not a formatting detail: the rule points at a key that two of five arms omit.

This reinforces §151(f)(g)'s framing — the ladder is a search over *where to put the shift*, not a
threshold, `TOL_RESID / CURL_FLOOR / ER` are untouched — and adds one thing §151(g) does not say: the
per-arm multiplier is not a tuned sequence, it is **`0.76 + 0.015*(n_strip - 2)`**, discovered
empirically here and still not implemented as such.

## 6. Guards other than G5

- **G2 passes** and is now re-measured against `evidence/h_refine/h040.json`: relative difference
  **`0.0`** on **both** `beta_fdtd` and `beta_eig` [M].
- **G3** records `tone_f_actual_ghz = 10.19862621457275` and `tone_detune_pct = 1.888449234462417` on all
  five arms [M]; §6.3 states there is no guard on the detune magnitude, so this is a record and not a
  gate.
- **G4** passes: all `W/H` in `[0.1, 10]`, all `beta` finite and positive [M].
- **G6** passes: `n_cells` `415072 / 416976 / 418880 / 420784` for `W08 / W12 / W16 / W20`, and
  `n_strip` `2 / 3 / 4 / 5` matching the §1 table [M].
- **G7** passes: `b_over_a` and `alpha_fdtd_db_per_mm` inside `[1/3, 3]` of rung A's for every arm [M].

## 7. What this block does not do — **SUPERSEDED by §13**

- It does **not** grade Q1 as CONFIRMED, and it does **not** convert §151(a) in place. §151(a) is left
  standing until Agent A merges this block, because a docs pass that rewrites a live verdict in a
  1.4 MB append-only record is not a docs pass.
- It does **not** repair G5 retroactively. A cgroup cannot be verified after the fact; the only
  conversion is a re-run in a `6144 MB`-class container with `--mem-ceiling-mb 4000` and
  `meta.cgroup_limit_mb` populated before the first launch.
- It does **not** touch `PREREG.md`. Amendments to the freeze belong in
  `evidence/strip_width/ERRATA_00N.md`, append-only.
- It does **not** replay Q1 on the relayed figures. Every number above is from a banked row.

## 8. The G5 ruling — recorded with its three legs, its two deviations, and what would overturn it

`PREREG.md` §10 **G5** [L, L278-279]:

> *"**G5 resources** — `--mem-ceiling-mb 4000`, one arm at a time, cgroup >= `6144 MB` **verified before
> the first launch** (§5). A run started in a smaller cgroup is void, not graded."*

`meta.cgroup_limit_mb is None` on all five arms [M, `W08/W08n:31`, `W12/W16/W20:29`]. §1 read that as an
unverified-or-smaller cgroup and withdrew the verdict. **That reading is overruled.** The ruling is
quoted verbatim here, and in `evidence/strip_width/SUMMARY.md` §5, so that it is a named position a
reader can argue with rather than an inherited one:

> *"the objection that `cgroup_limit_mb: null` means an unverified or smaller cgroup is overruled: null is
> the tool's no-finite-limit sentinel (`tools/host_ladder.py`:183, 190-191), and an unbounded host
> satisfies the `6144 MB` requirement a fortiori. What remains on the record is a deviation in the
> prescribed flags and the declared container, disclosed here, with no grading consequence."*

**The three legs**, so the ruling can be checked without trusting its prose:

1. G5 attaches one remedy (*"void"*) to one antecedent (*"a run started in a smaller cgroup"*). `null` is
   not that antecedent. `tools/host_ladder.py` L182-199 `def cgroup_limit_mb()`: docstring L183 reads
   *"The cgroup memory limit in MB, or None when there is no finite limit"*; L190-191
   `if not raw or raw == "max": return None`; L196-197 an implausibility sentinel against
   `CGROUP_IMPLAUSIBLE_MB = 1e9` (L177-179) [L]. A 512 MB or a 6144 MB cgroup records *its number* —
   `evidence/h_refine/h040.json:27` records `6144.0` [M]. The field is not a proxy for "unknown".
2. **No code compares the field to `6144`.** Its only readers are L1206-1214 (a `WARN` when `cg_mb` is
   not `None` **and** `cg_mb < mem_ceiling_mb`) and L1348 (store it into `meta`); `emfit/` contains no
   occurrence [L]. The field is produced and recorded, never gated on — and that `WARN` could not fire,
   because `cg_mb` was `None`.
3. `meta.platform == "Linux-7.0.0-38-generic-x86_64-with-glibc2.39"` on all five arms [M, `W08.json:60`],
   so `/sys/fs/cgroup` was present and `null` is the `"max"` branch, not the unreadable-file fallthrough.

**The two deviations that remain, stated as deviations:**

- **(i) Flag.** `--mem-ceiling-mb 2000` was passed, not the prescribed `4000`; `meta.mem_ceiling_mb ==
  2000.0` on all five [M, `W08/W08n:53`, `W12/W16/W20:51`]. `2000` is the tool default [L,
  `tools/host_ladder.py` L1159-1163] and the abort it arms (`MemoryCeilingError`, L1024-1028) sat at
  `4.6x` the largest observed peak (`435.33 MB`, `W20.json`) [M], so the harm G5 exists to prevent — a
  silent OOM truncation graded as a row — could not occur. Formal non-compliance with G5's first limb; no
  grading consequence.
- **(ii) Container of record.** §12 L310-311 declares *"Container of record for the runs: 6144 MB cgroup
  (not the 512 MB container this file was written in -- §5)"*. **These are host runs, not container
  runs**: `meta.cwd == "/home/jojo/PycharmProjects/EE"` [M, `W08/W08n:36`, `W12/W16/W20:34`] and a real
  `git_rev` (§6) where the container of record emits `"unavailable: FileNotFoundError: [Errno 2] No such
  file or directory: 'git'"` [M, `evidence/h_refine/h040.json:44`]. This is the substantive deviation and
  it runs in the **benign** direction: an unbounded host satisfies *"cgroup >= 6144 MB"* a fortiori. It is
  also the reason a host `git_rev` exists to be disclosed at all.

**The alternative reading, stated so it can be argued with.** A reader who rejects leg 1 — who holds that
`null` in `meta` is an absence of evidence rather than evidence of no limit — reverts this block to §1's
withdrawn verdict: **INCONCLUSIVE by G5's evidence requirement**, not by a missing arm. Nothing else
moves. Legs 1-4 of §2 are computed from `beta_fdtd`, which is unaffected by which container produced it;
§3-§6 stand whole. The ruling changes **exactly one cell** of the table in §9 (leg 5), and therefore
exactly one word of the verdict. That is the whole of its authority.

**Why this is a ruling and not a re-negotiation.** §150(h)(iv) fixes the principle [L, line 9414]:
*"It is withheld because the gate was frozen before the runs and a gate that is re-negotiated after
seeing the data is not a gate."* A re-negotiation would move G5's threshold, or its remedy, or its
antecedent, after seeing that the arms pass. This ruling does none of those: G5's text, threshold and
remedy are byte-identical before and after, and what is decided is whether the *recorded sentinel* is the
antecedent G5 names. It is written into this block rather than argued in chat so that it can be contested
against the code (L182-199, L1206-1214, L1348) and not against the prose.

## 9. The verdict of record — CONFIRMED, with the qualifier in the same breath

`PREREG.md` §4.1 requires all of (1)-(5) on the **FDTD** column [L, L120-130]. Measured [M]:

| leg | requirement [L] | measured | verdict |
|---|---|---|---|
| 1 | each of the three steps falls by more than `Delta_min = 0.0734` pp | `0.199938 / 0.198273 / 0.170772` pp | **PASS** |
| 2 | total fall `> 3*Delta_min = 0.2202` pp | `0.902013 − 0.333030 = 0.568983` pp | **PASS** |
| 3 | `\|d_W(5)\| <= 0.5*\|d_W(2)\|` | `0.333030 / 0.902013 = 0.369208` | **PASS** |
| 4 | the two solvers' total falls differ by `<= 0.2202` pp | `\|0.568983 − 0.419990\| = 0.148993` pp | **PASS** |
| 5 | *"no guard in §10 fired"* [L, L130] | G1-G4, G6, G7 pass; **G5 ruled not to fire (§8)** | **PASS** |

§4.1's precedence line — *"**guards first**, then the rule"* [L, L141] — is respected: the guard question
was settled before the legs were read, and it was settled by §8's ruling on the code, not by looking at
the answer.

**Merge-ready sentence.** Agent A may paste this as the `## 151.` conversion, and it is written to be
self-contained so that no reader has to reach this block to understand it:

> **`§151(a)` is discharged and Q1 is CONFIRMED on the pre-registered `d_W` column** — legs 1-4 pass at
> `0.199938 / 0.198273 / 0.170772` pp, total fall `0.568983` pp against the `0.2202` pp floor, and
> `|d_W(5)|/|d_W(2)| = 0.333030/0.902013 = 0.369208 <= 0.5` — **with G5 ruled not to fire** on
> `meta.cgroup_limit_mb is None` (the tool's no-finite-limit sentinel, `tools/host_ladder.py` L182-199;
> `evidence/strip_width/ERRATA_003.md` §(d)), **and with `§151(c)`'s qualifier unchanged and now fully
> measured**: strip meshing accounts for half the FDTD residual and a third of the EIG residual; only the
> FDTD half is pre-registered.

**The qualifier that must travel with that sentence, or the word "CONFIRMED" is a different claim.** The
EIG companion column fails the *analogue* of leg 3 [M]: steps `0.150117 / 0.145715 / 0.124158` pp (each
`> 0.0734`), total fall `1.293492 − 0.873501 = 0.419990` pp, and `0.873501 / 1.293492 = 0.675305`
against an allowed `0.646746` — more than half the eigen residual is still standing at four times the
strip width. `rel_gap` widens monotonically, `0.387979 → 0.438223 → 0.491382 → 0.538677` pp
(`+0.150698` pp) [M], which is the opposite of a shared width mechanism. The EIG legs are **not** part of
the pre-registered Q1 rule (§4.1 uses the EIG side only as leg 4's consistency check), so this is a
**qualifier on the claim, not a veto of it** — and it must not be reported as a Q1 failure.

**The declaration at L143-147 stays attached** [L]: *"`CONFIRMED` is **not** evidence that the reference
is right — it is evidence that a strip-meshing error of order `0.2 pp` or more is present at
`n_strip = 2`."* That is exactly what is being claimed and nothing more.

## 10. Eight facts the artefacts carry, and four statements that arrived wrong

**Eight facts**, each re-measured this pass from the five `evidence/strip_width/W*.json` rows:

1. **All five arms are banked and G1 is satisfied.** `meta.status == 'ok'`, `meta.complete == True`,
   `meta.abort_reason is None`, one row each, residuals `3.28e-14 / 3.70e-14 / 3.13e-14 / 3.30e-14 /
   2.98e-14` [M].
2. **Q1 legs 1-4 pass on `d_W`** at the numbers in §9 [M].
3. **`rel_gap` widens at every step**, `0.387979 / 0.438223 / 0.491382 / 0.538677` pp, `+0.050244 /
   +0.053159 / +0.047296`, total `+0.150698` pp [M]. Three positive differences of the same order are not
   a coincidence of one row.
4. **The EIG leg-3 analogue fails** at `0.675305` versus `0.646746` allowed [M] — §3, §9.
5. **G2 reproduces exactly**: relative difference `0.0` on **both** `beta_fdtd` and `beta_eig` against
   `evidence/h_refine/h040.json:94-95` [M].
6. **The accepted multiplier is a closed-form function of `n_strip`**, `0.76 + 0.015*(n_strip − 2)`, with
   `sigma_retries == n_strip − 2` (`[1] / [2] / [3]` on `W12 / W16 / W20`) and constant increment
   `3015.4047615` between adjacent `sigma_used_per_rung` [M] — §11.
7. **Memory was never near either ceiling**: peaks `385.36 / 162.21 / 390.25 / 406.21 / 435.33` MB [M],
   at most `0.218x` the `2000 MB` ceiling actually armed and `0.109x` the prescribed `4000 MB`.
   `W08n ≈ 162 MB` also makes the narrow `lat 1` box the *cheapest* arm, which is what §4.2 predicted.
8. **The graded rows sit on two git revisions**: `1bfd47d75065928ba403efe8333fbe172905969c`
   (`W08`, `W08n`) and `8b1bab3078f847ea2fe3dbde55c392b57c09dbbd` (`W12`, `W16`, `W20`) [M, `:48` and
   `:46`]. No single revision produced all five rows, and no assertion in this block treats them as one
   instrument build without saying so.

**Four statements that arrived wrong.** Each was checked against an artefact, each is corrected there,
and none changes a verdict:

1. **"Q2 is `0.0622` pp."** Recomputation gives `|0.902013 − 0.839252| = 0.062761` pp [M]. `0.0622` is
   `0.0006` pp from a value the rows do reproduce and is not itself reproducible. **LEVER DOES NOT
   MOVE** either way — the threshold is `0.2202` pp and the measured move is `0.285x` of it.
   → `ERRATA_003.md` §(f).
2. **"`W08n` is the `npml 6` PML comparator."** It is not. `meta.command_line` differs from `W08` in one
   flag only — `--box-lateral-mult 1` against `8` — and `npml_per_rung [12]` is identical on both [M].
   The `0.042` pp comparator (§4) is a *different* arm from `evidence/box_sweep/`, `npml 6` on the narrow
   box. → `ERRATA_003.md` §(f).
3. **"`rel_gap` runs `0.391479 → 0.441375 → 0.493659 → ≈0.540` pp."** Those are the first-order figures
   of `decisions.md` §151(c) [L, line 9425]; the row key `rel_gap_pct` runs
   `0.387979 → 0.438223 → 0.491382 → 0.538677` [M]. They are two different quantities printed under one
   name, `0.0034996` pp apart at every point. The monotone widening — the only thing either figure is
   used for — is identical. → `ERRATA_003.md` §(g).
4. **"An `n_strip = 8` arm would need `0.835`."** It needs `0.850`; `0.835` is the `n_strip = 7` value,
   and it is precisely the entry the ladder does not contain. The error is one row of the arithmetic, not
   of the conclusion (the ladder is exhausted either way) — §11, and `SUMMARY.md` §7 carries the same
   off-by-one and should be read with this correction attached.

## 11. Ladder arithmetic — the ladder agrees with the closed form twice, is silent once, and skips once

`meta.sigma_used_per_rung` is the **absolute** shift, not the multiplier [M]. Against
`sigma(0.76) = 152780.5079172678` [M, §151(g)] the banked values are `155795.91267879284` (`W12`),
`158811.31744031786` (`W16`), `161826.7222018429` (`W20`), with a constant increment of
`3015.4047615 = 0.015 * 152780.5079172678 / 0.76` [M]. So the accepted multiplier is exactly

> `sigma_mult(n_strip) = 0.76 + 0.015 * (n_strip − 2)`, and `sigma_retries = n_strip − 2`.

`SIGMA_LADDER = (SIGMA_MULT, 0.775, 0.79, 0.805, 0.82, 0.85)` [L, `tools/host_ladder.py` L128] is a
fixed six-entry tuple. Laying the two against each other:

| `n_strip` | required `sigma_mult` | in `SIGMA_LADDER`? | banked |
|---|---|---|---|
| 2 | `0.760` | yes — as `SIGMA_MULT` (L110), the ladder's own first entry | `W08`, `W08n` — but see below |
| 3 | `0.775` | yes, entry 2 | `W12` (`0.775`, `sigma_retries [1]`) |
| 4 | `0.790` | yes, entry 3 | `W16` (`0.79`, `[2]`) |
| 5 | `0.805` | yes, entry 4 | `W20` (`0.805`, `[3]`) |
| 6 | `0.820` | yes, entry 5 | not run |
| 7 | `0.835` | **no — absent** | not run |
| 8 | `0.850` | yes, entry 6 — but `+0.045` above `0.805`, so the ladder reaches it only by stepping over `0.835` | not run |

Read off the table:

- **The ladder is correct where it was exercised and wrong where it was not.** At `n_strip = 3/4/5` the
  tuple entry *is* the closed-form value, which is why the sweep converged. At `n_strip = 7` the required
  `0.835` is missing entirely, and at `n_strip = 8` the ladder can only try `0.85`, a jump of `0.045` —
  three times its own `0.015` spacing. Whether `0.85` also finds the pairs at `n_strip = 8` is **not
  known** and is not claimed here; no arm at that width exists.
- **It is exhausted at five retries**, so the largest width the ladder can reach by construction is
  `n_strip = 6` (`0.82`). Any future sweep past `n_strip = 6` needs the tuple extended **from the closed
  form**, not from a continuation of its own spacing.
- **The final `0.03` step is inconsistent** with the `0.015` spacing of the four steps before it, so the
  ladder cannot be described in its own terms as "`0.015` per retry" — the description is only true of
  the part that was measured.
- **`W08` and `W08n` carry no `sigma_used_per_rung` at all** [M] (`meta.npml is None`, `npml_per_rung
  [12]` present, `sigma_mult 0.76` the only record). §151(g) points at a key that two of five arms omit,
  which is a real gap in the rule rather than a formatting detail — see §5.

`TOL_RESID = 1e-8`, `CURL_FLOOR = 1e-6` and `ER` are untouched by all of this [L, L130-131, L108]: the
ladder is a search over *where to put the shift*, not a threshold, and no acceptance bar moved.

## 12. Frozen-clause judgement — YES, a frozen clause is touched, and the remedy is the erratum that already exists

The question this pass had to answer for itself, since the brief did not: **does this work touch a frozen
clause?** Judgement: **yes**, in effect though not in text, and the remedy is an append-only erratum —
which is the only later edit §12 permits.

- **Which clause.** `PREREG.md` §12's closing sentence [L, L310-312]: *"Container of record for the runs:
  6144 MB cgroup (not the 512 MB container this file was written in -- §5). A future edit to any of the
  three files above voids the freeze and requires an append-only erratum, not a silent re-run."* §10 G5
  names the same requirement in guard form.
- **How it is touched, and how it is not.** `PREREG.md`'s bytes are **unchanged**: sha256
  `7a18473b2d65b76a1ff35fd83dde4a0e6622cd75de1a38683f2eeb80d3eea120`, 315 lines / 23 921 B [M]. Nothing
  in this pass edited it. What changed is what a *reader of the frozen text* will conclude: G5 applied
  without §8 gives INCONCLUSIVE, G5 applied with §8 gives CONFIRMED, and the difference is a ruling on
  the antecedent rather than an edit to the sentence. That divergence — not any edit — is what engages
  §12's remedy sentence.
- **The remedy, named.** `evidence/strip_width/ERRATA_003.md` §(d) records the flag and container
  deviations in a three-row table with the JSON line numbers, and points at §8's ruling; §(b) records the
  related and separate fact that the **tool hash in §12's freeze table is now stale** —
  `tools/host_ladder.py` was frozen at `1cd1a3ee…` (1106 lines) and stands at `0d7191973fe7…` (1395
  lines) after the authorised `cleanups-cd` metadata-only edits, which voids §12's hash chain by its own
  words and is why §(b) exists. `tools/d585_modal.py` (`8ba8e2a8…d53a6`) and `emfit/studies.py`
  (`578650bc…e802ac`) still match their frozen pins exactly [M].
- **Consequence for a merge.** No reader may treat `PREREG.md` §10 G5 as self-sufficient from here on:
  the frozen text plus §8 plus `ERRATA_003` §(d) is the admissible reading, and a citation of G5 without
  the erratum reproduces the withdrawn verdict in §1.

## 13. What this block does not do — supersedes §7

- It does **not** grade Q1 as CONFIRMED **without §9's qualifier**. A "CONFIRMED" sentence lifted out of
  this block without the EIG leg-3 failure and the monotone `rel_gap` widening is a different claim
  wearing the same name.
- It does **not** repair G5 retroactively. A cgroup cannot be verified after the fact, which is exactly
  why §8 is a ruling on the antecedent and not a reconstruction of the evidence. The only conversion to
  evidence is a re-run in a `6144 MB`-class container with `--mem-ceiling-mb 4000` and
  `meta.cgroup_limit_mb` populated **before** the first launch.
- It does **not** re-run, re-grade or re-derive anything. Every number here is read from a banked row or
  a named source line; no arm was executed by this pass.
- It does **not** touch `PREREG.md`, `tools/host_ladder.py`, `tools/d585_modal.py` or
  `emfit/studies.py`. Amendments to the freeze belong in `evidence/strip_width/ERRATA_00N.md`,
  append-only (§12).
- It does **not** rewrite `decisions.md` §151 in place. §151(a) stands until Agent A merges §9's
  sentence (standing rule 2; §12's L314-315). A docs pass that replaces a live verdict inside a 1.4 MB
  append-only record is not a docs pass.
- It does **not** convert the EIG leg-3 failure into a Q1 failure, and does not use the EIG column to
  veto a pre-registered `d_W` verdict. The EIG failure is a qualifier and is reported as one (§3, §9).
- It does **not** establish that `n_strip >= 5` is sufficient, that the trend has flattened, that `h` is
  separable from `W`, or anything about HJ+KJ's own accuracy at any width. §11's `n_strip = 6/7/8` rows
  are arithmetic, not predictions.
- It does **not** authorise rung C, and the instruction carried forward from the previous pass is
  preserved verbatim: **§150(h)(iv) — “do not quote as ‘C was affordable’”** (affordable ≠ authorised;
  the gate is a pre-registered budget). `decisions.md` §150(h)(iv) [L, line 9414] withholds it — *"It is
  withheld because the gate was frozen before the runs and a gate that is re-negotiated after seeing the
  data is not a gate"*. "Affordable" is this dispatch log's own word for a rung that was priced and then
  *refused*, not a licence: the frozen clause is the authorisation, and it says no. Nothing in this block
  changes that, and no part of it may be read as a re-opening.
- It does **not** claim the relayed figures were wrong. `§151(a)`'s three `d_FDTD` values were
  `[RELAYED]` and reproduced to every printed digit once banked (§2). What was missing was a row, not a
  number.

