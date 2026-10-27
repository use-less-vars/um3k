# The numerical core contract

Status: design only. Nothing here has been implemented, and nothing here authorises a run. There is no
schema file, no validator, and no code that emits any of the documents described below.

Reading discipline: no code was executed to produce this document. Every statement about the repository
is a reading of a named line range, cited as `file:line`. Where a fact is known only through
`decisions.md`'s record of some other file, this document says so rather than citing the other file as if
it had been read directly.

The interface this contract lives inside is already specified: `decisions.md:7012-7093` (§101.19) fixes
`emfit.job.v1` in and `emfit.result.v1` out, and states at `decisions.md:7014` that it is design only and
authorises nothing. That section has no core-level sub-object. Everything this document adds to it is
marked **extends §101.19**, and each such addition names the defect in `decisions.md` that motivates it.

## 1. What a numerical core is

**Decision:** a core is the operation that advances (or solves) a discretised field problem and hands back
field unknowns; it is defined by that operation and by nothing else.

Reason: the current 3D core's entire update is `self.h -= self.dt * (self.inv_m_mu * (self.C @ self.e))`
(`emfit/evolve.py:191`, inside `step()` at `:186`), an expression containing no port, station, frequency
or S-parameter term, while the extraction layer already consumes raw `e`/`h` vectors and nothing else
(`emfit/ports.py:253` `column_path`, `:470` `station_poynting`, `:564` `DftAccumulator`).

The contract is therefore a statement about a boundary that already exists in the tree, not a proposal to
create one. `class FITStepper` (`emfit/evolve.py:83`) holds `.e`, `.h`, `.C`, `inv_m_mu`, `.dt`, `.time`;
`class Leapfrog(FITStepper)` (`:304`) adds only a check of `dt` against the Courant bound (`:308-309`,
bound computed by `cfl_dt` at `:68-79`). That is the whole of what the current core is.

### Opaque, and what opaque forbids

Opaque means the caller is given field unknowns and the metadata the contract names, and is given no
handle on how they were produced. The test of opacity is mechanical: a proposed core requirement that
mentions any of the six concerns below is not a core requirement, it is an extraction or study
requirement wearing a core's name.

**Port modes.** Forbidden. Mode profiles are a 2D eigenproblem solved above the boundary: `solve_modes`
(`emfit/mode2d.py:795`), `solve_modes_mixed` (`:935`), returning `class Mode2D` objects (`:605`) carrying
`freq`/`k0`/`beta`/`beta_sq`/`eps_eff`/`residual`/`candidates`/`e_t`. The microstrip profile used by the
audit path is likewise imported separately (`from emfit.mode_profile import microstrip_mode_profile`,
`tools/host/c1-audit/c1_audit.py:160-162`). A core that knew about port modes could not be replaced by one
that does not have them.

**Stations.** Forbidden. A station is a geometric line segment at which a one-time-sample Poynting flux is
computed (`emfit/ports.py:470`, which states it is "NOT a phasor and NOT 0.5 Re(V conj I)"); station
locations in the microstrip study are study constants (`emfit/studies.py:1177`, `:1179`). If stations were
in the core, the station count would be a core parameter — and today it is a driver constant
(`N_STATIONS=9`, `.scratch/tol/tol_driver.py:101-108`) that must agree with a study constant
(`MS_N_STATIONS = 9`, `emfit/studies.py:1179`).

**S-parameters.** Forbidden, and this is the load-bearing one. `reflection` (`emfit/ports.py:727`) is
"S11 = v_minus/v_plus at a reference plane"; `transmission` (`:745`) is "S21 from forward amplitudes at two
ports a distance d apart". Both are ratios of extracted phasors, computed after a `DftAccumulator`
(`:564`) has integrated `w(n) values[n] exp(-2j pi f n dt)` (`:609`) over the time series. A core that
produced S-parameters directly would not be a core; it would be what §101.19 calls a surrogate, which
produces a result document and is a different kind of thing (`decisions.md:7075`).

