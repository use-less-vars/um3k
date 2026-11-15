"""The layout builders: one function per column, and the seam they are called at.

``server/um3k_panels.py`` holds the page's layout as functions that take only
``ctx``, because a Trame widget attaches to the AMBIENT layout context - the
``with`` block live at the call site - so the position of a widget is decided by
whoever calls the builder, never by the builder. This file pins both halves:

* importing the module pulls in no trame and no pyvista, checked in a FRESH
  interpreter because this process has already loaded pytest;
* ``build_left_panel`` calls the ``_emit_solve_controls`` callback it was given,
  exactly once, and does nothing else;
* a context with nothing registered raises ``KeyError`` naming the missing
  callback AND what is registered instead - never a silent no-op, which would
  ship a left column with no solve controls in it;
* the seam in ``run_web_vis`` really moved: the 3-column row's left ``VCol``
  body is one call to ``build_left_panel(ctx)`` and its centre ``VCol`` body is
  ``view = build_center_panel(ctx)`` - parsed out of the source, not imported,
  because the layout only exists with the UI stack present - and the right
  column's body is one call to ``build_right_panel(ctx)``;
* the centre builder builds what it was given: called against recording fake
  widgets it constructs them in the order the column holds them, returns the
  view its own ``plotter_ui`` made, tolerates a widget table with no ``VBtn``,
  and refuses a context that is missing a handle instead of drawing nothing.
  or a tab widget it never probed;
* every page fixture DECLARES the kind it stands for through ``available=``,
  because a bare context computes the empty snapshot and so claims a field page
  by default: the centre fixture is explicitly the ANIMATION page whose player
  bar it builds, and a second fixture covers the field kind;
* the right builder builds what it was given: the readout strip, the three
  eager loaders ahead of any tab, five tabs whose values match five window
  items, the two ``info`` payloads handed to the load-series panel, and the
  stacked fallback when the optional tab classes are absent.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import um3k_context  # noqa: E402 - the path above is what makes it importable
import um3k_panels  # noqa: E402 - same two entries, same reason

POC_APP = REPO_ROOT / "server" / "poc_app.py"


def test_importing_the_module_pulls_in_no_ui_stack():
    """If this fails, the layout layer dragged trame or pyvista in on import.

    The point of the module is to be importable where the UI stack is absent,
    so the check runs in a FRESH interpreter: this process has already imported
    pytest (and whatever pytest loads), which would hide the module's own
    behaviour. A non-zero exit or a missing ``clean`` is the failure, and the
    child's stderr is printed so the offending import is named.
    """
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        f"sys.path.insert(0, {str(REPO_ROOT / 'server')!r})\n"
        "import um3k_panels\n"
        "assert 'trame' not in sys.modules, "
        "[m for m in sys.modules if m.startswith('trame')]\n"
        "assert 'pyvista' not in sys.modules, [m for m in sys.modules "
        "if m.startswith('pyvista')]\n"
        "print('clean')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=str(REPO_ROOT),
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"importing um3k_panels in a fresh interpreter failed\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "clean" in proc.stdout, (
        f"the child printed {proc.stdout!r} instead of clean\n"
        f"stderr:\n{proc.stderr}"
    )


# --- the page KIND every fixture below declares -------------------------------
# ``build_center_panel`` builds the player bar and the frame scrubber, and that
# furniture is the ANIMATION viewer's - it is the page that carries ``nt`` and
# scrubs it. ``PageContext()``, though, computes its snapshot from an EMPTY dump,
# which reports ``animation is False`` as well, so a centre fixture built that way
# claims a field page while the tests under it assert a vis player's controls.
# Each fixture therefore NAMES the kind it stands for - the same ``available=``
# idiom ``_fake_right_context`` already uses per test - so a snapshot and the
# assertions built on it cannot disagree without a test failing.
ANIMATION_PAGE = um3k_context.Available(animation=True, source_format="vis")
#: A field page holding none of the flagged data: the legacy (station, y, z)
#: dump, whose every :class:`um3k_context.Available` flag is false.
FIELD_PAGE = um3k_context.Available()


def _context(events=None):
    """A real page context whose one callback records that it was called.

    Declared a FIELD page, the kind this dump is: the SETUP column reads no
    snapshot at all, so the declaration is what keeps it from being a default.
    """
    ctx = um3k_context.PageContext(
        dump=um3k_context.LoadedDump(info={"nstep": 3, "nx": 2, "ny": 3, "nz": 4}),
    )
    ctx.available = FIELD_PAGE
    log = events if events is not None else []

    def _emit_solve_controls() -> None:
        log.append("emit")

    ctx.register("_emit_solve_controls", _emit_solve_controls)
    return ctx, log


def test_build_left_panel_calls_the_registered_callback_once():
    """If this fails, the SETUP column is built from something else entirely.

    The builder is allowed exactly one move: call what the page registered. A
    second call would build the controls twice into the same column, and no
    call at all is the silent empty left column this seam exists to prevent.
    """
    ctx, log = _context()

    um3k_panels.build_left_panel(ctx)

    assert log == ["emit"], (
        f"the builder called the solve-controls callback {log!r}, not once: it "
        f"must emit the page's own controls and nothing else"
    )


def test_build_left_panel_refuses_a_context_with_nothing_registered():
    """If this fails, an unregistered page draws a left column with no controls.

    ``PageContext.callback`` raises ``KeyError`` naming the missing name and
    what IS stored; the builder must not swallow that, because a swallowed
    KeyError is a page that looks built and is not.
    """
    bare = um3k_context.PageContext()
    bare.available = FIELD_PAGE  # kind: the refusal precedes any snapshot read

    with pytest.raises(KeyError) as excinfo:
        um3k_panels.build_left_panel(bare)

    message = str(excinfo.value)
    assert "_emit_solve_controls" in message
    assert "known" in message


def _with_calls(tree, name):
    """Every ``with <name>(...)`` block in ``tree``, in source order."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            expr = item.context_expr
            if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name)
                    and expr.func.id == name):
                found.append(node)
    return sorted(found, key=lambda node: node.lineno)


