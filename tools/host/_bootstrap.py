"""The one answer to "where is the repository root?" for the host scripts.

Four scripts under ``tools/host/`` each carried their own copy of the same
repo-root discovery: ``c1-audit/c1_audit.py``, ``c1-audit/pecbox_variant.py``,
``phaselag-subsets/phaselag_subsets.py`` and ``attribution/attribution.py``.
This module holds the single copy they now share.

The trap this module exists to bury: those scripts sit THREE levels below the
root (``<repo>/tools/host/<script>/x.py``), and ``python3 /path/to/x.py`` puts
only the script's *own* directory on ``sys.path`` -- never the root.  So never
count ``".."`` components: a fixed count yields ``<repo>/tools`` instead of
``<repo>``, which is exactly how ``import emfit`` died with
ModuleNotFoundError (see ``tools/host/attribution/out/run.log:3``).  Walk up
until a directory holding ``emfit/`` is found instead.

A second trap: ``run.sh`` exports ``C1_REPO``, but the interpreter does not
inherit a *path* from it -- only we can put the root on ``sys.path``.

No import-time side effects.  Importing this module does nothing; consumers
call :func:`bootstrap` (or :func:`find_repo`) explicitly.

Name policy -- ``REPO`` is the primary spelling; ``C1_REPO`` is kept as a
backward-compatible alias because ``tools/host/attribution/run.sh`` and the
sibling ``run.sh`` scripts export ``C1_REPO`` and this refactor does NOT edit
them, so both spellings must keep working as input and as output.  ``REPO`` is
written unconditionally, ``C1_REPO`` only when it is unset, so a root that a
caller already exported is never silently overwritten.
"""

import os
import sys

#: the package directory whose presence identifies the repository root
EMFIT = "emfit"

#: environment variables naming the root, in precedence order (REPO primary)
ENV_NAMES = ("REPO", "C1_REPO")


def find_repo(start=None):
    """Return the nearest ancestor of *start* that holds an ``emfit/`` directory.

    The environment is consulted first, ``REPO`` then ``C1_REPO``; a value
    counts only if that directory really holds ``emfit/``, so a stale exported
    root falls through to the walk instead of poisoning ``import emfit``.
    *start* defaults to the current working directory.

    SystemExit is raised -- naming both environment variables and the starting
    directory -- if neither the environment nor the walk produces a candidate.
    """
    here = os.path.abspath(start if start is not None else os.getcwd())

    stale = []
    for name in ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if not value:
            continue
        value = os.path.abspath(value)
        if os.path.isdir(os.path.join(value, EMFIT)):
            return value
        stale.append((name, value))

    cur = here
    while True:
        if os.path.isdir(os.path.join(cur, EMFIT)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:                      # hit the filesystem root
            break
        cur = parent

    notes = "".join(
        "  NOTE: %s=%r came from the environment and holds no %s/ directory.\n"
        % (name, value, EMFIT)
        for name, value in stale)
    raise SystemExit(
        "cannot locate the repository root:\n"
        "  walked up from : %s\n"
        "  looked for     : <dir>/emfit (an emfit/ package directory)\n"
        "  REPO env       : %s\n"
        "  C1_REPO env    : %s\n"
        "%s"
        "  state it       : C1_REPO=<repo> tools/host/<script>/run.sh\n"
        "run these host scripts through their run.sh, which discovers the root\n"
        "(git rev-parse --show-toplevel, else walk up to emfit/) and exports\n"
        "C1_REPO; do not invoke them directly."
        % (here,
           os.environ.get("REPO", "").strip() or "(unset)",
           os.environ.get("C1_REPO", "").strip() or "(unset)",
           notes))


def bootstrap(start=None, extra_paths=()):
    """Resolve the root, put it on ``sys.path``, export it, and return it.

    *extra_paths* are appended to ``sys.path`` right after the root; relative
    entries are resolved against the root.  Both the root and the extras go to
    the FRONT of ``sys.path`` (root first), each only when it is not already
    there -- an existing entry is never moved or duplicated.

    Side effects, in order: ``os.environ["REPO"] = root``, then
    ``os.environ.setdefault("C1_REPO", root)``.
    """
    root = find_repo(start)

    extras = []
    for entry in extra_paths:
        entry = entry if os.path.isabs(entry) else os.path.join(root, entry)
        entry = os.path.abspath(entry)
        if entry != root and entry not in extras:
            extras.append(entry)

    # reversed insertion keeps the documented order at the front: root, extras
    for entry in reversed([root] + extras):
        if entry not in sys.path:
            sys.path.insert(0, entry)

    os.environ["REPO"] = root
    os.environ.setdefault("C1_REPO", root)
    return root
