# Multifrequency station-fit beta test — `multifreq-beta-test-2026-11-07`

*Dated 2026-11-07. Dispatch id `multifreq-beta-test-2026-11-07`, **re-issued after a workspace bounce**:
the first dispatch landed no work, so nothing here inherits from it. Status: **HAS RUN**. The driver
script `evidence/termination/run_multifreq.py` was written by the worker; the FDTD run was made by the
operator across **2026-11-07T01:03:26Z → 2026-11-07T01:08:05Z**, five bins (`k = 5, 7, 8, 10, 12`,
3.6424–8.7417 GHz), **5/5 rows, 0 failures, 0 incomplete, 0 raised**. Headline: `beta_fit` sits **above**
`beta_model` at every bin, by **+3.275 % to +4.465 %** (mean **+3.922 %**), a max−min spread of
**1.190 %** across the band — scored against the brackets frozen in §5, one of which (**F1**) fires; the
`k = 12` row is `beta_ambiguous` and is excluded from the bracket count exactly as §6 requires, and that
exclusion does not change the verdict (§7). The §5 thresholds were written before the data and have not
been moved since. Provenance: **no modification of `emfit/` was made, and none is authorised by this
dispatch** — the test is built entirely out of the library's existing public parameters.
`infra/openems/reference/` is untouched. No commit accompanies this file.*

---

## 1. Purpose and hypothesis

The Stage A1 port-normalisation audit (`docs/design/port_normalisation_audit_2026-11-05.md`, §11 erratum)
concluded that the magnitude residual on the A arm is reproducible **only through the beta basis**.
Shifting the station-fit beta from **231.55331672912826 rad/m** to the Hammerstad–Jensen
**223.35306683909533 rad/m** moves `|Γ_port|` from 0.3258868 (−5.44 % on the series-R anchor) to
0.3425167 (−0.62 %), i.e. onto the anchor — but the same shift makes the station fit's own voltage
residual **8.2× worse** (`resid_v` 0.0011010 → 0.0093178) and moves the s11 phase residual from
**+7.18 deg to +16.50 deg** (`docs/design/beta_refit_test_2026-11-05.md:180-182, :249-251`). So the data
reject the lower beta, and the higher beta breaks the magnitude. One scalar cannot serve both.

Hypothesis under test: **the station fit's beta is absorbing model error.** The two-wave fit
(`fit_station_impedance` over the probe stations) assumes the line carries one forward and one backward
mode; near the load there is evanescent and fringing content the model cannot represent, and beta is the
free parameter that absorbs it. If that is what is happening, the fitted beta is not a property of the
line at all — it is a **proxy** for whatever the model is missing, and its value should therefore
**change with frequency**, because model error is frequency-dependent (the electrical distance to the
load, the evanescent decay length in cells, and the fringing capacitance all scale differently).

If, on the other hand, the fitted beta is **stable across frequency**, then the model is fine, the
estimator simply reads beta wrong by a constant, and the A1 audit's "231.55 is the fitted value" should be
attacked as an estimator bias rather than as model error.

**Only a multi-frequency run discriminates these.** A single frequency cannot: at one frequency a
proxy and a bias are observationally identical. That is the entire justification for this dispatch.

## 2. Excitation path — a broadband mode exists, and it is unusable here

A broadband mode exists in the library. `emfit/studies.py:1209-1220` defines

```
MS_EXCITE = "cw"        # "pulse" = the Ricker wavelet the broadband sweep is read off
MS_BAND_LO_GHZ = 2.0
MS_BAND_HI_GHZ = 12.0
MS_N_BINS = 25
MS_F_PULSE_GHZ = 5.83
```

and it is exposed as a knob — `Param("excite", ..., choices=("cw", "pulse"))` at `emfit/studies.py:5518`
and `:5637`. On a pulse run the per-bin block `bins` is populated (`studies.py:3709-3710`,
`freqs = np.linspace(band_lo, band_hi, n_bins)`), so **one solve would cover the whole band**, at a saving
of roughly 5× the wall time and memory this dispatch will otherwise spend.

