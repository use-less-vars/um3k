"""Browser front end for the studies in :mod:`emfit.studies`.

Run it with ``python -m emfit serve`` and open the URL it prints.  The server is
deliberately tiny: :mod:`http.server` from the standard library, one request at
a time (a module lock serialises studies), every page rendered as a single
self-contained HTML document: the study's PNG figures *and* any animated
attachment it produced (today the 24-frame ``rcs-animation.gif``) are inlined as
``data:`` URIs -- so there is no static-file route, no temp directory and
nothing to leak between runs.

**This is a local, single-user tool.**  It has no authentication, no CSRF
protection, no sandboxing and no resource limits: a submitted parameter set
ends up as the arguments of a numerical study that runs Python in the server
process.  Keep it on the loopback interface; do not expose it to a network you
do not control.

Routes
------
``GET  /``            landing page: every study as a card
``GET  /s/<name>``    the study's form (prefilled from the query string)
``GET  /demo``        303 to ``/s/<name>``: the demo picker (``?study=<name>``)
``POST /run/<name>``  validate with :func:`emfit.studies.coerce`, run, show results
``GET  /run/<name>``  the same, with the parameters in the query string
``GET  /healthz``     ``ok``, for probes
``GET  /favicon.ico`` empty 204, so a browser does not log a 404
anything else         404

The form controls come straight from :class:`emfit.studies.Param`: ``int`` and
``float`` become ``<input type=number>`` with the declared bounds, ``choice`` a
``<select>``, ``bool`` a checkbox backed by a hidden ``false`` field (so an
unchecked box posts an explicit ``false`` rather than "absent", which
:func:`coerce` would read as "use the default").
"""

from __future__ import annotations

import base64
import html
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import DEFAULT_PORT, __version__, studies
from .demos import DEMOS as _DEMOS

__all__ = ["make_server", "serve", "Handler"]

MAX_BODY = 64 * 1024
"""Largest accepted ``POST`` body; the form is a handful of short fields."""

_LOCK = threading.Lock()
"""Serialises study runs: the solvers are CPU-bound and share matplotlib."""

STYLE = """
:root { --ink:#1b1f24; --muted:#5b6672; --line:#dfe3e8; --accent:#0b6bcb;
        --wash:#f6f8fa; }
* { box-sizing:border-box; }
html { -webkit-text-size-adjust:100%; }
body { margin:0; background:#fff; color:var(--ink);
       font:16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
            "Helvetica Neue", Arial, sans-serif; }
main { max-width:60rem; margin:0 auto; padding:3rem 1.5rem 5rem; }
h1 { font-size:1.7rem; line-height:1.25; margin:0 0 .4rem; letter-spacing:-.01em; }
h2 { font-size:1.05rem; margin:2rem 0 .5rem; letter-spacing:-.005em; }
p { margin:.5rem 0; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.lede { color:var(--muted); max-width:44rem; font-size:1.02rem; }
.crumb { font-size:.9rem; margin:0 0 1.6rem; }
.cards { display:grid; gap:1rem; margin-top:2rem; }
.card { display:block; padding:1.25rem 1.4rem; border:1px solid var(--line);
        border-radius:.6rem; color:inherit; background:#fff;
        transition:border-color .12s ease, background .12s ease; }
.card:hover { border-color:var(--accent); background:var(--wash);
              text-decoration:none; }
.card h2 { margin:0 0 .35rem; font-size:1.12rem; color:var(--accent); }
.card p { margin:0; color:var(--muted); font-size:.95rem; }
.card .go { display:inline-block; margin-top:.7rem; font-size:.9rem;
            color:var(--accent); }
.card.demo { border-left:3px solid var(--accent); }
.tag { display:inline-block; margin:.7rem .6rem 0 0; padding:.05rem .5rem;
       font-size:.72rem; font-weight:600; letter-spacing:.06em;
       text-transform:uppercase; color:var(--accent); background:var(--wash);
       border:1px solid var(--line); border-radius:999px; }
form { border-top:1px solid var(--line); padding-top:1.4rem; margin-top:2rem; }
.field { display:grid; grid-template-columns:15rem 1fr; gap:.35rem 1.25rem;
         align-items:baseline; padding:.7rem 0; }
.field > label { font-weight:600; font-size:.95rem; }
.field .unit { color:var(--muted); font-weight:400; }
.field .help { grid-column:2; color:var(--muted); font-size:.86rem;
               margin:.15rem 0 0; }
input[type=number], input[type=text], select {
    width:100%; max-width:14rem; padding:.45rem .55rem; font:inherit;
    font-size:.95rem; color:inherit; background:#fff;
    border:1px solid var(--line); border-radius:.4rem; }
input[type=number]:focus, select:focus {
    outline:2px solid color-mix(in srgb, var(--accent) 35%, white);
    border-color:var(--accent); }
input[type=checkbox] { width:1.05rem; height:1.05rem; accent-color:var(--accent); }
button { margin-top:1.6rem; padding:.6rem 1.4rem; font:inherit; font-weight:600;
         color:#fff; background:var(--accent); border:0; border-radius:.45rem;
         cursor:pointer; }
button:hover { background:#0959a9; }
input[type=submit] { padding:.45rem .9rem; font:inherit; font-size:.9rem;
                     font-weight:600; color:#fff; background:var(--accent);
                     border:0; border-radius:.4rem; cursor:pointer; }
input[type=submit]:hover { background:#0959a9; }
table.metrics { border-collapse:collapse; margin-top:1rem; font-size:.94rem; }
table.metrics th, table.metrics td { text-align:left; padding:.35rem .9rem .35rem 0;
                                     vertical-align:top; }
table.metrics th { font-weight:600; color:var(--muted); white-space:nowrap;
                   padding-right:1.6rem; }
table.metrics tr + tr th, table.metrics tr + tr td {
    border-top:1px solid var(--line); }
figure { margin:2rem 0 0; padding-top:1.4rem; border-top:1px solid var(--line); }
figure img { max-width:100%; height:auto; display:block; margin:.6rem 0;
             border:1px solid var(--line); border-radius:.4rem; }
figcaption { color:var(--muted); font-size:.9rem; max-width:46rem; }
.hint { color:var(--muted); font-style:italic; }
.error { border:1px solid #d9534f; border-left-width:6px; background:#fdf3f3;
         border-radius:.4rem; padding:.9rem 1.1rem; margin:1.5rem 0; }
.error strong { color:#a12622; }
pre { overflow-x:auto; background:var(--wash); border:1px solid var(--line);
      border-radius:.4rem; padding:1rem; font-size:.82rem; line-height:1.45; }
footer { margin-top:3.5rem; padding-top:1.2rem; border-top:1px solid var(--line);
         color:var(--muted); font-size:.85rem; }
"""


