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
from scipy.linalg import expm

from emfit.terminations import RLCState, TerminalPort, step_rlc

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


# ---------------------------------------------------------------------------
# The coupled series-RLC load.  The gates above pin the port's algebra; these
# pin the load that rides on it -- an R-L-C branch from the terminals to
# ground, stepped with the trapezoidal rule and coupled back into the field
# through the very two functionals the gates above check.
# ---------------------------------------------------------------------------

C_FIELD = 1e-12


def _tank(e0=1.0, i0=0.0, v_c0=0.0):
    """One edge, one terminal, ``W_E = 1``: the smallest honest field there is.

    ``L = [[1]]`` and ``W_E = [[1]]`` make ``v = e`` and
    ``current_density(i) = i``, so both of the port's functionals are the
    identity and any discrepancy belongs to the coupled step rather than to the
    geometry.
    """
    port = TerminalPort(np.eye(1), np.eye(1))
    return port, RLCState(port, [C_FIELD], i=[i0], v_c=[v_c0], v=[e0])


def _energy(e, i, v_c, L, C):
    """Field + inductor + capacitor energy of the tank (J)."""
    return (0.5 * C_FIELD * np.asarray(e) ** 2
            + 0.5 * L * np.asarray(i) ** 2
            + 0.5 * C * np.asarray(v_c) ** 2)


def test_r_only_load_is_a_resistance_to_ground_not_an_open_circuit():
    """``R = 50`` with ``L = C = 0`` must bleed the node to ground.

    ``C = 0`` read as a *limit* is an open circuit (impedance
    ``1/(j*w*C) -> infinity``), which would isolate the node and leave its
    energy constant.  The companion convention -- ``C = 0`` means the capacitor
    is ABSENT, a short -- instead gives the scalar recursion
    ``v^{n+1} = v^n (1 - a/2)/(1 + a/2)`` with ``a = dt/(R*C_FIELD)``: the
    trapezoidal RC decay of a plain 50 ohm resistance to ground.  That closed
    form is asserted directly, because a load that had quietly gone open would
    keep its energy and could still pass a looser "it went down" test on
    roundoff alone.
    """
    _port, state = _tank(e0=1.0)
    R, dt, n_steps = 50.0, 1e-12, 200
    a = dt / (R * C_FIELD)
    factor = (1.0 - 0.5 * a) / (1.0 + 0.5 * a)

    e = np.array([1.0])
    u = [_energy(e[0], state.i[0], state.v_c[0], 0.0, 0.0)]
    for _ in range(n_steps):
        e, _h, state = step_rlc(e, None, dt, R, 0.0, 0.0, state)
        u.append(_energy(e[0], state.i[0], state.v_c[0], 0.0, 0.0))
    u = np.array(u)

    # (a) every single step removes energy; none of them puts any back.
    assert np.all(np.diff(u) < 0.0), f"energy not strictly decreasing: {u}"

    # (b) the decay is exactly the trapezoidal RC rate, so the load is drawing
    #     current rather than floating.
    v_expected = factor ** n_steps
    assert abs(e[0] - v_expected) <= 1e-12 * abs(v_expected), (
        f"R-only decay is off the closed form: v = {e[0]!r}, expected "
        f"{v_expected!r} (a = {a!r} after {n_steps} steps)"
    )

    # (c) a physically meaningful share of the energy is gone, not a
    #     roundoff-sized sliver.
    assert u[-1] <= 1e-3 * u[0], (
        f"dissipated only {1.0 - u[-1] / u[0]:.4%} of the initial energy"
    )