**It cannot be used, and the reason is a guard, not a preference.** `emfit/studies.py:2930-2935`:

```python
if excite == "pulse":
    raise ValueError(
        "s21_plane is a single-tone extraction, and excite=\"pulse\" "
        "reads the band off the kept record, whose columns are the "
        "stations: the cut plane is not one of them.")
```

The A arm **is** an `s21_plane="cut"` run — `run_build_A.py:1227` describes itself as "one load at p2,
s21_plane='cut'", and the reference A artefact carries that plane as an **integer index, not a name**:
`run.kwargs.s21_plane = 51` (int), `geometry.s21_plane_index = 51` with
`geometry.s21_plane_requested = 51.0`, and `s21.s21_plane_index = 51` with
`s21.s21_plane_requested = 51`; the string `"cut"` appears in no field of the artefact, only in
prose notes (`run.loaded_without_reference_note`) and in the policy flags `s21.plane_policy =
"explicit"`, `s21.plane_from_default_policy = false`, `s21.plane_sweep_diagnostic = true`
(`evidence/termination/build_A_50ohm_p51_phasors.json`). 51 is the load's own column 50 plus one,
i.e. the first plane downstream of the cut (`emfit/studies.py:2919-2951`: an index upstream of the
load column is refused rather than measured), and `s21.planes_m = [0.0032, 0.0204]` puts port and
cut at 3.2 mm and 20.4 mm. A pulse
run therefore **cannot emit the A arm's `s21.magnitude` at all**; the per-bin substitute, `_bin_metrics`
(`studies.py:1947`), carries its own `fit_one` (`:2005-2006`) and is off the build_A artefact path (see
the `s11-estimator-fix` row in the dispatch log). The pulse route would also force `n_warm = 0`
(`studies.py:2974-2975`) and retain the full `history` and `drive_trace` (`studies.py:3081-3083`) — a
memory profile the A-arm ceilings were never set for. Note also `MS_F_PULSE_GHZ = 5.83`: the broadband
centre is tuned to the very frequency under test, so even as a fallback it would be least trustworthy
exactly where the existing single-frequency number lives.

**Consequence.** The only route that preserves the A-arm extraction is **N single-tone solves, one per
DFT bin, varying nothing but `f_target`**. That is legal without touching `emfit/`: `f_target` is a plain
float parameter of `microstrip_wave` (`emfit/studies.py:2495`, `f_target: float = MS_F_TARGET`, default
`MS_F_TARGET = 6.0e9` at `:1163`), and the study layer already pipes a user knob into it
(`f_target=float(values["f0"]) * 1e9` at `studies.py:4246` and `:4259`; the knob is
`Param("f0", "Drive frequency", "float")` at `emfit/demos.py:362` and `:391`). `run_build_A.py` exposes
**no `--freq` / `--f0` / `--excite` flag** (its full CLI is `--out --load-at-mm --n-line --load-ohm
--label --mem-ceiling-mb --wall-limit-s --with-twin --s21-plane-index --dry-run --s11-settling
--measure-z-eff --ms-x-window --launch --flux-projection`, `run_build_A.py:1230-1333`), which is why a
separate driver was required rather than a flag on the existing one.

## 3. Frequency grid — DFT bins, derived and then checked against the artefact

The tone frequency is not free. It is snapped onto a bin of the accumulated record
(`emfit/studies.py:2969-2982`):

```
n_warm = nsteps // 4;  n_acc = nsteps - n_warm        # :2971, :2977
span   = n_acc * dt                                   # :2981
f0     = max(1, round(f_target * span)) / span        # :2982
```

So the reachable set is `f = k / span`, k integer, spacing `Δf = 1/span`. From the reference artefact
`evidence/termination/build_A_50ohm_p51_phasors.json` itself (and its siblings, identically),
`geometry.dt = 7.626299478123987e-13 s` and `geometry.nsteps = 2400` give `n_warm = 600` and
`n_acc = 1800`, which the artefact records directly as `geometry.n_warm = 600.0` and
`geometry.n_acc = 1800.0`; hence `span = 1.3727339e-9 s` and **Δf = 728.4733 MHz**. The same
artefact records `geometry.f = 5827786408.327286 Hz` (and `geometry.f_hz`, same value) against
`geometry.f_target = 6000000000.0` — i.e. the 6 GHz ask was
snapped down to **k = 8** (8 × 728.4733 MHz = 5827.7864 MHz), which reproduces the recorded value to the
last digit stored.

