#!/usr/bin/env python3
"""60V Phase A -- the 59V screen, rebuilt so that NOTHING is loaded from .scratch/.

Two panels, two artefacts, zero committed arrays.
  panel 1  mixed-mode e_z_node        -> UNCOMMITTED-WITHHELD (no field image is drawn)
  panel 2  the S-parameter refusal    -> E5, provenance quoted from committed text

Criterion B2: `.scratch/` is treated as absent. This script never opens, stats or
lists anything under it. The only `.scratch` strings in this file are PROVENANCE
LABELS drawn on the figure (allowed by B4: "the source path is named").
Criterion B4: panel 1's field image is not rendered; the panel is a withheld card.
Criterion B3: each panel prints artefact path, pointer, type/shape and a status tag.
Criterion B5: each panel carries a badge; panel 1's badge is itself withheld (B4).

Frozen spec: viz/acceptance.md (59V criteria A*, 60V criteria B*). Fence: writes
only inside viz/.   Run:  PYTHONDONTWRITEBYTECODE=1 python3 viz/d59v_screen.py
"""
from __future__ import annotations

import hashlib
import json
import os
import textwrap

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from PIL import Image

ROOT = "/workspace"
HERE = os.path.join(ROOT, "viz")
OUT = os.path.join(HERE, "out")
ACC_MD = os.path.join(HERE, "acceptance.md")          # committed text artefact (read only)
SOUND_MD = os.path.join(ROOT, "docs", "design", "soundness.md")   # committed ledger (read only)

# ---- provenance LABELS. These are strings drawn on the figure; none is a load path.
P1_SRC = ".scratch/s10118_mixed_mode.npz"
P1_KEY = "e_z_node"
P2_SRC = ".scratch/host/m3a-smoke/plane_record.npz"
P1_PTR = "viz/acceptance.md :: \u00a74 row 1"
P2_PTR = "viz/acceptance.md :: \u00a74 row 8"
TIER_PTR = "docs/design/soundness.md :: row C4"

WITHHELD = "rendered from uncommitted data - not reproducible, badge withheld"
P1_REASON = ("reason: no committed array artefact exists anywhere in the tree at HEAD 1cbe2fc. "
             "There are ZERO committed .npz files in this repository; the only field arrays are "
             "gitignored under .scratch/. A screen drawn from one would not be reproducible from "
             "the repository, so the field image, its colourbar and every number derived from it are withheld.")

DPI, FIGW, FIGH = 130, 16.0, 9.0
os.makedirs(OUT, exist_ok=True)

# ---- B10 tier tones -------------------------------------------------------------------
# ONE source of truth: the hexes below. Every luminance/ratio is computed FROM these hexes.
TIER_FILL = {"E1": "#FDFDFD", "WITHHELD": "#898989", "E5": "#272727"}
TIER_INK = {"E1": "#111111", "WITHHELD": "#FFFFFF", "E5": "#F5F5F5"}


def srgb_lin(v):
    c = v / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def wcag_L(hexstr):
    """WCAG 2.x relative luminance, computed from the hex."""
    h = hexstr.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * srgb_lin(r) + 0.7152 * srgb_lin(g) + 0.0722 * srgb_lin(b)


def wcag_ratio(la, lb):
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


L_TIER = {k: wcag_L(v) for k, v in TIER_FILL.items()}
RAT_TIERS = {"e1_vs_e5": wcag_ratio(L_TIER["E1"], L_TIER["E5"]),
             "e1_vs_withheld": wcag_ratio(L_TIER["E1"], L_TIER["WITHHELD"]),
             "e5_vs_withheld": wcag_ratio(L_TIER["E5"], L_TIER["WITHHELD"])}
RAT_GATE = min(RAT_TIERS.values()) >= 3.0
print("=== B10 WCAG TONES (computed from hex) ===")
for _k in ("E1", "WITHHELD", "E5"):
    print("  %-9s fill %s -> L %.4f   ink %s -> L %.4f  (ink ratio %.2f)"
          % (_k, TIER_FILL[_k], L_TIER[_k], TIER_INK[_k], wcag_L(TIER_INK[_k]),
             wcag_ratio(L_TIER[_k], wcag_L(TIER_INK[_k]))))
