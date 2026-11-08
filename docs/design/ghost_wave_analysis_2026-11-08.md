# Ghost-wave analysis: what the new dump actually says

**Dispatch:** `ghost-wave-data-analysis-2026-11-08`
**Artefacts:** `evidence/termination/build_A_50ohm_p51_ghostwave.json` (19 621 B), `evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz` (12 934 031 B)
**Run:** 2 399 steps, `dt_s` 7.626299478123987e-13, 1 800 accumulated samples, 38.53 s wall, 306.0 MB peak RSS. Grid 62 x 212 x 22, cell 0.0004 m.
**Mode:** read-only analysis. No code changed, no FDTD run.

---

## 1. The short version

The two channels I built do not say what I told you they would say. One works and one does not, and they are not the ones I would have guessed.

- **The current channel is right.** I took the raw H field out of the npz and integrated it myself, with none of my own code in the loop. Result at the plane-51 station: 4 756.623 A. What the run recorded: 4 757.152 A. That is 1 part in 10 000. Verified.
- **The voltage channel is not.** I took the raw E field out of the same npz and integrated it across the gap. On no transverse position, and on no choice of how many cells to include, does it reproduce the 217 354 V the run recorded. Best case it comes out 30 % low; on the physically correct gap width it comes out 92 % high. Unverified.
- **Everything downstream of that split inherits it.** `gamma_plane` (0.0439) is the most exposed number in the file, and I do not believe it.
- **The port S-parameters are not the problem.** `|s11| = 0.325863` and `|s21| = 0.761705` are supported by a fourth, independent measurement in section 7 that involves none of the suspect arithmetic.

So: **neither L1 nor L2 as written.** The load is not convicted. The extraction is lying, but at the plane, not at the port.

---

## 2. Four things I got wrong

I would rather list these than have you find them.

1. **Route B, as I documented it in `ghost_wave_forensics_2026-11-07.md`, is circular.** `Z = V/I` with `I = sum(V_k * G)` and `G = 1/(N*R)` returns `R` identically for any field whatsoever. It cannot fail, so it cannot convict. Section 3 has the algebra and the numbers.
2. **The load-edge channel dumps the wrong field component and over-counts by 9.** `studies.py:2917` uses `idx_ex` (longitudinal `E_x`) while `run_build_A.py:210` documents it as `E_z`. And the 9 edges are parallel across the strip width, summed with all `+1`, so the dumped 1 829 078 V is nine times the per-element value. Section 8.
3. **The sizing numbers in the 2026-11-07 document are wrong for this grid.** I predicted 1 050 754 edges and a 2-4 MB npz. Actual: 906 144 edges, and the npz is 12.93 MB, barely compressed at all.
4. **I predicted about 1 400 s and 2 000 MB for this run.** Actual: 38.5 s and 306 MB. You were right to be surprised, and in the good direction.

---

## 3. The test you asked for cannot work

The request was: take the raw per-edge voltages, form `I = sum(V_k * G)` with `G = 1/(N*R)`, then `Z = V/I`, and check whether it lands on 50 ohm exactly.

Let the N edge voltages be `V_k` and let `Vbar` be their mean, so `sum(V_k) = N*Vbar`. Then

    I = G * sum(V_k) = (1/(N*R)) * N * Vbar = Vbar / R
    Z = Vbar / I = Vbar / (Vbar / R) = R

`Vbar` cancels. Every field cancels. The answer is `R` because we divided by `R`, and for no other reason. Numerically, taking R = 50:

| field | resulting Z |
|---|---|
| all-ones | 50 - 1.555e-15j |
| doubled | 50 - 1.555e-15j |
| `(1+3j)` per edge | 50 + 2.001e-15j |

The imaginary part of the field, the phase, the amplitude, everything leaves no trace. A test that returns 50 ohm when the field is `1+3j` will return 50 ohm when the load is a short. It is not evidence. **This is why I pushed back on the task before doing it.**

A per-edge reading can still be useful as a *uniformity* check - are the nine edges doing the same thing? - and it did answer that. But it can never test the impedance.

---

## 4. Verified against not verified

The distinction that matters, and it cuts differently from what I expected.

