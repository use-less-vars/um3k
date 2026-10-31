# ERRATA 004 — rung C against its own guards, the third instrument link, and the launch attribution the log does not carry

Marks: **[M]** measured against an artefact that exists in this tree (a JSON, a hash, a line count, a grep result);
**[L]** read from a named file and cited there; **[R]** relayed — an owner assertion or an out-of-tree number
carried in with no artefact behind it, marked and **not graded**.

Scope. This is an append-only erratum. It amends nothing in place: `evidence/rung_c_errata/PREREG.md`,
`evidence/h_refine/PREREG.md` and `evidence/strip_width/PREREG.md` are **untouched**, no gate is re-priced,
no historical row is re-graded, and no run was performed for it. It records six things about the already-banked
rung-C row `evidence/rung_c/h020.json` and the paperwork around it: **(A)** the authorisation that §150(h)(iv)
demanded is on the record and the *launch* is not; **(B)** the instrument chain acquired a **third** link that no
erratum on the rung-C pre-registration covers, so G3's letter is unsatisfied a **second** time; **(C)** the
§151(f) "nine attempts" correction has to be carried into the rung-C record because §153 does not repeat it;
**(D)** what the dispatch table can and cannot record about all of this; **(E)** corrections to
`evidence/rung_c/SUMMARY.md`; **(F)** the six guards re-derived clause by clause.

---

## A. The authorisation exists in the log; the launch does not

- **A.1 What §150(h)(iv) demanded.** `decisions.md` L9414 [L]: *"An errata run of rung C needs an explicit
  dispatcher authorisation that says so in the log; absent that, the verdict of record is INCONCLUSIVE."*
  Two conditions in one sentence: an authorisation, and that it **say so in the log**.
- **A.2 The authorisation half is satisfied [M, grep].** The row
  `strip-width-and-errata-freeze-2026-10-31` in `docs/design/dispatch_log.md` contains the phrase
  **"one-shot run authorised"**, and it is the only authorisation wording anywhere in that table. Its mtime
  ordering places it before the run: the row describes the two pre-registrations frozen at
  `2026-10-31T01:53Z` (`evidence/rung_c_errata/PREREG.md` §13 L251 [L]), the file's mtime is `01:55`, and
  `evidence/rung_c/h020.json`'s mtime is `04:57` [M]. So the sentence exists, it is dated before the row it
  authorises, and it is the sentence §150(h)(iv) asked for.
- **A.3 The attribution half is **not** satisfied [M, grep].** No row in that table records the *launching* of
  the run. The `rung-c-2026-10-31` row states "No run performed by this pass" and then, in terms,
  *"no row in this file records the launching of the run — this row performed no run — so the dispatch
  attribution of the launch is unrecorded here"*. The two statements are consistent and they leave exactly
  one hole: **who dispatched the run, and under which row's fence, is not written down in this tree.**
- **A.4 What the artefact itself can and cannot supply [M].** `h020.json` records
  `command_line = 'host_ladder.py --h 0.2 --clearance 3.0 --box-lateral-mult 8 --box-lid-mult 1 --pml-mm 4.8 --mem-ceiling-mb 4000 --json evidence/rung_c/h020.json'`,
  `meta.cwd = '/home/jojo/PycharmProjects/EE'`, `meta.git_rev = '3092129843d79939579684d1af59b393ce0b3'`
  source `head-loose`, `meta.platform = 'Linux-7.0.0-38-generic-x86_64-with-glibc2.39'`. That is **how** the
  tool was invoked and **where**, not **who** authorised it. A command line is not an attribution, and the
  file's mtime is a write time, not a dispatch time. No arithmetic in this tree recovers the missing half.
- **A.5 So state it in the form it actually has.** §150(h)(iv)'s *danger* was a gate re-negotiated after
  seeing the data; that danger is not in play, because the `1400 s` ceiling was frozen at `01:53Z` before any
  `h = 0.2 mm` row existed anywhere in the tree [L, §13 L251] and is `4.6 %` clear of the measured
  `1335.56 s` [M]. §150(h)(iv)'s *condition* was procedural — an explicit authorisation in the log — and on
  that condition the record is **half satisfied**: authorised yes, attributed no. Both halves are recorded
  rather than one being traded for the other.

