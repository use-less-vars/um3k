"""The layout builders ONE um3k page is assembled from, one function per column.

The load-bearing invariant: a builder takes only ``ctx`` and is called from
INSIDE the layout container it is meant to fill. Trame's widget constructors
attach to the AMBIENT layout context - the ``with`` block live at the call site -
so a builder can never decide where its widgets land. That is why these are
plain module functions reached through :class:`um3k_context.PageContext` rather
than closures over the page: the call site owns the position, the builder owns
the content, and no trame or pyvista name appears in this file.
"""
from __future__ import annotations

import sys


def build_left_panel(ctx) -> None:
    """Fill the caller's left column with SETUP: which page, then what acts on it.

    Called inside the left ``VCol`` of the 3-column row, and every call goes
    through ``ctx`` so the widgets still land in the caller's layout. ``ctx``
    holds the callables rather than this module closing over the page
    (``poc_app.py`` registers them at the row, just before it opens).

    The header line - WHICH file this page is showing, and which kind of page it
    is (``state.page_source_text``, poc_app.py:778) - is OPTIONAL and resolved
    leniently, the same way the centre column resolves the station sentence: a
    context that registers no ``html_div`` builds exactly the column it built
    before, and the solve controls are reached either way.
    """
    # WHY the file name belongs HERE: the controls under it start a NEW study,
    # and a reader about to press them needs to know which artefact the page
    # under them came off (and whether it is an animation or a static snapshot).
    # Emitted through the caller's own html_div so it lands in the caller's
    # column; a failed emit costs the line and never the column.
    if "html_div" in ctx.callbacks:
        try:
            ctx.callback("html_div")(
                "{{ page_source_text }}",
                style="padding: 2px 4px; font-size: 12px;",
            )
        except Exception as exc:  # noqa: BLE001 - a header line is not the column
            print(
                f"[poc_app] page source line not emitted: {exc}",
                file=sys.stderr,
            )

    ctx.callback("_emit_solve_controls")()


