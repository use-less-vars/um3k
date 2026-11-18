"""The image knobs where the view is made, the painted rate, and a seek.

Three claims, one per block below, all against fakes - no trame server is
started, no plotter is created and nothing is rendered:

* ``--image-quality`` is asked for WHERE THE TRAME VIEW IS CREATED. A property
  assigned after the layout was generated edits this process's copy and never
  reaches the page, and a name the widget does not know must be reported as NOT
  applied rather than "set" on an element that answers ``None`` to everything;
* the rate in the summary is measured over the PAINTED span - first painted
  tick to last - so a run that stopped painting at the end, or was paused, is
  read at the rate it painted instead of being divided by the time it sat still;
* a slider seek lands on the client timeline as its own ``seek`` event carrying
  where it came from and where it went - and nothing at all with the suite off.

A bad ``--image-quality`` is a USAGE error, refused by the same rule that reads
both the flag and its ``POC_*`` variable.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # The same two entries every other poc_app test adds, so `import poc_app`
        # resolves from server/poc_app.py.
        sys.path.insert(0, _p)

# pyvista lives in the repo's own venv in this image (its bin/python is broken,
# the site-packages tree is not). Inert where it is installed normally.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

import poc_app  # noqa: E402  (sys.path above is why this import is not at the top)


# ---------------------------------------------------------------------------
# The image knobs: asked for at creation, and never reported as applied on the
# strength of an attribute that does not exist.
# ---------------------------------------------------------------------------


class _Impl:
    """The one bit of a trame widget the honest check reads."""

    def __init__(self, allowed):
        self.allowed_keys = set(allowed)


class _Element:
    """A trame element: an unknown name ANSWERS None instead of raising."""

    def __init__(self, allowed):
        self._impl = _Impl(allowed)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return None  # trame prints "... is missing" and returns None


class _Plain:
    """An ordinary object: what a fake view with real properties looks like."""

    def __init__(self, **attributes):
        for name, value in attributes.items():
            setattr(self, name, value)


def test_the_quality_is_asked_for_where_the_view_is_created():
    """The kwargs reach the constructor; nothing asked for leaves the default."""
    assert poc_app._image_view_kwargs(70) == {
        "still_quality": 70,
        "interactive_quality": 70,
    }
    assert poc_app._image_view_kwargs() == {}
    assert poc_app._image_view_kwargs(None) == {}, "a missing knob asks for nothing"


def test_a_name_the_view_does_not_know_is_not_reported_as_applied():
    """``hasattr`` lies on a trame element, so the allowed keys are what is read."""
    assert poc_app._view_takes_prop(_Plain(still_quality=0), "still_quality") is True
    assert poc_app._view_takes_prop(_Plain(), "still_quality") is False

    # A trame element that forwards NO image property: no quality is recorded as
    # applied, and the png request is noted rather than flattered.
    view = _Element(allowed=())
    image = poc_app._apply_image_knobs(view, "png", 70)
    assert image["applied"] == {}
    assert "NOT applied" in image["note"]

    # One that forwards the quality but has no encoding property.
    half = _Element(allowed=("still_quality", "interactive_quality"))
    partial = poc_app._apply_image_knobs(half, "png", 70)
    assert partial["applied"] == {"still_quality": 70, "interactive_quality": 70}
    assert partial["encoding_applied"] == "jpeg"
    assert "NOT applied" in partial["note"]


class _Parser:
    """A parser whose only job here is to refuse, the way argparse does."""

    def __init__(self) -> None:
        self.message = None

    def error(self, message):
        self.message = message
        raise SystemExit(2)


def _args(**values):
    base = {"msaa": None, "image_encoding": None, "image_quality": None}
    base.update(values)
    return types.SimpleNamespace(**base)


def test_a_bad_image_quality_is_a_usage_error_not_a_knob_quietly_dropped():
    """7070 and 0 are refused, by name and by range, before any run starts."""
    for refused in (7070, 0, -1):
        parser = _Parser()
        with pytest.raises(SystemExit) as excinfo:
            poc_app._display_knobs_or_exit(parser, _args(image_quality=refused))
        assert excinfo.value.code == 2
        assert "--image-quality" in parser.message
        assert "1..100" in parser.message, parser.message

    # A value inside the range passes straight through, unchanged.
    knobbed = poc_app._display_knobs_or_exit(_Parser(), _args(image_quality=70))
    assert knobbed["image_quality"] == 70
    # Nothing asked for stays "not asked for", not a made-up default.
    quiet = poc_app._display_knobs_or_exit(_Parser(), _args())
    assert quiet == {"msaa": None, "image_encoding": None, "image_quality": None}


# ---------------------------------------------------------------------------
# The rate: over the painted span, not over the run's wall time.
# ---------------------------------------------------------------------------


def test_the_rate_is_measured_over_the_painted_span():
    """13 paints from t=0.0 to t=5.2 is 2.50 paints/s, whatever the row count."""
    rows = [
        {"t": index * 0.1, "wall_ms": 10.0, "counts": {"render": 1}}
        for index in range(10)
    ]
    # Held back by the paint cap or the delivery hold: rows, but no picture.
    rows += [
        {"t": 1.0 + index, "wall_ms": 10.0, "counts": {"render": 0, "push": 0}}
        for index in range(4)
    ]
    rows += [
        {"t": 5.0, "wall_ms": 10.0, "counts": {"push": 1}},
        {"t": 5.1, "wall_ms": 10.0, "counts": {"render": 1}},
    ]
    # A row carrying no counters at all is taken at face value.
    rows += [{"t": 5.2, "wall_ms": 10.0}]

    lines = poc_app._profile_rate_lines(rows, 24)
    assert lines[0] == (
        "target: fps=24 frame=41.67 ms  painted=13 over 5.20 s  "
        "paints/s=2.50 vs cap 24.00 (10.4% of target)"
    )
    assert lines[1] == "over one frame period: 0 of 17 ticks (0.0%)"

    assert poc_app._profile_painted_span(rows) == (13, pytest.approx(5.2))


def test_a_run_that_stopped_painting_is_not_read_as_a_slow_run():
    """20 unpainted ticks after the last paint do not stretch the painted span."""
    rows = [
        {"t": index * 0.1, "wall_ms": 10.0, "counts": {"render": 1}}
        for index in range(10)
    ]
    rows += [
        {"t": 1.0 + index * 0.1, "wall_ms": 10.0, "counts": {"render": 0, "push": 0}}
        for index in range(20)
    ]

    line = poc_app._profile_rate_lines(rows, 24)[0]
    # The whole-run reading would be 30 ticks over 2.9 s = 10.34 ticks/s, i.e. a
    # rate the viewer never saw: the last picture was drawn at t=0.9.
    assert "painted=10 over 0.90 s" in line
    assert "paints/s=11.11 vs cap 24.00 (46.3% of target)" in line


def test_with_nothing_painted_the_rate_is_zero_rather_than_a_division():
    """No rows, or one row (a span of nothing): 0.00, and no crash."""
    empty = poc_app._profile_rate_lines([], 24)
    assert "painted=0 over 0.00 s  paints/s=0.00 vs cap 24.00 (0.0% of target)" in (
        empty[0]
    )
    single = poc_app._profile_rate_lines([{"t": 3.0, "wall_ms": 10.0}], 24)
    assert "painted=1 over 0.00 s  paints/s=0.00" in single[0]
    assert single[1] == "over one frame period: 0 of 1 ticks (0.0%)"

    # A target that was never recorded (or is nonsense) still yields no lines.
    rows = [{"t": 0.0, "wall_ms": 10.0}]
    assert poc_app._profile_rate_lines(rows, None) == []
    assert poc_app._profile_rate_lines(rows, 0) == []
    assert poc_app._profile_rate_lines(rows, "fast") == []


# ---------------------------------------------------------------------------
# A seek: its own client event, carried with from/to.
# ---------------------------------------------------------------------------


@pytest.fixture
def client_events():
    """The client timeline cleared, the suite ON, the clock at 0.0."""
    saved = {
        key: (value.copy() if isinstance(value, (dict, list)) else value)
        for key, value in poc_app._PROFILE.items()
    }
    saved_events = list(poc_app._PROFILE["client"]["events"])
    events = poc_app._PROFILE["client"]["events"]
    events.clear()
    poc_app._PROFILE["enabled"] = True
    poc_app._PROFILE["started"] = None  # so _profile_elapsed answers 0.0
    try:
        yield events
    finally:
        poc_app._PROFILE.update(saved)
        poc_app._PROFILE["client"]["events"] = saved_events


def test_a_seek_is_a_client_event_carrying_where_it_came_from(client_events):
    """A slider jump is recorded as kind=seek, and the summary prints from/to."""
    handles = {"frame_seen": 40}
    poc_app._profile_seek(handles, 440)
    handles["frame_seen"] = 440

    assert len(client_events) == 1
    event = client_events[0]
    assert event["kind"] == "seek"
    assert (event["from"], event["to"]) == (40, 440)

    printed = poc_app._profile_delivery_lines()
    assert "ev t=0.000 kind=seek from=40 to=440" in printed

    # A first position has nothing to come from, and the line says only where it
    # went; the kinds that carried no detail print exactly as they always did.
    poc_app._profile_client_record("speed")
    printed = poc_app._profile_delivery_lines()
    assert "ev t=0.000 kind=speed" in printed

    poc_app._profile_seek({}, 7)
    assert client_events[-1]["kind"] == "seek"
    assert "from" not in client_events[-1]
    assert "ev t=0.000 kind=seek to=7" in poc_app._profile_delivery_lines()


def test_a_seek_records_nothing_when_the_suite_is_off(client_events):
    """With --profile off the timeline is untouched: the slider still works."""
    poc_app._PROFILE["enabled"] = False
    assert poc_app._profile_seek({"frame_seen": 12}, 99) is None
    assert client_events == []
