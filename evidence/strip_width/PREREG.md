# Pre-registration: does the offset depend on how many cells the strip spans?

Frozen before any run in this directory (no JSON exists here at freeze time), 2026-10-31.
Append-only errata are the only later edits permitted. Provenance and hashes in §12.

Two questions are frozen here, and they are separate:

- **Q1 -- strip meshing.** At fixed `h = 0.4 mm`, does the graded offset per arm fall as the strip
  spans more cells (2 -> 3 -> 4 -> 5)? (§1, §4.1)
- **Q2 -- box lever at the pinned absorber.** At `h = 0.4 mm` and `npml 12`, does the offset at the
  **unit** lateral box differ from the offset at the **8x** lateral box by more than the resolution
  floor? (§4.2) The 8x-lateral arm of Q2 is *already measured* -- it is `h_refine` rung A -- so Q2
  costs one arm, not two.

## 0. The question, and what is NOT being asked

`evidence/h_refine/SUMMARY.md` §1/§4 measured a residual that falls with `h` but does not vanish: at
`lat 8 / lid 1`, `h 0.4 -> 0.26667`, `d_FDTD` fell `0.35166` pp (`+0.90201 -> +0.55036`) and `d_EIG`
`0.35890` pp (`+1.29349 -> +0.93459`), while the two-solver gap stayed put (`0.38798 -> 0.38213 %`)
[M]. On that ladder the strip was pinned in **metres** (`--strip-width-mm 0.8`), so `n_strip` moved
with `h`: `2` at `h 0.4`, `3` at `0.26667`, `4` at `0.2` (never run) [M, `resolve_strip` source
249-266]. **The strip's cell count and the cell size therefore moved together on every measured rung,
and the h-ladder cannot separate them.** Any part of the residual that is the strip's own meshing is
common-mode in that design.

This dispatch moves `n_strip` at **fixed `h`** and nothing else. `h = 0.4 mm`, `clearance 3 H`,
`lat 8 / lid 1`, absorber pinned at `4.8 mm` (`npml 12`), `nsteps 2400`, same driver, same reference
function. The independent variable is `--strip-width-mm`.

Not asked: the `h` term (held at 0.4, and already measured twice); the box term (held at `lat 8 /
lid 1`, the `h_refine` bridge geometry -- Q2 varies it only to check that the *pinned-mm absorber*
did not revive it); absolute agreement with truth; the reference's own accuracy; `T2_agree`,
`ModalPort.from_mode2d`, the C++ port.

**The honest framing, stated before the numbers exist:** these are four *different lines*, not one
line meshed four ways. A wider strip is a lower-impedance line with a different `eps_eff`, so both the
reference *and* the physics move between arms. Only the per-arm ratio `d_W` is comparable across arms
(§3, §6.1). This is the single largest limitation of the design and it is not repairable within it.

## 1. Design: four widths, all exactly on mesh, at h = 0.4 mm

At `h = 0.4 mm`, `grid_for` gives `n_sub = round(1.6/0.4) = 4`, `cell = 1.6/4 = 0.400 mm` exactly
[M, source 228-239]. `resolve_strip` returns `n_strip = max(round(W/cell), 1)` and the **meshed**
width `n_strip*cell` [M, source 249-266]. With `cell = 0.400` all four requests land on the mesh with
zero rounding error, so meshed width == requested width on every arm:

| arm | `--strip-width-mm` | `cell` (mm) | `W/cell` | `n_strip` | meshed `W` (mm) | `W/H` | `ref` at the rung-A tone (rad/m) [M] |
|---|---|---|---|---|---|---|---|
| W08 | 0.8 (default) | 0.400 | 2.0 | 2 | 0.800 | 0.500 | 384.7489756771 |
| W12 | 1.2 | 0.400 | 3.0 | 3 | 1.200 | 0.750 | 390.0472372151 |
| W16 | 1.6 | 0.400 | 4.0 | 4 | 1.600 | 1.000 | 394.7445116132 |
| W20 | 2.0 | 0.400 | 5.0 | 5 | 2.000 | 1.250 | 398.8870468748 |

Both `strip_width_m` and `strip_width_mm` are emitted per row as the **meshed** width [M, row keys at
source 725-757], so a request that silently rounded would be visible in the record: on this sweep it
cannot, and any row whose recorded meshed width differs from the table above is a mis-run, not an arm.

