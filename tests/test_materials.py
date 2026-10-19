"""Tests for :mod:`emfit.materials` -- the diagonal Hodge stars.

Two of these tests are regression tests for bugs the module used to have:

1. a callable ``eps_r`` / ``mu_r`` / ``sigma`` must be sampled on the
   *seam-free* complex, i.e. with the duplicated node of a periodic axis
   dropped.  Before that fix every callable raised ``ValueError`` on any grid
   with a periodic axis, because the transverse coordinate arrays were one
   entry too long there;
2. where an edge lies *in* a material interface, the energy-consistent Hodge
   entry is the average over the dual face the edge is crossed by, not the
   value at the edge centre -- which sits exactly *on* the interface and
   silently picks one side.  ``interface="dual"`` reproduces, exactly, the
   array every caller used to build by hand.

Everything else here pins the metric: ``m_eps[e] = eps_r * EPS0 * A~_e / L_e``
and ``m_mu[f] = mu_r * MU0 * A_f / L~_f``, the block order (x edges, then y,
then z -- the column order of ``C``), and the thin object wrappers.
"""

import numpy as np
import pytest

from emfit.grid import Grid
from emfit.materials import (C0, EPS0, ETA0, MU0, M_eps, M_mu, M_sigma,
                            Material, MaterialMatrix, material_matrices)
from emfit.operators import CellComplex


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _blocks(grid: Grid, values: np.ndarray, *, faces: bool = False) -> dict:
    """Split a concatenated (x, y, z) entity array back into its 3-D blocks.

    ``faces`` selects the primal-face block shape (node layers along the normal,
    cells across) instead of the edge shape (cells along, node layers across);
    the two are transposes of one another and must not be mixed up.
    """
    out, off = {}, 0
    for axis in "xyz":
        shape = grid.face_shape(axis) if faces else grid.edge_shape(axis)
        n = int(np.prod(shape))
        out[axis] = np.asarray(values[off:off + n], dtype=float).reshape(shape)
        off += n
    return out


def _edge_points(grid: Grid, axis: str) -> tuple:
    """Coordinates of every edge along ``axis``.

    Cell centres along the edge's own axis, node values transversely with the
    periodic seam node dropped -- the documented sampling convention, written
    out here so the callable path can be checked against an explicit array.
    """
    coords = []
    for name in "xyz":
        a = np.asarray(getattr(grid, name), dtype=float)
        coords.append(0.5 * (a[:-1] + a[1:]) if name == axis
                      else a[:grid.nodes(name)])
    return np.meshgrid(*coords, indexing="ij")


def _edge_array(grid: Grid, cc: CellComplex, func) -> np.ndarray:
    """One value per primal edge for the callable ``func`` (explicit array)."""
    out = np.empty(cc.n_edges, dtype=float)
    for axis in "xyz":
        x, y, z = _edge_points(grid, axis)
        off = getattr(cc, "off_e" + axis)
        count = getattr(cc, "n_e" + axis)
        out[off:off + count] = np.asarray(func(x, y, z), dtype=float).ravel()
    return out


def _cube(nx=4, ny=4, nz=4, lx=4.0, ly=4.0, lz=4.0, periodic=(False, False, False)):
    """Bounded or periodic shoebox; unit cells when the extents match the counts."""
    return Grid.uniform(nx, ny, nz, lx, ly, lz, periodic=periodic)


# ---------------------------------------------------------------------------
# 1. the metric itself
# ---------------------------------------------------------------------------
def test_constants_are_consistent():
    """``C0``, ``MU0``, ``EPS0`` and ``ETA0`` must satisfy their defining relations."""
    assert C0 == 299792458.0
    assert ETA0 == MU0 * C0
    assert C0 == pytest.approx(1.0 / np.sqrt(EPS0 * MU0), rel=1e-6)