def test_lc_tank_resonates_conserves_energy_and_converges_second_order():
    """Three independent claims about the same coupled block.

    (i) With ``R = 0`` the discrete energy is conserved to roundoff and the tank
        oscillates: it is a resonator, not a slow leak.  The field voltage
        itself never changes sign -- with ``C_FIELD = C`` the charge
        ``C_FIELD*e + C*v_c`` is conserved, so ``e`` swings between 0 and 1 V --
        which is why the oscillation is read off the branch current and off the
        span of ``e`` rather than off sign changes of ``e``.

    (ii) For ``R > 0`` the per-step balance ``dU_field + dU_L + dU_C + (dt/4) R
        (i^{n+1} + i^n)^2 = 0`` holds to roundoff.  The trapezoidal rule is
        exact on a quadratic form, so the scheme carries no damping of its own
        that could masquerade as the load's.

    (iii) Because (ii) is exact, whatever error remains is the global ``O(dt^2)``
        of Crank-Nicolson, and it is graded against the analytic solution
        ``expm(A*T)`` of the ODE the scheme approximates -- never against an
        internal residual, which would be blind to a scheme that conserved the
        wrong thing exactly.  The ODE limit, in the state ``y = [e, i, v_c]``,
        is ``C_FIELD de/dt = -i``, ``L di/dt = e - R i - v_c``, ``C dv_c/dt =
        i``.
    """
    L_s, C_s, dt = 1e-6, 1e-12, 1e-11

    # (i) R = 0: resonating, and lossless to roundoff.
    _port, state = _tank(e0=1.0)
    e = np.array([1.0])
    u0 = float(_energy(e[0], state.i[0], state.v_c[0], L_s, C_s))
    u, v, cur = [u0], [float(e[0])], [float(state.i[0])]
    for _ in range(900):
        e, _h, state = step_rlc(e, None, dt, 0.0, L_s, C_s, state)
        u.append(float(_energy(e[0], state.i[0], state.v_c[0], L_s, C_s)))
        v.append(float(e[0]))
        cur.append(float(state.i[0]))
    u, v, cur = np.array(u), np.array(v), np.array(cur)

    drift = np.max(np.abs(u - u0)) / u0
    assert drift <= 1e-13, f"R = 0 tank drifted by {drift:.3e} of U0"

    crossings = np.count_nonzero(np.diff(np.sign(cur)) != 0)
    assert crossings >= 2, (
        f"the branch current changed sign {crossings} time(s): no resonance"
    )
    assert v.max() / v.min() >= 1e3, (
        f"the field voltage barely moved: {v.min():.3e} .. {v.max():.3e} V"
    )

    # (ii) R > 0: the per-step energy balance is exact to roundoff.
    R_small = 1.0
    _port, state = _tank(e0=1.0)
    e = np.array([1.0])
    worst = 0.0
    for _ in range(200):
        e_new, _h, state_new = step_rlc(e, None, dt, R_small, L_s, C_s, state)
        balance = (
            0.5 * C_FIELD * (e_new[0] ** 2 - e[0] ** 2)
            + 0.5 * L_s * (state_new.i[0] ** 2 - state.i[0] ** 2)
            + 0.5 * C_s * (state_new.v_c[0] ** 2 - state.v_c[0] ** 2)
            + 0.25 * dt * R_small * (state_new.i[0] + state.i[0]) ** 2
        )
        worst = max(worst, abs(balance))
        e, state = e_new, state_new
    assert worst <= 1e-12 * u0, (
        f"per-step energy balance is off by {worst:.3e} J against U0 = "
        f"{u0:.3e} J"
    )

    # (iii) second order, against the analytic solution of the ODE limit.
    R_ode, T, dt0 = 566.0, 4.5e-9, 1e-11
    A = np.array([
        [0.0, -1.0 / C_FIELD, 0.0],
        [1.0 / L_s, -R_ode / L_s, -1.0 / L_s],
        [0.0, 1.0 / C_s, 0.0],
    ])
    y_exact = expm(A * T) @ np.array([1.0, 0.0, 0.0])
    u_exact = float(_energy(y_exact[0], y_exact[1], y_exact[2], L_s, C_s))
    assert u_exact <= 0.8 * u0, (
        f"the test point must be damped, not near-lossless: U(T) = {u_exact!r} "
        f"against U0 = {u0!r}"
    )

    def _residual(dt_step):
        _p, st = _tank(e0=1.0)
        ee = np.array([1.0])
        for _ in range(int(round(T / dt_step))):
            ee, _h, st = step_rlc(ee, None, dt_step, R_ode, L_s, C_s, st)
        return abs(float(_energy(ee[0], st.i[0], st.v_c[0], L_s, C_s)) - u_exact)

    residuals = [_residual(dt0), _residual(dt0 / 2.0), _residual(dt0 / 4.0)]
    ratios = [residuals[0] / residuals[1], residuals[1] / residuals[2]]
    assert all(3.2 <= r <= 4.8 for r in ratios), (
        f"Crank-Nicolson is not converging at second order: residuals "
        f"{residuals!r}, measured ratios {ratios!r} (halving dt should quarter "
        f"the error against expm(A*T))"
    )


