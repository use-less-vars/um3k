"""58.5 -- ripple / periodicity diagnostics on the d585_sweep station dumps.

Reads the .npz files written by ``d585_sweep.py`` (``dump`` key) and prints
plain numeric tables: phase increment, detrended amplitude and phase residuals
with their FFTs, and the pair-by-pair correlation between the local decay rate
alpha_i and the reflected amplitude ratio r_i = |a_b|/|a_f|.

    python -u tools/d585_ripple.py
"""

from __future__ import annotations

import numpy as np

H_MM = 0.2                      # one cell in mm
CELL = H_MM * 1e-3              # 2.0e-4 m
BETA_REF = 381.16               # /m, reference propagation constant

FILES = ["/workspace/.scratch/d585/w3h.npz",
         "/workspace/.scratch/d585/nx140.npz"]


def detrend(y, xx):
    A = np.vstack([xx, np.ones_like(xx)]).T
    (slope, inter), *_ = np.linalg.lstsq(A, y, rcond=None)
    return slope, inter, y - (slope * xx + inter)


def fft_peak(resid, ds_cells):
    n = resid.size
    X = np.fft.rfft(resid)
    amp = 2.0 * np.abs(X) / n
    amp[0] = 0.0
    k = int(np.argmax(amp))
    if k == 0:
        return float("nan"), float("nan"), float(amp[0]), 0.0
    period_cells = n * ds_cells / k
    # parabolic interpolation around the peak for a finer period
    if 0 < k < amp.size - 1:
        a, b, c = amp[k - 1], amp[k], amp[k + 1]
        denom = a - 2.0 * b + c
        if denom != 0.0:
            dk = 0.5 * (a - c) / denom
            period_cells = n * ds_cells / (k + dk)
    return (float(period_cells), float(period_cells * H_MM), float(amp[k]),
            float(k))


