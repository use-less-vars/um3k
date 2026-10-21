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

What ``run`` says on stderr before a deep run is pinned here as well.  ``nsteps``
was capped at 4000, which was the only thing between a user and an hours-long
field solve; the cap went because a 0.1 mm cell needs 9600, so the warning in
its place is what a user has left and it has a stream (not stdout) and a
threshold to get right.

The read side of ``board`` is pinned here too: the coupon's stackup and outline,
the microstrip spec ``from_kicad`` derives from them, a board that has neither a
stackup nor an outline (a report, not a failure), and the cell counts the coupon
cannot be cut into.  The boards are the fixtures -- a test that built one would
test the builder -- so each test asserts what the file states before what the
code derived from it: when a derived number moves, the assertions above it still
say whether the file changed or the derivation did.
"""

import dataclasses
import inspect
import json
import math
from pathlib import Path

import pytest

import emfit
from emfit import cli, studies, webapp

ROOT = Path(__file__).resolve().parent.parent
COUPON = ROOT / "kicad_support_project" / "kicad_support_project.kicad_pcb"
ROTATED = ROOT / "temp" / "rot" / "t.kicad_pcb"


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


# ---------------------------------------------------------------------------
# the bill: a deep record warns on stderr, a normal one stays silent
# ---------------------------------------------------------------------------
def test_a_deep_record_warns_on_stderr_and_a_normal_one_does_not(
        capsys, monkeypatch):
    """The price of a deep ``nsteps`` is said on stderr, and only then.

    ``nsteps`` was capped at 4000 until a 0.1 mm coupon cell needed 9600, so
    the cap that used to keep a user off an hours-long run is gone and this
    warning is what stands in its place.  Three things about it are contracts:
    it appears above 4000, it is silent at or below (the case almost every run
    hits, where a warning would be noise), and it is on stderr -- a warning on
    stdout would corrupt the single object ``--json`` promises to a script.

    The solve is stubbed, the way ``test_webapp.py`` stubs the same study: what
    is under test is the number in the line and the stream it goes to, and the
    real run this warns about is minutes long by definition.  The parameters,
    the coercion and the ceiling stay the real ones, so a cap that quietly came
    back would fail here rather than pass.
    """
    def run(values, sink):
        return {"leapfrog steps": str(values["nsteps"])}

    monkeypatch.setitem(studies.STUDIES, "microstrip",
                        dataclasses.replace(studies.MICROSTRIP, run=run))

    assert cli.main(["run", "microstrip", "--set", "nsteps=2400"]) == 0
    quiet = capsys.readouterr()
    assert "warning" not in quiet.err, quiet.err

    assert cli.main(["run", "microstrip", "--set", "nsteps=4800"]) == 0
    loud = capsys.readouterr()
    assert loud.err.startswith("warning: nsteps=4800"), loud.err
    # The two measurements the line is built from, still in it: the anchors are
    # all a reader has to go on, since no wall clock is predicted.
    assert "120.27 s" in loud.err and "288 s" in loud.err, loud.err
    assert "warning" not in loud.out, loud.out


def test_microstrip_board_reaches_the_cli_through_set(capsys, monkeypatch):
    """The board study is runnable from the CLI with its three text knobs.

    A text knob is the piece of ``--set`` the catalogue did not exercise before:
    a path has a ``/`` in it, a net name has no number in it, and a pad has a
    dot, so none of the three is the numeric or boolean parse every other study
    goes through.  They have to arrive at the study unchanged and come back in
    ``values``, because ``--json`` is what a script reads to record what it ran.

    The solve is stubbed: the coupon file is opened by the real study and the
    real ``coerce`` still types every value, so a text knob that stopped being
    free text would fail here rather than pass.
    """
    def run(values, sink):
        return {"board": values["board"], "net": values["net"],
                "port_pad": values["port_pad"]}

    monkeypatch.setitem(studies.STUDIES, "microstrip_board",
                        dataclasses.replace(studies.MICROSTRIP_BOARD, run=run))

    code = cli.main(["run", "microstrip_board",
                     "--set", f"board={COUPON}",
                     "--set", "net=RF_IN",
                     "--set", "port_pad=J1.1",
                     "--json"])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["values"]["board"] == str(COUPON)
    assert printed["values"]["net"] == "RF_IN"
    assert printed["values"]["port_pad"] == "J1.1"
    assert printed["metrics"] == {"board": str(COUPON), "net": "RF_IN",
                                 "port_pad": "J1.1"}


# ---------------------------------------------------------------------------
# board: what the file states, and then what was derived from it
# ---------------------------------------------------------------------------
def _board_json(capsys, *extra):
    """Run ``board <extra> --json`` and parse the one object it printed."""
    code = cli.main(["board", *[str(item) for item in extra], "--json"])
    assert code == 0
    return json.loads(capsys.readouterr().out)


def test_board_json_reads_the_coupon_then_derives_the_spec(capsys):
    """The coupon, in the order the command works: file first, spec second.

    ``--json`` is asked for because the object is the contract a script reads;
    the numbers below are the same ones the human report prints, and the order
    they are asserted in is the point.  A moved outline is a changed board; a
    moved ``x_far`` with the outline where it was is a changed derivation.
    """
    report = _board_json(capsys, COUPON, "--net", "RF_IN")
    entries = {entry["name"]: entry for entry in report["stackup"]}

    # what the file states
    assert report["outline_mm"] == pytest.approx([0.0, 0.0, 70.0, 20.0], abs=1e-9)
    assert entries["F.Cu"]["kind"] == "copper"
    assert entries["F.Cu"]["thickness_mm"] == pytest.approx(0.035, abs=1e-9)
    assert entries["dielectric 1"]["thickness_mm"] == pytest.approx(1.51, abs=1e-9)
    assert entries["dielectric 1"]["eps_r"] == pytest.approx(4.4, abs=1e-9)
    assert report["thickness_mm"] == pytest.approx(1.6, abs=1e-9)
    assert report["copper_layers"] == 2

    # and what from_kicad derived from it
    spec = report["spec"]
    assert spec["w"] == pytest.approx(3.0, abs=1e-9)
    assert spec["h"] == pytest.approx(1.6, abs=1e-9)
    assert spec["x_port"] == pytest.approx(8.65, abs=1e-9)
    assert spec["x_far"] == pytest.approx(32.22, abs=1e-9)
    assert spec["supplied"] == []


def test_board_json_has_a_port_key_and_it_is_null(capsys):
    """``spec.port`` is a key on every spec, and here it is null.

    ``from_kicad`` takes the port from its ``port_pad`` argument, and this run
    passes no ``--port-pad``, so nothing on this run names a pad and the port
    cannot be anything but ``None``.  The key is still there: an object
    that grows a key only once some later command learns to fill it in makes the
    absent port and the unknown port look the same to a script, and they are
    not the same answer.
    """
    report = _board_json(capsys, COUPON, "--net", "RF_IN")
    spec = report["spec"]
    assert "port" in spec
    assert spec["port"] is None


def test_board_json_fills_the_port_key_when_a_pad_is_named(capsys):
    """``--port-pad`` makes ``spec.port`` an object, and says which pad it is.

    The null case above is only half the key's contract.  ``J1.1`` is the pad the
    coupon's ``RF_IN`` track leaves from, so the port is at the extreme the taper
    rule would have picked anyway; the point is that it is now a stated pad and
    not a rule, and that the object carries the reference and number back.
    """
    report = _board_json(capsys, COUPON, "--net", "RF_IN",
                         "--port-pad", "J1.1")
    spec = report["spec"]
    port = spec["port"]
    assert isinstance(port, dict)
    assert port["reference"] == "J1"
    assert port["number"] == "1"
    assert port["net"] == "RF_IN"
    assert math.isfinite(port["position_mm"])
    assert math.isfinite(port["y_mm"])
    assert port["position_mm"] == pytest.approx(spec["x_port"], abs=1e-9)
    assert port["position_mm"] == pytest.approx(8.65, abs=1e-6)
    # The flag is what fills the key in: without it the same run is null again.
    assert _board_json(capsys, COUPON, "--net", "RF_IN")["spec"]["port"] is None


def test_board_refuses_a_port_pad_with_no_net(capsys):
    """``--port-pad`` without ``--net`` is a usage error, not a skipped flag.

    The pad is where the strip starts and the strip is the net, so naming the
    pad and not the net is half a request; printing the board report with no
    spec would be the flag silently dropped.
    """
    with pytest.raises(SystemExit) as raised:
        cli.main(["board", str(COUPON), "--port-pad", "J1.1"])
    assert raised.value.code == 2
    assert "--net" in capsys.readouterr().err


def test_board_reads_a_board_with_no_stackup_and_no_outline(capsys):
    """A thin board file is a report, not a failure: exit 0 and say what is not there.

    ``temp/rot/t.kicad_pcb`` declares no ``(stackup ...)`` block, draws no
    ``Edge.Cuts`` and carries no track, so three of the report's rows have
    nothing to measure.  The command's job is to say which -- and to keep its
    exit code for the one thing that really is a wrong request, a path it cannot
    read at all.
    """
    report = _board_json(capsys, ROTATED)
    assert report["stackup"] == []
    assert report["outline_mm"] is None
    assert report["thickness_mm"] == pytest.approx(1.6, abs=1e-9)
    assert report["nets"] == []

    code = cli.main(["board", str(ROTATED)])
    out = capsys.readouterr().out
    assert code == 0
    assert "stackup: none" in out
    assert "no Edge.Cuts" in out
    assert "no net carries a track" in out


def test_board_says_which_meshes_the_coupon_cannot_be(capsys):
    """The representability block, on a board no substrate cell count can hold.

    ``RF_IN`` is a 29.8 mm feed line on a 70 mm outline, so the strip stops well
    short of the far wall; every ``n_sub`` the command tries is refused for that
    one reason, and the refusal -- not a count -- is what a reader needs.  The
    closed-form line is printed above it and is labelled a reference: this is the
    number to compare a solve against, not the number the solve is fitted to.
    """
    report = _board_json(capsys, COUPON, "--net", "RF_IN")
    meshes = report["meshes"]
    assert [row["n_sub"] for row in meshes] == [2, 4, 6, 8]
    refusals = [row["error"] for row in meshes if "error" in row]
    assert refusals, meshes
    assert all("far absorber at the x wall" in message for message in refusals)
    assert not [row for row in meshes if "counts" in row], meshes

    code = cli.main(["board", str(COUPON), "--net", "RF_IN"])
    out = capsys.readouterr().out
    assert code == 0
    assert "no microstrip spec" not in out
    assert out.count("refused --") == len(refusals)
    assert "far absorber at the x wall" in out
    assert "35 um copper" in out
    assert "a reference, not a target" in out
