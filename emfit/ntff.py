"""Reading a recorded Huygens surface back, for a far-field transform.

What this module is
-------------------
:mod:`emfit.huygens_fields` produces the record: the tangential ``E`` and
``H`` phasors on a conformed box, the equivalent surface currents, and the
power crossing the surface, written to a ``.npz`` archive by
:meth:`~emfit.huygens_fields.SurfaceRecorder.save_npz`.  Its module docstring
says the transform that consumes those numbers "lives elsewhere"; this module
is the first half of that elsewhere, and:

* :class:`SurfaceDump` is the archive as arrays -- one attribute per key,
  with every structural promise the writer made checked on the way in;
* :func:`load_surface_dump` is a path to one of those.

The far field is here, and it is a phase sum
--------------------------------------------
The transform is the rest of this module, and it answers the questions the
TODO list at the end of this file used to hold, one per section of
``docs/design/3d_ntff_te_spec.md``:

* :func:`radiation_vectors` and :func:`far_field` are the transform itself
  (section 1): a plain phase sum, ``exp(+j k rhat . r_q)`` per stored sample,
  weighted by the ``dA`` recorded with it;
* what they sum is the stored ``J_s``/``M_s``, not a reconstruction from the
  two-slot tangential ``E_t``/``H_t`` basis -- the outward cross products are
  the writer's job and were done there;
* the result is ``F = r E_far``: the ``exp(-j k r) / r`` is factored out once
  and never divided out again, so ``U`` is already ``r^2`` times the power
  density and no radius has to be invented;
* the phase is ``exp(+j k rhat . r')`` -- the kernel's phasors are
  ``e^{+j omega t}`` (see :data:`emfit.plane_phasor.PLANE_CONVENTION`), so an
  outgoing wave is ``e^{-j k r}`` and its source-phase factor is positive.
  (:mod:`emfit.huygens_fields` says ``exp(-j w t)`` in one docstring; its
  power ``0.5 Re(E x conj(H))`` is the same number under either convention,
  so nothing that module computes depends on that prose.)

The schema is the writer's, not this reader's
---------------------------------------------
An archive has eighteen keys, and the shapes below are transcribed from
:meth:`emfit.huygens_fields.SurfaceRecorder.save_npz` rather than invented:
``schema_version``, ``stray``, ``dt``, ``dx``, ``dy``, ``dz``,
``colocation_rule``, ``freqs``, ``coordinates``, ``normals``, ``face_id``,
``dA``, ``E_t``, ``H_t``, ``J_s``, ``M_s``, ``flux`` and ``flux_face``.

The scalars are ``schema_version`` (int, ``1``), ``stray`` (bool), ``dt``
(s), ``dx``/``dy``/``dz`` (mean primal cell widths, m) and
``colocation_rule`` (a string).  The array keys, with ``n_freq`` frequencies
and ``n_surface`` sample points:

* ``freqs`` -- ``(n_freq,)`` float64, Hz, in the order the inner axes use;
* ``coordinates`` -- ``(n_surface, 3)`` float64, m: the sample positions;
* ``normals`` -- ``(n_surface, 3)`` float64: the outward unit normal of the
  box face each sample belongs to, axis aligned, so every entry is 0 or +-1;
* ``face_id`` -- ``(n_surface,)`` int8, ``0..5`` for ``xmin, xmax, ymin,
  ymax, zmin, zmax``;
* ``dA`` -- ``(n_surface,)`` float64, m^2: the metric area of each sample's
  primal face;
* ``E_t``, ``H_t`` -- ``(n_freq, n_surface, 2)`` complex128, V/m and A/m;
* ``J_s``, ``M_s`` -- ``(n_freq, n_surface, 3)`` complex128, A/m and V/m;
* ``flux`` -- ``(n_freq,)`` float64, W: the net real power crossing the
  surface;
* ``flux_face`` -- ``(n_freq, n_surface)`` complex128, W: the same integrand
  before the sum and the ``0.5 Re``.

The ``E_t``/``H_t`` slot of two is the pair of *tangential* components, in
ascending axis order excluding the normal (the convention
:mod:`emfit.huygens_fields` documents); ``J_s`` and ``M_s`` are full 3-vectors
whose normal component is zero.  Both field pairs are physical phasors -- V/m
and A/m, not grid voltages -- and no key is scaled to a source amplitude, so
nothing in the archive needs a rescale on the way in.

Why the reader is strict
------------------------
``numpy.load`` is not a reader: it hands back whatever the file contains, and
almost every way an archive can be wrong is quiet.  A missing key is an
``KeyError`` from somewhere deep in the transform; a transposed ``E_t`` gives
the right number of numbers and a pattern with the wrong symmetry; a normal
that is not a unit vector scales every contribution of its face by a factor
nobody will look for; a zero area silently drops a face, which is a hole in a
closed surface; a single ``nan`` poisons the whole angular spectrum and shows
up as a pattern that is merely "a bit off" everywhere.  None of these raise on
their own, so :func:`load_surface_dump` raises for them here, at the boundary,
where the message can still name the key and the index.

The writer's own ``stray=True`` archive is refused rather than read: it is
labelled zeros with ``dt=nan``, and a transform that accepted it would report
a pattern of zero for an unrecorded surface.
"""

