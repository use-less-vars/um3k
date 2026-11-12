#!/usr/bin/env python3
"""Load-side V(t) / I(t) of the diode-terminated cut (structure D) beside the
plain 50 ohm linear control (structure A) -- one packet, one grid, two
terminations.

WHY THE CONTROL ARM IS IN THIS FIGURE, AND WHY PLOTTING D ALONE WAS REJECTED
---------------------------------------------------------------------------
The claim under test is RECTIFICATION: the drive swings the termination both
ways, the termination conducts one way only.  A figure of D alone cannot carry
that claim, and the numbers printed below are what show why.

D's own load voltage is NOT two-sided.  Measured on this record:

    |min(v)|/max(v)   D = 202.441   (-179.369904 V against a positive side the
                                     diode clamps to +0.886036 V)

So D's voltage is already asymmetric, and D's one-sided current, seen alone, is
equally consistent with a one-sided SOURCE and with a one-sided DEVICE.  That
alternative -- plot D alone and call the current rectification -- was REJECTED:
it cannot separate the device's asymmetry from the source's.

The control arm A removes the confound.  Same cut, same solver, same Ricker
packet, same 2400-step grid, terminated in a plain 50 ohm resistor instead of
the diode.  A linear element cannot rectify, so A's current IS the drive:

    |min(v)|/max(v)   A = 0.463105   both polarities present at O(100 V)
    |min(i)|/max(i)   A = 0.463105   identical to 6 digits -- i = v/50 to
                                     float roundoff, i.e. purely linear
    Q_fwd/Q_rev       A = 0.999985   charge in = charge out (a linear element
                                     conserves charge)
    |min(i)|/max(i)   D = 2.33274e-11  forward conduction only
    Q_fwd/Q_rev       D = 1.54618e9    charge that went in and did not return

A's load voltage is two-sided but not equal-magnitude: the 15 GHz wave beats
against the |S11| = 0.327 port mismatch, so its positive half-cycle is the
taller one.  That asymmetry is in the DRIVE and is reproduced exactly in A's
current (same ratio), which is the point -- the control measures the drive, not
a device.  Q_fwd/Q_rev is the strongest single number here because a Ricker
packet enters and leaves, so a DC mean over the record is not a rectification
metric; the per-direction charge is, and it is immune to where in the record
the packet sits.  The DC means are printed anyway and are EXPECTED near zero
after the packet: this is a transient record, not a CW rectifier output,
claiming a DC rail from it would overclaim.

WHAT THE TRACES ARE
-------------------
``artifacts/load_trace_A.npz`` and ``artifacts/load_trace_D.npz`` are the packed
forms of the dumps written by ``evidence/termination/run_build_A.py --vis-dump``
(native solver quantities ``res.load_trace_v`` / ``res.load_trace_i``, read once
per step after the field writes have landed): ``load_t_ns``, ``load_v``,
``load_i``, float32, and nothing else -- the frames in the dumps are ~16.5 MB of
Ez per arm and are not needed for this figure, so they are not kept.  Nothing
here is reconstructed from a phasor: a single-frequency object cannot carry a
rectified waveform at all.

A packed trace therefore carries no ``load_trace_present`` flag.  Where the flag
IS present it must equal 1; where it is absent (stripped by the packer) the
arrays must be non-empty and of equal length.  Either arm failing that refuses
the plot, with the actual flags and shapes in the message: an honest failure
beats a curve.

Usage (from anywhere; paths resolve off this file's repo root)::

    PYTHONPATH=/workspace:/workspace/.venv/lib/python3.12/site-packages \
      /usr/local/bin/python3.12 evidence/termination/plot_load_trace.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display anywhere in this pipeline
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PNG = REPO / "artifacts" / "rectification_D.png"

# (key, legend label, packed trace, matplotlib colour)
ARMS = (
    (
        "A",
        "A - plain 50 ohm cut (linear control)",
        REPO / "artifacts" / "load_trace_A.npz",
        "C0",
    ),
    (
        "D",
        "D - diode-terminated cut",
        REPO / "artifacts" / "load_trace_D.npz",
        "C3",
    ),
)

TRACE_KEYS = ("load_t_ns", "load_v", "load_i")


def load_arm(key: str, label: str, path: Path, colour: str) -> dict:
    """Read one packed trace and hand back its series plus provenance.

    Refuses (with the actual flag and shapes) on a missing file, a trace whose
    ``load_trace_present`` says 0, a missing array, or empty/ragged arrays:
    every one of those means the run did not record what this figure claims.
    """
    if not path.exists():
        raise SystemExit(
            f"REFUSED: {path} does not exist (arm {key}).  Produce it first with\n"
            f"  PYTHONPATH=/workspace:/workspace/.venv/lib/python3.12/site-packages \\\n"
            f"  /usr/local/bin/python3.12 evidence/termination/run_build_A.py "
            f"--structure {key} --vis-dump artifacts/vis_dump_{key}.npz "
            f"--mem-ceiling-mb 500\n"
            "then pack load_t_ns/load_v/load_i out of that dump."
        )

    with np.load(path, allow_pickle=False) as d:
        files = list(d.files)
        flag = (
            int(np.asarray(d["load_trace_present"]).ravel()[0])
            if "load_trace_present" in files
            else None
        )
        missing = [k for k in TRACE_KEYS if k not in files]
        shapes = {
            k: (str(d[k].dtype), tuple(np.shape(d[k]))) for k in TRACE_KEYS if k in files
        }
        if missing or (flag is not None and flag != 1):
            raise SystemExit(
                f"REFUSED: {path.name} (arm {key}): load_trace_present={flag}, "
                f"missing={missing}, shapes={shapes}.  "
                "No usable load trace in this arm; fix the run, do not paper over it."
            )
        t = np.asarray(d["load_t_ns"], dtype=np.float64)
        v = np.asarray(d["load_v"], dtype=np.float64)
        i = np.asarray(d["load_i"], dtype=np.float64)

    if t.size == 0 or v.size == 0 or i.size == 0 or not (t.size == v.size == i.size):
        raise SystemExit(
            f"REFUSED: {path.name} (arm {key}): load_trace_present={flag} but the "
            f"arrays are empty or ragged: shapes={shapes}."
        )

    dt_ns = np.diff(t)
    dt_mean_s = float(dt_ns.mean()) * 1e-9
    n = int(t.size)

    v_min, v_max, v_mean = float(v.min()), float(v.max()), float(v.mean())
    i_min, i_max, i_mean = float(i.min()), float(i.max()), float(i.mean())

    q_fwd = float(i[i > 0].sum()) * dt_mean_s
    q_rev = float(-i[i < 0].sum()) * dt_mean_s

    tail = max(1, int(round(0.2 * n)))

    return {
        "key": key,
        "label": label,
        "path": path,
        "colour": colour,
        "flag": flag,
        "shapes": shapes,
        "t": t,
        "v": v,
        "i": i,
        "n": n,
        "dt_mean_ns": float(dt_ns.mean()),
        "dt_mean_s": dt_mean_s,
        "dt_min_ns": float(dt_ns.min()),
        "dt_max_ns": float(dt_ns.max()),
        "span_ns": float(t[-1] - t[0]),
        "v_min": v_min,
        "v_max": v_max,
        "v_mean": v_mean,
        "i_min": i_min,
        "i_max": i_max,
        "i_mean": i_mean,
        "v_ratio": abs(v_min) / v_max if v_max != 0 else float("inf"),
        "i_ratio": abs(i_min) / i_max if i_max != 0 else float("inf"),
        "q_fwd": q_fwd,
        "q_rev": q_rev,
        "q_ratio": q_fwd / q_rev if q_rev != 0 else float("inf"),
        "n_pos": int((i > 0).sum()),
        "n_neg": int((i < 0).sum()),
        "n_zero": int((i == 0).sum()),
        "n_pos_v": int((v > 0).sum()),
        "n_neg_v": int((v < 0).sum()),
        "tail": tail,
        "i_mean_tail": float(i[-tail:].mean()),
    }


def _fmt(x: float, width: int = 24) -> str:
    return f"{x:>{width}.6g}"


def print_table(arms: list[dict]) -> None:
    """One table, both arms: the comparison IS the evidence."""
    rows = (
        ("n samples", "n", "{:d}"),
        ("mean dt from diff(t) [ns]", "dt_mean_ns", "{:.6g}"),
        ("mean dt from diff(t) [s]", "dt_mean_s", "{:.6g}"),
        ("dt min [ns]", "dt_min_ns", "{:.6g}"),
        ("dt max [ns]", "dt_max_ns", "{:.6g}"),
        ("time span [ns]", "span_ns", "{:.6g}"),
        ("v min [V]", "v_min", "{:+.6g}"),
        ("v max [V]", "v_max", "{:+.6g}"),
        ("v mean [V]", "v_mean", "{:+.6g}"),
        ("i min [A]", "i_min", "{:+.6g}"),
        ("i max [A]", "i_max", "{:+.6g}"),
        ("i mean [A]", "i_mean", "{:+.6g}"),
        ("|min(v)|/max(v)", "v_ratio", "{:.6g}"),
        ("|min(i)|/max(i)", "i_ratio", "{:.6g}"),
        ("samples i>0", "n_pos", "{:d}"),
        ("samples i<0", "n_neg", "{:d}"),
        ("samples i==0", "n_zero", "{:d}"),
        ("samples v>0", "n_pos_v", "{:d}"),
        ("samples v<0", "n_neg_v", "{:d}"),
        ("Q_fwd [C]", "q_fwd", "{:+.6g}"),
        ("Q_rev [C]", "q_rev", "{:.6g}"),
        ("Q_fwd/Q_rev", "q_ratio", "{:.6g}"),
        ("mean i whole record [A]", "i_mean", "{:+.6g}"),
        ("mean i last 20% [A]", "i_mean_tail", "{:+.6g}"),
    )
    w = 28
    head = "quantity".ljust(w) + "".join(f"{a['label']:>26}" for a in arms)
    print("\n=== 0. BOTH ARMS SIDE BY SIDE (measured, one packet, one grid) ===")
    print(head)
    print("-" * len(head))
    for name, key, fmt in rows:
        print(name.ljust(w) + "".join(f"{fmt.format(a[key]):>26}" for a in arms))

    print("\ntwo-sidedness of the DRIVE (|min v|/max v, two-sided when O(1)):")
    for a in arms:
        verdict = "two-sided" if 0.2 < a["v_ratio"] < 5.0 else "LOP-SIDED: see caveat"
        print(f"  {a['key']}: {a['v_ratio']:.6g}   {verdict}")
    print("one-sidedness of the CURRENT (|min i|/max i, one-sided when << 1):")
    for a in arms:
        verdict = "one-sided (conduction only)" if a["i_ratio"] < 1e-3 else "two-sided (linear)"
        print(f"  {a['key']}: {a['i_ratio']:.6g}   {verdict}")
    print("charge balance (Q_fwd/Q_rev, ~1 for a linear element, >>1 rectifying):")
    for a in arms:
        print(f"  {a['key']}: {a['q_ratio']:.6g}")
    print("\ntail window (last 20%): " + ", ".join(
        f"{a['key']} last {a['tail']} of {a['n']} samples" for a in arms))


def print_arm(arm: dict) -> None:
    """The per-arm sections, kept recognisable from the D-only version."""
    print(f"\n--- arm {arm['key']}: {arm['label']} -------------------------------")
    print(f"trace      {arm['path']}  ({os.path.getsize(arm['path'])} bytes)")
    print(f"arrays     {arm['shapes']}  load_trace_present={arm['flag']}")
    print(f"dt         mean {arm['dt_mean_ns']:.6g} ns = {arm['dt_mean_s']:.6g} s"
          f"   min {arm['dt_min_ns']:.6g} ns   max {arm['dt_max_ns']:.6g} ns")
    print(f"time span  {arm['span_ns']:.6g} ns  (t[0]={arm['t'][0]:.6g} ns, "
          f"t[-1]={arm['t'][-1]:.6g} ns)")
    print(f"v_load [V] min {arm['v_min']:+.6g}  max {arm['v_max']:+.6g}  "
          f"mean {arm['v_mean']:+.6g}")
    print(f"i_load [A] min {arm['i_min']:+.6g}  max {arm['i_max']:+.6g}  "
          f"mean {arm['i_mean']:+.6g}")
    print(f"|min(v)|/max(v) = {arm['v_ratio']:.6g}")
    print(f"|min(i)|/max(i) = {arm['i_ratio']:.6g}   "
          f"({arm['n_pos']} i>0, {arm['n_neg']} i<0, {arm['n_zero']} i==0)")
    print(f"Q_fwd = {arm['q_fwd']:+.6g} C   Q_rev = {arm['q_rev']:.6g} C   "
          f"ratio = {arm['q_ratio']:.6g}")
    print(f"mean(i) whole = {arm['i_mean']:+.6g} A   "
          f"mean(i) last {arm['tail']} = {arm['i_mean_tail']:+.6g} A")


def plot(arms: list[dict]) -> None:
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(9.2, 6.8))

    for arm in arms:
        axes[0].plot(arm["t"], arm["v"], color=arm["colour"], lw=0.8,
                     label=arm["label"])
        axes[1].plot(arm["t"], arm["i"], color=arm["colour"], lw=0.8,
                     label=arm["label"])

    for ax, ylabel in ((axes[0], "v_load (V)"), (axes[1], "i_load (A)")):
        ax.axhline(0.0, color="0.6", lw=0.6, ls=":")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=8, framealpha=0.9)

    axes[1].set_xlabel("t (ns)")
    axes[0].set_title(
        "one packet, one grid, two terminations: A = plain 50 ohm cut (linear "
        "control), D = diode-terminated cut\n"
        "native per-step solver record (not a phasor reconstruction); linear "
        "axes, so D's reverse leakage (~1e-10 A) is invisible here and is "
        "carried by the numbers",
        fontsize=10,
    )

    fig.savefig(PNG, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"\nWROTE {PNG} ({os.path.getsize(PNG)} bytes)")


def verify_png() -> int:
    """No screen: the picture is verified by size, pixel dimensions and pixel
    statistics, never by "it looks right"."""
    try:
        from PIL import Image, ImageStat
    except ImportError:  # pragma: no cover
        print("PIL unavailable: PNG verification skipped (no pixel statistics)")
        return 0
    with Image.open(PNG) as im:
        im.load()
        w, h = im.size
        mode = im.mode
        stddev = [float(s) for s in ImageStat.Stat(im.convert("RGB")).stddev]
        ncolors = len(im.convert("RGB").getcolors(maxcolors=1 << 24) or [])
    print(f"PNG {w}x{h} px, mode {mode}, stddev RGB {stddev}, "
          f"distinct colours <= {ncolors}")
    if min(stddev) <= 0.0 or ncolors <= 1:
        raise SystemExit(
            f"REFUSED: {PNG} looks blank (stddev {stddev}, colours {ncolors})"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        raise SystemExit(
            f"no arguments: {argv!r}.  Edit ARMS at the top of this file."
        )

    arms = [load_arm(*spec) for spec in ARMS]
    print_table(arms)
    for arm in arms:
        print_arm(arm)
    plot(arms)
    return verify_png()


if __name__ == "__main__":
    raise SystemExit(main())
