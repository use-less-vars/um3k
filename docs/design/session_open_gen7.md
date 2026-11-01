# Session open — Generation 7

**Written 2026-11-02, at HEAD after `bca8d3b` + `e324089`. Reader: the incoming engineer; read this FIRST, then `session_close_gen6` if it exists, then the defect register, then the active scope.**

## How this document was written

Drafted by the outgoing Generation 6 on 2026-11-02, at HEAD `e324089`, immediately after the
`line-ref-transport-2026-11-02` row was added to `docs/design/dispatch_log.md`. Every numeric claim
below was checked against the artefact named beside it **at drafting time** — the JSON leaf, the
`path:line`, or `--dry-run` output — and not carried over from an earlier summary. A claim that could
not be checked against a file is tagged `[R]` (relayed from the owner) or `[L]` (an estimate no
artefact supports yet); nothing untagged is a guess. **The artefact always wins over this text:** if
a number here disagrees with `evidence/termination/*.json`, the register, or the scope, the file on
disk is right and this paragraph is wrong — say so in the next dispatch row rather than editing the
artefact.

Two drafting decisions, stated so they are not read as slips. (a) The numbering is **Gen 7**: an
earlier draft of this brief said Gen 8 and the owner corrected it. (b) `docs/design/session_close_gen7.md`
already exists, dated 2026-10-31 and written by the previous generation — it is a **close** document
for the *seventh* close of the *sixth* generation's bookkeeping, not a predecessor of this file. Read
`session_close_gen6.md` (29,804 B, 2026-10-31 18:50) as the handover; `session_close_gen7.md` is a
different artefact with a colliding name and should be folded or renamed by the owner.

## 1. Where we are

The absorbing-termination build is nearly done. The phase mechanism works; the magnitude chain does
not, and the reason is understood. The FDTD solve is healthy: the three v2 arms complete with
`meta.status` `"ok"`, no warnings, and no ceiling or wall trip.

**Working.**

- **AC-6 PASS on v2** — `graded_v2.json:/criteria/AC-6/pass` is `true`, with
  `achieved.load_kind` `"series_r"`, `load_value` `50.0`, `load_units` `"ohm"`,
  `load_plane_index` `50`, `load_position_mm` `20.0`, `s21_plane_index` `50`, `indices_agree` `true`
  (bar: `docs/design/absorbing_termination_scope.md:260-261`).
- **AC-7 PASS at 0.8 mm, FAIL at 3.2 mm, and the fail is the verdict of record.** The pre-v2
  revision (`build_A_50ohm.json`, `geometry.w` **0.0008** m, `geometry.grid` **[62, 206, 22]**,
  `cells` **280,984**) passed at `rel_error` **0.0004565049491949793** — **0.04565 %**, i.e. the
  0.0457 % on record — against `beta_modal` **216.86115860414054** rad/m
  (`graded.json:/criteria/AC-7/achieved/rel_error`, `pass` `true`). **That number belongs to the
  0.8 mm strip and must never be quoted for 3.2 mm**: at 3.2 mm the reference itself moves to
  **227.31018858464796** rad/m, so the two figures are not comparable. On v2 the same criterion
  reads `rel_error` **0.016404353915224042** — **1.6404 %** — against the bar
  `|beta_FDTD - beta_modal| / beta_modal <= 1.0e-3` (`scope:266-268`), with
  `beta_fdtd_rad_per_m` **223.58131180256908** and `beta_modal.beta_modal_rad_per_m`
  **227.31018858464796** (`graded_v2.json:/criteria/AC-7/{achieved,pass}` = `false`).
- **FDTD at 3.2 mm agrees with Hammerstad to 0.102 %** — `rel_error_vs_hammerstad`
  **0.0010219020795365688**, `beta_hammerstad_rad_per_m` **223.35306683909533** vs `beta_fdtd`
  **223.58131180256908** (`graded_v2.json:/criteria/AC-7/achieved`). **A candidate, not a quotable
  result** — see DR-14 and §7.

**Blocked.**

