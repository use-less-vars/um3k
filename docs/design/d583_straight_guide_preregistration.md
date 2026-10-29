# Phase 58.3 — Straight-guide (uniform through-line) pre-registration

**Status: NOT YET RUN.**

Nothing in this document is a measurement. It is written **before** the run so that the
band cannot be moved afterwards. §6 is empty and must stay empty until the band in §3 is
frozen and signed off.

---

## 1. Test definition

### 1.1 Stated decision (adopted, not open)

**"Straight guide" in phase 1 means a strip whose cross-section is constant along the
propagation direction — a continuous uniform microstrip through-line.** No gap, no step,
no width change, no stub, no port taper. This decision is taken by the engineer and is
not revisited here.

### 1.2 A3 — can `plane_mode` express a uniform cross-section? (decisive)

**Yes — uniformity along propagation is structural, not a parameter, and no
discontinuity is expressible at all.**

* `plane_mode(mode, *, nyn, nzn, k_strip, iy_strip_centre=None, cell=None)` is defined at
  `emfit/modal.py:267-269`. It does exactly one thing: it asks the profile for slices and
  copies four field arrays through them —
  `window = mode.plane_window(nyn, nzn, k_strip, iy_strip_centre=…, cell=…)`
  (`emfit/modal.py:288-289`), then `e_y[dst]=mode.e_y[src]` etc.
  (`emfit/modal.py:290-300`).
* `ModeProfile.plane_window` (`emfit/mode_profile.py:316-323`) is an **integer index
  placement into a two-dimensional transverse plane**. It computes two shifts and nothing
  else: `iy_shift = centre - self.iy_strip_centre` (`mode_profile.py:384`) and
  `k_shift = k_strip - self.n_sub` (`mode_profile.py:385`), and clips through `_fit`
  (`mode_profile.py:420-441`). It returns a `PlaneWindow` (`mode_profile.py:178`).
* **There is no propagation axis anywhere in this code path.** The objects it produces are
  `(nyn, nzn)` transverse planes (`modal.py:290-293`), and a plane cannot carry an
  `x`-dependence. Uniformity along the line is therefore automatic; it is impossible to
  express a gap, a step or a width change, because a width change would require the strip
  slice itself to move — and the strip slice is fixed by the profile
  (`ModeProfile.strip_nodes`, `mode_profile.py:306-309`; `_conductors` holds the strip row
  at 1 V, `mode_profile.py:473-474`). A longitudinal discontinuity would require a
  *sequence of different* `ModeProfile` objects along `x`; nothing in the repo does that,
  and the only adapter that could carry a mode into the solver,
  `ModalPort.from_mode2d` (`emfit/modalport.py:194`), is called **nowhere** in `emfit/`,
  `tests/`, `tools/` or `examples/` (every existing port uses `from_profile`).

**What the two parameters mean** (`emfit/mode_profile.py`):

| Parameter | Meaning | Default / constraint | Cite |
|---|---|---|---|
| `k_strip` | **Node row of the target plane that carries the strip.** The profile's ground plane lands on `k_strip - n_sub`, which must be the plane's own `k = 0`; the interface and the conductors must sit on the same nodes | `_FDTD_K_STRIP = 16` (`mode_profile.py:151`) = 1.6 mm at 0.1 mm cells; `k_strip < n_sub` raises (`:386-391`) | `mode_profile.py:320`, `:332-337`, `:385-391` |
| `iy_strip_centre` | **Node index of the strip centre in the target plane** (the first transverse axis) | default `nyn // 2` = 100 on the production plane (`:338-340`, `:383`) | `mode_profile.py:321`, `:338-340`, `:384` |
| `cell` | Plane cell size; must equal the profile's | default = profile's | `mode_profile.py:322`, `:341`, `:373` |

The profile's **own** strip centre is a separate, read-only quantity:
`ModeProfile.iy_strip_centre = n_clean + n_strip // 2` (`mode_profile.py:301-304`,
"First transverse node index at the centre of the strip"). The shift is the difference
between the two (`:384`).

**A strip-free rectangular guide is NOT expressible.** The mode basis is constructed only
by `microstrip_mode_profile` (`emfit/mode_profile.py:535`), whose `__all__` (`:124`) offers
no other constructor; the strip is mandatory (`_conductors`, `:473-474`; `strip_nodes`
holds `n_strip + 1` nodes at 1 V, `:306-309`), and `plane_window` *requires* a strip row
(`k_strip`, with the `k_strip < n_sub` refusal at `:386-391`). A hollow-waveguide mode
would need a different basis and a different port construction; neither exists. Phase 1
therefore tests the microstrip through-line only.