for _k, _v in RAT_TIERS.items():
    print("  ratio %-16s %.2f  %s" % (_k, _v, "PASS" if _v >= 3.0 else "FAIL"))
print("  B10 all tier pairs >= 3.0:", RAT_GATE)
if not RAT_GATE:
    raise SystemExit("FATAL: B10 tier fills fail the 3.0 WCAG ratio: %s -> %s" % (L_TIER, RAT_TIERS))

DRAWN = []


def rec(s):
    DRAWN.append(s)
    return s


def fill(s, width=96):
    return rec(textwrap.fill(" ".join(str(s).split()), width=width))


# ------------------------------------------------------------- committed sources
acc_raw = open(ACC_MD, encoding="utf-8").read()
acc = " ".join(acc_raw.split())          # markdown line-wraps are not part of the sentence
sound_raw = open(SOUND_MD, encoding="utf-8").read()
sound = " ".join(sound_raw.split())

Q_P1 = "`e_z_node` (527,) -> (31,17) on `xs`(31),`zs`(17)"
Q_EMPTY = "present but empty"
Q_SHAPES = "`f` (0,), `v` (0,9), `i` (0,9)"
Q_TRUNC = "`s11_*`/`s21*`/`passivity*` (0,)"
Q_PLANE = "`plane_Ez` (9,201,76)"
CHK = {
    "p1_shape_quote_in_acceptance_md": Q_P1 in acc,
    "p2_empty_quote_in_acceptance_md": Q_EMPTY in acc,
    "p2_shape_quote_in_acceptance_md": Q_SHAPES in acc,
    "p2_trunc_quote_in_acceptance_md": Q_TRUNC in acc,
    "p2_plane_ez_quote_in_acceptance_md": Q_PLANE in acc,
    "c4_row_in_soundness_md": "claim C4: the S-parameters are quotable" in sound,
    "c4_scope_in_soundness_md": "nothing about quotability is measured" in sound,
    "t4_amp_44_09_in_soundness_md": "44.09" in sound,
    "t2_agree_9_03_in_soundness_md": "9.03" in sound,
}
if not all(CHK.values()):
    raise SystemExit("FATAL: committed-source quote check failed: %s" % {k: v for k, v in CHK.items() if not v})

S1 = "A tier is a ceiling: it can be lowered by new evidence, not raised by emphasis. E5 is assertion, not measurement; it must not be quoted."
S2 = "This panel contains values that are not citable."
FIXED_CHECK = {"ceiling": S1 in acc, "not_citable": S2 in acc}

# ------------------------------------------------------------------- the figure
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.0,
    "svg.hashsalt": "d60v",
    "figure.dpi": DPI,
    "savefig.dpi": DPI,
})
fig = plt.figure(figsize=(FIGW, FIGH), dpi=DPI)

fig.text(0.5, 0.982, rec("60V \u2014 committed artefacts only: one field withheld, one number refused"),
         ha="center", va="top", fontsize=15, weight="bold")
fig.text(0.5, 0.947,
         fill("Two panels, two artefacts, zero committed arrays. Nothing under .scratch/ was opened by this build: "
              "criterion B2 treats it as absent. Panel 1 therefore renders a withheld card instead of a field image "
              "(B4); panel 2 quotes committed text for its shapes and refusal (B3/B6). Badge encoding: viz/acceptance.md "
              "\u00a73.1. Status tags are drawn from {COMMITTED, UNCOMMITTED-WITHHELD} and appear on every panel (B3).", 150),
         ha="center", va="top", fontsize=8.2)

# ------------------------------------------------------------------- panel 1
fig.text(0.040, 0.884, rec("PANEL 1 \u00b7 A FIELD THAT IS NOT RENDERED \u2014 mixed-mode e_z, withheld"),
         fontsize=11, weight="bold", va="bottom")

AX1 = [0.050, 0.400, 0.335, 0.450]
ax1 = fig.add_axes(AX1)
ax1.set_xlim(0, 1)
ax1.set_ylim(0, 1)
ax1.set_axis_off()
ax1.add_patch(Rectangle((0, 0), 1, 1, facecolor="0.90", edgecolor="black", linewidth=1.0, zorder=1))
ax1.add_patch(Rectangle((0.02, 0.02), 0.96, 0.96, facecolor="none", edgecolor="0.35",
                        linestyle=":", linewidth=1.2, zorder=2))