def test_orientation_flip_is_a_joint_flip_of_signs():
    """``L -> -L`` alone is NOT a symmetry; ``L -> -L`` with ``i -> -i`` is.

    Both halves are asserted, because they answer different questions:

    * The coupled step flips the incidence matrix and lets the load's current
      respond.  Then ``i`` flips with the geometry -- it is the same physical
      situation seen with the arrow reversed -- the edge voltages come out
      bit-identical (``j = W_E^{-1} L i`` is a product of two sign flips) and
      ``v*i``, the power, is invariant.  This is the physics.
    * Held the other way, with ``i`` pinned, ``v = L.T e`` negates and ``v @ i``
      negates with it: the bare algebra is orientation-odd.  A port that
      reported invariant power with ``i`` fixed would be reporting the wrong
      quantity.
    """
    R, L_s, C_s, dt, n_steps = 50.0, 1e-6, 1e-12, 1e-11, 200
    plus = TerminalPort(np.array([[1.0]]), np.eye(1))
    minus = TerminalPort(np.array([[-1.0]]), np.eye(1))

    def _run(port):
        e = np.array([1.0])
        # the stored terminal voltage must be the port's OWN reading of e, sign
        # included: taking it from the port is what keeps the two runs the same
        # physical situation rather than two different initial conditions.
        state = RLCState(port, [C_FIELD], i=[0.0], v_c=[0.0], v=port.voltage(e))
        traj = {"e": [], "v": [], "i": [], "v_c": [], "u": []}
        for _ in range(n_steps):
            e, _h, state = step_rlc(e, None, dt, R, L_s, C_s, state)
            traj["e"].append(e[0])
            traj["v"].append(state.v[0])
            traj["i"].append(state.i[0])
            traj["v_c"].append(state.v_c[0])
            traj["u"].append(
                float(_energy(e[0], state.i[0], state.v_c[0], L_s, C_s))
            )
        return {k: np.asarray(val, dtype=float) for k, val in traj.items()}

    ref, flip = _run(plus), _run(minus)

    # the same edges, edge for edge: j = W_E^{-1} L i is unchanged.
    assert np.array_equal(ref["e"], flip["e"]), (
        "flipping L must not move the field: max |de| = "
        f"{np.max(np.abs(ref['e'] - flip['e']))!r}"
    )
    # ... and every terminal quantity is the joint flip, exactly.
    assert np.array_equal(flip["v"], -ref["v"])
    assert np.array_equal(flip["i"], -ref["i"])
    assert np.array_equal(flip["v_c"], -ref["v_c"])
    # power at the terminals is invariant, as it must be.
    assert np.allclose(flip["v"] * flip["i"], ref["v"] * ref["i"],
                       rtol=1e-15, atol=0.0)
    # ... and so is the energy, term by term.
    assert np.array_equal(flip["u"], ref["u"])

    # The other half: with i held FIXED, L -> -L negates the power.
    e_held = np.array([1.0])
    i_held = np.array([0.25])
    p_plus = plus.port_power(e_held, i_held)
    p_minus = minus.port_power(e_held, i_held)
    assert p_plus != 0.0
    assert _close(p_minus, -p_plus), (
        f"orientation-odd power: {p_plus!r} against {p_minus!r}"
    )


def test_step_rlc_returns_the_advanced_magnetic_field():
    """The step hands back the field it moved, so a run can chain Faraday.

    Two halves, because they are two different obligations:

    * ``advance=None`` means the field is frozen.  The returned ``h`` must then
      be the caller's own object, unchanged -- not a copy and not ``None``: a
      caller chaining ``e, h, state = step_rlc(e, h, ...)`` must not see its
      history silently reset.
    * With an ``advance`` that does move the field, the returned ``h`` is what
      that hook produced, so feeding it into the next step chains H across
      steps (``h + 1``, then ``h + 2``) instead of restarting every step from
      the caller's stale value.
    """
    port = TerminalPort(np.eye(1), np.eye(1))
    e = np.array([1.0])
    h = np.array([3.0])

    # No Faraday side: the caller's own h comes straight back.
    frozen = RLCState(port, [C_FIELD], i=[0.0], v_c=[0.0], v=[0.0])
    _e_new, h_new, state_new = step_rlc(e, h, 1e-11, 0.0, 0.0, 0.0, frozen)
    assert h_new is h, "the frozen-field path must return the caller's own h"
    assert np.array_equal(h_new, h)
    assert isinstance(state_new, RLCState)

    # With a Faraday side, H chains: the second step starts from the FIRST
    # step's h, not from the caller's original.
    def _advance(e_in, h_in, dt):
        return e_in, h_in + 1.0

    moving = RLCState(port, [C_FIELD], advance=_advance,
                      i=[0.0], v_c=[0.0], v=[0.0])
    _e_1, h_1, moving = step_rlc(e, h, 1e-11, 0.0, 0.0, 0.0, moving)
    assert _close(h_1, h + 1.0), f"one step gave h = {h_1!r}, wanted {h + 1.0!r}"
    _e_2, h_2, _moving = step_rlc(e, h_1, 1e-11, 0.0, 0.0, 0.0, moving)
    assert _close(h_2, h + 2.0), f"two steps gave h = {h_2!r}, wanted {h + 2.0!r}"

