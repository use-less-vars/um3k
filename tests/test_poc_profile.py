"""``--profile``: WHERE the per-tick time goes, driven by a fake clock.

The suite in ``server/poc_app.py`` is a probe, and a probe is worth exactly what
its numbers are worth.  Nothing here boots the viewer or touches OpenGL: the
record functions are called directly, with a counter-based clock and hand-built
sheet meshes, so a failure names the bookkeeping rather than a rendered frame
nobody can inspect in this image.

The claims, one per test:

* off is a HARD no-op - every hook returns its neutral value, nothing is
  recorded and no file is opened, so ``--profile`` costs a run without the flag
  nothing at all;
* a tick row carries the WHOLE tick (``wall_ms``) beside the named phases, and
  a phase is measured from the previous mark, so the two are comparable;
* a sheet repainted at the index it already held is counted as a NO-OP - the
  waste metric - and the summary says "N of M";
* a rebind (``point_data[k] = fresh``) and an in-place write
  (``point_data[k][:] = data``) are counted apart, and an unreadable buffer is
  counted as NEITHER rather than being flattered as in-place;
* the loop-lag figure is the sampler's own lateness (wake interval minus the
  interval it asked for), and the first wake only sets the baseline;
* the idle record is the CPU this process burned while it drew nothing, with
  the call counters' deltas, and it is refused inside a tick;
* stacks are aggregated per innermost frame per thread, written as one line per
  sample;
* ``render``/``add_mesh``/``remove_actor`` are counted on the plotter INSTANCE,
  and a mute that replaces ``plotter.render`` is honestly not counted - those
  calls never reached the GL draw;
* the tick row is parked until the next tick, so the yield mark lands in the
  same row the file already serialised;
* the JSONL file gets one line per tick plus one per idle record;
* the summary never raises - an empty run included - and stays <= 60 lines;
* a profile directory that cannot be created costs the run its files, never its
  records;
* the three display knobs have ONE validating home, so a flag and its ``POC_*``
  variable are refused by the same rule instead of a value VTK would ignore
  being accepted and silently dropped;
* ``main`` hands those knobs to the shell AND records them, so the summary names
  the knobs that produced its numbers rather than guessing them later;
* a png request is reported as NOT applied, because the trame image transport
  writes jpeg itself and a knob recorded as honoured when it was not is a lie;
* the GL strings are read only from a window that has really rendered - asking an
  unrendered off-screen window for them takes the process down here - and what
  cannot be read is reported as pending, not guessed;
* ONE draw and ONE push per tick: a plotter whose own ``render()`` already pushes
  (a trame view registers a render callback) is NOT pushed again - that would
  ship the same picture twice - and a plotter without one still is;
* the push is counted where that decision is made AND only when one was really
  sent, so the tick row and the summary's ``calls:`` line name it beside
  ``render`` while a tick with no view counts nothing;
* every still is also NAMED by the control that asked for it (``push_by_site:``
  in the summary, ``push:<site>`` in the row), so the sites ADD UP to the
  ``push`` total instead of a control handler's own push being invisible;
* the renderer report is said a SECOND time, once, after the first frame has
  really drawn - the boot line cannot know the driver yet - and the prefix says
  which of the two lines it is;
* the image-delivery wrappers count each of trame's five calls AND still delegate
  to them, once however often the class is wrapped;
* a push trame would drop is attributed to the reason IT would have given -
  untracked, disabled, or dropped while a view animates - so a hundred attempted
  pushes that shipped nothing cannot be read as a hundred frames;
* a still is a measured encode: its milliseconds and its payload bytes, and a
  still that raised still reports the time it burned;
* the animated span is the wall time between animate() calls while a view really
  animates, and a client's start/stop is told apart from a user's drag by the
  observer that made the call;
* a tick row carries the delivery's DELTA over that tick, so a parked frame is
  read beside the tick that parked it rather than beside the run's total;
* without trame_vtk the hook says so (``available=no``) instead of reporting five
  zeros as if the delivery had been watched and found idle.
"""

from __future__ import annotations

import json
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
# The stand-ins: a clock, a sheet mesh, a plotter.
# ---------------------------------------------------------------------------


class _Points(dict):
    """The one bit of a pyvista mesh the sheet bookkeeping reads."""


class _Grid:
    """A cut sheet, reduced to the buffer the profiler compares."""

    def __init__(self, buf=None):
        self.point_data = _Points()
        if buf is not None:
            self.point_data["ez_abs"] = buf
        self.modified = 0

    def Modified(self):  # noqa: N802 - pyvista's own spelling
        self.modified += 1


class _Plotter:
    """A plotter whose three instrumented calls are all this test needs."""

    def __init__(self):
        self.actors = {"board": object(), "sheet": object()}
        self.renders = 0

    def render(self):
        self.renders += 1
        return "rendered"

    def add_mesh(self, *args, **kwargs):
        self.actors["mesh%d" % len(self.actors)] = object()
        return "added"

    def remove_actor(self, actor):
        self.actors.pop("mesh", None)
        return "removed"


class _Run:
    """A fake clock plus the handful of hook calls one tick is made of."""

    def __init__(self, clock):
        self.clock = clock

    def advance(self, ms: float) -> float:
        self.clock["t"] += float(ms) / 1000.0
        return self.clock["t"]

    def tick(
        self,
        frame=None,
        mode="ycut",
        phases=(("reanchor", 10.0), ("target", 2.0), ("draw", 20.0), ("flush", 1.0)),
        sheets=(),
        plotter=None,
        yield_ms=None,
    ):
        """Run one tick: begin, named phases, optional sheets, end, optional yield."""
        poc_app._profile_tick_begin(frame, mode)
        for name, ms in phases:
            self.advance(ms)
            poc_app._profile_phase(name)
        sheet_rows = []
        for key, index, mesh, ms in sheets:
            rec = poc_app._profile_sheet_begin(key, mesh)
            self.advance(ms)
            sheet_rows.append(poc_app._profile_sheet_end(rec, index, mesh))
        poc_app._profile_tick_end(frame, plotter=plotter, mode=mode)
        if yield_ms is not None:
            self.advance(yield_ms)
            poc_app._profile_yield()
        return sheet_rows


@pytest.fixture
def prof(tmp_path):
    """The suite on, with a fake clock that starts at 0.0 (which is a clock)."""
    saved = {
        key: (value.copy() if isinstance(value, (dict, list)) else value)
        for key, value in poc_app._PROFILE.items()
    }
    try:
        poc_app._profile_configure(False)
        poc_app._profile_reset()
        clock = {"t": 0.0}
        run = tmp_path / "profile"
        poc_app._profile_configure(
            True, run, clock=lambda: clock["t"], start_threads=False
        )
        files = dict(poc_app._PROFILE["files"])
        yield types.SimpleNamespace(
            clock=clock,
            run=_Run(clock),
            dir=run,
            files=files,
            ticks=files.get("ticks"),
            stacks=files.get("stacks"),
            summary=files.get("summary"),
        )
    finally:
        poc_app._profile_configure(False)
        poc_app._PROFILE["files"] = {}
        poc_app._PROFILE.update(saved)


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def _json_lines(path):
    return [json.loads(line) for line in _lines(path) if line.strip()]


# ---------------------------------------------------------------------------
# Off is off.
# ---------------------------------------------------------------------------


def test_disabled_profile_is_a_hard_noop(tmp_path):
    """With the suite off every hook is neutral and no file is opened."""
    poc_app._profile_configure(False)
    poc_app._profile_reset()

    assert poc_app._profile_enabled() is False
    assert poc_app._profile_configure(False, tmp_path / "run") is None
    assert poc_app._profile_tick_begin(0, "ycut") is None
    assert poc_app._profile_phase("draw") == 0.0
    assert poc_app._profile_sheet_begin("ycut", _Grid()) is None
    assert poc_app._profile_sheet_end(None, 0, None) is None
    assert poc_app._profile_tick_end(0, plotter=_Plotter(), mode="ycut") is None
    assert poc_app._profile_yield() == 0.0
    assert poc_app._profile_lag_sample() is None
    assert poc_app._profile_stack_sample() is None
    assert poc_app._profile_idle_sample() is None
    assert poc_app._profile_summary_text() == ""
    assert poc_app._profile_write_summary() == ""
    assert poc_app._profile_write("ticks", "{}") is False
    assert poc_app._profile_flush_pending() is False
    # The delivery hook is INSTALLED even with the suite off: the pump has to know
    # whether trame is mid-animation to avoid advancing a position into a still
    # trame discards, and that is a correctness fact, not telemetry. What stays
    # gated is the COUNTING behind the wrappers, so an unmeasured run still
    # records nothing at all.
    hooked = poc_app._profile_hook_delivery()
    assert isinstance(hooked, bool), hooked
    assert poc_app._PROFILE["push"]["attempts"] == 0
    assert poc_app._PROFILE["push"]["rendered"] == 0
    assert poc_app._PROFILE["still"]["n"] == 0
    # Put the flags back: the wrappers are idempotent and stay installed, but a
    # later test must be able to ask the hook again as if it had not been called.
    poc_app._PROFILE["delivery_hooked"] = False
    poc_app._PROFILE["push"]["available"] = False

    assert poc_app._PROFILE["rows"] == []
    assert poc_app._PROFILE["lag"] == []
    assert poc_app._PROFILE["idle"] == []
    assert poc_app._PROFILE["sheets"] == {}
    assert list(tmp_path.iterdir()) == []


def test_env_switches_ask_for_the_suite(monkeypatch):
    """POC_PROFILE and POC_TIMING both opt in; blank and "0" do not."""
    for key in poc_app._PROFILE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    assert poc_app._profile_env_enabled() is False
    for key in poc_app._PROFILE_ENV_KEYS:
        monkeypatch.setenv(key, "1")
        assert poc_app._profile_env_enabled() is True
        for value in ("0", "", "  "):
            monkeypatch.setenv(key, value)
            assert poc_app._profile_env_enabled() is False
        monkeypatch.delenv(key)


