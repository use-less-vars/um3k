"""n_line's bounds are the solver's own mesh, and the box says so where it is typed.

WHY THIS IS A SOURCE-LEVEL TEST, and not a render: ``server/poc_app.py`` builds
a trame application on import and needs a GL context this image does not have,
so the module cannot be imported here at all - every claim below is made on the
FILE TEXT (``ast`` for the function shapes, the raw text for the call sites),
exactly as ``tests/test_vis_extent_and_markers.py`` makes its structural claims.
A failure therefore points at the line that lost the behaviour.

The n_line box is the one control on the Run Config form whose value is a MESH,
so its range is physics and not taste: too few cells and the grid cuts the near
cut / drops the load column, too many and the press costs more than anyone asked
for. The claims, one per test:

(a) the seven module-level constants are the numbers derived from the mesh -
    floor 43, ceiling 116, reference 54, reference cells 289168, nx offset 8,
    ny 212, nz 22 - and the reference board really is
    ``(8 + 54) * 212 * 22`` cells, so the three numbers cannot drift apart;
(b) those UI numbers are the SOLVER's mesh, not a second copy of it: the ny
    total is ``2 * n_pml + n_strip + 2 * n_clean`` and the nz total is
    ``n_sub + n_air + n_top`` from ``emfit/studies.py``, and the nx offset is
    ``n_pml + n_ref`` - the solver's constants are read from the solver, never
    written as literals here, so this test fails the day one of them moves;
(c) ``_run_n_line_board`` is defined ONCE and its body really computes the
    board it claims: the nx offset added to the value, all three extents, the
    thousands-separated cell count and the ratio to the reference mesh, plus the
    four sentences the page can show (not a whole number / ceiling / floor /
    shipped default);
(d) the range is enforced AFTER ``RunConfig`` has filled the defaults in - the
    one ``RunConfig(`` call comes before the ``RUN_N_LINE_MIN``/``_MAX``
    comparison, so a blank box (54) and a typed 54 are the same press - and the
    refusal is a ``ValueError("run config refused: ...")`` that names the board
    through that same helper;
(e) the box has a ``@state.change("run_n_line")`` handler, it is the only one,
    and it writes ``state.run_n_line_note`` from that same helper; the note is
    also set once at boot from the form's own default, so the first paint has a
    sentence before any browser write arrives;
(f) the note reaches the page by INTERPOLATION (``html_div("{{ run_n_line_note
    }}")``, the precedent ``html_div("{{ cut_label }}")``), not by a two-way
    ``v_model`` binding, and it rides the form's own ``run_config_visible``
    flag, so a page that has put the form away keeps no note about it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POC_APP = REPO_ROOT / "server" / "poc_app.py"
STUDIES = REPO_ROOT / "emfit" / "studies.py"
RUN_BUILD_A = REPO_ROOT / "evidence" / "termination" / "run_build_A.py"


def _source(path: Path = POC_APP) -> str:
    """The module text. Never imported - see the module docstring."""
    return path.read_text(encoding="utf-8")


def _tree(path: Path = POC_APP) -> ast.Module:
    """The parsed module, for the shapes the text alone cannot pin."""
    return ast.parse(_source(path), filename=str(path))


def _int_constants(path: Path = POC_APP) -> dict[str, int]:
    """``{name: value}`` for the module-level ``NAME = <int literal>`` rows."""
    found: dict[str, int] = {}
    for node in _tree(path).body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        value = node.value.value
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                found[target.id] = value
    return found


def _dict_ints(path: Path, key: str) -> list[int]:
    """Every ``"<key>": <int literal>`` row in the file's dict literals."""
    found: list[int] = []
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if (
                isinstance(k, ast.Constant)
                and k.value == key
                and isinstance(v, ast.Constant)
                and isinstance(v.value, int)
                and not isinstance(v.value, bool)
            ):
                found.append(v.value)
    return found


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    """The one ``def name`` at any depth."""
    hits = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(hits) == 1, f"expected exactly one def {name}, found {len(hits)}"
    return hits[0]


def _function_text(source: str, name: str) -> str:
    """``source`` from ``def name(`` to the next top-level ``def``."""
    start = source.index(f"def {name}(")
    end = source.find("\ndef ", start + 1)
    return source[start:] if end == -1 else source[start:end]


def _names(node: ast.AST) -> set[str]:
    """Every identifier read or written inside ``node``."""
    return {inner.id for inner in ast.walk(node) if isinstance(inner, ast.Name)}


