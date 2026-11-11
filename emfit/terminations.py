"""Terminal ports: a lumped description of the edges a termination sits on.

A ``TerminalPort`` bundles the two things a set of terminals needs and nothing
else:

* ``L``, the *topological* incidence matrix of shape ``(n_edges, n_terminals)``.
  Its +-1 entries say which edge carries which terminal's current; it holds no
  length at all, so it is the same matrix whatever the grid metric is.
* ``W_E``, the *metric* (Hodge) matrix of those same edges -- an edge length
  times a dual face area, say.  Real orthogonal grids give a diagonal ``W_E``, a
  lumped element coupled through a non-orthogonal cell does not, so nothing here
  assumes diagonality.

The object is purely algebraic: it maps terminal voltages and currents to the
edge field and back.  It deliberately stops there -- no field solve, no time
stepping, no circuit assembly.
"""

from __future__ import annotations

import numpy as np

__all__ = ["TerminalPort", "RLCState", "step_rlc"]


class TerminalPort:
    """The edge bundle one lumped termination is attached to.

    Parameters
    ----------
    L : array_like, shape (n_edges, n_terminals)
        Incidence matrix: ``L[k, m]`` is the signed share of terminal ``m``'s
        current that flows on edge ``k``.  Topology only, no lengths -- reversing
        a terminal's orientation flips the corresponding column.
    W_E : array_like, shape (n_edges, n_edges)
        Metric matrix of those edges.  It is only ever used as the coefficient
        matrix of ``np.linalg.solve``, so a full (non-diagonal) matrix is fine
        and no inverse is formed.

    Notes
    -----
    Terminal voltages are ``v = L.T @ e`` and edge current densities are
    ``j = solve(W_E, L @ i)``, so the terminal power ``v @ i`` and the field
    power ``e @ (W_E @ j)`` agree identically -- for any ``L`` and any
    *invertible* ``W_E``.  Symmetry of ``W_E`` is never used: the identity is
    algebraic, not a consequence of the metric being symmetric, so a full
    metric from a non-orthogonal cell is just as safe.

    Sign convention: a positive ``port_power`` means power is delivered *from
    the EM field into the circuit's positive terminal*; equivalently,
    ``v @ i > 0`` when the circuit absorbs power.  Here "circuit" is the lumped
    network this port couples to, never the field solver -- the field is the
    source, so the same power is negative seen from the field side.  A
    resistive termination gives a non-negative value; a reactive one stores and
    returns, so its sign alternates over a cycle.
    """

    def __init__(self, L, W_E):
        L = np.asarray(L, dtype=float)
        W_E = np.asarray(W_E, dtype=float)

        if L.ndim != 2:
            raise ValueError(
                "L must be 2-D with shape (n_edges, n_terminals); "
                f"got shape {L.shape}"
            )
        if W_E.ndim != 2 or W_E.shape[0] != W_E.shape[1]:
            raise ValueError(
                "W_E must be 2-D square with shape (n_edges, n_edges); "
                f"got shape {W_E.shape}"
            )
        if W_E.shape[0] != L.shape[0]:
            raise ValueError(
                f"W_E has shape {W_E.shape}, i.e. {W_E.shape[0]} edges, but L "
                f"has shape {L.shape}, i.e. {L.shape[0]} edge rows"
            )

        self._L = L
        self._W_E = W_E

    @property
    def n_edges(self):
        """Number of edges the port is attached to."""
        return self._L.shape[0]

    @property
    def n_terminals(self):
        """Number of lumped terminals."""
        return self._L.shape[1]

    def voltage(self, e):
        """Terminal voltages ``L.T @ e`` for the edge voltages ``e``.

        Parameters
        ----------
        e : array_like, shape (n_edges,)
            Edge voltages (V) of the port's edges.

        Returns
        -------
        ndarray, shape (n_terminals,)
        """
        e = np.asarray(e, dtype=float)
        if e.shape != (self.n_edges,):
            raise ValueError(
                f"e must have shape ({self.n_edges},) for {self.n_edges} edges; "
                f"got shape {e.shape}"
            )
        return self._L.T @ e

    def current_density(self, i):
        """Edge current densities ``solve(W_E, L @ i)`` for terminal currents ``i``.

        Parameters
        ----------
        i : array_like, shape (n_terminals,)
            Terminal currents (A).

        Returns
        -------
        ndarray, shape (n_edges,)
        """
        i = np.asarray(i, dtype=float)
        if i.shape != (self.n_terminals,):
            raise ValueError(
                f"i must have shape ({self.n_terminals},) for "
                f"{self.n_terminals} terminals; got shape {i.shape}"
            )
        return np.linalg.solve(self._W_E, self._L @ i)

    def port_power(self, e, i, *, separate=False):
        """Power at the terminals ``v @ i`` for edge voltages ``e`` and currents ``i``.

        A positive value means power is delivered from the EM field into the
        circuit's positive terminal; equivalently, ``v @ i > 0`` when the
        circuit absorbs power.  The field is the source, so the same power is
        negative seen from the field side.

        Parameters
        ----------
        e : array_like, shape (n_edges,)
            Edge voltages (V).
        i : array_like, shape (n_terminals,)
            Terminal currents (A).
        separate : bool, keyword-only, optional
            Return ``(p_terminals, p_dual)`` instead of the single number, where
            ``p_dual`` is the same power evaluated on the edges,
            ``e @ (W_E @ current_density(i))``.  The two agree exactly in exact
            arithmetic, which is what makes the pair a self-check.  Note this
            is an algebraic identity for any invertible ``W_E``, not a physical
            conservation law -- it holds for junk matrices too, so it validates
            shapes and conventions, not physics.

        Returns
        -------
        float or (float, float)
        """
        v = self.voltage(e)
        i = np.asarray(i, dtype=float)
        if i.shape != (self.n_terminals,):
            raise ValueError(
                f"i must have shape ({self.n_terminals},) for "
                f"{self.n_terminals} terminals; got shape {i.shape}"
            )

        p_terminals = float(v @ i)
        if not separate:
            return p_terminals

        p_dual = float(np.asarray(e, dtype=float) @ (self._W_E @ self.current_density(i)))
        return p_terminals, p_dual


