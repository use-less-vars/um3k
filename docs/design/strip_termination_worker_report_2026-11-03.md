# strip-termination-2026-11-03 — worker report

**Status: STOP CONDITION HIT at Phase B1.3. The D1 fix was applied, verified, then REVERTED.**
`emfit/studies.py` is byte-identical to its pre-dispatch state (sha256 `254076bc…1648f`, 5425 lines, 0 occurrences of `nx_clean`).
Phases C, D and E were NOT written — see §6.

## 1. Delivered

| File | Delta |
|---|---|
| `emfit/studies.py` | applied +13/−4 over 3 hunks, then **reverted to sha256 `254076bc…1648f`** (net 0) |
| `docs/design/dispatch_log.md` | untouched (2 rows not appended — §6) |
| `docs/design/strip_termination_host_run_2026-11-03.md` | not created (§6) |
| `docs/design/strip_termination_worker_report_2026-11-03.md` | this file |

Phase 0 backup hashes were identical (`254076bc72edefee7901293e95d9da8365e0b5ec70b660dff97d085c8551648f`).
**The brief's "3721-ish" line-count expectation is wrong: the real file is 5425 lines.** The doc's hunk header
`@@ -2703,9 +2703,10 @@` and anchors 2706/2709/2728/2793 all matched exactly, so only the expected count was wrong.

## 2. Diff applied (full `diff -u`, before revert)

```
@@ -2701,12 +2701,13 @@
     # --- PEC: the six walls plus the thin strip sheet ------------------------
+    nx_clean = nx - n_pml                             # last node layer clear of the xmax PML
     pec = np.array(cc.pec_edge_mask(), dtype=bool)
     strip = np.zeros(cc.n_edges, dtype=bool)
-    x_cells = np.arange(ix_port, nx)                  # ex edges run along x
+    x_cells = np.arange(ix_port, nx_clean)            # ex edges run along x
     j_points = np.arange(j0, j1 + 1)
     strip[cc.idx_ex(x_cells[:, None], j_points[None, :], k_strip)] = True
-    x_points = np.arange(ix_port, nx + 1)             # ey edges run along y
+    x_points = np.arange(ix_port, nx_clean + 1)       # ey edges run along y
     j_cells = np.arange(j0, j1)
@@ -2725,10 +2726,10 @@
-            if not ix_port < ix_load < nx:
+            if not ix_port < ix_load < nx_clean:
                 raise ValueError(
                     f"load at {load.position!r} m lands on node column "
-                    f"{ix_load}, outside the strip ({ix_port} < ix < {nx})")
+                    f"{ix_load}, outside the strip ({ix_port} < ix < {nx_clean})")
@@ -2799,6 +2800,14 @@
                 "ratio stops describing it.")
+        if cut_index is not None and ix_extract > nx_clean - 1:
+            raise ValueError(
+                f"s21_plane resolves to node column {ix_extract}, which is "
+                f"inside the xmax PML: the strip now ends at node column "
+                f"{nx_clean} (nx = {nx} less n_pml = {n_pml}), so the deepest "
+                f"admissible extraction plane is {nx_clean - 1}.  A plane in "
+                "the absorber measures the matched layer rather than the line "
+                "and would report the PML's decay as if it were the load's.")
```
3 hunks, +13/−4, net +9 lines (5425 → 5434). Nothing outside 2701–2810. No signature change, no new parameter,
`_slice_index` untouched. Post-edit `py_compile` = 0. `nx_clean` at 2704, 2707, 2710, 2729, 2732, 2803, 2807, 2808.

## 3. Tests — baseline vs post-edit (same command, 150 s cap both times)

`pytest tests/test_studies.py -k "station or s21 or plane or strip" -q -v`

| | result |
|---|---|
| BASELINE (pre-edit) | `..........` — **10 dots, no `F`**, NO summary → killed at the 150 s cap. Stall point = test **#11** |
| POST-EDIT | `........FF` — **8 dots then 2 `F`**, NO summary → killed at 150 s cap |

