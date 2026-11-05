# openEMS vs emfit cross-check — pre-registration and validation logic

**Status: PRE-REGISTRATION. No script exists yet (`cross_check.py` is the next dispatch). No openEMS run has been performed for this cross-check.** Every number below is either re-read from a file in this workspace this dispatch (cited by path and JSON key path) or quoted as a threshold fixed *in advance* by the operator. Where the dispatch text and a file disagree, the file wins and the disagreement is listed in §10.

Date: 2026-11-05. Frequency of interest: **5.827786408327286e9 Hz, one frequency, CW.**

---

## 1. Purpose (S1)

Take one load-free microstrip cross-section, solve it in an **independent** FDTD engine (openEMS, commit `5fecbb5`, reference API copied read-only into `infra/openems/reference/`), and compare four published quantities against emfit:

| # | Quantity | openEMS leg | emfit leg (a): FDTD | emfit leg (b): static |
|---|---|---|---|---|
| 1 | β [rad/m] | own DFT at f0 | `line.beta` / cross-run raw phase | — |
| 2 | ε_eff [-] | derived from β | `line.eps_eff` | `quasistatic.z0_eps_eff` |
| 3 | Z0 [Ω] | own port/line extraction | `line.z0_re/z0_im` | `quasistatic.z0_eps_eff` |
| 4 | S-params | \|S11\|, \|S21\| at f0 | `s11.magnitude`, `s21.magnitude` | — |

The point is **not** to add a second solver to the ensemble. It is to test whether the 2.7–4.2 % excess that every emfit *station-fit* β carries over the closed form (`docs/design/beta_drift_analysis_2026-11-05.md`; `build_B_100ohm_v3d_p51_twin.json` `/line/beta` 232.73432451555712 against `/line/beta_model` 223.35306683909533) is a property of the *geometry* or of *emfit's extraction*. An independent engine that disagrees with emfit in the same direction is evidence about the mesh; one that agrees with the closed form is evidence against the extraction.

**Single frequency, stated once and not revisited.** `emfit/studies.py:1209` `MS_EXCITE = "cw"` is the default excitation, and `emfit/studies.py:1206-1208` says explicitly that `"cw"` is the historical single tone and that the default is the tone "so every number this study has ever quoted stays as it was". Every record quoted in §2 carries `geometry/excite = "cw"` and a single `geometry/f_hz = 5827786408.327286`. `board_poc/A_microstrip.json` `/metrics/drive frequency` reads `5.8278 GHz (asked 6.0000 GHz, snapped to a DFT bin)`, i.e. the drive is 5.8278 GHz because that is the DFT bin nearest the 6.0 GHz ask (`MS_F_TARGET = 6.0e9`, `emfit/studies.py:1163`), not because a band was swept. **This cross-check is one tone against one bin. There is no sweep and no band in it.** (`emfit/studies.py:1212-1240` defines the pulse/broadband path; that path is not exercised by any record in §2 and is not part of this cross-check.)

---

## 2. Data legs — re-verified from the files this dispatch (S1)

All values below were read by `python3 json.load(...)` this dispatch. Path relative to `/workspace`.

### 2.1 The emfit FDTD twin series (load-free, `dx = dy = dz = 0.4 mm`)

| Record | `geometry/grid` | `geometry/n_line` | `line/beta` | `line/eps_eff` | `line/z0_re + j z0_im` | `s11.magnitude` | `s21.magnitude` |
|---|---|---|---|---|---|---|---|
| `evidence/termination/build_B_100ohm_v3d_p51_twin.json` | 62×212×22 | 54 | 232.73432451555712 | 3.6307412162627744 | 50.232513848351594 + 15.5031195552717j | 0.003495904618551106 | 0.9875698346936435 |
| `evidence/termination/build_A_50ohm_twin_p51_twin.json` | 72×212×22 | 64 | 231.0873600620821 | 3.5795365321344415 | 49.4259949734449 + 16.33275604971187j | *not re-read* | *not re-read* |
| `evidence/termination/build_E_50ohm_v3d_twin.json` | 87×212×22 | 79 | 229.49183675350866 | 3.5302779521649104 | 50.767059791451885 + 16.32700128697807j | 0.0029754120466321684 | 1.0022374837446273 |

Common to all three: `geometry/cell` 0.0004 m, `geometry/w` 0.0032, `geometry/h` 0.0016, `geometry/eps_r` 4.4, `geometry/n_pml` 6, `geometry/n_sub` 4, `geometry/n_air` 12, `geometry/n_top` 6, `geometry/n_strip` 8, `geometry/n_ref` 2, `geometry/ix_port` 8, `geometry/excite` `"cw"`, `geometry/f_hz` 5827786408.327286, `geometry/nsteps` 2400, `run/kwargs/n_clean` 96.

Derived (arithmetic done here, from the numbers in the table): β above `line/beta_model` 223.35306683909533 by **+4.200 % / +3.463 % / +2.748 %** for B / A / E; ε_eff above `line/eps_eff_model` (3.3439383100189377 / same / same) by **+8.58 % / +7.05 % / +5.56 %** — note ε_eff moves twice as fast as β, because `line/eps_eff` is `(beta*C0/(2*pi*f))**2` (`emfit/studies.py:3543`). **|S11| in dB: B −49.13 dB, E −50.54 dB** (`20*log10` of the magnitudes above).

| `s11.magnitude` → dB | record |
|---|---|
| −49.13 dB | `build_B_100ohm_v3d_p51_twin.json` |
| −50.54 dB | `build_E_50ohm_v3d_twin.json` |