## B. G3: the letter is unsatisfied a **second** time, and by a link no erratum covers

- **B.1 The clause, verbatim [L, §9 L197–201].** *"**G3 same instrument** — `tools/host_ladder.py` sha256 must
  still be `1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` and `tools/d585_modal.py`
  `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6` [M, identical to the `box_sweep` §12
  freeze]. If either moved, the third rung is not on the same instrument as the first two and the three-rung
  sequence is not gradeable."*
- **B.2 The chain now has three links, not two [M/L].**

  | # | `tools/host_ladder.py` | lines | what moved it | which erratum covers it |
  |---|---|---|---|---|
  | 1 | `1cd1a3ee…abeb9` | 1106 | the frozen instrument — `strip_width` §12 and `rung_c_errata` §9 G3 both pin this | it *is* the pin |
  | 2 | `519365eb…0d57c` | 1261 | cleanups-cd tasks C + D (metadata only, two regions) | **yes** — `rung_c_errata/ERRATA_001.md` §3 |
  | 3 | `0d719197…0c9b` | 1395 | the ascending shift ladder replacing the descending one | **no erratum on the rung-C pre-registration** — covered only by `strip_width/ERRATA_002.md` §1.3/§2 and `strip_width/ERRATA_003.md` §(b) |

- **B.3 The ordering is the argument, and it holds [M].** mtimes: `rung_c_errata/PREREG.md` `01:55` →
  `rung_c_errata/ERRATA_001.md` `02:05` → `tools/host_ladder.py` `02:55` → `evidence/rung_c/h020.json`
  `04:57`. The third revision therefore landed **after** the erratum that pinned the second and **before** the
  run of record. It is not a post-hoc edit fitted to a result; the row could not have informed it. That is the
  same prospective argument `ERRATA_001.md` §3 makes for link 2, and it transfers to link 3 unchanged.
- **B.4 What actually preserves the protected object, re-measured this session [M].**
  `tools/d585_modal.py` = `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6`, **676** lines —
  byte-identical to its pin. `emfit/studies.py` =
  `578650bc59b1dbaa09832ec3dde2c0058fa69e0dcee56c2e8a4cc7ff37e802ac`, **5166** lines — byte-identical. So the
  **graded** reference function (`hammerstad_beta`), the solver call, the geometry law, the material stack, the
  reporter and the station estimator are all on the frozen bytes. Only `host_ladder.py` — the harness — moved.
- **B.5 And the moved region did not fire on this row [M].** `meta.sigma_retries = 0`,
  `meta.sigma_attempts = [[{accepted: True, sigma_mult: 0.76, ...}]]`, `sigma_ladder =
  [0.76, 0.775, 0.79, 0.805, 0.82, 0.85]`. The first multiplier `0.76` was accepted on the first attempt, so
  the ascending ladder — the entire substance of the third edit — was **exercised at exactly one point, and
  that point is the same `0.76` the frozen tool tried first** [L, `strip_width/ERRATA_002.md` §1.3; the old
  descending list began `0.760` too]. The edit cannot move a pass/fail line on a row where the ladder never
  advances, which is the narrowest and strongest form of the "same instrument" claim available here.
- **B.6 What is still wrong, stated plainly.** The letter of G3 is unsatisfied, and this is the **second**
  time: G3 asks for `1cd1a3ee…`, and the tree holds `0d719197…`. Two amendments have now been argued — link 2
  by `rung_c_errata/ERRATA_001.md` §3, link 3 by nobody on the rung-C side. The second is worse in one
  specific respect: link 2 was argued **in advance, in the file whose clause it superseded**, and link 3 was
  not argued anywhere on the rung-C side at all; it is recorded only in the strip-width errata, i.e. in a
  document that does not own the clause it leaves unmet. This erratum supplies the missing argument and
  **does not** claim that supplying it late is as good as supplying it early.
