"""Tests for :class:`emfit.pml.AbsorbedWork`, the opt-in absorber audit.

What is being checked
---------------------
``AbsorbedWork`` is the accounting behind the microstrip report row "|S21|
implied by the absorbed work", so a wrong number here is invisible: it does not
blow up, it just quietly publishes a wrong loss.  Two bugs of exactly that kind
were found while writing this file, both in ``AbsorbedWork._build``:

* the magnetic share was missing the ``mu0 / eps0`` factor (``sigma_m`` is
  stored already scaled, ``sigma_for_walls(kind="f")`` returns the unscaled
  profile), so the magnetic work read as *zero* and the total came out 1.89x
  low.  ``test_magnetic_share_and_power_balance`` guards that number directly.
* ``kind="h"`` was handed to ``sigma_for_walls``, which only accepts ``"e"``
  and ``"f"``.

The three properties asserted, in order of importance
-----------------------------------------------------
1. **A wall the layer does not open contributes exactly 0.0**, not "nearly
   nothing".  That is legitimate as an exact equality because
   ``sigma_for_walls`` returns a hard zero for a wall that is not in
   ``pml.walls``, so the weight vector of that bin is empty rather than small.
   The test is not vacuous: real ``sigma`` acts on the same grid, in the same
   run, and the opened bin reads a finite positive number.
2. **The magnetic share is non-zero** and of the same order as the electric
   one.  In a matched layer ``sigma_m / mu0 = sigma_e / eps0`` and the two
   field energies are equal in a travelling wave, so ``W_h / W_e`` is O(1) --
   the ``mu0/eps0`` bug put it at ~7e-6.
3. **The absorbed work closes against the energy the run actually lost.**

Why the closure test uses an *initial-value* problem
----------------------------------------------------
The obvious balance -- drive a source and compare the injected ``sum dt j e``
with the absorbed work -- was measured and does **not** close: in a 16^3 box
with a settled dipole, absorbed/injected = 0.807, and on a periodic
parallel-plate line the ratios ran -0.60, +0.75, +0.20 while the source's own
per-step self-kick ``dt j / m_eps`` was 5e7 times the absorbed work.  A hard
current source on small cells is almost pure reactance: the field at the source
is dominated by that kick (195 V against a 7e-7 V propagating field), so the
injected sum is a cancellation of terms ten orders larger than the answer and
cannot pin the power.  So nothing is driven here: the run starts from an
initial field, the layer is on every wall, there is no ``j`` anywhere, and the
only way energy leaves is through an absorber that the audit bins.

The measured closure is **first order in ``dt``**, because the audit counts the
change of the quadratic energy ``1/2 e.m_eps.e + 1/2 h.m_mu.h`` and not of the
mixed-state invariant ``U`` that the leapfrog actually conserves; the two
differ by the cross term ``-(dt/2)(C e).h``, whose change *during a damping
event* is O(dt) and is not counted.  Measured on the grid used below, run to 4000
steps at three Courant safeties (the initial field is not divergence free, so a
static part survives at Q_final/Q_0 ~ 0.49, never reaches the layer, and never
has to: it is energy the run *kept*, and ``U_0 - U_final`` counts it as kept):

    dt safety      A / (U_0 - U_final)
    0.99           1.641
    0.50           1.153
    0.25           1.057

so the tolerance below (10 %) is the measured O(dt) error at ``safety=0.25``,
not a slackened guess: it is what remains of a first-order defect that is
plainly converging to 1.  A genuine counting error -- the ``mu0/eps0`` bug --
was a factor 1.89, twenty times outside it.

Two API facts worth knowing (both cost a cycle to find out):
``PML.__init__`` requires ``0 < |target| < 1``, so ``target=1.0`` cannot be
used to build a literally lossless layer; and ``Grid.uniform``'s seventh
positional argument is ``origin``, not a frequency.
"""

from __future__ import annotations

import numpy as np

from emfit.evolve import FITStepper, cfl_dt
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.operators import CellComplex
from emfit.pml import PML, AbsorbedWork

ALL_WALLS = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")


