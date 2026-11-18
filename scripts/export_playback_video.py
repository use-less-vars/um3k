#!/usr/bin/env python3
"""Export a browser-playable video playback from an ``emfit.vis/2`` volume .npz.

The exporter picks one 2-D field plane out of a flat ``.npz`` volume dump,
decimates the frame axis to a requested count, renders each selected frame
with matplotlib (Agg backend) and pipes the raw RGB24 bytes into ffmpeg,
which muxes a ``yuv420p`` H.264 MP4 with ``+faststart`` -- i.e. ``video/mp4``
that every current browser can play in a ``<video>`` tag without plugins.

Only the requested array plus the small coordinate/index vectors are read
from the ``.npz`` (npz members are lazy, so the other arrays are never
materialised); frames are rendered and streamed one at a time, so peak
memory stays close to a single 2-D slice.

Usage::

    python3 scripts/export_playback_video.py
    python3 scripts/export_playback_video.py --array ez_xcut_near \
        --frames 100 --out artifacts/playback_xcut.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time

import numpy as np

# THE VIEWER'S STEP SENTENCE, REPRODUCED HERE - A DELIBERATE DUPLICATION.
#
# The real formatter lives in ``server/poc_app.py`` (``TimeAxis.label`` /
# ``_frame_label``), and that module builds a trame application on IMPORT, so
# this exporter must not import it. The grammar is therefore COPIED:
# ``Step {step} / {max_step} (Stride {stride})``, the stride stated even when it
# is 1, because a silent stride is indistinguishable from an undecimated one.
# If the viewer's wording ever changes, it has to be changed here too.
STEP_FMT = "Step {step} / {max_step} (Stride {stride})"
# The viewer's own degraded sentence, for a dump that records no step axis: count
# the frames, and state no stride the record never claimed. No parenthetical.
FRAME_FMT = "Step {frame} / {n_frames}"
DPI = 100


def step_label(step, max_step, stride):
    """One frame's label in the viewer's grammar: ``Step s / m (Stride k)``."""
    return STEP_FMT.format(step=int(step), max_step=int(max_step),
                           stride=int(stride))


def frame_label(frame, n_frames):
    """The degraded label: position-counted, no stride, no parenthetical."""
    return FRAME_FMT.format(frame=int(frame), n_frames=int(n_frames))


def frame_text(steps, src, max_step, stride, frame, n_frames):
    """The label for ONE drawn frame - and the place the lie is refused.

    ``max_step`` is ``steps.max()`` at the caller, so a numerator above the
    denominator cannot arise from a well-formed record. The guard raises anyway,
    here, at the only line that would PRINT the inconsistency: ``Step 2400 /
    2399`` is precisely the bug this formatter exists to make unrepresentable,
    and a file meant to be forwarded must fail loudly rather than be rendered.
    """
    if steps is None:
        return frame_label(frame, n_frames)
    step = int(steps[src])
    if not 1 <= step <= int(max_step):
        raise ValueError(
            f"frame {int(frame)} of {int(n_frames)} records step {step}, "
            f"outside 1..{int(max_step)}: refusing to render a step label "
            f"whose numerator exceeds its own denominator"
        )
    return step_label(step, max_step, stride)


def max_step_of(steps):
    """The label's DENOMINATOR: the last step the record actually reaches.

    ``frame_index.max()`` - not the run's step COUNT and not that count minus
    one: ``nsteps - 1`` printed "step 2400 / 2399" on the final frame, a
    numerator above its own denominator in a file meant to be forwarded to a
    colleague. The dump's own ``nsteps`` is deliberately NOT read: a count can
    fall below the steps its frames already reach, while a maximum taken from
    the SAME vector the numerator comes from can never be exceeded by it.

    ``None`` (a record that states no step axis) stays ``None``: the caller then
    prints the degraded frame label and never divides by a number it invented.
    """
    return int(steps.max()) if steps is not None else None


def plan_decimation(n_total, n_out):
    """Return ``n_out`` source indices evenly spaced over the FULL frame axis.

    The returned list always starts at ``0`` and ends at ``n_total - 1`` and is
    strictly increasing, i.e. the first and the last solver dump are never
    dropped.
    """
    if n_total < 1:
        raise ValueError("n_total must be >= 1")
    if n_out < 1:
        raise ValueError("n_out must be >= 1")
    if n_out > n_total:
        raise ValueError(f"n_out={n_out} exceeds n_total={n_total}")
    if n_out == 1:
        return [0]
    step = (n_total - 1) / (n_out - 1)
    return [int(round(i * step)) for i in range(n_out)]


def axis_names(npz, ny, nz):
    """Map the two in-plane array lengths to their coordinate vectors."""
    by_len = {}
    for name in ("x_mm", "y_mm", "z_mm"):
        if name in npz:
            by_len[int(npz[name].size)] = name
    if ny not in by_len or nz not in by_len:
        raise KeyError(f"no coordinate vector with length {ny} / {nz}")
    return by_len[ny], by_len[nz]


def recorded_steps(npz, n_total):
    """The dump's OWN frame->step map for this array, or ``None``.

    ``frame_index`` is the 1-D array of simulation step numbers, one per frame
    (``frame_index_xcut`` is the same record for the cut-plane arrays). A vector
    that is absent, whose length does not match this array's frame axis, or that
    numbers its frames from 0 is NOT padded, offset or guessed: the label
    degrades exactly as the viewer's does rather than inventing a step reading
    the record cannot defend.
    """
    for name in ("frame_index", "frame_index_xcut"):
        if name in npz:
            vec = np.asarray(npz[name]).ravel()
            if int(vec.size) != n_total:
                continue
            vec = vec.astype(np.int64)
            if int(vec[0]) < 1:
                return None
            return vec
    return None


def measured_stride(npz, steps):
    """The decimation of the step axis being DRAWN: its even spacing, else the
    dump's stated ``dump_stride``, else one step per frame.

    The spacing of the drawn axis is preferred over the dump's single scalar
    ``dump_stride`` because the exporter may draw an axis that scalar does not
    describe: in ``artifacts/volume_s59.npz`` ``frame_index`` is spaced 1 apart
    while ``frame_index_xcut`` is spaced 10 apart, so quoting the scalar for the
    x-cut video would state a stride its own frames contradict. A record with no
    even spacing (one frame, or an irregular axis) falls back to the scalar, and
    a record that states neither is one step per frame - the same "an even axis
    says its own spacing, else 1" rule the viewer's ``build_time_axis`` uses.
    """
    diffs = np.diff(np.asarray(steps, dtype=np.int64))
    if int(diffs.size) and bool(np.all(diffs == diffs[0])) and int(diffs[0]) > 0:
        return int(diffs[0])
    try:
        stated = int(npz["dump_stride"]) if "dump_stride" in npz else 0
    except (TypeError, ValueError):
        stated = 0
    return stated if stated > 0 else 1


def default_clim(data, indices):
    """Symmetric clim from the global 99.5th percentile of |data| over shown frames."""
    shown = np.concatenate([np.abs(np.asarray(data[i], dtype=np.float64)).ravel()
                            for i in indices])
    peak = float(np.percentile(shown, 99.5))
    if peak == 0.0:
        peak = 1.0
    return -peak, peak


def encode(args):
    """Render and encode the whole animation; return the summary dict."""
    # matplotlib is imported HERE, not at the top of the module: the Agg backend
    # switch and the pyplot import are side effects of RENDERING, and the label
    # grammar above has to stay importable - and unit-testable - without them.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    if not os.path.exists(ffmpeg):
        raise FileNotFoundError("ffmpeg not found on PATH")

    t_start = time.time()
    with np.load(args.npz, allow_pickle=False) as npz:
        if args.array not in npz:
            raise KeyError(f"{args.array!r} not in {args.npz}")
        data = npz[args.array]
        n_total = int(data.shape[0])
        ny, nz = int(data.shape[1]), int(data.shape[2])
        xname, zname = axis_names(npz, ny, nz)
        xs = np.asarray(npz[xname])
        zs = np.asarray(npz[zname])
        steps = recorded_steps(npz, n_total)
        stride = measured_stride(npz, steps) if steps is not None else None

    # The denominator is the last step the record reaches - see max_step_of.
    max_step = max_step_of(steps)

    indices = plan_decimation(n_total, args.frames)
    if args.clim is not None:
        lo, hi = float(args.clim[0]), float(args.clim[1])
    else:
        lo, hi = default_clim(data, indices)

    width, height = ny * args.scale, nz * args.scale
    extent = [float(xs[0]), float(xs[-1]), float(zs[0]), float(zs[-1])]
    n_out = len(indices)

    fig = plt.figure(figsize=(width / DPI, height / DPI), dpi=DPI)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_axis_off()
    im = ax.imshow(data[indices[0]], origin="lower", extent=extent, aspect="equal",
                   cmap=args.cmap, vmin=lo, vmax=hi, interpolation="nearest")
    label = None
    if args.label:
        label = ax.text(0.008, 0.992, "", transform=ax.transAxes, ha="left", va="top",
                        fontsize=6, family="monospace", color="black",
                        bbox={"facecolor": "white", "alpha": 0.75, "pad": 1.0,
                              "edgecolor": "none"})

    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
           "-r", str(args.fps), "-i", "-",
           "-vf", f"scale={width}:{height}:flags=neighbor",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    try:
        for k, src in enumerate(indices):
            im.set_data(data[src])
            if label is not None:
                label.set_text(frame_text(steps, src, max_step, stride,
                                          k + 1, n_out))
            fig.canvas.draw()
            frame = np.ascontiguousarray(
                np.asarray(fig.canvas.buffer_rgba())[:, :, :3])
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
    except BrokenPipeError:
        err = proc.stderr.read().decode("utf-8", "replace")
        proc.wait()
        raise RuntimeError(f"ffmpeg closed the pipe early: {err.strip()}")
    finally:
        plt.close(fig)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited {rc}: {err.strip()}")
    encode_seconds = time.time() - t_start

    probe = shutil.which("ffprobe")
    codec = "h264"
    if probe:
        out = subprocess.run(
            [probe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,width,height", "-of", "json",
             args.out], capture_output=True, text=True, check=False)
        if out.returncode == 0:
            streams = json.loads(out.stdout).get("streams") or [{}]
            codec = streams[0].get("codec_name", "h264")
    version = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True,
                             check=False).stdout.splitlines()[0]

    return {
        "ok": True,
        "encoder": f"{version} / -c:v libx264",
        "codec": codec,
        "out": args.out,
        "bytes": os.path.getsize(args.out),
        "frames": n_out,
        "fps": args.fps,
        "duration_s": round(n_out / float(args.fps), 3),
        "src_indices_first": indices[:5],
        "src_indices_last": indices[-5:],
        "encode_seconds": round(encode_seconds, 3),
        "clim": [lo, hi],
    }


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--npz", default="artifacts/volume_s59.npz",
                   help="volume .npz (default: %(default)s)")
    p.add_argument("--out", default="artifacts/playback.mp4",
                   help="output .mp4 (default: %(default)s)")
    p.add_argument("--array", default="ez_ycut",
                   help="2-D plane array to animate (default: %(default)s)")
    p.add_argument("--frames", type=int, default=60,
                   help="number of video frames (default: %(default)s)")
    p.add_argument("--fps", type=int, default=24,
                   help="frames per second (default: %(default)s)")
    p.add_argument("--scale", type=int, default=6,
                   help="integer nearest-neighbour pixel scale (default: %(default)s)")
    p.add_argument("--cmap", default="RdBu_r",
                   help="matplotlib colormap (default: %(default)s)")
    p.add_argument("--clim", nargs=2, type=float, default=None, metavar=("LO", "HI"),
                   help="fixed colour limits (default: symmetric 99.5th pct of |data|)")
    p.add_argument("--label", dest="label", action="store_true", default=True,
                   help="draw the step/frame label (default)")
    p.add_argument("--no-label", dest="label", action="store_false",
                   help="omit the step/frame label")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    print(json.dumps(encode(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