| k | f (GHz) | asked in dispatch | snap error |
|---|---|---|---|
| 5 | 3.6424 | 3.50 | +4.07 % |
| 7 | 5.0993 | 5.00 | +1.99 % |
| 8 | 5.8278 | 5.83 | −0.04 % (existing point, harness check) |
| 10 | 7.2847 | 7.50 | −2.87 % |
| 12 | 8.7417 | 9.00 | −2.87 % |

All five bins lie inside 3–10 GHz; the sweep spans **3.64–8.74 GHz, a factor 2.40 in frequency**. The
snap errors are recorded here rather than corrected, because a sweep silently re-asked is a sweep whose
grid nobody can audit. Bin 8 is retained deliberately: it must reproduce 5.827786408 GHz and the existing
station fit, or the harness is not the A arm and no other row counts (§4).

## 4. The script — `evidence/termination/run_multifreq.py` (written, and since run)

`AARM_KWARGS` mirrors the A arm: `h = 1.6 mm`, `w = 3.2 mm`, `eps_r = 4.4`, `n_sub = 4`, `n_top = 6`,
`n_clean = 96`, `n_strip = 8`, `n_air = 12`, `n_pml = 6`, **`n_line = 64`** — not the library
default `MS_N_LINE = 54` (`emfit/studies.py:1203`) — `n_stations = 9`, `nsteps = 2400`,
`s21_plane = 51` as an **integer index** (50 + 1), 50 Ω at p2, `excite = "cw"`. Each value is
the reference artefact's own: `geometry.n_line = 64.0`, `geometry.n_sub = 4.0`,
`geometry.n_top = 6.0`, `geometry.n_clean = 96.0`, `geometry.n_strip = 8.0`, `geometry.n_air = 12.0`,
`geometry.n_pml = 6.0`, `run.kwargs.s21_plane = 51`. `cross_check()` reads the reference artefact's `geometry` block and **refuses to start**
if any of those disagree with what this script would pass — the guard against sweeping some other
microstrip by accident. The artefact's own provenance, so the geometry is reproducible:
`meta.argv` = `evidence/termination/run_build_A.py --n-line 64 --load-at-mm 20 --load-ohm 50
--mem-ceiling-mb 2000 --s21-plane-index 51 --out evidence/termination/build_A_50ohm_p51_phasors.json`
(repeated verbatim in `meta.command_line`; `meta.cwd = /home/jojo/PycharmProjects/EE`,
`meta.started_utc = 2026-11-04T15:01:15+00:00`, `meta.git_rev = null`). That is where `n_line = 64`
and `s21_plane = 51` come from: `--n-line 64` is what moves `nx` from the older arm's 62 to 72
(`geometry.nx = 72.0`). **Station count, resolved:** the artefact records no key called
`n_stations` — it records the fitted count as `s11.station_phasors.n = 9`, and `geometry.station_fit_n = 8.0`
separately (that count after the load column is dropped). The guard resolves the reference value from
`s11.station_phasors.n`, falls back to `geometry.station_fit_n + 1` when that key is absent, and compares
it against this script's `n_stations = 9`. If neither basis resolves, it refuses to start (`SystemExit`)
rather than skipping the station count in silence. The loop runs `--k 5 7 8 10 12`, passing `f_target = k / span` exactly, so the
snap offset is zero by construction and `f_used == f_asked`.

