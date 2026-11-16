#!/usr/bin/env python3
"""Run the reference simulation ONCE, dump a 3-D |E| volume, and print how to look at it.

WHAT "THE REFERENCE SIMULATION" IS.  Arm A of the absorbing-termination build:
``evidence/termination/run_build_A.py`` terminates the microstrip's far port p2
in a 50 ohm ``series_r`` load and takes one FDTD solve of the stamp.  That file
is the reference -- the CW 50 ohm run every other arm (B/C/D) is compared
against -- and it is the only thing this script drives.  It is not reimplemented
here, not one mesh integer or budget is retyped: the call block, the mesh
(``vis_geometry``), the frame plan (``_vis_plan_stride``) and the volume budget
(``_vis_volume_budget_check``) are all *the reference's own functions*, imported
and called, so a mesh that moves in ``run_build_A.py`` moves here with it and
the numbers printed below are the numbers the solve will actually use.

WHY THIS SCRIPT EXISTS.  ``run_build_A.py`` grew a ``--volume-stride`` flag that
also writes ``e_abs_volume`` (|E| on the dump's own node grid, all three
components sampled and squared, so the viewer can scrub a solid volume instead
of two planes), but nothing in the tree exercises it end-to-end: the flag was
plumbed, priced and budgeted, and then never driven.  Getting a volume out of it
by hand means passing four flags where three of them are coupled -- the cadence
is counted in y-cut FRAMES and not in solver steps, the volume has its own
48 MB budget that REFUSES (it does not thin), and any run with ``--vis-dump`` is
a *deviation* from the certified configuration and therefore must be told where
its JSON artefact goes.  This script is that knowledge in one place, with the
arithmetic done ahead of the solve and printed before the first timestep.

THE TWO BUDGETS, AND WHY THE DEFAULTS FIT.  A plane dump has a 45 MB budget that
``_vis_plan_stride`` satisfies by RAISING the stride until it fits -- it never
refuses, it quietly records fewer frames.  The volume has a 48 MB budget that
REFUSES instead, because thinning a volume is not a stride change the caller
asked for but a different picture.  On the default mesh (62 x 212 x 22 = 289,168
cells at 0.4 mm) one volume frame is 1.16 MB, so 48 MB holds 41 frames; at the
default 2400 steps and stride 1 that is a cadence of ``--volume-stride 100`` for
24 frames = 27.8 MB.  The defaults below sit inside both budgets with room to
spare, and the plan line says by how much -- if you raise ``--nsteps`` the
printed figure is what tells you the run would be refused BEFORE it starts.

``--volume-stride`` COUNTS FRAMES, NOT STEPS.  It is applied to the y-cut frame
counter (the one ``--dump-stride`` already thins), so the solver steps between
two volume frames are ``dump_stride_settled * volume_stride`` and NOT
``volume_stride``.  On the default mesh the plane plan settles at stride 1 and
the two coincide, which is exactly why the mistake would go unnoticed: the plan
line prints both the frame cadence and the step cadence, so the coincidence is
visible rather than assumed.

WHY ``--out`` IS ALWAYS PASSED.  ``run_build_A.py`` treats a ``--vis-dump`` run
as a DEVIATION from arm A's certified configuration (pulse excitation instead of
CW) and REFUSES to guess a path for it, because the default path IS
``evidence/termination/build_A_50ohm.json`` -- the tracked CW document.  So this
script always names a JSON artefact under ``artifacts/``; there is no mode in
which it writes into ``evidence/``.

Usage (the one command to type, from the repository root):

    python3 scripts/run_reference_sim.py

That solves 2400 steps and writes ``artifacts/reference_sim_volume.npz`` (plus
``artifacts/reference_sim_run.json``), then prints the one command that serves
it.  Wants to see the plan without paying for the solve:

    python3 scripts/run_reference_sim.py --dry-run

A cheaper real solve while you are wiring something up:

    python3 scripts/run_reference_sim.py --nsteps 600 --volume-stride 30

and then, verbatim from the printed block:

    python3 server/poc_app.py --input artifacts/reference_sim_volume.npz

Defaults: ``--nsteps 2400`` (the reference's own), ``--volume-stride 100``,
``--dump-stride 1``, pulse excitation at ``run_build_A``'s ``VIS_F_PULSE_HZ``
(15 GHz), no ``--volume-frames`` cap.  There is no ``--freq``: a pulse dump is a
travelling packet, so a single CW frequency is not a knob this run has.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REFERENCE = REPO / "evidence" / "termination" / "run_build_A.py"
REFERENCE_REL = "evidence/termination/run_build_A.py"

# The arm whose run IS the reference.  Not a flag: B/C/D are the other
# terminations of the same study and answering "what does arm B look like in 3-D"
# is a different errand than reproducing the reference.
STRUCTURE = "A"

DEFAULT_NPZ = REPO / "artifacts" / "reference_sim_volume.npz"
DEFAULT_OUT = REPO / "artifacts" / "reference_sim_run.json"

DEFAULT_NSTEPS = 2400
DEFAULT_VOLUME_STRIDE = 100
DEFAULT_DUMP_STRIDE = 1

EVIDENCE_DIR = (REPO / "evidence").resolve()


# --------------------------------------------------------------------------- #
# making the reference importable
# --------------------------------------------------------------------------- #
def _sys_path_guard() -> None:
    """Put the repo and its venv's site-packages on ``sys.path`` before import.

    ``run_build_A.py`` imports ``emfit`` (in the tree) and the compiled kernel
    ``emfit_core``, which is installed in the project venv and NOT in the tree.
    Run from a bare shell without ``PYTHONPATH``, that import is what fails --
    ``emfit/evolve.py`` raises a RuntimeError about the kernel rather than
    anything a caller can act on from the error text.  A script that exists to
    be "the one command to type" cannot make typing two ``export`` lines a
    prerequisite, so the two directories are added here, and only if they exist
    (a plain checkout with no venv still gets a clear refusal below).  Nothing is
    added twice, and nothing already on ``sys.path`` is reordered.
    """
    wanted = [REPO]
    wanted.extend(sorted((REPO / ".venv" / "lib").glob("python3*/site-packages")))
    missing = [str(p) for p in wanted if p.is_dir() and str(p) not in sys.path]
    if missing:
        sys.path[0:0] = missing


def load_reference():
    """Import ``run_build_A.py`` as a module (it is not a package module).

    ``evidence/termination`` has no ``__init__.py`` and is not on the import
    path, so the file is loaded by spec.  The module name it is registered under
    is irrelevant -- nothing here looks it up in ``sys.modules`` -- but it is
    registered, because ``dataclasses``/``typing`` in the reference resolve
    forward references through ``sys.modules`` and a spec-less module breaks
    that.
    """
    if not REFERENCE.is_file():
        raise SystemExit(
            f"REFUSED: {REFERENCE_REL} is not here, so there is no reference "
            f"simulation to run (looked for {REFERENCE}). This script drives "
            "that file; it does not carry a copy of it.")

    _sys_path_guard()
    spec = importlib.util.spec_from_file_location("_reference_run_build_A",
                                                 REFERENCE)
    if spec is None or spec.loader is None:      # pragma: no cover - defensive
        raise SystemExit(f"REFUSED: cannot load {REFERENCE_REL} as a module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:           # pragma: no cover - env issue
        raise SystemExit(
            f"REFUSED: {REFERENCE_REL} needs the project environment and "
            f"{exc.name!r} is not importable. Run this from the repository root "
            f"with its venv present ({REPO / '.venv'}), or export "
            "PYTHONPATH=<repo>:<repo>/.venv/lib/python3.*/site-packages.")
    return module


# --------------------------------------------------------------------------- #
# the plan, taken from the reference itself
# --------------------------------------------------------------------------- #
def reference_argv(args: argparse.Namespace) -> list[str]:
    """The reference's own argv for this run, as a list main() accepts.

    Every path is absolute so the plan lines and the viewer command name the same
    file whatever directory this was typed from.
    """
    argv = [
        "--structure", STRUCTURE,
        "--nsteps", str(args.nsteps),
        "--vis-dump", str(Path(args.npz).resolve()),
        "--dump-stride", str(args.dump_stride),
        "--volume-stride", str(args.volume_stride),
        # ALWAYS explicit: a --vis-dump run deviates from arm A's certified
        # configuration, and the reference refuses to guess a path for it rather
        # than risk overwriting evidence/termination/build_A_50ohm.json.
        "--out", str(Path(args.out).resolve()),
    ]
    if args.volume_frames is not None:
        argv += ["--volume-frames", str(args.volume_frames)]
    if args.pulse_freq_ghz is not None:
        argv += ["--pulse-freq-ghz", str(args.pulse_freq_ghz)]
    return argv


def dry_run_call(reference, argv: list[str]) -> dict:
    """The reference's own ``--dry-run`` JSON call block, i.e. the real kwargs.

    The mesh is derived by ``vis_geometry`` from the call's kwargs, and the call
    is assembled by ``build_kwargs`` from a Namespace only ``main()`` can build
    (its parser lives inside main).  So the honest way to learn the mesh without
    solving anything is to ask the reference to print its own call block -- that
    path runs the real ``build_kwargs`` on the real parser and returns before the
    trip thread, the twin and the first timestep.

    ``main()`` prints two provenance lines before the JSON ("structure A: ...",
    "artefact: ...", "vis: ..."), so the document starts at the first line that
    is exactly an opening brace; everything before it is kept for the failure
    message.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = reference.main([*argv, "--dry-run"])
    text = buf.getvalue()
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "{"), None)
    if rc != 0 or start is None:
        raise SystemExit(
            f"REFUSED: {REFERENCE_REL} --dry-run did not print a call block "
            f"(exit {rc}), so the plan cannot be priced before the solve. Its "
            "output was:\n" + text)
    try:
        doc = json.loads("\n".join(lines[start:]))
        return doc["call"]["kwargs"]
    except (json.JSONDecodeError, KeyError) as exc:   # pragma: no cover
        raise SystemExit(
            f"REFUSED: the --dry-run call block from {REFERENCE_REL} is not the "
            f"{{\"call\": {{\"kwargs\": ...}}}} document this script prices the "
            f"plan from ({exc!r}). Its output was:\n" + text)


