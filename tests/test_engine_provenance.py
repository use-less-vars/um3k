"""Engine provenance: which step engine produced a number, written and read back.

The gap this closes
-------------------
``emfit.evolve`` dispatches ``FITStepper.step`` to the compiled kernel when the
extension is importable and reports this module's ABI, and to the Python
reference otherwise (``emfit/evolve.py:154`` ``_load_kernel``, ``:172-173``
``_KERNEL``/``_ACTIVE_STEP``).  The two agree in value -- that is what
``tests/test_cpp_parity.py`` and ``tests/test_cpp_dispatch.py`` pin -- so a
banked artefact could say which HOST produced it (``meta.python``,
``meta.platform``) and not which ARITHMETIC did.  Those are different facts:
one is a performance fact about the machine, the other a provenance fact about
the number.

What these tests pin
--------------------
* ``emfit.evolve.engine_report()`` names the engine from the module global
  *at call time*: a swapped ``_KERNEL`` changes the answer on the next call, so
  the report cannot go stale behind a default argument;
* a real artefact write carries it.  ``tools/host_ladder.py``'s payload is used
  because it is the one writer that can be driven end to end without an FDTD
  run: only ``run_rung`` is monkeypatched (the same harness
  ``tests/test_host_ladder_partial.py`` uses), the rung raises, and the file
  that lands on disk is the tool's own partial payload -- a real ``json.dump``
  of a real ``meta``, not a rebuilt dict;
* the value written is the live one, not a literal: with ``_KERNEL`` patched to
  ``None`` the same write says ``"python"``;
* ``evidence/termination/grade_2b.py`` reads an ABSENT key as
  ``"unknown (pre-6cbb89d)"`` and never as ``"python"`` -- a banked artefact
  predates the key, and "nobody recorded it" is not "the Python path ran".

* ``meta.n_threads_env_requested`` and ``meta.n_threads_env`` are two facts,
  not one: the REQUEST the operator made at process start and the EFFECT the
  process ran with (``emfit/_env.py`` captures ``OMP_NUM_THREADS`` in its module
  body, before ``pin_threads`` overwrites it in place).  The capture is taken
  once per interpreter, so those cases are pinned in fresh child processes.

No FDTD run and no modal solve happens anywhere in this file.  ``run_build_A``'s
``--dry-run`` is exercised because it builds the same ``meta`` dict that both of
its artefacts then copy, and it is cheap by construction (no solve, no file).
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import emfit.evolve as evolve
import tools.host_ladder as host_ladder

REPO = Path(__file__).resolve().parents[1]
TERMINATION = REPO / "evidence" / "termination"

_MODULES: dict = {}


def _load_by_path(name, path):
    """Import a standalone script that is not part of a package."""
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


def _module(name, path):
    """``_load_by_path`` with the import paid once per session."""
    if name not in _MODULES:
        _MODULES[name] = _load_by_path(name, path)
    return _MODULES[name]


class _Kernel:
    """The one attribute ``engine_report()`` reads off a kernel, and nothing else.

    A stand-in, not a fake: the report is about *which* kernel object the module
    holds and what ABI it announces, and this pins both without depending on
    whether ``emfit_core`` happens to be built in the environment running the
    suite.
    """

    KERNEL_ABI = 1


def _ladder_payload(monkeypatch, tmp_path, out_name="ladder.json"):
    """Drive ``host_ladder.main`` to a written payload with no solver running.

    ``run_rung`` raises on the first rung, which is the partial-JSON path: the
    payload is written anyway (``tests/test_host_ladder_partial.py``), and its
    ``meta`` is built on the same lines as a complete run's -- so the provenance
    checked below is the provenance every ladder file carries.
    """

    def fake_run_rung(h_mm, args, rss_branch):
        raise host_ladder.LadderError("no solver in this test: nothing is measured")

    monkeypatch.setattr(host_ladder, "run_rung", fake_run_rung)
    out = tmp_path / out_name
    rc = host_ladder.main(["--max-rungs", "2", "--json", str(out)])
    assert rc == 1, "the aborted ladder must still exit 1"
    assert out.exists(), "the aborted ladder wrote no payload at all"
    return json.loads(out.read_text(encoding="utf-8"))


def test_engine_report_names_the_compiled_kernel(monkeypatch):
    """With a kernel in hand the report says which one, ABI included."""
    monkeypatch.setattr(evolve, "_KERNEL", _Kernel())
    assert evolve.engine_report() == {
        "step_engine": "cpp",
        "kernel_abi": 1,
        "kernel_name": "emfit_core.fit_leapfrog",
    }


def test_engine_report_says_python_when_no_kernel_is_loaded(monkeypatch):
    """No kernel is a report about arithmetic, not an error: ``"python"``, no ABI."""
    monkeypatch.setattr(evolve, "_KERNEL", None)
    assert evolve.engine_report() == {
        "step_engine": "python",
        "kernel_abi": None,
        "kernel_name": None,
    }


def test_engine_report_rereads_the_module_global_on_every_call(monkeypatch):
    """The report follows ``_KERNEL`` live -- it is never captured at import.

    ``FITStepper.step`` reads the same global when it dispatches
    (``emfit/evolve.py`` ``step``), so a report captured in a default argument
    would be able to disagree with the path the stepper actually took.  Swapping
    the global twice here is what proves it does not.
    """
    monkeypatch.setattr(evolve, "_KERNEL", _Kernel())
    assert evolve.engine_report()["step_engine"] == "cpp"
    monkeypatch.setattr(evolve, "_KERNEL", None)
    assert evolve.engine_report()["step_engine"] == "python"
    monkeypatch.setattr(evolve, "_KERNEL", _Kernel())
    assert evolve.engine_report()["step_engine"] == "cpp"


def test_the_ladder_payload_carries_the_step_engine(monkeypatch, tmp_path):
    """A real written artefact names the engine, matching the live module state."""
    meta = _ladder_payload(monkeypatch, tmp_path)["meta"]
    report = evolve.engine_report()
    assert meta["step_engine"] == report["step_engine"], (
        f"payload says {meta['step_engine']!r}, module says "
        f"{report['step_engine']!r}")
    assert meta["step_engine"] == evolve._ACTIVE_STEP, (
        "the written provenance must be the engine this process is running")
    assert meta["step_engine"] in ("cpp", "python")
    assert meta["kernel_abi"] == report["kernel_abi"]
    assert meta["kernel_name"] == report["kernel_name"]


def test_the_written_engine_follows_a_swapped_kernel(monkeypatch, tmp_path):
    """The key is a measurement, not a literal: remove the kernel, get "python"."""
    monkeypatch.setattr(evolve, "_KERNEL", None)
    meta = _ladder_payload(monkeypatch, tmp_path, out_name="ladder_python.json")[
        "meta"]
    assert meta["step_engine"] == "python"
    assert meta["kernel_abi"] is None, "the Python path has no ABI to name"
    assert meta["kernel_name"] is None


def test_run_build_a_dry_run_meta_carries_the_step_engine(monkeypatch, capsys):
    """``meta`` is one dict for the twin record, the artefact and the dry run.

    The dry run prints it instead of writing it (no FDTD, no file), which makes
    it the cheap way to see the dict the two artefact writers copy.
    """
    run_build_A = _module("run_build_A_under_test",
                          TERMINATION / "run_build_A.py")
    assert run_build_A.main(["--dry-run"]) == 0
    text = capsys.readouterr().out
    dry = json.loads(text[text.index("{\n"):])
    assert dry["meta"]["step_engine"] == evolve._ACTIVE_STEP
    assert dry["meta"]["kernel_abi"] == evolve.engine_report()["kernel_abi"]


def test_the_grader_reports_a_missing_engine_as_unknown_not_python(tmp_path):
    """Absence is reported as absence.  ``"python"`` would be an invented claim.

    Both documents here are deliberately too thin to score (hence exit 1 and a
    ``problems`` list); the graded ``inputs`` block is built before any of that,
    and it is what carries the engine into the graded record.
    """
    grade_2b = _module("grade_2b_under_test", TERMINATION / "grade_2b.py")
    assert grade_2b.STEP_ENGINE_UNKNOWN == "unknown (pre-6cbb89d)"
    assert grade_2b.STEP_ENGINE_UNKNOWN != "python"

    wrote_it = tmp_path / "with_key.json"
    wrote_it.write_text(json.dumps(
        {"meta": {"label": "with-key", "step_engine": "cpp"}, "run": {}}),
        encoding="utf-8")
    predates_it = tmp_path / "without_key.json"
    predates_it.write_text(json.dumps(
        {"meta": {"label": "without-key"}, "run": {}}), encoding="utf-8")

    out = tmp_path / "graded.json"
    grade_2b.main([str(wrote_it), str(predates_it), "--out", str(out)])

    assert out.exists(), "the graded document was not written"
    inputs = json.loads(out.read_text(encoding="utf-8"))["inputs"]
    assert inputs["with-key"]["step_engine"] == "cpp", (
        "a present key must be carried through verbatim")
    assert inputs["without-key"]["step_engine"] == "unknown (pre-6cbb89d)"
    assert inputs["without-key"]["step_engine"] != "python"


# ---------------------------------------------------------------------------
# Thread provenance: what was REQUESTED and what was EFFECTIVE are two facts.
# ---------------------------------------------------------------------------
_CHILD_CAPTURE = """
import json
import os

