"""The state of ONE um3k page: what was loaded, what can be shown, what is drawn.

Not a loader (``reload_page`` is the one reader, poc_app.py:5333-5391), not a
drawing module (no trame, no pyvista at any level; the plotter is ``typing.Any``,
the separation ``poc_app`` draws around its 2D compute layer, poc_app.py:5396-5398)
and not a second opinion on ``is_vis`` (poc_app.py:348-353, used at :5390, :9541).
:class:`Available` is a frozen snapshot; :meth:`PageContext.recompute_available`
refreshes it, so a flag read and the draw after it cannot see the ground move.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# --- the key names one page's data is read by -------------------------------
# Copied literals, not imports (poc_app is a 441 KB UI module behind five
# strings); a test pins each one against poc_app's own constant, so the copies
# cannot drift in silence.
PLANE_KEY = "plane_ez"  # poc_app.py:96 - the legacy dump's (station, y, z) |Ez|
VOLUME_KEY = "e_centres"  # poc_app.py:100 - the colocated E volume (nx, ny, nz, 3)
VOLUME_RAW_KEY = "e_raw"  # poc_app.py:106 - the same vector, still un-colocated
VIS_FORMAT = "um3k"  # poc_app.py:154 - what load_vis writes (poc_app.py:500)
VIS_FORMATS = (VIS_FORMAT, "wavedude")  # poc_app.py:155 - the set _is_vis opens
FALLBACK_SRC = "FALLBACK"  # poc_app.py:3138 - provenance of a port x nobody recorded

#: :attr:`PageContext.view_mode`'s legal values: the label branches on the exact
#: string ``"port"`` and draws the volume otherwise (poc_app.py:3257, :3272); the
#: toggle flips between these two (:4239).
VIEW_MODES = ("port", "volume")
#: What the page shows before anyone toggles it (poc_app.py:4106).
DEFAULT_VIEW_MODE = "volume"
#: One page's seven values, in ``reload_page``'s order (poc_app.py:5380-5390);
#: the first six are ``PAGE_KEYS`` (poc_app.py:6894).
PAGE_FIELDS = ("path", "info", "planes", "multifreq", "structure_id", "record", "is_vis")


@dataclass
class LoadedDump:
    """One page's loaded values, as ``reload_page`` hands them over.

    ``is_vis`` is ``None`` when nobody has said, and :meth:`Available.compute`
    then applies the loader's own rule (poc_app.py:353), not one of its own.
    """

    path: Optional[Path] = None
    info: dict = field(default_factory=dict)
    planes: dict = field(default_factory=dict)
    multifreq: Any = None
    structure_id: Optional[str] = None
    record: Optional[dict] = None
    is_vis: Optional[bool] = None

    @classmethod
    def from_any_dump(cls, page) -> "LoadedDump":
        """Build from the page ``reload_page`` assembles (poc_app.py:5379-5391).

        ``load_any_dump`` returns the loader's INFO dict and nothing else
        (poc_app.py:603 declares ``-> dict``; :630 and :686 each return one), so
        this reads the page ``reload_page`` gathers. Order is :data:`PAGE_FIELDS`,
        the one place it is spelled out: mappings by key, sequences positionally.
        """
        if isinstance(page, dict):
            return cls(**{name: page.get(name) for name in PAGE_FIELDS})
        values = tuple(page)
        if len(values) != len(PAGE_FIELDS):
            raise ValueError(
                f"from_any_dump: expected {len(PAGE_FIELDS)} values in the order "
                f"{PAGE_FIELDS}, got {len(values)}"
            )
        return cls(**dict(zip(PAGE_FIELDS, values)))


def _stations(info: dict) -> int:
    """How many x-planes the page captured; 0 when it holds no plane stack.

    ``plane_ez``'s first axis is the station axis (poc_app.py:244-247), read as
    ``n_st`` (poc_app.py:3117). It never raises: the caller decides a flag here.
    """
    try:
        return int(info[PLANE_KEY].shape[0])
    except (KeyError, AttributeError, TypeError, IndexError, ValueError):
        return 0


@dataclass(frozen=True)
class Available:
    """What this page can show, decided once from the loaded data.

    Every field is a statement about the DATA, never about the widgets (whether a
    toggle exists belongs to the trame install, poc_app.py:3286-3289). An
    animation dump forks to its own viewer before any station logic runs
    (poc_app.py:9539-9545), so only ``animation``/``source_format`` describe it.
    """

    #: The 3-D vector field itself: it is a question about the KEYS the page
    #: carries, cell-centred (poc_app.py:100) or still staggered (:106), the two
    #: ``_volume_quiver_mesh`` tests before it draws anything (:6751-6762).
    volume_field: bool = False
    #: The |E| animation layer: the page carries ``e_abs_volume`` itself, which is
    #: what ``_draw_volume_layer`` paints (:16671) and what its two cut sheets are
    #: extracted from (:9139). Independent of ``plane_stack``: a vis dump has no
    #: ``plane_ez`` stack at all, and a plane-stack page need not carry a volume.
    volume_layer: bool = False
    #: The same layer, actually DRAWN: the data half above AND the page's policy
    #: half (poc_app.py:1109-1111, ``POC_SHOW_VOLUME``). Data alone cannot answer
    #: it - a vis dump carries ``e_abs_volume`` and still draws no layer, and its
    #: cut sliders would then move sheets that are not on screen.
    volume_layer_shown: bool = False
    #: The stacked-cut-plane case: MORE THAN ONE captured x-plane, which is what
    #: the volume view stacks (poc_app.py:3295-3296). Not the volume: a one-station
    #: dump can carry ``e_centres`` and a nine-station one can carry nothing.
    plane_stack: bool = False
    port_planes: bool = False
    multifreq: bool = False
    record: bool = False
    s11_record: bool = False
    animation: bool = False
    source_format: str = "field"

    @classmethod
    def compute(
        cls, info=None, planes=None, multifreq=None, record=None, is_vis=None,
        layer_shown: Optional[bool] = None
    ) -> "Available":
        """Compute every flag, once, with no I/O and no raising.

        ``info`` is the dict ``load_any_dump`` returns (poc_app.py:230-238 plane,
        :498-547 animation), ``planes`` the page layout (:3187-3202 plane,
        :5368-5376 vis), ``is_vis`` overrides :353; no file is opened here, so a
        deleted dump still answers -- and an empty page answers, every flag false.

        ``volume_field`` asks which KEYS the info holds (:100, :106) and
        ``plane_stack`` how many stations it captured (:3295-3296); the two are
        independent, so neither may be derived from the other.

        ``layer_shown`` is the POLICY half of the |E| layer - whether the page is
        switched to draw it (poc_app.py:1109-1111) - and is passed in rather than
        read here, so this module keeps no dependency on the app. ``volume_layer``
        is the data half alone; ``volume_layer_shown`` is the two ANDed, which is
        the question a cut slider asks.

        ``layer_shown=None`` is AUTOMATIC, not "off", and both halves of the reason
        are real: a vis dump carries ``e_abs_volume`` and no station axis at all, so
        declining to draw the box drew a blank page; a stacked-plane page has its own
        cut sheets, so a translucent volume box over them would show through sheets
        that already carry the field. The rule is therefore ``stations <= 1``, which
        is the same station count ``plane_stack`` is read from. An explicit True or
        False is the switch speaking and is obeyed as given.
        """
        info = info if isinstance(info, dict) else {}
        planes = planes if isinstance(planes, dict) else {}
        animation = (
            bool(is_vis) if is_vis is not None else info.get("format") in VIS_FORMATS
        )
        stations = _stations(info)
        volume_layer = info.get("e_abs_volume") is not None
        # None = AUTOMATIC (see the docstring): the page's own shape answers,
        # because neither half of the policy can be read off the data alone.
        policy = (stations <= 1) if layer_shown is None else bool(layer_shown)
        return cls(
            # The keys, not the station count (poc_app.py:100, :106, :6751-6762).
            volume_field=VOLUME_KEY in info or VOLUME_RAW_KEY in info,
            # The |E| animation volume, keyed literally like its loader (:5389).
            volume_layer=volume_layer,
            # ...and the page draws it (above AND poc_app.py:1109-1111), with
            # ``policy`` having already turned None into the automatic answer.
            volume_layer_shown=volume_layer and policy,
            plane_stack=stations > 1,  # stacks x-planes (poc_app.py:3295-3296)
            port_planes=stations > 0,  # one station (poc_app.py:3182-3185)
            multifreq=multifreq is not None,  # None is real (:5385, :981)
            record=record is not None,  # None = no record (:5357-5360)
            # An unrecorded port x is FALLBACK and the label says so (:3138, :3263).
            s11_record=planes.get("src_s11") not in (None, FALLBACK_SRC),
            animation=animation,
            source_format="vis" if animation else "field",
        )


def choose_entry(info=None, planes=None, is_vis=None) -> str:
    """Which viewer ``main`` may hand this page to: ``"vis"`` or ``"field"``.

    The one question the dispatch asks (poc_app.py:9539-9545), answered from the
    snapshot :class:`Available` already keeps - ``source_format`` - rather than
    from a second reading of the schema, so the fork and the flags under it
    cannot disagree about what was loaded. ``_is_vis`` is the loader's rule
    (poc_app.py:348-353) and :meth:`Available.compute` applies it unchanged;
    this names the answer. It never raises: a missing, empty or malformed
    ``info`` is the field page, so a deleted dump does not become a traceback.
    """
    return Available.compute(info, planes, is_vis=is_vis).source_format


class PageContext:
    """One page's data, its availability snapshot and its presentation state.

    Constructible bare, so a test can hold a page with no dump yet. ``plotter``,
    ``handles`` and ``callbacks`` are the drawing side's storage, opaque here so
    that the flag logic stays callable with no OpenGL (poc_app.py:5396-5398).
    """

    def __init__(
        self, dump: Optional[LoadedDump] = None, view_mode: str = DEFAULT_VIEW_MODE,
        plotter: Any = None, layer_shown: Optional[bool] = None
    ) -> None:
        self.dump = dump if dump is not None else LoadedDump()
        #: Kept, not folded in: ``recompute_available`` must answer the same way
        #: after a page swap, so the policy half outlives the snapshot it shaped.
        #: Stored VERBATIM, ``None`` included - the auto answer depends on the
        #: dump (``stations``), and a page swap replaces the dump, so folding that
        #: answer into a bool here would pin the old page's shape onto the new one.
        self.layer_shown = layer_shown
        self.available = self.recompute_available()
        self.set_view_mode(view_mode)
        self.plotter = plotter
        self.handles: dict[str, Any] = {}
        self.callbacks: dict[str, Any] = {}

    def recompute_available(self) -> Available:
        """Recompute the snapshot from ``self.dump`` and make it the live one.

        The explicit reload path: ``available`` is frozen at construction, so
        whoever replaces ``self.dump`` calls this rather than hoping a flag notices.
        """
        dump = self.dump
        self.available = Available.compute(
            dump.info, dump.planes, dump.multifreq, dump.record, dump.is_vis,
            layer_shown=self.layer_shown
        )
        return self.available

    def set_view_mode(self, mode: str) -> str:
        """Switch the drawn view, returning the mode that is now live.

        Checked rather than stored: the label branches on ``"port"`` and treats
        anything else as the volume (poc_app.py:3257, :3272), so a misspelling
        fails where it was made, not where it draws.
        """
        if mode not in VIEW_MODES:
            raise ValueError(
                f"{mode!r} is not a view mode: the page knows {VIEW_MODES[0]!r} and "
                f"treats {VIEW_MODES[1]!r} as the volume (poc_app.py:3257-3277)"
            )
        self.view_mode = mode
        return mode

    def register(self, name: str, fn: Any) -> None:
        """Store the callable a draw path will want under ``name``."""
        self.callbacks[name] = fn

    def register_handle(self, name: str, obj: Any) -> None:
        """Store a drawing handle (actor, widget, whatever) under ``name``."""
        self.handles[name] = obj

    def _stored(self, table: dict, name: str, kind: str) -> Any:
        """``table[name]``; KeyError naming what IS stored under ``kind``."""
        if name not in table:
            raise KeyError(
                f"no {kind} registered as {name!r}; known: {sorted(table)}"
            )
        return table[name]

    def callback(self, name: str) -> Any:
        """The callable stored under ``name``."""
        return self._stored(self.callbacks, name, "callback")

    def handle(self, name: str) -> Any:
        """The handle stored under ``name``."""
        return self._stored(self.handles, name, "handle")
