"""The state of ONE um3k page: what was loaded, what can be shown, what is drawn.

Not a loader (``reload_page`` is the one reader, poc_app.py:5318-5376), not a
drawing module (no trame, no pyvista at any level; the plotter is ``typing.Any``,
the separation ``poc_app`` draws around its 2D compute layer, poc_app.py:5381-5383)
and not a second opinion on ``is_vis`` (poc_app.py:333-338, used at :5375, :9736).
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
PLANE_KEY = "plane_ez"  # poc_app.py:81 - the legacy dump's (station, y, z) |Ez|
VOLUME_KEY = "e_centres"  # poc_app.py:85 - the colocated E volume (nx, ny, nz, 3)
VOLUME_RAW_KEY = "e_raw"  # poc_app.py:91 - the same vector, still un-colocated
VIS_FORMAT = "wavedude"  # poc_app.py:485 - the value _is_vis tests (poc_app.py:338)
FALLBACK_SRC = "FALLBACK"  # poc_app.py:3123 - provenance of a port x nobody recorded

#: :attr:`PageContext.view_mode`'s legal values: the label branches on the exact
#: string ``"port"`` and draws the volume otherwise (poc_app.py:3242, :3257); the
#: toggle flips between these two (:4224).
VIEW_MODES = ("port", "volume")
#: What the page shows before anyone toggles it (poc_app.py:4091).
DEFAULT_VIEW_MODE = "volume"
#: One page's seven values, in ``reload_page``'s order (poc_app.py:5365-5375);
#: the first six are ``PAGE_KEYS`` (poc_app.py:6879).
PAGE_FIELDS = ("path", "info", "planes", "multifreq", "structure_id", "record", "is_vis")


@dataclass
class LoadedDump:
    """One page's loaded values, as ``reload_page`` hands them over.

    ``is_vis`` is ``None`` when nobody has said, and :meth:`Available.compute`
    then applies the loader's own rule (poc_app.py:338), not one of its own.
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
        """Build from the page ``reload_page`` assembles (poc_app.py:5364-5376).

        ``load_any_dump`` returns the loader's INFO dict and nothing else
        (poc_app.py:588 declares ``-> dict``; :615 and :671 each return one), so
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

    ``plane_ez``'s first axis is the station axis (poc_app.py:214-217), read as
    ``n_st`` (poc_app.py:3102). It never raises: the caller decides a flag here.
    """
    try:
        return int(info[PLANE_KEY].shape[0])
    except (KeyError, AttributeError, TypeError, IndexError, ValueError):
        return 0


@dataclass(frozen=True)
class Available:
    """What this page can show, decided once from the loaded data.

    Every field is a statement about the DATA, never about the widgets (whether a
    toggle exists belongs to the trame install, poc_app.py:3271-3274). An
    animation dump forks to its own viewer before any station logic runs
    (poc_app.py:9734-9750), so only ``animation``/``source_format`` describe it.
    """

    volume_3d: bool = False
    port_planes: bool = False
    multifreq: bool = False
    record: bool = False
    s11_record: bool = False
    animation: bool = False
    source_format: str = "field"

    @classmethod
    def compute(
        cls, info=None, planes=None, multifreq=None, record=None, is_vis=None
    ) -> "Available":
        """Compute every flag, once, with no I/O and no raising.

        ``info`` is the dict ``load_any_dump`` returns (poc_app.py:215-223 plane,
        :483-532 animation), ``planes`` the page layout (:3172-3187 plane,
        :5353-5361 vis), ``is_vis`` overrides :338; no file is opened here, so a
        deleted dump still answers -- and an empty page answers, every flag false.
        """
        info = info if isinstance(info, dict) else {}
        planes = planes if isinstance(planes, dict) else {}
        animation = (
            bool(is_vis) if is_vis is not None else info.get("format") == VIS_FORMAT
        )
        stations = _stations(info)
        return cls(
            volume_3d=stations > 1,  # stacks x-planes (poc_app.py:3280-3281)
            port_planes=stations > 0,  # one station (poc_app.py:3167-3170)
            multifreq=multifreq is not None,  # None is real (:5370, :966)
            record=record is not None,  # None = no record (:5342-5345)
            # An unrecorded port x is FALLBACK and the label says so (:3123, :3248).
            s11_record=planes.get("src_s11") not in (None, FALLBACK_SRC),
            animation=animation,
            source_format="vis" if animation else "field",
        )


class PageContext:
    """One page's data, its availability snapshot and its presentation state.

    Constructible bare, so a test can hold a page with no dump yet. ``plotter``,
    ``handles`` and ``callbacks`` are the drawing side's storage, opaque here so
    that the flag logic stays callable with no OpenGL (poc_app.py:5381-5383).
    """

    def __init__(
        self, dump: Optional[LoadedDump] = None, view_mode: str = DEFAULT_VIEW_MODE,
        plotter: Any = None
    ) -> None:
        self.dump = dump if dump is not None else LoadedDump()
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
            dump.info, dump.planes, dump.multifreq, dump.record, dump.is_vis
        )
        return self.available

    def set_view_mode(self, mode: str) -> str:
        """Switch the drawn view, returning the mode that is now live.

        Checked rather than stored: the label branches on ``"port"`` and treats
        anything else as the volume (poc_app.py:3242, :3257), so a misspelling
        fails where it was made, not where it draws.
        """
        if mode not in VIEW_MODES:
            raise ValueError(
                f"{mode!r} is not a view mode: the page knows {VIEW_MODES[0]!r} and "
                f"treats {VIEW_MODES[1]!r} as the volume (poc_app.py:3242-3262)"
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
