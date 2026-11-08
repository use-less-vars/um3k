# Porting the FDTD time-stepper to C++: technical spec

2026-11-09

Status: proposal. Nothing here has been implemented or measured except where it says MEASURED.
Two kinds of statement appear below and they must not be confused: what the existing code does
(cited by `file:line`), and what a port *should* do (my recommendation, argued). Where I could not
verify something in the code it is tagged **UNVERIFIED**, and those tags are collected at the end.

## 0. What the code actually does today

### 0.1 The march loop

The loop that drives the build_A study is in `emfit/studies.py:3224`:

```
for n in range(nsteps):
    ...
    current[:] = 0.0
    current[port_edges] = float(drive) * ramp * np.sin(2.0 * np.pi * f0 * n * dt) * launch_profile
    stepper.step(current)
    if n < n_warm:
        continue
    for i, col in enumerate(columns):
        signals[i] = edge_path_voltage(stepper.e, col)
    ...
```

inside `microstrip_wave`, declared at `emfit/studies.py:2488`. So Python owns the loop, the
excitation waveform, the probe extraction and the DFT, and calls one method per step.

The update itself is `FITStepper.step`, `emfit/evolve.py:186-207`:

| line | operation |
|---|---|
| `evolve.py:191` | `self.h -= self.dt * (self.inv_m_mu * (self.C @ self.e))` — H from curl E |
| `evolve.py:192-193` | `self.pml.damp_h(self.h, self.dt)` — multiply H by the face factor |
| `evolve.py:194` | `ce = self.C_tilde @ self.h` — curl H |
| `evolve.py:195-196` | `ce = ce - j` — subtract the source current |
| `evolve.py:197-200` | `self.e += self.dt * (self.inv_m_eps * ce)`, or the lossy form `self.e = (self.e * self.loss_num + ce) * self.loss_den` |
| `evolve.py:201-202` | `self.pml.damp_e(self.e, self.dt)` |
| `evolve.py:203-204` | `self.e[self.pec_idx] = 0.0` |
| `evolve.py:205-206` | `self.time += self.dt; self.n += 1` |

That eight-line method is the entire hot path. Everything else in a run is setup, extraction or
bookkeeping.

### 0.2 The field arrays: two, not six

There are exactly two field arrays, both one-dimensional, both `float64`, both C-contiguous
(`emfit/evolve.py:168-169`):

- `self.e = np.zeros(self.C.shape[1], dtype=np.float64)` — length `n_edges` = 906,144, primal edge
  voltages [V], at integer time steps.
- `self.h = np.zeros(self.C.shape[0], dtype=np.float64)` — length `n_faces` = 886,676, dual edge
  magnetic voltages [A], at half time steps.

There are no separate `Ex/Ey/Ez` arrays. The three components are concatenated blocks of one flat
vector, addressed through fixed offsets `off_ex, off_ey, off_ez` and the index maps in
`emfit/operators.py:90-104`:

```
idx_ez(i,j,k) = off_ez + (i % nxn)*nyn*nz  + (j % nyn)*nz  + (k % nz)
idx_fx(i,j,k) = off_fx + (i % nxn)*ny*nz   + (j % ny)*nz   + (k % nz)
idx_fy(i,j,k) = off_fy + (i % nx)*nyn*nz   + (j % nyn)*nz  + (k % nz)
idx_fz(i,j,k) = off_fz + (i % nx)*ny*nzn   + (j % ny)*nzn  + (k % nzn)
```

From those formulas, and from the two counts the artefact records (`n_edges` = 906,144,
`n_faces` = 886,676), the extents and strides are fully determined. With `nx=62, ny=212, nz=22`
and the code's node-layer convention `nxn=63, nyn=213, nzn=23`, the component extents must be

| block | extent | count | stride i | stride j | stride k |
|---|---|---|---|---|---|
| `e` ex | nx × nyn × nzn | 303,738 | nyn·nzn = 4,899 | nzn = 23 | 1 |
| `e` ey | nxn × ny × nzn | 307,188 | ny·nzn = 4,876 | nzn = 23 | 1 |
| `e` ez | nxn × nyn × nz | 295,218 | nyn·nz = 4,686 | nz = 22 | 1 |
| `h` fx | nxn × ny × nz | 293,832 | ny·nz = 4,664 | nz = 22 | 1 |
| `h` fy | nx × nyn × nz | 290,532 | nyn·nz = 4,686 | nz = 22 | 1 |
| `h` fz | nx × ny × nzn | 302,312 | ny·nzn = 4,876 | nzn = 23 | 1 |

The two column totals are 906,144 and 886,676, matching `n_edges` and `n_faces` exactly, which is
what makes this table believable rather than guessed. Note three things it already tells you and
that a port must not paper over: **the six blocks have three different extents**, **the j-stride is
23 in the three blocks that are differenced in `y` (`e` ex, `e` ey, `h` fz) and 22 in the three
that are not (`e` ez, `h` fx, `h` fy)**, and **`k` is the fastest axis in all six**.
A kernel that hard-codes one stride set will be silently wrong in four of the six blocks.

### 0.3 E and H are updated by sparse mat-vec, not by a stencil loop

`self.C` is a **sparse CSR matrix** (built at `emfit/operators.py:170`, `curl()`; `curl_dual()` at
`operators.py:242-247` is `C.T` as a zero-copy view sharing `C.data`, with a comment saying so).
`evolve.py:191` and `:194` are therefore SciPy sparse mat-vecs, not six nested loops.

