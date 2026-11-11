"""Port-record name resolution in the openEMS referee: the basenames it must find.

No openEMS and no solver: the module is loaded under a non-``__main__`` sentinel
(it guards ``main()`` at ``docker/openems/build_A_referee.py:3709``) and only the
pure name-resolution helpers are exercised.  openEMS writes ``port_ut_1A`` /
``port_it_1B``, NOT ``port_1_utA``; this pins both spellings.
"""
import importlib.util
from pathlib import Path

REFEREE = Path(__file__).resolve().parents[1] / "docker" / "openems" / "build_A_referee.py"

# The seven records an MSLPort run leaves on disk.
OPENEMS_BASENAMES = ("port_ut_1A", "port_ut_1B", "port_ut_1C",
                     "port_it_1A", "port_it_1B", "port_ut_2", "port_it_2")
# The fallback spelling PROBE_NAME_CANDIDATES carries as its second element.
LEGACY_BASENAMES = ("port_1_utA", "port_1_utB", "port_1_utC",
                    "port_1_itA", "port_1_itB",
                    "port_ut_2", "port_it_2")


def _referee():
    assert 'if __name__ == "__main__":' in REFEREE.read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location("build_A_referee_under_test", REFEREE)
    module = importlib.util.module_from_spec(spec)
    module.__name__ = "build_A_referee_under_test"  # never "__main__": main() must not run
    spec.loader.exec_module(module)
    return module


def test_resolves_openems_basenames(tmp_path):
    ref = _referee()
    for basename in OPENEMS_BASENAMES:
        (tmp_path / basename).touch()
    for name in ref.PORT1_MSL_PROBES + ("port_ut_2", "port_it_2"):
        path = ref.resolve_port_record(str(tmp_path), name)
        assert path is not None, name
        assert Path(path).exists(), path


def test_resolves_legacy_basenames(tmp_path):
    ref = _referee()
    for name in ref.PORT1_MSL_PROBES:
        fallback = ref.PROBE_NAME_CANDIDATES[name][1]
        assert fallback in LEGACY_BASENAMES, fallback
        (tmp_path / fallback).touch()
    for basename in ("port_ut_2", "port_it_2"):
        (tmp_path / basename).touch()
    for name in ref.PORT1_MSL_PROBES + ("port_ut_2", "port_it_2"):
        path = ref.resolve_port_record(str(tmp_path), name)
        assert path is not None, name
        assert Path(path).exists(), path
        assert Path(path).name in LEGACY_BASENAMES, path
