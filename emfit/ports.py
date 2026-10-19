"""Wave-port primitives: probe voltages, DFT accumulation, travelling waves, S.

Why two probes and not a lumped load
------------------------------------
The obvious way to terminate a gap port is a series resistor: measure the
voltage across the gap, divide by ``R``, and call that the port current.  That
needs a *resistive* termination on a mesh edge, and
:class:`emfit.evolve.FITStepper` only knows how to pin PEC constraints -- there
is no resistive edge in the discrete model to divide by.  Faking one would put
a number in the code that no part of the solver enforces, and every S-parameter
built on it would be wrong in a way no test could catch.

So this module does not terminate anything.  Instead it **splits the standing
wave on the line into travelling waves**, using two voltage probes a known
distance ``d`` apart on a uniform section.  On a line that carries only the
dominant mode,

    v1 = v_plus + v_minus
    v2 = v_plus exp(-j beta d) + v_minus exp(+j beta d)

which is two equations for the two unknowns ``v_plus``, ``v_minus`` at the
reference plane of probe 1 -- see :func:`travelling_waves`.  Everything else
follows algebraically:

* ``S11 = v_minus / v_plus`` at the reference plane (:func:`reflection`), with
  no termination and no calibration run;
* ``S21`` from the *forward* amplitudes at the two ports, de-embedded by the
  known phase over their separation (:func:`transmission`);
* and none of it needs the port impedance.  A probe voltage is a line integral
  along a path (:class:`Probe`), a purely geometric quantity, so ``z0`` enters
  only where a caller wants an absolute power wave, never in a ratio.

The price is that the split is degenerate when the probes are a multiple of a
half wavelength apart -- both rows of the 2x2 are then the same equation -- so
:func:`travelling_waves` refuses that case instead of returning noise.  A
broadband run therefore wants ``d`` shorter than half a guide wavelength at the
highest frequency of interest; :func:`suggest_probe_spacing` picks one.

Nothing here touches the stepper.  These are the analytic primitives of a port:
the pieces a validation run is assembled from, testable on their own.

Sign convention
---------------
Each edge unknown is the line integral of ``E`` along that edge, in the
direction the edge is oriented.  A probe path's voltage is the integral **from
the tail of the first edge to the head of the last**, walking the listed edges
in order, with ``signs[i] = +1`` where the path runs with edge ``i`` and ``-1``
where it runs against it.  Reversing the path flips the sign; there is no
separate "positive terminal".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "Probe",
    "LumpedPort",
    "DftAccumulator",
    "column_path",
    "row_path",
    "edge_path_voltage",
    "probe_voltage",
    "travelling_waves",
    "reflection",
    "transmission",
    "suggest_probe_spacing",
    "write_touchstone",
    "read_touchstone",
]


# ---------------------------------------------------------------------------
# probe voltages
# ---------------------------------------------------------------------------
def edge_path_voltage(e, edges, signs=None) -> float:
    """Line integral of the electric field along a chain of edges, in volts.

    Every edge unknown *is* the line integral of ``E`` along that edge, in the
    direction of the edge's own orientation, so a path crossing a set of edges
    integrates to ``sum_i signs[i] * e[edges[i]]``.  The integral runs from the
    tail of the first edge to the head of the last, in the order given.

    Parameters
    ----------
    e : array_like
        Flat edge vector, at least as long as ``max(edges) + 1``.
    edges : array_like of int
        Edge indices, in path order.
    signs : array_like of float, optional
        ``+1``/``-1`` per edge; default all ``+1``.

    Returns
    -------
    float
    """
    e = np.asarray(e)
    idx = np.asarray(edges, dtype=int).ravel()
    if signs is None:
        s = np.ones(idx.size, dtype=float)
    else:
        s = np.asarray(signs, dtype=float).ravel()
        if s.size != idx.size:
            raise ValueError(
                f"signs has {s.size} entries for {idx.size} edges")
    if idx.size == 0:
        return 0.0
    return float(np.sum(s * e[idx]))


def probe_voltage(e, probe) -> float:
    """Voltage measured by ``probe``: :func:`edge_path_voltage` on its path."""
    return edge_path_voltage(e, probe.edges, probe.signs)


def _as_edges(name: str, edges) -> np.ndarray:
    """Validate edge indices: 1-D integers, stored as ``int``."""
    idx = np.asarray(edges).ravel()
    if idx.size == 0:
        raise ValueError(f"{name}: the edge list is empty")
    if not np.issubdtype(idx.dtype, np.integer):
        as_float = idx.astype(float)
        if not np.all(as_float == np.round(as_float)):
            raise ValueError(
                f"{name}: edge indices must be integers, got {edges!r}")
        idx = np.round(as_float)
    return idx.astype(int)


@dataclass(frozen=True, eq=False)
class Probe:
    """A voltage probe: a path through the edge lattice.

    Parameters
    ----------
    name : str
        Label used in reports.
    edges : array_like of int
        Edge indices along the path, in path order.
    signs : array_like of float
        ``+1`` or ``-1`` per edge: the path direction relative to each edge's
        own orientation (see the module's sign convention).

    Notes
    -----
    Frozen, and compared by identity rather than by value: the fields are
    arrays, for which ``==`` is elementwise.
    """

    name: str
    edges: np.ndarray
    signs: np.ndarray

    def __post_init__(self):
        object.__setattr__(self, "edges", _as_edges(f"probe {self.name!r}",
                                                   self.edges))
        signs = np.asarray(self.signs, dtype=float).ravel()
        if signs.size != self.edges.size:
            raise ValueError(
                f"probe {self.name!r}: {self.edges.size} edges but "
                f"{signs.size} signs")
        if not np.all((signs == 1.0) | (signs == -1.0)):
            raise ValueError(
                f"probe {self.name!r}: signs must be +1 or -1, got "
                f"{self.signs!r}")
        object.__setattr__(self, "signs", signs)

    def voltage(self, e) -> float:
        """Voltage across the probe path [V]; alias of :func:`probe_voltage`."""
        return edge_path_voltage(e, self.edges, self.signs)

    def __call__(self, e) -> float:
        return self.voltage(e)


@dataclass(frozen=True, eq=False)
class LumpedPort:
    """The feed gap of a port, as a voltage measured across it.

    A naming device over :class:`Probe`: ``edges`` span the gap between the two
    conductors and the voltage across them is the port voltage, so this module
    can talk about ports without pretending to terminate them.  ``z0`` is
    carried for the caller (turning a travelling wave into power, say);
    nothing here divides by it, because the two-probe decomposition does not
    need an impedance.

    Parameters
    ----------
    name : str
    edges : array_like of int
        The edge or edges spanning the gap.
    z0 : float
        Nominal port impedance [ohm].
    """

    name: str
    edges: np.ndarray
    z0: float = 50.0

    def __post_init__(self):
        object.__setattr__(self, "edges", _as_edges(f"port {self.name!r}",
                                                    self.edges))
        if not float(self.z0) > 0.0:
            raise ValueError(f"port {self.name!r}: z0 must be positive")

    def voltage(self, e) -> float:
        """Voltage across the gap [V]."""
        return edge_path_voltage(e, self.edges)

    @property
    def probe(self) -> Probe:
        """The equivalent :class:`Probe`, all signs ``+1``."""
        return Probe(self.name, self.edges, np.ones(self.edges.size))


# ---------------------------------------------------------------------------
# probe paths on a cell complex
# ---------------------------------------------------------------------------
def _node_index(axis: str, i, limit: int) -> int:
    """Validate a point-layer index on ``axis``: whole, and ``0 <= i < limit``.

    No periodic wrap is applied: an index equal to the layer count is an error,
    because a probe path that silently wrapped onto the other side of the mesh
    would measure a different gap and no test would notice.
    """
    j = int(i)
    if j != i:
        raise ValueError(f"{axis} must be a whole point-layer index, got {i!r}")
    if not 0 <= j < limit:
        raise IndexError(
            f"{axis}={j} is outside the {limit} point layers on that axis "
            f"(valid 0..{limit - 1}); no periodic wrap is applied")
    return j


def _stack_range(axis: str, k0, k1, limit: int) -> tuple[int, int]:
    """Validate a half-open run of cells on ``axis``, defaulting the upper end."""
    lo = int(k0)
    hi = limit if k1 is None else int(k1)
    if lo != k0 or (k1 is not None and hi != k1):
        raise ValueError(
            f"{axis} bounds must be whole cell indices, got {k0!r} and {k1!r}")
    if not 0 <= lo < hi <= limit:
        raise ValueError(
            f"the run [{lo}, {hi}) is empty or leaves the {limit} cells on "
            f"that axis (need 0 <= lo < hi <= {limit})")
    return lo, hi


def column_path(cc, ix, iy, k0=0, k1=None) -> np.ndarray:
    """Edge indices of one straight column of ``ez`` edges through the stack.

    A parallel-plate gap, and any other quasi-one-dimensional gap, is crossed
    by a line of ``ez`` edges that share one ``(x, y)`` point and step through
    the z cells.  This helper returns exactly that line, in path order, so that
    :func:`edge_path_voltage` can integrate ``E_z`` across the gap without the
    caller hand-rolling flat index arithmetic from ``cc.off_ez``.

    Ordering and signs
    ------------------
    The edge indices come back with the z cell index increasing,
    ``k0, k0 + 1, ..., k1 - 1``, which is the path that walks in the ``+z``
    direction.  Each edge is traversed with its own orientation, so a matching
    :class:`Probe` wants ``signs`` all ``+1`` -- the default of
    :func:`edge_path_voltage`.  Reversing the list reverses the voltage.

    The path runs from the z point layer ``k0`` to the point layer ``k1``, so
    with the defaults its two ends are ``z = zmin`` and ``z = zmax`` and the
    summed edge voltages are the whole plate separation, in volts.

    Parameters
    ----------
    cc : CellComplex
        The cell complex the flat edge vector belongs to; only its index
        helpers and counts are used.
    ix, iy : int
        Point-layer indices of the column: ``0 <= ix < cc.nxn`` and
        ``0 <= iy < cc.nyn``.  No periodic wrap is applied, so an index equal
        to the count raises instead of folding onto the far side.
    k0, k1 : int, optional
        Half-open run of z *cells*, ``0 <= k0 < k1 <= cc.nz``; ``k1`` defaults
        to ``cc.nz``, the full stack.

    Returns
    -------
    ndarray of int
        ``k1 - k0`` edge indices into the flat ``e`` vector, in path order.

    Raises
    ------
    ValueError
        If a bound is not a whole number, or the run ``[k0, k1)`` is empty or
        leaves the ``cc.nz`` cells.
    IndexError
        If ``ix`` or ``iy`` is outside the point layers of its axis.

    Examples
    --------
    The gap probe of a two-cell-thick parallel plate, with z the gap axis::

        gap = Probe("gap", column_path(cc, ix, iy), np.ones(cc.nz))

    which is the path :class:`LumpedPort` only names.
    """
    ix = _node_index("ix", ix, cc.nxn)
    iy = _node_index("iy", iy, cc.nyn)
    lo, hi = _stack_range("k", k0, k1, cc.nz)
    return np.asarray(cc.idx_ez(ix, iy, np.arange(lo, hi)), dtype=int)


def row_path(cc, iy, iz, i0=0, i1=None) -> np.ndarray:
    """Edge indices of one straight run of ``ex`` edges along the x axis.

    The transverse counterpart of :func:`column_path`: a line of ``ex`` edges
    that share one ``(y, z)`` point and step through the x cells, in path
    order.  This is the path that integrates ``E_x`` along a line -- the
    tangential field down a parallel-plate line, say -- which is the quantity
    an along-line phase or a group delay is read from.

    Ordering and signs
    ------------------
    The edge indices come back with the x cell index increasing,
    ``i0, i0 + 1, ..., i1 - 1``, which is the path that walks in the ``+x``
    direction, each edge with its own orientation, so ``signs`` all ``+1``.
    The summed edge voltages are in volts and run from the point layer ``i0`` to
    the point layer ``i1``.

    Parameters
    ----------
    cc : CellComplex
    iy, iz : int
        Point-layer indices of the row: ``0 <= iy < cc.nyn`` and
        ``0 <= iz < cc.nzn``; no periodic wrap is applied.  Both transverse
        coordinates of an ``ex`` edge are point layers, so on a bounded z axis
        ``iz`` runs up to ``cc.nzn``, which is one more than the ``cc.nz``
        cells.
    i0, i1 : int, optional
        Half-open run of x *cells*, ``0 <= i0 < i1 <= cc.nx``; ``i1`` defaults
        to ``cc.nx``, the full line.

    Returns
    -------
    ndarray of int
        ``i1 - i0`` edge indices into the flat ``e`` vector, in path order.

    Raises
    ------
    ValueError
        If a bound is not a whole number, or the run ``[i0, i1)`` is empty or
        leaves the ``cc.nx`` cells.
    IndexError
        If ``iy`` or ``iz`` is outside the point layers of its axis.
    """
    iy = _node_index("iy", iy, cc.nyn)
    iz = _node_index("iz", iz, cc.nzn)
    lo, hi = _stack_range("i", i0, i1, cc.nx)
    return np.asarray(cc.idx_ex(np.arange(lo, hi), iy, iz), dtype=int)


# ---------------------------------------------------------------------------
# time to frequency
# ---------------------------------------------------------------------------
class DftAccumulator:
    """Running single-frequency DFT of a handful of scalar signals.

    Feed it the probe voltages after every step and it accumulates

        ``S[f] += w(n) * values[n] * exp(-2j pi f n dt)``

    with the phase taken from the **time-step index** ``n``, not from an
    accumulated float clock: the index is exact, whereas a running ``t`` loses
    low bits over a long run and shows up as a slow phase drift.

    Bin spacing.  A record of ``n_steps`` samples at ``dt`` spans
    ``T = n_steps * dt`` and resolves frequencies ``1/T`` apart, so a tone that
    is not on a bin **leaks into its neighbours**.  For a rectangular window a
    tone half a bin off is not marginally off: the recovered amplitude is
    ``2/pi`` of the true one.  That is a property of the finite record, not of
    this code, so pick ``freqs`` on bins (``k / (n_steps * dt)``) and run the
    full record length.

    Windowing.  ``window="hann"`` weights sample ``n`` by
    ``0.5 - 0.5 cos(2 pi n / (n_steps - 1))``, which needs the record length,
    hence ``n_steps``; anything else can be passed as an explicit weight array.
    The standard single-sided correction factor is **not** applied: every
    consumer here builds ratios of phasors accumulated the same way, so a
    constant factor cancels, and a caller who wants volts from a tapered record
    normalises it themselves.

    Parameters
    ----------
    freqs : array_like
        Frequencies to accumulate, in Hz.
    dt : float
        Time step, in seconds.
    window : str or array_like
        ``"rect"``, ``"hann"``, or a per-sample weight array.
    n_steps : int, optional
        Record length; required by ``window="hann"``.

    Attributes
    ----------
    freqs : ndarray (n_freqs,)
    n_samples : int
        Samples accumulated since the last :meth:`reset`.
    """

    def __init__(self, freqs, dt, *, window="rect", n_steps=None):
        self.freqs = np.atleast_1d(np.asarray(freqs, dtype=float)).ravel()
        if self.freqs.size == 0:
            raise ValueError("freqs must contain at least one frequency")
        if not np.all(np.isfinite(self.freqs)) or np.any(self.freqs < 0.0):
            raise ValueError(
                f"freqs must be finite and non-negative, got {self.freqs!r}")
        self.dt = float(dt)
        if not self.dt > 0.0:
            raise ValueError(f"dt must be positive, got {dt!r}")
        if isinstance(window, str):
            if window not in ("rect", "hann"):
                raise ValueError(
                    f"window must be 'rect', 'hann' or a weight array, "
                    f"got {window!r}")
            if window == "hann" and n_steps is None:
                raise ValueError(
                    "window='hann' needs n_steps: the taper width is the record "
                    "length, and a Hann window without it is not defined")
        self.window = window
        self.n_steps = None if n_steps is None else int(n_steps)
        if self.n_steps is not None and self.n_steps < 1:
            raise ValueError(f"n_steps must be at least 1, got {n_steps!r}")
        self._acc: np.ndarray | None = None
        self.n_samples = 0

    # ------------------------------------------------------------------
    def _weight(self, n: int) -> float:
        w = self.window
        if isinstance(w, str):
            if w == "rect":
                return 1.0
            span = max(self.n_steps - 1, 1)
            return float(0.5 - 0.5 * np.cos(2.0 * np.pi * n / span))
        arr = np.asarray(w, dtype=float).ravel()
        if n >= arr.size:
            raise ValueError(
                f"the window has {arr.size} weights, sample {n} is past its end")
        return float(arr[n])

    def add(self, values, n) -> None:
        """Accumulate ``values`` (shape ``(n_signals,)``) taken at step ``n``."""
        v = np.asarray(values, dtype=float).ravel()
        if v.size == 0:
            raise ValueError("values must contain at least one signal")
        if self._acc is None:
            self._acc = np.zeros((self.freqs.size, v.size), dtype=np.complex128)
        elif v.size != self._acc.shape[1]:
            raise ValueError(
                f"values has {v.size} entries, but this accumulator holds "
                f"{self._acc.shape[1]} signals")
        n = int(n)
        phase = np.exp(-2.0j * np.pi * self.freqs * n * self.dt)
        self._acc += (self._weight(n) * phase)[:, None] * v[None, :]
        self.n_samples += 1

    @property
    def spectrum(self) -> np.ndarray:
        """``(n_freqs, n_signals)`` complex accumulator."""
        if self._acc is None:
            return np.zeros((self.freqs.size, 0), dtype=np.complex128)
        return self._acc

    def reset(self) -> None:
        """Forget every sample, keeping the frequency list."""
        self._acc = None
        self.n_samples = 0


# ---------------------------------------------------------------------------
# travelling waves
# ---------------------------------------------------------------------------
def travelling_waves(v1, v2, d, beta):
    """Split two probe voltages into forward and backward waves at probe 1.

    Convention: probe 2 sits a distance ``d`` (metres) **further along the
    direction of propagation** than probe 1, the line between them is uniform,
    and only the dominant mode is present, so

        ``v1 = v_plus + v_minus``
        ``v2 = v_plus exp(-j beta d) + v_minus exp(+j beta d)``

    With ``a = exp(-j beta d)`` and ``b = exp(+j beta d)``::

        v_plus  = (v1 * b - v2) / (b - a)
        v_minus = (v2 - v1 * a) / (b - a)

    and ``b - a == 2j sin(beta d)``.

    Raises
    ------
    ValueError
        When ``sin(beta d)`` vanishes to within a relative ``1e-12``: probes an
        exact multiple of a half wavelength apart see the same equation twice
        and no split exists.
    """
    v1 = np.asarray(v1, dtype=complex)
    v2 = np.asarray(v2, dtype=complex)
    d = np.asarray(d, dtype=float)
    beta = np.asarray(beta, dtype=float)
    v1, v2, d, beta = np.broadcast_arrays(v1, v2, d, beta)
    x = beta * d
    sin = np.sin(x)
    tol = 1.0e-12 * np.maximum(1.0, np.abs(x))
    bad = np.abs(sin) <= tol
    if np.any(bad):
        worst = float(np.ravel(x[bad])[0])
        raise ValueError(
            f"probes are {worst / np.pi:g} half wavelengths apart "
            f"(beta*d = {worst:g}): sin(beta*d) vanishes there, so the forward "
            f"and backward waves cannot be separated -- move the probes, or "
            f"pick a frequency where beta*d is not a multiple of pi")
    a = np.exp(-1j * x)
    b = np.exp(+1j * x)
    denom = b - a
    return (v1 * b - v2) / denom, (v2 - v1 * a) / denom


def reflection(v_plus, v_minus) -> np.ndarray:
    """``S11 = v_minus / v_plus`` at a reference plane.

    Raises
    ------
    ValueError
        If any ``v_plus`` is zero: a wave that is not there has no reflection
        coefficient, and an ``inf``/``NaN`` would travel silently.
    """
    v_plus = np.asarray(v_plus, dtype=complex)
    v_minus = np.asarray(v_minus, dtype=complex)
    v_plus, v_minus = np.broadcast_arrays(v_plus, v_minus)
    if np.any(np.abs(v_plus) == 0.0):
        raise ValueError(
            "cannot form a reflection coefficient: the forward wave is zero")
    return v_minus / v_plus


def transmission(v_from, v_to, d, beta) -> np.ndarray:
    """``S21`` from forward amplitudes at two ports a distance ``d`` apart.

    ``v_from`` is the forward wave on the near port's reference plane and
    ``v_to`` the forward wave on the far port's, ``d`` metres further along.
    Under the :func:`travelling_waves` convention plain propagation over that
    separation contributes ``exp(-j beta d)`` to the ratio, so removing it
    leaves the device::

        S21 = (v_to / v_from) * exp(+j beta d)

    Checks a reader can do: a lossless matched line has ``v_to = v_from *
    exp(-j beta d)`` and returns exactly 1; a line with ``S21 = 0.5`` gives
    ``0.5 exp(-j beta d)`` before de-embedding and ``0.5`` after.
    """
    v_from = np.asarray(v_from, dtype=complex)
    v_to = np.asarray(v_to, dtype=complex)
    d = np.asarray(d, dtype=float)
    beta = np.asarray(beta, dtype=float)
    v_from, v_to, d, beta = np.broadcast_arrays(v_from, v_to, d, beta)
    if np.any(np.abs(v_from) == 0.0):
        raise ValueError(
            "cannot form a transmission coefficient: the incident wave is zero")
    return (v_to / v_from) * np.exp(1j * beta * d)


def suggest_probe_spacing(beta_max, fraction=0.25) -> float:
    """A probe spacing that keeps the split well conditioned up to ``beta_max``.

    ``sin(beta d)`` degrades near multiples of ``pi``; keep ``beta_max * d`` at
    ``fraction * pi`` or below.  The default puts ``d`` at an eighth of a guide
    wavelength.

    Parameters
    ----------
    beta_max : float
        Largest phase constant of interest [rad/m].
    fraction : float
        Fraction of ``pi`` allowed at ``beta_max``.
    """
    if not float(beta_max) > 0.0:
        raise ValueError(f"beta_max must be positive, got {beta_max!r}")
    return float(fraction * np.pi / beta_max)


# ---------------------------------------------------------------------------
# Touchstone
# ---------------------------------------------------------------------------
def write_touchstone(handle, freqs, s, *, z0=50.0, fmt="ri") -> None:
    """Write a Touchstone v1 file for an ``n_ports``-port network.

    An option line (``# HZ S RI R 50``, or ``MA`` for ``fmt="ma"``), then one
    row per frequency: the frequency in Hz followed by the S-parameters with
    the **input port slowest and the output port fastest** --
    ``S11 S21 S12 S22`` for two ports, which is the order Touchstone v1
    mandates.  That is ``s[..., out, in]`` flattened in Fortran order over the
    last two axes.

    Parameters
    ----------
    handle : path or file object
        Opened for writing when a path is given.
    freqs : array_like (n_freqs,)
        Frequencies in Hz.
    s : array_like (n_freqs, n_ports, n_ports)
        Complex S-parameters, ``s[f, out, in]``.
    z0 : float
        Reference impedance for the option line [ohm].
    fmt : str
        ``"ri"`` (real/imaginary) or ``"ma"`` (magnitude/angle in degrees).
    """
    freqs = np.atleast_1d(np.asarray(freqs, dtype=float)).ravel()
    s = np.asarray(s, dtype=complex)
    if s.ndim != 3 or s.shape[1] != s.shape[2]:
        raise ValueError(
            f"s must have shape (n_freqs, n_ports, n_ports), got {s.shape}")
    if s.shape[0] != freqs.size:
        raise ValueError(
            f"{freqs.size} frequencies but {s.shape[0]} rows of S")
    n_ports = s.shape[1]
    mode = fmt.lower()
    if mode not in ("ri", "ma"):
        raise ValueError(f"fmt must be 'ri' or 'ma', got {fmt!r}")

    opened = False
    if not hasattr(handle, "write"):
        handle = open(handle, "w", encoding="utf-8")
        opened = True
    try:
        handle.write(f"# HZ S {mode.upper()} R {float(z0):g}\n")
        flat = s.reshape(freqs.size, n_ports * n_ports, order="F")
        for f, row in zip(freqs, flat):
            parts = [f"{float(f):.12g}"]
            for value in row:
                if mode == "ri":
                    parts.append(f"{value.real:.12g}")
                    parts.append(f"{value.imag:.12g}")
                else:
                    parts.append(f"{abs(value):.12g}")
                    parts.append(f"{np.degrees(np.angle(value)):.12g}")
            handle.write(" ".join(parts) + "\n")
    finally:
        if opened:
            handle.close()


def read_touchstone(handle) -> tuple[np.ndarray, np.ndarray]:
    """Read a Touchstone v1 file written by :func:`write_touchstone`.

    Returns
    -------
    (freqs, s)
        ``(n_freqs,)`` in Hz and ``(n_freqs, n_ports, n_ports)`` complex with
        ``s[f, out, in]`` -- the inverse of the Fortran-order flattening
        :func:`write_touchstone` uses.
    """
    opened = False
    if not hasattr(handle, "read"):
        handle = open(handle, "r", encoding="utf-8")
        opened = True
    try:
        text = handle.read()
    finally:
        if opened:
            handle.close()

    scale = 1.0
    mode = "RI"
    rows: list[list[float]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        if stripped.startswith("#"):
            for token in stripped[1:].upper().split():
                if token in ("HZ", "KHZ", "MHZ", "GHZ"):
                    scale = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}[token]
                elif token in ("RI", "MA", "DB"):
                    mode = token
            continue
        rows.append([float(tok) for tok in stripped.split()])
    if not rows:
        raise ValueError("no data rows in the Touchstone file")

    n_vals = len(rows[0])
    n_ports = int(round(np.sqrt((n_vals - 1) / 2.0)))
    if 2 * n_ports * n_ports + 1 != n_vals:
        raise ValueError(
            f"a Touchstone row has {n_vals} columns, which is one frequency "
            f"plus 2 * n_ports**2 values for no integer n_ports")
    freqs = np.empty(len(rows), dtype=float)
    s = np.empty((len(rows), n_ports, n_ports), dtype=complex)
    for n, row in enumerate(rows):
        if len(row) != n_vals:
            raise ValueError(f"row {n} has {len(row)} columns, expected {n_vals}")
        freqs[n] = row[0] * scale
        pairs = np.asarray(row[1:]).reshape(n_ports * n_ports, 2)
        if mode == "RI":
            values = pairs[:, 0] + 1j * pairs[:, 1]
        elif mode == "MA":
            values = pairs[:, 0] * np.exp(1j * np.radians(pairs[:, 1]))
        else:  # DB
            values = 10.0 ** (pairs[:, 0] / 20.0) * np.exp(
                1j * np.radians(pairs[:, 1]))
        s[n] = values.reshape(n_ports, n_ports, order="F")
    return freqs, s