The `h` value is deliberately the **already-measured** rung: arm W08 is the `h_refine` rung-A
configuration (same `h`, same box, same `npml 12`, same `nsteps 2400`, same 0.8 mm strip), so its row
must reproduce `evidence/h_refine/h040.json` (guard G2, §10). That is a free end-to-end check that the
arm was run on the instrument it claims.

## 2. Fixed parameters, and the command template

    python3 tools/host_ladder.py --h 0.4 --clearance 3.0 \
        --box-lateral-mult 8.0 --box-lid-mult 1.0 \
        --pml-mm 4.8 --npml 12 --nsteps 2400 \
        --strip-width-mm <0.8|1.2|1.6|2.0> \
        --mem-ceiling-mb 4000 --json evidence/strip_width/w<arm>.json

One arm at a time. `--npml 12` is passed *and* `--pml-mm 4.8` is passed, so the absorber is pinned in
millimetres and `npml` re-derives as `round(4.8/0.4) = 12`; the two agree at this `h` and the row
records both. `--strip-cells` is **not** used: it pins the width in *cells*, which at `cell == h` makes
`W` drift with `h` and the arms cease to be one structure [M, deprecation warning at source 266-283].

**Grid, and why the arms are affordable.** `ny` is the only extent that depends on the strip:
`ny = 2*n_clean + n_strip + 2*npml`, `nz = n_sub + n_air + npml`, `nx` independent of both (and of
`lateral_mult`). That law reproduces four banked grids exactly [M]: `h_refine` rung A `(68,218,28)`
and rung B `(101,327,42)`; `box_sweep` `lat1-lid1` `(62,38,22)` and `lat8-lid1` `(62,206,22)`. On this
sweep `ny` moves by one cell per arm, so `n_cells` moves by `1/218 = 0.46 %` across the four arms and
the per-arm cost is `232.0 s` FDTD / `388.4 MB` [M, rung A] to within half a percent. Whole sweep:
`4 x 232 = 928 s` FDTD plus `4 x 22.4 s` modal [M, rung A] ~= 16 minutes.

## 3. The graded reference, and how it is allowed to move

Per arm, the reference is
`tools/d585_modal.hammerstad_beta(f_arm, W=W_arm, H=1.6e-3, eps_r=4.4)['beta']` -- dispersive
Hammerstad-Jensen on Kirschning-Jansen `eps_eff` -- evaluated at **that arm's own realised DFT tone**
`f_hz`, exactly as the `h`-ladder does (PREREG §3 there). Both the tone and the width enter, so the
reference is recomputed per arm and both inputs are recorded.

The preview column in §1 is computed here, at the rung-A tone `10.19862621457275 GHz`, with the
thickness term verified inert (`t = 0` and `t = 35 um` agree to every digit) [M, computed in this
dispatch]. It is a **preview, not the graded value**: the realised tone is not known before the run,
and each arm is graded at its own. Two things it already settles:

- `W08` returns `384.7489756771`, the frozen pin `384.7489672644` to `2.2e-8` relative [M] -- the
  reference path is the same one `box_sweep` and `h_refine` were graded on.
