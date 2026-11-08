# Lessons learned on emfit

Six things this project got wrong, written for an engineer joining cold. Each
one cost real time, each one is still visible in the tree, and each one has a
rule that would have prevented it. The numbers are quoted as they are recorded
in the artefacts named beside them.

## L1 — Circular reasoning: the fit was checked against itself

**What happened.** The station-fit reflection `0.245` was treated as a biased
estimate of the load reflection and used to correct the port extraction. The fit
had been made *with* a two-wave decomposition whose `alpha` (11.255 Np/m) was
imposed rather than measured, so the "reference" being compared against was an
output of the same machinery under test. When the fit was re-run with `alpha`
free, the reflection came out 0.322297 and the 0.245 collapsed.

**What it cost.** Two sessions of analysis plus eleven retracted claims across
the passivity and port questions. Three scripts still bake the dead number in as
a reference constant (`read_s21_plane_sweep.py:34` `REF_S11 = 0.245108`,
`analyze_vi_forensics.py:36` `GAMMA_LIST = (0.245, 0.326)`,
`analyze_constrained_fit.py:70` `GAMMA_FREE_REFERENCE = 0.245`).

**The rule.** Only two measurements here are independent of the extraction
machinery: the port's own `|S11|`, and a direct voltage/current field
measurement at a known plane. Everything else is a consistency check between two
copies of the same model, and a consistency check cannot detect a shared error.
Before quoting a number as a reference, ask what produced it and whether that
producer is the thing under test. Provenance: `docs/design/upstream-extraction-2026-11-08.md:96-117`,
`docs/design/roadmap-next-2026-11-08.md:23`.

## L2 — The ruler was on the wrong side of the load

**What happened.** `|S11|^2 + |S21|^2` was reported above 1 and read as a
passivity violation. Extraction at the load's own column gives `|S21|` just
above 1.10; moving the measurement plane **one column past** the load drops it to
0.7617. A 45 percent drop from one cell of mesh is not physics: the plane was
sitting on the lumped element, and the recorded "forward" amplitude there
contains the element's own scattered near field, so the ratio was inflated.

**What it cost.** The passivity question was opened as a numerics bug, and the
explanation that survives is geometric — the measurement was downstream-adjacent
when it needed to be downstream. The plane-51 fix took two artefacts to isolate:
`build_A_50ohm_p50_plane.json` (`|S21|` 1.106043) against the plane-51 run
(`|S21|` 0.7617054231929281).

**The rule.** Before believing a physical violation, check where the probe is
relative to the discontinuity, and move it one cell to see whether the number
moves by a cell's worth or by a physics-worth. Provenance:
`docs/design/passivity-resolution-2026-11-09.md:84-98`.

## L3 — The same disease in the next package

**What happened.** `server/poc_app.py` needs the trame/pyvista/VTK stack, which
had been named as a single requirement. The real stack is split across `trame`,
`trame-vuetify`, `trame-pyvista` and `trame-vtk` plus `pyvista` and `vtk`, and a
partial install produces an import error from a package nobody had listed.
`requirements-web.txt` now names all six — but **with no version pins**, so the
fix is recommended, not in place: any future install can still drift.

**What it cost.** A debugging cycle on an import error whose cause was a missing
sibling package, in a container where the whole stack is absent anyway, so the
final state is "documented, still unexercised".

**The rule.** When a framework splits into satellite packages, enumerate the
satellites and pin them; an unpinned requirements file converts a solved problem
back into an open one on the next install. Say plainly whether the fix is in
place or only recommended. Provenance: `requirements-web.txt`,
`docs/design/web_ui_architecture_2026-11-08.md`.

## L4 — Stale constants outlive the fix that replaced them

**What happened.** The at-cut test line carried `0.118088` as its expected
`gamma_port`. It was re-measured and replaced: the assertion now reads
`0.1520918610341127` (`tests/test_studies.py:1667`), and the comment above it
(`:1662-1666`) records that the old figure was "a snapshot taken at 0545834 and
flagged UNVALIDATED in place: a regression pin — it says 'this number has not
moved', not 'this number is right'". The identical correction was applied to
`0.154492` -> `0.1510672` ("same provenance"). The old value is still present,
deliberately, in that comment and in `docs/design/dispatch_log.md:50`; it also
still appears as an unexplained mismatch in
`docs/design/roadmap-next-2026-11-08.md:296-299` ("Two pre-existing failures …
Neither is explained").

**What it cost.** One confusion cycle per reader who greps `0.118088` and finds
it in four places, only one of which is the live expectation.

**The rule.** A regression pin is a statement about drift, not about physics, and
must be labelled as one at the point of use. When a constant is re-measured,
update the assertion, keep the old value only in a dated comment or a dispatch
row that says why it is still there, and never let a stale pin be read as a
target. Provenance: `tests/test_studies.py:1662-1667`,
`docs/design/dispatch_log.md:50`.

## L5 — The agent cannot see images

**What happened.** Figures were produced and referred to by filename in reports
and reviews. Neither the agent nor a terminal reader can open a PNG, so
"see Figure 3" is an assertion with no reader: the figure's content cannot be
checked, quoted, or contradicted by anyone downstream, and a wrong plot survives
review indefinitely.

**What it cost.** Several review cycles in which a figure's claim was accepted
because it was pictured, not because it was numeric.

**The rule.** Every figure must have the array or table behind it committed
beside it, in text, in the same directory — the numbers are the evidence and the
image is decoration. If a claim can only be made visually, it is not yet
checkable.

## L6 — One ULP is not a universal liveness test

**What happened.** The v1 golden's non-vacuity control was a single-ULP bump of
`h0[0]` (1.1102230246251565e-16), which moved `max |e - golden|` to
8.6153306710912148e-14 after one step and 5.6843418860808015e-13 after three.
That worked because `|e|` there is about 1. On the v2 full-physics golden `|e|`
is about 1e3, so the absolute rounding floor is about 1e-13 and the same bump is
**absorbed**: `h0[0] + 1 ULP` gives a bit-identical three-step output, `+2 ULP`
moves `h3` by 7.2e-35, and `e0[0]` needs `+1024 ULP` before anything changes at
all (2.8e-17).

**What it cost.** One round of "the test looks vacuous" on a test that was not
vacuous — the control had silently stopped controlling, which is worse than
having no control, because a green run looked like it had been probed.

**The rule.** Put the ULP control on the **output** side (bump a stored output
by one ULP and assert the comparator raises and localises it), and make the
input-side liveness control a coarse relative perturbation (1e-3 on the largest
entry), which does reach the output regardless of scale. Say in the test why
each control is the size it is. Provenance:
`docs/design/cpp-kernel-status-2026-11-09.md` sections 6.3-6.4.