# ---------------------------------------------------------------------------
# One tick, one row.
# ---------------------------------------------------------------------------


def test_tick_row_carries_the_whole_wall_and_each_phase(prof):
    """``wall_ms`` is the whole tick; each phase is the span since the last mark."""
    prof.run.tick(
        frame=7,
        mode="xcut",
        phases=(("reanchor", 12.0), ("target", 3.0), ("draw", 25.0), ("flush", 5.0)),
        plotter=_Plotter(),
        yield_ms=4.0,
    )

    rows = poc_app._PROFILE["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "tick"
    assert row["n"] == 1
    assert row["frame_asked"] == 7
    assert row["frame_published"] == 7
    assert row["mode"] == "xcut"
    # 12 + 3 + 25 + 5 = 45 ms of named phases, and the yield mark is AFTER the
    # tick closed, so it is reported apart from the wall.
    assert row["wall_ms"] == pytest.approx(45.0)
    assert row["phases"]["reanchor"] == pytest.approx(12.0)
    assert row["phases"]["target"] == pytest.approx(3.0)
    assert row["phases"]["draw"] == pytest.approx(25.0)
    assert row["phases"]["flush"] == pytest.approx(5.0)
    assert row["phases"]["yield"] == pytest.approx(4.0)
    # The clock started at 0.0 and this is the first tick: t is 0, not "unset".
    assert row["t"] == pytest.approx(0.0)
    assert row["actors"] == len(_Plotter().actors)


def test_a_closed_tick_is_parked_until_the_next_one_starts(prof):
    """The yield mark lands in the row the file serialises, because it is parked."""
    prof.run.tick(frame=0, yield_ms=6.0)
    assert not prof.ticks.exists(), "the row is flushed by the NEXT tick, not now"

    prof.run.tick(frame=1, yield_ms=1.0)
    rows = _json_lines(prof.ticks)
    assert len(rows) == 1
    assert rows[0]["frame_asked"] == 0
    assert rows[0]["phases"]["yield"] == pytest.approx(6.0)

    poc_app._profile_flush_pending()
    rows = _json_lines(prof.ticks)
    assert len(rows) == 2
    assert rows[1]["frame_asked"] == 1
    assert [row["n"] for row in rows] == [1, 2]


def test_the_jsonl_gets_one_line_per_tick_plus_each_idle_record(prof):
    """Three ticks and one idle record: four lines, in that order."""
    prof.run.tick(frame=0)
    prof.run.tick(frame=1)
    prof.run.tick(frame=2)

    prof.run.advance(1000.0)
    assert poc_app._profile_idle_sample(
        cpu=1.0, utime=0.6, stime=0.4, counts={"render": 5}
    ) is None, "the first idle record is the baseline"
    prof.run.advance(1000.0)
    idle = poc_app._profile_idle_sample(
        cpu=1.05, utime=0.63, stime=0.42, counts={"render": 7}
    )
    assert idle is not None
    poc_app._profile_flush_pending()

    lines = _json_lines(prof.ticks)
    assert [row["kind"] for row in lines] == ["tick", "tick", "tick", "idle"]
    assert [row["n"] for row in lines[:3]] == [1, 2, 3]
    assert lines[3]["idle_s"] == pytest.approx(1.0)
    assert lines[3]["process_s"] == pytest.approx(0.05)
    assert lines[3]["utime_s"] == pytest.approx(0.03)
    assert lines[3]["stime_s"] == pytest.approx(0.02)
    assert lines[3]["cpu_per_s"] == pytest.approx(0.05)
    assert lines[3]["counts"] == {"render": 2}
    assert lines[3]["t"] == pytest.approx(2.099, abs=1e-6)


def test_no_idle_record_while_ticks_are_running(prof):
    """Idle means idle: a tick in the last second refuses the record."""
    prof.run.tick(frame=0)
    prof.run.advance(100.0)
    assert poc_app._profile_idle_sample(cpu=1.0, utime=0.6, stime=0.4) is None
    assert poc_app._PROFILE["idle"] == []


# ---------------------------------------------------------------------------
# The waste metric: a sheet repainted at the index it already held.
# ---------------------------------------------------------------------------


def test_repaint_at_an_unchanged_index_is_counted_as_a_noop(prof):
    """ycut moves every tick, the two x cuts hold at 0: 6 repaints, 4 no-ops."""
    for tick in range(3):
        grid_y = _Grid()
        grid_n = _Grid()
        grid_f = _Grid()
        prof.run.tick(
            frame=tick,
            sheets=(
                ("ycut", tick, grid_y, 3.0),
                ("xcut_near", 0, grid_n, 2.0),
                ("xcut_far", 0, grid_f, 2.0),
            ),
        )

    sheets = poc_app._PROFILE["sheets"]
    assert set(sheets) == {"ycut", "xcut_near", "xcut_far"}
    assert sheets["ycut"]["repaints"] == 3
    assert sheets["ycut"]["noop"] == 0
    assert sheets["ycut"]["index_changes"] == 3
    assert sheets["xcut_near"]["repaints"] == 3
    assert sheets["xcut_near"]["noop"] == 2
    assert sheets["xcut_near"]["index_changes"] == 1
    assert sheets["xcut_far"]["last_index"] == 0

    rows = poc_app._PROFILE["rows"]
    assert rows[1]["sheets"][1]["changed"] is False
    assert rows[2]["sheets"][0]["changed"] is True

    text = poc_app._profile_summary_text()
    assert "no-op sheet repaints (index unchanged): 4 of 9 (44.4%)" in text
    # Per-sheet numbers, in the sheet table: repaints, no-op and the split.
    ycut_line = [line for line in text.splitlines() if line.strip().startswith("ycut")][0]
    assert [part for part in ycut_line.split()] == ["ycut", "3", "3.00", "3.00", "3.00", "0", "0/0"]


def test_rebind_and_in_place_writes_are_counted_apart(prof):
    """``point_data[k] = fresh`` is an assignment; ``[:] = data`` is in place."""
    import numpy as np

    rebound = _Grid(np.zeros(4))
    in_place = _Grid(np.zeros(4))
    unknown = _Grid()  # no buffer to compare at all

    for tick in range(2):
        rec = poc_app._profile_sheet_begin("ycut", rebound)
        rebound.point_data["ez_abs"] = np.zeros(4)  # rebind: what the app does
        prof.run.advance(2.0)
        poc_app._profile_sheet_end(rec, tick, rebound)

        rec = poc_app._profile_sheet_begin("xcut_near", in_place)
        in_place.point_data["ez_abs"][:] = float(tick)  # write the same buffer
        prof.run.advance(2.0)
        poc_app._profile_sheet_end(rec, tick, in_place)

        rec = poc_app._profile_sheet_begin("xcut_far", unknown)
        prof.run.advance(2.0)
        row = poc_app._profile_sheet_end(rec, tick, unknown)

    sheets = poc_app._PROFILE["sheets"]
    assert sheets["ycut"]["assigned"] == 2
    assert sheets["ycut"]["in_place"] == 0
    assert sheets["xcut_near"]["in_place"] == 2
    assert sheets["xcut_near"]["assigned"] == 0
    # Unknown is neither: an unreadable buffer must not be flattered.
    assert sheets["xcut_far"]["in_place"] == 0
    assert sheets["xcut_far"]["assigned"] == 0
    assert row["in_place"] is None


def test_sheet_time_is_that_sheet_s_own_upload(prof):
    """Each sheet closes inside the loop: three sheets, three separate spans."""
    rows = prof.run.tick(
        frame=0,
        sheets=(
            ("ycut", 0, _Grid(), 3.0),
            ("xcut_near", 0, _Grid(), 5.0),
            ("xcut_far", 0, _Grid(), 7.0),
        ),
    )
    assert [row["ms"] for row in rows] == pytest.approx([3.0, 5.0, 7.0])
    text = poc_app._profile_summary_text()
    for key, ms in (("ycut", 3.0), ("xcut_near", 5.0), ("xcut_far", 7.0)):
        line = [line for line in text.splitlines() if line.strip().startswith(key)][0]
        assert float(line.split()[2]) == pytest.approx(ms)


# ---------------------------------------------------------------------------
# Loop lag and stacks.
# ---------------------------------------------------------------------------


def test_loop_lag_is_the_samplers_own_lateness(prof):
    """Asked to wake every 50 ms, woken after 60: 10 ms late, and the first is a baseline."""
    for _ in range(4):
        prof.run.advance(60.0)
        poc_app._profile_lag_sample()

    lag = poc_app._PROFILE["lag"]
    assert len(lag) == 3, "the first wake only sets the baseline"
    assert lag == pytest.approx([10.0, 10.0, 10.0])
    assert "loop lag (ms): n=3 mean=10.00 p95=10.00 max=10.00" in (
        poc_app._profile_summary_text()
    )


def test_a_wake_that_is_not_late_never_reports_a_negative_lag(prof):
    """The clock can round backwards; the record is clamped at zero."""
    poc_app._profile_lag_sample(now=1.0)
    poc_app._profile_lag_sample(now=1.01)  # 10 ms, ten EARLY of the 50 asked
    assert poc_app._PROFILE["lag"] == [0.0]


def test_stack_sample_aggregates_the_innermost_frame_of_every_thread(prof):
    """Two threads in the same function, one elsewhere: counted, and written down."""

    class _Code:
        def __init__(self, filename, name):
            self.co_filename = filename
            self.co_name = name

    class _Frame:
        def __init__(self, filename, name):
            self.f_code = _Code(filename, name)

    frames = {
        1: _Frame("/app/server/poc_app.py", "_show"),
        2: _Frame("/app/server/poc_app.py", "_show"),
        3: _Frame("/app/server/poc_app.py", "enqueue_output"),
    }
    prof.run.advance(200.0)
    leaves = poc_app._profile_stack_sample(frames=frames)

    assert leaves == {"poc_app.py:_show": 2, "poc_app.py:enqueue_output": 1}
    assert poc_app._PROFILE["stacks"]["poc_app.py:_show"] == 2

    lines = _lines(prof.stacks)
    assert len(lines) == 1
    assert lines[0].startswith("t=0.20s threads=2 ")
    assert "2x poc_app.py:_show" in lines[0]
    assert "1x poc_app.py:enqueue_output" in lines[0]

    text = poc_app._profile_summary_text()
    assert "top functions (stack samples, all threads):" in text
    assert " 2  66.7%  poc_app.py:_show" in text


# ---------------------------------------------------------------------------
# The plotter counter.
# ---------------------------------------------------------------------------


def test_attach_counts_the_three_calls_on_the_instance(prof):
    """render/add_mesh/remove_actor are counted where pyvista itself calls them."""
    plotter = _Plotter()
    assert poc_app._profile_attach(plotter) is True
    assert poc_app._profile_attach(plotter) is False, "one wrapper, not a stack"

    assert plotter.render() == "rendered"
    plotter.add_mesh(object())
    plotter.remove_actor(object())
    plotter.remove_actor(object())

    assert poc_app._PROFILE["counts"] == {"render": 1, "add_mesh": 1, "remove_actor": 2}
    assert _Plotter().render() == "rendered", "the CLASS is untouched"

    # A tick reports the calls THAT tick made, not the run's running total.
    poc_app._profile_tick_begin(0, "ycut")
    plotter.render()
    plotter.add_mesh(object())
    prof.run.advance(2.0)
    poc_app._profile_phase("draw")
    poc_app._profile_tick_end(0, plotter=plotter, mode="ycut")

    assert poc_app._PROFILE["rows"][0]["counts"] == {"render": 1, "add_mesh": 1}
    assert "calls: render=2 push=0 add_mesh=2 remove_actor=2" in (
        poc_app._profile_summary_text()
    )


def test_a_mute_that_replaces_render_is_not_counted(prof):
    """The honest reading: a muted render never reached the GL draw."""
    plotter = _Plotter()
    poc_app._profile_attach(plotter)
    inner = plotter.render

    plotter.render = lambda: None  # what the sheet layer does while it builds
    plotter.render()
    assert poc_app._PROFILE["counts"].get("render", 0) == 0

    plotter.render = inner
    plotter.render()
    assert poc_app._PROFILE["counts"]["render"] == 1


def test_a_plotter_that_refuses_the_wrapper_is_not_fatal(prof):
    """`__slots__` and friends: the counter is lost, the run is not."""

    class _Stubborn:
        __slots__ = ()

        def render(self):
            return "rendered"

    assert poc_app._profile_attach(_Stubborn()) is False
    assert poc_app._profile_enabled() is True


# ---------------------------------------------------------------------------
# The summary.
# ---------------------------------------------------------------------------


def test_summary_of_an_empty_run_never_raises(prof):
    """No ticks, no sheets, no lag, no stacks: still a readable summary."""
    text = poc_app._profile_summary_text()
    assert text.startswith("poc_app --profile summary  run=")
    assert "ticks=0" in text
    assert "phases (ms): phase       n     p50     p95     max" in text

    written = poc_app._profile_write_summary()
    assert written == text
    assert prof.summary.read_text(encoding="utf-8") == text


def test_summary_reports_phases_as_p50_p95_and_max(prof):
    """Three ticks of increasing draw time: the tail is reported, not hidden."""
    for ms in (10.0, 20.0, 60.0):
        prof.run.tick(
            frame=0,
            phases=(("reanchor", 5.0), ("target", 1.0), ("draw", ms), ("flush", 1.0)),
        )

    text = poc_app._profile_summary_text()
    draw = [line for line in text.splitlines() if line.strip().startswith("draw")][0]
    assert draw.split()[1:] == ["3", "20.00", "60.00", "60.00"]
    wall = [line for line in text.splitlines() if line.startswith("tick wall")][0]
    assert wall == "tick wall (ms): n=3 p50=27.00 p95=67.00 max=67.00"


def test_summary_is_never_longer_than_sixty_lines(prof):
    """A cap, so the last breath of a run is always a summary and not a dump."""
    prof.run.tick(frame=0)
    for index in range(80):
        poc_app._PROFILE.setdefault("stacks", {})["f.py:fn%d" % index] = 80 - index
    text = poc_app._profile_summary_text()
    assert len(text.splitlines()) <= 60
    assert text.endswith("\n")


def test_a_directory_that_cannot_be_created_costs_the_files_not_the_records(
    tmp_path, monkeypatch
):
    """Telemetry that cannot open a file still records, and still never raises."""
    poc_app._profile_configure(False)
    poc_app._profile_reset()
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")

    assert poc_app._profile_configure(True, blocker / "run", start_threads=False) is None
    assert poc_app._PROFILE["files"] == {}
    assert poc_app._profile_enabled() is True

    poc_app._profile_tick_begin(0, "ycut")
    poc_app._profile_phase("draw")
    poc_app._profile_tick_end(0, plotter=None, mode="ycut")
    assert len(poc_app._PROFILE["rows"]) == 1
    assert poc_app._profile_write("ticks", "{}") is False
    assert poc_app._profile_summary_text().startswith("poc_app --profile summary")
    assert poc_app._profile_write_summary() != ""
    poc_app._profile_configure(False)


# ---------------------------------------------------------------------------
# The display knobs: --msaa, --image-encoding, --image-quality.
# ---------------------------------------------------------------------------


@pytest.fixture
def knobs():
    """An empty knob record, restored afterwards (the record is process state)."""
    saved = dict(poc_app._PROFILE["knobs"])
    poc_app._PROFILE["knobs"] = {}
    try:
        yield poc_app._PROFILE["knobs"]
    finally:
        poc_app._PROFILE["knobs"] = saved


@pytest.fixture
def renderer():
    """The boot report, saved and restored: it is filled once per run."""
    saved = dict(poc_app._RENDERER)
    try:
        yield poc_app._RENDERER
    finally:
        poc_app._RENDERER.clear()
        poc_app._RENDERER.update(saved)


class _Recorder:
    """Stand in for a shell and remember every call."""

    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, *args, **kwargs) -> int:
        self.calls.append((args, kwargs))
        return 0


