# `z_free` shape — why the extracted longitudinal field has no node where the reference has one

Design note. **No implementation, no change to `emfit/` or `tools/`, no run.** Every number below is either a
byte-exact quote from source, a number already banked in an artefact, or arithmetic on those numbers. The single
measurement this note names is *specified*, not executed; nothing in this note was produced by running anything.
Companion to `docs/design/zfree_diagnosis.md` (which ranked the candidates); this note does not re-rank them, it
asks a narrower question and prices one measurement that answers it.

---

## 1. The question, and a premise check that has to come first

**The question as briefed.** Why does the extracted longitudinal field have a *node* at the strip centre instead
of a smooth profile — i.e. why is its across-strip sign structure wrong?

**Premise check — the record says it the other way round.** Two banked artefacts, both already read, put the node
on the *reference* side and the smooth profile on the *extracted* side:

* `.scratch/logs/corr_ez_followup.txt:31-34`
  ```
  analytic e_z sign under the strip: 496 neg / 1860 pos of 2356
  analytic e_z sign OUTSIDE the strip: 10046 neg / 2874 pos
  ^ the reference E_z has BOTH signs in one column, which is why an |e_z| reconstruction has a ceiling far below 1
  ```
* `.scratch/logs/corr_ez_followup.txt:39-40`
  ```
  z_free (free nodes)   mean = +9.531420107e-03   rms = 1.210776766e-02   min = +0.000000e+00   max = +3.951804e-02
  z_free top-row mean   = +7.548951776e-03   fraction of free nodes with z_free < 0 = 0.0000
  ```

and `decisions.md:7306` states it as a settled fact ("`z_free` is ***single-signed*** on every mesh: 0 of 483
negative entries at 31x17, and 483 of 483 negative at 41x22"), with `decisions.md:7310` adding that the
reconstruction "is **single-signed** and does *not* decay to the top wall — top-row mean `7.5e-3` against a mean of
`9.5e-3` — which violates `integral(e_z dz) = -(phi(H) - phi(0)) = 0` outside the strip."

So, on the record so far: **the reference carries the node; the extraction is the smooth one.** The brief's
phrasing inverts the two, and it must not be quietly re-worded in either direction, because the two readings are
not the same investigation. What survives the inversion, unchanged, is the real question:

> The across-strip **sign structure** of the extracted `Φ` is wrong. The reference has a sign change inside the
> strip window and the opposite sign outside it; the extraction has one sign everywhere. **Where** does the
> extraction's profile differ from the reference's, and **which layer** produced that?

**Why a node is the right thing to look for at all.** For this 2-D cross-section `∂_x ≈ 0`, so `∇·E = 0` with
`∂_z → -iβ` gives `E_z ∝ ∂_y E_y`. `E_y` is even about the strip centre with maxima at the two strip edges and a
minimum at the centre; therefore `E_z` vanishes where `∂_y E_y` vanishes — at the strip centre — and has opposite
signs on the two halves. **A node at the strip centre is the physically required structure**, not an artefact. The
number to explain is the extraction's *absence* of it, and `decisions.md:7310`'s integral identity is the same
statement in one line: outside the strip `φ(H) = φ(0) = 0`, so `∫ e_z dz = 0` must hold column by column, and a
single-signed `e_z` cannot satisfy it.

**Geometry, so the words have rows.** `CELL = 1e-4`, `ny = 200`, `nz = 76`, `H = 0.0076`, `h = 0.0016`
(`.scratch/logs/corr_ez_followup.txt:15`), strip `[0.0085, 0.0115]` m ⇒ on the `(201, 76)` plane arrays of
`A_ez`/`e_z`, **rows = axis 0 = y**, **columns = axis 1 = z**; the strip edges are **rows 85 and 115**, the strip
centre is **row 100**, and the substrate/air interface is at columns 15-16 with the top wall at columns 74-75
(`docs/design/zfree_diagnosis.md:1206-1220`).

---

## 2. What is already measured (and therefore not open)

Each line is quoted with the artefact it comes from. `A_ez` is the analytic reference field; `e_z` is the
extracted one after `e_z = -e_z_mag` (`tools/host/c1-audit/c1_audit.py:493`, `tools/host/mode_plot/mode_plot.py:367`,
both citing `s10118_basis.py:369`); `c` is `assemble_mixed`'s edge×node block.

| # | Fact | Value | Provenance |
|---|---|---|---|
| M1 | Shape defect is real and converged-wrong, on two independent meshes | `corr_e_z` = `+0.119160432391342` (31x17), `+0.147291446944630` (41x22); the legal-operator baseline is `0.119317007` (41x22) vs `0.117276695` (31x17) | `zfree_diagnosis.md:1098-1112`; `corr_ez_followup.txt:130`, `:182` |
| M2 | The transverse leg is *not* broken — the defect is longitudinal | `corr_e_y` = `+0.920770784811142` (31x17), `+0.912343044811209` (41x22); `1-\|corr\|` = `0.079`/`0.088` against `0.881`/`0.853` | `zfree_diagnosis.md:1098-1112`, `:1306-1322` |
| M3 | β and ε_eff barely move between those meshes, so this is not resolution | ε_eff `3.6295122080769704` → `3.606094999644309` (−0.645 %); β `312.782765` → `311.772112` (+0.324 %) | `zfree_diagnosis.md:1115-1116` |
| M4 | The operator's *forward* application to the exact analytic potential is the ceiling, and it is single-signed | `corr(c@φ_analytic, A_ez)` = `-0.772595940918107` (41x22), `0.770566870` (31x17); per-column oracle `201 of 201 columns flipped` | `corr_ez_followup.txt:177-179`; `zfree_diagnosis.md:221` |
| M5 | The ceiling is **not** 1.0 and cannot be, by construction | "`c@phi` is a mass-weighted area integral, not the edge integral, so 1.0 was never available to TE either" | `corr_ez_followup.txt:173-176` |
| M6 | The analytic derivative control *is* 1.0, so the lattice bookkeeping is not the suspect | `corr(-d(phi_analytic)/dz, same map)` = `-0.811883637859104`; `corr(analytic e_z, -d(analytic phi)/dz)` = `1.000000000000000` | `corr_ez_followup.txt:180`, `:27-30` |
| M7 | The extraction is single-signed; the reference is not | `fraction of free nodes with z_free < 0 = 0.0000`; reference `496 neg / 1860 pos` under the strip, `10046 neg / 2874 pos` outside | `corr_ez_followup.txt:31-32`, `:40`; `decisions.md:7306`, `:7310` |
| M8 | **The extraction's sign *relative to the reference* reverses at the strip boundary; the control's does not** | baseline: `corr(.,A_ez)` under strip `-0.199469783`, outside `+0.384180074`; legal operator TE: `-0.260462501` / `+0.334639628`; **control `c@φ`: `-0.878900532` / `-0.911779324`** | `corr_ez_followup.txt:155-157`, `:185-186` |
| M9 | Sign is not the cause: a global sign moves nothing | restoring the sign changes `corr_e_z` by exactly `0.000000000`; a per-column oracle buys only `0.161983870`/`0.199096` from `0.119`/`0.147` | `decisions.md:7306`, `:7308`; `corr_ez_followup.txt:138`, `:171` |
| M10 | The reconstruction equals the library's own field to machine precision, so this is not a capture bug | max rel diff `0.000e+00` (31x17), `8.484e-16` (41x22) | `zfree_diagnosis.md:213` (S8) |

**M8 is the most specific fact in the file, and it is the one the brief's question is really about.** Applied to the
*analytic* potential, the same operator keeps one sign in both regions (`-0.879` under the strip, `-0.912`
outside) — exactly the `201/201` uniform flip of M4. Applied to the *solver's* `Φ`, it reverses (`-0.260` /
`+0.335`). A field whose sign relative to the reference flips when you cross the strip edge is a field whose
across-strip structure is wrong in the same way a missing node is wrong: it has *one* lobe where the reference has
two. M8 is a **two-region** census; nothing in the record resolves the profile *inside* the strip window.

