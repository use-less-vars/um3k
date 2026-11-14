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
The grid unknowns the recorder reads are *voltages*, not fields: ``e`` is the
primal edge voltage ``E . L_e`` (V) and ``h`` the dual magnetic voltage
``H . L_dual`` (A).  A gather averages those voltages, so it is turned back into
a field by dividing by the metric mean of the lengths it averaged
(:func:`_metric_means`); and the ``exp(-j w t) * dt`` sum is turned into a
phasor by dividing by the half window ``Teff / 2``, with
``Teff = n_samples * dt``.  Each spectral entry is therefore a physical phasor:
:attr:`SurfaceRecorder.E_t` in V/m, :attr:`SurfaceRecorder.H_t` in A/m.  With
both in field units, :attr:`SurfaceRecorder.flux_face` multiplies
``(E_t x conj(H_t)) . n`` by the face area exactly **once**, which makes
:attr:`SurfaceRecorder.flux` a real power in W.

Nothing is scaled to a source amplitude: that is a property of the drive, not of
the record, so a caller that needs it scales once, at the end.  The raw running
sums are kept too (:attr:`SurfaceRecorder.E_t_raw`,
:attr:`SurfaceRecorder.H_t_raw`), because they are what the gather produces and
a broadband record may want no window at all.

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

Surface currents, flux, and export
----------------------------------
:attr:`SurfaceRecorder.J_s` and :attr:`SurfaceRecorder.M_s` are the equivalent
surface currents ``n x H_t`` and ``-n x E_t``; :attr:`SurfaceRecorder.flux_face`
is the per-face complex Poynting integrand ``(E_t x conj(H_t)) . n`` times the
face area; :attr:`SurfaceRecorder.flux` is ``0.5 Re`` of its sum over the
samples, the net real power crossing the surface; and
:meth:`SurfaceRecorder.save_npz` writes the whole record -- with ``dt``, the
mesh spacings and the geometry -- to a ``.npz`` archive.  What the currents are
*not* is the route to that power:

the power is asserted via the DIRECT Poynting integral over the surface, NOT via the equivalent-current far-field route. J_s and M_s are emitted as documented outputs for downstream use, but they are not the path by which flux is computed - the equivalent-current route yields the far field, not the surface power.

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

#: How the recorded ``E`` and ``H`` were placed at the sample points; written
#: verbatim into every archive by :meth:`SurfaceRecorder.save_npz` so the
#: numbers cannot be read back against the wrong colocation assumption.
_COLOCATION_RULE = (
    "E and H are recorded at the sample points by midpoint averaging: E is the "
    "mean of the two bounding primal edges, and H is averaged from the n-1/2 "
    "and n+1/2 half-steps onto the integer step n by the midpoint mean of the "
    "four primal faces of each tangential component, with an amplitude divide "
    "by cos(pi f dt) applied unless debias=False")


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


