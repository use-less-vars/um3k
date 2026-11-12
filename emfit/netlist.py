"""A JSON netlist format, its parser, and the transient driver that runs it.

:mod:`emfit.spice` deliberately parses nothing and owns no clock: it steps a
:class:`~emfit.spice.CircuitNetwork` given a step size and a source-level
vector, and leaves the loop to the caller.  This module is that caller.  It is
three layers, and they are separable on purpose:

``parse_netlist(...) -> Netlist``
    Reads a JSON document and builds a
    :class:`~emfit.spice.CircuitNetwork`.  A caller who only wants the parse
    reads ``Netlist.network`` and stops there; nothing about parsing depends on
    the driver.
``Netlist.transient(...) -> TransientResult``
    Owns the time loop: advances ``t``, evaluates each declared waveform at
    ``t``, and steps :class:`~emfit.spice.MNASolver`.  Recorded node voltages
    and branch currents come back as arrays indexed by the names the netlist
    used, so a test asserts on ``result.v["out"]`` and ``result.i["c1"]``
    instead of on row numbers.
``Waveform``
    The ``t -> level`` map the driver evaluates.  Frozen and callable; there is
    no state machine and no event queue.

The format
----------
::

    {"name": "rc_lowpass",
     "elements": [
       {"kind": "V", "name": "vin", "nodes": ["in", "0"], "value": 0.0,
        "waveform": {"type": "step", "amplitude": 1.0}},
       {"kind": "R", "name": "r1", "nodes": ["in", "out"], "value": 1000.0},
       {"kind": "C", "name": "c1", "nodes": ["out", "0"], "value": 1e-7}
     ]}

Top-level fields: ``elements`` (required), ``name`` (optional, a label for
error messages) and ``nodes`` (optional, see below).  Element fields: ``kind``
(``R``, ``L``, ``C``, ``V`` or ``I``), ``name`` (unique), ``nodes`` (exactly
two references), ``value`` (SI: ohm, henry, farad, volt, ampere) and, on
sources only, ``waveform``.  Any other field on an element, or any other
top-level field, is an **error**, not something quietly ignored.

Node references
---------------
``0``, ``"0"``, ``"gnd"`` and ``"ground"`` all mean ground (case-insensitive
for the three string spellings).  The token ``"0"`` is therefore never a name.
Any other integer, or any all-digit string (``"3"``), is read as a node
*index*; anything else is a node *name*.  Mixing the two is allowed.

Numbering is deterministic from the document alone.  Ground is ``0``.  Indices
fixed by an explicit numeric token keep their number, and the names are then
assigned the lowest indices free *above the highest explicit one* (``next_free
= max(indices) + 1``, then upwards) in a fixed order -- gaps left by explicit
tokens are not filled, so ``nodes: ["a"]`` next to the token ``3`` puts ``a``
at ``4`` -- namely: the ``nodes`` declaration
first (in declaration order), then any remaining names in first-appearance
order through ``elements``, node ``a`` before node ``b``.  ``n_nodes`` counts
ground, as
:class:`~emfit.spice.CircuitNetwork` requires -- the RC netlist above is
``in -> 1``, ``out -> 2``, ``n_nodes = 3``.  :class:`Netlist` exposes both maps
(``node_index`` name -> index, ``node_names`` index -> name) and the same pair
for elements (``element_index`` name -> branch index), so nothing has to be
re-derived.

If a ``nodes`` list is given it is the **authoritative** name space: a
reference to a name it does not declare is an "unknown node name" error.  A
declared node that nothing references stays a floating node, and
``np.linalg.solve`` will report the resulting singularity -- that is a
property of the netlist, so it is left to fail loudly rather than be repaired.

Sources and waveforms
---------------------
A ``V`` branch holds ``u_a - u_b``; an ``I`` branch drives current from ``a``
to ``b`` *through itself* (so it injects into ``b``) -- the conventions
:mod:`emfit.spice` pins.  A source's level at time ``t`` is::

    value + waveform(t)          (waveform(t) is 0.0 when no waveform is given)

with ``value`` defaulting to ``0.0``.  So a **bare ``value`` on a source is a
DC source** and is legal on its own; a source with neither ``value`` nor
``waveform`` is an error; a source with both means "this waveform riding on
this DC level", which is why the example above carries ``"value": 0.0``
alongside its step.  ``R``, ``L`` and ``C`` carry ``value`` only: a waveform on
a non-source is an error.

Implemented waveforms::

    {"type": "step", "amplitude": A, "delay": d}      A * (t >= d)
    {"type": "sine", "amplitude": A, "frequency": f,
                     "phase": p, "delay": d}          A * sin(2*pi*f*(t-d) + p)

``delay`` defaults to ``0.0`` and must be non-negative; ``phase`` is in
radians and defaults to ``0.0``; ``frequency`` must be positive; ``amplitude``
may be negative (a phase inversion) but must be finite.  A step is
**right-continuous**: at ``t == delay`` it is already at amplitude, so a step
with ``delay = 0`` is applied at ``t = 0``.  ``pulse`` is *reserved and not
implemented* -- it is rejected with a message saying so rather than being
silently aliased to ``step`` and left to be discovered later.  Nothing
integrates across a discontinuity: the driver samples a waveform at each step
time, so a source edge that falls inside a step is seen at the far end of it.

The time convention of the driver
---------------------------------
Backward Euler solves the step from ``t^n`` to ``t^{n+1}`` using the sources at
``t^{n+1}``, so that is where the driver evaluates them.  The returned record
has one row per step **plus** ``t = 0``, which is the initial state itself
(all zeros unless a state is passed in); its source values are the waveform at
``t = 0`` while its node voltages are the initial ones, so ``v["out"][0]`` is
the state *before* the first step.  ``TransientResult.t`` is therefore
``[0, dt, 2*dt, ...]`` with ``len(t) == n_steps + 1``.

Nothing here is a claim about physics
-------------------------------------
This is a parser and a loop.  It adds no new discretisation: the companions are
:class:`~emfit.spice.MNASolver`'s (backward Euler by default, first order in
``dt``), and the accuracy measured here is the accuracy of that scheme against
a closed form, argued in ``tests/test_netlist.py``.  Ledger item **E5 remains
UNVERIFIED**: no field is coupled here at all.

Absent on purpose: SPICE syntax, subcircuits, ``.model``, nonlinear devices,
``.ic``/operating-point solving, ``pulse``, dependent sources, and any notion
of a probe list (name a node or an element and read its column).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .spice import Branch, CircuitNetwork, Diode, MNASolver, TransmissionLine

__all__ = [
    "Element",
    "Netlist",
    "NetlistError",
    "TransientResult",
    "Waveform",
    "parse_netlist",
    "quarter_wave_tau",
]

_KINDS = ("R", "L", "C", "V", "I", "D", "T")
_SOURCE_KINDS = ("V", "I")
_GROUND_NAMES = frozenset({"0", "gnd", "ground"})

_TOP_FIELDS = ("elements", "name", "nodes")
_ELEMENT_FIELDS = {
    "R": frozenset({"kind", "name", "nodes", "value"}),
    "L": frozenset({"kind", "name", "nodes", "value"}),
    "C": frozenset({"kind", "name", "nodes", "value"}),
    "V": frozenset({"kind", "name", "nodes", "value", "waveform"}),
    "I": frozenset({"kind", "name", "nodes", "value", "waveform"}),
    # a diode has a model, not a value: 'value' is deliberately absent, so a
    # netlist that tries to set one is rejected rather than silently ignored
    "D": frozenset({"kind", "name", "nodes", "isat", "n", "vt", "gmin"}),
    # a transmission line is described by its delay and its impedance, and by
    # nothing else: 'len_mm'/'eps_eff' are deliberately absent, because tau
    # derived from geometry here would be a second source of truth for the one
    # number the line is actually made of.  Whoever lays the line out can
    # compute tau = len_mm * sqrt(eps_eff) / c and write it down.
    #
    # 'quarter_wave_hz' is the one thing a document may say about a line BESIDE
    # z0/tau, and it does not compete with tau: it names the tone the delay was
    # cut for, and tau must equal quarter_wave_tau(that tone) -- checked at
    # staging, so a file cannot claim one tone and carry another's delay.  It is
    # a declaration, not geometry: len_mm/eps_eff would let a *different* tau be
    # derived, whereas a tone names the tau already written down.  What it buys
    # is that the parser can RE-DERIVE tau for the tone a run is actually
    # analysed at (``parse_netlist(..., f_hz=...)``) instead of simulating a
    # line nobody asked for -- and can say so out loud when the two differ.
    "T": frozenset({"kind", "name", "nodes", "z0", "tau", "quarter_wave_hz"}),
}
_WAVEFORM_FIELDS = {
    "step": frozenset({"type", "amplitude", "delay"}),
    "sine": frozenset({"type", "amplitude", "frequency", "phase", "delay"}),
}
_RESERVED_WAVEFORMS = ("pulse",)
# Relative tolerance on the ONE consistency check a document gets against itself:
# a T element's ``tau`` versus ``quarter_wave_tau(quarter_wave_hz)``.  1e-6 is
# loose enough that a delay written down as a rounded float (and re-read on a
# different machine) still agrees with its own tone, and tight enough that an
# actual retune -- the smallest one in the tree is 3 % (5827786408.327286 Hz vs
# 6009904733.587513 Hz, evidence/termination/netlists/load_stub.json) -- cannot
# pass.  An absolute tolerance would be meaningless here: tau is ~1e-11 s, so
# 1e-6 s would accept every tone in the band.
_QUARTER_WAVE_RTOL = 1e-6


class NetlistError(ValueError):
    """A netlist document that cannot be turned into a circuit.

    A ``ValueError`` so that ``except ValueError`` catches it alongside
    ``Branch``'s own validation, which is reused rather than duplicated.  Every
    message names the offending element and field: nothing is repaired, and
    nothing is dropped in silence.
    """


@dataclass(frozen=True)
class Waveform:
    """A source level as a function of time, in SI units.

    Parameters
    ----------
    kind : {"step", "sine"}
        ``step`` is ``amplitude`` for ``t >= delay`` and ``0.0`` before;
        ``sine`` is ``amplitude * sin(2*pi*frequency*(t - delay) + phase)``.
        The step is right-continuous at ``t == delay``.
    amplitude : float
        Volts for a ``V`` source, amperes for an ``I`` source.  Any finite
        value, including a negative one.
    frequency : float, optional
        Hertz, strictly positive; required by ``sine``, not accepted by
        ``step``.
    phase : float, optional
        Radians, default ``0.0``.
    delay : float, optional
        Onset time in seconds, default ``0.0``, non-negative.  Before it the
        waveform contributes exactly ``0.0``.

    Callable, so the driver writes ``waveform(t)`` and the source level is
    ``value + waveform(t)``.  Frozen: a waveform is a description, not a
    generator, and holds no state across steps.
    """

    kind: str
    amplitude: float
    frequency: float | None = None
    phase: float = 0.0
    delay: float = 0.0

    def __post_init__(self):
        if self.kind not in _WAVEFORM_FIELDS:
            raise NetlistError(
                f"unknown waveform type {self.kind!r}; supported: "
                f"{sorted(_WAVEFORM_FIELDS)}"
            )
        for field_name in ("amplitude", "phase", "delay"):
            value = float(getattr(self, field_name))
            if not np.isfinite(value):
                raise NetlistError(
                    f"waveform field {field_name!r} must be finite; got "
                    f"{getattr(self, field_name)!r}"
                )
            object.__setattr__(self, field_name, value)
        if self.delay < 0.0:
            raise NetlistError(
                f"waveform field 'delay' must be non-negative; got {self.delay!r}"
            )
        if self.kind == "sine":
            if self.frequency is None:
                raise NetlistError("waveform field 'frequency' is required for a sine")
            frequency = float(self.frequency)
            if not np.isfinite(frequency) or frequency <= 0.0:
                raise NetlistError(
                    f"waveform field 'frequency' must be finite and positive; "
                    f"got {self.frequency!r}"
                )
            object.__setattr__(self, "frequency", frequency)
        elif self.frequency is not None:
            raise NetlistError(
                "waveform field 'frequency' is only meaningful for a sine; "
                f"a {self.kind!r} has no frequency"
            )

    def __call__(self, t):
        """The waveform's contribution at time ``t`` (s)."""
        t = float(t)
        if t < self.delay:
            return 0.0
        if self.kind == "step":
            return self.amplitude
        return self.amplitude * float(
            np.sin(2.0 * np.pi * self.frequency * (t - self.delay) + self.phase)
        )