def _children(block, name):
    """The ``with <name>(...)`` statements DIRECTLY inside ``block``."""
    return [
        stmt for stmt in block.body
        if isinstance(stmt, ast.With) and any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Name)
            and item.context_expr.func.id == name
            for item in stmt.items
        )
    ]


def _run_web_vis():
    """``run_web_vis`` as source: the layout only exists with the UI stack."""
    tree = ast.parse(POC_APP.read_text(encoding="utf-8"))
    found = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_web_vis"
    ]
    assert len(found) == 1, (
        f"expected one top-level run_web_vis in {POC_APP}, found {len(found)}"
    )
    return found[0]


def _three_column_row():
    """The VRow whose children are the three columns, not the player bar."""
    rows = _with_calls(_run_web_vis(), "VRow")
    columns = [(row, _children(row, "VCol")) for row in rows]
    candidates = [(row, cols) for row, cols in columns if len(cols) == 3]
    assert len(candidates) == 1, (
        "the 3-column row is not identifiable: the VRows hold "
        f"{[len(cols) for _row, cols in columns]} VCol children each "
        f"(lines {[row.lineno for row, _cols in columns]})"
    )
    return candidates[0][1]


def test_the_left_column_is_one_call_to_the_panel_builder():
    """If this fails, the solve controls are still built inline in the layout.

    One statement, and it is ``build_left_panel(ctx)``: anything more means the
    column's contents were not moved, and a second statement would be content
    the panel module does not own.
    """
    left = _three_column_row()[0]

    assert len(left.body) == 1, (
        f"the left VCol holds {len(left.body)} statements; the panel builder is "
        f"supposed to be all of them"
    )
    stmt = left.body[0]
    assert isinstance(stmt, ast.Expr), f"the left VCol's statement is {stmt!r}"
    call = stmt.value
    assert isinstance(call, ast.Call), f"the left VCol's expression is {call!r}"
    assert isinstance(call.func, ast.Name) and call.func.id == "build_left_panel", (
        f"the left VCol calls {ast.dump(call.func)[:80]}"
    )
    assert len(call.args) == 1 and isinstance(call.args[0], ast.Name), (
        f"build_left_panel takes {len(call.args)} positional argument(s)"
    )
    assert call.args[0].id == "ctx", f"the panel is handed {call.args[0].id!r}"
    assert not call.keywords, f"build_left_panel got keywords {call.keywords!r}"


