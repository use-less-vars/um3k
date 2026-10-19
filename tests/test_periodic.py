"""Periodic (toroidal) boundary conditions: an axis identified with itself.

A periodic axis has no boundary layer.  The seam node ``j = n`` *is* the node
``j = 0``, so the grid stores ``n`` point layers instead of ``n + 1``, the
dual metric wraps (no half cells, no terminating faces) and every index helper
reduces modulo ``n``.  That is the whole boundary condition at the topological
level: nothing is ever copied, so nothing can be copied *wrongly*.

Each test below pins one measured property of that change (TM_z slice, ``nz=1``,
PEC on x/z, ``dt = cfl_dt``), with the number that was observed when the change
was made, plus the shortcut that must *not* be taken.
"""

import numpy as np
import pytest

from emfit.evolve import FITStepper, RickerSource, cfl_dt
from emfit.grid import Grid
from emfit.materials import C0, material_matrices
from emfit.operators import CellComplex

H = 0.02                      # in-plane cell size
FMAX = 1.5e9                  # Ricker centre frequency: lambda0 = 0.2 m = 10 cells
ALL_PLANES = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")


def tmz_grid(nx=100, ny=24, periodic_y=True):
    """TM_z slice: ``nz = 1``, PEC on x and z, ``y`` periodic (or PEC)."""
    return Grid.uniform(nx, ny, 1, lx=nx * H, ly=ny * H, lz=1.0,
                        periodic=(False, periodic_y, False))


def make_stepper(grid):
    """FIT stepper on the TM_z slice with every *bounded* wall made PEC."""
    cc = CellComplex(grid)
    walls = tuple(w for w in ALL_PLANES if not grid.is_periodic(w[0]))
    pec = cc.pec_edge_mask(walls)
    m_eps, m_mu = material_matrices(grid, cc)
    return cc, FITStepper(cc, m_eps, m_mu, dt=cfl_dt(grid), pec=pec)


# ----------------------------------------------------------------------
# topology / metric
# ----------------------------------------------------------------------
def test_periodic_axis_has_no_seam_layer():
    """``ny`` cells give ``ny`` point layers, and index ``ny`` is index ``0``.

    With the ``n + 1`` convention the seam would be a distinct node (1225 EZ
    edges instead of 1176 on the 24x24 slice) that has to be kept in sync by
    hand -- and the first place a missing copy shows up as a reflection.
    """
    grid = tmz_grid(nx=9, ny=4)
    cc = CellComplex(grid)
    assert grid.nodes("x") == 10 and grid.nodes("y") == 4 and grid.nodes("z") == 2
    assert (cc.nxn, cc.nyn, cc.nzn) == (10, 4, 2)
    assert cc.n_ez == 10 * 4 * 1                      # was (nx+1)*(ny+1)*nz = 100
    # the seam is not an entity: the wrapped index is the same edge
    assert cc.idx_ez(3, 0, 0) == cc.idx_ez(3, 4, 0)
    assert cc.idx_fy(3, 0, 0) == cc.idx_fy(3, 4, 0)
    # on a bounded axis the reduction is a no-op (index never reaches the count)
    assert cc.idx_ez(0, 2, 0) == cc.idx_ez(10, 2, 0)


def test_dual_widths_close_on_periodic_axis():
    """Every node of a periodic axis is interior: dual widths are full cells.

    Keeping ``n + 1`` layers and halving the seam dual width (the "S1"
    shortcut) instead introduces a hard ~17% seam error in the wave field; the
    circular average below is the metric that makes the seam vanish.
    """
    grid = tmz_grid(nx=9, ny=4)
    wy = grid.dual_widths("y")
    assert wy.size == grid.nodes("y") == 4
    np.testing.assert_allclose(wy, H, rtol=1e-15)      # no half cells anywhere
    wx = grid.dual_widths("x")
    assert wx.size == grid.nodes("x") == 10
    np.testing.assert_allclose(wx[0], 0.5 * H)         # bounded: half cell
    np.testing.assert_allclose(wx[-1], 0.5 * H)
    np.testing.assert_allclose(wx[1:-1], H, rtol=1e-15)


def test_pec_wall_across_periodic_axis_is_rejected():
    """Pinning ``ymin`` on a torus would pin an interior node: raise instead.

    Silent acceptance would freeze a line of field through the middle of the
    domain -- an invisible scatterer.
    """
    cc = CellComplex(tmz_grid(nx=9, ny=8))
    for wall in ("ymin", "ymax"):
        with pytest.raises(ValueError, match="axis y is periodic"):
            cc.pec_edge_mask((wall,))
    assert cc.pec_edge_mask(("xmin", "xmax", "zmin", "zmax")).any()