import emfit                       # emfit/__init__.py runs pin_threads() here
from emfit._env import requested_omp_threads

print(json.dumps({
    "requested": requested_omp_threads(),
    "effective": os.environ.get("OMP_NUM_THREADS"),
}))
"""


def _child_provenance(omp):
    """Run the capture/overwrite pair in a NEW interpreter; return both facts.

    The capture happens once, in ``emfit._env``'s module body, so these cases
    cannot be produced by monkeypatching ``os.environ`` in this already-imported
    interpreter -- by then the capture has been taken and cannot be retaken.
    Each case therefore gets its own process with a controlled environment, and
    a crashed child is a failure with its output attached, never a skip.
    """
    env = {k: v for k, v in os.environ.items() if k != "OMP_NUM_THREADS"}
    if omp is not None:
        env["OMP_NUM_THREADS"] = omp
    proc = subprocess.run([sys.executable, "-c", _CHILD_CAPTURE], env=env,
                          cwd=str(REPO), capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"child interpreter failed (rc={proc.returncode}, "
        f"OMP_NUM_THREADS={omp!r})\nstdout:\n{proc.stdout}\nstderr:\n"
        f"{proc.stderr}")
    data = json.loads(proc.stdout)
    assert set(data) == {"requested", "effective"}, proc.stdout
    return data


def test_absent_omp_num_threads_is_requested_none_effective_one():
    """The pair, in one process: nothing was asked for, one thread was used."""
    data = _child_provenance(None)
    assert data["requested"] is None, (
        "an absent variable must read None, not '1': '1' would be an invented "
        "request that the operator never made")
    assert data["effective"] == "1", (
        "pin_threads must have written '1' into the environment")


def test_requested_twelve_survives_the_import_verbatim():
    """An operator who asked for 12 is recorded as 12, and is not overridden."""
    data = _child_provenance("12")
    assert data["requested"] == "12"
    assert data["effective"] == "12", (
        "pin_threads must leave a variable the operator set alone")


def test_explicit_one_is_the_case_that_used_to_be_ambiguous():
    """``OMP_NUM_THREADS=1`` asked for, against the absent case.

    Both read ``'1'`` out of ``os.environ`` once the import has run, which is
    exactly the ambiguity the requested/effective pair removes.  What tells them
    apart now is ``requested``: ``'1'`` here, ``None`` above.
    """
    data = _child_provenance("1")
    assert data["requested"] == "1"
    assert data["effective"] == "1"


_DRY_RUN = [sys.executable, str(TERMINATION / "run_build_A.py"), "--dry-run"]
"""The writer's cheap path, invoked the way its ``__main__`` guard invokes it."""


