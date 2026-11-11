# NOTE — twin-run provenance, and what the S11 referee number establishes

> **Rule.** A `*twin*.json` record may be cited only to show what changing one
> internal parameter does. It may never be cited as "the referee agrees", as
> "an independent anchor", or as validation. A residual computed against a twin
> run is a self-consistency check on the engine, not an error bar. Section 3
> identifies which of the two S11 anchors is twin-derived (0.34465) and which
> is not (0.3423544).

## 1. The two numbers

| quantity | value | source |
| --- | --- | --- |
| `s11_abs` — openEMS MSLPort independent referee, declared 50 ohm reference | **0.327164553** (`0.3271645531273824`) | `evidence/referee/s11_extraction.json` (`s11_abs`, `s11_ref50_abs`, `zref_ref50_ohm` 50.0, `port1_api` "mslport"), at `f_hz` 5827786408.327286 |
| `s11.magnitude` — in-house emfit, the artefact under cross-check | **0.325564866** (`0.32556486641109117`) | `evidence/termination/build_A_50ohm_p51_phasors.json` |
| difference | **1.5997e-3** in \|S11\| | derived |
| relative | **+0.4914 %** on an in-house basis (`1.5997e-3 / 0.3255648664110912`); **+0.4890 %** on a referee basis | derived — no field in either JSON prints it |

The in-house value is *below* the referee value. The +0.4914 % is a derived quantity; `docs/design/session_open_gen11.md` section 2 ("The number, and what \"VALIDATED\" means here") carries the same table and says so explicitly.

## 2. Size of the difference against the referee's own extraction floor

The referee's floor is `bias_floor.floor_gamma0` = `0.0005363610948678204` (5.364e-4) at `evidence/referee/s11_extraction.json:15`.

- |Δ| / floor = **2.9825** — the difference is about three times the referee's own floor, so the agreement is not the floor talking.
- |Δ| / (3 · floor) = **0.9942** — the three-times-the-floor bound is **99.4 % consumed**.

Do not describe this agreement as "well inside" anything. The correct statement is: *inside the 3x floor bound, but with essentially no margin left in it*. Quote 2.98x and 99.4 %; avoid adjectives.

## 3. The two anchors — and which one is which

| anchor | value | derivation | status |
| --- | --- | --- | --- |
| series-R **twin** anchor | 0.34465 | `50/(2*47.53662+50)`; 47.53662 is the twin's *fitted* zc (`evidence/termination/build_A_50ohm_twin_p51.json:312`, hard-coded at `evidence/termination/run_build_A.py:138-140`) | **RETRACTED** as non-independent (`docs/design/anchor_audit_2026-11-05.md:90-95`, `:166-168`: never produced by the run it grades). This is the twin-derived anchor. |
| correct-width anchor (E10) | 0.3423544 | `A = 50/(2*Z0+50)` with Z0 = 48.0237405 — `anchor.source` = "DR-37, the w=3.2 mm rerun of the quasistatic ladder" (`evidence/termination/build_A_50ohm.superseded.json`: `anchor.z0_ohm`, `anchor.formula`, `anchor.derived_anchor_s11`) | **Not** twin-derived; independent of the twin's fitted zc. |

These two anchors are routinely conflated in this project's own prose, so state the distinction explicitly: **0.3423544 is not the twin-derived anchor**, and **0.34465 is not independent**. Consequently the two residuals are measured against different anchors and must not be mixed:

- 0.32556487 against 0.34465 → -5.54 percent (the retracted-anchor figure, `build_A_50ohm_p51_phasors.json:385`);
- 0.32556487 against 0.3423544 → -4.90 percent (the correct-width figure, ledger E1).

Both are recorded in `docs/design/EM_SOLVER_LEDGER.md` E1 (`:26`) and E12 (`:37`).

## 4. What the referee does not cover

- **S21 is out of scope, explicitly**: port 2 is a lumped load to ground, not a launched port, so the referee produces no transmission measurement. The in-house record carries `s21.magnitude` = `0.7644184907560716` (`evidence/termination/build_A_50ohm_p51_phasors.json`); nothing in this cross-check corroborates it.
- **`Feed_R` was refused** on the MSLPort: it does not set a reference impedance, it inserts a lumped resistor into the model (`infra/openems/reference/ports.py:408-416`), i.e. it would have changed the physics in order to define the measurement.

