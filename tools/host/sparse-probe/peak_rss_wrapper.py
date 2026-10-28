#!/usr/bin/env python3
"""peak_rss_wrapper.py -- run an arbitrary command as a child and report wall clock and peak RSS.

RE-DERIVATION NOTICE
====================
This file is a **RE-DERIVATION of a lost untracked script, not the original**. The
original wrapper was used during this campaign, was never added to the tree, and its
exact text is gone. What is written here reproduces *what it had to do* -- spawn a
child, time it, read `resource.getrusage(RUSAGE_CHILDREN).ru_maxrss`, emit JSON, exit
with the child's status -- and nothing else about it can be claimed. In particular the
original's option names, JSON schema, field ordering and rounding are **not** recovered;
this file's interface is a fresh definition, so anything reading this output should read
this docstring rather than assume the old script behaved the same way.

WHY IT EXISTS
=============
The measurement environment has no `/usr/bin/time` and no `ps`, so the only route to an
external process's peak RSS is `getrusage(RUSAGE_CHILDREN)` from the parent. That route
is exactly what this wrapper takes. It lets an out-of-process number be compared against
the in-process `RUSAGE_SELF` figure the probes record themselves
(`peak_rss_mib = ru_maxrss / 1024.0`), which is how the wrapper itself was tested.

WHAT IT MEASURES
================
wall clock : `time.monotonic()` sampled immediately before the spawn and immediately
             after the child has been reaped.
peak RSS   : `resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss`, read **after**
             the child has been waited for. It is not updated while the child is running,
             so reading it early would report the previous child's peak or zero.

UNITS -- READ THIS BEFORE COMPARING NUMBERS
===========================================
On Linux `ru_maxrss` is in **KiB**. This script reports the raw value as
`ru_maxrss_kib` *and* the derived value as `ru_maxrss_mib` = `ru_maxrss_kib / 1024.0`.
The `/1024.0` conversion is deliberate: it is the same convention the probes in this
directory use, so a wrapper figure is directly comparable with a report's
`peak_rss_mib` without rescaling. A figure of `237.9` means `237.9` MiB, i.e. roughly
`243637`-`243660` KiB of raw `ru_maxrss`; it does **not** mean 237.9 KiB.

WHAT IT CANNOT REPRODUCE
========================
1. **Per-process attribution when the child forks.** `RUSAGE_CHILDREN` aggregates every
   descendant this wrapper has waited for into a *single* high-water mark: it is the
   maximum peak of any one child (plus any child it reaped that this process waited for
   through it), not a per-process list and not a sum. If the child forks workers, the
   reported number belongs to whichever process peaked highest and this script cannot
   say which one, nor how many processes were involved. A single-process measurement is
   the only case where the number is unambiguous -- which is the case for the probe it
   was tested against (one thread, `RUSAGE_SELF` reported by the probe itself).
2. **The child's own allocation timeline.** Only the high-water mark survives. When the
   peak occurred, how long the child held it, whether it was one large transient
   allocation or a slow climb, and how much was resident after the peak are all
   unrecoverable from `ru_maxrss`. This script reports a number and a duration; it is
   not a memory profiler.
3. **Peaks in descendants that were never reaped**, and peaks in processes still running
   when the child exits: `wait`-based accounting cannot see them.
4. **The wrapper's own footprint**, which is excluded by using `RUSAGE_CHILDREN` rather
   than `RUSAGE_SELF`. That is a feature (it measures the child), but it means the
   wrapper's runtime is not included in any figure here.

USAGE
=====
    python3 peak_rss_wrapper.py [--label NAME] [--json-out FILE] -- <command> [args...]

The child inherits stdin/stdout/stderr and the wrapper's cwd and environment; its output
is not captured or rewritten. JSON goes to stdout (and to `--json-out` if given), so
redirect the child's own output if you need the two separated. The wrapper's exit status
is the child's exit status; `127` means the command could not be spawned and `2` means
the wrapper was invoked without a command.
"""

import argparse
import datetime
import json
import os
import resource
import subprocess
import sys
import time

EXIT_USAGE = 2
EXIT_NOT_SPAWNABLE = 127


def _rusage_children():
    """RUSAGE_CHILDREN sampling of the reaped descendants; safe to call any time."""
    return resource.getrusage(resource.RUSAGE_CHILDREN)


def build_record(cmd, label, wall_s, use, error=None):
    """Assemble the JSON record. `use` is the post-reap RUSAGE_CHILDREN struct."""
    kib = int(use.ru_maxrss)
    record = {
        "tool": "peak_rss_wrapper.py",
        "tool_note": (
            "RE-DERIVATION of a lost untracked script, not the original; see module "
            "docstring for what it cannot reproduce"
        ),
        "label": label,
        "command": list(cmd),
        "cwd": os.getcwd(),
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "wall_s": round(wall_s, 6),
        "exit_code": None,
        "ru_maxrss_kib": kib,
        "ru_maxrss_mib": round(kib / 1024.0, 3),
        "ru_maxrss_units": "KiB raw; ru_maxrss_mib = ru_maxrss_kib / 1024.0",
        "child_utime_s": round(use.ru_utime, 6),
        "child_stime_s": round(use.ru_stime, 6),
        "measurement": (
            "resource.getrusage(RUSAGE_CHILDREN).ru_maxrss, sampled after the child was "
            "reaped; a single high-water mark over all waited-for descendants, not "
            "per-process attributable and with no timeline"
        ),
        "n_child_processes_attributed": 1 if error is None else 0,
    }
    if error is not None:
        record["error"] = error
    return record


def emit(record, json_out):
    text = json.dumps(record, indent=2, sort_keys=False)
    print(text, flush=True)
    if json_out:
        with open(json_out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run a command as a child and report wall clock and peak RSS from "
                    "getrusage(RUSAGE_CHILDREN); prints JSON, exits with the child's code.")
    parser.add_argument("--label", default=None,
                        help="free-form label copied into the record")
    parser.add_argument("--json-out", default=None,
                        help="also write the JSON record to this path")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="the command to run, optionally after a bare '--'")
    args = parser.parse_args(argv)

    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("usage: peak_rss_wrapper.py [--label NAME] [--json-out FILE] -- "
              "<command> [args...]", file=sys.stderr)
        return EXIT_USAGE

    t_start = time.monotonic()
    try:
        completed = subprocess.run(cmd)
    except OSError as exc:
        wall_s = time.monotonic() - t_start
        record = build_record(cmd, args.label, wall_s, _rusage_children(),
                              error=f"{type(exc).__name__}: {exc}")
        emit(record, args.json_out)
        return EXIT_NOT_SPAWNABLE
    wall_s = time.monotonic() - t_start

    record = build_record(cmd, args.label, wall_s, _rusage_children())
    record["exit_code"] = completed.returncode
    emit(record, args.json_out)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