@pytest.fixture
def wiring(monkeypatch, tmp_path):
    """``main`` with its four seams recorded and one synthetic structure entry.

    The same substitution tests/test_poc_dispatch.py uses: no trame server boots,
    no plotter is created and no npz is opened, so what is under test is the
    argument the routing carries.
    """
    entry = {"id": "s1"}
    page = {"info": None, "path": str(tmp_path / "d.npz")}
    monkeypatch.setattr(poc_app, "load_structures", lambda: [entry])
    monkeypatch.setattr(
        poc_app, "_structure_is_record_only", lambda structure: False
    )
    monkeypatch.setattr(
        poc_app, "reload_page", lambda npz_path, structure_id=None: page
    )
    recorders = {
        "print_keys": _Recorder(),
        "run_web_vis": _Recorder(),
        "run_web": _Recorder(),
    }
    for name, recorder in recorders.items():
        monkeypatch.setattr(poc_app, name, recorder)
    return {"page": page, "entry": entry, **recorders}


def _run_main(wiring, *extra: str) -> int:
    """``main`` on a synthetic animation page, with every seam recorded."""
    wiring["page"]["info"] = {
        "format": poc_app.VIS_FORMAT,
        "nt": 4,
        "nt_x": 2,
    }
    return poc_app.main(
        ["--structure", "s1", "--input", "fake.npz", *extra]
    )


def test_the_display_knobs_default_to_none_and_keep_their_spelling():
    """Unasked is None (not 0, not ""): the report spells that "default"."""
    assert poc_app._resolve_display_knobs() == {
        "msaa": None,
        "image_encoding": None,
        "image_quality": None,
    }
    # A flag arrives as text and a variable as text; both land on the same three
    # values, and the encoding is normalised so " JPEG " is the same request.
    assert poc_app._resolve_display_knobs("4", " JPEG ", "70") == {
        "msaa": 4,
        "image_encoding": "jpeg",
        "image_quality": 70,
    }


def test_a_bad_display_knob_is_refused_by_name():
    """A value VTK or the transport would ignore is a ValueError, not a no-op."""
    with pytest.raises(ValueError, match="--msaa"):
        poc_app._resolve_display_knobs(msaa=-1)
    with pytest.raises(ValueError, match="--msaa"):
        poc_app._resolve_display_knobs(msaa="four")
    with pytest.raises(ValueError, match="--image-encoding"):
        poc_app._resolve_display_knobs(image_encoding="gif")
    with pytest.raises(ValueError, match="--image-quality"):
        poc_app._resolve_display_knobs(image_quality=0)
    with pytest.raises(ValueError, match="--image-quality"):
        poc_app._resolve_display_knobs(image_quality=101)


def test_main_hands_the_display_knobs_to_the_shell(wiring, knobs):
    """The flags reach the one shell, and the run records what they became."""
    rc = _run_main(
        wiring,
        "--msaa",
        "4",
        "--image-encoding",
        "png",
        "--image-quality",
        "70",
    )

    assert rc == 0
    assert len(wiring["run_web_vis"].calls) == 1, wiring["run_web_vis"].calls
    _args, kwargs = wiring["run_web_vis"].calls[0]
    assert kwargs["msaa"] == 4
    assert kwargs["image_encoding"] == "png"
    assert kwargs["image_quality"] == 70
    # Recorded whatever the suite is doing: the summary names the knobs instead
    # of guessing them from an argument it never saw.
    assert poc_app._PROFILE["knobs"] == {
        "fps": poc_app.DEFAULT_FPS,
        "msaa": 4,
        "image_encoding": "png",
        "image_quality": 70,
    }


