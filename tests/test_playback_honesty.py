"""The player's label names the STEP it is showing, not the slider's position.

WHAT THIS PINS.  The player counts SOLVER STEPS of the PLANE family on
screen: ``frame_index`` (2400 recorded frames, one per step at the reference
dump) for the y-cut, ``frame_index_xcut`` (240) for the x-cuts.  A dump may also
save its |E| volume on a COARSER grid than those planes (``--volume-stride``):
24 captures, 100 steps apart, at the reference dump.  That volume is a
DECIMATED LAYER on the player's clock, not the clock itself - it used to BE the
clock, which gave 24 positions for 2400 recorded steps, a timeline four times
shorter than the run, and a label that had to explain a gap the player itself
had created.

So the label states ONE clock, read off the dump's own records:
``frame_index`` (the player's step, out of the run's ``nsteps``) and the stride
that axis really runs at - MEASURED from the axis, never the writer's
inconsistent ``e_abs_volume_stride`` scalar.  The |E| volume's decimation is a
property of that LAYER's own clock, so it is logged beside the draw
(``_log_volume_layer_note``) instead of being folded into the sentence.
``TimeAxis`` is that record, ``build_time_axis`` is the ONE place the
precedence between a recorded and a derived axis is decided, and
``_frame_label`` prints it.  So the assertions below are of three kinds:

    * on the SHIPPED reference volume, that the axis is the PLANE family's own
      step axis, that the label names the recorded step of the position drawn,
      and that the count it is out of is the count the scrubber can reach;
    * that the layer's MEASURED decimation is read by the LAYER's sentence and
      never leaks into the player's;
    * on constructed axes, the precedence and the absences - a page with no
      axis keeps the position-counted sentence (the legacy two-argument call),
      and a time base is NEVER invented: no real ``dt_s``, no seconds.

Skips: only when the reference volume itself is absent.  Nothing here boots the
server, builds a layout or touches the plotter - the label is a pure function of
the dump, so this file needs no pyvista, no trame and no VTK.
"""

from __future__ import annotations

import ast
import dataclasses
import gc
import inspect
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries tests/test_poc_playback.py adds, so `import
        # poc_app` resolves from server/poc_app.py
        sys.path.insert(0, _p)

import poc_app as app  # noqa: E402

REFERENCE_NPZ = REPO_ROOT / "artifacts" / "reference_sim_volume.npz"


@pytest.fixture(scope="module")
def real_info():
    """The shipped reference volume, loaded the way a boot loads it."""
    if not REFERENCE_NPZ.is_file():
        pytest.skip(f"reference volume absent: {REFERENCE_NPZ}")
    return app.load_vis(REFERENCE_NPZ)


def _recorded(path):
    """The VOLUME's step axis, the file's stride scalar and the run length.

    Kept as the contrast the axis assertions are made against: the published
    axis must be the PLANE family's (2400 one-step-apart frames), not this one
    (24 captures 100 steps apart), and the ``e_abs_volume_stride`` scalar this
    returns is the writer's known inconsistency rather than a decimation.
    """
    with np.load(path) as data:
        return (
            np.asarray(data["e_abs_volume_step_index"], dtype=int),
            int(np.asarray(data["e_abs_volume_stride"]).ravel()[0]),
            int(np.asarray(data["nsteps"]).ravel()[0]),
        )


def test_the_loader_publishes_the_recorded_step_axis(real_info):
    """``info["time_axis"]`` IS the PLANE family's step axis, not the volume's."""
    volume_steps, _stride_scalar, nsteps = _recorded(REFERENCE_NPZ)
    axis = real_info[app.TIME_AXIS_KEY]
    assert isinstance(axis, app.TimeAxis), (
        f"the loader published {type(axis).__name__}, not a TimeAxis: the label "
        "has nothing it can read a step from"
    )
    plane_steps = np.asarray(real_info["frame_index"], dtype=int)
    assert np.array_equal(axis.step_index, plane_steps), (
        f"the axis is {axis.step_index[:5]}..., the plane family records "
        f"{plane_steps[:5]}...: the player steps the PLANES, so an axis taken "
        "from the volume names the layer's clock as the player's"
    )
    assert not np.array_equal(axis.step_index, volume_steps), (
        "the published axis is still the VOLUME's: the decimated layer has "
        "taken the player's clock again"
    )
    assert axis.stride == 1, (
        f"the axis says a frame spans {axis.stride} steps; the plane family is "
        "recorded every step, and a stride above 1 would print the VOLUME's "
        "decimation on the player's own clock"
    )
    assert axis.n_steps == nsteps, (
        f"the denominator is {axis.n_steps}, the run recorded {nsteps} steps"
    )
    assert axis.n_frames == int(real_info["nt"]) == 2400, (
        f"the axis counts {axis.n_frames} frames, the planes record "
        f"{real_info['nt']}: the scrubber and the label would disagree"
    )
    assert axis.n_frames != volume_steps.size, (
        "the axis counts the volume's 24 captures, so the timeline is the "
        "layer's and not the plane family's"
    )


def test_the_axis_counts_the_frames_the_player_steps(real_info):
    """The axis and the player must be on ONE clock, or the label is unusable.

    ``_frame_label`` prints the axis only when it describes the same number of
    frames the player steps, so this is the assertion that keeps the two from
    drifting apart - and the scrubber's maximum is checked against the same
    count, because a label naming 24 positions above a slider offering 2400 is
    the defect in its other direction.
    """
    axis = real_info[app.TIME_AXIS_KEY]
    plan = app._volume_player_plan(real_info, "ycut")
    assert plan is not None, "the reference volume is the coarser recording"
    assert axis.n_frames == plan["frames"], (
        f"the axis describes {axis.n_frames} frames, the player steps "
        f"{plan['frames']}"
    )
    assert axis.n_frames == 2400, (
        f"the player steps {axis.n_frames} positions, the run recorded 2400 "
        "steps: the volume still has a vote on the length"
    )
    assert app._position_count(real_info) == real_info["nt"], (
        f"the timeline holds {app._position_count(real_info)} positions where "
        f"the planes record {real_info['nt']}: the volume shortened it"
    )
    # OBSOLETE as written: ``_frame_span_max`` took the family on screen and was
    # deleted by the refactor. The maximum is the axis's last position, read
    # straight off the timeline and identical in either mode.
    assert app._frame_max_for(real_info) == axis.n_frames - 1, (
        "the scrubber's maximum is not the axis's last frame"
    )


