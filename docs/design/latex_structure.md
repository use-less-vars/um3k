## 1. The reader, stated once

The reader is a numerically literate engineer who is taking this pipeline over: comfortable with Maxwell's
equations, finite differences and a sparse solve, unfamiliar with this codebase, and short of time. Every
consequence follows from that one sentence. Derivations that exist to display the author's understanding are
forbidden -- if a relation is standard, it is stated and cited, not derived. A chapter that exists to show work
already recorded in `decisions.md` is forbidden; so is prose that restates the decision log, because the log is
the record and a paraphrase is a second, weaker copy. Every quantitative claim must be traceable to a run
artefact or a test the reader can open. And every chapter ends by saying what the reader can now do or check,
in one or two sentences, with the artefact named.

## 2. The test a chapter must pass

A chapter is worth its pages if a reader with the background of §1, after one sitting of at most twenty minutes,
can do three things. (i) State the chapter's object in one sentence without looking back -- the thing the
chapter is about, not the list of its sections. (ii) Reproduce or check the chapter's central number or claim
from something in the repository: a script under `examples/`, a test, a dumped record, a closed-form value
computed independently. (iii) Name one thing that would make the claim false -- a mesh, a frequency, a
normalisation, a missing tolerance, an assumption that would break. A chapter whose central content survives
none of the three is failing, whatever its length.

The corollary is arithmetic, not taste. Length is not a virtue, and pages are not evidence: a six-page chapter
that passes beats thirty pages that fail. A failing chapter is cut or split; it is never padded, never given a
"for completeness" survey section, and never retained because deleting it would lose sentences that took work
to write. The work is in the log; the document is for the reader.

## 3. What exists today

All nineteen `.tex` files in `docs/report/` were opened this pass. `main.tex` includes eighteen section files by
`\input`; no section file includes anything itself; nothing is missing and nothing is orphaned.

