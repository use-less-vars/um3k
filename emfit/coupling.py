"""Couple an FIT field solve to a lumped circuit through a capacitive port.

The bridge is a statement about ONE object: the capacitance each primal edge
carries.  ``emfit.materials.material_matrices`` already stores it, on every
edge ``e``,

    m_eps[e] = eps_e * A~_e / L_e                                    [F]

-- permittivity times the dual face area over the primal length -- and that is
exactly the coefficient in the field energy and in Ampere's law.  So a group of
edges tied to one circuit terminal carries

    Q(V) = sum_e m_eps[e] V = C_group V,   C_group = sum_e m_eps[e]   [F]

provided the group is EQUIPOTENTIAL: the lumped assumption is that the metal
the terminal stands in for is an equipotential over a region small compared
with a wavelength, so every edge of the group moves together.  (That is an
assumption about the geometry the caller describes, not an identity: a group
stretched over several cells of a gap is treated as a bundle in parallel, not
as a series string -- see :func:`group_capacitance`.)

The port that makes the field see the circuit as ONE terminal is the
normalized incidence

    L[e, 0] = m_eps[e] / C_group,        W_E = identity.

WHY exactly this, and why not the alternatives
----------------------------------------------
Write ``c_e = m_eps[e]`` and ``C = C_group``.  Two requirements pin the port
down, and both are checked exactly by the test suite:

1. **Potential and charge.**  ``sum_e L[e,0] = sum_e c_e / C = 1``.  Terminal
   voltage is ``v = L.T @ e``, so a uniform field ``e = V`` reads back as
   ``v = V`` -- the terminal sees the potential difference across the gap.
   With ``W_E = I`` the edge current density is ``j = L i``, so
   ``sum_e j_e = i``: the terminal current is the total current entering the
   group, which is what the discrete Ampere law with a current source needs.

2. **Field inertia.**  ``emfit.terminations.step_rlc`` builds the load's
   inertia as ``M = (dt/2) L.T diag(1/m_eps) W_E^{-1} L``.  With the port
   above,

       M = (dt/2) sum_e L[e,0]^2 / c_e
         = (dt/2) sum_e (c_e/C)^2 / c_e
         = (dt/2) sum_e c_e / C^2
         = (dt/2) / C_group .

   Over one step the group loses ``dt i / C_group`` of voltage: the companion
   model of a capacitance ``C_group`` in series with the branch.  Equivalently
   every edge of the group drops by the SAME ``0.5 dt (i^{n+1}+i^n) / C_group``
   -- an equipotential group stays equipotential, which is the whole point.

Rejected alternative A: ``W_E = C_group * diag(1/c_e)``.  It looks natural
("the port's own metric"), and gives ``j_e = i / C_group`` on every edge --
the same current on a fat edge as on a thin one.  Then ``sum_e j_e = n i / C``
for ``n`` edges, so the terminal current is no longer the group's total, and
``M = (dt/2) sum_e c_e^2 / C^3``, which is ``(dt/2)/C`` only when every ``c_e``
is equal.  Both statements the port exists to make are wrong on a non-uniform
group.

Rejected alternative B: the boolean incidence ``L[e,0] = 1`` (or ``1/n``).  It
gets ``sum_e L = n`` (resp. 1) so either ``v = n V`` or a correct ``v``, but
``M = (dt/2) sum_e L^2 / c_e = (dt/2) / C_series`` with
``1/C_series = sum_e 1/c_e``: the edges in SERIES -- the wrong topology for a
bundle of parallel edge capacitances, and off by a factor ``n`` on a uniform
grid.  The ``c_e`` weighting is what selects parallel (equipotential) over
series.

Consequences, all exact rather than order-``dt^2``: the port's field energy is
``1/2 C_group v^2``; terminal power ``v i`` equals field power ``e . j``; a
resistive termination decays at the trapezoidal rate ``(1-x)/(1+x)`` with
``x = dt/(2 R C_group)``; an inductive one oscillates at the eigenvalue phase
``2 arctan(omega dt/2)``, ``omega = 1/sqrt(L C_group)``.

Everything here is built out of ``emfit.terminations``' public functionals
(``voltage``, ``current_density``, ``step_rlc``): this module adds geometry, an
energy helper and a run driver, and no coupling algebra of its own.
"""

