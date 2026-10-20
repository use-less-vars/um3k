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
"""

import inspect

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
