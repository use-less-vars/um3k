"""One period of a reconstructed field, as a looping GIF.

A run of ``emfit.studies.microstrip_wave`` hands out a **phasor**: one complex
amplitude per node of a plane, at a single frequency (``slice_ez``, shape
``(nxn, nyn)``).  The field at time ``t`` is that phasor times
``exp(s j omega t)``, so one period is ``n_frames`` samples of the real part --
:func:`frame_arrays` -- and the animation is those frames played back.

The colour limits are computed **once** from the whole phasor
(:func:`colour_limits`) and reused for every frame.  A per-frame autoscale would
renormalise each instant and hide exactly what the animation is for: the
amplitude rising and falling through the period.

Phase convention
----------------
The phasor comes out of ``emfit.ports.DftAccumulator``, whose accumulation line
(``emfit/ports.py:661``) is

    ``phase = np.exp(-2.0j * np.pi * self.freqs * n * self.dt)``

used as ``S[f] += w(n) * values[n] * exp(-2j pi f n dt)`` (docstring,
``emfit/ports.py:569``).  Summing against ``exp(-j omega t)`` extracts the
amplitude of the ``exp(+j omega t)`` term, so ``spectrum[0]`` is the complex
``A`` in ``Re{A exp(+j omega n dt)}``: the engineering ``exp(+j omega t)``
convention, the same one ``0.5 Re(conj(E) H)`` in :mod:`emfit.plane_phasor`
implies.

Spatially, a forward wave -- travelling toward ``+x``, away from the port at low
``x`` -- is ``exp(-1j * beta * x)`` throughout the repo (``emfit/ports.py:1671``,
and ``travelling_waves`` at ``emfit/ports.py:19``).  Together those give the
physical field of a forward wave as

    ``Re{A exp(-j beta x) exp(+j omega t)} = |A| cos(omega t - beta x)``

whose crest sits at ``beta x = omega t`` and therefore moves toward ``+x`` as
time grows -- what a viewer watching a wave launched at the port expects.

Advancing the phasor in time is therefore a multiplication by the *same*
exponential the accumulator absorbed, so the displayed exponent carries the same
sign: ``Re{E~ exp(+s j 2 pi k / n_frames)}`` with ``s = +1``.  That is why
``sign`` defaults to ``+1``; ``sign=-1`` shows the conjugate (backward) field.
``tests/test_animate.py`` pins the default with a forward-wave direction test
rather than trusting this paragraph.

Not touched here
----------------
The phasor's first and last rows and columns are exactly zero -- the PEC border
of the slice.  They are drawn as they are, with no masking, cropping or
extrapolation, so the animation shows a zero frame around the field and a viewer
is not told the metal is field-free when it is only unfilled.

This module imports nothing from :mod:`emfit`: it is a leaf, so the solver, the
study catalogue and the figure sink cannot form an import cycle through it.
"""

from __future__ import annotations

import tempfile

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (after backend selection)
import numpy as np  # noqa: E402

__all__ = ["frame_arrays", "colour_limits", "steady_state_gif"]

GIF_DPI = 80                     # pixels per inch of the saved frames
FIG_SIZE = (3.4, 2.6)            # inches: about 272 x 208 px at GIF_DPI


def _plane(slice_ez) -> np.ndarray:
    """Validate one phasor plane and return it as a 2-D complex array."""
    raw = np.asarray(slice_ez)
    if raw.ndim != 2:
        raise ValueError(
            f"slice_ez must be a 2-D plane of shape (nxn, nyn), got "
            f"{raw.ndim}-D with shape {raw.shape}: a phasor sampled on a plane "
            f"is the only thing an animation of that plane can show")
    if raw.size == 0:
        raise ValueError(
            f"slice_ez is empty (shape {raw.shape}): there is no field to "
            f"animate and no peak to scale the colours by")
    if not np.issubdtype(raw.dtype, np.complexfloating):
        raise ValueError(
            f"slice_ez must be complex, got dtype {raw.dtype}: a real plane "
            f"carries no phase, so there is no period to reconstruct -- pass "
            f"the accumulated phasor (real + 1j * imaginary), not its real part")
    return np.asarray(raw, dtype=np.complex128)


def _frame_count(n_frames) -> int:
    """Validate ``n_frames`` and return it as an ``int``."""
    n = int(n_frames)
    if n < 2:
        raise ValueError(
            f"n_frames must be at least 2 to show any motion, got {n_frames!r}")
    return n


def frame_arrays(slice_ez, *, n_frames=36, sign=+1) -> np.ndarray:
    """Real field of one period, frame by frame.

    Frame ``k`` is ``Re{slice_ez * exp(sign * 2j * pi * k / n_frames)}``, i.e.
    the phasor at ``t = k / (n_frames * f0)`` with the ``exp(+j omega t)``
    convention derived in the module docstring.  Frame 0 is ``np.real(slice_ez)``
    exactly, and the frames are exactly periodic: the last frame is the one
    before frame 0, so playing the sequence in a loop has no seam.

    Args:
        slice_ez: Complex phasor, shape ``(nxn, nyn)``, complex dtype.
        n_frames: Frames per period, at least 2.
        sign: ``+1`` (default) advances the phasor as ``exp(+j omega t)``, which
            is the accumulator's convention and makes a forward wave move toward
            ``+x``; ``-1`` shows the conjugate field instead.

    Returns:
        Real array of shape ``(n_frames, nxn, nyn)``.
    """
    ez = _plane(slice_ez)
    n = _frame_count(n_frames)
    turn = np.exp(float(sign) * 2.0j * np.pi * np.arange(n) / n)
    return np.real(ez[None, :, :] * turn[:, None, None])


