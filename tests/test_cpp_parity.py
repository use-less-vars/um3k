"""Parity between the compiled FIT kernel and the Python reference.

NOT RUN IN THIS CONTAINER -- no C++ toolchain, no network; this test exists to be
run on a host that has one.  Here it skips, and a skip is the honest result: a
pass would mean the comparison ran, so swallowing an ImportError into ``pass``
(or ``return``) would be a lie about the state of the port.

What it checks, once ``emfit_core`` is importable:

1. bit-identical agreement with the frozen golden vectors in
   ``tests/data/cpp_golden_step.npz`` (three steps, e and h, ``assert_array_equal``
   -- not ``allclose``; the claim being tested is *exactness*);
2. the same agreement against a *live* call to :func:`emfit.evolve.step_explicit`,
   so a stale or hand-edited golden file cannot make this file pass on its own;
3. that the golden file's bookkeeping (``n_edges`` / ``n_faces``) matches the
   shapes actually handed to the kernel, so a silently reshaped grid fails loudly
   instead of comparing two identically-wrong things.

The golden file is produced by ``evidence/termination/make_cpp_golden.py`` from
the Python reference, so there is one source of truth.

Note on the Ampere half: Python's ``C_tilde`` is a CSC view of ``C.T``, and the
kernel consumes the CSR copy stored as ``C_tilde_csr_*``.  Whether those two sum
in the same order is exactly what this file is for -- the argument that they do
is plausible, not proof, and the test decides.
"""

import os

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "data", "cpp_golden_step.npz")

# Built from source, not by the packaging backend: the documented alternative is
# `pip install -e .` (scikit-build-core), which cannot be exercised in this
# container -- scikit-build-core is not installed.  The output must live INSIDE
# the workspace: /tmp is mounted noexec, so a .so left there will not import.
BUILD_COMMANDS = (
    "/usr/bin/g++ -O3 -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra "
    "-I/workspace/.venv/lib/python3.12/site-packages/pybind11/include "
    "-I/usr/local/include/python3.12 -Isrc src/bindings.cpp src/emfit_core.cpp "
    '-o "build/cpp/emfit_core$(python3 -c "import sysconfig;'
    'print(sysconfig.get_config_var(\'EXT_SUFFIX\'))")" && '
    "PYTHONPATH=build/cpp python3 -m pytest tests/test_cpp_parity.py -v"
)

_IMPORT_ERROR = None
try:  # pragma: no cover - the point is which side of this we are on
    import emfit_core
except ImportError as exc:  # no cover
    emfit_core = None
    _IMPORT_ERROR = exc

pytestmark = pytest.mark.skipif(
    emfit_core is None,
    reason=(
        "emfit_core (the compiled FIT kernel) is not importable, so there is "
        f"nothing to compare: {_IMPORT_ERROR}. Build and run it on a host with "
        f"cmake + pybind11: {BUILD_COMMANDS}"
    ),
)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _require_golden():
    if not os.path.exists(GOLDEN):
        pytest.fail(
            f"golden file {GOLDEN} is missing; regenerate it with "
            "python3 evidence/termination/make_cpp_golden.py"
        )


# The binding declares its CSR index arrays as ``array_t<long>``
# (``src/bindings.cpp``) and ``long`` in ``emfit_core.h``'s ``Csr``.  On LP64
# Linux that is 8 bytes and numpy spells the same type both ``np.int64`` and
# ``np.int_``, so ``np.int64`` below IS the declared type rather than a tolerant
# choice.  On a platform where C ``long`` is 32-bit it would not be, and the
# binding would reject these arrays by name -- which is the intended outcome.
INDEX_DTYPE = np.int64


def _kernel_step(z, e, h):
    """One compiled step, in place on ``e``/``h``.

    Fed the CSR copy of the dual curl (``C_tilde_csr_*``): the kernel's row loop
    needs CSR, while Python holds ``C.T`` as CSC.

    Every argument is made exactly what the binding declares -- a tuple of
    Python ints for each shape, C-contiguous float64 / int64 arrays for the
    golden data -- so this test never leans on pybind11's implicit casting.  The
    binding is strict on purpose (no forcecast): if it were lenient, the parity
    claim would be about a converted copy rather than about these bytes.
    """
    e_ptr = e.__array_interface__["data"][0]
    h_ptr = h.__array_interface__["data"][0]
    e = np.ascontiguousarray(e, dtype=np.float64)
    h = np.ascontiguousarray(h, dtype=np.float64)
    assert (e.__array_interface__["data"][0] == e_ptr
            and h.__array_interface__["data"][0] == h_ptr), (
        "ascontiguousarray copied e or h: the kernel updates them in place, so "
        "a copy would leave the caller's arrays untouched and this test would "
        "compare stale data against the golden file")

    return emfit_core.step_explicit(
        e,
        h,
        np.ascontiguousarray(z["C_data"], dtype=np.float64),
        np.ascontiguousarray(z["C_indices"], dtype=INDEX_DTYPE),
        np.ascontiguousarray(z["C_indptr"], dtype=INDEX_DTYPE),
        tuple(int(v) for v in z["C_shape"]),
        np.ascontiguousarray(z["C_tilde_csr_data"], dtype=np.float64),
        np.ascontiguousarray(z["C_tilde_csr_indices"], dtype=INDEX_DTYPE),
        np.ascontiguousarray(z["C_tilde_csr_indptr"], dtype=INDEX_DTYPE),
        tuple(int(v) for v in z["C_tilde_shape"]),
        np.ascontiguousarray(z["inv_m_mu"], dtype=np.float64),
        np.ascontiguousarray(z["inv_m_eps"], dtype=np.float64),
        float(z["dt"]),
    )


