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
    DEFAULT_LOAD_OHM,
    DEFAULT_N_LINE,
    DEFAULT_NSTEPS,
    DEFAULT_VOLUME_STRIDE,
    DEFAULT_WALL_LIMIT_S,
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
    # The two runtime guards, at values that are deliberately NOT their
    # defaults: 300 s rather than the reference's 1400 s ceiling, and 75 ohm
    # rather than the ARM's own 50 -- a field that is silently dropped now
    # shows up as two more numbers the plan did not move (DR-52 shipped
    # exactly that).
    wall_limit_s=300.0,
    load_ohm=75.0,
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
    assert cfg.wall_limit_s == sim.DEFAULT_WALL_LIMIT_S == DEFAULT_WALL_LIMIT_S
    # None is "the arm's own" (A 50 ohm, B 100 ohm), NOT a number: a default of
    # 50.0 would re-terminate a 100 ohm arm in silence (emfit/config.py:93-100).
    assert cfg.load_ohm is None
    assert sim.DEFAULT_LOAD_OHM is None
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
        # The two runtime guards are action-less float flags whose ABSENT
        # value is meaningful (None = the arm's own load,
        # scripts/run_reference_sim.py:130), so the namespace has to carry
        # them or reference_argv cannot tell "absent" from "not given".
        wall_limit_s=None, load_ohm=None,
        # --no-volume is action="store_true" (scripts/run_reference_sim.py:595),
        # so the parser's own default is False; reference_argv reads it (:288).
        no_volume=False,
    )


#: The RunConfig fields that are NOT run knobs, and are therefore absent from
#: CONFIG_DRIVEN by design.
NOT_FORWARDED = frozenset({"schema_version"})

#: The one CONFIG_DRIVEN row whose flag is not its name with dashes for
#: underscores: the dump path reaches the reference as ``--vis-dump``
#: (scripts/run_reference_sim.py:278), while ``--npz`` is only THIS script's own
#: spelling of that field.  Stated once here rather than as a third column,
#: because the table's job is the wiring, not the reference's spelling.
FLAG_NAMES = {"npz": "--vis-dump"}


def test_config_driven_is_exactly_the_run_config_knobs():
    """CONFIG_DRIVEN, in scripts/run_reference_sim.py, is the contract.

    A field added to RunConfig and forgotten there is a document that
    validates, loads, and silently does nothing -- which is how load_ohm and
    wall_limit_s shipped (DR-52).  Set equality, not a subset, so a table row
    naming a field that no longer exists fails the same way.
    """
    forwarded = {name for name, _ in sim.CONFIG_DRIVEN}
    knobs = set(RunConfig.__dataclass_fields__) - NOT_FORWARDED
    assert forwarded == knobs, (
        f"CONFIG_DRIVEN is missing {sorted(knobs - forwarded)} and names "
        f"{sorted(forwarded - knobs)}, which RunConfig does not have")


@pytest.mark.parametrize("name", [name for name, _ in sim.CONFIG_DRIVEN])
def test_every_config_field_reaches_the_reference_argv(tmp_path, name):
    """The fields a plan cannot show (x-cuts, the load) still reach the solve.

    Driven by the TABLE, one field at a time, each at a value that is not its
    default: the version of this test that spelled a dozen flag/value pairs by
    hand stayed green while two table rows were missing (DR-52).  The flag
    spelling is the table's other invariant -- a row's flag is its name with
    underscores turned into dashes, FLAG_NAMES being the single documented
    exception -- so a row that is spelled wrongly fails here too.
    """
    values = dict(VARIANT, npz=str(tmp_path / "vol.npz"),
                  out=str(tmp_path / "r.json"))
    value = values[name]
    args = _namespace(write_config(tmp_path, **{name: value}))
    sim.apply_config(args, sim.load_config(args.config))
    argv = sim.reference_argv(args)

    flag = FLAG_NAMES.get(name, "--" + name.replace("_", "-"))
    got = flag_value(argv, flag)
    if isinstance(value, str):
        assert got == value
    else:
        # float(): reference_argv formats the two guards with %g and the rest
        # with str(), so 75.0 arrives as '75' and 600 as '600' -- the VALUE is
        # the contract, not the spelling.
        assert float(got) == float(value)
    # Arm A is not a config knob (B/C/D are other terminations, a different
    # errand), but every argv states it: the one test that builds an argv from a
    # document keeps the prologue honest.
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


# --------------------------------------------------------------------------- #
# DR-52: the guards the plan PRINTS are the guards the solve receives
# --------------------------------------------------------------------------- #
def test_dr52_a_named_load_is_what_the_plan_states(tmp_path):
    """A --config that names 75 ohm is solved at 75 ohm AND printed as 75.

    DR-52's old behaviour: the header said "50 ohm" for every run, because the
    number was a literal in the print (scripts/run_reference_sim.py:441-444), so
    a document that named 75 solved at 75 while the plan that prices a 1400 s
    solve read back as arm A's own 50 -- the two halves of one run disagreed.
    """
    npz = tmp_path / "never_written.npz"
    path = write_config(tmp_path, load_ohm=75.0, npz=str(npz),
                        out=str(tmp_path / "never_written.json"))

    rc, out = dry_run(["--config", path])

    assert rc == 0
    assert "75 ohm series_r at p2" in out
    assert "NAMED, and arm A's own is 50 ohm" in out
    # The line that used to be printed whatever the document said.
    assert "50 ohm series_r" not in out
    assert not npz.exists(), "a dry run must not write the dump"


def test_dr52_an_absent_load_is_the_arms_own(tmp_path):
    """Neither guard named: the plan states arm A's own 50 ohm and 1400 s.

    DR-52's old behaviour: the ceiling and the load were literals in the print
    (scripts/run_reference_sim.py:439-444), so a --config that named either one
    solved one thing and was priced as another.  Absent has to read as "the
    arm's own", not as 50.0, which would re-terminate a 100 ohm arm in silence
    (emfit/config.py:93-100).
    """
    npz = tmp_path / "never_written.npz"
    path = write_config(tmp_path, npz=str(npz),
                        out=str(tmp_path / "never_written.json"))

    rc, out = dry_run(["--config", path])

    assert rc == 0
    assert "50 ohm series_r at p2 - the arm's own, from STRUCTURES" in out
    assert "1400 s ceiling" in out
    assert not npz.exists(), "a dry run must not write the dump"
