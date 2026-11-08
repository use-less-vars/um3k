// emfit_core.cpp -- compiled FIT leapfrog update, C++ twin of the Python
// reference emfit.evolve.step_explicit().
//
// WHEN, and only when, a parity test says this agrees with the Python kernel
// *bit for bit*, this becomes the hot path.  Today that is true of the lossless,
// source-free path (tests/test_cpp_parity.py, 3/3, max|diff| 0.0); the PML,
// lossy, PEC and source branches added here are measured by hand, not by any
// committed test.
//
// Why the loops below are written in this exact shape
// ---------------------------------------------------
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
// The same rule applies to the optional branches, and it is why they are spelled
// out step by step instead of being folded into the loops that surround them:
//
//   * every damping step is ONE multiply per element by a stored factor
//     (`h[r] *= damp_h[r]`), never a fused (a*b)*c nor a precomputed product,
//     and it happens at the point in the sequence where Python applies it;
//   * the lossy Ampere branch keeps Python's three in-place statements --
//     `e *= loss_num`, `e += ce`, `e *= loss_den` -- as three separate rounded
//     operations, which is what the Python comment at evolve.py:123-124 says the
//     single expression is bit-identical to;
//   * the lossless branch keeps Python's multiply order, (inv_m_eps * ce) then
//     * dt, then the addition.
//
// Parallelism is over independent rows (schedule(static) so the partitioning is
// reproducible too); rows never interact, so the result is a pure function of
// the input bytes regardless of the thread count.  The two damping loops and the
// PEC reset are parallel for the same reason: every output element depends on
// that element only (PEC touches a zeroed list of distinct-or-not indices, each
// store idempotent).

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
                   const double* loss_num,
                   const double* loss_den,
                   const double* damp_e,
                   const double* damp_h,
                   const long* pec_idx,
                   long n_pec,
                   const double* j) {
    const long n_faces = C.n_rows;
    const long n_edges = C.n_cols;

    // 1. Faraday: h -= dt * (inv_m_mu * (C e)).        [evolve.py:114]
    // Same operation order as Python: the mat-vec, then the elementwise
    // multiply by inv_m_mu, then by dt, then the subtraction.
#pragma omp parallel for schedule(static)
    for (long r = 0; r < n_faces; ++r) {
        const double ce = row_dot(C, r, e);
        h[r] -= dt * (inv_m_mu[r] * ce);
    }

    // 2. PML damping of h, BEFORE the dual curl is taken.  [evolve.py:115-116]
    // Python: pml.damp_h(h, dt) -> `h *= f` with f = multipliers(dt)[1].
    if (damp_h != nullptr) {
#pragma omp parallel for schedule(static)
        for (long r = 0; r < n_faces; ++r) {
            h[r] *= damp_h[r];
        }
    }

    // 3. Ampere: ce = Ct h, minus the source, then one of the two e updates.
    //                                           [evolve.py:117-127]
    // The branch is chosen per call, not per element, exactly as in Python:
    // `if loss_den is None: e += dt * (inv_m_eps * ce) else: ...`.
    if (loss_den == nullptr) {
#pragma omp parallel for schedule(static)
        for (long r = 0; r < n_edges; ++r) {
            double ce = row_dot(Ct, r, h);
            if (j != nullptr) {
                ce -= j[r];
            }
            e[r] += dt * (inv_m_eps[r] * ce);
        }
    } else {
        // loss_num must be non-null whenever loss_den is; the binding refuses
        // the one-sided call rather than letting this dereference run.
#pragma omp parallel for schedule(static)
        for (long r = 0; r < n_edges; ++r) {
            double ce = row_dot(Ct, r, h);
            if (j != nullptr) {
                ce -= j[r];
            }
            e[r] *= loss_num[r];
            e[r] += ce;
            e[r] *= loss_den[r];
        }
    }

    // 4. PML damping of e, AFTER the Ampere update and BEFORE the PEC reset.
    //                                           [evolve.py:128-129]
    // Python: pml.damp_e(e, dt) -> `e *= f` with f = multipliers(dt)[0].
    if (damp_e != nullptr) {
#pragma omp parallel for schedule(static)
        for (long r = 0; r < n_edges; ++r) {
            e[r] *= damp_e[r];
        }
    }

    // 5. PEC: reset the constrained edge voltages to exactly +0.0, last.
    //                                           [evolve.py:130-131]
    // Python: e[pec_idx] = 0.0.  Idempotent per index and order-independent
    // (every store writes the same value), so a plain serial loop is exact.
    for (long k = 0; k < n_pec; ++k) {
        e[pec_idx[k]] = 0.0;
    }
}

}  // namespace emfit
