# S3 - Staleness of status claims (KB audit chunk 2)

Scope: the 27 files in `docs/` that carry a status header, plus the code tree as the ground truth
for claims of the form "nothing is implemented". Read-only audit; nothing was fixed, staged or
committed.

## Contents

| path | line | sev | one-line summary |
|---|---|---|---|
| docs/design/E11_residual_preregistration.md | 3 | A | "no results yet" while the same file publishes 6.52 % since 2026-11-10 |
| docs/design/s11_phase_investigation_2026-11-04.md | 4, 101 | A | "DR-24..DR-29 reserved, not yet in the register" - all six are in the register |
| docs/design/roadmap-next-2026-11-08.md | 5-6 | A | "no Touchstone writer ... no C++ source" - both exist |
| docs/design/strip_termination_design_2026-11-02.md | 4 | A | "proposal, not applied" - applied, exercised and reverted the next day |
| docs/design/session_close_gen10.md | 4 | A | "physics-debug phase is closed" vs GEN12_HANDOFF 48/251 "E11 is open" |
| docs/design/e13_antenna_scope.md | 3 | B | "No implementation exists" - emfit/ntff.py, emfit/antenna.py, tests/test_antenna.py |
| docs/design/onboarding/00_README.md | 138 | B | design/ is 160 files / 5,702,497 B - actually 165 / 5,780,607 B |
| docs/design/defect_register.md | 891 | B | DR-45 names two live violators; no file in docs/ now violates DR-45 |
| 28 files | - | C | an in-content date later than the file's own mtime |
| 48 files | - | C | SUPERSEDED/STALE tokens used as nouns; only 7 lines are status banners |

## Severity A - misleads into a wrong action

### A-1 docs/design/E11_residual_preregistration.md:3
Claim: `**Status:** PREREGISTERED (no results yet). Closes when exit criteria met.`
True: the file's own 2026-11-10 amendment at :11-:15 publishes the result - 6.52 % (fine mesh,
two-wave), raw -6.517281 % against `Gamma_anchor`; :45-:46 gives 6.52 / 6.42; :686 records
`-4.904143 -> -6.517281`. `dispatch_log.md:68` has the retarget entry
(residual-retarget-2026-11-10) and `GEN12_HANDOFF.md:48` says "E11 is open. Target after the
2026-11-10 amendment: 6.52 % (fine mesh, two-wave) / 6.42 % (one-wave); the coarse 4.90 % is
superseded." The phrase "no results yet" occurs only at :3.
Status header: yes (self-contradicted). Marker: none.
Why A: a reader takes E11 as an unrun pre-registration, re-runs it, or files it as open with no
result - when the number it exists to produce is already published two lines below the header.

### A-2 docs/design/s11_phase_investigation_2026-11-04.md:4 and :101
Claim: `DR-24..DR-29 reserved, not yet in the register.`
True: all six are in `docs/design/defect_register.md` - DR-24 :406, DR-25 :422, DR-26 :438,
DR-27 :454, DR-28 :478, DR-29 :494 (register mtime 2026-11-13, i.e. nine days later).
Status header: yes; marker: none (no SUPERSEDED, no STALE).
Why A: the six defects read as unlogged, and the free block invites a second allocation of
DR-24..DR-29 - the register's identity, not just its prose, then depends on a reader noticing.

### A-3 docs/design/roadmap-next-2026-11-08.md:5-6
Claim: `Design only. Nothing described here is implemented: there is no Touchstone writer, no
export command in emfit/cli.py, no run manifest, no C++ source.`
True, clause by clause:
- "no Touchstone writer" - FALSE. `emfit/ports.py:1801 def write_touchstone(handle, freqs, s, *,
  z0=50.0, fmt="ri")` and `:1859 def read_touchstone(handle)`.
- "no C++ source" - FALSE. `src/emfit_core.cpp` (7,406 B, 2026-11-13) "C++ twin of the Python
  reference emfit.evolve.step_explicit()", `src/emfit_core.h` (3,399 B), `src/bindings.cpp`
  (16,693 B); its own header records bit-for-bit parity with the Python kernel on the lossless,
  source-free path (tests/test_cpp_parity.py, 13/13, max|diff| 0.0).
- "Nothing described here is implemented" - FALSE in part: `emfit/spice.py` (66,405 B,
  2026-11-12) is an MNA circuit solver plus FDTD/circuit port coupling (Branch, Diode,
  TransmissionLine, CircuitNetwork, SpiceState), which is the SPICE-facing side of section 2 and
  the whole of section 6's premise; `emfit/quasistatic.py` (14,451 B) is the DC fill-in that
  section 2 lists as its option 3.