---

## 3. Five hypotheses, numbered by rank

`C1`/`C2`/`C3` are `zfree_diagnosis.md`'s candidates (`:305`, `:411`, `:441`), summarised here in the form the
across-strip question needs. Two are new in this note: `H3` (the longitudinal solve is fed the wrong right-hand
side) and `H5` (the field is produced by *inverting*, not by differentiating). Neither is a re-ranking of the
other three, and the numbering is by rank, not by authorship: `H3` enters at rank 3 because it predicts the same
bulk-wide census signature as `H5` while being the cheaper of the two to disprove, which pushes `C3` down to `H4`
(still demoted, still bounded at <1 %); `H5` is carried last because it is the only one that is a statement about
the *map* rather than about a term inside it. A reader of an earlier draft should re-read the labels: old `H3` is
now `H4`, old `H4` is now `H5`, `H2` has gained a half it did not have, and `H3` is new.

### H1 — the selector picked a non-fundamental candidate (`C1`, rank 1)

* **Asserts.** `k* = argmax{ β² : finite, > 0, residual < 1e-3 }` (`emfit/mode2d.py:1150`, `:1156-1160`, `:1167`)
  aims, by construction, at the far (dielectric-limit) end of a guided band whose ordering carries no mode
  information. The exported vector is then not the quasi-TEM mode, though its transverse part can be close to it.
* **Lives in.** `emfit/mode2d.py:1150-1167`; the driver's *independent* re-pick by max `E_strip_t`
  (`s10118_basis.py:196-208`), which is why both identifications are banked side by side.
* **Predicts for the across-strip profile.** A *different but well-formed* profile: `n_sc` (sign changes along y
  through rows 85-115) ≠ 1, and `n_sc` **varies with the z-column** (a mode, not a smooth response), while
  `corr_e_y` stays ≈ 0.92.
* **Would refute it.** `n_sc == 0` in every column of the extraction (`Φ` is a smooth single-lobe response, not a
  mode) — no candidate with a near-fundamental transverse part can be node-free in `y` and still be a mode of this
  pencil. Also refuted by any column whose three-sign tuple is `(s, s, s)` with `s` fixed, uniformly in z.

### H2 — boundary attribution: interface ε, graded cell size, and the two boundaries (`C2`, rank 2)

