"""SolveJob's output pipe: the reader thread that keeps it empty.

THE BUG THESE TESTS ARE ABOUT
-----------------------------
SolveJob spawns the solver with ``stdout=subprocess.PIPE, stderr=STDOUT``.
An operating-system pipe holds only ~64 KiB (65536 bytes on Linux). A child
that prints more than that cannot go on printing until somebody reads what is
already in the pipe: it blocks inside ``write()`` and never exits - so the
worker's ``wait()`` never returns either, and the solve appears to hang at
whatever the child printed last. The fix is the daemon reader thread in
``SolveJob._read_loop``: it drains the pipe for as long as the child lives,
which both unblocks the child and turns the tail into a LIVE log instead of a
thing that exists and is never shown.

WHY THE CLASS IS EXTRACTED INSTEAD OF IMPORTED
----------------------------------------------
``server/poc_app.py`` is a ~20k-line trame app: importing it pulls in the
whole plotting and UI stack. Nothing in SolveJob needs any of that - the class
uses only ``subprocess``, ``threading``, ``collections.deque``, ``sys``,
``time`` and the module constant ``SOLVER_SCRIPT``. So these tests take the
class's OWN source out of the file with ``ast`` and ``exec`` it against
exactly those names. What is under test is the code in the repository, byte
for byte, at the price of a parse instead of an import.

``cwd`` is always passed explicitly: left to its default, the job would use
the solver's own directory, which a test has no business depending on.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "server" / "poc_app.py"

#: The child the tests drive. It prints ~1.6 MB - 20000 lines of 79 'C's plus
#: one short line at the end - which is about 25x the ~64 KiB a pipe holds, so
#: a job that does not read while the child runs cannot get past the buffer.
CHATTER = """\
import sys
for _ in range(20000):
    print('C' * 79)
print('LAST')
sys.stdout.flush()
"""

ARGV = [sys.executable, "-c", CHATTER]
CWD = str(REPO_ROOT)


def _solve_job_class():
    """SolveJob, lifted out of server/poc_app.py without importing the app."""
    text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SolveJob":
            segment = ast.get_source_segment(text, node)
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


def test_reader_drains_the_pipe_and_the_run_finishes():
    """The happy path: a child that floods the pipe still finishes, and its
    last line is in the tail - i.e. the reader drained while the child ran."""
    SolveJob = _solve_job_class()
    job = SolveJob(ARGV, cwd=CWD)

    started = time.monotonic()
    status = job.run()
    elapsed = time.monotonic() - started

    assert status == "ok", (
        f"the child printed ~1.6 MB and exited 0, but run() returned {status!r} "
        f"after {elapsed:.2f} s"
    )
    assert elapsed < 60.0, (
        f"run() took {elapsed:.1f} s. The child's output was not read while it "
        "ran, so it blocked in write() against a full pipe and only got going "
        "again once something drained the pipe."
    )
    assert job.last_line == "LAST", (
        f"last_line is {job.last_line!r}, not 'LAST': the reader did not keep "
        "the END of the child's output"
    )
    assert len(job._tail) <= SolveJob.LOG_TAIL_LINES, (
        f"the tail holds {len(job._tail)} lines but is bounded to "
        f"{SolveJob.LOG_TAIL_LINES}"
    )
    assert isinstance(job.elapsed_seconds, float) and job.elapsed_seconds >= 0.0, (
        f"elapsed_seconds is {job.elapsed_seconds!r} on a job that ran"
    )
    # rstrip because the child's last line ends with a newline: the check is
    # about the LAST LINE of the log, not about the trailing byte.
    assert job.log.rstrip().endswith("LAST"), (
        f"log does not end with the child's last line; it ends "
        f"{job.log[-120:]!r}"
    )


def test_unread_pipe_blocks_the_same_child_forever():
    """The bug, made visible: with nothing reading the pipe, that same child is
    still 'running' after 5 s - while the read version of it finishes in a
    fraction of that. The disagreement IS the proof."""
    SolveJob = _solve_job_class()

    class Unread(SolveJob):
        """The pre-fix job: nothing drains the pipe while the child runs."""

        def _read_loop(self) -> None:
            return

    job = Unread(ARGV, cwd=CWD)
    try:
        job.start()
        time.sleep(5.0)
        observed = job.poll()
        code = job.returncode
    finally:
        proc = getattr(job, "_proc", None)
        if proc is not None:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001 - a dead handle is fine here
                pass
            try:
                proc.wait(timeout=10)
            except Exception:  # noqa: BLE001 - do not mask the assertion
                pass

    assert observed == "running", (
        f"with the pipe unread the child was expected to still be running "
        f"after 5.0 s, but poll() said {observed!r} (returncode {code!r})"
    )
    assert code is None, (
        f"with the pipe unread the child could not have exited, yet it has "
        f"returncode {code!r}"
    )

    read_job = SolveJob(ARGV, cwd=CWD)
    started = time.monotonic()
    status = read_job.run()
    read_elapsed = time.monotonic() - started

    assert status == "ok" and read_elapsed < 5.0, (
        "THE DISAGREEMENT that is the proof: the SAME child that was still "
        f"'running' after 5.0 s with its pipe unread finished with status "
        f"{status!r} in {read_elapsed:.2f} s once the reader drained the pipe"
    )


def test_status_is_live_while_the_child_runs():
    """start()/poll() - the path the server's watcher uses - must let a child
    that floods the pipe run to completion, and must report a moving clock
    while it does."""
    SolveJob = _solve_job_class()
    job = SolveJob(ARGV, cwd=CWD)
    job.start()

    lines: list[str] = []
    elapsed_seen: list[float] = []
    status = job.status
    deadline = time.monotonic() + 30.0
    try:
        while status in ("idle", "running"):
            if time.monotonic() > deadline:
                raise AssertionError(
                    "the child never finished within 30 s: its pipe was not "
                    "read while it ran, so it blocked in write() and could not "
                    "exit - this is the start()/poll() path the solve watcher "
                    "uses, where nothing is draining the pipe"
                )
            line = job.last_line
            if line:
                lines.append(line)
            elapsed_seen.append(job.elapsed_seconds)
            time.sleep(0.01)
            status = job.poll()
    finally:
        if job.status == "running":
            try:
                job._proc.kill()
            except Exception:  # noqa: BLE001 - a dead handle is fine here
                pass

    assert job.status == "ok", (
        f"the child exited 0 but the job is {job.status!r} "
        f"(returncode {job.returncode!r})"
    )
    assert lines, (
        "last_line was empty on every poll: the tail was not being filled "
        "while the child ran, so there is no live log to show"
    )
    assert max(elapsed_seen) > min(elapsed_seen), (
        f"elapsed_seconds never moved while the child ran: every sample was "
        f"{elapsed_seen[0]!r}, so the status text cannot show a live clock"
    )