| File | Lines | Included from `main.tex`? | What it is for | Verdict vs §2 |
|---|---|---|---|---|
| `main.tex` | 112 | root | Preamble (mathtools, `siunitx`, `booktabs`, `hyperref`, three `\newtheorem`s, material-matrix macros), the abstract, and the eighteen-entry `\input` list in reading order. | keep; the `\input` order is the only structural artefact in the repo |
| `sec_intro.tex` | 171 | yes, first | Aims and scope: what the tool is for, why FIT, and an explicit "working today / measured accuracy / not implemented" inventory with numbers (348 tests, 1.213 % mean cavity error, 7.8 % `eps_eff` bias, dense path refusing >3000 free edges). | keep-and-cut: keep §"Implemented and not yet implemented" as the spine of ch. 01; the "why FIT" motivation is textbook material |
| `sec_howitworks.tex` | 780 | yes | The tour: bricks, edge-versus-face unknowns, the ±1/0 curl matrix, leapfrog, materials, sources, walls, ports -- explicitly "no derivation here". | split: §bricks–§curl into ch. 03, §ports into ch. 08, the rest absorbed where it is used |
| `sec_theory.tex` | 340 | yes | The formal FIT statement: cell complexes, DoF as integrals, topological operators, Maxwell grid equations, Hodge stars, boundary conditions and sources, relation to Yee. | merge: operators into ch. 03, grid equations and stars into ch. 04 |
| `sec_energy.tex` | 271 | yes | The leapfrog update as implemented, the quadratic form actually preserved (not the obvious one), measured drift, the CFL bound, and numerical dispersion. | keep → ch. 04 |
| `sec_eigen.tex` | 383 | yes | The cavity eigenproblem, the static-eigenvalue cut that removes the gradient null space, the dense solve and its refusal, the spectrum of a box, convergence under refinement, and what was rejected. | keep → ch. 05 |
| `sec_impl.tex` | 297 | yes | The module map with per-file line counts, data layout and sparse operators, one reproduced worked example, the browser front end, and the test inventory. | split: example and front end into ch. 02; the line-count table cut to the modules a reader must touch; test inventory becomes a back-matter table |
| `sec_tline.tex` | 505 | yes | Textbook transmission-line material, declared "settled material ... nothing in this section is a claim about the solver". | merge-and-cut → ch. 09, cut to the identities the later chapters actually invoke |
| `sec_sparams.tex` | 472 | yes | Power waves, the definition of S, matched termination, S11 as an impedance, reciprocity/losslessness/passivity, the reference impedance, reference planes, power flow, Touchstone. | keep-and-cut → ch. 07; the power-flow order-of-magnitude subsection is the cut |
| `sec_smith.tex` | 361 | yes | The bilinear map, the two circle families, the passive disc, rotation, VSWR, two matching constructions, bandwidth, one worked example -- stated without figures because the preamble has no drawing package. | drop as a chapter: the worked example survives as a section of ch. 09 |
| `sec_microstrip.tex` | 296 | yes | The measurement vocabulary for one printed line: quasi-TEM cost, three impedances, de-embedding, five estimators of one attenuation, the acceptance criterion, the accounting identity. | keep → ch. 10 |
| `sec_microstrip_res.tex` | 624 | yes | All numbers from one `npml=10` audit run: the reference box, three impedances on one record, four rates, where the power went, the acceptance outcome, the import comparison, passivity bin by bin, the figures. | keep-and-cut → ch. 11; the bin-by-bin passivity block moves to ch. 08 where the port is built |
| `sec_method.tex` | 349 | yes | The rules of evidence, each illustrated by a break of itself: provenance, no fit as measurement, no self-oracle, stability ≠ accuracy, tolerances need pairs, discard windows, diagnostics stay diagnostics. | keep-and-cut → ch. 14 (rules half) |
| `sec_worked.tex` | 349 | yes | The ledger: four quantities sorted into quotable / diagnostic-only / withdrawn / withdrawn-pending, values printed as the records give them. | keep-and-cut → ch. 14 (ledger half) |
| `sec_loads.tex` | 383 | yes | Lumped elements at a transverse cut: what a cut means numerically, the series branch against a load-free run (passes), the shunt branch (fails, reported as an envelope). | keep → ch. 12 |
| `sec_results.tex` | 626 | yes | Output evidence: ring-down spectrum, field, energy in one run, time-domain checks, absorbing condition, the matched lossy layer, scattering/near-to-far/RCS, and a closing "what this establishes". | split: §§1–4 into ch. 04/05 as the time-domain evidence; §§5–7 into ch. 13; §"what this establishes" is the closing paragraph of ch. 13 |
| `sec_openproblem.tex` | 191 | yes, second to last | The 8 % passivity excess on a graded mesh: the observation, what it is not, four rivals, the registered test and its admission, what to check first; every number carries a `decisions.md` line. | keep → ch. 15 |
| `sec_outlook.tex` | 148 | yes | Milestones M0–M6 with status, open problems, scope. | merge into ch. 01 as the "what is planned and who owns the absence" block |
| `sec_glossary.tex` | 198 | yes, last | A flat `description` list fixing one sense per term and pointing at the defining and the measuring section; no subsections. | drop as a chapter -- it can carry no test; kept as unnumbered back matter |

The pattern is not a scattering of faults; it is one shape repeated. The document is 6,792 source lines and 105
pages, and a third of it sits in three files -- `sec_howitworks` (780), `sec_results` (626),
`sec_microstrip_res` (624) -- which are the files with the most numbers, so the chapters carrying evidence are
also the chapters carrying tour, restatement and figure commentary. Every one of the eighteen sections opens
with the same italic status banner, which is an honest device and also the report's main hedge: a reader is
told, eighteen times, how much of what follows to believe, instead of being told once which numbers are
quotable. Figure density is inverted against need: nine `includegraphics` calls in two files, none in the
fifteen chapters that ask the reader to believe a number. And the machinery that produces the report's most
quoted quantity -- the modal port -- is described in four lines of prose and a figure caption in
`sec_howitworks` (lines 683–687), while `sec_intro` declares waveguide ports and S-parameters unavailable;
chapters 11 and 15 then quote `|S11|` and `|S21|` at seven significant figures. The report therefore reads as if
its numbers come from nowhere.