### 1.3 A4 — where the reference beta comes from (decisive)

**`ModeProfile` carries no `beta`. The string `beta` does not occur even once in
`emfit/mode_profile.py`** (grep over all 742 lines: zero hits). The class fields are
`phi, e_y, e_z, h_y, h_z, eta_eff, c_prime, c_prime_air, eps_eff, z0, power, v_mode,
i_mode, power_full_box, cell, h, w, eps_r, n_sub, n_strip, n_clean, n_air`
(`emfit/mode_profile.py:272-293`).

The reference propagation constant is built from the **line parameters**:

```
k0        = 2*pi*f0 / C0                                  # C0 = speed of light
eps_eff   = ModeProfile.eps_eff  = c_prime / c_prime_air   # mode_profile.py:244, :280
beta_ref  = k0 * sqrt(eps_eff)                             # what this document calls beta
```

* **Provenance: a quasi-static 2-D electrostatic (Laplace) capacitance solve**, not an
  eigensolve of the time-domain mesh and not the extraction. `c_prime` is C' of the filled
  section and `c_prime_air` the same with `eps_r = 1` everywhere (`mode_profile.py:242-244`),
  produced by `microstrip_mode_profile` (`:535`) at a strip held at exactly 1 V and ground
  at 0 V (`v_scale = 1.0`, `:647`; `:699-702`), with an internal unit-power consistency
  assertion (`_require_close`, `:709-713`).
* **Is it independent enough? Yes.** The extraction consumes *time-domain phasors* recorded
  on the FDTD plane (`emfit/modal.py:372`); `beta_ref` comes from a capacitance ratio of a
  separate 2-D solve. The two share only the `emfit` package and the declared cross-section
  geometry, so `S11 = 0` / `S21 = exp(-j*beta_ref*L)` are **not** identities by
  construction. This is the property §5 makes mandatory.
* **Residual coupling to disclose:** `eps_eff` is the *quasi-static* (TEM) value, so it
  omits the physical dispersion of the microstrip. At f0 = 10 GHz on a 1.6 mm substrate that
  omission is small but it is a *systematic of the reference*, not of the code under test;
  it enters the phase residual as a bias and cannot be removed by refinement in `h`
  (see §4, "order is what is judged").
* **Second, mesh-consistent reference (recommended cross-check):** the 2-D cross-section
  eigensolve `emfit.mode2d.solve_modes_mixed` (mixed `e_t`/`e_z`, dense QZ — see
  `.scratch/mode2d/c2_slab.json:entry_point`). It is equally outside the extraction and, being
  a discretisation of the same operator family as the FDTD volume solve, it is the better
  reference for judging the *order* of the error. `.scratch/mode2d/c2_slab.json` is the
  evidence that it works and what its own error looks like (§3).

### 1.4 Geometry, stations, frequency (design parameters — chosen, not derived)

Fixed across all three rungs (this is what makes the run reproducible):

| Item | Value | Why |
|---|---|---|
| substrate thickness | 1.6 mm | integer cells at every rung: 8 / 16 / 32 |
| strip width w | 3.2 mm | integer cells at every rung: 16 / 32 / 64 |
| line length (physical) | 20.0 mm | ≥ 3 guide wavelengths at f0 |
| transverse box | 20.0 mm × 7.6 mm, **bare-substrate only** (no air above the strip is not implied; the box is the production plane 20.0 × 7.6 mm) | matches the production plane `201 × 77` nodes at 0.1 mm (`_FDTD_NYN`, `_FDTD_NZN`, `mode_profile.py:149-150`) |
| f0 | 10 GHz | sets `k0`, and makes `k0*h` at rung 2 comparable to the c2_slab design point (§3) |
| launch | soft source, `ModalPort.inject` (`emfit/modalport.py:316`), the `plane_mode` profile placed at the launch index | see §5 clause on soft sources |
| station 1 | `x1 = 6.0 mm` | ≥ 30 cells from the launch: evanescent contamination < 1e-6 by then |
| station 2 | `x2 = 18.0 mm` | `L = x2 - x1 = 12.0 mm` |
| run length | `T < 2*(20.0 - 6.0) mm / v_g` | **stops before the far-end echo reaches station 1** — there is no absorber in this codebase (`emfit/modalport.py:15-25`: "There is no absorbing port in this codebase"), so a hard-truncated line *does* reflect, and the phasor accumulator has no time gate (`emfit/studies.py:2783-2817`). Truncation of the *run*, not a window on the accumulator, is the only available protection. This is a real limitation of the measurement, recorded here deliberately. |