from __future__ import annotations

import math
import os
import warnings
from dataclasses import dataclass

import numpy as np

from .materials import C0, ETA0

__all__ = [
    "SCHEMA_VERSION",
    "SurfaceDump",
    "load_surface_dump",
    "FarField",
    "integration_angles",
    "radiation_vectors",
    "far_field",
    "total_radiated_power",
]

#: The only archive ``schema_version`` this reader understands.  A new writer
#: version means a new shape rule, so the reader refuses rather than guesses.
SCHEMA_VERSION = 1

#: The eighteen keys :meth:`SurfaceRecorder.save_npz` writes, in its order.
_KEYS = (
    "schema_version",
    "stray",
    "dt",
    "dx",
    "dy",
    "dz",
    "colocation_rule",
    "freqs",
    "coordinates",
    "normals",
    "face_id",
    "dA",
    "E_t",
    "H_t",
    "J_s",
    "M_s",
    "flux",
    "flux_face",
)

#: How far a normal may sit from unit length and still be one.
_UNIT_TOL = 1e-9

#: How far ``J_s`` or ``M_s`` may lean along the face normal, relative to the
#: largest entry of the same array.  The writer builds both by crossing the
#: unit normal with a tangential field, so the normal slot is exactly zero --
#: measured 0.0e+00 relative on archives from ``SurfaceRecorder.save_npz``,
#: which is why the tolerance is a tripwire for a *construction* change and
#: not a physical allowance.  Relative, not absolute, so it holds at any
#: excitation level and for any pattern's dynamic range.
_NORMAL_TOL = 1e-9


def _scalar(name, value):
    """One archive scalar as a float, refusing booleans and non-scalars."""
    arr = np.asarray(value)
    if arr.ndim != 0:
        raise ValueError(
            f"{name}: expected a scalar, got shape {arr.shape}")
    if arr.dtype.kind == "b":
        raise ValueError(
            f"{name}={value!r}: a boolean is not a number")
    if arr.dtype.kind not in "iuf":
        raise ValueError(
            f"{name}={value!r}: expected a real number, got dtype "
            f"{arr.dtype}")
    return float(arr)


def _text(name, value):
    """One archive scalar as a non-empty string, refusing everything else."""
    arr = np.asarray(value)
    if arr.ndim != 0 or arr.dtype.kind not in "US":
        raise ValueError(
            f"{name}={value!r}: expected a single string, got dtype "
            f"{arr.dtype} of shape {arr.shape}")
    text = str(arr)
    if not text:
        raise ValueError(
            f"{name}: empty string -- this key is provenance, and an empty "
            f"one says nothing about how E and H were placed")
    return text


def _array(name, value, shape, dtype, sizes):
    """One archive array as an owned, read-only array of the given shape."""
    arr = np.array(value, dtype=dtype, copy=True)
    if arr.shape != shape:
        raise ValueError(
            f"{name}: expected shape {shape} (n_freq={sizes[0]}, "
            f"n_surface={sizes[1]}), got {arr.shape}")
    arr.flags.writeable = False
    return arr


def _require_finite(name, arr):
    """Refuse an array holding ``nan`` or ``inf``, naming the first one."""
    if arr.dtype.kind == "c":
        bad = ~(np.isfinite(arr.real) & np.isfinite(arr.imag))
    else:
        bad = ~np.isfinite(arr)
    count = int(np.count_nonzero(bad))
    if not count:
        return
    first = tuple(int(i) for i in np.argwhere(bad)[0])
    raise ValueError(
        f"{name}: {count} non-finite "
        f"{'entry' if count == 1 else 'entries'}, first at index {first}")


