# Anchor: pre-registered run against the 2D mode solver

## 1. Status

The run produced NO verdict. It terminated because the pre-registered driven path cannot return the physical modes at the finer meshes.

This is a failure to measure rather than a measurement that failed, and the distinction is load-bearing: the instrument did not disagree with the pre-registration, it stopped being able to see the thing the pre-registration asked it to see. Nothing here contradicts the anchor hypothesis; nothing here supports it either.

Commit SHAs:

- pre-registration / dispatch commit: `UNASSIGNED`, to be filled at commit time
- results commit: `UNASSIGNED`, to be filled at commit time

## 2. Provenance and integrity record

Pre-registration v1:

- sha256 `3293f0393f1d48b69ccea5a0ad15f6a73f4f2150664c8abb781934e8fbf86532`
- 873 lines
- 43839 bytes

Pre-registration v2 (whole file):

- sha256 `9461e5c4c631cb934d37b7b69b50ebff7ed9eadffe9740b6b3e50c353f0648f2`
- 1028 lines
- 51809 bytes

`head -c 43839 <v2 file> | sha256sum` still returns the v1 hash. That proves v1 is an unmodified byte prefix of v2: the amendment appended to the frozen text rather than editing it. The file contains zero non-ASCII lines.

Ordering evidence, as modified timestamps, all on the same date and the same clock:

| artefact | mtime |
|---|---|
| `docs/design/anchor_preregistration.md` | 17:20:32.883 |
| `tools/host/anchor/ladder.py` | 17:21:54.151 |
| `tools/host/anchor/records/level1.json` | 17:21:58.159 |
| `tools/host/anchor/records/level2.json` | 17:21:58.864 |
| `tools/host/anchor/records/level3.json` | 17:22:31.545 |

The amendment precedes the earliest ladder result by 85.276 seconds, so no ladder number existed when it was written.

## 3. The analytic reference is correct

The reference routine reproduces the document's three roots. Worst relative difference 1.204e-16 against a stated limit of 1e-14, arising at the third root only; the first two reproduce bit for bit.

The three analytic betas are:

| order | beta | effective permittivity |
|---|---|---|
| 1 | 1637.9985692980779 | 1.3544758398156966 |
| 2 | 1296.2992799512633 | 0.8483103899760305 |
| 3 | 944.6029788248537 | 0.4504461177372278 |

The `eps_r = 1` self-check returns agreement of 1.568e-16 against the closed form.

The dispersion term scales and relative residuals reproduce the document's own residual table digit for digit, which is the evidence that the transcription is the document's code rather than a lookalike.

## 4. A defect in the printed reference code

The root-finder as printed in the document returns six roots rather than three. The three extras are the poles of the dispersion relation, at 911.579303003, 1172.382440722 and 1301.305505138.

The scan cut points are grid endpoints where the residual is of order 1e19 with a rounding-decided sign, which manufactures a bracket in the end cell; the two-resolution count-agreement guard cannot detect this because the artefact is the end cell at both resolutions.

The repair accepts a refined root only if the term scale there is below 1e9: the genuine roots sit at or below 7.8e3 and the poles at or above 3.8e16, which is nine decades of margin. No reference value changes. Rejected brackets are printed rather than dropped.

## 5. The v1 filter was unsatisfiable, which is why there is a v2

The level-1 evidence. Sixteen candidates contained eleven gradient states at effective permittivity equal to one and beta equal to k0. Their absolute curl ratio spanned 1.1e-12 to 4.0e-10, straddling the frozen 1e-10 cut. The cut therefore divided one round-off population rather than separating two populations, and the seven-decade requirement was then asked to hold between the two halves of that single population. The measured separation was minus 0.36 decades.

Stated plainly: the rule as frozen could not be satisfied by any threshold placed in that noise band.

The structural gap does exist, and is unambiguous: every state carrying structure sits at or above 4.31e4 and every gradient state at or below 4.02e-10, about fourteen decades.

The consequence. A non-gradient spurious state at beta 1736.2570207159, effective permittivity 1.5218514287, curl 4.31e4, sorted above the fundamental and displaced the entire by-order match, and the genuine third mode at beta 952.9911948313 was dropped.

## 6. The v2 amendment, and one erratum in it

What v2 changed:

- it froze the shift at 0.5 times k0 squared;
- it replaced curl-ratio thresholding with a structural test on effective permittivity;
- it retained a separation guard;
- it added surplus reporting.

No acceptance threshold changed: the order band 1.7 to 2.3, the absolute bound 2.0e-3 at the finest level, monotonicity, the requested candidate count of 16, the ladder geometry and the material parameters are all as frozen in v1.

