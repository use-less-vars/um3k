"""HTTP-level tests for the demo picker: ``GET /demo`` and the demo studies.

The seven real studies are reached from their cards; the two demos additionally
have a picker on the landing page.  A ``<select>`` cannot navigate on its own
without JavaScript, and :mod:`emfit.webapp` has none by design, so the picker is
an ordinary ``GET`` form that submits to ``/demo``, which answers ``303`` with a
``Location`` to the chosen study.  That indirection is exactly the kind of thing
a green smoke test hides: the landing page can render the ``<select>`` while
``/demo`` is a 404, and a browser only notices when someone presses the button.

Everything here drives a *real* server -- :func:`emfit.webapp.make_server` on
port 0, served from a daemon thread -- through :mod:`http.client` rather than
:mod:`urllib`.  ``urllib`` follows a ``303`` transparently and would hide both
the status code and the ``Location`` header, which is the whole subject of the
first two tests.

Runtime: the two demo runs are real (coarse mesh, 2 400 steps), about 3 s for
``demo_microstrip_line`` and 4.5 s for ``demo_microstrip_stub`` -- the stub runs
a loaded line *and* its load-free twin.  Those two submissions carry the
``slow`` marker, so ``-m 'not slow'`` keeps the page-rendering checks in the
fast part of the suite; the rest of the file is a few milliseconds of HTTP.
"""

from __future__ import annotations

import http.client
import threading
import urllib.parse

import pytest

from emfit import studies, webapp

DEMO_LINE = "demo_microstrip_line"
DEMO_STUB = "demo_microstrip_stub"


@pytest.fixture()
def server():
    """A server on an ephemeral port, in a daemon thread, torn down afterwards.

    ``port=0`` keeps the tests clear of whatever else is listening on the
    machine, and the bound port is read back from ``server_address`` rather than
    parsed from stdout.  The short poll interval is the same trick
    ``tests/test_webapp.py`` uses: the default 0.5 s would be paid again on
    every ``shutdown()``.
    """
    httpd = webapp.make_server(port=0)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    )
    thread.start()
    host, port = httpd.server_address[:2]
    try:
        yield host, port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _request(server, method: str, path: str, data: dict = None):
    """One request/response pair: ``(status, headers, body_bytes)``.

    No redirect following: a ``303`` comes back as a ``303``, so the test can
    check the status *and* the ``Location`` the browser would act on.
    """
    host, port = server
    payload = None if data is None else urllib.parse.urlencode(data).encode()
    headers = {}
    if payload is not None:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(payload)),
        }
    connection = http.client.HTTPConnection(host, port, timeout=120)
    try:
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def _no_script(body: bytes) -> None:
    """This front end is JavaScript-free on purpose; a page is not exempt."""
    assert b"<script" not in body, "a response carries a <script> block"


def test_landing_offers_a_javascript_free_demo_picker(server):
    """``GET /`` carries the picker above the cards, and one card per study.

    Catches the picker rendered without a submit control (a ``<select>`` that
    cannot be submitted), the option list drifting away from
    :data:`emfit.demos.DEMOS`, and a card going missing -- the count is taken
    from ``studies.STUDIES`` instead of a literal, so adding a study does not
    silently make this assertion meaningless while the 9 below pins the fact
    that the two demos did join the registry.
    """
    status, _headers, body = _request(server, "GET", "/")
    assert status == 200
    text = body.decode()
    assert "Load Demo" in text
    assert 'name="study"' in text
    assert 'action="/demo"' in text
    assert 'type="submit"' in text
    assert DEMO_LINE in text and DEMO_STUB in text
    assert len(studies.STUDIES) == 9, "the two demos did not join the registry"
    assert text.count('href="/s/') == len(studies.STUDIES), "a study has no card"
    assert text.count('class="card demo"') == 2, "the demo cards are not marked"
    _no_script(body)


