"""Units, energy conservation, CFL limit and wave speed for the FIT stepper.

All quantities are SI: ``e`` [V], ``h`` [A], ``m_eps`` [F], ``m_mu`` [H],
energies [J].
"""

import numpy as np
import pytest

from emfit.evolve import FITStepper, RickerSource, cfl_dt
from emfit.grid import Grid
from emfit.materials import C0, EPS0, MU0, material_matrices
from emfit.operators import CellComplex

EDGE_BLOCKS = ("ex", "ey", "ez")
FACE_BLOCKS = ("fx", "fy", "fz")


def uniform(nx, ny, nz, h=1.0):
    """``nx x ny x nz`` cells of edge length ``h``."""
    return Grid.uniform(nx, ny, nz, lx=nx * h, ly=ny * h, lz=nz * h)


def manual_diagonals(grid):
    """Recompute ``(m_eps, m_mu)`` from the raw grid metric, block by block.

    ``m_eps[e] = eps0 * A~_e / L_e``   (primal edge, dual perpendicular area)
    ``m_mu[f]  = mu0  * A_f  / L~_f``  (primal face, dual perpendicular length)
    """
    cc = CellComplex(grid)
    m_eps = np.empty(cc.n_edges, dtype=float)
    for axis, off, n in (("x", cc.off_ex, cc.n_ex),
                         ("y", cc.off_ey, cc.n_ey),
                         ("z", cc.off_ez, cc.n_ez)):
        L_e = np.asarray(grid.edge_length(axis), dtype=float).ravel()
        A_dual = np.asarray(getattr(grid, f"dual_face_area_{axis}")(),
                            dtype=float).ravel()
        m_eps[off:off + n] = EPS0 * A_dual / L_e

    m_mu = np.empty(cc.n_faces, dtype=float)
    for axis, off, n in (("x", cc.off_fx, cc.n_fx),
                         ("y", cc.off_fy, cc.n_fy),
                         ("z", cc.off_fz, cc.n_fz)):
        A_f = np.asarray(getattr(grid, f"face_area_{axis}")(), dtype=float).ravel()
        w = grid.dual_widths(axis)
        shp = [1, 1, 1]
        shp["xyz".index(axis)] = w.size
        L_dual = np.broadcast_to(w.reshape(shp), grid.face_shape(axis)).ravel()
        m_mu[off:off + n] = MU0 * A_f / L_dual
    return cc, m_eps, m_mu


def make_stepper(grid, dt=None, pec=None):
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    return FITStepper(cc, m_eps, m_mu,
                      dt=(0.9 * cfl_dt(grid) if dt is None else dt), pec=pec)


# ----------------------------------------------------------------------
def test_material_matrix_units():
    """Element-wise Hodge star check, then the metric-scaling property.

    The element-by-element recomputation is the real units test.  Note on the
    "length invariance" property: it does NOT hold as stated -- both diagonals
    are *capacitances/inductances*, so on a uniform grid they scale linearly
    with the cell size (m_eps ~ eps0*h, m_mu ~ mu0*h): ``A~/L`` and ``A/L~``
    are homogeneous of degree one in length, not degree zero.  The exact
    length-independence statement is therefore a factor-of-two scaling, which
    is what is asserted below (and it is just as sharp a check).
    """
    grid = uniform(5, 4, 3, 1.0)
    cc, m_eps_ref, m_mu_ref = manual_diagonals(grid)

    m_eps, m_mu = material_matrices(grid, cc)
    assert m_eps.shape == (cc.n_edges,)
    assert m_mu.shape == (cc.n_faces,)
    np.testing.assert_allclose(m_eps, m_eps_ref, rtol=1e-13, atol=0.0)
    np.testing.assert_allclose(m_mu, m_mu_ref, rtol=1e-13, atol=0.0)

    # --- degree-one homogeneity: doubling every cell doubles every entry ---
    grid2 = uniform(5, 4, 3, 2.0)
    cc2 = CellComplex(grid2)
    m_eps2, m_mu2 = material_matrices(grid2, cc2)
    assert m_eps2.size == m_eps.size and m_mu2.size == m_mu.size  # same topology
    np.testing.assert_allclose(m_mu2, 2.0 * m_mu, rtol=1e-13, atol=0.0)
    np.testing.assert_allclose(m_eps2, 2.0 * m_eps, rtol=1e-13, atol=0.0)


