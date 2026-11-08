# Roadmap after the S-parameter result (2026-11-08)

## Status

New document. Design only. Nothing described here is implemented: there is no Touchstone
writer, no export command in `emfit/cli.py`, no run manifest, no C++ source. This document
supersedes nothing and revises nothing.

## Where the code is, honestly

`emfit/` is a self-contained 3D FDTD solver with a study layer (`emfit/studies.py`; seven
studies: CAVITY, MODES, DUCT, SCATTER, RCS, MICROSTRIP, MICROSTRIP_BOARD) driven by
`emfit run <study> --set KEY=VALUE --out DIR --json`, a port and wave layer (`emfit/ports.py`:
`LumpedPort`, `Probe`, `DftAccumulator`, `BetaFit`, `travelling_waves`), and a viewer
(`server/poc_app.py`, pyvista around a loaded dump: `load_dump`, `build_grid`, `run_web`).
`tools/host_ladder.py` runs the resolution ladder outside the package.

The number this evening settled on is the de-embedded port S11 of 0.325863. The plane at the
load reads 0.318356 and agrees. One column past the load the field collapses to 0.043908, which
is what a terminating load does to a field, and the code now says so out loud instead of
reporting a number.

The old 0.245 is retracted. It came from a two-wave fit with alpha = 11.255 Np/m imposed, and
alpha itself was inverted from |s11| and |s21|. That is not a measurement, it is a
rearrangement, and it is withdrawn rather than re-derived.

So the solver works and yields one defensible number for one geometry at one frequency. The
three moves below are about turning that into something other people and other tools can use.

---

## 1. Co-simulation hooks

### What it is

A stable boundary. Something outside this repo, in any language, hands in a study
configuration, a run happens, and a result comes back with enough provenance that a stranger
can tell what was measured and whether to trust it. Three artefacts: a request (already
designed), a result file in a standard format, and a manifest that explains the result.

### Why it is the right next move here

Because most of it already exists as design. `docs/design/job_schema.md` specifies the job
request, `schemas/emfit.job.v1.schema.json` is on disk, `schemas/examples/` has a worked
example, and `tools/host/validate-job-schema.py` validates it. That schema is explicit that it
says nothing about provenance, on purpose, because an FDTD-shaped provenance block would bake
in a solver assumption.

That is exactly the hole. The request side is designed and the answer side is not. And the tree
already knows how to answer: `emfit run --json` prints a result object, the records under
`evidence/termination/` carry per-plane detail, and `tools/host_ladder.py` writes a payload
whose `meta` block survives a rung failing. None of it is a contract yet.

### What has to be built

`emfit/export.py`, new module:

- `s_parameters(record) -> SParameters` — frequencies and complex S values out of a study
  result or a stored record, without knowing which study produced it.
- `write_touchstone(sp, path, *, z0=50.0, ports=None)` — writes `.s1p` or `.s2p`.
- `touchstone_header(sp, comment_lines)` — option line plus comment block.

The format requirements that are not optional: an option line (`# HZ S RI R 50`, or whatever is
actually true of the data), frequency ascending, and for `.s2p` the column order S11 S21 S12
S22 — that order is the one place a wrong choice silently transposes a model. Port order has to
be declared, not inferred. Reference impedance goes in the option line and must match what the
port normalisation actually used.

`emfit/manifest.py`, new module:

- `RunManifest` — a dataclass, not a bag of dicts.
- `from_study_result(result, record_path, **overrides) -> RunManifest`
- `write_manifest(mf, path)` — one JSON object, sorted keys, stable field names.

Fields that have to be there, because the last two days of forensics were about exactly these:

- which extraction plane, and whether it was legal: `s11_at_plane_valid`,
  `s11_at_plane_invalid_reason` (already produced at `emfit/studies.py`:3706-3711, written into
  the record at :4028-4029);
- which de-embedding: method name, reference plane in metres, loads used for the fit;
- which record file the numbers came from, by path and by hash;
- the code revision (the tree is under version control even though this container is not);
- study name and the fully resolved parameter set, after `--set` overrides and after `coerce()`
  — not what the caller typed;
- what was measured versus what was fitted, per number. This is the field that would have kept
  0.245 out of a quotation.

CLI, in `emfit/cli.py`:

- `emfit export --record PATH --out NAME.s2p [--manifest NAME.json] [--z0 50] [--ports a,b]`
- `emfit run microstrip --set ... --json --export NAME.s2p --manifest NAME.json`

Non-Python entry point: a thin `tools/emfit-job` script that reads a job JSON, shells out to
`emfit run`, and writes the manifest beside the result. Not a second format, not a second code
path — the same `main()` the UI calls.

### First thin slice

One stored record, one study, one frequency. `emfit export` writes a `.s2p` and a manifest for
this evening's geometry. A test reads the `.s2p` back with an independent parser, asserts
round-trip equality of the complex numbers, and asserts the manifest names the plane and the
de-embedding. A day or two of work, and it makes the result citable from outside the repo.