**The walls half of this hypothesis is already dead, by numbers in the record.** A wall-set change is a *level*
term: the two `corr_e_z` values that make it are printed at `mode_plot.log:20` (`banked=+0.119160432391342`, PMC)
and `:26` (`banked=+0.147291446944630`, PEC); their difference `0.147291446944630 - 0.119160432391342` =
`0.028131014553288` is written out at `c2b_preregistration.md:33` as 23.6 % relative and `179.7`, i.e. `~180x`, the
mesh floor `F = 1.5657e-4` (`c2b_preregistration.md:29`), which is the noise level behind the `2F` = `3.1315e-4`
detection criterion at `:44`. It is also *fixed* in everything this note
measures — §4's census runs on banked arrays from one wall set — and it leaves the transverse field intact:
`corr_e_y` is `0.920770784811142` / `0.912343044811209` on the two panels (`zfree_diagnosis.md:1108`) while
`corr_e_z` is `0.119160432391342` / `0.147291446944630` (`:1109`). Those two panels also agree with each other
(`|corr| = 0.932705`, `:1119-1123`) and disagree with the reference *together*. The analytic array itself is not a
function of the walls at all: `mode_plot.log:29` records `max|A_ez(PMC) - A_ez(PEC)| = 0.000e+00`. Because the banked
`A_ez` is bit-identical under a wall-set change, the whole `0.028131` shift is a change in the *extraction*, and a
change of that size in the extraction cannot be what creates a nodal structure the extraction lacks — the
reference's node is wall-independent by construction, since it is cropped from a box that does not have these
walls. Walls shared by both panels cannot
be what separates them from the reference, so the wall term is bounded as a nuisance and is not a candidate cause
of the *shape*. What remains open inside `C2` is strip-local; it is listed below the `Lives in` bullet.

* **Asserts.** The ε_eff error is a boundary-layer artefact of (i) ε assigned by a *node* predicate at the metal
  plane and/or (ii) the local cell size at the interface not shrinking between the meshes. It must *also* explain a
  converged-wrong `Φ` shape, which is the stronger requirement (`zfree_diagnosis.md:420-424`), and it is plausible
  precisely because `Φ` is a *solve*, not a quadrature: "a locally wrong ε directly corrupts the operator producing
  it".
* **Lives in.** `emfit/mode2d.py:469-533`: `m_zz` is built from **nodal** ε (`c1_audit.py:386` passes
  `eps_r=eps_of`, a nodal array; `_per_triangle` at `mode2d.py:506` and `m_zz_loc = (area * eps_t / 12) ...` at
  `:518`) while `k_zz` is the plain stiffness (`:517`, `:527-529`) — i.e. the interface layer enters `m_zz` only,
  through `eps_t`, and enters `h_blk = k_zz − k0² m_zz` (`c1_audit.py:387`) through `k0²`.
* **The two halves still standing inside `C2`.** (i) *The strip surface is a Dirichlet boundary like the ground
  plane.* `BOUNDARIES = (ground, strip)` (`c1_audit.py:286`), with `def ground(p): return p[:, 1] == 0.0`
  (`:278-279`) and `def strip(p): return (p[:, 1] == HSUB) & (p[:, 0] >= Y0 - 1e-12) & (p[:, 0] <= Y1 + 1e-12)`
  (`:282-283`) — an error in how a metal surface enters the operator enters at the ground plane by the same
  mechanism, and the ground plane's profile is not the one that is wrong. That is what makes the strip-local
  version live and the global version not. (ii) *The source starts one cell off the strip while the field is
  pinned to zero on it.* `z_free` is solved on `free_n` and `e_z_node` is zero everywhere else (`:471-473`),
  while the right-hand side `c_f.T @ x` is assembled from edges touching those nodes — a one-sided divergence
  whose scale is the first off-strip cell, i.e. `h_edge`. That is exactly the quantity `C2b` varies, and it is
  the only reading of `C2` that survives the two paragraphs above it.
* **Predicts for the across-strip profile.** *Right* node structure in the bulk substrate, *wrong* confined to the
  bands: the substrate/air interface columns (15-16) and the strip-edge rows (85/115). A masked census should show
  `n_sc == 1` on interior columns and a broken tuple on the columns/rows adjacent to those bands; the defect's
  share of the total energy should concentrate there.
* **Would refute it.** A defect that is *uniform in z* — same wrong tuple on columns 17-73 as on 15-16 — is not a
  boundary-layer artefact of a graded `m_zz`; that kills H2 and promotes H5 (and leaves H3 standing).

### H3 — the longitudinal solve is fed the wrong right-hand side (new; implied by the code)

* **Asserts.** `Φ = h_blk⁻¹ Cᵀ x_t` is the divergence of the transverse field only if `x` *is* that field and
  `Cᵀ x` is that divergence with the right weight. Nothing in the record checks either. Three concrete ways the
  right-hand side can be the wrong object: (i) `x` is the eigenvector of a **Schur-reduced** problem, not of the
  original one — `h_blk = (k_zz − k0² m_zz)` on `free_n`, `c_f = c[free_e][:, free_n]`, `splu(h_blk)`
  (`c1_audit.py:387-389`), with `free_e ≠ free_n`; (ii) the same LU route runs with a real `beta` here
  (`:471`, `e_z_node[free_n] = beta * z_free`, `:473`) and with `1j * beta` in `emfit/mode2d.py:1175` — a
  difference the driver's own comment records as deliberate ("same LU route as `emfit/mode2d.py:1175` -- but
  SIGNED", `c1_audit.py:470`) and explains nowhere; (iii) `Cᵀ` carries the `1/μ_r` edge weight of `mode2d.py:477`
  and no factor of `beta`, so the map's *scale* is set by whatever normalisation `x` arrives in, not by the field.