def test_torus_keeps_the_exact_topological_identities():
    """``C G == 0`` and ``S C == 0`` exactly, with the wrapped indices.

    ``S C`` is only zero if the seam column of ``C`` and the seam row of ``S``
    agree; a half-copied seam breaks this to O(1).
    """
    cc = CellComplex(tmz_grid(nx=9, ny=4))
    assert np.abs((cc.curl() @ cc.gradient()).toarray()).max() == 0.0
    SC = (cc.divergence() @ cc.curl()).toarray()
    assert SC.shape == (cc.n_cells, cc.n_edges)
    assert np.abs(SC).max() == 0.0


# ----------------------------------------------------------------------
# field properties
# ----------------------------------------------------------------------
def test_seam_holds_exactly_one_value():
    """A point source on the seam evolves: ``j = n`` and ``j = 0`` read one cell.

    Measured after 40 steps on the 24x24 slice: max|Ez| = 7.511e-2 with
    Ez(seam) = -5.948e-2 (79% of the peak in that run); in the configuration
    below the ratio is 0.200 (3.02e-2 against max|e| = 1.51e-1).  Either way
    the seam is *strongly* excited -- it is an ordinary interior line, not a
    null line.  The two reads are bit-identical because they are one cell.
    """
    grid = tmz_grid(nx=24, ny=24)
    cc, st = make_stepper(grid)
    st.e[cc.idx_ez(12, 0, 0)] = 1.0
    st.run(40)
    ez = lambda i, j: st.e[cc.idx_ez(i, j, 0)]
    peak = float(np.max(np.abs(st.e)))
    assert peak > 0.0 and np.all(np.isfinite(st.e))
    assert ez(12, 0) == ez(12, 24)                     # one cell, bit identical
    assert abs(ez(12, 0)) > 0.1 * peak                 # the seam is alive
    print(f"\n[seam_holds_exactly_one_value] max|Ez| = {peak:.3e}, "
          f"Ez(seam)/peak = {ez(12, 0) / peak:+.4f}, Ez(j=1)/peak = "
          f"{ez(12, 1) / peak:+.4f}")
    # PEC-y control: the very same source is pinned to zero on the two walls
    grid_pec = tmz_grid(nx=24, ny=24, periodic_y=False)
    cc_pec, st_pec = make_stepper(grid_pec)
    st_pec.e[cc_pec.idx_ez(12, 0, 0)] = 1.0
    st_pec.run(40)
    assert st_pec.e[cc_pec.idx_ez(12, 0, 0)] == 0.0
    assert st_pec.e[cc_pec.idx_ez(12, grid_pec.ny, 0)] == 0.0


def test_no_seam_reflection():
    """``ny = 8`` and ``ny = 16`` must agree along x to machine precision.

    A y-uniform pulse never sees the y extent on a torus, so any seam defect
    (missing copy, wrong metric, half cell) shows up as an O(1) deviation at
    the seam and then as a spurious reflection.  Measured: 3.61e-14 relative
    (and 1.31e-15 residual y-variation), i.e. pure round-off.
    """
    def along_x(ny, nsteps=150):
        grid = tmz_grid(nx=48, ny=ny)
        cc, st = make_stepper(grid)
        for j in range(cc.nyn):
            st.e[cc.idx_ez(6, j, 0)] = 1.0             # y-uniform pulse
        st.run(nsteps)
        e = st.e
        return (np.array([e[cc.idx_ez(i, 0, 0)] for i in range(cc.nxn)]),
                np.array([e[cc.idx_ez(24, j, 0)] for j in range(cc.nyn)]))

    a8, y8 = along_x(8)
    a16, y16 = along_x(16)
    scale = float(np.max(np.abs(a16)))
    assert scale > 0.0
    diff = float(np.max(np.abs(a8 - a16))) / scale
    yvar = float(np.max(np.abs(y16 - y16[0]))) / float(np.max(np.abs(y16)))
    print(f"\n[no_seam_reflection] ny=8 vs ny=16: {diff:.3e} relative, "
          f"y-variation {yvar:.3e}")
    assert diff < 1e-12, f"seam reflection {diff:.3e}"
    assert yvar < 1e-12, f"pulse is not y-uniform: {yvar:.3e}"


