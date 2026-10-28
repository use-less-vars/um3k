# The visual engine: slices and isosurfaces over the result contract

## Status

**New document, authored at Dispatch 42.** It is not a revision of anything, it replaces nothing and it supersedes nothing. No `docs/design/visual_engine_arch.md` existed before this pass, and there is no earlier visual-engine design anywhere in the tree to inherit line numbers from.

**Design proposal only.** No part of this is implemented. There is no viewer code, no artefact emitter, no geometry buffer and no renderer library anywhere in the package. No dependency is ratified, no licence is ratified, and no third-party renderer is named as the choice. The two questions that decide the shape of an implementation are section 8 (the byte budget against a vendored library) and section 11 (the collected rulings); both are **OPEN**.

**Reading discipline.** No code was executed to produce this document and no measurement was taken for it. Every statement about the repository is a reading of a named line range, cited as `file:line`. Every number is either quoted from a file with its line, or is arithmetic performed on numbers that are quoted, in which case it is labelled *derived* and the arithmetic is shown. A number that is neither is written as a hole. No file under `emfit/` was written in producing this document; the package was read only.

## 1. Purpose and scope

This document fixes what a visual layer over this solver may be, and what it may not be. The narrow claim, and the only one worth defending, is that **the renderer is a software decision that must not become a second physics interface**. Every restriction below is that sentence applied to a concrete case.

In scope: 2D field slices, 3D isosurfaces, the data contract each of them consumes, the byte budget a self-contained artefact must live inside, and the tests that decide whether an implementation is correct without a browser.

Out of scope: anything that changes a number the solver produces, any new server route, any new fetch path, any change to `emfit.job.v1`, and any judgement about which solver ran.

### What this document does not decide

Collected in full in section 12. Named here so a reader does not mistake silence for a decision: it does not pick a library, does not ratify a licence, does not extend the job schema, does not define a new physics quantity, and does not change a tolerance.

## 2. The incumbent, stated as measurement

`emfit/webapp.py` is 541 lines and 25,490 bytes. It is the whole front end. Its module-level imports are `base64`, `html`, `threading`, `traceback`, `urllib.parse` and `http.server` (`emfit/webapp.py:38-43`), that is, the standard library only, plus the package itself (`:45-46`). `pyproject.toml` declares `numpy>=1.24` and `scipy>=1.10` as runtime dependencies and `matplotlib>=3.7` as an optional `viz` extra, so the plotting stack the front end relies on is optional by packaging, not by accident.

The shape of the thing, by the line numbers that matter:

| Part | Line | What it is |
|---|---|---|
| `_page(title, body)` | `emfit/webapp.py:140` | the one and only document shell; every response is one complete document |
| `STYLE` | `:56` | the stylesheet, as a module constant, inlined into the shell |
| `_study_page` | `:258` | the form page |
| `_figure_html` | `:275-287` | one PNG, base64 into a `data:` URI at `:281-284` |
| `_attachment_html` | `:290-309` | one non-PNG output, today the GIF, base64 into a `data:` URI at `:301-305` |
| `_results_page` | `:312-335` | metrics table, then figures, then attachments, then the form again |
| `_error_page` | `:338-348` | a traceback page that keeps the form usable |
| `class Handler` | `:359` | `BaseHTTPRequestHandler`, `protocol_version = "HTTP/1.1"` at `:363` |
| `_send` | `:369-377` | sets `Content-Length` at `:373` and `Cache-Control: no-store` at `:374` |
| `do_GET` / `do_POST` | `:432` / `:472` | six routes, no more (the route table is the module docstring, `:17-27`) |
| `make_server` / `serve` | `:501` / `:514` | `ThreadingHTTPServer` at `:509` |
| `MAX_BODY` | `:50` | 64 KiB, the largest accepted `POST` body |
| `_LOCK` | `:53` | a module lock; one study at a time |

What it is not, and this is the load-bearing part of the section. There is no geometry view: nothing in the file builds or draws a mesh. There is no client-side slicing: no field array reaches the browser, only PNG bytes. There is no colour mapping decision in the front end: colour is decided inside `emfit/viz.py`, server side, before the bytes exist. There is no viewer state: the response is stateless, `no-store`, and the only state a request carries is the submitted form. There is no isosurface anywhere in the tree.

The front end is also JavaScript-free deliberately, and that is asserted rather than assumed: `tests/test_demo_picker.py:96-98` defines `_no_script` as `assert b"<script" not in body, "a response carries a <script> block"` and applies it to served pages. Any artefact described in this document collides with that assertion, which is addressed in sections 8 and 9.

### The recorded cost of the current pattern

`decisions.md:13` is operative and is quoted exactly:

> The results page inlines every figure a study produces, PNG and animated GIF alike, as a `data:` URI produced by `emfit/webapp.py`; there is no route that serves a figure file and no WebSocket, so a result is one response and the browser fetches nothing afterwards.

The cost of that choice is recorded in the same entry (`decisions.md:14`) and is quoted exactly:

> A 280 689-byte animation is 374 KB once base64-encoded, which is 57 per cent of the 656 469-byte response, is re-encoded on every request and carries no cache validator; a `/media/<id>` route or a socket would send the bytes once and let the browser stream them.

Two details of that quotation are worth separating because the briefing conflates them. The absent thing is a *validator* (`ETag`, `Last-Modified`); what the response does send is `Cache-Control: no-store` (`emfit/webapp.py:374`), which is stronger than a missing validator and weaker than a cache: it forbids every cache, so the re-encode on every request is not an oversight that a header would fix. And the 57 per cent is not incidental. It is the measured cost of inlining one animation into one response, and it is the precedent this document's byte budget inherits in section 8.