Per frequency it writes `build_A_50ohm_multifreq_k{K}_{f:.4f}GHz.json` carrying `s11.magnitude`,
`s11.magnitude_one_wave_station_fit`, `s11.phase_deg`, `s21.magnitude`, `s21.phase_deg`, the station-fit
`beta_used` and `beta_two`, `run.station_fit.z0_re` / `z0_im`, `line.beta`, `line.beta_model`,
`line.eps_eff_model`, `beta_ambiguous`, and the derived `delta_beta_frac`. **Nulls are recorded as
nulls** — a bin whose fit did not close is a gap in the table, never a patched row, because a patched row
is precisely how an F4 falsifier gets laundered into an F1. The same discipline is enforced in code: F4
is built in, failures are collected, and if `failures * 2 > len(rows)` the script prints `BLOCKED` and
exits 5. A mostly-failed run cannot be read as a result. `--dry-run` prints the five planned calls and
executes no FDTD.

**Invocation, and a provenance gap owned up to.** The script now inserts the repository root on
`sys.path` itself (`evidence/termination/run_multifreq.py:73-77`) and records its own command line in
`meta.argv`, so plain `python3 evidence/termination/run_multifreq.py` runs from any working directory with
no `PYTHONPATH` set, and the artefact says how it was started. The five artefacts on disk **predate that
fix**: their `meta.argv` is `null` and no `meta.command_line` was written, so the exact invocation that
produced this run is **not recoverable** from the data. The parameters survive in `meta.kwargs` (and agree
with `AARM_KWARGS`), but the argv does not. That is a real provenance gap, recorded here rather than
papered over; re-running now would close it.

## 5. Pre-registered brackets

**These thresholds are frozen before the data and must not move after it.** The same discipline governs
`docs/design/beta_refit_test_2026-11-05.md:104-105`, and it applies here for the same reason: a bracket
chosen after the numbers are seen is not a test.

| bracket | condition | reading |
|---|---|---|
| **F1** | `beta_fit` varies > 1 % across 3.64–8.74 GHz **and** sits above `beta_model` at every bin | the offset is model error the extraction absorbs — fix the extraction model (three-wave fit / frequency-dependent correction), not beta |
| **F2** | `beta_fit` stable to < 0.5 % **and** offset above `beta_model` roughly constant | the model is fine and beta is simply wrong — investigate a bias in the fit's cost function |
| **F3** | `beta_fit` tracks `beta_model` within 1 % at every bin | the 5.83 GHz single-frequency case is anomalous (geometry, mesh or load position), not the model |
| **F4** | cannot be built without editing `emfit/`, or fit/beta missing at ≥ 3 of 5 bins (script exits 5) | **report blocked**; no bracket scored |

A pre-registered prior, from the refit doc, so that it cannot be claimed as hindsight: the residual basin
pins beta to about ±0.5 rad/m (±0.22 %), and the phases and `|Γ|` want betas that do not overlap
(`[224.575706, 234.529283]` vs `[236.146125, 239.710245]`). On that reading a **frequency-stable** beta
(F2) is the more likely of F1/F2. But the prior is not the test: **the sweep, not the prior, decides.**

## 6. Cost and caveats for the operator

**Five solves, not one.** Roughly 5× a single A-arm run (2400 steps, **72×212×22** cells = **335 808** cells, `geometry.grid` and `geometry.cells`
in the reference artefact; the 62 and 289 168 of an earlier draft belonged to the `n_line = 54`
default, not to this `--n-line 64` arm). Budget memory per the existing ceilings. The script's `--mem-ceiling-mb` is a
**pre-flight note only**: it does not re-implement the trip, which stays in `run_build_A.py:1362-1380`
where it already lives, and this dispatch does not duplicate it.

`beta_model` is the Hammerstad–Jensen closed form (`line.beta_model = 223.35306683909533` at 5.83 GHz) and
it is **frequency-dependent**. Each bin must therefore be compared against the model *at that bin*, never
against 223.3531 — the script reads `line.beta_model` per run for exactly this reason, and a table that
quotes a single model column for all five rows is wrong.

`beta_ambiguous` (`geometry.beta_ambiguous = |beta|·d_probe > π`; the reference artefact
records `geometry.beta_ambiguous = 0.0` at 5.83 GHz) must be checked per bin. At the higher
bins the probe spacing can alias beta, and **an aliased beta is not a bracket datum** — it is a
measurement that does not exist. The flag is recorded per row and must be honoured when scoring; a row
with `beta_ambiguous` true is treated as a missing row for F1–F3 purposes and counts toward F4's failure
tally.

