"""The page's clock: sample-and-hold, one position count, and the legacy plan.

The contract these tests pin is the one the viewer reads the picture with, so
each case names the defect it forbids rather than only the value it expects.
The last group reads the SHIPPED archive byte for byte, because the numbers that
matter - 2400 steps, 24 volume captures 100 apart - are properties of a real
recording and a synthetic one cannot lie about them in the same way.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from server.timeline import (
    VOLUME_LAYER,
    XCUT_LAYER,
    YCUT_LAYER,
    Frame,
    Layer,
    Timeline,
    _monotonic,
)

ARCHIVE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "artifacts",
    "reference_sim_volume.npz",
)


def _volume_layer() -> Layer:
    return Layer(name=VOLUME_LAYER, steps=(1, 101, 201))


def _timeline(steps=(1, 2, 3), layers=None, dt_s=None, t_ns=None) -> Timeline:
    return Timeline(
        nsteps=len(steps),
        steps=tuple(steps),
        dt_s=dt_s,
        t_ns=t_ns,
        layers=dict(layers or {}),
    )


# --------------------------------------------------------------------------
# sample and hold
# --------------------------------------------------------------------------


def test_a_frame_is_held_from_its_capture_until_the_next_one():
    """No position may show a sample captured AFTER it: that is data from the future."""
    layer = _volume_layer()
    assert [layer.index_for(step) for step in (1, 50, 100)] == [0, 0, 0], (
        "a step before the second capture showed a later sample - the nearest "
        "capture policy is back, and the picture is drawing the future"
    )
    assert [layer.index_for(step) for step in (101, 150, 200)] == [1, 1, 1]
    assert [layer.index_for(step) for step in (201, 900)] == [2, 2], (
        "the last stored sample is not held to the end of the clock"
    )


def test_a_step_before_the_first_capture_clamps_to_the_first_sample():
    layer = Layer(name=VOLUME_LAYER, steps=(101, 201))
    assert layer.index_for(0) == 0
    assert layer.index_for(-40) == 0
    assert layer.index_for(1) == 0


def test_hold_never_indexes_off_the_end_of_the_array():
    layer = Layer(name=VOLUME_LAYER, steps=(1, 101, 201))
    assert layer.index_for(10**9) == layer.count - 1


# --------------------------------------------------------------------------
# decimation and spans
# --------------------------------------------------------------------------


def test_decimation_is_the_measured_cadence():
    assert _volume_layer().decimation == 100
    assert Layer(name=XCUT_LAYER, steps=(1, 11, 21)).decimation == 10
    assert Layer(name=YCUT_LAYER, steps=(1, 2, 3)).decimation == 1


def test_a_single_sample_layer_has_decimation_one():
    layer = Layer(name=VOLUME_LAYER, steps=(7,))
    assert layer.decimation == 1
    assert layer.label(0) == "Frame 1 of 1", (
        "a one-sample layer printed a decimation clause it cannot defend"
    )


def test_a_dropped_sample_does_not_restate_the_cadence():
    """The median, not the first difference: one gap must not rewrite the film."""
    layer = Layer(name=VOLUME_LAYER, steps=(1, 101, 201, 1001))
    assert layer.decimation == 100


def test_a_span_is_the_window_a_stored_frame_owns():
    layer = _volume_layer()
    assert layer.span(0) == (1, 100)
    assert layer.span(1) == (101, 200)
    assert layer.span(2) == (201, 300), (
        "the last frame has no successor to bound it and must own one decimation "
        "window rather than an invented infinity"
    )


# --------------------------------------------------------------------------
# label wording
# --------------------------------------------------------------------------


def test_the_label_keeps_the_shipped_wording():
    layer = _volume_layer()
    assert layer.label(1) == "Frame 2 of 3, Volume Decimated \u00d7100 @ step 101", (
        "the decimation clause drifted; dozens of references match it verbatim"
    )


def test_an_undecimated_layer_prints_no_decimation_clause():
    layer = Layer(name=YCUT_LAYER, steps=(1, 2, 3))
    assert layer.label(0) == "Frame 1 of 3"


def test_held_is_said_only_when_the_frame_is_held_past_its_capture():
    layer = _volume_layer()
    assert layer.label(1, 101) == layer.label(1), "not held at its own capture"
    assert layer.label(1, 150).endswith(" (held)")


# --------------------------------------------------------------------------
# the axis reader
# --------------------------------------------------------------------------


def test_an_unreadable_axis_is_none():
    assert _monotonic(None) is None
    assert _monotonic(()) is None
    assert _monotonic([], ) is None
    assert _monotonic((1, 2, 1)) is None, (
        "a backwards axis was accepted; it must be refused rather than sorted"
    )
    assert _monotonic(("a", "b")) is None
    assert _monotonic((1.0, float("nan"))) is None


def test_a_flat_axis_is_still_readable():
    """A restart can record the same step twice; that is not a broken order."""
    assert _monotonic((1, 1, 2)) == (1, 1, 2)
    assert _monotonic(np.asarray([1, 11, 21])) == (1, 11, 21)


# --------------------------------------------------------------------------
# no timeline
# --------------------------------------------------------------------------


def test_an_empty_info_has_no_timeline():
    assert Timeline.from_dump({}) is None, "an empty dump must be 'no timeline'"
    assert Timeline.from_dump({"nt": 0}) is None
    assert Timeline.from_dump({"nt": None}) is None


def test_a_dump_with_no_frame_axis_has_no_timeline():
    bare = {"ez_ycut": np.zeros((2, 2, 2)), "nstep": 0, "dt_s": 0.0}
    assert Timeline.from_dump(bare) is None, (
        "a bare field dump was given a clock it never recorded"
    )


def test_a_bare_frame_count_still_makes_an_axis():
    timeline = Timeline.from_dump({"nt": 4})
    assert timeline is not None
    assert timeline.nsteps == 4
    assert timeline.steps == (1, 2, 3, 4)
    assert timeline.dt_s is None, "an absent dt_s must not become a zero time base"


# --------------------------------------------------------------------------
# clamping and resolution
# --------------------------------------------------------------------------


def test_clamp_is_tolerant_and_never_leaves_the_axis():
    timeline = _timeline(steps=(1, 2, 3))
    assert timeline.clamp(-5) == 0
    assert timeline.clamp(None) == 0
    assert timeline.clamp("junk") == 0
    assert timeline.clamp(3.7) == 2
    assert timeline.clamp(99999) == 2
    assert timeline.last_index == 2


def test_resolve_names_the_step_and_every_layer():
    volume = _volume_layer()
    timeline = _timeline(
        steps=tuple(range(1, 251)),
        layers={VOLUME_LAYER: volume, YCUT_LAYER: Layer(YCUT_LAYER, tuple(range(1, 251)))},
        dt_s=1e-12,
    )
    frame = timeline.resolve(150)
    assert isinstance(frame, Frame)
    assert frame.position == 150
    assert frame.step == 151, "the step is the dump's own 1-based number"
    assert frame.layer_indices[VOLUME_LAYER] == 1
    assert frame.layer_indices[YCUT_LAYER] == 150
    assert abs(frame.t_s - 150 * 1e-12) < 1e-24
    assert frame.layer_changed[VOLUME_LAYER] is False, (
        "position 150 is not where the volume advances; a rebuild there would be "
        "paid for nothing"
    )
    assert timeline.resolve(100).layer_changed[VOLUME_LAYER] is True


def test_the_first_position_is_where_each_layer_first_appears():
    timeline = _timeline(steps=(1, 2, 3), layers={VOLUME_LAYER: _volume_layer()})
    assert timeline.resolve(0).layer_changed[VOLUME_LAYER] is True


def test_layer_index_and_layer_label_are_none_for_an_absent_layer():
    timeline = _timeline(steps=(1, 2, 3), layers={YCUT_LAYER: Layer(YCUT_LAYER, (1, 2, 3))})
    assert timeline.layer_index(VOLUME_LAYER, 0) is None
    assert timeline.layer_label(VOLUME_LAYER, 0) is None
    assert timeline.layer(VOLUME_LAYER) is None


# --------------------------------------------------------------------------
# the caption
# --------------------------------------------------------------------------


def test_the_caption_names_the_recorded_step_and_time():
    timeline = _timeline(steps=(1, 2, 3), dt_s=7.626299478123987e-13)
    caption = timeline.caption(1)
    assert "step 2 / 3" in caption, f"the caption lost its step reading: {caption}"
    assert "ns" in caption, f"the caption lost its time reading: {caption}"


def test_the_caption_says_so_when_no_time_was_recorded():
    timeline = _timeline(steps=(1, 2, 3))
    caption = timeline.caption(0)
    assert "not recorded" in caption, (
        f"an absent time base was printed as a number: {caption}"
    )
    assert "step 1 / 3" in caption


def test_the_dumped_time_array_wins_over_dt_s():
    timeline = _timeline(steps=(1, 2, 3), dt_s=1.0, t_ns=(0.0, 5.0, 9.0))
    assert abs(timeline.resolve(2).t_ns - 9.0) < 1e-12


# --------------------------------------------------------------------------
# the legacy plan: one clock whatever the plane
# --------------------------------------------------------------------------


def test_the_plan_carries_exactly_the_legacy_keys():
    timeline = _timeline(
        steps=tuple(range(1, 251)),
        layers={VOLUME_LAYER: _volume_layer()},
    )
    plan = timeline.plan("ycut")
    assert set(plan) == {"steps", "frames", "plane", "volume"}
    assert plan["frames"] == 250
    assert plan["steps"] == tuple(range(1, 251))
    assert plan["plane"] == tuple(range(250))
    assert plan["volume"][:101] == (0,) * 100 + (1,), (
        "the plan is not sample-and-hold: position 100 is step 101, the second "
        "capture, so only the first hundred positions may show frame 20"
    )
    assert plan["volume"][101] == 1, (
        "position 101 is step 102, which the third capture has not replaced yet"
    )


def test_the_mode_arg_cannot_change_the_clock():
    """Switching plane used to change playback speed by ten; no argument may."""
    timeline = _timeline(
        steps=tuple(range(1, 251)),
        layers={VOLUME_LAYER: _volume_layer(), XCUT_LAYER: Layer(XCUT_LAYER, (1, 11, 21))},
    )
    assert timeline.plan("ycut") == timeline.plan("xcut"), (
        "the plan still depends on the plane on screen"
    )


def test_the_plan_is_none_without_a_volume():
    timeline = _timeline(steps=(1, 2, 3), layers={YCUT_LAYER: Layer(YCUT_LAYER, (1, 2, 3))})
    assert timeline.plan("ycut") is None


# --------------------------------------------------------------------------
# the shipped archive
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_info():
    if not os.path.exists(ARCHIVE):
        pytest.skip(f"the reference archive is not present at {ARCHIVE}")
    with np.load(ARCHIVE) as data:
        volume = np.asarray(data["e_abs_volume"])
        info = {
            "nt": int(data["nt"]),
            "nt_x": int(data["nt_x"]),
            "nstep": int(data["nsteps"]),
            "dt_s": float(data["dt_s"]),
            "t_ns": np.asarray(data["t_ns"], dtype=float),
            "frame_index": np.asarray(data["frame_index"], dtype=int),
            "frame_index_xcut": np.asarray(data["frame_index_xcut"], dtype=int),
            "e_abs_volume": volume,
            "e_abs_volume_step_index": np.asarray(
                data["e_abs_volume_step_index"], dtype=int
            ),
        }
    return info


def test_the_shipped_archive_pins_the_whole_contract(real_info):
    timeline = Timeline.from_dump(real_info)
    assert timeline is not None
    assert timeline.nsteps == 2400, (
        f"the master clock is {timeline.nsteps} steps, not the recording's 2400; "
        "a family's frame count is being used as the clock again"
    )
    volume = timeline.layer(VOLUME_LAYER)
    xcut = timeline.layer(XCUT_LAYER)
    assert volume.count == real_info["e_abs_volume"].shape[0] == 24
    assert volume.decimation == 100
    assert xcut.count == 240
    assert xcut.decimation == 10
    assert timeline.layer(YCUT_LAYER).decimation == 1
    assert [timeline.layer_index(VOLUME_LAYER, p) for p in (0, 50, 99, 100)] == [
        0,
        0,
        0,
        1,
    ], "the volume layer is not being held: position 50 showed step 101"
    assert timeline.layer_index(VOLUME_LAYER, 2399) == 23
    assert [timeline.layer_index(XCUT_LAYER, p) for p in (0, 9, 10, 2390)] == [
        0,
        0,
        1,
        239,
    ]
    caption = timeline.caption(1000)
    assert "step 1001" in caption and "ns" in caption, (
        f"the caption of position 1000 does not state the recorded step: {caption}"
    )
    label = timeline.layer_label(VOLUME_LAYER, 100)
    assert label.startswith("Frame 2 of 24, Volume Decimated \u00d7100 @ step 101"), label
