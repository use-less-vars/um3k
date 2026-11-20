"""The live log under the Solve card, and the lines it is made of.

THE GAP THESE TESTS ARE ABOUT
-----------------------------
``SolveJob`` keeps the child's output in ONE bounded tail (``log``: the last
4000 characters of it), and the card published exactly one line of that: the
last non-blank line, as the second line of ``solve_status``. A march that
prints a study's worth of numbers therefore showed the operator a single line
that changed every half second, and, on failure, a 400-character blob with no
line breaks a card could use. The fix is ``SolveJob.log_lines`` - the tail as
whole lines, newest last, bounded twice (a dozen lines of at most 160
characters each) - published into ``state.solve_log`` and drawn as a ``<pre>``
under the status line, which is also why the failure sentence stops repeating
that blob: the panel is already carrying it.

WHY THE CODE IS EXTRACTED INSTEAD OF IMPORTED
----------------------------------------------
``server/poc_app.py`` is a ~20k-line trame app: importing it pulls in the whole
plotting and UI stack. Nothing under test needs any of that. ``SolveJob`` uses
only ``subprocess``, ``threading``, ``collections.deque``, ``sys``, ``time`` and
the module constant ``SOLVER_SCRIPT``, so its own source is taken out with
``ast`` and exec'd against exactly those names. ``_tick_solve_status``,
``_action`` and the failure branch of ``_poll_solve`` are nested functions with
no such luck: they are lifted out the same way and given the smallest namespace
they read (``state``, ``widgets``, ``html_widgets``), so what runs is the code
in the repository, byte for byte, at the price of a parse instead of an import.

``cwd`` is always passed explicitly to a real job: left to its default it would
use the solver's own directory, which a test has no business depending on.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
import threading
import time
from collections import deque
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "server" / "poc_app.py"
CWD = str(REPO_ROOT)

TEXT = SOURCE.read_text(encoding="utf-8")
TREE = ast.parse(TEXT)


# =============================================================================
# The extraction harness: the shipped source, parsed rather than imported
# =============================================================================


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
    constants it reads (``_SOLVE_LOG_STYLE``) and the state it writes reach it
    without an import.
    """
    segment = ast.get_source_segment(TEXT, _node(name))
    exec(compile(segment, f"<{name}>", "exec"), namespace)
    return namespace[name]


def _constant(name: str):
    """A module-level constant whose value is a literal, evaluated from source."""
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if name in targets:
                return ast.literal_eval(node.value)
    raise AssertionError(
        f"{name} is not a module-level literal in server/poc_app.py: the card's "
        "log panel binds its style by name, and the tests must read the same "
        "value the widget was given"
    )


def _job(script: str):
    return _solve_job_class()([sys.executable, "-c", script], cwd=CWD)


class _Holder:
    """A dict-with-attributes: the smallest thing ``state`` has to be."""

    def __init__(self, **values):
        self.__dict__.update(values)


#: Thirty numbered lines plus a verdict: 31 lines in a 12-line window, so the
#: order and the cut are both visible in one list.
NUMBERED = """\
import sys
for _i in range(30):
    print(f"step {_i}")
print("done")
sys.stdout.flush()
"""


# =============================================================================
# SolveJob.log_lines: the tail as LINES
# =============================================================================


def test_log_lines_are_the_last_lines_oldest_first():
    """The window is the END of the output, in the order the child wrote it."""
    SolveJob = _solve_job_class()
    job = _job(NUMBERED)
    assert job.log_lines == [], (
        "a job that has never run already reports log lines: "
        f"{job.log_lines!r}"
    )

    status = job.run()
    assert status == "ok", f"the child exited 0 but run() said {status!r}"
    assert job.last_line == "done", (
        f"last_line is {job.last_line!r}: the tail was not kept to its end"
    )

    window = SolveJob.LOG_LINES_SHOWN
    expected = [f"step {i}" for i in range(30 - (window - 1), 30)] + ["done"]
    assert job.log_lines == expected, (
        f"log_lines is {job.log_lines!r}, not the last {window} lines of the "
        f"child's output in order ({expected!r}). The panel is a WINDOW on the "
        "end of the log, newest last; a reversed, unbounded or stale list puts "
        "the wrong lines on screen."
    )


