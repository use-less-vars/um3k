"""The Substrate opacity slider on the animated view panel.

WHAT IS BEING PINNED. The dielectric slab's opacity is a DRAWING property of an
actor that only exists in a live pyvista plotter, so no test here can look at a
picture. What CAN be pinned is that the control which owns that property is
wired end to end: the slab built at boot takes the module constant, a
``@state.change`` handler applies a moved slider to the actor already on screen,
the view panel carries a slider bound to ``substrate_opacity``, and the overlay
re-stamp inside ``_show`` reads the ONE reader rather than a second literal.

WHY TEXT AND AST, NEVER IMPORT. Importing ``server/poc_app.py`` builds a VTK
plotter, a server and a dataset reader as a side effect; a syntax-level check
needs none of that.

THE 0.08 THAT SURVIVES IN ``_show`` IS NOT THIS FEATURE'S. The slab's y-cut
dimming used to be the bare literal 0.08; it is now
``VIS_SUBSTRATE_YCUT_SCALE`` times whatever the slider says. The 0.08 that is
still written there belongs to the OTHER overlay boxes (ground plane, plane
strip, markers), which this slider does not own, so the check below is that the
SUBSTRATE branch never assigns a float literal to ``.opacity`` - not that the
file contains no 0.08 anywhere.
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


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    found = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(found) == 1, f"expected exactly one def {name}, found {len(found)}"
    return found[0]


def _body_text(fn: ast.FunctionDef) -> str:
    """The source of ``fn``'s own lines, indentation and all."""
    lines = _source().splitlines()
    start = fn.lineno - 1
    end = fn.end_lineno or fn.lineno
    return "\n".join(lines[start:end])


def _lines_with(text: str) -> list[int]:
    return [
        lineno
        for lineno, line in enumerate(_source().splitlines(), 1)
        if text in line
    ]