| quantity | value | independent check | verdict |
|---|---|---|---|
| plane-51 current | 4 757.152 A | raw `plane_hy` integral, best `k`: 4 756.623 A | **VERIFIED**, 1e-4 |
| plane-51 voltage | 217 354 V | raw `plane_ez` integral: 152 628 V (22 cells) or 416 981 V (4 cells) | **NOT REPRODUCED** |
| `V/I` at plane 51 | 45.6386 - 2.16680j | depends entirely on the voltage above | holds only as far as the voltage does |
| `gamma_plane` | 0.0439083 at -113.737 deg | raw-field envelope implies about 0.212 | **OUTLIER**, 4.8x low |
| `|s11|` | 0.325863 | agrees with the de-embedded envelope to 0.3 % | **SUPPORTED** |
| `|s21|` | 0.761705 | envelope plus loss predicts 0.763020, 0.17 % | **SUPPORTED** |
| load-edge voltage | 1 829 078 V | 9 edges bit-identical; per element 203 231 V | scale right, count and component wrong |

The space I searched is exhaustive in the two coordinates that matter: all nine stations, all 213 transverse positions, and both the full 22-cell stack and the physical 4-cell gap. Nothing reproduces 217 354 V. That is the finding.

---

## 5. The split is not using the impedance the file reports

`emfit/studies.py:1282-1294` is the whole of it:

```python
def _wave_amplitude(v, i, x, gamma, zc, sign, indices) -> np.ndarray:
    """Shared algebra of :func:`forward_wave_amplitude` and its mirror."""
    v = np.asarray(v, dtype=complex)
    i = np.asarray(i, dtype=complex)
    x = np.asarray(x, dtype=float)
    if not v.size == i.size == x.size:
        raise ValueError(
            f"v, i and x must be the same length, got {v.size}, {i.size} "
            f"and {x.size}")
    if indices is not None:
        idx = np.asarray(indices, dtype=int)
        v, i, x = v[idx], i[idx], x[idx]
    return 0.5 * (v + complex(sign * zc) * i) * np.exp(complex(sign * gamma) * x)
```

`forward_wave_amplitude` calls it with `sign = +1.0` (line 1351), the backward one with `sign = -1.0` (line 1375). So `a = (v + zc*i)/2` and `b = (v - zc*i)/2`, each de-embedded by `exp(+/- gamma*x)`.

That means the recorded quadruple should satisfy `v = a + b` and `i = (a - b)/zc`. It does satisfy the first: `a + b` reproduces `v` to a residual of 4.7e-7 V, relative 2e-12. It does **not** satisfy the second if `zc` is taken to be the `z0` the file reports.

| | value |
|---|---|
| `line.z0` as recorded | 42.7585031570 - 16.0461497776j (magnitude 45.6702, angle -20.57 deg) |
| `zc` implied by the recorded `a`, `b`, `v`, `i`, via `(2a - v)/i` | **47.30581504562189 + 1.5582142987505327j** (magnitude 47.3315, angle 1.887 deg) |

Using the implied value reproduces the recorded `i` to 2.4e-12 relative. Using the reported `z0` misses it by 39.8 %. The ratio between them is `0.95779 + 0.39587j`.

So **`line.z0` is not the impedance that was used to split the waves.** It is some other quantity - a station fit, most likely - and the value actually used is essentially real at 47.3 ohm. The reactive part in the reported `z0` (-16 ohm) does not appear anywhere in the split. Whatever reports `line` and whatever feeds `zc` to the split are computing two different things, and neither is documented as such.

Note also that 47.31 + 1.56j is close to the old fitted 47.364066848 + 1.644980793. The split has apparently not changed; the reporting of `z0` has.

---

## 6. What S21 actually is

The branch taken on this run is `reference is None` (`loaded_without_reference: true`), so `studies.py:3729`:

```python
s21, raw_s21 = line_s21(a_port, x_port, a_cut, x_cut, beta)
```

and `emfit/ports.py:768`:

```python
return (v_to / v_from) * np.exp(1j * beta * d)
```

i.e.

    s21 = (a_cut / a_port) * exp(+j * beta * d),   d = x_cut - x_port = 0.0204 - 0.0012 = 0.0192 m

with `beta = 232.79891853803187`, so `beta*d = 4.46974` rad.

