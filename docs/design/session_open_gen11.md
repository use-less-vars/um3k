# Session open — Generation 11

**Written 2026-11-14, at HEAD `3848d46`. Reader: the incoming engineer; read this FIRST, then `session_close_gen10` (the session this one inherits), then `docs/design/EM_SOLVER_LEDGER.md`:30 and `:37` (E5 and E12), then the active scope.**

## How this document was written

Drafted by the outgoing generation at HEAD `3848d46`. Every claim carries its warrant: **[M]** measured while writing this file, **[L]** read from the tree or the artefact named beside it, **[R]** relayed and unchecked. **The artefact always wins over this text:** if a number here disagrees with `evidence/referee/s11_extraction.json`, the ledger, the register or the dispatch log, the file on disk is right — record the disagreement in the next row rather than editing the artefact to match.

One boundary, so it is not read as an omission: §2 is the E12 verdict as the ledger states it, caveats included, and §3 is the *current* task — the visualiser — which is a **different** job from the one that just closed. Nothing in §2 needs re-deriving to start §3.

## 1. Where we are

**The physics-debug phase is closed and the project is not in a state of doubt.** E12 (Independent Referee) is recorded **VERIFIED** at `docs/design/EM_SOLVER_LEDGER.md`:37 [L]. An openEMS model — fully attached, strip PEC at `priority=10`, MSLPort launch on port 1, lumped port for the load — independently reproduced the in-house extraction at one frequency to inside half a percent.

The work now is a **viewer**, not a solver: the wave is known to be right and the question has moved from "is the number right" to "does the wave look right" (`session_close_gen10` §5) [R].

## 2. The number, and what "VALIDATED" means here

From `evidence/referee/s11_extraction.json` [L]:

| field | value |
|---|---|
| `f_hz` | **5827786408.327286** (5.827786 GHz) |
| `s11_abs` — openEMS MSLPort, independent referee | **0.327164553** (`0.3271645531273824`) |
| `s11_artefact_target` — in-house emfit | **0.325564866** (`0.32556486641109117`) |
| difference | **1.5997e-3** in \|S11\| |
| relative | **+0.4914 %** — *derived* (1.5997e-3 / 0.3255648664110912); **no field in the JSON prints it** |
| referee's own extraction floor (`bias_floor.floor_gamma0`) | **5.364e-4** |

The gap is about **three times** the referee's own floor (2.98x, *derived*), so the agreement is not the floor talking.

**"VALIDATED" here means one thing and not more:** a named referee agreed to within half a percent on `|S11|` at **one** frequency, under a **declared 50 ohm** reference (`zref_ref50_ohm` 50.0, `port1_api` `"mslport"`) [L]. It does **not** mean every gate is green, and the caveats below sit in the **same ledger row**, so Gen 11 inherits them rather than rediscovering them.

### The four caveats that travel with the number

1. **The mode fit did not pass its own gate.** `mode_fit_ok` is **false** in `s11_extraction.json`:91, with `mode_fit_ratio` **11.109793** against a tolerance of **0.01** (`mode_fit_tol`) [L]. In words: the field-derived characteristic impedance is not a mode — `beta` is complex there, 165.245862 + 1835.847243j, and `|Z_ref|` comes out 28.494912 ohm (`zref_field_ohm_abs`) against the declared 50 ohm reference, `zref_ref50_ohm` 50.0 [L]. This is why the 50 ohm reference is the model of record and the field-derived one is **demoted to a diagnostic**.
2. **The 0.327 number depends on the declared reference.** The same data, normalised by the field-derived Z_ref, reads **0.496975** (`s11_field_zref_abs`:106, with `zref_field_ohm` = `[23.24570567738614, -16.48020529222403]`) — about **52 % above** the 50 ohm value (*derived*). Say this plainly whenever the 0.327 is quoted: it is a 50-ohm-referenced number, not a reference-free one.
3. **The 5.5 % gap against the independent anchor `0.342` is read as a de-embedding / measurement difference, not an extraction defect** [L, ledger `:37`]. That cross-check found no extraction defect to explain it; it did not explain the gap either.
4. **S21 is out of scope, explicitly.** Port 2 is a lumped load to ground, not a launched port, so the model produces **no through measurement** and none is quoted [L, ledger `:37`]. Any sentence of the form "the referee also confirms S21" is wrong.

Two smaller things worth carrying: `Feed_R` was **refused** for port 1 because on an MSLPort it inserts a lumped resistor into the model rather than setting a reference (`infra/openems/reference/ports.py`:408-416) [L, ledger `:37`] — using it would have changed the physics in order to define the measurement. And the referee's `|S11|` angle is recorded as **-38.000423 deg** [L, ledger `:37`].

**What the ledger does not say, and you should not either.** The 0.327 is MSLPort **probe** arithmetic: an independent *solver* on the same extraction method, not an independent *extraction*. No independent `CalcPort` cross-check exists (`session_close_gen10` §6) [R]. And every run record on disk carries `"git_rev": null` (e.g. `artifacts/vis_run_1500.json`:208) [L], so numbers are tied to files, not commits — the DR-28 shape, still open.

## 3. The current task — the WaveDude visualiser

Two commits on 2026-11-10 [L, `git log`]:

1. **`f667e42` — "feat(fdtd): WaveDude time-series field dump for the visualiser"** — the writer. Touches `emfit/studies.py` and `evidence/termination/run_build_A.py`.
2. **`3848d46` — "feat(vis): WaveDude time-series player in the PoC web app"**, about 15 minutes later — the player. Touches `server/poc_app.py` **only**.

The pipeline itself (flag semantics, the three stored surfaces, cadence, schemas, dependencies) is documented in `docs/design/visualizer_architecture.md`; read that beside this file. This section is the **state of play**, which is worse than a feature list suggests.

