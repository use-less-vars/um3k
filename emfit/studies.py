"""Named, parameterised solver runs -- the catalogue behind every front end.

A *study* is a fixed experiment (a geometry, a physical question) with a small
set of knobs.  Three things live here and nothing else:

* :class:`Param` / :class:`Study` -- the declaration of a study: what it is
  called, what it does, which knobs it has and what types they have.
* :func:`coerce` -- **the** single place where raw strings coming from a CLI
  flag or an HTML form become typed values.  Every front end calls it, so a
  study cannot be driven into an invalid state by one entry point but not the
  other.
* :class:`FigureSink` -- where a run puts its figures, as PNG bytes.  A study
  never touches the filesystem; the CLI writes the sink out, the web UI embeds
  it.

Typical use::

    from emfit import studies

    study = studies.get("cavity")
    sink = studies.FigureSink()
    metrics = study.run(studies.coerce(study, {"nx": "6", "nsteps": "300"}), sink)

``metrics`` is a ``dict[str, str]`` of already-formatted human-readable values
(units included); ``sink.figures`` is a list of ``{slug, title, png, caption}``.

Grid caps
---------
``cavity``'s and ``modes``' ``nx, ny, nz`` are capped at 14 x 10 x 7 because the eigensolver
in :mod:`emfit.eigen` is a *dense* one restricted to
``max_dense = 3000`` free edges: that box already needs 2355 of them, and one
more cell in any direction crosses the limit and raises
``NotImplementedError`` instead of returning a spectrum.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import numpy as np

from . import viz  # selects the Agg backend before pyplot is imported anywhere
from .abc import Mur1Boundary
from .eigen import analytic_box_modes, resonances
from .evolve import FITStepper, RickerSource, cfl_dt
from .grid import Grid
from .materials import C0, material_matrices
from .operators import CellComplex

import matplotlib.pyplot as plt  # noqa: E402  (after the backend is fixed)

__all__ = ["Param", "Study", "FigureSink", "STUDIES", "coerce", "get"]

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

KINDS = ("int", "float", "choice", "bool")
"""Accepted values of :attr:`Param.kind`."""


# ---------------------------------------------------------------------------
# declaration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Param:
    """One knob of a study.

    Args:
        key: Identifier used by ``--set key=value`` and by the form field name.
        label: Short human label for the UI.
        kind: ``'int'``, ``'float'``, ``'choice'`` or ``'bool'``.
        default: Value used when the front end does not supply one.
        choices: Allowed values, required for ``kind='choice'``.
        lo: Lower bound (inclusive) for numeric kinds; ``None`` = unbounded.
        hi: Upper bound (inclusive) for numeric kinds; ``None`` = unbounded.
        unit: Unit shown next to the value, e.g. ``'MHz'``.
        help: One sentence of explanation, shown under the form field.
    """

    key: str
    label: str
    kind: str
    default: Any
    choices: tuple = ()
    lo: float = None
    hi: float = None
    unit: str = ""
    help: str = ""

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(
                f"param {self.key!r}: kind must be one of {', '.join(KINDS)}, "
                f"got {self.kind!r}")
        if self.kind == "choice":
            if not self.choices:
                raise ValueError(f"param {self.key!r}: a choice needs choices")
            if self.default not in self.choices:
                raise ValueError(
                    f"param {self.key!r}: default {self.default!r} is not one of "
                    f"{', '.join(map(str, self.choices))}")
        if self.kind in ("int", "float"):
            if self.lo is not None and self.default < self.lo:
                raise ValueError(f"param {self.key!r}: default below lo")
            if self.hi is not None and self.default > self.hi:
                raise ValueError(f"param {self.key!r}: default above hi")

    def __str__(self):  # pragma: no cover - cosmetic
        unit = f" {self.unit}" if self.unit else ""
        if self.kind == "choice":
            span = "|".join(map(str, self.choices))
        elif self.kind == "bool":
            span = "true|false"
        else:
            span = f"{self.lo if self.lo is not None else '-'}.." \
                   f"{self.hi if self.hi is not None else '-'}"
        return f"{self.key}={self.default}{unit} ({self.kind}: {span})"


class FigureSink:
    """Collects the figures of one run as PNG bytes (no filesystem involved).

    A study calls :meth:`add` (or renders straight into the sink with
    :meth:`add_figure`); the caller decides what to do with the images.
    """

    def __init__(self) -> None:
        self._figures: list[dict] = []

    # -- filling ------------------------------------------------------------
    def add(self, slug: str, title: str, png: bytes, caption: str = "") -> None:
        """Append one figure; ``slug`` is its identifier inside the run."""
        data = bytes(png)
        if not data.startswith(PNG_MAGIC):
            raise ValueError(f"figure {slug!r}: not PNG data")
        self._figures.append(
            {"slug": str(slug), "title": str(title), "png": data,
             "caption": str(caption)})

    def add_figure(self, slug: str, title: str, fig, caption: str = "",
                   dpi: int = 140) -> None:
        """Render ``fig`` through :func:`emfit.viz.png_bytes` and append it."""
        self.add(slug, title, viz.png_bytes(fig, dpi=dpi), caption=caption)

    # -- reading ------------------------------------------------------------
    @property
    def figures(self) -> list[dict]:
        """The collected figures as ``{slug, title, png, caption}`` dicts."""
        return [dict(f) for f in self._figures]

    def slugs(self) -> list[str]:
        return [f["slug"] for f in self._figures]

    def __len__(self) -> int:
        return len(self._figures)

    def __iter__(self):
        return iter(self._figures)

    def __getitem__(self, index):
        return self._figures[index]

    def __repr__(self):  # pragma: no cover - cosmetic
        return f"FigureSink({', '.join(self.slugs()) or 'empty'})"

    # -- persistence --------------------------------------------------------
    def save_to(self, directory) -> list[str]:
        """Write every figure as ``<slug>.png`` under ``directory``."""
        directory = os.fspath(directory)
        os.makedirs(directory, exist_ok=True)
        paths = []
        for fig in self._figures:
            path = os.path.join(directory, f"{fig['slug']}.png")
            with open(path, "wb") as handle:
                handle.write(fig["png"])
            paths.append(path)
        return paths


@dataclass(frozen=True)
class Study:
    """A named experiment: what it is, its knobs, and how to run it.

    ``run`` is a plain function ``(values, sink) -> metrics``; ``values`` is
    already typed and validated by :func:`coerce`, and every metric value is a
    non-empty, already-formatted string so that both front ends can print it
    without knowing anything about units.
    """

    name: str
    title: str
    blurb: str
    params: tuple
    run: Callable[[Mapping[str, Any], FigureSink], dict]

    def param(self, key: str) -> Param:
        for p in self.params:
            if p.key == key:
                return p
        raise ValueError(
            f"{self.name}: unknown parameter {key!r}; "
            f"valid: {', '.join(p.key for p in self.params)}")

    def defaults(self) -> dict:
        return {p.key: p.default for p in self.params}


# ---------------------------------------------------------------------------
# the one validation / coercion path
# ---------------------------------------------------------------------------
def _coerce_one(param: Param, value):
    """Turn one raw value into ``param``'s type; raises ``ValueError``."""
    if param.kind == "bool":
        if isinstance(value, str):
            low = value.strip().lower()
            if low in ("true", "yes", "on", "1"):
                return True
            if low in ("false", "no", "off", "0", ""):
                return False
            raise ValueError(
                f"{param.key}: expected a boolean "
                f"(true/false, yes/no, on/off, 1/0), got {value!r}")
        return bool(value)

    if value is None or (isinstance(value, str) and not value.strip()):
        return param.default                     # untouched form field

    if param.kind == "choice":
        candidate = str(value).strip()
        if candidate not in param.choices:
            raise ValueError(
                f"{param.key}: {candidate!r} is not one of "
                f"{', '.join(map(str, param.choices))}")
        return candidate

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{param.key}: expected a number, got {value!r}") from None
    if not np.isfinite(number):
        raise ValueError(f"{param.key}: expected a finite number, got {value!r}")
    if param.kind == "int":
        rounded = int(round(number))
        if abs(number - rounded) > 1e-9:
            raise ValueError(
                f"{param.key}: expected a whole number, got {value!r}")
        number = rounded

    unit = f" {param.unit}" if param.unit else ""
    if param.lo is not None and number < param.lo:
        raise ValueError(
            f"{param.key}: {number}{unit} is below the minimum {param.lo}{unit}")
    if param.hi is not None and number > param.hi:
        raise ValueError(
            f"{param.key}: {number}{unit} is above the maximum {param.hi}{unit}")
    return number


