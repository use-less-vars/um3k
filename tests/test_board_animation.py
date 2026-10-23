"""Tests for the ``plane`` knob of the ``microstrip_board`` animation.

The plane a run cuts its phasor on used to be a hard-wired ``n_sub // 2``; it
is now a named choice (``mid`` / ``strip`` / ``air``) that travels from the
form, through ``coerce``, into the solver and back out into the title and the
caption of the attached GIF.  Five things can break on that path and no unit
test of the solver would see any of them, so each is pinned here:

* T1 -- the form offers the plane as a *named* choice and defaults to ``mid``.
  Catches a knob that is registered on the study but never rendered, and a
  default that drifts off ``mid`` in the form while staying ``mid`` on the CLI.
* T2 -- a submitted plane reaches ``study.run`` unchanged, a missing field
  falls back to the default, and an unknown name is a 400 rather than a 500
  traceback.  Catches a route that drops the field, or validation that lets a
  typo through to a ``KeyError`` in the solver.
* T3 -- the attachment follows the ``f0`` knob: two tones, two GIFs, two
  captions that name the frequency they were handed.  Catches a caption that
  quotes the default frequency instead of the run's own.
* T4 -- the three names map to the three mesh indices they promise, and any
  other name is refused with a message that names all three.  Catches an
  off-by-one between "halfway up the substrate" and the index the field is
  actually cut on, and a ``KeyError`` that would hide the legal values.
* T5 -- at the default plane every string is byte for byte the one earlier
  versions printed, and at any other plane the title names the plane and its
  index.  Catches a "Mid-plane" title on a picture of the air above the strip.

No network and no board file: the HTTP tests drive a real server on an
ephemeral port (``webapp.make_server(port=0)``) but talk only to themselves,
and the animation tests hand ``_run_microstrip_board_animated`` a fake board
wrapper that fills the slice dict instead of running the solver.  The real
solver's slice is exercised by ``tests/test_studies.py``; what is under test
here is everything the animation layer does on top of it, which is where the
plane and the strings live.  Runtime for the file: about 5 s, the two
8-frame GIFs included.
"""

from __future__ import annotations

import dataclasses
import threading
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pytest

from emfit import studies, webapp