def test_the_knobs_can_come_from_the_environment(wiring, knobs, monkeypatch):
    """POC_MSAA / POC_IMAGE_ENCODING / POC_IMAGE_QUALITY: same numbers, no flag."""
    monkeypatch.setenv("POC_MSAA", "2")
    monkeypatch.setenv("POC_IMAGE_ENCODING", "jpeg")
    monkeypatch.setenv("POC_IMAGE_QUALITY", "55")

    assert _run_main(wiring) == 0

    _args, kwargs = wiring["run_web_vis"].calls[0]
    assert kwargs["msaa"] == 2
    assert kwargs["image_encoding"] == "jpeg"
    assert kwargs["image_quality"] == 55
    assert poc_app._PROFILE["knobs"]["msaa"] == 2
    assert poc_app._PROFILE["knobs"]["image_encoding"] == "jpeg"
    assert poc_app._PROFILE["knobs"]["image_quality"] == 55


def test_a_bad_flag_is_a_usage_error_not_a_silently_dropped_knob(wiring):
    """argparse reports it and exits 2; the run never reaches a plotter."""
    with pytest.raises(SystemExit) as caught:
        _run_main(wiring, "--msaa", "-1")
    assert caught.value.code == 2, "a bad knob must not start a viewer"
    assert wiring["run_web_vis"].calls == []


# ---------------------------------------------------------------------------
# What cannot be read is reported, never guessed.
# ---------------------------------------------------------------------------


class _Window:
    """The three render-window reads the report makes, and a call counter."""

    def __init__(self, caps="", never=1, size=(1024, 768), samples=8):
        self.caps_text = caps
        self.never = never
        self.size = size
        self.samples = samples
        self.caps_reads = 0

    def GetNeverRendered(self):
        return self.never

    def ReportCapabilities(self):
        # In this image the real call SEGFAULTS on a box with no GL driver, so a
        # test that reaches it must fail rather than quietly return nothing.
        self.caps_reads += 1
        return self.caps_text

    def GetSize(self):
        return self.size

    def GetMultiSamples(self):
        return self.samples


class _Reported:
    """A plotter, reduced to the window the boot report reads."""

    def __init__(self, window):
        self.render_window = window


class _View:
    """The trame view's two real quality knobs, and image_encoding when taken."""

    def __init__(self, accepts_encoding=False):
        self.still_quality = 0
        self.interactive_quality = 0
        if accepts_encoding:
            self.image_encoding = None


def test_the_gl_report_is_pending_until_the_window_has_really_rendered(renderer):
    """An unrendered window is NOT asked: the report says pending and the run lives."""
    window = _Window(caps="OpenGL vendor string: Mesa\n", never=1)
    assert poc_app._gl_capabilities(window) is None
    assert window.caps_reads == 0, "an unrendered window was asked for a GL report"

    report = poc_app._renderer_report(plotter=_Reported(window), msaa=8)
    assert report["pixels"] == (1024, 768)
    assert report["multi_samples"] == 8
    assert report["msaa_applied"] == 8, "applied must be what the WINDOW holds"
    assert report["gl_mode"] == "unknown"
    assert "not been rendered" in report["gl_note"]

    line = poc_app._renderer_report_line()
    assert line.startswith(
        "[poc_app] renderer: gl=unknown vendor=? renderer=? version=?"
    )
    assert "pixels=1024x768" in line
    assert "plotter multi_samples=8" in line
    assert "msaa requested=8 applied=8" in line
    assert "not been rendered" in line


def test_the_gl_strings_are_read_in_either_spelling_vtk_prints(renderer):
    """Both ReportCapabilities() layouts, and the mode they add up to."""
    old = poc_app._gl_parse_capabilities(
        "OpenGL vendor string: Mesa/X.org\n"
        "OpenGL renderer string: llvmpipe (LLVM 15.0.7, 256 bits)\n"
        "OpenGL version string: 4.5 (Core Profile) Mesa 23.0.4\n"
    )
    assert old == {
        "vendor": "Mesa/X.org",
        "renderer": "llvmpipe (LLVM 15.0.7, 256 bits)",
        "version": "4.5 (Core Profile) Mesa 23.0.4",
    }

    new = poc_app._gl_parse_capabilities(
        "Vendor: NVIDIA Corporation\n"
        "Driver Version: 535.86.10\n"
        "Renderer: NVIDIA GeForce RTX 3070/PCIe/SSE2\n"
        "Version: 4.6.0 NVIDIA 535.86.10\n"
    )
    assert new["vendor"] == "NVIDIA Corporation"
    assert new["renderer"] == "NVIDIA GeForce RTX 3070/PCIe/SSE2"
    assert new["version"] == "4.6.0 NVIDIA 535.86.10", (
        "Driver Version is the driver's number, not the GL one"
    )

    # A CPU rasteriser and a driver are named apart: the same field at llvmpipe
    # is a different claim about the timing than the same field on a GPU.
    assert poc_app._gl_mode("Mesa/X.org", "llvmpipe (LLVM 15.0.7)") == "software"
    assert poc_app._gl_mode("NVIDIA Corporation", "RTX 3070/PCIe/SSE2") == "direct"
    assert poc_app._gl_mode(None, None) == "unknown"

    # A rendered window is asked ONCE, and the answer reaches the report.
    window = _Window(
        caps="OpenGL vendor string: Mesa/X.org\n"
        "OpenGL renderer string: llvmpipe (LLVM 15.0.7)\n"
        "OpenGL version string: 4.5\n",
        never=0,
    )
    caps = poc_app._gl_capabilities(window)
    assert caps["mode"] == "software"
    assert window.caps_reads == 1
    report = poc_app._renderer_report(plotter=_Reported(window), msaa=None)
    assert report["gl_vendor"] == "Mesa/X.org"
    assert report["gl_mode"] == "software"
    assert report["gl_note"] is None


def test_a_png_request_is_applied_where_it_can_be_and_reported_where_it_cannot():
    """quality is a view property; the encoding is the transport's, so it is noted."""
    view = _View()
    image = poc_app._apply_image_knobs(view, "png", 70)
    assert image["applied"] == {"still_quality": 70, "interactive_quality": 70}
    assert (view.still_quality, view.interactive_quality) == (70, 70)
    assert image["encoding_applied"] == "jpeg"
    assert "NOT applied" in image["note"]
    assert "png" in image["note"]

    # A view that DOES take an encoding carries no note, and jpeg is the same
    # format the transport writes anyway, so nothing is being flattered.
    taken = _View(accepts_encoding=True)
    accepted = poc_app._apply_image_knobs(taken, "jpeg", 55)
    assert accepted["applied"] == {
        "still_quality": 55,
        "interactive_quality": 55,
        "image_encoding": "jpeg",
    }
    assert accepted["encoding_applied"] == "jpeg"
    assert accepted["note"] is None

    # No view at all costs both knobs, not the page.
    nothing = poc_app._apply_image_knobs(None, "png", 70)
    assert nothing["applied"] == {}
    assert nothing["encoding_applied"] == "jpeg"
    assert "NOT applied" in nothing["note"]


# ---------------------------------------------------------------------------
# The derived lines: ticks turned into an answer about the target rate.
# ---------------------------------------------------------------------------


def test_the_rate_lines_turn_ticks_into_an_answer_about_the_target():
    """Ten ticks 0.1s apart against 24 fps: 11.11 paints/s is 46.3% of the cap."""
    rows = [{"t": index * 0.1, "wall_ms": 50.0} for index in range(10)]
    lines = poc_app._profile_rate_lines(rows, 24)

    assert lines[0] == (
        "target: fps=24 frame=41.67 ms  painted=10 over 0.90 s  "
        "paints/s=11.11 vs cap 24.00 (46.3% of target)"
    )
    assert lines[1] == "over one frame period: 10 of 10 ticks (100.0%)"


def test_the_rate_lines_count_only_the_ticks_that_overran_one_frame():
    """A tick faster than the frame period is shown, not dropped: 0 of 10."""
    rows = [{"t": index * 0.1, "wall_ms": 10.0} for index in range(10)]
    lines = poc_app._profile_rate_lines(rows, 24)

    assert lines[0] == (
        "target: fps=24 frame=41.67 ms  painted=10 over 0.90 s  "
        "paints/s=11.11 vs cap 24.00 (46.3% of target)"
    )
    assert lines[1] == "over one frame period: 0 of 10 ticks (0.0%)"


def test_with_no_target_rate_there_is_nothing_to_compare_against():
    """No --fps recorded (or a nonsense one): no lines, rather than a fake rate."""
    rows = [{"t": 0.0, "wall_ms": 10.0}]
    assert poc_app._profile_rate_lines(rows, None) == []
    assert poc_app._profile_rate_lines(rows, 0) == []
    assert poc_app._profile_rate_lines(rows, "fast") == []


def test_the_summary_header_names_the_picture_and_the_knobs(prof, renderer):
    """A number is only an answer beside the picture and the knobs that made it."""
    prof.run.tick(frame=0)
    poc_app._profile_knobs(fps=24, msaa=8, image_encoding="png", image_quality=70)
    window = _Window(
        caps="OpenGL vendor string: Mesa/X.org\n"
        "OpenGL renderer string: llvmpipe (LLVM 15.0.7)\n"
        "OpenGL version string: 4.5\n",
        never=0,
    )
    poc_app._renderer_report(plotter=_Reported(window), msaa=8)

    lines = poc_app._profile_summary_text().splitlines()
    assert lines[0].startswith("poc_app --profile summary  run=")
    assert lines[1].startswith("ticks=1")
    assert lines[2] == (
        "renderer: gl=software vendor=Mesa/X.org renderer=llvmpipe (LLVM 15.0.7) "
        "version=4.5"
    )
    assert "pixels=1024x768" in lines[3]
    assert "plotter multi_samples=8" in lines[3]
    assert lines[4] == (
        "knobs: fps=24 msaa=8 image_encoding=png image_quality=70"
    )
    assert lines[5].startswith("target: fps=24 frame=41.67 ms  painted=")
    assert lines[6].startswith("over one frame period: ")
    assert lines[7] == "phases (ms): phase       n     p50     p95     max"