def test_the_label_names_the_step_the_picture_was_taken_at(real_info):
    """The step on screen and the decimation in effect, read off the file.

    "Step 301 / 2400 (Stride 1)": the PLAYER is at recorded plane frame 301 of
    the run's 2400 solver steps, one position spanning one step.  The |E| layer
    painted there runs on its OWN clock - stored volume frame 4 of 24, captured
    at step 301, 100 steps per stored frame - and is asserted separately below:
    ``_volume_layer_label`` names it and the page logs it, while
    ``_frame_label`` states the player's clock alone.
    """
    axis = real_info[app.TIME_AXIS_KEY]
    plan = app._volume_player_plan(real_info, "ycut")
    frames = plan["frames"]
    for index in (0, 3, 50, 51, 300, 304, frames - 1):
        step = int(axis.step_index[index])
        expected = f"Step {step} / {axis.max_step} (Stride {int(axis.stride)})"
        assert app._frame_label(index, frames, axis) == expected, (
            f"position {index} printed "
            f"{app._frame_label(index, frames, axis)!r}, not {expected!r}: the "
            "label is not naming the recorded step on screen"
        )
    # The LAYER's sentence, unchanged by the player's clock: which stored volume
    # frame is painted at a position, the step it was captured at, its stride.
    for index, layer_expected in (
        (0, "Frame 1 of 24, Volume Decimated \u00d7100 @ step 1"),
        (300, "Frame 4 of 24, Volume Decimated \u00d7100 @ step 301"),
        (304, "Frame 4 of 24, Volume Decimated \u00d7100 @ step 301"),
        (2399, "Frame 24 of 24, Volume Decimated \u00d7100 @ step 2301"),
    ):
        layer = app._volume_layer_label(real_info, "ycut", index)
        assert layer == layer_expected, (
            f"position {index} named the layer {layer!r}, not {layer_expected!r}"
        )
    # The sentences the reference volume is here to pin: the player's own steps
    # are 1, 4, 301, 305 and 2400 - never the layer's capture steps, and never
    # the layer's x100, which belongs to the other clock.
    for index, expected in (
        (0, "Step 1 / 2400 (Stride 1)"),
        (3, "Step 4 / 2400 (Stride 1)"),
        (300, "Step 301 / 2400 (Stride 1)"),
        (304, "Step 305 / 2400 (Stride 1)"),
        # ... and the LAST position is the last recorded step (2400), never the
        # last volume capture (2301): the tail of the run is reachable.
        (2399, "Step 2400 / 2400 (Stride 1)"),
    ):
        assert app._frame_label(index, frames, axis) == expected, (
            f"position {index} printed "
            f"{app._frame_label(index, frames, axis)!r}, not {expected!r}"
        )
    assert int(axis.step_index[300]) == 301, (
        "the 300th recorded plane frame is no longer step 301: the sentences "
        "above would not be the reference volume's"
    )


def test_a_page_with_no_axis_keeps_the_frame_only_sentence():
    """The legacy two-argument call keeps the position-counted sentence."""
    assert app._frame_label(0, 3) == "Step 1 / 3"
    assert app._frame_label(2, 3) == "Step 3 / 3"
    assert app._frame_label(0, None) is None, (
        "None is 'no timeline', never 'Step 1 / None'"
    )
    assert app._frame_label(0, None, app.build_time_axis(n_frames=4)) is None


def test_a_zero_based_record_keeps_the_frame_only_sentence():
    """A base we would have to guess is not printed as a step number.

    A dump whose first capture sits at step 0 numbers its steps from a base it
    never states, so "Step 0 / 12" would put a zero-based numerator under a
    one-based denominator. The axis still answers ``frame_to_step``; only the
    sentence falls back, and it falls back to the position-counted one.
    """
    axis = app.build_time_axis(step_index=[0, 4, 8], n_steps=12, dt_s=1e-12)
    assert axis.n_steps == 12 and axis.frame_to_step(1) == 0
    assert app._frame_label(0, 3, axis) == "Step 1 / 3", (
        f"a zero-based record printed {app._frame_label(0, 3, axis)!r}"
    )


def test_an_axis_of_another_family_is_not_printed(real_info):
    """A 24-frame volume axis must not label a 240-position x-cut timeline."""
    axis = real_info[app.TIME_AXIS_KEY]
    other = int(real_info["nt_x"])
    assert other != axis.n_frames
    assert app._frame_label(0, other, axis) == f"Step 1 / {other}", (
        "the label read an axis describing a different family than the player "
        f"steps: {app._frame_label(0, other, axis)!r}"
    )


def test_one_step_per_frame_when_the_dump_records_no_stride():
    """An undecimated axis STATES its stride: "Stride 1", never silence.

    A label that names its decimation only above 1 leaves the reader unable to
    tell "one step per frame" from "the dump never said" - the same ambiguity
    this page exists to remove, in the other direction.
    """
    axis = app.build_time_axis(
        step_index=np.arange(1, 2401), n_steps=2400, dt_s=1e-12, n_frames=2400
    )
    assert axis.stride == 1
    assert app._frame_label(300, 2400, axis) == "Step 301 / 2400 (Stride 1)", (
        f"undecimated label: {app._frame_label(300, 2400, axis)!r}"
    )


def test_a_decimated_axis_states_the_stride_it_really_runs_at():
    """A stride above 1 is named, MEASURED from the axis, never assumed at 1.

    FAILS IF the stride is hardcoded to 1, if it is derived from a frame or
    position count instead of the axis's own spacing, or if the numerator falls
    back to the position - which would print "Step 4 / 2400" for the frame the
    dump records at step 301.
    """
    axis = app.build_time_axis(
        step_index=np.arange(1, 2401, 100), n_steps=2400, dt_s=1e-12, n_frames=24
    )
    assert axis.n_frames == 24 and axis.n_steps == 2400, (
        f"the constructed axis counts {axis.n_frames} frames of {axis.n_steps} "
        "steps: not the decimated shape this test is about"
    )
    assert axis.stride == 100, (
        f"the axis measured a stride of {axis.stride} from steps 1, 101, 201..."
    )
    assert int(axis.step_index[3]) == 301
    assert app._frame_label(3, 24, axis) == "Step 301 / 2400 (Stride 100)", (
        f"decimated label: {app._frame_label(3, 24, axis)!r}"
    )


def test_a_stated_stride_cannot_relabel_the_axis_being_drawn():
    """The DRAWN axis decides the stride; a dump-wide scalar cannot overrule it.

    ``dump_stride`` is ONE number for a dump whose families are decimated
    differently: ``artifacts/volume_s59.npz`` records ``frame_index`` spaced 1
    apart and ``frame_index_xcut`` spaced 10 apart, so a scalar quoted over a
    100-spaced axis prints "Stride 1" beside frames that advance 100 steps - a
    cadence the picture on screen contradicts. FAILS IF the stated value is
    preferred over the measured spacing, and equally if the scalar is discarded:
    an axis with no even spacing has nothing to measure and must fall back to
    what the dump said, then to one step per frame.
    """
    axis = app.build_time_axis(
        step_index=np.arange(1, 2401, 100), stride=1, n_steps=2400,
        dt_s=1e-12, n_frames=24,
    )
    assert axis.stride == 100, (
        "a stated stride of 1 relabelled a 100-spaced axis: "
        f"{axis.stride}"
    )
    assert app._frame_label(3, 24, axis) == "Step 301 / 2400 (Stride 100)", (
        f"stated-scalar label: {app._frame_label(3, 24, axis)!r}"
    )
    # No even spacing to measure: the dump's own number is the fallback ...
    irregular = app.build_time_axis(step_index=[1, 2, 5], stride=10, n_steps=10)
    assert irregular.stride == 10, (
        f"an irregular axis ignored the stated stride: {irregular.stride}"
    )
    # ... and with no number either, one step per frame, never silence.
    unstated = app.build_time_axis(step_index=[1, 2, 5], n_steps=10)
    assert unstated.stride == 1


def test_frame_and_step_map_through_the_recorded_axis(real_info):
    """Both directions on the PLANE axis, and off-axis answers are absent."""
    axis = real_info[app.TIME_AXIS_KEY]
    assert axis.frame_to_step(1) == 1
    assert axis.frame_to_step(4) == 4
    assert axis.frame_to_step(2400) == 2400
    assert axis.step_to_frame(1) == 1
    assert axis.step_to_frame(300) == 300
    assert axis.step_to_frame(2400) == 2400
    assert axis.step_to_frame(0) is None
    assert axis.frame_to_step(0) is None
    assert axis.frame_to_step(axis.n_frames + 1) is None
    # The earlier-frame rule this page's clock does not need (one frame per step)
    # is still the axis's rule, so a genuinely decimated axis is checked here
    # rather than being left to whatever builds one next.
    spaced = app.build_time_axis(step_index=[1, 101, 201], n_steps=300, dt_s=1e-12)
    assert spaced.step_to_frame(100) == 1, (
        "a step between two captures must resolve to the EARLIER recorded frame: "
        f"{spaced.step_to_frame(100)!r}"
    )
    assert spaced.step_to_frame(101) == 2
    assert spaced.frame_to_step(4) is None, "frame 4 of a 3-frame axis answered"


