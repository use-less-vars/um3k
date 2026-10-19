"""Tests for :mod:`emfit.quasistatic`, the 2-D Laplace cross-section solver.

Three deliberately separate layers, so that a failure says which kind of claim
broke:

1. *Exact closed forms.*  A parallel plate and a two-layer series capacitor are
   one-dimensional problems: the potential varies along the stack only, so the
   transverse walls and the mesh never enter the answer and ``C'`` must equal
   ``eps0 eps_r W / H`` (resp. ``eps0 W / (t1/eps1 + t2/eps2)``) to roundoff.
   These run at ``rtol = 1e-12`` -- four orders tighter than the field problem
   itself deserves -- because nothing is being approximated.

2. *Convergence and regression pins for the microstrip section*  (``h = 1.6 mm``,
   ``W = 3.2 mm``, ``eps_r = 4.4``, ``3h`` of clean space laterally and above,
   ``4`` substrate cells at the coarsest level).  The permittivity is a plain
   callable handed to :func:`capacitance_per_length`, which hands it straight
   to :func:`emfit.materials.material_matrices`; the library's default
   ``interface="dual"`` rule then gives the tangential edges lying *in* the
   ``z = h`` interface the dual-face average ``2.7`` and never reads a value
   sampled exactly on that plane.  ``C'`` converges to the closed-form value
   from above; the two coarse levels are pinned at ``rtol = 1e-4`` as a
   regression.

3. *Structural claims about the box and about the interface.*  The vacuum
   capacitance is limited by the homogeneous-Neumann box -- a fixed bias, not a
   discretisation error -- so ``eps_eff`` and ``Z0`` inherit it; the interface
   plane is resolved exactly, in the sense that the value sampled *on* it is
   never used (two callables differing only there agree bit for bit, which the
   old edge-centre rule could not do); and ``C'`` does not depend on the width
   of the cell along the line axis, which is what proves the normalisation
   inside :func:`capacitance_per_length` is right.

The analytic oracle in layers 2 and 3 is :func:`emfit.microstrip.z0_eps_eff`,
the Hammerstad-Jensen fit, itself good only to a few per cent -- hence per-cent
bands there, while layer 1 needs no oracle at all.

Every pin below was measured on this code; the assertion messages carry the
numbers so a failure shows what moved without a re-run.
"""

from __future__ import annotations

from functools import lru_cache
from typing import NamedTuple

import numpy as np
import pytest

from emfit.grid import Grid
from emfit.materials import C0, EPS0, material_matrices
from emfit.microstrip import z0_eps_eff as analytic_z0_eps_eff
from emfit.operators import CellComplex
from emfit.quasistatic import (
    capacitance_per_length,
    node_index,
    node_shape,
    transverse_potential,
    z0_eps_eff,
)

# ---------------------------------------------------------------------------
# shared geometry
# ---------------------------------------------------------------------------
#: Cell size of the parallel-plate section [m]; ``W = 8 d`` and ``H = 4 d``.
D = 1.0e-3

#: Microstrip dimensions, matching the ``w/h = 2`` point of the analytic fit.
H_SUB = 1.6e-3          # substrate thickness [m]
W_STRIP = 3.2e-3        # strip width [m]  (w/h = 2)
EPS_SUB = 4.4           # substrate permittivity
N_SUB_CELLS = 4         # substrate cells across at the coarsest level
BOX_LATERAL = 3.0       # clean space each side of the strip, in h
BOX_TOP = 3.0           # clean space above the strip, in h


def _plate_grid(line_width: float = D) -> Grid:
    """8 x 4 cell section, one cell thick and periodic along x (the line axis).

    The line axis carries no potential variation in a 1-D field problem, so the
    section is infinitely long by construction and only the transverse plane
    matters.
    """
    return Grid.uniform(
        1, 8, 4, line_width, 8.0 * D, 4.0 * D, periodic=(True, False, False)
    )


def _plate_fixed(grid: Grid, top: float = 1.0, bottom: float = 0.0):
    """Hold the whole first and last transverse node row at two potentials."""
    n1, n2 = node_shape(grid)
    return [
        (top, [node_index(grid, i, n2 - 1) for i in range(n1)]),
        (bottom, [node_index(grid, i, 0) for i in range(n1)]),
    ]