## 3. The governing ruling

`decisions.md:7079` is §101.19(g), "The UI is a consumer of the same JSON". The three clauses this document is built on are quoted exactly. The sentence that carries the first two has an appositive aside delimited by dashes in the source; the aside is elided as `[...]` and restated in prose immediately below, so that no quotation in this document reprints source punctuation that the house style forbids.

> The field data is already arrays [...] the S-parameters are already in the Touchstone, and the provenance is already in the manifest. The UI reads the same documents the agent reads. Rendering is a software decision, and it must not become a second physics interface: if the UI needs a quantity, the quantity belongs in the contract, and the fix is an addition with a version bump rather than a private read of the solver's internals.

The elided appositive names the arrays: `plane_Ey`, `plane_Ez` and their siblings. Section 4 tests whether they are in the contract. They are not, and that is the finding of this document.

> This also settles when to build it. A UI written before the contract encodes the current data shapes, and those shapes change at every M3 milestone; a UI written after it reads `emfit.result.v1` and is stable.

Three consequences, each of which is a constraint on everything that follows.

**C1, the renderer reads the result document.** Not the solver's arrays, not a dump file, not a pickle. If a picture can only be made by reaching into `emfit.studies` or `emfit.evolve`, the picture is out of contract.

**C2, a missing quantity is a versioned addition to the result contract.** Not a private field, not a job-schema change, not an undocumented key on an existing object. `decisions.md:7059` states the rule the whole interface rests on: "A change to them is a version bump from `emfit.job.v1` to `emfit.job.v2`, never a silent reinterpretation of a field under the old name, because a caller that pinned v1 must keep working." The same rule applies on the result side, where the discriminator is `emfit.result.v1` (`decisions.md:7042`).

**C3, the renderer is written to the contract's shape, not to today's internals.** The timing argument is the reason. Today's field arrays are shaped by whichever study produced them, and those shapes change at every M3 milestone; a renderer written against them is rewritten at every M3 milestone.

## 4. The `emfit.result.v1` inventory

### The answer, first

**A 2D slice and a 3D isosurface are not drawable from `emfit.result.v1` today, and the reason is not rendering.** They are not drawable because there is no result document to read: no result schema file exists, and the sketch that stands in for one carries no field samples at all. A slice *is* drawable today, in one specific and contract-illegal sense: a study renders a matplotlib raster from the solver's own arrays inside the run and hands the front end PNG bytes, so the browser receives a picture of the field without ever holding field data. An isosurface is not drawable from anything in this tree.

The consequence for planning is stated plainly: **the MVP is blocked on a version bump, not on rendering work.** Writing the viewer first would produce code with nothing legal to draw.

### Evidence, in four parts

**(a) There is no result schema, and no emitter.** `schemas/` contains `emfit.job.v1.schema.json`, one example job and its sourcing note, and nothing else. `docs/design/job_schema.md:5-10` says so from the other side: "There is no job emitter, no job reader, no result schema, and no code in the package that knows this schema exists." `decisions.md:7014` says the same of §101.19 as a whole: "There is no schema file, no validator, no versioning machinery, and no code that emits either document below; the two JSON objects are specifications of intent."

**(b) The sketch that stands in for the result document carries no field samples.** The whole of `emfit.result.v1` at `decisions.md:7040-7053` is: `schema`, `status`, `artifacts` (two paths), `provenance` (six members), `warnings`. There is no array in it. `decisions.md:7055` is explicit about where the numbers went: "The numbers themselves do not live in this document; they live in the Touchstone file, whose path is an artifact." A Touchstone file is S-parameters: observables, not fields.

**(c) The arrays §101.19(g) calls "already arrays" live inside the solver, not in a document.** `emfit/studies.py:2718-2721` allocates `plane_ey`, `plane_ez`, `plane_hy`, `plane_hz` as `np.complex128` blocks, and only when the face plane capture is on (`:2719`, resolved at `:2071-2088` from a keyword argument or `EMFIT_PLANE_CAPTURE`). `:3218-3224` assembles them into a dict keyed `plane_Ey`, `plane_Ez`, `plane_Hy`, `plane_Hz` with `station_cells`, `station_x` and the capture source. That dict leaves the process through exactly one door, `EMFIT_BIN_DUMP` (`:3242`), which is an environment variable naming a path. A dump file selected by an environment variable is the definition of a private read of the solver's internals, and it is the thing C1 forbids the renderer to do.

**(d) What a slice is drawn from today.** `emfit/viz.py:206` defines `plot_field_slice(grid, values, component, axis="z", index=None, ax=None, cmap="RdBu_r", title=None, colorbar=True)`. Its `values` argument is documented at `:210-215` as "the full concatenated primal edge-voltage vector (length `cc.n_edges`, i.e. `[EX, EY, EZ]` in the block order of `:class:`emfit.operators.CellComplex``)", and the size is enforced at `:238-241`. That is a solver array plus the solver's grid object. The raster is produced through `pcolormesh` at `:287`. The front end never sees either argument: a study renders the PNG inside the run and appends bytes to a sink, `emfit/studies.py:207-214`, whose figure dict is `{slug, title, png, caption}`. So the incumbent slice is a server-side raster, and the demonstration case is `emfit/demos.py:190-194`, a plain mid-plane `|Ez|` heat map.

