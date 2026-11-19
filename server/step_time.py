"""Step is the only time base that crosses an API boundary.

A step is the simulation's integer leapfrog counter; a frame is only an index
into one surface's stored array, so it means nothing without that surface's
stride and offset.  Time is derived from a step and the run's ``dt``, never
stored, and nothing here converts a frame straight to seconds: go
frame -> step -> time, so the stride that made the frame stays visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

#: The three cut-plane normals the viewer offers (poc_app.py's station axes).
AXES = ("x", "y", "z")


@dataclass(frozen=True)
class SurfaceSpec:
    """How ONE stored surface array is sampled from the step axis.

    ``axis``/``position`` name the cut; ``stride``/``offset`` say which steps
    were kept.  Frame ``f`` of this surface was captured at step
    ``offset + f * stride``, and no other mapping is legal: the same array read
    with the wrong stride is a different (wrong) surface, not a resampling of
    this one.
    """

    axis: str
    position: float
    stride: int = 1
    offset: int = 0
    n_frames: int = 0

    def __post_init__(self) -> None:
        if self.axis not in AXES:
            raise ValueError(f"axis must be one of {AXES!r}, got {self.axis!r}")
        if self.stride < 1:
            raise ValueError(f"stride must be >= 1, got {self.stride!r}")
        if self.offset < 0:
            raise ValueError(f"offset must be >= 0, got {self.offset!r}")
        if self.n_frames < 0:
            raise ValueError(f"n_frames must be >= 0, got {self.n_frames!r}")

    def frame_count(self) -> int:
        """Stored samples: the length of the dump's frame axis (``n_frames``)."""
        return self.n_frames

    def step_count(self) -> int:
        """Steps spanned by the window: ``n_frames * stride``.

        NOT the same number as :meth:`frame_count` whenever ``stride > 1``: the
        window ``[offset, offset + step_count())`` is as wide as the sampling
        covers, but only every ``stride``-th step in it was kept, so a stride-10
        window of 240 samples spans 2400 steps.  For ``stride == 1`` the two
        agree.  The window also counts the unpainted gap after the last stored
        sample (steps ``last + 1 .. offset + step_count() - 1``), which
        :func:`frame_for_step` answers with ``None``.
        """
        return self.n_frames * self.stride


@dataclass(frozen=True)
class TimeBase:
    """The run's clock: ``dt`` seconds per step, the first step at ``t0``.

    There is deliberately no nanosecond field and no frame-side accessor: the
    solver's step index plus ``dt`` is the whole record of time, and a frame has
    no time of its own until a :class:`SurfaceSpec` turns it into a step.
    """

    dt: float
    t0: float = 0.0

    def time_of(self, step: int) -> float:
        """Seconds at ``step``: ``t0 + step * dt``."""
        return self.t0 + step * self.dt


def step_for_frame(spec: SurfaceSpec, frame: int) -> int:
    """The step at which ``frame`` was stored: ``offset + frame * stride``.

    Raises ``IndexError`` for a frame outside ``[0, n_frames)`` -- a frame that
    was never stored has no step, and inventing one (by extrapolating past the
    dump) is exactly the bug this module exists to make loud.
    """
    if frame < 0 or frame >= spec.n_frames:
        raise IndexError(
            f"frame {frame} outside [0, {spec.n_frames}) for {spec.axis}-cut "
            f"at {spec.position} (stride {spec.stride})"
        )
    return spec.offset + frame * spec.stride


def frame_for_step(spec: SurfaceSpec, step: int) -> Optional[int]:
    """FLOOR: the frame whose step is at or before ``step``; ``None`` if none.

    Rounding is toward the start of the run, never to nearest: for
    ``offset=0, stride=10``, step 19 answers frame 1 (the sample at step 10),
    step 20 answers frame 2, and step 9 answers frame 0.  ``None`` means "this
    dump says nothing about that step" and is returned for a step before the
    first stored sample, for a step after the last one, and for a surface with
    no frames at all -- it is never an ``IndexError``, because asking about a
    step is always a legal question.
    """
    if spec.n_frames == 0 or step < spec.offset:
        return None
    last = spec.offset + (spec.n_frames - 1) * spec.stride
    if step > last:
        return None
    return (step - spec.offset) // spec.stride


def is_sampled(spec: SurfaceSpec, step: int) -> bool:
    """True iff ``step`` is exactly one of the stored sample steps."""
    if spec.n_frames == 0 or step < spec.offset:
        return False
    delta = step - spec.offset
    if delta % spec.stride:
        return False
    return delta // spec.stride < spec.n_frames


def sample_steps(spec: SurfaceSpec) -> tuple[int, ...]:
    """Every stored step, ascending: ``offset, offset+stride, ...``."""
    return tuple(spec.offset + f * spec.stride for f in range(spec.n_frames))
