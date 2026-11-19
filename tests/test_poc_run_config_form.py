"""The other half of the run-form gate: a page with NO field data gets the form.

``server/poc_app.py``'s Run Config card draws its ten fields only on a page
that carries no field data at all - a page with a recording behind it already
knows those numbers.  ``tests/test_poc_run_config_panel.py`` pins the "absent"
half on a dump-backed page; this module pins the arriving half on the bare
board (``tests/test_poc_bare_board.py``, whose boot recipe is reused here).

WHY A SECOND MODULE: the left panel is emitted while the page is built, and one
process builds it once - a second boot in the same process emits no widgets, so
the two pages are observed in two processes rather than one weakened assertion.
"""

from __future__ import annotations

import contextlib
import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server"), str(REPO_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

pytest.importorskip("pyvista", reason="the board is drawn with pyvista")
pytest.importorskip("trame.app", reason="trame serves the page")
pytest.importorskip("trame.ui.vuetify3", reason="run_web_vis builds this UI")

import poc_app as app  # noqa: E402  (after the importorskip guards)

import test_animation_volume as av  # noqa: E402  (the boot recipe)
import test_poc_bare_board as bb  # noqa: E402  (the no-data page)

assert av.app is app, (
    "tests/test_animation_volume.py imported a different poc_app; the recipe "
    "above would boot the wrong module"
)

WIDGET_NAMES = ("VCard", "VCardText", "VSelect", "VTextField", "VAlert")


def _recorder(name, real, records):
    def _make(*args, **kwargs):
        records.append((name, args, kwargs))
        return real(*args, **kwargs)

    return _make


def _widget_holders():
    """Every module whose ``VCard`` etc. the bare page could be calling.

    ``trame.widgets.vuetify3`` is materialised FIRST, before anything is
    wrapped.  It is a one-line shim (``from trame_vuetify.widgets.vuetify3
    import *``) that does not exist until ``run_web_vis`` probes for it, so
    importing it while the classes were already wrapped copied the recorders
    into it and left them there for the rest of the process: this module then
    passed alone but recorded nothing when another module had booted first -
    the recorders it installed were never the ones the boot called.
    """
    importlib.import_module("trame.widgets.vuetify3")
    holders = [app]
    for module_name, module in list(sys.modules.items()):
        if module is None or not module_name.endswith("vuetify3"):
            continue
        if hasattr(module, "VCard"):
            holders.append(module)
    return holders


@contextlib.contextmanager
def _recording(records):
    """Record every widget the bare boot emits, then let the real one through.

    Every holder is wrapped from, and restored to, the canonical class.
    Restoring to the canonical class rather than to whatever a holder carried
    before is deliberate: it also repairs a shim that an earlier boot left
    holding a recorder.
    """
    holders = _widget_holders()
    restore = []
    try:
        for name in WIDGET_NAMES:
            real = next(
                (
                    getattr(holder, name, None)
                    for holder in holders
                    if isinstance(getattr(holder, name, None), type)
                ),
                None,
            )
            if real is None:
                continue
            for holder in holders:
                if not hasattr(holder, name):
                    continue
                setattr(holder, name, _recorder(name, real, records))
                restore.append((holder, name, real))
        yield records
    finally:
        for holder, name, real in restore:
            setattr(holder, name, real)


def _v_model(record):
    return record[2].get("v_model")


@pytest.fixture(scope="module")
def bare_boot(tmp_path_factory):
    """One boot of the no-data page: its live page, its emissions, its info."""
    records: list = []
    page = bb._page(tmp_path_factory.mktemp("run_config_form"))
    with av._render_doubled():
        with _recording(records):
            live = bb._boot(page["info"], page)
        av._silence_view(live)
    assert records, (
        "no widget call was recorded during the bare boot: the recorder did not "
        "reach the module the panel builds its widgets from, so the assertions "
        "below would read an empty list and prove nothing"
    )
    return live, records, page


