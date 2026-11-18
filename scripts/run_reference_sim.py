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

``--config`` IS THE SAME NUMBERS WITHOUT THE RETYPING.  ``--config PATH``
reads a ``emfit.config.RunConfig`` JSON document and gives every flag this run
did not get on the command line its value from that file (a typed flag always
wins, so ``--config run.json --nsteps 600`` is a variant of run.json and not a
silent conflict).  The config is not advisory: the fields it carries are the same
ones the flags are, resolved BEFORE the plan is priced, so what it changes is
the argv handed to the reference and therefore the mesh, the frame counts and
the budgets printed below.  A document is validated where it is read -- unknown
keys, a stride of 0 and a JSON ``2400.0`` are refused there and not after the
solve.

Usage (the one command to type, from the repository root):

    python3 scripts/run_reference_sim.py

That solves 2400 steps and writes ``artifacts/reference_sim_volume.npz`` (plus
``artifacts/reference_sim_run.json``), then prints the one command that serves
it.  Wants to see the plan without paying for the solve:

    python3 scripts/run_reference_sim.py --dry-run

A cheaper real solve while you are wiring something up:

    python3 scripts/run_reference_sim.py --nsteps 600 --volume-stride 30

the same run, stated once and then reused:

    python3 scripts/run_reference_sim.py --config artifacts/run.json --dry-run

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
# the run's numbers: a config file, or the flags, or the defaults above
# --------------------------------------------------------------------------- #
def load_config(path: str | None):
    """Read a ``RunConfig`` document, or ``None`` when no ``--config`` was given.

    Imported here and not at module top: ``emfit.config`` is only reachable once
    ``_sys_path_guard`` has run (this file is typed as a path, so ``scripts/`` is
    on ``sys.path`` and the repository root may not be), and the module is pure
    stdlib so the import is cheap when it does happen.

    A document that does not validate is turned into a SystemExit naming the
    path: the failure is ``--config``'s, so the message has to say which file it
    was, or the caller is left reading a TypeError about a field they never
    typed.
    """
    if path is None:
        return None
    _sys_path_guard()
    from emfit.config import RunConfig

    try:
        return RunConfig.from_json_file(path)
    except (OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"REFUSED: --config {path}: {exc}")


# Which namespace attribute comes from which config field, and what it is when
# NEITHER the flag nor a config names it.  The fallbacks are this module's own
# constants (or None for "the reference's default"), stated once, so a flag and
# the config field that overrides it cannot drift apart.
CONFIG_DRIVEN = (
    ("npz", str(DEFAULT_NPZ)),
    ("out", str(DEFAULT_OUT)),
    ("nsteps", DEFAULT_NSTEPS),
    ("volume_stride", DEFAULT_VOLUME_STRIDE),
    ("dump_stride", DEFAULT_DUMP_STRIDE),
    ("volume_frames", None),
    ("pulse_freq_ghz", None),
    ("n_line", None),
    ("xcut_near_mm", None),
    ("xcut_far_mm", None),
)


def apply_config(args: argparse.Namespace, config) -> argparse.Namespace:
    """Resolve every CONFIG_DRIVEN flag in place: flag if typed, else config.

    The flags whose value a config may supply default to ``None`` ("not given")
    rather than to their real default, because ``--nsteps 2400`` typed by hand
    and ``--nsteps`` absent are different statements -- the first is a choice
    that must BEAT the config, the second is the absence a config fills.  Both
    are None-checked here, once, and then the ordinary validation below runs on
    plain values again.

    Returns ``args`` for symmetry with the other helpers; the mutation is the
    point (``reference_argv`` / ``plan`` / ``print_plan`` read the namespace).
    """
    for name, fallback in CONFIG_DRIVEN:
        if getattr(args, name) is not None:
            continue                      # the command line wins, always
        value = getattr(config, name) if config is not None else None
        setattr(args, name, fallback if value is None else value)
    return args


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
        # ALWAYS explicit: a --vis-dump run deviates from arm A's certified
        # configuration, and the reference refuses to guess a path for it rather
        # than risk overwriting evidence/termination/build_A_50ohm.json.
        "--out", str(Path(args.out).resolve()),
    ]
    # The cadence is only passed when a volume was asked for: --no-volume is
    # the reference's own off switch, so it is STATED rather than left to be
    # inferred from an absent flag.
    if args.no_volume:
        argv += ["--no-volume"]
    else:
        argv += ["--volume-stride", str(args.volume_stride)]
    if args.volume_frames is not None:
        argv += ["--volume-frames", str(args.volume_frames)]
    if args.pulse_freq_ghz is not None:
        argv += ["--pulse-freq-ghz", str(args.pulse_freq_ghz)]
    # The mesh and the two x-cut frames.  Passed whenever they are known --
    # which, once a config is loaded, is always -- so that the values the plan
    # is priced on are the values the solve uses.  ``--n-line`` is the one that
    # moves the CELL COUNT (nx = n_pml + n_ref + n_line) and so the volume's
    # price; the x-cut pair only moves which columns the two frames show, which
    # the plan does not price but the dump does record.
    if args.n_line is not None:
        argv += ["--n-line", str(args.n_line)]
    if args.xcut_near_mm is not None:
        argv += ["--xcut-near-mm", str(args.xcut_near_mm)]
    if args.xcut_far_mm is not None:
        argv += ["--xcut-far-mm", str(args.xcut_far_mm)]
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
          f"p2) with "
          + ("NO |E| volume (cut planes only)" if args.no_volume
             else "a 3-D |E| volume"))
    print(f"  mesh        {geo['nx']} x {geo['ny']} x {geo['nz']} = "
          f"{cells:,} cells at {geo['cell_m'] * 1e3:.3f} mm")
    print(f"  solve       excite='pulse' at {pulse_hz / 1e9:.3f} GHz, "
          f"{int(kwargs['nsteps'])} steps, ONE FDTD solve")
    print(f"  Ez planes   stride {p['stride']}: {p['nt']} frames of "
          f"{geo['nx']}x{geo['nz']} on the j={geo['j_cut']} z-cut + {p['nt_x']} "
          f"frames of two {geo['ny']}x{geo['nz']} x-cuts, ~{p['est_mb']:.1f} MB "
          f"of a {p['planes_budget_mb']:.0f} MB budget (thinned to fit)")
    if args.no_volume:
        print("  |E| volume  NONE - --no-volume: no volume array, no volume key "
              "in the .npz, and nothing for the "
              f"{p['vol_budget_mb']:.0f} MB volume budget to refuse")
    else:
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