* **What the correct source would be.** Physically the longitudinal field is driven by the charge on the strip's
  surface (and the polarisation charge on the substrate-air interface), not by the divergence of the transverse
  field sampled through the bulk. The contrast is concrete: the coded source `c_f.T @ x` is concentrated where the
  transverse field varies fastest — at the strip edges and around the source — and is spread over the volume by the
  hat weighting, whereas a surface-charge source is a thin sheet on the strip and on the interface. An
  inverse-Helmholtz response to a source with the wrong support is exactly a smooth, single-signed potential over
  the whole domain, which is what is measured. The two source objects agree only if the transverse field is already
  the true solution and the volume term already integrates the charge away — the identity the code assumes and
  nothing checks.
* **Lives in.** `tools/host/c1-audit/c1_audit.py:386-389`, `:470-473`. The same three lines are re-implemented
  twice — `tools/host/mode_plot/mode_plot.py:318-321`, `:331-334` and `tools/host/c1-audit/pecbox_variant.py:
  410-419` — so a wrong right-hand side would be wrong *identically* in all three, which is why no agreement
  between any two panels in the record can exclude it.
* **Predicts for the across-strip profile.** A smooth, single-lobed, single-signed `Φ` (`n_sc == 0` in every
  column), node present only in the reference — the same census signature as `H5`. It separates from `H5` on
  *where it is uniform*: a right-hand-side error has no reason to spare the bulk, so it predicts a defect flat in
  `z` across the whole width, whereas `H2` predicts one confined to the interface-adjacent columns and rows.
* **Would refute it.** A census that is right in the bulk and wrong only beside the interface bands. Also refuted
  without a solve: differencing the stored `x` along `y` and comparing with the stored `Φ` either lands within
  the mesh floor `1.5657e-4` (`c2b_preregistration.md:29`) — the right-hand side *is* the divergence, `H3` is
  dead — or it does not, and the discrepancy is the defect itself.
* **What would change, and what would not.** If H3 is right, the edit is one expression — the right-hand side — on
  `tools/host/c1-audit/c1_audit.py:471`, plus the three re-implementations of the same route
  (`emfit/mode2d.py:1175`, `tools/host/mode_plot/mode_plot.py:318-334`,
  `tools/host/c1-audit/pecbox_variant.py:410-419`). What would *not* change: the assembled `h_blk` including its
  screening term, the factorisation `lu = splu(h_blk)` at `c1_audit.py:387-389`, the mesh, the eigenproblem, the
  mode selector, and the entire analytic side. That is why H3 is the cheapest hypothesis in the note to falsify: it
  leaves every expensive object alone.

### H4 — the reference itself carries a few percent (`C3`, rank 4, demoted)