**(e) There is no isosurface code.** A search for `marching`, `isosurface`, `skimage`, `trimesh`, `pyvista` and `vtk` across `*.py` returns no implementation: the only hits are the English word "marching" in the prose of `emfit/nearfield.py:6-7`.

### The inventory

The column "legal today" applies C1 and C2 to each row: *yes* means the renderer may read it because it is a member of the result document, *no* means reading it is the private read §101.19(g) forbids, and *n/a* means the quantity does not exist anywhere.

| # | Quantity | In `emfit.result.v1` today | Citation | Legal today |
|---|---|---|---|---|
| 1 | `schema` discriminator | yes, in the sketch only, no schema file | `decisions.md:7042` | yes |
| 2 | `status` (`ok` / `degraded` / `failed`) | yes, three-valued | `decisions.md:7043`, `:7055` | yes |
| 3 | `artifacts.touchstone` (path) | yes | `decisions.md:7044` | yes, as a path |
| 4 | `artifacts.manifest` (path) | yes | `decisions.md:7044` | yes, as a path |
| 5 | `provenance.mesh_cells`, `cell_mm` | yes | `decisions.md:7046` | yes |
| 6 | `provenance.solver` | yes, and the only trace of which solver ran | `decisions.md:7046`, `:7075` | yes |
| 7 | `provenance.tolerance_achieved` | yes | `decisions.md:7047` | yes |
| 8 | `provenance.reference`, `commits`, `decisions_section` | yes | `decisions.md:7048-7049` | yes |
| 9 | `warnings[]` | yes | `decisions.md:7051` | yes |
| 10 | S-parameter values | not in the document; in the file row 3 names | `decisions.md:7055` | yes, through the named artifact, and they are observables |
| 11 | `plane_Ey`, `plane_Ez`, `plane_Hy`, `plane_Hz` | **no** | in-memory only, `emfit/studies.py:2718-2721`, `:3218-3224`; §101.19(g)'s premise at `decisions.md:7079` | **no** |
| 12 | Station geometry for the plane (`station_cells`, `station_x`) | **no** | `emfit/studies.py:3221` | **no** |
| 13 | Node coordinates and element connectivity | **no** | absent from `decisions.md:7040-7053`; the grid is `emfit/grid.py`, reachable only through the solver | **no** |
| 14 | The eigenvalue or frequency a mode corresponds to | **no** | `lambda` and `beta_sq` exist only in a probe artefact, `tools/host/sparse-probe/out_mesh/mode_overlap.json:303-304` | **no** |
| 15 | The grid convention (edge offsets, cell widths, staggering) | **no** | `emfit/viz.py:210-215` documents the convention, in the renderer's argument docstring, not in a contract | **no** |
| 16 | The normalisation of a mode shape | **no, and undefined** | `decisions.md:7008` | **no**, and would mislead if it were read |

Two rows deserve a sentence each. Row 11 is the crux: the arrays exist, they are well shaped, and they are one function call from a picture, and none of that makes them contract data. Row 16 is the one that does not become legal by adding a field: the normalisation is itself an open defect, so a contract that carried a mode shape without carrying its normalisation would formalise the defect.

The honest headline, restated once: the data a slice needs is in `emfit/studies.py`; the data a viewer may read is in `decisions.md`; the two sets do not intersect. Section 5 is the proposal that makes them intersect.

## 5. The solver-to-renderer data contract

**This section proposes an addition to `emfit.result.v1`. The addition requires ratification and a version bump. It is not enacted here, no schema file was created, and no field named below exists in any artefact today.** `decisions.md:7059` fixes the rule: a change to the field set is a version bump, never a silent reinterpretation under the old name.

The addition has one job: to make the arrays in row 11 of section 4 into contract data, with the geometry needed to place them and the provenance needed to label them.

### 5.1 The shape, as a schema sketch

A JSON object, one per renderable view, carried in the result document. It is a sketch of members and meanings, not a schema: no types are normative until a `schemas/emfit.result.v2.schema.json` exists, and none does.

```json
{
  "views": [
    {
      "kind": "plane",
      "normal": "y",
      "index": 100,
      "coordinate_m": 0.01005,
      "grid": {
        "u": "x", "v": "z",
        "nu": 322, "nv": 40,
        "u_m": {"first": 0.0000, "last": 0.0322, "count": 322},
        "v_m": {"first": 0.0000, "last": 0.0040, "count": 40},
        "staggering": "cell-centre",
        "provenance": "co-located from primal edges, transverse node pairs averaged"
      },
      "components": [
        {"name": "Ez", "unit": "V_per_m", "dtype": "float32", "layout": "row-major",
         "encoding": "base64", "scale": 1.0, "offset": 0.0, "data": "(opaque)"}
      ],
      "frequency_ghz": 5.8278,
      "normalisation": {"kind": "unreported", "basis": "see decisions.md:7008"},
      "render": {
        "colormap": "RdBu_r",
        "domain": {"kind": "symmetric", "lo": -1.0, "hi": 1.0,
                   "source": "declared by the emitting study, not by the viewer"},
        "shared_across_panels": true
      }
    }
  ],
  "solver": "fit-leapfrog",
  "schema": "emfit.result.v1"
}
```

### 5.2 Requirements, each with its reason

**Units follow the existing policy rather than inventing a convention.** `docs/design/job_schema.md:95-110` fixes a three-layer rule: the job document is unit-suffixed (`_mm`, `_ghz`), the tool interior is SI (`emfit/demos.py:76` converts millimetres in, `:91` converts GHz in), and conversion happens exactly once at the boundary. The result side is the other side of that same line, so every numeric member carries a suffix (`coordinate_m`, `frequency_ghz`, `first`/`last` inside a member already named `_m`) and every array carries its unit in a named field (`unit: "V_per_m"`). A bare `h`, `f` or `E` appears nowhere.

