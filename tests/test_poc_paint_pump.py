"""The paint pump: one painted frame, one stride, and no render behind trame's.

The play loop used to advance the position on every TICK (a wall-clock target),
and every tick rendered twice - once itself, once through trame's image
delivery.  The pump decouples the two clocks: a position advances by a STRIDE
per PAINTED frame (``_play_stride``/``_play_advance``), a frame is painted at
most ``paint_fps`` times a second (``paint_every``), and with a view attached the
tick renders NOTHING of its own because ``PublishImageDelivery.still_render``
already calls ``StillRenderToString`` (publish_image_delivery.py:196) and stamps
it with ``GetLastStillRenderToMTime()`` (:218).

Nothing here boots the viewer or touches OpenGL: the helpers are called
directly, the tick runs against fakes, and the loop's structure is read off its
own AST, so a failure names the arithmetic rather than a rendering nobody can
inspect in this image.

Section (i) is the ONE exception, and it is here rather than in a new file
because it is about the same loop: the scrub hold is a DEADLINE the pump consults
on its next beat, so "nothing was published while the hand was down" is a claim
about time passing with the real ``_play_loop`` task running, and no direct call
can show it. It boots the page through the playback harness, which doubles the
GL draw and the client push and nothing else.
"""

from __future__ import annotations

import ast
import asyncio
import math
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # The same two entries every other poc_app test adds, so `import poc_app`
        # resolves from server/poc_app.py.
        sys.path.insert(0, _p)

import poc_app as app  # noqa: E402  (sys.path above is why this import is not at the top)


def _paint_every(fps, paint_fps):
    """The module's own duty arithmetic, repeated here so it cannot drift silently."""
    return max(1, int(math.ceil(max(1, int(fps)) / max(1, int(paint_fps)))))


# ---------------------------------------------------------------------------
# a) The stride a painted frame carries.
# ---------------------------------------------------------------------------


def test_the_stride_is_the_rate_at_the_default_base():
    """At the default stride the offered multipliers ARE the steps per frame."""
    for rate in (1, 2, 4, 8):
        assert app._play_stride(app.DEFAULT_PLAY_STRIDE, rate) == rate


def test_the_stride_multiplies_the_base_the_run_was_started_with():
    """--stride 8 at rate 1 is the same positions/s as --stride 4 at rate 2."""
    assert app.DEFAULT_PLAY_STRIDE == 4
    assert app._play_stride(8, 1) == 2
    assert app._play_stride(8, 2) == 4
    assert app._play_stride(8, 8) == 16


def test_the_boot_stride_is_the_users_stride():
    """At boot no rate is known yet, and the default rate is 4: 4*4/4 == 4.

    So `--stride N` is what a page opened at rest paints per frame - the value
    cannot drift by a rounding step at the one moment nobody is watching it.
    """
    import math as _m

    for base in (1, 2, 3, 4, 8):
        assert app._play_stride(base, app.DEFAULT_PLAY_RATE) == base, base
        assert _m.isclose(base * app.DEFAULT_PLAY_RATE / 4.0, base)
    assert app._play_stride(1, 4) == 1
    assert app._play_stride(2, 4) == 2
    assert app._play_stride(4, 4) == 4


def test_a_single_position_family_never_advances_to_a_bad_frame():
    """frames 0/1 must give a real index, not -1 and not NaN."""
    for frames in (0, 1, None):
        for stride in (1, 4, 999):
            got = app._play_advance(0, stride, frames)
            assert isinstance(got, int), got
            assert got == 0, (frames, stride, got)


def test_the_stride_never_reaches_zero():
    """A stride below one whole position would freeze the player at a still."""
    assert app._play_stride(1, 1) == 1
    assert app._play_stride(1, 2) == 1
    for junk in (None, "x", 0, -3, True if False else 0):
        assert app._play_stride(junk, 1) >= 1
        assert app._play_stride(app.DEFAULT_PLAY_STRIDE, junk) >= 1


# ---------------------------------------------------------------------------
# b) The advance one painted frame makes, wrapped by the family length.
# ---------------------------------------------------------------------------


def test_a_painted_frame_advances_by_the_stride_and_wraps():
    assert app._play_advance(10, 4, 240) == 14
    assert app._play_advance(238, 4, 240) == 2, "the loop the player loops"


def test_a_page_with_no_timeline_advances_within_its_single_position():
    for frames in (0, None, "junk", -5):
        assert app._play_advance(0, 4, frames) == 0


def test_an_unusable_stride_still_advances_one_position():
    assert app._play_advance(5, 0, 240) == 6
    assert app._play_advance(5, -3, 240) == 6


# ---------------------------------------------------------------------------
# c) The tick: one update with a view, one local render without it.
# ---------------------------------------------------------------------------