def test_uniform_grid_stars_match_the_closed_form():
    """``m_eps = eps0 dy~ dz~ / dx`` and ``m_mu = mu0 dy dz / dx~``, boundary included.

    The transverse directions are node axes, so their *dual* widths are a full
    cell inside the box and half a cell on the outer node layers: the metric
    really does vary across the block and ``m_eps`` must show it (a boundary
    x-edge sees a quarter of the interior area, a boundary x-face twice the
    interior ``1/L~``).
    """
    grid = _cube(4, 3, 2, 2.0, 3.0, 1.0)          # dx 0.5, dy 1.0, dz 0.5
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)

    dx, dy, dz = 0.5, 1.0, 0.5
    ex = _blocks(grid, m_eps)["x"]                # shape (nx, ny+1, nz+1)
    assert ex.shape == (4, 4, 3)
    # interior transverse node -> full dual widths
    assert ex[0, 1, 1] == pytest.approx(EPS0 * dy * dz / dx, rel=1e-15)
    # both transverse coordinates on the box wall -> a quarter of the area
    assert ex[0, 0, 0] == pytest.approx(EPS0 * (dy / 2) * (dz / 2) / dx, rel=1e-15)
    # edge length along the edge's own axis is the primary width, everywhere
    ey = _blocks(grid, m_eps)["y"]
    assert ey[1, 0, 1] == pytest.approx(EPS0 * dx * dz / dy, rel=1e-15)

    fx = _blocks(grid, m_mu, faces=True)["x"]     # shape (nx+1, ny, nz)
    assert fx.shape == (5, 3, 2)
    assert fx[1, 0, 0] == pytest.approx(MU0 * dy * dz / dx, rel=1e-15)
    assert fx[0, 0, 0] == pytest.approx(MU0 * dy * dz / (dx / 2), rel=1e-15)


def test_scalar_parameters_scale_the_vacuum_stars():
    """``eps_r`` and ``mu_r`` multiply their own star and nothing else."""
    grid = _cube(3, 3, 3, 3.0, 3.0, 3.0)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    m_eps2, m_mu3 = material_matrices(grid, cc, eps_r=2.0, mu_r=3.0)

    assert np.array_equal(m_eps2, 2.0 * m_eps)
    assert np.array_equal(m_mu3, 3.0 * m_mu)
    assert m_eps.size == cc.n_edges and m_mu.size == cc.n_faces


def test_array_parameter_is_one_value_per_entity_in_block_order():
    """An explicit array is indexed like ``C``: x block, then y, then z."""
    grid = _cube(3, 2, 2, 3.0, 2.0, 2.0)
    cc = CellComplex(grid)
    m_eps0, m_mu0 = material_matrices(grid, cc)

    eps = np.concatenate([np.full(cc.n_ex, 2.0), np.full(cc.n_ey, 3.0),
                          np.full(cc.n_ez, 4.0)])
    mu = np.concatenate([np.full(cc.n_fx, 5.0), np.full(cc.n_fy, 6.0),
                         np.full(cc.n_fz, 7.0)])
    m_eps, m_mu = material_matrices(grid, cc, eps_r=eps, mu_r=mu)

    for axis, factor in (("x", 2.0), ("y", 3.0), ("z", 4.0)):
        np.testing.assert_allclose(_blocks(grid, m_eps)[axis],
                                   factor * _blocks(grid, m_eps0)[axis],
                                   rtol=1e-15)
    for axis, factor in (("x", 5.0), ("y", 6.0), ("z", 7.0)):
        np.testing.assert_allclose(_blocks(grid, m_mu, faces=True)[axis],
                                   factor * _blocks(grid, m_mu0, faces=True)[axis],
                                   rtol=1e-15)


