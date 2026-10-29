"""The modal measurement harness: station planes -> (a_forward, a_backward).

This module is a thin *capture* around arithmetic that already exists.  Nothing
here invents an inner product: every line that touches the field was
transcribed from the study run itself, and every line that touches the mode
delegates to :mod:`emfit.modal`.

Provenance (auditable, by line)
-------------------------------
* The station-plane capture -- the four reshapes, the ``ix-1``/``ix`` straddle
  average of the ``H`` faces, and the phasor ``exp(-2j*pi*f0*n*dt)`` applied on
  the *integer step index* -- is transcribed **verbatim** from
  ``emfit/studies.py:2783-2817`` (the ``if plane_ey is not None:`` block inside
  ``microstrip_wave``'s time loop), whose own comment at
  ``emfit/studies.py:2718-2722`` states that the planes are stacked in the same
  complex128 the DFT uses and summed with the same ``exp(-2j pi f n dt)`` the
  probe accumulator applies.  That comment is the contract: the planes and the
  station voltages are one phasor set.
* The projection is **not** reimplemented.  :func:`emfit.modal.modal_station_phasors`
  (``emfit/modal.py:403-460``) is the repository's own overlap,
  ``a_E = (sum(e_y*E_y) + sum(e_z*E_z)) / (sum(e_y^2) + sum(e_z^2))``, with the
  ``H`` blocks de-staggered by ``exp(+j*pi*f*dt)``
  (:func:`emfit.plane_phasor.destagger`).  This module calls it.
* The mode is built by the existing constructor chain:
  :func:`emfit.mode_profile.microstrip_mode_profile` ->
  :func:`emfit.modal.plane_mode`, placed by integer index shift on the 3-D
  plane (``emfit/modal.py:267-307``).
* The two-station forward/backward split delegates to
  :func:`emfit.ports.travelling_waves` (``emfit/ports.py:663``), the house
  estimator, rather than solving the 2x2 again.

What this is not
----------------
There is **no absorbing port** and none is invented here
(:mod:`emfit.modalport` says the same in its docstring).  The capture is
therefore *truncated by step count* -- the caller sets ``limit`` -- so the
record can end before a far-end echo returns.  Truncating the run, not
windowing the accumulator, is the protection, exactly as §1.4 of the
preregistration records.

Units: the amplitudes this module returns are the **modal voltage phasors**
``v = a_E * v_mode`` from :class:`emfit.modal.StationPhasors` [V, mode units];
``a_e`` (dimensionless overlap) is reported beside them.  Absolute values are
calibration-free only in ratios of the same mode on the same plane.
"""

from __future__ import annotations

import numpy as np

from .modal import modal_station_phasors, plane_mode
from .mode_profile import microstrip_mode_profile
from .ports import travelling_waves

__all__ = [
    "build_mode_plane",
    "station_planes",
    "station_amplitude",
    "ModalStationCapture",
    "split_forward_backward",
]


# ---------------------------------------------------------------------------
# the mode, on the 3-D plane
# ---------------------------------------------------------------------------
def build_mode_plane(cc, *, h, w, eps_r, n_sub, k_strip, iy_strip_centre,
                     n_clean, n_air, check=False):
    """The microstrip mode placed on ``cc``'s transverse plane.

    ``microstrip_mode_profile`` builds the quasi-static section
    (``emfit/mode_profile.py:535``); ``plane_mode`` copies it into an
    ``(cc.nyn, cc.nzn)`` plane by integer index shift
    (``emfit/modal.py:267``).  ``k_strip`` is the node layer of the strip,
    ``iy_strip_centre`` the node layer of its centre in ``y``, and the profile's
    cell must be the grid's: ``h / n_sub == getattr(cc.grid, 'y')[1] - ...``.
    """
    profile = microstrip_mode_profile(h, w, eps_r, n_sub=n_sub,
                                      n_clean=n_clean, n_air=n_air,
                                      check=check)
    cell = float(h) / int(n_sub)
    return plane_mode(profile, nyn=cc.nyn, nzn=cc.nzn, k_strip=int(k_strip),
                      iy_strip_centre=iy_strip_centre, cell=cell)