# ---------------------------------------------------------------------------
# a series RLC load: the coupled trapezoidal step
# ---------------------------------------------------------------------------
#
# The load is a branch from the terminals to ground made of R, L and C in
# series.  It cannot be stepped on its own: its current is a function of the
# terminal voltage, and that voltage is what the field's own update produces,
# so the two are implicit in each other once the Ampere law is centred in time.
# Writing s = i^{n+1} + i^n (twice the mid-step branch current), the two
# equations that hold simultaneously are
#
#     field:   e^{n+1} = e* - (dt/2) m_eps^{-1} W_E^{-1} L s
#     branch:  v^{n+1} + v^n = a+ i^{n+1} + a- i^n + 2 v_c^n
#
# with e* the field advanced WITHOUT the load, v = L.T e the terminal voltage,
# and the companion coefficients
#
#     a+ = R + 2L/dt + dt/(2C),      a- = R - 2L/dt + dt/(2C)
#
# which follow from the trapezoidal rule applied to v = R i + L di/dt + v_c and
# C dv_c/dt = i (the dt/(2C) term is the charge the branch capacitor gains
# across the step, brought back as a voltage).  Eliminating v gives ONE linear
# system in i^{n+1},
#
#     [a+ I + M] i^{n+1} = v* + v^n - 2 v_c^n - [a- I + M] i^n ,
#
# where M = (dt/2) L.T m_eps^{-1} W_E^{-1} L is the field's own reactance seen
# from the terminals -- the "mass matrix" of the coupling.  M is what makes
# this a coupled block (2x2 for one terminal) rather than a circuit stepped
# against a fixed source: a current drawn by the load depresses the very
# voltage that drives it.  Degenerate L = 0 drops 2L/dt; degenerate C = 0 drops
# dt/(2C) and the charge history, and for R alone the block collapses to
# (R + M) s = v* + v^n, i.e. the trapezoidal decay of a plain resistance to
# ground -- not the open circuit that C -> 0 as a LIMIT would give.
#
# No Newton iteration is needed and none is used *on this RLC path*: every
# term below is linear, so e* is linear in the unknown current and one solve is
# exact.  (A circuit network reached through ``emfit.spice`` may carry a diode
# and then does iterate -- see ``spice._solve_step`` -- but that is a different
# element set, not this one.)  The resulting scheme conserves a discrete energy
# EXACTLY, per step:
#
#     dU_field + dU_L + dU_C + (dt/4) R s^2 = 0,   s = i^{n+1} + i^n
#
# which is the trapezoidal rule's usual exact-in-the-quadratic statement and is
# what the energy gates in the tests measure.