- **AC-3 (`|S11| <= 1.0e-3` and `| |S21| - 1 | <= 1.0e-3`, `scope:235`) — FAIL.** v2 shows gain in a
  passive structure: `s21.magnitude` is **1.1137907453296516** (A), **1.167514794293979** (B) and
  **1.0102359777545176** (E); `s11.magnitude` is **0.33273834094256227** (A),
  **0.4741188722731575** (B — the exploratory 100 Ω arm) and **0.3549094983549645** (E), all read
  from `build_*_v2.json:/s21/magnitude` and `/s11/magnitude`. Note the **mapping**: A is 1.11, B is
  1.17, E is 1.01 — an ordering that has already been mis-transcribed once. The graded criterion
  scores **A only** (`source_artefact` `"A"`): `s11_abs` **0.33273834094256227**,
  `s21_abs` **1.1137907453296516**, `s21_abs_minus_one` **0.11379074532965161**,
  `s11_margin` **-0.33173834094256227**
  (`graded_v2.json:/criteria/AC-3/achieved`). **Cause: the loaded runs had no reference.** All three
  v2 artefacts carry `run.loaded_without_reference` **`true`**, with the note that the cut branch
  "degraded to `zc_split = zc`" — the line constant used to transport the port plane to the cut is
  the run's own, not a load-free measurement.
- **AC-5 — FAIL, same blocker.** Bar (`scope:251`): no `|s21|` above **1.00001** anywhere in the
  batch (magnitude half), plus the seam half in AC-5b. Achieved: `s21_abs`
  **1.1137907453296516**, `tripwire` **1.00001**, `headroom` **-0.11378074532965154**
  (`graded_v2.json:/criteria/AC-5/achieved`). The quantity is **the same `|s21|` of the same
  artefact A** as AC-3's, compared against a slightly different bar — AC-3 uses `| |s21| - 1 |`
  against `1.0e-3`, AC-5 uses `|s21|` against `1.00001` — which is why `s21_margin` (-0.11279) and
  `headroom` (-0.11378) differ in the third decimal. `pass_scope` reads `"magnitude half only"` and
  the entry says in terms that `pass` must not be read as AC-5 closed.
- **AC-4 and AC-5b not run.** Both are `pass: null`, `achieved: null`, with an explanatory `status`
  string: AC-4 needs two **unmatched** loads (`scope:246-250`), AC-5b needs an open control and a
  PML-terminated reference in the same batch (`scope:256-258`). Both deferred to dispatch 2c. These
  are **not-evaluated, not failures** — `graded_v2.json:/verdict` carries `null` for both, and a
  reader who scans only the booleans will mis-count them.

## 2. In flight (pending host runs)

Three graded v3 runs **with `--with-twin`** are queued and **NOT run**. No v3 artefact exists:
`evidence/termination/` holds `build_{A_50ohm,B_100ohm,E_50ohm}.json`, the three `_v2.json` arms,
`build_smoke_50ohm_twin.json`, `grade_2b.py`, `graded.json`, `graded_v2.json`,
`graded_v2_refix.json` and six logs — and no `*_v3.json` or `*_v3_twin.json` of any kind.

The three commands (assembled from the v2 `meta.command_line` values by adding `--with-twin` and
moving `--out` to a v3 stem; **every flag verified against `run_build_A.py` argparse at
`:842-885`** — nine options exist, `--out`, `--load-at-mm`, `--n-line`, `--load-ohm`, `--label`,
`--mem-ceiling-mb`, `--wall-limit-s`, `--with-twin`, `--dry-run`, and **no strip-width flag
exists at all**, so no invocation can be described as dropping one):

```
python3 evidence/termination/run_build_A.py --n-line 54 --load-at-mm 20 --load-ohm 50  --mem-ceiling-mb 2000 --with-twin --out evidence/termination/build_A_50ohm_v3.json
python3 evidence/termination/run_build_A.py --n-line 54 --load-at-mm 20 --load-ohm 100 --mem-ceiling-mb 2000 --with-twin --out evidence/termination/build_B_100ohm_v3.json
python3 evidence/termination/run_build_A.py --n-line 79 --load-at-mm 30 --load-ohm 50  --mem-ceiling-mb 2000 --with-twin --out evidence/termination/build_E_50ohm_v3.json
```