def test_the_centre_column_is_one_call_to_the_panel_builder():
    """If this fails, the picture and its player bar are built inline again.

    One statement, and it is ``view = build_center_panel(ctx)``: the builder
    returns the view its own ``plotter_ui`` made, and the page stores that in
    ``handles["view"]`` after the layout closes. Anything more in the column is
    content the panel module does not own.
    """
    centre = _three_column_row()[1]

    assert len(centre.body) == 1, (
        f"the centre VCol holds {len(centre.body)} statements; the panel builder "
        f"is supposed to be all of them"
    )
    stmt = centre.body[0]
    assert isinstance(stmt, ast.Assign), f"the centre VCol's statement is {stmt!r}"
    assert len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name), (
        f"the centre VCol assigns {ast.dump(stmt.targets[0])[:80]}"
    )
    assert stmt.targets[0].id == "view", (
        f"the centre VCol assigns {stmt.targets[0].id!r}"
    )
    call = stmt.value
    assert isinstance(call, ast.Call), f"the centre VCol's expression is {call!r}"
    assert isinstance(call.func, ast.Name) and call.func.id == "build_center_panel", (
        f"the centre VCol calls {ast.dump(call.func)[:80]}"
    )
    assert len(call.args) == 1 and isinstance(call.args[0], ast.Name), (
        f"build_center_panel takes {len(call.args)} positional argument(s)"
    )
    assert call.args[0].id == "ctx", f"the panel is handed {call.args[0].id!r}"
    assert not call.keywords, f"build_center_panel got keywords {call.keywords!r}"


def test_the_right_column_is_one_call_to_the_panel_builder():
    """If this fails, the readout and the tabbed panels are built inline again.

    One statement, and it is ``build_right_panel(ctx)``: the builder owns the
    readout strip and the tab container, so anything more in the column is
    content the panel module does not own.
    """
    right = _three_column_row()[2]

    assert len(right.body) == 1, (
        f"the right VCol holds {len(right.body)} statements; the panel builder "
        f"is supposed to be all of them"
    )
    stmt = right.body[0]
    assert isinstance(stmt, ast.Expr), f"the right VCol's statement is {stmt!r}"
    call = stmt.value
    assert isinstance(call, ast.Call), f"the right VCol's expression is {call!r}"
    assert isinstance(call.func, ast.Name) and call.func.id == "build_right_panel", (
        f"the right VCol calls {ast.dump(call.func)[:80]}"
    )
    assert len(call.args) == 1 and isinstance(call.args[0], ast.Name), (
        f"build_right_panel takes {len(call.args)} positional argument(s)"
    )
    assert call.args[0].id == "ctx", f"the panel is handed {call.args[0].id!r}"
    assert not call.keywords, f"build_right_panel got keywords {call.keywords!r}"


class _FakeWidget:
    """A stand-in trame widget: remembers how it was built, and is a context.

    The centre body both calls widget factories as plain calls (the buttons, the
    labels, the spacer) and uses one as a ``with`` block (the wrapper div, the
    player bar), so the fake has to do both.
    """

    def __init__(self, name, args, kwargs):
        self.name = name
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def __repr__(self):
        return f"<fake {self.name}>"


class _FakeController:
    """Stands in for the page controller: reading a click handler is enough."""

    def __init__(self, log):
        self._log = log

    def __getattr__(self, name):
        def _handler(*args, **kwargs):
            self._log.append(("ctrl", name))
        return _handler


CENTER_WIDGETS = ("VBtn", "VLabel", "VSlider", "VSpacer")


def _fake_center_context(
    widget_names=CENTER_WIDGETS, nt=7, available=ANIMATION_PAGE, dump=None
):
    """A real page context carrying recording fakes, and what they recorded.

    Every fake factory takes any arguments, is usable as a ``with`` block and
    appends ``("widget", <name>)`` to the log; ``html_div``, ``VRow`` and
    ``plotter_ui`` append ``("callback", <name>)``, and ``plotter_ui`` returns
    the view sentinel so a test can assert on identity.

    The page is DECLARED an animation page (``available``): the player bar and
    the frame scrubber this column builds belong to the vis viewer, which is the
    page that carries ``nt``, so a fixture left on the empty snapshot would
    claim a field page while the assertions under it describe a vis one.
    ``dump`` is what the context computes from when a test wants a real dump's
    own snapshot instead of a declared kind, and ``available=None`` then means
    "keep what that dump computed".
    """
    log = []
    built = {}
    view = _FakeWidget("view", (), {})

    def _fake(kind, name, result=None):
        def _call(*args, **kwargs):
            log.append((kind, name))
            made = _FakeWidget(name, args, kwargs)
            built.setdefault(name, []).append(made)
            return made if result is None else result
        return _call

    widgets = {name: _fake("widget", name) for name in widget_names}
    ctx = um3k_context.PageContext(dump=dump)
    if available is not None:
        ctx.available = available
    ctx.register_handle("widgets", widgets)
    ctx.register_handle("ctrl", _FakeController(log))
    ctx.register_handle("nt", nt)
    ctx.register_handle("plotter", object())
    ctx.register("html_div", _fake("callback", "html_div"))
    ctx.register("VRow", _fake("callback", "VRow"))
    ctx.register("plotter_ui", _fake("callback", "plotter_ui", result=view))
    return ctx, log, built, view


