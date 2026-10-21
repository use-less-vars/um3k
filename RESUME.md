# RESUME -- session state

Position as of 2026-10-21, ~15:30 UTC.  The earlier chronological checkpoints have
been dropped from this file; their narrative is in `decisions.md` sections 54-65,
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
standing-wave reading of the board excess) is **dead**.  Section 65, added today, is
the **CW twin** at both bands: at 7.8333 GHz it reproduces the pulse's forward growth
almost intact, at 3.6667 GHz it does not reproduce it at all -- the CW record there
is a launch-region bump that decays, not a rate.

## In flight

Refinement solve, PID 3708, launched 15:26:28 UTC, expected back around 17:04.

    .scratch/m2/board_run_cw.py 7.8333 0.5

`dt = 9.532874347654860253e-14 s`, bit-exactly half the pulse step; the mesh is
unchanged at `322 x 200 x 76 cells at 0.1000 mm`; `nsteps=16067 n_warm=4016
n_acc=12051`; span 1.148806688e-09 s, so the tone snaps to 7.834216 GHz (residual
+0.916232 MHz, 0.65 MHz above the full-step tone).  That 8.3e-5 relative tone offset
is negligible beside the discriminator.

    dump  /workspace/.scratch/m2/board_cw_7.8333GHz_dts0.5.npz
    log   /workspace/.scratch/m2/board_cw_7.8333GHz_dts0.5.log

It runs on the CW path and **will exit 0**: the wrapper's post-solve `np.load` was
fixed on disk before this launch, unlike the two full-step runs, which both exited
non-zero after writing valid dumps.  The dump, not the exit code, is the deliverable.

## Next steps, in order

1. When it returns, run

       PYTHONPATH=/workspace python3 .scratch/m2/ab_decompose.py .scratch/m2/board_cw_7.8333GHz_dts0.5.npz

   read `|A9|/|A1|` and compute `alpha = ln(|A9|/|A1|) / 0.0096 m`.  The full-step
   values at 7.833566 GHz are `|A9|/|A1|` = 1.039055 and alpha = 3.990803 /m.  If
   alpha halves or falls substantially, the growth is a time-discretisation error and
   the repair is in the update rather than the reference plane; if it holds at 3.99 it
   is not a time-discretisation error.
2. Check the profile shape too, not only the rate: at the full step the CW profile
   rose monotonically to a maximum at station 8 and then dipped 0.13 % at station 9.
3. Then commit `decisions.md` and `RESUME.md` (docs only, no test run needed) and
   report to the ruling in under 400 words.

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
- `board_run_lid5_pw.py`, `compare_power.py`, `tri_compare.py`, `station_profile.py`.
- `ab_decompose.py` -- argv[1] = npz; the forward/backward split.
- `cw_vs_pw.py` -- argv[1] = npz, argv[2] = f in Hz.
- `validate_coupon.py`.

Hazard kept from an earlier session: `.scratch/study_run.py:11` writes
`open(".scratch/study_dump.txt", "w")` with a cwd-relative path, so running it from
the repo root would overwrite the evidence file with nothing visible in `git status`.
Run such scripts from `/tmp/retime`.

## Standing rules

- **No S-parameter measured on an imported board is quotable.**  The lid test is
  held, and nothing in section 65 is a reported S-parameter -- those are diagnostics.
- The `eps_eff` column of `.scratch/m2/cw_vs_pw.py` prints the *reciprocal* of the
  eps_eff that beta gives (0.27361, 0.27333 for the two full-step rows).  The label is
  wrong; no table may be built from that column until it is fixed.
- The 3.6667 GHz CW number is a net over a bump and a decay and must not be pushed
  into an alpha(f) fit; no power law is fitted to two CW frequencies.
- `dt_scale` refines time only: a spatial artefact is invisible to the refinement
  test, so "alpha invariant" would establish "not the time step", not "a property of
  the model".  Refining dx is out of reach inside the 4 GiB cap.