def test_seconds_exist_only_when_a_dt_was_really_recorded():
    """No real ``dt_s``, no time base: an invented one is the defect itself."""
    for dt in (None, 0.0, -1.0, float("nan"), float("inf"), "not a number"):
        axis = app.build_time_axis(n_frames=3, dt_s=dt)
        assert axis.time_seconds is None, (
            f"a time base was invented from dt_s={dt!r}: "
            f"{axis.time_seconds!r}"
        )
    timed = app.build_time_axis(
        step_index=[1, 101], stride=100, n_steps=200, dt_s=2.5e-12
    )
    assert np.allclose(timed.time_seconds, np.array([1.0, 101.0]) * 2.5e-12)


def test_the_reference_dumps_seconds_are_its_own_dt(real_info):
    axis = real_info[app.TIME_AXIS_KEY]
    assert axis.time_seconds is not None, (
        "the reference dump records a real dt_s, so the axis must carry seconds"
    )
    assert np.allclose(axis.time_seconds, axis.step_index * real_info["dt_s"])


def test_a_backwards_axis_falls_back_to_the_frame_count():
    """An unreadable step record is not a shorter one: count, don't cast order."""
    axis = app.build_time_axis(step_index=[5, 4, 3], n_frames=3)
    assert np.array_equal(axis.step_index, np.array([1, 2, 3]))
    assert axis.stride == 1
    assert axis.n_steps == 3


def test_a_page_with_no_timeline_has_no_axis():
    assert app.build_time_axis() is None
    assert app.build_time_axis(step_index=[], n_frames=0) is None
    assert app.build_time_axis(n_frames=0) is None