The slice is proven when a second person can take the two files, without reading any of this,
and know whether to trust 0.325863.

### What could make it a dead end

If the MICROSTRIP result object keeps changing shape, the exporter becomes a tax paid on every
study edit. That is a real risk: `emfit/studies.py` is where all the physics lives and it is
not stable. Mitigation is to export from the *record* (already serialised, already versioned
under `evidence/`) rather than from live result objects, and to keep the exporter's input
surface to two functions.

Second dead end: Touchstone has no way to say "this number is fit-derived". If the manifest is
not read, the format launders 0.245-class numbers into a standard file that tools will trust.
That is why `--manifest` should not be optional.

### Plane validity stops at `res.geometry`

`emfit run --json` prints study/values/metrics/figures/attachments and no geometry field
(`emfit/cli.py`:197-200), and no study registers `s21_plane` as a Param, so `--set` cannot
reach the gate. Today's route is `evidence/termination/run_build_A.py` (`--s21-plane-index` /
`--s21-plane-col`, default load column + 1), whose geometry copy floats every scalar:
`geometry.s11_at_plane_valid` reads 0.0/1.0 and `s11_at_plane_invalid_reason` vanishes when
None. Trust nested `s11_at_plane.valid` / `.invalid_reason`. Provenance only the evidence
script can emit is not a co-simulation contract; closing it is the first concrete task here.

### Cost

Days, not weeks, for the slice. The format work is small and well specified. The real cost is
the discipline of pinning a contract while the study layer still moves.

---

## 2. SPICE integration

### What it is

Getting the S-parameters into a circuit simulator (ngspice, Xyce) so the driver and the
terminating network are not frozen at simulation time.

### The case for it, argued rather than assumed

The strongest argument is that this codebase currently holds the load fixed. The termination is
baked into the geometry: the load column is resolved once (`emfit/studies.py`:2910), the
effective load impedance is computed once (`_load_z_eff`, :2410), and `LineReference` /
`MicrostripWave` are built around that. Every reflection number here means "S11 into this
load". A user with a real driver and a real receiver is asking a different question, and the
honest answer to it is a circuit-level one.

The counter-argument deserves stating: a line plus a load is a two-port for which a closed form
often suffices, and pulling in a circuit simulator adds a dependency, a licence question, and a
second place for units to go wrong. That is legitimate for simple terminations. It stops being
legitimate once the load is nonlinear or the driver has an output network, because the FDTD
cannot represent either.

Verdict in one line: worth doing for the co-simulation hook, not worth doing as a primary
output path.

### What has to be built

Format compliance, which is where this usually fails in practice:

- Option line with the reference impedance, matching what the port normalisation used. A `.s2p`
  claiming R 50 while the solver normalised to something else produces a plausible, wrong
  answer.
- Port order declared and documented in the manifest, because S12 and S21 swap silently.
- Frequency ascending, no duplicated bins, no gaps.
- DC and low frequency: FDTD produces nothing below the first simulated bin. There are three
  honest options and the code must pick one and record which:
  1. refuse, writing `low_freq_policy: "not_extrapolated"` into the manifest;
  2. hold the lowest bin constant down to DC, labelled as an extrapolation;
  3. fill the DC point from the quasi-static solver (`emfit/quasistatic.py`), labelled. For a
     transient run, option 1 will often fail to converge, which is a reason to offer 3, not a
     reason to pretend 2 is a measurement.
- Whether ngspice and Xyce each read a Touchstone directly, or need a rational fit /
  pole-residue model, has to be checked against those tools' own documentation. This document
  does not assume an answer; it is a to-verify item before the hook is designed in detail.

`emfit/spice.py`, new module:

- `to_spice_subckt(sp, name, *, z0, dc_policy) -> str` — an `.include`-able snippet.
- `to_spice_sources(...)` — equivalent sources for simulators without a native S-element.
- `fit_rational(sp, order, tol)` — if a fit turns out to be the required route.

`emfit/terminations.py`, new module, for the co-simulation hook:

- `LoadNetwork` base class; `Lumped(R, L, C)`, `Tline(z0, td)`, `FromFile(path)`.
- Studies accept `--load` as either the built-in termination or a netlist file, and the result
  records which.

What must move in the current flow: the load column resolution and `_load_z_eff` assume a
fixed, linear termination. A co-sim hook means the FDTD keeps a recorded port waveform (the
port accumulators already produce one) and the circuit simulator closes the loop on it. That is
a bigger project than the export. The realistic first version is one-way: FDTD produces
S-parameters, the simulator consumes them, the load stays linear.

### First thin slice

The same `.s2p` from section 1, dropped into a hand-written ngspice netlist with a voltage
source and a resistive termination, checking that the simulated |S11| at the solved frequency
matches 0.325863 to whatever tolerance the discretisation justifies. No new physics, no new
code in `emfit/` beyond the exporter. A day, plus the time spent fighting the simulator.