def test_the_page_really_has_no_field_data(bare_boot):
    """The precondition the gate reads, stated on the page itself."""
    _live, _records, page = bare_boot
    assert page["planes"] is None, (
        "the bare page grew plane data, so this boot no longer exercises the "
        "no-field branch and the form below would be drawn (or not) for the "
        "wrong reason"
    )
    assert not page["info"].get("volume_field"), (
        "the bare page grew a volume field, so this boot no longer exercises "
        "the no-field branch"
    )
    assert not page["info"].get("e_centres"), (
        "the bare page carries the colocated volume key, so it is a data page "
        "and the gate would be right for the wrong reason"
    )


def test_the_eight_run_fields_arrive_at_the_run_config_defaults(bare_boot):
    """All ten, once each, on the numbers the reference run would start from."""
    from emfit.config import RunConfig

    _live, records, _page = bare_boot
    defaults = RunConfig()
    for state_name, label, field in app.RUN_CONFIG_FIELDS:
        found = [
            record
            for record in records
            if record[0] == "VTextField"
            and _v_model(record)
            and _v_model(record)[0] == state_name
        ]
        assert len(found) == 1, (
            f"the {label!r} field was emitted {len(found)} times on a page with "
            "no field data: expected exactly one"
        )
        record = found[0]
        assert record[2].get("label") == label, (
            f"the {state_name!r} field is labelled {record[2].get('label')!r}, "
            f"not {label!r}"
        )
        assert _v_model(record) == (state_name, getattr(defaults, field)), (
            f"the {label!r} field opens on {_v_model(record)!r}, not on "
            f"{getattr(defaults, field)!r}: the form must start where the run "
            "would start"
        )


#: The three rows the form grew when the dump budget became visible: state name,
#: and the ``RunConfig`` field each one edits. Named here because every other
#: test in the suite WALKS ``RUN_CONFIG_FIELDS``: a row quietly deleted takes its
#: own assertion with it, so row presence has to be pinned by name.
BUDGET_ROWS = (
    ("run_dump_stride", "dump_stride"),
    ("run_volume_frames", "volume_frames"),
    ("run_n_line", "n_line"),
)


def test_the_dump_budget_rows_are_on_the_form():
    """The three budget boxes exist, and each edits the field of the same name."""
    from emfit.config import RunConfig

    reference = RunConfig()
    table = {state_name: field for state_name, _label, field in app.RUN_CONFIG_FIELDS}
    for state_name, field in BUDGET_ROWS:
        assert table.get(state_name) == field, (
            f"{state_name!r} maps to {table.get(state_name)!r} in "
            f"RUN_CONFIG_FIELDS, not to {field!r}: the box that decides how big "
            "this run's output is is not on the form"
        )
        assert hasattr(reference, field), (
            f"the {state_name!r} box edits {field!r}, which RunConfig does not "
            "have: the form would offer a knob no run can carry, and the boot "
            "value behind it would be an invention rather than the reference's"
        )


def test_the_int_and_float_kinds_split_the_table_exactly():
    """Every row is declared whole-number or float, and the split is honest.

    ``_RUN_CONFIG_INT_FIELDS`` is what decides how a typed string is parsed, and
    ``RunConfig`` refuses a float where an int belongs - so a row on the WRONG
    side of the split is a box that either refuses a number the user typed or
    quietly rounds one. Both directions are asserted: the tuple names no field
    the table does not have (and no field twice), and every field the table DOES
    have parses as the kind the split claims for it.
    """
    rows = list(app.RUN_CONFIG_FIELDS)
    known = {field for _state_name, _label, field in rows}
    int_fields = set(app._RUN_CONFIG_INT_FIELDS)

    assert len(int_fields) == len(app._RUN_CONFIG_INT_FIELDS), (
        "_RUN_CONFIG_INT_FIELDS names a field twice: "
        f"{app._RUN_CONFIG_INT_FIELDS!r}"
    )
    assert int_fields <= known, (
        f"_RUN_CONFIG_INT_FIELDS names {sorted(int_fields - known)!r}, which is "
        f"not one of the form's fields {sorted(known)!r}: the kind of that box "
        "is decided nowhere, so nothing stops it being parsed as a float"
    )
    for _state_name, label, field in rows:
        whole = app._run_config_field_value(label, field, "7")
        if field in int_fields:
            assert whole == 7 and isinstance(whole, int), (
                f"the {label!r} box is declared a whole number but read 7 as "
                f"{whole!r} ({type(whole).__name__}): RunConfig refuses a float "
                "where an int belongs"
            )
            with pytest.raises(ValueError) as refused:
                app._run_config_field_value(label, field, "7.5")
            assert "whole number" in str(refused.value), (
                f"the {label!r} box took 7.5 for {field!r} with "
                f"{str(refused.value)!r}: a fractional value in a whole-number "
                "box has to refuse the press, not be rounded"
            )
        else:
            assert whole == 7.0 and isinstance(whole, float), (
                f"the {label!r} box is not in the int split but read 7 as "
                f"{whole!r} ({type(whole).__name__}): a float box parsed as a "
                "whole number loses the fraction the user typed"
            )
            assert app._run_config_field_value(label, field, "7.5") == 7.5, (
                f"the {label!r} box read 7.5 as "
                f"{app._run_config_field_value(label, field, '7.5')!r}: it is "
                "a float field"
            )


