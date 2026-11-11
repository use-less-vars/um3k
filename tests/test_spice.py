"""``emfit.spice`` -- lumped companion models and their coupling to a port.

``emfit.spice`` is the scratch implementation behind the lumped-termination
derivation: ``Branch``/``CircuitNetwork`` describe a SPICE-like netlist,
``MNASolver`` steps it, and ``SpicePort`` couples a ``TerminalPort`` load to the
field through ``m_eps``.  Nothing here is a public API promise, which is exactly
why the behaviour needs pinning: a later edit to the companion forms or to the
port back-reaction is otherwise invisible.

The gates come in two families.

*Accuracy* (A-D): ``MNASolver`` against the closed form of the four textbook
one-ports.  The order is MEASURED by halving ``dt`` and carried in the assertion
message rather than declared: the default scheme is backward Euler, first order
on R-C and R-L (0.985 measured) and numerically damped on the undriven L-C tank
(0.822 measured).  The L-C decay is the scheme's damping, not physics.

*Structure* (E-K): the discrete energy balance

    dU_f + dU_C + dU_L + (dt/4) sum_R R_k s_k^2 = 0,   s_k = i_k' + i_k,

which is what makes ``SpicePort`` trapezoidal in the coupled sense.  It is
checked on the operator's own case (R = 50 across the port, E-H), on R||C and
R-L (F, G), contrasted against ``MNASolver``'s backward Euler on the same
circuits (J), cross-checked against ``emfit.terminations.step_rlc`` for a series
RLC (H), and closed with the documented non-diagonal ``W_E`` limitation (I) and
state immutability (K).

Tolerances: the energy gates compare ``|resid|`` against ``1e-24``.  The
measured values sit between ``1e-28`` (E, G) and ``1e-19`` (J's trapezoidal
R-L), i.e. at roundoff for O(1e-12) energies or below, so the bound is a
roundoff gate with several orders of margin rather than a tuned number.  The
``step_rlc`` cross-check uses ``1e-14`` on fields of order one.

Note on ``U_f``: ``emfit.spice`` states the field energy
``U_f = (1/2) sum_k w_k m_k e_k^2`` with ``w = diag(W_E)`` only in its module
docstring -- the module exports no ``U_f`` callable.  ``_u_f`` below is that one
formula, taken from the docstring, so the balance in this file is the module's
own statement and not a re-derivation.
"""

from __future__ import annotations

import numpy as np

from emfit.spice import Branch, CircuitNetwork, MNASolver, SpicePort, SpiceState
from emfit.terminations import RLCState, TerminalPort, step_rlc

RTOL = 1e-14
ATOL = 0.0

# The one port fixture used by every coupled gate: two edges, one terminal.
# Lm [[1,-1]] means v = e_0 - e_1, so e = [1.0, 0.4] is v = 0.6.
LM = np.array([[1.0], [-1.0]])
WE = np.diag([1.3, 0.7])
W_EN = np.array([[1.3, 0.2], [0.2, 0.7]])
M_EPS = np.array([2e-12, 3e-12])
E0 = np.array([1.0, 0.4])


def _close(actual, expected):
    return bool(np.all(np.isclose(actual, expected, rtol=RTOL, atol=ATOL)))


def _run(net, dt, T, u0=None, scheme="backward_euler"):
    """Step ``net`` to ``T`` and return the node-voltage history."""
    solver = MNASolver(net, scheme=scheme)
    st = SpiceState(net, u=u0) if u0 is not None else solver.initial_state()
    out = []
    for _ in range(max(1, int(round(T / dt)))):
        st, u, _ = solver.step(dt, st)
        out.append(u.copy())
    return np.array(out), st


def _order(err_fn, dt, T):
    """(err(dt), err(dt/2), measured order) -- order is measured, not assumed."""
    e1, e2 = err_fn(dt, T), err_fn(dt / 2.0, T)
    return e1, e2, float(np.log2(e1 / e2))


# --------------------------------------------------------------------------
# Accuracy gates A-D: MNASolver against closed forms.
# --------------------------------------------------------------------------


