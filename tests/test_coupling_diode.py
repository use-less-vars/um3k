"""Co-simulation of a :class:`~emfit.spice.CircuitNetwork` on a TEM line port.

Scope, stated up front because it is easy to over-read this file:

* What is tested is **lumped-port co-simulation on a parallel-plate TEM line**:
  an 80 x 1 x 4 cell vacuum box, PEC plates on the two ``y`` planes (all ``ex``
  and ``ez`` edges) plus a PEC back wall, driven by a current source on one
  transverse port plane; a :class:`~emfit.terminations.TerminalPort` on the
  opposite plane carries a SPICE netlist.
* It is **NOT a microstrip S-parameter validation**.  It does **NOT use
  ``microstrip_wave``**, it does **NOT terminate a real microstrip**, and it
  does **NOT move the E5 ledger row** at ``docs/design/EM_SOLVER_LEDGER.md:30``.
  No ``microstrip_wave``-to-circuit bridge exists and none is being built.
* The diode is the Task-2 Shockley model with **no junction capacitance**,
  verified against a root of its own equation -- it pins the solver, not a
  device.

The identity ``e^T j_port == v^T i_port`` is an algebraic tautology for any
invertible ``W_E`` and is **NOT evidence** of anything, so it is not asserted
anywhere in this file.

Geometry and drive
------------------
``h = 1 mm``, ``nx, ny, nz = 80, 1, 4`` (a one-cell gap, four cells wide, 80
cells long), ``dt = cfl_dt(grid)``.  Source on the 5 ``ey`` edges at ``i = 10``,
monitor on the 5 ``ey`` edges at ``i = 40``, port on the 5 ``ey`` edges at
``i = 80``.  The drive is ``V_peak * (s/tau**2) * exp(-s**2 / (2 tau**2))`` with
``s = n*dt - t0``, ``tau = 8*dt``, ``t0 = 20*dt`` -- a bipolar pulse whose
integral is exactly ``V_peak``.

``V_peak = 6 V``, not the 1 V first tried: at 1 V the monitor never exceeds
0.071 V, the junction stays in the ``1e-14 A`` reverse-leakage regime and the
diode trace is bit-identical to the open-line trace (measured), so nothing
about the diode can be tested there.  6 V puts the monitor peak at ~0.43 V, in
the junction's conduction knee.  The linear campaigns are amplitude
independent -- ``Gamma`` for the 63 ohm load is ``-0.2104`` at ``V_peak`` 1, 6
and 10 alike (measured) -- so raising the drive costs no generality.

``Gamma`` is the signed extremum of the monitor trace in the reflection window
(140..330 steps) over the signed extremum in the incident window (30..120),
per :func:`_gamma`.  That estimator was validated on a resistor sweep (1, 20,
47, 63, 94.25, 188, 400, 1e6 ohm) against ``(R - Z0)/(R + Z0)``: it crosses
zero at ``R = 94.25 ohm``, within 1% of the parallel-plate
``Z0 = sqrt(mu0/eps0)/nz = 94.18 ohm``.
"""

import numpy as np

from emfit.coupling import capacitive_port, field_energy, run_network
from emfit.evolve import FITStepper
from emfit.grid import Grid
from emfit.materials import MU0, EPS0, material_matrices
from emfit.netlist import parse_netlist
from emfit.operators import CellComplex
from emfit.spice import SpicePort

H = 1e-3
NX, NY, NZ = 80, 1, 4
NSTEPS = 500
V_PEAK = 6.0
I_SRC, I_MON = 10, 40

#: Parallel-plate characteristic impedance of this line, ohm: the gap is one
#: cell (``h``) and the width is ``NZ = 4`` cells (``4h``), so
#: ``Z0 = sqrt(mu0/eps0) * gap / width``.  188 ohm, the value this geometry is
#: sometimes quoted with, is ``sqrt(mu0/eps0)/2`` -- a two-cell-wide line.
Z0_LINE = float(np.sqrt(MU0 / EPS0) / NZ)
R_LOAD = 63.0


def _build():
    """The box, its PEC mask, and the three 5-edge ``ey`` planes of interest."""
    grid = Grid.uniform(NX, NY, NZ, NX * H, H, NZ * H)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    # Plates: the y = 0 and y = h planes, i.e. every tangential edge there.
    ex = [cc.idx_ex(i, j, k) for i in range(NX) for j in (0, 1) for k in range(NZ + 1)]
    ez = [cc.idx_ez(i, j, k) for i in range(NX + 1) for j in (0, 1) for k in range(NZ)]
    back = [cc.idx_ey(0, 0, k) for k in range(NZ + 1)]  # shorted far end
    pec = sorted(set(ex + ez + back))
    stepper = FITStepper(cc, m_eps, m_mu, dt=None, pec=pec)
    edges = np.array([cc.idx_ey(NX, 0, k) for k in range(NZ + 1)], dtype=int)
    src = np.array([cc.idx_ey(I_SRC, 0, k) for k in range(NZ + 1)], dtype=int)
    mon = np.array([cc.idx_ey(I_MON, 0, k) for k in range(NZ + 1)], dtype=int)
    return stepper, np.asarray(m_eps, dtype=float), edges, src, mon