class _Plotter:
    """A plotter reduced to the one call a tick makes on it."""

    def __init__(self):
        self.renders = 0

    def render(self):
        self.renders += 1
        return "rendered"


class _View:
    """A trame remote view, reduced to the one call a tick makes on it."""

    def __init__(self):
        self.updates = 0

    def update(self):
        self.updates += 1


def test_a_tick_with_a_view_updates_once_and_renders_nothing(monkeypatch):
    """The view update IS the render: a local one would draw the same picture twice."""
    counted = []
    monkeypatch.setitem(app._PROFILE, "enabled", True)
    monkeypatch.setattr(app, "_profile_count", counted.append)

    plotter, view = _Plotter(), _View()
    assert app._tick_render_and_push(plotter, view) is True
    assert plotter.renders == 0, "trame rendered this frame; we drew it again"
    assert view.updates == 1
    # ONE push, counted as the total AND named by the site that asked for it: the
    # default site is ``show``, so a caller that names nothing is still attributed
    # (see _push_still and the summary's push_by_site line) - not counted twice.
    assert counted == ["push", "push:show"], counted


def test_a_tick_with_no_view_renders_itself_and_pushes_nothing(monkeypatch):
    """Headless: nobody will ask for the image, so the local draw IS the picture."""
    counted = []
    monkeypatch.setitem(app._PROFILE, "enabled", True)
    monkeypatch.setattr(app, "_profile_count", counted.append)

    plotter = _Plotter()
    assert app._tick_render_and_push(plotter, None) is True
    assert plotter.renders == 1
    assert counted == [], "no image left the server, so no call is counted"


# ---------------------------------------------------------------------------
# d) The loop's structure, read off its own AST.
# ---------------------------------------------------------------------------


def _named_funcs(tree, name):
    # ``_play_loop`` is an ``async def``, i.e. an ``AsyncFunctionDef``.
    kinds = (ast.FunctionDef, ast.AsyncFunctionDef)
    return [node for node in ast.walk(tree) if isinstance(node, kinds)
            and node.name == name]