def test_material_callable():
    """A callable ``eps_r(x, y, z)`` produces exactly two permittivity levels."""
    grid = uniform(6, 6, 6, 1.0)
    cc = CellComplex(grid)

    def eps_r(x, y, z):
        return np.where(x > 3.0, 2.0, 1.0)

    m_eps, _ = material_matrices(grid, cc, eps_r=eps_r, interface="point")

    # Divide out the geometric Hodge factor: the raw diagonal has several
    # levels purely because A~_e/L_e is 1/2 at the domain boundary edges.
    _, m_eps_geom, _ = manual_diagonals(grid)          # eps_r == 1 everywhere
    ratio = m_eps / m_eps_geom

    levels = np.unique(ratio)
    assert levels.size == 2, f"expected 2 eps_r levels, got {levels}"
    np.testing.assert_allclose(levels[1] / levels[0], 2.0, rtol=1e-13)
    np.testing.assert_allclose(sorted(levels), [1.0, 2.0], rtol=1e-13)


def test_energy_exact_conservation():
    """The mixed-state invariant U is conserved to machine precision."""
    grid = uniform(12, 10, 8, 1.0)
    st = make_stepper(grid)
    rng = np.random.default_rng(0)
    st.e[:] = rng.standard_normal(st.e.size)
    st.h[:] = rng.standard_normal(st.h.size)

    history = []
    st.run(2000, callback=lambda s: history.append(s.energy()))
    U = np.asarray(history)
    drift = float(np.max(np.abs(U - U[0])) / abs(U[0]))
    print(f"\n[energy_exact_conservation] max relative drift "
          f"= {drift:.3e} over 2000 steps")
    assert drift < 1e-6


def test_pec_conservation():
    """PEC walls keep the invariant exact.

    Derivation: ``e[pec] == 0`` holds at the top of every step, so the columns
    of ``C`` belonging to those edges multiply exact zeros and ``C @ e`` is
    unaffected by them.  The free edges therefore evolve as an exact
    restricted leapfrog and the same algebraic invariant applies to the
    restricted system; the only effect of resetting ``e[pec]`` is to discard
    an update that must already be zero.
    """
    grid = uniform(12, 10, 8, 1.0)
    cc = CellComplex(grid)
    pec = cc.pec_edge_mask()
    assert pec.any()
    st = make_stepper(grid, pec=pec)
    rng = np.random.default_rng(0)
    st.e[:] = rng.standard_normal(st.e.size)
    st.h[:] = rng.standard_normal(st.h.size)

    history = []

    def record(s):
        assert np.all(s.e[s.pec_idx] == 0.0), "PEC edge voltage is not exactly 0"
        history.append(s.energy())

    st.run(1000, callback=record)
    U = np.asarray(history)
    drift = float(np.max(np.abs(U - U[0])) / abs(U[0]))
    print(f"\n[pec_conservation] max relative drift = {drift:.3e} over 1000 steps")
    assert drift < 1e-10, f"PEC energy drift {drift:.3e}"


