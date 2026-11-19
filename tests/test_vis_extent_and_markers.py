"""The web-vis frame: the domain extents are drawn, and the marker boxes still are.

WHY THIS IS A SOURCE-LEVEL TEST, and not a render: ``server/poc_app.py`` builds
a trame application on import and needs a GL context that this image does not
have, so the module cannot be imported here at all - every claim below is made
on the FILE TEXT (``ast`` for the function shapes, the raw text for the call
sites), exactly as ``tests/test_playback_honesty.py`` makes its structural
claim. A failure therefore points at the line that lost the behaviour, and no
part of this file needs a plotter to run.

The two behaviours pinned here are the P2a repair, and both of them are
invisible to every other suite:

* the domain box/boundary extents are part of the FRAME the browser sees on the
  web-vis page, so they must be drawn from inside ``run_web_vis`` - the page A
  helper ``_add_extent_outlines`` only reached the matplotlib scene before. A
  helper that exists but is never called from the page is the defect this
  guards: it draws nothing and nothing complains.
* the two marker-plane checkboxes must survive on a page with NO plane stack
  (the |E| volume page, which keeps no ``cut_redraw``). The old guard asked
  ``cut_redraw`` alone and silently emitted neither box there.

The claims, one per test:

(a) ``_add_extent_outlines(`` appears at least twice - the shared helper's own
    ``def`` is not the whole story - and at least one call is INSIDE the
    ``def run_web_vis`` -> ``def main`` span, i.e. on the page rather than in
    the matplotlib scene builder;
(b) ``_draw_extent_outlines`` is defined exactly once, in that same span, and
    its body calls ``_add_extent_outlines``;
(c) ``_plane_toggles_available`` is defined exactly once, is what
    ``_emit_vector_toggle`` asks, and the old ``if not
    callable(handles.get("cut_redraw")):`` early return is GONE from the file -
    the box emission is no longer gated on the stack it was written for;
(d) both marker boxes are still emitted, once each, by ``_emit_vector_toggle``.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POC_APP = REPO_ROOT / "server" / "poc_app.py"


def _source() -> str:
    """The module text. Never imported - see the module docstring."""
    return POC_APP.read_text(encoding="utf-8")


def _function_defs(tree: ast.Module, name: str) -> list:
    """Every ``def name`` in the module, at any nesting depth."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]


def _body(source: str, node) -> str:
    """The node's own source text (docstring included)."""
    return ast.get_source_segment(source, node) or ""


def test_the_page_draws_the_extent_outlines():
    """(a) ``_add_extent_outlines`` is called from inside ``run_web_vis``.

    Counted on the raw text rather than through ``ast``: what matters is that a
    CALL exists in the page's span, and the helper is also defined and called in
    the matplotlib scene builder, so the two cannot be told apart by name alone.
    """
    source = _source()
    tree = ast.parse(source)

    total = source.count("_add_extent_outlines(")
    assert total >= 2, (
        f"{POC_APP.name} mentions '_add_extent_outlines(' {total} time(s): the "
        "extent helper is defined and called in the scene builder, so fewer than "
        "two means one of the two has gone"
    )

    pages = _function_defs(tree, "run_web_vis")
    assert len(pages) == 1, f"{len(pages)} 'def run_web_vis' in {POC_APP.name}"
    page = pages[0]
    span = range(page.lineno, (page.end_lineno or page.lineno) + 1)

    lines = source.splitlines()
    calls = [
        number
        for number in span
        if "_add_extent_outlines(" in lines[number - 1]
    ]
    assert calls, (
        f"no call to '_add_extent_outlines(' on lines {span.start}-{span.stop - 1}: "
        "the web-vis page never draws the domain extents, and a frame without "
        "them looks exactly like a frame whose dump had none"
    )


