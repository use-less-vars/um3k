"""The one piece of CLI state a user can collide with: the port it binds.

``python -m emfit serve`` is a local, single-user page, so its port is a default
and not a contract -- but a default that nothing checks drifts, and the failure it
drifts into is the one this file exists for: the front end refuses to start
because something else already holds the port.  These tests pin the value the
parser hands to ``_cmd_serve``, that ``--port`` and ``--host`` still override it,
and that :func:`emfit.webapp.make_server` / :func:`emfit.webapp.serve` take their
default from the same constant, so the banner cannot advertise a port the CLI
never asked for.

Nothing here binds a socket: the http-level tests in ``test_webapp.py`` are the
place for that, and they use ``port=0`` for exactly the reason above.

The other thing pinned here is ``run --json``'s file contract: the object names
the still ``figures`` and, separately, the ``attachments`` -- the ``rcs``
study's GIF animation -- because a script reads that key to find the pictures
and an animation in it is a picture that will not render.  One cheap rcs run
covers it.
"""

import inspect
import json
from pathlib import Path

import pytest

import emfit
from emfit import cli, webapp


def _parse(*extra):
    return cli.build_parser().parse_args(["serve", *extra])


def test_default_port_is_the_documented_one():
    assert emfit.DEFAULT_PORT == 8010
    assert _parse().port == emfit.DEFAULT_PORT


def test_default_port_is_not_the_contested_one():
    """8000 is where another local tool is usually already sitting."""
    assert emfit.DEFAULT_PORT != 8000
    assert _parse().port != 8000


def test_port_and_host_are_still_overridable():
    args = _parse("--port", "9123", "--host", "0.0.0.0")
    assert args.port == 9123
    assert args.host == "0.0.0.0"


def test_zero_is_accepted_so_the_os_can_pick():
    assert _parse("--port", "0").port == 0


def test_help_quotes_the_default(capsys):
    """A default the help text does not name is a default nobody can find.

    Read through ``serve --help`` rather than ``format_help()``: the top-level
    parser does not print its subparsers' options, so the cheap version of this
    test would pass while the one line a user actually reads said 8000.
    """
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["serve", "--help"])
    assert str(emfit.DEFAULT_PORT) in capsys.readouterr().out


@pytest.mark.parametrize("func", [webapp.make_server, webapp.serve])
def test_server_defaults_come_from_the_same_constant(func):
    assert inspect.signature(func).parameters["port"].default == emfit.DEFAULT_PORT


# ---------------------------------------------------------------------------
# the key a script reads: which file --json calls a figure
# ---------------------------------------------------------------------------
def _run_json(capsys, out_dir, *extra):
    """Run ``run <extra> --out <out_dir> --json`` and parse what it printed.

    Read back the way a script reads it -- one object on stdout, ``json.loads``,
    nothing else -- because that is the contract the key is part of.
    """
    code = cli.main(["run", *extra, "--out", str(out_dir), "--json"])
    assert code == 0
    return json.loads(capsys.readouterr().out)


def test_json_files_the_animation_under_attachments_not_figures(capsys, tmp_path):
    """The one study that writes a GIF: it is an attachment, not a figure.

    ``FigureSink.save_to`` returns every file it wrote in one flat list, so the
    CLI is the only place left that knows what kind each one is.  The rcs run
    writes ``rcs-pattern.png`` and ``rcs-animation.gif``, and the GIF used to
    arrive under ``figures``: a script that embeds that list put an animation
    where a still belongs, and one that counts figures counted two.

    The cheap end of the study is 8 cells per wavelength at ka = 0.5; the time
    domain is a tenth of a second there and the 24-frame GIF is most of the
    rest, so the run is a few seconds and this is not a ``slow`` test.
    """
    written = _run_json(capsys, tmp_path, "rcs", "--set", "ka=0.5",
                        "--set", "ppw=8")

    on_disk = sorted(path.name for path in tmp_path.iterdir())
    pngs = [name for name in on_disk if name.endswith(".png")]
    gifs = [name for name in on_disk if name.endswith(".gif")]
    assert pngs and gifs, f"the run wrote {on_disk}, so nothing below is tested"

    figures = {Path(path).name for path in written["figures"]}
    attachments = {Path(path).name for path in written["attachments"]}

    assert figures == set(pngs), written["figures"]
    assert set(gifs) <= attachments, written["attachments"]
    assert not set(gifs) & figures, written["figures"]
