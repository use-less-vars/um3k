"""``server/step_time.py``: the ONLY bridge between a step and a frame index.

A cut-plane dump stores a subset of the run's steps, and how big that subset is
depends on the stride the dump was written with -- the P0 truth doc found the
same surface at stride 1 (``artifacts/live_run.npz``, 2400 frames) and at
stride 10 (``artifacts/reference_sim_volume.npz``, 240 frames).  Read with the
wrong stride the array is not slow, it is WRONG: frame 50 is step 50 in one
dump and step 500 in the other.  The claims, one per test:

* frame -> step -> frame round-trips for every stored frame, at every stride;
* ``frame_for_step`` floors (sample at or before the step) and ``is_sampled``
  is true exactly on the stored steps;
* a step outside the window answers ``None`` -- before the first sample, one
  past the last, or on an empty surface -- and never raises;
* the two REAL dumps disagree about the same step, in both directions, and no
  frame index carried across them reproduces the step it came from;
* every windowing field is validated, so a bad spec fails at construction;
* ``time_of`` is ``t0 + step*dt`` including a non-zero ``t0``.

Nothing here boots the viewer, imports numpy or touches OpenGL: the dumps are
only opened as zip archives to read their ``.npy`` shape headers.
"""
from __future__ import annotations

import ast
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

import step_time  # noqa: E402 - the path above is what makes it importable
from step_time import (  # noqa: E402
    SurfaceSpec,
    TimeBase,
    frame_for_step,
    is_sampled,
    sample_steps,
    step_for_frame,
)

WORKSPACE = Path(__file__).resolve().parents[1]
LIVE_DUMP = WORKSPACE / "artifacts" / "live_run.npz"
REF_DUMP = WORKSPACE / "artifacts" / "reference_sim_volume.npz"


def _npy_shape(npz_path: Path, key: str) -> tuple[int, ...]:
    """The shape of ``key``'s array, from the archive's ``.npy`` header alone."""
    with zipfile.ZipFile(npz_path) as archive:
        with archive.open(f"{key}.npy") as handle:
            assert handle.read(6) == b"\x93NUMPY"
            major = handle.read(1)[0]
            handle.read(1)
            size = int.from_bytes(handle.read(2 if major == 1 else 4), "little")
            header = ast.literal_eval(handle.read(size).decode("latin1").strip())
    return tuple(header["shape"])


# --- 1. round trip --------------------------------------------------------- IO

@pytest.mark.parametrize("stride", [1, 2, 3, 10])
@pytest.mark.parametrize("offset", [0, 7])
@pytest.mark.parametrize("n_frames", [0, 1, 5, 240])
def test_frame_step_round_trips_for_every_stored_frame(stride, offset, n_frames):
    spec = SurfaceSpec(axis="y", position=0.35, stride=stride, offset=offset,
                       n_frames=n_frames)
    assert len(sample_steps(spec)) == spec.frame_count() == n_frames
    for frame in range(n_frames):
        step = step_for_frame(spec, frame)
        assert step == offset + frame * stride
        assert frame_for_step(spec, step) == frame
        assert is_sampled(spec, step)


# --- 2. floor, and is_sampled exactly on the samples --------------------- IO

def test_frame_for_step_floors_to_the_sample_at_or_before():
    spec = SurfaceSpec(axis="x", position=-1.0, stride=10, offset=0, n_frames=5)
    # samples live at 0, 10, 20, 30, 40
    assert [frame_for_step(spec, s) for s in range(0, 10)] == [0] * 10
    assert frame_for_step(spec, 10) == 1
    assert frame_for_step(spec, 19) == 1        # floors, never rounds to 20
    assert frame_for_step(spec, 20) == 2
    assert frame_for_step(spec, 39) == 3
    assert frame_for_step(spec, 40) == 4        # the last sample itself
    assert is_sampled(spec, 40)
    # floor with an offset: the first sample is at 7, so step 6 is before it
    shifted = SurfaceSpec(axis="x", position=-1.0, stride=10, offset=7, n_frames=3)
    assert sample_steps(shifted) == (7, 17, 27)
    assert frame_for_step(shifted, 7) == 0
    assert frame_for_step(shifted, 16) == 0
    assert frame_for_step(shifted, 17) == 1
    assert frame_for_step(shifted, 27) == 2


@pytest.mark.parametrize("stride,offset", [(1, 0), (4, 3), (10, 0)])
def test_is_sampled_is_true_exactly_on_the_stored_steps(stride, offset):
    spec = SurfaceSpec(axis="z", position=2.5, stride=stride, offset=offset,
                       n_frames=6)
    stored = set(sample_steps(spec))
    assert len(stored) == 6
    for step in range(-5, offset + 6 * stride + 5):
        assert is_sampled(spec, step) is (step in stored), step
    # the samples ascend and are as wide as the spec says they span
    assert list(sample_steps(spec)) == sorted(stored)
    assert max(stored) - min(stored) == stride * (spec.frame_count() - 1)


