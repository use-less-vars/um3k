#!/usr/bin/env python3
"""make_before_after_figs.py -- the D24-T6 legibility split of the C2b picture.

WHY THIS FILE EXISTS
--------------------
tools/host/mode_plot/mode_plot.py draws ONE figure, ``figsize=(13.4, 11.2)``
(mode_plot.py:708), six rows by two runs, with panel titles at 6.1 pt, ticks at
6 pt, axis labels at 7 pt and a hand-wrapped caption at 5.8 pt
(mode_plot.py:642-643, :736-759).  docs/report/sec_modes.tex includes that PNG
at ``0.95\\textwidth``.  The report's text block is 455.24411 pt = 6.29922 in
(a4paper, margin=2.5cm -- ``.scratch/build/main.log:760``), so 0.95\\textwidth =
5.98426 in and the LaTeX scale factor is 5.98426/13.4 = 0.4466: a 6.1 pt title
printed at 2.7 pt.  That is the defect this script fixes.

THE FIX, IN ONE LINE OF ARITHMETIC
----------------------------------
Set the matplotlib figure width EQUAL to the printed width, so the scale factor
is 1.0 and every fontsize below is its true printed size::

    FIG_W = 0.95 * \\textwidth = 0.95 * 6.29922 in = 5.98426 in

The 13.4 in picture is then split into two figures, each three rows by two runs,
so each panel is ~2.5 in wide instead of ~2.1 in *and* is printed at 1:1 instead
of at 45%.  Fonts are set explicitly in RCPARAMS below (never inherited); the
smallest text element is 9 pt and prints at 9 pt.

DATA / PROVENANCE -- NOTHING IS SOLVED HERE
-------------------------------------------
* Analytic planes: banked, ``A_ez`` (201, 76) and ``A_ey`` (200, 77), in
  tools/host/c1-audit/out/c1_spectrum.npz (PMC) and .../pecbox_spectrum.npz
  (PEC); written by np.savez in tools/host/c1-audit/c1_audit.py:600-625
  (A_ez/A_ey at c1_audit.py:420-423), the second path redirected by
  tools/host/c1-audit/pecbox_variant.py:291-326.
* Extracted planes are NOT banked as planes (the npz carries the eigenvector
  column ``vecs_real[:, col]``, not the interpolated field).  They are rebuilt
  by importing ``mode_plot.reconstruct_run`` -- the SAME arithmetic the audit
  used (c1_audit.py:386-493: one mixed-block assembly, one sparse LU of the
  (n_free_n x n_free_n) system block, one Whitney ``e_at`` evaluation), which
  self-checks that all three banked correlations are reproduced to 1e-6.  No
  eigensolve, no gate, no emfit run, no new physics: the spectrum is re-read.
* Runs plotted: the two 31x17 runs the audit banks and the report already
  discusses --
      PMC / open top    c1_spectrum.npz      QZ col 738
      PEC / closed box  pecbox_spectrum.npz  QZ col 699
  The 41x22 run (.scratch/s10118_mode_41x22.npz) is NOT plotted: it banks
  ``e_t``, ``e_z_node``, ``z_free`` and its axes, but NO ``A_ez``/``A_ey``
  analytic plane and no corr array, so its panels cannot be drawn from banked
  data without regenerating the basis (out of scope, and forbidden here).

THE TWO FIGURES
---------------
fig_ez_before_after.{pdf,png}   the e_z story
    row 1  BEFORE  the superseded, mis-paired extraction: the analytic VERTICAL
           reference against the extracted LONGITUDINAL field
           (``corr_ez_superseded_longitudinal``).  Banked: +0.119160432391342
           (PMC) / +0.147291446944630 (PEC).
    row 2  AFTER   the correct pairing: vertical against VERTICAL
           (``corr_ez_vv``).  Banked: +0.935286730348765 / +0.936929717079781.
    row 3  DIFFERENCE  after minus before, same run, same lattice.
fig_ey_before_after.{pdf,png}   the e_y story
    row 1  REFERENCE  analytic e_y (width)
    row 2  EXTRACTED  e_y (width), ``corr_ey`` = +0.920770784811142 (PMC) /
           +0.912343044811209 (PEC) -- the metric that never changed.
    row 3  DIFFERENCE  reference minus extracted.

Both figures: each field divided by its own RMS (dimensionless, sign fixed by
the banked correlation's sign -- mode_plot.py:537-552), shared colour limits
within a row across the two runs, ``imshow`` extent in mm, dashed line at the
substrate interface, thick line at the strip (mode_plot.py:_overlay).  Contour
labels are deliberately NOT drawn: mode_plot.py prints them at 4.5 pt
(mode_plot.py:641) and nothing on these figures may print below 9 pt.

USAGE
    python3 tools/host/mode_plot/make_before_after_figs.py
"""