`k0 = 2*pi*1e10 / 2.99792458e8 = 209.5853 rad/m`; hence `k0*h` = **0.041917** (rung 1),
**0.020959** (rung 2), **0.010479** (rung 3).

### 1.5 The five stages, each with its function and file:line

**Stage 1 — mesh.** `emfit.evolve.FITStepper` is constructed on a conformal grid
`cc` with material vectors `m_eps` (shape `(n_edges,)`) and `m_mu` (shape `(n_faces,)`)
produced by `emfit.materials.material_matrices` (`emfit/evolve.py:88-89`; size checks
`evolve.py:181-190`). Arbitrary `eps`/`mu` volumes are accepted as those vectors; `dt`
defaults to `cfl_dt(cc.grid)`.

**Stage 2 — mode basis.** `emfit.mode_profile.microstrip_mode_profile`
(`emfit/mode_profile.py:535`) → `ModeProfile` (`:229`) → `emfit.modal.plane_mode`
(`emfit/modal.py:267`) → `PlaneMode` with `e_y` `(nyn-1, nzn)`, `e_z` `(nyn, nzn-1)`
(`modal.py:290-293`) → `ModalPort.from_mode2d(cls, mode, cc, axis, index)`
(`emfit/modalport.py:194`). **Note:** `from_mode2d` is exercised nowhere in the repo; phase
1 is its first real use. That is a finding, not a blocker.

**Stage 3 — volume solve.** `emfit.evolve.FITStepper(cc, m_eps, m_mu, dt=…, pec=…)`
(`emfit/evolve.py:122`), stepped with the port's soft source
`ModalPort.inject` (`emfit/modalport.py:316`). Soft source ⇒ the launched amplitude is not
unity and must be measured, not assumed; it is also why the run is truncated in time
(§1.4) rather than absorbed.

**Stage 4 — capture / projection.** There is **no standalone capture API**. Capture is
inline in `emfit.studies.microstrip_wave(...)` (`emfit/studies.py:2267`), enabled by
`plane_capture: bool | None = None` (`:2309`; board wrapper `microstrip_wave_board` at
`:3490`): allocation `:2718-2722`, accumulation `:2783-2817` (single-frequency phasor
`exp(-2*pi*j*f0*n*dt)` at `:2788`; `E` on the node layer `ix`; `H` = mean over the two
straddling `x` cells, `:2812-2817`), written by `_dump_bins` (`:2089`) under the `plane_*`
keys (`:2168-2179`).

**Stage 5 — extraction.** `emfit.modal.modal_station_phasors(planes, mode, stations, *,
f0, dt, convention=PLANE_CONVENTION, destagger_h=True)` (`emfit/modal.py:372`), with
`PLANE_COMPONENTS` (`modal.py:120`), the shape contract `e_y/h_z` `(nyn-1, nzn)` and
`e_z/h_y` `(nyn, nzn-1)` (`modal.py:262-266`, enforced `:436-439`), mesh line-integral units
(`emfit/plane_phasor.py:27-35`, `:79-95`), rectangular window, `E` at `t^n` / `H` at
`t^(n-1/2)` de-staggered (`modal.py:390-400`), and `f0`/`dt` required to match the recorded
`plane_f`/`plane_dt` to `_BIN_RTOL = 1e-9` (`modal.py:137`, `:411-424`).

With `A1 = phasor at x1`, `A2 = phasor at x2`, the S-parameters of this test are defined as

```
L        = x2 - x1
S21      := A2 / A1                          closed form  exp(-j*beta_ref*L)
S11      := b / a  from the two-station decomposition
            a = ( A1*exp(+j*beta_ref*x2) - A2*exp(+j*beta_ref*x1) ) / (2j*sin(beta_ref*L))
            b = ( A2*exp(-j*beta_ref*x1) - A1*exp(-j*beta_ref*x2) ) / (2j*sin(beta_ref*L))
                                             closed form  0
dphi     := arg(A2/A1) + beta_ref*L   [rad]  closed form  0
```

`S11` as defined is exactly the *non-forward residual*: `S11 == 0` iff
`A2 == A1*exp(-j*beta_ref*L)`. That identity is why §5 makes `beta_ref` external
mandatory — with `beta` fitted from `A1, A2` themselves the residual is zero by
construction and both closed forms become vacuous.

---

## 2. Acceptance band — DERIVED, not chosen

### 2.1 What the evidence file actually contains