def _writer_meta(omp):
    """Run ``run_build_A --dry-run`` in a CHILD process; return its ``meta``.

    In THIS process the check would prove nothing.  ``requested_omp_threads()``
    here reads the capture taken when this interpreter imported ``emfit``, so it
    is the same value the writer would have recorded whether or not the writer
    ever asked for it: with nothing requested, both sides are ``None`` and an
    unwired ``n_threads_env_requested = None`` would pass.  Only a child whose
    ``OMP_NUM_THREADS`` this test owns separates "recorded what was asked" from
    "recorded nothing".

    Fail-closed: a child that crashes is a failure with its output attached.
    """
    env = {k: v for k, v in os.environ.items() if k != "OMP_NUM_THREADS"}
    if omp is not None:
        env["OMP_NUM_THREADS"] = omp
    proc = subprocess.run(_DRY_RUN, env=env, cwd=str(REPO),
                          capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"child dry-run failed (rc={proc.returncode}, "
        f"OMP_NUM_THREADS={omp!r})\nstdout:\n{proc.stdout}\nstderr:\n"
        f"{proc.stderr}")
    text = proc.stdout
    return json.loads(text[text.index("{\n"):])["meta"]


def test_the_writer_records_the_request_beside_the_effective_value():
    """``meta`` carries both keys, and they differ when nothing was requested."""
    absent = _writer_meta(None)
    assert "n_threads_env" in absent, "the effective key must not be renamed"
    assert "n_threads_env_requested" in absent
    assert absent["n_threads_env_requested"] is None, (
        "nothing was requested, so the request must record None -- never the "
        "'1' that pin_threads wrote into the environment")
    assert absent["n_threads_env"] == "1", (
        "pin_threads must have made the EFFECTIVE value '1'")

    twelve = _writer_meta("12")
    assert twelve["n_threads_env_requested"] == "12", (
        "a request the operator did make must be recorded verbatim")
    assert twelve["n_threads_env"] == "12", (
        "pin_threads must leave a variable the operator set alone")