# D1/B4: the withholding literal is drawn as ONE unbroken line -- no wrap, no placeholder.
ax1.text(0.5, 0.80, rec(WITHHELD), ha="center", va="center", fontsize=7.8, weight="bold", zorder=3)
ax1.text(0.5, 0.66, rec("source path (not loaded): " + P1_SRC + " :: " + P1_KEY),
         ha="center", va="center", fontsize=7.4, fontfamily="DejaVu Sans Mono", zorder=3)
ax1.text(0.5, 0.555, fill(P1_REASON, 62), ha="center", va="top", fontsize=6.9, zorder=3)
# plot area marker: the frame the field WOULD have occupied, empty
ax1.add_patch(Rectangle((0.13, 0.115), 0.74, 0.30, facecolor="none", edgecolor="0.55",
                        linestyle="--", linewidth=1.0, zorder=2))
ax1.text(0.5, 0.265, rec("field image withheld \u2014 this frame is deliberately empty"),
         ha="center", va="center", fontsize=7.2, style="italic", color="0.30", zorder=3)
# B5 badge, itself withheld (B4): UNKNOWN line style, hatched field, '?' box
_tag_i0 = len(ax1.texts)
ax1.add_patch(Rectangle((0.02, 0.025), 0.96, 0.070, facecolor=TIER_FILL["WITHHELD"], edgecolor="black",
                        linestyle=":", linewidth=1.2, fill=True, zorder=3))
ax1.add_patch(Rectangle((0.02, 0.025), 0.96, 0.070, facecolor="none", edgecolor=TIER_INK["WITHHELD"],
                        linestyle="none", linewidth=0.0, hatch="//", fill=True, zorder=3))
ax1.text(0.045, 0.060, rec("UNCOMMITTED-WITHHELD \u00b7 badge withheld"),
         fontsize=8.4, weight="bold", va="center", zorder=4)
ax1.text(0.965, 0.060, rec("?"), fontsize=9.0, va="center", ha="center", zorder=4,
         bbox=dict(boxstyle="square,pad=0.08", facecolor="white", edgecolor="black", linewidth=0.8))
ax1.texts[_tag_i0].set_color(TIER_INK["WITHHELD"])   # tag label sits on the mid-grey fill

cap1 = [
    fill("PROVENANCE \u00b7 artefact path: %s \u00b7 pointer: %s (committed; type/shape only) \u00b7 "
         "key: %s \u00b7 type/shape: float64 (527,) as stored, documented as (527,) -> (31,17) on xs(31), zs(17) "
         "\u00b7 status: UNCOMMITTED-WITHHELD." % (P1_SRC, P1_PTR, P1_KEY), 92),
    fill("TIER \u00b7 the profile has no row in docs/design/soundness.md naming it, so its tier is UNKNOWN "
         "(acceptance.md \u00a74, row 1). Under B4 the badge is withheld rather than drawn as a tier: a tier on an "
         "unreproducible image would assert more than the repository supports.", 92),
    fill("WHAT WOULD UNBLOCK IT \u00b7 one committed array artefact holding e_z_node (527,) together with its xs(31) and "
         "zs(17) axes, at a path tracked in the repository rather than gitignored. Nothing else is required: the "
         "reshape, the diverging linear colour map and the \u00b1max|e_z_node| limits are already declared in the 59V spec.",
         92),
]
fig.text(0.040, 0.382, "\n".join(cap1), fontsize=6.9, va="top", linespacing=1.42)

# ------------------------------------------------------------------- panel 2
fig.text(0.470, 0.884, rec("PANEL 2 \u00b7 A NUMBER YOU MAY NOT \u2014 the S-parameter refusal"),
         fontsize=11, weight="bold", va="bottom")
ax2 = fig.add_axes([0.470, 0.372, 0.520, 0.478])
ax2.set_xlim(0, 1)
ax2.set_ylim(0, 1)
ax2.set_axis_off()
y = 0.988


def line(txt, dv=0.049, fs=7.6, mono=False, weight="normal", color="black"):
    global y
    ax2.text(0.006, y, rec(txt), fontsize=fs, va="top", ha="left", weight=weight, color=color,
             fontfamily="DejaVu Sans Mono" if mono else "DejaVu Sans")
    y -= dv
    return txt


