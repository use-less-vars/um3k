"""Tangential near fields on a conformed Huygens surface, recorded in the time loop.

What this module is
-------------------
:mod:`emfit.huygens` answers *where* the field components a near-to-far-field
transform needs live on the FIT Yee complex: :class:`~emfit.huygens.HuygensBounds`
is the box a caller asks for, and :meth:`~emfit.huygens.HuygensBounds.conform_to`
returns a :class:`~emfit.huygens.SurfaceSamples` carrying, per sample point, the
outward normal, the box face, and the flat ``e``/``h`` indices to read.

This module is the two pieces that turn that geometry into numbers:

* :func:`surface_areas` -- the area of the primal face each sample sits on, read
  off the grid metric (so it is exact for the mesh, and needs no formula of its
  own);
* :class:`SurfaceRecorder` -- a callback for
  :meth:`emfit.evolve.FITStepper.run` that accumulates the tangential ``E`` and
  ``H`` at every sample, at a set of frequencies, into spectral phasors.

It is deliberately the same kind of object as
:class:`emfit.nearfield.DFTAccumulator`: the same ``exp(-j w t)`` sign
convention, the same ``dt`` weighting, the same ``accumulate(t, stepper)`` /
``__call__`` calling forms.  The difference is the reduction axis -- a box
surface of arbitrary orientation rather than a fixed plane cut -- and the fact
that the magnetic field needs a second state of the recorder to be sampled *at
the same instant* as the electric one (see below).

Units
-----
Each spectral entry is a plain running sum of ``field * dt * exp(-j w t)``, not
divided by the number of samples and not normalised by anything.  For an ``E``
field in V/m and a time step in seconds the entries are therefore in ``V s / m``
(after multiplication by the face area, ``V s``, i.e. a spectral flux); the
``H`` entries are in ``A s / m`` and ``A s``.  That is the convention a
downstream transform wants: an impedance or energy ratio formed from them is
independent of the weighting, while a spectrum that has to be scaled to a source
amplitude is scaled once, at the end, by the caller.

Why E is co-located and H is not
--------------------------------
The two gathers are not equally accurate, and the asymmetry is a property of the
staggering, not of this code.

* ``E``: the two bounding edges of a sample's primal face are one cell apart and
  the sample sits exactly halfway between them -- ``(a[j] + a[j+1]) / 2``, which
  *is* the cell centre by definition.  The pair average is therefore
  **position exact** on any grid, uniform or graded, and the only error is the
  curvature of the tangential ``E`` across one cell.
* ``H``: four primal faces per tangential component.  The **transverse** factor
  is again a midpoint of two nodes straddling a cell centre, so it is position
  exact on any grid.  The **normal** pair straddles the sample's node plane and
  its members sit at cell centres half a cell to either side: exact up to
  curvature (``O(h^2)``) on a **uniform** grid, but on a **graded** mesh the two
  half widths differ, the midpoint lands ``(h_+ - h_-) / 4`` off the plane, and
  the error is ``O(h)``.  Nothing here corrects that: the caveat
  :mod:`emfit.huygens` states for the geometry applies unchanged to the value
  recorded on it.  A one-sided ``H`` sample (a stencil clamped at the domain
  boundary, where the pair degenerates to the same face twice) is likewise the
  value at the neighbouring cell centre, half a cell away, and is first order
  for that reason.

Why the recorder is a state machine
-----------------------------------
The leapfrog stepper advances in two half steps: after step ``k`` the electric
field sits at ``t = k dt`` and the magnetic field at ``t = (k - 1/2) dt``.  So
the ``H`` available at the instant the ``E`` is correct is half a step stale,
and pairing them naively gives the phasor of ``H`` a phase error of
``w dt / 2`` -- first order in the time step, which is a real error in an
impedance, not a real scale factor.

The fix is to keep the previous magnetic field and average it with the current
one, ``(h[(k-3/2) dt] + h[(k-1/2) dt]) / 2``.  That midpoint is the magnetic field
at ``t = (k-1) dt`` to ``O(dt^2)``, i.e. at the instant of the *previous* call's
electric field -- which is why the recorder emits its sample when it is called
the second time and later, using the electric field it was given last time
together with that midpoint.  For a single-frequency phasor the average is
``cos(w dt / 2)`` times the value at ``(k-1) dt``: **no phase error at all**, only
a real factor ``1 - (w dt)^2 / 8``, second order (and a uniform scale in ``w dt``,
so a ratio of an ``H`` entry to an ``E`` entry carries it at ``O(dt^2)`` too).
The factor is *divided out* by :attr:`SurfaceRecorder.H_t` by default
(``debias=True``), because at a recorded frequency it is an exact, known number
and leaving it in biases ``H`` low -- by ``1 - cos(pi f dt)``, which is 4.5e-4
(0.045 % in amplitude, 0.090 % in power) at 5 GHz on a 1 mm cell.  It is only
safe while ``pi f dt`` is small: the division amplifies whatever else the sum
carries, so a broadband record, or a step coarse enough that ``pi f dt`` is not
small, wants the raw sum instead (:attr:`SurfaceRecorder.H_t_raw`, or
``debias=False``).

The consequence to keep in mind: ``K`` calls of the callback produce ``K - 1``
samples, at ``t = dt, 2 dt, ..., (K-1) dt``.  The trailing rectangle rule is used,
matching :class:`emfit.nearfield.DFTAccumulator`.

What it does not do
-------------------
No far-field transform, no incident-field subtraction, no equivalence-surface
weights, no apodisation -- this module records the fields, and the transform that
consumes them lives elsewhere.  It also never writes to the stepper: both gathers
are indexed reads of ``stepper.e`` and ``stepper.h``, so a record made inside the
time loop cannot perturb the simulation being measured.  Pass an instance as
``callback=`` to :meth:`emfit.evolve.FITStepper.run` and read :attr:`E_t` /
:attr:`H_t` afterwards.
"""

