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

from .spice import Branch, CircuitNetwork, Diode, MNASolver

__all__ = [
    "Element",
    "Netlist",
    "NetlistError",
    "TransientResult",
    "Waveform",
    "parse_netlist",
]

_KINDS = ("R", "L", "C", "V", "I", "D")
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
}
_WAVEFORM_FIELDS = {
    "step": frozenset({"type", "amplitude", "delay"}),
    "sine": frozenset({"type", "amplitude", "frequency", "phase", "delay"}),
}
_RESERVED_WAVEFORMS = ("pulse",)


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
        ``kind`` in ``("R", "L", "C", "V", "I", "D")``; ``name`` unique in
        the document.
    nodes : (int, int)
        Resolved node indices, ``0`` ground.  ``nodes[0] -> nodes[1]`` is the
        positive branch-current direction.
    value : float
        The ``Branch`` value: ohm, henry, farad, or for a source its **DC
        level**, which is what a source with no waveform carries.  A diode
        carries its model parameters on the ``Diode`` branch instead and
        reports ``0.0`` here.
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
    """

    name: str
    network: CircuitNetwork
    elements: tuple
    node_index: Mapping
    node_names: tuple
    element_index: Mapping

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


def parse_netlist(source):
    """Parse a JSON netlist into a :class:`Netlist`.

    Parameters
    ----------
    source : dict, str or path-like
        A mapping (already-parsed JSON), JSON text (it must start with ``{``),
        or a path to a file holding that text.  A string that starts with
        ``{`` is always read as text; anything else is treated as a path and
        reported as such if no such file exists.

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
        waveform.  Nothing is repaired, defaulted away or dropped.
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
        if kind not in _SOURCE_KINDS + ("D",) and "value" not in entry:
            raise NetlistError(f"{label}: field 'value' is required for a {kind}")
        value = entry.get("value", 0.0)
        waveform = _waveform(entry["waveform"], label) if has_waveform else None
        model = {}
        if kind == "D":
            # defaults mirror the Diode dataclass; validation of the numbers
            # themselves is Diode's job, so it happens in one place only
            for field, default in (
                ("isat", 1e-14), ("n", 1.0), ("vt", 0.02585), ("gmin", 1e-12),
            ):
                model[field] = entry.get(field, default)
        staged.append(
            {
                "kind": kind,
                "name": element_name,
                "refs": refs,
                "value": value,
                "model": model,
                "waveform": waveform,
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
    for k, (element, nodes) in enumerate(zip(staged, resolved)):
        label = element["label"]
        if element["kind"] == "D":
            try:
                branch = Diode(nodes, **element["model"])
            except (TypeError, ValueError) as exc:
                raise NetlistError(f"{label}: field 'model': {exc}") from None
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
    )
