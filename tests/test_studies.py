"""Tests for :mod:`emfit.studies`, the catalogue behind every front end.

Only two kinds of claim are made here, and both are cheap:

* *Registration.*  A study in :data:`emfit.studies.STUDIES` is reachable by
  name through :func:`emfit.studies.get`, and its knobs coerce to exactly the
  keys and types it declares.  The check is written against the registry rather
  than against one entry, so a study added later is covered for free.
* *A tiny wave run.*  ``microstrip`` is the only study that builds a full 3-D
  time-domain case, so a smoke test is the only honest thing to run in a test
  suite: a handful of cells per axis, a few dozen steps, and assertions about
  shape and finiteness only.  ``Z0`` and ``eps_eff`` on such a grid are junk --
  pinning junk is worse than pinning nothing -- so they are deliberately
  **not** asserted.  The closed-form reference those numbers are compared
  against is not junk and not from the grid: it is the Hammerstad-Jensen value
  at the declared cross-section, so it is pinned -- on the 35 um foil the study
  is cut from, together with the two values that foil must leave alone,
  ``eps_eff`` and ``beta``.
* *The default case, once.*  The one grid whose numbers mean something is the
  default mesh, and the two ways to get a plausible-looking wrong ``beta`` out
  of it are a record too short for the transient and a phase difference taken
  between two stations.  That run is pinned: the snapped drive frequency, the
  fitted ``beta``, ``eps_eff`` and the two fit diagnostics, so neither failure
  can come back unnoticed.  It costs a few seconds, which is the price of the
  only physical claim in the file.
* *One refusal.*  ``n_strip`` sizes the strip on the mesh and ``w`` sizes the
  cross-section the closed form is evaluated at, and nothing else ties them
  together, so a pair that names two different widths is refused before the grid
  is built.  Both halves are pinned -- the mismatch raises, the library default
  still runs -- on a grid of a few hundred edges.
"""

from __future__ import annotations

import cmath
import dataclasses
import time
from pathlib import Path

import numpy as np
import pytest

from emfit import studies
from emfit.board import Load
from emfit.grid import Grid
from emfit.materials import M_sigma
from emfit.microstrip import COPPER_T, Microstrip
from emfit.operators import CellComplex


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------
def test_microstrip_study_is_registered():
    """``microstrip`` is a registry key and its declaration is well-formed."""
    assert "microstrip" in studies.STUDIES

    study = studies.get("microstrip")
    assert study is studies.STUDIES["microstrip"]
    assert study.name == "microstrip"
    assert callable(study.run)
    assert study.title and study.blurb

    # The knobs are exactly the declared ones, with the declared types: the
    # contract every entry in the registry is consumed under.
    values = studies.coerce(study, {})
    assert set(values) == {p.key for p in study.params}
    assert isinstance(values["nsteps"], int)
    assert isinstance(values["npml"], int)
    assert isinstance(values["f0"], float)

    # ... and it is present alongside the pre-existing studies, not instead.
    assert {"cavity", "modes", "duct", "scatter", "rcs"} <= set(studies.STUDIES)


ROOT = Path(__file__).resolve().parent.parent
COUPON = ROOT / "kicad_support_project" / "kicad_support_project.kicad_pcb"


def test_microstrip_board_study_is_registered():
    """``microstrip_board`` is a registry key whose knobs are all typed.

    Its three text knobs are the whole input -- the board file, the net and the
    optional pad -- because this study has no default geometry: everything else
    it needs is in the file.  Two things are pinned here and nothing else: the
    exact set of keys with their kinds, since every front end builds a form from
    it, and that each numeric knob's default sits inside its own bounds, since a
    default outside them would make the study unrunnable with no argument given.
    """
    assert "microstrip_board" in studies.STUDIES

    study = studies.get("microstrip_board")
    assert study is studies.MICROSTRIP_BOARD
    assert study.name == "microstrip_board"
    assert callable(study.run)
    assert study.title and study.blurb

    assert {param.key: param.kind for param in study.params} == {
        "board": "str",
        "net": "str",
        "port_pad": "str",
        "eps_r": "float",
        "crop": "bool",
        "n_sub": "int",
        "n_air": "int",
        "n_top": "int",
        "npml": "int",
        "nsteps": "int",
        "f0": "float",
        "n_stations": "int",
        "excite": "choice",
        "band_lo": "float",
        "band_hi": "float",
        "n_bins": "int",
        "f_pulse": "float",
        "animate": "choice",
        "plane": "choice",
        "n_frames": "int",
    }

    for param in study.params:
        if param.kind in ("int", "float"):
            assert param.lo is not None and param.hi is not None, param.key
            assert param.lo <= param.default <= param.hi, (
                param.key, param.lo, param.default, param.hi)


def test_the_board_study_form_defaults_two_substrate_cells():
    """The form's ``n_sub`` default is 2 while ``MS_N_SUB`` is still 4.

    Kills a front end that reads the module constant instead of the declared
    default, and the mirror-image edit that moves the historical constant along
    with the form: the two numbers are separate decisions and are pinned
    separately.  At ``MS_H = 1.6 mm`` they mean a 0.8 mm cell on the form and
    the 0.4 mm cell the reference mesh has always had.  Nothing here makes the
    default argument runnable, either: the reference coupon's cropped strip
    fits only ``n_sub = 16`` or ``32`` at the study's own ``npml = 6`` (measured
    over 1..32), so a board named with no ``n_sub`` is still refused at 2.
    """
    study = studies.get("microstrip_board")
    assert study is studies.STUDIES["microstrip_board"], (
        "the registry is how every front end reaches the study")

    declared = study.param("n_sub")
    assert declared.default == 2, (
        "the form default is 2 cells -- the value coerce() supplies to a run "
        "that names no n_sub")
    assert study.defaults()["n_sub"] == 2, (
        "defaults() is the map a form is pre-filled with, so it has to agree "
        "with the declaration")

    assert studies.MS_N_SUB == 4, (
        "MS_N_SUB is the historical 0.4 mm reference mesh and stays 4")

    assert declared.default != studies.MS_N_SUB, (
        "the form default and the module constant are separate knobs: moving "
        "one must not move the other")
    assert studies.MS_H / declared.default == pytest.approx(0.8e-3), (
        "2 cells across 1.6 mm is a 0.8 mm cell")
    assert studies.MS_H / studies.MS_N_SUB == pytest.approx(0.4e-3), (
        "4 cells across 1.6 mm is the 0.4 mm cell of the reference mesh")


def test_a_str_param_is_free_text():
    """A ``str`` knob takes a path or a net name as typed, and nothing else.

    The path reaches the study byte for byte -- no stripping, no normalising --
    because it is handed straight to a file reader; and an empty string is a
    legal *value*, not a missing one, because ``port_pad`` means "no pad
    named" that way.  The two refusals are the ones that would otherwise be a
    silently ignored keyword: a non-text default and bounds on free text.
    """
    param = studies.Param("board", "Board file", "str", "")
    assert param.kind == "str"
    assert "str: text" in str(param)

    study = studies.Study(
        name="one_text_knob",
        title="t",
        blurb="b",
        params=(param,),
        run=lambda values, sink: {"row": "x"},
    )
    assert studies.coerce(study, {})["board"] == ""
    # An untouched form field sends whitespace, and that is the default, not
    # a path of three spaces.
    assert studies.coerce(study, {"board": "   "})["board"] == ""
    assert studies.coerce(study, {"board": "a/b.kicad_pcb"})["board"] == \
        "a/b.kicad_pcb"

    with pytest.raises(ValueError, match="default must be text"):
        studies.Param("board", "Board file", "str", 3)
    with pytest.raises(ValueError, match="takes no choices and no bounds"):
        studies.Param("board", "Board file", "str", "", lo=1)


def test_microstrip_board_coerces_its_text_knobs():
    """``port_pad`` may be named or left empty; ``n_sub`` is still bounded.

    An empty pad is the ordinary case -- the port plane then comes from the end
    of the widest run of the net -- so it must coerce instead of being refused
    for being empty, and a named one must survive as text.  The numeric bound
    is checked on this study because it is the one that carries a mesh: 99
    substrate cells is above the declared ceiling of 24 and must be said so
    rather than clamped.
    """
    study = studies.get("microstrip_board")

    named = studies.coerce(study, {"board": str(COUPON), "net": "RF_IN",
                                   "port_pad": "J1.1"})
    assert named["port_pad"] == "J1.1"
    assert named["board"] == str(COUPON)
    assert named["net"] == "RF_IN"

    unnamed = studies.coerce(study, {"board": str(COUPON), "net": "RF_IN",
                                     "port_pad": ""})
    assert unnamed["port_pad"] == ""

    with pytest.raises(ValueError, match="above the maximum"):
        studies.coerce(study, {"board": str(COUPON), "net": "RF_IN",
                               "n_sub": 99})


def test_microstrip_board_refuses_a_pad_the_board_does_not_declare():
    """A pad that is not on the board stops the run before any solve.

    ``port_pad`` is free text, so the mistake can only be caught by the board
    reader -- and it must be caught there: the message lists the pads the file
    does declare, which is the only way a caller learns the right name.  The
    coupon has no J9, so this raises inside ``from_kicad`` and costs a file
    parse rather than a run.
    """
    study = studies.get("microstrip_board")
    values = studies.coerce(study, {"board": str(COUPON), "net": "RF_IN",
                                    "port_pad": "J9.7"})
    with pytest.raises(ValueError, match="the pads it declares"):
        study.run(values, studies.FigureSink())


