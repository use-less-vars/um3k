# E13 — antenna far-field post-processor: scope

Status: scope only. No implementation exists, no code is proposed here, and nothing in this document has been measured. Quantities that will eventually be numbers are marked `TBD`; interfaces that do not yet exist in the tree are marked `<to be named>`. Nothing here may be cited as a repo fact until it is written down against a commit.

## 1. What this component is

The far-field post-processor takes the near field of an already-solved problem on a closed surface and produces the radiated far field: pattern versus angle, and optionally radiated power. It is a post-processor in the narrow sense — it reads a solve result and produces a second result. It has its own entry point and its own output artifact. It does not modify the solve, the solver's inputs, or the solver's on-disk cache.

The work splits into two stages, deliberately separable:

1. Extraction — sample the solved field on a prescribed closed Huygens surface and reduce it to the data the radiation integral consumes, with the surface geometry carried alongside it.
2. Radiation — the Kirchhoff / radiation integral over that surface. This stage is handed to TE.

The seam between them is the point of this document. One team's data ends there and another's begins, so the seam must be a file contract with stated contents, not a shared mutable object.

## 2. What this does not do

- No antenna geometry authoring. The surface description arrives fully formed. No CAD surface, no geometry import, no editing of the model.
- No feed model. No ports, no coax, no baluns, no excitation definition. The source the solve used is the source; this component neither defines nor refines it.
- No optimisation and no synthesis. It does not adjust geometry, currents or weights to reach a pattern, null or beamwidth. Any such loop is an outer loop and is somebody else's component.
- No near-to-near transformation and no material handling.
- No change to the solver: not its discretisation, not its convergence criteria, not its outputs.
- No user interface. If a pattern is displayed, it is displayed by whatever already owns display, reading the artifact. This document defines no widgets and no application state.
- No accuracy certification. The component reports what it computed. It does not claim validity against a reference unless a criterion in section 6 says so.

## 3. Inputs it requires off the existing solve

Extraction cannot begin until every item below is available. Each is stated with what "available" means, because the failure mode here is a plausible-looking array carrying the wrong convention.

### 3.1 Field samples

Complex vector E, and preferably H, at caller-chosen points on the surface, in the solver's phasor convention. Available means: E can be obtained at an arbitrary interior point through the solver's existing interpolation entry point, without re-solving. The 3D entry point is `<to be named>`; it must be named by the owner of the 3D solver before this work is scheduled.

### 3.2 Frequency and wavenumber

One frequency per run, with units stated. A sweep is an outer loop over that frequency; it is not a new input to this component.

### 3.3 The surface

A closed surface specification: shape (box, sphere or cylinder), placement and extent in the solver's coordinate frame, and the outward normal convention. Closed is a requirement, not a preference. An open surface yields a pattern that is wrong in a way that still looks plausible.

### 3.4 Units and phasor convention

Length unit, field unit, and the sign convention of the time-harmonic factor, stated once in the artifact metadata so that no consumer has to infer it.

### 3.5 Provenance

Commit sha, the solver settings that affect the field (at least mesh size, element order and boundary condition), and the identity of the solve artifact consumed. Provenance is required, not optional. An artifact whose provenance is unrecorded is unusable and must be treated as absent.

Anything in 3.1 to 3.5 that is missing at run time is a hard error. No defaults, no guessing.

## 4. The Huygens surface

- The surface is chosen by the caller, and must enclose the radiating structure. The extractor does not solve for a surface; it evaluates on the one it is given.
- Sampling points are fixed once per surface, recorded, and reused, so that two runs over the same geometry sample the same points.
- The reduction to tangential components is the extractor's real work. It must emit the tangential components and the surface normal at every sample, because the integral needs both and reconstructing the normal downstream is where sign errors live.
- The outward-normal times tangential-field convention gets one worked example, written once and kept with the artifact. "Outward" is the most common silent error in this class of post-processor.

## 5. The interface it offers TE

One self-describing artifact, written by the extractor, read by TE.

- Format: a single file holding the arrays plus a metadata block that parses as JSON. The container `<to be named>` — one file, no sidecars, no directory-of-numpys.
- Required arrays: sample coordinates (N,3); outward normals (N,3); tangential E (N,3); tangential H (N,3). H is strongly preferred, because an exact field-equivalence formulation needs both and an E-only surface is an approximation that must be labelled as one.
- Required metadata: frequency, length unit, field unit, phasor convention, surface descriptor, and the provenance block from 3.5.
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

An accuracy criterion against a full-wave or analytic radiating element is out of scope for the first cut. It is listed as an open decision, not silently dropped.

## 7. Open decisions

These need a ruling from the owner of the solver or of TE. They are recorded here so they are not rediscovered as surprises.

- D1 The 3D solver's interpolation entry point, and the array and phasor conventions it returns. Everything in 3.1 depends on this. Without it the work cannot start.
- D2 E only, or E and H on the surface. E only is cheaper and sufficient for a far-field-only first cut, but it forecloses near-field checks and exact-equivalence formulations later.
- D3 Whether TE consumes the artifact as a file or as a Python callable. A file is auditable and testable across the seam; a callable is quicker to integrate. The recommendation is the file, with one schema and no exceptions.
- D4 The downstream pattern representation — angular grid, cut planes — which is TE's business, but which the metadata in section 5 must make possible.
- D5 Who owns the reference case in A3, and what tolerance counts as passing it.

## 8. Status

Nothing is implemented and nothing is measured. This document fixes the seam (section 5), the refusals (sections 3 and 6, criterion A2), and the questions that block scheduling (section 7). Implementation starts only after D1 and D2 are answered.