# ---------------------------------------------------------------------------
# 1. exact one-dimensional closed forms
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("eps_r", [1.0, 2.2, 4.0])
def test_parallel_plate_matches_closed_form(eps_r):
    """``C' = eps0 eps_r W / H`` for a uniform field between two plates.

    The potential depends on ``z`` alone, so every transverse Neumann wall is
    exact rather than approximate and the only error left is roundoff in the
    sparse solve: ``rtol = 1e-12``.
    """
    grid = _plate_grid()
    fixed = _plate_fixed(grid)

    c = capacitance_per_length(grid, eps_r, fixed)
    ref = EPS0 * eps_r * (8.0 * D) / (4.0 * D)

    assert c == pytest.approx(ref, rel=1e-12), (
        f"parallel plate eps_r={eps_r}: C'={c!r} F/m, closed form {ref!r} F/m"
    )

    # The same solve also exposes the potential used for the energy: it must
    # satisfy both conductor rows and, the field being monotone, stay inside
    # the conductor potentials.
    phi = transverse_potential(grid, eps_r, fixed)
    assert phi.shape == node_shape(grid) == (9, 5)
    # Rows are the horizontal index, columns the vertical one: the two
    # conductor rows are the first and last *column*.
    assert np.allclose(phi[:, 0], 0.0) and np.allclose(phi[:, -1], 1.0)
    assert phi.min() >= 0.0 and phi.max() <= 1.0


def test_two_layer_series_capacitor_matches_closed_form():
    """``C' = eps0 W / (t1/eps1 + t2/eps2)`` for two layers in series.

    This one is a useful trap.  The tangential edges lying in the interface
    plane carry no flux in a parallel-plate field, so their permittivity cannot
    matter and the closed form holds for *any* value assigned there -- the
    library's dual rule hands them the mean ``2.5``, the old edge-centre rule
    handed them ``1.0``, and both are exact here.  The microstrip below is the
    case where it does matter, because there the field is **not** tangential to
    the interface.
    """
    grid = _plate_grid()
    fixed = _plate_fixed(grid)
    z_iface = 2.0 * D                     # interface on a node plane
    t = 2.0 * D                           # both layers two cells thick

    eps_r = lambda x, y, z: np.where(z < z_iface, 4.0, 1.0)  # noqa: E731

    c = capacitance_per_length(grid, eps_r, fixed)
    ref = EPS0 * (8.0 * D) / (t / 4.0 + t / 1.0)

    assert c == pytest.approx(ref, rel=1e-12), (
        f"two-layer series capacitor: C'={c!r} F/m, closed form {ref!r} F/m"
    )


# ---------------------------------------------------------------------------
# 2. the microstrip section: explicit interface array, measured convergence
# ---------------------------------------------------------------------------
class _Microstrip(NamedTuple):
    """Everything one refinement level of the microstrip section yields."""

    c_avg: float        # C' of the callable, resolved by the dual-face rule
    c_air: float        # C' with eps_r = 1.0 everywhere (the air reference)
    c_alt: float        # same callable written ``z <= h``: must be bit-identical
    z0: float           # quasi-TEM impedance [ohm]
    eps_eff: float      # C'/C'_air
    nodes: int          # transverse node count


def _microstrip_grid(level: int) -> tuple:
    """Section mesh at refinement ``level`` and its cell size."""
    cell = H_SUB / (N_SUB_CELLS * 2 ** level)
    ny = int(round((2.0 * BOX_LATERAL * H_SUB + W_STRIP) / cell))
    nz = int(round((H_SUB + BOX_TOP * H_SUB) / cell))
    grid = Grid.uniform(
        1, ny, nz, cell, ny * cell, nz * cell, periodic=(True, False, False)
    )
    return grid, cell


def _microstrip_fixed(grid: Grid, cell: float):
    """Ground plane on the bottom node row, zero-thickness strip at ``z = h``."""
    n1, _ = node_shape(grid)
    i0 = int(round(BOX_LATERAL * H_SUB / cell))
    i1 = i0 + int(round(W_STRIP / cell))
    j = int(round(H_SUB / cell))
    strip = [node_index(grid, i, j) for i in range(i0, i1 + 1)]
    ground = [node_index(grid, i, 0) for i in range(n1)]
    return [(1.0, strip), (0.0, ground)]