# ---------------------------------------------------------------------------
# a wave run that is deliberately too small to be physical
# ---------------------------------------------------------------------------
def test_microstrip_wave_smoke():
    """A six-cell line for forty steps: populated result, finite phasors."""
    t_start = time.perf_counter()
    result = studies.microstrip_wave(
        n_sub=1,
        n_air=1,
        n_strip=2,
        n_clean=1,
        n_pml=2,
        n_top=0,          # plain PEC lid here; n_top must equal n_pml otherwise
        n_ref=1,
        n_line=6,
        x_first=6.4e-3,
        x_last=11.2e-3,
        n_stations=4,     # the two-wave fit needs four stations
        nsteps=40,
        sink=None,
    )
    elapsed = time.perf_counter() - t_start

    # --- geometry was actually built from the knobs ----------------------
    geo = result.geometry
    assert geo["nsteps"] == 40
    assert geo["n_warm"] == 10                    # a quarter of 40
    assert geo["n_acc"] == 30
    assert geo["nx"] == 2 + 1 + 6
    assert geo["ny"] == 2 * 2 + 2 + 2 * 1
    assert geo["nz"] == 1 + 1
    assert geo["cell"] == pytest.approx(1.6e-3)
    assert geo["f"] > 0.0 and np.isfinite(geo["f"])
    assert geo["dt"] > 0.0 and np.isfinite(geo["dt"])
    assert geo["n_edges"] > 0
    assert len(geo["station_cells"]) == 4

    # --- stations have the requested count, and are ordered -------------
    assert result.station_x.shape == (4,)
    assert result.v_stations.shape == (4,)
    assert np.all(np.isfinite(result.station_x))
    assert np.all(np.diff(result.station_x) > 0.0)  # strictly increasing
    assert result.y_extent > 0.0

    # --- every complex phasor is finite (junk is fine, an inf is not) ---
    phasors = {
        "v_stations": result.v_stations,
        "v_port": np.array([result.v_port]),
        "i_ground_full": np.array([result.i_ground_full]),
        "i_ground_truncated": np.array([result.i_ground_truncated]),
    }
    for name, value in phasors.items():
        assert np.all(np.isfinite(value)), f"{name} is not finite: {value!r}"

    # --- the closed form the run is compared against --------------------
    assert result.beta_model > 0.0
    assert result.eps_eff_model > 1.0
    assert result.z0_model > 0.0
    assert np.isfinite(result.beta) and result.beta > 0.0

    # --- the fits ran and returned numbers, plausible or not ------------
    assert np.isfinite(result.beta_two_station)
    assert np.isfinite(result.beta_two_wave) and result.beta_two_wave > 0.0
    assert np.isfinite(result.gamma)
    assert np.isfinite(result.fit_residual) and result.fit_residual >= 0.0
    assert result.station_fit_ok is True

    # --- and the one-line summary is actually a line --------------------
    line = result.summary()
    assert line.startswith("microstrip ")
    assert "\n" not in line

    # Cheap is the point: this must not become a slow test by accident.
    assert elapsed < 10.0, f"the tiny case took {elapsed:.2f} s"


# ---------------------------------------------------------------------------
# the closed-form reference the tiny run is compared against
# ---------------------------------------------------------------------------
def _study_line(t):
    """The closed form at the study's own cross-section, ``t`` metres of foil."""
    return Microstrip(w=studies.MS_W, h=studies.MS_H, eps_r=studies.MS_EPS_R, t=t)


@pytest.fixture(scope="module")
def tiny_wave():
    """The six-cell run of the smoke test above, run once for the two claims."""
    return studies.microstrip_wave(
        n_sub=1,
        n_air=1,
        n_strip=2,
        n_clean=1,
        n_pml=2,
        n_top=0,
        n_ref=1,
        n_line=6,
        x_first=6.4e-3,
        x_last=11.2e-3,
        n_stations=4,
        nsteps=40,
        sink=None,
    )


def test_microstrip_wave_z0_model_is_the_35_um_foil(tiny_wave):
    """``z0_model`` is 48.099 ohm, the foil value, not the 48.686 sheet one.

    The grid's own impedance is junk on six cells and stays unasserted; this is
    the closed form, which depends on the declared cross-section alone.  The
    two candidates are 0.587 ohm apart, so the second assertion is what gives
    the first one content.
    """
    assert tiny_wave.z0_model == pytest.approx(_study_line(COPPER_T).z0,
                                               rel=1e-12), (
        f"z0_model {tiny_wave.z0_model!r} is not the closed form's "
        f"{_study_line(COPPER_T).z0!r} at this cross-section")
    assert abs(tiny_wave.z0_model - _study_line(0.0).z0) > 0.4, (
        f"z0_model {tiny_wave.z0_model!r} is within 0.4 ohm of the "
        f"zero-thickness {_study_line(0.0).z0!r}, so the foil did not reach it")


def test_microstrip_wave_eps_eff_and_beta_do_not_see_the_foil(tiny_wave):
    """``eps_eff_model`` and ``beta_model`` must be the ``t = 0`` floats, to the bit.

    The thickness correction widens the strip, so it feeds ``Z0`` and nothing
    else; an ``eps_eff`` that moved with it would mean the correction had been
    routed into the dielectric as well.
    """
    foil = _study_line(COPPER_T)
    sheet = _study_line(0.0)
    f = tiny_wave.geometry["f"]
    assert tiny_wave.eps_eff_model == sheet.eps_eff, (
        f"eps_eff_model {tiny_wave.eps_eff_model!r} is not the sheet's "
        f"{sheet.eps_eff!r}")
    assert tiny_wave.beta_model == foil.beta(f), (
        f"beta_model {tiny_wave.beta_model!r} is not the closed form's "
        f"{foil.beta(f)!r} at {f!r} Hz")
    assert foil.beta(f) == sheet.beta(f), (
        "the foil thickness moved beta, which eps_eff alone sets")


# ---------------------------------------------------------------------------
# a finer time step on the same mesh
# ---------------------------------------------------------------------------
def test_microstrip_wave_dt_scale_steps_the_same_mesh_more_finely():
    """``dt_scale`` multiplies the CFL step and leaves every cell alone."""
    knobs = dict(
        n_sub=1,
        n_air=1,
        n_strip=2,
        n_clean=1,
        n_pml=2,
        n_top=0,          # plain PEC lid here; n_top must equal n_pml otherwise
        n_ref=1,
        n_line=6,
        x_first=6.4e-3,
        x_last=11.2e-3,
        n_stations=4,     # the two-wave fit needs four stations
        nsteps=300,       # the shortest record that returns a result at all
        sink=None,
    )
    full = studies.microstrip_wave(dt_scale=1.0, **knobs)
    half = studies.microstrip_wave(dt_scale=0.5, **knobs)

    # --- the step is scaled exactly, not approximately -------------------
    assert half.geometry["dt"] > 0.0
    assert half.geometry["dt"] == 0.5 * full.geometry["dt"]

    # --- and the mesh the step is taken on is untouched ------------------
    for key in ("nx", "ny", "nz", "cell", "nsteps", "n_warm", "n_acc",
                "n_edges", "f"):
        assert half.geometry[key] == full.geometry[key], key

    # --- a step that is not a step is refused before anything is built ---
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError):
            studies.microstrip_wave(dt_scale=bad, **knobs)


# ---------------------------------------------------------------------------
# a refused station fit: the guard, not the physics
# ---------------------------------------------------------------------------
def test_microstrip_wave_refused_station_fit_is_flagged_not_quoted():
    """A refused station fit is flagged and left out, which is all this pins.

    The board below is the smoke board with an open circuit cut into the
    strip and a record too short to resolve what comes back off it, so the
    phase constant arrives carrying a standard error as large as itself and
    the loss-aware station fit has nothing to divide by.  That is a property
    of this deliberately under-resolved two-cell strip, not of the line, so
    nothing about the numbers is asserted here -- only that the run finishes
    and says so.
    """
    with pytest.warns(RuntimeWarning,
                      match="loss-aware station-impedance fit"):
        result = studies.microstrip_wave(
            n_sub=1,
            n_air=1,
            n_strip=2,
            n_clean=1,
            n_pml=2,
            n_top=0,          # plain PEC lid; n_top must equal n_pml
            n_ref=1,
            n_line=6,
            x_first=6.4e-3,
            x_last=11.2e-3,
            n_stations=4,     # the two-wave fit needs four stations
            nsteps=200,       # still under-resolved for this reflecting line
            sink=None,
            loads=(Load(position=8.0e-3, kind="series_r",
                        value=float("inf")),),
        )

    assert result.station_fit_ok is False
    assert result.station_fit_lossy is None


# ---------------------------------------------------------------------------
# the default case: the only physical claim in this file
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_microstrip_default_case_is_converged():
    """The default run measures the line, not the transient.

    Each number below is a property of the default mesh and the default record,
    and each is here because it has been wrong once:

    * the drive is snapped to a DFT bin of the record, and the bin is decided
      by ``n_acc * dt``: ``8 / (1800 dt) = 5.8277864 GHz``, which is also
      ``2 / (450 dt)``, so lengthening the record must not move it;
    * ``beta`` comes from a one-wave fit over all nine stations and must land
      on the analytic 232.5 rad/m for this cross-section; the two-station
      difference over the same span agrees to 0.02 per cent **here**, which is
      why it is kept as a cross-check and not as the answer;
    * ``abs(gamma)`` and the fit residual are the record-length diagnostics: a
      transient still in flight leaves 0.018 and 0.020 at 1200 steps, and by
      the default 2400 they have fallen to 0.007 and 0.009 and stopped moving;
    * ``eps_eff`` follows from ``beta``, so it is pinned to 3.624 -- the value
      the fitted phase constant implies -- and not to the closed-form 3.344,
      which this mesh does not reproduce.
    * ``beta`` is also refitted on each half of the record, and the two halves
      must agree with each other (within ``MS_SETTLE_TOL``) and with the
      whole-record fit: 232.79 and 232.10 rad/m here, 0.30 per cent apart.  A
      record that is still filling fails this one while every other number
      above still looks perfectly reasonable.

    The tolerances are wide enough for a compiler's rounding and tight enough
    that a truncated record, or a two-station ``beta`` on a wrapped span,
    fails them.
    """
    t_start = time.perf_counter()
    result = studies.microstrip_wave(sink=None)
    elapsed = time.perf_counter() - t_start

    geo = result.geometry
    assert geo["nsteps"] == 2400
    assert geo["n_warm"] == 600                  # a quarter of 2400
    assert geo["n_acc"] == 1800

    # --- the tone actually driven, to the part in a million ---------------
    assert geo["f"] == pytest.approx(5.8277864e9, rel=1e-6)

    # --- the phase constant, from the fit, against the closed form --------
    assert result.beta == pytest.approx(232.5, rel=0.01)
    assert result.beta > 0.0                     # a forward wave, always

    # --- the standing wave and the misfit that make that believable ------
    assert abs(result.gamma) < 0.02
    assert result.fit_residual < 0.01

    # --- eps_eff is beta's, so it is pinned to beta's value --------------
    assert result.eps_eff == pytest.approx(3.624, rel=0.01)

    # --- the old estimator is the cross-check now, and it agrees ---------
    assert result.beta_two_station == pytest.approx(result.beta, rel=0.02)

    # --- the record has finished filling, and this is the test of it ------
    # A window can only be believed if it agrees with itself, so the phase
    # constant is refitted on the two halves of the same record.
    assert np.isfinite(result.beta_first_half)
    assert np.isfinite(result.beta_second_half)
    drift = (abs(result.beta_first_half - result.beta_second_half)
             / abs(result.beta))
    assert drift <= studies.MS_SETTLE_TOL, (
        f"the default record is not settled: {result.beta_first_half:.3f} and "
        f"{result.beta_second_half:.3f} rad/m over its two halves, "
        f"{100.0 * drift:.3f} % apart")
    # Each half must also land on the whole-record fit, not merely on the
    # other: two halves agreeing on the wrong line is still the wrong line.
    assert result.beta_first_half == pytest.approx(result.beta, rel=0.02)
    assert result.beta_second_half == pytest.approx(result.beta, rel=0.02)

    # A runaway guard, not a performance measurement: it exists to catch a hang
    # or a grid that has blown up, and it must never be tightened towards the
    # observed run time -- a wall-clock bound near the measured cost makes the
    # suite pass or fail with the machine's load, which is not a physical
    # assertion about the solver.
    assert elapsed < 60.0, f"the default run took {elapsed:.2f} s (runaway guard)"