def _fake_field_context(widget_names=CENTER_WIDGETS, nt=7):
    """The same fakes on a FIELD page: a legacy (station, y, z) plane dump.

    No kind is declared here on purpose: ``PageContext`` computes the snapshot
    from this dump, and ``animation`` is FALSE because the info carries no vis
    ``format`` - the loader's own rule (poc_app.py:353) - rather than a literal
    this file wrote. The two fixtures are the two page kinds, reached the two
    different ways a page ever reaches one.
    """
    return _fake_center_context(
        widget_names=widget_names,
        nt=nt,
        available=None,
        dump=um3k_context.LoadedDump(
            info={"nstep": 3, "nx": 2, "ny": 3, "nz": 4},
        ),
    )


def test_the_centre_fixture_declares_the_page_kind_it_stands_for():
    """If this fails, the centre tests sit on an UNDECLARED page kind.

    ``build_center_panel`` builds the player bar and the frame scrubber
    unconditionally, and that is the ANIMATION viewer's furniture, so the page
    the three centre tests build on has to say ``animation``. It said nothing: a
    bare ``PageContext()`` computes the empty snapshot, which reports ``animation
    is False`` too - the right answer for a page holding no data and the wrong
    one for the page whose player is being built, which is why the omission was
    invisible. The field fixture is the other kind, and reaches it the other
    way: computed from a legacy dump that carries no vis ``format``.
    """
    animation_ctx, _log, _built, _view = _fake_center_context()
    assert animation_ctx.available.animation is True, (
        f"the centre fixture claims {animation_ctx.available!r}"
    )
    assert animation_ctx.available.source_format == "vis"

    field_ctx, _log, _built, _view = _fake_field_context()
    assert field_ctx.available.animation is False
    assert field_ctx.available.source_format == "field"
    assert "format" not in field_ctx.dump.info, (
        "the field fixture carries a vis format, so its snapshot is false for a "
        f"reason the loader never gives: {field_ctx.dump.info!r}"
    )


def test_build_center_panel_constructs_the_column_in_order():
    """If this fails, the player bar's contents or their order changed.

    The expected log is the moved body read straight off: the wrapper div, the
    view, the player bar, then the three playback buttons, the frame slider
    with its label, the three view buttons and the spacer.
    """
    ctx, log, _built, _view = _fake_center_context()

    um3k_panels.build_center_panel(ctx)

    assert log == [
        ("callback", "html_div"),
        ("callback", "plotter_ui"),
        ("callback", "VRow"),
        ("widget", "VBtn"),
        ("widget", "VBtn"),
        ("widget", "VBtn"),
        ("widget", "VSlider"),
        ("widget", "VLabel"),
        ("widget", "VBtn"),
        ("widget", "VBtn"),
        ("widget", "VBtn"),
        ("widget", "VSpacer"),
    ], f"the centre column built {log!r}"


def test_build_center_panel_returns_the_view_it_built():
    """If this fails, ``handles["view"]`` gets something other than the picture."""
    ctx, _log, _built, view = _fake_center_context()

    assert um3k_panels.build_center_panel(ctx) is view


def test_build_center_panel_without_a_VBtn_skips_its_buttons_and_survives():
    """If this fails, a widget table with no buttons breaks the page.

    The body guards every button group on ``"VBtn" in widgets``; with the name
    gone the slider and the spacer must still be built and nothing may raise.
    """
    ctx, log, built, view = _fake_center_context(
        widget_names=("VLabel", "VSlider", "VSpacer")
    )

    result = um3k_panels.build_center_panel(ctx)

    assert "VBtn" not in built, f"a VBtn was built anyway: {sorted(built)}"
    assert result is view
    assert log == [
        ("callback", "html_div"),
        ("callback", "plotter_ui"),
        ("callback", "VRow"),
        ("widget", "VSlider"),
        ("widget", "VLabel"),
        ("widget", "VSpacer"),
    ], f"the column built {log!r}"


