"""The "Run Config" card: the Color Scale select wired end to end, plus the form.

``server/poc_app.py`` grew one new left-panel card between "Circuit" and
"Action".  It carries three promises, and this module pins all of them:

* the **Color Scale** select is a real control, not decoration - it offers the
  two modes as readable labels bound to machine tokens;
* it drives the state flag the warning banner is gated on, and flipping it
  repaints the frame that is already on screen (the volume layer caches on the
  frame, so a mode that only changes the clim is invisible to that key - the
  repaint is the whole point);
* the **run form** (steps, volume stride, pulse frequency, both cut planes) is
  absent on a dump-backed page: the recording already fixed those numbers, so
  the fields are left off rather than offered-and-ignored.  The other half of
  that gate - the form ARRIVING on a page with no field data - is
  ``tests/test_poc_run_config_form.py``: one boot per process is what emits the
  panel, so the two pages are observed in two processes.

The boot recipe, ``_render_doubled``, ``_silence_view``, ``_layer_entry`` and
``_drawn_range`` are taken from ``tests/test_animation_volume.py``, where they
are documented, and the ``state.ready()`` step from
``tests/test_poc_mode_picker.py``.

The widget assertions read what the page EMITTED, by wrapping the real trame
widget classes in recorders that still build the real widget: the panel's
widgets module is a local of ``run_web_vis``, so the emitted calls are the only
honest place to look - and wrapping (rather than replacing) keeps the page's
structure exactly what a user would get.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server"), str(REPO_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

pytest.importorskip("pyvista", reason="the volume is drawn with pyvista")
pytest.importorskip("trame.app", reason="trame serves the page")
pytest.importorskip("trame.ui.vuetify3", reason="run_web_vis builds this UI")

import poc_app as app  # noqa: E402  (after the importorskip guards)

#: The established recipe, reused rather than re-written.
import test_animation_volume as av  # noqa: E402

assert av.app is app, (
    "tests/test_animation_volume.py imported a different poc_app; the recipe "
    "above would boot the wrong module"
)

#: The labels a reader must see, spelled out here on purpose: these are the
#: user-visible strings, so a mapping that degrades to the raw tokens has to
#: fail this test rather than move the expectation with it.
EXPECTED_CLIM_ITEMS = [
    {"title": "Global (Comparable)", "value": "global"},
    {"title": "Per-Frame (Max Contrast)", "value": "per_frame"},
]

#: The banner's sentence, likewise pinned as text.
EXPECTED_WARNING = (
    "Warning: Per-Frame (Max Contrast) re-references the color scale to each "
    "frame's own peak, so the amplitude decay between frames is not visible."
)

#: Card headings this panel must sit between.
CARD = "Run Config"
BEFORE_CARD = "Circuit"
AFTER_CARD = "Action"

#: Every widget the card is built from.
WIDGET_NAMES = ("VCard", "VCardTitle", "VCardText", "VSelect", "VTextField", "VAlert")


def _recorder(name, real, records):
    """A stand-in that remembers the call and then builds the real widget."""

    def _make(*args, **kwargs):
        records.append((name, args, kwargs))
        return real(*args, **kwargs)

    return _make


def _widget_holders():
    """Every module whose ``VCard`` etc. a page could be calling.

    ``poc_app`` itself is included because a module-level ``from ... import
    VCard`` would have bound the class there; the vuetify3 modules are included
    because the panel is built from whichever of them ``run_web_vis`` resolved.

    ``trame.widgets.vuetify3`` is materialised FIRST, before anything is
    wrapped.  It is a one-line shim (``from trame_vuetify.widgets.vuetify3
    import *``) that does not exist until ``run_web_vis`` probes for it, so
    importing it while the classes were already wrapped copied the recorders
    into it and left them there for the rest of the process: this module then
    passed alone but starved every later boot of records, which is the
    cross-file order dependence this helper now rules out.
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
    """Record every widget the boot emits, then let the real widget through.

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


def _text(record) -> str | None:
    """The text a widget was given, positional or as children."""
    _name, args, kwargs = record
    if args and isinstance(args[0], str):
        return args[0]
    for key in ("children", "__children"):
        value = kwargs.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)) and value and isinstance(value[0], str):
            return value[0]
    return None


def _v_model(record):
    return record[2].get("v_model")


def _with_v_model(records, widget, state_name):
    return [
        record
        for record in records
        if record[0] == widget
        and _v_model(record)
        and _v_model(record)[0] == state_name
    ]


def _last_with_v_model(records, widget, state_name):
    found = _with_v_model(records, widget, state_name)
    assert found, (
        f"the boot emitted no {widget} bound to {state_name!r}: the control is "
        "missing from the page"
    )
    return found[-1]


def _titles(records) -> list:
    return [text for text in (_text(r) for r in records if r[0] == "VCardTitle") if text]


@pytest.fixture(scope="module")
def volume_boot(tmp_path_factory):
    """One dump-backed boot: its live page AND everything the page emitted."""
    records: list = []
    with av._render_doubled():
        with _recording(records):
            live = av._boot(
                tmp_path_factory.mktemp("run_config_volume"), with_volume=True
            )
        av._silence_view(live)
        # The one framework step the boot double skips: no port was bound, so
        # ``State.flush()`` refuses (``_status.skip_flushing`` while the state is
        # not ready) and a refused flush runs no ``@state.change`` listener -
        # the two select tests below would then drive nothing at all.
        # ``ready()`` is trame's own call (tests/test_poc_mode_picker.py:663).
        live.state.ready()
        live.state.flush()  # push the boot writes; no count depends on it
    assert live.state.is_ready, (
        "trame's state.ready() did not mark this page ready, so no flush can "
        "run a listener"
    )
    assert records, (
        "no widget call was recorded during the boot: the recorder did not "
        "reach the module the panel builds its widgets from, so these tests "
        "would pass vacuously"
    )
    return live, records


@pytest.fixture(scope="module")
def live(volume_boot):
    return volume_boot[0]


def test_the_card_sits_between_circuit_and_action(volume_boot):
    """The card's place in the panel, read off the headings that were built."""
    _live, records = volume_boot
    titles = _titles(records)
    assert titles.count(CARD) == 1, (
        f"the page emitted the {CARD!r} heading {titles.count(CARD)} times: "
        f"expected exactly one card. Headings seen: {titles}"
    )
    index = titles.index(CARD)
    assert BEFORE_CARD in titles[:index], (
        f"{CARD!r} is emitted before {BEFORE_CARD!r}: the headings in order are "
        f"{titles}"
    )
    assert AFTER_CARD in titles[index:], (
        f"{CARD!r} is emitted after {AFTER_CARD!r}: the headings in order are "
        f"{titles}"
    )