**The Hz-versus-GHz asymmetry decides the cardinality.** `job_schema.md:112-130` records that the job permits a *set* of frequencies while the interior is a single target: "The map is one-to-many outward and many-to-one inward, and v1 does not model a sweep" (`:128-130`). A result is on the inward side of that map, so a view carries exactly one `frequency_ghz`, the one actually solved. A viewer that receives a set would be re-deriving a sweep the interior never performed.

**The provenance field is carried so the renderer never has to know which solver ran.** `decisions.md:7075`: "A GPU FDTD, a frequency-domain FEM, and a surrogate model trained on FDTD results all produce `emfit.result.v1`, and the `solver` field in provenance is the only trace of which one ran." A renderer that branches on solver identity is a second interface; a renderer that prints `solver` is a label.

**A picture is labelled with a number the contract supplies.** The mode eigenvalue, the beta squared or the frequency is a member (row 14 of section 4, absent today), never a figure title typed into the study. Where no such number exists, the field is `null` and the renderer says so on the face of the image rather than leaving the axis unlabelled.

**Geometry is either structured or explicit, and says which.** A structured grid carries two axis vectors and a staggering convention; an unstructured mesh carries node coordinates and connectivity. The MVP takes the structured branch, because every plane capture in the tree is a structured block (`emfit/studies.py:2718-2721` allocates dense blocks, not sparse node lists). An unstructured branch is a hole for the FEM core that `docs/design/core_contract.md:143` discusses, and is not designed here.

**A view block is optional and plural.** A run with no captured plane carries `views: []` and a renderer has nothing to draw. That is a legal result document, and it must not be an error: the current capture default is off (`emfit/studies.py:2470`, `:2486-2488`).

## 6. What the renderer may and may not claim

This section exists because a visual tool becomes a second physics interface through its defaults, not through its features. Three defaults carry claims.

### 6.1 Colour mapping is not a measurement

A colormap maps a scalar to a colour, and a reader reads the colour as a magnitude whether or not the artefact said so. Two properties therefore have to be declared in the artefact rather than chosen by the viewer.

**The colormap.** The incumbent default is matplotlib's `RdBu_r` (`emfit/viz.py:207`), a diverging map, chosen because the signed components are signed. A diverging map asserts a meaningful zero and a meaningful symmetry about it. For `|E|` that assertion is false, which is why `:266-267` labels the magnitude panel unsigned and `:286` gives it `vmin=0.0`.

**The domain, and whether it is shared.** `emfit/viz.py:285-287` computes `amp = float(np.max(np.abs(data))) or 1.0` and passes `vmin=-amp, vmax=amp`. That is a per-panel autoscale to the data's own maximum, and its consequence is stated plainly: two runs of the same study, or two panels of the same run, cannot be compared by eye, because each panel is normalised to itself. The existing escape hatch is documented at `:228-231`: pass `colorbar=False` and draw one figure-level bar "when several panels share one colour scale". The MVP is required to take that route and to declare `shared_across_panels` and the explicit `lo`/`hi` in the artefact, so that the picture carries the scale instead of the viewer inventing one.

### 6.2 Amplitude normalisation is undefined

`decisions.md:7008` is quoted exactly:

> `emfit/mode2d.py:636` documents the normalisation as `e^T B e = 1`. The code at `:1127-1130` divides by the plain Euclidean 2-norm. The docstring is factually wrong about what the routine does, and the gap between them is a mass-matrix norm against a 2-norm, which is not a rounding difference.

`decisions.md:7010` adds that the status is OPEN and must not be fixed in a document. The rendering consequence is exact and must appear on the face of the artefact: **a mode-shape picture shows a shape, not an amplitude.** The colour bar of a mode panel is labelled as arbitrary units, the `normalisation` member of section 5.1 carries `kind: "unreported"`, and the renderer is forbidden from printing a units label it cannot source.

### 6.3 Isosurface level is a viewer parameter, not a result

An isosurface is a level set, and the level is chosen, not measured. If the level is not recorded with the image, the image is not reproducible: the same array at two levels is two different pictures, and a reader cannot tell which was drawn. The level, the units of the field it applies to, and the colour or opacity assigned to each surface are recorded in the artefact. A level supplied interactively by a reader is a rendering control, and a picture exported from one carries the level it was exported at.

## 7. MVP scope

Two capabilities and nothing else: 2D slices and 3D isosurfaces.

### 7.1 Slice sampling

A FIT field is staggered: the electric components live on primal edges, one family per axis (`emfit/viz.py:210-215`). A slice through cell centres therefore requires co-location before anything is drawn, and `emfit/viz.py:256-262` is the convention already in use: average the transverse node pairs onto the cell centre, then divide the edge voltage by the cell width along its own axis to reach V/m. The map is drawn with `shading="flat"` at `:287`, that is, nearest neighbour, no interpolation.

**The MVP reuses that convention exactly.** The reason is not conservatism for its own sake: a WebGL slice that interpolates differently from the PNG of the same run produces two pictures of one field that disagree, and neither is wrong, which is the worst possible outcome for a reader. The interpolation convention is declared in the artefact (`grid.provenance` in section 5.1) and any departure from the incumbent's convention is an **OPEN** ruling, not an implementation detail.

### 7.2 Isosurface extraction