Source: `.scratch/mode2d/c2_slab.json` (705,840 bytes; 7 cases; criterion
`"2B two-layer slab"`; entry point `emfit.mode2d.solve_modes_mixed (mixed e_t/e_z, dense
QZ)`; `"failures": []`; `"n_ok": 7`). Per-case scalars used below, verbatim:
`k0`, `k0_h`, `analytic_beta_sq`, `beta_sq_mesh`, `rel_dev` (= `(beta_sq_mesh -
analytic_beta_sq) / analytic_beta_sq`), plus the file-level `mesh.h = 0.05`,
`summary.all_rel_negative = true`, `summary.max_abs_rel_dev = 3.141044838746482e-05` at
`summary.at_k0 = 0.5`, `summary.k0_h_there = 0.025`.

### 2.2 The arithmetic — and what it does NOT support

The file has **one single mesh (`mesh = '8x64'`, `h = 0.05`) for all seven cases**; the
seven cases are a **k0 sweep at fixed h**, not an h-refinement. There is **no
`abs_rel_over_k0h2` key in the file**. Computed from the raw per-case numbers:

| case | k0 | k0·h (h=0.05) | rel_dev(beta²) | \|rel_dev\| / (k0·h)² |
|---|---|---|---|---|
| 0 | 0.05 | 0.0025 | −2.482616e−09 | 3.97e−04 |
| 1 | 0.10 | 0.0050 | −4.182636e−08 | 1.67e−03 |
| 2 | 0.20 | 0.0100 | −7.316789e−07 | 7.32e−03 |
| 3 | **0.50** | **0.0250** | **−3.141045e−05** | **5.03e−02** |
| 4 | 1.00 | 0.0500 | −2.234808e−05 | 8.94e−03 |
| 5 | 2.095845 | 0.1047922 | −3.304861e−06 | 3.01e−04 |
| 6 | 3.00 | 0.1500 | −6.696840e−07 | 2.98e−05 |

Worked example, case 3: `(0.5615913431957571 − 0.56160898358575) / 0.56160898358575 =
−3.141045e−05`; `|rel_dev| / (0.025)² = 3.141045e−05 / 6.25e−04 = 5.026e−02`.

**The ratio is not constant.** It spans 3.97e−04 … 5.03e−02, a factor of **1688**, and it
is *non-monotonic* in `k0` (peaks at the design point `k0 = 0.5`, collapses at
`k0 = 3.0`). So the premise "`abs_rel_over_k0h2` is constant ⇒ `beta²/k0²` error ∝ `(k0h)²`"
is **not supported by this file**: the file cannot fix the proportionality constant, and it
does not even exhibit the quadratic law. Two things are missing and are named here rather
than invented:

1. **An h-refinement at fixed frequency.** Every case shares `h = 0.05`; `refinement` is
   `[]` and `geometry`/`mesh` are single-valued. A coefficient of `(k0h)²` cannot be
   inferred from one `h` except through the `k0` dependence, which the table above refutes.
2. **A per-case `h` (or `k0h`) field with its own error at several `h`.** Not present.

What the file *does* fix is the **magnitude of a 2-D cross-section eigensolve's own
`beta²` error at `k0h = 0.025`: 3.141044838746482e−05, negative** (the discrete line is
slow: `beta_num < beta_analytic`). It is the single quantity this pre-registration is
willing to carry forward, and it is carried as an **order-of-magnitude prior only** — the
geometry is a two-layer slab (plates `y = 0, 3.2`, `sub_y = 1.6`, `eps = 4.4/1.0`,
**triangular** mesh `8×64`, `n_tris = 1024`), **not** the microstrip (`quad`-ish cell grid,
strip on node row `k_strip`). It cannot be a band for a different geometry.

### 2.3 The band, with the constant symbolic (binding)

Pre-registered ansatz, with `C_2` a **symbolic** constant:

```
(B1)  eps2(h) := |beta_num^2 - beta_ref^2| / beta_ref^2  =  C_2 * (k0*h)^2
(B2)  |dbeta/beta| = eps2/2 = (C_2/2) * (k0*h)^2
```

Propagate with `beta = beta_ref`, `L = x2 - x1`, `N = L/h`:

```
(i)   phase          |dphi|      <=  beta * L * |dbeta/beta|  =  (C_2/2) * (k0*h)^2 * beta*L     [rad]
(ii)  |S21|          | 1 - |S21|^2 |  <=  |S11|^2 + delta_E
(iii) |S11|          |S11|       <=  N * (C_2/2) * (k0*h)^2  =  (L/h) * (C_2/2) * (k0*h)^2
      passivity      0 <= 1 - ( |S11|^2 + |S21|^2 ) + delta_E
```

