"""Transverse mode profile of a quasi-static microstrip cross-section.

:mod:`emfit.quasistatic` answers *how much* -- ``C'``, ``Z0``, ``eps_eff`` --
from a scalar potential solve on the transverse plane.  This module keeps the
*field* that solve produced and hands it over in the layout a time-domain run
actually needs:

* ``e_y`` / ``e_z``, the transverse electric field on the **staggered edges** of
  the same Yee/FIT lattice the solver is built on (:mod:`emfit.operators`), so
  no interpolation is involved;
* ``h_y`` / ``h_z``, the companion magnetic field of the corresponding
  forward-travelling wave, from the local plane-wave relation;
* the integer offsets that say where the profile's ground plane and strip
  centre sit inside an FDTD transverse plane of a different size.

Normalisation
-------------
The returned field carries exactly ``1 W`` of modal power through the
**projection window** -- the clipped ``201 x 77`` node plane that
:meth:`ModeProfile.plane_window` copies into an FDTD grid -- because that is the
domain the excitation is ever measured against::

    0.5 / eta_eff * (sum e_y^2 + sum e_z^2) = 1 W     on those slices only.

``e^2`` is ``|E|^2 cell^2 = |E_t|^2 dA`` and ``e / eta_eff`` is ``H . dl``, so
that sum *is* the Poynting flux and the normalisation integral *is* the
projection integral.  It has to be: ``0.5 Re(V conj(I)) = P`` holds identically
for any excitation coefficient, so if the normalisation domain and the
projection domain differ, the difference enters as a pure scale bias on the
projected mode.  Normalising on the window makes the reported ``v_mode`` /
``i_mode`` the voltage and current a unit-power projection actually sees, which
is stronger than normalising over some box and rescaling afterwards.

Internally the potential solve still holds the strip at exactly ``1 V`` and the
ground plane at ``0 V`` -- that is what makes ``C'`` a capacitance and the
algebraic checks exact -- and only the last step rescales the whole field by
one scalar ``sqrt(1 W / P_window)``.  The edge field is ``e = -G phi``, i.e.
``E . dl`` in **volts per edge**, not ``V/m``; the edge lengths are already
folded in, which is what an FDTD field update wants and what makes the energy
identity below dimensionally clean.  Dividing by ``cell`` recovers ``E`` in
``V/m``.

A single positive scalar leaves the normalisation *checkable* rather than
assumed: the vertical z-edges of one strip column still telescope,

    sum_{k < n_sub} e_z[i, k] = -(phi[i, n_sub] - phi[i, 0]) = -v_mode,

exactly (to roundoff), where ``v_mode`` is the voltage that unit power implies
on this geometry.  That is asserted in :func:`microstrip_mode_profile` and
again, column by column, in the test suite.

Staggering -- which array lives where
-------------------------------------
At a fixed x-plane (one line-axis cell) the FIT lattice puts all four
transverse components:

    array   edges/faces          lattice position      shape
    e_y     EY  (edge)           y-cell  x z-node      (ny,   N2)
    h_z     FZ  (dual face)      y-cell  x z-node      (ny,   N2)
    e_z     EZ  (edge)           y-node  x z-cell      (N1,   nz)
    h_y     FY  (dual face)      y-node  x z-cell      (N1,   nz)

with ``N1 = ny + 1``, ``N2 = nz + 1`` the node counts and ``ny``, ``nz`` the
cell counts.  ``FY`` is *dual* to the ``EZ`` edge it sits on and ``FZ`` to
``EY``, so ``h_y`` is collocated with ``e_z`` and ``h_z`` with ``e_y``: the
four arrays of one x-plane are directly addable, no half-cell shift in ``x``
and no averaging.  The geometry is: ground plane on the ``k = 0`` node row,
strip on the ``k = n_sub`` node row (node plane, so the substrate interface
``z = h`` is resolved exactly -- see the :mod:`emfit.quasistatic` docstring),
Neumann walls on the outer box.

Companion magnetic field
------------------------
For a wave travelling along the line axis ``+x`` (the brief's "z" is the
*propagation* direction; here it is ``x`` because the cross-section solver
calls the other two axes ``y`` and ``z``), the local plane-wave relation is

    h = (1 / eta_eff) x_hat x e,     eta_eff = sqrt(MU0 / (EPS0 eps_eff)),

i.e. ``h_z = +e_y / eta_eff`` and ``h_y = -e_z / eta_eff``.  ``eta_eff`` is
built from the profile's *own* ``eps_eff``, so ``|e| / |h| = eta_eff`` holds
edge by edge, which is exactly what a single-mode excitation assumes and what
a wrong normalisation would break.

Units: ``e`` is volts, ``eta`` is ohms, so ``h`` comes out in **amperes** --
``H . dl`` over a dual edge, whose length equals the primal one on this
uniform grid (the profile is a uniform mesh by construction).

Limitations
-----------
* The profile is **static**.  It carries no dispersion, no radiation and no
  longitudinal field: the longitudinal components ``e_x``, ``h_x`` that a real
  guided mode has are not represented, because a 2-D Laplace solve has no
  eigenvalue to produce them.  That is the standard quasi-TEM excitation
  assumption -- good while the cross-section is small against a wavelength.
* Conductor thickness and finite conductivity are not modelled (a conductor is
  a set of nodes), exactly as in :mod:`emfit.quasistatic`.
* The box is truncated with homogeneous Neumann walls, so ``C'``, ``eps_eff``
  and ``Z0`` are all box-limited -- lateral wall placement, not mesh
  refinement, is what moves them (see the measured plateau in
  :func:`microstrip_mode_profile`).  The converged box is far wider than an
  FDTD plane, and what falls outside that plane is the modal power the PML
  absorbs: 0.57 % beyond ``|y| = 10 mm``, 0.78 % above ``z = 7.6 mm`` and
  1.16 % in total (measured on the converged profile, corner counted once).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .grid import Grid
from .materials import C0, EPS0, MU0
from .quasistatic import (
    _solve,
    _transverse_metric,
    capacitance_per_length,
    node_index,
    node_shape,
    z0_eps_eff,
)

__all__ = [
    "ModeProfile",
    "PlaneWindow",
    "SelfConsistencyError",
    "microstrip_mode_profile",
]


#: Substrate cells at the production cell size: ``h = 1.6 mm`` with
#: ``cell = 0.1 mm``, which is the FDTD board's own transverse cell.
_DEFAULT_N_SUB = 16
#: Clean dielectric/air cells each side of the strip: 20 mm of lateral wall,
#: i.e. far outside the FDTD plane's 8.5 mm.  Measured plateau
#: (``.scratch/mp_study.py``): the last 5 mm of wall still moves ``eps_eff`` by
#: 0.33 %, and the walls bind harder than the air ceiling.
_DEFAULT_N_CLEAN = 200
#: Air cells above the strip: 20 mm.  Measured plateau: the last 8 mm of air
#: still moves ``eps_eff`` by 0.19 % (14.85e-3 %/mm residual drift), i.e. the
#: curve has flattened but has not yet gone vertical; 200 cells is the widest
#: box that still solves in a few seconds.
_DEFAULT_N_AIR = 200

#: Transverse plane of the production FDTD board: ``ny = 200``, ``nz = 76``
#: cells of ``0.1 mm``, i.e. 201 x 77 nodes, strip on node row ``k = 16``
#: (= ``h``).
_FDTD_NYN = 201
_FDTD_NZN = 77
_FDTD_K_STRIP = 16
_FDTD_CELL = 1.0e-4

#: Roundoff-level tolerance for the identities asserted below.  They are
#: algebraic, not discretisation errors, so this is as tight as a double
#: allows and says nothing about how accurate the *physics* is.
_RTOL = 1.0e-12

#: Modal power the returned field is normalised to, in watts, integrated over the
#: **projection window** (the clipped ``_FDTD_NYN x _FDTD_NZN`` plane) -- see
#: :func:`microstrip_mode_profile`.
_POWER_W = 1.0


class SelfConsistencyError(RuntimeError):
    """The edge field and the line parameters disagree.

    Raised by :func:`microstrip_mode_profile` when ``check=True`` and one of
    the algebraic identities that tie the returned profile to
    :func:`emfit.quasistatic.capacitance_per_length` /
    :func:`emfit.quasistatic.z0_eps_eff` fails.  Any mismatch means the field
    and the numbers were not produced by the same solve -- a convention or an
    indexing bug, never a convergence issue -- so the profile must not be used.
    """


@dataclass(frozen=True)
class PlaneWindow:
    """Where a :class:`ModeProfile` sits in a *different* transverse plane.

    Attributes
    ----------
    iy_shift, k_shift:
        Integer index offsets: ``fdtd_index = profile_index + shift``.  They
        apply to nodes *and* cells alike, because an integer translation
        preserves the Yee stagger.  ``k_shift`` is the FDTD node row carrying
        the profile's ground plane (``k = 0`` in profile coordinates).
    ycell_znode:
        ``(source, destination)`` slice pairs for the arrays living on
        y-cells x z-nodes: ``e_y`` and ``h_z``.  Source slices index the
        profile array, destination slices the FDTD plane.
    ynode_zcell:
        The same for y-nodes x z-cells: ``e_z`` and ``h_y``.
    clipped:
        ``(label, low, high)`` per lattice class that lost source entries:
        ``low`` entries fell below the target plane (negative shift), ``high``
        entries past its far end.  Empty when the plane swallows the whole
        profile.  The slices are already shortened, so the caller never has to
        look at this -- it is the audit trail that says *which* part of the
        mode the plane does not see.
    """

    iy_shift: int
    k_shift: int
    ycell_znode: tuple
    ynode_zcell: tuple
    clipped: tuple = ()

    @property
    def full_coverage(self) -> bool:
        """True when every source entry landed inside the target plane."""
        return not self.clipped

    @property
    def dropped(self) -> int:
        """Total source entries outside the target plane (all classes)."""
        return sum(low + high for _, low, high in self.clipped)

    def report(self) -> str:
        """One line per clipped lattice class, ``"nothing clipped"`` if none."""
        if not self.clipped:
            return "nothing clipped"
        return "; ".join(
            f"{label}: {low} below, {high} beyond" for label, low, high in self.clipped
        )


@dataclass(frozen=True)
class ModeProfile:
    """Transverse mode profile of one microstrip cross-section at unit power.

    Field arrays (see the module docstring for the lattice positions)::

        phi   (N1, N2)  normalised potential on the nodes, V
        e_y   (ny, N2)  E . dl on the y-edges,        V   (at y-cell, z-node)
        e_z   (N1, nz)  E . dl on the z-edges,        V   (at y-node, z-cell)
        h_y   (N1, nz)  H . dl on the y-dual-faces,   A   (collocated with e_z)
        h_z   (ny, N2)  H . dl on the z-dual-faces,   A   (collocated with e_y)

    Line parameters, all from the same solve (``C0`` the speed of light)::

        c_prime      C' of the filled section, F/m
        c_prime_air  C' with eps_r = 1 everywhere, F/m
        eps_eff      c_prime / c_prime_air
        z0           sqrt(eps_eff) / (C0 * c_prime), ohm
        eta_eff      sqrt(MU0 / (EPS0 * eps_eff)), ohm

    Normalisation of the *fields*, in the terms a port projection needs::

        power           1 W, the normalisation target
        v_mode          volts the strip sits at under unit power, V
        i_mode          amps that unit power implies at that voltage, A
        power_full_box  power the whole wide box carries at the same scale, W

    **The field arrays are normalised to unit modal power over the projection
    window, not to 1 V.**  ``0.5 Re(v_mode conj(i_mode)) = power`` exactly, and
    so does the discrete ``0.5/eta_eff * sum(e_y^2 + e_z^2)`` over the edges
    :meth:`plane_window` selects for the default ``201 x 77`` plane.  The ``1 V``
    convention survives only as these diagnostics: the solve *is* done at 1 V
    and ``c_prime``, ``eps_eff``, ``z0`` are that solve's numbers, but the
    returned field is unit-power, so ``v_mode`` is the voltage that 1 W implies
    -- 9.9558 V on the converged section, because 1 V on this line is only
    ``0.5 / Z0``= 9.98 mW, and the missing tail makes it 0.58 % *higher* than the
    all-box ``sqrt(2 power Z0) = 10.0088 V``.  Scale the fields by ``1 / v_mode``
    to recover the 1 V normalisation.

    Geometry, in metres / integer cells::

        cell, h, w, eps_r, n_sub, n_strip, n_clean, n_air
    """

    phi: np.ndarray
    e_y: np.ndarray
    e_z: np.ndarray
    h_y: np.ndarray
    h_z: np.ndarray
    eta_eff: float
    c_prime: float
    c_prime_air: float
    eps_eff: float
    z0: float
    power: float
    v_mode: float
    i_mode: float
    power_full_box: float
    cell: float
    h: float
    w: float
    eps_r: float
    n_sub: int
    n_strip: int
    n_clean: int
    n_air: int

    # -- geometry helpers -------------------------------------------------
    @property
    def node_shape(self) -> tuple:
        """``(N1, N2)``, the shape of :attr:`phi`."""
        return self.phi.shape

    @property
    def iy_strip_centre(self) -> int:
        """First transverse node index at the centre of the strip."""
        return self.n_clean + self.n_strip // 2

    @property
    def strip_nodes(self) -> slice:
        """Nodes held at ``1 V`` along the first transverse axis."""
        return slice(self.n_clean, self.n_clean + self.n_strip + 1)

    @property
    def gap_cells(self) -> slice:
        """z-cells between the ground plane and the strip (``k < n_sub``)."""
        return slice(0, self.n_sub)

    def plane_window(
        self,
        nyn: int = _FDTD_NYN,
        nzn: int = _FDTD_NZN,
        k_strip: int = _FDTD_K_STRIP,
        iy_strip_centre: int | None = None,
        cell: float | None = None,
    ) -> PlaneWindow:
        """Slices placing this profile in an ``(nyn, nzn)`` FDTD plane.

        Parameters
        ----------
        nyn, nzn:
            **Node** counts of the target plane, defaults ``201`` x ``77`` --
            the production board's transverse plane (``ny = 200``, ``nz = 76``
            cells).
        k_strip:
            Node row of the target plane carrying the strip, default ``16``
            (``1.6 mm`` at ``0.1 mm`` cells).  The profile's ground plane lands
            on ``k_strip - n_sub``, which is the plane's own ``k = 0`` when the
            substrate thickness matches: put the interface and the conductors
            on the same nodes or nothing below holds.
        iy_strip_centre:
            Node index of the strip centre in the target plane, default
            ``nyn // 2`` (``100`` on the production plane).
        cell:
            If given, the target plane's cell size; it must equal
            :attr:`cell`, because only then are the two lattices the same
            lattice and an integer shift is meaningful.

        Returns
        -------
        PlaneWindow
            With ``src``/``dst`` slice pairs per lattice class; use it as ::

                (src, dst) = profile.plane_window().ycell_znode
                plane_e_y[dst] = profile.e_y[src]

        Notes
        -----
        **The profile is normally wider than the plane, and is clipped.**  The
        default box is 20 mm of clean dielectric on each side plus 20 mm of air
        (43.0 x 21.6 mm, 431 x 217 nodes) because that is where ``eps_eff``
        stops moving; the production plane is 20.0 x 7.6 mm (201 x 77 nodes).
        The two lattices share the cell size and the strip nodes, so the
        placement is still exact -- but only the central 20.0 x 7.6 mm of the
        mode is copied, and :attr:`PlaneWindow.clipped` says how much was left
        outside.  On the converged default profile that is 115 y-cells of
        dielectric on each side and 140 z-cells of air on top, which carried
        1.1649 % of the modal power (``.scratch/mp_split.py``: 0.5720 % from the
        y-clip alone, 0.7805 % above ``z = 7.6 mm``, 0.1876 % in the corner the
        two share).  A silent truncation would hide that, so it is reported
        instead.

        Raises
        ------
        ValueError
            If ``cell`` disagrees with the profile's, if ``k_strip < n_sub``,
            or if a lattice class misses the plane *entirely* (a shift so
            large that no source entry has a destination).
        """
        if cell is not None and not np.isclose(cell, self.cell, rtol=1e-9, atol=0.0):
            raise ValueError(
                f"target cell {cell!r} m is not the profile's cell "
                f"{self.cell!r} m: place the profile on its own lattice"
            )
        nyn, nzn, k_strip = int(nyn), int(nzn), int(k_strip)
        centre = nyn // 2 if iy_strip_centre is None else int(iy_strip_centre)
        iy_shift = centre - self.iy_strip_centre
        k_shift = k_strip - self.n_sub
        if k_shift < 0:
            raise ValueError(
                f"k_strip={k_strip} is above the profile's own substrate "
                f"(n_sub={self.n_sub} cells): the ground plane would fall "
                "outside the target plane"
            )

        # y-cells/z-nodes (e_y, h_z) and y-nodes/z-cells (e_z, h_y) are one
        # apart in either direction, so each lattice class gets its own fit --
        # a shared shift does not mean a shared clip count.
        yc, zn = self.e_y.shape
        yn, zc = self.e_z.shape
        yc_src, yc_dst, yc_lo, yc_hi = _fit("e_y/h_z, y", iy_shift, yc, nyn - 1)
        zn_src, zn_dst, zn_lo, zn_hi = _fit("e_y/h_z, z", k_shift, zn, nzn)
        yn_src, yn_dst, yn_lo, yn_hi = _fit("e_z/h_y, y", iy_shift, yn, nyn)
        zc_src, zc_dst, zc_lo, zc_hi = _fit("e_z/h_y, z", k_shift, zc, nzn - 1)
        return PlaneWindow(
            iy_shift=iy_shift,
            k_shift=k_shift,
            ycell_znode=((yc_src, zn_src), (yc_dst, zn_dst)),
            ynode_zcell=((yn_src, zc_src), (yn_dst, zc_dst)),
            clipped=tuple(
                record
                for record in (
                    ("e_y/h_z, y", yc_lo, yc_hi),
                    ("e_y/h_z, z", zn_lo, zn_hi),
                    ("e_z/h_y, y", yn_lo, yn_hi),
                    ("e_z/h_y, z", zc_lo, zc_hi),
                )
                if record[1] or record[2]
            ),
        )


def _fit(label: str, shift: int, count: int, extent: int) -> tuple:
    """Intersect source ``0:count`` with destination ``shift:shift + count``.

    Returns ``(src, dst, low, high)``: the aligned slice pair plus how many
    source entries fell below the target plane (``low``) and beyond its far end
    (``high``).  ``dst = src + shift`` elementwise, so the Yee stagger survives
    the placement.

    A too-wide profile is the *normal* case here (:meth:`ModeProfile.plane_window`
    places a 43 mm convergence box in a 20 mm plane), so overflow does not
    raise: it clips and hands the counts back for :attr:`PlaneWindow.clipped`.
    Only a placement with no overlap at all is an error, because then the
    shift is meaningless rather than merely tight.
    """
    low = max(0, -shift)
    high = min(count, extent - shift)
    if high <= low:
        raise ValueError(
            f"{label} misses the plane entirely: {count} entries at offset "
            f"{shift} do not intersect an extent of {extent}"
        )
    return slice(low, high), slice(low + shift, high + shift), low, count - high


# ----------------------------------------------------------------------
# section geometry
# ----------------------------------------------------------------------
def _section(h: float, w: float, n_sub: int, n_clean: int, n_air: int):
    """Cross-section mesh, its cell size and the strip width in cells."""
    if not (np.isfinite(h) and h > 0.0):
        raise ValueError(f"substrate thickness h must be positive, got {h!r}")
    if not (np.isfinite(w) and w > 0.0):
        raise ValueError(f"strip width w must be positive, got {w!r}")
    for name, n in (("n_sub", n_sub), ("n_clean", n_clean), ("n_air", n_air)):
        if int(n) != n or n < 1:
            raise ValueError(f"{name} must be a positive integer, got {n!r}")

    cell = h / int(n_sub)
    n_strip = int(round(w / cell))
    if n_strip < 1 or abs(n_strip * cell - w) > 1e-9 * cell:
        raise ValueError(
            f"strip width w={w!r} m is not a whole number of cells: w/cell = "
            f"{w / cell!r} at cell h/n_sub={cell!r} m.  A section strip is a "
            "fixed number of mesh cells wide, so pick n_sub to divide it."
        )
    ny = 2 * int(n_clean) + n_strip
    nz = int(n_sub) + int(n_air)
    grid = Grid.uniform(
        1, ny, nz, cell, ny * cell, nz * cell, periodic=(True, False, False)
    )
    return grid, cell, n_strip


def _conductors(grid: Grid, n_clean: int, n_strip: int, n_sub: int):
    """``fixed`` list: whole bottom row at 0 V, the strip row at 1 V.

    The strip is ``n_strip`` cells wide, i.e. ``n_strip + 1`` nodes, and sits on
    the node plane ``k = n_sub`` so the substrate interface is exactly resolved.
    """
    n1, _ = node_shape(grid)
    ground = [node_index(grid, i, 0) for i in range(n1)]
    strip = [
        node_index(grid, i, n_sub) for i in range(n_clean, n_clean + n_strip + 1)
    ]
    return [(0.0, ground), (1.0, strip)]


def _require_close(label: str, got: float, want: float, rtol: float = _RTOL):
    """Raise :class:`SelfConsistencyError` unless ``got == want`` to ``rtol``."""
    scale = max(abs(got), abs(want))
    if not np.isfinite(got) or abs(got - want) > rtol * scale:
        raise SelfConsistencyError(
            f"{label}: {got!r} != {want!r} (relative gap "
            f"{abs(got - want) / scale:.3e}, allowed {rtol:.0e}) -- the field "
            "and the line parameters did not come from the same solve"
        )


def _projection_slices(
    e_y_shape: tuple, e_z_shape: tuple, iy_shift: int, k_shift: int
) -> tuple:
    """Source slices of the profile that land inside the projection window.

    Returns ``(e_y y, e_y z, e_z y, e_z z)`` -- the four *source* slices of
    :class:`PlaneWindow`, for the default ``_FDTD_NYN x _FDTD_NZN`` plane.  Both
    the power normalisation and :meth:`ModeProfile.plane_window` go through
    :func:`_fit`, so the domain the profile is normalised over and the domain the
    projection integrates over cannot drift apart; that equality is the whole
    point of the normalisation (``tests/test_mode_profile.py`` asserts it).
    """
    yc, zn = e_y_shape
    yn, zc = e_z_shape
    return (
        _fit("e_y/h_z, y", iy_shift, yc, _FDTD_NYN - 1)[0],
        _fit("e_y/h_z, z", k_shift, zn, _FDTD_NZN)[0],
        _fit("e_z/h_y, y", iy_shift, yn, _FDTD_NYN)[0],
        _fit("e_z/h_y, z", k_shift, zc, _FDTD_NZN - 1)[0],
    )


def _modal_power(e_y, e_z, eta_eff: float) -> float:
    """``0.5 / eta_eff * sum(e_y^2 + e_z^2)`` over the edges handed in, in W.

    ``e`` is ``E . dl`` in volts, so ``e^2 = |E|^2 cell^2`` is exactly the flux
    element ``|E_t|^2 dA`` of the edge -- no cell size and no interpolation, and
    the same quadrature the projection uses.  Both families enter because they
    are the two components of one transverse vector: for the forward wave
    ``h = x_hat x e / eta_eff``, ``(e x h) . x_hat = (e_y^2 + e_z^2) / eta_eff``.
    """
    return 0.5 * float(np.sum(np.square(e_y)) + np.sum(np.square(e_z))) / eta_eff


# ----------------------------------------------------------------------
# the profile
# ----------------------------------------------------------------------
def microstrip_mode_profile(
    h: float,
    w: float,
    eps_r: float,
    *,
    n_sub: int = _DEFAULT_N_SUB,
    n_clean: int = _DEFAULT_N_CLEAN,
    n_air: int = _DEFAULT_N_AIR,
    check: bool = True,
) -> ModeProfile:
    """Quasi-static transverse mode profile of a zero-thickness microstrip.

    Parameters
    ----------
    h, w:
        Substrate thickness and strip width [m].  ``w`` must be a whole number
        of cells at ``cell = h / n_sub``; a section strip always is.
    eps_r:
        Relative permittivity of the substrate; the region above the strip is
        vacuum.  The interface sits on the node plane ``z = h`` and is resolved
        by the library's ``interface="dual"`` rule, so nothing is sampled *on*
        the plane (see :mod:`emfit.quasistatic`).
    n_sub:
        Substrate cells across ``h``; sets the cell size ``h / n_sub``.  The
        default ``16`` is the FDTD board's ``0.1 mm`` cell at ``h = 1.6 mm``.
    n_clean:
        Clean cells each side of the strip (the lateral Neumann walls).
    n_air:
        Air cells above the strip (the top Neumann wall).
    check:
        Assert the self-consistency identities at ``rtol = 1e-12`` and raise
        :class:`SelfConsistencyError` if one fails.  Turning this off is only
        for timing comparisons -- there is no approximation to relax.

    Returns
    -------
    ModeProfile
        Potential, transverse E and H on the staggered lattice, and the line
        parameters of the same solve.

    Raises
    ------
    ValueError
        On a non-positive dimension, a non-integer cell count, or a strip width
        that is not a whole number of cells.
    SelfConsistencyError
        If ``check`` and the edge field does not reproduce the solve's own
        ``C'``, ``Z0`` and ``eps_eff``, or the vertical drop against ``v_mode``.

    Notes
    -----
    The default box (``n_clean = 200``, ``n_air = 200`` cells: 43.0 x 21.6 mm,
    431 x 217 nodes at ``h = 1.6 mm``) is the measured plateau, deliberately
    **much wider than any FDTD plane** -- at 20 mm of wall each side and above,
    ``eps_eff`` is 3.35001 and ``Z0`` 50.088 ohm, i.e. +0.74 % / 1.04 % off the
    Hammerstad-Jensen fit, and the residual drift is 0.3 % per 5 mm of wall.
    A box sized to the FDTD plane instead would be 4-5 % high, so the profile is
    converged on its own terms and then *placed* by index offset with
    :meth:`ModeProfile.plane_window`.  Both counts are quoted in *cells* because
    the bias is a function of how many cells of clean space surround the strip,
    not of how finely that space is meshed.

    Normalisation: the returned arrays carry ``power = 1 W`` of modal power over
    the **projection window**, the ``201 x 77`` (``_FDTD_NYN x _FDTD_NZN``) node
    plane that :meth:`ModeProfile.plane_window` copies into an FDTD grid -- not
    over the converged box.  The two are not the same domain: 1.164852 % of this
    profile's modal power lies outside the FDTD plane (0.571953 % from the
    ``|y| > 10 mm`` clip, 0.780454 % above ``z = 7.6 mm``, 0.187555 % in the
    corner both cut).  That clip is a constant lateral truncation, identical at
    every station, so it biases the *level* of an excitation -- by
    ``sqrt(P_window / P_box) = 0.994159``, i.e. 0.584 % in amplitude and 1.165 %
    in power -- and cannot contribute to a decay along ``x``.  Normalising on the
    window removes the bias by construction instead of leaving it to be argued
    away.

    The ``1 V`` strip of the potential solve is therefore *reported*, not
    imposed: ``v_mode`` is the voltage that unit power implies on this geometry,
    ``i_mode = power / (0.5 v_mode)`` the current that goes with it, and
    ``power_full_box`` the power the same fields would carry through the whole
    converged box (``power_full_box = 1.01178580 W`` here: exactly the 1.164852 %
    the clip removed).
    """
    grid, cell, n_strip = _section(h, w, n_sub, n_clean, n_air)
    fixed = _conductors(grid, n_clean, n_strip, int(n_sub))
    substrate = lambda x, y, z: np.where(z < h, eps_r, 1.0)  # noqa: E731

    phi_flat, K, length = _solve(grid, substrate, fixed)
    G, m, _ = _transverse_metric(grid, substrate)

    n1, n2 = node_shape(grid)
    ny = grid.shape[1]
    nz = grid.shape[2]
    # ``G`` is the node-to-edge incidence (n_nodes x n_edges), so the edge
    # field is its transpose applied to the potentials.
    e = -(G.T @ phi_flat)                   # E . dl on every transverse edge
    e_y = e[: ny * n2].reshape(ny, n2)      # y-edges: y-cell  x z-node
    e_z = e[ny * n2:].reshape(n1, nz)       # z-edges: y-node  x z-cell
    if e_y.size + e_z.size != e.size:       # pragma: no cover - structural
        raise SelfConsistencyError(  # noqa: TRY003
            f"edge split {e_y.size} + {e_z.size} != {e.size}: the transverse "
            "edge families are not ordered y-then-z"
        )

    # --- line parameters: the solve's own numbers, plus the air reference ---
    v_scale = 1.0                           # strip 1 V, ground 0 V, exactly
    c_prime = float(phi_flat @ (K @ phi_flat)) / (v_scale ** 2 * length)
    c_air = capacitance_per_length(grid, 1.0, fixed)
    eps_eff = c_prime / c_air
    z0 = float(np.sqrt(eps_eff) / (C0 * c_prime))
    eta_eff = float(np.sqrt(MU0 / (EPS0 * eps_eff)))

    # --- unit modal power over the projection window -----------------------
    # The normalisation integral *is* the projection integral: 0.5 Re(V conj(I))
    # = P holds identically for any superposition coefficient, so if the two
    # domains differ, the clip enters as a pure scale bias on the projected
    # mode.  Measuring the power on the clipped window removes that by
    # construction, which is stronger than normalising over some box and
    # rescaling afterwards.
    iy_shift = _FDTD_NYN // 2 - (int(n_clean) + n_strip // 2)
    k_shift = _FDTD_K_STRIP - int(n_sub)
    win = _projection_slices(e_y.shape, e_z.shape, iy_shift, k_shift)
    p_full = _modal_power(e_y, e_z, eta_eff)
    p_win = _modal_power(e_y[win[0], win[1]], e_z[win[2], win[3]], eta_eff)
    if not p_win > 0.0:                     # pragma: no cover - structural
        raise ValueError(
            f"the projection window carries no power ({p_win!r} W): the profile "
            f"(e_y {e_y.shape}, e_z {e_z.shape}) does not overlap the "
            f"{_FDTD_NYN} x {_FDTD_NZN} node plane"
        )
    scale = float(np.sqrt(_POWER_W / p_win))
    e = e * scale
    e_y = e_y * scale
    e_z = e_z * scale
    phi_flat = np.asarray(phi_flat, dtype=float) * scale
    v_mode = float(scale * v_scale)         # volts that 1 W implies here
    i_mode = float(_POWER_W / (0.5 * v_mode))

    if check:
        # 1. The field carries the energy the solve produced.  Two different
        #    sums (edge-wise vs K) of the same quadratic form, so this catches
        #    any layout mistake in the reshapes above.
        _require_close(
            "sum(m e^2) / (V^2 L) vs phi^T K phi / (V^2 L)",
            float(np.sum(m * e ** 2)) / (v_mode ** 2 * length),
            c_prime,
        )
        # 2. ... and the profile's C' is the quasi-static module's C'.
        _require_close(
            "profile C' vs quasistatic.capacitance_per_length",
            c_prime,
            capacitance_per_length(grid, substrate, fixed),
        )
        # 3. ... as are the derived line parameters.
        z0_ref, eps_ref = z0_eps_eff(grid, substrate, fixed)
        _require_close("eps_eff vs quasistatic.z0_eps_eff", eps_eff, float(eps_ref))
        _require_close("Z0 vs quasistatic.z0_eps_eff", z0, float(z0_ref))
        # 4. The field still knows what voltage it is at: the z-edges of any strip
        #    column telescope to ``v_mode``, the voltage unit power implies, and
        #    no other column does (that one is left to the tests -- the potential
        #    off the strip is whatever the box makes it).  Scaling to unit power
        #    moved every one of these by the same factor, so the identity is as
        #    exact as it was at 1 V.
        drop = -float(np.sum(e_z[n_clean + n_strip // 2, : int(n_sub)]))
        _require_close("vertical drop over one strip column vs v_mode", drop, v_mode)
        # 5. ... and the power is the power the projection will see: the domain
        #    this integral uses is the domain plane_window() copies into.
        _require_close(
            "0.5 Re(v_mode conj(i_mode)) vs unit power",
            0.5 * v_mode * i_mode,
            _POWER_W,
        )

    # --- companion H: local plane wave h = (1/eta) x_hat x e --------------
    h_z = e_y / eta_eff                    # FZ, collocated with e_y
    h_y = -e_z / eta_eff                   # FY, collocated with e_z

    return ModeProfile(
        phi=np.asarray(phi_flat, dtype=float).reshape(n1, n2),
        e_y=e_y,
        e_z=e_z,
        h_y=h_y,
        h_z=h_z,
        eta_eff=eta_eff,
        c_prime=c_prime,
        c_prime_air=float(c_air),
        eps_eff=float(eps_eff),
        z0=z0,
        power=_POWER_W,
        v_mode=v_mode,
        i_mode=i_mode,
        power_full_box=float(p_full * scale ** 2),
        cell=float(cell),
        h=float(h),
        w=float(w),
        eps_r=float(eps_r),
        n_sub=int(n_sub),
        n_strip=int(n_strip),
        n_clean=int(n_clean),
        n_air=int(n_air),
    )
