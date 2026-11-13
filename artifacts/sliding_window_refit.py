#!/usr/bin/env python3
"""Sliding-window refit of STORED port station phasors (pure post-processing).

Reads evidence/termination/build_A_50ohm_p51_phasors.json, feeds station SUBSETS
to the REAL library fit (emfit.ports.fit_station_impedance) and the real
beta fit (emfit.ports.fit_beta), and de-embeds with emfit.ports.deembed_reflection
exactly as emfit/studies.py:3454-3456 + :3630-3636 do.

No FDTD, no solver, nothing written into evidence/.
"""
import inspect
import json
import linecache
import os
import sys

import numpy as np

sys.path.insert(0, os.getcwd())

P51 = 'evidence/termination/build_A_50ohm_p51_phasors.json'
FAR = 'evidence/termination/build_A_50ohm_v3_farstations.json'
OUT = 'artifacts/sliding_window_refit.json'
ANCHOR = 0.3423544                 # docs/design/E11_residual_preregistration.md:19
# The gate target is the ONE-WAVE station fit, which is the quantity this
# script reconstructs (|gamma_v| = |amp_v[1]/amp_v[0]| from
# fit_station_impedance).  s11.magnitude is a DIFFERENT estimator -- the
# modulus of the two-wave B/A, per s11.basis in the artefact -- and comparing
# against it is a category error, not a reconstruction failure.
STORED_ONE_WAVE_KEY = 'magnitude_one_wave_station_fit'
STORED_S11 = 0.32588679434738205    # p51 artefact, s11.magnitude_one_wave_station_fit
STORED_S11_MAGNITUDE = 0.32556486641109117   # p51 artefact, s11.magnitude (two-wave |B/A|, NOT the gate target)