@pytest.mark.parametrize("name", ["eps_r", "mu_r"])
def test_parameter_of_the_wrong_length_is_refused(name):
    """A per-entity array that is one short must not be silently broadcast."""
    grid = _cube(2, 2, 2, 2.0, 2.0, 2.0)
    cc = CellComplex(grid)
    count = cc.n_edges if name == "eps_r" else cc.n_faces
    with pytest.raises(ValueError, match=f"{name}: expected a scalar"):
        material_matrices(grid, cc, **{name: np.ones(count - 1)})


# ---------------------------------------------------------------------------
# 2. regression: callables on a periodic axis (the seam node)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("periodic", [(True, False, False),
                                      (False, True, False),
                                      (False, False, True),
                                      (True, True, True)])
def test_callable_is_sampled_on_the_seam_free_complex(periodic):
    """A callable must work on a periodic axis and match the explicit array.

    The seam node (the first node over again) is not an entity of the complex,
    so an axis with ``n`` cells has ``n`` point layers there, not ``n + 1``.
    Sampling the full node array used to make every callable raise, on every
    family, as soon as one axis was periodic.
    """
    grid = _cube(2, 4, 3, 2.0, 4.0, 3.0, periodic=periodic)
    cc = CellComplex(grid)
    func = lambda x, y, z: 1.0 + 0.1 * x + 0.2 * y + 0.3 * z   # noqa: E731

    m_eps, m_mu = material_matrices(grid, cc, eps_r=func, mu_r=func,
                                    interface="point")
    np.testing.assert_allclose(m_eps,
                               material_matrices(grid, cc,
                                                 eps_r=_edge_array(grid, cc, func),
                                                 interface="point")[0],
                               rtol=1e-12)

    # the same check for faces: mu_r is sampled at face centres
    mu_ref, off = np.empty(cc.n_faces), 0
    for axis in "xyz":
        coords = []
        for name in "xyz":
            a = np.asarray(getattr(grid, name), dtype=float)
            coords.append(a[:grid.nodes(name)] if name == axis
                          else 0.5 * (a[:-1] + a[1:]))
        fx, fy, fz = np.meshgrid(*coords, indexing="ij")
        count = int(np.prod(grid.face_shape(axis)))
        off_f = getattr(cc, "off_f" + axis)
        mu_ref[off_f:off_f + count] = np.asarray(func(fx, fy, fz)).ravel()
    np.testing.assert_allclose(m_mu, material_matrices(grid, cc,
                                                       mu_r=mu_ref,
                                                       interface="point")[1],
                               rtol=1e-12)


def test_callable_matches_the_explicit_array_on_a_bounded_grid():
    """The seam-free slicing must not change a bounded grid in any way."""
    grid = _cube(4, 3, 5, 4.0, 3.0, 5.0)
    cc = CellComplex(grid)
    func = lambda x, y, z: 2.0 + 0.5 * z - 0.25 * y    # noqa: E731

    m_eps, _ = material_matrices(grid, cc, eps_r=func, interface="point")
    np.testing.assert_allclose(m_eps,
                               material_matrices(grid, cc,
                                                 eps_r=_edge_array(grid, cc, func),
                                                 interface="point")[0],
                               rtol=1e-15)

    # a per-family array that is exactly right, from the same convention
    explicit = _edge_array(grid, cc, func)
    m_eps2, _ = material_matrices(grid, cc, eps_r=explicit)
    np.testing.assert_allclose(m_eps, m_eps2, rtol=1e-15)


def test_callable_with_the_wrong_shape_raises():
    """A callable that ignores its arguments cannot fill the block."""
    grid = _cube(3, 3, 3, 3.0, 3.0, 3.0)
    cc = CellComplex(grid)
    with pytest.raises(ValueError, match="eps_r callable returned"):
        material_matrices(grid, cc, eps_r=lambda x, y, z: np.ones(3))