def test_the_window_drops_blanks_and_caps_the_width():
    """A blank line spends the window saying nothing; a long one is trimmed."""
    SolveJob = _solve_job_class()
    long_line = "HEAD" + "A" * 400 + "TAIL"

    job = _job(
        "import sys\n"
        "print('')\n"
        "print('   ')\n"
        f"print({long_line!r})\n"
        "print('after')\n"
        "print('')\n"
        "sys.stdout.flush()\n"
    )
    assert job.run() == "ok", "the child exited 0 but run() disagreed"

    lines = job.log_lines
    assert "" not in lines, f"a blank line reached the card: {lines!r}"
    assert lines[-1] == "after", (
        f"the window does not end on the child's last line: {lines!r}"
    )
    assert len(lines) == 2, (
        f"the window is {lines!r}: two lines were printed and two blanks were "
        "dropped, so the panel is showing something else"
    )
    trimmed = lines[0]
    assert len(trimmed) == SolveJob.LOG_LINE_CHARS, (
        f"the 408-character line arrived as {len(trimmed)} characters: an "
        "untrimmed line wraps the card into a wall of text"
    )
    assert long_line.endswith(trimmed), (
        f"the WRONG end of the long line was kept: {trimmed!r} is not the tail "
        "of what the child printed, and last_line keeps the tail"
    )


# =============================================================================
# The card: the tick that publishes the lines, and the <pre> that shows them
# =============================================================================


def _tick():
    namespace = {
        "sys": sys,
        "_SOLVE_LOG_STYLE": _constant("_SOLVE_LOG_STYLE"),
        "_SOLVE_LOG_HIDDEN": _constant("_SOLVE_LOG_HIDDEN"),
    }
    return _exec_def("_tick_solve_status", namespace), namespace


class _FakeJob:
    """A job mid-run: a clock, a last line, and the lines behind it."""

    def __init__(self, lines, elapsed=2.4, last="step 29"):
        self.log_lines = list(lines)
        self.elapsed_seconds = elapsed
        self.last_line = last


def test_the_tick_publishes_the_lines_and_unhides_the_panel():
    """Every half second the card gets the WHOLE window, not just its last line."""
    tick, namespace = _tick()
    state = _Holder(
        solve_structure="B",
        solve_log="",
        solve_log_style=namespace["_SOLVE_LOG_HIDDEN"],
    )
    namespace["state"] = state

    lines = ["step 28", "step 29"]
    tick(_FakeJob(lines))

    assert state.solve_log == "step 28\nstep 29", (
        f"state.solve_log is {state.solve_log!r}: the card is showing "
        f"{len(lines)} available lines as something else, and a <pre> reads "
        "one line per newline"
    )
    assert state.solve_log_style == namespace["_SOLVE_LOG_STYLE"], (
        f"the panel is still styled {state.solve_log_style!r} with lines to "
        "show: it stays invisible and the log exists only in the state"
    )
    assert state.solve_status == "solving B - 2 s elapsed\nstep 29", (
        f"the one-line status changed shape: {state.solve_status!r}"
    )


def test_a_silent_job_hides_the_panel_again():
    """No lines means no box: an empty <pre> is height that says nothing."""
    tick, namespace = _tick()
    state = _Holder(
        solve_structure="B",
        solve_log="step 28\nstep 29",
        solve_log_style=namespace["_SOLVE_LOG_STYLE"],
    )
    namespace["state"] = state

    tick(_FakeJob([], last=""))

    assert state.solve_log == "", (
        f"a job with nothing to say left {state.solve_log!r} on screen: that "
        "is a previous run's log under this run's clock"
    )
    assert state.solve_log_style == namespace["_SOLVE_LOG_HIDDEN"], (
        f"the panel is styled {state.solve_log_style!r} around an empty log: an "
        "empty box is what the hidden default exists for"
    )
    assert "\n" not in state.solve_status, (
        f"the status line has a dangling second line: {state.solve_status!r}"
    )


class _FakeWidgets:
    """The Vuetify namespace the card emits into, recording in call order."""

    def __init__(self, calls):
        self.calls = calls

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        def emit(*args, **kwargs):
            self.calls.append((key, args, kwargs))

        return emit