# --- 3. boundaries: None, not IndexError --------------------------------- IO

def test_a_step_before_the_first_sample_answers_none():
    spec = SurfaceSpec(axis="x", position=0.0, stride=10, offset=20, n_frames=3)
    assert frame_for_step(spec, 19) is None
    assert frame_for_step(spec, 0) is None
    assert frame_for_step(spec, -1) is None
    assert is_sampled(spec, 19) is False
    assert frame_for_step(spec, 20) == 0


def test_the_last_sample_and_one_past_it():
    spec = SurfaceSpec(axis="x", position=0.0, stride=10, offset=0, n_frames=240)
    last = step_for_frame(spec, spec.frame_count() - 1)
    assert last == 2390
    assert frame_for_step(spec, last) == 239
    assert is_sampled(spec, last)
    # one past the last sample is PAST the dump, and asking is still legal
    with pytest.raises(IndexError):
        step_for_frame(spec, spec.frame_count())
    assert frame_for_step(spec, last + 1) is None
    assert is_sampled(spec, last + 1) is False
    # the unpainted tail of the window: step_count() over-covers by (stride-1)
    assert spec.step_count() == 2400
    assert frame_for_step(spec, 2399) is None


def test_an_empty_surface_answers_none_everywhere():
    empty = SurfaceSpec(axis="z", position=0.0, stride=4, offset=2, n_frames=0)
    assert empty.frame_count() == 0
    assert empty.step_count() == 0
    assert sample_steps(empty) == ()
    for step in (-1, 0, 2, 100):
        assert frame_for_step(empty, step) is None
        assert is_sampled(empty, step) is False
    with pytest.raises(IndexError):
        step_for_frame(empty, 0)


def test_step_for_frame_rejects_frames_outside_the_dump():
    spec = SurfaceSpec(axis="y", position=0.1, stride=1, offset=0, n_frames=3)
    assert step_for_frame(spec, 0) == 0
    assert step_for_frame(spec, 2) == 2
    for bad in (-1, 3, 10_000):
        with pytest.raises(IndexError):
            step_for_frame(spec, bad)


# --- 4. the two REAL dumps: same surface, different stride -------------- IO

def test_xcut_dumps_differ_in_stride_but_are_the_same_surface():
    """P0 truth: the x-cut near surface at stride 1 (2400) and stride 10 (240)."""
    if not (LIVE_DUMP.is_file() and REF_DUMP.is_file()):
        pytest.skip("real x-cut dumps not present in artifacts/")
    live = _npy_shape(LIVE_DUMP, "ez_xcut_near")
    ref = _npy_shape(REF_DUMP, "ez_xcut_near")
    # same surface over the same grid slice -- ONLY the step axis is resampled
    assert live[1:] == ref[1:] == (212, 22)
    assert live[0] == 2400 and ref[0] == 240

    s1 = SurfaceSpec(axis="x", position=0.0, stride=1, offset=0, n_frames=live[0])
    s10 = SurfaceSpec(axis="x", position=0.0, stride=10, offset=0, n_frames=ref[0])
    assert s1.frame_count() == 2400 and s10.frame_count() == 240
    assert s1.step_count() == s10.step_count() == 2400   # same steps covered


