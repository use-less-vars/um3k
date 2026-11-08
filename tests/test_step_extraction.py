"""Pin the extracted step kernel: ``FITStepper.step`` == ``step_explicit``.

The FIT leapfrog update now lives in the module-level function
:func:`emfit.evolve.step_explicit`, operating on bare arrays; ``FITStepper.step``
is a thin wrapper around it.  This suite is the regression net for that move.

It does *not* check physics -- ``tests/test_energy.py`` owns energy
conservation and the CFL limit.  It checks something narrower and stricter:
that the wrapper and the bare kernel produce **bit-for-bit identical** states
(``assert_array_equal``, never ``assert_allclose``).  That is the property the
C++ port will have to reproduce, so it must be pinned exactly, not
approximately.

Both sides start from the same seeded state, and the reference call is made on
*copies* of the arrays, so a divergence cannot be hidden by in-place aliasing.
"""

import numpy as np
import pytest

from emfit.evolve import FITStepper, cfl_dt, step_explicit
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.operators import CellComplex

SEED = 20261109
NX, NY, NZ = 4, 3, 2
H = 0.1


def build(m_sigma=None, pec=None):
    """Small real FIT system, constructed through the production path."""
    g = Grid.uniform(NX, NY, NZ, lx=NX * H, ly=NY * H, lz=NZ * H)
    cc = CellComplex(g)
    m_eps, m_mu = material_matrices(g, cc)
    st = FITStepper(cc, m_eps, m_mu, dt=0.9 * cfl_dt(g), pec=pec,
                    m_sigma=m_sigma)
    return g, cc, st


def seed_state(st, seed=SEED):
    """Fill ``e`` and ``h`` with seeded noise (no zeros to hide bugs behind)."""
    rng = np.random.default_rng(seed)
    st.e[:] = rng.standard_normal(st.e.size)
    st.h[:] = rng.standard_normal(st.h.size)


def kernel_reference(st, j=None):
    """One ``step_explicit`` call on copies of the stepper's current state."""
    e = st.e.copy()
    h = st.h.copy()
    step_explicit(e, h, st.C, st.C_tilde, st.inv_m_mu, st.inv_m_eps, st.dt,
                  st.loss_num, st.loss_den, st.pml, st.pec_idx, j)
    return e, h


# ----------------------------------------------------------------------
def test_lossless_step_matches_kernel_exactly():
    _, _, st = build()
    assert st.loss_den is None, "this case must exercise the lossless branch"
    seed_state(st)

    e_ref, h_ref = kernel_reference(st)
    st.step()

    np.testing.assert_array_equal(st.e, e_ref)
    np.testing.assert_array_equal(st.h, h_ref)
    assert st.n == 1
    assert st.time == st.dt


def test_lossless_three_steps_match_kernel_exactly():
    _, _, st = build()
    seed_state(st)

    for step_no in range(3):
        e_ref, h_ref = kernel_reference(st)
        st.step()
        np.testing.assert_array_equal(st.e, e_ref,
                                      err_msg=f"e after step {step_no + 1}")
        np.testing.assert_array_equal(st.h, h_ref,
                                      err_msg=f"h after step {step_no + 1}")
        assert st.n == step_no + 1


def test_with_current_source_matches_kernel_exactly():
    _, _, st = build()
    seed_state(st)
    rng = np.random.default_rng(SEED + 1)
    j = rng.standard_normal(st.e.size)

    e_ref, h_ref = kernel_reference(st, j=j)
    st.step(j=j)

    np.testing.assert_array_equal(st.e, e_ref)
    np.testing.assert_array_equal(st.h, h_ref)


def test_lossy_step_matches_kernel_exactly():
    """Trapezoidal Ampere branch: the in-place rewrite must be exact."""
    # A conductance on roughly a fifth of the edges: enough to enter the lossy
    # branch without making every edge lossy.
    _, cc, _ = build()
    rng = np.random.default_rng(SEED + 2)
    m_sigma = np.zeros(cc.n_edges)
    hits = rng.choice(m_sigma.size, size=max(1, m_sigma.size // 5),
                      replace=False)
    m_sigma[hits] = 1.0e-3
    _, _, st = build(m_sigma=m_sigma)

    expect = (st.m_eps / st.dt - 0.5 * m_sigma)
    np.testing.assert_array_equal(st.loss_num, expect)
    assert st.loss_den is not None, "the lossy branch was not entered"
    seed_state(st)

    for step_no in range(2):
        e_ref, h_ref = kernel_reference(st)
        st.step()
        np.testing.assert_array_equal(st.e, e_ref,
                                      err_msg=f"lossy e, step {step_no + 1}")
        np.testing.assert_array_equal(st.h, h_ref,
                                      err_msg=f"lossy h, step {step_no + 1}")


def test_pec_step_matches_kernel_exactly():
    g = Grid.uniform(NX, NY, NZ, lx=NX * H, ly=NY * H, lz=NZ * H)
    cc = CellComplex(g)
    mask = cc.pec_edge_mask(("xmin", "xmax"))
    _, _, st = build(pec=mask)
    assert st.pec_idx is not None
    seed_state(st)

    e_ref, h_ref = kernel_reference(st)
    st.step()

    np.testing.assert_array_equal(st.e, e_ref)
    np.testing.assert_array_equal(st.h, h_ref)
    # And the constraint itself still holds (non-vacuous: the mask is non-empty).
    assert st.pec_idx.size > 0
    np.testing.assert_array_equal(st.e[st.pec_idx], np.zeros(st.pec_idx.size))


def test_kernel_mutates_in_place_and_returns_the_same_objects():
    """The C++ port must fill caller-owned buffers; pin that contract here."""
    _, _, st = build()
    seed_state(st)
    e, h = st.e.copy(), st.h.copy()
    e_before, h_before = e.copy(), h.copy()
    e_out, h_out = step_explicit(e, h, st.C, st.C_tilde, st.inv_m_mu,
                                 st.inv_m_eps, st.dt, st.loss_num,
                                 st.loss_den, st.pml, st.pec_idx)
    assert e_out is e
    assert h_out is h
    # ...and the buffers really were written to (a no-op would be a silent pass).
    assert not np.array_equal(e, e_before)
    assert not np.array_equal(h, h_before)


def test_kernel_is_exported():
    import emfit.evolve as ev

    assert "step_explicit" in ev.__all__
    assert ev.step_explicit is step_explicit