from __future__ import annotations

import numpy as np

from .huygens import HuygensBounds, SurfaceSamples

__all__ = ["SurfaceRecorder", "surface_areas"]


def surface_areas(cc, samples):
    """Metric area of the primal face each sample point sits on.

    The area is read off the grid (:meth:`emfit.grid.Grid.face_area_x` and its
    siblings), so it is the mesh's own area -- exact for a graded mesh, and
    consistent with whatever :func:`emfit.materials.material_matrices` used to
    build the same faces.

    Parameters
    ----------
    cc : emfit.operators.CellComplex
        The complex the samples were conformed against; supplies the per-block
        offsets and the grid metric.
    samples : SurfaceSamples
        The conformed surface.

    Returns
    -------
    (N,) float64
        Face areas in square metres, ordered as ``samples.coordinates``.  An
        empty surface gives an empty array rather than an error, so a caller
        can ask before it has a box.

    Raises
    ------
    ValueError
        If a sample's slot for its own (normal) orientation holds a ``-1``,
        i.e. the array does not agree with ``face_id`` about which block the
        sample belongs to.
    """
    grid = cc.grid
    face_id = np.asarray(samples.face_id, dtype=np.intp)
    block = face_id // 2
    n = face_id.size
    areas = np.zeros(n, dtype=float)
    if n == 0:
        return areas
    live = np.asarray(samples.face_index, dtype=np.intp)
    for axis, name in enumerate("xyz"):
        sel = block == axis
        if not np.any(sel):
            continue
        flat = live[sel, axis]
        if np.any(flat < 0):
            raise ValueError(
                f"face_index: a sample on a {name}-normal box face has no "
                f"{name.upper()} slot, so its area is undefined; face_id and "
                f"face_index disagree")
        off = getattr(cc, f"off_f{name}")
        ijk = np.unravel_index(flat - off, grid.face_shape(name))
        areas[sel] = getattr(grid, f"face_area_{name}")()[ijk]
    return areas


