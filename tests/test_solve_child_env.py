"""``_solve_child_env``: the environment the solve child is really launched in.

THE GAP THESE TESTS ARE ABOUT
-----------------------------
Every launch the documents give puts the REPOSITORY ROOT on ``PYTHONPATH`` and
never the venv (``PYTHONPATH=. python3 server/poc_app.py``, RUN.md and
docs/kb/WORK/run.md:33-58). The compiled kernel is not on that path - it lives
in ``.venv/lib/python3.12/site-packages/emfit_core.cpython-312-*.so`` - so a
child started with the inherited environment dies on ``import emfit_core``
before it solves anything, and the operator sees a failure sentence that names
nothing they can fix. ``_solve_child_env()`` is the fix: ``os.environ`` plus
that one directory, APPENDED (the root keeps precedence), and only when the
directory really carries the kernel.

Both halves are pinned below. The path arithmetic is tested against a
CONTROLLED ``PYTHONPATH`` (this pytest process's own one already starts with the
venv, so reading it in-process would prove nothing about ORDERING), and the
claim that matters is tested by really spawning a child and importing the
kernel - with the same child, minus the env, as the negative control.

WHY THE PATH ARITHMETIC IS HERMETIC (DR-51)
-------------------------------------------
``.venv/`` is GITIGNORED (``.gitignore``, "Virtual environments"), so it does
not exist in a fresh checkout and does not exist in CI. A test that needs the
REAL venv to be on disk therefore passes on the box that wrote it and fails on
the host - which is a defect, by DR-51 in docs/defect_register.md. So every test
that needs the function to ACTUALLY APPEND points ``_VENV_SITE_PACKAGES`` at a
``tmp_path`` directory carrying one dummy
``emfit_core.cpython-312-x86_64-linux-gnu.so``. That is sufficient because the
shipped function only GLOBS that directory - it never opens, imports or executes
what it finds (see ``_solve_child_env``: ``glob`` then ``str(...)``). Only the
two tests that really spawn a child and import the kernel need the genuine
``.so``, and those are skipped - by name, with the missing thing named - when
the venv is absent.

WHY THE CODE IS EXTRACTED INSTEAD OF IMPORTED
----------------------------------------------
``server/poc_app.py`` is a ~20k-line trame app: importing it pulls in the whole
plotting and UI stack, and nothing under test needs any of that.
``_solve_child_env`` reads only ``os`` and ``_VENV_SITE_PACKAGES``, and
``SolveJob`` only ``subprocess``, ``threading``, ``collections.deque``, ``sys``,
``time`` and ``SOLVER_SCRIPT``, so their source is taken out with ``ast`` and
exec'd against exactly those names: what runs is the repository's code, byte for
byte, at the price of a parse instead of an import.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "server" / "poc_app.py"
#: The directory the shipped function appends. Named here rather than read out
#: of the module so a test can say what it expects without importing the app.
VENV_SITE_PACKAGES = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
#: The stand-in kernel's file name: the exact SHAPE the shipped
#: ``glob("emfit_core.cpython-*.so")`` matches. The file is EMPTY - see
#: :func:`_fake_venv` and the module docstring, the function only globs.
DUMMY_KERNEL_NAME = "emfit_core.cpython-312-x86_64-linux-gnu.so"
#: Whether THIS checkout carries the real kernel. ``.venv/`` is gitignored, so
#: this is False on a fresh clone / in CI - and then only the two real-import
#: tests are skipped, while the other five still run and still assert.
_HAVE_KERNEL = bool(list(VENV_SITE_PACKAGES.glob("emfit_core.cpython-*.so")))

TEXT = SOURCE.read_text(encoding="utf-8")
TREE = ast.parse(TEXT)


# =============================================================================
# The extraction harness: the shipped source, parsed rather than imported
# =============================================================================


def _node(name: str) -> ast.AST:
    """The FIRST ``def name`` anywhere in the file, nested or not."""
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node
    raise AssertionError(f"{name} not found in server/poc_app.py")


def _exec_def(name: str, namespace: dict):
    """Exec ONE shipped function into ``namespace`` and hand it back.

    The exec'd function's globals ARE ``namespace``, which is how the module
    constant it reads (``_VENV_SITE_PACKAGES``) reaches it without an import.
    """
    segment = ast.get_source_segment(TEXT, _node(name))
    exec(compile(segment, f"<{name}>", "exec"), namespace)
    return namespace[name]


def _solve_job_class():
    """``SolveJob``, lifted out of ``server/poc_app.py`` without the app."""
    for node in TREE.body:
        if isinstance(node, ast.ClassDef) and node.name == "SolveJob":
            segment = ast.get_source_segment(TEXT, node)
            break
    else:
        raise AssertionError("SolveJob not found in server/poc_app.py")
    namespace = {
        "deque": deque,
        "subprocess": subprocess,
        "threading": threading,
        "sys": sys,
        "time": time,
        "SOLVER_SCRIPT": SOURCE,
    }
    exec(compile(segment, "<SolveJob>", "exec"), namespace)
    return namespace["SolveJob"]


def _child_env(venv_site_packages=VENV_SITE_PACKAGES):
    """The shipped ``_solve_child_env``, with the dir it globs under control.

    A FRESH function per call - and therefore a fresh globals dict - so one
    test pointing the constant at a directory without a kernel cannot leak into
    the next.

    ``_solve_child_env`` takes no arguments and reads ``_VENV_SITE_PACKAGES`` as
    a MODULE GLOBAL at call time (it is loaded, never a default or a local), so
    handing it this namespace is the same lever as
    ``monkeypatch.setattr(poc_app, "_VENV_SITE_PACKAGES", tmp_path)`` would pull
    on the imported module.
    """
    namespace = {"os": os, "_VENV_SITE_PACKAGES": Path(venv_site_packages)}
    return _exec_def("_solve_child_env", namespace)


def _fake_venv(tmp_path) -> Path:
    """A ``_VENV_SITE_PACKAGES`` stand-in that carries a kernel-shaped file.

    WHY THIS EXISTS: ``.venv/`` is GITIGNORED, so a test that needs the REAL
    venv on disk passes on the author's box and fails on a fresh checkout - the
    defect DR-51 in docs/defect_register.md names. The shipped
    ``_solve_child_env`` only GLOBS its directory for
    ``emfit_core.cpython-*.so`` and never opens, imports or runs what it finds,
    so ONE EMPTY FILE with that name is enough to make it take its "append the
    venv" branch. Nothing here is weakened: the tests below still assert order,
    dedup and non-mutation exactly as before - they just no longer depend on a
    gitignored directory existing.
    """
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    (site_packages / DUMMY_KERNEL_NAME).write_bytes(b"")
    # The precondition the rest of each test rests on: the glob the shipped
    # function runs really does match here.
    assert list(site_packages.glob("emfit_core.cpython-*.so"))
    return site_packages


#: The one thing the real child is asked to do. If this line is reachable, the
#: kernel resolved; if it is not, ``import emfit_core`` is what failed.
IMPORT_KERNEL = "import emfit_core\nprint('kernel imported')\n"


def _job(script: str, env):
    """A real job: the interpreter that is running the tests, in the repo root."""
    return _solve_job_class()(
        [sys.executable, "-c", script], cwd=str(REPO_ROOT), env=env
    )


# =============================================================================
# The path arithmetic: appended, once, and never at the parent's expense
# =============================================================================


def test_the_venv_is_appended_after_what_was_already_on_the_path(
    monkeypatch, tmp_path
):
    """APPENDED, not prepended: the repository root keeps precedence."""
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(["/repo/root", "/elsewhere"]))
    venv = _fake_venv(tmp_path)
    env = _child_env(venv)()
    entries = env["PYTHONPATH"].split(os.pathsep)
    assert entries[:2] == ["/repo/root", "/elsewhere"]
    assert entries[-1] == str(venv)
    assert entries.count(str(venv)) == 1


def test_no_pythonpath_at_all_yields_just_the_venv(monkeypatch, tmp_path):
    """Nothing to preserve: the env gets the one directory and no stray separator."""
    monkeypatch.delenv("PYTHONPATH", raising=False)
    venv = _fake_venv(tmp_path)
    env = _child_env(venv)()
    assert env["PYTHONPATH"] == str(venv)


def test_a_second_call_does_not_add_it_twice(monkeypatch, tmp_path):
    """The child env is built per press; a re-press must not pile up entries."""
    monkeypatch.setenv("PYTHONPATH", "/repo/root")
    venv = _fake_venv(tmp_path)
    first = _child_env(venv)()
    second = _child_env(venv)()
    assert second["PYTHONPATH"] == first["PYTHONPATH"]
    assert second["PYTHONPATH"].split(os.pathsep).count(str(venv)) == 1


def test_the_parent_environment_is_left_alone(monkeypatch, tmp_path):
    """A COPY: the app's own env keeps the path the documents gave it."""
    monkeypatch.setenv("PYTHONPATH", "/repo/root")
    venv = _fake_venv(tmp_path)
    before = dict(os.environ)
    env = _child_env(venv)()
    assert dict(os.environ) == before
    assert os.environ["PYTHONPATH"] == "/repo/root"
    assert env is not os.environ
    assert env["PYTHONPATH"] != os.environ["PYTHONPATH"]


