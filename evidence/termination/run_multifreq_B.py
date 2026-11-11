#!/usr/bin/env python3
"""Arm-B entry point: exactly ``run_multifreq.py --structure B``.

Why this file exists
--------------------
The arm-B sweep was run once by patching ``run_multifreq``'s module globals from
outside the driver (``run_multifreq.ARTEFACT_PREFIX = ...``, ``LOAD_OHM = ...``)
and then calling ``main()``.  It worked, and every artefact it wrote lied: the
.md was headed "# A-arm multifrequency beta sweep", the dossier was the A arm's,
no artefact recorded the 100 ohm load the run actually used, and ``meta.argv``
named a call that passed no load at all.  Nothing on disk said which arm
produced those files.

The fix lives in the driver: one provenance record is resolved from
``--structure`` (see ``STRUCTURES`` / ``resolve_structure()`` in
run_multifreq.py) and threaded through the load, the output prefix, the .md
heading and the dossier.  This wrapper is ONLY the naming, so that the arm has a
command of its own to type and to quote in a dispatch.  It is a thin alias for

    python3 evidence/termination/run_multifreq.py --structure B

with the extra arguments forwarded unchanged, and it must stay that thin: a
wrapper that rewrote a module constant would reintroduce the exact bug.

What is recorded where
----------------------
``sys.argv`` is NOT touched, so each per-bin artefact's ``meta.argv`` records the
invocation the operator actually typed (``run_multifreq_B.py ...``), while
``meta.main_argv`` records the argument list handed to the driver
(``--structure B ...``).  ``meta.script`` names the ENTRY POINT that was run --
``run_multifreq_B.py`` for this wrapper, read from ``sys.argv[0]`` by
``run_multifreq._script_name()`` -- so the artefact says which command produced
it, while ``main_argv`` still says what that command asked the driver for.
Each per-bin artefact also carries the run label at its TOP level (``"dossier"``),
so a single file quoted out of the sweep still names the run it came from.

Exit codes are the driver's: 0 = every asked bin extracted, 5 = BLOCKED (the F4
falsifier fired: more than half the bins gave no station fit).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import run_multifreq as driver  # noqa: E402  (sys.path set above)


def main(argv=None):
    """Run the sweep as the B arm: ``--structure B`` plus the caller's args."""
    args = list(sys.argv[1:]) if argv is None else list(argv)
    return driver.main(["--structure", "B"] + args)


if __name__ == "__main__":
    sys.exit(main())