import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                       # mode_plot.py lives beside us
sys.path.insert(0, os.path.dirname(HERE))      # tools/host: _bootstrap.py
import mode_plot as mp                        # noqa: E402  (path set above)

# ---------------------------------------------------------------------------
# sizing: the printed width IS the figure width, so the scale factor is 1.0
# ---------------------------------------------------------------------------
TEXTWIDTH_PT = 455.24411                      # .scratch/build/main.log:760
PT_PER_IN = 72.27
TEXTWIDTH_IN = TEXTWIDTH_PT / PT_PER_IN       # 6.299215 in
FIG_W = 0.95 * TEXTWIDTH_IN                   # 5.984254 in  <- figsize width
FIG_H = 6.00                                  # <= 8.5 in, page + caption

#: every text element, set explicitly -- nothing is inherited
RCPARAMS = {
    "font.size": 9.5,
    "axes.labelsize": 10.0,
    "axes.titlesize": 9.5,
    "xtick.labelsize": 9.0,
    "ytick.labelsize": 9.0,
    "legend.fontsize": 9.0,
    "figure.titlesize": 10.0,
    "mathtext.fontset": "dejavusans",         # mathtext, never usetex
    "figure.dpi": 100,
    "savefig.bbox": None,                     # keep the declared inches exact
    "pdf.fonttype": 42,                       # TrueType, not Type 3: the text
    "ps.fonttype": 42,                        # stays extractable/measurable
}
plt.rcParams.update(RCPARAMS)

FS_TITLE = RCPARAMS["axes.titlesize"]
FS_AXLAB = RCPARAMS["axes.labelsize"]
FS_TICK = RCPARAMS["xtick.labelsize"]
FS_HEAD = RCPARAMS["figure.titlesize"]
FS_NOTE = 9.0                                 # footnote; still >= 9 pt

OUT_DIR = os.path.join(mp.REPO, "docs", "figures")   # what \\includegraphics
                                                     # ../figures/ resolves to
                                                     # from docs/report
CMAP = "RdBu_r"


def rms(f):
    f = np.asarray(f, dtype=float)
    return float(np.sqrt(np.mean(f * f)))


def rel_rms(d, a, b):
    return rms(d) / np.sqrt(0.5 * (rms(a) ** 2 + rms(b) ** 2))


def overlay(ax, geo):
    h = float(geo["h"]) * 1e3
    y0 = (float(geo["width"]) - float(geo["w"])) / 2 * 1e3
    y1 = y0 + float(geo["w"]) * 1e3
    ax.axhline(h, color="k", lw=0.6, ls=(0, (4, 3)), zorder=4)
    ax.plot([y0, y1], [h, h], color="k", lw=2.0, solid_capstyle="butt", zorder=5)
    for ye in (y0, y1):
        ax.axvline(ye, color="0.35", lw=0.5, ls=(0, (1, 2)), zorder=4)


def panel(ax, f, yc, zc, ext, title, vmax, show_x, show_y):
    ax.imshow(f.T, origin="lower", extent=ext, cmap=CMAP, vmin=-vmax, vmax=+vmax,
              interpolation="nearest", aspect="equal", zorder=1)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_title(title, fontsize=FS_TITLE, linespacing=1.35, pad=3.0)
    ax.tick_params(labelsize=FS_TICK)
    ax.tick_params(labelbottom=show_x, labelleft=show_y)
    if show_x:
        ax.set_xlabel("y  [mm]", fontsize=FS_AXLAB)
    if show_y:
        ax.set_ylabel("z  [mm]", fontsize=FS_AXLAB)