Three things worth stating plainly.

1. **There is no Z0 normalisation and no impedance ratio on this branch.** The number is a ratio of two like-normalised forward-wave amplitudes, both in volts, with a phase correction. That is why `|s21|` survives the broken voltage: `zc` largely cancels out of a ratio of two amplitudes taken the same way.
2. **`a_port` is taken at the port plane** and `a_cut` at the cut, and both are de-embedded to `x = 0` inside `_wave_amplitude` before being divided. The extra `exp(+j*beta*d)` is the only re-propagation. The net phase applied between the two planes is therefore `gamma*d + j*beta*d`, not `j*beta*d`. For a lossy line that is close to `j*2*beta*d`. I am flagging this as bookkeeping to verify rather than asserting a defect: `|s21|`, which is what section 7 validates, is unaffected by it.
3. **The magnitude is the part I can stand behind.** `|s21| = 0.761705`, angle +5.775 deg. The angle is not yet vouched for.

---

## 7. The measurement that settles it

The npz carries the raw phasor field on nine measurement planes. That data has passed through none of the arithmetic in sections 5 and 6. Integrating `plane_ez` across the gap at each station gives a total voltage, and a total voltage that varies along the line is a standing wave.

The nine values (full 22-cell stack, transverse index 106):

    144 282   124 320   106 403   100 155   109 442   127 381   144 472   154 127   152 628  volts

Minimum 100 155, maximum 154 127. A standing wave with that envelope has

    |Gamma| = (max - min) / (max + min) = 54  / 254  = 0.2122

against the 0.0439 the split reports. Four point eight times apart.

Now the other end. If the transmission line is lossy with attenuation `alpha`, the two port numbers and the reflection at the plane are tied together by `|s21|^2 = (1 - |s11|^2) * exp(-2*alpha*d)`. Invert that for `alpha`, then de-embed `|s11|` back to the plane over 19.2 mm and compare with the envelope:

| step | result |
|---|---|
| `alpha` from `|s11| = 0.325863` and `|s21| = 0.761705` | 11.255 Np/m, about 98 dB/m |
| `|s11|` de-embedded to the plane | 0.2115 |
| envelope measured from the raw field | 0.2122 |
| agreement | **0.3 %** |

And the other direction, taking the envelope as the truth:

| step | result |
|---|---|
| `alpha` from the envelope and `|s11|` | 11.166 Np/m |
| `|s21|` predicted | 0.763020 |
| `|s21|` recorded | 0.761705 |
| agreement | **0.17 %** |

Three measurements that the suspect split does not touch - the raw field envelope, the port reflection, the port transmission - agree with each other to a third of a percent. The one measurement that does depend on the split, `gamma_plane = b/a`, disagrees with all three by a factor of five.

**That is the answer to L2.** The extraction is not lying about S11 or S21. It is lying about the reflection at the plane, because the voltage it puts into the split is not the voltage the field actually has.

### The 31 % that goes missing

`|s11|^2 + |s21|^2 = 0.106187 + 0.580195 = 0.686382`, leaving 0.313618 unaccounted. That number has a clean reading: with `alpha = 11.255 Np/m` over 19.2 mm the line attenuates by `exp(-2*alpha*d) = 0.6491`, so of the 0.8938 that gets past the input mismatch, `0.8938 * (1 - 0.6491) = 0.313620` is dissipated in the line. To five figures that is the missing 0.313618.

The 31 % is not a leak and not a bug. It is the bill the line pays for being 19.2 mm of real conductor on a real substrate.

---

## 8. The load-edge channel

The nine indices are `247300, 247323, 247346, ... 247484`, stride 23. `emfit/operators.py:82-84` is

```python
def idx_ex(self, i, j, k):
    return (self.off_ex + (i % self.nx) * self.nyn * self.nzn
            + (j % self.nyn) * self.nzn + (k % self.nzn))
```

with `nzn = nz + 1 = 23`. A stride of 23 is a step in `j`. So the nine edges share one `i` (= 50, the load column) and one `k`, and differ only in the transverse index. They are nine parallel `E_x` edges, laid side by side across the strip width in the direction of propagation.

Two consequences, both mine to own.