from __future__ import annotations

import numpy as np

from .spice import SpicePort
from .terminations import RLCState, TerminalPort, step_rlc

__all__ = [
    "edge_capacitance",
    "group_capacitance",
    "capacitive_port",
    "gap_edges",
    "field_energy",
    "stored_energy",
    "run_terminated",
    "run_network",
]


def _edge_list(edges):
    """Validate an edge index list and return it 1-D and integer."""
    edges = np.asarray(edges, dtype=int).ravel()
    if edges.size == 0:
        raise ValueError("edges must name at least one primal edge; got an empty list")
    return edges


def edge_capacitance(m_eps, edges):
    """Edge capacitances ``m_eps[edges]`` [F] of a port's edges.

    Parameters
    ----------
    m_eps : array_like, shape (n_edges_total,)
        The ``m_eps`` diagonal of the Ampere law, from
        :func:`emfit.materials.material_matrices`.
    edges : array_like of int
        Indices into ``m_eps`` of the port's edges.

    Returns
    -------
    ndarray, shape (len(edges),)
    """
    m_eps = np.asarray(m_eps, dtype=float).ravel()
    edges = _edge_list(edges)
    if edges.min() < 0 or edges.max() >= m_eps.size:
        raise ValueError(
            f"edges must index into m_eps of length {m_eps.size}; got indices "
            f"in [{edges.min()}, {edges.max()}]"
        )
    return m_eps[edges]


def group_capacitance(m_eps, edges):
    """Port capacitance ``C_group = sum_e m_eps[e]`` [F].

    The SUM, not the series combination: the port is an equipotential bundle, so
    its edge capacitances charge in parallel.  For a one-cell gap between plates
    of area ``A`` a distance ``d`` apart this is exactly ``eps A / d``; for a gap
    spanning ``n`` equal cells it is ``n`` times that -- the parallel-bundle
    (equipotential) answer, not the series one.  This function reports what the
    port as specified carries, and the equipotential bundle is part of that
    specification.

    Parameters
    ----------
    m_eps : array_like, shape (n_edges_total,)
        Edge capacitances of the whole cell complex.
    edges : array_like of int
        The port's edge indices.

    Returns
    -------
    float
    """
    return float(np.sum(edge_capacitance(m_eps, edges)))


def capacitive_port(m_eps, edges):
    """One-terminal :class:`~emfit.terminations.TerminalPort` for an edge group.

    Builds ``L[e, 0] = m_eps[e] / C_group`` and ``W_E = identity``: the port
    whose voltage is the group's potential, whose terminal current is the
    group's total current, and whose field inertia is ``(dt/2)/C_group``.  The
    module docstring carries the derivation and the two rejected alternatives.

    Parameters
    ----------
    m_eps : array_like, shape (n_edges_total,)
        Edge capacitances of the whole cell complex.
    edges : array_like of int
        The port's edge indices; they are assumed equipotential.

    Returns
    -------
    TerminalPort
        With ``n_edges == len(edges)`` and ``n_terminals == 1``.
    """
    c = edge_capacitance(m_eps, edges)
    if not np.all(np.isfinite(c)) or np.any(c <= 0.0):
        raise ValueError(
            "every port edge needs a finite, positive capacitance -- it is the "
            f"field's own inertia; got {c.tolist()}"
        )
    L = (c / c.sum()).reshape(c.size, 1)
    return TerminalPort(L, np.eye(c.size))