# ---------------------------------------------------------------------------
# a record that is still filling must say so
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_microstrip_unsettled_record_is_labelled_not_reported():
    """A record still filling is labelled on the rows it would otherwise poison.

    The default record is settled -- 0.30 per cent between its halves -- so the
    claim that a short one is *caught* needs a run of its own: 300 steps on the
    same mesh, whose first half still carries the drive transient (132.9 rad/m
    against 233.4 over the second, 48.9 per cent apart).  What is pinned is not
    those numbers but the wording they produce, because the number a reader
    would take for a measurement is the attenuation: the settledness row must
    say NOT settled and name the tolerance it was judged against, both alpha
    rows must carry ``UNSETTLED`` and call themselves an upper bound, and the
    settledness row must come before the alphas it protects.
    """
    t_start = time.perf_counter()
    study = studies.get("microstrip")
    metrics = study.run(studies.coerce(study, {"nsteps": "300"}),
                        studies.FigureSink())
    elapsed = time.perf_counter() - t_start

    # --- the verdict, and the bar it was judged against -------------------
    settledness = metrics["beta drift (two averaging windows)"]
    assert "NOT settled" in settledness
    assert f"{100.0 * studies.MS_SETTLE_TOL:.1f} %" in settledness

    # --- and the alphas it protects carry the warning themselves ----------
    for key in ("alpha (joint fit, one wave)", "alpha (joint fit, two waves)"):
        row = metrics[key]
        assert "UNSETTLED" in row, f"{key} hid an unsettled record: {row!r}"
        assert "upper bound" in row, f"{key} did not qualify the number: {row!r}"

    # --- the warning has to come before what it warns about --------------
    keys = list(metrics)
    assert (keys.index("beta drift (two averaging windows)")
            < keys.index("alpha (joint fit, one wave)"))

    # A runaway guard, not a performance target: the same 2400-step run takes
    # 15-32 s standalone on this box and took 152.73 s under full pytest, so the
    # budget measures the container's load rather than the code. A runaway or a
    # hang would be minutes, so the guard sits at 300 s; do not tighten it again.
    assert elapsed < 300.0, f"the short study took {elapsed:.2f} s"


# ---------------------------------------------------------------------------
# the mesh, which must not drift again
# ---------------------------------------------------------------------------
def test_microstrip_default_mesh_is_the_historical_case():
    """The default mesh is the recovered reference case, cell for cell.

    These five numbers *are* the case: ``h / n_sub = 0.4 mm`` is the cell the
    reference ``Z0`` and ``eps_eff`` were taken at, and the edge count follows
    from ``62 x 44 x 22``.  Retuning any default changes the case, so the mesh
    is pinned here rather than left to whatever the constants happen to say.
    """
    # The mesh build is not separable from the time loop, so this runs the
    # default geometry for a handful of steps (~0.1 s).  Everything asserted
    # below is decided before the first step, so ``nsteps`` is irrelevant here.
    result = studies.microstrip_wave(nsteps=8)

    geo = result.geometry
    assert geo["nx"] == 62
    assert geo["ny"] == 44
    assert geo["nz"] == 22                 # 4 substrate + 12 air + 6 absorber
    assert geo["n_edges"] == 190296
    assert geo["cell"] == pytest.approx(0.4e-3)



# ---------------------------------------------------------------------------
# the two-plane transmission ratio, on numbers that are exact
# ---------------------------------------------------------------------------
def test_line_s21_de_embeds_the_delay_and_nothing_else():
    """``line_s21`` is a pure amplitude ratio when ``beta`` is real.

    One line, one model: the arrived amplitude is the launched amplitude times
    a real transmission times the line's own delay ``exp(-1j beta d)``.  With
    ``beta`` real the de-embedding factor has unit modulus, so the magnitude
    that comes back is the transmission and the phase removed is only the
    reference.  With ``beta = beta' - 1j alpha`` the raw ratio carries
    ``exp(-alpha d)`` and the factor carries ``exp(+alpha d)``, so the same
    call must return ``1``: the function cannot smuggle a loss of its own into
    either reading.
    """
    a1 = 1.0 + 0.5j                     # arbitrary: only the ratio is used
    x1 = 10.40e-3                       # the default run's first station
    d = 9.60e-3                         # ... to its last
    beta = 232.44696                    # its one-wave phase constant
    transmission = 0.98

    # --- beta real: the magnitude survives, the delay is what was removed ---
    a2 = a1 * transmission * np.exp(-1j * beta * d)
    s21, raw = studies.line_s21(a1, x1, a2, x1 + d, beta)
    assert abs(raw) == pytest.approx(transmission, rel=1e-12)
    assert abs(s21) == pytest.approx(transmission, rel=1e-12)
    assert s21 == pytest.approx(transmission, abs=1e-12)   # real, not complex

    # --- beta complex by -1j alpha: raw decays, de-embedded is exactly 1 ----
    alpha = 3.046
    beta_lossy = beta - 1j * alpha
    a3 = a1 * np.exp(-1j * beta_lossy * d)
    s21_lossy, raw_lossy = studies.line_s21(a1, x1, a3, x1 + d, beta_lossy)
    assert abs(raw_lossy) == pytest.approx(np.exp(-alpha * d), rel=1e-12)
    assert abs(s21_lossy) == pytest.approx(1.0, rel=1e-12)

    # --- the three ways the pair of planes can have no ratio in it --------
    with pytest.raises(ValueError):                     # planes the wrong way
        studies.line_s21(a1, x1 + d, a2, x1, beta)
    with pytest.raises(ValueError):                     # no span at all
        studies.line_s21(a1, x1, a2, x1, beta)
    with pytest.raises(ValueError):                     # nothing launched
        studies.line_s21(0.0, x1, a2, x1 + d, beta)



# ---------------------------------------------------------------------------
# one plane's algebra, and the ratio of two runs that makes s21 honest
# ---------------------------------------------------------------------------
# The default run's own numbers, used as the line every wave here travels on,
# so the arithmetic is tested on a gamma and a zc that are not toys: ~232 rad/m
# and a 4.6 deg phase in zc.
GAMMA = complex(2.4697, 232.44695963784835)
ZC = complex(50.54736386461998, 4.024590867955236)
X = np.linspace(10.4e-3, 20.0e-3, 9)          # the default station span [m]


def test_forward_wave_amplitude_undoes_a_travelling_wave_exactly():
    """``v = A exp(-gamma x)``, ``i = v / zc`` must give ``A`` back at every x.

    The split is exact algebra, not a fit, so the only error left is floating
    point: every station must return the same ``A`` to a part in 1e12, and the
    backward wave must be the rounding noise of ``zc * v / zc - v``.
    """
    a = 1.0e5
    v = a * np.exp(-GAMMA * X)
    i = v / ZC
    fwd = studies.forward_wave_amplitude(v, i, X, GAMMA, ZC)
    assert fwd.shape == X.shape
    assert np.allclose(fwd, a, rtol=1e-12)
    bwd = studies.backward_wave_amplitude(v, i, X, GAMMA, ZC)
    assert np.all(np.abs(bwd) < 1e-12 * abs(a))

    # the two are the same call with the sign of gamma and zc flipped: the
    # forward wave seen through the mirror is the one going the other way
    mirrored = studies.forward_wave_amplitude(v, -i, X, -GAMMA, ZC)
    assert np.allclose(mirrored, bwd, rtol=1e-12, atol=0.0)


def test_two_waves_are_separated_on_a_single_plane():
    """A standing wave needs no span to be split: one plane holds both waves.

    With ``v`` and ``i`` of ``A exp(-gamma x) + B exp(+gamma x)`` the forward
    and backward calls return ``A`` and ``B`` themselves -- referred to
    ``x = 0``, so they agree station to station even though the local phasors
    rotate by tens of radians across the span.
    """
    a = 1.0e5
    b = -0.37e5 + 0.11e5j
    fwd_wave = a * np.exp(-GAMMA * X)
    bwd_wave = b * np.exp(+GAMMA * X)
    v = fwd_wave + bwd_wave
    i = (fwd_wave - bwd_wave) / ZC

    fwd = studies.forward_wave_amplitude(v, i, X, GAMMA, ZC)
    bwd = studies.backward_wave_amplitude(v, i, X, GAMMA, ZC)
    assert np.allclose(fwd, a, rtol=1e-12)
    assert np.allclose(bwd, b, rtol=1e-12)

    # and the reflection coefficient at the first plane is B/A, whichever
    # station it is evaluated on
    assert bwd[0] / fwd[0] == pytest.approx(b / a, rel=1e-12)
    assert bwd[-1] / fwd[-1] == pytest.approx(b / a, rel=1e-12)

    # an index picks stations out instead of returning the whole array
    pair = studies.forward_wave_amplitude(v, i, X, GAMMA, ZC, indices=[0, -1])
    assert pair.shape == (2,)
    assert np.allclose(pair, (fwd[0], fwd[-1]), rtol=1e-15)

    with pytest.raises(ValueError):        # v, i and x must agree in length
        studies.forward_wave_amplitude(v[:-1], i, X, GAMMA, ZC)


