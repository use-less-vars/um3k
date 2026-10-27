"""Read the *whole* banked C1 spectrum and say which columns propagate.

``c1_audit.py`` writes ``out/c1_spectrum.npz`` (written at ``c1_audit.py:572-591``)
and prints only the columns that survived its eigenvalue predicate, plus a
post-hoc shape screen on top of those.  So the audit's headline number --
"one propagating mode" -- is a count of ``lam`` entries that pass

    |Im(lambda)| <= 1e-6 * max(1, |lambda|)      and      Re(lambda) > 0

(``c1_audit.py:459`` and ``:469-474``; the same tolerance the solver itself
applies at ``emfit/mode2d.py:1124``), where the eigenvalue *is* ``beta^2``
(``c1_audit.py:472`` ``bsq = real(lam[j])``, ``:487`` ``beta = sqrt(bsq)``).

That predicate can skip a column silently and the skip reasons are not
persisted (``c1_audit.py:470-471`` not real enough, ``:473-474`` non-finite or
``Re <= 0``, ``:478-479`` zero eigenvector).  Nothing in the audit's own output
distinguishes "9 columns are complex" from "1436 columns are complex", so the
question *is the spectrum one-mode only, or does the reporting hide the rest?*
cannot be answered from the audit's printout.  It can be answered from the
npz, which banks ``lam`` in full (all 1444 columns; ``vecs_real`` too).

This script therefore does one thing: it re-reads the banked eigenvalues,
re-applies the same predicate with the tolerance printed explicitly, shows the
distribution of the *rejected* mass, and lists every real-positive column by
index so the count is checkable by eye.  It reads only -- it never imports
``emfit``, never assembles, never solves, and never rewrites the npz.

What it settles
---------------
* how many columns are real-positive (the audit's "propagating modes"), and
  whether that set is exactly ``{738}``;
* how the other 1443 columns split between complex and real-negative, which is
  what "one propagating mode" has to mean if it is not a reporting artefact;
* whether the banked per-column correlations (``corr_ey``/``corr_ez``, present
  only for the columns the audit kept) cover the real-positive set.

What it cannot settle
---------------------
Whether a *second* propagating mode exists in the continuous problem but is
absent from this discrete spectrum because of the boundary conditions or the
mesh.  ``c1_audit.py`` supplies only the ground plane and the strip as PEC
predicates (``:299-307`` ``BOUNDARIES = (ground, strip)``), so the outer domain
walls are natural/Neumann -- "symmetry planes, not conductors"
(``emfit/mode2d.py:1322-1324``, and ``:44`` "natural on every other wall;
nothing is imposed").  A closed magnetic box is not the open cross-section, so
a missing mode here is a statement about this box, not about the stripline.
That question needs a new solve with the walls made PEC, not a re-read.

Run it directly (no wrapper, no arguments, no state written)::

    python3 tools/host/c1-audit/spectrum_report.py [path/to/c1_spectrum.npz]
"""

from __future__ import annotations

import os
import sys

import numpy as np

# ---------------------------------------------------------------------------
# repo layout: this file lives at <repo>/tools/host/c1-audit/spectrum_report.py,
# which is THREE levels below the repository root.  Never count ".." levels
# here -- a fixed count used to yield <repo>/tools instead of <repo>, which is
# why `import emfit` in c1_audit.py failed with ModuleNotFoundError.  The root
# is discovered (or handed over by run.sh via C1_REPO) and then validated.
# Copied from c1_audit.py:113-158 so the two tools agree on where the repo is.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))


def _find_repo(start):
    """Return the nearest ancestor of *start* that contains an ``emfit/`` dir.

    Counting ``..`` components is deliberately avoided (see above).  ``None``
    is returned if the walk reaches the filesystem root without a candidate.
    """
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, "emfit")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:                      # hit the filesystem root
            return None
        cur = parent