Chain of reasoning, every step named:

* (i) is the spec's `|dphi| <= beta*L*(dbeta/beta)` with (B2) substituted. A pure
  `beta` error is **phase-only**: it cannot change `|S21|`, so nothing in (ii) may be
  charged to (B1).
* (iii) assumes **A-refl**: the *per-cell* spurious reflection coefficient equals the
  per-cell relative dispersion error, `|r_cell| = (C_2/2)(k0*h)^2` — the same constant `C_2`,
  same order, same sign along the line (a uniform line has no cancellation), so the
  amplitudes add coherently over `N = L/h` cells. **A-refl is an assumption, stated as an
  assumption.** It is the only step in (iii) that is not algebra.
* (ii) follows from (iii) by passivity in a lossless PEC/`eps_r`-real problem: the missing
  power is either reflected or numerically lost, `1 - |S21|^2 = |S11|^2 + delta_E`.
  `delta_E` is the volume solver's energy-conservation defect, **symbolic**; no value for it
  exists in `.scratch/mode2d/c2_slab.json` (that file is an eigenvalue problem, it has no
  energy budget). **This is missing input #2 and it is not invented.**
* `beta_ref = k0*sqrt(ModeProfile.eps_eff)` (§1.3) — measured at run time from
  `ModeProfile.eps_eff`, so `beta*L` is a formula, not a constant of this document.
* `beta` in (i)–(iii) must come from §1.3. If it does not, the band is vacuous (§5).

**Numeric shape of the band (arithmetic only, `C_2` left symbolic).** With `k0*h` from
§1.4 and `L/h = 12 mm / h`:

| rung | h | k0·h | (C₂/2)(k0h)² | \|dphi\| bound | N = L/h | \|S11\| bound |
|---|---|---|---|---|---|---|
| R1 | 0.2 mm | 4.1917e−02 | 8.785e−04·C₂ | 8.785e−04·C₂·beta·L | 60 | 5.271e−02·C₂ |
| R2 | 0.1 mm | 2.0959e−02 | 2.196e−04·C₂ | 2.196e−04·C₂·beta·L | 120 | 2.636e−02·C₂ |
| R3 | 0.05 mm | 1.0479e−02 | 5.491e−05·C₂ | 5.491e−05·C₂·beta·L | 240 | 1.318e−02·C₂ |

(Check, R2: `(0.020959)^2 / 2 = 2.196e-04`; `120 * 2.196e-04 = 2.636e-02`.)

**Freeze protocol.** `C_2` and `delta_E` may be filled in **only** from a source that
existed before the run (a pre-existing 2-D eigensolve h-refinement, or an independent
published dispersion figure). If no such source exists at run time, the run may **not** be
graded pass/fail on (i)–(iii); only the **order** criterion of §3 is gradable. That is a
weaker verdict and it is the honest one — no number will be produced retroactively.

### 2.4 Provenance of C_2 (frozen — added after §2.3, nothing above changed)

§2.3 left `C_2` symbolic. This subsection *fills it in from sources that existed before the
run*, exactly as the freeze protocol there demands, and records one sign contradiction against
§3.4 rather than resolving it. **Nothing in §1–§2.3 is edited, weakened or deleted by this
addition.**

**What `dt` is.** The stepper's default step is `cfl_dt` (`emfit/evolve.py:68-79`):

```
dt = safety / ( c * sqrt( sum_{axis in x,y,z} 1 / min(widths(axis))^2 ) ),  safety = 0.99, c = C0
```

Docstring `evolve.py:69-73`: "Courant-limited time step `safety/(c sqrt(sum_axis 1/d_axis^2))`;
`d_axis` is the *smallest* cell width on that axis". It is one 3-D expression with no 2-D branch,
consumed as the default at `evolve.py:140` (`self.dt = float(cfl_dt(cc.grid) if dt is None else dt)`),
and duplicated with `safety=1.0` at `emfit/maxwell.py:79-86` (`FITSystem.cfl_dt`). For a grid of
cubic cells `h` in vacuum this gives `dt = 0.99*h/(C0*sqrt(3))`, i.e. an **axial Courant number**

```
S := c*dt/h = 0.99/sqrt(3) = 0.5715768,   S^2 = 0.3267000
```

`dt ∝ h`, so **`S` does not move with the rung** — which is precisely what lets a constant `C_2`
stand in (B1). *Proviso:* `dt` is pinned by the smallest width on each axis, so if a rung's grid is
graded, `S_x = c*dt/h_x ≠ 0.5716` and `C_2` below must be recomputed from the logged `Stepper.dt`.
That must be logged, not assumed.

