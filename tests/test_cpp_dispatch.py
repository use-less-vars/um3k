"""Runtime dispatch: ``FITStepper.step`` choosing the compiled kernel vs Python.

``emfit.evolve.step_explicit`` is the reference.  When the optional extension
``emfit_core`` is importable and reports the ABI this package was written against
(``src/bindings.cpp``), ``FITStepper`` builds a :class:`emfit.evolve._KernelPlan`
and :meth:`FITStepper.step` runs the same update there instead.  This file is the
*dispatcher's* own test -- the numerical parity of the two implementations is the
subject of ``tests/test_cpp_parity.py``; here it is only asserted one more time
through the object a user actually drives.

What is checked
---------------
* the extension-aware tests are skipped (never passed) when ``emfit_core`` is not
  importable, so a skip stays an honest "the comparison did not run";
* with it importable, a stepper gets a non-``None`` ``kernel`` and, driven for a
  few hundred steps with every physical branch live at once (PML on x, a
  conductance that selects the lossy Ampere branch, a PEC wall set, a Ricker
  source), it agrees with a twin stepper forced onto the Python path *bit for
  bit* -- ``array_equal``, not ``allclose``;
* the forced-Python path reproduces a hand-written ``step_explicit`` loop, so the
  dispatch changes the object, never the arithmetic, and this holds with or
  without the extension built;
* the ABI gate: a kernel whose ``KERNEL_ABI`` does not match is rejected, with no
  warning and no exception;
* a PML carrying an :class:`emfit.pml.AbsorbedWork` audit keeps the stepper on
  the Python path, because the audit needs the pre-damp field and the kernel's
  two-multiplier form cannot supply it.
"""

import warnings

import numpy as np
import pytest

import emfit.evolve as evolve
from emfit.evolve import FITStepper, RickerSource, cfl_dt, step_explicit
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.operators import CellComplex
from emfit.pml import PML, AbsorbedWork

try:  # pragma: no cover - the point is which side of this we are on
    import emfit_core
except ImportError:  # no cover
    emfit_core = None

# The precondition for the kernel-aware tests is not merely "emfit_core is
# importable" -- a stale or ABI-mismatched build can be importable and still be
# rejected by the dispatcher (see _load_kernel).  Key the skip on the decision the
# dispatcher itself made, so the skip matches what the code under test will do.
requires_kernel = pytest.mark.skipif(
    evolve._KERNEL is None,
    reason="no ABI-compatible emfit_core is active (evolve._KERNEL is None), so "
    "there is no kernel to dispatch to; build it as in tests/test_cpp_parity.py",
)

# A small uniform box.  Eight cells along x so the two-cell PML has an interior
# to leave untouched; D = 1 mm keeps dt ~ 1.9 ps, so a 1 GHz Ricker is still
# ramping after the few hundred steps below and the fields stay finite.
D = 1.0e-3
NX, NY, NZ = 8, 4, 4


def _build():
    """``(cc, m_eps, m_mu, dt, pec_mask)`` for the shared test geometry."""
    grid = Grid.uniform(NX, NY, NZ, NX * D, NY * D, NZ * D)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    pec = cc.pec_edge_mask(walls=("zmin", "zmax"))
    return cc, m_eps, m_mu, float(cfl_dt(grid)), pec