def test_the_axis_is_a_frozen_record():
    axis = app.build_time_axis(n_frames=3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        axis.stride = 7  # type: ignore[misc]


def test_the_decimation_is_measured_and_never_the_recorded_scalar(real_info):
    """The layer sentence reads the AXIS, whatever the file states.

    The shipped archive records ``e_abs_volume_stride = 4`` beside a step axis
    that runs 1, 101, 201, ... - a known defect in the writer. Only the axis
    describes the 24 frames actually on disk, so the MEASURED x100 must survive
    every value of that scalar, including none at all.
    """
    axis = real_info[app.TIME_AXIS_KEY]
    frames = app._volume_player_plan(real_info, "ycut")["frames"]
    cases = []
    for bogus in (4, 1, 100, 0, -1, None, "100", 1e3, float("nan")):
        info = dict(real_info)
        info["e_abs_volume_stride"] = bogus
        cases.append((f"e_abs_volume_stride={bogus!r}", info))
    absent = dict(real_info)
    absent.pop("e_abs_volume_stride", None)
    cases.append(("no e_abs_volume_stride", absent))
    for label, info in cases:
        assert app._volume_decimation(info) == 100, (
            f"{label} changed the measured decimation to "
            f"x{app._volume_decimation(info)}: the scalar is being read"
        )
        layer = app._volume_layer_label(info, "ycut", 300)
        assert layer == (
            "Frame 4 of 24, Volume Decimated \u00d7100 @ step 301"
        ), f"{label} printed the layer sentence {layer!r}"
        # ... and the PLAYER's sentence beside it must not inherit the layer's
        # x100: one position, one file, one clock each.
        assert app._frame_label(300, frames, axis) == "Step 301 / 2400 (Stride 1)", (
            f"{label} printed {app._frame_label(300, frames, axis)!r}"
        )


# ---------------------------------------------------------------------------
# The temporal-aliasing report the 3-D player's banner is built from.
#
# The player draws volume frames at its own clock, so on a decimated dump one
# click advances the SOLVER's clock by the stride - and if that jump turns the
# field through more than a period, the motion on screen is an alias of the real
# one.  ``_volume_aliasing`` is the one place that quantity is computed, and it
# is measured from the recording, never from a typed-in wavelength: the cases
# below are the three answers it may give (measured, undecidable, no volume) and
# the two thresholds it applies to a measured phase.
# ---------------------------------------------------------------------------

ALIASING_SENTENCE_X100 = (
    "Temporal Aliasing: Volume is decimated \u00d7100. "
    "Wave motion is not continuous between frames."
)


def test_the_reference_volume_reports_the_alias_it_really_shows(real_info):
    """411.820 deg between stored frames, read out of the dump's own numbers.

    The reference volume is decimated x100 and stores NO complex plane series,
    so the phase comes from the dump's recorded ``f_pulse_hz`` beside its real
    ``dt_s``: 2*pi * 1.5e10 Hz * 7.626299478123987e-13 s * 100 = 7.1876179 rad
    = 411.820 deg per drawn volume frame.  More than a full period, so the frames
    do not continue one another's motion and the banner sentence is true.
    """
    report = app._volume_aliasing(real_info)
    assert report is not None, (
        "the reference volume is the decimated dump this report exists for, and "
        "it came back as 'no volume'"
    )
    assert isinstance(report, app.AliasingReport), (
        f"the report is a {type(report).__name__}, not an AliasingReport"
    )
    assert report.stride == 100, (
        f"the report names a x{report.stride} decimation, the file recorded 100"
    )
    # The report counts the STORED volume frames, not the player's positions: the
    # axis now counts plane frames (2400), and a report quoting that number would
    # be describing a film the volume does not hold.
    stored = int(np.asarray(real_info["e_abs_volume"]).shape[0])
    assert report.frames == stored, (
        f"the report describes {report.frames} frames, the volume stores {stored}"
    )
    assert report.frames == 24, report.frames
    assert report.frames != real_info[app.TIME_AXIS_KEY].n_frames, (
        "the report counted the PLAYER's positions: 2400 positions are not the "
        "24 stored volume frames"
    )
    assert math.isfinite(report.phase_per_frame_rad), (
        f"the phase advance is {report.phase_per_frame_rad!r}: the banner would "
        "be drawn on a number that is not a number"
    )
    # 411.820 deg, measured: the band is wide enough to survive a re-recorded
    # dump at the same decimation but narrow enough that a half-period or a
    # whole-turn error cannot hide inside it.
    degrees = math.degrees(report.phase_per_frame_rad)
    assert 400.0 < degrees < 425.0, (
        f"the field advances {degrees:.3f} deg per volume frame, not the "
        "measured 411.820"
    )
    assert report.frames_per_period == pytest.approx(
        2.0 * math.pi / report.phase_per_frame_rad
    )
    assert 0.85 < report.frames_per_period < 0.90, (
        f"a period lasts {report.frames_per_period:.4f} volume frames: less than "
        "one frame means every stored frame lands at a new phase"
    )
    assert report.aliased is True
    assert report.severity == "discontinuous", (
        f"severity {report.severity!r}: past a full period the frames are not "
        "undersampled, they are unrelated"
    )
    assert "full period" in report.reason, (
        f"the reason does not name the rule that fired: {report.reason!r}"
    )
    assert "f_pulse_hz" in report.source, (
        f"the source does not name the recorded frequency it used: "
        f"{report.source!r}"
    )
    assert report.text == ALIASING_SENTENCE_X100, (
        f"the banner sentence is {report.text!r}, not the page's sentence "
        f"{ALIASING_SENTENCE_X100!r}"
    )


def test_an_undecimated_volume_measures_the_recorded_phase():
    """One stored frame per step: the phase is small and NO banner is due."""
    info = {
        "e_abs_volume": np.zeros((4, 2, 2), dtype=np.float32),
        "dt_s": 1e-12,
        "f_pulse_hz": 1e9,
        "ez_ycut": np.zeros((4, 2, 2), dtype=np.float32),
    }
    report = app._volume_aliasing(info)
    assert report is not None
    assert report.stride == 1, (
        f"a dump with no recorded stride is stored every step, not every "
        f"{report.stride}"
    )
    assert report.phase_per_frame_rad == pytest.approx(2.0 * math.pi * 1e9 * 1e-12)
    assert report.aliased is False
    assert report.severity == "none", f"severity {report.severity!r}"
    assert report.text is None, (
        f"an undecimated volume carried a banner sentence: {report.text!r}"
    )


def test_a_recording_with_no_phase_reference_says_it_cannot_decide():
    """A volume, but neither a complex plane nor f+dt: the answer is silence."""
    info = {
        "e_abs_volume": np.zeros((4, 2, 2), dtype=np.float32),
        "dt_s": None,
        "f_pulse_hz": None,
        "f_ref_hz": None,
        "ez_ycut": np.zeros((4, 2, 2), dtype=np.float32),
    }
    report = app._volume_aliasing(info)
    assert report is not None, (
        "a volume with nothing to measure it by is 'undecidable', not 'no volume'"
    )
    assert report.phase_per_frame_rad is None, (
        f"a phase was invented: {report.phase_per_frame_rad!r}"
    )
    assert report.frames_per_period is None
    assert report.aliased is False
    assert report.text is None, (
        f"a banner was drawn on an undecidable recording: {report.text!r}"
    )
    assert report.reason.strip(), "the undecidable answer carries no reason"


def test_a_complex_plane_series_measures_the_phase_frame_by_frame():
    """Route (a): a complex field whose phase really turns 0.3 rad per frame."""
    frames = 64
    field = np.exp(1j * 0.3 * np.arange(frames))[:, None, None] * np.ones(
        (frames, 4, 3)
    )
    info = {
        "e_abs_volume": np.zeros((frames, 2, 2), dtype=np.float32),
        "e_abs_volume_stride": 1,
        "frame_index": np.arange(frames),
        "ez_ycut": field.astype(np.complex128),
    }
    report = app._volume_aliasing(info)
    assert report is not None
    assert report.phase_per_frame_rad == pytest.approx(0.3, rel=1e-6), (
        f"the tracked phase is {report.phase_per_frame_rad!r}, not the 0.3 rad "
        "the field was built with"
    )
    assert "ez_ycut" in report.source, (
        f"the source does not say which plane was tracked: {report.source!r}"
    )
    assert report.aliased is False
    assert report.text is None


def test_an_all_zero_plane_is_not_read_as_still_motion():
    """A probe that records no field records no phase - it is not 'still'."""
    frames = 8
    info = {
        "e_abs_volume": np.zeros((frames, 2, 2), dtype=np.float32),
        "ez_ycut": np.zeros((frames, 4, 3), dtype=np.complex128),
    }
    report = app._volume_aliasing(info)
    assert report is not None
    assert report.phase_per_frame_rad is None, (
        f"all-zero samples were read as a phase: {report.phase_per_frame_rad!r}"
    )
    assert report.aliased is False
    assert report.text is None


def test_a_page_with_no_volume_has_no_aliasing_report():
    """Nothing decimated, nothing to say: the 2-D page draws no banner."""
    assert app._volume_aliasing({"e_abs_volume": None}) is None


def test_a_reference_frequency_fires_the_quarter_period_rule():
    """Without ``f_pulse_hz`` the recorded ``f_ref_hz`` still decides - 160.000 deg.

    2*pi * 5.82778641e9 Hz * 7.626299478123987e-13 s * 100 = 2.7925268 rad =
    160.000 deg: past a quarter period but not a full one, so the severity is
    'undersampled'. The SENTENCE is the decimation one either way - it is the
    page's only aliasing sentence - which is why this case pins both.
    """
    info = {
        "e_abs_volume": np.zeros((24, 2, 2), dtype=np.float32),
        # The decimation the report uses is MEASURED from this axis (24 captures,
        # 100 steps apart), which is why the axis has to be here at all.
        "e_abs_volume_step_index": np.arange(1, 2401, 100),
        "dt_s": 7.626299478123987e-13,
        "f_pulse_hz": None,
        "f_ref_hz": 5.82778641e9,
        "ez_ycut": np.zeros((2400, 2, 2), dtype=np.float32),
    }
    report = app._volume_aliasing(info)
    assert report is not None
    assert report.severity == "undersampled", f"severity {report.severity!r}"
    assert report.aliased is True
    assert report.text == app._aliasing_sentence(100), (
        f"the banner sentence is {report.text!r}"
    )


# ---------------------------------------------------------------------------
# The volume page's Color Scale control.  The two windows are a CHOICE, so the
# thing worth pinning is that whichever window is in force is SAID - in the
# option the reader picked, on the colour bar they are reading, and (when it
# costs them something) in the warning under the control.  Nothing below boots
# the server, builds a widget or touches the plotter: the titles, the items
# literal and the warning are pure functions of a mode token.
# ---------------------------------------------------------------------------


def test_the_color_scale_offers_the_two_windows_with_global_first():
    """Two options, the global one first, and global is what a page opens on."""
    titles = [app.VOLUME_CLIM_TITLES[token] for token in app.VOLUME_CLIM_MODES]
    assert titles == ["Global (Comparable)", "Per-Frame (Max Contrast)"], titles
    assert app.VOLUME_CLIM_DEFAULT == app.VOLUME_CLIM_GLOBAL
    assert app.VOLUME_CLIM_MODES[0] == app.VOLUME_CLIM_DEFAULT, (
        "the default window is not the first option: the select would open on an "
        f"entry it does not list first ({app.VOLUME_CLIM_MODES!r})"
    )


def test_the_select_items_literal_carries_both_tokens_and_both_window_titles():
    """The JS literal ``v_bind_items`` receives is the two {title, value} dicts."""
    assert ast.literal_eval(app._volume_clim_items_literal()) == [
        {"title": "Global (Comparable)", "value": "global"},
        {"title": "Per-Frame (Max Contrast)", "value": "per_frame"},
    ]


def test_the_volume_bar_names_the_window_its_colours_are_referenced_to():
    """The |E| bar says which window is in force, and the two windows differ."""
    for token, window in (
        (app.VOLUME_CLIM_GLOBAL, "Global (Comparable)"),
        (app.VOLUME_CLIM_PER_FRAME, "Per-Frame (Max Contrast)"),
    ):
        title = app._volume_bar_title(token)
        assert title == f"{app.VOLUME_BAR_TITLE} - {window}", title
        assert window in title, f"the bar title {title!r} omits the window"
    assert app._volume_bar_title(app.VOLUME_CLIM_GLOBAL) != app._volume_bar_title(
        app.VOLUME_CLIM_PER_FRAME
    ), "both windows carry the same bar title: the bar cannot state the window"


def test_both_ramps_are_titled_and_an_unknown_mode_is_the_default_window():
    """A linear retry is never titled log, and junk reads as the global window."""
    for token in app.VOLUME_CLIM_MODES:
        linear = app._volume_bar_title(token, log_scale=False)
        assert linear == (
            f"{app.VOLUME_BAR_TITLE_LINEAR} - {app.VOLUME_CLIM_TITLES[token]}"
        ), linear
        assert app.VOLUME_BAR_TITLE not in linear
    default_title = app._volume_bar_title(app.VOLUME_CLIM_DEFAULT)
    for junk in (None, "", "GLOBAL", "per frame", "per-frame", 3, ["global"]):
        assert app._volume_bar_title(junk) == default_title, (
            f"{junk!r} did not fall back to the default window's title"
        )
    titles = app._volume_bar_titles()
    assert len(titles) == 4, titles
    assert len(set(titles)) == 4, f"two titles collide, one bar is unremovable: {titles}"
    assert all(title.startswith("|E| (") for title in titles), titles


def test_the_per_frame_warning_names_the_offered_option_and_what_it_costs():
    """Warned in the renormalising mode only, by the title the reader picked."""
    for quiet in (app.VOLUME_CLIM_GLOBAL, None, "", "nonsense", 0):
        assert app._volume_clim_warning(quiet) == "", quiet
    warning = app._volume_clim_warning(app.VOLUME_CLIM_PER_FRAME)
    assert warning == app.VOLUME_CLIM_PER_FRAME_WARNING
    assert "Per-Frame (Max Contrast)" in warning, (
        f"the warning does not name the option it belongs to: {warning!r}"
    )
    assert "not visible" in warning, (
        f"the warning does not say what is lost, only that something is: {warning!r}"
    )
    assert bool(warning) is True
    assert bool(app._volume_clim_warning(app.VOLUME_CLIM_GLOBAL)) is False


def test_the_caption_bounds_what_comparable_is_allowed_to_mean():
    """'Comparable' is claimed for this volume's frames and for nothing else."""
    caption = app.VOLUME_CLIM_CAPTION
    assert "this volume" in caption, (
        f"the caption does not scope the claim to one volume: {caption!r}"
    )
    assert "cut sheet" in caption, (
        f"the caption does not except the cut sheets, which keep their own ranges: "
        f"{caption!r}"
    )
    assert "plane sheets" in caption, (
        f"the caption does not except the |Ez| plane stack, which keeps its own "
        f"global ceiling: {caption!r}"
    )
    assert "not comparable" in caption, caption


# ---------------------------------------------------------------------------
# The other half of the same fix: what the control OFFERS is pinned above; what
# the layer DRAWS is pinned here.
#
# Two things can drift apart from the control silently, and neither would fail a
# test that only reads the offered titles:
#
#   * the DEFAULT. The page must boot, and the volume path must fall back, on the
#     whole-recording window - the reference the layer drew before the mode
#     existed - and that window must still be the value
#     ``_volume_abs_global_clim`` returns, compared EXACTLY (not approximately):
#     this is the no-visual-change guarantee the shipped screenshots and every
#     claim made about the reference picture rest on.
#   * the DIFFERENCE between the two windows. A global range is one tuple for the
#     whole recording; a per-frame range is not. If the second ever became the
#     first, "Per-Frame (Max Contrast)" would be a label on the same picture, and
#     if the first ever became the second the recorded decay would be painted
#     away. Both are measured on the shipped volume, so the numbers are the
#     file's own.
#
# Still pure: a mode token and the reference volume. No plotter, no server, no
# widget, no browser.
# ---------------------------------------------------------------------------


def test_the_default_window_is_global_and_the_volume_path_defaults_to_it(real_info):
    """The default token is the global one, and the layer falls back to it."""
    volume = real_info["e_abs_volume"]
    assert app.VOLUME_CLIM_DEFAULT == app.VOLUME_CLIM_GLOBAL, (
        f"the default window token is {app.VOLUME_CLIM_DEFAULT!r}, not the "
        "global one: a volume page that never touches the select now draws a "
        "different reference than the one it has always drawn"
    )
    # The BEHAVIOUR of an absent mode - what a page with no control writes, what
    # a misspelled token writes, what the layer's own getattr fallback yields.
    whole = app._volume_abs_global_clim(volume)
    assert whole is not None, "the reference volume measures no global range"
    for frame in (0, 1, volume.shape[0] - 1):
        drawn = app._volume_clim_for(volume, frame, None)
        assert drawn == whole, (
            f"an absent clim mode drew volume frame {frame} on {drawn!r}, not "
            f"the whole-recording range {whole!r}: the default is not the "
            "global window"
        )
    # ... and the two sites that CHOOSE the default name the constant rather
    # than repeating a token, so the default has exactly one definition.
    source = inspect.getsource(app)
    assert 'getattr(state, "volume_clim_mode", VOLUME_CLIM_DEFAULT)' in source, (
        "the volume layer no longer falls back to VOLUME_CLIM_DEFAULT: a page "
        "whose state has no clim mode would draw some other window"
    )
    assert 'v_model=("volume_clim_mode", VOLUME_CLIM_DEFAULT)' in source, (
        "the Color Scale select no longer opens on VOLUME_CLIM_DEFAULT"
    )
    for wrong in (
        'getattr(state, "volume_clim_mode", VOLUME_CLIM_PER_FRAME)',
        'v_model=("volume_clim_mode", VOLUME_CLIM_PER_FRAME)',
    ):
        assert wrong not in source, (
            f"the default window is the renormalising one: {wrong!r} would make "
            "a page that says nothing paint the decay away"
        )


def test_the_bar_title_states_the_window_for_both_ramps():
    """The exact four titles the |E| bar can carry, log and linear."""
    assert app._volume_bar_title(app.VOLUME_CLIM_GLOBAL) == (
        "|E| (Log) - Global (Comparable)"
    ), app._volume_bar_title(app.VOLUME_CLIM_GLOBAL)
    assert app._volume_bar_title(app.VOLUME_CLIM_PER_FRAME) == (
        "|E| (Log) - Per-Frame (Max Contrast)"
    ), app._volume_bar_title(app.VOLUME_CLIM_PER_FRAME)
    assert app._volume_bar_title(app.VOLUME_CLIM_GLOBAL, log_scale=False) == (
        "|E| (Linear) - Global (Comparable)"
    )
    assert app._volume_bar_title(app.VOLUME_CLIM_PER_FRAME, log_scale=False) == (
        "|E| (Linear) - Per-Frame (Max Contrast)"
    )
    # The bare call is the default window's title, so a caller that passes no
    # mode cannot caption the bar with a window it did not draw.
    assert app._volume_bar_title() == app._volume_bar_title(app.VOLUME_CLIM_DEFAULT)


def test_the_global_window_is_one_range_for_every_frame_and_unchanged(real_info):
    """Frame-invariant, and the same tuple the layer drew before the mode existed."""
    volume = real_info["e_abs_volume"]
    frames = int(volume.shape[0])
    assert frames > 1, f"a {frames}-frame volume cannot show frame-invariance"
    whole = app._volume_abs_global_clim(volume)
    assert whole is not None, (
        "the reference volume measures no whole-recording range, so the layer "
        "would draw no |E| volume at all"
    )
    low, high = (float(value) for value in whole)
    assert math.isfinite(low) and math.isfinite(high), whole
    assert 0.0 < low < high, (
        f"the global range is {whole!r}: it must be finite with low < high or "
        "VTK is left guessing a clim"
    )
    for frame in range(frames):
        drawn = app._volume_clim_for(volume, frame, app.VOLUME_CLIM_GLOBAL)
        # EXACT equality, not pytest.approx: "no visual change" means the same
        # numbers reach the mapper, not numbers close enough to look alike.
        assert drawn == whole, (
            f"the global window moved on frame {frame}: {drawn!r} against the "
            f"whole-recording {whole!r} - the global window is ONE reference for "
            "the entire recording, and it is the one the layer already used"
        )
    # The 60 dB span the layer has always taken: a decibel span, not a guess.
    assert high / low == pytest.approx(1e3, rel=1e-12), (
        f"the global window spans {high / low:.6g}x, not 1e3 (60 dB)"
    )


def test_the_per_frame_window_follows_the_frame_it_is_drawn_on(real_info):
    """Not frame-invariant: it is referenced to each frame's own peak."""
    volume = real_info["e_abs_volume"]
    frames = int(volume.shape[0])
    drawn = [
        app._volume_clim_for(volume, frame, app.VOLUME_CLIM_PER_FRAME)
        for frame in range(frames)
    ]
    for frame, clim in enumerate(drawn):
        assert clim is not None, (
            f"frame {frame} of the reference volume yielded no per-frame range"
        )
        low, high = (float(value) for value in clim)
        assert math.isfinite(low) and math.isfinite(high), (frame, clim)
        assert 0.0 < low < high, (frame, clim)
    assert len(set(drawn)) > 1, (
        "every frame came back on the same range: 'Per-Frame (Max Contrast)' "
        "would be a label on the global window, i.e. a control that does nothing"
    )
    whole = app._volume_abs_global_clim(volume)
    assert drawn[0] != whole, (
        f"the quiet first frame is drawn on the recording's own window {whole!r}: "
        "the per-frame mode is not re-referencing anything"
    )
    # No frame may claim MORE amplitude than the recording holds: a per-frame
    # ceiling above the global one would be a peak this recording does not have.
    assert max(float(high) for _, high in drawn) <= float(whole[1]), (
        "a per-frame window outgrew the whole-recording one"
    )


def test_the_warning_agrees_with_the_per_frame_mode_and_never_with_global():
    """The sentence names the option it belongs to and is silent about nothing."""
    warning = app._volume_clim_warning(app.VOLUME_CLIM_PER_FRAME)
    assert warning == app.VOLUME_CLIM_PER_FRAME_WARNING, warning
    assert app.VOLUME_CLIM_TITLES[app.VOLUME_CLIM_PER_FRAME] in warning, (
        f"the warning does not name the option the reader picked: {warning!r}"
    )
    assert app.VOLUME_CLIM_TITLES[app.VOLUME_CLIM_GLOBAL] not in warning, (
        f"the warning names the COMPARABLE window it is warning against: "
        f"{warning!r}"
    )
    assert "not visible" in warning, (
        f"the warning says something is lost without saying what: {warning!r}"
    )
    for quiet in (app.VOLUME_CLIM_GLOBAL, None, "", "global", 0, "nonsense"):
        assert app._volume_clim_warning(quiet) == "", (
            f"{quiet!r} carries a per-frame warning while the page draws the "
            "global window"
        )
        assert not bool(app._volume_clim_warning(quiet)), quiet



# ---------------------------------------------------------------------------
# PLAY SPEED: how many positions one tick advances, and the caption that prices
# it. Still pure - the loop's arithmetic is three functions of (a time, a
# position, a rate and an fps) plus one memo - so nothing here boots the server,
# builds a layout or touches the plotter. The REJECTED alternative (advance a
# fixed number of positions per tick and let the box decide the speed) has no
# such representation to assert: it makes the sweep time a property of the
# machine, which is exactly what the clock reading below replaced.
# ---------------------------------------------------------------------------


def test_the_play_clock_reads_a_position_off_the_wall_time():
    """One second at 4 positions/tick and 24 fps is 96 positions, and only up.

    ``_play_target`` is the whole play loop's arithmetic: ``anchor_frame`` was on
    screen at ``anchor_time``, so the position at ``now`` is that frame plus the
    elapsed time times ``rate * fps``. The REJECTED alternative is the old
    advance-per-tick rule (add ``rate`` to the position each tick), which is
    simpler to write and makes the playback speed a property of the box: a busy
    machine plays slower, a fast one strobes, and the caption's "s per sweep"
    stops predicting anything. So what is asserted is that the target is monotone
    in the clock and that a second of wall time is exactly the arithmetic the
    caption quotes.
    """
    rate, fps = app.DEFAULT_PLAY_RATE, 24
    targets = [
        app._play_target(0.0, 0, now, rate, fps)
        for now in (0.0, 0.01, 0.02, 0.1, 0.25, 0.5, 1.0, 2.0)
    ]
    assert targets == sorted(targets), (
        f"the position went backwards while the clock only ran forward: {targets}"
    )
    assert app._play_target(0.0, 0, 1.0, rate, fps) == rate * fps, (
        f"one second at {rate} positions/tick and {fps} fps advanced "
        f"{app._play_target(0.0, 0, 1.0, rate, fps)} positions, not {rate * fps}"
    )
    assert app._play_target(100.0, 7, 101.0, rate, fps) == 7 + rate * fps, (
        "the advance is not measured FROM THE ANCHOR: an anchor of 7 at t=100 s "
        f"reached {app._play_target(100.0, 7, 101.0, rate, fps)} at t=101 s, not "
        f"{7 + rate * fps}"
    )


def test_a_late_tick_advances_further_instead_of_stalling():
    """A tick the box drew slowly loses POSITIONS, never time.

    Two readings of one second, anchored where the loop's previous draw landed,
    must add up to the same second read in one go - that is what makes the
    animation lose positions on a busy machine instead of running slow. The
    REJECTED alternative (per-tick advance) has no such identity: ten late ticks
    take ten times as long as ten on-time ones.
    """
    rate, fps = app.DEFAULT_PLAY_RATE, 24
    whole = app._play_target(0.0, 0, 1.0, rate, fps)
    first = app._play_target(0.0, 0, 0.5, rate, fps)
    second = app._play_target(0.5, 0, 1.0, rate, fps)
    assert first == rate * fps // 2, (
        f"half a second advanced {first} positions, not {rate * fps // 2}"
    )
    assert first < whole, (
        f"half a second ({first}) and a whole second ({whole}) advanced the same "
        "distance: the position is not being read off the clock"
    )
    assert first + second == whole, (
        f"{first} + {second} positions over the two halves of one second, but "
        f"{whole} for the whole second: the loop's speed depends on when its "
        "ticks happened to arrive"
    )