def plan(reference, kwargs: dict, args: argparse.Namespace) -> dict:
    """Mesh, plane frames, volume frames and both budgets -- all the reference's.

    The artefact serializer renames the cell size ``h`` to ``h_m`` on the way out
    of the call block (``run_build_A.py`` ``"h_m": kwargs["h"]``), while
    ``vis_geometry`` reads ``h``.  Undoing that one rename is what lets the
    printed mesh be the solved mesh instead of ``vis_geometry``'s fallback --
    which would be wrong here in a way that looks right: it falls back to
    ``studies.MS_N_CLEAN`` 12, and this run meshes ``n_clean`` 96, so the y
    extent would come out 44 where the solve uses 212.

    ``_vis_plan_stride`` / ``_vis_volume_budget_check`` are the reference's
    private helpers, called rather than copied because their whole value is that
    the number printed here is the number the solve checks against.  The volume
    check RAISES (SystemExit, "VIS REFUSED: ...") when the request is over
    budget -- deliberately not caught: that message is the actionable one, and it
    is the same message that would arrive after the solve had already been paid
    for, which is the reason to price it here.
    """
    geo_kwargs = dict(kwargs)
    if "h_m" in geo_kwargs and "h" not in geo_kwargs:
        geo_kwargs["h"] = geo_kwargs.pop("h_m")
    geo = reference.vis_geometry(geo_kwargs)

    stride, nt, nt_x, est_mb = reference._vis_plan_stride(
        int(kwargs["nsteps"]), int(args.dump_stride),
        geo["nx"], geo["ny"], geo["nz"])

    n_vol = 0
    vol_mb = 0.0
    if args.volume_stride is not None:
        n_vol = (nt + args.volume_stride - 1) // args.volume_stride
        if args.volume_frames is not None:
            n_vol = min(n_vol, args.volume_frames)
        vol_mb = reference._vis_volume_budget_check(
            n_vol, geo["nx"], geo["ny"], geo["nz"])

    return {
        "geo": geo, "stride": stride, "nt": nt, "nt_x": nt_x,
        "est_mb": est_mb, "planes_budget_mb": reference.VIS_BUDGET_MB,
        "n_vol": n_vol, "vol_mb": vol_mb,
        "vol_budget_mb": reference.VIS_VOLUME_BUDGET_MB,
        # The volume cadence is applied to the y-cut FRAME counter, so the solver
        # steps between two volume frames are this product -- NOT volume_stride.
        "steps_between": stride * (args.volume_stride or 1),
    }