**Pencils.** Forbidden to the 3D core; owned by the 2D core. The generalised eigenproblem is `mode2d`'s
business (`emfit/mode2d.py:795`, `:935`), and it has its own contract, its own diagnostics (`residual`,
`:1024-1027`) and its own anchor (`tools/host/c1-audit/pecbox_variant.py:561-620`). "Core" in this
document is a family, not a single class: today there is a 3D time-domain member (`emfit/evolve.py`) and a
2D eigenproblem member (`emfit/mode2d.py`), and §5 uses exactly that fact.

**Gates.** Forbidden. A gate today is a post-processing over a stored capture and does not touch a
stepper at all: `tools/gates_101_20.py:64-66` reads `.scratch/tol/logs/TOLFLUX_planes.npz`, `:69` names
`BLOCK_KEYS = ("plane_Ey","plane_Ez","plane_Hy","plane_Hz")`, and `:62` imports `flux_from_phasors` from
`emfit/plane_phasor`. A gate is a property of stored arrays. The core's only obligation to any gate is to
make the arrays it needs exist.

**The study layer.** Forbidden, and this is the only one the tree currently violates. `emfit/studies.py`
imports the concrete core at `:54` (`FITStepper`), the discretisation at `:55` (`Grid`), the operator
container at `:59` (`CellComplex`), the plane convention at `:60` (`PLANE_CONVENTION`) and the
extraction primitives at `:62-67`. §4 treats this as the swap blocker it is.

## 2. The core/extraction boundary

**Decision:** the boundary is drawn by one question — if this concern moved to the other side, would a core
without it become unreplaceable? — and by no other consideration.

The table answers each concern explicitly rather than by implication.

| Concern | Owner | Justification (swappability) |
|---|---|---|
| Port modes | Extraction | A 2D eigenproblem in `emfit/mode2d.py` (`:795`, `:935`) and a profile function imported separately (`tools/host/c1-audit/c1_audit.py:160-162`). A core that had to carry mode-solver code could not be swapped for a pure time-domain or GPU kernel. |
| Station phasors | Extraction | `DftAccumulator` (`emfit/ports.py:564`) integrates the time series at chosen edges (`:609`); it needs time samples, not a core. A frequency-domain core has no time series to hand it, so the concern cannot be core-side without excluding that core shape. |
| S-parameters | Extraction | Ratios of derived phasors at a reference plane (`emfit/ports.py:727`, `:745`). Any core that owned S-parameters would subsume the extraction layer and could not be replaced by a core that did not. |
| Frequency sweep | Split: the set is contract-level, the consumption is not | The frequency set is a job field already (`frequencies_ghz`, `decisions.md:7031`), and §101.19(f) asserts that a frequency-domain FEM, a GPU FDTD and a surrogate all produce the same result document (`decisions.md:7075`). A time-domain core must be told the set only so the extraction knows what to accumulate; a frequency-domain core must be told it because it solves there. Keeping the set in the contract and the consumption solver-side is the only arrangement in which both are true. |
| Mesh / grid | Core, with a declared summary in the result | The step size is a core property: `cfl_dt` derives the Courant bound from the smallest cell width (`emfit/evolve.py:68-79`) and `class Leapfrog` enforces it (`:304-309`). A core that did not own its mesh could not own its time step. What crosses the boundary is a summary, and the summary must be solver-specific because `mesh_cells`/`cell_mm` are structured-grid quantities (`decisions.md:7091`). |
| Refinement decision | Extraction (driver), never core | Convergence is a property of an observable, and the core does not know observables (row 2, row 3). The quality figure is recorded per observable in the result (`tolerance_achieved` keyed by `S11`/`S21`, `decisions.md:7050`). Extraction already emits discretisation *advice* for this reason — `suggest_probe_spacing` (`emfit/ports.py:1267`) is a recommendation about probe placement, not a decision the core takes. |

Two rows are splits rather than clean sides, and each has a real cost, so both are stated:

The frequency-sweep split costs the contract a field that one core shape will ignore: a time-domain core
receives `frequencies_ghz` and does nothing with it except pass it to the accumulator, which means the
field can be present and silently unused. **Decision:** keep the split and require a time-domain core to
echo the set back in its provenance, so an unused set is visible rather than invisible. Reason: the
alternative — letting each core shape declare its own job field — breaks the property that a pinned `v1`
caller keeps working (`decisions.md:7059`).

