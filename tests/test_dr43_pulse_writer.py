"""DR-43, pinned on the shipped entry point: a pulse run publishes no |S21|.

``evidence/termination/run_build_A.py`` is the writer every artefact in
``evidence/termination/`` came out of, and the defect DR-43 records lived in it:
with ``s21_plane`` unnamed -- the default for every pulse run -- there is no
single-plane transmission to report, and the writer used to publish the
station-span fallback (``emfit/studies.py:4137-4153``, a ratio of
``forward_wave_amplitude`` at the first and last probe) as ``s21.magnitude``,
which the passivity gate then summed against an |S11| from a different
estimator.  A passive 50 ohm termination was graded non-passive that way.

The unit-level reverts in ``tests/test_writer_station_phasors.py`` pin the guard
by disabling it and watching one test fail.  That file never runs the CLI.  This
one does: it drives ``evidence/termination/run_build_A.py`` exactly as an
operator would, with the default (plane-less) pulse path, and reads the record it
writes.  What is protected, in one line each:

    * the eight numeric ``s21`` keys are PRESENT and ``None`` -- present, so a
      reader cannot mistake a dropped key for a measured zero, and the key set
      is the same one a measured record carries;
    * ``s21.measured`` is ``False`` and ``s21.provenance`` is ``None``, which is
      the licence the writer publishes under;
    * ``s21.unmeasured_reason`` states the refusal in words and names the
      fallback it declined to publish, so the file says why it has no number
      instead of leaving a null to be read as "not computed yet";
    * ``s11.passivity`` reports ``NOT_ASSESSABLE`` with a null ``power_sum`` at
      ``PASSIVITY_TOL`` -- a skipped check that says it skipped, not a ``pass``;
    * there is no top-level ``power_sum`` key at all, so a reader that tests for
      the null lands on the block that explains it;
    * the ``--vis-dump`` archive is written beside it, because DR-43's default
      path is the one the visualisation stub also runs on.

The run is a real 2400-step 3-D solve.  It costs about a minute on this host
(50.6 s wall on the reference run, 378.4 MB peak RSS), which is why it is
``slow`` and NOT part of the fast gate -- the fast gate stays the 23 cheap tests
``README.md`` names.  Deselect with ``-m 'not slow'``.

Why 2400 steps: it is the writer's own default (``--nsteps`` ``default=2400``,
``evidence/termination/run_build_A.py:3123``) and the length row 1 of the DR-43
table was measured at -- ``artifacts/passivity_sweep_A2.json`` ``runs[0]``: nsteps
2400, pulse, no ``s21_plane``, |S11| 0.327238, |S21| 1.021737, ``power_sum``
1.151030784, ``FAIL_PASSIVITY`` (``docs/design/defect_register.md:838``).  Not a
threshold: the same sweep's 1200-step run fails too (``:840``).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "evidence" / "termination" / "run_build_A.py"


def _load_run_build_a():
    """Import ``evidence/termination/run_build_A.py`` by path, as a module.

    The house loader (``tests/test_extraction_plane_default.py:37-44``): the
    driver is a script, not a package member, and loading it by path reads the
    driver's OWN ``MEM_CEILING_MB_DEFAULT`` and ``cgroup_limit_mb`` (:157)
    instead of re-implementing either here -- a duplicated cgroup probe can
    disagree with the code under test.  Cheap: the module's top-level imports
    are standard library only, and ``if __name__ == "__main__":`` keeps
    ``main()`` from running on import.
    """
    evidence = SCRIPT.parent
    if str(evidence) not in sys.path:
        sys.path.insert(0, str(evidence))
    spec = importlib.util.spec_from_file_location("run_build_A", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("run_build_A", module)
    spec.loader.exec_module(module)
    return module


RUN_BUILD_A = _load_run_build_a()

# The eight keys ``published_s21_block`` writes as null rather than dropping
# (``evidence/termination/run_build_A.py:2284``, ``:2302``).
S21_NUMERIC_KEYS = (
    "magnitude", "phase_rad", "phase_deg", "real", "imag",
    "raw_magnitude", "raw_phase_rad", "raw_phase_deg",
)
PASSIVITY_TOL = 4.0e-9
PASSIVITY_NOT_ASSESSABLE = "NOT_ASSESSABLE"
NSTEPS = 2400
# Generous: the reference run is 50.6 s and this container is shared.  The
# pytest-wide timeout (pyproject.toml, 300 s) still bounds the test itself.
CLI_TIMEOUT_S = 900


def _env_with_repo_on_path() -> dict:
    """Inherit the environment, with the repo root first on ``PYTHONPATH``.

    The subprocess is a plain ``sys.executable`` run, so it must see ``emfit``
    by the same rule the test process does.  Prepending the root (instead of
    replacing) keeps whatever the caller set -- an editable install or a venv's
    site-packages -- intact.
    """
    env = os.environ.copy()
    parts = [str(REPO_ROOT)]
    parts += [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


@pytest.mark.slow
def test_a_pulse_run_names_no_plane_so_nothing_is_published(tmp_path):
    """A plane-less pulse run writes nulls that say so, and no verdict."""
    # WHY A SKIP AND NOT A LOWER --mem-ceiling-mb.  Dropping the flag to fit this
    # box would tune the test to the box: the run would then be asserted to
    # SURVIVE a trip set below the container's own limit, i.e. it would pin a
    # 2400-step 3-D solve on a few hundred MB of headroom that this mesh may
    # legitimately exceed -- replacing one environment-dependent red with a
    # flaky one.  REJECTED ALTERNATIVE: pass ``--mem-ceiling-mb`` below the
    # container limit (e.g. 400) so the guard lets the run through.  The flag is
    # not what this file tests (a pulse run names no plane), so the refusal is
    # reported, measured, and skipped rather than worked around.
    limit_mb = RUN_BUILD_A.cgroup_limit_mb()
    if limit_mb is not None and limit_mb < RUN_BUILD_A.MEM_CEILING_MB_DEFAULT:
        pytest.skip(
            f"this container's memory limit is {limit_mb:.1f} MB, below the "
            f"default --mem-ceiling-mb {RUN_BUILD_A.MEM_CEILING_MB_DEFAULT:.1f}, "
            "so the trip-vs-container guard (run_build_A.py:3766) refuses the "
            "run before it starts; the refusal is correct behaviour and cannot "
            "be tested around without changing the flag it is testing")
    out_json = tmp_path / "dr43_pulse.json"
    out_npz = tmp_path / "dr43_pulse.npz"

    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--structure", "C",
         "--nsteps", str(NSTEPS),
         "--out", str(out_json),
         "--vis-dump", str(out_npz)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_S,
        env=_env_with_repo_on_path(),
    )
    assert proc.returncode == 0, (
        f"run_build_A.py exited {proc.returncode}\n"
        f"stdout:\n{proc.stdout[-4000:]}\nstderr:\n{proc.stderr[-4000:]}")

    # --out is mandatory with --vis-dump, so both files must exist and be
    # non-empty; a refusal that wrote the archive but no record would be a
    # half-published run.
    assert out_json.is_file(), proc.stdout[-2000:]
    # Parsed with json's default hooks, i.e. a bare ``NaN`` is tolerated.  This
    # is deliberate and it is a finding, not an oversight: on the plane-less
    # path the record's ``gamma_plane`` block is written as ``NaN``
    # (``abs``/``arg_deg``/``re``/``im``) because a plane's reflection is not
    # defined when no plane is named, and that key set has no null convention
    # yet.  That is not DR-43's block and is not pinned here; what this file
    # pins is that ``s21`` uses nulls where ``gamma_plane`` uses NaN.
    record = json.loads(out_json.read_text(encoding="utf-8"))

    s21 = record["s21"]
    for key in S21_NUMERIC_KEYS:
        assert key in s21, (
            f"s21 key {key!r} was dropped instead of written as null; the key "
            "set must be identical on a measured and an unmeasured record")
        assert s21[key] is None, (
            f"s21.{key} = {s21[key]!r} on a record with no cut plane: DR-43 "
            "publishes a transmission only when an estimator names its plane")

    assert s21["measured"] is False
    assert s21["provenance"] is None
    reason = s21["unmeasured_reason"]
    assert isinstance(reason, str) and reason.strip(), (
        "an unmeasured |S21| must state its refusal, not leave a bare null")
    assert reason.startswith("unmeasured:"), reason
    assert "emfit/studies.py:4137-4153" in reason, (
        "the refusal must name the station-span fallback it declined to "
        f"publish; got: {reason}")
    assert "DR-43" in reason, reason

    passivity = record["s11"]["passivity"]
    assert passivity["status"] == PASSIVITY_NOT_ASSESSABLE
    assert passivity["power_sum"] is None, (
        "a sum of |S11|^2 + |S21|^2 was quoted for a record with no published "
        "|S21| -- that is the defect, not a number")
    assert passivity["tolerance"] == PASSIVITY_TOL
    assert "power_sum" not in record, (
        "a top-level power_sum appeared; the null must live at "
        "s11.passivity.power_sum, beside the words that explain it")

    # The plane's absence is the cause, so say so from the record itself.
    assert s21["plane_policy"] == "default"
    assert s21.get("s21_plane_requested") is None

    # The visualisation archive: written, openable, and this run's length.
    assert out_npz.is_file(), proc.stdout[-2000:]
    assert out_npz.stat().st_size > 1_000_000, out_npz.stat().st_size
    with np.load(out_npz) as dump:
        assert int(dump["nsteps"]) == NSTEPS
        assert dump["ez_ycut"].ndim == 3

    # argv is kept on the record, so the flags above are checkable from it.
    argv = record["meta"]["argv"]
    assert "--vis-dump" in argv and str(out_npz) in argv
