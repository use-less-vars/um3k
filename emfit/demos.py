"""Demo mode: two small, coarse-mesh microstrip demonstrations.

This module is **not** part of the measured study catalogue.  It exists so a
reader can open a browser, press one button and see a microstrip line and a
loaded microstrip line solve, with the field picture that goes with them.  Both
runs are deliberately cheap (one cell size, a few thousand nodes, a few
thousand steps) and the numbers they print are illustrative: the strip is only
:data:`N_SUB` cells above its ground plane, so ``eps_eff`` reads roughly 12 %
above the closed form, and the tone frequency lands on the DFT bin nearest the
one that was asked for.  Every row says which of the two it is reporting rather
than hiding the difference.  Quote :mod:`emfit.studies`' own studies, not these,
when a number has to survive review.

Registration happens at the *bottom* of :mod:`emfit.studies` (after its
``STUDIES`` literal), so the dependency points one way only: this module imports
``Param``/``Study``/``FigureSink``/``microstrip_wave`` from it, and it merges
``DEMOS`` back into its registry once it has finished defining them.
"""

import math
import time

import matplotlib

matplotlib.use("Agg")            # noqa: E402 - must precede pyplot

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402

from .board import Load                       # noqa: E402
from .studies import (FigureSink, LineReference, Param, Study,  # noqa: E402
                      microstrip_wave)

__all__ = ["DEMOS"]

#: Cells across the substrate.  ``cell = h / N_SUB``; the strip is built on the
#: node layer at ``z = h`` and is ``n_strip`` cells wide, so the strip width the
#: mesh actually contains is ``n_strip * cell`` -- that is the width handed to
#: the closed form as well, never a separate wish.
N_SUB = 2
N_CLEAN = 4
N_PML = 4
N_REF = 2
N_LINE = 40
N_AIR = 8
N_TOP = 4
N_STATIONS = 9

#: Defaults measured on this mesh: 16 215 nodes, 2 400 steps, ~2 s.
DEFAULT_H_MM = 1.6
DEFAULT_EPS_R = 4.4
DEFAULT_F0_GHZ = 5.0
DEFAULT_STRIP_CELLS = 6
DEFAULT_NSTEPS = 2400
DEFAULT_LOAD_AT_MM = 12.8


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
def _line_kwargs(eps_r=DEFAULT_EPS_R, h_mm=DEFAULT_H_MM, f0_ghz=DEFAULT_F0_GHZ,
                 strip_cells=DEFAULT_STRIP_CELLS, nsteps=DEFAULT_NSTEPS):
    """The exact keyword dict for :func:`emfit.studies.microstrip_wave`.

    Args:
        eps_r: Substrate permittivity [dimensionless].
        h_mm: Substrate height [mm]; it also sets the cell, ``h / N_SUB``.
        f0_ghz: Requested drive frequency [GHz].  The run snaps it to a DFT bin.
        strip_cells: Strip width in cells; the width in metres is
            ``strip_cells * h_mm * 1e-3 / N_SUB``.
        nsteps: Time steps of the record.

    Returns:
        A dict of keyword arguments, nothing positional.
    """
    h = float(h_mm) * 1e-3
    cell = h / N_SUB
    return dict(
        h=h,
        w=int(strip_cells) * cell,
        eps_r=float(eps_r),
        n_sub=N_SUB,
        n_air=N_AIR,
        n_top=N_TOP,
        n_strip=int(strip_cells),
        n_clean=N_CLEAN,
        n_pml=N_PML,
        n_ref=N_REF,
        n_line=N_LINE,
        n_stations=N_STATIONS,
        f_target=float(f0_ghz) * 1e9,
        nsteps=int(nsteps),
        keep_slice=True,
        audit=True,
    )