@dataclass(frozen=True)
class Element:
    """One parsed element: its branch index, its names, and its source level.

    Parameters
    ----------
    kind, name : str
        ``kind`` in ``("R", "L", "C", "V", "I", "D", "T")``; ``name`` unique
        in the document.
    nodes : (int, int)
        Resolved node indices, ``0`` ground.  ``nodes[0] -> nodes[1]`` is the
        positive branch-current direction.
    value : float
        The ``Branch`` value: ohm, henry, farad, or for a source its **DC
        level**, which is what a source with no waveform carries.  A diode
        and a transmission line carry their model parameters on the ``Diode``
        / ``TransmissionLine`` branch instead and report ``0.0`` here.
    waveform : Waveform or None
        ``None`` for an element with a constant level.
    index : int
        Position in ``Netlist.elements``, which is the branch index in
        ``CircuitNetwork.branches`` and hence the column in
        ``TransientResult.branch_currents``.
    """

    kind: str
    name: str
    nodes: tuple
    value: float
    waveform: Waveform | None
    index: int

    @property
    def is_source(self):
        """``True`` for ``V`` and ``I``: only those may carry a waveform."""
        return self.kind in _SOURCE_KINDS


class _Columns:
    """Read-only ``name -> trace`` view over a ``(n_records, n_columns)`` array.

    Subscript by name (``result.v["out"]``) or by column number.  Exists so a
    test never has to know that ``"out"`` is node 2: the mapping is the same
    one :class:`Netlist` publishes.
    """

    __slots__ = ("_data", "_index", "_what")

    def __init__(self, data, index, what):
        self._data = data
        self._index = index
        self._what = what

    def __getitem__(self, key):
        if isinstance(key, (int, np.integer)) and not isinstance(key, bool):
            return self._data[:, int(key)]
        try:
            column = self._index[key]
        except KeyError:
            raise KeyError(
                f"no {self._what} named {key!r}; known names: {sorted(self._index)}"
            ) from None
        return self._data[:, column]

    def __contains__(self, key):
        return key in self._index

    def __iter__(self):
        return iter(self._index)

    def __len__(self):
        return len(self._index)

    def keys(self):
        """The names, in index order."""
        return tuple(sorted(self._index, key=self._index.__getitem__))

    def items(self):
        """``(name, trace)`` pairs, in index order."""
        return tuple((name, self[name]) for name in self.keys())


