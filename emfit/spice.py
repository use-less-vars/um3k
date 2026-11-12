"""An independent MNA circuit solver, and the FDTD/circuit port coupling.

This module is two separable things.

``MNASolver`` is a plain linear circuit solver: ``R``, ``L``, ``C``, ideal
voltage sources and independent current sources between numbered nodes,
assembled into the modified-nodal-analysis system and solved with
``np.linalg.solve``.  Node ``0`` is ground and is eliminated (its row and
column are never built); node ``k`` is unknown ``k - 1``.  Its companions are
**backward Euler** (``C -> C/h``, ``L -> h/L``).  Backward Euler is used here on
purpose: it is the scheme this solver is specified with.  What that scheme
actually does against a closed form -- and the order *observed* when ``dt`` is
halved, rather than the order the textbook assigns to it -- is pinned by
``tests/test_spice.py`` and quoted under "Measured agreement" below.

``SpicePort`` couples that network to an existing
:class:`emfit.terminations.TerminalPort` where
:func:`emfit.terminations.step_rlc` sits, with the same calling shape and the
same return triple, so a caller can swap one for the other.  Its companions are
**trapezoidal**, because ``step_rlc`` is trapezoidal: the coupled step is then
the generalisation of ``step_rlc`` from one series RLC per terminal to an
arbitrary linear network, not a second, differently-integrated path.  Over
eight steps on a series RLC (``R = 50``, ``L = 1e-9``, ``C = 1e-12``, ``dt =
1e-10``) the two agree to ``max|de| = 6.661e-16``, ``max|di| = 2.765e-18`` and
``max|dv| = 1.110e-15``.  That agreement is **discretisation consistency**, not
validation against theory (see below).  Under trapezoidal companions the
per-step energy balance closes at round-off -- ``max|resid| = 1.050e-25`` on
R-C, ``1.333e-19`` on R-L -- while backward Euler leaves a real per-step
defect, ``1.994e-15`` and ``1.250e-14`` on the same two circuits from the same
consistent ``t = 0`` state.  Halving ``dt`` cuts the backward-Euler residual by
a factor ``3.994`` (R-C) and ``4.000`` (R-L), i.e. measured order 2.00 in
``dt``: that residual is a one-step truncation defect, not round-off.  Both
schemes come out of one assembly routine.

What a passing balance test does NOT establish
----------------------------------------------
``e^T j_port = v_p^T i_p`` (see ``emfit/terminations.py``) is an **algebraic
tautology for any invertible ``W_E``**: symmetry is never used, no conservation
law is being proven, and junk matrices satisfy it.  It is a
shape-and-convention check and it is **not** used as an acceptance criterion
anywhere here.

What the coupling test does establish is **discretisation consistency**: over a
step the circuit and the field exchange the same power, and the network
conserves (or dissipates) exactly what the trapezoidal rule says it should.
That is the algebra of the scheme agreeing with itself.  It is **not
validation** of the physics, it is not a comparison against a measured field,
and **ledger item E5 remains UNVERIFIED after this module lands.**

Measured agreement (pinned by ``tests/test_spice.py``)
-----------------------------------------------------
Every figure below is a printed measurement from that file -- 11 gates -- not
an estimate.

``MNASolver`` against closed forms.  A 1 V source across two 1 k resistors
reaches the exact DC operating point: ``u2 = 0.5`` with ``err = 0.000e+00``.
R-C charging against ``1 - exp(-t/(RC))``: ``err(dt = 5e-8) = 9.010e-03``,
``err(dt/2) = 4.551e-03``, measured order 0.985.  R-L current rise against
``(1/R)(1 - exp(-Rt/L))``: ``9.010e-06``, ``4.551e-06``, measured order 0.985.
The undriven L-C tank at ``w0 = 3.1623e+07`` rad/s: ``3.889e-01 -> 2.200e-01``,
measured order 0.822 -- the amplitude decay there is backward Euler's numerical
damping, not physics, so the gate pins the measured 0.822 rather than the order
the scheme would show on a better-behaved problem.

The coupled balance, ``U_f`` plus the network terms.  Operator's case --
``R = 50`` across the port, ``L = [[1],[-1]]``, ``W_E = diag([1.3, 0.7])``, a
consistent ``t = 0`` state, six steps at ``dt = 1e-10``: ``max|resid| =
2.174e-28`` against per-step energies of order ``1e-13``.  The per-step
*relative* residual grows from ``2.428e-16`` to ``9.529e-05`` only because both
terms decay to about ``1e-24``; the absolute residual stays at a ``~1e-28``
round-off floor, so that growth is not a loss of accuracy.  R||C at the terminal:
``max|resid| = 1.041e-25``.  R-L: ``5.756e-27``.  A series R-C to ground is
DC-blocked -- with a static field and a consistent ``t = 0`` state every
balance term is identically 0.0, so it gates nothing -- and the live
capacitance evidence is therefore R||C at the terminal.

The energy statement, and exactly when it is exact
--------------------------------------------------
For the field update ``e^{n+1} = e* - (dt/2) m_eps^{-1} W_E^{-1} L s`` with
``s = i^{n+1} + i^n``, the per-step balance is

    dU_f + dU_L + dU_C + (dt/4) * sum_R R_k s_k^2 = 0

with ``U_L = (1/2) L i_l^2``, ``U_C = (1/2) C v_c^2`` and the Joule term summed
over the **R branches only**: ``(dt/4) s_v s_i`` evaluated on a ``C`` or ``L``
branch *is* ``dU_C`` or ``dU_L``, so adding a Joule term for those branches
would double-count them.

The field functional is the easy part to get wrong, so it is stated rather than
buried: the ``Q`` that closes the balance is ``Q = diag(w * m_eps)`` with
``w = diag(W_E)``, i.e.

    U_f = (1/2) * sum_k w_k * m_k * e_k^2,

which equals the familiar ``(1/2) m_eps . e^2`` **only when ``W_E = I``**.  The
port term that enters the balance uses the terminal voltage from the
**previous** step -- ``v = L.T @ e^n``, not ``e^{n+1}`` -- so the field
contribution is

    dU_f = -(dt/4) * s . (v' + v).

Negative result, stated as such rather than as a footnote: for a
**non-diagonal** ``W_E = [[1.3, 0.2], [0.2, 0.7]]`` the balance does **not**
close.  The measured ``max|resid| = 1.014e-13``, relative up to ``1.0``, sits
orders of magnitude above the diagonal cases.  ``Q = W_E diag(m_eps)`` is not
symmetric, so **no** symmetric quadratic energy closes the per-step balance and
``U_f`` is bookkeeping only for a full metric.  No exactness is claimed there,
and the gate pinning it asserts the residual is non-zero instead of absorbing
it into a tolerance.

Reuse, and what is deliberately absent
--------------------------------------
Every field/circuit exchange goes through the port's own functionals:
``voltage`` for ``v = L.T @ e``, ``current_density`` for the metric solve
``W_E^{-1} L i``, and ``port_power`` as the single power convention.  ``W_E``
is never inverted here, no second metric is formed, and ``L`` is never
re-derived.  The three impedance names of the scope document
(``TerminalImpedance``, ``ModalCharacteristicImpedance``,
``SParameterReferenceImpedance``) are **not** created as types and never
convert into one another.

Absent on purpose: no SPICE-syntax reader, no subcircuits, no ``.model``, no
transmission line, no adaptive step, no operating-point solve, and no
``s_parameters`` (the ``(I - z0 Y)(I + z0 Y)^{-1}`` check against
``(R - z0)/(R + z0)`` was never carried out -- no closed-form verification
was ever obtained -- so the method was dropped rather than shipped unverified).

The one thing this module does now carry is a **per-step source level**.
:meth:`MNASolver.step` and :meth:`SpicePort.step` take a keyword-only
``sources`` vector of length ``n_branches``; ``None`` (the default, and the
only form used by ``tests/test_spice.py``) leaves every ``V``/``I`` branch at
its frozen ``value``.  Nothing here evaluates a waveform, owns a clock or reads
a file: :mod:`emfit.netlist` parses a JSON netlist into a
:class:`CircuitNetwork`, evaluates the waveforms it declares at each step, and
passes that vector in.  A ``V``/``I`` branch is therefore still immutable --
the level moves in the argument, not in the branch -- and a step still depends
only on ``(dt, state, sources)``, plus the Newton bound ``max_iter`` below.

Nonlinear steps
---------------
:class:`Diode` is the one nonlinear device, and it is **not** linearised once
and for all: :meth:`MNASolver.step` and :meth:`SpicePort.step` run a
Newton-Raphson loop *inside* the time step, re-stamping each junction at the
current iterate until the junction voltages stop moving.  Only the diode's own
stamp is re-evaluated and the same ``A x = b`` is solved again, so the history
vectors keep their meaning and the linear path is untouched: a network with no
diode assembles once and solves once, exactly as before.  What the loop adds is
a convergence claim the linear part never needed, so a step that fails to
converge **raises** :class:`DiodeConvergenceError` -- carrying its iteration
count and last update -- instead of returning its last iterate.  There is still
no operating-point solve: the loop converges *this step* starting from the
previous state's junction voltages, and ``initial_state()`` is still all zeros.

Sign conventions
----------------
Terminal current ``i`` is positive *into* the network at its terminal node and
terminal voltage is ``L.T @ e``; a positive ``TerminalPort.port_power`` means
power is delivered from the field into the circuit's positive terminal, the
convention ``emfit/terminations.py`` pins and the only one used here.  A branch
current is positive from ``branch.nodes[0]`` to ``branch.nodes[1]``, and an
``I`` branch drives ``value`` amperes through itself from ``nodes[0]`` to
``nodes[1]`` (so it injects into ``nodes[1]``).  A ``D`` branch's current is its
conduction current from anode ``nodes[0]`` to cathode ``nodes[1]``, reported at
the solved junction voltage.

The field energy functional ``U_f = (1/2) sum_k w_k m_k e_k^2`` is exported as
:func:`U_f`, so a caller that needs it (a balance check, say) reads the module's
statement instead of re-deriving it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .terminations import TerminalPort

__all__ = [
    "Branch",
    "CircuitNetwork",
    "Diode",
    "DiodeConvergenceError",
    "TransmissionLine",
    "SpiceState",
    "MNASolver",
    "SpicePort",
    "U_f",
]

_GROUND = 0
_KINDS = ("R", "L", "C", "V", "I")
_SCHEMES = ("backward_euler", "trapezoidal")

# Newton loop of one step, for the diodes only.  ``max_iter`` is a bound, not an
# iteration target: a step that reaches it is refused, never accepted.
_MAX_ITER = 100
# Convergence is on the junction voltages alone, ``max_j |dv_j| <=
# reltol * max_j |v_j| + vntol``.  1e-9 is far tighter than SPICE's 1e-3 because
# a time step is not an operating point: what the loop must deliver is the
# exact root of *this step's* discretised equations, so the only error left
# when it returns should be the companion model's own.  Newton is quadratic, so
# the extra digits cost one or two iterations.  1e-12 V absolute catches the
# reverse-biased junction, whose voltage is ~1e-11 V: a purely relative test
# there would ask for updates below what float64 resolves and the loop could
# never satisfy it.
_RELTOL = 1e-9
_VNTOL = 1e-12
# ``exp`` argument clamp for the junction exponential; see ``Diode.current``.
_EXP_CLAMP = 100.0


@dataclass(frozen=True)
class Branch:
    """One lumped element between two nodes, in SI units.

    Parameters
    ----------
    kind : {"R", "L", "C", "V", "I"}
        ``R`` ohm, ``L`` henry, ``C`` farad, ``V`` volt, ``I`` ampere.
    nodes : (int, int)
        ``(a, b)``, node ``0`` is ground.  For ``R``, ``L``, ``C`` the element
        sits between ``a`` and ``b``; for ``V`` it fixes ``u_a - u_b``; for
        ``I`` it drives current from ``a`` to ``b`` through the source.
    value : float
        ``R``, ``L``, ``C`` must be **positive**: a zero would be a short or an
        open, which is expressed by *omitting* the branch, not by a zero here.

    Carries no geometry, no net name and no position; placement is
    :mod:`emfit.board`'s job.  Frozen, so a solved netlist cannot be edited in
    place.
    """

    kind: str
    nodes: tuple
    value: float

    def __post_init__(self):
        if self.kind not in _KINDS:
            raise ValueError(f"kind must be one of {_KINDS}; got {self.kind!r}")
        nodes = tuple(int(n) for n in self.nodes)
        if len(nodes) != 2:
            raise ValueError(f"nodes must be a pair (a, b); got {self.nodes!r}")
        if min(nodes) < 0:
            raise ValueError(f"node indices are non-negative; got {nodes}")
        value = float(self.value)
        if not np.isfinite(value):
            raise ValueError(f"value must be finite; got {self.value!r}")
        if self.kind in ("R", "L", "C") and value <= 0.0:
            raise ValueError(
                f"{self.kind} must be finite and positive; got {value!r}.  A "
                f"zero {self.kind} is an absent element here -- omit the branch "
                "instead, so the two can never be confused"
            )
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "value", value)


class DiodeConvergenceError(RuntimeError):
    """The Newton loop inside one step did not converge.

    A ``RuntimeError`` because it is not a bad argument -- the caller passed a
    legal ``dt`` and a legal state -- but a step this module refuses to accept.
    Nothing is returned alongside it: handing back the last iterate would be a
    silently wrong answer that only a later comparison could catch, so the loop
    stops instead.

    Attributes
    ----------
    iterations : int
        How many Newton iterations were taken, i.e. ``max_iter``.
    step : float
        The last measured junction-voltage update ``max_j |dv_j|``, in volts.
    tolerance : float
        The tolerance that update had to meet, in volts.  ``step`` and
        ``tolerance`` together say *how far* from convergence it stopped, which
        an iteration count alone does not.
    """

    def __init__(self, message, *, iterations, step, tolerance):
        super().__init__(message)
        self.iterations = int(iterations)
        self.step = float(step)
        self.tolerance = float(tolerance)


@dataclass(frozen=True)
class Diode:
    """A junction diode: Shockley conduction in parallel with ``gmin``.

    Parameters
    ----------
    nodes : (int, int)
        ``(a, b)``, **anode first**: conduction current is positive from
        ``nodes[0]`` to ``nodes[1]``.  Node ``0`` is ground, the two nodes must
        be distinct, and a diode adds no node of its own.
    isat : float, optional
        Saturation current (A), default ``1e-14``.
    n : float, optional
        Emission coefficient, default ``1.0`` -- the ideal-junction value.
    vt : float, optional
        Thermal voltage ``k T / q`` (V), default ``0.02585``.
    gmin : float, optional
        Parallel leakage conductance (S), default ``1e-12``.

    The defaults are **model parameters for a silicon junction near 300 K, not
    the physics**: nothing here measures a temperature, a band gap or a doping
    profile, and no junction capacitance is modelled.  ``vt`` is a plain
    parameter precisely so that a run at another temperature can pass
    ``vt = 8.617333e-5 * T`` and get the exponential's scale right, while
    ``isat`` and ``n`` stay whatever the caller measured; a germanium junction
    is a different ``isat``, not a different class.

    ``gmin`` is part of the **model**, not a solver regulariser: it is stamped
    as a real conductance and it appears on both sides of every current this
    class reports, so the law is exactly

    ``I(v) = isat * (exp(v / (n vt)) - 1) + gmin * v``

    ``g(v) = dI/dv = (isat / (n vt)) * exp(v / (n vt)) + gmin``.

    Without it a strongly reverse-biased junction would carry exactly ``-isat``
    with zero slope, and a netlist whose only path to ground ran through that
    junction would be singular; ``gmin`` gives it a finite, physical slope
    instead.  It is the same element SPICE's own diodes carry, and it is why a
    reverse-biased diode here is an emitter of ``-isat``, not an open circuit.
    """

    nodes: tuple
    isat: float = 1e-14
    n: float = 1.0
    vt: float = 0.02585
    gmin: float = 1e-12

    def __post_init__(self):
        nodes = tuple(int(node) for node in self.nodes)
        if len(nodes) != 2:
            raise ValueError(f"nodes must be a pair (a, b); got {self.nodes!r}")
        if min(nodes) < 0:
            raise ValueError(f"node indices are non-negative; got {nodes}")
        if nodes[0] == nodes[1]:
            raise ValueError(
                f"nodes must be distinct; got {nodes}, and a diode from a node "
                "to itself would stamp a conductance plus its own companion "
                "current that cancel exactly, i.e. nothing at all"
            )
        for field_name in ("isat", "n", "vt"):
            value = float(getattr(self, field_name))
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"{field_name} must be finite and positive; got "
                    f"{getattr(self, field_name)!r}"
                )
            object.__setattr__(self, field_name, value)
        gmin = float(self.gmin)
        if not np.isfinite(gmin) or gmin < 0.0:
            raise ValueError(
                f"gmin must be finite and non-negative; got {self.gmin!r}.  "
                "Zero is allowed only if nothing relies on the junction's "
                "reverse slope; it makes a reverse-biased diode an exact "
                "current source of -isat"
            )
        object.__setattr__(self, "gmin", gmin)
        object.__setattr__(self, "nodes", nodes)

    @property
    def kind(self):
        """``"D"``: the branch kind this device occupies in a network."""
        return "D"

    @property
    def vcrit(self):
        """The junction voltage above which ``pnjlim`` starts limiting (V).

        ``n vt log(n vt / (sqrt(2) isat))`` -- SPICE's critical voltage, the
        point where the exponential's slope has outgrown the loop's ability to
        chase it without help.  At the defaults it is ``0.7297`` V.
        """
        return self.n * self.vt * np.log(
            self.n * self.vt / (np.sqrt(2.0) * self.isat)
        )

    def current(self, v):
        """Conduction current (A) from ``nodes[0]`` to ``nodes[1]`` at ``v``.

        The exponential's argument is clamped at ``_EXP_CLAMP`` so a wild Newton
        iterate cannot overflow to ``inf`` and poison the linear solve with a
        NaN.  At the clamp the junction already carries ~1e29 A, so the clamp
        never binds on a *converged* step (that would need ~2.6 V across one
        junction at 300 K): it trades an unrepresentable current for a finite
        one far outside the model's domain, and that is the whole point.
        ``expm1`` is used because near ``v = 0`` -- where a blocking junction
        spends its time -- ``exp(x) - 1`` would lose every significant digit.
        """
        v = np.asarray(v, dtype=float)
        x = np.minimum(v / (self.n * self.vt), _EXP_CLAMP)
        return self.isat * np.expm1(x) + self.gmin * v

    def conductance(self, v):
        """``dI/dv`` (S) at ``v``: the slope the Newton loop stamps."""
        return self.isat * _clamped_exp(
            np.asarray(v, dtype=float) / (self.n * self.vt)
        ) / (self.n * self.vt) + self.gmin


def _clamped_exp(x):
    """``exp(x)`` with ``x`` clamped at ``_EXP_CLAMP``; see ``Diode.current``."""
    with np.errstate(over="ignore"):
        return np.exp(np.minimum(np.asarray(x, dtype=float), _EXP_CLAMP))


@dataclass(frozen=True)
class TransmissionLine:
    """A lossless distributed line, discretised by the method of characteristics.

    Parameters
    ----------
    nodes : (int, int)
        ``(a, b)``, the two terminals; ``nodes[0]`` is the end a positive
        ``i_branch`` enters.  Neither end is ground unless the circuit says so,
        the two nodes must be distinct, and a line adds **no** node of its own:
        the whole delay is carried in the history, not in a chain of interior
        nodes.
    z0 : float, optional
        Characteristic impedance (ohm), finite and positive, default ``50.0``.
    tau : float, optional
        One-way delay (s), finite and positive, default ``1e-9`` -- i.e.
        ``length * sqrt(LC)``.  Not ``length``: the solver never needs the
        geometry, only the delay.

    The line is **lossless**: no series resistance, no shunt conductance, and
    therefore no attenuation and no dispersion.  That is a model, not an
    approximation of one: a lossy line needs a distributed R and G, which the
    method of characteristics cannot carry as a pure delay, so it is a
    different element rather than a parameter of this one.

    Discretisation.  With ``i_k`` the current *entering* the line at end ``k``
    and ``Z = z0``, a lossless line is exactly the two terminal relations

    ``v_a(t) = Z i_a(t) + H1(t)``,   ``H1(t) = v_b(t - tau) + Z i_b(t - tau)``
    ``v_b(t) = Z i_b(t) + H2(t)``,   ``H2(t) = v_a(t - tau) + Z i_a(t - tau)``

    i.e. each end is a resistor ``Z`` to ground in parallel with a current
    source of ``H_k / Z`` into the node, and each ``H`` is the *other* end's
    terminal relation read ``tau`` ago.  So one step reads two numbers out of a
    history buffer and writes two back, and the delay is exactly ``tau`` rather
    than a lumped ladder's approximation to it.  The rejected alternative is
    the lumped ladder (n segments of L and C): its phase velocity is wrong by
    ``O((omega dt)^2)`` per segment, it needs n interior nodes and n capacitors'
    worth of state, and reaching a given accuracy costs a quadratically growing
    MNA matrix.  The method of characteristics is exact in ``tau`` for any
    number of steps, so a stub of one electrical degree is as cheap as one of
    ninety.

    Two consequences worth stating because they differ from every other kind
    here.  First, the two ends do **not** carry the same current: a distributed
    line stores charge, so ``i_a`` and ``i_b`` differ during a transient, and
    ``i_branch`` reports ``i_a`` only (the current into ``nodes[0]``).  Second,
    the line needs a sample of history per step of its delay, so it has state
    that is neither a node voltage nor an element current: it lives in
    :class:`SpiceState` as a buffer of ``v + Z i`` samples, one pair per end
    (see ``_LineSamples``).

    The buffer is indexed by *time*, so the step must be uniform: ``MNASolver``
    refuses a ``dt`` that changes mid-run and a ``tau`` shorter than one step.
    """

    nodes: tuple
    z0: float = 50.0
    tau: float = 1e-9

    def __post_init__(self):
        nodes = tuple(int(node) for node in self.nodes)
        if len(nodes) != 2:
            raise ValueError(f"nodes must be a pair (a, b); got {self.nodes!r}")
        if min(nodes) < 0:
            raise ValueError(f"node indices are non-negative; got {nodes}")
        if nodes[0] == nodes[1]:
            raise ValueError(
                f"nodes must be distinct; got {nodes}, and a line from a node "
                "to itself is shorted at both ends at once, so every wave it "
                "launched would return with nothing to do"
            )
        for field_name in ("z0", "tau"):
            value = float(getattr(self, field_name))
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"{field_name} must be finite and positive; got "
                    f"{getattr(self, field_name)!r}.  A zero {field_name} is "
                    "not an absent line: ``z0 = 0`` would be a pair of solid "
                    "shorts and ``tau = 0`` a through wire, so omit the "
                    "branch (and use a Branch) instead"
                )
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "nodes", nodes)

    @property
    def kind(self):
        """``"T"``: the branch kind this element occupies in a network."""
        return "T"


# What a ``CircuitNetwork`` may hold: a linear ``Branch``, a nonlinear
# ``Diode``, or a lossless ``TransmissionLine``.  All three answer ``.kind``
# and ``.nodes``, which is all the assembly and the recovery need to treat
# them as one ordered list of elements.
_ELEMENT_TYPES = (Branch, Diode, TransmissionLine)


@dataclass(frozen=True)
class CircuitNetwork:
    """A frozen, ordered branch list plus the node count it lives on.

    Parameters
    ----------
    branches : tuple of Branch and Diode
        Branch order is the order of the element-current vector and fixes the
        MNA row order, so a network is comparable and reproducible.  A
        :class:`Diode` sits in the same tuple and adds **no** MNA unknown: it
        is stamped as a conductance plus a companion current, so ``i_branch``
        keeps length ``n_branches`` and the diode's slot holds its conduction
        current.
    n_nodes : int
        Total node count **including** ground: indices ``0 .. n_nodes - 1`` are
        legal and ``0`` is ground.

    For the coupling, nodes ``1 .. n_t`` are the port terminals in the order
    :class:`emfit.terminations.TerminalPort` uses; nodes above that are
    internal to the network.  Parses no netlist syntax; no subcircuits.
    """

    branches: tuple
    n_nodes: int

    def __post_init__(self):
        branches = tuple(self.branches)
        n_nodes = int(self.n_nodes)
        if n_nodes < 2:
            raise ValueError(
                "n_nodes counts ground, so one non-ground node means "
                f"n_nodes = 2; got {self.n_nodes!r}"
            )
        for branch in branches:
            if not isinstance(branch, _ELEMENT_TYPES):
                raise TypeError(
                    "branches must be Branch, Diode or TransmissionLine "
                    "instances, not "
                    f"{type(branch).__name__}"
                )
            for node in branch.nodes:
                if node >= n_nodes:
                    raise ValueError(
                        f"branch {branch} names node {node}, but the network has "
                        f"n_nodes = {n_nodes}, i.e. nodes 0..{n_nodes - 1}"
                    )
        object.__setattr__(self, "branches", branches)
        object.__setattr__(self, "n_nodes", n_nodes)

    @property
    def n_branches(self):
        """Number of branches, i.e. length of an element-current vector."""
        return len(self.branches)

    def indices(self, kind):
        """Branch indices of one kind, in branch order."""
        return tuple(k for k, br in enumerate(self.branches) if br.kind == kind)


def _as_vector(x, n, name):
    """``x`` as a length-``n`` float vector; ``None`` means all zeros."""
    if x is None:
        return np.zeros(n)
    x = np.asarray(x, dtype=float).ravel()
    if x.shape != (n,):
        raise ValueError(f"{name} must have shape ({n},); got shape {x.shape}")
    return x


def U_f(w, m_eps, e):
    """Field (fluid) energy ``U_f = (1/2) sum_k w_k m_eps_k e_k^2``.

    Parameters
    ----------
    w : array_like, shape (n_edges,)
        ``diag(W_E)``: the diagonal of the edge metric this coupling uses.
    m_eps : array_like, shape (n_edges,)
        Edge capacitances (the ``m_eps`` diagonal of the Ampere law), in farads.
    e : array_like, shape (n_edges,)
        The field/edge state the energy is evaluated at.

    Returns
    -------
    float
        The scalar energy, in joules for SI inputs.

    Notes
    -----
    ``Q = diag(w * m_eps)`` is the quadratic form this closes, so it equals the
    familiar ``(1/2) m_eps . e^2`` only when ``W_E = I``.  Its companion identity
    ``dU_f = -(dt/4) * s . (v' + v)`` pairs a step's *change* with ``v = L.T @ e``
    from the PREVIOUS step; that pairing, not the formula, is why the solver
    carries it.  For a non-diagonal ``W_E`` no symmetric quadratic energy closes
    the balance and ``U_f`` is bookkeeping only.

    The arithmetic is the elementwise ``w * m_eps * e * e`` then ``sum``, in that
    order: it stays that way so no caller's bit-level result changes.
    """
    w = np.asarray(w, dtype=float)
    m_eps = np.asarray(m_eps, dtype=float)
    e = np.asarray(e, dtype=float)
    return 0.5 * float(np.sum(w * m_eps * e * e))


class SpiceState:
    """The previous solution of a :class:`CircuitNetwork`, plus port history.

    Parameters
    ----------
    network : CircuitNetwork
        The network this state belongs to.  A step checks that solver and state
        agree on it instead of silently mixing two netlists.
    u, i_branch : array_like, optional
        Node voltages (length ``n_nodes``, ``u[0]`` is ground and stays 0) and
        branch currents (length ``n_branches``, positive ``nodes[0] ->
        nodes[1]``) at ``t^n``.  Default zeros.
    i, v : array_like, optional
        Port-terminal current and voltage at ``t^n``, the two history vectors
        ``emfit.terminations.RLCState`` also carries.  Default empty: a
        standalone network has no port; :class:`SpicePort` fills them.
    tline : _LineSamples, optional
        Travelling-wave history of every :class:`TransmissionLine` in the
        network, one row per line, or ``None`` for a network without a line.
        ``None`` on a network *with* a line is not an error: the first step
        creates the buffer, all zeros, which is the line at rest -- a line has
        nothing in flight until a step has put it there, so there is no
        initial condition to invent.  The buffer length depends on
        ``tau / dt``, which is why it can only be built at the first step.

    Notes
    -----
    A **plain class**, not a frozen dataclass and not a named tuple, because
    ``RLCState`` is a plain class and the two states sit at the same call sites.
    Immutability is by convention, as it is there: a step never writes to a
    state, it returns a new one, so the previous state stays inspectable and
    reusable.

    ``v_c`` and ``i_l`` are **derived** views, not stored state: keeping a second
    copy of the same number is how the two drift apart.
    """

    def __init__(self, network, *, u=None, i_branch=None, i=None, v=None,
                 tline=None):
        if not isinstance(network, CircuitNetwork):
            raise TypeError(
                f"network must be a CircuitNetwork, not {type(network).__name__}"
            )
        if tline is not None and not isinstance(tline, _LineSamples):
            raise TypeError(
                f"tline must be _LineSamples, not {type(tline).__name__}"
            )
        self.network = network
        self.u = _as_vector(u, network.n_nodes, "u")
        self.i_branch = _as_vector(i_branch, network.n_branches, "i_branch")
        self.tline = tline
        self.i = np.zeros(0) if i is None else np.asarray(i, dtype=float).ravel()
        self.v = np.zeros(0) if v is None else np.asarray(v, dtype=float).ravel()

    @property
    def n_port(self):
        """Number of port-terminal history entries this state carries."""
        return int(self.i.shape[0])

    @property
    def v_c(self):
        """Capacitor voltages at ``t^n``, in capacitor branch order."""
        return np.array([self.u[br.nodes[0]] - self.u[br.nodes[1]]
                         for br in self.network.branches if br.kind == "C"])

    @property
    def i_l(self):
        """Inductor currents at ``t^n``, in inductor branch order."""
        return np.array([self.i_branch[k] for k in self.network.indices("L")])


def _conductance(kind, value, dt, scheme):
    """Companion conductance of one ``R``/``L``/``C`` branch."""
    if kind == "R":
        return 1.0 / value
    if kind == "C":
        return 2.0 * value / dt if scheme == "trapezoidal" else value / dt
    return dt / (2.0 * value) if scheme == "trapezoidal" else dt / value


def _history(kind, g, v_prev, i_prev, scheme):
    """Companion history current of one branch, positive ``a -> b``."""
    if kind == "R":
        return 0.0
    if scheme == "trapezoidal":
        return -(i_prev + g * v_prev) if kind == "C" else (i_prev + g * v_prev)
    return -g * v_prev if kind == "C" else i_prev


def _source_values(network, sources):
    """Per-branch source levels for one step; ``None`` means ``Branch.value``.

    A ``V`` or ``I`` branch's level is normally its frozen ``value``.  A driver
    that owns a waveform evaluates it at the new time and passes the resulting
    length-``n_branches`` vector here, so the level can move between steps
    without making a branch mutable: ``Branch`` stays frozen and a step still
    depends only on ``(dt, state, sources)``.  Entries for ``R``/``L``/``C`` and
    ``D``/``T`` branches are carried for indexing convenience and never read --
    a diode and a line have no ``value`` at all, so their slot is a literal
    ``0.0`` rather than a number that means anything.
    """
    if sources is None:
        # ``D`` (a model) and ``T`` (a delay and an impedance) have no
        # ``value`` attribute at all, so their slot is a literal 0.0 rather
        # than a number that would mean something.
        return np.array(
            [0.0 if br.kind in ("D", "T") else br.value
             for br in network.branches],
            dtype=float,
        )
    src = np.asarray(sources, dtype=float).ravel()
    if src.shape != (network.n_branches,):
        raise ValueError(
            f"sources must have shape ({network.n_branches},), one level per "
            f"branch; got shape {src.shape}"
        )
    if not np.all(np.isfinite(src)):
        raise ValueError(f"sources must be finite; got {src.tolist()}")
    return src


class _LineSamples:
    """The travelling-wave samples every line still has in flight.

    ``values`` has shape ``(n_lines, capacity, 2)``: one row per line, one
    column per sample, and the last axis is ``(S1, S2)`` with

    ``S1 = v_a + z0 * i_a``   (the wave launched at ``nodes[0]``)
    ``S2 = v_b + z0 * i_b``   (the wave launched at ``nodes[1]``),

    ``i_k`` being the current *entering* the line at end ``k``.  Those are the
    two quantities the next step needs read back: ``H1`` is ``S2`` delayed by
    ``tau`` and ``H2`` is ``S1`` delayed by ``tau``, which is the whole
    physics of a lossless line -- a wave leaving one end arrives at the other
    unchanged, and nothing else happens.

    **Oldest sample first, newest last**, so walking backwards from ``-1``
    walks into the past and the delay lookup is plain negative indexing.  A
    ring buffer with a write pointer would avoid the shift in
    :func:`_line_advance`, but the shift is one ``memcpy`` of
    ``n_lines * capacity`` doubles (a few thousand at most) and buying O(1)
    with an index arithmetic that every reader has to re-derive is the wrong
    trade in a file whose whole job is to be checkable by hand.

    Rows before ``t = 0`` are zero, and they are *really there* rather than
    special-cased: a line at rest carries no travelling wave, so padding the
    buffer with zeros is exactly the initial condition, and the first ``tau``
    of a run then needs no branch in the lookup path.
    """

    __slots__ = ("values", "dt")

    def __init__(self, values, dt):
        values = np.asarray(values, dtype=float)
        if values.ndim != 3 or values.shape[2] != 2:
            raise ValueError(
                "a line buffer must have shape (n_lines, capacity, 2); got "
                f"{values.shape}"
            )
        if not np.all(np.isfinite(values)):
            raise ValueError("line history must be finite")
        self.values = values
        self.dt = float(dt)


def _line_slots(network):
    """Branch indices of the transmission lines, in branch order."""
    return tuple(k for k, br in enumerate(network.branches) if br.kind == "T")


def _line_capacity(network, dt):
    """Rows of history the longest delay in the network needs.

    The step at ``t^{n+1}`` reads the sample at ``t^{n+1} - tau``, which is
    ``tau/dt - 1`` samples back from the newest one (``t^n``).  That offset is
    not generally an integer, so the lookup needs the two samples that bracket
    it: ``floor(tau/dt - 1) + 2`` rows.  A ``tau`` shorter than one step has no
    bracket at all -- the answer would be in the future -- and is refused here
    rather than silently clamped to one step, because a line whose delay the
    grid cannot resolve is a line whose delay is not being modelled.
    """
    capacity = 1
    for k in _line_slots(network):
        br = network.branches[k]
        ratio = br.tau / dt
        if ratio < 1.0:
            raise ValueError(
                f"branch {k} is a transmission line with tau = {br.tau!r} s, "
                f"shorter than one step of dt = {dt!r} s: the method of "
                "characteristics reads the wave it launched tau ago, and a "
                "sample that old does not exist until one full step has "
                "passed.  Refused rather than rounded up to one step, which "
                "would model a different, slower line -- shrink dt or "
                "shorten tau"
            )
        capacity = max(capacity, int(np.floor(ratio - 1.0)) + 2)
    return capacity


def _line_buffers(network, dt, tline):
    """The history buffer to read this step from; ``None`` without a line.

    An existing buffer is reused as-is and a missing one is created all-zero
    (the line at rest).  A ``dt`` that differs from the one the buffer was
    built with is refused: every row is one step of history, so a change of
    step silently changes what the stored samples *mean*, and the delay would
    come out as the wrong multiple of a wrong step.  Re-gridding an in-flight
    history is a real algorithm and not this one.
    """
    if not _line_slots(network):
        if tline is not None:
            raise ValueError(
                "state carries line history but this network has no "
                "transmission line; the buffer would be advanced by nothing "
                "and would disagree with the netlist in silence"
            )
        return None
    capacity = _line_capacity(network, dt)
    if tline is None:
        return _LineSamples(
            np.zeros((len(_line_slots(network)), capacity, 2)), dt
        )
    if tline.dt != dt:
        raise ValueError(
            f"the line history was built with dt = {tline.dt!r} s but this "
            f"step is dt = {dt!r} s; every stored sample is one step of "
            "history and every delay is a count of steps, so a changed step "
            "would reinterpret the whole buffer as a different time axis.  "
            "Use one dt for a run, or start a fresh state"
        )
    if tline.values.shape != (len(_line_slots(network)), capacity, 2):
        raise ValueError(
            "the line history has shape "
            f"{tline.values.shape} but this network and step need "
            f"{(len(_line_slots(network)), capacity, 2)}"
        )
    return tline


def _line_history(network, lines, dt):
    """Per-line ``(H1, H2)`` for the step being solved.

    ``H1 = v_b + z0 i_b`` and ``H2 = v_a + z0 i_a``, both evaluated ``tau``
    ago -- see :class:`TransmissionLine`.  When ``tau/dt`` is not an integer the
    sample is taken by **linear interpolation** between the two that bracket
    it.  The rejected alternatives were to refuse a non-integer ``tau/dt``
    (which makes any real geometry unusable: ``tau`` comes from a length and a
    phase velocity, and nothing makes that a multiple of the step) and to round
    to the nearest step (which is cheap but silently shifts the phase velocity
    by up to half a step per pass -- an error that compounds every round trip
    and is invisible in a single-ended test).  Interpolation errs by
    ``O((dS/dt * dt)^2)`` inside one sample and, unlike rounding, is
    unbiased: a delay that *is* a whole number of steps still lands on the
    exact sample, so the exact case stays exact.
    """
    history = {}
    for row, k in enumerate(_line_slots(network)):
        br = network.branches[k]
        back = br.tau / dt - 1.0
        whole = int(np.floor(back))
        weight = back - whole
        samples = lines.values[row]
        s1, s2 = samples[:, 0], samples[:, 1]
        # row -1 is t^n, so offset ``whole`` back is row -(whole+1) and the
        # sample one step older than that is row -(whole+2), which exists
        # because capacity = floor(tau/dt - 1) + 2.
        newer, older = -(whole + 1), -(whole + 2)
        h2 = (1.0 - weight) * s1[newer] + weight * s1[older]
        h1 = (1.0 - weight) * s2[newer] + weight * s2[older]
        history[k] = (float(h1), float(h2))
    return history


def _line_advance(network, lines, dt, u, history):
    """The next buffer: one row shifted, one row appended at ``t^{n+1}``.

    ``S1 = 2 v_a - H1`` and ``S2 = 2 v_b - H2``, which is ``v + z0 i`` with
    ``z0 i_a = v_a - H1`` substituted.  Written that way the *same two
    numbers* the step read out are what it writes back, so the buffer is a
    delay line and nothing else: no gain, no loss, which is exactly why the
    discrete scheme conserves energy to the last bit (see the tests).
    """
    values = np.empty_like(lines.values)
    values[:, :-1, :] = lines.values[:, 1:, :]
    for row, k in enumerate(_line_slots(network)):
        a, b = network.branches[k].nodes
        h1, h2 = history[k]
        values[row, -1, 0] = 2.0 * u[a] - h1
        values[row, -1, 1] = 2.0 * u[b] - h2
    return _LineSamples(values, dt)


def _assemble(network, dt, u_prev, i_prev, scheme, coupling=None, sources=None,
              diode_bias=None, line_history=None):
    """Assemble ``A x = b`` for one step; returns ``(A, b, info)``.

    ``coupling`` is ``None`` for the standalone network, or
    ``(M, v_star, i_prev_port)`` to append the field's ``n_t`` branch rows and
    the ``n_t`` port-current unknowns: ``M`` into the ``(i, i)`` block and
    ``-M i^n`` into the source row, the field's own discretisation stamped as
    the circuit sees it.

    ``sources`` is ``None`` (use each branch's frozen ``value``) or a
    length-``n_branches`` vector of source levels for this step; see
    :func:`_source_values`.  It only moves ``V`` and ``I`` branches.

    ``diode_bias`` maps a diode's branch index to the junction voltage the
    Newton loop has linearised it at, ``v^k``; ``None`` means the network has no
    diode (and then nothing below changes).  It is **required** as soon as one
    exists: a diode has no linear companion, so an assembly that reached this
    point without a bias would silently stamp a different circuit.  The stamp
    is the diode's conductance at ``v^k`` -- exactly the shape of the ``R``
    stamp -- plus the companion current ``I(v^k) - g(v^k) v^k`` injected from
    ``nodes[0]`` to ``nodes[1]`` with the same sign an ``I`` branch uses.

    ``line_history`` maps a transmission line's branch index to the pair
    ``(H1, H2)`` that :func:`_line_history` read out of the buffer, and is
    required on exactly the same terms: a line has no linear companion either,
    so an assembly that reached one without its history would stamp a line at
    rest and quietly solve a different circuit.  The stamp is a conductance
    ``1/z0`` from **each end to ground** -- not end to end, which would force
    both ends to the same voltage and make the line a wire -- plus a current
    ``H_k/z0`` injected into end ``k``, which is the whole of the method of
    characteristics seen from the circuit's side.
    """
    n_rows = network.n_nodes - 1
    v_cols = {}
    for k, br in enumerate(network.branches):
        if br.kind == "V":
            v_cols[k] = n_rows + len(v_cols)
    n_port = 0 if coupling is None else int(np.shape(coupling[0])[0])
    size = n_rows + len(v_cols) + n_port
    src = _source_values(network, sources)

    A = np.zeros((size, size))
    b = np.zeros(size)

    def row(node):
        return None if node == _GROUND else node - 1

    def inject(node, value):
        r = row(node)
        if r is not None:
            b[r] += value

    def add_conductance(ra, rc, g):
        """Stamp ``g`` across its two rows, ground having no row to write."""
        if ra is not None:
            A[ra, ra] += g
            if rc is not None:
                A[ra, rc] -= g
        if rc is not None:
            A[rc, rc] += g
            if ra is not None:
                A[rc, ra] -= g

    for k, br in enumerate(network.branches):
        a, c = br.nodes
        ra, rc = row(a), row(c)
        if br.kind in ("R", "L", "C"):
            g = _conductance(br.kind, br.value, dt, scheme)
            hist = _history(br.kind, g, u_prev[a] - u_prev[c], i_prev[k], scheme)
            add_conductance(ra, rc, g)
            if hist != 0.0:
                inject(c, hist)
                inject(a, -hist)
        elif br.kind == "D":
            if diode_bias is None or k not in diode_bias:
                raise ValueError(
                    f"branch {k} is a diode: a diode has no linear companion, "
                    "its conductance and its companion current both depend on "
                    "the junction voltage the Newton loop has linearised at, "
                    "so _assemble needs diode_bias[k] -- stamping the bare "
                    "model instead would solve a different circuit"
                )
            v_k = float(diode_bias[k])
            g = br.conductance(v_k)
            i_eq = br.current(v_k) - g * v_k
            add_conductance(ra, rc, g)
            # The companion current flows *inside* the branch, from nodes[0] to
            # nodes[1], so it enters exactly as an ``I`` branch does: -i_eq at
            # the first node, +i_eq at the second.
            inject(c, i_eq)
            inject(a, -i_eq)
        elif br.kind == "T":
            if line_history is None or k not in line_history:
                raise ValueError(
                    f"branch {k} is a transmission line: the waves it launched "
                    "tau ago are the only thing that ties the two ends "
                    "together, so _assemble needs line_history[k] -- without "
                    "it the line would be stamped at rest, i.e. a different "
                    "circuit"
                )
            h1, h2 = line_history[k]
            g = 1.0 / br.z0
            add_conductance(ra, None, g)
            add_conductance(rc, None, g)
            inject(a, h1 * g)
            inject(c, h2 * g)
        elif br.kind == "I":
            inject(c, src[k])
            inject(a, -src[k])
        else:  # "V": u_a - u_b = value, with its own branch current unknown
            col = v_cols[k]
            if ra is not None:
                A[col, ra] += 1.0
                A[ra, col] += 1.0
            if rc is not None:
                A[col, rc] -= 1.0
                A[rc, col] -= 1.0
            b[col] = src[k]

    base_port = n_rows + len(v_cols)
    if coupling is not None:
        M, v_star, i_prev_port = coupling
        M = np.asarray(M, dtype=float)
        drive = M @ np.asarray(i_prev_port, dtype=float)
        for m in range(n_port):
            r = row(m + 1)
            if r is not None:
                A[r, base_port + m] -= 1.0
                A[base_port + m, r] = 1.0
            A[base_port + m, base_port:base_port + n_port] = M[m, :]
            b[base_port + m] = float(v_star[m]) - drive[m]

    info = {
        "n_rows": n_rows,
        "v_cols": v_cols,
        "base_port": base_port,
        "n_port": n_port,
        "u_prev": u_prev,
        "i_prev": i_prev,
        "dt": dt,
        "scheme": scheme,
        "sources": src,
        "line_history": line_history,
    }
    return A, b, info


def _recover(network, x, info):
    """Node voltages and element currents from a solved ``x``."""
    u = np.zeros(network.n_nodes)
    u[1:] = x[:info["n_rows"]]
    dt, scheme = info["dt"], info["scheme"]
    currents = np.zeros(network.n_branches)
    for k, br in enumerate(network.branches):
        a, c = br.nodes
        if br.kind in ("R", "L", "C"):
            g = _conductance(br.kind, br.value, dt, scheme)
            hist = _history(br.kind, g, info["u_prev"][a] - info["u_prev"][c],
                            info["i_prev"][k], scheme)
            currents[k] = g * (u[a] - u[c]) + hist
        elif br.kind == "V":
            currents[k] = x[info["v_cols"][k]]
        elif br.kind == "T":
            # The current *into* the line at nodes[0], from v_a = z0 i_a + H1.
            # Deliberately not the current at the other end: a distributed line
            # stores charge, so the two differ during a transient, and one
            # number per branch cannot say both.  ``nodes[0]`` is the one every
            # other kind here reports at, so the branch-current vector keeps
            # one meaning.
            h1, _ = info["line_history"][k]
            currents[k] = (u[a] - h1) / br.z0
        elif br.kind == "D":
            # A diode carries its conduction current at the *solved* junction
            # voltage.  There is no diode current in ``x`` to read -- the diode
            # occupies no row -- only the node voltages that set it.
            currents[k] = br.current(u[a] - u[c])
        else:
            currents[k] = info["sources"][k]
    return u, currents


def _pnjlim(v_old, v_new, diode):
    """Limit one Newton update the way SPICE's ``pnjlim`` does.

    Without this the loop diverges on the very first forward step instead of
    converging.  The reason is the exponential's shape, not its size: a solve
    linearised at ``v = 0`` stamps the *flat* part of the junction, so it puts
    the whole source voltage across the diode (5 V where the answer is 0.7 V),
    and the next linearisation at 5 V stamps the near-vertical part, which
    throws the iterate far the other way.  ``pnjlim`` caps each update at the
    point where the exponential's own curvature stops tolerating it: above
    ``vcrit`` the step is compressed to ``n vt log(...)``, which turns the
    geometric blow-up into a walk of ``n vt``-sized steps that Newton then
    finishes quadratically once it is below ``vcrit``.  This is SPICE's own
    limiter, formula for formula (``v_old > 0`` and ``v_old <= 0`` are handled
    separately because the log's argument differs).

    Limiting cannot move the *answer*: it only ever moves an iterate, and the
    loop converges on the unlimited solves once the iterates are close.
    """
    step = v_new - v_old
    threshold = 2.0 * diode.n * diode.vt
    if v_new > diode.vcrit and abs(step) > threshold:
        if v_old > 0.0:
            return v_old + diode.n * diode.vt * np.log1p(step / (diode.n * diode.vt))
        return diode.n * diode.vt * np.log(v_new / (diode.n * diode.vt))
    return v_new


def _diode_slots(network):
    """Branch indices of the diodes, in branch order."""
    return tuple(k for k, br in enumerate(network.branches) if br.kind == "D")


def _solve_step(network, dt, u_prev, i_prev, scheme, *, coupling=None,
                sources=None, max_iter=_MAX_ITER, line_history=None):
    """Solve one step's ``A x = b``, Newton-iterating if there are diodes.

    Returns ``(x, info, iterations)``; ``iterations`` is ``0`` exactly when the
    network has no diode and the loop below never ran.  Both
    :meth:`MNASolver.step` and :meth:`SpicePort.step` come through here, so the
    loop body, its tolerances and its failure mode exist once.

    The iteration is the textbook one, and the reason it is safe here is that a
    *step* is not an operating point: the diodes start from the previous
    state's junction voltages, which for a waveform-driven netlist are within a
    few ``n vt`` of this step's, and the limiter covers the rest.  Per
    iteration: linearise each junction at ``v^k`` (conductance plus companion
    current, see :func:`_assemble`), solve, and read each junction's new voltage
    off the solved node voltages.  Convergence is judged on the **junction
    voltages only** -- not on ``x``, whose port and source rows carry amperes
    and volts at once and would make one scalar tolerance meaningless.

    The last solve's ``x`` is what is returned, i.e. the solution at the
    converged iterate rather than at the converged iterate plus its last,
    below-tolerance correction.  That difference is bounded by ``reltol`` and
    entering the residual one more time through the conductance would not
    remove it; the alternative (an extra assembly and solve for no visible
    digits) is not worth an iteration.
    """
    slots = _diode_slots(network)
    if not slots:
        # No diode: one assembly, one solve, no iteration.  The linear path is
        # this branch, untouched by the loop below.
        A, b, info = _assemble(
            network, dt, u_prev, i_prev, scheme, coupling=coupling,
            sources=sources, line_history=line_history,
        )
        return np.linalg.solve(A, b), info, 0

    max_iter = int(max_iter)
    if max_iter < 1:
        raise ValueError(f"max_iter must be at least 1; got {max_iter}")
    diodes = tuple(network.branches[k] for k in slots)
    n_rows = network.n_nodes - 1
    # The initial guess is the previous state's junction voltages, never zero:
    # a zero start lands in the flat part of the exponential and would need the
    # limiter to walk all the way up on every step (see _pnjlim).
    bias = np.array(
        [u_prev[br.nodes[0]] - u_prev[br.nodes[1]] for br in diodes], dtype=float
    )
    step = tolerance = float("inf")
    iteration = 0
    for iteration in range(1, max_iter + 1):
        A, b, info = _assemble(
            network, dt, u_prev, i_prev, scheme, coupling=coupling,
            sources=sources,
            diode_bias={k: bias[j] for j, k in enumerate(slots)},
            line_history=line_history,
        )
        x = np.linalg.solve(A, b)
        u = np.zeros(network.n_nodes)
        u[1:] = x[:n_rows]
        raw = np.array([u[br.nodes[0]] - u[br.nodes[1]] for br in diodes])
        bias_new = np.array(
            [_pnjlim(bias[j], raw[j], diodes[j]) for j in range(len(diodes))]
        )
        tolerance = _RELTOL * float(np.max(np.abs(bias_new))) + _VNTOL
        step = float(np.max(np.abs(bias_new - bias)))
        if step <= tolerance:
            return x, info, iteration
        bias = bias_new
    raise DiodeConvergenceError(
        "the Newton loop inside this step did not converge: after "
        f"{iteration} iteration(s) the largest junction-voltage update was "
        f"still {step:.3e} V against a tolerance of {tolerance:.3e} V, so this "
        "step is refused rather than returned as if it were solved.  A forward "
        "junction that will not settle means the step is too large, the model "
        "parameters are self-contradictory (isat/n/vt), or max_iter is below "
        "what the step needs -- shrink dt or raise max_iter, do not ignore it",
        iterations=iteration, step=step, tolerance=tolerance,
    )


class MNASolver:
    """A generic linear netlist solved by MNA, with backward-Euler companions.

    Parameters
    ----------
    network : CircuitNetwork
        The netlist.
    scheme : {"backward_euler", "trapezoidal"}, keyword-only, optional
        Companion integrator.  The default ``"backward_euler"`` is **first order
        in ``dt``**: it is the scheme this solver is specified with, and its
        accuracy against a closed form is measured by the accompanying proof
        script rather than claimed here.  ``"trapezoidal"`` exists because
        :class:`SpicePort` needs the same assembly with ``step_rlc``'s
        companions; it is not the default and is not claimed to be
        unconditionally better, only exact-in-the-quadratic.

    Ground (node ``0``) is eliminated, not merely pinned: its row and column are
    never built, so a network with a node that has no path to ground is
    singular and raises from ``np.linalg.solve`` instead of being regularised
    silently.  When such a network is coupled, :class:`SpicePort` supplies the
    reference through the field's own ``M``.
    """

    def __init__(self, network, *, scheme="backward_euler"):
        if not isinstance(network, CircuitNetwork):
            raise TypeError(
                f"network must be a CircuitNetwork, not {type(network).__name__}"
            )
        if scheme not in _SCHEMES:
            raise ValueError(f"scheme must be one of {_SCHEMES}; got {scheme!r}")
        self.network = network
        self.scheme = scheme

    def initial_state(self):
        """All-zero history: no charge, no current, no node voltage."""
        return SpiceState(self.network)

    def step(self, dt, state, *, sources=None, max_iter=_MAX_ITER):
        """One step.  Returns ``(state_new, u, i_branch)``.

        Parameters
        ----------
        dt : float
            Time step (s), finite and positive.
        state : SpiceState
            History at ``t^n``, on this network.
        sources : array_like, shape (n_branches,), keyword-only, optional
            Source levels evaluated at ``t^{n+1}``, the implicit-Euler point
            this step solves at.  ``None`` uses each branch's frozen
            ``value``, i.e. a source whose level never moves.
        max_iter : int, keyword-only, optional
            Newton iteration cap, used only when the network contains a
            diode; a linear network is solved in one shot and never iterates.
            Exceeding the cap raises :class:`DiodeConvergenceError`, never a
            silent under-converged answer.

        Returns
        -------
        (SpiceState, ndarray, ndarray)
            Advanced history, node voltages at ``t^{n+1}`` (length ``n_nodes``,
            ``[0]`` ground and 0) and branch currents at ``t^{n+1}`` (length
            ``n_branches``, positive ``nodes[0] -> nodes[1]``).  ``state`` is
            never written to.
        """
        dt = float(dt)
        if not np.isfinite(dt) or dt <= 0.0:
            raise ValueError(f"dt must be finite and positive; got {dt!r}")
        if not isinstance(state, SpiceState):
            raise TypeError(f"state must be a SpiceState, not {type(state).__name__}")
        if state.network is not self.network:
            raise ValueError(
                "state was built for a different CircuitNetwork; a solver and "
                "its state must agree on the netlist, or branch order and node "
                "count silently disagree"
            )
        lines = _line_buffers(self.network, dt, state.tline)
        history = None if lines is None else _line_history(
            self.network, lines, dt
        )
        x, info, _ = _solve_step(
            self.network, dt, state.u, state.i_branch, self.scheme,
            sources=sources, max_iter=max_iter, line_history=history,
        )
        u, currents = _recover(self.network, x, info)
        tline = (
            None if lines is None
            else _line_advance(self.network, lines, dt, u, history)
        )
        return (
            SpiceState(
                self.network, u=u, i_branch=currents, i=state.i, v=state.v,
                tline=tline,
            ),
            u,
            currents,
        )


class SpicePort:
    """Couples a :class:`CircuitNetwork` to the field through a ``TerminalPort``.

    Parameters
    ----------
    port : TerminalPort
        The edge bundle the network hangs on.  Both of its functionals are used
        and nothing else, exactly as ``step_rlc`` uses them: ``voltage`` for
        ``v = L.T @ e`` and ``current_density`` for the metric solve
        ``W_E^{-1} L i``.
    m_eps : array_like, shape (n_edges,)
        Edge capacitances (the ``m_eps`` diagonal of the Ampere law, farads).
        Finite and positive on every edge.
    network : CircuitNetwork, keyword-only
        Nodes ``1 .. n_t`` must be the port terminals, in the port's own order.
    advance : callable, keyword-only, optional
        The load-free field update ``(e, h, dt) -> (e*, h*)``, the same hook
        ``RLCState`` takes.  ``None`` means no field motion this step.

    ``M = (dt/2) L.T m_eps^{-1} W_E^{-1} L`` is built the way ``step_rlc``
    builds it -- one ``current_density`` and one ``voltage`` call per terminal,
    no private matrix touched -- so ``W_E`` is reused and never inverted.  ``M``
    depends on ``dt``, so it is rebuilt each step; like ``step_rlc`` this is
    written for small ``n_t`` and claims nothing about larger ones.

    ``tests/test_spice.py:383 test_spice_port_reproduces_step_rlc_on_a_series_rlc``
    is the acceptance test for this coupling: a series R-L-C stepped here and
    through ``step_rlc`` from the same field must agree to ``1e-14`` on every
    record.  That is an identity check on the trapezoidal companion -- one
    algebraic step reproduced by a second implementation -- not a field
    co-simulation.
    """

    def __init__(self, port, m_eps, *, network, advance=None):
        if not isinstance(port, TerminalPort):
            raise TypeError(
                f"port must be a TerminalPort, not {type(port).__name__}: the "
                "coupling is expressed entirely in the port's voltage and "
                "current_density functionals"
            )
        if not isinstance(network, CircuitNetwork):
            raise TypeError(
                f"network must be a CircuitNetwork, not {type(network).__name__}"
            )
        m_eps = np.asarray(m_eps, dtype=float).ravel()
        if m_eps.shape != (port.n_edges,):
            raise ValueError(
                f"m_eps must have shape ({port.n_edges},) for {port.n_edges} "
                f"edges; got shape {m_eps.shape}"
            )
        if not np.all(np.isfinite(m_eps)) or np.any(m_eps <= 0.0):
            raise ValueError(
                "m_eps must be finite and positive on every edge; got "
                f"{m_eps.tolist()} -- a non-positive edge capacitance has no "
                "inverse, so the field could not react to the load"
            )
        if network.n_nodes < port.n_terminals + 1:
            raise ValueError(
                f"network has n_nodes = {network.n_nodes}, i.e. nodes 0.."
                f"{network.n_nodes - 1}, but the port has {port.n_terminals} "
                f"terminals, which must be nodes 1..{port.n_terminals}"
            )
        self.port = port
        self.m_eps = m_eps
        self.network = network
        self.advance = advance

    def initial_state(self, *, v=None):
        """All-zero history at the terminals, then optional initial voltages.

        ``v`` sets the port terminals' node voltages, so the network starts from
        that same ``v`` instead of from a contradiction.  No operating point is
        solved and nothing is pre-charged beyond what is passed here.
        """
        n_t = self.port.n_terminals
        v = _as_vector(v, n_t, "v")
        u = np.zeros(self.network.n_nodes)
        u[1:n_t + 1] = v
        return SpiceState(self.network, u=u, i=np.zeros(n_t), v=v)

    def _field_reactance(self, dt):
        """``M = (dt/2) L.T m_eps^{-1} W_E^{-1} L``, column by column."""
        n_t = self.port.n_terminals
        block = np.empty((n_t, n_t))
        for m in range(n_t):
            unit = np.zeros(n_t)
            unit[m] = 1.0
            block[:, m] = self.port.voltage(
                self.port.current_density(unit) / self.m_eps
            )
        return 0.5 * dt * block

    def step(self, e, h, dt, state, *, sources=None, max_iter=_MAX_ITER):
        """One coupled trapezoidal step.  Returns ``(e_new, h_new, state_new)``.

        Same signature and same return shape as
        ``emfit.terminations.step_rlc``: ``e`` and ``state`` are unmodified, and
        ``h_new`` is ``h`` itself when ``advance`` is ``None``.

        ``sources`` is the per-step source-level vector ``MNASolver.step``
        takes, evaluated at ``t^{n+1}``; ``None`` keeps every source at its
        frozen ``value``.  ``max_iter`` is that method's Newton cap for a
        network with diodes; the field coupling is external to the Newton loop
        (``v_star`` is fixed before it starts), exactly as the linear case
        already was.
        """
        dt = float(dt)
        if not np.isfinite(dt) or dt <= 0.0:
            raise ValueError(f"dt must be finite and positive; got {dt!r}")
        if not isinstance(state, SpiceState):
            raise TypeError(f"state must be a SpiceState, not {type(state).__name__}")
        if state.network is not self.network:
            raise ValueError(
                "state was built for a different CircuitNetwork; a SpicePort "
                "and its state must agree on the netlist"
            )
        e_prev = np.asarray(e, dtype=float).ravel()
        if e_prev.shape != (self.port.n_edges,):
            raise ValueError(
                f"e must have shape ({self.port.n_edges},) for "
                f"{self.port.n_edges} edges; got shape {e_prev.shape}"
            )

        if self.advance is None:
            e_star, h_new = e_prev.copy(), h
        else:
            e_star, h_new = self.advance(e_prev, h, dt)
            e_star = np.asarray(e_star, dtype=float)
        v_star = self.port.voltage(e_star)

        M = self._field_reactance(dt)
        lines = _line_buffers(self.network, dt, state.tline)
        history = None if lines is None else _line_history(
            self.network, lines, dt
        )
        x, info, _ = _solve_step(
            self.network, dt, state.u, state.i_branch, "trapezoidal",
            coupling=(M, v_star, state.i), sources=sources, max_iter=max_iter,
            line_history=history,
        )
        u, currents = _recover(self.network, x, info)
        tline = (
            None if lines is None
            else _line_advance(self.network, lines, dt, u, history)
        )

        n_t = self.port.n_terminals
        i_new = x[info["base_port"]:info["base_port"] + n_t]
        e_new = e_star - 0.5 * dt * (
            self.port.current_density(i_new + state.i) / self.m_eps
        )
        return e_new, h_new, SpiceState(
            self.network, u=u, i_branch=currents, i=i_new,
            v=self.port.voltage(e_new), tline=tline,
        )