# ---------------------------------------------------------------------------
# rendering helpers
# ---------------------------------------------------------------------------
def _esc(value) -> str:
    """Escape for HTML text and attribute values."""
    return html.escape(str(value), quote=True)


def _page(title: str, body: str) -> bytes:
    """Wrap ``body`` in the one-and-only document shell."""
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{_esc(title)}</title><style>{STYLE}</style></head><body><main>"
        f"{body}"
        f"<footer>emfit {_esc(__version__)} &middot; local single-user server, "
        "no authentication &middot; run with <code>python -m emfit serve</code>"
        "</footer></main></body></html>\n"
    ).encode("utf-8")


def _fmt_value(param, value) -> str:
    """Format a value for an ``<input value=...>`` attribute."""
    if param.kind == "float":
        try:
            return f"{float(value):g}"
        except (TypeError, ValueError):
            return _esc(value)
    return _esc(value)


def _control(form_key: str, param, value) -> str:
    """One form control, chosen from :attr:`Param.kind`."""
    ident = _esc(form_key + param.key)
    name = _esc(param.key)
    if param.kind == "choice":
        options = "".join(
            f"<option value=\"{_esc(choice)}\""
            f"{' selected' if str(choice) == str(value) else ''}>"
            f"{_esc(choice)}</option>"
            for choice in param.choices)
        return f"<select id=\"{ident}\" name=\"{name}\">{options}</select>"
    if param.kind == "bool":
        checked = " checked" if bool(value) else ""
        return (f"<input type=\"hidden\" name=\"{name}\" value=\"false\">"
                f"<input type=\"checkbox\" id=\"{ident}\" name=\"{name}\" "
                f"value=\"true\"{checked}>")
    if param.kind == "str":
        # A text field, and deliberately not ``required``: an empty string is a
        # legal value for a ``str`` parameter here (port_pad empty means "no
        # pad named"), and the study that needs one raises its own message
        # naming the flag rather than the browser refusing the submit.
        must = " required" if str(param.default) else ""
        return (f"<input type=\"text\" id=\"{ident}\" name=\"{name}\" "
                f"value=\"{_fmt_value(param, value)}\"{must}>")
    bounds = ""
    if param.lo is not None:
        bounds += f" min=\"{_esc(param.lo)}\""
    if param.hi is not None:
        bounds += f" max=\"{_esc(param.hi)}\""
    step = "1" if param.kind == "int" else "any"
    return (f"<input type=\"number\" id=\"{ident}\" name=\"{name}\" "
            f"value=\"{_fmt_value(param, value)}\"{bounds} step=\"{step}\" required>")


