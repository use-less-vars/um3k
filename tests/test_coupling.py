"""The capacitive port is the lumped limit of the field, not a fitted bridge.

Claims proved here, in priority order:

T1  Uniformity: over one step every edge of the group drops by the SAME
    ``0.5*dt*(i^{n+1}+i^n)/C_group``, even when the group's edge capacitances
    differ 2.5:1 -- the equipotential group behaves as one capacitor.
T2  Field inertia: ``M = (dt/2) L.T diag(1/m_eps) W_E^{-1} L`` is exactly
    ``(dt/2)/C_group``, while equal-weight edges would give ``(dt/2)/C_series``
    (the discriminator between a parallel bundle and a series string).
T3  Energy balance with a shunt resistor: ``dU_field + (dt/4) R s^2 = 0``
    step by step, with ``s = i^{n+1}+i^n``.
T4  Open-circuit conservation: with a practically open load the port stores its
    field energy unchanged.
T5  Five hundred coupled steps stay finite and non-increasing in energy.
T6  Geometry: a one-cell gap gives ``C_group = eps0 A / d`` exactly.
T7  A resistive termination decays at the trapezoidal rate ``(1-x)/(1+x)``,
    ``x = dt/(2 R C_group)``.
T8  An inductive termination's eigenvalue phase is ``2 arctan(omega dt/2)``,
    ``omega = 1/sqrt(L C_group)``.
T9  A real 3D FIT stepper driven through the port measures ``C_group`` back out
    of the observed one-step voltage ratio.
"""

from __future__ import annotations

import numpy as np

from emfit.coupling import (
    capacitive_port,
    edge_capacitance,
    field_energy,
    gap_edges,
    group_capacitance,
    run_terminated,
    stored_energy,
)
from emfit.evolve import FITStepper
from emfit.grid import Grid
from emfit.materials import EPS0, material_matrices
from emfit.operators import CellComplex
from emfit.terminations import RLCState, TerminalPort, step_rlc

RTOL = 1e-14
ATOL = 0.0

H = 1e-3

# Unequal edge capacitances (2.5:1), so the weighting is tested with genuinely
# different c_e and not with a uniform grid's equal ones.  ``EDGES`` is just an
# index list; the coupling algebra needs no cell complex.
M_SYN = np.array([2.0e-13, 3.0e-13, 5.0e-13])
EDGES = np.array([0, 2, 1])


def _close(a, b, rtol=RTOL, atol=ATOL):
    return np.allclose(a, b, rtol=rtol, atol=atol)


def _box(nx=4, ny=3, nz=4, h=H):
    grid = Grid.uniform(nx, ny, nz, nx * h, ny * h, nz * h)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    return grid, cc, m_eps, m_mu


def _incidence(port):
    """Read the port's incidence matrix off its public ``voltage`` functional."""
    return np.column_stack(
        [port.voltage(np.eye(port.n_edges)[k]) for k in range(port.n_edges)]
    )


def _field_reactance(port, m_eps):
    """``L.T diag(1/m_eps) W_E^{-1} L`` by column, as ``step_rlc`` builds it."""
    out = np.empty((port.n_terminals, port.n_terminals))
    for m in range(port.n_terminals):
        unit = np.zeros(port.n_terminals)
        unit[m] = 1.0
        out[:, m] = port.voltage(port.current_density(unit) / m_eps)
    return out


# --------------------------------------------------------------------------- #
# T1 -- the equipotential group moves as one
# --------------------------------------------------------------------------- #
def test_T1_every_edge_of_the_group_drops_by_the_same_voltage():
    port = capacitive_port(M_SYN, EDGES)
    c = edge_capacitance(M_SYN, EDGES)
    total = c.sum()
    assert abs(c[0] / c[2] - 1.0) > 0.1  # a non-uniform group, on purpose

    dt, R = 1e-13, 50.0
    e0 = np.full(3, 0.4)
    state = RLCState(port, c, v=port.voltage(e0))
    e1, _, st1 = step_rlc(e0, None, dt, R, 0.0, 0.0, state)

    s = st1.i[0] + state.i[0]
    assert abs(s) > 0.0
    drop = -0.5 * dt * s / total
    # Identical drop on a thin edge and on a fat one: L = c_e/C_group is what
    # makes diag(1/m_eps) cancel, so the group stays equipotential.  Identical
    # to the last bit -- the tolerance below is only the cancellation in e1-e0.
    d = e1 - e0
    assert d[0] == d[1] == d[2]
    assert _close(d, np.full(3, drop), rtol=1e-12)
    assert _close(port.voltage(e1) - port.voltage(e0), np.array([drop]), rtol=1e-12)