- "no export command in emfit/cli.py" - holds: no `export` and no `spice` token in
  `emfit/cli.py` (29,967 B).
Status header: yes (`## Status`, :3). Marker: none.
Why A: the roadmap's own reading instructions say every section below is unstarted. C++ port
(section 3), co-simulation hooks (section 1), Touchstone export (section 2) and Volume
Parts/SPICE (section 6) are all presented as future work in whole or in part while code for them
is on disk. This is the largest single source of duplicated work in the KB.

### A-4 docs/design/strip_termination_design_2026-11-02.md:4
Claim: `**Status:** proposal, not applied. No source edited, no solve run.`
True: `docs/design/strip_termination_refuted_2026-11-03.md:3` - "negative result. The D1 change was
applied, exercised and reverted before commit"; `strip_termination_worker_report_2026-11-03.md:11`
- "applied +13/-4 over 3 hunks, then reverted to sha256 254076bc...1648f (net 0)", `emfit/studies.py`
byte-identical, 0 occurrences of `nx_clean`.
Status header: yes; marker: none; and the design doc does not cite either 2026-11-03 file.
Why A: the proposal was tried and refuted one day after this header was written. The header
invites a second implementation of a change already measured to fail.

### A-5 docs/design/session_close_gen10.md:4 vs docs/design/GEN12_HANDOFF.md:48, :251
Claim: `Date: 2026-11-13` / `Status: validation complete - the independent referee agrees with the
in-house extraction to 0.49 percent; the physics-debug phase is closed.`
Contradicted in the same window: `GEN12_HANDOFF.md:48` "E11 is open. Target after the 2026-11-10
amendment: 6.52 % ... the coarse 4.90 % is superseded", and `:251` lists as open item 4 "The
6.52 % E11 residual partition. Resolve: H1 routing with the operator".
Status header: yes (both files). This is a contradiction between two live documents, not a stale
sentence in a superseded one; neither carries a marker pointing at the other.
Why A: a reader planning work from the session close believes the physics-debug phase is finished
and the residual account is settled, while the handoff written in the same days says the largest
residual (6.52 %) is an unresolved partition.

## Severity B - misleads into confusion

### B-1 docs/design/e13_antenna_scope.md:3
Claim: `Status: scope only. No implementation exists, no code is proposed here, and nothing in this
document has been measured.`
True now: `emfit/ntff.py` (54,646 B) provides `load_surface_dump` / `plane_cut`; `emfit/antenna.py`
(9,510 B, 2026-11-14) renders E/H plane cuts; `tests/test_antenna.py` is "Presentation tests for
emfit.antenna" and grades peak directivity against physics (10*log10(1.5) = 1.7609 dBi).
Caveat: both modules' last-modified dates (2026-11-14) postdate the document (2026-11-13) and the
tree carries no commit dates here, so "false when written" is not provable - only "stale now, with
no marker". The file is also an orphan: 0 inbound citations, 15,291 B.
Status header: yes; marker: none.

### B-2 docs/design/onboarding/00_README.md:138
Claim: `| \`docs/design/\` | 160 files, 5,702,497 B | \`[BRIEFING]\`. Where the register and the plans live. |`
True: `find docs/design -type f | wc -l` = 165 and `du -sb docs/design` = 5,780,607 B. Off by 5
files and 78,110 B, with no "as of" qualifier on the row. The same scale block counts text only:
the 48 non-text files (8,445,464 B, 66 % of all docs bytes) are not in it.
Status header: no. This is a provably false statement inside the onboarding pack.

### B-3 docs/design/defect_register.md:891 (DR-45)
Claim: DR-45 is still violated by `visualizer_architecture.md:7` and
`lessons_learned_emfit_addendum.md:28` (both dated 2026-11-14).
True: DR-45 forbids a date later than the newest commit date. `onboarding/STATE.json` records
`as_of.head_commit` a5886031... with `head_commit_date` 2026-11-16, and no file under `docs/`
carries any date >= 2026-11-17 (verified by scanning every text doc for 2026-11-1[7-9] / 2026-12).
There is therefore no live DR-45 violation.
Caveat: the HEAD date is taken from STATE.json; this container has no git binary and no commit
dates, so the rule cannot be re-evaluated from first principles here.
Status header: no (register row).

