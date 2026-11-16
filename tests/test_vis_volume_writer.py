"""The OPTIONAL ``|E|`` volume of the emfit-vis dump: written only when asked.

The volume is ADDITIVE and GATED on ``--volume-stride``.  A run that did not ask
for one must write the archive it always wrote, key for key -- ``vis_selftest``
refuses an unexpected key, and every reader that walks the archive would
otherwise start counting frames twice -- so the absence test below is the
contract the file already had, not politeness.

The volume is TWO numberings over one record and they are easy to confuse: axis
0 of ``e_abs_volume`` is a FRAME index, ``e_abs_volume_step_index`` is the
1-BASED STEP number of each of those frames, and the stride is in frames.  So
the tests below store values that ARE the step numbers.  A shift of one -- the
frame number, the 0-based frame, or a plain off-by-one -- changes the number and
fails, which is the only way to tell a correct mapping from three that all
index arrays of the right length.

The size guard is checked through the WRITER, not through its helper alone,
because the reason it exists is that a refusal arriving after the 1400 s march
has already spent the run.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries tests/test_poc_playback.py adds, so
        # `import poc_app` resolves from server/poc_app.py
        sys.path.insert(0, _p)

import poc_app  # noqa: E402 - the path above is what makes it importable


def _load_run_build_a():
    """Import ``evidence/termination/run_build_A.py`` as a module."""
    evidence = REPO_ROOT / "evidence" / "termination"
    if str(evidence) not in sys.path:
        sys.path.insert(0, str(evidence))
    import run_build_A

    return run_build_A


# The smallest geometry that still has the real shapes: two x-cut frames out of
# six, and an int32 step index.  Small on purpose -- nothing here is about size.
NX, NY, NZ = 5, 4, 3
NT = 6
XCUT_STRIDE = 3
DT_S = 7.626299478123987e-13
CELL_M = 0.4e-3


def _dump(path, *, volume=None, volume_stride=None, volume_frames=None,
          nx=NX, ny=NY, nz=NZ, nt=NT):
    """One dump, through the real writer, with the optional volume handed in.

    ``frame_index`` carries the 1-BASED step number of each kept frame, exactly
    as ``_VisRecorder`` fills it (``stepper.n``), and the volume's frames are
    every ``volume_stride``-th of THOSE -- already sub-sampled by the caller, as
    the recorder hands them over.
    """
    run_build_A = _load_run_build_a()
    x_mm = np.arange(nx) * CELL_M * 1e3
    fi = np.arange(1, nt + 1, dtype=np.int32)
    time_s = fi.astype(np.float64) * DT_S
    sel = np.arange(0, nt, XCUT_STRIDE)
    ez = np.repeat(fi.astype(np.float32)[:, None, None], nx * nz, axis=1)
    ez = ez.reshape(nt, nx, nz)
    side = np.zeros((sel.size, ny, nz), dtype=np.float32)
    return run_build_A.write_vis_dump(
        path, ez_ycut=ez, ez_xcut_near=side, ez_xcut_far=side,
        frame_index=fi, frame_index_xcut=fi[sel], frame_time_s=time_s,
        dt_s=DT_S, nx=nx, ny=ny, nz=nz, cell_m=CELL_M, j_cut=1,
        dump_stride=1, nsteps=nt, f_pulse_hz=15.0e9,
        xcut_near_mm=float(x_mm[1]), xcut_far_mm=float(x_mm[-1]),
        structure_id="A", load_ohm=50.0,
        volume_e_abs=volume, volume_stride=volume_stride,
        volume_frames=volume_frames)


# -- 1. the volume comes back out of the file it went into --------------------


def test_the_volume_round_trips_through_the_writer_and_the_loader(tmp_path):
    ramp = (np.arange(3, dtype=np.float32) + 0.5).reshape(3, 1, 1, 1)
    volume = np.repeat(np.repeat(np.repeat(ramp, NX, 1), NY, 2), NZ, 3)
    path = tmp_path / "volume.npz"
    _dump(path, volume=volume, volume_stride=2)

    info = poc_app.load_vis(path)

    assert info["e_abs_volume"].dtype == np.float32
    assert info["e_abs_volume"].shape == (3, NX, NY, NZ)
    # Exactly, not approximately: 0.5/1.5/2.5 are float32-representable, so a
    # conversion or a scaling applied on the way through would show up here.
    assert np.array_equal(info["e_abs_volume"], np.asarray(volume, np.float32))
    assert info["e_abs_volume_stride"] == 2


# -- 2. the step axis is the STEP, not the frame ------------------------------


def test_the_step_axis_is_the_step_number_and_a_one_frame_shift_fails(tmp_path):
    stride = 2
    fi = np.arange(1, NT + 1, dtype=np.int32)
    # Every volume frame is filled with the step number it must carry: 1, 3, 5.
    # The 0-based frame indices (0, 2, 4) and a +-1 shift (2, 4, 6) are both
    # different numbers, so neither can pass this.
    kept = fi[::stride]
    volume = np.repeat(np.repeat(np.repeat(
        kept.astype(np.float32)[:, None, None, None], NX, 1), NY, 2), NZ, 3)
    path = tmp_path / "steps.npz"
    _dump(path, volume=volume, volume_stride=stride)

    info = poc_app.load_vis(path)
    values = info["e_abs_volume"][:, 0, 0, 0]

    assert list(info["e_abs_volume_step_index"]) == [1, 3, 5]
    assert np.array_equal(values, np.asarray([1.0, 3.0, 5.0], np.float32))
    assert not np.array_equal(values, np.asarray([2.0, 4.0, 6.0], np.float32))
    assert not np.array_equal(values, np.asarray([0.0, 2.0, 4.0], np.float32))


def test_the_recorder_and_the_writer_agree_on_which_steps_the_frames_are(tmp_path):
    """Recorder -> payload -> writer -> loader, with values that are not constant.

    The fake stepper's field is ``3n``/``4n``/``12n`` per component, so
    ``|E| = sqrt(9 + 16 + 144) * n = 13n`` exactly (169 is a float32 integer):
    each frame's voxels therefore NAME the step the recorder took it at, and a
    volume frame taken one step early or late reads 13n +- 13.
    """
    run_build_A = _load_run_build_a()
    recorder = run_build_A._VisRecorder(
        nx=NX, ny=NY, nz=NZ, nt=NT, nt_x=2, stride=1, j_cut=1,
        ix_near=1, ix_far=3, xcut_stride=XCUT_STRIDE, volume_stride=2)
    for n in range(1, NT + 1):
        recorder(_fake_stepper(n))

    payload = recorder.payload()

    assert payload["volume_stride"] == 2
    assert [int(v) for v in payload["frame_index"][::2]] == [1, 3, 5]
    assert np.array_equal(payload["volume_e_abs"][:, 0, 0, 0],
                          np.asarray([13.0, 39.0, 65.0], np.float32))

    path = tmp_path / "chain.npz"
    _dump(path, volume=payload["volume_e_abs"],
          volume_stride=payload["volume_stride"])
    info = poc_app.load_vis(path)
    assert list(info["e_abs_volume_step_index"]) == [1, 3, 5]
    assert np.array_equal(info["e_abs_volume"][:, 0, 0, 0],
                          np.asarray([13.0, 39.0, 65.0], np.float32))


def _fake_stepper(n: int):
    """A stepper-shaped object: the three E blocks the recorder slices, at step n.

    Only the attributes ``_VisRecorder`` reads are here, and the block shapes are
    the real ones (``(nx, ny+1, nz)``, ``(nx+1, ny, nz)``, ``(nx+1, ny+1, nz)``),
    so this exercises the same slicing a solve would.
    """
    n_ex = NX * (NY + 1) * NZ
    n_ey = (NX + 1) * NY * NZ
    n_ez = (NX + 1) * (NY + 1) * NZ
    cc = SimpleNamespace(
        nx=NX, ny=NY, nz=NZ, nxn=NX + 1, nyn=NY + 1, nzn=NZ,
        off_ex=0, n_ex=n_ex, off_ey=n_ex, n_ey=n_ey,
        off_ez=n_ex + n_ey, n_ez=n_ez, n_edges=n_ex + n_ey + n_ez)
    e = np.zeros(cc.n_edges, dtype=float)
    e[cc.off_ex:cc.off_ex + cc.n_ex] = 3.0 * n
    e[cc.off_ey:cc.off_ey + cc.n_ey] = 4.0 * n
    e[cc.off_ez:cc.off_ez + cc.n_ez] = 12.0 * n
    return SimpleNamespace(cc=cc, e=e, n=n, dt=DT_S, time=n * DT_S)


# -- 3. no stride, no volume, no key -----------------------------------------


def test_a_dump_without_a_volume_writes_no_volume_key_and_no_zeros(tmp_path):
    path = tmp_path / "plain.npz"
    _dump(path)

    with np.load(str(path), allow_pickle=False) as data:
        volume_keys = [key for key in data.files if "volume" in key]

    assert volume_keys == []
    info = poc_app.load_vis(path)
    # None, not a zero-filled array: "this dump has no volume" and "this dump
    # has a volume of zeroes" must stay two different answers all the way out.
    assert info["e_abs_volume"] is None
    assert info["e_abs_volume_step_index"] is None
    assert info["e_abs_volume_stride"] is None


def test_the_self_tests_exact_key_set_still_passes(tmp_path):
    """``vis_selftest`` refuses an unexpected key, so this is the absence proof.

    It raises ``SystemExit`` on any failed check, ``extra keys`` included.
    """
    run_build_A = _load_run_build_a()
    summary = run_build_A.vis_selftest(tmp_path / "selftest.npz")

    assert all(check["ok"] for check in summary["checks"]), summary["checks"]
    assert summary["nt"] == 300


def test_the_recorder_allocates_nothing_without_a_stride_and_caps_when_asked():
    run_build_A = _load_run_build_a()
    kwargs = dict(nx=NX, ny=NY, nz=NZ, nt=NT, nt_x=2, stride=1, j_cut=1,
                  ix_near=1, ix_far=3, xcut_stride=XCUT_STRIDE)

    off = run_build_A._VisRecorder(**kwargs)
    assert off.volume_stride is None
    assert off.e_abs_volume is None
    assert "volume_e_abs" not in off.payload()

    on = run_build_A._VisRecorder(**kwargs, volume_stride=3)
    assert on.e_abs_volume.shape == (2, NX, NY, NZ)   # ceil(6 / 3)
    assert set(on.payload()) - set(off.payload()) == {"volume_e_abs",
                                                      "volume_stride"}

    capped = run_build_A._VisRecorder(**kwargs, volume_stride=3,
                                      volume_frames=1)
    # The cap is on the ALLOCATION, which is what makes --volume-frames a
    # memory ceiling and not only a tail trim.
    assert capped.e_abs_volume.shape == (1, NX, NY, NZ)


# -- 4. the size guard refuses, and says what to turn -----------------------


def test_an_over_budget_volume_is_refused_and_the_message_names_both_flags(
        tmp_path):
    # 4 frames of 200 x 200 x 100 float32 = 64.0 MB, over the 48 MB volume
    # budget.  ``broadcast_to`` so the test pays for the SHAPE the guard is
    # asked about and not for the payload it never gets to write.
    n_vol, nx, ny, nz = 4, 200, 200, 100
    volume = np.broadcast_to(np.float32(1.0), (n_vol, nx, ny, nz))
    path = tmp_path / "big.npz"

    with pytest.raises(SystemExit) as excinfo:
        _dump(path, volume=volume, volume_stride=1, nx=nx, ny=ny, nz=nz, nt=4)

    text = str(excinfo.value.code)
    assert "--volume-stride" in text, text
    assert "--volume-frames" in text, text
    assert "64.0 MB" in text, text
    assert "48 MB volume budget" in text, text
    assert not path.exists()


# -- 5. a volume with no stride is refused, not guessed ---------------------


def test_a_volume_handed_in_with_no_stride_is_refused_and_nothing_is_written(
        tmp_path):
    path = tmp_path / "nostride.npz"

    with pytest.raises(SystemExit) as excinfo:
        _dump(path, volume=np.zeros((3, NX, NY, NZ), dtype=np.float32))

    text = str(excinfo.value.code)
    assert "volume_stride" in text, text
    assert "nothing is written" in text, text
    assert not path.exists()


# -- 6. the loader refuses a volume the planes would be drawn wrong from ----


def _doctor(tmp_path, mutate, name="doctored.npz"):
    """A good dump, then ``mutate`` applied to its arrays, re-saved."""
    path = tmp_path / "good.npz"
    _dump(path, volume=np.zeros((3, NX, NY, NZ), np.float32), volume_stride=2)
    with np.load(str(path), allow_pickle=False) as data:
        arrays = {key: data[key] for key in data.files}
    mutate(arrays)
    out = tmp_path / name
    np.savez_compressed(str(out), **arrays)
    return out


def test_the_loader_refuses_a_volume_that_is_not_on_the_planes_node_grid(
        tmp_path, capsys):
    path = _doctor(
        tmp_path,
        lambda arrays: arrays.__setitem__(
            "e_abs_volume", np.zeros((3, NX, NY, NZ + 1), np.float32)))

    with pytest.raises(SystemExit) as excinfo:
        poc_app.load_vis(path)

    assert excinfo.value.code == 2
    assert "e_abs_volume has shape" in capsys.readouterr().err


def test_the_loader_refuses_a_volume_whose_step_axis_is_another_length(
        tmp_path, capsys):
    path = _doctor(
        tmp_path,
        lambda arrays: arrays.__setitem__(
            "e_abs_volume_step_index",
            arrays["e_abs_volume_step_index"][:-1]))

    with pytest.raises(SystemExit) as excinfo:
        poc_app.load_vis(path)

    assert excinfo.value.code == 2
    assert "cannot be read at two lengths" in capsys.readouterr().err