- **B.7 A second gap, disclosed because it is the sort of thing a later reader would assume was done.**
  `ERRATA_001.md` §2 records two post-edit checks against the 1106→1261 step: `python3 -m py_compile
  tools/host_ladder.py` → OK, and `--help` → exit 0 with a **byte-identical** 75-line text [L]. Those two
  checks were **never re-run against the 1261→1395 step**: a search of `evidence/` for `py_compile` / `--help
  exit 0` / `byte-identical 75-line` returns only the `ERRATA_001` blocks for link 2 [M, grep]. So link 3 has
  **no recorded smoke test in this tree**. It is not claimed to be broken — the row it produced parses, and
  the row's own fields are self-consistent — but the check is absent rather than passing, and "absent" is
  written down here instead of being read as "fine".
- **B.8 The alternative reading is recorded, not defeated.** G3 admits no amendment: a pre-registered hash
  clause is the one commitment in the file that cannot be superseded by argument, so rung C is not on the same
  instrument as rungs A and B and **the three-rung sequence is not gradeable**; the fall in §2 of the summary
  is then a comparison of two instruments. That reading is not answered here, and it is not answered by the
  observation that the ladder did not fire — a reader who holds that a moved hash voids the rung is not
  making a claim about which lines ran, but about what was pre-registered. Both readings are on the record;
  the tree does not contain an arbiter.

## C. Carried in: §151(f)'s "nine attempts" and the `0.93`–`0.99` band are both wrong

- **C.1 Why it belongs here [L].** The correction lives in `evidence/strip_width/ERRATA_003.md` §(c), which
  amends the **strip-width** pre-registration. `decisions.md` §153 writes up rung C and does not repeat it,
  so a reader of the rung-C record alone carries §151(f) uncorrected. Carried in verbatim in substance,
  re-derived here:
- **C.2 The "nine" is a multiplier list, not a count of attempts [M].** §151(f) says *"Its nine attempts are
  exactly the non-converged attempts banked in `W12`/`W16`/`W20`, residual `0.93`-`0.99`"*. The nine is the
  **old descending ladder's multiplier list** — `0.760, 0.757, 0.754, 0.751, 0.748, 0.745, 0.700, 0.600,
  0.900` — i.e. the number of *rungs the ladder could have tried*, not the number of attempts any row made.
- **C.3 The banked non-converged attempts are SIX, not nine [M].** One in `W12`, two in `W16`, three in
  `W20`, with residuals `0.9559803168921627` (`W12`); `0.9374781042952944`, `0.9523820823233484` (`W16`);
  `0.9327792913828687`, `0.9650183697692649`, `0.9221065847163377` (`W20`).
- **C.4 The band is too narrow by `0.008` [M].** `0.9221065847163377` lies **outside** the stated `0.93`-`0.99`
  range. The correct band is **`0.92`–`0.99`**, and a report that quotes `0.93`-`0.99` as the observed spread
  of banked junk residuals has excluded one of the six numbers it is describing.
- **C.5 A dangling pointer, recorded and **not** repaired [M].** `evidence/strip_width/EIG_strip_width.json`
  L25's `cross_warrant` points at `meta.failure`, a key that no longer exists on the three arms; the values
  survive at `sigma_attempts[0][0].best_residual`. The witness file is **not edited** by this erratum: it is
  evidence, and evidence is not rewritten to agree with a later schema.
- **C.6 Rung C does not inherit the defect [M].** `sigma_retries = 0` and one attempt in
  `meta.sigma_attempts`, so no junk residual was banked for rung C and no band applies to it. The correction
  above is about the **strip-width** rows and about §151(f)'s description of them, not about the rung-C row.

## D. What the dispatch table can and cannot now record

- **D.1 Two rows are added by this dispatch, and one of them was rewritten on the repair pass [M].** The
  `rung-c-errata-2026-10-31` row fences this file, the `## 154.`–`## 156.` blocks of `decisions.md`, §11 of
  `evidence/rung_c/SUMMARY.md`, and the rows themselves. The second row, `rung-c-launch-2026-10-31`, is an
  **authorising** row — recorded 2026-10-31 **after** the run (`04:57`) and saying so — whose **referent** is
  the launch itself (its scope is *none*: it writes no path, and the run it authorises is the already-banked
  `evidence/rung_c/h020.json`), and whose **attribution** is an owner relay `[R]`, marked and not graded,
  because no artefact in this tree names a dispatcher. This replaces the earlier wording, which called the
  row *"not a dispatch and authorises nothing"*: that was true of the row as first written and is superseded
  by a row that states what it can and cannot carry. The table's own first paragraph says *"A dispatch that
  is not on this list is not authorised"*; the honest position after A.3 is that the launch now has a row
  naming it and an authorisation that predates it, and still **no attributed dispatcher** — writing that
  down is better than leaving the reader to infer a completeness the table does not have.