The ERRATUM. The separation guard in the v2 text is written as the base-10 logarithm of D over R, with D the largest absolute curl ratio over the dropped set and R the smallest over the retained set. Since the dropped set is the low-curl population, this expression is necessarily negative and the stored boolean is therefore always false. The intended comparison is R over D. Measured the intended way the separations are 14.21, 14.47 and 13.77 decades at levels one, two and three, against a six-decade requirement.

The erratum is recorded here and the frozen amendment is deliberately not edited, so that a reader comparing the two documents sees one freeze and one correction rather than a document quietly rewritten to agree with its results.

## 7. What the three completed levels contain

### Level 1

ny 16, nx 2, h 0.00048828125, free degrees of freedom 78, solver wall time 0.0217 s, peak memory 77.22 MB. Retained five of sixteen, dropped eleven. Largest dropped absolute curl 2.6791731109636385e-10, smallest retained 43125.805495970926.

| index | beta | effective permittivity | absolute curl ratio | status |
|---|---|---|---|---|
| 0 | 1736.2570207158685 | 1.5218514286533689 | 43125.805495970926 | retained |
| 1 | 1636.5986739978343 | 1.3521616569484933 | 785938.0820841311 | retained |
| 13 | 1296.9723776897456 | 0.8491915816227373 | 394355.4698929652 | retained |
| 14 | 952.9911948312771 | 0.4584816966495742 | 1282546.6726233843 | retained |
| 15 | negative square root | -0.09073579324957178 | 2511614.864733763 | retained |
| - | about 1407.4335088082 | within 7e-14 of 1 | 8.062809977508971e-11 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 1.5597863041551842e-10 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 8.954906737125078e-11 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 7.289663823913732e-11 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 5.606681334849376e-11 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 4.440540234007879e-11 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 3.5302376941387836e-11 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 9.350709576752479e-11 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 2.6791731109636385e-10 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 1.4366571542772984e-10 | dropped |
| - | about 1407.4335088082 | within 7e-14 of 1 | 2.2676322651385317e-10 | dropped |

The eleven dropped rows were supplied as the group description above (beta about 1407.4335088082, effective permittivity within 7e-14 of one) plus the eleven absolute curl values; individual per-row betas and effective permittivities were not supplied, and the rows above are listed in stored order with those values left as the group description rather than reconstructed.

By-order match at level 1:

| measured beta | reference beta | relative error |
|---|---|---|
| 1736.2570207158685 | 1637.9985692980779 | 5.998690e-02 |
| 1636.5986739978343 | 1296.2992799512633 | 2.625161e-01 |
| 1296.9723776897456 | 944.6029788248537 | 3.730344e-01 |

Surplus reported one, at index 14.

### Level 2

ny 32, nx 4, h 0.000244140625, free 348, wall time 0.7032 s, peak memory 77.72 MB. Retained two of sixteen, dropped fourteen, all dropped at beta 1407.4335088082 with effective permittivity within 1.4e-14 of one. Largest dropped absolute curl 1.3408753265465457e-09, smallest retained 393673.6817123007.

| index | beta | effective permittivity | absolute curl ratio | status |
|---|---|---|---|---|
| 14 | 1296.4632008496378 | 0.8485249462831824 | 393673.6817123007 | retained |
| 15 | 946.6516295409791 | 0.4524020875403645 | 1286133.3998208065 | retained |

The fourteen dropped rows are not tabulated. Count fourteen; beta 1407.4335088082; their absolute curl ratio runs from a minimum of 2.8747687804998776e-11 to a maximum of 1.3408753265465457e-09.

By-order match at level 2:

| measured beta | reference beta | relative error |
|---|---|---|
| 1296.4632008496378 | 1637.9985692980779 | 2.085077e-01 |
| 946.6516295409791 | 1296.2992799512633 | 2.697276e-01 |
| absent | 944.6029788248537 | - |

Note recorded: fewer than three retained, and section 5 forbids extrapolating missing modes.

### Level 3

ny 64, nx 8, h 0.0001220703125, free 1464, wall time 14.890 s, peak memory 79.28 MB. Retained two of sixteen, dropped fourteen at beta 1407.4335088082 with effective permittivity within 3.6e-14 of one. Largest dropped absolute curl 6.61052631017697e-09, smallest retained 393544.3492550656.

| index | beta | effective permittivity | absolute curl ratio | status |
|---|---|---|---|---|
| 14 | 1296.3400089040304 | 0.8483636976297834 | 393544.3492550656 | retained |
| 15 | 945.1123879493056 | 0.45093208536595036 | 1287190.535495436 | retained |