def _stub_loads(load_kind, load_at_mm, load_value):
    """One lumped load, in the units the knobs are given in.

    ``open`` is a bare cut: ``series_r`` with an infinite resistance, which is
    the model's own spelling of an open circuit.  ``shunt_c`` takes picofarads.
    """
    kind = str(load_kind).strip().lower()
    at = float(load_at_mm) * 1e-3
    if kind == "open":
        return (Load(at, "series_r", float("inf")),)
    if kind == "series_r":
        return (Load(at, "series_r", float(load_value)),)
    if kind == "shunt_c":
        return (Load(at, "shunt_c", float(load_value) * 1e-12),)
    raise ValueError(f"unknown load_kind {load_kind!r}; "
                     "available: open, series_r, shunt_c")


def _stub_kwargs(eps_r=DEFAULT_EPS_R, h_mm=DEFAULT_H_MM, f0_ghz=DEFAULT_F0_GHZ,
                 strip_cells=DEFAULT_STRIP_CELLS, nsteps=DEFAULT_NSTEPS,
                 load_kind="series_r", load_at_mm=DEFAULT_LOAD_AT_MM,
                 load_value=200.0):
    """The line's own keyword dict plus its one lumped load.

    ``reference`` is added by the runner: it needs a finished load-free twin on
    the identical mesh, so it cannot be built here.
    """
    kwargs = _line_kwargs(eps_r=eps_r, h_mm=h_mm, f0_ghz=f0_ghz,
                          strip_cells=strip_cells, nsteps=nsteps)
    kwargs["loads"] = _stub_loads(load_kind, load_at_mm, load_value)
    return kwargs


# ---------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------
def _db(value):
    """``|value|`` in decibels, or ``n/a`` when there is no ratio to take."""
    mag = float(abs(value))
    if not math.isfinite(mag) or mag <= 0.0:
        return "n/a dB"
    return f"{20.0 * math.log10(mag):.2f} dB"


def _mesh_row(geometry):
    """One row: what was meshed, and how much of it there is."""
    nodes = ((geometry["nx"] + 1) * (geometry["ny"] + 1)
             * (geometry["nz"] + 1))
    return (f"{nodes} nodes = {geometry['nx'] + 1} x {geometry['ny'] + 1} x "
            f"{geometry['nz'] + 1}, cell {geometry['cell'] * 1e3:.2f} mm, "
            f"{geometry['nsteps']} steps; box "
            f"{geometry['length'] * 1e3:.1f} x {geometry['width'] * 1e3:.1f} x "
            f"{geometry['height'] * 1e3:.1f} mm, strip "
            f"{geometry['n_strip'] * geometry['cell'] * 1e3:.2f} mm wide")


def _frequency_rows(geometry):
    """The requested frequency and the one the run actually accumulated.

    Both rows are always present: the tone accumulator only sees the DFT bins of
    its record, so the second number is the honest one to read a phasor on and
    the first is the one the user typed.
    """
    f = float(geometry["f"])
    f_target = float(geometry["f_target"])
    offset = (f / f_target - 1.0) * 100.0 if f_target else float("nan")
    return {
        "drive frequency": f"{f_target / 1e9:.3f} GHz (requested)",
        "DFT frequency (snapped)": (
            f"{f / 1e9:.4f} GHz ({offset:+.2f} % from the request; the record "
            f"carries {geometry['n_acc']} tone steps, so its bins are the only "
            f"frequencies the phasors live on)"),
    }


def _fit_rows(result):
    """``z0`` off the station fit, or the honest refusal."""
    fit = result.station_fit
    if fit is None:
        return {"z0 (station fit)": "n/a: this record carries no station fit"}
    z0 = complex(fit.z0)
    if not math.isfinite(abs(z0)):
        return {"z0 (station fit)": "n/a: the station fit was refused on this "
                                    "record, so there is no mode to quote"}
    return {"z0 (station fit)": f"{abs(z0):.1f} ohm (|z0|), "
                                f"{math.degrees(math.atan2(z0.imag, z0.real)):+.1f} deg"}


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------
def _add_midplane_figure(sink, result, slug, title, caption):
    """A plain mid-plane ``|Ez|`` heat map: ``slice_ez`` is already a plane."""
    geometry = result.geometry
    ez = np.abs(np.asarray(result.slice_ez))
    fig, ax = plt.subplots(figsize=(7.2, 3.4), layout="constrained")
    image = ax.imshow(ez.T, origin="lower", aspect="equal", cmap="viridis",
                      extent=[0.0, geometry["length"] * 1e3,
                              0.0, geometry["width"] * 1e3])
    ax.set_xlabel("x along the line [mm]")
    ax.set_ylabel("y across the line [mm]")
    ax.set_title(title)
    fig.colorbar(image, ax=ax, label="|Ez| [a.u.]")
    sink.add_figure(slug, title, fig, caption=caption)
    plt.close(fig)


