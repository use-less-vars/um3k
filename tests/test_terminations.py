"""``emfit.terminations.TerminalPort`` -- the terminal/edge duality.

The one structural claim: ``v @ i`` with ``v = L.T @ e`` equals ``e @ (W_E @ j)``
with ``j = W_E^{-1} @ L @ i``.  The gates pin hand values, random matrices, the
single-terminal case, a three-terminal chain and orientation, plus the shape
validation.

Comparisons use ``rtol=1e-14`` and ``atol=0.0``: the quantities are sums of O(1)
terms, so an absolute floor would hide nothing, while the tight relative bound
still catches a wrong transpose or a stray factor.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.terminations import TerminalPort

RTOL = 1e-14
ATOL = 0.0


def _close(actual, expected):
    return bool(np.all(np.isclose(actual, expected, rtol=RTOL, atol=ATOL)))


def test_hand_computed_voltage_and_power():
    """Gate 1: two edges, one terminal, values small enough to do by hand."""
    L = np.array([[1.0], [-1.0]])
    W_E = np.diag([1.3, 0.7])
    e = np.array([2.0, 0.5])
    i = np.array([0.25])

    port = TerminalPort(L, W_E)

    assert port.n_terminals == 1
    assert port.n_edges == 2

    # v = L.T @ e = 1*2.0 + (-1)*0.5
    assert _close(port.voltage(e), np.array([1.5]))
    # p = v @ i = 1.5 * 0.25
    assert _close(port.port_power(e, i), 0.375)


def test_random_matrices_satisfy_the_terminal_edge_identity():
    """Gate 2: the identity on random ports, diagonal and full SPD alike."""
    rng = np.random.default_rng(0)

    for trial in range(6):
        n_edges = int(rng.integers(2, 6))
        n_terminals = int(rng.integers(1, n_edges + 1))

        # Positive weights only: no cancellation, so the tightened relative
        # tolerance measures roundoff rather than an unfortunate near-zero sum.
        L = rng.uniform(0.2, 1.5, size=(n_edges, n_terminals))

        if trial % 2:
            A = rng.normal(size=(n_edges, n_edges))
            W_E = A @ A.T + n_edges * np.eye(n_edges)  # full SPD, well conditioned
        else:
            W_E = np.diag(rng.uniform(0.5, 1.5, size=n_edges))

        e = rng.uniform(0.5, 1.5, size=n_edges)
        i = rng.uniform(0.5, 1.5, size=n_terminals)

        port = TerminalPort(L, W_E)
        assert port.n_edges == n_edges
        assert port.n_terminals == n_terminals

        p_terminals, p_dual = port.port_power(e, i, separate=True)

        # separate=False is the same number, not a second convention.
        assert _close(p_terminals, port.port_power(e, i))
        # v @ i == e @ (W_E @ j), the claim the whole class exists to make.
        assert _close(p_terminals, p_dual)

        # j is defined by W_E @ j == L @ i, whatever W_E looks like.
        j = port.current_density(i)
        assert j.shape == (n_edges,)
        assert _close(W_E @ j, L @ i)


def test_single_terminal_recovers_the_edge_voltage_itself():
    """Gate 3: with L = [[1]] and W_E = [[2]] the port is a bare wire."""
    port = TerminalPort(np.array([[1.0]]), np.array([[2.0]]))
    e = np.array([3.5])
    i = np.array([-0.4])

    assert _close(port.voltage(e), e)
    # The metric cancels in the power: 2.0 * (i/2.0) == i.
    assert _close(port.port_power(e, i), e[0] * i[0])


def test_three_terminal_chain_keeps_the_identity():
    """Gate 4: three terminals over three edges.

    The identity holds algebraically for *any* ``L``, so it cannot fail here for
    an algebraic reason: this gate guards shapes and transposes, where an
    ``L``/``L.T`` mix-up shows up as a broadcast error or a wrong length.
    """
    L = np.array(
        [
            [1.0, 0.0, 0.0],
            [-1.0, 1.0, 0.0],
            [0.0, -1.0, 1.0],
        ]
    )
    W_E = np.array(
        [
            [1.3, 0.2, 0.0],
            [0.2, 0.7, 0.1],
            [0.0, 0.1, 1.1],
        ]
    )
    e = np.array([2.0, 0.5, -1.0])
    i = np.array([0.1, 0.2, 0.4])

    port = TerminalPort(L, W_E)
    assert port.n_terminals == 3
    assert port.n_edges == 3

    # v = L.T @ e = [e0 - e1, e1 - e2, e2]
    assert _close(port.voltage(e), np.array([1.5, 1.5, -1.0]))

    j = port.current_density(i)
    assert j.shape == (3,)
    assert _close(W_E @ j, L @ i)

    p_terminals, p_dual = port.port_power(e, i, separate=True)
    assert _close(p_terminals, p_dual)


def test_orientation_flip():
    """Gate 5: where the sign convention lives, and where it does not."""
    L = np.array([[1.0], [-1.0]])
    W_E = np.diag([1.3, 0.7])
    e = np.array([2.0, 0.5])
    i = np.array([0.25])

    forward = TerminalPort(L, W_E)
    flipped = TerminalPort(-L, W_E)

    # (1) Both the terminal voltage and the edge current density negate: the
    #     orientation is carried by L alone, W_E is untouched.
    assert _close(flipped.voltage(e), -forward.voltage(e))
    assert _close(flipped.current_density(i), -forward.current_density(i))

    # (2) The identity is orientation blind -- it still holds after the flip.
    p_terminals, p_dual = flipped.port_power(e, i, separate=True)
    assert _close(p_terminals, p_dual)

    # (3) Flipping L alone sends v -> -v with i held fixed, so the power changes
    #     sign: a termination that absorbed power now delivers it.
    assert _close(flipped.port_power(e, i), -forward.port_power(e, i))
    # Flipping L and i together sends v -> -v and i -> -i, so the power is
    # invariant: a reversed terminal carrying reversed current is one and the
    # same physical situation.
    assert _close(flipped.port_power(e, -i), forward.port_power(e, i))


def test_constructor_rejects_mismatched_shapes():
    """Gate 6: the constructor names the offending shapes instead of guessing."""
    with pytest.raises(ValueError, match="shape"):
        TerminalPort(np.array([1.0, -1.0]), np.eye(2))  # L is 1-D

    with pytest.raises(ValueError, match="shape"):
        TerminalPort(np.array([[1.0], [-1.0]]), np.ones((2, 3)))  # W_E not square

    with pytest.raises(ValueError, match="shape"):
        TerminalPort(np.array([[1.0], [-1.0]]), np.eye(3))  # 3 edges vs 2 rows of L
