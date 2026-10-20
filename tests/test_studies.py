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

import dataclasses
import time

import numpy as np
import pytest

from emfit import studies
from emfit.board import Load


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
    assert result.station_fit_ok is True

    # --- and the one-line summary is actually a line --------------------
    line = result.summary()
    assert line.startswith("microstrip ")
    assert "\n" not in line

    # Cheap is the point: this must not become a slow test by accident.
    assert elapsed < 10.0, f"the tiny case took {elapsed:.2f} s"


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


def test_the_reference_only_answers_on_its_own_two_planes():
    """A ratio measured on other planes is a ratio of another piece of line."""
    a = 1.0e5
    fwd_wave = a * np.exp(-GAMMA * X)
    reference = studies.LineReference(gamma=GAMMA, zc=ZC, station_x=X,
                                      v_stations=fwd_wave,
                                      i_stations=fwd_wave / ZC)
    # a run consistent with its own reference de-embeds to a constant, so its
    # own ratio is 1 -- there is no decay left in it to measure
    assert reference.forward_ratio(X[0], X[-1]) == pytest.approx(1.0, abs=1e-15)
    with pytest.raises(ValueError):        # the wrong downstream plane
        reference.forward_ratio(X[0], X[-2])
    with pytest.raises(ValueError):        # the wrong upstream plane
        reference.forward_ratio(X[1], X[-1])

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