- The reference is **not** W-independent: it rises `+1.37706 / +2.59789 / +3.67464` pp across arms
  W12 / W16 / W20 [M] while the FDTD residual being graded is `+0.90201` pp at W08 [M]. Grading
  `d_W` (offset relative to each arm's own reference) rather than `beta` is what makes the arms
  comparable; the reference's own W-dependent *error* is not cancelled by this and is not measured
  here (§11).
- `W/H` spans `0.5 .. 1.25`, inside the Kirschning-Jansen validity window `0.1 <= W/H <= 10` [M], and
  `beta` is finite, positive and monotone increasing in `W` at every arm -- no NaN, no sign flip.

`emfit.microstrip.Microstrip.beta` is not used anywhere in this dispatch: it is quasi-static and is the
superseded basis (decisions.md 146/148(b)).

## 4. Pre-registered readings and the decision rule

Per arm: `d_W = 100*(beta_fdtd/ref(W, f_hz) - 1)`, `d_EIG` likewise, `rel_gap = 100*(beta_eig/beta_fdtd
- 1)`, all in percentage points; `W/cell` is `n_strip` by construction.

Resolution floor, carried unchanged: **`Delta_min = 0.0734 pp`**, threshold **`3*Delta_min = 0.2202
pp`**. Provenance, and the reason it is *not* re-derived for this sweep, in §7.

### 4.1 Q1 -- strip meshing

**CONFIRMED (strip meshing implicated)** -- all of:

1. `|d_W|` falls at **each** of the three consecutive steps `2 -> 3 -> 4 -> 5`, i.e. each step is a
   fall of more than `Delta_min`; a step smaller than the floor does not count as a fall;
2. total fall `|d_W(2)| - |d_W(5)| > 0.2202 pp`;
3. at least half the `n_strip = 2` residual is removed: `|d_W(5)| <= 0.5 * |d_W(2)|`;
4. the EIG side does not move *against* the FDTD side by more than `0.2202 pp` (the modal half meshes
   the same strip and checks `ny_strip == n_strip` against the FDTD half [M, `build_modal` source
   ~345-360], so it is a second, independent read on the same quantity; a large disagreement means
   the two halves did not measure the same change);
5. no guard in §10 fired.

**REFUTED (meshing is not the explanation)** -- any of: the sequence is not strictly falling by more
than `Delta_min` at each step; total fall `<= 0.2202 pp` (this is what "flat" means, quantified); the
half-residual condition (3) fails. Then the residual at `n_strip = 2` survives a strip `2.5x` wider in
cells and is not attributable to how the strip is meshed at this `h`.

**INCONCLUSIVE** -- anything else: any arm aborted or missing (`meta.abort_reason` not `None`,
non-zero exit, no row); any arm tripping the §5 gate; guard G1/G2/G4/G6 fired; the two solver sides
disagreeing per (4). Not a weak confirmation and not a weak refutation.

Precedence: **guards first**, then the rule.

**Declared in advance, so that no later reader over-reads either outcome:** with four arms spanning
`W/cell = 2..5` only, a sequence that falls and then plateaus is **indistinguishable** from a residual
that has a model-error floor. `REFUTED` is therefore **not** evidence that the reference is wrong, and
`CONFIRMED` is **not** evidence that the reference is right -- it is evidence that a strip-meshing
error of order `0.2 pp` or more is present at `n_strip = 2`.

### 4.2 Q2 -- the box lever at the pinned absorber

One new arm: **W08-N** = `--h 0.4 --clearance 3.0 --box-lateral-mult 1.0 --box-lid-mult 1.0 --pml-mm
4.8 --npml 12 --nsteps 2400 --strip-width-mm 0.8`, i.e. the unit lateral box with the same 4.8 mm
absorber. Compared against `h_refine` rung A, which is the *wide* (`lat 8`) arm at the same `h`,
`npml`, `nsteps` and `W` -- already measured `d_FDTD +0.90201` pp, `415072` cells, `232.0 s`,
`388.4 MB` [M]. The only difference between the two arms is `--box-lateral-mult`.

Grid of the narrow arm, from the same validated law [M]: `n_clean = 3*1*1.6/0.4 = 12`,
`ny = 24 + 2 + 24 = 50`, `nz = 4 + 12 + 12 = 28`, `nx = 68` (independent of `lateral_mult`: both
`box_sweep` lateral arms are `nx = 62` at `npml 6`) -> `68 x 50 x 28 = 95 200` cells. Priced by ratio
to rung A: `232.0 * 95 200/415 072 = 53.2 s` FDTD, `388.4 * 95 200/415 072 <= 89.1 MB` [L -- ratio, not
measured]. **Not** copied from the `box_sweep` `lat1-lid1` row, which is `(62,38,22)` at `npml 6`: the
pinned-mm absorber changes `nx` and `nz`, so that row is a different grid and must not be used to price
this arm.

    MOVES        iff  |d_wide - d_narrow| > 0.2202 pp
    DOES-NOT-MOVE otherwise

Secondary reading, reported but not graded: `|d_narrow|` itself, against the `0.2202 pp` threshold.
If it also moves, the box lever is live *at the pinned absorber* and the `h`-ladder's bridge geometry
is questioned -- which would be a finding about `h_refine`, not about `h`.

Why this is asked at all: `box_sweep` measured the box lever at **`npml 6`** and found it small --
the whole unit-box -> `lat8/lid4` move is `0.0971` pp against a `+1.1107 %` base offset [M]. The
`h_refine` rungs then ran at `npml 12` (4.8 mm absorber) and, per §5 there, that absorber change alone
moves `d_FDTD` by `0.16625` pp [L] -- **larger than the lever `box_sweep` had just measured**, on a
different grid. Q2 never runs the narrow box at `npml 6`, so it is not a re-run of `box_sweep`.

## 5. Per-arm sizing gate, declared before the runs

Hard stop, per arm, on either `wall_fdtd_s > 900` or `peak_rss_mb > 4000` -- the `h_refine` numbers,
unchanged. Priced per arm at `232.0 s` / `388.4 MB` +/- 0.5 % [M], the gate sits `3.9x` / `10x` above
the expectation, so it cannot fire on cost. It is kept as a **check, not a budget**: if it fires, the
geometry law of §2 was wrong and the arm is not the box this file pre-registers, so it must not be
graded (guard G6). The narrow Q2 arm is priced at `53 s` / `<= 89 MB` [L] and is not near the gate
either.

**Environment gate (added because this dispatch's own container failed it).** The `h_refine` runs
recorded a `6144 MB` cgroup [M, `meta` in `h040.json`]. The container this file was *written* in
reports `memory.max = 536870912` (512 MB) [M, `/sys/fs/cgroup/memory.max`]. Rung A's measured
`peak_rss` alone is `388.4 MB` = `76 %` of that cap. **The arms must therefore be run in a
6144 MB-class container with the cgroup verified before the first launch**, and the gate above is
meaningless until that is confirmed; an arm run at `--mem-ceiling-mb 4000` inside a 512 MB cgroup
would be graded against a ceiling it can never reach.

## 6. Confounds declared in advance

1. **A different line at every arm.** `W` sets `eps_eff`, `Z0` and the reference (3.67 pp across the
   sweep, §3). The comparison is `d_W` vs `W/cell`, *not* `beta` vs `beta`. HJ+KJ's W-dependent error
   does not cancel and is not bounded here.
2. **Wall loading varies slightly.** The box is fixed in metres while the strip takes a larger share
   of it (2 of 50 cells at the wide box, 5 of 54 at arm W20). A larger strip perturbs the box fields
   nearer the walls. Not separable from meshing by this design.
3. **The tone snaps per arm.** `beta` is dispersive and the extraction snaps to the nearest DFT bin;
   each arm is graded at **its own realised** `f_hz` (recorded per row). At rung A the detune is
   `+1.888 %` and `tone_warn` is `True` under the driver's `|detune| > 0.1 %` rule [M, source
   775-782] -- and that rung was still graded. **`tone_warn` is therefore not a validity criterion
   here**, and no guard is built on it; the realised tone is.
4. **`h` is not refined**, so if the residual is mostly an `h` error the arms should read flat -- and
   that would be `REFUTED` for the wrong reason. This is why §4.1(2) requires the *total fall* to
   exceed the threshold rather than merely a good endpoint.
5. **The EIG half is not an independent measurement of `h`.** Both halves share the box and the strip
   rounding; the EIG half is a cross-check on *this* change, not on the reference.

## 7. The resolution floor: where `0.0734 pp` comes from, and why it is not re-derived here

`Delta_min` is carried unchanged from `box_sweep` -> `h_refine` -> here.

- Provenance [M]: `evidence/h_refine/PREREG.md` §4 -- "`Delta_min = 0.0734 pp` (the smallest
  difference that sweep could resolve)"; ultimately `box_sweep` §7 (`Delta_min = 0.10 %` of
  `384.749` = `0.38475 rad/m`).
