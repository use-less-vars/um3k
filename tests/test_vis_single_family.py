"""One family on screen means ONE place says which families are drawn.

WHY THIS IS A SOURCE-LEVEL TEST, and not a render: ``server/poc_app.py`` builds a
trame application on import and needs a GL context that this image does not
have, so the module cannot be imported here at all - every claim below is made
on the FILE TEXT (``ast`` for the function shapes, the raw text for the write
sites), exactly as ``tests/test_vis_extent_and_markers.py`` makes its structural
claims. A failure therefore points at the line that lost the behaviour, and no
part of this file needs a plotter to run.

The defect this pins: the web-vis page shows the sheets of ONE family (``ycut``
OR ``xcut``) at a time, and "which families are drawn?" used to be answered
privately at every write site - ``entry["family"] == mode`` in the sheet loop,
``state.mode == "xcut"`` in the two draw helpers. A private opinion is exactly
how a second plane ends up left visible on a frame it was never drawn for. Each
claim below is one half of that repair, and none of them is visible to the other
suites:

* ``_visible_families(mode)`` is the ONE author of the answer, and it derives the
  answer from ``state.show_other_family`` (default False) rather than from a
  second name;
* no write site compares a family to ``mode`` any more, ``state.mode`` is
  written in exactly one place, and the coercion that keeps the name one of TWO
  families is still there;
* the three field pictures (boot sheets, mode picture, rebuilt sheets) still
  carry their own colour limits and the single boot-time plane bar.
"""

from __future__ import annotations

import ast
import re
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


def _code_only(node) -> str:
    """The node's statements with the docstring dropped, unparsed."""
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return "\n".join(ast.unparse(statement) for statement in body)