## 4. What the document is missing

**An opening chapter on what the tool does and does not do -- needed, and it exists only as an embryo.**
`sec_intro` already contains the inventory (working today, measured accuracy, absorbing boundaries in part,
layout import in part, not implemented), which is exactly the right material in the wrong container: it is
buried at line 81 of an "Aims and scope" chapter whose first 80 lines are motivation. The reader of §1 needs
the limit statement before anything else, including the honest limits that are currently only visible by
cross-reading three files: the dense path refusing more than 3000 free edges, `Sigma_s` assembled but not
coupled into the step, no non-orthogonal grid, the near-to-far agreement "not reached". Without this chapter
the reader cannot tell a bug from a declared absence, and every later chapter inherits the ambiguity.

**A chapter on what a mode is in this solver and how it is extracted -- needed, and it is the largest hole.**
The word "mode" appears 178 times across the report, but almost all of it is the quasi-TEM microstrip mode of
chapters 10–11. The object the code actually computes -- a transverse eigenproblem on a two-dimensional
cross-section, a mode selected from a spectrum, a profile normalised, a coefficient kept and the rest discarded
-- is stated nowhere except the four lines at `sec_howitworks:683` and the caption of
`fig:hiw:modalport`. Meanwhile `emfit/mode2d.py` and `emfit/modalport.py` exist and are the modules that
produce every S-parameter the report quotes. A reader cannot check a port number without knowing which
normalisation the profile carries and which quantity is fixed by which; that is precisely the content a
structure document must reserve a chapter for, and it is the one chapter in §5 that cannot be assembled from
existing text.

**A chapter on which numbers may be quoted -- needed, but not as new writing.** `sec_method` and `sec_worked`
already are a trust chapter: the rules of evidence and the ledger that sorts four quantities into quotable,
diagnostic-only, withdrawn and withdrawn-pending. The gap is placement and consolidation, not content. Today
the reader meets the rules at 4,000 lines in, after the numbers they govern, and the honest verdicts live in a
chapter that the abstract does not point at. Merged into one chapter, placed after the number-bearing chapters
and pointed at from chapter 01, this material answers the "may I quote this?" question that no other chapter
answers.

**A chapter on how to run the tool and read its output -- needed, and it is currently a subsection of the
implementation chapter.** `sec_impl` has one reproduced example and a front-end section that documents
`python -m emfit serve`; `pyproject.toml` declares no console script, and nothing in the report says what lands
on disk or how to read it. The reader of §1 who wants to run something must currently reverse-engineer the
studies. This is the cheapest gap to close and the one that most changes whether the report is used.

**A reference chapter of formulae -- not needed.** The definitions the code actually uses are already where
they are used: the operators and their two identities in `sec_theory`, the preserved quadratic form and the
CFL bound in `sec_energy`, the S-parameter conventions in `sec_sparams`, the attenuation identities in
`sec_microstrip`. A separate formula sheet would be a second copy of those statements, it would drift from them
at the first revision, and it would fail §2 on its own: it has no central claim to reproduce and nothing that
could make it false. The glossary, kept as unnumbered back matter, is the correct amount of reference material
-- it fixes one sense per term and points at the section that governs.

Nothing else is missing at chapter level. In particular a chapter on the package architecture is not needed:
`docs/architecture.md` (92 lines) is the right place for it, and the only architectural facts a report reader
needs -- where the operators live, how the unknowns are numbered, how the conductor constraint is expressed --
are already the content of chapters 02 and 03.

## 5. Proposed chapter list

Fifteen chapters, one above the 8–14 band: chapter 15 is the only place the document carries a live,
uncorrected defect with record-level citations, and folding it into 14 would bury it inside a rules chapter.

