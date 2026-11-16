"""The other half of the run-form gate: a page with NO field data gets the form.

``server/poc_app.py``'s Run Config card draws its five fields only on a page
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


def test_the_five_run_fields_arrive_at_the_run_config_defaults(bare_boot):
    """All five, once each, on the numbers the reference run would start from."""
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