def _worst(actual, expected):
    """(max |diff|, flat index of it, actual there, expected there)."""
    d = np.abs(np.asarray(actual) - np.asarray(expected))
    if d.size == 0:
        return 0.0, -1, 0.0, 0.0
    idx = int(np.argmax(d))
    return float(d.flat[idx]), idx, float(np.asarray(actual).flat[idx]), \
        float(np.asarray(expected).flat[idx])


def _assert_bit_identical(actual, expected, what):
    """``assert_array_equal``, but say *how far off* before it fires."""
    if np.array_equal(actual, expected):
        return
    worst, idx, got, want = _worst(actual, expected)
    n_bad = int(np.count_nonzero(np.asarray(actual) != np.asarray(expected)))
    detail = (f"{what} is NOT bit-identical: {n_bad}/{np.size(expected)} "
              f"entries differ, worst |diff| = {worst:.6e} at flat index {idx} "
              f"(cpp {got!r} vs expected {want!r})")
    try:
        np.testing.assert_array_equal(actual, expected)
    except AssertionError as exc:  # noqa: PERF203 - deliberate
        raise AssertionError(f"{detail}\n{exc}") from None


# ----------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------
def test_cpp_matches_frozen_golden_bit_for_bit():
    _require_golden()
    with np.load(GOLDEN) as z:
        e = np.array(z["e0"], dtype=np.float64, order="C")
        h = np.array(z["h0"], dtype=np.float64, order="C")
        n_steps = int(z["n_steps"])
        assert n_steps >= 1

        for step_no in range(1, n_steps + 1):
            _kernel_step(z, e, h)
            _assert_bit_identical(e, z[f"e{step_no}"],
                                  f"C++ e after step {step_no}")
            _assert_bit_identical(h, z[f"h{step_no}"],
                                  f"C++ h after step {step_no}")


def test_cpp_matches_live_python_kernel_bit_for_bit():
    """Second comparison against ``step_explicit``, not against the golden file."""
    from emfit.evolve import step_explicit

    _require_golden()
    with np.load(GOLDEN) as z:
        e_cpp = np.array(z["e0"], dtype=np.float64, order="C")
        h_cpp = np.array(z["h0"], dtype=np.float64, order="C")
        e_py = e_cpp.copy()
        h_py = h_cpp.copy()

        inv_m_mu = z["inv_m_mu"]
        inv_m_eps = z["inv_m_eps"]
        dt = float(z["dt"])
        # Both operators from the CSR arrays the kernel was fed, so this test
        # isolates "cpp vs python on identical inputs" from the CSC/CSR question.
        import scipy.sparse as sp

        C = sp.csr_matrix((z["C_data"], z["C_indices"], z["C_indptr"]),
                          shape=tuple(int(v) for v in z["C_shape"]))
        C_tilde_csr = sp.csr_matrix(
            (z["C_tilde_csr_data"], z["C_tilde_csr_indices"],
             z["C_tilde_csr_indptr"]),
            shape=tuple(int(v) for v in z["C_tilde_shape"]))

        for step_no in range(1, int(z["n_steps"]) + 1):
            _kernel_step(z, e_cpp, h_cpp)
            step_explicit(e_py, h_py, C, C_tilde_csr, inv_m_mu, inv_m_eps, dt)
            _assert_bit_identical(e_cpp, e_py, f"e, cpp vs live python, step {step_no}")
            _assert_bit_identical(h_cpp, h_py, f"h, cpp vs live python, step {step_no}")


def test_golden_bookkeeping_matches_the_shapes_handed_to_the_kernel():
    _require_golden()
    with np.load(GOLDEN) as z:
        n_edges = int(z["n_edges"])
        n_faces = int(z["n_faces"])
        c_rows, c_cols = (int(v) for v in z["C_shape"])
        ct_rows, ct_cols = (int(v) for v in z["C_tilde_shape"])

        assert (c_rows, c_cols) == (n_faces, n_edges), (
            f"C is {(c_rows, c_cols)}, expected (n_faces, n_edges) = "
            f"{(n_faces, n_edges)}: the grid was reshaped and the golden data "
            "no longer describes the system the kernel is being given")
        assert (ct_rows, ct_cols) == (n_edges, n_faces), (
            f"C_tilde is {(ct_rows, ct_cols)}, expected (n_edges, n_faces) = "
            f"{(n_edges, n_faces)}")

        # The CSR structures really do have the stated shapes.
        assert z["C_indptr"].size == n_faces + 1
        assert z["C_tilde_csr_indptr"].size == n_edges + 1
        assert z["C_data"].size == z["C_indices"].size
        assert z["C_tilde_csr_data"].size == z["C_tilde_csr_indices"].size
        # ...and the state vectors match the edge/face counts.
        for name, size in (("e0", n_edges), ("h0", n_faces),
                           ("inv_m_eps", n_edges), ("inv_m_mu", n_faces)):
            assert z[name].size == size, f"{name} has {z[name].size}, want {size}"
        # The stored int64 index dtypes are what the strict binding wants.
        assert z["C_indices"].dtype == np.int64
        assert z["C_indptr"].dtype == np.int64
        # Both copies of the dual carry the same non-zeros.
        assert z["C_tilde_data"].size == z["C_tilde_csr_data"].size