# ---------------------------------------------------------------------------
# ONE draw and ONE push per tick.
# ---------------------------------------------------------------------------


class _CallbackPlotter(_Plotter):
    """A plotter carrying pyvista's render-callback container.

    pyvista iterates that container at the END of ``render()``, so a fake that
    holds it but does not run it still poses the question the tick must answer:
    will somebody else push this frame, or must we?
    """

    def __init__(self, callbacks=()):
        super().__init__()
        self._on_render_callbacks = set(callbacks)


class _ViewHandle:
    """A trame remote view, reduced to the one call a tick makes on it."""

    def __init__(self, explode=False):
        self.updates = 0
        self.explode = explode

    def update(self):
        self.updates += 1
        if self.explode:
            raise RuntimeError("boom")


class _RefusingPlotter(_Plotter):
    """A plotter whose draw throws: a tick has to survive that."""

    def render(self):
        self.renders += 1
        raise RuntimeError("no GL")


class _DrawingPlotter(_Reported):
    """A plotter that has REALLY drawn once its ``render()`` has run.

    ``GetNeverRendered()`` is the flag ``_gl_capabilities`` obeys, so a fake that
    clears it on ``render()`` reproduces the ONLY sequence in which the GL strings
    are safe to ask for: after a draw.
    """

    def __init__(self, window):
        super().__init__(window)
        self.renders = 0

    def render(self):
        self.renders += 1
        self.render_window.never = 0
        return "rendered"


def test_a_tick_with_a_view_renders_nothing_of_its_own():
    """Trame renders the frame the view update asks for: a second draw is waste.

    ``PublishImageDelivery.still_render`` calls the app's ``StillRenderToString``
    (publish_image_delivery.py:196) and stamps the reply with
    ``GetLastStillRenderToMTime()`` (:218), so ``view.update()`` IS the render.
    A ``plotter.render()`` in front of it drew the same picture twice into a
    window nobody reads - and, where pyvista's render callback ships the result,
    encoded and sent it twice as well.
    """
    for plotter in (_CallbackPlotter(callbacks=[lambda *args: None]),
                    _CallbackPlotter(), _Plotter()):
        view = _ViewHandle()
        assert poc_app._tick_render_and_push(plotter, view) is True
        assert plotter.renders == 0, "the view update already renders this frame"
        assert view.updates == 1, "exactly one image leaves the server per tick"


def test_the_render_callback_question_no_longer_decides_anything():
    """Kept as a plain fact: the tick stopped asking it, so either answer is fine.

    ``_plotter_pushes_on_render`` is retained (and still answers), but the tick no
    longer branches on it: with a view trame owns the render whatever the callback
    container holds, so the same one-update-no-local-render path runs for both.
    """
    assert poc_app._plotter_pushes_on_render(
        _CallbackPlotter(callbacks=[lambda *args: None])
    ) is True
    assert poc_app._plotter_pushes_on_render(_CallbackPlotter()) is False


def test_a_tick_with_no_view_handle_still_draws():
    """A headless page: the draw happens and there is simply nothing to push."""
    plotter = _Plotter()
    assert poc_app._tick_render_and_push(plotter, None) is True
    assert plotter.renders == 1


def test_a_tick_with_nothing_to_push_counts_no_push(prof):
    """``calls:`` counts images that left the server, not ticks that ran.

    No view and no render callback means nothing was sent, so a push recorded
    here would be an image the client never received - and, being the number the
    tick rate is read against, a lie.
    """
    plotter = _Plotter()
    poc_app._profile_tick_begin(0, "ycut")
    assert poc_app._tick_render_and_push(plotter, None) is True
    poc_app._profile_tick_end(0, plotter=plotter, mode="ycut")

    assert plotter.renders == 1, "the draw still happened"
    assert "push" not in poc_app._PROFILE["rows"][0]["counts"]
    assert "calls: render=0 push=0 add_mesh=0 remove_actor=0" in (
        poc_app._profile_summary_text()
    )


def test_a_push_that_raises_is_swallowed_and_reported(capsys):
    """A trame update that throws costs the frame, never the tick.

    False, not True: with a view there is no local render to fall back on, so a
    tick whose only image failed painted nothing and must not be counted as one.
    """
    plotter = _Plotter()
    view = _ViewHandle(explode=True)
    assert poc_app._tick_render_and_push(plotter, view) is False
    assert view.updates == 1
    assert plotter.renders == 0
    assert "view update skipped: boom" in capsys.readouterr().err


def test_a_render_that_raises_is_swallowed_and_reported(capsys):
    """False is the honest answer: the report above the tick must not claim a draw.

    The raising draw is the HEADLESS path - with a view there is no local render
    to fail, because trame's still render is the one that draws.
    """
    plotter = _RefusingPlotter()
    assert poc_app._tick_render_and_push(plotter, None) is False
    assert "render skipped: no GL" in capsys.readouterr().err


def test_a_view_that_raises_still_reports_no_render(capsys):
    """With a view the local render never ran, so a failed update is the whole tick."""
    plotter = _RefusingPlotter()
    assert poc_app._tick_render_and_push(plotter, _ViewHandle(explode=True)) is False
    assert plotter.renders == 0
    assert "view update skipped: boom" in capsys.readouterr().err


def test_the_tick_row_and_the_summary_count_the_push(prof):
    """One push per tick, counted once, where the decision is made."""
    plotter = _CallbackPlotter(callbacks=[lambda *args: None])
    poc_app._profile_tick_begin(0, "ycut")
    poc_app._tick_render_and_push(plotter, _ViewHandle())
    poc_app._profile_tick_end(0, plotter=plotter, mode="ycut")

    # ``render`` is 0 here because that counter lives on the wrapper _show
    # installs around the plotter, which this tick did not; the push is counted
    # in the tick instead, so it reads 1 whether the image went out inside
    # render() or through an explicit update(). The SITE tag rides along: one
    # push, named once - the total and the name are not two different images.
    assert poc_app._PROFILE["rows"][0]["counts"] == {"push": 1, "push:show": 1}
    summary = poc_app._profile_summary_text()
    assert "calls: render=0 push=1 add_mesh=0 remove_actor=0" in summary
    assert "push_by_site: show=1" in summary


def test_every_still_is_named_by_the_control_that_asked_for_it(prof):
    """A still is counted ONCE, and it is also NAMED - the two are the same image.

    The failure this rules out is the one that raised the question: a run painted
    600 ticks and reported 1330 deliveries, because a push made from a control
    handler (a cut slider, a station change, a mode choice) never went through
    ``_show`` and so was never counted at all. Every still now leaves through
    ``_push_still``, which bumps the total AND the site, so the breakdown can be
    read as an accounting of the total - not a second, unrelated table.
    """
    view = _ViewHandle()
    poc_app._profile_tick_begin(0, "ycut")
    poc_app._tick_render_and_push(_Plotter(), view, "play")
    poc_app._tick_render_and_push(_Plotter(), view, "play")
    poc_app._push_still(view, "cut")
    poc_app._profile_tick_end(0, plotter=_Plotter(), mode="ycut")

    counts = poc_app._PROFILE["rows"][0]["counts"]
    assert view.updates == 3, "each still reached the view once"
    assert counts["push"] == 3
    assert counts["push:play"] == 2, (
        "the two play ticks are named as the play loop's own, not folded into a "
        f"single anonymous total: {counts!r}"
    )
    assert counts["push:cut"] == 1, (
        "the cut slider pushed a picture and was counted nowhere before: "
        f"{counts!r}"
    )
    assert counts["push"] == sum(
        value for name, value in counts.items() if name.startswith("push:")
    ), f"the sites do not add up to the push total: {counts!r}"


def test_a_still_with_no_view_is_named_nowhere(prof):
    """Nobody to send to is not a push: the total and the breakdown both stay empty.

    A headless tick renders locally and pushes nothing, so a site name there would
    claim a delivery that never happened - and the summary says ``none`` rather
    than dropping the line, because an absent line reads as a suite that cannot
    measure sites at all.
    """
    assert poc_app._push_still(None, "play") is False
    assert poc_app._push_still(None, "cut") is False
    assert poc_app._PROFILE["counts"].get("push", 0) == 0
    assert not [
        name
        for name in poc_app._PROFILE["counts"]
        if name.startswith("push:")
    ], "a site was named for a push that never left the server"
    assert "push_by_site: none" in poc_app._profile_summary_text()


def test_the_site_breakdown_is_busiest_first(prof):
    """The summary leads with the control that shipped the most stills."""
    view = _ViewHandle()
    for _ in range(3):
        poc_app._push_still(view, "play")
    poc_app._push_still(view, "cut")
    poc_app._push_still(view, "seek")

    line = [
        text
        for text in poc_app._profile_summary_text().splitlines()
        if text.startswith("push_by_site: ")
    ]
    assert line == ["push_by_site: play=3 cut=1 seek=1"], (
        f"the breakdown is not the busiest site first: {line!r}"
    )


def test_a_failed_still_is_named_neither(prof, capsys):
    """A view that throws shipped nothing, so no site may claim it did."""
    assert poc_app._push_still(_ViewHandle(explode=True), "play") is False
    assert "view update skipped: boom" in capsys.readouterr().err
    assert poc_app._PROFILE["counts"].get("push", 0) == 0
    assert "push_by_site: none" in poc_app._profile_summary_text()