line("PROVENANCE \u00b7 artefact path: %s \u00b7 pointer: %s \u00b7 key set: 12 S-parameter keys \u00b7 "
     "type/shape: npz, all zero-length (shapes below) \u00b7 status: UNCOMMITTED-WITHHELD." % (P2_SRC, P2_PTR),
     dv=0.044, fs=7.0)
line("Sought: a quotable complex s11 or s21 \u2014 a number with a true error bar \u2014 for the nine station planes this same file records.",
     dv=0.042)
line("Found, quoted from the committed source and NOT read this run: 12 S-parameter-related keys, all present, all "
     "carrying ZERO samples. Nothing was substituted for them: no zero, no placeholder curve, no reconstruction, no "
     "simulated line. The npz itself was never opened (B2: .scratch/ is treated as absent).", dv=0.058)
line("  %-18s %-9s %s" % ("key", "shape", "reading"), dv=0.030, fs=6.5, mono=True, weight="bold")
P2_ROWS = [
    ("f", "(0,)", "no frequency axis"),
    ("v", "(0,9)", "no wave amplitudes at the stations"),
    ("i", "(0,9)", "no currents at the stations"),
    ("z0", "not stated", "no reference impedance"),
    ("beta", "not stated", "no propagation constant"),
    ("s11_measured", "(0,) via `s11_*`", "no measured reflection"),
    ("s11_port", "(0,) via `s11_*`", "no port-plane reflection"),
    ("s21", "(0,) via `s21*`", "no transmission"),
    ("s21_power", "(0,) via `s21*`", "no power-wave transmission"),
    ("passivity", "(0,) via `passivity*`", "no passivity check"),
    ("passivity_power", "(0,) via `passivity*`", "no power-wave passivity check"),
    ("refused", "not stated", "no refusal flags"),
]
for k, shp, rd in P2_ROWS:
    line("  %-18s %-19s %s" % (k, shp, rd), dv=0.0245, fs=6.4, mono=True)
y -= 0.010
line("For contrast, in the same file plane_Ez is stored as complex128 (9,201,76) per the committed \u00a74 row 6 \u2014 the "
     "field planes are real. The field is present; the S-parameter is absent. That asymmetry is this panel.", dv=0.040)

# ---- E5 badge: double rule + 45 deg hatch + value struck through
_e5_i0 = len(ax2.texts)
bx0, by0, bw, bh = 0.006, 0.010, 0.988, 0.300
ax2.add_patch(Rectangle((bx0, by0), bw, bh, facecolor=TIER_FILL["E5"], edgecolor="black",
                        linewidth=1.0, zorder=1))
ax2.add_patch(Rectangle((bx0, by0), bw, bh, facecolor="none", edgecolor=TIER_INK["E5"],
                        linestyle="none", linewidth=0.0, hatch="////", fill=True, zorder=1.5))
ax2.add_patch(Rectangle((bx0 - 0.008, by0 - 0.013), bw + 0.016, bh + 0.026, facecolor="none",
                        edgecolor="black", linewidth=1.0, zorder=2))
by = by0 + bh - 0.042
ax2.text(bx0 + 0.012, by, rec("E5 \u2014 NOT CITABLE"), fontsize=15, weight="bold", color="#8b0000",
         va="top", zorder=3)
ty = by - 0.078
ax2.text(bx0 + 0.012, ty, rec("s21"), fontsize=13, style="italic", va="top", zorder=3)
ax2.add_line(Line2D([bx0 + 0.010, bx0 + 0.052], [ty - 0.012, ty - 0.012], color="black", linewidth=2.2, zorder=4))
ax2.text(bx0 + 0.060, ty, rec("struck through: the value this figure is not allowed to show"),
         fontsize=8.4, va="top", zorder=3)
by2 = ty - 0.055
ax2.text(bx0 + 0.012, by2, rec("%s: 'claim C4: the S-parameters are quotable' \u2014 tier E5, scope 'none: "
                               "nothing about quotability is measured'." % TIER_PTR),
         fontsize=7.4, va="top", zorder=3)
ax2.text(bx0 + 0.012, by2 - 0.045,
         rec("Recorded against it: D09, F14, G04, G06 \u2014 each a recorded FAIL; T4_amp stands FAIL at 44.09 %, "
             "T2_agree at 9.03x tol."), fontsize=7.4, va="top", zorder=3)
