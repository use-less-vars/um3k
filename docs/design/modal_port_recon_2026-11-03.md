# Modal port wiring — recon 2026-11-03

## What this is for

Where a modal launch would replace the lumped launch in `microstrip_wave`, and whether that
plane meets `ModalPort.from_mode2d`'s precondition. Read-only; re-verified in the last section.

## Q1 — Launch construction (`emfit/studies.py:2837-2847`)

```python
js = np.clip(js, ix_port + 1, nx - 2)                                     # 2837
station_x = js * cell                                                     # 2842
columns = [column_path(cc, int(ix), j_centre, 0, k_strip) for ix in js]    # 2843
port_column = column_path(cc, ix_port, j_centre, 0, k_strip)              # 2844
port = LumpedPort("line", port_column, z0=MS_Z0_NOMINAL)                  # 2845
port_edges = np.unique(np.concatenate(
    [column_path(cc, ix_port, int(j), 0, k_strip) for j in range(j0, j1 + 1)]))  # 2846-2847
```
`port_edges` is a flat edge-index array over the full strip width; `port` is used once, at `:2941`.

## Q2 — What the launch is (`studies.py:2905-2936`)

```python
current = np.zeros(cc.n_edges, dtype=float)                               # 2908
for n in range(nsteps):                                                   # 2919
    current[:] = 0.0                                                      # 2924
    if excite == "pulse":
        drive_now = float(drive)*float(ricker(n*dt, 2.0/f_pulse, f_pulse)) # 2930-2931
        current[port_edges] = drive_now                                   # 2932
    else:
        ramp = min(1.0, (n + 1) / max(n_warm, 1))                         # 2934
        current[port_edges] = float(drive)*ramp*np.sin(2.0*np.pi*f0*n*dt) # 2935
    stepper.step(current)                                                 # 2936
```
Docstring `:2454-2456`: "The port is a lumped current source on the ``E_z`` edges that span the
substrate across the whole strip width at the port plane, ramped on over the warm-up ...". Zeroed at
`:2924` and re-prescribed each step → **hard prescribed** current. `evolve.py:186 step(self, j=None)`
takes "an optional current vector [A] on the primal edges" and does `ce = ce - j` (`:195-196`).

## Q3 — Signature and only caller

`studies.py:2339-2381`, keyword-only (`*` at `:2340`), ~35 kwargs; **no** `mode`/`mode_2d`/
`port_kind`/launch kwarg. Args `:2471-2568` (`drive` `:2496` "Source amplitude [A].", `excite`
`:2525`); Returns `:2570`; Raises `:2573-2577`. Only caller `evidence/termination/run_build_A.py:393-411`
(`:1172`, `:1203`); `check_mesh` (`:287-311`) needs `n_top == n_pml`.

## Q4 — Plane mesh vs `from_mode2d`'s precondition

