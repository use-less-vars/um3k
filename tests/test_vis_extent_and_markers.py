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

The four claims appended below are the P2b repair, made on the same terms:

(e) the flat field sheets are drawn UNLIT - every ``add_mesh`` call that is a
    turbo, flat-shaded field sheet passes ``lighting=False``;
(f) those calls are the three the page really draws (the boot sheets, the mode
    picture and the rebuilt sheets), and NOT the |E| volume layer's translucent
    cut sheets, which are a different picture and are tuned by opacity;
(g) the one-shot actor dump is defined once and called once, from inside an
    ``if rendered:`` branch - a scene listed before the draw is half-built;
(h) that dump is opt-in through ``POC_DUMP_ACTORS``, resolved ONCE at import,
    and it spends its one-shot flag BEFORE it prints, so a dump that raises
    halfway is never retried on every tick.

The one claim appended below is the P2c repair, on the same terms:

(i) every flat field sheet is drawn on a VISIBLE mesh - it passes
    ``edge_color=VIS_EDGE_COLOR`` and ``line_width=VIS_EDGE_WIDTH`` on its own
    call, those two constants keep the values the lattice was tuned to, and NO
    other ``add_mesh`` call passes them, because the geometry under the sheets
    already draws its own edges.
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


# ---------------------------------------------------------------------------
# P2b: the flat field sheets are drawn UNLIT, and the scene can be dumped ONCE.
#
# Every claim below is structural, for the reason in the module docstring: the
# module cannot be imported here, so the FILE TEXT is the only evidence there
# is. The two behaviours are invisible to the other suites - a lit sheet is a
# valid ``add_mesh`` call and a dump that never fires raises nothing.
# ---------------------------------------------------------------------------


def _add_mesh_segments(source: str) -> list:
    """Every ``add_mesh(`` call as ``(line_number, segment_text)``.

    The segment is cut with a balanced-paren scan from the call's OWN opening
    bracket, so a claim about "this call" cannot be satisfied by an argument
    that belongs to the NEXT call - which is exactly what a whole-file search
    for the token would allow.
    """
    segments = []
    token = "add_mesh("
    index = 0
    while True:
        found = source.find(token, index)
        if found == -1:
            return segments
        depth = 0
        for position in range(found + len(token) - 1, len(source)):
            char = source[position]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    line = source.count("\n", 0, found) + 1
                    segments.append((line, source[found : position + 1]))
                    index = position + 1
                    break
        else:  # an unbalanced call: report what was read, do not loop forever
            return segments


def _scalar_sheets(source: str) -> list:
    """The FIELD sheets: a turbo, FLAT-SHADED ``add_mesh`` call.

    The filter is the claim, not a line range. The |E| volume layer's cut
    sheets are ``add_mesh`` calls too, but they carry ``opacity=0.75`` and no
    ``smooth_shading`` at all - they are a translucent VOLUME slice, tuned by
    that opacity, and they are not what P2b is about. ``smooth_shading=False``
    is the same statement as "this is a field of values on a grid", so it is
    what tells the two pictures apart.
    """
    return [
        (line, segment)
        for line, segment in _add_mesh_segments(source)
        if 'cmap="turbo"' in segment and "smooth_shading=False" in segment
    ]


def _enclosing_name(tree: ast.Module, line: int):
    """The name of the INNERMOST function whose span contains ``line``."""
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append(
                (
                    (node.end_lineno or node.lineno) - node.lineno,
                    node.lineno,
                    node.end_lineno or node.lineno,
                    node.name,
                )
            )
    spans.sort()
    for _size, start, end, name in spans:
        if start <= line <= end:
            return name
    return None


def test_the_flat_field_sheets_are_drawn_unlit():
    """(e) Every field sheet passes ``lighting=False``, on its own call.

    Page A never lit its sheets: the value is read off the COLOUR against the
    bar, and a surface normal in the light path dims exactly that colour. A lit
    sheet is not an error, which is why nothing else catches it.
    """
    source = _source()
    sheets = _scalar_sheets(source)
    assert len(sheets) == 3, (
        f"{len(sheets)} flat field sheets found at lines "
        f"{[line for line, _ in sheets]}, not three: the boot sheets, the mode "
        "picture and the rebuilt sheets are the three the page draws, so a "
        "different number means the selection has drifted off them"
    )
    missing = [line for line, segment in sheets if "lighting=False" not in segment]
    assert not missing, (
        f"the field sheet call(s) at line(s) {missing} are drawn LIT: page A "
        "paints a flat field, and light would dim the colour the reader is "
        "being asked to compare against the bar"
    )