ax2.text(bx0 + 0.012, by2 - 0.090,
         rec("NONE ON DISK \u2014 this box carries no value because the file carries none."),
         fontsize=7.4, va="top", weight="bold", zorder=3)
for _t in ax2.texts[_e5_i0:]:      # B10: every text inside the E5 badge takes its light ink
    _t.set_color(TIER_INK["E5"])
for _l in ax2.lines:               # the strike-through follows the ink, not black
    _l.set_color(TIER_INK["E5"])

# ---------------------------------------------------------- fixed sentences
fig.text(0.040, 0.223, rec(S1), fontsize=7.8, va="top", style="italic")
fig.text(0.470, 0.223, rec(S2), fontsize=7.8, va="top", style="italic", weight="bold")

# ------------------------------------------------------------- badge legend
axL = fig.add_axes([0.040, 0.030, 0.925, 0.150])
axL.set_xlim(0, 1)
axL.set_ylim(0, 1)
axL.set_axis_off()
axL.text(0.000, 1.02, fill("Badge legend \u2014 the three styles below are STYLE SAMPLES ONLY. No quantity on this figure is E1; the E1 "
                           "sample is drawn so the withdrawn/UNKNOWN style can be compared against a citable style in greyscale "
                           "(acceptance.md A7).", 150),
         fontsize=7.0, va="bottom")


def sample(x0, w, tier_text, caption, hatch=None, ls="-", lw=1.5, double=False,
           grey=None, qmark=False, strike_on=None):
    # B10: the tone comes from the one tone table, keyed by the tier label itself.
    key = "E1" if tier_text.startswith("E1") else ("E5" if tier_text.startswith("E5") else "WITHHELD")
    face, ink = TIER_FILL[key], TIER_INK[key]
    h = 0.44
    axL.add_patch(Rectangle((x0, 0.36), w, h, facecolor=face,
                            edgecolor="black", linestyle=ls, linewidth=lw, fill=True, zorder=1))
    if hatch:   # light-on-dark: mpl takes the hatch colour from edgecolor, hence the overlay
        axL.add_patch(Rectangle((x0, 0.36), w, h, facecolor="none", edgecolor=ink,
                                linestyle="none", linewidth=0.0, hatch=hatch, fill=True, zorder=2))
    if double:
        axL.add_patch(Rectangle((x0 - 0.004, 0.335), w + 0.008, h + 0.05, facecolor="none",
                                edgecolor="black", linewidth=1.0, zorder=2))
    axL.text(x0 + 0.008, 0.60, rec(tier_text), fontsize=7.6, weight="bold", va="center", zorder=3,
             color=ink)
    if qmark:
        axL.text(x0 + w - 0.030, 0.60, rec("?"), fontsize=10, va="center", ha="center", zorder=3,
                 bbox=dict(boxstyle="square,pad=0.12", facecolor="white", edgecolor="black", linewidth=0.8))
    if strike_on:
        axL.text(x0 + w - 0.075, 0.60, rec(strike_on), fontsize=8.5, style="italic", va="center", zorder=3,
                 color=ink)
        axL.add_line(Line2D([x0 + w - 0.082, x0 + w - 0.030], [0.60, 0.60], color=ink, linewidth=2.0,
                            zorder=4))
    axL.text(x0 + 0.008, 0.22, fill(caption, 46), fontsize=6.3, va="top")


sample(0.000, 0.300, "E1 PROVEN",
       "single solid 1.5 pt rule, plain field, value unstruck \u2014 style sample only.", lw=1.5)
sample(0.340, 0.300, "E5  NOT CITABLE",
       "double rule + 45\u00b0 hatch + value struck through \u2014 this is panel 2's badge.",
       hatch="////", lw=1.0, double=True, strike_on="s21")
sample(0.680, 0.300, "UNCOMMITTED-WITHHELD",
       "dotted rule + 50 % grey hatched field + boxed '?' \u2014 this is panel 1's status tag; its tier badge is withheld (B4).",
       ls=":", lw=1.2, grey="0.83", qmark=True, hatch="//")

