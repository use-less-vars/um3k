"""Headless matplotlib figures for the FIT solver.

This module is deliberately **matplotlib-only**: no seaborn, no plotly, no
notebook backends.  ``matplotlib.use("Agg")`` is selected before ``pyplot`` is
imported, so every helper here is safe in a headless batch job, a CI container
or a LaTeX build pipeline.  No function calls ``plt.show()``; they all return
the created :class:`matplotlib.figure.Figure` (and usually the axes) so the
caller can either inspect it or hand it to :func:`save`.

Typical use::

    from emfit import viz
    fig, ax = viz.plot_spectrum(computed_hz, analytic_hz)
    viz.save(fig, "docs/figures/cavity_spectrum.png")
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (after backend selection)
import numpy as np  # noqa: E402

from .operators import CellComplex  # noqa: E402

__all__ = ["save", "plot_spectrum", "plot_field_slice", "plot_energy"]

# --- style -----------------------------------------------------------------
plt.rcParams.update(
    {
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "axes.grid": False,
        "axes.linewidth": 0.6,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "legend.frameon": False,
        "lines.linewidth": 1.2,
        "figure.dpi": 110,
        "savefig.dpi": 140,
        "figure.constrained_layout.use": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

# small fixed palette (colour-blind friendly, prints fine in greyscale)
COL_PRIMARY = "#2b6cb0"   # computed / main curves
COL_ACCENT = "#c05621"    # second series / annotations
COL_MUTED = "#7a7a7a"     # analytic reference lines
COL_INK = "#1a202c"       # outlines and axes


# ---------------------------------------------------------------------------
def save(fig, path, dpi: int = 140) -> str:
    """Write ``fig`` to ``path`` and close it.

    Parent directories are created when missing; the tight bounding box is
    used so the LaTeX page sees no wasted margin.

    Args:
        fig: Matplotlib figure to write.
        path: Destination file (its suffix selects the format, e.g. ``.png``).
        dpi: Raster resolution for bitmap formats.

    Returns:
        The path as an absolute path string.
    """
    path = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fig.savefig(path, dpi=int(dpi), bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
def _fmt(ax=None):
    """Return ``(fig, ax)`` creating a fresh single panel when ``ax`` is None."""
    if ax is None:
        return plt.subplots()
    return ax.figure, ax


def plot_spectrum(computed_hz, analytic_hz=None, ax=None, title=None):
    """Compare computed resonances against the analytic cavity spectrum.

    Each computed mode is drawn as a horizontal lollipop on a frequency axis in
    MHz: a stem from the analytic value (if given, otherwise from the left edge
    of the axis) to the computed value, with a marker at the computed value and
    the relative error annotated in percent.  Analytic modes appear as dashed
    grey vertical reference lines.

    Args:
        computed_hz: Computed resonant frequencies [Hz], one per mode.
        analytic_hz: Optional analytic frequencies [Hz], same ordering.
        ax: Axes to draw on; a new figure is made when omitted.
        title: Optional axes title.

    Returns:
        ``(fig, ax)``.
    """
    fig, ax = _fmt(ax=ax)
    computed = np.asarray(computed_hz, dtype=float).ravel() / 1e6
    analytic = None if analytic_hz is None else np.asarray(analytic_hz, float).ravel() / 1e6
    if computed.size == 0:
        raise ValueError("plot_spectrum needs at least one computed frequency")

    modes = np.arange(computed.size)
    if analytic is None:
        base = np.full(computed.size,
                      computed.min() - 0.05 * max(float(np.ptp(computed)), 1e-9))
        err = np.zeros(computed.size)
    else:
        if analytic.size < computed.size:
            raise ValueError(
                f"need at least {computed.size} analytic modes, got {analytic.size}")
        analytic = analytic[: computed.size]
        base = analytic
        err = computed / analytic - 1.0
        for f in np.unique(analytic):
            ax.axvline(f, ls="--", lw=0.6, color=COL_MUTED, zorder=0)

    ax.hlines(modes, np.minimum(base, computed), np.maximum(base, computed),
              color=COL_PRIMARY, lw=1.0, zorder=2)
    ax.plot(computed, modes, "o", ms=4.2, color=COL_PRIMARY, zorder=3,
            label="FIT (computed)")
    if analytic is not None:
        ax.plot([], [], ls="--", lw=0.6, color=COL_MUTED, label="analytic $f_{mnp}$")
    for i, (f, e) in enumerate(zip(computed, err)):
        if analytic is not None:
            ax.annotate(f"{100.0 * e:+.2f} %", (f, i), xytext=(7, 0),
                        textcoords="offset points", va="center",
                        fontsize=7.5, color=COL_ACCENT)

    ax.set_xlabel("frequency [MHz]")
    ax.set_ylabel("mode index")
    ax.set_yticks(modes)
    ax.set_ylim(-0.7, computed.size - 0.3)
    ax.set_title(title or "PEC cavity spectrum")
    ax.legend(loc="lower right")
    return fig, ax


# ---------------------------------------------------------------------------
def _co_locate(a: np.ndarray, axis: int) -> np.ndarray:
    """Average adjacent entries along ``axis`` (node pair -> cell centre)."""
    lo = [slice(None)] * a.ndim
    hi = [slice(None)] * a.ndim
    lo[axis] = slice(0, -1)
    hi[axis] = slice(1, None)
    return 0.5 * (a[tuple(lo)] + a[tuple(hi)])


def plot_field_slice(grid, values, component, axis="z", index=None, ax=None,
                     cmap="RdBu_r", title=None):
    """Colour map of one electric-field component on a grid-aligned slice.

    ``values`` is the **full** concatenated primal edge-voltage vector (length
    ``cc.n_edges``, i.e. ``[EX, EY, EZ]`` in the block order of
    :class:`emfit.operators.CellComplex`).  The requested component is
    re-assembled from its block, co-located onto the cell centres of the slice
    (transverse node pairs are averaged; the edge voltage is divided by the
    cell width along its own axis so the map is in V/m) and drawn with
    ``pcolormesh`` through cell ``index`` along ``axis``.  The PEC boundary is
    overlaid as a solid box outline.

    Args:
        grid: :class:`emfit.grid.Grid` used to build the cell complex.
        values: Full edge-vector array of length ``cc.n_edges``.
        component: ``'EX'``, ``'EY'``, ``'EZ'`` or ``'magnitude'``.
        axis: Slice normal, ``'x'``, ``'y'`` or ``'z'``.
        index: Cell index along ``axis``; defaults to the middle cell.
        ax: Axes to draw on; a new figure is made when omitted.
        cmap: Matplotlib colormap (diverging for signed components).
        title: Optional axes title.

    Returns:
        ``(fig, ax)``.
    """
    cc = CellComplex(grid)
    vals = np.asarray(values, dtype=float).ravel()
    if vals.size != cc.n_edges:
        raise ValueError(
            f"values must have {cc.n_edges} entries (one per primal edge), "
            f"got {vals.size}")
    axis = str(axis).strip().lower()
    if axis not in ("x", "y", "z"):
        raise ValueError(f"axis must be 'x', 'y' or 'z', got {axis!r}")
    comp = str(component).strip().upper()
    if comp not in ("EX", "EY", "EZ", "MAGNITUDE"):
        raise ValueError(f"component must be EX, EY, EZ or magnitude, got {component!r}")

    blocks = {"EX": cc.off_ex, "EY": cc.off_ey, "EZ": cc.off_ez}
    wanted = ("EX", "EY", "EZ") if comp == "MAGNITUDE" else (comp,)
    fields = {}
    for name in wanted:
        par = name[1].lower()
        a = vals[blocks[name]: blocks[name] + int(np.prod(grid.edge_shape(par)))]
        a = a.reshape(grid.edge_shape(par))
        for d, ax_name in enumerate("xyz"):
            if ax_name != par:                       # node pair -> cell centre
                a = _co_locate(a, d)
        widths = np.asarray(grid.widths(par), dtype=float)
        shaper = [1, 1, 1]
        shaper["xyz".index(par)] = widths.size
        fields[name] = a / widths.reshape(shaper)    # V -> V/m

    if comp == "MAGNITUDE":
        data3 = np.sqrt(sum(f ** 2 for f in fields.values()))
        label = r"$|\mathbf{E}|$ [V/m]"
        signed = False
    else:
        data3 = fields[comp]
        label = rf"$E_{{{comp[1].lower()}}}$ [V/m]"
        signed = True

    d = "xyz".index(axis)
    n_along = int(grid.shape[d])
    k = n_along // 2 if index is None else int(index)
    if not 0 <= k < n_along:
        raise ValueError(
            f"index {k} out of range for axis {axis!r} with {n_along} cells")
    data = np.take(data3, k, axis=d)                 # remaining axes (u, v)
    u, v = [name for name in "xyz" if name != axis]

    fig, ax = _fmt(ax=ax)
    ue = np.asarray(getattr(grid, u), dtype=float)
    ve = np.asarray(getattr(grid, v), dtype=float)
    amp = float(np.max(np.abs(data))) or 1.0
    kw = {"vmin": -amp, "vmax": amp} if signed else {"vmin": 0.0, "vmax": amp}
    mesh = ax.pcolormesh(ue, ve, data.T, shading="flat", cmap=cmap, **kw)
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label(label)

    ax.plot([ue[0], ue[-1], ue[-1], ue[0], ue[0]],
            [ve[0], ve[0], ve[-1], ve[-1], ve[0]], color=COL_INK, lw=0.9)
    ax.set_xlabel(f"${u}$ [m]")
    ax.set_ylabel(f"${v}$ [m]")
    ax.set_aspect("equal")
    coord = 0.5 * (np.asarray(getattr(grid, axis), float)[k]
                   + np.asarray(getattr(grid, axis), float)[k + 1])
    ax.set_title(title or f"{comp} slice at ${axis} = {coord:.3f}$ m")
    return fig, ax


# ---------------------------------------------------------------------------
def plot_energy(t, energies, ax=None, title=None):
    """Energy history together with its relative drift.

    The upper panel shows ``U(t)`` in joules; the lower panel (or a twin axis
    when ``ax`` is supplied) shows ``(U(t) - U(0)) / U(0)`` and annotates the
    maximum absolute drift in scientific notation, i.e. the discrete
    conservation quality of the leapfrog scheme.

    Args:
        t: Time samples [s].
        energies: Energy samples [J], same length as ``t``.
        ax: Axes for the energy panel; a new two-panel figure is made when
            omitted, otherwise the drift is drawn on a twin axis.
        title: Optional title for the energy panel.

    Returns:
        ``(fig, ax)`` with ``ax`` the energy panel.
    """
    t = np.asarray(t, dtype=float).ravel()
    u = np.asarray(energies, dtype=float).ravel()
    if t.size != u.size:
        raise ValueError(f"t and energies differ in length: {t.size} vs {u.size}")
    if t.size < 2:
        raise ValueError("need at least two samples to plot an energy history")

    if ax is None:
        fig, (ax_e, ax_d) = plt.subplots(2, 1, sharex=True,
                                         gridspec_kw={"height_ratios": [2, 1]})
    else:
        fig = ax.figure
        ax_e = ax
        ax_d = ax.twinx()

    ax_e.plot(t * 1e9, u, color=COL_PRIMARY, lw=1.0)
    ax_e.set_ylabel("$U$ [J]")
    ax_e.set_title(title or "leapfrog energy history")
    ax_e.set_ylim(bottom=0.0)

    scale = u[0] if abs(u[0]) > 0.0 else max(float(np.max(np.abs(u))), 1e-300)
    drift = (u - u[0]) / scale
    ax_d.plot(t * 1e9, drift, color=COL_ACCENT, lw=0.8)
    ax_d.axhline(0.0, color=COL_MUTED, lw=0.5, ls=":")
    peak = float(np.max(np.abs(drift))) if drift.size else 0.0
    ax_d.annotate(rf"max $|\Delta U/U| = {peak:.2e}$",
                  xy=(0.02, 0.92), xycoords="axes fraction",
                  fontsize=8, color=COL_ACCENT)
    ax_d.set_ylabel(r"$\Delta U/U$")
    ax_d.set_xlabel("time [ns]")
    return fig, ax_e
