"""The structure registry: what it promises, and what the tree can actually back.

``structures.json`` is the picker's catalogue. Its entries are path STRINGS (the
server resolves them late, per press) and a declared cell shape (the picker's
label, kept apart from the artefact so a wrong label is visible without opening
an 80 MB file). Nothing else in the suite reads the file itself - the server
tests mock ``load_structures`` out - so a typo in a path, a bogus cell string or
a dropped entry is invisible until a user presses a button and the page comes
back empty. These six tests are that missing read.

They are JSON + numpy only: no ``poc_app`` import (it builds a trame app on
import and needs a GL context this image does not have) and no plotting. A
failure therefore names a fact about the catalogue, not a rendering.

``ROOT`` is deliberately ``parents[1]`` of this file and NOT the workspace root:
a copy of this file under ``probes/`` is meant to resolve against its own
scratch root, which is how the mutation rig proves these tests have teeth. Do
not "fix" it to an absolute path.
"""

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "structures.json"

# The schemas ``load_vis`` in server/poc_app.py still accepts for a dump.
VIS_SCHEMAS = ("emfit.vis/2", "emfit.wavedude/1", "emfit.wavedude/2")
# The one pre-vis plane dump shape that is still in the tree.
LEGACY_PLANE_KEYS = ("e", "h", "plane_ez", "nstep", "nx", "ny", "nz", "cell_m")
BLOCKS = ("field_dump", "sparams", "multifreq")


def _document():
    """The parsed registry - every test starts from the file, not a fixture."""
    return json.loads(REGISTRY.read_text())


def _entries(doc=None):
    return (doc or _document())["structures"]


def _dump_path(entry):
    """The declared field-dump path as a Path under ROOT, or None if undeclared."""
    block = entry.get("field_dump")
    if not isinstance(block, dict):
        return None
    return ROOT / block["path"]


def test_document_shape():
    """A catalogue the picker can iterate: one schema tag, unique labelled ids.

    The picker builds a dropdown from ``id`` + ``label`` and looks entries up by
    ``id``, so a duplicate id silently hides one arm and an empty label renders
    as a blank row. Both are cheap to assert and free to break by hand-editing
    the JSON, which is exactly how this file is maintained.
    """
    doc = _document()
    assert doc["schema"] == "emfit.structures/1", (
        f"registry schema is {doc['schema']!r}, expected 'emfit.structures/1'"
    )
    entries = doc["structures"]
    assert isinstance(entries, list) and entries, (
        f"'structures' must be a non-empty list, got {type(entries).__name__} "
        f"of length {len(entries) if hasattr(entries, '__len__') else '?'}"
    )
    assert all(isinstance(e, dict) for e in entries), (
        "every entry must be a dict, got "
        f"{[type(e).__name__ for e in entries if not isinstance(e, dict)]}"
    )
    ids = [e.get("id") for e in entries]
    assert all(isinstance(i, str) and i for i in ids), (
        f"every entry needs a non-empty string 'id', got {ids!r}"
    )
    assert len(set(ids)) == len(ids), f"duplicate entry ids: {ids!r}"
    bad = [e["id"] for e in entries
           if not (isinstance(e.get("label"), str) and e["label"])]
    assert not bad, f"entries with a missing or empty 'label': {bad!r}"


def test_paths_are_relative_posix():
    """Every declared path is a tree-relative POSIX string.

    The server joins these onto the project root, so an absolute path (or one
    that climbs out with ``..``) resolves off-tree on someone else's machine,
    and a backslash never resolves at all on Linux. The path is the ONE field
    that must be right: the server checks it exists, nothing else here does.
    """
    for entry in _entries():
        for name in BLOCKS:
            block = entry.get(name)
            if block is None:
                continue
            assert isinstance(block, dict), (
                f"{entry['id']}.{name} must be a dict or null, "
                f"got {type(block).__name__}"
            )
            path = block.get("path")
            assert isinstance(path, str) and path, (
                f"{entry['id']}.{name}.path must be a non-empty string, "
                f"got {path!r}"
            )
            assert "\\" not in path, (
                f"{entry['id']}.{name}.path uses a backslash: {path!r}"
            )
            assert not path.startswith("/") and not Path(path).is_absolute(), (
                f"{entry['id']}.{name}.path must be relative, got {path!r}"
            )
            assert ".." not in Path(path).parts, (
                f"{entry['id']}.{name}.path climbs out of the tree: {path!r}"
            )


