"""Regression tests for the first-order Mur absorbing boundary.

The boundary update is::

    E_tan^{n+1}(0) = E_tan^n(1) + K * ( E_tan^{n+1}(1) - E_tan^n(0) )

with **both** history terms at time level ``n`` -- the field *before* the
leapfrog step that produced level ``n+1``.  That time level is not cosmetic:
handing :meth:`emfit.abc.Mur1Boundary.apply` the level ``n-1`` field instead
degrades the reflection of the duct used here from about ``-49.6 dB`` to about
``-9.0 dB``.  Two tests guard it -- the K -> 0 oracle
(``test_k_zero_limit_is_one_cell_translation``, where the update must collapse
to the exact one-cell translation ``E^{n+1}(0) = E^n(1)``) and the measured
reflection (``test_mur_absorbs_outgoing_pulse``).

Duct used by the two physical tests: the smallest configuration that still
gives an unambiguous measurement.  The probe sits 1 m from each wall, so the
incident pulse and the two echoes are separated by ~4 ns -- far more than the
~1.5 ns pulse width -- and the residual reflection sits at the
numerical-dispersion floor rather than at a window artefact::

    nx x ny x nz = 320 x 16 x 1 cells, lx x ly x lz = 2.4 x 0.64 x 0.04 m
    (dx = 7.5 mm, dy = 40 mm), CFL-limited dt = 2.394e-11 s, 900 steps.
    PEC on ymin/ymax/zmin/zmax makes this an exact 2-D TM_z problem: only EZ
    is non-zero, EX and EY are pinned to zero by those walls.
    TE10 profile sin(pi*y/ly) injected on EZ at x = 1.2 m, EZ probe at
    x = 0.9 m, 2 GHz tone burst (tau = 0.8 ns, t0 = 3 ns).
    Incident pulse at 4.12 ns, xmin echo at 9.96 ns, xmax echo at 11.94 ns.

One 900-step run of that duct costs about 0.25 s, so the two physical tests
(one Mur run, one PEC run, cached at module scope) keep the whole module near
1 s -- cheap enough that no coarser grid, which would trade a validated
measurement for a noisier one, is needed.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from emfit.abc import ALL_PLANES, Mur1Boundary
from emfit.evolve import FITStepper
from emfit.grid import CartesianGrid, Grid
from emfit.materials import C0, M_eps, M_mu
from emfit.operators import CellComplex

# ---------------------------------------------------------------------------
# physical test configuration (rationale in the module docstring)
# ---------------------------------------------------------------------------
_LX, _NX = 2.4, 320
_LY, _NY = 0.64, 16
_LZ, _NZ = 0.04, 1
_SRC_X, _PRB_X = 1.2, 0.9
_F0, _T0, _TAU = 2.0e9, 3.0e-9, 0.8e-9
_NSTEPS = 900
_SIDE_WALLS = ("ymin", "ymax", "zmin", "zmax")


def _waveform(t):
    """Gaussian-windowed 2 GHz tone burst."""
    s = (t - _T0) / _TAU
    return float(np.sin(2.0 * np.pi * _F0 * (t - _T0)) * np.exp(-s * s))


def _peak(trace, t, t_expected, half_window):
    """Largest ``|trace|`` inside ``t_expected +/- half_window``; returns (amp, t)."""
    sel = np.flatnonzero(np.abs(t - t_expected) <= half_window)
    assert sel.size > 0, "sampling window fell outside the trace"
    k = sel[int(np.argmax(np.abs(trace[sel])))]
    return float(abs(trace[k])), float(t[k])


def _run_duct(with_abc):
    """Launch one TE10 pulse and pick the incident pulse and the two echoes.

    With ``with_abc`` the x walls carry the Mur condition and the four side
    walls are PEC; without it all six walls are PEC (the control).  Returns a
    dict of amplitudes and timings, all lengths in metres/seconds.
    """
    grid = Grid.uniform(_NX, _NY, _NZ, lx=_LX, ly=_LY, lz=_LZ)
    cc = CellComplex(grid)
    walls = _SIDE_WALLS if with_abc else ALL_PLANES
    stepper = FITStepper(
        cc, M_eps(grid, cc, 1.0).diag, M_mu(grid, cc, 1.0).diag,
        pec=cc.pec_edge_mask(walls))
    mur = None
    if with_abc:
        mur = Mur1Boundary(grid, stepper.dt, cc=cc,
                           planes=("xmin", "xmax"), pec=stepper.pec_idx)

    dx = _LX / _NX
    i_src, i_prb = int(round(_SRC_X / dx)), int(round(_PRB_X / dx))
    profile = np.sin(np.pi * np.arange(_NY + 1) / _NY)
    src = np.array([cc.idx_ez(i_src, j, 0) for j in range(_NY + 1)], dtype=np.intp)
    probe = int(cc.idx_ez(i_prb, _NY // 2, 0))

    current = np.zeros_like(stepper.e)
    trace = np.empty(_NSTEPS)
    for n in range(_NSTEPS):
        current[:] = 0.0
        current[src] = profile * _waveform(stepper.time)
        e_prev = stepper.e.copy()          # field at time n, BEFORE the step
        stepper.step(current)              # e -> time n+1
        if mur is not None:
            mur.apply(stepper.e, e_prev)   # pre-step field = correct time level
        trace[n] = stepper.e[probe]

    t = stepper.dt * np.arange(1, _NSTEPS + 1)
    omega = 2.0 * np.pi * _F0
    v_ph = omega / np.sqrt((omega / C0) ** 2 - (np.pi / _LY) ** 2)
    t_inc = _T0 + (_SRC_X - _PRB_X) / v_ph
    t_near = _T0 + (_SRC_X + _PRB_X) / v_ph
    t_far = _T0 + (2.0 * _LX - _SRC_X - _PRB_X) / v_ph

    inc, _ = _peak(trace, t, t_inc, 1.0e-9)
    near, t_near_meas = _peak(trace, t, t_near, 1.2e-9)
    far, t_far_meas = _peak(trace, t, t_far, 1.2e-9)
    return {
        "inc": inc, "near": near, "far": far,
        "db_near": 20.0 * np.log10(near / inc),
        "db_far": 20.0 * np.log10(far / inc),
        "t_near": t_near_meas, "t_near_expected": t_near,
        "t_far": t_far_meas, "t_far_expected": t_far,
        "v_ph": v_ph,
    }


@pytest.fixture(scope="module")
def abc_run():
    """The duct with Mur on xmin/xmax (expensive: computed once)."""
    return _run_duct(True)


@pytest.fixture(scope="module")
def pec_run():
    """The same duct closed with PEC on all six walls (the control)."""
    return _run_duct(False)


# ---------------------------------------------------------------------------
# 1. structure: the neighbour is the parallel edge one cell inward
# ---------------------------------------------------------------------------
def _edge_table(cc):
    """``{global index: (component, i, j, k)}`` for every edge of ``cc``."""
    nx, ny, nz = cc.nx, cc.ny, cc.nz
    table = {}
    for i in range(nx):
        for j in range(ny + 1):
            for k in range(nz + 1):
                table[cc.idx_ex(i, j, k)] = ("x", i, j, k)
    for i in range(nx + 1):
        for j in range(ny):
            for k in range(nz + 1):
                table[cc.idx_ey(i, j, k)] = ("y", i, j, k)
    for i in range(nx + 1):
        for j in range(ny + 1):
            for k in range(nz):
                table[cc.idx_ez(i, j, k)] = ("z", i, j, k)
    return table


def test_neighbour_map_is_parallel_edge_one_cell_inward():
    """Every ``nbr`` is the parallel edge one cell inward on its own normal."""
    grid = CartesianGrid(5, 4, 3, lx=1.0, ly=1.0, lz=1.0)
    cc = CellComplex(grid)
    table = _edge_table(cc)
    assert len(table) == cc.n_edges

    mur = Mur1Boundary(grid, 1.0e-12, cc=cc)          # all six planes, no PEC
    assert [p.name for p in mur.planes] == list(ALL_PLANES)

    seen = []
    axis_pos = {"x": 0, "y": 1, "z": 2}
    for p in mur.planes:
        axis = axis_pos[p.name[0]]
        inward = +1 if p.name.endswith("min") else -1
        edge = 0 if p.name.endswith("min") else grid.shape[axis]
        for a, b in zip(p.idx, p.nbr):
            ca, ia, ja, ka = table[int(a)]
            cb, ib, jb, kb = table[int(b)]
            assert ca == cb, f"{p.name}: component changed {ca} -> {cb}"
            assert (ia, ja, ka)[axis] == edge, (
                f"{p.name}: idx {a} is not on the boundary layer")
            assert (ib, jb, kb)[axis] == edge + inward, (
                f"{p.name}: nbr {b} is not one cell inward")
            for t in range(3):
                if t != axis:
                    assert (ia, ja, ka)[t] == (ib, jb, kb)[t], (
                        f"{p.name}: transverse index moved {a} -> {b}")
        seen.append(p.idx)
        assert not np.any(p.idx == p.nbr), f"{p.name}: self-neighbour"

    # no edge claimed by two planes, and no PEC edge ever claimed
    claim = np.concatenate(seen)
    assert claim.size == np.unique(claim).size, "an edge is claimed twice"
    pec = cc.pec_edge_mask(_SIDE_WALLS)
    mur_pec = Mur1Boundary(grid, 1.0e-12, cc=cc, pec=pec)
    mapped = np.concatenate([p.idx for p in mur_pec.planes])
    assert mapped.size > 0
    assert not np.any(pec[mapped]), "a PEC-pinned edge was handed to the ABC"


# ---------------------------------------------------------------------------
# 2. the K -> 0 oracle: the update must be one-cell translation
# ---------------------------------------------------------------------------
def test_k_zero_limit_is_one_cell_translation():
    """With ``K = 0`` the update reduces *exactly* to E^{n+1}(0) = E^n(1).

    This is the sharpest guard against the history-level bug: the translation
    is only reproduced when ``e_prev`` is the field at time ``n`` (the level
    just before the step), and it holds to machine precision rather than to a
    dB threshold.
    """
    grid = CartesianGrid(5, 4, 3, lx=1.0, ly=1.0, lz=1.0)
    cc = CellComplex(grid)
    mur = Mur1Boundary(grid, 1.0e-12, cc=cc)

    # the stored coefficient is the Mur coefficient (c*dt - h)/(c*dt + h)
    for p in mur.planes:
        assert p.K == (C0 * mur.dt - p.h) / (C0 * mur.dt + p.h)

    rng = np.random.default_rng(20240)
    e_new = rng.normal(size=cc.n_edges)
    e_prev = rng.normal(size=cc.n_edges)

    zero_k = [dataclasses.replace(p, K=0.0) for p in mur.planes]
    mur.planes = zero_k
    e_there = e_new.copy()
    mur.apply(e_there, e_prev)
    for p in zero_k:
        np.testing.assert_allclose(e_there[p.idx], e_prev[p.nbr],
                                   rtol=1e-15, atol=0.0, err_msg=p.name)
        assert np.array_equal(e_there[p.idx], e_prev[p.nbr]), p.name

    # with the real coefficient the boundary layer must actually move, and by
    # an amount that scales with K -- i.e. the translation above is the K = 0
    # limit of one update, not a bypassed one
    mur.planes = [dataclasses.replace(p, K=(C0 * mur.dt - p.h) / (C0 * mur.dt + p.h))
                  for p in zero_k]
    e_k = e_new.copy()
    mur.apply(e_k, e_prev)
    moved = np.concatenate([np.abs(e_k[p.idx] - e_there[p.idx]) for p in mur.planes])
    assert moved.max() > 1.0e-3, "K had no effect at all"
    assert not np.allclose(e_k, e_there), "K had no effect at all"


# ---------------------------------------------------------------------------
# 3. physics: the ABC really absorbs
# ---------------------------------------------------------------------------
def test_mur_absorbs_outgoing_pulse(abc_run, pec_run):
    """Both echoes must be below -40 dB, and the incident pulse unaffected.

    Measured with the parameters in the module docstring: -49.6 dB (xmin) and
    -49.6 dB (xmax), against the continuum prediction of -49.2 dB for this
    duct's v_ph = 1.0069 c.  The -40 dB threshold leaves ~9 dB of margin while
    still failing loudly for the level-``n-1`` wiring bug (-9.0 dB).
    """
    inc, near, far = abc_run["inc"], abc_run["near"], abc_run["far"]
    assert inc > 0.0

    msg = (f"xmin echo {abc_run['db_near']:+.2f} dB, "
           f"xmax echo {abc_run['db_far']:+.2f} dB "
           f"(incident amplitude {inc:.3f}, theory -49.2 dB)")
    assert abc_run["db_near"] < -40.0, msg
    assert abc_run["db_far"] < -40.0, msg

    # the echoes must arrive where geometry says they should -- otherwise the
    # numbers above could come from some arbitrary wiggle of the trace
    assert abs(abc_run["t_near"] - abc_run["t_near_expected"]) < 3.0e-10
    assert abs(abc_run["t_far"] - abc_run["t_far_expected"]) < 3.0e-10
    assert near > 0.0 and far > 0.0

    # the ABC must not disturb the outgoing pulse: incident amplitude is
    # identical to the PEC-terminated control (measured ratio 1.000000)
    ratio = inc / pec_run["inc"]
    assert abs(ratio - 1.0) < 1.0e-6, f"incident amplitude ratio {ratio:.8f}"


# ---------------------------------------------------------------------------
# 4. the control that makes test 3 meaningful
# ---------------------------------------------------------------------------
def test_pec_control_reflects(pec_run):
    """PEC terminations must give near-total reflection (|R| ~ 1, 0 dB).

    Without this, a mis-placed probe could return a tiny signal in every
    window and pass the absorption test vacuously.  Measured here: +0.21 dB
    (xmin) and +0.22 dB (xmax).
    """
    assert pec_run["inc"] > 0.0
    msg = (f"PEC control reflects {pec_run['db_near']:+.2f} dB (xmin), "
           f"{pec_run['db_far']:+.2f} dB (xmax); expected ~0 dB")
    assert abs(pec_run["db_near"]) < 1.0, msg
    assert abs(pec_run["db_far"]) < 1.0, msg

    # the reflected amplitude really is comparable to the incident one, i.e.
    # the probe does see the echo (a dead probe would report a tiny "echo")
    assert pec_run["near"] > 0.5 * pec_run["inc"], msg
    assert pec_run["far"] > 0.5 * pec_run["inc"], msg
