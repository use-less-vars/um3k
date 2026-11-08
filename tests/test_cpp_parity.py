"""Parity between the compiled FIT kernel and the Python reference.

NOT RUN IN THIS CONTAINER -- no C++ toolchain, no network; this test exists to be
run on a host that has one.  Here it skips, and a skip is the honest result: a
pass would mean the comparison ran, so swallowing an ImportError into ``pass``
(or ``return``) would be a lie about the state of the port.

Two golden files, one per branch configuration, both produced by
``evidence/termination/make_cpp_golden.py`` from the Python reference, so there
is one source of truth and the golden data cannot drift away from the scheme:

* ``tests/data/cpp_golden_step.npz`` (v1) -- the lossless, source-free,
  non-PML, non-PEC step.  Written first and never regenerated to match the
  kernel: it is the independent witness the port was validated against.
* ``tests/data/cpp_golden_step_v2.npz`` (v2) -- every branch of
  ``step_explicit`` live at once: a PML on one axis (stored as the two
  multiplier vectors the kernel takes, not as a layer object), a conductance
  distribution (so the lossy Ampere constants ``loss_num`` / ``loss_den`` are
  stored), a PEC index array, and a non-zero current source ``j``.

What it checks, once ``emfit_core`` is importable:

v1, lossless path
1. bit-identical agreement with the frozen v1 golden vectors (three steps, e
   and h, ``assert_array_equal`` -- not ``allclose``; the claim being tested is
   *exactness*);
2. the same agreement against a *live* call to :func:`emfit.evolve.step_explicit`,
   so a stale or hand-edited golden file cannot make this file pass on its own;
3. that the golden file's bookkeeping (``n_edges`` / ``n_faces``) matches the
   shapes actually handed to the kernel, so a silently reshaped grid fails loudly
   instead of comparing two identically-wrong things.

v2, full-physics path
4. bit-identical agreement with the frozen v2 golden vectors, same three steps,
   with every optional argument passed;
5. the same agreement against a live Python call, at every step;
6. v2 bookkeeping: each branch array has the length of the set it indexes, the
   ``pec_idx`` dtype is the int64 the binding declares (not a bool mask), and
   every branch is *actually engaged* in the file (a damping factor < 1, a
   conductance that selected the lossy branch, a non-empty PEC set, a non-zero
   source) -- a v2 file that quietly degenerated into v1 would test nothing;
7. ablation: dropping any single branch (PML, lossy, PEC, source) must change
   the three-step result -- on both sides, by the same bytes.  A *non-zero*
   difference is the assertion: it is what proves those branches are covered
   rather than merely passed through;
8. non-vacuity controls: consecutive golden steps are different vectors, the
   bit comparison itself catches a one-ULP change (so "0 of 133 differ" is a
   measurement, not an artefact of comparing an array to itself), and a
   perturbation of one input element propagates into the three-step result.

What is NOT covered, and is not claimed: the golden grid is 4x3x2 (133 edges,
98 faces), far too small for the OpenMP loop to split across threads, so nothing
here says anything about parallel execution; and a bit-identical result is a
property of the build line (no FMA contraction, no reassociation), not of the
algorithm -- see docs/design/cpp-kernel-status-2026-11-09.md.

Regenerate v2 with ``python3 evidence/termination/make_cpp_golden.py --v2``; v1
only with ``... --v1``.  The script defaults to v1-only on purpose, so that
``--v2`` cannot silently rewrite the frozen witness.

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
GOLDEN_V2 = os.path.join(HERE, "data", "cpp_golden_step_v2.npz")

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

# The six optional arguments of ``step_explicit``, in the order the binding
# declares them.  ``None`` means "branch absent"; the C++ side spells the PML as
# its two multiplier vectors (``damp_e`` / ``damp_h``) rather than as a layer.
_BRANCH_KEYS = ("loss_num", "loss_den", "damp_e", "damp_h", "pec_idx", "j")


def _kernel_step(z, e, h, **branch):
    """One compiled step, in place on ``e``/``h``.

    Fed the CSR copy of the dual curl (``C_tilde_csr_*``): the kernel's row loop
    needs CSR, while Python holds ``C.T`` as CSC.

    Every argument is made exactly what the binding declares -- a tuple of
    Python ints for each shape, C-contiguous float64 / int64 arrays for the
    golden data -- so this test never leans on pybind11's implicit casting.  The
    binding is strict on purpose (no forcecast): if it were lenient, the parity
    claim would be about a converted copy rather than about these bytes.

    ``branch`` is any subset of :data:`_BRANCH_KEYS`.  Names left out stay at the
    kernel's own ``None`` default, which is how the v1 tests go on calling
    exactly the lossless entry point they always did; a name passed as ``None``
    is the ablation test dropping that branch on purpose.
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

    for name, arr in branch.items():
        assert name in _BRANCH_KEYS, f"unknown branch argument {name!r}"
        if arr is None:  # an arm of the ablation test, dropped on purpose
            continue
        want = INDEX_DTYPE if name == "pec_idx" else np.float64
        assert (arr.ndim == 1 and arr.dtype == want
                and arr.flags["C_CONTIGUOUS"]), (
            f"{name}: expected a C-contiguous 1-D {np.dtype(want)} array, got "
            f"{arr.ndim}-D {arr.dtype}, "
            f"C_CONTIGUOUS={arr.flags['C_CONTIGUOUS']}")

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
        **branch,
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