- Its operational origin [M]: `evidence/box_sweep/SUMMARY.md:123` records the lid-`4x` arm moving
  FDTD by `-0.07344` pp and marks that cell **INVARIANT** because it is below the floor;
  `SUMMARY.md:88` quotes the base sequence as `0.0734` pp against a base offset of `1.11069` pp.
- **Disclosed circularity.** So `0.0734 pp` is, operationally, *the largest arm-induced change
  `box_sweep` retained as null*. Using it as the floor is mildly self-fulfilling: a lever that moved
  `0.08 pp` would have been graded as a move under a floor of `0.0734` and as noise under `0.0735`. A
  tighter same-geometry estimate exists: on the `h_refine` absorber plateau, `npml 12 -> 16` moves
  `d_FDTD` by `0.0108 pp` [L, `h_refine` SUMMARY §5] -- `6.8x` tighter.
- **Frozen anyway, and the bias is named.** Keeping `0.0734 / 0.2202` keeps this row numerically
  comparable with the two rows already frozen (`box_sweep`, `h_refine`); switching floors mid-series
  lets the choice of floor decide a verdict. The bias runs in one direction only -- a large floor makes
  `CONFIRMED` harder and `REFUTED` easier, i.e. against the hypothesis this dispatch is testing. That
  is the direction a floor should err in, and it is recorded rather than repaired.

