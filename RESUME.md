# RESUME -- session state

Position as of 2026-10-21, ~19:45 UTC.  The earlier chronological checkpoints have
been dropped from this file; their narrative is in `decisions.md` sections 54-68,
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
at 3.6667 GHz it does not reproduce it at all.  Section 66 is the
**dt refinement**: halving the time step moved alpha by -0.030 per cent (3.990803 ->
3.989607 per metre) and left the nine-station profile unchanged to 0.025 percentage
points, so the growth is **not** a time-discretisation error.  The negative branch of
the pre-registered tree fired.  Section 67 is the **Poynting diagnostic**: opt-in,
non-invasive (flag-off bit-exact on five keys), 9/9 tests in `tests/test_poynting.py`,
suite green in 369 s.  Its own bias on a matched fixture is a **mesh-independent
decay** -- 6.2646 per cent peak-to-peak at a 0.800 mm cell, 6.3135 per cent at
0.400 mm, rate ratio 1.0044 -- i.e. of **opposite sign** to the board's +8.45 per cent
growth.  A cramped control box (1.2 mm gap, 1.2 mm margins) gives 26.05 per cent, so
the tilt tracks the box and not the cell.

Section 68, written today, is the **board run with the Poynting diagnostic on**: the
solve is COMPLETE (2630.1 s, `EXIT=0`, every artefact check PASS; dump
`.scratch/m2/board_cw_7.8333GHz_poy.npz`, seventeen keys including `sx_station` and
`sx_station_sub`, both shape (9,)).  The reading is **estimator-side**: the flux falls
(net -3.0723 per cent from station 1 to station 9, `alpha_e2e` -3.250504 per metre)
while the circuit quantity grows (+8.4742 per cent, +8.473143 per metre, digit-identical
to sections 65 and 66), so the +8.5 per cent board excess lives in the estimator and
not in the field.  Branch 3 of the pre-registered tree did **not** fire: the substrate
share of the flux moves only 76.736 -> 77.745 per cent, far too little to call a
drifting mode definition.  The flux column is therefore the **interim insertion
loss**: `|S21|_poynting = 0.984519`, -0.1355 dB over the 9.6 mm line, 0.0141 dB/mm --
1.6 per cent above the recorded `0.0139` dB/mm floor and 1.22x the audited lateral-leak
rate of 0.01160 dB/mm.  Two things are **absent** and are not defects of the run: the
dump carries no first-half / second-half pair, so the halves check cannot be made at
all, and the port is not mode-matched, so no beta, eps_eff, Z0, S11 or passivity number
comes out of this record.

## In flight

**Nothing.  Nothing is running.**  The 7.8333 GHz board CW solve with the Poynting
diagnostic on finished at 19:26:49 and its dump is on disk.  The detached wrapper
logged `launcher exit=0`, `EXIT=0`, `TOTAL_ELAPSED=2632s`, at 0.3274 s/step for
`nsteps=8034` (`n_warm=2008`, `n_acc=6026`, full step `1.90657e-13 s`, tone snapped to
7.833566 GHz, mesh `322 x 200 x 76` at 0.1000 mm).  A later `run.sh check` at 19:44
exited 4 because the dump already exists; that is why `result.log` has a 19:44 mtime
and it is not a second run.  `dump written: None` in the solve log is **cosmetic**
(`np.savez` returns None).

## Next steps, in order

1. Section 68 is recorded -- done.  `decisions.md` section 68 carries the reading, the
   nine-station table and the net/p2p/alpha_e2e table.  No code changed, no solve was
   relaunched, no pytest run was made; the last green suite is still
   `396 passed in 301.58s`.
2. **The modal port (M3) is next.**  The flux diagnostic has now been taken as far as
   it goes without one: `sx_station` is a raw cross-section integral over the line,
   with no mode normalisation and no tilt divided out, and the halves check is
   unavailable from this dump.  Until a port projects the line fields onto the mode,
   nothing here can be turned into an S-parameter, so the next unit of work is the
   mode-matched port that section 68's closing paragraph names (G4).
3. The **only** carry-forward number from section 68 is the flux-column insertion loss,
   `|S21|_poynting = 0.984519` (-0.1355 dB, 0.0141 dB/mm over 9.6 mm), and it is
   quotable **as a flux diagnostic only**.  beta, eps_eff, Z0, S11 and any passivity
   statement are **not** quotable from this record.  The standing rule below is intact:
   no S-parameter measured on an imported board is quotable.
