"""One colour window for the WHOLE animation, computed once and memoised.

WHAT THIS PINS.  The field on screen decays: a clim taken per frame would
renormalise on every step and paint the tail of the pulse as bright as its
leading edge, so the decay the dump records would be invisible.  ``global_clim``
is the one door the page asks for a window through, and it answers from a memo
after the first call.

Both assertions are FALSIFYING, and each names the failure it catches:

    * call twice fifty times and count the computations - a viewer that
      rescales per frame grows the count on every draw;
    * the ceiling returned is the whole-axis percentile, and it is strictly
      above the last (decayed) frame's own percentile - a frame-local clim
      returns the smaller number and the equality below fails.

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


def test_the_colour_window_is_computed_once_for_the_whole_animation():
    """FALSIFIED BY a per-frame clim: the 50 redraws below would recompute.

    Also falsified by asking only the drawn frame: the ceiling asserted here is
    the whole-axis percentile, and the last frame's own percentile is strictly
    below it, so a frame-local answer cannot satisfy the equality.
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
    assert first[1] == pytest.approx(_percentile(data)), (
        f"the ceiling {first[1]!r} is not the whole-axis "
        f"{app.COLOR_PERCENTILE}th percentile {_percentile(data)!r}"
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
    assert loud_window[1] == pytest.approx(_percentile(loud))
    assert quiet_window[1] == pytest.approx(_percentile(quiet))