This matters for the spec in two opposite ways. It is the reason a structured stencil kernel is
worth writing: a mat-vec on this grid does one indirect gather per nonzero, plus the CSR index
reads, whereas the same operator on a structured grid is four (faces) or four (edges) neighbouring
loads at fixed strides. And it is the reason the port must be *validated* against the matrices: the
CSR triplets are the authoritative statement of which edges each face sums and with what sign, so
the structured kernel's incidence table should be *generated from* `C` once at setup, not retyped
from a textbook. **UNVERIFIED**: I did not read the row/column/sign construction at
`operators.py:170-240`, and I did not count the nonzeros per row. I am treating the sign pattern as
"whatever the CSR triplets say" throughout.

### 0.4 The leapfrog convention (confirmed)

`emfit/evolve.py:13-18` states the scheme exactly:

```
h^{n+1/2} = h^{n-1/2} - dt * (1/m_mu) * (C e^n)
e^{n+1}   = [ (m_eps/dt - m_sigma/2) e^n + (C~ h^{n+1/2} - j) ] / (m_eps/dt + m_sigma/2)
e^{n+1}[PEC] = 0
```

So **E lives at integer times on primal edges and H at half times on dual faces**, and the Ampere
law is trapezoidal (Crank–Nicolson) in time, elementwise, which the module docstring (`evolve.py:20-31`)
argues for because it is unconditionally stable for any non-negative conductance, whereas an
explicit `-dt*m_sigma*e` term would need `dt*m_sigma/m_eps < 2`. The convention is also visible in
the attributes: `e` is documented at `self.time` and `h` at `self.time - dt/2` (`evolve.py:110-113`).

### 0.5 The PML: two constant vectors, no auxiliary state

This is the single most important fact for the port, so it is worth being blunt: **the PML here
needs no per-step memory at all.**

- `emfit/pml.py:402` `class PML`. `:538` `self.sigma_e = self._sigma_edges()` — a length-`n_edges`
  conductivity [S/m], "zero on the whole physical interior, a sum of graded profiles inside the
  layers" (`pml.py:459-468`). `:539` `self.sigma_m = self._sigma_faces() * (MU0/EPS0)`, length
  `n_faces`.
- The profile is polynomial, `pml.py:562`: `sigma_max[axis] * s**order`, with
  `sigma_max = -(order+1)*ln(target)/d` (`pml.py:535`), `order=2`, `target=1e-4` at the study's
  call site (`studies.py:3009-3010`).
- Application is a **diagonal multiplication**: `multipliers(dt)` at `pml.py:662-694` returns
  `(exp(-sigma_e*dt/EPS0), exp(-sigma_m*dt/MU0))`, cached per `dt`; `damp_e` (`pml.py:716-726`) does
  `e *= f` and `damp_h` (`pml.py:727-738`) does `h *= f`.

So the layer costs two extra `float64` vectors of the same length as `e` and `h`, computed once
before the march and constant thereafter, and two extra elementwise multiplies per step. There is
no split field, no auxiliary differential equation, no convolution state, no per-step coefficient
recomputation. For the kernel this is a gift: the PML does not complicate memory layout at all, and
it does not prevent bit-for-bit reproduction.

Two honest caveats. First, the multipliers are `exp(...)`, not the trapezoidal ratio; the docstring
at `pml.py:675-682` explains why (`(1 - s dt/2eps)/(1 + s dt/2eps)` goes negative once the grading
pushes `sigma_max` far enough, and a sign flip every step is a Nyquist oscillation, not a decay).
Second, because the factor is `1.0` exactly in the interior, the interior is untouched bit for bit —
which is what makes a "PML off vs PML on with a zero layer" identity test possible.

### 0.6 Port excitation and the series load: both precomputable, no callbacks

**Port.** The driven edges are a static index list built once, before the loop:
`studies.py:3041-3042`

```
port_edges = np.unique(np.concatenate(
    [column_path(cc, ix_port, int(j), 0, k_strip) for j in range(j0, j1 + 1)]))
```

and the waveform is a pure function of the step index: `current[port_edges] = drive * ramp *
sin(2π f0 n dt) * launch_profile` (`studies.py:3237-3240`; the pulse arm uses `ricker(n*dt, ...)`).
The source enters the update as a soft current subtracted from curl H at `evolve.py:195-196`.

**Series load.** `studies.py:2916-2942`: for `kind == "series_r"` the load takes the `E_x` edges of
the cut column (`cc.idx_ex([ix_load], j_points, k_strip).ravel()`), frees them from PEC
(`pec[edges] = False`), and puts a conductance on them:

```
sigma[edges] += 1.0 / (edges.size * float(load.value))
```

which becomes `m_sigma`. `FITStepper.__init__` (`evolve.py:146-157`) then folds that into two
constant vectors, `loss_num = m_eps/dt - m_sigma/2` and `loss_den = 1/(m_eps/dt + m_sigma/2)`, and
the per-step cost is the elementwise expression at `evolve.py:200`. The module docstring puts the
design intent plainly (`evolve.py:8-11`): "a load is nothing but a conductance between two edges, so
the stepper never has to learn what a board is."

**Consequence for the interface: the kernel needs no callbacks.** Everything time-varying is one
scalar per step (the drive), and everything spatial is a constant index list or a constant vector.
The kernel signature can be

