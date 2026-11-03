# Flux-projection renormaliser: what the source fixes, and what it does not
Read-only check at HEAD: no code written, nothing executed; quotes are exact by path:line.
## Q1. The current-channel renormaliser, symbolically
Voltage channel - a bare signed edge sum, no measure (`emfit/ports.py:111`):
    return float(np.sum(s * e[idx]))
and `emfit/ports.py:82-85`: "Every edge unknown *is* the line integral of ``E`` along
that edge", so each sample is already `E_z * dz`; no cell width is applied.
Current channel - `plate_current`, also measure-free (`emfit/ports.py:467-468`):
    faces = np.asarray(cc.idx_fy(ix, np.arange(j0, j1), iz), dtype=int)
    return float(h[faces].sum())
`emfit/ports.py:400-405`: h holds "magnetic *voltages* ``H_y * dy`` in amperes"; "No
cell width is applied and none is missing"; "``V / I`` ... ``eta0 * LZ / LY``".
Take BOTH channels on one shared index set: same y row `j_centre`, same `k` range, same `phi`:
    I' = sum_k phi[k] * h_y[j_centre, k]
    V' = sum_k phi[k] * e_z[j_centre, k]
Both measures sit inside the unknowns (`emfit/ports.py:481-489`), each exactly once.
## Q2. Which sum is it: sum(phi_h), sum(phi_h*dz) or sum(phi_h*dz*dyt)?
`sum(phi_h)`: a plain coefficient-weighted sum of the `FY` unknowns, with neither `dz`
nor `dyt` nor the product applied on top; `dz * dyt` appears only in the flux
functional (`emfit/ports.py:552-556`), a power rather than a channel:
    px2 = float(np.sum(ez_l * hy_l * (dwy[:, None] * wz[z_ez][None, :])))
Nothing cancels and nothing is missing between the channels, because neither carries an
explicit measure; the one requirement is that the index set be shared.
## Q3. Does it equal -sum(phi_e * w_E) / eta_eff exactly?
Yes, on shared indices: divisor `-eta_eff`, no measure factor (`emfit/mode_profile.py:717`):
    h_y = -e_z / eta_eff                   # FY, collocated with e_z
and `plane_mode` fills that pairing from zeroed arrays (`emfit/modal.py:298-300`):
    (src, dst) = window.ynode_zcell
    e_z[dst] = mode.e_z[src]
    h_y[dst] = mode.h_y[src]
so for ANY filter - constant, tapered or not - the constant passes through the sum:
    I' = sum_k phi[k] h_y[k] = -(1/eta_eff) sum_k phi[k] e_z[k] = -(1/eta_eff) V'
The CONDITION is that shared index set. On the pair now in place it is not met: voltage
runs over `k` in one column (`emfit/studies.py:2912-2913`):
    cut_column = (column_path(cc, ix_extract, j_centre, 0, k_strip)
while current runs over `j` in one y run at `iz = 0` (`emfit/studies.py:3031-3035`):
            cut_signals[1] = 0.5 * (
                plate_current(stepper.h, cc, ix_extract - 1, 0,
                              y_extent=y_half)
Then equality would need `sum_j phi[j] e_z[j, iz] == sum_k phi[k] e_z[j_centre, k]`, a
y profile against a z profile - an identity nothing in the source supplies.
## Q4. What does the a/b split leave free?
`emfit/studies.py:1297` takes the pair on `zc`; the algebra is `emfit/studies.py:1294`:
def forward_wave_amplitude(v, i, x, gamma, zc, indices=None) -> np.ndarray:
    return 0.5 * (v + complex(sign * zc) * i) * np.exp(complex(sign * gamma) * x)
(a) `i = i_cut`: `a_cut = (v_cut + zc*i_cut)/2 * exp(+gamma*x)`.
(b) `i = -V'/eta_eff`, `v = V'`: `a_cut' = V'*(1 - zc/eta_eff)/2 * exp(+gamma*x)`, so
`a_cut'/a_cut = (V'/v_cut) * (1 - zc/eta_eff) / (1 + zc*i_cut/v_cut)`: projection gain,
renormalisation constant, baseline pair ratio; a forward pair (`i = v/zc`) makes it 2.
WARNING - `(1 - zc/eta_eff)/2` is near-CANCELLING, not near-unity (`zc = z0_power` is a few
percent off `eta_eff`), so the rescale is of order `1/(1 - zc/eta_eff)` - tens. Extraction
negates current (`emfit/studies.py:3139-3140`), so commit 11 must fix that sign explicitly and
pin it by test before any host run (`a_cut'` same order as `a_cut`), not from `h_y` alone.
VERDICT: extra weights - const (1 - zc/eta_eff)/(1 + zc*i_cut/v_cut); gain V'/v_cut separate
## What this means for the design
The sums are exact and measure-free, so no `dz` or `dyt` factor belongs on either channel.
The constant is the only piece commit 11 must write into code; the gain V'/v_cut is
what the four host runs measure, and the two must not be folded together or the
bracket prediction is contaminated. So the projection is a single-channel projection
rescaled by a known constant, not independent information - as the owner assumed, now sourced.