def coerce(study: Study, submitted: Mapping[str, Any] = None) -> dict:
    """Validate and type the submitted values of ``study``.

    This is the **only** place where strings become values; the CLI and the web
    UI both hand their raw input to it and use the result unchanged.

    Behaviour, in full:

    * unknown keys are rejected with a message naming the valid keys;
    * missing keys take :attr:`Param.default` (an empty or whitespace-only
      string counts as missing -- that is what an untouched form field sends);
    * ``choice`` values must be one of :attr:`Param.choices`;
    * ``bool`` accepts ``true/false``, ``yes/no``, ``on/off``, ``1/0``;
    * ``int`` accepts ``'10'`` and ``10`` alike and rejects ``'10.5'``;
    * out-of-range numerics are **rejected**, not clamped: silently turning a
      request for 40 cells into 14 would hide a mistake, so the error names the
      bound instead.

    Args:
        study: The study whose parameters are being filled.
        submitted: Raw ``key -> value`` mapping (or ``None`` for all defaults).

    Returns:
        A new dict with exactly the study's keys, each of the declared type.

    Raises:
        ValueError: On an unknown key, a bad value or an out-of-range number.
    """
    raw = {str(k): v for k, v in dict(submitted or {}).items()}
    known = {p.key: p for p in study.params}

    unknown = sorted(set(raw) - set(known))
    if unknown:
        raise ValueError(
            f"{study.name}: unknown parameter(s) {', '.join(unknown)}; "
            f"valid: {', '.join(known)}")

    values = {}
    for key, param in known.items():
        value = raw.get(key, param.default)
        if isinstance(value, (list, tuple)):      # repeated form field
            value = value[-1] if value else param.default
        values[key] = _coerce_one(param, value)
    return values


