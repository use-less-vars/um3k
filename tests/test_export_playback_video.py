"""The exporter's step sentence, pinned without rendering a single frame.

``scripts/export_playback_video.py`` is not part of the app: it is a standalone
exporter whose only contract with the viewer is the LABEL it burns into every
frame, and it DELIBERATELY reproduces the viewer's wording instead of importing
``server/poc_app.py`` (that module builds a trame application on import). The
duplication is the reason this file exists - nothing else would notice the two
copies drifting apart, or the numerator/denominator guard being weakened.

No case here loads an ``artifacts/*.npz`` volume, starts ffmpeg or draws a
figure: every helper is fed plain arrays and strings, so a regression in the
wording, in the stride, in the denominator or in the guard fails in
milliseconds. The one structural case reads the script's own source with
``ast`` to prove the grammar stays importable without matplotlib.
"""

from __future__ import annotations

import ast
import pathlib
import re

import numpy as np
import pytest

from scripts.export_playback_video import (
    FRAME_FMT,
    STEP_FMT,
    axis_names,
    default_clim,
    frame_label,
    frame_text,
    max_step_of,
    measured_stride,
    plan_decimation,
    recorded_steps,
    step_label,
)

SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "scripts"
    / "export_playback_video.py"
)

#: The two forms the exporter may print, and nothing else: ``Step s / m
#: (Stride k)`` and the degraded ``Step i / n``.
LABEL_RE = re.compile(r"^Step (\d+) / (\d+)(?: \(Stride (\d+)\))?$")


def _steps(spacing: int, n_frames: int) -> np.ndarray:
    """A 1-based step axis of ``n_frames`` frames spaced ``spacing`` apart."""
    return np.arange(1, 1 + spacing * n_frames, spacing, dtype=np.int64)


# --- the two sentence forms ------------------------------------------------


def test_the_label_is_the_viewers_step_sentence():
    """``Step s / m (Stride k)`` - the wording the viewer's overlay prints."""
    assert step_label(41, 2401, 10) == "Step 41 / 2401 (Stride 10)"


def test_the_label_templates_are_the_viewers_templates():
    """The two format strings, byte for byte - this is what must not drift."""
    assert STEP_FMT == "Step {step} / {max_step} (Stride {stride})"
    assert FRAME_FMT == "Step {frame} / {n_frames}"


def test_the_stride_is_stated_even_when_it_is_one():
    """A silent stride is indistinguishable from an undecimated axis."""
    assert step_label(7, 120, 1) == "Step 7 / 120 (Stride 1)"


def test_the_label_takes_ints_from_whatever_numeric_it_is_handed():
    """numpy scalars arrive from the step vector, so they must not print as 41L."""
    assert step_label(np.int64(41), np.int64(2401), np.int64(10)) == (
        "Step 41 / 2401 (Stride 10)"
    )


def test_the_degraded_label_counts_positions_and_states_no_stride():
    """A record with no step axis gets a position count, never a stride."""
    text = frame_label(3, 60)
    assert text == "Step 3 / 60"
    assert "Stride" not in text


def test_a_record_with_no_step_axis_prints_the_degraded_label():
    """``frame_text`` degrades on ``steps is None`` - it invents no step."""
    assert frame_text(None, 0, None, None, 3, 60) == "Step 3 / 60"


def test_a_record_with_a_step_axis_prints_the_step_sentence():
    """The informative path: the numerator is the record's own step number."""
    steps = _steps(100, 25)
    max_step = max_step_of(steps)
    stride = measured_stride({}, steps)
    assert frame_text(steps, 5, max_step, stride, 6, 25) == "Step 501 / 2401 (Stride 100)"


# --- the denominator -------------------------------------------------------


def test_max_step_is_the_last_step_the_record_reaches():
    """``frame_index.max()`` - 2401, not the 25 frames it took to get there."""
    assert max_step_of(_steps(100, 25)) == 2401