def test_build_center_panel_refuses_a_context_missing_a_handle():
    """If this fails, a missing page object draws a half-built column instead.

    ``PageContext.handle`` raises ``KeyError`` naming the missing name and what
    IS stored; the builder must let that through rather than draw nothing.
    """
    ctx = um3k_context.PageContext()
    ctx.available = ANIMATION_PAGE  # kind: the centre column is the vis player
    ctx.register_handle("widgets", {})

    with pytest.raises(KeyError) as excinfo:
        um3k_panels.build_center_panel(ctx)

    message = str(excinfo.value)
    assert "ctrl" in message
    assert "known" in message
    assert "widgets" in message, f"the message does not name what is stored: {message}"


def test_build_center_panel_without_a_timeline_leaves_the_player_out():
    """If this fails, a page with no timeline ships a player over nothing.

    The page is DECLARED an animation page (``available=ANIMATION_PAGE``)
    because that is the page ``run_web_vis`` hands this builder for a legacy
    dump: its page dict says ``is_vis``, so the snapshot claims the animation
    even though the registered frame count is None.  The gate therefore keys on
    ``nt is None``, not on the snapshot: the player (prev/play/next) and the
    scrubber are absent, one visible label says why in their place, and the
    column still returns the picture it built.
    """
    ctx, log, built, view = _fake_center_context(nt=None)

    result = um3k_panels.build_center_panel(ctx)

    assert result is view
    assert log == [
        ("callback", "html_div"),
        ("callback", "plotter_ui"),
        ("callback", "VRow"),
        ("widget", "VLabel"),
        ("widget", "VBtn"),
        ("widget", "VBtn"),
        ("widget", "VBtn"),
        ("widget", "VSpacer"),
    ], f"the centre column built {log!r}"
    assert "VSlider" not in built, (
        f"a scrubber was built over no frame axis: {sorted(built)}"
    )
    button_labels = [made.args[0] for made in built["VBtn"]]
    assert button_labels == ["Switch plane", "Top View", "Side View"], (
        f"the buttons built are {button_labels}; the player's three are not "
        "among them"
    )
    reason = built["VLabel"][0].args[0]
    assert "no timeline" in reason, (
        f"the label standing in for the player says {reason!r}"
    )
    assert "\n" not in reason, f"the reason is not one line: {reason!r}"


RIGHT_CALLBACKS = (
    "_load_s_params_panel", "_load_far_field_panel", "_load_confidence_panel",
    "_emit_s_params_panel", "_emit_far_field_panel", "_emit_confidence_panel",
    "_emit_mode_caption", "_emit_mode_picker", "_emit_vector_toggle",
    "_emit_circuit_netlist", "_emit_load_series_panel",
)
TAB_CLASSES = ("VTabs", "VTab", "VTabsWindow", "VTabsWindowItem")
READOUT_ROWS = (
    "{{ structure_readout }}", "{{ t_label }}", "{{ mode_label }}",
    "{{ phase_label }}", "{{ scale_label }}", "{{ velocity_label }}",
    "{{ velocity_note }}",
)


def _fake_right_context(tab_classes=True, info=None, available=FIELD_PAGE):
    """A real page context carrying the DATA column's fakes, and the log.

    ``html_div`` and every panel callback append ``("callback", <name>)``, the
    four tab classes append ``("tab", <name>)``, and each made widget is kept in
    ``built`` so a test can read its arguments. ``available`` is the page KIND
    this fixture declares - a FIELD page holding none of the flagged data, so
    every tab is offered - and a test stands the column on another page by
    passing its own snapshot (``animation=True``, ``multifreq=True``,
    ``record=True``) rather than by leaving the constructor's default in place.
    """
    log = []
    built = {}

    def _fake(kind, name):
        def _call(*args, **kwargs):
            log.append((kind, name))
            made = _FakeWidget(name, args, kwargs)
            built.setdefault(name, []).append(made)
            return made
        return _call

    module = type("FakeWidgetModule", (), {})()
    if tab_classes:
        for cls in TAB_CLASSES:
            setattr(module, cls, _fake("tab", cls))
    ctx = um3k_context.PageContext()
    ctx.register_handle("widgets_module", module)
    ctx.register_handle("info", dict(info or {}))
    ctx.register("html_div", _fake("callback", "html_div"))
    for name in RIGHT_CALLBACKS:
        ctx.register(name, _fake("callback", name))
    ctx.available = available
    return ctx, log, built


