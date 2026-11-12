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

No FDTD run and no modal solve happens anywhere in this file.  ``run_build_A``'s
``--dry-run`` is exercised because it builds the same ``meta`` dict that both of
its artefacts then copy, and it is cheap by construction (no solve, no file).
"""

import importlib.util
import json
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
