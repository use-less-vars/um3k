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
import tempfile
import time
import warnings
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

import numpy as np

from . import nearfield
from . import scatter
from . import viz  # selects the Agg backend before pyplot is imported anywhere
from .abc import Mur1Boundary
from .board import Load, MicrostripBoard
from .eigen import analytic_box_modes, resonances
from .evolve import FITStepper, RickerSource, cfl_dt, ricker
from .grid import Grid
from .kicad import load_board
from .materials import C0, material_matrices
from .microstrip import Microstrip
from .operators import CellComplex
from .pml import PML, AbsorbedWork, cells_for_wavelength
from .ports import (
    DftAccumulator,
    LineFit,
    LumpedPort,
    StationFit,
    column_path,
    deembed_reflection,
    deembed_transmission,
    edge_path_voltage,
    fit_beta,
    fit_line,
    fit_station_impedance,
    plate_current,
    power_current_check,
    sigma_beta_from_curvature,
)

import matplotlib.pyplot as plt  # noqa: E402  (after the backend is fixed)

__all__ = [
    "Param",
    "Study",
    "FigureSink",
    "LineReference",
    "MicrostripBoard",
    "MicrostripWave",
    "STUDIES",
    "backward_wave_amplitude",
    "coerce",
    "forward_wave_amplitude",
    "get",
    "line_s21",
    "microstrip_reference_board",
    "microstrip_wave",
    "microstrip_wave_board",
]

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

KINDS = ("int", "float", "choice", "bool", "str")
"""Accepted values of :attr:`Param.kind`."""


NO_LOADED_IMPEDANCE = (
    "n/a: no impedance is quoted on this record -- the only fit that would "
    "supply one averages over stations on both sides of the cut a load makes, "
    "so what it returned would be the load measured as part of the line.  "
    "A load-free run of the same mesh supplies the reference impedance and the "
    "load-free ratio; it does not supply a propagation constant for this "
    "record")
"""Refusal printed in place of a station impedance on a loaded record.  The
magnitude of ``s21`` survives that record; the impedance does not."""

NO_LOADED_BETA = (
    "n/a: no eps_eff is quoted on this record -- it comes from a fitted beta, "
    "and a beta fitted here spans the cut the load makes, so it belongs to the "
    "load and the line together rather than to the line alone.  A load-free "
    "run of the same mesh supplies the reference impedance and the load-free "
    "ratio; it does not supply a beta for this record")
"""Refusal printed in place of ``eps_eff`` on a loaded record."""