def _lines_with(source: str, needle: str) -> list:
    """Every line NUMBER whose text contains ``needle``."""
    return [
        number
        for number, text in enumerate(source.splitlines(), start=1)
        if needle in text
    ]


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
    """The FIELD pictures: a turbo, FLAT-SHADED ``add_mesh`` call.

    The filter is the claim, not a line range. The |E| volume layer's cut
    sheets are ``add_mesh`` calls too, but they carry ``opacity=0.75`` and no
    ``smooth_shading`` at all, so they are not field pictures of |Ez|.
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


# ---------------------------------------------------------------------------
# The write sites that used to answer "is this family drawn?" privately.
# ``needle`` is the exact line text, ``expected`` the number of such lines, and
# ``owners`` the function each MUST be inside, innermost first.
# ---------------------------------------------------------------------------
FAMILY_SITES = (
    (
        'visible = entry["family"] in _visible_families(mode)',
        1,
        ("_show",),
    ),
    (
        'mode_entry.get("family") in _visible_families(mode)',
        1,
        ("_show",),
    ),
    (
        'quiver_entry.get("family") in _visible_families(mode)',
        1,
        ("_show",),
    ),
    (
        'actor.visibility = "xcut" in _visible_families(state.mode)',
        2,
        ("_draw_mode_picture", "_draw_mode_quiver"),
    ),
    (
        'visible = _visible_families(mode)',
        1,
        ("_swap_scalar_bar",),
    ),
)


def test_the_visible_families_helper_is_the_one_author():
    """(a) ONE ``_visible_families``, reading the flag and nothing else."""
    source = _source()
    tree = ast.parse(source)
    defs = _function_defs(tree, "_visible_families")
    assert len(defs) == 1, (
        f"{POC_APP.name} defines '_visible_families' {len(defs)} time(s): the "
        "set of drawn families must have ONE author, or the sheet loop, the "
        "mode picture, the quiver and the plane bar can each answer it "
        "differently - which is the defect this file pins."
    )
    node = defs[0]
    body = _body(source, node)
    code = _code_only(node)

    assert "state.show_other_family" in code, (
        "'_visible_families' does not read ``state.show_other_family``: the "
        "second family then has no switch, and some write site would have to "
        "guess it again.\n" + body
    )
    assert 'state.show_other_family = False' in source, (
        "``state.show_other_family`` is never initialised: the helper reads it "
        "on the page's first draw, so a missing default is a boot-time crash."
    )
    assert "frozenset(" in code, (
        "'_visible_families' does not return a set, so its callers cannot ask "
        "membership.\n" + body
    )

    # Two families only, both named here, and the second one DERIVED from the
    # argument - a second hard-coded family name is how the two drift apart.
    named = set(re.findall("[\"']([A-Za-z0-9_]+)[\"']", code))
    assert named == {"ycut", "xcut"}, (
        "'_visible_families' names "
        f"{sorted(named)}: the page has exactly two families, 'ycut' and "
        "'xcut', and the one not being switched to must be derived.\n" + body
    )

    # Pure: a question every caller asks must not move the state it asks about.
    assert not re.search(r"state\.[A-Za-z_]+ *=[^=]", code), (
        "'_visible_families' WRITES state; it must only read it.\n" + body
    )


def test_the_other_family_is_a_flag_not_a_second_name():
    """(b) No private family comparison, and ONE write of ``state.mode``."""
    source = _source()
    tree = ast.parse(source)

    # ONE comparison of a sheet's family to ``mode`` survives, and it is not a
    # visibility question: the plane bar reads from the PRIMARY family's sheet,
    # and "which family is primary" is ``mode`` by definition. Everywhere else
    # the two are compared only to ask "is this family drawn?", which has one
    # author - so this reports a stray, not that pick (pinned by
    # test_the_plane_legend_is_the_primary_family_s_own).
    private = [
        line
        for line in _lines_with(source, '["family"] == mode')
        + _lines_with(source, 'get("family") == mode')
        if _enclosing_name(tree, line) != "_swap_scalar_bar"
    ]
    assert private == [], (
        "these line(s) still answer 'is this family drawn?' privately instead "
        f"of asking _visible_families(): {private}"
    )

    writes = _lines_with(source, "state.mode = mode")
    assert len(writes) == 1, (
        f"'state.mode = mode' appears {len(writes)} time(s) at {writes}: the "
        "current family is recorded in exactly ONE place, _show(), so every "
        "reader sees the same tick's decision."
    )
    owner = _enclosing_name(tree, writes[0])
    assert owner == "_show", (
        f"'state.mode = mode' at line {writes[0]} is inside {owner!r}, not "
        "'_show': the mode is the thing _show was asked to show."
    )

    coercion = _lines_with(
        source, 'mode = "xcut" if mode == "xcut" else "ycut"'
    )
    assert len(coercion) == 1, (
        "the coercion of the mode argument to one of the two known families is "
        f"gone (found {coercion}): _show would then accept a family nothing "
        "was built for and hide every sheet."
    )
    assert _enclosing_name(tree, coercion[0]) == "_show", (
        f"the mode coercion at line {coercion[0]} left _show()"
    )


def test_every_family_visibility_write_asks_the_helper():
    """(c) Each edited write site asks membership, in the function it belongs to."""
    source = _source()
    tree = ast.parse(source)

    for needle, expected, owners in FAMILY_SITES:
        lines = _lines_with(source, needle)
        assert len(lines) == expected, (
            f"expected {expected} line(s) reading {needle!r}, found "
            f"{len(lines)} at {lines}: this is a visibility WRITE site, and a "
            "site that stops asking _visible_families() draws a family nobody "
            "chose."
        )
        found = tuple(_enclosing_name(tree, line) for line in lines)
        assert found == owners, (
            f"{needle!r} is inside {found}, expected {owners}: the rule is "
            "pinned to the function that applies it."
        )

    # One definition plus the six sites above, plus the camera latch and the
    # plane bar's own latch.
    total = source.count("_visible_families(")
    assert total == 9, (
        f"'_visible_families(' appears {total} time(s): one definition, the "
        "six write sites (sheet loop, mode picture, quiver, two draw helpers, "
        "plane-bar pick), the camera latch's family set and the plane bar's."
    )

    # The sweep: no OTHER actor visibility write keeps a family opinion.
    sweep = [
        (number, text)
        for number, text in enumerate(source.splitlines(), start=1)
        if ".visibility =" in text
        and ("family" in text or "state.mode" in text)
    ]
    offenders = [(number, text.strip()) for number, text in sweep if "_visible_families(" not in text]
    assert offenders == [], (
        "these actor-visibility writes still decide the family themselves "
        f"instead of asking _visible_families(): {offenders}"
    )


def test_the_three_field_pictures_keep_their_own_colour_limits():
    """(d) Three field pictures, each with explicit ``clim``; the dump's two
    builders share the ONE dump range, the mode picture keeps its own."""
    source = _source()
    tree = ast.parse(source)
    sheets = _scalar_sheets(source)
    assert len(sheets) == 3, (
        "the page builds THREE field pictures (the boot sheets' loop, the mode "
        f"picture and the rebuild loop); found {len(sheets)} at "
        f"{[line for line, _ in sheets]}"
    )
    for line, segment in sheets:
        assert "clim=(" in segment, (
            f"field picture at line {line} passes no explicit colour limits: "
            "an auto range would move the colours frame to frame."
        )
    by_owner = {}
    for line, segment in sheets:
        owner = _enclosing_name(tree, line)
        assert owner not in by_owner, (
            f"two field pictures inside {owner!r}: the pin below assumes one "
            "per builder."
        )
        by_owner[owner] = (line, segment)
    assert set(by_owner) == {"run_web_vis", "_draw_mode_picture", "_rebuild_sheets"}, (
        f"the field pictures moved: {sorted(by_owner)}"
    )
    for owner in ("run_web_vis", "_rebuild_sheets"):
        line, segment = by_owner[owner]
        assert "clim=(vmin, vmax)" in segment, (
            f"the |Ez| sheet built in {owner} (line {line}) no longer passes "
            "the dump's ONE colour range: the y-cut and both x-cut sheets must "
            "share it, or the same field changes colour with the family."
        )
    line, segment = by_owner["_draw_mode_picture"]
    assert "clim=(vmin, vmax)" not in segment, (
        f"the mode picture (line {line}) borrowed the dump's colour range: |E| "
        "of the mode is a different field on a different scale."
    )
    assert "clim=(0.0," in segment, (
        f"the mode picture (line {line}) lost its own limits: it must be scaled "
        "from its own array."
    )


def test_the_boot_sheets_still_join_one_plane_bar():
    """(e) The single build-time bar, ``show_scalar_bar=(family == "ycut")``."""
    source = _source()
    assert source.count('show_scalar_bar=(family == "ycut")') == 1, (
        "the boot sheets must still let exactly ONE family's sheet build the "
        "plane bar (the x-cut sheets make none), found "
        f"{source.count('show_scalar_bar=(family == \"ycut\")')} occurrence(s)."
    )
    sheets = _scalar_sheets(source)
    owning = [
        (line, segment)
        for line, segment in sheets
        if 'show_scalar_bar=(family == "ycut")' in segment
    ]
    assert len(owning) == 1, (
        "the build-time bar argument is on "
        f"{len(owning)} of the three field pictures: it belongs to the boot "
        "sheets' call only."
    )
    for line, segment in sheets:
        if 'show_scalar_bar=(family == "ycut")' in segment:
            continue
        assert "show_scalar_bar=False" in segment, (
            f"field picture at line {line} builds a bar of its own: the page "
            "leaves exactly one plane bar standing (_swap_scalar_bar)."
        )


# ---------------------------------------------------------------------------
# The sheet loop itself: EVERY sheet paints its OWN family's stored frame.
# The loop is sliced out of ``_show`` by AST rather than by line number - the
# module is 19k lines and a loop that MOVED must not let a pin below pass by
# accident, nor fail for the wrong reason.
# ---------------------------------------------------------------------------
def _sheet_loop_code(source: str) -> str:
    """The sheet loop's code, comment lines dropped.

    The loop is the ``for`` over ``sheets.items()`` inside ``_show``: found by
    AST so a pin cannot be satisfied by an unrelated line elsewhere in the
    module, and quoted from the ORIGINAL source (not ``ast.unparse``) so a
    needle written here is a needle in the file. Comments are dropped because
    they QUOTE the old expressions while explaining why they are gone.
    """
    tree = ast.parse(source)
    shows = _function_defs(tree, "_show")
    assert len(shows) == 1, (
        f"{POC_APP.name} defines '_show' {len(shows)} time(s): the sheet loop "
        "these pins slice lives in the one function that draws a tick."
    )
    loops = [
        node
        for node in ast.walk(shows[0])
        if isinstance(node, ast.For) and "sheets.items()" in ast.unparse(node.iter)
    ]
    assert len(loops) == 1, (
        f"'_show' has {len(loops)} loop(s) over 'sheets.items()': every field "
        "frame is placed by that ONE loop, and the pins below assume one."
    )
    raw = ast.get_source_segment(source, loops[0]) or ""
    return "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith("#")
    )


def test_each_sheet_paints_its_own_family_layer():
    """(f) The per-sheet frame comes from the sheet's OWN family's layer."""
    code = _sheet_loop_code(_source())
    assert 'entry.get("family")' in code, (
        "the sheet loop no longer reads the sheet's own family, so it cannot "
        "resolve a layer per family.\n" + code
    )
    assert "timeline.layer_index(" in code, (
        "the sheet loop does not ask the timeline for the sheet's own layer: "
        "that lookup is what maps a position to THIS family's stored sample, "
        "and resolving it once above the loop is how a second family is handed "
        "another family's frame.\n" + code
    )
    for private in ('["family"] == mode', 'get("family") == mode'):
        assert private not in code, (
            "the sheet loop answers 'is this family drawn?' privately with "
            f"{private!r} instead of asking _visible_families().\n" + code
        )


def test_both_frame_picks_in_the_sheet_loop_use_the_sheet_index():
    """(g) ``plane_index`` is the PRIMARY family's frame and must not leak."""
    code = _sheet_loop_code(_source())
    assert "plane_index" not in code, (
        "the sheet loop reads ``plane_index``: that index is the PRIMARY "
        "family's frame (the one the sim-time label and the |E| layer read), "
        "so a sheet of the second family would be painted from the primary's "
        "position. Each sheet resolves ``sheet_index`` for itself.\n" + code
    )
    picks = code.count("min(sheet_index,")
    assert picks == 2, (
        f"the sheet loop picks a frame with ``min(sheet_index, ...)`` {picks} "
        "time(s), expected 2 - the scalars it uploads and the number its "
        "profile row reports: both must clamp the SAME per-sheet index.\n"
        + code
    )


