# M3a production harness -- hostile placement, explicit artefact directory

These two files were relocated here from `.scratch/host/m3a-smoke/run.sh` and
`.scratch/m2/board_run_cw_poynting.py` (previously unversioned). Content was
byte-identical to those originals; only the location changed. The originals
were deleted only after all four md5s were confirmed equal, so the claim is
checkable against commit `f123a5a` without them:

| file | md5 |
|---|---|
| `run.sh` | `cc1fd368797671f55ddb14bdde035f94` |
| `board_run_cw_poynting.py` | `f345b537a40637ba12d792d301cc26f8` |

## Why the harness takes a RUN_DIR

The harness used to derive every artefact path from the location of the script
itself. That made the script's location carry two unrelated meanings: where the
code lives, and where the results land. `RUN_DIR` separates them. The script now
resolves `ROOT` by walking up from its own directory and places every artefact
under `RUN_DIR` (default: the script's own directory).

## Run commands

```bash
cd ~/PycharmProjects/EE
mkdir -p .scratch/host/m3a-scan/nwarm1000 .scratch/host/m3a-scan/nwarm2000
POY_WARM=1000 POY_NACC=1339 RUN_DIR="$PWD/.scratch/host/m3a-scan/nwarm1000" bash tools/host/m3a-smoke/run.sh
POY_WARM=2000 POY_NACC=1339 RUN_DIR="$PWD/.scratch/host/m3a-scan/nwarm2000" bash tools/host/m3a-smoke/run.sh
```

`RUN_DIR` must be an absolute path. `POY_SMOKE` must stay UNSET: it is the
pair total and setting it bypasses the pair contract. `POY_WARM` and `POY_NACC`
are set together or not at all -- a half-set is refused.

## Exit codes

All fifteen codes the script can return. The numbered codes are a
machine-readable contract; the header comment in `run.sh` documents the same
set.

| exit | meaning |
|---|---|
| 0  | pass |
| 2  | usage -- unrecognised argument |
| 10 | interpreter -- the chosen python cannot run |
| 11 | numpy/scipy missing from that interpreter |
| 12 | `emfit` cannot be imported, or inputs rejected |
| 13 | disk preflight failed (nothing was launched) |
| 14 | memory preflight failed (nothing was launched) |
| 15 | clobber refused, or `--reuse-record` usable-record check failed (record absent, stale, or partial) |
| 16 | the solve itself failed -- only reachable when a solve actually ran, so never under `--reuse-record` |
| 17 | artefact check failed (no plane record, or `solve.out` held no PROGRESS line) |
| 18 | analysis stage failed or returned non-zero |
| 19 | gate FAIL -- note this also fires on any non-zero verdict-runner status, including a crash, not only a genuine gate failure |
| 20 | solve-context probe failed (the runner's own imports, before any solve) |
| 21 | warm-up pair refused: half-set, non-numeric, zero step count, or `POY_SMOKE` disagreeing with the pair |
| 22 | `ROOT` or `RUN_DIR` could not be resolved; where the failure is on the run-directory side no write was attempted |

## Settled production parameters

`POY_WARM=4000 POY_NACC=6026`. This is the production-parameter record the
`|S21|_poynting` figure is taken from.

## Records

Each run writes `plane_record.npz` (8845003 bytes on the production record)
into its own `RUN_DIR`. Records are NOT versioned -- they are large binaries
and are treated as run outputs. The `RUN_DIR` name is the record's provenance;
name directories after the parameters they hold (e.g. `nwarm4000_nacc6026`).

## Known documentation staleness

`board_run_cw_poynting.py`'s docstring `Usage::` line still names the file
`board_run_cw.py`. The filename is `board_run_cw_poynting.py`. Preserved as-is
to keep the file byte-identical to its pre-relocation copy.

## What is not here

The `.npz` plane records and the `analysis.*` / `verdict.txt` files these
runs produced are run outputs and are not versioned. Only the code and the
parameters needed to reproduce them are. A figure quoted from a run whose
`RUN_DIR` is gone is not reproducible here and should be re-run before
being quoted again.
