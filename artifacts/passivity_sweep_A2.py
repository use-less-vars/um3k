"""MEASURED passivity attribution sweep, arm A (diagnosis only).

Same harness as artifacts/passivity_sweep_A.py (recovers it verbatim) but every
recorded field goes through a ravel-safe coercer, and every diagnostic block is
wrapped so a diagnostic can never kill a row.

M1 transient truncation      -> pulse at nsteps 1200/2400/4800/9600
M2 split-impedance bias      -> per-run pure post-processing of a+/a- for
                                zc = published station_fit.z0, 50+0j, 0j, power_z0
M3 branch-excitation confound-> pulse vs cw, both s21_plane=None (station span)
M4 tone outside pulse band   -> see artifacts/passivity_m4_band.py (no solver)

No tracked file is modified; nothing is written outside artifacts/.
"""
import json
import sys
import time

import numpy as np

import emfit.studies as S
from emfit.board import Load

OUT = "artifacts/passivity_sweep_A2.json"

BASE = dict(
    h=1.6e-3, n_sub=4, n_air=12, n_top=6, n_strip=8, n_clean=96, n_pml=6,
    n_line=54, loads=(Load(0.02, "series_r", 50.0),), launch="lumped",
    flux_projection=False,
)
F_PULSE = 15.0e9          # run_build_A.py VIS_F_PULSE_HZ (artefact f_pulse)
CUT_COL = 51              # build_C_plain_cut.json run.kwargs s21_plane


# --- every scalar that leaves here goes through one of these ----------------
def _f(x):
    return float(np.asarray(x, dtype=float).ravel()[0])


def _i(x):
    return int(np.asarray(x).ravel()[0])


def _c(x):
    a = np.asarray(x, dtype=complex).ravel()[0]
    return [float(a.real), float(a.imag)]


def _cm(x):
    """magnitude of a phasor whose shape is not trusted"""
    return float(abs(complex(np.asarray(x, dtype=complex).ravel()[0])))


def _arr_mag(x):
    return [float(v) for v in np.abs(np.asarray(x, dtype=complex).ravel())]