#: run.sh exports the root it discovered; only a direct invocation needs the
#: local walk.  Either way the result is validated immediately below.
_REPO_ENV = os.environ.get("C1_REPO", "").strip()
REPO = _REPO_ENV if _REPO_ENV else _find_repo(HERE)
EMFIT_DIR = os.path.join(REPO, "emfit") if REPO else None
if not REPO or not os.path.isdir(EMFIT_DIR):
    _hint = "" if not _REPO_ENV else (
        "  NOTE: C1_REPO=%r came from the environment and looks stale.\n"
        % (_REPO_ENV,))
    raise SystemExit(
        "cannot locate the repository root:\n"
        "  REPO      = %r\n"
        "  emfit dir = %r  (not a directory)\n"
        "%s"
        "run this through tools/host/c1-audit/run.sh, which discovers the root\n"
        "and exports C1_REPO; or export C1_REPO yourself."
        % (REPO, EMFIT_DIR, _hint))
#: nothing below imports emfit -- this is a reader -- but the root is still
#: checked, because a wrong root means a wrong default npz path.
NPZ_DEFAULT = os.path.join(HERE, "out", "c1_spectrum.npz")

#: The audit's eigenvalue predicate, verbatim in value (c1_audit.py:459, which
#: is also emfit/mode2d.py:1124).  Kept as one constant so the printed
#: tolerance and the applied tolerance cannot drift apart.
REL_TOL = 1e-6

#: how many rows of the by-Re table to show
TOP_N = 20


def say(*a) -> None:
    """Print one flushed line."""
    print(" ".join(str(x) for x in a), flush=True)


# ---------------------------------------------------------------------------
# tolerant key access: a missing key degrades the report, it never raises
# ---------------------------------------------------------------------------
def _opt(data, name, want_len=None, want_ndim=None):
    """Return ``data[name]`` or ``None``, printing exactly why it is unusable.

    ``want_len`` / ``want_ndim`` are checked only when given.  Every rejection
    prints one line starting with ``ABSENT`` or ``SKIP`` so that a degraded
    report says what it is missing instead of silently printing a shorter table.
    """
    if name not in data.files:
        say(f"  {name:<14} ABSENT  -- key not in the npz; reported as '-'")
        return None
    arr = data[name]
    if want_ndim is not None and arr.ndim != want_ndim:
        say(f"  {name:<14} SKIP    -- ndim {arr.ndim}, expected {want_ndim}; "
            f"reported as '-'")
        return None
    if want_len is not None and arr.size != want_len:
        say(f"  {name:<14} SKIP    -- size {arr.size}, expected {want_len}; "
            f"reported as '-'")
        return None
    return arr


def _fmt(x, spec="12.6f"):
    """Format a number, or '-' for anything that is None / non-finite."""
    if x is None:
        return "-".rjust(len(spec % 0.0))
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if not np.isfinite(v):
        return "-".rjust(len(spec % 0.0))
    return spec % v


