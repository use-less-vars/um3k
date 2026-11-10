# The time-domain visualiser: the WaveDude dump and its player

**Scope, one line:** this document is the record of the **time-domain animation pipeline** — the writer that emits a frame series and the player that reads it — and it specialises `docs/design/visual_engine_arch.md` (436 lines, the slice/isosurface design, **not edited by this pass**); where the two disagree on the time-domain path, **this document is the newer record**.

## Status and reading discipline

**Written 2026-11-14, at HEAD `3848d46`.** No code was executed to produce this document and no measurement was taken for it. Every statement about the repository is a reading of a named line or of an artefact on disk, cited as `file:line` or by JSON field. Every number is either quoted with its location or is arithmetic on quoted numbers, labelled *derived* with the arithmetic shown. A number that is neither is written as a hole. File sizes below were read from the directory listing.

**Implemented, and only half of it verified.** The writer exists and has run on the host; the player exists and has **never run**. That asymmetry is the single most important fact in this document and it is repeated in §8.

## 1. What the pipeline is, in two commits

- **`f667e42` — "feat(fdtd): WaveDude time-series field dump for the visualiser"** (2026-11-10): the writer, in `evidence/termination/run_build_A.py` (with `emfit/studies.py`).
- **`3848d46` — "feat(vis): WaveDude time-series player in the PoC web app"** (same day, ~15 minutes later): the player, in `server/poc_app.py` only.

Two products, one direction: the solver writes an `.npz` frame series, the app reads it and animates it. No new solver quantity, no new physics — the same field the solve already computed, kept over time instead of at one instant.

## 2. The writer: `--wavedude-dump`

Declared at `evidence/termination/run_build_A.py`:2368-2376 [L], with

```python
ap.add_argument(
    "--wavedude-dump", nargs="?", const=WAVEDUDE_DEFAULT_OUT, default=None,
    metavar="PATH", ...)
```

- **Bare flag** (`--wavedude-dump`) writes the default path, `WAVEDUDE_DEFAULT_OUT = "evidence/vis_dump.npz"` (`:463`).
- **With an argument** (`--wavedude-dump PATH`) writes there instead.
- **Absent** (`default=None`) — no dump is written; the run is the ordinary solve.

The help text is explicit that this is **not** a replacement for the existing field dump: *"This is a SECOND, independent product: `--dump-fields` still writes its own snapshot, and both can be asked for in the same run."* (`:2374-2376`) [L]. The sibling is real — `--dump-fields` is a `store_true` flag at `:2356` that keeps **one** timestep, the last (`:432`) [L]. Asking for both is legal and neither changes the other's output.

There is also a **third** entry point worth knowing about, because it needs no solve at all: `--selftest` (`:2396-2400`) writes a *synthetic* WaveDude `.npz` (numpy only — no grid, no march) and re-opens it, checking every key, dtype and shape; its default path is `artifacts/vis_dump_selftest.npz` (`:464`) [L]. That is the only part of the writer that can be exercised without a host run.

## 3. What is written: three surfaces, not one

The dump holds `Ez` on **three** planes, and they are not interchangeable [L]:

1. **`ez_ycut`** — the x-z sheet along the line at one fixed `j`, recorded for **every kept simulation step**. The cut index is chosen at `:616` as

   ```python
   j_cut = n_pml + n_clean + n_strip // 2
   ```

   i.e. the centre of the strip *in index terms*, not a hand-picked number. In the one recorded real run the realised value is **`j_centre` = 106.0** (`artifacts/vis_run_1500.json`:123) [L].
2. **`ez_near`** — an x-cut (y-z sheet) at `--xcut-near-mm`, default **20.4 mm**: on the line, just before the load (`:2389-2391`).
3. **`ez_far`** — an x-cut at `--xcut-far-mm`, default **22.0 mm**: past the load (`:2392-2395`).

So the animation has a longitudinal view **and** two transverse sections through it. A player that draws only `ez_ycut` is drawing a third of the file.