# ---------------------------------------------------------------------------
# 3. regression: the dual-face average in a material interface
# ---------------------------------------------------------------------------
def _layered_cube(z_iface=2.0, eps_below=4.0, eps_above=1.0):
    """Unit-cell cube whose permittivity steps at the node plane ``z_iface``."""
    grid = _cube(4, 4, 4, 4.0, 4.0, 4.0)
    cc = CellComplex(grid)
    eps_r = lambda x, y, z: np.where(z < z_iface, eps_below, eps_above)  # noqa: E731
    return grid, cc, eps_r


def test_default_interface_rule_is_the_dual_face_average():
    """Leaving ``interface`` out is ``interface="dual"``, exactly.

    The default is what every caller of :func:`material_matrices` gets, and it
    is the rule that fixes a node-aligned interface, so it is pinned here
    rather than left to a keyword default nobody reads.
    """
    grid, cc, eps_r = _layered_cube()
    default, _ = material_matrices(grid, cc, eps_r=eps_r)
    m_dual, _ = material_matrices(grid, cc, eps_r=eps_r, interface="dual")
    m_point, _ = material_matrices(grid, cc, eps_r=eps_r, interface="point")

    assert np.array_equal(default, m_dual), "the default is not the dual rule"
    assert not np.array_equal(default, m_point), (
        "the default agrees with point sampling across a node-aligned "
        "interface, so this grid cannot tell the two rules apart"
    )


def test_interface_point_sampling_picks_one_branch_and_dual_averages():
    """``interface="point"`` lands on the surface; ``"dual"`` takes the mean.

    The interface is on a node plane, so a transverse edge centre is exactly on
    the surface and the callable's ``<`` picks the upper branch.  The dual-face
    average of ``4`` and ``1`` is ``2.5``, and that is exactly the array the
    callers used to build by hand.
    """
    grid, cc, eps_r = _layered_cube()
    m_point, _ = material_matrices(grid, cc, eps_r=eps_r, interface="point")
    m_dual, _ = material_matrices(grid, cc, eps_r=eps_r, interface="dual")

    # tangential edges (EX, EY) sit at z nodes; the family normal to the
    # interface (EZ) sits at z cell centres and is unaffected
    for axis in ("x", "y"):
        ratio = _blocks(grid, m_dual)[axis] / _blocks(grid, m_point)[axis]
        on_iface = np.zeros(grid.edge_shape(axis), dtype=bool)
        on_iface[:, :, 2] = True                 # z node index 2 == z_iface
        assert np.all(ratio[on_iface] == pytest.approx(2.5, rel=1e-15))
        assert np.all(ratio[~on_iface] == pytest.approx(1.0, rel=1e-15))
    np.testing.assert_allclose(_blocks(grid, m_dual)["z"],
                               _blocks(grid, m_point)["z"], rtol=1e-15)

    # the hand-built array is checked in the next test


def test_dual_interface_array_reproduces_the_hand_built_array():
    """``interface="dual"`` is bit-for-bit the array callers wrote by hand."""
    grid, cc, eps_r = _layered_cube()
    m_dual, _ = material_matrices(grid, cc, eps_r=eps_r, interface="dual")

    hand = np.empty(cc.n_edges, dtype=float)
    for axis in "xyz":
        x, y, z = _edge_points(grid, axis)
        val = np.where(z < 2.0 - 1e-9, 4.0, 1.0)
        val = np.where(np.abs(z - 2.0) <= 1e-9, 2.5, val)
        off = getattr(cc, "off_e" + axis)
        count = getattr(cc, "n_e" + axis)
        hand[off:off + count] = val.ravel()
    m_hand, _ = material_matrices(grid, cc, eps_r=hand)

    assert np.array_equal(m_dual, m_hand), (
        "dual-face averaging does not reproduce the hand-built interface "
        f"array: max difference {np.max(np.abs(m_dual - m_hand)):.3e}"
    )