```
step(e, h, inv_m_eps, inv_m_mu, loss_num|null, loss_den|null,
     e_factor, h_factor, pec_idx[npec], src_idx[nsrc], src_val,
     C_triplets, n_triplets) -> void
```

called once per step. Probes, DFT accumulation, station voltages and current extraction stay in
Python: they are O(n_stations) per step, not O(cells), and moving them would buy nothing.

One thing in the current loop is worth naming because a port should delete it: `current[:] = 0.0`
at `studies.py:3233` writes 906,144 doubles (7.25 MB) every step to zero a vector that is nonzero on
a few hundred edges. In a kernel that takes `src_idx` and `src_val`, that memset disappears.

### 0.7 The measured baseline

From `evidence/termination/build_A_50ohm.json`, all MEASURED on 2026-11-08:

- `meta.wall_total_s` = **37.73064746707678** s
- `geometry.cells` = **289,168** (= nx·ny·nz = 62·212·22)
- `run.kwargs.nsteps` = **2400**
- `geometry.n_edges` = 906,144, `geometry.n_faces` = 886,676, `geometry.dt` = 7.626299478123987e-13 s
- `geometry.cell_m` = 0.0004 m, `n_pml` = 6

Arithmetic, done here rather than trusted:

```
cell-updates      = 289,168 × 2,400 = 694,003,200
wall              = 37.73064746707678 s
cell-updates/s    = 694,003,200 / 37.73064746707678 = 18,393,620  ≈ 1.84e7 per second
```

That figure is the one asked for, and it is MEASURED — but it is an **end-to-end** figure: the wall
clock includes setup, the mode solve, every Python probe extraction, and the DFT. Three derived
numbers make it interpretable:

```
unknown-updates/step = 906,144 + 886,676 = 1,792,820
total                = 1,792,820 × 2,400 = 4,302,768,000
unknown-updates/s    = 4,302,768,000 / 37.73064746707678 = 114,036,000  ≈ 1.14e8 per second
wall per step        = 37.73064746707678 / 2,400 = 15.72 ms
wall per cell-step   = 37.73064746707678 / 694,003,200 = 54.4 ns
```

54 nanoseconds per cell per step, at ~5 flops per cell-step, is roughly two orders of magnitude
above what a memory-bound double-precision update should cost: 14 MB of field data touched per step,
at even 5 GB/s, is under 3 ms. That gap is the entire business case for this document, and it says
the win is available on one CPU core before any GPU is mentioned. **UNVERIFIED**: I did not profile
the run, so I cannot say what fraction of the 15.72 ms is the two mat-vecs and what fraction is the
Python around them. I decline to guess; a `cProfile` of one 100-step slice would settle it and should
be the first thing done.

---

## 1. API boundary

The Python side owns the grid, the materials, the index lists and the waveform; the C++ side owns
one step. The question is only how the arrays cross the line.

### Option A — pybind11

```cpp
void step(py::array_t<double, py::array::c_style> e, py::array_t<double, py::array::c_style> h, ...)
{
    py::buffer_info ei = e.request(true);        // writable
    double* __restrict ep = static_cast<double*>(ei.ptr);
    // extents and strides are IN the buffer_info; check them here, once, outside the march
    py::gil_scoped_release no_gil;
    for (int n = 0; n < nsteps_this_call; ++n) { ... }
}
```

- **Type safety.** Compile-time on the C++ side; on the Python side `py::array_t<T, c_style>`
  performs the dtype and contiguity check *at the boundary* and raises `TypeError` if the array is
  not `float64` or not C-contiguous. With `py::array::forcecast` it will instead silently copy a
  non-conforming array — that flag is convenient and it is exactly how a hidden copy per step gets
  into a benchmark, so the recommendation below forbids it.
- **Strides.** `buffer_info::strides` carries them explicitly, in bytes. A wrong stride is caught
  only if the binding is told what to expect; `c_style` asserts C-order on the *whole* array, which
  is the right assertion for a 1-D buffer and says nothing about the six-block interpretation
  inside it. So: accept `c_style` for the raw vectors, and validate the *block structure* (`offex,
  offey, offez, nxn, nyn, nzn, nx, ny, nz`) against the derived table in §0.2 with an explicit
  check that raises. This is cheap, once per call.
- **Copy avoidance.** Zero copies for contiguous `float64` arrays; the seven field and coefficient
  vectors cross as pointers.
- **Exception translation.** Automatic: `std::runtime_error` → `RuntimeError`,
  `std::invalid_argument` → `ValueError`, `std::out_of_range` → `IndexError`. A bug becomes a
  traceback rather than a corrupted field.
- **Build friction and CI.** Needs a C++ compiler and the pybind11 headers at build time, and
  produces an ABI-specific extension (one wheel per Python minor version). That is real cost: a
  build job, a compiler pin, and the failure mode where the wheel is stale relative to a header.
- **GIL.** `py::gil_scoped_release` inside the function body releases it for the march and
  reacquires on exit. One line, and it is the documented mechanism. Without it the march holds the
  GIL and no other Python thread runs at all — which for a 2400-step call is the whole run.

### Option B — ctypes / cffi

An `extern "C"` entry point taking `double*` and `size_t` extents, driven from Python by
`arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))` (ctypes) or a cdef/ABI declaration (cffi).

- **Type safety.** None from the ABI. cffi's ABI mode checks argument counts and basic types and
  will let you pass a `float32` pointer where a `double*` is expected. ctypes checks even less.