def test_divider_reaches_the_exact_dc_operating_point():
    """Gate A: 1 V across two equal resistors settles at 0.5 V exactly.

    The resistive part of the MNA matrix is exact, so a single step of either
    scheme must land on the DC operating point with no scheme error at all --
    any residue here would mean the conductance stamp is wrong.
    """
    net = CircuitNetwork(
        (
            Branch("V", (1, 0), 1.0),
            Branch("R", (1, 2), 1e3),
            Branch("R", (2, 0), 1e3),
        ),
        3,
    )
    us, _ = _run(net, 1e-7, 1e-7)
    err = abs(us[-1][2] - 0.5)
    assert _close(us[-1][1], 1.0), f"driven node u1={us[-1][1]:.16g}"
    assert _close(us[-1][2], 0.5), f"divider node u2={us[-1][2]:.16g}, err={err:.3e}"


def test_rc_charging_matches_the_closed_form():
    """Gate B: R-C charge-up against ``1 - exp(-t/RC)``, first-order error.

    Measured: err(dt=5e-8) = 9.010e-03, err(dt/2) = 4.551e-03, order 0.985.
    """
    R, C = 1e3, 1e-9
    net = CircuitNetwork(
        (
            Branch("V", (1, 0), 1.0),
            Branch("R", (1, 2), R),
            Branch("C", (2, 0), C),
        ),
        3,
    )

    def err_fn(dt, T):
        us, _ = _run(net, dt, T)
        t = np.arange(1, len(us) + 1) * dt
        return float(np.max(np.abs(us[:, 2] - (1 - np.exp(-t / (R * C))))))

    e1, e2, p = _order(err_fn, 5e-8, 5e-6)
    assert e1 < 1e-2, f"RC err(dt=5e-8)={e1:.3e}"
    assert 0.9 < p < 1.1, f"RC measured order={p:.3f} (err {e1:.3e} -> {e2:.3e})"


def test_rl_current_matches_the_closed_form():
    """Gate C: R-L current rise against ``(1/R)(1 - exp(-Rt/L))``.

    The inductor current is read from the branch vector, not the node
    voltages, so this also pins the branch ordering of ``MNASolver.step``.
    Measured: err(dt=5e-8) = 9.010e-06, err(dt/2) = 4.551e-06, order 0.985.
    """
    R, L = 1e3, 1e-3
    net = CircuitNetwork(
        (
            Branch("V", (1, 0), 1.0),
            Branch("R", (1, 2), R),
            Branch("L", (2, 0), L),
        ),
        3,
    )

    def err_fn(dt, T):
        solver = MNASolver(net)
        st = solver.initial_state()
        err = 0.0
        for k in range(max(1, int(round(T / dt)))):
            st, _, cur = solver.step(dt, st)
            ref = (1.0 / R) * (1 - np.exp(-R * (k + 1) * dt / L))
            err = max(err, abs(cur[2] - ref))
        return float(err)

    e1, e2, p = _order(err_fn, 5e-8, 5e-6)
    assert e1 < 1e-5, f"RL err(dt=5e-8)={e1:.3e}"
    assert 0.9 < p < 1.1, f"RL measured order={p:.3f} (err {e1:.3e} -> {e2:.3e})"


def test_lc_tank_rings_at_the_analytic_frequency():
    """Gate D: undriven C||L from ``u = [0, 1]`` against ``cos(w0 t)``.

    Backward Euler damps the tank (the amplitude decays), so the error is large
    and the measured order is below one; the gate therefore pins the measured
    0.822 rather than pretending to second order.  A wrong L or C stamp shows
    up as a frequency error, which is far outside this bound.
    """
    L, C = 1e-6, 1e-9
    w0 = 1.0 / np.sqrt(L * C)
    net = CircuitNetwork((Branch("C", (1, 0), C), Branch("L", (1, 0), L)), 2)

    def err_fn(dt, T):
        us, _ = _run(net, dt, T, u0=np.array([0.0, 1.0]))
        t = np.arange(1, len(us) + 1) * dt
        return float(np.max(np.abs(us[:, 1] - np.cos(w0 * t))))

    e1, e2, p = _order(err_fn, 5e-9, 2e-7)
    assert _close(w0, 1.0 / np.sqrt(1e-6 * 1e-9)), f"w0={w0:.6e}"
    assert e1 < 0.5, f"LC err(dt=5e-9)={e1:.3e} at w0={w0:.4e}"
    assert 0.7 < p < 0.95, f"LC measured order={p:.3f} (err {e1:.3e} -> {e2:.3e})"