def build_center_panel(ctx) -> object:
    """Fill the caller's centre column with VIEW: the picture and its player bar.

    Called from inside the centre ``VCol`` of the 3-column row, so the wrapper
    div and the player-bar row land in the caller's layout. Objects the page
    already owns arrive as handles (the widget table, the controller, the frame
    count, the plotter); the three callables the body calls arrive as callbacks.
    ``nt`` is the frame count as the page registered it, which is the count this
    layout is built with - and ``None`` on a page that has NO timeline (a plain
    field dump): the player and the scrubber are then not built at all, and one
    label says why in their place. A page with a plane stack opens the column
    with the two cut sliders, bound to the page's own ``cut_y``/``cut_z``
    triggers, above the picture, followed by the station sentence that page
    publishes - an OPTIONAL callback, so a context that has none builds exactly
    the row it always built. Returns the view ``plotter_ui`` made, which the
    page keeps as ``handles["view"]``.
    """
    widgets = ctx.handle("widgets")
    ctrl = ctx.handle("ctrl")
    # The scrubber's range is the timeline's last index, published by the page as
    # `frame_max`; no frame COUNT is read here any more (one clock, one maximum).
    frame_max = ctx.handle("frame_max")
    plotter = ctx.handle("plotter")
    html_div = ctx.callback("html_div")
    VRow = ctx.callback("VRow")
    plotter_ui = ctx.callback("plotter_ui")

    # THE CUT SHEETS: a page that captured more than one x-plane has a stack to
    # cut through, and the two sliders that move the cut belong with the
    # picture they move - in this column, above it, rather than in the toolbar.
    # `cut_shape` and the emitter are registered by the page ONLY behind the
    # same `plane_stack` gate (poc_app.py:7572), so on any other page this block
    # does not run and neither handle is ever asked for. `placeholder` is None
    # on purpose: there is no placeholder div in this layout, and the emitter
    # falls back to the row's own html_div for the label (poc_app.py:4049-4064).
    if ctx.available.plane_stack:
        n_j, n_k = ctx.handle("cut_shape")
        # THE STATION SENTENCE: ordinary page text naming the plane this stack is
        # drawn at, inside the row whose sliders choose it (poc_app.py:9630).
        # Resolved LENIENTLY - the page registers `_emit_station_readout` beside
        # the cut row, but this column is also built by contexts that have no
        # such emitter (the header tests' fakes, a diff whose stack carries no
        # station axis), and those must build the row they always built.
        emit_station_readout = (
            ctx.callback("_emit_station_readout")
            if "_emit_station_readout" in ctx.callbacks
            else None
        )
        with html_div(
            style=(
                "flex: 0 0 auto; display: flex; flex-wrap: wrap; "
                "align-items: center; padding: 2px 12px;"
            )
        ):
            ctx.callback("_emit_cut_sliders")(
                ctx.handle("missing_widgets"),
                None,
                html_div,
                widgets,
                ctx.handle("state"),
                n_j,
                n_k,
            )
            if emit_station_readout is not None:
                emit_station_readout()

    # VIEW: the 3-D picture keeps the wrapper div it
    # has always had, and now shares the column with
    # the player bar beneath it - VCol is already a
    # flex column, so the picture takes the height and
    # the bar takes its own.
    with html_div(
        style=(
            "flex: 1 1 auto; min-height: 0;"
        )
    ):
        # mode="server" (PyVistaRemoteView): the server
        # renders and streams the image, so the view
        # does not depend on the client's WebGL context
        # surviving inside a flexed container. "remote"
        # is not a valid mode (valid:
        # trame/client/server/wasm) and
        # default_server_rendering only applies to
        # mode="trame", so both are left alone.
        view = plotter_ui(
            plotter, mode="server", add_menu=False
        )
    # PLAYER BAR: the frame scrubber and the playback
    # buttons, out of the toolbar and under the
    # picture, where the eye already is. The guards are
    # the toolbar's own, kept one for one; the spacer
    # rides along at the end so no widget is lost.
    with VRow(
        style=(
            "flex: 0 0 auto; align-items: center; "
            "gap: 4px; width: 100%; padding: 4px 0;"
        )
    ):
        # NO TIMELINE: nt is None (never 0), so there is no frame to play or
        # scrub. The player and the slider are left OUT of this row rather
        # than built over an invented frame count, and one visible line takes
        # their place - the same degraded-row idiom the guards below use.
        #
        # The line says what the page IS, not what is missing from it: it stands
        # in a control bar, so it gets a control bar's length. The long form of
        # the reason (no frame axis recorded, so nothing to play or scrub) is
        # what the boot log prints as its
        # "[poc_app] no timeline on this page:" line, which is where a
        # reader goes to ask WHY.
        if frame_max is None:
            if "VLabel" in widgets:
                widgets["VLabel"]("Static field snapshot - no timeline")
        if frame_max is not None and "VBtn" in widgets:
            try:
                widgets["VBtn"](
                    "<< PREV", click=ctrl.step_back
                )
                widgets["VBtn"](
                    "{{ play_label }}",
                    click=ctrl.play_toggle,
                )
                widgets["VBtn"](
                    "NEXT >>", click=ctrl.step_fwd
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[poc_app] playback buttons "
                    f"unavailable: {exc}",
                    file=sys.stderr,
                )
                if "VLabel" in widgets:
                    widgets["VLabel"](
                        "playback unavailable "
                        "(button binding failed)"
                    )
        if frame_max is not None and "VSlider" in widgets and "VLabel" in widgets:
            try:
                widgets["VSlider"](
                    v_model=("frame", 0),
                    min=0,
                    max=("frame_max", 0),
                    step=1,
                    thumb_label=True,
                    hide_details=True,
                    style=(
                        "flex: 1 1 auto; "
                        "min-width: 120px; "
                        "margin-right: 16px;"
                    ),
                )
                widgets["VLabel"]("{{ frame_label }}")
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[poc_app] frame slider "
                    f"unavailable: {exc}",
                    file=sys.stderr,
                )
        # THE PLAY SPEED: how many positions a tick advances, and the sweep time
        # that costs - the one control the bar was missing, because a position is a
        # SOLVER STEP and one to eight of them a tick turns a 100 s strobe into a
        # 12 s review. It rides in the bar beside the scrubber it changes.
        #
        # THE SELECT CLASS COMES IN AS A HANDLE, not out of ``widgets``: that table
        # probes only VSpacer/VSlider/VLabel/VContainer/VBtn, and VSelect is kept
        # out of it on purpose (a Vuetify variant without VSelect would otherwise
        # degrade the whole column instead of costing one control). So the page
        # resolves the class and registers it here, and the block is skipped whole
        # when it is absent: a context that registers neither handle builds exactly
        # the column it built before.
        #
        # The CAPTION is emitted only WITH the select: the sentence states what the
        # select is set to, so alone it would be a claim about a control that is
        # not on the page - both or neither.
        options = ctx.handles.get("play_rate_options")
        select_cls = ctx.handles.get("play_rate_select")
        if (
            frame_max is not None
            and options
            and select_cls is not None
            and "VLabel" in widgets
        ):
            try:
                # v_bind_items takes a JS ARRAY LITERAL, not a Python list:
                # trame reads a list-valued binding as (state_name, default) and
                # would emit only its first element. The entries are Vuetify
                # OBJECTS (title beside value) because a row's visible text comes
                # from item.title: bare numbers left the rows showing the garbage
                # the operator reported ("st 1", "st 2", "8"). The items arrive
                # pre-shaped from the page (poc_app._play_rate_items), so this
                # column carries no second copy of the wording.
                #
                # repr, NOT json.dumps: trame re-wraps this string in DOUBLE
                # quotes, so a `"` inside it ends the attribute mid-array - the
                # trap poc_app._volume_clim_items_literal documents. repr emits
                # single quotes, which Vue's expression parser accepts.
                rate_items = repr(list(options["items"]))
                select_cls(
                    label="steps per tick",
                    v_model=("play_rate", options["default"]),
                    v_bind_items=rate_items,
                    # The item keys are named, not inferred: the select reads
                    # item.title for the row text and item.value for the bound
                    # value, and the page's items spell exactly those keys.
                    item_title="title",
                    item_value="value",
                    hide_details=True,
                    density="compact",
                    style="max-width: 150px; flex: 0 0 auto;",
                )
                widgets["VLabel"]("{{ play_caption }}")
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[poc_app] play speed control "
                    f"unavailable: {exc}",
                    file=sys.stderr,
                )
        if "VBtn" in widgets:
            try:
                widgets["VBtn"](
                    "Switch plane",
                    click=ctrl.mode_toggle,
                )
                widgets["VBtn"](
                    "Top View", click=ctrl.top_view
                )
                widgets["VBtn"](
                    "Side View", click=ctrl.side_view
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[poc_app] view buttons "
                    f"unavailable: {exc}",
                    file=sys.stderr,
                )
                if "VLabel" in widgets:
                    widgets["VLabel"](
                        "view buttons unavailable "
                        "(button binding failed)"
                    )
        if "VSpacer" in widgets:
            widgets["VSpacer"]()

    return view


