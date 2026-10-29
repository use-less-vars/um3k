# Dispatch 52b — Acceptance criteria (verbatim), with collision report

**Written:** first action of dispatch 52b, before any other artefact.
**Status:** front-most fence of the dispatch. Nothing below is negotiable.
**Coexists with:** `docs/design/d52_acceptance.md` (dispatch 52, first pass).

---

## 0. Why this file is not `docs/design/d52_acceptance.md`

The brief first action names `docs/design/d52_acceptance.md`. That file already
exists and is committed at `ba1f8f0`. It records the **first pass** of dispatch 52:
there, Task 1 was an acceptance document, Task 2 a criteria rewrite, Task 3 a
pairing-rule pre-registration, Task 4 an adversarial review.

The revised brief restructures the dispatch. Task 1 is now a new artefact
(`docs/design/soundness.md`); Task 2 is a rewrite of an existing table; Task 3 is a
header addition to a document that already exists; Task 4 is the same review under a
sharper instruction. Writing the new criteria into the old file would overwrite the
record of the first pass, and the brief own rule is *the artifact wins — report
before editing*. This file is therefore new. `d52_acceptance.md` is left
byte-identical, at sha256
`630dc94000b1f7c2751583163d62a43b77054dc36e03b80cf65b3e4a823635e7`.

### Reconnaissance results, taken before writing this file [VERIFIED this session]

| fact | value |
|---|---|
| `.md` files in `docs/design` | 41 |
| total lines in `docs/design` | 15 334 |
| `docs/design/soundness.md` | ABSENT |
| C++ criterion table location | `docs/design/cpp_solver_arch.md` section 5, registered at line 160 |
| the table itself | four rows, lines 247-248 |
| pre-existing tier vocabulary | none: zero hits for tier or evidence grade as concepts |

---

## 1. Fences (verbatim)

> **Fences:** no gate run in this dispatch. No `emfit/` edits. Do not modify the
> frozen A-1.5 module or `preservation_gate.py`. `decisions.md` append-only.
> **Task 4 ends the dispatch.**

Additionally, from the brief standing rule: **no line numbers in the brief by
design**, and every number carries a provenance tag — `[VERIFIED this session]`,
`[RELAYED]`, `[USER]`. Untagged means `RELAYED`.

---

## 2. Task 1 — `docs/design/soundness.md` (verbatim)

> - Consequence level **MODERATE**, with the two things it explicitly does not claim
>   (safety-critical fitness; replacement for build-and-measure) written out.
> - The tier vocabulary, defined for this project — not borrowed wholesale from a
>   paper. **Do not cite an external tier scheme as authority unless you verify it
>   this session**; if unverified, say the vocabulary is ours and name the general
>   tradition it follows.
> - The claim ledger, with at minimum the four claims sketched above, plus every
>   claim currently asserted anywhere in `docs/design/` that has no tier. **Sweep the
>   directory** — an incomplete ledger is worse than none, because it implies the
>   unlisted claims are settled.
> - **Promotion requirement on every row.** This is the clause that lets the project
>   graduate to higher consequence levels later.
> - The withdrawn section, seeded with the three void clauses from dispatches 50-51.
> - The "where I think this is wrong" section, written by me, for the next engineer.

---

## 3. Task 2 — Re-scope the C++ criterion table (verbatim)

> Rewrite row four and its neighbours to reference ledger IDs rather than carry their
> own prose. A criterion that cites `C3 (E3, eps_r<=3.5)` is citable and honest; one
> that says physics invariants is neither. Where a row has no claim behind it, mark it
> `UNMEASURED — no ledger entry`.

---

## 4. Task 3 — Pairing rule pre-registration, scoped by the ledger (verbatim)

> As previously specified — derive the per-mesh tolerance from the scheme order rather
> than choosing a constant, with a mandatory feasibility argument, and a clause for a
> level-1 pairing stop distinct from an annihilation stop. **Now additionally:** state
> in its header which ledger claims it will promote, which it could demote, and what
> happens to `C1` if it fails.

Note: the document this task amends already exists at revision 2. The brief
as-previously-specified clause is therefore already satisfied or already disputed
on the record — see section 7.2. This task reduces to the header addition plus an
audit of the existing adversarial table against the five attacks named in Task 4.

---

## 5. Task 4 — Adversarial review, then freeze (verbatim)

> The new standing step. One instruction: **construct the input that makes this gate
> vacuously pass, and the input that makes it vacuously fail.** At minimum: zero
> physical modes; correct count with one substituted; coarsest mesh only;
> annihilation at L1 only; contrast high enough that discretization exceeds the
> tolerance at every level. Record attacks and outcomes as a table in the
> pre-registration, then revise. **Do not run.** Report what the review changed.