def _ratio_of_ratios(v_load, i_load, v_ref, i_ref, gamma=GAMMA, zc=ZC):
    """``s21`` as :func:`microstrip_wave` computes it with a reference.

    Written out here so the test can move ``gamma`` without rebuilding a run.
    The two quotients are formed with the *same* expression
    ``complex(a[1] / a[0])`` that :meth:`LineReference.forward_ratio` uses:
    numpy's complex division and Python's are not the same algorithm in the
    last bit, and only one of them can cancel here.
    """
    reference = studies.LineReference(gamma=gamma, zc=zc, station_x=X,
                                      v_stations=v_ref, i_stations=i_ref)
    a = studies.forward_wave_amplitude(v_load, i_load, X, gamma, zc,
                                       indices=[0, -1])
    return complex(a[1] / a[0]) / reference.forward_ratio(X[0], X[-1])


def test_the_same_two_runs_give_a_ratio_of_one():
    """Identical phasors must divide to ``1``, to the last bit that survives.

    ``forward_ratio`` and the loaded ratio are then the same expression on the
    same numbers, so their quotient is ``1`` in IEEE arithmetic.  It is
    asserted to 1e-15 rather than bit-exactly only because the two quotients
    are formed by different complex divisions (numpy's inside the array path,
    Python's on the returned scalars), which may differ by an ulp.  Anything
    larger means the two paths differ in more than rounding -- a different
    plane, a different factor -- which is the bug the normalisation exists to
    make impossible.
    """
    a = 1.0e5
    b = -0.37e5 + 0.11e5j
    fwd_wave = a * np.exp(-GAMMA * X)
    bwd_wave = b * np.exp(+GAMMA * X)
    v = fwd_wave + bwd_wave
    i = (fwd_wave - bwd_wave) / ZC

    ratio = _ratio_of_ratios(v, i, v, i)
    assert abs(ratio - 1.0) <= 1e-15


def _step_runs():
    """A synthetic two-port: the forward wave steps down 1 -> 0.6 at the load.

    Stations ``0..3`` carry amplitude ``A``, stations ``4..8`` carry ``0.6 A``,
    each with ``i = a / zc``.  A uniform scale in front of the whole line would
    be invisible here -- ``a+`` is de-embedded to ``x = 0`` and is a constant
    for any travelling wave, so scaling the run cancels in the ratio -- but a
    *step between the two planes* is exactly what a transmission coefficient
    measures.
    """
    a = 1.0e5
    amp = np.full(X.shape, a)
    amp[4:] = 0.6 * a
    wave = amp * np.exp(-GAMMA * X)
    i_step = wave / ZC
    fwd_wave = a * np.exp(-GAMMA * X)
    bwd_wave = (-0.37e5 + 0.11e5j) * np.exp(+GAMMA * X)
    v_ref, i_ref = fwd_wave + bwd_wave, (fwd_wave - bwd_wave) / ZC
    return wave, i_step, v_ref, i_ref


def test_a_step_in_the_forward_wave_is_measured_not_fitted():
    """A discontinuity between the planes comes back as its own ratio.

    Every station's ``a+`` is its own amplitude (the exponential cancels), so
    the ratio of the two planes is ``0.6 / 1`` and nothing else: the loaded run
    is compared with the reference run plane by plane, not fitted across the
    step.  That is the property the whole path exists for.
    """
    v_load, i_load, v_ref, i_ref = _step_runs()
    assert _ratio_of_ratios(v_load, i_load, v_ref, i_ref) == pytest.approx(
        0.6, rel=1e-14)


def test_the_ratio_of_ratios_does_not_care_what_alpha_it_was_told():
    """The loss never enters, because it is the same factor in both runs.

    If the true decay is ``alpha_true`` and the supplied ``alpha`` is
    ``alpha_told``, both runs' ``a+`` carry ``exp((alpha_told - alpha_true) x)``
    and so both ratios carry the identical factor ``exp((alpha_told -
    alpha_true) d)``.  Feeding a different ``alpha`` therefore changes the
    quotient by rounding alone.  This is the load-bearing assumption that lets
    the loaded number be quoted without knowing ``alpha``, so it is pinned.
    """
    v_load, i_load, v_ref, i_ref = _step_runs()
    # the real part of gamma is the damping: 0 here, the default run's alpha
    # there.  The quotient must not know which of the two it was told.
    lossless = _ratio_of_ratios(v_load, i_load, v_ref, i_ref,
                                gamma=complex(0.0, GAMMA.imag))
    lossy = _ratio_of_ratios(v_load, i_load, v_ref, i_ref,
                             gamma=complex(2.4697030928, GAMMA.imag))
    assert lossy == pytest.approx(lossless, rel=1e-14)
    assert lossless == pytest.approx(0.6, rel=1e-14)


def test_the_reference_transports_off_its_own_two_planes():
    """Other planes get the station residual rescaled, not a refusal.

    The measurement exists only on the station planes, and what it holds is a
    residual: the split is de-embedded to ``x = 0``, where this pure travelling
    wave is a constant, so the measured ratio is ``1`` -- a run that agrees with
    its own fit has nothing left to measure.  A residual of 1 rescales to 1 over
    any span, which is the point: another pair of planes may only rescale what
    was measured, never add a correction of its own.  It is emphatically *not*
    the local phasor ratio ``exp(-gamma (x2 - x1))``, a quantity this method
    does not return.
    """
    a = 1.0e5
    fwd_wave = a * np.exp(-GAMMA * X)
    reference = studies.LineReference(gamma=GAMMA, zc=ZC, station_x=X,
                                      v_stations=fwd_wave,
                                      i_stations=fwd_wave / ZC)
    # a run consistent with its own reference de-embeds to a constant, so its
    # own ratio is 1 -- there is no decay left in it to measure
    assert reference.forward_ratio(X[0], X[-1]) == pytest.approx(1.0, abs=1e-15)
    for x1, x2 in ((X[0], X[-2]), (X[1], X[-1]), (X[0], X[-1] + 4e-3)):
        got = reference.forward_ratio(x1, x2)
        assert got == pytest.approx(1.0, abs=1e-14)
        # and not the local phasor ratio, which is a different quantity
        assert abs(got - complex(np.exp(-GAMMA * (float(x2) - float(x1))))) > 0.1
    # a reference with no forward wave has nothing to normalise by
    silent = studies.LineReference(gamma=GAMMA, zc=ZC, station_x=X,
                                   v_stations=np.zeros_like(X, dtype=complex),
                                   i_stations=np.zeros_like(X, dtype=complex))
    with pytest.raises(ValueError):
        silent.forward_ratio(X[0], X[-1])




# ---------------------------------------------------------------------------
# |S21| across the station planes, and what a load with no reference may not say
# ---------------------------------------------------------------------------
# The numbers these tests hold the code to were measured on the default mesh
# (24.8 mm of line, 0.4 mm cells, six matched-layer cells, 2400 steps, a
# 5.827786 GHz bin) with the same code: they are a regression fence around a
# published set of values, not a tolerance chosen for comfort.  A board run is
# what they cost, which is why every one of them is a slow test.
SEAM_STEPS = 2400


# The guard below asserts about row *wording* and quotes no measured number, so
# what it has to show is that a loaded, unreferenced record refuses to publish
# an impedance -- not that the mesh converged.  A coarse mesh is therefore the
# honest choice, and the only thing the mesh must buy is a station fit that
# succeeds: if it did not, the rows would collapse to the "n/a: this record
# carried no stations to split" fallback and the test would be vacuous.
GUARD_STEPS = 400


# Three records carry the whole fence, because a board run is what each one
# costs and the rest of the table is interpolated between these ends:
#
# * series 100 ohm is the largest departure the reference path shows from the
#   closed form (+9.040 per cent), so it is the record that moves first if the
#   normalisation is disturbed at all.
# * shunt 1.0 pF is the most reactive load of those measured, so its ``|S21|``
#   is the largest departure from unity on a passive load, and it is the one
#   record taken with no reference -- the guard's case.
# * the 25 and 50 ohm series loads and the 0.2 and 0.5 pF shunts are interior
#   points of the same form; the published control table holds them, and three
#   more board runs here would only re-derive the curve the two ends already
#   fix.
#
# One fixture per record, and each test asks for only the records it needs.
# The rule: a single test costs **at most two board runs**, because one
# 2400-step board is the largest unit a blocking budget can hold and a fixture
# that built all three records at once would make every test that touched it
# cost three -- unschedulable alone, which is the same thing as untested.  That
# is why the reference-path test builds its own reference out of ``free_wave``
# (two runs: free, then loaded) and why the free test shares nothing at all.
#
# The trade, stated so nobody optimises it back into one fixture: a run that
# selects both the free test and the reference-path test requests
# ``free_wave`` twice, and module scope *caches* it, so the full-suite cost is
# still exactly three board runs.  Only a test run alone pays less, which is
# the whole point of splitting them.
@pytest.fixture(scope="module")
def free_wave():
    """The load-free record: one board run, and the reference for a load."""
    return studies.microstrip_wave_board(
        studies.microstrip_reference_board(), nsteps=SEAM_STEPS)


@pytest.fixture(scope="module")
def series100_wave(free_wave):
    """Series 100 ohm on the reference path: one run, on top of the free."""
    reference = studies.LineReference.from_wave(free_wave)
    return studies.microstrip_wave_board(
        dataclasses.replace(
            studies.microstrip_reference_board(),
            loads=(Load(15.2e-3, "series_r", 100.0),)),
        nsteps=SEAM_STEPS, reference=reference)


@pytest.fixture(scope="module")
def shunt1_wave():
    """Shunt 1.0 pF on the default path (no reference): one board run."""
    return studies.microstrip_wave_board(
        dataclasses.replace(
            studies.microstrip_reference_board(),
            loads=(Load(15.2e-3, "shunt_c", 1.0e-12),)),
        nsteps=SEAM_STEPS)


@pytest.mark.slow
def test_free_run_s21_is_the_power_the_matched_layers_took(free_wave):
    """No load, so the departure from unity is the absorber and nothing else.

    Measured 0.981263 at +0.333 degrees over the 9.60 mm between the planes;
    the one-sided fence is 1 per cent, which is what a transmitting length is
    asked for, and it is wide enough to hold a rebuilt mesh.
    """
    wave = free_wave
    assert wave.loaded_without_reference is False
    assert abs(abs(wave.s21) - 0.981263) < 0.01
    assert abs(wave.s21) <= 1.0


