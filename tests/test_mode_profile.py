"""Tests for :mod:`emfit.mode_profile`, the transverse field of the microstrip.

The module's own ``check=True`` path already asserts the algebraic identities
that tie the edge field to :func:`emfit.quasistatic.capacitance_per_length`; the
tests below deliberately do *not* repeat those.  They pin the claims that the
profile makes in its **own** terms, i.e. things a caller can verify from the
returned arrays alone:

1. ``e`` is the gradient of ``phi`` on the staggered edges (one-sided difference
   per edge, y-edges on y-cells x z-nodes, z-edges on y-nodes x z-cells).
2. The ``1 V`` normalisation telescopes exactly over the gap cells of *every*
   strip column, and does not over a column that misses the strip.
3. The field in the gap points from the strip to the ground plane, ``e_z < 0``,
   under the whole strip (not merely on average).
4. The field under the strip is predominantly vertical.
5. ``h`` is the local plane-wave companion of ``e``, ``h_z = e_y / eta_eff`` and
   ``h_y = -e_z / eta_eff``.
6. :meth:`ModeProfile.plane_window` places the profile in an FDTD plane by
   integer offset and **clips with a report** when the plane is smaller -- both
   branches, with the numbers a reader needs to see what moved.

Geometry.  Two sections appear below:

* the *coarse* section ``h = 1.6 mm``, ``W = 1.6 mm`` (``w/h = 1``), ``eps_r =
  4.4``, ``n_sub = 4`` substrate cells, 20 clean cells each side and above.
  ``cell = 0.4 mm``, 45 x 25 nodes, ``n_strip = 4``: fast, and coarse enough that
  the gap is only 4 cells -- fine for the algebraic claims, whose tolerance is
  roundoff, and for signs;
* the *converged* section, the module defaults: ``h = 1.6 mm``, ``W = 3.0 mm``,
  ``n_sub = 16`` (``cell = 0.1 mm``, the production board's own cell), 200 clean
  cells each side and above.  431 x 217 nodes, ``eps_eff = 3.35001``,
  ``Z0 = 50.088 ohm``.  Used where the box must be *wider* than the FDTD plane,
  which is exactly the case :meth:`plane_window` has to clip.

Every pin below was measured on this code; the assertion messages carry the
numbers so a failure shows what moved without a re-run.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pytest

from emfit.mode_profile import (
    PlaneWindow,
    microstrip_mode_profile,
)

# ---------------------------------------------------------------------------
# shared sections
# ---------------------------------------------------------------------------
H_SUB = 1.6e-3
EPS_SUB = 4.4

#: Coarse section: ``w/h = 1``, four substrate cells, 20 clean cells around.
W_COARSE = 1.6e-3
N_SUB_COARSE = 4
N_CLEAN_COARSE = 20
N_AIR_COARSE = 20

#: Converged section: the module defaults, ``w/h = 1.875``.
W_CONVERGED = 3.0e-3


@lru_cache(maxsize=1)
def _coarse():
    """The 45 x 25 node section; cached because several tests share it."""
    return microstrip_mode_profile(
        H_SUB,
        W_COARSE,
        EPS_SUB,
        n_sub=N_SUB_COARSE,
        n_clean=N_CLEAN_COARSE,
        n_air=N_AIR_COARSE,
    )


@lru_cache(maxsize=1)
def _converged():
    """The default 431 x 217 node section (~10 s); cached for the same reason."""
    return microstrip_mode_profile(H_SUB, W_CONVERGED, EPS_SUB)


# ---------------------------------------------------------------------------
# 1. the edge field is the gradient of the potential
# ---------------------------------------------------------------------------
def test_edge_field_is_the_potential_gradient():
    """``e_y[i, k] = -(phi[i+1, k] - phi[i, k])`` and likewise in ``z``.

    This is the claim the whole module rests on: the arrays are the staggered
    edge integrals of one scalar solve, not an interpolation of it.  Nothing is
    approximated, so the tolerance is roundoff (``1e-12`` relative to the
    largest edge) rather than a physics band.
    """
    p = _coarse()
    phi = p.phi
    scale = max(np.abs(p.e_y).max(), np.abs(p.e_z).max())

    gy = -np.diff(phi, axis=0)                      # (ny, N2): y-edges
    gz = -np.diff(phi, axis=1)                      # (N1, nz): z-edges
    err_y = np.abs(p.e_y - gy).max()
    err_z = np.abs(p.e_z - gz).max()
    assert err_y <= 1e-12 * scale, (
        f"e_y is not -d(phi)/dy: max |e_y + diff(phi, y)| = {err_y:.3e} V "
        f"against a largest edge of {scale:.3e} V "
        f"(rel {err_y / scale:.3e}), shapes e_y {p.e_y.shape} diff {gy.shape}"
    )
    assert err_z <= 1e-12 * scale, (
        f"e_z is not -d(phi)/dz: max |e_z + diff(phi, z)| = {err_z:.3e} V "
        f"against a largest edge of {scale:.3e} V "
        f"(rel {err_z / scale:.3e}), shapes e_z {p.e_z.shape} diff {gz.shape}"
    )


# ---------------------------------------------------------------------------
# 2. the 1 V normalisation, exactly
# ---------------------------------------------------------------------------
def test_vertical_drop_over_every_strip_column_is_one_volt():
    """Each strip column telescopes to ``-1 V`` (to roundoff); an off-strip one does not.

    The strip is held at ``1 V`` and the ground at ``0 V``, so
    ``sum_k e_z[i, k] = -(phi[i, n_sub] - phi[i, 0]) = -1 V`` for every node
    ``i`` of the strip.  This is the only place the absolute scale of the
    profile is checked, and it is *algebraic*: the measured spread over the
    ``n_strip + 1 = 5`` columns is roundoff, not a mesh effect.
    """
    p = _coarse()
    drops = -p.e_z[p.strip_nodes, : p.n_sub].sum(axis=1)
    assert drops.shape == (p.n_strip + 1,), (
        f"expected {p.n_strip + 1} strip columns, got {drops.shape}"
    )
    assert np.allclose(drops, p.v_mode, rtol=0.0, atol=1e-12), (
        f"strip-column drops {drops!r} V should all be v_mode = {p.v_mode!r} V "
        f"(spread {np.ptp(drops):.3e} V over {drops.size} columns); n_sub="
        f"{p.n_sub}, cell={p.cell:.4g} m"
    )

    off = 1                                       # one node inside the clean wall
    off_drop = -p.e_z[off, : p.n_sub].sum()
    # Fringing potential, not a defect: one node into the wall the measured drop
    # is 1.630e-2 V, i.e. 1.63 % of the applied volt.  The band is per-cent
    # because the coarse section puts the strip edge one 0.4 mm cell from here.
    assert off_drop < 5.0e-2 * p.v_mode, (
        f"a column {off} node inside the clean wall drops {off_drop:.3e} V = "
        f"{100 * off_drop:.2f} % of the applied 1 V; the fringing potential must "
        "stay a small fraction of it (pinned 1.63 %)"
    )


@pytest.mark.slow
def test_placed_profile_keeps_its_normalisation():
    """Placement is an integer index shift, so the 1 V drop survives the copy.

    The clip is lateral-only on the converged box, so the strip columns are
    untouched and the plane's own z-edges still telescope -- which is what makes
    a plane_window copy directly usable as a port mode.
    """
    p = _converged()
    w = p.plane_window()
    plane_ez = np.zeros((201, 76))
    (src, dst) = w.ynode_zcell
    plane_ez[dst] = p.e_z[src]

    col = 100                                     # default plane centre
    drop = -plane_ez[col, : p.n_sub].sum()
    assert abs(drop - p.v_mode) <= 1e-12, (
        f"placed profile drops {drop!r} V at plane node {col}, expected "
        f"v_mode = {p.v_mode!r} V "
        f"(shifts iy {w.iy_shift}, k {w.k_shift})"
    )


# ---------------------------------------------------------------------------
# 3. the sign and the direction of the gap field
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_normalisation_domain_is_the_projection_window():
    """Unit power is measured on the clipped plane, not on the wide box.

    The guard is the discrete Poynting sum over the very slices
    :meth:`ModeProfile.plane_window` copies: it is 1 W to roundoff, that being
    the domain the port mode is ever measured on.  The whole box carries
    1.01178580 W at the same scale, i.e. 1.164852 % more (a cross-section
    figure -- the solve has no station index), so a re-normalisation over the
    wide box would put the window 1.165 % (0.584 % in amplitude) low and fail
    *there*, on ``the plane_window slices carry ...``.  This is what pins the
    *domain* of the normalisation.
    """
    # Consistency check, not a domain guard: ``i_mode`` is *defined* as
    # ``_POWER_W / (0.5 * v_mode)``, so this identity holds by construction
    # under any normalisation, including one taken over the wide box.
    p = _converged()
    assert abs(0.5 * p.v_mode * p.i_mode - 1.0) <= 1e-12, (
        f"0.5 v_mode i_mode = {0.5 * p.v_mode * p.i_mode!r} W, expected 1 W "
        f"(v_mode {p.v_mode!r} V, i_mode {p.i_mode!r} A)"
    )

    w = p.plane_window()
    (sy, sz) = w.ycell_znode[0]
    (sny, snz) = w.ynode_zcell[0]
    p_win = 0.5 * (np.sum(p.e_y[sy, sz] ** 2) + np.sum(p.e_z[sny, snz] ** 2))
    p_win /= p.eta_eff
    assert abs(p_win - 1.0) <= 1e-12, (
        f"the plane_window slices carry {p_win!r} W, expected 1 W: the "
        f"normalisation domain is not the projection domain ({w.report()})"
    )

    p_box = 0.5 * (np.sum(p.e_y ** 2) + np.sum(p.e_z ** 2)) / p.eta_eff
    assert abs(p_box - p.power_full_box) <= 1e-12 * p.power_full_box, (
        f"recomputed whole-box power {p_box!r} W != power_full_box "
        f"{p.power_full_box!r} W (same integral, so roundoff only)"
    )
    assert p_box > 1.0, (
        f"the whole box carries {p_box!r} W <= 1 W: unit power cannot have been "
        "normalised on the clipped window"
    )
    assert abs(p_box - 1.01178580) < 1e-8, (
        f"power_full_box = {p_box!r} W, pinned at 1.01178580 W = 1 / (1 - "
        "0.01164852), i.e. the 1.164852 % the clip removed at this "
        "cross-section (station-independence is inferred, not measured: "
        "a 2-D eigen-solve has no station index)"
    )


def test_gap_field_points_up_everywhere_under_the_strip():
    """``e_z < 0`` for every gap cell under the strip: ``E`` runs strip to ground.

    A sign or an index flip in the edge split would leave the telescoping sum
    intact while reversing the field, so this is a separate claim.  It is
    asserted over the whole strip footprint, not on the average, and the
    message quotes the most positive cell.
    """
    p = _coarse()
    gap = p.e_z[p.strip_nodes, : p.n_sub]
    worst = gap.max()
    assert worst < 0.0, (
        f"gap e_z has a non-negative entry {worst!r} V (mean "
        f"{gap.mean():.6g} V over {gap.size} cells, n_sub={p.n_sub}); "
        "the field must point from the 1 V strip down to the 0 V ground"
    )
    # 4 coarse cells in the gap, uniform enough that no cell may carry less than
    # a quarter of the 1 V total: |e_z| > 0.25 / 4 V = 0.0625 V.
    assert worst < -0.25 * p.v_mode / p.n_sub, (
        f"the weakest gap cell carries only {worst!r} V; with {p.n_sub} cells "
        f"sharing v_mode = {p.v_mode!r} V no cell should be below "
        f"-{0.25 * p.v_mode / p.n_sub:.4g} V"
    )


def test_field_under_the_strip_is_predominantly_vertical():
    """``|e_y| < |e_z|`` in the gap under the strip.

    On the coarse section (4 cells across a 1.6 mm gap, ``eps_r = 4.4``) the
    measured worst case is ``|e_y| = 0.17037 V`` against ``|e_z| = 0.25923 V``,
    ratio 0.657 -- comfortably below the 0.8 asserted here.  A finer gap pushes
    the ratio down; it does not need a tight band to make the point that the
    quasi-TEM mode is vertical, so the band is left loose on purpose.
    """
    p = _coarse()
    rows = p.strip_nodes
    ey = np.abs(p.e_y[rows.start : rows.stop, 1 : p.n_sub]).max()
    ez = np.abs(p.e_z[rows, 1 : p.n_sub - 1]).max()
    assert ey < 0.8 * ez, (
        f"|e_y| under the strip = {ey:.6g} V is not small against "
        f"|e_z| = {ez:.6g} V (ratio {ey / ez:.4f}, allowed 0.8); "
        f"cell {p.cell:.4g} m, n_sub {p.n_sub}, eps_r {p.eps_r}"
    )


# ---------------------------------------------------------------------------
# 4. the companion magnetic field
# ---------------------------------------------------------------------------
def test_h_is_the_plane_wave_companion_of_e():
    """``h_z = e_y / eta_eff`` and ``h_y = -e_z / eta_eff``, bit for bit.

    ``eta_eff`` comes from the same solve as ``eps_eff``, so this is a division
    and nothing else -- it is checked because the *signs* are the physics (a
    ``+x``-travelling wave has ``x_hat x e``), and a copied array with the wrong
    sign would still look plausible.
    """
    p = _coarse()
    assert np.array_equal(p.h_z, p.e_y / p.eta_eff), (
        f"h_z != e_y / eta_eff with eta_eff = {p.eta_eff:.12g} ohm; "
        f"max gap {np.abs(p.h_z - p.e_y / p.eta_eff).max():.3e} A"
    )
    assert np.array_equal(p.h_y, -p.e_z / p.eta_eff), (
        f"h_y != -e_z / eta_eff with eta_eff = {p.eta_eff:.12g} ohm; "
        f"max gap {np.abs(p.h_y + p.e_z / p.eta_eff).max():.3e} A"
    )


# ---------------------------------------------------------------------------
# 5. placement in an FDTD plane -- the clipping branch
# ---------------------------------------------------------------------------
def test_plane_window_clips_the_converged_box_into_the_fdtd_plane():
    """The 43.0 x 21.6 mm box in a 20.0 x 7.6 mm plane: clipped, and reported.

    This is the production case.  The strip node row and centre still land on
    the plane's own (``k = 16``, ``iy = 100``), the destination slices fill the
    plane exactly, and the 115 y-cells per side plus the 140 z-cells of air that
    do **not** fit are carried in :attr:`PlaneWindow.clipped` instead of being
    dropped silently.  The energy kept is 98.208 % of the profile's ``sum e_y^2``
    -- the remaining 1.8 % is mode the plane cannot see.
    """
    p = _converged()
    w = p.plane_window()

    assert isinstance(w, PlaneWindow)
    assert w.full_coverage is False, (
        f"a {p.node_shape} profile cannot be fully covered by a 201 x 77 node "
        "plane; plane_window reported no clipping"
    )
    assert (w.iy_shift, w.k_shift) == (100 - p.iy_strip_centre, 16 - p.n_sub), (
        f"shifts ({w.iy_shift}, {w.k_shift}) should be "
        f"({100 - p.iy_strip_centre}, {16 - p.n_sub}) for the production plane"
    )

    # the four clip records, in the order the fits are made
    assert w.clipped == (
        ("e_y/h_z, y", 115, 115),
        ("e_y/h_z, z", 0, 140),
        ("e_z/h_y, y", 115, 115),
        ("e_z/h_y, z", 0, 140),
    ), f"unexpected clip records {w.clipped!r}; report() says {w.report()!r}"
    assert w.dropped == 740, (
        f"dropped {w.dropped} source entries, expected 740 "
        f"(2*115 + 140 for each lattice class, minus the nodes' extra row)"
    )
    assert "115 below" in w.report() and "140 beyond" in w.report(), (
        f"report() = {w.report()!r} does not name both clips"
    )

    # the copy fills the plane and keeps 98.208 % of the y-edge energy
    plane_ey = np.zeros((200, 77))
    (src, dst) = w.ycell_znode
    plane_ey[dst] = p.e_y[src]
    assert plane_ey.shape == (200, 77)
    keep = (plane_ey ** 2).sum() / (p.e_y ** 2).sum()
    assert 0.982 < keep < 0.983, (
        f"the plane keeps {100 * keep:.3f} % of sum(e_y^2), pinned at 98.208 %; "
        f"clipped {w.report()}"
    )


def test_plane_window_places_a_smaller_profile_without_clipping():
    """A profile that fits is placed by pure integer offset, nothing dropped.

    The coarse section (45 x 25 nodes, ``cell = 0.4 mm``) is put in the default
    201 x 77 node plane with no ``cell`` argument: ``plane_window`` is a lattice
    statement, so it does not need to know the cell size, and the shifts come out
    as ``iy = 78`` (strip centre 22 -> 100) and ``k = 12`` (ground row 4 -> 16).
    """
    p = _coarse()
    w = p.plane_window(201, 77, 16)

    assert w.full_coverage is True, (
        f"a {p.node_shape} profile fits a 201 x 77 plane; clipped {w.report()}"
    )
    assert w.clipped == () and w.dropped == 0
    assert w.report() == "nothing clipped"

    assert (w.iy_shift, w.k_shift) == (78, 12), (
        f"shifts ({w.iy_shift}, {w.k_shift}) should be (78, 12): strip centre "
        f"{p.iy_strip_centre} -> 100, ground row {p.n_sub} -> 16"
    )
    (src, dst) = w.ycell_znode
    assert (src[0].start, src[0].stop) == (0, 44), (
        f"e_y source slice {src[0]!r} should cover all 44 y-edges"
    )
    assert (dst[0].start, dst[0].stop) == (78, 122), (
        f"e_y destination slice {dst[0]!r} should be 78:122"
    )
    assert src[0].stop - src[0].start == dst[0].stop - dst[0].start
    assert src[1].stop - src[1].start == dst[1].stop - dst[1].start


def test_plane_window_rejects_a_different_cell_size():
    """Only the profile's own cell size is allowed: the shift is in *indices*.

    On a different cell size the same integer offset would land the strip
    somewhere else in metres, so the placement must be refused rather than
    silently mis-scaled.
    """
    p = _coarse()
    with pytest.raises(ValueError, match="not the profile's cell"):
        p.plane_window(cell=2.0 * p.cell)


def test_plane_window_rejects_a_ground_plane_below_the_target_plane():
    """``k_strip < n_sub`` puts the ground row outside the plane: refused.

    The profile's substrate is ``n_sub`` cells thick, so a strip row above it
    would push ``k = 0`` (the ground plane) to a negative index.
    """
    p = _coarse()
    with pytest.raises(ValueError, match="above the profile's own substrate"):
        p.plane_window(k_strip=N_SUB_COARSE - 1)


def test_plane_window_rejects_a_placement_with_no_overlap():
    """Clip, yes; disjoint, no.  A shift that misses the plane entirely raises."""
    p = _coarse()
    with pytest.raises(ValueError, match="misses the plane entirely"):
        p.plane_window(201, 77, 16, iy_strip_centre=-(p.iy_strip_centre) - 1000)