def test_build_right_panel_builds_the_readout_strip_first():
    """If this fails, the readout rows, or what they say, changed.

    One ``html_div`` wrapper, the seven template rows in order, then the note
    saying where a solve runs. The FALLBACK context, so the count is the strip.
    """
    ctx, log, built = _fake_right_context(tab_classes=False)

    um3k_panels.build_right_panel(ctx)

    assert log[0] == ("callback", "html_div"), f"the column began with {log[0]!r}"
    strip = built["html_div"]
    assert len(strip) == 9, f"the column made {len(strip)} html_div calls"
    rows = strip[1:]
    assert len(rows) == 8, f"the strip holds {len(rows)} rows, not eight"
    assert [row.args[0] for row in rows[:7]] == list(READOUT_ROWS), (
        f"the readout rows are {[row.args[0] for row in rows[:7]]!r}"
    )
    assert "solve runs on the HOST" in rows[7].args[0], (
        f"the last row reads {rows[7].args[0]!r}"
    )


def test_build_right_panel_loads_the_three_panels_before_any_tab():
    """If this fails, a tab can be selected before its panel was filled in.

    Each loader runs once, at layout time, in the order the panels were
    stacked, and all three before the first tab widget exists.
    """
    ctx, log, _built = _fake_right_context()

    um3k_panels.build_right_panel(ctx)

    names = [name for kind, name in log if kind == "callback"]
    assert names[9:12] == list(RIGHT_CALLBACKS[:3]), (
        f"the loaders ran {names[9:14]!r}"
    )
    first_tab = next(i for i, (kind, _n) in enumerate(log) if kind == "tab")
    loader_at = [i for i, entry in enumerate(log) if entry[1] in RIGHT_CALLBACKS[:3]]
    assert len(loader_at) == 3, f"the loaders ran {len(loader_at)} times"
    assert max(loader_at) < first_tab, (
        f"a tab was built at {first_tab} before the loaders ended at "
        f"{max(loader_at)}"
    )


def test_build_right_panel_names_both_sides_of_every_tab():
    """If this fails, the tab bar selects a value its window cannot match.

    Five tabs and five window items carrying the SAME five strings, both
    containers handed one ``v_model`` tuple, each panel emitting in its item.
    """
    ctx, log, built = _fake_right_context()

    um3k_panels.build_right_panel(ctx)

    values = ["s_params", "far_field", "confidence", "modes", "circuit"]
    for cls in ("VTab", "VTabsWindowItem"):
        assert [w.kwargs["value"] for w in built[cls]] == values
    for container in ("VTabs", "VTabsWindow"):
        made = built[container]
        assert len(made) == 1, f"{container} was built {len(made)} times"
        model = made[0].kwargs["v_model"]
        assert isinstance(model, tuple) and model == ("tab", "s_params"), (
            f"{container} was handed v_model={model!r}"
        )
    assert log[-14:] == [
        ("tab", "VTabsWindowItem"), ("callback", "_emit_s_params_panel"),
        ("tab", "VTabsWindowItem"), ("callback", "_emit_far_field_panel"),
        ("tab", "VTabsWindowItem"), ("callback", "_emit_confidence_panel"),
        ("tab", "VTabsWindowItem"), ("callback", "_emit_mode_caption"),
        ("callback", "_emit_mode_picker"), ("callback", "_emit_vector_toggle"),
        ("tab", "VTabsWindowItem"), ("callback", "html_div"),
        ("callback", "_emit_circuit_netlist"),
        ("callback", "_emit_load_series_panel"),
    ], f"the window built {log[-14:]!r}"


def test_build_right_panel_shows_every_tab_on_an_animation_page():
    """If this fails, the animation page lost a tab it has always shown.

    A vis page is what this column was built for: its snapshot says
    ``animation``, and it keeps all five tabs whatever the other flags hold,
    still opening on S-Parameters.
    """
    ctx, _log, built = _fake_right_context(
        available=um3k_context.Available(animation=True, source_format="um3k")
    )

    um3k_panels.build_right_panel(ctx)

    values = ["s_params", "far_field", "confidence", "modes", "circuit"]
    for cls in ("VTab", "VTabsWindowItem"):
        assert [w.kwargs["value"] for w in built[cls]] == values, (
            f"{cls} carries {[w.kwargs['value'] for w in built[cls]]!r}"
        )
    for container in ("VTabs", "VTabsWindow"):
        assert built[container][0].kwargs["v_model"] == ("tab", "s_params")