@pytest.mark.slow
def test_reference_path_still_reports_the_published_series_hundred(
        series100_wave):
    """The normalised route is untouched, deviation and all.

    0.549464 against the textbook 0.503909 is +9.040 per cent, and that is the
    number the report quotes; if it moves, the reference path was disturbed.
    """
    wave = series100_wave
    textbook = 0.503909
    assert abs(abs(wave.s21) - 0.549464) < 0.001
    deviation_pc = 100.0 * (abs(wave.s21) / textbook - 1.0)
    assert abs(deviation_pc - 9.040) < 0.1


@pytest.mark.slow
def test_a_load_with_no_reference_may_not_exceed_unity(shunt1_wave):
    """A passive load cannot make the transmitted wave larger than the incident.

    Each plane is split on its own phasors and the two forward amplitudes
    divided, so this is a ratio of two measurements of one wave and its
    magnitude is the decay between them.  Measured 0.623117 on the 1.0 pF shunt
    -- the most reactive load, and the one taken with no reference, so it is
    both the largest departure from unity and the guard's own record.
    """
    wave = shunt1_wave
    assert wave.loaded_without_reference is True
    assert abs(wave.s21) <= 1.0


@pytest.mark.slow
def test_metrics_refuse_an_impedance_when_a_load_has_no_reference(monkeypatch):
    """The guard: the magnitude stands, an impedance read out of it may not.

    A loaded record's own station fit assumes one onward wave at every station,
    which is the continuity the load breaks, so its ``z0`` is not the line's
    ``zc`` and nothing recovered from ``s21`` through it means anything.  The
    row has to say that rather than quote a number.
    """
    from emfit import studies as S

    real = S.microstrip_wave

    def loaded(**kwargs):
        kwargs["loads"] = (Load(15.2e-3, "series_r", 100.0),)
        return real(**kwargs)

    monkeypatch.setattr(S, "microstrip_wave", loaded)
    metrics = S.MICROSTRIP.run(
        {"nsteps": GUARD_STEPS, "f0": 5.827786, "npml": 6}, S.FigureSink())
    row = metrics["|S21| between station planes"]
    # Not the no-stations fallback: on a coarse mesh the fit still has to land,
    # or every assertion below would pass on row text that means nothing.
    assert "no stations" not in row, row
    assert "no impedance" in row
    assert "reference=" in row
    assert "ohm" not in row
    unity = metrics["G1 (|S21| within 1 % of unity)"]
    assert "cannot say which is which" in unity
    assert "ohm" not in unity

    # A refusal two rows up contradicted by a number here is not a refusal, so
    # every row that would read an impedance off the same fit has to say the
    # same thing -- and say it without a figure in it.
    for key in ("line Z0 from stations, real part",
                "line Z0, sigma total",
                "line Z0 with loss, real part",
                "port Z, modulus",
                "port Z, phase",
                "port Z, real part",
                "port modulus / model",
                "port real part / model",
                "power-current Z0 at stations",
                "power-current ratio at stations",
                "power-current Z0 at the port plane",
                "power-current ratio at the port plane"):
        row = metrics[key]
        assert "no impedance" in row, f"{key}: {row!r}"
        assert "ohm" not in row, f"{key}: {row!r}"
        assert not any(ch.isdigit() for ch in row), f"{key}: {row!r}"
    eps = metrics["eps_eff"]
    assert "no eps_eff" in eps, eps
    assert not any(ch.isdigit() for ch in eps), eps


@pytest.mark.slow
def test_a_loaded_run_quotes_a_ratio_against_a_load_free_twin():
    """The knob-driven reference path: the study builds the twin, unprompted.

    A record with a load across the strip cannot measure its own line constant,
    so the study runs a load-free twin on the identical mesh and hands it to the
    loaded run as ``reference=``, which turns ``|S21|`` into a ratio of ratios
    while the station-fit rows go on refusing.  That is what this test pins, and
    it does it the way a caller would: the load is declared in the parameter
    dict (``load_kind``/``load_value``), so every step -- twin, reference,
    normalisation -- is the study's own.  ``f0`` is pinned because its default,
    ``6.0`` GHz, is not the measured config; ``eps_r = 4.4``, ``h_mm = 1.6`` and
    ``strip_cells = 8`` are the ``MS_*`` defaults and are not restated.

    Not redundant with
    ``test_metrics_refuse_an_impedance_when_a_load_has_no_reference``: that one
    monkeypatches ``microstrip_wave`` to bolt a load onto a record with no
    ``reference``, which is the direct-caller path -- someone calling the
    low-level function has to run the twin himself, and the study's knobs cannot
    reach that path at all.  It covers what the rows do when nothing normalises
    the record; this one covers what they do when the study normalises it.  The
    station-fit rows refuse on both; ``|S21|`` does not.

    The tolerance is the discriminator, and all three readings of this one
    record are machine-checked: ``0.613960`` with the twin, ``0.327195`` with no
    ``reference=``, and ``0.541741`` for the load-free twin itself, each to
    ``0.01``.  The first two differ by nearly a factor of two, so the ``0.01``
    window holds one and rejects the other; a looser bound would pass on either
    and the test would stop covering the reference at all.  The fourth assertion
    is the identity between them, ``0.327195 / 0.541741 = 0.603970`` reproducing
    the referenced ``0.613960``, held to ``0.02`` because the residual is
    ``1.6`` per cent -- the fit's own, not a free parameter, and still far
    tighter than the ``1.88`` gap it separates.  These are ``300``-step readings,
    and they are a consistency check rather than a measurement of what the load
    transmits: the twin reads ``0.541741`` here because the record is too short,
    not because the line loses half its power, and the same twin reaches
    ``0.989576`` at ``9600`` steps.  What this test rules out is a reference that
    is stale, wrongly paired or wrongly normalised -- a wrong reference breaks the
    identity far more than ``1.6`` per cent.

    The same config at ``9600`` steps (``npml = 6``, the ``0.400`` mm cell, the
    transform using ``7200`` samples) gives the same three readings and the same
    division: ``0.544853`` with no reference, ``0.989576`` for the load-free twin
    and ``0.556575`` with the twin supplied, so ``0.544853 / 0.989576 = 0.550593``
    reproduces ``0.556575`` to ``1.075`` per cent.  That triple is not reachable
    from the study, which always supplies a twin when a load is present; it is
    quoted from a direct ``microstrip_wave(..., reference=None)`` run and is
    recorded here rather than asserted.  Over the two lengths the terms of the
    division climbed ``66.52`` and ``82.67`` per cent while the referenced reading
    fell ``9.35`` per cent, which is why the residual is quoted for the arithmetic
    and not as evidence of convergence.
    """
    from emfit import studies as S

    values = {"nsteps": 300, "npml": 6, "f0": 5.827786,
              "load_kind": "series_r", "load_value": 100.0}
    metrics = S.MICROSTRIP.run(values, S.FigureSink())

    # --- the numeric branch ran, and it is the referenced one -----------------
    row = metrics["|S21| between station planes"]
    assert "no impedance" not in row, row
    assert S.NO_LOADED_IMPEDANCE not in row, row
    # The referenced branch, not the load-free one: this wording only exists
    # when the record was handed a twin to divide itself by.
    assert "ratio of ratios" in row, row
    s21 = float(row.split()[0])          # ValueError if the row went ``n/a``
    assert abs(s21 - 0.613960) < 0.01, row
    unity = metrics["G1 (|S21| within 1 % of unity)"]
    assert "cannot say which is which" not in unity, unity
    assert "per cent" in unity, unity
    passivity = metrics[
        "passivity bound: |S11|^2 + |S21|^2 between the station planes"]
    assert "no passivity bound" not in passivity, passivity
    assert "must satisfy" in passivity, passivity

    # --- and the refusals survive beside it ----------------------------------
    # Tighter than a substring: on a loaded record these rows are the constants
    # themselves, so anything else here is a number smuggled past a refusal.
    assert metrics["eps_eff"] == S.NO_LOADED_BETA, metrics["eps_eff"]
    for key in ("line Z0 with loss, real part",
                "line Z0 from stations, real part",
                "port Z, modulus",
                "power-current Z0 at stations"):
        assert metrics[key] == S.NO_LOADED_IMPEDANCE, f"{key}: {metrics[key]!r}"

    # --- the row that says a twin existed, and its absence without a load ----
    assert "reference" in metrics, sorted(metrics)
    assert "identical run with no load" in metrics["reference"], metrics["reference"]

    # --- the same record, read three ways -------------------------------------
    # (b) The direct-caller path: the study has no knob that suppresses the twin,
    # so an unreferenced loaded record can only be had by calling the bridge.
    # Same board, same load, same mesh, same frequency; only the normalisation
    # differs from the study run above.
    unreferenced_wave = S.microstrip_wave_board(
        dataclasses.replace(S.microstrip_reference_board(),
                            loads=(Load(15.2e-3, "series_r", 100.0),)),
        nsteps=300, f_target=5.827786e9)
    assert unreferenced_wave.loaded_without_reference is True
    unreferenced = abs(unreferenced_wave.s21)

    # (c) The record with no load at all, on the identical mesh: the same run the
    # study builds as its twin, so its ``|S21|`` pins the loss the ratio below
    # divides out.  Third and last board run in this test, and the record the
    # absence check is made on -- no load, so neither a ``load`` nor a
    # ``reference`` row.
    free_metrics = S.MICROSTRIP.run({"nsteps": 300, "npml": 6, "f0": 5.827786,
                                     "load_kind": "none"}, S.FigureSink())
    free = float(free_metrics["|S21| between station planes"].split()[0])
    assert "reference" not in free_metrics, sorted(free_metrics)
    assert "load" not in free_metrics, sorted(free_metrics)

    # Each reading is named, so a shift in either is reported as that number
    # rather than absorbed into the ratio.
    assert abs(unreferenced - 0.327195) < 0.01, unreferenced
    assert abs(free - 0.541741) < 0.01, free

    # The identity the reference path *is*: the loaded reading divided by the
    # twin's own reading -- plane ratio over plane ratio -- reproduces the
    # referenced number, so the twin is being used on the same record, between
    # the same stations, against the same zc.  A stale cache, a wrong plane or a
    # wrong reference impedance would break it.  The residual today is 1.6 per
    # cent, so the window is a deliberately generous 0.02, and it is still far
    # tighter than the factor-of-1.88 gap between the referenced and
    # unreferenced readings that it separates.
    assert abs(s21 - unreferenced / free) < 0.02, (s21, unreferenced / free)


