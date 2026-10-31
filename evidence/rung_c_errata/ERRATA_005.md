# ERRATA 005 — the instrument moved a fourth time, and it is the first link in the chain with an executed check behind it

Marks: **[M]** measured against an artefact that exists in this tree (a JSON, a hash, a line count, a grep result);
**[L]** read from a named file and cited there; **[R]** relayed — an owner assertion or an out-of-tree number
carried in with no artefact behind it, marked and **not graded**.

Scope. This is an append-only erratum. It amends nothing in place: `evidence/rung_c_errata/PREREG.md`,
`evidence/h_refine/PREREG.md` and `evidence/strip_width/PREREG.md` are **untouched**, no gate is re-priced,
no historical row is re-graded, no number is moved, and **no run is banked** for it. It records four things
about `tools/host_ladder.py` as it now stands in the working tree: **(A)** the chain acquired a **fourth**
link, and this time the pin is git-computable rather than only re-hashable; **(B)** what that re-pin does and
does not vouch for; **(C)** the "parameter-only" claim restated as a predicate that can be checked, together
with the checks that were run against it; **(D)** the limits of all of it — including one artefact that no
longer exists and the fields that died with it.

---

## A. The fourth link

- **A.1 The new pin.** `tools/host_ladder.py` in the working tree is **70026 bytes / 1403 lines** [M], git blob
  id **`ed24416300fc9b6b356023930c466fe2b6c0fda4`** [M] and sha256
  **`a76b645acf7a7a4ba1d929fa470002d6e1d04b86606c50daa37b563ecdc8a8bc`** [M].
- **A.2 A new kind of value for this chain, and the one that can be checked by git.** The prior links are
  **not** all quoted at 64 hex. In `ERRATA_004.md` exactly **one** of them carries a full-length rendering —
  link 1, `1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` at L68 [L] — while the §B.2
  table at L76-78 records all three links only as a 12-hex prefix + `…` + a 5-hex suffix (`1cd1a3ee…abeb9` /
  1106 L, `519365eb…0d57c` / 1261 L, `0d719197…0c9b` / 1395 L) [L]. On that record this is the **better-pinned
  of the four**, not merely the newest: its sha256 above is given at the same full 64 hex as the one
  full-length prior rendering **and** it carries the 40-hex blob id — the form
  `git rev-parse HEAD:tools/host_ladder.py` returns after commit — so it is checkable at both lengths, by
  re-hash and by git, while the two abbreviated priors are checkable, in that table, only by prefix (§A.2b)
  [M].
- **A.2b Link 3's abbreviation, checked against the tree rather than assumed.** The first draft of this
  section was to record link 3 as a pin "in name only" — the same defect class as the 37-character
  `git_rev` in `ERRATA_004.md` §A.6, except unrecoverable. The search refutes that, so it is not recorded.
  `grep -rn "0d719197" evidence/` returns **14 hits over 10 lines in 8 files**; a python `os.walk` over
  `evidence/` counting the substring directly agrees (14 lines, 14 occurrences); and the regex
  `0d719197[0-9a-f]{8,}` returns **six full 64-hex renderings**, every one the same value,
  `0d7191973fe7babf53463205a1da968befcca205e725027ed83dc0267b190c9b`: `rung_c/SUMMARY.md` L271,
  `strip_width/ERRATA_002.md` L114, `strip_width/_make_EIG_strip_width.py` L151,
  `strip_width/EIG_strip_width.json` L7 (`host_ladder_sha256`), and `strip_width/ERRATA_003.md` L70 and L77
  [M]. L78 of `ERRATA_004.md` abridges that to `0d719197…0c9b`; the tree does not. So link 3 **is**
  recomputable, and a transcription slip at L78 would be catchable against five independent renderings of
  the same string — the opposite of §A.6, where the full form had to be located before the slip could be
  seen at all. The defect is a display convention in `ERRATA_004.md`, it belongs to link 3 and not link 4,
  and nothing here needs repair because no value is missing.