class SurfaceRecorder:
    """Accumulate the tangential ``E`` and ``H`` on a Huygens surface.

    A probe for :meth:`emfit.evolve.FITStepper.run`::

        recorder = SurfaceRecorder(bounds, freqs, cc=cc)
        stepper.run(nsteps, callback=recorder)
        e_spectrum, h_spectrum = recorder.E_t, recorder.H_t

    Parameters
    ----------
    surface : HuygensBounds or SurfaceSamples
        The box to record, either as a request in metres (conformed against
        ``cc`` here, through :meth:`HuygensBounds.conform_to`) or already
        conformed.
    freqs : float or (n_freq,) float
        Frequencies in hertz.  Must be finite and strictly positive: a phasor
        is defined by a frequency, and a zero or negative one is a mistake
        upstream rather than a degenerate request.
    cc : emfit.operators.CellComplex, optional
        Required -- the face metric is needed for :attr:`face_areas`, and the
        conformed indices only mean something against the complex they were
        built for.  Passed explicitly rather than taken from the first stepper
        the recorder sees, so a mis-paired stepper is a loud error instead of a
        silently wrong gather.
    debias : bool, optional
        Divide the ``H`` phasors by the real factor ``cos(pi f dt)`` that the
        half-step midpoint average leaves in them (default ``True``); see
        :attr:`H_t`.  ``False`` -- or :attr:`H_t_raw` -- gives the raw running
        sum, which is what a broadband record wants.

    Attributes
    ----------
    cc : emfit.operators.CellComplex
    samples : SurfaceSamples
        The conformed surface recorded from.
    freqs : (n_freq,) float64
    coordinates, normals, face_id, face_index : array
        Shorthands for the matching :class:`SurfaceSamples` arrays.
    face_areas : (N,) float64
        From :func:`surface_areas`.
    n_surface : int
        Number of sample points ``N``.
    n_samples : int
        Number of spectral samples accumulated so far (``K - 1`` after ``K``
        calls).
    t_last : float
        Time of the most recent accumulated sample, in seconds; ``nan`` before
        the first one.
    debias : bool
        Whether :attr:`H_t` divides out ``cos(pi f dt)``.

    Raises
    ------
    TypeError
        If ``surface`` is neither :class:`HuygensBounds` nor
        :class:`SurfaceSamples`.
    ValueError
        If ``cc`` is missing, if ``freqs`` is empty or not finite and positive,
        or if the surface has no samples.
    """

    def __init__(self, surface, freqs, cc=None, *, debias=True):
        if isinstance(surface, HuygensBounds):
            if cc is None:
                raise ValueError(
                    "cc: a HuygensBounds is a request in metres and can only "
                    "be conformed against a cell complex; pass cc=CellComplex("
                    "grid) (or a pre-conformed SurfaceSamples instead)")
            samples = surface.conform_to(cc)
        elif isinstance(surface, SurfaceSamples):
            samples = surface
        else:
            raise TypeError(
                "surface: expected HuygensBounds or SurfaceSamples, got "
                f"{type(surface).__name__}")
        if cc is None:
            raise ValueError(
                "cc: the face metric of the complex the surface was conformed "
                "against is needed for face_areas; pass cc=...")
        freqs = np.atleast_1d(np.asarray(freqs, dtype=float)).ravel()
        if freqs.size == 0:
            raise ValueError("freqs: at least one frequency is required")
        if not np.all(np.isfinite(freqs)) or np.any(freqs <= 0.0):
            raise ValueError(
                f"freqs: must be finite and positive, got {freqs!r}")
        n_surface = int(np.asarray(samples.face_id).size)
        if n_surface == 0:
            raise ValueError(
                "surface: the conformed surface has no samples, so there is "
                "nothing to record")

        self.cc = cc
        self.samples = samples
        self.freqs = freqs
        self.coordinates = samples.coordinates
        self.normals = samples.normals
        self.face_id = samples.face_id
        self.face_index = samples.face_index
        self.face_areas = surface_areas(cc, samples)
        self.n_surface = n_surface
        self.debias = bool(debias)

        self._e_idx = np.asarray(samples.edge_index, dtype=np.intp)
        self._h_idx = np.asarray(samples.h_face_index, dtype=np.intp)
        self._e_flat = np.zeros((freqs.size, n_surface, 2), dtype=np.complex128)
        self._h_flat = np.zeros((freqs.size, n_surface, 2), dtype=np.complex128)
        self.n_samples = 0
        self.t_last = float("nan")
        self._prev_e = None
        self._prev_h = None
        self._t_prev = None
        self._h_scale = None

    # ---------------------------------------------------------------- views

    @property
    def E_t(self):
        """Tangential ``E`` phasors, ``(n_freq, N, 2)`` complex128.

        Slot 0 is the first tangential component, slot 1 the second, in
        ascending axis order excluding the sample normal -- the order
        :attr:`SurfaceSamples.edge_index` uses (``E_y, E_z`` on an x-normal box
        face, ``E_x, E_z`` on a y-normal one, ``E_x, E_y`` on a z-normal one).
        Entries are in ``V s / m``: sums of ``E * dt * exp(-j w t)``, neither
        normalised nor phase corrected.  A copy, so a caller cannot corrupt the
        running sum by editing what it reads.
        """
        return self._e_flat.copy()

    @property
    def H_t(self):
        """Tangential ``H`` phasors, ``(n_freq, N, 2)`` complex128.

        Same slot order as :attr:`E_t`.  Each entry is a sum of
        ``H * dt * exp(-j w t)`` at the instant of the matching ``E`` sample
        (the half-step midpoint average, see the module docstring), which
        leaves the real factor ``cos(pi f dt)`` in it; with ``debias`` set (the
        default) that factor is divided out, so the entry is the phasor the
        field has at the sample instant.  With ``debias=False`` the raw sum is
        returned, exactly as :attr:`H_t_raw` always does.  In ``A s / m``.

        The division is exact for a tone at a frequency in ``freqs`` and
        meaningless for a broadband signal, where no single ``f`` owns the
        factor -- record raw and leave it to whatever forms the ratio.  On a
        CFL-limited step it is small: a 1 mm cell gives ``dt = 1.907e-12 s``, so
        at 5 GHz ``pi f dt = 0.0299`` and the raw sum is low by
        ``1 - cos(pi f dt) = 4.48e-4``, i.e. 0.045 % in amplitude and 0.090 %
        in power.  It grows as ``(pi f dt)^2 / 2``, and the correction diverges
        as ``pi f dt -> pi/2``.  A copy.
        """
        if self.debias and self._h_scale is not None:
            return self._h_flat * self._h_scale[:, None, None]
        return self._h_flat.copy()

    @property
    def H_t_raw(self):
        """Tangential ``H`` phasors with the ``cos(pi f dt)`` left in.

        The running sum :meth:`accumulate` builds, in ``A s / m``: neither
        normalised nor phase corrected, and :attr:`H_t` times ``cos(pi f dt)``.
        This is the quantity the gather produces; the de-bias is a scale applied
        on read.  A copy.
        """
        return self._h_flat.copy()

    # -------------------------------------------------------------- gathers

    def _gather_e(self, e):
        """Tangential ``E`` at every sample, ``(N, 2)``."""
        i = self._e_idx
        return np.stack(
            (0.5 * (e[i[:, 0]] + e[i[:, 1]]),
             0.5 * (e[i[:, 2]] + e[i[:, 3]])),
            axis=1)

    def _gather_h(self, h):
        """Tangential ``H`` at every sample, ``(N, 2)``.

        Per component, a 2-average over the normal pair and then over the two
        results -- the same reduction :mod:`emfit.huygens` documents for
        ``h_face_index``.
        """
        i = self._h_idx
        out = np.empty((i.shape[0], 2), dtype=float)
        for c in range(2):
            base = 4 * c
            p0 = 0.5 * (h[i[:, base]] + h[i[:, base + 1]])
            p1 = 0.5 * (h[i[:, base + 2]] + h[i[:, base + 3]])
            out[:, c] = 0.5 * (p0 + p1)
        return out

    # ---------------------------------------------------------- accumulate

    def accumulate(self, t, stepper):
        """Record one time sample.

        Called with the time in seconds and the stepper holding the field.  The
        first call only primes the state (there is no previous ``h`` to average
        with, so no sample can be formed); from the second call on each call
        emits one sample, at the time of the *previous* call.

        Parameters
        ----------
        t : float
            Simulation time in seconds; passed to ``exp(-j w t)``.
        stepper : object
            Anything with ``e``, ``h``, ``dt`` --
            :class:`emfit.evolve.FITStepper` in practice.  Read only.
        """
        if self._h_scale is None:
            # dt is only known from the first call; the de-bias factor of the
            # half-step midpoint average is fixed from then on
            self._h_scale = 1.0 / np.cos(np.pi * self.freqs * float(stepper.dt))
        e_now = self._gather_e(np.asarray(stepper.e).reshape(-1))
        h_now = self._gather_h(np.asarray(stepper.h).reshape(-1))
        if self._prev_e is not None:
            t_emit = self._t_prev
            h_mid = 0.5 * (self._prev_h + h_now)
            weight = np.exp(-2j * np.pi * self.freqs * t_emit) * float(stepper.dt)
            self._e_flat += weight[:, None, None] * self._prev_e[None, :, :]
            self._h_flat += weight[:, None, None] * h_mid[None, :, :]
            self.n_samples += 1
            self.t_last = float(t_emit)
        self._prev_e = e_now
        self._prev_h = h_now
        self._t_prev = float(t)

    def __call__(self, t, stepper=None):
        """Accept both ``callback(stepper)`` and ``accumulate(t, stepper)``.

        A time-loop callback is handed the stepper alone; a caller replaying a
        stored record has the time to hand.  With one argument the time is read
        off ``stepper.time``, which the stepper sets to the instant of the
        electric field it is holding -- exactly the convention the two-argument
        form expects.
        """
        if stepper is None:
            stepper = t
            t = float(stepper.time)
        self.accumulate(float(t), stepper)
