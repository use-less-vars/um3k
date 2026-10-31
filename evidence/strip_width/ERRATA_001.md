# Erratum 001 — `evidence/strip_width/`

**Append-only erratum to the freeze declaration.** This file amends `evidence/strip_width/PREREG.md`
§12, frozen **2026-10-31T01:53Z** and committed as **`5af2756`**. `PREREG.md` is not modified — not one
byte — and nothing here restates, softens or re-opens a clause it froze. It discharges §12's own
instruction: *"A future edit to any of the three files above voids the freeze and requires an
append-only erratum, not a silent re-run."*

Issued under dispatch `cleanups-cd-2026-10-31` (tasks C and D).

**No FDTD run is performed, graded, re-graded, re-priced or extrapolated by this erratum.** No arm of
this directory exists; none is claimed. `meta.status`, every `beta_fdtd`, every `beta_eig` and the
rung-A tone `10.19862621457275 GHz` are exactly as §1/§3 froze them.

## 1. What changed, and why

Two edits, both to `tools/host_ladder.py`, both **metadata-only**.

### 1.1 Task D — `git_rev()` no longer shells out

The old body was one `subprocess.run(["git", "rev-parse", "--short", "HEAD"], …)` — the short HEAD
on success, and on failure the single string `unavailable: <ExcType>: <message>`. In the **container of
record** there is no `git` binary at all, so the field never once carried a revision: **all nine frozen
rows record the same non-answer**, `"git_rev": "unavailable: FileNotFoundError: [Errno 2] No such file
or directory: 'git'"` [M, `evidence/h_refine/h040.json`, `evidence/h_refine/h0267.json`,
`evidence/box_sweep/lat*.json`]. The old code was honest but inert — one reason, no route to a rev where
`git` does not exist, and a `timeout=10` that could only ever fail. It is replaced by a resolver that
costs no subprocess, no shell and no network, reads in three layers, and returns a **pair**
`(rev, source)` so the record says *where* the rev came from:

1. `env` — `EMFIT_GIT_REV`, accepted only if it is 40/64 hex, optionally suffixed `-dirty`;
2. `head` — `.git/HEAD`, resolved through loose `refs/…` or `packed-refs`, annotated
   `head-loose` / `head-packed` / `head-detached`;
3. `file` — `.git/emfit_git_rev` or the path in `EMFIT_GIT_REV_FILE`.

Total failure keeps the old `unavailable:` convention, so no reader has to learn a second format, but now
**every** layer that failed is named in the one string (`unavailable:env …;head …;file …`) — and none of
the three layers needs a `git` binary, which is the actual repair. The row's `meta` now carries
`git_rev` **and** `git_rev_source`.

Two behaviours changed and are disclosed rather than buried:

- The value is now the **full 40-hex** object name; the old code emitted the **short** rev. On this
  host, `git_read` reports `HEAD` = `ref: refs/heads/master` and `.git/refs/heads/master` =
  `5af2756fb4e3fc19cdfd55e7daf42e49656a65b2`, so a new row records `5af2756…65b2` where a host-side run
  of the old code recorded `5af2756` (and a container-side run recorded no rev at all). Same commit,
  different string length — new `git_rev` values are **not string-comparable** with earlier ones.
- `import subprocess` (line 89) is now **unused** and was deliberately **left in place**: removing it
  would mean touching a third region of the file for a cosmetic gain. Recorded here so the next reader
  of the diff does not read it as a leftover edit in progress.

The resolver was exercised in a throwaway process against replica trees (monkeypatched
`host_ladder.__file__`) [M, this dispatch]: env 40-hex, env 64-hex, env `<40>-dirty`, env invalid
(falls through), `head-loose`, `head-packed` (nested ref + comment line + `^` peeled line + unrelated
ref), `head-detached` (raw 40-hex), `.git/emfit_git_rev`, `EMFIT_GIT_REV_FILE`, no `.git` anywhere
(three-reason `unavailable` string), and a deliberately corrupt `.git/HEAD` (three-reason `unavailable`
string naming the offending content). Nine success paths and two failure paths, no `None`.

### 1.2 Task C — the graded basis is emitted, the superseded one is labelled