- **D.2 What no row can supply now [M].** A row can record a fence and a status; it cannot record who issued a
  dispatch that was never written. Nothing added today converts the missing attribution into a present one,
  and nothing in this erratum dates the launch — `04:57` is when the JSON was written.
- **D.3 A constraint on later rows, stated so it is not violated by the next pass.** The `strip-width-docs`
  row's instruction — **do not quote as "C was affordable"** — still binds. §150(h)(iv)'s affordability
  sentence describes a *pre-registered budget*, not a resource wall, and A.2's authorisation does not convert
  it into one. The `1400 s` ceiling was met at `1335.56 s` (`1400 / 1335.56 = 1.048`) [M]; that is a
  measurement inside a budget, not a licence.

## E. Corrections to `evidence/rung_c/SUMMARY.md` (carried out in §11 of that file)

- **E.1 The station count in the recommendation was wrong [M/L].** `SUMMARY.md` L237 reads *"the `9.6 mm`
  station span and the `8` stations"*. The count is **nine**: `emfit/studies.py` L1176–1180 sets
  `MS_X_FIRST, MS_X_LAST = 10.4e-3, 20.0e-3` and `MS_N_STATIONS = 9` [L], and the row itself reports
  `n_stations: 9` [M]. The span `20.0 − 10.4 = 9.6 mm` at `1.2 mm` spacing is **eight intervals and nine
  stations**; `8` is the number of intervals. The recommendation's substance is unaffected — a shorter span
  still de-aliases the two-station estimate, and the wrap modulus `2*pi/span = 654.498 rad/m` is a function of
  the **span**, not the count [M, recomputed].
- **E.2 The `[R]` quarantines stand unchanged.** `0.59` (relayed FDTD order) and the relayed `0.377` pp
  extraction bias remain `[R]`/`[UNVERIFIED]`: a tree-wide search still finds `0.59` only in `SUMMARY.md`
  L83/88/90/94 *as not reproducing* and in one dispatch row, and finds no provenance for `0.377` at all [M].
  Neither is promoted by anything in this erratum.
- **E.3 The §6 counter-example note stands.** Rung C's `sigma_mult_used = 0.76` at an effective `n_strip = 4`
  is a counter-example to the closed form `0.76 + 0.015*(n_strip − 2)` recorded at §152.11 — the multiplier
  follows the residual, and one row is not a law's refutation but is a reason not to quote it as one [M].

## F. The six guards, re-derived clause by clause

