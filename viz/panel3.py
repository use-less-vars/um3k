#!/usr/bin/env python3
"""Panel 3 of the 59V screen -- the T4 amplitude bar at the five rungs.

Standalone module. `python3 viz/panel3.py` builds a throwaway figure at the real
FIGW x FIGH x DPI, draws panel 3 onto it, prints every assertion with its
operands, and renders once to /tmp so layout, font and hatch errors surface.
This file writes nothing under viz/: d59v_screen.py owns screen.png, screen.svg,
screen.json and strings.txt.

Contract
    draw_panel3(fig, drawn, out=None) -> record
        fig    matplotlib Figure. Panel 3 is drawn in the empty bottom band of
               the canvas, figure coords roughly y in [0.03, 0.33], full width,
               on axes of its own (AX1 / AX2R / AXLR are never touched).
        drawn  append-only iterable -- the main script's DRAWN list. Every
               string drawn on the figure is appended to it in draw order.
        out    directory for derived artefact paths. None -> viz/out/ beside
               this file, so the module runs standalone.
        returns `record`, which d59v_screen.py stores as screen.json["panel3"].

Data -- committed JSON only, tier E1
    evidence/t4/ladder_convergence.json    /constants, /rungs[i], /verdict,
                                           /route_c_cross_check
    evidence/t4/rung4_routeC_report.json   /verdict/route_C/rung4/agreement/status
/rungs is a LIST; rungs are located by their "rung" field, never by position.

Run:  PYTHONDONTWRITEBYTECODE=1 python3 viz/panel3.py
"""
from __future__ import annotations

import json
import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_OUT = os.path.join(HERE, "out")

LADDER = "evidence/t4/ladder_convergence.json"
ROUTEC = "evidence/t4/rung4_routeC_report.json"

FIGW, FIGH, DPI = 16.0, 13.60, 130

# ---- palette: the SAME hexes as viz/d59v_screen.py (TIER_FILL / TIER_INK).
# Copied rather than imported so this module stays runnable on its own; every
# luminance and contrast ratio below is computed FROM these strings.
TIER_FILL = {"E1": "#FDFDFD", "WITHHELD": "#898989", "E5": "#272727"}
TIER_INK = {"E1": "#111111", "WITHHELD": "#FFFFFF", "E5": "#F5F5F5"}
PAGE = "#FFFFFF"          # the figure's page
INK = "#111111"           # default ink, same as TIER_INK["E1"]
RED = "#8b0000"           # the caption red already used on panels 1-2


def _srgb_lin(v):
    c = v / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def wcag_L(h):
    """WCAG 2.x relative luminance, computed from the hex."""
    r, g, b = _rgb(h)
    return 0.2126 * _srgb_lin(r) + 0.7152 * _srgb_lin(g) + 0.0722 * _srgb_lin(b)


