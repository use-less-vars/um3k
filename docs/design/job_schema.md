# The emfit job schema, v1

## Status

**Design only.** Nothing in this document is implemented in `emfit/`. There is no job
emitter, no job reader, no result schema, and no code in the package that knows this
schema exists. What exists is a JSON Schema document (`schemas/emfit.job.v1.schema.json`),
one worked example (`schemas/examples/microstrip_stub.job.json`) with a sourcing note, and
a validator (`tools/host/validate-job-schema.py`) that lives outside the package and is a
development aid, not a runtime component.

The reason to say this loudly is `decisions.md:7014`, which records §101.19 itself as
design-only, and `decisions.md:7083`, which says the interface is stable only *after* M3c.
So this is a design artefact written ahead of its own stabilisation date, and the
divergences below are the price of that.

A second banner: `decisions.md:7091` records that the provenance record §101.19 sketches is
**FDTD-shaped** — it assumes a time-domain solver accumulating over a run. This schema
describes a *job request*, and deliberately says nothing about provenance, because
committing to an FDTD-shaped provenance block in v1 would bake in a solver assumption that
§101.19(i) already flags as a defect to be repaired.

## The criteria this work was held to

Seven criteria, frozen in `.scratch/dispatch41_task2_prereg.md` **before** any artefact was
written, so that the artefacts could not quietly redefine their own success.

| # | Criterion | Verdict |
|---|---|---|
| J1 | `$schema` is 2020-12, the document parses, and `Draft202012Validator.check_schema` accepts it. | **PASS** — `$schema` is `https://json-schema.org/draft/2020-12/schema`, `$id` is `urn:emfit:job:v1`, `check_schema` raises nothing under jsonschema 4.26.0. |
| J2 | Every node carrying `properties` also carries `additionalProperties: false`. | **PASS** — walk over all 7 property-bearing nodes: 0 not closed. |
| J3 | Every property description ≥ 20 characters; every numeric property is unit-suffixed (`_mm`, `_ghz`) or on an allow-list; `frequencies_ghz`'s description distinguishes GHz from Hz in words. | **PASS** — 0 short descriptions, 0 unsuffixed numeric properties (allow-list: `substrate_eps_r`, `substrate_cells`, `value`), `frequencies_ghz` says "GIGAHERTZ, not hertz". |
| J4 | The example validates, and every numeric literal in the sourcing table has a `file:line` origin with the arithmetic recomputed. | **PASS** — validator exit 0; see `schemas/examples/microstrip_stub.job.note.md`. |
| J5 | Stdlib-only imports; identical exit codes under `python3 -S`. | **PASS with a caveat** — module-level imports are `argparse, json, os, re, sys`. `jsonschema` is imported *lazily inside* the cross-check function (`tools/host/validate-job-schema.py:402`) and its absence is reported, never decisive. Under `-S` all four exit codes are unchanged (0 / 1 / 1 / 1). |
| J6 | Three mutations each exit 1 naming the exact JSON pointer. | **PASS** — see Results. |
| J7 | Ten literal headings present in this document. | **PASS** — this document. |

### Pre-registration provenance

This subsection exists because the criteria this work was held to are not, in the end, a
verbatim copy of the criteria it was commissioned against. Recorded plainly rather than
smoothed over.

**What is true.** J1–J7 were fixed in `.scratch/dispatch41_task2_prereg.md` **before any
artefact in this deliverable existed** — before the schema, the example, the note and the
validator. The prereg file was written first and was not edited afterwards to match what
was built. That ordering is real and is the reason the criteria can be trusted as criteria.

**What is also true.** The criteria in that file are a **restatement**. The verbatim
dispatch wording was lost to a context summarisation part-way through the task, and the
seven criteria were reconstructed from the dispatch plan. In reconstructing them, they were
**renumbered and partly re-scoped**: one intended criterion was replaced by a different
criterion wearing the same number, one was widened, and one new criterion was added that
the commission never asked for. The prereg is therefore honest about intent but is not
authentic as a quotation.

The mapping, criterion by criterion, with gaps named as gaps:

