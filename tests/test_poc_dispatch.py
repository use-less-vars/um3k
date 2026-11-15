"""One entry point, one shell: what ``main`` hands each artefact.

``main`` reads the dump through ``reload_page`` - the same call a browser reload
uses - and then opens the ONE shell, ``run_web_vis``, whichever schema came back
(poc_app.py:9856-9886). The page's own context (``ctx.available``) decides which
machinery that shell builds; dispatch no longer forks on the schema, so there is
no second viewer in ``main`` to keep in step.

These tests assert the CALL, not the page. ``run_web_vis``, ``run_web``,
``print_keys`` and ``reload_page`` are replaced with recorders and the structure
registry with one synthetic entry, so no trame server boots, no plotter is
created and no npz is opened - what is under test is the routing decision and the
arguments it carries. The routing is the whole subject: a regression here hands
an artefact to a viewer the page was not built by, and nothing else in the suite
would notice.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries artifacts/verify_wd.py adds, so `import poc_app`
        # resolves from server/poc_app.py
        sys.path.insert(0, _p)

# In this image pyvista/trame/vtk live in the repo's own venv (its bin/python is
# broken, the site-packages tree is not).  On a host where they are installed
# normally this directory is either absent or already on sys.path, so the block
# is inert there.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

pytest.importorskip("pyvista", reason="poc_app imports pyvista at module scope")
pytest.importorskip("trame.app", reason="poc_app imports trame at module scope")

import poc_app  # noqa: E402  (after the sys.path / importorskip preamble)


def _field_info() -> dict:
    """A bare field dump: the (station, y, z) stack and NO ``format`` tag.

    ``load_dump`` writes no ``format`` key at all, which is exactly what makes
    this the artefact the old fork sent to ``run_web``.
    """
    info = {
        "plane_ez": np.zeros((3, 4, 5)),
        "nstep": 1,
        "nx": 5,
        "ny": 4,
        "nz": 5,
        "cell_m": 4e-4,
    }
    assert "format" not in info
    return info


def _vis_info() -> dict:
    """An animation dump: the tag ``load_vis`` writes, and a timeline."""
    return {"format": poc_app.VIS_FORMAT, "nt": 4, "nt_x": 2}


class _Recorder:
    """Stand in for a shell / printer and remember every call."""

    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, *args, **kwargs) -> int:
        self.calls.append((args, kwargs))
        return 0


@pytest.fixture
def wiring(monkeypatch, tmp_path):
    """``main`` with its four seams recorded and one synthetic structure entry."""
    entry = {"id": "s1"}
    page = {"info": None, "path": str(tmp_path / "d.npz")}
    monkeypatch.setattr(poc_app, "load_structures", lambda: [entry])
    monkeypatch.setattr(
        poc_app, "_structure_is_record_only", lambda structure: False
    )
    monkeypatch.setattr(
        poc_app, "reload_page", lambda npz_path, structure_id=None: page
    )
    recorders = {
        "print_keys": _Recorder(),
        "run_web_vis": _Recorder(),
        "run_web": _Recorder(),
    }
    for name, recorder in recorders.items():
        monkeypatch.setattr(poc_app, name, recorder)
    return {"page": page, "entry": entry, **recorders}


def _main(info: dict, wiring: dict, *extra: str) -> int:
    """Run ``main`` on this page, with the dump read faked to hand ``info`` back."""
    wiring["page"]["info"] = info
    return poc_app.main(["--structure", "s1", "--input", "fake.npz", *extra])


def test_main_sends_a_field_dump_to_the_unified_shell(wiring):
    """If this fails, a field dump still forks to the legacy station viewer."""
    info = _field_info()

    rc = _main(info, wiring)

    assert rc == 0, f"main returned {rc}"
    assert len(wiring["run_web"].calls) == 0, (
        "a field dump was handed to run_web: "
        f"{wiring['run_web'].calls}"
    )
    assert len(wiring["run_web_vis"].calls) == 1, (
        "the unified shell was not called once for a field dump: "
        f"{wiring['run_web_vis'].calls}"
    )
    (args, kwargs) = wiring["run_web_vis"].calls[0]
    assert args[0] is info, "the shell was not handed the reloaded page's info"
    assert args[1] == poc_app.DEFAULT_HOST
    assert args[2] == poc_app.DEFAULT_PORT
    assert args[3] == poc_app.DEFAULT_FPS, (
        "the fps argument is not the parser's default any more: "
        f"{args[3]!r} != {poc_app.DEFAULT_FPS!r}"
    )
    assert args[4] == wiring["entry"], "the resolved structure was not forwarded"
    assert args[5] == [wiring["entry"]], "the registry was not forwarded"
    assert kwargs["loaded_page"] is wiring["page"], (
        "the page main already loaded was not forwarded, so the shell would "
        "reload the dump a second way"
    )
    assert kwargs["surface_dump"] is None, "--surface-dump was not given"


def test_main_still_sends_a_vis_dump_to_the_unified_shell(wiring):
    """The animation dump keeps the shell it already had - the fork must not flip."""
    info = _vis_info()

    rc = _main(info, wiring)

    assert rc == 0, f"main returned {rc}"
    assert len(wiring["run_web"].calls) == 0
    assert len(wiring["run_web_vis"].calls) == 1, (
        "the unified shell was not called once for an animation dump: "
        f"{wiring['run_web_vis'].calls}"
    )
    (args, kwargs) = wiring["run_web_vis"].calls[0]
    assert args[0] is info
    assert args[3] == poc_app.DEFAULT_FPS
    assert kwargs["loaded_page"] is wiring["page"]


def test_main_list_keys_returns_before_either_shell(wiring):
    """``--list-keys`` prints and exits; no page is ever served for it."""
    info = _field_info()

    rc = _main(info, wiring, "--list-keys")

    assert rc == 0, f"main returned {rc}"
    assert len(wiring["print_keys"].calls) == 1, (
        f"print_keys was called {len(wiring['print_keys'].calls)} times"
    )
    (args, kwargs) = wiring["print_keys"].calls[0]
    assert args[0] is info, "print_keys was handed something other than the info"
    assert kwargs == {}
    assert wiring["run_web"].calls == []
    assert wiring["run_web_vis"].calls == []