def test_the_sheet_loop_skips_only_what_it_cannot_paint():
    """(h) Two ``continue``s, each the whole body of a named guard."""
    code = _sheet_loop_code(_source())
    lines = code.splitlines()
    continues = [number for number, text in enumerate(lines) if text.strip() == "continue"]
    assert len(continues) == 2, (
        f"the sheet loop continues {len(continues)} time(s), expected 2: a "
        "sheet whose family is not on screen, and a dump with no frame for it. "
        "An extra one is a VISIBLE sheet going without scalars.\n" + code
    )
    guards = []
    for number in continues:
        before = [text.strip() for text in lines[:number] if text.strip()]
        guards.append(before[-1])
    assert guards == ["if not visible:", "if array.shape[0] == 0:"], (
        f"the sheet loop's ``continue``s are guarded by {guards}: the only two "
        "reasons a sheet may be skipped are that its family is not on screen "
        "and that the dump holds no frame for it.\n" + code
    )


# ---------------------------------------------------------------------------
# The camera latch: the view is framed for a SET of families, not for a flag.
# ---------------------------------------------------------------------------
def _assigned_value(source: str, function: str, name: str) -> str:
    """The source of the expression assigned to ``name`` inside ``function``."""
    tree = ast.parse(source)
    for node in _function_defs(tree, function):
        for child in ast.walk(node):
            if isinstance(child, ast.Assign) and any(
                getattr(target, "id", None) == name for target in child.targets
            ):
                return ast.get_source_segment(source, child.value) or ""
    return ""