4. Nothing else.  Do not launch another solve, and do not run pytest while the docs are
   the only open item.

## Working tree -- what must not be staged

- The section-67 work and the Poynting instrument (`emfit/ports.py`, `emfit/studies.py`,
  `tests/test_poynting.py`) plus `decisions.md` and this file are **one commit**
  (`ab948ba`).
- Uncommitted now, and docs-only: the section-68 append to `decisions.md` and this
  `RESUME.md` edit.  There is no code change in the tree from the section-68 run.
- The only other changes left in the tree are `Intro.txt` (30982 B, untouched) and
  `docs/report/main.pdf` (1226821 B, a rebuild), both **never staged**: `Intro.txt` is
  not ours; `main.pdf` is a rebuild.  `docs/report/` also holds `main.log`, `main.tex`
  and the `sec_*.tex` sources, which are ours and may be staged.

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
  That cap belongs to the worker container, not to the host: the host run used 15.3 GiB
  total / about 8.0 GiB available on 12 cores.
- Guard pytest with `ulimit -v 1100000`, and never pass `-q`: `pyproject.toml` already
  sets `addopts = "-q"`, so a second one suppresses the summary line.
- The report builds with `.tools/bin/tectonic -X compile docs/report/main.tex`.

### Host harness for long solves

The section-68 solve was run **on the host**, not in the container, because the
container's `.venv` is Python 3.13.5 with no numpy and the solve dies at import (one
earlier in-container attempt was OOM-killed, exit 137).

- Invoke from the repo root `~/PycharmProjects/EE`:
  `bash .scratch/host/poynting-7.8333/run.sh`.  `run.sh check` is a **preflight only**
  and runs no solve.  `run.sh check` therefore fails its import stage inside the
  container by design (venv 3.12 versus container 3.13) and passes on the host.
- Everything is written beside the script: `result.log` (appended to, per invocation),
  `solve.out` (the solve's own verbatim output), `bare.out`, `manifest.md`.
- The launcher **always exits 0**, so the artefacts decide, not the exit status.  Exit
  codes that matter: **3** MemAvailable below 3800 MB (refuses before launch), **4**
  the dump already exists and will not be overwritten, **7** artefacts missing or
  incomplete after the solve, **8** the instrument self-test (5/5 preflight stages)
  failed, **137** OOM kill.
- Success reads as: the npz exists with `sx_station` and `sx_station_sub` at shape (9,),
  `ELAPSED` and `DONE` both present, `EXIT=0`, a `TOTAL_ELAPSED=`, and a `READING:`
  line from `poy_profile.py`.
- **Host runs must narrate themselves** -- standing requirement, not preference: a run a
  human cannot watch is a run a human cannot trust. Unbuffered output always (`-u`,
  `PYTHONUNBUFFERED=1`); a `PROGRESS` line every 500 steps or 30 s, whichever is sooner,
  with step/total/per cent/elapsed/ETA; a phase header before each stage; and a tee to
  `result.log` so it can be `tail -f`'d -- never a silent redirect.
- Geometry of that run, for reference: `n_air 48, n_clean 73, n_top 12, n_strip 30,
  n_pml 12, n_ref 75, n_line 235, ix_port 87`, station cells 104..200 step 12,
  `y_extent 0.0088`.

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
  end-to-end column (`ln(|A9|/|A1|)/0.0096 m`).
- `cw_vs_pw.py` -- argv[1] = npz, argv[2] = f in Hz; its `eps_eff` column is fixed.
- `validate_coupon.py`.
- `poy_profile.py` -- argv[1] = npz (or no argv for the default); prints the three
  nine-station profiles normalised to station 1 (`sx_station`, `sx_station_sub`, and
  0.5 Re(v conj i)), the net / peak-to-peak / `alpha_e2e` table, a `READING:` line
  naming the branch that fired, and `half fields ABSENT` when the dump carries no
  first-half / second-half pair.  This is the script `run.sh` calls after the solve.

Not in `.scratch/m2/`: `run.sh` is the host harness at
`.scratch/host/poynting-7.8333/run.sh` (see above).

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