# --------------------------------------------------------------- save, deterministic
for _a in fig.axes:
    if not _a.axison:
        continue
    for _t in list(_a.get_xticklabels()) + list(_a.get_yticklabels()):
        if _t.get_text() and _t.get_visible():
            rec(_t.get_text())
    if _a.get_xlabel():
        rec(_a.get_xlabel())
    if _a.get_ylabel():
        rec(_a.get_ylabel())

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


def region(x0, y0, x1, y1):
    c = L[int((1 - y1) * H):int((1 - y0) * H), int(x0 * W):int(x1 * W)]
    return float((c < 96).mean()), float(c.mean()), int(np.unique(c).size)


def fx(ax, fx0, fx1):
    return ax[0] + ax[2] * fx0, ax[0] + ax[2] * fx1


def fy(ax, fy0, fy1):
    return ax[1] + ax[3] * fy0, ax[1] + ax[3] * fy1


p1_field = region(fx(AX1, 0.13, 0.87)[0], fy(AX1, 0.115, 0.415)[0], fx(AX1, 0.13, 0.87)[1], fy(AX1, 0.115, 0.415)[1])
p1_badge = region(fx(AX1, 0.02, 0.98)[0], fy(AX1, 0.025, 0.095)[0], fx(AX1, 0.02, 0.98)[1], fy(AX1, 0.025, 0.095)[1])
e5 = region(0.470 + 0.006 * 0.520, 0.372 + 0.012 * 0.478, 0.470 + 0.988 * 0.520, 0.372 + 0.300 * 0.478)
e1 = region(0.040, 0.030 + 0.36 * 0.150, 0.040 + 0.300 * 0.925, 0.030 + 0.80 * 0.150)
unk = region(0.040 + 0.680 * 0.925, 0.030 + 0.36 * 0.150, 0.040 + 0.980 * 0.925, 0.030 + 0.80 * 0.150)


# B10 is a property of the TONE TABLE, not of mean pixel grey: the ratios were computed
# from the hexes above (RAT_TIERS) and gated there. The region means below stay as a
# cross-check that the rendered fills are the tones that were declared.
RAT = RAT_TIERS
RENDERED_MEANS = {"e1": round(e1[1], 1), "e5": round(e5[1], 1),
                  "withheld": round(unk[1], 1), "withheld_field": round(p1_field[1], 1)}

# --------------------------------------------------------------- sidecars
json.dump({
    "figure": {"png": "viz/out/screen.png", "svg": "viz/out/screen.svg",
               "pixels": [W, H], "dpi": DPI, "static_only": True, "javascript": False},
    "panels": [
        {"panel": 1, "rendered": "withheld card (no field image)",
         "artefact_path_label": P1_SRC + " :: " + P1_KEY,
         "pointer": P1_PTR, "pointer_verified": CHK["p1_shape_quote_in_acceptance_md"],
         "keys": [P1_KEY, "xs", "zs"], "type_shape": "float64 (527,) as stored; documented (527,) -> (31,17) on xs(31), zs(17)",
         "status_tag": "UNCOMMITTED-WITHHELD", "tier": "WITHHELD", "tier_note": "UNKNOWN per acceptance.md \u00a74 row 1; badge withheld under B4",
         "withheld_text": WITHHELD, "reason": P1_REASON,
         "display_transforms": [], "derived_labels": []},
        {"panel": 2, "rendered": "refusal table + E5 badge",
         "artefact_path_label": P2_SRC, "pointer": P2_PTR,
         "pointer_verified": all((CHK["p2_empty_quote_in_acceptance_md"], CHK["p2_shape_quote_in_acceptance_md"],
                                 CHK["p2_trunc_quote_in_acceptance_md"])),
         "keys": [r[0] for r in P2_ROWS],
         "type_shape": {r[0]: r[1] for r in P2_ROWS}, "zero_length_keys": 12, "arrays_read": False,
         "status_tag": "UNCOMMITTED-WITHHELD", "tier": "E5", "tier_source": TIER_PTR,
         "tier_source_verified": all((CHK["c4_row_in_soundness_md"], CHK["c4_scope_in_soundness_md"])),
         "display_transforms": ["none: no array values were read by this build"], "derived_labels": []},
    ],
    "committed_source_checks": CHK,
    "fixed_sentences": {"ceiling": S1, "not_citable": S2},
    "fixed_sentences_verbatim_in_acceptance_md": FIXED_CHECK,
    "greyscale": {"rgb_unique": n_rgb, "L_unique_full": n_grey_full, "L_unique_half": n_grey_half,
                  "p1_withheld_field": {"dark_frac": p1_field[0], "mean_grey": p1_field[1], "levels": p1_field[2]},
                  "p1_status_badge": {"dark_frac": p1_badge[0], "mean_grey": p1_badge[1], "levels": p1_badge[2]},
                  "e5_badge": {"dark_frac": e5[0], "mean_grey": e5[1], "levels": e5[2]},
                  "e1_sample": {"dark_frac": e1[0], "mean_grey": e1[1], "levels": e1[2]},
                  "withheld_sample": {"dark_frac": unk[0], "mean_grey": unk[1], "levels": unk[2]},
                  "tier_fills": TIER_FILL, "tier_ink": TIER_INK,
                  "tier_wcag_L": {k: round(v, 4) for k, v in L_TIER.items()},
                  "tier_contrast_ratios_wcag": {k: round(v, 3) for k, v in RAT_TIERS.items()},
                  "wcag_min_over_3_1": RAT_GATE, "rendered_means": RENDERED_MEANS},
}, open(os.path.join(OUT, "screen.json"), "w"), indent=1)
open(os.path.join(OUT, "strings.txt"), "w").write("\n".join(DRAWN) + "\n")