- **Strides.** Passed by hand, in elements or bytes, and checked by hand or not at all. A transposed
  or sliced array marches happily and produces plausible-looking garbage.
- **Copy avoidance.** Perfect, if the arrays are contiguous; `np.ascontiguousarray` is the caller's
  responsibility and is easy to forget.
- **Exception translation.** None. Every failure has to become a return code, and every return code
  has to be checked at the call site; C++ exceptions must not cross the ABI boundary at all, so
  `noexcept` discipline is mandatory.
- **Build friction.** Low on the C++ side (a plain `.so`), but the ABI is unversioned and untyped,
  so nothing catches a signature drift between the two languages except a crash.
- **GIL.** ctypes releases the GIL for the duration of a foreign call by default, so this option is
  *easy* on the GIL — arguably easier than pybind11, where forgetting the scope keeps it.

### Option C — flat-buffer handoff

Python owns the numpy arrays; the call passes raw pointers plus explicit extents and strides
(`sx, sy, sz` per block) and the callee validates them against the expected table, returning an
error code on mismatch.

- **Type safety.** Whatever the validator implements; typically an explicit dtype check on the
  Python side before the call.
- **Strides.** This is the option that *states* the contract most explicitly — every stride is a
  named argument, so the six-block asymmetry of §0.2 is visible in the signature rather than implied
  by a flag. But the checking is entirely ours to write, and a missed check is a wrong answer.
- **Copy avoidance.** Maximal, and dependency-free (no pybind11, no cffi).
- **Exception translation.** None by construction; error codes only.
- **Build friction.** Lowest of the three: a `.so` and a tiny C header.
- **GIL.** Must be released explicitly (`Py_BEGIN_ALLOW_THREADS`), and the binding layer is ours to
  write, so it is more code than pybind11's one line, in the one place where a mistake is invisible.

### Recommendation: pybind11

**It is the only one of the three where the dtype/contiguity contract is enforced by the binding
layer at the boundary, and where exception translation and GIL release are one line each, at zero
run-time cost once the arrays are already contiguous.**

The flat-buffer option is the tempting one for a hot loop, and it is the wrong trade: it saves a
build-time dependency and buys a class of bug — wrong stride, wrong dtype, forgotten GIL — that
manifests as a plausible field thousands of steps later. Two concrete rules go with the choice:
never use `py::array::forcecast` (a silent per-step copy is the one performance bug this design
cannot survive), and put every stride/extent check in a separate `validate()` call made once per
run, not per step.

---

## 2. Core loop

The pseudocode below is the *proposed* structured-grid kernel. It computes the same algebra as
`emfit/evolve.py:191-204`; it does not yet compute it in the same *order*, and §2.3 is about why
that matters.

### 2.1 H update (Faraday), then the layer, then curl H

```
// Geometry, from §0.2. e-blocks and h-blocks have DIFFERENT j-strides.
// h = h_fx | h_fy | h_fz ;  e = e_ex | e_ey | e_ez
// per block: sx, sy, sz are (i, j, k) strides in doubles; sz == 1 in all six.

for each face family F in {fx, fy, fz}:                 // 3 blocks
  for i in 0 .. nF_i-1:                                  // nxn or nx
    for j in 0 .. nF_j-1:                                // ny or nyn
      base = off_F + i*sx_F + j*sy_F
      for k in 0 .. nF_k-1:                              // innermost: stride 1
        idx = base + k*sz_F                             // sz_F == 1
        // four incident edges, signed, in ASCENDING GLOBAL INDEX (see 2.3)
        acc =  c0 * e[n0] + c1 * e[n1] + c2 * e[n2] + c3 * e[n3]   // c* in {+1,-1}
        h[idx] -= dt * inv_m_mu[idx] * acc
        h[idx] *= h_factor[idx]                          // PML, pml.py:727-738
```

### 2.2 Curl H, source, E update, layer, PEC

```
// (a) curl H into a scratch array ce, or into e directly with an accumulator:
for each edge family G in {ex, ey, ez}:
  for i, for j, for k (k innermost, stride 1):
        idx = off_G + i*sx_G + j*sy_G + k
        acc = d0*h[m0] + d1*h[m1] + d2*h[m2] + d3*h[m3]
        // (b) source: soft current on a static edge list  (studies.py:3041-3240)
        if idx in src_idx:  acc -= src_val          // or: scatter src_val into ce beforehand
        // (c) E update: lossless or lossy, exactly as evolve.py:197-200
        if has_loss:
            e[idx] = (e[idx]*loss_num[idx] + acc) * loss_den[idx]
        else:
            e[idx] += dt * inv_m_eps[idx] * acc
        // (d) PML
        e[idx] *= e_factor[idx]
        // (e) PEC  (evolve.py:203-204)
        if is_pec(idx): e[idx] = 0.0
```

### 2.3 Update order, stated precisely

The order inside one step is not a style choice; a permutation of these six stages is a different
scheme and will produce a confident, stable, wrong answer rather than a crash:

1. `h -= dt * inv_m_mu * (C e)` — must read the **old** `e`, so no E write may precede any H read
   in the same step (or the H update must be double-buffered).
2. `h *= h_factor` — the H damping applies to `h^{n+1/2}`, i.e. *after* the H update
   (`evolve.py:192-193`).