@dataclass(frozen=True)
class TransientResult:
    """A recorded transient: the time vector plus both current tables.

    Parameters
    ----------
    t : ndarray, shape (n_records,)
        ``[0, dt, 2*dt, ...]``; row 0 is the initial state, before any step.
    node_voltages : ndarray, shape (n_records, n_nodes)
        Column ``k`` is node ``k``; column ``0`` is ground and is all zeros.
    branch_currents : ndarray, shape (n_records, n_branches)
        Column ``k`` is the branch of ``Netlist.elements[k]``, positive
        ``nodes[0] -> nodes[1]``.
    netlist : Netlist
        The netlist the traces were produced from, which is where the name
        maps come from.

    ``v`` and ``i`` are name-indexed views of the two arrays.  Both arrays are
    flagged read-only when the record is built, so a caller cannot edit history
    by accident.
    """

    t: np.ndarray
    node_voltages: np.ndarray
    branch_currents: np.ndarray
    netlist: "Netlist"

    def __post_init__(self):
        for name in ("t", "node_voltages", "branch_currents"):
            array = np.asarray(getattr(self, name), dtype=float)
            array.setflags(write=False)
            object.__setattr__(self, name, array)

    @property
    def v(self):
        """Node-voltage traces by name, e.g. ``result.v["out"]``."""
        return _Columns(self.node_voltages, self.netlist.node_index, "node")

    @property
    def i(self):
        """Branch-current traces by element name, e.g. ``result.i["c1"]``."""
        return _Columns(self.branch_currents, self.netlist.element_index, "element")

    @property
    def n_records(self):
        """Number of recorded time points, ``n_steps + 1``."""
        return int(self.t.shape[0])

    def final(self):
        """The last row as ``(t, {node: v}, {element: i})`` floats."""
        return (
            float(self.t[-1]),
            {name: float(self.v[name][-1]) for name in self.v},
            {name: float(self.i[name][-1]) for name in self.i},
        )


