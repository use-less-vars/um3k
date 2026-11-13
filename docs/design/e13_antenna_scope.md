# E13 — antenna far-field post-processor: scope

Status: scope only. No implementation exists, no code is proposed here, and nothing in this document has been measured. Quantities that will eventually be numbers are marked `TBD`; interfaces that do not yet exist in the tree are marked `<to be named>`. Nothing here may be cited as a repo fact until it is written down against a commit.

## 1. What this component is

The far-field post-processor takes the near field of an already-solved problem on a closed surface and produces the radiated far field: pattern versus angle, and optionally radiated power. It is a post-processor in the narrow sense — it reads a solve result and produces a second result. It has its own entry point and its own output artifact. It does not modify the solve, the solver's inputs, or the solver's on-disk cache.

The work splits into two stages, deliberately separable:

1. Extraction — sample the solved field on a prescribed closed Huygens surface and reduce it to the data the radiation integral consumes, with the surface geometry carried alongside it.
2. Radiation — the Kirchhoff / radiation integral over that surface. This stage is handed to TE.

The seam between them is the point of this document. One team's data ends there and another's begins, so the seam must be a file contract with stated contents, not a shared mutable object.

The solve this reads is an FDTD solve on a uniform grid, and that single fact shapes everything below. The field lives on a Yee cell, so E and H are staggered in space and half a time step apart in time. There is no stored "field at a point" to read: a sample is always an interpolation, and the two fields are always at different instants until something co-locates them. Sections 3.1 and 6 exist because of that, and section 2 says what this component may not assume about the grid.

## 2. What this does not do

- No antenna geometry authoring. The surface description arrives fully formed. No CAD surface, no geometry import, no editing of the model.
- No feed model. No ports, no coax, no baluns, no excitation definition. The source the solve used is the source; this component neither defines nor refines it.
- No optimisation and no synthesis. It does not adjust geometry, currents or weights to reach a pattern, null or beamwidth. Any such loop is an outer loop and is somebody else's component.
- No meshing, and no accuracy-by-refinement loop. The grid is the solver's, uniform by construction, and it is not this component's to change. If a pattern needs finer resolution, that is a finer solve — run by the solver and paid for by the solver. The extractor does not refine a mesh, does not iterate towards a converged answer, and does not claim the accuracy of the grid it is reading.
- No near-to-near transformation and no material handling.
- No change to the solver: not its discretisation, not its convergence criteria, not its outputs.
- No user interface. If a pattern is displayed, it is displayed by whatever already owns display, reading the artifact. This document defines no widgets and no application state.
- No accuracy certification. The component reports what it computed. It does not claim validity against a reference unless a criterion in section 6 says so.

## 3. Inputs it requires off the existing solve

Extraction cannot begin until every item below is available. Each is stated with what "available" means, because the failure mode here is a plausible-looking array carrying the wrong convention.

### 3.1 Field samples: E and H, co-located in space and in time

Both E and H, at caller-chosen points on the surface. On a Yee grid neither is directly available: the six components sit at different offsets within a cell, and the leapfrog update puts E and H half a time step apart by construction. "Available" therefore means three things at once, and each of them is named below (D1):

- the access path that returns both fields at an arbitrary interior point without re-solving: `extract_huygens_surface`, named in section 7 (D1);
- the spatial co-location rule it applies — which averaging of the staggered components produces a value at the requested point: the `interp` argument, `"linear"` in the first cut and nothing else (D1);
- the time-level convention — how the two fields are brought to the same instant before any product of them is formed, and which instant that was: E's own integer time level `n`, reached from H by averaging the half-steps either side of it, recorded in the artifact metadata (D1, section 5).

An E-only sample is not sufficient, and section 5 says why. Sampling E and H a half step apart is not a detail either: the resulting pattern is smooth, plausible and wrong, which is the worst failure mode available to this component.

### 3.2 Frequency and wavenumber

One frequency per run, with units stated. A sweep is an outer loop over that frequency; it is not a new input to this component.

### 3.3 The surface

A closed surface specification: shape (box, sphere or cylinder), placement and extent in the solver's coordinate frame, and the outward normal convention. Closed is a requirement, not a preference. An open surface yields a pattern that is wrong in a way that still looks plausible.

### 3.4 Units and phasor convention

Length unit, field unit, and the sign convention of the time-harmonic factor, stated once in the artifact metadata so that no consumer has to infer it.

### 3.5 Provenance

Commit sha, the solver settings that affect the field (at least the Yee cell size, the time step, and the boundary condition), and the identity of the solve artifact consumed. Provenance is required, not optional. An artifact whose provenance is unrecorded is unusable and must be treated as absent.

Anything in 3.1 to 3.5 that is missing at run time is a hard error. No defaults, no guessing.

## 4. The Huygens surface

- The surface is chosen by the caller, and must enclose the radiating structure. The extractor does not solve for a surface; it evaluates on the one it is given.
- Sampling points are fixed once per surface, recorded, and reused, so that two runs over the same geometry sample the same points.
- The reduction to tangential components is the extractor's real work. It must emit the tangential components and the surface normal at every sample, because the integral needs both and reconstructing the normal downstream is where sign errors live.
- The outward-normal times tangential-field convention gets one worked example, written once and kept with the artifact. "Outward" is the most common silent error in this class of post-processor.

## 5. The interface it offers TE

One self-describing artifact, written by the extractor, read by TE.