## 4. Cadence, stride and the budget

Recording happens in the march callback at `:742-757` [L]:

```python
slot = n - 1
if slot % self.stride:
    return
fi = slot // self.stride
...
self.ez_ycut[fi] = e[self._map_ycut]
if fi % self.xcut_stride == 0:
    xi = fi // self.xcut_stride
    self.ez_near[xi] = e[self._map_near]
    self.ez_far[xi] = e[self._map_far]
```

- `ez_ycut` takes **every kept step**.
- The two x-cuts take **only every `WAVEDUDE_XCUT_STRIDE` = 10th** y-cut frame (`:472`), so `nt_x == ceil(nt / 10)` (`:470-471`) — **one time base, two cadences**, with no second time array to say so.
- `--dump-stride N` keeps every Nth step (`:2377-2381`, default 1) [L].
- The stride is **planned before the solve**, never discovered afterwards: `_wavedude_plan_stride` prices `--nsteps` and the mesh against `WAVEDUDE_BUDGET_MB = 45.0` (`:467`) and **raises the effective stride with a warning** if the arrays would exceed it (`:453-459`). It never fails for size — "a dump that refuses to exist is worse than a dump with fewer frames" — and the stride it settled on is written into the file as `dump_stride`, so **the cadence of a file is read from the file**, not assumed.
- One hard refusal exists and is the right one: if the plan and the march disagree, the writer raises `WAVEDUDE REFUSED … a dump that silently drops its tail is worse than none` (`:746-750`) [L].

The one recorded real invocation (`artifacts/vis_run_1500.json`:205) [L]:

```
evidence/termination/run_build_A.py --nsteps 1500 --out artifacts/vis_run_1500.json \
  --wavedude-dump artifacts/vis_dump_1500.npz --dump-stride 1
```

1500 steps at stride 1, producing `artifacts/vis_dump_1500.npz` (**10,178,360 B**, ~10.2 MB) and, from the selftest path, `artifacts/vis_dump_selftest.npz` (**1,297,685 B**, ~1.3 MB) [L, directory listing].

### The 15 GHz choice, in one paragraph

The dump's wavelet is struck at `WAVEDUDE_F_PULSE_HZ = 15.0e9` (`:476`) so the packet is short compared with the line — at 5.828 GHz the guided wavelength is 27.14 mm on a 24.8 mm line, which is not a travelling packet but the whole line sloshing (`:440-448`) [L]. The frequency recorded in the file is **unconditionally** `WAVEDUDE_F_REF_HZ` 5.8278 GHz (`:477`), and `--pulse-freq-ghz` "overrides `f_pulse` only, never `f_target`" (`:446`). **Extraction math stays at 5.827 GHz; this is a viewing choice, not a physics change.** Reasoning in full: `docs/design/session_open_gen11.md` §3.

## 5. The file and state contract

| tag / symbol | value | defined at |
|---|---|---|
| `WAVEDUDE_SCHEMA` | `"emfit.wavedude/1"` | `evidence/termination/run_build_A.py`:461 (writer) and `server/poc_app.py`:94 (reader) — same literal on both sides [L] |
| `WAVEDUDE_ENGINE` | `"emfit.fdtd.fit-leapfrog/microstrip_wave"` | `run_build_A.py`:462 |
| `STATE_SCHEMA_WAVEDUDE` | `"emfit.poc-state/2"` | `server/poc_app.py`:95 |
| loader | `load_wavedude(path)`, "numpy only, no pyvista" | `server/poc_app.py`:207-208 |
| format discriminator | `_is_wavedude(info)` — `info["format"] == "wavedude"` | `server/poc_app.py`:202-204 |

The reader **validates** rather than assumes: a file whose schema is not `emfit.wavedude/1` is refused with a message naming the schema it wanted (`:247-257`), and one that declares the schema but is missing keys is refused too (`:257`) [L]. A legacy plane dump is handled on a separate branch (`:366`) — the two are not silently mixed.

## 6. Dependencies, and how to stand them up