_DT = _build()[0].dt


def _drive(v_peak):
    """``dV/dt`` source: ``v_peak * (s/tau**2) exp(-s**2/(2 tau**2))``."""
    tau = 8.0 * _DT
    t0 = 20.0 * _DT

    def source(n):
        s = n * _DT - t0
        return v_peak * (s / tau**2) * np.exp(-s**2 / (2.0 * tau**2))

    return source


def _advance_factory(stepper, m_eps, edges, src, cell):
    """The port-open field step, in the same in-place form ``run_network`` uses."""
    me = m_eps.ravel()

    def advance(e_local, h, _dt):
        stepper.e[edges] = np.asarray(e_local, dtype=float)
        stepper.h[:] = np.asarray(h, dtype=float)
        current = np.zeros(me.size)
        current[src] = me[src] * cell[0]
        stepper.step(current)
        return (
            np.array(stepper.e, dtype=float)[edges].copy(),
            np.array(stepper.h, dtype=float).copy(),
        )

    return advance


def _run(v_peak, network=None, nsteps=NSTEPS):
    """One campaign: ``(trace, energy, stepper, state)``.

    The interior monitor is the capacitance-weighted mean of ``e`` on the 5
    ``ey`` edges at ``i = 40`` -- the TEM potential of that plane -- sampled
    once per step.  This loop deliberately duplicates the ``advance`` closure
    inside :func:`emfit.coupling.run_network` (scatter the port slice in, inject
    the launch current, step, hand the port slice back out) for the sole reason
    that it also has to sample an interior plane, which ``run_network`` does not
    expose.  ``run_network`` itself is exercised separately, by
    :func:`test_run_network_field_energy_is_the_whole_grid`.
    """
    stepper, m_eps, edges, src, mon = _build()
    me = m_eps.ravel()
    c = me[mon]
    w = c / c.sum()
    drive = _drive(v_peak)
    trace = np.empty(nsteps + 1)
    energy = np.empty(nsteps + 1)
    trace[0] = float(w @ np.asarray(stepper.e, dtype=float)[mon])
    energy[0] = stepper.energy()

    if network is None:  # bare line, nothing on the port
        for n in range(nsteps):
            current = np.zeros(me.size)
            current[src] = me[src] * drive(n)
            stepper.step(current)
            trace[n + 1] = float(w @ np.asarray(stepper.e, dtype=float)[mon])
            energy[n + 1] = stepper.energy()
        return trace, energy, stepper, None

    port = capacitive_port(m_eps, edges)
    cell = [0.0]
    spice_port = SpicePort(
        port, m_eps[edges], network=network, advance=_advance_factory(stepper, m_eps, edges, src, cell)
    )
    e_local = np.array(stepper.e, dtype=float)[edges].copy()
    h = np.array(stepper.h, dtype=float).copy()
    state = spice_port.initial_state(v=port.voltage(e_local))
    for n in range(nsteps):
        cell[0] = float(drive(n))
        e_local, h, state = spice_port.step(e_local, h, _DT, state)
        stepper.e[edges] = np.asarray(e_local, dtype=float)
        trace[n + 1] = float(w @ np.asarray(stepper.e, dtype=float)[mon])
        energy[n + 1] = stepper.energy()
    return trace, energy, stepper, state


def _diode_network():
    return parse_netlist(
        {"nodes": ["0", "1"], "elements": [{"kind": "D", "name": "D1", "nodes": ["1", "0"]}]}
    ).network


def _resistor_network(value=R_LOAD):
    return parse_netlist(
        {
            "nodes": ["0", "1"],
            "elements": [{"kind": "R", "name": "R1", "nodes": ["1", "0"], "value": value}],
        }
    ).network


INCIDENT = slice(30, 120)
REFLECTED = slice(140, 330)


def _gamma(trace):
    """``Gamma`` from two window extrema of one monitor trace."""
    inc = trace[INCIDENT]
    ref = trace[REFLECTED]
    return float(ref[np.argmax(np.abs(ref))] / inc[np.argmax(np.abs(inc))])