def _add_profile_figure(sink, result, slug, title, caption):
    """``max_y |Ez|`` against x: the standing wave a lumped load sets up."""
    geometry = result.geometry
    ez = np.abs(np.asarray(result.slice_ez))
    profile = ez.max(axis=1)
    x_mm = np.arange(profile.size) * geometry["cell"] * 1e3
    fig, ax = plt.subplots(figsize=(7.2, 3.4), layout="constrained")
    ax.plot(x_mm, profile, color="tab:blue", lw=1.6)
    ax.axvline(geometry["ix_port"] * geometry["cell"] * 1e3, color="0.5",
               ls="--", lw=1.0)
    ax.set_xlabel("x along the line [mm]")
    ax.set_ylabel("max over y of |Ez| [a.u.]")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    sink.add_figure(slug, title, fig, caption=caption)
    plt.close(fig)


# ---------------------------------------------------------------------------
# studies
# ---------------------------------------------------------------------------
def _run_microstrip_line(values, sink):
    """Demo: one unloaded microstrip line, one tone, one picture."""
    kwargs = _line_kwargs(eps_r=values["eps_r"], h_mm=values["h_mm"],
                          f0_ghz=values["f0"],
                          strip_cells=values["strip_cells"],
                          nsteps=values["nsteps"])
    start = time.perf_counter()
    result = microstrip_wave(**kwargs)
    wall = time.perf_counter() - start

    geometry = result.geometry
    metrics = {"mesh and box": _mesh_row(geometry)}
    metrics.update(_frequency_rows(geometry))
    metrics["beta"] = f"{result.beta:.1f} rad/m"
    metrics["beta (closed form)"] = f"{result.beta_model:.1f} rad/m"
    metrics["eps_eff"] = f"{result.eps_eff:.3f}"
    metrics["eps_eff (closed form)"] = f"{result.eps_eff_model:.3f}"
    metrics["|S11|"] = (f"{abs(result.gamma):.4f} = {_db(result.gamma)} at the "
                        f"measured plane")
    metrics["|S11| at the port plane"] = (f"{abs(result.gamma_port):.4f} = "
                                          f"{_db(result.gamma_port)}")
    metrics["|S21|"] = (f"{abs(result.s21):.4f} = {_db(result.s21)} "
                        f"between the station planes")
    metrics.update(_fit_rows(result))
    metrics["mesh caveat"] = (
        f"{N_SUB} cells across the substrate: eps_eff reads about 12 % above "
        f"the closed form and beta about 6 % above it, which is the mesh "
        f"talking, not the physics")
    metrics["solve wall time"] = f"{wall:.2f} s"

    if result.slice_ez is not None:
        _add_midplane_figure(
            sink, result, "midplane-ez",
            f"Demo microstrip line: mid-plane |Ez| at {geometry['f'] / 1e9:.3f} GHz",
            "<b>|Ez| on the mid-plane</b> of one unloaded microstrip line at the "
            "run's DFT frequency. The strip runs along x above the ground plane; "
            "the tone decays into the absorber at the far wall, which is why "
            "|S11| is small.")
    return metrics