def test_the_unlit_sheets_are_the_three_the_page_draws():
    """(f) Those calls are the boot sheets, the mode picture, the rebuild.

    Named by their ENCLOSING function rather than by line number, so the claim
    survives unrelated edits above them - and so that a fourth scenic
    ``add_mesh`` slipping into the selection is caught by where it lives.
    """
    source = _source()
    tree = ast.parse(source)
    owners = [_enclosing_name(tree, line) for line, _ in _scalar_sheets(source)]
    assert owners == ["run_web_vis", "_draw_mode_picture", "_rebuild_sheets"], (
        f"the unlit sheets are drawn by {owners}, not by the page's three field "
        "sites: the boot sheets live directly in 'run_web_vis', the mode picture "
        "in '_draw_mode_picture' and the rebuilt dump in '_rebuild_sheets'"
    )
    assert not any("volume" in (name or "") for name in owners), (
        f"a |E| volume layer draw ({owners}) is in the selection: its translucent "
        "cut sheets are a different picture, tuned by opacity=0.75, and lighting "
        "was never what they were judged by"
    )


def test_the_actor_dump_is_called_once_from_the_rendered_tick():
    """(g) One definition, one call, inside ``if rendered:``.

    The gate is the point: ``_tick_render_and_push`` only QUEUES the draw, so a
    dump taken anywhere else can list a half-built scene and make a real defect
    look like a timing artefact.
    """
    source = _source()
    tree = ast.parse(source)

    dumps = _function_defs(tree, "_dump_actors_once")
    assert len(dumps) == 1, (
        f"{len(dumps)} 'def _dump_actors_once' in {POC_APP.name} at lines "
        f"{[node.lineno for node in dumps]}, not one"
    )

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_dump_actors_once"
    ]
    assert len(calls) == 1, (
        f"{len(calls)} call(s) to '_dump_actors_once' at lines "
        f"{[node.lineno for node in calls]}, not one: a second call site is a "
        "second description of the scene, free to disagree with the first"
    )
    call = calls[0]

    gates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "rendered"
        and node.lineno <= call.lineno <= (node.end_lineno or node.lineno)
    ]
    assert gates, (
        f"the actor dump at line {call.lineno} is not inside an 'if rendered:' "
        "branch: it would describe a scene whose first frame has not drawn yet"
    )


def test_the_actor_dump_is_opt_in_at_import_and_spent_before_it_prints():
    """(h) ``POC_DUMP_ACTORS`` resolved once, and the flag set before the print.

    Both halves matter. An environment read INSIDE the helper is a switch that
    can change its answer between ticks; a flag set AFTER the first line is a
    dump that repeats for ever if it ever raises halfway.
    """
    source = _source()
    tree = ast.parse(source)

    wanted = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_ACTOR_DUMP_WANTED"
            for target in node.targets
        )
    ]
    assert len(wanted) == 1, (
        f"{len(wanted)} MODULE-LEVEL '_ACTOR_DUMP_WANTED' assignment(s) at lines "
        f"{[node.lineno for node in wanted]}, not one: the switch is resolved "
        "once, at import, so no two ticks can describe different scenes"
    )
    assert "POC_DUMP_ACTORS" in _body(source, wanted[0]), (
        "the module-level switch does not read POC_DUMP_ACTORS: the dump is "
        "either unreachable or reachable through a name nothing sets"
    )

    predicates = _function_defs(tree, "_actor_dump_wanted")
    assert len(predicates) == 1, (
        f"{len(predicates)} 'def _actor_dump_wanted' in {POC_APP.name}"
    )
    predicate_body = _body(source, predicates[0])
    assert "_ACTOR_DUMP_WANTED" in predicate_body, (
        "'_actor_dump_wanted' does not answer from the module constant: the "
        "environment would be read per call"
    )
    assert "os.environ" not in predicate_body, (
        "'_actor_dump_wanted' reads os.environ: the switch must be resolved once"
    )

    dumps = _function_defs(tree, "_dump_actors_once")
    assert len(dumps) == 1, (
        f"{len(dumps)} 'def _dump_actors_once' in {POC_APP.name}"
    )
    body = _body(source, dumps[0])
    assert "os.environ" not in body, (
        "the dump re-reads the environment: POC_DUMP_ACTORS is resolved once at "
        "import (see _ACTOR_DUMP_WANTED), and a per-call read is a switch that "
        "can turn itself off between the gate and the print"
    )
    assert 'handles["actors_dumped"]' in body, (
        "the dump has no once-flag: it would print the scene on every tick that "
        "draws a frame"
    )
    spent = body.index('handles["actors_dumped"] = True')
    first_print = body.index("print(")
    assert spent < first_print, (
        "the once-flag is set AFTER the first line is printed: a dump that "
        "raises halfway is retried on every tick, at full volume"
    )