| guard | clause (short) | verdict | basis |
|---|---|---|---|
| **G1** | the physics is untouched; "any edit to them voids this file" | **PASS** | `d585_modal.py` and `studies.py` byte-identical to their pins, re-measured this session [M]; `hammerstad_beta` is *in* `d585_modal.py` [L, `ERRATA_001` §2] |
| **G2** | `wall_fdtd_s > 1400` or `peak_rss_mb > 4000` ⇒ "not measured, gate tripped", never extrapolated, no retry | **PASS** | `1335.5644 s` and `2388.48046875 MB`: `1400 / 1335.5644 = 1.048` (4.6 % headroom), `4000 / 2388.48 = 1.675x` [M] |
| **G3** | `host_ladder.py` still `1cd1a3ee…` | **FAIL (letter)** | it is `0d719197…`, `1395` lines [M]; the argument in §B is the only thing standing between this and ungradeable, and the alternative reading is recorded (§B.8) |
| **G4** | `hammerstad_beta` reproduces the pin to `1e-6` at rung C's realised tone | **PASS** | computed this session: `hammerstad_beta(f=10.19862621457275e9, W=0.8e-3, H=1.6e-3, eps_r=4.4)['beta'] = 384.74897567707814` vs pin `384.7489756770833` → relative `1.34e-14`, five orders inside the `1e-6` gate [M] |
| **G5** | exit 0, `meta.status 'ok'`, `abort_reason` None, cell count within 5 % of 3.27 M | **PASS** | `status 'ok'`, `complete True`, `abort_reason None`, `n_cells 3 271 744` vs `3.27e6` = `0.05 %`; box `lat 8 / lid 1` per §150(h)(iii); `npml 24` = `4.8 mm / 0.2 mm` [M] |
| **G6** | exactly one `h = 0.2` run authorised | **PASS** | a search of `evidence/` for `"h_mm": 0.2` returns exactly one artefact, `evidence/rung_c/h020.json` [M] |

- **F.1 What the table says that the prose does not.** Five of six guards are satisfied **by measurement**;
  one fails **in letter**. The gradeability of the ladder therefore rests on a single argument (§B.4–B.5) and
  not on a clean sweep, and nothing in this erratum upgrades the argument into a measurement.
- **F.2 Two residual attacks that survive and are recorded as surviving.**
  (i) `meta.mem_ceiling_mb = 4000.0`, i.e. exactly the prescribed value, while `meta.cgroup_limit_mb = null`
  (the tool's "no finite limit" / `"max"` sentinel) — so the memory leg of G2 was met against a self-declared
  ceiling on an unbounded host and not against a container limit [M]. (ii) `meta.cwd =
  '/home/jojo/PycharmProjects/EE'` with a real `git_rev` means this is a **host run, not the container of
  record** [M], the same deviation disclosed for the strip-width arms at
  `strip-width-closeout-2026-10-31` item (ii). Neither changes a number; both change what the numbers are
  taken to have been taken on.
- **F.3 One number that must not be promoted.** The `1400 s` ceiling was set from the `1163 s` **projection**
  (`1163 * 1.20 = 1395.6 → 1400`) [L, §4 L96-99], before the run. The run's `1335.56 s` is inside it. That is
  a measurement inside a frozen budget. It is not evidence that the budget was right, and it is not a licence
  to say C was affordable (§D.3).

---

## What this erratum does not do

It does not claim G3 is satisfied: the hash moved a **second** time and the letter of the clause is unmet, and
the argument offered in §B is an argument, not a measurement. It does not defeat the alternative reading that
rung C is ungradeable — that reading is recorded in §B.8 and the tree holds no arbiter between them. It does
not supply the missing launch attribution (§A.3): a row that says "not recorded" is not a record of the thing
itself, and nothing here dates the launch. It does not repair the missing `py_compile` / `--help` check on the
1261→1395 step (§B.7) — the check is absent and is now labelled absent, not retro-run against a tree that has
moved on. It does not re-price the wall or memory ceilings, does not re-grade any historical row, and does not
edit `PREREG.md`, `tools/`, `emfit/`, `tests/` or the witness `EIG_strip_width.json`. It does not promote
`0.59` or `0.377` pp out of `[R]`. And it does not convert five passing guards into a clean sweep: the
sequence is gradeable only if §B's argument holds, and a reader who rejects it should read the verdict of
record as **unsettled** rather than as DISCRETISATION IMPLICATED.