def _row(arr, index):
    """A short printable form of one row, for an error message."""
    return "(" + ", ".join(f"{float(x)!r}" for x in arr[index]) + ")"


@dataclass(frozen=True)
class SurfaceDump:
    """One recorded Huygens surface, as read back from an archive.

    The arrays are copies owned by this object and marked read-only, so the
    frozen promise is not merely decorative.

    Attributes
    ----------
    schema_version : int
        The writer's archive version; must equal :data:`SCHEMA_VERSION`.
    stray : bool
        The writer's label for a placeholder archive.  Always ``False`` here:
        a stray archive is refused by :func:`load_surface_dump` before it is
        built, because its zeros are not a measurement.
    dt : float
        The time step the phasors were integrated with, in seconds.
    dx, dy, dz : float
        Mean primal cell widths of the three axes, in metres.  Provenance
        only: the per-sample geometry is :attr:`coordinates` and :attr:`dA`.
    colocation_rule : str
        How ``E`` and ``H`` were placed at the sample points, as the writer
        recorded it.
    freqs : (n_freq,) float64
        Frequencies of the phasors, in Hz, in the order the inner axes use.
    coordinates : (n_surface, 3) float64
        Sample positions in metres.
    normals : (n_surface, 3) float64
        Outward unit normal of the box face each sample belongs to; axis
        aligned, so every entry is ``0`` or ``+-1``.
    face_id : (n_surface,) int8
        Which box face: ``0..5`` for ``xmin, xmax, ymin, ymax, zmin, zmax``.
    dA : (n_surface,) float64
        Metric area of each sample's primal face, in m^2.  Strictly positive:
        a face with no area is a sample that cannot be weighted.
    E_t, H_t : (n_freq, n_surface, 2) complex128
        Tangential electric (V/m) and magnetic (A/m) phasors, two components
        per sample in the writer's ascending-axis slot order.
    J_s, M_s : (n_freq, n_surface, 3) complex128
        Equivalent electric (A/m) and magnetic (V/m) surface currents, the
        writer's ``n_hat x H_t`` and ``-n_hat x E_t``.
    flux : (n_freq,) float64
        Net real power crossing the surface, in W: the ``0.5 Re`` of the
        direct Poynting integral over these faces, not a far-field quantity.
    flux_face : (n_freq, n_surface) complex128
        The same integrand before the sum and the ``0.5 Re``, in W, kept
        because it says which faces carry the power.
    """

    schema_version: int
    stray: bool
    dt: float
    dx: float
    dy: float
    dz: float
    colocation_rule: str
    freqs: np.ndarray
    coordinates: np.ndarray
    normals: np.ndarray
    face_id: np.ndarray
    dA: np.ndarray
    E_t: np.ndarray
    H_t: np.ndarray
    J_s: np.ndarray
    M_s: np.ndarray
    flux: np.ndarray
    flux_face: np.ndarray

    def __post_init__(self):
        version = int(_scalar("schema_version", self.schema_version))
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"schema_version={version}: this reader knows "
                f"{SCHEMA_VERSION} only")
        stray = bool(np.asarray(self.stray))
        if stray:
            raise ValueError(
                "stray=True: the writer marked this archive as labelled "
                "zeros (dt=nan, every phasor zero), so it holds no "
                "measurement to transform")
        object.__setattr__(self, "stray", stray)
        for name, unit in (("dt", "s"), ("dx", "m"), ("dy", "m"),
                           ("dz", "m")):
            value = _scalar(name, getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"{name}={value!r}: a positive finite number of {unit} "
                    f"is required")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "colocation_rule",
                           _text("colocation_rule", self.colocation_rule))

        # The two lengths every other shape is measured against come from
        # freqs and coordinates, so they are checked before anything that
        # quotes them.
        freqs = np.array(self.freqs, dtype=float, copy=True)
        if freqs.ndim != 1 or freqs.size == 0:
            raise ValueError(
                f"freqs: expected a non-empty 1-D array of frequencies, got "
                f"shape {freqs.shape}")
        coordinates = np.array(self.coordinates, dtype=float, copy=True)
        if coordinates.ndim != 2 or coordinates.shape[1] != 3:
            raise ValueError(
                f"coordinates: expected shape (n_surface, 3), got "
                f"{coordinates.shape}")
        n_freq = freqs.shape[0]
        n_surface = coordinates.shape[0]
        if n_surface == 0:
            raise ValueError(
                "coordinates: no samples -- a surface with nothing on it "
                "cannot be transformed, and the writer refuses to produce "
                "one")
        sizes = (n_freq, n_surface)

        for arr in (freqs, coordinates):
            arr.flags.writeable = False
        object.__setattr__(self, "freqs", freqs)
        object.__setattr__(self, "coordinates", coordinates)

        normals = _array("normals", self.normals, (n_surface, 3), float,
                         sizes)
        lengths = np.linalg.norm(normals, axis=1)
        off = np.flatnonzero(np.abs(lengths - 1.0) > _UNIT_TOL)
        if off.size:
            index = int(off[0])
            raise ValueError(
                f"normals[{index}]={_row(normals, index)} has |n|="
                f"{float(lengths[index])!r}: the outward normal of a box face "
                f"is a "
                f"unit vector")
        skew = np.flatnonzero(np.count_nonzero(normals, axis=1) != 1)
        if skew.size:
            index = int(skew[0])
            raise ValueError(
                f"normals[{index}]={_row(normals, index)}: a conformed "
                f"surface is axis aligned, so each normal is exactly one "
                f"+-1 entry")
        dA = _array("dA", self.dA, (n_surface,), float, sizes)
        empty = np.flatnonzero(~(dA > 0.0))
        if empty.size:
            index = int(empty[0])
            raise ValueError(
                f"dA[{index}]={float(dA[index])!r}: a face area must be "
                f"positive -- a sample with no area carries no flux")

        arrays = {
            "freqs": freqs,
            "coordinates": coordinates,
            "normals": normals,
            "face_id": _array("face_id", self.face_id, (n_surface,), np.int8,
                              sizes),
            "dA": dA,
            "E_t": _array("E_t", self.E_t, (n_freq, n_surface, 2),
                          np.complex128, sizes),
            "H_t": _array("H_t", self.H_t, (n_freq, n_surface, 2),
                          np.complex128, sizes),
            "J_s": _array("J_s", self.J_s, (n_freq, n_surface, 3),
                          np.complex128, sizes),
            "M_s": _array("M_s", self.M_s, (n_freq, n_surface, 3),
                          np.complex128, sizes),
            "flux": _array("flux", self.flux, (n_freq,), float, sizes),
            "flux_face": _array("flux_face", self.flux_face,
                                (n_freq, n_surface), np.complex128, sizes),
        }
        for name, arr in arrays.items():
            _require_finite(name, arr)
        for name in ("J_s", "M_s"):
            vec = arrays[name]
            along = np.abs(np.einsum("fqc,qc->fq", vec, normals))
            scale = float(np.abs(vec).max())
            worst = float(along.max())
            if scale == 0.0 or worst <= _NORMAL_TOL * scale:
                continue
            freq_i, sample_i = np.unravel_index(int(along.argmax()), along.shape)
            raise ValueError(
                f"{name}[{freq_i}, {sample_i}]="
                f"{_row(vec.reshape(-1, 3), freq_i * n_surface + sample_i)} "
                f"has |{name} . n_hat|={worst!r}, which is "
                f"{worst / scale!r} of max|{name}|={scale!r}: the equivalent "
                f"current of a face is tangential to it, because the writer "
                f"formed it by crossing the unit normal with a tangential "
                f"field")
        for name in ("face_id", "E_t", "H_t", "J_s", "M_s", "flux",
                     "flux_face"):
            object.__setattr__(self, name, arrays[name])


