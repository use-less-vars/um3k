"""M4: is the analysed tone inside the f_pulse=15 GHz Ricker's band? No solver.

Cheap, MEASURED from the same expressions the solver uses:
  * f0 per step count, from emfit.studies.snapped_tone with n_warm=0 (the pulse
    path, emfit/studies.py:3233),
  * the drive's own spectrum: the DFT bin the pulse accumulator reads,
    sum_n ricker(n dt, 2/fmax, fmax) exp(-2 pi i f0 n dt) over the record, and
    the same sum at every other bin of the record, i.e. where the drive's energy
    actually is,
  * the analytic envelope |X(f)| ~ f^2 exp(-(f/fmax)^2).
"""
import json

import numpy as np

import emfit.studies as S
from emfit.evolve import ricker

# dt of the arm-A mesh (h=1.6mm/n_sub=4, fit-leapfrog):
# run_build_A.py records 1800*dt = 1.3727339060623177e-9 s at nsteps=2400.
DT = 1.3727339060623177e-9 / 1800.0
FMAX = 15.0e9
F_TARGET = 6.0e9
BAND_LO, BAND_HI = S.MS_BAND_LO_GHZ * 1e9, S.MS_BAND_HI_GHZ * 1e9
F_PUBLISHED = 6.009904733588e9     # build_C_plain_cut_pulse.json f0

out = {"dt": DT, "f_pulse_hz": FMAX, "band_lo_hz": BAND_LO,
       "band_hi_hz": BAND_HI, "f0_published_hz": F_PUBLISHED,
       "f0_published_in_band": bool(BAND_LO <= F_PUBLISHED <= BAND_HI),
       "f0_published_over_fmax": F_PUBLISHED / FMAX,
       "analytic_envelope_ratio": {
           "form": "|X(f)| ~ f^2 exp(-(f/fmax)^2), ratio to its own peak at fmax",
           "value": float((F_PUBLISHED ** 2 * np.exp(-(F_PUBLISHED / FMAX) ** 2))
                          / (FMAX ** 2 * np.exp(-1.0)))},
       "analytic_db": float(20.0 * np.log10(
           (F_PUBLISHED ** 2 * np.exp(-(F_PUBLISHED / FMAX) ** 2))
           / (FMAX ** 2 * np.exp(-1.0)))),
       "per_nsteps": []}

for nsteps in (1200, 2400, 4800, 9600):
    k = int(round(F_TARGET * nsteps * DT / 1.0))
    k = max(1, min(nsteps // 2 - 1, k))
    f0 = k / (nsteps * DT)
    t = np.arange(nsteps) * DT
    w = np.asarray([ricker(x, 2.0 / FMAX, FMAX) for x in t], dtype=float)
    n = np.arange(nsteps)
    def binamp(f):
        return float(abs(np.sum(w * np.exp(-2j * np.pi * f * n * DT))))
    a0 = binamp(f0)
    # every DFT bin of the record that lies in the reported sweep band
    spec = np.abs(np.fft.rfft(w))
    freqs = np.fft.rfftfreq(nsteps, DT)
    inband = (freqs >= BAND_LO) & (freqs <= BAND_HI)
    ipk = int(np.argmax(spec))
    iband = np.flatnonzero(inband)
    band_pk = float(spec[iband].max()) if iband.size else None
    rec = dict(
        nsteps=nsteps, k=k, f0=f0, f0_ghz=f0 / 1e9, n_warm=0,
        drive_bin_amp=a0,
        drive_peak_freq_hz=float(freqs[ipk]),
        drive_peak_amp=float(spec[ipk]),
        drive_bin_over_peak=a0 / float(spec[ipk]),
        drive_bin_over_peak_db=float(20 * np.log10(a0 / float(spec[ipk]))),
        band_peak_freq_hz=(float(freqs[iband][int(np.argmax(spec[iband]))])
                           if iband.size else None),
        band_peak_amp=band_pk,
        drive_bin_over_band_peak=(a0 / band_pk if band_pk else None),
        band_energy_fraction=float(spec[inband].__pow__(2).sum()
                                   / spec.__pow__(2).sum()),
        f0_in_band=bool(BAND_LO <= f0 <= BAND_HI),
        ricker_useful_top_hz=2.5 * FMAX,
    )
    out["per_nsteps"].append(rec)
    print("M4 nsteps=%d f0=%.6f GHz bin_amp/peak=%.6f (%.2f dB) "
          "band_peak=%.3f GHz f0_in_band=%s band_energy_frac=%.4f"
          % (nsteps, f0 / 1e9, rec["drive_bin_over_peak"],
             rec["drive_bin_over_peak_db"],
             (rec["band_peak_freq_hz"] or 0.0) / 1e9, rec["f0_in_band"],
             rec["band_energy_fraction"]), flush=True)

# the CW reference tone, for contrast (n_warm = nsteps//4)
cw = []
for nsteps in (2400,):
    n_warm = nsteps // 4
    f0 = 5.827786408327286e9
    cw.append(dict(nsteps=nsteps, n_warm=n_warm, f0=f0,
                   band_lo=S.MS_BAND_LO_GHZ * 1e9, band_hi=S.MS_BAND_HI_GHZ * 1e9,
                   ricker_peak_hz=FMAX))
out["cw"] = cw

with open("artifacts/passivity_m4_band.json", "w") as fh:
    json.dump(out, fh, indent=1)
print("wrote artifacts/passivity_m4_band.json", flush=True)
