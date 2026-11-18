"""The page's clock, and the sample that clock puts on screen, in one owner.

The viewer used to answer "what time is it" and "which stored frame is on
screen" in a dozen places: the frame total was re-derived at seventeen call
sites, and the position-to-volume mapping lived in a private plan dict that one
function built and every consumer re-read. One of those answers was wrong rather
than merely scattered - the number of positions was the SELECTED family's frame
count, so y-cut carried 2400 positions and x-cut 240, and the same play rate
advanced ten times as far per tick after a plane switch. A sweep therefore took
ten times as long depending on which picture the operator was looking at.

This module makes the master clock the FINEST recorded step axis, measured in
SOLVER STEPS (the dump's own 1-based numbering), and demotes the plane family to
a VIEW of it. The position count, the step at each position and the duration of
a sweep are then properties of the recording and cannot change when the picture
does. The REJECTED alternative is the one that shipped: count positions per
family, which is not a clock at all but a per-picture scale factor.

Two clocks are kept apart on purpose and are never added or divided by each
other. :class:`Timeline` counts solver steps; :class:`Layer` counts STORED
SAMPLES of one recorded series - 2400 y-cut frames, 240 x-cut frames and 24
volume frames on the reference archive. :meth:`Layer.index_for` is the only
place the two meet.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass

import numpy as np

__all__ = ["Frame", "Layer", "Timeline", "VOLUME_LAYER", "XCUT_LAYER", "YCUT_LAYER"]

YCUT_LAYER = "ycut"
XCUT_LAYER = "xcut"
VOLUME_LAYER = "volume"


def _monotonic(values) -> tuple[int, ...] | None:
    """One recorded step axis as ints, or None when it cannot be read.

    The port of ``poc_app._monotonic_axis``, kept semantically identical because
    two readers of the same dump must not disagree about whether its axis exists:
    None for an absent, empty, non-finite or BACKWARDS axis, and non-decreasing
    otherwise. None is this module's "no mapping can be defended".

    The REJECTED alternative is to sort a backwards axis into order. That reads as
    a repair and is not one: a dump whose captures run backwards is a broken
    record, and silently reordering it pairs frame 1 with the step of frame N.
    Equal neighbours are tolerated - a restart can legitimately record the same
    step twice - but nothing here invents an order the file did not state.
    """
    if values is None:
        return None
    try:
        axis = np.asarray(values).ravel()
    except (TypeError, ValueError):
        return None
    if axis.size < 1:
        return None
    try:
        as_float = axis.astype(float)
    except (TypeError, ValueError):
        return None
    if not bool(np.all(np.isfinite(as_float))):
        return None
    if as_float.size > 1 and bool(np.any(np.diff(as_float) < 0.0)):
        return None
    return tuple(int(value) for value in as_float.astype(int))


def _positive_int(value) -> int | None:
    """``value`` as a positive int, or None - the "not recorded" of a count."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _median(values: list[int]) -> int:
    """The median of a non-empty list of ints, as an int."""
    return int(round(float(np.median(np.asarray(values, dtype=float)))))


