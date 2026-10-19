"""End-to-end wave-port test: a parallel-plate TEM line with probes on it.

Everything in :mod:`tests.test_ports` is arithmetic on made-up signals.  This
file does the opposite: it runs the solver on a real line and asks whether the
port primitives recover physics that was never put in by hand.

The device.  Two perfect-conductor plates at ``z = 0`` and ``z = LZ``, periodic
in ``y``, absorbing (a PML) at the two ends of ``x``, and a single ``EZ`` sheet
of edges at ``x = IX_SOURCE`` driven by a Ricker pulse centred on ``F0``.  That
launches the TEM mode of the parallel-plate guide, whose fields do not vary
with ``y`` or between the plates, so the analytic answers are exact rather than
approximate:

    beta = 2 pi F0 sqrt(eps_r) / c0        [rad/m]
    Z0   = ETA0 LZ / (LY sqrt(eps_r))      [ohm]  (voltage over plate current)

Probe voltages come from :func:`emfit.ports.column_path` -- the ``EZ`` stack
through the plates at one ``(x, y)`` -- and :func:`emfit.ports.probe_voltage`.
The plate current is the sum of the dual ``H`` unknowns on the top wall, which
is why nothing here needs a ``y``-directed primal-edge path.

What sets the grid.  ``DX`` is chosen so that a probe pair on the *air* line
lands exactly six cells apart and a pair on the ``eps_r = 4`` line exactly
three, both equal to :func:`emfit.ports.suggest_probe_spacing` of the
respective phase constant to machine precision (asserted in ``_run``).  So the
signal processing is not being asked to work near a degenerate spacing: it is
being asked to work at the spacing it recommends, with the grid doing the
rounding instead of the request.

Three configurations, one fixture each, about 90 ms of solver time each:

* ``air_run`` -- ``eps_r = 1`` throughout.  A matched line: ``S11`` should be
  zero and ``S21`` should be one.  Measured: ``|S11| = 3.6e-4`` (-68.8 dB),
  ``|S21| = 1.0000006``, phase error ``-0.095 deg``, passivity
  ``1.000001``.
* ``eps4_run`` -- ``eps_r = 4`` throughout.  Same claims, but every length
  and impedance is halved or quartered by the dielectric, so ``beta`` and
  ``Z0`` are tested against numbers that moved.  Measured: ``|S11| = 1.4e-3``
  (-56.9 dB), ``|Z0| = 37.6824`` against 37.6730 ohm (+0.025 %), phase error
  ``-0.839 deg``.
* ``step_run`` -- dielectric stepped from 1 to 4 at ``x = 38 DX``.  This is a
  real discontinuity, so the answer is not zero/one but the Fresnel
  amplitudes of two semi-infinite lines: ``S11 = -1/3``, ``S21 = 2/3``.
  Measured: ``|S11| = 0.33621``, ``|S21| = 0.66868``.

Normalisation, and why the step has no phase claim.  These ports carry a
*voltage*, not a power wave, so the two-port is not power-normalised and the
naive ``|S11|^2 + |S21|^2 = 1`` is wrong across an impedance change: the
measured sum is ``0.5602``, close to the exact ``5/9`` for a 1:4 step.  The
lossless claim that does hold is ``|S11|^2 + (Z1/Z2) |S21|^2 = 1`` with
``Z1/Z2 = sqrt(eps2/eps1) = 2`` for this step; the measured value is
``1.0073``.  The step test therefore asserts magnitudes only -- an ``S21``
phase would need the discontinuity to be de-embedded from a reference plane,
and being half a grid cell wrong about where the interface sits would show up
as tens of degrees of error in a quantity the solver is not actually wrong
about.

One library note, recorded here because this test works around it.  The
stepped permittivity is passed as a **per-edge array**, not as a callable:
``emfit.materials._centres`` shapes a profile with ``v.size``, which on a
periodic transverse axis is ``ny + 1`` while the edges only need ``ny``, so
``material_matrices(..., eps_r=callable)`` raises a broadcast error on this
geometry.  ``_eps_step`` below builds the array with the same convention the
material code uses (cell centres along ``x`` for ``EX`` edges, node values for
``EY``/``EZ``) so the interface sits exactly on an ``EZ`` node layer.

Timing note.  ``F0`` is deliberately not on a DFT bin (``F0 * T = 13.904``
bins), so every recovered phasor carries the same rectangular-window leakage
factor.  Every S-parameter here is a ratio of phasors of the same tone over the
same record, so the factor cancels; the absolute volts are consequently not
amplitudes and are never asserted.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.evolve import FITStepper, RickerSource, cfl_dt
from emfit.grid import Grid
from emfit.materials import C0, ETA0, material_matrices
from emfit.operators import CellComplex
from emfit.pml import PML
from emfit.ports import (
    DftAccumulator,
    column_path,
    read_touchstone,
    reflection,
    suggest_probe_spacing,
    travelling_waves,
    write_touchstone,
)

# ---------------------------------------------------------------------------
# the line
# ---------------------------------------------------------------------------
#: Drive frequency [Hz].
F0 = 5.0e9
#: Cells and cross-section [m].  Five cells across a periodic ``y`` is enough
#: for a mode with no ``y`` variation, and two cells between the plates
#: resolve the ``EZ`` stack exactly.
NX, NY, NZ = 80, 5, 2
LY, LZ = 5.0e-3, 1.0e-3
#: Recorder length and step.  The step comes from the CFL limit, the length
#: from wanting the pulse (and its tail) to fit: 2000 steps is 2.781 ns, and
#: the last 40 samples of the air run still move by only 4.7e-3 V against a
#: forward wave of 1.1e4 V.
N_STEPS = 2000

#: Phase constants of the two dielectrics [rad/m].
BETA1 = 2.0 * np.pi * F0 / C0
BETA2 = BETA1 * np.sqrt(4.0)
#: The recommended probe spacings, in metres: 7.494811 mm and 3.747406 mm.
D1 = suggest_probe_spacing(BETA1)
D2 = suggest_probe_spacing(BETA2)
#: Cell size [m], chosen so that D1 is 6 cells and D2 is 3 cells exactly.
DX = D1 / 6.0
LX = NX * DX
K1, K2 = 6, 3
#: Cell indices: source, the two stations, and the step.
IX_SOURCE, IX_A, IX_B, IX_STEP = 16, 28, 48, 38
#: Separation of the two stations [m], 24.9827 mm.
D_AB = (IX_B - IX_A) * DX


def _build():
    """The grid, its cell complex and the CFL time step."""
    g = Grid.uniform(NX, NY, NZ, LX, LY, LZ, origin=(0.0, 0.0, 0.0),
                     periodic=(False, True, False))
    return g, CellComplex(g), cfl_dt(g)


def _eps_step(g, cc, xs):
    """Edge-wise ``eps_r`` for a step from 1 to 4 at ``x = xs`` [m].

    Built as an explicit array because the callable route through
    :func:`emfit.materials.material_matrices` cannot be shaped on this
    geometry (see the module docstring).  The convention has to match the
    material code: ``EX`` edges sample the profile at cell centres, ``EY`` and
    ``EZ`` edges at nodes, so the interface falls on a face of ``EX`` and on a
    node of the transverse edges -- which is what makes one edge either wholly
    1 or wholly 4 and no edge a mixture.
    """
    xc = 0.5 * (g.x[:-1] + g.x[1:])
    blocks = []
    for axis, profile in (("x", xc), ("y", g.x), ("z", g.x)):
        # eps_r varies along x only, so the profile rides on axis 0 of every
        # edge_shape(axis) and is broadcast across the other two.
        values = np.broadcast_to(profile.reshape(-1, 1, 1),
                                 g.edge_shape(axis)).ravel()
        blocks.append(np.where(values >= xs, 4.0, 1.0))
    eps = np.concatenate(blocks)
    assert eps.size == cc.n_edges
    return eps


def _wrap(degrees):
    """Wrap an angle into ``(-180, 180]`` so phases compare without a jump."""
    return (degrees + 180.0) % 360.0 - 180.0


def _run(eps_r, k_a, k_b, beta_a, beta_b):
    """Drive the line once and return every number the tests assert on.

    ``eps_r`` is a scalar or a callable ``f(grid, cc) -> array``; ``k_a`` and
    ``k_b`` are the probe separations in cells at stations A and B, used with
    phase constants ``beta_a`` and ``beta_b`` (rad/m) for the two-probe split.

    Probe ``i`` of a station is the ``y = 0`` column; station A sits in the
    first medium and B in the second, so ``k_a``/``beta_a`` are the near-side
    pair and ``k_b``/``beta_b`` the far-side pair.  The plate current is taken
    at station A only.
    """
    g, cc, dt = _build()
    d_a, d_b = k_a * DX, k_b * DX
    # The grid is sized from D1, so the placed spacings are the recommended
    # ones exactly -- the port code is never tested off its own advice.
    assert abs(d_a - suggest_probe_spacing(beta_a)) < 1.0e-12
    assert abs(d_b - suggest_probe_spacing(beta_b)) < 1.0e-12

    if callable(eps_r):
        eps_r = eps_r(g, cc)
    m_eps, m_mu = material_matrices(g, cc, eps_r=eps_r)
    pec = cc.pec_edge_mask(walls=("zmin", "zmax"))
    pml = PML(g, thickness_cells=12, order=2, target=1.0e-4, axes=("x",), cc=cc)
    stepper = FITStepper(cc, m_eps, m_mu, dt=dt, pec=pec, pml=pml)

    # Voltage probe columns and the plate-current edge indices.  The current
    # sums the dual H unknowns on the top wall over the periodic y copies,
    # which is the total current per unit length in x -- a dual-face sum, not
    # an edge path.
    col_a1, col_a2 = column_path(cc, IX_A, 0), column_path(cc, IX_A + k_a, 0)
    col_b1, col_b2 = column_path(cc, IX_B, 0), column_path(cc, IX_B + k_b, 0)
    fy_at_a = np.array([cc.idx_fy(IX_A, j, NZ - 1) for j in range(cc.nyn)])
    source_edges = np.concatenate(
        [column_path(cc, IX_SOURCE, j) for j in range(cc.nyn)])
    source = RickerSource(cc.n_edges, source_edges, fmax=F0)

    acc = DftAccumulator([F0], dt)

    def record(state):
        e, h = state.e, state.h
        acc.add([float(e[col_a1].sum()), float(e[col_a2].sum()),
                 float(e[col_b1].sum()), float(e[col_b2].sum()),
                 float(h[fy_at_a].sum())], state.n)

    stepper.run(N_STEPS, source=source, callback=record)

    v_a1, v_a2, v_b1, v_b2, current = acc.spectrum[0]
    v_plus_a, v_minus_a = travelling_waves(v_a1, v_a2, d_a, beta_a)
    v_plus_b, v_minus_b = travelling_waves(v_b1, v_b2, d_b, beta_b)

    s11 = reflection(v_plus_a, v_minus_a)
    # Ratio of forward waves at the two reference planes, propagation included.
    ratio = v_plus_b / v_plus_a
    phase = float(np.degrees(np.angle(ratio)))
    eps_val = 4.0 if np.ndim(eps_r) else float(eps_r)
    return {
        "eps_r": eps_val,
        "dt": dt,
        "n_samples": acc.n_samples,
        "v_plus_a": complex(v_plus_a),
        "v_minus_a": complex(v_minus_a),
        "v_plus_b": complex(v_plus_b),
        "v_minus_b": complex(v_minus_b),
        "s11": complex(s11),
        "ratio": complex(ratio),
        "phase": phase,
        # analytic phase of the ratio for a uniform line: pure propagation
        "phase_analytic": _wrap(float(np.degrees(-beta_b * D_AB))),
        "phase_error": _wrap(phase - _wrap(float(np.degrees(-beta_b * D_AB)))),
        # voltage over plate current at station A [ohm], and its closed form
        "z0": float(np.abs(v_a1 / current)),
        "z0_analytic": float(ETA0 * LZ / (LY * np.sqrt(eps_val))),
        "z0_argument": float(np.degrees(np.angle(v_a1 / current))),
        "beta_b": beta_b,
    }


# ---------------------------------------------------------------------------
# the three runs (about 90 ms of solver each)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def air_run():
    """Air-filled line, probes 6 cells apart; ``S11`` should vanish."""
    return _run(1.0, K1, K1, BETA1, BETA1)


@pytest.fixture(scope="module")
def eps4_run():
    """Line filled with ``eps_r = 4``, probes 3 cells apart."""
    return _run(4.0, K2, K2, BETA2, BETA2)


@pytest.fixture(scope="module")
def step_run():
    """Dielectric stepped 1 -> 4 at ``x = 38 DX`` = 47.4671 mm.

    Station A is on the air side (6 cells, ``beta1``) and station B on the
    dielectric side (3 cells, ``beta2``), each pair at its own recommended
    spacing.
    """
    xs = IX_STEP * DX
    return _run(lambda g, cc: _eps_step(g, cc, xs), K1, K2, BETA1, BETA2)


# ---------------------------------------------------------------------------
# 1. the matched line
# ---------------------------------------------------------------------------
def test_air_line_is_matched(air_run):
    """A uniform air line reflects nothing and transmits everything.

    No absorber tuning, no de-embedding, no fitted correction: the two-probe
    split with ``beta = 2 pi F0 / c0`` has to give the whole answer itself.
    The residual is the PML and the discretisation, nothing else.

    Measured: ``S11 = 3.618e-4`` (-68.8 dB), ``|S21| = 1.000000583``,
    ``|S11|^2 + |S21|^2 = 1.000001``.  The floor asserted is -40 dB -- far
    above the measured value, because the point of the claim is "there is no
    reflection", not six digits of it.
    """
    s11_db = 20.0 * np.log10(abs(air_run["s11"]))
    assert s11_db < -40.0, f"|S11| = {s11_db:+.2f} dB, expected a matched line"
    assert abs(abs(air_run["ratio"]) - 1.0) < 1.0e-3, (
        f"|S21| = {abs(air_run['ratio']):.9f}, expected 1")
    assert air_run["n_samples"] == N_STEPS

    # The transmission phase is pure delay across D_AB = 24.9827 mm, which is
    # -150.0000 deg at 5 GHz in air.  Measured error -0.0953 deg.
    assert abs(air_run["phase_error"]) < 2.0, (
        f"S21 phase error {air_run['phase_error']:+.4f} deg")
    # Lossless: for equal impedances at both ports the naive sum is the right
    # one.  Measured 1.000001.
    energy = abs(air_run["s11"]) ** 2 + abs(air_run["ratio"]) ** 2
    assert abs(energy - 1.0) < 1.0e-2, f"|S11|^2 + |S21|^2 = {energy:.6f}"


# ---------------------------------------------------------------------------
# 2. the characteristic impedance
# ---------------------------------------------------------------------------
def test_characteristic_impedance(air_run, eps4_run):
    """``Z0 = |V / I|`` matches ``ETA0 LZ / (LY sqrt(eps_r))`` for both fills.

    ``V`` is the plate-to-plate voltage and ``I`` the total plate current, so
    their ratio is the line impedance in the voltage/current normalisation the
    port uses -- the same quantity an analytic TEM model would quote.  A
    factor-of-two slip anywhere (plates, ``y`` sum, ``sqrt(eps_r)``) moves the
    answer by 100 %, which is why the tolerance is 2 % and not 0.1 %.

    Measured: 75.3421 vs 75.3461 ohm in air (-0.005 %), 37.6824 vs 37.6730
    ohm in the dielectric (+0.025 %).  In both cases ``arg(V/I)`` sits near
    -180 deg (-174.998 and -171.234), i.e. current and voltage are in
    antiphase as a lumped element would not be: the residual angle is the
    discretisation of the ``H`` sampling half a cell away.
    """
    for run, label in ((air_run, "air"), (eps4_run, "eps_r=4")):
        z0, analytic = run["z0"], run["z0_analytic"]
        error = 100.0 * (z0 - analytic) / analytic
        assert abs(error) < 2.0, (
            f"Z0 ({label}): {z0:.4f} ohm against {analytic:.4f} ohm "
            f"({error:+.3f} %)")

    # The dielectric moves beta, so the same 20-cell offset is a different
    # electrical length: -300 deg raw, which wraps to +60.0000 deg.  Wrapping
    # both sides is essential; comparing unwrapped angles would report a
    # bogus 359 deg error.  Measured error -0.839 deg.
    assert abs(eps4_run["phase_error"]) < 2.0, (
        f"S21 phase error in eps_r=4: {eps4_run['phase_error']:+.4f} deg")


# ---------------------------------------------------------------------------
# 3. the dielectric step
# ---------------------------------------------------------------------------
def test_dielectric_step_gives_the_fresnel_amplitudes(step_run):
    """A 1 -> 4 step reflects ``-1/3`` and transmits ``2/3`` of the voltage.

    Two semi-infinite lines of impedance ``Z1`` and ``Z2`` meeting at a plane
    have ``S11 = (Z2 - Z1)/(Z2 + Z1) = -1/3`` and ``S21 = 2 Z2/(Z2 + Z1) =
    2/3`` for ``Z1/Z2 = 2``.  Both magnitudes are asserted with the same 3 %
    the discretisation earns on a jump that sits on one face.

    Measured: ``|S11| = 0.336207`` (-9.47 dB), ``|S21| = 0.668677``.

    The lossless check has to be impedance-weighted.  These ports carry
    voltages, not power waves, so the transmitted voltage carries only
    ``Z1/Z2 = sqrt(4) = 2`` times the power the naive sum assumes::

        |S11|^2 + (Z1/Z2) |S21|^2 = 1

    Measured 1.0073.  The naive sum is ``|S11|^2 + |S21|^2 = 0.5602``, against
    the exact ``5/9`` for this step -- asserted too, because a future change
    that quietly renormalised the port would push it to 1 and this test should
    notice.  No phase is asserted: that would need the discontinuity
    de-embedded from a reference plane.
    """
    s11 = abs(step_run["s11"])
    s21 = abs(step_run["ratio"])
    assert abs(s11 - 1.0 / 3.0) < 0.03 * (1.0 / 3.0), (
        f"|S11| = {s11:.6f}, expected 0.333333")
    assert abs(s21 - 2.0 / 3.0) < 0.03 * (2.0 / 3.0), (
        f"|S21| = {s21:.6f}, expected 0.666667")

    weighted = s11 ** 2 + 2.0 * s21 ** 2
    assert abs(weighted - 1.0) < 1.0e-2, (
        f"|S11|^2 + (Z1/Z2)|S21|^2 = {weighted:.6f}")
    naive = s11 ** 2 + s21 ** 2
    assert abs(naive - 5.0 / 9.0) < 1.0e-2, (
        f"|S11|^2 + |S21|^2 = {naive:.6f}, expected 5/9 for a voltage port")


# ---------------------------------------------------------------------------
# 4. carrying the result out of the run
# ---------------------------------------------------------------------------
def test_step_run_round_trips_through_touchstone(step_run, tmp_path):
    """The measured S-matrix survives a ``.s2p`` write and read.

    The step is reciprocal, so ``S12 = S21``; the port order on disk is input
    slowest, so ``S`` is assembled as ``[f, out, in]`` and the file has to
    hand back the same numbers.  This is the join between the physics above
    and the file format a downstream tool reads -- a transposed write would
    pass every test in section 3 and still produce a wrong file.

    Measured hardware: the transmitted phasor carries a +130.72 deg phase
    because it is not de-embedded, and magnitudes of 0.336207 / 0.668677.
    """
    freqs = np.array([F0])
    s = np.empty((1, 2, 2), dtype=complex)  # s[f, out, in]
    s[:, 0, 0] = step_run["s11"]
    s[:, 1, 0] = step_run["ratio"]
    s[:, 0, 1] = step_run["ratio"]  # reciprocal: an S12 = 0 here would pass
    # the write test and describe a different device
    s[:, 1, 1] = 0.0 + 0.0j  # no backward launch in this run, so not measured

    path = tmp_path / "step.s2p"
    write_touchstone(path, freqs, s)
    text = path.read_text().splitlines()
    assert text[0] == "# HZ S RI R 50"
    assert len(text) == 2

    f2, s2 = read_touchstone(path)
    assert np.allclose(f2, freqs, rtol=0.0, atol=1.0e-3)
    assert np.allclose(s2, s, rtol=0.0, atol=1.0e-9)
    # and the numbers that came back are the physics, not a coincidence
    assert abs(abs(s2[0, 0, 0]) - abs(step_run["s11"])) < 1.0e-12
    assert abs(abs(s2[0, 1, 0]) - abs(step_run["ratio"])) < 1.0e-12
    assert abs(s2[0, 0, 1] - s2[0, 1, 0]) < 1.0e-12  # reciprocal