@dataclass(frozen=True)
class Netlist:
    """A parsed netlist: the circuit, its two name maps, and the driver.

    Parameters
    ----------
    name : str
        The document's ``name`` (``""`` when absent); used in messages only.
    network : CircuitNetwork
        The circuit, in element order.  This is the whole parse: a caller that
        wants only a network reads this and never calls the driver.
    elements : tuple of Element
        In branch order; ``elements[k].index == k``.
    node_index : dict
        Name -> index, ground included as ``"0"``.
    node_names : tuple of str
        Index -> name, ``node_names[0] == "0"``.
    element_index : dict
        Element name -> branch index.
    quarter_wave : tuple of dict
        One record per ``T`` element that declared ``quarter_wave_hz``, in
        element order: ``{"name", "declared_hz", "tau_document_s", "tau_s",
        "f_hz"}``.  ``declared_hz`` is the tone the document's own ``tau`` was
        cut for; ``tau_s`` is the delay this parse actually DELIVERED (the
        document's, unless :func:`parse_netlist` was told the run's tone with
        ``f_hz``, in which case it is ``quarter_wave_tau(f_hz)``);
        ``tau_document_s`` is what the file itself said, kept so a retune is
        written down rather than inferred; ``f_hz`` is the tone the parse was
        asked for (``None`` when the caller did not say).  Empty for every
        document that declares no tone -- which is every document written
        before the field existed, and every document that has no ``T``.
    """

    name: str
    network: CircuitNetwork
    elements: tuple
    node_index: Mapping
    node_names: tuple
    element_index: Mapping
    # Trailing and DEFAULTED on purpose: ``()`` is the honest value for a
    # netlist that never said which tone its delays were cut for, and a caller
    # that builds a Netlist by hand (or reads only ``network``) keeps working
    # untouched.
    quarter_wave: tuple = ()

    def element(self, name):
        """The :class:`Element` called ``name``."""
        return self.elements[self.element_index[name]]

    @property
    def waveforms(self):
        """Waveforms in branch order; ``None`` where an element is constant."""
        return tuple(element.waveform for element in self.elements)

    def source_values(self, t):
        """Source levels at time ``t``, as the length-``n_branches`` vector.

        This is exactly what ``MNASolver.step(..., sources=...)`` takes:
        ``value + waveform(t)`` on the source branches (``value`` alone where
        there is no waveform) and each branch's own frozen ``value`` elsewhere,
        which the assembly never reads for ``R``/``L``/``C``.
        """
        t = float(t)
        if not np.isfinite(t):
            raise ValueError(f"t must be finite; got {t!r}")
        values = np.array([element.value for element in self.elements], dtype=float)
        for k, element in enumerate(self.elements):
            if element.waveform is not None:
                values[k] = element.value + element.waveform(t)
        return values

    def transient(self, *, dt, t_end=None, n_steps=None, scheme="backward_euler",
                  state=None):
        """Run the time loop and record every step.

        Parameters
        ----------
        dt : float
            Step size (s), finite and positive.
        t_end, n_steps : float, int, keyword-only, optional
            Exactly one of the two: either an end time, rounded to the nearest
            whole number of steps, or a step count directly.  Whichever is
            given, ``len(result.t) == n_steps + 1``.
        scheme : {"backward_euler", "trapezoidal"}, optional
            Passed to :class:`~emfit.spice.MNASolver`; the default is that
            solver's default.
        state : SpiceState, optional
            Initial history.  ``None`` means the solver's all-zero state.  It
            must belong to this netlist's own
            :class:`~emfit.spice.CircuitNetwork`; a state from an equal but
            distinct network is refused, because node counts and branch order
            would then agree only by coincidence.

        Returns
        -------
        TransientResult
            ``t``, ``node_voltages`` and ``branch_currents``, plus the ``v``
            and ``i`` name-indexed views.

        Sources are evaluated at ``t^{n+1}``, the point backward Euler solves
        the step at; see the module docstring for the record's ``t = 0`` row.
        """
        dt = float(dt)
        if not np.isfinite(dt) or dt <= 0.0:
            raise ValueError(f"dt must be finite and positive; got {dt!r}")
        if (t_end is None) == (n_steps is None):
            raise ValueError(
                "give exactly one of t_end or n_steps; got "
                f"t_end={t_end!r}, n_steps={n_steps!r}"
            )
        if n_steps is None:
            t_end = float(t_end)
            if not np.isfinite(t_end) or t_end <= 0.0:
                raise ValueError(f"t_end must be finite and positive; got {t_end!r}")
            n_steps = int(round(t_end / dt))
            if n_steps < 1:
                raise ValueError(
                    f"t_end = {t_end!r} is shorter than one step of dt = {dt!r}"
                )
        else:
            n_steps = int(n_steps)
            if n_steps < 1:
                raise ValueError(f"n_steps must be at least 1; got {n_steps!r}")

        solver = MNASolver(self.network, scheme=scheme)
        current = solver.initial_state() if state is None else state
        if current.network is not self.network:
            raise ValueError(
                "state was built for a different CircuitNetwork; a driver and "
                "its state must agree on the netlist"
            )

        times = [0.0]
        voltages = [np.array(current.u, dtype=float)]
        currents = [np.array(current.i_branch, dtype=float)]
        for step in range(1, n_steps + 1):
            t = step * dt
            current, u, i_branch = solver.step(
                dt, current, sources=self.source_values(t)
            )
            times.append(t)
            voltages.append(np.array(u, dtype=float))
            currents.append(np.array(i_branch, dtype=float))

        return TransientResult(
            t=np.array(times),
            node_voltages=np.array(voltages),
            branch_currents=np.array(currents),
            netlist=self,
        )

    simulate = transient