def grey8(h):
    """8-bit greyscale value of the hex, for printing alongside WCAG L."""
    r, g, b = _rgb(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag_ratio(la, lb):
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def load_data():
    with open(os.path.join(ROOT, LADDER), "r", encoding="utf-8") as f:
        A = json.load(f)
    with open(os.path.join(ROOT, ROUTEC), "r", encoding="utf-8") as f:
        B = json.load(f)
    rungs = {}
    for r in A["rungs"]:
        rungs[int(r["rung"])] = r            # locate by the rung field, never by position
    return {
        "A": A,
        "B": B,
        "constants": A["constants"],
        "rungs": rungs,
        "verdict": A["verdict"],
        "rc": A["route_c_cross_check"],
        "rc_status": B["verdict"]["route_C"]["rung4"]["agreement"]["status"],
    }


def check(d):
    """The four required assertions. Each prints its operands and raises on failure."""
    c = d["constants"]
    verdict = d["verdict"]
    rungs = d["rungs"]
    tol = float(c["tol_rel"])
    Ra = float(c["R_analytic"])

    print("=== ASSERTION 1: the band's two edges, derived BOTH ways ===")
    lo_t, hi_t = 1.0 - tol, 1.0 + tol
    lo_r, hi_r = float(c["band_lo"]) / Ra, float(c["band_hi"]) / Ra
    print("  via tol_rel        : lo = 1 - %.17g = %.17g" % (tol, lo_t))
    print("                       hi = 1 + %.17g = %.17g" % (tol, hi_t))
    print("  via band/R_analytic: lo = %.17g / %.17g = %.17g" % (float(c["band_lo"]), Ra, lo_r))
    print("                       hi = %.17g / %.17g = %.17g" % (float(c["band_hi"]), Ra, hi_r))
    d_lo, d_hi = abs(lo_t - lo_r), abs(hi_t - hi_r)
    print("  |difference|       : lo = %.6e   hi = %.6e   (limit 1e-12)" % (d_lo, d_hi))
    if not (d_lo <= 1e-12 and d_hi <= 1e-12):
        raise AssertionError("band edges disagree: lo %.6e hi %.6e" % (d_lo, d_hi))
    print("  PASS: both derivations agree to 1e-12")

    print("\n=== ASSERTION 2: |Q-1| from Q vs err_pct/100, and in_band, for all five rungs ===")
    print("  rung  free_e        Q                          |Q-1|                      "
          "err_pct/100                difference   in_band  |Q-1|<=tol")
    for k in sorted(rungs):
        r = rungs[k]
        q = float(r["Q"])
        a = abs(q - 1.0)
        e = float(r["err_pct"]) / 100.0
        diff = abs(a - e)
        inb = bool(r["in_band"])
        recomp = (a <= tol)
        print("  %4d  %6d  %.17g  %.17g  %.17g  %.6e  %-7s  %-7s"
              % (k, int(r["free_e"]), q, a, e, diff, inb, recomp))
        if diff > 1e-12:
            raise AssertionError("rung %d: |Q-1| %.17g != err_pct/100 %.17g (diff %.6e)"
                                 % (k, a, e, diff))
        if inb != recomp:
            raise AssertionError("rung %d: in_band %s but |Q-1| <= tol is %s (|Q-1| %.17g, tol %.17g)"
                                 % (k, inb, recomp, a, tol))
    print("  PASS: 5/5 agree to 1e-12; in_band matches (|Q-1| <= tol_rel = %.17g)" % tol)

    print("\n=== ASSERTION 3: rung-field mapping (located by 'rung', never by position) ===")
    want = {0: 1444, 1: 2404, 2: 3604, 3: 5044, 4: 9604}
    got = {k: int(rungs[k]["free_e"]) for k in sorted(rungs)}
    print("  list order vs rung field : %s" % [(i, int(r["rung"])) for i, r in enumerate(d["A"]["rungs"])])
    print("  rung fields present      : %s" % sorted(rungs))
    print("  free_e from JSON         : %s" % [got[k] for k in sorted(got)])
    print("  free_e required          : %s" % [want[k] for k in sorted(want)])
    if sorted(rungs) != [0, 1, 2, 3, 4]:
        raise AssertionError("rung fields are %s, expected 0..4" % sorted(rungs))
    if got != want:
        raise AssertionError("free_e mapping %s != required %s" % (got, want))
    print("  PASS: rungs 0..4 with free_e 1444, 2404, 3604, 5044, 9604")

    print("\n=== ASSERTION 4: /verdict/multiple_of_allowance vs |Q_rung4 - 1| / allowance ===")
    q4 = float(rungs[4]["Q"])
    allow = float(verdict["allowance"])
    mult = float(verdict["multiple_of_allowance"])
    calc = abs(q4 - 1.0) / allow
    print("  Q_rung4 (by rung field)        = %.17g" % q4)
    print("  /verdict/Q                     = %.17g   (identical to Q_rung4: %s)"
          % (float(verdict["Q"]), float(verdict["Q"]) == q4))
    print("  |Q_rung4 - 1|                  = %.17g" % abs(q4 - 1.0))
    print("  allowance                      = %.17g" % allow)
    print("  computed |Q-1| / allowance     = %.17g" % calc)
    print("  /verdict/multiple_of_allowance = %.17g" % mult)
    print("  |difference|                   = %.6e   (limit 1e-12)" % abs(calc - mult))
    if abs(calc - mult) > 1e-12:
        raise AssertionError("multiple_of_allowance %.17g != computed %.17g (diff %.6e)"
                             % (mult, calc, abs(calc - mult)))
    print("  PASS")

    print("\n=== CHECK 5: the two Q values footnote (h) must quote, read from /rungs ===")
    q0, q1 = float(rungs[0]["Q"]), float(rungs[1]["Q"])
    print("  rung 0: Q = %r   |Q-1| = %.17g  (57c_acceptance.md, section"
          " 'Numbers carried in, all [RELAYED], all unverified', writes '0.441')" % (q0, abs(q0 - 1.0)))
    print("  rung 1: Q = %r   |Q-1| = %.17g  (57c_acceptance.md, same section, writes '0.345')"
          % (q1, abs(q1 - 1.0)))
    if q0 != 1.440865461991999 or q1 != 1.3452649773413672:
        raise AssertionError("footnote operands moved: %r, %r" % (q0, q1))
    print("  PASS: Q are 1.440865461991999 and 1.3452649773413672; 0.441 and 0.345 are |Q-1|")

    return {"lo_tol": lo_t, "hi_tol": hi_t, "lo_R": lo_r, "hi_R": hi_r,
            "lo_diff": d_lo, "hi_diff": d_hi, "calc_multiple": calc}


def draw_panel3(fig, drawn, out=None):
    """Draw panel 3 onto `fig`; append every drawn string to `drawn`; return `record`."""
    out_dir = DEFAULT_OUT if out is None else out
    n0 = len(drawn)
    d = load_data()
    chk = check(d)

    c = d["constants"]
    rungs = d["rungs"]
    verdict = d["verdict"]
    rc = d["rc"]
    order = sorted(rungs)
    fe = [int(rungs[k]["free_e"]) for k in order]
    qs = [float(rungs[k]["Q"]) for k in order]
    tol = float(c["tol_rel"])
    lo_q, hi_q = 1.0 - tol, 1.0 + tol

    def rec(s):
        drawn.append(str(s))
        return str(s)

    # ---------------------------------------------------------------- title + (d) headline
    fig.text(0.012, 0.322,
             rec("Panel 3 \u2014 the T4 amplitude bar: all five rungs sit ABOVE the pre-registered band"),
             fontsize=12.0, weight="bold", color=INK, va="bottom")

    mult = float(verdict["multiple_of_allowance"])
    headline = ('/verdict/T4_amp = "%s"   |   |Q-1| at rung 4 = %.4f x allowance   (allowance = %.4g)'
                % (verdict["T4_amp"], mult, float(verdict["allowance"])))
    fig.text(0.012, 0.298, rec(headline), fontsize=10.0, weight="bold", color=RED, va="bottom")

    # ---------------------------------------------------------------- (a)(b)(c) the five Q points
    ax = fig.add_axes([0.050, 0.118, 0.405, 0.162])
    ax.set_facecolor("#ffffff")
    for sp in ax.spines.values():
        sp.set_linewidth(0.8)
        sp.set_color(INK)
    ax.tick_params(labelsize=7, colors=INK, length=2.5)
    ax.set_xlim(700, 10300)
    ax.set_ylim(0.85, 1.50)
    ax.set_xticks(fe)
    ax.set_xticklabels([str(v) for v in fe])
    ax.set_title(rec("Q = R_extracted / R_analytic at the five rungs (x = free_e); band |Q-1| <= 0.10 shaded"),
                 fontsize=7.4, color=INK, pad=3)

    # (b) the pre-registered band, and full-weight labelled bars at its edges
    ax.axhspan(lo_q, hi_q, facecolor="#d9d9d9", edgecolor="#8a8a8a", lw=0.5, zorder=0)
    ax.text(5500, 0.5 * (lo_q + hi_q),
            rec("pre-registered band  0.90 <= Q <= 1.10  (|Q-1| <= 0.10)"),
            fontsize=6.4, color="#333333", ha="center", va="center", zorder=1)
    ax.axhline(hi_q, color="#000000", lw=2.2, zorder=3)
    ax.text(10150, hi_q + 0.012, rec("Q = 1.10 \u2014 band edge (bar, not a soft guide)"),
            fontsize=6.4, color=INK, ha="right", va="bottom", zorder=5)
    ax.axhline(lo_q, color="#000000", lw=2.2, zorder=3)
    ax.text(10150, lo_q - 0.012, rec("Q = 0.90 \u2014 band edge (bar, not a soft guide)"),
            fontsize=6.4, color=INK, ha="right", va="top", zorder=5)

    # (a) the points, and (c) Q with |Q-1| to 4 dp, staggered so adjacent labels do not collide
    ax.plot(fe, qs, ls="none", marker="o", ms=7.0, mfc="#1a1a1a", mec="#ffffff", mew=1.0, zorder=4)
    for i, k in enumerate(order):
        q = qs[i]
        a = abs(q - 1.0)
        above = (i % 2 == 0)
        ax.annotate(rec("Q=%.4f  |Q-1|=%.4f" % (q, a)),
                    (fe[i], q), textcoords="offset points",
                    xytext=(0, 10 if above else -12),
                    ha="center", va="bottom" if above else "top",
                    fontsize=6.4, color=INK, zorder=6)

    # ---------------------------------------------------------------- (e) the boxed Route C inset
    axc = fig.add_axes([0.495, 0.145, 0.300, 0.135])
    axc.set_xlim(0, 1)
    axc.set_ylim(0, 1)
    axc.set_axis_off()
    axc.add_patch(Rectangle((0.0, 0.0), 1.0, 1.0, transform=axc.transAxes,
                            facecolor="#f6f6f6", edgecolor=INK, lw=1.0, zorder=1))

    ag = rc["agreement"]
    cm = rc["cost_measured"]
    caption = ("CAPTION (mandatory): the 11-digit agreement is with the SAME-MESH DENSE SOLVE, "
               "NOT with R_analytic \u2014 therefore it does not mean the gate passed.")
    box = [
        ("BOXED INSET \u2014 Route C cross-check at the rung-4 mesh",
         {"fontsize": 7.0, "weight": "bold"}),
        ("agreement: beta_sq_digits = %.4f, R_digits = %.4f matching digits, against the dense solve at this same mesh"
         % (float(ag["beta_sq_digits"]), float(ag["R_digits"])), {"fontsize": 6.2}),
        ("cost: factor_nnz = %s, fill_per_row = %.4f, factor_memory_gb = %.6f"
         % (format(int(cm["factor_nnz"]), ","), float(cm["fill_per_row"]), float(cm["factor_memory_gb"])),
         {"fontsize": 6.2}),
        (caption, {"fontsize": 6.2, "weight": "bold", "color": RED}),
        ("purpose (verbatim, /route_c_cross_check/purpose): " + rc["purpose"],
         {"fontsize": 6.0, "style": "italic"}),
        ("status: %s   (/verdict/route_C/rung4/agreement/status)" % d["rc_status"], {"fontsize": 6.2}),
    ]
    yb = 0.950
    for s, kw in box:
        for ln in textwrap.wrap(" ".join(str(s).split()), width=86):
            kw_txt = {"color": INK}
            kw_txt.update(kw)
            axc.text(0.015, yb, rec(ln), transform=axc.transAxes, va="top", ha="left",
                     zorder=2, **kw_txt)
            yb -= 0.062

    # ---------------------------------------------------------------- (f) committed provenance
    prov = ("SOURCES (committed JSON, tier E1) \u2014 evidence/t4/ladder_convergence.json :: "
            "/constants{R_analytic, band_lo, band_hi, tol_rel}, "
            "/rungs[i]{rung, free_e, Q, err_pct, in_band} located by the \"rung\" field never by position, "
            "/verdict{T4_amp, Q, Q_minus_1_abs, allowance, multiple_of_allowance}, "
            "/route_c_cross_check{agreement.beta_sq_digits, agreement.R_digits, cost_measured.factor_nnz, "
            "cost_measured.fill_per_row, cost_measured.factor_memory_gb, purpose}   ||   "
            "evidence/t4/rung4_routeC_report.json :: /verdict/route_C/rung4/agreement/status")
    yp = 0.132
    for ln in textwrap.wrap(" ".join(prov.split()), width=118):
        fig.text(0.495, yp, rec(ln), fontsize=6.2, color=INK, va="top")
        yp -= 0.010

    # ---------------------------------------------------------------- (g) the E1 badge
    fill, ink = TIER_FILL["E1"], TIER_INK["E1"]
    L_fill, L_ink = wcag_L(fill), wcag_L(ink)
    ratio = wcag_ratio(L_ink, L_fill)
    print("\n=== CHECK (g): E1 badge tones, computed from the hexes ===")
    print("  fill %s  WCAG L = %.4f   greyscale = %.1f / 255" % (fill, L_fill, grey8(fill)))
    print("  ink  %s  WCAG L = %.4f   greyscale = %.1f / 255" % (ink, L_ink, grey8(ink)))
    print("  contrast ratio ink-on-fill = %.2f:1   (gate >= 3.0)" % ratio)
    print("  fill vs page %s            = %.2f:1   (the badge reads by double rule + hatch, not by tone)"
          % (PAGE, wcag_ratio(L_fill, wcag_L(PAGE))))
    if ratio < 3.0:
        raise AssertionError("E1 badge ink/fill contrast %.2f:1 is below the 3.0 gate" % ratio)
    print("  PASS: %.2f:1 >= 3.0" % ratio)

    bx, by, bw, bh = 0.800, 0.232, 0.185, 0.048
    fig.add_artist(Rectangle((bx, by), bw, bh, transform=fig.transFigure, facecolor=fill,
                             edgecolor=ink, lw=1.4, hatch="//////", zorder=6))
    fig.add_artist(Rectangle((bx + 0.0035, by + 0.0035), bw - 0.007, bh - 0.007,
                             transform=fig.transFigure, facecolor="none", edgecolor=ink,
                             lw=0.7, zorder=7))
    fig.text(bx + 0.010, by + 0.030, rec("E1 \u2014 PROVEN"), fontsize=10.0, weight="bold",
             color=ink, va="center", zorder=8)
    fig.text(bx + 0.010, by + 0.012, rec("committed JSON only \u00b7 reproducible from the repository"),
             fontsize=6.0, color=ink, va="center", zorder=8)
    note = ("badge fill %s (L %.4f, grey %.1f) \u00b7 ink %s (L %.4f, grey %.1f) \u00b7 contrast %.2f:1 "
            "computed in code, gate >= 3.0 PASS" % (fill, L_fill, grey8(fill), ink, L_ink, grey8(ink), ratio))
    yn = by - 0.012
    for ln in textwrap.wrap(note, 55):
        fig.text(bx, yn, rec(ln), fontsize=5.8, color=INK, va="top")
        yn -= 0.010

    # (g2) B3 status tag -- drawn in the free space under the badge note, right-hand column.
    # One line would end at x = 1.1045 (measured), past the page edge, so it is wrapped at 48.
    for ln in textwrap.wrap("status: COMMITTED \u2014 every number on this panel is read from "
                            "committed JSON at HEAD (B3)", 48):
        fig.text(bx, yn, rec(ln), fontsize=6.4, weight="bold", color=INK, va="top")
        yn -= 0.010

    # ------------------------------------------------- (h) the footnote, cited by section, not by line
    fn1 = ("57c_acceptance.md, section \"Numbers carried in, all [RELAYED], all unverified\", writes "
           "\"Q = 1.272\" for rung 4 \u2014 correct: this panel reads %r." % (float(verdict["Q"]),))
    fn2 = ("Its \"Q = 0.441 and 0.345\" for rungs 0-1 are |Q-1|, not Q; this panel's Q, from committed "
           "JSON, are %r and %r." % (qs[0], qs[1]))
    fn3 = ("Those doc numbers are [RELAYED] \u2014 \"carried from a dispatch, brief or prior agent, "
           "unverified\"; every number here is read from committed JSON at HEAD.")
    fn4 = ("docs/design/57c_closeout.md, verdict A: \"T4_amp: FAIL was decided before any rung ran\" "
           "\u2014 the registered quantity and gate, not the solver.")
    yf = 0.092
    for ln in textwrap.wrap(" ".join((fn1 + " " + fn2 + " " + fn3 + " " + fn4).split()), width=112):
        fig.text(0.012, yf, rec(ln), fontsize=6.4, color=INK, va="top")
        yf -= 0.010

    record = {
        "panel": 3,
        "rendered": ("five Q points against the pre-registered band, full-weight band bars, "
                     "Route C cross-check inset, E1 badge, committed provenance"),
        "tier": "E1",
        "status_tag": "COMMITTED",
        "tier_note": ("every number drawn is read from committed JSON at HEAD; nothing comes from "
                      ".scratch/ and nothing is uncommitted"),
        "sources": [LADDER, ROUTEC],
        "pointers": [
            LADDER + " :: /constants",
            LADDER + " :: /rungs[i] (located by the \"rung\" field)",
            LADDER + " :: /verdict",
            LADDER + " :: /route_c_cross_check",
            ROUTEC + " :: /verdict/route_C/rung4/agreement/status",
        ],
        "band": {
            "tol_rel": tol,
            "lo": lo_q, "hi": hi_q,
            "lo_via_R_over_Ranalytic": chk["lo_R"], "hi_via_R_over_Ranalytic": chk["hi_R"],
            "lo_difference": chk["lo_diff"], "hi_difference": chk["hi_diff"],
            "agreement_limit": 1e-12,
        },
        "points": [
            {
                "rung": k,
                "free_e": fe[i],
                "Q": qs[i],
                "abs_Q_minus_1": abs(qs[i] - 1.0),
                "err_pct": float(rungs[k]["err_pct"]),
                "in_band": bool(rungs[k]["in_band"]),
            }
            for i, k in enumerate(order)
        ],
        "verdict": {
            "T4_amp": verdict["T4_amp"],
            "Q": float(verdict["Q"]),
            "Q_minus_1_abs": float(verdict["Q_minus_1_abs"]),
            "allowance": float(verdict["allowance"]),
            "multiple_of_allowance": mult,
            "headline": headline,
        },
        "route_c": {
            "beta_sq_digits": float(ag["beta_sq_digits"]),
            "R_digits": float(ag["R_digits"]),
            "factor_nnz": int(cm["factor_nnz"]),
            "fill_per_row": float(cm["fill_per_row"]),
            "factor_memory_gb": float(cm["factor_memory_gb"]),
            "agreement_status": d["rc_status"],
            "caption": caption,
            "purpose": rc["purpose"],
        },
        "badge": {
            "tier": "E1", "fill": fill, "ink": ink,
            "L_fill": L_fill, "L_ink": L_ink,
            "grey8_fill": grey8(fill), "grey8_ink": grey8(ink),
            "contrast_ratio": ratio, "contrast_gate": 3.0,
        },
        "footnote": {
            "acceptance_md_Q_quote": fn1,
            "acceptance_md_absQ_quote": fn2,
            "acceptance_md_relayed_tag": fn3,
            "closeout_verdict_quote": fn4,
            "true_Q_rung0": qs[0],
            "true_Q_rung1": qs[1],
        },
        "axes": {
            "panel3_plot": [0.050, 0.118, 0.405, 0.162],
            "route_c_inset": [0.495, 0.145, 0.300, 0.135],
            "badge_box": [bx, by, bw, bh],
        },
        "out_dir": out_dir,
        "strings_drawn": len(drawn) - n0,
    }
    return record


if __name__ == "__main__":
    print("=== viz/panel3.py standalone: FIGW %.2f x FIGH %.2f x DPI %d ===" % (FIGW, FIGH, DPI))
    fig = plt.figure(figsize=(FIGW, FIGH), dpi=DPI)
    drawn = []
    record = draw_panel3(fig, drawn)

    print("\n=== RECORD (stored by d59v_screen.py as screen.json['panel3']) ===")
    print(json.dumps(record, indent=1, sort_keys=True))

    print("\n=== DRAWN STRINGS (%d) ===" % len(drawn))
    for i, s in enumerate(drawn, 1):
        print("  %3d  %s" % (i, s))

    tmp = "/tmp/panel3_standalone.png"
    fig.savefig(tmp, dpi=DPI, metadata={"Software": None})
    print("\nstandalone render: %s  %d bytes  (%.2f x %.2f in at %d dpi)"
          % (tmp, os.path.getsize(tmp), FIGW, FIGH, DPI))
    plt.close(fig)
    print("\nALL ASSERTIONS PASSED; panel 3 renders standalone.")
