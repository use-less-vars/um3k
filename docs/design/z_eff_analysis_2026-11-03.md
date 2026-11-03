# Z_eff of the discretised 50 Ω series load at 5.83 GHz

Question: what impedance does the `series_r` stamp (`emfit/studies.py:2789-2793`, `emfit/evolve.py:6-18`) present
at 5.8278 GHz, and does it explain a graded series load reading as ~25.5 + j31.6 Ω? Tags: **[M]** measured, in a
banked artefact; **[L]** derived here from code + constants; **[R]** recomputed here from artefact numbers.
Nothing below is fitted to the target.

## S1 — What is stamped

`emfit/evolve.py:6` — ``C~ h = d/dt (m_eps e) + m_sigma e + j , C~ = C.T`` — with `:8-11` defining the container:
"``m_sigma`` is the diagonal of the conductance star: one non-negative entry per primal edge, in siemens. It
represents distributed material conductivity and, *equally*, a lumped circuit load". The step is the staggered
leapfrog (`:15-18`), the σ term carried by the trapezoidal (Crank–Nicolson) rule (`:20-31`), `e^{n+1}[PEC] = 0`.

The stamp itself (`emfit/studies.py:2789-2793`) is three lines of arithmetic: free the load column's `E_x` edges
of PEC, then `sigma[edges] += 1.0 / (edges.size * float(load.value))`, under the comment "One element spread
over the ``len(edges)`` parallel paths." For run A the artefact records
`loads = [{kind: series_r, value: 50.0, column: 50, x: 0.02, n_edges: 9}]` **[M]** (`j_points = np.arange(j0,
j1 + 1)` is inclusive over `n_strip = 8` cells, so 9 `E_x` edges).

## S2 — Series or parallel, and the effective R

Three arithmetically possible readings of "50 Ω on 9 edges"; the code does exactly one **[R]**: 9 × 50 = **450 Ω**
(the edges in series); 50 / 9 = **5.556 Ω** (`R/edges.size`); or `1/(edges.size * R)` = 2.2222e-3 S per edge, nine
in parallel → 9 × 2.2222e-3 = **20.0 mS → 50.000 Ω**. The last is what is written: the *conductance* is divided by
9, which is the correct parallel split. The stamp is a 50 Ω resistor, exactly, by construction — not a factor-2
error in either direction.

The one real qualification is that it is a *sheet*, not a point: 20.0 mS over 9 edges of `dy = 0.4 mm`, i.e.
6.25 S/m of strip width **[R]**. For an edge voltage profile V_i the sheet impedance is
`R_eff = (1/G)·ΣV_i²/(ΣV_i)²`, whose Cauchy–Schwarz minimum is `1/(9G) = 50 Ω` at uniform `V_i` and which rises
(450 Ω if the current sat on one edge) **[L]**. The stamp can therefore only be *more* resistive than 50 Ω, never
25.5 Ω; the at-plane inversion of S4 gives Re Z = 49.55 Ω, so here the distribution penalty is under 1 %.

## S3 — The quantitative discretisation correction, and it is tiny

Crank–Nicolson on the σ term substitutes `d/dt → (2/dt)·tanh(s·dt/2)` in the Ampere law; at `s = jω` that leaves
**σ untouched** and multiplies **ε by `tan(x)/x` with `x = ω·dt/2`** (ε up, so Z0 slightly down and β slightly up)
**[L]**. There are no `ca`/`cb` coefficient arrays in the tree (NOT FOUND IN TREE); the coefficients are
`loss_num`/`loss_den` (`emfit/evolve.py:146-155`, with `rate = self.m_eps / self.dt` at `:154`).

For run A, `dt = 7.626299478123987e-13 s` **[M]**, `f = 5.827786408 GHz` **[M]** → `ω·dt = 0.0279253`,
`x = 0.0139626`, `tan(x)/x − 1 = 6.4990e-5`, leading term `(ω·dt)²/12 = 6.4985e-5` **[R]**. The load's own
impedance is real to 6.5e-5: a reactive error of ≈ 3e-3 Ω and a resistance error of 0.003 Ω — four orders below
the 31.6 Ω the hypothesis needs. **Not a factor-of-2 effect, nor a factor-of-1.1 effect.**