The mesh split costs the result document a shape that is not universal. **Decision:** provenance carries a
small required core (`solver`, `tolerance_achieved`, `reference`, `commits`, `decisions_section`) plus an
open solver-specific object, and `mesh_cells`/`cell_mm` move into that object. This **extends §101.19** and
is exactly the repair recorded as defect (`decisions.md:7091`), which states that "a frequency-domain FEM
has no `cell_mm`, and a surrogate has neither a mesh nor a cell". Reason: as drafted at
`decisions.md:7045-7050` the provenance block is FDTD-shaped and would have to be reinterpreted by every
non-FDTD core, which is the silent reinterpretation `decisions.md:7059` forbids.

## 3. Three core shapes

All three must satisfy §1 and §2 unchanged. What follows is what each needs that today's core is not told,
and what each may not be asked for. No stubs: each shape is described to the level at which its
incompatibility with today's tree can be checked.

### What today's core is not told

Five things, each of which a swapped core must receive and the current core does not:

1. **What is wanted, at which frequencies, to what tolerance.** The job carries `observables`
   (`decisions.md:7030`) and `tolerance` (`:7032`), but these are consumed study-side: the driver passes
   `f_target=` into a study call (`.scratch/c3_driver.py:156`) and the core sees none of it.
2. **The time step as a contract value.** It is currently a driver literal,
   `ANCHOR_DT=1.9065748695309721e-13` (`.scratch/tol/tol_driver.py:101-108`), while the bound that
   justifies it is computed inside the core (`emfit/evolve.py:68-79`). The number that defines
   comparability between runs is therefore not in any interface.
3. **A storage budget.** Today's workaround is to monkeypatch the core's own operator methods
   (`.scratch/tol/tol_driver.py:48-96`, patching `CellComplex.curl_dual`/`curl_h_to_e` at `:58-96`) to
   avoid "the second 769,356,828-byte sparse copy" (`:73-74`). A core whose memory behaviour can only be
   changed by editing its source is not swappable.
4. **Which field samples must be materialised.** Plane capture keys are literals downstream
   (`tools/gates_101_20.py:69`), and the dump itself is reached by calling study internals
   (`.scratch/tol/tol_driver.py:297-301`). The core is told nothing; the caller guesses.
5. **A quality verdict.** The result document is three-valued, `ok`/`degraded`/`failed`
   (`decisions.md:7043`, explained at `:7055`), but the core has only "it ran". The nearest thing to a
   quality number inside a core is `mode2d`'s `residual`, which is explicitly "a *diagnostic* ... **not**
   [a tolerance]" (`emfit/mode2d.py:1024-1027`).

**Decision:** all five become core-contract inputs or outputs, carried in a core-level sub-object inside
the job and the result. This **extends §101.19**, which has no core-level sub-object at all
(`decisions.md:7024-7034`, `:7040-7053`). Reason: every one of the five is currently encoded as a constant
or a monkeypatch in driver code, which is the definition of an interface that does not exist yet.

### FEM 3D external package

Inputs: the discretisation it will build itself, material assignment, boundary conditions, the source
definition, the frequency set (`decisions.md:7031`), the time-step policy from item 2, and the core
sub-object.

Returns: the field solution at the requested frequencies, plus the required provenance quantities
(`solver`, `tolerance_achieved`, `reference`, `commits`, `decisions_section`, per `decisions.md:7091`'s
repair) and its own solver-specific object describing its mesh.

Must be told, today not told: the frequency set as a solve parameter rather than as an accumulation
parameter (item 1); the tolerance per observable — this **extends §101.19**, which records the
scope-asymmetry of a global job tolerance against a per-observable achieved tolerance as defect
(`decisions.md:7089`) and notes that the cheaper repair is to make the request per observable too; and the
geometry, which today is board-shaped (`decisions.md:7093`, "parametric geometry is only a word"), so a
parametric form **extends §101.19** as well.

Cannot be asked for: any time series. It has no leapfrog loop, so it cannot feed the `DftAccumulator`
that integrates `w(n) values[n] exp(-2j pi f n dt)` (`emfit/ports.py:609`), and station phasors as defined
(`:470`) have no meaning for it. It cannot supply `cell_mm` (`decisions.md:7091`). It cannot expose Python
objects, so the assertion style at `.scratch/lever/run_real.py:50-53` — `inspect.getsource` on
`CellComplex.curl_dual` — is impossible against it.

