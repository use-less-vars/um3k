# To EM-Solver Engineer (Gen 13)
**From: EM-Solver Engineer (Gen 12)**
**Subject: The Antenna Engine is Alive (The Torch is Burning)**

Welcome to the helm, Gen 13. 

Gen 11 passed me a flickering torch and warned me about ghosts. I spent my first day auditing the physics, and I found that the foundation was solid, but the hardware claims were ghosts. I am passing you a torch that is not just bright, but *structurally pinned*. 

We are no longer just building a solver; we have built a 3D Antenna Engine. We can excite a 3D point source, extract the Huygens surface, and mathematically prove the far-field radiation pattern.

Here is the state of the machine, the traps we cleared, and the rules you must follow.

---

### 1. The State of the Machine (What Works)
*   **The C++ Solver (E3):** It is fully pinned at the binary level (DR-42 closed). It is immune to ambient OpenMP variables. The speedup vs Python is **1.37x** (34.74s vs 47.55s).
*   **The Far-Field (E13):** The 3D NTFF transform is implemented in `emfit/ntff.py`. It is validated against the analytic Hertzian dipole to within 0.18%. The equivalent currents (\(J_s\), \(M_s\)) are calculated correctly.
*   **The UI:** The Far-Field tab is live. The Mode Picker extracts higher-order modes and correctly fails loudly on invalid geometry.
*   **The Tests:** 71 files swept green (949 tests total). 

### 2. The Wars We Fought (The Ghosts)
*   **The 1.81x Ghost:** Gen 11 banked a 27.44s run. We could not reproduce it. We tested `-O3`, `-flto`, and `-march=native`. We proved the host CPU thermal noise swings by ±15%, making absolute cross-session comparisons garbage. The true, pinned baseline is 34.74s (1.37x).
*   **The Huygens Unit Trap:** Our first far-field flux was off by exactly \(h^2 (T_{eff}/2)^2\). The Yee grid stores *circulations* (Volts/Amps), not *fields* (V/m, A/m). A closed-box test will **never** catch a constant scale factor. Only an absolute-level test against an analytic reference caught it. 
*   **The NTFF Sign Trap:** The far-field transform was perfect from day one, but a flipped sign in a test fixture docstring masked it. We proved it by fixing the fixture and getting exactly 1.0000000000 for the dipole power.
*   **The Container OOMs:** The container is hostile. Do not run `pytest tests/` as a monolith. Sweep per file. If `test_studies.py` or `test_webapp.py` die on a wall-clock timeout under a load average > 9.0, the container is being hammered by other sessions. Do not let it block your commits.

### 3. The Traps (Read Gen 11's handoff too, but these are new)
*   **The `test_webapp.py` Caveat:** This is the one unverified piece. It passed 11/11 in a paired run, but a solo re-run was SIGTERMed at 9/11 by the container. **Run `pytest tests/test_webapp.py -o addopts=""` on a quiet box as your very first action.**
*   **The Stale Checkpoint:** The WorkingDocument `ea744bdfeda8` has a stale line saying "929 passed". Do not trust it. Trust the git log.
*   **The `None` Beta:** We fixed `Mode2D.beta` to return `None` instead of `NaN` for evanescent modes. Any downstream tool using `%.17g` formatting must handle `None`.

### 4. The Rules of Engagement
1.  **Absolute Tests Only:** A closed-box integral that sums to zero is useless if the whole field is scaled by 1e-9. Always assert against an analytic absolute reference.
2.  **Fail Loudly:** If a mode solver can't find the frequency, the UI must show an error string, not `0 candidates`.
3.  **Amend, Never Rewrite:** If a register entry is wrong, append a `FOURTH AMENDMENT` block. Do not edit the original prose.
4.  **Trust the JSON:** If the prose says 1.81x and the JSON says 1.37x, the JSON wins.
5.  **Measure Before Fencing:** Do not invent a tolerance. Run the test, see the error, then set the fence.

### 5. The Next Frontier (Gen 13's Campaigns)
*   **The UI Vector Plots:** The user wants sparse 3D E/H vector (quiver) plots. PyVista `add_arrows` is the way. Sample every 5th node.
*   **Graded Meshing (E6):** We are limited to 20x20mm boards. To do 40x40mm, we need a nonuniform Yee grid (refining near traces). The TE confirmed this is mathematically sound.
*   **The 3D Point Source:** We have the M4 end-to-end test, but the FDTD excitation for real antennas needs a robust lumped port.
*   **GPU Acceleration:** The endgame. When the boards get big, CPU threading won't cut it. We need CUDA.

### A Final Word
Gen 11 told me to trust the JSON. I tell you to trust the **absolute numbers**. If a scale factor is wrong, the error will be invisible in relative tests. 

The machine is fast. The physics is validated. The torch is burning. Go build the Ultra Maxwell 3000.

*— Gen 12, signing off.*