def test_draw_extent_outlines_is_defined_once_and_calls_the_helper():
    """(b) One nested drawer, in the page's span, and it calls the helper."""
    source = _source()
    tree = ast.parse(source)

    drawers = _function_defs(tree, "_draw_extent_outlines")
    assert len(drawers) == 1, (
        f"{len(drawers)} 'def _draw_extent_outlines' in {POC_APP.name} at lines "
        f"{[node.lineno for node in drawers]}: two drawers would stack two "
        "copies of the same frame"
    )
    drawer = drawers[0]

    pages = _function_defs(tree, "run_web_vis")
    assert len(pages) == 1, f"{len(pages)} 'def run_web_vis' in {POC_APP.name}"
    page = pages[0]
    assert page.lineno < drawer.lineno <= (page.end_lineno or page.lineno), (
        f"'_draw_extent_outlines' is defined at line {drawer.lineno}, outside the "
        f"page span {page.lineno}-{page.end_lineno}: only the page owns the "
        "plotter it has to draw on"
    )

    body = _body(source, drawer)
    assert "_add_extent_outlines(" in body, (
        "the page's extent drawer does not call the shared "
        "'_add_extent_outlines': it is a second implementation of the same "
        "picture, free to disagree with the matplotlib scene"
    )


def test_the_plane_toggle_gate_is_shared_and_precedes_the_boxes():
    """(c) One predicate, asked by the emitter, and the old guard is gone.

    The old early return ``if not callable(handles.get("cut_redraw")):`` is
    asserted ABSENT by exact text: on the |E| volume page there is no
    ``cut_redraw``, so that line emitted neither box while the marker discs were
    on screen - the regression P2a replaced.
    """
    source = _source()
    tree = ast.parse(source)

    predicates = _function_defs(tree, "_plane_toggles_available")
    assert len(predicates) == 1, (
        f"{len(predicates)} 'def _plane_toggles_available' in {POC_APP.name} at "
        f"lines {[node.lineno for node in predicates]}: the emitter and the "
        "repaint must ask the SAME question or a box can be offered where "
        "nothing repaints"
    )

    emitters = _function_defs(tree, "_emit_vector_toggle")
    assert len(emitters) == 1, (
        f"{len(emitters)} 'def _emit_vector_toggle' in {POC_APP.name}"
    )
    body = _body(source, emitters[0])

    assert "_plane_toggles_available()" in body, (
        "the marker boxes are emitted without asking "
        "'_plane_toggles_available()': the gate has drifted off the emitter"
    )
    assert 'if not callable(handles.get("cut_redraw")):' not in source, (
        "the old 'if not callable(handles.get(\"cut_redraw\")):' early return is "
        "back in the file: it withholds both marker boxes on the |E| volume "
        "page, whose discs the volume layer repaints"
    )

    box = '("show_load_plane", "Show Load Plane (red)")'
    assert box in body, "the load plane box is not emitted here"
    assert body.index("_plane_toggles_available()") < body.index(box), (
        "the gate is asked AFTER the load plane box is emitted: the box would be "
        "created before anything decided the page can hide it"
    )


def test_both_marker_plane_boxes_are_still_emitted():
    """(d) The red load plane and the purple S11 port plane, once each."""
    source = _source()
    tree = ast.parse(source)

    emitters = _function_defs(tree, "_emit_vector_toggle")
    assert len(emitters) == 1, (
        f"{len(emitters)} 'def _emit_vector_toggle' in {POC_APP.name}"
    )
    body = _body(source, emitters[0])

    for state_name, label in (
        ("show_load_plane", "Show Load Plane (red)"),
        ("show_port_plane", "Show S11 Port Plane (purple)"),
    ):
        literal = f'("{state_name}", "{label}")'
        occurrences = source.count(literal)
        assert occurrences == 1, (
            f"{POC_APP.name} emits {literal} {occurrences} time(s), not once: a "
            "fourth marker box would be a control nobody wired"
        )
        assert literal in body, (
            f"{literal} is emitted somewhere other than "
            "'_emit_vector_toggle', which is the only entry point registered and "
            "called for these controls"
        )
