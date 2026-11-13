"""MEASURED convergence sweep for the pulse passivity violation (diagnosis only).

Reproduces evidence/termination/run_build_A.py arm A (50 ohm series_r at 20 mm)
through emfit.studies.microstrip_wave and records, per run, exactly the two
numbers the driver's passivity_guard publishes:
    |S11| = |res.gamma|      (two-wave |B/A|, run_build_A.py:3396)
    |S21| = |res.s21|        (run_build_A.py:3387)
    power_sum = |S11|^2 + |S21|^2   (run_build_A.py:2161)
No tracked file is modified; nothing is written outside artifacts/.
"""
import json
import sys
import time

import numpy as np

import emfit.studies as S
from emfit.board import Load

OUT = "artifacts/passivity_sweep_A.json"

BASE = dict(
    h=1.6e-3, n_sub=4, n_air=12, n_top=6, n_strip=8, n_clean=96, n_pml=6,
    n_line=54, loads=(Load(0.02, "series_r", 50.0),), launch="lumped",
    flux_projection=False,
)
F_PULSE = 15.0e9          # run_build_A.py VIS_F_PULSE_HZ (artefact f_pulse)
CUT_COL = 51              # build_C_plain_cut.json run.kwargs s21_plane


def tail(v):
    v = np.asarray(v, dtype=float)
    n = v.size
    k = int(np.floor(0.9 * n))
    e = v * v
    tot = float(e.sum())
    pk = float(np.max(np.abs(v)))
    return dict(
        n_samples=int(n), n_tail=int(n - k),
        tail_energy_fraction=(float(e[k:].sum()) / tot if tot else None),
        tail_peak_ratio=(float(np.max(np.abs(v[k:]))) / pk if pk else None),
    )


def amp_ratio(res, zc):
    """|a+(last)/a+(first)| for the split zc the caller names."""
    a1, a2 = S.forward_wave_amplitude(
        res.v_stations, res.i_stations, res.station_x, 0j, complex(zc),
        indices=[0, -1])
    return dict(a1=complex(a1), a2=complex(a2),
                ratio=complex(a2) / complex(a1) if a1 != 0 else None,
                mag=(abs(complex(a2) / complex(a1)) if a1 != 0 else None))


def one(nsteps, excite, s21_plane):
    kw = dict(BASE, nsteps=nsteps, excite=excite, f_pulse=F_PULSE,
              s21_plane=s21_plane, load_trace=True)
    t0 = time.monotonic()
    res = S.microstrip_wave(**kw)
    wall = time.monotonic() - t0
    g = res.geometry
    s11 = abs(complex(res.gamma))
    s21 = abs(complex(res.s21))
    fit = res.station_fit
    rec = dict(
        nsteps=int(nsteps), excite=str(excite), s21_plane=s21_plane,
        wall_s=round(wall, 1),
        f0=float(g["f"]), dt=float(g["dt"]), n_warm=int(g["n_warm"]),
        n_acc=int(g["n_acc"]), band_lo=float(g["band_lo"]),
        band_hi=float(g["band_hi"]), n_bins=int(g["n_bins"]),
        s11_two_wave_mag=s11,
        s11_one_wave_mag=(abs(complex(fit.gamma_v)) if fit is not None else None),
        s21_mag=s21,
        s21_raw_mag=(abs(complex(res.s21_raw)) if res.s21_raw is not None else None),
        s21_planes=[float(x) for x in res.s21_planes],
        s21_plane_index=res.s21_plane_index,
        power_sum=s11 * s11 + s21 * s21,
        passivity_status=("FAIL_PASSIVITY"
                          if s11 * s11 + s21 * s21 > 1.0 + 4.0e-9 else None),
        beta=float(res.beta), beta_two_wave=float(res.beta_two_wave),
        beta_model=float(res.beta_model),
        gamma=complex(res.gamma), gamma_v=(complex(fit.gamma_v) if fit else None),
        zc=(complex(fit.z0) if fit else None),
        z0_model=(float(res.z0_model) if res.z0_model is not None else None),
        fit_residual=float(res.fit_residual),
        power_z0=(complex(res.power_z0) if res.power_z0 is not None else None),
        power_ratio=(float(res.power_ratio) if res.power_ratio is not None else None),
        loaded_without_reference=bool(res.loaded_without_reference),
        station_x=[float(x) for x in res.station_x],
        alt_split={},
        tail_v=(tail(res.load_trace_v) if res.load_trace_v is not None else None),
        tail_i=(tail(res.load_trace_i) if res.load_trace_i is not None else None),
    )
    # sensitivity of the published |S21| to the split impedance it was taken with
    for name, zc in (
            ("station_fit_z0", complex(fit.z0) if fit else None),
            ("zc_0j", 0j),
            ("power_z0", complex(res.power_z0) if res.power_z0 is not None else None),
    ):
        if zc is None:
            continue
        a = dict(amp_ratio(res, zc), zc=[zc.real, zc.imag])
        rec["alt_split"][name] = a
    print("RESULT "
          + json.dumps({k: rec[k] for k in (
              "nsteps", "excite", "s21_plane", "f0", "dt", "n_acc",
              "s11_two_wave_mag", "s21_mag", "power_sum", "passivity_status",
              "power_sum")}), flush=True)
    return rec


def main():
    runs = []
    plan = [
        (1200, "pulse", None), (2400, "pulse", None),
        (4800, "pulse", None), (9600, "pulse", None),
        (2400, "cw", CUT_COL), (2400, "cw", None),
    ]
    for nsteps, excite, plane in plan:
        sys.stderr.write(f"=== running nsteps={nsteps} excite={excite} "
                         f"s21_plane={plane}\n")
        sys.stderr.flush()
        try:
            runs.append(one(nsteps, excite, plane))
        except Exception as exc:  # noqa: BLE001 - a failed point is a result
            runs.append(dict(nsteps=nsteps, excite=excite, s21_plane=plane,
                             error=f"{type(exc).__name__}: {exc}"))
            sys.stderr.write(f"!!! FAILED {nsteps}/{excite}/{plane}: {exc}\n")
        with open(OUT, "w") as fh:
            json.dump(dict(plan=plan, runs=runs), fh, indent=1, default=str)
    sys.stderr.write(f"=== wrote {OUT}\n")


if __name__ == "__main__":
    main()
