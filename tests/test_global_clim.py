"""One colour window for the WHOLE animation, computed once and memoised.

WHAT THIS PINS.  The field on screen decays: a clim taken per frame would
renormalise on every step and paint the tail of the pulse as bright as its
leading edge, so the decay the dump records would be invisible.  ``global_clim``
is the one door the page asks for a window through, and it answers from a memo
after the first call.

Both assertions are FALSIFYING, and each names the failure it catches:

    * call twice fifty times and count the computations - a viewer that
      rescales per frame grows the count on every draw;
    * the ceiling returned is the MEDIAN of the per-frame percentiles, and it is
      strictly above the last (decayed) frame's own percentile - a frame-local
      clim returns the smaller number and the equality below fails;
    * ONE 150x-hot frame in forty does NOT move the ceiling. A percentile
      POOLED over every sample at once does, and that is the rule this one
      replaced: on ``vis_dump_1500.npz`` the pooled p99.5 is 24.81 V/m while
      the median frame's own p99.5 is 3.20 and its brightest cell is 4.15, so
      97 % of a typical frame sat in the darkest tenth of the map.

No dump is opened and no plotter is touched: the window is pure arithmetic over
arrays this file builds itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import poc_app as app  # noqa: E402

FRAMES = 12


def _decaying_stack() -> np.ndarray:
    """A pulse that decays over the run, as every frame axis in the dumps does."""
    t = np.linspace(0.0, 1.0, FRAMES)
    field = np.ones((9, 6))
    return np.stack(
        [float(np.sin(np.pi * ti)) * np.exp(-2.0 * i / FRAMES) * field
         for i, ti in enumerate(t)]
    )


def _percentile(array, percentile: float = app.COLOR_PERCENTILE) -> float:
    return float(np.percentile(np.abs(np.asarray(array, dtype=np.float64)), percentile))


def _median_of_frame_percentiles(
    frames, percentile: float = app.COLOR_PERCENTILE
) -> float:
    """The oracle: the MEDIAN of each frame's own percentile, frame by frame.

    Written here from the DEFINITION, never by calling ``poc_app``, so that it
    can disagree with the implementation it is pinning. A frame is every plane
    that HAS that frame index (the x-cut planes need not share the y-cut's
    frame count); an empty or entirely non-finite frame is skipped because it
    has no ceiling of its own; an ALL-ZERO frame is NOT skipped, because zero is
    a ceiling a drawn frame really has.
    """
    blocks = [np.abs(np.asarray(frame, dtype=np.float64)) for frame in frames]
    blocks = [
        block.reshape(block.shape[0], -1) if block.ndim > 1 else block.reshape(1, -1)
        for block in blocks
        if block.size
    ]
    ceilings = []
    for index in range(max(block.shape[0] for block in blocks)):
        parts = [block[index] for block in blocks if index < block.shape[0]]
        parts = [part for part in parts if part.size]
        if not parts:
            continue
        chunk = np.concatenate(parts)
        if not np.any(np.isfinite(chunk)):
            continue
        ceilings.append(float(np.nanpercentile(chunk, percentile)))
    return float(np.median(ceilings))


def _pooled_percentile(
    frames, percentile: float = app.COLOR_PERCENTILE
) -> float:
    """The rule this one replaced: ONE percentile over every sample at once."""
    flat = [np.abs(np.asarray(frame, dtype=np.float64)).ravel() for frame in frames]
    return float(np.percentile(np.concatenate(flat), percentile))


def test_the_colour_window_is_computed_once_for_the_whole_animation():
    """FALSIFIED BY a per-frame clim: the 50 redraws below would recompute.

    Also falsified by asking only the drawn frame: the ceiling asserted here is
    the median of the per-frame percentiles, and the last frame's own percentile
    is strictly below it, so a frame-local answer cannot satisfy the equality.
    """
    data = _decaying_stack()
    app.GLOBAL_CLIM_CACHE.clear()
    calls_before = app.GLOBAL_CLIM_CALLS

    first = app.global_clim((data,))
    for _ in range(50):
        assert app.global_clim((data,)) == first, (
            "the same data set answered with a different window: the colour "
            "scale moved while the animation played"
        )

    computed = app.GLOBAL_CLIM_CALLS - calls_before
    assert computed == 1, (
        f"{computed} window(s) computed for 51 reads of ONE data set: the clim "
        "is not memoised, so a redraw rescaled the picture"
    )
    assert first[0] == 0.0 and first[2] is False
    expected = _median_of_frame_percentiles((data,))
    assert first[1] == pytest.approx(expected), (
        f"the ceiling {first[1]!r} is not the median of the per-frame "
        f"{app.COLOR_PERCENTILE}th percentiles {expected!r}"
    )
    assert first[1] > _percentile(data[-1]), (
        "the window equals the LAST frame's own percentile: this is a "
        "frame-local clim wearing a global name"
    )


def test_the_memo_is_keyed_on_the_data_not_on_its_shape():
    """FALSIFIED BY a shape-keyed memo: two dumps of one shape would share a clim.

    That failure is silent and wrong on screen - a live solve of the same grid
    would be painted on the previous run's ceiling - so the memo is keyed on the
    identity of the planes and the arrays are held alive beside the entry.
    """
    quiet = _decaying_stack() * 1.0
    loud = _decaying_stack() * 100.0

    quiet_window = app.global_clim((quiet,))
    loud_window = app.global_clim((loud,))

    assert quiet_window[1] != loud_window[1], (
        f"both data sets were given the window {quiet_window[1]!r}: the memo is "
        "keyed on the shape, not on the data"
    )
    assert loud_window[1] == pytest.approx(_median_of_frame_percentiles((loud,)))
    assert quiet_window[1] == pytest.approx(_median_of_frame_percentiles((quiet,)))


def test_limit_is_spike_robust():
    """FALSIFIED BY the pooled rule: one 150x-hot frame would set every scale.

    Forty typical frames whose own p99.5 is 1.0, plus ONE frame 150x hotter.
    The median of the per-frame ceilings is still 1.0 - the TYPICAL frame
    decides the scale - while the percentile POOLED over every sample at once
    is 150, which paints those forty frames 150x too dark. That is the bug on
    ``vis_dump_1500.npz``, where a pooled 24.81 V/m against a median frame's
    3.20 made a decaying pulse read as black.
    """
    typical = np.ones((40, 9, 6))
    hot = np.full((1, 9, 6), 150.0)
    stack = np.concatenate([typical, hot], axis=0)

    app.GLOBAL_CLIM_CACHE.clear()
    limit = app.global_clim((stack,))[1]

    per_frame = [
        _percentile(frame) for frame in stack
    ]
    assert float(np.median(per_frame[:-1])) == pytest.approx(1.0)
    pooled = _pooled_percentile((stack,))
    assert pooled == pytest.approx(150.0), (
        f"the hot frame did not move the pooled percentile ({pooled!r}): the "
        "test would not catch a revert to it"
    )
    assert limit == pytest.approx(1.0), (
        f"the limit {limit!r} followed the 150x-hot frame instead of the "
        "1.0 of the forty typical frames"
    )
    assert limit < 0.1 * pooled, (
        f"the limit {limit!r} is within 10 % of the POOLED percentile "
        f"{pooled!r}: this is the concatenate-everything rule wearing a "
        "global name"
    )