#: The substrate, written as the callers write it -- a bare callable.  Nothing
#: below builds an edge array: ``material_matrices`` resolves the interface.
_SUBSTRATE = lambda x, y, z: np.where(z < H_SUB, EPS_SUB, 1.0)   # noqa: E731
#: The same substrate, differing from ``_SUBSTRATE`` **only** on the plane
#: ``z = h`` itself.  The dual-face rule never reads that value, so this must
#: return exactly the same numbers -- see
#: ``test_interface_plane_node_value_is_never_sampled``.
_SUBSTRATE_LE = lambda x, y, z: np.where(z <= H_SUB, EPS_SUB, 1.0)  # noqa: E731


@lru_cache(maxsize=None)
def _microstrip(level: int) -> _Microstrip:
    """Solve one refinement level once and share it between the tests."""
    grid, cell = _microstrip_grid(level)
    fixed = _microstrip_fixed(grid, cell)
    c_avg = capacitance_per_length(grid, _SUBSTRATE, fixed)
    c_air = capacitance_per_length(grid, 1.0, fixed)
    c_alt = capacitance_per_length(grid, _SUBSTRATE_LE, fixed)
    z0, eps_eff = z0_eps_eff(grid, _SUBSTRATE, fixed)
    return _Microstrip(c_avg, c_air, c_alt, float(z0), float(eps_eff),
                       int(np.prod(node_shape(grid))))


def test_microstrip_capacitance_converges_upward_bounded():
    """``C'`` converges to the closed form monotonically from above.

    Measured, with the callable resolved by the library's dual-face interface
    rule, in pF/m::

        h/4   130.89447459510577   (561 nodes)
        h/8   127.17360354273877   (2145 nodes)
        h/16  125.36373600589517   (8385 nodes)
        fit   125.28711219305132

    These are the numbers the hand-built ``4.4 / 1.0 / 2.7`` edge array used to
    give, to the last bit that roundoff allows, which is why the pins did not
    move when the array was deleted.

    The error falls by roughly a factor three per refinement, and the ``6e-4``
    relative agreement at ``h/16`` is inside the Hammerstad-Jensen fit's own
    uncertainty -- so this is the one quantity the coarse mesh already gets
    right, unlike ``eps_eff`` and ``Z0``, which are dominated by the box (see
    the two tests below).
    """
    ref = np.sqrt(3.3439383100189377) / (C0 * 48.68576813308817)   # C' from the fit

    coarse, medium, fine = (_microstrip(level) for level in (0, 1, 2))

    assert fine.nodes == 8385 and medium.nodes == 2145 and coarse.nodes == 561

    # Pin the two coarse levels: a regression guard on the assembly, the
    # interface averaging and the strip geometry all at once.
    assert coarse.c_avg == pytest.approx(1.3089447459510577e-10, rel=1e-4), (
        f"microstrip C'(h/4)={coarse.c_avg!r} F/m, pinned 1.30894474595e-10"
    )
    assert medium.c_avg == pytest.approx(1.2717360354273877e-10, rel=1e-4), (
        f"microstrip C'(h/8)={medium.c_avg!r} F/m, pinned 1.27173603543e-10"
    )

    # Converged value against the independent (closed-form) oracle.
    assert fine.c_avg == pytest.approx(ref, rel=2e-3), (
        f"microstrip C'(h/16)={fine.c_avg!r} F/m, Hammerstad-Jensen {ref!r} F/m"
    )

    # Monotone, from above: a strip edge singularity resolves late, so every
    # refinement adds capacitance rather than oscillating around the limit.
    assert coarse.c_avg > medium.c_avg > fine.c_avg > ref, (
        f"C' not converging downward onto the fit: {coarse.c_avg!r} > "
        f"{medium.c_avg!r} > {fine.c_avg!r} > {ref!r}"
    )


