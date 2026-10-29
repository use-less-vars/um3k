"""58.4 Phase A -- does the two-field (E,H) travelling pair remove ``alpha``?

One run, two cases, identical ``dt`` and identical ``f0`` (same bin index):

``CASE A``
    48x18x14, stations 14 / 26 / 38 -- the baseline coupon.  Reproduces the
    recorded ``beta_raw`` / ``beta_pipeline`` / ``|a_f|`` / ``alpha`` numbers
    before anything new is claimed.
``CASE B``
    the line lengthened to 96 cells (nx = 4 + 4 + 96 = 104), source 32 cells
    behind station 1, six stations evenly spaced in the middle third, 30 cells
    clear of the far PML.  Geometry alone, no arithmetic change.

Per station: ``a_e``, ``a_h`` (both temporal H de-stagger signs), the measured
``Z = V/I``, and the two-field split

    ``a_pm = (a_e * v_mode +- Z * a_h * i_mode) / (2 * v_mode) = (a_e +- a_h)/2``

which is the split the record currently throws away (it never forms the H side).
From those: ``alpha`` (least squares on ``log|a_f|``), ``beta`` (unwrapped phase
slope), ``|a_f|**2 - |a_b|**2``, and a 7-point trial-beta sweep of a genuine
two-station / two-field least-squares split (four equations, two unknowns) --
not tautological, because the trial beta moves the answer.

Nothing under ``emfit/`` is edited: this only calls the public harness.
"""

from __future__ import annotations

import time

import numpy as np

from emfit.evolve import FITStepper, cfl_dt
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.modal_harness import (ModalStationCapture, build_mode_plane,
                                 split_forward_backward)
from emfit.operators import CellComplex
from emfit.pml import PML

C0 = 299792458.0
DB = 8.685889638065036  # nepers -> dB

# --- the coupon ------------------------------------------------------------
H = 1.6e-3
N_SUB = 8
CELL = H / N_SUB
EPS_R = 4.4
N_STRIP = 4
W = N_STRIP * CELL
N_CLEAN = 3
N_AIR = 4
N_TOP = 2
N_PML = 4
N_REF = 4
N_WARM = 600
K_BIN = 8
N_ACC = 2096

# --- baseline record (58.3), for the reproduction check ---------------------
BL = {"beta_raw": 473.4598882238203, "beta_pipeline": 480.82771869847704,
      "ratio_mag": 0.8903491584, "ratio_ang": 8.799958,
      "af": (3.740134e5, 2.859922e5), "alpha": 111.8030,
      "a_e14": (-1.623550e4, -1.841280e4), "a_h14": (-2.118413e4, -1.764731e4)}


# ---------------------------------------------------------------------------
# build / run
# ---------------------------------------------------------------------------
def build(n_line):
    nx = N_PML + N_REF + n_line
    ny = 2 * N_PML + N_STRIP + 2 * N_CLEAN
    nz = N_SUB + N_AIR + N_TOP
    grid = Grid.uniform(nx, ny, nz, nx * CELL, ny * CELL, nz * CELL)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(
        grid, cc, eps_r=lambda x, y, z: np.where(z <= H, EPS_R, 1.0))

    ix_port = N_PML + N_REF
    k_strip = N_SUB
    j0 = N_PML + N_CLEAN
    j1 = j0 + N_STRIP

    pec = np.array(cc.pec_edge_mask(), dtype=bool)
    strip = np.zeros(cc.n_edges, dtype=bool)
    strip[cc.idx_ex(np.arange(ix_port, nx)[:, None],
                    np.arange(j0, j1 + 1)[None, :], k_strip)] = True
    strip[cc.idx_ey(np.arange(ix_port, nx + 1)[:, None],
                    np.arange(j0, j1)[None, :], k_strip)] = True
    pec |= strip

    pml = PML(grid, thickness_cells=N_PML, order=2, target=1e-4,
              walls=("xmin", "xmax", "ymin", "ymax", "zmax"), cc=cc)
    stepper = FITStepper(cc, m_eps, m_mu, dt=float(cfl_dt(grid)), pec=pec,
                         pml=pml)
    mode = build_mode_plane(cc, h=H, w=W, eps_r=EPS_R, n_sub=N_SUB,
                            k_strip=k_strip, iy_strip_centre=j0 + N_STRIP // 2,
                            n_clean=N_CLEAN, n_air=N_AIR)
    return cc, stepper, mode, ix_port, k_strip, j0, j1, (nx, ny, nz)