- **01. Status: what the tool does, what it does not, and what is planned**
- *Reader:* an engineer deciding in ten minutes whether this repository can answer their question.
- *Object:* the capability and limit statement -- the working path, the measured accuracy, the three partial capabilities, the not-implemented list, and the milestone that owns each absence.
- *Test:* the reader locates the refusal threshold (dense path, more than 3000 free edges) and the `eps_eff` bias (7.8 per cent) in the text, then matches each to `emfit/eigen.py` and `docs/roadmap.md`.
- *Depends on:* none.

- **02. Running it, and reading what comes out**
- *Reader:* the engineer who has decided to use the tool and has thirty minutes.
- *Object:* invocation (`python -m emfit run <study> --out <dir>`, `python -m emfit serve`), the record written to disk with its fields, the figures, and which module owns each study.
- *Test:* the reader runs one study to a directory, names three fields of the `.npz` it wrote, and points at the line of code that wrote each.
- *Depends on:* 01.

- **03. The discrete system: bricks, unknowns, the curl, and the material stars**
- *Reader:* anyone who will change the grid, the operators or the material layer.
- *Object:* the tensor-product grid, primal and dual unknowns as integrals, the incidence matrices with `C G = 0` and `S C = 0` exact, the diagonal Hodge stars, PEC as a constraint on the unknown vector, and the free-edge counts.
- *Test:* the reader checks `C G = 0` on a small grid against a hand-written stencil and reconciles the free-edge count with the 216 (coarse) / 702 (fine) pair quoted for the cavity.
- *Depends on:* 01.

- **04. Time stepping: the update, the energy identity, and the two limits**
- *Reader:* anyone who will choose a time step or a run length.
- *Object:* the leapfrog update as implemented, the mixed-state quadratic form it preserves, the measured drift, the stability bound set by the smallest cell, and the numerical dispersion of a wavefront.
- *Test:* the reader reproduces the drift of `8.5e-16` relative over 1800 steps and the stability edge (stable at 1.01× the limit, divergent at 1.02×) from `tests/test_energy.py`.
- *Depends on:* 03.

- **05. Cavity resonances: the eigenproblem, the null space, and convergence**
- *Reader:* anyone who will quote a resonance frequency or judge a mesh by it.
- *Object:* the generalised eigenproblem, the static-eigenvalue cut that removes the gradient null space, the dense solve and its refusal, and the convergence of the spectrum under refinement.
- *Test:* the reader checks the mean error falling 1.213 % → 0.615 % and the ratio 0.507 against the 0.510 predicted for the 1.4× refinement, using `examples/cavity_resonance.py`.
- *Depends on:* 03, 04.

- **06. What a mode is here, and how it is extracted**
- *Reader:* anyone who will build, or trust, a port.
- *Object:* the transverse eigenproblem on a two-dimensional cross-section, how one mode is selected from the computed spectrum, what the field normalisation is, and which quantity is fixed by which.
- *Test:* the reader extracts a mode from the reference-box cross-section with `emfit/mode2d.py` and `emfit/modalport.py`, states which components carry the normalisation, and checks the resulting `eps_eff` against the 7.8 per cent bias that chapter 11 reports.
- *Depends on:* 03, 04.

- **07. Scattering parameters, and the reference impedance that is part of the number**
- *Reader:* anyone who will compare a computed S-matrix with a datasheet or a bench measurement.
- *Object:* power waves, the definition of S, a matched termination, reciprocity/losslessness/passivity, reference-plane rotation, and the Touchstone file as the interchange format.
- *Test:* the reader renormalises one `S11` from 50 Ω to 75 Ω by hand and matches the report's formula to `1e-3`.
- *Depends on:* 06.

- **08. Ports: from a transverse mode to a number**
- *Reader:* anyone reading an S-parameter this tool produced.
- *Object:* the modal port as a projection onto a known profile, what keeping one coefficient discards, the pair of ports that turns a field record into `S11` and `S21`, and the bin-by-bin passivity check that follows.
- *Test:* the reader takes `board_cw_7.8333GHz.npz`, reproduces `|S11| = 0.013677` and `|S21| = 1.039055` at 7.833566 GHz, and obtains `|S11|^2 + |S21|^2 = 1.079823`.
- *Depends on:* 06, 07.

