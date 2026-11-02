# The strip reaches the far wall: making the load terminate the line

**Status:** proposal, not applied. No source edited, no solve run.
**Date:** 2026-11-02
**Target:** `emfit/studies.py`, strip-mask construction. All line numbers verified against the working tree.

## A. The problem

The microstrip strip mask is PEC-continuous to the far wall at node `nx`. `emfit/studies.py:2704-2712` takes the six PEC walls from `cc.pec_edge_mask()`, then fills the strip mask with **`ex`** edges over `x_cells = np.arange(ix_port, nx)` and **`ey`** edges over `x_points = np.arange(ix_port, nx + 1)`, and ORs the result into `pec`. The xmax PML is built *outside* that wall, not inside it, so the conductor runs the whole length of the domain and is short-circuited to the xmax PEC face. The load - a sigma stamp on one `ex` column, `2732-2736` - is therefore not a termination at all: it is a series element inside a shorted stub whose far end is a PEC wall 22 cells away (arm A) or 12 cells away (arms B, D, E). The measured transmission on arm B is `|s21| = 1.1688893`, above the model-free passivity ceiling of 1 that holds for a series resistance in a line for **any** beta, any Z0 and any L; the same defect is visible on arm E at `1.0196007`. No choice of beta can remove that excess, so the closed-form comparison is currently being made against a structure the model does not describe.

## B. Proposed change (diff shown only; not applied)

End both eye-node masks at the PML start instead of at the outer wall, so the metal stops at the last clean node layer and the absorber is the only thing beyond it.

```diff
--- a/emfit/studies.py
+++ b/emfit/studies.py
@@ -2703,9 +2703,10 @@
 # --- PEC: the six walls plus the thin strip sheet ------------------------
+nx_clean = nx - n_pml                             # last node layer clear of the xmax PML
 pec = np.array(cc.pec_edge_mask(), dtype=bool)
 strip = np.zeros(cc.n_edges, dtype=bool)
-x_cells = np.arange(ix_port, nx)                  # ex edges run along x
+x_cells = np.arange(ix_port, nx_clean)            # ex edges run along x
 j_points = np.arange(j0, j1 + 1)
 strip[cc.idx_ex(x_cells[:, None], j_points[None, :], k_strip)] = True
-x_points = np.arange(ix_port, nx + 1)             # ey edges run along y
+x_points = np.arange(ix_port, nx_clean + 1)       # ey edges run along y
 j_cells = np.arange(j0, j1)
 strip[cc.idx_ey(x_points[:, None], j_cells[None, :], k_strip)] = True
```

Two reasons for `nx_clean = nx - n_pml` and not the alternative `nx - n_pml + 1`. The `ex` mask indexes *cells* between nodes, so `arange(ix_port, nx_clean)` leaves the last metal cell at `x = nx_clean - 1`, wholly outside the PML. The `ey` mask indexes *nodes*, and `arange(ix_port, nx_clean + 1)` ends on node `nx_clean`, which is the shared node of that last cell - the two masks stay edge-consistent at the new end face exactly as they are at the old one. Moving only one of them would open the strip along one edge family and create a one-cell slot line.

## C. Knock-on analysis

**`ix_extract` gains a real ceiling.** The deepest admissible extraction plane becomes `nx_clean - 1 = nx - n_pml - 1`. Nothing in `studies.py` enforces it: the file contains no occurrence of `nx - n_pml` at all, and `ix_extract` is only range-checked upstream (`2793-2801`) and stored (`3608`). The check that a plane lies outside the xmax PML lives in the writer, `evidence/termination/run_build_A.py` (`inside_xmax_pml`, `last_clean_plane = nx - n_pml - 1`), so the two must agree on the same constant - they now do by construction, which is the point.

**`_slice_index` needs no change.** `def _slice_index(plane, *, n_sub, n_air, k_strip)` at `3680`, called once at `2695`, maps a *z* plane name to a *z* index. It never looks at x extents or at `n_pml`.

**The AC-6 `inside_xmax_pml` check does not become stricter in form, only meaningful.** Before the fix a plane inside the xmax PML could still lie on PEC metal, so "inside PML" and "on the strip" were different statements and a plane there was wrong for two reasons. After the fix the strip ends where the PML starts, so the existing check is exactly the right one and its pass/fail semantics are unchanged.