def test_the_report_is_said_once_and_only_after_a_frame_really_drew(capsys, renderer):
    """A queued draw is not a rendered one: nothing is said, and nothing is burnt."""
    window = _Window(
        caps="OpenGL vendor string: Mesa/X.org\n"
        "OpenGL renderer string: llvmpipe (LLVM 15.0.7)\n"
        "OpenGL version string: 4.5\n",
        never=1,
    )
    plotter = _DrawingPlotter(window)
    image = poc_app._apply_image_knobs(_View(), None, 55)
    handles = {"renderer_image": image, "renderer_msaa": 8}

    # Boot: nothing has drawn, so there is nothing to say and the caps are NOT read.
    poc_app._renderer_report(plotter=plotter, image=image, msaa=8)
    assert poc_app._RENDERER["gl_mode"] == "unknown"
    assert window.caps_reads == 0

    # The same tick as the first push: the view only QUEUED the draw, so the
    # window is still unrendered and the report must wait rather than say
    # "gl=unknown" and burn its one shot (that is the bug this covers).
    assert poc_app._renderer_report_after_render(plotter, handles) is False
    assert capsys.readouterr().out == ""
    assert "renderer_reported" not in handles, "the one shot was burnt unspent"
    assert window.caps_reads == 0

    # The first tick really draws, and then the report is said - once.
    assert poc_app._tick_render_and_push(plotter, None) is True
    assert poc_app._renderer_report_after_render(plotter, handles) is True
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2, "one report line, and one shout for the CPU rasteriser"
    assert out[0].startswith("[poc_app] renderer: gl=software")
    assert "vendor=Mesa/X.org" in out[0]
    assert "renderer=llvmpipe (LLVM 15.0.7)" in out[0]
    assert "pixels=1024x768" in out[0]
    assert "msaa requested=8 applied=8" in out[0]
    assert "quality=55" in out[0]
    assert "not been rendered" not in out[0]
    assert out[1].startswith("[poc_app] WARNING: software rasteriser")
    assert "llvmpipe (LLVM 15.0.7)" in out[1]
    assert window.caps_reads == 1

    # The second tick is silent, and does not ask the window for its caps again.
    poc_app._tick_render_and_push(plotter, None)
    assert poc_app._renderer_report_after_render(plotter, handles) is False
    assert capsys.readouterr().out == ""
    assert window.caps_reads == 1


def test_the_second_report_names_a_direct_gl_renderer(capsys, renderer):
    """The mode word is what a log is scanned for: a real driver says direct."""
    window = _Window(
        caps="OpenGL vendor string: NVIDIA Corporation\n"
        "OpenGL renderer string: NVIDIA GeForce RTX 3070/PCIe/SSE2\n"
        "OpenGL version string: 4.6.0 NVIDIA 535.104.05\n",
        never=1,
    )
    plotter = _DrawingPlotter(window)
    # The stash the boot site makes: the second reading must quote the SAME msaa
    # request, so a report that says "default" here would be a lost knob.
    handles = {"renderer_msaa": 4}
    poc_app._renderer_report(plotter=plotter, msaa=4)
    assert poc_app._RENDERER["gl_mode"] == "unknown"

    assert poc_app._tick_render_and_push(plotter, None) is True
    assert poc_app._renderer_report_after_render(plotter, handles) is True
    line = capsys.readouterr().out
    assert line.startswith("[poc_app] renderer: gl=direct")
    assert "vendor=NVIDIA Corporation" in line
    assert "msaa requested=4 applied=8" in line
    assert "WARNING" not in line, "a real driver earns no shout"


def test_a_boot_report_that_already_knew_is_not_said_again(capsys, renderer):
    """Nothing to add: a window that had drawn at boot already answered."""
    window = _Window(
        caps="OpenGL vendor string: Mesa/X.org\n"
        "OpenGL renderer string: llvmpipe (LLVM 15.0.7)\n"
        "OpenGL version string: 4.5\n",
        never=0,
    )
    poc_app._renderer_report(plotter=_Reported(window), msaa=8)
    assert poc_app._RENDERER["gl_mode"] == "software"

    handles = {}
    assert poc_app._renderer_report_after_render(_Reported(window), handles) is False
    assert capsys.readouterr().out == ""
    assert handles["renderer_reported"] is True, "the flag still guards later ticks"



# ---------------------------------------------------------------------------
# The image-delivery path: what trame was asked to ship, and what it did.
#
# The tick block above can only see OUR loop. The other half of a frame's
# journey happens inside vtkWebPublishImageDelivery, which decides for itself
# whether an update becomes an encoded still and DROPS the update outright while
# a view is animating. Nothing here imports trame_vtk: a fake class with the same
# five methods is wrapped, so a failure names the bookkeeping and not a server.
# ---------------------------------------------------------------------------

_DELIVERY_IMAGE = b"jpeg-still" * 10


class _Delivery:
    """vtkWebPublishImageDelivery, reduced to the five calls the suite watches.

    ``tracking_views`` and ``views_in_animations`` are the two pieces of STATE
    that decide whether a push reaches the encoder or is thrown away, so they are
    plain attributes a test can move. The five methods only remember that they
    ran and hand back a sentinel - which is how delegation is checked.
    """

    IMAGE = _DELIVERY_IMAGE
    tracking_views = {"v1": {"enabled": True, "quality": 100}}

    def __init__(
        self,
        animated=False,
        fps=30.0,
        clock=None,
        still_ms=0.0,
        image=_DELIVERY_IMAGE,
        explode=False,
    ):
        self.views_in_animations = {"v1": True} if animated else {}
        self.target_frame_rate = fps
        self.clock = clock
        self.still_ms = float(still_ms)
        self.image = image
        self.explode = explode
        self.seen = []

    def push_render(self, v_id, ignore_animation=False, stale_count=0):
        self.seen.append(("push_render", v_id, ignore_animation))
        return "pushed"

    def still_render(self, options):
        self.seen.append(("still_render", options))
        if self.clock is not None:
            self.clock["t"] += self.still_ms / 1000.0
        if self.explode:
            raise RuntimeError("encoder died")
        return {"image": self.image, "format": "jpeg"}

    def animate(self):
        self.seen.append(("animate",))
        return "animated"

    def start_view_animation(self, view_id="-1"):
        self.seen.append(("start_view_animation", view_id))
        return "started"

    def stop_view_animation(self, view_id="-1"):
        self.seen.append(("stop_view_animation", view_id))
        return "stopped"


def _wrapped(base=_Delivery, **kwargs):
    """A FRESH subclass with the wrappers installed, instantiated.

    The subclass is what makes the idempotence claim truthful: the wrapped marker
    lives on the class, so wrapping ``_Delivery`` itself would leave every later
    test looking at an already-wrapped class.
    """
    klass = type("_DeliveryUnderTest", (base,), {})
    assert poc_app._profile_wrap_delivery(klass) is True
    return klass(**kwargs)


def test_the_wrappers_count_each_call_and_still_delegate(prof):
    """Every wrapped method forwards, returns what it got, AND is counted once."""
    delivery = _wrapped()
    assert poc_app._profile_wrap_delivery(type(delivery)) is True, "idempotent"
    assert poc_app._profile_wrap_delivery(type(delivery)) is True

    assert delivery.push_render("v1") == "pushed"
    assert delivery.still_render({"quality": 90})["image"] == _Delivery.IMAGE
    assert delivery.animate() == "animated"
    assert delivery.start_view_animation() == "started"
    assert delivery.stop_view_animation() == "stopped"

    push = poc_app._PROFILE["push"]
    assert push["attempts"] == 1, "the second wrap must not count the same call twice"
    assert push["rendered"] == 1
    assert poc_app._PROFILE["still"]["n"] == 1
    assert poc_app._PROFILE["animate"]["calls"] == 1
    client = poc_app._PROFILE["client"]
    assert (client["animation_start"], client["animation_stop"]) == (1, 1)
    # The delegate really ran: the fake remembers its own calls, in order.
    assert delivery.seen == [
        ("push_render", "v1", False),
        ("still_render", {"quality": 90}),
        ("animate",),
        ("start_view_animation", "-1"),
        ("stop_view_animation", "-1"),
    ]


def test_every_dropped_push_is_attributed_to_its_own_reason(prof):
    """The three early returns of push_render, replayed: no drop is anonymous."""
    delivery = _wrapped()

    assert delivery.push_render("nope") == "pushed"  # untracked view
    delivery.tracking_views = {"v1": {"enabled": False, "quality": 100}}
    delivery.push_render("v1")  # disabled view
    delivery.tracking_views = {"v1": {"enabled": True, "quality": 100}}
    delivery.views_in_animations = {"v1": True}
    delivery.push_render("v1")  # a view is animating: trame drops it
    delivery.push_render("v1", ignore_animation=True)  # ... unless asked for

    push = poc_app._PROFILE["push"]
    assert push["attempts"] == 4
    assert push["dropped_untracked"] == 1
    assert push["dropped_disabled"] == 1
    assert push["dropped_animation"] == 1
    assert push["rendered"] == 1


def test_a_still_records_its_encode_time_and_the_bytes_it_carried(prof):
    """A still is a measured encode, not just a count: ms AND payload size."""
    delivery = _wrapped(clock=prof.clock, still_ms=37.5, image=b"z" * 1234)
    reply = delivery.still_render({"quality": 100})

    still = poc_app._PROFILE["still"]
    assert reply["image"] == b"z" * 1234
    assert still["n"] == 1
    assert still["ms"] == pytest.approx([37.5])
    assert still["total_ms"] == pytest.approx(37.5)
    assert still["bytes"] == [1234]
    assert still["total_bytes"] == 1234

    # A reply with NO image has no size: counted as a still, never as 0 bytes.
    delivery.image = None
    assert delivery.still_render({})["image"] is None
    assert still["n"] == 2
    assert still["bytes"] == [1234]
    assert still["total_bytes"] == 1234


