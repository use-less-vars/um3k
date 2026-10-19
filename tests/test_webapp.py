"""HTTP-level tests for :mod:`emfit.webapp`.

These drive a *real* server -- :func:`emfit.webapp.make_server` on port 0, i.e.
an ephemeral port the OS picks, served from a daemon thread -- with plain
:mod:`urllib`.  Nothing is stubbed, so what is checked is the whole path a
browser would take: routing, form controls, ``coerce``/400 on a bad value, the
numerical study itself and the HTML that carries the PNG.

Each test states what it would catch, because a web-app test that only asserts
"200 OK" catches nothing: the interesting failures are a route that silently
becomes a 404, an exception that escapes as a 500 instead of a validation
error, and a results page that loses its figure.

Runtime: one real study run (``modes`` at defaults, ~1.1 s with the pinned
thread count) plus six page renders -- about 2 s for the whole file.
"""

from __future__ import annotations

import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from emfit import webapp


@pytest.fixture()
def base_url():
    """A server on an ephemeral port, in a thread, torn down afterwards.

    ``port=0`` keeps the tests clear of whatever else is listening on the
    machine; the bound port is read back from ``server_address`` rather than
    parsed from stdout.
    """
    httpd = webapp.make_server(port=0)
    # A short poll interval: the default 0.5 s would be paid again on every
    # shutdown(), which is half the runtime of this file.
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


def test_landing_lists_every_study(base_url):
    """``GET /`` is the entry point: it must name each registered study.

    Catches an empty or mis-wired landing page -- if ``STUDIES`` stops being
    iterated (or a study is added without a card) the browser front end has no
    way in at all, which no unit test of the studies would notice.
    """
    status, body = _request(base_url + "/")
    assert status == 200
    text = body.decode()
    for name in ("cavity", "modes", "duct"):
        assert name in text, f"landing page does not link {name}"
    assert 'href="/s/cavity"' in text


def test_study_form_renders_controls(base_url):
    """``GET /s/<name>`` shows one labelled, bounded control per parameter.

    Catches a form that renders but cannot be submitted: the number inputs must
    carry the declared ``min``/``max`` (which is the only guidance the user
    gets before a 400) and the page must contain the POST target and a submit
    button, otherwise "open the page and press Run" is broken while every
    server-side route still looks fine.
    """
    status, body = _request(base_url + "/s/cavity")
    assert status == 200
    text = body.decode()
    assert 'action="/run/cavity"' in text
    assert 'type="number"' in text
    assert 'type="submit"' in text
    # The bounds come from studies.Param; a cavity grid is capped at 14.
    assert 'max="14"' in text


def test_post_run_modes_returns_results_with_figure(base_url):
    """A real submission runs the study and returns metrics *and* the PNG.

    Catches the two failure modes a smoke test misses: a results page that
    renders the title but no metrics table (a ``study.run`` signature drift),
    and a figure pipeline that stops inlining the PNG -- the ``data:`` URI is
    what makes the page self-contained, so if it is gone the image is a broken
    link in a browser even though the HTTP response is still 200.
    """
    status, body = _request(
        base_url + "/run/modes",
        {"nx": "6", "ny": "5", "nz": "4", "nmodes": "2"},
    )
    assert status == 200
    text = body.decode()
    assert 'class="metrics"' in text
    assert "data:image/png;base64," in text
    # "Run again" must carry the submitted values back, not the defaults.
    assert 'value="6"' in text


def test_out_of_range_value_is_a_400_not_a_500(base_url):
    """A typo in a parameter is a validation error, not a crash.

    Catches the regression that matters most in a server: if ``coerce``'s
    ``ValueError`` escapes instead of being answered with 400, the user gets an
    opaque 500 (or a dropped connection) for something as ordinary as typing 99
    into a field whose maximum is 14 -- and the message has to name the bound,
    or the user has no idea what to fix.
    """
    status, body = _request(base_url + "/run/cavity", {"nx": "99"})
    assert status == 400, "an out-of-range value must not be a server error"
    text = body.decode()
    assert "maximum 14" in text
    assert "nx" in text


def test_healthz_is_plain_ok(base_url):
    """``GET /healthz`` answers ``ok`` -- the probe endpoint stays trivial.

    Catches a health route that starts rendering a full page (slow, and useless
    to a probe) or disappears into the 404 branch, which would make any uptime
    check report the tool as down while it is serving fine.
    """
    status, body = _request(base_url + "/healthz")
    assert status == 200
    assert body == b"ok"


def test_unknown_path_is_404(base_url):
    """Anything unrouted answers 404 with a readable page.

    Catches a catch-all that turns every typo into a 200 (which hides broken
    links) or an unhandled exception: the 404 body must still be HTML, since
    the browser shows it to a human.
    """
    status, body = _request(base_url + "/nope")
    assert status == 404
    assert b"<html" in body.lower()


def test_favicon_returns_no_content(base_url):
    """``/favicon.ico`` is an empty 204 so the request log stays clean.

    Catches the noisy case: without this route every page load logs a 404 for
    the icon, which trains the reader to ignore the log where real 404s show
    up.  A 200 with a body would mean someone shipped an icon we never meant to
    serve.
    """
    status, body = _request(base_url + "/favicon.ico")
    assert status == 204
    assert body == b""