def test_cells_strings_parse():
    """A declared cell shape is exactly three positive integers in 'NxNxN' form.

    ``cells`` is what the picker shows ("62x212x22") and what the other tests
    compare against the artefact's own nx/ny/nz, so it has to unpack cleanly:
    a zero, a float or a missing axis would otherwise compare unequal for the
    wrong reason and send the reader looking at the dump instead of the label.
    """
    for entry in _entries():
        for name in ("field_dump", "sparams"):
            block = entry.get(name)
            if block is None or "cells" not in block:
                continue
            cells = block["cells"]
            assert isinstance(cells, str), (
                f"{entry['id']}.{name}.cells must be a string, "
                f"got {type(cells).__name__}"
            )
            parts = cells.split("x")
            assert len(parts) == 3, (
                f"{entry['id']}.{name}.cells is not three axes separated by 'x': "
                f"{cells!r}"
            )
            assert all(p.isdigit() for p in parts), (
                f"{entry['id']}.{name}.cells has a non-integer axis: {cells!r}"
            )
            nx, ny, nz = (int(p) for p in parts)
            assert min(nx, ny, nz) >= 1, (
                f"{entry['id']}.{name}.cells has a non-positive axis: {cells!r}"
            )


def test_declared_cells_match_the_file():
    """The label matches the dump it names - read from the dump's own scalars.

    This is the whole point of keeping ``cells`` beside ``path``: the picker
    shows the label, the loader reads the array, and only a comparison catches
    a label copy-pasted from the sibling entry. Only the three tiny integer
    scalars are read here (never the field data), so it stays cheap.
    """
    checked = []
    for entry in _entries():
        path = _dump_path(entry)
        if path is None or not path.is_file():
            continue
        with np.load(path, allow_pickle=False) as handle:
            missing = [k for k in ("nx", "ny", "nz") if k not in handle.files]
            assert not missing, (
                f"{entry['id']}: {path.relative_to(ROOT)} has no {missing!r} "
                "scalar, so its declared cells cannot be checked"
            )
            actual = "x".join(str(int(np.asarray(handle[k]).item()))
                              for k in ("nx", "ny", "nz"))
        declared = entry["field_dump"]["cells"]
        assert declared == actual, (
            f"{entry['id']}: registry says {declared!r} but "
            f"{path.relative_to(ROOT)} is {actual!r}"
        )
        checked.append(entry["id"])
    assert checked, (
        "no declared field dump exists under "
        f"{ROOT}, so this test checked nothing - the rig is wrong, not the file"
    )


def test_every_dump_is_loadable():
    """Each registered dump is one of the two shapes the server can open.

    Registering a path is a promise that pressing it works, and the server only
    discovers a bad key set when the press already happened. The key set alone
    (``f.files``) is enough to tell the shapes apart, so no field array is read:
    a vis dump carries the ``schema`` tag ``load_vis`` accepts, a legacy plane
    dump carries the eight keys of the pre-vis format, and there is no third
    shape in the tree.
    """
    checked = []
    for entry in _entries():
        path = _dump_path(entry)
        if path is None or not path.is_file():
            continue
        with np.load(path, allow_pickle=False) as handle:
            keys = set(handle.files)
            is_vis = "schema" in keys
            if is_vis:
                schema = str(np.asarray(handle["schema"]).item())
        where = f"{entry['id']}: {path.relative_to(ROOT)}"
        if is_vis:
            assert schema in VIS_SCHEMAS, (
                f"{where} carries schema {schema!r}, which load_vis does not "
                f"accept (VIS_SCHEMAS={VIS_SCHEMAS!r})"
            )
        else:
            missing = [k for k in LEGACY_PLANE_KEYS if k not in keys]
            assert not missing, (
                f"{where} is neither a vis dump (no 'schema' key) nor a legacy "
                f"plane dump (missing {missing!r}); keys are {sorted(keys)!r}"
            )
        checked.append(entry["id"])
    assert checked, (
        "no registered dump exists under "
        f"{ROOT}, so this test checked nothing - the rig is wrong, not the file"
    )


def test_reachable_set_is_explicit():
    """Which entries a user can actually open, stated as a set.

    ``structures.json`` lists records that have no artefact on purpose (the gap
    is meant to be visible), so the file's length says nothing about what works.
    Pinning the reachable set is what makes adding or losing a dump a decision
    someone has to make in this test rather than a silent change of what the
    page offers.
    """
    reachable, empty = set(), set()
    for entry in _entries():
        path = _dump_path(entry)
        (reachable if path is not None and path.is_file() else empty).add(
            entry["id"]
        )
    expected_reachable = {
        "build_A_50ohm",
        "build_B_100ohm",
        "live_run",
        "reference_sim",
    }
    expected_empty = {"build_A_50ohm_100ohm", "build_A_series_R"}
    assert reachable == expected_reachable, (
        f"entries with an existing field dump: {sorted(reachable)!r}, "
        f"expected {sorted(expected_reachable)!r}"
    )
    assert empty == expected_empty, (
        f"entries with no field dump: {sorted(empty)!r}, "
        f"expected {sorted(expected_empty)!r}"
    )
