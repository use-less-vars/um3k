#!/usr/bin/env python3
"""59V Phase B -- one static screen: a field you may look at, a number you may not.

Frozen spec: viz/acceptance.md.   Fence: this script writes only inside viz/.
Run:  PYTHONDONTWRITEBYTECODE=1 python3 viz/d59v_screen.py
No solve is run and no solver artefact is modified; every transform is declared on
the figure itself.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import textwrap
import zipfile

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from numpy.lib import format as npformat
from PIL import Image

ROOT = "/workspace"
HERE = os.path.join(ROOT, "viz")
OUT = os.path.join(HERE, "out")
F1 = os.path.join(ROOT, ".scratch", "s10118_mixed_mode.npz")
F2 = os.path.join(ROOT, ".scratch", "host", "m3a-smoke", "plane_record.npz")

DPI, FIGW, FIGH = 130, 16.0, 9.0
os.makedirs(OUT, exist_ok=True)

DRAWN = []          # every string drawn on the figure, in draw order
def rec(s):
    DRAWN.append(s)
    return s

def fill(s, width=96):
    return rec(textwrap.fill(" ".join(str(s).split()), width=width))

# ---------------------------------------------------------------- load panel 1
if not os.path.exists(F1):
    sys.exit(f"FATAL: missing {F1}")
with np.load(F1) as d1:
    if "e_z_node" not in d1.files:
        sys.exit(f"FATAL: key 'e_z_node' absent from {F1}; keys={d1.files}")
    ez = np.asarray(d1["e_z_node"], dtype=float)
    xs = np.asarray(d1["xs"], dtype=float)
    zs = np.asarray(d1["zs"], dtype=float)
EZ_DTYPE, EZ_RAW = ez.dtype.str, tuple(ez.shape)
NX, NZ = int(xs.size), int(zs.size)
if ez.size != NX * NZ:
    sys.exit(f"FATAL: e_z_node.size={ez.size} != len(xs)*len(zs)={NX*NZ}")
# node index = j*nx + i for (xs[i], zs[j])  -> .scratch/logs/s10118_basis.py:321
GRID = ez.reshape(NZ, NX)            # rows = zs, cols = xs
EZ_SHAPE = tuple(GRID.shape)
LIM = float(np.max(np.abs(ez)))

# ------------------------------------------------- panel 2: headers only, no arrays
def npz_headers(path):
    hdr = {}
    with zipfile.ZipFile(path) as z:
        for name in sorted(z.namelist()):
            if not name.endswith(".npy"):
                continue
            with z.open(name) as fh:
                ver = npformat.read_magic(fh)
                if ver == (1, 0):
                    shp, fort, dt = npformat.read_array_header_1_0(fh)
                elif ver == (2, 0):
                    shp, fort, dt = npformat.read_array_header_2_0(fh)
                else:
                    shp, fort, dt = npformat._read_array_header(fh, ver)
            hdr[name[:-4]] = (dt.str, tuple(int(s) for s in shp))
    return hdr

if not os.path.exists(F2):
    sys.exit(f"FATAL: missing {F2}")
HDR = npz_headers(F2)
F2_BYTES = os.path.getsize(F2)
SP_KEYS = ["f", "v", "i", "z0", "beta", "s11_measured", "s11_port", "s21",
           "s21_power", "passivity", "passivity_power", "refused"]
missing = [k for k in SP_KEYS if k not in HDR]
if missing:
    sys.exit(f"FATAL: keys absent from {F2}: {missing}")
SP = {k: HDR[k] for k in SP_KEYS}
NZERO = sum(1 for k in SP_KEYS if int(np.prod(SP[k][1])) == 0)
NONEMPTY = [k for k in SP_KEYS if int(np.prod(SP[k][1])) != 0]
PLANE_EZ = HDR.get("plane_Ez")

# ------------------------------------------------------------------ the figure
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.0,
    "svg.hashsalt": "d59v",
    "figure.dpi": DPI,
    "savefig.dpi": DPI,
})
fig = plt.figure(figsize=(FIGW, FIGH), dpi=DPI)

S1 = "A tier is a ceiling: it can be lowered by new evidence, not raised by emphasis. E5 is assertion, not measurement; it must not be quoted."
S2 = "This panel contains values that are not citable."

fig.text(0.5, 0.982, rec("59V Phase B \u2014 one field you may look at, and one number you may not"),
         ha="center", va="top", fontsize=15, weight="bold")
fig.text(0.5, 0.947,
         fill("Two panels, two artefacts already on disk. No solve was run and no solver output was regenerated. "
              "Every number on this figure is either a value stored in an array read from disk, or a value quoted "
              "from docs/design/soundness.md; each panel carries the tier badge its quantity's ledger row gives it. "
              "Badge encoding: viz/acceptance.md \u00a73.1.", 150),
         ha="center", va="top", fontsize=8.2)

# ------------------------------------------------------------------- panel 1
fig.text(0.040, 0.878, rec("PANEL 1 \u00b7 A FIELD YOU MAY LOOK AT \u2014 mixed-mode e_z, raw node vector"),
         fontsize=11, weight="bold", va="bottom")
ax1 = fig.add_axes([0.050, 0.395, 0.335, 0.455])
im = ax1.imshow(GRID, origin="lower", aspect="equal", interpolation="nearest",
                extent=[float(xs[0]), float(xs[-1]), float(zs[0]), float(zs[-1])],
                cmap="RdBu_r", vmin=-LIM, vmax=LIM)
ax1.set_xlabel("xs \u2014 stored axis, units not stored", fontsize=7.5)
ax1.set_ylabel("zs \u2014 stored axis, units not stored", fontsize=7.5)
ax1.tick_params(labelsize=6.5)
ax1.set_title("e_z_node \u2190 .scratch/s10118_mixed_mode.npz", fontsize=8.2)
DRAWN_TITLE1 = ax1.get_title()
cbar = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.03)
cbar.ax.tick_params(labelsize=6.0)
cbar.set_label("stored e_z_node value, units not stored", fontsize=6.8)

cap1 = [
    fill("File: /workspace/.scratch/s10118_mixed_mode.npz   \u00b7   Key: e_z_node   \u00b7   dtype %s   \u00b7   raw shape %s as stored."
         % (EZ_DTYPE, EZ_RAW), 92),
    fill("Reshape (declared, not a transform of values): %s \u2192 %s in C order \u2014 rows are the zs index, columns the xs index. "
         "Basis: .scratch/logs/s10118_basis.py:321, 'structured_mesh node index must be j*nx + i for (XS[i], ZS[j])', "
         "with nx = len(xs) = %d and nz = len(zs) = %d. The transpose (31, 17) is deliberately NOT used: it would put xs on the "
         "vertical axis and put the field on its side against that line." % (EZ_RAW, EZ_SHAPE, NX, NZ), 92),
    fill("Display transform (declared): colour = diverging linear on the stored e_z_node values, interpolation='nearest', "
         "limits \u00b1max|e_z_node| = \u00b1%.6g on both sides, no normalisation, no smoothing, no cropping, no dB, no interpolation "
         "onto a finer grid. Colourbar tick labels are stored values under that same linear mapping. Units are not stored "
         "on the array or on either axis, so none are supplied." % LIM, 92),
    fill("What this panel is not: this is a raw plot of one eigenvector component. No mode amplitude is normalised, no power, "
         "flux or impedance is formed, no effective index is computed. Whether the profile is physically correct is a "
         "separate question that needs a convergence study this cached file cannot supply.", 92),
]
fig.text(0.040, 0.372, "\n".join(cap1), fontsize=6.9, va="top", linespacing=1.42)

# ------------------------------------------------------------------- panel 2
fig.text(0.470, 0.878, rec("PANEL 2 \u00b7 A NUMBER YOU MAY NOT \u2014 the S-parameter refusal"),
         fontsize=11, weight="bold", va="bottom")
ax2 = fig.add_axes([0.470, 0.372, 0.520, 0.478])
ax2.set_xlim(0, 1); ax2.set_ylim(0, 1); ax2.set_axis_off()
y = 0.985
def line(txt, dv=0.049, fs=7.6, mono=False, weight="normal", color="black"):
    global y
    ax2.text(0.006, y, rec(txt), fontsize=fs, va="top", ha="left", weight=weight, color=color,
             fontfamily="DejaVu Sans Mono" if mono else "DejaVu Sans")
    y -= dv
    return txt

line("Sought: a quotable complex s11 or s21 \u2014 a number with a true error bar \u2014 for the nine station planes this same file records.")
line("Looked in: /workspace/.scratch/host/m3a-smoke/plane_record.npz (%d bytes on disk). Keys, dtypes and shapes were read from the "
     "archive headers; the arrays themselves were never loaded." % F2_BYTES)
line("Found: %d S-parameter-related keys, all present, and %d of them carry ZERO samples. Nothing was substituted for them: no zero, "
     "no placeholder curve, no reconstruction, no simulated line." % (len(SP_KEYS), NZERO))
y -= 0.008
line("  %-17s %-12s %-9s %s" % ("key", "dtype", "shape", "reading"), dv=0.0, fs=6.5, mono=True, weight="bold")
y -= 0.030
READING = {
    "f": "no frequency axis", "v": "no wave amplitudes at the stations", "i": "no currents at the stations",
    "z0": "no reference impedance", "beta": "no propagation constant",
    "s11_measured": "no measured reflection", "s11_port": "no port-plane reflection",
    "s21": "no transmission", "s21_power": "no power-wave transmission",
    "passivity": "no passivity check", "passivity_power": "no power-wave passivity check",
    "refused": "no refusal flags",
}
for k in SP_KEYS:
    dt, shp = SP[k]
    line("  %-17s %-12s %-9s %s" % (k, dt, str(shp), READING[k]), dv=0.026, fs=6.5, mono=True)
y -= 0.012
line("For contrast, in the same file plane_Ez is stored as %s %s \u2014 the field planes are real. The field is present; the "
     "S-parameter is absent. That asymmetry is this panel." % (PLANE_EZ[1], PLANE_EZ[0]) if PLANE_EZ else
     "For contrast, in the same file plane_Ez is stored; the field planes are real, the S-parameter is absent.")

# ---- E5 badge: double rule + 45 deg hatch + value struck through
bx0, by0, bw, bh = 0.006, 0.012, 0.988, 0.300
ax2.add_patch(Rectangle((bx0, by0), bw, bh, facecolor="white", edgecolor="black",
                        hatch="////", linewidth=1.0, zorder=1))
ax2.add_patch(Rectangle((bx0 - 0.008, by0 - 0.013), bw + 0.016, bh + 0.026, facecolor="none",
                        edgecolor="black", linewidth=1.0, zorder=2))
by = by0 + bh - 0.035
ax2.text(bx0 + 0.012, by, rec("E5 \u2014 NOT CITABLE"), fontsize=15, weight="bold", color="#8b0000",
         va="top", zorder=3)
ty = by - 0.075
ax2.text(bx0 + 0.012, ty, rec("s21"), fontsize=13, style="italic", va="top", zorder=3)
ax2.add_line(Line2D([bx0 + 0.010, bx0 + 0.052], [ty - 0.012, ty - 0.012], color="black", linewidth=2.2, zorder=4))
ax2.text(bx0 + 0.060, ty, rec("struck through: the value this figure is not allowed to show"),
         fontsize=8.4, va="top", zorder=3)
by2 = ty - 0.052
ax2.text(bx0 + 0.012, by2,
         rec("soundness.md row C4: 'claim C4: the S-parameters are quotable' \u2014 tier E5, scope 'none: nothing about quotability is measured'."),
         fontsize=7.4, va="top", zorder=3)
ax2.text(bx0 + 0.012, by2 - 0.040,
         rec("Recorded against it: D09, F14, G04, G06 \u2014 each a recorded FAIL; T4_amp stands FAIL at 44.09 %, T2_agree at 9.03x tol."),
         fontsize=7.4, va="top", zorder=3)
ax2.text(bx0 + 0.012, by2 - 0.080,
         rec("NONE ON DISK \u2014 this box carries no value because the file carries none."),
         fontsize=7.4, va="top", weight="bold", zorder=3)

# ---------------------------------------------------------- fixed sentences
fig.text(0.040, 0.223, rec(S1), fontsize=7.8, va="top", style="italic")
fig.text(0.470, 0.223, rec(S2), fontsize=7.8, va="top", style="italic", weight="bold")

# ------------------------------------------------------------- badge legend
axL = fig.add_axes([0.040, 0.030, 0.925, 0.150]); axL.set_xlim(0, 1); axL.set_ylim(0, 1); axL.set_axis_off()
axL.text(0.000, 1.02, fill("Badge legend \u2014 the three styles below are STYLE SAMPLES ONLY. No quantity on this figure is E1; the E1 "
                           "sample is drawn so that the E5 style can be compared against a citable style in greyscale (acceptance.md A7).", 150),
         fontsize=7.0, va="bottom")

def sample(x0, w, tier_text, caption, hatch=None, ls="-", lw=1.5, double=False,
           grey=None, qmark=False, strike_on=None):
    h = 0.44
    axL.add_patch(Rectangle((x0, 0.36), w, h, facecolor=(grey if grey else "white"),
                            edgecolor="black", linestyle=ls, linewidth=lw,
                            hatch=hatch, fill=True, zorder=1))
    if double:
        axL.add_patch(Rectangle((x0 - 0.004, 0.335), w + 0.008, h + 0.05, facecolor="none",
                                edgecolor="black", linewidth=1.0, zorder=2))
    axL.text(x0 + 0.008, 0.60, rec(tier_text), fontsize=7.6, weight="bold", va="center", zorder=3)
    if qmark:
        axL.text(x0 + w - 0.030, 0.60, rec("?"), fontsize=10, va="center", ha="center", zorder=3,
                 bbox=dict(boxstyle="square,pad=0.12", facecolor="white", edgecolor="black", linewidth=0.8))
    if strike_on:
        axL.text(x0 + w - 0.075, 0.60, rec(strike_on), fontsize=8.5, style="italic", va="center", zorder=3)
        axL.add_line(Line2D([x0 + w - 0.082, x0 + w - 0.030], [0.60, 0.60], color="black", linewidth=2.0, zorder=4))
    axL.text(x0 + 0.008, 0.22, fill(caption, 46), fontsize=6.3, va="top")

sample(0.000, 0.300, "E1 PROVEN",
       "single solid 1.5 pt rule, plain field, value unstruck \u2014 style sample only.", lw=1.5)
sample(0.340, 0.300, "E5  NOT CITABLE",
       "double rule + 45\u00b0 hatch + value struck through \u2014 this is panel 2's badge.",
       hatch="////", lw=1.0, double=True, strike_on="s21")
sample(0.680, 0.300, "UNKNOWN",
       "dotted rule + 50 % grey '?' tiling + boxed '?' \u2014 this is panel 1's badge.",
       ls=":", lw=1.2, grey="0.83", qmark=True)

# ------------------------------------------------------------- panel-1 badge
bx, byy, bwd, bht = 0.400, 0.640, 0.078, 0.052          # figure fractions
axf = fig.add_axes([bx, byy, bwd, bht]); axf.set_xlim(0, 1); axf.set_ylim(0, 1); axf.set_axis_off()
axf.add_patch(Rectangle((0.01, 0.06), 0.98, 0.88, facecolor="0.83", edgecolor="black",
                        linestyle=":", linewidth=1.2, fill=True))
axf.text(0.05, 0.50, rec("UNKNOWN"), fontsize=8.0, weight="bold", va="center")
axf.text(0.72, 0.50, rec("?"), fontsize=9.0, va="center", ha="center",
         bbox=dict(boxstyle="square,pad=0.10", facecolor="white", edgecolor="black", linewidth=0.8))
fig.text(bx + bwd + 0.006, byy + bht * 0.62,
         fill("no row in docs/design/soundness.md names e_z_node or the mixed-mode profile, so panel 1 is badged "
              "UNKNOWN and not given a neighbour's tier (acceptance.md \u00a74).", 74),
         fontsize=6.3, va="center")

# every string actually rendered, read back off the live figure (axis + tick labels)
for _a in fig.axes:
    if not _a.axison:          # axis switched off -> its tick labels are never rendered
        continue
    for _t in list(_a.get_xticklabels()) + list(_a.get_yticklabels()):
        if _t.get_text() and _t.get_visible():
            rec(_t.get_text())
    if _a.axison and _a.get_xlabel():
        rec(_a.get_xlabel())
    if _a.axison and _a.get_ylabel():
        rec(_a.get_ylabel())

# --------------------------------------------------------------- save, deterministic
png = os.path.join(OUT, "screen.png")
svg = os.path.join(OUT, "screen.svg")
fig.savefig(png, dpi=DPI, metadata={"Software": None})
fig.savefig(svg, dpi=DPI, metadata={"Date": None})
plt.close(fig)

# --------------------------------------------------------------- greyscale audit
im = Image.open(png).convert("RGB")
W, H = im.size
a = np.asarray(im).reshape(-1, 3).astype(np.int64)
n_rgb = int(np.unique(a[:, 0] * 65536 + a[:, 1] * 256 + a[:, 2]).size)
L = np.asarray(im.convert("L"))
n_grey_full = int(np.unique(L).size)
half = im.convert("L").resize((W // 2, H // 2), Image.LANCZOS)
n_grey_half = int(np.unique(np.asarray(half)).size)

def dark_frac(x0, y0, x1, y1):
    c = L[int((1 - y1) * H):int((1 - y0) * H), int(x0 * W):int(x1 * W)]
    return float((c < 96).mean()), int(np.unique(c).size)

e5_dark, e5_levels = dark_frac(bx0 * 0.520 + 0.470, 0.372 + 0.012 * 0.478,
                               0.470 + 0.520, 0.372 + (0.012 + 0.300) * 0.478)
e1_dark, e1_levels = dark_frac(0.040, 0.030 + 0.36 * 0.150, 0.040 + 0.300 * 0.925, 0.030 + 0.80 * 0.150)
unk_dark, unk_levels = dark_frac(0.040 + 0.680 * 0.925, 0.030 + 0.36 * 0.150, 0.040 + 0.980 * 0.925, 0.030 + 0.80 * 0.150)

# --------------------------------------------------------------- sidecars
acc_raw = open(os.path.join(HERE, "acceptance.md")).read()
acc = " ".join(acc_raw.split())   # markdown line-wraps are not part of the sentence

json.dump({
    "figure": {"png": "viz/out/screen.png", "svg": "viz/out/screen.svg",
               "pixels": [W, H], "dpi": DPI},
    "panels": [
        {"panel": 1, "title": DRAWN_TITLE1, "source_path": F1, "keys": ["e_z_node", "xs", "zs"],
         "shape": list(EZ_SHAPE), "raw_shape": list(EZ_RAW), "dtype": EZ_DTYPE,
         "tier": "UNKNOWN",
         "tier_source": "no row in docs/design/soundness.md names e_z_node or the mixed-mode profile; acceptance.md \u00a74 sets UNKNOWN",
         "display_transforms": ["reshape (527,) -> (17,31) in C order, rows=zs, cols=xs; basis .scratch/logs/s10118_basis.py:321",
                                "colour = diverging linear on stored e_z_node, limits +/-max|e_z_node| = +/-%.17g" % LIM,
                                "cmap RdBu_r, interpolation='nearest', origin='lower', aspect='equal'"],
         "derived_labels": []},
        {"panel": 2, "title": "the S-parameter refusal", "source_path": F2,
         "keys": SP_KEYS, "headers_only": True,
         "shapes": {k: {"dtype": SP[k][0], "shape": list(SP[k][1])} for k in SP_KEYS},
         "zero_length_keys": NZERO, "nonempty_keys": NONEMPTY,
         "tier": "E5", "tier_source": "docs/design/soundness.md row C4",
         "display_transforms": ["none: no array values were read (headers only)"],
         "derived_labels": []},
    ],
    "fixed_sentences": {"ceiling": S1, "not_citable": S2},
    "fixed_sentences_verbatim_in_acceptance_md": {"ceiling": S1 in acc, "not_citable": S2 in acc},
    "greyscale": {"rgb_unique": n_rgb, "L_unique_full": n_grey_full, "L_unique_half": n_grey_half,
                  "e5_badge_dark_frac": e5_dark, "e5_badge_levels": e5_levels,
                  "e1_sample_dark_frac": e1_dark, "e1_sample_levels": e1_levels,
                  "unknown_sample_dark_frac": unk_dark, "unknown_sample_levels": unk_levels},
}, open(os.path.join(OUT, "screen.json"), "w"), indent=1)
open(os.path.join(OUT, "strings.txt"), "w").write("\n".join(DRAWN) + "\n")

# --------------------------------------------------------------- report
print("=== FILES ===")
for p in (png, svg, os.path.join(OUT, "screen.json"), os.path.join(OUT, "strings.txt")):
    print("%-28s %8d bytes  sha256=%s" % (os.path.basename(p), os.path.getsize(p),
          hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]))
print("PNG pixels %dx%d at %d dpi" % (W, H, DPI))
print("=== DATA MEASURED AT RENDER TIME ===")
print("panel1 %s key=e_z_node raw=%s dtype=%s -> grid %s (nx=%d, nz=%d) max|e_z|=%.12g"
      % (F1, EZ_RAW, EZ_DTYPE, EZ_SHAPE, NX, NZ, LIM))
print("panel2 %s bytes=%d keys=%d sp_keys=%d zero_length=%d nonempty=%s plane_Ez=%s"
      % (F2, F2_BYTES, len(HDR), len(SP_KEYS), NZERO, NONEMPTY, PLANE_EZ))
for k in SP_KEYS:
    print("   %-16s %-10s %s" % (k, SP[k][0], SP[k][1]))
print("=== FIXED SENTENCES VERBATIM vs acceptance.md ===")
print("ceiling sentence, verbatim vs acceptance.md (whitespace-normalised):", S1 in acc)
print("not-citable sentence, verbatim vs acceptance.md (whitespace-normalised):", S2 in acc)
print("same as a raw byte substring (md wraps the line, so False here is expected):",
      S1 in acc_raw, S2 in acc_raw)
print("=== GREYSCALE AUDIT ===")
print("unique RGB colours %d -> unique grey levels %d (full) / %d (50%% LANCZOS)"
      % (n_rgb, n_grey_full, n_grey_half))
print("E5 badge    : dark-pixel fraction %.4f, distinct grey levels %d" % (e5_dark, e5_levels))
print("E1 sample   : dark-pixel fraction %.4f, distinct grey levels %d" % (e1_dark, e1_levels))
print("UNKNOWN smpl: dark-pixel fraction %.4f, distinct grey levels %d" % (unk_dark, unk_levels))
print("E5 vs E1 dark-pixel ratio: %.1fx  (a struck, double-framed, hatched box vs a plain one)"
      % (e5_dark / max(e1_dark, 1e-9)))
print("=== STRINGS DRAWN (%d) ===" % len(DRAWN))
for i, s in enumerate(DRAWN, 1):
    print("[%02d] %s" % (i, s.replace("\n", " \\n ")))