def _run_microstrip_stub(values, sink):
    """Demo: the same line with one lumped load, and the wave it reflects."""
    load_kind = str(values["load_kind"])
    load_value = float(values["load_value"])
    kwargs = _stub_kwargs(eps_r=values["eps_r"], h_mm=values["h_mm"],
                          f0_ghz=values["f0"],
                          strip_cells=values["strip_cells"],
                          nsteps=values["nsteps"],
                          load_kind=load_kind,
                          load_at_mm=values["load_at_mm"],
                          load_value=load_value)

    start = time.perf_counter()
    # A loaded record cannot measure its own line constant -- the cut breaks the
    # one-wave assumption the station fit rests on -- so it is given a load-free
    # twin on the identical mesh, whose decomposition supplies the only two
    # things the ratio needs.  The twin keeps no slice and audits nothing: its
    # figures are not this run's output.
    twin_kwargs = dict(kwargs)
    twin_kwargs.pop("loads")
    twin_kwargs["keep_slice"] = False
    twin_kwargs["audit"] = False
    twin = microstrip_wave(**twin_kwargs)
    reference = LineReference.from_wave(twin)
    result = microstrip_wave(reference=reference, **kwargs)
    wall = time.perf_counter() - start

    geometry = result.geometry
    load = kwargs["loads"][0]
    shown = "infinite ohm (a bare cut)" if not math.isfinite(load.value) \
        else f"{load.value:.4g} " + ("ohm" if load.kind == "series_r" else "F")
    metrics = {"mesh and box": _mesh_row(geometry)}
    metrics.update(_frequency_rows(geometry))
    metrics["load"] = (f"{load.kind} = {shown} at x = "
                       f"{load.position * 1e3:.2f} mm of a "
                       f"{geometry['length'] * 1e3:.1f} mm line")
    metrics["|gamma|"] = f"{abs(result.gamma):.4f} (standing wave at z = 0)"
    metrics["|S11|"] = (f"{abs(result.gamma):.4f} = {_db(result.gamma)} at the "
                        f"measured plane")
    metrics["|S11| at the port plane"] = (f"{abs(result.gamma_port):.4f} = "
                                          f"{_db(result.gamma_port)}")
    metrics["|S21|"] = (f"{abs(result.s21):.4f} = {_db(result.s21)} across the "
                        f"station span, normalised by the load-free twin")
    metrics["|S21| (raw)"] = f"{abs(result.s21_raw):.4f} before that normalisation"
    metrics["beta"] = (
        f"{result.beta:.1f} rad/m, but a loaded record's one-wave station fit "
        f"swallows the standing wave the load creates, so this is not the "
        f"line's beta -- the twin's number is the one to quote")
    metrics["beta (closed form)"] = f"{result.beta_model:.1f} rad/m"
    metrics["eps_eff"] = (
        "n/a: the loaded path refuses the line constant (NO_LOADED_BETA in "
        "emfit.studies), so this demo quotes the closed form instead: "
        f"{result.eps_eff_model:.3f} at "
        f"{geometry['f'] / 1e9:.3f} GHz on this strip")
    metrics["mesh caveat"] = (
        f"{N_SUB} cells across the substrate: for scale, the unloaded twin's "
        f"eps_eff reads {twin.eps_eff:.3f} against {twin.eps_eff_model:.3f} "
        f"closed form")
    metrics["solve wall time"] = (f"{wall:.2f} s (twin plus loaded run on the "
                                  f"same mesh)")
    if sink is not None and hasattr(result, "station_fit_ok"):
        metrics["station fit usable"] = ("yes" if result.station_fit_ok else
                                         "no: the reflection is strong enough "
                                         "to break the loss-aware fit, which "
                                         "is a diagnostic this run does not use")

    if result.slice_ez is not None:
        _add_midplane_figure(
            sink, result, "midplane-ez-loaded",
            f"Demo loaded line: mid-plane |Ez| at {geometry['f'] / 1e9:.3f} GHz",
            "<b>|Ez| on the mid-plane</b> with one lumped load on the strip. "
            "The ripple along x is the standing wave the load reflects; its "
            "spacing is half a guided wavelength.")
        _add_profile_figure(
            sink, result, "ez-along-line",
            "Demo loaded line: |Ez| along the strip axis",
            "<b>max over y of |Ez| against x</b>, taken off the same slice. "
            "The dashed line is the port plane. Peaks and nulls alternate at "
            "half a guided wavelength, which is the measurement a load is for.")
    return metrics


