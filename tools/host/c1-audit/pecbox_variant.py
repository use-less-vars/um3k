#!/usr/bin/env python3
# =============================================================================
# tools/host/c1-audit/pecbox_variant.py
#
# Close the c1-audit cross-section into a PEC box and re-run the *same* solve.
#
# WHAT c1_audit.py DOES, AND WHAT THIS CHANGES
#   c1_audit.py solves the mixed (e_t, e_z) pencil on the 31 x 17 node
#   cross-section of the banked TOLFLUX geometry with
#
#       BOUNDARIES = (ground, strip)          # c1_audit.py:286
#
#   -- the ground plane at z = 0 and the 3 mm strip at z = 1.6 mm are PEC, the
#   three remaining outer walls of the 20 mm x 7.6 mm cross-section are OPEN
#   (natural boundary).  This variant runs exactly the same 31 x 17 mixed solve
#   with the three remaining walls added to the PEC set:
#
#       wall at y = 0        (left  side; y is the 20 mm transverse axis)
#       wall at y = 20 mm    (right side)
#       wall at z = 7.6 mm   (top)          [height = 7.6 mm]
#
#   Ground (z = 0) and strip (z = 1.6 mm, y in [8.5, 11.5] mm) stay PEC, so the
#   result is a fully PEC-closed 20 mm x 7.6 mm box still containing the same
#   1.6 mm / eps_r = 4.4 substrate and the same 3 mm strip.
#
# HOW THE OVERRIDE IS DONE (and why it is not a copy of c1_audit.py)
#   c1_audit.py is a flat script: no main(), no functions around its steps, and
#   `BOUNDARIES` is a module-level constant consumed immediately at line 293
#   (pec_edge_mask), 294 (pec_node_mask) and 366 (solve_modes_mixed).  There is
#   therefore NO caller-side seam *inside* c1_audit.py -- by the time anything
#   of ours could touch a module attribute, the solve has already run.
#
#   The seam used instead is one level down, in the emfit API that c1_audit.py
#   calls: emfit/mode2d.py:539 pec_edge_mask(mesh, boundaries) and
#   emfit/mode2d.py:571 pec_node_mask(mesh, boundaries) are the *only* two
#   places where the boundary tuple turns into DOFs -- and solve_modes_mixed
#   itself re-derives its masks through those same two module-level functions
#   (emfit/mode2d.py:1083-1084), so c1_audit's own step-1 masks (its free_e /
#   free_n, used for the e_z LU and the reporting) and the solver's masks stay
#   identical by construction.  This module wraps those two functions for the
#   duration of `import c1_audit`, appending the three wall predicates, then
#   restores them.  c1_audit.py is imported and executed, never edited or
#   copied: no line of its ~665 lines is reproduced here, and emfit/ is never
#   modified on disk (the wrappers live on the in-memory module object only).
#
# SAFEGUARDS (all fatal on failure, exit non-zero)
#   (a) the boundary label set that actually reaches the assembler is printed,
#       together with per-wall node / edge counts found in the mesh;
#   (b) the PEC edge count before and after the override is printed and MUST
#       increase;
#   (c) the ground+strip PEC edge count is printed and MUST be unchanged (the
#       override may only add DOFs to the constrained set);
#   (d) c1_audit.py writes out/c1_table.txt and out/c1_spectrum.npz at import
#       time.  Those files belong to the *open-top* audit and are not mine to
#       overwrite: both writes are redirected to out/pecbox_table.txt and
#       out/pecbox_spectrum.npz, and the sha256 of the two original files is
#       compared before/after and MUST be unchanged.
#
# REPORT BLOCK
#   For EVERY propagating eigenvalue (real lambda at the audit's own
#   1e-6 relative tolerance on the imaginary part, beta^2 = +Re(lambda)) one
#   row: eigenvalue, beta, beta^2/k0^2, eps_eff, corr_e_y, corr_e_z, and the
#   dominant field component.  `N_PROPAGATING` counts EIGENVALUES and is
#   printed on its own; the |corr| screen is applied afterwards and reported
#   alongside, never folded into the count.
#
#   `dominant` is defined on the audit's own field lattices: the reconstructed
#   e_y on the (NYN-1) x NZN = 200 x 77 plane lattice and e_z on the
#   NYN x (NZN-1) = 201 x 76 lattice, compared by Frobenius norm -- the same
#   fields c1_audit.py correlates against the analytic plane basis.  They are
#   re-derived here only because c1_audit.py keeps the two scalar correlations
#   in `rows` and discards the field arrays; the re-derivation is checked
#   against c1_audit's own stored corr_e_y / corr_e_z and the largest
#   discrepancy is printed.
#
#   PEC_TE10_PREDICTION and ANCHOR_NOTE are labelled reference lines only --
#   documentation, not pass/fail gates.
#
# OPTIONAL
#   --self-test-anchor  additionally solves a plain 20 mm x 7.6 mm VACUUM PEC
#   box (all four walls, no dielectric, no strip) at 10 GHz and checks that
#   TE10 lands on beta^2/k0^2 = 0.43828 +/- 2 %.  It runs after the whole of
#   deliverable 1 has been printed and cannot affect it.
#
# Read-only w.r.t. the repo: the only files written are the two redirected
# outputs under tools/host/c1-audit/out/.
# =============================================================================
import builtins
import hashlib
import os
import sys
import time

