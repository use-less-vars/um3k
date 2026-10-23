"""Tests for :mod:`emfit.animate`: phasor -> frames -> looping GIF.

Everything here is synthetic: no solver run, no board file.  The one test that
matters physically is :func:`test_forward_wave_moves_toward_positive_x`, which
pins the sign convention the module derives from ``emfit.ports.DftAccumulator``.
"""

from __future__ import annotations

import hashlib
import io

import numpy as np
import pytest
from PIL import Image

from emfit import animate

NF = 4                      # frames per period; small keeps the GIF cheap


def _smooth_plane(nx=24, ny=16, peak=3.0):
    """A complex phasor with an exactly known peak and a live imaginary part.

    The phase step is a quarter turn, so the rotation is ``1, 1j, -1, -1j`` and
    ``|z|`` is bitwise the amplitude -- no ``exp(1j*theta)`` rounding, which is
    what lets the peak tests compare with ``==``.  Zero on the border, as the
    solver's plane phasor is (PEC) on the metal.
    """
    i = np.arange(nx)[:, None]
    j = np.arange(ny)[None, :]
    taper = np.cos(0.5 * np.pi * i / (nx - 1)) * np.cos(0.5 * np.pi * j / (ny - 1))
    amp = np.minimum(peak * np.broadcast_to(taper, (nx, ny)), peak)
    quarter = np.asarray([1.0, 1.0j, -1.0, -1.0j])
    z = amp * quarter[(i + j) % 4]
    z[0, :] = 0.0
    z[-1, :] = 0.0
    z[:, 0] = 0.0
    z[:, -1] = 0.0
    z[nx // 2, ny // 2] = peak + 0.0j          # the known, exactly-peaked sample
    return z


def _gif(z, **kw):
    args = {"dx": 2.0e-4, "dy": 2.0e-4, "f0": 7.83e9, "n_frames": NF}
    args.update(kw)
    return animate.steady_state_gif(z, **args)


def test_gif_has_the_requested_frame_count_and_a_sane_size():
    blob = _gif(_smooth_plane())
    assert blob.startswith(b"GIF8"), "not a GIF: no GIF87a/GIF89a header"
    with Image.open(io.BytesIO(blob)) as image:
        assert image.n_frames == NF
        assert image.size[0] > 100 and image.size[1] > 100, (
            f"animation is {image.size} px: too small to read a field from")


def test_colour_limits_span_the_peak_and_no_frame_exceeds_them():
    z = _smooth_plane(peak=3.0)
    peak = float(np.max(np.abs(z)))
    assert peak == 3.0, f"test fixture lost its known peak (got {peak!r})"
    assert animate.colour_limits(z) == (-peak, peak)
    frames = animate.frame_arrays(z, n_frames=12)
    # the peak is reached inside the period, so a fixed (-peak, +peak) scale
    # neither clips a frame nor wastes dynamic range
    assert np.max(np.abs(frames)) == peak


def test_frame_zero_is_the_real_part_bitwise():
    z = _smooth_plane()
    assert np.array_equal(animate.frame_arrays(z, n_frames=NF)[0], np.real(z))


def test_frames_are_exactly_periodic():
    z = _smooth_plane()
    n = 9
    frames = animate.frame_arrays(z, n_frames=n)
    k = 2
    peak = float(np.max(np.abs(z)))
    for index in (k, k + n):
        unrolled = np.real(z * np.exp(2j * np.pi * index / n))
        assert np.allclose(frames[k], unrolled, rtol=0.0, atol=1.0e-12 * peak)


def test_forward_wave_moves_toward_positive_x():
    """A forward wave must travel toward +x on screen, not toward the port.

    ``emfit.ports`` writes a forward wave as ``exp(-1j beta x)`` and its
    accumulator uses ``exp(+j omega t)``, so the field of such a wave is
    ``cos(omega t - beta x)``: its crest sits at ``x = (omega / beta) t`` and
    moves toward +x.  If ``sign`` were flipped, every frame would show the crest
    where the crest was one frame *earlier* and the animation would play a wave
    running back into the port -- physically the reflected wave, which is the
    one thing this picture must not silently show.
    """
    nx, dx = 161, 1.0e-3
    x = (np.arange(nx) - (nx - 1) / 2.0) * dx     # x = 0 at the middle
    lam = 2.0 * (nx - 1) * dx                     # one crest in the frame
    beta = 2.0 * np.pi / lam
    col = np.ones((1, 3))
    forward = np.exp(-1j * beta * x)[:, None] * col
    backward = np.conj(forward)

    def crest(plane, index):
        return int(np.argmax(animate.frame_arrays(plane, n_frames=8)[index][:, 1]))

    assert crest(forward, 1) > crest(forward, 0), (
        f"forward wave moved from x-index {crest(forward, 0)} to "
        f"{crest(forward, 1)}: the animation runs backwards, so `sign` in "
        f"emfit.animate.frame_arrays does not match the accumulator's "
        f"exp(+j omega t) convention")
    assert crest(backward, 1) < crest(backward, 0), (
        "the conjugate phasor must travel the other way; if both run toward +x "
        "the frame formula has lost the phasor's phase entirely")


def test_two_calls_give_byte_identical_gifs():
    z = _smooth_plane()
    first = hashlib.sha256(_gif(z)).hexdigest()
    second = hashlib.sha256(_gif(z)).hexdigest()
    assert first == second, (
        f"the GIF is not reproducible ({first} != {second}): something in the "
        f"writer is stamping a time or a memory address into the file")


def test_bad_input_is_refused():
    z = _smooth_plane()
    with pytest.raises(ValueError, match="2-D"):
        animate.frame_arrays(np.zeros(z.shape[0], dtype=complex))
    with pytest.raises(ValueError, match="complex"):
        animate.frame_arrays(np.zeros(z.shape, dtype=float))
    with pytest.raises(ValueError, match="empty"):
        animate.colour_limits(np.zeros((0, z.shape[1]), dtype=complex))
    with pytest.raises(ValueError, match="at least 2"):
        animate.frame_arrays(z, n_frames=1)


def test_an_all_zero_phasor_still_animates():
    z = np.zeros((12, 9), dtype=complex)
    assert animate.colour_limits(z) == (-1.0, 1.0)
    frames = animate.frame_arrays(z, n_frames=NF)
    assert np.all(frames == 0.0) and np.all(np.isfinite(frames))
    blob = _gif(z)
    with Image.open(io.BytesIO(blob)) as image:
        assert image.n_frames == NF
