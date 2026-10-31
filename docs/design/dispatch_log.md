# Dispatch log

One line per dispatch in flight. Written by whoever issues the dispatch and read by every agent
before starting work. This file exists because Dispatch 58 was issued with a write scope that
contradicted R5 of Dispatch 57b in the same message: both agents obeyed their own brief, and the
conflict was caught only at commit time. A dispatch that is not on this list is not authorised.

| dispatch | scope of writes | status |
|---|---|---|
| 57 | `evidence/t4/**`, `docs/design/order_p_preregistration.md` | CLOSED — task 1 `f92d36b`, task 2 `92d9ad5`; task 3 folded into 57b |
| 57b | `docs/design/d57b_acceptance.md`, `tests/**`, `emfit/mode2d.py`, `decisions.md` (Agent A only) | SUPERSEDED by 57c — landed T0 only |
| 57c | as 57b, plus `docs/design/dispatch_log.md` | OPEN — T0 landed; T3a baseline next; T3b CANCELLED and replaced by the `Q` diagnosis |
| 58 | `docs/design/component_map.md`, `docs/design/d58_acceptance.md`, `decisions.md` (scope as issued) | CLOSED — `9cece7b`, ratified |
| 59V | visualisation acceptance doc and `viz/**` (scope as issued) | CLOSED — `39b0657`, `1cbe2fc`, authorised retroactively |
| box-sweep-2026-10-31 *(dated slug in place of a dispatch number — none is verifiable in this tree)* | `evidence/box_sweep/**` (7 JSONs + `SUMMARY.md`), `docs/design/box_sweep_preregistration.md`, one row in this file | CLOSED — six preregistered box-sweep arms at h = 0.4 mm run post-freeze, all guards G1–G5 pass, frozen verdict **INCONCLUSIVE** (`evidence/box_sweep/SUMMARY.md` §5); §148(h) left open; no `decisions.md` write claimed |
| h-refine-2026-10-31 *(dated slug — no dispatch number verifiable in this tree)* | `evidence/h_refine/**` (PREREG, SUMMARY, `analyse.py`, `h040.json/.log`, `h0267.json/.log`), one row in this file, and the `## 150.` block in `decisions.md` (append-only, on this dispatch's authorisation) | CLOSED — frozen `h` refinement at `lat 8 / lid 1`, two rungs (`h 0.4` and `0.26667`) run with per-run HJ+KJ re-derivation (pin `384.7489672644` passes at `2.2e-8`); rung `h 0.2` **priced and refused** on the pre-registered 900 s sizing gate (`3.27 M` cells / `1163` s / `2195` MB); frozen verdict **INCONCLUSIVE** (`evidence/h_refine/SUMMARY.md` §4, third clause); post-hoc fall `0.35166` pp FDTD / `0.35890` pp EIG = `1.6 x` the `3*Delta_min` threshold with an h-invariant gap (`0.38798 → 0.38213 %`); order NOT determined, rung C affordable but withheld pending errata authorisation |
| strip-width-and-errata-freeze-2026-10-31 *(dated slug \u2014 no dispatch number verifiable in this tree)* | `evidence/strip_width/PREREG.md`, `evidence/rung_c_errata/PREREG.md`, one row in this file | FROZEN \u2014 two pre-registrations written and frozen before any run; **no FDTD run performed, no row graded, nothing extrapolated**. (i) `evidence/strip_width/`: Q1 fixed-`h` strip-meshing sweep (`W = 0.8 / 1.2 / 1.6 / 2.0 mm` \u2192 `n_strip = 2/3/4/5` exactly, at `cell = 0.400 mm`, graded `d_W` vs `W/cell` against a per-arm HJ+KJ reference, floor `3*Delta_min = 0.2202` pp carried unchanged with its circularity disclosed) and Q2 unit-vs-`8x` lateral box at the **pinned** 4.8 mm absorber (`npml 12`: one new arm priced `95 200` cells / `53 s` [L], the `8x` arm being `h_refine` rung A, `415 072` cells / `232.0 s` / `388.4 MB` [M]); per-arm gate `900 s` / `4000 MB`, `Delta_min` provenance and the `0.0108` pp tighter estimate all recorded. (ii) `evidence/rung_c_errata/`: a **resource-budget-only** erratum to `h_refine` PREREG \u00a75 \u2014 `wall_fdtd_s > 900` \u2192 `> 1400` by the rule "next 100 s at or above 1.20x the projection", `peak_rss_mb > 4000` unchanged, every \u00a74 verdict clause / `Delta_min` / reference tolerance byte-identical, trip clause and "never extrapolated" re-pinned, one-shot run authorised; the naive `h^-4` pricing (`1882 s`) **still trips** and that is declared rather than papered over. **Provenance correction:** `163.65 s` is the six-config `box_sweep` total (`10.82+17.65+31.31+58.64+16.72+28.52`), never a rung-C price \u2014 the linear-in-cells model costed `6.9 M` **cells** and would also have refused C (`2880 s`), so the erratum is argued as a budget amendment, not a model correction. **Withheld, out of the issued fence:** the two `tools/host_ladder.py` edits the brief's tasks C (`beta_model` provenance at source 740/589) and D (`git_rev()` at source 184/1014) actually require \u2014 the fence names `emfit/` and `tools/d585_modal.py` only \u2014 so neither task was attempted; a minimal patch is proposed unapplied for authorisation |


## Standing rules

1. **Path ownership beats convenience.** Check this table before writing. If the path is not in
your row, stop and report. Never commit and explain afterwards.
2. **`decisions.md` is single-writer: Agent A.** Any other agent's decisions text goes to
`docs/design/<dispatch>_decisions_block.md` for Agent A to merge. Dispatch 58 predates this rule;
its committed block is ratified. The rule binds from 57c onward.
3. **Only Agent A commits.** Workers propose; Agent A stages, inspects and commits.
4. **A retired ruling is recorded with both halves.** The entry states that the ruling was false
*and* what the replacement does or does not establish. Retiring "no sparse route exists at any
resolution" is recorded together with the measured fact that Route C fails its own quality gate at
every rung including rung 0 — so that no future reader infers the replacement is validated.