def gap_edges(cc, *, ix, j0, j1, k0=0, k1=None):
    """The ``ey`` edges of the y-gap ``j0 <= j < j1`` in the column ``(ix, k)``.

    These are the edges that carry the field across a gap between plates normal
    to ``y``: edge ``(ix, j, k)`` runs from node ``(ix, j, k)`` to
    ``(ix, j+1, k)``, so ``j in [j0, j1)`` spans the gap from plane ``j0`` to
    plane ``j1``.  Returned flattened in ``(j, k)`` order, which is the edge
    order the port and the field then share.

    Parameters
    ----------
    cc : CellComplex
        The cell complex the stepper runs on.
    ix : int
        x-index of the column the gap edges live in.
    j0, j1 : int
        Half-open range of y-cells the gap spans; ``j1 > j0``.
    k0, k1 : int, optional
        Half-open range of z-indices; ``k1`` defaults to ``cc.nz``.

    Returns
    -------
    ndarray of int, shape (n_edges,)
    """
    if k1 is None:
        k1 = getattr(cc, "nz", None)
        if k1 is None:
            raise ValueError(
                "k1 was not given and cc exposes no 'nz' to default it from"
            )
    ix, j0, j1, k0, k1 = int(ix), int(j0), int(j1), int(k0), int(k1)
    if j1 <= j0:
        raise ValueError(f"the gap must span at least one y-cell; got j0={j0}, j1={j1}")
    if k1 <= k0:
        raise ValueError(f"the gap must span at least one z-cell; got k0={k0}, k1={k1}")
    return np.asarray(
        [int(cc.idx_ey(ix, j, k)) for j in range(j0, j1) for k in range(k0, k1)],
        dtype=int,
    )


def field_energy(m_eps, e):
    """Electric field energy ``1/2 sum_e m_eps[e] e_e^2`` [J] of these edges.

    Parameters
    ----------
    m_eps : array_like, shape (n_edges,)
        Edge capacitances of these edges (port-local is the usual case).
    e : array_like, shape (n_edges,)
        Edge voltages.

    Returns
    -------
    float
    """
    m_eps = np.asarray(m_eps, dtype=float).ravel()
    e = np.asarray(e, dtype=float).ravel()
    if m_eps.shape != e.shape:
        raise ValueError(
            f"m_eps and e must have the same shape; got {m_eps.shape} and {e.shape}"
        )
    return float(0.5 * np.dot(m_eps, e * e))


def stored_energy(m_eps, e, state, *, L, C):
    """Field energy plus the branch's inductor and capacitor energy [J].

    ``1/2 sum_e m_eps[e] e_e^2 + 1/2 L_s |i|^2 + 1/2 C_s |v_c|^2`` -- the
    quantity :func:`emfit.terminations.step_rlc` conserves up to the resistor's
    ``(dt/4) R |i^{n+1}+i^n|^2`` dissipation, with ``L``/``C`` the branch values
    (zero means the element is absent, exactly as in ``step_rlc``).

    Parameters
    ----------
    m_eps : array_like, shape (n_edges,)
        Edge capacitances of the port's edges.
    e : array_like, shape (n_edges,)
        Edge voltages at the same time as ``state``.
    state : RLCState
        The load history to read ``i`` and ``v_c`` from.
    L, C : float
        Series branch inductance (H) and capacitance (F).

    Returns
    -------
    float
    """
    if not isinstance(state, RLCState):
        raise TypeError(f"state must be an RLCState, not {type(state).__name__}")
    m_eps = np.asarray(m_eps, dtype=float).ravel()
    if m_eps.shape != (state.port.n_edges,):
        raise ValueError(
            f"m_eps must have shape ({state.port.n_edges},) for the port's "
            f"edges; got {m_eps.shape}"
        )
    return float(
        field_energy(m_eps, e)
        + 0.5 * float(L) * float(np.dot(state.i, state.i))
        + 0.5 * float(C) * float(np.dot(state.v_c, state.v_c))
    )