@dataclass(frozen=True)
class Layer:
    """One recorded series and which of its stored samples a solver step shows.

    ``steps`` are the solver steps the dump says its samples were captured at,
    one entry per stored frame and in the dump's own numbering - measured, never
    ``step // stride``: a restart or a dropped capture leaves a cadence that
    arithmetic would misread, and the reference writer states a stride of 4
    beside an axis that actually runs 1, 101, 201 in steps of 100.

    ``count`` and ``decimation`` are derived, not carried: a decimation is a
    MEASURED property of the axis (the median positive difference), so a layer
    cannot claim a cadence its frames do not have.
    """

    name: str
    steps: tuple[int, ...]

    @property
    def count(self) -> int:
        """How many samples this layer stored."""
        return len(self.steps)

    @property
    def decimation(self) -> int:
        """How many solver steps ONE stored sample spans, measured.

        The median of the positive differences between consecutive steps, so one
        dropped sample or one restart cannot restate the cadence of the whole
        film. 1 when it cannot be measured - fewer than two samples - which is
        also what makes the decimation clause DISAPPEAR instead of printing a
        "x1" over an undecimated layer.
        """
        if self.count < 2:
            return 1
        diffs = sorted(
            int(b) - int(a) for a, b in zip(self.steps, self.steps[1:]) if int(b) > int(a)
        )
        if not diffs:
            return 1
        return max(1, _median(diffs))

    def index_for(self, step: int) -> int:
        """The stored sample on screen at ``step``: SAMPLE AND HOLD, clamped.

        The LAST sample captured at or before ``step``, which is what a real
        instrument displays, and 0 when the step precedes the first capture.

        The REJECTED alternative is the NEAREST capture, which is what the viewer
        did until now. It is rejected because at position 50 of the reference
        archive - step 51, with captures at 1 and 101 - nearest shows the sample
        from step 101, i.e. the picture is drawing data from the FUTURE. A viewer
        used to read physics off the picture cannot do that: a held sample says
        "the last thing I actually measured", while a nearest one says "something
        that has not happened yet" and cannot be distinguished from it by eye.
        """
        if not self.steps:
            return 0
        try:
            wanted = int(step)
        except (TypeError, ValueError):
            return 0
        found = bisect_right(self.steps, wanted) - 1
        return max(0, min(self.count - 1, found))

    def span(self, index: int) -> tuple[int, int]:
        """The (first_step, last_step) during which stored sample ``index`` shows.

        Under sample-and-hold a frame owns everything up to the next capture.
        The LAST frame has no successor to bound it, so it owns one decimation
        window of its own rather than an invented infinity: that is the furthest
        the clock can run before a capture the dump does not have.
        """
        if not self.steps:
            return (0, 0)
        position = max(0, min(self.count - 1, int(index)))
        first = int(self.steps[position])
        if position + 1 < self.count:
            last = int(self.steps[position + 1]) - 1
        else:
            last = first + self.decimation - 1
        return (first, max(first, last))

    def label(self, index: int, step: int | None = None) -> str:
        """The layer's half of the on-screen sentence, e.g. "Frame 2 of 24".

        The wording is the viewer's existing one, preserved byte for byte because
        dozens of tests and the operator's own reading habit match on it:
        "Frame 4 of 24, Volume Decimated x100 @ step 301". The decimation clause
        rides ONLY on a decimated layer, so an undecimated one is never labelled
        with a cadence it does not have.

        ``step`` is the position's own step, and it is what makes " (held)" mean
        something: a stored frame is HELD at every position after its capture
        until the next one, and the suffix says so only when asked about such a
        position. Without ``step`` there is no claim to make, so none is added -
        which is also the legacy two-argument call.
        """
        if not self.steps:
            return "Frame 0 of 0"
        position = max(0, min(self.count - 1, int(index)))
        text = f"Frame {position + 1} of {self.count}"
        decimation = self.decimation
        if decimation > 1:
            noun = "Volume Decimated" if self.name == VOLUME_LAYER else "Decimated"
            text += f", {noun} \u00d7{decimation} @ step {int(self.steps[position])}"
        if step is not None:
            try:
                held = int(step) > int(self.steps[position])
            except (TypeError, ValueError):
                held = False
            if held:
                text += " (held)"
        return text


@dataclass(frozen=True)
class Frame:
    """Everything the page needs to know about ONE player position.

    ``position`` is the slider value, ``step`` the solver step it stands on,
    ``t_s``/``t_ns`` the recorded time of that step (NaN when the dump recorded
    no usable time base), ``layer_indices`` the stored sample of every layer that
    this position puts on screen, and ``layer_changed`` which of those layers
    ADVANCE here - the one fact a redraw that rebuilds a layer needs and a
    redraw that only swaps a scalar array must not pay for.
    """

    position: int
    step: int
    t_s: float
    t_ns: float
    layer_indices: dict[str, int]
    layer_changed: dict[str, bool]