def _parse_json(text, where):
    """``json.loads`` with a message that says what was being read."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise NetlistError(f"{where}: not valid JSON: {exc}") from None


def _load_document(source):
    """A dict from a dict, a JSON string, or a path to a JSON file."""
    if isinstance(source, Mapping):
        return dict(source)
    if isinstance(source, bytes):
        return _parse_json(source.decode("utf-8"), "<bytes>")
    if isinstance(source, os.PathLike):
        with open(source, encoding="utf-8") as handle:
            return _parse_json(handle.read(), os.fspath(source))
    if isinstance(source, str):
        if source.lstrip().startswith("{"):
            return _parse_json(source, "<string>")
        if not os.path.exists(source):
            raise NetlistError(
                "netlist source is neither JSON text (it does not start with "
                f"'{{') nor an existing file: {source[:120]!r}"
            )
        with open(source, encoding="utf-8") as handle:
            return _parse_json(handle.read(), source)
    raise NetlistError(
        "netlist source must be a dict, a JSON string or a path; got "
        f"{type(source).__name__}"
    )


def _node_ref(token, where):
    """Canonical ``("idx", n)`` or ``("name", s)`` for one node reference."""
    if isinstance(token, bool) or not isinstance(token, (int, str)):
        raise NetlistError(
            f"{where}: field 'nodes' entries must be an int or a node name; "
            f"got {token!r}"
        )
    if isinstance(token, int):
        if token < 0:
            raise NetlistError(
                f"{where}: field 'nodes' may not name a negative index; got {token!r}"
            )
        return ("idx", int(token))
    text = token.strip()
    if not text:
        raise NetlistError(f"{where}: field 'nodes' may not contain a blank name")
    if text.lower() in _GROUND_NAMES:
        return ("idx", 0)
    if text.isdigit():
        return ("idx", int(text))
    return ("name", text)


def _waveform(spec, where):
    """Build a :class:`Waveform` from one element's ``waveform`` field."""
    if not isinstance(spec, Mapping):
        raise NetlistError(
            f"{where}: field 'waveform' must be an object; got {spec!r}"
        )
    kind = spec.get("type")
    if kind is None:
        raise NetlistError(f"{where}: field 'waveform.type' is required")
    if not isinstance(kind, str):
        raise NetlistError(
            f"{where}: field 'waveform.type' must be a string; got {kind!r}"
        )
    if kind in _RESERVED_WAVEFORMS:
        raise NetlistError(
            f"{where}: waveform type {kind!r} is reserved and NOT implemented; "
            f"supported: {sorted(_WAVEFORM_FIELDS)}"
        )
    if kind not in _WAVEFORM_FIELDS:
        raise NetlistError(
            f"{where}: unknown waveform type {kind!r}; supported: "
            f"{sorted(_WAVEFORM_FIELDS)} ({', '.join(_RESERVED_WAVEFORMS)} is "
            "reserved and not implemented)"
        )
    unknown = set(spec) - _WAVEFORM_FIELDS[kind]
    if unknown:
        raise NetlistError(
            f"{where}: unexpected waveform field(s) {sorted(unknown)} for a "
            f"{kind!r}; allowed: {sorted(_WAVEFORM_FIELDS[kind])}"
        )
    if "amplitude" not in spec:
        raise NetlistError(
            f"{where}: field 'waveform.amplitude' is required for a {kind!r}"
        )
    kwargs = {"kind": kind, "amplitude": spec["amplitude"]}
    if kind == "sine" and "frequency" not in spec:
        raise NetlistError(
            f"{where}: field 'waveform.frequency' is required for a 'sine'"
        )
    for field_name in ("frequency", "phase", "delay"):
        if field_name in spec:
            kwargs[field_name] = spec[field_name]
    try:
        return Waveform(**kwargs)
    except NetlistError as exc:
        raise NetlistError(f"{where}: field 'waveform': {exc}") from None


