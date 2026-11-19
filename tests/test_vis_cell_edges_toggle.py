"""The Grid (cell edges) box on the animated view panel.

WHAT IS BEING PINNED. The cell grid under the animated field sheets is a
DRAWING property (``show_edges``) of an actor that only exists in a live
pyvista plotter, so no test here can look at a picture. What CAN be pinned is
that the switch which now owns that property is wired end to end: the sheets
built at boot and the sheets rebuilt after a solve both read the ONE helper, the
y-cut overlay reads it too, the view panel carries a box bound to
``show_cell_edges``, and a ``@state.change`` handler applies the value to the
actors already on screen.

WHY TEXT AND AST, NEVER IMPORT. Importing ``server/poc_app.py`` builds a VTK
plotter, a server and a dataset reader as a side effect; a syntax-level check
needs none of that.

WHY ``VIS_SHOW_EDGES`` MUST STAY A MODULE-LEVEL LITERAL ``True``. It is the
box's own default, so it has to be a value a fresh session can bind to; a page
whose default came from the runtime flag would have nothing to bind.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "server" / "poc_app.py"


def _source() -> str:
    assert SOURCE.is_file(), f"poc_app.py not found at {SOURCE}"
    return SOURCE.read_text(encoding="utf-8")


def _tree() -> ast.Module:
    return ast.parse(_source())


def _enclosing_name(tree: ast.Module, lineno: int) -> str:
    """Name of the INNERMOST function whose body holds ``lineno``."""
    found: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            end = node.end_lineno or node.lineno
            if node.lineno <= lineno <= end:
                if found is None or node.lineno > found.lineno:
                    found = node
    return found.name if found is not None else ""


def _parent_name(tree: ast.Module, target: ast.AST) -> str:
    """Name of the innermost function that CONTAINS ``target`` (not itself)."""
    assert isinstance(target, ast.FunctionDef)
    found: ast.FunctionDef | None = None
    last = target.end_lineno or target.lineno
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node is target:
            continue
        end = node.end_lineno or node.lineno
        if node.lineno <= target.lineno and last <= end:
            if found is None or node.lineno > found.lineno:
                found = node
    return found.name if found is not None else ""


def _lines_with(text: str) -> list[int]:
    return [
        lineno
        for lineno, line in enumerate(_source().splitlines(), 1)
        if text in line
    ]


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    found = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(found) == 1, f"expected exactly one def {name}, found {len(found)}"
    return found[0]


def _assigned_attrs(fn: ast.FunctionDef) -> set[str]:
    """Every attribute set by a plain/augmented/annotated assignment in ``fn``."""
    attrs: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Attribute):
                attrs.add(target.attr)
    return attrs


def _method_calls(fn: ast.FunctionDef, obj: str, attr: str) -> list[ast.Call]:
    """Calls written as ``obj.attr(...)`` anywhere inside ``fn``."""
    return [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == obj
    ]


def test_grid_default_is_still_a_module_level_literal_true() -> None:
    """``VIS_SHOW_EDGES = True`` at module level: the box needs a value to bind."""
    tree = _tree()
    hits = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "VIS_SHOW_EDGES"
            for target in node.targets
        )
    ]
    assert len(hits) == 1, (
        "VIS_SHOW_EDGES must be assigned exactly once at module level, "
        f"found {len(hits)}"
    )
    assert ast.literal_eval(hits[0].value) is True


def test_every_sheet_edge_decision_comes_from_the_one_helper() -> None:
    """Both sheet builds and the y-cut overlay read the helper, not the flag.

    THREE readers, one rule: a boot sheet, a rebuilt sheet and the dimmed
    substrate outline must agree, or a solve silently restores a grid the box
    just switched off. The module flag itself is read in the helper ONLY.
    """
    src = _source()
    assert src.count("show_edges=VIS_SHOW_EDGES") == 0, (
        "a sheet still takes show_edges straight from the module flag"
    )
    sheet_calls = _lines_with("show_edges=_cell_edges_on(),")
    assert len(sheet_calls) == 2, sheet_calls

    assert src.count("actor.prop.show_edges = VIS_SHOW_EDGES") == 0, (
        "the y-cut overlay still takes show_edges straight from the flag"
    )
    overlay_calls = _lines_with("actor.prop.show_edges = _cell_edges_on()")
    assert len(overlay_calls) == 1, overlay_calls

    tree = _tree()
    owners = {_enclosing_name(tree, lineno) for lineno in sheet_calls}
    assert owners == {"run_web_vis", "_rebuild_sheets"}, owners
    assert _enclosing_name(tree, overlay_calls[0]) == "_show"

    helper = _function(tree, "_cell_edges_on")
    assert _parent_name(tree, helper) == "run_web_vis"
    dump = ast.dump(helper)
    assert "VIS_SHOW_EDGES" in dump, "the helper ignores the module default"
    assert "edges_state" in dump, "the helper ignores what the box writes"
    assert helper.lineno < min(sheet_calls), (
        "the helper must be defined ABOVE the boot sheet loop that calls it"
    )


def test_the_mode_picture_keeps_its_own_edges_off() -> None:
    """The 2-D mode picture never had a grid, and this switch must not give it one."""
    hits = _lines_with("show_edges=False")
    assert len(hits) == 1, hits
    assert _enclosing_name(_tree(), hits[0]) == "_draw_mode_picture"


def test_view_panel_carries_a_grid_box_bound_to_the_state_name() -> None:
    """One box, bound to (``show_cell_edges``, ``VIS_SHOW_EDGES``), in the panel."""
    tree = _tree()
    boxes: list[tuple[ast.Call, dict[str, ast.expr]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "checkbox_cls"):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg is not None}
        binding = kwargs.get("v_model")
        if not isinstance(binding, ast.Tuple) or len(binding.elts) != 2:
            continue
        name = binding.elts[0]
        if isinstance(name, ast.Constant) and name.value == "show_cell_edges":
            boxes.append((node, kwargs))

    assert len(boxes) == 1, (
        f"expected exactly one checkbox bound to show_cell_edges, found {len(boxes)}"
    )
    node, kwargs = boxes[0]
    binding = kwargs["v_model"]
    assert isinstance(binding, ast.Tuple)  # narrowed again for the type checker
    default = binding.elts[1]
    assert isinstance(default, ast.Name) and default.id == "VIS_SHOW_EDGES", (
        f"the box must default to the module flag, not a literal: {ast.dump(default)}"
    )
    label = kwargs.get("label")
    assert isinstance(label, ast.Constant) and isinstance(label.value, str), (
        "the box must carry a readable label"
    )
    assert "grid" in label.value.lower() and "cell" in label.value.lower(), (
        f"the label must say what it switches, got {label.value!r}"
    )
    assert _enclosing_name(tree, node.lineno) == "_emit_vector_toggle"


def test_a_state_change_handler_applies_the_box_to_the_live_actors() -> None:
    """``@state.change("show_cell_edges")`` and not ``@ctrl.set``: v_model only
    reaches a change callback."""
    tree = _tree()
    handler = _function(tree, "_on_show_cell_edges")

    keys: list[str] = []
    for decorator in handler.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        func = decorator.func
        if not (isinstance(func, ast.Attribute) and func.attr == "change"):
            continue
        assert isinstance(func.value, ast.Name) and func.value.id == "state", (
            "the change callback must be registered on server.state"
        )
        keys.extend(ast.literal_eval(arg) for arg in decorator.args)
    assert keys == ["show_cell_edges"], (
        f"expected exactly one @state.change('show_cell_edges'), got {keys}"
    )

    assert "'show_cell_edges'" in ast.dump(handler), (
        "the handler never reads the value it is told has changed"
    )
    assert "show_edges" in _assigned_attrs(handler), (
        "the handler never sets show_edges on the live actor"
    )
    assert _method_calls(handler, "plotter", "render"), (
        "the handler must repaint, or the box changes nothing on screen"
    )

    edges_calls = [
        node
        for node in ast.walk(handler)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_cell_edges_on"
    ]
    assert edges_calls, "the handler must set the edges THROUGH the one helper"