def _form_html(study, values, submit: str = "Run", form_key: str = "f-") -> str:
    """The parameter form of ``study``, prefilled from ``values``."""
    fields = []
    for param in study.params:
        value = values.get(param.key, param.default)
        unit = f" <span class=\"unit\">[{_esc(param.unit)}]</span>" if param.unit else ""
        help_text = (f"<p class=\"help\">{_esc(param.help)}</p>"
                     if param.help else "")
        fields.append(
            f"<div class=\"field\">"
            f"<label for=\"{_esc(form_key + param.key)}\">"
            f"{_esc(param.label)}{unit}</label>"
            f"{_control(form_key, param, value)}{help_text}</div>")
    return (f"<form method=\"post\" action=\"/run/{_esc(study.name)}\">"
            + "".join(fields)
            + f"<button type=\"submit\">{_esc(submit)}</button></form>")


def _demo_selector() -> str:
    """The demo picker: an ordinary GET form, because there is no JavaScript.

    A ``<select>`` cannot navigate on its own without a handler, so the picker
    submits to ``/demo``, which answers with a 303 to the chosen study's page.
    The option list comes from :data:`emfit.demos.DEMOS`, not from a second
    hand-maintained copy of the names.
    """
    options = "".join(
        f"<option value=\"{_esc(study.name)}\">{_esc(study.title)}</option>"
        for study in _DEMOS)
    return (
        "<form method=\"get\" action=\"/demo\">"
        "<label for=\"demo-study\"><strong>Load Demo</strong></label> "
        f"<select id=\"demo-study\" name=\"study\">{options}</select> "
        "<input type=\"submit\" value=\"Load Demo\">"
        "<p class=\"hint\">These are coarse-mesh demonstrations: they need no "
        "KiCad file, they run in seconds, and their numbers are illustrative "
        "rather than converged.</p></form>")


def _landing() -> bytes:
    demo_names = {study.name for study in _DEMOS}
    cards = []
    for study in studies.STUDIES.values():
        is_demo = study.name in demo_names
        tag = "<span class=\"tag\">demo</span>" if is_demo else ""
        cards.append(
            f"<a class=\"card{' demo' if is_demo else ''}\" "
            f"href=\"/s/{_esc(study.name)}\">"
            f"<h2>{_esc(study.title)}</h2><p>{_esc(study.blurb)}</p>{tag}"
            f"<span class=\"go\">Open study &rarr;</span></a>")
    body = (
        "<h1>emfit &mdash; finite-integration time-domain studies</h1>"
        f"<p class=\"lede\">{len(studies.STUDIES)} self-contained electromagnetics "
        "experiments on a Yee-type cell complex: pick one, adjust its handful of "
        "parameters and run it; the numbers and the figures come back in the same "
        "page.</p>"
        f"{_demo_selector()}"
        f"<div class=\"cards\">{''.join(cards)}</div>")
    return _page("emfit studies", body)


def _study_page(study, values, error: str = None) -> bytes:
    """The study's form page; ``error`` is shown above the form, fields kept."""
    error_html = ""
    if error:
        error_html = (f"<div class=\"error\"><strong>That did not run.</strong>"
                      f"<p>{_esc(error)}</p>"
                      f"<p>The values you typed are still in the form &mdash; "
                      f"adjust them and submit again.</p></div>")
    body = (
        "<p class=\"crumb\"><a href=\"/\">&larr; all studies</a></p>"
        f"<h1>{_esc(study.title)}</h1>"
        f"<p class=\"lede\">{_esc(study.blurb)}</p>"
        f"{error_html}"
        f"<h2>Parameters</h2>{_form_html(study, values)}")
    return _page(f"{study.name} &middot; emfit", body)


def _figure_html(figure) -> str:
    """One figure as an inline ``data:`` image with title and caption.

    The caption is authored as HTML in :mod:`emfit.studies` (it uses ``<i>`` and
    ``<sub>``), so it is inserted as-is; everything else on the page is escaped.
    """
    encoded = base64.b64encode(figure["png"]).decode("ascii")
    return (f"<figure><h2>{_esc(figure['title'])}</h2>"
            f"<img alt=\"{_esc(figure['title'])}\" "
            f"src=\"data:image/png;base64,{encoded}\">"
            f"<figcaption>{figure['caption']} "
            f"<span class=\"hint\">Right-click the image and save it to keep "
            f"the PNG.</span></figcaption></figure>")