# --------------------------------------------------------------------------- #
# T2 -- field inertia
# --------------------------------------------------------------------------- #
def test_T2_field_inertia_is_dt_over_two_group_capacitance():
    port = capacitive_port(M_SYN, EDGES)
    c = edge_capacitance(M_SYN, EDGES)
    total = c.sum()
    dt = 1e-15
    M = 0.5 * dt * _field_reactance(port, c)
    assert M.shape == (1, 1)
    assert _close(M, np.array([[0.5 * dt / total]]), rtol=1e-15)

    # The rejected alternative: unweighted edges put the group in SERIES.
    port_equal = TerminalPort(np.full((3, 1), 1.0 / 3.0), np.eye(3))
    M_equal = 0.5 * dt * _field_reactance(port_equal, c)
    assert _close(M_equal, np.array([[0.5 * dt * np.sum(1.0 / c) / 9.0]]))
    assert not _close(M_equal, M, rtol=1e-3)


# --------------------------------------------------------------------------- #
# T3 -- energy balance with a shunt resistor
# --------------------------------------------------------------------------- #
def test_T3_energy_balance_with_a_shunt_resistor():
    port = capacitive_port(M_SYN, EDGES)
    c = edge_capacitance(M_SYN, EDGES)
    dt, R = 1e-13, 50.0
    e = np.full(3, 1.0)
    state = RLCState(port, c, v=port.voltage(e))
    u0 = field_energy(c, e)
    assert _close(stored_energy(c, e, state, L=0.0, C=0.0), u0)

    dissipated = 0.0
    for _ in range(20):
        i_prev = state.i[0]
        e, _, state = step_rlc(e, None, dt, R, 0.0, 0.0, state)
        s = state.i[0] + i_prev
        dissipated += 0.25 * dt * R * s * s
        # every intermediate step balances too, not only the endpoint
        assert abs(field_energy(c, e) - u0 + dissipated) <= 1e-14 * u0
    assert 0.0 < field_energy(c, e) < u0  # the resistor did dissipate


# --------------------------------------------------------------------------- #
# T4 -- open circuit conserves
# --------------------------------------------------------------------------- #
def test_T4_open_circuit_conserves_the_field_energy():
    port = capacitive_port(M_SYN, EDGES)
    c = edge_capacitance(M_SYN, EDGES)
    dt, R_open = 1e-13, 1e18  # practically no path to ground
    e = np.full(3, 0.4)
    state = RLCState(port, c, v=port.voltage(e))
    u0 = field_energy(c, e)
    for _ in range(50):
        e, _, state = step_rlc(e, None, dt, R_open, 0.0, 0.0, state)
        assert abs(field_energy(c, e) - u0) <= 1e-12 * u0
    assert _close(e, np.full(3, 0.4), rtol=1e-12)


# --------------------------------------------------------------------------- #
# T5 -- five hundred coupled steps with a real field
# --------------------------------------------------------------------------- #
def test_T5_five_hundred_coupled_steps_stay_finite():
    grid, cc, m_eps, m_mu = _box()
    edge = int(cc.idx_ey(1, 1, 1))
    edges = np.array([edge])
    port = capacitive_port(m_eps, edges)
    stepper = FITStepper(cc, m_eps, m_mu, dt=1e-13)
    stepper.e[:] = 0.0
    stepper.h[:] = 0.0
    stepper.e[edge] = 1.0

    out = run_terminated(stepper, port, edges, R=50.0, nsteps=500)
    for key in ("v", "i", "e", "field_energy"):
        assert np.all(np.isfinite(out[key])), key
    assert out["v"].size == 501
    assert out["e"].shape == (501, 1)
    assert np.all(out["field_energy"] >= 0.0)
    assert out["field_energy"][-1] <= out["field_energy"][0] * (1.0 + 1e-9)
    assert isinstance(out["state"], RLCState)


# --------------------------------------------------------------------------- #
# T6 -- geometry
# --------------------------------------------------------------------------- #
def test_T6_one_cell_gap_capacitance_is_eps_area_over_length():
    grid, cc, m_eps, _ = _box()
    # An INTERIOR edge: the dual face is whole, A = dx*dz = h^2, d = dy = h.
    edges = gap_edges(cc, ix=1, j0=0, j1=1, k0=1, k1=2)
    assert edges.shape == (1,)
    c = group_capacitance(m_eps, edges)
    assert _close(c, EPS0 * (H * H) / H)
    assert _close(c, EPS0 * H, rtol=1e-15)

    # An equipotential group charges in parallel: the sum, not the series value.
    edges2 = gap_edges(cc, ix=1, j0=0, j1=1, k0=1, k1=3)
    assert _close(edge_capacitance(m_eps, edges2), np.full(2, EPS0 * H), rtol=1e-15)
    assert _close(group_capacitance(m_eps, edges2), 2 * EPS0 * H, rtol=1e-15)