def pearson(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if a.size < 2 or np.std(a) == 0.0 or np.std(b) == 0.0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def shifted_corr(alpha, r, m):
    """Correlation of alpha[i] with r[i + m] over the valid overlap."""
    i = np.arange(alpha.size)
    j = i + m
    keep = (j >= 0) & (j < r.size)
    a = alpha[i[keep]]
    b = r[j[keep]]
    if a.size < 3:
        return float("nan")
    return pearson(a, b)


def report(path):
    z = np.load(path)
    st = np.asarray(z["station_cells"], dtype=int)
    amp = np.asarray(z["amp"], dtype=float)
    ph = np.asarray(z["phase_rad"], dtype=float)
    r = np.asarray(z["ab_over_af"], dtype=float)

    xx = (st - st[0]).astype(float)          # cells since first station
    ds = float(np.median(np.diff(xx)))       # station spacing in cells
    n = st.size

    lam_g = 2.0 * np.pi / BETA_REF           # m
    lam_g_cells = lam_g / CELL
    lam_g_half_cells = lam_g_cells / 2.0

    print(f"=== {path} ===")
    print(f"{'n_stations':34s} {n:d}")
    print(f"{'station_cells_min':34s} {int(st[0]):d}")
    print(f"{'station_cells_max':34s} {int(st[-1]):d}")
    print(f"{'station_spacing_cells':34s} {ds:.1f}")
    print(f"{'span_cells':34s} {float(xx[-1]):.1f}")

    dph_deg = np.degrees(np.diff(np.unwrap(ph)))
    incr = dph_deg / np.diff(xx)
    print(f"{'mean_phase_incr_deg_per_cell':34s} {float(np.mean(incr)):.6f}")
    print(f"{'std_phase_incr_deg_per_cell':34s} {float(np.std(incr)):.6f}")

    # ---- amplitude residual ------------------------------------------------
    lnamp = np.log(amp)
    sl, ic, res_a = detrend(lnamp, xx)
    pc_a, mm_a, pk_a, ka = fft_peak(res_a, ds)
    print(f"{'logamp_slope_per_cell':34s} {sl:.9f}")
    print(f"{'logamp_residual_rms_ln':34s} {float(np.sqrt(np.mean(res_a**2))):.9f}")
    print(f"{'logamp_fft_peak_period_cells':34s} {pc_a:.4f}")
    print(f"{'logamp_fft_peak_period_mm':34s} {mm_a:.6f}")
    print(f"{'logamp_fft_peak_amp_ln':34s} {pk_a:.9f}")
    print(f"{'logamp_fft_peak_bin':34s} {ka:.3f}")

    # ---- phase residual ----------------------------------------------------
    slp, icp, res_p = detrend(np.unwrap(ph), xx)
    pc_p, mm_p, pk_p, kp = fft_peak(res_p, ds)
    res_p_deg = np.degrees(res_p)
    pk_p_deg = np.degrees(pk_p)
    print(f"{'phase_slope_rad_per_cell':34s} {slp:.9f}")
    print(f"{'phase_residual_rms_deg':34s} {float(np.sqrt(np.mean(res_p_deg**2))):.9f}")
    print(f"{'phase_fft_peak_period_cells':34s} {pc_p:.4f}")
    print(f"{'phase_fft_peak_period_mm':34s} {mm_p:.6f}")
    print(f"{'phase_fft_peak_amp_deg':34s} {pk_p_deg:.9f}")
    print(f"{'phase_fft_peak_bin':34s} {kp:.3f}")

    print(f"{'lambda_g_cells_at_beta_381.16':34s} {lam_g_cells:.4f}")
    print(f"{'lambda_g_over_2_cells':34s} {lam_g_half_cells:.4f}")
    print(f"{'lambda_g_over_2_mm':34s} {lam_g_half_cells * H_MM:.6f}")

    # ---- pair-by-pair ------------------------------------------------------
    dx = np.diff(xx) * CELL
    alpha = -np.log(amp[1:] / amp[:-1]) / dx
    rr = r[:-1]
    print(f"{'n_pairs':34s} {alpha.size:d}")
    print(f"{'alpha_mean_per_m':34s} {float(np.mean(alpha)):.6f}")
    print(f"{'alpha_std_per_m':34s} {float(np.std(alpha)):.6f}")
    print(f"{'alpha_min_per_m':34s} {float(np.min(alpha)):.6f}")
    print(f"{'alpha_max_per_m':34s} {float(np.max(alpha)):.6f}")
    print(f"{'r_mean':34s} {float(np.mean(rr)):.9f}")
    print(f"{'r_std':34s} {float(np.std(rr)):.9f}")
    print(f"{'pearson_alpha_r_shift_0':34s} {shifted_corr(alpha, r, 0):.6f}")
    print(f"{'pearson_alpha_r_shift_-2':34s} {shifted_corr(alpha, r, -2):.6f}")
    print(f"{'pearson_alpha_r_shift_-1':34s} {shifted_corr(alpha, r, -1):.6f}")
    print(f"{'pearson_alpha_r_shift_+1':34s} {shifted_corr(alpha, r, +1):.6f}")
    print(f"{'pearson_alpha_r_shift_+2':34s} {shifted_corr(alpha, r, +2):.6f}")
    A = np.vstack([rr, np.ones_like(rr)]).T
    (slope, inter), *_ = np.linalg.lstsq(A, alpha, rcond=None)
    resid = alpha - (slope * rr + inter)
    print(f"{'slope_alpha_vs_r_per_m':34s} {float(slope):.6f}")
    print(f"{'intercept_alpha_vs_r_per_m':34s} {float(inter):.6f}")
    print(f"{'alpha_vs_r_fit_resid_rms_per_m':34s} {float(np.sqrt(np.mean(resid**2))):.6f}")

    # ---- sign alternation --------------------------------------------------
    s = np.sign(alpha)
    changes = int(np.sum(s[1:] != s[:-1]))
    print(f"{'n_positive_alpha_pairs':34s} {int(np.sum(s > 0)):d}")
    print(f"{'n_negative_alpha_pairs':34s} {int(np.sum(s < 0)):d}")
    print(f"{'sign_changes':34s} {changes:d}")
    print(f"{'sign_change_fraction':34s} {changes / max(alpha.size - 1, 1):.6f}")
    lag1 = pearson(alpha[:-1], alpha[1:]) if alpha.size > 2 else float("nan")
    print(f"{'alpha_autocorr_lag1':34s} {lag1:.6f}")
    lag2 = pearson(alpha[:-2], alpha[2:]) if alpha.size > 3 else float("nan")
    print(f"{'alpha_autocorr_lag2':34s} {lag2:.6f}")
    pc_al, mm_al, pk_al, kal = fft_peak(alpha - np.mean(alpha), ds)
    print(f"{'alpha_ripple_peak_period_cells':34s} {pc_al:.4f}")
    print(f"{'alpha_ripple_peak_period_mm':34s} {mm_al:.6f}")
    print(f"{'alpha_ripple_peak_amp_per_m':34s} {pk_al:.6f}")
    print(f"{'alpha_ripple_peak_bin':34s} {kal:.3f}")
    print(f"{'alt2_period_cells':34s} {2.0 * ds:.4f}")
    print(f"{'ratio_lambda_g_over_2_to_pair2':34s} {lam_g_half_cells / (2.0 * ds):.6f}")
    print()

    # ---- numeric dump of the pair series ----------------------------------
    print(f"{'pair_i':>6s} {'cell_i':>7s} {'cell_i1':>7s} "
          f"{'alpha_i_per_m':>16s} {'r_i':>14s} {'lnamp_i':>14s}")
    for i in range(alpha.size):
        print(f"{i:6d} {int(st[i]):7d} {int(st[i + 1]):7d} "
              f"{alpha[i]:16.6f} {r[i]:14.9f} {lnamp[i]:14.9f}")
    print()

    print(f"{'station_j':>9s} {'cell':>6s} {'amp':>16s} {'phase_rad':>16s} "
          f"{'r_j':>14s} {'resid_lnamp':>14s} {'resid_phase_deg':>18s}")
    for j in range(n):
        print(f"{j:9d} {int(st[j]):6d} {amp[j]:16.9f} {ph[j]:16.9f} "
              f"{r[j]:14.9f} {res_a[j]:14.9f} {res_p_deg[j]:18.9f}")
    print()


def main():
    for path in FILES:
        report(path)


if __name__ == "__main__":
    main()