- **09. The line identities this report uses, and the chart**
- *Reader:* anyone who needs the quarter-wave, half-wave or rotation relation a later chapter invokes.
- *Object:* the telegrapher's equations and their lossless solution, the reflection coefficient and the `lambda_g/2` ripple, the quarter- and half-wave identities, the rotation law, and one worked chart example done in algebra.
- *Test:* the reader checks the quarter-wave identity on the report's own `Z_L = 25 + j25 Ω` example to `1e-3` and states the frequency band in which the quasi-TEM picture it rests on fails.
- *Depends on:* 07.

- **10. The microstrip line: what a measurement of it can mean**
- *Reader:* anyone who will quote a number about a printed line.
- *Object:* the cost of the quasi-TEM assumption, which of the three impedances called `Z_0` is meant, de-embedding, five estimators of one attenuation, the acceptance criterion and its resolution, and the accounting identity.
- *Test:* the reader names the `Z_0` convention used by chapter 11 and shows which of the five estimators the acceptance criterion can resolve at the stated resolution, and which it cannot.
- *Depends on:* 06, 07, 09.

- **11. The reference box: what one record measures**
- *Reader:* anyone auditing a quoted board number.
- *Object:* one geometry stated once (`w = 3.20` mm, `h = 1.60` mm, `w/h = 2.000`, `eps_r = 4.4`, `66×52×26` cells of 0.400 mm), the four rates for one attenuation, where the power went, the acceptance outcome, and the import comparison.
- *Test:* the reader recomputes one of the four rates from `.scratch/study_dump.txt` and reaches the same pair of printed values for the one quantity the record carries twice -- without averaging them.
- *Depends on:* 10.

- **12. Lumped elements at a transverse cut**
- *Reader:* anyone who will put an element in the mesh and read its effect.
- *Object:* what a cut means numerically, the series branch evaluated against a load-free run of the same line, and the shunt branch reported as an envelope that says how far it gets.
- *Test:* the reader checks the series resistance against the load-free run and states the margin by which the shunt capacitance misses the value the mesh was asked to inject.
- *Depends on:* 11.

- **13. Open boundaries: the one-way condition, the lossy layer, and the far field**
- *Reader:* anyone who needs a wave to leave the domain.
- *Object:* the first-order absorbing condition and its measured reflection at normal incidence, the matched lossy layer and the acceptance criterion it fails, and the near-to-far transform set against a Mie series.
- *Test:* the reader checks the "about −50 dB" reflection against `examples/abc_duct.py` and names which acceptance criterion is unmet and by how much the Mie comparison falls short.
- *Depends on:* 04, 05.

- **14. Which numbers may be quoted: the rules and the ledger**
- *Reader:* anyone about to quote this report.
- *Object:* the rules of evidence, each stated with the break that produced it, and the ledger that applies them -- quotable, diagnostic only, withdrawn, withdrawn pending.
- *Test:* the reader follows each of the four ledger entries to its cited record, and states the one sentence about that quantity the entry still supports.
- *Depends on:* 11, 12, 13.

- **15. One open problem: an 8 per cent passivity excess**
- *Reader:* whoever picks up the remaining work.
- *Object:* the observation, what it is not, four rival explanations, the test that was registered and what was admitted about it, and what to check first.
- *Test:* the reader rebuilds `1.079823` from the two magnitudes, finds the same excess at the `decisions.md` line the text cites, and says which of the four rivals the registered test would separate.
- *Depends on:* 08, 11, 14.

## 6. Order and depth

