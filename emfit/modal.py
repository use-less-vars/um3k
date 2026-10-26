"""Modal port quantities: project a captured plane onto the line's own mode.

What this module is for
-----------------------
:mod:`emfit.mode_profile` knows the transverse field of the microstrip,
:mod:`emfit.plane_phasor` knows what the time loop's DFT sums mean, and
:mod:`emfit.ports` will fit a line to a set of station phasors.  None of them
turns the four captured plane blocks into the two numbers a port needs -- a
modal voltage and a modal current on a plane.  This module is that step and
nothing else: it does not capture, does not evolve, and does not decide what a
study measures.

The normalisation this module does **not** undo
----------------------------------------------
:class:`~emfit.mode_profile.ModeProfile`'s field arrays are normalised to
**unit modal power over the projection window, not to 1 V**:
``0.5 Re(v_mode conj(i_mode)) = 1 W`` exactly, and so does the discrete
``0.5 / eta_eff * sum(e_y**2 + e_z**2)`` over the edges
:meth:`~emfit.mode_profile.ModeProfile.plane_window` selects for the default
201 x 77 plane.  The 1 V convention survives only as a diagnostic --
``v_mode`` is 9.9558 V on the converged section rather than 1 V.

So the mode is used here as a **unit-power basis**, and the amplitude of the
field on the plane is a complex scalar ``a`` that means "``a`` times the mode",
not "``a`` volts".  Nothing in this module divides by ``v_mode``: a caller who
wants the 1 V convention can scale the returned phasors by ``1 / v_mode``
themselves, and is welcome to, but the power pair returned here is the one that
satisfies ``0.5 Re(V conj(I)) = P`` without a fudge factor.

How the projection works, and why it is a least squares
-------------------------------------------------------
Write the plane's own phasors as ``E`` and the mode's as ``e`` (both live on the
*plane's* lattice, via :func:`plane_mode`).  The best complex multiple of ``e``
in the least-squares sense is

    ``a_E = sum(e . E) / sum(e . e)``

summed over both transverse components and both transverse axes -- no
conjugation, because ``e`` is real.  Applying the same rule to the magnetic
side, ``a_H = sum(h . H) / sum(h . h)``, then

    ``V = a_E * v_mode``,  ``I = a_H * i_mode``.

This is the only pairing that makes the two sides agree about power.  For a
single forward wave ``E = a e`` and ``H = a h`` so ``a_E = a_H = a``, and
because ``0.5/eta_eff sum(e**2) = 1 W`` and ``h = +-e/eta_eff``,

    ``0.5 Re(V conj(I)) = 0.5 |a|**2 v_mode i_mode = |a|**2 * 1 W``.

A wave travelling the other way reverses ``H`` against ``E`` (the profile's
``h_y = -e_z/eta_eff`` carries that sign), so it gives ``a_H = -a_b`` while
``a_E = +a_b``: ``V = (a_f + a_b) v_mode`` and ``I = (a_f - a_b) i_mode``, which
is the two-wave model :func:`emfit.ports.travelling_waves` inverts, with
``gamma_i = -gamma_v`` and :attr:`~emfit.ports.StationFit.mode_purity` the
residual that says so.

Which characteristic impedance this module quotes
-------------------------------------------------
``v_mode / i_mode`` -- the **power-current** impedance whose product with the
current reproduces the unit power.  It is *not* the profile's own
:attr:`~emfit.mode_profile.ModeProfile.z0`: on the coarse section the two read
64.3839 ohm and 66.4084 ohm, a 3.06 % difference, because the different
definitions of ``Z0`` (power-current, power-voltage, quasistatic ``1/(c C)``)
agree only for the exact mode.  The number quoted here is the one the
projection's current actually pairs with, so ``0.5 Re(V conj(I))`` and
``|I|**2 Re(Z0)/2`` agree to roundoff; :attr:`PlaneMode.z0_power` says so in
its own docstring, and nothing compares it with the electrostatic ``z0``
silently.

Which surface of the profile is used
------------------------------------
``ModeProfile._projection_slices`` and ``_modal_power`` are private, so this
module goes through the public :meth:`~emfit.mode_profile.ModeProfile.plane_window`
and reads ``.ycell_znode`` / ``.ynode_zcell`` from the :class:`PlaneWindow` it
returns.  That is the surface the profile documents as its placement API, and
it means a change to the slicing stays inside one module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .materials import C0
from .mode_profile import ModeProfile
from .plane_phasor import PLANE_CONVENTION, destagger
from .ports import (
    BetaFit,
    StationFit,
    deembed_reflection,
    fit_beta,
    fit_station_impedance,
    power_current_check,
    reflection,
    transmission,
    travelling_waves,
)

__all__ = [
    "PLANE_COMPONENTS",
    "ModalLine",
    "ModalSparams",
    "PlaneMode",
    "ResidualGate",
    "ResidualReport",
    "StationPhasors",
    "modal_line_quantities",
    "modal_sparams",
    "modal_station_phasors",
    "plane_mode",
    "residual_gate",
    "residual_gates",
]

#: The four plane blocks a capture writes, in the order the projection reads
#: them (``e_y``/``h_z`` on the y-cell/z-node lattice, ``e_z``/``h_y`` on the
#: y-node/z-cell one).
PLANE_COMPONENTS = ("plane_Ey", "plane_Ez", "plane_Hy", "plane_Hz")

#: The default FDTD cross-section, by value: ``ModeProfile.plane_window``'s own
#: defaults, repeated here so this module depends on the public signature and
#: not on ``mode_profile``'s private ``_FDTD_*`` constants.
_DEFAULT_NYN = 201
_DEFAULT_NZN = 77
_DEFAULT_K_STRIP = 16

#: Relative tolerance for "the same bin".  The frequency the capture recorded
#: and the one a caller names are the same number computed twice, so the only
#: slack needed is the last bits of a float round trip.  The comparison is
#: relative and has no absolute floor, because one of the two numbers compared
#: is a time step of order ``1e-13`` s, where a floor such as ``max(1.0, ...)``
#: would swallow any mismatch whatever: ``dt`` and ``10 * dt`` would compare
#: equal and the half-step angle would then be computed from the wrong step.
_BIN_RTOL = 1.0e-9

_UNSET = object()


# ---------------------------------------------------------------------------
# reading the capture: a mapping, an npz, or an object with the attributes
# ---------------------------------------------------------------------------
def _component(planes, key, default=_UNSET):
    """Return one plane block from a mapping, an ``npz`` file or an object."""
    try:
        return planes[key]
    except (KeyError, IndexError, TypeError):
        pass
    try:
        return getattr(planes, key)
    except AttributeError:
        if default is not _UNSET:
            return default
        raise ValueError(
            f"the plane stack has no {key!r}: pass the capture as a mapping "
            f"(or an npz/object) with the keys {', '.join(PLANE_COMPONENTS)}, "
            f"got {type(planes).__name__}") from None


def _same_bin(a: float, b: float) -> bool:
    """True when two numbers are the same to a float round trip, relatively.

    Used for a recorded frequency against a requested one and for a recorded
    time step against a requested one, so the tolerance is relative with no
    absolute floor: an absolute 1e-9 s floor would call a step of 1e-13 s and
    ten times it "the same dt", and the half-step angle ``pi f dt`` would then
    be computed from the wrong number.
    """
    return math.isclose(float(a), float(b), rel_tol=_BIN_RTOL, abs_tol=0.0)


def _block(planes, key, expected_shape, stations):
    """Select ``stations`` from one plane block, refusing a wrong lattice."""
    raw = np.asarray(_component(planes, key), dtype=complex)
    shape = tuple(int(n) for n in expected_shape)
    if raw.ndim != 3:
        raise ValueError(
            f"{key} must be a stack of planes shaped (n_stations, {shape[0]}, "
            f"{shape[1]}), got shape {raw.shape}")
    if raw.shape[1:] != shape:
        raise ValueError(
            f"{key} planes are {raw.shape[1:]}, but this mode needs {shape}: the "
            "mode is placed on the plane's own lattice, so a transposed, "
            "unclipped or differently meshed capture will not project")
    if np.any(stations >= raw.shape[0]) or np.any(stations < -raw.shape[0]):
        raise ValueError(
            f"{key} holds {raw.shape[0]} stations, so {stations.tolist()} is "
            "out of range")
    return raw[stations]


# ---------------------------------------------------------------------------
# the mode, placed on the plane
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PlaneMode:
    """A :class:`ModeProfile` laid out on an FDTD plane, ready to project.

    The four arrays are *plane-shaped*: ``e_y``/``h_z`` on the y-cell/z-node
    lattice ``(nyn - 1, nzn)`` and ``e_z``/``h_y`` on the y-node/z-cell one
    ``(nyn, nzn - 1)``, i.e. the same shapes as a capture's ``plane_Ey`` and
    ``plane_Ez`` blocks.  Zeros outside the placed window, so an unclipped mode
    sums to nothing where the plane carries nothing.

    Attributes:
        e_y: Transverse electric field on the y-cells [V] (mode units).
        e_z: Transverse electric field on the z-cells [V] (mode units).
        h_y: Magnetic field on the z-cells, ``-e_z / eta_eff`` [A].
        h_z: Magnetic field on the y-cells, ``+e_y / eta_eff`` [A].
        v_mode: The profile's modal voltage for full amplitude [V].
        i_mode: The profile's modal current for full amplitude [A], defined so
            that ``0.5 * v_mode * i_mode = power`` exactly.
        eta_eff: Wave impedance of the substrate [ohm].
        power: The power the profile claims the window carries [W], normally
            ``1.0`` by construction.
        report: :meth:`PlaneWindow.report` for the placement, so a clipped
            placement says so instead of hiding in the zeros.
    """

    e_y: np.ndarray
    e_z: np.ndarray
    h_y: np.ndarray
    h_z: np.ndarray
    v_mode: float
    i_mode: float
    eta_eff: float
    power: float
    report: str

    @property
    def electric_norm(self) -> float:
        """``sum(e_y**2) + sum(e_z**2)``, the denominator of the projection."""
        return float(np.sum(self.e_y ** 2) + np.sum(self.e_z ** 2))

    @property
    def magnetic_norm(self) -> float:
        """``sum(h_y**2) + sum(h_z**2)``, the denominator on the magnetic side."""
        return float(np.sum(self.h_y ** 2) + np.sum(self.h_z ** 2))

    @property
    def discrete_power(self) -> float:
        """``0.5 / eta_eff`` times :attr:`electric_norm` [W].

        This is the discrete Poynting sum the profile's normalisation is
        defined by, recomputed from the placed arrays: equal to
        :attr:`power` (1 W) when the placement keeps the whole window.
        """
        return 0.5 * self.electric_norm / self.eta_eff

    @property
    def z0_power(self) -> float:
        """``v_mode / i_mode`` [ohm]: the power-current impedance.

        *Not* :attr:`~emfit.mode_profile.ModeProfile.z0`, which is the
        electrostatic figure.  See the module docstring for the 3 % gap on the
        coarse section.
        """
        return self.v_mode / self.i_mode

    @property
    def shapes(self):
        """The ``(plane_Ey, plane_Ez)`` shapes a capture must match."""
        return self.e_y.shape, self.e_z.shape


def plane_mode(mode: ModeProfile, *, nyn: int = _DEFAULT_NYN,
               nzn: int = _DEFAULT_NZN, k_strip: int = _DEFAULT_K_STRIP,
               iy_strip_centre=None, cell=None) -> PlaneMode:
    """Place ``mode`` in a ``nyn`` x ``nzn`` plane, by integer index shift.

    The window comes from :meth:`ModeProfile.plane_window`, so the clipping,
    the offsets and the refusals are the profile's own; this function only
    copies the four field arrays through the slices it returns and keeps its
    report.  ``nyn`` and ``nzn`` count the plane's **nodes** (a 201 x 77 plane
    has 200 y-cells and 76 z-cells), which is how a capture's ``plane_Ey`` and
    ``plane_Ez`` blocks are shaped.

    Returns:
        A :class:`PlaneMode` whose ``e_y`` is ``(nyn - 1, nzn)`` and whose
        ``e_z`` is ``(nyn, nzn - 1)``.

    Raises:
        ValueError: Whatever :meth:`ModeProfile.plane_window` raises -- a cell
            size that is not the profile's, a strip row below the ground
            plane, or a placement that misses the plane entirely.
    """
    window = mode.plane_window(nyn, nzn, k_strip, iy_strip_centre=iy_strip_centre,
                              cell=cell)
    e_y = np.zeros((nyn - 1, nzn))
    e_z = np.zeros((nyn, nzn - 1))
    h_y = np.zeros((nyn, nzn - 1))
    h_z = np.zeros((nyn - 1, nzn))

    (src, dst) = window.ycell_znode
    e_y[dst] = mode.e_y[src]
    h_z[dst] = mode.h_z[src]
    (src, dst) = window.ynode_zcell
    e_z[dst] = mode.e_z[src]
    h_y[dst] = mode.h_y[src]

    return PlaneMode(
        e_y=e_y,
        e_z=e_z,
        h_y=h_y,
        h_z=h_z,
        v_mode=float(mode.v_mode),
        i_mode=float(mode.i_mode),
        eta_eff=float(mode.eta_eff),
        power=float(mode.power),
        report=window.report(),
    )


# ---------------------------------------------------------------------------
# the projection: plane phasors -> modal voltage and current per station
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StationPhasors:
    """Modal voltage and current on each of the stations asked for.

    ``v`` and ``i`` satisfy ``0.5 Re(v conj(i)) = P`` in watts, with ``P`` the
    power the projected field carries: ``|a|**2`` times the mode's own 1 W for
    a full mode amplitude ``a``.  Every quantity is in the profile's unit-power
    normalisation, so ``v`` is not in volts unless the caller has rescaled by
    ``v_mode``.

    Attributes:
        v: Modal voltage phasors [V, mode units], shaped like ``stations``.
        i: Modal current phasors [A, mode units].
        station_indices: The indices into the capture's station axis, as given.
        f0: The DFT bin these phasors belong to [Hz].
        dt: The capture's time step [s], kept so the half-step removal is
            auditable after the fact.
        a_e: The electric overlap amplitude ``a_E`` per station, dimensionless.
        a_h: The magnetic overlap amplitude ``a_H`` per station.
        z0_power: ``v_mode / i_mode`` [ohm], the impedance these two phasors
            are quoted on.
    """

    v: np.ndarray
    i: np.ndarray
    station_indices: np.ndarray
    f0: float
    dt: float
    a_e: np.ndarray
    a_h: np.ndarray
    z0_power: float

    @property
    def power(self) -> np.ndarray:
        """``0.5 Re(v conj(i))`` per station [W]."""
        return 0.5 * np.real(self.v * np.conj(self.i))

    @property
    def amplitude_mismatch(self) -> np.ndarray:
        """``|a_e - a_h|`` per station, dimensionless.

        Zero for a single travelling mode.  A non-zero value is the project's
        own reading of "the two sides of the plane are not one mode" -- the
        same question :attr:`~emfit.ports.StationFit.mode_purity` asks of a
        fitted line, but answerable from one station.
        """
        return np.abs(self.a_e - self.a_h)

    def report(self) -> str:
        return (f"{self.v.size} stations at f0 = {self.f0:.6g} Hz, "
                f"|V| {np.abs(self.v).min():.6g}..{np.abs(self.v).max():.6g} V, "
                f"max |a_e - a_h| = {self.amplitude_mismatch.max():.3g}")


def modal_station_phasors(planes, mode: PlaneMode, stations, *, f0: float,
                          dt: float, convention=PLANE_CONVENTION,
                          destagger_h: bool = True) -> StationPhasors:
    """Project the captured plane blocks onto ``mode`` station by station.

    ``planes`` is the capture: either a mapping (a dict, an ``npz`` file) or any
    object with ``plane_Ey``, ``plane_Ez``, ``plane_Hy`` and ``plane_Hz``
    attributes, each shaped ``(n_stations, ...)`` on the lattice
    :func:`plane_mode` produced.  ``stations`` are indices into that first axis
    -- *not* positions in metres; a caller who needs positions for
    :func:`modal_line_quantities` has them in the capture's own
    ``plane_station_x``.

    Two things are refused rather than fixed up:

    * a frequency that is not the capture's own bin.  A DFT bin is not
      interpolatable: asking for 5.0 GHz from a capture whose bin sits at
      4.999 GHz would quietly project a phasor that means something else, so
      ``f0`` and ``dt`` must match whatever the capture recorded (when it
      recorded them).
    * the half-step, unless told otherwise.  :data:`PLANE_CONVENTION` puts the
      electric phasors at ``t^n`` and the magnetic ones at ``t^(n-1/2)`` and
      does **not** remove the ``exp(-j pi f dt)`` that leaves, so the magnetic
      blocks are de-staggered by :func:`emfit.plane_phasor.destagger` before
      they are projected.  ``destagger_h=False`` exists to show that it
      matters, and for a caller whose blocks are already collocated.

    ``convention`` is compared **by value**, not by identity: the convention
    that arrives with a capture is an equal string held as a *distinct* object
    (an ``npz`` or a JSON record does not hand back the module's own constant),
    so an identity test would refuse the capture's own convention.

    Returns:
        A :class:`StationPhasors`.  See its attributes for the normalisation.

    Raises:
        ValueError: If a block is missing or on another lattice, if a station
            index is out of range, if ``f0``/``dt`` disagree with the capture's
            own, if ``convention`` is not :data:`PLANE_CONVENTION`, or if the
            placed mode carries no field (in which case there is nothing to
            project onto).
    """
    if convention != PLANE_CONVENTION:
        raise ValueError(
            "only PLANE_CONVENTION is implemented: the half-step removal below "
            f"is its inverse, so {convention!r} would need a different factor")

    recorded_f = _component(planes, "plane_f", None)
    recorded_dt = _component(planes, "plane_dt", None)
    if recorded_f is not None and not _same_bin(float(recorded_f), float(f0)):
        raise ValueError(
            f"the planes were captured at {float(recorded_f)!r} Hz, not at the "
            f"{float(f0)!r} Hz bin asked for: a DFT bin is not interpolatable, "
            "so project the capture's own bin")
    if recorded_dt is not None and not _same_bin(float(recorded_dt), float(dt)):
        raise ValueError(
            f"the planes were captured with dt = {float(recorded_dt)!r} s, not "
            f"{float(dt)!r} s: the half-step angle pi f dt is set by the "
            "capture's own time step")

    stations = np.atleast_1d(np.asarray(stations, dtype=int)).ravel()
    if stations.size == 0:
        raise ValueError("no stations asked for: nothing to project")

    e_y = _block(planes, "plane_Ey", mode.e_y.shape, stations)
    e_z = _block(planes, "plane_Ez", mode.e_z.shape, stations)
    h_y = _block(planes, "plane_Hy", mode.e_z.shape, stations)
    h_z = _block(planes, "plane_Hz", mode.e_y.shape, stations)
    if destagger_h:
        h_y = destagger(h_y, f0, dt)
        h_z = destagger(h_z, f0, dt)

    den_e = mode.electric_norm
    den_h = mode.magnetic_norm
    if den_e <= 0.0 or den_h <= 0.0:
        raise ValueError(
            f"the placed mode carries no field (sum e^2 = {den_e!r}, "
            f"sum h^2 = {den_h!r}): {mode.report}")

    a_e = (np.sum(mode.e_y * e_y, axis=(-2, -1))
           + np.sum(mode.e_z * e_z, axis=(-2, -1))) / den_e
    a_h = (np.sum(mode.h_y * h_y, axis=(-2, -1))
           + np.sum(mode.h_z * h_z, axis=(-2, -1))) / den_h

    return StationPhasors(
        v=a_e * mode.v_mode,
        i=a_h * mode.i_mode,
        station_indices=stations,
        f0=float(f0),
        dt=float(dt),
        a_e=a_e,
        a_h=a_h,
        z0_power=mode.z0_power,
    )


# ---------------------------------------------------------------------------
# line quantities from those phasors
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ModalLine:
    """The line the modal phasors describe, on the planes they were taken on.

    ``beta`` and the two travelling amplitudes come from
    :func:`emfit.ports.fit_beta` on the modal voltages; ``z0``, ``gamma_v``,
    ``gamma_i`` and ``mode_purity`` from
    :func:`emfit.ports.fit_station_impedance` on both series at that ``beta``.
    Both are the house fits, applied to modal quantities instead of raw probe
    voltages, and no new estimator is introduced here.

    Attributes:
        f0: The DFT bin everything is referred to [Hz].
        beta_fit: The voltage fit, i.e. ``beta`` and the two amplitudes.
        station_fit: The two-series fit, i.e. ``z0``, the two gammas and the
            reference plane they belong to.
        epsilon_eff: ``(beta * c0 / omega)**2``, dimensionless -- the effective
            permittivity the *measured* phase constant implies, which is the
            one number comparable with
            :attr:`~emfit.mode_profile.ModeProfile.eps_eff`.
        z0_power: The impedance the phasors' own power and current imply per
            station [ohm], from :func:`emfit.ports.power_current_check`.
        power_ratio: That impedance divided by ``Re(z0)``, per station,
            dimensionless: 1 for a pure mode, and further out than the
            standing-wave bound then the pair is not one mode.
    """

    f0: float
    beta_fit: BetaFit
    station_fit: StationFit
    epsilon_eff: float
    z0_power: np.ndarray
    power_ratio: np.ndarray

    @property
    def beta(self) -> float:
        """The fitted phase constant [rad/m]; positive, belonging to ``+x``."""
        return float(self.beta_fit.beta)

    @property
    def z0(self) -> complex:
        """The fitted characteristic impedance at the reference plane [ohm]."""
        return self.station_fit.z0

    @property
    def mode_purity(self) -> float:
        """``|gamma_i + gamma_v|``: 0 when the two series are one mode."""
        return float(self.station_fit.mode_purity)

    @property
    def reference_plane(self) -> float:
        """The ``x`` the amplitudes and ``z0`` are referred to [m]."""
        return float(self.station_fit.reference_plane)

    @property
    def wavelength(self) -> float:
        """``2 pi / beta``, the guide wavelength [m]."""
        return 2.0 * np.pi / self.beta

    def report(self) -> str:
        return (f"f0 = {self.f0:.6g} Hz, beta = {self.beta:.6g} rad/m, "
                f"eps_eff = {self.epsilon_eff:.6g}, "
                f"z0 = {abs(self.z0):.6g} ohm at {1000.0 * self.reference_plane:.4g} mm "
                f"(angle {self.station_fit.phase_deg:.3g} deg, mode purity "
                f"{self.mode_purity:.3g}, {self.station_fit.n_stations} stations)")


def modal_line_quantities(v, i, stations_m, *, f0: float,
                          alpha: float = 0.0) -> ModalLine:
    """Fit ``beta``, ``eps_eff`` and ``z0`` to modal phasors at several stations.

    ``stations_m`` are the station positions [m] the phasors belong to, in any
    order; ``v`` and ``i`` are the modal pairs, e.g. from :func:`modal_station_phasors`.
    ``alpha`` is an attenuation constant [1/m] if one is already known, and
    defaults to zero, which is the lossless model.

    ``eps_eff`` is ``(beta c0 / omega)**2`` and not ``beta**2 c0**2 / omega**2``
    with ``omega = 2 pi f0`` written out twice, so a caller reading the code sees
    the same expression the docstring of
    :attr:`~emfit.mode_profile.ModeProfile.eps_eff` uses: the permittivity the
    measured phase constant implies, which is only equal to the profile's
    electrostatic ``eps_eff`` if the mode travelling on the plane really is the
    profile's mode.

    Raises:
        ValueError: From :func:`emfit.ports.fit_beta` (fewer than three
            stations, non-finite input, a zero span) or from
            :func:`emfit.ports.fit_station_impedance` (fewer than four
            stations, a zero forward amplitude), or here for a length
            mismatch, a non-positive ``f0`` or a negative ``alpha``.
    """
    x = np.asarray(stations_m, dtype=float).ravel()
    v = np.asarray(v, dtype=complex).ravel()
    i = np.asarray(i, dtype=complex).ravel()
    if not x.size == v.size == i.size:
        raise ValueError(
            f"stations_m, v and i must hold the same number of stations, got "
            f"{x.size}, {v.size} and {i.size}")
    f0 = float(f0)
    if not f0 > 0.0:
        raise ValueError(f"f0 must be positive, got {f0!r}")
    if not float(alpha) >= 0.0:
        raise ValueError(f"alpha must be non-negative, got {alpha!r}")

    beta_fit = fit_beta(x, v)
    beta = float(beta_fit.beta)
    omega = 2.0 * np.pi * f0
    epsilon_eff = (beta * C0 / omega) ** 2
    station_fit = fit_station_impedance(x, v, i, beta, alpha=float(alpha))
    z0_power, power_ratio = power_current_check(v, i, station_fit.z0)

    return ModalLine(
        f0=f0,
        beta_fit=beta_fit,
        station_fit=station_fit,
        epsilon_eff=float(epsilon_eff),
        z0_power=z0_power,
        power_ratio=power_ratio,
    )


# ---------------------------------------------------------------------------
# S-parameters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ModalSparams:
    """Two-port scattering numbers from modal phasors on one uniform line.

    ``S11`` is the exact two-probe split of the end phasors
    (:func:`emfit.ports.travelling_waves` then
    :func:`emfit.ports.reflection`): the reflection coefficient on the near
    station's plane, needing no model.  ``S21`` is
    :func:`emfit.ports.transmission`, which **removes** the line's own delay, so
    a matched lossless length of line reads exactly ``1`` and the number left is
    the device's.  The interior stations therefore serve ``beta`` (through the
    fit) and the consistency checks, not the two-probe splits.

    Attributes:
        f0: The DFT bin [Hz].
        s11: ``v_minus / v_plus`` on the near plane, dimensionless.
        s21: De-embedded transmission, dimensionless.
        line: The :class:`ModalLine` the phasors fitted, so ``beta``, ``z0``,
            ``gamma_v``, ``gamma_i`` and ``mode_purity`` are all reachable
            without a second call.
        reference_distance: How far upstream ``S11`` was moved [m]; zero means
            it stays on the near station's plane.
        reference_impedance: The impedance the caller said the ports should be
            quoted on [ohm], or ``None``.  This module does **not** renormalise
            (see :meth:`report`), it only checks.
        passivity: ``|S11|**2 + |S21|**2``, dimensionless.
        passivity_tolerance: How far above 1 :attr:`passive` still calls the
            pair passive, dimensionless.
    """

    f0: float
    s11: complex
    s21: complex
    line: ModalLine
    reference_distance: float
    reference_impedance: complex | None
    passivity: float
    passivity_tolerance: float = 1.0e-9

    @property
    def beta(self) -> float:
        return self.line.beta

    @property
    def z0(self) -> complex:
        return self.line.z0

    @property
    def mode_purity(self) -> float:
        return self.line.mode_purity

    @property
    def reference_plane(self) -> float:
        return self.line.reference_plane - self.reference_distance

    @property
    def passive(self) -> bool:
        """``|S11|**2 + |S21|**2 <= 1 + passivity_tolerance``.

        Read the failure carefully: on a *uniform* line a reflection is not a
        loss mechanism -- the forward wave still arrives -- so ``|S21| = 1`` and
        the sum exceeds 1 whenever ``S11`` is not small.  A ``False`` here is
        this module saying that these two numbers cannot both be a passive
        two-port's, which is true: the reflection belongs to the port, not to
        the length of line between the reference planes.
        """
        return bool(self.passivity <= 1.0 + self.passivity_tolerance)

    @property
    def impedance_mismatch(self) -> float | None:
        """``|z0 - reference_impedance| / |reference_impedance|``, or ``None``."""
        if self.reference_impedance is None:
            return None
        return float(abs(self.line.z0 - self.reference_impedance)
                     / abs(self.reference_impedance))

    def report(self) -> str:
        text = (f"S11 = {self.s11.real:+.6g}{self.s11.imag:+.6g}j, "
                f"S21 = {self.s21.real:+.6g}{self.s21.imag:+.6g}j, "
                f"|S11|^2 + |S21|^2 = {self.passivity:.9g}"
                f"{'' if self.passive else ' (not passive)'}")
        if self.impedance_mismatch is not None:
            text += (f"; the ports are on this line's own z0 = "
                     f"{abs(self.line.z0):.6g} ohm, {100.0 * self.impedance_mismatch:.4g} % "
                     f"from the {abs(self.reference_impedance):.6g} ohm asked for "
                     "-- not renormalised, because a one-sided renormalisation of "
                     "S11 alone would break the passivity sum above")
        return text


def modal_sparams(v, i, stations_m, *, f0: float,
                  reference_impedance=None, reference_distance: float = 0.0,
                  alpha: float = 0.0) -> ModalSparams:
    """``S11`` and ``S21`` from modal phasors on one uniform length of line.

    ``v``, ``i`` and ``stations_m`` are as for :func:`modal_line_quantities`;
    the outermost two stations are the two reference planes, ``d`` apart.

    ``reference_distance`` moves ``S11`` upstream by that many metres with
    :func:`emfit.ports.deembed_reflection` (default: leave it where it was
    measured).  ``reference_impedance`` is *not* applied: a power-wave
    renormalisation of ``S11`` alone would have to be matched by a
    renormalisation of ``S21`` to keep ``|S11|**2 + |S21|**2`` meaningful, and a
    half-done version of that formula fails silently, so the impedance asked
    for is compared with the fitted one and the difference is reported instead
    (see :attr:`ModalSparams.impedance_mismatch`).

    Raises:
        ValueError: From the fits and splits (:func:`modal_line_quantities`,
            :func:`emfit.ports.travelling_waves` with probes an exact multiple
            of a half wavelength apart, :func:`emfit.ports.reflection` with no
            forward wave), or here for a non-negative ``reference_distance``
            being asked for with zero stations.
    """
    x = np.asarray(stations_m, dtype=float).ravel()
    v = np.asarray(v, dtype=complex).ravel()
    i = np.asarray(i, dtype=complex).ravel()
    if not x.size == v.size == i.size:
        raise ValueError(
            f"stations_m, v and i must hold the same number of stations, got "
            f"{x.size}, {v.size} and {i.size}")
    if x.size < 4:
        raise ValueError(
            "S-parameters need four stations: the two-probe split takes the "
            f"outer pair and the impedance fit needs the rest, got {x.size}")

    order = np.argsort(x, kind="stable")
    x, v, i = x[order], v[order], i[order]

    line = modal_line_quantities(v, i, x, f0=f0, alpha=alpha)
    beta = line.beta
    d = float(x[-1] - x[0])

    v_plus, v_minus = travelling_waves(v[0], v[-1], d, beta)
    s11_measured = complex(reflection(v_plus, v_minus))
    if reference_distance:
        s11 = complex(deembed_reflection(s11_measured, beta,
                                         float(reference_distance)))
    else:
        s11 = s11_measured

    # The far end's forward wave: what arrived there, minus the backward wave
    # carried to it.  There is no third plane beyond it, so no two-probe split
    # exists there and the near pair's own split is propagated along the line
    # instead -- the same model ``travelling_waves`` inverts, so what is left of
    # the ratio is the length of line's own ``exp(-j beta d - alpha d)`` and
    # ``S21`` reads the device's even when the line is not matched.
    v_minus_far = v_minus * np.exp((1j * beta + float(alpha)) * d)
    v_plus_far = v[-1] - v_minus_far
    s21 = complex(transmission(v_plus, v_plus_far, d, beta))

    passivity = float(np.abs(s11) ** 2 + np.abs(s21) ** 2)
    return ModalSparams(
        f0=float(f0),
        s11=s11,
        s21=s21,
        line=line,
        reference_distance=float(reference_distance),
        reference_impedance=(None if reference_impedance is None
                             else complex(reference_impedance)),
        passivity=passivity,
    )


# ---------------------------------------------------------------------------
# the residual gate: does the modal route beat the circuit one?
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResidualGate:
    """One quantity, three values, and whether the modal one is close enough.

    ``circuit`` is the value the closed-form (transmission-line) model gives
    after the circuit route's correction, ``modal`` the one the modal route
    gives, and ``closed_form`` the exact analytic value both are trying to
    reach.  The gate is

        ``|modal - closed_form| <= ratio * |circuit - closed_form|``

    i.e. the modal route must leave at most ``ratio`` of the circuit route's
    residual.  It is a **ratio of absolute residuals**, not a percentage claim
    about the quantities: a residual of 0.2 rad/m in ``beta`` and a residual of
    0.2 ohm in ``z0`` are compared with their own kind only.

    Both residuals are absolute values, so a value that *overshoots* the closed
    form is charged its full overshoot.  There is deliberately no "undershoot
    only" reading: a route that goes 1.0 past the answer is not better than one
    that stops 0.9 short, and truncating at the closed form would make the first
    one free.

    Attributes:
        quantity: Which quantity this is, e.g. ``"z0"``, used in reports.
        circuit: The circuit route's value, in the quantity's own unit.
        modal: The modal route's value.
        closed_form: The analytic value both are measured against.
        ratio: The fraction of the circuit residual allowed, dimensionless.
        gap_circuit: ``|circuit - closed_form|``, in the quantity's unit.
        gap_modal: ``|modal - closed_form|``, likewise.
        passed: Whether the criterion held.
    """

    quantity: str
    circuit: float
    modal: float
    closed_form: float
    ratio: float
    gap_circuit: float
    gap_modal: float
    passed: bool

    @property
    def allowance(self) -> float:
        """``ratio * gap_circuit``: the largest modal residual that passes."""
        return self.ratio * self.gap_circuit

    @property
    def improvement(self) -> float:
        """``gap_circuit / gap_modal``: how many times closer the modal route is.

        ``inf`` when the modal route is exact, ``nan`` when neither route has a
        residual (in which case there is nothing to improve on).
        """
        if self.gap_modal == 0.0:
            return float("inf") if self.gap_circuit > 0.0 else float("nan")
        return self.gap_circuit / self.gap_modal

    def report(self) -> str:
        name = self.quantity or "quantity"
        return (f"{name}: circuit {self.circuit:.10g}, modal {self.modal:.10g}, "
                f"closed form {self.closed_form:.10g} -> residual "
                f"{self.gap_modal:.4g} vs {self.gap_circuit:.4g} allowed "
                f"{self.allowance:.4g} ({'pass' if self.passed else 'FAIL'})")


def residual_gate(value_circuit, value_modal, value_closed_form, *,
                  quantity: str = "", ratio: float = 0.50) -> ResidualGate:
    """Build one :class:`ResidualGate` from the three values of one quantity.

    ``ratio`` defaults to a half: the modal route has to halve the circuit
    route's residual, which is the smallest improvement worth claiming from a
    change of method rather than of arithmetic.

    A circuit residual of exactly zero is handled rather than divided by: the
    gate then passes only if the modal route is exact too, and
    :attr:`ResidualGate.improvement` is ``nan`` because the comparison carries
    no information.

    Raises:
        ValueError: If any value is not finite, or if ``ratio`` is negative.
    """
    circuit = float(value_circuit)
    modal = float(value_modal)
    closed_form = float(value_closed_form)
    ratio = float(ratio)
    if not np.all(np.isfinite([circuit, modal, closed_form])):
        raise ValueError(
            f"{quantity or 'the quantity'}: circuit {circuit!r}, modal {modal!r} "
            f"and closed form {closed_form!r} must all be finite -- a nan cannot "
            "pass a gate")
    if ratio < 0.0:
        raise ValueError(f"ratio must be non-negative, got {ratio!r}")

    gap_circuit = abs(circuit - closed_form)
    gap_modal = abs(modal - closed_form)
    passed = gap_modal == 0.0 if gap_circuit == 0.0 else gap_modal <= ratio * gap_circuit
    return ResidualGate(
        quantity=quantity,
        circuit=circuit,
        modal=modal,
        closed_form=closed_form,
        ratio=ratio,
        gap_circuit=gap_circuit,
        gap_modal=gap_modal,
        passed=bool(passed),
    )


@dataclass(frozen=True)
class ResidualReport:
    """The three gates of a route comparison, and which of them failed.

    Attributes:
        beta: The phase-constant gate [rad/m].
        eps_eff: The effective-permittivity gate, dimensionless.
        z0: The impedance gate [ohm].
    """

    beta: ResidualGate
    eps_eff: ResidualGate
    z0: ResidualGate

    @property
    def gates(self) -> tuple:
        """The three gates, in the order ``(beta, eps_eff, z0)``."""
        return (self.beta, self.eps_eff, self.z0)

    @property
    def all_pass(self) -> bool:
        """True only when all three gates passed."""
        return all(gate.passed for gate in self.gates)

    @property
    def failed(self) -> tuple:
        """The **names** of the quantities that failed; empty when all passed.

        Named rather than summarised, because ``all_pass is False`` on its own
        says nothing about which number to go and look at.
        """
        return tuple(gate.quantity for gate in self.gates if not gate.passed)

    def report(self) -> str:
        if self.all_pass:
            return "all three quantities pass (beta, eps_eff, z0): " + "; ".join(
                gate.report() for gate in self.gates)
        return ("; ".join(gate.report() for gate in self.gates)
                + " -- failed: " + ", ".join(self.failed))


def residual_gates(beta, eps_eff, z0, *, ratio: float = 0.50) -> ResidualReport:
    """Gate ``beta``, ``eps_eff`` and ``z0`` at once, each as a value triple.

    Every argument is ``(circuit, modal, closed_form)`` for that quantity, and
    the same ``ratio`` is applied to all three.  The result names the
    quantities that failed (:attr:`ResidualReport.failed`) instead of answering
    with a bare ``False``: a route can halve two residuals and lose the third,
    and that is the case worth reporting precisely.

    Raises:
        ValueError: If a triple does not hold exactly three numbers, or
            whatever :func:`residual_gate` raises.
    """
    triples = {"beta": beta, "eps_eff": eps_eff, "z0": z0}
    gates = {}
    for name, triple in triples.items():
        values = tuple(np.asarray(triple, dtype=float).ravel())
        if len(values) != 3:
            raise ValueError(
                f"{name} must be a (circuit, modal, closed form) triple, got "
                f"{len(values)} values: {values!r}")
        gates[name] = residual_gate(*values, quantity=name, ratio=ratio)
    return ResidualReport(beta=gates["beta"], eps_eff=gates["eps_eff"],
                          z0=gates["z0"])