def print_plan(p: dict, kwargs: dict, args: argparse.Namespace,
               reference) -> None:
    """Say what is about to happen, in the units the budgets are enforced in."""
    geo = p["geo"]
    cells = geo["nx"] * geo["ny"] * geo["nz"]
    # The frequency the reference will actually use, not the flag's value: an
    # absent --pulse-freq-ghz means the reference's own VIS_F_PULSE_HZ, and a
    # plan that printed "None GHz" would hide which pulse is being solved.
    pulse_hz = (float(args.pulse_freq_ghz) * 1e9 if args.pulse_freq_ghz
                else float(reference.VIS_F_PULSE_HZ))
    print(f"PLAN - the reference simulation (arm {STRUCTURE}, 50 ohm series_r at "
          f"p2) with a 3-D |E| volume")
    print(f"  mesh        {geo['nx']} x {geo['ny']} x {geo['nz']} = "
          f"{cells:,} cells at {geo['cell_m'] * 1e3:.3f} mm")
    print(f"  solve       excite='pulse' at {pulse_hz / 1e9:.3f} GHz, "
          f"{int(kwargs['nsteps'])} steps, ONE FDTD solve")
    print(f"  Ez planes   stride {p['stride']}: {p['nt']} frames of "
          f"{geo['nx']}x{geo['nz']} on the j={geo['j_cut']} z-cut + {p['nt_x']} "
          f"frames of two {geo['ny']}x{geo['nz']} x-cuts, ~{p['est_mb']:.1f} MB "
          f"of a {p['planes_budget_mb']:.0f} MB budget (thinned to fit)")
    print(f"  |E| volume  {p['n_vol']} frames of "
          f"{geo['nx']}x{geo['ny']}x{geo['nz']} float32, one every "
          f"{args.volume_stride} y-cut frames = every {p['steps_between']} "
          f"solver step(s), ~{p['vol_mb']:.1f} MB of a "
          f"{p['vol_budget_mb']:.1f} MB budget (refused if over, not thinned)")
    print(f"  npz         {Path(args.npz).resolve()}")
    print(f"  artefact    {Path(args.out).resolve()}")


