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

Absent on purpose: no netlist-file reader, no subcircuits, no ``.model``, no
nonlinear device (that needs a Newton loop; this coupling is explicit by
construction), no transmission line, no adaptive step, no operating-point
solve, no ``s_parameters`` (the ``(I - z0 Y)(I + z0 Y)^{-1}`` check against
``(R - z0)/(R + z0)`` was never carried out -- no closed-form verification
was ever obtained -- so the method was dropped rather than shipped unverified),
and no time-dependent sources -- ``V`` and ``I`` branches carry fixed values.

Sign conventions
----------------
Terminal current ``i`` is positive *into* the network at its terminal node and
terminal voltage is ``L.T @ e``; a positive ``TerminalPort.port_power`` means
power is delivered from the field into the circuit's positive terminal, the
convention ``emfit/terminations.py`` pins and the only one used here.  A branch
current is positive from ``branch.nodes[0]`` to ``branch.nodes[1]``, and an
``I`` branch drives ``value`` amperes through itself from ``nodes[0]`` to
``nodes[1]`` (so it injects into ``nodes[1]``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .terminations import TerminalPort

__all__ = ["Branch", "CircuitNetwork", "SpiceState", "MNASolver", "SpicePort"]

_GROUND = 0
_KINDS = ("R", "L", "C", "V", "I")
_SCHEMES = ("backward_euler", "trapezoidal")


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


@dataclass(frozen=True)
class CircuitNetwork:
    """A frozen, ordered branch list plus the node count it lives on.

    Parameters
    ----------
    branches : tuple of Branch
        Branch order is the order of the element-current vector and fixes the
        MNA row order, so a network is comparable and reproducible.
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
            if not isinstance(branch, Branch):
                raise TypeError(
                    f"branches must be Branch instances, not {type(branch).__name__}"
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

    def __init__(self, network, *, u=None, i_branch=None, i=None, v=None):
        if not isinstance(network, CircuitNetwork):
            raise TypeError(
                f"network must be a CircuitNetwork, not {type(network).__name__}"
            )
        self.network = network
        self.u = _as_vector(u, network.n_nodes, "u")
        self.i_branch = _as_vector(i_branch, network.n_branches, "i_branch")
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


def _assemble(network, dt, u_prev, i_prev, scheme, coupling=None):
    """Assemble ``A x = b`` for one step; returns ``(A, b, info)``.

    ``coupling`` is ``None`` for the standalone network, or
    ``(M, v_star, i_prev_port)`` to append the field's ``n_t`` branch rows and
    the ``n_t`` port-current unknowns: ``M`` into the ``(i, i)`` block and
    ``-M i^n`` into the source row, the field's own discretisation stamped as
    the circuit sees it.
    """
    n_rows = network.n_nodes - 1
    v_cols = {}
    for k, br in enumerate(network.branches):
        if br.kind == "V":
            v_cols[k] = n_rows + len(v_cols)
    n_port = 0 if coupling is None else int(np.shape(coupling[0])[0])
    size = n_rows + len(v_cols) + n_port

    A = np.zeros((size, size))
    b = np.zeros(size)

    def row(node):
        return None if node == _GROUND else node - 1

    def inject(node, value):
        r = row(node)
        if r is not None:
            b[r] += value

    for k, br in enumerate(network.branches):
        a, c = br.nodes
        ra, rc = row(a), row(c)
        if br.kind in ("R", "L", "C"):
            g = _conductance(br.kind, br.value, dt, scheme)
            hist = _history(br.kind, g, u_prev[a] - u_prev[c], i_prev[k], scheme)
            if ra is not None:
                A[ra, ra] += g
                if rc is not None:
                    A[ra, rc] -= g
            if rc is not None:
                A[rc, rc] += g
                if ra is not None:
                    A[rc, ra] -= g
            if hist != 0.0:
                inject(c, hist)
                inject(a, -hist)
        elif br.kind == "I":
            inject(c, br.value)
            inject(a, -br.value)
        else:  # "V": u_a - u_b = value, with its own branch current unknown
            col = v_cols[k]
            if ra is not None:
                A[col, ra] += 1.0
                A[ra, col] += 1.0
            if rc is not None:
                A[col, rc] -= 1.0
                A[rc, col] -= 1.0
            b[col] = br.value

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
        else:
            currents[k] = br.value
    return u, currents


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

    def step(self, dt, state):
        """One step.  Returns ``(state_new, u, i_branch)``.

        Parameters
        ----------
        dt : float
            Time step (s), finite and positive.
        state : SpiceState
            History at ``t^n``, on this network.

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
        A, b, info = _assemble(self.network, dt, state.u, state.i_branch,
                               self.scheme)
        x = np.linalg.solve(A, b)
        u, currents = _recover(self.network, x, info)
        return (
            SpiceState(self.network, u=u, i_branch=currents, i=state.i, v=state.v),
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

    def step(self, e, h, dt, state):
        """One coupled trapezoidal step.  Returns ``(e_new, h_new, state_new)``.

        Same signature and same return shape as
        ``emfit.terminations.step_rlc``: ``e`` and ``state`` are unmodified, and
        ``h_new`` is ``h`` itself when ``advance`` is ``None``.
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
        A, b, info = _assemble(self.network, dt, state.u, state.i_branch,
                               "trapezoidal", coupling=(M, v_star, state.i))
        x = np.linalg.solve(A, b)
        u, currents = _recover(self.network, x, info)

        n_t = self.port.n_terminals
        i_new = x[info["base_port"]:info["base_port"] + n_t]
        e_new = e_star - 0.5 * dt * (
            self.port.current_density(i_new + state.i) / self.m_eps
        )
        return e_new, h_new, SpiceState(
            self.network, u=u, i_branch=currents, i=i_new,
            v=self.port.voltage(e_new),
        )