def test_dual_interface_average_is_width_weighted_on_a_non_uniform_grid():
    """Unequal cells on the two sides of the interface weight the mean by width.

    The dual face around an edge is cut by the node into half of each adjacent
    cell, so the value is ``(w_lo eps_lo + w_hi eps_hi) / (w_lo + w_hi)`` --
    the arithmetic mean only when the two cells are the same size.
    """
    z = np.array([0.0, 0.5, 1.5, 3.0])           # widths 0.5, 1.0, 1.5
    grid = Grid.nonuniform(np.linspace(0.0, 1.0, 5), np.linspace(0.0, 1.0, 5), z)
    cc = CellComplex(grid)
    eps_r = lambda x, y, z: np.where(z < 1.5, 4.0, 1.0)      # noqa: E731

    m_point, _ = material_matrices(grid, cc, eps_r=eps_r, interface="point")
    m_dual, _ = material_matrices(grid, cc, eps_r=eps_r, interface="dual")

    expected = (1.0 * 4.0 + 1.5 * 1.0) / (1.0 + 1.5)         # 2.2
    assert expected == pytest.approx(2.2)

    for axis in ("x", "y"):
        ratio = _blocks(grid, m_dual)[axis] / _blocks(grid, m_point)[axis]
        on_iface = np.zeros(grid.edge_shape(axis), dtype=bool)
        on_iface[..., 2] = True                              # z node 2 == 1.5
        assert np.all(ratio[on_iface] == pytest.approx(expected, rel=1e-14)), (
            f"{axis} edges on the interface average to {ratio[on_iface][0]!r}, "
            f"width weighted mean {expected!r}"
        )


def test_dual_sampling_midpoint_rule_is_exact_on_a_non_uniform_grid():
    """The sample point is the half-cell midpoint, not the neighbouring centre.

    ``z`` doubles in width across the node plane ``z = 1``, so the dual face of
    an ``EX`` edge spans ``[0.5, 2.0]`` and is cut at ``z = 1`` into parts of
    extent ``0.5`` and ``1.0``.  Weighting the two half-cell midpoints
    (``z = 0.75`` and ``z = 1.5``) by their extent reproduces the *integral*
    mean of ``eps = 1 + z`` over that dual face exactly, ``2.25``, against
    ``2.0`` for the point sample.  Sampling the neighbouring cell centres
    instead (``0.5`` and ``2.0`` -- the midpoint offset doubled, so a whole
    half-cell too far out) gives ``2.5``: the three rules are distinct.
    """
    grid = Grid.nonuniform(np.linspace(0.0, 1.0, 3), np.linspace(0.0, 1.0, 3),
                           np.array([0.0, 1.0, 3.0]))
    cc = CellComplex(grid)
    eps_r = lambda x, y, z: 1.0 + z                 # noqa: E731

    m_point, _ = material_matrices(grid, cc, eps_r=eps_r, interface="point")
    m_dual, _ = material_matrices(grid, cc, eps_r=eps_r, interface="dual")

    expected = (1.0 * (1.0 + 0.75) + 2.0 * (1.0 + 1.5)) / (1.0 + 2.0)
    assert expected == pytest.approx(2.25)

    ratio = _blocks(grid, m_dual)["x"] / _blocks(grid, m_point)["x"]
    on_iface = np.zeros(grid.edge_shape("x"), dtype=bool)
    on_iface[:, :, 1] = True                              # z node 1 == 1.0
    assert np.all(ratio[on_iface] == pytest.approx(expected / 2.0, rel=1e-14)), (
        f"EX edges on the interface average to {ratio[on_iface][0]!r} times "
        f"the point sample, expected {expected / 2.0!r} (2.25 / 2.0)"
    )


