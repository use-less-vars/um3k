# PML absorber: working notes

Milestone log, one line per step, so a later turn can resume where this one stopped.

- M1 (read): signatures recorded below; no existing file modified.

## M1: what the codebase actually looks like (read only, nothing changed)

The solver is **not** a 2-D `Ez/Hx/Hy` scalar array set.  It is a 3-D FIT
(discrete-curl) scheme on flat vectors, and a 2-D TM_z problem is run as a
one-cell-thick slab pinned by PEC on the two z planes.  The mapping to the
brief's "(Ez on corners, Hx at (i, j+1/2), Hy at (i+1/2, j))" is the edge/face
centres below: an edge along x has its along-axis coordinate at a cell centre
and its transverse coordinates at node values, which is the same staggering.

Exact signatures found:

```
emfit/grid.py
  class Grid:  x, y, z: np.ndarray, periodic: tuple = (False, False, False)
  Grid.uniform(cls, nx, ny, nz, lx=1.0, ly=1.0, lz=1.0,
               origin=(0.0, 0.0, 0.0), periodic=(False, False, False))
  Grid.nodes(self, axis: str) -> int
  Grid.is_periodic(self, axis: str) -> bool
  Grid.widths(self, axis) / Grid.dual_widths(self, axis)
  Grid.edge_shape(self, axis) / Grid.face_shape(self, axis)
  Grid.edge_length(self, axis)
  Grid.face_area_x/y/z(self), Grid.dual_face_area_x/y/z(self)

emfit/operators.py
  class CellComplex(grid)            # curl = cc.curl(), curl_dual = cc.curl_dual()
  cc.idx_ex / idx_ey / idx_ez (i, j, k) -> flat edge index
  cc.off_ex .. off_ez, cc.n_ex .. n_ez, cc.n_edges
  cc.off_fx .. off_fz, cc.n_fx .. n_fz, cc.n_faces
  cc.nxn, cc.nyn, cc.nzn            # point layers per axis
  cc.pec_edge_mask(planes)

emfit/evolve.py
  def ricker(t, t0, fmax)
  def cfl_dt(grid, c: float = C0, safety: float = 0.99) -> float
  class FITStepper(cc, m_eps, m_mu, dt: float | None = None, pec=None)
      .e ndarray (n_edges,)   .h ndarray (n_faces,)   .dt   .time   .n
      .step(j=None)   .energy()   .energy_components()   .run(nsteps, probe=None, source=None, callback=None)
  class RickerSource(n_edges, idx, fmax, t0=None, amplitude=1.0)
  class Leapfrog(FITStepper)

emfit/abc.py
  ALL_PLANES = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
  class Mur1Boundary(grid, dt, cc=None, planes=ALL_PLANES, pec=None, c=C0)
      .apply(e_new, e_prev=None)   .update_history(e)   .reset_history()   .plane_summary()

emfit/materials.py
  material_matrices(grid, cc, eps_r=1.0, mu_r=1.0) -> (m_eps (n_edges,), m_mu (n_faces,))
  C0, EPS0, MU0, ETA0 = MU0 * C0
  _centres(grid, axis, along_mid)   # edge centres (True) / face centres (False)

emfit/studies.py
  DUCT_LX, DUCT_LY, DUCT_LZ = 2.4, 0.64, 0.04 m;  DUCT_F0 = 2.0 GHz
  DUCT_SIDE_WALLS = ("ymin", "ymax", "zmin", "zmax");  DUCT_ABC_PLANES = ("xmin", "xmax")
  Param("termination", "far-end termination", "choice", "mur", choices=("mur", "pec"))
```

Storage summary: `e` is `concat(EX, EY, EZ)` by the `off_ex/off_ey/off_ez`
blocks of length `n_ex, n_ey, n_ez`; `h` is `concat(HX, HY, HZ)` by
`off_fx .. off_fz`.  Both are 1-D float64, so a matched layer is a flat
per-entry multiplier plus a flat conductivity array - no reshaping, no
auxiliary variables, no change to `C` or `C.T`.

`FITStepper.step` order inside one call: `h -= dt*inv_m_mu*(C e)`, then
`ce = C_tilde @ h`, `e += dt*inv_m_eps*ce`, then the PEC reset.  So the two
damping points are: straight after the `h` update, and straight after the `e`
update (i.e. at the end of the step, before the PEC reset - PEC wins on the
walls either way).


### Two lessons from the 2024 reflection measurements

- **Window trap.**  A shared probe window must span *both* echoes: the wall echo (~3.3 ns after the source peak) *and* the PML interface echo (~2.0 ns). A window that closes before the Mur echo arrives differences to float noise (-186 dB) and made Mur look 109 dB better than it is — the comparison must be timed from the arrival table, never eyeballed.
- **Wavelength law.**  Thickness in dB is linear: ~-52 dB at one free-space wavelength, ~-79 dB at two, mesh independent to 0.6 dB between 20 and 40 ppw. `emfit.pml.cells_for_wavelength(lam0, h)` encodes it.