def _attachment_html(attachment) -> str:
    """One non-PNG output -- today the ``rcs`` animation -- as a ``data:`` image.

    A figure is PNG by contract and :func:`_figure_html` embeds it as such; an
    attachment is any other media type, so it cannot go through that path.  The
    only attachment is a GIF, which the browser animates straight out of the
    ``data:`` URI, so the page stays one self-contained document with no media
    route behind it.  Unlike a figure's caption -- authored as HTML in
    :mod:`emfit.studies` -- an attachment's caption is plain text, so it is
    escaped here along with the title and the file name.
    """
    encoded = base64.b64encode(attachment["data"]).decode("ascii")
    title = _esc(attachment["title"])
    return (f"<figure><h2>{title}</h2>"
            f"<img alt=\"{title}\" "
            f"src=\"data:image/gif;base64,{encoded}\">"
            f"<figcaption>{_esc(attachment['caption'])} "
            f"<span class=\"hint\">The animation plays here; right-click it "
            f"and save it to keep {_esc(attachment['filename'])}.</span>"
            f"</figcaption></figure>")


def _results_page(study, values, metrics, figures, attachments=()) -> bytes:
    """Metrics table, then the figures, then any animation, then the form.

    ``attachments`` defaults to none, so the callers that only have figures
    (and every test that predates them) keep working unchanged.
    """
    rows = "".join(f"<tr><th>{_esc(key)}</th><td>{_esc(value)}</td></tr>"
                   for key, value in metrics.items())
    figures_html = "".join(_figure_html(figure) for figure in figures)
    if not figures_html:
        figures_html = "<p class=\"lede\">This run produced no figures.</p>"
    attachments_html = "".join(_attachment_html(attachment)
                                for attachment in attachments)
    body = (
        "<p class=\"crumb\"><a href=\"/\">&larr; all studies</a></p>"
        f"<h1>{_esc(study.title)}</h1>"
        f"<p class=\"lede\">Run of <code>{_esc(study.name)}</code> with the "
        f"parameters below.</p>"
        f"<table class=\"metrics\">{rows}</table>"
        f"{figures_html}"
        f"{attachments_html}"
        f"<h2>Run again</h2>{_form_html(study, values, submit='Run again')}"
        "<p class=\"crumb\"><a href=\"/\">&larr; back to all studies</a></p>")
    return _page(f"{study.name} &middot; emfit", body)


def _error_page(study, values, traceback_text: str) -> bytes:
    """500: the study raised; show the traceback and keep the form usable."""
    body = (
        "<p class=\"crumb\"><a href=\"/\">&larr; all studies</a></p>"
        f"<h1>{_esc(study.title)}</h1>"
        "<div class=\"error\"><strong>The study raised an exception.</strong>"
        "<p>These parameters reach the solver unchanged, so the traceback below "
        "is the real failure &mdash; change the parameters and run again.</p>"
        f"<pre>{_esc(traceback_text)}</pre></div>"
        f"<h2>Run again</h2>{_form_html(study, values, submit='Run again')}")
    return _page(f"{study.name} &middot; error &middot; emfit", body)


# ---------------------------------------------------------------------------
# request handling
# ---------------------------------------------------------------------------
def _prefill(study, raw) -> dict:
    """The study's keys, taking any submitted value over the default."""
    return {param.key: raw.get(param.key, param.default) for param in study.params}


