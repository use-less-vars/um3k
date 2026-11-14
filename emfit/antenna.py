"""A presentation layer: a surface archive in, one picture and a few rows out.

This module owns no physics.  It calls :func:`emfit.ntff.plane_cut` twice -- once
for the ``E`` plane, once for the ``H`` plane, at the same frequency and the
same angles -- and turns the two :class:`emfit.ntff.PlaneCut` results into a
polar plot (base64 PNG) plus a short list of ``(label, value)`` strings.  It is
deliberately total: every failure mode of a viewer (a mistyped path, a file that
is not an archive, a frequency index that does not exist, matplotlib not
installed) comes back as a dict with ``image=None`` and a one-line ``reason``
instead of an exception, because the caller is a UI that has to draw *something*.
"""

import base64
import io
import os

import numpy as np

from .ntff import SurfaceDump, dbi, load_surface_dump, plane_cut

__all__ = ["build_far_field_report"]

#: How far below the peak the radial axis is cut off, in dB.  A dipole null is
#: ``-inf`` dB, and a radial axis that has to reach it shows nothing else.
_FLOOR_DB = 40.0

#: Longest ``reason`` string kept.  A reason is a sentence for a status bar,
#: not a log line, so a library's full diagnostic is trimmed, not forwarded.
_REASON_MAX = 180


def _import_pyplot():
    """``matplotlib.pyplot``, or ``None`` when matplotlib is not installed.

    Imported here rather than at module import so that this module can be used
    (and its failure path exercised) without the optional ``viz`` extra.
    """
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None
    return plt


def _ascii(text):
    """``text`` as ASCII, with anything else replaced rather than dropped."""
    return str(text).encode("ascii", "replace").decode("ascii")


def _one_line(text, limit=_REASON_MAX):
    """``text`` on one line, whitespace collapsed, trimmed to ``limit``."""
    collapsed = " ".join(_ascii(text).split())
    if len(collapsed) > limit:
        collapsed = collapsed[:limit - 3].rstrip() + "..."
    return collapsed


def _as_dump(source):
    """``source`` as a :class:`SurfaceDump`: loaded if it is a path, else as is."""
    if isinstance(source, SurfaceDump):
        return source
    try:
        name = os.fspath(source)
    except TypeError:
        raise ValueError(
            f"source of type {type(source).__name__}: a path to a surface "
            f"archive or a SurfaceDump is required") from None
    if not os.path.exists(name):
        raise ValueError(f"surface archive not found: {name}")
    try:
        return load_surface_dump(name)
    except (ValueError, OSError) as exc:
        raise ValueError(f"not a surface dump: {_one_line(exc)}") from None


def _peak_dbi(cuts):
    """The largest directivity over ``cuts``, in dBi."""
    peak = max(float(np.max(np.ravel(cut.D))) for cut in cuts)
    if not (np.isfinite(peak) and peak > 0.0):
        raise ValueError(
            "the cuts hold no positive directivity: every direction has "
            "zero radiation intensity")
    return float(dbi(peak))


def _peak_angle_deg(cut):
    """The ``theta`` at which ``cut`` peaks, in degrees."""
    return float(cut.theta_deg[int(np.argmax(cut.D))])


def _rows(cuts, freq, p_rad, peak_d, p_in_w):
    """The ``(label, value)`` rows of the report, in reading order."""
    rows = [
        ("Frequency", f"{freq / 1e6:.3f} MHz"),
        ("Radiated power", f"{p_rad:.6g} W"),
        ("Peak directivity", f"{peak_d:.3f} dBi"),
    ]
    for cut in cuts:
        cut_peak = float(dbi(float(np.max(np.ravel(cut.D)))))
        rows.append((cut.label,
                     f"{cut_peak:.3f} dBi at theta = "
                     f"{_peak_angle_deg(cut):.1f} deg"))
    if p_in_w is not None:
        peak_g = float(dbi(max(float(np.max(np.ravel(cut.G)))
                               for cut in cuts)))
        rows.append(("Peak gain", f"{peak_g:.3f} dBi"))
    return [(_ascii(_one_line(label)), _ascii(_one_line(value)))
            for label, value in rows]


def _caption(cuts, freq, p_rad, peak_d):
    """One ASCII sentence describing the figure that was drawn."""
    planes = " and ".join(cut.plane for cut in cuts)
    return _ascii(
        f"{planes}-plane cuts of the far field at {freq / 1e6:.3f} MHz: peak "
        f"directivity {peak_d:.2f} dBi, radiated power {p_rad:.4g} W, radial "
        f"scale in dBi clipped at peak - {_FLOOR_DB:.0f} dB.")