def test_the_camera_latch_names_the_families_it_framed():
    """(i) ``camera_framed_for`` records WHICH families the view was framed for.

    A boolean says the camera was framed for *something*: switch the second
    plane on and the first plane's framing quietly stays, leaving half the
    field outside the picture. The latch is the family SET, so the flag and
    the mode are both compared on every tick - and the bare board records the
    empty set, which no flag can change.
    """
    source = _source()
    assert 'handles["camera_framed"]' not in source, (
        "a bare ``handles[\"camera_framed\"]`` flag survives at "
        f"{_lines_with(source, 'handles[\"camera_framed\"]')}: a boolean "
        "cannot say which families the camera was framed for, so a second "
        "plane would be drawn outside the view."
    )
    writes = _lines_with(source, 'handles["camera_framed_for"]')
    assert len(writes) == 3, (
        f"``handles[\"camera_framed_for\"]`` is written at {writes}: exactly "
        "three places own it - the bare board's empty set, the successful "
        "reframe, and the solve's reset."
    )
    reads = _lines_with(source, 'handles.get("camera_framed_for")')
    assert len(reads) == 1, (
        f"``handles.get(\"camera_framed_for\")`` is read at {reads}: the "
        "reframe guard is the ONE place that decides, and a second reader "
        "would be a second opinion about the camera."
    )
    guard = source.splitlines()[reads[0] - 1]
    assert "mode_changed" in guard, (
        "the reframe guard no longer re-frames on a mode change, which is the "
        f"one case a stale latch cannot cover:\n{guard}"
    )
    value = _assigned_value(source, "_show", "framed_for")
    assert "_visible_families(" in value, (
        "the family set the camera latches is not derived from "
        f"_visible_families():\n{value}"
    )
    assert "sheets" in value, (
        "the latched set is not the families of the sheets on this page, so a "
        f"page with no sheet would be re-framed by a flag it cannot draw:\n{value}"
    )
    assert "framed_for" in source.splitlines()[reads[0] - 1], (
        "the reframe guard compares something other than the latched set at "
        f"line {reads[0]}:\n{guard}"
    )