# ----------------------------------------------------------------------
# v2: every optional branch live at once
# ----------------------------------------------------------------------
# The four arms of the ablation test: the branches a full-physics step can be
# decomposed into, each dropped on both sides at the same time.
ABLATIONS = (
    ("pml", ("damp_e", "damp_h")),
    ("lossy", ("loss_num", "loss_den")),
    ("pec", ("pec_idx",)),
    ("source", ("j",)),
)


def _require_golden_v2():
    if not os.path.exists(GOLDEN_V2):
        pytest.fail(
            f"golden file {GOLDEN_V2} is missing; regenerate it with "
            "python3 evidence/termination/make_cpp_golden.py --v2"
        )


def _branch_arrays(z, drop=()):
    """The six optional arguments, as the strict binding declares them.

    Dropped names come back as ``None`` rather than absent, so every call site
    states every argument explicitly and an arm that misspelled a name would
    show up as "no difference" instead of passing through unnoticed.
    """
    out = {}
    for name in _BRANCH_KEYS:
        if name in drop:
            out[name] = None
            continue
        dtype = INDEX_DTYPE if name == "pec_idx" else np.float64
        out[name] = np.ascontiguousarray(z[name], dtype=dtype)
    return out


class _StoredPML:
    """Replays the two multiplier vectors the kernel was fed, in place.

    ``PML.damp_e`` is literally ``e *= self.multipliers(dt)[0]`` and
    ``PML.damp_h`` is ``h *= self.multipliers(dt)[1]``, with no other arithmetic
    in either (``emfit/pml.py:716-735``).  Handing the Python reference the same
    two vectors therefore performs the identical operation, without having to
    rebuild a PML object whose multipliers would have to agree to the last bit.
    """

    def __init__(self, damp_e, damp_h):
        self._damp_e = damp_e
        self._damp_h = damp_h

    def damp_e(self, e, dt=None):
        e *= self._damp_e
        return e

    def damp_h(self, h, dt=None):
        h *= self._damp_h
        return h


def _python_v2_stepper(z, drop=()):
    """``(e, h, advance)`` for a live Python reference run of the stored system.

    No golden vector is read: the operators are rebuilt from the stored CSR
    arrays, so this is a reference run and not a replay of the file.
    """
    import scipy.sparse as sp

    from emfit.evolve import step_explicit

    e = np.array(z["e0"], dtype=np.float64, order="C")
    h = np.array(z["h0"], dtype=np.float64, order="C")
    C = sp.csr_matrix(
        (z["C_data"], z["C_indices"], z["C_indptr"]),
        shape=tuple(int(v) for v in z["C_shape"]))
    # The file carries no ``C_tilde_csr_shape``: that copy is the dual curl, so
    # its shape is the transpose of C's.
    C_tilde_csr = sp.csr_matrix(
        (z["C_tilde_csr_data"], z["C_tilde_csr_indices"],
         z["C_tilde_csr_indptr"]),
        shape=tuple(int(v) for v in z["C_tilde_shape"]))
    inv_m_mu = np.array(z["inv_m_mu"], dtype=np.float64, order="C")
    inv_m_eps = np.array(z["inv_m_eps"], dtype=np.float64, order="C")
    dt = float(z["dt"])
    dropped = set(drop)

    def pick(name):
        if name in dropped:
            return None
        dtype = INDEX_DTYPE if name == "pec_idx" else np.float64
        return np.array(z[name], dtype=dtype, order="C")

    # The PML arm is all-or-nothing: step_explicit takes the layer object, so
    # dropping either multiplier means no PML at all on this side.
    pml = None
    if not ("damp_e" in dropped or "damp_h" in dropped):
        pml = _StoredPML(pick("damp_e"), pick("damp_h"))

    kwargs = dict(
        loss_num=pick("loss_num"),
        loss_den=pick("loss_den"),
        pml=pml,
        pec_idx=pick("pec_idx"),
        j=pick("j"),
    )

    def advance():
        return step_explicit(e, h, C, C_tilde_csr, inv_m_mu, inv_m_eps, dt,
                             **kwargs)

    return e, h, advance


