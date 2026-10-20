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
  **not** asserted.
* *The default case, once.*  The one grid whose numbers mean something is the
  default mesh, and the two ways to get a plausible-looking wrong ``beta`` out
  of it are a record too short for the transient and a phase difference taken
  between two stations.  That run is pinned: the snapped drive frequency, the
  fitted ``beta``, ``eps_eff`` and the two fit diagnostics, so neither failure
  can come back unnoticed.  It costs a few seconds, which is the price of the
  only physical claim in the file.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from emfit import studies


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

    # --- and the one-line summary is actually a line --------------------
    line = result.summary()
    assert line.startswith("microstrip ")
    assert "\n" not in line

    # Cheap is the point: this must not become a slow test by accident.
    assert elapsed < 10.0, f"the tiny case took {elapsed:.2f} s"


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