# ---------------------------------------------------------------------------
# the strip the mesh builds against the strip the closed form prices
# ---------------------------------------------------------------------------
def _cheap_strip_kwargs(**overrides):
    """The cheapest grid that still carries a strip, for the width-pair checks.

    ``h = MS_H`` over ``n_sub = 4`` is the historical 0.4 mm cell, which is what
    makes the mismatch testable: a ``n_strip = 2`` pin left over from a coarser
    grid is 0.8 mm against the default 3.2 mm ``w``.  Eight steps are enough
    because the refusal comes before the grid exists -- nothing is stepped.
    The test that the guard lets the *right* pair through cannot use this grid:
    an eight-step record carries no wave for the station fit to read, so it runs
    on the smoke test's own six-cell line instead (``n_sub = 1, n_strip = 2``,
    the same 3.2 mm), which costs a solve and is known to come back.
    """
    kwargs = dict(
        n_sub=4,
        n_air=1,
        n_strip=8,
        n_clean=1,
        n_pml=2,
        n_top=0,          # plain PEC lid; n_top must equal n_pml otherwise
        n_ref=1,
        n_line=20,
        x_first=2.0e-3,
        x_last=3.2e-3,
        n_stations=4,
        nsteps=8,
        sink=None,
    )
    kwargs.update(overrides)
    return kwargs


def test_microstrip_wave_refuses_an_n_strip_that_disagrees_with_w():
    """``n_strip`` sizes the mesh and ``w`` sizes the closed form; a pair that
    disagrees is refused before the grid exists.

    Nothing in the function ties the two together: the strip is ``n_strip``
    cells wide, and ``w`` is only read back when the reference is built
    (``Microstrip(w=w, ...)``).  So a caller can mesh 0.8 mm and quote the phase
    constant of 3.2 mm, and no number on the record would say which width the
    grid was.  That is the bug this test is here for -- ``n_strip=2`` beside the
    default ``w`` is exactly the shape of it.

    The refusal has to come before the solve, and the cheap knobs are the
    evidence: a completed run on this grid is a second of work, the error is
    none.  It also has to name both widths and the count that would have fitted,
    or the caller cannot tell which of the two arguments to change.
    """
    t_start = time.perf_counter()
    with pytest.raises(ValueError) as excinfo:
        studies.microstrip_wave(**_cheap_strip_kwargs(n_strip=2))
    elapsed = time.perf_counter() - t_start

    message = str(excinfo.value)
    # Both widths, in metres: 2 x 0.4 mm against the 3.2 mm ``w``.
    assert "0.0008" in message, message
    assert "0.0032" in message, message
    # ... and the repair: eight cells is what 3.2 mm is at this cell size.
    assert "n_strip=8" in message, message
    # Refused, not run: the grid and the 8-step march are the seconds this
    # comparison saves.
    assert elapsed < 1.0, f"the refusal took {elapsed:.2f} s: it ran the solve"


def test_microstrip_wave_accepts_the_strip_w_names():
    """A pair that agrees still runs: two 1.6 mm cells are the 3.2 mm ``w``.

    The refusal above is only worth having if a legitimate call goes through
    untouched, and the interesting legitimate call is a *non-default* strip:
    ``n_strip = 2`` on the cell ``h / n_sub = 1.6e-3 / 1`` -- the library
    ``w``, reached by two cells instead of eight.  It is the smoke test's own
    geometry and its forty steps, because the point is the comparison at the
    top of the function and not anything the march computes; an eight-step
    record carries no wave, the station fit refuses to form, and the run would
    stop for a reason that has nothing to do with this guard.

    The geometry the run reports is what closes the loop: the strip's own cell
    count and the cell size multiply back to ``w``, so the mesh and the closed
    form are talking about the same metal.
    """
    result = studies.microstrip_wave(**_cheap_strip_kwargs(
        n_sub=1, n_strip=2, n_line=6,
        x_first=6.4e-3, x_last=11.2e-3, nsteps=40))

    geo = result.geometry
    assert geo["n_strip"] == 2
    assert geo["cell"] == pytest.approx(1.6e-3)
    assert geo["n_strip"] * geo["cell"] == pytest.approx(geo["w"])
    assert geo["w"] == pytest.approx(studies.MS_W)


# ---------------------------------------------------------------------------
# forward_ratio away from the station planes: how a residual rescales
# ---------------------------------------------------------------------------
# Synthetic stations on the default coupon's own geometry: 0.4 mm apart from
# 10.4 mm, the span a real run's probes sit on, over a gamma and a zc that are
# the default run's (see GAMMA / ZC above), so nothing here is a toy and
# nothing here solves a field.
XS = 10.4e-3 + 0.4e-3 * np.arange(25)
# The two planes the default run is normalised between -- a port at 3.2 mm and
# a cut at 20 mm, so the upstream plane is 7.2 mm before the first station.
RUN_A = (3.2e-3, 20.0e-3)
# Gamma 1.77 % away from the fit: the residual such a reference leaves behind
# is a couple of degrees over the station span, not a quarter turn.
GAMMA_OFF = GAMMA * 1.0177
# Those residuals, read off the library once and pinned here: 2.2630 deg over
# the 9.6 mm station span, 3.9603 deg over Run A's 16.8 mm.
RESIDUAL_REF = complex(0.9996394917219922, 0.03950369287789778)
RESIDUAL_RUN_A = complex(0.9983450395985279, 0.06911614195418925)


class TestForwardRatioTransport:
    """``LineReference.forward_ratio`` off its own two planes.

    The measurement exists on the station planes only, and the ratio there is a
    *residual*: 1 for a line that agrees with its own fit, because the split has
    already divided out ``exp(gamma x)``.  Off those planes the residual is
    rescaled as ``ratio ** (run_span / station_span)`` -- a departure from the
    fit grows like ``exp(dgamma L)`` over the span ``L`` it was measured on --
    which is exact on a uniform line, composes, and so never invents a
    correction the measurement did not contain.
    """

    @staticmethod
    def _reference(gamma=GAMMA, amplitude=1.0e5):
        """A load-free coupon, split with the matched ``gamma``.

        ``v = A exp(-gamma x)``, ``i = v / zc`` with the coupon's own ``gamma``
        -- the convention :func:`studies.forward_wave_amplitude` documents --
        so the split hands back ``A`` at every station and the residual across
        any pair of stations is 1.  Only the ``LineReference``'s own ``gamma``
        is the caller's to override; the wave is always built matched, so
        ``None``, ``nan`` and ``inf`` describe a reference that disagrees with
        the data rather than a fixture that cannot be built.
        """
        wave = amplitude * np.exp(-GAMMA * XS)
        reference = studies.LineReference(
            gamma=gamma, zc=ZC, station_x=XS, v_stations=wave,
            i_stations=wave / ZC)
        a = studies.forward_wave_amplitude(wave, wave / ZC, XS, GAMMA, ZC,
                                          indices=[0, -1])
        return reference, a

    def test_matching_endpoints_is_bit_identical(self):
        """On the station planes the method is exactly what it always was.

        The residual formed there is the same ``a[1] / a[0]`` the split hands
        back, on the same array path, so the two are the same IEEE number and
        ``==`` -- not ``approx`` -- holds: no existing normalisation moved.
        Asked the other way round the residual is its reciprocal, which is a
        different number, so the pair cannot silently collapse to a constant.
        """
        reference, a = self._reference()
        assert reference.forward_ratio(XS[0], XS[-1]) == complex(a[1] / a[0])
        assert reference.forward_ratio(XS[-1], XS[0]) != complex(a[1] / a[0])

    def test_a_perfect_reference_rescales_to_one(self):
        """A plane change never invents a correction the measurement lacks.

        A reference whose stations agree with its own fit has a residual of 1
        and knows nothing else, so every pair of planes must rescale to 1 --
        inside its span, beyond it, and on the real Run A pair whose upstream
        plane sits 7.2 mm before the first station.  That is the whole safety
        argument for answering off-plane at all.
        """
        reference, _ = self._reference()
        assert reference.forward_ratio(XS[0], XS[-1]) == pytest.approx(
            1.0, abs=1e-15)
        for x1, x2 in ((XS[0], XS[-2]), (XS[1], XS[-1]),
                       (XS[0], XS[-1] + 4e-3), RUN_A, (0.0, 0.2)):
            assert reference.forward_ratio(x1, x2) == pytest.approx(
                1.0, abs=1e-14)

    def test_residual_rescales_as_a_power_of_the_span(self):
        """A residual measured over 9.6 mm rescales to any span as its power.

        With ``gamma`` 1.77 % off the fit, the residual is 2.26 deg over the
        9.6 mm station span; a departure that grows like ``exp(dgamma L)`` puts
        3.96 deg over Run A's 16.8 mm.  That is a power of the measured
        residual -- ``1.75`` of it -- and not the line's own transport.  Both
        forms are pinned: the independent ``M ** (run_span / station_span)``
        and the number itself.
        """
        reference, _ = self._reference(gamma=GAMMA_OFF)
        station_span = float(XS[-1]) - float(XS[0])
        run_span = RUN_A[1] - RUN_A[0]
        residual = reference.forward_ratio(XS[0], XS[-1])
        assert residual == pytest.approx(RESIDUAL_REF, rel=1e-12)
        assert np.degrees(cmath.phase(residual)) == pytest.approx(2.26,
                                                                 abs=0.01)
        got = reference.forward_ratio(*RUN_A)
        assert got == pytest.approx(residual ** (run_span / station_span),
                                   rel=1e-12)
        assert got == pytest.approx(RESIDUAL_RUN_A, rel=1e-12)
        assert np.degrees(cmath.phase(got)) == pytest.approx(3.96, abs=0.01)

    def test_the_transport_does_not_rotate_the_residual(self):
        """Rescaling a near-unity residual must not inject the line's phase.

        The residual is 2.26 deg, so over a longer span it can only grow to a
        few degrees.  Multiplying it by the line's own transport instead
        applies ``exp(-gamma delta)`` -- 95 deg of phase here -- a second time,
        while leaving the magnitude within 2 % of 1: only the phase reveals
        that mistake, so the phase is pinned first and the rejected operator is
        then shown to be nowhere near the answer.
        """
        reference, _ = self._reference(gamma=GAMMA_OFF)
        value = reference.forward_ratio(*RUN_A)
        assert abs(cmath.phase(value)) < 0.1
        assert abs(abs(value) - 1.0) < 1e-2
        delta = (RUN_A[1] - RUN_A[0]) - (float(XS[-1]) - float(XS[0]))
        assert abs(value - complex(np.exp(-GAMMA * delta))) > 0.5

    def test_rescaling_composes(self):
        """Two rescaling steps must equal the one across their outer planes.

        Composition is the property a span rescaling has to have, and it is
        what the rejected operator failed.  It has to be measured on a
        reference whose residual is not 1 -- on a matched one every value is 1
        and the test would prove nothing -- so the residual of an off-gamma
        reference carried to 15 mm and then on to 20 mm is compared with the
        residual carried straight to 20 mm.
        """
        reference, _ = self._reference(gamma=GAMMA_OFF)
        product = (reference.forward_ratio(3.2e-3, 15.0e-3)
                   * reference.forward_ratio(15.0e-3, 20.0e-3))
        assert product == pytest.approx(reference.forward_ratio(3.2e-3,
                                                              20.0e-3),
                                       rel=1e-12)

    def test_reversing_the_planes_inverts_the_ratio(self):
        """The two directions are one measurement and its reciprocal.

        A residual over a signed span must rescale to the reciprocal when the
        span is taken the other way, so the pair multiplies to 1.  Off-gamma,
        where the residual is not 1, that is a real constraint rather than an
        identity.
        """
        reference, _ = self._reference(gamma=GAMMA_OFF)
        assert (reference.forward_ratio(*RUN_A)
                * reference.forward_ratio(RUN_A[1], RUN_A[0])) == pytest.approx(
                    1.0, rel=1e-12)

    def test_guards(self):
        """What it refuses -- and what the old path answers before it can.

        No span to measure a residual over, no forward amplitude left at the
        last station, and a ``gamma`` that is ``nan`` or ``inf`` each refuse
        with a ``ValueError`` naming the thing that is missing.  ``None`` never
        reaches that guard: the split itself uses ``gamma`` and raises
        ``TypeError`` first, on the station planes as much as off them, so the
        guard is defence in depth.  A degenerate reference asked about its own
        planes is likewise answered by the endpoint branch before the span is
        looked at, and returns 1 rather than raising.
        """
        # (a) nothing to measure a residual over -- own planes answered first
        flat = studies.LineReference(
            gamma=GAMMA, zc=ZC, station_x=np.array([5e-3, 5e-3]),
            v_stations=np.full(2, 1.0e5, dtype=complex),
            i_stations=np.full(2, 1.0e5 / ZC, dtype=complex))
        assert flat.forward_ratio(5e-3, 5e-3) == pytest.approx(1.0, abs=1e-15)
        with pytest.raises(ValueError, match="span"):
            flat.forward_ratio(*RUN_A)

        # (b) no forward amplitude at the last station: no residual to rescale
        reference, _ = self._reference()
        v = np.array(reference.v_stations, dtype=complex)
        i = np.array(reference.i_stations, dtype=complex)
        v[-1] = 0.0
        i[-1] = 0.0
        dead = studies.LineReference(gamma=GAMMA, zc=ZC, station_x=XS,
                                     v_stations=v, i_stations=i)
        with pytest.raises(ValueError, match="residual"):
            dead.forward_ratio(*RUN_A)

        # (c) a propagation constant that cannot rescale anything
        for gamma in (complex(np.nan, 0.0), complex(np.inf, 0.0),
                      complex(0.0, np.inf)):
            broken, _ = self._reference(gamma=gamma)
            with pytest.raises(ValueError, match="propagation constant"):
                broken.forward_ratio(*RUN_A)

        # (d) no gamma at all: the split refuses before the guard is reached
        missing, _ = self._reference(gamma=None)
        with pytest.raises(TypeError):
            missing.forward_ratio(*RUN_A)
        with pytest.raises(TypeError):            # the station planes too
            missing.forward_ratio(XS[0], XS[-1])