Marching cubes or an equivalent level-set extractor, run over a scalar field sampled on a declared grid, producing a triangle soup. Two things about it are marked **OPEN** rather than assumed.

Whether the specific algorithm's usage, or any particular library's implementation of it, carries any encumbrance is not established here. That question is general knowledge about the field and the literature, and **it was not verified in this tree**: no licence file, no vendoring record and no third-party source is present in the repository to check, and no search for the answer was performed. It is recorded as unverified because a claim of "no encumbrance" that nobody checked is exactly the class of statement this project refuses elsewhere.

### 7.3 The input scale the MVP must survive

These are the numbers in the tree, not invented ones.

| Mesh | Free edges | Citation |
|---|---|---|
| `M5_ctrl_rung4` | 9,604 | `tools/host/sparse-probe/out_mesh/mode_overlap.json:57`, `:71-73` |
| `M1_fe11888` | 11,888 | `mode_overlap.json:114`, `:130` |
| `M2_fe19665` | 19,665 | `mode_overlap.json:171`, `:187` |
| `M3_fe28980` | 28,980 | `mode_overlap.json:228`, `:244` |
| `M4_fe30672` | 30,672 | `mode_overlap.json:285`, `:299-301` |
| target class | 30,000 | `docs/design/sparse_eigenmode.md:355` (`free_e = 30000`) |

So the range a transverse-plane slice must survive is 9,604 to 30,672 free edges, with a design target of 30,000. A plane capture of that kind is not the hard case; `emfit/studies.py:2720-2721` allocates dense blocks per station in exactly this size class.

### 7.4 The full 3D grid, and why the size is not a guess here

An isosurface needs a volumetric field, not a plane, and the volumetric size is where the MVP meets the budget. The recorded run at `decisions.md:812` is `322 x 200 x 40` cells at 0.1000 mm. Derived from that, and *derived* is the operative word:

- cells: `322 x 200 x 40 = 2,576,000`
- primal edges at three families per cell: about `7.73e6`
- one complex field array at 8 bytes per value (`complex64`): `61.8e6` bytes, about 61.8 MB
- base64 at four characters per three bytes: about `82.4e6` bytes, about 82.4 MB
- against the incumbent's measured 656,469-byte response (`decisions.md:14`): about 125 times larger

A full 3D field grid therefore does not ship inside a single response, and no viewer design changes that. The only route is server-side extraction or a declared decimation of the sampling grid before the field is serialised. Which decimation is chosen, and its ratio, is an **OPEN** ruling; **the triangle count and the byte size of the extracted surface are (to be filled at run time)**, because they depend on the field and the level, and any figure written here for them would be invented.

## 8. Delivery and the byte budget

### 8.1 One response, nothing fetched

The delivery path is fixed by `decisions.md:13` and by the incumbent: one HTTP response, `Content-Length` set (`emfit/webapp.py:373`), `Cache-Control: no-store` (`:374`), no media route, no WebSocket, and the browser fetches nothing afterwards. Everything the artefact needs is inside the response body.

### 8.2 What gets inlined

The geometry block, the field arrays, the colour table, the shader source (as a string), the viewer code (as a string), and the labels. This is the same shape as the incumbent's stylesheet, which is already a Python constant inlined into every page (`emfit/webapp.py:56`, used by `_page` at `:140`), so inlining text is precedent and not novelty. What is novel is inlining *code that executes in the browser*.

### 8.3 The byte budget

**Proposed budget: any single response stays at or below 656,469 bytes, the measured worst case of the current front end** (`decisions.md:14`). The justification is the 57 per cent: the current page already spends 374 KB of that 656,469 on one animation, and that expenditure was accepted only because the alternative was a media route the design rejects (`:15`). A viewer that needs more than the page it replaces is asking for a ruling, not making an engineering choice.

The budget is not a formality. It is what makes the library question a question, as the next subsection derives.

### 8.4 The derived constraint, stated as a derivation

The steps are: the response is one document and the browser fetches nothing afterwards (`decisions.md:13`); therefore no second request exists in which a library could be fetched; therefore no CDN and no relative `src` to a server route can supply a renderer library; therefore any third-party renderer must be present inside the whole at the moment the response is written, which means vendored and inlined; and therefore its bytes are spent out of the same 656,469-byte budget as the field data it is meant to draw.

> **A self-contained artefact that fetches nothing cannot load a library. Any third-party renderer must therefore be vendored, inlined into the same single response, and paid for out of the same byte budget as the field data. The library and the field are not a dependency and its consumer; they are two competitors for the bytes of one response.** That competition, and not taste, decides the library question, and it is why this document ratifies nothing.

### 8.5 The two branches, with the tradeoff stated both ways

**Branch A, hand-written WebGL against no third-party dependency.** The cost is that the shaders, the matrix stack and the interaction code are ours, reviewed and tested like the rest of the repository, and the code spends budget the field data needs. The benefit is that the artefact stays inside the standard-library discipline the front end already holds (`emfit/webapp.py:38-43`), no licence question exists, and section 9's tests can be written against code this project owns. The risk is that hand-written graphics code is exactly where a project writes a bug it cannot see, because it has no browser.

**Branch B, a vendored renderer library.** The cost is a licence question this document does not answer, plus a code size that competes directly with the field arrays: a general-purpose 3D renderer is a large artefact by any measure, and **its exact minified size is (to be filled at run time)**, because no such library is present in this tree to measure and a remembered number would be a fabrication. The benefit is that the hard geometry code is somebody else's and the byte cost is paid once.