def test_a_rate_or_an_fps_of_zero_still_advances_one_position_a_tick():
    """A missing rate is the SLOWEST speed, never a division by zero or a rewind.

    ``rate`` and ``fps`` are floored at 1: a page built before the select
    existed, or a select that never reached the widget table, hands over a zero.
    The REJECTED alternative is to let the arithmetic speak for itself - a zero
    factor freezes the player, and a negative one (an unvalidated value from a
    URL) runs it backwards while the caption still claims a forward sweep.
    """
    for bad_rate in (0, -4):
        assert app._play_target(0.0, 10, 1.0, bad_rate, 1) == 11, bad_rate
    for bad_fps in (0, -24):
        assert app._play_target(0.0, 10, 1.0, 1, bad_fps) == 11, bad_fps
    assert app._play_target(0.0, 10, 1.0, 0, 0) == 11, "both factors floored"


def test_a_clock_read_before_its_anchor_never_goes_negative():
    """An index cannot be -9, but it CAN be past the end: the caller wraps it.

    The clamp at 0 is not a second, softer clamp at the family length: whether
    the player loops or stops is a property of the dump, not of time, so a
    position past the last frame is answered and left to the caller's wrap.
    """
    assert app._play_target(5.0, 3, 1.0, 4, 24) == 0, (
        "a clock read before its anchor produced a negative index"
    )
    assert app._play_target(0.0, 0, 100.0, 4, 24) == 9600, (
        "the target was clamped at the family length: the caller wraps it, and a "
        "clamp here would silently stop the player short"
    )


