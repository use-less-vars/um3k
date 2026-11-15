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
  column still holds what it held;
* the centre builder builds what it was given: called against recording fake
  widgets it constructs them in the order the column holds them, returns the
  view its own ``plotter_ui`` made, tolerates a widget table with no ``VBtn``,
  and refuses a context that is missing a handle instead of drawing nothing.
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


def _context(events=None):
    """A real page context whose one callback records that it was called."""
    ctx = um3k_context.PageContext(
        dump=um3k_context.LoadedDump(info={"nstep": 3, "nx": 2, "ny": 3, "nz": 4}),
    )
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


def test_the_right_column_is_untouched():
    """If this fails, the move took the readout with it.

    The right column still carries its readout template rows, checked by shape,
    so a column that was emptied to make the row parse fails here.
    """
    _left, _centre, right = _three_column_row()

    readouts = [
        node for node in ast.walk(right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "html_div" and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and "{{ structure_readout }}" in node.args[0].value
    ]
    assert readouts, "the right column lost its structure readout row"


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


def _fake_center_context(widget_names=CENTER_WIDGETS, nt=7):
    """A real page context carrying recording fakes, and what they recorded.

    Every fake factory takes any arguments, is usable as a ``with`` block and
    appends ``("widget", <name>)`` to the log; ``html_div``, ``VRow`` and
    ``plotter_ui`` append ``("callback", <name>)``, and ``plotter_ui`` returns
    the view sentinel so a test can assert on identity.
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
    ctx = um3k_context.PageContext()
    ctx.register_handle("widgets", widgets)
    ctx.register_handle("ctrl", _FakeController(log))
    ctx.register_handle("nt", nt)
    ctx.register_handle("plotter", object())
    ctx.register("html_div", _fake("callback", "html_div"))
    ctx.register("VRow", _fake("callback", "VRow"))
    ctx.register("plotter_ui", _fake("callback", "plotter_ui", result=view))
    return ctx, log, built, view


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
    ctx.register_handle("widgets", {})

    with pytest.raises(KeyError) as excinfo:
        um3k_panels.build_center_panel(ctx)

    message = str(excinfo.value)
    assert "ctrl" in message
    assert "known" in message
    assert "widgets" in message, f"the message does not name what is stored: {message}"


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
