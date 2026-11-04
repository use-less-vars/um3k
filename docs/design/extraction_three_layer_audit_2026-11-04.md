# Extraction three-layer audit — Layer 1: field measurement

*"The TE's three-layer audit (Q3 response). The anchor note's reasoning is refuted (DR-32) — six records carry the pre-2026-11-03 'shorted stub' framing, which the strip-into-PML reframe and the |Gamma| < 0.02 test refute. The 27pp/33pp swings must be located in the extraction code before any mechanism test. Plus DR-31 (asserts-and-retracts record pattern) and DR-32 (refuted note reasoning)."* [unwrapped: verbatim]

Wrap note: lines are wrapped at <= 126 characters except (a) the provenance line above, quoted
verbatim as issued, and (b) any source line quoted from the tree, reproduced exactly rather than
wrapped. Each exception carries the marker `[unwrapped: verbatim]` in place and is the only reason
that line exceeds 126 characters. Every other line is <= 126 characters.

## Scope

Layer 1 of the three-layer audit: field measurement, read only from the tree at the cited lines.
Nothing is run, no artefact is edited, nothing is re-graded and no number is recomputed. The
question is where V and I come from, at which Yee indices and at which effective planes, and
whether anything in that sampling could carry a 27 pp or 33 pp swing. Layers 2 (modal extraction)
and 3 (network normalization) are heading stubs only.

## Layer 1 — Field measurement

### 1.1 V: which E components, at which Yee indices

**Answer: `E_z` only, summed along a single node-layer column at the x,y of the extraction point.**

- `edge_path_voltage(e, edges, signs=None)` — `emfit/ports.py:79`, body 100-111, terminating in
  `return float(np.sum(s * e[idx]))` at `emfit/ports.py:111`. A pure sum of primal-edge unknowns,
  i.e. an approximation of int E.dl along the edge list; `signs` defaults to all +1.
- `Probe.voltage` at `emfit/ports.py:171`; `class LumpedPort` at `:180`; `LumpedPort.voltage` at
  `:209-211` -> `edge_path_voltage(e, self.edges)`.
- `column_path(cc, ix, iy, k0=0, k1=None)` — def at `emfit/ports.py:253`. It validates `ix` as a
  **point/node layer** against `cc.nxn` (`:308`) and `iy` against `cc.nyn` (`:309`), then returns
  `cc.idx_ez(ix, iy, np.arange(lo, hi))` at `:311` — a column of `E_z` edges that share one (x,y)
  node and step through z *cells* 0..nz.
- Study wiring (all `emfit/studies.py`): `js = np.floor(wanted/cell+0.5).astype(int)` (`:2986-2987`),
  then `station_x = js * cell` (`:2992`), then
  `columns = [column_path(cc, int(ix), j_centre, 0, k_strip) for ix in js]` (`:2993`),
  `port_column = column_path(cc, ix_port, j_centre, 0, k_strip)` (`:2994`),
  `port = LumpedPort("line", port_column, z0=MS_Z0_NOMINAL)` (`:2995`).
  Indices: `ix_port = n_pml + n_ref` (`:2830`), `k_strip = n_sub` (`:2831`),
  `j_centre = j0 + n_strip//2` (`:2834`).
- => **V = sum over k = 0..n_sub-1 of E_z(ix, j_centre, k)**. `E_z` only. One y node layer (the
  strip centre — no average across the strip width). x on a node layer, x = ix*cell. z over node
  layers 0..n_sub, i.e. from the ground plane to the top of the substrate.

### 1.2 I: which H components, at which Yee indices

**Answer: `H_y` only (as magnetic voltages `H_y*dy`), summed across y node layers at one x cell
and one z cell.**

- `plate_current(h, cc, ix, iz, y_extent=None)` — def `emfit/ports.py:395`. `h` must be flat,
  length `cc.n_faces`. `ix = _node_index("ix", ix, cc.nx)` at `:458`, so `ix` here is an **x CELL**
  index (note the opposite convention from `column_path`). `iz` is validated against `cc.nz`, also
  a cell. Then `j0, j1 = _y_columns(cc, y_extent)` (`:460`),
  `faces = cc.idx_fy(ix, np.arange(j0, j1), iz)` (`:461`), and
  `return float(h[faces].sum())` (`:462`).
- => **I = sum over j = j0..j1-1 of H_y(ix, j, iz)**. `H_y` only. One x cell, one z cell. No cell
  width is applied, because the stored face value is already `H_y*dy` (an ampere-turns sum).
- `FY` is a face of the x-cell `ix`, so this current lives at **x = (ix + 1/2)*cell**, i.e. half a
  cell downstream of an x node layer. With `iz = 0` (`studies.py:3190-3192`) it sits at the centre
  of z cell 0, i.e. `cell/2` above the ground plane, inside the substrate.
- `_y_columns(cc, y_extent)` — def `emfit/ports.py:363`. `None` -> `(0, cc.nyn)`, every y point
  layer. A scalar is a half-width in metres about the y-axis centre, converted to the contiguous
  run of y point layers (raises if the run is not contiguous). A pair is a half-open run.
