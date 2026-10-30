# D58.5 — pre-registration: H ladder (transverse box clearance)

PURPOSE. Decide whether the FDTD propagation constant beta is converged in mesh size h at the box that the clearance sweep validated (3.0H), and measure the observed order p. Written and committed in advance so that the outcome cannot be reinterpreted after the fact. NOTHING below has been run.

REFERENCE STATE (measured, Task 1, h=0.2mm, nx=104, stations 40..70, n_acc=2096, ny x nz = 60 x 36, 224640 cells, 65.9 s wall):
  beta(h=0.2) = 381.1589 /m short-window; 380.5 +- 0.6 /m long-window (>=2 guide wavelengths, Task 2)
  alpha(h=0.2) = 5.83772 /m
  eps_eff = (beta/k0)^2 = 3.290 with k0 = 209.78 /m;  beta_bound = k0*sqrt(er) = 440.048305 /m
  Hammerstad quasi-static: beta 365 /m, eps_eff 3.04 (W/H = 0.5)
  Measured modal quasi-TEM (deflated, open closure, cl=1.0): 364.794 /m at H/h=8 rising monotonically to 365.457 /m at H/h=13.

LADDER (FDTD, cl = 3.0H fixed, h is the only variable). nx scales as 1/h so the physical station window is unchanged.
  rung | h (mm) | H/h | nx  | ny x nz | cells   | predicted wall | status
  R0   | 0.4     | 4   | 52  | 30 x 18 | 28080   | ~4 s           | not run
  R1   | 0.2667  | 6   | 78  | 45 x 27 | 94770   | ~13 s          | not run
  R2   | 0.2     | 8   | 104 | 60 x 36 | 224640  | 65.9 s MEASURED| ALREADY RUN (Task 1)
  R3   | 0.16    | 10  | 130 | 75 x 45 | 438750  | ~161 s         | not run
  R4   | 0.1333  | 12  | 156 | 90 x 54 | 758160  | ~334 s         | not run
Wall model: cells ~ h^-3 (nx ~ 1/h, ny,nz ~ 1/h each) and wall ~ cells^1.33 => wall ~ h^-4, calibrated on R2. Scaling constants: from 65.9 s at h=0.2.

PREDICTIONS (falsifiable, stated before the run):
  P1 beta increases OR decreases monotonically with refinement and |beta(R4) - beta(R3)|/beta < 0.5%.
  P2 extrapolated beta_0 stays <= beta_bound = 440.048 /m with margin >= 8% (Task 1 gave 13.4% at h=0.2).
  P3 observed order p in 1.5..2.5 (second-order scheme). p outside 1..3 is an anomaly to be reported as such, NOT re-fitted with a different model.
  P4 alpha is NOT converged in h (it is a transverse-box artifact, Task 1/2) and must be reported per rung with NO acceptance gate attached.

ACCEPTANCE CRITERIA (all must be stated as pass/fail verbatim in the report):
  A1 CONVERGENCE: |beta(R4) - beta(R3)| / beta(R3) < 0.5%  => "beta converged in h".
  A2 ORDER: 1.5 <= p <= 2.5 from the 3-point exact power-law fit on the three finest rungs (the same bisection solver already implemented as _order_triple in tools/d585_modal.py). If p is undefined because the fit is ill-conditioned (successive differences not decreasing), report A2 = UNDETERMINED with the three betas - do not silently substitute a 2-point estimate.
  A3 BAND: beta_0 <= 440.048 /m, and report the margin as a percentage. This is the ONLY surviving form of the original "<= k0 sqrt(er)" claim; at h=0.2 the margin is 13.4%, not 1%.
  A4 ALPHA: reported per rung, no gate.

FALSIFICATION (what kills which claim):
  F1 If |beta(R4)-beta(R2)|/beta > 1%, then beta(h=0.2) is not reportable and every beta quoted in this project carries a >1% band retroactively.
  F2 If p < 1, the scheme is not behaving second-order on this geometry and the h=0.2 discretisation error cannot be extrapolated at all.
  F3 If beta_0 > 440.048 /m, the "under the dielectric bound" claim dies outright.
  F4 If alpha(R4) tracks alpha(R2) within 10%, the box-artifact interpretation in Task 2 is wrong and alpha must be treated as physical loss.

PRE-REGISTERED INFRA BLOCKER (state now, before running): rungs R3, R4 exceed the container's ~120-150 s reclaim and its 512 MB cgroup cap (the tool's mem_limit is ignored). R4 at ~334 s is not runnable in-container by a factor of ~2.5. Therefore this ladder requires either a raised cgroup/time limit or a host run, and if it is not run, that is an infrastructure limitation and NOT evidence about beta.

MODAL CROSS-CHECK LADDER (already feasible, cl=1.0 only, 512 MB cap): h = 0.4 / 0.2667 / 0.2 / 0.16 / 0.123077, deflated engine, k=16, closure open. Observed: 364.259 / 364.604 / 364.794 / 364.913 / 365.457. Acceptance M1: the quasi-TEM candidate (identified by max |curl_ratio| among eps_eff < er-1e-6, NOT by beta ordering) lies within 1% of Hammerstad 365 at the two finest meshes. Pass: 364.913 (+0.02%) and 365.457 (-0.13%). Note the h=0.128 request snapped to nz_sub=13 => cell 0.123077, so the nominal geometric ratio 1.25 became 1.231; any order-p from this series is ill-conditioned and must be reported as UNDETERMINED.