def run_case(name, n_line, stations):
    cc, stepper, mode, ix_port, k_strip, j0, j1, mesh = build(n_line)
    dt = float(stepper.dt)
    f0 = K_BIN / (N_ACC * dt)
    stations = np.asarray(stations, dtype=int)
    cap = ModalStationCapture(cc, mode, stations, f0=f0, dt=dt, limit=N_ACC,
                              n_warm=N_WARM, destagger_h=False)  # raw H kept
    port_edges = np.unique(np.concatenate(
        [cc.idx_ez(np.array([ix_port]), np.array([j]),
                   np.arange(0, k_strip)).ravel() for j in range(j0, j1 + 1)]))

    def drive(n):
        cur = np.zeros(cc.n_edges, dtype=float)
        cur[port_edges] = min(1.0, (n + 1) / N_WARM) * np.sin(
            2.0 * np.pi * f0 * n * dt)
        return cur

    t0 = time.perf_counter()
    res = cap.run(stepper, drive=drive)
    wall = time.perf_counter() - t0
    res.update(f0=f0, dt=dt, wall_s=wall, mesh=mesh, n_steps=N_WARM + N_ACC,
               ix_port=int(ix_port), station_list=[int(s) for s in stations])
    print(f"[{name}] mesh {mesh} stations {stations.tolist()} "
          f"dt {dt!r} f0 {f0!r} steps {res['steps']} wall {wall:.2f} s",
          flush=True)
    return res, mode