# ---------------------------------------------------------------------------
# one station plane, straight out of the stepper
# ---------------------------------------------------------------------------
def station_planes(stepper, cc, ix):
    """``(E_y, E_z, H_z, H_y)`` of one station plane, unaccumulated.

    Transcribed from ``emfit/studies.py:2795-2817``: the same four reshapes off
    the same block offsets, ``E`` on the node layer ``ix``, ``H`` on the x cells
    that straddle it (``ix-1``, ``ix``; a single cell at either end), averaged.
    """
    pl_ey = stepper.e[cc.off_ey:cc.off_ey + cc.n_ey].reshape(
        cc.nxn, cc.ny, cc.nzn)
    pl_ez = stepper.e[cc.off_ez:cc.off_ez + cc.n_ez].reshape(
        cc.nxn, cc.nyn, cc.nz)
    pl_fz = stepper.h[cc.off_fz:cc.off_fz + cc.n_fz].reshape(
        cc.nx, cc.ny, cc.nzn)
    pl_fy = stepper.h[cc.off_fy:cc.off_fy + cc.n_fy].reshape(
        cc.nx, cc.nyn, cc.nz)
    ix = int(ix)
    if 0 < ix < cc.nx:
        straddle = (ix - 1, ix)
    elif ix == 0:
        straddle = (0,)
    else:
        straddle = (cc.nx - 1,)
    return (pl_ey[ix], pl_ez[ix],
            np.mean(pl_fz[list(straddle), :, :], axis=0),
            np.mean(pl_fy[list(straddle), :, :], axis=0))


def _project(planes, mode, stations, f0, dt, destagger_h=True):
    """Run the repository's own overlap on a set of plane snapshots."""
    return modal_station_phasors(planes, mode, stations, f0=f0, dt=dt,
                                 destagger_h=destagger_h)


def station_amplitude(stepper, cc, mode, station, *, f0, dt,
                      destagger_h=True):
    """Project the field *as it stands* at one station: a complex amplitude.

    One snapshot, no accumulation.  The number is the modal voltage phasor of
    whatever is on the plane -- for a single forward wave that is the forward
    amplitude; a mixed plane needs the two-station split
    (:func:`split_forward_backward`), because one plane cannot separate them.
    """
    ey, ez, hz, hy = station_planes(stepper, cc, station)
    planes = {"plane_Ey": ey[None, ...], "plane_Ez": ez[None, ...],
              "plane_Hz": hz[None, ...], "plane_Hy": hy[None, ...],
              "plane_f": float(f0), "plane_dt": float(dt)}
    ph = _project(planes, mode, [0], f0, dt, destagger_h=destagger_h)
    return complex(ph.v[0])


def split_forward_backward(v1, v2, d, beta):
    """Two station phasors -> ``(forward, backward)`` at station 1.

    Delegates to :func:`emfit.ports.travelling_waves`
    (``v1 = vp + vm``, ``v2 = vp exp(-j beta d) + vm exp(+j beta d)``); station 2
    is a distance ``d`` further along the direction of propagation.
    """
    vp, vm = travelling_waves(complex(v1), complex(v2), float(d), float(beta))
    return complex(vp), complex(vm)


