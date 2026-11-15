"""Pure proof that ``load_multifreq`` refuses ANOTHER arm's summary file.

``load_multifreq`` reaches a sweep file through two doors.  The beside-the-dump
glob is already filtered by arm (``_multifreq_candidates`` keeps only names
carrying ``_<arm>_``), but ``MULTIFREQ_BY_STRUCTURE`` is a registry of LITERAL
paths keyed by arm - so an entry that points at the other arm's summary is a
file the scan could never have chosen and that nothing else would question.  If
it were believed, the |S11|/|S21| panel would plot B's numbers under A's name,
which is the one thing an artefact panel may not do.  The guard is the last
check before the file is parsed, and these tests assert its OBSERVABLE effect:
the call returns no sweep, and stderr says why, in those words.

Nothing here boots a server.  ``load_multifreq`` is called directly with the
registry monkeypatched and the files in ``tmp_path``: no trame, no plotter, no
network, no sleeps, no child processes.  The dump file itself is never opened on
this path (the SUMMARY is), but it is written so the directory the beside-dump
scan reads is a real one, and so the only door that can reach these summaries is
the registry under test.

Two tests, one pair of fixtures: the wrong-arm file is REFUSED, and the same
setup DOES load when the filename carries the arm the dump claims - so neither
result can be an artefact of the files simply being unreadable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries the rest of this suite adds, so `import poc_app`
        # resolves from server/poc_app.py
        sys.path.insert(0, _p)

# In this image pyvista/trame/vtk live in the repo's own venv (its bin/python is
# broken, the site-packages tree is not).  On a host where they are installed
# normally this directory is either absent or already on sys.path, so the block
# is inert there.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

import poc_app as app  # noqa: E402


def _write_sweep(path: Path, rows) -> Path:
    """A sweep summary with one synthetic row per ``(f_ghz, s11, s21)``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dossier": "poc-multifreq-arm-guard-test",
        "generated_utc": "2026-01-01T00:00:00Z",
        "bin_spacing_mhz": 500.0,
        "rows": [
            {
                "artefact": f"{path.stem}_k{k}.json",
                "f_ghz_used": f_ghz,
                "s11.magnitude": s11,
                "s21.magnitude": s21,
                "k": k,
                "beta_ambiguous": False,
                "errors": [],
            }
            for k, (f_ghz, s11, s21) in enumerate(rows)
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _dump(tmp_path: Path) -> Path:
    """A dump whose own directory carries NO summary - the scan finds nothing."""
    dump = tmp_path / "dumps" / "dump.npz"
    dump.parent.mkdir(parents=True, exist_ok=True)
    dump.write_bytes(b"")
    return dump


def test_another_arms_summary_is_refused(tmp_path, monkeypatch, capsys):
    """Arm A is offered B's readable, valid sweep: it must not be drawn."""
    dump = _dump(tmp_path)
    b_summary = _write_sweep(
        tmp_path / "sweeps" / "build_B_100ohm_multifreq_summary.json",
        [(4.0, 0.48, 0.53), (5.0, 0.47, 0.52), (6.0, 0.46, 0.51)],
    )
    assert b_summary.is_file(), "fixture: the offered summary has to be readable"
    # The registry, and only the registry, can reach this file: it does not sit
    # beside the dump, and the beside-dump scan would drop it by arm anyway.
    monkeypatch.setattr(app, "MULTIFREQ_BY_STRUCTURE", {"A": str(b_summary)})
    monkeypatch.setattr(app, "SINGLE_RUN_BY_STRUCTURE", {})

    result = app.load_multifreq(dump, "A")

    err = capsys.readouterr().err
    assert result is None, (
        "load_multifreq returned a sweep for arm A out of "
        f"{b_summary.name}: the wrong-arm guard did not fire "
        f"(returned path: {result.get('path') if result else None})"
    )
    assert "is not named for structure arm A" in err, (
        "the refusal has to say WHY in the log, not merely return None; "
        f"stderr was: {err!r}"
    )
    assert b_summary.name in err, (
        f"the refusal has to name the file it refused; stderr was: {err!r}"
    )


def test_the_named_arms_summary_still_loads(tmp_path, monkeypatch, capsys):
    """Positive control: the same fixtures load when the name carries the arm."""
    dump = _dump(tmp_path)
    a_summary = _write_sweep(
        tmp_path / "sweeps" / "build_A_50ohm_multifreq_summary.json",
        [(4.0, 0.48, 0.53), (5.0, 0.47, 0.52)],
    )
    monkeypatch.setattr(app, "MULTIFREQ_BY_STRUCTURE", {"A": str(a_summary)})
    monkeypatch.setattr(app, "SINGLE_RUN_BY_STRUCTURE", {})

    result = app.load_multifreq(dump, "A")

    err = capsys.readouterr().err
    assert result is not None, (
        "the guard refused an arm A summary named for arm A; "
        f"stderr was: {err!r}"
    )
    assert result["path"] == a_summary
    assert result["single_point"] is False
    assert [point["f_ghz"] for point in result["points"]] == [4.0, 5.0]
    assert "is not named for structure arm" not in err, err