**Does a closed form exist? Yes — in the test suite, not in `emfit/`.** `tests/test_modalport.py:377-396`
`_dispersion(cc, m_eps, m_mu, dt, f)` implements the 1-D Yee dispersion from the fixture's own
material matrices:

```
sin^2(beta dx/2)/dx^2 = sin^2(omega dt/2)/(c^2 dt^2),   c^2 = 1/(eps mu)  from an E_y edge and an E_z face
s    = sqrt(c1*l1)/dt * sin(omega*dt/2)
beta = 2/DX * arcsin(s)                                    # :393
c_num = DX/sqrt(c1*l1);  vg = c_num*cos(beta*DX/2)/cos(omega*dt/2)   # :394-395
```

Its own docstring says it is "Analytic, computable before the run, nothing fitted" (`:380-382`).
`tests/test_periodic.py:192-227` holds the same relation in the form
`sin(w dt/2) = S sin(k dx/2)`, `k = 2*arcsin(sin(w dt/2)/S)/H`, `v_g = C0 cos(kH/2)/cos(w dt/2)`
(`:220-223`). What the *library* offers instead is only the half-step stagger, closed-form:
`emfit/plane_phasor.py:94-118` `half_step_angle = -pi*f*dt` and `:121-137` `destagger`. That is a
*time-origin* correction with no `k`-dependence and therefore **not** a dispersion coefficient —
nothing in `emfit/` quantifies `beta` error (`emfit/microstrip.py:358` is the continuum
`c0/sqrt(eps_eff)`). So the closed form is available, and `C_2` is *derived*, not guessed; but the
production path does not contain it.

**FROZEN: the homogeneous axial coefficient.** Expand the discrete relation at fixed drive `omega_0`
against the continuum `k_ref = omega_0/c` of the same medium. With `theta = k_ref*h/2`:

```
sin(k_num h/2) = sin(S*theta)/S,   sin(S*theta)/S = theta - S^2 theta^3/6 + O(theta^5)
arcsin(theta - S^2 theta^3/6) = theta + (1 - S^2) theta^3/6
=> k_num = k_ref * [ 1 + (1 - S^2)(k_ref h)^2 / 24 ]
=> (beta_num^2 - beta_ref^2)/beta_ref^2 = [(1 - S^2)/12] * (k0 h)^2
```

so, with `S` the **medium's** Courant number `S_med = C0*dt/h / sqrt(eps_r)`:

```
(2.4a)   C_2^hom = (1 - S_med^2) / 12      [frozen; general axial form C_2 = (1 - S_x^2)/12, S_x = c*dt/dx]
```

| medium | `S_med` | `S_med^2` | **`C_2^hom`** |
|---|---|---|---|
| air, `eps_r = 1` | 0.5715768 | 0.3267000 | **+0.0561083** |
| substrate, `eps_r = 4.4` | 0.2724885 | 0.0742500 | **+0.0771458** |

This reproduces §2.3 exactly: (B2) `|dbeta/beta| = eps2/2` and (B1) `eps2 = C_2 (k0h)^2` are the
same two statements as the expansion above, to the order kept. Evaluating §2.3's band with the
frozen constant (`beta*L = 2.51502*sqrt(eps_eff)` rad, `L = 12 mm`):

| rung | `h` | `(k0h)^2` | `eps2` (air) | `eps2` (substrate) | `\|dphi\|/sqrt(eps_eff)` (air) |
|---|---|---|---|---|---|
| R1 | 0.20 mm | 1.7570e-03 | 9.8585e-05 | 1.3555e-04 | 1.2397e-04 rad |
| R2 | 0.10 mm | 4.3926e-04 | 2.4646e-05 | 3.3887e-05 | 3.0993e-05 rad |
| R3 | 0.05 mm | 1.0982e-04 | 6.1615e-06 | 8.4718e-06 | 7.7482e-06 rad |

**STILL SYMBOLIC — what this does NOT freeze.**

1. **The interface / staircase term.** The line is a staircase of PEC strip and `eps_r` jump on a
   Cartesian mesh. That contribution is an `O(h)` *geometric* error converted to a phase error
   through field sensitivity at the edge; its sign is not fixed a priori (a staircase may over- or
   under-estimate the local `C'` and the edge-field concentration) and its scaling is **not**
   cleanly `(k0h)^2`. It is therefore **not derivable**, and it is left symbolic together with
   **`delta_E`** (§2.3, still no value anywhere in the evidence).
