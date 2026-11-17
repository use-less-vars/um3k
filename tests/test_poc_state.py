"""The PoC page's numpy-only state dump: the composite, as a document.

``server/poc_app.py --dump-state PATH`` is the half of the page that can be
checked on a machine with no pyvista, no trame and no VTK: it writes what the
page WOULD composite, where each number came from, and where the seams are. This
file drives that CLI exactly as an operator would - one subprocess, one file on
disk, then every assertion reads the parsed document - so what is tested is the
shipped entry point, not a helper called directly.

What each test is protecting, in one line:

    T1  the CLI runs at all (exit 0) on the real artefacts;
    T2  the file is STRICT JSON - no NaN, no Infinity, no Python-only literals;
    T3  the field dump and the S-parameter record are declared as different runs
        (62 vs 72 cells) instead of being presented as one solve;
    T4  both cell counts are read from their own source and disagree;
    T5  the residual percentages ship with BOTH anchors, as a diagnosis, never
        as a validation;
    T6  the sweep bin with an unresolved dispersion branch is marked as such;
    T7  the frequency chart is markers-only and says it does not interpolate;
    T8  an unknown structure id is refused (exit 2) and the valid ones are named;
    T9  the two extents are distinct numbers with a stated basis - domain cells
        vs the line the stored planes cover on x and the stored array's shape on
        y/z - and the old single ``extent_mm`` key is gone;
    T10 a record-only structure id is REFUSED (exit 2, it names itself, it names
        what CAN be opened, and it writes no state file) instead of silently
        rendering another case's field data under that id;
    T11 the same for the second record-only id - the two are parametrised over
        one body, not copy-pasted, so a third one cannot slip through.

Skips: only when the field dump itself is absent. Never for a missing optional
package: nothing on this path imports pyvista, trame or matplotlib, and a test
that skipped for those would be silent about the regression it exists to catch.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "server" / "poc_app.py"
NPZ = (
    REPO_ROOT
    / "evidence"
    / "termination"
    / "build_A_50ohm_p51_ghostwave_fields.npz"
)
# build/, NOT /tmp: /tmp is noexec on this host and the dump is meant to be
# readable afterwards, beside the other build artefacts.
STATE_PATH = REPO_ROOT / "build" / "pytest_state_dump.json"
CLI_TIMEOUT_S = 120
# The one-time release volume a bare invocation prefers. It is gitignored, so a
# fresh clone does not have it and still boots (on the legacy dump, out loud) -
# which is why the default-boot test skips here instead of failing.
REFERENCE_NPZ = REPO_ROOT / "artifacts" / "reference_sim_volume.npz"
# The stored plane_ez shape: 9 captured x-planes, then 213 rows in y - ONE MORE
# than the 212 cells the domain record declares - and 22 in z. The sampled y
# extent is therefore 213 * 0.4 = 85.2 mm, not the domain's 84.8 mm.
STORED_PLANE_SHAPE = (9, 213, 22)
# Registry entries with a recorded S-parameter set and NO field dump on disk.
RECORD_ONLY_IDS = ("build_A_series_R", "build_A_50ohm_100ohm")


def _reject_constant(name):
    """parse_constant hook: a bare NaN/Infinity in the dump is a defect."""
    raise AssertionError(f"state dump is not strict JSON: bare {name} constant")


@pytest.fixture(scope="module")
def cli_run():
    """Run ``--dump-state`` ONCE for the whole module; keep stdout/stderr/exit."""
    if not NPZ.is_file():
        pytest.skip(f"field dump absent: {NPZ}")
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.unlink(missing_ok=True)
    proc = subprocess.run(
        # --structure is PINNED here. Every assertion fed by this fixture is
        # about the legacy Build A dump (its shape, its npz, its extents), and
        # a bare run now boots on the reference volume instead - leaving the
        # id off would make those pins compare against a different artefact.
        # The boot default itself is covered by test_t14 below.
        [
            sys.executable,
            str(SCRIPT),
            "--structure",
            "build_A_50ohm",
            "--dump-state",
            str(STATE_PATH),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_S,
    )
    return {
        "proc": proc,
        "path": STATE_PATH,
        "text": STATE_PATH.read_text(encoding="utf-8")
        if STATE_PATH.is_file()
        else "",
    }


@pytest.fixture(scope="module")
def state(cli_run):
    """The parsed document every assertion below reads (strict, no NaN)."""
    return json.loads(cli_run["text"], parse_constant=_reject_constant)


def _number(value, label):
    """A finite float from the dump, or a failure that names the field."""
    assert isinstance(value, (int, float)) and not isinstance(value, bool), (
        f"{label} is not a number: {value!r}"
    )
    return float(value)


# --- T1: the CLI runs -------------------------------------------------------


def test_t1_dump_state_exits_zero(cli_run):
    proc = cli_run["proc"]
    assert proc.returncode == 0, (
        f"--dump-state exited {proc.returncode}\nstdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )
    assert cli_run["text"].strip(), "--dump-state wrote an empty file"


# --- T2: strict JSON --------------------------------------------------------


def test_t2_state_dump_is_strict_json(cli_run, state):
    # parse_constant already rejected NaN/Infinity/-Infinity while the fixture
    # parsed; this pins the same rule against the raw text, because a bare NaN
    # can also arrive unquoted inside a string the loader never looks at.
    for literal in ("NaN", "Infinity"):
        assert literal not in cli_run["text"], (
            f"state dump carries the bare literal {literal}, which is not JSON"
        )
    assert isinstance(state, dict), "the state dump is not a JSON object"
    assert state["schema"].startswith("emfit.poc-state/"), state["schema"]


# --- T3: the two halves are declared as different runs ----------------------


def test_t3_mismatch_is_flagged_and_names_both_cell_counts(state):
    mismatch = state["mismatch"]
    assert mismatch["flag"] is True, (
        "the field dump (62x212x22) and the S-parameter record (72x212x22) are "
        "different runs; the dump must say so"
    )
    reason = mismatch["reason"]
    assert "62x212x22" in reason and "72x212x22" in reason, (
        f"the mismatch reason must name both cell counts, got: {reason!r}"
    )


# --- T4: both cell counts, each from its own source -------------------------


def test_t4_cell_counts_come_from_both_sides_and_differ(state):
    field_cells = state["field_dump"]["cells"]
    sparams_cells = state["sparams"]["cells"]
    for label, cells in (("field_dump.cells", field_cells), ("sparams.cells", sparams_cells)):
        assert isinstance(cells, dict) and cells, f"{label} is empty: {cells!r}"
        for axis in ("nx", "ny", "nz"):
            assert axis in cells, f"{label} has no {axis}: {cells!r}"
    # The field count is the npz's own shape; the S-parameter count is parsed
    # out of that record's summary_line. They must NOT be reconciled silently.
    assert field_cells["nx"] == 62, field_cells
    assert sparams_cells["nx"] == 72, sparams_cells
    assert field_cells["nx"] != sparams_cells["nx"], (
        "nx agrees between the field dump and the S-parameter record; either the "
        "artefacts changed or one count is being read from the wrong file"
    )
    assert (field_cells["ny"], field_cells["nz"]) == (
        sparams_cells["ny"],
        sparams_cells["nz"],
    ), (field_cells, sparams_cells)


# --- T5: residuals are a diagnosis, with both anchors -----------------------


def test_t5_residuals_are_unvalidated_and_name_both_anchors(state):
    residuals = state["residuals"]
    assert residuals["validated"] is False, (
        "no residual in this tree has been validated; the dump must not claim it"
    )
    assert residuals["status"] == "diagnosis in progress", residuals["status"]
    independent = residuals["anchor_independent"]
    circular = residuals["anchor_circular"]
    assert independent["basis"] == circular["basis"] == "50/(50 + 2*z0)"
    assert pytest.approx(
        _number(independent["s11_over_anchor_pct"], "anchor_independent"), abs=0.01
    ) == -4.9, independent
    assert pytest.approx(
        _number(circular["s11_over_anchor_pct"], "anchor_circular"), abs=0.01
    ) == -5.54, circular
    # Two denominators wearing one label is the whole DR-19 confusion: the two
    # anchors must carry different Z0 and therefore different anchors.
    assert independent["z0_ohm"] != circular["z0_ohm"]
    assert independent["anchor"] != circular["anchor"]
    assert {"E1", "E11"} <= set(residuals["ledger_refs"]), residuals["ledger_refs"]


# --- T6: the unresolved dispersion branch is marked -------------------------


def test_t6_ambiguous_bin_is_marked(state):
    multifreq = state["multifreq"]
    assert multifreq is not None, "no sweep rows were read from the summary"
    assert 12 in multifreq["ambiguous_bins"], multifreq["ambiguous_bins"]
    flagged = [point["k"] for point in multifreq["points"] if point["beta_ambiguous"]]
    assert flagged == multifreq["ambiguous_bins"], (flagged, multifreq["ambiguous_bins"])


# --- T7: markers only, no interpolation ------------------------------------


def test_t7_chart_is_markers_only(state):
    chart = state["chart"]
    assert chart["interpolation"] is False, chart["interpolation"]
    assert chart["mode"] == "markers-only", chart["mode"]
    assert len(chart["points"]) == len(state["multifreq"]["points"]), (
        "the chart must plot one marker per recorded row and nothing between them"
    )


# --- T8: an unknown structure id is refused --------------------------------


def test_t8_unknown_structure_id_exits_two_and_lists_valid_ids():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--structure", "nosuchid",
         "--dump-state", str(STATE_PATH.with_name("pytest_unknown_structure.json"))],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_S,
    )
    assert proc.returncode == 2, (
        f"an unknown --structure must exit 2, got {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    stderr = proc.stderr
    assert "unknown --structure" in stderr, stderr
    for structure_id in ("build_A_50ohm", "build_A_50ohm_100ohm", "build_A_series_R"):
        assert structure_id in stderr, (
            f"the refusal must list the valid ids; {structure_id} is absent from: "
            f"{stderr!r}"
        )


# --- T9: two extents, a stated basis, no legacy key ------------------------


def test_t9_two_extents_have_a_basis_and_the_legacy_key_is_gone(state):
    field = state["field_dump"]
    assert "extent_mm" not in field, (
        "the single extent_mm key is the ambiguity this split removes; it must "
        "be gone, not kept beside the two new ones"
    )
    domain = field["extent_domain_mm"]
    sampled = field["extent_sampled_mm"]
    cell = _number(field["grid_cell_mm"], "grid_cell_mm")
    assert cell == pytest.approx(0.4, abs=1e-12), cell
    for label, extent in (("extent_domain_mm", domain), ("extent_sampled_mm", sampled)):
        assert isinstance(extent, dict) and set(extent) == {"x", "y", "z"}, (
            f"{label} must carry exactly x/y/z, got: {extent!r}"
        )
    # 24.8 mm / 0.4 mm = 62 cells across the DOMAIN; 10.0 mm / 0.4 mm = 25 cells
    # across the line the captured planes COVER on x. Both divide by the cell
    # exactly, which is the only reason a reader can trust either figure to the
    # cell count it claims.
    assert domain["x"] == pytest.approx(24.8, abs=1e-9), domain
    assert sampled["x"] == pytest.approx(10.0, abs=1e-9), sampled
    # On y and z the sampled span is the stored array's own shape: 85.2 mm = 213
    # rows in y, 8.8 mm = 22 in z. Reading y off the domain (212 cells -> 84.8
    # mm) is the off-by-one-row this pins against. x is no longer read off the
    # shape at all - it is the span the stations themselves cover.
    assert sampled["y"] == pytest.approx(85.2, abs=1e-9), sampled
    assert sampled["z"] == pytest.approx(8.8, abs=1e-9), sampled
    cells = field["cells"]
    n_sampled_x, n_sampled_y, n_sampled_z = STORED_PLANE_SHAPE
    # The stored shape is the one thing here no record can supply: if the dump's
    # own n_stations disagrees with the array it claims to describe, every
    # stations_x_mm entry below is off as well.
    assert field["n_stations"] == n_sampled_x, (field["n_stations"], STORED_PLANE_SHAPE)
    # End to end: the x extent IS this axis, so the axis is pinned with it. The
    # nine planes the npz stores sit on the study's own stations, 10.4 .. 20.0 mm
    # three cells apart - not at i * 0.4 mm from the port end, which is what a
    # shape-only axis would claim.
    stations = field["stations_x_mm"]
    assert field["stations_src"] == "s11.station_phasors.x_m", field.get("stations_src")
    assert len(stations) == field["n_stations"] == 9, stations
    assert stations[0] == pytest.approx(10.4, abs=1e-9), stations
    assert stations[-1] == pytest.approx(20.0, abs=1e-9), stations
    assert {round(b - a, 9) for a, b in zip(stations, stations[1:])} == {1.2}, stations
    # The x extent is cells COVERED, not planes SAMPLED: nine planes three cells
    # apart span 25 cells (10.4 .. 20.0 mm is 9.6 mm, plus the cell each plane
    # covers), so 10.0 mm / 0.4 mm = 25 - while n_stations stays 9 above.
    n_covered_x = 25
    for label, extent, expected in (
        ("extent_domain_mm.x", domain["x"], cells["nx"]),
        ("extent_domain_mm.y", domain["y"], cells["ny"]),
        ("extent_domain_mm.z", domain["z"], cells["nz"]),
        ("extent_sampled_mm.x", sampled["x"], n_covered_x),
        ("extent_sampled_mm.y", sampled["y"], n_sampled_y),
        ("extent_sampled_mm.z", sampled["z"], n_sampled_z),
    ):
        quotient = extent / cell
        assert abs(quotient - round(quotient)) < 1e-9, (
            f"{label} = {extent!r} mm does not divide into whole cells of "
            f"{cell!r} mm (quotient {quotient!r})"
        )
        assert round(quotient) == expected, (
            f"{label} is {round(quotient)} cells, expected {expected}"
        )
    # The covered span, not the plane count times the cell: 9 * 0.4 = 3.6 mm is
    # what an invented uniform-from-zero axis reports, and it covers less than
    # half the line these planes actually span.
    assert sampled["x"] == pytest.approx((stations[-1] - stations[0]) + cell, abs=1e-9), (
        sampled,
        stations,
    )
    # 212 domain cells vs 213 stored rows: the samples ARE the padded/extended
    # array, so the two y extents cannot be the same number. Equality would mean
    # one count was borrowed from the other - the defect this split removes.
    assert sampled["y"] != domain["y"], (sampled, domain)
    basis = field["extent_basis"]
    assert isinstance(basis, str) and basis.strip(), field["extent_basis"]
    assert "domain_mm" in basis and "sampled_mm" in basis, basis


# --- T10/T11: a record-only entry is refused, never substituted -------------


@pytest.mark.parametrize("structure_id", RECORD_ONLY_IDS)
def test_t10_t11_record_only_structure_is_refused_not_substituted(structure_id):
    """Exit 2, the id named, the renderable ones named, and no file written.

    The failure mode this catches is SILENCE: an entry with no dump used to
    resolve to no path and the CLI then fell back to DEFAULT_INPUT, so
    ``--structure build_A_series_R --dump-state ...`` exited 0 with a state
    file describing run A's field data under the series-R name. Every
    assertion below is one half of that sentence.
    """
    target = REPO_ROOT / "build" / f"pytest_record_only_{structure_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--structure", structure_id,
         "--dump-state", str(target)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_S,
    )
    assert proc.returncode == 2, (
        f"a record-only --structure must exit 2 rather than fall back to "
        f"another case's dump; got {proc.returncode}\nstdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )
    assert not target.is_file(), (
        f"a refused run must leave no state file behind, and {target} exists"
    )
    stderr = proc.stderr
    assert structure_id in stderr, (
        f"the refusal must name the id that was asked for: {stderr!r}"
    )
    assert "record" in stderr.lower(), (
        f"the refusal must say the entry is record-only: {stderr!r}"
    )
    listed = re.search(r"renderable structures: (.+)", stderr)
    assert listed, f"the refusal must list what CAN be opened: {stderr!r}"
    renderable = [item.strip() for item in listed.group(1).split(",")]
    assert "build_A_50ohm" in renderable, renderable
    assert structure_id not in renderable, (
        f"{structure_id} has no dump and must not be offered as renderable: "
        f"{renderable}"
    )


# --- T12/T13: the load's own trace, and its absence, in the state document ---


def _vis_schema() -> str:
    """The vis schema literal the loader accepts, read from the module emitting it."""
    server = REPO_ROOT / "server"
    if str(server) not in sys.path:
        sys.path.insert(0, str(server))
    import poc_app

    return poc_app.VIS_SCHEMA


def _write_vis_dump(path: Path, *, trace: bool) -> Path:
    """A minimal vis dump: the keys load_vis demands, plus the trace or nothing.

    ``trace=False`` is the dump an older solver wrote - it carries none of the
    ``load_*`` keys at all, which is a DIFFERENT absence from a run that took no
    trace and says so. Only the first is built here.
    """
    import numpy as np

    nt, nx, nz = 3, 6, 4
    nt_x, ny_x = 2, 5
    rng = np.random.default_rng(0)
    payload = {
        "schema": _vis_schema(),
        "ez_ycut": rng.normal(size=(nt, nx, nz)),
        "ez_xcut_near": rng.normal(size=(nt_x, ny_x, nz)),
        "ez_xcut_far": rng.normal(size=(nt_x, ny_x, nz)),
        "t_ns": np.arange(nt) * 1e-3,
        "frame_index": np.arange(nt),
        "frame_index_xcut": np.arange(nt_x) * 2,
        "x_mm": np.linspace(0.0, 5.0, nx),
        "y_mm": np.linspace(-1.0, 1.0, ny_x),
        "z_mm": np.linspace(0.0, 2.0, nz),
        "nx": np.array(nx),
        "ny": np.array(ny_x),
        "nz": np.array(nz),
        "nt": np.array(nt),
        "nt_x": np.array(nt_x),
        "dt_s": np.array(1e-13),
        "cell_m": np.array(1e-5),
        "structure_id": np.array("A"),
        "load_ohm": np.array(50.0),
    }
    if trace:
        payload["load_t_ns"] = np.array([0.0, 0.5, 1.0])
        payload["load_v"] = np.array([-0.85, 0.0, 0.85])
        payload["load_i"] = np.array([-1e-3, 0.0, 1e-3])
        payload["load_trace_present"] = np.array(1)
        payload["load_netlist_json"] = np.array(
            json.dumps({"name": "cut_test", "elements": []})
        )
    np.savez(path, **payload)
    return path


@pytest.fixture(scope="module")
def vis_states(tmp_path_factory):
    """Run ``--input <vis dump> --dump-state`` once per trace case, parse both."""
    root = tmp_path_factory.mktemp("vis_load_series")
    docs = {}
    for name, has_trace in (("traced", True), ("untraced", False)):
        npz = _write_vis_dump(root / f"{name}.npz", trace=has_trace)
        out = root / f"{name}.json"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--input", str(npz),
             "--dump-state", str(out)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_S,
        )
        assert proc.returncode == 0, (
            f"--dump-state on the {name} vis dump exited {proc.returncode}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
        docs[name] = json.loads(
            out.read_text(encoding="utf-8"), parse_constant=_reject_constant
        )
    return docs


def test_t12_vis_document_carries_the_load_trace(vis_states):
    """The vis document names its own version AND ships the recorded series."""
    document = vis_states["traced"]
    assert document["schema"] == "emfit.poc-state/3", (
        "the vis branch gained the load_series keys, so its document is /3; "
        f"the dump declares {document['schema']!r}"
    )
    assert document["format"] == "um3k", document["format"]
    series = document["load_series"]
    assert isinstance(series, dict), (
        "the traced dump produced no load_series block, so the page has no "
        f"trace to draw: {series!r} (reason {document['load_series_reason']!r})"
    )
    assert series["n"] == 3, series
    for key, expected in (
        ("load_t_ns", [0.0, 0.5, 1.0]),
        ("load_v", [-0.85, 0.0, 0.85]),
        ("load_i", [-0.001, 0.0, 0.001]),
    ):
        values = series[key]
        assert values == pytest.approx(expected), (key, values)
        assert all(isinstance(value, float) for value in values), (
            f"{key} left the loader as {[type(v) for v in values]}, not floats: "
            "the document is JSON-serialised for the browser"
        )
    assert series["netlist_name"] == "cut_test", series
    assert document["load_series_reason"] is None, (
        "a dump that carries a trace must not also carry a reason for its "
        f"absence: {document['load_series_reason']!r}"
    )


def test_t13_trace_less_dump_is_null_plus_the_reason_it_is_absent(vis_states):
    """An old dump still opens, and says WHY there is nothing to draw."""
    document = vis_states["untraced"]
    assert document["schema"] == "emfit.poc-state/3", document["schema"]
    assert document["load_series"] is None, (
        "a dump with no load_* keys produced a series: a zero-filled or "
        f"zero-length one would be a picture of a run that never measured it: "
        f"{document['load_series']!r}"
    )
    reason = document["load_series_reason"]
    assert isinstance(reason, str) and reason.strip(), (
        f"the null trace carries no reason: {reason!r}"
    )
    assert "untraced.npz" in reason, (
        f"the reason must name the dump it looked in: {reason!r}"
    )
    assert "before the solver" in reason, (
        "the reason must say the dump PREDATES the trace rather than claiming "
        f"this run skipped it: {reason!r}"
    )


# --- T14: a bare run boots on the volume, not the legacy dump ----------------


def test_t14_bare_run_boots_on_the_reference_volume(tmp_path):
    """No ``--structure``: the id and the frame axis the boot default promises.

    The change this pins is a DEFAULT, so a run that names an id proves nothing
    about it. Both halves are asserted: the id the boot resolved to is the
    example volume, and its document carries a frame axis (``animation``), which
    is what distinguishes it from the legacy station dump - the page a bare run
    used to land on, which has no time axis and prints "no timeline on this
    page".
    """
    if not REFERENCE_NPZ.is_file():
        pytest.skip(f"reference volume absent: {REFERENCE_NPZ}")
    target = tmp_path / "bare_boot.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--dump-state", str(target)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_S,
    )
    assert proc.returncode == 0, (
        f"a bare --dump-state exited {proc.returncode}\nstdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )
    document = json.loads(
        target.read_text(encoding="utf-8"), parse_constant=_reject_constant
    )
    assert document["structure"]["id"] == "reference_sim", (
        "a bare run must boot on the example volume while its npz is on disk; "
        f"the dump resolved to {document['structure']!r} (stderr: "
        f"{proc.stderr!r})"
    )
    assert document["format"] != "legacy", (
        "the boot default must land on a dump with a time axis, not the legacy "
        f"station dump: format is {document['format']!r}"
    )
    animation = document["animation"]
    assert isinstance(animation, dict), (
        "the boot document carries no animation block, so the page would print "
        f"\"no timeline on this page\": {animation!r}"
    )
    assert animation["frames"] > 1 and animation["frames_xcut"] > 1, (
        "a single frame is not a timeline; got "
        f"frames={animation['frames']!r}, frames_xcut={animation['frames_xcut']!r}"
    )