def run_terminated(stepper, port, edges, *, R=0.0, L=0.0, C=0.0, nsteps, source=None):
    """Run the field solver with the port's RLC load attached at every step.

    Each step is one :func:`~emfit.terminations.step_rlc` call whose ``advance``
    hook is this stepper: the load-free update is
    :meth:`emfit.evolve.FITStepper.step` with ``j=None``, and the load then adds
    its back-reaction as a current density on the port's own edges through the
    port's metric solve.  The field outside the port is exactly what the
    load-free update made it -- the load is felt only through those edges.

    Parameters
    ----------
    stepper : FITStepper
        The field solver.  Its ``e`` and ``h`` are the state and are left at the
        final time on return.
    port : TerminalPort
        A port over ``edges``, e.g. from :func:`capacitive_port`.
    edges : array_like of int
        Global edge indices of the port's edges, in the port's own order.
    R, L, C : float, keyword-only
        Series branch resistance (ohm), inductance (H), capacitance (F); a zero
        means the element is absent (``R=50, L=0, C=0`` is 50 ohm to ground).
        Default: all absent, a short across the port.
    nsteps : int, keyword-only
        Number of steps; must be positive.
    source : callable, keyword-only, optional
        ``source(n)`` is evaluated before step ``n`` (0-based).  If it returns a
        number, the port's edges are set to that potential just before the step
        -- an ideal voltage drive.  ``None`` (the default, or a ``None`` return)
        leaves the field alone.

    Returns
    -------
    dict
        ``v``, ``i``, ``field_energy`` (float arrays of length ``nsteps + 1``),
        ``e`` (shape ``(nsteps + 1, port.n_edges)``) and ``state`` (the final
        :class:`RLCState`).  Entry 0 is the state before the first step.
    """
    if not isinstance(port, TerminalPort):
        raise TypeError(f"port must be a TerminalPort, not {type(port).__name__}")
    edges = _edge_list(edges)
    if edges.shape != (port.n_edges,):
        raise ValueError(
            f"edges must list the port's {port.n_edges} edges; got {edges.shape[0]}"
        )
    nsteps = int(nsteps)
    if nsteps < 1:
        raise ValueError(f"nsteps must be positive; got {nsteps}")
    dt = getattr(stepper, "dt", None)
    if dt is None:
        raise ValueError(
            "stepper.dt is None -- this driver needs the step the field solver "
            "actually uses, so construct FITStepper with dt"
        )
    dt = float(dt)

    def advance(e_local, h, _dt):
        # The load-free field update.  ``step_explicit`` works in place, so the
        # port's slice is scattered into the stepper's arrays and the result
        # comes back as copies: ``step_rlc`` still needs the ``e`` it was handed
        # (as ``e_prev``) to form the back-reaction.
        stepper.e[edges] = np.asarray(e_local, dtype=float)
        stepper.h[:] = np.asarray(h, dtype=float)
        stepper.step()  # returns the stepper itself; the field is in-place
        return np.array(stepper.e, dtype=float)[edges].copy(), np.array(
            stepper.h, dtype=float
        ).copy()

    m_eps = np.asarray(stepper.m_eps, dtype=float).ravel()[edges]
    e_local = np.array(stepper.e, dtype=float)[edges].copy()
    h = np.array(stepper.h, dtype=float).copy()
    state = RLCState(port, m_eps, advance=advance, v=port.voltage(e_local))

    hist_v = np.empty(nsteps + 1)
    hist_i = np.empty(nsteps + 1)
    hist_e = np.empty((nsteps + 1, port.n_edges))
    hist_u = np.empty(nsteps + 1)
    hist_v[0] = port.voltage(e_local)[0]
    hist_i[0] = state.i[0]
    hist_e[0] = e_local
    hist_u[0] = field_energy(m_eps, e_local)

    for n in range(nsteps):
        if source is not None:
            drive = source(n)
            if drive is not None:
                e_local = np.full(port.n_edges, float(drive))
        e_local, h, state = step_rlc(e_local, h, dt, R, L, C, state)
        hist_v[n + 1] = port.voltage(e_local)[0]
        hist_i[n + 1] = state.i[0]
        hist_e[n + 1] = e_local
        hist_u[n + 1] = field_energy(m_eps, e_local)

    return {
        "v": hist_v,
        "i": hist_i,
        "e": hist_e,
        "field_energy": hist_u,
        "state": state,
    }