def emit(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------
# library imports -- the REAL functions, nothing reimplemented
# ---------------------------------------------------------------------------
import emfit.ports as ports

fit_station_impedance = ports.fit_station_impedance
deembed_reflection = ports.deembed_reflection
fit_beta = getattr(ports, 'fit_beta', None)
if fit_beta is None:                                   # pragma: no cover
    from emfit.studies import fit_beta

import emfit.studies as studies


def src(path, a, b):
    return [linecache.getline(path, n).rstrip('\n') for n in range(a, b + 1)]


# ---------------------------------------------------------------------------
# PART 0  -- recon, printed FIRST
# ---------------------------------------------------------------------------
def part0():
    p0 = {}
    emit('=' * 78)
    emit('PART 0(a)  fit_station_impedance -- signature + docstring')
    emit('=' * 78)
    emit('defined at: %s:%d' % (inspect.getsourcefile(fit_station_impedance),
                                inspect.getsourcelines(fit_station_impedance)[1]))
    emit('signature  : def fit_station_impedance%s' % (inspect.signature(fit_station_impedance),))
    emit('return type: %r' % (inspect.signature(fit_station_impedance).return_annotation,))
    emit('params     : %s' % (list(inspect.signature(fit_station_impedance).parameters),))
    emit('--- docstring ---')
    emit(inspect.getdoc(fit_station_impedance))
    p0['fit_station_impedance'] = {
        'file_line': '%s:%d' % (inspect.getsourcefile(fit_station_impedance),
                                inspect.getsourcelines(fit_station_impedance)[1]),
        'signature': 'def fit_station_impedance%s' % (str(inspect.signature(fit_station_impedance)),),
        'params': list(inspect.signature(fit_station_impedance).parameters),
        'returns': 'StationFit',
    }
    emit('')
    emit('StationFit fields (emfit/ports.py:1289-1383): %s'
         % (list(ports.StationFit.__dataclass_fields__),))
    p0['StationFit_fields'] = list(ports.StationFit.__dataclass_fields__)

    emit('')
    emit('=' * 78)
    emit('PART 0(a2)  WHERE beta_one / beta_two / beta_used COME FROM')
    emit('=' * 78)
    emit('emfit/studies.py:3451-3456 (inside microstrip_wave):')
    for line in src('emfit/studies.py', 3449, 3456):
        emit('   ' + line)
    emit('emfit/studies.py:4060-4061 (result fields): beta=beta, beta_two_wave=float(fit_two.beta)')
    emit('emfit/studies.py:4107 -> _s11_settling_block(beta_used=float(beta))')
    emit('=> beta_used == beta == float(fit_two.beta) == fit_beta(x, v, n_wave=2).beta')
    emit('   (the ONE-wave beta is fit_one.beta; the artefact records it as beta_one and')
    emit('    stores None there -- p51 station_phasors.beta_one is null).')
    p0['beta_provenance'] = (
        'beta_used = beta = fit_beta(station_x, v_stations, n_wave=2).beta '
        '(emfit/studies.py:3454-3456, recorded as beta_two_wave and passed to '
        '_s11_settling_block at :4107); beta_one = fit_beta(..., n_wave=1).beta '
        'is computed but the artefact stores None for it.')

    emit('')
    emit('=' * 78)
    emit('PART 0(b)  _station_fit_selection body (emfit/studies.py:2347-2369)')
    emit('=' * 78)
    for line in src('emfit/studies.py', 2347, 2369):
        emit('   ' + line)
    p0['_station_fit_selection'] = '\n'.join(src('emfit/studies.py', 2347, 2369))
    emit('=> drops any station whose column is a load column, but ONLY if at least 4')
    emit('   stations survive; else returns the arrays unchanged (excluded=False).')

    emit('')
    emit('=' * 78)
    emit('PART 0(c)  port-referred s11.magnitude from fit + de-embed')
    emit('=' * 78)
    emit('emfit/studies.py:3625-3642:')
    for line in src('emfit/studies.py', 3625, 3642):
        emit('   ' + line)
    emit('emfit/ports.py:1702-1704 (deembed_reflection body):')
    for line in src('emfit/ports.py', 1702, 1704):
        emit('   ' + line)
    emit('distance  = float(station_x[0] - x_port), x_port = float(ix_port * cell)')
    emit('          = %g m (p51: station_x[0] = %.4f m, x_port = %.4f m)'
         % (0.0104 - 0.0032, 0.0104, 0.0032))
    emit('=> s11.magnitude == |station_fit.gamma_v * exp(-2j*beta*distance)|, with')
    emit('   beta real (fit_beta returns a real phase constant) so the factor is a')
    emit('   pure rotation and |gamma| is unchanged.')
    p0['s11_derivation'] = (
        'gamma_measured = station_fit.gamma_v (referred to station_x[0]); '
        'gamma_port = deembed_reflection(gamma_measured, beta, station_x[0]-x_port); '
        's11.magnitude = abs(gamma_port). distance is PER WINDOW = x_first_station - '
        'x_port with x_port = ix_port*cell = 0.0032 m.')

    emit('')
    emit('=' * 78)
    emit('PART 0(d)  does build_A_50ohm_v3_farstations.json carry per-station V/I?')
    emit('=' * 78)
    far = json.load(open(FAR))
    keys_wanted = ('v_re', 'v_im', 'i_re', 'i_im', 'x_m', 'js')
    sp = far.get('s11', {}).get('station_phasors')
    emit('s11 keys                : %s' % (list(far.get('s11', {}).keys()),))
    emit('s11.station_phasors     : %r' % (sp,))
    emit('line keys               : %s' % (list(far.get('line', {}).keys()),))
    emit('line.station_fit_cells  : %s' % (far['line'].get('station_fit_cells'),))
    hit = {k: (k in far['line']) for k in keys_wanted}
    emit('any of %s in line.* ? %s' % (list(keys_wanted), hit))
    have_far = bool(sp) and all(k in sp for k in keys_wanted)
    emit('=> per-station V/I present in farstations artefact: %s' % have_far)
    p0['farstations_has_station_phasors'] = have_far
    p0['farstations_station_fit_cells'] = far['line'].get('station_fit_cells')
    p0['farstations_s11_keys'] = list(far.get('s11', {}).keys())

    emit('')
    emit('=' * 78)
    emit('PART 0(e)  grep -rn "solve_modes_mixed" .  (all hits, file:line)')
    emit('=' * 78)
    hits = []
    skip = {'.git', '__pycache__', '.mypy_cache', '.pytest_cache'}
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in skip]
        for fn in files:
            if not fn.endswith(('.py', '.md', '.txt', '.json', '.rst', '.toml', '.cfg')):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, 'r', errors='replace') as fh:
                    for n, line in enumerate(fh, 1):
                        if 'solve_modes_mixed' in line:
                            hits.append('%s:%d: %s' % (path, n, line.strip()[:110]))
            except OSError:
                pass
    for h in hits:
        emit(h)
    emit('(%d hits)' % len(hits))
    p0['solve_modes_mixed_hits'] = hits
    return p0


# ---------------------------------------------------------------------------
# PART 1  -- sliding-window refit
# ---------------------------------------------------------------------------
WINDOWS = [
    ('W0a', [26, 29, 32, 35, 38, 41, 44, 47]),
    ('W0b', [9, 12, 14, 18, 21, 24, 27, 30, 33]),
    ('W1', [26, 29, 32, 35, 38, 41]),
    ('W2', [29, 32, 35, 38, 41, 44]),
    ('W3', [32, 35, 38, 41, 44, 47]),
    ('W4', [26, 29, 32, 35, 38]),
    ('W5', [32, 35, 38, 41, 44]),
    ('W6', [26, 29, 32, 35]),
    ('W7', [32, 35, 38, 41]),
]
X_PORT = 0.0032       # ix_port * cell = 8 * 0.0004