3. `ce = C_tilde h` — must read the **damped** `h`.
4. `ce -= j` — the source is subtracted from curl H *before* the E update, not added to E afterwards
   (`evolve.py:195-196`). This is a soft current: it does not force an edge voltage.
5. `e = (e*loss_num + ce) * loss_den` — one pass, no intermediate scaling of `ce`; the lossy and
   lossless branches are *different expressions*, not the same one with `m_sigma = 0`
   (`evolve.py:197-200`), and the docstring at `evolve.py:30-31` claims they agree bit for bit when
   `m_sigma` is all zero. **UNVERIFIED**: I did not verify that bit-identity claim by running it.
6. `e *= e_factor`, then `e[pec_idx] = 0` — damping before PEC, so a PEC edge ends at exactly 0.

Because H at step `n` reads the E of step `n` and writes only H, and the E update reads only the
just-written H, the H sweep and the E sweep can be parallelised internally but **cannot be fused**
without a second buffer or a colouring scheme. Do not fuse them.

### 2.4 Loop nesting: which axis is innermost, and why

**k is innermost.** From §0.2, `k` has stride 1 in all six blocks; `j` has stride 22 or 23; `i` has
stride 4,664 to 4,899. The innermost loop therefore walks contiguous memory for the array being
written and for two of its four stencil neighbours, and the vectoriser sees a unit-stride loop.

Two refinements that follow from the real numbers rather than from folklore:

- `nz` is only 22 (23 for the `z`-oriented blocks), so a `k`-line is 176 bytes — under three cache
  lines, too short to amortise loop overhead. Walk `(j,k)` as one contiguous run: the flat index is
  `i*sx + j*sy + k` with `sy` the block's j-stride, so `j` then `k` with `sz == 1` covers
  `nF_j * sy` doubles as one contiguous span (212 × 22 = 4,664 doubles = 37 kB for the `h` `fx`
  block). That is one L1-resident tile per `i`, and it makes the `i` stride the only long jump.
- Block over `i`: keep two to four `i`-planes of `e` and one of `h` in cache, because the H sweep
  reads `e` at `i` and `i±1` and the E sweep reads `h` at `i` and `i±1`. With `sx ≈ 4.7 kB` per
  plane that is trivially achievable and it removes most of the TLB and prefetch pressure that the
  CSR form suffers today.

### 2.5 Numerical hygiene

**Keep `double`.** The current code is `float64` by construction (`evolve.py:127-128` cast every
material vector with `dtype=float`; `:168-169` allocate the fields as `np.float64`), and changing it
would not be a port, it would be a different instrument. The reason is physical, not stylistic: the
material diagonals are of order `m_eps ≈ 1.5e-14 F` and `m_mu ≈ 1e-12`, the series load is a
conductance of `1/(8 × 50) = 2.5e-3 S` spread over eight parallel edges, and the PML factor is
`exp(-sigma dt/eps0)` — a number whose *difference from 1* is the entire effect. In `float32`, whose
relative rounding is ~6e-8, a factor of `1 - 1e-6` is representable but the `1e-9`-level differences
that decide whether a sum sits at 0.9999 or 1.0001 are not. The quantity the study actually reports
is a ratio of fitted amplitudes whose interesting structure is at the `1e-3` level
(`evidence/termination/build_A_convergence_p51.txt`: |S21| moves 7.9e-4 between 4800 and 9600
steps); halving the mantissa to chase throughput would put the instrument's own convergence study
below its own rounding. The cost is understood: `double` halves the SIMD lane count versus `float`,
and this kernel is memory-bound anyway, so the lanes are not what is limiting it.

**Fix the reduction order.** Any reduction that crosses the kernel boundary — the energy
`U = ½e·m_eps·e + ½h·m_mu·h − (dt/2)(Ce)·h` (`evolve.py:210-218`), the probe sums
(`evolve.py:265`), the DFT accumulation, the station sums — is a sum whose order determines its last
bits. Today that order is whatever numpy does (pairwise summation for `np.sum`, ascending column
index for a CSR row). The moment any of it becomes a parallel reduction, the last bits change, and
every banked artefact stops matching. So: **write the reduction order down as part of the spec and
keep it fixed** — ascending index within a row, fixed thread order across threads (see §3), and the
thread count recorded in the artefact metadata so a change of core count is visible as a change of
answer rather than as a mystery.

Bit-reproducibility *across* the port (Python mat-vec vs C++ stencil) is a separate and harder
requirement, and it is the first thing §5 asks for. The CSR row sums four terms in ascending
*global column index*; over the blocks that means all `ex` contributions first, then `ey`, then `ez`,
with the two neighbours inside a block in their own index order. A stencil loop that accumulates in
the order `(ex_lo, ex_hi, ey_lo, ey_hi, ez_lo, ez_hi)` reproduces that whenever the block offsets
are ascending in that order. **UNVERIFIED**: I have not confirmed that `off_ex < off_ey < off_ez`
nor the exact per-face neighbour order, so treat this as the hypothesis the identity test in §5
must confirm, not as an established fact.

---

## 3. Parallelisation

### Recommendation: OpenMP first, and no CUDA in this project yet

Five reasons, in the order that they actually bind:

1. **It is memory-bound, not compute-bound.** The whole update is: read four neighbours, do about
   five flops, multiply by two coefficients, write one value. There is no arithmetic to hide a
   latency behind. GPUs help compute-bound kernels; for a kernel whose time is set by bytes moved,
   a GPU's advantage is bandwidth, and bandwidth is the one thing that is also easy to get on a
   CPU — by using properly strided, contiguous access instead of the CSR gather the code does today.