def test_max_step_is_not_the_frame_count_and_not_the_count_minus_one():
    """The 2400/2399 defect: a COUNT is not the range the labels are printed in."""
    steps = _steps(100, 25)
    assert max_step_of(steps) != int(steps.size)
    assert max_step_of(steps) != int(steps.size) - 1


def test_a_record_without_a_step_axis_has_no_denominator():
    """No step axis means no denominator - not a made-up zero or one."""
    assert max_step_of(None) is None


# --- the guard: a numerator above its denominator is unrepresentable -------


def test_a_step_above_the_denominator_is_refused():
    """The historical frame: step 2400 printed over a denominator of 2399."""
    steps = np.array([1, 101, 2400], dtype=np.int64)
    with pytest.raises(ValueError, match="numerator exceeds its own denominator"):
        frame_text(steps, 2, 2399, 100, 3, 3)


def test_the_refusal_names_the_offending_frame_and_the_range_it_broke():
    """A forwarded file must fail with the numbers that explain it."""
    steps = np.array([1, 101, 2400], dtype=np.int64)
    with pytest.raises(
        ValueError, match=r"frame 3 of 3 records step 2400, outside 1\.\.2399"
    ):
        frame_text(steps, 2, 2399, 100, 3, 3)


def test_a_zero_step_is_refused_too():
    """A zero-based axis is out of range, not "one off" - it has no step axis."""
    steps = np.array([0, 1], dtype=np.int64)
    with pytest.raises(ValueError, match="outside 1..1"):
        frame_text(steps, 0, 1, 1, 1, 2)


def test_only_the_step_that_exceeds_the_denominator_is_refused():
    """The guard is per frame, exactly where the inconsistency would be printed."""
    steps = _steps(100, 25)
    max_step = max_step_of(steps) - 1
    for k in range(int(steps.size)):
        if k == int(steps.size) - 1:
            with pytest.raises(ValueError):
                frame_text(steps, k, max_step, 100, k + 1, 25)
        else:
            assert frame_text(steps, k, max_step, 100, k + 1, 25).startswith("Step ")


def test_no_label_ever_shows_a_numerator_above_its_denominator():
    """Property: for every axis the exporter can draw, s <= m and s >= 1."""
    checked = 0
    for spacing in (1, 2, 10, 100):
        for n_frames in (1, 2, 3, 24, 25, 60):
            steps = _steps(spacing, n_frames)
            assert int(steps.size) == n_frames
            max_step = max_step_of(steps)
            stride = measured_stride({}, steps)
            for k in range(n_frames):
                text = frame_text(steps, k, max_step, stride, k + 1, n_frames)
                match = LABEL_RE.match(text)
                assert match, f"{text!r} is not the exporter's step sentence"
                step, denominator = int(match.group(1)), int(match.group(2))
                assert 1 <= step <= denominator, (
                    f"{text!r} prints step {step} over {denominator}: a numerator "
                    "above its own denominator"
                )
                assert int(match.group(3)) == stride
                checked += 1
    assert checked == (1 + 2 + 3 + 24 + 25 + 60) * 4


# --- the stride ------------------------------------------------------------


def test_the_stride_is_the_even_spacing_of_the_drawn_axis():
    """An evenly spaced axis states its own spacing - 100 here, not the scalar."""
    assert measured_stride({}, _steps(100, 25)) == 100


def test_the_drawn_spacing_wins_over_the_dumps_stated_scalar():
    """volume_s59.npz: frame_index spaced 1, frame_index_xcut spaced 10."""
    assert measured_stride({"dump_stride": np.int64(1)}, _steps(10, 24)) == 10


def test_an_irregular_axis_falls_back_to_the_stated_stride():
    """No even spacing to measure, so the record's own scalar is quoted."""
    assert measured_stride({"dump_stride": np.int64(10)}, np.array([1, 2, 5])) == 10


def test_a_record_that_states_no_stride_is_one_step_per_frame():
    """Neither a spacing nor a scalar: the conservative reading is 1."""
    assert measured_stride({}, np.array([1, 2, 5])) == 1
    assert measured_stride({}, np.array([1])) == 1


