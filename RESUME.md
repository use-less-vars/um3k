# RESUME -- session state

Position as of 2026-10-21, ~17:05 UTC.  The earlier chronological checkpoints have
been dropped from this file; their narrative is in `decisions.md` sections 54-66,
which is the record of argument.  What is left here is only what is needed to
resume: where HEAD is, what is running, what to do next, and the constraints the
harness imposes.

## Position

HEAD is commit `e2fa4f5` ("studies: opt-in dt_scale on both wave studies,
defaulting to the CFL step").  The full suite is green: `396 passed in 301.58s`,
exit 0, log `.scratch/m2/pytest_full.log`.  Do not budget 550 s for the tests: the
earlier `556.58 s` single-file figure was inflated by CPU contention with a solve
running at the same time, and on an idle machine the whole suite takes about 300 s.

`decisions.md` section 63 (the Im(z_c) hypothesis) is **refuted**.  Section 64 (the
standing-wave reading of the board excess) is **dead**.  Section 65 is the **CW twin**
at both bands: at 7.8333 GHz it reproduces the pulse's forward growth almost intact,
at 3.6667 GHz it does not reproduce it at all.  Section 66, written today, is the
**dt refinement**: halving the time step moved alpha by -0.030 per cent (3.990803 ->
3.989607 per metre) and left the nine-station profile unchanged to 0.025 percentage
points, so the growth is **not** a time-discretisation error.  The negative branch of
the pre-registered tree fired.  The remaining causes are the spatial discretisation
and the model itself, and neither is testable inside the 4 GiB cap.

## In flight

Nothing.  No solve is running; the machine is idle.

The refinement solve (PID 3708) returned at 16:58:56 with `ELAPSED 5547.6 s`,
0.3453 s per step, and **EXIT=0** -- the first clean exit of the three CW runs,
because the wrapper's post-solve `np.load` fix landed on disk before the launch.

    dump  /workspace/.scratch/m2/board_cw_7.8333GHz_dts0.5.npz
    log   /workspace/.scratch/m2/board_cw_7.8333GHz_dts0.5.log

`ab_decompose.py`, `cw_vs_pw.py` and `station_profile.py` have all been run on that
dump; every number is in section 66 and is not repeated here.

## Next steps, in order

1. Commit `decisions.md` and `RESUME.md` (docs only, no test run needed).  Stage
   nothing else: `Intro.txt` and `docs/report/main.pdf` are never staged.
2. Report to the ruling in under 400 words.  The line is: the refinement is flat, so
   the growth is not the time step; the steady-state passivity statement (8.4549 per
   cent more flux at station 9 than at station 1, `|S11|` 37 dB down) is the form to
   argue; no S-parameter measured on the imported board is quotable.
3. Only if the thread is reopened: the open discriminators are spatial (dx, blocked by
   memory) and the model itself.  Do the memory arithmetic before launching anything
   (roughly eightfold per halving against a 4 GiB cap).

## Working tree -- what must not be staged

- `Intro.txt` and `docs/report/main.pdf` are modified in the working tree and are
  **never staged**.  `Intro.txt` is not ours; `main.pdf` is a rebuild.
- `.scratch/` is untracked and must stay untracked unless a launcher is deliberately
  promoted.
- Everything else of ours is committed.

## Harness constraints (all still true)

- The worker window is about 480 s, so keep any single job under about 420 s.
- Long solves must be launched detached and polled in short loops:

      setsid nohup bash -c '...; echo EXIT=$?' < /dev/null >/dev/null 2>&1 &

  A solve launched without setsid/nohup dies when its exec session's container goes
  away; that has already happened once.
- `docker`, `ps`, `pgrep`, `free`, `dmesg` and `git` are all absent.  Use `/proc`,
  `/proc/<pid>/status` and the cgroup files instead.
- PID 1 does not reap, so finished processes persist as zombies: `State: Z` means
  **done**, not alive.  Never use `while [ -d /proc/PID ]` as a liveness test.
- The memory cap is 4 GiB (`/sys/fs/cgroup/memory.max`), and one solve peaks near
  3.6 GB.  One solve at a time, and **never run pytest while a solve is in flight**.
- Guard pytest with `ulimit -v 1100000`, and never pass `-q`: `pyproject.toml` already
  sets `addopts = "-q"`, so a second one suppresses the summary line.
- The report builds with `.tools/bin/tectonic -X compile docs/report/main.tex`.

## Scripts in `.scratch/m2/`

- `board_run.py` -- the pulse/board launcher.
- `board_run_pw.py` -- **do not edit**.
- `board_run_cw.py` -- takes `f_GHz` and an optional `dt_scale`; snaps the tone to its
  own DFT bin and searches the record length.
- `board_run_lid5_pw.py`, `compare_power.py`, `tri_compare.py`, `station_profile.py`
  (argv[1] = npz; the nine-station `P/P1` profile and the launch-vs-cumulative split).
- `ab_decompose.py` -- argv[1] = npz; the forward/backward split, plus an `alpha_e2e`
  end-to-end column added today (`ln(|A9|/|A1|)/0.0096 m`).
- `cw_vs_pw.py` -- argv[1] = npz, argv[2] = f in Hz; its `eps_eff` column is fixed.
- `validate_coupon.py`.

Hazard kept from an earlier session: `.scratch/study_run.py:11` writes
`open(".scratch/study_dump.txt", "w")` with a cwd-relative path, so running it from
the repo root would overwrite the evidence file with nothing visible in `git status`.
Run such scripts from `/tmp/retime`.

## Standing rules

- **No S-parameter measured on an imported board is quotable.**  The lid test is
  held, and nothing in sections 65-66 is a reported S-parameter -- those are
  diagnostics.
- The `eps_eff` column of `.scratch/m2/cw_vs_pw.py` printed the *reciprocal* of the
  eps_eff that beta gives; that bug was fixed today (pre-edit copies at `/tmp/*.orig`)
  and the column now agrees with the beta-derived value (3.65849 against 3.65849 at
  dt/2; 3.65855 against 3.65855 at the full step).  No table may be built from output
  produced before that fix.
- The 3.6667 GHz CW number is a net over a bump and a decay and must not be pushed
  into an alpha(f) fit; no power law is fitted to two CW frequencies.
- `dt_scale` refines time only: the refinement has now been run and the growth
  survived it, so the result establishes "not the time step", not "a property of the
  model".  Refining dx is out of reach inside the 4 GiB cap.
