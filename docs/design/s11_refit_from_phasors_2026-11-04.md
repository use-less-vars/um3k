# S11 refit from stored phasors

- Dispatch `s11-refit-from-phasors-2026-11-04`, 2026-11-04.
- DATA: **refit NOT possible from stored data - no per-station phasors are banked** (absent
  keys below). Unchanged.
- MECHANISM: **derived from source, not inferred** - one beta consumed twice (trace below).
- What the fix did: `s11.phase_deg` +59.764416639 deg (-160.26362819520853 ->
  -100.49921155605985); `s11.magnitude_one_wave_station_fit` 0.23216690987276836 ->
  0.32588679434738205 (x1.4036746); `s11.magnitude` bit-identical at 0.32556486641109117.

## Evidence: the phasors are absent (SUB-TASK 0)

- `build_A_50ohm_v3_betafix.json` top-level keys (names only): ac, gamma_plane, geometry,
  line, meta, run, s11, s11_at_plane, s21, summary_line. Pre-fix value in
  `build_A_50ohm_v3_zeff.json` (`s11.magnitude_one_wave_station_fit`, 18 artefacts share it).
- Exact-key scan, all 45 `evidence/termination/*build_A*.json` (48 paths repo-wide):
  `v_stations` 0 files, `i_stations` 0, `station_phasors` 0, `station_v` 0, `station_i` 0,
  `loss_fit.v` 0, `loss_fit.i` 0, `fit.gamma_v` 0, `fit_beta.gamma_v` 0, `gamma_v` 0.
  Only `beta` survives (45 files, as `line.beta`).
- 253 distinct key names; every phase/magnitude key is a scalar summary (gamma_plane,
  gamma_port, gamma_re/im, station_fit(_cells/_n/_span_m), deembed_gamma_used,
  deembedded_phase_deg) - none re-evaluable at another beta.

## Mechanism: derived, not inferred

- `fit_beta(z, v, n_wave=1)` (`ports.py:861`) takes NO beta argument; it RETURNS a `BetaFit`
  whose `beta`/`gamma` are self-consistent at the fitted beta (`gamma = backward/forward`, :963).
- `gamma_v = amp_v[1]/amp_v[0]` is computed in `fit_station_impedance(x, v, i, beta, ...)`
  (`ports.py:1429`) at `:1517`, from `_two_wave_fit(u, v, beta, alpha)` (`:1508`) - a linear
  least-squares projection at FIXED passed beta: `fit_two.beta` post-fix, `fit_one.beta` pre-fix
  (`studies.py:3387` -> `:3472`).
- Fit ORDER is ruled out: `_two_wave_fit` hardcodes order 2 (`_fit_design(u, beta, 2, alpha)`,
  `ports.py:1393`) and `fit_station_impedance` has no `n_wave` parameter; `n_wave` 1 vs 2 enters
  ONLY as which scalar beta is passed (286.35930483082825 pre, 231.55331672912826 post).
- So: **one beta consumed twice** - the fixed beta of the amplitude split producing `gamma_v`
  (`:1508`/`:1517`), and the plane-shift phase in `deembed_reflection` (`ports.py:1673`, called
  at `studies.py:3565`).
- Check: with real beta the de-embed cannot change modulus (guard `< 1e-9`, `studies.py:3572
  -3576`), so `|gamma_port| == |gamma_v|`; `res.gamma` = `complex(fit_two.gamma)`
  (`studies.py:3951`), at the fit's own beta, untouched by the fix - hence the bit-identical
  `s11.magnitude` beside a moved `|gamma_port|`.
- `magnitude_one_wave_station_fit` is a **stale name**: its amplitudes are an unconditional
  two-wave split (`ports.py:1508`); only the beta it consumed was one-wave.

## Status, numerical split, minimal change

- The +59.764416639 deg shift is +45.218186068 deg de-embed (`exp(-2j*beta*d)`, d = 0.0072,
  `ports.py:1673`) + 14.546230571 deg `gamma_v`; s21 -54.310700145 = -54.010611 + -0.300089.
  Exact additive decomposition - arithmetic, not a refit: the phasors are absent.
- `MicrostripWave` (`studies.py:1396`, `@dataclass` :1397) already carries `station_x` (:1591),
  `v_stations` (:1592), `i_stations` (:1593), read by the writer (`run_build_A.py:1415`): one
  payload block emitting `station_phasors: {x_m, v_re, v_im, i_re, i_im}` enables a real refit.

## Recommendation

1. Land the writer-only `station_phasors` block: a few lines, no re-run of the old grids, and
   every later beta question becomes an artefact refit instead of a field test.
2. Until then the deferred field test `s11-beta-test-2026-11-04` is the only route - and it is
   blocked: `ix_port = n_pml + n_ref = 8` is documented at `run_build_A.py:353` with `n_pml = 6`
   hardcoded (:298/:318/:331) and no `--ix-port` flag exists.