@pytest.fixture()
def base_url():
    """A server on an ephemeral port, in a thread, torn down afterwards."""
    httpd = webapp.make_server(port=0)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    )
    thread.start()
    host, port = httpd.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _request(url: str, data: dict = None):
    """GET ``url``, or POST ``data``, and return ``(status, body_bytes)``.

    A 4xx/5xx is an expected outcome here, not an error: ``HTTPError`` carries
    the code and the body, so it is unwrapped instead of raised.
    """
    payload = None if data is None else urllib.parse.urlencode(data).encode()
    try:
        with urllib.request.urlopen(url, data=payload, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _fake_board(values, sink, *, midplane=None):
    """Stand-in for :func:`emfit.studies._run_microstrip_board`.

    The real wrapper runs the solver and leaves the slice in ``midplane``; the
    properties checked below are the ones the animation layer builds *from*
    that dict, so the dict is filled directly and the solver is not run.  The
    numbers are the fake's own -- 12 x 12 cells at 0.2 mm, plane ``k = 4`` at
    0.8 mm, and a bin frequency that follows the f0 the run asked for -- and
    every assertion that quotes one quotes the literal here, so no tolerance
    is involved.

    ``midplane`` is keyword-only on the real signature (``*, midplane=None``),
    hence the ``*`` here: a positional fake would only pass while the caller
    kept passing the dict by keyword, and would mask a signature drift.
    """
    if midplane is None:                    # a caller that wants no phasor
        return {"note": "no slice"}
    n = 12
    ramp = np.linspace(0.0, 1.0, n)
    # A phasor with a phase gradient, so the frames of the GIF actually differ
    # from one another the way a travelling wave's do.
    ez = np.outer(ramp, ramp) * np.exp(1j * np.pi * ramp)[None, :]
    ez[0, :] = ez[-1, :] = 0.0              # PEC border, as the real one has
    ez[:, 0] = ez[:, -1] = 0.0
    midplane.update({
        "ez": ez.astype(complex),
        "f": float(values.get("f0", 6.0)) * 1e9,
        "dx": 2.0e-4,
        "dy": 2.0e-4,
        "uniform_xy": True,
        "plane_index": 4,
        "plane_z": 8.0e-4,
        "plane": str(values.get("plane", studies.MS_ANIMATE_PLANE)),
        "nx": n,
        "ny": n,
        "nz": 24,
        "nsteps": 120,
    })
    return {"plane": values.get("plane", studies.MS_ANIMATE_PLANE)}


def test_the_form_offers_the_plane_as_a_named_choice(base_url):
    """``GET /s/microstrip_board`` renders the plane as a select of three names.

    Catches a knob that is registered on the study but never reaches the page,
    a default that is not ``mid``, and -- the reason it is a select and not a
    number field -- an index a user could type that no mesh is going to have.
    """
    status, body = _request(base_url + "/s/microstrip_board")
    text = body.decode("utf-8")
    assert status == 200
    assert '<select id="f-plane" name="plane">' in text
    # ``mid`` is the plane every earlier version cut on, so it is the one the
    # browser offers pre-selected.
    assert '<option value="mid" selected>mid</option>' in text
    for name in ("strip", "air"):
        assert f'<option value="{name}">{name}</option>' in text
    # The frequency the caption quotes is a number field on the same form, at
    # the study's 6 GHz default.
    assert ('<input type="number" id="f-f0" name="f0" value="6"'
            ' min="1.0" max="20.0" step="any" required>' in text)


def test_a_submitted_plane_reaches_the_study_unchanged(base_url, monkeypatch):
    """``POST /run/microstrip_board`` hands the choice to ``run`` as typed.

    Catches a route that loses the field between ``coerce`` and ``study.run``
    (the animation would then always be cut on ``mid`` whatever was asked for),
    a missing field that does not fall back to the default, and an unknown name
    that escapes as a 500 instead of the 400 every other bad choice gets.
    """
    study = studies.get("microstrip_board")
    seen = []

    def run(values, sink):
        seen.append(values["plane"])
        return {"plane": values["plane"]}

    monkeypatch.setitem(studies.STUDIES, study.name,
                        dataclasses.replace(study, run=run))

    status, _ = _request(base_url + "/run/microstrip_board", {"plane": "air"})
    assert status == 200
    assert seen == ["air"]

    # An untouched form field sends nothing; that is "use the default", and the
    # default is still mid.
    status, _ = _request(base_url + "/run/microstrip_board", {})
    assert status == 200
    assert seen == ["air", "mid"]

    # A name that is not one of the three is refused before the study runs.
    status, body = _request(base_url + "/run/microstrip_board",
                           {"plane": "top"})
    assert status == 400
    assert b"plane" in body
    assert seen == ["air", "mid"], "the bad run must not reach the study"


def test_the_attachment_follows_the_frequency_knob(monkeypatch):
    """Two different ``f0`` values give two different GIFs and two captions.

    Catches a caption or a title that quotes a constant instead of the run's
    own frequency -- the mistake that makes an animation look right while
    claiming the wrong tone -- and a GIF that is generated but not attached.
    ``n_frames`` is held at 8 (the form's floor) rather than the study's 36:
    the frame count is not this test's subject and 36 frames cost seconds.
    """
    monkeypatch.setattr(studies, "_run_microstrip_board", _fake_board)
    attachments = []
    for f0 in (6.0, 8.0):
        sink = studies.FigureSink()
        metrics = studies._run_microstrip_board_animated(
            {"animate": "yes", "f0": f0, "plane": "mid", "n_frames": 8}, sink)
        assert metrics["plane"] == "mid"        # metrics pass through untouched
        assert sink.attachments, "animate=yes must attach the animation"
        attachment, = sink.attachments          # exactly one, and it is a GIF
        attachments.append(attachment)

    six, eight = attachments
    for attachment in attachments:
        assert attachment["slug"] == "midplane-animation"
        assert attachment["filename"] == "midplane-ez-steady-state.gif"
        # GIF87a and GIF89a both start here; either is a Pillow-valid GIF.
        assert attachment["data"][:4] == b"GIF8"

    # The caption is the run's own claim about which tone it played: it has to
    # name the knob it was handed, formatted to the three decimals the study
    # prints.
    assert "f0 = 6.000 GHz" in six["caption"]
    assert "f0 = 8.000 GHz" in eight["caption"]
    assert "f0 = 8.000 GHz" not in six["caption"]
    # The title names the *plane* and not the tone, so it is the same for both
    # runs and the frequency has to be carried by the caption (and by the
    # pixels).  A title that started quoting a frequency would be the same bug
    # in the other direction, which is why it is pinned here.
    assert six["title"] == eight["title"]
    assert "GHz" not in six["title"]
    # Two tones must give two files: the difference enters through the pixels
    # (the fake's bin follows f0) as well as the embedded title text.
    assert six["data"] != eight["data"]


def test_the_plane_names_map_to_one_mesh_index():
    """``mid`` / ``strip`` / ``air`` are the three named z positions, and no more.

    Catches an off-by-one in the mapping (the kept field is the mean of layers
    ``k - 1`` and ``k``, so the index is a count of cells and not a length), an
    ``air`` plane that lands in the first air cell -- the one that belongs half
    to the strip's own node layer -- and a lookup failure that hides the three
    legal names from whoever typed the wrong one.
    """
    assert studies._slice_index("mid", n_sub=4, n_air=12, k_strip=4) == 2
    assert studies._slice_index("strip", n_sub=4, n_air=12, k_strip=4) == 4
    assert studies._slice_index("air", n_sub=4, n_air=12, k_strip=4) == 10
    # With a single air cell there is no "halfway up": the floor is the first
    # cell above the strip's node layer, never index 0 of the air block.
    assert studies._slice_index("air", n_sub=4, n_air=1, k_strip=4) == 5
    # The form's value is a name, not a symbol: whitespace and case are not a
    # fourth plane.
    assert studies._slice_index(" AIR ", n_sub=4, n_air=12, k_strip=4) == 10

    with pytest.raises(ValueError) as excinfo:
        studies._slice_index("top", n_sub=4, n_air=12, k_strip=4)
    message = str(excinfo.value)
    for name in ("mid", "strip", "air"):
        assert f"'{name}'" in message, "the refusal has to name the legal planes"


def test_the_default_plane_keeps_every_earlier_string(monkeypatch):
    """At ``mid`` the attachment title is the old string byte for byte.

    Catches a title that starts naming the plane on runs that asked for
    nothing -- every earlier report says ``Mid-plane Ez of the driven
    microstrip, one period at f0`` and a moved title breaks comparisons that
    have nothing to do with this knob -- and, in the other direction, a
    non-default plane that still claims to be the mid plane.
    """
    monkeypatch.setattr(studies, "_run_microstrip_board", _fake_board)
    assert studies.MS_ANIMATE_PLANE == "mid"
    assert studies.get("microstrip_board").defaults()["plane"] == "mid"

    sink = studies.FigureSink()
    # No "plane" key at all: the default path, as the CLI and an untouched form
    # both take it.
    studies._run_microstrip_board_animated(
        {"animate": "yes", "f0": 6.0, "n_frames": 8}, sink)
    default, = sink.attachments
    assert default["title"] == (
        "Mid-plane Ez of the driven microstrip, one period at f0")

    sink = studies.FigureSink()
    studies._run_microstrip_board_animated(
        {"animate": "yes", "f0": 6.0, "plane": "air", "n_frames": 8}, sink)
    moved, = sink.attachments
    # The fake puts the slice on k = 4, and the title has to quote the index
    # the run actually cut on, not the name alone.
    assert moved["title"] == (
        "Ez on the air plane (k = 4) of the driven microstrip, one period at f0")
    assert moved["title"] != default["title"]
    # Both files are the same GIF pipeline, so a title-only difference is the
    # plane in the picture, not a broken attachment.
    assert moved["data"][:4] == b"GIF8" and default["data"][:4] == b"GIF8"