def test_vacuum_capacitance_is_box_limited():
    """``C'_air`` is a Neumann-wall truncation, and a *fixed* one at that.

    Measured, in pF/m::

        h/4   36.58543201075163
        h/8   35.74963906553175
        h/16  35.33798468906550
        fit   37.46669...        (= 1 / (C0 Z0 sqrt(eps_eff)))

    The box scales with ``h`` rather than with the cell, so refining the mesh
    does not push the wall out and the deficit settles near 5.7 % instead of
    going to zero.  This test exists to stop a future reader attributing the
    ``eps_eff`` / ``Z0`` error in the next test to the discretisation: it is
    the box, and no amount of refinement will fix it.
    """
    z0_ref = 48.68576813308817
    ee_ref = 3.3439383100189377
    c_air_ref = 1.0 / (C0 * z0_ref * np.sqrt(ee_ref))

    coarse, medium, fine = (_microstrip(level) for level in (0, 1, 2))

    assert coarse.c_air > medium.c_air > fine.c_air, (
        f"C'_air not decreasing under refinement: {coarse.c_air!r}, "
        f"{medium.c_air!r}, {fine.c_air!r}"
    )

    deficit = 1.0 - fine.c_air / c_air_ref
    assert 0.05 < deficit < 0.07, (
        f"C'_air(h/16)={fine.c_air!r} F/m is {deficit:.2%} below the "
        f"closed form {c_air_ref!r} F/m; expected the box bias to stay "
        "between 5 % and 7 % rather than refine away"
    )


def test_interface_plane_node_value_is_never_sampled():
    """``z < h`` and ``z <= h`` give bit-identical ``C'``: only dual faces count.

    ``material_matrices`` resolves the callable with its default
    ``interface="dual"`` rule, so an edge lying *in* the ``z = h`` interface
    takes the dual-face mean of the two materials and the value sampled exactly
    *on* the plane is never read.  Two callables that differ only there
    therefore agree to the last bit at every refinement level.

    That is precisely what the old edge-centre rule could not do: the centre of
    a tangential interface edge sits exactly on the plane, so ``<`` and ``<=``
    silently selected different branches -- a bias in ``C'``, not a mesh error.
    Measured relative gaps of that rule, ``(C'_dual - C'_point) / C'_dual``::

        h/4    5.685 %
        h/8    3.490 %
        h/16   2.051 %

    It shrinks first order but does not vanish, because the misassigned edges
    stay on the interface however fine the mesh gets.  The rule is still
    selectable at the materials level, so the size of the error it made is
    pinned below as a regression -- and as the reason the default is ``dual``.
    """
    for level in (0, 1, 2):
        result = _microstrip(level)
        assert result.c_avg == result.c_alt, (
            f"C'(h/{4 * 2 ** level}) depends on the value sampled *on* the "
            f"interface plane: {result.c_avg!r} vs {result.c_alt!r} F/m"
        )

    # Reproduce the edge-centre rule: `capacitance_per_length` has no interface
    # argument (it must not, the rule is the library's), so the point-rule star
    # is asked for directly and divided by the vacuum star (eps_r = 1) to undo
    # the geometry and hand the solver the per-edge permittivity it expects.
    grid, cell = _microstrip_grid(0)
    cc = CellComplex(grid)
    m_point, _ = material_matrices(grid, cc, eps_r=_SUBSTRATE, interface="point")
    m_unit, _ = material_matrices(grid, cc, eps_r=1.0)
    c_point = capacitance_per_length(
        grid, np.asarray(m_point) / np.asarray(m_unit),
        _microstrip_fixed(grid, cell),
    )
    c_dual = _microstrip(0).c_avg
    gap = (c_dual - c_point) / c_dual
    assert gap == pytest.approx(0.05685062637519966, rel=1e-6), (
        f"the edge-centre rule's interface gap at h/4 is {gap:.5%}, "
        "pinned 5.685 % (measured when it was the default)"
    )


