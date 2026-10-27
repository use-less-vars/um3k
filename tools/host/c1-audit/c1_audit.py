"""c1_audit.py -- audit EVERY propagating eigenvector of the mixed 2-D pencil.

Question
--------
``.scratch/logs/s10118_basis.py`` identified ONE mode of the mixed solver and
compared it with the analytic plane basis, banking ``corr_e_y = 0.9207707848111418``
and ``corr_e_z = 0.11916043239134175`` (``.scratch/s10118_result.txt:105``).  Does
that agreement mean the *identified* mode is special, or does every propagating
eigenvector of the same pencil agree about as well?  This script answers it by
keeping the whole dense spectrum and running the identical reconstruction /
correlation for every column.

Design constraints (why the code looks like this)
-------------------------------------------------
* ``solve_modes_mixed`` (emfit/mode2d.py:935) returns only the *selected* mode's
  ``e_t``; the other eigenvectors are not exposed.  The only honest way to get
  them all is the hook the earlier experiment already used
  (``.scratch/logs/s10118_basis.py:162-175``): wrap ``m2._dense_eig``
  (``from scipy.linalg import eig as _dense_eig``, emfit/mode2d.py:79, called at
  emfit/mode2d.py:1120), capture ``(lam, vecs)`` and restore the original in a
  ``finally`` block.  Nothing in ``emfit`` is modified.
* The capture also grabs the dense ``a`` and ``b`` the QZ was called with, so the
  per-column backward error is recomputed with the *same* scale-aware formula
  the solver uses for its own audit trail (emfit/mode2d.py:1127-1139):
  ``||A x - lam B x|| / ((||A||_F + |lam| ||B||_F) ||x||)``.
* ``e_y`` comes from the public ``Mode2D.e_at`` (emfit/mode2d.py:742) on the
  plane's y-cell / z-node lattice, exactly as ``.scratch/logs/s10118_basis.py:301-314``
  and ``tools/corr_ez_101_20.py:291-293`` build it.
* ``e_z`` comes from the longitudinal block by the same LU route the solver uses
  (emfit/mode2d.py:1105-1107, 1174-1175) and ``.scratch/logs/s10118_basis.py:218-224``,
  but **signed**: ``beta * z_free`` rather than ``abs(beta * z_free)``.  The
  absolute value in the old script is the thing under audit, so it is not
  reproduced here; the sign is physical and is kept.

Citation table for every number / call this file uses
-----------------------------------------------------
banked anchors
    tools/corr_ez_101_20.py:78-80   CORR_EZ_DISK / CORR_EY_DISK
    .scratch/s10118_result.txt:105  the same two numbers as printed on disk
    .scratch/logs/corr_ez_followup.txt:43, :47  reproduced / baseline rows
geometry + mesh (copied, not invented)
    .scratch/logs/s10118_basis.py:66-75   geometry keys, Y0/Y1
    .scratch/logs/s10118_basis.py:78-88   axis() chunks, XS/ZS, structured_mesh
    .scratch/logs/s10118_basis.py:97-118  eps_of / ground / strip / BOUNDARIES / K0
    .scratch/logs/s10118_basis.py:120-127 pec_edge_mask / pec_node_mask / free_e /
                                          free_n / the _MIXED_DENSE_MAX guard
model + solve
    emfit/mode2d.py:287          structured_mesh
    emfit/mode2d.py:378-394      _per_triangle (centroid sampling -- see below)
    emfit/mode2d.py:397          assemble
    emfit/mode2d.py:469          assemble_mixed
    emfit/mode2d.py:539, :571    pec_edge_mask, pec_node_mask
    emfit/mode2d.py:787          k0_from_freq
    emfit/mode2d.py:935-945      solve_modes_mixed signature (NO interface kwarg)
    emfit/mode2d.py:1051-1052    assemble + assemble_mixed call sites
    emfit/mode2d.py:1105-1120    h block, splu, dense pencil, _dense_eig call
    emfit/mode2d.py:1127-1139    per-candidate normalisation + scale-aware residual
    emfit/mode2d.py:605-666      Mode2D fields (frozen dataclass, no __post_init__)
    emfit/mode2d.py:742          Mode2D.e_at -> (n, 2), [:, 0] = E_y component
field reconstruction + correlation
    .scratch/logs/s10118_basis.py:218-224  assemble_mixed, h_blk, c_f, splu, z_free,
                                           e_z_node[free_n] = |beta * z_free|
    .scratch/logs/s10118_basis.py:301-314  plane lattices, e_at sampling, e_y = ...*CELL
    .scratch/logs/s10118_basis.py:323-356  node-ordering guard, ez_grid reshape,
                                           RegularGridInterpolator((ZS, XS)), ez sampling
    .scratch/logs/s10118_basis.py:369      e_z = -e_z_mag (E points strip -> ground)
    .scratch/logs/s10118_basis.py:385-390  analytic reference call pair
    tools/corr_ez_101_20.py:118-124        corr(a, b), NaN on zero norm / size mismatch
    tools/corr_ez_101_20.py:183-188        the same analytic reference call pair
    tools/corr_ez_101_20.py:206-208        plane_mode() does NOT expose phi

Why the criterion uses |corr|
-----------------------------
A generalised eigenvector is defined up to an arbitrary non-zero scalar, and
``scipy.linalg.eig`` fixes no sign: column ``j`` may come back as ``+x`` or
``-x`` (and ``e_z`` is linear in ``x``, so it flips with it).  A signed
correlation would therefore report the same mode as ``+0.92`` or ``-0.92``
depending on LAPACK's internal choices, which is not a property of the physics.
The table is consequently ranked and thresholded on ``|corr|`` -- and the
*signed* values are printed alongside, so nothing is hidden.
The thresholds are ``|corr_e_y| >= 0.89`` and ``|corr_e_z| <= 0.30``: e_y must
carry the shape, e_z must *not* (the analytic e_z has both signs within one
column, which is why an |e_z| reconstruction has a ceiling far below 1 --
tools/corr_ez_101_20.py:227-228).

What this script does NOT do
----------------------------
* It does not resample eps_r, assemble, or solve anything twice: the pencil is
  built once by ``solve_modes_mixed`` and the blocks are rebuilt once.
* It does not touch emfit/.  ``m2._dense_eig`` is restored in a ``finally``.
* ``PANA`` (analytic ``PlaneMode``) exposes only e_y/e_z/h_y/h_z -- no ``phi``
  (tools/corr_ez_101_20.py:206-208) -- and no potential is correlated here.

Mesh and output knobs (environment only -- this script has no argument parser)
-----------------------------------------------------------------------------
* ``C1_STRIP_CELLS`` -- cells across the strip band.  Default 12, the banked
  31 x 17 node mesh (9 | 12 | 9 across, 8 | 4 | 4 up).  Anything else is a
  DIFFERENT mesh and a different spectrum, so pair it with ``C1_OUTDIR``:
  a variant must not overwrite the captures the rest of the record reads.
* ``C1_OUTDIR`` -- output directory.  Default ``out/`` beside this file, where
  ``c1_spectrum.npz`` and ``c1_table.txt`` live and are read from.
* ``C1_ALLOW_REMESH=1`` -- permit the non-banked mesh that ``C1_STRIP_CELLS``
  produces.  The banked-cache guard (step 1) is a mesh-identity gate: a
  refinement study is a different mesh ON PURPOSE, and without this the run is
  refused.  Banked column unknown then, so the reproduction check runs on the
  best-|corr_e_y| column and is EXPECTED to fail -- loud, not fatal.
* ``C1_Y_AIR_CELLS`` -- cells in EACH of the two air bands of the first axis,
  the 9 | 9 either side of the strip.  Default 9, the banked mesh; the strip
  band (``C1_STRIP_CELLS``) is untouched, so the family stays symmetric.
* ``C1_Z_CELLS`` -- cells in the three bands of the second axis, substrate |
  interface | air, as three comma-separated ints.  Default ``8,4,4``, the
  banked mesh; each value must be >= 1.

Unset, all of them leave the mesh and both paths exactly as they were.

Run:
    tools/host/c1-audit/run.sh
or directly:
    cd <repo> && python3 -u tools/host/c1-audit/c1_audit.py
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

import numpy as np
import scipy
from scipy.interpolate import RegularGridInterpolator
from scipy.sparse.linalg import splu

# ---------------------------------------------------------------------------
# repo layout: this file lives at <repo>/tools/host/c1-audit/c1_audit.py,
# which is THREE levels below the repository root.  Never count ".." levels
# here -- a fixed count used to yield <repo>/tools instead of <repo>, which is
# why `import emfit` below failed with ModuleNotFoundError.  The root is now
# discovered by tools/host/_bootstrap.py (or handed over by run.sh via
# C1_REPO) and validated there; that module's docstring keeps the traps.
#
# run this audit through tools/host/c1-audit/run.sh, which discovers the root
# (git rev-parse --show-toplevel, else walk up to emfit/) and exports C1_REPO;
# do not invoke c1_audit.py directly.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))

#: run.sh exports the root it discovered; only a direct invocation needs the
#: local walk.  Captured BEFORE bootstrap(), which writes REPO into the
#: environment -- after that the "came from the environment" banner is gone.
_REPO_ENV = (os.environ.get("REPO", "").strip()
             or os.environ.get("C1_REPO", "").strip())

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
from _bootstrap import bootstrap  # noqa: E402

REPO = bootstrap(start=HERE)
EMFIT_DIR = os.path.join(REPO, "emfit")     # presence validated in find_repo()

import emfit.modal as M  # noqa: E402
import emfit.mode2d as m2  # noqa: E402
from emfit.mode_profile import microstrip_mode_profile  # noqa: E402

GEOJSON = os.path.join(REPO, ".scratch", "tol", "logs", "TOLFLUX.json")
PLANES = os.path.join(REPO, ".scratch", "tol", "logs", "TOLFLUX_planes.npz")
BANKED = os.path.join(REPO, ".scratch", "s10118_mixed_mode.npz")
#: repointed by ``C1_OUTDIR`` in the same env-only style as the repo override
#: above (no argument parser here).  Unset -- the normal case -- this is ``out/``
#: beside this file, byte for byte the directory run.sh and pecbox_variant.py
#: already read and write.
_OUTDIR_ENV = os.environ.get("C1_OUTDIR", "").strip()
OUTDIR = os.path.abspath(_OUTDIR_ENV) if _OUTDIR_ENV else os.path.join(HERE, "out")
NPZ_PATH = os.path.join(OUTDIR, "c1_spectrum.npz")
TABLE_PATH = os.path.join(OUTDIR, "c1_table.txt")

#: banked record this audit must reproduce on the identified column
ANCHOR_CORR_EY = 0.9207707848111418      # tools/corr_ez_101_20.py:80
ANCHOR_CORR_EZ = 0.11916043239134175     # tools/corr_ez_101_20.py:78

#: banked ``R_extracted`` of the identified column of the PMC mesh (QZ column
#: 738): ``sum(e_z_vv^2) / sum(e_y^2)`` over the extracted field.  Unlike the two
#: correlation anchors this one is gated EXACTLY, not to a relative tolerance: it
#: is one float64 division of two float64 sums over one fixed deposited field, so
#: on the mesh that reproduces the banked column it comes back bit-identical, and
#: any difference means the summed field is no longer the identified column's.
#: Gated only where that identity holds -- the resolved banked column has to BE
#: the cached identified column (see the step-5 resolution); on any other mesh
#: there is no anchor and the measured ratio is reported, not gated.  The PEC box
#: is such a mesh: its solver-selected column is 699, ratio 4.163656524825077.
#: HISTORY, recorded rather than dropped: before the step-5 fix, ``R_extracted``
#: was formed from loop-scoped arrays, i.e. from the LAST SCANNED propagating
#: column.  On the PMC mesh that column happens to be the identified column, so
#: 4.0489791163982565 is also what the defective code wrote.  On the PEC box it
#: wrote 70.63501855512833 -- column 704's ratio (the failing witness, second of
#: the two propagating columns) -- while the mode the solver actually selects is
#: column 699, whose ratio is 4.163656524825077.  70.63501855512833 is therefore
#: a wrong-column artefact and must never be quoted as a measurement; it survives
#: in the already-banked out/pecbox_spectrum.npz (not overwritten here) and in
#: pecbox_variant.py's TRAP-2 note.
ANCHOR_R_EXTRACTED = 4.0489791163982565

#: shape-pair criterion (see the module docstring): e_y must match, e_z must not.
#: ``CORR_EY_MIN`` is DERIVED, not a round number: the population is the two
#: clean PMC mesh legs, ``|corr_e_y| = 0.920770784811142`` (31x17) and
#: ``0.938702180035899`` (41x22) (decisions.md:7875; docs/design/zfree_shape.md:77,
#: row M2), the rule is the same k=2 round-up used for ``CORR_EZ_VV_MIN`` below:
#: S = 0.938702180035899 - 0.920770784811142 = 0.017931395224757, and
#: 0.9207707848111419 - 2*S = 0.8849079943616279 -> 0.89.  Failing witness:
#: PEC col 704, ``corr_e_y = -0.426418989``, 0.46 below the bar.  The wider
#: three-leg population (adding 0.912343044811209) gives 0.86 and is NOT adopted:
#: widening a population must not loosen a bar, and that leg's e_y attribution is
#: disputed (docs/design/m3c_gate_v2.md, section 3.3).  0.89 is the LOOSER of the
#: two correlation bars here (``CORR_EZ_VV_MIN = 0.91``); neither is the other
#: reused -- different statistic, different spread.
#: NOTE the side effect: this constant also sets the floor of the SUPERSEDED
#: ``shape_pair_ok_legacy`` (line ~562), so that floor moves 0.90 -> 0.89 too.
#: No recorded verdict flips (passing legs sit at 0.92 / 0.94, the witness at
#: 0.43), but a re-run writes ``criterion = [0.89, 0.30]`` into the npz where the
#: banked one carries 0.90; nothing in the tree compares those arrays.
CORR_EY_MIN = 0.89
CORR_EZ_MAX = 0.30

#: derived bar for the same-component vertical statistic; derivation and its
#: self-reference caveat: docs/design/corr_ez_vv_threshold.md.  NOT the
#: ``corr_e_y`` >= 0.89 number reused (a vertical reference against the mode's
#: VERTICAL component is a different reading, with its own spread).
#: ``CORR_EZ_MAX`` is untouched; ``CORR_EY_MIN`` is the derived 0.89 above, so the
#: SUPERSEDED ``shape_pair_ok_legacy`` floor moves with it (see the note there).
#: Rule: T = (weakest passing leg) - 2 * S_good,
#: rounded UP to 0.01, where S_good = 0.0132433711770793 is the SPREAD of the
#: three passing legs (max - min) -- which on this population is also the
#: 31x17 -> 41x22 PMC step on |corr_ez_vv| itself
#: (.scratch/logs/d22_41x22_replay.txt:70-74; zero solves, reproduces the
#: banked values to 4.3e-16).  0.9352867303487647 - 2*S_good =
#: 0.9087999879946061 -> 0.91; rounding up tightens by 0.0012, deliberately.
#: The passing legs sit 1.91 / 2.91 / 2.03 spreads above the bar; PEC col 704
#: sits 62.4 spreads below.  S_good is measured FROM the legs it judges, so it
#: bounds reproducibility, not accuracy (two points, no sigma).  The legacy
#: F = 1.5657e-4 (docs/design/c2b_preregistration.md:29) is the SUPERSEDED
#: statistic's spread: no conversion exists, and it puts the bar at 0.934974.
CORR_EZ_VV_MIN = 0.91

#: reproduction gate (step 6): relative tolerance on |measured - banked| / |banked|.
#: 1e-6 is tight enough to catch the 2e-2-scale drift the analytic reference
#: placement has already produced once (superseded 0.1462 in
#: .scratch/logs/mesh51.log:18 vs the current 0.1192), and loose enough not to
#: fire on ordinary LAPACK / summation non-determinism.
REPRO_RTOL = 1e-6

T0 = time.time()
_LOCK = threading.Lock()
_STATE = {"phase": "startup"}


def say(*a) -> None:
    """Print one flushed line (stdout is tee'd into out/run.log by run.sh)."""
    line = " ".join(str(x) for x in a)
    with _LOCK:
        print(line, flush=True)


def phase(name: str) -> None:
    """Publish the current phase for the heartbeat line."""
    with _LOCK:
        _STATE["phase"] = name


class Heartbeat(threading.Thread):
    """Daemon thread: one PROGRESS line every 25 s, so a 2-minute QZ looks alive."""

    PERIOD = 25.0

    def __init__(self) -> None:
        super().__init__(daemon=True, name="c1-heartbeat")

    def run(self) -> None:
        last = 0.0
        while True:
            time.sleep(1.0)
            now = time.time() - T0
            if now - last >= self.PERIOD:
                last = now
                with _LOCK:
                    ph = _STATE["phase"]
                print(f"PROGRESS [heartbeat] {now:.1f} s phase={ph}", flush=True)


def corr(a, b) -> float:
    """Cosine overlap; NaN on a zero norm or a size mismatch.

    Copied from tools/corr_ez_101_20.py:118-124 so the number here is the same
    statistic the banked record was measured with.
    """
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0 or a.size != b.size:
        return float("nan")
    return float(np.sum(a * b) / (na * nb))


Heartbeat().start()

# ---------------------------------------------------------------------------
# step 0 -- provenance
# ---------------------------------------------------------------------------
phase("step0 provenance")
say("=" * 100)
say("c1_audit.py -- full-spectrum audit of the mixed 2-D pencil vs the analytic basis")
say("=" * 100)
say("EXPECTED COST: dense QZ ~111 s on the 31x17 node mesh (1486 edges, 1444 free),")
say("               ~1-2 GB RAM peak, per-mode loop ~10-20 s, TOTAL ~2-4 min.")
say("repo       :", REPO, "(from C1_REPO)" if _REPO_ENV else "(discovered)")
say("emfit      :", EMFIT_DIR, "(FOUND)")
say("python     :", sys.version.split()[0])
say("numpy      :", np.__version__)
say("scipy      :", scipy.__version__)
say("out dir    :", OUTDIR)

phase("step1 geometry")
for _p, _tag in ((GEOJSON, "geojson"), (PLANES, "plane npz")):
    if not os.path.exists(_p):
        raise SystemExit(f"missing {_tag}: {_p}")

os.makedirs(OUTDIR, exist_ok=True)

# ---------------------------------------------------------------------------
# step 1 -- geometry, mesh, PEC masks, k0
# (.scratch/logs/s10118_basis.py:66-127, copied verbatim in substance)
# ---------------------------------------------------------------------------
G = json.load(open(GEOJSON))["geometry"]
W, H = G["width"], G["height"]
HSUB, WSTRIP, EPS_R = G["h"], G["w"], G["eps_r"]
N_SUB, K_STRIP, J_CENTRE = G["n_sub"], G["k_strip"], G["j_centre"]
NY, NZ, CELL = G["ny"], G["nz"], G["cell"]
Y0, Y1 = W / 2 - WSTRIP / 2, W / 2 + WSTRIP / 2
say("geometry   :", dict(W=W, H=H, h=HSUB, w=WSTRIP, eps_r=EPS_R, ny=NY, nz=NZ,
                         cell=CELL, strip=[Y0, Y1], n_sub=N_SUB,
                         k_strip=K_STRIP, j_centre=J_CENTRE))


def axis(edges, cells):
    """np.linspace chunks concatenated, seam node dropped (s10118_basis.py:78-83)."""
    pieces = [np.linspace(a, b, n + 1) for (a, b), n in zip(edges, cells)]
    out = pieces[0]
    for p in pieces[1:]:
        out = np.concatenate([out, p[1:]])
    return out


#: strip-band resolution only: 12 is the banked mesh (31 x 17 nodes) and
#: ``C1_STRIP_CELLS`` overrides it.  The 9 | 9 air cells and the 8 | 4 | 4
#: substrate do NOT move, so a sweep over this knob is a one-parameter family.
#: ``C1_Y_AIR_CELLS`` (both 9s, kept symmetric) and ``C1_Z_CELLS`` (the
#: 8 | 4 | 4 triple) give the same one-parameter treatment to the two bands
#: that were never varied alone; unset, they reproduce the banked mesh.
_STRIP_CELLS = int(os.environ.get("C1_STRIP_CELLS", "").strip() or 12)
if _STRIP_CELLS < 1:
    raise SystemExit(f"C1_STRIP_CELLS must be >= 1, got {_STRIP_CELLS}")
_Y_AIR = int(os.environ.get("C1_Y_AIR_CELLS", "").strip() or 9)
if _Y_AIR < 1:
    raise SystemExit(f"C1_Y_AIR_CELLS must be >= 1, got {_Y_AIR}")
_Z_RAW = os.environ.get("C1_Z_CELLS", "").strip() or "8,4,4"
_Z = []
for _tok in _Z_RAW.split(","):
    try:
        _v = int(_tok.strip())
    except ValueError:
        raise SystemExit(
            f"C1_Z_CELLS must be three comma-separated ints >= 1, got "
            f"{_Z_RAW!r} (bad value {_tok.strip()!r})")
    if _v < 1:
        raise SystemExit(
            f"C1_Z_CELLS must be three comma-separated ints >= 1, got "
            f"{_Z_RAW!r} (bad value {_v})")
    _Z.append(_v)
if len(_Z) != 3:
    raise SystemExit(
        f"C1_Z_CELLS must be exactly three comma-separated ints, got "
        f"{_Z_RAW!r} ({len(_Z)} values)")
XS = axis([(0.0, Y0), (Y0, Y1), (Y1, W)], [_Y_AIR, _STRIP_CELLS, _Y_AIR])
ZS = axis([(0.0, HSUB), (HSUB, 0.0036), (0.0036, H)], list(_Z))
mesh = m2.structured_mesh(XS, ZS)
_nx, _nz = int(XS.size), int(ZS.size)
say("mesh       :", dict(nodes=mesh.n_nodes, tris=mesh.n_tris,
                         edges=mesh.n_edges, xs=_nx, ys=_nz,
                         strip_cells=_STRIP_CELLS, y_air_cells=_Y_AIR,
                         z_cells=list(_Z)))


def eps_of(p):
    return np.where(p[:, 1] <= HSUB + 1e-12, EPS_R, 1.0)


def ground(p):
    return p[:, 1] == 0.0


def strip(p):
    return (p[:, 1] == HSUB) & (p[:, 0] >= Y0 - 1e-12) & (p[:, 0] <= Y1 + 1e-12)


BOUNDARIES = (ground, strip)

_D = np.load(PLANES)
F0 = float(_D["plane_f"])
K0 = m2.k0_from_freq(F0)
say("bin        :", dict(f0=F0, k0=K0))

edge_pec = m2.pec_edge_mask(mesh, BOUNDARIES)
node_pec = m2.pec_node_mask(mesh, BOUNDARIES)
free_e = np.flatnonzero(~edge_pec)
free_n = np.flatnonzero(~node_pec)
say("dof        :", dict(free_edges=int(free_e.size), free_nodes=int(free_n.size),
                         n_edges=int(mesh.n_edges), n_nodes=int(mesh.n_nodes),
                         mixed_dense_max=int(m2._MIXED_DENSE_MAX)))
if free_e.size > m2._MIXED_DENSE_MAX:
    raise SystemExit(f"{free_e.size} free edges > _MIXED_DENSE_MAX "
                     f"{m2._MIXED_DENSE_MAX}: the dense mixed pencil cannot run")

# node ordering must be j*nx + i for (XS[i], ZS[j]) or every interpolation below
# is silently transposed (.scratch/logs/s10118_basis.py:323-337)
_probe = [(0, 0), (_nx - 1, 0), (5, 3), (_nx - 1, _nz - 1)]
for (i, j) in _probe:
    k = j * _nx + i
    got = np.asarray(mesh.nodes[k], dtype=float)
    want = np.array([XS[i], ZS[j]], dtype=float)
    if not np.array_equal(got, want):
        raise SystemExit(f"node ordering guard FAILED at node[{j}*{_nx}+{i}]: "
                         f"{got.tolist()} != {want.tolist()}")
say("node order : OK (4 probe nodes, layout j*nx+i)")

# ---- banked cache: mesh reproduction check + the identified column ----------
bank_col = -1
bank_status = "absent"
#: the guard below is a MESH-IDENTITY gate: a silently mis-built mesh must not
#: be scored against the banked column.  A strip-band refinement study is a
#: different mesh on purpose, so ``C1_ALLOW_REMESH=1`` downgrades the two
#: refusals to a loud warning and leaves ``bank_col`` unknown (-1), which puts
#: the reproduction check on the best-|corr_e_y| column, where it is EXPECTED to
#: fail.  Default (unset) is unchanged: a wrong mesh is still fatal.
_ALLOW_REMESH = os.environ.get("C1_ALLOW_REMESH", "").strip().lower() in (
    "1", "true", "yes", "on")

if os.path.exists(BANKED):
    _b = np.load(BANKED)
    _bxs = np.asarray(_b["xs"], dtype=float)
    _bzs = np.asarray(_b["zs"], dtype=float)
    _edges_same = int(_b["n_edges"]) == int(mesh.n_edges)
    _axes_same = (_bxs.shape == XS.shape and np.array_equal(_bxs, XS)
                  and _bzs.shape == ZS.shape and np.array_equal(_bzs, ZS))
    if not (_edges_same and _axes_same):
        _msg = (f"banked n_edges {int(_b['n_edges'])} != rebuilt "
                f"{int(mesh.n_edges)}" if not _edges_same else
                "banked xs/zs differ from the rebuilt axes")
        if not _ALLOW_REMESH:
            raise SystemExit(_msg + ": the mesh is not the banked one")
        say("WARNING    :", _msg + ": the mesh is not the banked one -- allowed "
            "by C1_ALLOW_REMESH=1; banked column unknown (-1), so the "
            "reproduction check below runs on the best-|corr_e_y| column and is "
            "EXPECTED to fail")
        bank_status = "not this mesh (C1_ALLOW_REMESH=1)"
    else:
        bank_col = int(_b["col"])
        bank_status = "loaded"
        say("banked     : mesh reproduced (n_edges + xs/zs identical); identified "
            "column =", bank_col,
            dict(beta=float(_b["beta"]), beta_sq=float(_b["beta_sq"]),
                 eps_eff=float(_b["eps_eff"]), residual=float(_b["residual"]),
                 n_dof=int(_b["n_dof"]), n_pec=int(_b["n_pec"])))
else:
    say("banked     : no cache at", BANKED,
        "-> identified column unknown (-1); reproduction check falls back to",
        "the best-|corr_e_y| mode")

# ---------------------------------------------------------------------------
# step 2 -- the mixed solve, with every eigenvector captured
# (.scratch/logs/s10118_basis.py:161-178)
# ---------------------------------------------------------------------------
phase("step2 mixed QZ solve (~111 s)")
captured: dict = {}
_real_eig = m2._dense_eig


def _capture(a, b):
    lam, vecs = _real_eig(a, b)
    captured["lam"] = np.asarray(lam)
    captured["vecs"] = np.asarray(vecs)
    # the dense pencil itself, so the per-column residual below is the solver's
    # own statistic (emfit/mode2d.py:1131-1139) rather than a re-invention
    captured["a"] = np.asarray(a, dtype=float)
    captured["b"] = np.asarray(b, dtype=float)
    return lam, vecs


_t0 = time.time()
m2._dense_eig = _capture
try:
    mode = m2.solve_modes_mixed(mesh, K0, sigma=1.0, eps_r=eps_of,
                               boundaries=BOUNDARIES)
finally:
    m2._dense_eig = _real_eig
say(f"solve_modes_mixed done in {time.time() - _t0:.2f} s",
    dict(chosen=int(mode.chosen), beta=mode.beta, eps_eff=mode.eps_eff,
         residual=mode.residual, n_dof=int(mode.n_dof), n_pec=int(mode.n_pec)))
if "lam" not in captured:
    raise SystemExit("the dense-QZ capture hook never fired: no spectrum to audit")
lam = np.asarray(captured["lam"])
vecs_all = np.asarray(captured["vecs"])
A_dense = np.asarray(captured["a"], dtype=float)
B_dense = np.asarray(captured["b"], dtype=float)
say("spectrum   :", dict(QZ_columns=int(lam.size), pencil=list(A_dense.shape),
                         hook_restored=bool(m2._dense_eig is _real_eig)))

# ---------------------------------------------------------------------------
# step 3 -- blocks (once), LU (once), analytic reference (once)
# (.scratch/logs/s10118_basis.py:218-221, 385-390)
# ---------------------------------------------------------------------------
phase("step3 blocks + LU + analytic reference")
m1, m_eps_m, c, k_zz, m_zz = m2.assemble_mixed(mesh, eps_r=eps_of)
h_blk = (k_zz[free_n][:, free_n] - K0 * K0 * m_zz[free_n][:, free_n]).tocsc()
c_f = c[free_e][:, free_n].tocsc()
lu = splu(h_blk)
say("blocks     :", dict(h=list(h_blk.shape), c_f=list(c_f.shape),
                         nnz_h=int(h_blk.nnz), nnz_c=int(c_f.nnz)))

NYN, NZN = NY + 1, NZ + 1
yn_node = np.arange(NYN) * CELL
zn_node = np.arange(NZN) * CELL
yc_mid = (np.arange(NYN - 1) + 0.5) * CELL
zc_mid = (np.arange(NZN - 1) + 0.5) * CELL
yy, zz = np.meshgrid(yc_mid, zn_node, indexing="ij")        # E_y lattice (ny, nz+1)
iyy, izz = np.meshgrid(yn_node, zc_mid, indexing="ij")      # E_z lattice (ny+1, nz)
_ey_pts = np.stack([yy.ravel(), zz.ravel()], axis=1)
_ez_pts = np.stack([izz.ravel(), iyy.ravel()], axis=1)
#: the SAME E_z lattice in Mode2D.e_at's (x, y) = (XS, ZS) order.  ``_ez_pts`` is
#: (z, y), which is right for the (ZS, XS)-ordered RegularGridInterpolator at
#: :491 and wrong for e_at -- handing it to e_at raises
#: ``ValueError: point ... lies outside the mesh``.  Component-1 sampling uses
#: this array, not ``_ez_pts``.
_ezc_pts = np.stack([iyy.ravel(), izz.ravel()], axis=1)

_t0 = time.time()
prof = microstrip_mode_profile(HSUB, WSTRIP, EPS_R, n_sub=N_SUB)
PANA = M.plane_mode(prof, nyn=NYN, nzn=NZN, k_strip=K_STRIP,
                    iy_strip_centre=J_CENTRE, cell=CELL)
A_ez = np.asarray(PANA.e_z, dtype=float)
A_ey = np.asarray(PANA.e_y, dtype=float)
say(f"analytic   : {time.time() - _t0:.2f} s", PANA.report)
say("analytic   :", dict(e_z=list(A_ez.shape), e_y=list(A_ey.shape),
                         profile_cell=prof.cell, eps_eff=float(prof.eps_eff)))
_want_ez = (NYN, NZN - 1)
_want_ey = (NYN - 1, NZN)
if A_ez.shape != _want_ez or A_ey.shape != _want_ey:
    raise SystemExit(f"analytic shapes e_z {A_ez.shape} / e_y {A_ey.shape} != the "
                     f"plane lattices e_z {_want_ez} / e_y {_want_ey}")

# ez layout guard, independent of the reshape ordering and of any one mode:
# a synthetic field that equals the flat node index must come back out of the
# (ZS, XS)-ordered interpolator at the coordinate of that node
# (.scratch/logs/s10118_basis.py:341-353)
_coord_index = {(float(n[0]), float(n[1])): k for (k, n) in enumerate(mesh.nodes)}
_test_flat = np.arange(mesh.n_nodes, dtype=float)
_test_grid = _test_flat.reshape(_nz, _nx)
_test_itp = RegularGridInterpolator((ZS, XS), _test_grid, bounds_error=False)
for (i, j) in _probe:
    k = _coord_index[(float(XS[i]), float(ZS[j]))]
    got = float(np.asarray(_test_itp([[float(ZS[j]), float(XS[i])]])).ravel()[0])
    if k != j * _nx + i or got != _test_grid[j, i]:
        raise SystemExit(f"ez layout guard FAILED at (i={i}, j={j}): coord index "
                         f"{k} vs {j * _nx + i}, interp {got} vs {_test_grid[j, i]}")
say("ez layout  : OK (4 probe nodes, (nz, nx) grid, (ZS, XS)-ordered interpolator)")

# ---------------------------------------------------------------------------
# step 4 -- one reconstruction per propagating QZ column
# ---------------------------------------------------------------------------
phase("step4 per-column reconstruction + correlation")
real_enough = np.abs(np.imag(lam)) <= 1e-6 * np.maximum(1.0, np.abs(lam))
norm_a = float(np.linalg.norm(A_dense))
norm_b = float(np.linalg.norm(B_dense))

#: (col, beta_sq, beta, eps_eff, corr_e_y, corr_ez_vv,
#:  corr_ez_superseded_longitudinal, residual, shape_ok) -- 9 fields per
#: propagating QZ column; every derived array below indexes this list
rows: list[tuple] = []
#: (e_y energy, e_z_vv energy) per row, in the same order as ``rows``.  R_extracted
#: is a ratio of ONE column's field, so the energies are kept per column and the
#: ratio is taken at step 5 for the banked column only -- not after the loop, where
#: the names still point at whichever column was visited last.
energies: list[tuple[float, float]] = []
n_scanned = 0
_t_loop = time.time()

for j in range(int(lam.size)):
    if not bool(real_enough[j]):
        continue
    bsq = float(np.real(lam[j]))
    if not np.isfinite(bsq) or bsq <= 0.0:
        continue

    x = np.real(vecs_all[:, j])
    nxv = float(np.linalg.norm(x))
    if nxv == 0.0:
        continue
    x = x / nxv

    # the solver's own scale-aware backward error (emfit/mode2d.py:1131-1139)
    resid = float(
        np.linalg.norm(A_dense @ x - bsq * (B_dense @ x)) / (norm_a + abs(bsq) * norm_b)
    )

    beta = float(np.sqrt(bsq))
    e_t = np.zeros(mesh.n_edges)
    e_t[free_e] = x

    # longitudinal block, same LU route as emfit/mode2d.py:1175 -- but SIGNED
    z_free = np.asarray(lu.solve(np.asarray(c_f.T @ x).ravel()), dtype=float).ravel()
    e_z_node = np.zeros(mesh.n_nodes, dtype=float)
    e_z_node[free_n] = beta * z_free

    # Mode2D is a frozen dataclass with no __post_init__ (emfit/mode2d.py:605-666),
    # so it is used here purely as a field carrier for e_at: the audit trail fields
    # (candidates / curl_ratio) are left empty rather than mislabelled, and
    # chosen=j is the raw QZ column index, not an index into the solver's list.
    MODE = m2.Mode2D(
        freq=float(mode.freq), k0=K0, beta=beta, beta_sq=bsq,
        eps_eff=float(bsq / (K0 * K0)), residual=resid,
        candidates=tuple(), curl_ratio=None, chosen=int(j), sigma=1.0,
        n_dof=int(mode.n_dof), n_pec=int(mode.n_pec),
        e_t=e_t, mesh=mesh, e_z=None,
    )

    E_t = MODE.e_at(_ey_pts).reshape(NYN - 1, NZN, 2)
    e_y = E_t[:, :, 0] * CELL          # *CELL as in s10118_basis.py:314; corr is
                                       # invariant to it, kept for faithfulness
    # vertical, SAME COMPONENT: component 1 of the transverse field sampled on the
    # A_ez lattice in e_at's (x, y) order (iyy, izz) -- a vertical reference against
    # the VERTICAL mode component.  This is the primary e_z metric; the block below
    # is retained as the superseded mis-pairing and is still computed.
    E_tz = MODE.e_at(_ezc_pts).reshape(NYN, NZN - 1, 2)
    e_z_vv = E_tz[:, :, 1] * CELL

    ez_grid = np.asarray(e_z_node, dtype=float).reshape(_nz, _nx)
    ez_itp = RegularGridInterpolator((ZS, XS), ez_grid, bounds_error=True)
    e_z_mag = ez_itp(_ez_pts).reshape(NYN, NZN - 1)
    e_z = -e_z_mag                     # s10118_basis.py:369 (E: strip -> ground)

    cy = corr(A_ey, e_y)
    cz_vv = corr(A_ez, e_z_vv)         # PRIMARY: vertical vs vertical
    cz = corr(A_ez, e_z)               # SUPERSEDED: A_ez (vertical) against the
                                       # LONGITUDINAL field beta*z_free -- a
                                       # component mis-pairing.  Kept and still
                                       # computed so the old numbers remain
                                       # reproducible; it is not a shape test.
    shape_ok = bool(e_y.shape == A_ey.shape and e_z_vv.shape == A_ez.shape
                    and e_z.shape == A_ez.shape)
    rows.append((int(j), bsq, beta, float(bsq / (K0 * K0)), cy, cz_vv, cz, resid,
                 shape_ok))
    energies.append((float(np.sum(e_y ** 2)), float(np.sum(e_z_vv ** 2))))

    n_scanned += 1
    if n_scanned % 50 == 0:
        phase(f"step4 per-column ({n_scanned} done, {time.time() - _t_loop:.1f} s)")
        say(f"PROGRESS [columns] {time.time() - T0:.1f} s  col={j}/{int(lam.size)}  "
            f"kept={n_scanned}  |corr_e_y|={abs(cy):.6f}  "
            f"|corr_ez_vv|={abs(cz_vv):.6f}  |corr_ez_superseded|={abs(cz):.6f}")

say(f"loop done in {time.time() - _t_loop:.2f} s for {n_scanned} propagating columns")

# ---------------------------------------------------------------------------
# step 5 -- persist: full table + npz
# ---------------------------------------------------------------------------
phase("step5 write outputs")
abs_cy = np.array([abs(r[4]) for r in rows], dtype=float)
abs_cz_vv = np.array([abs(r[5]) for r in rows], dtype=float)
abs_cz_superseded = np.array([abs(r[6]) for r in rows], dtype=float)
#: the corrected criterion, on the same-component vertical metric
ok_arr = np.array([bool(r[8]) and np.isfinite(r[4]) and np.isfinite(r[5])
                   and abs(r[4]) >= CORR_EY_MIN and abs(r[5]) >= CORR_EZ_VV_MIN
                   for r in rows], dtype=bool)
#: the legacy criterion, unchanged, on the superseded longitudinal number
ok_arr_legacy = np.array([bool(r[8]) and np.isfinite(r[4]) and np.isfinite(r[6])
                          and abs(r[4]) >= CORR_EY_MIN and abs(r[6]) <= CORR_EZ_MAX
                          for r in rows], dtype=bool)
order = np.argsort(-abs_cy, kind="stable")

# ---- which column the banked figures belong to ------------------------------
#: ``R_extracted`` (and every banked corr figure read off a row) belongs to ONE
#: QZ column.  This resolution names it, and nothing here invents a selection
#: rule: the column is the one the SOLVER selected, recovered by matching the
#: eigenvalue it reports (``mode.beta_sq``) back to a row.  ``mode.chosen`` is NOT
#: used for this -- it is an index into mode2d's re-ordered candidate list
#: (emfit/mode2d.py:1150-1167), not a QZ column index, so using it as one would be
#: the same class of mistake this block exists to fix.  Fallbacks, in order: the
#: single column that passes the criterion, then the best-|corr_e_y| column; each
#: records itself in ``banked_src`` and every caller prints it.
banked_idx = -1
chosen_col = -1
banked_src = "none (no propagating column)"
R_by_col = (np.array([ez / ey for (ey, ez) in energies], dtype=float)
            if rows else np.zeros(0, dtype=float))
if rows:
    _sel_bsq = float(mode.beta_sq)
    _hits = [i for i, r in enumerate(rows) if float(r[1]) == _sel_bsq]
    if len(_hits) == 1:
        banked_idx = _hits[0]
        chosen_col = int(rows[banked_idx][0])
        banked_src = "solver selection (matched by mode.beta_sq)"
    if banked_idx < 0:
        _hits = [i for i, flag in enumerate(ok_arr) if bool(flag)]
        if len(_hits) == 1:
            banked_idx = _hits[0]
            banked_src = ("unique criterion-passing column (solver eigenvalue not "
                          "matched exactly)")
    if banked_idx < 0:
        banked_idx = int(order[0])
        banked_src = ("best-|corr_e_y| column (no solver eigenvalue match, no "
                      "unique criterion pass)")
banked_col = int(rows[banked_idx][0]) if banked_idx >= 0 else -1
R_extracted = float(R_by_col[banked_idx]) if banked_idx >= 0 else float("nan")

_hdr = (
    "# c1_audit.py -- every propagating eigenvector of the mixed 2-D pencil\n"
    "# vs the analytic plane basis (microstrip_mode_profile -> plane_mode)\n"
    "#\n"
    f"# repo                 : {REPO}\n"
    f"# mesh                 : {_nx} x {_nz} nodes, {int(mesh.n_edges)} edges, "
    f"{int(free_e.size)} free after PEC\n"
    f"# QZ columns           : {int(lam.size)} (dense QZ, every eigenvector kept)\n"
    f"# propagating columns  : {n_scanned} (real lambda, beta^2 > 0)\n"
    f"# f0 / k0              : {F0:.12g} Hz / {K0:.12g} rad/m\n"
    f"# criteria             : ok = |corr_e_y| >= {CORR_EY_MIN:g} and "
    f"|corr_ez_vv| >= {CORR_EZ_VV_MIN:g} and shapes match  (the |corr_ez_vv| bar "
    "is derived -- docs/design/corr_ez_vv_threshold.md)\n"
    "#                        the npz keys shape_pair_ok / shape_only_ok are the "
    "GEOMETRY flag alone\n"
    "#                        (shapes line up, no correlation bar) -- they are not "
    "this column and\n"
    "#                        never were; the column below is ok (the npz's ok)\n"
    f"# criteria SUPERSEDED  : shape_pair_ok_legacy = |corr_e_y| >= {CORR_EY_MIN:g} "
    f"and |corr_ez| <= {CORR_EZ_MAX:g} on corr_ez_superseded_longitudinal\n"
    "# criterion uses |corr| because an eigenvector's sign is arbitrary; the\n"
    "# signed values are printed too, so nothing is hidden.\n"
    "# corr_ez_vv                       = vertical reference vs VERTICAL mode "
    "component (primary)\n"
    "# corr_ez_superseded_longitudinal  = vertical reference vs the LONGITUDINAL "
    "field beta*z_free (the mis-pairing, retained)\n"
    f"# banked anchors       : corr_e_y {ANCHOR_CORR_EY!r} / corr_e_z {ANCHOR_CORR_EZ!r}"
    "  (both belong to the superseded pairing)\n"
    f"# banked identified col: {bank_col} ({bank_status})\n"
    "#\n"
    "  rank     col        beta_sq         beta    eps_eff     corr_e_y   "
    "corr_ez_vv  |corr_e_y|  |corr_ez_vv|     ok           "
    "corr_ez_superseded_longitudinal  |corr_ez_superseded|  shape_pair_ok_legacy\n"
)

_lines = [_hdr]
for rank, idx in enumerate(order, start=1):
    j, bsq, beta, ee, cy, cz_vv, cz_sup, resid, shape_ok = rows[idx]
    _lines.append(
        f"{rank:6d} {j:7d} {bsq:15.7e} {beta:12.5e} {ee:10.6f} {cy:+12.7f} "
        f"{cz_vv:+12.7f} {abs(cy):11.7f} {abs(cz_vv):12.7f}  "
        f"{str(bool(ok_arr[idx])):>5s} {cz_sup:+32.7f} {abs(cz_sup):20.7f}  "
        f"{str(bool(ok_arr_legacy[idx])):>5s}\n"
    )
with open(TABLE_PATH, "w", encoding="utf-8") as fh:
    fh.writelines(_lines)
say("wrote", TABLE_PATH)

np.savez(
    NPZ_PATH,
    lam=lam,
    vecs_real=np.real(vecs_all).astype(np.float64),
    j=np.array([r[0] for r in rows], dtype=np.int64),
    beta_sq=np.array([r[1] for r in rows], dtype=float),
    beta=np.array([r[2] for r in rows], dtype=float),
    eps_eff=np.array([r[3] for r in rows], dtype=float),
    corr_ey=np.array([r[4] for r in rows], dtype=float),
    corr_ez_vv=np.array([r[5] for r in rows], dtype=float),
    corr_ez_superseded_longitudinal=np.array([r[6] for r in rows], dtype=float),
    # compatibility alias, NOT for new work: mode_plot.py:278-291 reads "corr_ez"
    # and compares it with the banked LONGITUDINAL numbers (+0.119160432391342 /
    # +0.147291446944630).  Same value as corr_ez_superseded_longitudinal.
    corr_ez=np.array([r[6] for r in rows], dtype=float),
    residual=np.array([r[7] for r in rows], dtype=float),
    # TWO DIFFERENT FLAGS, and their names now say which is which:
    #   ok            = the criterion -- shapes match AND |corr_e_y| >= the bar
    #                   AND |corr_ez_vv| >= its bar.  This is the table's "ok"
    #                   column and what the VERDICT counts.
    #   shape_pair_ok = GEOMETRY ONLY -- the three field shapes line up, no
    #                   correlation bar applied.  The banked key name is kept for
    #                   readers of existing files, and aliased as shape_only_ok
    #                   because "pair_ok" reads like a verdict and it is not one.
    ok=ok_arr,
    shape_pair_ok=np.array([r[8] for r in rows], dtype=bool),
    shape_only_ok=np.array([r[8] for r in rows], dtype=bool),
    shape_pair_ok_legacy=ok_arr_legacy,
    xs=XS, zs=ZS, k0=K0, f0=F0,
    n_edges=int(mesh.n_edges), n_nodes=int(mesh.n_nodes),
    free_e=free_e, free_n=free_n,
    # bank_col used to carry the CACHE's identified column -- a property of the
    # PMC mesh, not of this QZ sweep.  In the PEC box it was 738, a column that
    # is not even propagating there, and the R_extracted written beside it came
    # from a different column entirely.  bank_col now names the column the
    # R_extracted / banked figures in THIS file belong to: the column the solver
    # itself resolved (-1 when there is none).  The old cache value is still
    # recorded, under identified_col.
    bank_col=int(banked_col),
    identified_col=int(bank_col),
    chosen_col=int(chosen_col),
    n_eligible=int(len(rows)),
    eligible_cols=np.array([r[0] for r in rows], dtype=np.int64),
    # per-ELIGIBLE-column diagnostics, same order as j / beta_sq:
    #   R_by_col                     sum(e_z_vv^2)/sum(e_y^2) of that column
    #   corr_ey_by_col, corr_ez_vv_by_col   the two correlation aliases
    R_by_col=R_by_col,
    corr_ey_by_col=np.array([r[4] for r in rows], dtype=float),
    corr_ez_vv_by_col=np.array([r[5] for r in rows], dtype=float),
    # the full QZ spectrum, for diagnostics.  It records the null-space risk:
    # the non-physical branch sits near Re(lambda) = -6.2e8..-6.9e8 while the
    # physical band is k0^2 = 2.694e4 (eps_r k0^2 = 1.185e5), so eligibility is
    # a single scalar filter (finite, real, > 0, residual < tol) with NO band --
    # deliberately not added here.
    beta_sq_all=lam,
    A_ey=A_ey, A_ez=A_ez,
    # R_extracted: vertical / in-plane energy ratio of the EXTRACTED field,
    # sum(e_z_vv^2) / sum(e_y^2) -- the T4_amp numerator.  Its analytic
    # counterpart, read off the references written above, is
    # sum(A_ez^2)/sum(A_ey^2) = 2.810102138752.  The numerator is the SAME
    # vertical array the primary metric corr_ez_vv is formed from and the
    # denominator the SAME in-plane array corr_ey is formed from; both are
    # scaled by CELL and the ratio is scale invariant.
    # WHICH COLUMN: the one named by bank_col, i.e. the column the solver
    # resolved (banked_src says how).  NOT the last column the scan happened to
    # visit.  For c1_spectrum.npz both are 738 and the value is unchanged:
    # 4.0489791163982565 (exact anchor, ANCHOR_R_EXTRACTED).  For
    # pecbox_spectrum.npz the old last-visited form banked the failing witness
    # 704 and wrote 70.63501855512833; the solver resolves 699 and this file now
    # holds 4.163656524825077.  Every eligible column's ratio is in R_by_col;
    # whether the selected column passed the criterion is R_extracted_ok.
    R_extracted=R_extracted,
    R_extracted_ok=bool(ok_arr[banked_idx]) if banked_idx >= 0 else False,
    criterion=np.array([CORR_EY_MIN, CORR_EZ_MAX], dtype=float),
    criterion_ez_vv=np.array([CORR_EY_MIN, CORR_EZ_VV_MIN], dtype=float),
)
say("wrote", NPZ_PATH)

# the same table, on stdout (ranked by |corr_e_y|)
say("")
say("=" * 118)
say("  rank     col        beta_sq         beta    eps_eff     corr_e_y   "
    "corr_ez_vv  |corr_e_y|  |corr_ez_vv|     ok           "
    "corr_ez_superseded_longitudinal  |corr_ez_superseded|  shape_pair_ok_legacy")
say("-" * 118)
for rank, idx in enumerate(order, start=1):
    j, bsq, beta, ee, cy, cz_vv, cz_sup, resid, shape_ok = rows[idx]
    say(f"{rank:6d} {j:7d} {bsq:15.7e} {beta:12.5e} {ee:10.6f} {cy:+12.7f} "
        f"{cz_vv:+12.7f} {abs(cy):11.7f} {abs(cz_vv):12.7f}  "
        f"{str(bool(ok_arr[idx])):>5s} {cz_sup:+32.7f} {abs(cz_sup):20.7f}  "
        f"{str(bool(ok_arr_legacy[idx])):>5s}")
say("=" * 118)

# ---------------------------------------------------------------------------
# step 6 -- verdict + reproduction check
# ---------------------------------------------------------------------------
phase("step6 verdict")
n_kept = len(rows)
n_ok = int(ok_arr.sum())
ok_cols = [int(r[0]) for r, f in zip(rows, ok_arr) if f]
n_ok_legacy = int(ok_arr_legacy.sum())
ok_cols_legacy = [int(r[0]) for r, f in zip(rows, ok_arr_legacy) if f]
best_idx = int(order[0]) if n_kept else -1

say("")
say("-" * 100)
say("VERDICT")
say(f"  propagating modes considered (real lambda, beta^2 > 0) : {n_kept}")
say(f"  ok (criterion: |corr_e_y| >= {CORR_EY_MIN:g} and |corr_ez_vv| >= "
    f"{CORR_EZ_VV_MIN:g}, shapes match) : {n_ok}")
say(f"  their QZ columns                                      : {ok_cols}")
say(f"  shape_pair_ok_legacy SUPERSEDED (|corr_e_y| >= {CORR_EY_MIN:g} and "
    f"|corr_ez| <= {CORR_EZ_MAX:g} on corr_ez_superseded_longitudinal) : "
    f"{n_ok_legacy}")
say(f"  their QZ columns                                      : {ok_cols_legacy}")
if n_kept:
    j, bsq, beta, ee, cy, cz_vv, cz_sup, resid, shape_ok = rows[best_idx]
    say(f"  best |corr_e_y| mode                                  : col {j}"
        f"  |corr_e_y| = {abs(cy):.15f}  |corr_ez_vv| = {abs(cz_vv):.15f}"
        f"  |corr_ez_superseded| = {abs(cz_sup):.15f}"
        f"  beta^2 = {bsq:.12g}  eps_eff = {ee:.9f}  residual = {resid:.3e}"
        f"  ok = {bool(ok_arr[best_idx])}"
        f"  shape_pair_ok_legacy = {bool(ok_arr_legacy[best_idx])}")
    say(f"  resolved propagating column                           : {banked_col}"
        f"  [{banked_src}]")
    if bank_col >= 0:
        same = (int(j) == int(bank_col))
        say(f"  banked / identified column                            : {bank_col}")
        say(f"  best-|corr_e_y| column == banked column               : "
            f"{'YES' if same else 'NO'}")
    else:
        say("  banked / identified column                            : unknown "
            "(no cache) -- comparison not possible")
else:
    say("  no propagating mode: nothing to reproduce")

# reproduction check on the column the SOLVER resolved.  This used to hunt the
# table for the CACHE's column -- which in the PEC box silently moved the check
# onto the same last-visited column that R_extracted was wrongly taking its
# value from, so both the gate and the number agreed with each other and with
# nothing else.
_target = banked_idx if banked_idx >= 0 else None
_target_label = f"column {banked_col} [{banked_src}]" if _target is not None else "none"

_repro_ok = False        # gate result, reported in the DONE line below
if _target is not None:
    j, bsq, beta, ee, cy, cz_vv, cz_sup, resid, shape_ok = rows[_target]
    say("")
    say(f"REPRODUCTION CHECK ({_target_label})")
    say(f"  |corr_e_y| = {abs(cy):.17f}   anchor {ANCHOR_CORR_EY!r}   "
        f"delta = {abs(cy) - ANCHOR_CORR_EY:+.3e}")
    say(f"  |corr_ez_superseded| = {abs(cz_sup):.17f}   anchor {ANCHOR_CORR_EZ!r}   "
        f"delta = {abs(cz_sup) - ANCHOR_CORR_EZ:+.3e}")
    say(f"  |corr_ez_vv| = {abs(cz_vv):.17f}   (corrected same-component "
        f"pairing; the banked anchor is the SUPERSEDED value, so no gate here)")
    say(f"  signed     = ({cy:+.15f}, {cz_sup:+.15f}, {cz_vv:+.15f})  "
        f"(e_y, e_z_superseded, e_z_vv; signs are LAPACK-arbitrary; "
        f"the anchors are magnitudes)")
    # a delta that nothing checks is how drift survives: gate both anchors.
    # This is LOUD but not fatal -- the spectrum bank and the table above are the
    # primary product and must still reach disk even when the gate fails.
    _repro = []
    for _tag, _meas, _bank in (("REPRO e_y", abs(float(cy)), ANCHOR_CORR_EY),
                               ("REPRO e_z", abs(float(cz_sup)), ANCHOR_CORR_EZ)):
        _rel = abs(_meas - _bank) / max(abs(_bank), 1e-300)
        _pass = bool(np.isfinite(_rel) and _rel <= REPRO_RTOL)
        _repro.append(_pass)
        say(f"  {_tag}  banked = {_bank!r}  measured = {_meas:.17g}  "
            f"rel_delta = {_rel:.3e}  tol = {REPRO_RTOL:g} (relative)  "
            f"{'PASS' if _pass else 'FAIL'}")
    # R_extracted: gated EXACTLY, and only where an anchor exists -- the case where
    # the resolved column IS the cache's identified column (c1_spectrum.npz).  There
    # the banked value is a bit-for-bit property of the banked npz, so the
    # tolerance is 0 and any movement at all fails.
    if bank_col >= 0 and banked_col == int(bank_col):
        _pass = bool(R_extracted == ANCHOR_R_EXTRACTED)
        _repro.append(_pass)
        say(f"  REPRO R  banked = {ANCHOR_R_EXTRACTED!r}  "
            f"measured = {R_extracted!r}  exact_match = {_pass}  tol = 0  "
            f"{'PASS' if _pass else 'FAIL'}")
    else:
        say(f"  REPRO R  R_extracted = {R_extracted!r}  (no anchor: resolved column "
            f"{banked_col} is not the cache's identified column {bank_col}; "
            f"pecbox_spectrum.npz is expected to read 4.163656524825077 here)")
    _repro_ok = all(_repro)
    say(f"  REPRO overall: {'PASS' if _repro_ok else 'FAIL'}")
else:
    say("")
    say("REPRODUCTION CHECK: skipped (no propagating mode / no reference column)")
    say("  REPRO overall: FAIL (skipped: nothing was reproduced)")

say("-" * 100)
say(f"DONE c1_audit.py elapsed={time.time() - T0:.1f}s modes_kept={n_kept} "
    f"ok={n_ok} shape_pair_ok_legacy={n_ok_legacy} "
    f"best_col={int(rows[best_idx][0]) if n_kept else -1} "
    f"best_abs_corr_ey={abs_cy[best_idx] if n_kept else float('nan'):.15f} "
    f"best_abs_corr_ez_vv={abs_cz_vv[best_idx] if n_kept else float('nan'):.15f} "
    f"cache_col={bank_col} bank_col={banked_col} banked_src={banked_src!r} "
    f"repro={'PASS' if _repro_ok else 'FAIL'} "
    f"repro_rtol={REPRO_RTOL:g} npz={NPZ_PATH} table={TABLE_PATH}")