2. **Consequence, stated as an argument and not an assertion.** `C_2^hom` is the *homogeneous axial*
   contribution — definite sign, variance-free, present at every point of the medium. It is a bound
   on the observed error only under the extra stated assumption that the staircase term is
   negligible or of the same sign. The measured `eps2` is the **sum** of (i) and (ii), so
   `C_2 ≈ +0.056…+0.077` is a *central value / predicted contribution*, not a floor. The **order**
   and the rung ratios of §3.1–§3.3 remain the primary gradable criterion; §2.3's freeze protocol
   still forbids grading pass/fail on (i)–(iii) if the staircase term is not pinned.
3. **A-refl is untouched.** Nothing here derives the per-cell *reflection* amplitude of (iii); that
   remains the stated assumption it always was.
4. **Range of validity.** `C_2 (k0h)^2` is asymptotic in `h` against *both* `lambda` and the
   transverse scale (1.6 mm substrate): transverse evanescent content enters at `O((h/H)^2)`, not
   proportional to `(k0h)^2`. At R1 (`k0h = 0.042`) the neglected `O((k0h)^4)` term is ~1e-3 of
   `eps2`, so the rung ratios of §3.1 are unaffected at that level.

**RECORDED CONTRADICTION (added, not resolved; §3.4 is not edited).** `C_2^hom > 0` in *both*
media, so the discrete line is **phase-fast**: `beta_num > beta_ref`, hence

```
dphi = arg(A2/A1) + beta_ref*L = (beta_ref - beta_num)*L < 0   =>   dphi NEGATIVE at every rung.
```

§3.4 infers the opposite (`dphi > 0`) from `c2_slab`'s `all_rel_negative: true`. **The two cannot
both hold.** This document records the contradiction and does not settle it: §3.4's inference is
about a *finite-element cross-section eigensolve* of a 2B slab, this derivation is about the *FDTD
leapfrog axial relation* on a cubic grid — different discretisations, so neither refutes the other.
§3.4 stays exactly as written and is still not a pass/fail item; the sign is to be *reported as
measured*, and a measurement of `dphi > 0` would be evidence that the staircase term (ii) is
negative and dominant, not that `C_2^hom` is wrong. Numeric coincidence, **not** a result: at
`k0h = 0.025`, `C_2^air (k0h)^2 = +3.5068e-05` against `c2_slab`'s `max_abs_rel_dev = -3.1410e-05`
— same magnitude, opposite sign, and (see above) different geometry and discretisation. At the
rung-2 design point `k0h = 0.020959` the same comparison reads `+2.4646e-05` against `-3.1410e-05`.

---

## 3. Refinement ladder and the pre-registered order prediction

Three rungs, halving `h`, same physical geometry, same `f0`, same stations:

| rung | `h` | substrate cells | strip cells | plane nodes `(nyn, nzn)` | `k_strip` (= `n_sub`) | cost ∝ cells·steps ∝ h⁻³ |
|---|---|---|---|---|---|---|
| **R1_coarse** | 0.20 mm | 8 | 16 | (101, 39) | 8 | 1 |
| **R2_production** | 0.10 mm | 16 | 32 | (201, 77) | 16 | 8 |
| **R3_fine** | 0.05 mm | 32 | 64 | (401, 153) | 32 | 64 |

R2 is the production cell (`_FDTD_CELL = 1.0e-4`, `_FDTD_NYN/_FDTD_NZN = 201/77`,
`_FDTD_K_STRIP = 16`, `emfit/mode_profile.py:149-152`). `k_strip` is chosen equal to the
substrate cell count at every rung so the ground plane lands on the plane's own `k = 0`
(`mode_profile.py:332-337`, `:385`). Width and substrate thickness stay integer cell counts
(16/32/64 and 8/16/32 cells) so the geometry is *the same physical line* at each rung —
without that, the ladder measures geometry error, not discretisation error.

**PRE-REGISTERED PREDICTION (part of the acceptance criterion, not a commentary):**

1. **`|dphi|` falls at second order in `h`.** Ratio `|dphi|(R_n) / |dphi|(R_{n+1}) = 3.8 – 4.2`
   for both halvings. This is the direct signature of `eps2 ∝ (k0h)²` in (B1).
2. **`|S11|` falls at *first* order in `h`.** From (iii): `(L/h)` doubles while `(k0h)²`
   quarters, so ratio `= 1.9 – 2.1` per halving. This asymmetry against (1) is the
   distinguishing prediction — a code whose `|S11|` fell at ratio ≈ 4 would mean the
   reflection is not the accumulated per-cell one, i.e. **A-refl is wrong**.
