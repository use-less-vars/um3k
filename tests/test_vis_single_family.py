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
        'if item["family"] in _visible_families(mode)',
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

    private = _lines_with(source, '["family"] == mode') + _lines_with(
        source, 'get("family") == mode'
    )
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

    # One definition plus the six sites above.
    total = source.count("_visible_families(")
    assert total == 7, (
        f"'_visible_families(' appears {total} time(s): one definition and the "
        "six write sites (sheet loop, mode picture, quiver, two draw helpers, "
        "plane-bar pick)."
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