def test_the_loop_keeps_its_origin_when_nothing_moved():
    """The common tick is a no-op: the anchor is returned untouched.

    ``current_frame`` equal to ``drawn_frame`` means the loop's own draw is the
    only thing that moved the position, so re-anchoring there would restart the
    clock every tick and turn the rate into an upper bound.
    """
    for current in (40, 41, 0):
        assert app._play_reanchor(12.5, 40, 13.0, current, current) == (12.5, 40), (
            f"a tick with current == drawn == {current} moved the origin"
        )


def test_a_seek_becomes_the_new_origin_of_the_play_clock():
    """A scrubber moved while playing is RESPECTED, not overwritten next tick.

    ``current_frame`` differing from what the loop last drew means somebody else
    moved the player, so that position becomes the origin AT THE CURRENT TIME -
    and the very next target, read at the same instant, is the seek itself rather
    than the position the old clock had reached. The REJECTED alternatives are to
    lock the player while it plays (a dead slider) or to reuse
    ``suppress_frame_listener`` for user seeks (silencing a real operator action
    for a whole tick; that flag exists to hide the loop's own re-entry).
    """
    anchor_time, anchor_frame = app._play_reanchor(12.5, 40, 13.0, 900, 40)
    assert (anchor_time, anchor_frame) == (13.0, 900), (
        f"a seek to 900 at t=13 s left the origin at {(anchor_time, anchor_frame)}"
    )
    assert app._play_target(anchor_time, anchor_frame, 13.0, 4, 24) == 900, (
        "the next target after a seek is not the sought position: the clock "
        "drags the player back to where nobody asked for it"
    )