class _FakeHtml:
    """The trame html layer, recording in the SAME order (or without ``Pre``)."""

    def __init__(self, calls, with_pre=True):
        self.calls = calls
        if with_pre:
            self.Pre = self._pre

    def _pre(self, *args, **kwargs):
        self.calls.append(("Pre", args, kwargs))


def _action(with_pre=True):
    calls: list = []
    namespace = {
        "widgets": _FakeWidgets(calls),
        "ctrl": _Holder(solve_start=None),
        "html_widgets": _FakeHtml(calls, with_pre=with_pre),
        "_SOLVE_LOG_HIDDEN": _constant("_SOLVE_LOG_HIDDEN"),
    }
    _exec_def("_action", namespace)()
    return calls


def test_the_card_carries_the_log_under_the_status_line():
    """Action card order: the button, what it said, then the log behind it."""
    calls = _action()
    kinds = [kind for kind, _args, _kwargs in calls]
    assert kinds == ["VBtn", "VLabel", "Pre"], (
        f"the Action card emitted {kinds}: the Solve button, the status line "
        "and the log under them is the order a run is read in"
    )

    label_args = calls[1][1]
    assert label_args == ("{{ solve_status }}",), (
        f"the status line is no longer bound to solve_status: {label_args!r}"
    )

    _kind, pre_args, pre_kwargs = calls[2]
    assert pre_args == ("{{ solve_log }}",), (
        f"the panel is bound to {pre_args!r}, not to the state the tick fills"
    )
    assert pre_kwargs == {
        "style": ("solve_log_style", _constant("_SOLVE_LOG_HIDDEN"))
    }, (
        f"the panel's style is {pre_kwargs!r}: it must be BOUND to "
        "solve_log_style, or it can never be un-hidden when a run starts, and "
        "its default must be the hidden style the boot state also starts on"
    )


def test_a_build_without_the_html_layer_keeps_its_button():
    """No ``Pre`` in this variant: the panel goes, the press stays."""
    calls = _action(with_pre=False)
    kinds = [kind for kind, _args, _kwargs in calls]
    assert kinds == ["VBtn", "VLabel"], (
        f"a variant with no html layer emitted {kinds}: the log panel is an "
        "extra, and losing it must not cost the page its Solve button"
    )


# =============================================================================
# The failure sentence: the log is on screen, so it is not printed again
# =============================================================================


def _failure_branch():
    """``_poll_solve``'s failure body, as a callable over (state, job, ...)."""
    poll = _node("_poll_solve")
    for node in ast.walk(poll):
        if isinstance(node, ast.If) and ast.unparse(node.test) == "status != 'ok'":
            body = node.body
            break
    else:
        raise AssertionError(
            'the `if status != "ok":` branch is gone from _poll_solve: a failed '
            "solve says nothing at all about the page on screen"
        )
    segment = "\n".join(ast.get_source_segment(TEXT, stmt) for stmt in body)
    wrapper = "def _failure(state, job, status, elapsed):\n" + textwrap.indent(
        textwrap.dedent(segment), "    "
    )
    namespace: dict = {
        "_SOLVE_LOG_STYLE": _constant("_SOLVE_LOG_STYLE"),
        "_SOLVE_LOG_HIDDEN": _constant("_SOLVE_LOG_HIDDEN"),
    }
    _exec_def("_solve_failure_hint", namespace)
    exec(compile(wrapper, "<failure>", "exec"), namespace)
    return namespace["_failure"]


class _CrashedJob:
    """A dead job with nothing to say: what the failure branch reads of it."""

    returncode = 2
    #: The branch unhides the panel from ``log_lines``. A job that died before
    #: its first line leaves this empty, which is exactly the case the
    #: 400-character blob is kept for.
    log_lines = ()

    def __init__(self, log):
        self.log = log


CRASH_LOG = "step 28\nstep 29\nTraceback (most recent call last):\nBOOM\n"