def test_a_still_that_raises_still_reports_the_time_it_took(prof):
    """A still that took 12 ms and then failed is not a still that took no time."""
    delivery = _wrapped(clock=prof.clock, still_ms=12.0, explode=True)
    with pytest.raises(RuntimeError, match="encoder died"):
        delivery.still_render({})

    still = poc_app._PROFILE["still"]
    assert still["n"] == 1
    assert still["ms"] == pytest.approx([12.0])
    assert still["total_bytes"] == 0


def test_animate_records_the_target_rate_and_the_animated_span(prof):
    """``in_animation_s`` is the wall time BETWEEN animate() calls, while animating."""
    delivery = _wrapped(animated=True, fps=24.0, clock=prof.clock)
    delivery.animate()  # the baseline: no span to add yet

    anim = poc_app._PROFILE["animate"]
    assert anim["calls"] == 1
    assert anim["last_target_fps"] == pytest.approx(24.0)
    assert anim["in_animation_s"] == pytest.approx(0.0)

    prof.run.advance(500.0)  # 0.5 s in which every unasked push was dropped
    delivery.animate()
    assert anim["calls"] == 2
    assert anim["in_animation_s"] == pytest.approx(0.5)

    # A delivery whose views are NOT animating adds no animated span.
    idle = _wrapped(animated=False, fps=12.0, clock=prof.clock)
    idle.animate()
    prof.run.advance(500.0)
    idle.animate()
    assert anim["in_animation_s"] == pytest.approx(0.5)
    assert anim["calls"] == 4
    assert anim["last_target_fps"] == pytest.approx(12.0)


def test_an_interaction_edge_is_told_apart_from_an_animation(prof):
    """A drag the USER started is not an animation a client asked for over the wire."""

    delivery = _wrapped(clock=prof.clock)

    def start_callback():  # the name vtkWebPublishImageDelivery registers
        return delivery.start_view_animation()

    def stop_callback():
        return delivery.stop_view_animation()

    assert start_callback() == "started"
    prof.run.advance(100.0)
    assert stop_callback() == "stopped"
    prof.run.advance(100.0)
    assert delivery.start_view_animation() == "started"  # an RPC, not an observer
    assert delivery.stop_view_animation() == "stopped"

    client = poc_app._PROFILE["client"]
    assert client["start_interaction"] == 1
    assert client["end_interaction"] == 1
    assert client["animation_start"] == 1
    assert client["animation_stop"] == 1
    assert [event["kind"] for event in client["events"]] == [
        "start_interaction",
        "end_interaction",
        "animation_start",
        "animation_stop",
    ]
    assert client["events"][1]["t"] == pytest.approx(0.1)


def test_a_tick_row_carries_what_the_delivery_did_during_it(prof):
    """The row reports the DELTA of the run's delivery totals, not the total."""
    delivery = _wrapped(fps=30.0, clock=prof.clock, still_ms=20.0)

    poc_app._profile_tick_begin(0, "ycut")
    delivery.push_render("v1")  # reaches the encoder
    delivery.still_render({})  # 20 ms of encode, inside this tick
    prof.run.advance(10.0)
    poc_app._profile_tick_end(0, plotter=None, mode="ycut")

    row = poc_app._PROFILE["rows"][0]
    assert row["push_attempts"] == 1
    assert row["push_rendered"] == 1
    assert row["push_dropped_animation"] == 0
    assert row["still_ms"] == pytest.approx(20.0)
    assert row["in_animation_s"] == pytest.approx(0.0)

    poc_app._profile_tick_begin(1, "ycut")
    delivery.views_in_animations = {"v1": True}
    delivery.push_render("v1")  # DROPPED: a view is animating
    delivery.animate()
    prof.run.advance(250.0)
    delivery.animate()
    poc_app._profile_tick_end(1, plotter=None, mode="ycut")

    row = poc_app._PROFILE["rows"][1]
    assert row["push_attempts"] == 1
    assert row["push_rendered"] == 0
    assert row["push_dropped_animation"] == 1
    assert row["still_ms"] == pytest.approx(0.0), "no still was encoded this tick"
    assert row["in_animation_s"] == pytest.approx(0.25)

    # A tick that touched neither reports zeros, not the run's running total.
    poc_app._profile_tick_begin(2, "ycut")
    poc_app._profile_tick_end(2, plotter=None, mode="ycut")
    row = poc_app._PROFILE["rows"][2]
    assert row["push_attempts"] == 0
    assert row["still_ms"] == pytest.approx(0.0)
    assert row["in_animation_s"] == pytest.approx(0.0)


def test_the_summary_names_the_delivery_and_every_edge(prof):
    """Four lines beside ``calls:``, plus one line per edge while the list is short."""
    delivery = _wrapped(
        animated=True, fps=24.0, clock=prof.clock, still_ms=5.0, image=b"q" * 800
    )

    def start_callback():
        return delivery.start_view_animation()

    start_callback()
    delivery.still_render({})
    delivery.push_render("v1")  # dropped_animation: a view is animating
    poc_app._PROFILE["push"]["available"] = True

    text = poc_app._profile_summary_text()
    assert (
        "push: attempts=1 rendered=0 dropped_animation=1 dropped_untracked=0 "
        "dropped_disabled=0 available=yes"
    ) in text
    assert "still: n=1 p50=" in text
    assert "bytes_total=800" in text
    assert "animate: calls=0 last_target_fps=default in_animation_s=0.000" in text
    assert "client: events=1 start_interaction=1 end_interaction=0" in text
    assert "animation_start=0 animation_stop=0" in text
    assert "first_t=0.000 last_t=0.000" in text
    assert "ev t=0.000 kind=start_interaction" in text

    # Unhooked is said, not implied: the same run reports available=no.
    poc_app._PROFILE["push"]["available"] = False
    assert "available=no" in poc_app._profile_summary_text()


def test_per_event_lines_stop_when_the_session_gets_long(prof):
    """Thousands of drags would bury the summary: the counts above still say how many."""
    for index in range(poc_app._PROFILE_DELIVERY_MAX_EVENTS + 1):
        poc_app._profile_client_record("animation_start", now=index * 0.5)

    text = poc_app._profile_summary_text()
    assert "ev t=" not in text
    assert "client: events=41" in text
    assert "animation_start=41" in text


def test_without_trame_vtk_the_hook_says_so_and_never_raises(prof, monkeypatch):
    """An image without the delivery has no counters to watch; the run is not lost."""
    monkeypatch.setitem(
        sys.modules, "trame_vtk.modules.vtk.protocols.publish_image_delivery", None
    )

    assert poc_app._profile_hook_delivery() is False
    assert poc_app._PROFILE["delivery_hooked"] is False
    assert poc_app._PROFILE["push"]["available"] is False
    text = poc_app._profile_summary_text()
    assert "push: attempts=0 rendered=0 dropped_animation=0" in text
    assert "available=no" in text


def test_a_wrapped_delivery_records_nothing_while_the_suite_is_off(tmp_path):
    """Off is off even for an INSTALLED wrapper: it forwards, and counts nothing."""
    poc_app._profile_configure(False)
    poc_app._profile_reset()

    delivery = _wrapped(animated=True, still_ms=9.0)
    assert delivery.push_render("v1") == "pushed"
    assert delivery.still_render({})["image"] == _Delivery.IMAGE
    assert delivery.animate() == "animated"
    assert delivery.start_view_animation() == "started"
    assert delivery.stop_view_animation() == "stopped"

    assert poc_app._PROFILE["push"]["attempts"] == 0
    assert poc_app._PROFILE["still"]["n"] == 0
    assert poc_app._PROFILE["animate"]["calls"] == 0
    assert poc_app._PROFILE["client"]["events"] == []
    assert poc_app._profile_summary_text() == ""



def test_a_wrapper_keeps_the_marker_wslink_finds_its_rpcs_by(prof):
    """The RPC URIs live in the method's own __dict__: the wrapper must carry them."""

    class _Rpc(_Delivery):
        def start_view_animation(self, view_id="-1"):
            return "started"

    _Rpc.start_view_animation._wslinkuris = [
        {"uri": "viewport.image.animation.start"}
    ]
    klass = type("_RpcUnderTest", (_Rpc,), {})
    assert poc_app._profile_wrap_delivery(klass) is True

    wrapped = klass.start_view_animation
    assert wrapped is not _Rpc.start_view_animation, "the class attribute is wrapped"
    assert wrapped.__dict__["_wslinkuris"] == [
        {"uri": "viewport.image.animation.start"}
    ], "an unregistered RPC is a broken app, not a lost counter"
    # And the base class it was reading from is untouched.
    assert _Rpc.start_view_animation.__dict__["_wslinkuris"]


# ---------------------------------------------------------------------------
# POC_TICK_STALL: WHICH tick stalled, and what was running when it did.
#
# The two suites above answer "how long did this tick take" and "where did that
# time go on average".  This probe answers the operator's question instead -
# WHICH tick was it, and was the second spent re-anchoring, drawing, flushing,
# or in a gc nothing else here can see.  The claims, one per test:
#
# * off is a HARD no-op: no gc hook, no record, no file, every hook inert -
#   a run that never asked for the probe pays nothing for it;
# * ``1`` is how one writes ON, so anything above it is a threshold in ms, and
#   an unreadable value falls back to the default rather than crashing;
# * a slow tick prints ONE field=value line - also appended to the run's log -
#   naming its phases, its gc, its render/push counts and its frame;
# * the lines are BOUNDED while every slow tick is still counted, so a run that
#   stalls on every tick cannot bury itself in stderr;
# * a gc pause is measured INTO the tick that paid for it, from gc.callbacks,
#   which is the one sample no phase mark can see;
# * the summary is <= 40 lines - per-phase percentiles, gc per GENERATION, and
#   the worst ticks - and the file IS that text, in the run directory.
# ---------------------------------------------------------------------------


