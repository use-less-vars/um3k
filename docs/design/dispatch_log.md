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
