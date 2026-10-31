# Erratum 001 — `evidence/rung_c_errata/`

**Append-only erratum to the freeze declaration.** This file amends `evidence/rung_c_errata/PREREG.md`
§13 — whose provenance line pins `tools/host_ladder.py` at `1cd1a3ee…abeb9` (1106 lines) — frozen
**2026-10-31T01:53Z** and committed as **`5af2756`**. `PREREG.md` is not modified — not one byte — and
nothing here restates, softens or re-opens a clause it froze. §13 itself names no erratum mechanism; it
is `evidence/strip_width/PREREG.md` §12 ("A future edit to any of the three files above voids the freeze
and requires an append-only erratum, not a silent re-run") that does, and that sentence covers this file
too because both PREREGs pin the same three hashes. The operative guard *in this file* is §9 **G3**,
addressed on its own terms in §3 below.

Issued under dispatch `cleanups-cd-2026-10-31` (tasks C and D).

**No FDTD run is performed, priced, authorised or extrapolated by this erratum.** No `h = 0.2 mm` row
exists anywhere in this tree, before or after this file. In particular this erratum **does not extend,
renew or re-issue the one-shot grant of §9 G6**: exactly one `h = 0.2` run remains authorised, under the
gate as amended by the PREREG above, and it has not been launched.

## 1. What changed, and why

Two edits, both to `tools/host_ladder.py`, both **metadata-only**. They are the same two edits recorded
in `evidence/strip_width/ERRATA_001.md` — one edit, two frozen PREREGs, two errata, because §13 and
`strip_width` §12 pin the same file.

### 1.1 Task D — `git_rev()` no longer shells out

The old body was one `subprocess.run(["git", "rev-parse", "--short", "HEAD"], …)` — the short HEAD on
success, and on failure the single string `unavailable: <ExcType>: <message>`. In the **container of
record** there is no `git` binary, so the field never once carried a revision: **all nine frozen rows
record the same non-answer**, `"git_rev": "unavailable: FileNotFoundError: [Errno 2] No such file or
directory: 'git'"` [M, `evidence/h_refine/h040.json`, `h0267.json`, `evidence/box_sweep/lat*.json`]. It
is replaced by a three-layer resolver that costs no subprocess, no shell and no network, and returns a
**pair** `(rev, source)`: `env` (`EMFIT_GIT_REV`, 40/64 hex, optional `-dirty`) → `head` (`.git/HEAD` via
loose `refs/…` or `packed-refs`, annotated `head-loose` / `head-packed` / `head-detached`) → `file`
(`.git/emfit_git_rev` or `EMFIT_GIT_REV_FILE`). Total failure keeps the old `unavailable:` convention but
names **every** failed layer in the one string (`unavailable:env …;head …;file …`); none of the three
layers needs a `git` binary, which is the actual repair. `meta` now carries `git_rev` **and**
`git_rev_source`.

Disclosed behaviour changes: the value is now the **full 40-hex** object name where the old code emitted
the **short** rev (on this host `.git/HEAD` = `ref: refs/heads/master` and
`.git/refs/heads/master` = `5af2756fb4e3fc19cdfd55e7daf42e49656a65b2`, so a new row records
`5af2756…65b2` where a host-side run of the old code recorded `5af2756`, and the frozen rows recorded no
rev at all); and `import subprocess` (line 89) is now **unused
and deliberately left in place**, because removing it would touch a third region of the file for a
cosmetic gain. Both are format/provenance notes, not numerical ones.

Success and failure paths were exercised against replica trees in a throwaway process [M]: env 40-hex,
env 64-hex, env `<40>-dirty`, invalid env (falls through), `head-loose`, `head-packed` (nested ref,
comment line, `^` peeled line, unrelated ref), `head-detached`, `.git/emfit_git_rev`,
`EMFIT_GIT_REV_FILE`, no `.git` anywhere, and a corrupt `.git/HEAD`. Nine successes, two
three-reason `unavailable` strings, no `None`.

### 1.2 Task C — the graded basis is emitted, the superseded one is labelled

The row emitted `beta_model` = `emfit.microstrip.Microstrip.beta`, the **quasi-static** quantity that is
not the graded reference anywhere in this series. It is now emitted as `beta_quasistatic_retired` with
the **value unchanged**, next to a `beta_model_basis` prose field (quasi-static; superseded per
`decisions.md` 146/148(b); retained for continuity, not graded); and a new `beta_hj_kj_graded` field
emits `d585_modal.hammerstad_beta(f_hz, W=w, H=1.6e-3, eps_r=4.4)['beta']` at the same realised tone the
row banks as `f_hz`.

**Recompute, not reuse**, because there was nothing in scope to reuse: the ladder only reaches
`dm.section` / `dm.boxes` / `dm.eps_fun` (source 362/372/373) and never calls `dm.hammerstad_beta`. It
uses the module's own constants (`H_SUB = 1.6e-3`, `ER = 4.4`, identical to the pinned `H=1.6e-3,
eps_r=4.4`) plus one deliberate keyword, `verbose=False`, which gates only a print
(`tools/d585_modal.py` 124–138); the value is bit-identical either way [M]:
`hammerstad_beta(10.0096e9, W=0.8e-3, H=1.6e-3, eps_r=4.4)['beta']` = `377.343366741485`.

**The dropped key has no reader** [M, grep this dispatch]: no `["beta_model"]` and no
`.get("beta_model")` anywhere in `tools/`, `emfit/`, `docs/`, `evidence/`, `examples/`, `tests/`. Only
writers, the same-named object **attribute** (`emfit/demos.py` 240/315, `emfit/studies.py`
1604/1665/3034/3297/3388/4298–4302/4616, untouched), one prose mention
(`docs/design/box_sweep_preregistration.md` 102–103) and the nine historical JSON artefacts that carry
the key and are left untouched. The console text is unchanged (`beta_model` local and the `HJ_model=`
print at source 727/852 were not edited), and the rung-A emitted value stays `373.2885327645` —
value-preserving, not a repoint.

## 2. Hashes, before and after [M, `sha256sum` in this dispatch]

| file | at freeze (§13) | after this dispatch's edit (`cleanups-cd-2026-10-31`) | delta |
|---|---|---|---|
| `tools/host_ladder.py` | `1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` (**1106 lines**) | `519365eb4623bd6a1456258565d23dea5aba94af464d02d4d2f8e8752910d57c` (**1261 lines**) | **+155 lines, exactly two regions** |
| `tools/d585_modal.py` | `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6` (676 lines) | `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6` (676 lines) | **UNCHANGED** |
| `emfit/studies.py` | `578650bc59b1dbaa09832ec3dde2c0058fa69e0dcee56c2e8a4cc7ff37e802ac` (5166 lines) | `578650bc59b1dbaa09832ec3dde2c0058fa69e0dcee56c2e8a4cc7ff37e802ac` (5166 lines) | **UNCHANGED** |

The three pre-edit hashes were re-measured **before any edit** and matched §13 exactly (1106 / 676 /
5166 lines). Post-edit [M]: `python3 -m py_compile tools/host_ladder.py` → OK;
`python3 tools/host_ladder.py --help` → exit 0 with a **byte-identical** 75-line help text (the 16-line
flag list — 15 `add_argument` calls plus argparse's own `-h`; `diff` before vs after **empty**);
`git status` against `5af2756` shows **only** ` M tools/host_ladder.py`. Python/numpy/scipy of record are
unchanged: 3.12.15 / 2.5.4 / 1.18.1.

## 3. The clause that actually has to be argued: §9 G3

`strip_width` §12 needed only a re-pinned table. Here the pin **is** a guard, so it is set out with every
word kept (only the two hash literals elided), so that nothing is read into it that it does not say:

> **G3 same instrument** — `tools/host_ladder.py` sha256 must still be
> `1cd1a3ee…abeb9` and `tools/d585_modal.py` `8ba8e2a8…d53a6`. If either moved, the third rung is not
> on the same instrument as the first two and the three-rung sequence is not gradeable.

Taken as a literal string comparison, G3 has **moved**, and this erratum does not pretend otherwise: the
letter of G3 is superseded, not satisfied. What is argued is the object G3 protects.

- **What G3 is for.** It is an identity guard on the *instrument* that produced rungs A and B, so that a
  third rung is not silently collected on a different one. The hash is the *evidence* of identity, not
  the identity itself.
- **What the instrument is.** The graded quantity of `h_refine` §4 — and of this erratum's §6 — is the
  FDTD row's `beta_fdtd` / `beta_eig` graded against `hammerstad_beta`. The reference function, the
  solver call, the geometry law, the material stack, the tone record and the reporter all live in the
  byte-identical pair `tools/d585_modal.py` + `emfit/studies.py`, and in the untouched regions of
  `tools/host_ladder.py`. The diff is five find/replace blocks in two regions, both **outside** the
  numerical path: `--help` byte-identical, `py_compile` clean, console text byte-identical, and the
  solver region not opened.
- **Why this is prospective, not a re-reading of collected data.** No `h = 0.2` row exists. Rungs A and
  B were collected under `1cd1a3ee…`; this erratum is issued **before** rung C is launched, so the
  amendment binds the whole three-rung sequence rather than retro-fitting one rung. No already-frozen
  number is re-graded, and none is claimed to have been produced on the amended file.
- **The amendment, stated as a replacement guard.** G3 stands, with the `tools/host_ladder.py` pin
  replaced by `519365eb…0d57c` (1261 lines) and the `tools/d585_modal.py` pin left at `8ba8e2a8…d53a6`.
  If **either** file moves again before rung C runs, the third rung is not on the same instrument and
  the sequence is not gradeable — the guard's force is unchanged, only its constant.

**The alternative reading is real and is not defeated here.** A reader may hold that G3 admits no
amendment at all, in which case rung C is ungradeable and the record stays at two rungs with the third
"not measured, gate tripped". That reading is defensible from the frozen text, and it is recorded rather
than argued away: **it is this erratum's own judgement** — that a metadata-only diff restores G3's object
— and not something the frozen PREREG grants. Any rung-C row published later must cite this erratum by
name so that the judgement is visible in the graded record.

## 4. Clause by clause

- **§6 (verdict rule).** `h_refine` PREREG §4 applied unchanged to three rungs: monotone fall with total
  `>= 0.22 pp` → DISCRETISATION IMPLICATED; `< 0.22 pp` → NOT THE EXPLANATION; otherwise INCONCLUSIVE.
  **Untouched.** The two-rung INCONCLUSIVE stands as the verdict of that record; the supersession rule is
  unedited.
- **§9 G1 physics untouched.** G1 names its own objects — "the §4 verdict rule, `Delta_min`, the
  `0.22 pp` threshold, the graded reference and its `1e-6` tolerance". **None of the five moved**: no
  threshold, no floor, no reference, no tolerance was edited, re-derived or re-worded, and G1's
  invalidation trigger ("any edit to them voids this file") is not triggered by this erratum.
- **§9 G2 trip clause.** `wall_fdtd_s > 1400`, `peak_rss_mb > 4000`, "not measured, gate tripped",
  "never extrapolated", no retry inside this dispatch — **untouched**. The new per-row evaluation is
  closed-form and allocates nothing on the FDTD path; it cannot perturb a ~1400 s-class arm.
- **§9 G3.** Amended, as argued in §3.
- **§9 G4 reference reproduction.** `hammerstad_beta` must reproduce the frozen pin to `1e-6` relative at
  rung C's realised tone, checked against the pinned *function* rather than a memorised number —
  **untouched, and now easier to discharge**, because the function's module is byte-identical and the row
  emits the reference the check is run against.
- **§9 G5 completeness.** Exit `0`, `meta.status == 'ok'`, `meta.abort_reason is None`, cells within
  `5 %` of the `3.27 M` projection — **untouched**.
- **§9 G6 one-shot.** Exactly one `h = 0.2` run authorised — **untouched, and not exercised**: this
  erratum performs no run and grants no retry.
- **§10 amended clause table.** `wall_fdtd_s > 1400` (AMENDED), `peak_rss_mb > 4000` (unchanged),
  pricing basis (unchanged), on-trip behaviour (unchanged), verdict rule / `Delta_min = 0.0734 pp` /
  `3*Delta_min = 0.22 pp` (unchanged) — **all five rows hold exactly as frozen**. This erratum amends
  §13's hashes only; the §10 amendment remains §10's.
- **§13 freeze declaration.** Superseded by the table in §2 above, as §13 itself directs.

Geometry, FDTD numerics, the graded reference, `Delta_min`, `3*Delta_min`, the `1e-6` tolerance and every
§4/§6 verdict clause are untouched. **No numerical path was touched — that is a measurement, not an
intention** (§2's checks: two regions, five blocks, `--help` diff empty, `d585_modal.py` and
`studies.py` byte-identical).

## 5. What this erratum does not establish

- It does not make rung C runnable, affordable or authorised. The gate, the pricing basis and the
  one-shot grant are exactly as the PREREG above left them; the earlier `1882 s` naive `h^-4` pricing
  still trips and is still declared rather than papered over.
- It does not claim any row was produced on the amended file, and it does not re-grade rungs A or B.
- It does not resolve the G3 reading in §3 in favour of amendment; that is a stated judgement with its
  alternative on the record.
- It does not claim the new `git_rev` was exercised on the container of record: the container available
  here mounts `/workspace/.git` as an empty directory, so the in-container real-path call reaches only
  the failure layer (`unavailable:…`). The host success path is proven on a replica tree carrying the
  host's real `.git`/`HEAD` content [M].
- It does not restore `beta_model` to any reader (none existed) and leaves the nine historical artefacts
  carrying the key untouched; nor does it make the new full-40-hex `git_rev` string-comparable with the
  short revs in the frozen rows.
- It does not touch `decisions.md`: any decisions text remains for Agent A to merge (standing rule 2).

## 6. Recovering the pre-edit file

`git show 5af2756:tools/host_ladder.py` reproduces `1cd1a3ee…abeb9` (1106 lines) exactly, and
`git diff 5af2756 -- tools/host_ladder.py` is the whole edit — so no reader has to trust this document.