- Format: a single file holding the arrays plus a metadata block that parses as JSON. The container `<to be named>` — one file, no sidecars, no directory-of-numpys.
- Required arrays: sample coordinates (N,3); outward normals (N,3); tangential E (N,3); tangential H (N,3). Both fields are required, not preferred: the near-to-far transform forms equivalent currents from both, and an E-only surface would force a wave-impedance assumption that does not hold in the near field — which is exactly where the surface has to sit.
- Equivalent currents. The integral forms `J_s = n_hat x H` and `M_s = -n_hat x E` from those tangential arrays, with `n_hat` the outward surface normal carried per sample — the reason section 4 insists the normal travels with the data and section 3.3 insists the outward convention is stated. The sign of the time-harmonic factor is section 3.4's, and it is recorded rather than assumed. This is the formulation TE was asked to confirm (D2).
- Required metadata: frequency, length unit, field unit, phasor convention, surface descriptor, the time level the two fields were co-located to (3.1), and the provenance block from 3.5.
- The artifact carries a schema version integer. TE refuses unknown major versions rather than guessing.
- Ownership is one-directional. This component writes, TE reads. Neither side mutates the other's file, and no live Python object crosses the boundary.
- Failures are the writer's responsibility. A missing required array, a non-finite sample or an unrecorded provenance field fails at write time, loudly, before the artifact exists. It is not deferred to the reader.

## 6. Acceptance criteria

Each criterion is written so that it can fail.

- A1 Round trip. An artifact written and read back returns identical arrays and metadata that parses. Recorded in a test.
- A2 Refusal. A surface specification missing normals, or a sample set containing a non-finite value, is refused before any artifact is written, and the error names the requirement from section 3 that was not met.
- A3 Self-consistency. For an analytic case — a plane wave crossing the surface — the extracted tangential components reproduce the exact tangential field to a stated tolerance, `TBD`. Recorded as a test, not as a claim.
- A4 Provenance. The artifact records the commit sha of both the solver and the extractor, and a test asserts those fields are present and non-empty.
- A5 Determinism. Two runs on identical inputs sample identical points and produce identical arrays. Machine-checked, not asserted in prose.
- A6 No-solve guarantee. Extraction never invokes the solver. This is proven causally, by counting calls to the solver's entry point in a test, not by inspecting imports.
- A7 Handoff. A small synthetic reference artifact is committed as a fixture, and a reader test on the TE side consumes it and asserts the section 5 contract. This is the mechanism that keeps the two sides from drifting apart.
- A8 Co-location. For the same analytic plane wave, the extracted E and H are formed into the surface power flux and compared against the exact flux, to a stated tolerance, `TBD`. This is the criterion that fails when the two fields are sampled half a time step apart or interpolated by inconsistent rules: each field on its own stays plausible, and only their product is wrong.

An accuracy criterion against a full-wave or analytic radiating element is out of scope for the first cut. It is listed as an open decision, not silently dropped.

## 7. Open decisions

These need a ruling from the owner of the solver or of TE. They are recorded here so they are not rediscovered as surprises.

- D1 DEFINED — the extraction call. `extract_huygens_surface(bounds, time_step, interp="linear")`, three arguments and no fourth:
  - `bounds` — the section 3.3 surface descriptor: shape, placement and extent in the solver's coordinate frame, and the outward-normal convention. It is not optional and it is not defaulted. An open or unbounded specification is refused here, before any sample is taken (A2).
  - `time_step` — the solver's time step, in seconds. It is an argument because the half-step offset between E and H is only expressible in time against this number, and because section 3.5 provenance records it: a sample whose `time_step` is not the one the solve ran with is a sample of a different problem.
  - `interp` — the co-location rule, `"linear"` by default and the only value the first cut supports. Any other value is refused loudly; there is no silent fallback to linear, because a fallback would mean the samples carried one rule while the artifact recorded another.
  The remaining section 3 inputs are deliberately NOT arguments: the solve handle (3.1), the frequency (3.2), the units and phasor convention (3.4) and the provenance (3.5) are bound once before sampling, cannot vary per sample, and would be meaningless per call. They belong to the extractor the call is a method of, and they leave in the artifact rather than in an argument list.
  Return contract: the section 5 artifact, or a failure that names the unmet section 3 requirement. Nothing partially written survives a failure (A2).
  Time co-location, stated once here because it is the obligation the Yee grid imposes: E and H are half a time step apart, so the extractor brings both to E's own integer level `n`, reaching it from H by averaging the half-steps either side. Which instant was chosen, and which rule reached it, are both recorded in the artifact metadata; a consumer never infers either. `TBD` is the temporal interpolation order beyond the first cut, and A8 is the criterion that fails if this is done wrong — each field on its own remains plausible and only their product is wrong.
  Not yet implemented: this section names an interface, not a function in the tree. Nothing here may be cited as a repo fact until it is written down against a commit, and A6 is the criterion that keeps the extractor from quietly invoking the solver to satisfy it.
- D2 RULED — both E and H are captured. The near field has no fixed wave impedance, so an integral over E alone cannot be justified where the Huygens surface has to sit, and the equivalent currents need both fields. TE is asked to confirm the exact formulation — the equivalent currents and the power-conjugate overlap integral — not whether both fields are needed.
- D3 Whether TE consumes the artifact as a file or as a Python callable. A file is auditable and testable across the seam; a callable is quicker to integrate. The recommendation is the file, with one schema and no exceptions.
- D4 The downstream pattern representation — angular grid, cut planes — which is TE's business, but which the metadata in section 5 must make possible.
- D5 Who owns the reference case in A3 and A8, and what tolerance counts as passing it.

## 8. Status

Nothing is implemented and nothing is measured. This document fixes the seam (section 5), the refusals (sections 3 and 6, criterion A2), the sampling obligation the Yee grid imposes (section 3.1, criterion A8), and the questions that block scheduling (section 7). D2 is ruled and TE has confirmed the formulation (section 5). D1 is defined (section 7): the call, its three arguments, its return contract and its time co-location obligation are named, though nothing is implemented. Implementation starts only after D3 is ruled.
