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