| Intended | What was actually registered and adjudicated | Status |
|---|---|---|
| J1 — schema parses, declares the 2020-12 `$schema` URI and an `$id` | registered J1 — `$schema` URI, parse, `check_schema`, `$id` | **matched** (registered J1 is slightly stronger: it also runs `check_schema`) |
| J2 — top-level `schema` is exactly `emfit.job.v1` | registered J2 — every `properties`-bearing node has `additionalProperties: false` | **GAP.** A different criterion took the number. The version-string binding was not adjudicated at all until mutation `m4` was added after the fact. |
| J3 — example validates with zero errors, validator exit 0 | registered J4 — example validates **and** every numeric literal is sourced | **matched and widened** (intended J3 was folded together with intended J6) |
| J4 — ≥3 negative mutations rejected, each naming its JSON path, a wrong-reason rejection not counting | registered J6 — three mutations each exit 1 at the exact pointer | **matched** |
| J5 — validator stdlib-only, runs under `python3 -S` or a bare interpreter, `jsonschema` cross-check optional | registered J5 — stdlib import audit + identical exit codes under `-S` | **matched**, with the caveat that `jsonschema` does appear as an optional in-function import |
| J6 — every numeric value traceable to a named `file:line` or a stated derivation, zero invented numbers | registered J4 — sourcing table with `file:line` and recomputed arithmetic | **matched** (same criterion as intended J3 above) |
| J7 — the note states a normative units policy and contains a 'Divergences from `decisions.md` §101.19' section | registered J7 — ten literal headings present in this document | **weaker instrument.** The two required sections are among the ten, so both exist; but a heading-presence check is syntactic and does not test whether the units policy is normative or the divergences are real. The content was written to be both; the *check* did not prove it. |
| — (not commissioned) | registered J3 — descriptions ≥20 chars, unit-suffix audit, GHz-not-Hz wording | **added during the restatement**, at no one's request |

**The gap is now closed.** Mutation `m4` (`.scratch/m4_wrong_version.job.json`) changes the
top-level `schema` value to `emfit.job.v2` and nothing else of substance; mutation `m4b`
changes it to `emfit.job.v1.`. Both exit 1 at `/schema` with `must be the constant
"emfit.job.v1"`. That is the evidence intended J2 asked for, obtained after the fact rather
than during the pass, and it is recorded here as after the fact.

## The field map

The field map derives from `decisions.md:7016-7036` (§101.19(b)), with the boundary rule at
`:7016-7022` deciding what belongs in the job rather than in the machine. The full working
map is `.scratch/job_v1_fieldmap.md`; the schema itself is the normative artefact.

| Job member | Type | Required | Source |
|---|---|---|---|
| `schema` | `const "emfit.job.v1"` | yes | version discriminator |
| `geometry` | `oneOf` kicad \| parametric | yes | `decisions.md:7036` (parametric is the required branch) |
| `materials` | `substrate_eps_r`, `substrate_h_mm` | yes | `decisions.md:7028` |
| `sources` | array of `$defs/source`, min 1 | yes | `decisions.md:7029` |
| `observables` | array of `$defs/observable`, min 1 | yes | `decisions.md:7030` |
| `frequencies_ghz` | array of numbers, unique | yes | `decisions.md:7031` |
| `tolerance` | object `{kind: const "sparam_abs", value: number > 0}` | yes | `decisions.md:7032` |

Seven members, all required. See the divergences below for why "all required" is itself a
divergence.

## Units policy

Three-layer rule, applied without exception:

1. **The job document is unit-suffixed.** A field name carries its unit (`_mm`, `_ghz`), or
   its unit is stated in the description where no suffix is possible (`substrate_eps_r` is
   dimensionless; `substrate_cells` counts cells; `value` inherits its unit from the key it
   belongs to). A bare `h` or `f` never appears.
2. **The tool interior is SI.** `emfit/demos.py:76` converts millimetres to metres on the
   way in (`h = float(h_mm) * 1e-3`); nothing downstream carries a millimetre.
3. **Conversion happens exactly once, at the boundary.** `emfit/demos.py:91` is the frequency
   boundary: `f_target = float(f0_ghz) * 1e9`. The job schema is the other side of that same
   line.

This is why the schema can validate a document without knowing anything about the solver,
and why the solver never has to ask what a number meant.

## The Hz-versus-GHz asymmetry

The schema gives `frequencies_ghz` an `items` `maximum` of `1000.0`. That number needs
justifying, because a schema that caps a physical quantity is making a claim.

**It is a unit guard, not a physics claim.** A caller who writes `2.4e9` where `2.4` was
meant has written a number of the correct *type* — no type keyword, no `minimum`, and no
`pattern` can catch it, because the error is dimensional, not syntactic. What can catch it
is a magnitude ceiling set far above any physical fixture in this repository and far below
the smallest plausible unit error. `1000.0 GHz` is 1 THz: the demos run between 1 and 20 GHz
(`emfit/demos.py:392` bounds `f0_ghz` to 1.0–20.0, and `:52` defaults it to 5.0), so the
ceiling sits a factor of fifty above the top of the working range, while a hertz-for-GHz
mistake sits a factor of 10⁹ above it. The gap between "legitimate request" and "unit
mistake" spans nine orders of magnitude; any ceiling inside that gap does the same job.