### What could make it a dead end

If the only consumers wanted a single reflection number, this is machinery for nobody. That
shows up as the export never being used twice, which is cheap to find out: ship the `.s2p`
first and wait.

Also a dead end if the low-frequency policy cannot be made honest without a much wider band
simulation. Then the simulator converges on an extrapolation and the exercise moves the problem
rather than solving it.

### Cost

The export side is days. A genuine co-simulation loop, FDTD and circuit simulator exchanging
waveforms per timestep, is weeks and needs a decision on who owns the time base. Recommend the
one-way version only, for now.

---

## 3. C++ port

### What it is

Moving the numerically hot parts out of Python while `emfit/` stays the thing you talk to.

### Real bottlenecks, named

- The FDTD update loop in `emfit/evolve.py` — every cell, every step, Python with NumPy
  vectorisation over slices. The dominant cost of any run that is not tiny.
- The eigenmode and modal work (`emfit/eigen.py`, `emfit/modal.py`, `emfit/mode2d.py`,
  `emfit/modalport.py`): sparse factorisation and pencil solves, where the Python is a thin
  wrapper around SciPy and the cost is already in C.
- The per-rung ladder sweep in `tools/host_ladder.py` — the whole ladder is re-run per
  resolution, so anything that makes one rung cheaper multiplies.
- The studies layer, but only its bookkeeping; it is not where the time goes.

`docs/design/cpp_solver_arch.md` already covers the 2D eigenproblem path, rules SuperLU for
port v1 on attribution grounds, and leaves binding, threading and storage format open. A new
port should read those decisions, not re-open them.

### Strategy

Python control plane, compiled kernel behind a flat-array API. No per-cell Python objects, no
callbacks per timestep, no Python in the inner loop. The boundary is a few functions over
contiguous buffers:

- `kernel_init(nx, ny, nz, dt, materials_arrays) -> handle`
- `kernel_step(handle, n)` — advance n timesteps
- `kernel_probe_dft(handle, probes) -> complex arrays`
- `kernel_fields(handle) -> arrays` — for the viewer and for evidence dumps

Python owns geometry, materials, the study layer, the manifest, the export. C++ owns
arithmetic. `emfit/_kernel.py` holds the binding and the pure-Python fallback, so the package
keeps working with no compiler present.

### Proving equivalence

The regression oracle is already in the tree: the records under `evidence/termination/` and the
ladder payloads written by `tools/host_ladder.py --json`. Compare bin-by-bin on the DFT spectra
and number-by-number on the ladder `meta` block, at a relative tolerance derived from the
discretisation and stated in the test, not invented to make it pass. Any field outside that
tolerance blocks the port, because a fast kernel that is subtly wrong is worse than a slow one
that is right.

Also required: the fake rung in `tests/test_host_ladder_partial.py` keeps passing untouched,
since it pins the contract the ladder reports through, not the solver.

### The real risk

Two implementations drifting. Same class of bug as plane-past-the-load: everything runs, every
number looks like a number, and one is wrong because a boundary or an indexing convention
differs by one column. In Python there is one code path and drift is impossible. With two there
must be a differential test that runs on every change, not a one-off comparison at porting
time.

### Verdict

Not yet. Do the export first. A correct but slow solver other tools can call is worth more than
a fast one nobody can call. Port the update loop only after the export and the manifest exist,
because the manifest is what makes a fast kernel checkable against the slow one.

### Cost

Weeks for a correct kernel plus binding, assuming the eigen path stays in SciPy. The
differential harness is not optional and is not small.

---

## What has to be true before any of this

These are debts, not stop signs. Each is a place where the tree currently disagrees with
itself, and each would be inherited by anything built on top.

**Two pre-existing failures in `tests/test_studies.py`.** One is a cut-guard that does not
raise when the test says it should. The other expects `gamma_port` at 0.118088 and gets
0.1520918610341127. Neither is explained. Until they are, the study layer's own tests are
telling us something we have chosen not to hear.

**`s11_at_plane_valid` exists on two stored records.** The gate is now written through end to
end: `gate_gate_build_A_p50.json` carries a valid plane at 0.3183560234963229 and
`gate_gate_build_A_p51.json` an invalid one at the load column + 1, reason `plane_beyond_load`.
The debt is now narrower: only those two records carry the flag, and the public CLI cannot
produce it at all (§1, *Plane validity stops at `res.geometry`*).

**An unresolved 2.0% gap between a fitted beta of 228.25 and `line.beta` of 232.80.** Two
answers for the same quantity, both from code in this tree. Not large enough to break the S11
result, large enough that quoting either without a note is overclaiming, and exactly the kind a
second implementation would turn into a silent disagreement.

None of these blocks the export. All of them block trusting anything built on top of it for
very long.

Ultra Maxwell 3000 earned the name tonight: the field collapsed in the right place, the number
held, and for once the code said so instead of inventing a fit.