def _opt(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as exc:                                  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def tail(v):
    v = np.asarray(v, dtype=float).ravel()
    n = v.size
    e = v * v
    tot = float(e.sum())
    pk = float(np.max(np.abs(v))) if n else 0.0
    out = dict(n_samples=int(n))
    for frac in (0.10, 0.25):
        k = int(np.floor((1.0 - frac) * n))
        out[f"tail_fraction_{int(frac * 100)}pct"] = (
            float(e[k:].sum()) / tot if tot else None)
    out["peak_ratio_in_last_10pct"] = (
        float(np.max(np.abs(v[int(np.floor(0.9 * n)):]))) / pk if pk else None)
    out["argmax_frac"] = (float(np.argmax(np.abs(v))) / n if n else None)
    out["first_over_peak"] = (float(abs(v[0])) / pk if pk else None)
    out["rms"] = float(np.sqrt(tot / n)) if n else None
    return out


def splits(res):
    """a+/a- per station for each split impedance, pure post-processing.

    gamma=0j exactly as the published pulse path passes it
    (emfit/studies.py:3104-3106): A = (v + zc i)/2, B = (v - zc i)/2.
    """
    v = np.asarray(res.v_stations, dtype=complex).ravel()
    i = np.asarray(res.i_stations, dtype=complex).ravel()
    out = {}
    cands = [("zc_published", res.station_fit.z0 if res.station_fit else None),
             ("zc_50", 50.0 + 0j),
             ("zc_0j", 0j),
             ("zc_power", (res.power_z0[0] if res.power_z0 is not None else None))]
    for name, zc in cands:
        if zc is None:
            continue
        try:
            zc = complex(np.asarray(zc, dtype=complex).ravel()[0])
            ap = 0.5 * (v + zc * i)
            am = 0.5 * (v - zc * i)
            ratio = ap[-1] / ap[0] if ap[0] != 0 else None
            rec = dict(zc=[zc.real, zc.imag],
                       a_plus_abs=[float(x) for x in np.abs(ap)],
                       a_minus_abs=[float(x) for x in np.abs(am)],
                       a_minus_over_a_plus=[float(a / b) if b else None
                                            for a, b in zip(np.abs(am),
                                                            np.abs(ap))],
                       ratio_mag=(abs(ratio) if ratio is not None else None),
                       ratio=_c(ratio) if ratio is not None else None)
            if ratio is not None:
                s21, raw = S.line_s21(ap[0], res.s21_planes[0],
                                      ap[-1], res.s21_planes[1], res.beta)
                rec["line_s21_mag"] = _cm(s21)
                rec["line_s21"] = _c(s21)
            out[name] = rec
        except Exception as exc:                              # noqa: BLE001
            out[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def one(nsteps, excite, s21_plane):
    kw = dict(BASE, nsteps=nsteps, excite=excite, f_pulse=F_PULSE,
              s21_plane=s21_plane, load_trace=True)
    t0 = time.monotonic()
    res = S.microstrip_wave(**kw)
    wall = time.monotonic() - t0
    g = res.geometry
    fit = res.station_fit
    rec = dict(
        nsteps=int(nsteps), excite=str(excite), s21_plane=s21_plane,
        wall_s=round(wall, 1),
        f0=_f(g["f"]), dt=_f(g["dt"]), n_warm=_i(g["n_warm"]),
        n_acc=_i(g["n_acc"]),
        window_s=_f(g["n_acc"]) * _f(g["dt"]),
        band_lo=_f(g["band_lo"]), band_hi=_f(g["band_hi"]),
        n_bins=_i(g["n_bins"]), f_pulse=_f(g["f_pulse"]),
        s11_mag=_cm(res.gamma),
        s11_one_wave_mag=_cm(fit.gamma_v) if fit is not None else None,
        s21_mag=_cm(res.s21),
        s21_raw_mag=_cm(res.s21_raw) if res.s21_raw is not None else None,
        s21_planes=[float(x) for x in res.s21_planes],
        s21_plane_index=(_i(res.s21_plane_index)
                         if res.s21_plane_index is not None else None),
        status=None,
        beta=_f(res.beta), beta_two_wave=_f(res.beta_two_wave),
        beta_model=_f(res.beta_model),
        gamma_re=_f(np.real(res.gamma)), gamma_im=_f(np.imag(res.gamma)),
        gamma_two_wave=None, fit_residual=_f(res.fit_residual),
        zc_published=_c(fit.z0) if fit is not None else None,
        z0_model=(_f(res.z0_model) if res.z0_model is not None else None),
        power_z0=[_c(x) for x in np.asarray(res.power_z0).ravel()],
        power_ratio=[_f(x) for x in np.asarray(res.power_ratio).ravel()],
        power_z0_port=(_f(res.power_z0_port)
                       if res.power_z0_port is not None else None),
        loaded_without_reference=bool(res.loaded_without_reference),
        station_fit_ok=bool(res.station_fit_ok),
        station_x_mm=[float(x) * 1e3 for x in np.asarray(res.station_x).ravel()],
        v_abs=_arr_mag(res.v_stations), i_abs=_arr_mag(res.i_stations),
        gamma_two_wave_attr=_opt(lambda: _c(res.gamma)),
        n_bins_rows=(_opt(lambda: len(res.bins)) if res.bins else 0),
    )
    s11, s21 = rec["s11_mag"], rec["s21_mag"]
    rec["power_sum"] = s11 * s11 + s21 * s21
    rec["status"] = ("FAIL_PASSIVITY"
                     if rec["power_sum"] > 1.0 + 4.0e-9 else "ok")
    rec["headroom_s21_at_gate"] = float(np.sqrt(max(0.0, 1.0 + 4.0e-9 - s11 * s11)))
    rec["s21_upper_bound_passive"] = rec["headroom_s21_at_gate"]
    rec["split_by_zc"] = _opt(splits, res)
    rec["tail_v"] = (_opt(tail, res.load_trace_v)
                     if res.load_trace_v is not None else None)
    rec["tail_i"] = (_opt(tail, res.load_trace_i)
                     if res.load_trace_i is not None else None)
    # one-line MEASURED print per row
    sys.stderr.write(
        "ROW nsteps=%d excite=%s plane=%s f0=%.6fGHz s11=%.6f s21=%.6f "
        "sum=%.9f %s | beta=%.3f beta2=%.3f g_re=%.6f zc=%.3f%+.3fj "
        "tailv10=%s\n" % (
            rec["nsteps"], rec["excite"], rec["s21_plane"], rec["f0"] / 1e9,
            s11, s21, rec["power_sum"], rec["status"], rec["beta"],
            rec["beta_two_wave"], rec["gamma_re"],
            rec["zc_published"][0] if rec["zc_published"] else float("nan"),
            rec["zc_published"][1] if rec["zc_published"] else float("nan"),
            (rec["tail_v"] or {}).get("tail_fraction_10pct")))
    sys.stderr.flush()
    return rec


PLAN = [
    (2400, "pulse", None),      # row 1: MUST reproduce 1.151030784330
    (2400, "cw", None),         # row 2: M3 discriminator (pulse vs tone, span)
    (1200, "pulse", None),      # rows 3-5: M1
    (4800, "pulse", None),
    (9600, "pulse", None),
    (2400, "cw", CUT_COL),      # row 6: the published PASSING cut run (0.686382)
]


def main():
    runs = []
    for nsteps, excite, plane in PLAN:
        sys.stderr.write(f"=== running nsteps={nsteps} excite={excite} "
                         f"s21_plane={plane}\n")
        sys.stderr.flush()
        try:
            runs.append(one(nsteps, excite, plane))
        except Exception as exc:                              # noqa: BLE001
            runs.append(dict(nsteps=nsteps, excite=excite, s21_plane=plane,
                             error=f"{type(exc).__name__}: {exc}"))
            sys.stderr.write(f"!!! FAILED {nsteps}/{excite}/{plane}: "
                             f"{type(exc).__name__}: {exc}\n")
        with open(OUT, "w") as fh:
            json.dump(dict(plan=PLAN, base=str(BASE), f_pulse_hz=F_PULSE,
                           cut_col=CUT_COL, runs=runs), fh, indent=1)
    sys.stderr.write(f"=== wrote {OUT}\n")


if __name__ == "__main__":
    main()
