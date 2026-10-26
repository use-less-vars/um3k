# Modal port measurement pipeline — ownership map (design pass 1)

Evidence base: `emfit/` as it stands in the repo, `.scratch/logs/s10118_basis.py` (465 lines), `.scratch/logs/s10118_mesh_study.py` (422 lines), and the only copy of the modal module, `.scratch/wt-m3b-diag/emfit/modal.py` (935 lines). Every citation below was opened this turn. Nothing here is fixed, re-run, or proposed as architecture; the document assigns ownership and names the holes.

## 1. Reader and purpose

The headline figure is 8.6 %. The placed route's modal index on the 31x17 mesh is 336.675159 rad/m against the analytic reference 309.981864 rad/m (`.scratch/s10118_payload.txt:26`, `decisions.md:6844`), which is +8.61 %; the 41x22 point is worse at +8.87 % (337.464145). Three of the placed-route points in that set were one known bug — the node-ordering transpose, `(nz,nx)` read as `(nx,nz)` — repaired this block (§9). After the repair the same three meshes read 326.910765 / 327.094486 / 327.280996 rad/m (+5.46 / +5.52 / +5.58 %) and eps reads 3.964798 / 3.969256 / 3.973784 against 3.564800282 (+11.2 / +11.3 / +11.5 %). The repair is therefore worth about 3.1 of the 8.61 points and nothing more: what is left is unexplained, not explained by it.

The eigen route on the same three meshes sits at +0.90 / +0.64 / +0.48 % on beta and +1.82 / +1.28 / +0.96 % on eps. Two routes over the same physics differing from each other by 5 % is the reason this map exists. Treat it as an ownership register: for each number the pipeline prints, which line decides it, whether that line is in the repository, and what breaks if it is wrong. Nothing in it is a verdict on whether the pipeline should be trusted; that verdict needs the two tests in §8, which do not exist yet.

## 2. The chain, end to end

Seven stages. No stage has a second, independent implementation; three stages exist twice as copies, and one of the copies is where the defect repaired this block lived.

**1. Mesh and region assignment.** Consumes the geometry JSON (`s10118_basis.py:47-48`, parsed at `:67-77`, which yields `NY`, `NZ`, `CELL`, `HSUB`, `WSTRIP`, `EPS_R`, `J_CENTRE`, `N_SUB`) and produces a structured node lattice plus the PEC masks that set the degrees of freedom: `XS`/`ZS` from three segments each (`s10118_basis.py:87-88`), `m2.structured_mesh` (`emfit/mode2d.py:287`), `pec_edge_mask`/`pec_node_mask` (`s10118_basis.py:121-122`). Region assignment is a point predicate on height alone — `eps_of` returns `EPS_R` for `z <= HSUB` (`s10118_basis.py:98-99`) — with the strip and ground masks at `:107-115`. Owning file: `s10118_basis.py` for this run. Second implementation: none, but a duplicate — `s10118_mesh_study.py:118-139` rebuilds the same three-segment axes by largest-remainder rounding (`split`, `:118`) so the break lines stay put.

**2. Transverse mode profile / basis.** Consumes either the analytic quasi-static profile (`microstrip_mode_profile`, `s10118_basis.py:386`) or the mixed solver's eigenvector, and produces a `PlaneMode` (`modal.py:197`) carrying four blocks shaped `(nyn-1, nzn)` for `e_y`,`h_z` and `(nyn, nzn-1)` for `e_z`,`h_y` (`modal.py:289-296`). The promoted entry point that would do this from a mesh is `ModalPort.from_mode2d` (`emfit/modalport.py:194`) and it has no call sites (§5); every live basis is assembled at the call site: `s10118_basis.py:381` (mixed), `:387` (`M.plane_mode` on the analytic profile), `s10118_mesh_study.py:389` (mixed, 41x22). Owning file: the call sites. Second implementation: no, three copies of an assembly recipe.