def _full_system():
    """The geometry with every branch engaged: PML, lossy, PEC, source.

    Returns ``(cc, m_eps, m_mu, kwargs, n_edges, source_idx, fmax)`` where
    ``kwargs`` is exactly the keyword set to hand :class:`FITStepper`, so a
    kernel twin and a Python twin are built from the *same* material and the same
    operators.  The source edges are chosen off the PEC set, otherwise the PEC
    reset would zero the drive before it did anything.
    """
    cc, m_eps, m_mu, dt, pec = _build()

    pml = PML(cc.grid, thickness_cells=2, order=2, target=1.0e-4, axes=("x",),
              cc=cc)

    # A small, everywhere-nonzero conductance so the lossy Ampere branch is
    # actually selected (an all-zero m_sigma is treated as lossless), but tiny
    # enough that it perturbs nothing physically.
    m_sigma = np.zeros(cc.n_edges, dtype=float)
    m_sigma[:: max(1, cc.n_edges // 7)] = 1.0e-6

    free = np.flatnonzero(~pec)
    source_idx = free[free.size // 2: free.size // 2 + 3]
    assert source_idx.size == 3

    kwargs = dict(dt=dt, pec=pec, pml=pml, m_sigma=m_sigma)
    return cc, m_eps, m_mu, kwargs, cc.n_edges, source_idx, 1.0e9


def _n_diff(a, b):
    a = np.asarray(a)
    b = np.asarray(b)
    assert a.shape == b.shape, (a.shape, b.shape)
    return int(np.count_nonzero(a != b))


# ----------------------------------------------------------------------
# 1. the kernel is selected
# ----------------------------------------------------------------------
@requires_kernel
def test_stepper_selects_the_kernel_when_available():
    cc, m_eps, m_mu, dt, pec = _build()
    st = FITStepper(cc, m_eps, m_mu, dt=dt)
    assert evolve._ACTIVE_STEP == "cpp"
    assert st.kernel is not None
    # The ABI the dispatcher checked is the one the active module advertises.
    assert evolve._KERNEL.KERNEL_ABI == evolve._KERNEL_ABI


# ----------------------------------------------------------------------
# 2. kernel stepper == Python stepper, bit for bit, all branches live
# ----------------------------------------------------------------------
@requires_kernel
def test_kernel_and_python_steppers_agree_bit_for_bit(monkeypatch):
    """300 steps, every branch engaged, ``array_equal`` (not ``allclose``)."""
    cc, m_eps, m_mu, kwargs, n_edges, source_idx, fmax = _full_system()

    # Kernel twin: built with the extension present.
    cpp = FITStepper(cc, m_eps, m_mu, **kwargs)
    assert cpp.kernel is not None
    assert cpp.loss_num is not None, "the lossy branch did not engage"
    assert cpp.pec_idx is not None and cpp.pml is not None

    # Python twin: identical construction, but the dispatcher is blinded to the
    # kernel for this build only, so __init__ leaves self.kernel as None.
    monkeypatch.setattr(evolve, "_KERNEL", None)
    py = FITStepper(cc, m_eps, m_mu, **kwargs)
    assert py.kernel is None

    # Two source instances: RickerSource reuses its output buffer, so a single
    # object would have one step's ``j`` overwrite the other's.
    src_cpp = RickerSource(n_edges, source_idx, fmax=fmax, amplitude=1.0e-2)
    src_py = RickerSource(n_edges, source_idx, fmax=fmax, amplitude=1.0e-2)

    n_steps = 300
    j_peak = 0.0
    for _ in range(n_steps):
        j_cpp = src_cpp(cpp.time)
        j_py = src_py(py.time)
        j_peak = max(j_peak, float(np.max(np.abs(j_cpp))))
        cpp.step(j_cpp)
        py.step(j_py)

    assert j_peak > 0.0, "the source injected nothing: the j branch is inert"
    assert np.all(np.isfinite(cpp.e)) and np.all(np.isfinite(cpp.h)), (
        "the run diverged, so a bit comparison would be meaningless "
        "(or poisoned by nan != nan)")
    assert np.isfinite(py.e).all() and np.isfinite(py.h).all()

    de = _n_diff(cpp.e, py.e)
    dh = _n_diff(cpp.h, py.h)
    # Printed so a failure reports the shape of the disagreement, not just "False".
    print(f"after {n_steps} steps: e differs in {de}/{cpp.e.size}, "
          f"h differs in {dh}/{cpp.h.size}")
    np.testing.assert_array_equal(cpp.e, py.e,
                                  err_msg="kernel e != python e")
    np.testing.assert_array_equal(cpp.h, py.h,
                                  err_msg="kernel h != python h")
    assert cpp.n == py.n == n_steps
    assert cpp.time == py.time


# ----------------------------------------------------------------------
# 3. forced-Python dispatch reproduces a bare step_explicit loop
# ----------------------------------------------------------------------
def test_forced_python_path_matches_a_direct_step_explicit_loop(monkeypatch):
    """Runs with or without the extension: the None branch is exact Python."""
    cc, m_eps, m_mu, kwargs, n_edges, source_idx, fmax = _full_system()

    monkeypatch.setattr(evolve, "_KERNEL", None)
    st = FITStepper(cc, m_eps, m_mu, **kwargs)
    assert st.kernel is None

    # A hand-written twin of FITStepper.step's Python branch, over its own zeros.
    e = np.zeros(st.C.shape[1], dtype=np.float64)
    h = np.zeros(st.C.shape[0], dtype=np.float64)
    src = RickerSource(n_edges, source_idx, fmax=fmax, amplitude=1.0e-2)

    n_steps = 50
    for _ in range(n_steps):
        j = src(st.time)
        st.step(j)
        step_explicit(e, h, st.C, st.C_tilde, st.inv_m_mu, st.inv_m_eps, st.dt,
                      st.loss_num, st.loss_den, st.pml, st.pec_idx, j)

    np.testing.assert_array_equal(st.e, e, err_msg="stepper e != direct loop e")
    np.testing.assert_array_equal(st.h, h, err_msg="stepper h != direct loop h")


# ----------------------------------------------------------------------
# 4. the ABI gate rejects a mismatched kernel, silently
# ----------------------------------------------------------------------
def test_load_kernel_rejects_a_mismatched_abi_silently():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert evolve._load_kernel(abi=-1) is None
    assert caught == [], f"_load_kernel warned instead of returning None: {caught}"

    # Positive control: with the ABI check disabled the same importer returns the
    # module if one is importable -- proving the abi=-1 rejection above was the
    # ABI gate, not a missing extension -- and the real-ABI decision agrees with
    # whatever the module already settled on at import.
    if emfit_core is not None:
        assert evolve._load_kernel(abi=None) is emfit_core
    else:
        assert evolve._load_kernel(abi=None) is None
    assert evolve._load_kernel() is evolve._KERNEL


# ----------------------------------------------------------------------
# 5. an audited PML keeps the stepper on the Python path
# ----------------------------------------------------------------------
def test_audited_pml_forces_the_python_path(monkeypatch):
    """``AbsorbedWork.record`` needs the pre-damp field, which the kernel lacks."""
    cc, m_eps, m_mu, dt, pec = _build()
    audit = AbsorbedWork(groups={"ends": ("xmin", "xmax")})
    pml = PML(cc.grid, thickness_cells=2, order=2, target=1.0e-4, axes=("x",),
              cc=cc, audit=audit)

    # Even with a perfectly usable kernel importable, the audit is disqualifying.
    if emfit_core is not None:
        monkeypatch.setattr(evolve, "_KERNEL", emfit_core)
    st = FITStepper(cc, m_eps, m_mu, dt=dt, pec=pec, pml=pml)
    assert st.power_audit is audit
    assert st.kernel is None