def test_the_play_loop_advances_by_the_pump_and_not_by_the_clock():
    tree = ast.parse(Path(app.__file__).read_text(encoding="utf-8"))
    loops = _named_funcs(tree, "_play_loop")
    assert len(loops) == 1, f"{len(loops)} _play_loop definitions"
    loop = loops[0]

    called = {
        node.func.id
        for node in ast.walk(loop)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    for helper in ("_play_stride", "_play_advance", "_play_reanchor",
                   "_play_rate_near", "_delivery_animating"):
        assert helper in called, f"the loop does not call {helper}"
    assert "_play_target" not in called, (
        "the loop still integrates a wall-clock target: a tick that painted "
        "nothing would advance the position anyway"
    )
    assert "render" not in called, "the loop renders for itself; _show owns the tick"


def test_the_paint_cap_gate_comes_before_the_advance():
    """A skipped tick must not reach the advance: that is the whole pump."""
    tree = ast.parse(Path(app.__file__).read_text(encoding="utf-8"))
    loop = _named_funcs(tree, "_play_loop")[0]

    gate_continues = []
    for node in ast.walk(loop):
        if not isinstance(node, ast.If):
            continue
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        mods = [n for n in ast.walk(node.test) if isinstance(n, ast.BinOp)
                and isinstance(n.op, ast.Mod)]
        if "paint_every" in names and mods:
            gate_continues += [n.lineno for n in ast.walk(node)
                               if isinstance(n, ast.Continue)]
    assert gate_continues, "no `(tick - 1) % paint_every` gate in the loop"

    advance = [node.lineno for node in ast.walk(loop)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "_play_advance"]
    assert advance, "the loop never advances a position"
    assert min(gate_continues) < min(advance), (
        "the paint-cap gate does not skip the advance: a tick that paints "
        "nothing still moves the position"
    )


# ---------------------------------------------------------------------------
# e) The delivery question (None when it cannot be answered).
# ---------------------------------------------------------------------------


class _Delivery:
    def __init__(self, views=None):
        self.views_in_animations = [] if views is None else views


class _Unmeasurable:
    class _Bad:
        def __len__(self):
            raise RuntimeError("nope")

    views_in_animations = _Bad()


def test_no_delivery_object_yet_is_not_an_answer(monkeypatch):
    monkeypatch.setattr(app, "_DELIVERY_INSTANCE", None)
    assert app._delivery_animating() is None


def test_a_delivery_animating_a_view_is_animating(monkeypatch):
    delivery = _Delivery()
    monkeypatch.setattr(app, "_DELIVERY_INSTANCE", delivery)
    assert app._delivery_animating() is False
    delivery.views_in_animations.append("v1")
    assert app._delivery_animating() is True
    delivery.views_in_animations.clear()
    assert app._delivery_animating() is False


def test_an_unreadable_view_list_is_not_an_answer(monkeypatch):
    """A renamed attribute or a list that will not measure must not stop playback."""
    monkeypatch.setattr(app, "_DELIVERY_INSTANCE", object())
    assert app._delivery_animating() is None
    monkeypatch.setattr(app, "_DELIVERY_INSTANCE", _Unmeasurable())
    assert app._delivery_animating() is None


# ---------------------------------------------------------------------------
# f) The wrapping remembers the delivery with the suite OFF.
# ---------------------------------------------------------------------------


class _PublishImageDelivery:
    def __init__(self):
        self.views_in_animations = []

    def push_render(self, *args, **kwargs):
        return "pushed"

    def still_render(self, *args, **kwargs):
        return "still"

    def animate(self, *args, **kwargs):
        return "animated"

    def start_view_animation(self, *args, **kwargs):
        return "started"

    def stop_view_animation(self, *args, **kwargs):
        return "stopped"


def test_a_wrapped_delivery_is_remembered_even_with_the_suite_off(monkeypatch):
    """The pump asks with --profile off too, so the remembering cannot be gated."""
    monkeypatch.setitem(app._PROFILE, "enabled", False)
    monkeypatch.setattr(app, "_DELIVERY_INSTANCE", None)

    wrapped = type("_WrappedDelivery", (_PublishImageDelivery,), {})
    assert app._profile_wrap_delivery(wrapped) is True

    delivery = wrapped()
    assert delivery.push_render("v1") == "pushed"
    assert app._DELIVERY_INSTANCE is delivery, "the pump never saw the delivery"

    assert app._delivery_animating() is False
    delivery.views_in_animations.append("v1")
    assert app._delivery_animating() is True

    # Every wrapped method remembers, not just push_render: a still or an
    # animation start is the first call of a session often enough.
    other = wrapped()
    other.start_view_animation()
    assert app._DELIVERY_INSTANCE is other
    # And nothing was COUNTED: the suite is off.
    assert app._PROFILE["push"]["attempts"] == 0
    assert app._PROFILE["client"]["events"] == []


# ---------------------------------------------------------------------------
# g) Duty: paint_every never paints more often than the cap, never less often
#    than the frame rate needs, and the positions/s are rate * fps.
# ---------------------------------------------------------------------------


def test_the_paint_cap_turns_the_tick_rate_into_a_paint_interval():
    assert _paint_every(24, 24) == 1
    assert _paint_every(24, 12) == 2
    assert _paint_every(24, 8) == 3
    assert _paint_every(25, 10) == 3, "ceil: painting 2 of 25 would exceed 10/s"
    # A cap above the frame rate is not an instruction to paint more often.
    assert _paint_every(24, 60) == 1


def test_the_positions_per_second_do_not_depend_on_the_paint_cap():
    """The speed select means the same thing at every cap: stride grows, rate does not."""
    for paint_fps in (24, 12, 8):
        for rate in (1, 2, 4, 8):
            stride = app._play_stride(app.DEFAULT_PLAY_STRIDE, rate)
            assert stride * paint_fps == rate * 24 * (paint_fps / 24)
    for rate in (1, 2, 4, 8):
        assert app._play_stride(app.DEFAULT_PLAY_STRIDE, rate) * 24 == rate * 24


def test_the_default_duty_is_one_and_a_capped_run_is_one_in_paint_every():
    """fps=24/paint_fps=24 -> every tick paints; fps=24/paint_fps=8 -> one in three."""
    default_every = _paint_every(24, 24)
    assert default_every == 1
    assert 1.0 / default_every == pytest.approx(1.0)

    capped_every = _paint_every(24, 8)
    assert capped_every == 3
    assert (1.0 / capped_every) == pytest.approx(1.0 / 3.0)


# ---------------------------------------------------------------------------
# h) The boot notice: the speed select collapses at small strides.
# ---------------------------------------------------------------------------


def test_the_offered_speeds_are_distinct_only_with_a_big_enough_stride():
    """The strides are anchored at rate 4, so the select needs room to differ."""
    at_default = [app._play_stride(app.DEFAULT_PLAY_STRIDE, rate) for rate in app.PLAY_RATES]
    assert at_default == [1, 2, 4, 8]
    assert len(set(at_default)) == len(app.PLAY_RATES), "the default lost a speed"

    at_one = [app._play_stride(1, rate) for rate in app.PLAY_RATES]
    assert at_one == [1, 1, 1, 2]
    assert len(set(at_one)) < len(app.PLAY_RATES), "stride 1 is the collision to warn about"


def test_the_collapsed_speed_notice_names_the_collision_and_stays_silent_at_the_default():
    """One line, naming the rates that did nothing and the stride that fixes it."""
    notice = app._stride_collision_notice(1)
    assert notice, "stride 1 collapses three speeds and said nothing"
    assert notice.startswith("[poc_app]")
    assert "\n" not in notice, "one boot line, not a block"
    assert "--stride" in notice
    assert str(app.DEFAULT_PLAY_STRIDE) in notice, "it must name the stride to raise to"
    assert "1, 2 and 4" in notice, "it must name the rates that collided"
    assert "1 position per painted frame" in notice

    assert app._stride_collision_notice(app.DEFAULT_PLAY_STRIDE) == "", "the default is fine"

    # 2 is 1, 1, 2, 4: two speeds, not four, and it says which two.
    two = app._stride_collision_notice(2)
    assert two and "1 and 2" in two
    assert "1, 2 and 4" not in two, "only the rates that actually collided"

    # 3 is 1, 2, 3, 6 - every rate its own stride, so there is nothing to say.
    assert app._stride_collision_notice(3) == ""



# ---------------------------------------------------------------------------
# i) The scrub hold: the pump stands off the timeline while a hand is on it.
#
# The one section that boots the page (see the module docstring).  Everything is
# still the shipped code - the same ``handles`` dict the frame listener stamps and
# the play loop reads, the same ``@ctrl.set("frame_scrub_end")`` the slider's
# ``end`` event calls - and only the GL draw and the client push are doubled.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _the_volume_layer_is_on():
    """Boot this module's page with the same switch the playback harness uses.

    ``SHOW_VOLUME_LAYER_DEFAULT`` (server/poc_app.py:892) keeps the 3-D |E| volume
    off the page, and the playback module turns it on for the page it asserts on.
    The boot below happens HERE, under this module's fixtures, so the same opt-in
    has to be in place or the page is not the one the harness's own tests proved.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(app, "SHOW_VOLUME_LAYER_DEFAULT", True)
        yield


@pytest.fixture(scope="module")
def harness():
    """The playback harness, imported HERE so sections a) - h) still run without it.

    ``tests/test_poc_playback.py`` skips itself at import when pyvista or trame is
    missing, and it is the module that knows how to boot the page with a doubled
    draw.  Importing it at module scope would skip this whole file - including the
    forty tests that need neither - so the import lives inside the fixture.
    """
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        # test_poc_playback.py is a test module, not a package member: it is
        # importable only from its own directory.
        sys.path.insert(0, here)
    return pytest.importorskip(
        "test_poc_playback",
        reason="the scrub hold can only be watched with the real play loop running",
    )


@pytest.fixture(scope="module")
def scrub_page(tmp_path_factory, harness):
    """The animation page on the timeline the clock tests need (``CLOCK_FRAMES``).

    The four-position dump would not do: one tick advances four positions, so a
    seek, the loop's own clock and a snap-back to it would all sit on the same
    number and no assertion could tell them apart.
    """
    yield from harness._playback_page(tmp_path_factory, frames=harness.CLOCK_FRAMES)


def _counts() -> dict:
    """A copy of the run's counters, so a delta is two reads and not one alias."""
    return dict(app._PROFILE.get("counts") or {})


