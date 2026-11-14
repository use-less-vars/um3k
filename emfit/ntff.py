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

The far field is *not* here.  See "What is not here" at the end of this
docstring for why, and for the questions that have to be answered first.

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
from dataclasses import dataclass

import numpy as np

__all__ = ["SCHEMA_VERSION", "SurfaceDump", "load_surface_dump"]

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
# TODO(TE): the transform itself.  Deliberately absent -- no Kirchhoff
# integral, no Green's function, no angular spectrum, no gain -- because the
# conventions it would have to fix are open questions, written up in
# docs/design/3d_ntff_te_query.md.  One marker per question: whichever ruling
# arrives, this is where its code goes, and nothing above it has to move.
#
# TODO(TE) Q1  Far field from J_s/M_s (the radiation integrals) or from the
#              tangential fields E_t/H_t (Stratton-Chu): which is the
#              reference form, and do they differ on a closed surface?
# TODO(TE) Q2  Spatial integration: the one-point midpoint rule per face with
#              dA as its weight, or something of higher order, and over what.
# TODO(TE) Q3  Gain normalisation: is flux (the 0.5 Re of the direct Poynting
#              sum) the accepted P_rad, and is the emitted quantity D or G,
#              peak or rms?
# TODO(TE) Q4  Sample position: the recorded coordinates as written, or
#              displaced half a cell along the normal; and whether H keeps a
#              half-step exp(+j w dt / 2) beyond the writer's debias.
# TODO(TE) Q5  Input power with the box inside a PML: the surface flux, or the
#              source-current integral -0.5 Re(int J . conj(E) dV).
# TODO(TE) Q6  theta/phi convention, and which polarisation basis is reported
#              (E_theta/E_phi, or the IEEE/Ludwig-3 E_co/E_cross pair).
# TODO(TE) Q7  Direct summation versus an FFT route: the cost crossover, and
#              which of the two is the reference for the other.
# TODO(TE) Q8  Analytic validation: the Hertzian dipole (peak D = 1.5 =
#              1.7609 dBi, sin(theta) pattern), the departure from it to be
#              expected, and the analytic value it is graded against.
# ---------------------------------------------------------------------------