**Cost [L].** ~80 s (A), ~74 s (B), ~101 s (E) — that is **~2x the measured v2 single-solve wall**,
and the doubling is the point: `--with-twin` runs **two** solves under one process budget
(`--with-twin` help: "the single `--wall-limit-s` budget is a PROCESS budget that has to cover
both"). Measured v2 single-solve cost [M]:
A **40.12149550707545 s** / peak RSS **303.859375 MB**; B **36.73167413903866 s** /
**303.8671875 MB**; E **50.59691300103441 s** / **388.94140625 MB** (`meta.wall_total_s`,
`meta.peak_rss_mb`). Two operational facts: the mem ceiling is checked **before launch** and a
request above the container's cgroup limit is refused with exit 2 (`run_build_A.py:961-969`), and
the v2 artefacts record `cgroup_limit_mb` **`null`** — so these need a host launch, not a small
sandbox; and each run writes its **twin JSON before its loaded JSON**, so a failed loaded half still
leaves the twin banked.

**Grade with** `evidence/termination/grade_2b.py` over the three new files, exactly as the refix row
did. **Expected if the fix works:** the AC-3 magnitude criterion; the seam — `line.beta` across
A / E / B within **1 %** on identical geometry; and AC-3b — a phase transport residual within
**5 deg** in `arg s21` and **1 %** in `|s21|`, against a second twin whose stations are the run's own
planes.

**Decision rules — write the outcome into a dispatch row before interpreting it.**

| outcome | reading |
|---|---|
| AC-3 **and** AC-3b **and** seam pass | DR-16 → **FIXED-TESTED**, first quotable S11 candidate, AC-3 closes |
| AC-3 passes, AC-3b fails | transport mechanism defect — **DR-17 opens**, do not close DR-16 |
| AC-3 fails, AC-3b and seam pass | transport works, magnitude problem is separate; next dispatch = magnitude chain |
| anything else | diagnose; **do not declare DR-16 closed** |

**Do not claim the register agrees with the owner on AC-3b.** The owner recorded the AC-3b
ratification on 2026-11-02, but `docs/design/defect_register.md:213` still reads "The **5 deg** figure
is **PROPOSED and NOT ratified**" as of this commit, and `:249` adds that AC-3b "is graded by
**nothing**". The register lags the owner here; the lag is deliberate (the register is a separate
owner edit) and must not be papered over. A related mismatch is inside the tree already:
`dispatch_log.md` L40 item (v) states the AC-3b bar as **1 deg**, while the register says **5 deg**.

## 3. Open defects

Summary only — **`docs/design/defect_register.md` is the authority** (261 L; DR-1…DR-13 live outside
this tree by design).

- **DR-14 — OPEN, MEDIUM (`:18`).** Two closed forms for the same cross-section disagree by
  **1.7717 %** in beta at w 3.2 mm / h 1.6 mm / 5.8277864083 GHz: `mode_profile`
  **227.31018858464796** vs Hammerstad **223.35306683909533** (eps_eff 3.463476 vs 3.343938), which
  is **17.7x** the `1.0e-3` bar (`:51`: 1.7717 % / 0.1 % = 17.7169x). `beta_fdtd`
  **223.58131180256908** sits 0.1022 % from Hammerstad and 1.6404 % from mode_profile — too close to
  either to arbitrate. **It does not gate AC-7**: AC-7 is graded against `mode_profile` because
  `scope:266-268` names it. Three candidate causes listed, **none picked**. Not the earlier ~2.9 %
  Flag 1 scare (a tone artefact).
- **DR-15 — RESERVED, not opened (`:255`).** Holds the unloaded-twin **seam check**: `line.beta`
  across A / E / B within **1 %** on identical geometry, else the twin fix carries its own defect.
  The register says when it opens only implicitly — "held for the seam check … else the twin fix
  carries its own defect. The check has not been run; this line only reserves the number" — so *v3
  seam check fails ⇒ DR-15 opens* is a reading of that sentence, not a sentence in it. Mark it as
  such.