def test_build_right_panel_shows_only_the_tabs_the_page_can_fill():
    """If this fails, a tab is drawn for data the page does not hold.

    A field page with a sweep keeps S-Parameters, the Far Field tab (which
    reads the --surface-dump archive, not the page), Modes (which solves from
    the dump's own metadata when no record sits beside it) and the Circuit box
    that asks the page for nothing; only Confidence N-lambda, the one RECORD
    reader left, is gone from BOTH sides of the tab pair, not just one.
    """
    ctx, _log, built = _fake_right_context(
        available=um3k_context.Available(multifreq=True)
    )

    um3k_panels.build_right_panel(ctx)

    values = ["s_params", "far_field", "modes", "circuit"]
    for cls in ("VTab", "VTabsWindowItem"):
        assert [w.kwargs["value"] for w in built[cls]] == values, (
            f"{cls} carries {[w.kwargs['value'] for w in built[cls]]!r}"
        )
    assert built["VTabs"][0].kwargs["v_model"] == ("tab", "s_params")


def test_build_right_panel_opens_on_the_first_tab_it_kept():
    """If this fails, the column opens on a tab the page cannot draw.

    With only a record, Far Field is the first kept tab - the always-on row
    that asks the page for nothing - so both containers are handed ITS value
    rather than the hard-coded ``s_params``, which this page cannot fill at all.
    """
    ctx, _log, built = _fake_right_context(
        available=um3k_context.Available(record=True)
    )

    um3k_panels.build_right_panel(ctx)

    for cls in ("VTab", "VTabsWindowItem"):
        assert [w.kwargs["value"] for w in built[cls]] == [
            "far_field", "confidence", "modes", "circuit"
        ]
    for container in ("VTabs", "VTabsWindow"):
        assert built[container][0].kwargs["v_model"] == ("tab", "far_field"), (
            f"{container} was handed {built[container][0].kwargs['v_model']!r}"
        )


def test_build_right_panel_keeps_all_five_when_no_flag_is_true():
    """If this fails, a page that claims nothing loses the whole right side.

    The bare context's snapshot says nothing about anything: a wrong flag has to
    cost a tab at most, never the column, so all five are drawn.
    """
    ctx, _log, built = _fake_right_context()
    true_flags = [
        flag for _label, _value, flag in um3k_panels.RIGHT_TABS
        if flag is not None and getattr(ctx.available, flag, False)
    ]
    assert not true_flags, f"the bare context claims {true_flags!r}"

    um3k_panels.build_right_panel(ctx)

    values = ["s_params", "far_field", "confidence", "modes", "circuit"]
    for cls in ("VTab", "VTabsWindowItem"):
        assert [w.kwargs["value"] for w in built[cls]] == values


def test_build_right_panel_pairs_each_label_with_its_own_value():
    """If this fails, a tab is drawn under one name and selects another.

    Each label and the value it registers come off ONE ``RIGHT_TABS`` row, so
    the bar can never advertise a panel it cannot reach.
    """
    ctx, _log, built = _fake_right_context()

    um3k_panels.build_right_panel(ctx)

    pairs = [(made.args[0], made.kwargs["value"]) for made in built["VTab"]]
    assert pairs == [
        (label, value) for label, value, _flag in um3k_panels.RIGHT_TABS
    ], f"the tabs read {pairs!r}"


def test_build_right_panel_hands_the_load_series_its_two_info_values():
    """If this fails, the load's trace is built from the wrong keys.

    ``_emit_load_series_panel`` takes exactly those two payloads, by identity,
    so a renamed or reordered pair fails here instead of drawing an empty box.
    """
    series = object()
    reason = object()
    info = {"load_series": series, "load_series_reason": reason}
    ctx, _log, built = _fake_right_context(tab_classes=False, info=info)

    um3k_panels.build_right_panel(ctx)

    assert len(built["_emit_load_series_panel"]) == 1
    args = built["_emit_load_series_panel"][0].args
    assert len(args) == 2 and args[0] is series and args[1] is reason, (
        f"_emit_load_series_panel got {args!r}"
    )


