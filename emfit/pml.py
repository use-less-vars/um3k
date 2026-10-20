"""Matched lossy layer absorber for the FIT leapfrog scheme.

Why this form
-------------
A layer whose *electric* conductivity ``sigma_e`` and *magnetic* conductivity
``sigma_m`` satisfy

    sigma_m / mu0 = sigma_e / eps0

has the same wave impedance as vacuum, so in the continuum it is reflectionless
at **every** angle of incidence and for both polarisations: the wave is
attenuated, not scattered.  That is the matched lossy layer (sometimes called
the matched PML), and it is the form implemented here -- not split-field
Berenger and not the UPML material tensors.

The practical reason is the one that matters in this codebase: a matched lossy
layer needs **no auxiliary variables** and **no change to the curl operators**.
It is a pointwise multiplicative decay applied to the already-computed field
values, so it cannot disturb the discrete de Rham structure that
:mod:`emfit.operators` provides, and with the layer switched off the update is
bit-identical to the one without it.

What it is not: perfect.  Because the layer is a matched lossy layer -- not
split-field Berenger and not UPML -- there is no mechanism for reflection in
the continuum at any angle, so the only residual is the discretisation error
of the graded profile (plus whatever the outer wall lets through).  That
residual is what the measurements in ``docs/pml_notes.md`` show, and thickness
is the knob that controls it: the reflection improves roughly **linearly in
dB** with thickness.  Measured by a two-run difference at normal incidence for
``order=2, target=1e-4``::

    thickness_cells    20      30      40      50
    reflection (dB)   -52     -63     -79     -89

so 20 cells is a deliberately modest default that fits small grids, not the
optimum; a real absorber wants 40 or more.  Even at 20 cells the layer is far
better than the first-order Mur condition in :mod:`emfit.abc`, which is a
one-way (normal-incidence) approximation, and the gap widens with angle.

Grading
-------
With ``d`` the physical thickness of the layer on one axis, ``h`` the cell
width there and ``order`` the polynomial order of the profile,

    sigma_max = -(order + 1) * ln|target| / (eta0 * d),

which is the normal-incidence grading formula: the one-way attenuation through
the layer is ``exp(-eta0 * integral sigma dx)``, and for a profile
``sigma = sigma_max * (xi/d)**order`` the integral is ``sigma_max * d /
(order + 1)``, so the round-trip reflection is ``exp(-2 * eta0 * sigma_max * d
/ (order + 1)) = target**2`` in the continuum.  ``target`` is therefore the
one-way amplitude at the far side, not the reflection.

On an axis with a layer at both ends the 1-D profile is, with
``depth`` the distance from the nearer wall,

    s(xi) = clip(1 - depth / d, 0, 1),  sigma = sigma_max * s**order

so ``sigma`` is ``sigma_max`` at the wall, falls to zero at the inner
interface and is identically zero on the whole physical interior.

For a cell or face in a corner the axes are **summed**, which is the
standard corner combination: the loss rates of the two 1-D layers add, and the
impedance stays matched in the corner because both parts are matched
individually.

Staggering
----------
The FIT layout is the Yee one, so the conductivity has to be sampled where the
component actually lives:

* an edge parallel to ``axis`` sits at the cell centre along ``axis`` and at
  node values across it (``EX`` at ``(i+1/2, j, k)``, i.e. the ``Ez`` of a 2-D
  TM run is at a node pair as expected),
* a face normal to ``axis`` sits at node values along ``axis`` and at cell
  centres across it (``HX`` at ``(i, j+1/2, k+1/2)``).

Half a cell of slip in a graded profile is a first-order error in ``sigma``
where the profile is steepest, and it shows up as a residual reflection well
above the -60 dB level, so :func:`_coordinates` reproduces the sampling
convention of :func:`emfit.materials.material_matrices` exactly (that rule is
written out here so this module does not reach into private helpers).

The matched condition in one line
---------------------------------
``sigma_m`` is sampled on the faces with the *same* 1-D profiles as ``sigma_e``
on the edges, which is what "the corresponding mu0 form" means: the two
multipliers differ only in the constant in the denominator, and when
``sigma_m = sigma_e * mu0 / eps0`` the dimensionless products
``sigma_e*dt/(2 eps0)`` and ``sigma_m*dt/(2 mu0)`` are equal by construction.

Usage
-----
::

    pml = PML(grid, thickness_cells=20, order=2, target=1e-4,
              axes=("x", "y"))
    stepper = FITStepper(cc, m_eps, m_mu, pml=pml)     # damping inside step()
    # or by hand, at the two leapfrog points:
    pml.damp_h(stepper.h, stepper.dt)      # after the h update
    pml.damp_e(stepper.e, stepper.dt)      # after the e update

A direction that carries no absorber is simply left out of ``axes``.  A
**periodic** direction may not receive one: the layer would wrap onto itself,
so :class:`PML` refuses it at construction time.
"""