class Handler(BaseHTTPRequestHandler):
    """Serves the three routes; every response is a complete document."""

    server_version = f"emfit/{__version__}"
    protocol_version = "HTTP/1.1"

    # -- plumbing -----------------------------------------------------------
    def log_message(self, fmt, *args):        # pragma: no cover - console only
        print(f"emfit: {self.address_string()} {fmt % args}", flush=True)

    def _send(self, code: int, body: bytes = b"",
              content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        """303 to ``location`` with an empty body: the demo picker's answer.

        ``GET /demo?study=<name>`` is a form submission but must end up as a
        page load, so it is redirected rather than rendered; ``no-store`` is
        the same cache policy every other response carries.
        """
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _not_found(self) -> None:
        body = _page("not found &middot; emfit",
                     "<h1>404 &mdash; no such page</h1>"
                     "<p class=\"lede\">That route does not exist. Start from "
                     "the <a href=\"/\">list of studies</a>.</p>")
        self._send(404, body)

    def _study_or_none(self, name: str):
        try:
            return studies.get(name)
        except ValueError:
            return None

    # -- routes -------------------------------------------------------------
    def _run_study(self, study, submitted, raw) -> None:
        """Coerce, run under the lock, and answer with the results page.

        Used by ``POST /run/<name>`` (form body) and ``GET /run/<name>``
        (query string), so both paths get the same validation and the same
        400/500 behaviour.
        """
        prefill = _prefill(study, raw)
        try:
            values = studies.coerce(study, submitted)
        except ValueError as exc:              # a typo must not dead-end
            return self._send(400, _study_page(study, prefill, error=str(exc)))

        sink = studies.FigureSink()
        try:
            with _LOCK:
                metrics = study.run(values, sink)
        except Exception:                      # noqa: BLE001 - the server must live
            return self._send(500, _error_page(study, values,
                                               traceback.format_exc()))
        return self._send(200, _results_page(study, values, metrics,
                                             sink.figures, sink.attachments))

    def do_GET(self) -> None:
        parts = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parts.path)
        if path == "/healthz":
            return self._send(200, b"ok", "text/plain; charset=utf-8")
        if path == "/favicon.ico":
            return self._send(204, b"")
        if path == "/":
            return self._send(200, _landing())
        if path == "/demo":
            query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
            name = (query.get("study") or [""])[-1].strip().lower()
            study = self._study_or_none(name)
            if study is not None:
                return self._redirect(f"/s/{study.name}")
            return self._send(400, _page(
                "demo &middot; emfit",
                "<h1>400 &mdash; pick a demo</h1>"
                f"<p class=\"lede\">No demo study named <code>{_esc(name)}</code>. "
                "Choose one from the <a href=\"/\">list of studies</a>.</p>"))
        if path.startswith("/s/"):
            study = self._study_or_none(path[3:].strip("/"))
            if study is None:
                return self._not_found()
            query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
            raw = {key: (values[-1] if values else "")
                   for key, values in query.items()}
            return self._send(200, _study_page(study, _prefill(study, raw)))
        if path.startswith("/run/"):
            study = self._study_or_none(path[5:].strip("/"))
            if study is None:
                return self._not_found()
            query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
            raw = {key: (values[-1] if values else "")
                   for key, values in query.items()}
            return self._run_study(study, query, raw)
        return self._not_found()

    def do_POST(self) -> None:
        parts = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parts.path)
        if not path.startswith("/run/"):
            return self._not_found()
        study = self._study_or_none(path[5:].strip("/"))
        if study is None:
            return self._not_found()

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            return self._send(413, _page(
                "request too large &middot; emfit",
                "<h1>413 &mdash; request too large</h1><p class=\"lede\">The form "
                f"is a few short fields; {length} bytes is more than this server "
                "accepts.</p>"))
        body = self.rfile.read(max(length, 0)).decode("utf-8", "replace")
        submitted = urllib.parse.parse_qs(body, keep_blank_values=True)
        raw = {key: (values[-1] if values else "")
               for key, values in submitted.items()}
        return self._run_study(study, submitted, raw)


# ---------------------------------------------------------------------------
# server lifecycle
# ---------------------------------------------------------------------------
def make_server(host: str = "127.0.0.1",
                port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Bind and return a server; ``port=0`` lets the OS pick (read it back).

    The returned object has ``.server_address`` (host, port) and the usual
    ``serve_forever`` / ``shutdown`` / ``server_close``; tests drive it from a
    thread, :func:`serve` drives it in the foreground.
    """
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    return httpd


def serve(host: str = "127.0.0.1", port: int = DEFAULT_PORT, on_ready=None):
    """Serve the web UI until interrupted; returns the server object.

    Args:
        host: Interface to bind. Keep it on loopback -- the server trusts what
            it is sent and runs the parameters through a Python study.
        port: Port; ``0`` asks the OS for a free one (the real port is printed,
            and :func:`make_server`'s ``server_address`` has it).
        on_ready: Optional callable receiving the bound server before the loop
            starts -- the hook a test needs to learn a ``port=0`` binding
            without parsing stdout.

    Returns:
        The :class:`http.server.ThreadingHTTPServer`, after it has shut down.
    """
    httpd = make_server(host, port)
    bound_host, bound_port = httpd.server_address[:2]
    print(f"emfit {__version__}: {len(studies.STUDIES)} studies on "
          f"http://{bound_host}:{bound_port}/  (Ctrl-C to stop)", flush=True)
    try:
        if on_ready is not None:
            on_ready(httpd)
        httpd.serve_forever()
    except KeyboardInterrupt:                  # Ctrl-C is a normal way to stop
        print("\nemfit: stopped", flush=True)
    finally:
        httpd.server_close()
    return httpd
