"""``_load_kernel`` fails LOUDLY when a built extension exists but will not import.

The gap this closes
-------------------
``emfit/evolve.py`` ``_load_kernel`` used to answer ``None`` for every reason it
could not get ``emfit_core`` -- no extension anywhere, an ABI it does not know,
or a ``.so`` sitting right there that failed to import.  The first two are
honest absences; the third is a broken install, and reporting it as an absence
is a false provenance claim: the process records ``step_engine="python"`` (see
``emfit.evolve.engine_report`` and ``tools/host_ladder.py``'s ``meta``) while a
compiled kernel that would have been used is on the disk beside it.  A reader
of a banked artefact cannot tell that "python" means "not built".

What these tests pin
--------------------
* an extension that imports is returned, and the on-disk probe is never
  consulted on that path (it is a diagnostic, not a decision);
* a ``.so`` on disk plus an import that raises is a ``RuntimeError`` naming the
  file, the original exception, and both ways out -- with the original
  exception chained, so a traceback still shows why the import failed;
* nothing on disk plus an import that raises is still ``None``: an unbuilt
  extension remains an ordinary, silent absence;
* ``EMFIT_FORCE_PYTHON=1`` is ``None`` *without* importing or probing -- the
  deliberate Python path must not pay for, or trip over, either;
* the real probe finds the extension in whatever environment this suite runs
  in, or says so with a skip -- a probe that finds nothing everywhere would be
  silent again through the back door.

No FDTD run, no import of the real ``emfit_core`` and no build happens here;
every case that needs an extension substitutes a stand-in or replaces the
importer.
"""

import pytest

import emfit.evolve as evolve


class _Kernel:
    """Stand-in with the two attributes ``_load_kernel`` reads, and nothing else."""

    KERNEL_ABI = evolve._KERNEL_ABI

    def step_explicit(self):                # callable, never called
        raise AssertionError("_load_kernel must not call the kernel")


def _never_called(what):
    """A probe that fails the test if anything asks it anything."""
    def probe():
        raise AssertionError(f"{what} must not be consulted on this path")
    return probe


def test_an_importable_extension_is_returned_without_probing_the_disk(monkeypatch):
    """The happy path: the importer's module, and the disk is not even read."""
    monkeypatch.delenv(evolve._FORCE_PYTHON_ENV, raising=False)
    kernel = _Kernel()
    monkeypatch.setattr(evolve, "_import_kernel", lambda: kernel)
    monkeypatch.setattr(evolve, "_probe_kernel_files",
                        _never_called("the on-disk extension probe"))
    assert evolve._load_kernel() is kernel


def test_a_so_on_disk_that_cannot_be_imported_raises_naming_the_file(monkeypatch):
    """The whole point: present-but-unimportable is an error, not an absence."""
    monkeypatch.delenv(evolve._FORCE_PYTHON_ENV, raising=False)
    cause = ImportError(
        "libgomp.so.1: cannot open shared object file: No such file or directory")
    path = ("/somewhere/.venv/lib/python3.12/site-packages/"
            "emfit_core.cpython-312-x86_64-linux-gnu.so")

    def failing_import():
        raise cause

    monkeypatch.setattr(evolve, "_import_kernel", failing_import)
    monkeypatch.setattr(evolve, "_probe_kernel_files", lambda: [path])

    with pytest.raises(RuntimeError) as excinfo:
        evolve._load_kernel()

    message = str(excinfo.value)
    assert path in message, "the error must name the file it found"
    assert "ImportError" in message, "the error must name the original exception"
    assert cause.args[0] in message, "and quote what it said"
    assert "put the venv site-packages on PYTHONPATH" in message
    assert "pass --force-python / set EMFIT_FORCE_PYTHON=1" in message
    assert excinfo.value.__cause__ is cause, "the original failure must stay chained"


def test_nothing_on_disk_that_cannot_be_imported_stays_silent(monkeypatch):
    """An extension that was never built is not an error -- it is the default."""
    monkeypatch.delenv(evolve._FORCE_PYTHON_ENV, raising=False)

    def failing_import():
        raise ModuleNotFoundError("No module named 'emfit_core'")

    monkeypatch.setattr(evolve, "_import_kernel", failing_import)
    monkeypatch.setattr(evolve, "_probe_kernel_files", lambda: [])
    assert evolve._load_kernel() is None


def test_the_force_python_variable_skips_both_the_import_and_the_probe(monkeypatch):
    """``EMFIT_FORCE_PYTHON=1`` is a decision, so it is taken before any work."""
    monkeypatch.setenv(evolve._FORCE_PYTHON_ENV, "1")
    monkeypatch.setattr(evolve, "_import_kernel",
                        _never_called("the extension import"))
    monkeypatch.setattr(evolve, "_probe_kernel_files",
                        _never_called("the on-disk extension probe"))
    assert evolve._load_kernel() is None


def test_the_real_probe_finds_the_extension_this_environment_can_import():
    """Not a fake: the probe must see the built extension where it really is."""
    found = evolve._probe_kernel_files()
    if not found:
        pytest.skip("no emfit_core extension file anywhere this probe looks")
    assert all("emfit_core" in str(p) for p in found)
    assert all(str(p).endswith((".so", ".pyd")) for p in found)
    assert found == sorted(found), "the probe sorts, so its message is stable"