def test_a_failed_solve_does_not_print_its_log_twice():
    """The panel has the lines; the sentence must not carry the blob as well."""
    failure = _failure_branch()
    state = _Holder(solve_log="step 28\nstep 29\nTraceback (most recently")

    failure(state, _CrashedJob(CRASH_LOG), "failed", "3.0")

    assert state.solve_status == (
        "solve failed after 3.0 s (rc=2) - "
        "the page on screen is still the previous dump"
    ), (
        f"the failure sentence is {state.solve_status!r}. The child's output is "
        "on screen in the log panel already, so appending it here printed the "
        "last screen of a failed solve twice - the second time as one string "
        "with no line breaks the card can use."
    )


def test_a_failure_before_the_first_tick_still_carries_the_output():
    """No panel to carry it (nothing ticked): the blob is the only copy."""
    failure = _failure_branch()
    state = _Holder(solve_log="")

    failure(state, _CrashedJob(CRASH_LOG), "crashed", "0.2")

    assert state.solve_status == (
        "solve crashed after 0.2 s (rc=2) - "
        f"the page on screen is still the previous dump\n{CRASH_LOG[-400:]}"
    ), (
        f"the failure sentence is {state.solve_status!r}: with an empty log "
        "panel the child's last 400 characters are the ONLY thing the reader "
        "has to go on, and they are missing"
    )


# =============================================================================
# The hint: WHY it died, when this build can name the cause
# =============================================================================


#: The child's own words for each measured cause, verbatim: the import failure
#: is emfit/evolve.py:260's, the refusal is
#: evidence/termination/run_build_A.py:3767-3772's (exit 2).
EMFIT_LOG = (
    "Traceback (most recent call last):\n"
    '  File "emfit/evolve.py", line 258, in _load\n'
    "import emfit_core\n"
    "ModuleNotFoundError: No module named 'emfit_core'\n"
)
MEM_LOG = (
    "REFUSED: --mem-ceiling-mb 2000.0 MB is above the container limit "
    "512.0 MB, so the solver does not start\n"
)


def test_the_hint_names_the_two_measured_causes():
    """The pure function: both causes get a sentence, junk gets nothing."""
    hint = _exec_def("_solve_failure_hint", {})

    assert hint(EMFIT_LOG) == (
        "the child interpreter cannot import the compiled kernel: "
        "start the app with the venv site-packages on PYTHONPATH "
        "(PYTHONPATH=.:.venv/lib/python3.12/site-packages python3 "
        "server/poc_app.py), which RUN.md's PYTHONPATH=. alone does not do"
    ), "the missing-kernel hint is not the venv launch RUN.md leaves out"
    assert hint("emfit_core exists on disk but could not be imported") == (
        "the child interpreter cannot import the compiled kernel: "
        "start the app with the venv site-packages on PYTHONPATH "
        "(PYTHONPATH=.:.venv/lib/python3.12/site-packages python3 "
        "server/poc_app.py), which RUN.md's PYTHONPATH=. alone does not do"
    ), (
        "the same cause in evolve.py:260's own wording is not recognised: "
        "the reader gets the log and no name for what it means"
    )
    assert hint(MEM_LOG) == (
        "the requested memory ceiling is above the limit of the "
        "environment the app runs in, so the solver refuses before it "
        "starts"
    ), "the refusal's hint is not the fix the refusal is asking for"

    for text in (
        "",
        None,
        CRASH_LOG,
        "emfit_core is fine, honestly",
        "--mem-ceiling-mb 2000 MB, with no limit named anywhere",
    ):
        assert hint(text) is None, (
            f"a hint was invented for {text!r}: a hint is a claim about the "
            "operator's machine, and a wrong one sends the reader after a fix "
            "that is not theirs. The child's own words are on the card."
        )


class _DeadJob:
    """A job that has LANDED: the things ``_poll_solve`` reads of it."""

    def __init__(self, log, returncode=1, status="failed", elapsed=3.0,
                 lines=()):
        self.log = log
        self.returncode = returncode
        self.status = status
        self.elapsed_seconds = elapsed
        self.log_lines = list(lines)
        self.last_line = self.log_lines[-1] if self.log_lines else ""

    def poll(self):
        return self.status


