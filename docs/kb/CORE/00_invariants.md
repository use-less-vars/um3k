---
status: current
layer: core
pinned_commit: 36c71d3eaaecf9ee04857dac2d68b04ba5ab97ef
pinned_at: 2026-11-18
byte_budget: 2560
last_verified: 2026-11-18
reads_when: every session, before any code and before any other kb file - this is the whole invariant set
supersedes: null
superseded_by: null
core_handoff_id: gen13->gen14
---
# emfit L0 invariants: do not re-derive these.
## Physics
1 Z0*sqrt(eps_eff) is invariant to eps_r, NOT to lateral box. Analytic 89.03, measured 93.39 ohm (+4.9%). Cross-check only; never use it to rule out truncation.
2 Truncation vs probe, same geometry: wave-extracted Z0 == static-solve Z0 means lateral truncation; disagreement means the V/I probe (ground-return current over lateral PML columns). A wider box is NOT a diagnostic (394,824 edges).
3 Never sweep vertical again: top walls flat to 0.01 ohm. Lateral half-width, dx=0.4mm: 3.0h 51.4886, 4.5h 50.2670, 6.0h 49.6218, 7.5h 49.2420, 9.0h 49.0101 ohm.
4 5% vs Hammerstad-Jensen at a stated box is the TEST. 2% is a report claim only and must quote its fit residual and the 3.0h-9.0h range. A test that cannot pass on the affordable box is a bad test.
## Stored literals - DATA, never identifiers
5 VIS_SCHEMA emfit.vis/2, legacy emfit.wavedude/1 and /2. STATE_SCHEMA_VIS emfit.poc-state/3; /1 is byte-frozen. VIS_FORMAT um3k or wavedude. Renaming one corrupts stored states.
6 pytest 9.2.0 aborts collection on tests/test_abc.py: stray compiled emfit_core shadows the reference and emfit/evolve.py:260 raises. Always --ignore=tests/test_abc.py.
## Epistemics
7 No path:line, no claim. When prose and line disagree, the line wins.
8 Silent failure is the default mode: nothing throws, it draws something plausible. A passing test may only prove no exception.
9 Keep four states apart: VERIFIED-BY-RUN, FIXED-TESTED, closed, measured. Read lines from git show HASH:path, never the working tree.
10 git status the path before you write it. An untracked file is a delete waiting for a helpful person (DR-44).
11 Claims of absence are the cheapest to make and the costliest to act on. Three ghosts refuted.
12 DR-47: no @state.change listener runs in the suite. A green suite says nothing about the UI; any claim resting on a listener test is unverified.