# ---------------------------------------------------------------------------
# The plane legend: ONE bar, for the PRIMARY family, rebuilt when the SET moves.
# ---------------------------------------------------------------------------
def _code_text(source: str, node) -> str:
    """The node's statements quoted from the FILE, docstring and comments gone.

    The docstring QUOTES the handles the pins below count, and a comment can
    name a line that was replaced, so a count taken over the whole body would
    pass on prose. What is left here is code the interpreter runs.
    """
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    raw = "\n".join(
        ast.get_source_segment(source, statement) or "" for statement in body
    )
    return "\n".join(
        text for text in raw.splitlines() if not text.strip().startswith("#")
    )


def test_the_plane_legend_is_the_primary_family_s_own():
    """(j) The bar reads the PRIMARY family's sheet, and the latch is honest.

    The bar used to take the FIRST sheet whose family was visible. With the
    second plane switched on that is not a decision at all - the order of
    ``sheets`` decides it - so the legend described a plane picked by dict
    insertion. ``mode`` is the plane the view is turned to, so ``mode`` is the
    family the bar describes. The latch records the SET that was described and
    is written AFTER the bar is standing: a rebuild that raises records nothing,
    so the next tick tries again instead of believing a bar that was never
    built.
    """
    source = _source()
    defs = _function_defs(ast.parse(source), "_swap_scalar_bar")
    assert len(defs) == 1, (
        f"{POC_APP.name} defines '_swap_scalar_bar' {len(defs)} time(s): the "
        "page leaves exactly ONE plane bar standing, so there is one place "
        "that rebuilds it."
    )
    code = _code_text(source, defs[0])
    assert "next(" not in code, (
        "the bar is still the FIRST sheet whose family is visible: with a "
        "second family switched on, which sheet that is depends on the order "
        "of ``sheets``, not on the plane the view is turned to.\n" + code
    )
    assert 'item["family"] == mode' in code, (
        "the bar no longer picks the PRIMARY family's sheet, so the numbers "
        "it shows belong to whichever sheet happened to come first.\n" + code
    )
    recorded = code.count('handles["bar_for"]')
    assert recorded == 2, (
        f"``handles[\"bar_for\"]`` is written {recorded} time(s), expected 2 - "
        "the settled no-sheet answer and the bar actually standing - so one "
        "of the two branches leaves the latch claiming a set it did not "
        "draw.\n" + code
    )
    tail = code.rsplit("except", 1)[-1]
    assert 'handles["bar_for"]' not in tail, (
        "the failure branch records the family set: a bar that could not be "
        "built would then be believed for the rest of the session, and the "
        "rebuild that would fix it never happens.\n" + code
    )


def test_the_plane_legend_is_rebuilt_when_the_family_set_changes():
    """(k) The guard compares the SET, not only the mode.

    Switching the second family on changes what is drawn WITHOUT changing
    ``mode``, so a guard that only knew ``mode_changed`` would leave a bar
    describing a set that is no longer on screen. The guard reads the same
    ``_visible_families(mode)`` that ``_swap_scalar_bar`` writes, so the two
    cannot disagree about when the bar is current.
    """
    source = _source()
    tree = ast.parse(source)
    lines = source.splitlines()

    calls = [
        number
        for number, text in enumerate(lines, start=1)
        if "_swap_scalar_bar(mode)" in text
    ]
    assert len(calls) == 1, (
        f"'_swap_scalar_bar(mode)' is called at {calls}, expected once: the "
        "_show() guard is the ONE decision about a mode change, and the "
        "solve's rebuild passes ``mode or state.mode``."
    )
    owner = _enclosing_name(tree, calls[0])
    assert owner == "_show", (
        f"the guarded rebuild at line {calls[0]} is inside {owner!r}, not "
        "'_show': the bar is part of drawing a tick."
    )
    guard = ""
    for text in reversed(lines[: calls[0] - 1]):
        if text.strip().startswith("if "):
            guard = text.strip()
            break
    assert "bar_for" in guard, (
        "the rebuild guard names nothing about the family SET, so switching "
        "the second plane on would leave the old bar standing:\n" + guard
    )
    assert "mode_changed" in guard, (
        "the rebuild guard no longer re-builds on a mode change:\n" + guard
    )

    # The boot sheets must still let ONE family build the plane bar: the
    # rebuild above replaces that bar, it does not hand every sheet its own.
    boot = [
        segment
        for _line, segment in _add_mesh_segments(source)
        if 'show_scalar_bar=(family == "ycut")' in segment
    ]
    assert len(boot) == 1, (
        f"{len(boot)} add_mesh call(s) build the plane bar at boot, expected "
        "exactly one: with none, the first tick has no bar to replace; with "
        "more, the page starts with bars for families it is not drawing."
    )