The asymmetry worth naming: the schema permits a *set* of frequencies and labels it GHz,
while the tool's interior is a *target* frequency in Hz. The map is one-to-many outward and
many-to-one inward, and v1 does not model a sweep — see "What this document does not
decide".

## Sourcing table

Every number in `schemas/examples/microstrip_stub.job.json` traces to a line of code or a
line of decision, with the arithmetic recomputed by hand. The full table, including the
numbers deliberately *omitted*, is in `schemas/examples/microstrip_stub.job.note.md`.

Summary of the recomputation, all from `emfit/demos.py:40-55` and `emfit/studies.py:2555`:

| Quantity | Arithmetic | Value |
|---|---|---|
| cell size | `h / N_SUB` = 1.6 / 2 | 0.8 mm |
| grid extent | `N_PML + N_REF + N_LINE` = 4 + 2 + 40 | 46 cells |
| line length | `nx * cell` = 46 × 0.8 | 36.8 mm |
| strip width | `strip_cells * cell` = 6 × 0.8 | 4.8 mm |
| port position | `ix_port = N_PML + N_REF` = 4 + 2 → 6 × 0.8 | 4.8 mm |

The example is **UNLOADED**: the demo's `load_value` and `load_at_mm` are not expressible in
v1, so the example cannot reproduce `demo_microstrip_stub` exactly. The note says so rather
than papering over it.

## Divergences from decisions.md §101.19

Recorded, not repaired. Each is a place where the frozen prose and a machine-checkable
document could not both be satisfied, and the schema took the checkable reading.

1. **`frequencies_ghz` is kept verbatim.** §101.19 uses that name; the schema does not
   rename it to anything tidier. The prose at `decisions.md:7031` shows `[2.4, 2.45, 2.5]`.
2. **All seven members are required.** `decisions.md:7022` says "six things … and the one
   thing it may ask for", which implies exactly one member is optional — and the prose never
   says *which*. Rather than guess, v1 requires all seven. This is a real divergence: an
   optional member that is silently required will reject documents §101.19 would accept.
3. **The tolerance is global.** `decisions.md:7089` records a defect — tolerance scope
   asymmetry, where the tolerance is stated once but applies unevenly across observables.
   A single top-level `tolerance` **object** applies to the whole job, one `{kind, value}` pair
   for every observable at once, and so reproduces that asymmetry; it does not repair it.
   Repairing it needs per-observable tolerances, which is a v2 field.
4. **The document is closed.** `decisions.md:7063` says unknown fields are tolerated. A
   closed document (`additionalProperties: false` everywhere) rejects them. Resolved on the
   *reading* side: the schema is normative for what a job may contain, and a reader that
   wants forward tolerance can strip unknown members before validating. The schema does not
   try to encode "tolerant" as a validation rule, because JSON Schema cannot express it
   without also accepting typos.
5. **The `net`/`x_mm` cross-document rule is not enforced.** `source` is a `oneOf` over a
   netlist reference and an explicit x-position. Whether a given net name exists in a given
   KiCad file is a cross-document fact: no single-document schema can check it, and v1 does
   not pretend to.
6. **There is no load member.** `emfit/demos.py:118-119` defaults `load_value` to 200.0 at
   `load_at_mm` 12.8 mm (`:55`); the demo is a *loaded* stub. v1 has no field for a load, so
   the worked example is the unloaded case and the note declares it.
7. **`nsteps` and `dt` are absent.** `decisions.md:7036` mentions "a stated time step" in
   prose. Since a time step is a solver choice, not a job requirement, v1 omits it — see
   "What this document does not decide".

## Versioning policy

`decisions.md:7059` is the anchor: any change to the set of fields bumps the version.

- **v1 is frozen at `emfit.job.v1`.** The `schema` member is a `const`, so a v2 document
  cannot pass as a v1 document and vice versa.
- **Any field added, removed, renamed, or reinterpreted is a v2.** No silent
  reinterpretation: if the meaning of `tolerance` narrows from global to per-observable,
  that is v2, even though the name could be kept.