| Chapter | Target pages | Why that depth |
|---|---|---|
| 01 Status | 3 | A decision, not an argument: it exists so the reader can stop reading or start trusting. |
| 02 Running it | 4 | Enough to run one study and read one record; every further page is a page `--help` and the code already serve. |
| 03 The discrete system | 9 | The chapter every other chapter cites; the two exactnesses must be shown on a small grid, not listed. |
| 04 Time stepping | 7 | One identity and two limits, each with a number attached; the dispersion derivation is stated and cited, not re-derived. |
| 05 Cavity resonances | 8 | The null space is the one place the eigenproblem can lie silently; the convergence table is the chapter's whole evidence. |
| 06 Modes | 7 | New, and short by design: it owes the reader one thing -- what a mode is and where the normalisation sits. |
| 07 S-parameters | 6 | Cut from 472 source lines to the conventions later chapters use; the passivity algebra is the floor. |
| 08 Ports | 5 | One record, one arithmetic chain, one passivity check; longer would be padding. |
| 09 Line identities and chart | 5 | Identities plus one worked example; no chart figures, because the preamble has no drawing package. |
| 10 Microstrip | 8 | The vocabulary chapter: it must be complete before chapter 11 quotes anything. |
| 11 Reference box | 10 | The largest evidence block and the only place two reductions of one capture are compared side by side. |
| 12 Lumped elements | 6 | One pass and one failure, each stated as such; the shunt envelope is the point, not a caveat. |
| 13 Open boundaries | 8 | Three capabilities, one unmet criterion; the lossy-layer subsection halves once the tuning narrative goes. |
| 14 Rules and ledger | 7 | Rules short, ledger longer: the four entries carry their own length and their own citations. |
| 15 Open problem | 4 | A problem statement with a priced test and no result; anything longer would be speculation. |
| Back matter | 4 | Glossary (3) kept unnumbered, plus the test inventory as one table (1). |

The arithmetic is the argument: 89 pages of chapters plus 4 of back matter against 105 today, with two chapters
added -- which means roughly twenty pages of existing text is cut, and the cut is named file by file in §3.

Three reading paths, each of which must work without reading the others. *Linear*: 01 → 15, which is the order
of the table and the order of `main.tex`. *"I just want to run it"*: 01 for the limits, 02 for the invocation
and the record, then straight to the chapter of the study at hand (05, 11, 13) -- nothing on this path requires
the theory chapters, and no cross-reference on it may point into 03 or 04 for something essential. *"I need to
know whether to trust this number"*: the chapter that prints the number, then 14 for the rule that sorts it,
then the record the chapter cites. The third path is the reason 14 must come after 11, 12 and 13 and the reason
chapter 01 must name it: the reader arrives at a number before they arrive at the rules, so the rules have to be
findable from the front.

## 7. What this pass deliberately did not decide

1. Whether `decisions.md` (7,067 lines) stays a separate artefact that chapters cite by line number, or is
   distilled into the chapters that use it. Chapter 15 currently binds the report to a file the report does not
   contain, and either answer changes how that chapter is written.
2. Whether chapter 02 documents the CLI, the web application, or both. `emfit/cli.py` and `emfit/webapp.py` both
   exist and `pyproject.toml` declares no console script, so the "how to run it" answer is currently a choice
   about which surface is the supported one.
3. Whether the trust material is chapter 14 as proposed, or a table of quotable numbers in the front matter with
   the rules kept short behind it.
4. Whether the glossary survives as unnumbered back matter or is dropped entirely; §3 rules it out as a chapter,
   not out of the document.
5. What chapter 06 may assert about the transverse-field normalisation -- whether it is stated as settled or
   recorded as open. That is a question about the code, not about the document, and this pass did not rule on it.
6. Whether the Smith chart material survives only as the worked example inside chapter 09, or is dropped whole.
7. Figure policy: nine `includegraphics` calls in two of eighteen files today, and no drawing package in the
   preamble. Whether new chapters may carry figures, or whether tables are the house form, is a decision about
   how the report argues, and it is not made here.
8. Whether every chapter keeps the italic "Status: draft/settled" banner that all eighteen files currently
   open with. It is the document's honesty device and also its main hedge, and the choice changes the register
   of every chapter.
9. How chapter 01 words port availability. It currently declares waveguide ports and S-parameters unavailable
   while chapters 11 and 15 quote `|S11|` and `|S21|` to seven figures; whether 01 states availability per port
   kind, or restates the limitation differently, is the operator's call.
10. Whether 89 + 4 pages is a cap or an estimate produced by the page-per-claim arithmetic of §2.