## 5. Pointers

- Referee artefact: `evidence/referee/s11_extraction.json`
- In-house artefact: `evidence/termination/build_A_50ohm_p51_phasors.json`
- Narrative form of the same table: `docs/design/session_open_gen11.md` section 2 ("The number, and what \"VALIDATED\" means here"); caveat 3 there reads the ~5.5 % gap as a de-embedding/measurement difference; note that the 5.5 % figure belongs to the retracted twin-derived anchor 0.34465, while the correct-width anchor 0.3423544 gives -4.90 % (section 3). The two must not be mixed.
- Ledger rows: E1 (`docs/design/EM_SOLVER_LEDGER.md:26`), E12 (`docs/design/EM_SOLVER_LEDGER.md:37`).

## 6. Files in this directory whose names contain "twin" — snapshot, not exhaustive

`ls -1 evidence/termination/ | grep -i twin` returns 13 files plus one directory (`twin_multifreq`): `build_A_50ohm_twin_p51.json`, `build_A_50ohm_twin_p51_s11fix.json`, `build_A_50ohm_twin_p51_s11fix_twin.json`, `build_A_50ohm_twin_p51_twin.json`, `build_A_50ohm_v3_twin.json`, `build_A_50ohm_v3_twin_check.json`, `build_A_50ohm_v3_twin_check_twin.json`, `build_A_50ohm_v3b_s11fix_twin.json`, `build_A_50ohm_v3c_twin.json`, `build_B_100ohm_v3d_p51_twin.json`, `build_B_100ohm_v3d_twin.json`, `build_E_50ohm_v3d_twin.json`, `build_smoke_50ohm_twin.json`.

`build_A_50ohm_twin_p51_s11fix.json` (16,594 B, tracked in HEAD) is easy to overlook because its name lacks the `_twin` suffix; do not read its absence from a `*_twin*` glob as its absence from the record.

## 7. The twin that wasn't: the interrupted `referee_run2` write

Everything above depends on knowing which directory a number was read from,
because a "twin" that is not byte-for-byte a twin silently converts a
re-extraction into a quotation. There is a live instance of that failure mode
in this very repository.

`evidence/referee_run2/` was written by a run that did not finish. The write was
interrupted at **Wed Nov 11 02:07:03 2026**, on build **`5fecbb5`**, and was
parked before the tree was restored from **`db162d6`**. The park is still in the
stash:

```
stash@{0}: On master: interrupted referee_run2 write (run @Wed Nov 11 02:07:03 2026, build 5fecbb5) — parked before restoring from db162d6
```

Seven tracked `port_*` files under `evidence/referee_run2/` were truncated by
that interruption. They are still tracked, still present, and still quotable.
Two other files, by contrast, are provably shared: `et` (blob `8f47122`) and
`ht` (blob `9b85496`) have identical blob hashes in `evidence/referee/` and in
`evidence/referee_run2/`.

So `referee_run2/` is **not** a byte-identical twin of `referee/`. It is
consistent with a partial copy of the same run, interrupted mid-write. Identity
has been established for two blobs and for nothing else, and the `port_*`
divergence is positive evidence against extending that identity to the rest.

Two consequences, both of which this note has to live with:

1. **The two directories are distinct corpora.** A number belongs to the tree it
   was read from. "It is the same run as `referee/`" is not available as a
   licence to re-attribute a `referee_run2/` figure — that premise is exactly
   what the `port_*` truncation falsifies.
2. **`0.34465` is retracted.** It was derived on the twin premise. The anchor
   that replaces it is `0.3423544 = 50 / (2 · 48.0237405 + 50)`, DR-37 at
   w = 3.2 mm, taken from its own tree with its own provenance.

This is not an aside. The whole of sections 1-6 is an argument about twin
provenance and about anchors that are twin-derived; `referee_run2/` is that
argument's own failure mode, sitting in the working tree, tracked and quotable.