# --------------------------------------------------------------------------
# Energy-balance helpers E-K.
# --------------------------------------------------------------------------


def _terminal_current(net, cur, nd):
    """Net current leaving node ``nd`` (a -> b sign convention, ground = 0)."""
    tot = 0.0
    for k, br in enumerate(net.branches):
        a, c = br.nodes
        if a == nd:
            tot += cur[k]
        if c == nd:
            tot -= cur[k]
    return tot


def _dc_init(net, port, e0):
    """A consistent t=0 state: terminals held at ``L.T e0``, L shorted, C open.

    ``SpicePort.initial_state`` alone is not enough for the balance gates: the
    residual is a *difference* of energies, so the first step must start from a
    state that already satisfies the DC constraints of the network.  Otherwise
    step 1 carries the startup transient and the balance is dominated by it.
    """
    n, n_t = net.n_nodes, port.n_terminals
    u = np.zeros(n)
    u[1:n_t + 1] = port.voltage(np.asarray(e0, float))
    free = list(range(n_t + 1, n))
    lb = list(net.indices("L"))
    pos = {nd: i for i, nd in enumerate(free)}
    lp = {k: len(free) + j for j, k in enumerate(lb)}
    m = len(free) + len(lb)
    x = np.zeros(0)
    if m:
        A = np.zeros((m, m))
        rhs = np.zeros(m)
        for nd, ri in pos.items():
            for br in net.branches:
                a, c = br.nodes
                if br.kind == "R":
                    for me, other in ((a, c), (c, a)):
                        if me == nd:
                            g = 1.0 / br.value
                            A[ri, ri] += g
                            if other in pos:
                                A[ri, pos[other]] -= g
                            else:
                                rhs[ri] += g * u[other]
                elif br.kind == "L":
                    if a == nd:
                        A[ri, lp[net.branches.index(br)]] += 1.0
                    elif c == nd:
                        A[ri, lp[net.branches.index(br)]] -= 1.0
        for k, j in lp.items():
            a, c = net.branches[k].nodes
            for node, sg in ((a, 1.0), (c, -1.0)):
                if node in pos:
                    A[j, pos[node]] += sg
                else:
                    rhs[j] -= sg * u[node]
        x = np.linalg.solve(A, rhs)
        for nd, i in pos.items():
            u[nd] = x[i]
    cur = np.zeros(net.n_branches)
    for k, br in enumerate(net.branches):
        a, c = br.nodes
        if br.kind == "R":
            cur[k] = (u[a] - u[c]) / br.value
        elif br.kind == "L":
            cur[k] = x[lp[k]]
    ip = np.array([_terminal_current(net, cur, m + 1) for m in range(n_t)])
    return SpiceState(net, u=u, i_branch=cur, i=ip, v=port.voltage(np.asarray(e0, float)))


def _u_f(w, m_eps, e):
    """``U_f = (1/2) sum_k w_k m_k e_k^2`` with ``w = diag(W_E)``.

    ``emfit.spice`` carries this formula in its module docstring but exports no
    callable for it, so the test file spells it once here.  It is the module's
    own statement of the coupled field energy, not a new derivation.
    """
    e = np.asarray(e, float)
    return 0.5 * float(np.sum(w * m_eps * e * e))