def colour_limits(slice_ez) -> tuple:
    """Symmetric colour limits ``(-peak, +peak)`` for a whole phasor.

    ``peak`` is ``float(np.max(np.abs(slice_ez)))``.  The map is a diverging one
    (``RdBu_r`` by default), so zero -- the PEC border, and the nulls of the
    field -- sits at the middle of the scale and the two signs are equally wide.

    An all-zero (or non-finite) phasor has no peak to scale by, and returning
    ``(0, 0)`` would divide by zero inside the colour mapping and produce NaNs;
    the guard returns ``(-1.0, 1.0)`` instead, a unit window in which every
    frame is correctly drawn as flat zero.

    Args:
        slice_ez: Complex phasor, shape ``(nxn, nyn)``.

    Returns:
        ``(vmin, vmax)``, both finite.
    """
    ez = _plane(slice_ez)
    peak = float(np.max(np.abs(ez)))
    if not peak > 0.0:                       # also catches a NaN/Inf peak
        return (-1.0, 1.0)
    return (-peak, peak)


def steady_state_gif(slice_ez, *, dx, dy, f0, n_frames=36, fps=12,
                     cmap="RdBu_r", title=None, xlabel="x (mm)",
                     ylabel="y (mm)", plane_note=None) -> bytes:
    """Looping GIF of one period of the field the phasor describes.

    Frames come from :func:`frame_arrays` at its default ``sign`` (+1, the
    convention derived in the module docstring) and are written through
    :class:`matplotlib.animation.PillowWriter`, which needs no external encoder.
    ``PillowWriter`` wants a path it can resolve, so the GIF is written into a
    private :class:`tempfile.TemporaryDirectory` and read back as bytes; this
    module never chooses an output location.

    Geometry convention: index ``i`` along the first axis sits at ``x = i * dx``
    and index ``j`` along the second at ``y = j * dy``, with ``dx, dy`` in
    metres -- the **cell centre** of cell ``i``, not its lower-left corner.  The
    drawn image therefore extends half a cell beyond the outer centres
    (``-dx/2`` to ``(nxn - 1/2) dx``) so that each of those centres falls in the
    middle of its pixel, and the axes are labelled in millimetres.

    The first and last rows and columns of the phasor are exactly zero (the PEC
    border of the slice) and are shown as zero rather than masked or cropped.

    Args:
        slice_ez: Complex phasor, shape ``(nxn, nyn)``, complex dtype.
        dx, dy: Cell size along each axis [m].
        f0: Frequency of the phasor [Hz]; sets the instant each frame shows.
        n_frames: Frames per period, at least 2.
        fps: Playback rate [frames/s].
        cmap: Diverging colormap for a signed field.
        title: Figure title; ``None`` leaves the figure untitled.
        xlabel, ylabel: Axis labels, millimetres by default.
        plane_note: Optional text added to every frame's caption, e.g. the plane
            the slice was cut on.

    Returns:
        The complete GIF file, as bytes.
    """
    from matplotlib.animation import FuncAnimation, PillowWriter

    ez = _plane(slice_ez)
    n = _frame_count(n_frames)
    f0 = float(f0)
    if not f0 > 0.0:
        raise ValueError(
            f"f0 must be a positive frequency [Hz], got {f0!r}: it is what turns "
            f"a frame index into an instant")
    dx_mm = 1000.0 * float(dx)
    dy_mm = 1000.0 * float(dy)
    nxn, nyn = ez.shape
    frames = frame_arrays(ez, n_frames=n)
    vmin, vmax = colour_limits(ez)
    extent = (-0.5 * dx_mm, (nxn - 0.5) * dx_mm,
              -0.5 * dy_mm, (nyn - 0.5) * dy_mm)
    instants_ns = 1.0e9 * np.arange(n) / (n * f0)

    fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=GIF_DPI,
                           constrained_layout=True)
    if title:
        fig.suptitle(title)
    mesh = ax.imshow(frames[0], origin="lower", extent=extent, cmap=cmap,
                     vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_aspect("equal")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.colorbar(mesh, ax=ax, shrink=0.9, label=r"$\mathrm{Re}\,E_z$ [V/m]")
    caption = ax.set_title("")

    def update(index: int):
        mesh.set_data(frames[index])
        parts = [f"t = {instants_ns[index]:.4g} ns"]
        if plane_note is not None:
            parts.append(str(plane_note))
        caption.set_text(", ".join(parts))
        return ()

    anim = FuncAnimation(fig, update, frames=n, blit=False)
    try:
        with tempfile.TemporaryDirectory() as scratch:
            path = f"{scratch}/steady-state.gif"
            anim.save(path, writer=PillowWriter(fps=fps), dpi=GIF_DPI)
            with open(path, "rb") as handle:
                return handle.read()
    finally:
        plt.close(fig)
