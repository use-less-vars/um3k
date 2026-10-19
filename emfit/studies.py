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
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import numpy as np

from . import nearfield
from . import scatter
from . import viz  # selects the Agg backend before pyplot is imported anywhere
from .abc import Mur1Boundary
from .eigen import analytic_box_modes, resonances
from .evolve import FITStepper, RickerSource, cfl_dt
from .grid import Grid
from .materials import C0, material_matrices
from .microstrip import Microstrip
from .operators import CellComplex
from .pml import PML, cells_for_wavelength
from .ports import (
    DftAccumulator,
    LumpedPort,
    column_path,
    edge_path_voltage,
    plate_current,
)

import matplotlib.pyplot as plt  # noqa: E402  (after the backend is fixed)

__all__ = [
    "Param",
    "Study",
    "FigureSink",
    "MicrostripWave",
    "STUDIES",
    "coerce",
    "get",
    "microstrip_wave",
]

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
MS_NSTEPS = 600
#: Matched-layer cells at each absorbing face (``x``, ``y`` and ``zmax``).
MS_N_PML = 6
#: First and last probe station of the default run [m].
MS_X_FIRST, MS_X_LAST = 10.4e-3, 20.0e-3
#: Probe stations along the line.
MS_N_STATIONS = 9
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


@dataclass
class MicrostripWave:
    """What one :func:`microstrip_wave` run measured, and on which mesh.

    Every length is SI metres and every phasor is a complex DFT coefficient of
    the state at ``geometry['f']``, accumulated over the same record for every
    signal, so ratios of two of them are meaningful and the overall normalising
    factor cancels.

    Attributes:
        geometry: Everything the mesh build decided -- cell counts, cell size,
            the strip and port indices, the station cells, ``dt``, the drive
            frequency actually used (a DFT bin, which is not ``f_target``) and
            the warm-up split of the record.
        station_x: ``(n_stations,)`` x positions of the voltage probes [m].
        v_stations: ``(n_stations,)`` complex gap voltages at those stations [V].
        v_port: Complex gap voltage on the port plane [V].
        i_ground_full: Complex return current summed over **every** ``y``
            column of the ground plane at the port station [A].
        i_ground_truncated: The same sum over the physical strip extent only,
            i.e. with the lateral matched-layer columns left out [A].
        y_extent: Half-width used for the truncated sum [m].
        beta: Phase constant from the plain phase difference between the first
            and the last station [rad/m].  No fit: exact only for a single
            travelling wave, and ambiguous once ``beta * d`` passes ``pi``
            (flagged in ``geometry['beta_ambiguous']``).
        beta_model: ``emfit.microstrip`` Hammerstad-Jensen value at the same
            frequency [rad/m].
        z0: ``V / I`` at the port station, ``V`` from the port gap and ``I``
            from the truncated ground return [ohm].
        z0_model: Closed-form quasi-static impedance of the cross-section [ohm].
        eps_eff: Effective permittivity implied by ``beta``.
        eps_eff_model: Closed-form effective permittivity of the cross-section.
    """

    geometry: dict
    station_x: np.ndarray
    v_stations: np.ndarray
    v_port: complex
    i_ground_full: complex
    i_ground_truncated: complex
    y_extent: float
    beta: float
    beta_model: float
    z0: complex
    z0_model: float
    eps_eff: float
    eps_eff_model: float

    def summary(self) -> str:
        """One machine-readable line, the same fields the CLI prints."""
        g = self.geometry
        return (
            f"microstrip f={g['f'] / 1e9:.4f}GHz"
            f" f_target={g['f_target'] / 1e9:.4f}GHz"
            f" cells={g['nx']}x{g['ny']}x{g['nz']}"
            f" cell={g['cell'] * 1e3:.4f}mm nsteps={g['nsteps']}"
            f" n_warm={g['n_warm']}"
            f" beta={self.beta:.4f}rad/m beta_model={self.beta_model:.4f}rad/m"
            f" eps_eff={self.eps_eff:.5f} eps_eff_model={self.eps_eff_model:.5f}"
            f" z0={abs(self.z0):.4f}ohm z0_model={self.z0_model:.4f}ohm"
            f" i_ground_full={abs(self.i_ground_full):.6e}A"
            f" i_ground_truncated={abs(self.i_ground_truncated):.6e}A"
            f" y_extent={self.y_extent * 1e3:.4f}mm")


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
    sink: FigureSink = None,
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
    onto the strip.  The strip runs
    from the port plane to the far ``x`` wall, so the line is **unterminated**:
    there is no resistive edge in this solver, so the far end is a PEC wall and
    the line carries a standing wave.  That is a property of the default case,
    not an accident, and it is why the phase difference below is only a plain
    two-station estimate.

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
        n_stations: Number of probe stations, equally spaced in the wanted span.
        f_target: Wanted drive frequency [Hz].
        nsteps: Leapfrog steps; the first ``n_warm`` are warm-up.
        n_warm: Warm-up steps, ``nsteps // 4`` by default.
        drive: Source amplitude [A].
        sink: Where to put the figure; ``None`` (the default) draws nothing.

    Returns:
        A :class:`MicrostripWave`.

    Raises:
        ValueError: If the mesh or the station span leaves no interior to
            probe, or if warm-up leaves no record to transform.
    """
    n_sub, n_air, n_strip = int(n_sub), int(n_air), int(n_strip)
    n_top = int(n_top)
    n_clean, n_pml, n_ref, n_line = int(n_clean), int(n_pml), int(n_ref), int(n_line)
    n_stations, nsteps = int(n_stations), int(nsteps)
    if n_sub < 1 or n_air < 1 or n_strip < 1 or n_clean < 1 or n_pml < 1:
        raise ValueError(
            "n_sub, n_air, n_strip, n_clean and n_pml must all be at least 1")
    if n_line < 1 or n_ref < 0:
        raise ValueError(f"n_line must be at least 1 and n_ref at least 0")
    if n_stations < 2:
        raise ValueError(
            f"n_stations must be at least 2 to take a phase difference, got "
            f"{n_stations}")

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

    # ``walls`` replaces ``axes``: name every face, and add zmax only when a
    # top layer was actually asked for.
    pml_walls = ("xmin", "xmax", "ymin", "ymax") + (("zmax",) if n_top else ())
    pml = PML(grid, thickness_cells=n_pml, order=2, target=1e-4,
              walls=pml_walls, cc=cc)
    stepper = FITStepper(cc, m_eps, m_mu, dt=cfl_dt(grid), pec=pec, pml=pml)
    dt = float(stepper.dt)

    # --- the record and its DFT bin ----------------------------------------
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

    # --- the time loop -----------------------------------------------------
    acc = DftAccumulator([f0], dt)
    current = np.zeros(cc.n_edges, dtype=float)
    signals = np.zeros(n_stations + 3, dtype=float)
    for n in range(nsteps):
        current[:] = 0.0
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
        acc.add(signals, n)

    spec = acc.spectrum[0]
    v_stations = np.asarray(spec[:n_stations], dtype=complex)
    v_port = complex(spec[n_stations])
    i_full = complex(spec[n_stations + 1])
    i_trunc = complex(spec[n_stations + 2])

    # --- plain two-station phase difference; no fit this turn ---------------
    d_probe = float(station_x[-1] - station_x[0])
    d_phase = float(np.angle(v_stations[-1] * np.conj(v_stations[0])))
    beta = -d_phase / d_probe

    line = Microstrip(w=float(w), h=float(h), eps_r=float(eps_r))
    beta_model = float(line.beta(f0))
    eps_eff = (beta * C0 / (2.0 * np.pi * f0)) ** 2
    z0 = complex(v_port / i_trunc) if i_trunc != 0.0 else complex(np.nan, np.nan)

    geometry = {
        "nx": nx, "ny": ny, "nz": nz, "cell": cell,
        "length": nx * cell, "width": ny * cell, "height": nz * cell,
        "h": float(h), "w": float(w), "eps_r": float(eps_r),
        "n_sub": n_sub, "n_air": n_air, "n_top": n_top, "n_strip": n_strip,
        "n_clean": n_clean, "n_pml": n_pml, "n_ref": n_ref, "n_line": n_line,
        "ix_port": ix_port, "ix_far": nx, "k_strip": k_strip,
        "j_strip": (j0, j1), "j_centre": j_centre, "y_extent": y_half,
        "station_cells": [int(v) for v in js],
        "f": f0, "f_target": float(f_target), "dt": dt,
        "nsteps": nsteps, "n_warm": n_warm, "n_acc": n_acc,
        "n_edges": cc.n_edges, "n_faces": cc.n_faces,
        "beta_ambiguous": bool(abs(beta_model) * d_probe > np.pi),
    }

    if sink is not None:
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
                     f"driven at {f0 / 1e9:.3f} GHz, {nsteps} steps of "
                     f"{dt:.3e} s. The dotted ramp is the closed-form phase "
                     "slope at the same frequency."))

    return MicrostripWave(
        geometry=geometry,
        station_x=station_x,
        v_stations=v_stations,
        v_port=v_port,
        i_ground_full=i_full,
        i_ground_truncated=i_trunc,
        y_extent=y_half,
        beta=beta,
        beta_model=beta_model,
        z0=z0,
        z0_model=float(line.z0),
        eps_eff=float(eps_eff),
        eps_eff_model=float(line.eps_eff),
    )


def _run_microstrip(values: Mapping[str, Any], sink: FigureSink) -> dict:
    """Study wrapper: one default wave run, reported as formatted strings."""
    result = microstrip_wave(
        f_target=float(values["f0"]) * 1e9,
        nsteps=int(values["nsteps"]),
        n_pml=int(values["npml"]),
        sink=sink)
    g = result.geometry
    gain = abs(result.i_ground_full) / max(abs(result.i_ground_truncated), 1e-300)
    return {
        "drive frequency": (f"{g['f'] / 1e9:.4f} GHz "
                            f"(asked {g['f_target'] / 1e9:.4f} GHz, snapped to a DFT bin)"),
        "mesh": f"{g['nx']} x {g['ny']} x {g['nz']} cells at {g['cell'] * 1e3:.4f} mm",
        "box": (f"{g['length'] * 1e3:.2f} x {g['width'] * 1e3:.2f} x "
                f"{g['height'] * 1e3:.2f} mm, {g['nsteps']} steps "
                f"({g['n_acc']} transformed)"),
        "stations": (f"{len(result.station_x)} from "
                     f"{result.station_x[0] * 1e3:.2f} to "
                     f"{result.station_x[-1] * 1e3:.2f} mm"),
        "beta": f"{result.beta:.3f} rad/m",
        "beta (Hammerstad-Jensen)": f"{result.beta_model:.3f} rad/m",
        "beta error": (f"{100.0 * (result.beta / result.beta_model - 1.0):.2f} %"
                       if result.beta_model else "n/a"),
        "eps_eff": f"{result.eps_eff:.5f}",
        "eps_eff (Hammerstad-Jensen)": f"{result.eps_eff_model:.5f}",
        "Z0 = V/I at the port": f"{abs(result.z0):.3f} ohm",
        "Z0 (Hammerstad-Jensen)": f"{result.z0_model:.3f} ohm",
        "ground current, full domain": f"{abs(result.i_ground_full):.6e} A",
        "ground current, strip extent": f"{abs(result.i_ground_truncated):.6e} A",
        "full / strip current": f"{gain:.3f}",
        "beta ambiguity": ("beta*d > pi: the two-station difference has aliased"
                           if g["beta_ambiguous"] else "phase step below pi"),
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
        "beta comes from a plain phase difference between the first and last "
        "station (no fit yet), Z0 from V/I at the port station, eps_eff from "
        "beta, and each is printed next to the Hammerstad-Jensen closed form. "
        "The far end of the strip is a PEC wall, so the default case carries a "
        "standing wave; read the phasor figure before believing beta."),
    params=(
        Param("nsteps", "leapfrog steps", "int", MS_NSTEPS, lo=64, hi=4000,
              help="The first quarter is warm-up; the rest is Fourier "
                   "transformed, and the drive frequency is snapped to one of "
                   "its bins."),
        Param("f0", "drive frequency", "float", MS_F_TARGET / 1e9,
              lo=1.0, hi=20.0, unit="GHz",
              help="Wanted tone; the run uses the nearest DFT bin of the "
                   "record and reports both."),
        Param("npml", "matched-layer cells", "int", MS_N_PML, lo=2, hi=12,
              help="Layer thickness at each absorbing face (both x ends and "
                   "both lateral ends); thicker absorbs more and costs more "
                   "cells."),
    ),
    run=_run_microstrip,
)

STUDIES: dict = {study.name: study
                 for study in (CAVITY, MODES, DUCT, SCATTER, RCS, MICROSTRIP)}
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