Choosing B means arguing the budget upward, and the budget is the 57-per-cent precedent, so the argument has to be that a *viewer* is worth more of the response than an *animation*. That is a product ruling, not a technical one: **OPEN**.

### 8.6 Where the artefact is generated

Two candidates, both consistent with the contract and both **OPEN**: a build-time static page produced once and served as a constant, or a per-result page produced inside `_results_page` alongside the figures (`emfit/webapp.py:312-335`). The per-result route reuses the existing plumbing and keeps the picture next to the metrics table; the build-time route amortises the viewer code across runs and keeps the per-run response small. They differ in where the byte budget is spent, which is why the ruling is coupled to section 8.5.


## 9. Acceptance tests that do not need a browser

The governing fact is `decisions.md:16`: "No browser binary exists in this container, so the animation is verified by decode and not by watching it play." Every test below is therefore a computation over bytes or over numbers. **The verdict vocabulary is exactly PASS and FAIL. "Looks right" is not a verdict.** There are no screenshot diffs and no visual regressions, because a screenshot diff needs a renderer, and the renderer is the thing under test; a suite that compared two PNGs would be comparing two runs of code nobody had checked.

Six tests. Each states what it pins, and each is a stronger statement than it first appears, which is why they are written out rather than listed.

### 9.1 The artefact fetches nothing

A byte scan of the response body for every construct that causes a subresource request. The banned set, checked case-insensitively against the attribute names:

| Construct | Why it is banned |
|---|---|
| `src="http`, `src='http`, `href="http`, `href='http` | an absolute URL is a fetch, whether or not the network is up |
| `src="//`, `href="//` | protocol relative; same fetch, one scheme shorter |
| `fetch(`, `XMLHttpRequest`, `importScripts`, `new Worker` | programmatic fetch, and the two worker constructors |
| `integrity=`, `crossorigin` | an attribute that only exists to validate or authorise a fetched resource |
| `@import`, `url(` inside the inlined stylesheet | a stylesheet import or a `url()` reference is a fetch from inside CSS, where a `src` scan does not look |

The last row is the one that is easy to miss, and it is the reason the stylesheet matters: the front end already inlines its CSS as a Python constant (`emfit/webapp.py:56`, consumed by `_page` at `:140`), so the whole of the CSS is available to the scanner, and any `url(` in it is a fetch that no `<img>` search would find.

One pattern must **not** be scanned: a bare `//`. Standard base64 includes `/` in its alphabet, so field data encoded per section 5.1 can contain `//` by accident, and an unanchored search would fail a correct artefact on a byte that means nothing. The protocol-relative check has to be anchored to `src="` or `href="`.

`data:` URIs are allowed and are the delivery mechanism (`decisions.md:13`). The distinction the test draws is not "external versus inline" but "does the browser issue a second request".

**What this test cannot see.** Whether the browser *would* have fetched something is not observable here. The scan is a statement about the bytes, and it is the only statement available without a browser. It is still the right statement: a construct that cannot appear cannot be dereferenced.

### 9.2 The decode round-trip

`components[].data` is base64, so three properties are asserted. First, the decoded length equals `nu * nv * itemsize` for the declared `dtype`. Derived: the example view of section 5.1 is `322 x 40` at `float32`, so `12,880` values at `4` bytes is `51,520` bytes, and its base64 form is `ceil(51520 / 3) * 4 = 68,696` characters. Second, the decoded values equal the source array. Third, a deliberately corrupted body fails the same test.

The tolerance is the interesting part, and it is not invented here. If the artefact carries the dtype the solver produced, base64 is lossless and the assertion is exact equality, which should be the default assertion because a tolerance would hide an encoding bug behind a number. If the dtype is narrowed to fit the budget, the recorded float32 round-trip of the captured fields is `1.10e-10` and `9.87e-11` relative (`decisions.md:7192`), so the assertion is a relative error at or below `1.10e-10`, the larger of the two measured figures. That is a measured bound on the operation the test performs, not a convenience.

The corrupted-body case is not padding. A test whose only input is a known-good artefact proves that the code runs; it does not prove that the assertion can fail. Every test in this section has a failing input named with it for that reason.

### 9.3 The analytic sphere

The one isosurface test that needs no field data, no mesh and no solver: a synthetic scalar field `f(x, y, z) = sqrt((x - x0)^2 + (y - y0)^2 + (z - z0)^2)` sampled on a declared grid, with a level set at `f = r0`. The exact answer is known in closed form, which is the whole point: the extractor can be checked against geometry rather than against a picture of geometry.

Assertions:

- every vertex `p` satisfies `abs(|p - centre| - r0) <= tolerance`, with the tolerance stated below;
- the surface is closed: every triangle edge is shared by exactly two triangles, checked over the edge multiset;
- the normals are outward: `dot(n, p - centre) > 0` for the triangle normal `n` and its centroid;
- the topology is a sphere: `V - E + F = 2`;
- the triangle count is greater than zero and is reported, so a later regression in the table walk shows up as a changed number rather than as silence;
- a second case, a level that the field never reaches, returns zero triangles and raises nothing.

**The tolerance is proposed, not measured: half a cell diagonal, `0.5 * sqrt(dx^2 + dy^2 + dz^2)`.** The reason it is a proposal is the reading discipline of this document: no code was executed for it, so no vertex-radius error was observed. The protocol that replaces it is the one this project uses elsewhere: run the extractor on the sphere, record the measured maximum vertex-radius error, and set the tolerance to that measurement with a stated margin. Until then the number is a guess, and it is labelled one.

