"""Reading KiCad boards (``.kicad_pcb``) into plain Python objects.

Why a hand-written reader
-------------------------
The obvious alternatives are the KiCad Python bindings (``pcbnew``, which exist
only inside a full KiCad install) and a geometry stack such as ``kikit`` plus
``shapely``.  Neither is a dependency of this package, and neither is needed for
the part a field solver cares about: a ``.kicad_pcb`` file is S-expression text,
and layers, nets, tracks, vias, pads, zones and the outline sit within a handful
of nesting levels of the root.  A reader written against the standard library
only costs a couple of hundred lines and runs wherever Python runs, which is the
same bargain :mod:`emfit.grid` strikes by not depending on a mesher.

Units
-----
**Every length in this module is a millimetre.**  A ``.kicad_pcb`` file carries
no unit declaration and pcbnew always writes millimetres, so the numbers are
taken verbatim and never scaled.  Angles are degrees.

Tolerance
---------
The format grows between KiCad releases and this reader is built to survive
that: an unknown form is ignored, a missing key becomes ``None`` or an empty
list, and a board with no stackup, no zones or no vias loads without complaint.
Both the tokeniser loop and the outline walk are iterative, so a deeply nested
file cannot exhaust the interpreter stack.

What is deliberately not modelled
---------------------------------
* **Zone fills.**  A poured zone stores a triangulation per island, which is a
  mesh rather than a description.  :attr:`Zone.has_fill` records whether such
  geometry is present and nothing more; interpreting it is the caller's job.
* **Footprint-local geometry in the raw model.**  A :class:`Pad` keeps the
  position the file stores for it, which is in the footprint's own frame.  The
  one place that rotates and translates a pad onto the board is
  :meth:`Board.pads_in_board_frame`, and that view -- not :attr:`Board.pads` --
  is what geometry code should consume.

Pad placement
-------------
:meth:`Board.pads_in_board_frame` turns a footprint-local :class:`Pad` into a
:class:`PlacedPad` in board millimetres.  For a pad at footprint-local
``(x, y)`` inside a footprint at ``(px, py)`` whose ``at`` carries the
orientation ``theta``, the board-frame centre is::

    x' = px + x cos(theta) + y sin(theta)
    y' = py + y cos(theta) - x sin(theta)

Everything stays in the file's own frame, where ``y`` grows *downwards*: read
on screen, the formula above is a *counter-clockwise* rotation by ``theta``,
which is what pcbnew calls a positive orientation.  The sign was not assumed --
it was checked against KiCad's own artwork.  ``J1`` of the coupon fixture is
placed at ``(4.5, 10, 90)`` and its asymmetric silkscreen chevron, drawn at
footprint-local ``(-4.1, 0.5) -> (-3.6, 0) -> (-4.1, -0.5)``, appears in
``F_Silkscreen.gto`` at ``(5.0, 14.1) -> (4.5, 13.6) -> (4.0, 14.1)`` (Gerber
``y`` negated), which is what this sign produces and what the opposite sign
cannot produce.

A footprint on ``B.Cu`` needs no second mirroring here.  KiCad mirrors a
footprint's pads when the footprint is *flipped* and then writes the result:
pcbnew stores each pad's relative position as ``RotatePoint(pos - fp_pos,
-fp_orientation)`` and writes pad layer sets as ``B.Cu``/``B.Mask``, so the
stored local geometry is already mirrored and the formula above holds on both
sides.  Applying another mirror on top of it would mirror twice.  Unlike the
rotation sign, that reading is *not* verified against an oracle here: there is
no ``B.Cu`` footprint anywhere in this repository, so :attr:`PlacedPad.side` is
reported and nothing further is claimed about the back side.

Layer questions are refused rather than guessed.  A footprint whose layer is
neither ``F.Cu`` nor ``B.Cu``, and a pad declaring a layer that is neither
copper nor mask nor paste or a copper layer this board does not have, raise
:class:`LayerError` naming the footprint and, where there is one, the pad.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np

__all__ = [
    "Board",
    "Footprint",
    "LayerError",
    "Net",
    "Pad",
    "PlacedPad",
    "StackupEntry",
    "Track",
    "Via",
    "Zone",
    "load_board",
    "parse_file",
    "parse_sexpr",
    "tokenize",
]

#: A point in millimetres, ``(x, y)``.
Point = tuple[float, float]

# ---------------------------------------------------------------------------
# S-expression layer
# ---------------------------------------------------------------------------

#: One quoted string (with backslash escapes), one paren, or one bare atom.
_TOKEN_RE = re.compile(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()"]+')

#: The escapes KiCad actually emits; anything else is taken literally.
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"'}


def _unquote(tok: str) -> str:
    """Strip the surrounding quotes and resolve backslash escapes."""
    body = tok[1:-1]
    if "\\" not in body:
        return body
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            out.append(_ESCAPES.get(body[i + 1], body[i + 1]))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _atom(tok: str) -> object:
    """Classify one raw token: quoted string, int, float, or bare atom."""
    if tok[0] == '"':
        return _unquote(tok)
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        return tok


def tokenize(text: str) -> Iterator[str]:
    """Yield the raw tokens of ``text``: parens, bare atoms, quoted strings.

    Quoted strings are yielded verbatim, quotes and escapes included, so that
    :func:`parse_sexpr` is the single place that decides how to unescape them.
    """
    for match in _TOKEN_RE.finditer(text):
        yield match.group(0)


def parse_sexpr(text: str) -> list:
    """Parse S-expression text into nested lists of atoms.

    Returns the list of *top-level* forms, normally exactly one for a KiCad
    file.  Quoted strings become ``str``, integer atoms become ``int``, other
    numeric atoms become ``float``, and every remaining atom stays a ``str``
    (so ``signal`` and ``F.Cu`` survive unchanged).

    The paren matching is an explicit stack, not recursion, and a stray ``)`` at
    top level is dropped rather than raised: one malformed bracket should not
    cost the caller an entire board.
    """
    stack: list[list] = [[]]
    for tok in tokenize(text):
        if tok == "(":
            node: list = []
            stack[-1].append(node)
            stack.append(node)
        elif tok == ")":
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1].append(_atom(tok))
    return stack[0]


def parse_file(path) -> list:
    """Read ``path`` and return its top-level S-expression forms."""
    return parse_sexpr(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# small accessors over the parsed tree
# ---------------------------------------------------------------------------
def _head(node) -> str | None:
    """Name of a form, i.e. its first atom, or ``None`` for a bare list."""
    if isinstance(node, list) and node and isinstance(node[0], str):
        return node[0]
    return None


def _kids(node, name: str) -> list:
    """Every direct child form whose head is ``name``, in file order."""
    return [c for c in node[1:] if _head(c) == name]


def _kid(node, name: str):
    """The first direct child form whose head is ``name``, or ``None``."""
    for c in node[1:]:
        if _head(c) == name:
            return c
    return None


def _scalar(node, name: str, default=None):
    """First argument of the child form ``(name arg ...)``."""
    child = _kid(node, name)
    if child is None or len(child) < 2:
        return default
    return child[1]


def _num(node, name: str, default=None) -> float | None:
    """Child form ``(name value)`` as a ``float``, or ``default``."""
    value = _scalar(node, name, None)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(node, name: str, default=0):
    """Child form ``(name value)`` as an ``int``, or ``default``."""
    value = _scalar(node, name, None)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _str(node, name: str, default: str = "") -> str:
    """Child form ``(name value)`` as a ``str``, or ``default``."""
    value = _scalar(node, name, None)
    return default if value is None else str(value)


def _opt_str(node, name: str) -> str | None:
    """Child form ``(name value)`` as a ``str``, or ``None`` when absent."""
    value = _scalar(node, name, None)
    return None if value is None else str(value)


def _numbers(form, skip: int = 0) -> list[float]:
    """The numeric arguments of a form, as floats, after ``skip`` positions."""
    if form is None:
        return []
    return [float(v) for v in form[1 + skip:] if isinstance(v, (int, float))]


def _point(form, default: Point = (0.0, 0.0)) -> Point:
    """The first two numeric arguments of a coordinate form, in millimetres."""
    vals = _numbers(form)
    if len(vals) < 2:
        return default
    return (vals[0], vals[1])


def _rotation(form) -> float:
    """The third numeric argument of an ``(at x y rot)`` form, in degrees."""
    vals = _numbers(form)
    return vals[2] if len(vals) > 2 else 0.0


# ---------------------------------------------------------------------------
# board model
# ---------------------------------------------------------------------------
@dataclass
class StackupEntry:
    """One physical layer of the board cross-section.

    ``kind`` is a normalised label: ``copper``, ``core``, ``prepreg``,
    ``soldermask``, ``silkscreen``, ``paste`` or ``other``.  ``thickness`` is in
    millimetres and is ``None`` when the file omits it -- silkscreen and paste
    layers never carry one, and a stackup saved by an older KiCad may have no
    thicknesses at all.  ``epsilon_r`` and ``loss_tangent`` are ``None`` for
    every non-dielectric, and for dielectrics in files that predate the fields.
    """

    name: str
    kind: str
    thickness: float | None = None
    material: str | None = None
    epsilon_r: float | None = None
    loss_tangent: float | None = None

    @property
    def is_copper(self) -> bool:
        """Whether this entry is a copper foil."""
        return self.kind == "copper"


@dataclass
class Net:
    """A net declaration.  Code 0 is the unnamed net and is always present."""

    code: int
    name: str


@dataclass
class Track:
    """One straight copper segment (``segment`` in the file).

    ``start`` and ``end`` are board coordinates, ``width`` is the drawn width,
    all in millimetres.
    """

    start: Point
    end: Point
    width: float
    layer: str
    net: int

    def length(self) -> float:
        """Length in millimetres."""
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return float(np.hypot(dx, dy))


@dataclass
class Via:
    """A plated via.

    ``size`` is the pad diameter and ``drill`` the finished hole, both in
    millimetres; ``layers`` is the layer span exactly as written, which for an
    ordinary through via is ``("F.Cu", "B.Cu")``.  ``span`` normalises the
    file's optional ``blind``/``micro`` marker to ``through``, ``blind`` or
    ``micro`` so that callers need not re-parse it.
    """

    position: Point
    size: float | None
    drill: float | None
    layers: tuple[str, str]
    net: int
    span: str = "through"

    @property
    def is_through(self) -> bool:
        """Whether the via crosses the whole board."""
        return self.span == "through"


@dataclass
class Pad:
    """One footprint pad.

    ``position`` is *footprint-local* millimetres -- what the file stores, in
    the footprint's own frame -- so it must be rotated and translated by the
    owning :class:`Footprint` before it means anything on the board.  Ask
    :meth:`Board.pads_in_board_frame` for that placed view; it is the only place
    in this module that does the arithmetic.

    ``size`` keeps the file's own shape (one number for a circular pad, two for
    anything rectangular or oval) and ``layers`` keeps the raw layer tokens,
    wildcards included, which is why :meth:`on_layer` is the thing to ask rather
    than the tuple itself.  For an oval drill ``drill`` is the first (x)
    dimension.
    """

    number: str
    type: str
    shape: str
    position: Point
    size: tuple[float, ...]
    layers: tuple[str, ...]
    drill: float | None
    net: int
    rotation: float = 0.0

    def on_layer(self, layer: str) -> bool:
        """Whether the pad touches ``layer``, honouring ``*.Cu``/``F&B.Cu``."""
        if layer in self.layers:
            return True
        copper = layer.endswith(".Cu")
        for token in self.layers:
            if token == "*.Cu" and copper:
                return True
            if token == "F&B.Cu" and layer in ("F.Cu", "B.Cu"):
                return True
        return False


@dataclass
class Footprint:
    """A placed component.

    ``position`` and ``rotation`` are board coordinates and degrees; the pads'
    own positions stay in the footprint frame (see :class:`Pad`).  ``value``
    comes from the ``Value`` property when the file has one and falls back to
    the ``fp_text value`` field otherwise, because KiCad 6 wrote the latter and
    KiCad 7 the former.
    """

    reference: str
    value: str
    position: Point
    rotation: float
    layer: str
    pads: list[Pad] = field(default_factory=list)
    library_link: str | None = None


#: Pad layer tokens that are not copper and need no interpretation: they carry
#: no current and take no part in the board-frame transform.
_NON_COPPER_PAD_LAYERS = frozenset(
    {"F.Mask", "B.Mask", "*.Mask", "F.Paste", "B.Paste", "*.Paste"}
)


class LayerError(ValueError):
    """A footprint or pad sits on a layer whose meaning this module cannot place.

    Raised instead of guessing, because a wrong side or a wrong copper layer
    would silently put a pad on the wrong face of the board -- exactly the kind
    of error a field solver is least able to notice.
    """


@dataclass(frozen=True)
class PlacedPad:
    """One pad in board coordinates, as :meth:`Board.pads_in_board_frame` returns it.

    ``position`` is the pad centre in board millimetres and ``rotation`` the
    absolute orientation in degrees, the footprint's ``at`` angle plus the pad's
    own; the module docstring states the convention and how its sign was
    checked.  ``side`` is ``"front"`` or ``"back"`` and comes from the owning
    footprint's layer, while ``copper_layers`` lists the copper layers of *this
    board* that the pad actually reaches -- every one of them for a ``*.Cu``
    through-hole pad, a single layer for an SMD pad.  ``net_name`` is
    :meth:`Board.net_name` of the pad's net code, so an unnamed net is ``""``.
    """

    reference: str
    number: str
    side: str
    position: Point
    rotation: float
    copper_layers: tuple[str, ...]
    shape: str
    size: tuple[float, ...]
    drill: float | None
    net_name: str


def _footprint_side(footprint: Footprint) -> str:
    """``"front"`` or ``"back"`` from the footprint layer, refusing anything else."""
    if footprint.layer == "F.Cu":
        return "front"
    if footprint.layer == "B.Cu":
        return "back"
    raise LayerError(
        f"footprint {footprint.reference!r} is placed on layer "
        f"{footprint.layer!r}, which is neither 'F.Cu' nor 'B.Cu', so which side "
        "of the board its pads sit on is not intelligible"
    )


def _pad_copper_layers(
    pad: Pad, copper: list[str], reference: str
) -> tuple[str, ...]:
    """The board copper layers ``pad`` reaches, refusing unknown layer tokens."""
    # A file with no ``(layers ...)`` table still has the two outer layers.
    known = list(copper) or ["F.Cu", "B.Cu"]
    reached: list[str] = []
    for token in pad.layers:
        if token == "*.Cu":
            reached.extend(known)
        elif token == "F&B.Cu":
            reached.extend(name for name in ("F.Cu", "B.Cu") if name in known)
        elif token in _NON_COPPER_PAD_LAYERS:
            continue
        elif token.endswith(".Cu"):
            if token not in known:
                raise LayerError(
                    f"pad {pad.number!r} of footprint {reference!r} declares copper "
                    f"layer {token!r}, which this board does not have"
                )
            reached.append(token)
        else:
            raise LayerError(
                f"pad {pad.number!r} of footprint {reference!r} declares layer "
                f"{token!r}, which is neither copper, mask nor paste"
            )
    if not reached:
        raise LayerError(
            f"pad {pad.number!r} of footprint {reference!r} reaches no copper layer"
        )
    return tuple(dict.fromkeys(reached))


@dataclass
class Zone:
    """A copper pour or keepout outline.

    ``outline`` is an ``(n, 2)`` array of millimetre vertices taken from the
    first ``polygon`` in the file; additional islands are not modelled, and an
    arc inside the outline contributes its two endpoints only.  ``layers``
    holds every layer the zone is applied to, so a single-layer pour and a
    multi-layer plane share one representation.

    ``has_fill`` is the honest answer to "was this zone ever poured": it is
    ``True`` only when the file carries ``filled_polygon`` or ``fill_segments``
    geometry.  The geometry itself is not parsed -- see the module docstring.
    """

    net: int
    net_name: str
    layers: tuple[str, ...]
    priority: int
    outline: np.ndarray
    has_fill: bool
    keepout: bool = False
    min_thickness: float | None = None

    def __post_init__(self):
        self.outline = np.asarray(self.outline, dtype=float).reshape(-1, 2)


@dataclass
class Board:
    """A parsed board.  All lengths are millimetres.

    ``copper_layers`` is ordered front to back, ``layer_names`` maps a canonical
    KiCad layer name to the user-facing name where the file provides one (a
    KiCad 6 file typically does not), and ``edge_bbox`` is
    ``(xmin, ymin, xmax, ymax)`` over every ``Edge.Cuts`` drawing item, or
    ``None`` for a board with no outline drawn at all.
    """

    version: int | None
    generator: str
    thickness: float | None
    copper_layers: list[str]
    layer_names: dict[str, str]
    stackup: list[StackupEntry]
    nets: list[Net]
    tracks: list[Track]
    vias: list[Via]
    footprints: list[Footprint]
    zones: list[Zone]
    edge_bbox: tuple[float, float, float, float] | None

    # ------------------------------------------------------------------
    # derived views
    # ------------------------------------------------------------------
    @property
    def pads(self) -> list[Pad]:
        """Every pad of every footprint, flattened, still footprint-local."""
        return [pad for fp in self.footprints for pad in fp.pads]

    def pads_in_board_frame(self) -> list[PlacedPad]:
        """Every pad, rotated and translated into board coordinates.

        Pads come back footprint by footprint in the order
        :attr:`footprints` holds them and, within a footprint, in file order, so
        a caller can match them against an artwork import one for one.  The
        transform and the sign of the rotation are stated in the module
        docstring; so is the one thing here that is reasoned rather than
        verified, namely the back side.  A flipped footprint follows the same
        rule because KiCad writes each pad's post-flip local coordinates; no
        back-side footprint exists in this repository, so that half is argued
        from the format and not checked against plotted artwork.

        Raises
        ------
        LayerError
            If a footprint sits on a layer that is neither ``F.Cu`` nor
            ``B.Cu``, or a pad declares a layer that cannot be placed.
        """
        placed: list[PlacedPad] = []
        for footprint in self.footprints:
            side = _footprint_side(footprint)
            radians = math.radians(footprint.rotation)
            cos, sin = math.cos(radians), math.sin(radians)
            px, py = footprint.position
            copper = _pad_copper_layers
            for pad in footprint.pads:
                x, y = pad.position
                placed.append(
                    PlacedPad(
                        reference=footprint.reference,
                        number=pad.number,
                        side=side,
                        position=(px + x * cos + y * sin, py + y * cos - x * sin),
                        rotation=(footprint.rotation + pad.rotation) % 360.0,
                        copper_layers=copper(pad, self.copper_layers, footprint.reference),
                        shape=pad.shape,
                        size=pad.size,
                        drill=pad.drill,
                        net_name=self.net_name(pad.net),
                    )
                )
        return placed

    def pad_at(self, reference: str, number: str) -> PlacedPad:
        """The one pad called ``number`` of the footprint called ``reference``.

        ``reference`` and ``number`` are the file's own identifiers, compared as
        text -- a footprint reference such as ``J1`` and a pad number such as
        ``1``, not a position -- and the pad comes back placed like every other
        one from :meth:`pads_in_board_frame`, in board millimetres.

        A pad number that appears more than once inside one footprint is refused
        rather than disambiguated by position.  "Pad 2 of J1" is a different
        question on a two-leg part and on a four-leg one, and the file does not
        say which leg an instrument would be connected to, so picking the
        nearest one would be a guess dressed as an answer.

        Raises
        ------
        ValueError
            If no pad matches the pair, or if more than one does.  The first
            message lists every pad the board declares; the second gives the
            board-frame position of each candidate.
        """
        wanted = str(number)
        placed = self.pads_in_board_frame()
        matches = [pad for pad in placed
                   if pad.reference == reference and str(pad.number) == wanted]
        if not matches:
            known = ", ".join(
                sorted({f"{pad.reference}.{pad.number}" for pad in placed})) \
                or "none"
            raise ValueError(
                f"no pad {reference}.{wanted} on this board; the pads it declares "
                f"are {known}")
        if len(matches) > 1:
            listing = "; ".join(
                f"({pad.position[0]:g}, {pad.position[1]:g}) mm"
                for pad in matches)
            raise ValueError(
                f"{len(matches)} pads are called {reference}.{wanted}: {listing}. "
                f"A pad number that appears more than once inside one footprint "
                f"cannot name a single port -- the file does not say which of "
                f"them an instrument would be connected to, so this is refused "
                f"instead of being resolved by position")
        return matches[0]

    def net_name(self, code: int) -> str:
        """Name of net ``code``, or ``""`` if the board never declares it."""
        for net in self.nets:
            if net.code == code:
                return net.name
        return ""

    def used_net_codes(self) -> set[int]:
        """Net codes with at least one track, via, pad or zone attached.

        Compare the size of this with ``len(board.nets)`` to see how much of the
        schematic the layout actually carries.
        """
        used = {t.net for t in self.tracks}
        used |= {v.net for v in self.vias}
        used |= {p.net for p in self.pads}
        used |= {z.net for z in self.zones}
        return used

    def stackup_thickness(self) -> float | None:
        """Sum of the stackup thicknesses in millimetres, or ``None``.

        This is the cross-section as drawn, so for a well-formed file it equals
        the declared board ``thickness``.
        """
        vals = [e.thickness for e in self.stackup if e.thickness is not None]
        return float(sum(vals)) if vals else None


# ---------------------------------------------------------------------------
# form -> model
# ---------------------------------------------------------------------------
#: Substrings of the stackup ``type`` string, longest/most specific first.
_STACKUP_KINDS = (
    ("copper", "copper"),
    ("solder mask", "soldermask"),
    ("silk", "silkscreen"),
    ("paste", "paste"),
    ("prepreg", "prepreg"),
    ("core", "core"),
)

#: Layer types that are copper, as opposed to documentation/mechanical layers.
_COPPER_TYPES = ("signal", "power", "mixed", "jumper")


def _stackup_kind(type_name: str) -> str:
    """Normalise a stackup ``type`` string, e.g. ``Top Solder Mask``."""
    low = type_name.lower()
    for needle, kind in _STACKUP_KINDS:
        if needle in low:
            return kind
    return "other"


def _parse_stackup(forms) -> list[StackupEntry]:
    """The ``(stackup ...)`` block of ``(setup ...)``, or an empty list."""
    node = None
    for form in forms:
        if _head(form) == "setup":
            node = _kid(form, "stackup")
            if node is not None:
                break
    if node is None:
        return []
    out = []
    for layer in _kids(node, "layer"):
        type_form = _kid(layer, "type")
        type_name = ""
        if type_form is not None and len(type_form) > 1:
            type_name = str(type_form[1])
        out.append(
            StackupEntry(
                name=str(layer[1]) if len(layer) > 1 else "",
                kind=_stackup_kind(type_name),
                thickness=_num(layer, "thickness"),
                material=_opt_str(layer, "material"),
                epsilon_r=_num(layer, "epsilon_r"),
                loss_tangent=_num(layer, "loss_tangent"),
            )
        )
    return out


def _parse_layers(forms) -> tuple[list[str], dict[str, str]]:
    """Copper layers front-to-back, plus canonical -> user names.

    Sorting by the numeric layer id gives the physical order regardless of how
    the file happens to list them; ``F.Cu`` is 0 and ``B.Cu`` is 31 by
    convention, so the sort puts the back copper last.
    """
    node = None
    for form in forms:
        if _head(form) == "layers":
            node = form
            break
    if node is None:
        return [], {}
    copper: list[tuple[int, str]] = []
    names: dict[str, str] = {}
    for entry in node[1:]:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        canon = str(entry[1])
        kind = str(entry[2]) if len(entry) > 2 else ""
        user = str(entry[3]) if len(entry) > 3 else ""
        if kind in _COPPER_TYPES:
            try:
                ident = int(entry[0])
            except (TypeError, ValueError):
                ident = len(copper)
            copper.append((ident, canon))
        if user and user != canon:
            names[canon] = user
    copper.sort(key=lambda item: item[0])
    return [canon for _, canon in copper], names


def _parse_thickness(root) -> float | None:
    """The declared board thickness from ``(general (thickness ...))``."""
    general = _kid(root, "general")
    if general is None:
        return None
    return _num(general, "thickness")


def _parse_net(form) -> Net:
    """One top-level ``(net code "name")`` declaration."""
    code = form[1] if len(form) > 1 else 0
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = 0
    return Net(code=code, name=str(form[2]) if len(form) > 2 else "")


def _parse_track(form) -> Track:
    """One ``(segment ...)`` form."""
    return Track(
        start=_point(_kid(form, "start")),
        end=_point(_kid(form, "end")),
        width=_num(form, "width", 0.0),
        layer=_str(form, "layer"),
        net=_int(form, "net", 0),
    )


def _parse_via(form) -> Via:
    """One ``(via ...)`` form, normalising the through/blind/micro marker."""
    layers: tuple[str, str] = ("", "")
    node = _kid(form, "layers")
    if node is not None:
        vals = [str(v) for v in node[1:] if isinstance(v, str)]
        if len(vals) >= 2:
            layers = (vals[0], vals[1])
    span = "through"
    # KiCad writes the marker as a bare atom right after "via", and some
    # exporters write it as (type blind); accept either spelling.
    for tok in form[1:3]:
        if isinstance(tok, str) and tok in ("blind", "buried", "micro"):
            span = "micro" if tok == "micro" else "blind"
    type_form = _kid(form, "type")
    if type_form is not None and len(type_form) > 1 and isinstance(type_form[1], str):
        if type_form[1] == "micro":
            span = "micro"
        elif type_form[1] in ("blind", "buried"):
            span = "blind"
    return Via(
        position=_point(_kid(form, "at")),
        size=_num(form, "size"),
        drill=_num(form, "drill"),
        layers=layers,
        net=_int(form, "net", 0),
        span=span,
    )


def _parse_pad(form) -> Pad:
    """One ``(pad ...)`` form.  Position stays in the footprint frame."""
    size_form = _kid(form, "size")
    layers_form = _kid(form, "layers")
    drill = None
    drill_form = _kid(form, "drill")
    if drill_form is not None:
        # (drill 0.65) or (drill oval 1.2 0.6); take the first dimension and
        # let the caller see the pad shape if it needs the second.
        vals = _numbers(drill_form)
        if vals:
            drill = vals[0]
    return Pad(
        number=str(form[1]) if len(form) > 1 else "",
        type=str(form[2]) if len(form) > 2 else "",
        shape=str(form[3]) if len(form) > 3 else "",
        position=_point(_kid(form, "at")),
        size=tuple(_numbers(size_form)),
        layers=tuple(str(v) for v in (layers_form[1:] if layers_form else [])
                     if isinstance(v, str)),
        drill=drill,
        net=_int(form, "net", 0),
        rotation=_rotation(_kid(form, "at")),
    )


def _parse_footprint(form) -> Footprint:
    """One ``(footprint ...)`` form, including its pads."""
    reference = ""
    value = ""
    for prop in _kids(form, "property"):
        if len(prop) > 2 and str(prop[1]) == "Reference":
            reference = str(prop[2])
        elif len(prop) > 2 and str(prop[1]) == "Value":
            value = str(prop[2])
    for text in _kids(form, "fp_text"):
        if len(text) > 2 and str(text[1]) == "reference" and not reference:
            reference = str(text[2])
        elif len(text) > 2 and str(text[1]) == "value" and not value:
            value = str(text[2])
    at = _kid(form, "at")
    return Footprint(
        reference=reference,
        value=value,
        position=_point(at),
        rotation=_rotation(at),
        layer=_str(form, "layer"),
        pads=[_parse_pad(p) for p in _kids(form, "pad")],
        library_link=str(form[1]) if len(form) > 1 and isinstance(form[1], str) else None,
    )


def _parse_zone(form) -> Zone:
    """One ``(zone ...)`` form.  Fill geometry is recorded, not interpreted."""
    layers: tuple[str, ...] = ()
    node = _kid(form, "layers")
    if node is not None:
        layers = tuple(str(v) for v in node[1:] if isinstance(v, str))
    else:
        single = _kid(form, "layer")
        if single is not None and len(single) > 1:
            layers = (str(single[1]),)
    outline = np.zeros((0, 2))
    polygon = _kid(form, "polygon")
    if polygon is not None:
        pts = _kid(polygon, "pts")
        if pts is not None:
            verts = [(float(p[1]), float(p[2])) for p in _kids(pts, "xy") if len(p) > 2]
            if verts:
                outline = np.asarray(verts, dtype=float)
    return Zone(
        net=_int(form, "net", 0),
        net_name=_opt_str(form, "net_name") or "",
        layers=layers,
        priority=_int(form, "priority", 0),
        outline=outline,
        has_fill=bool(_kids(form, "filled_polygon") or _kids(form, "fill_segments")),
        keepout=_kid(form, "keepout") is not None,
        min_thickness=_num(form, "min_thickness"),
    )


#: Coordinate children of a drawing form, as written by pcbnew.
_COORD_HEADS = ("start", "end", "mid", "center", "xy")


def _draw_points(node) -> list[Point]:
    """Coordinate children of a drawing form, in millimetres."""
    pts: list[Point] = []
    for child in node[1:]:
        head = _head(child)
        if head in _COORD_HEADS:
            vals = _numbers(child)
            if len(vals) >= 2:
                pts.append((vals[0], vals[1]))
        elif head == "pts":
            pts.extend(_draw_points(child))
    return pts


def _edge_bbox(forms):
    """``(xmin, ymin, xmax, ymax)`` over every ``Edge.Cuts`` item, or ``None``.

    Both board-level ``gr_*`` items and footprint-level ``fp_*`` items are
    visited, because an outline is occasionally drawn inside a footprint (a
    castellated module, say).  The walk uses an explicit stack, so nesting depth
    is not a hazard.
    """
    pts: list[Point] = []
    stack = list(forms)
    while stack:
        node = stack.pop()
        if not isinstance(node, list):
            continue
        head = _head(node)
        if head is None:
            continue
        if head.startswith("gr_") or head.startswith("fp_"):
            if _str(node, "layer") == "Edge.Cuts":
                pts.extend(_draw_points(node))
            continue
        stack.extend(c for c in node[1:] if isinstance(c, list))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def load_board(path) -> Board:
    """Read a ``.kicad_pcb`` file and return a :class:`Board`.

    All lengths are millimetres.  Unknown forms are ignored, and a file with no
    stackup, no zones or no vias still loads -- the corresponding attributes are
    simply empty.
    """
    forms = parse_file(path)
    root = None
    for form in forms:
        if _head(form) == "kicad_pcb":
            root = form
            break
    if root is None:
        raise ValueError(f"{path}: no (kicad_pcb ...) form found")
    copper_layers, layer_names = _parse_layers(root[1:])
    return Board(
        version=_int(root, "version", None),
        generator=_str(root, "generator"),
        thickness=_parse_thickness(root),
        copper_layers=copper_layers,
        layer_names=layer_names,
        stackup=_parse_stackup(root[1:]),
        nets=[_parse_net(f) for f in _kids(root, "net")],
        tracks=[_parse_track(f) for f in _kids(root, "segment")],
        vias=[_parse_via(f) for f in _kids(root, "via")],
        footprints=[_parse_footprint(f) for f in _kids(root, "footprint")],
        zones=[_parse_zone(f) for f in _kids(root, "zone")],
        edge_bbox=_edge_bbox(forms),
    )