def _as_terminal_vector(x, n, name):
    """``x`` as a length-``n`` float vector; ``None`` means all zeros."""
    if x is None:
        return np.zeros(n)
    x = np.asarray(x, dtype=float).ravel()
    if x.shape != (n,):
        raise ValueError(
            f"{name} must have shape ({n},) for {n} terminals; got shape "
            f"{x.shape}"
        )
    return x


class RLCState:
    """A series-RLC load's memory, plus the operators the coupled step reads.

    Parameters
    ----------
    port : TerminalPort
        The edge bundle the load is attached to.  Both of the port's
        functionals are used and nothing else: ``voltage`` for ``v = L.T @ e``
        and ``current_density`` for the mass-matrix solve ``W_E^{-1} @ L @ i``.
    m_eps : array_like, shape (n_edges,)
        Edge capacitances of the port's edges (the ``m_eps`` diagonal of the
        Ampere law, in farads).  Positive: it is the field's own inertia, and a
        zero would leave the field with no say in the coupling at all.
    advance : callable, keyword-only, optional
        The field update with the load REMOVED, ``(e, h, dt) -> (e*, h*)``.
        This is where :func:`emfit.evolve.step_explicit` is plugged in -- pass a
        closure that calls it with ``j=None`` and the same C, C~, inverse
        masses, PML and PEC mask the rest of the run uses, so the only thing
        this module adds to the field is the load current.  ``None``, the
        default, means *no field motion this step*: the pure circuit-side case
        of a node capacitance with no Faraday side.
    i, v_c, v : array_like, shape (n_terminals,), keyword-only, optional
        History the trapezoidal rule needs: last branch current, last capacitor
        voltage and last terminal voltage.  Default zeros.

    Notes
    -----
    A step never mutates a state; :func:`step_rlc` returns a new one.  Keeping
    the old one costs three short vectors and buys the ability to inspect or
    re-run the last step.
    """

    def __init__(self, port, m_eps, *, advance=None, i=None, v_c=None, v=None):
        if not isinstance(port, TerminalPort):
            raise TypeError(
                "port must be a TerminalPort, not "
                f"{type(port).__name__}: the coupling is expressed entirely in "
                "the port's voltage and current_density functionals"
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
        self.port = port
        self.m_eps = m_eps
        self.advance = advance
        self.i = _as_terminal_vector(i, port.n_terminals, "i")
        self.v_c = _as_terminal_vector(v_c, port.n_terminals, "v_c")
        self.v = _as_terminal_vector(v, port.n_terminals, "v")


def step_rlc(e, h, dt, R, L, C, state):
    """One coupled trapezoidal step of a series RLC load on ``state.port``.

    Solves the block (n_t x n_t) that couples the load current to the terminal
    voltage and applies the field back-reaction as a current density through the
    port's own metric solve.  See the derivation above :class:`RLCState`; no
    Newton iteration is involved or needed.

    Parameters
    ----------
    e : array_like, shape (n_edges,)
        Edge voltages at ``t^n``.
    h : array_like or None
        Magnetic field at ``t^{n-1/2}``.  Passed straight to ``state.advance``
        and otherwise returned untouched, so this call has the same shape as the
        load-free field update it extends.
    dt : float
        Time step (s), positive.
    R, L, C : float
        Series branch resistance (ohm), inductance (H) and capacitance (F).
        Non-negative, and a ZERO means the element is ABSENT (a short in the
        branch), not a limit:

        * ``L = 0`` drops the ``2L/dt`` term -- a wire.
        * ``C = 0`` drops the ``dt/(2C)`` term AND the charge history -- a wire.
          This is the one place the choice matters: ``C -> 0`` as a *limit* is
          an OPEN circuit (impedance ``1/(jwC) -> inf``), so a literal
          implementation would silently switch the load off and leave ``R``
          dangling with no path to ground.  The companion-model convention is
          used instead, so ``R=50, L=0, C=0`` is a 50 ohm resistance to ground.
    state : RLCState
        Port, edge masses, field-advance hook and the history of the last step.

    Returns
    -------
    (e_new, h_new, state_new) : (ndarray, array_like or None, RLCState)
        Edge voltages at ``t^{n+1}``, the magnetic field the field update left
        behind, and the advanced history.  ``e`` itself is not modified.
        ``h_new`` is ``h`` itself -- the same object, not a copy -- whenever
        ``state.advance`` is ``None``: with no Faraday side to move the field is
        frozen, so the caller's own ``h`` is handed straight back.
    """
    dt = float(dt)
    R = float(R)
    L_s = float(L)  # the incidence matrix already lives on ``state.port``
    C_s = float(C)

    if not np.isfinite(dt) or dt <= 0.0:
        raise ValueError(f"dt must be finite and positive; got {dt!r}")
    for name, value in (("R", R), ("L", L_s), ("C", C_s)):
        if not np.isfinite(value) or value < 0.0:
            raise ValueError(
                f"{name} must be finite and non-negative (it is a physical "
                f"element, and a ZERO means absent, not a limit); got {value!r}"
            )
    if not isinstance(state, RLCState):
        raise TypeError(f"state must be an RLCState, not {type(state).__name__}")
    if C_s == 0.0 and np.any(state.v_c != 0.0):
        raise ValueError(
            "C = 0 means the branch capacitor is ABSENT (a short), but the "
            f"state carries a charge voltage {state.v_c.tolist()}; a short "
            "holds no voltage, so this state is inconsistent with the load"
        )

    port = state.port
    n_t = port.n_terminals
    e_prev = np.asarray(e, dtype=float).ravel()
    if e_prev.shape != (port.n_edges,):
        raise ValueError(
            f"e must have shape ({port.n_edges},) for {port.n_edges} edges; "
            f"got shape {e_prev.shape}"
        )

    # (1) Faraday + Ampere with NO load.  Everything the load does is a
    #     correction to this, which is what keeps the block linear.
    if state.advance is None:
        e_star = e_prev.copy()
        h_new = h
    else:
        e_star, h_new = state.advance(e_prev, h, dt)
        e_star = np.asarray(e_star, dtype=float)
    v_star = port.voltage(e_star)

    # (2) M = (dt/2) L.T m_eps^{-1} W_E^{-1} L, column by column through the
    #     port's own functionals: current_density injects a unit terminal
    #     current, /m_eps turns it into a voltage drop on the edges, and
    #     voltage reads the terminals back off those edges.  No private matrix
    #     is touched and the metric solve is the one the port already owns.
    field_reactance = np.empty((n_t, n_t))
    for m in range(n_t):
        unit = np.zeros(n_t)
        unit[m] = 1.0
        field_reactance[:, m] = port.voltage(
            port.current_density(unit) / state.m_eps
        )
    M = 0.5 * dt * field_reactance

    # (3) trapezoidal companion of the series branch.
    beta = 0.0 if L_s == 0.0 else 2.0 * L_s / dt
    charge = 0.0 if C_s == 0.0 else dt / (2.0 * C_s)
    eye = np.eye(n_t)
    a_plus = R + beta + charge
    a_minus = R - beta + charge

    # (4) the block: one linear solve in i^{n+1}.
    lhs = a_plus * eye + M
    rhs = (v_star + state.v - 2.0 * state.v_c
           - (a_minus * eye + M) @ state.i)
    i_new = np.linalg.solve(lhs, rhs)

    # (5) field back-reaction: the mean current over the step, injected as a
    #     current density, is exactly the ``-j`` term of the Ampere law.
    step_current = i_new + state.i
    e_new = e_star - 0.5 * dt * (port.current_density(step_current)
                                 / state.m_eps)
    v_new = port.voltage(e_new)

    v_c_new = (state.v_c + charge * step_current if C_s != 0.0
               else np.zeros(n_t))

    return e_new, h_new, RLCState(
        port, state.m_eps, advance=state.advance,
        i=i_new, v_c=v_c_new, v=v_new,
    )