### 9.4 The byte budget

`len(response_body) <= 656469` (`decisions.md:14`), asserted on the bytes the server returns, not on the JSON before encoding. The distinction is the whole of section 8: the HTML wrapper, the base64 expansion and the inlined viewer code all spend the same budget, and only the returned body shows the total.

The share available to a viewer on a page that already carries an animation is smaller, and deserves its own number. Derived: the recorded animation is 280,689 bytes, its base64 form is `ceil(280689 / 3) * 4 = 374,252` characters, which is the record's "374 KB", so the budget remaining is `656,469 - 374,252 = 282,217` bytes. A viewer that lands on that page is arguing over 282,217 bytes, not 656,469.

The test's failure message reports the measured length and the overrun in bytes. A bare FAIL sends the next author back to the arithmetic; the number sends them to the item that grew.

### 9.5 The declarations are present

Presence assertions over the contract, none of which assert that a value is *right*: `render.colormap`; `render.domain.lo` and `render.domain.hi`; `render.shared_across_panels`; the isosurface level on every view whose `kind` is `isosurface`; `normalisation.kind`; `frequency_ghz`; `solver`.

`normalisation.kind: "unreported"` is a **legal value**, so the assertion is presence and not truth. This is deliberate and it follows from section 6.2: a test that required a real normalisation everywhere would push an author to write one, and the defect at `decisions.md:7008` is open, so a written normalisation would be the defect formalised. The test that would be wrong here is the stricter one.

Two negative assertions belong with these. The rendered page must not print a units label for a component whose `unit` is absent, and must not print a colour-bar range that differs from the declared `lo` and `hi`. Both are string comparisons against the artefact that produced the page, both are cheap, and both catch the exact failure mode of section 10.3.

### 9.6 The existing gate, the collision it produces, and the ruling that resolves it

`tests/test_demo_picker.py:96-98` is already in the tree:

```python
def _no_script(body: bytes) -> None:
    """This front end is JavaScript-free on purpose; a page is not exempt."""
    assert b"<script" not in body, "a response carries a <script> block"
```

It is called on the landing page (`:122`), the error page (`:152`), a study form (`:169`) and both results pages (`:187`, `:205`). The results page is exactly where a viewer would live.

**A client-side viewer cannot pass this gate, and the sentence that decides it is the docstring's: "a page is not exempt."** WebGL is reached from script; a `<canvas>` with no script is a blank rectangle; an SVG that a reader can rotate is script. So as the tree stands, sections 7 and 8 describe an artefact that the front end's own test forbids on every page it serves.

This is not a defect in the test and not a defeat for the design. It is a conflict between two intents, and it was recorded at Dispatch 42 as an **OPEN** ruling. It is **ruled** at Dispatch 43: **R2, the script policy, stands, and a page served by this front end does not execute script.** A client-side viewer is therefore not admissible on any page this front end serves, and the three ways out below are reduced to the ones that do not change the policy. **The guard condition matters as much as the ruling.** R2 binds the pages this handler serves (`emfit/webapp.py:359`, `do_GET` at `:432`), not the visual engine and not the artefact: a viewer that renders without script is admissible anywhere, and a page produced by a different handler, outside this front end, is outside this ruling and must say so where the artefact is generated (8.6). The ruling is about which pages may run script, and it is not a statement that interaction is unwanted.

1. **Render on the server** and ship a raster or a server-written SVG. No script, passes the gate as written, and is what the incumbent already does (`emfit/viz.py:287`, `pcolormesh` to PNG). The cost is the interaction that motivated a client-side viewer, and section 7's MVP becomes a better PNG rather than a model in the browser.
2. **Put the viewer on a page outside the front end's policy.** This one does not survive contact with the code: every response is served by the same handler (`emfit/webapp.py:359`, `do_GET` at `:432`, `do_POST` at `:472`), so there is no outside.
3. **Change the policy.** Allowed, deliberate, and a ruling. The docstring's "a page is not exempt" is the sentence that makes it a ruling rather than a test edit.

### 9.7 What this suite does not establish

PASS on all six means: the artefact fetched nothing, decoded correctly, extracted a sphere within a stated tolerance, fitted the budget, declared its labels, and did not carry a script block it was not allowed to carry. It does **not** mean the picture is readable, well labelled for a human, or interpreted correctly by whoever looks at it. That is a limit of testing without a browser and it should be written down rather than discovered later.

## 10. Failure modes

Five ways this goes wrong. The first three are visible in the artefact; the fourth is the lesson this project has already paid for; the fifth is the one that looks like success.

### 10.1 The silent external dependency

The visual analogue of a change that works in one environment and not another. The artefact looks self-contained, the author's machine has network, the picture is right, and on a machine with no network the page renders blank or renders wrong with no error anywhere. Nothing in the artefact announces the dependency, and no test in the tree looks for it. Section 9.1 is the countermeasure and it must be in the suite before the first viewer, not after the first blank page.

### 10.2 The colormap that makes a physics claim

A diverging map on an unsigned quantity asserts a meaningful zero and a symmetry about it. The picture is not wrong; the reading is. This is worse than a wrong picture, because a reader never questions a picture that looks plausible, and the claim was made by a default (`emfit/viz.py:207`, `RdBu_r`) rather than by a sentence. Section 6.1 and test 9.5 are the countermeasures: the colormap and the domain are declared by the emitting study, never chosen by the viewer.

### 10.3 The unlabelled normalisation