def load_surface_dump(path):
    """Read a ``.npz`` written by ``SurfaceRecorder.save_npz``.

    Parameters
    ----------
    path : str or os.PathLike
        The archive.  ``numpy.load`` is used without ``mmap`` and without
        pickle, so a file that is not a plain array archive is refused by
        :mod:`numpy` rather than executed.

    Returns
    -------
    SurfaceDump
        The record, validated (see the class docstring for the shape of every
        member).

    Raises
    ------
    ValueError
        If the archive is not a Huygens surface dump: a key is missing, the
        ``schema_version`` is not :data:`SCHEMA_VERSION`, the writer marked it
        ``stray``, an array has a shape that does not agree with ``freqs`` and
        ``coordinates``, a normal is not a unit axis-aligned vector, a face
        area is not strictly positive, or a field array holds a non-finite
        entry.  Every message names the offending key and index, because the
        caller's next move is to find out which recording produced it.
    """
    name = os.fspath(path)
    prefix = f"load_surface_dump: {name}: "
    try:
        with np.load(name, allow_pickle=False) as data:
            missing = [key for key in _KEYS if key not in data.files]
            if missing:
                raise ValueError(
                    f"not a Huygens surface archive: missing key(s) "
                    f"{', '.join(missing)}")
            raw = {key: data[key] for key in _KEYS}
        return SurfaceDump(**raw)
    except ValueError as exc:
        raise ValueError(prefix + str(exc)) from None