def test_the_clim_select_offers_readable_labels_bound_to_tokens(volume_boot):
    """Two items, a title AND a value - and a literal trame can re-wrap."""
    _live, records = volume_boot
    select = _last_with_v_model(records, "VSelect", "volume_clim_mode")
    _name, _args, kwargs = select

    assert _v_model(select) == ("volume_clim_mode", app.VOLUME_CLIM_DEFAULT), (
        "the Color Scale select is bound to "
        f"{_v_model(select)!r}, not to "
        f"{('volume_clim_mode', app.VOLUME_CLIM_DEFAULT)!r}: it must open on the "
        "page's default mode"
    )
    assert kwargs.get("item_title") == "title", (
        "the select does not name the item's title key "
        f"({kwargs.get('item_title')!r}): the labels would not be shown"
    )
    assert kwargs.get("item_value") == "value", (
        "the select does not name the item's value key "
        f"({kwargs.get('item_value')!r}): the tokens would not be bound"
    )

    literal = kwargs.get("v_bind_items")
    assert isinstance(literal, str), (
        f"v_bind_items was emitted as {type(literal).__name__}, not the literal "
        "string trame re-wraps"
    )
    assert '"' not in literal, (
        f"v_bind_items was emitted as {literal!r}: a double quote inside it "
        "collides with the quoting trame puts around the attribute"
    )
    assert ast.literal_eval(literal) == EXPECTED_CLIM_ITEMS, (
        f"the select offers {ast.literal_eval(literal)!r}, not "
        f"{EXPECTED_CLIM_ITEMS!r}: a reader must get a mode name, not a token"
    )


def test_the_warning_banner_is_gated_on_the_state_flag(volume_boot):
    """The sentence, and the flag that hides it - both pinned."""
    _live, records = volume_boot
    alerts = [
        record
        for record in records
        if record[0] == "VAlert" and _text(record) == EXPECTED_WARNING
    ]
    assert alerts, (
        "no VAlert carries the relative-scaling warning: the banner the select "
        "is supposed to raise is not on the page"
    )
    for record in alerts:
        assert record[2].get("v_if") == ("clim_relative_warning", False), (
            "the warning banner is gated on "
            f"{record[2].get('v_if')!r}, not on "
            f"{('clim_relative_warning', False)!r}: it would not appear exactly "
            "when the renormalising mode is selected"
        )