def quarter_wave_tau(f_hz):
    """The delay of a line that is a quarter wave long at ``f_hz``.

    ``tau = 1 / (4 f)``.  At that tone a lossless line of delay ``tau``,
    shorted at its far end, presents ``Zin = j z0 tan(2 pi f tau) =
    j z0 tan(pi/2)``, i.e. it looks like an OPEN -- which is exactly what a
    quarter-wave stub termination is for (see
    ``evidence/termination/netlists/load_stub.md``).

    This is the single definition of the number a ``T`` element's ``tau`` and a
    document's ``quarter_wave_hz`` are tied together by: the parser checks a
    document against it, and re-derives the DELIVERED ``tau`` from it when it is
    told the tone the run will actually be analysed at.  One expression, one
    home -- a second copy of ``1/(4f)`` in a caller is how the two drift apart.

    Parameters
    ----------
    f_hz : float
        Hertz, finite and strictly positive.

    Returns
    -------
    float
        Seconds.

    Raises
    ------
    ValueError
        ``f_hz`` is not a finite, strictly positive number.  (A ``ValueError``
        because :class:`NetlistError` is one; the parser re-raises it as a
        ``NetlistError`` naming the element and the field.)
    """
    try:
        f_hz = float(f_hz)
    except (TypeError, ValueError):
        raise ValueError(
            f"a quarter-wave tone must be a number in hertz; got {f_hz!r}"
        ) from None
    if not np.isfinite(f_hz) or f_hz <= 0.0:
        raise ValueError(
            f"a quarter-wave tone must be finite and strictly positive; got "
            f"{f_hz!r}"
        )
    return 1.0 / (4.0 * f_hz)


