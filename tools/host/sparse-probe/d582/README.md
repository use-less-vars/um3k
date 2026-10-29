# d582 — interface-jump ladder probes (D58.2)

Promoted from `.scratch/d582/` on 2026-10-29 so that the numbers in
`docs/design/d58_extraction_acceptance.md` §10.7–§10.8 have surviving code. The
`.scratch/` copies are retained.

| script | produces | section |
| --- | --- | --- |
| `t1_probe.py` | `t1_probe_out.json` | §10.7.2 (first reproduction of the 13.85 % deficit) |
| `t1_allrungs.py` | `t1_allrungs.json` | §10.7.3–§10.7.6, §10.8.1 (ladder, element straddle, metadata) |
| `t1_final.py` | `t1_final.json` | §10.7.4, §10.7.7–§10.7.9, §10.8.2 (exponents, quartiles, J2, in-strip) |
| `build_analytic_control.py` | `analytic_control.npz` | §10.8.3, §10.9.4 (the exact-field control) |

Outputs are written to `.scratch/d582/` and are not tracked.

## Two rules that apply to every script here

1. **Rung-0 gate.** Before any ratio is quoted, the reconstruction must reproduce
   J1 = 3.7903993750636298 to an absolute difference below 1e-12. It currently
   achieves 8.9e-16. A run that does not pass this gate has not measured anything.
2. **Never load rung 4.** Its archive is 9604 × 9604 (~738 MB) and adds nothing:
   R at rung 4 is 3.575412753195199 in `evidence/t4/rung4_dense_anchor.json`, and
   that record is the authority.

## What these scripts are not

They do not solve anything. Every number in §10.7–§10.8 comes from the field
already banked in the rung archives. No new solves, no `emfit/` changes.
