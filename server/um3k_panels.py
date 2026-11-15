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
    """Fill the caller's left column with SETUP: the solve controls.

    Called inside the left ``VCol`` of the 3-column row, and stated as one
    callback call so the widgets still land in the caller's layout. ``ctx``
    holds the callables rather than this module closing over the page
    (``poc_app.py`` registers them at the row, just before it opens).
    """
    ctx.callback("_emit_solve_controls")()


def build_center_panel(ctx) -> object:
    """Fill the caller's centre column with VIEW: the picture and its player bar.

    Called from inside the centre ``VCol`` of the 3-column row, so the wrapper
    div and the player-bar row land in the caller's layout. Objects the page
    already owns arrive as handles (the widget table, the controller, the frame
    count, the plotter); the three callables the body calls arrive as callbacks.
    ``nt`` is the frame count as the page registered it, which is the count this
    layout is built with. Returns the view ``plotter_ui`` made, which the page
    keeps as ``handles["view"]``.
    """
    widgets = ctx.handle("widgets")
    ctrl = ctx.handle("ctrl")
    nt = ctx.handle("nt")
    plotter = ctx.handle("plotter")
    html_div = ctx.callback("html_div")
    VRow = ctx.callback("VRow")
    plotter_ui = ctx.callback("plotter_ui")

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
        if "VBtn" in widgets:
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
        if "VSlider" in widgets and "VLabel" in widgets:
            try:
                widgets["VSlider"](
                    v_model=("frame", 0),
                    min=0,
                    max=("frame_max", nt - 1),
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
        with tabs_cls(v_model=("tab", "s_params")):
            tab_cls("S-Parameters", value="s_params")
            # Second, beside the S-parameters it is
            # read against: both are the antenna's
            # own numbers, one from the feed and
            # one from the radiating currents.
            tab_cls("Far Field", value="far_field")
            tab_cls(
                "Confidence N-lambda",
                value="confidence",
            )
            tab_cls("Modes", value="modes")
            tab_cls("Circuit", value="circuit")
        with tabs_window_cls(
            v_model=("tab", "s_params")
        ):
            with tabs_item_cls(value="s_params"):
                _emit_s_params_panel()
            with tabs_item_cls(value="far_field"):
                _emit_far_field_panel()
            with tabs_item_cls(value="confidence"):
                _emit_confidence_panel()
            with tabs_item_cls(value="modes"):
                # The Mode panel's ONE line: the
                # hint before the first press, the
                # solve's own caption after one, or
                # the reason the solve refused.
                _emit_mode_caption()
                _emit_mode_picker()
                # The arrow toggle sits with the
                # picker it annotates: both are
                # about the picture above them.
                _emit_vector_toggle()
            with tabs_item_cls(value="circuit"):
                # The netlist's OWN home, so it is
                # reachable without scrolling the
                # SETUP column to find it.
                html_div(
                    "The netlist names the circuit "
                    "on the load's cut; its V(t) "
                    "and I(t) become part of the "
                    "run. Empty box = the built-in "
                    "resistor.",
                    style="padding: 2px 0;",
                )
                _emit_circuit_netlist()
                # The load's trace belongs to the netlist above it.
                _emit_load_series_panel(
                    info.get("load_series"),
                    info.get("load_series_reason"),
                )
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
