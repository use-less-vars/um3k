// emfit_core.cpp -- compiled FIT leapfrog update, C++ twin of the Python
// reference emfit.evolve.step_explicit().
//
// WHEN, and only when, a parity test says this agrees with the Python kernel
// *bit for bit*, this becomes the hot path.  Until then Python is the reference
// and this file is an untested port.
//
// Why the loop below is written in this exact shape
// -------------------------------------------------
// The port claims bit-identical results, not merely "close".  In IEEE-754
// double arithmetic a dot product depends on the order of its additions, so the
// accumulator must visit the non-zeros of a row in the same order SciPy's
// CSR mat-vec does: ascending column index, one sequential accumulator per row,
// starting from +0.0.  Hence:
//
//   * one scalar accumulator per output entry, never a tree/partial-sum split;
//   * no `reduction` clause and no atomics anywhere in this file;
//   * no compiler reassociation: built with -O3 only (see CMakeLists.txt),
//     never -ffast-math / -fassociative-math, which would let the optimiser
//     re-parent the additions and silently change the last bit.
//
// Parallelism is over independent rows (schedule(static) so the partitioning is
// reproducible too); rows never interact, so the result is a pure function of
// the input bytes regardless of the thread count.

#include "emfit_core.h"

namespace emfit {

namespace {

// y[r] = sum_k A.data[k] * x[A.indices[k]] for row r, in stored (ascending
// column) order.  Returned rather than stored so the caller can fuse the
// scaling into the update without a temporary vector.
inline double row_dot(const Csr& A, long r, const double* x) {
    double acc = 0.0;
    for (long k = A.indptr[r]; k < A.indptr[r + 1]; ++k) {
        acc += A.data[k] * x[A.indices[k]];
    }
    return acc;
}

}  // namespace

void step_explicit(double* e,
                   double* h,
                   const Csr& C,
                   const Csr& Ct,
                   const double* inv_m_mu,
                   const double* inv_m_eps,
                   double dt,
                   const double* j) {
    const long n_faces = C.n_rows;
    const long n_edges = C.n_cols;

    // Faraday: h -= dt * (inv_m_mu * (C e)).
    // Same operation order as Python: the mat-vec, then the elementwise
    // multiply by inv_m_mu, then by dt, then the subtraction.
#pragma omp parallel for schedule(static)
    for (long r = 0; r < n_faces; ++r) {
        const double ce = row_dot(C, r, e);
        h[r] -= dt * (inv_m_mu[r] * ce);
    }

    // Ampere: e += dt * (inv_m_eps * (Ct h - j)).
#pragma omp parallel for schedule(static)
    for (long r = 0; r < n_edges; ++r) {
        double ce = row_dot(Ct, r, h);
        if (j != nullptr) {
            ce -= j[r];
        }
        e[r] += dt * (inv_m_eps[r] * ce);
    }
}

}  // namespace emfit