def _substrate_branch(fn: ast.FunctionDef) -> ast.If:
    """The ``if actor is plotter.actors.get("substrate"):`` inside ``_show``."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "actor"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Is)
            and len(test.comparators) == 1
        ):
            continue
        call = test.comparators[0]
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "get"
            and isinstance(call.func.value, ast.Attribute)
            and call.func.value.attr == "actors"
            and isinstance(call.func.value.value, ast.Name)
            and call.func.value.value.id == "plotter"
            and len(call.args) == 1
            and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == "substrate"
        ):
            continue
        return node
    raise AssertionError(
        '_show must branch on ``actor is plotter.actors.get("substrate")``'
    )


def _enclosing_for(fn: ast.FunctionDef, target: ast.AST) -> ast.For:
    """The INNERMOST ``for`` loop in ``fn`` whose body holds ``target``."""
    assert isinstance(target, ast.stmt)
    end = target.end_lineno or target.lineno
    found: ast.For | None = None
    for node in ast.walk(fn):
        if not isinstance(node, ast.For):
            continue
        loop_end = node.end_lineno or node.lineno
        if node.lineno <= target.lineno and end <= loop_end:
            if found is None or node.lineno > found.lineno:
                found = node
    assert found is not None, "the substrate branch must live inside the overlay loop"
    return found


def _opacity_assigns(nodes: list[ast.stmt]) -> list[ast.Assign]:
    """Every ``X.opacity = ...`` assignment anywhere inside ``nodes``."""
    found: list[ast.Assign] = []
    for root in nodes:
        for node in ast.walk(root):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "opacity":
                    found.append(node)
    return found


def test_both_module_constants_are_module_level_literals() -> None:
    """The slider needs two numbers to bind to: the default and the y-cut scale."""
    tree = _tree()
    for name, expected in (
        ("VIS_SUBSTRATE_OPACITY", 0.10),
        ("VIS_SUBSTRATE_YCUT_SCALE", 0.8),
    ):
        hits = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            )
        ]
        assert len(hits) == 1, (
            f"{name} must be assigned exactly once at module level, "
            f"found {len(hits)}"
        )
        assert ast.literal_eval(hits[0].value) == expected, (
            f"{name} must be the shipped {expected}, "
            f"got {ast.literal_eval(hits[0].value)!r}"
        )


def test_the_boot_slab_takes_the_constant_not_a_literal() -> None:
    """The slab drawn at boot reads the ONE number the slider starts from."""
    tree = _tree()
    body = _body_text(_function(tree, "_vis_geometry"))
    assert body.count("opacity=0.10") == 0, (
        "the substrate is still drawn with a bare 0.10 the slider cannot move"
    )
    assert body.count("opacity=VIS_SUBSTRATE_OPACITY") == 1, (
        "the substrate must be drawn with opacity=VIS_SUBSTRATE_OPACITY exactly "
        f"once, found {body.count('opacity=VIS_SUBSTRATE_OPACITY')}"
    )
    hits = _lines_with("opacity=VIS_SUBSTRATE_OPACITY")
    assert len(hits) == 1, hits
    assert _enclosing_name(tree, hits[0]) == "_vis_geometry"


def test_the_substrate_overlay_is_restamped_from_the_one_reader() -> None:
    """``_show`` moves the slab through ``_substrate_drawn``, never a literal.

    The other overlays (ground plane, plane strip, markers) keep their own
    numbers - the 0.08 in the sibling y-cut branch is one of those, not this
    slider's. Only the substrate branch must refuse float literals.
    """
    tree = _tree()
    branch = _substrate_branch(_function(tree, "_show"))
    assigns = _opacity_assigns(branch.body)
    assert assigns, "the substrate branch never sets .opacity"

    literals = [
        node
        for node in assigns
        if isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, (int, float))
        and not isinstance(node.value.value, bool)
    ]
    assert not literals, (
        "the substrate branch sets .opacity to a bare number, so moving the "
        f"slider would be undone on the next family swap: line(s) "
        f"{[node.lineno for node in literals]}"
    )

    readers = [
        node
        for node in assigns
        if isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_substrate_drawn"
    ]
    assert readers, (
        "the substrate branch must set .opacity through _substrate_drawn, the "
        "one reader the slider also writes"
    )
    loop = _enclosing_for(_function(tree, "_show"), branch)
    assert "_cell_edges_on" in ast.dump(loop), (
        "the slab's re-stamp must keep the grid helper on the same actor, or "
        "the y-cut overlay loses its outline"
    )
    assert "substrate" in ast.dump(loop), (
        "the outline and the opacity must move together in the overlay loop"
    )


def test_view_panel_carries_a_slider_bound_to_the_state_name() -> None:
    """One slider, bound to (``substrate_opacity``, ``VIS_SUBSTRATE_OPACITY``)."""
    binding = 'v_model=("substrate_opacity", VIS_SUBSTRATE_OPACITY)'
    hits = _lines_with(binding)
    assert len(hits) == 1, (
        f"expected exactly one slider bound to substrate_opacity, found {len(hits)} "
        f"at {hits}"
    )
    assert _enclosing_name(_tree(), hits[0]) == "_emit_vector_toggle", (
        "the slider belongs in the view panel's control block"
    )


def test_a_state_change_handler_applies_the_slider_to_the_live_actor() -> None:
    """``@state.change("substrate_opacity")`` and not ``@ctrl.set``: v_model only
    reaches a change callback."""
    tree = _tree()
    handler = _function(tree, "_on_substrate_opacity")

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
    assert keys == ["substrate_opacity"], (
        f"expected exactly one @state.change('substrate_opacity'), got {keys}"
    )
    assert "ctrl" not in ast.dump(handler.decorator_list[0]), (
        "@ctrl.set never sees a v_model write"
    )

    stores = [
        node
        for node in ast.walk(handler)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Name)
        and target.value.id == "substrate_state"
        and isinstance(target.slice, ast.Constant)
        and target.slice.value == "opacity"
    ]
    assert stores, "the handler must write what the slider says into substrate_state"

    applies = [
        node
        for node in ast.walk(handler)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Attribute)
        and target.attr == "opacity"
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_substrate_drawn"
    ]
    assert applies, (
        "the handler must move the slab on screen through _substrate_drawn, or "
        "the slider changes nothing until the next redraw"
    )
    assert "plotter" in ast.dump(handler), (
        "the handler must touch the live plotter's actor"
    )