def finish(fig, out_stem, head, note):
    fig.text(0.5, 0.985, head, fontsize=FS_HEAD, ha="center", va="top")
    fig.text(0.5, 0.022, note, fontsize=FS_NOTE, ha="center", va="bottom",
             color="0.25", linespacing=1.3)
    pdf = os.path.join(OUT_DIR, out_stem + ".pdf")
    png = os.path.join(OUT_DIR, out_stem + ".png")
    fig.savefig(pdf)
    fig.savefig(png, dpi=400)
    plt.close(fig)
    return pdf, png


def layout(fig, nrow, ncol_key):
    gs = GridSpec(nrow, 4, figure=fig,
                  width_ratios=[1.0, 0.05, 1.0, 0.05],
                  left=0.085, right=0.985, top=0.885, bottom=0.105,
                  wspace=0.07, hspace=0.62)
    fields, cbars = {}, {}
    for r in range(nrow):
        for c, key in enumerate(("pmc", "pec")):
            fields[(r, key)] = fig.add_subplot(gs[r, 2 * c])
            fields[(r, key)].set_anchor("N")
            cbars[(r, key)] = fig.add_subplot(gs[r, 2 * c + 1])
    return fields, cbars


def draw_ez(cases, geo):
    pmc, pec = cases["pmc"], cases["pec"]
    fig = plt.figure(figsize=(FIG_W, FIG_H))
    fields, cbars = layout(fig, 3, None)
    for key, case in (("pmc", pmc), ("pec", pec)):
        yc, zc = case["y_ez"], case["z_ez"]
        EXT = (-0.05, case["y_hi"] * 1e3 + 0.05, -0.05, case["z_hi"] * 1e3 + 0.05)
        E_bef, E_aft = case["viz"]["E"]["before"], case["viz"]["E"]["corrected"]
        v_common = max(np.max(np.abs(E_bef)), np.max(np.abs(E_aft)))
        D = E_aft - E_bef
        v_diff = float(np.max(np.abs(D)))
        c_sup, c_vv = case["corr_ez_sup"], case["corr_ez_vv"]
        titles = {
            0: "BEFORE  superseded, mis-paired\nvertical ref vs longitudinal\n$e_z$ corr = %+.4f" % c_sup,
            1: "AFTER  correctly paired\nvertical ref vs VERTICAL\n$e_z$ corr = %+.4f" % c_vv,
            2: "DIFFERENCE  after \u2212 before\nmax|\u0394| = %.2f, rms(\u0394)/rms = %.2f\ndimensionless" % (v_diff, rel_rms(D, E_aft, E_bef)),
        }
        for r, f, vmax in ((0, E_bef, v_common), (1, E_aft, v_common), (2, D, v_diff)):
            ax, cax = fields[(r, key)], cbars[(r, key)]
            panel(ax, f, yc, zc, EXT, titles[r], vmax, show_x=(r == 2),
                  show_y=(key == "pmc"))
            overlay(ax, geo)
            im = ax.images[0]
            cb = fig.colorbar(im, cax=cax)
            cb.ax.tick_params(labelsize=FS_TICK)
            cb.locator = matplotlib.ticker.MaxNLocator(4)
            cb.update_ticks()
            # the run label, once, on the top panel of its column
            if r == 0:
                ax.annotate(case["spec"]["label"].replace(" / ", "/\n"),
                            xy=(0.5, 1.72), xycoords="axes fraction",
                            ha="center", va="bottom", fontsize=FS_HEAD,
                            fontweight="bold")
    head = "$e_z$: what the mis-pairing did, and what the correct pairing gives"
    note = ("Fields divided by their own RMS (dimensionless).  Columns PMC / PEC are the two banked 31\u00d717 runs: "
            "c1_spectrum.npz QZ col 738 and pecbox_spectrum.npz QZ col 699.\n"
            "Dashed line: substrate interface h.  Thick line: strip.  Dotted verticals: strip edges y = 8.5 / 11.5 mm.  "
            "Colour limits shared across the two runs within a row; difference row on its own limit.")
    return finish(fig, "fig_ez_before_after", head, note)