def _drawn(page) -> int:
    """How many times the picture has been pushed to the screen."""
    return len(page.renders) + len(page.view_updates)


def _seek(page, listener, position) -> None:
    """Send one operator scrub, the way trame dispatches a client's change.

    The listener is called DIRECTLY, for the reason test_poc_playback.py:670
    gives: this harness never enters trame's event loop, so ``state.flush()``
    dispatches nothing and a flush-only seek would prove nothing.
    """
    page.state.frame = position
    page.state.flush()
    listener(frame=position)


async def _start_playing(page, harness):
    """Press play and hand back the ONE loop task the press scheduled."""
    tasks_before = harness._other_tasks()
    await asyncio.wait_for(page.trigger(), timeout=harness.RETURN_TIMEOUT_S)
    created = harness._other_tasks() - tasks_before
    assert len(created) == 1, (
        f"the play press scheduled {len(created)} tasks, expected exactly 1"
    )
    return created.pop()


async def _stop_playing(page, harness, task) -> None:
    """Pause, and be sure the loop is gone before the next scenario measures."""
    if not task.done() and page.state.playing:
        await asyncio.wait_for(page.trigger(), timeout=harness.RETURN_TIMEOUT_S)
    await harness._drain([task])


def _restore(page, was_frame) -> None:
    """Put the page back at rest, so no scenario can inherit the last one's hold."""
    page.handles["scrub_until"] = None
    page.handles["play_echo_frame"] = None
    page.state.playing = False
    page.state.frame = was_frame
    page.state.flush()