# ---------------------------------------------------------------------------
# The transform.  The questions above used to be open here; each is now
# resolved against docs/design/3d_ntff_te_spec.md, by section, and the
# formulas there are normative -- nothing below re-derives them.
#
# Q1  J_s/M_s or E_t/H_t?  -> section 1: the stored equivalent currents.  They
#                              are already ``n_hat x H`` and ``-n_hat x E`` as
#                              full 3-vectors whose normal component is zero,
#                              so the outward cross products are the writer's
#                              job and were done there; the transform is a
#                              plain phase sum, not a reconstruction from a
#                              two-component tangential basis.
# Q2  Spatial quadrature.  -> section 2: the one-point midpoint rule per patch,
#                              phase at the recorded patch centre, ``dA`` its
#                              weight -- applied once, never twice.
# Q3  D or G, peak or rms. -> section 4: ``D`` is self-contained, dividing by
#                              the radiated power this module integrates.
#                              ``G`` needs the input power, which the archive
#                              does not record, so it is computed only when the
#                              caller passes ``p_in_w`` and is ``None``
#                              otherwise, with a warning.
# Q4  Sample position and the H half-step. -> resolved by the archive, not
#                              here: the recorder writes the sample
#                              coordinates it accumulated at, and de-biases
#                              the staggered ``H`` phasor by ``cos(pi f dt)``
#                              (its ``colocation_rule``), so ``E_t`` and
#                              ``H_t`` -- and hence ``J_s`` and ``M_s`` -- are
#                              already co-located at the patch centre.  No
#                              half-step is removed and no sample is displaced.
# Q6  Angles and polarisation. -> section 3: ``rhat`` from ``+Z``, ``phi`` from
#                              ``+X``, reporting ``E_theta`` and ``E_phi``.
# Q7  Direct sum or FFT.   -> section 2: the direct phase sum.  The angle axis
#                              is walked in blocks sized so the
#                              ``(n_angle, n_surface)`` phase matrix is never
#                              held whole, and this route stays the reference
#                              an FFT could be graded against.
# Q8  Analytic validation. -> asserted in tests/test_ntff.py against the
#                              Hertzian dipole: ``D = 1.5`` at 90 degrees, a
#                              ``sin(theta)`` pattern, the fixture's own flux
#                              against ``eta_0 k^2 m^2 / (12 pi)``, and the
#                              pattern's absolute amplitude against
#                              ``j eta_0 k m / (4 pi)``.
#
# TODO(TE) Q5  Input power with the box inside a PML is the one question still
#              open: ``P_in`` is not in the archive.  The writer records the
#              power crossing the surface, not the power the source delivered,
#              so a gain needs a number only the caller has -- ``p_in_w``.  A
#              resolved answer needs a new schema field ``p_in_w`` written by
#              ``SurfaceRecorder.save_npz``; until then this module refuses to
#              estimate one, warns, and returns ``G = None``.
# ---------------------------------------------------------------------------

#: Bytes per ``complex128`` entry of the phase matrix.
_PHASE_BYTES = 16

#: The phase matrix is ``(n_angle, n_surface)`` and is never held whole: the
#: angle axis is walked in blocks whose phase block stays under this budget,
#: whatever the size of the archive.
_BLOCK_BYTES = 64 << 20

#: The angular grid :func:`far_field` integrates the radiated power on.  It is
#: midpoint in both angles -- spectrally accurate in ``phi``, where the
#: integrand is periodic, and second order in ``theta`` -- and it is fixed
#: rather than inherited from the caller's angles, because ``P_rad`` is a
#: property of the surface and not of the pattern anyone asked to see.  For the
#: smooth patterns this kernel radiates the angular residual is orders of
#: magnitude below the surface-quadrature one.
_P_RAD_N_THETA = 64
_P_RAD_N_PHI = 128