def _python_v2_run(z, n_steps, drop=()):
    e, h, advance = _python_v2_stepper(z, drop=drop)
    for _ in range(n_steps):
        advance()
    return e, h


def test_cpp_matches_frozen_golden_v2_bit_for_bit():
    """Full-physics step, three steps, every optional argument supplied."""
    _require_golden_v2()
    with np.load(GOLDEN_V2) as z:
        e = np.array(z["e0"], dtype=np.float64, order="C")
        h = np.array(z["h0"], dtype=np.float64, order="C")
        branch = _branch_arrays(z)
        n_steps = int(z["n_steps"])
        assert n_steps >= 1

        for step_no in range(1, n_steps + 1):
            _kernel_step(z, e, h, **branch)
            _assert_bit_identical(e, z[f"e{step_no}"],
                                  f"C++ v2 e after step {step_no}")
            _assert_bit_identical(h, z[f"h{step_no}"],
                                  f"C++ v2 h after step {step_no}")


def test_cpp_matches_live_python_kernel_v2_bit_for_bit():
    """Second opinion: against a live ``step_explicit``, step by step."""
    _require_golden_v2()
    with np.load(GOLDEN_V2) as z:
        e_cpp = np.array(z["e0"], dtype=np.float64, order="C")
        h_cpp = np.array(z["h0"], dtype=np.float64, order="C")
        branch = _branch_arrays(z)
        e_py, h_py, advance = _python_v2_stepper(z)

        for step_no in range(1, int(z["n_steps"]) + 1):
            _kernel_step(z, e_cpp, h_cpp, **branch)
            advance()
            _assert_bit_identical(
                e_cpp, e_py, f"e, cpp vs live python (v2), step {step_no}")
            _assert_bit_identical(
                h_cpp, h_py, f"h, cpp vs live python (v2), step {step_no}")


def test_v2_golden_bookkeeping():
    """Every branch must be *engaged* in the file, not merely present."""
    _require_golden_v2()
    with np.load(GOLDEN_V2) as z:
        assert str(z["case"]) == "v2-full-physics", (
            f"unexpected case tag {str(z['case'])!r}: this is not the "
            "full-physics golden")
        n_edges = int(z["n_edges"])
        n_faces = int(z["n_faces"])

        for name, size in (("e0", n_edges), ("e3", n_edges),
                           ("damp_e", n_edges), ("loss_num", n_edges),
                           ("loss_den", n_edges), ("inv_m_eps", n_edges),
                           ("j", n_edges), ("h0", n_faces), ("h3", n_faces),
                           ("damp_h", n_faces), ("inv_m_mu", n_faces)):
            assert z[name].size == size, f"{name} has {z[name].size}, want {size}"

        # The PEC set is an int64 index array, not a bool mask, and the edges it
        # names really are zero in the final state.
        assert z["pec_idx"].dtype == INDEX_DTYPE, (
            f"pec_idx is {z['pec_idx'].dtype}, the binding declares int64")
        assert z["pec_idx"].size > 0, "the PEC branch would test nothing"
        assert np.all(z["e3"][z["pec_idx"]] == 0.0), (
            "pec_idx names edges that are not zero in e3: the PEC set and the "
            "state vector disagree")

        # A damping factor below 1 is what makes the PML branch active at all.
        assert np.any(z["damp_e"] < 1.0), "no edge is damped: PML is inert"
        assert np.any(z["damp_h"] < 1.0), "no face is damped: PML is inert"
        # loss_num == 1 for every edge would mean the file degenerated to the
        # lossless path, and the lossy branch would never be exercised.
        assert np.all(z["loss_num"] != 1.0), (
            "loss_num is 1 everywhere: the lossy Ampere branch is not engaged")
        assert np.all(z["loss_den"] != 1.0), (
            "loss_den is 1 everywhere: the lossy Ampere branch is not engaged")
        assert np.count_nonzero(z["j"]) > 0, "the source branch is inert"
        assert int(z["n_sigma"]) > 0, (
            "a zero-conductivity grid would leave the lossy branch inert")


@pytest.mark.parametrize("arm,dropped", ABLATIONS,
                         ids=[arm for arm, _ in ABLATIONS])