- `run_build_A.py:210` describes this probe as "every `E_z` edge of the load's own column". It is not `E_z`. The edge set comes from `idx_ex`, so it is `E_x` - the longitudinal component, not the transverse gap field. The docstring is wrong and so was my description of it.
- `edge_path_voltage` defaults to `signs = +1` for every edge and simply sums. Nine parallel edges summed with `+1` give nine times the voltage that is actually across any one of them. The dumped 1 829 078 V is not a gap voltage.

Dividing by nine gives **203 231 V per element**, and that number is not nonsense: it sits at 0.935 of the recorded plane voltage (217 354 V) and 0.854 of `|I|` times 50 ohm (237 858 V). So the *scale* is right - volts, factor 1.0, no missing cell width - while the *count* and the *component* are wrong. That is a much better place to be than a units error, and it is fixable in a dozen lines.

All nine values are bit-identical, spread exactly 0.0. With nine distinct transverse positions that is what an equipotential strip looks like, and it kills the hypothesis that the load edges were shorting across the gap. **The edges are doing exactly what they should.** That is the one question this channel did settle.

---

## 9. Data inventory, for the render

Keys in `build_A_50ohm_p51_ghostwave_fields.npz`:

| key | shape | dtype | notes |
|---|---|---|---|
| `plane_ez` | (9, 213, 22) | complex128 | phasors, `E_z` on the nine measurement planes |
| `plane_hy` | (9, 213, 22) | complex128 | phasors, `H_y` |
| `plane_ey` | (9, 212, 23) | complex128 | phasors, `E_y` |
| `plane_hz` | (9, 212, 23) | complex128 | phasors, `H_z` |
| `e` | (906 144,) | float64 | raw field vector at the final step, 7.25 MB |
| `h` | (886 676,) | float64 | raw field vector at the final step, 7.09 MB |
| `nstep` | scalar | int64 | 2399 |
| `nx`, `ny`, `nz` | scalar | int64 | 62, 212, 22 |
| `cell_m` | scalar | float64 | 0.0004 |

`e` and `h` together are 14.34 MB uncompressed against 12.93 MB on disk, so the archive is barely compressed: the fields are genuinely dense, and there is no sparsity to exploit.

None of the arrays is zero and none contains a non-finite value. Peak magnitudes: `e` 96.75, `h` 0.745.

The four `plane_*` arrays are the useful ones for a first render: each is nine 2-D slices of a phasor field on a fixed plane, which maps straight onto nine `pyvista` grids with no index arithmetic. `e` and `h` are flat vectors and need the Yee edge and face mapping from `operators.py:82-92` before they can be reshaped to a 3-D grid; that mapping, not the plotting, is the work.

---

## 10. What is still open

In the order I would attack them.

1. **Why `s21_plane.v` is not reproducible from `plane_ez`.** Two candidates: the plane capture at `studies.py:3333` accumulates over a different step window than the cut accumulator, or the plane capture integrates a different edge set than `column_path(cc, ix_extract, j_centre, 0, k_strip)` at `studies.py:3092`. One of the two is the wrong voltage. This is the single highest-value read in the codebase right now.
2. **Which `k` range is the physical gap.** `h = 1.6 mm` is four cells, and the field column flips sign at `k = 4` and then decays, so four cells looks right and twenty-two does not. This was inferred, not read from the capture code, so it needs confirming.
3. **`line.z0` versus the `zc` actually used.** 42.7585 - 16.0461j against 47.3058 + 1.5582j. Which one is the design answer, which is a fit, and is a -16 ohm reactive part physical for this line at all?
4. **The `|s21|` phase.** The de-embed contributes `gamma*d` and `line_s21` contributes another `exp(+j*beta*d)`. Worth confirming the conventions against a known-length through line.
5. **Rebuild the load-edge channel properly** on `E_z` across the gap, single edge or with a 1/N normalisation, and re-run the uniformity check. Then the load can be tested against the plane current, which is the one channel now verified from raw fields.
6. **Redo the load-plane reflection inversion against this artefact.** The 50.35 and 49.22 ohm figures from the previous dispatch came from a run whose JSON, `build_A_50ohm_p51.json`, is not in the tree. Every old-versus-new comparison in this document rests on numbers quoted in the dispatch log, not on a file anyone can reopen.