def test_the_caption_prices_one_sweep_in_the_arithmetic_the_loop_integrates():
    """The sentence beside the select IS the quantity ``_play_target`` integrates.

    ``frames / (rate * fps)`` is both the sweep time the caption prints and the
    wall time the clock needs to cross the whole family, so the two cannot drift
    apart. The REJECTED alternative is to caption the caption - state the rate
    and leave the duration implicit - and then nothing on the page says what the
    choice costs, which is the thing an operator changing it is deciding.
    """
    assert app._play_caption(2400, 4, 24) == (
        "4 steps/tick at 24 fps - 25.0 s per sweep"
    ), app._play_caption(2400, 4, 24)
    for frames, rate, fps in ((240, 4, 24), (2400, 1, 24), (2400, 8, 24)):
        sweep_s = frames / (rate * fps)
        caption = app._play_caption(frames, rate, fps)
        assert caption.endswith(f"- {sweep_s:.1f} s per sweep"), caption
        assert app._play_target(0.0, 0, sweep_s, rate, fps) == frames, (
            f"the caption quotes {sweep_s:.1f} s per sweep, but the clock needs "
            f"{app._play_target(0.0, 0, sweep_s, rate, fps) / (rate * fps):.3f} s "
            f"to cross {frames} positions at {rate}/{fps}"
        )


def test_a_page_with_no_timeline_gets_a_word_not_a_division():
    """No frames is a WORD, and a zero rate/fps is floored rather than divided by.

    The REJECTED alternative is to divide anyway: zero frames raises
    ZeroDivisionError inside a layout builder and takes the whole column down,
    and a non-zero denominator over no frames prints a confident "0.0 s per
    sweep" for a page that has nothing to sweep - the same invented-answer
    dishonesty the timeline labels refuse.
    """
    for frames in (None, 0, -5):
        assert app._play_caption(frames, 4, 24) == "no timeline", frames
    assert app._play_caption(24, 0, 0) == app._play_caption(24, 1, 1), (
        "a zero rate/fps was divided by instead of floored at 1"
    )
    assert app._play_caption(24, 0, 0).endswith("- 24.0 s per sweep"), (
        app._play_caption(24, 0, 0)
    )


def test_the_select_value_snaps_to_the_nearest_offered_rate():
    """Nearest wins, ties go to the SLOWER rate, junk falls back on the default.

    The speed arrives from a select, a URL or a script that set it to whatever it
    liked, so it is never trusted to be one of ``PLAY_RATES``. The REJECTED
    alternative is default-on-anything-unrecognised: the number on screen and the
    number the loop uses would then disagree for the rest of the session, and the
    caption would be the only witness. Ties go slower because a strobe is
    unreadable and the operator asking for exactly a half-way speed has no
    preference this can violate.
    """
    assert app.DEFAULT_PLAY_RATE in app.PLAY_RATES, (
        f"the page opens on {app.DEFAULT_PLAY_RATE}, which the select does not "
        f"offer ({app.PLAY_RATES}): it could never be put back"
    )
    for value, expected in ((1, 1), (4, 4), (7, 8), (5, 4), (0, 1), (2.6, 2)):
        assert app._play_rate_near(value) == expected, (
            f"{value} snapped to {app._play_rate_near(value)}, not to the nearest "
            f"offered rate {expected}"
        )
    for tie, slower in ((3, 2), (6, 4)):
        assert app._play_rate_near(tie) == slower, (
            f"the tie at {tie} went to {app._play_rate_near(tie)}, not to the "
            f"slower rate {slower}: a tie must never go to the strobe"
        )
    for junk in (None, "4", True, False, object(), [4]):
        assert app._play_rate_near(junk) == app.DEFAULT_PLAY_RATE, junk
    for value in range(-5, 20):
        assert app._play_rate_near(value) in app.PLAY_RATES, value


#: A tiny record the plan can be built from: two captures over four plane
#: frames, so the mapping has a real shape without needing a file on disk.
def _plan_info(steps=(1, 5, 9, 13)):
    steps = np.asarray(steps, dtype=int)
    return {
        "e_abs_volume": np.zeros((steps.size, 2, 2), dtype=np.float32),
        "e_abs_volume_step_index": steps,
        "frame_index": steps,
        "frame_index_xcut": steps,
    }


def test_the_player_plan_is_memoised_per_record_and_mode():
    """Same record and mode ⇒ the SAME plan object; another record ⇒ its own.

    The plan is two 2400-entry ``searchsorted`` passes and a
    ``maximum.accumulate`` for a picture that cannot have changed between ticks,
    so it is memoised - and the identity is what is asserted, because an
    equal-valued SECOND object would mean the memo is doing no work at all. The
    REJECTED alternative is to cache on the info dict's *contents*: it is a dict
    of numpy arrays, so a content key costs a hashing pass over every frame -
    more than the plan it saves.
    """
    app._VOLUME_PLAN_CACHE.clear()
    info = _plan_info()
    first = app._volume_player_plan(info, "ycut")
    assert first is not None, "the tiny record carries a volume and two axes"
    again = app._volume_player_plan(info, "ycut")
    assert again is first, (
        "the same record asked twice returned two plan objects: every tick "
        "rebuilds the mapping the memo exists to avoid"
    )
    assert again == first, "the memoised plan is not even equal to the first one"
    other_mode = app._volume_player_plan(info, "xcut")
    assert other_mode == first, "the two modes disagree on an identical record"
    assert other_mode is not first, (
        "the MODE is not part of the memo key: one family's plan is being served "
        "for the other"
    )


def test_the_plan_cache_never_serves_a_plan_built_for_another_record():
    """A new dict is never handed the old record's plan, however equal it looks.

    The entry is filed under ``id(info)`` and holds ``info`` itself, so the id
    cannot be recycled while the entry lives, and the ``is`` check on lookup
    rejects an entry that no longer belongs to the dict asked about. The REJECTED
    alternative - filing under the id alone, holding no reference - lets a freed
    record's id be reused by a dump with different arrays and serves the old
    mapping for the new axes: a picture taken from another recording, with no
    error anywhere.
    """
    app._VOLUME_PLAN_CACHE.clear()
    info = _plan_info()
    stale = app._volume_player_plan(info, "ycut")
    assert stale is not None
    del info
    gc.collect()
    fresh = _plan_info()
    served = app._volume_player_plan(fresh, "ycut")
    assert served == stale, (
        "an equal-valued record got a different plan: the mapping depends on "
        "something other than the record"
    )
    assert served is not stale, (
        "a fresh record was served the plan built for a deleted one: the memo is "
        "keyed on an id it does not hold the object for"
    )


def _play_loop_node():
    """The ``_play_loop`` coroutine as AST, found inside ``run_web_vis``.

    It is a CLOSURE, not a module attribute, so ``app._play_loop`` does not
    exist and ``inspect.getsource`` cannot be pointed at it directly: the node
    has to be found inside the function that defines it. Nothing here executes
    the loop - the source is what is being read.
    """
    tree = ast.parse(inspect.getsource(app))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_web_vis":
            for child in ast.walk(node):
                if isinstance(child, ast.AsyncFunctionDef) and child.name == "_play_loop":
                    return child
    return None


