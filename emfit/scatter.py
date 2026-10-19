"""2-D scattering from a PEC cylinder, by plane-wave incidence, minus background.

What the model is
-----------------
TMz polarisation on a single cell layer (``nz = 1``): the only electric
component is ``Ez``, a node quantity in this discretisation, and the PEC
structure is imposed by *pinning the ``Ez`` edges that fall inside the body to
zero*.  That is exactly the TMz boundary condition ``Ez = 0`` on a metal, and on
a Cartesian mesh the resulting body is the usual axis-aligned staircase -- not
an approximation to be apologised for, but the geometry this scheme actually
solves on.

Incidence, without a TF/SF split
-------------------------------
The incident field is launched by a **y-uniform soft line source**: a Ricker
pulse on every ``Ez`` edge of one vertical column of nodes.  The drive itself
has no ``y`` dependence and there is no cylindrical spreading to undo, so no
TF/SF injection is needed: a plane-wave-like front is what the source line
radiates, and the cylinder simply sits in it.

The front is plane-wave-*like*, not ideal, and it is worth being exact about
this because the difference is measurable.  The ``y`` direction is closed by
PEC walls behind a matched layer, and a layer damps the field that runs
*parallel* to its interface instead of letting it through, so it windows the
launched beam across ``y``.  Measured at the centre line at ``ka = 3``,
``ppw = 15``, ``|Ez|`` is flat to ``8%`` from ``0.8`` to ``3.2`` wavelengths
from the wall, ``0.58`` of the peak ``0.2`` wavelengths inside the layer
interface, and zero on the wall itself.  For a scattering number this is
harmless in the one way that matters: the taper belongs to the incident run,
which is precisely the run that is subtracted, so the scattered field is the
body response to a known illumination of finite aperture.  Dropping the ``y``
layer (``axes=("x",)``) leaves the front uniform to ``0.83`` - ``0.99`` across
the interior; that changes the incident amplitude everywhere, so it is a
choice for the caller rather than a silent default.

Along ``z`` nothing happens at all: ``nz = 1`` with ``Ez`` on the nodes and both
``z`` planes PEC leaves ``Ez`` as the only free component, which is exactly
the TMz problem.

The scattered field is then defined by subtraction::

    E_scattered = E_total - E_background

where the *background* is the identical setup with the cylinder absent.  Both
runs share the mesh, the time step, the source (the same ``RickerSource``
object, evaluated at the same times), the PML and the PEC walls, so every
artefact of the setup -- the incident pulse shape, the discretisation error of
the source line, the residual reflection of the layer -- cancels exactly in the
difference.  With the mask empty the two runs are *bit-identical* and the
subtracted field is exactly zero (this is asserted in the tests); with a real
cylinder the only surviving term is the field the body itself radiates.

Units and resolution
--------------------
Everything is scaled to ``LAM0 = 1 m``: the domain is ``6`` wavelengths across,
the PML is ``1`` wavelength thick (about -52 dB, measured), leaving ``4``
wavelengths of interior, and ``ppw`` cells per wavelength sets the mesh.  The
cylinder radius is ``a = ka / (2 pi)`` wavelengths, i.e. ``ka * ppw / (2 pi)``
cells -- at ``ka = 1`` and ``ppw = 20`` that is only 3.2 cells, so the small
cylinder is deliberately under-resolved.  That is a result to report, not a bug
to hide: the staircase of a 3-cell-radius disc is a large fraction of its
surface, and the scattering cross-section error that follows is a property of
the mesh, not of the absorber.

Usage
-----
The whole experiment is one call::

    from emfit import scatter

    res = scatter.run_scatter(ka=3.0, ppw=20)
    res.ez_scattered        # E_total - E_background, (nx + 1, ny + 1)
    res.n_pec_edges, res.radius_cells, res.timings

The pieces underneath (:func:`setup`, :func:`run_field`, :func:`run_pair`,
:func:`background_subtract`) are public too, so a caller that wants several
instants from one pair of runs pays for the integration once.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .evolve import FITStepper, RickerSource, cfl_dt
from .grid import Grid
from .materials import C0, material_matrices
from .operators import CellComplex
from .pml import PML

__all__ = [
    "LAM0", "N_LAMBDA", "PML_LAMBDA", "SRC_INSET",
    "ScatterSetup", "ScatterRun", "ScatterResult",
    "setup", "cylinder_pec_mask", "y_uniform_line_edges", "line_source",
    "nsteps_for_traversals", "frame_indices", "run_field", "run_pair",
    "background_subtract", "run_scatter", "ez_slice",
]

#: free-space wavelength at ``fmax``; sets the length unit of the whole study
LAM0 = 1.0
#: domain side, in wavelengths
N_LAMBDA = 6.0
#: matched-layer thickness, in wavelengths (~ -52 dB at normal incidence)
PML_LAMBDA = 1.0
#: distance from the left PML interface to the source line, in wavelengths
SRC_INSET = 0.5

#: walls that are always PEC: behind the layer on all four sides, plus the two
#: ``z`` planes, which is what reduces the 3-D scheme to 2-D TMz (it pins ``Ex``
#: and ``Ey``, the in-plane components, on both z planes).
WALLS = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")


# ---------------------------------------------------------------------------
# the Ez node array: the only field view this module needs
# ---------------------------------------------------------------------------
def ez_slice(cc: CellComplex, e) -> np.ndarray:
    """``(nx + 1, ny + 1)`` array of ``Ez`` from a flat edge vector.

    ``Ez`` edges are the third block of the primal edge vector and, with
    ``nz = 1``, one per ``(i, j)`` node pair -- so the slice is just that block
    reshaped.  Copied, so a snapshot survives the next time step.
    """
    vals = np.asarray(e, dtype=float).ravel()
    if vals.size != cc.n_edges:
        raise ValueError(
            f"e must have {cc.n_edges} entries (one per primal edge), "
            f"got {vals.size}")
    block = vals[cc.off_ez:cc.off_ez + cc.n_ez]
    return block.reshape(cc.nxn, cc.nyn, cc.nz)[:, :, 0].copy()


# ---------------------------------------------------------------------------
# (a) the scatterer: a PEC cylinder as a pinned-edge mask
# ---------------------------------------------------------------------------
def cylinder_pec_mask(cc: CellComplex, centre, radius: float) -> np.ndarray:
    """Boolean mask (length ``cc.n_edges``) of the ``Ez`` edges inside a disc.

    Built from **edge coordinates**, not index arithmetic: an ``Ez`` edge spans
    the nodes either side of the cell in ``x`` and ``y``, so both of its
    endpoints sit on the node grid and the midpoint of the edge is the node
    ``(x[i], y[j])``.  The test is therefore the continuum one,
    ``(x - cx)**2 + (y - cy)**2 <= radius**2``, evaluated in metres on every
    node at once.  Because the grid is staggered, index arithmetic (an integer
    radius loop over ``i - ic``, ``j - jc``) is simply wrong here: the node
    coordinates of a graded grid are not equally spaced, and even on a uniform
    grid the node offset from the centre is not an integer.

    Edges flagged ``True`` are pinned to zero voltage by the stepper after every
    update, which is the PEC condition ``Ez = 0`` inside the body; on this
    Cartesian mesh the resulting boundary is an axis-aligned staircase.

    Parameters
    ----------
    cc : emfit.operators.CellComplex
        Cell complex of the grid the run uses.
    centre : tuple of float, or None
        ``(x, y)`` centre in metres.  ``None`` means the domain centre.
    radius : float
        Cylinder radius in metres.  ``<= 0`` returns an **empty** mask (a node
        exactly at the centre would otherwise pin one edge), which is a
        convenient way to spell "no scatterer" without a second code path.

    Returns
    -------
    ndarray of bool, shape ``(cc.n_edges,)``
        Only the ``Ez`` block can be ``True``.
    """
    mask = np.zeros(cc.n_edges, dtype=bool)
    if not radius > 0.0:
        return mask
    x = np.asarray(cc.grid.x, dtype=float)
    y = np.asarray(cc.grid.y, dtype=float)
    if centre is None:
        xc, yc = 0.5 * (x[0] + x[-1]), 0.5 * (y[0] + y[-1])
    else:
        xc, yc = (float(v) for v in centre)
    i, j, k = np.indices(cc.grid.edge_shape("z"))
    inside = (x[i] - xc) ** 2 + (y[j] - yc) ** 2 <= radius * radius
    mask[cc.idx_ez(i, j, k)] = inside
    return mask


# ---------------------------------------------------------------------------
# (b) the source: a y-uniform soft line with a Ricker pulse
# ---------------------------------------------------------------------------
def y_uniform_line_edges(cc: CellComplex, x0: float):
    """``Ez`` edge indices of the node column nearest ``x0``, plus its index.

    The whole column is one edge set, so driving it with the same current on
    every ``y`` launches a field with no ``y`` dependence at all: in this
    discretisation that is a plane wave travelling in ``+x``, not an
    approximation to one.
    """
    x = np.asarray(cc.grid.x, dtype=float)
    i = int(np.argmin(np.abs(x - x0)))
    j = np.arange(cc.nyn, dtype=np.intp)
    return np.asarray(cc.idx_ez(i, j, 0), dtype=np.intp), i


def line_source(cc: CellComplex, x0: float, fmax: float, t0: float = None,
                amplitude: float = 1.0) -> RickerSource:
    """Soft y-uniform line source: a Ricker pulse on one node column.

    Reuses :class:`emfit.evolve.RickerSource` -- the same wavelet and the same
    soft-current convention as the cavity study, so there is only ever one
    source convention in the codebase.  The driving amplitude is the normalised
    knob it is everywhere else: ``amplitude = 1`` and the resulting ``Ez``
    amplitudes are whatever the FIT system produces.
    """
    idx, _ = y_uniform_line_edges(cc, x0)
    return RickerSource(cc.n_edges, idx, fmax=fmax, t0=t0, amplitude=amplitude)


# ---------------------------------------------------------------------------
# the setup: one frozen description, shared by both runs of the pair
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class ScatterSetup:
    """Mesh, source, absorber and scatterer of one scattering experiment.

    Built by :func:`setup`.  Both members of a pair are run from *this* object,
    which is what makes the background subtraction exact: there is no second
    copy of the mesh or the source to drift.
    """

    ka: float
    ppw: int
    lam: float
    h: float
    lx: float
    ly: float
    radius: float
    centre: tuple
    x_src: float
    fmax: float
    t0: float
    dt: float
    nsteps: int
    grid: Grid
    cc: CellComplex
    m_eps: np.ndarray
    m_mu: np.ndarray
    pml: PML
    source: RickerSource
    walls: tuple = WALLS

    # -- derived quantities used by the figures and the metrics --------------
    @property
    def radius_cells(self) -> float:
        """Radius in cells -- ``ka * ppw / (2 pi)``."""
        return self.radius / self.h

    @property
    def cells_across(self) -> float:
        """Cells across the radius; below ~5 the staircase is coarse."""
        return self.radius_cells

    @property
    def pml_cells(self) -> int:
        return int(round(PML_LAMBDA * self.lam / self.h))

    @property
    def interior_cells(self) -> int:
        return self.cc.nx - 2 * self.pml_cells

    def snapshot_step(self, delay: float) -> int:
        """Step index at which the pulse peak has travelled ``delay`` seconds."""
        return int(np.clip(round((self.t0 + delay) / self.dt), 0, self.nsteps))


def setup(ka: float = 3.0, ppw: int = 20, traversals: float = 1.5) -> ScatterSetup:
    """Build the mesh, layer, source and cylinder for ``(ka, ppw)``.

    Args:
        ka: electrical size ``2 pi a / lambda``.  ``1`` is deliberately
            under-resolved at these ``ppw`` (3 cells of radius) and is kept as
            a parameter precisely so that the failure is visible.
        ppw: cells per wavelength at ``fmax``; the domain is ``6 ppw`` cells
            square and the layer is ``ppw`` cells thick.
        traversals: simulated time, in domain crossings, after the pulse peak.

    Returns:
        :class:`ScatterSetup`.
    """
    ka = float(ka)
    ppw = int(ppw)
    if ka <= 0.0:
        raise ValueError(f"ka must be > 0, got {ka!r}")
    if ppw < 4:
        raise ValueError(f"ppw must be >= 4, got {ppw!r}")

    lam = LAM0
    h = lam / ppw
    lx = ly = N_LAMBDA * lam
    nx = ny = int(round(lx / h))
    grid = Grid.uniform(nx, ny, 1, lx, ly, h)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)

    pml = PML(grid, thickness_cells=int(round(PML_LAMBDA / h)), order=2,
              target=1e-4, axes=("x", "y"), cc=cc)

    fmax = C0 / lam
    t0 = 1.0 / fmax
    x_src = PML_LAMBDA * lam + SRC_INSET * lam
    radius = ka * lam / (2.0 * np.pi)
    dt = cfl_dt(grid)
    nsteps = nsteps_for_traversals(t0, dt, float(np.hypot(lx, ly)), traversals)
    return ScatterSetup(
        ka=ka, ppw=ppw, lam=lam, h=h, lx=lx, ly=ly, radius=radius,
        centre=(0.5 * lx, 0.5 * ly), x_src=x_src, fmax=fmax, t0=t0, dt=dt,
        nsteps=nsteps, grid=grid, cc=cc, m_eps=m_eps, m_mu=m_mu, pml=pml,
        source=line_source(cc, x_src, fmax, t0=t0))


def nsteps_for_traversals(t0: float, dt: float, length: float,
                          traversals: float = 1.5) -> int:
    """Steps needed to simulate ``traversals`` crossings of ``length`` after the
    pulse peak.

    ``length`` is the domain diagonal in metres: the pulse has to reach the
    cylinder, cross it, and put its shadow on the far side, all before the run
    stops.  ``t0`` is added because the wavelet itself starts at ``t = t0``.
    """
    return int(np.ceil((t0 + traversals * length / C0) / dt))


def frame_indices(st: ScatterSetup, delays) -> np.ndarray:
    """Step indices for snapshot ``delays`` (seconds after the pulse peak)."""
    return np.unique(np.array([st.snapshot_step(float(d)) for d in delays],
                              dtype=np.intp))


# ---------------------------------------------------------------------------
# (c) the pair of runs
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class ScatterRun:
    """``Ez`` snapshots of one run, on the node grid."""

    times: np.ndarray        # (n_frames,) seconds
    frames: np.ndarray       # (n_frames, nx + 1, ny + 1) volts
    nsteps: int
    pec_edges: int

    @property
    def peak(self) -> float:
        return float(np.max(np.abs(self.frames))) if self.frames.size else 0.0


def run_field(st: ScatterSetup, frames, mask=None, probe=None) -> ScatterRun:
    """Integrate one member of the pair, keeping ``Ez`` at step ``frames``.

    ``mask`` is a PEC mask from :func:`cylinder_pec_mask` (``None`` = no
    scatterer).  Everything else -- grid, ``dt``, source object, layer, walls --
    comes from ``st``, so the two members of a pair differ only by the mask.
    ``probe`` is a callable ``probe(time, stepper)`` invoked after every
    completed step; the default ``None`` leaves the result bit-identical.
    """
    frames_idx = np.asarray(frames, dtype=np.intp)
    pec = st.cc.pec_edge_mask(st.walls)
    if mask is not None:
        pec = pec | mask
    stepper = FITStepper(st.cc, st.m_eps, st.m_mu, dt=st.dt, pec=pec, pml=st.pml)

    wanted = {int(k): n for n, k in enumerate(frames_idx)}
    out = np.empty((len(wanted), st.cc.nxn, st.cc.nyn))
    times = np.empty(len(wanted))
    for n in range(st.nsteps):
        stepper.step(st.source(stepper.time))
        if probe is not None:
            probe(stepper.time, stepper)
        slot = wanted.get(n)
        if slot is not None:
            out[slot] = ez_slice(st.cc, stepper.e)
            times[slot] = stepper.dt * (n + 1)
    return ScatterRun(times=times, frames=out, nsteps=st.nsteps,
                      pec_edges=int(pec.sum()))


def run_pair(st: ScatterSetup, frames=None, mask=None):
    """Run the cylinder and the background; return ``(total, background)``.

    The returned pair is what :func:`background_subtract` expects.  ``frames``
    defaults to the money frame -- the instant the pulse peak is over the
    cylinder centre -- and ``mask`` to the cylinder mask of ``st``.
    """
    if frames is None:
        frames = frame_indices(st, [(st.centre[0] - st.x_src) / C0])
    if mask is None:
        mask = cylinder_pec_mask(st.cc, st.centre, st.radius)
    total = run_field(st, frames, mask)
    background = run_field(st, frames, None)
    return total, background


# ---------------------------------------------------------------------------
# (d) the subtraction
# ---------------------------------------------------------------------------
def background_subtract(total, background):
    """``total - background`` elementwise, shapes must match exactly.

    Accepts either one snapshot ``(nx+1, ny+1)`` or a stack
    ``(n_frames, nx+1, ny+1)``.  This *is* the definition of the scattered
    field here -- there is no approximate decomposition hiding behind it.
    """
    a = np.asarray(total, dtype=float)
    b = np.asarray(background, dtype=float)
    if a.shape != b.shape:
        raise ValueError(
            f"total and background must have the same shape, "
            f"got {a.shape} and {b.shape}")
    return a - b


# ---------------------------------------------------------------------------
# (e) the whole experiment in one call
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class ScatterResult:
    """Fields and metadata of one scattering experiment, ready to plot.

    Returned by :func:`run_scatter`.  ``ez_total`` and ``ez_background`` are the
    ``Ez`` node arrays of the two members of the pair and ``ez_scattered`` is
    their difference, which *is* the field the body radiates.  Each array is
    ``(nx + 1, ny + 1)`` for a single snapshot and
    ``(n_frames, nx + 1, ny + 1)`` when several delays were requested.

    Attributes
    ----------
    ez_total, ez_background, ez_scattered : ndarray
        ``Ez`` [V] on the node grid; the first index is ``x``, the second
        ``y``.
    cc : emfit.operators.CellComplex
        The cell complex both runs used.
    mask : ndarray of bool
        The PEC mask handed to the total run: ``True`` on the ``Ez`` edges of
        the cylinder.
    ka : float
        Electrical size ``2 pi a / lambda``.
    ppw : int
        Cells per wavelength.
    lam0 : float
        Wavelength the mesh was built for [m].
    a : float
        Cylinder radius [m].
    radius_cells : float
        ``a / h``: how many cells the radius spans.
    n_pec_edges : int
        Number of ``Ez`` edges pinned by the cylinder itself (the PEC walls are
        counted separately by the stepper).
    nsteps : int
        Steps each run took.
    dt : float
        Time step [s].
    times : ndarray
        Simulation time of each stored snapshot [s].
    timings : dict
        ``{"setup", "run", "total"}`` wall-clock seconds.
    setup : ScatterSetup
        The frozen description, for callers that want to run further frames.
    """

    ez_total: np.ndarray
    ez_background: np.ndarray
    ez_scattered: np.ndarray
    cc: CellComplex
    mask: np.ndarray
    ka: float
    ppw: int
    lam0: float
    a: float
    radius_cells: float
    n_pec_edges: int
    nsteps: int
    dt: float
    times: np.ndarray
    setup: ScatterSetup
    timings: dict = field(default_factory=dict)

    @property
    def peak_total(self) -> float:
        """Largest ``|Ez|`` of the run with the cylinder present."""
        return float(np.max(np.abs(self.ez_total)))

    @property
    def peak_background(self) -> float:
        """Largest ``|Ez|`` of the run with the cylinder absent."""
        return float(np.max(np.abs(self.ez_background)))

    @property
    def peak_scattered(self) -> float:
        """Largest ``|Ez_scattered|``, i.e. the size of the body response."""
        return float(np.max(np.abs(self.ez_scattered)))

    @property
    def scattered_fraction(self) -> float:
        """``peak_scattered / peak_background``; zero if the pair cancels."""
        peak = self.peak_background
        return self.peak_scattered / peak if peak > 0.0 else 0.0


def run_scatter(ka: float = 3.0, ppw: int = 20, traversals: float = 1.5,
                delays=None) -> ScatterResult:
    """Run the cylinder/background pair and return fields plus metrics.

    Parameters
    ----------
    ka : float, optional
        Electrical size ``2 pi a / lambda`` (default 3).
    ppw : int, optional
        Cells per wavelength at ``fmax`` (default 20).
    traversals : float, optional
        Simulated time after the pulse peak, in domain crossings (default 1.5).
    delays : sequence of float, optional
        Snapshot times after the pulse peak [s].  Default is the single *money
        frame*: the instant the pulse peak is over the cylinder centre.

    Returns
    -------
    ScatterResult
        ``ez_total``, ``ez_background``, ``ez_scattered`` and the metadata
        listed in its docstring.

    Notes
    -----
    The two runs share the mesh, the time step, the source object, the layer
    and the walls, and differ only by the PEC mask, so ``ez_scattered`` is the
    body response and nothing else.
    """
    t_start = time.perf_counter()
    st = setup(ka, ppw, traversals)
    t_setup = time.perf_counter() - t_start

    if delays is None:
        delays = [(st.centre[0] - st.x_src) / C0]
    frames = frame_indices(st, delays)

    t_run = time.perf_counter()
    mask = cylinder_pec_mask(st.cc, st.centre, st.radius)
    total, background = run_pair(st, frames, mask)
    t_run = time.perf_counter() - t_run

    scattered = background_subtract(total.frames, background.frames)
    if total.frames.shape[0] == 1:
        # one instant: drop the frame axis so the arrays are plain images
        ez_total = total.frames[0]
        ez_background = background.frames[0]
        ez_scattered = scattered[0]
    else:
        ez_total, ez_background, ez_scattered = (total.frames,
                                                background.frames, scattered)

    return ScatterResult(
        ez_total=ez_total, ez_background=ez_background,
        ez_scattered=ez_scattered, cc=st.cc, mask=mask, ka=st.ka, ppw=st.ppw,
        lam0=st.lam, a=st.radius, radius_cells=st.radius_cells,
        n_pec_edges=int(mask.sum()), nsteps=st.nsteps, dt=st.dt,
        times=total.times,
        timings={"setup": t_setup, "run": t_run,
                 "total": time.perf_counter() - t_start},
        setup=st)