from __future__ import annotations

import numpy as np

from .materials import EPS0, ETA0, MU0
from .operators import CellComplex

__all__ = ["PML", "AbsorbedWork", "AXES", "cells_for_wavelength"]

#: the three index axes, in the order the flat edge/face vectors use
AXES = ("x", "y", "z")

#: the six walls, spelled exactly as :meth:`emfit.operators.CellComplex.pec_edge_mask`
_WALLS = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")


# ----------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------
def _fit(values: np.ndarray, size: int) -> np.ndarray:
    """Fit a 1-D coordinate array to ``size`` samples.

    Only needed on a *periodic* transverse axis, where :class:`emfit.grid.Grid`
    stores ``n + 1`` nodes but the field arrays carry ``n`` layers (the last
    node is the first node again).  Truncating or repeating the end point keeps
    the sampling consistent without changing any value that is used twice.
    """
    if values.size == size:
        return values
    if values.size > size:
        return values[:size]
    return np.concatenate([values, np.full(size - values.size, values[-1])])


def _coordinates(grid, axis: str, along_mid: bool):
    """Coordinates of every edge (``along_mid``) or face centre of ``axis``.

    Same convention as :func:`emfit.materials.material_matrices`: along the
    edge direction an edge is at a cell centre and a face at a node; across the
    direction it is the other way round.  The three returned arrays are
    broadcast to the full edge/face shape, so they can be summed directly.
    """
    target = grid.edge_shape(axis) if along_mid else grid.face_shape(axis)
    a = AXES.index(axis)
    out = []
    for t, name in enumerate(AXES):
        nodes = np.asarray(getattr(grid, name), dtype=float)
        if (t == a) == along_mid:
            values = 0.5 * (nodes[1:] + nodes[:-1])
        else:
            values = nodes
        values = _fit(values, target[t])
        shape = [1, 1, 1]
        shape[t] = values.size
        out.append(np.broadcast_to(values.reshape(shape), target))
    return out


def _wall_names(walls) -> tuple:
    """Canonicalise ``walls`` to a tuple in ``_WALLS`` order.

    Duplicates collapse and the order is fixed, so two callers who name the
    same walls in a different order get the same layer (and the same
    ``repr``).  An unknown name, a bare string or an empty selection is an
    error rather than a silently ignored wall: a misspelt ``"zmin"`` would
    otherwise leave the field reflecting off a wall the caller believed was
    absorbing.
    """
    if isinstance(walls, str):
        raise ValueError(
            f"walls must be a sequence of wall names, not the single string "
            f"{walls!r}; expected a subset of {_WALLS}")
    try:
        names = tuple(walls)
    except TypeError:
        raise ValueError(
            f"walls must be a sequence of wall names, got {walls!r}; "
            f"expected a subset of {_WALLS}") from None
    for name in names:
        if name not in _WALLS:
            raise ValueError(
                f"unknown wall {name!r}; expected a subset of {_WALLS}")
    if not names:
        raise ValueError(
            f"walls is empty: a layer that damps no wall damps nothing; "
            f"expected a subset of {_WALLS}")
    return tuple(name for name in _WALLS if name in names)


def _blocks(cc, kind: str):
    """``((axis, offset, count), ...)`` for the ``"e"`` (edge) or ``"f"`` blocks."""
    if kind == "e":
        return (("x", cc.off_ex, cc.n_ex),
                ("y", cc.off_ey, cc.n_ey),
                ("z", cc.off_ez, cc.n_ez))
    return (("x", cc.off_fx, cc.n_fx),
            ("y", cc.off_fy, cc.n_fy),
            ("z", cc.off_fz, cc.n_fz))