# ---------------------------------------------------------------------------
# the discrete bridge: is the ``series_r`` load really the resistance it says?
# ---------------------------------------------------------------------------
def _load_bridge(n_strip, *, R=50.0, cell=2.5e-4, ix_load=3, j0=1, k_strip=1):
    """The smallest grid that holds one ``series_r`` bridge, built as studies does.

    Six cells along the line by ``n_strip + 3`` across by three in z, the strip a
    PEC sheet on the ``k_strip`` node layer.  The load block is
    ``emfit/studies.py:2699-2708`` verbatim: free the ``E_x`` edges of the node
    column ``ix_load`` and give each of them ``1 / (len(edges) * R)``.
    """
    nx, nz = 6, 3
    ny = n_strip + 3
    grid = Grid.uniform(nx, ny, nz, nx * cell, ny * cell, nz * cell)
    cc = CellComplex(grid)
    pec = np.array(cc.pec_edge_mask(), dtype=bool)
    j_points = np.arange(j0, j0 + n_strip + 1)
    j_cells = np.arange(j0, j0 + n_strip)
    strip = np.zeros(cc.n_edges, dtype=bool)
    strip[cc.idx_ex(np.arange(1, nx)[:, None], j_points[None, :], k_strip)] = True
    strip[cc.idx_ey(np.arange(1, nx + 1)[:, None], j_cells[None, :], k_strip)] = True
    pec |= strip
    sigma = np.zeros(cc.n_edges, dtype=float)
    edges = cc.idx_ex(np.array([ix_load]), j_points, k_strip).ravel()
    pec[edges] = False
    sigma[edges] += 1.0 / (edges.size * float(R))
    return grid, cc, edges, sigma, cell


def test_series_load_bridge_presents_50_ohm():
    """The bridge's total conductance is ``1/R``, not ``1/R`` times a Hodge factor.

    ``m_sigma`` is the **diagonal of the conductance star, in siemens**
    (``emfit/evolve.py``: "one non-negative entry per primal edge, in siemens";
    it is consumed elementwise against ``m_eps/dt`` in ``FITStepper.__init__``),
    so a value written straight into it is a conductance and the ``A~/L``
    weighting is *already folded in*.  The canonical ``M_sigma`` builder shows
    it: ``M_sigma(grid, cc, sigma=1.0).diag`` on these edges is ``A~/L = cell``,
    not 1 -- a conductivity is multiplied by ``A~/L``; the load block, which
    writes ``1/(len(edges) * R)`` directly, is not.

    So the whole load is ``len(edges)`` conductances of ``1/(len(edges) * R)``
    in parallel between the two equipotential halves of the strip (the ``E_y``
    edges at both node layers bounding the cut stay PEC, which is what stops the
    halves shorting), total ``1/R``.  Measured here on a 1 V step across the cut
    using the code's own ``CellComplex.gradient`` for the edge voltages:
    ``R_eff = 50.000`` ohm at 4 edges and at 8, on two cell sizes.

    This pins the convention, not a taste: had ``1/(len(edges) * R)`` been read
    as a conductivity, the delivered resistance would be ``R * L/A = R/cell`` --
    200 000 ohm at ``cell = 0.25`` mm, i.e. no load at all -- and no choice of
    ``s21`` plane could have rescued a run that made that mistake.
    """
    for n_strip, n_edges_expected in ((3, 4), (7, 8)):
        for cell in (2.5e-4, 1.0e-3):
            grid, cc, edges, sigma, cell = _load_bridge(n_strip, cell=cell)
            assert edges.size == n_edges_expected

            # 1 V across the cut: a step potential at the load's own node column,
            # so the edge voltage is whatever the code's gradient says it is.
            mesh = np.meshgrid(np.arange(cc.nxn), np.arange(cc.nyn),
                               np.arange(cc.nzn), indexing="ij")
            phi = np.zeros(cc.n_nodes)
            phi[cc.idx_node(*(a.ravel() for a in mesh))] = np.where(
                mesh[0].ravel() <= 3, 0.0, 1.0)
            volts = np.abs((cc.gradient() @ phi)[edges])
            assert np.allclose(volts, 1.0, rtol=0.0, atol=1.0e-12)

            i_total = float(np.sum(sigma[edges] * volts))
            r_eff = 1.0 / i_total
            assert abs(r_eff - 50.0) <= 0.5, (
                f"{n_edges_expected} edges on cell={cell}: R_eff = {r_eff!r} ohm")

            # ... and the geometric factor is exactly what the load skips: A~/L
            # equals the cell size here, and M_sigma applies it to a conductivity.
            a_dual = np.asarray(grid.dual_face_area_x()).ravel()
            l_edge = np.asarray(grid.edge_length("x")).ravel()
            assert np.allclose(a_dual[edges] / l_edge[edges], cell)
            assert np.allclose(M_sigma(grid, cc, sigma=1.0).diag[edges], cell)



def test_load_station_is_excluded_from_the_fit():
    """A station on the lumped load's own column is not a station for s11.

    The load is a conductance stamped on the load column's edges, so the field
    there is the load's boundary condition, not the line's travelling wave;
    letting it into ``fit_station_impedance`` turns a stub artefact into a
    quoted ``z0``.  The mask is exercised directly -- a board run would only
    re-test the solver.
    """
    import numpy as np

    cell = 0.0004
    js = np.arange(26, 51, 3, dtype=int)          # 26, 29, ..., 50
    x = js * cell
    v = np.ones(js.size, dtype=complex)
    i = np.ones(js.size, dtype=complex)
    loads = [{"kind": "series_r", "value": 50.0, "column": 50}]

    fit_x, fit_v, fit_i, excluded = studies._station_fit_selection(
        js, x, v, i, loads)

    assert excluded is True
    assert fit_x.size == js.size - 1
    assert [int(round(float(col) / cell)) for col in fit_x] == js[:-1].tolist()
    assert fit_v.size == fit_i.size == fit_x.size
    # The span is the remaining stations', not the full list's.
    assert abs((fit_x[-1] - fit_x[0]) - (x[-2] - x[0])) < 1e-15
    assert abs((fit_x[-1] - fit_x[0]) - (x[-1] - x[0])) > 1e-6

    # No load: every station is kept and nothing is claimed excluded.
    same_x, _, _, excluded_again = studies._station_fit_selection(
        js, x, v, i, [])
    assert excluded_again is False
    assert same_x is x

    # A station list that would drop below fit_station_impedance's four
    # stations is left alone rather than emptied.
    thin = js[-4:]
    thin_x, _, _, thin_excluded = studies._station_fit_selection(
        thin, thin * cell, np.ones(4, dtype=complex),
        np.ones(4, dtype=complex), loads)
    assert thin_excluded is False
    assert thin_x.size == 4