def test_the_same_step_is_a_different_frame_in_each_dump_both_ways():
    """Read at the wrong stride the array is not slow, it is WRONG."""
    if not (LIVE_DUMP.is_file() and REF_DUMP.is_file()):
        pytest.skip("real x-cut dumps not present in artifacts/")
    s1 = SurfaceSpec(axis="x", position=0.0, stride=1, offset=0,
                     n_frames=_npy_shape(LIVE_DUMP, "ez_xcut_near")[0])
    s10 = SurfaceSpec(axis="x", position=0.0, stride=10, offset=0,
                      n_frames=_npy_shape(REF_DUMP, "ez_xcut_near")[0])

    for step in (0, 9, 10, 50, 500, 1234, 2390):
        assert frame_for_step(s1, step) == step
        assert frame_for_step(s10, step) == step // 10
    # the two agree only where stride 1 and stride 10 coincide
    for step in (10, 50, 500, 1234, 2390):
        assert frame_for_step(s1, step) != frame_for_step(s10, step)

    # frame 50 of one dump is NOT frame 50 of the other: different steps
    assert step_for_frame(s1, 50) == 50
    assert step_for_frame(s10, 50) == 500
    assert step_for_frame(s1, 50) != step_for_frame(s10, 50)

    # a carried frame index does NOT round-trip across specs: the stride-10
    # dump's frame 5 is step 50, but read against the stride-1 spec it claims
    # step 5 -- silently the wrong tick, which is the bug this module forbids.
    frame_from_s10 = frame_for_step(s10, 50)
    assert frame_from_s10 == 5
    assert step_for_frame(s10, frame_from_s10) == 50          # its own spec: fine
    assert step_for_frame(s1, frame_from_s10) == 5            # the other: WRONG
    assert step_for_frame(s1, frame_from_s10) != 50
    # and the other direction: stride-1 frame 50 is step 500 under stride 10
    frame_from_s1 = frame_for_step(s1, 50)
    assert frame_from_s1 == 50
    assert step_for_frame(s10, frame_from_s1) == 500
    assert step_for_frame(s10, frame_from_s1) != frame_from_s1

    # the stride-10 dump stops answering long before the stride-1 one does
    assert frame_for_step(s1, 2399) == 2399
    assert frame_for_step(s10, 2399) is None
    assert is_sampled(s10, 2399) is False


# --- 5. validation ------------------------------------------------------- IO

@pytest.mark.parametrize("kwargs", [
    {"axis": "w"},                       # not one of x/y/z
    {"axis": "X"},                       # case is not forgiven
    {"axis": ""},
    {"stride": 0},                       # a stride of zero stores nothing sane
    {"stride": -1},
    {"stride": -10},
    {"offset": -1},                      # steps are not negative
    {"n_frames": -1},
])
def test_a_bad_spec_raises_ValueError_at_construction(kwargs):
    base = dict(axis="x", position=0.0, stride=1, offset=0, n_frames=4)
    base.update(kwargs)
    with pytest.raises(ValueError):
        SurfaceSpec(**base)


def test_the_legal_edges_do_not_raise():
    for spec in (
        SurfaceSpec(axis="x", position=0.0, stride=1, offset=0, n_frames=0),
        SurfaceSpec(axis="y", position=0.0, stride=1, offset=0, n_frames=1),
        SurfaceSpec(axis="z", position=-3.5, stride=10, offset=0, n_frames=240),
        SurfaceSpec(axis="x", position=1e6, stride=2400, offset=2399, n_frames=2),
    ):
        assert spec.frame_count() == spec.n_frames


# --- 6. TimeBase --------------------------------------------------------- IO

def test_time_of_is_t0_plus_step_times_dt():
    clock = TimeBase(dt=2.5e-12)
    assert clock.t0 == 0.0
    assert clock.time_of(0) == 0.0
    assert clock.time_of(1) == 2.5e-12
    assert clock.time_of(2400) == pytest.approx(6.0e-9)

    shifted = TimeBase(dt=4.0e-13, t0=1.5e-9)
    assert shifted.t0 == 1.5e-9
    assert shifted.time_of(0) == 1.5e-9          # t0 != 0 is the first step's time
    assert shifted.time_of(2500) == pytest.approx(1.5e-9 + 1.0e-9)
    assert shifted.time_of(0) != TimeBase(dt=4.0e-13).time_of(0)


def test_time_is_derived_from_a_step_never_from_a_frame():
    """A frame has no time until a spec turns it into a step."""
    assert list(TimeBase.__dataclass_fields__) == ["dt", "t0"]  # no ns field
    assert "time_of" in dir(TimeBase(dt=1e-12))
    assert not hasattr(TimeBase(dt=1e-12), "time_of_frame")
    clock = TimeBase(dt=1e-12, t0=0.0)
    s10 = SurfaceSpec(axis="x", position=0.0, stride=10, offset=0, n_frames=240)
    frame = frame_for_step(s10, 50)
    assert frame == 5
    # the same frame index means a different TIME under a different stride
    s1 = SurfaceSpec(axis="x", position=0.0, stride=1, offset=0, n_frames=2400)
    assert clock.time_of(step_for_frame(s10, frame)) == 50e-12
    assert clock.time_of(step_for_frame(s1, frame)) == 5e-12
    assert clock.time_of(step_for_frame(s10, frame)) != clock.time_of(
        step_for_frame(s1, frame))


# --- 7. the module's own promise ---------------------------------------- IO

def test_the_module_is_stdlib_only():
    """No numpy, no VTK, no pyvista, no app: it must import in a bare image."""
    source = (WORKSPACE / "server" / "step_time.py").read_text()
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "dataclasses", "typing"}, imported
    assert step_time.AXES == ("x", "y", "z")
