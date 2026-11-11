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

__all__ = ["TerminalPort"]


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