def integration_angles(n_theta, n_phi):
    """A midpoint angular grid over the whole sphere, in radians.

    One point per cell centre: ``theta_m = (m + 1/2) pi / n_theta`` over
    ``(0, pi)`` and ``phi_n = (n + 1/2) 2 pi / n_phi`` over ``(0, 2 pi)``.
    ``theta`` is the slow axis, ``phi`` the fast one, and both come back flat
    and ready for :func:`far_field`: the same rule
    :func:`total_radiated_power` integrates with, so a caller who wants the
    pattern on the power grid gets both from one call.

    Parameters
    ----------
    n_theta, n_phi : int
        Cells along each angle; at least one.

    Returns
    -------
    theta, phi : (n_theta * n_phi,) float64
        Cell centres, radians.
    """
    nt, nph = int(n_theta), int(n_phi)
    if nt < 1 or nph < 1:
        raise ValueError(
            f"n_theta={n_theta!r}, n_phi={n_phi!r}: a midpoint grid needs at "
            f"least one cell on each angle")
    theta = (np.arange(nt) + 0.5) * (math.pi / nt)
    phi = (np.arange(nph) + 0.5) * (2.0 * math.pi / nph)
    th, ph = np.meshgrid(theta, phi, indexing="ij")
    return th.ravel(), ph.ravel()


def _flatten_angles(theta, phi):
    """Broadcast the two angles against each other and flatten both."""
    th = np.asarray(theta, dtype=float)
    ph = np.asarray(phi, dtype=float)
    try:
        th, ph = np.broadcast_arrays(th, ph)
    except ValueError:
        raise ValueError(
            f"theta of shape {th.shape} and phi of shape {ph.shape} do not "
            f"broadcast: one of them may be a grid axis of the other, but not "
            f"both ways round") from None
    return np.ravel(th), np.ravel(ph)


def _unit_vectors(theta, phi):
    """``rhat``, ``e_theta`` and ``e_phi`` at flat angles, each ``(n, 3)``.

    Section 3 of the specification: the polar axis is ``+Z`` and ``phi`` is
    measured from ``+X``.
    """
    sin_t, cos_t = np.sin(theta), np.cos(theta)
    sin_p, cos_p = np.sin(phi), np.cos(phi)
    r_hat = np.stack((sin_t * cos_p, sin_t * sin_p, cos_t), axis=-1)
    e_theta = np.stack((cos_t * cos_p, cos_t * sin_p, -sin_t), axis=-1)
    e_phi = np.stack((-sin_p, cos_p, np.zeros_like(theta)), axis=-1)
    return r_hat, e_theta, e_phi


def _frequency_index(dump, freq_index):
    """``freq_index`` checked against the archive's frequency axis."""
    n_freq = int(dump.freqs.shape[0])
    index = int(freq_index)
    if index != freq_index or not 0 <= index < n_freq:
        raise IndexError(
            f"freq_index={freq_index!r}: the archive holds {n_freq} "
            f"frequenc{'y' if n_freq == 1 else 'ies'}, so the index runs "
            f"0..{n_freq - 1}")
    return index


def _wavenumber(freq):
    """Free-space ``k = 2 pi f / c0`` of one archive frequency, in 1/m."""
    freq = float(freq)
    if not math.isfinite(freq) or freq <= 0.0:
        raise ValueError(
            f"freq={freq!r}: a positive finite frequency in Hz is required "
            f"before there is a wavenumber to sum phases with")
    return 2.0 * math.pi * freq / C0


def _block_rows(n_surface, n_angle, block):
    """Angles per block: ``block`` as given, or sized to the byte budget."""
    if block is None:
        rows = _BLOCK_BYTES // (_PHASE_BYTES * n_surface)
    else:
        rows = int(block)
        if rows < 1:
            raise ValueError(
                f"block={block!r}: a block of angles must hold at least one "
                f"angle")
    return max(1, min(rows, n_angle))


def _phase_blocks(r_hat, coordinates, k, block):
    """Yield ``(start, stop, phase)``, ``phase`` a ``(stop - start, n_q)``."""
    n_angle = int(r_hat.shape[0])
    rows = _block_rows(int(coordinates.shape[0]), n_angle, block)
    coords_t = coordinates.T
    for start in range(0, n_angle, rows):
        stop = min(start + rows, n_angle)
        yield start, stop, np.exp(1j * k * (r_hat[start:stop] @ coords_t))