2. **The grid is small.** MEASURED: 289,168 cells, 906,144 edges, 886,676 faces (build_A). The `e`
   vector is 7.25 MB and `h` is 7.09 MB — both comfortably resident in the L3 of a current server
   core complex. A problem this size is where a GPU is *least* useful, because there is no working
   set to stream; there is only a small array to keep hot.
3. **The GPU boundary would have to move the whole march, not one step.** One step on a GPU is
   microseconds of work; if Python called it per step, the transfer and the launch would dominate.
   So a CUDA port means moving the loop, the source waveform, the probes and the DFT into the
   kernel — i.e. rewriting the study, not porting the stepper. The measured end-to-end cost of
   15.72 ms per step is *not* evidence that a GPU is needed; it is evidence that the Python-side
   per-step work is worth removing, and that is available on one core.
4. **CI.** There is no CUDA toolchain in CI. **UNVERIFIED**: I did not inspect the CI configuration
   to confirm that; it is taken as given by the brief and I have not checked it. If it is true, a
   CUDA port makes the fast path untestable in the one place tests run.
5. **The interface and the divergence properties are identical.** The stencil, the exchange
   pairs, the flux-conserving transfer and the divergence monitor of §4 have the same form on CPU
   and on GPU. Starting on the CPU loses nothing that cannot be recovered; starting on the GPU
   would build the hard part (§4) on the platform that is hardest to debug.

### Where the pragmas go

```cpp
#pragma omp parallel for schedule(static, 1)
for (int i = 0; i < nF_i; ++i) {          // outermost index: x-planes
    // j, then k innermost, k unit stride, as in §2.4
}
```

- **Which loop:** the `i` loop of each family sweep — never the `k` loop (it is short and
  vectorisable, and putting threads there kills the vectoriser) and never the family loop.
- **`collapse` or not:** for the H sweep and the E sweep the `(i, j)` pair is independent, so
  `collapse(2)` is legal and worth it when `nF_i` is smaller than a few times the thread count.
  With build_A's `nx = 62` and, say, 8 threads, plain `i`-parallelism is 7.75 planes per thread,
  which is adequate but uneven; `collapse(2)` over `(i, j)` with `schedule(static)` gives a much
  finer grain and is the safer default. Do **not** collapse `k` as well — it destroys unit-stride
  vectorisation.
- **`schedule`:** `static` (or `static, 1`) everywhere. `dynamic` buys nothing on a uniform grid and
  costs deterministic ordering, which §2.5 has just been at pains to preserve.

Correctness note: the H sweep reads `e` and writes `h`; the E sweep reads `h` and writes `e`. Within
a sweep there is no write-write or read-write conflict, so no colouring is needed and the parallel
result is independent of thread order — **as long as no thread writes a value another thread reads
in the same sweep**, which holds here.

### The one real hazard: nondeterministic reductions

Everything else parallelises cleanly. The thing that does not is any sum: OpenMP's `reduction`
clause gives no guarantee of accumulation order, and in practice its order depends on the thread
count, so the same run on 8 cores and on 16 cores differs in the last bits. For this project that
is not cosmetic — the artefacts are compared bit for bit, and §0.7's whole baseline is a number we
intend to defend.

**Fix:** never use `reduction(...)` on a quantity that reaches an artefact. Allocate one accumulator
per thread, indexed by `omp_get_thread_num()`, have each thread accumulate into its own slot for the
whole sweep, and after the sweep sum the slots in ascending thread index (0 … T-1) in one serial
loop. Then record `threads=T` in the artefact metadata. The result is reproducible for a fixed `T`,
and a change of `T` is visible rather than mysterious.

### What would justify CUDA later

Not a promise, a condition. Move to CUDA when all three hold, measured on a real run:

1. the two sweeps are a measured majority of the step time (i.e. the Python-side and extraction
   costs have already been removed and a profiler attributes most of the remaining time to the
   stencil), **and**
2. the whole march fits resident in GPU memory so the transfer cost is O(1) per run rather than per
   step — for build_A that is ~15 MB of fields plus ~30 MB of coefficient vectors, so this is
   certainly satisfiable *now*, which means the condition that actually binds is (1) and (3), and
3. the problem has grown to the point where it no longer fits in L3 — i.e. the grid is several times
   build_A's 289k cells, so the CPU's cache advantage is gone.

Until (1) and (3) are true, a GPU would be a slower, less testable version of the same kernel.

---

## 4. Subgridding hook

This section is the one that will be judged in a year, so it is written as constraints on today's
data layout rather than as a plan for a feature.

### 4.1 Structure-of-arrays per component, all extents and strides explicit

Six contiguous buffers — `e_ex, e_ey, e_ez, h_fx, h_fy, h_fz` — each with its own
`(extent_i, extent_j, extent_k)` and its own `(sx, sy, sz)`, passed as arguments and validated once.

Today's code is already *almost* this: one allocation, six blocks, six index maps, offsets held as
`off_ex … off_fz` (`emfit/operators.py:90-104`). The port should keep the single allocation (one
`numa`-friendly region, one lifetime) and expose the six base pointers, so the requirement is
literally "six contiguous runs with explicit geometry", not "six malloc calls".

What must never happen:

- **A struct-of-structs** (`struct Cell { double ex, ey, ez, hx, hy, hz; }`): every access then
  strides by `sizeof(Cell)` and touches a different component than the lane next to it, so the
  vectoriser either gives up or does a gather per component, and the memory traffic multiplies by
  the number of components per cache line.
- **A 3-D array of pointers** (`double*** a`): each access is a dependent load. Prefetch cannot
  resolve it, the compiler cannot vectorise it, and it costs three pointer chases to find one
  double. It is the single most common way a "port for speed" ends up slower than numpy.

The six-block asymmetry from §0.2 is exactly why the strides must be arguments and not constants:
`fz` has j-stride 23 while `fx` has 22; the `i`-strides run 4,664 to 4,899. Any kernel that assumes
one stride set is wrong in four blocks of six, and wrong in a way that produces a plausible field.

### 4.2 The fine patch is a separate grid object with its own halo

Not fine cells interleaved into the coarse array. The reason is not tidiness, it is the inner loop:

**The coarse array's stride assumptions are what make the fast loop fast.** §2.4's performance
comes from `k` being unit stride, `(j,k)` being one contiguous 37 kB span, and the `i` direction
being the only long jump. Interleaving fine cells into the coarse buffer changes the stride of
every access in the *whole* array in order to help the one region that needs it — which means the
fast path is replaced by a general gathered path everywhere, and the 95 % of the domain that did not
need refinement pays the bill. A separate `Grid` object with its own extents, its own strides, its
own halo and its own `dt` keeps the coarse kernel exactly as it is and confines the slow, general,
correctness-critical code to the interface.

The halo is not optional: the fine patch's stencil needs neighbours one cell outside its interior on
every side, on the same staggered layout as the coarse grid, or the update is inconsistent at the
patch edge and the inconsistency is a *reflection* that looks like a material.

### 4.3 The coupling surface

Built once, at setup, into flat arrays:

- `coarse_edge_of_interface[k]`, `fine_edge_of_interface[k]` — tangential E pairs on the shared
  surface (for a refinement factor `r`, one coarse edge faces `r` fine edges; the pair list carries
  the mapping and the weights).
- `coarse_face_of_interface[m]`, `fine_face_of_interface[m]` — the corresponding tangential H (flux)
  quantities.
- Weights, normalised so their sum over each coarse element is exactly 1 (see §4.4).

Exchange order, which is as load-bearing as §2.3:

1. **Coarse step.** The coarse grid completes one full step (§2.3) using, for its faces on the
   interface, the *last known* fine flux.
2. **Fine step(s).** The fine patch advances one or more sub-steps. With refinement factor `r`, the
   fine `dt` is `dt/r` (from its own CFL) and it takes `r` steps per coarse step; the coarse E on the
   interface is held fixed across those sub-steps, i.e. it is treated as a Dirichlet boundary for the
   fine patch.
3. **Exchange.** Tangential **E** goes **coarse → fine** (the fine patch's interface edges take the
   interpolated coarse values). Tangential **H** goes **fine → coarse** (the fine fluxes are summed
   into the coarse faces, and enter the coarse E update as an extra current added to `ce` before the
   `loss_num/loss_den` expression at `evolve.py:200`).

Both directions happen once per coarse step, at a single defined point in the sequence. An
implementation that exchanges at different points in different fields will conserve the wrong
quantity, and §4.4 is the test that catches it.

### 4.4 The divergence constraint

This is the part that kills naive implementations, so it is stated as a rule, not a caution.

Interpolating tangential E across the interface (or tangential H) does **not** preserve the discrete
divergence of the other field. In a Yee scheme the two curls are exact adjoints, so
`div(curl) = 0` holds identically — until a boundary condition is imposed by interpolation, at which
point the identity is broken on the interface faces. What that means physically is that **charge is
created at the interface**. It does not blow up. It appears as a small, smooth, growing field that
looks like a slow wave or a drifting bias for a few thousand steps, and then it destroys the answer.
In a study that measures a transmission coefficient at the `1e-3` level after 2400 steps, that is
indistinguishable from physics for the whole life of the run.

So the transfer must be **flux-conserving**, not resampling:

- coarse → fine: **distribute** — the fine edges' values are chosen so that their *sum* over the
  interface element equals the coarse value (weights summing to 1 for E, and the corresponding area
  weights for fluxes);
- fine → coarse: **accumulate** — the coarse face receives the *sum* of the fine fluxes it covers,
  never an average, so the total flux crossing the interface is unchanged by the transfer.

Think of the coarse-fine exchange as a current crossing a surface: what must be conserved is the
integral, so one side distributes and the other accumulates. Treating it as a resampling of a field
(interpolate in both directions) conserves the field value and destroys the flux, which is the
failure mode above.

**Regression test, permanent, not optional:** integrate the discrete divergence over the interface
faces every step and assert it stays at round-off relative to the field magnitude. The operator
exists: `CellComplex.divergence()` returns `S` and `S_tilde = S.T` is exposed at
`emfit/operators.py:255-258`, so the monitor is a sparse mat-vec restricted to the interface face
subset, plus an `abs().sum()`. This test must run on every subgridding commit forever; it is the only
thing standing between a slow interface charge and a published wrong number.

### 4.5 A ladder of three steps, and what each buys