## 8. Three-outcome table (frozen)

| verdict | criterion (necessary and sufficient) | what it would mean |
|---|---|---|
| **CONFIRMED** -- strip meshing implicated | §4.1(1)-(5) all hold | part of the `+0.90 pp` FDTD residual at `n_strip = 2` is the strip's cell count, and any design that pins the strip in metres inherits an `h`-correlated strip term. The `h_refine` fall then has a second contributor, and the `h`-term is smaller than the raw two-rung fall |
| **REFUTED** -- meshing not the explanation | the sequence is not strictly falling by more than `Delta_min` at every step, **or** total fall `<= 0.2202 pp`, **or** less than half the residual is removed | the residual at `h 0.4 / lat 8 / lid 1` is not how the strip is meshed. Surviving candidates: the `h` term itself (measured by `h_refine`), the box/absorber (Q2, §4.2), and the reference's own accuracy |
| **INCONCLUSIVE** | anything else, including any §10 guard | reported as unresolved. Not a weak confirmation |

| verdict | criterion | what it would mean |
|---|---|---|
| **LEVER MOVES** (Q2) | `|d_wide - d_narrow| > 0.2202 pp` | the box lever is live at the pinned 4.8 mm absorber, so `box_sweep`'s `npml 6` conclusion does not transfer to the `h_refine` geometry |
| **LEVER DOES NOT MOVE** (Q2) | `|d_wide - d_narrow| <= 0.2202 pp` | the box's contribution is unchanged by pinning the absorber in mm, and `h_refine`'s choice of the 8x box is not doing any work |

Rows are reported even when they would not be graded, so the record shows what was measured.

## 9. Standing adversarial review before the freeze (rule 1 of `session_close_gen5.md` §3)

Run against §0-§8 above, before the freeze. The disposition column says what it changed.

| # | attack | disposition |
|---|---|---|
| A1 | "Four arms of four *different lines* is not a meshing study -- `W` changes the physics, the reference and `Z0`." | **Disclosed, not repaired** (§0, §6.1). `d_W` is compared, not `beta`, so the reference change cancels by construction; HJ+KJ's W-dependent error does not. This is the design's largest hole and no arm in it can close the hole. |
| A2 | "`|d|` monotone decreasing will happen by regression to the mean." | **Changed.** §4.1(1) requires each of the three steps to fall by *more than* `Delta_min` -- sign alone is not a fall -- and (3) requires half the residual to be removed. Four points, three steps, each outside the floor. |
| A3 | "`0.0734 pp` is a self-fulfilling floor." | **Disclosed** (§7), with the tighter `0.0108 pp` estimate quoted, the circular origin named, and the direction of the resulting bias stated. Not re-derived, for series comparability. |
| A4 | "The 900 s gate cannot fire on a 232 s arm, so it is decoration." | **Accepted and restated.** §5 calls it a *check* on the geometry law, not a budget; guard G6 makes a trip mean "the arm is not the box this file registers", not "the machine was slow". |
| A5 | "`tone_warn` is `True` at rung A and you graded it, so your validity rules contradict themselves." | **Changed.** No guard anywhere on `tone_warn`; the realised tone is recorded and used per arm (§6.3), and the contradiction is stated instead of inherited silently. |
| A6 | "The EIG side will disagree with the FDTD side and you will pick the one you like." | **Changed.** §4.1(4) makes a large opposite-signed EIG move INCONCLUSIVE, and `rel_gap` is reported so the disagreement is visible in the row. |
| A7 | "One run per arm; the verdict hangs on four single runs and an aborted arm gets dropped." | **Changed.** Guard G1: a missing/aborted arm makes the verdict INCONCLUSIVE. No partial row is graded. |
| A8 | "Widening the strip at a fixed box changes the wall loading, and you will call it meshing." | **Disclosed** (§6.2). Bounded, weakly: the `box_sweep` lever (`0.0971` pp [M]) and the `npml 6 -> 12` absorber term (`0.16625` pp [L]) are both below the threshold, so a loading confound of that size cannot manufacture CONFIRMED on its own -- but neither was measured at `W = 2.0 mm`, and Q2 does not measure it either (Q2 holds `W` at 0.8). |
| A9 | "You did not check that the reference is even computable at `W = 2.0 mm`." | **Changed.** Computed at freeze time (§3): finite, positive, monotone, `W/H` inside the KJ window at all four arms; guard G4 re-checks per arm at the realised tone. |
| A10 | "You are running and reviewing your own pre-registration." | **Disclosed.** Same as `box_sweep` A9: this pass is a checklist applied to its own criteria, weaker than an independent reviewer. Mitigation: every rule in §4/§8 is mechanical over the row keys named in §3, so a reader can re-apply it to the JSONs in `evidence/strip_width/` without trusting this prose. |