def viewer_command(npz: Path) -> str:
    """The one command that serves the dump (it does NOT open a browser)."""
    return f"python3 server/poc_app.py --input {npz}"


def summarise_dump(npz: Path) -> None:
    """Report the keys the viewer will find, and refuse if the volume is absent.

    The solve can succeed and still hand back a planes-only file if the volume
    flags never reach the recorder -- a stride is a stride whether or not
    anything is recorded through it -- so the key set is checked rather than
    assumed.  Reading the header of an npz is O(directory), not O(payload): no
    array is materialised.
    """
    import numpy as np

    with np.load(npz, allow_pickle=False) as data:
        keys = sorted(data.files)
        shape = data["e_abs_volume"].shape if "e_abs_volume" in keys else None
        steps = (data["e_abs_volume_step_index"] if
                 "e_abs_volume_step_index" in keys else None)
        cadence = (int(data["e_abs_volume_stride"]) if
                   "e_abs_volume_stride" in keys else None)

    print(f"WROTE {npz} ({npz.stat().st_size / 1e6:.1f} MB, "
          f"{len(keys)} keys)")
    if shape is None:
        raise SystemExit(
            "REFUSED: the dump has no e_abs_volume, so there is no volume to "
            "scrub -- the run wrote planes only and --volume-stride did not "
            "reach the recorder. The keys present are: " + ", ".join(keys))
    first_last = (f"steps {int(steps[0])}..{int(steps[-1])}"
                  if steps is not None and len(steps) else "no step index")
    print(f"  e_abs_volume            {shape} float32 [V/m], {first_last}, "
          f"cadence {cadence} y-cut frame(s)")
    print(f"  keys                    {', '.join(keys)}")