def test_the_clim_select_is_on_this_page_too(bare_boot):
    """The select is NOT gated: it changes how a volume is rendered."""
    _live, records, _page = bare_boot
    found = [
        record
        for record in records
        if record[0] == "VSelect"
        and _v_model(record)
        and _v_model(record)[0] == "volume_clim_mode"
    ]
    assert len(found) == 1, (
        f"the Clim Mode select was emitted {len(found)} times on a page with no "
        "field data: it is the run form that is gated, not the select"
    )
    assert _v_model(found[0]) == ("volume_clim_mode", app.VOLUME_CLIM_DEFAULT)


GUARD_ROWS = (
    ("run_wall_limit_s", "wall_limit_s"),
    ("run_load_ohm", "load_ohm"),
)


def test_the_runtime_guards_are_two_more_form_rows() -> None:
    """``--wall-limit-s`` and ``--load-ohm`` are rows like the other eight.

    Row, default and argv, all three off the ONE table: the state name the form
    writes, the ``RunConfig`` field behind it (``_run_config_defaults`` reads the
    default off that field, so a row without a field is a KeyError at boot, not a
    silent zero), and the flag the press sends.  The CEILING opens on the
    reference's own 1400 s (run_build_A.py:128), so a blank box still sends it;
    the LOAD opens blank ON PURPOSE - the reference resolves it per ARM (A 50
    ohm at :692 from the LOAD_VALUE_OHM constant at :137, B 100 ohm at :703, the
    absent flag resolved at :3593-3594) and a box opened on 50 would silently
    re-terminate an arm B press, the trap the WARNING at :3585-3588 names.
    """
    from emfit.config import RunConfig

    table = {state_name: field for state_name, _label, field in app.RUN_CONFIG_FIELDS}
    defaults = app._run_config_defaults()
    reference = RunConfig()
    for state_name, field in GUARD_ROWS:
        assert table.get(state_name) == field, (
            f"{state_name} is not a row of RUN_CONFIG_FIELDS mapped to {field}: "
            f"{sorted(table)}"
        )
        assert hasattr(reference, field), (
            f"{field} is not a RunConfig field, so {state_name} has no default"
        )
        assert defaults[state_name] == getattr(reference, field), (
            f"{state_name} opens on {defaults[state_name]!r}, not on RunConfig's "
            f"{getattr(reference, field)!r}"
        )
    assert RunConfig().wall_limit_s == 1400.0, (
        "the ceiling must open on the reference's own 1400 s, so a blank box "
        "states the number a bare command line would have used"
    )
    assert RunConfig().load_ohm is None, (
        "the load must open BLANK: None is the ARM's own termination, and 50 "
        "would re-terminate an arm B press"
    )

    blank = app._run_config_argv(app.run_config_from_form({}))
    assert blank[-2:] == ["--wall-limit-s", "1400"], (
        f"an untouched form produced {blank!r}: the ceiling travels on every press"
    )
    assert "--load-ohm" not in blank, (
        f"an untouched form produced {blank!r}: it must not name a load"
    )

    filled = app.run_config_from_form(
        {"run_wall_limit_s": "60", "run_load_ohm": "75.5"}
    )
    flags = app._run_config_argv(filled)
    assert flags[-4:] == ["--wall-limit-s", "60", "--load-ohm", "75.5"], (
        f"typed boxes produced {flags!r}, not the values that were typed"
    )