`requirements-web.txt` declares **exactly six** packages, **all unpinned** [L]:

```
trame
trame-vuetify
trame-pyvista
trame-vtk
pyvista
vtk
```

with the file's own note that the launcher needs only numpy and "everything here is the trame/pyvista/VTK stack that the browser view needs", installed by `python3 -m pip install -r requirements-web.txt`.

`requirements.txt` carries `pyvista>=0.49.0` and a **comment that must not be ignored**: pyvista pulls `vtk` itself and constrains it (`vtk>=9.3.1,<9.8.0,!=9.4.0,!=9.4.1`), so "**do NOT pin vtk here** or the two constraint sets will fight" [L]. The unpinned `vtk` in `requirements-web.txt` is the same package from the same resolver; pinning either one by hand re-creates the conflict that note exists to prevent.

## 7. The three warnings a reader must carry

**(a) The entire GUI layer is unverified by default.** trame, pyvista and vtk are *declared but were never installed in the build container*, so the server, layout, slider callbacks and panel placement have **never rendered** — the module docstring says so at `server/poc_app.py`:49-55 [L]. This is not "untested edge cases"; it is "never executed once". Verify before debugging.

**(b) The dumps are not in git; the run records are.** `.gitignore` has **no** `artifacts/` rule, but it does have a blanket `*.npz` with only `!tests/data/*.npz` exempted [L]. Consequence: `artifacts/vis_dump_1500.npz` and `artifacts/vis_dump_selftest.npz` are **local, uncommitted** files; what is committed beside them is the JSON/text run record (`artifacts/vis_run_1500.json`) and the scripts. A fresh clone therefore has the *record* of the dump and not the dump. Regenerate with `--wavedude-dump` (or `--selftest` for the synthetic one); do not assume the file travels.

**(c) Where the browserless debugging fallback actually is — a corrected statement.** An earlier note in circulation claimed there is **no** `--dump-state` flag and that the fallback is only the run-record JSON. That is **half wrong and should not be repeated** [L]:

- On the **writer**, `evidence/termination/run_build_A.py` has **no** `--dump-state` — true, and nobody should hunt for one there.
- On the **reader**, `server/poc_app.py` **does** have `--dump-state PATH` (`:3941-3949`), described as *"write a JSON snapshot of everything the viewer knows and exit (numpy only, no pyvista, no trame)"*, alongside `--list-keys` (`:3935-3939`) and `--fps` (`:3953-3962`). So the debugging fallback is a **real flag on the app**, not an absence.

Correct model, in one sentence: **the writer's record is the run-record JSON (`artifacts/vis_run_*.json`); the reader's record is `--dump-state` plus the numpy-only loader; neither requires a browser and neither requires the other.**

## 8. Unverified / open — what not to assume

1. **The player has never run.** Every browser-side behaviour — rendering, camera, slider callbacks, panel placement, play/pause — is unverified (§7a). Do not treat a described feature as a working one.
2. **No dump is proven to have been rendered.** The `.npz` files exist and their loader is numpy-only testable, but nothing in the tree records a successful **render** of `ez_ycut`, `ez_near` or `ez_far`. Whether the camera, the axis orientation and the mm/ns axes are right is an open question, not a known one.
3. **No commit ties to a record.** `artifacts/vis_run_1500.json`:208 carries `"git_rev": null` [L], so the 1500-step run is tied to a file, not a revision (the DR-28 shape).
4. **The budget is a plan, not a guarantee.** 45.0 MB is enforced by raising the stride *before* the march; the observed 10.2 MB file is well under it, but no measurement here shows what happens at the boundary.
5. **`nt_x == ceil(nt / 10)` is the stated relationship, not a checked one in this document.** A reader comparing x-cut and y-cut frame counts should read `dump_stride` and `nt_x` from the file rather than recompute from `--nsteps`.
6. **This document does not ratify a library.** The six packages are declared; the two-constraint note (§6) is the only dependency ruling made here, and it is the repository's ruling, quoted.
