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


def test_a_stored_sample_owns_the_window_until_the_next_capture():
    """The hold is one fact about the recording, and :meth:`span` states it.

    A stored sample is HELD from its capture until the next one, which is why
    ``Layer.span`` exists and why this case reads the window instead of a suffix
    on the label: the label names the sample and the step it was captured at,
    and the sentence it completes already prints the player's step beside the
    capture's, so a per-position " (held)" said the same thing twice.
    """
    layer = _volume_layer()  # captures at 1, 101 and 201; decimation 100
    assert layer.span(1) == (101, 200), (
        "the sample captured at step 101 must own 101..(next capture - 1), not "
        "only the instant it was taken"
    )
    assert layer.span(0) == (1, 100), "the step-1 sample must own 1..100"
    assert layer.span(2) == (201, 300), (
        "the LAST sample has no successor to bound it; it must own exactly one "
        "decimation window rather than an invented infinity"
    )
    label = layer.label(1)
    assert label == "Frame 2 of 3, Volume Decimated \u00d7100 @ step 101", (
        f"the label drifted from the shipped wording: {label!r}"
    )
    assert "held" not in label.lower(), (
        f"the hold leaked back into the label ({label!r}); it is stated by "
        "span() alone"
    )



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
    assert "Step 2 / 3 (Stride 1)" in caption, (
        f"the caption lost its step reading, or left the stride unstated: {caption}"
    )
    assert "ns" in caption, f"the caption lost its time reading: {caption}"


def test_the_caption_says_so_when_no_time_was_recorded():
    timeline = _timeline(steps=(1, 2, 3))
    caption = timeline.caption(0)
    assert "not recorded" in caption, (
        f"an absent time base was printed as a number: {caption}"
    )
    assert "Step 1 / 3 (Stride 1)" in caption


# The reference archive's volume cadence: one capture every hundred solver
# steps, 1, 101, 201, ..., 2301 - 24 positions spanning 2301 steps.
DECIMATED_STEPS = tuple(range(1, 2400, 100))


def test_a_decimated_caption_ends_on_the_last_step_not_on_the_position_count():
    """The denominator is the last STEP, never the number of positions.

    The shipped caption was ``f"step {frame.step} / {self.nsteps}"``: a RECORDED
    step divided by a COUNT of positions, so this axis printed "step 2301 / 24" -
    a numerator larger than its own denominator, and a reading that names a
    denominator which cannot exist. Every position is checked, not only the last
    one, because the defect scales with the stride and the first frame is the one
    that made "1 / 24" look plausible.
    """
    steps = DECIMATED_STEPS
    assert len(steps) == 24 and steps[-1] == 2301, steps
    timeline = _timeline(steps=steps)
    assert timeline.caption(len(steps) - 1).startswith("Step 2301 / 2301 (Stride 100)"), (
        f"the last position does not name the step it ends on: "
        f"{timeline.caption(len(steps) - 1)}"
    )
    assert timeline.caption(0).startswith("Step 1 / 2301 (Stride 100)"), (
        f"the first position does not name its step and the whole axis: "
        f"{timeline.caption(0)}"
    )
    for position in range(len(steps)):
        caption = timeline.caption(position)
        assert "/ 24" not in caption, (
            f"position {position} divided a recorded step by the COUNT of "
            f"positions: {caption}"
        )
    legacy = f"step {int(steps[-1])} / {int(timeline.nsteps)} \u00b7 t = not recorded"
    assert legacy.startswith("step 2301 / 24"), legacy
    assert [p for p in range(len(steps)) if legacy == timeline.caption(p)] == [], (
        "the old expression is still what the decimated axis prints"
    )


@pytest.mark.parametrize(
    "steps",
    [
        tuple(range(1, 2401)),  # the plane family: one capture per solver step
        DECIMATED_STEPS,  # the volume cadence: one capture every hundred steps
        (1, 2, 3),  # a three-position record
    ],
)
def test_the_caption_speaks_the_viewers_step_sentence_byte_for_byte(steps):
    """One grammar, two modules: the caption may not paraphrase the page's label.

    ``poc_app.TimeAxis.label`` is the sentence the page draws and
    ``Timeline.caption`` is the same clock read from the other side of the port,
    so they are compared BYTE FOR BYTE against the axis built from the SAME
    fabricated record. The expected text is deliberately not written here: a
    hand-copied "Step 1 / 2301 (Stride 100)" would pin this test to whatever the
    author typed, and the two implementations could then drift together.
    """
    from server.poc_app import build_time_axis

    timeline = _timeline(steps=tuple(steps))
    axis = build_time_axis(step_index=np.asarray(steps, dtype=int), n_steps=len(steps))
    assert axis is not None, "the viewer got no axis for a record the timeline read"
    for position in range(len(steps)):
        drawn = axis.label(position + 1)
        assert drawn is not None, (
            f"the viewer refused a step reading the timeline states: {timeline.caption(position)}"
        )
        sentence = timeline.caption(position).split(f" \u00b7 ")[0]
        assert sentence == drawn, (
            f"position {position}: the caption says {sentence!r} and the page says "
            f"{drawn!r} - one clock, two grammars"
        )


def test_a_page_without_a_recorded_step_says_only_which_frame_it_is_on():
    """No step recorded means no step sentence - and no stride invented.

    ``poc_app._frame_label`` degrades to "Step {i} / {n}" for a page with no
    axis, and to the same sentence when the record's numbering cannot be
    defended; the caption degrades the same way and for the same two reasons.
    """
    zero_based = _timeline(steps=(0, 1, 2))
    empty = Timeline(nsteps=0, steps=())
    for timeline, position in ((zero_based, 2), (empty, 0)):
        caption = timeline.caption(position)
        assert "Stride" not in caption, (
            f"a record with no measurable stride printed one anyway: {caption}"
        )
        assert caption == f"Step {position + 1} / {int(timeline.nsteps)} \u00b7 t = not recorded", (
            f"the degraded sentence is not the viewer's frame-counted one: {caption}"
        )


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
    assert "Step 1001 / 2400 (Stride 1)" in caption and "ns" in caption, (
        f"the caption of position 1000 does not state the recorded step: {caption}"
    )
    label = timeline.layer_label(VOLUME_LAYER, 100)
    assert label.startswith("Frame 2 of 24, Volume Decimated \u00d7100 @ step 101"), label