# --------------------------------------------------------------------------- #
# T7 -- resistive termination
# --------------------------------------------------------------------------- #
def test_T7_resistive_termination_decays_at_the_trapezoidal_rate():
    port = capacitive_port(M_SYN, EDGES)
    c = edge_capacitance(M_SYN, EDGES)
    total = c.sum()
    R, dt, V = 50.0, 1e-13, 1.0
    x = dt / (2.0 * R * total)
    r = (1.0 - x) / (1.0 + x)

    e = np.full(3, V)
    state = RLCState(port, c, v=port.voltage(e))
    for n in range(1, 6):
        e, _, state = step_rlc(e, None, dt, R, 0.0, 0.0, state)
        assert _close(port.voltage(e)[0], V * r**n, rtol=1e-13)

    x_meas = (1.0 - r) / (1.0 + r)
    assert _close(dt / (2.0 * R * x_meas), total, rtol=1e-13)


# --------------------------------------------------------------------------- #
# T8 -- inductive termination
# --------------------------------------------------------------------------- #
def test_T8_inductive_termination_phase_is_the_warped_frequency():
    port = capacitive_port(M_SYN, EDGES)
    c = edge_capacitance(M_SYN, EDGES)
    total = c.sum()
    L_s = 4e-9
    omega = 1.0 / np.sqrt(L_s * total)
    dt = 0.5 / omega  # the warping is a 2% effect here, not a rounding error
    theta = 2.0 * np.arctan(0.5 * omega * dt)

    def one_step(i0, v0):
        state = RLCState(port, c, i=np.array([i0]), v=np.array([v0]))
        e1, _, st1 = step_rlc(np.full(3, v0), None, dt, 0.0, L_s, 0.0, state)
        return np.array([st1.i[0], port.voltage(e1)[0]])

    A = np.column_stack([one_step(1.0, 0.0), one_step(0.0, 1.0)])
    lam = np.linalg.eigvals(A)
    assert _close(np.abs(lam), np.ones(2), rtol=1e-12)
    phase = np.sort(np.abs(np.angle(lam)))
    assert _close(phase, np.array([theta, theta]), rtol=1e-10)
    assert not _close(phase[0], omega * dt, rtol=1e-3)


# --------------------------------------------------------------------------- #
# T9 -- the driver on a real 3D field
# --------------------------------------------------------------------------- #
def test_T9_field_driver_measures_the_group_capacitance():
    grid, cc, m_eps, m_mu = _box()
    edge = int(cc.idx_ey(1, 1, 1))
    edges = np.array([edge])
    port = capacitive_port(m_eps, edges)
    total = group_capacitance(m_eps, edges)

    dt, R, V = 1e-13, 50.0, 1.0

    def fresh():
        st = FITStepper(cc, m_eps, m_mu, dt=dt)
        st.e[:] = 0.0
        st.h[:] = 0.0
        st.e[edge] = V
        return st

    out = run_terminated(fresh(), port, edges, R=R, nsteps=1)
    # The explicit field step advances h before e, so the field the driver sees
    # at step 1 is not e0: measure it with the very same no-op advance.
    free = fresh()
    free.step()
    v_star = port.voltage(np.array(free.e)[edges])[0]
    assert abs(v_star - V) > 1e-3 * V

    # Trapezoid over the branch: v1*(1+x) = v_star - x*v0, x = dt/(2 R C_group),
    # because the resistor current is evaluated at both voltage levels.
    x = dt / (2.0 * R * total)
    v0, v1 = out["v"][0], out["v"][1]
    assert _close(v0, V)
    assert _close(v1, (v_star - x * v0) / (1.0 + x), rtol=1e-12)

    # ... and the capacitance measured back out of that pair is C_group.
    x_meas = (v_star - v1) / (v1 + v0)
    assert _close(dt / (2.0 * R * x_meas), total, rtol=1e-12)

    # Accessor-agreement check only, NOT acceptance evidence: ``e^T j == v^T i``
    # is a TAUTOLOGY for any invertible W_E, because both sides are the same
    # quadratic form written through two views of one operator.
    for n in range(out["v"].size):
        e_n = out["e"][n]
        i_n = np.array([out["i"][n]])
        assert _close(
            port.voltage(e_n) @ i_n, float(np.dot(e_n, port.current_density(i_n)))
        )