def test_dual_sampling_is_exact_for_a_linear_profile_on_a_uniform_grid():
    """The midpoint rule over the whole dual entity changes nothing to first order."""
    grid = _cube(4, 4, 4, 4.0, 4.0, 4.0)
    cc = CellComplex(grid)
    func = lambda x, y, z: 1.0 + 0.5 * z        # noqa: E731

    m_point, _ = material_matrices(grid, cc, eps_r=func, interface="point")
    m_dual, _ = material_matrices(grid, cc, eps_r=func, interface="dual")

    # Around an *interior* node the two half-cell midpoints straddle it
    # symmetrically, so a linear profile is reproduced exactly and ``"dual"``
    # is a no-op.  On the outer node layers only the interior half exists, so
    # the sample moves to that half's midpoint and the value shifts by half a
    # half-cell -- the documented price of resolving the interface at all.
    for axis in "xyz":
        inner = [slice(None)] * 3
        for t, name in enumerate("xyz"):
            if name != axis:
                inner[t] = slice(1, -1)
        np.testing.assert_allclose(
            _blocks(grid, m_dual)[axis][tuple(inner)],
            _blocks(grid, m_point)[axis][tuple(inner)],
            rtol=1e-15,
        )


def test_dual_sampling_averages_both_transverse_directions():
    """An edge in the corner of two interfaces sees all four quadrants.

    ``eps`` is a product of two step functions, so the area-weighted mean over
    the four quadrants of the dual face is the product of the two means:
    ``2.5 * 1.5 = 3.75`` for an ``EX`` edge on both node planes.  An ``EZ``
    edge is dual only in the two directions transverse to it, so it sees the
    ``y`` mean alone, ``(2 + 1) / 2 = 1.5``, and nothing from ``z`` -- ``z`` is
    its own axis and the dual entity does not reach across it.
    """
    grid = _cube(4, 4, 4, 4.0, 4.0, 4.0)
    cc = CellComplex(grid)
    eps_r = lambda x, y, z: (np.where(z < 2.0, 4.0, 1.0)      # noqa: E731
                             * np.where(y < 2.0, 2.0, 1.0))
    m_point, _ = material_matrices(grid, cc, eps_r=eps_r, interface="point")
    m_dual, _ = material_matrices(grid, cc, eps_r=eps_r, interface="dual")

    ex_ratio = _blocks(grid, m_dual)["x"] / _blocks(grid, m_point)["x"]
    corner = np.zeros(grid.edge_shape("x"), dtype=bool)
    corner[:, 2, 2] = True                                   # y node 2, z node 2
    assert np.all(ex_ratio[corner] == pytest.approx(3.75, rel=1e-14))

    ez_ratio = _blocks(grid, m_dual)["z"] / _blocks(grid, m_point)["z"]
    on_y = np.zeros(grid.edge_shape("z"), dtype=bool)
    on_y[..., 2, :] = True                                   # y node 2
    assert np.all(ez_ratio[on_y] == pytest.approx(1.5, rel=1e-14))


def test_dual_sampling_works_across_a_periodic_axis():
    """A periodic axis has no outer nodes, so both halves of every dual face exist."""
    grid = _cube(2, 4, 4, 2.0, 4.0, 4.0, periodic=(True, False, False))
    cc = CellComplex(grid)
    eps_r = lambda x, y, z: np.where(z < 2.0, 4.0, 1.0)      # noqa: E731

    m_point, _ = material_matrices(grid, cc, eps_r=eps_r, interface="point")
    m_dual, _ = material_matrices(grid, cc, eps_r=eps_r, interface="dual")
    ratio = _blocks(grid, m_dual)["x"] / _blocks(grid, m_point)["x"]
    on_iface = np.zeros(grid.edge_shape("x"), dtype=bool)
    on_iface[:, :, 2] = True
    assert np.all(ratio[on_iface] == pytest.approx(2.5, rel=1e-15))


@pytest.mark.parametrize("call", [
    lambda grid, cc: material_matrices(grid, cc, eps_r=1.0, interface="mean"),
    lambda grid, cc: M_eps(grid, cc, interface="mean"),
    lambda grid, cc: M_mu(grid, cc, interface="mean"),
    lambda grid, cc: M_sigma(grid, cc, sigma=1.0, interface="mean"),
])
def test_unknown_interface_rule_is_refused(call):
    """A typo must not fall back to point sampling."""
    grid = _cube(2, 2, 2, 2.0, 2.0, 2.0)
    with pytest.raises(ValueError, match="interface must be 'point' or 'dual'"):
        call(grid, CellComplex(grid))