def _poll():
    """The WHOLE ``_poll_solve``, exec'd over a stand-in page and job slot.

    The shipped function is a closure (``nonlocal nt, nt_x``), so its source
    is wrapped in one enclosing ``def`` that owns those two names. Everything
    else it reads - the page, the state, the panel loaders, the repaint - is a
    stand-in: this test is about the two sentences the watcher writes, not
    about the page it repaints.
    """
    segment = ast.get_source_segment(TEXT, _node("_poll_solve"))
    wrapper = (
        "def _make():\n"
        "    nt = nt_x = None\n"
        + textwrap.indent(textwrap.dedent(segment), "    ")
        + "\n    return _poll_solve\n"
    )
    state = _Holder(
        solve_log="",
        solve_log_style=_constant("_SOLVE_LOG_HIDDEN"),
        frame="0",
    )
    page = {"info": {}}
    namespace = {
        "sys": sys,
        "Path": Path,
        "state": state,
        "solve": {},
        "page": page,
        "LIVE_DUMP": "probes/live_run.npz",
        "reload_page": lambda path: page,
        "apply_page": lambda loaded, dump: {"new_path": "runs/live_run.npz"},
        "ctx": _Holder(available=True, recompute_available=lambda: None),
        "handles": {},
        "_load_s_params_panel": lambda: None,
        "_load_far_field_panel": lambda: None,
        "_load_confidence_panel": lambda: None,
        "_is_vis": lambda info: False,
        "_rebuild_sheets": lambda: None,
        "_show": lambda frame, mode, site: None,
        "_push_still": lambda view, site: True,
        "_solve_refused_page": lambda nt, available: False,
        "_tick_solve_status": lambda job: None,
        "_SOLVE_LOG_STYLE": _constant("_SOLVE_LOG_STYLE"),
        "_SOLVE_LOG_HIDDEN": _constant("_SOLVE_LOG_HIDDEN"),
    }
    _exec_def("_solve_failure_hint", namespace)
    exec(compile(wrapper, "<poll>", "exec"), namespace)
    return namespace["_make"](), namespace


def test_a_missing_kernel_unhides_the_log_and_names_the_launch():
    """The panel the reader needs, and the ONE launch that explains it.

    A solve that dies on its first import is over in about two seconds, and
    the tick is every half second: the last tick can land before the death and
    leave the log hidden on the one screen that explains it. The verdict has
    to unhide it, and say which launch is being asked for.
    """
    poll, namespace = _poll()
    state = namespace["state"]
    namespace["solve"]["job"] = _DeadJob(
        EMFIT_LOG,
        returncode=1,
        status="failed",
        elapsed=3.0,
        lines=[
            "import emfit_core",
            "ModuleNotFoundError: No module named 'emfit_core'",
        ],
    )

    poll()

    assert state.solve_log == (
        "import emfit_core\n"
        "ModuleNotFoundError: No module named 'emfit_core'"
    ), (
        f"the card carries {state.solve_log!r}: the child's own words are the "
        "evidence for the hint under them, and the panel is where they live"
    )
    assert state.solve_log_style == _constant("_SOLVE_LOG_STYLE"), (
        f"the panel is still styled {state.solve_log_style!r} on a failed "
        "solve: the log exists in the state and nowhere on screen"
    )
    assert state.solve_status == (
        "solve failed after 3.0 s (rc=1) - the page on screen is still the "
        "previous dump\n"
        "hint: the child interpreter cannot import the compiled kernel: "
        "start the app with the venv site-packages on PYTHONPATH "
        "(PYTHONPATH=.:.venv/lib/python3.12/site-packages python3 "
        "server/poc_app.py), which RUN.md's PYTHONPATH=. alone does not do"
    ), (
        f"the verdict is {state.solve_status!r}: what failed is the child's "
        "own words, which launch fixes it is this build's to say"
    )