_CACHE = {}


def _campaigns():
    """The five campaigns, run once and shared by every test below."""
    if not _CACHE:
        _CACHE["open"] = _run(V_PEAK)
        _CACHE["diode"] = _run(V_PEAK, _diode_network())
        _CACHE["res"] = _run(V_PEAK, _resistor_network())
        _CACHE["diode_rev"] = _run(-V_PEAK, _diode_network())
        _CACHE["res_rev"] = _run(-V_PEAK, _resistor_network())
        for key, run in _CACHE.items():
            peak = int(np.argmax(np.abs(run[0])))
            print(
                f"{key:10s} Gamma={_gamma(run[0]):+.4f} "
                f"peak={run[0][peak]:+.4f}@{peak} "
                f"U_end/U_max={run[1][-1] / run[1].max():.4f}"
            )
    return _CACHE


# --------------------------------------------------------------------------


def test_open_line_is_bounded():
    trace, energy, stepper, _ = _campaigns()["open"]
    assert np.all(np.isfinite(trace))
    assert np.all(np.isfinite(np.asarray(stepper.e)))
    assert np.all(np.isfinite(np.asarray(stepper.h)))
    # A PEC-bounded box with an open port is lossless: the total (E + H) energy
    # must return to where it started.  Measured U_end/U_max = 1.0000.
    ratio = energy[-1] / energy.max()
    assert 0.9 < ratio < 1.1, f"lossless line changed total energy: {ratio}"
    gamma_open = _gamma(trace)
    print(f"Gamma_OPEN = {gamma_open:+.4f}")
    # An open end reflects in phase and at nearly full amplitude.  Measured
    # +1.0483; the 5% excess over 1 is the estimator reading a neighbouring
    # lobe of a bipolar pulse, not gain.
    assert 0.9 < gamma_open < 1.2, f"open end did not reflect: Gamma={gamma_open}"


def test_run_network_field_energy_is_the_whole_grid():
    """``run_network``'s ``field_energy`` is the TOTAL grid energy, not the port's."""
    stepper, m_eps, edges, src, _ = _build()
    result = run_network(
        stepper,
        capacitive_port(m_eps, edges),
        edges,
        _diode_network(),
        nsteps=50,
        source=_drive(V_PEAK),
        source_edges=src,
    )
    for key, shape in (
        ("v", (51, 1)),
        ("i", (51, 1)),
        ("e", (51, 5)),
        ("field_energy", (51,)),
        ("u", (51, 2)),
        ("i_branch", (51, 1)),
    ):
        assert np.shape(result[key]) == shape, (key, np.shape(result[key]))
        assert np.all(np.isfinite(result[key])), key
    assert np.all(np.isfinite(result["state"].i_branch))
    assert result["field_energy"][0] == 0.0  # the field starts empty
    # The last entry must be the whole-grid value at the state the routine left
    # the stepper in.  While this tally was the port's 5 edges only, it
    # under-reported by ~7 orders of magnitude -- which is what this pins.
    total = field_energy(
        np.asarray(stepper.m_eps, dtype=float).ravel(),
        np.asarray(stepper.e, dtype=float).ravel(),
    )
    last = result["field_energy"][-1]
    port_only = field_energy(
        np.asarray(stepper.m_eps, dtype=float).ravel()[edges],
        np.asarray(stepper.e, dtype=float)[edges],
    )
    print(f"field_energy[-1] = {last:.6e}, whole grid = {total:.6e}, port only = {port_only:.6e}")
    assert last > 0.0
    assert abs(last - total) <= 1e-12 * total, (last, total)
    assert last > 1e3 * port_only, (last, port_only)


def test_diode_termination_is_bounded():
    trace, energy, stepper, state = _campaigns()["diode"]
    open_energy = _campaigns()["open"][1]
    assert np.all(np.isfinite(trace))
    assert np.all(np.isfinite(np.asarray(stepper.e)))
    assert np.all(np.isfinite(np.asarray(stepper.h)))
    assert np.all(np.isfinite(state.i_branch))
    assert np.all(np.isfinite(state.u))
    assert np.all(np.isfinite(state.i))
    # A passive load cannot put more energy into the box than the lossless line
    # reached.  Measured max = the open-line max to four digits.
    assert energy.max() <= 1.001 * open_energy.max(), (energy.max(), open_energy.max())
    assert energy.min() >= 0.0
    ratio = energy[-1] / energy.max()
    print(f"diode U_end/U_max = {ratio:.4f}")
    # Measured 0.6505: the junction dissipates about a third of the pulse.
    assert 0.2 < ratio < 0.95, ratio