# ----------------------------------------------------------------------
# where the absorbed energy went
# ----------------------------------------------------------------------
class AbsorbedWork:
    """Opt-in accounting of the energy a :class:`PML` removes, by wall group.

    A matched layer that is doing its job removes a little of the guided field
    every step.  This class adds those removals up and bins them, so a run can
    say *where* the power it loses actually goes -- the termination at the far
    end of a line, or the lateral walls it was never meant to touch -- instead
    of only that a fitted decay exists.

    What is counted
    ---------------
    The damping is a multiplicative decay of the already-updated field,
    ``e <- f e``, so the electric energy it takes out of one entry in a step is
    exactly

        w = 1/2 m_eps e^2 (1 - f^2)      [J]

    with ``m_eps`` the same diagonal material matrix the stepper uses (so the
    sum over entries is the change in ``1/2 e.m_eps.e``, not a density).  The
    faces get the identical expression with ``m_mu`` and the ``h`` multiplier.
    Nothing is divided by ``f`` and the field is read *before* the multiplier
    is applied, so the count is exact in the discrete quadratic form and cannot
    be distorted by a small ``f``.

    At a corner a cell carries the *sum* of two 1-D layers, and one product
    ``1 - f^2`` cannot be attributed to either of them.  It is split by rate,
    ``sigma_wall / sigma_total``, which is exact in the continuum limit and
    keeps the bins summing to the total removed work to round-off either way.

    How it is binned
    ----------------
    ``groups`` maps a name to the walls that group owns, e.g.
    ``{"end": ("xmin", "xmax"), "lateral": ("ymin", "ymax", "zmax")}``.
    ``None`` (default) makes one group per axis the layer is open on.  A wall
    the layer does not open contributes exactly zero, which is how a group that
    is switched off reads: not "nearly nothing" but ``0.0``.

    Cost, and why it is off by default
    ----------------------------------
    With no audit attached ``damp_e``/``damp_h`` take no extra branch, allocate
    nothing and are bit-identical to the layer without this class.  With one
    attached, each ``damp_*`` costs one gather and one dot product per group
    over the entries of that group -- a few thousand doubles on a small grid.
    The weight vectors are built once per ``dt`` and reused, so no per-step
    preparation is done in the time loop.

    Reset it to accumulate a window rather than the whole run: ``active``
    turned off records nothing, and :meth:`reset` zeroes the bins, which is how
    a caller accumulates only the settled part of a record.

    Attributes
    ----------
    work : dict
        ``{kind: {group: joules}}`` with ``kind`` in ``("e", "h")``.
    steps : int
        Number of ``dt`` intervals recorded (zero while inactive).
    active : bool
        Whether :meth:`record` accumulates.
    """

    def __init__(self, groups=None, active: bool = True):
        self.groups = (None if groups is None else
                       {str(name): _wall_names(walls)
                        for name, walls in dict(groups).items()})
        if self.groups is not None and not self.groups:
            raise ValueError("groups is empty: no group would be counted")
        self.active = bool(active)
        self.steps = 0
        self.work = {"e": {}, "h": {}}
        self._pml = None
        self._m = {"e": None, "h": None}
        self._dt = None
        self._weights = None

    # ------------------------------------------------------------------
    def attach(self, pml) -> "AbsorbedWork":
        """Bind to ``pml`` and finish the bounds of the bins.

        Called by the layer itself, so a caller only has to hand the object to
        ``PML(audit=...)``.  With no ``groups`` given the bins become one per
        axis the layer actually opens.
        """
        self._pml = pml
        if self.groups is None:
            self.groups = {axis: pml.walls_for(axis) for axis in pml.axes}
        self.reset()
        return self

    def bind_materials(self, m_eps, m_mu) -> "AbsorbedWork":
        """Bind the diagonal material matrices the weights are built from.

        They live on the stepper, not on the layer, so this cannot happen at
        construction: the field the layer damps is the one the stepper's own
        ``m_eps``/``m_mu`` priced.
        """
        self._m = {"e": np.asarray(m_eps, dtype=float).ravel(),
                   "h": np.asarray(m_mu, dtype=float).ravel()}
        self._weights = None
        return self

    def reset(self) -> "AbsorbedWork":
        """Zero the bins and the step count, keeping the bindings."""
        names = () if self.groups is None else tuple(self.groups)
        self.work = {"e": dict.fromkeys(names, 0.0),
                     "h": dict.fromkeys(names, 0.0)}
        self.steps = 0
        return self

    # ------------------------------------------------------------------
    def _build(self, dt: float) -> None:
        """Weight vectors: joules removed per unit field squared, per entry."""
        pml = self._pml
        if pml is None:
            raise RuntimeError("the audit is not attached to a PML yet")
        if self._m["e"] is None or self._m["h"] is None:
            raise RuntimeError(
                "the audit has no material matrices: call bind_materials() "
                "with the stepper's m_eps and m_mu (FITStepper does this)")
        f_e, f_h = pml.multipliers(dt)
        weights = {"e": {}, "h": {}}
        # ``sigma_e`` is ``sigma`` on the edges; ``sigma_m`` is the same profile
        # on the faces scaled by ``mu0/eps0``, while ``sigma_for_walls`` returns
        # the unscaled profile, so the face share has to undo that factor.
        for kind, f, sigma, sampling, scale in (
                ("e", f_e, pml.sigma_e, "e", 1.0),
                ("h", f_h, pml.sigma_m, "f", MU0 / EPS0)):
            m = self._m[kind]
            if m.size != f.size:
                raise ValueError(
                    f"m_{'eps' if kind == 'e' else 'mu'} has {m.size} entries, "
                    f"the layer's {kind} multiplier has {f.size}")
            live = sigma > 0.0
            base = 0.5 * m * (1.0 - f * f)
            for name, walls in self.groups.items():
                share = np.zeros(sigma.size, dtype=float)
                np.divide(scale * pml.sigma_for_walls(walls, kind=sampling),
                          sigma, out=share, where=live)
                w = base * share
                idx = np.flatnonzero(w)
                weights[kind][name] = (idx, w[idx])
        self._weights = weights
        self._dt = float(dt)

    def record(self, kind: str, field, dt: float, pml) -> None:
        """Accumulate the work ``pml`` is about to remove from ``field``.

        Called from ``damp_e``/``damp_h`` *before* the multiplier is applied;
        the layer's own ``multipliers(dt)`` call has already cached ``f``, so
        the weights only have to be rebuilt when ``dt`` changes.
        """
        if not self.active:
            return
        if self._pml is None:
            self.attach(pml)
        if self._weights is None or float(dt) != self._dt:
            self._build(float(dt))
        field = np.asarray(field, dtype=float)
        bins = self.work[kind]
        for name, (idx, w) in self._weights[kind].items():
            values = field[idx]
            bins[name] = bins.get(name, 0.0) + float(w @ (values * values))
        if kind == "e":
            self.steps += 1

    # ------------------------------------------------------------------
    def total(self, name: str) -> float:
        """Joules removed by one group, both fields together."""
        return float(self.work["e"].get(name, 0.0)
                     + self.work["h"].get(name, 0.0))

    def total_work(self) -> float:
        """Joules removed by the whole layer, all groups together."""
        return float(sum(self.total(name) for name in self.work["e"]))

    def fractions(self) -> dict:
        """``{group: share of the removed work}``; all zeros if none removed."""
        total = self.total_work()
        names = tuple(self.work["e"])
        if total <= 0.0:
            return dict.fromkeys(names, 0.0)
        return {name: self.total(name) / total for name in names}

    def __repr__(self):  # pragma: no cover - cosmetic
        parts = ", ".join(f"{name}: {self.total(name):.4g} J"
                          for name in self.work["e"])
        return f"AbsorbedWork(steps={self.steps}, {parts})"