# ---------------------------------------------------------------------------
# 3. derived parameters and the normalisation
# ---------------------------------------------------------------------------
def test_z0_and_eps_eff_and_the_identity_between_them():
    """``Z0 sqrt(eps_eff) = 1/(C0 C'_air)`` and the size of the box bias.

    At ``h/8`` with the ``3h`` box::

        eps_eff  3.5573395107463908   vs 3.3439383100189377   (+6.4 %)
        Z0       49.47034938842009    vs 48.68576813308817    (+1.6 %)

    ``Z0`` moves little because the quasi-TEM relation makes it
    ``1/(C0 C'_air sqrt(eps_eff))`` and the two box errors very nearly cancel --
    but not quite, and the residual is why the band below is not symmetric
    with the ``eps_eff`` one.  Both are box artefacts established by
    ``test_vacuum_capacitance_is_box_limited``.
    """
    grid, cell = _microstrip_grid(1)                       # h / 8
    fixed = _microstrip_fixed(grid, cell)
    result = _microstrip(1)

    c_air = capacitance_per_length(grid, 1.0, fixed)

    assert result.eps_eff == pytest.approx(3.5573395107463908, rel=1e-3), (
        f"eps_eff at h/8 is {result.eps_eff!r}, pinned 3.55733951075"
    )
    assert result.z0 == pytest.approx(49.47034938842009, rel=1e-3), (
        f"Z0 at h/8 is {result.z0!r} ohm, pinned 49.47034938842"
    )

    # The identity the whole module is built on, at solver precision.
    lhs = result.z0 * np.sqrt(result.eps_eff)
    rhs = 1.0 / (C0 * c_air)
    assert lhs == pytest.approx(rhs, rel=1e-12), (
        f"Z0 sqrt(eps_eff)={lhs!r} != 1/(C0 C'_air)={rhs!r}"
    )

    # Both are biased high by the box, and eps_eff by substantially more.
    ee_err = result.eps_eff / 3.3439383100189377 - 1.0
    z0_err = result.z0 / 48.68576813308817 - 1.0
    assert 0.05 < ee_err < 0.08, f"eps_eff bias {ee_err:.2%}, expected 5-8 %"
    assert 0.005 < z0_err < 0.05, f"Z0 bias {z0_err:.2%}, expected 0.5-5 %"


def test_line_axis_width_cancels():
    """``C'`` is independent of the cell width along the line axis.

    The mass matrix is built from dual face areas, which carry that width, and
    ``capacitance_per_length`` normalises by the same width, so the two cancel
    exactly.  A wider line-axis cell therefore cannot silently rescale the
    answer -- this is the regression test for the ``length`` footgun.
    """
    narrow = _plate_grid(D)
    wide = _plate_grid(2.0 * D)

    c_narrow = capacitance_per_length(narrow, 4.0, _plate_fixed(narrow))
    c_wide = capacitance_per_length(wide, 4.0, _plate_fixed(wide))

    assert c_wide == pytest.approx(c_narrow, rel=1e-12), (
        f"line-axis width changed C': {c_narrow!r} F/m for a {D} m cell, "
        f"{c_wide!r} F/m for a {2.0 * D} m cell"
    )


# ---------------------------------------------------------------------------
# 4. rejected inputs
# ---------------------------------------------------------------------------
def test_rejects_malformed_grids_and_conductors():
    """Every degenerate input must raise ``ValueError``, not return nonsense."""
    grid = _plate_grid()
    fixed = _plate_fixed(grid)

    # Two periodic axes: the section geometry is ambiguous.
    two_periodic = Grid.uniform(1, 8, 4, D, 8 * D, 4 * D, periodic=(True, True, False))
    with pytest.raises(ValueError, match="exactly one axis must be periodic"):
        capacitance_per_length(two_periodic, 1.0, fixed)

    # Two cells thick along the line axis: several sections in series, and any
    # material variation across them would be silently discarded.
    thick = Grid.uniform(2, 8, 4, D, 8 * D, 4 * D, periodic=(True, False, False))
    with pytest.raises(ValueError, match="one cell thick"):
        capacitance_per_length(thick, 1.0, fixed)

    # Node indices outside the transverse node array.
    with pytest.raises(ValueError, match="outside"):
        node_index(grid, -1, 0)
    with pytest.raises(ValueError, match="outside"):
        node_index(grid, 9, 0)

    # One conductor, and two conductors at the same potential: the problem is
    # then pure Neumann and has no unique solution.
    with pytest.raises(ValueError, match="all conductor potentials are equal"):
        capacitance_per_length(grid, 1.0, [(1.0, [node_index(grid, 0, 4)])])
    with pytest.raises(ValueError, match="all conductor potentials are equal"):
        capacitance_per_length(grid, 1.0, [(1.0, [0, 1]), (1.0, [2, 3])])

    # A conductor with no nodes at all.
    with pytest.raises(ValueError, match="no nodes"):
        capacitance_per_length(grid, 1.0, [(1.0, []), (0.0, [0])])