- **Widening a bound is a substantive change** and is treated as a version event when it
  changes what a conforming document *means* (e.g. raising the `frequencies_ghz` ceiling to
  admit millimetre-wave work changes the unit guard's margin).
- **v1 documents remain readable forever.** A validator for v1 is never deleted when v2
  lands; it is kept so old run records stay interpretable.

## Results

All results reproduced on Python 3.12.15, jsonschema 4.26.0, from `/workspace`.

**The example validates (J4).**

```
$ python3 tools/host/validate-job-schema.py
OK /workspace/schemas/examples/microstrip_stub.job.json: valid against /workspace/schemas/emfit.job.v1.schema.json
cross-check: jsonschema agrees — this validator says valid, jsonschema says valid (0 error(s))
EXIT=0
```

**The three mutations are each rejected at the exact pointer (J6).**

```
$ python3 tools/host/validate-job-schema.py schemas/emfit.job.v1.schema.json .scratch/m1_missing_h.job.json
FAIL .scratch/m1_missing_h.job.json: 1 error(s)
  /materials: required property 'substrate_h_mm' is missing
EXIT=1

$ python3 tools/host/validate-job-schema.py schemas/emfit.job.v1.schema.json .scratch/m2_extra_seed.job.json
FAIL .scratch/m2_extra_seed.job.json: 1 error(s)
  /seed: unexpected property 'seed': the object is closed (additionalProperties is false)
EXIT=1

$ python3 tools/host/validate-job-schema.py schemas/emfit.job.v1.schema.json .scratch/m3_hz_not_ghz.job.json
FAIL .scratch/m3_hz_not_ghz.job.json: 1 error(s)
  /frequencies_ghz/0: 5000000000.0 is greater than the maximum 1000.0
EXIT=1
```

Each mutation is JSON-valid — the failure is a schema failure, not a syntax failure — so the
rejection is attributable to the constraint under test and not to a broken fixture.

**Malformed input is distinguished from invalid input.**

```
$ python3 tools/host/validate-job-schema.py schemas/emfit.job.v1.schema.json .scratch/malformed.job.json
FAIL .scratch/malformed.job.json: the instance at .scratch/malformed.job.json is not valid JSON: Expecting property name enclosed in double quotes: line 2 column 1 (char 28)
EXIT=2
```

Exit 2 is reserved for "could not check" (unparseable instance, unsupported keyword, missing
schema); exit 1 means "checked, and it is wrong". A caller can therefore tell "your document
is bad" from "my checker is bad".

**Keyword inventory.** `--list-keywords` reports 21 distinct keywords, **0 unsupported**, of
which 15 are implemented, 6 annotation-only (`$id`, `$schema`, `description`, `title`, and
their kin), and none are silently ignored. The fail-closed path — an unimplemented keyword
causes exit 2 rather than a false "valid" — is the reason this count matters: a validator
that ignores what it does not understand can certify anything.

**Stdlib-only (J5).** Module-level imports are `argparse, json, os, re, sys`. `jsonschema`
is imported lazily inside the cross-check (`:402`) and its absence downgrades the output to
`cross-check: NOT PERFORMED` without changing the verdict. Exit codes are identical under
`python3 -S` (0 / 1 / 1 / 1).

## What this document does not decide

- **Whether a frequency list is a set or a sweep.** `emfit.job.v1` never says. The schema
  chose `uniqueItems: true`, i.e. set semantics, because the tool's interior is a single
  `f_target` and a sweep would need power levels and a per-point provenance record that v1
  has no place for. This is a choice, not a finding.
- **Whether the tolerance is global or per-observable.** v1 states one number and thereby
  inherits the `decisions.md:7089` defect. The fix is a v2 field, not a v1 clarification.
- **What provenance a run emits.** Nothing here. `decisions.md:7091` flags the sketched
  provenance as FDTD-shaped; a v1 provenance schema would freeze that defect.
- **Whether a job can request a load.** It cannot. This is why the example is UNLOADED and
  cannot reproduce `demo_microstrip_stub`.
- **Whether the geometry is board-shaped.** `decisions.md:7093` records that the sketched
  geometry is board-shaped, i.e. assumes a PCB. The `geometry` `oneOf` admits a parametric
  branch that does not name a board, but it does not settle the question.
- **How a reader tolerates unknown fields.** The schema is closed; the tolerance policy
  belongs to whatever reading code eventually exists (`decisions.md:7063`).
- **Whether v1 is stable.** `decisions.md:7083` says stability arrives after M3c. This
  document is written before that; its own status banner says so.
- **Anything about the solver.** No time step, no step count, no PML thickness, no port
  treatment. Those are implementation, and v1 describes a request, not a run.