Finally: **the operator runs it, and reports the summary table back.** Nothing here is a result until the
five artefacts exist.

## Files

| file | status |
|---|---|
| `evidence/termination/run_multifreq.py` | created, 547 lines |
| `docs/design/multifreq_beta_test_2026-11-07.md` | created (this file) |
| `docs/design/dispatch_log.md` | row appended |

---

## 7. Results — the sweep has run

*Appended 2026-11-07, after the sweep. Numbered 7 and placed after the Files table on purpose: nothing in
§1–§6 is renumbered, re-titled or re-worded, so the pre-registered text keeps its line numbers and the
reader can still see, in situ, what was promised before the data and what arrived after it.*

### 7.1 The five bins, read from the artefacts

Every value below is taken from `row` in `evidence/termination/build_A_50ohm_multifreq_k{K}_{f:.4f}GHz.json`
(five files, 2855–2862 B each). `station_fit.beta`, `line.beta` and `station_fit.beta_two` are identical
at every bin, so the row's beta is the station fit's beta.

| k | f_ghz_used | station_fit.beta (rad/m) | line.beta_model (rad/m) | delta_beta_frac | \|S11\| | \|S21\| | beta_ambiguous |
|---|---|---|---|---|---|---|---|
| 5 | 3.642367 | 145.198 | 139.596 | +4.013 % | 0.330769 | 0.667230 | false |
| 7 | 5.099313 | 201.835 | 195.434 | +3.275 % | 0.320662 | 0.735339 | false |
| 8 | 5.827786 | 231.553 | 223.353 | +3.671 % | 0.325565 | 0.764418 | false |
| 10 | 7.284733 | 291.658 | 279.191 | +4.465 % | 0.316934 | 0.731901 | false |
| 12 | 8.741680 | 349.043 | 335.030 | +4.183 % | 0.310726 | 0.809805 | **true** |

Bin 8 reproduces the reference arm's 5.827786408 GHz and its station fit, which is the condition §3 set
for the other rows to count.

### 7.2 Run health

From `evidence/termination/build_A_50ohm_multifreq_summary.json`, verbatim:

    rows: 5, failures: 0, incomplete: 0, raised: 0

and `row["errors"]` is `[]` in all five artefacts — checked in code (`all(errs == [] ...)` → `True`), not
by eye. The `cross_check` block records `checked: true`, `n_stations: 9`,
`n_stations_basis: "s11.station_phasors.n"`, `reference: "build_A_50ohm_p51_phasors.json"`, so the §4
guard did resolve the station count rather than refuse to start. Summary generated
`2026-11-07T01:08:05+00:00`; `meta.started_utc` inside the artefacts is `2026-11-07T01:03:26+00:00`.

### 7.3 Statistics on `delta_beta_frac`

Computed, not estimated. Code as run:

```python
import json, glob, statistics, math

rows = []
for p in sorted(glob.glob('evidence/termination/build_A_50ohm_multifreq_k*_*GHz.json')):
    r = json.load(open(p))['row']
    rows.append(dict(k=r['k'], f=r['f_ghz_used'], frac=r['delta_beta_frac']))
rows.sort(key=lambda r: r['k'])

def stats(vals, label):
    mean = statistics.mean(vals); sd = statistics.stdev(vals)
    mn, mx = min(vals), max(vals)
    print('%s n=%d mean=%.12f stdev=%.12f min=%.12f max=%.12f spread=%.12f'
          % (label, len(vals), mean, sd, mn, mx, mx-mn))
    print('         mean_pct=%.6f stdev_pct=%.6f spread_pct=%.6f' % (100*mean, 100*sd, 100*(mx-mn)))

def pearson(x, y):
    n = len(x); mx = sum(x)/n; my = sum(y)/n
    sx = math.sqrt(sum((a-mx)**2 for a in x)); sy = math.sqrt(sum((b-my)**2 for b in y))
    return sum((a-mx)*(b-my) for a, b in zip(x, y))/(sx*sy)

def rank(v):                       # average ranks, ties handled
    order = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0]*len(v); i = 0
    while i < len(order):
        j = i
        while j+1 < len(order) and v[order[j+1]] == v[order[i]]:
            j += 1
        avg = (i+j)/2.0 + 1
        for t in range(i, j+1): r[order[t]] = avg
        i = j+1
    return r

allf = [r['frac'] for r in rows]
exf  = [r['frac'] for r in rows if r['k'] != 12]
stats(allf, 'ALL-FIVE ')
stats(exf,  'EXCL-K12 ')

x  = [r['f'] for r in rows]
xe = [r['f'] for r in rows if r['k'] != 12]
pa = pearson(x, allf); pe = pearson(xe, exf)
print('pearson_all  r=%.9f r2=%.9f' % (pa, pa*pa))
print('spearman_all r=%.9f' % pearson(rank(x), rank(allf)))
print('pearson_excl r=%.9f r2=%.9f' % (pe, pe*pe))
print('spearman_excl r=%.9f' % pearson(rank(xe), rank(exf)))
```

Output, verbatim:

```
ALL-FIVE  n=5 mean=0.039216037525 stdev=0.004616612077 min=0.032753433246 max=0.044653686728 spread=0.011900253482
         mean_pct=3.921604 stdev_pct=0.461661 spread_pct=1.190025
EXCL-K12  n=4 mean=0.038562949253 stdev=0.005057072356 min=0.032753433246 max=0.044653686728 spread=0.011900253482
         mean_pct=3.856295 stdev_pct=0.505707 spread_pct=1.190025
pearson_all  r=0.501953696 r2=0.251957513
spearman_all r=0.600000000
pearson_excl r=0.420775618 r2=0.177052121
spearman_excl r=0.400000000
```

Read out. **All five rows:** mean +3.9216 %, sample stdev 0.4617 %, min +3.2753 % (k = 7), max
+4.4654 % (k = 10), max−min spread **1.1900 %**. **Excluding k = 12:** mean +3.8563 %, sample stdev
0.5057 %, min and max unchanged (still k = 7 and k = 10), so the spread is unchanged at **1.1900 %**. The
exclusion moves the mean by 0.065 pp and the stdev by 0.044 pp; it moves the spread not at all, because
the two extreme bins are the same bins either way.

Trend of `delta_beta_frac` against `f_ghz_used` — **no trend test was pre-registered, so this is
descriptive only**: Pearson r = **0.5020** (r² = 0.2520), Spearman ρ = **0.6000** over all five; r = 0.4208
(r² = 0.1771), ρ = 0.4000 over the four. The fraction is **not monotone**: it dips to 3.275 % at k = 7,
rises to 4.465 % at k = 10, then falls back to 4.183 % at k = 12. That is a weak positive drift plus a
troughly U-shaped excursion, not a clean frequency dependence, and with five bins nothing stronger than
that should be read into it.

### 7.4 The `k = 12` caveat, up front

`beta_ambiguous` is **true** for k = 12 in the artefact and in `summary.json`, and false for the other
four. `build_A_50ohm_multifreq_summary.md` prints `ok` for all five rows — **this is not a conflict**: that
`status` column is the run-health column and the markdown carries no ambiguity column at all, so it cannot
contradict the artefact. Read the markdown as a health line, never as a bracket datum.