- **A.3 Method, and a cross-check that does not depend on it.** The blob id is
  `sha1(b"blob " + str(len(data)) + b"\0" + data)` over the file's 70026 bytes [M]. Git computed the same
  post-image for itself: the diff for this file prints `index 2652472..ed24416 100644` [M], whose right-hand
  abbreviation is the prefix of the value above. Two independent computations, one convention.
- **A.4 The chain as it now reads.**
  `1cd1a3ee…abeb9` (1106 L) → `519365eb…0d57c` (1261 L) → `0d719197…0c9b` (1395 L, abridged exactly as
  `ERRATA_004.md` L78 has it; full value in §A.2b) → **`a76b645a…a8bc` / blob `ed24416…0fda4`
  (1403 L, 70026 B)** [M for link 4; links 1–3 read from the record].
- **A.5 The step this erratum covers is `1395 → 1403`**, +8 net lines, diff **+11 / −3 over four hunks**
  whose spans are 425, 476, 810 and 1179 [M]. It is the fourth link, and it is the one this document is
  filed against — not link 3, which §B.2 of `ERRATA_004.md` and `decisions.md` §156(c) already carry.

## B. What the re-pin vouches for

- **B.1 The moved region is named, not implied.** Four hunks: the `run_fdtd` docstring/signature at 425 (the
  `n_stations: int = studies.MS_N_STATIONS` keyword, L427-429), the same function's use of it at 476 (L480,
  formerly L479), the single call site at 810 (L814), and the argparse block at 1179 (the `--stations` flag,
  L1183-1189, `type=int`, `default=studies.MS_N_STATIONS`, `metavar="N"`, with a two-line "PARAMETER ONLY"
  comment) [L/M]. Nothing else in the file moved: the diff has four hunks and this is all of them [M].
- **B.2 The neighbours are byte-identical, and here that is a measurement rather than an ordering
  argument.** `emfit/studies.py` sha256 is
  `578650bc59b1dbaa09832ec3dde2c0058fa69e0dcee56c2e8a4cc7ff37e802ac` [M], **identical to the pin quoted for
  it in `ERRATA_004.md` §12/§13** [L], so the file that owns `MS_N_STATIONS = 9` did not move while
  `host_ladder.py` did. `tools/d585_modal.py` is `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6`
  [M]. The instrument's *dependencies* are pinned while its *surface* changes — which is the whole claim
  §C makes, and it is why the sibling hashes are quoted here at all.
- **B.3 It compiles.** `python3 -m py_compile tools/host_ladder.py` exits 0 [M]. That is the check whose
  *absence* was recorded against the `1261 → 1395` step in `ERRATA_004.md` §B.2 and in the
  `session-close-gen6-2026-10-31` dispatch row; it is present here, for this link only. The label on link 3
  **stays as written** — a check performed on link 4 does not retroactively supply one for link 3.
- **B.4 What it does not vouch for.** A pin is not a warrant for a number. Nothing in §A or §B says the
  ladder's output is correct, that `beta`, the gap or any rung is what it was, or that the fourth link is the
  instrument the banked `evidence/rung_c/h020.json` was produced by — that artefact belongs to **link 3**
  (`0d719197…0c9b`, 1395 L; full 64-hex value in §A.2b) [L]. G3's letter, which `ERRATA_004.md` §B.2 records
  as **FAIL a second time** for links 2 and 3, is not repaired by this document; a fourth link with a better
  pin is a fourth link.

## C. "Parameter-only", restated as something that can be checked

- **C.1 The claim.** The edit adds a *parameter*, not a *behaviour*: `n_stations` becomes settable from the
  command line, and its default is the constant it already had, so every existing invocation resolves to the
  same value it resolved to before.