def radiation_vectors(dump, theta, phi, *, freq_index=0, block=None):
    """The radiation integrals ``J_tilde`` and ``M_tilde``, ``(n_angle, 3)``.

    Section 1 of the specification, with the patch area applied exactly once::

        J_tilde(rhat) = sum_q J_s[q] exp(+j k rhat . r_q) dA[q]
        M_tilde(rhat) = sum_q M_s[q] exp(+j k rhat . r_q) dA[q]

    Parameters
    ----------
    dump : SurfaceDump
        The archive.
    theta, phi : float or array_like
        Angles in radians, broadcast against each other.  ``rhat`` is from
        ``+Z``, ``phi`` from ``+X`` (section 3).
    freq_index : int, optional
        Which frequency of the archive to transform; ``0`` by default.
    block : int, optional
        Angles per phase block.  ``None`` sizes the block so the phase matrix
        stays under :data:`_BLOCK_BYTES`.  The result does not depend on it.

    Returns
    -------
    J_tilde, M_tilde : (n_angle, 3) complex128
        In ``A m`` and ``V m``: a surface current times a patch area.
    """
    index = _frequency_index(dump, freq_index)
    k = _wavenumber(dump.freqs[index])
    r_hat, _, _ = _unit_vectors(*_flatten_angles(theta, phi))
    j_s = dump.J_s[index] * dump.dA[:, None]
    m_s = dump.M_s[index] * dump.dA[:, None]
    n_angle = int(r_hat.shape[0])
    j_tilde = np.empty((n_angle, 3), dtype=np.complex128)
    m_tilde = np.empty((n_angle, 3), dtype=np.complex128)
    for start, stop, phase in _phase_blocks(r_hat, dump.coordinates, k, block):
        j_tilde[start:stop] = phase @ j_s
        m_tilde[start:stop] = phase @ m_s
    return j_tilde, m_tilde


@dataclass(frozen=True)
class FarField:
    """One far-field evaluation, and the normalisations built from it.

    Everything here comes from ``F = r E_far`` (section 1's
    ``exp(-j k r) / r`` factored out), so every entry is independent of any
    radius: ``U`` is already ``r^2`` times the power density, and no ``r`` was
    invented to divide out again.

    Attributes
    ----------
    freq : float
        The archive frequency that was transformed, in Hz.
    theta, phi : (n_angle,) float64
        The angles handed in, flattened, in radians.
    E_theta, E_phi : (n_angle,) complex128
        The two spherical components of ``F``, in V.
    U : (n_angle,) float64
        Radiation intensity ``(|E_theta|^2 + |E_phi|^2) / (2 eta_0)``, in W
        per steradian once the ``r^2`` is divided out.
    P_rad : float
        Radiated power in W: ``4 pi`` times the mean of ``U`` over the sphere,
        integrated here by midpoint quadrature on
        :data:`_P_RAD_N_THETA` x :data:`_P_RAD_N_PHI` cells (section 4).
    D : (n_angle,) float64
        Directivity ``4 pi U / P_rad``, dimensionless.
    G : (n_angle,) float64 or None
        Gain ``4 pi U / p_in``, dimensionless, or ``None`` when the caller did
        not supply the input power -- the archive does not record one.
    p_in : float or None
        The input power ``G`` was normalised by, in W.
    """

    freq: float
    theta: np.ndarray
    phi: np.ndarray
    E_theta: np.ndarray
    E_phi: np.ndarray
    U: np.ndarray
    P_rad: float
    D: np.ndarray
    G: np.ndarray | None
    p_in: float | None


def _angular_fields(dump, theta, phi, k, index, block):
    """``E_theta``, ``E_phi`` and ``U`` at flat angles, block by block."""
    r_hat, e_theta, e_phi = _unit_vectors(theta, phi)
    j_s = dump.J_s[index] * dump.dA[:, None]
    m_s = dump.M_s[index] * dump.dA[:, None]
    n_angle = int(theta.shape[0])
    e_th = np.empty(n_angle, dtype=np.complex128)
    e_ph = np.empty(n_angle, dtype=np.complex128)
    scale = 1j * k / (4.0 * math.pi)
    for start, stop, phase in _phase_blocks(r_hat, dump.coordinates, k, block):
        r_blk = r_hat[start:stop]
        j_tilde = phase @ j_s
        m_tilde = phase @ m_s
        # rhat x (rhat x A) = rhat (rhat . A) - A, the identity the literal
        # nested cross product satisfies; tests/test_ntff.py checks this form
        # against a slow literal cross product to 1e-12.
        along = np.einsum("qc,qc->q", r_blk, j_tilde)
        f_vec = scale * (ETA0 * (r_blk * along[:, None] - j_tilde)
                         + np.cross(r_blk, m_tilde))
        e_th[start:stop] = np.einsum("qc,qc->q", f_vec, e_theta[start:stop])
        e_ph[start:stop] = np.einsum("qc,qc->q", f_vec, e_phi[start:stop])
    u = (np.abs(e_th) ** 2 + np.abs(e_ph) ** 2) / (2.0 * ETA0)
    return e_th, e_ph, u