§6's rule is explicit: *a row with `beta_ambiguous` true is treated as a missing row for F1–F3 purposes and
counts toward F4's failure tally.* So the bracket count is **four rows** (k = 5, 7, 8, 10), with k = 12
excluded from F1–F3. (On the F4 side the script does not implement the "counts toward F4's failure tally"
clause — it reports `failures: 0, incomplete: 0, raised: 0` — so F4 is scored here on "all five rows
present and built", which they are; the discrepancy is named rather than smoothed over.)

Arithmetic of the exclusion, both ways. **With k = 12 included:** min = +3.2753 % (k = 7), max = +4.4654 %
(k = 10), spread = 1.1900 % > 1 %, and `beta_fit > beta_model` at 5 of 5 bins. **With k = 12 excluded:**
min = +3.2753 % (k = 7), max = +4.4654 % (k = 10) — the same two bins — spread = 1.1900 % > 1 %, and
`beta_fit > beta_model` at 4 of 4 bins. **The exclusion does not change which bracket fires:** F1 is
reached with five rows and with four.

### 7.5 F1–F4, applied literally

Each threshold is quoted from §5 verbatim, then the observed value. No bracket is scored beyond its own
wording.

| bracket | pre-registered threshold (§5, verbatim) | observed | verdict |
|---|---|---|---|
| **F1** | "`beta_fit` varies > 1 % across 3.64–8.74 GHz **and** sits above `beta_model` at every bin" | spread 1.190 % > 1 % (all five); `beta_fit` − `beta_model` = +4.013 %, +3.275 %, +3.671 %, +4.465 %, +4.183 %, positive at 5 of 5 bins. On the four non-ambiguous rows: spread 1.190 %, positive at 4 of 4. | **FIRES** |
| **F2** | "`beta_fit` stable to < 0.5 % **and** offset above `beta_model` roughly constant" | stdev 0.4617 % (all five) / 0.5057 % (four); the offset runs from +3.275 % to +4.465 %, a 1.1900 % spread, i.e. not constant. A conjunction requires both limbs. | **DOES NOT FIRE** (second limb) |
| **F3** | "`beta_fit` tracks `beta_model` within 1 % at every bin" | \|delta_beta_frac\| ≥ 3.275 % at all five bins; no bin lies within 1 %. | **DOES NOT FIRE** |
| **F4** | "cannot be built without editing `emfit/`, or fit/beta missing at ≥ 3 of 5 bins (script exits 5)" | built and run with no file under `emfit/` modified; `failures: 0, incomplete: 0, raised: 0`; a numeric `station_fit.beta` in 5 of 5 rows; the script did not exit 5. | **DOES NOT FIRE** |

**Post-hoc commentary** — labelled as such; none of it is part of the pre-registration.

- *F1, letter vs spirit:* the letter fires on a spread of 1.190 %, which clears the 1 % line by 0.19 pp, so
  "varies > 1 %" is met but not by much; the spirit — an offset best read as model-shaped rather than as a
  wrong beta — is supported by the offset being one-signed and of the same order at every bin, not by the
  margin.
- *F2, letter vs spirit:* §5's pre-registered prior expected F2 to be the likelier branch, and the letter
  contradicts that only because of the conjunction — the all-five stdev (0.4617 %) passes the 0.5 % limb
  while the offset limb fails, and on the four rows the pre-registration actually admits the stdev
  (0.5057 %) fails that limb too.
- *F3, letter vs spirit:* no divergence worth a sentence — 3.275 % is not near 1 %.
- *F4, letter vs spirit:* no divergence worth a sentence — the arm was built out of the library's existing
  public parameters, as §5 required, and no row is missing.

### 7.6 Provenance and limits

One geometry, one frequency axis: a **single load** (50 Ω in series at 20 mm), one board (`w = 3.2 mm`,
`h = 1.6 mm`, `eps_r = 4.4`, `n_line = 64`, 72×212×22 cells), **five** DFT bins, no replicate at any bin,
no second width, no second `eps_r`, and **no unloaded twin of the same board yet** — so nothing here
separates load-position error from extraction-model error, and F1's verdict is a statement about this load
at these five bins, not about the extraction model in general. Two provenance limits are stated plainly.
First, the exact command line that produced these artefacts is **not recoverable**: their `meta.argv` is
`null` because they predate the `sys.path` / `meta.argv` fix described in §4, so what is known about the
invocation is `meta.kwargs` and the artefacts' own `summary_line`, not the argv. Second, wall-clock per bin
was 43.7–70.46 s, which is cheap enough that a second width or an unloaded twin should be run **before**
any change to an extraction model is made on the strength of F1.