async def _sample_positions(state, seconds):
    """Every value ``state.frame`` takes over the next ``seconds``."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    seen = []
    while loop.time() < deadline:
        seen.append(int(state.frame))
        await asyncio.sleep(0.002)
    return seen


async def _watch_ahead(state, origin, frames, seconds):
    """Each sample as (distance AHEAD of ``origin``, when it was taken).

    The WHEN is the loop clock the sample was read at, so a scenario can say not
    only that the pump moved but after how long it did - which is the whole of
    the hold's claim on one side and of the release's on the other.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    seen = []
    while loop.time() < deadline:
        seen.append(((int(state.frame) - origin) % frames, loop.time()))
        await asyncio.sleep(0.002)
    return seen


def test_a_scrub_stops_the_pump_until_the_window_runs_out(scrub_page, harness):
    """A seek mid-playback is the picture, and the pump publishes nothing after it.

    The report this pins is the mirror image of the one the playback tests pin:
    the seek now reaches the picture, but a pump that keeps drawing its own clock
    over it would still fight the hand - one still render per mouse move, which
    looks exactly like "the scrubber does nothing while it plays".
    """
    page = scrub_page
    frames = int(page.state.frame_max) + 1

    async def scenario() -> None:
        state = page.state
        assert state.playing is False, "boot already left the page playing"
        was_frame = int(state.frame)
        task = await _start_playing(page, harness)
        try:
            # Four ticks at 25 fps: the loop is past its first beat, so the
            # position it would publish next is a real one and not the boot value.
            await asyncio.sleep(4 * (1.0 / harness.FPS))
            clock = int(state.frame)
            # Half a sweep away from the loop's own clock: a tick carries four
            # positions, so "the seek" and "the clock" cannot be the same number.
            seek = (clock + frames // 2) % frames
            _seek(page, harness._frame_listener(state), seek)
            drawn = _drawn(page)
            seen = await _sample_positions(state, 0.2)
            assert seen, "the sampler saw nothing at all"
            assert all(value == seek for value in seen), (
                f"the pump published over an operator's scrub: the position was "
                f"put at {seek} and moved to {sorted(set(seen))} while the hand "
                "was still on the control"
            )
            assert _drawn(page) == drawn, (
                f"{_drawn(page) - drawn} paint(s) happened during a held scrub: "
                "the seek drew itself, so these are a second picture of the same "
                "position and the drag is competing with the pump"
            )
        finally:
            await _stop_playing(page, harness, task)
            _restore(page, was_frame)

    asyncio.run(scenario())


def test_the_pump_carries_on_from_the_seek_and_never_from_its_own_clock(
    scrub_page, harness
):
    """When the hold runs out, playback resumes FROM the seek, not back over it.

    ``_play_reanchor`` is what makes resuming cost no code of its own: ``drawn``
    still names the loop's own last paint, ``state.frame`` names the operator's,
    so the difference IS the seek and it becomes the new clock origin.  The bound
    on the distance is what tells that from a drag back: the pre-seek clock sits
    exactly half a sweep ahead in modular terms, so a loop that resumed from its
    own clock would read ``frames // 2`` or more.

    Two claims share one window, and each is pinned by a different part of it.
    The LOWER bound on the onset pins the hold: nothing may be published before
    ``SCRUB_HOLD_S`` has run out, because a pump still on the timeline is a pump
    fighting the hand.  Everything else in the window pins the RESUME - that it
    happened at all, that it started one stride from the operator's position and
    that it never climbed to the loop's own pre-seek clock.
    """
    page = scrub_page
    frames = int(page.state.frame_max) + 1

    async def scenario() -> None:
        state = page.state
        assert state.playing is False, "boot already left the page playing"
        was_frame = int(state.frame)
        task = await _start_playing(page, harness)
        try:
            await asyncio.sleep(4 * (1.0 / harness.FPS))
            clock = int(state.frame)
            seek = (clock + frames // 2) % frames
            at_seek = asyncio.get_running_loop().time()
            _seek(page, harness._frame_listener(state), seek)
            # The hold plus 0.12 s: at 100 positions/s that is at most twelve
            # positions of resumed playback, i.e. three strides.
            ahead = await _watch_ahead(
                state, seek, frames, app.SCRUB_HOLD_S + 0.12
            )
            moving = [(offset, when) for offset, when in ahead if offset]
            assert moving, (
                "the pump never published again after the hold ran out: the "
                f"position sat at {seek} for {app.SCRUB_HOLD_S + 0.12}s of a "
                "running playback"
            )
            # THE LOWER BOUND PINS THE HOLD. The clock is read at the seek, so
            # this is how long the position stood still, i.e. how long the pump
            # respected the hand. 50 ms of slack is the sampling step times the
            # cost of reading the clock, not tolerance for a shorter hold.
            onset = moving[0][1] - at_seek
            assert onset >= app.SCRUB_HOLD_S - 0.05, (
                f"playback published {onset:.3f}s after the seek, inside the "
                f"{app.SCRUB_HOLD_S}s hold: the seek did not stop the pump, it "
                "only drew over it"
            )
            assert 1 <= moving[0][0] <= 12, (
                f"the first publish after the hold was {moving[0][0]} positions "
                "past the operator's position; one stride is 4, so playback "
                "either jumped or resumed somewhere other than the seek"
            )
            assert all(offset < frames // 2 for offset, _when in ahead), (
                f"the pump ran up to {max(offset for offset, _when in ahead)} "
                f"positions past the seek, which includes the loop's own "
                f"pre-seek clock ({frames // 2} ahead of it): playback carried "
                "on from its clock instead of from the position the operator "
                "left"
            )
        finally:
            await _stop_playing(page, harness, task)
            _restore(page, was_frame)

    asyncio.run(scenario())


def test_every_new_seek_re_stamps_the_hold(scrub_page, harness):
    """A drag is a BURST of seeks: the last one decides when the hold ends.

    The stamp is a deadline, not a flag, so the second seek has to move it. The
    first stamp is left to run out 0.1 s INTO the window sampled below, so a hold
    that was not re-stamped is a hold that lets the pump back on the timeline
    with the hand still down.
    """
    page = scrub_page
    frames = int(page.state.frame_max) + 1

    async def scenario() -> None:
        state = page.state
        assert state.playing is False, "boot already left the page playing"
        was_frame = int(state.frame)
        task = await _start_playing(page, harness)
        try:
            await asyncio.sleep(4 * (1.0 / harness.FPS))
            listener = harness._frame_listener(state)
            clock = int(state.frame)
            first = (clock + frames // 2) % frames
            _seek(page, listener, first)
            # A quarter of the 0.5 s hold: the first stamp expires 0.1 s into the
            # 0.35 s window below, i.e. while it is still being sampled.
            await asyncio.sleep(0.25)
            second = (first + frames // 8) % frames
            _seek(page, listener, second)
            seen = await _sample_positions(state, 0.35)
            assert seen, "the sampler saw nothing at all"
            assert all(value == second for value in seen), (
                f"the hold left by the FIRST seek of the drag: the position was "
                f"moved to {second} and the pump took it to "
                f"{sorted(set(seen))} with the hand still on the control"
            )
        finally:
            await _stop_playing(page, harness, task)
            _restore(page, was_frame)

    asyncio.run(scenario())


def test_a_held_beat_is_counted_as_a_scrub_hold_and_not_as_a_paint_cap(
    scrub_page, harness
):
    """A held beat is attributed to the hold, so the profile names the right bug.

    All three gates below the deadline sit on the same shape - count, yield,
    ``continue`` - and ``_PROFILE_GATE_COUNTS`` folds them onto the next written
    tick row.  A beat held by the operator's hand counted as ``paint_cap`` would
    send a reader tuning ``--paint-fps`` for a stand-off no cap setting causes.
    """
    page = scrub_page
    frames = int(page.state.frame_max) + 1

    async def scenario() -> None:
        state = page.state
        assert state.playing is False, "boot already left the page playing"
        was_frame = int(state.frame)
        task = await _start_playing(page, harness)
        try:
            await asyncio.sleep(4 * (1.0 / harness.FPS))
            clock = int(state.frame)
            seek = (clock + frames // 2) % frames
            _seek(page, harness._frame_listener(state), seek)
            # Let a beat that was already past the gate land before the baseline
            # is read: the only yield between the gate and the paint is a
            # sleep(0)/sleep(0.012), so nothing is still pending on this side of
            # the gate after 20 ms.
            await asyncio.sleep(0.02)
            before = _counts()
            await asyncio.sleep(0.2)  # ~5 beats at the 0.04 s period
            after = _counts()
            held = after.get("scrub_hold", 0) - before.get("scrub_hold", 0)
            assert held >= 3, (
                f"{held} held beat(s) counted in 0.2s of a held scrub, expected "
                "at least 3 of the 5 beats that period fits: the gate is not "
                "being reached, or it is not counting"
            )
            # The DUTY this page runs at: --paint-fps defaults to --fps, so
            # paint_every is 1 and the cap below the hold cannot fire at all.
            # That is exactly why a held beat must not be attributed to it.
            assert _paint_every(harness.FPS, harness.FPS) == 1
            # Both other gates are therefore UNREACHABLE at this duty - the cap's
            # `(tick - 1) % 1` is always 0, and delivery_hold needs a client
            # animation trame is not running here - so neither can be counted, and
            # neither says anything about this page. Only scrub_hold is asserted:
            # a count that CANNOT be non-zero would be a test of the harness, not
            # of the attribution this name promises.
            #
            # THE FIRST TICK ROW AFTER THE HOLD MUST NOT REPORT THE HOLD AS ITS
            # INTERVAL. `interval_ms` is the wall-clock gap since the previous
            # PAINTED tick (server/poc_app.py:16967-16971), and `_last_tick_at` is
            # only written on a painted tick - so a baseline left at the last
            # paint makes the first row after a hold claim ~SCRUB_HOLD_S of tick
            # interval, i.e. a deliberate stand-off logged as a stalled loop. The
            # gate resets that baseline beside its `t0` rebase, which is what this
            # reads: the resumed tick's own numbers, parked by _timing_play_tick
            # and moved onto the row as `interval_ms` (server/poc_app.py:1501).
            loop = asyncio.get_running_loop()
            deadline = loop.time() + app.SCRUB_HOLD_S + 0.4
            while loop.time() < deadline and int(state.frame) == seek:
                await asyncio.sleep(0.002)
            assert int(state.frame) != seek, (
                "playback never resumed after the hold, so no row was written "
                "after it to read"
            )
            interval = (app._TIMING.get("play") or {}).get("interval_ms")
            assert interval is None or interval < 0.5 * app.SCRUB_HOLD_S * 1000.0, (
                f"the first tick row after the hold reports an interval of "
                f"{interval} ms, which spans the {app.SCRUB_HOLD_S}s the pump "
                "was told to stand off: a reader tuning the loop against its "
                "period_ms would chase a stall nobody's machine had"
            )
        finally:
            await _stop_playing(page, harness, task)
            _restore(page, was_frame)

    asyncio.run(scenario())


def test_the_slider_end_event_lifts_the_hold_without_waiting_it_out(
    scrub_page, harness
):
    """The thumb coming up ends the hold now, not when ``SCRUB_HOLD_S`` is up.

    Without the lift, a released drag would keep the pump waiting for the rest of
    the window with nobody touching anything - the picture frozen after every
    scrub, for half a second, which is long enough to read as "it stuck".

    The deadline is stamped BY HAND here and NO seek is sent, so the release is
    the only thing that can end the hold: motion after it can only be the lift,
    and the first half of the window is the control that proves the stamp was
    standing before it was lifted. It also pins WHAT the release must not do - the
    position advances by exactly ONE stride from the last painted one, because
    ``anchor_frame`` is the loop's own last paint and ``_play_advance`` steps it
    once per painted frame. A hold that left a stale origin behind would resume
    with a burst of strides, i.e. playback cashing in the time it was told to
    stand off.
    """
    page = scrub_page
    frames = int(page.state.frame_max) + 1

    async def scenario() -> None:
        state, handles = page.state, page.handles
        assert state.playing is False, "boot already left the page playing"
        was_frame = int(state.frame)
        task = await _start_playing(page, harness)
        try:
            await asyncio.sleep(4 * (1.0 / harness.FPS))
            # The same deadline the frame listener stamps on a seek, written
            # here by hand: the release is then the ONLY thing that can end it.
            handles["scrub_until"] = time.monotonic() + app.SCRUB_HOLD_S
            held_at = int(state.frame)
            quiet = await _watch_ahead(state, held_at, frames, 0.15)
            assert all(offset == 0 for offset, _when in quiet), (
                "the pump published while the deadline was standing and nobody "
                f"was touching the control: positions went to "
                f"{sorted({offset for offset, _w in quiet})} ahead of {held_at}"
            )
            # Read AFTER the quiet window, so this is the last position the loop
            # itself painted - the one the release has to step away from.
            last = int(state.frame)
            assert last == held_at
            assert handles["scrub_until"] is not None, (
                "the deadline did not survive the quiet window, so there is "
                "nothing for the release to lift"
            )
            end = harness._registered_trigger(
                page.server.controller, "frame_scrub_end"
            )
            end()
            assert handles["scrub_until"] is None, (
                "the thumb's release left the deadline standing: playback stays "
                f"held for the rest of SCRUB_HOLD_S ({app.SCRUB_HOLD_S}s)"
            )
            # 0.25 s is a quarter of the window the stamp would have run for, so
            # motion here can only be the release having lifted the hold.
            resumed = await _watch_ahead(state, last, frames, 0.25)
            moving = [(offset, when) for offset, when in resumed if offset]
            assert moving, (
                "playback did not resume after the thumb was released: the "
                "hold is still standing with nothing touching the control"
            )
            one = app._play_stride(
                app.DEFAULT_PLAY_STRIDE,
                app._play_rate_near(
                    getattr(state, "play_rate", app.DEFAULT_PLAY_RATE)
                ),
            )
            assert moving[0][0] == one, (
                f"the first publish after the release was {moving[0][0]} "
                f"positions past the last painted one ({last}), expected one "
                f"stride ({one}): the release resumed from somewhere other "
                "than the position on screen, so it either jumped or burst to "
                "catch up on the hold"
            )
            assert all(offset < frames // 2 for offset, _when in resumed), (
                f"the pump ran up to "
                f"{max(offset for offset, _w in resumed)} positions past the "
                f"last painted one, which includes its own pre-hold clock "
                f"({frames // 2} ahead of it)"
            )
        finally:
            await _stop_playing(page, harness, task)
            _restore(page, was_frame)

    asyncio.run(scenario())


def test_the_scrub_gate_skips_the_beat_before_the_paint_cap_and_the_advance():
    """Read off the AST: the hold must skip the beat, not merely yield in it.

    A gate that waited and then fell through would still advance and paint, which
    is the behaviour the hold exists to stop - and one that had drifted BELOW the
    paint cap would let a capped beat reach the cap's counter first, so a held
    scrub would be reported as a repaint problem again.
    """
    tree = ast.parse(Path(app.__file__).read_text(encoding="utf-8"))
    loop = _named_funcs(tree, "_play_loop")[0]

    gates = []
    for node in ast.walk(loop):
        if not isinstance(node, ast.If):
            continue
        strings = {n.value for n in ast.walk(node.test)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if "scrub_until" in strings:
            gates.append(node)
    assert len(gates) == 1, f"{len(gates)} scrub gates in the play loop, expected 1"
    gate = gates[0]

    continues = [n.lineno for n in ast.walk(gate) if isinstance(n, ast.Continue)]
    assert continues, (
        "the scrub gate does not continue: a held beat falls through to the "
        "paint and the pump draws over the hand anyway"
    )

    caps = []
    for node in ast.walk(loop):
        if not isinstance(node, ast.If):
            continue
        if "paint_every" in {n.id for n in ast.walk(node.test)
                             if isinstance(n, ast.Name)}:
            caps.append(node)
    assert caps, "no `(tick - 1) % paint_every` gate in the loop"

    advance = [node.lineno for node in ast.walk(loop)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "_play_advance"]
    assert advance, "the loop never advances a position"
    assert min(continues) < min(node.lineno for node in caps), (
        "the scrub gate sits below the paint cap: a capped beat is then counted "
        "as a repaint before the hold is ever consulted"
    )
    assert min(continues) < min(advance), (
        "the scrub gate does not skip the advance: a held beat still moves the "
        "position the operator is holding"
    )

    # THE DEADLINE GRID IS REBASED INSIDE THE GATE, and the assertion is here
    # because removing it changes nothing a picture shows - `tick` keeps counting
    # through the hold, so the grid would run ahead by one period per held beat
    # and a released playback would burn the banked deadlines off in a burst of
    # fast frames, which only the RATE of resumed playback can reveal.
    rebase = [
        node for node in ast.walk(gate)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "t0"
                for target in node.targets)
    ]
    assert len(rebase) == 1, (
        f"{len(rebase)} `t0 = ...` statements inside the scrub gate, expected 1: "
        "without it the hold banks a period per beat and playback bursts "
        "through the banked deadlines on release"
    )
    value = rebase[0].value
    assert isinstance(value, ast.BinOp) and isinstance(value.op, ast.Sub), (
        "the rebase is not a SUBTRACTION (t0 = <clock> - <what tick counted>): "
        "the grid has to be moved back by the ticks the hold spent, not reset "
        "to an unrelated number"
    )
    assert any(
        isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult)
        and "tick" in {name.id for name in ast.walk(node)
                        if isinstance(name, ast.Name)}
        for node in ast.walk(value.right)
    ), (
        "the rebase does not undo the ticks the hold counted (`- tick * period`): "
        "tick keeps counting through the hold, so the grid would still run "
        "ahead by one period per held beat"
    )
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "time"
        for node in ast.walk(value.left)
    ), (
        "the rebase does not read the loop clock on the left (`loop.time() - ...`): "
        "the grid has to be put back where the WALL clock is, so it cannot be "
        "a constant or a value carried over from before the hold"
    )
    # THE CONDITION IS A CLOCK READ AGAINST THE STAMP: `time.monotonic()` on one
    # side of a comparison, `handles`' `scrub_until` on the other. Either half on
    # its own is a different bug - a stamp nobody compares holds forever, a clock
    # compared to a constant holds never - and both would pass the `continue`
    # check above while the hand is not being respected.
    assert isinstance(gate.test, ast.Compare), (
        "the scrub gate's condition is not a comparison, so it is not a deadline "
        "being read against the clock"
    )
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "monotonic"
        for node in ast.walk(gate.test)
    ), (
        "the gate does not read a monotonic clock: a wall-clock timestamp would "
        "step with the operator's timezone, and a loop clock would not be the "
        "one the listener stamped"
    )
    assert any(
        isinstance(node, ast.Constant) and node.value == "scrub_until"
        for node in ast.walk(gate.test)
    ), (
        "the gate does not read the `scrub_until` the seek stamps, so nothing a "
        "drag writes can ever hold the pump"
    )