# ----------------------------------------------------------------------
# the layer
# ----------------------------------------------------------------------
class PML:
    """Matched lossy layer on the outer cells of a grid.

    Parameters
    ----------
    grid : emfit.grid.Grid
        The grid whose outer cells are to be damped.
    thickness_cells : int, optional
        Thickness of the layer on each active axis, in cells (default 20).
        The physical thickness is ``thickness_cells * h`` with ``h`` the
        smallest cell width on that axis.  The reflection improves roughly
        linearly in dB with this number (-52 dB at 20 cells, -63 at 30, -79 at
        40, -89 at 50 for the other defaults), so 20 is a small-grid default
        rather than a recommendation: use min(40, n_cells // 8) when the grid
        allows it.
    order : int, optional
        Polynomial order of the grading (default 2).  Higher order means a
        gentler start to the profile, hence less discretisation error, at the
        cost of needing a few more cells for the same total attenuation; in
        this discretisation order 2 measured better than 3 at fixed
        thickness.
    target : float, optional
        One-way amplitude at the outer side of the layer in the continuum
        (default ``1e-4``, i.e. -80 dB one way).  Only ``|target|`` is used.
        This sets ``sigma_max``; pushing it much below ``1e-4`` over-drives the
        profile (attenuation above ~1.5 Np/cell stops helping, and the
        measured floor stalls near -45 dB), so the default is deliberately
        loose.
    axes : sequence of str, optional
        Which directions get a layer, a subset of ``("x", "y", "z")``
        (default ``("x", "y")``).  A direction that is not listed keeps
        whatever boundary condition the caller imposes, so an open direction
        should always be listed and a periodic one never.  Ignored (and
        replaced, see ``walls``) when ``walls`` is given.
    cc : emfit.operators.CellComplex, optional
        Cell complex of ``grid``, built on demand if omitted.
    audit : emfit.pml.AbsorbedWork, optional
        Opt-in accounting of the energy the layer removes, binned by wall
        group (default ``None``: no bookkeeping, and the damping loop is
        unchanged to the bit).  See :class:`AbsorbedWork`; the stepper binds
        the material matrices for it, so this needs nothing else from the
        caller.
    walls : sequence of str, optional
        Which of the six walls get a layer, a subset of ``("xmin", "xmax",
        "ymin", "ymax", "zmin", "zmax")`` -- the same spelling
        :meth:`emfit.operators.CellComplex.pec_edge_mask` takes, so one tuple
        can be handed to both.  ``None`` (default) means "both ends of every
        axis in ``axes``", which is the historical behaviour.

        When ``walls`` is given it **replaces** ``axes``: the active axes are
        the ones the named walls belong to, and a layer can be opened on one
        end of an axis while the other end keeps whatever boundary condition
        the caller imposes -- the case of a guide that runs out of the box on
        one side only.  A single-ended layer only needs ``thickness_cells``
        cells, not ``2 * thickness_cells``, and the profile it applies is the
        same graded one either way: the unselected end is exactly zero.

    Attributes
    ----------
    sigma_e : ndarray (n_edges,)
        Electric conductivity sampled at the edges [S/m]; zero on the whole
        physical interior, a sum of graded profiles inside the layers.
    sigma_m : ndarray (n_faces,)
        Magnetic conductivity at the faces [ohm/m], equal to ``sigma_e *
        mu0 / eps0`` sampled on the same profiles.
    sigma_max : dict
        ``{axis: sigma_max}`` actually used [S/m].
    d : dict
        ``{axis: physical thickness}`` [m].
    walls : tuple of str
        The selected walls, in ``("xmin", ..., "zmax")`` order.
    """

    def __init__(self, grid, thickness_cells: int = 20, order: int = 2,
                 target: float = 1e-4, axes=("x", "y"), cc=None, walls=None,
                 audit=None):
        self.grid = grid
        self.cc = CellComplex(grid) if cc is None else cc
        self.thickness_cells = int(thickness_cells)
        if self.thickness_cells < 1:
            raise ValueError(
                f"thickness_cells must be >= 1, got {thickness_cells!r}")
        self.order = int(order)
        if self.order < 1:
            raise ValueError(f"order must be >= 1, got {order!r}")
        target = float(target)
        if not (0.0 < abs(target) < 1.0):
            raise ValueError(
                f"target must satisfy 0 < |target| < 1, got {target!r}")
        self.target = abs(target)

        axes = tuple(axes)
        for name in axes:
            if name not in AXES:
                raise ValueError(
                    f"unknown axis {name!r}; expected a subset of {AXES}")
        axes = tuple(name for name in AXES if name in axes)

        if walls is None:
            self.walls = tuple(f"{name}{end}" for name in axes
                               for end in ("min", "max"))
        else:
            self.walls = _wall_names(walls)
            if axes != ("x", "y"):
                for name in axes:
                    if not any(w.startswith(name) for w in self.walls):
                        raise ValueError(
                            f"axis {name!r} is listed in axes={axes!r} but "
                            f"walls={self.walls!r} selects no wall on it: "
                            f"walls replaces axes when it is given, so name "
                            f"the walls you want instead of passing both")
        self.axes = tuple(name for name in AXES if self.walls_for(name))

        self.d = {}
        self.sigma_max = {}
        for name in self.axes:
            if grid.is_periodic(name):
                raise ValueError(
                    f"axis {name!r} is periodic: a PML would wrap onto itself")
            n_cells = int(grid.shape[AXES.index(name)])
            ends = self.walls_for(name)
            if len(ends) == 2:
                if 2 * self.thickness_cells >= n_cells:
                    raise ValueError(
                        f"axis {name!r}: {self.thickness_cells} cells of PML "
                        f"on each side do not fit in {n_cells} cells")
            elif self.thickness_cells >= n_cells:
                raise ValueError(
                    f"axis {name!r}: {self.thickness_cells} cells of PML on "
                    f"the {ends[0]} side do not fit in {n_cells} cells")
            h = float(np.min(grid.widths(name)))
            self.d[name] = self.thickness_cells * h
            # normal-incidence grading: exp(-eta0 * int sigma dx) = target
            self.sigma_max[name] = (-(self.order + 1.0) * np.log(self.target)
                                    / (ETA0 * self.d[name]))

        self.sigma_e = self._sigma_edges()
        self.sigma_m = self._sigma_faces() * (MU0 / EPS0)
        self._last_dt = None
        self._multipliers = None

        # Off by default: ``None`` leaves the damping loop exactly as it was.
        self._audit = audit
        if audit is not None:
            audit.attach(self)

    # ------------------------------------------------------------------
    # the 1-D profile and the two samplings
    # ------------------------------------------------------------------
    def profile(self, axis: str, position):
        """1-D graded conductivity of ``axis`` at ``position`` [S/m].

        ``position`` may be a scalar or an array of coordinates along
        ``axis``.  Zero outside the layer, ``sigma_max`` at the outer face.
        """
        nodes = np.asarray(getattr(self.grid, axis), dtype=float)
        lo, hi = float(nodes[0]), float(nodes[-1])
        position = np.asarray(position, dtype=float)
        depth = np.minimum(position - lo, hi - position)
        s = np.clip(1.0 - depth / self.d[axis], 0.0, 1.0)
        return self.sigma_max[axis] * s ** self.order

    def walls_for(self, axis: str) -> tuple:
        """The selected walls of ``axis``, in ``_WALLS`` order.

        Empty means the axis carries no layer; one entry means a single-ended
        layer on that wall.
        """
        if axis not in AXES:
            raise ValueError(
                f"unknown axis {axis!r}; expected one of {AXES}")
        return tuple(w for w in self.walls if w.startswith(axis))

    def _wall_profile(self, axis: str, position, walls) -> np.ndarray:
        """1-D profile of ``axis`` restricted to the selected ``walls``.

        With both ends selected this is :meth:`profile` unchanged, bit for bit,
        which is what keeps the default layer identical to the two-sided one
        this class has always built.  With a single end the profile keeps the
        values on that half of the axis and sets the other half to exactly
        zero, so the layer stops at the mid-plane instead of leaking a second
        one in through the far wall.
        """
        values = np.asarray(self.profile(axis, position), dtype=float)
        if len(walls) == 2:
            return values
        nodes = np.asarray(getattr(self.grid, axis), dtype=float)
        mid = 0.5 * (float(nodes[0]) + float(nodes[-1]))
        position = np.asarray(position, dtype=float)
        if walls[0] == f"{axis}min":
            return np.where(position <= mid, values, 0.0)
        return np.where(position > mid, values, 0.0)

    def _sigma_block(self, axis: str, along_mid: bool, walls=None) -> np.ndarray:
        """Sum of the active 1-D profiles on one edge/face block.

        ``walls`` (default ``None``) restricts the sum to those walls, which is
        what :meth:`sigma_for_walls` needs to price one wall group against the
        others; ``None`` is the total layer conductivity, bit for bit.
        """
        coords = _coordinates(self.grid, axis, along_mid)
        total = np.zeros(coords[0].shape, dtype=float)
        for name, pos in zip(AXES, coords):
            ends = self.walls_for(name)
            if walls is not None:
                ends = tuple(w for w in ends if w in walls)
            if not ends:
                continue
            total = total + self._wall_profile(name, pos, ends)
        return total.ravel()

    def _sigma(self, kind: str, along_mid: bool, walls=None) -> np.ndarray:
        n = self.cc.n_edges if kind == "e" else self.cc.n_faces
        out = np.zeros(n, dtype=float)
        for axis, off, count in _blocks(self.cc, kind):
            values = self._sigma_block(axis, along_mid, walls)
            if values.size != count:
                raise RuntimeError(          # pragma: no cover - layout guard
                    f"{kind}-block {axis}: sampled {values.size} values, "
                    f"expected {count}")
            out[off:off + count] = values
        return out

    def _sigma_edges(self) -> np.ndarray:
        """``sigma_e`` on the primal edges (edges are at cell centres along)."""
        return self._sigma("e", along_mid=True)

    def _sigma_faces(self) -> np.ndarray:
        """``sigma_e`` sampled on the primal faces (faces are at nodes along)."""
        return self._sigma("f", along_mid=False)

    def sigma_for_walls(self, walls, kind: str = "e") -> np.ndarray:
        """``sigma_e`` of just ``walls``, sampled like ``sigma_e``/``sigma_m``.

        ``kind="e"`` samples the primal edges, ``"f"`` the primal faces with
        their own staggering -- the same two samplings the layer itself uses,
        so a set of wall groups sums to ``sigma_e`` (or to
        ``sigma_m * eps0 / mu0``) exactly.

        A wall this layer does not open contributes nothing, which is what lets
        a caller ask for a group that is switched off and get exactly zero
        rather than an error.
        """
        names = _wall_names(walls)
        if kind not in ("e", "f"):
            raise ValueError(f"kind must be 'e' or 'f', got {kind!r}")
        n = self.cc.n_edges if kind == "e" else self.cc.n_faces
        out = np.zeros(n, dtype=float)
        for axis, off, count in _blocks(self.cc, kind):
            values = self._sigma_block(axis, kind == "e", names)
            if values.size != count:
                raise RuntimeError(          # pragma: no cover - layout guard
                    f"{kind}-block {axis}: sampled {values.size} values, "
                    f"expected {count}")
            out[off:off + count] = values
        return out

    # ------------------------------------------------------------------
    # multipliers
    # ------------------------------------------------------------------
    def multipliers(self, dt: float):
        """``(e_factor, h_factor)`` for the time step ``dt``.

        The factor is the exact decay of a constant conductivity over one
        step,

            a = exp(-sigma * dt / eps0)

        on the edges and the same expression with ``mu0`` in place of ``eps0``
        on the faces.  Both lie in ``(0, 1]``, and are exactly ``1`` wherever
        the conductivity vanishes, which is what leaves the interior
        untouched.

        The exponential is chosen over the trapezoidal
        ``(1 - s*dt/(2 eps)) / (1 + s*dt/(2 eps))`` because the grading
        formula deliberately drives ``sigma_max`` up until ``sigma*dt/(2 eps0)``
        exceeds one (the CFL limit caps ``dt`` while ``sigma_max`` grows like
        ``1/d``), and the trapezoidal factor then turns **negative**: it stays
        stable in magnitude but flips sign every step, which is a Nyquist
        oscillation rather than a decay.  ``exp`` is unconditionally
        dissipative and monotone, so the layer cannot inject energy.

        The result is cached per ``dt``; a different step rebuilds it.
        """
        dt = float(dt)
        if not np.isfinite(dt) or dt <= 0.0:
            raise ValueError(f"dt must be positive and finite, got {dt!r}")
        if self._multipliers is not None and dt == self._last_dt:
            return self._multipliers
        self._multipliers = (np.exp(-self.sigma_e * dt / EPS0),
                             np.exp(-self.sigma_m * dt / MU0))
        self._last_dt = dt
        return self._multipliers

    @property
    def e_factor(self) -> np.ndarray:
        """Edge multiplier of the current ``dt`` (raises before one is set)."""
        return self._require()[0]

    @property
    def h_factor(self) -> np.ndarray:
        """Face multiplier of the current ``dt`` (raises before one is set)."""
        return self._require()[1]

    def _require(self):
        if self._multipliers is None:
            raise RuntimeError(
                "no time step yet: call multipliers(dt) (or damp_* with a dt) "
                "before asking for the factors")
        return self._multipliers

    # ------------------------------------------------------------------
    # damping
    # ------------------------------------------------------------------
    def damp_e(self, e, dt: float = None, inplace: bool = True):
        """Apply the edge multiplier to ``e`` (``e`` at time ``n+1``)."""
        dt = self._dt(dt)
        f = self.multipliers(dt)[0]
        if self._audit is not None:
            self._audit.record("e", e, dt, self)
        if not inplace:
            return np.asarray(e, dtype=float) * f
        e *= f
        return e

    def damp_h(self, h, dt: float = None, inplace: bool = True):
        """Apply the face multiplier to ``h`` (``h`` at time ``n+1/2``)."""
        dt = self._dt(dt)
        f = self.multipliers(dt)[1]
        if self._audit is not None:
            self._audit.record("h", h, dt, self)
        if not inplace:
            return np.asarray(h, dtype=float) * f
        h *= f
        return h

    def damp(self, state, dt: float = None):
        """Damp both fields of a stepper-like ``state`` in place.

        ``state`` only needs ``.e`` and ``.h`` attributes: it is deliberately
        duck typed, so this module never imports the solver.
        """
        dt = self._dt(dt)
        self.damp_h(state.h, dt)
        self.damp_e(state.e, dt)
        return state

    def _dt(self, dt):
        if dt is None:
            if self._last_dt is None:
                raise ValueError(
                    "dt is required the first time (the multipliers depend on it)")
            return self._last_dt
        return float(dt)

    # ------------------------------------------------------------------
    def sigma_summary(self):
        """``{axis: (d, sigma_max)}`` -- for reports and tests."""
        return {name: (self.d[name], self.sigma_max[name])
                for name in self.axes}

    def __repr__(self):  # pragma: no cover - cosmetic
        parts = ", ".join(f"{name}: d={self.d[name]:.4g} m, "
                          f"sigma_max={self.sigma_max[name]:.4g} S/m"
                          for name in self.axes)
        return (f"PML(axes=({', '.join(self.axes)}), "
                f"order={self.order}, target={self.target:.1e}, {parts})")