def test_build_right_panel_without_the_tab_widgets_stacks_the_five_panels():
    """If this fails, a trame-vuetify-free page lost a panel.

    With no tab classes the body stacks all five panels in the flat pre-tabs
    order, asserts below, and builds no tab at all.
    """
    ctx, log, built = _fake_right_context(tab_classes=False)

    um3k_panels.build_right_panel(ctx)

    names = [name for kind, name in log if kind == "callback"]
    assert names[-8:] == [
        "_emit_confidence_panel", "_emit_s_params_panel",
        "_emit_far_field_panel", "_emit_circuit_netlist",
        "_emit_load_series_panel", "_emit_mode_caption",
        "_emit_mode_picker", "_emit_vector_toggle",
    ], f"the fallback built {names[-8:]!r}"
    assert not [name for name in built if name.startswith("VTab")], (
        f"a tab was built without the classes: {sorted(built)}"
    )


def test_build_right_panel_refuses_a_context_missing_a_handle():
    """If this fails, a missing page object draws a half-built DATA column.

    ``PageContext.handle`` raises ``KeyError`` naming the missing name and what
    IS stored; the builder must let that through rather than draw nothing.
    """
    ctx = um3k_context.PageContext()
    ctx.available = FIELD_PAGE  # kind: the refusal precedes any snapshot read
    ctx.register_handle("widgets_module", object())

    with pytest.raises(KeyError) as excinfo:
        um3k_panels.build_right_panel(ctx)

    message = str(excinfo.value)
    assert "info" in message
    assert "known" in message
    assert "widgets_module" in message, (
        f"the message does not name what is stored: {message}"
    )


def _child_env_without_server_on_path():
    """The child's environment, minus any PYTHONPATH entry handing it server/.

    The package-form test is only honest if server/ is NOT on the path the
    child is given, so an entry equal to it is stripped rather than assumed
    absent from the ambient PYTHONPATH.
    """
    env = os.environ.copy()
    entries = [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    kept = [p for p in entries if Path(p).resolve() != REPO_ROOT / "server"]
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT), *kept])
    return env


def _run_child(script, env=None):
    """Run ``script`` in a fresh interpreter started at the repository root."""
    return subprocess.run(
        [sys.executable, "-c", script], cwd=str(REPO_ROOT),
        capture_output=True, text=True, env=env,
    )


def test_package_form_import_works_without_server_on_the_path():
    """If this fails, `import server.poc_app` is broken again.

    ``server/`` has no ``__init__.py``, so a package-form import leaves
    ``sys.path[0]`` at the repository root and a bare ``import um3k_context``
    does not resolve. The child runs from the repository root with server/
    stripped from ``PYTHONPATH``: the form the report at
    ``reports/2026-11-11_18-23-43_Visual_layer_pass*:15`` records as clean, and
    the one the script-form imports broke.
    """
    script = (
        "import sys\n"
        f"assert {str(REPO_ROOT / 'server')!r} not in sys.path, sys.path\n"
        "import server.poc_app\n"
        "print('package-ok')\n"
    )
    proc = _run_child(script, env=_child_env_without_server_on_path())
    assert proc.returncode == 0, (
        f"package-form import of server.poc_app failed\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "package-ok" in proc.stdout, (
        f"the child printed {proc.stdout!r} instead of package-ok\n"
        f"stderr:\n{proc.stderr}"
    )


def test_a_missing_dependency_inside_our_modules_is_not_swallowed():
    """If this fails, the guard re-routes more than our own two names.

    A finder in the child raises ``ModuleNotFoundError`` for a name that is NOT
    ours while ``um3k_context`` is being imported. The guard must re-raise it,
    so the child dies naming that dependency; swallowing it would fall through
    to ``from . import um3k_context`` and report a relative-import error that
    names no dependency at all - which is what the assertion on the name rules
    out.
    """
    script = (
        "import sys\n"
        "class _RaiseForOurs:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'um3k_context':\n"
        "            raise ModuleNotFoundError(\n"
        '                "No module named \'not_a_real_dependency\'",\n'
        "                name='not_a_real_dependency')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _RaiseForOurs())\n"
        f"sys.path.insert(0, {str(REPO_ROOT / 'server')!r})\n"
        "import poc_app\n"
        "print('swallowed')\n"
    )
    proc = _run_child(script)
    assert "swallowed" not in proc.stdout, (
        f"poc_app imported despite a missing dependency\nstdout:\n{proc.stdout}"
    )
    assert proc.returncode != 0, (
        f"the child exited 0 with a missing dependency\nstdout:\n{proc.stdout}"
    )
    assert "not_a_real_dependency" in proc.stderr, (
        f"the missing dependency was not named in the failure, so the guard "
        f"swallowed it instead of re-raising it\nstderr:\n{proc.stderr}"
    )