def test_v2_ablation_detects_each_branch(arm, dropped):
    """Dropping one branch must change the answer -- on both sides, equally.

    Two assertions per arm, and both are needed.  The kernel and the reference
    must agree *with the branch gone* (so the optional plumbing is right for
    that subset too), and that shared answer must differ from the full-physics
    golden by a non-zero amount (so the branch is load-bearing rather than
    passed in and ignored).
    """
    _require_golden_v2()
    with np.load(GOLDEN_V2) as z:
        n_steps = int(z["n_steps"])
        e_cpp = np.array(z["e0"], dtype=np.float64, order="C")
        h_cpp = np.array(z["h0"], dtype=np.float64, order="C")
        branch = _branch_arrays(z, drop=dropped)
        e_py, h_py = _python_v2_run(z, n_steps, drop=dropped)

        for _ in range(n_steps):
            _kernel_step(z, e_cpp, h_cpp, **branch)

        _assert_bit_identical(
            e_cpp, e_py, f"e, cpp vs python, v2 with the {arm} branch dropped")
        _assert_bit_identical(
            h_cpp, h_py, f"h, cpp vs python, v2 with the {arm} branch dropped")

        want_e = z[f"e{n_steps}"]
        want_h = z[f"h{n_steps}"]
        de, ie, ge, we = _worst(e_cpp, want_e)
        dh, ih, gh, wh = _worst(h_cpp, want_h)
        assert not np.array_equal(e_cpp, want_e) \
            and not np.array_equal(h_cpp, want_h), (
                f"dropping the {arm} branch left the {n_steps}-step state "
                "bit-identical to the full-physics golden, so that branch is "
                f"not covered by this file (e worst {de!r}, h worst {dh!r})")
        assert de > 0.0 and dh > 0.0, (
            f"{arm}: expected a non-zero difference; got e {de!r} at {ie} "
            f"({ge!r} vs {we!r}), h {dh!r} at {ih} ({gh!r} vs {wh!r})")


def test_v2_consecutive_steps_differ():
    """The golden's steps are distinct vectors, so agreement is a measurement."""
    _require_golden_v2()
    with np.load(GOLDEN_V2) as z:
        for step_no in range(1, int(z["n_steps"]) + 1):
            for name in ("e", "h"):
                prev = z[f"{name}{step_no - 1}"]
                cur = z[f"{name}{step_no}"]
                assert not np.array_equal(prev, cur), (
                    f"{name}{step_no - 1} and {name}{step_no} are the same "
                    "vector: that step is a no-op and compares nothing")


def test_bit_comparison_sees_a_one_ulp_difference():
    """Control for the comparator itself: one ULP must be caught.

    On the output side on purpose.  On the *input* side a single ULP is absorbed
    by this regime's rounding floor (|e| ~ 1e3 after one lossy step) -- a real
    property worth recording, but useless as a control; see
    ``test_v2_input_perturbation_propagates`` for the coarse version.
    """
    _require_golden_v2()
    with np.load(GOLDEN_V2) as z:
        expected = np.array(z["e3"], dtype=np.float64, order="C")
        bumped = expected.copy()
        bumped[0] = np.nextafter(bumped[0], np.inf)
        assert bumped[0] != expected[0]
        assert np.array_equal(bumped[1:], expected[1:])

        with pytest.raises(AssertionError) as excinfo:
            _assert_bit_identical(bumped, expected, "one-ULP bump of e3[0]")
        assert "1/133" in str(excinfo.value), (
            "the failure did not localise the single changed entry: "
            f"{excinfo.value}")


def test_v2_input_perturbation_propagates():
    """A coarse input change must reach the three-step output.

    Deliberately *not* one ULP: with |e| ~ 1e3 after the first lossy step, a
    single-ULP change to ``h0`` or ``e0`` is absorbed by rounding and the
    three-step output comes back bit-identical to the golden.  That is a
    property of the regime rather than a defect, and it is why the ULP control
    above lives on the output side.  The perturbation here is 1e-3 relative,
    ten orders of magnitude above that floor.
    """
    _require_golden_v2()
    with np.load(GOLDEN_V2) as z:
        n_steps = int(z["n_steps"])
        branch = _branch_arrays(z)
        e = np.array(z["e0"], dtype=np.float64, order="C")
        h = np.array(z["h0"], dtype=np.float64, order="C")
        # The largest input entry, so the change is well above the absolute
        # rounding floor of this system: h0 is O(1e-19) here, and scaling that
        # by 1e-3 is far too small to survive three steps.
        k = int(np.argmax(np.abs(e)))
        e[k] *= 1.0 + 1e-3

        for _ in range(n_steps):
            _kernel_step(z, e, h, **branch)

        de, ie, ge, we = _worst(e, z[f"e{n_steps}"])
        dh, ih, gh, wh = _worst(h, z[f"h{n_steps}"])
        assert de > 0.0 and dh > 0.0, (
            f"a 1e-3 relative change to e0[{k}] did not reach the {n_steps}-step "
            f"output: e worst {de!r} at {ie} ({ge!r} vs {we!r}), h worst "
            f"{dh!r} at {ih} ({gh!r} vs {wh!r}) -- the output does not depend "
            "on the input")