---

## 6. Close-out (verbatim)

> **Close-out:** commits, the adversarial table, every disagreement with this brief,
> and — explicitly — whether the ledger sweep found claims asserted in
> `docs/design/` that nobody had tiered.

---

## 7. Reconnaissance findings that change how the tasks must be read

These are reported before the work they constrain, not after.

### 7.1 The brief tier tokens collide with live gate-clause ids

The brief names the tiers `T1`-`T5`. This repo already uses `T1`-`T5` as a
**different** namespace: the correlation-gate clause family `T1_stab`, `T2_agree`,
`T3_scale`, `T4_amp`, `T5_ez_corr`, `T5_fringe_excess`, registered at
`decisions.md:7129` and live in `docs/design/m3c_gate_v2.md`. Those are not dormant:
`T4_amp` is a recorded **FAIL** and `T2_agree` is currently scored against a 4.52 %
gap at a 0.5 % tolerance.

The failure this dispatch exists to prevent is a specific that *reads* as verified
while being ambiguous. Claim `C1` is `T2` printed two pages from `T2_agree` is
4.52 % against a 0.5 % tolerance is exactly that: two meanings for one token,
neither of them wrong on its own page.

**Resolution.** The tier vocabulary in `soundness.md` uses `E1`-`E5` (evidence level)
and `X` (withdrawn). The mapping to the brief letters is recorded in the document
so nothing is lost:

| brief | document | meaning |
|---|---|---|
| T1 | **E1** | Proven — mathematical argument, no numerical dependence |
| T2 | **E2** | Verified — measured vs independent analytic reference, convergence rate demonstrated, >=3 resolutions |
| T3 | **E3** | Characterised — measured vs reference with incomplete convergence evidence, OR heuristic with measured behaviour and no derivation |
| T4 | **E4** | Calibrated — agrees with external tool/measurement, no internal error analysis |
| T5 | **E5** | Asserted — believed, not measured. NOT CITABLE |
| X | **X** | Withdrawn |

This is a **deviation from the brief letter**, reported as such. It is not a
deviation from its purpose: the brief already requires the vocabulary to be defined
for this project, not borrowed wholesale, and a project that has spent `T1`-`T5` on
gate clauses cannot spend them again on tiers.

Claim ids stay as the brief sketches them, `C1`, `C2`, ..., because the collision there
is weaker: files are lower-case (`c1_spectrum.npz`, `c2b_preregistration.md`) and the
uppercase token is distinguishable. The rule that makes it safe is stated in
`soundness.md`: **`C<n>` is always written with the word claim adjacent on first
use in a section, and never bare next to a filename.**

### 7.2 Task 3 previously-specified is already disputed on the record

The brief asks for a per-mesh tolerance derived from the scheme order rather than
chosen as a constant. `pairing_rule_preregistration.md` section 3.1 (revision 2)
already **rejected** an h-dependent tolerance, on arithmetic rather than taste: any
tolerance that a scheme-order derivation could produce at level 1 is `~2e-2`, while
the datum the gate must not fail sits at `7.09799e-02`, i.e. `3.549 x 2e-2`. To pass,
such a tolerance must be inflated to at least `8.9e-2`, clearing by `1.25 x` — that is
a fit to the failing datum, not a derivation from the scheme.

That rejection stands on the record and is not silently reversed here. What Task 3
does deliver, and what the brief is actually reaching for, is already true of R3: the
tracking window is `6.0 x max(e_{o,k+1}, 1e-12)`, i.e. **per-level and derived from
the measured error at the adjacent level**, not a fixed constant applied at every
mesh. The one remaining constant, the multiplier `6.0`, is disclosed as a calibration
in section 4.1 and defended on the ground that it has never decided a verdict.

This is **disagreement 2** with the brief, reported before the edit rather than after.

### 7.3 Sweep the directory needs a stated scope cut

The brief warns that an incomplete ledger is worse than none, because it implies the
unlisted claims are settled. `docs/design` is 41 files and 15 334 lines, and a large
fraction of it is **historical dispatch record** — `d43b`-`d52` acceptance and results
documents, which report what a dispatch found, in past tense, each carrying its own
`[VERIFIED]` / `[RELAYED]` tags.

The cut taken is by **document role**, and it is stated explicitly in `soundness.md`
rather than left implicit:

- **In scope — standing documents**, whose claims are asserted as currently true:
  `core_contract.md`, `cpp_solver_arch.md`, `physics_invariant_layer.md`,
  `normalization_scheme.md`, `sparse_eigenmode.md`, `modalport_ownership.md`,
  `m3c_gate_v2.md`, `corr_ez_vv_threshold.md`, `zfree_shape.md`, `t4_amp_ratio.md`,
  `job_schema.md`, `visual_engine_arch.md`.