23 tests are selected (`--collect-only`). `-qq` from `addopts = "-q"` + CLI `-q` suppresses test names, so names
are mapped from collection order:
1 registered, 2 board_registered, 3 board_coerces, 4 board_refuses_pad, 5 wave_smoke, 6 z0_model, 7 eps_eff_beta,
8 dt_scale, **9 `test_microstrip_wave_refused_station_fit_is_flagged_not_quoted`**, **10 `test_microstrip_default_case_is_converged`**,
11 `test_microstrip_unsettled_record_is_labelled_not_reported` (stall point, both runs), 12 default_mesh_historical, …
**NEW FAILURES: #9 and #10. Both passed at baseline; both fail after the diff.** Confirmed by direct re-run:

* `test_microstrip_default_case_is_converged` → `assert result.beta == pytest.approx(232.5, rel=0.01)`
  **Obtained `326.8366386149376`, expected 232.5 ± 2.325** (a 40 % shift).
* `test_microstrip_wave_refused_station_fit_is_flagged_not_quoted` → FAILED (assertion, not the guard).
* Warning seen: `emfit/studies.py:3186` `RuntimeWarning` "loss-free station-impedance fit could not be formed
  (sigma_beta 152.06 > beta 17.06)" — the **pre-existing** station-fit warning the brief mentions (line moved
  3177 → 3186 by the +9 lines). Not chased, not caused by the fix.

Per the stop rule I did not retry the baseline and did not exceed the cap. `STATUS=0` in both runs is `tail`'s
exit status, not pytest's (the pipeline's last command), so it carries no pass/fail information.

## 4. Dispatch rows

**Not appended** (see §6). Both rows are reproduced verbatim here so nothing is lost.

*Row C (strip-termination-2026-11-03)* — as ordered, asserting "fix applied, awaiting host run" + 4 brackets.
*Row D (sweep-attribution-recon-2026-11-02)* — as ordered, forward correction to `s21-plane-sweep-2026-11-02`.

## 5. Host-run doc

Not created (§6). The Phase E safeguard check **was** performed (read-only):
`build_A_50ohm_v3_beta2wave.json` `meta.command_line` =
`evidence/termination/run_build_A.py --n-line 64 --load-at-mm 20 --load-ohm 50 --mem-ceiling-mb 2000 --s21-plane-index 51 --out evidence/termination/build_A_50ohm_v3_beta2wave.json`
— **matches the Phase E command in every flag except `--out`**; `s21.magnitude = 0.7628473102840976` confirmed;
`geometry.nx = 72`, `n_pml = 6`, `s21_plane_index = 51`, `loaded_without_reference` present. No mismatch to report.

## 6. Surprises / stop conditions

1. **STOP CONDITION (B1.3).** New failures #9 and #10 → reverted, sha256 confirmed. `beta` moving 232.5 → 326.8 on the
   *default, load-free* case is far too large to be explained by trimming metal out of a 6-cell absorber, and it points
   at the station span now straddling the new end face rather than at a benign re-baselining. **This needs an owner
   decision, not a worker guess:** either the two tests encode the old shorted-stub behaviour and must be re-baselined
   with evidence, or the fix alters the line too much to be the right one.
2. **Phases C, D, E NOT written — deliberate.** Row C asserts "fix applied, awaiting host run" and row E would send the
   owner to `--out …_v3_terminated.json` against a tree that no longer contains the fix; both would falsify the record
   and a "terminated" artefact produced by unfixed code is worse than no artefact. Say the word and they go in verbatim.
   Row D is independent of the code state and *could* be appended as-is; I left it out only so the log stays consistent.
3. **`/tmp` is not shared between container calls.** The Phase 0 backup and the post-edit `/tmp/studies.py.new` did not
   survive to the next tool call. I reconstructed the original by reverse-applying my three exact replacements and
   verified it against the Phase 0 sha256 before writing it back — the restore is hash-proven, but the backup is gone.
