"""Command line front end: ``python -m emfit <command>``.

The CLI owns no physics and no validation of its own -- it looks a study up in
:data:`emfit.studies.STUDIES`, hands the raw ``--set`` strings to
:func:`emfit.studies.coerce` (the single place where strings become values) and
prints what came back.  Two commands::

    python -m emfit list
    python -m emfit run <study> [--set KEY=VALUE ...] [--out DIR] [--json]
    python -m emfit board <path> [--net NAME] [--eps-r EPS] [--json]
    python -m emfit serve [--host H] [--port N]

Exit codes, because scripts want to tell the cases apart:

* ``0`` -- the command ran;
* ``2`` -- the *request* was wrong: unknown study, unknown parameter, a value
  that does not parse or is out of range, a malformed ``--set``.  Nothing was
  computed; the message says what to fix;
* ``1`` -- the request was fine but the run blew up; the traceback goes to
  stderr so the failure is reproducible.

``--json`` prints exactly one JSON object (``study``, ``values``, ``metrics``,
``figures``, ``attachments``) and nothing else on stdout, so it can be piped
straight into ``json.load``.  ``figures`` holds the still PNG images and
``attachments`` everything a run wrote beside them -- the ``rcs`` study's GIF
animation -- because a file is a figure only when it is a ``.png``;
:meth:`emfit.studies.FigureSink.save_to` returns both in one flat list, so the
splitting happens here.  Files are only written when ``--out`` is given: a run
with no ``--out`` still renders them (the studies always do) but leaves your
disk alone.

A record deeper than :data:`SLOW_STEPS` steps prints one line on stderr saying
what runs like it have cost, before the study starts.  It is a warning and not
a refusal: the microstrip ceiling that used to make a 0.1 mm cell unaskable is
gone, so the price has to be stated instead of enforced, and it goes to stderr
because stdout is the JSON.

``board`` is the read-only command: it parses a ``.kicad_pcb`` file and prints
what a study could take from it -- the stackup, the outline, the nets that carry
tracks -- and, for one named net, the microstrip cross-section that net makes
and the mesh cell counts that cross-section fits.  Every length it reports is in
millimetres, the unit the file states; the metres of
:class:`emfit.board.MicrostripBoard` never reach the page unconverted.  A file
the reader cannot turn into a spec is not a failure: the stackup and the nets
are the report, the refusal is printed beside them, and the exit code stays
``0`` -- ``2`` is kept for a path that cannot be read at all.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback

from . import DEFAULT_PORT, __version__, studies
from .board import MicrostripBoard
from .kicad import load_board
from .microstrip import Microstrip

__all__ = ["build_parser", "main"]

EXIT_USAGE = 2
EXIT_RUNTIME = 1

#: Nets the ``board`` geometry table prints before it shows the longest instead.
BOARD_NET_ROWS = 12
#: Substrate cell counts the ``board --net`` representability report tries.
BOARD_N_SUBS = (2, 4, 6, 8)
#: Copper thickness the closed-form comparison assumes, in metres: 35 um.
BOARD_COPPER_T = 35e-6

#: ``nsteps`` above which ``run`` says on stderr what the record will cost.
#: This was the microstrip study's ceiling until a 0.1 mm cell needed 9600
#: steps and the cap had to go; it stays as the threshold because it is exactly
#: the depth the cap used to refuse, i.e. the runs nobody has been able to ask
#: for, and so nobody has any feel for what they cost.
SLOW_STEPS = 4000

#: What ``run`` prints above :data:`SLOW_STEPS`: the two measurements that
#: exist, and nothing extrapolated from them.  The 0.2 mm coupon and the 0.1 mm
#: port path are different meshes at different cell sizes, so a formula fitted
#: through the two would read as a promise the numbers do not support -- the
#: honest statement is the order of magnitude plus the anchors to measure
#: against.  One line, because it is a warning and not a page.
_SLOW_WARNING = (
    "warning: nsteps={nsteps} -- minutes to hours, not seconds. Measured: the "
    "0.2 mm coupon (124x87x44, pml 12) took 120.27 s at 4800 steps; the 0.1 mm "
    "port path (70x200x52, pml 12) about 288 s at 9600. No wall clock is "
    "predicted for this mesh.")


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------
def _one_line(text: str) -> str:
    """Collapse whitespace and keep the first sentence of a blurb.

    ``Study.blurb`` is written for documentation, where two or three sentences
    are fine; in the ``list`` table one sentence per study keeps the columns
    readable and every study on a single row.
    """
    flat = " ".join(str(text).split())
    head, sep, _ = flat.partition(". ")
    return f"{head}." if sep else flat


def _table(rows, header=None, indent: str = "  ") -> str:
    """Render ``(left, right)`` pairs as an aligned two-column block."""
    width = max([len(str(left)) for left, _ in rows]
                + ([len(str(header[0]))] if header else [0]))
    lines = [f"{indent}{str(header[0]):<{width}}  {header[1]}"] if header else []
    lines += [f"{indent}{str(left):<{width}}  {right}" for left, right in rows]
    return "\n".join(lines)


def _split_written(paths):
    """Split the files a run wrote into ``(figures, attachments)``.

    :meth:`emfit.studies.FigureSink.save_to` returns one flat list -- the PNG
    figures first, then the attachments under their own file names -- and says
    nothing about which is which, so the extension is what decides: a ``.png``
    is a figure and anything else (the ``rcs`` study's GIF) is an attachment.
    A GIF filed under ``figures`` would be a lie about the field a script reads
    to find the pictures.
    """
    figures = [path for path in paths if path.lower().endswith(".png")]
    attachments = [path for path in paths if not path.lower().endswith(".png")]
    return figures, attachments


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def _cmd_list(args) -> int:
    """``list``: every registered study, one row each."""
    rows = [(study.name, study.title, _one_line(study.blurb))
            for study in studies.STUDIES.values()]
    w_name = max(len(row[0]) for row in rows)
    w_title = max(len(row[1]) for row in rows)
    print(f"{'name':<{w_name}}  {'title':<{w_title}}  blurb")
    for name, title, blurb in rows:
        print(f"{name:<{w_name}}  {title:<{w_title}}  {blurb}")
    print()
    print("run one with: python -m emfit run <study> "
          "[--set KEY=VALUE ...] [--out DIR] [--json]")
    return 0


def _parse_sets(items) -> dict:
    """Turn ``['nx=6', 'nsteps=300']`` into ``{'nx': '6', ...}`` (last wins)."""
    submitted = {}
    for item in items:
        key, sep, value = str(item).partition("=")
        if not sep or not key.strip():
            raise ValueError(f"--set {item!r}: expected KEY=VALUE")
        submitted[key.strip()] = value
    return submitted


def _cmd_run(args) -> int:
    """``run``: coerce the parameters, run the study, report or dump JSON."""
    try:
        study = studies.get(args.study)
    except ValueError as exc:                 # unknown study
        print(exc, file=sys.stderr)
        return EXIT_USAGE

    try:
        values = studies.coerce(study, _parse_sets(args.set))
    except ValueError as exc:                 # bad key, bad value, out of range
        print(exc, file=sys.stderr)
        return EXIT_USAGE

    # The cap that used to refuse a deep record is gone, so the cost has to be
    # said out loud instead of refused: with the cap in place a run slower than
    # a couple of minutes could not be asked for at all, and now it can.  To
    # stderr, because stdout carries the single object ``--json`` promises; and
    # silent at or below the line, because that is the common case and a warning
    # there would be noise on every run.
    nsteps = values.get("nsteps")
    if isinstance(nsteps, int) and nsteps > SLOW_STEPS:
        print(_SLOW_WARNING.format(nsteps=nsteps), file=sys.stderr)

    sink = studies.FigureSink()
    try:
        metrics = study.run(values, sink)
        paths = sink.save_to(args.out) if args.out else []
    except Exception:                         # noqa: BLE001 - report, do not hide
        traceback.print_exc()
        return EXIT_RUNTIME

    figures, attachments = _split_written(paths)

    if args.json:
        print(json.dumps({"study": study.name, "values": values,
                          "metrics": metrics,
                          "figures": figures, "attachments": attachments}))
        return 0

    print(f"{study.name}: {study.title}")
    print("parameters: " + " ".join(f"{key}={value}" for key, value in values.items()))
    print()
    print(_table(metrics.items(), ("metric", "value")))
    print()
    if figures:
        print(f"figures ({len(figures)}):")
        for path in figures:
            print(f"  {path}")
    if attachments:
        print(f"attachments ({len(attachments)}):")
        for path in attachments:
            print(f"  {path}")
    if not paths:
        print("no files written (add --out DIR to save the figures)")
    return 0


# ---------------------------------------------------------------------------
# reading a board file: what it states, in millimetres
# ---------------------------------------------------------------------------
def _mm(value: float) -> str:
    """A length held in metres, as millimetres to three decimals."""
    return f"{value * 1e3:.3f} mm"


def _entry_rows(stackup) -> list:
    """One ``(layer, cross-section)`` pair per stackup entry.

    Three decimals on the thickness because that is the resolution a stackup is
    written to, and a dash -- not a zero -- for a field the file leaves out:
    "no loss tangent stated" and "loss tangent 0" are not the same board.
    """
    rows = []
    for entry in stackup:
        thickness = "-" if entry.thickness is None else f"{entry.thickness:.3f} mm"
        material = entry.material or "-"
        eps_r = "-" if entry.epsilon_r is None else f"{entry.epsilon_r:g}"
        tan_d = "-" if entry.loss_tangent is None else f"{entry.loss_tangent:g}"
        rows.append((entry.name,
                     f"{entry.kind:<10} {thickness:>10}  {material:<10}  "
                     f"{eps_r:>6}  {tan_d:>6}"))
    return rows


_ENTRY_HEADER = ("layer",
                 f"{'kind':<10} {'thickness':>10}  {'material':<10}  "
                 f"{'eps_r':>6}  {'tan_d':>6}")


def _widths_text(widths) -> str:
    """The distinct track widths of one net, or their span when there are many.

    A taper carries dozens of them and printing every value would bury the row,
    so above four the count and the range stand in: that is the honest summary
    of a line which is not uniform anyway.
    """
    if len(widths) <= 4:
        return "w " + ", ".join(f"{width:g}" for width in widths) + " mm"
    return f"w {len(widths)} widths {widths[0]:g}..{widths[-1]:g} mm"


def _net_geometry(board) -> list:
    """Per net that carries tracks: how many, how wide, on what, where, how long.

    Nets with no track are left out -- a row of zeroes says nothing about what a
    study can read -- and the rows come longest-first, which is the order the
    tail rule in :func:`_cmd_board` needs.
    """
    runs: dict = {}
    for track in board.tracks:
        runs.setdefault(track.net, []).append(track)
    nets = []
    for code, tracks in runs.items():
        xs = [float(x) for track in tracks for x in (track.start[0], track.end[0])]
        ys = [float(y) for track in tracks for y in (track.start[1], track.end[1])]
        nets.append({
            "name": board.net_name(code),
            "tracks": len(tracks),
            "widths_mm": sorted({round(float(track.width), 9) for track in tracks}),
            "layers": sorted({track.layer for track in tracks}),
            "x_extent_mm": [min(xs), max(xs)],
            "y_extent_mm": [min(ys), max(ys)],
            "length_mm": float(sum(track.length() for track in tracks)),
        })
    nets.sort(key=lambda net: -net["length_mm"])
    return nets


def _net_rows(nets) -> list:
    """``(name, numbers)`` pairs for :func:`_net_geometry`'s records."""
    rows = []
    for net in nets:
        xmin, xmax = net["x_extent_mm"]
        ymin, ymax = net["y_extent_mm"]
        rows.append((net["name"] or "(unnamed)",
                     f"{net['tracks']:>3} tracks  {_widths_text(net['widths_mm'])}  "
                     f"{','.join(net['layers']) or '-'}  "
                     f"x {xmin:.3f}..{xmax:.3f}  y {ymin:.3f}..{ymax:.3f} mm  "
                     f"len {net['length_mm']:.3f} mm"))
    return rows


def _port_pad(text: str) -> tuple:
    """``--port-pad REF.NUM``: the footprint reference and the pad number.

    ``argparse`` type function, so a malformed value is a usage error (exit 2)
    naming the form, rather than a report that quietly lost the port.
    """
    reference, dot, number = text.rpartition(".")
    if not dot or not reference or not number:
        raise argparse.ArgumentTypeError(
            f"{text!r} is not in REF.NUM form: give the footprint reference and "
            "the pad number separated by a dot, e.g. --port-pad J1.1 "
            "(pad 1 of footprint J1)")
    return reference, number


def _board_spec(board, net: str, eps_r, port_pad=None):
    """``(spec, refusal)``: the coupon as a spec, or why there is none.

    ``taper='dominant'`` is asked for deliberately.
    :meth:`emfit.board.MicrostripBoard.from_kicad` refuses to pick a width out of
    a tapering line unless it is told which rule to use, and a report that
    stopped there would show nothing for the commonest coupon there is;
    ``'dominant'`` takes the width covering the most track length, which is the
    strip and not the taper either side of it.  ``port_pad``, when given, is the
    ``(reference, number)`` of the pad to launch from; the taper rule then has
    no effect on where the port sits.
    """
    try:
        spec = MicrostripBoard.from_kicad(board, net=net, eps_r=eps_r,
                                          taper="dominant", port_pad=port_pad)
    except ValueError as exc:                 # no such net, no track, no stackup
        return None, str(exc)
    return spec, None


def _mesh_rows(spec, n_pml: int) -> list:
    """One ``{'n_sub', 'counts'|'error'}`` record per substrate cell count."""
    rows = []
    for n_sub in BOARD_N_SUBS:
        try:
            counts = spec.to_cell_counts(n_sub=n_sub, n_pml=n_pml)
        except ValueError as exc:              # the message names the dimension
            rows.append({"n_sub": n_sub, "error": str(exc)})
        else:
            rows.append({"n_sub": n_sub, "counts": {
                "n_strip": counts["n_strip"], "n_clean": counts["n_clean"],
                "n_ref": counts["n_ref"], "n_line": counts["n_line"],
                "cell_mm": float(counts["cell"]) * 1e3}})
    return rows


def _cmd_board(args) -> int:
    """``board``: read a ``.kicad_pcb`` file and report what a study could use.

    Read-only: nothing is meshed and nothing is solved.  The file is read with
    :func:`emfit.kicad.load_board`, so every length taken from it is in
    **millimetres**, the unit the file states.  :class:`MicrostripBoard` holds
    its fields in SI metres, so the ``--net`` block converts on the way out and
    prints ``mm`` on every line; ``--json`` keeps the same convention --
    ``thickness_mm``, ``outline_mm``, the stackup rows, ``x_extent_mm``,
    ``length_mm``, ``widths_mm`` and every length under ``spec`` are
    millimetres in the board's own coordinates (an extent is a place, not a
    size), ``eps_r`` and ``loss_tangent`` are dimensionless, and the one cell
    size in ``meshes`` is ``cell_mm``.

    A board the solver cannot represent is not an error: the stackup, the
    outline and the nets are the report, and a net
    :meth:`~emfit.board.MicrostripBoard.from_kicad` refuses is printed as
    ``no microstrip spec:`` with the exact message beside it, exit code ``0``.
    A wrong request is ``2``: a path that cannot be read -- no such file, or no
    ``(kicad_pcb ...)`` form in it -- or ``--port-pad`` without the ``--net``
    whose strip the port is placed on.
    """
    if args.port_pad is not None and not args.net:
        print("emfit board: error: --port-pad needs --net: the net is the strip "
              "the port is placed on", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)

    try:
        board = load_board(args.path)
    except (OSError, ValueError) as exc:       # no such file, not a board file
        print(f"cannot read {args.path}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    nets = _net_geometry(board)
    n_pml = int(studies.MS_N_PML)
    spec, refusal, meshes = None, None, []
    if args.net:
        spec, refusal = _board_spec(board, args.net, args.eps_r, args.port_pad)
        if spec is not None:
            meshes = _mesh_rows(spec, n_pml)

    if args.json:
        payload = {
            "file": args.path,
            "stackup": [{"name": entry.name, "kind": entry.kind,
                         "thickness_mm": entry.thickness,
                         "material": entry.material,
                         "eps_r": entry.epsilon_r,
                         "loss_tangent": entry.loss_tangent}
                        for entry in board.stackup],
            "thickness_mm": board.thickness,
            "copper_layers": len(board.copper_layers),
            "outline_mm": list(board.edge_bbox) if board.edge_bbox else None,
            "nets": nets,
        }
        if args.net:
            payload["spec"] = None if spec is None else {
                "h": spec.h * 1e3, "w": spec.w * 1e3, "eps_r": spec.eps_r,
                "length": spec.length * 1e3, "width": spec.width * 1e3,
                "x_port": spec.x_port * 1e3, "x_far": spec.x_far * 1e3,
                "clearance": spec.clearance * 1e3,
                "w_over_h": spec.w_over_h,
                "supplied": list(spec.supplied),
                "port": None if spec.port is None else {
                    "position_mm": spec.port.position * 1e3,
                    "y_mm": spec.port.y * 1e3,
                    "net": spec.port.net,
                    "reference": spec.port.reference,
                    "number": spec.port.number,
                    "side": spec.port.side,
                },
            }
            payload["meshes"] = meshes
        if refusal is not None:
            # stdout stays one object a script can load; why there is no spec is
            # a report line, and a report line goes to stderr here.
            print(f"no microstrip spec: {refusal}", file=sys.stderr)
        print(json.dumps(payload))
        return 0

    print(f"board: {args.path}")
    print()
    if board.stackup:
        print(f"stackup ({len(board.stackup)} entries):")
        print(_table(_entry_rows(board.stackup), _ENTRY_HEADER))
    else:
        print("stackup: none -- the file declares no (stackup ...) block, so "
              "the cross-section is not written down")
    print()

    bbox = board.edge_bbox
    rows = [
        ("thickness",
         f"{board.thickness:.3f} mm from (general (thickness ...))"
         if board.thickness is not None else
         "none -- the file declares no (general (thickness ...)) either"),
        ("copper layers",
         f"{len(board.copper_layers)}"
         + (f" ({', '.join(board.copper_layers)})" if board.copper_layers else
            " -- no copper layer is declared")),
        ("outline",
         f"({bbox[0]:.3f}, {bbox[1]:.3f}) - ({bbox[2]:.3f}, {bbox[3]:.3f}) mm"
         if bbox else "none -- the board draws no Edge.Cuts geometry"),
        ("board size",
         f"{bbox[2] - bbox[0]:.3f} x {bbox[3] - bbox[1]:.3f} mm"
         if bbox else "none -- there is no outline to measure"),
        ("nets", f"{len(board.nets)} declared, {len(nets)} carrying tracks"),
    ]
    print(_table(rows))
    print()

    if not nets:
        print("no net carries a track segment, so there is no track geometry "
              "to report")
    else:
        shown = nets[:BOARD_NET_ROWS]
        omitted = len(nets) - len(shown)
        print(f"nets with tracks ({len(nets)}"
              + (f", the {len(shown)} longest shown):" if omitted else "):"))
        print(_table(_net_rows(shown),
                     ("net", "tracks, widths, layers, extents, total length")))
        if omitted:
            print(f"  {omitted} net(s) with tracks omitted: the {len(shown)} "
                  f"with the greatest total track length are the ones printed")

    if args.net:
        print()
        if spec is None:
            print(f"no microstrip spec: {refusal}")
            return 0
        launch = ("taper='dominant'" if spec.port is None
                  else f"port on {spec.port.reference}.{spec.port.number}")
        print(f"microstrip spec (net {spec.name!r}, {launch}):")
        print(_table([
            ("h", _mm(spec.h)),
            ("w", _mm(spec.w)),
            ("eps_r", f"{spec.eps_r:g}"),
            ("length", _mm(spec.length)),
            ("width", _mm(spec.width)),
            ("x_port", _mm(spec.x_port)),
            ("x_far", _mm(spec.x_far)),
            ("lateral clearance", _mm(spec.clearance)),
            ("supplied", ", ".join(spec.supplied) or
             "nothing -- every value came out of the file"),
            ("w/h", f"{spec.w_over_h:.4f}"),
        ]))
        print()
        line = Microstrip(w=spec.w, h=spec.h, eps_r=spec.eps_r,
                          t=BOARD_COPPER_T)
        print(f"closed form (emfit.microstrip.Microstrip, 35 um copper, "
              f"t = {BOARD_COPPER_T * 1e3:.3f} mm): a reference, not a target")
        print(_table([("z0", f"{line.z0:.4f} ohm"),
                      ("eps_eff", f"{line.eps_eff:.4f}")]))
        print()
        print(f"representability at n_pml = {n_pml} "
              f"(emfit.studies.MS_N_PML), cell = h / n_sub:")
        for record in meshes:
            if "counts" not in record:
                print(f"  n_sub = {record['n_sub']}: refused --")
                for text in record["error"].splitlines():
                    print(f"    {text}")
                continue
            counts = record["counts"]
            print(f"  n_sub = {record['n_sub']}: n_strip {counts['n_strip']}, "
                  f"n_clean {counts['n_clean']}, n_ref {counts['n_ref']}, "
                  f"n_line {counts['n_line']} "
                  f"(cell {counts['cell_mm']:.6f} mm)")
    return 0


def _cmd_serve(args) -> int:
    """``serve``: run the browser front end until interrupted."""
    from .webapp import serve                  # imported only when needed

    try:
        serve(host=args.host, port=args.port)
    except OSError as exc:                     # port in use, no such interface
        print(f"cannot bind {args.host}:{args.port}: {exc}\n"
              f"the port may already be held, or the interface may not exist; "
              f"--port N moves it, --port 0 asks the OS for a free one",
              file=sys.stderr)
        return EXIT_RUNTIME
    return 0


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Assemble the argument parser (``--help`` / ``--version`` included)."""
    parser = argparse.ArgumentParser(
        prog="emfit",
        description="Finite-integration time-domain electromagnetics: run one "
                    "of the packaged studies from the command line.",
        epilog="Study parameters are validated by emfit.studies.coerce, so a "
               "bad - or out-of-range - value is reported and nothing runs.")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="command", required=True)

    p_list = sub.add_parser("list", help="show the available studies")
    p_list.set_defaults(func=_cmd_list)

    p_run = sub.add_parser("run", help="run one study and print its metrics")
    p_run.add_argument("study", metavar="study",
                       help="study name, as shown by 'list'")
    p_run.add_argument("--set", metavar="KEY=VALUE", action="append", default=[],
                       help="override one parameter; repeat for several")
    p_run.add_argument("--out", metavar="DIR", default=None,
                       help="directory for the PNG figures (default: write none)")
    p_run.add_argument("--json", action="store_true",
                       help="print one JSON object instead of the tables")
    p_run.set_defaults(func=_cmd_run)

    p_board = sub.add_parser(
        "board", help="read a .kicad_pcb file and report its stackup and nets")
    p_board.add_argument("path", metavar="PATH",
                         help="the .kicad_pcb file to read (read-only: nothing "
                              "is written and nothing is solved)")
    p_board.add_argument("--net", metavar="NAME", default=None,
                         help="net that carries the strip; adds the microstrip "
                              "cross-section it makes and the meshes it fits")
    p_board.add_argument("--eps-r", metavar="EPS", type=float, default=None,
                         help="substrate relative permittivity to use instead of "
                              "the stackup's (a board with no stackup needs one)")
    p_board.add_argument("--port-pad", metavar="REF.NUM", type=_port_pad,
                         default=None,
                         help="place the port on this pad -- footprint reference "
                              "and pad number, e.g. J1.1 -- instead of at the "
                              "extremes of the net's own track")
    p_board.add_argument("--json", action="store_true",
                         help="print one JSON object instead of the tables")
    p_board.set_defaults(func=_cmd_board)

    p_serve = sub.add_parser("serve", help="run the browser front end")
    p_serve.add_argument("--host", metavar="HOST", default="127.0.0.1",
                         help="interface to bind (default: 127.0.0.1; keep it "
                              "on loopback, the server has no authentication)")
    p_serve.add_argument("--port", metavar="PORT", type=int, default=DEFAULT_PORT,
                         help=f"port to bind (default: {DEFAULT_PORT}; 8000 is "
                              "left to whatever else is already on this "
                              "machine; 0 picks a free one)")
    p_serve.set_defaults(func=_cmd_serve)
    return parser


def main(argv=None) -> int:
    """Run the CLI and return the process exit code."""
    args = build_parser().parse_args(argv)
    return int(args.func(args))