def test_s21_plane_may_sit_downstream_of_the_cut_never_upstream():
    """The extraction plane is the cut or a plane past it -- never one before it.

    Downstream of the cut the wave has already passed the element, so the ratio
    between the port plane and that one is a transmission through the load: that
    is the plane a convergence sweep walks, one N at a time.  Upstream the span
    between the two planes does not contain the load at all, so the ratio stops
    describing it and the index is refused.

    The refusal is exercised on the cheap strip grid (``_cheap_strip_kwargs``)
    with the load at 2.6 mm, which quantises to node column 6 -- both numbers
    appear in the message, so a caller can see which side of the element the
    index landed on.  The *downstream* half cannot be completed on this grid: an
    eight-step record carries no wave, so the run stops for want of a
    station-impedance fit.  That is the assertion -- the downstream index got
    past the plane guard and stopped at the fit, while the upstream ones stopped
    at the plane -- because a completed solve here would be a second of work for
    a claim that is not about the march.
    """
    kwargs = _cheap_strip_kwargs(loads=(Load(2.6e-3, "series_r", 50.0),))

    for upstream in (1, 5):
        with pytest.raises(ValueError) as excinfo:
            studies.microstrip_wave(s21_plane=upstream, **kwargs)
        message = str(excinfo.value)
        assert "UPSTREAM" in message, message
        assert f"node column {upstream}" in message, message
        assert "node column 6" in message, message

    # The cut itself, by name and by its own index, is still accepted: neither
    # stops at the plane guard.
    for at_the_cut in ("cut", 6):
        with pytest.raises(ValueError) as excinfo:
            studies.microstrip_wave(s21_plane=at_the_cut, **kwargs)
        assert "UPSTREAM" not in str(excinfo.value)

    # Downstream: past the guard, and stopped by the record rather than by a plane.
    for downstream in (7, 12):
        with pytest.raises(ValueError) as excinfo:
            studies.microstrip_wave(s21_plane=downstream, **kwargs)
        message = str(excinfo.value)
        assert "UPSTREAM" not in message, message
        assert "node column" not in message, message
        assert "station-impedance fit" in message, message

    # A name other than "cut" is still refused, downstream relaxation or not.
    with pytest.raises(ValueError, match="the only name it takes"):
        studies.microstrip_wave(s21_plane="end", **kwargs)


def test_gamma_port_and_gamma_plane_are_different_quantities():
    """``gamma_port`` and ``gamma_plane`` are two numbers, not one renamed.

    An artefact that quotes a reflection as ``s11`` and also records the
    extraction plane's own reflection has to keep the two apart: the port value
    is what a user's S-parameters are referred to, and it does not move when the
    extraction plane moves, while ``gamma_plane`` is ``b_cut / a_cut`` on that
    plane and exists only when one was named.  A writer that put
    ``gamma_plane`` in both fields would be quoting the element's own cut as an
    input reflection, which is what makes this worth an assertion.

    The nullable half is the span record: with ``s21_plane=None`` there is no
    plane and ``gamma_plane`` stays nan (``MicrostripWave.gamma_plane``), which
    is exactly the case a writer must emit as JSON ``null`` rather than nan.

    Both records are the cheap six-cell line with a load at 8.0 mm, so the pair
    costs about two seconds.
    """
    kwargs = _cheap_strip_kwargs(
        n_sub=1, n_strip=2, n_line=6,
        x_first=6.4e-3, x_last=11.2e-3, nsteps=40,
        loads=(Load(8.0e-3, "series_r", 50.0),))

    span = studies.microstrip_wave(**kwargs)
    assert span.s21_plane_index is None
    assert not np.isfinite(complex(span.gamma_plane).real)
    assert np.isfinite(complex(span.gamma_port).real)
    assert np.isfinite(complex(span.gamma_port).imag)
    assert abs(span.gamma_port) == pytest.approx(0.118088, rel=1e-4)

    at_cut = studies.microstrip_wave(s21_plane="cut", **kwargs)
    assert at_cut.s21_plane_index == 5
    assert np.isfinite(complex(at_cut.gamma_plane).real)
    # The port value is the same number on both records: naming a plane moves
    # where the transmission is measured, not where the reflection is quoted.
    assert at_cut.gamma_port == pytest.approx(span.gamma_port)
    assert abs(at_cut.gamma_plane) == pytest.approx(0.154492, rel=1e-4)
    # Two quantities, a third of a magnitude apart -- not rounding.
    assert abs(abs(at_cut.gamma_port) - abs(at_cut.gamma_plane)) > 1e-2



# ---------------------------------------------------------------------------
# the two AC-4 writer fields
# ---------------------------------------------------------------------------
def _load_run_build_a():
    """Import ``evidence/termination/run_build_A.py`` as a module.

    The writer is a script rather than a package member, so it is reachable
    only by path.  Its module body imports the standard library only and its
    ``main`` sits behind ``if __name__ == "__main__"``, so importing it writes
    nothing and runs no solve.
    """
    import sys

    evidence = Path(__file__).resolve().parents[1] / "evidence" / "termination"
    if str(evidence) not in sys.path:
        sys.path.insert(0, str(evidence))
    import run_build_A

    return run_build_A


def _stub_reference():
    """A stand-in for a ``LineReference``: six attributes are all it reads."""

    class Stub:
        zc = 47.5 + 1.8j
        gamma = 3.1 + 231.0j
        station_x = np.array([2.0e-3, 6.8e-3, 11.6e-3])

    return Stub()


class TestAc4ReferenceAndDeembedWriterFields:
    """The two artefact fields an AC-4 check has to read, and nothing else.

    ``run.reference`` records the line the reflection was measured on, and
    ``s21.deembed_distance_m`` records how far the reflection was moved to
    reach the port plane.  A grader that compares a measured ``|Gamma|``
    against ``|R - Zc|/(2Zc + R)`` needs the first or it has no ``Zc``, and it
    needs the second only if it wants to know the gap is not zero.  Neither
    was in any artefact before this writer change, so neither could be read
    and the AC-4 block stayed ``achieved: None``.

    All three claims here are cheap: two stub-level calls and one six-cell
    line, about four seconds together.
    """

    def test_run_reference_publishes_the_line_it_was_given(self):
        """``run_reference`` is the record, not a rearrangement of it.

        Six keys, the line's own numbers in them, and ``None`` in, ``None``
        out -- that last one is the reference-free case, which must stay a
        JSON ``null`` rather than becoming a dict of ``nan``.

        The key names are deliberately unsuffixed (``zc_re``, not
        ``zc_re_ohm``), which is what makes this a separate helper from
        :func:`describe_reference` and not a duplicate of it: the artefact's
        ``run`` block already names its units in the key, and an AC-4 reader
        that looked for ``zc_ohm`` would find nothing.
        """
        run_build_A = _load_run_build_a()
        got = run_build_A.run_reference(_stub_reference())

        assert set(got) == {
            "zc_re",
            "zc_im",
            "gamma_re",
            "gamma_im",
            "station_span_m",
            "n_stations",
        }
        assert got["zc_re"] == pytest.approx(47.5)
        assert got["zc_im"] == pytest.approx(1.8)
        assert got["gamma_re"] == pytest.approx(3.1)
        assert got["gamma_im"] == pytest.approx(231.0)
        assert got["station_span_m"] == pytest.approx(9.6e-3)
        assert got["n_stations"] == 3

        # No reference in play is an absent field, not a zeroed one.
        assert run_build_A.run_reference(None) is None

    def test_deembed_distance_is_the_port_to_first_station_gap(self):
        """``deembed_distance`` is ``station_x[0] - ix_port * cell``, not a span.

        ``MicrostripWave.deembed_distance`` is documented as the distance the
        reflection was moved upstream, and that is the port plane to the
        *first* station (``emfit/studies.py:3263``, docstring ``:1532-1533``).
        It is emphatically not "the s21 plane span minus the port plane":
        on this record the span is ``station_x[-1] - station_x[0]`` and the
        two numbers differ by the probe span, here about 4.8 mm.

        The identity is worth pinning because both writer fields that carry it
        -- ``s11.deembed_distance_m`` and ``s21.deembed_distance_m`` -- are
        the *same attribute* of the same object, so they are equal by
        construction and an assertion that they agree would be tautological.
        What is not tautological is that the attribute is this gap and not
        some span, and a writer that recomputed either field from
        ``s21_planes_m`` would get a number 2.4x too large and still look
        plausible.
        """
        kwargs = _cheap_strip_kwargs(
            n_sub=1, n_strip=2, n_line=6,
            x_first=6.4e-3, x_last=11.2e-3, nsteps=40,
            loads=(Load(8.0e-3, "series_r", 50.0),))
        res = studies.microstrip_wave(**kwargs)

        geometry = res.geometry
        expected = float(res.station_x[0] - geometry["ix_port"] * geometry["cell"])
        assert res.deembed_distance == pytest.approx(expected)
        assert res.deembed_distance > 0.0
        # ... and it is not the probe span, which is what a mis-wiring uses.
        assert res.deembed_distance != pytest.approx(
            float(res.station_x[-1] - res.station_x[0]))

    def test_a_reference_free_run_keeps_the_gap_and_drops_the_reference(self):
        """The two fields are independent: one absent does not null the other.

        A run with no ``reference`` builds no ``LineReference``, so
        ``run.reference`` is ``None`` -- and the reflection is still measured
        on the stations and still moved to the port plane, so the gap is a
        finite number.  A writer that emitted the distance only when a
        reference was in play would silently drop the field from every
        reference-free arm, which is all of them today.
        """
        run_build_A = _load_run_build_a()
        kwargs = _cheap_strip_kwargs(
            n_sub=1, n_strip=2, n_line=6,
            x_first=6.4e-3, x_last=11.2e-3, nsteps=40,
            loads=(Load(8.0e-3, "series_r", 50.0),))
        assert kwargs.get("reference") is None

        res = studies.microstrip_wave(**kwargs)

        assert run_build_A.run_reference(kwargs.get("reference")) is None
        assert np.isfinite(res.deembed_distance)

