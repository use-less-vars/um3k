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


def build_left_panel(ctx) -> None:
    """Fill the caller's left column with SETUP: the solve controls.

    Called inside the left ``VCol`` of the 3-column row, and stated as one
    callback call so the widgets still land in the caller's layout. ``ctx``
    holds the callables rather than this module closing over the page
    (``poc_app.py`` registers them at the row, just before it opens).
    """
    ctx.callback("_emit_solve_controls")()