# ---------------------------------------------------------------------------
# small estimators
# ---------------------------------------------------------------------------
def fit_line(x, y):
    """Least-squares line: slope, intercept, residual rms, slope sigma."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    A = np.vstack([x, np.ones_like(x)]).T
    (slope, inter), *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - (slope * x + inter)
    rms = float(np.sqrt(np.mean(r ** 2)))
    sigma = float("nan")
    if x.size > 2:
        s2 = float(np.sum(r ** 2) / (x.size - 2))
        sxx = float(np.sum((x - x.mean()) ** 2))
        if sxx > 0.0:
            sigma = float(np.sqrt(s2 / sxx))
    return float(slope), float(inter), rms, sigma


def pair_split_2field(ae1, ah1, ae2, ah2, d, beta):
    """Two stations x two fields -> least-squares ``(p, m)`` at station 1.

    Model, with ``w = exp(-j beta d)``::

        a_e1 = p + m        a_h1 = p - m
        a_e2 = p w + m / w  a_h2 = p w - m / w

    Four complex equations, two complex unknowns.  ``p`` is the forward modal
    amplitude in ``a_e`` units.  A wrong trial ``beta`` spoils the fit (the
    residual is returned), so the sweep below is a real test.
    """
    w = np.exp(-1j * beta * d)
    A = np.array([[1.0, 1.0], [1.0, -1.0],
                  [w, 1.0 / w], [w, -1.0 / w]], dtype=complex)
    b = np.array([ae1, ah1, ae2, ah2], dtype=complex)
    G = A.conj().T @ A
    r = A.conj().T @ b
    p, m = np.linalg.solve(G, r)
    resid = float(np.linalg.norm(A @ np.array([p, m]) - b) / np.linalg.norm(b))
    return complex(p), complex(m), resid


def hdr(title):
    print(f"\n=== {title} " + "=" * max(0, 72 - len(title)))


# ---------------------------------------------------------------------------
# the analysis
# ---------------------------------------------------------------------------
def analyse(name, res, mode):
    st = np.array(res["station_list"], dtype=int)
    n = st.size
    x = (st - st[0]) * CELL                      # m, station 1 at 0
    d = float(np.median(np.diff(x))) if n > 1 else CELL
    f0, dt = res["f0"], res["dt"]
    k0 = 2.0 * np.pi * f0 / C0
    th = np.pi * f0 * dt                          # the half-step angle

    ae = np.array([res["a_e"][int(i)] for i in st])
    ah_raw = np.array([res["a_h"][int(i)] for i in st])
    ah_p = ah_raw * np.exp(+1j * th)               # house sign
    ah_m = ah_raw * np.exp(-1j * th)               # the other sign
    v = np.array([res["amplitudes"][int(i)] for i in st])   # a_e * v_mode

    v_mode = float(mode.v_mode)
    i_mode = float(mode.i_mode)
    z0 = float(mode.z0_power)
    eta = float(mode.eta_eff)

    hdr(f"{name}: station phasors (x in mm from station 1)")
    print("  ix   x_mm      |a_e|     arg a_e   |a_h+|     arg a_h+"
          "  |a_h-|     arg a_h-   d(arg)  |a_e/a_h|  arg(a_e/a_h)")
    for i in range(n):
        dphi = np.angle(ah_p[i]) - np.angle(ah_m[i])
        print(f"  {st[i]:3d} {x[i]*1e3:7.3f} {abs(ae[i]):10.4e} "
              f"{np.degrees(np.angle(ae[i])):+9.3f} {abs(ah_p[i]):10.4e} "
              f"{np.degrees(np.angle(ah_p[i])):+9.3f} {abs(ah_m[i]):10.4e} "
              f"{np.degrees(np.angle(ah_m[i])):+9.3f} "
              f"{np.degrees(dphi):+7.3f} {abs(ae[i]/ah_p[i]):9.4f} "
              f"{np.degrees(np.angle(ae[i]/ah_p[i])):+9.3f}")

    r = np.abs(ae / ah_p)
    pr = np.degrees(np.angle(ae / ah_p))
    print(f"  half-step angle pi*f*dt = {np.degrees(th):.4f} deg "
          f"(sign flip moves arg a_h by 2*that = {2*np.degrees(th):.4f} deg)")
    print(f"  a_e/a_h magnitude spread max/min-1 = {r.max()/r.min()-1:+.4e}, "
          f"phase spread = {pr.max()-pr.min():.4f} deg")

    hdr(f"{name}: Z from the mode E/H fields vs measured V/I")
    den_e = float(np.sum(mode.e_y ** 2) + np.sum(mode.e_z ** 2))
    den_h = float(np.sum(mode.h_y ** 2) + np.sum(mode.h_z ** 2))
    print(f"  mode: v_mode {v_mode:.6g}  i_mode {i_mode:.6g}  "
          f"z0_power {z0:.6f} ohm  eta_eff {eta:.6f} ohm  "
          f"sqrt(den_e/den_h) {np.sqrt(den_e/den_h):.6f} ohm  "
          f"discrete_power {mode.discrete_power:.6f}")
    print("  ix     |Z| ohm    arg Z    |Z|/z0    arg Z deg")
    for i in range(n):
        Z = ae[i] * v_mode / (ah_p[i] * i_mode)
        print(f"  {st[i]:3d} {abs(Z):11.4f} {np.degrees(np.angle(Z)):+9.4f} "
              f"{abs(Z)/z0:9.4f} {np.degrees(np.angle(Z)):+11.4f}")

    hdr(f"{name}: two-field split a_pm = (a_e*v_mode +- Z*a_h*i_mode)/2 / v_mode")
    print("  (identical to (a_e +- a_h)/2 because Z_mode = v_mode/i_mode)")
    splits = {}
    for tag, ahx in (("house(-)", ah_p), ("other(+)", ah_m)):
        af = (ae * v_mode + z0 * ahx * i_mode) / (2.0 * v_mode)
        ab = (ae * v_mode - z0 * ahx * i_mode) / (2.0 * v_mode)
        splits[tag] = (af, ab)
        print(f"  [{tag}]")
        print("   ix    |a_f|      arg a_f   |a_b|     |a_b|/|a_f|  "
              "|a_f|^2-|a_b|^2")
        for i in range(n):
            print(f"   {st[i]:3d} {abs(af[i]):10.4e} "
                  f"{np.degrees(np.angle(af[i])):+9.3f} {abs(ab[i]):10.4e} "
                  f"{abs(ab[i])/abs(af[i]):10.4f} "
                  f"{abs(af[i])**2-abs(ab[i])**2:14.6e}")
    af, ab = splits["house(-)"]

    hdr(f"{name}: alpha and beta from the two-field forward amplitude")
    alphas = {}
    for tag in ("raw_e", "twofield", "twofield_other"):
        if tag == "raw_e":
            amp = np.abs(ae)
        elif tag == "twofield":
            amp = np.abs(splits["house(-)"][0])
        else:
            amp = np.abs(splits["other(+)"][0])
        sl, ic, rms, sig = fit_line(x, np.log(amp))
        a = -sl
        alphas[tag] = a
        extra = f" sigma {sig:.4e}" if np.isfinite(sig) else ""
        print(f"  alpha[{tag:14s}] = {a:+11.5f} /m  = {a*1e-3*DB:+9.5f} dB/mm"
              f"  over span {a*x[-1]*DB:+8.4f} dB"
              f"  fit residual rms {rms:.4e} in ln|a|{extra}")
    # least-squares beta from the unwrapped phase of a_f
    ph = np.unwrap(np.angle(af))
    besl, _, brms, bsig = fit_line(x, ph)
    beta = -besl
    print(f"  beta(two-field phase slope) = {beta:.6f} /m  "
          f"eps_eff {(beta/k0)**2:.6f}  phase residual rms "
          f"{np.degrees(brms):.4f} deg")
    print(f"  beta*d = {np.degrees(beta*d):.4f} deg for d = {d*1e3:.4f} mm; "
          f"span {np.degrees(beta*x[-1]):.4f} deg over {x[-1]*1e3:.3f} mm")
    print(f"  d(beta)/beta per 1 deg of phase over d = "
          f"{100.0/np.degrees(beta*d):.4f} %")

    print("\n  reproduction check against the 58.3 record (classic pipeline):")
    beta_fp = BL["beta_pipeline"]
    pair_af = []
    for _ in range(6):
        afc = []
        for i in range(n - 1):
            p, m = split_forward_backward(v[i], v[i + 1], float(x[i + 1] - x[i]),
                                          beta_fp)
            afc.append(p)
        afc = np.array(afc)
        new = -np.angle(afc[1] / afc[0]) / float(np.mean(np.diff(x))) if n > 2 \
            else -np.angle(afc[0]) / d
        beta_fp = float(new)
        pair_af = afc
    print(f"    classic pairwise |a_f| = {[f'{abs(q):.6e}' for q in pair_af]}")
    print(f"    record |a_f| = {BL['af'][0]:.6e}, {BL['af'][1]:.6e}; "
          f"beta_classic = {beta_fp:.9f} (record {BL['beta_pipeline']:.9f})")
    if n > 2:
        xm = 0.5 * (x[:-1] + x[1:])
        slc, _, rmsc, _ = fit_line(xm, np.log(np.abs(pair_af)))
        print(f"    alpha_classic = {-slc:+11.5f} /m "
              f"({-slc*1e-3*DB:+.5f} dB/mm), residual rms {rmsc:.4e}")
        alphas["classic"] = -slc
    print(f"    beta_raw (total field phase slope) = "
          f"{-np.polyfit(x, np.unwrap(np.angle(v)), 1)[0]:.6f} /m "
          f"(record {BL['beta_raw']:.6f})")

    hdr(f"{name}: 7-point trial-beta sweep of the two-station/two-field LS fit")
    beta_ref = beta if np.isfinite(beta) and beta > 0 else BL["beta_pipeline"]
    print(f"  beta_ref = {beta_ref:.6f} /m, pairs of spacing "
          f"{[f'{1e3*(x[i+1]-x[i]):.3f}' for i in range(n-1)]} mm")
    print("  trial beta      rel     |p| per pair ..."
          "                    spread   max|m|/|p|  resid")
    sweep = {}
    for fac in np.linspace(0.90, 1.10, 7):
        bt = fac * beta_ref
        ps, ms, rs = [], [], []
        for i in range(n - 1):
            p, m, rr = pair_split_2field(ae[i], ah_p[i], ae[i + 1], ah_p[i + 1],
                                         float(x[i + 1] - x[i]), bt)
            ps.append(abs(p))
            ms.append(abs(m))
            rs.append(rr)
        ps = np.array(ps)
        sweep[fac] = ps
        print(f"  {bt:11.4f} {fac:6.3f} " +
              " ".join(f"{q:11.4e}" for q in ps) +
              f" {ps.max()/ps.min()-1:8.4f} "
              f"{max(mm/pp for mm, pp in zip(ms, ps)):10.4f} "
              f"{max(rs):8.4f}")
    allp = np.concatenate([sweep[f] for f in sweep])
    print(f"  sweep |p| range {allp.min():.6e} .. {allp.max():.6e} "
          f"(ratio {allp.max()/allp.min():.4f})")
    # classic sweep, for the record
    print("  classic (single-field) sweep, |a_f| per pair:")
    for fac in np.linspace(0.90, 1.10, 7):
        bt = fac * beta_ref
        q = [abs(split_forward_backward(v[i], v[i + 1],
                                        float(x[i + 1] - x[i]), bt)[0])
             for i in range(n - 1)]
        print(f"    {bt:11.4f} {fac:6.3f} " +
              " ".join(f"{qq:11.4e}" for qq in q))

    hdr(f"{name}: one-line summary")
    print(f"  alpha(raw a_e) {alphas['raw_e']:+9.3f} /m | "
          f"alpha(2-field) {alphas['twofield']:+9.3f} /m | "
          f"alpha(2-field, other H sign) {alphas['twofield_other']:+9.3f} /m"
          + (f" | alpha(classic) {alphas['classic']:+9.3f} /m"
             if "classic" in alphas else ""))
    print(f"  a_e/a_h |.| spread {r.max()/r.min()-1:+.4e}, phase spread "
          f"{pr.max()-pr.min():.4f} deg | beta {beta:.4f} /m | "
          f"|a_b|/|a_f| max {np.max(np.abs(ab)/np.abs(af)):.4f}")
    return dict(name=name, alpha=alphas, split=dict(splits),
                ratio_mag=r, ratio_ph=pr, beta=beta, beta_classic=beta_fp,
                sweep=sweep, x=x, st=st, d=d, th=th)


def main():
    t0 = time.perf_counter()
    out = {}
    for name, n_line, stations in (("CASE A", 40, (14, 26, 38)),
                                   ("CASE B", 96, (40, 46, 52, 58, 64, 70))):
        res, mode = run_case(name, n_line, stations)
        out[name] = analyse(name, res, mode)
    print(f"\ntotal wall {time.perf_counter()-t0:.2f} s", flush=True)


if __name__ == "__main__":
    main()