# ---------------------------------------------------------------------------
# declaration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Param:
    """One knob of a study.

    Args:
        key: Identifier used by ``--set key=value`` and by the form field name.
        label: Short human label for the UI.
        kind: ``'int'``, ``'float'``, ``'choice'``, ``'bool'`` or ``'str'``.
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
        if self.kind == "str":
            if not isinstance(self.default, str):
                raise ValueError(
                    f"param {self.key!r}: a str param's default must be text, "
                    f"got {self.default!r}")
            if self.choices or self.lo is not None or self.hi is not None:
                raise ValueError(
                    f"param {self.key!r}: a str param is free text, so it "
                    "takes no choices and no bounds")
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
        elif self.kind == "str":
            span = "text"
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
        self._attachments: list[dict] = []

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

    def add_attachment(self, slug: str, filename: str, data: bytes,
                       title: str = "", caption: str = "") -> None:
        """Attach an output that is not a PNG (the ``rcs`` animation).

        The figures themselves are PNG by contract -- both front ends embed
        them as ``<img>`` -- but an animation is a GIF and cannot travel that
        way.  An attachment keeps the same declaration (``slug``, ``title``,
        ``caption``) and adds the file ``filename`` it must be written as, so
        :meth:`save_to` can put it next to the figures and report its path
        without the caller having to know that a study produced one.
        """
        self._attachments.append(
            {"slug": str(slug), "title": str(title), "filename": str(filename),
             "data": bytes(data), "caption": str(caption)})

    # -- reading ------------------------------------------------------------
    @property
    def figures(self) -> list[dict]:
        """The collected figures as ``{slug, title, png, caption}`` dicts."""
        return [dict(f) for f in self._figures]

    @property
    def attachments(self) -> list[dict]:
        """The collected non-PNG outputs as ``{slug, title, filename, data}``."""
        return [dict(a) for a in self._attachments]

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
        """Write every figure as ``<slug>.png`` under ``directory``.

        Attachments are written too, under their own file name, after the
        figures; the returned list is every file written, so a caller that
        just prints it reports the animation as well.
        """
        directory = os.fspath(directory)
        os.makedirs(directory, exist_ok=True)
        paths = []
        for fig in self._figures:
            path = os.path.join(directory, f"{fig['slug']}.png")
            with open(path, "wb") as handle:
                handle.write(fig["png"])
            paths.append(path)
        for attachment in self._attachments:
            path = os.path.join(directory, attachment["filename"])
            with open(path, "wb") as handle:
                handle.write(attachment["data"])
            paths.append(path)
        return paths


def dump_figures(sink, directory="study-out", prefix="fig_g1_") -> list[str]:
    """Write every figure of one run as ``<directory>/<prefix><slug>.png``.

    The study itself never touches the filesystem, so the dump has to live
    somewhere a caller can reach; putting it here means a benchmark run leaves
    its pictures on disk as a side-effect of running instead of needing a
    second script that reproduces the run to get them back.

    A file that already exists is **not** overwritten.  ``study-out`` is shared
    between studies -- the box sweep left ``fig_g1_s21_convergence.png`` there
    -- so a colliding name is skipped and reported rather than silently
    replaced with a different quantity that happens to share a slug.

    Returns the paths actually written, so a caller can print the byte total.
    """
    if sink is None:
        return []
    directory = os.fspath(directory)
    os.makedirs(directory, exist_ok=True)
    paths = []
    for fig in sink.figures:
        path = os.path.join(directory, f"{prefix}{fig['slug']}.png")
        if os.path.exists(path):
            continue
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

    if param.kind == "str":
        return str(value)                       # free text, taken as written

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
    * ``str`` is taken as given: a path or a net name reaches the study
      exactly as it was typed, and an empty string is a legal value (it means
      "nothing named" to a parameter that offers one), so only the
      whitespace-only check above turns one into the default;
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
DUCT_PML_MIN_CELLS, DUCT_PML_MAX_CELLS = 8, 40   # matched-layer clip
DUCT_ABC_PLANES = ("xmin", "xmax")
DUCT_THRESHOLD_DB = -40.0


def _duct_pml_cells(nx: int, f0: float = None, h: float = None) -> int:
    """Matched-layer thickness (cells) for a duct resolved with ``nx`` cells.

    Given the drive frequency and the mesh step, the thickness comes from the
    measured reflection law in :func:`emfit.pml.cells_for_wavelength`, aimed at
    -79 dB -- the level the duct run quotes.  The two clips keep it sane: eight
    cells is the floor that still fits a coarse run, and a quarter of the grid
    is the most the layer may take before the interior is gone.  Without
    ``f0`` and ``h`` the 1/8 rule is used instead.
    """
    if f0 is not None and h is not None:
        cells = cells_for_wavelength(C0 / f0, h, target_db=-79.0)
        return min(max(cells, DUCT_PML_MIN_CELLS), nx // 4)
    return min(DUCT_PML_MAX_CELLS, max(DUCT_PML_MIN_CELLS, nx // 8))


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
    """Pulse in a PEC duct ended by a matched layer, a Mur ABC or a wall."""
    nx, ny = int(values["nx"]), int(values["ny"])
    nsteps = int(values["nsteps"])
    termination = str(values["termination"])
    mur_on = termination == "mur"
    pml_on = termination == "pml"
    absorbing = mur_on or pml_on

    dx = DUCT_LX / nx
    grid = Grid.uniform(nx, ny, 1, DUCT_LX, DUCT_LY, DUCT_LZ)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)

    # The layer sits against the PEC end planes, so the same wall mask serves
    # both absorbing terminations; only the Mur run leaves the ends free.
    walls = DUCT_SIDE_WALLS if mur_on else DUCT_ABC_PLANES + DUCT_SIDE_WALLS
    pml = (PML(grid, thickness_cells=_duct_pml_cells(nx, DUCT_F0, dx), order=2,
               target=1e-4, axes=("x",), cc=cc) if pml_on else None)
    stepper = FITStepper(cc, m_eps, m_mu, pec=cc.pec_edge_mask(walls), pml=pml)
    mur = (Mur1Boundary(grid, stepper.dt, cc=cc, planes=DUCT_ABC_PLANES,
                        pec=stepper.pec_idx) if mur_on else None)

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
    label = {"mur": "Mur ABC", "pml": "PML (matched layer)"}.get(
        termination, "PEC (reflecting)")
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
        "theory: Mur reflection": (f"{theory_db:.2f} dB" if mur_on else
                                   "n/a, no closed form for the layer"),
        "echo / incident, far end": f"{far / inc:.4f}",
        "incident peak": f"{inc:.3f} V",
        "phase velocity": f"{v_ph / C0:.5f} c",
        "echo arrival, near / far": f"{t_near_meas * 1e9:.2f} / "
                                    f"{t_far_meas * 1e9:.2f} ns",
        "time step dt": f"{stepper.dt:.4e} s",
    }


# ---------------------------------------------------------------------------
# study 4: 2-D scattering from a PEC cylinder
# ---------------------------------------------------------------------------
SCATTER_FRAMES = 6              # panels in the sequence figure
SCATTER_SPAN = 1.0              # half-width of the sequence, in wavelengths


def _scatter_vector(cc: CellComplex, ez) -> np.ndarray:
    """Full edge vector holding ``ez`` in the ``Ez`` block, zero elsewhere.

    :func:`emfit.viz.plot_field_slice` wants one value per primal edge, while
    this study only has the ``Ez`` node array: a single cell layer between two
    PEC ``z`` planes leaves ``Ez`` as the only electric component, so the
    padded vector's ``MAGNITUDE`` is ``|Ez|`` exactly rather than approximately.
    """
    vals = np.zeros(cc.n_edges, dtype=float)
    vals[cc.off_ez:cc.off_ez + cc.n_ez] = np.asarray(ez, dtype=float).ravel()
    return vals


def _scatter_overlay(ax, cc: CellComplex, mask, centre, radius: float) -> None:
    """Circle of the ideal scatterer plus the ``Ez`` nodes the PEC pins."""
    theta = np.linspace(0.0, 2.0 * np.pi, 361)
    ax.plot(centre[0] + radius * np.cos(theta), centre[1] + radius * np.sin(theta),
            color=viz.COL_INK, lw=0.9, ls="--")
    ii, jj = np.meshgrid(np.arange(cc.nxn), np.arange(cc.nyn), indexing="ij")
    pinned = np.asarray(mask, dtype=bool)[cc.idx_ez(ii, jj, 0)]
    ax.plot(np.asarray(cc.grid.x, dtype=float)[ii[pinned]],
            np.asarray(cc.grid.y, dtype=float)[jj[pinned]],
            linestyle="none", marker="s", ms=1.6, color=viz.COL_ACCENT)


def _run_scatter(values: Mapping[str, Any], sink: FigureSink) -> dict:
    """Plane-wave-like incidence on a PEC cylinder, background subtracted.

    Two pictures from **one** pair of integrations: a total/scattered snapshot
    of the instant the pulse peak is over the cylinder, and a sequence of that
    same scattered field as the wave sweeps the body.  The scattered field is
    defined by subtraction, never by an approximate decomposition, so the
    incident pulse, the taper of the source line and the residual reflection of
    the layer all cancel exactly.
    """
    ka, ppw = float(values["ka"]), int(values["ppw"])

    # Snapshot delays, measured from the pulse peak, around the instant the
    # peak reaches the cylinder centre.  Spacing well below one wavelength
    # keeps the frames distinct at every ppw the parameter allows.
    to_centre = 0.5 * scatter.N_LAMBDA - scatter.PML_LAMBDA - scatter.SRC_INSET
    offsets = np.linspace(-SCATTER_SPAN, SCATTER_SPAN, SCATTER_FRAMES)
    delays = (to_centre + offsets) * scatter.LAM0 / C0

    result = scatter.run_scatter(ka=ka, ppw=ppw, delays=delays)
    st = result.setup
    cc = result.cc
    total = np.asarray(result.ez_total, dtype=float)
    scattered = np.asarray(result.ez_scattered, dtype=float)
    if total.ndim == 2:                              # a single frame came back
        total, scattered = total[None, ...], scattered[None, ...]
    delay_ns = (np.asarray(result.times, dtype=float) - st.t0) * 1e9
    n_frames = delay_ns.size

    # --- figure: total and scattered field at the money frame ---------------
    fig, (ax_tot, ax_sca) = plt.subplots(1, 2, figsize=(9.6, 4.0),
                                         constrained_layout=True)
    for ax, data, heading, label in (
            (ax_tot, total[-1], "total field", r"$|E_z|$ [V/m]"),
            (ax_sca, scattered[-1], "scattered field",
             r"$|E_z^{scat}|$ [V/m]")):
        viz.plot_field_slice(st.grid, _scatter_vector(cc, data), "MAGNITUDE",
                             axis="z", ax=ax, cmap="viridis", colorbar=False,
                             title=f"{heading}, $t$ = {delay_ns[-1]:.2f} ns")
        fig.colorbar(ax.collections[0], ax=ax, shrink=0.9, label=label)
        _scatter_overlay(ax, cc, result.mask, st.centre, result.a)
    ax_tot.text(0.02, 0.98,
                f"$ka$ = {result.ka:g}\n{result.ppw} cells / wavelength\n"
                f"radius a = {result.radius_cells:.2f} cells\n"
                f"{result.n_pec_edges} pinned $E_z$ nodes",
                transform=ax_tot.transAxes, va="top", ha="left", fontsize=7,
                color=viz.COL_INK)
    fig.suptitle(f"PEC cylinder, $ka$ = {result.ka:g}, {result.ppw} cells per "
                 f"wavelength: incident and scattered field", fontsize=10)
    sink.add_figure(
        "scatter-snapshot", "PEC cylinder: total and scattered |Ez|", fig,
        caption=(f"TMz incidence on a PEC cylinder of radius a = "
                 f"{result.radius_cells:.2f} cells ({result.a:.3f} m), "
                 f"{result.n_pec_edges} pinned Ez nodes, the instant the pulse "
                 f"peak is over the centre. Left: the total field, which is the "
                 f"incident beam plus the body response; right: the same instant "
                 f"with the cylinder removed and subtracted, so only the field "
                 f"the body radiates survives. Dashed circle: the ideal "
                 f"scatterer; squares: the nodes the staircase actually pins."))

    # --- figure: the scattered field as the pulse sweeps the body -----------
    ncols = min(3, n_frames)
    nrows = -(-n_frames // ncols)                     # ceil
    fig, axes = plt.subplots(nrows, ncols, squeeze=False,
                            figsize=(3.2 * ncols, 2.6 * nrows),
                            constrained_layout=True)
    panels = axes.ravel()
    peak = float(np.max(np.abs(scattered))) or 1.0
    mesh = None
    for i in range(n_frames):
        _, ax = viz.plot_field_slice(
            st.grid, _scatter_vector(cc, scattered[i]), "MAGNITUDE", axis="z",
            ax=panels[i], cmap="viridis", colorbar=False,
            title=f"$t$ = {delay_ns[i]:.2f} ns")
        mesh = ax.collections[0]
        mesh.set_clim(0.0, peak)
        _scatter_overlay(ax, cc, result.mask, st.centre, result.a)
    for ax in panels[n_frames:]:
        ax.axis("off")
    fig.colorbar(mesh, ax=panels.tolist(), shrink=0.9,
                 label=r"$|E_z^{scat}|$ [V/m]")
    fig.suptitle(f"Scattered field, $ka$ = {result.ka:g}, {result.ppw} cells "
                 f"per wavelength", fontsize=10)
    sink.add_figure(
        "scatter-sequence", "Scattered |Ez| as the pulse sweeps the cylinder",
        fig,
        caption=(f"One shared colour scale and one shared bar, so the panels "
                 f"can be compared: 0 to {peak:.1f} V/m, the largest "
                 f"|Ez scattered| anywhere in the sequence. Times are measured "
                 f"from the peak of the launched pulse. The front is "
                 f"plane-wave-like rather than ideal, and the scattered field "
                 f"is the response to that known illumination of finite "
                 f"aperture."))

    return {
        "electrical size ka": f"{result.ka:.3f}",
        "cells per wavelength": f"{result.ppw}",
        "cylinder radius a": f"{result.a:.4f} m",
        "radius in cells": f"{result.radius_cells:.2f}",
        "wavelength": f"{result.lam0:.3f} m",
        "pinned Ez nodes": f"{result.n_pec_edges}",
        "peak |Ez|, total": f"{result.peak_total:.3f} V/m",
        "peak |Ez|, scattered": f"{result.peak_scattered:.3f} V/m",
        "scattered / incident": f"{result.scattered_fraction:.4f}",
        "time steps": f"{result.nsteps}",
        "time step dt": f"{result.dt:.4e} s",
        "snapshots": f"{n_frames}",
        "wall time": f"{result.timings.get('total', 0.0):.2f} s",
    }


# ---------------------------------------------------------------------------
# study 5: bistatic RCS of the PEC cylinder (polar pattern, animation)
# ---------------------------------------------------------------------------
RCS_SAMPLES = 180                 # pattern points, two degrees apart
RCS_ANIM_FRAMES = 24              # frames in the animation
RCS_ANIM_SPAN = (-1.5, 3.5)       # wavelengths either side of the peak arrival
RCS_ANIM_HALF_WIDTH = 2.2         # half-width of the animated window [lambda]
RCS_ANIM_DPI = 72
RCS_ANIM_FPS = 8


def _rcs_animation_gif(result, delay_ns: np.ndarray) -> bytes:
    """GIF bytes of |Ez scattered| sweeping past the PEC cylinder.

    ``result`` is an :class:`emfit.scatter.ScatterResult` holding one frame per
    entry of ``delay_ns``.  The colour scale is computed **once** from the
    whole stack and then held fixed, so a frame can be compared with any other
    frame; per-frame scaling would make the outgoing wave look constant in
    amplitude and hide exactly what the animation is for.  The cylinder circle
    is drawn from the analytic geometry, the same overlay the still figures
    use, so the staircase is never mistaken for the ideal body.

    The animation is written through
    :class:`matplotlib.animation.PillowWriter`, which needs no external
    encoder (the image has no ffmpeg).  ``PillowWriter`` insists on a path it
    can resolve, so the frames go through a private temporary file and come
    back as bytes; the study itself still owns no output location -- it hands
    the bytes to the sink, which decides where they land.

    Parameters
    ----------
    result : ScatterResult
        Fields of the sweep, ``ez_scattered`` of shape ``(n_frames, nx+1,
        ny+1)`` (or ``(nx+1, ny+1)`` for a single frame).
    delay_ns : ndarray
        Time of each frame [ns], measured from the peak of the launched pulse.

    Returns
    -------
    bytes
        The complete GIF.
    """
    from matplotlib.animation import FuncAnimation, PillowWriter

    st = result.setup
    frames = np.abs(np.asarray(result.ez_scattered, dtype=float))
    if frames.ndim == 2:                          # a single frame came back
        frames = frames[None, ...]
    peak = float(np.max(frames)) or 1.0
    delay_ns = np.asarray(delay_ns, dtype=float).ravel()

    grid = st.grid
    x = np.asarray(grid.x, dtype=float)
    y = np.asarray(grid.y, dtype=float)
    centre = st.centre
    half = RCS_ANIM_HALF_WIDTH * st.lam

    fig, ax = plt.subplots(figsize=(3.4, 2.9), dpi=RCS_ANIM_DPI,
                           constrained_layout=True)
    mesh = ax.imshow(frames[0], origin="lower",
                     extent=(x[0], x[-1], y[0], y[-1]), cmap="viridis",
                     vmin=0.0, vmax=peak, interpolation="nearest")
    _scatter_overlay(ax, result.cc, result.mask, centre, result.a)
    ax.set_xlim(centre[0] - half, centre[0] + half)
    ax.set_ylim(centre[1] - half, centre[1] + half)
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    fig.colorbar(mesh, ax=ax, shrink=0.9, label=r"$|E_z^{scat}|$ [V/m]")
    heading = ax.set_title("")

    def update(index: int):
        mesh.set_data(frames[index])
        heading.set_text(f"$ka$ = {result.ka:g}, {result.ppw} cells / "
                         f"$\\lambda$, $t$ = {delay_ns[index]:.2f} ns")
        return ()

    anim = FuncAnimation(fig, update, frames=frames.shape[0], blit=False)
    try:
        with tempfile.TemporaryDirectory() as scratch:
            path = os.path.join(scratch, "rcs-animation.gif")
            anim.save(path, writer=PillowWriter(fps=RCS_ANIM_FPS),
                      dpi=RCS_ANIM_DPI)
            with open(path, "rb") as handle:
                return handle.read()
    finally:
        plt.close(fig)


def _rcs_at(phis_deg: np.ndarray, values: np.ndarray, angle: float) -> float:
    """Value of ``values`` at the sampled angle nearest ``angle`` [deg]."""
    return float(np.asarray(values, dtype=float)[
        int(np.argmin(np.abs(np.asarray(phis_deg, dtype=float) - angle)))])


def _run_rcs(values: Mapping[str, Any], sink: FigureSink) -> dict:
    """Bistatic scattering width of a PEC cylinder, against exact Mie.

    One :func:`emfit.nearfield.run_rcs` call at every angle gives the whole
    pattern; the contour integral is a post-processing step over the same two
    integrations, so sweeping the observation angle costs nothing.  The second
    figure is an animation of the run the same setup produces, animated past
    the body so the outgoing wave is visible rather than inferred.
    """
    ka, ppw = float(values["ka"]), int(values["ppw"])
    t_start = time.perf_counter()

    phis = np.arange(0.0, 360.0, 360.0 / RCS_SAMPLES)
    result = nearfield.run_rcs(ka=ka, ppw=ppw, phis_deg=phis)
    ours_db = np.asarray(result.sigma_2d_db, dtype=float)
    mie_db = np.asarray(result.sigma_mie_db, dtype=float)
    diff = np.asarray(result.db_diff, dtype=float)
    rms_db = float(np.sqrt(np.mean(diff ** 2)))
    worst = int(np.argmax(np.abs(diff)))
    worst_db = float(diff[worst])

    # Mean over a uniform angle sweep is the 2-D total scattering width normalised
    # so that an isotropic pattern has sigma_total = sigma(phi).
    sigma_total_ours = float(np.mean(result.sigma_2d))
    sigma_total_mie = float(np.mean(result.sigma_mie))

    # --- figure: polar pattern and the same curves on Cartesian axes --------
    fig = plt.figure(figsize=(11.0, 4.6), constrained_layout=True)
    ax_polar = fig.add_subplot(1, 2, 1, projection="polar")
    ax_polar.set_theta_zero_location("E")     # 0 deg at +x, to the right
    ax_polar.set_theta_direction(1)           # increasing anticlockwise
    theta = np.radians(phis)
    ax_polar.plot(theta, ours_db, color=viz.COL_PRIMARY, lw=1.4,
                  label="FIT (this code)")
    ax_polar.plot(theta, mie_db, color=viz.COL_ACCENT, lw=1.1, ls="--",
                  label="exact Mie")

    # Radial limits from the data, with a margin: the forward lobe is the
    # largest value on the plot and must stay inside the frame.
    lo = float(np.floor(min(ours_db.min(), mie_db.min()))) - 1.0
    hi = float(np.ceil(max(ours_db.max(), mie_db.max()))) + 1.0
    ticks = np.arange(np.ceil(lo / 10.0) * 10.0, hi, 10.0)
    ax_polar.set_rlim(lo, hi)
    ax_polar.set_rgrids(ticks, labels=[f"{tick:g}" for tick in ticks],
                        angle=135.0, fontsize=7)
    ax_polar.set_thetagrids(np.arange(0.0, 360.0, 30.0),
                            labels=[f"{a:g}" for a in np.arange(0.0, 360.0, 30.0)],
                            fontsize=7)
    ax_polar.grid(color=viz.COL_MUTED, lw=0.4, alpha=0.6)
    ax_polar.set_title(r"$10\log_{10}\,\sigma_{2D}$ [dB m] against $\phi$",
                       fontsize=9)
    ax_polar.text(0.02, 0.98,
                  f"$ka$ = {result.ka:g}\n{result.ppw} cells / wavelength\n"
                  f"radius $a$ = {result.a:.4f} m ({result.radius_cells:.2f} cells)\n"
                  f"$\\sigma_{{tot}}$ = {sigma_total_ours:.3f} / "
                  f"{sigma_total_mie:.3f} m",
                  transform=ax_polar.transAxes, va="top", ha="left", fontsize=7,
                  color=viz.COL_INK)
    ax_polar.legend(loc="lower left", fontsize=7, framealpha=0.9)

    ax_db = fig.add_subplot(1, 2, 2)
    ax_db.plot(phis, ours_db, color=viz.COL_PRIMARY, lw=1.4,
               label="FIT (this code)")
    ax_db.plot(phis, mie_db, color=viz.COL_ACCENT, lw=1.1, ls="--",
               label="exact Mie")
    ax_db.set_xlabel(r"observation angle $\phi$ [deg]")
    ax_db.set_ylabel(r"$10\log_{10}\,\sigma_{2D}$ [dB m]")
    ax_db.set_xlim(0.0, 360.0)
    ax_db.set_xticks(np.arange(0.0, 361.0, 45.0))
    ax_db.grid(color=viz.COL_MUTED, lw=0.4, alpha=0.5)
    ax_db.set_title("same curves, with the error on their own axis", fontsize=9)
    ax_db.legend(loc="upper right", fontsize=7, framealpha=0.9)

    ax_err = ax_db.twinx()
    ax_err.fill_between(phis, 0.0, diff, color=viz.COL_ACCENT, alpha=0.20, lw=0)
    ax_err.plot(phis, diff, color=viz.COL_ACCENT, lw=0.9)
    ax_err.axhline(0.0, color=viz.COL_INK, lw=0.5)
    ax_err.set_ylabel("difference, FIT minus Mie [dB]", fontsize=8)
    spread = float(np.max(np.abs(diff))) or 1.0
    ax_err.set_ylim(-1.35 * spread, 1.35 * spread)
    ax_err.tick_params(labelsize=7)
    ax_db.text(0.02, 0.03,
               f"rms |diff| = {rms_db:.2f} dB\n"
               f"max |diff| = {abs(worst_db):.2f} dB at {phis[worst]:.0f} deg",
               transform=ax_db.transAxes, va="bottom", ha="left", fontsize=7.5,
               color=viz.COL_INK,
               bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=viz.COL_MUTED,
                         alpha=0.85, lw=0.5))
    fig.suptitle(f"Bistatic scattering width of a PEC cylinder, $ka$ = "
                 f"{result.ka:g}, {result.ppw} cells per wavelength", fontsize=10)
    sink.add_figure(
        "rcs-pattern", "Bistatic RCS of the PEC cylinder against Mie", fig,
        caption=(f"Left: polar plot of the scattering width, 0 deg along +x and "
                 f"increasing anticlockwise, radial limits {lo:g} to {hi:g} dB "
                 f"taken from the data so the forward lobe stays in frame. "
                 f"Right: the same two curves on Cartesian axes with the "
                 f"difference (FIT minus Mie) shaded on the right-hand axis; "
                 f"rms {rms_db:.2f} dB, largest {abs(worst_db):.2f} dB at "
                 f"{phis[worst]:.0f} deg. The error is the whole pipeline -- "
                 f"staircase, dispersion, contour quadrature, absorber "
                 f"leakage -- and is concentrated where the pattern is "
                 f"shallowest (the nulls), as it must be: a fixed relative "
                 f"error is a large dB error where sigma is small."))

    # --- figure: the run itself, as an animation ---------------------------
    to_centre = 0.5 * scatter.N_LAMBDA - scatter.PML_LAMBDA - scatter.SRC_INSET
    offsets = np.linspace(RCS_ANIM_SPAN[0], RCS_ANIM_SPAN[1], RCS_ANIM_FRAMES)
    delays = (to_centre + offsets) * scatter.LAM0 / C0
    sweep = scatter.run_scatter(ka=ka, ppw=ppw, delays=delays)
    delay_ns = (np.asarray(sweep.times, dtype=float) - sweep.setup.t0) * 1e9
    gif = _rcs_animation_gif(sweep, delay_ns)
    sink.add_attachment(
        "rcs-animation", "rcs-animation.gif", gif,
        title="Scattered |Ez| sweeping past the PEC cylinder",
        caption=(f"{delay_ns.size} frames, {delay_ns[0]:.2f} to "
                 f"{delay_ns[-1]:.2f} ns from the peak of the launched pulse. "
                 f"One fixed colour scale for the whole animation, taken from "
                 f"the largest |Ez scattered| anywhere in the sweep, so the "
                 f"amplitude decay is real and not a re-normalisation. Dashed "
                 f"circle: the ideal scatterer."))

    contour_w, contour_h = result.contour_size_lambda
    timings = dict(result.timings or {})
    return {
        "electrical size ka": f"{result.ka:.3f}",
        "cells per wavelength": f"{result.ppw}",
        "cylinder radius a": f"{result.a:.4f} m",
        "radius in cells": f"{result.radius_cells:.2f}",
        "wavenumber k": f"{result.k:.4f} 1/m",
        "sigma @ 0 / 90 / 180 deg": " / ".join(
            f"{_rcs_at(phis, result.sigma_2d, angle):.4f}"
            for angle in (0.0, 90.0, 180.0)) + " m",
        "sigma Mie @ 0 / 90 / 180 deg": " / ".join(
            f"{_rcs_at(phis, result.sigma_mie, angle):.4f}"
            for angle in (0.0, 90.0, 180.0)) + " m",
        "sigma total, ours": f"{sigma_total_ours:.4f} m (mean over phi)",
        "sigma total, Mie": f"{sigma_total_mie:.4f} m (mean over phi)",
        "rms dB difference": f"{rms_db:.3f} dB",
        "max dB difference": f"{abs(worst_db):.3f} dB at {phis[worst]:.0f} deg",
        "pattern points": f"{phis.size}",
        "time steps": f"{result.nsteps}",
        "time step dt": f"{result.dt:.4e} s",
        "contour size": f"{contour_w:.2f} x {contour_h:.2f} wavelengths",
        "animation frames": f"{delay_ns.size} at {RCS_ANIM_FPS} fps, "
                            f"{len(gif) / 1024.0:.0f} kB",
        "time domain wall time": f"{timings.get('total', 0.0):.2f} s",
        "wall time": f"{time.perf_counter() - t_start:.2f} s",
    }


# ---------------------------------------------------------------------------
# study 6: microstrip wave -- phasors along the line, and what the layer does
# ---------------------------------------------------------------------------
#: Substrate thickness of the default cross-section [m].
MS_H = 1.6e-3
#: Strip width of the default cross-section [m]; ``w/h = 2``.
MS_W = 3.2e-3
#: Relative permittivity of the default substrate.
MS_EPS_R = 4.4
#: Drive frequency asked for [Hz]; snapped onto a DFT bin of the record.
MS_F_TARGET = 6.0e9
#: Leapfrog steps of the default run.
#:
#: A quarter of them is warm-up, so the record is 1800 steps.  The strip runs
#: into the six-cell absorber on the far ``x`` wall, so the guided mode is
#: terminated by that layer and not by the metal behind it; the residual
#: reflection of the termination is all the line has, and the launched
#: transient has to reach it and fade before the record is a steady state.  At
#: 600 steps the record was 450 steps of a transient still in flight and every
#: phase measured on it was biased; at 2400 the fitted numbers move by about a
#: tenth of a per cent if the record is lengthened further.
MS_NSTEPS = 2400
#: Matched-layer cells at each absorbing face (``x``, ``y`` and ``zmax``).
MS_N_PML = 6
#: First and last probe station of the default run [m].
MS_X_FIRST, MS_X_LAST = 10.4e-3, 20.0e-3
#: Probe stations along the line.
MS_N_STATIONS = 9
#: How far the phase constant may move between the two halves of one averaging
#: window before the record is called unsettled [relative].  A record whose
#: ``beta`` is still moving by more than this has not finished filling, and no
#: decay read off it is a measurement.
MS_SETTLE_TOL = 0.01
#: Substrate cells across ``h``; this fixes the cell size of the whole mesh.
#: Four cells over 1.6 mm is a 0.4 mm cell: the historical reference mesh.
MS_N_SUB = 4
#: Air cells between the strip and the layer at ``zmax``.
MS_N_AIR = 12
#: Matched-layer cells against the ``zmax`` face; ``0`` leaves it a plain PEC
#: lid and builds no layer there.  A single :class:`emfit.pml.PML` carries one
#: thickness for every wall it opens, so a non-zero value has to equal
#: ``MS_N_PML``; that is checked, never silently ignored.
MS_N_TOP = 6
#: Cells across the strip width.
MS_N_STRIP = 8
#: Clean cells between the strip edge and the lateral matched layer.
MS_N_CLEAN = 12
#: Line cells between the port plane and the layer behind it.
MS_N_REF = 2
#: Line cells between the port plane and the far (PEC) end of the strip.
MS_N_LINE = 54
#: Nominal port impedance carried by the :class:`LumpedPort` [ohm].
MS_Z0_NOMINAL = 50.0
#: Excitation of the default run: ``"cw"`` is the historical single tone, and
#: ``"pulse"`` the Ricker wavelet the broadband sweep is read off.  The default
#: is the tone, so every number this study has ever quoted stays as it was.
MS_EXCITE = "cw"
#: Lower edge of the broadband sweep [GHz].  A pulse run reports its bins
#: between here and ``MS_BAND_HI_GHZ``; a tone run never looks at either.
MS_BAND_LO_GHZ = 2.0
#: Upper edge of the broadband sweep [GHz].
MS_BAND_HI_GHZ = 12.0
#: How many frequencies the broadband sweep reports.
MS_N_BINS = 25
#: Centre frequency of the broadband pulse [GHz].  A Ricker's spectrum peaks at
#: its own ``fmax`` and falls to nothing by ``2.5 fmax``, so this is where the
#: drive has energy and where the band has to sit to be measurable.
MS_F_PULSE_GHZ = 5.83
#: The weight the broadband sweep multiplies the kept record by before summing
#: a bin, and measures its own drive spectrum through: ``"rect"`` or
#: ``"hann"``.  Flat is a deliberate choice here and not the default by
#: omission; the sweep in :func:`microstrip_wave` says why, and quotes what
#: tapering measured.
PULSE_WINDOW = "rect"


def line_s21(a1, x1, a2, x2, beta) -> tuple[complex, complex]:
    """``|S21|`` between two planes from the forward amplitudes on them.

    ``a1`` and ``a2`` are the forward amplitudes of two fits whose stations
    were shifted onto ``x1`` and ``x2``, so each is the travelling wave *at*
    its own plane.  Their ratio is what crossed the gap, and
    :func:`emfit.ports.deembed_transmission` then takes the line's own delay
    ``exp(-1j beta d)`` back out of it.

    With a real ``beta`` the factor has unit modulus, so the de-embedding
    cannot change the magnitude: this is a pure amplitude ratio, and the phase
    it removes is only a reference.  With a complex ``beta = beta' - 1j
    alpha`` the factor's magnitude is ``exp(+alpha d)``, exactly the
    attenuation the ratio carries, so a lossy length de-embeds to ``1`` while a
    lossless one comes back as measured.

    Args:
        a1, a2: Complex forward-wave amplitudes at ``x1`` and ``x2``.
        x1, x2: The two planes [m]; ``x2`` must be downstream of ``x1``.
        beta: Phase constant for the de-embedding [rad/m], real or complex.

    Returns:
        ``(s21, raw)``: the de-embedded coefficient and the plain ratio
        ``a2 / a1`` it was made from.

    Raises:
        ValueError: If ``x2 <= x1``, or if ``a1`` is zero and there is no
            ratio to take.
    """
    d = float(x2) - float(x1)
    if d <= 0.0:
        raise ValueError(
            f"x2 must be downstream of x1, got x1={x1!r} m and x2={x2!r} m")
    if complex(a1) == 0.0:
        raise ValueError("a1 is zero: there is no forward amplitude to divide by")
    raw = complex(a2) / complex(a1)
    return deembed_transmission(raw, beta, d), raw


def _wave_amplitude(v, i, x, gamma, zc, sign, indices) -> np.ndarray:
    """Shared algebra of :func:`forward_wave_amplitude` and its mirror."""
    v = np.asarray(v, dtype=complex)
    i = np.asarray(i, dtype=complex)
    x = np.asarray(x, dtype=float)
    if not v.size == i.size == x.size:
        raise ValueError(
            f"v, i and x must be the same length, got {v.size}, {i.size} "
            f"and {x.size}")
    if indices is not None:
        idx = np.asarray(indices, dtype=int)
        v, i, x = v[idx], i[idx], x[idx]
    return 0.5 * (v + complex(sign * zc) * i) * np.exp(complex(sign * gamma) * x)


def forward_wave_amplitude(v, i, x, gamma, zc, indices=None) -> np.ndarray:
    """The wave travelling towards ``+x``, de-embedded to ``x = 0``.

    ``v`` and ``i`` are the gap voltage [V] and the trace current [A] at
    position ``x`` [m]; ``gamma`` is the propagation constant [1/m] and ``zc``
    the characteristic impedance [ohm] of the line they belong to.  With the
    convention every fit in this package uses,

        ``v(x) = A exp(-gamma x) + B exp(+gamma x)``
        ``i(x) = (A exp(-gamma x) - B exp(+gamma x)) / zc``

    where ``A`` travels towards ``+x`` and ``B`` back towards ``-x``, both
    referred to ``x = 0`` -- the same origin for every station, which is what
    makes two stations' amplitudes comparable.  Adding and subtracting give the
    two waves on one plane,

        ``A exp(-gamma x) = (v + zc i) / 2``
        ``B exp(+gamma x) = (v - zc i) / 2``

    so multiplying by ``exp(+gamma x)`` walks ``A`` back to the origin.  What
    comes back is the amplitude ``A`` itself, not the local phasor.

    Why one plane is enough
    -----------------------
    A ratio between two planes needs no fit once ``gamma`` and ``zc`` are known:
    on a uniform line the split above is exact algebra, and the two unknowns of
    a fit were only ever ``gamma`` and ``zc``.  Given them, one station's two
    phasors determine its forward wave.

    That is what makes this usable as a *normalisation*: with the same
    ``gamma``, ``zc`` and station positions, the exponential factor at a
    station is the same floating-point number in two runs, so a ratio of
    amplitude ratios computed this way does not depend on the real part of
    ``gamma`` at all -- the line's delay and loss divide out exactly instead of
    being de-embedded by an approximation that has to be trusted.

    Args:
        v, i: Complex phasors of the gap voltage [V] and the trace current [A],
            the current in the forward sense (the negative of the ground return
            current, see :func:`emfit.ports.plate_current`).
        x: Station positions [m], on the same axis the phasors were measured.
        gamma: ``alpha + 1j beta`` [1/m], ``exp(-gamma x)`` forward.
        zc: Characteristic impedance [ohm], complex; ``v / i`` of the forward
            wave alone.
        indices: Optional station indices to evaluate at -- negative values
            count from the end -- instead of the whole array.

    Returns:
        ``(n,)`` (or ``len(indices)``) complex array of ``A``, i.e. each
        station's forward wave referred to ``x = 0`` [V].

    Raises:
        ValueError: If ``v``, ``i`` and ``x`` are not the same length.
    """
    return _wave_amplitude(v, i, x, gamma, zc, 1.0, indices)


def backward_wave_amplitude(v, i, x, gamma, zc, indices=None) -> np.ndarray:
    """The wave travelling towards ``-x``, de-embedded to ``x = 0``.

    The mirror of :func:`forward_wave_amplitude`, and literally the same
    algebra with the sign of both ``gamma`` and ``zc`` flipped: ``B exp(+gamma
    x)`` referred to the origin is ``(v - zc i) / 2 exp(-gamma x)``, with the
    same units, conventions and station axis (see there for the model).

    Args:
        v, i: Complex phasors of the gap voltage [V] and the trace current [A].
        x: Station positions [m].
        gamma: ``alpha + 1j beta`` [1/m], ``exp(-gamma x)`` forward.
        zc: Characteristic impedance [ohm], complex.
        indices: Optional station indices to evaluate at.

    Returns:
        ``(n,)`` (or ``len(indices)``) complex array of ``B`` [V].

    Raises:
        ValueError: If ``v``, ``i`` and ``x`` are not the same length.
    """
    return _wave_amplitude(v, i, x, gamma, zc, -1.0, indices)


def _drive_frequency_text(g: dict) -> str:
    """The frequency, or band, a report row may name for this run -- honestly.

    A tone run has one frequency and may name it.  A pulse run does not: its
    numbers are read one bin at a time off a broadband record, and ``g['f']`` is
    only the snapped bin of the tone accumulator that shares that record -- a
    frequency no bin of the sweep was read at, so quoting it as the run's
    frequency would be a lie about what was measured.  The band, the bin count
    and ``f_pulse`` are what such a run can honestly report.
    """
    if g.get("excite") == "pulse":
        return (f"broadband {g['band_lo'] / 1e9:.4f}..{g['band_hi'] / 1e9:.4f}"
                f" GHz in {g['n_bins']} bins, pulse peaked at "
                f"{g['f_pulse'] / 1e9:.4f} GHz")
    return (f"{g['f'] / 1e9:.4f} GHz (asked {g['f_target'] / 1e9:.4f} GHz, "
            "snapped to a DFT bin)")


@dataclass
class MicrostripWave:
    """What one :func:`microstrip_wave` run measured, and on which mesh.

    Every length is SI metres and every phasor is a complex DFT coefficient of
    the state at ``geometry['f']``, accumulated over the same record for every
    signal, so ratios of two of them are meaningful and the overall normalising
    factor cancels.

    Attributes:
        geometry: Everything the mesh build decided -- cell counts, cell size,
            the strip and port indices, the station cells, ``dt``, the tone
            accumulator's frequency (a DFT bin, which is not ``f_target``: on a
            tone run that is the drive frequency, on a pulse run it is
            neither the drive nor any bin of the sweep, so a report names the
            band instead -- see :func:`_drive_frequency_text`) and the warm-up
            split of the record.
        station_x: ``(n_stations,)`` x positions of the voltage probes [m].
        v_stations: ``(n_stations,)`` complex gap voltages at those stations [V].
        i_stations: ``(n_stations,)`` complex trace currents at those stations
            [A], in the same (forward) sense as ``z0``.
        v_port: Complex gap voltage on the port plane [V].
        i_ground_full: Complex return current summed over **every** ``y``
            column of the ground plane at the port station [A].
        i_ground_truncated: The same sum over the physical strip extent only,
            i.e. with the lateral matched-layer columns left out [A].
        y_extent: Half-width used for the truncated sum [m].
        beta_two_station: Phase constant from the plain phase difference
            between the first and the last station [rad/m], ``-angle(v_last *
            conj(v_first)) / span``.  Kept as a cross-check: it is exact only
            for a single travelling wave, and it carries the sign of whichever
            way the phasor happened to rotate over the span, so it may come out
            negative.
        beta: Phase constant from a least-squares one-wave fit over every
            station, ``v(z) = A exp(-j beta z)`` [rad/m].  Positive by
            construction: the fit only searches ``beta > 0``, so this is the
            forward wave and no branch ambiguity can arise.  This is the
            number to quote.
        beta_two_wave: Phase constant from the two-wave fit, ``v(z) = A
            exp(-j beta z) + B exp(+j beta z)`` [rad/m].  Its distance from
            ``beta`` is the size of the standing wave the one-wave model had to
            swallow.
        beta_first_half, beta_second_half: The one-wave phase constant refitted
            on the first and on the second half of the transformed record, each
            half accumulated separately out of the same run [rad/m].  A record
            that still carries a transient, or a mode whose amplitude is still
            climbing, hands the two halves different ``beta``.  The halves are
            not on the DFT bins of the whole record, so each carries its own
            leakage -- but the leakage factor is common to every station, so it
            moves neither ``beta`` nor any station ratio.  ``nan`` when the
            record was too short to split.
        gamma: ``B / A`` of that two-wave fit, the reflection coefficient at
            ``z = 0`` (dimensionless, complex).  ``abs(gamma)`` is the
            standing-wave diagnostic.
        fit_residual: Relative RMS misfit of the one-wave fit,
            ``||v - model|| / ||v||`` (dimensionless).  Large means the phasors
            are not one travelling wave -- a standing wave, or a record too
            short for the transient to have left the line.
        loss_fit: :func:`emfit.ports.fit_line` on the same stations -- the same
            one-wave model as :func:`fit_beta`, except that the decay is free
            too, ``v(z) = A exp(-(alpha + j beta) z)`` with ``alpha`` in Np/m,
            and with the joint covariance of ``(alpha, beta)`` beside it.
            ``None`` when the record holds nothing to fit.  Its ``alpha`` is
            ``None`` in turn when the record cannot support one (the standard
            error reaching across the whole span), which is a refusal to
            quote, not a zero.
        loss_fit_two: The same fit with a backward wave allowed.  Its ``alpha``
            and ``beta`` are read off a standing wave rather than through it;
            the pair of them against ``loss_fit`` is this study's loss
            analogue of ``beta`` against ``beta_two_wave``.
        beta_model: ``emfit.microstrip`` Hammerstad-Jensen value at the same
            frequency [rad/m].
        z0: ``V / I`` at the port station, ``V`` from the port gap and ``I``
            from the truncated ground return, complex [ohm].  This is the
            impedance of the port plane, not of the line: ``abs(z0)`` is its
            modulus and ``z0.real`` its resistive part, and neither may be
            quoted as the characteristic impedance without the phase beside
            it.  The value is referred to the trace (forward) current -- the
            return current is summed in the opposite sense, so the raw
            ``V / I`` is negated -- which makes ``arg(z0)`` the excess phase of
            the port impedance (about +17 deg at the default case).
        station_fit: The characteristic impedance of the *line*, fitted to the
            station voltages and to the station ground currents at ``beta`` --
            a different quantity from ``z0``, which is one port plane's
            ``V / I``.  It comes with its own uncertainty budget (statistical
            plus the part carried over from ``beta``) and with the reference
            plane it is referred to, without which the number means nothing.
            A line of stations sees the standing wave over several centimetres,
            so it can separate the two travelling waves; one port plane cannot.
            ``None`` when that fit was refused too: a record whose phase
            constant carries a standard error as large as the phase constant
            has no impedance to quote, and the run says so once instead of
            dying with a good record in hand.
        station_fit_lossy: ``station_fit`` repeated with the loss the line
            actually has: the propagation constant is
            ``loss_fit.alpha + j loss_fit.beta`` instead of a bare
            ``j beta``, and ``sigma_beta`` is ``loss_fit.beta_sigma``.  On a
            lossy line the voltage and current waves no longer stay in step
            along the span, so the pair of them carries information the
            lossless fit throws away.  The sensitivity to ``alpha`` -- a
            central difference over ``loss_fit.alpha +- alpha_sigma`` -- is
            folded into its ``z0_sigma_total``, because an uncertainty budget
            that leaves out the dominant term is worse than no budget; when
            ``alpha`` has no error estimate the total falls back to the
            ``beta`` and statistical terms alone.  ``None`` when that fit
            could not be formed at all: :func:`emfit.ports.fit_station_impedance`
            refuses when the phase constant it is handed carries a standard
            error as large as the phase constant itself, which a strongly
            reflecting line can do, so the run warns and carries on instead of
            dying with a good record in hand.
        station_fit_ok: Whether the station-impedance fits were formed at all
            -- a flag, not a number.  ``True`` on every ordinary run;
            ``False`` means one of them was refused, ``station_fit_lossy`` is
            ``None`` rather than half filled (``station_fit`` too, when it was
            the loss-free one that went), and the reason was raised as a
            single ``RuntimeWarning`` at the time.  ``beta`` does not depend on
            them, but ``s21`` does take the ``zc`` its split needs from the
            loss-free fit's ``z0``: when that fit is missing the ``zc`` comes
            from the ``reference`` instead, and a run with neither refuses
            rather than quoting a split it cannot make.
        loaded_without_reference: ``True`` when this record carried a lumped
            load but no ``reference`` to normalise ``s21`` against -- a flag,
            not a number.  A loaded record's own two-wave fit is not a
            description of the line, because the stations straddle the cut and
            the fit assumes the continuity the load breaks, so its ``Zc`` is
            not the impedance the mode has and ``Zc`` has to come from a
            load-free run on the same mesh.  The magnitude of ``s21`` is still
            reported, since it needs only ``zc`` and the two station phasors,
            but the metrics recover no impedance from it and say why, and on
            this path that magnitude reads about 3 per cent low (0.533392
            against 0.549464 on the 100 ohm series load), so a default-path
            load is a magnitude record and never an impedance.
        gamma_port: ``station_fit.gamma_v`` moved from its reference plane to
            the port plane with :func:`emfit.ports.deembed_reflection`
            (dimensionless, complex).  With a real ``beta`` its magnitude is
            exactly that of ``gamma_v``; only its phase moves, and only the
            phase is what a de-embedding can honestly change here.
        deembed_distance: How far upstream the reflection was moved, i.e.
            ``station_x[0] - ix_port * cell`` [m].
        s21: Transmission coefficient from the first station plane to the
            last, de-embedded with :func:`emfit.ports.deembed_transmission`
            (dimensionless, complex).  No fit stands in it: the forward wave is
            taken from the algebra that splits ``v`` and ``i`` with the run's
            own measured ``zc``, on one plane at each end of the span, so the
            cut between them is measured rather than averaged into a fit's
            model.  ``beta`` is real, so the de-embedding has unit modulus:
            this is the amplitude ratio across the span and the factor only
            fixes its phase.  The solver has no loss model, so on a load-free
            record a departure from ``1`` is power leaving the guided mode for
            the matched layers, which the metrics measure a second way as
            ``exp(-alpha L)``.  On a loaded record with no ``reference`` the
            magnitude stands but nothing may be recovered from it: see
            ``loaded_without_reference``.  A run given a ``reference``
            (:class:`LineReference`)
            reports here the ratio of the forward amplitudes across the same
            two planes divided by that of the load-free line -- the delay and
            the loss of the line, and any error ``gamma`` and ``zc`` share
            between the two runs, cancel by construction instead of being
            de-embedded -- so the number is the load's transmission and needs
            no ``beta`` to be right.
        s21_raw: The same ratio before the de-embedding, ``a2 / a1``.
        s21_planes: The two station planes it spans, ``(x1, x2)`` [m].
        power_z0: ``(n_stations,)`` impedance each station's own power and
            current imply, ``Re(V conj(I)) / |I|**2`` [ohm].
        power_ratio: The same divided by ``Re(station_fit.z0)``; 1 for one
            travelling wave.
        power_z0_port: The power-current impedance on the port plane [ohm].
        power_ratio_port: And its ratio to ``Re(z0)`` on that plane.
        z0_model: Closed-form quasi-static impedance of the cross-section [ohm].
        eps_eff: Effective permittivity implied by ``beta``, i.e. by the
            one-wave fit and not by the two-station difference.
        eps_eff_model: Closed-form effective permittivity of the cross-section.
        slice_ez: ``(nxn, nyn)`` complex phasor of ``E_z`` on the mid-plane
            ``z = k_mid * cell``, the node layer halfway up the substrate,
            from the average of the two ``E_z`` cells that straddle it.  Only
            filled when the run was asked for it (``keep_slice=True``);
            otherwise ``None``, because the map costs one DFT accumulator over
            the whole plane and a run that will not draw it should not pay.
            The transverse node pairs are **not** averaged here -- this is the
            raw accumulator, and :func:`emfit.viz.plot_field_slice` does the
            co-location when it draws.
        power_balance: What the matched layers removed during the settled part
            of the record, binned by which family of walls removed it.  Only
            filled when the run was asked for it (``audit=True``), otherwise
            ``None``.  See :class:`emfit.pml.AbsorbedWork` for what is counted.
        bins: One :class:`BinMetric` per frequency of the broadband sweep, in
            ascending frequency order, or ``()`` when the record was the
            single-tone drive.  A bin carries its own refusal rather than
            raising, so one unusable frequency does not cost the other
            twenty-four theirs: see :func:`_bin_metrics` for what each field
            means and for why the post-processing is a deliberate copy of the
            tone path's rather than a sharing of it.
    """

    geometry: dict
    station_x: np.ndarray
    v_stations: np.ndarray
    i_stations: np.ndarray
    v_port: complex
    i_ground_full: complex
    i_ground_truncated: complex
    y_extent: float
    beta_two_station: float
    beta: float
    beta_two_wave: float
    beta_first_half: float
    beta_second_half: float
    gamma: complex
    fit_residual: float
    beta_model: float
    z0: complex
    station_fit: StationFit | None
    gamma_port: complex
    deembed_distance: float
    s21: complex
    s21_raw: complex
    s21_planes: tuple[float, float]
    power_z0: np.ndarray
    power_ratio: np.ndarray
    power_z0_port: float
    power_ratio_port: float
    z0_model: float
    eps_eff: float
    eps_eff_model: float
    loss_fit: LineFit | None
    loss_fit_two: LineFit | None
    station_fit_lossy: StationFit | None
    slice_ez: np.ndarray | None
    power_balance: dict | None = None
    station_fit_ok: bool = True
    loaded_without_reference: bool = False
    bins: tuple = ()

    def summary(self) -> str:
        """One machine-readable line, the same fields the CLI prints."""
        g = self.geometry
        # A loaded record with no reference has no line constant to quote: its
        # beta and its station fit span the cut, so they carry the load as well
        # as the line.  These fields say ``n/a`` here rather than smuggle a
        # number past a report that states the refusal in words.
        if self.loaded_without_reference:
            eps_eff_txt = "n/a"
            z0_modulus = z0_phase = z0_real = "n/a"
        else:
            eps_eff_txt = f"{self.eps_eff:.5f}"
            z0_modulus = f"{abs(self.z0):.4f}ohm"
            z0_phase = f"{np.degrees(np.angle(self.z0)):.4f}deg"
            z0_real = f"{self.z0.real:.4f}ohm"
        if g.get("excite") == "pulse":
            # A pulse run has no single frequency to put after ``f=``: ``g['f']``
            # is the tone accumulator's bin, not the frequency of the run, and
            # naming it here would smuggle that number out as if it were.  The
            # band, the bin count and the pulse's own peak are what it can say.
            f_txt = (f"f=broadband band={g['band_lo'] / 1e9:.4f}-"
                     f"{g['band_hi'] / 1e9:.4f}GHz n_bins={g['n_bins']}"
                     f" f_pulse={g['f_pulse'] / 1e9:.4f}GHz")
        else:
            f_txt = f"f={g['f'] / 1e9:.4f}GHz"
        line = (
            f"microstrip {f_txt}"
            f" f_target={g['f_target'] / 1e9:.4f}GHz"
            f" cells={g['nx']}x{g['ny']}x{g['nz']}"
            f" cell={g['cell'] * 1e3:.4f}mm nsteps={g['nsteps']}"
            f" n_warm={g['n_warm']}"
            f" beta={self.beta:.4f}rad/m beta_model={self.beta_model:.4f}rad/m"
            f" eps_eff={eps_eff_txt} eps_eff_model={self.eps_eff_model:.5f}"
            f" |z0|={z0_modulus}"
            f" arg_z0={z0_phase}"
            f" Re_z0={z0_real}"
            f" z0_model={self.z0_model:.4f}ohm"
            f" i_ground_full={abs(self.i_ground_full):.6e}A"
            f" i_ground_truncated={abs(self.i_ground_truncated):.6e}A"
            f" y_extent={self.y_extent * 1e3:.4f}mm")
        # The audit, when it was asked for: appended rather than woven in so
        # the default line stays byte-identical.
        if self.power_balance is None:
            return line
        return line + (
            f" lateral_work_fraction={self.power_balance['lateral_fraction']:.6f}"
            f" implied_s21={self.power_balance['implied_s21']:.6f}"
            f" implied_length={self.power_balance['length'] * 1e3:.4f}mm")


@dataclass(frozen=True)
class LineReference:
    """A load-free run's travelling-wave decomposition, kept for normalising.

    :func:`microstrip_wave` reads ``s21`` from the forward amplitudes on two
    planes, and a forward amplitude needs a ``gamma`` and a ``zc``
    (:func:`forward_wave_amplitude`).  Taking those from a run of the *same*
    line with nothing on it turns the line's removal from an approximation into
    an identity: the loaded and the load-free ratio carry the same
    ``exp(-gamma d)``, computed from the same ``gamma`` and the same station
    positions, so dividing one by the other leaves only what the load did --
    and it leaves it however wrong ``gamma`` and ``zc`` are, because both runs
    were wrong by the same amount.  That is the whole point of this type: a
    number a fit produced is trustworthy here only as a *shared* error, so
    nothing about it is hard-coded and nothing has to be quoted.

    Every length is SI metres, impedances ohm, ``gamma`` rad/m and 1/m, and the
    phasors are the complex DFT coefficients of the run at ``geometry['f']``.

    Attributes:
        gamma: ``alpha + 1j beta`` [1/m], with ``exp(-gamma x)`` the forward
            wave.
        zc: Characteristic impedance [ohm], complex -- ``v / i`` of the forward
            wave alone, which is what ``station_fit.z0`` measures.
        station_x: ``(n,)`` station positions [m].
        v_stations, i_stations: ``(n,)`` station gap voltages [V] and trace
            currents [A], the phasors a :class:`MicrostripWave` carries.
    """

    gamma: complex
    zc: complex
    station_x: np.ndarray
    v_stations: np.ndarray
    i_stations: np.ndarray

    @classmethod
    def from_wave(cls, wave: MicrostripWave) -> LineReference:
        """The reference a run of an unloaded line implies.

        ``gamma`` is the run's own ``alpha`` -- ``0`` when the record cannot
        support one, which is the honest value for a line with no loss model in
        it -- plus ``1j`` times its ``beta``; ``zc`` is ``station_fit.z0``, the
        impedance the station voltages and currents themselves imply rather
        than the closed-form ``z0_model``.  The phasors are copied, so the
        reference outlives the run it came from.

        Args:
            wave: A :class:`MicrostripWave` measured on a line with no load.

        Returns:
            A :class:`LineReference` over the same stations and planes.
        """
        alpha = 0.0
        if wave.loss_fit is not None and wave.loss_fit.alpha is not None:
            alpha = float(wave.loss_fit.alpha)
        return cls(
            gamma=complex(alpha, float(wave.beta)),
            zc=complex(wave.station_fit.z0),
            station_x=np.array(wave.station_x, dtype=float),
            v_stations=np.array(wave.v_stations, dtype=complex),
            i_stations=np.array(wave.i_stations, dtype=complex),
        )

    def forward_ratio(self, x1: float, x2: float) -> complex:
        """``a+(x2) / a+(x1)`` on this reference [dimensionless].

        ``x1`` and ``x2`` are the planes the caller wants normalised against
        and must be this reference's own first and last station [m]: a ratio
        taken on other planes is a ratio of a different piece of line, and
        normalising a loaded run by it would silently divide out something that
        was never in it.  A mismatch raises instead.

        Args:
            x1, x2: The two planes of the run being normalised [m].

        Returns:
            The complex forward-amplitude ratio across them.

        Raises:
            ValueError: If the planes are not this reference's own (closer than
                a nanometre), or if it has no forward amplitude to divide by.
        """
        planes = (float(self.station_x[0]), float(self.station_x[-1]))
        for want, got in zip((float(x1), float(x2)), planes):
            if abs(want - got) > 1e-9:
                raise ValueError(
                    f"reference stations span {planes} m but the run's planes "
                    f"are {(float(x1), float(x2))} m: s21 is normalised by a "
                    f"ratio measured on the same two planes of the same mesh, "
                    f"or not at all")
        a = forward_wave_amplitude(self.v_stations, self.i_stations,
                                   self.station_x, self.gamma, self.zc,
                                   indices=[0, -1])
        if a[0] == 0.0:
            raise ValueError(
                "the reference has no forward amplitude at its first station: "
                "there is nothing to normalise by")
        return complex(a[1] / a[0])


def _blank_station_fit(reference_plane: float, beta: float,
                       sigma_beta: float | None,
                       n_stations: int) -> StationFit:
    """A station fit that carries no number at all: every field is n/a.

    A run too short to carry the drive (the mesh test takes eight steps)
    leaves both series identically zero, so there is no mode to fit and
    :func:`fit_station_impedance` refuses rather than inventing one.  The
    port's ``z0`` already falls back to NaN in that case, and this keeps a
    mesh-only run from raising as well.  The same object stands in for a fit
    that was refused on a record that *did* carry a wave -- there the wave was
    real and the fit was not -- so a report can say ``n/a`` on a row without
    branching on every row.
    """
    nan = float(np.nan)
    return StationFit(
        z0=complex(nan, nan), z0_sigma_stat=None, z0_sigma_beta=None,
        z0_sigma_total=None, phase_deg=nan, gamma_v=complex(nan, nan),
        gamma_i=complex(nan, nan), mode_purity=nan, beta=float(beta),
        sigma_beta=sigma_beta, reference_plane=float(reference_plane),
        n_stations=int(n_stations), residual_v=nan, residual_i=nan,
        residual_v_stations=np.full(int(n_stations), nan, dtype=complex),
        residual_i_stations=np.full(int(n_stations), nan, dtype=complex))


#: Least phase a bin may accumulate across the station span before its
#: ``beta`` is a fit and not noise [rad].  Two fifths of a turn is the floor
#: below which the curvature that ``sigma_beta_from_curvature`` reads is the
#: curvature of the misfit and not of a wave.
_BIN_SPAN_PHASE_MIN = 2.0 * np.pi / 5.0
#: How far below its own peak the weighted drive spectrum may be at a bin
#: before that bin is measuring the sweep's own leakage rather than the drive
#: [dB].  The weight is ``PULSE_WINDOW``, the same one the bins are read with.
_BIN_DRIVE_DB = -20.0
#: How far above one a bin's passivity may sit before it is a bug and not noise
#: [dimensionless].  Nothing is clamped: the row says BUG and quotes the number.
_BIN_PASSIVITY_SLACK = 1e-6


@dataclass(frozen=True)
class BinMetric:
    """What one frequency of the broadband sweep measured -- or why it did not.

    One instance per bin, in ascending frequency order.  Every number is the
    bin's own: nothing here is an average over the band, because an average of
    a bounded quantity is exactly what hides the bins that break the bound.
    ``refusal`` is the reason there is no number, and it is a string rather
    than an exception because one unusable frequency must not cost the rest
    their rows.

    Attributes:
        f: The frequency this bin was evaluated at [Hz].  It is *not* a DFT
            bin of the record: the phasors are summed directly at ``f``.
        beta: One-wave phase constant from the same station fit the tone path
            uses [rad/m].
        sigma_beta: Its standard error from the misfit curvature [rad/m], or
            ``None`` when no fit was made.
        s11_measured: ``|gamma_v|`` of the station fit, i.e. ``|S11|`` at the
            first station's own plane [dimensionless].
        s11_port: The same moved to the port plane [dimensionless].
        s21: ``|S21|`` across the station span, measured on two planes with the
            run's own ``zc`` -- or, when a reference was supplied, normalised by
            the load-free line exactly as the tone path does [dimensionless].
        passivity: ``|S11|^2 + |S21|^2`` of the two rows above [dimensionless].
        s21_power: The same span measured as a *net power* ratio instead of an
            amplitude ratio, ``sqrt(P(x2) / P(x1))`` with ``P`` the station's
            own ``0.5 Re(V conj(I))`` -- no single ``zc`` is assumed, so an
            impedance step along the span no longer shows up as loss or gain
            [dimensionless].  It is equal to ``|S21|`` only when the span is
            reflectionless, which is why it is quoted beside, not instead of,
            ``s21``.
        passivity_power: ``|S11|^2 + |S21_power|^2`` [dimensionless].
        eps_eff: Effective permittivity implied by ``beta`` [dimensionless].
        residual: Relative RMS misfit of the one-wave fit [dimensionless].
        refusal: Why this bin quotes nothing, or ``None`` when it does.
    """

    f: float
    beta: float = float("nan")
    sigma_beta: float | None = None
    s11_measured: float = float("nan")
    s11_port: float = float("nan")
    s21: float = float("nan")
    passivity: float = float("nan")
    s21_power: float = float("nan")
    passivity_power: float = float("nan")
    eps_eff: float = float("nan")
    residual: float = float("nan")
    refusal: str | None = None


def _station_power(v, i):
    """The power each station's own voltage and current carry [W].

    ``0.5 Re(V conj(I))`` is the same algebra ``power_current_check`` uses to
    imply a per-station impedance, and it needs no assumed ``zc``: a pure
    impedance step in a lossless wave leaves it unchanged, which is exactly
    the effect a single-``zc`` amplitude ratio cannot tell apart from loss.
    """
    v = np.asarray(v, dtype=complex)
    i = np.asarray(i, dtype=complex)
    return 0.5 * np.real(v * np.conj(i))


def _bin_metrics(spec, *, f, station_x, n_stations, x_port, reference,
                 drive_db) -> BinMetric:
    """Read one broadband bin off one weighted phasor vector.

    The weight is ``PULSE_WINDOW``, flat by default: see the sweep in
    :func:`microstrip_wave` for why, and for what tapering cost.

    This deliberately duplicates about thirty lines of the tone path above:
    the station voltages and currents sliced out of ``spec``, the one-wave fit
    of ``beta``, its curvature standard error, the station-impedance fit, the
    ``zc`` choice, the de-embedding of the reflection and the two-plane split
    of ``s21``.  It is a copy because the tone path is what 388 tests certify,
    line by line and number by number, and routing it through a shared helper
    would mean editing the code those tests pin in order to add a feature that
    they do not cover.  A copy can be wrong in a way the original is not; a
    refactor cannot be *checked* against the numbers the original already
    produced.  So the original stays byte for byte and this repeats what it
    does, at frequencies the original never sees.

    Everything that can go wrong at one frequency is a refusal, never an
    exception: a bin where the drive has no energy, where the phase across the
    span is too small to fit, where it passes ``pi`` and the one-wave branch is
    ambiguous, or where no impedance fit could be formed, says so in words and
    leaves the other bins alone.

    Args:
        spec: The phasor of the whole signal vector at this frequency, in the
            layout the time loop fills: ``n_stations`` station voltages, the
            port voltage, the full and truncated ground currents, then the
            station currents.  It is the same layout :func:`microstrip_wave`
            accumulates, so the slices below are the ones it takes.
        f: The frequency this phasor was summed at [Hz].
        station_x: ``(n_stations,)`` station positions [m].
        n_stations: How many stations the record carries.
        x_port: The port plane [m].
        reference: A :class:`LineReference` of the same line with no load, or
            ``None``.  Its ``gamma`` and ``zc`` split and normalise ``s21``
            exactly as they do on the tone path.
        drive_db: How far the windowed drive spectrum is below its own peak at
            this frequency [dB]; the guard below reads it, nothing guesses it.

    Returns:
        The bin's :class:`BinMetric`, with ``refusal`` set when there is no
        number to quote.
    """
    if not np.isfinite(drive_db) or drive_db < _BIN_DRIVE_DB:
        return BinMetric(f=float(f), refusal=(
            "the drive has no energy here: the weighted excitation spectrum is "
            f"{drive_db:.1f} dB below its own peak at this frequency, so what "
            "is left is the sweep's own leakage and not a measurement"))
    n_currents = int(n_stations) + 3
    v_stations = np.asarray(spec[:n_stations], dtype=complex)
    i_stations = -np.asarray(spec[n_currents:n_currents + n_stations],
                             dtype=complex)
    if not np.any(v_stations):
        return BinMetric(f=float(f), refusal=(
            "the record carries no voltage at this frequency"))
    d_probe = float(station_x[-1] - station_x[0])
    fit_one = fit_beta(station_x, v_stations, n_wave=1)
    beta = float(fit_one.beta)
    residual = float(fit_one.residual)
    span_phase = beta * d_probe
    if span_phase < _BIN_SPAN_PHASE_MIN:
        return BinMetric(f=float(f), beta=beta, residual=residual, refusal=(
            f"beta * span = {span_phase:.3f} rad is below the "
            f"{_BIN_SPAN_PHASE_MIN:.3f} rad floor: the phase across the "
            "stations is too small for a phase constant to be read off it"))
    if span_phase > np.pi:
        return BinMetric(f=float(f), beta=beta, residual=residual, refusal=(
            f"beta * span = {span_phase:.3f} rad passes pi, so the one-wave "
            "fit's branch is ambiguous at this frequency"))
    sigma_beta = sigma_beta_from_curvature(station_x, v_stations, beta)
    station_fit = None
    if np.any(i_stations):
        try:
            station_fit = fit_station_impedance(station_x, v_stations,
                                                i_stations, beta, sigma_beta)
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            station_fit = None
    if station_fit is None:
        # ``s21`` could still be formed against a reference, but ``S11`` and the
        # passivity built from it could not, and half a row is worse than none:
        # a passivity without its reflection is a number that looks fine.
        return BinMetric(f=float(f), beta=beta, sigma_beta=sigma_beta,
                         residual=residual, refusal=(
                             "no station-impedance fit could be formed at this "
                             "frequency" + ("" if reference is None else
                                            ", and a reference supplies zc "
                                            "but no reflection")))
    x1, x2 = float(station_x[0]), float(station_x[-1])
    gamma_measured = complex(station_fit.gamma_v)
    gamma_port = deembed_reflection(gamma_measured, beta,
                                    float(x1 - x_port))
    s11_measured = float(abs(gamma_measured))
    s11_port = float(abs(gamma_port))
    s21 = float("nan")
    if reference is not None:
        a1, a2 = forward_wave_amplitude(v_stations, i_stations, station_x,
                                        reference.gamma, reference.zc,
                                        indices=[0, -1])
        ratio = reference.forward_ratio(x1, x2)
        if a1 != 0.0 and ratio != 0.0:
            s21 = float(abs((complex(a2) / complex(a1)) / ratio))
    else:
        a1, a2 = forward_wave_amplitude(v_stations, i_stations, station_x, 0j,
                                        complex(station_fit.z0),
                                        indices=[0, -1])
        if a1 != 0.0:
            s21 = float(abs(line_s21(a1, x1, a2, x2, beta)[0]))
    # The same span on the power the stations themselves carry.  This branch
    # deliberately does not touch ``s21`` above: the amplitude row stays exactly
    # what it was, so the two can be compared line for line.
    s21_power = float("nan")
    p1 = _station_power(v_stations[0], i_stations[0])
    p2 = _station_power(v_stations[-1], i_stations[-1])
    if p1 > 0.0 and p2 > 0.0:
        s21_power = float(np.sqrt(float(p2) / float(p1)))
        if reference is not None:
            span_ratio = complex(reference.forward_ratio(x1, x2))
            if span_ratio != 0.0:
                s21_power = float(s21_power / abs(span_ratio))
    return BinMetric(
        f=float(f), beta=beta, sigma_beta=sigma_beta,
        s11_measured=s11_measured, s11_port=s11_port, s21=s21,
        passivity=float(s11_measured ** 2 + s21 ** 2),
        s21_power=s21_power,
        passivity_power=float(s11_measured ** 2 + s21_power ** 2),
        eps_eff=float((beta * C0 / (2.0 * np.pi * f)) ** 2),
        residual=residual)


def _bin_row(metric: BinMetric) -> str:
    """One bin as a report row: the numbers, or the refusal and its frequency."""
    if metric.refusal is not None:
        return f"REFUSED at {metric.f / 1e9:.2f} GHz: {metric.refusal}"

    def db(magnitude: float) -> str:
        """``20 log10`` of a magnitude, floored so a null cannot eat the row."""
        return f"{20.0 * np.log10(max(float(magnitude), 1e-30)):.1f} dB"

    passivity = metric.passivity
    # A passivity above one is a bug, not a number to be tidied away: the run
    # measured more power leaving the span than entered it.  Clamping it here
    # would hide exactly the thing the broadband sweep was built to catch.
    flag = ("BUG: passivity exceeds 1, not clamped: "
            if np.isfinite(passivity)
            and passivity > 1.0 + _BIN_PASSIVITY_SLACK else "")
    return (f"beta = {metric.beta:.2f} rad/m, "
            f"eps_eff = {metric.eps_eff:.4f}, "
            f"|S11| = {db(metric.s11_measured)} (measured plane) / "
            f"{db(metric.s11_port)} (port plane), "
            f"|S21| = {db(metric.s21)}, "
            f"{flag}passivity = |S11|^2 + |S21|^2 = {passivity:.6f}, "
            f"power-normalised: |S21| = {db(metric.s21_power)}, "
            f"passivity = |S11|^2 + |S21_power|^2 = "
            f"{metric.passivity_power:.6f}, "
            f"fit residual = {metric.residual:.4f}")


def _broadband_rows(bins, sink, *, span: float, nsteps: int) -> dict:
    """The broadband report: one row per bin, the summaries, and the figure.

    Rows come in frequency order and are named by the frequency they were
    evaluated at, ``bin 07 @ 4.92 GHz``, so a reader can find a bin in the
    figure without counting.  The summaries say how many bins were used and how
    many refused, what the record's frequency resolution is -- one over the
    span, which is the floor under any spacing of the bins -- and, in words,
    that nothing here is averaged across the band.

    Args:
        bins: The run's :class:`BinMetric` instances, ascending in frequency.
        sink: Where the passivity figure goes, or ``None``.
        span: The record's duration [s], which sets the resolution.
        nsteps: How many steps the record holds, for the caption.

    Returns:
        A ``dict[str, str]`` of rows, in the order they should be read.
    """
    rows = {}
    used = []
    for k, metric in enumerate(bins):
        rows[f"bin {k:02d} @ {metric.f / 1e9:.2f} GHz"] = _bin_row(metric)
        if metric.refusal is None:
            used.append(metric)
    refused = len(bins) - len(used)
    rows["bins used / refused"] = (
        f"{len(used)} / {refused} of {len(bins)}")
    resolution = 1.0 / float(span) if span > 0.0 else float("nan")
    rows["bin resolution (1/span)"] = (
        f"{resolution / 1e9:.4f} GHz (span = {span:.4e} s over {nsteps} steps)")
    rows["passivity across the band"] = (
        "no passivity number is averaged across the bins: each bin's "
        "passivity is its own row, because an average of a bounded quantity "
        "hides the bins that break the bound. A bin above 1 beyond the noise "
        "floor is printed as a bug and left unclamped.")

    if sink is not None:
        fig, ax = plt.subplots(figsize=(6.4, 3.4), constrained_layout=True)
        if used:
            fx = np.array([m.f for m in used]) / 1e9
            fy = np.array([m.passivity for m in used], dtype=float)
            ax.plot(fx, fy, "o-", color=viz.COL_PRIMARY, lw=1.0, ms=3.5,
                    label="$|S_{11}|^2 + |S_{21}|^2$")
            floor = min(float(np.nanmin(fy)), 1.0)
            ceiling = max(float(np.nanmax(fy)), 1.0)
        else:
            floor, ceiling = 0.0, 1.05
        ax.axhline(1.0, color=viz.COL_INK, ls="--", lw=0.9,
                   label="lossless (1.0)")
        if refused:
            rx = np.array([m.f for m in bins if m.refusal is not None]) / 1e9
            ax.plot(rx, np.full(rx.size, floor), "x", color=viz.COL_INK,
                    ms=5.0, ls="none", label="refused")
        pad = 0.08 * max(ceiling - floor, 0.05)
        ax.set_ylim(floor - pad, ceiling + pad)
        ax.set_xlabel("f [GHz]")
        ax.set_ylabel("passivity")
        ax.set_title("passivity against frequency, one bin at a time")
        ax.legend(loc="best", fontsize=7)
        sink.add_figure(
            "passivity-vs-frequency",
            "Passivity of the line bin by bin across the band", fig,
            caption=(
                f"$|S_{{11}}|^2 + |S_{{21}}|^2$ at {len(bins)} frequencies "
                f"spread evenly over the band, each read off one flat-weighted "
                f"record of {nsteps} steps of "
                f"the same pulse. The dashed line is 1.0, which a lossless "
                f"two-port cannot cross. Refused bins are marked on the floor "
                f"and carry the reason in their row. The record is "
                f"{span:.4e} s long, so no two bins closer than "
                f"{resolution / 1e9:.4f} GHz are independent."))
    return rows


def microstrip_wave(
    *,
    h: float = MS_H,
    w: float = MS_W,
    eps_r: float = MS_EPS_R,
    n_sub: int = MS_N_SUB,
    n_air: int = MS_N_AIR,
    n_top: int = MS_N_TOP,
    n_strip: int = MS_N_STRIP,
    n_clean: int = MS_N_CLEAN,
    n_pml: int = MS_N_PML,
    n_ref: int = MS_N_REF,
    n_line: int = MS_N_LINE,
    x_first: float = MS_X_FIRST,
    x_last: float = MS_X_LAST,
    n_stations: int = MS_N_STATIONS,
    f_target: float = MS_F_TARGET,
    nsteps: int = MS_NSTEPS,
    n_warm: int = None,
    drive: float = 1.0,
    keep_slice: bool = False,
    audit: bool = False,
    loads: tuple[Load, ...] = (),
    reference: LineReference | None = None,
    sink: FigureSink = None,
    excite: str = MS_EXCITE,
    band_lo: float = MS_BAND_LO_GHZ * 1e9,
    band_hi: float = MS_BAND_HI_GHZ * 1e9,
    n_bins: int = MS_N_BINS,
    f_pulse: float = MS_F_PULSE_GHZ * 1e9,
) -> MicrostripWave:
    """Drive a microstrip line and read its phasors, beta, Z0 and ground current.

    The line runs along ``x`` on a uniform mesh of one cell size (``h / n_sub``,
    isotropic on all three axes), the ground plane is the ``zmin`` PEC wall and
    the strip is a thin PEC sheet on the ``z = h`` node layer, ``n_strip`` cells
    wide.  The ground plane and the four lateral faces are PEC, and a matched
    layer of ``n_pml`` cells sits against the two ``x`` walls (behind the port
    and behind the far end of the strip) and against the two ``y`` walls.  The
    **top face is not a lid**: ``n_top`` cells of matched layer close the box at
    ``zmax``, so the air channel above the strip is terminated by an absorber
    and ``nz = n_sub + n_air + n_top``.  Passing ``n_top=0`` restores the plain
    PEC lid (and builds no layer at ``zmax``); that is not the default, because
    a PEC lid over a few air cells reflects the vertical field straight back
    onto the strip.  The strip runs from the port plane into the ``n_pml``-cell
    absorber on the far ``x`` wall, and it is the absorber, not the metal wall
    behind it, that terminates the guided mode: the layer takes the wave down
    before the wall is reached and returns only its own residual reflection,
    which is the 0.0075 that ``abs(gamma)`` reports.  That termination, not a
    short and not an open, decides how the phase constant may be measured.

    The phasors are ``v(z) = A exp(-j beta z) + B exp(+j beta z)``, so the
    angle between the first and the last station is not ``beta`` times the
    span, and the trouble is worse than a small bias: an angle is a principal
    value, so once the total phase across the span passes ``pi`` the
    two-station difference is aliased outright.  ``beta`` therefore comes from
    a least-squares fit over **all** the stations -- one wave for the number
    quoted, positive by construction because the fit only searches
    ``beta > 0``, and two waves alongside it.  The two-wave fit is what says
    how much wave the one-wave model had to swallow: it returns
    ``beta_two_wave`` and ``gamma = B/A``, so ``abs(gamma)`` is the standing
    wave, and ``fit_residual`` is the relative RMS the one-wave model left.
    The old first-to-last difference is still reported, as
    ``beta_two_station``, as a cross-check; it carries the sign of whichever
    way the phasors happened to rotate over the span, so it can come out
    negative.

    The other half of the measurement is the record length.  The line is a
    cavity until the launched transient has gone out to the far wall and come
    back, and every phasor transformed before that is a snapshot of a wave in
    flight.  At the default ``nsteps = 2400`` the record is 1800 steps, and by
    then the diagnostics have settled: the two-wave fit finds
    ``abs(gamma) = 0.0075``, the one-wave fit leaves a residual of 0.0095, and
    both read the same to a thousandth at 3600 and 4800 steps.  ``beta`` itself
    keeps creeping (232.45 rad/m at 2400 steps, 232.11 at 3600, 232.00 at
    4800), so quote it to three or four digits and not to five.  Read the
    residual and ``abs(gamma)`` before believing ``beta``: 1200 steps gives
    0.020 and 0.018, which is a record still filling up, not a measurement.
    ``geometry['beta_ambiguous']`` flags the one failure the two-station
    difference cannot survive on its own, the total phase across the span
    passing ``pi``.

    The default case is the recovered historical mesh, and the numbers in it are
    load-bearing: ``h = 1.6 mm`` resolved by ``n_sub = 4`` cells makes the cell
    size of the whole cubic mesh ``0.4 mm``, which in turn gives ``62 x 44 x 22``
    cells -- ``n_line = 54`` along the line, ``n_strip = 8`` across a 3.2 mm
    strip, ``n_clean = 12`` clear cells either side, ``n_air = 12`` above the
    strip and ``n_top = 6`` absorber cells on top.  The substrate is therefore
    ``h/4``, not the ``h/2`` a first-principles mesh would pick: 0.4 mm is the
    cell size the reference result was taken at, so ``n_sub`` is fixing the
    cell, not claiming four layers resolve the substrate.  Change any of these
    and the reported ``Z0`` and ``eps_eff`` are a different case, not a better
    one.

    This function is also the fixture the parsed-board path is pinned to:
    :func:`microstrip_reference_board` writes the cell counts above down as an
    :class:`emfit.board.MicrostripBoard`, and :func:`microstrip_wave_board` is
    the only route from a board file into this function.  A spec taken through
    that route has to reproduce the numbers of this default run exactly -- the
    spec adds bookkeeping (where each number came from), not physics.

    The port is a lumped current source on the ``E_z`` edges that span the
    substrate across the whole strip width at the port plane, ramped on over the
    warm-up so the record that is Fourier transformed holds a steady sine.  A
    :class:`DftAccumulator` then accumulates one phasor per signal over the
    remaining steps: the gap voltage at each probe station (a ``E_z`` column
    from the ground plane up to the strip), the port gap voltage, and the ground
    return current **twice** -- once over the whole domain and once over the
    physical strip extent only, using ``plate_current(..., y_extent=...)`` with a
    half-width that excludes the lateral matched-layer columns.  Comparing those
    two currents is the diagnostic point of the study: what a matched layer adds
    to a plate-current sum is not current any conductor carries.

    The drive frequency is snapped to an integer number of cycles over the
    accumulated record, because a tone off a bin leaks into its neighbours
    (see :class:`emfit.ports.DftAccumulator`).  ``geometry['f_target']`` keeps
    what was asked for and ``geometry['f']`` what was used.

    Args:
        h, w, eps_r: Substrate thickness, strip width and relative permittivity.
        n_sub: Substrate cells across ``h``; this sets the cell size.
        n_air: Air cells between the strip and the layer at ``zmax``.
        n_top: Matched-layer cells at ``zmax``; ``0`` puts a plain PEC lid there
            instead.  Must equal ``n_pml`` when non-zero, because one
            :class:`emfit.pml.PML` has a single thickness for all its walls.
        n_strip: Cells across the strip width.
        n_clean: Clean cells between the strip edge and the lateral layer.
        n_pml: Cells of matched layer at each absorbing face.
        n_ref: Line cells between the port plane and the layer behind it.
        n_line: Line cells from the port plane to the far end of the strip.
        x_first, x_last: Wanted first and last probe station, in metres; each is
            snapped to the nearest node layer and the positions actually used
            come back in ``station_x``.
        n_stations: Number of probe stations, equally spaced in the wanted span;
            at least 4, the minimum a two-wave fit needs.
        f_target: Wanted drive frequency [Hz].
        nsteps: Leapfrog steps; the first ``n_warm`` are warm-up and the rest
            are Fourier transformed, so this is the record length.
        n_warm: Warm-up steps, ``nsteps // 4`` by default.
        drive: Source amplitude [A].
        keep_slice: Accumulate the phasor of ``E_z`` over the whole mid-plane
            of the substrate as the run goes, and return it in
            ``slice_ez``.  Off by default: it is one DFT accumulator over
            ``nxn * nyn`` signals, which is nothing beside the field update on
            the mesh test but still wasted on a run that only wants numbers.
            When it is on and a ``sink`` is given, the plane is also drawn.
        loads: Lumped loads placed on the strip's ``E_z`` edges; see
            :func:`emfit.evolve.add_load` for what each of them is.
        reference: A :class:`LineReference` -- a load-free run of the same line
            -- to normalise ``s21`` against.  ``None`` (the default) reports the
            run's own ratio across the station span, one plane at each end and
            no fit between them, which is the whole of what a load-free record
            needs; a loaded record without one reports that ratio as a
            magnitude and recovers no impedance from it (see
            ``loaded_without_reference``).  When one is given, ``s21`` becomes
            the loaded run's forward-amplitude ratio across the station span
            divided by the reference's on the same planes, so the line's own
            delay and attenuation divide out exactly and only the load is
            left; ``s21_raw`` stays the loaded run's own ratio.  ``beta``,
            ``station_fit`` and every other number are untouched: the reference
            calibrates ``s21``, it does not re-derive the line.
        sink: Where to put the figure; ``None`` (the default) draws nothing.
        excite: ``"cw"`` (the default) drives the single tone this study has
            always used -- the warm-up ramp and the one DFT bin -- and
            ``"pulse"`` drives a Ricker wavelet centred on ``f_pulse`` so the
            whole band can be read off the one record.  A pulse run has no
            tone to ramp on, so it has no warm-up (``n_warm`` is forced to 0),
            and it is the only kind that fills ``bins``.
        band_lo, band_hi: Edges of the broadband sweep [Hz].  Read only when
            ``excite == "pulse"``; ``band_lo`` must be positive and
            ``band_hi`` above it.
        n_bins: How many frequencies the sweep reports; at least 2.
        f_pulse: Centre frequency of the Ricker excitation [Hz].

    Returns:
        A :class:`MicrostripWave`.

    Raises:
        ValueError: If the mesh or the station span leaves no interior to
            probe, if fewer than four stations survive, or if warm-up leaves no
            record to transform.
    """
    n_sub, n_air, n_strip = int(n_sub), int(n_air), int(n_strip)
    n_top = int(n_top)
    n_clean, n_pml, n_ref, n_line = int(n_clean), int(n_pml), int(n_ref), int(n_line)
    n_stations, nsteps = int(n_stations), int(nsteps)
    # The excitation is a choice between two runs, not a slider on one: "cw"
    # is the tone every number this study has quoted was taken at, "pulse" is
    # the waveform the broadband sweep is read off.  Anything else is refused
    # here rather than quietly run as a tone.
    if excite not in ("cw", "pulse"):
        raise ValueError(f"excite must be 'cw' or 'pulse', got {excite!r}")
    band_lo, band_hi = float(band_lo), float(band_hi)
    n_bins, f_pulse = int(n_bins), float(f_pulse)
    if band_lo <= 0.0:
        raise ValueError(f"band_lo must be positive, got {band_lo!r} Hz")
    if band_hi <= band_lo:
        raise ValueError(
            f"band_hi must be above band_lo, got {band_hi!r} Hz against "
            f"{band_lo!r} Hz")
    if n_bins < 2:
        raise ValueError(f"n_bins must be at least 2, got {n_bins}")
    if n_sub < 1 or n_air < 1 or n_strip < 1 or n_clean < 1 or n_pml < 1:
        raise ValueError(
            "n_sub, n_air, n_strip, n_clean and n_pml must all be at least 1")
    if n_line < 1 or n_ref < 0:
        raise ValueError(f"n_line must be at least 1 and n_ref at least 0")
    if n_stations < 4:
        raise ValueError(
            f"n_stations must be at least 4: the phase constant comes from a "
            f"two-wave fit, which needs four stations to leave a residual to "
            f"judge, got {n_stations}")

    if n_top < 0:
        raise ValueError(f"n_top must be at least 0, got {n_top}")
    if n_top and n_top != n_pml:
        raise ValueError(
            f"n_top={n_top} does not match n_pml={n_pml}: a single PML carries "
            f"one thickness for every wall it opens, so the zmax layer has to "
            f"share the lateral thickness. Pass n_top={n_pml} (or 0 for a "
            f"plain PEC lid)")

    cell = float(h) / n_sub
    nx = n_pml + n_ref + n_line
    ny = 2 * n_pml + n_strip + 2 * n_clean
    nz = n_sub + n_air + n_top
    grid = Grid.uniform(nx, ny, nz, nx * cell, ny * cell, nz * cell)
    cc = CellComplex(grid)

    substrate = lambda x, y, z: np.where(z <= float(h), float(eps_r), 1.0)  # noqa: E731
    m_eps, m_mu = material_matrices(grid, cc, eps_r=substrate)

    # --- where everything is ------------------------------------------------
    ix_port = n_pml + n_ref                  # node layer of the port plane
    k_strip = n_sub                          # node layer of the strip (z = h)
    j0 = n_pml + n_clean                     # first y point layer of the strip
    j1 = j0 + n_strip                        # one past the last one
    j_centre = j0 + n_strip // 2
    y_half = 0.5 * (n_strip + 2 * n_clean) * cell   # physical strip extent

    # --- PEC: the six walls plus the thin strip sheet ------------------------
    pec = np.array(cc.pec_edge_mask(), dtype=bool)
    strip = np.zeros(cc.n_edges, dtype=bool)
    x_cells = np.arange(ix_port, nx)                  # ex edges run along x
    j_points = np.arange(j0, j1 + 1)
    strip[cc.idx_ex(x_cells[:, None], j_points[None, :], k_strip)] = True
    x_points = np.arange(ix_port, nx + 1)             # ey edges run along y
    j_cells = np.arange(j0, j1)
    strip[cc.idx_ey(x_points[:, None], j_cells[None, :], k_strip)] = True
    pec |= strip

    # --- lumped loads: a cut in the sheet, and the element across it ---------
    # A ``series_r`` load frees the ``E_x`` edges of its node column, so the
    # strip is really interrupted there and the two halves talk only through
    # the element (and the fringing across the cut, which is part of the model).
    # The ``E_y`` edges stay pinned at both node layers bounding the cut, so the
    # end face of each half is still equipotential and the halves do not short
    # to each other along the rails.
    m_sigma = None
    loads_used = []
    if loads:
        sigma = np.zeros(cc.n_edges, dtype=float)
        eps = np.array(m_eps, dtype=float)
        for load in loads:
            ix_load = int(np.floor(float(load.position) / cell + 0.5))
            if not ix_port < ix_load < nx:
                raise ValueError(
                    f"load at {load.position!r} m lands on node column "
                    f"{ix_load}, outside the strip ({ix_port} < ix < {nx})")
            if load.kind == "series_r":
                edges = cc.idx_ex(np.array([ix_load]), j_points, k_strip).ravel()
                pec[edges] = False
                # One element spread over the ``len(edges)`` parallel paths.
                sigma[edges] += 1.0 / (edges.size * float(load.value))
            else:
                # ``n_strip`` columns in parallel, each ``n_sub`` edges in
                # series: C_edge = C * n_sub / n_strip reproduces C in total.
                edges = np.concatenate(
                    [column_path(cc, ix_load, int(j), 0, k_strip)
                     for j in range(j0, j0 + n_strip)])
                eps[edges] += float(load.value) * n_sub / n_strip
            loads_used.append({"kind": load.kind, "value": float(load.value),
                               "x": ix_load * cell, "column": ix_load,
                               "n_edges": int(edges.size)})
        m_sigma = sigma if np.any(sigma) else None
        m_eps = eps

    # ``walls`` replaces ``axes``: name every face, and add zmax only when a
    # top layer was actually asked for.
    pml_walls = ("xmin", "xmax", "ymin", "ymax") + (("zmax",) if n_top else ())
    # Optional energy audit: bin the work the matched layers remove by which
    # family of walls removed it.  ``None`` everywhere below when it is off, so
    # the stepping path stays byte-identical.
    absorbed = None
    if audit:
        absorbed = AbsorbedWork(groups={
            "end": ("xmin", "xmax"),
            "lateral": ("ymin", "ymax") + (("zmax",) if n_top else ())})
    pml = PML(grid, thickness_cells=n_pml, order=2, target=1e-4,
              walls=pml_walls, cc=cc, audit=absorbed)
    stepper_kwargs = {} if m_sigma is None else {"m_sigma": m_sigma}
    stepper = FITStepper(cc, m_eps, m_mu, dt=cfl_dt(grid), pec=pec, pml=pml,
                         **stepper_kwargs)
    dt = float(stepper.dt)

    # --- the record and its DFT bin ----------------------------------------
    # A pulse run has nothing to discard: the wavelet is the whole record, not
    # a tone that has to settle first, so there is no warm-up window to open.
    if excite == "pulse":
        n_warm = 0
    n_warm = nsteps // 4 if n_warm is None else int(n_warm)
    n_acc = nsteps - n_warm
    if n_acc < 1:
        raise ValueError(
            f"n_warm={n_warm} leaves no steps to transform out of nsteps={nsteps}")
    span = n_acc * dt
    f0 = max(1, int(round(float(f_target) * span))) / span

    # --- probe stations, snapped to node layers ----------------------------
    wanted = np.linspace(float(x_first), float(x_last), n_stations)
    js = np.floor(wanted / cell + 0.5).astype(int)
    js = np.clip(js, ix_port + 1, nx - 2)
    if np.unique(js).size < 2:
        raise ValueError(
            f"the stations collapse onto one node layer on this mesh: "
            f"x_first={x_first!r} m, x_last={x_last!r} m, cell={cell!r} m")
    station_x = js * cell
    columns = [column_path(cc, int(ix), j_centre, 0, k_strip) for ix in js]
    port_column = column_path(cc, ix_port, j_centre, 0, k_strip)
    port = LumpedPort("line", port_column, z0=MS_Z0_NOMINAL)
    port_edges = np.unique(np.concatenate(
        [column_path(cc, ix_port, int(j), 0, k_strip) for j in range(j0, j1 + 1)]))

    # --- the mid-plane map, when one was asked for -------------------------
    # ``E_z`` does not live on a node layer: the edge of a cell stops one
    # ``z`` cell short of the next one, so the field at the node layer between
    # two cells is not stored anywhere.  Their mean is that field to second
    # order, and ``k_mid = n_sub // 2`` is halfway up the substrate -- where a
    # microstrip's field is, neither grazing the ground plane nor gathered
    # under the strip edge.  The whole plane is accumulated at once, through a
    # second :class:`DftAccumulator` sharing ``f0`` and ``dt`` with the probe
    # one, so the map is at the same phase reference as every other phasor.
    k_mid = n_sub // 2
    slice_acc = DftAccumulator([f0], dt) if keep_slice else None
    slice_signals = (np.zeros(cc.nxn * cc.nyn, dtype=float)
                     if keep_slice else None)

    # --- the time loop -----------------------------------------------------
    acc = DftAccumulator([f0], dt)
    # The same record split in two, for the settledness check after the loop.
    # A DFT sum is linear in its samples and both accumulators take their phase
    # from the step index ``n``, so the second half is exactly ``spec`` minus
    # the first: one extra accumulator, not a second run.
    n_split = n_warm + n_acc // 2
    half_acc = DftAccumulator([f0], dt)
    current = np.zeros(cc.n_edges, dtype=float)
    n_currents = n_stations + 3        # station currents start here in signals
    signals = np.zeros(n_currents + n_stations, dtype=float)
    # A pulse run has no single bin to accumulate: the broadband sweep sums the
    # record at every frequency of the band, so the record itself has to be
    # kept.  A block, not one more :class:`DftAccumulator`, because every one
    # of those sums wants exactly the same steps -- and the drive beside it,
    # which is the only honest answer to what the source put into each bin.
    history = (np.zeros((nsteps, signals.size), dtype=float)
               if excite == "pulse" else None)
    drive_trace = np.zeros(nsteps) if excite == "pulse" else None
    for n in range(nsteps):
        if absorbed is not None and n == n_warm:
            # Warm-up work is not part of the settled record: bin only the
            # steps the DFT also sees.
            absorbed.reset()
        current[:] = 0.0
        if excite == "pulse":
            # The wavelet, not a tone.  ``t0 = 2 / f_pulse`` puts the peak well
            # past the start of the record: a Ricker evaluated at ``t = 0``
            # with that centre is ~1e-17 of its peak, so nothing is launched
            # at step 0 and the record is the whole of a clean pulse.
            drive_now = float(drive) * float(
                ricker(n * dt, 2.0 / f_pulse, f_pulse))
            current[port_edges] = drive_now
        else:
            ramp = min(1.0, (n + 1) / max(n_warm, 1))
            current[port_edges] = float(drive) * ramp * np.sin(2.0 * np.pi * f0 * n * dt)
        stepper.step(current)
        if n < n_warm:
            continue
        for i, col in enumerate(columns):
            signals[i] = edge_path_voltage(stepper.e, col)
        signals[n_stations] = port.voltage(stepper.e)
        signals[n_stations + 1] = plate_current(stepper.h, cc, ix_port, 0)
        signals[n_stations + 2] = plate_current(
            stepper.h, cc, ix_port, 0, y_extent=y_half)
        # Station currents, on the same node layers as the voltages.  The E_z
        # edges a column walks sit at the *node* layer x = ix * cell, but the
        # FY faces ``plate_current`` sums are the faces of an x *cell*, centred
        # half a cell further along.  Taking the two cells that straddle the
        # station and averaging them interpolates the current back onto the
        # node to second order; without it the ratio would carry beta * cell / 2
        # of spurious phase (about 2.7 deg at the default case).  The sum is
        # truncated like the port's, so it is the same physical current.
        for i, ix in enumerate(js):
            signals[n_currents + i] = 0.5 * (
                plate_current(stepper.h, cc, int(ix) - 1, 0, y_extent=y_half)
                + plate_current(stepper.h, cc, int(ix), 0, y_extent=y_half))
        acc.add(signals, n)
        if history is not None:
            history[n] = signals
            drive_trace[n] = drive_now
        if n < n_split:
            half_acc.add(signals, n)
        if slice_acc is not None:
            ez = stepper.e[cc.off_ez:cc.off_ez + cc.n_ez].reshape(
                cc.nxn, cc.nyn, cc.nz)
            slice_signals[:] = 0.5 * (ez[:, :, k_mid - 1] + ez[:, :, k_mid]).ravel()
            slice_acc.add(slice_signals, n)

    spec = acc.spectrum[0]
    spec_early = half_acc.spectrum[0]
    spec_late = (spec - spec_early if half_acc.n_samples
                 else np.zeros_like(spec))
    v_stations = np.asarray(spec[:n_stations], dtype=complex)
    v_port = complex(spec[n_stations])
    i_full = complex(spec[n_stations + 1])
    i_trunc = complex(spec[n_stations + 2])
    # Same reference-plane convention as ``z0`` below: the ground return is
    # summed in its own sense, antiparallel to the trace current, so negating
    # it refers the station impedance to the forward current.
    i_stations = -np.asarray(spec[n_currents:n_currents + n_stations], dtype=complex)

    # --- phase constant: multi-station fits, the old difference kept beside --
    # The two-station difference is what this study used to quote.  It only
    # looks at the ends of the span, so it cannot tell a standing wave from a
    # travelling one and it aliases once the phase across the span passes pi.
    # The fits use every station, and only search beta > 0, so the value they
    # return is the forward wave without a branch choice to make.
    d_probe = float(station_x[-1] - station_x[0])
    d_phase = float(np.angle(v_stations[-1] * np.conj(v_stations[0])))
    beta_two_station = -d_phase / d_probe
    fit_one = fit_beta(station_x, v_stations, n_wave=1)
    fit_two = fit_beta(station_x, v_stations, n_wave=2)
    beta = float(fit_one.beta)

    # --- has the record settled? -------------------------------------------
    # Nothing in a single phase constant says whether the waveform it was read
    # off had stopped changing: a record that is still filling, or still
    # climbing in amplitude, fits perfectly well and gives a ``beta`` that
    # depends on where the averaging window was opened.  Refitting the first
    # and the second half of the same window costs one accumulator and answers
    # exactly that question, so every run states it.
    def half_beta(samples):
        """One-wave ``beta`` on one half of the record, ``nan`` if empty."""
        if samples.size < n_stations or not np.any(samples):
            return float(np.nan)
        return float(fit_beta(station_x, samples[:n_stations],
                              n_wave=1).beta)

    beta_first_half = half_beta(spec_early)
    beta_second_half = half_beta(spec_late)

    # --- line impedance from the stations, with its uncertainty ------------
    # ``beta``'s own uncertainty comes from the curvature of the one-wave
    # misfit, which is the only route available: ``fit_beta`` returns no
    # covariance.  It is then carried into ``z0`` by refitting both series at
    # beta +- sigma_beta rather than by a derivative.
    sigma_beta = sigma_beta_from_curvature(station_x, v_stations, beta)

    # A diagnostic must not be able to take the run down with it.  ``beta`` is
    # already measured by this point, and a station-impedance fit is an
    # addition on top of it -- except that the transmission split below takes
    # its ``zc`` from this fit, so a record that loses it falls back to a
    # ``reference`` and, with neither, refuses where the split is made.  On a
    # strongly reflecting line the phase constant's own standard error can come
    # back as large as the phase constant itself, and
    # ``fit_station_impedance`` refuses such a beta outright (``ValueError``)
    # rather than quoting a number built from a trial at
    # ``beta - sigma_beta < 0``.  Catch that refusal at both
    # fit sites -- the loss-free one here, the loss-aware one below -- keep the
    # degraded field empty instead of half filled, and say what happened once
    # and not twice: a run that lost a diagnostic should not read like a run
    # that failed.
    station_fit_warned = False

    def warn_station_fit_skipped(exc: BaseException, what: str) -> None:
        """Warn -- once per run -- that a station-impedance fit was skipped."""
        nonlocal station_fit_warned
        if station_fit_warned:
            return
        station_fit_warned = True
        warnings.warn(
            f"The {what} station-impedance fit could not be formed on this "
            f"run ({type(exc).__name__}: {exc}), so that diagnostic is "
            "reported as unavailable (station_fit_ok is False).  It needs the "
            "phase constant's own standard error to be smaller than the "
            "phase constant, which a strongly reflecting line can put out of "
            "reach; the fit is skipped rather than quoted.  This touches that "
            "one diagnostic and one thing besides: the zc the transmission "
            "split needs, which now comes from reference=... when one was "
            "given and otherwise stops the run with this same reason.  Every "
            "other number -- beta, the phases, the powers -- is unaffected.",
            RuntimeWarning,
            stacklevel=2,
        )

    station_fit: StationFit | None = None
    station_fit_ok = True
    # The refusal, when there was one: the zc-without-a-reference path below
    # quotes it, so a caller who hits that refusal sees why this record had no
    # impedance long before it sees where the impedance was wanted.
    station_fit_error: BaseException | None = None
    if np.any(v_stations) and np.any(i_stations):
        try:
            station_fit = fit_station_impedance(station_x, v_stations,
                                               i_stations, beta, sigma_beta)
        except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
            station_fit_error = exc
            station_fit_ok = False
            warn_station_fit_skipped(exc, "loss-free")
    else:
        station_fit = _blank_station_fit(station_x[0], beta, sigma_beta,
                                         station_x.size)

    # --- the same fits with the decay free: loss, and its covariance -------
    # ``fit_beta`` holds the amplitude fixed in modulus, which is what a solver
    # with no loss model in it deserves.  The line does decay all the same --
    # the strip is a thin PEC sheet on a real mesh, and the grid disperses --
    # and pushing the decay into the fit is the only way to see it without a
    # second run.  Everything below is an *addition*: the lossless numbers
    # above are computed first and are not disturbed by any of it.
    slice_ez = (slice_acc.spectrum[0].reshape(cc.nxn, cc.nyn)
                if slice_acc is not None and slice_acc.n_samples else None)
    loss_fit = loss_fit_two = None
    if np.any(v_stations):
        loss_fit = fit_line(station_x, v_stations, n_wave=1)
        loss_fit_two = fit_line(station_x, v_stations, n_wave=2)

    def lossy_station_fit() -> StationFit | None:
        """``station_fit`` at ``alpha + j beta``, with ``alpha``'s wiggle in it.

        The propagation constant is the joint fit's, and the sensitivity to
        ``alpha`` is a central difference over ``alpha +- alpha_sigma`` on the
        whole refit -- the same treatment ``z0_sigma_beta`` gets, for the same
        reason: a linearisation of a quantity built from two ratios is not
        the thing itself.  ``z0_sigma_total`` is rebuilt because
        :class:`StationFit` has no slot for a fourth term and an incomplete
        budget must not be reported as if it were the whole of one.
        """
        if loss_fit is None or not np.any(i_stations):
            return station_fit          # nothing to fit: the lossless answer stays
        alpha_hat = 0.0 if loss_fit.alpha is None else float(loss_fit.alpha)
        fitted = fit_station_impedance(station_x, v_stations, i_stations,
                                       loss_fit.beta, loss_fit.beta_sigma,
                                       alpha=alpha_hat)
        sigma_alpha = loss_fit.alpha_sigma
        if loss_fit.alpha is None or sigma_alpha is None:
            return fitted
        step = float(sigma_alpha)
        z_plus = fit_station_impedance(station_x, v_stations, i_stations,
                                       loss_fit.beta, loss_fit.beta_sigma,
                                       alpha=alpha_hat + step).z0
        z_minus = fit_station_impedance(station_x, v_stations, i_stations,
                                        loss_fit.beta, loss_fit.beta_sigma,
                                        alpha=alpha_hat - step).z0
        sigma_alpha_z0 = 0.5 * abs(z_plus - z_minus)
        terms = [t for t in (fitted.z0_sigma_stat, fitted.z0_sigma_beta)
                 if t is not None]
        total = float(np.sqrt(sum(t * t for t in terms)
                              + sigma_alpha_z0 * sigma_alpha_z0)) if terms else None
        return replace(fitted, z0_sigma_total=total)

    # The same refusal, guarded the same way -- and ``warn_station_fit_skipped``
    # is shared, so a record that loses both fits still warns once.
    try:
        station_fit_lossy = lossy_station_fit()
    except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
        station_fit_lossy = None
        station_fit_ok = False
        warn_station_fit_skipped(exc, "loss-aware")

    line = Microstrip(w=float(w), h=float(h), eps_r=float(eps_r))
    beta_model = float(line.beta(f0))
    eps_eff = (beta * C0 / (2.0 * np.pi * f0)) ** 2
    # The minus sign is the reference-plane convention, not a result.  The port
    # current is taken from the ground-plane return, and ``plate_current`` sums
    # that return in its own sense, which is antiparallel to the trace current;
    # the raw ratio ``V / I`` therefore carries a spurious 180 deg.  Negating it
    # refers the impedance to the trace (forward) current, which is the
    # convention every transmission-line reference uses, and turns the phase
    # into the port's excess phase (about +17 deg here) instead of -163 deg.
    # The magnitude is untouched by the sign, so every ``|S|`` and every
    # tolerance is unaffected.
    z0 = (-complex(v_port / i_trunc)
          if i_trunc != 0.0 else complex(np.nan, np.nan))

    # --- reference planes: the reflection, measured here, quoted at the port --
    # ``station_fit`` refers its numbers to the first station; the port plane,
    # which is where a user's S-parameters are wanted, sits ``deembed_distance``
    # upstream of it.  The port plane is a node layer (``ix_port * cell``), the
    # same plane the lumped port drives, so nothing has to be interpolated.
    x_port = float(ix_port * cell)
    deembed_distance = float(station_x[0] - x_port)
    gamma_measured = (complex(station_fit.gamma_v) if station_fit is not None
                      else complex(np.nan, np.nan))
    gamma_port = (deembed_reflection(gamma_measured, beta, deembed_distance)
                  if np.isfinite(gamma_measured)
                  else complex(np.nan, np.nan))
    if np.isfinite(gamma_measured):
        # ``beta`` is real (``fit_beta`` returns a real phase constant and this
        # run has no loss model), so a plane shift may rotate the reflection
        # but must not touch its magnitude.  A difference here is a bug in the
        # factor or its sign, not physics.
        assert abs(abs(gamma_port) - abs(gamma_measured)) < 1e-9, (
            "de-embedding changed |gamma| with a real beta: "
            f"{abs(gamma_port)!r} against {abs(gamma_measured)!r}")

    # --- |S21|: what crossed the station span ------------------------------
    # A transmission coefficient needs two planes, and one station on each is
    # enough: on a uniform line the split into two travelling waves is exact
    # algebra, so the only unknowns a fit over a span could ever supply are
    # ``gamma`` and ``zc``.  Each of the two planes is therefore split on its
    # own -- see :func:`forward_wave_amplitude` -- and the ratio of the two
    # forward amplitudes is what arrived at the far plane for what left the
    # near one.  Two waves and not one, because the termination's reflection
    # has to be projected out of the amplitude rather than carried in it.
    #
    # No fit is the point.  A fit averages the field over the stations it is
    # given, so a discontinuity reads as a smeared step and a load sitting
    # between two stations reads as a fraction of itself; split on one plane,
    # the cut is measured rather than fitted.  ``gamma = 1j * beta`` with
    # ``beta`` real makes the propagation factor a pure rotation, so the
    # amplitude ratio carries the whole of the decay and the de-embedding
    # carries the delay only.  A caller who supplies a ``reference`` gets the
    # ratio of ratios instead, which removes ``beta`` and ``zc`` with it: see
    # :class:`LineReference`.
    #
    # ``zc`` for that split: the fit's own z0 when there is one, the
    # reference's when the fit was refused, and a refusal of our own when
    # neither exists.  The reference is exactly the right substitute -- it is
    # the same line, load-free, so its zc is the impedance this record's mode
    # has -- and without one there is nothing to measure the amplitude against.
    # The power-current check below takes the same number, for the same reason.
    if station_fit is not None:
        zc = complex(station_fit.z0)
    elif reference is not None:
        zc = complex(reference.zc)
    else:
        raise ValueError(
            "no station-impedance fit was formed on this record "
            f"({type(station_fit_error).__name__}: {station_fit_error}), so "
            "neither the split nor the power-current check has a zc to "
            "measure against.  Run it with reference=..., which takes zc "
            "from a load-free run of the same line; a record whose phase "
            "constant carries a standard error as large as itself cannot "
            "supply one of its own.")
    s21_planes = (float(station_x[0]), float(station_x[-1]))
    # A load with no reference: the metrics report the magnitude of ``s21`` and
    # derive no impedance from it, because the record's own station fit believes
    # in a continuity the cut breaks.  See the field of that name.
    loaded_without_reference = bool(loads_used) and reference is None
    s21 = raw_s21 = complex(np.nan, np.nan)
    if reference is not None:
        # Ratio of ratios, and the only thing here that needs no trust in
        # ``gamma``: the load-free run's wave crosses the same two planes
        # through the same ``gamma`` and ``zc`` at the same station positions,
        # so its ratio carries the same ``exp(-gamma d)`` -- the same floats --
        # and dividing it out removes the line exactly, delay, attenuation and
        # every error the two numbers are wrong by, because both runs are wrong
        # by it identically.  What is left is what the load did.
        if np.any(v_stations):
            a1, a2 = forward_wave_amplitude(
                v_stations, i_stations, station_x, reference.gamma,
                reference.zc, indices=[0, -1])
            reference_ratio = reference.forward_ratio(*s21_planes)
            if a1 != 0.0:
                raw_s21 = complex(a2) / complex(a1)
                s21 = raw_s21 / reference_ratio
    elif np.any(v_stations):
        # One plane at each end, the run's own measured ``zc`` chosen above and
        # its own measured ``beta`` for the delay, and no fit anywhere.  The
        # split is taken on each station's own phasors -- ``gamma = 0``, so
        # nothing is propagated yet -- which leaves the whole of the decay in
        # the ratio; :func:`line_s21` then takes the line's own delay out of it
        # with the measured ``beta``.
        a1, a2 = forward_wave_amplitude(
            v_stations, i_stations, station_x, 0j, zc, indices=[0, -1])
        if a1 != 0.0:
            s21, raw_s21 = line_s21(a1, s21_planes[0], a2, s21_planes[1],
                                    beta)

    # --- are the two phasors one mode?  The power-current check -------------
    # Cheap, assumption-free, and the only thing that can license a Poynting
    # vector later: for one travelling wave the power and the current at a
    # station imply the same impedance the fit does.  The port plane is checked
    # too, with the port current negated onto the forward sense like ``z0``.
    # ``zc`` was chosen above, where the split needed it: one property of the
    # mode serves both, and it is the same number the split used.
    z0_power, power_ratio = power_current_check(v_stations, i_stations, zc)
    z0_power_port, power_ratio_port = power_current_check(
        np.array([v_port]), np.array([-i_trunc]), z0)

    # --- the broadband sweep: one weighted sum per frequency ----------------
    # The tone path above reads one phasor at one bin.  A pulse has no such bin
    # -- it is broadband by construction -- so each frequency of the band is
    # summed straight off the kept record, at that frequency and no other.  The
    # drive's spectrum, taken through the same weight, is what says whether a
    # frequency is measuring the pulse or the sweep's own leakage
    # (``_bin_metrics`` reads that and refuses the bin).  Nothing here runs on a
    # tone: ``bins`` is empty unless the pulse was asked for.
    bins: tuple = ()
    if excite == "pulse":
        freqs = np.linspace(band_lo, band_hi, n_bins)
        # One ``weight``, used twice on purpose: it multiplies the record before
        # the bin phasor sum, and it multiplies the drive trace before the
        # guard that refuses a bin, so a bin's numbers and the test of whether
        # the drive reached that bin come off one estimator.  A guard taken
        # through a different weight would be judging one measurement by
        # another one's leakage.
        #
        # ``"rect"`` is the deliberate choice, not the default by omission.  A
        # taper exists to hide a truncation discontinuity, and this record has
        # none: it is a closed transient, the Ricker is ~1e-17 of its peak at
        # t = 0, and the packet is through the PML before the record ends.
        #
        # The cost of tapering anyway was measured on the default coupon
        # (2..12 GHz, 25 bins, 2400 steps) against the cw twin at 5.83 GHz: the
        # bin nearest that tone read |S21| = 1.24903 through a Hann weight,
        # 0.99017 flat and 0.98126 for the cw twin; passivity 1.563072, 0.980464
        # and 0.962932; one-wave residual 0.065, 0.0066 and 0.0095; and the bins
        # flagged "BUG: passivity exceeds 1" 12, 0 and 0.  The mechanism is that
        # a taper is not amplitude-neutral for a transient that does not fill
        # the record -- it multiplies the packet by a curve that is still moving
        # under it -- so the per-bin phasors stop being one mode, and the fits
        # that read beta, zc and S21 off them are then reading the taper.
        if PULSE_WINDOW == "rect":
            weight = np.ones(nsteps)
        elif PULSE_WINDOW == "hann":
            weight = np.hanning(nsteps)
        else:
            raise ValueError(
                f"PULSE_WINDOW must be 'rect' or 'hann', not {PULSE_WINDOW!r}")
        n_index = np.arange(nsteps, dtype=float)
        drive_sum = np.exp(
            -2j * np.pi * np.outer(freqs, dt * n_index)) @ (drive_trace * weight)
        drive_peak = float(np.max(np.abs(drive_sum)))
        if drive_peak > 0.0:
            drive_db = 20.0 * np.log10(
                np.maximum(np.abs(drive_sum) / drive_peak, 1e-300))
        else:
            drive_db = np.full(freqs.size, -np.inf)
        spectra = np.empty((freqs.size, history.shape[1]), dtype=complex)
        for k, f in enumerate(freqs):
            spectra[k] = (np.exp(-2j * np.pi * f * dt * n_index)
                          @ (history * weight[:, None]))
        bins = tuple(
            _bin_metrics(spectra[k], f=float(f), station_x=station_x,
                         n_stations=n_stations, x_port=x_port,
                         reference=reference, drive_db=float(db))
            for k, (f, db) in enumerate(zip(freqs, drive_db)))

    geometry = {
        "nx": nx, "ny": ny, "nz": nz, "cell": cell,
        "length": nx * cell, "width": ny * cell, "height": nz * cell,
        "h": float(h), "w": float(w), "eps_r": float(eps_r),
        "n_sub": n_sub, "n_air": n_air, "n_top": n_top, "n_strip": n_strip,
        "n_clean": n_clean, "n_pml": n_pml, "n_ref": n_ref, "n_line": n_line,
        "ix_port": ix_port, "ix_far": nx, "k_strip": k_strip,
        "k_mid": k_mid, "z_mid": k_mid * cell, "keep_slice": bool(keep_slice),
        "j_strip": (j0, j1), "j_centre": j_centre, "y_extent": y_half,
        "station_cells": [int(v) for v in js],
        "f": f0, "f_target": float(f_target), "dt": dt,
        "nsteps": nsteps, "n_warm": n_warm, "n_acc": n_acc,
        "audit": bool(audit),
        "n_edges": cc.n_edges, "n_faces": cc.n_faces,
        "beta_ambiguous": bool(abs(beta) * d_probe > np.pi),
        "excite": excite, "band_lo": band_lo, "band_hi": band_hi,
        "n_bins": n_bins, "f_pulse": f_pulse,
    }

    if sink is not None:
        drove = (f"driven at {f0 / 1e9:.3f} GHz" if excite != "pulse"
                 else f"driven broadband, phasors shown at {f0 / 1e9:.3f} GHz")
        fig, (ax_mag, ax_phase) = plt.subplots(1, 2, figsize=(9.2, 3.2),
                                              constrained_layout=True)
        ax_mag.plot(station_x * 1e3,
                    20.0 * np.log10(np.maximum(np.abs(v_stations), 1e-30)),
                    "o-", color=viz.COL_PRIMARY, lw=1.0)
        ax_mag.set_xlabel("x [mm]")
        ax_mag.set_ylabel("$|V|$ [dB]")
        ax_mag.set_title("gap voltage along the line")
        phase = np.unwrap(np.angle(v_stations))
        ax_phase.plot(station_x * 1e3, phase, "o-", color=viz.COL_PRIMARY,
                      lw=1.0, label="measured")
        ax_phase.plot(station_x * 1e3,
                      phase[0] - beta_model * (station_x - station_x[0]),
                      ls=":", lw=0.9, color=viz.COL_INK,
                      label="Hammerstad-Jensen")
        ax_phase.set_xlabel("x [mm]")
        ax_phase.set_ylabel("phase [rad]")
        ax_phase.set_title("phase, and the closed form")
        ax_phase.legend(loc="best", fontsize=7)
        sink.add_figure(
            "line-phasors", "Probe voltage magnitude and phase along the line", fig,
            caption=(f"{n_stations} stations from "
                     f"{station_x[0] * 1e3:.2f} to {station_x[-1] * 1e3:.2f} mm, "
                     # For a pulse run the drive is not at ``f0``: the phasors
                     # plotted are ``f0``'s, but the record itself is broadband.
                     f"{drove}, {nsteps} steps of "
                     f"{dt:.3e} s. The dotted ramp is the closed-form phase "
                     "slope at the same frequency."))

    # --- the mid-plane map, drawn from the phasor ---------------------------
    # ``plot_field_slice`` wants a whole edge vector and a component block in
    # it, so the plane is written back into two ``E_z`` cells of an otherwise
    # empty vector and drawn through the ordinary slice routine: the same
    # co-location, the same PEC outline, one picture per run rather than a
    # private copy of the plotting code.  The phasor is complex and a colour
    # map is not, so the real part is what is drawn -- the field at the phase
    # the accumulated record starts on.
    if sink is not None and slice_ez is not None:
        ez_block = np.zeros((cc.nxn, cc.nyn, cc.nz), dtype=complex)
        ez_block[:, :, max(k_mid - 1, 0)] = slice_ez
        ez_block[:, :, k_mid] = slice_ez
        vec = np.zeros(cc.n_edges, dtype=float)
        vec[cc.off_ez:cc.off_ez + cc.n_ez] = np.real(ez_block).ravel()
        z_mid = k_mid * cell
        fig_s, ax_s = viz.plot_field_slice(
            grid, vec, "EZ", axis="z", index=max(k_mid - 1, 0),
            title=rf"$\mathrm{{Re}}\,E_z$ at $z = {z_mid * 1e3:.2f}$ mm")
        ax_s.axvline(ix_port * cell, color=viz.COL_INK, lw=0.8, ls="--")
        ax_s.axhline(j0 * cell, color=viz.COL_INK, lw=0.8, ls="--")
        ax_s.axhline(j1 * cell, color=viz.COL_INK, lw=0.8, ls="--")
        sink.add_figure(
            "midplane-ez", "Mid-plane E_z of the driven microstrip", fig_s,
            caption=(f"Real part of the {f0 / 1e9:.3f} GHz phasor of $E_z$ on "
                     f"the node layer $z = {z_mid * 1e3:.2f}$ mm, halfway up "
                     f"the {float(h) * 1e3:.2f} mm substrate, from the mean of "
                     f"the two cells that straddle it on the "
                     f"{'x'.join(str(n) for n in (nx, ny, nz))}-cell mesh of "
                     f"{cell * 1e3:.1f} mm cells. Dashed: the port plane and "
                     "the two strip edges. Phase referred to the first "
                     "accumulated step; the backward wave (|gamma| = "
                     f"{abs(fit_two.gamma):.4f}) is why the pattern is not a "
                     "plain moving wave."))

    # The audit's bookkeeping, when it was asked for: energy the layer removed
    # over the same settled record the DFT saw, split by wall family.  ``length``
    # is the span between the two transmisson planes, so the implied loss is a
    # bound over exactly the distance ``s21`` was de-embedded across.
    if loads_used:
        geometry["loads"] = tuple(loads_used)

    power_balance = None
    if absorbed is not None and absorbed.steps:
        fractions = absorbed.fractions()
        lateral_fraction = float(fractions.get("lateral", 0.0))
        power_balance = {
            "work": {name: absorbed.total(name) for name in absorbed.work["e"]},
            "steps": int(absorbed.steps),
            "length": float(s21_planes[1] - s21_planes[0]),
            "fractions": fractions,
            "lateral_fraction": lateral_fraction,
            "end_fraction": float(fractions.get("end", 0.0)),
            "implied_s21": float(np.sqrt(max(0.0, 1.0 - lateral_fraction))),
        }

    return MicrostripWave(
        geometry=geometry,
        station_x=station_x,
        v_stations=v_stations,
        i_stations=i_stations,
        v_port=v_port,
        i_ground_full=i_full,
        i_ground_truncated=i_trunc,
        y_extent=y_half,
        beta_two_station=float(beta_two_station),
        beta=beta,
        beta_two_wave=float(fit_two.beta),
        beta_first_half=beta_first_half,
        beta_second_half=beta_second_half,
        gamma=complex(fit_two.gamma),
        fit_residual=float(fit_one.residual),
        beta_model=beta_model,
        z0=z0,
        station_fit=station_fit,
        gamma_port=gamma_port,
        deembed_distance=deembed_distance,
        s21=s21,
        s21_raw=raw_s21,
        s21_planes=s21_planes,
        power_z0=z0_power,
        power_ratio=power_ratio,
        power_z0_port=float(z0_power_port[0]),
        power_ratio_port=float(power_ratio_port[0]),
        z0_model=float(line.z0),
        eps_eff=float(eps_eff),
        eps_eff_model=float(line.eps_eff),
        loss_fit=loss_fit,
        loss_fit_two=loss_fit_two,
        station_fit_lossy=station_fit_lossy,
        slice_ez=slice_ez,
        power_balance=power_balance,
        station_fit_ok=station_fit_ok,
        loaded_without_reference=loaded_without_reference,
        bins=bins,
    )


def microstrip_reference_board() -> MicrostripBoard:
    """The default cross-section of :func:`microstrip_wave` as a board spec.

    Every number is one of the ``MS_*`` constants the default run uses, so the
    spec and the mesh cannot drift apart: the cell size is ``MS_H / MS_N_SUB``
    and the outline is the number of cells the run allocates on each axis.  The
    result describes the historical ``62 x 44`` mesh at ``0.4 mm``, a port plane
    ``MS_N_PML + MS_N_REF`` node layers in from the ``xmin`` wall, and a strip
    that runs out into the far absorber.

    Returns:
        An :class:`emfit.board.MicrostripBoard` in metres.
    """
    cell = MS_H / MS_N_SUB
    x_port = (MS_N_PML + MS_N_REF) * cell
    x_far = (MS_N_PML + MS_N_REF + MS_N_LINE) * cell
    return MicrostripBoard(
        length=x_far,
        width=(2 * MS_N_PML + MS_N_STRIP + 2 * MS_N_CLEAN) * cell,
        h=MS_H,
        eps_r=MS_EPS_R,
        w=MS_W,
        x_port=x_port,
        x_far=x_far,
        name="reference",
    )


def microstrip_wave_board(
    spec: MicrostripBoard,
    *,
    n_sub: int = MS_N_SUB,
    n_air: int = MS_N_AIR,
    n_top: int = MS_N_TOP,
    n_pml: int = MS_N_PML,
    x_first: float = MS_X_FIRST,
    x_last: float = MS_X_LAST,
    n_stations: int = MS_N_STATIONS,
    f_target: float = MS_F_TARGET,
    nsteps: int = MS_NSTEPS,
    keep_slice: bool = False,
    audit: bool = False,
    reference: LineReference | None = None,
    sink: FigureSink = None,
    excite: str = MS_EXCITE,
    band_lo: float = MS_BAND_LO_GHZ * 1e9,
    band_hi: float = MS_BAND_HI_GHZ * 1e9,
    n_bins: int = MS_N_BINS,
    f_pulse: float = MS_F_PULSE_GHZ * 1e9,
) -> MicrostripWave:
    """Run :func:`microstrip_wave` on a coupon that came out of a board file.

    This is the one bridge from a :class:`emfit.board.MicrostripBoard` to the
    solver: the spec is asked for its integer cell counts
    (:meth:`emfit.board.MicrostripBoard.to_cell_counts`, which is where a
    geometry that does not land on the mesh is refused) and the resulting counts
    and dimensions are handed straight to :func:`microstrip_wave`.  Nothing is
    adjusted here -- a strip that stops short of the far wall, or a clearance
    that is not a whole number of cells, raises there instead of being rounded
    into something the caller did not ask for.

    The knobs are the ones the spec does not determine: how finely ``h`` is
    resolved (``n_sub``, which sets the cell size and hence every count), the air
    and top-layer thicknesses, the absorber thickness, and the probe and record
    settings.  A bigger coupon needs a different ``n_sub``, not a set of counts:
    the counts follow from the spec.

    Args:
        spec: The coupon, in metres.
        n_sub: Substrate cells across ``spec.h``; this sets the cell size.
        n_air: Air cells between the strip and the layer at ``zmax``.
        n_top: Matched-layer cells at ``zmax``; ``0`` puts a plain PEC lid there
            instead, and a non-zero value must equal ``n_pml``.
        n_pml: Matched-layer cells at each absorbing face, and the thickness
            taken out of the port plane and out of the clearance before either
            is counted in cells.
        x_first, x_last: Wanted first and last probe station [m].
        n_stations: Number of probe stations along the line.
        f_target: Wanted drive frequency [Hz].
        nsteps: Leapfrog steps; the record is what is left after warm-up.
        keep_slice: Whether to accumulate the mid-plane phasor block, which is
            what the ``midplane-ez`` figure is drawn from; it is a separate
            accumulation through the time loop, so a run that wants no picture
            should leave it off.
        audit: Whether to build the absorbed-work accounting; ``False`` (the
            default) skips it because it costs substantially more than the
            solve itself.
        reference: A :class:`LineReference` of the same coupon with no load,
            passed straight through to :func:`microstrip_wave`, which
            normalises ``s21`` against it.  ``None`` (the default) reports the
            un-normalised station-plane ratio, which for a loaded record is a
            magnitude with no impedance behind it.
        sink: Where to put the figure; ``None`` (the default) draws nothing.
        excite: Passed straight through to :func:`microstrip_wave`: ``"cw"``
            is the single tone, ``"pulse"`` the broadband run whose bins the
            sweep is read off.
        band_lo, band_hi: Edges of the broadband sweep [Hz], passed straight
            through.
        n_bins: How many frequencies the sweep reports, passed straight
            through.
        f_pulse: Centre frequency of the Ricker excitation [Hz], passed
            straight through.

    The spec's ``loads`` are passed straight through: a
    :class:`emfit.board.Load` carries its position in metres and its value in
    SI, so the mesh quantises it exactly as :func:`microstrip_wave` would.

    Returns:
        A :class:`MicrostripWave`.

    Raises:
        ValueError: If the spec is not representable on the mesh, or for any
            reason :func:`microstrip_wave` raises.
    """
    counts = spec.to_cell_counts(n_sub=n_sub, n_pml=n_pml)
    return microstrip_wave(
        h=spec.h,
        w=spec.w,
        eps_r=spec.eps_r,
        n_sub=int(n_sub),
        n_air=n_air,
        n_top=n_top,
        n_strip=counts["n_strip"],
        n_clean=counts["n_clean"],
        n_pml=n_pml,
        n_ref=counts["n_ref"],
        n_line=counts["n_line"],
        x_first=x_first,
        x_last=x_last,
        n_stations=n_stations,
        f_target=f_target,
        nsteps=nsteps,
        keep_slice=keep_slice,
        audit=audit,
        loads=spec.loads,
        reference=reference,
        sink=sink,
        excite=excite,
        band_lo=band_lo,
        band_hi=band_hi,
        n_bins=n_bins,
        f_pulse=f_pulse,
    )


def _run_microstrip(values: Mapping[str, Any], sink: FigureSink) -> dict:
    """Study wrapper: one default wave run, reported as formatted strings."""
    loads = ()
    load_kind = values.get("load_kind", "none")
    if load_kind != "none":
        value = float(values.get("load_value", 100.0))
        if load_kind == "shunt_c":
            value *= 1e-12
        loads = (Load(float(values.get("load_at_mm", 15.2)) * 1e-3,
                      load_kind, value),)
    # The board this run will actually mesh.  ``w`` on its own does not move the
    # strip -- the strip is ``n_strip`` cells wide -- so the width handed to the
    # closed form below is the width the mesh contains, not a separate wish.
    board_h = float(values.get("h_mm", MS_H * 1e3)) * 1e-3
    board_eps = float(values.get("eps_r", MS_EPS_R))
    strip_cells = int(values.get("strip_cells", MS_N_STRIP))
    board_cell = board_h / MS_N_SUB
    board_w = strip_cells * board_cell
    board_changed = (not np.isclose(board_h * 1e3, MS_H * 1e3)
                     or not np.isclose(board_eps, MS_EPS_R)
                     or strip_cells != MS_N_STRIP)
    # The excitation, in the units the knobs are given in: the three frequencies
    # arrive in GHz and are hertz from here on, which is what the solver reads.
    # ``cw`` is the single tone, and the default, so the report of a run that
    # says nothing about this is the one it always was.
    excite = str(values.get("excite", MS_EXCITE))
    band_lo = float(values.get("band_lo", MS_BAND_LO_GHZ)) * 1e9
    band_hi = float(values.get("band_hi", MS_BAND_HI_GHZ)) * 1e9
    n_bins = int(values.get("n_bins", MS_N_BINS))
    f_pulse = float(values.get("f_pulse", MS_F_PULSE_GHZ)) * 1e9
    # A loaded run cannot measure its own line constant: the cut breaks the
    # one-onward-wave assumption the station fit rests on.  So it is given a
    # load-free twin on the identical mesh, whose decomposition supplies the
    # only two things the ratio needs -- ``gamma``/``zc`` for the split and the
    # ratio ``a+(x2)/a+(x1)`` of the line itself.  The twin's figures are
    # rendered into a throwaway sink: they are not this run's output, and
    # ``dump_figures`` below only ever sees the real one.
    reference = None
    if loads:
        twin = microstrip_wave(
            f_target=float(values["f0"]) * 1e9,
            nsteps=int(values["nsteps"]),
            n_pml=int(values["npml"]),
            n_top=int(values["npml"]),
            h=board_h, w=board_w, eps_r=board_eps, n_strip=strip_cells,
            excite=excite, band_lo=band_lo, band_hi=band_hi,
            n_bins=n_bins, f_pulse=f_pulse,
            keep_slice=False,
            audit=False,
            sink=FigureSink())
        reference = LineReference.from_wave(twin)

    result = microstrip_wave(
        f_target=float(values["f0"]) * 1e9,
        nsteps=int(values["nsteps"]),
        n_pml=int(values["npml"]),
        n_top=int(values["npml"]),
        h=board_h,
        w=board_w,
        eps_r=board_eps,
        n_strip=strip_cells,
        excite=excite, band_lo=band_lo, band_hi=band_hi,
        n_bins=n_bins, f_pulse=f_pulse,
        keep_slice=True,
        audit=True,
        loads=loads,
        reference=reference,
        sink=sink)
    g = result.geometry
    gain = abs(result.i_ground_full) / max(abs(result.i_ground_truncated), 1e-300)
    # A record whose station fit was refused still has a report to write, and
    # every row below reads its numbers off ``sf``: a blank fit says ``n/a`` on
    # all of them through ``num()`` instead of raising nine-tenths of the way
    # through a table.
    sf = (result.station_fit if result.station_fit is not None
          else _blank_station_fit(result.station_x[0], result.beta, None,
                                  len(result.station_x)))

    def num(value, unit, spec=".4f"):
        """Format an optional number, or ``n/a`` when the fit could not give it."""
        if value is None or not np.isfinite(value):
            return "n/a"
        return f"{value:{spec}} {unit}".strip()

    def decibel(magnitude):
        """``20 log10`` of a magnitude, or ``None`` when no magnitude exists."""
        if magnitude is None or not np.isfinite(magnitude) or magnitude <= 0.0:
            return None
        return 20.0 * np.log10(magnitude)

    # The power-current check, summarised: the mean is not the point, the
    # spread and the worst station are, because a mode that is not one mode
    # fails first where it is least like a plain travelling wave.
    z0_power = np.asarray(result.power_z0, dtype=float)
    ratio = np.asarray(result.power_ratio, dtype=float)
    usable = np.isfinite(z0_power) & np.isfinite(ratio)
    gamma_abs = abs(sf.gamma_v)
    bound = (((1.0 + gamma_abs) / (1.0 - gamma_abs)) ** 2 - 1.0
             if gamma_abs < 1.0 else float("inf"))
    if np.any(usable):
        worst = int(np.argmax(np.abs(ratio[usable] - 1.0)))
        power_z0_row = (f"mean {np.mean(z0_power[usable]):.4f} ohm, spread "
                        f"{np.ptp(z0_power[usable]):.4f} ohm over "
                        f"{int(usable.sum())} stations")
        power_ratio_row = (
            f"mean {np.mean(ratio[usable]):.6f}, spread "
            f"{np.ptp(ratio[usable]):.2e}, worst "
            f"{result.station_x[usable][worst] * 1e3:.2f} mm at "
            f"{ratio[usable][worst]:.6f}")
    else:
        power_z0_row = power_ratio_row = "n/a: no station carried a current"
    if np.isfinite(bound):
        power_ratio_row += (
            f"; a passive reflection of |gamma| = {gamma_abs:.4f} can move it "
            f"by at most {100.0 * bound:.1f} %, further out than that is not a "
            "standing wave but two things that are not one mode")

    s11_measured_db = decibel(gamma_abs)
    s11_port_db = decibel(abs(result.gamma_port))
    if s11_port_db is None:
        g1_row = "n/a: this run fitted no reflection"
    elif s11_port_db < -20.0:
        g1_row = (f"met: {s11_port_db:.2f} dB on the port plane, below the "
                  "-20 dB the goal asks for")
    else:
        g1_row = (f"NOT met: {s11_port_db:.2f} dB on the port plane, above "
                  "the -20 dB the goal asks for")

    # A reflection this small reads more easily as a mismatch than as a
    # decibel, and the same number bounds how far a standing wave can move the
    # power ratio two rows above -- which is what makes that spread one
    # observation and not two.
    vswr = ((1.0 + gamma_abs) / (1.0 - gamma_abs)
            if gamma_abs < 1.0 else float("inf"))
    if np.any(usable) and np.isfinite(bound):
        bound_row = (
            f"observed spread {np.ptp(ratio[usable]):.2e} against the "
            f"{100.0 * bound:.1f} % ({bound:.4f}) that |gamma| = "
            f"{gamma_abs:.4f} can put there: it sits inside the bound, so it is "
            "this reflection seen again and not a second error")
    else:
        bound_row = "n/a: no station carried a current to compare"

    # |S21| needs two planes and the row has to say which two.  Each plane is
    # split on its own station's phasors, so no fit stands between them.  On a
    # loaded record the ``zc`` and ``beta`` that split and de-embed come from
    # the load-free twin (this record's own fit spans the cut), and the row
    # prints the ratio of the two plane ratios.
    #
    # A load with no ``reference`` is the one case where the number must come
    # with a refusal attached: the split takes its ``zc`` from the record's own
    # station fit, and that fit believes in one onward wave at every station,
    # which is exactly what the cut breaks.  The magnitude is still a
    # measurement of the two planes; an impedance read out of its phase is not,
    # and the row says so instead of quoting one.
    s21_db = decibel(abs(result.s21))
    x1, x2 = result.s21_planes
    # The tolerance the row below prints and the comparison it makes are
    # one number, so the words cannot drift away from the test.
    s21_tolerance = 0.01
    if s21_db is not None:
        departure = abs(result.s21) - 1.0
        if result.loaded_without_reference:
            s21_row = (
                f"{abs(result.s21):.6f} = {s21_db:.3f} dB between x = "
                f"{x1 * 1e3:.2f} mm and x = {x2 * 1e3:.2f} mm, "
                f"{(x2 - x1) * 1e3:.2f} mm apart: one plane at each end, its "
                "forward wave taken from the algebra that splits v and i with "
                "this record's own zc, and the two divided, so no fit stands "
                "between the planes and this magnitude is measured.  There is "
                "no impedance to be read out of it.  This record carried "
                "a load, the load sits between the two planes, and every "
                "station-impedance fit on the record -- the one whose z0 the "
                "split took its zc from included -- assumes one onward "
                "travelling wave at all the stations, which is the continuity "
                "the cut breaks.  The load needs a normalisation this run did "
                "not carry: a direct caller of microstrip_wave has to run the "
                "same mesh with no load and hand that record to reference=, "
                "and the line divides itself out of the delay and the loss "
                "alike.  The microstrip study arranges that twin itself, so a "
                "loaded study run does not land on this wording")
            s21_unity_row = (
                f"{100.0 * departure:+.3f} % from unity is the load and the "
                "line together, and this run cannot say which is which: some "
                "of it is power the load took, some is power the surrounding "
                "matched layers took, and separating the two takes the "
                "load-free reference.  The exp(-alpha L) row below is fitted "
                "across the same span with the load inside it, so it inherits "
                "the same doubt")
        else:
            s21_row = (
                f"{abs(result.s21):.6f} = {s21_db:.3f} dB between x = "
                f"{x1 * 1e3:.2f} mm and x = {x2 * 1e3:.2f} mm, "
                f"{(x2 - x1) * 1e3:.2f} mm apart: one plane at each end, its "
                "forward wave taken from the algebra that splits v and i, and "
                "the two divided.  No fit stands between the planes -- a fit "
                "would average the field over the stations it was handed, and "
                "a load reads as a fraction of itself that way.  With a load "
                "in the mesh this is a ratio of ratios: the plane ratio above "
                "divided by the same plane ratio from an identical run with "
                "no load, and the line's own delay and impedance -- its beta "
                "and its zc -- are taken from that load-free twin, because "
                "this record's own fit spans the cut.  The line divides "
                "itself out either way (on a record that never carried a load "
                "the twin is the record itself), and what survives the "
                "division is the wave's own fate over this span, decay and "
                "all")
            s21_unity_row = (
                f"{100.0 * departure:+.3f} % from unity, "
                + ("inside" if abs(departure) < s21_tolerance else "outside")
                + f" the {100.0 * s21_tolerance:.0f} per cent a transmitting "
                "length is asked for.  The "
                "difference is real and not noise: with no ohmic loss in the "
                "solver, a decay this size is power leaving the guided mode "
                "for the surrounding matched layers, and the row below that "
                "exponentiates the fitted alpha states the same decay from a "
                "different measurement")
    else:
        s21_row = "n/a: this record carried no stations to split"
        s21_unity_row = s21_row

    # The passivity bound, and it is a bound and nothing more.  A passive
    # network cannot return more power than it was handed, so
    # ``|S11|^2 + |S21|^2 <= 1``.  The plain sum of squares is legitimate here
    # because both magnitudes are read on one cross-section -- the two station
    # planes -- and the split gives both of them the same ``zc``, so the
    # per-plane power-wave weighting ``sqrt(Re zc)`` that the general form of
    # this test carries is the same factor on both terms and cancels.  Planes
    # on two different cross-sections would need that factor written out, which
    # is why the same sum is not a valid test in that geometry.  What the row
    # catches is a sign or a normalisation error in the wave split, which lifts
    # the sum above 1; the surrounding matched layers only ever remove power
    # the two planes never see again, so they push the sum down and a wide
    # margin is the expected reading rather than a defect.
    gamma_sq = float(abs(result.gamma)) ** 2
    s21_sq = float(abs(result.s21)) ** 2
    if np.isfinite(gamma_sq) and np.isfinite(s21_sq):
        bound_sum = gamma_sq + s21_sq
        assert bound_sum <= 1.0 + 1e-9, (
            "passivity bound violated between the station planes: "
            f"|S11|^2 + |S21|^2 = {gamma_sq:.6f} + {s21_sq:.6f} = "
            f"{bound_sum:.6f} is above 1, with |S11| = "
            f"{abs(result.gamma):.6f} and |S21| = {abs(result.s21):.6f}; a "
            "passive network cannot return more power than it was handed, so "
            "a sum above 1 is a sign or a normalisation error in the wave "
            "split and not a measured excess")
        passivity_row = (
            f"{bound_sum:.6f} from |S11|^2 = {gamma_sq:.6f} plus |S21|^2 = "
            f"{s21_sq:.6f}: a passive network must satisfy "
            "|S11|^2 + |S21|^2 <= 1, and the two sides of that bound are two "
            "different claims.  Above 1 is a bug.  Near 1 is what a model "
            "with no material loss should return, because the sum is the "
            "power budget of the two station planes and with nothing in the "
            "model to absorb energy there is nothing for it to be short of.  "
            "Well below 1 is power that left through something the two planes "
            "do not see -- an absorbing boundary close enough to the line, a "
            "source that radiates -- and that sink has to be found before any "
            "number from this run is quoted.  The plain sum is legitimate "
            "here because both magnitudes are read on the same cross-section, "
            "the two station planes, and the split hands both of them the one "
            "zc chosen for this record: the per-plane sqrt(Re zc) weighting "
            "is then the same factor on both terms and cancels, where two "
            "planes on different cross-sections would need it written out.")
    else:
        passivity_row = (
            "n/a: this record has no finite |S11| or |S21| to add, so there "
            "is no passivity bound to quote; the bound itself is "
            "|S11|^2 + |S21|^2 <= 1 between the station planes")

    # --- loss: the joint fit's alpha, and what it predicts for |S21| -------
    # The unit the attenuation sweep is quoted in, and the only conversion in
    # the file: nepers per metre to decibels per millimetre.
    def db_per_mm(alpha_np_per_m):
        return 20.0 * np.log10(np.e) * float(alpha_np_per_m) / 1e3

    lf = result.loss_fit
    lf2 = result.loss_fit_two
    lfl = result.station_fit_lossy

    # --- is the record settled? -------------------------------------------
    # Every alpha below is read off an averaging window, and a window can only
    # be believed if it agrees with itself: the phase constant refitted on the
    # two halves of the same record is that self-check, and it is stated before
    # the number it protects.  Nothing else in the report can see this -- a
    # record still filling fits perfectly well, it just fits a different line
    # depending on where the window was opened.
    drift = (abs(result.beta_first_half - result.beta_second_half)
             / abs(result.beta)
             if np.isfinite(result.beta_first_half)
             and np.isfinite(result.beta_second_half) and result.beta
             else float("nan"))
    settled = bool(np.isfinite(drift) and drift <= MS_SETTLE_TOL)

    def alpha_row(fit, label):
        """One attenuation row out of one joint fit."""
        if fit is None:
            return "n/a: this record carried no stations to fit"
        if fit.alpha is None:
            return ("n/a: the joint fit refused an alpha -- its standard error "
                    "reaches across the whole span, so a decay that small "
                    "cannot be told from a straight line")
        alpha_db = db_per_mm(fit.alpha)
        sigma = (db_per_mm(fit.alpha_sigma)
                 if fit.alpha_sigma is not None else None)
        plus = num(sigma, "", ".5f") if sigma is not None else "n/a"
        used = ("one travelling wave" if label == "one-wave"
                else "a backward wave allowed")
        return (f"{alpha_db:.5f} +- {plus} dB/mm ({fit.alpha:.4f} Np/m, "
                f"beta = {fit.beta:.3f} +- "
                f"{num(fit.beta_sigma, '', '.3f')} rad/m, same fit): "
                f"{label} model, {used}, over "
                f"{fit.span * 1e3:.2f} mm of line.  In a solver with no loss "
                "model this is not copper: it is power the guided mode gives "
                "up to the surrounding matched layers plus the grid's own "
                "numeric dispersion"
                + ("" if settled else ".  UNSETTLED: the two halves of this "
                   "record disagreed on beta (see the row above), so this "
                   "alpha is an upper bound on any decay, not a measurement "
                   "of it"))

    if not np.isfinite(drift):
        settledness_row = ("n/a: this record was too short to split into two "
                           "halves worth fitting")
    else:
        settledness_row = (
            f"beta = {result.beta_first_half:.3f} rad/m over the first half of "
            f"the transformed record and {result.beta_second_half:.3f} rad/m "
            f"over the second, {100.0 * drift:.3f} % apart against the "
            f"{100.0 * MS_SETTLE_TOL:.1f} % this study allows: "
            + ("settled, so a window is a fair sample of the steady state"
               if settled else
               "NOT settled -- the waveform was still changing across the "
               "window, so the alpha rows below bound whatever decay is "
               "there and do not measure it"))

    alpha_one_row = alpha_row(lf, "one-wave")
    alpha_two_row = alpha_row(lf2, "two-wave")
    if lf is None or lf.alpha is None or lf.beta_sigma is None:
        alpha_cov_row = "n/a: no joint covariance to report"
    elif lf.rho is None:
        alpha_cov_row = (f"sigma_beta = {lf.beta_sigma:.4f} rad/m on its own; "
                         "the joint fit returned no correlation")
    else:
        alpha_cov_row = (
            f"rho(alpha, beta) = {lf.rho:+.4f}, from the 2 x 2 block of "
            f"s^2 (D^T D)^-1 on those two parameters alone with "
            f"{2 * lf.n_stations} measurements in it. "
            + ("The two are nearly orthogonal, so the decay costs the phase "
               "constant almost nothing to measure"
               if abs(lf.rho) < 0.5 else
               "They are not orthogonal: on this span a decay and a phase "
               "slope trade against each other, and each quoted error is "
               "larger than it would be with the other fixed"))

    # The same attenuation, stated as the transmission it implies across the
    # station span -- the number G1 asks about, from a different measurement
    # than the station-plane ratio, which is the point of putting the two rows
    # side by side.
    if lf is None or lf.alpha is None:
        s21_loss_row = "n/a: no fitted decay to exponentiate"
    else:
        span_length = float(lf.span)
        s21_loss = float(np.exp(-lf.alpha * span_length))
        loss_db = decibel(s21_loss)
        sigma_s21 = (s21_loss * lf.alpha_sigma * span_length
                     if lf.alpha_sigma is not None else None)
        sig_str = (f"{sigma_s21:.6f}" if sigma_s21 is not None else "n/a")
        departure = s21_loss - 1.0
        within = abs(departure) < s21_tolerance
        s21_loss_row = (
            f"{s21_loss:.6f} = {num(loss_db, 'dB', '.3f')} "
            f"(+- {sig_str}) over the {span_length * 1e3:.2f} mm between the "
            f"first and last station, from exp(-alpha L) with "
            f"alpha = {db_per_mm(lf.alpha):.5f} dB/mm: "
            f"{100.0 * departure:+.3f} % from unity, "
            + ("inside" if within else "outside")
            + f" the {100.0 * s21_tolerance:.0f} per cent G1 asks for. "
            + ("It agrees with the |S21| between station planes quoted "
               "above, which is the check worth making: one number fitted to "
               "the field at every station and one a ratio of two planes, two "
               "measurements of one decay"
               if abs(departure - (abs(result.s21) - 1.0)) < 0.01 else
               "It does not agree with the |S21| between station planes quoted "
               "above, so one of the two is reading something that is not "
               "attenuation; the |S21| implied by the absorbed work, below, "
               "is the third measurement and says which"))

    # The same transmission from the other side: not a fit to the field at all,
    # but a bookkeeping of the energy the matched layers removed.  The box has
    # no other exit -- every face that is not an absorber is PEC -- so the work
    # the layer did is a closed account of where the injected power went, split
    # by which family of walls took it.  Whatever the lateral walls took is
    # power the guided mode lost sideways, and two different numbers can be
    # made of that, so both are stated:
    #
    #  * charged to the station span -- all of the lateral work, as if those
    #    walls ran only between the two transmission planes.  They do not: they
    #    run the whole box, ``length / span`` times as far, so this charges too
    #    much work to the span and is an upper bound on the loss over it;
    #  * per unit length of line -- the lateral work *rate* per metre of wall,
    #    divided by ``2 P``, which is the definition of an attenuation
    #    constant.  That is the one an alpha can be compared against, and it is
    #    the one this row believes.
    pb = result.power_balance
    if pb is None:
        s21_audit_row = ("n/a: this run did not ask for the absorbed-work "
                         "audit (``audit=True``)")
    else:
        audit_length = float(pb["length"])
        implied = float(pb["implied_s21"])
        lateral_fraction = float(pb["lateral_fraction"])
        lateral_pct = 100.0 * lateral_fraction
        end_pct = 100.0 * float(pb["end_fraction"])
        implied_loss = 100.0 * (1.0 - implied)
        tops = " plus the top" if g["n_top"] else ""
        # The accounting's own resolution, in units of the lateral fraction:
        # ``implied = sqrt(1 - f)`` is ``1 - f/2`` near unity and is printed to
        # six decimals, so a fraction below this cannot move a digit of it.
        audit_resolution = 2e-6
        basis = (
            f"Charged to the station span (an upper bound): "
            f"{implied:.6f} = {num(decibel(implied), 'dB', '.3f')}, "
            f"{implied_loss:.3f} % below unity over the "
            f"{audit_length * 1e3:.2f} mm between the first and last station "
            f"plane. Basis: the work the matched layers removed during the "
            f"{pb['steps']} settled (post-warm-up) steps, split by wall "
            f"family -- {lateral_pct:.3f} % of it at the lateral walls "
            f"(ymin, ymax{tops}) and {end_pct:.3f} % at the end walls (xmin, "
            f"xmax), the box having no other exit because every remaining "
            f"face is PEC. Normalisation: every joule is measured against "
            f"the total removed work in that window, and in the steady state "
            f"every joule injected is absorbed, so that total is the injected "
            f"power and the lateral share is the share of the injected power "
            f"lost sideways -- a statement about steady state only, which is "
            f"why the warm-up steps are excluded from it. This is an "
            f"accounting bound over the travelled length "
            f"{audit_length * 1e3:.2f} mm, not a fitted exponential: the "
            f"lateral walls run the whole box length and all their work is "
            f"charged to this shorter span, so the loss it implies is if "
            f"anything an over-estimate. ")
        # The attenuation constant itself.  ``alpha = (power lost per unit
        # length) / (2 P)``: the lateral walls are the only leak along the
        # line, they run the whole box, and both work totals cover the same
        # steps, so the window length cancels out of the ratio.
        wall_length = float(g["length"])
        lateral_work = float(pb["work"].get("lateral", 0.0))
        total_work = float(sum(pb["work"].values()))
        alpha_leak = (lateral_work / (2.0 * total_work * wall_length)
                      if total_work > 0.0 else float("nan"))
        leak_loss = 1.0 - float(np.exp(-alpha_leak * audit_length))
        per_length = (
            f"Per unit length of line it is {alpha_leak:.4f} Np/m = "
            f"{db_per_mm(alpha_leak):.5f} dB/mm: the lateral walls removed "
            f"{lateral_work:.6e} J in the same {pb['steps']} steps in which "
            f"the run put {total_work:.6e} J into the box, and they run "
            f"{wall_length * 1e3:.2f} mm of line, so the work per metre is "
            f"2 * alpha * P. Over the {audit_length * 1e3:.2f} mm of the "
            f"station span that rate is exp(-alpha L) = "
            f"{float(np.exp(-alpha_leak * audit_length)):.6f}, "
            f"{100.0 * leak_loss:.3f} % below unity. That is the number to "
            f"set a fitted alpha against; the {implied_loss:.3f} % above "
            f"charges every metre of wall to a span "
            f"{wall_length / audit_length:.2f} times shorter and so reads "
            f"{implied_loss / (100.0 * leak_loss):.2f} times too large. ")
        if lateral_fraction < audit_resolution:
            comparison = (
                f"The lateral share is below the resolution of the "
                f"accounting ({audit_resolution:.0e} of the removed work), so "
                f"this row says the line does not measurably attenuate over "
                f"that span and there is no loss here to set against the "
                f"exp(-alpha L) row above; a fitted alpha that disagrees is "
                f"reading something other than attenuation")
        elif lf is not None and lf.alpha is not None:
            # Compare losses, not magnitudes: near unity a ratio of |S21| is
            # 1.0 to every digit the fit can resolve, while the losses behind
            # it differ by tens of per cent.
            fitted_loss = 1.0 - float(np.exp(-lf.alpha * float(lf.span)))
            two_alpha = (lf2.alpha if lf2 is not None and lf2.alpha is not None
                         else None)
            two_bit = (
                "" if two_alpha is None else
                f" (the two-wave alpha, {db_per_mm(two_alpha):.5f} dB/mm, "
                f"{100.0 * (1.0 - float(np.exp(-two_alpha * float(lf2.span)))):.3f} "
                f"% over the same span, "
                f"{(1.0 - float(np.exp(-two_alpha * float(lf2.span)))) / leak_loss:.2f} "
                "times the leaked rate)")
            comparison = (
                f"In loss, not magnitude: the per-unit-length rate above puts "
                f"{100.0 * leak_loss:.3f} % below unity over the "
                f"{audit_length * 1e3:.2f} mm, against "
                f"{100.0 * fitted_loss:.3f} % from exp(-alpha L) above, so "
                f"the fitted decay reads {fitted_loss / leak_loss:.2f} times "
                f"the rate the lateral walls actually removed{two_bit}. ")
            measured = (float(abs(result.s21))
                        if np.isfinite(result.s21) else None)
            if measured is not None and 0.0 < measured < 1.0:
                measured_loss = 1.0 - measured
                alpha_measured = -float(np.log(measured)) / audit_length
                comparison += (
                    f"The direct measurement sides with the accounting, not "
                    f"with the fit: the station-plane |S21| row is "
                    f"{100.0 * measured_loss:.3f} % below unity, an effective "
                    f"{alpha_measured:.4f} Np/m = "
                    f"{db_per_mm(alpha_measured):.5f} dB/mm, "
                    f"{abs(100.0 * (leak_loss / measured_loss - 1.0)):.1f} % "
                    f"from the leaked rate. This row therefore believes the "
                    f"per-unit-length rate: of the three it is the only one "
                    f"that both counts joules and agrees with the amplitude "
                    f"ratio, whereas a decay "
                    f"{fitted_loss / leak_loss:.2f} times faster would have "
                    f"to be paid for by lateral work this account does not "
                    f"see -- and it sees {lateral_pct:.3f} % of the injected "
                    f"power, with the end walls taking the rest. ")
            else:
                comparison += (
                    "This row believes the per-unit-length rate: it is the "
                    "only one here that turns work into an attenuation "
                    "constant rather than charging a whole wall to part of "
                    "the line. ")
        else:
            comparison = "No fitted alpha to compare it with"
        s21_audit_row = basis + per_length + comparison

    # The absorbed-work audit bins only the matched layer's damping (pml.py);
    # a lumped load removes work in the stepper (evolve.py), so on a loaded
    # run the audit's total is injected-minus-load and its normalisation would
    # charge the load to the absorber. Say so instead of quoting the number.
    if g.get("loads"):
        s21_audit_row = (
            "not reported: the absorbed-work audit assumes every joule the "
            "drive injects leaves through the matched layers, which is what "
            "makes its total equal to the injected power. This run also "
            "places a lumped load on the strip, and the load removes work "
            "itself (in the stepper, not in the layer), so the audit total is "
            "injected minus dissipated and this row would charge the load to "
            "the absorber. Read |S21| between the planes directly, or remove "
            "the load to restore this row.")

    # The station impedance the loss affects: with alpha in the propagation
    # constant the voltage and current waves no longer keep their relative
    # phase along the span, and the lossless fit has to absorb that somewhere.
    # A load present means the station fit spans the cut, so its beta and Z0 are
    # not the line's whether or not a reference was supplied: the reference
    # contributes ``zc`` and the load-free ratio and nothing else.  Every row
    # that reads that fit is gated on the load, not on how the split was made.
    if bool(g.get("loads")):
        lossy_z0_row = NO_LOADED_IMPEDANCE
    elif lfl is not None and np.isfinite(lfl.z0.real) and np.isfinite(sf.z0.real):
        lossy_z0_row = (
            f"{lfl.z0.real:.4f} ohm +- {num(lfl.z0_sigma_total, 'ohm', '.4f')}"
            f" against {sf.z0.real:.4f} ohm with the decay held fixed "
            f"({lfl.z0.real - sf.z0.real:+.4f} ohm), "
            f"{100.0 * (lfl.z0.real / result.z0_model - 1.0):+.3f} % from the "
            f"{result.z0_model:.3f} ohm closed form.  The two fits differ only "
            "in whether alpha is free, so the difference is what the lossless "
            "model was hiding; the error is that fit's budget with the alpha "
            "term squared in")
    elif not result.station_fit_ok and np.isfinite(sf.z0.real):
        lossy_z0_row = (
            "n/a: the loss-aware fit was refused on this record -- its "
            "warning says why -- so the only station impedance quoted is the "
            f"{sf.z0.real:.4f} ohm above, with the decay held fixed")
    elif not result.station_fit_ok:
        lossy_z0_row = (
            "n/a: both station-impedance fits were refused on this record -- "
            "its warning says why -- so there is no station impedance to "
            "quote here at all")
    else:
        lossy_z0_row = "n/a: this record fitted no station impedance"

    # The seven rows that read an impedance off ``sf`` are gated the same way:
    # a refusal in the |S21| row contradicted two rows later by a number in ohm
    # is not a refusal, and the fit behind those rows is the one that row names.
    if bool(g.get("loads")):
        stations_z0_modulus = NO_LOADED_IMPEDANCE
        stations_z0_phase = NO_LOADED_IMPEDANCE
        stations_z0_real = NO_LOADED_IMPEDANCE
        stations_z0_sigma_stat = NO_LOADED_IMPEDANCE
        stations_z0_sigma_beta = NO_LOADED_IMPEDANCE
        stations_z0_sigma_total = NO_LOADED_IMPEDANCE
    else:
        stations_z0_modulus = num(abs(sf.z0), "ohm")
        stations_z0_phase = (num(sf.phase_deg, "deg")
                             + " (two-wave fit, forward current)")
        stations_z0_real = num(sf.z0.real, "ohm")
        stations_z0_sigma_stat = num(sf.z0_sigma_stat, "ohm")
        stations_z0_sigma_beta = num(sf.z0_sigma_beta, "ohm")
        stations_z0_sigma_total = num(sf.z0_sigma_total, "ohm")

    # The port impedance and the power-current rows are gated for the same
    # reason, on their own physics: ``2P/|I|**2`` equals ``Re(V I*) / |I|**2``,
    # which is the characteristic impedance only for a single travelling wave.
    # On a loaded line P is the net power and |I| a superposition amplitude, so
    # the ratio is a standing-wave-contaminated estimate that resembles a line
    # property without being one -- and the port-plane version divides by
    # ``z0 = -v_port / i_trunc`` inside the port's own near field, so it is
    # weaker still.  The two ratios under ``port Z`` are that same refused
    # number divided by the closed form, so they go with it.
    if bool(g.get("loads")):
        port_z_modulus = port_z_phase = port_z_real = NO_LOADED_IMPEDANCE
        port_z_modulus_ratio = port_z_real_ratio = NO_LOADED_IMPEDANCE
        power_z0_stations = power_ratio_stations = NO_LOADED_IMPEDANCE
        power_z0_port = power_ratio_port = NO_LOADED_IMPEDANCE
    else:
        port_z_modulus = f"{abs(result.z0):.3f} ohm"
        port_z_phase = (f"{np.degrees(np.angle(result.z0)):.3f} deg "
                        "(excess phase, trace-current reference)")
        port_z_real = f"{result.z0.real:.3f} ohm"
        port_z_modulus_ratio = f"{abs(result.z0) / result.z0_model:.4f}"
        port_z_real_ratio = f"{result.z0.real / result.z0_model:.4f}"
        power_z0_stations = power_z0_row
        power_ratio_stations = power_ratio_row
        power_z0_port = num(result.power_z0_port, "ohm")
        power_ratio_port = (
            num(result.power_ratio_port, "", ".6f")
            + " -- 1 by construction: z0 at that plane *is* V/I on it, so "
            "the two phasors are one number and this row can only disagree "
            "with 1 through round-off.  The stations row above is the "
            "measurement; this one is an identity check")

    # The load this run placed, named in the unit it was asked for: a row only
    # when there is one, so the default report is unchanged.
    load_row = ""
    if loads:
        series = loads[0].kind == "series_r"
        load_row = (f"{'series R' if series else 'shunt C'} = "
                    f"{float(values['load_value']):.2f} "
                    f"{'ohm' if series else 'pF'} at "
                    f"{loads[0].position * 1e3:.2f} mm; |S21| between the "
                    "planes is measured through this element")

    # The board this run meshed, named in the units the knobs are given in: a row
    # only when a knob moved off its default, so the default report is unchanged.
    board_row = ""
    if board_changed:
        board_row = (f"h = {board_h * 1e3:.2f} mm, eps_r = {board_eps:.2f}, "
                     f"strip = {strip_cells} cells = {board_w * 1e3:.4f} mm wide "
                     f"at cell = {board_cell * 1e3:.4f} mm; the closed-form "
                     "curves are drawn for this same width")

    # The broadband report, when a pulse was run: one row per frequency, the
    # summaries, and the passivity figure.  It is built here, before
    # ``dump_figures``, because that figure is part of this run's output and a
    # figure added after the dump would never reach the disk; the rows are
    # merged into the report below.  A tone run carries no bins, so this is
    # empty and the report is byte for byte the one it always was.
    bin_rows = (_broadband_rows(result.bins, sink,
                                span=float(g["n_acc"]) * float(g["dt"]),
                                nsteps=int(g["nsteps"]))
                if result.bins else {})

    # Leave the pictures on disk: a benchmark's figures are part of its output.
    dump_figures(sink)

    metrics = {
        "drive frequency": _drive_frequency_text(g),
        "mesh": f"{g['nx']} x {g['ny']} x {g['nz']} cells at {g['cell'] * 1e3:.4f} mm",
        "box": (f"{g['length'] * 1e3:.2f} x {g['width'] * 1e3:.2f} x "
                f"{g['height'] * 1e3:.2f} mm, {g['nsteps']} steps "
                f"({g['n_acc']} transformed)"),
        "stations": (f"{len(result.station_x)} from "
                     f"{result.station_x[0] * 1e3:.2f} to "
                     f"{result.station_x[-1] * 1e3:.2f} mm"),
        "beta (one-wave fit)": f"{result.beta:.3f} rad/m",
        "beta (two-wave fit)": f"{result.beta_two_wave:.3f} rad/m",
        "beta (two stations)": f"{result.beta_two_station:.3f} rad/m",
        "|gamma|": f"{abs(result.gamma):.5f}",
        "fit residual": f"{result.fit_residual:.5f}",
        "beta drift (two averaging windows)": settledness_row,
        "alpha (joint fit, one wave)": alpha_one_row,
        "alpha (joint fit, two waves)": alpha_two_row,
        "alpha and beta together": alpha_cov_row,
        "beta (Hammerstad-Jensen)": f"{result.beta_model:.3f} rad/m",
        "beta, fit vs model": (f"{100.0 * (result.beta / result.beta_model - 1.0):.2f} %"
                               " (diagnostic: the model is quasi-static, so "
                               "this compares two different problems)"
                               if result.beta_model else "n/a"),
        "eps_eff": (NO_LOADED_BETA if bool(g.get("loads")) else (
            f"{result.eps_eff:.5f} (from this run's beta; the closed form it "
            f"is compared with is evaluated at w/h = {g['w'] * 1e3:.2f}/"
            f"{g['h'] * 1e3:.2f} mm = {g['w'] / g['h']:.3f} and eps_r = "
            f"{g['eps_r']:g}, and eps_eff falls as w/h rises at fixed h, so a "
            "thinner substrate at fixed w raises it and lowers Z0)")),
        "eps_eff (Hammerstad-Jensen)": (
            f"{result.eps_eff_model:.5f} (closed form at w/h = "
            f"{g['w'] * 1e3:.2f}/{g['h'] * 1e3:.2f} mm = {g['w'] / g['h']:.3f} "
            f"and eps_r = {g['eps_r']:g})"),
        "port Z, modulus": port_z_modulus,
        "port Z, phase": port_z_phase,
        "port Z, real part": port_z_real,
        "line Z0 (Hammerstad-Jensen)": f"{result.z0_model:.3f} ohm",
        "port modulus / model": port_z_modulus_ratio,
        "port real part / model": port_z_real_ratio,
        "line Z0 from stations, modulus": stations_z0_modulus,
        "line Z0 from stations, phase": stations_z0_phase,
        "line Z0 from stations, real part": stations_z0_real,
        "line Z0, sigma (statistical)": stations_z0_sigma_stat,
        "line Z0, sigma (beta)": stations_z0_sigma_beta,
        "line Z0, sigma total": stations_z0_sigma_total,
        "line mode purity": (num(sf.mode_purity, "", ".3e")
                             + " as |gamma_I + gamma_V|; 0 is a pure mode"),
        "line Z0, reference plane": num(sf.reference_plane * 1e3, "mm"),
        "beta sigma (curvature)": (num(sf.sigma_beta, "rad/m", ".4g")
                                   + (" (relative "
                                      + num(sf.sigma_beta / abs(sf.beta), "", ".2e")
                                      + ")")
                                   if sf.sigma_beta is not None and sf.beta
                                   else ""),
        "power-current Z0 at stations": power_z0_stations,
        "power-current ratio at stations": power_ratio_stations,
        "power-current Z0 at the port plane": power_z0_port,
        "power-current ratio at the port plane": power_ratio_port,
        "|S11| at the measured plane": (
            f"{gamma_abs:.5f} = {num(s11_measured_db, 'dB', '.2f')} at x = "
            f"{sf.reference_plane * 1e3:.2f} mm, the first station, because "
            "that is the plane the fit refers it to: a station is a "
            "measurement, and a lumped source's own plane is only defined by "
            "the gap it drives.  What reflects is the port lump plus the "
            f"{g['n_pml']}-cell absorber that terminates the far end, and at "
            "this level the absorber's residual is the larger of the two"),
        "|S11| at the port plane": (
            f"{abs(result.gamma_port):.5f} = {num(s11_port_db, 'dB', '.2f')} "
            f"after exp(-2j beta d) with d = {result.deembed_distance * 1e3:.2f} "
            "mm: the same reflection, port lump plus absorber termination, "
            "quoted on the plane a user's S-parameters are wanted on.  beta is "
            "real, so the move changes phase and nothing else"),
        "|S11| as VSWR": (
            f"{vswr:.4f} : 1 at the same plane, from (1 + |gamma|) / "
            f"(1 - |gamma|) with |gamma| = {gamma_abs:.5f}: quoted because a "
            "reflection at this level is easier to read as a mismatch than as "
            "a decibel"),
        "power ratio, bound from |S11|": bound_row,
        "G1 (|S11| < -20 dB)": g1_row,
        "|S21| between station planes": s21_row,
        "G1 (|S21| within 1 % of unity)": s21_unity_row,
        "passivity bound: |S11|^2 + |S21|^2 between the station planes": (
            passivity_row),
        "|S21| from the fitted alpha": s21_loss_row,
        "|S21| implied by the absorbed work": s21_audit_row,
        "line Z0 with loss, real part": lossy_z0_row,
        "ground current, full domain": f"{abs(result.i_ground_full):.6e} A",
        "ground current, strip extent": f"{abs(result.i_ground_truncated):.6e} A",
        "full / strip current": f"{gain:.3f}",
        "beta ambiguity": ("total span phase > pi: the two-station difference "
                           "has wrapped, read the fit"
                           if g["beta_ambiguous"] else "phase step below pi"),
    }
    if loads:
        metrics["load"] = load_row
        metrics["reference"] = (
            "|S21| is a ratio against an identical run with no load: a record "
            "with an element across the strip cannot measure its own "
            "propagation constant or impedance, because the cut breaks the fit "
            "those come from. The beta, eps_eff and station-impedance rows "
            "above therefore still refuse; only the ratio and the reference "
            "impedance are used.")
    if board_changed:
        metrics["board"] = board_row
    if result.bins:
        metrics.update(bin_rows)
    return metrics


def _run_microstrip_board(values: Mapping[str, Any], sink: FigureSink) -> dict:
    """Study wrapper: one coupon read out of a board file, as formatted strings."""
    path = str(values.get("board", "")).strip()
    if not path:
        raise ValueError(
            "board: no board file given; name the file to read with "
            "--set board=<path>.kicad_pcb.  A board study has no default "
            "geometry: the file is the input, and every number below is read "
            "out of it")
    net = str(values.get("net", "")).strip()
    if not net:
        raise ValueError(
            "net: no net named; give the copper net that carries the strip "
            "with --set net=<name>.  A board file usually carries several "
            "nets and nothing here picks one for you")
    port_pad = None
    pad_text = str(values.get("port_pad", "")).strip()
    if pad_text:
        reference, dot, number = pad_text.rpartition(".")
        if not dot or not reference or not number:
            raise ValueError(
                f"port_pad: {pad_text!r} is not in REF.NUM form: give the "
                "footprint reference and the pad number separated by a dot, "
                "e.g. port_pad=J1.1 (pad 1 of footprint J1)")
        port_pad = (reference, number)

    n_sub = int(values.get("n_sub", MS_N_SUB))
    n_air = int(values.get("n_air", MS_N_AIR))
    n_top = int(values.get("n_top", MS_N_TOP))
    npml = int(values.get("npml", MS_N_PML))
    n_stations = int(values.get("n_stations", MS_N_STATIONS))
    eps_r = float(values.get("eps_r", 0.0))
    # The excitation, in the units the knobs are given in: the three frequencies
    # arrive in GHz and are hertz from here on, which is what the solver reads.
    # ``cw`` is the single tone, and the default, so this path reports exactly
    # what it always did unless the pulse was asked for by name.
    excite = str(values.get("excite", MS_EXCITE))
    band_lo = float(values.get("band_lo", MS_BAND_LO_GHZ)) * 1e9
    band_hi = float(values.get("band_hi", MS_BAND_HI_GHZ)) * 1e9
    n_bins = int(values.get("n_bins", MS_N_BINS))
    f_pulse = float(values.get("f_pulse", MS_F_PULSE_GHZ)) * 1e9

    # The file is read here and not in the CLI: this study owns every number it
    # reports, and ``MicrostripBoard.from_kicad`` is the one bridge from a
    # parsed board to a mesh.  ``taper='dominant'`` is asked for deliberately
    # -- a tapering line would otherwise be refused and the commonest coupon
    # there is would show nothing -- and a named pad takes the choice of port
    # plane away from that rule.
    board = load_board(path)
    try:
        spec = MicrostripBoard.from_kicad(
            board, net=net, eps_r=(eps_r if eps_r > 0.0 else None),
            taper="dominant", port_pad=port_pad)
    except ValueError as exc:            # no such net, no run along x, no stackup
        raise ValueError(f"board {path}: {exc}") from None
    if bool(values.get("crop", True)):
        # The box ends where the strip does: the outline supplied the lateral
        # clearance and the far wall, and it is the strip's propagation
        # constant the record reports.  ``n_sub`` is handed in so that cropping
        # also lands the two ``x`` planes on cell boundaries, which is what
        # ``to_cell_counts`` is going to ask of them anyway.
        spec = spec.cropped_to_strip(n_sub=n_sub)

    # The stations are placed on the strip this file draws, not at the fixed
    # 10.4/20.0 mm of the typed-in default line: on a coupon those two numbers
    # are wherever the board happens to put the copper.
    span = spec.x_far - spec.x_port
    result = microstrip_wave_board(
        spec,
        n_sub=n_sub,
        n_air=n_air,
        n_top=n_top,
        n_pml=npml,
        x_first=spec.x_port + 0.2 * span,
        x_last=spec.x_port + 0.8 * span,
        n_stations=n_stations,
        f_target=float(values["f0"]) * 1e9,
        nsteps=int(values["nsteps"]),
        excite=excite, band_lo=band_lo, band_hi=band_hi,
        n_bins=n_bins, f_pulse=f_pulse,
        keep_slice=True,
        sink=sink)
    g = result.geometry
    # A record whose station fit was refused still has a report to write, and
    # every row below reads its numbers off ``sf``: a blank fit says ``n/a`` on
    # all of them through ``num()`` instead of raising nine-tenths of the way
    # through a table.
    sf = (result.station_fit if result.station_fit is not None
          else _blank_station_fit(result.station_x[0], result.beta, None,
                                  len(result.station_x)))

    def num(value, unit, fmt=".4f"):
        """Format an optional number, or ``n/a`` when the fit could not give it."""
        if value is None or not np.isfinite(value):
            return "n/a"
        return f"{value:{fmt}} {unit}".strip()

    def decibel(magnitude):
        """``20 log10`` of a magnitude, or ``None`` when no magnitude exists."""
        if magnitude is None or not np.isfinite(magnitude) or magnitude <= 0.0:
            return None
        return 20.0 * np.log10(magnitude)

    # Which plane the wave was launched from, said as the fact it is: a pad the
    # file declares, or a rule applied to the track the file draws.
    if spec.port is None:
        launch = (
            f"taper='dominant' at the run extremes: no pad was named, so the "
            f"port plane is the end of the {spec.w * 1e3:.3f} mm run of net "
            f"{spec.name!r} that the model drives from (x = "
            f"{spec.x_port * 1e3:.3f} mm), with the far plane at the other "
            f"end (x = {spec.x_far * 1e3:.3f} mm).  The width is the one that "
            "covers the most of the net, which is the strip and not the taper "
            "either side of it; name a pad with port_pad=REF.NUM to launch "
            "from it instead")
    else:
        port = spec.port
        launch = (
            f"pad {port.reference}.{port.number} on net {port.net!r}, at x = "
            f"{port.position * 1e3:.3f} mm, y = {port.y * 1e3:.3f} mm on the "
            f"{port.side} copper: the pad decides which end of the run is the "
            "port plane -- the end it sits nearest to -- and not how wide the "
            f"strip is, so the line is still the {spec.w * 1e3:.3f} mm run "
            "that covers the most of the net")

    gamma_abs = abs(sf.gamma_v)
    s11_measured_db = decibel(gamma_abs)
    s11_port_db = decibel(abs(result.gamma_port))
    # ``1.0 - 1e-9``, not ``1.0``: a numerically total reflection otherwise
    # comes out as a finite VSWR of 9.0e15, which is a float artefact printed
    # as though it had been measured.
    vswr = ((1.0 + gamma_abs) / (1.0 - gamma_abs)
            if gamma_abs < 1.0 - 1e-9 else float("inf"))
    vswr_text = f"{vswr:.4f}" if np.isfinite(vswr) else "unbounded"
    s21_db = decibel(abs(result.s21))
    x1, x2 = result.s21_planes

    # The passivity bound.  It is a bound and nothing more: a passive network
    # cannot return more power than it was handed, so |S11|^2 + |S21|^2 <= 1
    # between the two station planes.  The plain sum is legitimate because both
    # magnitudes are read on one cross-section, so the per-plane power-wave
    # weighting sqrt(Re zc) is the same factor on both terms and cancels.
    gamma_sq = float(abs(result.gamma)) ** 2
    s21_sq = float(abs(result.s21)) ** 2
    if np.isfinite(gamma_sq) and np.isfinite(s21_sq):
        passivity_row = (
            f"{gamma_sq + s21_sq:.6f} from |S11|^2 = {gamma_sq:.6f} plus "
            f"|S21|^2 = {s21_sq:.6f}: a passive network must satisfy "
            "|S11|^2 + |S21|^2 <= 1, and the two sides of that bound are two "
            "different claims.  Above 1 is a bug.  Near 1 is what a model "
            "with no material loss should return, because the sum is the "
            "power budget of the two station planes and with nothing in the "
            "model to absorb energy there is nothing for it to be short of.  "
            "Well below 1 is power that left through something the two planes "
            "do not see -- an absorbing boundary close enough to the line, a "
            "source that radiates -- and that sink has to be found before any "
            "number from this run is quoted.  The plain sum is legitimate "
            "here because both magnitudes are read on the same cross-section, "
            "the two station planes, and the split hands both of them the one "
            "zc chosen for this record: the per-plane sqrt(Re zc) weighting "
            "is then the same factor on both terms and cancels, where two "
            "planes on different cross-sections would need it written out.")
    else:
        passivity_row = (
            "n/a: this record has no finite |S11| or |S21| to add, so there is "
            "no passivity bound to quote; the bound itself is "
            "|S11|^2 + |S21|^2 <= 1 between the station planes")

    gain = abs(result.i_ground_full) / max(abs(result.i_ground_truncated), 1e-300)

    metrics = {
        "board": f"{path} (net {spec.name!r})",
        "launch": launch,
        "line, from the board": (
            f"{spec.w * 1e3:.3f} mm strip on {spec.h * 1e3:.3f} mm of eps_r = "
            f"{spec.eps_r:g} (w/h = {spec.w / spec.h:.3f}); port plane at "
            f"{spec.x_port * 1e3:.3f} mm, far plane at "
            f"{spec.x_far * 1e3:.3f} mm, outline {spec.length * 1e3:.3f} x "
            f"{spec.width * 1e3:.3f} mm"),
        "supplied by the caller": (
            ", ".join(spec.supplied) if spec.supplied
            else "nothing: every number above came out of the file"),
        "drive frequency": _drive_frequency_text(g),
        "mesh": (f"{g['nx']} x {g['ny']} x {g['nz']} cells at "
                 f"{g['cell'] * 1e3:.4f} mm"),
        "counts, from the spec": (
            f"n_strip = {g['n_strip']}, n_clean = {g['n_clean']}, "
            f"n_ref = {g['n_ref']}, n_line = {g['n_line']}"),
        "box": (f"{g['length'] * 1e3:.2f} x {g['width'] * 1e3:.2f} x "
                f"{g['height'] * 1e3:.2f} mm, {g['nsteps']} steps "
                f"({g['n_acc']} transformed)"),
        "stations": (f"{len(result.station_x)} from "
                     f"{result.station_x[0] * 1e3:.2f} to "
                     f"{result.station_x[-1] * 1e3:.2f} mm"),
        "beta (one-wave fit)": f"{result.beta:.3f} rad/m",
        "beta (Hammerstad-Jensen)": f"{result.beta_model:.3f} rad/m",
        "|gamma|": f"{abs(result.gamma):.5f}",
        "fit residual": f"{result.fit_residual:.5f}",
        "eps_eff": f"{result.eps_eff:.5f} (from this run's beta)",
        "eps_eff (Hammerstad-Jensen)": f"{result.eps_eff_model:.5f}",
        "line Z0 (Hammerstad-Jensen)": f"{result.z0_model:.3f} ohm",
        "line Z0 from stations": num(abs(sf.z0), "ohm"),
        "|S11| at the measured plane": (
            f"{gamma_abs:.5f} = {num(s11_measured_db, 'dB', '.2f')} at x = "
            f"{sf.reference_plane * 1e3:.2f} mm, the first station: that is "
            "the plane the station fit refers its reflection to, because a "
            "lumped source's own plane is defined by the gap it drives and "
            "not by a coordinate"),
        "|S11| at the port plane": (
            f"{abs(result.gamma_port):.5f} = {num(s11_port_db, 'dB', '.2f')} "
            f"after exp(-2j beta d) with d = "
            f"{result.deembed_distance * 1e3:.2f} mm: the same reflection "
            "moved onto the plane an instrument at the pad would see, and beta "
            "is real here, so the move changes phase and nothing else"),
        "|S11| as VSWR": (
            f"{vswr_text} : 1 from (1 + |gamma|) / (1 - |gamma|) with "
            f"|gamma| = {gamma_abs:.5f}: a reflection at this level is easier "
            "to read as a mismatch than as a decibel"),
        "|S21| between station planes": (
            f"{abs(result.s21):.6f} = {num(s21_db, 'dB', '.3f')} between x = "
            f"{x1 * 1e3:.2f} mm and x = {x2 * 1e3:.2f} mm, "
            f"{(x2 - x1) * 1e3:.2f} mm apart: one plane at each end, each split "
            "into its forward wave and the two divided, so no fit stands "
            "between the planes"),
        "passivity bound: |S11|^2 + |S21|^2 between the station planes": (
            passivity_row),
        "ground current, full domain": f"{abs(result.i_ground_full):.6e} A",
        "ground current, strip extent": (
            f"{abs(result.i_ground_truncated):.6e} A"),
        "full / strip current": f"{gain:.3f}",
        "beta ambiguity": ("total span phase > pi: the two-station difference "
                           "has wrapped, read the fit"
                           if g["beta_ambiguous"] else "phase step below pi"),
    }
    # The broadband rows, when a pulse was asked for: one per frequency, plus
    # the summaries.  A tone run carries no bins, so the report of one is the
    # dict above and nothing else.
    if result.bins:
        metrics.update(_broadband_rows(
            result.bins, sink, span=float(g["n_acc"]) * float(g["dt"]),
            nsteps=int(g["nsteps"])))
    return metrics


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
    title="Absorbing duct termination: Mur vs PML vs PEC",
    blurb=("A pulse launched into a PEC waveguide, measured at a probe near the "
           "source. With the first-order Mur condition at the two ends of the "
           "duct the outgoing pulse is absorbed (-49 dB, matching the analytic "
           "reflection coefficient); with a matched lossy layer (PML) of 12 "
           "cells at each end the echo is weaker still; with a plain PEC wall it "
           "comes back almost undamped. Switch the termination to compare."),
    params=(
        Param("nx", "cells along the duct", "int", 320, lo=64, hi=400,
              help="Axial resolution; the duct is 2.4 m long."),
        Param("ny", "cells across the duct", "int", 16, lo=8, hi=32),
        Param("nsteps", "time steps", "int", 900, lo=200, hi=2000,
              help="Enough steps must be taken for the echo to reach the probe "
                   "(about 10 ns after the incident pulse)."),
        Param("termination", "far-end termination", "choice", "mur",
              choices=("mur", "pml", "pec"),
              help="'mur' and 'pml' absorb the outgoing pulse (a first-order "
                   "ABC and a matched lossy layer), 'pec' reflects it so the "
                   "reflection is visible."),
    ),
    run=_run_duct,
)

SCATTER = Study(
    name="scatter",
    title="PEC cylinder in a plane-wave-like beam",
    blurb=("A pulse launched from a uniform line source sweeps a PEC cylinder "
           "and the field with the body present is compared with the same run "
           "without it. The difference is the scattered field and nothing "
           "else, because the two runs share the mesh, the time step, the "
           "source, the layer and the walls -- so the whole artefact stack "
           "cancels exactly. Two figures: total against scattered field at the "
           "instant the peak is over the cylinder, and the scattered field "
           "running through the body. The incident front is plane-wave-like, "
           "not plane, as documented in emfit.scatter."),
    params=(
        Param("ka", "electrical size ka", "float", 3.0, lo=0.5, hi=6.0,
              help="Circumference in wavelengths, 2 pi a / lambda; the radius "
                   "follows as ka / (2 pi) wavelengths, so below ka = 1 the "
                   "staircase is only a few cells across."),
        Param("ppw", "cells per wavelength", "int", 20, lo=8, hi=32,
              help="The domain is six wavelengths square and the layer one "
                   "wavelength thick, so the cell count and the run time "
                   "follow directly from this."),
    ),
    run=_run_scatter,
)

RCS = Study(
    name="rcs",
    title="Bistatic RCS of a PEC cylinder against exact Mie",
    blurb=("A PEC cylinder in a pulse beam, measured at every angle: the far "
           "field on a contour around the body is integrated into a bistatic "
           "scattering width and compared with the Mie series for the same "
           "ka. Left panel of the figure is the polar pattern at a glance, "
           "the right one the same two curves with the difference drawn on its "
           "own axis; the second output is an animation of the scattered "
           "field sweeping past the cylinder. The error reported is the error "
           "of the whole pipeline, not of one step."),
    params=(
        Param("ka", "electrical size ka", "float", 3.0, lo=0.5, hi=6.0,
              help="Circumference in wavelengths, 2 pi a / lambda; the pattern "
                   "sharpens with it, and the staircase gets relatively "
                   "smaller."),
        Param("ppw", "cells per wavelength", "int", 20, lo=8, hi=32,
              help="The domain is six wavelengths square, so the cell count "
                   "and the run time follow from this; below about 12 the "
                   "pattern is visibly dispersion-limited."),
    ),
    run=_run_rcs,
)

MICROSTRIP = Study(
    name="microstrip",
    title="Microstrip wave: beta, Z0 and the return current the layer spoils",
    blurb=(
        "A microstrip line (h = 1.6 mm, w = 3.2 mm, eps_r = 4.4) driven by a "
        "lumped current port at one end, with the gap voltage sampled at nine "
        "stations between 10.4 mm and 20.0 mm and the ground return current "
        "taken twice: over the whole domain, and over the physical strip "
        "extent only, with the lateral matched-layer columns left out. "
        "Comparing those two currents is the point -- what a matched layer "
        "adds to a plate-current sum is not current any conductor carries. "
        "beta comes from a least-squares one-wave fit over all nine stations, "
        "with the two-station difference kept beside it as a cross-check and a "
        "two-wave fit reporting beta and |gamma|; Z0 from V/I at the port "
        "station, eps_eff from beta, and each is printed next to the "
        "Hammerstad-Jensen closed form. The strip ends in a six-cell absorber "
        "on the far wall, so what reflects is that termination and not a load: "
        "|gamma| = 0.0075 in the default case, and |S11| measures it. A record "
        "too short for the transient to reach the far end lies about beta: read "
        "the fit residual and |gamma| first."),
    params=(
        # 20000, not 4000: this ceiling is here to catch a mistyped digit, not
        # to forbid a cell size.  A 0.2 mm coupon cell needs 4800 steps and the
        # 9600 that a 0.1 mm cell needs is the run this study's own board path
        # exists for, so a cap of 4000 refused the geometry the package now
        # describes while ``microstrip_wave`` underneath was fine with both.
        Param("nsteps", "leapfrog steps", "int", MS_NSTEPS, lo=64, hi=20000,
              help="The first quarter is warm-up; the rest is Fourier "
                   "transformed, and the drive frequency is snapped to one of "
                   "its bins. The record also has to be long enough for the "
                   "launched transient to leave the line."),
        Param("f0", "drive frequency", "float", MS_F_TARGET / 1e9,
              lo=1.0, hi=20.0, unit="GHz",
              help="Wanted tone; the run uses the nearest DFT bin of the "
                   "record and reports both."),
        Param("npml", "matched-layer cells", "int", MS_N_PML, lo=2, hi=12,
              help="Layer thickness at each absorbing face (both x ends and "
                   "both lateral ends); thicker absorbs more and costs more "
                   "cells."),
        Param("load_kind", "Load", "choice", "none",
              choices=("none", "series_r", "shunt_c"),
              help="A lumped element placed across the strip at load_at_mm. "
                   "none reproduces the published default record. series_r "
                   "is a series resistance; shunt_c is a shunt "
                   "capacitance."),
        Param("load_at_mm", "Load position", "float", 15.2,
              lo=10.4, hi=20.0, unit="mm",
              help="Distance from the left edge of the line. Confined to "
                   "the span between the two measurement planes "
                   "(10.4-20.0 mm): a load outside them does not sit "
                   "between the planes and would drop out of |S21|."),
        Param("load_value", "Load value", "float", 100.0,
              lo=0.01, hi=1.0e5, unit="",
              help="In ohm for series_r, in picofarad for shunt_c "
                   "(converted to farad internally). Ignored when "
                   "load_kind is none."),
        Param("eps_r", "Substrate permittivity", "float", MS_EPS_R,
              lo=1.0, hi=16.0, unit="",
              help="Relative permittivity of the board. Used directly as "
                   "the substrate material; nothing is rounded."),
        Param("h_mm", "Substrate thickness", "float", MS_H * 1e3,
              lo=1.3, hi=3.2, unit="mm",
              help="Sets the cell size: cell = h / n_sub, so every "
                   "dimension, the timestep and the frequency bin move with "
                   "it. Not snapped to a whole number of cells. The floor is "
                   "not arbitrary: the two measurement planes sit at fixed "
                   "distances while the line is a fixed number of cells, so a "
                   "mesh finer than this cannot fit enough stations between "
                   "them and the run refuses."),
        Param("strip_cells", "Strip width in cells", "int", MS_N_STRIP,
              lo=4, hi=24, unit="cells",
              help="The strip is drawn this many cells wide. This is the "
                   "quantity the simulation actually contains; the width in "
                   "mm is strip_cells * cell and is reported in the board "
                   "row."),
        # The broadband knobs.  Every one of them is ignored by a tone run --
        # the default -- so a reader who does not want a sweep loses nothing:
        # the report below is unchanged unless excite says pulse.
        Param("excite", "Excitation", "choice", MS_EXCITE,
              choices=("cw", "pulse"),
              help="cw is the single tone every row of the default report is "
                   "measured on; pulse drives a Ricker wavelet instead and the "
                   "band below is then reported one frequency at a time."),
        Param("band_lo", "Band start", "float", MS_BAND_LO_GHZ,
              lo=0.1, hi=40.0, unit="GHz",
              help="Lowest frequency of the broadband sweep. Read only when "
                   "excite is pulse."),
        Param("band_hi", "Band stop", "float", MS_BAND_HI_GHZ,
              lo=0.1, hi=40.0, unit="GHz",
              help="Highest frequency of the broadband sweep; it has to be "
                   "above band_lo and is read only when excite is pulse."),
        Param("n_bins", "Sweep frequencies", "int", MS_N_BINS, lo=3, hi=200,
              help="How many frequencies the sweep reports, spread evenly over "
                   "the band. Each is its own row: no number is averaged "
                   "across the sweep."),
        Param("f_pulse", "Pulse centre", "float", MS_F_PULSE_GHZ,
              lo=0.1, hi=40.0, unit="GHz",
              help="Centre frequency of the Ricker wavelet the pulse run is "
                   "driven with. Read only when excite is pulse."),
    ),
    run=_run_microstrip,
)

MICROSTRIP_BOARD = Study(
    name="microstrip_board",
    title="Microstrip from a board file: the coupon as the layout draws it",
    blurb=(
        "The same run as microstrip, on the coupon a board file actually "
        "contains: one net is picked out of a .kicad_pcb, the substrate "
        "thickness and permittivity are read from the stackup, the port plane "
        "from a pad if one is named, and the box is cropped to the strip. "
        "Every dimension below is a number read out of the file, so the "
        "report says which ones came from the file and which the caller had "
        "to supply: a board without a stackup has no h and no eps_r, and "
        "those two are the only numbers a coupon cannot be simulated "
        "without. A net that tapers is driven from the widest run of it "
        "(taper='dominant'), which is the strip and not the launch, because a "
        "tapered net would otherwise be refused and the commonest coupon "
        "there is would show nothing; naming a pad with port_pad=REF.NUM "
        "takes the choice of port plane away from that rule. beta, eps_eff, "
        "Z0, |S11| and |S21| are measured between stations at 20% and 80% of "
        "the strip, not at the typed-in geometry's 10.4/20.0 mm, and the "
        "same warnings apply: a record too short for the transient to reach "
        "the far absorber lies about beta, so read the fit residual first. "
        "The stations sit between 20% and 80% of the strip and not at its two "
        "ends because the ends are exactly where the board's copper stops "
        "being a uniform line -- the pad's launch fan-out at one, the "
        "terminating absorber at the other -- and the fit assumes everything "
        "between its two planes is the line the file draws."),
    params=(
        Param("board", "Board file", "str", "",
              help="Path to the .kicad_pcb to read. This study has no "
                   "default geometry: the file is the input."),
        Param("net", "Net", "str", "",
              help="Name of the copper net that carries the strip, exactly "
                   "as the board spells it (net names are case-sensitive). "
                   "Nothing picks a net for you."),
        Param("port_pad", "Port pad", "str", "",
              help="Optional REF.NUM, e.g. J1.1: the pad the wave is "
                   "launched from. Empty means no pad is named and the port "
                   "plane is the end of the widest run of the net."),
        Param("eps_r", "Substrate permittivity", "float", 0.0,
              lo=0.0, hi=16.0, unit="",
              help="0 reads the value from the board stackup and is what a "
                   "coupon normally wants; anything else overrides the "
                   "stackup and is reported as supplied by the caller."),
        Param("crop", "Crop the box to the strip", "bool", True,
              help="End the box where the strip does, keeping the outline's "
                   "lateral clearance. Off keeps the whole outline, which "
                   "costs cells the strip does not use."),
        # The ceiling is 32, not 24, because 32 is the largest value
        # ``to_cell_counts`` can name: its search for a fitting mesh is
        # ``range(1, 33)`` (board.py:631), so a coupon whose only fitting mesh is
        # 32 would otherwise be told to pass a value this study refuses -- the
        # same contradiction the nsteps cap was. A finer cell is the only way to
        # reduce the discretisation error of a mesh that has to be integral, so
        # the ceiling has to reach past the coarsest useful mesh.
        Param("n_sub", "Substrate cells", "int", MS_N_SUB, lo=1, hi=32,
              unit="cells",
              help="Cells across the substrate. Sets the cell size, so every "
                   "dimension and the timestep move with it. A board's strip "
                   "is whatever the layout drew, so it is rarely a whole "
                   "number of cells at the default: the refusal names the "
                   "n_sub values that do fit this coupon, and the ceiling is "
                   "32 because that is the finest the refusal will ever "
                   "name."),
        # The ceiling is 64, not 40: at h = 1.6 mm a 0.1 mm cell needs 48
        # air cells for the top PML face to sit 3h above the strip, and a face
        # any closer absorbs the mode (measured: passivity sum 0.753 at 12).
        Param("n_air", "Air cells", "int", MS_N_AIR, lo=1, hi=64,
              unit="cells",
              help="Cells between the strip and the lid at zmax."),
        Param("n_top", "Lid absorber cells", "int", MS_N_TOP, lo=0, hi=12,
              unit="cells",
              help="0 leaves the lid a plain PEC and builds no absorber "
                   "there; a non-zero value opens it."),
        Param("npml", "Matched-layer cells", "int", MS_N_PML, lo=2, hi=12,
              unit="cells",
              help="Layer thickness at each absorbing face, both x ends and "
                   "both lateral ends; thicker absorbs more and costs more "
                   "cells."),
        Param("nsteps", "Leapfrog steps", "int", MS_NSTEPS, lo=64,
              hi=20000,
              help="The first quarter is warm-up; the rest is Fourier "
                   "transformed. The record also has to be long enough for "
                   "the launched transient to leave the line."),
        Param("f0", "Drive frequency", "float", MS_F_TARGET / 1e9,
              lo=1.0, hi=20.0, unit="GHz",
              help="Wanted tone; the run uses the nearest DFT bin of the "
                   "record and reports both."),
        Param("n_stations", "Measurement stations", "int", MS_N_STATIONS,
              lo=2, hi=21, unit="cells",
              help="Samples of the gap voltage along the strip, spread over "
                   "20-80% of it."),
        # The broadband knobs.  Every one of them is ignored by a tone run --
        # the default -- so a reader who does not want a sweep loses nothing:
        # the report below is unchanged unless excite says pulse.
        Param("excite", "Excitation", "choice", MS_EXCITE,
              choices=("cw", "pulse"),
              help="cw is the single tone every row of the default report is "
                   "measured on; pulse drives a Ricker wavelet instead and the "
                   "band below is then reported one frequency at a time."),
        Param("band_lo", "Band start", "float", MS_BAND_LO_GHZ,
              lo=0.1, hi=40.0, unit="GHz",
              help="Lowest frequency of the broadband sweep. Read only when "
                   "excite is pulse."),
        Param("band_hi", "Band stop", "float", MS_BAND_HI_GHZ,
              lo=0.1, hi=40.0, unit="GHz",
              help="Highest frequency of the broadband sweep; it has to be "
                   "above band_lo and is read only when excite is pulse."),
        Param("n_bins", "Sweep frequencies", "int", MS_N_BINS, lo=3, hi=200,
              help="How many frequencies the sweep reports, spread evenly over "
                   "the band. Each is its own row: no number is averaged "
                   "across the sweep."),
        Param("f_pulse", "Pulse centre", "float", MS_F_PULSE_GHZ,
              lo=0.1, hi=40.0, unit="GHz",
              help="Centre frequency of the Ricker wavelet the pulse run is "
                   "driven with. Read only when excite is pulse."),
    ),
    run=_run_microstrip_board,
)

STUDIES: dict = {study.name: study
                 for study in (CAVITY, MODES, DUCT, SCATTER, RCS, MICROSTRIP,
                               MICROSTRIP_BOARD)}
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


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------
def _main(argv: list[str] = None) -> int:
    """Run one study: ``python -m emfit.studies NAME [key=value ...]``.

    Prints a single ``RESULT`` line of ``key=value`` tokens (spaces inside a
    value become underscores, so the line splits on whitespace) followed by one
    ``FIGURE`` line per image, and writes the figures under
    ``$EMFIT_STUDY_OUT`` (default ``study-out/<name>``).  Nothing here is
    interactive, so the line can be taken from a detached ``nohup`` run.
    """
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    name = argv.pop(0) if argv else "cavity"
    study = get(name)
    values = coerce(study, dict(arg.split("=", 1) for arg in argv if "=" in arg))

    sink = FigureSink()
    t_start = time.perf_counter()
    metrics = study.run(values, sink)
    elapsed = time.perf_counter() - t_start

    fields = " ".join(f"{k.replace(' ', '_')}={str(v).replace(' ', '_')}"
                      for k, v in metrics.items())
    print(f"RESULT study={study.name} wall={elapsed:.2f}s {fields}", flush=True)

    out = os.environ.get("EMFIT_STUDY_OUT") or os.path.join("study-out", study.name)
    for path in sink.save_to(out):
        print(f"FIGURE {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