def _radiated_power(dump, k, index, block):
    """The integral of ``U`` over the sphere, in W."""
    theta, phi = integration_angles(_P_RAD_N_THETA, _P_RAD_N_PHI)
    _, _, u = _angular_fields(dump, theta, phi, k, index, block)
    d_omega = ((math.pi / _P_RAD_N_THETA)
               * (2.0 * math.pi / _P_RAD_N_PHI))
    return float(np.sum(u * np.sin(theta)) * d_omega)


def far_field(dump, theta, phi, *, freq_index=0, p_in_w=None, block=None):
    """The far field of one recorded surface at the given angles.

    Section 1 of the specification assembled into the pattern::

        F(rhat) = (j k / 4 pi) [ eta_0 rhat x (rhat x J_tilde)
                                 + rhat x M_tilde ]
        U       = (|E_theta|^2 + |E_phi|^2) / (2 eta_0)
        D       = 4 pi U / P_rad
        G       = 4 pi U / p_in

    ``F`` is ``r`` times the far field, so ``U``/``D``/``G`` never need a
    radius.  ``P_rad`` is ``4 pi`` times the mean of ``U`` over the sphere --
    the same thing as the integral of ``U`` over the solid angle, written the
    way section 4 writes it -- and is integrated here, not accepted from the
    archive's ``flux`` (which is the direct Poynting integral and the yardstick
    the angular one is checked against in the tests).

    ``G`` needs an input power the archive does not hold, so it is computed
    only when ``p_in_w`` is passed; otherwise no value is estimated, no default
    is invented, and a :class:`RuntimeWarning` says why.

    Parameters
    ----------
    dump : SurfaceDump
        The archive.
    theta, phi : float or array_like
        Angles in radians, broadcast against each other.
    freq_index : int, optional
        Which frequency of the archive to transform; ``0`` by default.
    p_in_w : float, optional
        Input power in W, for the gain.  Must be positive and finite.
    block : int, optional
        Angles per phase block; the result is invariant to it.

    Returns
    -------
    FarField
        Pattern, ``P_rad``, directivity and gain.

    Raises
    ------
    IndexError
        If ``freq_index`` is not a frequency of the archive.
    ValueError
        If the frequency has no wavenumber, if ``p_in_w`` is not a positive
        finite power, or if the surface radiates nothing at all (no
        directivity to report).
    """
    index = _frequency_index(dump, freq_index)
    freq = float(dump.freqs[index])
    k = _wavenumber(freq)
    if p_in_w is None:
        p_in = None
    else:
        p_in = float(p_in_w)
        if not math.isfinite(p_in) or p_in <= 0.0:
            raise ValueError(
                f"p_in_w={p_in!r}: an input power must be positive and finite "
                f"to normalise a gain by")
    th, ph = _flatten_angles(theta, phi)
    e_theta, e_phi, u = _angular_fields(dump, th, ph, k, index, block)
    p_rad = _radiated_power(dump, k, index, block)
    if p_rad <= 0.0:
        raise ValueError(
            f"freq={freq!r}: the surface radiates nothing (P_rad={p_rad!r} W), "
            f"so it has no directivity to report")
    d = 4.0 * math.pi * u / p_rad
    if p_in is None:
        warnings.warn(
            f"far_field: input power is absent from the archive -- it records "
            f"the power crossing the surface, not the power the source "
            f"delivered -- so gain cannot be computed; pass p_in_w= to get "
            f"one.  Directivity is unaffected.",
            RuntimeWarning, stacklevel=2)
        g = None
    else:
        g = 4.0 * math.pi * u / p_in
        g.flags.writeable = False
    for arr in (th, ph, e_theta, e_phi, u, d):
        arr.flags.writeable = False
    return FarField(freq=freq, theta=th, phi=ph, E_theta=e_theta,
                    E_phi=e_phi, U=u, P_rad=p_rad, D=d, G=g, p_in=p_in)


def total_radiated_power(far):
    """The radiated power :func:`far_field` measured, in W.

    Returned as measured: the quadrature is the one :func:`far_field` ran on
    :data:`_P_RAD_N_THETA` x :data:`_P_RAD_N_PHI` midpoint cells, not on
    whatever angles the caller asked to see.
    """
    return float(far.P_rad)