def test_demo_route_redirects_to_the_chosen_study(server):
    """``GET /demo?study=<a demo>`` is a ``303`` to that study's page.

    Catches the two failures the browser shows as a blank page: the route
    missing (404) and a 200 rendering the study inline instead of redirecting,
    which would leave the address bar on ``/demo?study=...`` and break reload
    and bookmarking.
    """
    status, headers, body = _request(server, "GET", f"/demo?study={DEMO_LINE}")
    assert status == 303, f"expected a redirect, got {status}"
    assert headers.get("Location") == f"/s/{DEMO_LINE}"
    assert body == b"", "a 303 must not carry a body"
    assert headers.get("Cache-Control") == "no-store"


def test_demo_route_rejects_an_unknown_study_with_400(server):
    """A name that is not a study is a ``400``, never a ``500`` or a traceback.

    Catches the failure mode a hand-typed or stale URL produces: an exception
    escaping ``studies.get`` as a 500 page with a traceback, which reads as a
    server bug rather than as "pick a demo".
    """
    status, _headers, body = _request(server, "GET", "/demo?study=nope")
    assert status == 400, f"expected 400, got {status}"
    text = body.decode()
    assert "nope" in text, "the rejected name is not echoed back"
    assert "Traceback" not in text
    _no_script(body)


def test_demo_stub_form_offers_every_load_kind(server):
    """``GET /s/demo_microstrip_stub`` renders the ``load_kind`` choice control.

    Catches a choice parameter that renders as free text (which ``coerce`` then
    rejects) or a choices tuple that lost an option, so the third load the
    study supports becomes unreachable from the browser.
    """
    status, _headers, body = _request(server, "GET", f"/s/{DEMO_STUB}")
    assert status == 200
    text = body.decode()
    assert 'name="load_kind"' in text
    assert "<select" in text
    for choice in ("open", "series_r", "shunt_c"):
        assert f'value="{choice}"' in text, f"load_kind lost {choice}"
    _no_script(body)


@pytest.mark.slow
def test_post_run_demo_line_returns_metrics_and_a_png(server):
    """A real submission of the line demo returns an S11 row and an inline PNG.

    Catches the results page that loses its figure -- base64 dropped, wrong
    media type -- and a metric table whose keys stopped mentioning ``S11``,
    which is the one number this demonstration exists to show.
    """
    defaults = studies.get(DEMO_LINE).defaults()
    status, _headers, body = _request(server, "POST", f"/run/{DEMO_LINE}", defaults)
    assert status == 200, f"the demo run failed with {status}"
    text = body.decode()
    assert "data:image/png;base64," in text, "the results page lost its figure"
    assert "<th>|S11|</th>" in text, "no S11 metric row"
    assert "<th>|S21|</th>" in text, "no S21 metric row"
    _no_script(body)


@pytest.mark.slow
def test_post_run_demo_stub_open_returns_two_figures(server):
    """The stub demo at ``load_kind=open`` draws both of its figures.

    Catches a second figure that is computed but never added to the sink: the
    mid-plane heat map alone still looks like a successful run, so only the
    count of ``data:`` PNGs tells them apart.
    """
    values = dict(studies.get(DEMO_STUB).defaults())
    values["load_kind"] = "open"
    status, _headers, body = _request(server, "POST", f"/run/{DEMO_STUB}", values)
    assert status == 200, f"the demo run failed with {status}"
    text = body.decode()
    assert text.count("data:image/png;base64,") >= 2, "expected two figures"
    assert "<th>|S11|</th>" in text
    _no_script(body)


def test_healthz_still_answers_ok(server):
    """``GET /healthz`` is untouched by the picker: plain ``ok``, 2 bytes.

    Catches a route table edit that shadows the probe endpoint, which would make
    every health check fail while the human-facing pages still look fine.
    """
    status, _headers, body = _request(server, "GET", "/healthz")
    assert status == 200
    assert body == b"ok"
