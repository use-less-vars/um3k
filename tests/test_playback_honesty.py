"""The player's label names the STEP it is showing, not the slider's position.

WHAT THIS PINS.  A dump may save its |E| volume on a COARSER grid than its
planes (``--volume-stride``), so on that page one slider click moves the solver
clock by N steps.  The label used to say "frame 4 / 24", which reads as if the
fourth click were step 4 of 24 - a timeline four times shorter than the run and
a step number nobody could recover from the picture.

The record that fixes it is the dump's own: ``e_abs_volume_step_index`` beside
``e_abs_volume_stride`` and the run's ``nsteps``.  ``TimeAxis`` is that record,
``build_time_axis`` is the ONE place the precedence between a recorded and a
derived axis is decided, and ``_frame_label`` prints it.  So the assertions
below are of two kinds:

    * on the SHIPPED reference volume, that the axis is the file's own step
      axis, that the label names the recorded step of the position drawn, and
      that the count it is out of is the count the scrubber can reach;
    * on constructed axes, the precedence and the absences - a page with no
      axis keeps the frame-only sentence byte for byte (the legacy two-argument
      call), and a time base is NEVER invented: no real ``dt_s``, no seconds.

Skips: only when the reference volume itself is absent.  Nothing here boots the
server, builds a layout or touches the plotter - the label is a pure function of
the dump, so this file needs no pyvista, no trame and no VTK.
"""

from __future__ import annotations

import dataclasses
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
    """The step axis, stride and run length exactly as the FILE states them."""
    with np.load(path) as data:
        return (
            np.asarray(data["e_abs_volume_step_index"], dtype=int),
            int(np.asarray(data["e_abs_volume_stride"]).ravel()[0]),
            int(np.asarray(data["nsteps"]).ravel()[0]),
        )


def test_the_loader_publishes_the_recorded_step_axis(real_info):
    """``info["time_axis"]`` IS the file's step axis, not a re-count of it."""
    recorded, stride, nsteps = _recorded(REFERENCE_NPZ)
    axis = real_info[app.TIME_AXIS_KEY]
    assert isinstance(axis, app.TimeAxis), (
        f"the loader published {type(axis).__name__}, not a TimeAxis: the label "
        "has nothing it can read a step from"
    )
    assert np.array_equal(axis.step_index, recorded), (
        f"the axis is {axis.step_index[:5]}..., the file records "
        f"{recorded[:5]}...: a derived axis is not this dump's record"
    )
    assert axis.stride == stride, (
        f"the axis says a frame spans {axis.stride} steps, the file says "
        f"{stride}: the decimation clause would misname the recording"
    )
    assert axis.n_steps == nsteps, (
        f"the denominator is {axis.n_steps}, the run recorded {nsteps} steps"
    )
    assert axis.n_frames == recorded.size


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
    nt_synced, _nt_x_synced = app._synced_frame_counts(
        real_info, real_info["nt"], real_info["nt_x"]
    )
    assert real_info["nt"] != nt_synced, (
        "this fixture no longer exercises the decimated case: the volume is not "
        "coarser than the planes"
    )
    assert app._frame_span_max(nt_synced, real_info["nt_x"], "ycut") == (
        axis.n_frames - 1
    ), "the scrubber's maximum is not the axis's last frame"


def test_the_label_names_the_step_the_picture_was_taken_at(real_info):
    """"Step 301 / 2400 (Frame 4 of 24, Volume Decimated ×100)", from the file."""
    axis = real_info[app.TIME_AXIS_KEY]
    frames = app._volume_player_plan(real_info, "ycut")["frames"]
    for index in (0, 3, frames - 1):
        step = int(axis.step_index[index])
        expected = (
            f"Step {step} / {axis.n_steps} "
            f"(Frame {index + 1} of {frames}, "
            f"Volume Decimated \u00d7{axis.stride})"
        )
        assert app._frame_label(index, frames, axis) == expected, (
            f"position {index} printed {app._frame_label(index, frames, axis)!r}, "
            f"not {expected!r}: the label is counting clicks, not steps"
        )
    # The one sentence the reference volume is here to pin: the 4th volume frame
    # is the capture taken at solver step 301, and the run was 2400 steps long.
    assert int(axis.step_index[3]) == 301
    assert app._frame_label(3, frames, axis).startswith("Step 301 / "), (
        "the 4th recorded volume frame is no longer step 301: "
        f"{app._frame_label(3, frames, axis)!r}"
    )


def test_a_page_with_no_axis_keeps_the_frame_only_sentence():
    """The legacy two-argument call is untouched: no axis, no new words."""
    assert app._frame_label(0, 3) == "frame 1 / 3"
    assert app._frame_label(2, 3) == "frame 3 / 3"
    assert app._frame_label(0, None) is None, (
        "None is 'no timeline', never 'frame 1 / None'"
    )
    assert app._frame_label(0, None, app.build_time_axis(n_frames=4)) is None


def test_a_zero_based_record_keeps_the_frame_only_sentence():
    """A base we would have to guess is not printed as a step number.

    A dump whose first capture sits at step 0 numbers its steps from a base it
    never states, so "Step 0 / 12" would put a zero-based numerator under a
    one-based denominator. The axis still answers ``frame_to_step``; only the
    sentence falls back, and it falls back to the frame-only one.
    """
    axis = app.build_time_axis(step_index=[0, 4, 8], n_steps=12, dt_s=1e-12)
    assert axis.n_steps == 12 and axis.frame_to_step(1) == 0
    assert app._frame_label(0, 3, axis) == "frame 1 / 3", (
        f"a zero-based record printed {app._frame_label(0, 3, axis)!r}"
    )


def test_an_axis_of_another_family_is_not_printed(real_info):
    """A 24-frame volume axis must not label a 240-position x-cut timeline."""
    axis = real_info[app.TIME_AXIS_KEY]
    other = int(real_info["nt_x"])
    assert other != axis.n_frames
    assert app._frame_label(0, other, axis) == f"frame 1 / {other}", (
        "the label read an axis describing a different family than the player "
        f"steps: {app._frame_label(0, other, axis)!r}"
    )


def test_one_step_per_frame_when_the_dump_records_no_stride():
    """An undecimated axis says so by OMITTING the clause, never '×1'."""
    axis = app.build_time_axis(
        step_index=np.arange(1, 2401), n_steps=2400, dt_s=1e-12, n_frames=2400
    )
    assert axis.stride == 1
    assert app._frame_label(300, 2400, axis) == (
        "Step 301 / 2400 (Frame 301 of 2400)"
    ), f"undecimated label: {app._frame_label(300, 2400, axis)!r}"


def test_frame_and_step_map_through_the_recorded_axis(real_info):
    """Both directions, and the off-axis answers are absent rather than 0."""
    axis = real_info[app.TIME_AXIS_KEY]
    assert axis.frame_to_step(4) == 301
    assert axis.step_to_frame(301) == 4
    assert axis.step_to_frame(300) == 3, (
        "a step between two captures must resolve to the EARLIER recorded frame: "
        f"{axis.step_to_frame(300)!r}"
    )
    assert axis.step_to_frame(0) is None
    assert axis.frame_to_step(0) is None
    assert axis.frame_to_step(axis.n_frames + 1) is None


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
    axis = real_info[app.TIME_AXIS_KEY]
    assert report.stride == 100, (
        f"the report names a x{report.stride} decimation, the file recorded 100"
    )
    assert report.frames == 24 == axis.n_frames, (
        f"the report describes {report.frames} frames, the axis {axis.n_frames}"
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
        "e_abs_volume_stride": 100,
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