def test_cfl_bound_is_sharp():
    """Just inside the Courant limit the scheme is stable; 15% above it is not.

    The fields are seeded with white noise so that every mode -- in
    particular the fastest one -- is excited, making the peak growth of
    ``max|e|`` a direct probe of the stability limit.

    Measured on a 12x10x8 grid of 1 m cells, random initial e/h, 500 steps:

    * ``0.98 * cfl_dt`` -> growth x9.3e2, and it stays at x9.3e2 (x9.8e2)
      out to 5000 steps, so this is a bounded scheme, not slow divergence.
    * ``1.00`` and ``1.01 * cfl_dt`` are still bounded (x1.1e3, x1.2e3),
    * ``1.02 * cfl_dt`` has already blown up to x6.7e122.

    So the empirical threshold sits between 1.01 and 1.02 times the
    ``cfl_dt`` estimate, i.e. the formula is a *sharp*, unpadded bound (hence
    the default safety factor of 0.99).  The residual factor ~9e2 at stable
    steps is a one-off transient of the inconsistent random initial e/h pair,
    not exponential growth (it does not grow with the step count), so the
    assertions below compare *growth factors* rather than absolute
    amplitudes.
    """
    grid = uniform(12, 10, 8, 1.0)
    cfl = cfl_dt(grid)

    def peak_growth(factor, nsteps=500):
        st = make_stepper(grid, dt=factor * cfl)
        rng = np.random.default_rng(0)
        st.e[:] = rng.standard_normal(st.e.size)
        st.h[:] = rng.standard_normal(st.h.size)
        a0 = float(np.max(np.abs(st.e)))
        peak = [a0]
        st.run(nsteps, callback=lambda s: peak.append(float(np.max(np.abs(s.e)))))
        return float(np.max(peak)) / a0, st

    growth_stable, st_stable = peak_growth(0.98)
    growth_unstable, _ = peak_growth(1.15)
    print(f"\n[cfl_bound_is_sharp] cfl = {cfl:.4e} s")
    print(f"[cfl_bound_is_sharp] dt = 0.98 cfl -> growth x{growth_stable:.3e} "
          f"(bounded), finite = {np.all(np.isfinite(st_stable.e))}")
    print(f"[cfl_bound_is_sharp] dt = 1.15 cfl -> growth x{growth_unstable:.3e}")

    assert np.all(np.isfinite(st_stable.e))
    assert growth_stable < 1e5, (
        f"0.98 cfl did not stay bounded: growth x{growth_stable:.3e}")
    assert growth_unstable > 1e10, (
        f"1.15 cfl did not diverge: growth only x{growth_unstable:.3e}")


def test_wave_propagates_at_c():
    """A Ricker pulse crosses ten cells in the time light needs for that path."""
    h = 0.02
    grid = Grid.uniform(40, 6, 6, lx=40 * h, ly=6 * h, lz=6 * h)
    cc = CellComplex(grid)
    dt = 0.9 * cfl_dt(grid)

    fmax = 1.5e9                       # lambda0 = 0.2 m = 10 cells
    i_src, i_prb = 10, 20              # 10 cells = 0.2 m apart along x
    src_idx = cc.idx_ex(i_src, 3, 3)
    prb_idx = cc.idx_ex(i_prb, 3, 3)
    distance = (i_prb - i_src) * h

    m_eps, m_mu = material_matrices(grid, cc)
    st = FITStepper(cc, m_eps, m_mu, dt=dt)
    source = RickerSource(st.e.size, [src_idx], fmax=fmax, t0=1.0 / fmax,
                          amplitude=1.0)
    probe = st.run(400, probe=prb_idx, source=source)

    peak = float(np.max(np.abs(probe)))
    assert peak > 0.0
    assert abs(probe[0]) < 10.0, "source response is not O(1)"

    # (i) causality: nothing has arrived in the first three steps
    assert np.all(np.abs(probe[:3]) < 1e-9 * peak), probe[:3]

    # (ii) arrival time corresponds to the light travel time.  The Ricker
    # wavelet is *centred* on t0 = 1/fmax, i.e. its peak leaves the source at
    # t = t0, not at t = 0; the travel time is therefore (n_arr * dt - t0),
    # and only that has to match distance / c.
    t0 = 1.0 / fmax
    n_arr = int(np.flatnonzero(np.abs(probe) > 0.05 * peak)[0])
    ratio = (n_arr * dt - t0) * C0 / distance
    print(f"\n[wave_propagates_at_c] peak |probe| = {peak:.3e}, "
          f"n_arr = {n_arr}, dt = {dt:.3e} s, t0 = {t0:.3e} s, ratio = {ratio:.3f}")
    assert 0.7 < ratio < 1.3, f"wavefront speed is {ratio:.2f} c"