def run_network(
    stepper,
    port,
    edges,
    network,
    *,
    nsteps,
    source=None,
    source_edges=None,
    max_iter=None,
):
    """Run the field solver with a SPICE ``CircuitNetwork`` on the port.

    The counterpart of :func:`run_terminated` for a load that is a netlist
    instead of one series R-L-C: each step is one
    :meth:`emfit.spice.SpicePort.step`, whose ``advance`` hook is this stepper's
    own load-free update.  That placement is deliberate -- ``SpicePort.step``
    forms ``e_new = e_star - (dt/2) L (i_new + i_old) / m_eps`` from what
    ``advance`` returns, so ``advance`` must be the *port-open* field step.  A
    second back-reaction there would count the terminal current twice.

    Parameters
    ----------
    stepper : FITStepper
        The field solver.  Its ``e`` and ``h`` are the state and are left at the
        final time on return.
    port : TerminalPort
        A port over ``edges``, e.g. from :func:`capacitive_port`.
    edges : array_like of int
        Global edge indices of the port's edges, in the port's own order.
    network : CircuitNetwork
        The circuit.  Nodes ``1 .. port.n_terminals`` are the port terminals, in
        the port's own order; node 0 is ground.
    nsteps : int, keyword-only
        Number of steps; must be positive.
    source : callable, keyword-only, optional
        ``source(n)`` is evaluated before step ``n`` (0-based) and must return a
        scalar drive in volts per second (a ``dV/dt``), or ``None`` for no drive
        that step.  The drive is turned into a current density
        ``j[e] = m_eps[e] * drive`` on ``source_edges`` -- proportional to the
        edge capacitance, so that every driven edge drops by the same
        ``dt * drive``.  Equal current on unequal edge capacitances would tilt
        the launched pulse off the line's TEM profile.
    source_edges : array_like of int, keyword-only, optional
        Global edge indices carrying the launch current.  ``None`` (the default)
        means the port's own edges.
    max_iter : int, keyword-only, optional
        Newton cap handed to :meth:`SpicePort.step`; ``None`` keeps the
        network solver's own default.  The private name is not imported here.

    Returns
    -------
    dict
        ``v``, ``i`` (``(nsteps + 1, port.n_terminals)``: terminal voltage and
        current), ``e`` (``(nsteps + 1, port.n_edges)``), ``field_energy``
        (length ``nsteps + 1``: the TOTAL electric field energy of the grid, in
        joules, ``0.5 * sum(m_eps * e**2)`` over every edge -- not the port's
        share of it), ``u`` (``(nsteps + 1, network.n_nodes)``: node
        voltages), ``i_branch`` (``(nsteps + 1, network.n_branches)``: branch
        currents, positive ``nodes[0] -> nodes[1]``) and ``state`` (the final
        :class:`emfit.spice.SpiceState`).  Entry 0 is the state before the first
        step.

    Scope
    -----
    Lumped-port co-simulation on a parallel-plate TEM line.  NOT a microstrip
    S-parameter validation, does NOT use ``microstrip_wave``, does NOT terminate
    a real microstrip, does NOT move the E5 ledger row in
    ``docs/design/EM_SOLVER_LEDGER.md:30``.  No ``microstrip_wave``-to-circuit
    bridge exists and none is being built.  The diode is the Task-2 Shockley
    model with no junction capacitance, verified against a root of its own
    equation -- it pins the solver, not the device.
    """
    if not isinstance(port, TerminalPort):
        raise TypeError(f"port must be a TerminalPort, not {type(port).__name__}")
    edges = _edge_list(edges)
    if edges.shape != (port.n_edges,):
        raise ValueError(
            f"edges must list the port's {port.n_edges} edges; got {edges.shape[0]}"
        )
    nsteps = int(nsteps)
    if nsteps < 1:
        raise ValueError(f"nsteps must be positive; got {nsteps}")
    dt = getattr(stepper, "dt", None)
    if dt is None:
        raise ValueError(
            "stepper.dt is None -- this driver needs the step the field solver "
            "actually uses, so construct FITStepper with dt"
        )
    dt = float(dt)

    m_eps_field = np.asarray(stepper.m_eps, dtype=float).ravel()
    n_edges_all = m_eps_field.size
    src = edges if source_edges is None else _edge_list(source_edges)
    if src.size and (src.min() < 0 or src.max() >= n_edges_all):
        raise ValueError(
            f"source_edges must lie in 0..{n_edges_all - 1}; got "
            f"{int(src.min())}..{int(src.max())}"
        )

    # The drive for the step the solver is about to take.  A closure cannot take
    # an argument, so the value is handed over in this one-slot cell.
    drive = [0.0]

    def advance(e_local, h, _dt):
        # The load-free field update, in the same in-place form run_terminated
        # uses: scatter the port's slice in, step, copy back out.
        stepper.e[edges] = np.asarray(e_local, dtype=float)
        stepper.h[:] = np.asarray(h, dtype=float)
        current = np.zeros(n_edges_all)
        if src.size:
            current[src] = m_eps_field[src] * drive[0]
        stepper.step(current)  # returns the stepper itself; the field is in-place
        return (
            np.array(stepper.e, dtype=float)[edges].copy(),
            np.array(stepper.h, dtype=float).copy(),
        )

    spice_port = SpicePort(port, m_eps_field[edges], network=network, advance=advance)
    e_local = np.array(stepper.e, dtype=float)[edges].copy()
    h = np.array(stepper.h, dtype=float).copy()
    state = spice_port.initial_state(v=port.voltage(e_local))
    kw = {} if max_iter is None else {"max_iter": int(max_iter)}

    n_t = port.n_terminals
    hist_v = np.empty((nsteps + 1, n_t))
    hist_i = np.empty((nsteps + 1, n_t))
    hist_e = np.empty((nsteps + 1, port.n_edges))
    hist_u = np.empty(nsteps + 1)
    hist_un = np.empty((nsteps + 1, network.n_nodes))
    hist_ib = np.empty((nsteps + 1, network.n_branches))

    hist_v[0] = port.voltage(e_local)
    hist_i[0] = state.i
    hist_e[0] = e_local
    hist_u[0] = field_energy(m_eps_field, np.asarray(stepper.e, dtype=float).ravel())
    hist_un[0] = state.u
    hist_ib[0] = state.i_branch

    for n in range(nsteps):
        drive[0] = 0.0
        if source is not None:
            value = source(n)
            if value is not None:
                drive[0] = float(value)
        e_local, h, state = spice_port.step(e_local, h, dt, state, **kw)
        # ``SpicePort.step`` applies the trapezoidal back-reaction to the port
        # slice it *returns*, not in place on ``stepper.e``: until it is
        # scattered back, the stepper's field is one correction stale on those
        # edges (the interior was advanced by ``advance`` this step).  Scatter
        # before reading the whole-grid energy so the tally is the state the
        # solver is actually carrying.
        stepper.e[edges] = np.asarray(e_local, dtype=float)
        hist_v[n + 1] = port.voltage(e_local)
        hist_i[n + 1] = state.i
        hist_e[n + 1] = e_local
        hist_u[n + 1] = field_energy(
            m_eps_field, np.asarray(stepper.e, dtype=float).ravel()
        )
        hist_un[n + 1] = state.u
        hist_ib[n + 1] = state.i_branch

    return {
        "v": hist_v,
        "i": hist_i,
        "e": hist_e,
        "field_energy": hist_u,
        "u": hist_un,
        "i_branch": hist_ib,
        "state": state,
    }