`studies.py:2670-2674`: `ny = 2*n_pml + n_strip + n_clean_lo + n_clean_hi`, `nz = n_sub + n_air +
n_top`, `Grid.uniform(...)` → `CellComplex(grid)` (`cell = h/n_sub` `:2651`, `ix_port = n_pml + n_ref`
`:2680`; default 62x44x22). Nothing from `modal`/`mode2d`/`mode_profile` is imported — no 2-D mesh.
`modalport.py:194 from_mode2d(cls, mode, cc, axis, index)` reads `mesh = mode.mesh`, `axes2 =
`getattr(mesh, "grid_axes", ())` (`:213`), raises "this mesh has no grid_axes" (`:215-219`), needs
`np.allclose(c1, axes2[0], rtol=0.0, atol=1e-12*span)` (`:224-231`), then `mode.e_t` + `mesh.nodes`/
`mesh.edges` (`:257-258`). `ModeProfile` is `@dataclass(frozen=True)` (`:228`) with `phi/e_y/e_z/h_y/h_z`
+ `plane_window()` (`:316`) — **no `.mesh`, no `grid_axes`**; section `ny = 2*n_clean + n_strip`,
`nz = n_sub + n_air` (`:447-468`).
Working alternative: `modal_harness.py:67 build_mode_plane(cc, *, h, w, eps_r, n_sub, k_strip,
iy_strip_centre, n_clean, n_air, check=False)` (`:82`) → `modal.py:267 plane_mode(mode, *, nyn, nzn,
k_strip, iy_strip_centre, cell) -> PlaneMode` carrying `e_y (nyn-1, nzn)`, `e_z (nyn, nzn-1)`.
Injection idiom: `modalport.py:316 inject(self, strength, shape=None)` → an `n_edges` current
vector, used as `st.step(j=src.inject(1.0, shape=_drive(...)))` (`tests/test_modalport.py:428`).

## Q5 — Test surface

`pytest tests/test_studies.py --collect-only -q -o addopts=""` → "42 tests collected"; no name
mentions launch/mode/source. `microstrip_wave` touched at `:243`,`:344`,`:361`,`:384`,`:422`,`:600`,
`:1189`,`:1221`,`:1598-1622`, plus `test_poynting.py:127-145`, `test_plane_capture.py:74`, `test_board.py:106/:206/:576`. Modal code only via `test_modalport.py` / `test_d583_harness.py`.

## Preconditions and risks

- `cc.grid.y`/`cc.grid.z` are uniform node arrays, so `mode2d.structured_mesh(cc.grid.y, cc.grid.z)`
  satisfies `from_mode2d` — what is missing is construction, not regularity.
- `ModeProfile` covers a smaller rectangle (no PML, no `n_top`) → index shift or re-sectioning;
  a new kwarg must default to today's lumped launch, and `n_top == n_pml` must still hold.

**The wiring site is `emfit/studies.py:2837-2847` (launch construction) with per-step injection at `emfit/studies.py:2918-2936`. The current launch is a hard prescribed total current, `drive * ramp * sin(2*pi*f0*n*dt)` (or a Ricker pulse), written onto every `E_z` edge of the single `ix_port` column spanning the substrate across the full strip width. The 3D port plane mesh does not satisfy `from_mode2d`'s structured-rectangle precondition today, because `microstrip_wave` never builds a 2-D cross-section mesh at all and the ready-made profile (`mode_profile.ModeProfile`) carries no `.mesh`/`grid_axes` and covers a different rectangle (`ny = 2*n_clean + n_strip`, `nz = n_sub + n_air`) than the study plane (`ny = 2*n_pml + n_strip + n_clean_lo + n_clean_hi`, `nz = n_sub + n_air + n_top`, 44 x 22 by default) — although `cc.grid.y`/`cc.grid.z` are themselves uniform node arrays, so the precondition is satisfiable by constructing `mode2d.structured_mesh(cc.grid.y, cc.grid.z)`.**

## Verification pass (independent)

1. **C1 CONFIRMED** — quoted above; only `station_x`/`columns` numbers were misreported
   (`:2842`/`:2843`, not `:2839`/`:2840`). Zero `:2924`, assign `:2932`/`:2935`, `step` `:2936`.
2. **C2 CONFIRMED** — `mesh = mode.mesh`; `getattr(mesh, "grid_axes", ())`; `ModeProfile` has no
   `mesh`/`grid_axes` field (the only `mesh` hits in `mode_profile.py` are prose and `_section`).
3. **C3 CONFIRMED, with a gap** — `build_mode_plane` → `plane_mode` is real, but returns a `PlaneMode`
   of field *arrays*, not the flat per-edge vector `ModalPort` validates against `_plane_geometry["edge"]`.
4. **C4 FALSE as stated** — `port` is used once: `signals[n_stations] = port.voltage(stepper.e)`
   (`:2941`). Nothing divides by `port.z0` (`ports.py:180-188`); `s21` uses `station_fit.z0` (`:3305`).
5. **C5 CONFIRMED** — `step(self, j=None)` does `ce = ce - j`; `step(current)` already passes a full `n_edges` vector, so `evolve.py` need not change.

### The decisive question

**YES.** `stepper.step` already takes a full `n_edges` vector, so: (1) add one optional kwarg (e.g.
`launch="lumped"`); (2) call `modal_harness.build_mode_plane(cc, h=h, w=w, eps_r=eps_r, n_sub=n_sub,
k_strip=k_strip, iy_strip_centre=j_centre, n_clean=n_clean_lo, n_air=n_air)` for a `PlaneMode`;
(3) flatten its `e_z`/`e_y` onto the plane's edge indices with the `column_path` helpers already in
`studies.py`; (4) pass that vector to `ModalPort.from_profile(cc, "x", ix_port, e_profile)` and swap
`:2932`/`:2935` for `current = modal_port.inject(drive * ramp, shape=np.sin(...))`. No edit to
`modalport.py`, `mode2d.py`, `mode_profile.py` or `evolve.py`; only `from_mode2d` stays unreachable,
since it needs a `Mode2D` from a `mode2d` solve (mesh + PEC setup) that nothing here builds.