def test_a_refused_memory_ceiling_says_which_limit_was_asked_for():
    """The refusal names a box, not a model: the hint has to place it.

    The refusal is ONE physical line of ~180 characters, so the panel's
    160-character trim can cut the half that matters: the hint reads
    ``job.log``, the untrimmed tail, not the panel.
    """
    failure = _failure_branch()
    state = _Holder(
        solve_log="", solve_log_style=_constant("_SOLVE_LOG_HIDDEN")
    )

    failure(
        state,
        _DeadJob(
            MEM_LOG,
            returncode=2,
            status="crashed",
            elapsed=0.4,
            lines=[MEM_LOG.strip()],
        ),
        "crashed",
        "0.4",
    )

    assert state.solve_status == (
        "solve crashed after 0.4 s (rc=2) - the page on screen is still the "
        "previous dump\n"
        "hint: the requested memory ceiling is above the limit of the "
        "environment the app runs in, so the solver refuses before it starts"
    ), (
        f"the verdict is {state.solve_status!r}: a refusal that never started "
        "a solve is a fact about the environment, and the reader cannot see "
        "that in the child's own words"
    )
    assert state.solve_log == MEM_LOG.strip(), (
        f"the panel carries {state.solve_log!r}: the refusal's own line is "
        "the evidence for the hint"
    )
    assert state.solve_log_style == _constant("_SOLVE_LOG_STYLE"), (
        f"the panel is styled {state.solve_log_style!r} with a line to show"
    )


def test_an_unrecognised_failure_adds_no_hint():
    """No cause this build can name: the child's words and nothing else."""
    failure = _failure_branch()
    state = _Holder(solve_log="step 28\nstep 29\nTraceback (most recently)")

    failure(state, _CrashedJob(CRASH_LOG), "failed", "3.0")

    assert "\nhint:" not in state.solve_status, (
        "a hint was invented for an unrecognised crash: "
        f"{state.solve_status!r}"
    )
    assert state.solve_status == (
        "solve failed after 3.0 s (rc=2) - the page on screen is still the "
        "previous dump"
    ), f"the failure sentence changed shape: {state.solve_status!r}"


def test_a_solved_run_says_so_and_leaves_the_panel_alone():
    """The OK path is untouched: no hint line, no log written by the verdict."""
    poll, namespace = _poll()
    state = namespace["state"]
    namespace["solve"]["job"] = _DeadJob(
        "step 29\ndone\n", returncode=0, status="ok", elapsed=1.2
    )

    poll()

    assert state.solve_status == (
        "solved -> live_run.npz in 1.2 s; result loaded"
    ), (
        f"the success sentence is {state.solve_status!r}: a solved run must "
        "not grow a second line about a cause"
    )
    assert state.solve_log == "", (
        f"the success path wrote {state.solve_log!r} into the panel: the log "
        "belongs to what is running, and nothing is"
    )
    assert state.solve_log_style == _constant("_SOLVE_LOG_HIDDEN"), (
        f"the success path unhid the panel: {state.solve_log_style!r}"
    )


# =============================================================================
# The memory ceiling this environment can survive
# =============================================================================


def _ceiling():
    """``_solve_mem_ceiling_mb``, whose policy reads two module constants."""
    return _exec_def(
        "_solve_mem_ceiling_mb",
        {
            "_SOLVER_MEM_CEILING_MB_DEFAULT": _constant(
                "_SOLVER_MEM_CEILING_MB_DEFAULT"
            ),
            "_CEILING_MARGIN_MB": _constant("_CEILING_MARGIN_MB"),
        },
    )


def test_a_512_mb_container_gets_the_ceiling_the_certified_runs_used():
    """512 MB -> 500.0: the number the certified runs in one cgroup used.

    The solver's own default is 2000 MB, and the refusal at
    ``evidence/termination/run_build_A.py:3767-3772`` (exit 2) turns that
    default into a solve that never starts inside 512 MB.  The 12 MB margin
    is what keeps the cgroup's killer - which writes no marker and no
    artefact - from firing before the solver's own trip, which writes both
    and exits 3 (``run_build_A.py:452-453``).
    """
    ceiling = _ceiling()

    assert ceiling(512.0) == 500.0, (
        f"a 512 MB container gets {ceiling(512.0)!r}: every certified run "
        "made in one used 500.0 (evidence/termination/build_A_50ohm_cal.json)"
    )
    assert ceiling(512) == 500.0, (
        f"an int limit of 512 MB gets {ceiling(512)!r}: _cgroup_limit_mb "
        "divides in floats, but an int handed in must not fall to None"
    )


def test_a_container_with_no_visible_limit_gets_no_flag():
    """No cgroup limit: nothing to stay under, so the line is left alone."""
    ceiling = _ceiling()

    assert ceiling(None) is None, (
        f"an unbounded container gets {ceiling(None)!r}: there is no limit "
        "to stay under, so any number here would be one nobody measured"
    )