demo_microstrip_line = Study(
    name="demo_microstrip_line",
    title="Demo: microstrip line on a coarse mesh",
    blurb=("Demonstration only: one tone down an unloaded microstrip line, "
           "cheap mesh, illustrative numbers."),
    params=(
        Param("eps_r", "Substrate permittivity", "float", DEFAULT_EPS_R,
              lo=1.0, hi=16.0, unit="",
              help="Relative permittivity of the substrate slab."),
        Param("h_mm", "Substrate height", "float", DEFAULT_H_MM,
              lo=1.3, hi=3.2, unit="mm",
              help="Height of the slab, and it also sets the cell: the mesh "
                   "uses h/2, so a taller board is a coarser one."),
        Param("f0", "Drive frequency", "float", DEFAULT_F0_GHZ,
              lo=1.0, hi=20.0, unit="GHz",
              help="The tone the port is driven at. The run reports the DFT "
                   "bin it actually accumulated beside this number."),
        Param("strip_cells", "Strip width", "int", DEFAULT_STRIP_CELLS,
              lo=4, hi=24, unit="cells",
              help="Width of the strip in cells. The mesh fixes the width, so "
                   "this is the width the closed form is given as well."),
        Param("nsteps", "Time steps", "int", DEFAULT_NSTEPS,
              lo=400, hi=4000, unit="steps",
              help="Length of the record. More steps put the DFT bins closer "
                   "together, which is what makes the snapped frequency land "
                   "near the one asked for."),
    ),
    run=_run_microstrip_line,
)

demo_microstrip_stub = Study(
    name="demo_microstrip_stub",
    title="Demo: loaded microstrip line on a coarse mesh",
    blurb=("Demonstration only: the same coarse line with one lumped load, and "
           "the standing wave it reflects."),
    params=(
        Param("eps_r", "Substrate permittivity", "float", DEFAULT_EPS_R,
              lo=1.0, hi=16.0, unit="",
              help="Relative permittivity of the substrate slab."),
        Param("h_mm", "Substrate height", "float", DEFAULT_H_MM,
              lo=1.3, hi=3.2, unit="mm",
              help="Height of the slab; the cell is h/2."),
        Param("f0", "Drive frequency", "float", DEFAULT_F0_GHZ,
              lo=1.0, hi=20.0, unit="GHz",
              help="The tone the port is driven at, before it is snapped to a "
                   "DFT bin."),
        Param("strip_cells", "Strip width", "int", DEFAULT_STRIP_CELLS,
              lo=4, hi=24, unit="cells",
              help="Width of the strip in cells."),
        Param("nsteps", "Time steps", "int", DEFAULT_NSTEPS,
              lo=400, hi=4000, unit="steps",
              help="Length of the record, for both the twin and the loaded "
                   "run."),
        Param("load_kind", "Load kind", "choice", "series_r",
              choices=("series_r", "shunt_c", "open"),
              help="series_r puts a resistor in the trace, shunt_c a capacitor "
                   "to the ground plane, and open cuts the trace outright "
                   "(series_r with an infinite resistance)."),
        Param("load_at_mm", "Load position", "float", DEFAULT_LOAD_AT_MM,
              lo=5.0, hi=34.0, unit="mm",
              help="Distance from the near wall, in the mesh's own metres "
                   "after quantising to the nearest node column."),
        Param("load_value", "Load value", "float", 200.0,
              lo=0.0, hi=1.0e6, unit="",
              help="Ohms for series_r, picofarads for shunt_c. Ignored by "
                   "open, which is an infinite resistance by definition."),
    ),
    run=_run_microstrip_stub,
)

#: Every demonstration, in the order the registry should list them.
DEMOS = (demo_microstrip_line, demo_microstrip_stub)