def test_a_backwards_axis_is_not_read_as_an_even_spacing():
    """A decreasing axis measures -2 and must not be printed as a stride."""
    assert measured_stride({}, np.array([5, 3, 1])) == 1


# --- which vector is the step axis ----------------------------------------


def test_a_frame_index_of_the_recorded_length_is_the_step_axis():
    """The dump's own 1-based map, returned as integers."""
    steps = recorded_steps({"frame_index": np.array([1, 101, 201])}, 3)
    assert steps is not None
    assert list(steps) == [1, 101, 201]


def test_a_zero_based_frame_index_states_no_step_axis():
    """Numbering frames from 0 is a position count, not a step number."""
    assert recorded_steps({"frame_index": np.array([0, 100, 200])}, 3) is None


def test_a_frame_index_of_the_wrong_length_is_not_used():
    """A vector for another array's frame axis is not padded or truncated."""
    assert recorded_steps({"frame_index": np.array([1, 2])}, 3) is None


def test_the_cut_plane_axis_answers_when_the_volume_axis_is_absent():
    """``frame_index_xcut`` is the same record for the cut-plane arrays."""
    steps = recorded_steps({"frame_index_xcut": np.array([1, 11, 21])}, 3)
    assert steps is not None
    assert list(steps) == [1, 11, 21]


def test_the_volume_axis_wins_over_the_cut_plane_one():
    """Both present and both the right length: the main axis is the one read."""
    steps = recorded_steps(
        {
            "frame_index": np.array([1, 2, 3]),
            "frame_index_xcut": np.array([1, 11, 21]),
        },
        3,
    )
    assert steps is not None
    assert list(steps) == [1, 2, 3]


# --- the frame count the video really has ---------------------------------


def test_the_plan_keeps_the_first_and_the_last_frame():
    """The first and the last solver dump are never dropped."""
    indices = plan_decimation(2401, 60)
    assert indices[0] == 0
    assert indices[-1] == 2400
    assert len(indices) == 60


def test_the_plan_is_strictly_increasing():
    """No frame is drawn twice and none goes backwards."""
    indices = plan_decimation(2401, 60)
    assert all(b > a for a, b in zip(indices, indices[1:]))


def test_one_frame_out_is_the_first_frame():
    """A single-frame video is the start of the record, not an empty list."""
    assert plan_decimation(2401, 1) == [0]


@pytest.mark.parametrize(
    "n_total, n_out",
    [(0, 1), (1, 0), (10, 11)],
)
def test_an_impossible_plan_is_refused(n_total, n_out):
    """Asking for more frames than were recorded cannot be honoured silently."""
    with pytest.raises(ValueError):
        plan_decimation(n_total, n_out)


# --- the other pure helpers the exporter relies on ------------------------


def test_the_coordinate_vectors_are_found_by_their_lengths():
    """In-plane axes are matched by length, so a transposed dump is caught."""
    npz = {"x_mm": np.zeros(3), "y_mm": np.zeros(4), "z_mm": np.zeros(5)}
    assert axis_names(npz, 4, 5) == ("y_mm", "z_mm")


def test_a_dump_without_a_vector_of_the_drawn_length_is_refused():
    """A missing axis is an error, never a silent fallback to frame numbers."""
    with pytest.raises(KeyError):
        axis_names({"x_mm": np.zeros(3)}, 4, 3)


def test_the_colour_limits_are_symmetric_around_zero():
    """Both directions share one peak, so zero keeps the same colour everywhere."""
    assert default_clim(np.full((2, 2, 2), 3.0), [0, 1]) == (-3.0, 3.0)


# --- the structure that makes all of the above testable -------------------


def test_the_grammar_is_importable_without_matplotlib():
    """matplotlib is imported by the RENDER path, never by the module body.

    ``matplotlib.use("Agg")`` is a process-wide backend switch, so importing the
    exporter for its grammar must not perform it.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "matplotlib" not in imported, (
        "the exporter imports matplotlib at module scope again: importing it for "
        "the label grammar would switch the process to the Agg backend"
    )
