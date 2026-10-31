# Engineering recommendations making the Nédélec.txt
# Engineering recommendations: making the Nédélec solver faster and more reliable

I've gone through the entire brief and researched the numerical methods behind its five questions.

My main recommendation is:

**Do not rewrite the eigensolver yet. Keep the existing sparse shift-invert implementation as the reference, improve its convergence and mode selection, and run a small number of carefully selected experiments against structure-aware alternatives.**

There is an encouraging fact in your measurements: at 37,276 free edges, the entire solve takes approximately 4.2 seconds and uses only 72 MB for the reported factorization. That is already a useful result. The implementation is not facing an immediate computational wall. Its biggest opportunity is reducing the eigensolver's iteration count and ensuring that it finds the correct physical modes. Pasted text

I would give the engineer the following advice.

---

# 1. First, understand what the current mathematics is doing

Your problem is:

\[
Kx=\lambda Mx,\qquad \lambda=\beta^2.
\]

The matrices have the structure

\[
K=
\begin{bmatrix}
A&0\\
0&0
\end{bmatrix},
\qquad
M=
\begin{bmatrix}
m&-c\\
-c^T&h
\end{bmatrix}.
\]

The important properties are:

- \(K\) is singular.
- \(M\) is symmetric but indefinite.
- The physical eigenvalues are not the entire spectrum.
- There are additional gradient-related and mixed-formulation spectral difficulties.

This is not an ordinary symmetric eigenvalue problem.

That distinction should guide every solver decision.

### Why this matters for the implementation

Many engineers instinctively reach for `eigsh` when they see symmetric matrices.

That would be an inappropriate direct substitution here.

SciPy's standard generalized symmetric eigensolver assumes a positive-definite or positive-semidefinite mass matrix for its relevant operating modes. Your measured negative eigenvalues of \(M\) violate those assumptions. The buckling mode supports an indefinite mass matrix under different conditions, but requires the first matrix to be positive definite, which your singular \(K\) does not satisfy. [SciPy Documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.eigsh.html?utm_source=chatgpt.com)

So the current use of a general Arnoldi method is understandable.

It is not necessarily the fastest possible method, but replacing it with a standard Lanczos implementation without considering the indefinite pencil would be a mistake.

**Advice:** preserve the current implementation as the benchmark against which every alternative must be measured.

# 2. Question 1: Sparse matrix fill and ordering

This is where I would be quite conservative.

Your engineer has correctly identified that explicitly eliminating \(e_z\) produces

\[
S=m-ch^{-1}c^T.
\]

Although this is mathematically useful, it creates a computational problem.

The matrix \(h\) is sparse, but its inverse \(h^{-1}\) is generally dense. Consequently, the reduced operator \(S\) can have substantial nonlocal coupling.

**Do not explicitly construct this Schur complement.**

Instead, preserve the full block formulation:

\[
K-\sigma M=
\begin{bmatrix}
A-\sigma m & \sigma c\\
\sigma c^T &-\sigma h
\end{bmatrix}.
\]

This retains the sparse local structure of the original discretization.

### What I recommend testing

Run the same matrix through four ordering configurations:

| Configuration | Purpose |
|---|---|
| SuperLU COLAMD | Existing reference |
| SuperLU MMD_AT_PLUS_A | Minimum-degree ordering on the symmetrized graph |
| METIS nested dissection | Exploit the two-dimensional geometric structure |
| SCOTCH nested dissection | Independent ordering comparison |

The exact availability of these orderings will depend on the installed solver interfaces.

