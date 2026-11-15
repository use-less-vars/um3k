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