def test_diode_reflection_is_inverted():
    gamma_diode = _gamma(_campaigns()["diode"][0])
    gamma_open = _gamma(_campaigns()["open"][0])
    print(f"Gamma_DIODE = {gamma_diode:+.4f}  Gamma_OPEN = {gamma_open:+.4f}")
    # The claim asserted is the SIGN: a forward-biased junction clamps the port
    # voltage and so reflects with inversion, while the open end reflects in
    # phase.  Measured -1.0219 against +1.0483.
    assert gamma_diode < 0.0 < gamma_open
    assert gamma_diode < -0.9 and gamma_open > 0.9
    # NOT asserted: "the diode suppresses the reflection".  |Gamma_DIODE| =
    # 1.0219 against |Gamma_OPEN| = 1.0483 is a 2.5% deficit, and it REVERSES at
    # V_peak = 10 V (|Gamma_DIODE| = 1.0979 > 1.0483), so it is an estimator
    # artifact, not physics: a clamp reflects with |Gamma| ~ 1 by construction
    # -- it forbids the voltage, it does not absorb the wave.  The absorbing
    # campaign is the resistor below.


def test_resistor_loads_the_line():
    gamma_res = _gamma(_campaigns()["res"][0])
    gamma_open = _gamma(_campaigns()["open"][0])
    predicted = (R_LOAD - Z0_LINE) / (R_LOAD + Z0_LINE)
    print(f"Gamma_RES({R_LOAD:g} ohm) = {gamma_res:+.4f}  predicted {predicted:+.4f}")
    assert abs(gamma_res) < abs(gamma_open) / 2.0  # measured 0.21 vs 1.05
    # Measured -0.2104 against -0.1984 from Z0 = sqrt(mu0/eps0)/4 = 94.18 ohm:
    # the 0.012 gap is 6% relative, so 0.03 absolute is a real margin.  (188
    # ohm would predict -0.50; that is a line two cells wide, not four.)
    assert abs(gamma_res - predicted) < 0.03, (gamma_res, predicted)
    energy = _campaigns()["res"][1]
    assert energy[-1] / energy.max() < 0.05  # measured 0.0018: it absorbed


def test_diode_is_asymmetric_resistor_is_symmetric():
    campaigns = _campaigns()
    res_gap = abs(_gamma(campaigns["res"][0]) - _gamma(campaigns["res_rev"][0]))
    diode_gap = abs(_gamma(campaigns["diode"][0]) - _gamma(campaigns["diode_rev"][0]))
    print(f"|dGamma| resistor = {res_gap:.3e}  diode = {diode_gap:.4f}")
    # A linear resistor has no polarity: negating the whole trace negates both
    # window extrema, so Gamma is unchanged -- measured difference 0.0 exactly.
    assert res_gap < 1e-9, res_gap
    # The diode is strongly polarised: measured -1.0219 forward against +1.0251
    # reverse (reverse bias is only the 1e-12 S gmin leak, i.e. an open).
    assert diode_gap > 1.0, diode_gap


def _diode_current_history():
    """The diode campaign again, keeping the whole ``i_branch`` history."""
    stepper, m_eps, edges, src, _ = _build()
    network = _diode_network()
    port = capacitive_port(m_eps, edges)
    drive = _drive(V_PEAK)
    cell = [0.0]
    spice_port = SpicePort(
        port, m_eps[edges], network=network, advance=_advance_factory(stepper, m_eps, edges, src, cell)
    )
    e_local = np.array(stepper.e, dtype=float)[edges].copy()
    h = np.array(stepper.h, dtype=float).copy()
    state = spice_port.initial_state(v=port.voltage(e_local))
    history = [state.i_branch.copy()]
    for n in range(NSTEPS):
        cell[0] = float(drive(n))
        e_local, h, state = spice_port.step(e_local, h, _DT, state)
        history.append(state.i_branch.copy())
    return np.array(history), network


def test_diode_current_is_unidirectional():
    history, network = _diode_current_history()
    (index,) = network.indices("D")
    current = history[:, index]
    print(f"diode current: min {current.min():+.4e} A, max {current.max():+.4e} A")
    assert np.all(np.isfinite(current))
    # It conducts: measured max +2.93e-3 A.  The reverse floor is the documented
    # gmin term, I = -isat + gmin*v, i.e. -1e-14 + 1e-12*(-0.85) = -8.5e-13 A --
    # measured -8.53e-13 A, so a -1e-11 A floor is 12x above it, not a widened
    # tolerance but the difference between "leaks" and "conducts backwards".
    assert current.max() > 0.0
    assert current.min() >= -1e-11, current.min()
    assert current.max() >= 1e-3, current.max()
