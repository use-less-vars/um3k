// emfit_core.h -- declarations for the compiled FIT update kernel.
//
// Deliberately free of pybind11 / CPython includes: this header is what
// src/emfit_core.cpp is compiled against, so the numerical translation unit can
// be syntax-checked (indeed, later, unit-tested) without Python headers.
#ifndef EMFIT_CORE_H
#define EMFIT_CORE_H

#include <cstddef>

namespace emfit {

// Raw CSR view of a sparse matrix, row-major, column indices ascending within
// each row (scipy's invariant for C/Ct as built by emfit.operators).
struct Csr {
    const double* data = nullptr;
    const long* indices = nullptr;  // column indices
    const long* indptr = nullptr;   // row pointers, length n_rows + 1
    long n_rows = 0;
    long n_cols = 0;
};

// One leapfrog step of the FIT scheme -- the C++ twin of the Python reference
// emfit.evolve.step_explicit().  Mutates e and h in place.
//
//   h -= dt * inv_m_mu * (C e)
//   ce = Ct h [- j]
//   e += dt * inv_m_eps * ce
//
// The PML damping and the PEC reset are NOT part of this kernel: it is the
// explicit, lossless core only (see docs/design/cpp-kernel-status-2026-11-09.md
// for what is missing and why PML comes first).
//
// j may be nullptr (no source).  All vectors are length n_edges (e, inv_m_eps,
// j) or n_faces (h, inv_m_mu).  C is (n_faces, n_edges); Ct is
// (n_edges, n_faces).
void step_explicit(double* e,
                   double* h,
                   const Csr& C,
                   const Csr& Ct,
                   const double* inv_m_mu,
                   const double* inv_m_eps,
                   double dt,
                   const double* j);

}  // namespace emfit

#endif  // EMFIT_CORE_H