def _render(cuts, freq, peak_d, dpi, title):
    """The polar figure as a base64 PNG data URI, or ``None`` without pyplot."""
    plt = _import_pyplot()
    if plt is None:
        return None, "matplotlib unavailable"
    floor = peak_d - _FLOOR_DB
    fig = plt.figure(figsize=(6.4, 6.4), dpi=dpi)
    try:
        ax = fig.add_subplot(1, 1, 1, projection="polar")
        ax.set_theta_zero_location("E")   # 0 deg at +x, to the right
        ax.set_theta_direction(1)         # increasing anticlockwise
        for cut, color, style in zip(cuts, ("#1f4e9c", "#c0392b"), ("-", "--")):
            # Clipping a null to the floor keeps the lobe structure visible;
            # the clip is named in the caption and on the radial axis.
            radial = np.maximum(dbi(cut.D), floor)
            ax.plot(cut.theta, radial, color=color, linestyle=style,
                    linewidth=1.4, label=cut.label)
        ax.set_rlim(floor, peak_d + 2.0)
        ax.set_rlabel_position(112.5)
        ax.set_ylabel(f"D, dBi (clipped at {floor:.1f})", fontsize=8)
        base = _ascii(title) if title else "Far-field plane cuts"
        ax.set_title(f"{base} - {freq / 1e6:.3f} MHz, peak {peak_d:.2f} dBi",
                     fontsize=10)
        ax.legend(loc="lower left", bbox_to_anchor=(-0.12, -0.08), fontsize=7)
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(fig)
    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{payload}", None


def _failure(reason):
    """The report of a run that could not draw anything."""
    reason = _one_line(reason)
    return {
        "image": None,
        "rows": [],
        "reason": reason,
        "caption": _ascii(f"Far-field report unavailable: {reason}"),
        "freq": None,
        "peak_d_dbi": None,
        "p_rad": None,
        "plane_labels": [],
    }


def build_far_field_report(source, *, freq_index=0, n_theta=181, p_in_w=None,
                           dpi=110, title=None):
    """The ``E``- and ``H``-plane cuts of a surface archive, as a picture.

    Two :func:`emfit.ntff.plane_cut` calls -- one per principal plane, at the
    same ``freq_index`` and the same ``n_theta`` angles -- are drawn on a single
    polar axes: angle is ``theta`` from ``0`` to ``pi``, radius is directivity in
    dBi, clipped at ``peak - 40`` dB so a null cannot swallow the plot.

    This function never raises.  A missing file, a file that is not an archive,
    a frequency index the archive does not have, or an absent matplotlib all
    come back as a report with ``image=None`` and a one-line ``reason``.

    Parameters
    ----------
    source : str, os.PathLike or SurfaceDump
        The archive, or one already loaded.  A path goes through
        :func:`emfit.ntff.load_surface_dump`, so the same validation applies.
    freq_index : int, optional
        Which frequency of the archive to cut; ``0`` by default.
    n_theta : int, optional
        Angles along each cut, at least two; ``181`` by default.
    p_in_w : float, optional
        Input power in W, for the gain rows.  Without it no gain is reported:
        the archive does not hold a delivered power (see the ``TODO(TE)`` note
        in :mod:`emfit.ntff`).
    dpi : int, optional
        Resolution of the PNG; ``110`` by default.
    title : str, optional
        Figure title prefix; the frequency and peak directivity are appended.

    Returns
    -------
    dict
        Exactly the keys ``image``, ``rows``, ``reason``, ``caption``, ``freq``,
        ``peak_d_dbi``, ``p_rad`` and ``plane_labels``.  ``image`` is a
        ``data:image/png;base64,...`` string or ``None``; ``rows`` is a list of
        ``(label, value)`` strings, empty on failure; ``reason`` is ``None`` on
        success and one line of ASCII otherwise.
    """
    try:
        dump = _as_dump(source)
        n_freq = int(np.asarray(dump.freqs).size)
        index = int(freq_index)
        if index < 0 or index >= n_freq:
            raise ValueError(
                f"freq_index {index} out of range for {n_freq} "
                f"frequenc{'y' if n_freq == 1 else 'ies'}")
        cuts = [
            plane_cut(dump, plane=name, freq_index=index, n_theta=n_theta,
                      p_in_w=p_in_w)
            for name in ("E", "H")
        ]
        freq = float(cuts[0].freq)
        p_rad = float(cuts[0].P_rad)
        peak_d = _peak_dbi(cuts)
        image, reason = _render(cuts, freq, peak_d, dpi, title)
        if image is None:
            return _failure(reason)
        return {
            "image": image,
            "rows": _rows(cuts, freq, p_rad, peak_d, p_in_w),
            "reason": None,
            "caption": _caption(cuts, freq, p_rad, peak_d),
            "freq": freq,
            "peak_d_dbi": peak_d,
            "p_rad": p_rad,
            "plane_labels": [cut.label for cut in cuts],
        }
    except Exception as exc:                      # the contract: never raise
        return _failure(f"{str(exc) or type(exc).__name__}")
