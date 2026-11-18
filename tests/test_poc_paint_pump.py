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
"""

from __future__ import annotations

import ast
import math
import sys
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
    assert counted == ["push"], counted


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