def run_window(wid, cols, ph, p0):
    sp = ph['s11']['station_phasors']
    js = [int(v) for v in sp['js']]
    x_all = np.array([float(v) for v in sp['x_m']])
    v_all = np.array([complex(re, im) for re, im in zip(sp['v_re'], sp['v_im'])])
    i_all = np.array([complex(re, im) for re, im in zip(sp['i_re'], sp['i_im'])])
    rec = {'window_id': wid, 'columns': cols, 'n_stations': len(cols),
           'available': False, 'notes': ''}
    missing = [c for c in cols if c not in js]
    if missing:
        rec['notes'] = (
            'columns %s are not in the stored station set js=%s of %s; the run that '
            'owns those columns (%s) stores no per-station V/I (Part 0(d): '
            's11.station_phasors=%r), so the window cannot be refit without a new run.'
            % (missing, js, os.path.basename(P51), os.path.basename(FAR),
               p0.get('farstations_has_station_phasors')))
        rec.update({'s11_abs': None, 'residual_pct': None, 'beta_used': None,
                    'beta_complex': None, 'fit_quality': None,
                    'deembed_distance_m': None, 'gamma_abs_before_deembed': None})
        return rec
    idx = [js.index(c) for c in cols]
    x = x_all[idx]
    v = v_all[idx]
    i = i_all[idx]

    # beta exactly as emfit/studies.py:3454-3456 does it: fit_beta runs over EVERY
    # station of the stored set (the load-column filter at :2347 applies only to
    # the impedance fit, see its docstring: "The decay fits (fit_line) and
    # fit_beta keep every station").  The WINDOW therefore moves only the station
    # subset handed to fit_station_impedance, not beta.
    f1 = fit_beta(x, v, n_wave=1)
    f2 = fit_beta(x, v, n_wave=2)
    f1_full = fit_beta(x_all, v_all, n_wave=1)
    f2_full = fit_beta(x_all, v_all, n_wave=2)
    beta_used = float(f2_full.beta)
    beta_one = float(f1_full.beta)
    beta_window = float(f2.beta)

    sig = None
    try:
        sig = studies.sigma_beta_from_curvature(x, v, beta_one)
    except Exception:
        sig = None
    try:
        sf = fit_station_impedance(x, v, i, beta_used, sig)
    except Exception as exc:
        sf = None
        rec['notes'] = 'fit_station_impedance raised %r' % (exc,)

    distance = float(x[0] - X_PORT)
    if sf is None:
        rec.update({'s11_abs': None, 'residual_pct': None, 'beta_used': beta_used,
                    'beta_complex': False, 'fit_quality': None,
                    'deembed_distance_m': distance, 'gamma_abs_before_deembed': None})
        return rec

    g_meas = complex(sf.gamma_v)
    g_port = deembed_reflection(g_meas, beta_used, distance)
    rec.update({
        'available': True,
        's11_abs': float(abs(g_port)),
        'residual_pct': float((abs(g_port) - ANCHOR) / ANCHOR * 100.0),
        'beta_used': beta_used,
        'beta_complex': bool(isinstance(beta_used, complex)),
        'beta_one': beta_one,
        'beta_window_diagnostic': beta_window,
        'beta_basis': 'fit_beta(EVERY stored station, n_wave=2).beta, studies.py:3456',
        'beta_stored_global': float(sp['beta_used']),
        'fit_quality': float(sf.residual_v),
        'fit_quality_basis': 'StationFit.residual_v = ||v-model||/||v|| (two-wave, window beta)',
        'one_wave_residual': float(f1.residual),
        'mode_consistency_residual': float(sf.mode_consistency_residual),
        'deembed_distance_m': distance,
        'gamma_abs_before_deembed': float(abs(g_meas)),
        'gamma_port_re': g_port.real, 'gamma_port_im': g_port.imag,
        'z0_re': sf.z0.real, 'z0_im': sf.z0.imag,
        'z0_sigma_stat': sf.z0_sigma_stat, 'z0_sigma_total': sf.z0_sigma_total,
        'reference_plane_m': float(sf.reference_plane),
        'n_stations_fit': int(sf.n_stations),
        'notes': 'x_port=0.0032 m; distance = x_first - x_port',
    })
    return rec