def _coupled(net, port, e0, dt, nsteps):
    """Step the coupled port+network and return per-step balance rows.

    Columns: (dU_f, dU_C, dU_L, joule, residual, |residual|/sum|terms|).
    The joule term is the trapezoidal form ``(dt/4) R s^2`` with ``s = i' + i``.
    """
    sp = SpicePort(port, M_EPS, network=net)
    st = _dc_init(net, port, e0)
    e = np.array(e0, float)
    w = np.diag(WE)
    iC = list(net.indices("C"))
    iL = list(net.indices("L"))
    rows = []
    for _ in range(nsteps):
        eo, so = e.copy(), st
        e, _, st = sp.step(e, None, dt, st)
        dUf = _u_f(w, M_EPS, e) - _u_f(w, M_EPS, eo)
        jo = 0.0
        for k, br in enumerate(net.branches):
            if br.kind == "R":
                s = st.i_branch[k] + so.i_branch[k]
                jo += 0.25 * dt * br.value * s * s
        dUC = sum(
            0.5 * net.branches[k].value * (st.v_c[j] ** 2 - so.v_c[j] ** 2)
            for j, k in enumerate(iC)
        )
        dUL = sum(
            0.5 * net.branches[k].value * (st.i_l[j] ** 2 - so.i_l[j] ** 2)
            for j, k in enumerate(iL)
        )
        rs = dUf + dUC + dUL + jo
        sc = abs(dUf) + abs(dUC) + abs(dUL) + abs(jo) + 1e-300
        rows.append((dUf, dUC, dUL, jo, rs, abs(rs) / sc))
    return np.array(rows), e, st


def _scheme_resid(net, scheme, st0, dt, n):
    """Per-step balance under ``MNASolver`` itself (no port, no field term)."""
    solver = MNASolver(net, scheme=scheme)
    st = st0
    iC = list(net.indices("C"))
    iL = list(net.indices("L"))
    out = []
    for _ in range(n):
        vcp, ilp, cp = st.v_c.copy(), st.i_l.copy(), st.i_branch.copy()
        st, _, cur = solver.step(dt, st)
        dUC = sum(
            0.5 * net.branches[k].value * (st.v_c[j] ** 2 - vcp[j] ** 2)
            for j, k in enumerate(iC)
        )
        dUL = sum(
            0.5 * net.branches[k].value * (st.i_l[j] ** 2 - ilp[j] ** 2)
            for j, k in enumerate(iL)
        )
        jo = sum(
            0.25 * dt * br.value * (cur[k] + cp[k]) ** 2
            for k, br in enumerate(net.branches)
            if br.kind == "R"
        )
        r = dUC + dUL + jo
        out.append((r, abs(dUC) + abs(dUL) + abs(jo) + 1e-300))
    return np.array(out)


# --------------------------------------------------------------------------
# E-K: structure.
# --------------------------------------------------------------------------


def test_single_resistor_load_balances_to_roundoff():
    """Gate E: R = 50 across the port, six steps, diagonal ``W_E``.

    This is the operator's own case: a resistive load is the only one where the
    field energy ``U_f`` and the joule term are the whole story, so a residual
    here is the cleanest statement that ``SpicePort``'s back-reaction is the
    trapezoidal companion.  Measured max|resid| = 2.174e-28 (energies O(1e-12)).
    """
    net = CircuitNetwork((Branch("R", (1, 0), 50.0),), 2)
    rows, _, _ = _coupled(net, TerminalPort(LM, WE), E0, 1e-10, 6)
    worst = float(np.max(np.abs(rows[:, 4])))
    assert worst <= 1e-24, f"max|resid|={worst:.3e} over {len(rows)} steps"


def test_r_parallel_c_load_balances_to_roundoff():
    """Gate F: C||R at the terminal, where a static field does pump charge.

    A *series* R-C to ground is DC-blocked -- with a static field and a
    consistent t=0 state every term is identically 0.0, which gates nothing --
    so the capacitor is exercised here in parallel with the resistor instead.
    Measured max|resid| = 1.041e-25.
    """
    net = CircuitNetwork(
        (Branch("C", (1, 0), 1e-9), Branch("R", (1, 0), 50.0)),
        2,
    )
    rows, _, _ = _coupled(net, TerminalPort(LM, WE), E0, 1e-10, 4)
    worst = float(np.max(np.abs(rows[:, 4])))
    assert worst <= 1e-24, f"max|resid|={worst:.3e} over {len(rows)} steps"