The mode-shape picture whose colour bar reads `V/m`. `decisions.md:7008` records that the normalisation is undefined and `:7010` records that the status is OPEN, so any amplitude printed on that figure is a fabricated number wearing a real unit. The harm-to-effort ratio here is the worst in this document: it costs one string to avoid and it invalidates whichever conclusion was drawn from the figure. Section 6.2 and the two negative assertions of 9.5 are the countermeasure.

### 10.4 The lesson already in the record

`decisions.md:808` states it, quoted exactly:

> That would have been a study that worked from the command line and was unusable in the interface, and no test would have caught it. A parameter kind is not finished until the form knows what to draw for it.

The generalisation this document adopts is one line: **a quantity is not finished until the renderer knows how to draw it.** A field array that exists, is arithmetically correct and has no declared geometry is that failure in its visual form. It can be computed, it can be plotted by whoever has the solver in front of them, and it cannot be drawn by anything downstream. Section 4's rows 11 to 16 are six quantities in exactly that state, which is why the answer to "can this be drawn today" is no.

### 10.5 The viewer that draws everything

The mirror of 10.4. A renderer that will draw whatever it is handed hides the absence of a quantity: an unlabelled axis looks like a labelled one at a glance, and a viewer that autoscales silently makes every array look like a good array. The countermeasure is the declaration requirement of section 5, applied as an assertion: a member that is missing must produce a visible statement on the face of the image or a refusal, and never a default that fills the gap.

## 11. Rulings: two taken, seven open

Nine, collected in one table so that the number is visible. Seven are **OPEN**: nothing in those seven is a decision this document is entitled to take. Two are **ruled** at Dispatch 43 and are marked in the table with the number this document gives them beside the brief's label: **R2, the script policy, is ruling 8 below** and is recorded in 9.6; **R3, field arrays in `emfit.result.v1`, is ruling 5 below** and carries two specifications.

| # | Ruling | What it decides | Where it bites |
|---|---|---|---|
| 1 | A third-party renderer, and its licence | whether branch A or branch B of 8.5 is taken at all | the whole of sections 8 and 9 |
| 2 | Vendoring against the byte budget | whether a renderer library's bytes may displace field bytes, and by how much | 8.3, 8.4, 9.4 |
| 3 | Slice interpolation | whether the viewer reproduces the incumbent's nearest-neighbour convention or interpolates | 7.1; two pictures of one run that disagree |
| 4 | The isosurface algorithm, and its encumbrance | which extractor is written or vendored | 7.2, unverified and recorded as unverified |
| 5 | Whether field arrays enter `emfit.result.v1` | **RULED (R3): they enter as a sidecar, with two specifications.** First, the **absent case is legal**: a result that carries no field arrays is a legal result, and a page must declare the absence rather than default it (5, 10.4). Second, the arrays are **not base64-encoded**: the sidecar carries them as binary, because base64 inflates a field by a third and the byte budget is already an argument (8.3, 8.4) | 4, 5, `decisions.md:7059` |
| 6 | The colormap default and the domain policy per component | what a reader is told a colour means | 6.1, 10.2 |
| 7 | Where the artefact is generated | build-time static against per-result, and therefore where the budget is spent | 8.6 |
| 8 | Whether a page may execute script | **RULED (R2): it may not**, on any page this front end serves, and any artefact it serves must render without script. Guard condition: the ruling binds the served pages and not the engine, so a page from a different handler is out of scope and must say so (9.6, 8.6) | 9.6, and the shape of the MVP |
| 9 | The sampling or decimation ratio for a volumetric field | what an isosurface is extracted from, given 7.4's size | 7.4 |

Rulings 1, 5 and 8 are the ones that gate everything else. Ruling 5 comes first in time because it is the only one that is not a matter of taste: without arrays in the contract there is no viewer to argue about. Ruling 8 is the one most likely to be discovered late, because it is a test in a file about demo pickers, and it is included here so that it is discovered in a document rather than in a failing build.

## 12. What this document does not decide

A list, because the boundary of a design document is the most useful thing in it.

- **It does not extend `emfit.job.v1`.** `docs/design/job_schema.md` remains authoritative for the job document, and section 5 is a proposal about the result document only.
- **It adds no server route.** No media route, no WebSocket, no second request. `decisions.md:13` fixes one response and nothing fetched afterwards, and every section above is written inside that constraint.
- **It ratifies no library and no licence.** No dependency is named as the choice, in section 8 or anywhere else.
- **It proposes no physics.** No field, no tolerance, no mesh, no solver behaviour and no observability is changed by anything here.
- **It does not repair `decisions.md:7008`.** The normalisation defect stays OPEN and is handled by declaration on the artefact, which is the only handling available to a rendering layer.
- **It does not fix the isosurface tolerance of 9.3.** That number is a proposal pending a measurement, and it is labelled as one.
- **It answers none of section 11 except the two rulings taken at Dispatch 43**, R2 in 9.6 and R3 in the table, which are marked as rulings there and are appended rather than substituted into this section.
- **It writes nothing under `emfit/`.** The package was read to produce this document and not modified.

The one sentence a reader should carry out of it: **the MVP is blocked on the schema addition and on two conditions, not on the two rulings.** R3 admits field arrays into `emfit.result.v1` as a sidecar, and what remains is the absent case (a page must declare it rather than default it) and the transfer form (binary, not base64). R2 keeps the JavaScript-free policy, and what remains is the guard test that enforces it on every page the front end serves. The data is one function call from a picture, the picture is one schema addition from being legal, and the byte budget is one argument away from being enough or not enough.