def summarise_dump(npz: Path, want_volume: bool = True) -> None:
    """Report the keys the viewer will find; refuse only if a REQUESTED volume is absent.

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
        ycut = data["ez_ycut"].shape if "ez_ycut" in keys else None
        near = data["ez_xcut_near"].shape if "ez_xcut_near" in keys else None
        far = data["ez_xcut_far"].shape if "ez_xcut_far" in keys else None
        plane_stride = (int(data["dump_stride"]) if "dump_stride" in keys
                        else None)

    print(f"WROTE {npz} ({npz.stat().st_size / 1e6:.1f} MB, "
          f"{len(keys)} keys)")
    if shape is None and not want_volume:
        # --no-volume: the planes ARE the record, so what is checked is the
        # plane families and the stride they were recorded at. The viewer opens
        # a volume-less dump already (it drops a stale layer and keeps the
        # plane clock).
        print("  e_abs_volume            absent (--no-volume: planes only)")
        print(f"  ez_ycut                 {ycut} float32 [V/m], dump_stride "
              f"{plane_stride}")
        print(f"  ez_xcut_near            {near} float32 [V/m]")
        print(f"  ez_xcut_far             {far} float32 [V/m]")
        print(f"  keys                    {', '.join(keys)}")
        return
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
        "--config", default=None, metavar="PATH",
        help="read the run's numbers from an emfit.config.RunConfig JSON "
             "document (default: none). Every flag below that was NOT typed on "
             "this command line takes its value from the file; a typed flag "
             "wins. The file is validated where it is read: an unknown key, a "
             "stride of 0 and a JSON 2400.0 are refused there, before anything "
             "is priced. --npz/--out/--nsteps/--volume-stride/--dump-stride "
             "/--volume-frames/--pulse-freq-ghz/--n-line/--xcut-near-mm "
             "/--xcut-far-mm are all config-driven.")
    ap.add_argument(
        "--npz", default=None, metavar="PATH",
        help="where the field dump goes (default: artifacts/reference_sim_volume"
             ".npz). This is the file the viewer loads, and the only argument "
             "the viewer needs. Refused if it resolves inside evidence/, because "
             "run_build_A.py does not guard this path and the tree keeps no "
             "history to restore a tracked dump from.")
    ap.add_argument(
        "--out", default=None, metavar="PATH",
        help="where the run's JSON artefact goes (default: artifacts/"
             "reference_sim_run.json). ALWAYS passed explicitly: a --vis-dump "
             "run is pulse-excited, i.e. a DEVIATION from arm A's certified CW "
             "configuration, so run_build_A.py refuses to guess a path for it "
             "rather than risk writing another run's numbers over "
             "evidence/termination/build_A_50ohm.json.")
    ap.add_argument(
        "--nsteps", type=int, default=None, metavar="N",
        help=f"FDTD steps (default: {DEFAULT_NSTEPS}, which is run_build_A.py's "
             "own default and the length the certified run uses). This is the "
             "knob that moves the volume's frame count, and therefore the one "
             "that can push the volume over its 48 MB budget -- the plan line "
             "says so before the solve starts.")
    ap.add_argument(
        "--volume-stride", type=int, default=None, metavar="N",
        help=f"keep every Nth y-cut FRAME in the |E| volume (default: "
             f"{DEFAULT_VOLUME_STRIDE}). FRAMES, not solver steps: the counter "
             "this divides is the one --dump-stride already thins, so the steps "
             "between two volume frames are dump_stride x this. On the default "
             "mesh the plane plan settles at dump stride 1, so the two coincide "
             "here -- the plan line prints both rather than letting the "
             "coincidence stand in for the definition.")
    ap.add_argument(
        "--no-volume", action="store_true",
        help="record the two cut-plane families and NO 3-D |E| volume. This is "
             "the flag that makes the planes the whole picture: it passes "
             "--no-volume to the reference, which allocates no volume, samples "
             "none during the march and writes no volume key, so the 48 MB "
             "volume budget has nothing to refuse. A --volume-stride typed on "
             "this command line is a contradiction and is refused; a cadence a "
             "--config supplied is simply turned off (the flag wins).")
    ap.add_argument(
        "--volume-frames", type=int, default=None, metavar="N",
        help="cap the volume at N frames (default: no cap). A cap shortens the "
             "recorded tail rather than thinning the whole march, so it is the "
             "wrong lever for a budget problem -- --volume-stride is that lever "
             "-- and it is here for 'the first N frames are what I want to "
             "look at'. Refused at 0: a dump with no frames is not a smaller "
             "dump, it is a file that lies about having a volume.")
    ap.add_argument(
        "--dump-stride", type=int, default=None, metavar="N",
        help=f"keep every Nth solver step's planes (default: "
             f"{DEFAULT_DUMP_STRIDE}). run_build_A.py RAISES this itself if the "
             "planes would not fit their 45 MB budget, so a value here is a "
             "floor and not a guarantee; the plan line shows the stride the "
             "reference actually settled on, which is also the multiplier in the "
             "volume's step cadence.")
    ap.add_argument(
        "--n-line", type=int, default=None, metavar="N",
        help="line cells between the reference plane and the top of the grid "
             "(default: run_build_A.py's own 54, i.e. a 62 column mesh; 79 "
             "gives 87, Run E's length). nx = n_pml + n_ref + n_line, so this "
             "is the one mesh integer that moves the CELL COUNT and therefore "
             "the |E| volume's price -- the plan line re-prices it for you.")
    ap.add_argument(
        "--xcut-near-mm", type=float, default=None, metavar="MM",
        help="x position of the near x-cut frame stored in the dump (default: "
             "run_build_A.py's 20.4 mm, on the line just before the load). The "
             "dump records this frame's column; the plan does not price it.")
    ap.add_argument(
        "--xcut-far-mm", type=float, default=None, metavar="MM",
        help="x position of the far x-cut frame stored in the dump (default: "
             "run_build_A.py's 22.0 mm, past the load). Must be greater than "
             "--xcut-near-mm in the config, where the pair is validated.")
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
    # Captured BEFORE a --config can fill it: a cadence TYPED here and
    # --no-volume together are a contradiction, while one a config supplied is
    # not -- a flag beats a document, so the flag simply turns it off.
    typed_volume_stride = args.volume_stride is not None

    # A config supplies every flag that was not typed, and it does so HERE --
    # before the validation below and before anything is priced. That ordering
    # is what makes the file load-bearing rather than decorative: from this
    # point on the namespace holds plain values and every downstream helper
    # (``reference_argv``, ``plan``, ``print_plan``) is pricing the config's
    # numbers without knowing a config was involved.
    config = load_config(args.config)
    apply_config(args, config)
    if config is not None:
        # Named in the plan, because a run whose mesh came from a file has to
        # say which file: the flags printed below are the resolved values, and
        # without this line the document they came from is invisible.
        print(f"CONFIG      {Path(args.config).resolve()} "
              f"(schema {config.schema_version})")

    if args.nsteps < 1:
        raise SystemExit(f"REFUSED: --nsteps {args.nsteps}: a solve needs at "
                         "least one step.")
    if args.no_volume:
        if typed_volume_stride:
            raise SystemExit(
                f"REFUSED: --no-volume with --volume-stride "
                f"{args.volume_stride}: one asks for no volume and the other "
                "for one every N frames. Drop one of them.")
        if args.volume_frames is not None:
            raise SystemExit(
                f"REFUSED: --no-volume with --volume-frames "
                f"{args.volume_frames}: there is no volume to cap. Drop one of "
                "them.")
        args.volume_stride = None
    if not args.no_volume and (args.volume_stride is None
                               or args.volume_stride < 1):
        raise SystemExit(
            f"REFUSED: --volume-stride {args.volume_stride}: the cadence is a "
            "count of frames, so it must be at least 1. For the cut planes "
            "only, pass --no-volume.")
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

    summarise_dump(npz, want_volume=not args.no_volume)
    print("OPEN IT WITH (- the server prints its URL and does not open a "
          "browser; Ctrl-C stops it):")
    print(f"  {viewer_command(npz)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