The fourteen dropped rows are not tabulated. Their absolute curl ratio runs from 2.579039201141767e-10 to 6.61052631017697e-09.

By-order match at level 3:

| measured beta | reference beta | relative error |
|---|---|---|
| 1296.3400089040304 | 1637.9985692980779 | 2.085829e-01 |
| 945.1123879493056 | 1296.2992799512633 | 2.709150e-01 |
| absent | 944.6029788248537 | - |

## 8. What could not be measured, and why

Levels four and five produced no numbers. Two attempts were made to compute level four and neither returned a result within the worker's time budget.

An earlier report attributed this to an ARPACK non-convergence exception at 60001 iterations with 10 of 16 eigenvectors converged. That attribution is UNVERIFIED: no traceback exists on disk, and the worker that reported it never ran the solver.

The two mixed-path and negative-control steps were NOT RUN, and they remain outstanding obligations.

The primary statistic, which combines the relative errors at levels three, four and five, therefore cannot be formed.

## 9. The mechanism: eigenpair starvation by the curl-free null space

This is the finding. The shift is at 990434.5408581193.

Distances from the shift:

| state | beta squared | distance from the shift |
|---|---|---|
| third analytic mode | 908192.2174259451 | 82242.3 |
| second analytic mode | 1682137.3484901919 | 691702.8 |
| gradient cluster | 1980869.08171624 | 990434.5 |
| first analytic mode | 2678455.2197314696 | 1688020.7 |
| spurious state | 3014588.4419851443 | 2024153.9 |

A shift-invert solver returns the eigenvalues nearest the shift. The gradient states form an exactly degenerate cluster at beta squared equal to k0 squared, and its multiplicity was 11 at level one and at least 14 at levels two and three, capped only by the requested count of 16.

Because every member of the cluster is nearer the shift than the fundamental, the cluster consumes the entire eigenpair budget, and the fundamental cannot be returned at any requested count the ladder can afford.

The multiplicity grows with mesh refinement because the curl-free subspace grows, so the starvation worsens at exactly the levels the anchor needs.

Raising the requested count or moving the shift cannot fix this, since the multiplicity is unbounded. The fix is to remove the curl-free subspace before the eigensolve, which is a solver change and not a pre-registration change.

## 10. An observation that is not a verdict

What follows is not the pre-registered statistic and cannot be promoted to one.

The value correspondence is unambiguous for the two modes that are returned.

Second analytic mode, relative errors at levels one, two and three: 5.192e-04, 1.2645e-04, 3.1420e-05. Successive ratios 4.106 and 4.024.

Third analytic mode, relative errors at levels one, two and three: 8.8801e-03, 2.1687e-03, 5.3928e-04. Successive ratios 4.0946 and 4.0215.

Base-two logarithms of the ratios are 2.038 and 2.009 for the second mode, 2.034 and 2.008 for the third, mean 2.02.

This apparent second-order convergence sits inside the pre-registered band. It is nevertheless not a pass, for three stated reasons:

1. it rests on value matching rather than the pre-registered by-order matching;
2. it omits the fundamental entirely;
3. it rests on three levels rather than five.

The correct reading is that the solver is probably converging at second order and the anchor as registered cannot demonstrate it.

## 11. Ruling and consequences

The anchor produces no verdict. The gate outcome is failed to measure, and the cause is named above.

Row four of the C++ criterion table remains unmeasured, and it now has a second named blocker in addition to the normalisation defect: the driven path cannot resolve the physical modes at fine meshes because the curl-free null space starves the eigenpair budget.

Proposing a corrected shift or a deflation step now, after seeing the convergence rates above, would be a re-registration informed by the result, and it is therefore deliberately not done here. It requires a fresh dispatch with its own openly dated amendment recording that the first attempt failed and why.

The observed rates being already inside the band means such a change could not buy a pass that is not already informally present, which is precisely why it must be made in the open.

## 12. What a reader can check independently

- that the v1 hash is still a prefix of the v2 file (`head -c 43839 <v2> | sha256sum` equals the v1 sha256);
- that the reference routine reproduces the three analytic roots to 1e-16 and reproduces the document's residual table;
- that `solve_modes` imported from the package is object-identical to the module attribute and resolves to the workspace file;
- that the free degree-of-freedom counts 78, 348, 1464 match the document's table;
- that the three JSON files contain the candidate lists transcribed in section 7;
- that the distances in section 9 follow by subtraction from the numbers given there.