- Docstrings: for periodic y the full sum is required because otherwise the loop is "one column
  short" (`emfit/ports.py:406-409`); `y_extent` exists because "Inside a PML the field is a
  numerical absorber ... summing H across it adds a current that no conductor carries"
  (`emfit/ports.py:411-418`).
- Signal layout in the tone run (`emfit/studies.py`): `n_currents = n_stations + 3` (`:3074`), then
  `signals = np.zeros(n_currents + n_stations)` (`:3075`). Channels: `[0..n_stations-1]` station V
  (`:3187-3188`); `[n_stations]` `v_port = port.voltage(stepper.e)` (`:3189`); `[n_stations+1]`
  `plate_current(stepper.h, cc, ix_port, 0)`, **untruncated** in y (`:3190`); `[n_stations+2]` the
  same with `y_extent=y_half`, **truncated** (`:3191-3192`); `[n_currents..]` station currents as
  `0.5*(plate_current(..., ix-1, 0, y_half) + plate_current(..., ix, 0, y_half))` (`:3201-3204`),
  with the comment at `:3193-3200` naming the reason ("without it the ratio would carry
  beta*cell/2 of spurious phase (about 2.7 deg at the default case)").

### 1.3 Other V/I consumers and their effective planes

**Answer: every V/I pair in this file is co-planar except `line.z0` and the port-level `a`/`b`, which
pair a node-plane V with a single-cell I half a cell downstream without compensation.**

- (a) **line / station impedance** — V from `columns` (`studies.py:2993`, node layers), I as the
  two-cell average (`:3201-3204`). **Same plane.** Residual is amplitude only, about
  `cos(beta*cell/2)`; zero phase error. Phasors: `i_stations = -spec[n_currents:n_currents+n_stations]`
  (`:3348`); fit calls at `:3471` (`fit_station_impedance(fit_x, fit_v, fit_i, beta, sigma_beta)`),
  and again at `:3509`, `:3516`, `:3519` (lossy, z_plus, z_minus). `fit_station_impedance` def
  `emfit/ports.py:1429`; `z0 = amp_v[0]/amp_i[0]` at `emfit/ports.py:1516`. **Note: the tone-path
  call is `studies.py:3471`, not the "near :3563" of the earlier reading.**
- (b) **`line.z0`** — `studies.py:3553-3554`, `-v_port/i_trunc`: V on the node layer at
  `ix_port*cell`, I at `(ix_port + 1/2)*cell` from a **single** cell, y-truncated. **Half-cell
  offset, uncompensated.** The comment at `:3544-3552` explains only the 180 deg negation; the
  docstring at `emfit/ports.py:1468-1476` records `arg(z0)` ~ +17 deg at the default case.
- (c) **`_load_z_eff`** — def `studies.py:2394-2421`, called at `:3250-3251`.
  `signals[0] = edge_path_voltage(stepper.e, column_path(cc, int(ix_load), int(j_centre), 0,
  int(k_strip)))` (`:2416-2417`); `signals[1] = 0.5*(plate_current(..., int(ix_load)-1, 0,
  y_extent=y_half) + plate_current(..., int(ix_load), 0, y_extent=y_half))` (`:2418-2420`);
  `z_acc.add(signals, n)` (`:2421`). **Same plane.** Docstring `:2405-2411` repeats the half-cell
  argument. Consumed at `v_load = z_spec[0]`, `i_load = -z_spec[1]`, `z_eff = v_load/i_load`
  (`:3364-3372`).
- (d) **cut plane** — `v_cut = cut_spec[0]`, `i_cut = -cut_spec[1]` (`studies.py:3354-3355`).
  **Same plane** (two-cell average). Voltage source at `:3212` (`edge_path_voltage(stepper.e,
  cut_column)`), current at `:3213-3217`. The `flux_projection` branch projects only the voltage
  (`:3239-3241`) and leaves the current as the two-cell average (`:3242-3246`).
- (e) **`a`/`b` split at the port** —
  `a_port = forward_wave_amplitude([v_port], [-i_trunc], [x_port], gamma_split, zc_split)`
  (`studies.py:3643-3644`), `b_port = backward_wave_amplitude([...])` (`:3649-3650`): this mixes a
  node-plane V with a half-cell-plane I while labelling both `x_port`. At the cut the same call is
  given `(v_cut, i_cut, x_cut)` (`:3645-3648`), which **is** co-planar. Defs:
  `forward_wave_amplitude` `studies.py:1297` (`A e^{-gamma x} = (v + zc i)/2` at `:1313`),
  `backward_wave_amplitude` `:1354`.
- (f) **power checks** — `power_current_check(v_stations, i_stations, zc)` (`studies.py:3696`);
  `power_current_check([v_port], [-i_trunc], z0)` (`:3697-3698`), the half-cell pair again.
  `power_current_check` def `emfit/ports.py:1737`.
- (g) **`station_poynting`** — `emfit/ports.py:470-` : E on the node layer `ix`, H averaged over the
  straddling cells (`cells = (ix-1, ix)`, or a single cell at the ends) via
  `hz = np.mean(fz[list(cells),:,:], axis=0)` / `hy = np.mean(fy[list(cells),:,:], axis=0)`.
  **Co-planar spatially**, but one raw time sample, so it carries the `t^n` / `t^{n-1/2}` offset of
  1.4; returns `px1 - px2`.
- (h) **S-parameters** — `s21` is a ratio of forward-wave amplitudes (`studies.py:3656-3659`) and
  `gamma_plane = b_cut/a_cut` (`:3653`), so neither is a V/I ratio.
- (i) **defaults** (`studies.py:1157-1234`): `MS_H=1.6e-3`, `MS_W=3.2e-3`, `MS_EPS_R=4.4`,
  `MS_F_TARGET=6.0e9`, `MS_NSTEPS=2400`, `MS_N_PML=6`, `MS_X_FIRST/LAST=10.4/20.0e-3`,
  `MS_N_STATIONS=9`, `MS_N_SUB=4`, `MS_N_AIR=12`, `MS_N_TOP=6`, `MS_N_STRIP=8`, `MS_N_CLEAN=12`,
  `MS_N_REF=2`, `MS_N_LINE=54`, `MS_Z0_NOMINAL=50`, `MS_EXCITE="cw"`, `MS_ANIMATE_PLANE="mid"`.
  With the assert at `:2810-2818` forcing `n_strip = round(w/cell)`, `cell = w/n_strip = 0.4 mm`,
  so **one half cell = 0.2 mm**.

### 1.4 Temporal phasor: same time index, or offset?

**Answer: same time index `n` for every channel, but the two half-steps of the leapfrog mean the
E-derived and H-derived phasors are `omega*dt/2` out of phase within that one index.**

- Loop: `for n in range(nsteps)` (`studies.py:3167`); ramp drive
  `current[port_edges] = drive*ramp*sin(2*np.pi*f0*n*dt)*launch_profile` (`:3183`);
  `stepper.step(current)` (`:3184`); signals read (`:3187-3204`); `acc.add(signals, n)` (`:3205`).
  `z_acc` / `_load_z_eff` (`:3248-3251`); `plane_ey` block (`:3252-3270`) with
  `phase = np.exp(-2.0j*np.pi*f0*n*dt)` at `:3257`.
- `class DftAccumulator` `emfit/ports.py:564`; `def add(self, values, n)` `:649`;
  `phase = np.exp(-2.0j*np.pi*self.freqs*n*self.dt)`,
  `self._acc += (self._weight(n)*phase)[:,None]*v[None,:]` (~`:660-662`). Docstring: the phase comes
  from the **time-step index n**, "not from an accumulated float clock".
- `FITStepper.step` `emfit/evolve.py:186-214`: `self.h -= self.dt*(self.inv_m_mu*(self.C @ self.e))`
  FIRST, then `ce = self.C_tilde @ self.h` (-j), then `self.e += dt*(inv_m_eps*ce)` (or the lossy
  form), then `self.n += 1`. => after a step, `(e, h) = (e^n, h^{n-1/2})`.
- Confirmed in-tree by the `station_poynting` docstring `emfit/ports.py:483-487`: "after
  :meth:`FITStepper.step` ``e`` is at ``t^n`` and ``h`` at ``t^{n-1/2}``, so the product carries a
  fixed ``exp(+j omega dt / 2)``".
- => **There is no half-step correction anywhere on the tone path.** One `exp(-j*omega*n*dt)`
  multiplies both the E-derived and the H-derived channels of the same `acc.add(signals, n)`. So
  every V/I ratio in this file carries **+omega*dt/2**: the I phasor is the true phasor times
  `exp(-j*omega*dt/2)`.
- **Measured magnitudes** (read-only evaluation of `Microstrip(...).beta(6e9)` and the stability
  step for the study's own grid, no solver run): `eps_eff = 3.34394`, `beta = 229.953 rad/m`,
  `beta*cell = 0.091981 rad = 5.2701 deg`, so `beta*cell/2 = 0.045991 rad = **2.6351 deg**` — which
  is the code's own "~2.7 deg" at `studies.py:3193-3200`. `cos(beta*cell/2) = 0.998943`, i.e.
  **+0.1059 %** amplitude. With the study's grid (nx=62, ny=44, nz=22, uniform 0.4 mm) the
  stability step is `dt = 7.6263e-13 s` and `omega*dt/2 = 0.014375 rad = **0.8236 deg**`.
- The `emfit/ports.py:483-487` figure of "about 3e-3 rad at the default step" does **not** belong to
  this study: 3e-3 rad needs `dt ~ 8e-14 s`, i.e. a ~0.04 mm cell. At the microstrip default
  (0.4 mm, 6 GHz) the correct figure is 0.0144 rad = 0.82 deg, and it is identical for every channel
  of a given step, so it rotates all V/I ratios alike rather than skewing one against another.

## Layer 2 — Modal extraction

### 2.1 `fit_beta` and the design matrix

**Answer: an exact two-column exponential design in `z`, linear in the amplitudes, searched over one
real parameter `beta`.**

- `_fit_design(z, beta, n_wave, alpha=0.0)` — `emfit/ports.py:804` — builds every column the fit uses:
  `forward = np.exp(-(alpha + 1j*beta)*z)` (`:817`). `n_wave == 1` returns `forward[:, None]`
  (`:818-819`); `n_wave == 2` returns `np.column_stack((forward, np.exp((alpha + 1j*beta)*z)))`
  (`:820`) — one `|beta|`, two signs.
- `fit_beta(z, v, n_wave=1)` — `ports.py:861` — states the model at `:870-871`:
  `n_wave=1: v(z) = A exp(-j beta z)`; `n_wave=2: v(z) = A exp(-j beta z) + B exp(+j beta z)`.
  Linear in the amplitudes once `beta` is fixed (`:873-875`), so the search is one-dimensional:
  a 2048-point scan over `(0, pi/dz]` (`:931-934`), a bounded `minimize_scalar` on that bracket
  (`:946-949`), and — for `n_wave == 1` only — a Newton polish `_polish_one_wave` (`:953-958`).
- Unknowns, counted in real numbers: `n_wave=1` -> **3** (real beta, complex A); `n_wave=2` -> **5**
  (one real beta shared by both columns, complex A, complex B). The guard `if z.size < n_wave + 2`
  raises (`:913-916`), i.e. >=3 and >=4 stations respectively.
- `beta` is real and positive by construction: only positive values are ever scanned (docstring
  `:879-881`), and the consumer re-checks it (`:1497`).

### 2.2 What `amp_v[1] / amp_v[0]` is

**Answer: `B/A`, the reflection coefficient of the two-wave model at the FIRST station, not at the
port; `beta` enters as a real positive number multiplying `1j`, in the `exp(-j beta z)` = forward
direction.**

- `fit_station_impedance(x, v, i, beta, sigma_beta=None, alpha=0.0)` — `emfit/ports.py:1429` —
  refers both series to the first station, not the port: `plane = float(x[0])`, `u = x - plane`
  (`:1507-1508`). Both then go through `_two_wave_fit(u, ..., beta, alpha)` (`:1511`, `:1512`),
  whose design is `_fit_design(u, beta, 2, alpha)` (`ports.py:1385-1393`) — the `2` is hard-coded,
  so a two-wave decomposition is done on V and I even when the caller's `beta` came from a one-wave
  fit.
- `gamma_v = complex(amp_v[1] / amp_v[0])` (`:1517`), `gamma_i` likewise (`:1518`), and
  `z0 = complex(amp_v[0] / amp_i[0])` (`:1516`). So `amp_v[1]/amp_v[0]` is the `B/A` of
  `v(z) = A exp(-(alpha + 1j beta) z) + B exp(+(alpha + 1j beta) z)` (docstring `:986-992`),
  referenced to `u = 0`, i.e. to the first station.
- Sign: the DFT accumulator stores `exp(-2j pi f n dt)` (`:660-662`), so a stored phasor
  `exp(-j beta z)` is the +x-travelling wave under an `exp(+j omega t)` convention. "Forward" = +x,
  `beta` real and >0 (`:1496-1498`). Changing `n_wave` does not change that convention — same
  forward column, same positive-only search — it changes whether a backward amplitude exists at
  all, the dof, and which `beta` the caller picks up.

### 2.3 Is the fit linear, and in what?

**Answer: linear in the amplitudes and nonlinear in `beta` only — one real scalar. It is not one
solve: each `fit_beta` call is 2048 least-squares solves plus a scalar minimisation.**

- The amplitude solve is exactly linear: `np.linalg.lstsq` at `ports.py:827` and `:1393`. The only
  nonlinear unknown is the single real `beta`, which is why the profile is scanned (`:931-934`),
  bracketed (`:946-949`) and, for `n_wave == 1`, Newton-polished (`:953-958`).
- `fit_line` (`ports.py:1058`) is the genuinely nonlinear one: it seeds `beta` from `fit_beta`
  (`:1132`) and then treats `[Re A, Im A, (Re B, Im B), alpha, beta]` as a joint vector
  (`:1134-1157`), with `alpha` seeded at 0.0.
- Assumptions actually made: `beta` REAL and >0 (enforced `:1497`, only positive values scanned
  `:931-933`); `alpha` real, default 0.0 (`:1430`, `:1510`); amplitudes COMPLEX. A real `Z0` is NOT
  assumed — `z0 = complex(amp_v[0] / amp_i[0])` (`:1516`).
- `beta` uncertainty is a profile curvature, not a covariance: `sigma_beta_from_curvature`
  (`ports.py:1578`), `dof = 2*z.size - 2*n_wave` (`:1634`), central second difference of the cost
  (`:1638-1644`). Its default `n_wave=1` gives the ONE-wave dof even when the `beta` being scored
  came from a two-wave fit.

### 2.4 One `beta` for both components, or one each?

**Answer: ONE, shared. `fit_station_impedance` takes a single scalar `beta`, fitted on the
voltages alone, and applies it unchanged to the current — V and I are never fitted independently
for `beta`, only for their complex amplitudes.**

- The signature is `fit_station_impedance(x, v, i, beta, ...)` (`ports.py:1429`) and the identical
  value goes to both `_two_wave_fit` calls (`:1511`, `:1512`). No per-component `beta` exists
  anywhere in the module, and the >0 check sits once, on the shared value (`:1496-1498`).
- The caller fits it on V: `fit_two = fit_beta(station_x, v_stations, n_wave=2)`
  (`emfit/studies.py:3386`), `beta = float(fit_two.beta)` (`:3387`), then
  `fit_station_impedance(fit_x, fit_v, fit_i, beta, sigma_beta)` (`:3471`).
- Consequence, stated as fact rather than a hedge: because both series are re-referenced at the
  same `beta`, a `beta` error rotates both forward amplitudes identically and so cannot create a
  first-order relative phase between V and I at a common plane. It acts instead through the
  two-wave decomposition of each series and, downstream, through
  `zc = complex(station_fit.z0)` (`emfit/studies.py:3603`) into the a/b split.

### 2.5 Where the `beta` in the s11 path comes from

**Answer: eight distinct sources. The a/b split itself uses none of them — `beta` reaches s11 only
through `z0`, and through the `line_s21` de-embedding of `s21` on the branches that take it.**

- The split is `a_port`/`b_port`/`a_cut`/`b_cut` from `forward_wave_amplitude` /
  `backward_wave_amplitude` (`emfit/studies.py:1297`, `:1354`), called at `:3643-3650` with
  `gamma_split` (`:3625-3626`) and `zc_split`; and `zc = complex(station_fit.z0)` (`:3603`), else
  `reference.zc` (`:3605`), else it raises (`:3607-3616`).
- 1. TWO-WAVE station fit on V, `fit_beta(..., n_wave=2)` (`:3386`), `beta = float(fit_two.beta)`
  (`:3387`). This is the tone path's beta: it feeds `sigma_beta_from_curvature` (`:3411`),
  `fit_station_impedance` (`:3471`), the split's `zc`, and the recorded `beta`/`beta_two_wave`
  (`:3944-3945`) and `beta_used` (`:3991`).
- 2. ONE-WAVE station fit, `fit_one = fit_beta(..., n_wave=1)` (`:3385`); only `.residual` is used
  (`:3949`).
- 3. LOSSY JOINT fit, `loss_fit.beta` / `loss_fit.beta_sigma` from `fit_line` (`ports.py:1058`),
  handed to `fit_station_impedance` at `:3509`, `:3516`, `:3519`.
- 4. CURVATURE sigma, `sigma_beta_from_curvature(...)` (`:3411`) — a one-wave dof formula
  (`ports.py:1578`) applied to the two-wave beta.
- 5. CLOSED FORM, `beta_model = float(line.beta(f0))` (`:3542`, `microstrip.py:372`,
  Hammerstad-Jensen): comparison row (`:4878-4879`) and phase de-trending (`:3849`), never a seed.
- 6. TWO-STATION diagnostic, `beta_two_station = -d_phase / d_probe` (`:3383-3384`), recorded at
  `:3943`.
- 7. BROADBAND bin metrics, one-wave (`:2005`, `:2195`); `eps_eff` from `(beta*C0/(2*pi*f))**2`
  (`:2074`).
- 8. DE-EMBEDDING, `line_s21(a1, x1, a2, x2, beta)` (`:1243`) -> `deembed_transmission`
  (`ports.py:1707`), which multiplies by `exp(+1j*beta*d)`. Called with the run's own beta at
  `:3659` (cut branch, no reference) and `:3686` (no-station-fit branch), and with the bin-metric
  beta at `:2055` — so on those branches the adjacent `s21` does consume beta.
- No call site in `emfit/` reads a `beta` back out of an artefact: every beta handed to
  `fit_station_impedance` is fitted in the same run (`:3387`, `:3509`); artefacts carry it as
  output (`beta_used`, `:3991`). The estimator does differ between paths — the tone path takes the
  two-wave value (`:3387`), the bin-metric path the one-wave value (`:2005`, `:2195`).
- The two values in circulation are therefore not a conflict: `231.5533 rad/m` is source 1, a
  measured two-wave fit at `f = 5.8278 GHz` (recorded as `beta`/`beta_two_wave`/`beta_used` in
  `evidence/termination/build_A_50ohm_*.json`); `229.953 rad/m` is source 5, the closed form at
  `f = 6.0000 GHz`. At the artefact's own frequency its `summary_line` carries
  `beta_model=223.3531`, so fit-vs-model there is `+3.67 %`, not `0.7 %` — the `0.7 %` compares
  across frequencies. Its grid is `cells=72x212x22` against the current tree's `62x44x22`
  defaults: a code/grid vintage, not a beta-source difference.

## Layer 3 — Network normalization

### 3.1 the split — pseudo-waves in volts, not power waves

**Answer: a ½-scaled, zc-divided pair of *pseudo*-waves in volts — `A = (v + zc i)/2 * exp(+gamma x)` — and s11 is
two of them on one plane, so both the ½ and the zc cancel and what is left is `(v - zc i)/(v + zc i)`. No sqrt is
anywhere in the path.**

- `_wave_amplitude(v, i, x, gamma, zc, sign, indices)` — `emfit/studies.py:1282`, with a single return at `:1294`:
  `return 0.5 * (v + complex(sign * zc) * i) * np.exp(complex(sign * gamma) * x)`. Its two public faces are
  `forward_wave_amplitude` (`:1297`, passing `sign = 1.0` at `:1351`) and `backward_wave_amplitude` (`:1354`,
  passing `-1.0` at `:1375`).
- The factor is 0.5 exactly: no `sqrt`, no `sqrt(2)` and no `1/sqrt(2)` occurs in the helper, and the return is
  documented as `A`, the forward wave referred to `x = 0` in volts (`:1345-1346`). A power wave would carry
  `1/(2 sqrt(zc))`; this carries `1/2`. So it is a pseudo-wave (V/I normalised), and `zc` — "Characteristic
  impedance [ohm], complex" (`:1339-1340`) — is a divisor, never a normalising impedance.
- The model it inverts is the package's own two-wave convention (`:1305-1306`): `v(x) = A exp(-gamma x) + B
  exp(+gamma x)` and `i(x) = (A exp(-gamma x) - B exp(+gamma x)) / zc`, with `A` towards `+x` and `B` towards `-x`,
  both referred to `x = 0`. Adding and subtracting give `A exp(-gamma x) = (v + zc i)/2` and
  `B exp(+gamma x) = (v - zc i)/2` (`:1313-1314`), and the `exp(+gamma x)` walks `A` back to the origin — "the
  amplitude A itself, not the local phasor" (`:1316-1317`).
- s11 is four of these on two planes (`:3643-3650`): `a_port` from `[v_port], [-i_trunc]` (`:3643-3644`, the port
  current negated onto the forward sense), `a_cut` from `[v_cut], [i_cut]` unnegated (`:3645-3646`), then `b_cut`
  and `b_port` as the backward pair (`:3647-3650`), with `gamma_plane = complex(b_cut)/complex(a_cut)` (`:3653`).
- Both cut-plane waves take the same `(gamma_split, zc_split)` at the same `x_cut`, so the ½ and the
  `exp(+gamma x)` cancel exactly and the ratio collapses to `(v_cut - zc_split i_cut)/(v_cut + zc_split i_cut)` —
  the classical reflection formula with no sqrt in it. Calling the pair pseudo- or power-waves does not change
  this ratio, because the normalisation is common to numerator and denominator; it changes only what the stored
  `a` and `b` *are*, and those are volts (`:1345-1346`).

### 3.2 `zc` vs `zc_split`

**Answer: the same quantity class — a fitted *complex* characteristic impedance in ohms — differing only in
provenance, under a documented precedence; the artefact's 0.34465 is not a zc at all.**

- `zc` is chosen once, `emfit/studies.py:3603-3616`: `if station_fit is not None: zc = complex(station_fit.z0)`
  (`:3603-3604`); `elif reference is not None: zc = complex(reference.zc)` (`:3605-3606`); otherwise a ValueError
  (`:3607-3616`) that says "so neither the split nor the power-current check has a zc to measure against. Run it
  with reference=...".
- `zc_split` is that same number, re-selected per branch: the `s11_settling` initialisation at `:3625-3626` takes
  `complex(reference.zc)` when a reference exists and `complex(zc)` otherwise, and the `ix_extract` branch says
  the same in if/else form — `zc_split = complex(reference.zc)` (`:3639`) or `zc_split = zc` (`:3642`), with
  `gamma_split` moving with it (`:3638`, `:3641`).
- The precedence is single-sourced and stated (`:3597-3602`): "the fit's own z0 when there is one, the
  reference's when the fit was refused, and a refusal of our own when neither exists", the reference being
  "exactly the right substitute -- it is the same line, load-free, so its zc is the impedance this record's mode
  has". Both sides are the same recipe on different runs: `station_fit.z0` is `complex(amp_v[0] / amp_i[0])`
  (`emfit/ports.py:1516`) and `reference.zc` is `complex(wave.station_fit.z0)` (`emfit/studies.py:1760`).
- The two provenances are alternates, not rival estimates of different things:
  `loaded_without_reference = bool(loads_used) and reference is None` (`:3621`), with the branch comment "a loaded
  record's station fit is distrusted across the cut, so in practice zc comes from reference" (`:3632-3633`).
- **The 0.34465 anchor is a different animal.** It is not in code; it is prose in artefacts, e.g.
  `evidence/termination/build_A_50ohm_v3_lumped_check.json:288`: "the magnitude above is the modulus of the
  two-wave B/A ... it reads 0.3256 against the series-R anchor 0.34465, i.e. 5.54 percent low", and
  `build_A_50ohm_twin_p51_s11fix.json:329` adds "clean synthetic alpha=0 data with a genuine B/A=0.3447 standing
  wave ... the two-wave fit returns |Gamma|=0.34465 exactly", calling it "the series-R anchor 0.345".
- It is the |Gamma| of a 50 ohm series load on the 50 ohm nominal line (`MS_Z0_NOMINAL = 50.0`, `:1205`),
  computed outside `emfit` and compared against `|amp_v[1]/amp_v[0]|` (`emfit/ports.py:1517`): real,
  dimensionless, a yardstick. `zc_split` is complex, in ohms, and is the divisor that splits `(v, i)` into
  travelling waves. The anchor is not built from `zc_split` and is not a check on it.

### 3.3 is there a Zref in s21

**Answer: no. No reference impedance enters s21 at any point: `line_s21` is a raw volts/volts amplitude ratio,
de-embedded by a unit-modulus phase factor.**

- `line_s21(a1, x1, a2, x2, beta)` — `emfit/studies.py:1243`; body `:1272-1279`: `d = float(x2) - float(x1)`, the
  guards for `d <= 0.0` (`:1273-1275`) and `a1 == 0.0` (`:1276-1277`), then `raw = complex(a2) / complex(a1)`
  (`:1278`) and `return deembed_transmission(raw, beta, d), raw` (`:1279`). No impedance is passed in or read.
- `deembed_transmission(s21, beta, distance)` — `emfit/ports.py:1707`; body `:1729-1731`:
  `out = np.asarray(s21, dtype=complex) * np.exp(1j * complex(beta) * float(distance))`. Two numbers and a
  distance; no `Zref`, no `sqrt`, no `/sqrt(2)` and no renormalisation anywhere on the path.
- The same `(gamma_split, zc_split)` pair serves s11 and the s21 amplitudes (`:3643-3650`), and the reference
  branch feeds `reference.gamma` and `reference.zc` to both (`:3670-3672`). `zc_split` shapes the split; it never
  divides the ratio.
- Because numerator and denominator carry the same ½ and the same zc, both cancel: s21 is a pseudo-wave ratio,
  where a power-wave s21 would carry the square root of the reference-impedance ratio. That factor is absent.

### 3.4 the de-embed — `exp(j beta d)`, not `exp(j (beta - j alpha) d)`

**Answer: the code multiplies by `exp(+1j * beta * distance)` with one `beta` symbol and no separate alpha
argument, and every caller in the tree hands it a real fitted beta — so the factor has unit modulus and attenuation
is not removed.**

- Exact expression, `emfit/ports.py:1729-1730`: `s21 * np.exp(1j * complex(beta) * float(distance))`. One symbol,
  `beta`; the signature `deembed_transmission(s21, beta, distance)` (`:1707`) has no `alpha` parameter at all.
- The complex-beta capability is documented but unexercised: `beta` "may be complex: with `beta = beta' - 1j *
  alpha` and `alpha > 0` [1/m] the factor's magnitude is `exp(+alpha distance)`, which is precisely the
  attenuation that is being undone" (`:1721-1723`); `line_s21`'s docstring says the same
  (`emfit/studies.py:1252-1257`) and its argument is "real or complex" (`:1262`).
- Every call passes a real beta. `beta = float(fit_two.beta)` (`:3387`) reaches
  `line_s21(a_port, x_port, a_cut, x_cut, beta)` (`:3659`) and
  `line_s21(a1, s21_planes[0], a2, s21_planes[1], beta)` (`:3686-3687`); in `_bin_metrics` the same
  `beta = float(fit_one.beta)` reaches the third site (`:2055`). Magnitude is untouched on all three.
- The fitters cannot hand over a complex propagation constant either: `fit_beta` scans positive reals only,
  `grid = np.linspace(beta_max / n_scan, beta_max, n_scan)` (`emfit/ports.py:931-933`), and returns a real beta
  plus a residual, no alpha; `fit_line` returns real alpha and real beta as separate scalars in
  `p = [Re A, Im A, (Re B, Im B), alpha(0.0), beta]` (`:1134-1136`). `fit_line`'s alpha never reaches this
  de-embed.
- Sign is consistent: the forward convention is `exp(-gamma x) = exp(-alpha x) exp(-j beta x)` (`:1338`), so a
  ratio across `d > 0` carries `exp(-j beta d)` and `exp(+j beta d)` removes it — and it is the opposite sign to
  the `exp(-2j beta distance)` of the reflection counterpart (`emfit/ports.py:1716-1717`), as documented.
- No double count. At `:3659` the split was set to `gamma_split = 0j` (`:3641`), so `a_port`/`a_cut` are local
  phasors and the phase factor is exactly the delay being removed; the second site passes `0j` explicitly
  (`:3684-3685`). Where `gamma_split` is non-zero (`:3638-3639`, reference present) the amplitudes are already
  referred to `x = 0` and the code takes the ratio-of-ratios branch instead (`:3656-3657`, `:3673-3676`), so
  `line_s21` is never called on them.

### 3.5 verdicts

**Answer: all four are CONSISTENT and nothing in this layer is `not determined`; the one seam found is an
unenforced relation, not a contradiction.**

- 3.1 CONSISTENT: `_wave_amplitude` (`emfit/studies.py:1294`) inverts the same two-wave model that `_fit_design`
  builds, `exp(-(alpha + 1j * beta) * z)` and its mirror (`emfit/ports.py:817-820`), and the docstring model
  (`emfit/studies.py:1305-1306`) is that same cancellation.
- 3.2 CONSISTENT: one quantity class under a documented precedence (`emfit/studies.py:3604`, `:3606`, `:3626`,
  `:3639`, `:3642`); the difference is provenance only, and 0.34465 is an external |Gamma|, not a zc.
- 3.3 CONSISTENT: no reference impedance reaches s21 (`emfit/studies.py:1278`, `emfit/ports.py:1729-1731`); the
  coefficient is a volts/volts ratio.
- 3.4 CONSISTENT on sign (`emfit/studies.py:1338` against `emfit/ports.py:1729`), with the limitation stated
  there: alpha is not removed, because every caller hands a real beta (`emfit/studies.py:3387` reaching `:3659`
  and `:3686-3687`).
- The seam: the split assumes a single mode, `i = (A exp(-gamma x) - B exp(+gamma x)) / zc`, while
  `fit_station_impedance` fits `gamma_i` freely (`emfit/ports.py:1518`) and nothing enforces
  `gamma_i = -gamma_v`. `gamma_i` is computed and never fed to the split — an output with no consumer, and a
  relation the split asserts without checking. That is not yet an inconsistency, so no verdict drops off
  CONSISTENT.

## Brackets

**Answer: L1 fires. L2, L3 and L4 do not. No qualifier recorded in the next section re-grades any of them, and
none of the four is a nearer-miss than that.**

- **L1 FIRES** — all three layers consistently documented and internally coherent, so the swings come from
  configuration, estimator or vintage choice rather than from a broken method. Every layer returned consistency:
  Layer 3 graded 3.1, 3.2 and 3.3 CONSISTENT and 3.4 CONSISTENT-on-sign with a stated limitation (`### 3.5`);
  Layer 1's V/I mismatch is a systematic half-step offset with a known closed-form value (~0.82°), not a scatter;
  Layer 2's single shared beta cannot produce a first-order V/I relative phase error at all. A coherent method
  meeting differing choices is exactly what the bracket describes, so L1 fires on its own terms.
- **L2 DOES NOT FIRE** — no layer contradicts itself. What the audit found is systematic offsets, each with a
  quantified magnitude (the ~0.82° temporal offset; the tone-versus-bin estimator difference), and one unenforced
  relation (`gamma_i = -gamma_v`, recorded below). A contradiction needs two statements in the tree that cannot
  both hold; none was found at any of the three layers.
- **L3 DOES NOT FIRE** — the conventions are documented, not missing. `zc` carries a written provenance and
  precedence comment at `emfit/studies.py:3597-3602`, and the complex-beta capability is documented if
  unexercised, at `emfit/ports.py:1721-1723` and `emfit/studies.py:1252-1257`. Documented-but-unused is not
  missing, and an unused capability is not an undocumented convention.
- **L4 DOES NOT FIRE — but only for the mechanism question.** The falsifier was "the code is consistent and the
  answer still swings"; the code is consistent, so the falsifier is not met. Scope, exactly: the swing itself was
  not re-measured anywhere in this dispatch — every number here is read out of the tree or out of stored
  artefacts. L4 is therefore falsified for the mechanism question only, and it says nothing about whether the
  27 pp and 33 pp swings are real, reproducible, or correctly attributed.

## What this does not settle

**Answer: seven qualifiers. Every one of them limits how far L1 may be pushed; none of them is a ground to re-grade
a bracket and none of them is a new bracket.**

1. **The estimator is not the same on both paths.** The tone path fits two waves (`emfit/studies.py:3386`); the
   bin-metric path fits one (`emfit/studies.py:2005`). That is directly relevant to the 27 pp estimator swing. It
   is not a consistency defect — but two "extractions" of the same observable are not the same estimator, and any
   comparison across them inherits the difference.
2. **A degree-of-freedom mismatch in the beta-error budget.** `sigma_beta_from_curvature` (`emfit/ports.py:1578`)
   defaults to `n_wave = 1` but is called with a two-wave `beta` (`emfit/studies.py:3411`). The curvature is then
   taken on the wrong model, so any beta uncertainty quoted from it is not the uncertainty of the beta used.
3. **No temporal half-step correction exists anywhere.** A single `exp(-j omega n dt)` is applied to both channels
   (`emfit/ports.py:661`, one accumulator call at `emfit/studies.py:3205`), although the stepper leaves `e^n`
   against `h^(n-1/2)` (`emfit/evolve.py:186-214`). That is a ~0.82° systematic — an offset, not a swing, and it
   cannot explain a 27 pp change.
4. **Two V/I consumers mix the planes.** `line.z0` (`emfit/studies.py:3553`) is the only V/I consumer that pairs a
   node-plane V with a half-cell I uncompensated, and the port `a`/`b` split (`emfit/studies.py:3643-3650`) also
   mixes the two planes under one `x_port` label. Neither is wrong as documented; both leave the effective plane
   of the reported impedance an approximation.
5. **Nothing enforces `gamma_i = -gamma_v`.** `fit_station_impedance` fits `gamma_i` freely
   (`emfit/ports.py:1518`) and `gamma_i` is never fed to the `a`/`b` split. The split assumes a single mode; the
   fit does not check that assumption.
6. **De-embedding removes phase but not attenuation.** `exp(+1j beta d)` with one real `beta` and no `alpha`
   argument (`emfit/ports.py:1729-1730`); the complex-beta branch is unexercised because `beta = float(...)`
   (`emfit/studies.py:3387`). On a lossy length the reported `s21` therefore still carries the line's attenuation.
7. **Whether `0.34465` applies to the current structure is not settled here.** That question is re-opened from
   scratch by DR-32 and belongs to Dispatch 8. This audit reads the anchor as an external yardstick and neither
   validates nor invalidates its applicability.

The layering, in one sentence each: **the solver is not broken** — nothing in the field, modal or network layer
contradicts another; **the extraction chain is under-characterised rather than contradictory** — it is documented,
and what is missing is measurement of the things the documentation leaves free (estimator choice, plane choice,
beta-error budget); **the anchor question is re-opened by DR-32, not answered by this audit** — the note's reason
for withholding the anchor is dead, while its conclusion may survive for a reason the note does not give.