def test_the_clim_flag_follows_the_select(live):
    """``@state.change("volume_clim_mode")`` drives the banner, both ways."""
    assert live.state.clim_relative_warning is False, (
        "the page boots with clim mode "
        f"{live.state.volume_clim_mode!r} but a relative-scaling warning flag of "
        f"{live.state.clim_relative_warning!r}"
    )

    live.state.volume_clim_mode = app.VOLUME_CLIM_PER_FRAME
    live.state.flush()
    try:
        assert live.state.clim_relative_warning is True, (
            "selecting "
            f"{app.VOLUME_CLIM_PER_FRAME!r} left the warning flag at "
            f"{live.state.clim_relative_warning!r}: the banner never appears"
        )

        live.state.volume_clim_mode = app.VOLUME_CLIM_DEFAULT
        live.state.flush()
        assert live.state.clim_relative_warning is False, (
            "going back to "
            f"{app.VOLUME_CLIM_DEFAULT!r} left the warning flag at "
            f"{live.state.clim_relative_warning!r}: the banner never clears"
        )

        live.state.volume_clim_mode = "per-frame"
        live.state.flush()
        assert live.state.clim_relative_warning is False, (
            "a misspelled mode selected the renormalising branch: the flag is "
            f"{live.state.clim_relative_warning!r}"
        )
    finally:
        live.state.volume_clim_mode = app.VOLUME_CLIM_DEFAULT
        live.state.flush()


def test_flipping_the_mode_repaints_the_frame_already_on_screen(live):
    """The control must bite on the frame in front of the user, not on the next.

    The volume layer caches on the frame, so a mode that only changes the clim
    is invisible to that key: a handler that did not repaint would leave the
    layer stamped with the OLD mode and painted on the old range, and the
    select would look dead until the slider moved.
    """
    volume = live.page["info"]["e_abs_volume"]
    before_entry = av._layer_entry(live)
    assert before_entry["clim_mode"] == app.VOLUME_CLIM_DEFAULT, (
        "the layer on screen is stamped "
        f"{before_entry['clim_mode']!r}, not the default "
        f"{app.VOLUME_CLIM_DEFAULT!r}: this test does not start from the state "
        "it describes"
    )
    before = av._drawn_range(live)

    live.state.volume_clim_mode = app.VOLUME_CLIM_PER_FRAME
    live.state.flush()
    try:
        after_entry = av._layer_entry(live)
        assert after_entry["clim_mode"] == app.VOLUME_CLIM_PER_FRAME, (
            "flipping to "
            f"{app.VOLUME_CLIM_PER_FRAME!r} left the layer on screen stamped "
            f"{after_entry['clim_mode']!r}: the frame was not repainted, so the "
            "control only takes effect at the next frame change"
        )
        frame_peak = float(np.max(volume[after_entry["frame"]]))
        frame_clim = (frame_peak * 1e-3, frame_peak)
        assert av._drawn_range(live) == pytest.approx(frame_clim, rel=1e-9), (
            f"the repaint painted the volume on {av._drawn_range(live)}, not on "
            f"the per-frame range {frame_clim} of the frame it is showing"
        )

        live.state.volume_clim_mode = app.VOLUME_CLIM_DEFAULT
        live.state.flush()
        assert av._layer_entry(live)["clim_mode"] == app.VOLUME_CLIM_DEFAULT, (
            "going back to "
            f"{app.VOLUME_CLIM_DEFAULT!r} left the layer stamped "
            f"{av._layer_entry(live)['clim_mode']!r}: the repaint is one-way"
        )
        assert av._drawn_range(live) == pytest.approx(before), (
            f"going back to {app.VOLUME_CLIM_DEFAULT!r} painted the volume on "
            f"{av._drawn_range(live)}, not on the {before} it started on"
        )
    finally:
        live.state.volume_clim_mode = app.VOLUME_CLIM_DEFAULT
        live.state.flush()


def test_a_dump_backed_page_shows_no_run_form(volume_boot):
    """The recording already fixed those numbers: the fields stay off."""
    _live, records = volume_boot
    emitted = [
        _v_model(record)[0]
        for record in records
        if record[0] == "VTextField" and _v_model(record)
    ]
    for state_name, label, _field in app.RUN_CONFIG_FIELDS:
        assert state_name not in emitted, (
            f"the {label!r} field was drawn on a page that already has field "
            "data, where the value it edits is fixed by the recording"
        )