def test_rl_load_balances_to_roundoff():
    """Gate G: series R-L to ground (R: 1-2, L: 2-0), so ``dU_L`` is live.

    Measured max|resid| = 5.756e-27.
    """
    net = CircuitNetwork(
        (Branch("R", (1, 2), 50.0), Branch("L", (2, 0), 1e-6)),
        3,
    )
    rows, _, _ = _coupled(net, TerminalPort(LM, WE), E0, 1e-10, 4)
    worst = float(np.max(np.abs(rows[:, 4])))
    assert worst <= 1e-24, f"max|resid|={worst:.3e} over {len(rows)} steps"


def test_spice_port_reproduces_step_rlc_on_a_series_rlc():
    """Gate H: ``SpicePort`` vs ``emfit.terminations.step_rlc``, same load.

    Both are supposed to implement one and the same trapezoidal coupled step
    (R: 1-2, L: 2-3, C: 3-0), so their fields and port quantities must agree to
    roundoff over eight steps.  Measured: max|de| = 6.661e-16,
    max|di| = 2.765e-18, max|dv| = 1.110e-15.
    """
    R, L, C = 50.0, 1e-9, 1e-12
    net = CircuitNetwork(
        (
            Branch("R", (1, 2), R),
            Branch("L", (2, 3), L),
            Branch("C", (3, 0), C),
        ),
        4,
    )
    port = TerminalPort(LM, WE)
    sp = SpicePort(port, M_EPS, network=net)
    ss = sp.initial_state()
    rs = RLCState(port, M_EPS)
    dt = 1e-10
    a = E0.copy()
    b = E0.copy()
    de = di = dv = 0.0
    for _ in range(8):
        a, _, ss = sp.step(a, None, dt, ss)
        b, _, rs = step_rlc(b, None, dt, R, L, C, rs)
        de = max(de, float(np.max(np.abs(a - b))))
        di = max(di, float(np.max(np.abs(ss.i - rs.i))))
        dv = max(dv, float(np.max(np.abs(ss.v - rs.v))))
    assert de <= 1e-14, f"max|de|={de:.3e}"
    assert di <= 1e-14, f"max|di|={di:.3e}"
    assert dv <= 1e-14, f"max|dv|={dv:.3e}"


def test_non_diagonal_we_is_a_documented_limitation_not_a_gate():
    """Gate I: a full ``W_E`` does NOT close the balance, and the test says so.

    ``Q = W_E diag(m_eps)`` is non-symmetric for ``W_E = [[1.3, 0.2],[0.2, 0.7]]``,
    so no symmetric quadratic form has its gradient as the port's back-reaction:
    ``U_f`` above is bookkeeping only.  Measured max|resid| = 1.014e-13, i.e.
    eleven orders above the diagonal cases and far above roundoff -- this gate
    pins the limitation so that a future "fix" cannot quietly change it into a
    silent, unmeasured claim.
    """
    net = CircuitNetwork((Branch("R", (1, 0), 50.0),), 2)
    rows, _, _ = _coupled(net, TerminalPort(LM, W_EN), E0, 1e-10, 4)
    worst = float(np.max(np.abs(rows[:, 4])))
    assert worst > 1e-15, f"max|resid|={worst:.3e} -- non-diagonal W_E unexpectedly balanced"


