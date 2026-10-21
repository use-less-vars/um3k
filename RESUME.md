# RESUME -- session state

Position as of 2026-10-21, ~18:00 UTC.  The earlier chronological checkpoints have
been dropped from this file; their narrative is in `decisions.md` sections 54-67,
which is the record of argument.  What is left here is only what is needed to
resume: where HEAD is, what is running, what to do next, and the constraints the
harness imposes.

## Position

The commit that closed section 67 and shipped the Poynting instrument is `ab948ba`.
HEAD is that commit or a later docs-only touch-up of this file.  The full suite is
green: `396 passed in 301.58s`, exit 0, log `.scratch/m2/pytest_full.log`.  Do not
budget 550 s for the tests: the earlier `556.58 s` single-file figure was inflated by
CPU contention with a solve running at the same time, and on an idle machine the whole
suite takes about 300 s.

`decisions.md` section 63 (the Im(z_c) hypothesis) is **refuted**.  Section 64 (the
standing-wave reading of the board excess) is **dead**.  Section 65 is the **CW twin**
at both bands: at 7.8333 GHz it reproduces the pulse's forward growth almost intact,
at 3.6667 GHz it does not reproduce it at all.  Section 66, written today, is the
**dt refinement**: halving the time step moved alpha by -0.030 per cent (3.990803 ->
3.989607 per metre) and left the nine-station profile unchanged to 0.025 percentage
points, so the growth is **not** a time-discretisation error.  The negative branch of
the pre-registered tree fired.  The remaining causes are the spatial discretisation
and the model itself, and neither is testable inside the 4 GiB cap.  Section 67, written
today, is the **Poynting diagnostic**: opt-in, non-invasive (flag-off bit-exact on five
keys), 9/9 tests in `tests/test_poynting.py`, suite green in 369 s.  Its own bias on a
matched fixture is a **mesh-independent decay** -- 6.2646 per cent peak-to-peak at a
0.800 mm cell, 6.3135 per cent at 0.400 mm, rate ratio 1.0044 -- i.e. of **opposite sign**
to the board's +8.45 per cent growth.  A cramped control box (1.2 mm gap, 1.2 mm margins)
gives 26.05 per cent, so the tilt tracks the box and not the cell.

## In flight

One solve, launched detached 17:52:09 on 2026-10-21: the 7.8333 GHz board CW run with
the Poynting diagnostic on.

    PID   6066
    cmd   cd /workspace && nohup env PYTHONPATH=/workspace \
          python3 .scratch/m2/board_run_cw_poynting.py 7.8333 \
          > /workspace/.scratch/m2/board_cw_7.8333GHz_poy.log 2>&1 &
    dump  /workspace/.scratch/m2/board_cw_7.8333GHz_poy.npz
    log   /workspace/.scratch/m2/board_cw_7.8333GHz_poy.log

`nsteps=8034 n_warm=2008 n_acc=6026`, full time step `1.90657e-13 s`, tone snapped to
7.833566 GHz (residual 0.266 MHz, 0.031 per cent of a bin), mesh `322 x 200 x 76` at
0.1000 mm.  It writes the usual fifteen keys **plus `sx_station` and `sx_station_sub`**.
Expect roughly 2900 s at 0.366 s/step, so about 18:41.  `dump written: None` in the log is
**cosmetic** (`np.savez` returns None); judge success by the file existing and by the
`dump schema: [...]` line, and by `BOARD_RUN_CW 7.8333GHz: DONE` plus `ELAPSED`.

## Next steps, in order

1. Commit - done: HEAD contains section 67 + the Poynting instrument (emfit/ports.py,
   emfit/studies.py, tests/test_poynting.py) + the docs.  Nothing to redo.
2. Analyse `board_cw_7.8333GHz_poy.npz`: normalise three nine-station profiles to
   station 1 and compare their **shapes** -- `sx_station`, `sx_station_sub`, and
   0.5 Re(v conj i) -- and check the first-half against the second-half pair.  Growth of
   `sx_station` with the circuit quantity means a field effect; flat or decaying
   `sx_station` against a growing circuit quantity means estimator-side; `sx_station_sub`
   growing faster than `sx_station` means the mode definition is drifting.  No absolute
   calibration is applied and no tilt is divided out.
3. Report that reading, in under 400 words, keeping the standing rule that no
   S-parameter measured on an imported board is quotable.
4. Nothing else.  Do not launch another solve, and do not run pytest while the dump
   analysis is the only open item.

## Working tree -- what must not be staged

- The section-67 work and the Poynting instrument (`emfit/ports.py`, `emfit/studies.py`,
  `tests/test_poynting.py`) plus `decisions.md` and this file are now **one commit**.
- The only changes left in the tree are `Intro.txt` and `docs/report/main.pdf`, both
  **never staged**: `Intro.txt` is not ours; `main.pdf` is a rebuild.
- A later docs-only edit to this file follows that commit.

Never smoke-test the full 322x200x76 mesh (120 steps > 600 s) - validate the dump
schema on the cheap 24x20x10 mesh (~2-7 s) instead, and remember `dump written: None`
is cosmetic (`str(np.savez(...))` returns `"None"`).

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
- `board_run_cw_poynting.py` -- `board_run_cw.py` plus the Poynting diagnostic; stem
  `board_cw_<f>GHz_poy`, `POY_SMOKE=<n>` for a throwaway `_smoke` run.  `board_run_cw.py`
  itself is untouched.
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
- **`n_air`, `n_clean` and `n_top` are counted in CELLS, not millimetres.**  Halving the
  cell silently halves the air gap and the strip margins and produces a different
  waveguide, not a refinement: the first attempt read eps_eff 4.1337 against 3.6979 and a
  rate ratio near 4.2 that looked like clean second-order scaling.  Re-derive those counts
  from millimetres for every `microstrip_wave` refinement.
- **`sx_station` carries a mesh-independent fixture tilt** -- 6.2646 per cent peak-to-peak
  on the matched calibration fixture at 0.800 mm, 6.3135 per cent at 0.400 mm -- so it is
  for **shape comparison**, never for absolute conservation checks.  For a conservation
  check use 0.5 Re(v conj i), which carries 1.9 per cent there.
- **The calibration tilt is never divided out of a board number.**  It is a property of
  that fixture and box, not a universal constant; the scaled correction that would have
  turned 8.45 per cent into 19.7 per cent was computed and **rejected**.
- The 3.6667 GHz CW number is a net over a bump and a decay and must not be pushed
  into an alpha(f) fit; no power law is fitted to two CW frequencies.
- `dt_scale` refines time only: the refinement has now been run and the growth
  survived it, so the result establishes "not the time step", not "a property of the
  model".  Refining dx is out of reach inside the 4 GiB cap.