## 10. Invalidating guards (frozen)

- **G1 completeness** -- one row per arm, exit `0`, `meta.status == 'ok'`, `meta.abort_reason is None`.
  A missing or aborted arm -> INCONCLUSIVE; no partial row graded.
- **G2 arm-W08 reproduction** -- arm W08 must reproduce `evidence/h_refine/h040.json` in
  `beta_fdtd` and `beta_eig` to `1e-9` relative. It is the same configuration. A mismatch means the
  instrument moved, and the other three arms are then not on the same instrument.
- **G3 tone record** -- `meta.tone_f_actual_ghz` and `meta.tone_detune_pct` recorded per arm; each arm
  is graded at its own tone. No guard on the detune magnitude (§6.3).
- **G4 reference reachability** -- for every arm, `hammerstad_beta` at the realised tone and that arm's
  `W` returns finite, positive `beta` with `W/H` in `[0.1, 10]`; else INCONCLUSIVE.
- **G5 resources** -- `--mem-ceiling-mb 4000`, one arm at a time, cgroup >= `6144 MB` **verified before
  the first launch** (§5). A run started in a smaller cgroup is void, not graded.
- **G6 geometry** -- each row's `n_cells` must equal the §2 law to `+/- 5 %` and `n_strip` must equal
  the §1 table; else the arm is not the pre-registered box and is void (this is what makes the §5 gate
  a check rather than a budget).
- **G7 mode identity** -- `b_over_a` and `alpha_fdtd_db_per_mm` within a factor `[1/3, 3]` of rung A's;
  a row outside that band is MODE-SUSPECT and makes the verdict INCONCLUSIVE.

## 11. What this pre-registration does NOT establish

- It does not measure the `h` term (`h` is fixed at 0.4) and cannot separate a strip term from an `h`
  term -- it can only show whether a strip term of the required size is *present* at this `h`.
- It does not bound HJ+KJ's own accuracy at any `W`, and therefore cannot say whether a "flat" result
  is physics or reference error.
- It does not test absolute agreement with truth, `T2_agree`, `ModalPort.from_mode2d`, the C++ port,
  or whether `+0.90 pp` is an acceptable engineering tolerance.
- Q2 does not re-run `box_sweep` (it never raises `npml` from 6 to 12 on the narrow box), and it does
  not vary the lid.
- It does not establish that `n_strip >= 5` is sufficient -- only whether the trend is still falling
  at `n_strip = 5`.

## 12. Freeze declaration

Frozen 2026-10-31T01:53Z, before any arm of this directory existed. Provenance of the code under
test [M, `sha256sum` in the container this file was written in]:

| file | sha256 | note |
|---|---|---|
| `tools/host_ladder.py` (1106 lines) | `1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` | identical to the hash frozen in `box_sweep` §12 |
| `tools/d585_modal.py` | `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6` | identical to the hash frozen in `box_sweep` §12 |
| `emfit/studies.py` | `578650bc59b1dbaa09832ec3dde2c0058fa69e0dcee56c2e8a4cc7ff37e802ac` | geometry driver behind `microstrip_wave` |

Python 3.12.15, numpy 2.5.4, scipy 1.18.1 [M]. Container of record for the runs: 6144 MB cgroup (not
the 512 MB container this file was written in -- §5). A future edit to any of the three files above
voids the freeze and requires an append-only erratum, not a silent re-run.

No `decisions.md` write is claimed by this dispatch; any decisions text goes to
`docs/design/<dispatch>_decisions_block.md` for Agent A to merge (standing rule 2).
