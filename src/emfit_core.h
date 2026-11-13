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
// The order below IS the Python statement order (emfit/evolve.py) and may not be
// reordered, fused or precomputed:
//
//   h -= dt * (inv_m_mu * (C e))          evolve.py:114      Faraday
//   [h *= damp_h]                         evolve.py:115-116  pml.damp_h
//   ce = Ct h  [- j]                      evolve.py:117-119
//   e += dt * (inv_m_eps * ce)            evolve.py:121      lossless Ampere
//     or e *= loss_num; e += ce; e *= loss_den   evolve.py:125-127  lossy Ampere
//   [e *= damp_e]                         evolve.py:128-129  pml.damp_e
//   e[pec_idx] = 0.0                      evolve.py:130-131  PEC reset
//
// An optional piece is ABSENT by passing nullptr (n_pec == 0 for the PEC index
// list), and the corresponding step then does nothing -- exactly what Python
// does for None.  Which Ampere branch runs is selected by loss_den being
// non-null, as in Python (`if loss_den is None`); loss_num is read only when
// loss_den is non-null.
//
// damp_e / damp_h are not the emfit.pml.PML object: they are the elementwise
// multiplier arrays that PML.damp_e / PML.damp_h apply, i.e.
// pml.multipliers(dt)[0] and pml.multipliers(dt)[1], both float64.  The kernel
// does one multiply per element by those arrays, once each, at the two points
// shown above; it does not recompute them, because the Python kernel does not
// recompute them either -- it multiplies by exactly these stored factors.
//
// All vectors are length n_edges (e, inv_m_eps, loss_num, loss_den, damp_e, j)
// or n_faces (h, inv_m_mu, damp_h).  C is (n_faces, n_edges); Ct is
// (n_edges, n_faces).
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
                   const double* j);

// The thread team step_explicit() runs its parallel loops on.  One thread by
// default, so an inherited OMP_NUM_THREADS cannot silently change what a call
// costs (DR-42).  set_num_threads() clamps n to at least 1, applies it to the
// OpenMP runtime and returns the count now in force.
int get_num_threads();
int set_num_threads(int n);

}  // namespace emfit

#endif  // EMFIT_CORE_H
