"""``emfit.config.RunConfig`` and the ``--config`` wiring of
``scripts/run_reference_sim.py``.

WHAT THIS PINS.  A configuration file is only worth having if it CHANGES the
run, so the interesting assertions here are not the round trip (that is easy and
boring) but the ones that say the numbers in the file reach the plan that gets
priced: ``nsteps`` moves the step count, ``dump_stride`` the plane stride,
``volume_stride``/``volume_frames`` the volume's frame count, ``n_line`` the
mesh's cell count, ``pulse_freq_ghz`` the printed centre frequency, and
``npz``/``out`` the two paths.  Both halves are run through the script's real
``main`` and compared, so a config field that is parsed and then ignored fails
here instead of in a 1400 s solve.

NOTHING IS SOLVED.  Every invocation here passes ``--dry-run``: the reference's
own dry-run path builds no mesh, runs no timestep and writes no file (only
``build_kwargs`` and its JSON call block), so the whole file costs a couple of
seconds and touches no artefact.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json

import pytest

from emfit.config import (
    DEFAULT_DUMP_STRIDE,
    DEFAULT_N_LINE,
    DEFAULT_NSTEPS,
    DEFAULT_VOLUME_STRIDE,
    DEFAULT_XCUT_FAR_MM,
    DEFAULT_XCUT_NEAR_MM,
    SCHEMA_VERSION,
    RunConfig,
)

# ``scripts/`` has no ``__init__.py``: pytest's ``pythonpath=["."]`` puts the
# repository root first on sys.path, so this is a PEP 420 namespace package and
# the import is the same one the command line gets.  Importing the module is
# cheap -- it defers loading run_build_A.py until a run needs it.
sim = importlib.import_module("scripts.run_reference_sim")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def dry_run(argv: list[str]) -> tuple[int, str]:
    """Run the script's real ``main`` in dry-run mode and return (rc, stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = sim.main([*argv, "--dry-run"])
    return rc, buf.getvalue()


def flag_value(argv: list[str], flag: str) -> str:
    """The value argv gives ``flag`` (the reference's argv is one string each)."""
    assert flag in argv, f"{flag} never reached the reference: {argv!r}"
    return argv[argv.index(flag) + 1]


def write_config(tmp_path, **fields) -> str:
    """Write a RunConfig document under ``tmp_path`` and return its path."""
    path = tmp_path / "run.json"
    path.write_text(RunConfig(**fields).to_json(), encoding="utf-8")
    return str(path)


# A configuration that differs from the defaults in EVERY config-driven field,
# so a field that is silently dropped shows up as a plan line that did not move.
# n_line 79 (not the default 54) is run_build_A.py's Run E length: it makes the
# mesh 87 x 212 x 22 = 405,768 cells, which is what proves the mesh came from
# the file and not from the reference's own default.
VARIANT = dict(
    nsteps=600,
    dump_stride=2,
    volume_stride=30,
    volume_frames=8,
    pulse_freq_ghz=10.0,
    n_line=79,
    xcut_near_mm=20.4,
    xcut_far_mm=22.0,
)


# --------------------------------------------------------------------------- #
# the document itself
# --------------------------------------------------------------------------- #
def test_defaults_are_a_json_document():
    """Every field is JSON-native and the schema version is stamped in."""
    doc = RunConfig().to_dict()
    assert doc["schema_version"] == SCHEMA_VERSION
    assert set(doc) == set(RunConfig.__dataclass_fields__)
    # No custom encoder anywhere: the document must survive a plain json pass.
    assert json.loads(json.dumps(doc)) == doc


def test_defaults_are_the_scripts_own_defaults():
    """The file's defaults are the ones a run without a file would use.

    Otherwise ``--config <a file that states nothing>`` would silently be a
    DIFFERENT run from no config at all, which is the one way a config file can
    make a run unreproducible rather than reproducible.
    """
    cfg = RunConfig()
    assert cfg.nsteps == sim.DEFAULT_NSTEPS == DEFAULT_NSTEPS
    assert cfg.volume_stride == sim.DEFAULT_VOLUME_STRIDE == DEFAULT_VOLUME_STRIDE
    assert cfg.dump_stride == sim.DEFAULT_DUMP_STRIDE == DEFAULT_DUMP_STRIDE
    assert cfg.n_line == DEFAULT_N_LINE
    assert cfg.xcut_near_mm == DEFAULT_XCUT_NEAR_MM
    assert cfg.xcut_far_mm == DEFAULT_XCUT_FAR_MM
    # None is "the script's own path", not a path relative to the config file.
    assert cfg.npz is None and cfg.out is None