3. **The measured exponent is itself a pass/fail item.** Fit
   `log(|dphi|) = p*log(h) + const` over the three rungs; **`p = 2.0 ± 0.2` is required**.
   A measured `p ≈ 1` (first order) or `p ≈ 0` (floor) is a **fail of the order criterion**
   even if every `|dphi|` number happens to sit inside the §2 band. Refining one rung
   further is allowed; *relaxing* `p` is not (§4).
4. **Sign (secondary, inferred — not a pass/fail item).** `.scratch/mode2d/c2_slab.json`
   has `all_rel_negative: true`, i.e. the finite-element cross-section eigensolve
   under-estimates `beta²`. If the FDTD volume solve inherits the same conservative
   under-estimate, `beta_num < beta_ref` and therefore **`dphi > 0`** at every rung. This
   is recorded as an inference, flagged as such, and must not be turned into a band.

Cost note: R3 is ~64× R1 and ~8× R2 in cells·steps; R3 should be scheduled last and its
result reported even if only R1/R2 complete — two rungs give a ratio but *not* an exponent,
and a two-rung-only result must be reported as "order not established".

---

## 4. No post-hoc relaxation

**Clause 1 — the bar may not move.** Once §2's band and §3's order criterion are frozen,
using the observed numbers to widen `C_2`, to drop a rung, to change `L`, to change
`f0`, to redefine `S11` (e.g. dropping the `b` term), or to reinterpret `p = 2.0 ± 0.2` as
"approximately second order", is a **breach of this pre-registration**. The precedent is
explicit: `high_res_run.py:195` is the place where an observed value was used to move a
bar, and that is the failure mode this document exists to prevent. If the band turns out to
be wrong, the *correct* response is to record "band failed / band was mis-derived", publish
the numbers, and write a **new** pre-registration for the next attempt — not to edit this
one.

**Clause 2 — `beta` must come from outside the extraction.** `S11 = 0` and
`S21 = exp(-j*beta*L)` are only meaningful if `beta` is fixed by something other than
`A1, A2`. §1.5 defines `S11` as the two-station non-forward residual and `dphi` with
`beta_ref` in it; **if `beta` is fitted to `A1, A2` (or to any phasor from the same run),
then `S11 ≡ 0` and `S21 = exp(-j*beta_ref*L)` hold algebraically, for any code, correct or
broken.** That is the audit's "exact by construction" class of non-result and is forbidden
here. Sanctioned sources for `beta`, in order of preference:
(a) `beta_ref = k0*sqrt(ModeProfile.eps_eff)` — quasi-static 2-D capacitance solve
(`emfit/mode_profile.py:244`, `:280`, `:535`), independent of the FDTD run;
(b) `beta` from the 2-D cross-section eigensolve `emfit.mode2d.solve_modes_mixed`
(`.scratch/mode2d/c2_slab.json:entry_point`) — also independent, mesh-consistent, and
carrying its own known error (§2.2).
Nothing else is admissible. The `beta` actually used, and its source, must be printed with
every number in §5.

**Clause 3 — no hidden second reference.** The profile used for the projection (stage 2)
and the profile used to form `beta_ref` must be the **same** `ModeProfile` object, and its
`eps_eff`, `z0` and normalisation must be logged. A run that projects onto one mode and
compares to another mode's `beta` is not a test of anything.

---

## 5. Results

| rung | `h` [mm] | `f0` [GHz] | `beta_ref` [rad/m] (source) | `beta_ref*L` [rad] | `arg(A2/A1)+beta_ref*L` = `dphi` [rad] | \|S21\| | \|S11\| | `1−(\|S11\|²+\|S21\|²)` | verdict vs §2 band | verdict vs §3 order |
|---|---|---|---|---|---|---|---|---|---|---|
| R1_coarse | 0.20 | 10.0 | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* |
| R2_production | 0.10 | 10.0 | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* |
| R3_fine | 0.05 | 10.0 | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* | *(pending)* |

Fitted exponent: `p = ______` (required `2.0 ± 0.2`) ·
Rung ratios `|dphi|(R1)/|dphi|(R2) = ______`, `|dphi|(R2)/|dphi|(R3) = ______`
(required `3.8 – 4.2`) · `|S11|` ratios `______`, `______` (required `1.9 – 2.1`).
`C_2` used (if any) and its pre-existing source: `______`.
Overall: *(pending)* — **this table may be filled only after §2 and §3 are frozen, and may
not be edited afterwards.**