# --------------------------------------------------------------- report
print("=== FILES ===")
for p in (png, svg, os.path.join(OUT, "screen.json"), os.path.join(OUT, "strings.txt")):
    print("%-28s %8d bytes  sha256=%s" % (os.path.basename(p), os.path.getsize(p),
          hashlib.sha256(open(p, "rb").read()).hexdigest()))
print("PNG pixels %dx%d at %d dpi" % (W, H, DPI))
print("=== COMMITTED-SOURCE QUOTE CHECKS ===")
for k, v in CHK.items():
    print("  %-40s %s" % (k, v))
print("=== WITHHELD WORDING: ONE UNBROKEN LINE ===")
_lit_lines = [i for i, _l in enumerate(open(os.path.join(OUT, "strings.txt")).read().split("\n"), 1)
              if _l == WITHHELD]
_lit_drawn = [s for s in DRAWN if WITHHELD in s]
LIT_OK = (len(_lit_lines) == 1) and (len(_lit_drawn) == 1) and ("\n" not in _lit_drawn[0])
print("  strings.txt lines EQUAL to the literal (must be exactly 1):", _lit_lines)
print("  drawn unbroken, no newline inside the drawn string:", LIT_OK)
print("  LITERAL-LINE: %s" % WITHHELD)
print("=== GREYSCALE AUDIT ===")
print("unique RGB colours %d -> unique grey levels %d (full) / %d (50%% LANCZOS)" % (n_rgb, n_grey_full, n_grey_half))
print("panel1 withheld field : dark %.4f mean %.1f levels %d" % p1_field)
print("panel1 status badge   : dark %.4f mean %.1f levels %d" % p1_badge)
print("panel2 E5 badge       : dark %.4f mean %.1f levels %d" % e5)
print("legend E1 sample      : dark %.4f mean %.1f levels %d" % e1)
print("legend withheld sample: dark %.4f mean %.1f levels %d" % unk)
print("tier WCAG ratios %s -> %s  B10 min >= 3.0: %s"
      % (" ".join("%s L=%.4f" % (k, v) for k, v in L_TIER.items()),
         {k: round(v, 2) for k, v in RAT_TIERS.items()}, RAT_GATE))
print("rendered means (cross-check) %s" % RENDERED_MEANS)
print("=== STRINGS DRAWN (%d) ===" % len(DRAWN))
for i, s in enumerate(DRAWN, 1):
    print("[%02d] %s" % (i, s.replace("\n", " \\n ")))

if not (LIT_OK and RAT_GATE):
    raise SystemExit("FATAL: B10 gate %s / D1 one-line literal %s" % (RAT_GATE, LIT_OK))
print("GATES: B10 %s  D1 %s -> %s" % (RAT_GATE, LIT_OK, "ALL PASS" if (LIT_OK and RAT_GATE) else "FAIL"))
