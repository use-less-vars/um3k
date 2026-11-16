"""The station axis: where each captured plane actually sits on the line.

Claims pinned by this file:

1. ``_station_axis_mm`` resolves the x of every captured station from the
   artefacts, in one documented order - ``info["station_x_m"]``, then the
   record's ``s11.station_phasors.x_m``, then ``geometry.station_cells``, then
   ``line.station_fit_cells`` - and only then falls back to the stated uniform
   ``i * cell`` assumption. A step is accepted ONLY when it is ``n_st`` finite
   numbers, so a short, long, non-numeric or non-finite sequence is skipped
   rather than believed.
2. On the shipped Build A record the nine stations are 10.4 mm .. 20.0 mm in
   1.2 mm steps, NOT ``i * 0.4 mm``: the study snaps each wanted station to the
   nearest grid cell.
3. ``build_grid`` puts the volume on that axis - x bounds 10.4 .. 20.0 mm -
   while the assumption puts the same nine planes over the port end, 0 .. 3.2 mm.
4. ``_cut_layout`` / ``build_cut_sheets`` carry the same axis into the cuts.
5. The load marker (20.0 mm) lies ON the captured slab; the S11 port marker
   (3.2 mm = ix_port 8 x 0.4 mm) lies upstream of it. That is the record, not
   a bug, and the test says so.
6. ``load_dump`` publishes ``info["station_x_m"]`` only when the archive holds
   exactly one finite number per captured plane; a short, long or non-finite
   array is stored as nothing at all, not as a smaller lie.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

import poc_app  # noqa: E402

# The shipped Build A artefacts. The dump is the field data, the JSON beside it
# is the study record: the axis lives in the RECORD, the dump carries none.
NPZ = REPO_ROOT / "evidence" / "termination" / "build_A_50ohm_p51_ghostwave_fields.npz"
RECORD_JSON = (
    REPO_ROOT / "evidence" / "termination" / "build_A_50ohm_p51_ghostwave.json"
)

CELL_M = 0.0004  # 0.4 mm, the shipped grid cell
CELL_MM = CELL_M * 1e3
N_ST = 9  # captured stations in the shipped dump

# The exact wording of the assumed-axis provenance: the UI prints it, so a
# silent reword would stop the page admitting the axis is a guess.
ASSUMED_SRC = "ASSUMED uniform i*cell (no station axis recorded)"


# --- helpers ---------------------------------------------------------------


def _fake_info(n_st: int = N_ST) -> dict:
    """The smallest ``info`` the axis resolver reads: a plane and the cell."""
    plane = np.zeros((n_st, 3, 2), dtype=complex)
    plane[:] = 1.0 + 0.0j
    return {
        poc_app.PLANE_KEY: plane,
        "cell_m": CELL_M,
        "nx": 4,
        "ny": 3,
        "nz": 2,
        "nstep": 0,
    }


def _assumed_axis(n_st: int = N_ST) -> list:
    return [i * CELL_MM for i in range(n_st)]


def _write_dump(path: Path, *, n_st: int = 5, station_x_m=None) -> Path:
    """A minimal dump the ``load_dump`` ingest path accepts verbatim."""
    arrays = {
        poc_app.PLANE_KEY: np.zeros((n_st, 3, 2), dtype=complex),
        "nstep": np.int64(1),
        "nx": np.int64(4),
        "ny": np.int64(3),
        "nz": np.int64(2),
        "cell_m": np.float64(CELL_M),
    }
    if station_x_m is not None:
        arrays["station_x_m"] = station_x_m
    np.savez(path, **arrays)
    return path


@pytest.fixture(scope="module")
def build_a():
    """``(info, record)`` for the shipped Build A dump, or a skip if absent."""
    if not NPZ.is_file():
        pytest.skip(f"field dump absent: {NPZ}")
    if not RECORD_JSON.is_file():
        pytest.skip(f"study record absent: {RECORD_JSON}")
    return poc_app.load_dump(NPZ), poc_app.load_record(NPZ)


# --- 1. the resolution order, and what it refuses ---------------------------


def test_the_dump_axis_beats_every_sidecar():
    info = _fake_info()
    info["station_x_m"] = np.arange(N_ST) * 1e-3  # metres
    record = {
        "s11": {"station_phasors": {"x_m": [0.9] * N_ST}},
        "geometry": {"station_cells": [70] * N_ST},
        "line": {"station_fit_cells": [60] * N_ST},
    }
    stations, src = poc_app._station_axis_mm(info, record)
    assert src == "station_x_m"
    assert stations == pytest.approx([float(i) for i in range(N_ST)], abs=1e-9)


def test_the_record_axis_is_preferred_in_the_documented_order():
    info = _fake_info()
    record = {
        "s11": {"station_phasors": {"x_m": [0.001 * (i + 1) for i in range(N_ST)]}},
        "geometry": {"station_cells": [26 + 3 * i for i in range(N_ST)]},
        "line": {"station_fit_cells": [26 + 3 * i for i in range(N_ST)]},
    }
    stations, src = poc_app._station_axis_mm(info, record)
    assert src == "s11.station_phasors.x_m"
    assert stations == pytest.approx([float(i + 1) for i in range(N_ST)], abs=1e-9)

    # Drop the s11 phasors: the CELL INDEX list is next, and it is scaled by the
    # cell, not by a metre->mm factor.
    del record["s11"]
    stations, src = poc_app._station_axis_mm(info, record)
    assert src == "geometry.station_cells"
    assert stations == pytest.approx(
        [(26 + 3 * i) * CELL_MM for i in range(N_ST)], abs=1e-9
    )

    # And with the geometry list gone, the fit cells are the last recorded word.
    del record["geometry"]
    stations, src = poc_app._station_axis_mm(info, record)
    assert src == "line.station_fit_cells"
    assert stations == pytest.approx(
        [(26 + 3 * i) * CELL_MM for i in range(N_ST)], abs=1e-9
    )


def test_with_no_artefact_at_all_the_axis_says_it_is_assumed():
    stations, src = poc_app._station_axis_mm(_fake_info())
    assert src == ASSUMED_SRC
    assert stations == pytest.approx(_assumed_axis(), abs=1e-9)


@pytest.mark.parametrize(
    "bad",
    [
        [0.01] * (N_ST - 1),  # one station short
        [0.01] * (N_ST + 1),  # one station long
        [0.01] * (N_ST - 1) + [float("nan")],  # a hole in the axis
        [0.01] * (N_ST - 1) + [float("inf")],  # an axis running to infinity
        "0.01" * N_ST,  # a string is not a sequence of numbers
        0.01,  # a scalar is not a sequence at all
        {"x": 0.01},  # a dict is not an axis
        ["a"] * N_ST,  # entries that are not numbers
        None,  # the key present but empty
    ],
)
def test_a_step_that_is_not_n_finite_numbers_is_skipped(bad):
    info = _fake_info()
    info["station_x_m"] = bad
    record = {"s11": {"station_phasors": {"x_m": [0.005] * N_ST}}}
    stations, src = poc_app._station_axis_mm(info, record)
    # The refusal falls THROUGH to the next source instead of raising or of
    # handing back a sequence of the wrong length.
    assert src == "s11.station_phasors.x_m"
    assert stations == pytest.approx([5.0] * N_ST, abs=1e-9)


def test_the_eight_entry_fit_axis_is_dropped_for_nine_stations():
    # ``line.station_fit_cells`` drops the load station, so on this record it
    # has 8 entries for 9 planes: a shorter axis is not a smaller axis.
    info = _fake_info()
    record = {"line": {"station_fit_cells": [26, 29, 32, 35, 38, 41, 44, 47]}}
    stations, src = poc_app._station_axis_mm(info, record)
    assert src == ASSUMED_SRC
    assert stations == pytest.approx(_assumed_axis(), abs=1e-9)


@pytest.mark.parametrize("record", [None, "not a record", 42, [], {}])
def test_a_record_that_is_not_a_record_only_costs_the_axis(record):
    stations, src = poc_app._station_axis_mm(_fake_info(), record)
    assert src == ASSUMED_SRC
    assert stations == pytest.approx(_assumed_axis(), abs=1e-9)


# --- 2. the shipped record, end to end -------------------------------------


def test_build_a_stations_are_the_recorded_ones_not_the_cell_steps(build_a):
    info, record = build_a
    stations, src = poc_app._station_axis_mm(info, record)
    assert src == "s11.station_phasors.x_m"
    assert len(stations) == N_ST
    # 10.4 .. 20.0 mm in 1.2 mm steps - twenty-six cells, not one.
    assert stations == pytest.approx([10.4 + 1.2 * i for i in range(N_ST)], abs=1e-9)
    assert stations[0] == pytest.approx(10.4, abs=1e-9)
    assert stations[-1] == pytest.approx(20.0, abs=1e-9)
    # The assumption would have stacked the same planes over the port end.
    assert stations != pytest.approx(_assumed_axis(), abs=1e-9)


def test_build_a_layout_reads_load_and_both_port_planes_from_the_record(build_a):
    info, record = build_a
    assert info[poc_app.PLANE_KEY].shape == (N_ST, 213, 22)
    assert poc_app._cell_mm(info) == pytest.approx(0.4, abs=1e-9)

    layout = poc_app._plane_layout(info, record)
    assert layout["n_st"] == N_ST
    assert layout["cell_mm"] == pytest.approx(0.4, abs=1e-9)
    assert layout["stations_src"] == "s11.station_phasors.x_m"
    assert layout["stations_mm"] == pytest.approx(
        [10.4 + 1.2 * i for i in range(N_ST)], abs=1e-9
    )
    # The load sits at the end of the line (cell 50 = 20.0 mm).
    assert layout["src_load"] == "geometry.loads[0].x"
    assert layout["x_load_mm"] == pytest.approx(20.0, abs=1e-9)
    assert layout["ix_load"] == pytest.approx(50.0, abs=1e-9)
    # The S11 port is cell 8 = 3.2 mm, upstream of the first captured station.
    assert layout["src_s11"] == "geometry.ix_port"
    assert layout["x_s11_mm"] == pytest.approx(3.2, abs=1e-9)
    # The S21 plane is cell 51 = 20.4 mm, i.e. past the load - the record says
    # the field there has collapsed, which is a validity flag, not a re-aim.
    assert layout["src_s21"] == "s21_plane.x_m"
    assert layout["x_s21_mm"] == pytest.approx(20.4, abs=1e-9)
    assert layout["s21_valid"] is False
    # The slice drawn is the captured plane nearest the S11 marker.
    assert layout["slice_index"] == 0
    assert layout["slice_index"] == min(
        range(N_ST),
        key=lambda i: abs(layout["stations_mm"][i] - layout["x_s11_mm"]),
    )


# --- 3. the grid is built on that axis -------------------------------------


def test_build_grid_spans_the_recorded_stations(build_a):
    import pyvista as pv

    info, record = build_a
    stations, _src = poc_app._station_axis_mm(info, record)
    grid = poc_app.build_grid(info, stations)

    assert isinstance(grid, pv.ImageData)  # the axis is uniform: 1.2 mm steps
    assert tuple(grid.dimensions) == (N_ST, 213, 22)
    assert tuple(grid.spacing) == pytest.approx((1.2, 0.4, 0.4), abs=1e-9)
    assert tuple(grid.origin) == pytest.approx((10.4, 0.0, 0.0), abs=1e-9)
    bounds = tuple(grid.bounds)
    assert bounds[0] == pytest.approx(10.4, abs=1e-9)
    assert bounds[1] == pytest.approx(20.0, abs=1e-9)
    # y/z really are one cell per sample, from 0.
    assert bounds[2] == pytest.approx(0.0, abs=1e-9)
    assert bounds[3] == pytest.approx(212 * 0.4, abs=1e-9)
    assert bounds[4] == pytest.approx(0.0, abs=1e-9)
    assert bounds[5] == pytest.approx(21 * 0.4, abs=1e-9)
    assert grid.point_data["ez_abs"].shape == (N_ST * 213 * 22,)
    assert grid.point_data["ez_real"].shape == (N_ST * 213 * 22,)


def test_build_grid_without_the_axis_still_uses_the_stated_assumption(build_a):
    info, _record = build_a
    grid = poc_app.build_grid(info)  # no axis handed in

    assert tuple(grid.spacing) == pytest.approx((0.4, 0.4, 0.4), abs=1e-9)
    assert tuple(grid.origin) == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    bounds = tuple(grid.bounds)
    assert bounds[0] == pytest.approx(0.0, abs=1e-9)
    assert bounds[1] == pytest.approx(3.2, abs=1e-9)  # the port end, not 20.0


def test_a_non_uniform_axis_becomes_an_explicit_point_grid(build_a):
    import pyvista as pv

    info, record = build_a
    stations, _src = poc_app._station_axis_mm(info, record)
    nudged = list(stations)
    nudged[3] += 0.05  # one station off the 1.2 mm ladder
    grid = poc_app.build_grid(info, nudged)

    assert not isinstance(grid, pv.ImageData)  # no single spacing fits
    assert isinstance(grid, pv.StructuredGrid)
    bounds = tuple(grid.bounds)
    assert bounds[0] == pytest.approx(10.4, abs=1e-9)
    assert bounds[1] == pytest.approx(20.0, abs=1e-9)
    assert grid.n_points == N_ST * 213 * 22
    assert grid.point_data["ez_abs"].shape == (N_ST * 213 * 22,)


# --- 4. the cuts carry the same axis ---------------------------------------


def test_cut_layout_without_the_axis_uses_the_cell_stack(build_a):
    info, _record = build_a
    cut = poc_app._cut_layout(info)
    assert cut["n_st"] == N_ST
    assert cut["n_j"] == 213 and cut["n_k"] == 22
    assert cut["j"] == 106 and cut["k"] == 11
    assert cut["x_lo_mm"] == pytest.approx(0.0, abs=1e-9)
    assert cut["x_hi_mm"] == pytest.approx(3.2, abs=1e-9)
    assert cut["dx_mm"] == pytest.approx(0.4, abs=1e-9)
    assert cut["y_mm"] == pytest.approx(106 * 0.4, abs=1e-9)
    assert cut["z_mm"] == pytest.approx(11 * 0.4, abs=1e-9)


def test_cut_layout_on_the_recorded_axis_spans_the_slab(build_a):
    info, record = build_a
    stations, _src = poc_app._station_axis_mm(info, record)
    cut = poc_app._cut_layout(info, stations_mm=stations)
    assert cut["x_lo_mm"] == pytest.approx(stations[0], abs=1e-9)
    assert cut["x_hi_mm"] == pytest.approx(stations[-1], abs=1e-9)
    assert cut["x_lo_mm"] == pytest.approx(10.4, abs=1e-9)
    assert cut["x_hi_mm"] == pytest.approx(20.0, abs=1e-9)
    assert cut["dx_mm"] == pytest.approx(1.2, abs=1e-9)


def test_cut_sheets_sit_on_the_recorded_axis_and_carry_the_plane_data(build_a):
    import pyvista as pv

    info, record = build_a
    stations, _src = poc_app._station_axis_mm(info, record)
    cut = poc_app._cut_layout(info, stations_mm=stations)
    sheets = poc_app.build_cut_sheets(info, cut)

    # Each entry is ``(axis, sheet, clim)``: the colour range is the sheet's own
    # and is pinned by the volume-view tests, not here.
    assert [label for label, _sheet, _clim in sheets] == ["y", "z"]
    plane = info[poc_app.PLANE_KEY]
    for (label, sheet, _clim), dims, expected in (
        (sheets[0], (N_ST, 1, 22), np.abs(plane[:, cut["j"], :])),
        (sheets[1], (N_ST, 213, 1), np.abs(plane[:, :, cut["k"]])),
    ):
        assert isinstance(sheet, pv.ImageData), label
        assert tuple(sheet.dimensions) == dims, label
        # The x spacing is the STATION step, and the sheet starts at the first
        # captured station - not at the port end of the line.
        assert tuple(sheet.spacing) == pytest.approx((1.2, 0.4, 0.4), abs=1e-9), label
        assert sheet.origin[0] == pytest.approx(10.4, abs=1e-9), label
        assert tuple(sheet.bounds)[0] == pytest.approx(10.4, abs=1e-9), label
        assert tuple(sheet.bounds)[1] == pytest.approx(20.0, abs=1e-9), label
        np.testing.assert_allclose(
            sheet.point_data["ez_abs"], expected.ravel(order="F"), rtol=0, atol=0
        )


# --- 5. the markers against the slab ---------------------------------------


def test_the_load_marker_lies_on_the_captured_slab(build_a):
    info, record = build_a
    stations, _src = poc_app._station_axis_mm(info, record)
    layout = poc_app._plane_layout(info, record)
    cut = poc_app._cut_layout(info, stations_mm=stations)

    assert cut["x_lo_mm"] <= layout["x_load_mm"] <= cut["x_hi_mm"]
    # It coincides with the LAST captured station: the load is where the
    # measurement stops, which is why the slab ends there.
    assert layout["x_load_mm"] == pytest.approx(stations[-1], abs=1e-9)


def test_the_s11_marker_is_upstream_of_the_slab_and_that_is_legitimate(build_a):
    """The port plane is NOT one of the captured planes, and is not meant to be.

    The S11 marker is the excited port at ix_port 8 x 0.4 mm = 3.2 mm, while the
    study snapped its WANTED stations forward to cells 26, 29, ... 50 - so the
    first captured plane is 10.4 mm. Drawing that marker outside the slab is the
    honest picture of this record; moving it onto the slab would be the bug.
    ``slice_index`` absorbs the gap by drawing the nearest captured plane.
    """
    info, record = build_a
    stations, _src = poc_app._station_axis_mm(info, record)
    layout = poc_app._plane_layout(info, record)
    cut = poc_app._cut_layout(info, stations_mm=stations)

    assert layout["x_s11_mm"] == pytest.approx(3.2, abs=1e-9)
    assert layout["x_s11_mm"] < cut["x_lo_mm"]
    assert layout["x_s11_mm"] < stations[0]
    # The gap is real, not a rounding artefact: it is several station steps.
    assert stations[0] - layout["x_s11_mm"] == pytest.approx(10.4 - 3.2, abs=1e-9)
    assert stations[0] - layout["x_s11_mm"] > cut["dx_mm"]
    # ...and the S21 marker is past the load, which the record flags as invalid.
    assert layout["x_s21_mm"] > layout["x_load_mm"]
    assert layout["x_s21_mm"] == pytest.approx(20.4, abs=1e-9)
    assert layout["s21_valid"] is False
    assert layout["slice_index"] == 0


# --- 6. what the dump itself may contribute --------------------------------


def test_load_dump_publishes_a_well_formed_station_axis(tmp_path):
    metres = [0.005 + 0.001 * i for i in range(5)]
    dump = _write_dump(tmp_path / "d.npz", n_st=5, station_x_m=metres)
    info = poc_app.load_dump(dump)

    assert info["path"] == dump
    assert info[poc_app.PLANE_KEY].shape == (5, 3, 2)
    assert "station_x_m" in info
    stations, src = poc_app._station_axis_mm(info)
    assert src == "station_x_m"
    assert stations == pytest.approx([5.0, 6.0, 7.0, 8.0, 9.0], abs=1e-9)


def test_load_dump_without_the_axis_stores_no_placeholder(tmp_path):
    dump = _write_dump(tmp_path / "d.npz", n_st=5)
    info = poc_app.load_dump(dump)

    assert "station_x_m" not in info
    stations, src = poc_app._station_axis_mm(info)
    assert src == ASSUMED_SRC
    assert stations == pytest.approx([i * 0.4 for i in range(5)], abs=1e-9)


@pytest.mark.parametrize(
    "station_x_m",
    [
        [0.005] * 4,  # short: 4 numbers for 5 planes
        [0.005] * 6,  # long: 6 numbers for 5 planes
        [0.005, 0.006, float("nan"), 0.008, 0.009],  # a hole
        [0.005, 0.006, float("inf"), 0.008, 0.009],  # no finite bound
    ],
    ids=["short", "long", "nan", "inf"],
)
def test_load_dump_refuses_an_axis_that_is_not_one_finite_x_per_plane(
    tmp_path, station_x_m
):
    dump = _write_dump(tmp_path / "d.npz", n_st=5, station_x_m=station_x_m)
    info = poc_app.load_dump(dump)

    # No key at all - not a truncated, re-ordered or NaN-padded stand-in.
    assert "station_x_m" not in info
    assert info[poc_app.PLANE_KEY].shape == (5, 3, 2)
    stations, src = poc_app._station_axis_mm(info)
    assert src == ASSUMED_SRC
    assert stations == pytest.approx([i * 0.4 for i in range(5)], abs=1e-9)


def test_a_dump_axis_beats_the_record_beside_it(tmp_path):
    dump = _write_dump(tmp_path / "d.npz", n_st=5, station_x_m=[0.002] * 5)
    info = poc_app.load_dump(dump)
    record = {"s11": {"station_phasors": {"x_m": [0.030] * 5}}}

    stations, src = poc_app._station_axis_mm(info, record)
    assert src == "station_x_m"
    assert stations == pytest.approx([2.0] * 5, abs=1e-9)