The A twin's S-params are the one cell in this table not re-read: the read script aborted on the *loaded* file of nearly the same name before reaching it (§10, item 1). The script must read them; nothing in the pre-registration depends on their values.

### 2.2 The board report record (independent emfit run, different lateral box)

`evidence/board_poc/A_microstrip.json`, `values/load_kind = "none"`, `/metrics/mesh` = `62 x 44 x 22 cells at 0.4000 mm`, `/metrics/box` = `24.80 x 17.60 x 8.80 mm`.

| Quantity | Value | Key |
|---|---|---|
| β, one-wave fit | 232.447 rad/m | `/metrics/beta (one-wave fit)` |
| β, two-wave fit | 232.558 rad/m | `/metrics/beta (two-wave fit)` |
| β, two stations | 232.493 rad/m | `/metrics/beta (two stations)` |
| **β range quoted for this leg** | **232.45 – 232.56 rad/m** | the three keys above |
| ε_eff (from this run's β) | 3.62178 | `/metrics/eps_eff` |
| β, Hammerstad–Jensen | 223.353 rad/m | `/metrics/beta (Hammerstad-Jensen)` |
| \|S11\| (measured plane = port plane) | −42.52 dB (0.00748) | `/metrics/|S11| at the measured plane` |
| \|S21\| between station planes | 0.981263 (−0.164 dB over 9.60 mm) | `/metrics/|S21| between station planes` |
| port Z, real part / modulus / phase | 50.954 Ω / 53.368 Ω / 17.299° | `/metrics/port Z, real part`, `…, modulus`, `…, phase` |
| line Z0 from stations, real part / modulus | 50.5474 Ω / 50.7073 Ω | `/metrics/line Z0 from stations, real part`, `…, modulus` |
| line Z0, Hammerstad–Jensen | 48.099 Ω (t = 0.035 mm) | `/metrics/line Z0 (Hammerstad-Jensen)` |

Note for the script: this record's lateral count is **44**, not 212 (`MS_N_CLEAN = 12` at `emfit/studies.py:1199` gives `ny = 2*6 + 8 + 12 + 12 = 44`, `emfit/studies.py:2821`), whereas the twins pass `n_clean = 96` (`run/kwargs/n_clean`) and land on 212. Two different lateral boxes, same cross-section and same cell — so the twins and the board record are *not* interchangeable as a bracket-D comparator. Use the twins for D; use the board record only as a third β opinion (§2.4).

### 2.3 The closed form and the direct raw-phase β

| Quantity | Value | Source |
|---|---|---|
| β Hammerstad–Jensen | 223.35306683909533 | `line/beta_model` in every twin; `/metrics/beta (Hammerstad-Jensen)` in `A_microstrip.json`; `graded_v2_refix.json` `/criteria/AC-7/reference_spread/beta_hammerstad` |
| **β direct raw phase** | **223.58131180256908** | `graded_v2_refix.json` `/criteria/AC-7/achieved/beta_fdtd_rad_per_m` |
| Δraw phase it came from | −128.1026554428571° | `/criteria/AC-7/achieved/delta_raw_phase_deg` |
| dL it was divided by | 0.010000000000000002 m | `/criteria/AC-7/achieved/dL_m`, `dL_from` = "s21.planes_m[1] of E minus that of A" |
| Branch check | λ_g/2 = 13.8207 mm > dL = 10 mm, `branch_unambiguous: true` | `/criteria/AC-7/achieved/branch_note`, `…/branch_unambiguous` |
| β mode_profile (2-D eigen, second closed reference) | 227.31018858464796 | `/criteria/AC-7/reference_spread/beta_mode_profile` |
| direct raw phase vs Hammerstad | +0.102 % | `/criteria/AC-7/achieved/rel_error_vs_hammerstad` = 0.0010219020795365688 |
| direct raw phase vs mode_profile | −1.640 % | `/criteria/AC-7/achieved/rel_error` = 0.016404353915224042 |

Re-verified independently this dispatch from the two source records: `build_A_50ohm_v2.json` `/s21/raw_phase_rad` 2.381603550187504 (136.4558°), `build_E_50ohm_v2.json` `/s21/raw_phase_rad` 0.14579043216181267 (8.3532°), `/s21/planes_m` [0.0032, 0.02] and [0.0032, 0.03]; difference −2.2358131180256913 rad over 0.01 m = 223.58131 rad/m. \|β·dL\| = 2.236 < π, so the wrap is the identity and the number is a *measurement of one period*, not a branch choice.

**Why this number is the emfit reference for bracket A, and not `line/beta`:** it is the cross-run slope of the **raw** phase (`/criteria/AC-7/which_phase`: "NOT `s21.phase_rad`: that phase is de-embedded with each run's own measured beta"). It touches no fitted β, no station fit, and no de-embedding; the de-embedded slope over the same span is 240.776 rad/m (`/criteria/AC-7/achieved/deembedded_slope_rad_per_m`), which is NOT a measurement of the line and must never be compared to openEMS. **A record's `line/beta` is not the geometry's β** — the loaded siblings of this same cross-section carry 286.36 / 286.87 / 173.41 while every load-free twin sits at 229.5–232.7 — so the script must name the record for every β it quotes.

### 2.4 The four β opinions on one cross-section, side by side

| Opinion | β [rad/m] | vs Hammerstad 223.353 | Source |
|---|---|---|---|
| Hammerstad–Jensen | 223.35306683909533 | 0.000 % | `line/beta_model` |
| direct raw phase, cross-run | 223.58131180256908 | +0.102 % | `graded_v2_refix.json` AC-7 |
| mode_profile 2-D eigen | 227.31018858464796 | +1.772 % | AC-7 `reference_spread` |
| emfit station fit, n_line 79 (E twin) | 229.49183675350866 | +2.748 % | `build_E_50ohm_v3d_twin.json` |
| emfit station fit, n_line 64 (A twin) | 231.0873600620821 | +3.463 % | `build_A_50ohm_twin_p51_twin.json` |
| emfit station fit, board record 62×44×22 | 232.447 – 232.558 | +4.07 % | `A_microstrip.json` (+4.07 % is the record's own `/metrics/beta, fit vs model`) |
| emfit station fit, n_line 54 (B twin) | 232.73432451555712 | +4.200 % | `build_B_100ohm_v3d_p51_twin.json` |

The spread of the station fit is a **function of line length** (−0.324 rad/m per mm of added line, `docs/design/beta_drift_analysis_2026-11-05.md`), and it lands on the *same* value for two different lateral boxes at the same length (232.45–232.56 at 54 cells; 232.73 for the 212-lateral twin at the same 54 cells). That is the pattern a mesh artefact makes, and it is what openEMS is being brought in to adjudicate.

---

## 3. Geometry, in metres and in cells (S2)

Source of every number: `emfit/studies.py` (constants block at 1156–1216, mesh at 2820–2834) and the records' own `geometry/` blocks. `h/n_sub` is the cell; there is exactly one cell size in the mesh.

| Quantity | Metres | Cells | Source |
|---|---|---|---|
| strip width w | 3.2e-3 | 8 (= `n_strip`) | `emfit/studies.py:1159` `MS_W`; `:1197` `MS_N_STRIP`; records `geometry/w`, `geometry/n_strip` |
| substrate thickness h | 1.6e-3 | 4 (= `n_sub`) | `emfit/studies.py:1157` `MS_H`; `:1188` `MS_N_SUB`; `geometry/h`, `geometry/n_sub` |
| ε_r | 4.4 | — | `emfit/studies.py:1161` `MS_EPS_R`; `geometry/eps_r` |
| cell (x = y = z) | 0.4e-3 | 1 | `geometry/cell` 0.0004; `emfit/studies.py:1186-1188` ("Four cells over 1.6 mm is a 0.4 mm cell: the historical reference mesh") |
| air above strip, below lid | 4.8e-3 | 12 | `emfit/studies.py:1190` `MS_N_AIR`; `geometry/n_air` |
| top matched layer | 2.4e-3 | 6 | `emfit/studies.py:1195` `MS_N_TOP`; `geometry/n_top` |
| matched layer, other faces | 2.4e-3 | 6 | `emfit/studies.py:1176` `MS_N_PML`; `geometry/n_pml` |
| strip | 3.2e-3 | 8 | `emfit/studies.py:1197` |
| port plane behind the layer | 0.8e-3 | 2 | `emfit/studies.py:1201` `MS_N_REF`; `geometry/n_ref` |
| port plane from the back wall | **3.2e-3** | **8** | `emfit/studies.py:2830` `ix_port = n_pml + n_ref`; `geometry/ix_port` 8 |
| line: port plane → far PEC end (default) | 21.6e-3 | 54 | `emfit/studies.py:1203` `MS_N_LINE`; `geometry/n_line` |
| line, longest twin | 31.6e-3 | 79 | `build_E_50ohm_v3d_twin.json` `geometry/n_line` 79 |
| lateral extent, twins | 84.8e-3 | 212 | `geometry/ny`; `emfit/studies.py:2821` with `n_clean = 96` |
| vertical extent z | 8.8e-3 | 22 | `emfit/studies.py:2822` `nz = n_sub + n_air + n_top`; `geometry/nz`, `geometry/height` 0.0088 |
| length x, twins | 24.8e-3 … 34.8e-3 | 62 / 72 / 87 | `geometry/nx`, `geometry/length`, `emfit/studies.py:2820` `nx = n_pml + n_ref + n_line` |
| strip centre, y | — | `j_centre = 106` | `geometry/j_centre`; `emfit/studies.py:2834` |
| strip node layer, z | 1.6e-3 | `k_strip = n_sub = 4` | `geometry/k_strip`; `emfit/studies.py:2831` |

**openEMS uses the same 0.4 mm cell.** The cross-check is only a cross-check if the two engines are asked the same discrete problem, and the 0.4 mm cell is the number every record in §2 was produced at. openEMS brings its own mesher (`csx.GetGrid()` / `SetLines`, `docker/openems/smoke_solve.py:79-83`; `infra/openems/reference/CSXCAD.pyx`), so the faithful choice is a **uniform 0.4 mm line lattice in x, y and z** over the same extents, with the strip and substrate landing on node planes exactly as §3 says. Any refinement or grading is a *second* experiment and must be registered separately — a finer openEMS mesh that agrees with the closed form would not distinguish "emfit's mesh is coarse" from "emfit's extraction is biased", which is the whole question.

The matched layers cost 6 cells (2.4 mm) on each face, so the physical box openEMS must reproduce is 0.4 mm × (nx − 12) × (ny − 12) × (nz − 12) cells of interior. For the B twin: 50 × 200 × 10 cells interior over 20 × 80 × 4 mm.

---

## 4. Excitation and extraction (S3)

| Item | Requirement | Why / source |
|---|---|---|
| Source | **modulated Gaussian centred at f0 = 5.827786408327286e9 Hz**, `SetGaussExcite(f0, fc)` with **fc ≈ 2e9 Hz** | `infra/openems/reference/openEMS.pyx:257` `SetGaussExcite(self, f0, fc, dc_free=False)` |
| Never baseband | **fc must be well above 0.** A baseband Gaussian (fc = 0, or fc ≈ f0 with dc content) leaves a static near field that does not decay | `docker/openems/smoke_solve.py:96-100`: "This case uses a BASEBAND Gaussian (fc == f0 == 1 GHz) … which leaves a static near-field residual: measured energy floor is −18.58 dB and it never crosses −60 dB". That residual is DC on the port records and biases a DFT bin at f0. If `fc` alone does not remove it, `dc_free=True` is available at `openEMS.pyx:257`. |
| Record | one run, one tone, **DFT at exactly f0** | §1. A broadband transform of the same record is a different experiment. |
| Sweep | **none** | §1 |
| Termination criterion | `FDTD.SetEndCriteria(10 ** (-15 / 10))` — a **LINEAR** energy ratio, which the solver prints as `10*log10` | `docker/openems/smoke_solve.py:109`, with the same statement at `:105-108`: "SetEndCriteria() takes a LINEAR ratio; the solver renders it as 10*log10(ratio) (its default 1e-6 is reported as −60 dB)". `openEMS.pyx:131`. A run that asks for "−15 dB" by passing 15 or −15 asks for nothing. |
| Iteration cap | `FDTD.SetNumberOfTimeSteps(5e4)` — belt and braces | `docker/openems/smoke_solve.py:113`; setter at `openEMS.pyx:124`. **There is NO `max_timesteps` kwarg and NO CLI flag for it** — `smoke_solve.py:111-112`: "There is no max_timesteps Run() kwarg (openEMS 5fecbb5 has no such CLI option); the cap is the SetNumberOfTimeSteps() setter (1e9 by default)". Do not write `Run(..., max_timesteps=...)`. |
| Boundary | six-element list; **`PML_8` is not the choice here** — it means *8 cells per side*, and this mesh is 6 | `openEMS.pyx:310` `SetBoundaryCond`, `:320`, `:333-334` (`if BC[n].startswith('PML_'): size = int(BC[n].strip('PML_'))`). The emfit side uses 6 cells (`MS_N_PML`). **`ports.pyx` was not copied into `infra/openems/reference/`, so the exact spelling/limits of the PML boundary token must be verified against `openEMS.pyx` before use, not from memory.** |
| Ports | `AddMSLPort(port_nr, metal_prop, start, stop, prop_dir, exc_dir, excite=0, **kw)` | `openEMS.pyx:425` (docstring at `:426`). Same warning applies: the `**kw` (feed resistance, reference plane, ref impedance) lives in `openEMS.ports.MSLPort` — `openEMS.pyx:436` — and `ports.pyx` is **not** in the reference copy, so **the kwargs must be verified against `openEMS.pyx`/the installed module before the script relies on any of them.** |
| Grid | explicit, metres, via `csx.GetGrid()`; `csx.DefineGrid()` is broken in CSXCAD 0.6.2 and there is no auto-mesh | `docker/openems/smoke_solve.py:77-83` |
| numpy shim | map `np.float/int/complex/bool` before importing openEMS | `docker/openems/smoke_solve.py:47-52` — otherwise every `AddLumpedPort`/`AddMSLPort` call dies with "'module' object has no attribute 'float'" |
| Run | `FDTD.Run(OUTDIR, cleanup=True, verbose=1, numThreads=n)` | `docker/openems/smoke_solve.py:116`, `openEMS.pyx:655` |

`docker/openems/smoke_solve.py` is the **proven pattern** — it is the one file in this repo that has been shown to make openEMS 5fecbb5 execute end to end (its `:32-39` block records a measured run: ~3 min, `port_ut_1` 1207446 B, header written by the C++ binary). It is not a microstrip and not physics (`:9-14` says so explicitly: "A later unloaded-line / microstrip cross-check must build its own model and must not treat this file as a validated example"). Copy its *plumbing*, not its geometry.

The extraction the script needs is the one every openEMS MSL example uses and which `smoke_solve.py` does not do: per-port `port_ut_i`/`port_it_i` time series → DFT at f0 → `S11 = (u1 - R·i1)/(u1 + R·i1)`-style power-wave normalization against the port's own reference impedance, and `S21` from the two forward waves. Which reference impedance openEMS reports for an MSL port is exactly what must be read out of `ports.pyx` (not available) — hence the §5 gate exists: **the script must not compare an S-parameter before it has shown that the engine is solving the right problem.**

---

## 5. Stage 1 — THE TRUST-MAKER: the static gate, fail-fast, before any S-param comparison (S4)

This is the load-bearing stage. If openEMS and the static solve do not agree on the DC cross-section, then nothing downstream is interpretable — a disagreement in β would have at least two candidate causes (extraction, mesh) instead of one, and the S-parameters would be noise about a geometry neither engine agrees on. So the gate runs **first, out of process order, and ABORTS** (`sys.exit(nonzero)`, no partial verdict written) on failure.

### 5.1 The API, verified line by line

`emfit/quasistatic.py`, 352 lines, 14451 bytes.

| Symbol | Line | Signature / meaning |
|---|---|---|
| `__all__` | 75 | `capacitance_per_length`, `z0_eps_eff`, `transverse_potential`, `node_index`, `node_shape` — **the public surface; `_solve`, `_dirichlet`, `_transverse_metric` are private** |
| `node_shape` | 116 | `(grid) -> (N1, N2)`, the transverse point-layer counts in `xyz` order |
| `node_index` | 127 | `(grid, iy, iz) -> int`, flat index `iy*N2 + iz`; raises outside `[0, N1) × [0, N2)` |
| `capacitance_per_length` | 276 | `(grid, eps_r=1.0, fixed=None) -> float` — `phi^T K phi / (V^2 * length)` |
| `transverse_potential` | 323 | `(grid, eps_r=1.0, fixed=None) -> ndarray` shaped `node_shape` |
| `z0_eps_eff` | 334 | `(grid, eps_r=1.0, fixed=None) -> (Z0, eps_eff)` |

`fixed` is `[(potential, node_indices), ...]`, at least two distinct potentials (`:288-291`), nodes from `node_index`, outer walls homogeneous Neumann.

### 5.2 The physics, as the module states it

| Statement | Line |
|---|---|
| `C' = phi^T K phi / (V^2 * length)` [F/m] | `:18` |
| `length` is the cell width along the line axis, read from the grid, never chosen by the caller | `:20-24`, `:253-260` |
| `eps_eff = C'/C'_air`, `Z0 = 1/(C0 * C'_air)` | `:25-26` |
| implementation: `return np.sqrt(eps_eff) / (C0 * c_line), float(eps_eff)` with `c_air` solved at `eps_r = 1.0` | `:350-352` |
| `Z0 = Z0_air / sqrt(eps_eff)` holds by construction; **no dispersion** | `:60-62` |
| conductor thickness and finite conductivity are not modelled | `:55-58` |

Note `Z0` comes back as a **plain float** (`float(eps_eff)` for ε_eff, and the Z0 expression is real arithmetic on real scalars). That has a consequence the gate must encode — §5.4.

### 5.3 The constraint the caller must satisfy — the guard code, verbatim

`emfit/quasistatic.py:95-112`, inside `_line_and_transverse`, which every public entry point calls first:

```python
    if not isinstance(grid, Grid):
        raise ValueError(
            f"grid must be an emfit.grid.Grid, got {type(grid).__name__}"
        )
    periodic = [a for a in "xyz" if grid.is_periodic(a)]
    if len(periodic) != 1:
        raise ValueError(
            "exactly one axis must be periodic (the line axis), got "
            f"periodic={grid.periodic!r}"
        )
    line = periodic[0]
    thick = grid.shape["xyz".index(line)]
    if thick != 1:
        raise ValueError(
            "the grid must be one cell thick along the periodic line axis "
            f"{line!r}, got {thick} cells"
        )
```

with the docstring (`:28-31`): "The grid must be **one cell thick and periodic along the line axis** -- exactly one entry of `grid.periodic` may be `True`."

**Consequences for the script, stated because they are easy to get wrong:**

1. **You cannot pass `(w, h, eps_r)`.** The call is `z0_eps_eff(grid, eps_r_callable_or_float, fixed)`; the geometry enters only through a `emfit.grid.Grid` you build yourself (`emfit/grid.py:76` `Grid.uniform(nx, ny, nz, lx, ly, lz, origin=..., periodic=...)`).
2. **The section grid is not the FDTD grid.** The FDTD twin is 62×212×22 with the line along x; the section is `1 × ny × nz` with `periodic=(True, False, False)`, i.e. the line axis collapsed to one cell → transverse pair `(y, z)`. This is exactly what `emfit/mode_profile.py:467-469` does:
   ```python
   grid = Grid.uniform(
       1, ny, nz, cell, ny * cell, nz * cell, periodic=(True, False, False)
   )
   ```
   and its conductor list (`emfit/mode_profile.py:473-484`) is the pattern to copy: whole bottom row at 0 V, `n_strip + 1` nodes at `k = n_sub` at 1 V.
3. **`node_index(grid, iy, iz)` names the *transverse* indices in `xyz` order** — for a line along x that is `(y, z)`, so `iy` is a y index and `iz` a z index. They are not FDTD `j`/`k` offsets: the section's y origin differs from the FDTD box's (`n_clean` vs `n_pml + n_clean`).
4. Interfaces must sit on node planes (`:48-52`) — they do here: substrate top at `k = n_sub = 4` = 1.6 mm, exactly `h` (`emfit/mode_profile.py:475-483`, "sits on the node plane `k = n_sub` so the substrate interface is exactly resolved").
5. The Neumann walls must be "pushed out until the answer stops moving" (`:58-59`). The measured plateau for this exact cross-section is `n_clean = 200`, `n_air = 200` → 43.0 × 21.6 mm, 431 × 217 nodes, giving **ε_eff 3.35001 and Z0 50.088 Ω, i.e. +0.74 % / +1.04 % off Hammerstad–Jensen**, with residual drift 0.3 % per 5 mm of wall (`emfit/mode_profile.py:588-596`). A box sized to the FDTD plane is "4-5 % high" by the same note. **The gate must therefore run the static solve on the converged box, not on the FDTD box** — otherwise the gate's own 5 % bar is being spent on a wall artefact.

### 5.4 The complex-vs-real trap, and which statistic the gate uses

| | emfit FDTD port/line Z0 | emfit static `z0_eps_eff` |
|---|---|---|
| type | **complex** | **real float** |
| why | `z0 = complex(amp_v[0] / amp_i[0])` — ratio of two fitted complex forward amplitudes, `emfit/ports.py:1516`; carried as `complex` at `:1367` | `return np.sqrt(eps_eff) / (C0 * c_line)` on reals, `emfit/quasistatic.py:352` |
| observed | B twin 50.2325 + 15.5031j; A twin 49.4260 + 16.3328j; E twin 50.7671 + 16.3270j; board record 53.368 Ω ∠ 17.299° | order 50.088 Ω ∠ 0° at the converged box |

The +15–16 Ω imaginary part is a **port convention, not loss**: `emfit/studies.py:3545-3552` explains that the raw `V/I` carries a spurious 180° because `plate_current` sums the ground return in its own (antiparallel) sense, and negation refers the impedance to the trace current, leaving an excess phase "about +17 deg here". A lossless quasi-TEM line has a real Z0; a lossless FDTD extraction with a reference plane off the current reference does not.

**Therefore: gate on `Re(Z)`, never on raw complex equality and never on `|Z|` alone.**

- `Re(Z)` is the quantity that carries the impedance; the excess phase is an artefact of where the current is referenced.
- `|Z|` is rejected as the primary statistic because it mixes the artefact in: it is `|Z| = Re(Z)/cos(17.3°)`, so a gate on `|Z|` with a 5 % bar is silently a 5.25 % bar on `Re(Z)` and, worse, would *pass* an engine whose Re(Z) is 4.8 % low purely because a phase error inflated its modulus.
- Raw complex equality is rejected outright: it would compare `50.23 + 15.50j` against `50.09 + 0j` and fail at 34 % on an artefact.

`|Z|` is still computed and reported, as a **diagnostic only**, so that a future port-convention fix can be checked against the record.

### 5.5 Gate thresholds and the abort behaviour

| Gate | Statistic | PASS | ABORT if | Justification |
|---|---|---|---|---|
| G1 | `Re(Z0)` from openEMS vs static `Z0` | within **5 %** | worse than 5 % | The static value is box-dependent by construction: +1.04 % off Hammerstad at the converged box, and "4-5 % high" on an FDTD-sized box (`emfit/mode_profile.py:588-596`). A 5 % bar is the width of that *known* box systematic, i.e. it fails only on a disagreement bigger than the artefact the static solve admits to. Tighter than 5 % would fail on the box, not on the physics. |
| G2 | `eps_eff` from the static solve vs the static solve at the FDTD box | within **3 %** | worse than 3 % | The ε_eff box drift on this cross-section is 0.18 % (3.35001 vs 3.34394) with 0.3 % per 5 mm of wall residual — 3 % is an order of magnitude above the admitted artefact, so a trip means the two grids are not the same problem (wrong `n_sub`, wrong interface node, wrong strip width in cells). |

On failure: **ABORT**, name the disagreeing leg and both numbers, and write no β/ε_eff/Z0/S-param comparison. A failed gate is a statement that the cross-check cannot be run as registered, not a result about either engine.

**Expected values the gate is checked against (from files, not recomputed here):**

| Quantity | Value | Source |
|---|---|---|
| static Z0, converged box | 50.088 Ω | `emfit/mode_profile.py:589-591` |
| static ε_eff, converged box | 3.35001 | `emfit/mode_profile.py:589-590` |
| Hammerstad Z0 | 48.099 Ω | `A_microstrip.json` `/metrics/line Z0 (Hammerstad-Jensen)` |
| Hammerstad β | 223.35306683909533 | `line/beta_model` |
| direct raw-phase β | 223.58131180256908 | `graded_v2_refix.json` AC-7 |
| station-fit β | 229.49 / 231.09 / 232.73 | the three twins |

**ε_eff can never corroborate β independently.** `emfit/studies.py:3543` computes `eps_eff = (beta * C0 / (2.0 * np.pi * f0)) ** 2`, one line below the β it is derived from (the same identity at `:2074`, and `:1565-1567` documents it as "Effective permittivity implied by ``beta``"). Any ε_eff read from a record is β alias √·, so a record cannot be used to check its own β with its own ε_eff, and bracket C (§6) is only meaningful because its left side is derived from **openEMS's** β and its right side from the **static Laplace solve** — two engines, not two columns of one JSON.

---

## 6. Pre-registered brackets (S5)

Fixed before any openEMS number exists. Reproduced as registered.

### A. β agreement

| | |
|---|---|
| Comparison | `\|β_openEMS − β_emfit_direct\| / β_emfit_direct`, with `β_emfit_direct` = **223.58131180256908** (`graded_v2_refix.json` AC-7, cross-run raw-phase slope) |
| PASS | ≤ **2 %** |
| FAIL | > **5 %** — and the extraction bug is **emfit's, not openEMS's** |
| Indeterminate | 2 % – 5 %: report as such; it names neither side |

**Rationale.** The direct raw phase is the one β in this repo that is unambiguous: −128.1026554428571° over dL = 10.0000 mm with `|β·dL| = 2.236 < π` (`/criteria/AC-7/achieved/branch_unambiguous: true`, λ_g/2 = 13.8207 mm against dL = 10 mm), computed from two records' **raw** phases with no fitted β, no station fit and no de-embedding in the path (`/criteria/AC-7/which_phase`). It already sits **+0.102 %** from Hammerstad (`rel_error_vs_hammerstad` 0.0010219). So "the physics" is known to 0.1 % on this geometry, and a 2 % bar is 20× that margin: it passes only if openEMS independently lands on the same value, which is exactly the claim being tested. The 5 % FAIL edge is set at the *largest excess the emfit station fit already carries* (4.200 % at n_line 54): an openEMS number beyond 5 % cannot be an emfit-family value, so it indicts the extraction rather than the mesh.

### B. Z0 trust gate

| | |
|---|---|
| Comparison | `Re(Z0_openEMS)` vs static `Z0` from `emfit.quasistatic.z0_eps_eff` |
| PASS | within **5 %** → continue |
| ABORT | worse than 5 % → **abort before any S-parameter comparison** |
| Never | raw complex equality; `\|Z\|` as the primary statistic (§5.4) |

### C. ε_eff consistency

| | |
|---|---|
| Comparison | ε_eff implied by **openEMS's** β (`(β·c0/2πf)²`, the identity at `emfit/studies.py:3543`) vs the static solve's ε_eff |
| PASS | within **3 %** |

### D. Load-free sanity

| | |
|---|---|
| openEMS | `\|S11\| ≤ −20 dB` **and** `\|S21\| ≥ 0.95` |
| emfit twins | same thresholds: `\|S11\| ≤ −20 dB`, `\|S21\| ≥ 0.95` |
| Either side fails | **the comparison is VOID, not a result** — a line that reflects or attenuates like that is not the matched line this cross-check is about |

Existing emfit evidence for D: B twin `|S11|` 0.0035 → −49.13 dB, `|S21|` 0.98757; E twin `|S11|` 0.002975 → −50.54 dB, `|S21|` 1.00224; board record −42.52 dB / 0.981263. All pass, with margin ≥ 22 dB on S11 and ≥ 3.7 % on S21.

### Decision tree

```
        ┌───────────────────────────────────────────────┐
        │ B. Re(Z0_openEMS) vs static Z0 within 5 % ?   │  ← runs FIRST, gates everything
        └───────────────┬───────────────────────────────┘
             no         │         yes
        ┌───────────────┴───────┐
        │  ABORT                │
        │  name the leg,        ▼
        │  write no S-params    ┌──────────────────────────────────┐
        └───────────────────────│ A. |Δβ|/β_direct ≤ 2 % ?         │
                                └──────┬───────────────────────────┘
                        ≤2 %           │            >5 %
                     ┌─────────────────┴──────────────┐
                     │ PASS                           │ FAIL → cross-check becomes PRIMARY
                     ▼                                │ evidence; the emfit extraction
        ┌────────────────────────────────┐            │ (station fit) is the suspect
        │ C. ε_eff(β_openEMS) vs static  │            │
        │    ε_eff within 3 % ?          │            │
        └────────────┬───────────────────┘            │
                     ▼                                │
        ┌────────────────────────────────┐            │
        │ D. load-free sanity, both sides│            │
        │    |S11| ≤ −20 dB, |S21| ≥ 0.95│            │
        └────────────┬───────────────────┘            │
                     ▼                                ▼
              report the four numbers          report A as the finding
```

Order is B → A → C → D. A FAIL in A does **not** stop C and D: they are what turns "the two engines disagree" into "they disagree about β, and here is what each says about the static cross-section and about the matching".

---

## 7. Pre-flight arithmetic: what each bracket returns against numbers already on disk

This is not a result — no openEMS run exists. It is the arithmetic the registered brackets will perform, so that the script's verdict cannot be a surprise and so that an un-closeable bracket is visible before the solve is paid for.

| If openEMS β lands on… | A vs 223.5813 | C vs static ε_eff 3.35001 | What it would mean |
|---|---|---|---|
| 223.58 (the direct raw phase) | 0.00 % PASS | ε_eff 3.344, −0.18 % PASS | Both engines on the physics; every emfit station-fit β (229.5–232.7) is then an extraction artefact |
| 227.31 (mode_profile) | +1.67 % PASS | ε_eff 3.463, +3.37 % FAIL | the two static routes disagree; the mode_profile eigen is not a static corroboration |
| 229.49 (E twin) | +2.64 % indeterminate | ε_eff 3.530, +5.38 % FAIL | openEMS reproduces the *shortest-line* emfit value; A is undecided, C fails |
| 232.73 (B twin) | +4.08 % indeterminate | ε_eff 3.628, +8.30 % FAIL | openEMS reproduces emfit's mesh artefact in the static route too |

Two things follow and are registered here so they cannot be read as post-hoc:

1. **A cannot FAIL against evidence already on disk** unless openEMS β < 212.4 or > 234.8 rad/m — the emfit family's own spread (223.35–232.73) sits entirely inside A's 0–5 % band. So A's discriminating power is "did openEMS join the emfit family or not", not "which member".
2. **C is the sharper bracket**: it is β-equivalent to 1.49 % (ε_eff moves twice as fast as β), i.e. *tighter* than A's 2 %, and its two sides come from different methods (static Laplace vs FDTD), so it can fail while A passes. §5's gate G2 is the same comparison at 3 % on a *grid* difference; C is the same 3 % on an *engine* difference. **C is expected to be the bracket that fires.** It is registered at 3 % anyway, because 3 % is the width the static solve's own box systematic justifies (§5.5) and a wider bracket would not be a test.

---

## 8. Out of scope (S6)

| Excluded | Why |
|---|---|
| **Loaded / gap geometry** | The cross-check is about the load-free line. A load introduces `reference`, de-embedding and a load plane, i.e. three more things that can disagree; and a loaded record's β is not the geometry's β (loaded siblings: 286.36 / 286.87 / 173.41 vs twins 229.5–232.7). |
| **Field data, animations, any visualisation** | There is **no field data anywhere in this repo**. A recursive key census over all **61** JSONs in `evidence/termination/` found no `Ex`/`Ey`/`Ez`/`Hx`/`Hy`/`Hz`/`fields`/`field_dump` keys — only scalars plus S-parameter phasors. A field image would have to be manufactured from a new emfit run, which is not what this dispatch may do (no solves), and reconstructing one from scalars is not possible. The field gif is therefore **dropped, not deferred**. |
| A frequency sweep, dispersion, group delay | §1: one tone, one bin. |
| Agreement on `Z0` as a complex number, or on port reference conventions | §5.4: the static solve has no phase to agree with. `Im(Z)` is reported as a diagnostic and never gated. |
| Any claim about openEMS's own mesh convergence | §3: uniform 0.4 mm is the registered choice; a refinement study is a separate registration. |

---

## 9. Status, sources, and what must be verified before the script runs (S7)

| Item | Status |
|---|---|
| This document | **The pre-registration.** Written 2026-11-05, before any openEMS run and before `cross_check.py` exists. |
| `cross_check.py` | **Not written.** Next dispatch. Nothing in this document is a measurement. |
| openEMS runs for this cross-check | **None performed.** The only openEMS execution on record is `docker/openems/smoke_solve.py`'s empty-air-box smoke test (`:32-39`). |
| `emfit/quasistatic.py` | 352 lines, 14451 B — read this dispatch; all line numbers above re-verified. |
| `emfit/studies.py`, `emfit/ports.py`, `emfit/mode_profile.py` | read this dispatch at the cited lines. |
| `infra/openems/reference/CSXCAD.pyx` | 597 lines, 20602 B — copied read-only from openEMS `5fecbb5`. |
| `infra/openems/reference/openEMS.pyx` | 735 lines, 28440 B — same; `SetNumberOfTimeSteps` :124, `SetEndCriteria` :131, `SetGaussExcite` :257, `SetBoundaryCond` :310, `AddLumpedPort` :339, `AddMSLPort` :425, `Run` :655. |
| `ports.pyx` | **NOT copied.** `AddMSLPort` delegates to `openEMS.ports.MSLPort` (`openEMS.pyx:436`), so `MSLPort`'s keyword arguments (feed resistance, reference plane, reference impedance) and the exact `PML_n` token handling are **unverified** and must be read out of `openEMS.pyx` / the installed `openEMS.ports` module before the script relies on them. |
| Where the numbers cited from JSON come from | §2: every one is a JSON key path, re-read this dispatch. |

---

## 10. Discrepancies between the dispatch text and the files (the file wins)

| # | The dispatch said | The file says | Ruling |
|---|---|---|---|
| 1 | third data leg `build_A_50ohm_twin_p51.json`, 72×212×22, n_line 64, β 231.0873600620821 | `evidence/termination/build_A_50ohm_twin_p51.json` is a **LOADED** record: `run/load_port = "p2"`, `line/beta = 286.35930483082825`, `line/eps_eff = 5.49663647596545`, `s11.magnitude` 0.0489985288420461, `s21.magnitude` 0.7675574763802439, `z0` 42.43786214405251 − 15.727993189312496j | **The script must use `evidence/termination/build_A_50ohm_twin_p51_twin.json`** — the load-free record with `geometry/grid` [72, 212, 22], `n_line` 64, `line/beta` 231.0873600620821, `line/eps_eff` 3.5795365321344415, `z0` 49.4259949734449 + 16.33275604971187j. The load-free siblings of that cross-section are `build_A_50ohm_twin_p51_twin.json`, `build_A_50ohm_twin_p51_s11fix_twin.json`, `build_A_50ohm_v3c_twin.json`, `build_A_50ohm_v3_twin_check_twin.json`. Quoting 231.087 under the *loaded* filename is the exact confusion §2.3 warns about. |
| 2 | `zc = station_fit.z0` at `emfit/studies.py:3601` | `zc = complex(station_fit.z0)` is at **`emfit/studies.py:3604`** (the `:3601` line is the comment "has -- and without one there is nothing to measure the amplitude against") | cite 3603–3604 |
| 3 | `deembed_reflection` assert at `studies.py:3571-3575` | the call is `emfit/studies.py:3565`; the comment is 3571–3574; the `assert abs(abs(gamma_port) - abs(gamma_measured)) < 1e-9` is at **3575** | cite 3565 (call) and 3575 (assert) |
| 4 | `ports.py` basis at 804 / 817 / 820 | `_fit_design` is at `emfit/ports.py:806`; the forward column `np.exp(-(alpha + 1j*beta)*z)` at **817**, the backward `column_stack` at **820** | consistent; cite 806–820 |
| 5 | S2 implies the lateral grid is 212 everywhere | 212 is the **twins** (`run/kwargs/n_clean = 96`). `board_poc/A_microstrip.json` is **44** lateral (`MS_N_CLEAN = 12`, `emfit/studies.py:1199`), `/metrics/mesh` "62 x 44 x 22" | both are correct for their own record; §2.2 and §3 say which is which |
| 6 | `A_microstrip.json` "β ~232.45–232.56" | confirmed: 232.447 (one-wave) / 232.558 (two-wave) / 232.493 (two stations) | no conflict |
| 7 | the `A` twin's S-params | not re-read this dispatch (the read aborted on the loaded file, item 1) | the script must read `s11.magnitude` / `s21.magnitude` from `build_A_50ohm_twin_p51_twin.json` and apply bracket D to them |
