// bindings.cpp -- pybind11 glue for emfit_core.  See CMakeLists.txt.
//
// Contract, deliberately strict:
//   * every array is requested as py::array_t<double> (or int64 for the sparse
//     index arrays) with c_style memory, and NO forcecast -- a float32 or
//     non-contiguous or int32 array raises instead of being silently converted.
//     A silent conversion is exactly the class of bug that would make a parity
//     test pass for the wrong reason.
//   * shapes are validated once, against the CSR views, before the kernel runs.
//   * the GIL is released around the numerical call; the kernel touches only
//     caller-owned buffers.
//
// NOTE: this file has never been compiled in this container -- cmake and
// pybind11 are absent -- so treat it as unbuilt source, not working code.

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <cstddef>
#include <string>
#include <vector>

#include "emfit_core.h"

namespace py = pybind11;

namespace {

using DArr = py::array_t<double, py::array::c_style>;
using IArr = py::array_t<long, py::array::c_style>;

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
void py_step_explicit(DArr e, DArr h,
                      DArr c_data, IArr c_idx, IArr c_ptr,
                      std::vector<long> c_shape,
                      DArr ct_data, IArr ct_idx, IArr ct_ptr,
                      std::vector<long> ct_shape,
                      const DArr& inv_m_mu, const DArr& inv_m_eps,
                      double dt, py::object j_obj) {
    if (c_shape.size() != 2 || ct_shape.size() != 2) {
        throw py::value_error("C_shape and C_tilde_shape must be (rows, cols)");
    }
    const long n_faces = c_shape[0];
    const long n_edges = c_shape[1];
    if (ct_shape[0] != n_edges || ct_shape[1] != n_faces) {
        throw py::value_error("C_tilde must be the (n_edges, n_faces) dual");
    }
    if (e.ndim() != 1 || e.size() != n_edges) throw py::value_error("bad e");
    if (h.ndim() != 1 || h.size() != n_faces) throw py::value_error("bad h");
    if (inv_m_eps.ndim() != 1 || inv_m_eps.size() != n_edges)
        throw py::value_error("bad inv_m_eps");
    if (inv_m_mu.ndim() != 1 || inv_m_mu.size() != n_faces)
        throw py::value_error("bad inv_m_mu");

    const emfit::Csr C = as_csr(c_data, c_idx, c_ptr, n_faces, n_edges, "C");
    const emfit::Csr Ct =
        as_csr(ct_data, ct_idx, ct_ptr, n_edges, n_faces, "C_tilde");

    const double* j = nullptr;
    DArr j_arr;  // must outlive the released-GIL section
    if (!j_obj.is_none()) {
        j_arr = DArr::ensure(j_obj);  // rejects wrong dtype/shape, no cast
        if (j_arr.ndim() != 1 || j_arr.size() != n_edges)
            throw py::value_error("bad j");
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
              "emfit.evolve.step_explicit); numerics UNVERIFIED until "
              "tests/test_cpp_parity.py runs against the golden data.";
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