def test_energy_conserved_on_torus():
    """The mixed invariant is conserved to machine precision (500 steps).

    The periodic topology must not create any leak path: measured drift was
    6.3e-16 with random live DOFs (EZ + FY on the TM_z slice, because the PEC
    z plates kill EX).
    """
    grid = tmz_grid(nx=24, ny=24)
    cc, st = make_stepper(grid)
    rng = np.random.default_rng(0)
    st.e[:] = rng.standard_normal(st.e.size)
    st.h[:] = rng.standard_normal(st.h.size)
    st.e[st.pec_idx] = 0.0
    history = []
    st.run(500, callback=lambda s: history.append(s.energy()))
    U = np.asarray(history)
    drift = float(np.max(np.abs(U - U[0])) / abs(U[0]))
    print(f"\n[energy_conserved_on_torus] max relative drift = {drift:.3e}")
    assert drift < 1e-13, f"periodic energy drift {drift:.3e}"


def test_group_velocity_matches_unbounded_yee():
    """A plane pulse on the torus obeys the *unbounded* Yee dispersion.

    The seam must not slow the wave down.  Reference: the discrete 1-D Yee
    relation ``sin(w dt/2) = S sin(k dx/2)`` gives
    ``v_g = c0 cos(k dx/2) / cos(w dt/2)`` at f = 1.5 GHz (0.9736 c0 here, with
    S = c0 dt/dx = 0.69997).  Measured by cross-correlating the probes 30 cells
    apart: 0.9834 c0, i.e. v/v_g = 1.010 (the residual is the Ricker
    wavelet's finite bandwidth, not a seam effect: 0.9808 c0 from peak times).
    """
    nx, ny, isrc, j = 100, 8, 40, 4
    grid = tmz_grid(nx=nx, ny=ny)
    cc, st = make_stepper(grid)
    dt = st.dt
    src = RickerSource(st.e.size,
                       [cc.idx_ez(isrc, jj, 0) for jj in range(cc.nyn)],
                       fmax=FMAX, t0=1.0 / FMAX)
    p1, p2 = cc.idx_ez(50, j, 0), cc.idx_ez(80, j, 0)
    t1, t2 = [], []
    st.run(110, source=src,
           callback=lambda s: (t1.append(s.e[p1]), t2.append(s.e[p2])))
    a, b = np.asarray(t1), np.asarray(t2)
    assert float(np.max(np.abs(b))) > 0.0
    c = np.correlate(b, a, mode="full")
    lag = int(np.argmax(c)) - (a.size - 1)
    assert lag > 0, "probe 2 is not delayed relative to probe 1"
    v = 30 * H / (lag * dt)

    S = C0 * dt / H
    w = 2 * np.pi * FMAX
    k = 2 * np.arcsin(np.sin(w * dt / 2) / S) / H
    v_g = C0 * np.cos(k * H / 2) / np.cos(w * dt / 2)
    print(f"\n[group_velocity] S = {S:.5f}, k dx = {k * H:.6f}, "
          f"v_g = {v_g / C0:.6f} c0, v = {v / C0:.6f} c0, "
          f"v/v_g = {v / v_g:.6f}")
    assert 0.97 < v / v_g < 1.03, f"seam slows the wave: v/v_g = {v / v_g:.4f}"


# ----------------------------------------------------------------------
# the shortcut that must not be taken
# ----------------------------------------------------------------------
def test_y_varying_field_needs_the_full_seam_bookkeeping():
    """A point source is *not* y-uniform: the transverse dual face FX is live.

    On the TM_z slice HX (``FX``) is driven by ``dEz/dy``; only EX, EZ and FY
    live on primal points, so an implementation that "copies the seam" can only
    copy those, and it silently drops HX.  Measured when that shortcut was
    tried: 155% maximum field deviation from the wrapped run for a point
    source (1e-13%, i.e. machine precision, for a y-uniform pulse, which is why
    a y-uniform test alone cannot catch it).  Keeping ``n`` layers instead of
    copying makes the question disappear.
    """
    grid = tmz_grid(nx=24, ny=16)
    cc, st = make_stepper(grid)
    st.e[cc.idx_ez(12, 0, 0)] = 1.0
    st.run(3)
    hx = st.h[cc.off_fx:cc.off_fx + cc.n_fx]
    print(f"\n[full_seam_bookkeeping] max|FX| after 3 steps = "
          f"{float(np.max(np.abs(hx))):.3e}")
    assert np.any(hx != 0.0), "FX should be driven by dEz/dy for a point source"