#: The DATA column's tabs, in the order it has always shown them: the label, the
#: value BOTH sides of the tab pair carry, and the ``Available`` flag whose truth
#: is what the panel behind it READS before it has anything to draw. Each flag is
#: the real one from :class:`um3k_context.Available`, picked off its own loader;
#: ``None`` marks a tab that is always offered: either it needs no page data at
#: all, or it fills a refusal when the data it would have read is missing.
RIGHT_TABS = (
    # The sweep: ``multifreq = load_multifreq(info["path"], structure_id)``.
    # NO flag, deliberately: the tab is offered on EVERY page, because the page
    # that has no sweep is exactly the page whose reader needs to be told so.
    # Flagged on ``multifreq`` it vanished on the customer's shape - a legacy
    # dump with no sweep but a study record beside it (``record`` true made
    # "some flag is true" true, so the filter dropped this one) - and the panel
    # that fills the refusal never ran. The body says "No sweep file found"
    # instead (poc_app._emit_s_params_panel).
    ("S-Params", "s_params", None),
    # NOT page data: the panel is ``build_far_field_panel(surface_dump)``, i.e.
    # the --surface-dump archive, which no Available flag describes.
    ("Far Field", "far_field", None),
    # The record: ``_field_record(info["path"])``.
    ("Confidence", "confidence", "record"),
    # Always-on: with no record beside the dump ``_mode_view`` solves from the
    # dump's own metadata instead (``_mode_geometry_from_dump``, poc_app.py:5936)
    # and otherwise fills a refusal (:5937-5943), so a record-less page can still
    # fill this tab and hiding it would hide an answer.
    ("Modes", "modes", None),
    # The operator's own netlist text plus the load trace: no page data at all.
    ("Circuit", "circuit", None),
)


