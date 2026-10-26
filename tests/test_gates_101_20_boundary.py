"""Boundary case of the T3 detection comparison in ``tools/gates_101_20.py``.

The defect these tests pin
--------------------------
``T3_ey_slot`` injects a break of size ``b`` into the ``plane_Ey`` slot and
asks whether the slot statistic

    ``|rho(b)/rho(1) - 1|``,   ``rho = sum conj(Ey)Hz / sum conj(Ez)Hy``

has reached the tolerance.  The break travels through the code as ``(1+b)`` in
double, so at ``b == tol`` the statistic does **not** come out exactly ``tol``:
1 ulp of 1.0 is 2.2e-16, which is 2.2e-11 *relative* at ``tol = 1e-5``, so the
statistic lands a few ulp either side of the threshold depending on the data.
The module's own measured curve records the shortfall as 3.8e-11 *below*
(see the ``T3_TOL`` comment).  A bare ``>= tol`` therefore reports exactly the
break the gate exists to catch as "not detected" -- the promise "the gate fires
on a break of size ``tol``" held only by luck of the rounding.

The fix is ``_DETECT_RTOL = 1e-9`` and ``_detected(statistic, tol)``, i.e.
detection is the half-open side ``statistic >= tol * (1 - _DETECT_RTOL)``.
``1e-9`` is 26x the measured 3.8e-11 shortfall, and at ``tol = 1e-5`` it moves
the threshold by 1e-14 -- four decades below the record's 1.1e-10
reproducibility floor -- so it reclassifies no real detection, it only makes
the boundary deterministic.

What is tested
--------------
``test_detected_*`` exercise the predicate directly at the three points that
matter: exactly ``tol`` (detected), the measured 3.8e-11 shortfall (detected),
and a genuine miss of 1e-6 / 1e-3 relative (not detected).

``test_slot_gate_detects_a_break_of_exactly_tol`` runs the whole gate on a
synthetic in-memory capture whose slot statistic at ``b == tol`` is *measured
to land below* ``tol`` (asserted as a premise, so the test cannot decay into
a tautology if numpy's rounding ever changes) and requires the row to read
detected anyway.  The flux route on the same capture is blind at that break,
which is the module's whole argument for gating the slot rather than the ratio.

No solve, no ``.npz`` on disk, no ``emfit`` change: the capture is four small
literal arrays handed to ``T3_ey_slot`` as a dict, which ``_load_capture``
returns unchanged.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pytest

_MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "gates_101_20.py"


def _load_gates():
    """Import ``tools/gates_101_20.py`` by path -- ``tools/`` is not a package."""
    spec = importlib.util.spec_from_file_location("gates_101_20", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("gates_101_20", module)
    spec.loader.exec_module(module)
    return module


gates = _load_gates()

#: The tolerance the gate is ruled at (``gates.T3_TOL``); pinned below.
TOL = 1e-5

#: The shortfall the module's measured curve records at ``b == tol``: the
#: double representation of ``(1+b)``, not physics (see the ``T3_TOL`` comment).
MEASURED_SHORTFALL = 3.8e-11


def test_tolerance_is_the_ruled_value():
    assert gates.T3_TOL == TOL


# ---------------------------------------------------------------------------
# the predicate, at the boundary and on both sides of it
# ---------------------------------------------------------------------------
def test_detected_at_exactly_tol():
    """``b == tol`` must read as detected -- this is the defect."""
    assert gates._detected(TOL, TOL) is True


def test_detected_at_the_measured_shortfall():
    """The statistic a real capture produces at ``b == tol``, 3.8e-11 short."""
    assert gates._detected(TOL * (1.0 - MEASURED_SHORTFALL), TOL) is True


@pytest.mark.parametrize("relative_miss", [1e-6, 1e-3, 1e-1])
def test_not_detected_below_the_slack(relative_miss):
    """The slack is a boundary allowance, not a blanket 'yes'."""
    assert gates._detected(TOL * (1.0 - relative_miss), TOL) is False


def test_slack_is_the_documented_value():
    assert gates._DETECT_RTOL == 1e-9


# ---------------------------------------------------------------------------
# the gate end to end, on a synthetic capture
# ---------------------------------------------------------------------------
# One station's worth of phasors.  Station 1 carries a 1 % taller Hz block, so
# the station flux ratio R = F[8]/F[0] is not trivially 1 and the break has to
# travel through the ratio to move it.  The Ey*Hz share of Sx is ~20 % of the
# Ez*Hy term, which is what makes the flux route nearly blind to an Ey break
# (measured share on the real record: 0.193803 vs 0.192777, i.e. the ratio gate
# sees only their difference -- here the flux statistic comes out ~1e-8 at
# b = 1e-5, three decades below the threshold).
_HZ_STATION1_SCALE = 1.01
_EY = np.array([0.006045682285011601 - 0.01320923711164163j,
                -0.01671681808701549 - 0.07807496467203805j])
_HZ = np.array([1.799707382720902 - 0.32542283686782436j,
                1.1441658720372287 + 0.7738065867276614j])
_EZ = np.array([[0.28121066979764925 - 0.3288239040579627j,
                 -0.5538228364240524 - 0.7921467553588982j],
                [0.9775674511260357 + 0.45495807124085547j,
                 -0.31055654665915255 - 0.09919805171738795j]])
_HY = np.array([[0.5452887139646817 + 0.8414649723701431j,
                 -0.6071856998706371 + 0.18803508698068597j],
                [0.12682784711186987 + 0.33057100813532614j,
                 -0.8922740434297903 + 0.41050391297026284j]])


def _capture():
    """``(n_stations, n_y, n_z)`` / ``(n_stations, n_y+1, n_z)`` blocks."""
    two = np.stack([_EY, _EY]).reshape(2, 1, 2)
    hz = np.stack([_HZ, _HZ * _HZ_STATION1_SCALE]).reshape(2, 1, 2)
    ez = np.stack([_EZ, _EZ]).reshape(2, 2, 2)
    hy = np.stack([_HY, _HY]).reshape(2, 2, 2)
    return {"plane_Ey": two, "plane_Ez": ez, "plane_Hy": hy,
            "plane_Hz": hz, "plane_n_samples": np.array([4])}


def test_slot_gate_detects_a_break_of_exactly_tol():
    result = gates.T3_ey_slot(_capture(), tol=TOL, ladder=(TOL,))
    row = result["rows"][0]

    # Premise: this capture really does land just *below* tol, i.e. the bare
    # ``>= tol`` of the pre-fix code called the threshold break undetected.
    assert row["slot_statistic"] < TOL
    assert (TOL - row["slot_statistic"]) <= 1e-9 * TOL

    assert row["slot_detected"] is True
    assert result["pass"] is True
    # ... and the flux route is blind to the same break, as documented: the
    # statistic is nonzero (so it is a real blind spot, not a division by zero)
    # but sits decades under the threshold.
    assert 0.0 < row["flux_statistic"] < 1e-3 * TOL
    assert row["flux_detected"] is False
    assert result["flux_route_reaches_tol"] is False


def test_slot_gate_stays_silent_just_below_tol():
    """A break 1 % under the tolerance is still not a detection."""
    break_level = TOL * (1.0 - 1e-2)
    result = gates.T3_ey_slot(_capture(), tol=TOL, ladder=(break_level,))
    row = result["rows"][0]
    assert row["slot_statistic"] < TOL * (1.0 - 1e-9)
    assert row["slot_detected"] is False