import numpy as np
from scipy.interpolate import RegularGridInterpolator

C0 = 299792458.0                 # m/s, exactly (emfit.mode2d.C0)
K0_REF = 164.1794                # rad/m, the value named in the task's arithmetic
W_BOX = 0.020                    # m, transverse width of the box (y)
H_BOX = 0.0076                   # m, height of the box (z)
F_SELF_TEST = 10.0e9             # Hz, only for --self-test-anchor
SELF_TEST_BETA_TOL = 0.02        # relative, only for --self-test-anchor

HERE = os.path.dirname(os.path.abspath(__file__))
T0 = time.time()

OUTDIR = os.path.join(HERE, "out")
TABLE_OWN = os.path.join(OUTDIR, "c1_table.txt")            # c1_audit.py's
NPZ_OWN = os.path.join(OUTDIR, "c1_spectrum.npz")           # c1_audit.py's
TABLE_BOX = os.path.join(OUTDIR, "pecbox_table.txt")        # ours
NPZ_BOX = os.path.join(OUTDIR, "pecbox_spectrum.npz")       # ours


def say(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------
# repo discovery -- one answer only, from tools/host/_bootstrap.py, handed to
# c1_audit.py via C1_REPO (same fallback rule as run.sh: walk up until a
# directory holding emfit/).  The traps live in that module's docstring.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
from _bootstrap import bootstrap  # noqa: E402

# two sys.path entries, as before: the repo root, then this script's directory
REPO = bootstrap(start=HERE, extra_paths=(HERE,))
C1_REPO = REPO                          # module-level name, kept for importers
os.environ["C1_REPO"] = REPO            # c1_audit.py cannot re-derive another

import emfit.mode2d as m2                                    # noqa: E402

say("=" * 100)
say("pecbox_variant.py -- the c1 audit's mixed solve in a CLOSED 20 x 7.6 mm PEC box")
say("=" * 100)
say("repo       :", REPO)
say("emfit      :", os.path.join(REPO, "emfit"), "(FOUND)")
say("python     :", sys.version.split()[0])
say("numpy      :", np.__version__)
say("out dir    :", OUTDIR)
say("started    :", time.strftime("%Y-%m-%dT%H:%M:%S%z"))


def _sha256(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# the three walls that c1_audit.py leaves open
# ---------------------------------------------------------------------------
# The predicates take the (nn, 2) node array and use column 0 = y, column 1 = z
# (c1_audit.py:278-283 ground/strip read p[:, 1] = z and p[:, 0] = y).  The wall
# coordinates are taken from the mesh itself, so nothing here has to agree with
# a hard-coded millimetre figure.
_WALL_TOL = 1e-12


def _wall_specs(mesh):
    """(label, predicate) for the three open walls of the box."""
    y_lo = float(np.min(mesh.nodes[:, 0]))
    y_hi = float(np.max(mesh.nodes[:, 0]))
    z_hi = float(np.max(mesh.nodes[:, 1]))
    return (
        (f"wall_y={y_lo * 1e3:.6g}mm",
         lambda p, v=y_lo: np.abs(p[:, 0] - v) <= _WALL_TOL),
        (f"wall_y={y_hi * 1e3:.6g}mm",
         lambda p, v=y_hi: np.abs(p[:, 0] - v) <= _WALL_TOL),
        (f"wall_z={z_hi * 1e3:.6g}mm",
         lambda p, v=z_hi: np.abs(p[:, 1] - v) <= _WALL_TOL),
    )


_ORIG_EDGE_MASK = m2.pec_edge_mask
_ORIG_NODE_MASK = m2.pec_node_mask

_STATE = {
    "active": False,          # only armed while c1_audit.py executes
    "said_edges": False,
    "said_nodes": False,
    "labels": [],             # labels appended by the override
    "base_labels": [],        # labels c1_audit.py itself supplied
    "edge_before": None,
    "edge_after": None,
    "node_before": None,
    "node_after": None,
    "calls": 0,
}


def _describe(boundaries):
    """Names of c1_audit.py's own predicates -- no guessing: they are its own
    module-level functions, identified by __name__."""
    return [getattr(b, "__name__", repr(b)) for b in boundaries]


def _augment(mesh, boundaries):
    base = tuple(boundaries)
    specs = _wall_specs(mesh)
    return base + tuple(fn for _lbl, fn in specs), [lbl for lbl, _fn in specs], base


def _pec_edge_mask_override(mesh, boundaries=()):
    if not _STATE["active"]:
        return _ORIG_EDGE_MASK(mesh, boundaries)
    aug, wall_labels, base = _augment(mesh, boundaries)
    before = np.asarray(_ORIG_EDGE_MASK(mesh, boundaries), dtype=bool)
    after = np.asarray(_ORIG_EDGE_MASK(mesh, aug), dtype=bool)
    kept = int(np.count_nonzero(before & after))
    # ---- safeguard (b): the constrained edge set must GROW -----------------
    if int(after.sum()) <= int(before.sum()):
        raise SystemExit(
            "SAFEGUARD (b) FAILED: PEC edge count did not increase "
            f"({int(before.sum())} -> {int(after.sum())}); the walls did not reach "
            "the mesh, refusing to report a box that is not a box"
        )
    # ---- safeguard (c): ground+strip must be untouched ---------------------
    if kept != int(before.sum()):
        raise SystemExit(
            "SAFEGUARD (c) FAILED: ground/strip PEC edges changed "
            f"({int(before.sum())} before, {kept} still PEC); the override must "
            "only ADD to the constrained set"
        )
    _STATE.update(edge_before=int(before.sum()), edge_after=int(after.sum()),
                  labels=wall_labels, base_labels=_describe(base), calls=_STATE["calls"] + 1)
    # ---- safeguard (a): what actually reaches the assembler ---------------
    if not _STATE["said_edges"]:
        _STATE["said_edges"] = True
        say("")
        say("BOUNDARIES (pec_edge_mask / pec_node_mask seam)")
        say("  c1_audit.py passes        :", "(" + ", ".join(_describe(base)) + ")")
        say("  override appends         :", "(" + ", ".join(wall_labels) + ")")
        say("  effective set reaching the assembler (the PEC masks that eliminate")
        say("    DOFs before assembly) :",
            "(" + ", ".join(_describe(base) + wall_labels) + ")")
        say("  walls found in the mesh  :")
        for lbl, fn in zip(wall_labels, aug[len(base):]):
            on = np.asarray(fn(mesh.nodes), dtype=bool)
            one = np.asarray(_ORIG_EDGE_MASK(mesh, (fn,)), dtype=bool)
            say(f"    {lbl:<16s} nodes={int(on.sum()):5d}  edges PEC by this wall alone="
                f"{int(one.sum()):5d}")
        say(f"  SAFEGUARD (b) PEC edges  : {int(before.sum())} before -> "
            f"{int(after.sum())} after  (+{int(after.sum()) - int(before.sum())})  OK")
        say(f"  SAFEGUARD (c) ground+strip PEC edges : {int(before.sum())} before -> "
            f"{kept} still PEC  (UNCHANGED, OK)")
    return after


def _pec_node_mask_override(mesh, boundaries=()):
    if not _STATE["active"]:
        return _ORIG_NODE_MASK(mesh, boundaries)
    aug, wall_labels, base = _augment(mesh, boundaries)
    before = np.asarray(_ORIG_NODE_MASK(mesh, boundaries), dtype=bool)
    after = np.asarray(_ORIG_NODE_MASK(mesh, aug), dtype=bool)
    kept = int(np.count_nonzero(before & after))
    if int(after.sum()) <= int(before.sum()):
        raise SystemExit(
            "SAFEGUARD (b-node) FAILED: PEC node count did not increase "
            f"({int(before.sum())} -> {int(after.sum())})"
        )
    if kept != int(before.sum()):
        raise SystemExit(
            "SAFEGUARD (c-node) FAILED: ground/strip PEC nodes changed "
            f"({int(before.sum())} before, {kept} still PEC)"
        )
    _STATE.update(node_before=int(before.sum()), node_after=int(after.sum()))
    if not _STATE["said_nodes"]:
        _STATE["said_nodes"] = True
        say(f"  SAFEGUARD (b) PEC nodes  : {int(before.sum())} before -> "
            f"{int(after.sum())} after  (+{int(after.sum()) - int(before.sum())})  OK")
        say(f"  SAFEGUARD (c) ground+strip PEC nodes : {int(before.sum())} before -> "
            f"{kept} still PEC  (UNCHANGED, OK)")
        say("")
    return after


# ---------------------------------------------------------------------------
# output redirect: c1_audit.py must not overwrite the open-top audit's results
# ---------------------------------------------------------------------------
_REDIRECT = {
    os.path.abspath(TABLE_OWN): TABLE_BOX,
    os.path.abspath(NPZ_OWN): NPZ_BOX,
}


class _RedirectWrites:
    """Redirect exactly c1_audit.py's two output paths, everything else passes
    straight through (it is a path-exact shim, not a global interception)."""

    def __enter__(self):
        self._open = builtins.open
        self._savez = np.savez
        shim_open, shim_savez = self._open, self._savez

        def _key(file):
            try:
                return os.path.abspath(os.fspath(file))
            except TypeError:
                return None

        def _open_shim(file, *a, **kw):
            k = _key(file)
            if k is not None and k in _REDIRECT:
                say(f"REDIRECT   : {k}\n           -> {_REDIRECT[k]}  (original left untouched)")
                return shim_open(_REDIRECT[k], *a, **kw)
            return shim_open(file, *a, **kw)

        def _savez_shim(file, *a, **kw):
            k = _key(file)
            if k is not None and k in _REDIRECT:
                say(f"REDIRECT   : {k}\n           -> {_REDIRECT[k]}  (original left untouched)")
                return shim_savez(_REDIRECT[k], *a, **kw)
            return shim_savez(file, *a, **kw)

        builtins.open = _open_shim
        np.savez = _savez_shim

    def __exit__(self, *exc):
        builtins.open = self._open
        np.savez = self._savez
        return False


# ---------------------------------------------------------------------------
# run the audit with the override armed
# ---------------------------------------------------------------------------
say("")
say("SEAM       : c1_audit.py is a flat script (no main(), no boundary argument),")
say("             so the override is applied one level down at the emfit API:")
say("             emfit/mode2d.py:539 pec_edge_mask and :571 pec_node_mask are")
say("             wrapped while c1_audit.py imports.  solve_modes_mixed reaches")
say("             its masks through those same two functions (mode2d.py:1083-1084),")
say("             so step-1 masks and solver masks cannot disagree.")
say("")
say("c1_audit.py output is imported unmodified; its own two output files are")
say("redirected so the open-top audit's results survive:")
say(f"  {TABLE_OWN}  ->  {TABLE_BOX}")
say(f"  {NPZ_OWN}  ->  {NPZ_BOX}")

_HASH_BEFORE = {_p: _sha256(_p) for _p in (TABLE_OWN, NPZ_OWN)}
for _p, _h in _HASH_BEFORE.items():
    say(f"GUARD pre  : {_p} sha256={'absent' if _h is None else _h[:32] + '...'}")

m2.pec_edge_mask = _pec_edge_mask_override
m2.pec_node_mask = _pec_node_mask_override
_STATE["active"] = True
try:
    with _RedirectWrites():
        import c1_audit                                        # noqa: E402
finally:
    _STATE["active"] = False
    m2.pec_edge_mask = _ORIG_EDGE_MASK
    m2.pec_node_mask = _ORIG_NODE_MASK

if not _STATE["calls"]:
    raise SystemExit(
        "SAFEGUARD FAILED: the override never fired -- c1_audit.py did not call "
        "emfit.mode2d.pec_edge_mask through the module object; the run above is "
        "the open-top geometry, not the box"
    )

_HASH_AFTER = {_p: _sha256(_p) for _p in (TABLE_OWN, NPZ_OWN)}
say("")
for _p, _h0 in _HASH_BEFORE.items():
    _h1 = _HASH_AFTER[_p]
    if _h0 != _h1:
        raise SystemExit(
            f"SAFEGUARD (d) FAILED: {_p} was modified (sha256 "
            f"{'absent' if _h0 is None else _h0[:16]} -> "
            f"{'absent' if _h1 is None else _h1[:16]})"
        )
    say(f"SAFEGUARD (d) existing output untouched: {os.path.basename(_p)} "
        f"sha256={'absent (was absent)' if _h0 is None else _h0[:32] + '...'}  OK")
say(f"             box outputs : {TABLE_BOX}")
say(f"                           {NPZ_BOX}")

# ===========================================================================
# THE REPORT BLOCK
# ===========================================================================
lam = np.asarray(c1_audit.lam)
vecs_all = np.asarray(c1_audit.vecs_all)
real_enough = np.abs(np.imag(lam)) <= 1e-6 * np.maximum(1.0, np.abs(lam))
lam_re = np.real(lam)
propagating = real_enough & np.isfinite(lam_re) & (lam_re > 0.0)
n_prop = int(np.count_nonzero(propagating))

by_col = {int(r[0]): r for r in c1_audit.rows}

say("")
say("#" * 100)
say(f"#  N_PROPAGATING = {n_prop}")
say(f"#  eigenvalues with |Im(lambda)| <= 1e-6 max(1,|lambda|) and beta^2 = +Re(lambda) > 0")
say(f"#  (of {int(lam.size)} QZ columns of the mixed pencil, {_STATE['edge_after']} PEC edges)")
say("#" * 100)


def _reconstruct(j, bsq, beta, eps_eff, resid):
    """e_y / e_z for QZ column j, on the audit's own planes.

    Mirrors c1_audit.py:455-493 (same LU route, same +-sign, same lattices) and
    is verified against c1_audit's stored correlations by the caller.
    """
    x = np.real(vecs_all[:, j])
    nrm = float(np.linalg.norm(x))
    if nrm == 0.0:
        return None
    x = x / nrm
    e_t = np.zeros(int(c1_audit.mesh.n_edges))
    e_t[c1_audit.free_e] = x
    z_free = np.asarray(
        c1_audit.lu.solve(np.asarray(c1_audit.c_f.T @ x).ravel()), dtype=float
    ).ravel()
    e_z_node = np.zeros(int(c1_audit.mesh.n_nodes), dtype=float)
    e_z_node[c1_audit.free_n] = beta * z_free
    MODE = m2.Mode2D(
        freq=float(c1_audit.mode.freq), k0=float(c1_audit.K0), beta=float(beta),
        beta_sq=float(bsq), eps_eff=float(eps_eff), residual=float(resid),
        candidates=tuple(), curl_ratio=None, chosen=int(j), sigma=1.0,
        n_dof=int(c1_audit.mode.n_dof), n_pec=int(c1_audit.mode.n_pec),
        e_t=e_t, mesh=c1_audit.mesh, e_z=None,
    )
    E_t = MODE.e_at(c1_audit._ey_pts).reshape(c1_audit.NYN - 1, c1_audit.NZN, 2)
    e_y = E_t[:, :, 0] * c1_audit.CELL
    ez_grid = np.asarray(e_z_node, dtype=float).reshape(c1_audit._nz, c1_audit._nx)
    ez_itp = RegularGridInterpolator((c1_audit.ZS, c1_audit.XS), ez_grid,
                                     bounds_error=True)
    e_z = -ez_itp(c1_audit._ez_pts).reshape(c1_audit.NYN, c1_audit.NZN - 1)
    return e_y, e_z


say("")
say("REPORT -- one row per propagating eigenvalue (dominant field component on the")
say("          audit's own planes: e_y (NYN-1)xNZN=200x77 vs e_z NYNx(NZN-1)=201x76,")
say("          compared by Frobenius norm)")
say("-" * 148)
say("  idx    col        Re(lambda)        Im(lambda)          beta      beta^2/k0^2 "
    "        eps_eff        corr_e_y        corr_e_z   dominant")
say("-" * 148)

screen_flags = []
corr_mismatch = 0.0
dom_counts = {"e_y": 0, "e_z": 0, "n/a": 0}
for idx, j in enumerate(np.flatnonzero(propagating), start=1):
    j = int(j)
    bsq = float(lam_re[j])
    row = by_col.get(j)
    if row is None:
        beta = float(np.sqrt(bsq))
        eps_eff = float(bsq / (c1_audit.K0 * c1_audit.K0))
        cy = cz = float("nan")
        resid = float("nan")
    else:
        _jj, bsq, beta, eps_eff, cy, cz, resid, _shape_ok = row
        bsq, beta, eps_eff, cy, cz = (float(bsq), float(beta), float(eps_eff),
                                      float(cy), float(cz))
    # dominant component
    dom = "n/a"
    try:
        fields = _reconstruct(j, bsq, beta, eps_eff, resid)
        if fields is not None:
            e_y, e_z = fields
            ny_norm = float(np.linalg.norm(e_y))
            nz_norm = float(np.linalg.norm(e_z))
            dom = "e_y" if ny_norm > nz_norm else "e_z"
            if np.isfinite(cy) and np.isfinite(cz):
                cy_chk = c1_audit.corr(c1_audit.A_ey, e_y)
                cz_chk = c1_audit.corr(c1_audit.A_ez, e_z)
                for a, b in ((cy, cy_chk), (cz, cz_chk)):
                    if np.isfinite(a) and np.isfinite(b):
                        corr_mismatch = max(corr_mismatch, abs(a - b))
    except Exception as exc:                        # never lose the row over this
        dom = f"n/a ({type(exc).__name__})"
    dom_counts["e_y" if dom == "e_y" else "e_z" if dom == "e_z" else "n/a"] += 1
    passed = bool(np.isfinite(cy) and np.isfinite(cz)
                  and abs(cy) >= c1_audit.CORR_EY_MIN
                  and abs(cz) <= c1_audit.CORR_EZ_MAX)
    screen_flags.append(passed)
    say(f"{idx:6d} {j:7d} {lam_re[j]:+16.9e} {np.imag(lam[j]):+16.9e} {beta:13.6e} "
        f"{bsq / (c1_audit.K0 ** 2):16.9f} {eps_eff:15.9f} {cy:+15.9f} {cz:+15.9f}   {dom}")
say("-" * 148)

n_screen = int(np.count_nonzero(screen_flags))
say("")
say("#" * 100)
say(f"#  N_PROPAGATING = {n_prop}")
say(f"#  N_PASSING_CORRELATION_SCREEN = {n_screen}"
    f"   (|corr_e_y| >= {c1_audit.CORR_EY_MIN:g} and |corr_e_z| <= "
    f"{c1_audit.CORR_EZ_MAX:g}; applied AFTER the count above, not folded into it)")
say(f"#  (c1_audit.py's own ok_arr also requires shape_pair_ok and gives "
    f"{int(np.count_nonzero(c1_audit.ok_arr))} of {len(c1_audit.rows)})")
say(f"#  dominant-field tally: e_y {dom_counts['e_y']}, e_z {dom_counts['e_z']}, "
    f"unavailable {dom_counts['n/a']}")
say(f"#  re-derivation cross-check: max |corr(re-derived) - corr(c1_audit row)| = "
    f"{corr_mismatch:.3e}")
say("#" * 100)

if len(c1_audit.rows) != n_prop:
    say(f"NOTE: c1_audit.py's rows hold {len(c1_audit.rows)} columns for {n_prop} "
        "propagating eigenvalues (it also drops zero-norm eigenvectors); the count "
        "above is the eigenvalue count.")
say("")
say("NOTE: the single mode that c1_audit.py's own step-2 / step-6 lines call the")
say("      'chosen' mode is emfit's own pick (largest positive beta^2 below the")
say("      residual tolerance, emfit/mode2d.py:1156-1167), not the quasi-TEM mode;")
say("      the per-eigenvalue table above is the audit's actual product.")
say("NOTE: c1_audit.py's own REPRODUCTION CHECK / REPRO lines will read FAIL here.")
say("      Its anchors (corr_e_y 0.9207707848111418 / corr_e_z 0.11916043239134175)")
say("      belong to the open-top geometry; closing the box moves every eigenvalue,")
say("      so those anchors are not a gate for this variant.")

# ---------------------------------------------------------------------------
# labelled reference lines -- documentation, NOT pass/fail
# ---------------------------------------------------------------------------
_f0 = K0_REF * C0 / (2.0 * np.pi)
_fc = C0 / (2.0 * W_BOX)
_ratio = _fc / _f0
_pred = 1.0 - _ratio ** 2
say("")
say(f"PEC_TE10_PREDICTION = {_pred:.6f}")
say(f"    1 - (c/(2W)/f0)^2 with W = {W_BOX * 1e3:.3f} mm")
say(f"    f0            = {_f0:.6f} Hz = {_f0 / 1e9:.9f} GHz   (k0 = {K0_REF!r} rad/m)")
say(f"    c/(2W)        = {_fc:.6f} Hz = {_fc / 1e9:.9f} GHz")
say(f"    ratio         = {_ratio:.6f}   ratio^2 = {_ratio ** 2:.6f}")
say("    documentation only -- this is the TE10 of a 20 mm vacuum PEC box at this")
say("    f0; the geometry solved here has a 1.6 mm eps_r = 4.4 substrate and a strip,")
say("    so no measured eps_eff is expected to equal it.")
say(f"    for reference, the audit's own k0 : {float(c1_audit.K0)!r} rad/m "
    f"(f = {float(c1_audit.F0) / 1e9:.9f} GHz) -> "
    f"prediction {1.0 - (_fc / (float(c1_audit.F0))) ** 2:.6f}")
say("")
say("ANCHOR_NOTE: beta^2/k0^2 = 0.4383 is docstring-only prose at "
    "emfit/mode2d.py:1020-1022, no executable counterpart in the repo, "
    "arithmetically consistent with a 20 mm vacuum PEC box at 10 GHz rather than "
    "this geometry -- its absence here is expected, not a failure.")

# ---------------------------------------------------------------------------
# optional: TE10 anchor in a plain vacuum PEC box
# ---------------------------------------------------------------------------
def _self_test_anchor():
    say("")
    say("=" * 100)
    say("SELF-TEST ANCHOR (--self-test-anchor): plain 20 x 7.6 mm VACUUM PEC box at 10 GHz")
    say("=" * 100)
    xs = np.linspace(0.0, W_BOX, 31)
    zs = np.linspace(0.0, H_BOX, 17)
    mesh_v = m2.structured_mesh(xs, zs)
    bnds = (
        lambda p: np.abs(p[:, 0] - 0.0) <= _WALL_TOL,
        lambda p: np.abs(p[:, 0] - W_BOX) <= _WALL_TOL,
        lambda p: np.abs(p[:, 1] - 0.0) <= _WALL_TOL,
        lambda p: np.abs(p[:, 1] - H_BOX) <= _WALL_TOL,
    )
    k0v = m2.k0_from_freq(F_SELF_TEST)
    mesh_v_n_edges = int(mesh_v.n_edges)
    free_e_v = int(np.count_nonzero(~_ORIG_EDGE_MASK(mesh_v, bnds)))
    say(f"  mesh      : {int(xs.size)} x {int(zs.size)} nodes, {mesh_v_n_edges} edges, "
        f"{free_e_v} free after PEC")
    if free_e_v > int(m2._MIXED_DENSE_MAX):
        raise RuntimeError(f"{free_e_v} free edges > _MIXED_DENSE_MAX "
                           f"{int(m2._MIXED_DENSE_MAX)}: dense QZ not available")
    cap = {}
    save = m2._dense_eig

    def _capture(a, b):
        lam_v, vec_v = save(a, b)
        cap["lam"] = np.asarray(lam_v)
        return lam_v, vec_v

    _t = time.time()
    m2._dense_eig = _capture
    try:
        m2.solve_modes_mixed(mesh_v, k0v, sigma=1.0,
                             eps_r=lambda p: np.ones(p.shape[0]), boundaries=bnds)
    finally:
        m2._dense_eig = save
    say(f"  solve     : {time.time() - _t:.2f} s, {int(cap['lam'].size)} QZ columns")
    lam_v = cap["lam"]
    re_v = np.abs(np.imag(lam_v)) <= 1e-6 * np.maximum(1.0, np.abs(lam_v))
    rr = np.real(lam_v)
    keep = re_v & np.isfinite(rr) & (rr > 0.0)
    ee = rr[keep] / (k0v * k0v)
    pred_v = 1.0 - (_fc / F_SELF_TEST) ** 2
    say(f"  f0        : {F_SELF_TEST / 1e9:.6f} GHz, k0 = {k0v:.9f} rad/m, "
        f"c/(2W) = {_fc / 1e9:.9f} GHz")
    say(f"  TE10 target: 1 - (c/(2W)/f0)^2 = {pred_v:.6f}")
    say(f"  N_PROPAGATING = {int(ee.size)}")
    for v in np.sort(ee)[::-1]:
        say(f"    beta^2/k0^2 = {v:.9f}")
    if ee.size == 0:
        say("  SELF_TEST_ANCHOR = FAIL (no propagating eigenvalue in the vacuum box)")
        return False
    k = int(np.argmin(np.abs(ee - pred_v)))
    rel = abs(float(ee[k]) - pred_v) / pred_v
    ok = bool(rel <= SELF_TEST_BETA_TOL)
    say(f"  closest   : beta^2/k0^2 = {float(ee[k]):.9f}   target {pred_v:.6f}   "
        f"rel_delta = {rel:.3e}   tol = {SELF_TEST_BETA_TOL:g} (relative)")
    say(f"  SELF_TEST_ANCHOR = {'PASS' if ok else 'FAIL'}")
    return ok


_self_test_ok = None
if "--self-test-anchor" in sys.argv[1:]:
    try:
        _self_test_ok = _self_test_anchor()
    except Exception as exc:
        say(f"  SELF_TEST_ANCHOR = FAIL ({type(exc).__name__}: {exc})")
        _self_test_ok = False
    say("  (the self-test writes nothing and ran after the report above)")

say("")
say("=" * 100)
say(f"DONE pecbox_variant.py elapsed={time.time() - T0:.1f}s N_PROPAGATING={n_prop} "
    f"screen_passed={n_screen} pec_edges={_STATE['edge_before']}->{_STATE['edge_after']} "
    f"self_test_anchor="
    f"{'not-requested' if _self_test_ok is None else ('PASS' if _self_test_ok else 'FAIL')} "
    f"table={TABLE_BOX} npz={NPZ_BOX}")
if _self_test_ok is False:
    sys.exit(3)