- **C.2 Four checks against that claim, all executed** [M]:
  (i) `--help` exits 0 and shows `--stations N`;
  (ii) `parse_args([]).stations == studies.MS_N_STATIONS == 9` — the default path is the old constant;
  (iii) `parse_args(["--stations","13"]).stations == 13` — the flag is live and reaches the parser;
  (iv) `run_fdtd.__kwdefaults__["n_stations"] == 9` — the keyword's default is the constant too, so the
  library entry point is unchanged for any caller that does not pass it.
- **C.3 One full run of the *default* path** [M, from the captured stdout of the run — the JSON behind it no
  longer exists, see §D.4]: `python3 tools/host_ladder.py --h 0.4 --mem-ceiling-mb 2000 --json /tmp/smoke_pre_9st.json`
  exits **0** in **18 s** wall, prints `LADDER OK rungs=1 max_rel_gap=0.8946%`, and the written JSON carries
  `rungs[0]['n_stations'] == 9` among 62 rung keys, 6606 bytes. The value that reaches the solver is the value
  it always was — measured through the whole pipeline, not inferred from the parser.
- **C.4 What §C.3 does and does not establish.** It establishes the **default** path end to end at `9`
  stations. It does **not** establish that `13` or `18` stations runs: `--stations 13` was exercised against
  the *parser* only (§C.2(iii)), and no FDTD solve was performed at any value but `9`. So "parameter-only"
  is verified in the direction that matters for the existing record — nothing already banked changed
  meaning — and **unverified** in the direction the flag exists for.

## D. Limits

- **D.1 Nothing re-priced, nothing re-graded, no number moved.** No gate, threshold, verdict or grade is
  touched by this erratum, and no row in `docs/design/dispatch_log.md` is edited in place; the dispatch table
  gains one row and keeps every byte it had [M: 205 → 206 lines, one inserted line].
- **D.2 The banked artefact is not this link's.** `evidence/rung_c/h020.json` was produced by link 3
  (`0d719197…0c9b`, 1395 L). The fourth link post-dates it in `mtime` order but nothing in this document claims
  `h020.json` was produced by, or would reproduce under, the code now in the tree. That question is not posed
  here and is not answered here.
- **D.3 No `18`-station run is claimed, priced or implied.** The flag exists; the case it was built for has
  not been exercised, and this document says so rather than letting a live flag be read as a result.
- **D.4 One artefact no longer exists, and its fields are not reconstructed.** `/tmp/smoke_pre_9st.json` is
  gone: the execution environment that wrote it is ephemeral, and `ls` on the path fails [M]. The values that
  survive are the ones that reached the run's captured stdout — `n_stations 9`, `free_e 1262`, `n_dof 1691`,
  `beta_fdtd 389.0223`, `beta_eig 392.5025`, gap `+0.8946 %`, `t_splu 0.00 s`, `t_eigs 0.09 s`,
  `wall_eig 0.10 s`, `wall_fdtd 14.49 s`, residual `3.878e-14`, and the console label `HJ_model=373.2885`
  (JSON field `beta_hj_kj_graded`) [M, from the captured stdout of that run]. **Not available:
  `t_assembly_s` and `opinv_calls`** — no console line carried them. Recovering either requires re-running,
  which this dispatch's fence forbids, so they are recorded as **unavailable** rather than inferred from a
  neighbouring field or from a previous run.
- **D.5 An observation about the solver path, reported and not resolved.** `opinv_calls` is set from
  `op.calls` at L579 and L582 and banked at L1016 (`opinv_calls=int(rec["opinv_calls"])`) [L/M]; the file's
  own prose pins the solver as `scipy.sparse.linalg.eigs`, *"NOT eigsh: `M` is indefinite"* (L16, L23-24,
  L1340) [L]. A search for `solve_freedof`, `solve_dense` or `solve_modes` anywhere in `tools/host_ladder.py`
  returns **no match** [M] — so the ladder does not call the mode solver named in the chain's other documents;
  it runs a local `eigs` path of its own. Whether that is the same instrument by another route, or a second
  instrument, is **not settled here**, because settling it means opening the function behind `op` and
  re-deriving what it counts, which is a reading task for a document with a wider fence than this one.