def visible_right_tabs(available=None) -> list:
    """The tab values this page can fill, in :data:`RIGHT_TABS` order.

    A tab is dropped only for a flag it HAS and that flag is FALSE. With
    S-Params offered unconditionally the only flagged row left is Confidence
    (``record``), so no snapshot can drop a tab TODAY: a false ``record`` is
    also the flag that trips the "no flag is true" rescue below, which keeps
    all five. The filter stays anyway, because a false flag must cost a tab at
    most and never the column, and the next flagged row added rides it. Every
    other case KEEPS the tab too:

    * ``None`` in :data:`RIGHT_TABS` is a row with no flag at all - S-Params
      fills "No sweep file found" when the arm has none registered
      (poc_app._emit_s_params_panel), Far Field reads the --surface-dump
      archive, Modes falls back to the dump's own metadata and Circuit asks the
      page for nothing - so it is never dropped;
    * ``available`` of ``None`` - a context that never carried a snapshot -
      keeps all five, the same answer as a snapshot that carries the flags;
    * an ANIMATION page keeps all five: it is the page this column was built
      for, and each of its panels already says so itself when its neighbour
      file is missing;
    * a page that claims NONE of the flags keeps all five rather than an empty
      column, so a wrong flag can cost a tab but never the whole right side -
      and that is the second reason the field page with no sweep still gets the
      panel that says "No sweep file found".
    """
    values = [value for _label, value, _flag in RIGHT_TABS]
    if available is None or getattr(available, "animation", False):
        return list(values)
    if not any(
        getattr(available, flag, False)
        for _label, _value, flag in RIGHT_TABS
        if flag is not None
    ):
        return list(values)
    return [
        value
        for _label, value, flag in RIGHT_TABS
        if flag is None or getattr(available, flag, False)
    ]