def main(argv):
    path = argv[1] if len(argv) > 1 else NPZ_DEFAULT
    say("=" * 78)
    say("C1 spectrum distribution reader -- reads only, never solves")
    say(f"  repo      : {REPO}")
    say(f"  npz       : {path}")
    say(f"  predicate : |Im(lam)| <= {REL_TOL:g} * max(1, |lam|)  and  Re(lam) > 0")
    say(f"              (c1_audit.py:459, :469-474; emfit/mode2d.py:1124)")
    say(f"              beta^2 = Re(lam), beta = sqrt(Re(lam))  (c1_audit.py:472, :487)")
    say("=" * 78)
    if not os.path.isfile(path):
        raise SystemExit(
            f"npz not found: {path}\n"
            "  The audit writes it at c1_audit.py:572-591 -- run the audit first.")

    with np.load(path, allow_pickle=False) as data:
        # --- what is actually in the file -----------------------------------
        say("")
        say("--- npz contents (keys and shapes, in file order) ---")
        n_show = 0
        for k in data.files:
            arr = data[k]
            say(f"  {k:<14} shape={str(arr.shape):<16} dtype={arr.dtype}")
            n_show += 1
        say(f"  ({n_show} keys)")

        # --- the full eigenvalue list ---------------------------------------
        say("")
        say("--- eigenvalues: lam is ALL columns, not only the kept ones ---")
        lam = _opt(data, "lam", want_ndim=1)
        if lam is None and "lam" in data.files:
            # a (1, n) or (n, 1) bank would be recoverable; anything else is not
            flat = np.asarray(data["lam"]).ravel()
            say(f"  lam reshape: ravel() of shape {np.shape(data['lam'])} -> {flat.size}")
            lam = flat
        if lam is None:
            say("  DEGRADED: no usable 'lam'; falling back to the kept-column")
            say("            arrays, which cannot show the rejected mass.")
            bsq = _opt(data, "beta_sq", want_ndim=1)
            if bsq is None:
                raise SystemExit(
                    "neither 'lam' nor 'beta_sq' is usable: this npz is not the\n"
                    "c1_audit.py output and nothing can be said about the spectrum.")
            total = int(bsq.size)
            say(f"  total kept columns (beta_sq) : {total}")
            say(f"  beta_sq > 0                   : {int((bsq > 0).sum())}")
            say("  VERDICT: undecidable from this file -- no full spectrum banked.")
            return 0

        lam = np.asarray(lam)
        n_tot = int(lam.size)
        re = np.real(lam)
        im = np.imag(lam)
        tol = REL_TOL * np.maximum(1.0, np.abs(lam))
        real_enough = np.abs(im) <= tol
        is_prop = real_enough & np.isfinite(re) & (re > 0.0)
        prop = np.flatnonzero(is_prop)
        i_cplx = np.flatnonzero(~real_enough)
        i_nonpos = np.flatnonzero(real_enough & ~is_prop)

        # --- the distribution -----------------------------------------------
        say("")
        say("--- distribution (tolerance printed, not implied) ---")
        say(f"  total columns                : {n_tot}")
        say(f"  tolerance per column         : |Im| <= {REL_TOL:g} * max(1, |lam|)")
        say(f"  real & Re > 0  (PROPAGATING) : {int(prop.size)}")
        say(f"  real & Re <= 0 (evanescent)  : {int(i_nonpos.size)}")
        say(f"  not real enough (complex)    : {int(i_cplx.size)}")
        if i_cplx.size:
            ratio = np.abs(im[i_cplx]) / np.maximum(1.0, np.abs(lam[i_cplx]))
            say(f"    worst |Im|/max(1,|lam|)    : {ratio.max():.3e}   "
                f"(min {ratio.min():.3e}, median {np.median(ratio):.3e})")
            say(f"    nearest miss to the cutoff : {ratio.min():.3e}  "
                f"(would pass at tol {ratio.min():.1e})")
        if i_nonpos.size:
            say(f"    most negative Re           : {re[i_nonpos].min():+.6e}")

        # --- the kept-column extras, for the table --------------------------
        say("")
        say("--- optional keys (a missing key degrades the table, never raises) ---")
        corr_ey = _opt(data, "corr_ey", want_ndim=1)
        corr_ez = _opt(data, "corr_ez", want_ndim=1)
        idx_j = _opt(data, "j", want_ndim=1)
        beta_k = _opt(data, "beta", want_ndim=1)
        n_kept = None
        for name, arr in (("j", idx_j), ("corr_ey", corr_ey), ("corr_ez", corr_ez),
                          ("beta", beta_k)):
            if arr is not None:
                n_kept = int(arr.size) if n_kept is None else n_kept
        if n_kept is not None:
            say(f"  kept-column arrays have length {n_kept} "
                f"(one entry per column the audit kept, NOT per column of lam)")

        def kept_lookup(arr, col):
            """Map a lam index to a kept-row value, or None when not banked.

            The audit writes the kept arrays in lam order, in the loop that
            walks ``j`` ascending, so row position == rank among the kept
            indices.  Both ``j`` (explicit) and position are accepted; ``j``
            wins when present because it is the invariant the code guarantees.
            """
            if arr is None or n_kept is None:
                return None
            if idx_j is not None and idx_j.size == arr.size:
                hit = np.flatnonzero(np.asarray(idx_j).astype(int) == int(col))
                if hit.size == 1:
                    return arr[int(hit[0])]
                return None
            return None

        # --- top rows by Re -------------------------------------------------
        say("")
        say(f"--- top {TOP_N} columns by Re(lambda) ---")
        order = np.argsort(re)[::-1][:TOP_N]
        head = (f"  {'rank':>4} {'idx':>6} {'Re(lam)':>15} {'Im(lam)':>15} "
                f"{'|lam|':>13} {'beta':>13} {'corr_ey':>9} {'corr_ez':>9}")
        say(head)
        say("  " + "-" * (len(head) - 2))
        for rank, i in enumerate(order, start=1):
            is_prop = bool(real_enough[i]) and bool(np.isfinite(re[i])) and re[i] > 0.0
            beta = np.sqrt(re[i]) if is_prop else None
            say(f"  {rank:>4} {int(i):>6} {_fmt(re[i], '%15.6e')} "
                f"{_fmt(im[i], '%15.6e')} {_fmt(abs(lam[i]), '%13.6e')} "
                f"{_fmt(beta, '%13.6f')} "
                f"{_fmt(kept_lookup(corr_ey, i), '%9.4f')} "
                f"{_fmt(kept_lookup(corr_ez, i), '%9.4f')}")

        # --- every real-positive column, listed -----------------------------
        say("")
        say("--- every real-positive column (the propagating set, listed in full) ---")
        if prop.size == 0:
            say("  (none)")
        else:
            say(f"  {'idx':>6} {'Re(lam)=beta^2':>18} {'Im(lam)':>13} "
                f"{'beta':>13} {'corr_ey':>9} {'corr_ez':>9}")
            for i in prop:
                say(f"  {int(i):>6} {_fmt(re[i], '%18.10e')} {_fmt(im[i], '%13.3e')} "
                    f"{_fmt(np.sqrt(re[i]), '%13.6f')} "
                    f"{_fmt(kept_lookup(corr_ey, i), '%9.4f')} "
                    f"{_fmt(kept_lookup(corr_ez, i), '%9.4f')}")

        # --- the one-line verdict -------------------------------------------
        say("")
        say("--- verdict ---")
        only = (prop.size == 1)
        if only:
            say(f"  VERDICT: 1 propagating mode, column {int(prop[0])} -- "
                f"738 is the only one: "
                f"{'YES' if int(prop[0]) == 738 else f'NO (it is {int(prop[0])})'}")
        else:
            words = ", ".join(str(int(i)) for i in prop) if prop.size <= 12 else (
                ", ".join(str(int(i)) for i in prop[:12]) + f", ... ({prop.size} total)")
            say(f"  VERDICT: {prop.size} propagating modes, columns [{words}] -- "
                f"738 is the only one: {'YES' if prop.size == 1 else 'NO'}")
        say(f"  rejected mass: {int(i_cplx.size)} complex + "
            f"{int(i_nonpos.size)} real-non-positive of {n_tot} "
            f"(the audit persists the kept count only, c1_audit.py:610-621)")
        if prop.size == 0:
            say("  NOTE: no real-positive column at all -- the single-mode headline")
            say("        did not come from this file.")
        elif prop.size == 1:
            say("  NOTE: this settles the COUNT, not the physics.  One discrete")
            say("        propagating mode in a box whose outer walls are Neumann")
            say("        (emfit/mode2d.py:44, :1322-1324) is not the same claim as")
            say("        one propagating mode in the open cross-section.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