def draw_ey(cases, geo):
    pmc, pec = cases["pmc"], cases["pec"]
    fig = plt.figure(figsize=(FIG_W, FIG_H))
    fields, cbars = layout(fig, 3, None)
    for key, case in (("pmc", pmc), ("pec", pec)):
        yc, zc = case["y_ey"], case["z_ey"]
        EXT = (-0.05, case["y_hi"] * 1e3 + 0.05, -0.05, case["z_hi"] * 1e3 + 0.05)
        A, E = case["viz"]["A_ey"], case["viz"]["E_ey"]
        v_common = max(np.max(np.abs(A)), np.max(np.abs(E)))
        D = A - E
        v_diff = float(np.max(np.abs(D)))
        c_ey = case["corr_ey"]
        titles = {
            0: "REFERENCE  analytic $e_y$\nwidth component\nunit RMS",
            1: "EXTRACTED  $e_y$\nwidth vs WIDTH\n$e_y$ corr = %+.4f" % c_ey,
            2: "DIFFERENCE  ref \u2212 extracted\nmax|\u0394| = %.2f, rms(\u0394)/rms = %.2f\ndimensionless" % (v_diff, rel_rms(D, A, E)),
        }
        for r, f, vmax in ((0, A, v_common), (1, E, v_common), (2, D, v_diff)):
            ax, cax = fields[(r, key)], cbars[(r, key)]
            panel(ax, f, yc, zc, EXT, titles[r], vmax, show_x=(r == 2),
                  show_y=(key == "pmc"))
            overlay(ax, geo)
            im = ax.images[0]
            cb = fig.colorbar(im, cax=cax)
            cb.ax.tick_params(labelsize=FS_TICK)
            cb.locator = matplotlib.ticker.MaxNLocator(4)
            cb.update_ticks()
            if r == 0:
                ax.annotate(case["spec"]["label"].replace(" / ", "/\n"),
                            xy=(0.5, 1.72), xycoords="axes fraction",
                            ha="center", va="bottom", fontsize=FS_HEAD,
                            fontweight="bold")
    head = "$e_y$: the same reference, the same pairing, the same metric throughout"
    note = ("Fields divided by their own RMS (dimensionless).  Columns PMC / PEC are the two banked 31\u00d717 runs: "
            "c1_spectrum.npz QZ col 738 and pecbox_spectrum.npz QZ col 699.\n"
            "Dashed line: substrate interface h.  Thick line: strip.  Dotted verticals: strip edges y = 8.5 / 11.5 mm.  "
            "Colour limits shared across the two runs within a row; difference row on its own limit.")
    return finish(fig, "fig_ey_before_after", head, note)


def main():
    with open(mp.GEOJSON) as fh:
        geo = json.load(fh)["geometry"]
    cases = {}
    for spec in mp.RUNS:
        cases[spec["key"]] = mp.reconstruct_run(spec, geo)
    print("")
    print("sizing : \\textwidth = %.5f pt = %.5f in ; figsize width = 0.95*\\textwidth"
          " = %.5f in ; height = %.2f in" % (TEXTWIDTH_PT, TEXTWIDTH_IN, FIG_W, FIG_H))
    print("fonts  : %s" % (RCPARAMS,))
    for fn in (draw_ez, draw_ey):
        pdf, png = fn(cases, geo)
        print("wrote  : %s (%d B)  %s (%d B)"
              % (pdf, os.path.getsize(pdf), png, os.path.getsize(png)))
    print("")
    print("plotted correlations (banked, read from the npz, never hard-coded):")
    for key, c in cases.items():
        print("  %-4s col %-4d corr_ez_superseded=%+.15f  corr_ez_vv=%+.15f  corr_ey=%+.15f"
              % (key, c["col"], c["corr_ez_sup"], c["corr_ez_vv"], c["corr_ey"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