# ---------------------------------------------------------------------------
# the accumulating capture
# ---------------------------------------------------------------------------
class ModalStationCapture:
    """Phasor-accumulate the mode amplitude at stations as the stepper runs.

    Parameters
    ----------
    cc : CellComplex
        The 3-D cell complex the run is on.
    mode : PlaneMode
        The placed mode (:func:`build_mode_plane`), on the plane lattice
        ``(cc.ny, cc.nzn)`` / ``(cc.nyn, cc.nz)``.
    stations : sequence of int
        Node layers ``ix`` along the guide axis.  Indices into the plane set,
        not positions in metres.
    f0 : float
        The DFT bin [Hz].  It must be the bin the record spans
        (``k / (n_acc * dt)``), not an arbitrary tone: a DFT bin is not
        interpolatable.
    dt : float
        The stepper's time step [s].
    limit : int, optional
        **The step limit.**  :meth:`run` stops after this many accumulated
        steps, so the record can be truncated before a far-end echo returns.
        ``None`` means "no limit"; the caller who wants a clean window must
        set it.
    n_warm : int, optional
        Steps to skip before accumulating (the drive ramp), as in the study.
    destagger_h : bool, optional
        De-stagger the magnetic blocks by ``exp(+j pi f dt)`` before projecting
        (default, the house convention).
    """

    def __init__(self, cc, mode, stations, *, f0, dt, limit=None, n_warm=0,
                 destagger_h=True):
        self.cc = cc
        self.mode = mode
        self.stations = np.atleast_1d(np.asarray(stations, dtype=int)).ravel()
        if self.stations.size == 0:
            raise ValueError("no stations asked for: nothing to capture")
        self.f0 = float(f0)
        self.dt = float(dt)
        self.limit = None if limit is None else int(limit)
        if self.limit is not None and self.limit < 1:
            raise ValueError(f"limit must be at least 1, got {limit!r}")
        self.n_warm = int(n_warm)
        self.destagger_h = bool(destagger_h)
        n = self.stations.size
        self.plane_ey = np.zeros((n, cc.ny, cc.nzn), dtype=np.complex128)
        self.plane_ez = np.zeros((n, cc.nyn, cc.nz), dtype=np.complex128)
        self.plane_hy = np.zeros((n, cc.nyn, cc.nz), dtype=np.complex128)
        self.plane_hz = np.zeros((n, cc.ny, cc.nzn), dtype=np.complex128)
        self.n_samples = 0
        self.n_seen = 0

    # -- accumulation ----------------------------------------------------
    def add(self, stepper, n):
        """Accumulate the plane at step index ``n`` (after the step)."""
        n = int(n)
        if n < self.n_warm:
            self.n_seen += 1
            return
        if self.limit is not None and self.n_samples >= self.limit:
            return
        # The phase is the accumulator's own expression, on the step index: the
        # same line ``DftAccumulator.add`` runs (``emfit/ports.py:679``), which
        # is why the planes and the station voltages share one phasor set.
        phase = np.exp(-2.0j * np.pi * self.f0 * n * self.dt)
        for i, ix in enumerate(self.stations):
            ey, ez, hz, hy = station_planes(stepper, self.cc, ix)
            self.plane_ey[i] += phase * ey
            self.plane_ez[i] += phase * ez
            self.plane_hz[i] += phase * hz
            self.plane_hy[i] += phase * hy
        self.n_samples += 1
        self.n_seen += 1

    def run(self, stepper, drive=None, limit=None):
        """Step ourselves, accumulating, until the limit (or ``drive`` ends).

        ``drive(n)`` may return an ``n_edges`` current vector for step ``n``, or
        ``None`` for a silent step.  ``limit`` overrides the constructor's for
        this call only; the number of accumulated samples is the caller's
        window, and it is deliberately the only termination this capture knows.
        """
        stop = self.limit if limit is None else int(limit)
        n = 0
        while stop is None or self.n_samples < stop:
            cur = None if drive is None else drive(n)
            if cur is not None:
                stepper.step(cur)
            else:
                stepper.step(np.zeros(self.cc.n_edges, dtype=float))
            self.add(stepper, n)
            n += 1
        return self.result()

    # -- the answer ------------------------------------------------------
    @property
    def planes(self):
        """The four accumulated blocks, keyed exactly as a capture record is."""
        return {"plane_Ey": self.plane_ey, "plane_Ez": self.plane_ez,
                "plane_Hy": self.plane_hy, "plane_Hz": self.plane_hz,
                "plane_f": self.f0, "plane_dt": self.dt}

    def phasors(self, stations=None):
        """The repository's projection of the accumulated blocks."""
        idx = (np.arange(self.stations.size) if stations is None
               else np.atleast_1d(np.asarray(stations, dtype=int)).ravel())
        return _project(self.planes, self.mode, idx, self.f0, self.dt,
                        destagger_h=self.destagger_h)

    def amplitude(self, station):
        """The accumulated amplitude at one station, a Python ``complex``."""
        pos = int(np.flatnonzero(self.stations == int(station))[0]) \
            if int(station) in self.stations else int(station)
        return complex(self.phasors([pos]).v[0])

    def result(self):
        """``dict``: station ``ix`` -> complex amplitude, plus the record facts."""
        ph = self.phasors()
        return {
            "amplitudes": {int(ix): complex(v)
                           for ix, v in zip(self.stations, ph.v)},
            "a_e": {int(ix): complex(a) for ix, a in zip(self.stations, ph.a_e)},
            "a_h": {int(ix): complex(a) for ix, a in zip(self.stations, ph.a_h)},
            "f0": self.f0,
            "dt": self.dt,
            "steps": self.n_samples,
            "limit": self.limit,
            "stations": [int(ix) for ix in self.stations],
            "mode_report": self.mode.report,
        }
