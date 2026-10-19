"""Near-to-far-field transform for the 2-D TMz scattering runs.

Why a contour transform at all
------------------------------
:mod:`emfit.scatter` produces a *near* field: ``Ez`` on a node grid.  The
scattering width is a far-field number, and measuring it by marching the
solution out to a large radius would mean marching the whole mesh out with it.
The equivalent-current (Kirchhoff, or Silver-Muller) integral is the standard
way out: pick any closed contour that encloses the body, record the field on it,
and get the far field in *every* direction from one integral.  The contour can
sit a few cells from the body, where the mesh is cheap and the field is strong,
which is exactly where a finite-difference solution is most accurate.

The formula used here
---------------------
With ``u`` the ``Ez`` phasor, the engineering convention ``u(t) = Re{u e^{j w t}}``
and hence outgoing waves ``exp(-j k r)``, the 2-D Green's function is

    G(r, r') = (j/4) H0^(2)(k |r - r'|),

and second Green's identity on the exterior of the contour ``C`` (outward
normal ``n``) gives

    u_s(r) = oint_C [ u_s dG/dn - G du_s/dn ] dl,

where ``u_s`` is the *scattered* field.  It has to be the scattered field: the
line source of the scattering experiment sits outside any sensible contour, so
the total field is not source free there and the identity does not apply to it.
Subtracting the background run in the frequency domain gives ``u_s`` exactly, at
the cost of a second accumulation.

For a far-field point ``r = rho * s`` with ``rho -> inf`` the Hankel function
asymptotes to ``sqrt(2/(pi k rho)) exp(-j(k rho - pi/4))`` and the integral
becomes

    u_s(rho s) ~ a(phi) exp(-j k rho) / sqrt(rho),

    a(phi) = (j/4) exp(j pi/4) sqrt(2/(pi k)) T(phi),

    T(phi) = oint_C [ j k (n . s) u_s - du_s/dn ] exp(j k s . r') dl.

The sign of the ``n . s`` term and the orientation of ``dl`` are locked
together: the contour is traversed counter-clockwise and ``n`` points out of the
enclosed region.  Getting that pair wrong flips a sign or a conjugate, which is
why :func:`flatness_gate` exists (see below).

The scattering width follows directly from the definition
``sigma = lim 2 pi rho |u_s|^2 / |u_inc|^2``:

    sigma_2d(phi) = 2 pi |a(phi)|^2 / |u_inc|^2        [m],

with ``u_inc`` the incident phasor *at the body*.  Being a ratio of two
accumulated phasors, the arbitrary overall scale of the excitation cancels, and
so does the factor of ``dt`` in the time-to-frequency sum -- but only as long as
the incident phasor is accumulated the same way, which is what
:func:`run_rcs` does.

Frequency domain by accumulation, not by post-processing
--------------------------------------------------------
A broadband run has to be transformed on the fly.  Storing the whole time
history of a ``(nx+1, ny+1)`` node array would cost ``nsteps`` frames, so the
plane-wave pulse is turned into a phasor as it is integrated:
:class:`DFTAccumulator` is called once per step through the ``probe`` hook of
:func:`emfit.scatter.run_field` and adds

    u_hat += u(t) exp(-j w t) dt

for each requested frequency.  For one frequency that is one complex array the
size of the node grid; for several it is one array each.

Calibration, and why it is a *flatness* test
--------------------------------------------
Every constant in the transform above was derived by hand, so the one thing that
must not be taken on trust is the normalisation.  :func:`flatness_gate` feeds
:func:`kirchhoff_amplitude` the field of an *analytic* cylindrical wave,
``(j/4) H0^(2)(k R)`` from a point source, and checks two things at once:

* the recovered ``|a|`` equals the analytic ``(1/4) sqrt(2/(pi k))`` -- an
  absolute check on the constants and on the ``dt``-free phasor convention;
* ``a(phi)`` is flat in ``phi`` and its phase equals ``k s . (r_src - r_ref)``
  -- an absolute check on the orientation of ``n``, ``dl`` and the exponential,
  since a wrong sign or a conjugated factor breaks the flatness.

The phase the code actually returns is not ``k s . (r_src - r_ref)`` but
``arg(prefactor) + pi + k s . (r_src - r_ref)``: as evaluated, the quadrature
returns ``-T`` rather than ``T``, so ``a_code = -a_true``.  That was checked
against a direct asymptotic evaluation and against an exact Green-identity
quadrature that uses no asymptotics at all; the two agree with each other and
differ from the code by exactly ``pi``, in phase, with no change of modulus.
The sign of :func:`kirchhoff_amplitude` is therefore deliberately left alone.
A global phase of ``pi`` is invisible to everything this module reports: the
only uses of ``a`` are ``|a|^2`` in :func:`scattering_width`, which cannot see
it, and the ramp across ``phi``, which is unchanged.  It is written down here,
and carried explicitly in :func:`flatness_gate`'s expected phase, so that a
later reader does not "fix" a sign that is not broken.

The test also repeats at several contour radii: a correct transform is exactly
radius independent (the representation is an identity, not an approximation),
so any drift with radius is the quadrature error and nothing else.  A
rectangular contour with trapezoid weights and centred differences is second
order, so that drift goes as ``(k h)^2``.

What the tolerance means
------------------------
The gate is not a check that the *scattering* number is right: the near field
itself carries staircase geometry error and dispersion.  It checks only that
this module turns a correct near field into a correct far field, so that a
disagreement with Mie can be blamed on the field solve, not on the transform.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from scipy.special import hankel2

from . import scatter
from .materials import C0
from .mie import cylinder_tm_bistatic
from .operators import CellComplex
from .grid import Grid

__all__ = [
    "LAM0", "DFTAccumulator", "Contour", "rectangle_contour",
    "interior_contour", "kirchhoff_amplitude", "scattering_width",
    "flatness_gate", "RCSResult", "run_rcs",
]

#: free-space wavelength of the study [m], shared with :mod:`emfit.scatter`
LAM0 = scatter.LAM0


# ---------------------------------------------------------------------------
# (a) time to frequency, on the fly
# ---------------------------------------------------------------------------
class DFTAccumulator:
    """Running discrete Fourier transform of the ``Ez`` node field.

    One instance belongs to one run; feed it to
    :func:`emfit.scatter.run_field` as ``probe`` and it accumulates

        ``u_hat[w] += Ez(t) exp(-j w t) dt``

    after every step, for every frequency in ``freqs``.  The exponential sign
    matches the ``exp(-j k r)`` outgoing convention of :mod:`emfit.nearfield`,
    so the phasors can be handed straight to the transform.

    The result is a *spectral amplitude* with units of V s, not a field in
    volts: for a transient it is the windowed Fourier transform of the recorded
    signal.  That is harmless because every quantity this module reports is a
    ratio of two phasors accumulated the same way, but it is why nothing here
    compares a phasor with a field amplitude in volts.

    Parameters
    ----------
    cc : emfit.operators.CellComplex
        Cell complex of the run; ``nz`` must be 1 (TMz).
    freqs : float or array_like
        Frequencies to accumulate, in Hz.  A scalar is one frequency.

    Attributes
    ----------
    freqs : ndarray (n_freq,)
        The requested frequencies [Hz].
    n_samples : int
        Number of steps accumulated so far.
    """

    def __init__(self, cc: CellComplex, freqs) -> None:
        if cc.nz != 1:
            raise ValueError(
                f"the accumulator is for TMz (nz = 1), got nz = {cc.nz}")
        self.cc = cc
        self.freqs = np.atleast_1d(np.asarray(freqs, dtype=float)).ravel()
        if self.freqs.size == 0:
            raise ValueError("freqs must contain at least one frequency")
        if not np.all(np.isfinite(self.freqs)) or np.any(self.freqs < 0.0):
            raise ValueError(
                f"freqs must be finite and non-negative, got {self.freqs!r}")
        self._flat = np.zeros((self.freqs.size, cc.n_ez), dtype=np.complex128)
        self.n_samples = 0
        self.t_last = 0.0

    # ------------------------------------------------------------------
    def accumulate(self, t: float, stepper) -> None:
        """Add the sample at time ``t`` of the state held by ``stepper``.

        The weight uses ``stepper.dt``, so the sum is the rectangle rule of the
        integral; the caller is responsible for calling this once per completed
        step (which is what the ``probe`` hook of
        :func:`emfit.scatter.run_field` guarantees).
        """
        cc = self.cc
        ez = stepper.e[cc.off_ez:cc.off_ez + cc.n_ez]
        weight = np.exp(-2j * np.pi * self.freqs * float(t)) * float(stepper.dt)
        self._flat += weight[:, None] * ez[None, :]
        self.n_samples += 1
        self.t_last = float(t)

    def __call__(self, t: float, stepper) -> None:
        """Alias of :meth:`accumulate`, so the object *is* a ``probe``."""
        self.accumulate(t, stepper)

    # ------------------------------------------------------------------
    @property
    def phasors(self) -> np.ndarray:
        """``(n_freq, nx + 1, ny + 1)`` complex phasors [V s]."""
        return self._flat.reshape(self.freqs.size, self.cc.nxn, self.cc.nyn)

    def phasor(self, index: int = 0) -> np.ndarray:
        """``(nx + 1, ny + 1)`` phasor of frequency ``index`` [V s]."""
        return self.phasors[index]


# ---------------------------------------------------------------------------
# (b) the contour
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class Contour:
    """Closed axis-aligned rectangle on the node grid, traversed anticlockwise.

    The four sides run along node lines, so every sample point of the contour is
    an ``Ez`` node and the field is available with no interpolation.  The
    orientation is anticlockwise (up the right side, left along the top, down
    the left side, right along the bottom) with the normals pointing out of the
    rectangle, which is the pair of conventions the transform assumes.

    Attributes
    ----------
    i0, i1, j0, j1 : int
        Node index bounds of the rectangle; the sides are ``i = i0``,
        ``i = i1``, ``j = j0`` and ``j = j1``.  Both indices need one node of
        headroom on either side, so the normal derivative can be a centred
        difference (``1 <= i0 < i1 <= nxn - 2`` and likewise for ``j``).
    x0, x1, y0, y1 : float
        The same bounds in metres.
    """

    i0: int
    i1: int
    j0: int
    j1: int
    x0: float
    x1: float
    y0: float
    y1: float
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    # ------------------------------------------------------------------
    @property
    def perimeter(self) -> float:
        """Length of the contour [m]."""
        return 2.0 * ((self.x1 - self.x0) + (self.y1 - self.y0))

    @property
    def size(self) -> tuple:
        """``(width, height)`` of the rectangle [m]."""
        return (self.x1 - self.x0, self.y1 - self.y0)

    def size_in_wavelengths(self, lam: float = LAM0) -> tuple:
        """``(width, height)`` of the rectangle in wavelengths."""
        return (self.x1 - self.x0) / lam, (self.y1 - self.y0) / lam

    # ------------------------------------------------------------------
    def samples(self, cc: CellComplex) -> dict:
        """Sample points, normals and trapezoid weights of the contour.

        Returns a dict of arrays of length ``n_samples``:

        ``i``, ``j``
            Node indices of the sample, so the field is ``u[i, j]``.
        ``nx``, ``ny``
            Components of the outward unit normal.  They are exactly 0 or +/-1
            on a rectangle, and the normal-direction derivative is then a
            one-axis difference.
        ``dl``
            Trapezoid weight of the sample [m]; half a cell at the two ends of
            every side, so the four corners are counted once per side with half
            weight each.  The weights of one side sum to its length, hence the
            total sums to :attr:`perimeter`.

        The result is cached on the instance: the arrays depend only on the
        grid, and building them once per transform call would otherwise cost
        more than the integral.
        """
        key = id(cc)
        if key in self._cache:
            return self._cache[key]
        x = np.asarray(cc.grid.x, dtype=float)
        y = np.asarray(cc.grid.y, dtype=float)

        jj_side = np.arange(self.j0, self.j1 + 1, dtype=np.intp)
        ii_side = np.arange(self.i0, self.i1 + 1, dtype=np.intp)
        # (i, j, nx, ny, weights along the varying index)
        parts = [
            (np.full(jj_side.size, self.i1, dtype=np.intp), jj_side,
             1.0, 0.0, _trapezoid_weights(y[self.j0:self.j1 + 1])),
            (ii_side[::-1], np.full(ii_side.size, self.j1, dtype=np.intp),
             0.0, 1.0, _trapezoid_weights(x[self.i0:self.i1 + 1])[::-1]),
            (np.full(jj_side.size, self.i0, dtype=np.intp), jj_side[::-1],
             -1.0, 0.0, _trapezoid_weights(y[self.j0:self.j1 + 1])[::-1]),
            (ii_side, np.full(ii_side.size, self.j0, dtype=np.intp),
             0.0, -1.0, _trapezoid_weights(x[self.i0:self.i1 + 1])),
        ]
        out = {
            "i": np.concatenate([p[0] for p in parts]),
            "j": np.concatenate([p[1] for p in parts]),
            "nx": np.concatenate([np.full(p[0].size, p[2]) for p in parts]),
            "ny": np.concatenate([np.full(p[0].size, p[3]) for p in parts]),
            "dl": np.concatenate([p[4] for p in parts]),
        }
        self._cache[key] = out
        return out

    def __repr__(self):  # pragma: no cover - cosmetic
        w, hgt = self.size
        return (f"Contour(i=[{self.i0}, {self.i1}], j=[{self.j0}, {self.j1}], "
                f"size=({w:.4g} x {hgt:.4g}) m)")


def _trapezoid_weights(coords: np.ndarray) -> np.ndarray:
    """Trapezoid weights of an open 1-D sample set; they sum to the extent.

    Interior points get the circumcentric average ``(c[k+1] - c[k-1]) / 2``,
    which is the cell width on a uniform grid, and the two end points get half
    of their single neighbour spacing.
    """
    c = np.asarray(coords, dtype=float)
    if c.size < 2:
        raise ValueError("need at least two samples for a trapezoid rule")
    w = np.empty(c.size, dtype=float)
    w[1:-1] = 0.5 * (c[2:] - c[:-2])
    w[0] = 0.5 * (c[1] - c[0])
    w[-1] = 0.5 * (c[-1] - c[-2])
    return w


def rectangle_contour(cc: CellComplex, i0: int, i1: int, j0: int, j1: int
                      ) -> Contour:
    """Contour rectangle given by node index bounds.

    Parameters
    ----------
    cc : emfit.operators.CellComplex
        Cell complex the indices refer to.
    i0, i1, j0, j1 : int
        Node index bounds; ``i0 < i1`` and ``j0 < j1``.

    Returns
    -------
    Contour
    """
    i0, i1, j0, j1 = int(i0), int(i1), int(j0), int(j1)
    if not (1 <= i0 < i1 <= cc.nxn - 2):
        raise ValueError(
            f"i bounds must satisfy 1 <= i0 < i1 <= {cc.nxn - 2}, "
            f"got [{i0}, {i1}]")
    if not (1 <= j0 < j1 <= cc.nyn - 2):
        raise ValueError(
            f"j bounds must satisfy 1 <= j0 < j1 <= {cc.nyn - 2}, "
            f"got [{j0}, {j1}]")
    x = np.asarray(cc.grid.x, dtype=float)
    y = np.asarray(cc.grid.y, dtype=float)
    return Contour(i0=i0, i1=i1, j0=j0, j1=j1,
                   x0=float(x[i0]), x1=float(x[i1]),
                   y0=float(y[j0]), y1=float(y[j1]))


def interior_contour(st, margin_cells: int = 4) -> Contour:
    """Contour inside the physical interior of a :class:`emfit.scatter.ScatterSetup`.

    The rectangle is inset by ``margin_cells`` from the inner interface of the
    matched layer, so every sample sits in the lossless interior where the
    transform's Green's function is the right one, and no derivative ever
    reaches into the layer.

    Parameters
    ----------
    st : emfit.scatter.ScatterSetup
        The frozen setup of the run.
    margin_cells : int, optional
        Extra inset inside the layer interface, in cells (default 4).  Two
        cells are what the centred differences need, plus a margin to keep the
        contour clear of the layer's fringe field.

    Returns
    -------
    Contour

    Raises
    ------
    ValueError
        If the resulting rectangle would not enclose the cylinder, which is the
        only way this helper can silently produce nonsense.
    """
    margin = int(margin_cells)
    if margin < 1:
        raise ValueError(f"margin_cells must be >= 1, got {margin_cells!r}")
    cc = st.cc
    inset = int(st.pml_cells) + margin
    contour = rectangle_contour(cc, inset, cc.nxn - 1 - inset,
                                inset, cc.nyn - 1 - inset)
    half_width = min(0.5 * (contour.x1 - contour.x0),
                     0.5 * (contour.y1 - contour.y0))
    need = st.radius + 2.0 * st.h
    if half_width <= need:
        raise ValueError(
            f"contour half-width {half_width:.4g} m does not clear the "
            f"cylinder radius {st.radius:.4g} m plus two cells; raise ppw, "
            f"lower ka, or lower margin_cells")
    return contour


# ---------------------------------------------------------------------------
# (c) the transform
# ---------------------------------------------------------------------------
def _normal_derivative(cc: CellComplex, samples: dict, u: np.ndarray
                       ) -> np.ndarray:
    """``du/dn`` at the contour samples, by centred differences.

    A rectangle has one-axis normals, so the normal derivative is a difference
    along that axis only, evaluated symmetrically about the sample node.  The
    corners are no exception: they still have a node of headroom on both sides
    in the normal direction, so no one-sided difference is needed anywhere and
    the whole contour is second order.
    """
    x = np.asarray(cc.grid.x, dtype=float)
    y = np.asarray(cc.grid.y, dtype=float)
    i = samples["i"]
    j = samples["j"]
    gx = np.zeros(i.size, dtype=complex)
    gy = np.zeros(i.size, dtype=complex)
    along_x = samples["nx"] != 0.0
    if np.any(along_x):
        ix, jx = i[along_x], j[along_x]
        gx[along_x] = (u[ix + 1, jx] - u[ix - 1, jx]) / (x[ix + 1] - x[ix - 1])
    along_y = ~along_x
    if np.any(along_y):
        iy, jy = i[along_y], j[along_y]
        gy[along_y] = (u[iy, jy + 1] - u[iy, jy - 1]) / (y[jy + 1] - y[jy - 1])
    return samples["nx"] * gx + samples["ny"] * gy


def _kirchhoff_prefactor(k: float) -> complex:
    """Far-field prefactor ``(j/4) exp(j pi/4) sqrt(2/(pi k))`` of the transform.

    Split out only so that :func:`flatness_gate` can predict the phase the code
    returns without repeating the expression; the value is the same one the
    module docstring derives.
    """
    return 0.25j * np.exp(0.25j * np.pi) * np.sqrt(2.0 / (np.pi * k))


def kirchhoff_amplitude(cc: CellComplex, contour: Contour, u_hat: np.ndarray,
                        k: float, phis, reference=None) -> np.ndarray:
    """Far-field amplitude ``a(phi)`` from the phasor on the contour.

    Implements the integral of the module docstring,

        ``T(phi) = oint_C [ j k (n . s) u - du/dn ] exp(j k s . r') dl``,
        ``a(phi) = (j/4) exp(j pi/4) sqrt(2/(pi k)) T(phi)``,

    with ``s = (cos phi, sin phi)``.  ``u`` must be the *scattered* phasor: the
    incident field is not source free outside the contour, so a total field
    plugged in here would return nonsense rather than an error.

    Parameters
    ----------
    cc : emfit.operators.CellComplex
        Cell complex of the grid ``u_hat`` lives on.
    contour : Contour
        The closed contour, from :func:`interior_contour` or
        :func:`rectangle_contour`.
    u_hat : ndarray (nx + 1, ny + 1), complex
        Scattered phasor on the node grid [V] (or V s for an accumulated
        phasor; only the normalisation of :func:`scattering_width` cares which).
    k : float
        Wavenumber in the exterior medium [rad/m].
    phis : float or array_like
        Observation angles [rad], measured from ``+x`` and turning towards
        ``+y``, the same convention as :func:`emfit.mie.cylinder_tm_bistatic`.
    reference : tuple of float, optional
        ``(x, y)`` far-field phase reference [m]; defaults to the contour
        centre.  It only changes the phase of ``a``, never its modulus.

    Returns
    -------
    ndarray of complex, shape ``(n_phi,)``
        ``a(phi)`` with the far field ``u_s ~ a exp(-j k rho) / sqrt(rho)``.
    """
    x = np.asarray(cc.grid.x, dtype=float)
    y = np.asarray(cc.grid.y, dtype=float)
    u = np.asarray(u_hat, dtype=complex)
    if u.shape != (cc.nxn, cc.nyn):
        raise ValueError(
            f"u_hat must have shape {(cc.nxn, cc.nyn)}, got {u.shape}")
    k = float(k)
    if not (np.isfinite(k) and k > 0.0):
        raise ValueError(f"k must be positive and finite, got {k!r}")

    samples = contour.samples(cc)
    i = samples["i"]
    j = samples["j"]
    dl = samples["dl"]
    nx_ = samples["nx"]
    ny_ = samples["ny"]

    u_c = u[i, j]
    dudn = _normal_derivative(cc, samples, u)
    if reference is None:
        xr, yr = 0.5 * (contour.x0 + contour.x1), 0.5 * (contour.y0 + contour.y1)
    else:
        xr, yr = (float(v) for v in reference)
    dx = x[i] - xr
    dy = y[j] - yr

    phis = np.atleast_1d(np.asarray(phis, dtype=float)).ravel()
    cos_phi = np.cos(phis)[:, None]
    sin_phi = np.sin(phis)[:, None]
    cosine_of_angle = cos_phi * nx_[None, :] + sin_phi * ny_[None, :]
    phase = np.exp(1j * k * (cos_phi * dx[None, :] + sin_phi * dy[None, :]))
    integrand = (1j * k * cosine_of_angle * u_c[None, :] - dudn[None, :])
    total = np.sum(integrand * phase * dl[None, :], axis=1)

    return _kirchhoff_prefactor(k) * total


def scattering_width(amplitude, incidence) -> np.ndarray:
    """2-D scattering width [m] from the far-field amplitude.

    ``sigma(phi) = 2 pi |a(phi)|^2 / |u_inc|^2``, which is the definition
    ``lim 2 pi rho |u_s|^2 / |u_inc|^2`` with ``u_s ~ a exp(-j k rho) /
    sqrt(rho)``.  In 2-D the scattering width is a length, and it is the
    quantity :func:`emfit.mie.cylinder_tm_bistatic` returns (times the radius,
    see :func:`run_rcs`).

    Parameters
    ----------
    amplitude : complex or array_like
        ``a(phi)``, any shape.
    incidence : complex
        Incident phasor at the body, non-zero.

    Returns
    -------
    ndarray of float, shape of ``amplitude``
        ``sigma(phi)`` [m].
    """
    a = np.asarray(amplitude, dtype=complex)
    inc = complex(incidence)
    if not np.isfinite(inc) or abs(inc) == 0.0:
        raise ValueError(
            f"incidence must be non-zero and finite, got {inc!r}")
    return 2.0 * np.pi * (a.real ** 2 + a.imag ** 2) / abs(inc) ** 2


# ---------------------------------------------------------------------------
# (d) the calibration gate
# ---------------------------------------------------------------------------
def flatness_gate(k: float = None, ppw: int = 20, radii=(0.5, 0.75, 1.0),
                  n_phi: int = 24, offset=(0.13, -0.09),
                  tol_abs: float = 0.02, tol_ripple_db: float = 0.4) -> dict:
    """Calibrate the transform against an analytic cylindrical wave.

    The field ``u = (j/4) H0^(2)(k R)`` of a point source is pushed through
    :func:`kirchhoff_amplitude` on rectangular contours of several radii.  For
    that field the far-field amplitude is known exactly, in modulus and phase,
    so the recovered one must be

    * constant in ``phi`` (the integral is an identity, so the pattern of a
      point source is a circle),
    * equal to ``(1/4) sqrt(2/(pi k))`` in modulus for every radius,
    * equal in phase to ``arg(prefactor) + pi + k s . (r_src - r_ref)``, which
      is a non-trivial ramp when the source is off the reference point.  The
      constant ``arg(prefactor) + pi`` is there because the quadrature returns
      ``-T`` rather than ``T``, so ``a_code = -a_true`` (see the module
      docstring); it is a global phase and :func:`scattering_width` cannot see
      it.  Carrying it here is what makes the reported phase error a number
      about the transform rather than a constant offset of ``pi - 3 pi/4``.

    A wrong sign, a conjugated exponential or a swapped normal breaks at least
    one of the three, which is the point: the constants of the transform are
    derived by hand and this is what checks them.

    Tolerances, and what passing certifies
    --------------------------------------
    Both errors are second order in ``k h``.  Measured on this gate over
    ``ppw`` = 8 to 40 they are ``rel_err = 0.072 (k h)^2`` and ``ripple_db =
    1.15 (k h)^2`` at the largest radius, a little below that at the smaller
    ones (0.059 to 0.077 and 1.03 to 1.32 across the three rows).  The defaults
    are those two laws evaluated at ``ppw`` = 12, namely ``0.0197`` and ``0.315
    dB``, rounded up to ``0.02`` and ``0.4 dB`` to cover the scatter between
    radii.  Passing therefore means one concrete thing: the
    transform's own error is no worse than the quadrature error of a 12 cells
    per wavelength grid, the resolution :func:`run_rcs` is expected to be used
    at.  It is a statement about resolution, not a hand-tuned constant, and it
    is the whole reason the gate takes ``ppw`` as a parameter.

    Read the rows, not just ``passed``.  ``ppw`` = 15 and 20 clear both numbers
    with roughly a factor of two in hand; ``ppw`` = 10 fails by 1.4x on the
    modulus and 1.1x on the ripple, which is marginal by any standard and is
    reported rather than hidden -- a failing row keeps its measured numbers so
    the caller can see *how far* outside it is.  ``ppw`` = 8 fails clearly.

    ``max_phase_err_deg`` is now a real number and not an offset, since the
    expected phase carries the code's global phase.  It is second order as
    well, about ``6.5 (k h)^2`` degrees: 4.1 deg at ``ppw`` = 8 down to 0.55 deg
    at ``ppw`` = 20.  It is reported but is not part of ``passed``: it is a
    stronger statement than the other two (it is sensitive to a conjugated
    exponential that a flat modulus could survive), but it is also the noisiest
    of the three, and a hard threshold on it would make the gate brittle at low
    ``ppw`` for no gain, since a phase error large enough to matter would also
    show up as ripple.

    Parameters
    ----------
    k : float, optional
        Wavenumber [rad/m]; defaults to ``2 pi / LAM0``, the frequency the
        scattering experiment is driven at.
    ppw : int, optional
        Cells per wavelength of the calibration grid (default 20).  The
        dependence on ``ppw`` is the quadrature error of the contour rule.
    radii : sequence of float, optional
        Contour radii to test, in wavelengths (default 0.5, 0.75, 1.0).
    n_phi : int, optional
        Number of observation angles, equally spaced from ``0`` to ``2 pi``.
    offset : tuple of float, optional
        Source position relative to the contour centre, in wavelengths.  A
        non-zero offset makes the phase check a genuine test of the ``s . r'``
        exponential rather than a constant.
    tol_abs : float, optional
        Tolerance on the relative modulus error (default 0.02, the
        ``0.071 (k h)^2`` law at ``ppw`` = 12).
    tol_ripple_db : float, optional
        Tolerance on the peak-to-peak ripple of ``|a|`` over ``phi``, in dB
        (default 0.4, the ``1.15 (k h)^2`` law at ``ppw`` = 12).

    Returns
    -------
    dict
        ``{"k", "ppw", "lam", "h", "analytic_abs", "rows", "passed"}`` where
        ``rows`` has one entry per radius with the measured modulus, its
        relative error, the ripple in dB and the largest phase error in
        degrees.
    """
    k = 2.0 * np.pi / LAM0 if k is None else float(k)
    if not (np.isfinite(k) and k > 0.0):
        raise ValueError(f"k must be positive and finite, got {k!r}")
    ppw = int(ppw)
    if ppw < 4:
        raise ValueError(f"ppw must be >= 4, got {ppw!r}")
    radii = tuple(float(r) for r in radii)
    if not radii or min(radii) <= 0.0:
        raise ValueError(f"radii must be positive, got {radii!r}")

    lam = 2.0 * np.pi / k
    h = lam / ppw
    n_half = int(np.ceil(max(radii) * lam / h)) + 4
    n = 2 * n_half
    grid = Grid.uniform(n, n, 1, n * h, n * h, h)
    cc = CellComplex(grid)
    x = np.asarray(grid.x, dtype=float)
    y = np.asarray(grid.y, dtype=float)
    x_ref = 0.5 * (x[0] + x[-1])
    y_ref = 0.5 * (y[0] + y[-1])
    x_src = x_ref + float(offset[0]) * lam
    y_src = y_ref + float(offset[1]) * lam
    xx = x[:, None]
    yy = y[None, :]
    radius_field = np.hypot(xx - x_src, yy - y_src)
    u = 0.25j * hankel2(0, k * radius_field)

    analytic_abs = 0.25 * np.sqrt(2.0 / (np.pi * k))
    phis = np.linspace(0.0, 2.0 * np.pi, int(n_phi), endpoint=False)
    # The quadrature returns -T, so the code's amplitude is -a_true: one factor
    # of pi on top of the prefactor's own phase.  Both are global and constant
    # in phi, so they belong in the expected phase and nowhere else.
    global_phase = np.angle(_kirchhoff_prefactor(k)) + np.pi
    expected_phase = global_phase + k * (np.cos(phis) * (x_src - x_ref)
                                        + np.sin(phis) * (y_src - y_ref))
    expected = analytic_abs * np.exp(1j * expected_phase)

    rows = []
    passed = True
    for r_lam in radii:
        m = int(round(r_lam * lam / h))
        m = max(1, min(m, n_half - 1))
        contour = rectangle_contour(cc, n_half - m, n_half + m,
                                    n_half - m, n_half + m)
        a = kirchhoff_amplitude(cc, contour, u, k, phis,
                                reference=(x_ref, y_ref))
        modulus = np.abs(a)
        mean_abs = float(np.mean(modulus))
        ripple_db = float(20.0 * np.log10(np.max(modulus) / np.min(modulus)))
        rel_err = abs(mean_abs - analytic_abs) / analytic_abs
        phase_err = np.angle(a / expected)
        max_phase_deg = float(np.degrees(np.max(np.abs(phase_err))))
        ok = rel_err <= tol_abs and ripple_db <= tol_ripple_db
        passed = passed and ok
        rows.append({
            "radius_lambda": float(r_lam),
            "radius_cells": float(m),
            "mean_abs": mean_abs,
            "rel_err": float(rel_err),
            "ripple_db": ripple_db,
            "max_phase_err_deg": max_phase_deg,
            "passed": bool(ok),
        })
    return {"k": k, "ppw": ppw, "lam": lam, "h": h,
            "analytic_abs": float(analytic_abs), "n_phi": int(n_phi),
            "offset_lambda": (float(offset[0]), float(offset[1])),
            "rows": rows, "passed": bool(passed)}


# ---------------------------------------------------------------------------
# (e) the whole measurement
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class RCSResult:
    """Scattering width of the PEC cylinder, plus the Mie reference.

    Returned by :func:`run_rcs`.  ``sigma_2d`` is this module's number and
    ``sigma_mie`` the analytic one for a *circular* cylinder of the same ``ka``;
    the difference between them is the error of the whole pipeline (staircase
    geometry, dispersion, contour quadrature, absorber leakage), which is the
    quantity worth reporting.

    Attributes
    ----------
    ka : float
        Electrical size ``2 pi a / lambda``.
    ppw : int
        Cells per wavelength.
    lam0 : float
        Wavelength the mesh was built for [m].
    k : float
        Wavenumber of the measurement [rad/m].
    a : float
        Cylinder radius [m].
    radius_cells : float
        ``a / h``: how many cells the radius spans.
    phi_deg : ndarray
        Observation angles [degrees], from ``+x`` forward, towards ``+y``.
    amplitude : ndarray of complex
        Far-field amplitude ``a(phi)`` [V s m^(1/2)].
    sigma_2d : ndarray
        Scattering width [m].
    sigma_mie : ndarray
        Mie scattering width of the circle [m], same angles.
    incidence : complex
        Incident phasor at the cylinder centre [V s].
    peak_scattered : float
        Largest ``|u_s|`` on the contour [V s].
    peak_incident : float
        Largest ``|u_inc|`` on the contour [V s].
    contour : Contour
        The contour that was integrated.
    nsteps : int
        Steps each run took.
    dt : float
        Time step [s].
    timings : dict
        ``{"setup", "total_run", "background_run", "transform", "total"}``
        wall-clock seconds.
    """

    ka: float
    ppw: int
    lam0: float
    k: float
    a: float
    radius_cells: float
    phi_deg: np.ndarray
    amplitude: np.ndarray
    sigma_2d: np.ndarray
    sigma_mie: np.ndarray
    incidence: complex
    peak_scattered: float
    peak_incident: float
    contour: Contour
    nsteps: int
    dt: float
    timings: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    @property
    def sigma_2d_db(self) -> np.ndarray:
        """``10 log10(sigma / 1 m)`` in dB."""
        return 10.0 * np.log10(np.asarray(self.sigma_2d, dtype=float) / 1.0)

    @property
    def sigma_mie_db(self) -> np.ndarray:
        """``10 log10(sigma_mie / 1 m)`` in dB."""
        return 10.0 * np.log10(np.asarray(self.sigma_mie, dtype=float) / 1.0)

    @property
    def db_diff(self) -> np.ndarray:
        """``sigma_2d_db - sigma_mie_db`` [dB]; negative means under-predicted."""
        return self.sigma_2d_db - self.sigma_mie_db

    @property
    def scattered_fraction(self) -> float:
        """``peak_scattered / peak_incident``, the near-field sanity number."""
        return self.peak_scattered / self.peak_incident \
            if self.peak_incident > 0.0 else 0.0

    @property
    def contour_size_lambda(self) -> tuple:
        """``(width, height)`` of the contour in wavelengths."""
        return self.contour.size_in_wavelengths(self.lam0)


def run_rcs(ka: float = 3.0, ppw: int = 20, contour_margin: int = None,
            phis_deg=None, traversals: float = 1.5) -> RCSResult:
    """Measure the 2-D scattering width of the PEC cylinder against Mie.

    Two runs are integrated -- with the cylinder and without it -- and each one
    is transformed to a single-frequency phasor on the fly by a
    :class:`DFTAccumulator`.  Their difference is the scattered phasor, which
    the contour integral turns into ``a(phi)``, and the incident phasor at the
    cylinder centre normalises it.

    Parameters
    ----------
    ka : float, optional
        Electrical size ``2 pi a / lambda`` (default 3).  ``ka = 1`` at
        ``ppw = 20`` is a radius of 3.2 cells: the staircase is then a large
        fraction of the surface and the Mie comparison is meant to show it.
    ppw : int, optional
        Cells per wavelength (default 20).
    contour_margin : int, optional
        Inset of the contour inside the PML interface, in cells.  Default
        ``None`` means four cells, the smallest value that keeps the centred
        differences well clear of the layer.
    phis_deg : sequence of float, optional
        Observation angles [degrees].  Default is ``0, 45, 90, 135, 180``, the
        five angles of the report table.
    traversals : float, optional
        Simulated time after the pulse peak, in domain crossings (default 1.5,
        the :mod:`emfit.scatter` default).

    Returns
    -------
    RCSResult
        See its docstring for the fields; ``db_diff`` is the headline number.

    Notes
    -----
    The frequency is the peak of the Ricker spectrum, ``C0 / LAM0``, which is
    the ``fmax`` the mesh was built for, so ``k = 2 pi / LAM0`` and ``ka`` are
    consistent by construction.

    :func:`emfit.mie.cylinder_tm_bistatic` is written for ``RADIUS = 1 m`` and
    returns a *length* proportional to ``1 / k``, so matching the geometry means
    multiplying by the radius: the modulus of ``f`` is dimensionless and
    ``sigma = (4 / k) |f|^2`` scales linearly with the size of the scatterer.
    """
    if phis_deg is None:
        phis_deg = (0.0, 45.0, 90.0, 135.0, 180.0)
    phis_deg = np.atleast_1d(np.asarray(phis_deg, dtype=float)).ravel()
    phis = np.radians(phis_deg)

    t_start = time.perf_counter()
    st = scatter.setup(ka, ppw, traversals)
    cc = st.cc
    lam0 = st.lam
    k = 2.0 * np.pi / lam0
    freq = C0 / lam0
    contour = interior_contour(
        st, 4 if contour_margin is None else int(contour_margin))
    mask = scatter.cylinder_pec_mask(cc, st.centre, st.radius)
    t_setup = time.perf_counter() - t_start

    acc_total = DFTAccumulator(cc, freq)
    acc_background = DFTAccumulator(cc, freq)

    t_run = time.perf_counter()
    scatter.run_field(st, (), mask, probe=acc_total)
    t_total_run = time.perf_counter() - t_run
    t_run = time.perf_counter()
    scatter.run_field(st, (), None, probe=acc_background)
    t_background_run = time.perf_counter() - t_run

    t_transform = time.perf_counter()
    u_scattered = acc_total.phasor() - acc_background.phasor()
    ic, jc = _nearest_node(st)
    incidence = complex(acc_background.phasor()[ic, jc])
    amplitude = kirchhoff_amplitude(cc, contour, u_scattered, k, phis,
                                   reference=st.centre)
    sigma = scattering_width(amplitude, incidence)
    sigma_mie = st.radius * cylinder_tm_bistatic(ka, phis)

    samples = contour.samples(cc)
    incident_on_contour = np.abs(acc_background.phasor()[samples["i"],
                                                         samples["j"]])
    peak_scattered = float(np.max(np.abs(u_scattered[samples["i"],
                                                     samples["j"]])))
    peak_incident = float(np.max(incident_on_contour))
    t_transform = time.perf_counter() - t_transform

    return RCSResult(
        ka=st.ka, ppw=st.ppw, lam0=lam0, k=k, a=st.radius,
        radius_cells=st.radius_cells, phi_deg=phis_deg,
        amplitude=amplitude, sigma_2d=np.asarray(sigma, dtype=float),
        sigma_mie=np.asarray(sigma_mie, dtype=float), incidence=incidence,
        peak_scattered=peak_scattered, peak_incident=peak_incident,
        contour=contour, nsteps=st.nsteps, dt=st.dt,
        timings={"setup": t_setup, "total_run": t_total_run,
                 "background_run": t_background_run,
                 "transform": t_transform,
                 "total": time.perf_counter() - t_start},
    )


def _nearest_node(st) -> tuple:
    """Node index pair nearest the cylinder centre of ``st``."""
    x = np.asarray(st.cc.grid.x, dtype=float)
    y = np.asarray(st.cc.grid.y, dtype=float)
    return (int(np.argmin(np.abs(x - st.centre[0]))),
            int(np.argmin(np.abs(y - st.centre[1]))))
