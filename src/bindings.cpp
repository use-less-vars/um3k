// bindings.cpp -- pybind11 glue for emfit_core.  See CMakeLists.txt.
//
// Contract, deliberately strict:
//   * every array parameter must be a numpy array of the exact dtype the kernel
//     consumes (float64, or int64 for the sparse index arrays), C-contiguous,
//     and -- where the kernel updates it in place -- writeable.  There is NO
//     forcecast: float32, int32, non-contiguous and read-only inputs raise
//     instead of being silently converted or copied.  A silent conversion is
//     exactly the class of bug that would make a parity test pass for the wrong
//     reason.
//   * the dtype/contiguity check is done by hand, against the py::object, so
//     the exception names the parameter, what arrived and what was required.
//     Leaving it to overload resolution produces a list of every candidate
//     pybind11 knows -- all of it true, none of it usable.
//   * the (rows, cols) shapes are std::vector<py::ssize_t>: that is the type
//     pybind11 casts Python ints through, and <pybind11/stl.h> supplies the
//     caster for it.  Without that include the parameter has no caster at all
//     and every call fails, at overload resolution, with no mention of shapes.
//   * shapes are validated once, against the CSR views, before the kernel runs.
//   * the GIL is released around the numerical call; the kernel touches only
//     caller-owned buffers.
//
// STATUS: built, and exercised against golden data.  Compiled here with
// g++ (Debian 14.2.0-19) 14.2.0 against pybind11 3.1.0, flags
// -O3 -fopenmp -std=c++17 -shared -fPIC -Wall -Wextra: 0 warnings, one
// artifact (emfit_core.cpython-312-x86_64-linux-gnu.so).  Runtime parity is
// exact, not approximate -- 3/3 tests in tests/test_cpp_parity.py pass, and the
// kernel is bit-identical (assert_array_equal; 0 of 98 e and 0 of 133 h
// entries differing) to BOTH the frozen golden vectors in
// tests/data/cpp_golden_step.npz and the live Python reference
// emfit.evolve.step_explicit, over all 3 recorded steps.

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstddef>
#include <string>
#include <vector>

#include "emfit_core.h"

namespace py = pybind11;