- **DR-16 — OPEN (`:102`), fix landed in `bca8d3b`.** `LineReference.forward_ratio` refused any run
  whose `s21` planes were not identical to the reference's own first and last station, so
  `--with-twin` could not normalise a graded run — the guard fired after the expensive half was
  paid for. The fix transports the residual per metre as `ratio ** (run_span / station_span)`, keeps
  the endpoint case byte-identical, and excludes the load-inside-line pairing. `FIXED-TESTED` is
  **pending v3**; the register's own transition rule requires a host run of A / E / B with
  `--with-twin` in which the magnitude criterion **and** the transport criterion of (iii) both pass.
  Its four unpaid requirements: (i) a loaded run completing with
  `loaded_without_reference` **False**; (ii) the transported residual and the exponent **1.75**
  quoted out of an artefact; (iii) AC-3b; (iv) the graded arms re-checked with a reference in hand
  (A / B / E were graded with `reference=None` and an assumed `zc`). Item (v) records the re-grade
  and its caveat: 136 leaves, 0 differing, but `grade_2b.py` contains zero occurrences of
  `forward_ratio`, so the re-grade is **necessary and not sufficient**.
- **Not in the register at all, and said so here rather than left to be searched for:** `T4_amp`,
  `T2_agree`, the **deflation no-op**, the **ker A retirement**, and the **`grid_for(0.3)` silent
  substitution** return **zero matches** in `defect_register.md`. They exist in the tree —
  `T4_amp` in `docs/design/t4_amp_ratio.md` (FAIL at 44.09 % on the 2026-11 record) and
  `decisions.md`; `T2_agree` at `evidence/strip_width/PREREG.md:32`; the deflation no-op and
  `ker A = {0}` at `decisions.md:9949` and `evidence/matrix_audit/k0squared_classify.md:157`; the
  `grid_for(0.3)` 20 % silent narrowing at `decisions.md:9406` / `:9430` and
  `evidence/h_refine/SUMMARY.md:137` — but **none of them has a DR number**, so none of them is
  gated by this register. That absence is the finding: five known tool/threshold defects are carried
  outside the defect register.

## 4. Error count