# ---------------------------------------------------------------------------
# P2c: the field sheet is drawn on a MESH THE READER CAN SEE - a pale lattice.
#
# A flat turbo field is one colour per cell, so on screen the mesh is the only
# evidence of how coarse the discretisation is. P2c asks for that evidence: the
# edge colour and width on every sheet, and on NOTHING else - the geometry under
# the sheets already draws its own edges, and a second set over it is noise.
# ---------------------------------------------------------------------------


def test_every_field_sheet_carries_the_cell_lattice_and_nothing_else_does():
    """(i) The three field sheets pass the lattice constants; no other call does.

    The colour and the width are named CONSTANTS rather than literals at the
    call sites, so the plane can be retuned in one place - which is only true if
    the call sites pass those NAMES and not a copy of their values.
    """
    source = _source()
    tree = ast.parse(source)
    sheets = _scalar_sheets(source)
    assert len(sheets) == 3, (
        f"{len(sheets)} flat field sheets found at lines "
        f"{[line for line, _ in sheets]}, not three: the selection has drifted "
        "off the page's three field sites, so the claims below are about some "
        "other call"
    )

    constants = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    for name in ("VIS_SHOW_EDGES", "VIS_EDGE_COLOR", "VIS_EDGE_WIDTH"):
        assert name in constants, (
            f"no MODULE-LEVEL {name!r} assignment in {POC_APP.name}: the sheet "
            "call sites pass a name that does not resolve to the lattice, or a "
            "literal that cannot be retuned in one place"
        )
    assert ast.literal_eval(constants["VIS_SHOW_EDGES"]) is True, (
        "'VIS_SHOW_EDGES' is not True: the lattice the user asked to see is "
        "switched off, and a sheet with no edges looks exactly like a field "
        "whose cells are too small to matter - the reading it must not invite"
    )
    assert ast.literal_eval(constants["VIS_EDGE_COLOR"]) == "#b8c4d0", (
        f"'VIS_EDGE_COLOR' is {ast.literal_eval(constants['VIS_EDGE_COLOR'])!r}, "
        "not the pale grey the lattice was tuned to: a near-black edge over a "
        "turbo field reads as a LATTICE of its own, not as the mesh the field "
        "is drawn on"
    )
    assert ast.literal_eval(constants["VIS_EDGE_WIDTH"]) == 0.4, (
        f"'VIS_EDGE_WIDTH' is {ast.literal_eval(constants['VIS_EDGE_WIDTH'])!r}, "
        "not 0.4: at a readable width the edges start to win against the field "
        "they are only supposed to describe"
    )

    missing = [
        line
        for line, segment in sheets
        if "edge_color=VIS_EDGE_COLOR" not in segment
        or "line_width=VIS_EDGE_WIDTH" not in segment
    ]
    assert not missing, (
        f"the field sheet call(s) at line(s) {missing} do not pass BOTH "
        "edge_color=VIS_EDGE_COLOR and line_width=VIS_EDGE_WIDTH on their OWN "
        "call: the mesh is invisible again there, or its width is vtk's default"
    )

    # The mode picture is the ONE sheet that keeps ``show_edges=False``: it is
    # the coarse companion view, and P2c asked for the mesh on the field sheets,
    # not for a second lattice in a picture that is read as a shape. Named here
    # rather than left implicit, so that turning it on later is a decision.
    off = [line for line, segment in sheets if "show_edges=False" in segment]
    assert len(off) == 1, (
        f"{len(off)} field sheet(s) at line(s) {off} have show_edges=False; "
        "exactly one is expected - the mode picture - and any other is a sheet "
        "whose mesh is still hidden"
    )
    owner = _enclosing_name(tree, off[0])
    assert owner == "_draw_mode_picture", (
        f"the sheet with show_edges=False is drawn by {owner!r}, not by "
        "'_draw_mode_picture': the lattice is missing from a sheet that is "
        "supposed to carry it"
    )

    strays = [
        line
        for line, segment in _add_mesh_segments(source)
        if not ('cmap="turbo"' in segment and "smooth_shading=False" in segment)
        and ("VIS_EDGE_COLOR" in segment or "VIS_EDGE_WIDTH" in segment)
    ]
    assert not strays, (
        f"the non-sheet add_mesh call(s) at line(s) {strays} pass the sheet "
        "lattice constants: the geometry under the sheets already draws its own "
        "edges, and a second set over it is noise the reader has to filter out"
    )