### C++ FIT production port

Inputs: the same contract, plus a thread count and a dt policy, because the time step is a core property
(item 2) and the result must be idempotent under an input hash while determinism across machine, thread
count and BLAS is explicitly not supported by anything in the repo (`decisions.md:7065`).

Returns: `e`/`h` samples at declared probes and on the declared planes (item 4), the `dt` actually used,
the three-valued status (item 5), and the required provenance core.

Must be told, today not told: the probe and plane list as data rather than as a source-level patch; the
storage budget (item 3). It also needs the frequency set only for the extraction handshake, per the split
in §2.

Cannot be asked for: in-memory mutation as a variation mechanism. The only way the tree varies the 2D core
today is by monkeypatching `emfit/mode2d.py:539 pec_edge_mask` and `:571 pec_node_mask` on the imported
module for the duration of another import (`tools/host/c1-audit/pecbox_variant.py:33-44`, whose docstring
explains that this is necessary because "c1_audit.py is a flat script: no main() ... There is therefore NO
caller-side seam *inside* c1_audit.py"). An out-of-process core has no analogue of that, so the variation
point must become the contract. It also cannot be asked to expose source for `inspect.getsource`
(`.scratch/lever/run_real.py:50-53`), and it cannot be asked to hold the whole transient resident.

### GPU/JAX FIT

Inputs: as the C++ shape, plus a device policy and an explicit determinism policy, for the same reason at
`decisions.md:7065`.

Returns: as the C++ shape, with its own solver-specific object naming the backend and the reductions it
used.

Must be told, today not told: everything in items 1-5, and in particular that its output will be compared
against a CPU run, so the comparison quantity must be dimensionless or tolerance-checked rather than
bitwise. That requirement is not in the job today.

Cannot be asked for: bitwise equality with a CPU core (`decisions.md:7065`); the anchor's exact cell count,
since `ANCHOR_N=4894400` with `ANCHOR_GRID=(322,200,76)` (`.scratch/tol/tol_driver.py:101-108`) is a
grid-bound literal, not a core-independent fact — note that the same figure appears as `mesh_cells` in the
example provenance block at `decisions.md:7045`, which is an observed equality between the two documents
and not an argument that the figure is universal. And it cannot be asked to reproduce
`inspect.getsource`-style assertions.

## 4. Why layer 7 need not change, and where it would break today

The study layer's outward product is a JSON object of named values and metrics, not fields:
`emfit/cli.py:22-27` defines `--json` as printing exactly one object with `study`, `values`, `metrics`,
`figures`, `attachments`; the dump site is `:197-201`; `board --json` at `:398-434` is the same shape with
millimetre conventions stated at `:364-369`. If §2 holds, that surface never touches a field array, so a
core swap cannot reach it. That is the whole argument for leaving layer 7 alone, and it is an argument
from the tree rather than from taste.

What would break is not layer 7's output but its plumbing. The drivers below are what actually exists.

Tracked:

| Driver | Path | Breakage |
|---|---|---|
| PEC-box audit | `tools/host/c1-audit/c1_audit.py` | Its own root discovery (`_find_repo` at `:123-137`, env var at `:141-142`, sys.path insert `:157-158`), and a `SystemExit` text that prescribes a specific shell wrapper (`:144-156`). Imports the 2D core directly at `:160-162`. |
| Box variant | `tools/host/c1-audit/pecbox_variant.py` | A second, independent root walk at `:118-146`, whose comment at `:120` says "same fallback rule as run.sh: walk up until a directory holding emfit/" — the rule is duplicated, not shared. Varies the core by monkeypatch (`:33-44`). Hard-codes the anchor constants at `:97-102`. |
| Gate harness | `tools/gates_101_20.py` | `WORKSPACE = "/workspace"` at `:58`; a hard-coded capture path at `:64-66`; plane keys as literals at `:69`; imports extraction at `:62`; quotes a cached wall time `wall_s = 4210.484 s = 70.2 min` at `:229-237`; own beta estimator at `:427` with a self-declared estimator-mismatch warning at `:446-461`. |
| Cross-check | `tools/corr_ez_101_20.py` | Paths and caches as literals at `:63-71`; its own `sha256` at `:110-115`; a fixed npz key list at `:269-311` including `int(d["col"])` at `:310-311`, i.e. the eigenvector column index is baked into the cache format. |
| Destagger ratio | `tools/destagger_ratio_101_20.py` | sys.path insert and direct `import emfit.mode2d as m2` at `:67-68`; the same three literal caches at `:70-76`; an anchor literal at `:78`; its own `sha256` at `:90-95`; a re-hash of inputs at `:348-350`. |
| Study layer | `emfit/studies.py` | Imports core internals at `:49-62` (`FITStepper` `:54`, `Grid` `:55`, `CellComplex` `:59`, `PLANE_CONVENTION` `:60`, ports `:62-67`); keeps study constants that drivers must mirror (`:1175`, `:1179`); entry point at `:3490`. |

Untracked. `.scratch/` is gitignored (`.gitignore:34`), so none of the following is in version control
and none of it can be migrated by a commit:

| Driver | Path | Breakage |
|---|---|---|
| Tolerance driver | `.scratch/tol/tol_driver.py` | Declares itself byte-identical to `.scratch/gate/gate_driver.py` except the log tag, the npz path and one diagnostics line (`:1-29`). `sys.path.insert(0, "/workspace")` at `:41` with five direct `emfit` imports at `:42-46`; the core monkeypatch and hash preamble at `:48-96`; a board path literal at `:99`; the whole comparability constant block at `:101-108`; calls private study internals `S._bin_metrics`, `S._dump_bins`, `S._bin_row` at `:297-301`, `:304`. |
| C3 driver | `.scratch/c3_driver.py` | Lines 1-35 are byte-identical to `.scratch/lever/run_real.py:1-35`; root at `:30`, imports `:31-35`, constants `:41-48`, reads study return-object attributes `cw.geometry["f"]`, `cw.station_x`, `cw.v_stations`, `cw.v_port`, `cw.i_ground_full`, `cw.i_ground_truncated` at `:161-181`, private metrics at `:178`, `:182`, json dump at `:241-242`. |
| Real-path lever | `.scratch/lever/run_real.py` | Root and imports at `:30-35`; proves the lever lives inside `emfit/` by hashing `emfit/operators.py` and `emfit/evolve.py` at `:37-45`; asserts on `CellComplex.curl_dual` via `inspect.getsource` at `:50-53`. |

A further ~90 one-off scripts exist under `.scratch/` (`.scratch/c3_driver.py`, `.scratch/lever/run_real.py`,
`.scratch/gate/gate_driver.py`, `.scratch/sweep_wall_driver.py`, `.scratch/s0_driver.py`,
`.scratch/s1_driver.py`, `.scratch/study_run.py`, `.scratch/mp_study.py`, `.scratch/m2/board_run_cw.py`,
`.scratch/tol/tol_driver_armc.py` among them). They are named here from a directory listing only; this
document makes no line-level claim about the ones not in the table above.

**Decision:** four concerns consolidate into one place each, and the consolidation is a prerequisite for
the swap, not a follow-up to it.

1. **Root discovery.** Today it is reimplemented at `tools/host/c1-audit/c1_audit.py:123-137`,
   `tools/host/c1-audit/pecbox_variant.py:118-146` (whose own comment at `:120` admits it copies
   `run.sh`), and hard-coded as `/workspace` in `.scratch/tol/tol_driver.py:41`, `.scratch/c3_driver.py:30`,
   `.scratch/lever/run_real.py:30` and `tools/gates_101_20.py:58`. One function, one behaviour.
2. **Cache keying.** Today it is literal strings — `("31x17", ...)`, `("41x22", ...)` at
   `tools/corr_ez_101_20.py:63-71` and `:70-76` of the destagger script — plus a npz key list that includes
   an eigenvector column index (`tools/corr_ez_101_20.py:310-311`). The key must be a hash of the contract
   inputs plus the discretisation summary, so that a swapped core cannot accidentally read a cache
   produced by a different one.
3. **Observables, probes and the time step.** Today these are a constant block per driver
   (`.scratch/tol/tol_driver.py:101-108`, `.scratch/c3_driver.py:41-48`) that must agree with study
   constants (`emfit/studies.py:1179`). Note the duplication is visible in a single expression: the driver
   writes `N_STATIONS=9` and also reads `int(S.MS_N_STATIONS)` (`:101-108` against `emfit/studies.py:1179`)
   — two sources for one number. They must become one declaration.
4. **Core access and verification.** Today there are three separate access idioms — direct import of
   internals (`emfit/studies.py:54`), in-memory monkeypatching
   (`tools/host/c1-audit/pecbox_variant.py:33-44`, `.scratch/tol/tol_driver.py:48-96`), and source
   inspection (`.scratch/lever/run_real.py:50-53`) — and three independent `sha256` helpers
   (`tools/corr_ez_101_20.py:110-115`, `tools/destagger_ratio_101_20.py:90-95`,
   `.scratch/tol/tol_driver.py:52-56`). One access path (the contract) and one verification path.

The source-split is not incidental to this consolidation. Once the core owns its excitation waveform —
`ricker` and `RickerSource` sit inside the core module (`emfit/evolve.py:58`, `:272`) — while a lumped port
that also injects current sits in extraction (`emfit/ports.py:180`, with `z0` defaulting to 50.0 at `:201`),
there are two injection mechanisms for one physical act, and which one a run used is recorded nowhere. That
is the same class of defect as the missing core sub-object in §3.

## 5. A minimum viable swap test

**Decision:** the swap gate is one existing anchor, computed through two cores, compared as a dimensionless
ratio at the anchor's own tolerance.

The anchor is the PEC-box curling mode. It is the one the tree calls load-bearing: `emfit/mode2d.py:1017-1022`
states that anchors (i) and (ii) validate the plumbing only and that the load-bearing anchor is a curling
mode where `q(e_t) != 0` and a missing `k_q` shows up as `beta^2/k0^2 = 1.0` instead of `0.4383`.
`decisions.md:7666-7668` records the executable form and its result: a 10 GHz, 20 x 7.6 mm vacuum PEC box,
`beta^2/k0^2 = 0.438322827` against a predicted `0.438278`, `rel_delta` 1.022e-4, PASS at tolerance 0.02,
and explicitly "a *formulation* validation, not a *problem* validation".

Measured value: `rel_delta` = 1.022e-4 on `beta^2/k0^2` = 0.438322827 against 0.438278
(`decisions.md:7666-7668`; the code is `_self_test_anchor()` at
`tools/host/c1-audit/pecbox_variant.py:561-620`, which builds `np.linspace(0,W_BOX,31)` by
`np.linspace(0,H_BOX,17)`, calls `m2.structured_mesh`, prints `rel_delta` at `:618` and
`SELF_TEST_ANCHOR = PASS/FAIL` at `:619`, wired at `:624`; constants `C0`, `K0_REF`, `W_BOX=0.020`,
`H_BOX=0.0076`, `F_SELF_TEST=10.0e9`, `SELF_TEST_BETA_TOL=0.02` at `:97-102`).

The two cores are the ones that already exist. Core A is the 2D eigenproblem member
(`emfit/mode2d.py:795`, `:935`), which is what the anchor runs through today. Core B is the 3D
time-domain member (`emfit/evolve.py:83`, `:186`, `:304`) run on the same box, with the guide wavenumber
recovered from station phase by the estimator already in the tree,
`_beta_from_phase_slope` (`tools/gates_101_20.py:427`, returning
`abs(float(np.polyfit(xx, phi, 1)[0]))` at `:462`). Core B does not need a new extraction path; it needs
the existing one pointed at a PEC box.

Comparability is defined as follows.

Identical inputs. Same physical box and frequency: `W_BOX=0.020`, `H_BOX=0.0076`, `F_SELF_TEST=10.0e9`,
vacuum, PEC on all walls (`tools/host/c1-audit/pecbox_variant.py:97-102`).

Matched discretisation. Same transverse node placement, 31 along x and 17 along y over the same physical
extent (`:561-620`). Core B's step must come from `cfl_dt` on a grid of the same cell widths
(`emfit/evolve.py:68-79`), and the value used must be reported rather than assumed — that is item 2 of §3,
and it is the difference between a test and a coincidence.

Stated tolerance. `|rel_delta| <= 0.02`, reused verbatim from `SELF_TEST_BETA_TOL`
(`tools/host/c1-audit/pecbox_variant.py:97-102`). It is not tightened for this test. It is roughly 200x
the measured 1.022e-4 and about 5x the 0.3993 % inter-code floor in beta reported for the same box from
`docs/design/zfree_diagnosis.md` §7.2 item 3 (summarised at `decisions.md:7658`), which is the right
relationship: a swap gate looser than a code-to-code floor is not a gate, and one tighter than the anchor's
own tolerance would fail on the anchor's own noise.

Expected not to match, and why. Three things:

1. The eigenvector amplitude and normalisation. `emfit/mode2d.py:636` documents the normalisation as
   `e^T B e = 1` while `:1127-1130` divides by the plain Euclidean 2-norm; that discrepancy is recorded as
   **OPEN** at `decisions.md:7008` and this document asserts nothing about it in either direction.
   Comparability therefore rests on the ratio `beta^2/k0^2`, which is the anchor's own headline form, and
   any comparison that depends on field scale is out of scope by construction.
2. Field arrays, bitwise. Determinism across machine, thread count and BLAS is not supported by anything
   in the repo (`decisions.md:7065`), so array equality between two cores is not an available criterion.
3. Provenance key sets. A 2D eigenproblem solve and a 3D time-domain solve do not describe themselves with
   the same terms; that is the defect at `decisions.md:7091` and the reason for the open solver-specific
   object in §2.

Wall time is reported but never compared. The tree's own cost figure, `wall_s = 4210.484 s = 70.2 min`
quoted at `tools/gates_101_20.py:229-237`, is a cost of the current core on the current grid; a faster core
is expected to differ by orders of magnitude, so a wall-time comparison would fail the test precisely when
the test succeeded.

Limit of this test, stated rather than hidden: it exercises the field-unknown contract and the provenance
core, and it does not exercise S-parameters. The job's `tolerance` (`decisions.md:7032`) is an S-parameter
tolerance and is not the right instrument here. A second gate at observable level requires two cores that
both emit the same observable, which per §2 row 3 means both must sit behind the same extraction layer —
that is a larger change than the swap and is not part of the minimum.

## Open rulings

Principal-only. Nothing below is decided by this document.

- **Core-level sub-object vs separate document pair.** §3 puts a core sub-object inside the job and the
  result, which **extends §101.19** and adds fields that section does not have. The alternative is a
  separate `emfit.core.v1` document pair the job references by path. Cost of the sub-object: two documents
  gain a field whose absence is silently tolerated under the unknown-field rule (`decisions.md:7063`), so a
  malformed core block may pass conformance. Cost of the separate pair: one more schema to version and a
  cross-document reference to keep valid. Recommend the sub-object; the cost is named above.
- **Whether the three §101.19(i) repairs land here or in the interface section.** This document adopts all
  three — per-observable tolerance (`decisions.md:7089`), solver-agnostic provenance (`:7091`), parametric
  geometry (`:7093`) — because a core contract cannot be written without them. That adoption is an
  editorial act on §101.19 if the repairs are meant to be made there instead.
- **When the study layer stops importing the core.** §4 treats the direct imports at
  `emfit/studies.py:49-62` as the swap blocker, but §101.19(h) sequences the interface as stable only after
  M3c once the §101.18 anchor gate result is in (`decisions.md:7083`). Whether the import is cut before or
  after that point is a scheduling decision, not a design one.
- **What happens to the unversioned drivers.** `.scratch/` is gitignored (`.gitignore:34`), so the ~90
  scripts there, including the three named drivers, cannot be migrated by a commit and are invisible to
  review. Whether they are promoted into `tools/host/` or abandoned determines whether the consolidation in
  §4 is checkable.
- **The `mode2d` normalisation defect** is open (`decisions.md:7008`) and is deliberately left unresolved
  here. §5 is written so that the swap gate does not depend on it.