def _metric_means(cc, samples):
    """Metric length of the gather behind each recorded tangential component.

    The grid unknowns are voltages -- ``e`` is the primal edge voltage
    ``E . L_e`` and ``h`` the dual magnetic voltage ``H . L_dual`` -- so a
    gather that averages them is a mean *voltage*, and recovering the field
    means dividing by the mean *length* it averaged.  Those lengths are the
    primitive metric itself: :meth:`emfit.grid.Grid.edge_length` for the two
    bounding primal edges of an ``E`` slot, and
    :meth:`emfit.grid.Grid.dual_widths` for the four primal faces of an ``H``
    slot.  Reading them off the grid is exact for a graded mesh, where a single
    nominal ``h`` is not (the four faces of one ``H`` slot have two different
    normal widths).

    Parameters
    ----------
    cc : emfit.operators.CellComplex
        Supplies the per-block offsets and the grid metric.
    samples : SurfaceSamples
        The conformed surface; its ``edge_index`` and ``h_face_index`` select
        which lengths are averaged.

    Returns
    -------
    (e_len, h_len) : tuple of (N, 2) float64
        Per-sample, per-slot mean lengths in metres, slot order as
        :attr:`SurfaceRecorder.E_t`.  Empty surfaces give ``(0, 2)`` arrays.
    """
    grid = cc.grid
    face_id = np.asarray(samples.face_id, dtype=np.intp)
    n = face_id.size
    if n == 0:
        return np.zeros((0, 2), dtype=float), np.zeros((0, 2), dtype=float)
    edge_index = np.asarray(samples.edge_index, dtype=np.intp)
    h_face_index = np.asarray(samples.h_face_index, dtype=np.intp)

    # primal edge lengths, in the flat ``e`` layout
    edge_len = np.empty(cc.n_edges, dtype=float)
    for axis, name in enumerate("xyz"):
        off = getattr(cc, f"off_e{name}")
        cnt = getattr(cc, f"n_e{name}")
        edge_len[off:off + cnt] = np.asarray(
            grid.edge_length(name), dtype=float).ravel()
    # dual lengths, in the flat ``h`` layout (dual_widths is 1-D per node line,
    # so it has to be broadcast along the two dual directions of the face)
    dual_len = np.empty(cc.n_faces, dtype=float)
    for axis, name in enumerate("xyz"):
        off = getattr(cc, f"off_f{name}")
        cnt = getattr(cc, f"n_f{name}")
        w = np.asarray(grid.dual_widths(name), dtype=float)
        shp = [(w.size, 1, 1), (1, w.size, 1), (1, 1, w.size)][axis]
        dual_len[off:off + cnt] = np.broadcast_to(
            w.reshape(shp), grid.face_shape(name)).ravel()

    e_len = np.stack(
        (0.5 * (edge_len[edge_index[:, 0]] + edge_len[edge_index[:, 1]]),
         0.5 * (edge_len[edge_index[:, 2]] + edge_len[edge_index[:, 3]])),
        axis=1)
    h_len = np.stack(
        (0.25 * (dual_len[h_face_index[:, 0]] + dual_len[h_face_index[:, 1]]
                 + dual_len[h_face_index[:, 2]] + dual_len[h_face_index[:, 3]]),
         0.25 * (dual_len[h_face_index[:, 4]] + dual_len[h_face_index[:, 5]]
                 + dual_len[h_face_index[:, 6]] + dual_len[h_face_index[:, 7]])),
        axis=1)
    return e_len, h_len


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
    dt : float or None
        The time step of the first call to :meth:`accumulate`, in seconds;
        ``None`` until then.
    n_hat : (N, 3) float64
        The outward unit normals, i.e. :attr:`normals`.
    dA : (N,) float64
        The sample face areas, i.e. :attr:`face_areas`.
    J_s, M_s : (n_freq, N, 3) complex128
        Equivalent surface currents ``n_hat x H_t`` and ``-n_hat x E_t``.
    flux_face : (n_freq, N) complex128
        Per-face complex Poynting integrand, before the sum and the ``0.5 Re``.
    flux : (n_freq,) float64
        Net real power crossing the surface, in watts: ``0.5 Re`` of the sum of
        :attr:`flux_face`.

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
        # which axis each sample's normal is along, 0/1/2 for x/y/z; this is
        # what fixes the tangential slot order (see E_t)
        self._normal_axis = np.asarray(self.face_id, dtype=np.intp) // 2

        self._e_idx = np.asarray(samples.edge_index, dtype=np.intp)
        self._h_idx = np.asarray(samples.h_face_index, dtype=np.intp)
        # the voltages the gathers average, per slot: a length to divide by to
        # get back to a field (see _metric_means)
        self._e_len, self._h_len = _metric_means(cc, samples)
        self._e_flat = np.zeros((freqs.size, n_surface, 2), dtype=np.complex128)
        self._h_flat = np.zeros((freqs.size, n_surface, 2), dtype=np.complex128)
        self.n_samples = 0
        self.t_last = float("nan")
        self.dt = None
        self._prev_e = None
        self._prev_h = None
        self._t_prev = None
        self._h_scale = None

    # ---------------------------------------------------------------- views

    @property
    def _window(self):
        """Half the recording window ``Teff / 2``, in seconds.

        ``Teff = n_samples * dt`` is the total time the running sums integrate
        over, and a trailing-rectangle sum of ``field * dt * exp(-j w t)`` over
        it is ``Teff / 2`` times the phasor of a tone.  ``0.0`` before the first
        sample (when ``dt`` or ``n_samples`` is not yet known), which is what
        makes the phasors of an empty record zero rather than ``nan``.
        """
        if self.dt is None or self.n_samples == 0:
            return 0.0
        return 0.5 * self.n_samples * self.dt

    @property
    def E_t(self):
        """Tangential ``E`` phasors, ``(n_freq, N, 2)`` complex128, in V/m.

        Slot 0 is the first tangential component, slot 1 the second, in
        ascending axis order excluding the sample normal -- the order
        :attr:`SurfaceSamples.edge_index` uses (``E_y, E_z`` on an x-normal box
        face, ``E_x, E_z`` on a y-normal one, ``E_x, E_y`` on a z-normal one).

        The running sum of the edge *voltages* ``E . L_e`` is divided by the
        mean length the gather averaged (:func:`_metric_means`) and by the half
        window ``Teff / 2``, so an entry is the phasor of ``E`` itself -- the
        value a plane wave injected as ``e = E L_e`` records back as ``E``.
        ``V/m``, not normalised to any source amplitude.  A copy, so a caller
        cannot corrupt the running sum by editing what it reads; the sum itself
        is :attr:`E_t_raw`.
        """
        window = self._window
        if window <= 0.0:
            return np.zeros_like(self._e_flat)
        return self._e_flat / (self._e_len * window)[None, :, :]

    @property
    def E_t_raw(self):
        """Tangential ``E`` running sum, ``(n_freq, N, 2)`` complex128, in V s.

        Exactly what :meth:`accumulate` builds: a sum of the gathered edge
        voltages times ``dt * exp(-j w t)``, with no metric divide, no window
        divide and no phase correction.  It is :attr:`E_t` times
        ``e_len * Teff / 2``, and it is the quantity to keep when a record has
        to be re-normalised by something other than the window -- a broadband
        drive, or a caller that owns its own spectral weighting.  A copy.
        """
        return self._e_flat.copy()

    @property
    def H_t(self):
        """Tangential ``H`` phasors, ``(n_freq, N, 2)`` complex128, in A/m.

        Same slot order as :attr:`E_t`.  The running sum of the dual magnetic
        voltages ``H . L_dual`` is divided by the mean length the gather
        averaged (:func:`_metric_means`) and by the half window ``Teff / 2``,
        and each entry is taken at the instant of the matching ``E`` sample
        (the half-step midpoint average, see the module docstring), which
        leaves the real factor ``cos(pi f dt)`` in it; with ``debias`` set (the
        default) that factor is divided out, so the entry is the phasor the
        field has at the sample instant.  With ``debias=False`` the raw sum is
        returned, exactly as :attr:`H_t_raw` always does -- in ``A s``.

        The division is exact for a tone at a frequency in ``freqs`` and
        meaningless for a broadband signal, where no single ``f`` owns the
        factor -- record raw and leave it to whatever forms the ratio.  On a
        CFL-limited step it is small: a 1 mm cell gives ``dt = 1.907e-12 s``, so
        at 5 GHz ``pi f dt = 0.0299`` and the raw sum is low by
        ``1 - cos(pi f dt) = 4.48e-4``, i.e. 0.045 % in amplitude and 0.090 %
        in power.  It grows as ``(pi f dt)^2 / 2``, and the correction diverges
        as ``pi f dt -> pi/2``.  A copy.
        """
        window = self._window
        if window <= 0.0:
            return np.zeros_like(self._h_flat)
        field = self._h_flat / (self._h_len * window)[None, :, :]
        if self.debias and self._h_scale is not None:
            return field * self._h_scale[:, None, None]
        return field

    @property
    def H_t_raw(self):
        """Tangential ``H`` running sum, ``(n_freq, N, 2)`` complex128, in A s.

        The sum :meth:`accumulate` builds from the gathered dual magnetic
        voltages: no metric divide, no window divide, no phase correction, and
        the ``cos(pi f dt)`` of the half-step midpoint average left in.  So
        ``H_t = H_t_raw * cos(pi f dt) / (h_len * Teff / 2)`` with ``debias``
        set, and ``H_t = H_t_raw / (h_len * Teff / 2)`` without it -- this is
        the quantity the gather produces, and the de-bias is a scale applied on
        read.  A copy.
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
        self.dt = float(stepper.dt)
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

    # ------------------------------------------------------------- geometry

    @property
    def n_hat(self):
        """Outward unit normals of the sample points, ``(N, 3)`` float64.

        The conformed normals themselves (:attr:`normals`): axis aligned, so
        every entry is exactly ``0`` or ``+-1``.  Nothing is re-derived here, so
        a surface whose normals were edited is measured as edited -- which is
        what lets a test pin the sign of the flux by turning them round.
        """
        return self.normals

    @property
    def dA(self):
        """Face areas of the sample points, ``(N,)`` float64.

        The same metric :attr:`face_areas` carries, under the name the surface
        integral uses.
        """
        return self.face_areas

    # ------------------------------------------------------------- currents

    def _tangential_to_vec(self, t2):
        """Scatter ``(n_freq, N, 2)`` tangential phasors to ``(n_freq, N, 3)``.

        The inverse of the slot convention :attr:`E_t` and :attr:`H_t`
        document: slot 0 goes to the first tangential axis of the sample, slot 1
        to the second, in ascending axis order excluding the normal.  The normal
        component is exactly zero: the recorder measures the *tangential* field,
        and the vector a cross product with ``n_hat`` needs is that one.
        """
        t2 = np.asarray(t2)
        out = np.zeros((t2.shape[0], self.n_surface, 3), dtype=np.complex128)
        for axis in range(3):
            sel = self._normal_axis == axis
            if not np.any(sel):
                continue
            first, second = [b for b in range(3) if b != axis]
            out[:, sel, first] = t2[:, sel, 0]
            out[:, sel, second] = t2[:, sel, 1]
        return out

    @property
    def J_s(self):
        """Equivalent electric surface current, ``(n_freq, N, 3)`` complex128.

        ``J_s = n_hat x H_t``, formed from the tangential magnetic phasor (so
        from the de-biased one whenever ``debias`` is set) and the outward
        normal.  In ``A/m``, the same physical units :attr:`H_t` has, and
        likewise not scaled to a source amplitude.

        A documented output for downstream use, not the route to the power --
        see :attr:`flux`.
        """
        return np.cross(self.n_hat[None, :, :],
                        self._tangential_to_vec(self.H_t))

    @property
    def M_s(self):
        """Equivalent magnetic surface current, ``(n_freq, N, 3)`` complex128.

        ``M_s = -n_hat x E_t``, in ``V/m``: the same physical units as
        :attr:`E_t`, and the same caveat as :attr:`J_s`.
        """
        return -np.cross(self.n_hat[None, :, :],
                         self._tangential_to_vec(self.E_t))

    # ----------------------------------------------------------------- power

    @property
    def flux_face(self):
        """Per-face complex Poynting integrand, ``(n_freq, N)`` complex128.

        ``(E_t x conj(H_t)) . n_hat`` times the face area at every sample: the
        integrand of the surface integral *before* the sum over faces and
        *before* the ``0.5 Re``, so :attr:`flux` is exactly
        ``0.5 * flux_face.real.sum(axis=1)``.  Keeping it means a caller can see
        which faces carry the power and which merely cancel.

        The conjugate sits on ``H`` because these are ``exp(-j w t)`` phasors
        and the two are in field units (:attr:`E_t` in V/m, :attr:`H_t` in
        A/m), so ``(E_t x conj(H_t)) . n_hat`` is already a power density in
        ``W/m^2``: multiplying by the face area **once** is the whole of the
        integration, and the entries are in W.  There is no ``dt`` left in it
        and no area to divide out again -- a face counted twice would show up as
        an ``h^2`` error in the total, which is exactly what
        :attr:`flux` must not have.
        """
        s_vec = np.cross(self._tangential_to_vec(self.E_t),
                         np.conj(self._tangential_to_vec(self.H_t)))
        return (np.einsum("fnk,nk->fn", s_vec, self.n_hat)
                * self.face_areas[None, :])

    @property
    def flux(self):
        """Net real power crossing the surface, ``(n_freq,)`` float64, in W.

        ``0.5 Re`` of the sum of :attr:`flux_face` over the samples.  A closed
        surface in a lossless region gives zero to round-off; an open one gives
        the power leaving through the opening, in W, with the sign of the
        outward normal.

        The route matters, and it is deliberate:

        the power is asserted via the DIRECT Poynting integral over the surface, NOT via the equivalent-current far-field route. J_s and M_s are emitted as documented outputs for downstream use, but they are not the path by which flux is computed - the equivalent-current route yields the far field, not the surface power.
        """
        return 0.5 * np.real(self.flux_face.sum(axis=1))

    # ---------------------------------------------------------------- export

    def save_npz(self, path, *, stray=False):
        """Write the record to a ``.npz`` archive at ``path``.

        Keys: ``schema_version`` (int, ``1``), ``stray`` (bool), ``dt`` (s),
        ``dx``, ``dy``, ``dz`` (primal cell widths, m), ``colocation_rule`` (a
        string saying how the samples were placed), ``freqs``, ``coordinates``,
        ``normals``, ``face_id``, ``dA``, ``E_t``, ``H_t``, ``J_s``, ``M_s``,
        ``flux`` and ``flux_face``.

        ``E_t`` and ``H_t`` are the physical phasors (V/m and A/m), ``J_s`` and
        ``M_s`` the physical surface currents (A/m and V/m), ``flux_face`` the
        per-face power in W and ``flux`` the net power in W -- all as read off
        the properties, so nothing is re-scaled on the way out.  ``dt`` and the
        spacings still travel with them, as provenance: they are what the sums
        were integrated with, so a reader can rebuild the raw sums
        (``E_t * e_len * Teff / 2``) or check the de-bias, and an archive is
        never a table of values with no units.  The spacings are the mean cell
        widths of the three axes -- exact for a uniform grid, nominal for a
        graded one, where the per-sample geometry is ``coordinates`` and
        ``dA``, which are exact.

        Parameters
        ----------
        path : str or os.PathLike
            Target file; ``numpy.savez`` appends ``.npz`` if it is missing.
        stray : bool, optional
            Write a labelled placeholder instead of raising when nothing has
            been recorded yet.  Every phasor is then still zero and ``dt`` is
            ``nan``, and the ``stray`` key says so, so a reader can refuse the
            archive rather than read zeros as a measurement.

        Raises
        ------
        ValueError
            If nothing has been recorded (``n_samples == 0``) and ``stray`` is
            not set.  ``E_t``, ``H_t``, ``dt``, ``J_s``, ``M_s`` and the flux
            are all still unset at that point, and an archive of zeros is a
            silent wrong answer: two calls of the recorder are needed before
            the first sample exists.

        Notes
        -----
        No far-field transform is stored, because none is computed here -- see
        :attr:`flux` for why the power does not come from the equivalent
        currents.
        """
        if self.n_samples == 0 and not stray:
            raise ValueError(
                "save_npz: nothing recorded -- E_t, H_t, dt, J_s, M_s and flux "
                "are all still unset because the recorder has not produced a "
                "sample (K calls of accumulate give K - 1 samples); record "
                "from the time loop first, or pass stray=True to export "
                "labelled zeros")
        grid = self.cc.grid
        dx, dy, dz = (float(np.mean(grid.widths(axis))) for axis in "xyz")
        np.savez(
            path,
            schema_version=np.int64(1),
            stray=np.asarray(bool(stray), dtype=bool),
            dt=np.float64(np.nan if self.dt is None else self.dt),
            dx=np.float64(dx),
            dy=np.float64(dy),
            dz=np.float64(dz),
            colocation_rule=np.asarray(_COLOCATION_RULE),
            freqs=np.asarray(self.freqs, dtype=float),
            coordinates=np.asarray(self.coordinates, dtype=float),
            normals=np.asarray(self.normals, dtype=float),
            face_id=np.asarray(self.face_id, dtype=np.int8),
            dA=np.asarray(self.face_areas, dtype=float),
            E_t=self.E_t,
            H_t=self.H_t,
            J_s=self.J_s,
            M_s=self.M_s,
            flux=self.flux,
            flux_face=self.flux_face,
        )