### The UI quirk: it has never been run

The player lives in `server/poc_app.py` (4,031 lines) and is **unverified** — not merely "buggy". Its own docstring says so at lines 49-55 [L]:

> STATUS: the web path (trame server, layout, slider callbacks, panel placement) is UNTESTED. Only the numpy / CLI path (`--help`, `--list-keys`) has been exercised. Treat any browser-side behaviour as unverified. All four layers above were added in the same environment: pyvista, trame and VTK are not installed here, so they have never been rendered either.

Read that precisely: the GUI has **never once executed**. Nothing about it is known-good; there is no symptom list to triage, only a claim that has never been tested. Do not start by "fixing" a rendering bug you have not reproduced.

The good news is structural: GUI imports are **deferred inside functions** (`:3309` says it outright for the numpy-only paths), so the data half is importable and testable with numpy alone — `load_wavedude` at `server/poc_app.py`:207 is documented "numpy only, no pyvista" [L]. **The first dispatch is therefore: stand up trame / pyvista / vtk, then verify the player renders and the numpy path still reads the same file** — before touching a single symptom.

### The 15 GHz rule — a viewing choice, not a physics change

`evidence/termination/run_build_A.py`:476-477 [L]:

```
WAVEDUDE_F_PULSE_HZ = 15.0e9
WAVEDUDE_F_REF_HZ   = 5827786408.327286
```

`--pulse-freq-ghz` (declared `default=None` at `:2383`, resolving to the 15.0 GHz constant — the help text prints "default 15.0 GHz") sets the centre the visual dump's wavelet is struck at, is **only used together with `--wavedude-dump`**, and "overrides `f_pulse` only, never `f_target`" (`:446`) [L]. The reference frequency recorded in the file is **unconditionally** `WAVEDUDE_F_REF_HZ` 5.8278 GHz, *whatever the picture was struck at* (`:447-450`).

The reason is geometric, and it is the whole rule. At 5.828 GHz the guided wavelength is **27.14 mm** at the measured phase velocity 1.5814e8 m/s (`WAVEDUDE_V_FALLBACK_M_S`, `:478-482`) — on a **24.8 mm** line (`:443`), i.e. a Ricker wavelet one wavelength long is *not a travelling packet, it is the whole line sloshing* (`:440-444`). At 15 GHz the wavelength is **~10.5 mm** (*derived*, 1.5814e8 / 15e9) and the motion is visible.

**So: extraction math stays at 5.827 GHz. The 15 GHz pulse is a viewing choice.** A wavelet run is a VISUAL run — its `s21`/AC numbers are not a measurement and are not claimed to be (`:450-451`) [L]. Do not let a pretty picture become a quoted number.

## 4. What is open, by name and id

- **DR-41** — the openEMS MSLPort silently dropped its own launch primitive (priority tie with the substrate top face → the launch box discarded, no error, energy trace flat at -8.54 dB), *and* the probe files are named component-first (`port_ut_1A`, not `port_1_utA`). **FIXED-TESTED**, filed for the landmine, not as an open item [`docs/design/defect_register.md`:760-782] [L].
- **E5 — Co-simulation: UNVERIFIED** [`docs/design/EM_SOLVER_LEDGER.md`:30] [L]. The SPICE-facing direction is analysed and unimplemented; the volume-parts boundary is **not decided**. `emfit/spice.py` is **confirmed absent** from the tree (34 modules, none named `spice.py`) [L], and the ledger row itself says so.
- **The visualiser** — writer landed, player landed, **nothing verified in a browser** (§3). This is the live item.
- **No independent `CalcPort` cross-check** of the probe-derived referee numbers (`session_close_gen10` §6) [R].
- **DR-28** — `meta.git_rev` is null, so no run record is tieable to a commit (visible at `artifacts/vis_run_1500.json`:208) [L].

## 5. Next dispatches, in priority order

1. **Stand up the GUI and verify the player renders.** Install `requirements-web.txt` (six packages, unpinned) and run the player against a WaveDude dump. Success = a rendered animated sheet with a time scrubber. Until this is done, every visualiser claim in the tree is unverified.
2. **Fix the camera / playback bindings** — only after (1) has produced a symptom, and with the numpy-only path (`load_wavedude`:207) kept working, since that is the only part of the player anyone has exercised.
3. **`emfit/spice.py` for Volume Parts / E5.** Confirmed the **E5** label: it is a ledger row, `E5 | Co-simulation | UNVERIFIED`, at `docs/design/EM_SOLVER_LEDGER.md`:30, with the proposal analysed at `docs/design/roadmap-next-2026-11-08.md`:136-218 [L]. Decide the boundary **first** — the export side is the cheap part; the ledger says so in as many words.

## 6. Honest state of knowledge

**(1) The half-percent is one frequency, one reference, one pair of instruments.** §2 caveats 1-3 are not footnotes; they are the limits of the claim.

**(2) The 0.49 % is derived, not printed.** No field in `s11_extraction.json` carries it (`:90`, `:99`, `:101` carry the inputs) [L]. Quote it as arithmetic, and name the two fields it came from.

**(3) Nothing visual has been seen.** The player has never executed; the dumps are not committed (blanket `*.npz` in `.gitignore` with only `!tests/data/*.npz` exempted) [L], so the ~10.2 MB `artifacts/vis_dump_1500.npz` on this disk is a **local** artefact, regenerable only by re-running `--wavedude-dump` on the host [L]. A reader who assumes the dump ships with the repo will be wrong.

**(4) The engineer's role, one sentence:** mission keeper and scope defender who does not run tools or read code and who asks "why" until the answer is real — the habit that carried generation 10 through the referee dig.