# (a)
def test_the_bounds_are_the_numbers_we_derived() -> None:
    consts = _int_constants(POC_APP)
    assert consts["RUN_N_LINE_MIN"] == 43
    assert consts["RUN_N_LINE_MAX"] == 116
    assert consts["RUN_N_LINE_REFERENCE"] == 54
    assert consts["RUN_N_LINE_REFERENCE_CELLS"] == 289168
    assert consts["RUN_MESH_NX_OFFSET"] == 8
    assert consts["RUN_MESH_NY"] == 212
    assert consts["RUN_MESH_NZ"] == 22
    # the reference board IS the mesh at the shipped n_line: (8 + 54) * 212 * 22.
    assert (
        (consts["RUN_MESH_NX_OFFSET"] + consts["RUN_N_LINE_REFERENCE"])
        * consts["RUN_MESH_NY"]
        * consts["RUN_MESH_NZ"]
        == consts["RUN_N_LINE_REFERENCE_CELLS"]
    )
    # and it sits INSIDE the range it is the middle of.
    assert consts["RUN_N_LINE_MIN"] < consts["RUN_N_LINE_REFERENCE"] < consts["RUN_N_LINE_MAX"]


# (b)
def test_the_board_is_the_solvers_own_mesh() -> None:
    ui = _int_constants(POC_APP)
    solver = _int_constants(STUDIES)
    n_pml = solver["MS_N_PML"]
    n_ref = solver["MS_N_REF"]
    n_strip = solver["MS_N_STRIP"]
    n_sub = solver["MS_N_SUB"]
    n_air = solver["MS_N_AIR"]
    n_top = solver["MS_N_TOP"]
    # the cross-line cells are the BUILD's, not studies.py's default: the kwargs
    # dict in run_build_A is the one place the reference run states them.
    n_clean_hits = _dict_ints(RUN_BUILD_A, "n_clean")
    assert len(n_clean_hits) == 1, f"expected one literal n_clean, got {n_clean_hits}"
    n_clean = n_clean_hits[0]
    assert 2 * n_pml + n_strip + 2 * n_clean == ui["RUN_MESH_NY"]
    assert n_sub + n_air + n_top == ui["RUN_MESH_NZ"]
    assert n_pml + n_ref == ui["RUN_MESH_NX_OFFSET"]


# (c)
def test_the_helper_names_the_board_and_its_ratio() -> None:
    source = _source(POC_APP)
    assert source.count("def _run_n_line_board(") == 1
    body = _function_text(source, "_run_n_line_board")
    assert "RUN_MESH_NX_OFFSET + value" in body
    assert "RUN_MESH_NY" in body
    assert "RUN_MESH_NZ" in body
    assert "{cells:,}" in body
    assert "/ float(RUN_N_LINE_REFERENCE_CELLS)" in body
    assert "is not a whole number" in body
    assert "ceiling" in body
    assert "floor" in body
    assert "shipped default" in body


# (d)
def test_the_range_is_enforced_after_the_defaults_are_filled() -> None:
    source = _source(POC_APP)
    func = _function(_tree(POC_APP), "run_config_from_form")
    calls = [
        node
        for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "RunConfig"
    ]
    assert len(calls) == 1, f"expected one RunConfig( call, found {len(calls)}"
    built = calls[0].lineno
    checks = [
        node
        for node in ast.walk(func)
        if isinstance(node, ast.Compare)
        and "RUN_N_LINE_MIN" in _names(node.left)
        and any("RUN_N_LINE_MAX" in _names(side) for side in node.comparators)
    ]
    assert len(checks) == 1, f"expected one n_line range check, found {len(checks)}"
    assert checks[0].lineno > built, "the range is checked before the defaults are filled"
    body = _function_text(source, "run_config_from_form")
    assert "_run_n_line_board(config.n_line)" in body
    assert re.search(r'raise ValueError\(\s*f?"run config refused: ', body)


# (e)
def test_the_box_has_a_change_handler_that_writes_the_note() -> None:
    source = _source(POC_APP)
    tree = _tree(POC_APP)
    handlers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "change"
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and decorator.args[0].value == "run_n_line"
            for decorator in node.decorator_list
        )
    ]
    assert len(handlers) == 1, f"expected one @state.change(\"run_n_line\"), found {len(handlers)}"
    handler = handlers[0]
    targets: list[ast.expr] = []
    for node in ast.walk(handler):
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets.append(node.target)
    written = [
        target
        for target in targets
        if isinstance(target, ast.Attribute) and target.attr == "run_n_line_note"
    ]
    assert written, "the handler does not write state.run_n_line_note"
    assert "_run_n_line_board(" in _function_text(source, handler.name)
    # boot writes it too, from the form's own default: the first paint has a note.
    assert source.count("state.run_n_line_note =") >= 2
    assert (
        'state.run_n_line_note = _run_n_line_board(_run_defaults.get("run_n_line"))'
        in source
    )


# (f)
def test_the_note_is_bound_by_interpolation_not_v_model() -> None:
    source = _source(POC_APP)
    emit = re.search(r'html_div\(\s*"\{\{ run_n_line_note \}\}"', source)
    assert emit is not None, "the page does not emit the n_line note"
    assert 'v_model=("run_n_line_note"' not in source
    after = source[emit.end() : emit.end() + 300]
    assert 'v_if=("run_config_visible", True)' in after
    # the precedent this binding copies: a state name, never a widget value.
    assert 'html_div("{{ cut_label }}")' in source