The row previously emitted `beta_model` = `emfit.microstrip.Microstrip.beta`. §3 states in as many
words that this quantity *is not used anywhere in this dispatch*: it is quasi-static and is the
superseded basis (`decisions.md` 146/148(b)). A key named `beta_model` sitting in a strip-width JSON
is an invitation to the exact misreading §3 forbids.

- `beta_model` is **renamed** to `beta_quasistatic_retired`, **value unchanged**; a new
  `beta_model_basis` field carries the prose reason (quasi-static; superseded per `decisions.md`
  146/148(b); retained for continuity, not graded).
- A new `beta_hj_kj_graded` field now emits the §3 reference itself,
  `d585_modal.hammerstad_beta(f_hz, W=w, H=1.6e-3, eps_r=4.4)['beta']`, evaluated at **the same
  realised tone the row banks as `f_hz`** (`float(gy["f"])`), so the row is self-describing and §10 G4
  becomes checkable from the row alone.

**Reuse versus recompute — recomputed, and why.** The ladder never calls `dm.hammerstad_beta`; it only
reaches `dm.section` / `dm.boxes` / `dm.eps_fun` (source 362/372/373). There was therefore **no
in-scope value to reuse**. The call uses the constants the module already carries (`H_SUB = 1.6e-3`,
`ER = 4.4`, identical to §3's `H=1.6e-3, eps_r=4.4`) with **one deliberate addition, `verbose=False`**;
`verbose` gates only a print (`tools/d585_modal.py` 124–138) and the value is bit-identical with and
without it [M]: `hammerstad_beta(10.0096e9, W=0.8e-3, H=1.6e-3, eps_r=4.4)['beta']` =
`377.343366741485` both ways.

**The dropped key has no reader.** [M, grep this dispatch] there is no `["beta_model"]` and no
`.get("beta_model")` anywhere in `tools/`, `emfit/`, `docs/`, `evidence/`, `examples/`, `tests/`. The
key's only occurrences are writers and the object **attribute** of the same name
(`emfit/demos.py` 240/315, `emfit/studies.py` 1604/1665/3034/3297/3388/4298–4302/4616 — untouched),
one prose mention (`docs/design/box_sweep_preregistration.md` 102–103), and the nine historical JSON
artefacts (`evidence/h_refine/h040.json`, `h0267.json`, `evidence/box_sweep/lat*.json`) that still
carry it and are left untouched. Renaming a key with no reader cannot move a number.

The console text is unchanged: the local variable `beta_model` and the `HJ_model=` print
(source 727 and 852) were **not** edited, so stdout of a new arm remains line-for-line comparable with
the two frozen rows. The rung-A **emitted** value is still `373.2885327645` — value-preserving, not a
repoint to the new field.

## 2. Hashes, before and after [M, `sha256sum` in this dispatch]

| file | at freeze (§12) | after this dispatch's edit (`cleanups-cd-2026-10-31`) | delta |
|---|---|---|---|
| `tools/host_ladder.py` | `1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` (**1106 lines**) | `519365eb4623bd6a1456258565d23dea5aba94af464d02d4d2f8e8752910d57c` (**1261 lines**) | **+155 lines, exactly two regions** |
| `tools/d585_modal.py` | `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6` (676 lines) | `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6` (676 lines) | **UNCHANGED** |
| `emfit/studies.py` | `578650bc59b1dbaa09832ec3dde2c0058fa69e0dcee56c2e8a4cc7ff37e802ac` (5166 lines) | `578650bc59b1dbaa09832ec3dde2c0058fa69e0dcee56c2e8a4cc7ff37e802ac` (5166 lines) | **UNCHANGED** |

The three pre-edit hashes were re-measured before any edit and matched §12 **exactly** (1106 / 676 /
5166 lines) [M]. After the edit, `python3 -m py_compile tools/host_ladder.py` → OK, and
`python3 tools/host_ladder.py --help` → exit 0 with a **byte-identical** 75-line help text (the 16-line
flag list, 15 `add_argument` calls plus argparse's own `-h`; `diff` before vs after **empty**). The
FDTD solver, the geometry law, the material stack, the tone record and the reporter were not touched.

**The function §3 grades on did not move.** `hammerstad_beta` lives in `tools/d585_modal.py`, which is
byte-identical to the freeze. Only the *caller* of that function changed, in the ladder, and only to
*record* its return value.

## 3. Why the freeze is not voided — clause by clause

§12's sentence is that an edit "voids the freeze **and requires an append-only erratum**". This file is
that erratum; the mechanism §12 prescribes is being followed, not circumvented. On the substance:

- **§3 (the graded reference).** Frozen as `tools/d585_modal.hammerstad_beta(f_arm, W=W_arm,
  H=1.6e-3, eps_r=4.4)['beta']` at each arm's own realised tone, with both inputs recorded, and with
  `W08` returning `384.7489756771` against the frozen pin `384.7489672644` to `2.2e-8`. **Unchanged**:
  the module holding that function is byte-identical, and the new `beta_hj_kj_graded` field calls *that
  same function* at *that same tone* and *that same W*. The reference is not merely preserved, it is now
  emitted per row.
- **§4 / §4.1 / §4.2 (readings and criteria).** `d_W`, `d_EIG`, `rel_gap`, the Q1 sequence criterion and
  the Q2 `|d_wide − d_narrow| > 0.2202 pp` test read `beta_fdtd` / `beta_eig` / `ref` and nothing else.
  No field they read changed, and the one field that disappeared (`beta_model`) has no reader (§1.2).
- **§5 (per-arm gate `900 s` / `4000 MB`).** Unchanged. The new work is one closed-form evaluation of a
  function the per-row cost already includes; it allocates nothing on the FDTD path and cannot perturb a
  `232.0 s` / `388.4 MB` arm against a `900 s` / `4000 MB` ceiling.
- **§7 (`Delta_min = 0.0734 pp`, `3*Delta_min = 0.2202 pp`).** Not re-derived, not touched, circularity
  disclosure stands as written.
- **§8 (three-outcome table).** `CONFIRMED` / `REFUTED` / `INCONCLUSIVE` and the two Q2 rows are
  byte-identical; no criterion was reworded and no threshold moved.
- **§10 G1–G7.** `G1` completeness, `G2` W08 reproduction to `1e-9`, `G3` tone record
  (`meta.tone_f_actual_ghz`, `meta.tone_detune_pct`), `G5` resources, `G6` cell law, `G7` mode identity
  (`b_over_a`, `alpha_fdtd_db_per_mm`) are numerical and untouched. `G4` reference reachability is
  **strengthened**, not relaxed: the row now carries the reference it must be reachable for.
- **§12 freeze table.** Superseded by the table in §2 above, as §12 itself directs.

"It touched only metadata" is a claim, so it is stated as a checkable one: five find/replace blocks, two
regions, `--help` diff empty, `py_compile` clean, `d585_modal.py` and `studies.py` byte-identical,
`git status` showing **only** ` M tools/host_ladder.py` against `5af2756`. **No numerical path was
touched — that is true, not merely intended.**

## 4. What this erratum does not establish

- It does not re-open, re-grade or strengthen any frozen verdict: `box_sweep` **INCONCLUSIVE** and
  `h_refine` **INCONCLUSIVE** stand as published, and no row of this directory is graded.
- It does not claim the new `git_rev` was exercised on the container of record. The container available
  to this dispatch mounts `/workspace/.git` as an **empty directory**, so the in-container real-path call
  reaches only the failure layer (`unavailable:…`). The host success path is proven on a replica tree
  carrying the host's real `.git`/`HEAD` content [M], not on the run container. A future arm's `git_rev`
  field should be read with that in mind until it is seen in situ.
- It does not restore `beta_model` for any reader — none existed — and it leaves the nine historical
  artefacts carrying the key **untouched** (append-only). A reader diffing an old row against a new one
  will see `beta_model` → `beta_quasistatic_retired`; the value is identical.
- It does not make the new rows' `git_rev` comparable with the frozen rows' short rev (§1.1).

## 5. Recovering the pre-edit file

The frozen, pre-edit file remains recoverable, so no reader has to trust this document:
`git show 5af2756:tools/host_ladder.py` reproduces `1cd1a3ee…abeb9` (1106 lines) exactly, and
`git diff 5af2756 -- tools/host_ladder.py` is the whole edit.