**3. Vector eigensolve.** Consumes mesh, masks and `k0` (`emfit/mode2d.py:787`, computed from the capture's `plane_f` at `s10118_basis.py:117-118`) and produces `beta`, `beta_sq`, `e_t`, `e_z_solver`, `v_mode`, `i_mode`, `eta_eff`: `solve_modes_mixed` (`emfit/mode2d.py:935`) over `assemble_mixed` (`:469`), driven from `s10118_basis.py:160-245` and `s10118_mesh_study.py:184`. Mode selection is the column choice at `s10118_basis.py:181-217`. Owning file: `emfit/mode2d.py`. Second implementation: `solve_modes` (`emfit/mode2d.py:795`) is a second entry point over the same assembly, not an independent implementation, and the studies do not call it.

**4. Placed field synthesis.** Consumes the mode's `e_t` and `e_z_node` and produces a `PlaneMode` on the port lattice: `Mode2D.e_at` sampled at `s10118_basis.py:314-315`, e_z interpolated at `:357`, sign fixed at `:370`, one common scale at `:371-373`, `h_y`/`h_z` from `eta_eff` at `:374-375`, block assembly at `:381`. The whole block is duplicated in `s10118_mesh_study.py:355-391`. Owning file: the two scripts. Second implementation: no — the second file is a transcription, which is why a defect in one could survive in the other and why the transpose bug had to be fixed twice.

**5. Port phasor extraction.** Consumes the capture's plane blocks (`plane_Ey`, `plane_Ez`, `plane_Hy`, `plane_Hz`, `plane_station_x`, `plane_f`, `plane_dt`; file at `s10118_basis.py:47`, loaded at `:116-117`) and the `PlaneMode`, and produces modal voltage and current phasors per station: `modal_station_phasors` (`modal.py:372`), called at `s10118_basis.py:404`. The convention is not selectable — a capture whose convention is not `PLANE_CONVENTION` is refused rather than reinterpreted (`modal.py:414-417`) — and the magnetic blocks are de-staggered by default (`modal.py:373`). Owning file: `modal.py` (not in the repo, §5). Second implementation: none.

**6. S-parameter assembly.** Consumes `v`, `i` and `stations_m` and produces `s11`, `s21`, `passivity` and the `ModalLine` they were fitted from: `modal_sparams` (`modal.py:685`), `ModalSparams` (`modal.py:596`), called at `s10118_basis.py:407` inside a handler that records a refusal instead of failing (`:408-411`). Because `ModalSparams.beta` is `line.beta` (`modal.py:635-637`), the S-parameters and stage 7's beta come from one fit. Owning file: `modal.py`. Second implementation: none; `residual_gates` (`modal.py:912`) is a separate gate family, not a second S-parameter route.

**7. beta/eps inversion against analytic.** Consumes the station phasors and produces `beta` from a three-or-more-station fit and `eps_eff` algebraically from it: `fit_beta` at `modal.py:575`, `epsilon_eff = (beta * C0 / omega) ** 2` at `modal.py:578`. The comparison target is not a formula in the tree: it is the same pipeline run on the analytic profile (`s10118_basis.py:386-388`, `PANA`), measured by the same function (`:438`), and differenced into `OUT["deltas"]` (`:441-453`). Owning file: `modal.py` for the inversion, `s10118_basis.py` for the comparison. Second implementation: none — and no tolerance or assertion exists on this comparison anywhere (`:441-461`); the only pass/fail in the whole script is `mode_purity > 0.95` (`:454`).

## 3. Fact ownership table

| Fact | Declared owner (file:line) | Where it is really decided (file:line) | Duplicate / conflicting definition | Failure mode if wrong |
|---|---|---|---|---|
| Mesh element splits & node counts | `s10118_basis.py:87-88` — `[9,12,9]` over `(0,Y0),(Y0,Y1),(Y1,W)` and `[8,4,4]` over `(0,HSUB),(HSUB,0.0036),(0.0036,H)` | same two lines; node counts come from `GEOJSON` `ny`/`nz` (`:71`), not from the splits | `s10118_mesh_study.py:129-132` re-derives both by largest-remainder rounding (`split`, `:118`); the two agree only for the three meshes used | a moved break line puts the strip edge between nodes; `n_edges` then stops matching the cache (`:145`) and the DOF class changes with no warning, as the reported DOF 1927 → 3369 → 3595 show |
| 0.0036 m dielectric-region boundary | `s10118_basis.py:88`, again `s10118_mesh_study.py:132`, as bare literals | the literals; `eps_of` tests only `z <= HSUB` (`:98-99`), and `GEO` (`:74`) does not carry the value | two copies, no constant name, no test | the only material interface in the problem is at `HSUB`, which *is* named; the 0.0036 break is a mesh-refinement break over an air slab 4 z-cells thick, so nothing checks it and nothing would notice it moving except the cell count of a region with no material meaning |
| Transverse mode profile / basis | `ModalPort.from_mode2d` (`emfit/modalport.py:194`) | each call site: `s10118_basis.py:381`, `:387`, `s10118_mesh_study.py:389` | three assembly sites; the promoted one is dead code (`modalport.py:194`, its error string at `:217`) | the basis is set per run with no record beyond a free-text `report` string (`s10118_basis.py:384`); the docstring equivalence claim at `s10118_mesh_study.py:17-30` ("same expressions, same order") is the only link between the 31x17 and 41x22 bases |
| e_y amplitude scaling | `s10118_basis.py:315` — `e_y = E_t[:,:,0] * CELL` | `:212` — `x_t = x_t / np.linalg.norm(x_t)`, so e_y inherits unit L2 over free edges; then the common scale at `:372` | none | e_y's absolute scale is the solver's, not SI volts; measured rms 0.0024 |
| e_z amplitude scaling | `s10118_basis.py:225` — `e_z_node[free_n] = np.abs(beta * z_free)` | the same line; `z_free = lu.solve(c_f.T @ x_t)` at `:223` sets the scale, and the `beta` in it is the *solver's* beta (312.78 / 311.96 / 311.46), not the placed beta | none | e_z carries beta-times-solver-solution scale, measured rms ~4.0 — about 1667x the e_y rms; no downstream code knows the two are on different scales (§4) |
| Port plane location & station | the capture file, `s10118_basis.py:47` (`PLANES` npz); keys consumed at `:404-406` and `:117` | the npz; no code in `emfit/` computes, derives or validates `x_port` or `plane_station_x` | measured values `x_port = 0.0087`, stations `0.0104 .. 0.020`, `ref_plane = 0.0104` (`.scratch/s10118_result.txt:108`); the first station is not on the port plane | everything is measured 1.7 mm downstream of the port; the label at `s10118_basis.py:55-56` already records that the ruled plane sits outside the capture, and the 0.9687 flux ratio is therefore not the port ratio |
| Phasor extraction convention | `modal.py:373` — default `convention=PLANE_CONVENTION`, `destagger_h=True` | `modal.py:414-417` refuses any other value; `destagger` imported at `modal.py:88` | the capture's own convention is compared by value at `modal.py:410`, not by identity | a wrong convention rotates i against v by `exp(-j pi f dt)`; it surfaces as mode_purity and z0, never as an error |
| beta<->eps inversion | `modal.py:575` (`beta_fit = fit_beta(x, v)`) and `modal.py:578` (`epsilon_eff = (beta*C0/omega)**2`) | the same two lines; `ModalLine.beta` returns `beta_fit.beta` (`modal.py:506-509`) | none | eps is not measured, it is beta squared — one degree of freedom for two printed numbers (§6) |
| Analytic reference values | no owner in code | produced by `measure(PANA, ...)` at `s10118_basis.py:438` from the analytic profile of `:386-388`; the constants exist only in outputs (`.scratch/s10118_result.txt:15,20`; `decisions.md:6844-6845`) | none, because it is never a constant | the "analytic" beta is a fit on the *same capture* projected onto a different profile, so it is not independent of the thing it judges; an agreement claim against it is a consistency claim |
| Cache key / archive reuse | `s10118_basis.py:50` (`CACHE`) with the load at `:133-158` | the key is `n_edges` plus exact `xs`/`zs` array equality (`:145-149`); no `ny`/`nz` key exists in `_need` (`:137-139`) | the 41x22 archive is a different file (`s10118_mesh_study.py:71-72`) with the same key list (`:277-280`) | see §7: the 31x17 archive cannot be re-solved from the documented entry point |
| Tolerance settings | `modal.py:632` `passivity_tolerance = 1.0e-9`; `s10118_basis.py:454` `mode_purity > 0.95`; `s10118_mesh_study.py:54` `FREE_EDGE_GUARD = 2800` | those three lines and nowhere else | `plane_mode`'s defaults `nyn=201, nzn=77, k_strip=16` (`modal.py:125-127`) are never used — `s10118_basis.py:387-388` passes all three explicitly | there is no tolerance on beta or on eps: `deltas` (`:441-453`) is recorded and never tested, and the single existing gate (`:454`) passes on a quantity that is an artefact (§4) |
| v_mode / i_mode / z0_power | `s10118_basis.py:376-377` | the same lines: `v_mode = -sum(e_z[J_CENTRE, :N_SUB])`, `i_mode = 2.0 / v_mode`, hence `z0_power = v_mode/i_mode = v_mode**2/2` | none; `s10118_mesh_study.py:376-386` adds a zero guard that mirrors it | this is the only place in the pipeline where the e_z scale is multiplied by itself, so z0 reports a scale constant and nothing about the mode; before the guard existed the 51x19 run died here on `2.0 / v_mode` |

## 4. PRIMARY FINDING — relative amplitude of e_y and e_z is unowned

The ratio of the two electric blocks is not owned by any code path and is not checked by any test. It is set by two unrelated normalisations that happen to feed the same plane.

`e_y`'s scale comes from the transverse eigenvector: `x_t` is normalised to unit L2 over the free edges at `s10118_basis.py:212`, sampled at `:315` (`e_y = E_t[:,:,0] * CELL`), and its rms over the plane is 0.0024.

`e_z`'s scale comes from a different system: `e_z_node[free_n] = np.abs(beta * z_free)` at `s10118_basis.py:225`, where `z_free = lu.solve(c_f.T @ x_t)` (`:223`). That solve is driven by a unit-L2 `x_t`, but the result is a potential-like vector in its own units, and nothing normalises it. Its rms over the plane is ~4.0.

The only normalisation applied to the pair is one common scalar at `:371-373`, chosen so the discrete power is 1 W (`:364`, `:380`). A common scalar is the one transform that cannot change a ratio, so the ratio is exactly what the two independent normalisations left:

    sum(e_z**2) / sum(e_y**2) = 2.72e6 / 2.64e6 / 2.54e6   (31x17 / 41x22 / 51x19)

Consequences, stated plainly.

At the pipeline's own 1 W normalisation, 99.99996 % of the stored field energy sits in `e_z`; `e_y` contributes about 4e-7 of it. A "unit-power mode" here means "an `e_z` block of unit discrete power".

Every number that combines `v` and `i` combines the `e_z` scale with the `e_y` scale. That is `v_mode` (`:376`), `i_mode` (`:377`), `z0_power` (`= v_mode**2/2` by algebra), `mode_purity = |gamma_i + gamma_v|` (`modal.py:516-519`), `amplitude_mismatch` (`modal.py:356`), and `passivity` (`modal.py:632`). Those numbers measure the ratio of two normalisation constants, not a property of the field.

`mode_purity` 0.177850 / 0.185542 (pre-repair) and 0.206827 / 0.208738 / 0.208551 (post-repair) is therefore an artefact. It moved by ~0.03 between the two runs because the repair changed the sampled `e_z`; it did not become a measurement. The `mode_purity > 0.95` verdict at `s10118_basis.py:454` cannot pass for any field produced by this route, and its failure says nothing about the mode.

The same applies to the V/I ratio, to any power normalisation built on this plane, and to any mode-purity figure derived from it. They are not "biased" or "within tolerance of wrong" — they are dimensionless ratios of two unrelated unit choices.

The missing invariant is small and its absence is total: `grep -n norm s10118_basis.py` returns `:192` and `:212` only, both on the transverse vector; no line scales `e_z` against `e_y`; and the ratio is not in `DELTA_KEYS` (`:441-442`), is not in the result JSON's compared set, and appears in no assertion in either script.

The ratio does drift with the mesh — 2.72e6, 2.64e6, 2.54e6, about -3 % per refinement — which is the only monotone signal the mixed block offers, and it is not converged at 51x19.

## 5. Provenance hole — the modal module is not in the repository

`emfit/modal.py` does not exist. `ls emfit/modal.py` returns `No such file or directory`, and the package listing in `emfit/` has no `modal` entry: the modules that are there are `modalport.py`, `mode2d.py`, `mode_profile.py`, `plane_phasor.py`, `ports.py` and so on. The only copy of the module is `.scratch/wt-m3b-diag/emfit/modal.py` — 935 lines, 39846 bytes — inside a worktree that version control ignores (`.gitignore:34`, `.scratch/`).

The scripts reach it by appending a directory to the package search path at run time, before importing:

    s10118_basis.py:39   sys.path.insert(0, "/workspace")
    s10118_basis.py:42   emfit.__path__.append("/workspace/.scratch/wt-m3b-diag/emfit")
    s10118_basis.py:43   import emfit.modal as M

So `import emfit.modal` resolves to a file in a gitignored scratch tree, and every run re-resolves it. The measured pipeline is therefore larger than the repository by exactly the file that defines the measurement.

Verified anchors in that copy:

| Symbol | Line | What it decides |
|---|---|---|
| `class PlaneMode` | `modal.py:197` | the four field blocks, and their norms at `:232`, `:237`, `:242`, `:252` |
| `def plane_mode` | `modal.py:267` | placement of a profile onto the port lattice (defaults `nyn=201, nzn=77, k_strip=16` at `:125-127`) |
| `def modal_station_phasors` | `modal.py:372` | port phasor extraction and the projection convention |
| `def modal_line_quantities` | `modal.py:538` | beta fit, eps inversion, z0 |
| `class ModalSparams` | `modal.py:596` | `s11`, `s21`, `passivity`, `passive` |
| `def modal_sparams` | `modal.py:685` | assembly of the scattering pair |

Consequences, in order of how much they cost:

- The code that defines the measurement is invisible to version control. `git log` cannot say whether it changed between the run that produced `.scratch/s10118_result.txt` and any later run; a diff of the repository is not evidence about the pipeline's behaviour.
- A re-run cannot be shown to be the same code. The only copy lives in a scratch worktree whose own state is not tracked, so "same command, same result" is not checkable after the fact.
- The import mechanism hides it further: nothing in `emfit/__init__.py` or in the repo's package layout says that `emfit.modal` exists, and the failure mode if the scratch tree is removed is an `ImportError` at run time, not a missing module at review time.

Second half of the same hole: the promoted entry point for building a port mode from a mesh is dead. `ModalPort.from_mode2d` is defined at `emfit/modalport.py:194` and has zero call sites — a repo-wide search for the name returns only the definition (`:194`), its own error message (`:217`), and a docstring note in the scratch script (`s10118_basis.py:12`) that records the zero. The basis is therefore set ad hoc at each call site:

    s10118_basis.py:381        PMIX = M.PlaneMode(e_y=..., e_z=..., h_y=..., h_z=..., v_mode=...)
    s10118_basis.py:387        PANA = M.plane_mode(prof, nyn=NYN, nzn=NZN, k_strip=K_STRIP, ...)
    s10118_mesh_study.py:389   PMIX = M.PlaneMode(e_y=..., e_z=..., ...)   (41x22 transcription)

Three call sites, two of them transcriptions of each other, none of them the function that was written to own the job. That is why the ordering defect fixed this block had two homes (§9) and why the 31x17 and 41x22 bases are only linked by a docstring claim of equivalence (`s10118_mesh_study.py:17-30`).

## 6. The placed route has one degree of freedom, not two

`beta_placed` and `eps_placed` are not two measurements. They are one fitted number and its algebraic square.

The governing lines are `modal.py:575` and `modal.py:578`:

    modal.py:575   beta_fit = fit_beta(x, v)
    modal.py:576   beta = float(beta_fit.beta)
    modal.py:577   omega = 2.0 * np.pi * f0
    modal.py:578   epsilon_eff = (beta * C0 / omega) ** 2

`epsilon_eff` is computed from `beta` on the next line, and `ModalLine.beta` returns `beta_fit.beta` (`modal.py:506-509`). Nothing else contributes to `eps`. So the identity `beta == k0 * sqrt(eps)` holds by construction, not by agreement, and the six published pairs confirm it: the quotient `beta / sqrt(eps)` is 164.1794 rad/m for every one of them.

| Pair | beta | eps | beta / sqrt(eps) |
|---|---|---|---|
| placed 31x17, post-repair | 326.910765 | 3.964798 | 164.179409 |
| placed 41x22, post-repair | 327.094486 | 3.969256 | 164.179401 |
| placed 51x19, post-repair | 327.280996 | 3.973784 | 164.179398 |
| analytic | 309.981864 | 3.564800282 | 164.179407 |
| placed 31x17, pre-repair | 336.675159 | 4.205181853 | 164.179407 |
| placed 41x22, pre-repair | 337.464145 | 4.224914330 | 164.179407 |

The spread is 1.1e-7 relative, which is what six-decimal rounding of the inputs produces; the identity itself is exact at `modal.py:578`. The common quotient is `k0 = 164.1794 rad/m`, i.e. 7.8335 GHz in free space by `f0 = k0 c / 2 pi` — a value inferred from the identity in this pass, not read from the capture's `plane_f` (`s10118_basis.py:117`).

Direction of the dependency, corrected against the earlier record: the code derives eps from beta (`:578`), not beta from eps; `beta` is a three-or-more-station fit of the modal voltage (`:575`). The conclusion does not depend on which way round it is written — there is one fitted quantity and one definition, so the pair carries exactly one number of information.

What follows, and it matters for any gate:

- "beta agrees and eps agrees" is one check counted twice. A gate that reports both as separate passes halves its apparent error, and any averaged or combined error metric built from them is meaningless.
- The eps gap is arithmetically the square of the beta gap, so it is not independent evidence of anything. The post-repair placed numbers demonstrate it exactly: `1.0546**2 = 1.1122`, and the reported gaps are 5.46 % on beta against 11.2 % on eps; likewise `1.0552**2 = 1.1134` against 11.3 %, and `1.0558**2 = 1.1148` against 11.5 %. Quote the beta gap and be done.
- The same holds for the eigen route, which reports 0.90 / 0.64 / 0.48 % on beta and 1.82 / 1.28 / 0.96 % on eps — squares of each other within rounding.

The one thing this does *not* say: that the fit is wrong. `fit_beta` is a genuine measurement of the phasor series; what is missing is any second route to eps that does not pass through it. There is none in the tree — no capacitance, no charge, no energy-based eps inversion appears in either script or in `modal.py`.

## 7. The cache is dimensioned to one mesh

Verified in `.scratch/logs/s10118_basis.py`:

- The archive path is a single fixed constant, `CACHE = "/workspace/.scratch/s10118_mixed_mode.npz"` (`:50`). The script's whole entry point is the command string at `:51`; there is no argument parser in it, so no flag can select a different archive or force a fresh solve.
- The load is unconditional when the file exists (`:134`) and the validation keys carry no mesh description: `_need = ("beta", "eps_eff", "beta_sq", "E_strip_t", "k0", "col", "n_dof", "n_pec", "residual", "e_t", "e_z_node", "xs", "zs", "n_edges")` (`:137-139`). There is no `ny`, no `nz`, no code hash, no timestamp.
- What actually defends the archive is a content check: `n_edges` must equal the current mesh's (`:145`), `xs`/`zs` must be equal as arrays (`:146-148`), and the field blocks must have the current shapes (`:149`). On mismatch the cache is set to `None` and the script re-solves, saying so at `:156`.
- Consequence for changing resolution: editing `ny`/`nz` in the geometry JSON (`:71`, read at `:67-77`) makes the cache invalid, so the run *does* change resolution — it just pays a fresh solve and overwrites the archive on the way out (`:237-245`). The archive is dimensioned to one mesh in the sense that it cannot be *reused* for another; it is not keyed to one.
- Consequence in the other direction, and this is the sharp one: the archive's own resolution cannot be re-solved through the documented entry point. Because the load precedes the solve unconditionally, a fresh 31x17 solve requires deleting or moving `.scratch/s10118_mixed_mode.npz` first. `s10118_mesh_study.py` cannot do it either — it imports `s10118_basis` as a module (`:53`), inheriting the same load, and its own archive is a different file per resolution (`:71-72`, chosen from `--xs`/`--zs` at `:59-69`).

Inferred rather than verified in this pass:

- That no other script writes `s10118_mixed_mode.npz`. The tree was searched for the import and the path constant, not audited for writers, so a second producer would not have been found.
- That the archive's `n_edges` check is sufficient to distinguish the three meshes used. `n_edges` for 31x17, 41x22 and 51x19 are certainly distinct, but I did not read the values from the npz; the check is a single integer, so any two meshes with equal edge counts and equal axis arrays would be indistinguishable — a risk, not an observation.
- The runtime consequence for a re-capture (that regenerating the archive at 31x17 costs the ~111 s mixed solve recorded at `s10118_mesh_study.py:55`) is arithmetic on a recorded baseline, not a measurement made here.

## 8. What the gate must test

Two tests, and no others, until both pass. Both are cheap: neither needs a new solve if the existing captures are kept, and both are statements about the extraction and the placement, not about the physics. Neither exists in the tree today; the only assertion in either script is `mode_purity > 0.95` at `s10118_basis.py:454`, which reads an artefact (§4).

### 8(a) EXTRACTION CONSISTENCY

**Falsifies:** that `beta` is a property of the mode rather than of the station window the fit was given.

**Quantity measured:** `beta` from `modal_line_quantities` (`modal.py:538`) — which is `fit_beta(x, v).beta` (`:575`) — computed twice from one capture: once over all stations in `plane_station_x` (`s10118_basis.py:404-406`), and once with the nearest station dropped (`xs[1:]`, `v[1:]`, `i[1:]`). Report `|beta_a - beta_b| / beta_a`. Repeat for the mixed basis and the analytic basis, on all three meshes.

**Acceptance:** `|beta_a - beta_b| / beta_a <= 1.0e-3` (0.1 %), both bases, all three meshes.

**Why that tolerance:** the smallest gap under dispute is 0.476 % (eigen route, 51x19), so a 0.1 % consistency floor still leaves that gap visible; anything looser would let an extraction artefact masquerade as the effect being measured. On the other side, the fit is over roughly nine stations spanning `0.0104 .. 0.020` m, i.e. 3.14 rad of phase at `beta = 327` rad/m, and dropping one station shortens the span by ~11 %, so a fit that is genuinely single-mode should reproduce `beta` to well under 1e-3. The number is proposed, not derived; the operator should rule on it.

**What a failure would mean:** `beta_placed` (326.91) against the eigen route's `beta` (312.78) differ by 4.5 %. If this test fails, that difference is partly the window and cannot be read as a statement about the basis at all. Note that it does not test the difference itself — it tests whether the difference is stable enough to be talked about.

### 8(b) RELATIVE AMPLITUDE

**Falsifies:** that the two electric blocks on the port plane are on comparable scales.

**Quantity measured:** `R = sum(e_z**2) / sum(e_y**2)`, evaluated on the placed blocks after the common normalisation at `s10118_basis.py:371-373`. `R` is invariant under that common scale by construction, so it measures only the relative amplitude. Report `R` per mesh; the values on record are 2.72e6 / 2.64e6 / 2.54e6.

**Acceptance:** `R <= 1.0e-2` if `e_z` is the longitudinal component, or `0.1 <= R <= 10` if it is the vertical transverse component. Which branch applies is itself an open question and must be settled first — see the caveat below.

**Why those two bands:** both are derived from the quasi-static field of a microstrip cross-section, not from this code. For a quasi-TEM line the longitudinal component vanishes in the TEM limit and is `O(t/h)` for a finite-thickness conductor, so an upper bound of 10 % in energy (`R <= 1e-2`) is generous and still five orders of magnitude below what the pipeline produces. If on the other hand `e_z` is the vertical component of the cross-section field, then both blocks are transverse components of one quasi-static solution and their energy ratio must be of order one — a uniform strip-to-ground field gives `E_z >> E_y` away from the edges but the fringe field is not negligible, so a one-decade band on either side of unity is the honest width for a sampled rms on a lattice whose spacing is a fifth of the strip width. Any refinement of the band needs the analytic profile evaluated on the same lattice, which is a comparison of code, so it is not part of this test.

**What a failure would mean:** the current `R` fails both branches by five to eight orders of magnitude, so a run of this test today is a red result regardless of branch. That is the point: the test is designed to be unambiguous, and it distinguishes only one thing — whether the two blocks were ever put on a common scale.

**Caveat that must be resolved before the band is fixed:** the block the code fills is built from the scalar node solve (`e_z_node`, `s10118_basis.py:223-225`) and the script's comment calls it the longitudinal component (`:368-369`), but it is sampled at the vertical stagger — shape `(nyn, nzn-1)`, `modal.py:289-296` — and stored in the capture's `plane_Ez` slot, which is the vertical cross-section component. The name, the comment and the sampling location do not agree. Until they do, `R` can be bounded but not interpreted, and test 8(b) should be reported as a branch-conditional result rather than a pass.

## 9. What this block did NOT do

Fenced explicitly, because the numbers below are quoted out of runs that did other things:

- No normalisation fix was made. `e_z` is still on its own scale in both scripts (§4).
- No gate was run, and neither test in §8 exists in code.
- No re-capture was taken; the captures in `.scratch/` are the ones produced before this pass.
- No C5 and no wall work was done in this block.
- No edit was made to `emfit/eigen.py` — or to any file whose path starts with `emfit/`.

What this block did do outside this document: it repaired a node-ordering defect in the two scratch scripts — `.scratch/logs/s10118_basis.py` and `.scratch/logs/s10118_mesh_study.py`, not `.scratch/logs/mesh_study.py`, whose name the earlier brief used but which does not exist. The defect was that the structured mesh's node index is `j*nx + i` for coordinates `(XS[i], ZS[j])`, while the interpolation was reshaping as if the flat index ran `(nx, nz)`; the two agree only when `nx == nz`, which none of the three meshes satisfies. Each script now carries a coordinate-indexed guard on four probe nodes before any interpolation, and refuses to continue if it fails: `s10118_basis.py:325-354`, `s10118_mesh_study.py:325-355`. That repair is worth about 3.1 of the 8.61 points on the 31x17 placed route and is what removed the 51x19 `ZeroDivisionError` on `2.0 / v_mode` (`s10118_basis.py:377`), because the transposed `e_z` sum was cancelling to zero.

The repair does not explain the remainder. Post-repair, the placed route still sits 5.46 / 5.52 / 5.58 % above the analytic beta, and the eigen route still sits 0.90 / 0.64 / 0.48 % above it. Neither gap is attributed to anything by this block.

A re-run must reproduce these numbers, or state why not:

| Mesh | beta_placed | eps_placed | mode_purity | passivity |
|---|---|---|---|---|
| 31x17 | 326.910765 | 3.964798 | 0.206827 | 2.001381 |
| 41x22 | 327.094486 | 3.969256 | 0.208738 | 2.000680 |
| 51x19 | 327.280996 | 3.973784 | 0.208551 | 1.999854 |

`eps_placed` is not an independent check of these (§6), and `mode_purity` and `passivity` are artefacts of the unowned ratio (§4) — they are listed as fingerprints of the run, not as evidence.

## 10. Handover

- First change a future block should make: put the two electric blocks on one scale — normalise `e_z` against `e_y`, or normalise both to unit discrete power with a stated reference — and add test 8(b) in the same commit, so the change cannot be accepted without the number that shows it took effect.
- One file to promote out of scratch into the repository: `.scratch/wt-m3b-diag/emfit/modal.py`, as `emfit/modal.py`, with `s10118_basis.py:42` deleted so the import resolves through the package and the diff becomes reviewable.
- One test to write before any further convergence claim: 8(a), extraction consistency — because every convergence statement on record compares a `beta` whose stability against the station window has never been checked.
