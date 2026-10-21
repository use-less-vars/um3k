"""A microstrip coupon as a solver spec -- the one bridge from KiCad to a study.

Two unit conventions, on purpose
--------------------------------
:mod:`emfit.kicad` reports **millimetres**, verbatim from the file, and it will
keep doing so: a ``.kicad_pcb`` carries no unit declaration, so a reader that
rescaled its numbers would stop being a faithful reader of the text and start
being half a parser.  Everything downstream of this module is in **metres** --
the cell size of a :class:`emfit.grid.Grid`, the thickness of a
:class:`emfit.pml.PML`, the span between two probe stations -- because that is
what the field equations are written in, and a stray millimetre there is a
thousand-fold error that no range check would notice.

So the conversion happens **here, once**: :class:`MicrostripBoard` holds metres
and :meth:`MicrostripBoard.from_kicad` is the only place a millimetre is read.
This module imports :mod:`emfit.kicad` and nothing else from the package -- in
particular not :mod:`emfit.studies` -- so a spec can be built and validated with
no solver present.

The model, and what it leaves out
---------------------------------
One straight strip of uniform width on a single isotropic dielectric slab over a
full ground plane, driven at ``x_port`` and terminated by the far absorber at
``x_far``.  That is the geometry :func:`emfit.studies.microstrip_wave` computes,
and a spec is only ever a description of it.

Deliberately **not** represented, because the model above has no place to put
them: soldermask and any surface finish (a cover layer would be a second
dielectric on the top face, which the model terminates with an absorber
instead); more than one dielectric layer (``eps_r`` is one number, so a stack
with prepreg and core of different materials is collapsed to the first one
found, and a multilayer board with a plane in the middle is a different
problem); every other net (one named net defines the strip and nothing checks
that the copper around it is far enough away to be ignored); pads, vias, zone
pours, keepouts and silkscreen (they are placement and routing geometry, not a
cross-section); a non-rectangular outline (``length`` and ``width`` come from an
axis-aligned bounding box, so an L-shaped or rounded board is overstated);
copper thickness, surface roughness and conductor loss (the strip is an
infinitesimally thin PEC sheet); and bends (a corner radiates, which changes the
line, so a spec is one straight run and a curved one has to be cut into pieces
by the caller).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .kicad import Board, Track

__all__ = ["Load", "MM", "MicrostripBoard", "Port"]

#: One millimetre in metres -- the conversion this module exists to make.
MM = 1e-3

#: Relative tolerance for "this length is an integral number of cells".  Both
#: sides of the comparison were written down exactly in a file, so anything
#: beyond round-off is a real mismatch and not a tolerance question.
TOL = 1e-12

#: Relative tolerance for "this segment runs along x".  Looser than :data:`TOL`
#: because a track's coordinates are written as decimals and a line drawn by a
#: router need not land on the axis to the last bit; a track that is genuinely
#: diagonal misses it by orders of magnitude more.
AXIS_TOL = 1e-9


#: The load kinds :class:`Load` understands.  ``series_r`` breaks the strip and
#: puts a resistance in the break; ``shunt_c`` bridges the strip to the ground.
LOAD_KINDS = ("series_r", "shunt_c")


@dataclass(frozen=True)
class Load:
    """One lumped element sitting on the strip at ``position``.

    **Every length is in metres, and ``value`` is SI** -- ohms for
    ``series_r``, farads for ``shunt_c`` -- for the same reason
    :class:`MicrostripBoard` keeps metres: nothing downstream converts.

    A load is a circuit element and carries no geometry of its own.  It is
    placed by ``position``, measured along the line from the ``xmin`` edge like
    :attr:`MicrostripBoard.x_port`, and the mesh quantises that to the nearest
    node column, so two positions inside one cell are the same load.

    A ``series_r`` element genuinely interrupts the strip: the sheet is cut
    across its whole width and the resistance is the only path from one half to
    the other.  The capacitance of the cut itself (the fringing across the gap
    plus the substrate under it) is therefore *part of the model*, not an error
    term to be subtracted -- at the default ``0.4 mm`` cell it is a few hundred
    ohms of reactance at a few gigahertz, which is not small.  ``value`` of
    ``float("inf")`` gives a bare open cut.

    Attributes:
        position: Where the element sits along the line [m].
        kind: One of :data:`LOAD_KINDS`.
        value: Resistance [ohm] or capacitance [F], per ``kind``.
    """

    position: float
    kind: str
    value: float

    def __post_init__(self) -> None:
        if not self.position > 0.0:
            raise ValueError(
                f"position must be positive, got {self.position!r} "
                "(all lengths are metres)")
        if self.kind not in LOAD_KINDS:
            raise ValueError(
                f"kind must be one of {LOAD_KINDS}, got {self.kind!r}")
        if not self.value > 0.0:
            raise ValueError(
                f"value must be positive, got {self.value!r} "
                "(ohm for series_r, farad for shunt_c)")


@dataclass(frozen=True)
class Port:
    """The plane where an instrument would be connected to the strip.

    A port is a geometric plane, not a circuit element: the cross-section
    through the strip at which a probe or a connector launches the wave.  It is
    located on a pad, because that is the copper the instrument is soldered to,
    so its position is a fact read off the board rather than a number chosen to
    make the model come out.

    **``position`` is in metres and uses the same datum as
    :attr:`MicrostripBoard.x_port`** -- measured along the line from the
    ``xmin`` edge of the outline.

    ``y`` is recorded and deliberately not used.  It is here because a caller
    may want to check that the strip really does run under the pad the port
    claims to launch from, and that check needs the pad's coordinate across the
    line.  :class:`MicrostripBoard` models the strip centred on the outline
    whatever the copper does, though, so ``y`` is a fact about the launch and
    not a parameter of the line.

    Attributes:
        position: Where the port plane crosses the line, from the ``xmin`` edge
            [m].
        y: The pad's coordinate across the line [m]; recorded, not used.
        net: Name of the net the port launches onto.
        reference: Footprint reference of the pad, e.g. ``'J1'``.
        number: Pad number of the pad, e.g. ``'1'``.
        side: ``'front'`` or ``'back'`` -- the copper face the pad is on.
    """

    position: float
    y: float
    net: str
    reference: str
    number: str
    side: str

    def __post_init__(self) -> None:
        if not self.position > 0.0:
            raise ValueError(
                f"position must be positive, got {self.position!r} "
                "(all lengths are metres)")
        if not self.net:
            raise ValueError(
                "net must be a net name, got an empty string: a port launches "
                "onto a named net")
        if not self.reference:
            raise ValueError(
                "reference must be a footprint reference, got an empty string")
        if not self.number:
            raise ValueError(
                "number must be a pad number, got an empty string")
        if self.side not in ("front", "back"):
            raise ValueError(
                f"side must be 'front' or 'back', got {self.side!r}")


@dataclass(frozen=True)
class MicrostripBoard:
    """One microstrip coupon: a rectangular outline with a strip across it.

    **Every length is in metres.**  The KiCad reader keeps millimetres (see its
    docstring); this is the far side of the one conversion, so nothing that
    holds a :class:`MicrostripBoard` has to think about units again.

    The strip is centred on the outline: ``x`` runs along the line, from the
    port plane at ``x_port`` to the far plane at ``x_far``, and the strip of
    width ``w`` sits in the middle of ``width``, which is why
    :attr:`clearance` is a single number rather than two.

    Attributes:
        length: Outline along the line (``x``) [m].
        width: Outline across the line (``y``) [m].
        h: Substrate thickness [m].
        eps_r: Relative permittivity of the substrate.
        w: Strip width [m].
        x_port: Position of the port plane, measured from the ``xmin`` edge [m].
        x_far: Position where the strip ends [m].
        name: What the spec is called -- the net name when it came from a board.
        supplied: Names of the fields the **caller** supplied rather than the
            file.  A number that did not come from the board is recorded here
            instead of being indistinguishable from one that did.
        loads: Lumped elements on the strip, in the order they were written.
        port: The plane an instrument would be connected at, when the caller
            named a pad to launch from; ``None`` for a spec that carries no
            launch.
    """

    length: float
    width: float
    h: float
    eps_r: float
    w: float
    x_port: float
    x_far: float
    name: str = ""
    supplied: tuple[str, ...] = ()
    loads: tuple[Load, ...] = ()
    port: Port | None = None

    def __post_init__(self) -> None:
        for field_name in ("length", "width", "h", "eps_r", "w", "x_port", "x_far"):
            value = getattr(self, field_name)
            if not value > 0.0:
                raise ValueError(
                    f"{field_name} must be positive, got {value!r}"
                    + (" (all lengths are metres)" if field_name != "eps_r" else ""))

    # ------------------------------------------------------------------
    # derived views
    # ------------------------------------------------------------------
    @property
    def w_over_h(self) -> float:
        """Strip width over substrate thickness -- the shape of the cross-section."""
        return self.w / self.h

    @property
    def clearance(self) -> float:
        """Metal-free distance from each strip edge to the side of the outline [m].

        The strip is centred, so one number covers both sides; it is ``width/2 -
        w/2`` and it is what :meth:`to_cell_counts` turns into the clean cells
        once the lateral matched layer is taken out of it.
        """
        return 0.5 * (self.width - self.w)

    # ------------------------------------------------------------------
    # KiCad in
    # ------------------------------------------------------------------
    @classmethod
    def from_kicad(
        cls,
        board: Board,
        *,
        net: str,
        eps_r: float | None = None,
        taper: str = "raise",
        port_pad: tuple[str, str] | None = None,
    ) -> "MicrostripBoard":
        """Read a coupon out of a parsed board, from **one named net**.

        Where each number comes from:

        * ``h`` -- the stackup's total thickness if the file has a stackup, else
          the ``(general (thickness ...))`` declaration.  A board with neither
          raises: the substrate thickness decides the cell size of the whole
          mesh, so it is not a number to guess at.
        * ``eps_r`` -- the first core or prepreg entry of the stackup that
          carries one.  A board without a stackup (or whose stackup omits the
          permittivity) has to be given ``eps_r=`` explicitly, and the fact that
          the caller gave it is recorded in :attr:`supplied`.  There is no
          default, silent or otherwise: a wrong ``eps_r`` does not fail, it
          quietly moves ``eps_eff`` and ``Z0``.
        * ``w``, ``x_port``, ``x_far`` -- the axis-aligned segments of that
          net's tracks: the width, and the two extreme ``x`` coordinates of the
          run that carries it.  A net with no track at all raises, and so does
          one whose segments only run along ``y`` or diagonally.
        * ``length``, ``width`` -- the outline's axis-aligned bounding box.  A
          board with no ``Edge.Cuts`` geometry raises, because the lateral
          clearance (and hence the whole ``y`` extent of the mesh) is defined
          against that rectangle.

        A tapered line is not one uniform strip.  When the net's segments
        disagree about their width the default ``taper="raise"`` refuses to pick
        one and says which widths it found; ``taper="dominant"`` takes the width
        that covers the most track length and uses the extreme ``x`` of the
        segments that carry it.

        ``port_pad`` places the port on a pad instead of at the extreme ``x`` of
        the net.  The pad is looked up by the file's own identifiers (see
        :meth:`emfit.kicad.Board.pad_at`), so an absent or repeated pad number
        raises there rather than being guessed at here; after that the line has
        to start where the pad is, which changes both ``w`` and ``x_port``.  The
        width is read off the copper *at the port plane*, and ``x_far`` becomes
        the end of the run of that width which begins at the port.  On this
        repository's coupon that shortens the modelled line from 23.57 mm to
        2.5 mm: the line at the connector is 2.0 mm wide, the 3.0 mm run does not
        begin until 8.65 mm, and one uniform strip can only start where it is
        uniform.  Because the width comes from the port plane, ``taper`` has no
        effect on the width when ``port_pad`` is given -- it only has to be one
        of the two accepted modes.

        Args:
            board: A :class:`emfit.kicad.Board`; its lengths are millimetres.
            net: Name of the net that carries the strip.
            eps_r: Relative permittivity to use when the stackup does not carry
                one (or to override it).  ``None`` means "read it from the
                file", which raises if the file has nothing to read.
            taper: ``'raise'`` (the default) or ``'dominant'``.
            port_pad: ``(reference, number)`` of the pad an instrument would be
                connected to, or ``None`` -- the default -- to take the two
                extreme ``x`` of the net's own track as the port and far planes.

        Returns:
            A :class:`MicrostripBoard` in metres.

        Raises:
            ValueError: If ``taper`` is not one of the two modes, if the net is
                not declared, if it has no usable axis-aligned track, if the
                width is ambiguous under ``taper='raise'``, if the substrate
                thickness or the outline is missing, or if no permittivity is
                available and none was given.
        """
        if taper not in ("raise", "dominant"):
            raise ValueError(
                f"taper must be 'raise' or 'dominant', got {taper!r}")

        code = _net_code(board, net)
        tracks = [track for track in board.tracks if track.net == code]
        if not tracks:
            raise ValueError(
                f"net {net!r} carries no track segments, so there is no strip to "
                f"measure: the width and the two x planes of the line are read "
                f"off a track, and pads, zones and vias are not substitutes for one")

        along: list[Track] = []
        elsewhere = 0
        for track in tracks:
            dx = abs(track.end[0] - track.start[0])
            dy = abs(track.end[1] - track.start[1])
            if dx == 0.0 and dy == 0.0:
                continue                       # degenerate: no geometry in it
            if dy <= AXIS_TOL * dx:
                along.append(track)
            else:
                elsewhere += 1
        if not along:
            raise ValueError(
                f"net {net!r} has {elsewhere} segment(s) and none of them runs "
                f"along x: the reference line runs along x, so the strip width "
                f"and its port and far planes can only come from a segment that "
                f"does (the others are diagonal or run along y)")

        port: Port | None = None
        if port_pad is None:
            widths: dict[float, float] = {}
            for track in along:
                key = round(track.width, 9)
                widths[key] = widths.get(key, 0.0) + track.length()
            if len(widths) > 1 and taper == "raise":
                listing = ", ".join(
                    f"{width:g} mm over {run:.3f} mm"
                    for width, run in sorted(widths.items()))
                raise ValueError(
                    f"net {net!r} carries {len(widths)} distinct track widths "
                    f"({listing}): a line that tapers is not one uniform strip, and "
                    f"taking one of those widths unasked would be a guess. Pass "
                    f"taper='dominant' to use the width that covers the most length.")
            w_mm = max(widths, key=lambda width: widths[width])
            strip = [track for track in along if round(track.width, 9) == w_mm]
            x_port = min(min(track.start[0], track.end[0]) for track in strip) * MM
            x_far = max(max(track.start[0], track.end[0]) for track in strip) * MM
        else:
            reference, number = port_pad
            pad = board.pad_at(reference, number)
            if pad.net_name != net:
                raise ValueError(
                    f"pad {pad.reference}.{pad.number} is on net "
                    f"{pad.net_name!r}, not on {net!r}: a port launches onto the "
                    f"line the spec models, so the pad has to sit on that net")

            # The line has to begin where the instrument is attached, and the
            # width it has there is the width of the copper at that plane -- not
            # the widest run anywhere on the net.
            x_pad_mm = pad.position[0]
            at_plane = [track for track in tracks if _reaches(track, x_pad_mm)]
            if not at_plane:
                raise ValueError(
                    f"pad {pad.reference}.{pad.number} sits at x = "
                    f"{x_pad_mm:.6f} mm, where no segment of net {net!r} ends: a "
                    f"port is where the instrument meets the line, so the line "
                    f"has to begin at the port plane")
            widths_at_port: dict[float, float] = {}
            for track in at_plane:
                key = round(track.width, 9)
                widths_at_port[key] = widths_at_port.get(key, 0.0) + track.length()
            if len(widths_at_port) > 1:
                listing = ", ".join(
                    f"{width:g} mm over {span:.3f} mm"
                    for width, span in sorted(widths_at_port.items()))
                raise ValueError(
                    f"the segments of net {net!r} that meet the port pad at x = "
                    f"{x_pad_mm:.6f} mm disagree about their width ({listing}): a "
                    f"port is one plane across one uniform strip, so the line it "
                    f"launches onto has to have a single width there")
            w_mm = next(iter(widths_at_port))
            x_port = x_pad_mm * MM

            # Walk the run of that width starting at the port plane and stop
            # where it stops being that width: that is the far plane.
            same_width = [track for track in along
                          if round(track.width, 9) == w_mm]
            x_far_mm = x_pad_mm
            while True:
                following = [track for track in same_width
                             if abs(min(track.start[0], track.end[0]) - x_far_mm)
                             <= TOL * max(1.0, abs(x_far_mm))]
                if not following:
                    break
                if len(following) > 1:
                    raise ValueError(
                        f"net {net!r} branches at x = {x_far_mm:.6f} mm into "
                        f"{len(following)} segments of width {w_mm:g} mm: a branch "
                        f"is not a strip, so the line that starts at the port has "
                        f"no single far plane")
                x_far_mm = max(following[0].start[0], following[0].end[0])
            x_far = x_far_mm * MM
            if x_far <= x_port:
                behind_mm = min(
                    x_pad_mm,
                    *(min(track.start[0], track.end[0]) for track in at_plane))
                raise ValueError(
                    f"the port at {pad.reference}.{pad.number} sits at x = "
                    f"{x_pad_mm:.6f} mm, and the {w_mm:g} mm run of net {net!r} at "
                    f"that plane only extends back to {behind_mm:.6f} mm: this "
                    f"model runs the line from the port plane towards the far "
                    f"wall, so a port on the far end of a line cannot be placed "
                    f"without reversing the line")
            port = Port(
                position=x_port,
                y=pad.position[1] * MM,
                net=pad.net_name,
                reference=pad.reference,
                number=pad.number,
                side=pad.side,
            )

        stackup_h = board.stackup_thickness()
        if stackup_h is not None:
            h_mm = stackup_h
        elif board.thickness is not None:
            h_mm = float(board.thickness)
        else:
            raise ValueError(
                "the board declares neither a stackup nor a (general (thickness "
                "...)): the substrate thickness fixes the cell size of the whole "
                "mesh and cannot be guessed")

        supplied: list[str] = []
        dielectric = None
        for entry in board.stackup:
            if entry.kind in ("core", "prepreg") and entry.epsilon_r is not None:
                dielectric = entry
                break
        if eps_r is not None:
            eps = float(eps_r)
            supplied.append("eps_r")
        elif dielectric is not None:
            eps = float(dielectric.epsilon_r)
        else:
            raise ValueError(
                "no dielectric layer of the stackup declares an eps_r, so the "
                "substrate permittivity has to be given: pass eps_r=... "
                "explicitly. This reader has no default, because a wrong eps_r "
                "does not fail anywhere -- it just reports a different line")

        bbox = board.edge_bbox
        if bbox is None:
            raise ValueError(
                "the board draws no Edge.Cuts outline, so its length and width "
                "are undefined and there is nothing to measure the lateral "
                "clearance against")
        xmin, ymin, xmax, ymax = bbox

        return cls(
            length=(xmax - xmin) * MM,
            width=(ymax - ymin) * MM,
            h=h_mm * MM,
            eps_r=eps,
            w=w_mm * MM,
            x_port=x_port,
            x_far=x_far,
            name=net,
            supplied=tuple(supplied),
            port=port,
        )

    # ------------------------------------------------------------------
    # cropping the outline to the line
    # ------------------------------------------------------------------
    def cropped_to_strip(self) -> "MicrostripBoard":
        """This same line in a box that ends where the strip does.

        The crop sets ``length`` to ``x_far`` and changes nothing else -- the
        width, the substrate, the two ``x`` planes, the loads and the port are
        carried over untouched.  It is the **box** that moves, not the line: the
        geometry the study models is the strip, and the outline only ever
        supplied the lateral clearance and the far wall.

        ``'length'`` is appended to :attr:`supplied` (once), because the number
        now in that field is this method's and not the file's: the outline the
        board draws is longer than the spec.  A spec that already ends at
        ``x_far`` comes back unchanged, declaration included -- a caller
        comparing ``supplied`` against what it passed would otherwise be told it
        had given a number it never gave.

        **The trade is real.**  After the call, ``length`` is no longer the
        board's outline: the modelled geometry is the strip alone, so a caller
        that goes on to compare ``length`` with the ``Edge.Cuts`` bounding box is
        comparing a crop to a board, not taking two measurements of one thing.
        Nor does cropping make the numbers divide: it lands the far plane on the
        wall, which is what :meth:`to_cell_counts` asks for first, and that
        method still gets the final word -- a cropped spec whose strip width,
        clearance or port plane is not a whole number of cells refuses exactly as
        it did before.

        Returns:
            A :class:`MicrostripBoard` whose ``length`` is its ``x_far``.
        """
        if abs(self.x_far - self.length) <= TOL * self.length:
            return self
        supplied = (self.supplied if "length" in self.supplied
                    else self.supplied + ("length",))
        return replace(self, length=self.x_far, supplied=supplied)

    # ------------------------------------------------------------------
    # to the study's cell counts
    # ------------------------------------------------------------------
    def to_cell_counts(self, *, n_sub: int, n_pml: int) -> dict:
        """The integer cell counts :func:`emfit.studies.microstrip_wave` wants.

        The study's mesh is cubic: one cell size ``h / n_sub`` on all three axes,
        and every geometric feature has to land on a node layer of it.  The
        strip width, the clearance either side and the two ``x`` planes
        therefore have to be integral numbers of cells -- not "close", because a
        strip that is half a cell too wide is a different strip, and the study
        would silently round it.  This method does the dividing and refuses when
        the division does not come out.

        The far plane is checked separately and first: the study terminates the
        strip in the ``n_pml``-cell absorber on the far ``x`` wall, so ``x_far``
        has to *be* the wall.  A coupon whose strip stops short of the outline
        edge is not a shorter model, it is a model with a piece of line the
        study does not have.

        Args:
            n_sub: Substrate cells across ``h``; this fixes the cell size.
            n_pml: Matched-layer cells at each absorbing face, which is the
                thickness that has to be taken out of the clearance and out of
                the port plane before what is left can be counted in cells.

        Returns:
            ``{'n_strip', 'n_clean', 'n_ref', 'n_line', 'cell'}``, ready to pass
            to :func:`emfit.studies.microstrip_wave` (``cell`` in metres).

        Raises:
            ValueError: If ``n_sub`` or ``n_pml`` is below 1, if the strip does
                not reach the far wall, or if any dimension is not an integral
                number of cells -- in which case the message carries every
                offending dimension and the ``n_sub`` values that would fit.
        """
        n_sub, n_pml = int(n_sub), int(n_pml)
        if n_sub < 1 or n_pml < 1:
            raise ValueError(
                f"n_sub and n_pml must both be at least 1, got n_sub={n_sub} and "
                f"n_pml={n_pml}")
        if abs(self.x_far - self.length) > TOL * self.length:
            raise ValueError(
                f"the strip ends at x_far = {self.x_far * 1e3:.6f} mm but the "
                f"outline is {self.length * 1e3:.6f} mm long: the model terminates "
                f"the strip in the far absorber at the x wall, so a strip that "
                f"stops short of that boundary cannot be represented (and neither "
                f"can one that runs past it). Crop the outline to the strip, or "
                f"extend the net to the board edge.")

        cell = self.h / n_sub
        dims = (
            ("n_strip", self.w, 0, "the strip width"),
            ("n_clean", self.clearance, n_pml,
             "the clearance beside the strip, less the lateral absorber"),
            ("n_ref", self.x_port, n_pml,
             "the port plane, less the absorber behind it"),
            ("n_line", self.x_far - self.x_port, 0,
             "the port plane to the far plane"),
        )
        wanted = {name: run / cell - cut for name, run, cut, _ in dims}
        bad = [dim for dim in dims if not _integral(wanted[dim[0]])]
        if bad:
            rows = [
                f"  {name} = {run * 1e3:.6f} mm / {cell * 1e3:.6f} mm"
                + (f" - {cut}" if cut else "")
                + f" = {wanted[name]:.6f} cells  ({note})"
                for name, run, cut, note in bad]
            fits = [ns for ns in range(1, 33)
                    if all(_integral(run / (self.h / ns) - cut)
                           for _, run, cut, _ in dims)]
            advice = (f"n_sub = {', '.join(str(ns) for ns in fits)} would fit every "
                      f"dimension" if fits else
                      "no n_sub in 1..32 fits every dimension")
            raise ValueError(
                f"the mesh is cubic, so every dimension of the model has to be an "
                f"integral number of cells, and at cell = h / n_sub = "
                f"{self.h * 1e3:.6f} mm / {n_sub} = {cell * 1e3:.6f} mm these do "
                f"not fit:\n" + "\n".join(rows)
                + f"\n{advice}; otherwise the geometry or n_sub has to change.")

        return {
            "n_strip": int(round(wanted["n_strip"])),
            "n_clean": int(round(wanted["n_clean"])),
            "n_ref": int(round(wanted["n_ref"])),
            "n_line": int(round(wanted["n_line"])),
            "cell": cell,
        }


def _reaches(track: Track, x_mm: float) -> bool:
    """Whether ``track`` has an end at ``x_mm`` (millimetres, relative tolerance)."""
    low = min(track.start[0], track.end[0])
    high = max(track.start[0], track.end[0])
    tolerance = TOL * max(1.0, abs(x_mm))
    return abs(low - x_mm) <= tolerance or abs(high - x_mm) <= tolerance


def _net_code(board: Board, name: str) -> int:
    """The code of the net called ``name``, or a ``ValueError`` listing the nets."""
    codes = [net.code for net in board.nets if net.name == name]
    if not codes:
        known = ", ".join(
            sorted({net.name for net in board.nets if net.name})) or "none"
        raise ValueError(
            f"no net named {name!r} on this board; the named nets it declares are "
            f"{known}")
    return codes[0]


def _integral(value: float) -> bool:
    """Whether ``value`` is a whole number to round-off (relative)."""
    return abs(value - round(value)) <= TOL * max(1.0, abs(value))