def test_json_round_trip_is_lossless():
    cfg = RunConfig(**VARIANT, npz="artifacts/volume.npz", out="artifacts/run.json")
    again = RunConfig.from_json(cfg.to_json())
    assert again == cfg
    assert json.loads(cfg.to_json()) == cfg.to_dict()


def test_missing_keys_mean_the_defaults():
    cfg = RunConfig.from_dict({"nsteps": 600})
    assert cfg.nsteps == 600
    assert cfg.volume_stride == DEFAULT_VOLUME_STRIDE
    assert cfg.npz is None


def test_unknown_key_is_refused_by_name():
    """A misspelled field would otherwise fall back to its default, silently."""
    with pytest.raises(ValueError, match="unknown key"):
        RunConfig.from_dict({"nstep": 600})


@pytest.mark.parametrize(
    "fields, error, match",
    [
        ({"nsteps": 0}, ValueError, "nsteps must be at least 1"),
        ({"nsteps": 2400.0}, TypeError, "nsteps must be an int"),
        ({"nsteps": True}, TypeError, "nsteps must be an int"),
        ({"dump_stride": 0}, ValueError, "dump_stride must be at least 1"),
        ({"volume_stride": 0}, ValueError, "volume_stride must be at least 1"),
        ({"volume_frames": 0}, ValueError, "volume_frames must be at least 1"),
        ({"n_line": 0}, ValueError, "n_line must be at least 1"),
        ({"pulse_freq_ghz": 0.0}, ValueError, "pulse_freq_ghz must be positive"),
        ({"pulse_freq_ghz": float("nan")}, TypeError, "finite number"),
        ({"xcut_near_mm": -1.0}, ValueError, "xcut_near_mm must be positive"),
        ({"xcut_near_mm": 23.0, "xcut_far_mm": 22.0}, ValueError,
         "must be less than"),
        ({"npz": ""}, ValueError, "non-empty path"),
        ({"schema_version": SCHEMA_VERSION + 1}, ValueError, "schema_version"),
    ],
)
def test_validation_refuses_what_would_mean_something_else(fields, error, match):
    with pytest.raises(error, match=match):
        RunConfig(**fields)


def test_a_valid_document_is_what_validate_accepts():
    """``validate`` and the constructor agree (no path accepts more than the other)."""
    cfg = RunConfig(**VARIANT)
    assert cfg.validate() is cfg
    assert RunConfig.from_json(cfg.to_json()) == cfg


# --------------------------------------------------------------------------- #
# the wiring: the config reaches the reference's argv
# --------------------------------------------------------------------------- #
def _namespace(config_path):
    """The namespace the parser would build, with every flag absent."""
    return argparse.Namespace(
        config=config_path,
        npz=None, out=None, nsteps=None, volume_stride=None, dump_stride=None,
        volume_frames=None, pulse_freq_ghz=None, n_line=None, xcut_near_mm=None,
        xcut_far_mm=None,
    )


def test_every_config_field_reaches_the_reference_argv(tmp_path):
    """The fields a plan cannot show (x-cuts) still have to arrive at the solve."""
    npz = tmp_path / "vol.npz"
    args = _namespace(
        write_config(tmp_path, **VARIANT, npz=str(npz), out=str(tmp_path / "r.json")))
    cfg = sim.load_config(args.config)
    sim.apply_config(args, cfg)
    argv = sim.reference_argv(args)

    assert flag_value(argv, "--nsteps") == "600"
    assert flag_value(argv, "--dump-stride") == "2"
    assert flag_value(argv, "--volume-stride") == "30"
    assert flag_value(argv, "--volume-frames") == "8"
    assert flag_value(argv, "--pulse-freq-ghz") == "10.0"
    assert flag_value(argv, "--n-line") == "79"
    assert flag_value(argv, "--xcut-near-mm") == "20.4"
    assert flag_value(argv, "--xcut-far-mm") == "22.0"
    assert flag_value(argv, "--vis-dump") == str(npz)
    assert flag_value(argv, "--out") == str(tmp_path / "r.json")
    # Arm A is not a knob (B/C/D are other terminations, a different errand).
    assert flag_value(argv, "--structure") == sim.STRUCTURE == "A"


