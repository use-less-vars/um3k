"""Reading RS-274X Gerber layers (``.gtl``/``.gbl``/``.gbr`` ...) into plain objects.

Why a hand-written reader
-------------------------
The same bargain :mod:`emfit.kicad` strikes: a Gerber file is a stream of
one-statement commands terminated by ``*`` and of extended commands wrapped in
``%...%``, so a few hundred lines of standard library code read the part a field
solver cares about -- apertures, draw/flash primitives, polarity and the extent
of the artwork.  No dependency on ``pcbnew``, ``gerbonara`` or ``shapely``.

Units
-----
**Every length in this module is a millimetre.**  Intra-file coordinates are
integers in units of ``10**-dec_digits`` of the file unit declared by ``%MO``;
they are scaled to millimetres on the way in, aperture parameters with them.
:attr:`GerberLayer.units` keeps the unit *the file declared* (``"mm"`` or
``"in"``) for reporting, not for arithmetic.

What is deliberately not modelled
---------------------------------
* **Arcs.**  ``G02``/``G03`` strokes are counted (:attr:`GerberLayer.arcs`) and
  the current point advances to their end point, but nothing is flattened into
  chords: a chord is not the arc, and ``I``/``J`` are not retained.
* **Aperture macros.**  ``%AM`` blocks are skipped, so an aperture defined
  through a macro is recorded with ``shape == "other"`` and its raw parameter
  text: its true outline is not reconstructed.
* **Paint/clear semantics.**  ``%LPC`` only bumps a counter; a clear-polarity
  primitive is stored like any other and subtracting it is the caller's job.
* **Extent expansion.**  :attr:`GerberLayer.bbox` spans primitive endpoints and
  region vertices *without* growing them by the aperture: it is the extent of
  the centreline artwork, not of the copper it produces.

Tolerance
---------
Unknown commands are ignored rather than refused, and a file that ends without
``M02`` reads normally, following :mod:`emfit.kicad`'s rule that a format which
grows between tool releases should not break a parser.  What *is* refused is a
stroke with no usable aperture, because that would silently invent geometry.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "Aperture",
    "Segment",
    "Flash",
    "GerberLayer",
    "read_gerber",
]

#: Millimetres per file unit, keyed by the ``%MO`` argument.
_UNIT_MM = {"MM": 1.0, "IN": 25.4}

#: Aperture shapes this reader understands; anything else becomes ``"other"``.
_KNOWN_SHAPES = frozenset("CROP")

#: ``<letter><signed digits>`` -- the only word form an RS-274X command has.
_WORD_RE = re.compile(r"([A-Z])([+-]?\d+)")


@dataclass(frozen=True)
class Aperture:
    """One ``%ADD`` definition.

    Attributes
    ----------
    code
        The D-code the aperture is addressed by (``10`` for ``D10``).
    shape
        ``"C"`` (circle), ``"R"`` (rectangle), ``"O"`` (obround), ``"P"``
        (polygon), or ``"other"`` for a macro/unknown shape.
    params
        For a known shape, the ``X``-separated parameters as floats in
        millimetres -- ``(2.5,)`` for ``%ADD11C,2.5*%``.  For ``"other"`` the
        raw text, unconverted, so nothing is lost.
    """

    code: int
    shape: str
    params: tuple = ()

    @property
    def width(self) -> float | None:
        """Stroke width in mm for a circular aperture, else ``None``.

        A rectangle, obround or polygon "width" is not a scalar (and a macro's
        outline is not even known), so those return ``None`` rather than a
        number a caller could mistake for a stroke width.
        """
        return self.params[0] if self.shape == "C" and self.params else None


@dataclass(frozen=True)
class Segment:
    """A stroked line from ``(x0, y0)`` to ``(x1, y1)``, in millimetres."""

    x0: float
    y0: float
    x1: float
    y1: float
    width: float | None
    aperture: int

    def length(self) -> float:
        """Euclidean length of the stroke, in millimetres."""
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)


@dataclass(frozen=True)
class Flash:
    """A ``D03`` stamp of ``aperture`` at ``(x, y)``, in millimetres."""

    x: float
    y: float
    aperture: int


@dataclass
class GerberLayer:
    """The primitives of one Gerber layer.

    Attributes
    ----------
    path
        The file this layer was read from.
    units
        The unit the file declared, ``"mm"`` or ``"in"``; coordinates in this
        object are millimetres either way.
    int_digits, dec_digits
        The coordinate format from ``%FS``: ``(4, 6)`` for ``%FSLAX46Y46*%``.
    apertures
        ``code -> Aperture`` for every ``%ADD`` in the file.
    segments
        Stroked lines (``D01``), in file order.
    flashes
        Stamped pads (``D03``), in file order.
    regions
        One list of ``(x, y)`` vertices per ``G36``/``G37`` contour.
    polarity_switches
        How many ``%LPD``/``%LPC`` commands the file issued.
    arcs
        How many ``G02``/``G03`` strokes were counted (and *not* flattened).
    bbox
        ``(xmin, ymin, xmax, ymax)`` over segment endpoints, flash positions and
        region vertices, or ``None`` if the layer holds no geometry.
    """

    path: Path
    units: str
    int_digits: int
    dec_digits: int
    apertures: dict[int, Aperture] = field(default_factory=dict)
    segments: list[Segment] = field(default_factory=list)
    flashes: list[Flash] = field(default_factory=list)
    regions: list[list[tuple[float, float]]] = field(default_factory=list)
    polarity_switches: int = 0
    arcs: int = 0
    bbox: tuple[float, float, float, float] | None = None


def _statements(text: str):
    """Yield the file's statements with their terminators stripped.

    Extended commands come back framed as ``"%FSLAX46Y46*%"`` and plain commands
    as their text without the trailing ``*``.  An extended command may span
    lines -- a KiCad ``%AM`` macro body does -- so the scan looks for the next
    ``*%`` rather than the next newline.  An unterminated tail is ignored.
    """
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            return
        if text[i] == "%":
            end = text.find("*%", i + 1)
            if end < 0:
                return
            yield text[i : end + 2]
            i = end + 2
        else:
            end = text.find("*", i)
            if end < 0:
                return
            yield text[i:end]
            i = end + 1


def _scaled(digits: str, dec_digits: int, unit_mm: float) -> float:
    """Turn a file coordinate (an integer count of ``10**-dec_digits``) into mm."""
    return int(digits) / 10**dec_digits * unit_mm


def _aperture(code: int, body: str, unit_mm: float) -> Aperture:
    """Parse the text after the code in ``%ADD<code><shape>,<params>*%``."""
    shape, _, rest = body.partition(",")
    shape = shape.strip()
    if shape in _KNOWN_SHAPES:
        try:
            params = tuple(
                float(value) * unit_mm for value in rest.split("X") if value.strip()
            )
        except ValueError:
            return Aperture(code, "other", (body,))
        return Aperture(code, shape, params)
    return Aperture(code, "other", (body,))


def _bbox(layer: GerberLayer) -> tuple[float, float, float, float] | None:
    """Extent of the layer's centreline geometry, aperture not included."""
    xs: list[float] = []
    ys: list[float] = []
    for segment in layer.segments:
        xs += [segment.x0, segment.x1]
        ys += [segment.y0, segment.y1]
    for flash in layer.flashes:
        xs.append(flash.x)
        ys.append(flash.y)
    for contour in layer.regions:
        for vx, vy in contour:
            xs.append(vx)
            ys.append(vy)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def read_gerber(path: str | Path) -> GerberLayer:
    """Parse the RS-274X file at ``path`` into a :class:`GerberLayer`.

    Parameters
    ----------
    path
        A Gerber file.  KiCad's thin ``.gtl``/``.gbl`` extensions are ordinary
        RS-274X and read the same as ``.gbr``.

    Returns
    -------
    GerberLayer
        Apertures, stroked segments, flashes and regions; lengths in mm.

    Raises
    ------
    ValueError
        If a stroke arrives with no aperture selected, or with a code no
        ``%ADD`` ever defined -- the two cases in which geometry would otherwise
        have to be invented.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")

    layer = GerberLayer(path=path, units="mm", int_digits=0, dec_digits=0)

    unit_mm = 1.0
    x = y = 0.0
    aperture: int | None = None
    circular = True  # G01; G02/G03 clear it until the next G01
    in_region = False
    contour: list[tuple[float, float]] = []
    ended = False

    def resolve(x0: float, y0: float) -> tuple[int, float | None]:
        """The selected aperture's code and stroke width, or a clear refusal."""
        if aperture is None:
            raise ValueError(
                f"{path}: draw from ({x0}, {y0}) with no aperture selected"
            )
        definition = layer.apertures.get(aperture)
        if definition is None:
            raise ValueError(
                f"{path}: aperture D{aperture} is used but no %ADD defines it"
            )
        return aperture, definition.width

    for statement in _statements(text):
        if ended:
            break
        prev_x, prev_y = x, y  # where D01 starts from within this statement

        if statement.startswith("%"):
            body = statement[1:-2]
            if body.startswith("FS"):
                # %FSLAX46Y46*%: zero omission, absolute, then per-axis formats.
                if body[2:3] == "T":
                    raise ValueError(
                        f"{path}: trailing-zero-omitted coordinates are not supported"
                    )
                for axis, digits in _WORD_RE.findall(body):
                    if axis in "XY" and len(digits) >= 2:
                        layer.int_digits, layer.dec_digits = int(digits[0]), int(
                            digits[1]
                        )
            elif body.startswith("MO"):
                argument = body[2:].strip()
                if argument in _UNIT_MM:
                    unit_mm = _UNIT_MM[argument]
                    layer.units = "in" if argument == "IN" else "mm"
            elif body.startswith("AD"):
                match = re.match(r"ADD(\d+)(.*)$", body, re.DOTALL)
                if match:
                    code = int(match.group(1))
                    layer.apertures[code] = _aperture(code, match.group(2), unit_mm)
            elif body.startswith("LP"):
                layer.polarity_switches += 1
            # %AM macros, %TF/%TA/%TO/%TD attributes and anything else: skipped.
            continue

        if statement.startswith("G04"):  # comment
            continue

        for letter, digits in _WORD_RE.findall(statement):
            if letter == "G":
                code_g = int(digits)
                if code_g in (1, 2, 3):
                    circular = code_g == 1
                    if not circular:
                        layer.arcs += 1
                elif code_g == 36:
                    in_region, contour = True, []
                elif code_g == 37:
                    in_region = False
                    if contour:
                        layer.regions.append(contour)
                    contour = []
            elif letter == "X":
                x = _scaled(digits, layer.dec_digits, unit_mm)
            elif letter == "Y":
                y = _scaled(digits, layer.dec_digits, unit_mm)
            elif letter == "D":
                operation = int(digits)
                if operation == 1:
                    if in_region:
                        contour.append((x, y))
                    elif circular:
                        code_d, width = resolve(x, y)
                        layer.segments.append(
                            Segment(
                                prev_x, prev_y, x, y, width=width, aperture=code_d
                            )
                        )
                    else:
                        resolve(x, y)  # arc: counted, never flattened
                elif operation == 2:
                    if in_region:
                        if contour:  # a second contour inside the same region
                            layer.regions.append(contour)
                        contour = [(x, y)]
                elif operation == 3:
                    code_d, _ = resolve(x, y)
                    layer.flashes.append(Flash(x, y, code_d))
                else:
                    aperture = operation
            elif letter == "M" and int(digits) == 2:
                ended = True

    if contour:
        layer.regions.append(contour)
    layer.bbox = _bbox(layer)
    return layer
