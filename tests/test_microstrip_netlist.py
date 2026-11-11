"""``microstrip_wave(load_netlist=...)`` against the ``series_r`` stamp.

The bridge hangs a SPICE netlist on the ``E_x`` edges a ``series_r`` ``Load``
frees, so the two ways of putting the *same* element on that cut -- the
per-edge conductance ``1 / (n_edges * R)`` and an MNA solve of a 50 ohm
resistor across the same edges -- have to agree, and a nonlinear element on
the same cut has to stay bounded.  A 50 ohm resistor is the one netlist whose
answer is known independently, which is why it carries the equivalence check.

Every run here is short (``NSTEPS`` steps, the default mesh) and the module
fixtures share the three runs, so the file costs about ten seconds.
"""

import numpy as np
import pytest

from emfit.board import Load
from emfit.studies import microstrip_wave

NSTEPS = 120
LOAD_X = 15.2e-3
R_OHM = 50.0

LOAD = Load(position=LOAD_X, kind="series_r", value=R_OHM)
# A one-element netlist documents the cut's two nodes: ``1`` on the frees edges,
# ``0`` on the ground the far end of the element sits on.
RESISTOR = {"name": "r50", "nodes": ["1", "0"],
            "elements": [{"kind": "R", "name": "r1", "nodes": ["1", "0"],
                          "value": R_OHM}]}
DIODE = {"name": "d1", "nodes": ["1", "0"],
         "elements": [{"kind": "D", "name": "d1", "nodes": ["1", "0"],
                       "isat": 1e-14, "n": 1.0, "vt": 0.02585}]}

BASE = dict(nsteps=NSTEPS, loads=(LOAD,), z_eff_requested=True,
            load_edge_dump=True, sink=None, reference=None)


def _run(**kwargs):
    return microstrip_wave(**BASE, **kwargs)


@pytest.fixture(scope="module")
def sigma_run():
    """The ``Load`` stamp, with the per-step trace on."""
    return _run(load_trace=True)


@pytest.fixture(scope="module")
def resistor_run():
    """The same 50 ohm element, as a netlist."""
    return _run(load_netlist=RESISTOR, load_trace=True)


@pytest.fixture(scope="module")
def diode_run():
    """A nonlinear element on the same cut."""
    return _run(load_netlist=DIODE, load_trace=True)


def test_resistor_netlist_reproduces_the_sigma_stamp(sigma_run, resistor_run):
    """A 50 ohm netlist and a 50 ohm ``Load`` are the same element.

    The two paths free the same cut and differ only in where the element's
    current comes from, so the impedance seen at the cut and the whole V(t)
    record have to agree to well inside the discretisation error.  Measured on
    this mesh: ``z_eff`` to 4.4e-5 relative, the trace to 6.6e-4 of its peak.
    """
    assert sigma_run.load_edges is not None
    assert np.array_equal(sigma_run.load_edges, resistor_run.load_edges)

    dz = abs(sigma_run.z_eff - resistor_run.z_eff) / abs(sigma_run.z_eff)
    assert dz <= 1e-3, f"z_eff disagrees by {dz:.3e}"

    dv = np.abs(sigma_run.load_trace_v - resistor_run.load_trace_v).max()
    assert dv <= 2e-3 * np.abs(sigma_run.load_trace_v).max(), (
        f"V(t) disagrees by {dv:.3e} of {np.abs(sigma_run.load_trace_v).max():.3e}")

    di = np.abs(sigma_run.load_trace_i - resistor_run.load_trace_i).max()
    assert di <= 2e-3 * np.abs(sigma_run.load_trace_i).max(), (
        f"I(t) disagrees by {di:.3e} of {np.abs(sigma_run.load_trace_i).max():.3e}")

    dv_spectrum = np.abs(sigma_run.load_edge_v - resistor_run.load_edge_v).max()
    assert dv_spectrum <= 1e-2 * np.abs(sigma_run.load_edge_v).max()


def test_diode_netlist_stays_finite_and_clamped(sigma_run, diode_run):
    """The load-free field step plus the MNA solve does not run away.

    A diode is the case the conductance stamp cannot express at all, and the
    case where a mis-signed or mis-scaled port current shows up immediately as
    an exponential.  What is asserted is that it converged, that the cut's
    voltage is clamped far below the linear run's (measured 0.85 V against
    39.0 V), and that the element passes far more current per volt than 50 ohm
    would (measured 1.82 A against 0.017 A) -- which is the diode conducting.
    """
    v = diode_run.load_trace_v
    i = diode_run.load_trace_i
    assert np.all(np.isfinite(v)) and np.all(np.isfinite(i))

    clamped = np.abs(v).max()
    linear = np.abs(sigma_run.load_trace_v).max()
    assert clamped < 0.1 * linear, (
        f"diode cut reached {clamped:.3e} V against the linear {linear:.3e} V")

    # Nonlinear, not merely smaller: same volts, orders more amps.
    assert np.abs(i).max() > 10.0 * clamped / R_OHM

    # Settled rather than winding up: the last fifth of the record is within a
    # per cent of the whole record's peak, and nothing grew after it.
    tail = np.abs(v)[-NSTEPS // 5:].max()
    assert tail <= 1.05 * clamped
    assert tail >= 0.99 * clamped

    assert abs(diode_run.z_eff) < abs(sigma_run.z_eff)


def test_netlist_without_a_series_r_load_is_refused():
    """The netlist hangs on the cut a ``series_r`` load frees, so one is needed.

    Its ``value`` is unused -- the netlist supplies the element -- but the load
    is the only thing that names the column, so asking for the bridge without
    one has to say so instead of silently running load-free.
    """
    shunt = Load(position=LOAD_X, kind="shunt_c", value=0.25e-12)
    with pytest.raises(ValueError, match="series_r"):
        microstrip_wave(nsteps=8, loads=(shunt,), load_netlist=RESISTOR,
                        sink=None, reference=None)


def test_trace_is_off_by_default_and_moves_no_number(sigma_run):
    """``load_trace`` is purely additive: off it allocates nothing, on it
    changes nothing.

    The record of a run without the flag is compared field for field against
    the traced run's, so a trace that perturbed the time loop (a stray write to
    ``current``, a double field step) would fail here as well as in the
    equivalence test above.
    """
    plain = _run()
    assert plain.load_trace_v is None
    assert plain.load_trace_i is None

    assert sigma_run.load_trace_v.shape == (NSTEPS,)
    assert sigma_run.load_trace_i.shape == (NSTEPS,)
    assert np.all(np.isfinite(sigma_run.load_trace_v))
    assert np.all(np.isfinite(sigma_run.load_trace_i))

    assert plain.z_eff == sigma_run.z_eff
    assert plain.load_edge_v is not None
    assert np.array_equal(plain.load_edge_v, sigma_run.load_edge_v)