# ----------------------------------------------------------------------
# sizing helper
# ----------------------------------------------------------------------
def cells_for_wavelength(lam0: float, h: float, target_db: float = -79.0) -> int:
    """Layer thickness (cells) worth ``target_db`` of reflection at ``lam0``.

    Empirical law for *this* discretisation (graded profile, ``order=2``,
    ``target=1e-4``), measured by the two-run difference at normal incidence:
    the reflection improves linearly in dB with thickness, from about -52 dB at
    one free-space wavelength to -79 dB at two::

        lam = 1.0 + (target_db + 52.0) / -27.0

    The law is mesh independent to within 0.6 dB between 20 and 40 points per
    wavelength, which is the range it is meant for.  The count is clipped from
    below at 8 cells, the smallest layer that still behaves like one.

    Parameters
    ----------
    lam0 : float
        Longest free-space wavelength to absorb, in metres (must be > 0).
    h : float
        Mesh cell size, in metres (must be > 0).
    target_db : float, optional
        Wanted reflection level in dB, negative; defaults to -79 dB, the
        figure measured for the 40-cell duct layer.

    Returns
    -------
    int
        Cell count to hand to ``PML(thickness_cells=...)``.
    """
    if not lam0 > 0.0:
        raise ValueError(f"lam0 must be > 0, got {lam0!r}")
    if not h > 0.0:
        raise ValueError(f"h must be > 0, got {h!r}")
    lam = 1.0 + (float(target_db) + 52.0) / -27.0
    return max(8, int(np.ceil(lam * lam0 / h)))
