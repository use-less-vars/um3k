import numpy as np
import os

def load(name):
    path = f"evidence/referee/{name}"
    if not os.path.exists(path): return None
    return np.loadtxt(path, comments='%')

print("--- Loading MSLPort records ---")
uA = load("port_1_utA"); uB = load("port_1_utB")
iA = load("port_1_itA"); iB = load("port_1_itB")
u2 = load("port_ut_2"); i2 = load("port_it_2")

if uA is None:
    print("MSLPort files missing."); exit(1)

t = uA[:, 0]
v1 = uA[:, 1] - uB[:, 1]
i1 = iA[:, 1]
v2 = u2[:, 1]
iv2 = i2[:, 1]

print(f"Port 1 V/I (should be ~48 ohm): {np.sqrt(np.mean(v1**2)) / np.sqrt(np.mean(i1**2)):.4f} ohm")
print(f"Port 2 V/I (should be 50.0 ohm): {np.sqrt(np.mean(v2**2)) / np.sqrt(np.mean(iv2**2)):.4f} ohm")

f_target = 5.827786408327286e9
omega = 2 * np.pi * f_target
phase = np.exp(-1j * omega * t)

Z0 = 50.0
a1 = (v1 + Z0 * i1) / 2; b1 = (v1 - Z0 * i1) / 2
A1 = np.sum(a1 * phase); B1 = np.sum(b1 * phase)
a2 = (v2 + 50.0 * iv2) / 2; b2 = (v2 - 50.0 * iv2) / 2
A2 = np.sum(a2 * phase); B2 = np.sum(b2 * phase)

S11 = B1 / A1; S21 = B2 / A1
print(f"\n--- Results at {f_target/1e9:.3f} GHz ---")
print(f"|S11| = {abs(S11):.6f}  (Artefact: 0.325565 | Anchor: 0.342354)")
print(f"|S21| = {abs(S21):.6f}  (Artefact: 0.761705)")