def build_right_panel(ctx) -> None:
    """Fill the caller's right column with DATA: the readout and the tabbed panels.

    Called from inside the right ``VCol`` of the 3-column row, so the readout
    strip and the tab container land in the caller's layout. The body reads two
    page objects (the widget module the optional tab classes are probed on, and
    the dump's ``info``) and the callbacks that fill each panel, so this file
    still names no trame and no pyvista widget.
    """
    widgets_module = ctx.handle("widgets_module")
    info = ctx.handle("info")
    html_div = ctx.callback("html_div")
    _load_s_params_panel = ctx.callback("_load_s_params_panel")
    _load_far_field_panel = ctx.callback("_load_far_field_panel")
    _load_confidence_panel = ctx.callback("_load_confidence_panel")
    _emit_s_params_panel = ctx.callback("_emit_s_params_panel")
    _emit_far_field_panel = ctx.callback("_emit_far_field_panel")
    _emit_confidence_panel = ctx.callback("_emit_confidence_panel")
    _emit_mode_caption = ctx.callback("_emit_mode_caption")
    _emit_mode_picker = ctx.callback("_emit_mode_picker")
    _emit_vector_toggle = ctx.callback("_emit_vector_toggle")
    _emit_circuit_netlist = ctx.callback("_emit_circuit_netlist")
    _emit_load_series_panel = ctx.callback("_emit_load_series_panel")

    with html_div(
        style=(
            "flex: 0 0 auto; padding: 4px 12px; "
            "font-size: 13px; line-height: 1.4;"
        )
    ):
        html_div("{{ structure_readout }}")
        html_div("{{ t_label }}")
        html_div("{{ mode_label }}")
        html_div("{{ phase_label }}")
        html_div("{{ scale_label }}")
        html_div("{{ velocity_label }}")
        html_div("{{ velocity_note }}")
        # Two things the button does NOT tell you: where it
        # runs, and what it cannot produce.
        html_div(
            "solve runs on the HOST machine running this "
            "app (a child process, not in the browser). A "
            "vis-dump solve forces the PULSE excitation, "
            "so it writes NO cut-plane S21 - the "
            "S-Parameters panel keeps whatever sweep file "
            "it already finds."
        )
    # Fill both panels ONCE, here, at layout time:
    # the tabs own visibility now, so there is no
    # button and no first click to load on - whichever
    # tab a reader selects must already hold its text.
    # Each loader swallows its own failure (stderr).
    for _load_panel in (
        _load_s_params_panel,
        _load_far_field_panel,
        _load_confidence_panel,
    ):
        _load_panel()
    # DATA: one tab per panel, so the column holds the
    # readout plus ONE open panel instead of three
    # stacked ones. The TAB owns visibility here: no
    # wrapper, no style string and no toggle button,
    # because selecting a tab already shows the panel
    # the eager loader above has just filled in.
    def _emit_modes_tab() -> None:
        # The Mode panel's ONE line: the hint before the
        # first press, the solve's own caption after
        # one, or the reason the solve refused.
        _emit_mode_caption()
        _emit_mode_picker()
        # The arrow toggle sits with the picker it
        # annotates: both are about the picture above
        # them.
        _emit_vector_toggle()

    def _emit_circuit_tab() -> None:
        # The netlist's OWN home, so it is reachable
        # without scrolling the SETUP column to find it.
        html_div(
            "The netlist names the circuit on the "
            "load's cut; its V(t) and I(t) become part "
            "of the run. Empty box = the built-in "
            "resistor.",
            style="padding: 2px 0;",
        )
        _emit_circuit_netlist()
        # The load's trace belongs to the netlist above it.
        _emit_load_series_panel(
            info.get("load_series"),
            info.get("load_series_reason"),
        )

    _emit_tab = {
        "s_params": _emit_s_params_panel,
        "far_field": _emit_far_field_panel,
        "confidence": _emit_confidence_panel,
        "modes": _emit_modes_tab,
        "circuit": _emit_circuit_tab,
    }
    # Which tabs this page can fill, in RIGHT_TABS order. The
    # FIRST kept one is the tab the column opens on.
    shown = visible_right_tabs(getattr(ctx, "available", None))
    tabs_cls = getattr(widgets_module, "VTabs", None)
    tab_cls = getattr(widgets_module, "VTab", None)
    tabs_window_cls = getattr(
        widgets_module, "VTabsWindow", None
    )
    tabs_item_cls = getattr(
        widgets_module, "VTabsWindowItem", None
    )
    if None not in (
        tabs_cls,
        tab_cls,
        tabs_window_cls,
        tabs_item_cls,
    ):
        # EVERY tab names its value, and the value is
        # the SAME string as the window item below it.
        # WHY (this is the whole fix): Vuetify's tab
        # item registers whatever ``value`` prop it was
        # handed - its group-item props default is
        # ``value: null`` and ``useGroupItem`` takes
        # ``toRef(() => props.value)`` as-is, with NO
        # index fallback for VTab. So five bare
        # ``VTab("label")`` calls all register ``null``,
        # and ``VTabsWindow`` resolves its model to the
        # selected TAB's value - null - which matches
        # none of the five STRING window-item values.
        # Result: a tab bar that highlights a tab and a
        # window that renders nothing. Naming both
        # sides is the contract; the alternative
        # (indexes on the window items, so the tabs'
        # implicit values line up) was rejected because
        # the tab state would then be a number the
        # reader cannot see in the code.
        # The label and the value ride the SAME widget:
        # RIGHT_TABS holds them as one pair, so a tab can
        # never be drawn under one name and select another.
        # The kept order is RIGHT_TABS order, which is the
        # order the five have always had.
        # Five labels in a column this narrow only fit if the BAR is asked to
        # be small: ``density="compact"`` is Vuetify 3's short tab bar (there
        # is no ``dense`` prop in v3 - that one is v2, and passing it here is
        # silently dropped), ``show_arrows`` turns an overflow into a pair of
        # pagination arrows instead of labels clipped off the panel edge, and
        # the tag padding/min-width override Vuetify's 90px floor, which is
        # what pushed "Modes" and "Circuit" out of sight.
        with tabs_cls(
            v_model=("tab", shown[0]),
            density="compact",
            show_arrows=True,
            style="font-size: 11px;",
        ):
            for _label, _value, _flag in RIGHT_TABS:
                if _value in shown:
                    tab_cls(
                        _label,
                        value=_value,
                        style=(
                            "min-width: 0; padding: 0 6px; "
                            "text-transform: none;"
                        ),
                    )
        with tabs_window_cls(
            v_model=("tab", shown[0])
        ):
            for _value in shown:
                with tabs_item_cls(value=_value):
                    _emit_tab[_value]()
    else:
        # FALLBACK, and here is why it exists: the tab
        # widgets come from trame-vuetify, an optional
        # install. Without them the page still has to
        # show all five panels, so they are stacked in
        # the flat order they had before the tabs -
        # Confidence, then S-Parameters, then the Far
        # Field pattern, then the Circuit box, then the
        # Mode caption that used
        # to sit in the readout. Same
        # emitters, same state names, same eagerly
        # loaded payloads; only the tab container around
        # them is missing.
        _emit_confidence_panel()
        _emit_s_params_panel()
        _emit_far_field_panel()
        _emit_circuit_netlist()
        _emit_load_series_panel(
            info.get("load_series"),
            info.get("load_series_reason"),
        )
        _emit_mode_caption()
        _emit_mode_picker()
        _emit_vector_toggle()