# ---------------------------------------------------------------------------
# study 1: PEC cavity (resonances, snapshot, energy conservation)
# ---------------------------------------------------------------------------
CAVITY_LX, CAVITY_LY, CAVITY_LZ = 1.0, 0.7, 0.5      # metres
CAVITY_NMODES = 6


def _run_cavity(values: Mapping[str, Any], sink: FigureSink) -> dict:
    """Eigenmodes + ring-down of a closed rectangular PEC box."""
    nx, ny, nz = int(values["nx"]), int(values["ny"]), int(values["nz"])
    fmax = float(values["fmax"]) * 1e6
    nsteps = int(values["nsteps"])
    n_warm = max(1, nsteps // 6)
    n_rec = max(1, nsteps - n_warm)

    grid = Grid.uniform(nx, ny, nz, CAVITY_LX, CAVITY_LY, CAVITY_LZ)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)

    # --- resonances ------------------------------------------------------
    result = resonances(grid, cc, m_eps, m_mu, k=CAVITY_NMODES)
    fit = np.asarray(result.freqs, dtype=float)
    if fit.size == 0:
        raise RuntimeError(
            "no physical mode survived the filters on this grid; "
            "use more cells per direction")
    exact = analytic_box_modes(CAVITY_LX, CAVITY_LY, CAVITY_LZ, count=fit.size)

    box = f"{CAVITY_LX:g} x {CAVITY_LY:g} x {CAVITY_LZ:g} m, {nx}x{ny}x{nz} cells"
    fig, _ = viz.plot_spectrum(fit, exact, title=f"PEC cavity {box}")
    sink.add_figure(
        "spectrum", "Resonances against the analytic box spectrum", fig,
        caption=(f"Stems run from the analytic <i>f<sub>mnp</sub></i> to the FIT "
                 f"eigenvalue; the annotation is the relative error. "
                 f"{fit.size} lowest modes, mean |error| "
                 f"{100 * np.mean(np.abs(fit / exact - 1.0)):.2f} %."))

    # --- ring-down -------------------------------------------------------
    dt = cfl_dt(grid)
    stepper = FITStepper(cc, m_eps, m_mu, dt=dt, pec=cc.pec_edge_mask())
    source = RickerSource(cc.n_edges, cc.idx_ez(1, 1, 1), fmax=fmax)
    stepper.run(n_warm, source=source)

    times, energies = [], []
    best = {"norm": -1.0, "e": None, "t": 0.0}

    def record(state):
        times.append(state.time)
        energies.append(state.energy())
        norm = float(np.linalg.norm(state.e))
        if norm > best["norm"]:
            best.update(norm=norm, e=state.e.copy(), t=state.time)

    stepper.run(n_rec, callback=record)
    t = np.asarray(times, dtype=float)
    u = np.asarray(energies, dtype=float)

    fig, _ = viz.plot_field_slice(
        grid, best["e"], "EZ", axis="z",
        title=rf"$E_z$ at $t = {best['t'] * 1e9:.1f}$ ns (mid-plane)")
    sink.add_figure(
        "field-ez", "Mid-plane snapshot of the dominant field component", fig,
        caption=(f"$E_z$ on the mid-plane after {n_warm + n_rec} leapfrog steps, "
                 f"taken at the instant of largest field norm. The box outline "
                 f"is the PEC wall."))

    fig, _ = viz.plot_energy(t, u, title="lossless ring-down: energy and drift")
    sink.add_figure(
        "energy-drift", "Energy history and its relative drift", fig,
        caption=("A lossless cavity must conserve energy exactly; the lower "
                 "panel is the discrete conservation error of the scheme."))

    # --- metrics ---------------------------------------------------------
    rel = fit / exact - 1.0
    worst = int(np.argmax(np.abs(rel)))
    scale = u[0] if abs(u[0]) > 0.0 else max(float(np.max(np.abs(u))), 1e-300)
    peak_drift = float(np.max(np.abs((u - u[0]) / scale)))
    return {
        "modes found": f"{fit.size}",
        "mean |rel. error|": f"{100 * float(np.mean(np.abs(rel))):.3f} %",
        "worst mode error": (f"{100 * abs(float(rel[worst])):.3f} % "
                             f"(mode {worst}, {fit[worst] / 1e6:.3f} MHz vs "
                             f"{exact[worst] / 1e6:.3f} MHz)"),
        "time step dt": f"{dt:.4e} s",
        "simulated time": f"{t[-1] * 1e9:.2f} ns",
        "max relative energy drift": f"{peak_drift:.2e}",
        "free / total edges": f"{result.n_free} of {result.n_edges}",
        "rejected eigenvalues": (
            f"{result.n_rejected_static} static, "
            f"{result.n_rejected_nonphysical} non-physical"),
    }