## Severity C - cosmetic or unresolvable with the tools available

### C-1 in-content date later than the file's own mtime (28 files)
Examples (mtime -> newest in-content date, hit count): EM_SOLVER_LEDGER 11-13 -> 11-14 x6;
GEN12_HANDOFF_STATE 11-12 -> 11-14 x8, 11-13 x3; defect_register 11-13 -> 11-14 x20;
session_open_gen11 11-12 -> 11-14 x3; dispatch_log 11-09 -> 11-10 x7, 11-11 x3;
independent_anchor_qucs_2026-11-04 11-04 -> 11-05 x3; openems_referee_spec 11-09 -> 11-11 x4;
session_open_gen7 11-01 -> 11-02 x4; E11 11-09 -> 11-10 x2; visualizer_architecture 11-11 ->
11-14 x1; lessons_learned_emfit_addendum 11-11 -> 11-14 x1; e3_phase2_closure 11-13 -> 11-14 x1.
Either forward-dated entries or mtime unreliable on checkout - STATE.json's own `mtime_caveat`
warns that mtime is not authorship. Recorded as a risk, not a defect.

### C-2 SUPERSEDED tokens are overwhelmingly nouns, not status banners
177 lines across 48 files contain SUPERSEDED. Only 7 are status banners
(`pairing_rule_preregistration.md` x5 "Superseded in place - revision 3/4", `zfree_shape.md:3`,
`d58_13_strip_width_decisions_block.md:11`). The rest are phrases such as "the superseded pairing",
"the superseded statistic", "superseded run". See S3b for the per-file successor check.

## Checked and clean (negative results)

- GHOST AUDIT CLEAN. None of the three refuted claims in `onboarding/STATE.json`
  `ghosts_rejected` is asserted as fact anywhere under `docs/`. Every mention is the refutation
  itself: `00_README.md:215/217`, `01_ARCHITECTURE.md:335`, `03_KNOWN_BUGS.md:316-329/352`,
  `STATE.json:200-206`. `_volume_quiver_mesh` is asserted to EXIST at `UM3K_UI_ARCHITECTURE.md:11`,
  which is true (`server/poc_app.py:9315`, called :6116/:9431). Zero occurrences of `vi.Plane`
  anywhere in the tree. Zero `xfail`/`finalizer` in `tests/test_animation_volume.py` (only
  `importorskip` at :50-54); the xfail mentions elsewhere are unrelated run counts.
- `GEN12_HANDOFF_STATE.md` cites 24 distinct `evidence/` paths; 23 exist, the 24th is a glob
  (`evidence/logs/*.log`). No dangling evidence there.
- Headers that hold up on a keyword sweep: `57c_acceptance` (FROZEN), `cpp-kernel-spec-2026-11-09`
  ("except where it says MEASURED"), `graded_meshing_plan` ("DESIGN ONLY": no `emfit/graded*` and
  no `emfit/mesh*` exist; the "a graded y axis is not implemented" text at :444 is a proposed
  `+` diff line), `passivity_ceiling`, `modal_port_wiring_design`/`_measurement`,
  `e3_baseline_benchmark`, `s11_frame_pin`, `d52`/`d52b`/`d53` acceptance fences,
  `deflation_preregistration` (living document), `residual_vs_configuration_survey`,
  `3d_ntff_te_query` and `TE_query_s2p_convolution` (still open enquiries).
- `core_contract.md:3` "Nothing here has been implemented": not contradicted on a keyword sweep,
  but not verified line by line either - see the unknowns.
- doc-level supersession, where it exists, is well formed: `zfree_shape.md:3` names the
  supersession pass in `decisions.md`, `d58_13_strip_width_decisions_block.md:11` names sections 8-13.

## Unknowns

1. No commit dates in this container (no git binary): every date judgement rests on mtime or on an
   in-content date, and 28 files disagree between the two.
2. Whether the roadmap's "no run manifest" clause is still true was not checked.
3. Whether `core_contract.md`'s components exist under other names was not verified.
4. The roadmap's passivity claim ("exactly one passivity assertion in this tree ... deliberately
   left un-gated") is not matched by any `passiv` symbol in `emfit/*.py` or `server/*.py`; it may
   be named differently. Not counted as a finding.

<!-- generated by KB audit chunk 2; sources: filesystem walk + targeted greps + reads; mtime used as last-touch proxy except where an in-content date is quoted; no git history available -->