def test_a_limit_the_solver_would_not_refuse_leaves_the_line_alone():
    """At or above the solver's own default the bare line already works.

    The refusal is STRICT (``cg < args.mem_ceiling_mb``,
    ``run_build_A.py:3767``), so a limit equal to the 2000 MB default is not
    refused, and a flag there would rewrite a command line that works.
    """
    ceiling = _ceiling()
    default = _constant("_SOLVER_MEM_CEILING_MB_DEFAULT")

    for limit in (default, 4096.0):
        assert ceiling(limit) is None, (
            f"a {limit} MB container gets {ceiling(limit)!r}: the solver "
            f"does not refuse its {default:g} MB default there, so the flag "
            "would change a line that is already right"
        )


def test_a_limit_the_margin_would_swallow_gets_no_flag():
    """8 MB minus a 12 MB margin is below zero: silence beats nonsense.

    The solver's own refusal names the number it wanted; a negative ceiling
    would be a value no run could honour and no reader could act on.
    """
    ceiling = _ceiling()

    assert ceiling(8.0) is None, (
        f"an 8 MB container gets {ceiling(8.0)!r}: 8 - 12 is negative, and "
        "the solver's own refusal is a better answer than a negative ceiling"
    )


#: The trip's own words, verbatim from ``run_build_A.py:452-453`` (``_fire``,
#: exit 3): the marker's path is this build's own naming, kept to its shape.
TRIP_LOG = (
    "\nTRIP (memory): peak RSS 512.4 MB exceeded --mem-ceiling-mb 500.0 MB\n"
    "marker: /tmp/vis_run_B_20250101T000000_001.trip.json\n"
)

#: The pre-flight refusal, verbatim from ``run_build_A.py:1155-1160``
#: (exit 2): written before the first step of the march.
PREFLIGHT_LOG = (
    "MEM: estimated footprint ~1830.4 MB for 220x220x120 "
    "(5808000 cells, 40 volume frames) exceeds the safe limit 500.0 MB\n"
    "Error: Estimated memory exceeds safe limits. Reduce mesh density, "
    "volume_stride, or n_line.\n"
)


def test_a_tripped_ceiling_is_named_as_the_builds_own_ceiling():
    """A run the ceiling stopped is a fact about the study's size, not a bug.

    ``_fire`` (``run_build_A.py:443-455``) writes a marker and exits 3, so
    there is no traceback and nothing that reads like a crash: without this
    sentence the card shows a log and a return code and stops.
    """
    hint = _exec_def("_solve_failure_hint", {})

    text = hint(TRIP_LOG)
    assert text, (
        "the trip's own line reached the card with no hint: the reader is "
        f"shown {TRIP_LOG!r} and left to guess what stopped the run"
    )
    assert "--mem-ceiling-mb" in text and "exit 3" in text, (
        f"the trip hint is {text!r}: it has to name the flag and the exit "
        "status the child used, or the reader cannot check it against the log"
    )
    assert "traceback" not in text.lower(), (
        f"the trip hint is {text!r}: a trip is a ceiling that fired, not a "
        "crash, and calling it one sends the reader after the wrong cause"
    )


def test_the_preflight_refusal_is_named_and_is_not_the_trip():
    """A solve refused BEFORE its first step says something else.

    ``run_build_A.py:1155-1160`` exits 2 without building a mesh, so the
    reader's next move is a smaller study rather than a bigger container; the
    two hints must differ, or the card would say one thing about a run that
    never started and one that was stopped mid-march.
    """
    hint = _exec_def("_solve_failure_hint", {})

    text = hint(PREFLIGHT_LOG)
    assert text, (
        "the pre-flight refusal reached the card with no hint: "
        f"{PREFLIGHT_LOG!r}"
    )
    assert "exit 2" in text, (
        f"the pre-flight hint is {text!r}: the child exited 2 there "
        "(run_build_A.py:1155-1160), and that code is what ties the sentence "
        "to this refusal rather than to the trip's"
    )
    assert text != hint(TRIP_LOG), (
        f"both causes produce {text!r}: a run stopped mid-march and a run "
        "that never started need different advice, and now share one sentence"
    )