**52 errors from the supervisor this generation, all caught** [R, the owner's own count]. Catch rate
**100 %**; the cost is the **rate of generation**, not the detection. Class breakdown as recorded
[UNVERIFIED — the owner's classes, not independently re-counted]: path / citation 9+, borrowed
specific 2, premature closure 2, fabrication 2, arithmetic slip 3, inverted inference 1, spec defect
4+, unit conflation 2, timer-as-measurement 1, fence-too-tight 1, others. The pattern is uniform and
worth naming: **plausible-sounding generated specifics, caught by artefact comparison** — a number
that looks like the one in the file, a citation that looks like the right line, a conclusion that
looks like the one the data supports. The fix is procedural, not moral: **fewer unverified claims per
dispatch**, and every specific tied to a `path:line` or a JSON leaf before it is written.

## 5. Theory engineer

Two consultation rounds are recorded, but **not at the path this brief assumed**:
`docs/design/theory_consultations.md` **does not exist** (`find -iname "*consult*"` is empty). What
exists is **`docs/design/theory_round2_memo.md`** — "Round-2 memo: parked third-party analysis, not a
project decision", 2026-10-31, a verbatim memo from one theory-engineer worker, `claim -> path:line ->
tag`, explicitly "an opinion, not a decision, not a dispatch record, not graded, nothing ratified".
**No round-1 document is findable in this tree.** Treat "rounds 1 and 2 substantive" as **half
supported**: round 2 is substantive and on disk; round 1 has no artefact here.

**Next trigger:** after the v3 runs land, or when DR-14 is taken up. **The question worth paying
for:** which of the two standard closed forms is authoritative at w/h = 2.0 — and, second, whether
FDTD's 0.102 % agreement with Hammerstad counts *for* Hammerstad, or *against* `mode_profile`. That
question is answerable and it is the one DR-14 has parked.

## 6. Next four dispatches

1. **Run v3 on the host and grade it.** Decide AC-3 / seam / AC-3b by the table in §2. This is the
   only dispatch that can move DR-16.
2. **AC-4 + AC-5b in 2c.** Two unmatched loads (25 Ω and 100 Ω in one batch) plus an open control
   and a PML-terminated reference pair. Both criteria are currently `null`; neither is closeable by
   reading.
3. **Modal port wiring.** `ModalPort.from_mode2d` is defined at `emfit/modalport.py:194` (its error
   string at `:217`) and has **zero callers** — the only two `from_mode2d` occurrences in
   `emfit/`, `tools/` and `tests/` are those two lines in the defining file. Hours of work, not
   dispatches. Nothing downstream that needs a modal launch can start without it.
4. **First quotable S-parameter with a real error bar.** Everything in §1 is a candidate until this
   exists.

After those: the stub-loaded demo, the graphical engine POC, antenna S11 (needs the modal port; PML,
Mur and near-field extraction exist), multi-port.

## 7. What to distrust

- **Any specific in this file or any summary that is not cited to a `path:line` or a JSON leaf.**
  Fifty-two of them were wrong this generation and all fifty-two were the same species.
- **The E4 tag.** "FDTD's 0.10 % agreement with Hammerstad is the first E4 candidate this project has
  produced" is **contradicted**: E4 is the **Calibrated** tier of the project's own vocabulary
  (`viz/acceptance.md:104`, `decisions.md:8658`), and an E4 candidate is already on record —
  `evidence/rung_c/SUMMARY.md:97` "E4 candidate: the gap is `h`-invariant", carried at
  `decisions.md:9875(e)` and `:9934(p)`. It is a candidate; it is not the first.
- **Any "two of three" from mid-session.** The verdict set of record in `graded_v2.json` (identical
  at every boolean in `graded_v2_refix.json`) is: **AC-6 `true`; AC-3 `false`; AC-5 `false` (magnitude
  half only); AC-7 `false`; AC-4 `null`; AC-5b `null`** — `/verdict`. That is **one pass, four not-passed
  of which two are not-evaluated**, not "two of three". The older framing — one genuine pass
  (provenance, AC-6), one circular pass (phase, AC-7 at 0.8 mm before the strip-width fix), two
  failures (both magnitude criteria) — describes the **history**, and it silently drops AC-7's
  present `false`; a reader who takes it as the current set will undercount the failures by one.
- **"The phase mechanism works" is supported, with two complications.** Supported: the 0.8 mm
  revision passed AC-7 at 0.04565 %, and the cross-run raw-phase slope is the quantity that carries
  the information. Complication one: the pass came at a **different geometry against a different
  reference** (w 0.8 mm, `beta_modal` 216.86), so it is evidence about the method, not about the
  3.2 mm line. Complication two: at 3.2 mm the same mechanism is **1.64 % out**, which is 16.4x the
  bar — so "the phase mechanism works" is true of the extraction, not of the termination's phase
  fidelity at the graded width.
- **"The magnitude chain does not work" is supported, but it is not yet an independent finding.**
  `|s21|` > 1 on all three arms and `|s11|` = 0.33 at a matched load is gain in a passive structure,
  and the recorded cause is `loaded_without_reference` — the same missing reference that the twin
  fix addresses. Until v3 runs with a reference in hand, "magnitude fails" and "the reference was
  absent" are one observation, not two. If v3 fixes the magnitude as well, the honest sentence is
  that the magnitude failure was a symptom; if it does not, the magnitude chain is a separate defect
  and the dispatch is §6 item 1's third row.

## 8. Nédélec RAM roadmap

This section was missing from the first commit of this document (§1–§7 only) and is appended here. It is a pointer, not a re-derivation; the numbers are carried from the cited artefacts, no new numbers are introduced.

- **Production modal basis = quasistatic 2D Laplace** (`emfit/mode_profile.py`). This is what AC-7 is graded against (`docs/design/absorbing_termination_scope.md:266-268` names it), and it is what the production path uses. It does not call the Nédélec solver.
- **The expensive Nédélec mixed pencil is validation-only**, capped at `_MIXED_DENSE_MAX = 3000` free edges (`emfit/mode2d.py:185` [M]). It is not on the production path; it exists to validate the modal basis, not to produce it.
- **If the production basis ever needs full-wave, Route C is proven-in-probe but not landed.** Landing it is a **build dispatch, not a research problem** — see `docs/design/theory_round2_memo.md`. The probe result and its caveats live there.
- **SLEPc / p=2 / matrix-free Schur become necessary at ~200k–300k dof** [R, quoted from `docs/design/theory_round2_memo.md`]. Below that, the dense/quasistatic path is sufficient; above it, the dense path's RAM becomes the binding constraint.