- **Out of scope — historical record**, which states nothing about the present and is
  already tiered by the per-claim `[VERIFIED]` / `[RELAYED]` convention:
  every `d4*_acceptance.md`, every `d4*_results.md`, `d52_acceptance.md`,
  `d52b_acceptance.md` (this file), and every `*_preregistration.md` (a
  pre-registration asserts what will happen, not what is).

That cut is a judgement, not a measurement, and `soundness.md` says so. If the
supervisor reads the boundary differently, the fix is to add files, not to rebuild.

---

## 8. What done means for this dispatch

1. `soundness.md` exists and its ledger has a row for every standing claim found by
   the sweep, each with tier, scope, dependencies, expiry trigger and promotion
   requirement.
2. `cpp_solver_arch.md` section 5 row four cites a ledger id or is marked
   `UNMEASURED — no ledger entry`.
3. `pairing_rule_preregistration.md` header names the claims it promotes, the claims
   it could demote, and the consequence for `C1` of its own failure — and its
   adversarial table is audited against the five named attacks.
4. `decisions.md` carries the dispatch record, appended, nothing above it altered.
5. One commit. Close-out states every disagreement with the brief, including the
   three pre-registered here: the tier rename (7.1), the standing rejection of the
   h-derived tolerance (7.2), and the sweep scope cut (7.3).

No gate run. No `emfit/` edits. No change to the frozen A-1.5 module or
`preservation_gate.py`.

---

### 7.4 The ledger is two files, not one

The sweep produced 143 rows and inlining them into `soundness.md` is the obvious move and
the wrong one. The ledger carries the claims that other documents cite — roughly fifteen of
them, each with scope, dependencies, expiry trigger and promotion requirement — and a
143-row working table in the middle of the document buries that citable set under its own
evidence. A reader who wants claim `C4` would page past 143 rows to reach it, which turns a
ledger into an archive with a preface.

The split taken [VERIFIED this session]:

- **`docs/design/soundness.md`** — the ledger of record. Every citable claim, tiered. This is
  the file `cpp_solver_arch.md` section 5 cites.
- **`docs/design/d52b_claim_inventory.md`** — the evidence base. All 143 rows verbatim, with
  the per-document tier counts computed from the rows rather than typed, and the limitations of
  the sweep stated at the top. Nothing in it is citable; it is what the ledger's tiers rest on.

Leaving the inventory in `.scratch/` is not the third option it looks like. `.scratch/` is
gitignored, so an inventory there is not evidence — it is a file on one machine that no reader
of the claim can consult. This is the same defect row `A32` records against `job_schema.md`:
the J1-J7 criteria are asserted to have been frozen before any artefact existed, and the
pre-registration that would show the ordering is in gitignored, unversioned `.scratch/`, so the
ordering is not independently checkable and the claim tiers E5 rather than E1. An artefact the
auditor cannot read does not support the claim it is offered for. Both files are committed, in
the same commit.

### 7.5 The tier tally was 144 rows and the files hold 143

Hand tallies taken during the sweep summed to 144 rows. The six sweep files hold 143: A 54,
B 14, rest 31, E 16, F 14, G 14, no duplicate ids.

The excess is one row, `C15`. The C section hit its 20-word row cap at `C14`, so `C15` was
written in a second `sparse_eigenmode.md` section appended after `m3c_gate_v2.md`. A tally that
counts the C range as `C01`-`C15` **and** counts the supplementary section as its own entry
counts `C15` twice. It is the only row in the sweep that can be counted twice, because it is
the only row sitting under a second heading for a document already closed: 14 + 16 + 1 = 31,
not 32.

The reconciled count is **E1 37, E2 0, E3 58, E4 3, E5 28, X 15, UNKNOWN 2; total 143**, and it
is recorded in `d52b_claim_inventory.md`, where it is computed from the committed rows. The
per-file counts are authoritative. The 144 is not restated anywhere in a committed artefact and
is used nowhere — in particular not in any count in `soundness.md`.

One second arithmetic fault fell out of the same recount and is worth recording, because it will
bite the next person who counts: the tier cell is not at a fixed field position. Five rows
(`A13`, `A23`, `G04`, `G06`, `G14`) carry an escaped pipe in the claim cell, so their tier sits
in the sixth pipe-delimited field; an `awk` on the fourth field reports `E3` 54 and `E5` 27
against the true 58 and 28, and a total of 138 against 143. The counts in the inventory take the
first cell that is exactly a tier token, whatever its position.