1. **Graded mesh, no patches.** The tensor grid already supports non-uniform widths — `cfl_dt`
   (`evolve.py:68-79`) takes the *minimum* width per axis, with a comment saying a graded grid must
   use the minimum. So refinement by grading is available today with no new data structure. It buys
   resolution where it is wanted and it costs global `dt` stiffness: the smallest cell anywhere sets
   the step for the whole domain. Start here; most of the substrate-refinement questions in this
   project can be answered by it.
2. **One-axis refinement.** A strip of fine cells along one axis only, still conforming — a second
   tensor block in that axis, no exchange machinery, no halo, no divergence monitor. It buys the
   thing this geometry actually needs (the substrate is 4 cells thick against 12 air and 6 top:
   the vertical resolution, not the lateral one, is what limits the impedance), and it is
   one-dimensional so it stays tractable. **If the physics can be served this way, it should be, and
   step 3 is unnecessary.**
3. **True subgridding on all three axes.** This is where §4.1-4.4 all bind: separate grid object,
   halo, coupling arrays, flux-conserving exchange, divergence monitor. It buys arbitrary local
   refinement at the cost of an interface that is a permanent source of subtle error — i.e. the
   maintenance cost is not the code, it is the test you can never remove.

The staging is the point: (1) and (2) are worth doing on their own merits and each removes work from
(3). Attempting (3) first, because it is the general case, is how projects end up with a divergence
monitor that fails on one machine and a paper that cannot be reproduced.

---

## 5. What to build first

Five steps, in this order. **Nothing in this section is a speedup claim**; steps 1–2 are about
establishing that any speed later gained is real, and steps 3–5 keep that property.

1. **Extract the current update into a single function with an explicit signature, called once per
   step from Python, and prove it produces bit-identical output to today's loop on one banked case.**
   One function, one call per step, arguments named exactly as in §0.6, no reordering of
   expressions, still using `C @ e` and `C_tilde @ h`. Prove it by running
   `run_build_A.py --s21-plane-col 51` before and after and comparing the final `e`, `h` and the
   recorded |S11|/|S21| with `==`, not `approx`; the p51/n2400 artefact
   (`build_A_n_default_p51.json`, |S11| = 0.32586326001662264, |S21| = 0.7617054231929281) is the
   reference. If this step does not reproduce bit for bit, stop: the refactor is wrong, not the
   reference.

2. **Write the identity harness, and make it the gate for everything after.** A script that runs the
   extracted step function over the same case, hashes `e` and `h` (and the extraction outputs) and
   compares against the stored reference. Run it on two cases with *different* geometry — p51 at
   2400 steps is one; a case with `zmax`-open (`n_top = 0`) or a different `n_pml` is the second —
   because a kernel that is wrong in one stride set can still pass on one grid.

3. **Dump the incidence tables and implement the C++ H and E sweeps against them.** From Python,
   write out the CSR triplets of `C` (row, col, sign) into a flat file at setup; implement the
   stencil sweep of §2.1-2.2 walking those tables, accumulating in ascending global column index as
   in §2.5; compare against the step-2 hash. **If it does not match bit for bit, decide explicitly**
   between reproducing the summation order and accepting a documented tolerance — and if it is a
   tolerance, record the size of the difference and the case it was measured on, because from then
   on every artefact carries that tolerance.

4. **Move the six field pointers across a pybind11 boundary with a validating signature.** Python
   keeps the loop, the waveform and the extraction; the call takes the buffers with extents and
   strides, validates them once (§1), releases the GIL, and does one step. No `forcecast`, no copy,
   no per-step allocation. The step-2 harness is the acceptance test and it must still pass.

5. **Make the parallel loop bit-reproducible, then re-run the harness.** `omp parallel for` over the
   `i` index (or `collapse(2)` over `(i,j)`) with `schedule(static)`; per-thread accumulators for
   every sum, folded in ascending thread index; `threads=T` written into the artefact metadata. The
   harness must pass at `T = 1` and at the default `T`, and the two must agree with each other.

Only after step 5 is green is a timing measurement meaningful — and when it is taken, it should be
reported against §0.7's MEASURED 18,393,620 cell-updates per second (or the 1.14e8
unknown-updates per second), on the same case, with the same extraction, so that the comparison is
between two runs of the same experiment rather than between two ideas.

---

## Claims marked UNVERIFIED in this document

1. §0.3 — that the CSR rows of `C`/`C_tilde` carry the sign pattern of a textbook Yee stencil, and
   how many nonzeros each row has. I did not read `operators.py:170-240` or count them.
2. §0.7 — that the step time is dominated by the two mat-vecs rather than by the Python around them.
   I did not profile; the arithmetic in §0.7 is inference from the total wall clock.
3. §2.3 item 5 — the docstring's claim (`evolve.py:30-31`) that the lossy and lossless E updates
   agree bit for bit when `m_sigma` is identically zero. I did not run it.
4. §2.5 — that `off_ex < off_ey < off_ez` and the exact per-face neighbour order, i.e. whether a
   stencil loop can reproduce the CSR row's summation order exactly. This is a hypothesis to be
   confirmed by the step-3 identity test.
5. §3 reason 4 — that there is no CUDA toolchain in CI. Taken as given by the brief; I did not
   inspect the CI configuration.
6. §0.7 — that SciPy's CSR mat-vec accumulates in ascending column index. I did not read the SciPy
   source; the statement is about what the row-sum order must be, and it should be checked against
   the installed version before the bit-identity claim in §2.5 is relied on.
