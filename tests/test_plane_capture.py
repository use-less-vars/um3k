"""``plane_capture`` reaches the ``EMFIT_BIN_DUMP`` record on **both** drives.

The flag accumulates the four single-tone phasor blocks of the station
cross-sections on the time loop a tone and a pulse both run, but the record
they are written into is reached from the pulse path only -- the dump belongs
to the broadband sweep, and a tone has no sweep.  A ``cw`` run with the flag on
therefore came back with no ``plane_*`` key anywhere.

The fix writes the plane record separately, so the two claims these tests make
are the ones that matter for a frozen record:

* with the flag **off** nothing new happens on either drive -- a tone still
  writes no file at all, and a pulse's payload is untouched;
* with the flag **on** the payload is what it was, plus exactly the ``plane_*``
  keys -- nothing added, removed or altered besides them.  For a tone "what it
  was" is the record ``_dump_bins`` writes for an empty sweep, and the test
  builds that record from the same call, so the comparison is against the
  function's own output rather than against another run's.

The default coupon mesh (62 x 44 x 22 at 0.4 mm) is the geometry this is about,
so no mesh knob is overridden; ``nsteps`` is the only thing shortened.
"""

import numpy as np
import pytest

from emfit import studies

#: The four cross-section blocks and the shape each must have, given the
#: transverse cell counts: ``E_y``/``H_z`` sit on the dual layers in z and
#: ``E_z``/``H_y`` on the nodes, each with one cross-section per station
#: (``n_stations = 9`` by default).
BLOCKS = {
    "plane_Ey": lambda ny, nz: (9, ny, nz + 1),
    "plane_Hz": lambda ny, nz: (9, ny, nz + 1),
    "plane_Ez": lambda ny, nz: (9, ny + 1, nz),
    "plane_Hy": lambda ny, nz: (9, ny + 1, nz),
}

#: The whole plane key set: the four blocks, where they were taken, and the
#: scalars that formed the sum.  Named exactly, so a renamed key fails here.
PLANE_KEYS = frozenset({
    "plane_Ey", "plane_Ez", "plane_Hy", "plane_Hz",
    "plane_station_cells", "plane_station_x",
    "plane_f", "plane_dt", "plane_n_samples", "plane_convention",
})

#: Short runs: a tone needs a couple of hundred steps to hand back a fitted
#: impedance, a pulse a few hundred more for the packet to cross the line and
#: fade.  Both are long enough that the record is a real one, and short enough
#: to keep the file cheap.
NSTEPS = {"cw": 200, "pulse": 900}


def _run(monkeypatch, tmp_path, excite, plane_capture):
    """Run one short study; return ``(result, path, payload or None)``."""
    path = tmp_path / f"{excite}-{plane_capture}.npz"
    monkeypatch.setenv(studies.BIN_DUMP_ENV, str(path))
    result = studies.microstrip_wave(excite=excite,
                                     plane_capture=plane_capture,
                                     nsteps=NSTEPS[excite])
    if not path.exists():
        return result, path, None
    with np.load(path) as loaded:
        return result, path, {name: loaded[name] for name in loaded.files}


def _base_of(payload):
    return {name: value for name, value in payload.items()
            if not name.startswith("plane_")}


def _assert_same_payload(got, want, *, what):
    """Key for key, shape for shape, dtype for dtype, and value for value."""
    assert set(got) == set(want), what
    for name, value in want.items():
        assert np.shape(got[name]) == np.shape(value), name
        assert np.asarray(got[name]).dtype == np.asarray(value).dtype, name
        assert np.array_equal(
            np.asarray(got[name]), np.asarray(value), equal_nan=True), name


def _empty_sweep_baseline(tmp_path, result):
    """The record ``_dump_bins`` writes for a tone's (absent) sweep, no planes.

    This is what a tone's dump would have contained had the plane blocks been
    written beside the sweep all along: the call the fix makes, minus the
    ``planes`` argument whose effect is what the test is measuring.
    """
    n_stations = len(result.geometry["station_cells"])
    path = tmp_path / "baseline.npz"
    studies._dump_bins(
        str(path), freqs=np.empty(0),
        spectra=np.empty((0, 2 * n_stations + 3)),
        station_x=result.station_x, n_stations=n_stations,
        x_port=float(result.geometry["ix_port"] * result.geometry["cell"]),
        bins=())
    with np.load(path) as loaded:
        return {name: loaded[name] for name in loaded.files}


# --------------------------------------------------------------------------- #
# the claims about the record
# --------------------------------------------------------------------------- #
def test_a_tone_with_the_flag_off_still_writes_no_file(monkeypatch, tmp_path):
    """The frozen invocation: ``EMFIT_BIN_DUMP`` set, no flag, no file."""
    _, path, payload = _run(monkeypatch, tmp_path, "cw", False)
    assert payload is None
    assert not path.exists()


def test_a_tone_with_the_flag_on_adds_the_blocks_and_nothing_else(
        monkeypatch, tmp_path):
    result, _, payload = _run(monkeypatch, tmp_path, "cw", True)
    assert payload is not None
    base = _empty_sweep_baseline(tmp_path, result)

    # Nothing the tone's record already said may move, and the sweep half stays
    # empty: the fix adds the blocks, it does not invent a bin for the tone.
    _assert_same_payload(_base_of(payload), base, what="tone base payload")
    assert payload["f"].shape == (0,)
    assert payload["v"].shape == (0, 9)

    plane_keys = {name for name in payload if name.startswith("plane_")}
    assert plane_keys == set(PLANE_KEYS)
    assert set(payload) == set(base) | set(PLANE_KEYS)


def test_a_pulse_with_the_flag_on_adds_the_blocks_and_nothing_else(
        monkeypatch, tmp_path):
    _, _, off = _run(monkeypatch, tmp_path, "pulse", False)
    _, _, on = _run(monkeypatch, tmp_path, "pulse", True)
    assert off is not None and on is not None

    assert not any(name.startswith("plane_") for name in off)
    _assert_same_payload(_base_of(on), off, what="pulse base payload")

    plane_keys = {name for name in on if name.startswith("plane_")}
    assert plane_keys == set(PLANE_KEYS)


# --------------------------------------------------------------------------- #
# what the blocks themselves are
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("excite", ["cw", "pulse"])
def test_the_flag_on_writes_every_block_on_both_drives(
        monkeypatch, tmp_path, excite):
    result, _, payload = _run(monkeypatch, tmp_path, excite, True)
    assert payload is not None

    # The default coupon, unmodified: this is the mesh the shapes assert.
    geometry = result.geometry
    assert (geometry["nx"], geometry["ny"], geometry["nz"]) == (62, 44, 22)
    assert geometry["excite"] == excite

    ny, nz = geometry["ny"], geometry["nz"]
    for name, shape in BLOCKS.items():
        block = payload[name]
        assert block.shape == shape(ny, nz), name
        assert block.dtype == np.complex128, name
        # A capture that never ran would still be a correctly shaped block of
        # zeros; the sum runs on real fields, so it cannot be identically zero.
        assert np.any(block != 0.0), name

    samples = payload["plane_n_samples"]
    assert samples > 0
    assert int(samples) == geometry["n_acc"]
    assert float(payload["plane_dt"]) == pytest.approx(geometry["dt"])
    assert np.asarray(payload["plane_station_cells"]).tolist() == (
        geometry["station_cells"])
    assert np.asarray(payload["plane_station_x"]).shape == (9,)
