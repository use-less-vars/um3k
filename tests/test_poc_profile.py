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
  cannot be read is reported as pending, not guessed.
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
    assert "calls: render=2 add_mesh=2 remove_actor=2" in poc_app._profile_summary_text()


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
    """Ten ticks 0.1s apart against 24 fps: 11.11 ticks/s is 46.3% of the target."""
    rows = [{"t": index * 0.1, "wall_ms": 50.0} for index in range(10)]
    lines = poc_app._profile_rate_lines(rows, 24)

    assert lines[0] == (
        "target: fps=24 frame=41.67 ms  achieved=11.11 ticks/s (46.3% of target)"
    )
    assert lines[1] == "over one frame period: 10 of 10 ticks (100.0%)"


def test_the_rate_lines_count_only_the_ticks_that_overran_one_frame():
    """A tick faster than the frame period is shown, not dropped: 0 of 10."""
    rows = [{"t": index * 0.1, "wall_ms": 10.0} for index in range(10)]
    lines = poc_app._profile_rate_lines(rows, 24, elapsed=1.0)

    assert lines[0] == (
        "target: fps=24 frame=41.67 ms  achieved=10.00 ticks/s (41.7% of target)"
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
    assert lines[5].startswith("target: fps=24 frame=41.67 ms  achieved=")
    assert lines[6].startswith("over one frame period: ")
    assert lines[7] == "phases (ms): phase       n     p50     p95     max"
