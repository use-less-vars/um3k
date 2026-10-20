"""Command line front end: ``python -m emfit <command>``.

The CLI owns no physics and no validation of its own -- it looks a study up in
:data:`emfit.studies.STUDIES`, hands the raw ``--set`` strings to
:func:`emfit.studies.coerce` (the single place where strings become values) and
prints what came back.  Two commands::

    python -m emfit list
    python -m emfit run <study> [--set KEY=VALUE ...] [--out DIR] [--json]
    python -m emfit serve [--host H] [--port N]

Exit codes, because scripts want to tell the cases apart:

* ``0`` -- the command ran;
* ``2`` -- the *request* was wrong: unknown study, unknown parameter, a value
  that does not parse or is out of range, a malformed ``--set``.  Nothing was
  computed; the message says what to fix;
* ``1`` -- the request was fine but the run blew up; the traceback goes to
  stderr so the failure is reproducible.

``--json`` prints exactly one JSON object (``study``, ``values``, ``metrics``,
``figures``) and nothing else on stdout, so it can be piped straight into
``json.load``.  Figures are only written when ``--out`` is given: a run with no
``--out`` still renders them (the studies always do) but leaves your disk alone.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback

from . import DEFAULT_PORT, __version__, studies

__all__ = ["build_parser", "main"]

EXIT_USAGE = 2
EXIT_RUNTIME = 1


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

    sink = studies.FigureSink()
    try:
        metrics = study.run(values, sink)
        paths = sink.save_to(args.out) if args.out else []
    except Exception:                         # noqa: BLE001 - report, do not hide
        traceback.print_exc()
        return EXIT_RUNTIME

    if args.json:
        print(json.dumps({"study": study.name, "values": values,
                          "metrics": metrics, "figures": paths}))
        return 0

    print(f"{study.name}: {study.title}")
    print("parameters: " + " ".join(f"{key}={value}" for key, value in values.items()))
    print()
    print(_table(metrics.items(), ("metric", "value")))
    print()
    if paths:
        print(f"figures ({len(paths)}):")
        for path in paths:
            print(f"  {path}")
    else:
        print("no files written (add --out DIR to save the figures)")
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