def test_without_the_kernel_in_it_the_env_comes_back_unchanged(
    monkeypatch, tmp_path
):
    """No ``emfit_core.cpython-*.so``: refuse, rather than add a dead entry."""
    monkeypatch.setenv("PYTHONPATH", "/repo/root")
    empty = tmp_path / "site-packages"
    empty.mkdir()
    assert not list(empty.glob("emfit_core.cpython-*.so"))
    env = _child_env(empty)()
    assert env == dict(os.environ)
    assert env["PYTHONPATH"] == "/repo/root"


# =============================================================================
# The claim itself: a child that is really spawned
# =============================================================================


@pytest.mark.skipif(
    not _HAVE_KERNEL,
    reason=(
        "needs the workspace venv (.venv/, gitignored and absent from a fresh "
        "checkout) to supply emfit_core"
    ),
)
def test_a_child_launched_with_this_env_can_import_the_kernel():
    """The whole point: ``import emfit_core`` succeeds under this env."""
    job = _job(IMPORT_KERNEL, _child_env()())
    assert job.run() == "ok"
    assert "kernel imported" in job.log


def test_the_same_child_launched_without_this_env_cannot():
    """The control that makes the test above mean something.

    ``emfit_core`` is installed ONLY in the venv's site-packages, so a child
    given nothing but ``PATH`` must fail on the import - otherwise the test
    above would pass whether or not the function did anything.

    NOT SKIPPED, deliberately: this test asserts a FAILURE, so it needs no
    kernel to be present and it is equally true on a checkout with no ``.venv``
    (where nothing supplies ``emfit_core`` at all). Guarding it would have
    thrown away the one assertion that survives a fresh clone.
    """
    job = _job(IMPORT_KERNEL, {"PATH": os.environ.get("PATH", "")})
    assert job.run() == "failed"
    assert "emfit_core" in job.log