def refuse_evidence_write(npz: Path) -> None:
    """Refuse a dump path inside ``evidence/``.

    The reference guards its JSON artefact against the evidence tree and says
    why ("this tree keeps no history"), but it does NOT guard the npz: a
    ``--vis-dump evidence/vis_dump.npz`` overwrites a tracked dump, and the
    overwrite is silent because the file is written last and in full.  A 2400
    step pulse run recorded over the certified dump is not recoverable either, so
    the same rule is stated here for the file the reference does not look at.
    """
    if Path(npz).resolve().is_relative_to(EVIDENCE_DIR):
        raise SystemExit(
            f"REFUSED: --npz {npz} is inside evidence/. This tree keeps no "
            "history, so a dump written over a tracked one cannot be undone -- "
            "and unlike the JSON artefact, run_build_A.py does not guard the "
            "dump path, so nothing downstream would stop it. Give --npz a path "
            "outside evidence/ (the default, artifacts/reference_sim_volume.npz, "
            "is one).")


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="scripts/run_reference_sim.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Run the reference simulation (arm A) with a 3-D |E| volume "
                    "dump and print the command that serves it.",
        epilog="The dump is written by evidence/termination/run_build_A.py "
               "itself; this script only decides the flags, prices the plan "
               "against that file's own budgets, and names the outputs. Then:\n"
               "  python3 server/poc_app.py --input <the npz>\n"
               "(the server prints its URL and does not open a browser; Ctrl-C "
               "stops it).")
    ap.add_argument(
        "--npz", default=str(DEFAULT_NPZ), metavar="PATH",
        help="where the field dump goes (default: artifacts/reference_sim_volume"
             ".npz). This is the file the viewer loads, and the only argument "
             "the viewer needs. Refused if it resolves inside evidence/, because "
             "run_build_A.py does not guard this path and the tree keeps no "
             "history to restore a tracked dump from.")
    ap.add_argument(
        "--out", default=str(DEFAULT_OUT), metavar="PATH",
        help="where the run's JSON artefact goes (default: artifacts/"
             "reference_sim_run.json). ALWAYS passed explicitly: a --vis-dump "
             "run is pulse-excited, i.e. a DEVIATION from arm A's certified CW "
             "configuration, so run_build_A.py refuses to guess a path for it "
             "rather than risk writing another run's numbers over "
             "evidence/termination/build_A_50ohm.json.")
    ap.add_argument(
        "--nsteps", type=int, default=DEFAULT_NSTEPS, metavar="N",
        help=f"FDTD steps (default: {DEFAULT_NSTEPS}, which is run_build_A.py's "
             "own default and the length the certified run uses). This is the "
             "knob that moves the volume's frame count, and therefore the one "
             "that can push the volume over its 48 MB budget -- the plan line "
             "says so before the solve starts.")
    ap.add_argument(
        "--volume-stride", type=int, default=DEFAULT_VOLUME_STRIDE, metavar="N",
        help=f"keep every Nth y-cut FRAME in the |E| volume (default: "
             f"{DEFAULT_VOLUME_STRIDE}). FRAMES, not solver steps: the counter "
             "this divides is the one --dump-stride already thins, so the steps "
             "between two volume frames are dump_stride x this. On the default "
             "mesh the plane plan settles at dump stride 1, so the two coincide "
             "here -- the plan line prints both rather than letting the "
             "coincidence stand in for the definition.")
    ap.add_argument(
        "--volume-frames", type=int, default=None, metavar="N",
        help="cap the volume at N frames (default: no cap). A cap shortens the "
             "recorded tail rather than thinning the whole march, so it is the "
             "wrong lever for a budget problem -- --volume-stride is that lever "
             "-- and it is here for 'the first N frames are what I want to "
             "look at'. Refused at 0: a dump with no frames is not a smaller "
             "dump, it is a file that lies about having a volume.")
    ap.add_argument(
        "--dump-stride", type=int, default=DEFAULT_DUMP_STRIDE, metavar="N",
        help=f"keep every Nth solver step's planes (default: "
             f"{DEFAULT_DUMP_STRIDE}). run_build_A.py RAISES this itself if the "
             "planes would not fit their 45 MB budget, so a value here is a "
             "floor and not a guarantee; the plan line shows the stride the "
             "reference actually settled on, which is also the multiplier in the "
             "volume's step cadence.")
    ap.add_argument(
        "--pulse-freq-ghz", type=float, default=None, metavar="GHZ",
        help="centre of the Ricker pulse (default: run_build_A.py's "
             "VIS_F_PULSE_HZ, 15 GHz). A dump is the march of ONE packet, so the "
             "excitation is pulse and not CW. There is no --freq: a pulse carries "
             "a band, so a single CW frequency is not a knob this run has.")
    ap.add_argument(
        "--dry-run", action="store_true",
        help="print the plan and the command that would serve the result, and "
             "solve nothing. Worth the second it costs before any real run: the "
             "volume budget refuses rather than thins, and this is where that "
             "refusal arrives cheap. It prices the plan with the reference's own "
             "--dry-run call block, so the mesh and frame counts are the ones the "
             "solve would use, not this script's opinion of them.")
    args = ap.parse_args(argv)

    if args.nsteps < 1:
        raise SystemExit(f"REFUSED: --nsteps {args.nsteps}: a solve needs at "
                         "least one step.")
    if args.volume_stride is None or args.volume_stride < 1:
        raise SystemExit(
            f"REFUSED: --volume-stride {args.volume_stride}: the cadence is a "
            "count of frames, so it must be at least 1. This script exists to "
            "produce a volume; to record planes only, run "
            f"{REFERENCE_REL} directly without the flag.")
    if args.volume_frames is not None and args.volume_frames < 1:
        raise SystemExit(
            f"REFUSED: --volume-frames {args.volume_frames}: a dump with no "
            "frames is not a smaller dump, it is a file that claims a volume it "
            "does not carry. Drop the flag for no cap (the default), or use "
            "--volume-stride to record fewer frames across the whole march.")
    if args.dump_stride < 1:
        raise SystemExit(f"REFUSED: --dump-stride {args.dump_stride}: a stride of "
                         "0 selects no step at all.")

    npz = Path(args.npz).resolve()
    refuse_evidence_write(npz)

    reference = load_reference()
    argv_reference = reference_argv(args)

    kwargs = dry_run_call(reference, argv_reference)
    priced = plan(reference, kwargs, args)

    print_plan(priced, kwargs, args, reference)

    if args.dry_run:
        print("DRY RUN - nothing was solved. The command that will serve it:")
        print(f"  {viewer_command(npz)}")
        return 0

    npz.parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).resolve().parent.mkdir(parents=True, exist_ok=True)
    print(f"SOLVING - {int(kwargs['nsteps'])} steps; the reference prints its "
          "own VIS plan and timings below")

    rc = reference.main(argv_reference)
    if rc != 0:
        return int(rc)
    if not npz.is_file():
        raise SystemExit(
            f"REFUSED: {REFERENCE_REL} returned 0 but wrote no {npz}. Nothing "
            "to serve; check the VIS lines above for where the dump actually "
            "went.")

    summarise_dump(npz)
    print("OPEN IT WITH (- the server prints its URL and does not open a "
          "browser; Ctrl-C stops it):")
    print(f"  {viewer_command(npz)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