namespace {

using DArr = py::array_t<double, py::array::c_style>;
using IArr = py::array_t<long, py::array::c_style>;

// What the caller actually handed over, for the error message below.
std::string describe(const py::object& obj) {
    if (!py::isinstance<py::array>(obj)) {
        return std::string(py::str(py::type::of(obj)).cast<std::string>()) +
               ", which is not a numpy array";
    }
    const py::array a = py::reinterpret_borrow<py::array>(obj);
    const auto flags = a.flags();
    std::string s = "dtype " + py::str(a.dtype()).cast<std::string>();
    s += (flags & py::array::c_style) ? ", C-contiguous" : ", NOT C-contiguous";
    s += a.writeable() ? ", writeable" : ", read-only";
    return s;
}

[[noreturn]] void reject(const char* name, const char* want, const py::object& obj,
                         const char* why) {
    throw py::type_error(std::string(name) + ": expected " + want + ", got " +
                         describe(obj) + " [" + why + "]");
}

// float64, C-contiguous, and writeable when the kernel writes through it.
DArr as_f64(const py::object& obj, const char* name, bool writable) {
    const char* want = writable ? "a C-contiguous, writeable numpy float64 array"
                                : "a C-contiguous numpy float64 array";
    if (!py::isinstance<py::array>(obj)) {
        reject(name, want, obj, "not an array");
    }
    const py::array a = py::reinterpret_borrow<py::array>(obj);
    const auto flags = a.flags();
    if (a.dtype().num() != py::dtype::of<double>().num()) {
        reject(name, want, obj, "dtype is not float64");
    }
    if (!(flags & py::array::c_style)) {
        reject(name, want, obj, "not C-contiguous; pass np.ascontiguousarray(a)");
    }
    if (writable && !a.writeable()) {
        reject(name, want, obj, "read-only, and step_explicit updates it in place");
    }
    return DArr::ensure(a);  // dtype and layout are already exact: pure re-wrap
}

// int64 (= C long on LP64), C-contiguous; the CSR index arrays.
IArr as_index(const py::object& obj, const char* name) {
    const char* want = "a C-contiguous numpy int64 array";
    if (!py::isinstance<py::array>(obj)) {
        reject(name, want, obj, "not an array");
    }
    const py::array a = py::reinterpret_borrow<py::array>(obj);
    const auto flags = a.flags();
    if (a.dtype().num() != py::dtype::of<long>().num()) {
        reject(name, want, obj, "dtype is not int64");
    }
    if (!(flags & py::array::c_style)) {
        reject(name, want, obj, "not C-contiguous; pass np.ascontiguousarray(a)");
    }
    return IArr::ensure(a);
}

// Length check, with the same legibility rule as the dtype check.
void require_len(const py::array& a, const char* name, long want) {
    if (a.ndim() == 1 && a.size() == want) {
        return;
    }
    throw py::value_error(std::string(name) + ": expected a 1-D array of length " +
                          std::to_string(want) + ", got " +
                          std::to_string(a.ndim()) + "-D of length " +
                          std::to_string(a.size()));
}

emfit::Csr as_csr(const DArr& data, const IArr& indices, const IArr& indptr,
                  long n_rows, long n_cols, const char* name) {
    if (data.ndim() != 1 || indices.ndim() != 1 || indptr.ndim() != 1) {
        throw py::value_error(std::string(name) + ": expected 1-D CSR arrays");
    }
    if (data.size() != indices.size()) {
        throw py::value_error(std::string(name) +
                              ": data and indices must have equal length");
    }
    if (indptr.size() != n_rows + 1) {
        throw py::value_error(std::string(name) +
                              ": indptr must have n_rows + 1 entries");
    }
    emfit::Csr m;
    m.data = data.data();
    m.indices = indices.data();
    m.indptr = indptr.data();
    m.n_rows = n_rows;
    m.n_cols = n_cols;
    return m;
}

// step_explicit(e, h, C_data, C_indices, C_indptr, C_shape,
//               C_tilde_data, C_tilde_indices, C_tilde_indptr, C_tilde_shape,
//               inv_m_mu, inv_m_eps, dt, j=None)
//
// The arrays arrive as py::object on purpose: that is the only way to say what
// was received about *this* argument instead of failing overload resolution.
void py_step_explicit(const py::object& e_obj, const py::object& h_obj,
                      const py::object& c_data_obj, const py::object& c_idx_obj,
                      const py::object& c_ptr_obj,
                      const std::vector<py::ssize_t>& c_shape,
                      const py::object& ct_data_obj, const py::object& ct_idx_obj,
                      const py::object& ct_ptr_obj,
                      const std::vector<py::ssize_t>& ct_shape,
                      const py::object& inv_m_mu_obj,
                      const py::object& inv_m_eps_obj, double dt,
                      const py::object& j_obj) {
    if (c_shape.size() != 2 || ct_shape.size() != 2) {
        throw py::value_error("C_shape and C_tilde_shape must be (rows, cols)");
    }
    // LP64: py::ssize_t and the `long` index type in emfit_core.h are both
    // 64-bit, which is also what numpy spells int64.  State the assumption
    // rather than imply it: on a 32-bit `long` the cast below would truncate.
    const long n_faces = static_cast<long>(c_shape[0]);
    const long n_edges = static_cast<long>(c_shape[1]);
    if (ct_shape[0] != n_edges || ct_shape[1] != n_faces) {
        throw py::value_error("C_tilde must be the (n_edges, n_faces) dual");
    }

    DArr e = as_f64(e_obj, "e", /*writable=*/true);
    DArr h = as_f64(h_obj, "h", /*writable=*/true);
    DArr c_data = as_f64(c_data_obj, "C_data", /*writable=*/false);
    IArr c_idx = as_index(c_idx_obj, "C_indices");
    IArr c_ptr = as_index(c_ptr_obj, "C_indptr");
    DArr ct_data = as_f64(ct_data_obj, "C_tilde_data", /*writable=*/false);
    IArr ct_idx = as_index(ct_idx_obj, "C_tilde_indices");
    IArr ct_ptr = as_index(ct_ptr_obj, "C_tilde_indptr");
    DArr inv_m_mu = as_f64(inv_m_mu_obj, "inv_m_mu", /*writable=*/false);
    DArr inv_m_eps = as_f64(inv_m_eps_obj, "inv_m_eps", /*writable=*/false);

    require_len(e, "e", n_edges);
    require_len(h, "h", n_faces);
    require_len(inv_m_eps, "inv_m_eps", n_edges);
    require_len(inv_m_mu, "inv_m_mu", n_faces);

    const emfit::Csr C = as_csr(c_data, c_idx, c_ptr, n_faces, n_edges, "C");
    const emfit::Csr Ct =
        as_csr(ct_data, ct_idx, ct_ptr, n_edges, n_faces, "C_tilde");

    const double* j = nullptr;
    DArr j_arr;  // must outlive the released-GIL section
    if (!j_obj.is_none()) {
        j_arr = as_f64(j_obj, "j", /*writable=*/false);
        require_len(j_arr, "j", n_edges);
        j = j_arr.data();
    }

    {
        py::gil_scoped_release release;
        emfit::step_explicit(e.mutable_data(), h.mutable_data(), C, Ct,
                             inv_m_mu.data(), inv_m_eps.data(), dt, j);
    }
}

}  // namespace

PYBIND11_MODULE(emfit_core, m) {
    m.doc() = "Compiled FIT leapfrog kernel (C++ port of "
              "emfit.evolve.step_explicit).  Verified bit-identical (max|diff| "
              "0.0) to the Python reference over the frozen golden data: 3/3 "
              "tests in tests/test_cpp_parity.py pass.  Build from source (see "
              "BUILD_COMMANDS there); `pip install -e .` was not exercised in "
              "this container.";
    m.def("step_explicit", &py_step_explicit,
          py::arg("e"), py::arg("h"),
          py::arg("C_data"), py::arg("C_indices"), py::arg("C_indptr"),
          py::arg("C_shape"),
          py::arg("C_tilde_data"), py::arg("C_tilde_indices"),
          py::arg("C_tilde_indptr"), py::arg("C_tilde_shape"),
          py::arg("inv_m_mu"), py::arg("inv_m_eps"), py::arg("dt"),
          py::arg("j") = py::none(),
          "One FIT leapfrog step, in place on e and h.");
}