def _pulse(n=12, cells=4, walls=ALL_WALLS, groups=None, safety=0.99,
           max_steps=400, energy_floor=1e-8):
    """A box of ``n**3`` cells with a pulse in it and a layer on ``walls``.

    Returns ``(audit, stepper, U0, energies)`` with ``energies`` the
    ``energy_components()`` dict of the last state.  The pulse is three ``EX``
    edges at the centre, i.e. enough structure to feed every wall; it is *not*
    divergence free, so a static part remains forever -- see the module
    docstring for why that is harmless here and how the floor is chosen.
    """
    grid = Grid.uniform(n, n, n, 0.12, 0.12, 0.12)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    audit = AbsorbedWork(groups)
    pml = PML(grid, thickness_cells=cells, order=2, target=1e-4, cc=cc,
              walls=walls, audit=audit)
    st = FITStepper(cc, m_eps, m_mu, dt=cfl_dt(grid, safety=safety), pml=pml)
    mid = n // 2
    for k in range(mid - 1, mid + 2):
        for j in range(mid - 1, mid + 2):
            st.e[cc.idx_ex(mid, j, k)] = 1.0
    u0 = st.energy()
    # Energy sampled every 25 steps, not every step: ``energy_components``
    # costs its own ``C @ e``, which dominates the loop otherwise.
    for _ in range(int(max_steps)):
        st.step()
        if st.n % 25 == 0:
            c = st.energy_components()
            if c["electric"] + c["magnetic"] < energy_floor * u0:
                break
    return audit, st, u0, st.energy_components()


# ---------------------------------------------------------------------------
# 1. a bin the layer does not own is exactly zero
# ---------------------------------------------------------------------------
def test_a_wall_the_layer_does_not_open_reads_exactly_zero():
    """``lateral`` is ``0.0`` while ``end`` carries the whole loss.

    Exact equality is the point of the test: a switched-off group must read
    zero, not a small number, or a report cannot distinguish "the lateral walls
    absorb nothing" from "they absorb a little".  It is exact because
    ``PML.sigma_for_walls`` returns a hard zero outside ``pml.walls``, which
    makes the bin's weight vector empty; there is no arithmetic to round.
    """
    groups = {"end": ("zmin", "zmax"),
              "lateral": ("xmin", "xmax", "ymin", "ymax")}
    audit, st, u0, c = _pulse(walls=("zmin", "zmax"), groups=groups)

    assert np.max(np.abs(st.e)) > 0.0, "no field: the test would be vacuous"
    assert audit.steps > 0
    # the layer really is absorbing, so the zero below is a comparison
    assert audit.total("end") > 0.0

    assert audit.total("lateral") == 0.0
    assert audit.work["e"]["lateral"] == 0.0
    assert audit.work["h"]["lateral"] == 0.0
    fractions = audit.fractions()
    assert fractions["lateral"] == 0.0
    assert fractions["end"] == 1.0
    # ... and the opened group equals the layer total, all of it accounted for
    assert audit.total("end") == audit.total_work()


# ---------------------------------------------------------------------------
# 2 and 3. the magnetic share, and the closure
# ---------------------------------------------------------------------------
def test_magnetic_share_and_power_balance():
    """``W_h/W_e`` is O(1) and the absorbed work equals the energy lost.

    Two independent assertions on one run:

    * ``W_h / W_e`` -- if the face share loses its ``mu0/eps0`` factor the
      magnetic work reads as zero (measured ~7e-6 of the electric one) and the
      total is 1.89x low.  In a matched layer the two shares are comparable, so
      a factor-of-three window around 1 is wide enough to be robust and narrow
      enough to fail on that bug.
    * ``A == U_0 - U_final`` to 10 %, the measured first-order-in-dt error
      (see the module docstring: 1.641 / 1.153 / 1.057 at dt safety
      0.99 / 0.50 / 0.25, and this run uses 0.25).
    """
    audit, st, u0, c = _pulse(safety=0.25, max_steps=4000)

    work_e = sum(audit.work["e"].values())
    work_h = sum(audit.work["h"].values())
    assert work_e > 0.0
    ratio = work_h / work_e
    assert 1.0 / 3.0 < ratio < 3.0, f"magnetic/electric share {ratio:.3e}"

    absorbed = audit.total_work()
    lost = u0 - c["total"]
    assert lost > 0.0
    assert absorbed == pytest_approx(lost, rel=0.10)


def pytest_approx(value, rel=1e-6):
    """``pytest.approx`` without importing pytest for one call site."""
    import pytest

    return pytest.approx(value, rel=rel)