# ---------------------------------------------------------------------------
# study 2: cavity mode shapes (one panel per eigenmode)
# ---------------------------------------------------------------------------
def _run_modes(values: Mapping[str, Any], sink: FigureSink) -> dict:
    """Gallery of the lowest cavity modes, one panel per mode.

    Every panel is the same quantity -- ``|E|`` on the mid-plane -- so the
    pictures can be compared mode by mode, but each mode is normalised to its
    own peak (a global scale would leave the higher modes invisible).  The
    panels therefore share one colour scale, ``|E| / max|E|`` of that mode, and
    one figure-level colour bar instead of six per-panel bars.
    """
    nx, ny, nz = int(values["nx"]), int(values["ny"]), int(values["nz"])
    nmodes = int(values["nmodes"])

    grid = Grid.uniform(nx, ny, nz, CAVITY_LX, CAVITY_LY, CAVITY_LZ)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)

    result = resonances(grid, cc, m_eps, m_mu, k=nmodes)
    fit = np.asarray(result.freqs, dtype=float)
    if fit.size == 0:
        raise RuntimeError(
            "no physical mode survived the filters on this grid; "
            "use more cells per direction")
    drawn = int(fit.size)

    ncols = min(3, drawn)
    nrows = -(-drawn // ncols)                       # ceil
    fig, axes = plt.subplots(nrows, ncols, squeeze=False,
                             figsize=(3.2 * ncols, 2.6 * nrows),
                             constrained_layout=True)
    panels = axes.ravel()
    mesh = None
    for i in range(drawn):
        _, ax = viz.plot_field_slice(
            grid, result.vectors[:, i], "MAGNITUDE", axis="z", ax=panels[i],
            cmap="viridis", colorbar=False,
            title=f"mode {i + 1}: {fit[i] / 1e6:.1f} MHz")
        mesh = ax.collections[0]
        data = np.asarray(mesh.get_array(), dtype=float)
        peak = float(np.max(np.abs(data))) or 1.0     # per-panel normalisation
        mesh.set_array(data / peak)
        mesh.set_clim(0.0, 1.0)
    for ax in panels[drawn:]:
        ax.axis("off")

    fig.colorbar(mesh, ax=panels.tolist(), shrink=0.9,
                 label=r"$|\mathbf{E}|$ / peak of the panel")
    fig.suptitle(
        f"PEC cavity {CAVITY_LX:g} x {CAVITY_LY:g} x {CAVITY_LZ:g} m, "
        f"{nx}x{ny}x{nz} cells: $|\\mathbf{{E}}|$ on the mid-$z$ plane",
        fontsize=10)
    sink.add_figure(
        "mode-shapes", "Mid-plane |E| of the lowest cavity modes", fig,
        caption=(f"One panel per FIT eigenmode, |E| on the mid-z slice. Each "
                 f"panel is normalised to its own peak, so the shared colour "
                 f"bar reads 0 to 1 in units of that mode; the title of a panel "
                 f"is the frequency the eigensolver returned for it."))

    rel = fit / analytic_box_modes(CAVITY_LX, CAVITY_LY, CAVITY_LZ, count=drawn) - 1.0
    metrics = {
        "modes drawn": f"{drawn} of {nmodes}",
        "frequencies": ", ".join(f"{f / 1e6:.2f}" for f in fit) + " MHz",
        "mean |rel. error|": f"{100 * float(np.mean(np.abs(rel))):.3f} %",
        "worst mode error": (f"{100 * float(np.max(np.abs(rel))):.3f} % "
                             f"(mode {int(np.argmax(np.abs(rel))) + 1})"),
    }
    if drawn < nmodes:
        metrics["truncation"] = (
            f"only {drawn} of the {nmodes} requested modes came back; the "
            f"filter that drops static and non-physical eigenvalues removed "
            f"the rest -- use a finer grid for more modes")
    return metrics


# ---------------------------------------------------------------------------
# study 3: absorbing duct termination (Mur vs PEC)
# ---------------------------------------------------------------------------
DUCT_LX, DUCT_LY, DUCT_LZ = 2.4, 0.64, 0.04          # metres
DUCT_SRC_X, DUCT_PRB_X = 0.5 * DUCT_LX, 0.375 * DUCT_LX
DUCT_F0, DUCT_T0, DUCT_TAU = 2.0e9, 3.0e-9, 0.8e-9
DUCT_SIDE_WALLS = ("ymin", "ymax", "zmin", "zmax")
DUCT_ABC_PLANES = ("xmin", "xmax")
DUCT_THRESHOLD_DB = -40.0


def _duct_waveform(t: float) -> float:
    s = (t - DUCT_T0) / DUCT_TAU
    return float(np.sin(2.0 * np.pi * DUCT_F0 * (t - DUCT_T0)) * np.exp(-s * s))


def _duct_peak(trace, t, t_expected, half_window):
    """Largest ``|trace|`` within ``half_window`` of the expected arrival."""
    sel = np.flatnonzero(np.abs(t - t_expected) <= half_window)
    if sel.size == 0:
        sel = np.arange(t.size)
    k = int(sel[int(np.argmax(np.abs(trace[sel])))])
    return float(abs(trace[k])), float(t[k])


def _run_duct(values: Mapping[str, Any], sink: FigureSink) -> dict:
    """Pulse in a PEC duct, with either a Mur ABC or a reflecting wall."""
    nx, ny = int(values["nx"]), int(values["ny"])
    nsteps = int(values["nsteps"])
    termination = str(values["termination"])
    absorbing = termination == "mur"

    grid = Grid.uniform(nx, ny, 1, DUCT_LX, DUCT_LY, DUCT_LZ)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)

    walls = DUCT_SIDE_WALLS if absorbing else DUCT_ABC_PLANES + DUCT_SIDE_WALLS
    stepper = FITStepper(cc, m_eps, m_mu, pec=cc.pec_edge_mask(walls))
    mur = (Mur1Boundary(grid, stepper.dt, cc=cc, planes=DUCT_ABC_PLANES,
                        pec=stepper.pec_idx) if absorbing else None)

    dx = DUCT_LX / nx
    i_src = int(round(DUCT_SRC_X / dx))
    i_prb = int(round(DUCT_PRB_X / dx))
    profile = np.sin(np.pi * np.arange(ny + 1) / ny)
    src = np.array([cc.idx_ez(i_src, j, 0) for j in range(ny + 1)], dtype=np.intp)
    probe = int(cc.idx_ez(i_prb, ny // 2, 0))

    current = np.zeros_like(stepper.e)
    trace = np.empty(nsteps)
    for n in range(nsteps):
        current[:] = 0.0
        current[src] = profile * _duct_waveform(stepper.time)
        e_prev = stepper.e.copy()
        stepper.step(current)
        if mur is not None:
            mur.apply(stepper.e, e_prev)     # pre-step field = correct level
        trace[n] = stepper.e[probe]

    t = stepper.dt * np.arange(1, nsteps + 1)
    omega = 2.0 * np.pi * DUCT_F0
    kx = np.sqrt((omega / C0) ** 2 - (np.pi / DUCT_LY) ** 2)
    v_ph = omega / kx
    t_inc = DUCT_T0 + (DUCT_SRC_X - DUCT_PRB_X) / v_ph
    t_near = DUCT_T0 + (DUCT_SRC_X + DUCT_PRB_X) / v_ph
    t_far = DUCT_T0 + (2 * DUCT_LX - DUCT_SRC_X - DUCT_PRB_X) / v_ph

    inc, _ = _duct_peak(trace, t, t_inc, 1.0e-9)
    near, t_near_meas = _duct_peak(trace, t, t_near, 1.2e-9)
    far, t_far_meas = _duct_peak(trace, t, t_far, 1.2e-9)
    db_near = 20.0 * np.log10(max(near, 1e-30) / max(inc, 1e-30))
    db_far = 20.0 * np.log10(max(far, 1e-30) / max(inc, 1e-30))
    theory_db = 20.0 * np.log10(abs((v_ph - C0) / (v_ph + C0)))

    # --- figure: linear trace and the same trace in dB --------------------
    fig, (ax_t, ax_db) = plt.subplots(1, 2, figsize=(9.2, 3.2))
    colour = viz.COL_PRIMARY if absorbing else viz.COL_ACCENT
    label = "Mur ABC" if absorbing else "PEC (reflecting)"
    ax_t.plot(t * 1e9, trace, color=colour, lw=1.0, label=label)
    for t_expected, name in ((t_inc, "incident"), (t_near, "echo @ probe"),
                             (t_far, "echo @ source")):
        ax_t.axvline(t_expected * 1e9, color=viz.COL_MUTED, lw=0.6, ls="--")
        ax_t.annotate(f"{name}\n{t_expected * 1e9:.1f} ns",
                      xy=(t_expected * 1e9, 1.0), xycoords=("data", "axes fraction"),
                      xytext=(2, -6), textcoords="offset points",
                      rotation=90, va="top", fontsize=6.5, color=viz.COL_MUTED)
    ax_t.set_xlabel("time [ns]")
    ax_t.set_ylabel("probe $E_z$ [V]")
    ax_t.set_title(f"probe trace, {label}")
    ax_t.legend(loc="upper right")

    floor = 1e-7 * max(inc, 1e-30)
    ax_db.plot(t * 1e9, 20.0 * np.log10(np.maximum(np.abs(trace), floor) / max(inc, 1e-30)),
               color=colour, lw=0.9, label=label)
    ax_db.axhline(DUCT_THRESHOLD_DB, color=viz.COL_ACCENT, lw=0.6, ls=":")
    ax_db.annotate(f"{DUCT_THRESHOLD_DB:.0f} dB", xy=(0.02, DUCT_THRESHOLD_DB + 2.0),
                   fontsize=7, color=viz.COL_ACCENT)
    ax_db.set_xlabel("time [ns]")
    ax_db.set_ylabel("$|E_z| / |E_z^{inc}|$ [dB]")
    ax_db.set_ylim(-80.0, 10.0)
    ax_db.set_title(f"same trace in dB ({label})")
    sink.add_figure(
        "probe-trace", f"Duct probe trace, far end: {label}", fig,
        caption=(f"Source at x = {DUCT_SRC_X:.2f} m, probe at "
                 f"{DUCT_PRB_X:.2f} m, {nx}x{ny} cells, {nsteps} steps. The "
                 f"dashed markers are the analytically predicted arrival times "
                 f"of the incident pulse and of the two end reflections."))

    return {
        "far-end termination": label,
        "echo level, near end": f"{db_near:.2f} dB",
        "echo level, far end": f"{db_far:.2f} dB",
        "theory: Mur reflection": f"{theory_db:.2f} dB",
        "echo / incident, far end": f"{far / inc:.4f}",
        "incident peak": f"{inc:.3f} V",
        "phase velocity": f"{v_ph / C0:.5f} c",
        "echo arrival, near / far": f"{t_near_meas * 1e9:.2f} / "
                                    f"{t_far_meas * 1e9:.2f} ns",
        "time step dt": f"{stepper.dt:.4e} s",
    }


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------
CAVITY = Study(
    name="cavity",
    title="PEC cavity: resonances, snapshot, energy",
    blurb=("A closed rectangular box. Solves the generalised eigenproblem for "
           "the lowest modes and compares them with f_mnp = (c/2)|(m/a, n/b, p/d)|, "
           "then rings the cavity down with a Ricker pulse and checks that the "
           "leapfrog scheme conserves energy. Three figures: spectrum, mid-plane "
           "E_z and the energy drift."),
    params=(
        Param("nx", "cells along x", "int", 10, lo=4, hi=14,
              help="More cells resolve the modes better; the dense eigensolver "
                   "cost grows steeply (3000 free edges is the hard limit)."),
        Param("ny", "cells along y", "int", 7, lo=4, hi=10),
        Param("nz", "cells along z", "int", 5, lo=3, hi=7),
        Param("fmax", "drive band", "float", 400.0, lo=100.0, hi=1000.0,
              unit="MHz",
              help="Upper frequency of the Ricker pulse that excites the box."),
        Param("nsteps", "leapfrog steps", "int", 1800, lo=200, hi=4000,
              help="Time-domain steps after the eigenproblem; the first sixth "
                   "is driven, the rest is free ring-down."),
    ),
    run=_run_cavity,
)

MODES = Study(
    name="modes",
    title="PEC cavity: mode shapes",
    blurb=("The same closed box as 'cavity', but pictured instead of tabulated: "
           "one panel per eigenmode, |E| on the mid-plane, each titled with the "
           "frequency the eigensolver returned. Panels are normalised to their "
           "own peak so that higher modes stay visible; one bar is shared."),
    params=(
        Param("nx", "cells along x", "int", 8, lo=4, hi=14,
              help="More cells resolve the mode pattern better; the dense "
                   "eigensolver cost grows steeply (3000 free edges is the "
                   "hard limit)."),
        Param("ny", "cells along y", "int", 6, lo=4, hi=10),
        Param("nz", "cells along z", "int", 4, lo=3, hi=7),
        Param("nmodes", "modes to draw", "int", 6, lo=1, hi=12,
              help="How many of the lowest modes to solve for and draw; the "
                   "grid may return fewer and say so."),
    ),
    run=_run_modes,
)

DUCT = Study(
    name="duct",
    title="Absorbing duct termination: Mur vs PEC",
    blurb=("A pulse launched into a PEC waveguide, measured at a probe near the "
           "source. With the first-order Mur condition at the two ends of the "
           "duct the outgoing pulse is absorbed (-49 dB, matching the analytic "
           "reflection coefficient); with a plain PEC wall it comes back almost "
           "undamped. Switch the termination to see the difference."),
    params=(
        Param("nx", "cells along the duct", "int", 320, lo=64, hi=400,
              help="Axial resolution; the duct is 2.4 m long."),
        Param("ny", "cells across the duct", "int", 16, lo=8, hi=32),
        Param("nsteps", "time steps", "int", 900, lo=200, hi=2000,
              help="Enough steps must be taken for the echo to reach the probe "
                   "(about 10 ns after the incident pulse)."),
        Param("termination", "far-end termination", "choice", "mur",
              choices=("mur", "pec"),
              help="'mur' absorbs the outgoing pulse, 'pec' reflects it so the "
                   "reflection is visible."),
    ),
    run=_run_duct,
)

STUDIES: dict = {study.name: study for study in (CAVITY, MODES, DUCT)}
"""Registry of every study, keyed by :attr:`Study.name`."""


def get(name: str) -> Study:
    """Look up a study by name.

    Raises:
        ValueError: If ``name`` is not registered, listing the valid names.
    """
    key = str(name).strip().lower()
    if key not in STUDIES:
        raise ValueError(
            f"unknown study {name!r}; available: {', '.join(sorted(STUDIES))}")
    return STUDIES[key]