# --------------------------------------------------------------------------- #
# the plan: the file's numbers are the numbers that get priced
# --------------------------------------------------------------------------- #
def test_config_drives_the_priced_plan(tmp_path):
    """Every number the config states is the number printed, and nothing is written."""
    npz = tmp_path / "never_written.npz"
    path = write_config(tmp_path, **VARIANT, npz=str(npz),
                        out=str(tmp_path / "never_written.json"))

    rc, out = dry_run(["--config", path])

    assert rc == 0
    # The provenance line names the file: the flags below are resolved values.
    assert f"CONFIG      {path}" in out
    assert f"(schema {SCHEMA_VERSION})" in out
    # n_line 79 -> nx = n_pml 6 + n_ref 2 + 79 = 87 (the default is 62).
    assert "mesh        87 x 212 x 22 = 405,768 cells at 0.400 mm" in out
    assert "at 10.000 GHz, 600 steps" in out
    assert "stride 2: 300 frames" in out
    assert "one every 30 y-cut frames = every 60 solver step(s)" in out
    # 8 frames of 87 x 212 x 22 float32 + 8 int32 steps = 13.0 MB, priced by the
    # reference's own budget function against its own 48 MB.
    assert "~13.0 MB of a 48.0 MB budget" in out
    assert f"npz         {npz}" in out
    assert "DRY RUN - nothing was solved" in out
    assert not npz.exists(), "a dry run must not write the dump"


def test_without_a_config_the_defaults_are_priced(tmp_path):
    """The same subtraction the test above makes, from the other side: no file."""
    npz = tmp_path / "never_written.npz"
    rc, out = dry_run(["--npz", str(npz), "--out", str(tmp_path / "r.json")])

    assert rc == 0
    assert "CONFIG" not in out
    assert "mesh        62 x 212 x 22 = 289,168 cells at 0.400 mm" in out
    assert "at 15.000 GHz, 2400 steps" in out
    assert "stride 1: 2400 frames" in out
    assert "one every 100 y-cut frames = every 100 solver step(s)" in out
    assert "~27.8 MB of a 48.0 MB budget" in out
    assert not npz.exists()


def test_the_config_is_load_bearing_not_decorative(tmp_path):
    """One field at a time: the plan moves, and only by what the file says.

    This is the assertion the whole file exists for.  Each case changes a single
    field away from its default and looks for the plan line that must follow;
    a config that were merely parsed and then ignored would leave every one of
    these at its default value, and the ``hides`` half would fail.
    """
    npz = tmp_path / "never_written.npz"
    out_path = str(tmp_path / "r.json")
    cases = [
        # (field, value, must appear, must NOT appear)
        ("nsteps", 600, "at 15.000 GHz, 600 steps", "2400 steps"),
        ("dump_stride", 4, "stride 4: 600 frames", "stride 1:"),
        ("volume_stride", 60, "one every 60 y-cut frames", "every 100 y-cut frames"),
        ("volume_frames", 3, "|E| volume  3 frames", "|E| volume  24 frames"),
        ("pulse_freq_ghz", 12.0, "at 12.000 GHz", "at 15.000 GHz"),
        ("n_line", 79, "mesh        87 x 212 x 22", "mesh        62 x 212 x 22"),
    ]
    for field, value, shows, hides in cases:
        path = write_config(tmp_path, **{field: value}, npz=str(npz), out=out_path)
        rc, text = dry_run(["--config", path])
        assert rc == 0
        assert shows in text, f"{field}={value} never reached the plan:\n{text}"
        assert hides not in text, f"{field}={value} left a default in the plan:\n{text}"
    assert not npz.exists()


def test_a_typed_flag_beats_the_config(tmp_path):
    """The command line is the more specific statement, so it wins -- per flag."""
    npz = tmp_path / "never_written.npz"
    path = write_config(tmp_path, **VARIANT, npz=str(npz),
                        out=str(tmp_path / "r.json"))

    rc, out = dry_run(["--config", path, "--nsteps", "300"])

    assert rc == 0
    assert "at 10.000 GHz, 300 steps" in out          # from the flag
    assert "mesh        87 x 212 x 22" in out         # still the config's mesh
    assert "stride 2: 150 frames" in out              # still the config's stride


def test_a_refused_config_stops_before_anything_is_priced(tmp_path):
    """A document that does not validate is refused where it is read."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"nstep": 600}), encoding="utf-8")
    npz = tmp_path / "never_written.npz"

    with pytest.raises(SystemExit) as exc:
        dry_run(["--config", str(bad), "--npz", str(npz)])

    message = str(exc.value.code)
    assert "REFUSED" in message and str(bad) in message
    assert "unknown key" in message
    assert not npz.exists()


def test_a_missing_config_file_is_refused_by_path(tmp_path):
    missing = tmp_path / "not_here.json"
    with pytest.raises(SystemExit) as exc:
        dry_run(["--config", str(missing)])
    assert "REFUSED" in str(exc.value.code) and str(missing) in str(exc.value.code)