@pytest.fixture
def stall(tmp_path, monkeypatch):
    """The stall probe on, on the same fake clock, in its own run directory."""
    saved_threshold = poc_app._STALL["threshold_ms"]
    monkeypatch.setenv("POC_TICK_STALL", "1")
    poc_app._profile_configure(False)
    poc_app._stall_uninstall_gc()
    poc_app._profile_reset()
    clock = {"t": 0.0}
    run = tmp_path / "stall"
    # _profile_configure installs the probe: it is the block that takes the
    # marks this one rides, so POC_TICK_STALL alone must not claim to be on.
    poc_app._profile_configure(
        True, run, clock=lambda: clock["t"], start_threads=False
    )
    try:
        yield types.SimpleNamespace(
            clock=clock,
            run=_Run(clock),
            dir=run,
            summary=run / "poc_tick_stall.txt",
            log=run / "poc_tick_stall.log",
        )
    finally:
        poc_app._profile_configure(False)
        poc_app._stall_uninstall_gc()
        poc_app._stall_reset()
        poc_app._STALL["threshold_ms"] = saved_threshold
        poc_app._PROFILE["files"] = {}


def test_the_stall_probe_is_off_unless_asked(tmp_path, monkeypatch):
    """No POC_TICK_STALL: no hook, no record, no file - and every hook inert."""
    monkeypatch.delenv("POC_TICK_STALL", raising=False)
    poc_app._profile_configure(False)
    poc_app._stall_uninstall_gc()
    poc_app._stall_reset()

    assert poc_app._stall_env_enabled() is False
    assert poc_app._stall_install_gc() is False, "the env is the ONLY switch"
    assert poc_app._stall_enabled() is False
    assert poc_app._stall_tick_begin(0, "ycut") is None
    assert poc_app._stall_phase("draw", 999.0) is None
    assert poc_app._stall_tick_end({"counts": {"render": 1}}) is None
    assert poc_app._stall_gc_stop({"generation": 0}) == 0.0
    assert poc_app._stall_summary_text() == ""
    assert poc_app._stall_write_summary() == ""
    assert poc_app._STALL["ticks"] == 0
    assert poc_app._STALL["slow"] == 0
    assert poc_app._STALL["worst"] == []

    # And a configured run that did not ask still leaves not one file behind.
    off = tmp_path / "off"
    poc_app._profile_configure(True, off, start_threads=False)
    try:
        assert poc_app._STALL["enabled"] is False
        assert sorted(p.name for p in off.iterdir()) == []
    finally:
        poc_app._profile_configure(False)


def test_the_env_value_is_the_threshold_not_just_a_switch(monkeypatch):
    """"1" is how one writes ON; anything above it is a threshold in ms."""
    assert poc_app._STALL_DEFAULT_MS == pytest.approx(150.0)
    for raw, want in (
        ("1", 150.0),        # on, at the default
        ("400", 400.0),      # on, at 400 ms
        ("12.5", 12.5),      # fractional ms is a number, not a mistake
        ("yes", 150.0),      # unreadable: the default, never a crash
        ("", 150.0),         # blank is off, but still a readable default
        ("  ", 150.0),
    ):
        monkeypatch.setenv("POC_TICK_STALL", raw)
        assert poc_app._stall_env_threshold() == pytest.approx(want), raw
    for raw in ("", "0", "   "):
        monkeypatch.setenv("POC_TICK_STALL", raw)
        assert poc_app._stall_env_enabled() is False, raw
    monkeypatch.setenv("POC_TICK_STALL", "1")
    assert poc_app._stall_env_enabled() is True


def test_a_slow_tick_prints_one_line_naming_what_it_did(stall, capsys):
    """One field=value line, in a fixed order, to stderr AND to the run's log."""
    poc_app._STALL["threshold_ms"] = 100.0

    poc_app._profile_tick_begin(7, "xcut")
    for name, ms in (("reanchor", 20.0), ("draw", 210.0), ("flush", 5.0)):
        stall.run.advance(ms)
        poc_app._profile_phase(name)
    # The counts a tick row carries are what the line reports: the probe reads
    # the ROW, so it cannot disagree with the profile suite about that tick.
    poc_app._PROFILE["tick_counts"] = {"render": 1, "push": 1}
    poc_app._profile_tick_end(7, mode="xcut")

    record = poc_app._STALL["worst"][0]
    assert record["n"] == 1
    assert record["total_ms"] == pytest.approx(235.0)
    assert record["slow"] is True
    assert poc_app._STALL["slow"] == 1

    text = capsys.readouterr().err.strip()
    assert text.startswith("[poc_app] slow tick 1/1"), text
    for field in (
        "total=235.0ms",
        "threshold=100.0ms",
        "gc=0.0ms",
        "frame=7",
        "mode=xcut",
        "reanchor=20.0ms",
        "draw=210.0ms",
        "flush=5.0ms",
        "render=1",
        "push=1",
    ):
        assert field in text, (field, text)
    # The gap is the beat BEFORE this tick; the first tick has none, and an
    # invented 0.0 would read as a loop that never slept.
    assert "gap=" not in text, text
    # The log is the same one line, in the run directory and nowhere else.
    assert _lines(stall.log) == [text]


def test_a_run_that_stalls_every_tick_suppresses_lines_but_counts_every_tick(stall, capsys):
    """A probe that buries stderr is a probe an operator turns off."""
    poc_app._STALL["threshold_ms"] = 1.0
    assert poc_app._STALL_MAX_LINES == 200

    poc_app._profile_tick_begin(0, "ycut")
    for frame in range(205):
        if frame:
            poc_app._profile_tick_begin(frame, "ycut")
        stall.run.advance(5.0)
        poc_app._profile_phase("draw")
        poc_app._profile_tick_end(frame, mode="ycut")

    assert poc_app._STALL["ticks"] == 205
    assert poc_app._STALL["slow"] == 205, "every slow tick is COUNTED"
    assert poc_app._STALL["lines_printed"] == 200
    assert poc_app._STALL["lines_suppressed"] == 5
    assert len(capsys.readouterr().err.strip().splitlines()) == 200
    # Worst-first and bounded: the 20 slowest records survive the run.
    assert len(poc_app._STALL["worst"]) == poc_app._STALL_MAX_WORST
    assert all(rec["slow"] for rec in poc_app._STALL["worst"])
    # The 200-tick beat rewrote the summary without anyone asking for it.
    assert stall.summary.exists()
    assert "ticks: 200" in stall.summary.read_text(encoding="utf-8")
    assert "ticks: 205" in poc_app._stall_write_summary()


def test_a_gc_pause_lands_inside_the_tick_that_paid_for_it(stall):
    """gc.callbacks is the one sample no phase mark can see, so it is hooked."""
    import gc as _gc

    assert poc_app._STALL["gc_hooked"] is True
    was_enabled = _gc.isenabled()
    _gc.disable()  # a REAL collection mid-test would steal the manual start
    try:
        poc_app._profile_tick_begin(0, "ycut")
        poc_app._stall_gc_callback("start", {"generation": 0})
        stall.run.advance(4.0)  # 4 ms of gc inside a tick that did nothing else
        poc_app._stall_gc_callback("stop", {"generation": 0})
        poc_app._profile_tick_end(0, mode="ycut")
    finally:
        if was_enabled:
            _gc.enable()

    record = poc_app._STALL["worst"][0]
    assert record["total_ms"] == pytest.approx(4.0)
    assert record["gc_ms"] == pytest.approx(4.0), "the pause is INSIDE the tick"
    agg = poc_app._STALL["gc"][0]
    assert agg["n"] == 1
    assert agg["total_ms"] == pytest.approx(4.0)
    assert agg["max_ms"] == pytest.approx(4.0)
    assert poc_app._STALL["gc_ms_total"] == pytest.approx(4.0)
    # Nested collections keep the outer start rather than double-counting it.
    poc_app._stall_gc_callback("start", {"generation": 2})
    started = poc_app._STALL["gc_t0"]
    poc_app._stall_gc_callback("start", {"generation": 2})
    assert poc_app._STALL["gc_t0"] == started
    # Unhooking is idempotent, and the probe is off either way.
    assert poc_app._stall_uninstall_gc() is True
    assert poc_app._stall_uninstall_gc() is False
    assert poc_app._stall_enabled() is False


def test_the_summary_names_the_phases_the_generations_and_the_worst_ticks(stall):
    """<= 40 lines: per-phase percentiles, gc per generation, the worst ticks."""
    import gc as _gc

    poc_app._STALL["threshold_ms"] = 100.0
    stall.run.tick(frame=1, phases=(("draw", 210.0),))
    stall.run.tick(frame=2, phases=(("draw", 400.0),))

    was_enabled = _gc.isenabled()
    _gc.disable()
    try:
        poc_app._stall_gc_callback("start", {"generation": 0})
        stall.run.advance(2.0)
        poc_app._stall_gc_callback("stop", {"generation": 0})
    finally:
        if was_enabled:
            _gc.enable()

    text = poc_app._stall_summary_text()
    lines = text.splitlines()
    assert lines[0] == "POC_TICK_STALL - slow-tick probe"
    assert len(lines) <= 40
    assert "ticks: 2  slow(>=100.0ms): 2  lines suppressed: 0" in text
    assert "phase (ms)" in text
    assert any(line.startswith("  draw") for line in lines), text
    # gc is per GENERATION: "gen0" alone would hide a gen2 pause entirely.
    assert any(line.startswith("  gen0") for line in lines), text
    assert "worst ticks:" in text
    # Worst FIRST, so the tick worth reading is the one at the top.
    worst_rows = [line for line in lines if line.strip()[:1] in ("1", "2")]
    assert worst_rows, text
    assert "400.0" in worst_rows[0], worst_rows[0]
    assert "210.0" in worst_rows[1], worst_rows[1]

    # The file IS that text, in the run directory - never the source tree.
    assert poc_app._stall_write_summary() == text
    assert stall.summary.read_text(encoding="utf-8") == text
    assert poc_app._stall_path() == stall.summary
    assert poc_app._stall_log_path() == stall.log