def test_the_play_loop_advances_by_the_pump_and_never_by_a_wall_clock_target():
    """One draw per tick, and the position comes from the pump's stride, not a clock.

    Read off the SHIPPED source rather than a re-implementation: ``_show`` writes
    ``state.frame``, which fires the frame listener on the flush, so a loop that
    reached ``_show`` twice per tick would draw the same position twice and lose
    the operand of the whole speed control. The REJECTED alternative that this
    guards against is the removed ``PLAY_STEPS_PER_TICK`` counter - a constant
    compiled into the loop, which no select can change and no caption can price -
    so its absence from the module is asserted too, not just its absence here.
    """
    source = inspect.getsource(app)
    assert "PLAY_STEPS_PER_TICK" not in source, (
        "the old per-tick counter is still in the module: the speed is a UI value "
        "now, and a constant beside it would be a second, contradictory answer"
    )
    loop = _play_loop_node()
    assert loop is not None, (
        "no async _play_loop inside run_web_vis: the player's advance cannot be "
        "read, so nothing below is a statement about the shipped loop"
    )
    draws = [
        node
        for node in ast.walk(loop)
        if isinstance(node, ast.Name) and node.id == "_show"
    ]
    assert len(draws) == 1, (
        f"the play loop references _show {len(draws)} times per tick: each call "
        "writes state.frame and draws, so more than one draws the same position "
        "twice"
    )
    # THE DRAW IS *NOT* HANDED TO A WORKER THREAD, AND THIS PINS THAT. The GL
    # context belongs to the thread that created it: handing _show to
    # asyncio.to_thread aborted the process inside X_GLXMakeCurrent with "X
    # Error: BadAccess" - no traceback, no exception, the viewer vanished.
    off_thread = [
        node
        for node in ast.walk(loop)
        if (
            isinstance(node, ast.Name)
            and node.id in {"to_thread", "run_in_executor", "Thread", "threading"}
        )
        or (
            isinstance(node, ast.Attribute)
            and node.attr in {"to_thread", "run_in_executor", "Thread"}
        )
        or (
            isinstance(node, ast.Import)
            and any(alias.name == "threading" for alias in node.names)
        )
        or (isinstance(node, ast.ImportFrom) and node.module == "threading")
    ]
    assert not off_thread, (
        "the play loop hands its draw to a worker thread again: the GL context "
        "is made on the event-loop thread, and rendering it off that thread "
        "kills the process inside X_GLXMakeCurrent ('X Error: BadAccess'), with "
        "no traceback to explain the vanishing viewer"
    )
    # ... AND THE TICK STILL YIELDS. The draw is synchronous now, so a tick whose
    # deadline already passed owns no sleep of its own: without an unconditional
    # sleep(0) the loop iterates without ever suspending, starves the websocket
    # and freezes the picture while the position keeps advancing.
    tick_loops = [node for node in ast.walk(loop) if isinstance(node, ast.While)]
    assert len(tick_loops) == 1, (
        f"the play loop has {len(tick_loops)} while loops, not one: the body "
        "read below cannot be identified as the loop that advances the frame"
    )
    tick_awaits = [
        node
        for statement in tick_loops[0].body
        for node in ast.walk(statement)
        if isinstance(node, ast.Await)
    ]
    assert tick_awaits, (
        "the tick body has no await at all: a late tick (its deadline already "
        "passed) takes no sleep, so a synchronous draw lets the loop iterate "
        "without ever suspending - the websocket starves and the viewer freezes "
        "while the picture keeps moving"
    )
    called = {
        node.func.id
        for node in ast.walk(loop)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    for helper in (
        "_play_advance",
        "_play_stride",
        "_play_reanchor",
        "_play_rate_near",
        # The delivery gate: a position advanced while trame is animating its
        # own views is a still trame discards, so the loop must ASK.
        "_delivery_animating",
    ):
        assert helper in called, (
            f"the loop does not call {helper}: the position on screen is not the "
            "one the pump chose from the selected rate"
        )
    assert "_play_target" not in called, (
        "the loop still integrates a wall-clock target: a tick that paints "
        "nothing must advance nothing, or the sequence on screen is not the one "
        "the caption describes"
    )



def test_a_page_with_no_timeline_still_hands_the_loop_a_frame_count():
    """None is "no timeline", not a crash: the loop divides by this count.

    ``nt``/``nt_x`` are None on a page that claims no timeline, and the shipped
    loop called ``int(None)`` inside a task nobody awaits - the TypeError was
    collected at GC, so the page stayed ``playing`` with nothing advancing.
    """
    assert app._play_frames(None) == 1
    assert app._play_frames(0) == 1
    assert app._play_frames(-5) == 1
    assert app._play_frames("junk") == 1
    assert app._play_frames(2400) == 2400


def test_the_speed_select_offers_titled_objects_not_bare_numbers():
    """Every offered rate, with the wording beside the value it selects.

    Bare numbers left the rows showing garbage ("st 1", "st 2", "8"): the row
    text of a Vuetify select comes from ``item.title``, which a number has not.
    """
    items = app._play_rate_items(app.PLAY_RATES)
    assert [item["title"] for item in items] == [
        "1 step/tick", "2 steps/tick", "4 steps/tick", "8 steps/tick",
    ], items
    assert [item["value"] for item in items] == [1, 2, 4, 8], items
    assert all(isinstance(item["value"], int) for item in items), items


# ---------------------------------------------------------------------------
# ONE indicator, checked in the SOURCE.  Every test above reads the sentence
# itself, so none of them can see a SECOND sentence being drawn beside it: a
# plotter-drawn counter or a second writable state field would satisfy all of
# them and still put two different step numbers on the page.
# ---------------------------------------------------------------------------


def test_the_page_carries_exactly_one_step_indicator():
    """One sentence per page, composed in one place, bound in one place.

    A STRUCTURAL claim, made on the source rather than on a render: the defect
    it guards against is a duplicate indicator, and a duplicate draws perfectly.
    No unrelated mechanism can satisfy it, because each assertion names the ONE
    artefact it counts - the identifiers, the assignment, the template binding:

    * no ``step_counter``/``step_text`` identifier survives in
      ``server/poc_app.py``: the plotter-drawn counter and the state field that
      carried it are gone, not merely unused.  (``time.perf_counter`` and the
      profile's own counters are untouched by this - the names below are the
      step indicator's, not every name holding the word "counter".)
    * exactly ONE assignment in the whole module writes ``state.frame_label``,
      and its line is reported: a second writer could disagree with the player.
    * exactly ONE template binding prints it, and it is in
      ``server/um3k_panels.py``; ``server/poc_app.py`` binds it nowhere.
    """
    source_path = REPO_ROOT / "server" / "poc_app.py"
    panels_path = REPO_ROOT / "server" / "um3k_panels.py"
    source = source_path.read_text(encoding="utf-8")
    panels = panels_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    #: Identifiers only - never comments or docstrings, which describe
    #: mechanisms without being one.
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    for gone in ("step_counter", "step_text"):
        survivors = sorted(name for name in names if gone in name)
        assert not survivors, (
            f"{survivors} still name a SECOND step indicator in "
            f"{source_path.name}: the label is the page's only one, and a "
            "plotter-drawn counter or a second state field would print a step "
            "number nobody reconciles with it"
        )

    writers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute) and target.attr == "frame_label"
            for target in node.targets
        )
    ]
    assert len(writers) == 1, (
        f"{len(writers)} assignments write state.frame_label "
        f"(lines {[node.lineno for node in writers]}): the page would carry two "
        "step indicators, and the second is free to disagree with the sentence "
        "every test in this file pins"
    )

    bound = panels.count("{{ frame_label }}")
    assert bound == 1, (
        f"{panels_path.name} binds the step sentence {bound} times, not once: a "
        "second binding is a second indicator on the same page"
    )
    assert source.count("{{ frame_label }}") == 0, (
        f"{source_path.name} binds the step sentence too: the layout module is "
        "the only place a page reads it"
    )