Mesh dispersion is the same order and lives in the *line*, not the load: `β·dx = 231.0874 × 4e-4 = 0.09244 rad`
**[M/R]**, leading Yee term `(β·dx)²/24 = 3.56e-4`; it moves the reference plane by a fraction of a cell, not R.
Documentation drift: `evolve.py:20-31` works its example on "8 parallel edges (G = 2.5e-3 S each)" while the
shipped path uses 9 at 2.2222e-3 S; both total 20.0 mS, but the quoted per-edge `a = dt·σ/ε` is 11 % off.

## S4 — Z_eff at 5.83 GHz

Predicted from the stamp alone: **Z_eff = 50.000 + j0.000 Ω**, with the S3 correction ≈ 3e-3 Ω **[R]**.

Measured, from `evidence/termination/build_A_50ohm_v3_twin_check.json` **[M]**: `s11_at_plane` =
0.0243065 + j0.0425447 (|Γ| = 0.048999, ∠60.26°) at `plane_index` 51, against a reference
`zc = 47.5366 + j1.9309 Ω` (a `LineReference` built from the load-free twin). Inverting `Z = zc(1+Γ)/(1−Γ)`:

* against the twin's `zc`: **49.548 + j6.260 Ω** **[R]**
* against a 50 Ω reference: **52.297 + j4.461 Ω** **[R]** — |Z| = 49.94 Ω either way.

The `+j` is the reference plane, not the element: the load sits at column 50 and the record at plane 51, so one
cell of line contributes `j·50·tan(β·dx) = j4.64 Ω` **[R]**, and the full j6.26 Ω corresponds to 0.54 mm of line
ahead of the element. Residual at the load itself: well inside 1 % of |Z|.

## S5 — Can the banked data produce 25.5 + j31.6 Ω?

Required reflection: `Γ = (Z−50)/(Z+50) = −0.12707 + j0.47173`, **|Γ| = 0.48854, ∠105.08°** **[R]**. Every
reflection banked for this run is far below it: |Γ| = 0.32556 (port, two-wave), 0.23217 (one-wave station fit),
0.048999 (at plane) **[M]**. The natural inversions **[R]**:

| source | inverted against | Z (Ω) |
|---|---|---|
| port | 50 Ω | 26.006 − j6.396 |
| port | twin `zc` | 24.971 − j5.077 |
| port, conjugated | 50 Ω | 90.649 − j22.295 |
| at plane | twin `zc` | 49.548 + j6.260 |

None is 25.5 + j31.6: the reactance sign is wrong in all four and nothing approaches +31.6 Ω — **not
reproducible [R]**. Its real part is reproducible, and revealingly so: `50(1−|s11|)/(1+|s11|) = 25.440 Ω` **[R]**.
The "~25.5 Ω" is |s11| = 0.3256 read as a *pure resistance with the phase discarded*; the "+j31.6" has no
counterpart anywhere in the artefact.

That reading also rests on a quantity the record itself declines to vouch for. Lossless de-embedding preserves
|Γ| up to the reference's own attenuation, `e^{−2αL} = e^{−2×3.1565×0.0072} = 0.956` **[M/R]**, so |Γ| = 0.0490 at
the load plane must appear as ≈ 0.0468 at the port — the record carries 0.32556, factor **6.95** over a 4.4 %
loss budget. The record already flags it: `s11.validation_status = UNVALIDATED`, with
`magnitude_one_wave_station_fit = 0.23217` kept beside it. Any argument built on the 0.3256 must first explain a
sevenfold magnitude excess on a passive 50 Ω load.

## S6 — Verdict

**(B) close to 50 + j0 → the effective-impedance hypothesis is REFUTED; a direct load-plane measurement is
required.** The stamp delivers 50.000 Ω real by construction, Crank–Nicolson moves it by 6.5e-5, and the one
measured load-plane inversion gives 49.5–52.3 Ω real with |Z| = 49.94 Ω, the small `+j` being ≤ 1.35 cells of
line ahead of the element — nothing in the discretisation turns 50 Ω into 25.5 + j31.6 Ω.

Settling artefact (one line): a record carrying `b_cut/a_cut` at the load's own column 50 **and** the de-embedded
port-plane Γ of the same waveform, the two required to agree to `e^{−2αL} = 0.956`; today's 6.95× spread does not.