def test_trapezoidal_closes_the_balance_where_backward_euler_does_not():
    """Gate J: same circuits, same functional, both schemes of ``MNASolver``.

    The trapezoidal companion is ``MNASolver(scheme="trapezoidal")``; the
    default is backward Euler.  From a consistent t=0 state the trapezoidal
    residual is at roundoff (measured 1.050e-25 on R-C, 1.333e-19 on R-L) while
    backward Euler leaves a real defect (1.994e-15, 1.250e-14).  Halving dt cuts
    the backward-Euler residual by 3.994x (R-C) and 4.000x (R-L): a ratio of
    four means order 2.00 in dt, i.e. a one-step truncation error on an O(dt)
    quantity -- the scheme's order, NOT first order overall, and not roundoff
    either.  That ratio is measured here rather than asserted in prose.
    """
    g_rc = CircuitNetwork((Branch("C", (1, 0), 1e-9), Branch("R", (1, 0), 50.0)), 2)
    g_rl = CircuitNetwork((Branch("L", (1, 0), 1e-3), Branch("R", (1, 0), 50.0)), 2)
    starts = {
        "R-C": (
            g_rc,
            lambda: SpiceState(
                g_rc, u=np.array([0.0, 1.0]), i_branch=np.array([-1 / 50.0, 1 / 50.0])
            ),
        ),
        "R-L": (
            g_rl,
            lambda: SpiceState(
                g_rl, u=np.array([0.0, -50.0]), i_branch=np.array([1.0, -1.0])
            ),
        ),
    }

    worst = {}
    for name, (net, mk) in starts.items():
        trap = float(np.max(np.abs(_scheme_resid(net, "trapezoidal", mk(), 1e-10, 4)[:, 0])))
        be = float(np.max(np.abs(_scheme_resid(net, "backward_euler", mk(), 1e-10, 4)[:, 0])))
        worst[name] = (trap, be)
        assert trap < 1e-16, f"{name}: trapezoidal max|resid|={trap:.3e}"
        assert be > 1e-16, f"{name}: backward Euler max|resid|={be:.3e} (expected a defect)"

    # Order of the backward-Euler defect: dt -> dt/2, steps doubled.
    for name, (net, mk) in starts.items():
        m1 = float(np.max(np.abs(_scheme_resid(net, "backward_euler", mk(), 1e-10, 4)[:, 0])))
        m2 = float(np.max(np.abs(_scheme_resid(net, "backward_euler", mk(), 5e-11, 8)[:, 0])))
        ratio = m1 / m2
        assert 3.5 < ratio < 4.5, (
            f"{name}: BE max|resid| {m1:.3e} -> {m2:.3e}, ratio={ratio:.3f} "
            f"(order {np.log2(ratio):.2f})"
        )


def test_stepping_leaves_the_input_state_and_field_untouched():
    """Gate K: ``SpicePort.step`` is pure in its state and in ``e``.

    Two steps from one state must give bitwise identical results (no hidden
    mutation of the state, so the second step cannot be poisoned by the first),
    and neither the passed state's arrays nor the passed ``e`` may change.
    Measured: every difference is exactly 0.000e+00.
    """
    net = CircuitNetwork((Branch("R", (1, 0), 50.0),), 2)
    sp = SpicePort(TerminalPort(LM, WE), M_EPS, network=net)
    dt = 1e-10
    st0 = sp.initial_state()
    snap = (st0.u.copy(), st0.i_branch.copy(), st0.i.copy(), st0.v.copy())
    e0 = E0.copy()

    ea, _, sa = sp.step(e0, None, dt, st0)
    eb, _, sb = sp.step(e0, None, dt, st0)

    d_same = max(
        float(np.max(np.abs(ea - eb))),
        float(np.max(np.abs(sa.u - sb.u))),
        float(np.max(np.abs(sa.i - sb.i))),
        float(np.max(np.abs(sa.v - sb.v))),
    )
    d_state = max(
        float(np.max(np.abs(st0.u - snap[0]))),
        float(np.max(np.abs(st0.i_branch - snap[1]))),
        float(np.max(np.abs(st0.i - snap[2]))),
        float(np.max(np.abs(st0.v - snap[3]))),
    )
    d_input = float(np.max(np.abs(e0 - E0)))

    assert d_same == 0.0, f"two steps from one state differ by {d_same:.3e}"
    assert d_state == 0.0, f"input state was mutated by {d_state:.3e}"
    assert d_input == 0.0, f"input field was mutated by {d_input:.3e}"