# ---------------------------------------------------------------------------
# 4. conductivity and the object wrappers
# ---------------------------------------------------------------------------
def test_sigma_star_is_a_conductance():
    """``m_sigma[e] = sigma A~_e / L_e`` [S], and ``sigma = 0`` is the identity."""
    grid = _cube(4, 3, 2, 2.0, 3.0, 1.0)
    cc = CellComplex(grid)
    assert np.all(M_sigma(grid, cc).diag == 0.0)

    m = M_sigma(grid, cc, sigma=2.0)
    sx = _blocks(grid, m.diag)["x"]
    assert sx[0, 1, 1] == pytest.approx(2.0 * 1.0 * 0.5 / 0.5, rel=1e-15)
    assert sx[0, 0, 0] == pytest.approx(2.0 * 0.5 * 0.25 / 0.5, rel=1e-15)


def test_sigma_callable_handles_a_periodic_axis_and_interfaces():
    """``sigma`` follows the same sampling rules as ``eps_r``."""
    grid, cc, _ = _layered_cube()
    sigma = lambda x, y, z: np.where(z < 2.0, 0.5, 0.1)      # noqa: E731
    m_point = M_sigma(grid, cc, sigma=sigma, interface="point")
    m_dual = M_sigma(grid, cc, sigma=sigma, interface="dual")

    ratio = _blocks(grid, m_dual.diag)["x"] / _blocks(grid, m_point.diag)["x"]
    on_iface = np.zeros(grid.edge_shape("x"), dtype=bool)
    on_iface[:, :, 2] = True
    # the centre is on the plane and picks the upper branch (0.1); the dual
    # face averages the two sides (0.5 + 0.1) / 2 = 0.3
    assert np.all(ratio[on_iface] == pytest.approx(3.0, rel=1e-15))

    periodic = _cube(2, 3, 3, 2.0, 3.0, 3.0, periodic=(True, False, False))
    assert M_sigma(periodic, CellComplex(periodic),
                   sigma=lambda x, y, z: 1.0 + 0.0 * z).diag.size == \
        CellComplex(periodic).n_edges


def test_material_matrix_wrappers_agree_with_the_arrays():
    """``M_eps`` / ``M_mu`` are the canonical arrays in a thin object."""
    grid = _cube(3, 3, 3, 3.0, 3.0, 3.0)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc, eps_r=2.0, mu_r=4.0)

    eps, mu = M_eps(grid, cc, eps_r=2.0), M_mu(grid, cc, mu_r=4.0)
    assert np.array_equal(eps.diag, m_eps) and np.array_equal(mu.diag, m_mu)
    assert eps.shape == (cc.n_edges, cc.n_edges) and len(eps) == cc.n_edges

    x = np.arange(cc.n_edges, dtype=float)
    assert np.array_equal(eps.apply(x), m_eps * x)
    assert np.array_equal(eps @ x, m_eps * x)
    assert np.allclose(eps.solve(eps.apply(x)), x, rtol=1e-15)
    assert np.array_equal(eps.inv_diag, 1.0 / m_eps)


def test_material_uniform_helper_is_a_plain_container():
    """``Material`` holds scalars and validates nothing (documented as such)."""
    m = Material.uniform(eps_r=2.0, mu_r=3.0, sigma=0.5)
    assert (m.eps_r, m.mu_r, m.sigma) == (2.0, 3.0, 0.5)
    grid = _cube(2, 2, 2, 2.0, 2.0, 2.0)
    assert m.check(grid) is m
    assert "eps_r=2.0" in repr(m)