* **Asserts.** `microstrip_mode_profile` (the repo's own quasi-static FD solver, `n_sub = 16`) is the denominator
  of every percentage in the record and is not benchmarked in this tree; if it were a few percent low the target
  moves.
* **Lives in.** `.scratch/logs/s10118_basis.py:67-71` (the geometry literals), `:385`; `emfit/mode_profile.py:586-595`, which records the reference box as `n_clean = 200`, `n_air = 200` cells — 43.0 x 21.6 mm, 431 x 217 nodes at `h = 1.6 mm`, i.e. "deliberately **much wider than any FDTD plane**" — and then *cropped* into the 20 x 7.6 mm plane (`.scratch/logs/corr_ez_followup.txt:20-23`, `clipped [('e_y/h_z, y', 115, 115), ...]`, `phi cropped into the plane`). The reference therefore does **not** see the FDTD walls, while the solve is *closed* by them (`c1_audit.py:278-286`: exactly two boundaries, `ground` and `strip`) — a reference-side confound that lives in the outer rows and is one more reason the census window is the strip footprint (rows 85-115) and not the whole plane.
* **Predicts for the across-strip profile.** Nothing structural: the reference would have the right *shape* and the
  wrong *level*. It predicts the extraction and the reference differ in size, not in node count — and that the two
  extracted panels agree with each other while both disagree with the reference (they do: `|corr| = 0.932705`
  between panels, `zfree_diagnosis.md:1119-1123`).
* **Would refute it.** Already refuted as a *cause*: Hammerstad/Jensen gives `3.32546` against the reference
  `3.3500085193`, i.e. **+0.74 %** — inside the 1 % kill criterion, and far too small to produce a 4.09 %/8.35 %
  gap (`zfree_diagnosis.md:450-460`). Keep it only as a bounded nuisance (<1 %).

### H5 — the longitudinal field is produced by *inverting*, not by differentiating (new; implied by the code)

* **Asserts.** The physical `E_z` is a **derivative of the transverse field** (`E_z ∝ ∂_y E_y`, §1), a first-order,
  sign-changing, node-preserving map. The code does not apply that map. It solves
  ```
  e_z_node[free_n] = beta * z_free ,     z_free = lu.solve(c_f.T @ x)          # c1_audit.py:471-473
  e_z[free_n]      = 1j * beta * lu_h.solve(c_f.T @ x)                         # emfit/mode2d.py:1175
  ```
  i.e. `Φ = (k_zz − k0² m_zz)⁻¹ Cᵀ x_t` — the **inverse** of a stiffness-plus-mass Helmholtz operator applied to
  the *divergence* of the transverse field (`c[e,i] = ∫ (1/μ) W_e·∇φ_i`, `mode2d.py:477`, assembled as
  `c_local = (area/3)(∇φ_b − ∇φ_a)·∇φ_j` at `:493`, `:513-514`). An inverse Helmholtz application is a *smoothing*
  operator: it cannot manufacture a sign change that the source does not already carry, and its response to a
  source concentrated near the strip edges is a single-lobed, single-signed potential.
* **Lives in.** `tools/host/c1-audit/c1_audit.py:387-389`, `:471-473`; `emfit/mode2d.py:1174-1175`, `:469-533`.
* **Why it is none of the operator's three, and why it matters for reading them.** The `0.770567`/`0.772596` ceiling (M4)
  is measured by applying `c` **forwards** to `φ_analytic` — `corr(c@φ, A_ez)` — whereas the code's `Φ` is the
  **inverse** route `lu.solve(Cᵀ x)`. The two statements "the operator can reach 0.77" and "the field fails the
  operator" therefore compare a forward map against an inverse map, and the 15.2 %/15.8 % ratio does not bound the
  route the code actually takes. `zfree_diagnosis.md:215` (S10) reads that ratio as proof the *field* is at fault;
  H5 says the ratio is silent about the field, because the ceiling was never measured on the map in use.
  *(This note does not claim H5 is true — only that it is implied by the code and is discriminated by the
  measurement in §4, which every existing statistic averages away.)*
* **Predicts for the across-strip profile.** `n_sc == 0` in **every** z-column of the extraction (single-lobe,
  smooth), with the node appearing only in the reference; and the under-strip/outside sign reversal of M8 as its
  visible signature at the coarse scale.
* **Would refute it.** `n_sc == 1` on the extraction for a substantial set of columns — the inverse map *did*
  produce a node, so the shape defect is in `Cᵀ x` (H1), in `h_blk`'s coefficients (H2), or in what is fed to the
  solve as its right-hand side (H3) — not in the direction of the map. Also refuted if the extraction's node count
  matches the reference's column by column.

### 3.1 Mapping to `zfree_diagnosis.md`'s candidate list

`C1`/`C2`/`C3` stay filed where they were; this note adds two, and the table exists so that neither list drifts
from the other.

| this note | `zfree_diagnosis.md` | the claim, in one line | status here |
|---|---|---|---|
| H1 | `C1` (`:305-347`) | the selector picked a non-fundamental candidate | live, rank 1; refuted by `n_sc == 0` on every column |
| H2 | `C2` (`:411-439`) | ε attribution / graded cell size at the interface band | live, rank 2; walls half killed above; strip-local halves live |
| H3 | — (new) | the longitudinal solve's right-hand side is the wrong object | live, rank 3; same census signature as H5, cheaper refutation |
| H4 | `C3` (`:441-465`) | the reference carries a few percent | bounded nuisance, <1 % (`+0.74 %`); not a cause |
| H5 | — (new) | the field is produced by inverting, not differentiating | live, unranked; the operative reading in §5's first row |

The second table is not a second mapping of `C1`/`C2`/`C3`: it exists because item [3] of the brief was a request
that an outside reader be able to find *his own* three suggestions inside this note.

| the operator's suggestion | where it lands here | its status after the record |
|---|---|---|
| operator #1 — mode/parity selection is wrong (the wrong eigenvector is picked) | `H1` | still open, untested by any measurement in this note; the selector cited above is the mechanism, and the census (§4) is what would kill it |
| operator #2 — the boundary conditions are wrong | `H2` (and its walls half is dead on numbers, see the H2 paragraph) | the outer-wall half is excluded by the panel comparison; the strip-surface / interface half is open |
| operator #3 — the right-hand side of the longitudinal solve is wrong | `H3` | open, and it is the hypothesis the record's own sign evidence (M7 single-signed extraction, M8's two-region sign reversal) points at |

All three of his suggestions are inside this note and none was dropped; two of them — his #2 and his #3 — arrived
only in this revision.

---

## 4. The single cheapest measurement that discriminates them

**One measurement: a masked per-row sign census of the across-strip profile.**

For each of the four arrays already in memory — `A_ez` and `e_z` for both panels (`pmc`, `pec`), shapes `(201,76)`
— compute, per z-column `c` restricted to the interior columns `17..73` (excluding the interface band 15-16 and the
top wall 74-75):

```
n_sc(c)      = number of sign changes of f[85:116, c] as y increases      # 1 IS the physical answer
tuple(c)     = (sign f[85,c], sign f[100,c], sign f[115,c])              # strip edge / centre / strip edge
```

and reduce to three integers per array: **`#{c : n_sc == 0}`, `#{c : n_sc == 1}`, `#{c : n_sc >= 2}`**. Nothing
else: no correlation, no rms, no new solve, no re-assembly, no rebuild of the reference (`A_ez` is banked,
`c1_audit.py:551-570`, key `A_ez`).

* **Insertion point.** `tools/host/mode_plot/mode_plot.py:395`, immediately after the `fields` line, where
  `A_ez`/`e_z` and their validated shapes are in hand (`:351-367` already asserts the `(201,76)` lattice and the
  `(ZS,XS)` reshape); or `tools/host/c1-audit/c1_audit.py:496`, next to `cy = corr(...)` / `cz = corr(...)`.
* **Cost.** The existing `mode_plot.py` re-run — **no new eigensolve, no new assembly**; both spectra and both
  `A_ez` copies are already on disk (`.scratch/logs/corr_ez_followup.txt:13-14`, `c1_audit.py:551-570`). The
  re-run's cost is *estimated* at 1.6 s in `zfree_diagnosis.md:1225-1227` — **estimate, never measured; not run
  here.**
* **Why this one and not the cheaper-looking alternatives.** The whole-plane correlation (M1) is one inner product
  and structurally blind to *where* a profile disagrees; the under-strip/outside split M8 is the two-region
  ancestor of this census but cannot say whether the boundary is a node, a step, or noise; the per-column sign
  oracle (M9) is scale- and shape-blind by construction. The sign census is the only reduction on record that
  reads the object the question names, and it costs one row slice of an array that is already in memory.

### 4.1 The bar any follow-up must clear is already set, and it is not this census's bar

The census answers a *shape* question. The project's own detection bar answers the *level* question that every
follow-up has to clear, and it is already written down: two meshes give an interval and not a dispersion, so the
noise level is `F = 1.5657e-4` and the threshold is `2F` = `3.1315e-4` (0.26 % relative) —
`docs/design/c2b_preregistration.md:29` — and applied to this very statistic at `:44`:
`||corr_e_z|_patched - |corr_e_z|_baseline|` must exceed `3.1315e-4` absolute. Two consequences. The wall term
clears that bar by `180x` (`0.028131014553288`, `:44`), so it is measurable and therefore has to be held fixed
(this is what H2's walls paragraph does with it). And any later candidate fix — a redone census, a `C2b` step,
a re-extraction — that moves `|corr_e_z|` by less than `3.1315e-4` at fixed walls is not evidence for anything,
whatever the profile does. The census is cheap because it needs no new solve, not because it is exempt from the
bar; §5's readings are statements about shape and are read alongside these numbers, not instead of them.

### 4.2 What each route costs — and which of these numbers is a measurement

| what runs | what it touches | wall-clock ESTIMATE | eigensolve needed? | `emfit/` touched? |
|---|---|---|---|---|
| the sign census of §4 | `tools/host/mode_plot/mode_plot.py` (or `c1_audit.py`) only — it reads the banked `A_ez` and calls no solver | **ESTIMATE**, inherited: the `mode_plot.py` re-run, ~1.6 s (`zfree_diagnosis.md:1225-1227`); never measured, not run here | no | no |
| the surface-charge RHS prototype for H3 | `tools/host/c1-audit/c1_audit.py:471`, plus its three re-implementations — reuses `h_blk` and `lu`, swapping only the right-hand side | **ESTIMATE: no figure in the record** — the record states no time for it | no | no |
| `C2b` Step 0, per `docs/design/c2b_step0_plan.md` | the strip-edge refinement ladder — meshes only; `emfit/` is not edited | **ESTIMATE: no figure in the record** — that plan declines to publish a minutes figure until a per-solve elapsed time is read off `out/run.log` / `out/pecbox_run.log` (`c2b_step0_plan.md:59-68`) | one per step: 3 solves from the banked cache, 4 if the baseline is re-solved as the ladder's first row | no |

The ordering is the argument: the census and the one-expression prototype both cost **zero** solves, and the ladder
that tests one of the five hypotheses costs 3-4. Nothing above needs its last row executed in order to be read.

### The transposed census: changes along z at fixed y (Dispatch 21)

The census in 4.1 counts sign changes along **y** at fixed z-column. The transposed census - changes along **z** at fixed y-row - is the one that tests the interface node, and it had not been run. Measured on `A_ez`, structural threshold `1e-2 * max|v| = 1.578671918791774e-02`:

- Exactly one sign change per row on rows 84..116 (33 rows), always at column boundary 16 = z node 1.600 mm = h.
- Cols 0-15 negative, cols 16-75 positive. 30/30 strip rows.
- Away from the strip no crossing is detectable: the substrate-side value lies inside the zero band.
- Row tally (rows with 0 / 1 changes): 132 / 69 structural; 82 / 119 at 1e-12. Never state "no sign change" without naming the threshold.
- Zero-transparent convention throughout (a change counts only when both endpoints are outside the band). It reproduces the `A_ez` tallies 132 / 69 / 0 / 0, the 33 rows 84..116 at index 15, and the 30/30 strip rows.

Two counts of the same object are compatible and must not be reconciled: under `numpy.sign` all 57 interior columns reverse along y (the 4.1 count is correct), while under the structural threshold only 30 of the 57 reverse strictly, cols 17-46, the other 27 crossing inside the band. A count reports that a crossing exists; it cannot report whether the crossing is resolvable. An adjacent-row counter (`.scratch/m8_fieldlevel.py`) is blind to precisely that distinction and under-reports by construction - it is not wrong, and neither is 4.1.

### Status of this section's premise (Dispatch 21)

The title of this section asserts a defect: that the extracted longitudinal field has no node where the reference has one. Dispatch 21 then measured the thing that had never been measured - a same-component correlation - and found the 0.92 / 0.12 pair to be `A_ez` (vertical) paired against the longitudinal component, two orthogonal quantities; see `decisions.md`, Dispatch 21 section 1. Same-component, the two legs read 0.935 and 0.949, with orthogonal controls at 0.028 or below. The reference's node at z = h is a property of `A_ez` itself, and no measurement in this repo establishes that the longitudinal component should share it. The premise above is therefore contested and is awaiting the operator's ruling. It is not withdrawn here; sections 3 and 5 are left exactly as written, and the null-hypothesis ordering in section 4 stands either way.

---

## 5. What each outcome decides

| Census outcome (extraction, interior columns) | Reference + control, for contrast | Reading |
|---|---|---|
| `n_sc == 0` on **every** column, tuple `(s,s,s)` | reference `n_sc == 1` (node at row 100); control `n_sc == 1` (it inherits `φ`'s node) | **H1 refuted** (no mode is node-free across the strip), **H2 demoted** (a boundary layer cannot flatten the profile in the bulk), **H5 promoted** to the operative reading (with **H3** untouched, since a wrong right-hand side produces this same signature) |
| `n_sc == 1` on most columns but tuple `(s,t,s)` with the centre sign wrong / shifted off row 100 | reference node at row 100 | The map *can* make a node; the source `Cᵀ x` or `h_blk`'s coefficients are wrong ⇒ **H1 and H2 both live**; H5 loses its sharpest claim |
| `n_sc` **varies with z**: correct near the interface columns, wrong in the bulk (or vice versa) | reference uniform in z | **H2 confirmed** (boundary-layer, graded `m_zz`), and the defect gets a location (`mode2d.py:506-518`) |
| `n_sc == 1` with the *same* tuple on every column, i.e. structure right / node in the wrong place | reference node at row 100 | Neither H1 nor H5: a *translation* of the profile, which points at the coupling `Cᵀ` / edge orientation, not at either map |
| `A_ez`'s own census is not `n_sc == 1` | — | the row/column convention in §1 is wrong and **all of the above is void** — this is the built-in check that makes the census self-verifying |

Two things this table does deliberately **not** claim: that any of H1-H5 dies on arithmetic (only H4 is already
bounded, at <1 %), and that the census's outcome *identifies* a fix. It locates the defect in one of three
places — the source, the operator's coefficients, or the direction of the map — which is as much as one free
measurement can buy.

---

## 6. What this note does not establish

* **Nothing was run.** The census is specified, not executed; the "1.6 s" is an inherited estimate
  (`zfree_diagnosis.md:1225-1227`), not a measurement, and the container was not started for this note.
* **The premise inversion rests on two artefacts, not on a re-measurement.** `decisions.md:7306`/`:7310` and
  `corr_ez_followup.txt:31-40` were read and quoted; the brief's wording was not reconciled with them beyond this.
  If either artefact's `z_free` is a different object from the one in `c1_spectrum.npz`, the inversion is wrong and
  §1 must be re-read — the census in §4 would settle it either way.
* **The 31x17 counterpart of M8 was not read in this pass.** `corr_ez_followup.txt:155-157` and `:185-186` sit in
  the 41x22 section; no 31x17 under-strip/outside split is quoted here.
* **Two 0.119-class numbers are not reconciled.** `0.119317007` (followup baseline, 41x22,
  `corr_ez_followup.txt:182`) and `0.147291446944630` (the mode_plot PEC panel, `zfree_diagnosis.md:1098-1112`)
  are different measurement chains; this note quotes each against its own source and mixes neither.
* **H5 is a reading of the code, not a measurement.** It rests on two facts that *are* in the record — the ceiling
  is a forward application (M4, `corr_ez_followup.txt:173-179`) and the code is an inverse solve
  (`c1_audit.py:471`) — plus the textbook property that an inverse Helmholtz operator smooths. It is not tested.
* **Node *position* is assumed, not measured.** Rows 85/115 as strip edges and row 100 as centre follow from the
  banked geometry (`corr_ez_followup.txt:15`, `zfree_diagnosis.md:1206-1220`); the reference's node could sit at
  the strip *edge* rather than the centre (its under-strip counts, `496/1860`, do not localise it). That ambiguity
  is precisely why the census reports a three-sign tuple rather than a single bit.
* **The reference is a cropped larger-box solution, and the solve is not.** `emfit/mode_profile.py:586-595` puts the reference on a 43.0 x 21.6 mm box and `.scratch/logs/corr_ez_followup.txt:20-23` crops it to the 20 x 7.6 mm plane; the solve instead is closed by two PEC/PMC boundaries (`c1_audit.py:278-286`). At the lateral and top walls the two therefore disagree *by construction*, which is a live confound for every whole-plane statistic in M1 and for the "outside the strip" half of M8 — not for the census in §4, which never leaves the strip footprint. This note does not measure that confound.
* **It does not re-open anything `zfree_diagnosis.md` closed** — S1-S4 (the coupling sign and the Schur
  elimination), L4 (the geometry literals), S8 (the capture driver) — and it does not re-rank `C1`/`C2`.

---

## 7. Provenance of every number used

| Number | Source |
|---|---|
| `0.119160432391342` / `0.147291446944630` (`corr_e_z`), `0.920770784811142` / `0.912343044811209` (`corr_e_y`), `3.6295122080769704` / `3.606094999644309` (ε_eff), `312.782765` / `311.772112` (β), `-0.645 %`, `+0.324 %`, `0.932705` (cross-panel) | `docs/design/zfree_diagnosis.md:1098-1123` |
| `0.770566870` (31x17 ceiling), `0.117276695` (31x17 TE), `15.2 %`, `201/201`, `124/201`, `78/201`, `+0.573448286090104` | `docs/design/zfree_diagnosis.md:214-230` |
| `-0.772595940918107` (41x22 ceiling), `-0.769644553327422` (in-range), `201 of 201 columns flipped`, `-0.811883637859104` (derivative control) | `.scratch/logs/corr_ez_followup.txt:177-180` |
| `c@phi is a mass-weighted area integral, not the edge integral, so 1.0 was never available` | `.scratch/logs/corr_ez_followup.txt:173-176` |
| `496 neg / 1860 pos` (under strip), `10046 neg / 2874 pos` (outside), `corr(analytic e_z, -d(analytic phi)/dz) = 1.000000000000000` | `.scratch/logs/corr_ez_followup.txt:27-32` |
| `mean = +9.531420107e-03`, `rms = 1.210776766e-02`, `min = +0.000000e+00`, `max = +3.951804e-02`, `top-row mean = +7.548951776e-03`, `fraction < 0 = 0.0000` | `.scratch/logs/corr_ez_followup.txt:39-40` |
| `-0.199469783` / `+0.384180074` (baseline under/outside), `166 of 201` | `.scratch/logs/corr_ez_followup.txt:155-157` |
| `-0.260462501` / `+0.334639628` (TE), `-0.878900532` / `-0.911779324` (control) | `.scratch/logs/corr_ez_followup.txt:185-186` |
| `+0.161983870` (per-column oracle on TE), `0.199096` (5c) | `.scratch/logs/corr_ez_followup.txt:138`, `:171` |
| geometry dict (`ny 200`, `nz 76`, `cell 0.0001`, `strip [0.0085, 0.0115]`, `h 0.0016`, `H 0.0076`), npz paths | `.scratch/logs/corr_ez_followup.txt:13-15` |
| `0 of 483 negative` (31x17), `483 of 483` (41x22), `0.000000000` sign-restoration, `0.119317007`, `0.119160432`, top-row `7.5e-3` vs mean `9.5e-3`, ∫ identity | `decisions.md:7306`, `:7308`, `:7310`, `:7311` |
| `z_free = lu.solve(c_f.T @ x)`, `e_z_node[free_n] = beta * z_free`, `h_blk = k_zz − K0² m_zz`, `c_f = c[free_e][:, free_n]`, `splu`, `e_z = -e_z_mag`, banked `A_ez` | `tools/host/c1-audit/c1_audit.py:386-389`, `:471-473`, `:493`, `:551-570` |
| `c[e,i] = INT (1/mu_r) W_e . grad phi_i dA`, `c_local[s,j] = (area/3)(grad phi_b - grad phi_a).grad phi_j`, `m_zz_loc = (area/12)·_P1_MASS_PATTERN·eps`, `k_zz_loc = area·inv_mu·dot`, `_per_triangle` | `emfit/mode2d.py:469-533` |
| `k* = argmax{β² : finite, >0, residual < 1e-3}`; `chosen = int(np.flatnonzero(eligible)[np.argmax(beta_sq[eligible])])`; `e_z[free_n] = 1j*beta*lu_h.solve(c_f.T @ x)`; unit two-norm `:1127-1130` | `emfit/mode2d.py:1149-1175`, `:1127-1130` |
| `C1` / `C2` / `C3` statements and their kill criteria; Hammerstad/Jensen `3.32546` vs `3.3500085193` = `+0.74 %`; S8 `0.000e+00` / `8.484e-16`; `microstrip_mode_profile` as the shared denominator | `docs/design/zfree_diagnosis.md:305-347`, `:411-439`, `:441-465`, `:213` |
| `CORR_TOL = 1e-6`, `corr()` at `:206`, `fields` line at `:394-395`, shape guards `:351-367`, `_overlay` strip line `:436-440`, cross-panel reductions `:465-475` | `tools/host/mode_plot/mode_plot.py:191-206`, `:351-367`, `:394-395`, `:436-440`, `:465-475` |
| `F = 1.5657e-4` (noise level), `2F` = `3.1315e-4` (0.26 % relative, detection threshold), `corr_e_z` criterion `3.1315e-4` absolute, wall term `0.028131014553288` = ~180x | `docs/design/c2b_preregistration.md:29`, `:44` |
| Step 0 cost: 3 solves from the banked cache / 4 if the baseline is re-solved as the ladder's first row, one solve per step; cell counts for steps 1-3 `UNKNOWN`; no wall-clock figure published | `docs/design/c2b_step0_plan.md:59` (and the two bullets under it) |
| `BOUNDARIES = (ground, strip)`, `ground(p) = p[:, 1] == 0.0`, `strip(p) = (p[:, 1] == HSUB) & (Y0 - 1e-12 <= p[:, 0] <= Y1 + 1e-12)` | `tools/host/c1-audit/c1_audit.py:278-286` |
| the same LU route re-implemented three times (`lu.solve(c_f.T @ x)`, then `e_z_node[free_n] = beta * z_free`), on the Schur-reduced `h_blk`; driver comment "-- but SIGNED" | `tools/host/c1-audit/c1_audit.py:470-473`, `tools/host/mode_plot/mode_plot.py:318-334`, `tools/host/c1-audit/pecbox_variant.py:410-419` |
| `c[e, i] = INT (1/mu_r) W_e . grad phi_i dA` (edge x node), `e_z[free_n] = 1j * beta * lu_h.solve(c_f.T @ x)` | `emfit/mode2d.py:477`, `:1175` |

**No code was changed and nothing was run to produce this document.** It adds one file,
`docs/design/zfree_shape.md`, and specifies — but does not execute — one measurement.