**The load-placement guard becomes too loose and must be tightened.** `2728` reads `if not ix_port < ix_load < nx:`; after the change a load at `nx_clean <= ix_load < nx` would be stamped in the absorber with no metal under it. Proposed replacement, same shape and same message wording:

```python
            if not ix_port < ix_load < nx_clean:
                raise ValueError(
                    f"load at {load.position!r} m lands on node column "
                    f"{ix_load}, outside the strip ({ix_port} < ix < {nx_clean})")
```

**A second guard should be added** for the down-stream side of the new ceiling: `if cut_index is not None and ix_extract > nx_clean - 1: raise ValueError(...)` beside `2793-2801`, so a request for a plane in the absorber fails at configuration time rather than returning a contaminated reading. The upstream guard at `2793-2801` stays reachable and unchanged.

**Extraction readers are unaffected**: `2904-2907` (accumulator, signals, `cut_column`), `2965-2967` (`plate_current` at `ix_extract - 1` and `ix_extract`), `3324`/`3332` (`x_cut = float(ix_extract * cell)`), `3604`/`3608`, `3669` all take the index as given.

## D. Tests that would catch a regression (proposed, not written)

1. **Load-free passivity.** A load-free run, any mesh, extraction at a plane downstream of the port: `|s21|` close to 1 within a few per cent. This is the pure-strip control; it is currently untestable as a passivity statement because the strip-only line is a shorted stub and its transmission is whatever the stub resonance gives.
2. **Loaded transmission is passive.** Arm A or B geometry with R = 50: `|s21| < 1` strictly, on both `magnitude` and `raw_magnitude`. This is the assertion that would have failed loudly on the current tree (B reads `1.1688893`).
3. **Upstream extraction still refused.** `s21_plane` at `ix_load - 1` raises, message still names the cut. Guards against the new ceiling code accidentally replacing rather than augmenting the upstream test at `2793`.
4. **Load in the absorber refused.** A load position resolving to `ix_load >= nx_clean` raises the tightened `2728` message. This is the regression that the fix itself introduces.
5. **End-face edge consistency.** Constructing the geometry on a small mesh gives a strip whose `ex` and `ey` masks share the same terminal node layer - the check that catches moving only one of `2706`/`2709`.

## E. What NOT to change

* **The load stamp mechanism.** `2721-2748`: `pec[edges] = False` on the cut column, `sigma[edges] += 1.0/(edges.size*value)`, the capacitive branch's `n_sub/n_strip` bookkeeping, `m_sigma`/`m_eps`. It is correct and it is the thing the fix is meant to set free.
* **The zc priority: `station_fit` first, reference second.** That ordering was verified against a stale brief and is not stale - it must not be "corrected".
* **The two-wave `s11` writer path.** Untouched by this change; the reflection is computed from the same `ix_extract` and needs no edit.
* **`beta_two_wave` emission.** Its value (`231.55331672912826` rad/m on `build_A_50ohm_v3_beta2wave.json`) is a property of the geometry, not of the termination; leave the emission alone so the before/after comparison stays one-variable.
* **`plane_sweep_diagnostic`.** The sweep is the instrument that will show whether the fix worked; editing it in the same change destroys the comparison.
* **`n_pml`, the PML itself, `pml_walls` at `2805`, and the port reference plane** `ix_port = n_pml + n_ref`.

## F. Checkpoint plan

One arm, not the matrix. Re-run **arm A** (R = 50, `nx = 72`, `ix_load = 50`) on the new geometry and read `|s21|` at plane `ix_load + 1 = 51` - one column downstream of the cut, the shallowest admissible plane, so the reading is not yet affected by the stub that remains between the load and `nx_clean`.

Cost is one solve, no sweep and no B/E re-run. Decision rule:

* **The fix is falsified** if `|s21|` at plane 51 is still `> 1`. Nothing about beta, Z0 or the plane convention can lift a passive structure above the ceiling, so a value above 1 means a second reflection path survives - most likely the xmax face still shorting through the absorber, or the cut column's `ey` edges still tying the two halves together.
* **The anchor is falsified** if `|s21|` falls below 1 but lands far from the closed-form value computed at `L = nx_clean - ix_load` cells with `Z0 = 47.53662`. That would say the load, not the termination, is mis-described - and the first place to look is the plane convention (`ix_load + 1` versus the station span), not the strip.
* **Both survive** if `|s21|` is below 1 and within a few per cent of the closed form: then the anchor can be trusted for the first time, and arms B/E follow as confirmation rather than exploration.