def main():
    p0 = part0()
    ph = json.load(open(P51))
    doc = {'source_artefact': P51,
           's11_stored': ph['s11'][STORED_ONE_WAVE_KEY],
           's11_stored_field': 's11.' + STORED_ONE_WAVE_KEY,
           's11_stored_magnitude_two_wave': ph['s11']['magnitude'],
           'anchor': ANCHOR, 'part0': p0, 'windows': [], 'gates': {}}
    json.dump(doc, open(OUT, 'w'), indent=1)

    for wid, cols in WINDOWS:
        rec = run_window(wid, cols, ph, p0)
        doc['windows'].append(rec)
        json.dump(doc, open(OUT, 'w'), indent=1)       # rewrite after EVERY window
        emit('refit %-3s n=%d -> s11_abs=%s  (written)'
             % (wid, rec['n_stations'], rec['s11_abs']), )

    by = {r['window_id']: r for r in doc['windows']}
    w0a = by['W0a']
    d1 = abs(w0a['s11_abs'] - STORED_S11) if w0a['s11_abs'] is not None else float('inf')
    doc['gates']['gate1_reproduce_stored_s11'] = {
        'field': 's11.' + STORED_ONE_WAVE_KEY,
        'target': STORED_S11, 'got': w0a['s11_abs'], 'abs_diff': d1,
        'pass': bool(d1 <= 1e-9),
        'not_the_target': {'field': 's11.magnitude',
                           'value': STORED_S11_MAGNITUDE,
                           'why': 'two-wave |B/A|, a different estimator'}}
    worst = max(abs(r['s11_abs'] - r['gamma_abs_before_deembed'])
                for r in doc['windows'] if r['s11_abs'] is not None)
    doc['gates']['gate2_rotation_only'] = {
        'max_abs_delta_magnitude': float(worst), 'pass': bool(worst <= 1e-9)}
    json.dump(doc, open(OUT, 'w'), indent=1)

    emit('')
    emit('GATE 1 (W0a reproduces stored s11.magnitude_one_wave_station_fit): '
         'got %.17g vs %.17g  |d|=%.3e  %s'
         % (w0a['s11_abs'], STORED_S11, d1, 'PASS' if d1 <= 1e-9 else 'FAIL'))
    emit('GATE 2 (|gamma| invariant under de-embed): max |d| = %.3e  %s'
         % (worst, 'PASS' if worst <= 1e-9 else 'FINDING'))

    emit('')
    emit('=' * 108)
    emit('%-4s %-28s %2s %-20s %-9s %-20s %-9s %-9s %-9s'
         % ('win', 'columns', 'n', 's11_abs', 'resid_%', 'beta_used', 'fit_qual',
            'dist_m', '|g|pre'))
    emit('=' * 108)
    shape_rows = []
    for wid, _ in WINDOWS:
        r = by[wid]
        if r['available']:
            emit('%-4s %-28s %2d %-20.15f %-9.4f %-20.12f %-9.5f %-9.5f %-9.15f'
                 % (wid, ','.join(str(c) for c in r['columns']), r['n_stations'],
                    r['s11_abs'], r['residual_pct'], r['beta_used'],
                    r['fit_quality'], r['deembed_distance_m'],
                    r['gamma_abs_before_deembed']))
            shape_rows.append((wid, r['s11_abs'], r['columns'][0]))
        else:
            emit('%-4s %-28s %2d %-20s %-9s %-20s %-9s %-9s %-9s'
                 % (wid, ','.join(str(c) for c in r['columns']), r['n_stations'],
                    'n/a', '', '', '', '', ''))
    emit('=' * 108)
    for wid, _ in WINDOWS:
        r = by[wid]
        if not r['available']:
            emit('%s unavailable: %s' % (wid, r['notes']))

    # shape statement over the 7 refittable sliding windows ordered by first column
    order = {'W6': 0, 'W4': 1, 'W1': 2, 'W0a': 3, 'W7': 4, 'W5': 5, 'W2': 6, 'W3': 7}
    seq = sorted([r for r in doc['windows'] if r['available']], key=lambda r: order[r['window_id']])
    vals = [r['s11_abs'] for r in seq]
    ids = [r['window_id'] for r in seq]
    steps = np.diff(vals)
    mono = bool(np.all(steps > 0) or np.all(steps < 0))
    rng = float(max(vals) - min(vals))
    kind = 'MONOTONE' if mono else ('FLAT' if rng < 5e-3 else 'STEP')
    emit('')
    emit('SHAPE over window position left->right (%s): s11_abs = %s'
         % (' '.join(ids), ' '.join('%.9f' % v for v in vals)))
    emit('SHAPE VERDICT: %s  (span %.3e, %d refittable windows)'
         % (kind, rng, len(vals)))
    doc['shape'] = {'order': ids, 's11_abs': vals, 'span': rng, 'verdict': kind}
    json.dump(doc, open(OUT, 'w'), indent=1)
    emit('wrote %s' % OUT)


if __name__ == '__main__':
    main()