For symmetric-indefinite factorization, I would additionally investigate MUMPS. It supports general symmetric indefinite matrices, including 2-by-2 pivoting, and interfaces to METIS, SCOTCH and AMD ordering methods. [MUMPS Solver](https://mumps-solver.org/index.php/index.php?page=home\&utm_source=chatgpt.com)

### Why nested dissection is interesting

For a two-dimensional mesh with \(N\) unknowns, nested dissection has the familiar theoretical scaling:

\[
\text{Factorization work}=O(N^{3/2})
\]

\[
\text{Factor storage}=O(N\log N).
\]

This compares favourably with dense factorization:

\[
O(N^3)\text{ work}, \qquad O(N^2)\text{ storage}.
\]

These are idealized sparse-direct-solver estimates. Numerical pivoting in an indefinite system can increase the constants and affect practical scaling. [Cornell Computer Science](https://www.cs.cornell.edu/courses/cs6210/2025fa/lec/2025-09-22.html?utm_source=chatgpt.com)

### One important correction to the existing measurements

The brief compares:

- `fill_per_row = 106.9`
- `factor_nnz / nnz(S) ≈ 10.7`

These are not necessarily equivalent measurements.

Before drawing a scaling conclusion, calculate the same quantities consistently:

\[
\text{Fill ratio}=
\frac{\operatorname{nnz}(L)+\operatorname{nnz}(U)}
{\operatorname{nnz}(K-\sigma M)}.
\]

Also record peak memory, factorization time and solve time.

I would then perform the proposed approximately 80,000-unknown experiment.

**My verdict:** nested dissection is worth benchmarking, but I would not spend substantial engineering time implementing a custom ordering algorithm. Existing sparse-direct-solver libraries have already invested heavily in this area.

---

# 3. Question 2: Can we replace ARPACK with something better?

This is probably the most promising optimization opportunity.

The current measurements are:

| Operation | Time |
|---|---:|
| Sparse LU | 0.23 s |
| Eigenvalue iteration | 3.92 s |
| Total | 4.15 s |

The eigensolver accounts for approximately 94% of the total time.

Therefore, optimizing the factorization alone cannot produce a transformative improvement.

The engineer has identified the right target.

## My first recommendation: benchmark SLEPc

I would investigate SLEPc before writing a custom eigenvalue solver.

It is a mature eigenvalue software library built around PETSc, with support for several iterative algorithms and different classes of generalized eigenvalue problems.

Most importantly, it explicitly supports:

\[
Ax=\lambda Bx
\]

where both matrices are symmetric or Hermitian, but \(B\) is indefinite.

This is precisely the problem class described in your brief.

SLEPc calls it:

`EPS_GHIEP`

(Generalized Hermitian-Indefinite Eigenvalue Problem.)

It also has a Krylov-Schur implementation that supports indefinite Lanczos for this problem type. [SLEPc](https://slepc.upv.es/release/manualpages/EPS/EPS_GHIEP.html?utm_source=chatgpt.com)

### But there is a warning

SLEPc's documentation explicitly warns that exploiting the indefinite inner product can introduce numerical instability.

It even recommends considering a non-Hermitian treatment when this happens. [SLEPc](https://slepc.upv.es/release/manualpages/EPS/EPS_GHIEP.html?utm_source=chatgpt.com)

That is important.

I would not simply replace ARPACK with SLEPc and assume the problem is solved.

Instead, compare two implementations:

**Experiment A: Generalized non-Hermitian formulation**

Treat the matrices as a general pencil and use Krylov-Schur.

**Experiment B: Generalized Hermitian-indefinite formulation**

Declare the actual symmetry and use `EPS_GHIEP` with indefinite Lanczos.

Both should use the same shift-invert target and the same numerical problem.

The comparison should establish whether exploiting symmetry actually improves performance without damaging numerical stability.

### What I would measure

| Metric | Why |
|---|---|
| Wall-clock time | Actual performance |
| Number of shifted solves | Measures iterative work |
| Number of restarts | Reveals convergence problems |
| Final generalized residual | Tests numerical accuracy |
| Imaginary part of eigenvalue | Detects unexpected complex solutions |
| Eigenvector agreement | Detects convergence to a different mode |
| Memory | Ensures the method remains practical |

The key formula is:

\[
r=
\frac{\|Kx-\lambda Mx\|}
{\|K\|\|x\|+|\lambda|\|M\|\|x\|}.
\]

Use a consistently scaled residual across all implementations.

### Second recommendation: investigate Jacobi-Davidson

SLEPc also implements Jacobi-Davidson.

This is interesting because the current method performs many applications of an inverse operator. A Jacobi-Davidson approach can use an approximate correction equation and a preconditioner instead of requiring an exact shifted solve at every iteration.

However, the correction equation must be designed carefully for the indefinite pencil.

I would put it in the benchmark, but not assume it wins.

The test matrix should be:

1. Current SciPy/ARPACK implementation.
2. SLEPc Krylov-Schur, general formulation.
3. SLEPc Krylov-Schur, GHIEP.
4. SLEPc Jacobi-Davidson.

That is a much better experiment than immediately implementing a new research algorithm.

## Third recommendation: improve the starting vector

There is a relatively inexpensive optimization that I think your engineer should try immediately.

Your solver is being used across different mesh levels, parameter variations and geometries.

The physical mode usually changes continuously as these parameters change, except near mode crossings or degeneracies.

Therefore, a previously computed eigenvector can provide an excellent starting approximation for the next problem.

Instead of starting Arnoldi from an arbitrary random vector:

1. Take the previous mode.
2. Interpolate it onto the new mesh.
3. Normalize it.
4. Use it as the initial vector \(v_0\).
5. Check that its residual is acceptable before continuing.

This is particularly attractive for repeated geometry and frequency sweeps.

I would test this before more ambitious algorithm development.

Also benchmark the Krylov subspace dimension (`ncv`). SciPy recommends taking it larger than twice the requested number of eigenpairs. Increasing it can reduce restarts, although it also increases memory and orthogonalization costs. [SciPy Documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.eigsh.html?utm_source=chatgpt.com)

My proposed initial sweep:

\[
ncv\in\{20,32,48,64\}.
\]

Keep the requested eigenpairs and accuracy target fixed.

Record the actual operator applications, not just the reported outer iteration count.

**My verdict:** SLEPc GHIEP versus GNHEP, better initialization and Krylov-subspace tuning are the highest-priority algorithmic experiments.

---

# 4. Question 3: Can we eliminate the gradient nullspace properly?

This is the most mathematically interesting question in the brief.

It is also where I would be most careful about introducing a quick fix.

The underlying issue comes from the differential structure of Maxwell's equations.

### The discrete gradient and curl operators

For a conventional compatible finite-element discretization, there is a sequence of spaces:

\[
H^1(\Omega)
\xrightarrow{\nabla}
H(\mathrm{curl},\Omega)
\xrightarrow{\nabla\times}
L^2(\Omega).
\]

In discrete form, this produces matrices representing:

- A scalar-to-edge gradient operator \(G\).
- An edge-to-cell curl operator \(C\).

They should satisfy the topological identity:

\[
\boxed{CG=0}
\]

This is the discrete equivalent of:

\[
\nabla\times\nabla\phi=0.
\]

It is one of the major advantages of using compatible Nédélec elements.

However, your problem is a mixed electromagnetic formulation.

The transverse electric field \(e_t\) is coupled to the longitudinal field \(e_z\).

Consequently, simply removing every vector belonging to \(\ker(A)\) is not necessarily correct.

Your engineer has already observed that the attempted gradient deflation does not remove the problematic modes consistently. The measured \(\epsilon/\mu\) residual of approximately 0.0216 is a reason not to trust the widened basis. Pasted text

### What should replace it?

I would investigate the discrete version of Gauss's law:

\[
\nabla\cdot(\epsilon\mathbf E)=0
\]

for a source-free dielectric region.

With longitudinal dependence represented by \(e^{\mp i\beta z}\), this becomes, according to the chosen phase convention,

\[
\boxed{
\nabla_t\cdot(\epsilon E_t)
\mp i\beta\epsilon E_z=0.
}
\]

Notice that the constraint involves both \(E_t\) and \(E_z\).

That is important.

A deflation method that only considers the transverse gradient subspace is potentially incomplete.

### My suggested implementation experiment

Rather than immediately constructing a large projector, proceed in stages:

**Stage A: derive the actual discrete divergence constraint.**

Start from the continuous Gauss law and derive the corresponding discrete operator using the same finite-element spaces, material coefficients and sign conventions as the existing assembly.

**Stage B: construct the physical constraint space.**

Determine how the gradient-related degrees of freedom interact with \(e_z\) and \(\beta\).

**Stage C: test a constrained formulation on a small mesh.**

Compare the resulting eigenvalues and eigenvectors against a dense generalized QZ reference.

**Stage D: only then investigate deflation.**

If the constrained space is correct, look for a projection or basis transformation that eliminates the unwanted subspace without removing physical solutions.

One further caution: the indefinite Schur complement

\[
S=m-ch^{-1}c^T
\]

means the relevant orthogonality is not automatically ordinary Euclidean orthogonality.

A naive projection using a Euclidean gradient basis could be mathematically inconsistent with the material-weighted formulation.

There is a substantial literature on discrete compactness and spurious-mode-free Maxwell eigenproblems. The important lesson is to construct compatible discrete spaces rather than simply delete suspicious eigenvectors. [SIAM](https://epubs.siam.org/doi/10.1137/090772629?utm_source=chatgpt.com)

**My verdict:** do not spend time trying more versions of the existing gradient projection. Derive the complete mixed constraint first.

---

# 5. Question 4: Would higher-order Nédélec elements make the solver cheaper?

Potentially yes. But the engineer should not interpret this as an automatic performance improvement.

This is the distinction between two approaches.

### H-refinement

Make the mesh finer:

\[
h\rightarrow \frac h2.
\]

You get more elements and more unknowns.

### P-refinement

Keep the mesh but increase the polynomial order:

\[
p=1\rightarrow2\rightarrow3\rightarrow4.
\]

Each element can represent more complicated field distributions.

The attraction of p-refinement is that it may deliver considerably higher accuracy without requiring an equally large increase in the number of elements.

For electromagnetic finite elements, higher-order Nédélec families have a well-developed mathematical foundation. Research on discrete differential forms establishes discrete compactness for several widely used p-version edge-element families. This matters because it provides a route to convergent Maxwell eigenvalue calculations without introducing arbitrary spurious modes. [SIAM](https://epubs.siam.org/doi/10.1137/090772629?utm_source=chatgpt.com)

### But there is a catch: conditioning

Higher-order elements also introduce additional degrees of freedom and can worsen the conditioning of the mass and curl-curl matrices.

Ainsworth and Coyle specifically studied the conditioning of hierarchical p-version Nédélec elements and derived bounds for the relevant matrix condition numbers. [SIAM](https://epubs.siam.org/doi/10.1137/S003614290239590X?utm_source=chatgpt.com)

So I would not recommend jumping directly to p=4.

### My proposed experiment

Use one small, well-understood cross-section.

Compare:

| Implementation | Polynomial order | Objective |
|---|---:|---|
| Existing element | 1 | Baseline |
| Higher-order element | 2 | First improvement |
| Higher-order element | 3 | Evaluate further gain |

For each, record:

- Number of unknowns.
- Memory consumption.
- Eigenvalue error.
- Generalized residual.
- Factorization time.
- Eigenvalue iteration time.
- Total wall-clock time.

The metric that matters is:

\[
\boxed{
\text{Computational cost for a specified eigenvalue accuracy}
}
\]

Not simply the number of elements or the number of degrees of freedom.

### One additional recommendation

Investigate hierarchical basis functions and static condensation.

Static condensation can eliminate element-interior degrees of freedom locally, leaving a smaller global system involving interface degrees of freedom.

This is especially relevant when using higher polynomial orders.

Also, your microstrip has dielectric discontinuities and a PEC boundary. Increasing polynomial order on a mesh that poorly represents those interfaces will not magically fix the geometric approximation.

I would use h-refinement where the geometry and material interfaces need improved resolution, and p-refinement in smoother parts of the domain.

**My verdict:** p=2 is worth a prototype. It is not an immediate replacement for the current implementation.

---

# 6. Question 5: Could Helmholtz decomposition give us a better formulation?

This is another promising research direction.

The basic idea is to separate an electromagnetic field into different mathematical components.

In a suitably defined two-dimensional domain, a transverse vector field can be decomposed schematically as

\[
\boxed{
E_t=\nabla_t\phi+
\hat z\times\nabla_t\psi+
E_{\mathrm{harmonic}}.
}
\]

The terms represent:

- A gradient-related component.
- A rotational or curl-related component.
- A possible harmonic component associated with the topology and boundary conditions.

The harmonic component is important in multiply connected domains and should not be silently discarded.

### Why this could help

The original edge-element formulation carries both gradient-related and curl-related degrees of freedom.

Those components behave differently in Maxwell's equations.

The gradient component is curl-free:

\[
\nabla_t\times\nabla_t\phi=0.
\]

The rotational component carries the transverse curl behaviour.

Separating them can make the mathematical constraints easier to identify and may provide a more direct way to handle spurious modes.

It is particularly attractive because your engineer's current difficulty is precisely related to the coupling between the gradient nullspace and the mixed longitudinal field.

### But I would avoid a naive decomposition

There is an important complication.

Your dielectric permittivity is spatially varying:

\[
\epsilon=\epsilon(x,y).
\]

The physically relevant divergence constraint is weighted by permittivity:

\[
\nabla\cdot(\epsilon E)=0.
\]

An ordinary, unweighted Helmholtz decomposition does not automatically satisfy this condition.

The decomposition must be compatible with the material-weighted constitutive relations and the conductor boundary conditions.

The interface conditions matter too.

Otherwise, you risk building a mathematically elegant formulation that does not represent the actual electromagnetic problem correctly.

### What I would implement

A small proof of concept:

1. Construct the discrete gradient and curl spaces.
2. Verify \(CG=0\) to numerical precision.
3. Identify the gradient, rotational and harmonic subspaces.
4. Construct the appropriate material-weighted constraint.
5. Compare the resulting eigenvalues against the existing mixed formulation.

Do this on a homogeneous rectangular waveguide first, then on the microstrip.

I would not implement the full decomposition in production until the small example demonstrates an advantage.

**My verdict:** interesting research direction, but not the next engineering dispatch.

---

# 7. An additional idea: solve directly for β rather than β²

I particularly like this question from your brief.

Your existing eigenproblem uses

\[
\lambda=\beta^2.
\]

But the propagation dependence in Maxwell's equations is naturally first-order in the longitudinal derivative:

\[
\frac{\partial}{\partial z}.
\]

For a mode with dependence \(e^{-i\beta z}\),

\[
\frac{\partial}{\partial z}\rightarrow-i\beta.
\]

This makes a formulation directly in terms of \(\beta\) possible.

One approach uses the transverse electric and magnetic fields together:

\[
\Psi=
\begin{bmatrix}
E_x\\E_y\\H_x\\H_y
\end{bmatrix}.
\]

The resulting waveguide problem can be written schematically as

\[
\boxed{
A\Psi=\beta B\Psi.
}
\]

This is a generalized propagation-constant eigenvalue problem.

It is closely related to the Hamiltonian formulation of electromagnetic waveguides.

The literature discusses this formulation specifically for finding modal propagation constants, rather than their squares. [Cambridge University Press](https://www.cambridge.org/core/books/fundamentals-of-photonic-crystal-guiding/hamiltonian-formulation-of-maxwells-equations-for-waveguides-propagationconstant-consideration/927F6E5BAC623CDAD310E5343836A0B5?utm_source=chatgpt.com)

There is also a useful observation from MIT's waveguide eigenproblem material: the relevant first-order formulation has Hermitian operators, but the propagation-constant matrix is indefinite. [MIT Mathematics](https://math.mit.edu/~stevenj/18.369/spring12/?utm_source=chatgpt.com)

### Why investigate it?

There are several potential advantages:

1. The eigenvalue is directly the propagation constant.
2. Forward and backward solutions appear naturally as opposite signs of \(\beta\).
3. The formulation retains more of the first-order Maxwell structure.
4. It could provide an independent cross-check of the existing \(\beta^2\) formulation.

### Why not immediately replace the current solver?

Because the new formulation may also produce an indefinite generalized eigenproblem.

It may introduce additional unknowns, constraints or singular blocks.

There is no guarantee that it will converge faster.

I would treat it as a separate mathematical prototype.

The most useful first result would be to solve the same homogeneous guide and microstrip cross-section using both formulations and compare:

\[
\beta_{\mathrm{linear}}
\quad\text{against}\quad
\sqrt{\lambda_{\mathrm{quadratic}}}.
\]

If they agree, that is valuable independent evidence.

If the linear formulation also identifies the physical mode more easily, it becomes a serious candidate for the production architecture.

---

# 8. My recommended implementation roadmap

Here is the order I would actually give the engineer.

I am deliberately prioritizing short experiments with high diagnostic value over ambitious mathematical development.

| Priority | Task | Effort | Expected value |
|---|---|---|---|
| P0 | Verify which code path actually performs the 37k sparse solve | Very low | Resolves the stale implementation record |
| P1 | Audit matrix symmetry, generalized residuals and dense QZ reference cases | Low | Establishes mathematical reliability |
| P1 | Benchmark SLEPc GHIEP versus GNHEP | Medium | Potential reduction in eigenvalue iterations |
| P1 | Tune ARPACK `ncv`, starting vector and shift selection | Low | Potential immediate speed improvement |
| P2 | Benchmark METIS/SCOTCH orderings and factorization scaling | Medium | Reduces memory and factorization cost |
| P2 | Repeat the scaling experiment around 80k unknowns | Medium | Establishes workstation limits |
| P3 | Derive the correct mixed Gauss-law constraint | Medium to high | Potential solution to spurious modes |
| P3 | Prototype p=2 Nédélec elements | Medium | Potentially better accuracy per unknown |
| P4 | Prototype the direct-\(\beta\) formulation | High | Independent formulation and possible numerical improvement |
| P4 | Investigate Helmholtz decomposition | High | Potential structural improvement |

The distinction between P1 and P4 is important.

I would not delay the production solver while investigating Hamiltonian reformulations and higher-order elements.

The current sparse implementation has already demonstrated that it can solve a meaningful problem at a practical cost.

---

# 9. Two things I would add to the engineer's brief

There are two important checks missing from the proposed research questions.

## A. Verify the actual implementation before optimizing it

Your engineer explicitly says the record may be stale.

The reference tool reportedly solves 37,276 unknowns in 4.2 seconds, but `mode2d.py` may still have a dense-solver limit at 3,000 unknowns.

These are materially different situations. Pasted text

I would make this the first task:

1. Identify exactly which function performs the 37k solve.
2. Identify whether it lives in the reference tool or the reusable library.
3. Establish whether the sparse implementation is already available through the production API.
4. Update the component map and tests to reflect the actual state.

Do not build a second sparse implementation if the existing one can simply be wired into the library.

That would be unnecessary engineering.

## B. Audit the matrices before experimenting with algorithms

This is something I would insist on.

The brief defines \(A\) using a symmetrization:

\[
A=\frac12(B+B^T).
\]

That may be entirely intentional. However, the engineer should inspect the original assembled matrix \(B\) before symmetrization.

Why?

If the unsymmetrized matrix contains an unexpected asymmetry caused by indexing, boundary treatment or quadrature, symmetrization could conceal that assembly error.

I would add these numerical checks:

\[
\delta_K=
\frac{\|K-K^T\|}{\|K\|}
\]

\[
\delta_M=
\frac{\|M-M^T\|}{\|M\|}.
\]

Check them before any corrective symmetrization.

Then use a small mesh where dense generalized QZ is affordable to compare the complete eigenvalue spectrum against the sparse implementation.

In particular, investigate the reported spurious eigenvalues at

\[
\beta^2=\varepsilon_r k_0^2.
\]

Determine whether their exact location and growing multiplicity follow from the algebraic structure of the discretization, rather than merely filtering them out during eigenvalue selection.

This distinction matters: a filter can make the output look correct while leaving the underlying eigenproblem defective.

---

# 10. What I would actually send to the implementation engineer

Here is my condensed engineering directive.

### Immediate work

**1. Establish the real state of Route C.**

Resolve whether the 37k sparse implementation is already in `mode2d.py` or only in the reference tool.

**2. Preserve the current solver.**

Do not remove the SuperLU + ARPACK implementation. It is the reference implementation and provides a useful fallback.

**3. Audit the mathematical assembly.**

Verify symmetry before symmetrization, the mixed-block structure, the dense QZ reference cases and the physical eigenpair residuals.

**4. Run the eigensolver comparison.**

Benchmark:

- Existing SciPy/ARPACK.
- SLEPc GHIEP.
- SLEPc GNHEP.
- SLEPc Jacobi-Davidson.

Tune the starting vector, shift and Krylov subspace dimension.

**5. Investigate the proper mixed constraint.**

Derive the discrete Gauss-law constraint before trying another gradient-deflation implementation.

### Subsequent work

**6. Benchmark sparse ordering.**

Try METIS, SCOTCH and symmetric-indefinite factorization through MUMPS.

**7. Establish the scaling limit.**

Run the additional approximately 80k-unknown experiment, measuring actual peak memory and total solve time.

**8. Prototype higher-order elements.**

Start with p=2, using an element family with established Maxwell eigenvalue convergence properties.

**9. Investigate the direct-\(\beta\) formulation.**

First as an independent cross-check, not an immediate replacement.

**10. Keep Helmholtz decomposition as a research branch.**

Do not let this delay the working implementation.

---

# 11. The papers and technical references I would give the engineer

These are particularly relevant to the actual mathematical difficulties.

| Reference | Why it is useful |
|---|---|
| [SLEPc: Generalized Hermitian-Indefinite Problems](https://slepc.upv.es/release/manualpages/EPS/EPS_GHIEP.html) | Directly addresses the mathematical class of your pencil. |
| [SLEPc: Krylov-Schur](https://slepc.upv.es/release/manualpages/EPS/EPSKRYLOVSCHUR.html) | Indefinite Lanczos and iterative eigenvalue algorithms. |
| [Discrete Compactness for the p-Version of Discrete Differential Forms](https://doi.org/10.1137/090772629) | Important theoretical foundation for higher-order Nédélec elements. |
| [Ainsworth and Coyle: Conditioning of Hierarchic p-Version Nédélec Elements](https://doi.org/10.1137/S003614290239590X) | Explains the conditioning issues associated with increasing polynomial order. |
| [MUMPS](https://mumps-solver.org/) | Practical alternative for sparse symmetric-indefinite factorization. |
| [Cambridge: Hamiltonian Formulation of Maxwell's Equations for Waveguides](https://doi.org/10.1017/CBO9780511575228.006) | Background for the direct propagation-constant formulation. |
| [Nested Dissection: Cornell Matrix Computations](https://www.cs.cornell.edu/courses/cs6210/2025fa/lec/2025-09-22.html) | Explains sparse fill and the scaling of two-dimensional direct solvers. |

---

# My final judgement

I see three different engineering opportunities here.

**First: make the existing implementation faster.**

This is the most immediate opportunity. The current solver is already practical, but the eigensolver consumes most of the time. SLEPc, better starting vectors and better Krylov-subspace parameters are worth investigating.

**Second: make the eigenmode calculation mathematically cleaner.**

This is the more important scientific opportunity. The mixed formulation, gradient-related nullspace and indefinite mass matrix deserve a proper mathematical treatment. I would prioritize deriving the correct constraint over trying increasingly clever filters.

**Third: make the solver scale better.**

Nested dissection, sparse symmetric-indefinite factorization and higher-order elements are the longer-term opportunities.

My advice is not to pursue all three simultaneously.

### The one thing I would prioritize above everything else

I would ask the engineer to run the following comparison:

\[
\boxed{
\text{ARPACK}
\quad\text{vs}\quad
\text{SLEPc GHIEP}
\quad\text{vs}\quad
\text{SLEPc GNHEP}
}
\]

Same mesh. Same assembled matrices. Same shift. Same target mode. Same accuracy requirement.

That experiment will tell you whether your current bottleneck is primarily the algorithm or the mathematical structure of the eigenproblem.

And one final rule:

**Never accept a faster eigenvalue solver merely because it returns an eigenvalue with a small residual.**

It must return the correct physical microstrip mode, with the correct field distribution, correct propagation constant, and consistent behaviour under mesh refinement.

A fast solver that finds the wrong mode is simply a very efficient way of getting the wrong answer.

That is the standard I would set for this project.
