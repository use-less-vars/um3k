# A 3D near-to-far-field transform on a recorded Huygens box: an enquiry put to TE

Status: OPEN enquiry against commit `27df752`. Not a decision, a plan or a gate; no code
proposed. Read-only: nothing here was run, measured or fitted. The transform itself does
not exist yet -- `emfit/ntff.py` reads the archive back and stops at the reading.

What exists, and is not in question: `emfit/huygens.py:211` places a closed box on the Yee
complex, `emfit/huygens_fields.py:686` writes what the time loop recorded on it to a
`.npz` archive (18 keys: the sample geometry, the tangential phasors `E_t`/`H_t`, the
equivalent currents `J_s`/`M_s`, the per-face and net surface power), and
`emfit/ntff.py` turns such an archive back into arrays. Everything downstream of the
arrays -- the far field, the pattern, the gain -- is missing, and the three questions below
are why it has not been written.

## Context

The surface record is complete and the far-field transform that consumes it is not
written. Three conventions have to be ruled on before it is, because each of them changes
the numbers the transform emits while leaving it looking correct.

## The questions

We have successfully extracted the Huygens surface using our FDTD engine. We are storing the tangential electric and magnetic fields (E_t, H_t) co-located at the integer time step, and we have validated the power flux against an analytic dipole to within 0.18%.

We are now ready to build the 3D Near-to-Far-Field (NTFF) post-processor. The target is to compute the far-field radiation pattern E(theta, phi) and directivity/gain.

Given our grid (where the surface is a box conforming to Yee node planes), what is the exact discrete Kirchhoff integral we should implement? Specifically:

1. Do we compute the equivalent currents J_s = n_hat x H_t and M_s = -n_hat x E_t at the surface and then integrate them with the free-space Green's function, or should we directly integrate the fields using the Stratton-Chu equations?
2. How should we handle the spatial integration over the discrete cells (e.g., trapezoidal rule, or does the Yee staggering require a specific 2D quadrature)?
3. What is the exact normalization factor for the far-field pattern to ensure the absolute gain (dBi) is correct relative to the input power?

Additional questions from the implementation side:

4. Where is the equivalent-current sample located on a conforming box surface - at the face centroid, or offset by a half cell from the Yee node plane - and does the phase of the far-field integrand need a corresponding half-cell correction?
5. For absolute gain, is the input power correctly taken as the outgoing flux already computed on the surface (valid only in the lossless case), or must it be integrated separately from the source current, and how should the two differ if the surface sits inside a PML?
6. What (theta, phi) sampling convention should we emit so that the pattern plots directly in a standard dBi polar plot (theta measured from +z, phi from +x, and the standard IEEE polarisation basis)?
7. For surfaces of 1e3-1e4 faces and 1e3-1e4 directions, is direct summation over faces acceptable, or do you recommend an FFT-based NTFF, and at what problem size does it become necessary?
8. What analytic reference should the NTFF be validated against first, and what exact value should a Hertzian dipole produce (peak directivity 1.5 = 1.7609 dBi, with pattern sin(theta)) - including any discretisation-induced deviation you would expect at our resolution?