def parse_netlist(source, *, f_hz=None):
    """Parse a JSON netlist into a :class:`Netlist`.

    Parameters
    ----------
    source : dict, str or path-like
        A mapping (already-parsed JSON), JSON text (it must start with ``{``),
        or a path to a file holding that text.  A string that starts with
        ``{`` is always read as text; anything else is treated as a path and
        reported as such if no such file exists.
    f_hz : float, keyword-only, optional
        The tone the circuit will actually be ANALYSED at, in hertz.  When
        given, every ``T`` element that declares ``quarter_wave_hz`` is
        delivered ``tau = quarter_wave_tau(f_hz)`` -- the delay of a quarter
        wave at THIS tone -- instead of the ``tau`` written in the document,
        and the substitution is recorded in :attr:`Netlist.quarter_wave`.  A
        ``T`` element that declares no tone is never touched: nothing here can
        know what its delay was cut for.  ``None`` (the default) delivers every
        ``tau`` exactly as written, so a caller that does not know its tone gets
        the document verbatim and byte-identical behaviour to before the
        parameter existed.

    Returns
    -------
    Netlist

    Raises
    ------
    NetlistError
        A ``ValueError``.  Rejected, with the element and field named: an
        unknown ``kind``; a missing or unexpected field; a duplicate element
        name; a node reference outside a declared ``nodes`` list, or a
        malformed one; fewer than two distinct nodes; a non-finite value, or a
        non-positive one where the element requires positive (``R``, ``L``,
        ``C`` -- that check is ``Branch``'s, reused here and only re-worded to
        name the element); a ``waveform`` on a non-source; a source with
        neither ``value`` nor ``waveform``; an unknown, malformed or reserved
        waveform; a ``quarter_wave_hz`` that is not a finite positive frequency,
        or that disagrees with the element's own ``tau`` (relative tolerance
        ``1e-6`` -- a document may not declare one tone and carry another's
        delay).  Nothing is repaired, defaulted away or dropped; the one thing
        that is DERIVED rather than copied is a declared ``tau`` for the tone
        given as ``f_hz``, and that derivation is recorded in the Netlist.
    """
    document = _load_document(source)
    if not isinstance(document, Mapping):
        raise NetlistError(
            "a netlist document must be a JSON object; got "
            f"{type(document).__name__}"
        )
    unknown_top = set(document) - set(_TOP_FIELDS)
    if unknown_top:
        raise NetlistError(
            f"top level: unexpected field(s) {sorted(unknown_top)}; allowed: "
            f"{list(_TOP_FIELDS)}"
        )
    if "elements" not in document:
        raise NetlistError("top level: field 'elements' is required")

    name = document.get("name", "")
    if not isinstance(name, str):
        raise NetlistError(
            f"top level: field 'name' must be a string; got {name!r}"
        )
    raw_elements = document["elements"]
    if not isinstance(raw_elements, (list, tuple)):
        raise NetlistError(
            f"top level: field 'elements' must be a list; got "
            f"{type(raw_elements).__name__}"
        )
    declared = document.get("nodes", None)
    if declared is not None and not isinstance(declared, (list, tuple)):
        raise NetlistError(
            f"top level: field 'nodes' must be a list of node names; got "
            f"{type(declared).__name__}"
        )

    # -- pass 1: element fields, in document order -------------------------
    staged = []
    seen_names = {}
    for position, entry in enumerate(raw_elements):
        if not isinstance(entry, Mapping):
            raise NetlistError(
                f"element #{position}: must be an object; got "
                f"{type(entry).__name__}"
            )
        kind = entry.get("kind")
        label = (
            f"element {entry['name']!r}"
            if isinstance(entry.get("name"), str) and entry.get("name")
            else f"element #{position}"
        )
        if kind is None:
            raise NetlistError(f"{label}: field 'kind' is required")
        if not isinstance(kind, str) or kind not in _KINDS:
            raise NetlistError(
                f"{label}: unknown kind {kind!r}; expected one of {list(_KINDS)}"
            )
        unknown = set(entry) - _ELEMENT_FIELDS[kind]
        if unknown:
            raise NetlistError(
                f"{label}: unexpected field(s) {sorted(unknown)} for a {kind} "
                f"element; allowed: {sorted(_ELEMENT_FIELDS[kind])}"
            )
        element_name = entry.get("name")
        if not isinstance(element_name, str) or not element_name.strip():
            raise NetlistError(
                f"{label}: field 'name' is required and must be a non-blank "
                f"string; got {element_name!r}"
            )
        if element_name in seen_names:
            raise NetlistError(
                f"{label}: duplicate element name {element_name!r}, already used "
                f"by element #{seen_names[element_name]}"
            )
        seen_names[element_name] = position

        nodes = entry.get("nodes")
        if not isinstance(nodes, (list, tuple)) or len(nodes) != 2:
            raise NetlistError(
                f"{label}: field 'nodes' must be a two-entry list; got {nodes!r}"
            )
        refs = tuple(_node_ref(token, label) for token in nodes)

        has_waveform = "waveform" in entry
        if has_waveform and kind not in _SOURCE_KINDS:
            raise NetlistError(
                f"{label}: field 'waveform' is only allowed on a source (V or "
                f"I); a {kind} carries a constant 'value'"
            )
        if kind in _SOURCE_KINDS and not has_waveform and "value" not in entry:
            raise NetlistError(
                f"{label}: a {kind} source needs a 'value' (a DC level) or a "
                "'waveform'; got neither"
            )
        if kind not in _SOURCE_KINDS + ("D", "T") and "value" not in entry:
            raise NetlistError(f"{label}: field 'value' is required for a {kind}")
        value = entry.get("value", 0.0)
        waveform = _waveform(entry["waveform"], label) if has_waveform else None
        model = {}
        # A T element's tone declaration, carried from here to the build pass,
        # where the delay is actually decided.  ``None`` on every other kind,
        # and on a T that declares no tone -- which is then taken exactly as
        # written, for ever, because nothing here can know what its delay was
        # cut for.
        quarter_wave = None
        if kind == "D":
            # defaults mirror the Diode dataclass; validation of the numbers
            # themselves is Diode's job, so it happens in one place only
            for field, default in (
                ("isat", 1e-14), ("n", 1.0), ("vt", 0.02585), ("gmin", 1e-12),
            ):
                model[field] = entry.get(field, default)
        elif kind == "T":
            # No defaults, on purpose: TransmissionLine would fall back to
            # z0 = 50 ohm / tau = 1 ns, so a netlist that simply forgot its
            # delay would simulate a line nobody asked for.  Both are required.
            for field in ("z0", "tau"):
                if field not in entry:
                    raise NetlistError(
                        f"{label}: a T element needs '{field}' (SI: ohm, s); "
                        "the parser carries no default for it"
                    )
                model[field] = entry[field]
            # The optional tone declaration, checked against the document's
            # OWN tau.  This is the one place the file is held to the single
            # number it is made of: without it a document could say "cut for
            # 5.83 GHz" while carrying 4.16e-11 s, and a reader (or a later
            # re-derivation from the declared tone) would be reading a lie.
            # The check is RELATIVE (1e-6): tau is ~1e-11 s here, so an
            # absolute tolerance would accept every tone in the band, and an
            # actual retune in this tree is a 3 % move, not a rounding noise.
            declared_hz = entry.get("quarter_wave_hz")
            if declared_hz is not None:
                try:
                    declared_tau = quarter_wave_tau(declared_hz)
                except ValueError as exc:
                    raise NetlistError(
                        f"{label}: field 'quarter_wave_hz': {exc}"
                    ) from None
                try:
                    stated_tau = float(entry["tau"])
                except (TypeError, ValueError):
                    stated_tau = float("nan")
                if not (
                    np.isfinite(stated_tau)
                    and abs(stated_tau - declared_tau)
                    <= _QUARTER_WAVE_RTOL * declared_tau
                ):
                    raise NetlistError(
                        f"{label}: field 'tau' ({entry['tau']!r} s) is not the "
                        f"quarter-wave delay of field 'quarter_wave_hz' "
                        f"({declared_hz!r} Hz), which is "
                        f"quarter_wave_tau = {declared_tau!r} s; a T element "
                        "may not declare one tone and carry another's delay "
                        "-- write the tau that belongs to the tone, or drop "
                        "the declaration"
                    )
                quarter_wave = {
                    "declared_hz": float(declared_hz),
                    "tau_document_s": stated_tau,
                }
        staged.append(
            {
                "kind": kind,
                "name": element_name,
                "refs": refs,
                "value": value,
                "model": model,
                "waveform": waveform,
                "quarter_wave": quarter_wave,
                "label": label,
            }
        )

    # -- node numbering: explicit indices first, then names in fixed order --
    indices = {0}
    for element in staged:
        for kind_token, token in element["refs"]:
            if kind_token == "idx":
                indices.add(token)
    next_free = max(indices) + 1

    node_index = {"0": 0}
    node_names = {0: "0"}
    declared_names = []
    declared_indices = set()
    if declared is not None:
        for position, token in enumerate(declared):
            kind_token, raw = _node_ref(token, f"top level: field 'nodes'[{position}]")
            if kind_token == "idx":
                indices.add(raw)
                declared_indices.add(raw)
                continue
            if raw in declared_names:
                raise NetlistError(
                    f"top level: field 'nodes' declares {raw!r} twice"
                )
            declared_names.append(raw)
        next_free = max(indices) + 1

    for raw in declared_names:
        node_index[raw] = next_free
        node_names[next_free] = raw
        declared_indices.add(next_free)
        next_free += 1

    for element in staged:
        for kind_token, token in element["refs"]:
            if kind_token == "name" and token not in node_index:
                if declared is not None:
                    raise NetlistError(
                        f"{element['label']}: unknown node name {token!r}; the "
                        f"declared nodes are {sorted(node_index)} "
                        "(plus ground as 0, '0', 'gnd', 'ground')"
                    )
                node_index[token] = next_free
                node_names[next_free] = token
                next_free += 1

    resolved = []
    for element in staged:
        pair = []
        for kind_token, token in element["refs"]:
            pair.append(token if kind_token == "idx" else node_index[token])
        resolved.append(tuple(pair))

    used = {0} | {node for pair in resolved for node in pair}
    if len(used) < 2:
        raise NetlistError(
            f"netlist {name!r}: fewer than 2 distinct nodes "
            f"({sorted(node_names[node] for node in used)}); a circuit needs at "
            "least two nodes, one of them ground"
        )
    n_nodes = max(used) + 1
    # every node number below n_nodes needs a name, so an explicit index that
    # the netlist uses but does not name is still addressable in the record
    for index in range(n_nodes):
        if index not in node_names:
            node_names[index] = str(index)
            node_index.setdefault(str(index), index)
    for index in sorted(declared_indices):
        if index not in used:
            raise NetlistError(
                "top level: field 'nodes' declares "
                f"{node_names[index]!r} as node {index}, but no element reaches "
                "it; declare only nodes the netlist uses"
            )

    # -- pass 2: the branches ---------------------------------------------
    branches = []
    elements = []
    element_index = {}
    # One record per T element that declared the tone its delay was cut for;
    # empty for every other document, so :attr:`Netlist.quarter_wave` says
    # "nothing was declared" rather than "nothing was needed".
    quarter_wave_records = []
    for k, (element, nodes) in enumerate(zip(staged, resolved)):
        label = element["label"]
        if element["kind"] == "D":
            try:
                branch = Diode(nodes, **element["model"])
            except (TypeError, ValueError) as exc:
                raise NetlistError(f"{label}: field 'model': {exc}") from None
            branch_value = 0.0
        elif element["kind"] == "T":
            model = dict(element["model"])
            # The delay, decided HERE, once: if the document declared the tone
            # its tau was cut for, then tau belongs to that tone and is
            # re-derived for the tone this parse was asked about (``f_hz``,
            # the tone the run will actually be analysed at).  With no ``f_hz``
            # the document's own number is delivered unchanged, which is what
            # keeps every existing caller byte-identical.
            #
            # Why derive it here rather than in the caller: the caller would
            # have to reach into the branch list and poke ``tau`` on a frozen
            # TransmissionLine, i.e. two sources of truth for one number.  The
            # record below is what the caller gets to warn about; the number
            # itself is decided in the one place that builds branches.
            declared = element["quarter_wave"]
            if declared is not None:
                delivered_tau = declared["tau_document_s"]
                if f_hz is not None:
                    # f_hz is validated by quarter_wave_tau itself; a bad tone
                    # is a caller error, so it propagates as the ValueError it
                    # is rather than being re-worded as a document error.
                    delivered_tau = quarter_wave_tau(f_hz)
                model["tau"] = delivered_tau
                quarter_wave_records.append(
                    {
                        "name": element["name"],
                        "declared_hz": declared["declared_hz"],
                        "tau_document_s": declared["tau_document_s"],
                        "tau_s": delivered_tau,
                        "f_hz": None if f_hz is None else float(f_hz),
                    }
                )
            try:
                branch = TransmissionLine(nodes, **model)
            except (TypeError, ValueError) as exc:
                raise NetlistError(f"{label}: {exc}") from None
            branch_value = 0.0
        else:
            try:
                branch = Branch(element["kind"], nodes, element["value"])
            except (TypeError, ValueError) as exc:
                raise NetlistError(f"{label}: field 'value': {exc}") from None
            branch_value = branch.value
        branches.append(branch)
        element_index[element["name"]] = k
        elements.append(
            Element(
                kind=element["kind"],
                name=element["name"],
                nodes=branch.nodes,
                value=branch_value,
                waveform=element["waveform"],
                index=k,
            )
        )

    network = CircuitNetwork(branches=tuple(branches), n_nodes=n_nodes)
    return Netlist(
        name=name,
        network=network,
        elements=tuple(elements),
        node_index=dict(node_index),
        node_names=tuple(node_names[index] for index in range(n_nodes)),
        element_index=element_index,
        quarter_wave=tuple(quarter_wave_records),
    )