@dataclass(frozen=True)
class Timeline:
    """The page's one clock: ``nsteps`` solver positions and the layers on them.

    ``steps`` is the MASTER axis - the recorded step of each player position, in
    order - and it is the finest stored axis the dump carries, so the player
    steps the recording at the resolution it was recorded at. ``dt_s`` and
    ``t_ns`` are the recorded time base and are None when the dump recorded none:
    an invented time base would turn "no time recorded" into a number, which is
    exactly the dishonesty the label is supposed to remove.
    """

    nsteps: int
    steps: tuple[int, ...]
    dt_s: float | None = None
    t_ns: tuple[float, ...] | None = None
    layers: dict[str, Layer] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if len(self.steps) != self.nsteps:
            raise ValueError(
                f"steps has {len(self.steps)} entries but nsteps is {self.nsteps}; "
                "the axis and its length are one record"
            )
        if self.layers is None:
            object.__setattr__(self, "layers", {})

    @property
    def last_index(self) -> int:
        """The highest legal position; 0 on an axis of one."""
        return max(0, int(self.nsteps) - 1)

    @classmethod
    def from_dump(cls, info: dict) -> "Timeline | None":
        """Read a viewer ``info`` dict, or None for a page with no timeline.

        THE PRECEDENCE, in one place: ``frame_index`` (recorded every solver
        step), else ``frame_index_xcut`` (every tenth), else
        ``e_abs_volume_step_index`` (every hundredth), else the bare frame count
        ``nt``/``nt_x`` expanded to 1..n. The finest axis wins because it is the
        only one on which a position can mean one solver step; taking a coarser
        one would quantise the clock to a recording decision.

        None is "no timeline", NEVER "zero frames": a bare field dump records no
        frame axis at all and gets no clock, rather than a clock of length zero
        that every consumer then has to guard against dividing by.
        """
        if not isinstance(info, dict):
            return None
        axes = {
            YCUT_LAYER: _monotonic(info.get("frame_index")),
            XCUT_LAYER: _monotonic(info.get("frame_index_xcut")),
        }
        if info.get("e_abs_volume") is not None:
            axes[VOLUME_LAYER] = _monotonic(info.get("e_abs_volume_step_index"))
        else:
            axes[VOLUME_LAYER] = None
        layers = {
            name: Layer(name=name, steps=steps)
            for name, steps in axes.items()
            if steps is not None
        }
        master = axes[YCUT_LAYER] or axes[XCUT_LAYER] or axes[VOLUME_LAYER]
        if master is None:
            counted = _positive_int(info.get("nt")) or _positive_int(info.get("nt_x"))
            if counted is None:
                return None
            master = tuple(range(1, counted + 1))
        recorded_dt = info.get("dt_s")
        try:
            dt_s = float(recorded_dt)
        except (TypeError, ValueError):
            dt_s = float("nan")
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            dt_s = None
        times = info.get("t_ns")
        t_ns = None
        if times is not None:
            try:
                as_float = np.asarray(times, dtype=float).ravel()
            except (TypeError, ValueError):
                as_float = None
            if as_float is not None and as_float.size == len(master):
                t_ns = tuple(float(value) for value in as_float)
        return cls(
            nsteps=len(master), steps=tuple(master), dt_s=dt_s, t_ns=t_ns, layers=layers
        )

    def clamp(self, position) -> int:
        """``position`` as a legal index: an int, never negative, never past the end.

        Tolerant on purpose, because the writers of ``state.frame`` are a slider,
        four keyboard triggers and a play loop, and a page must not die because
        one of them handed over a None or a float. Junk is 0 - the first picture -
        rather than an exception or a silent 900-frame skip.
        """
        try:
            value = int(round(float(position)))
        except (TypeError, ValueError, OverflowError):
            return 0
        return max(0, min(self.last_index, value))

    def resolve(self, position) -> Frame:
        """The :class:`Frame` at ``position``: one step, one time, every layer.

        ``layer_changed`` is True where a layer's stored sample ADVANCES, which
        includes position 0 - that is where its first sample appears. It is
        computed from the PREVIOUS position's step rather than from the index, so
        an axis with a gap in it still answers correctly.
        """
        index = self.clamp(position)
        step = int(self.steps[index])
        seconds = self._seconds(index)
        previous_step = int(self.steps[index - 1]) if index > 0 else None
        indices: dict[str, int] = {}
        changed: dict[str, bool] = {}
        for name, layer in self.layers.items():
            held = layer.index_for(step)
            indices[name] = held
            changed[name] = previous_step is None or layer.index_for(previous_step) != held
        return Frame(
            position=index,
            step=step,
            t_s=seconds,
            t_ns=seconds * 1e9,
            layer_indices=indices,
            layer_changed=changed,
        )

    def _seconds(self, index: int) -> float:
        """The recorded time of ``index`` in seconds, or NaN when none was recorded.

        The dumped ``t_ns`` wins because it is the solver's own clock; ``dt_s``
        times the number of positions elapsed is the fallback, and it is indexed
        from 0 because a dump's first capture is its zero.
        """
        if self.t_ns is not None and 0 <= index < len(self.t_ns):
            value = float(self.t_ns[index])
            if math.isfinite(value):
                return value * 1e-9
        if self.dt_s is not None:
            return float(index) * float(self.dt_s)
        return float("nan")

    def layer(self, name: str) -> Layer | None:
        """The named layer, or None when this dump does not carry it."""
        return self.layers.get(name)

    def layer_index(self, name: str, position) -> int | None:
        """The stored sample of ``name`` on screen at ``position``, or None."""
        layer = self.layers.get(name)
        if layer is None:
            return None
        return layer.index_for(int(self.steps[self.clamp(position)]))

    def caption(self, position) -> str:
        """The clock half of the label: "step 1001 / 2400 - t = 0.763 ns".

        The step and its denominator come from the recording, so the sentence
        cannot be read as a click count; the time is the recorded one, and
        "not recorded" is printed rather than a zero that would look like a
        measurement.
        """
        frame = self.resolve(position)
        if math.isfinite(frame.t_ns):
            tail = f"t = {frame.t_ns:.3f} ns"
        else:
            tail = "t = not recorded"
        return f"step {frame.step} / {int(self.nsteps)} \u00b7 {tail}"

    def layer_label(self, name: str, position) -> str | None:
        """The named layer's half of the label, or None when there is no such layer."""
        layer = self.layers.get(name)
        if layer is None:
            return None
        index = self.clamp(position)
        step = int(self.steps[index])
        return layer.label(layer.index_for(step), step)

    def plan(self, mode: str) -> dict | None:
        """The LEGACY position-to-indices dict, or None when there is no volume.

        Exactly the keys ``poc_app._build_volume_player_plan`` returns today -
        ``steps``, ``frames``, ``plane``, ``volume`` - so the producer can be
        swapped without touching a single consumer.

        ``mode`` is accepted and deliberately ignored: it names a VIEW. Handing a
        different dict to the x-cut page is how the old code made a plane switch
        change the playback speed by ten, and no argument of this method may do
        that again. The REJECTED alternative is to keep per-mode plans, which is
        two clocks pretending to be one.
        """
        volume = self.layers.get(VOLUME_LAYER)
        if volume is None or volume.count < 1:
            return None
        master = np.asarray(self.steps, dtype=float)
        samples = np.asarray(volume.steps, dtype=float)
        held = np.clip(
            np.searchsorted(samples, master, side="right") - 1, 0, volume.count - 1
        )
        return {
            "steps": tuple(int(step) for step in self.steps),
            "frames": int(self.nsteps),
            "plane": tuple(range(int(self.nsteps))),
            "volume": tuple(int(index) for index in held),
        }
