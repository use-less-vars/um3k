"""Tests for :mod:`emfit.mode2d`, the 2-D cross-section eigenmode solver.

Provenance: **none of these tests has been executed.**  They were written by
reading ``emfit/mode2d.py`` and the recorded anchor run in ``evidence/logs/pecbox.log``, with
no interpreter available, so every expectation below is traced to a line of
code or to a logged measurement rather than to a run of this file.  The one
recorded prototype of the anchor is ``tools/host/c1-audit/pecbox_variant.py
--self-test-anchor`` (its ``_self_test_anchor`` at ``pecbox_variant.py:544-603``
and the run it left in ``evidence/logs/pecbox.log:163-174``); that script is *not* imported
here, because it is a driver, not a module -- importing it would execute its
whole audit report (top-level ``say`` calls from ``pecbox_variant.py:528`` on).

Three numbers carry the weight:

* ``0.438278`` -- the analytic ``1 - (c/2W / f_0)^2`` of TE10 in a 20 mm vacuum
  PEC guide at 10 GHz, formed the way the recorded anchor forms it
  (``pecbox_variant.py:587``);
* ``0.438322827`` -- what the same 30 x 16 mesh actually produced, one value out
  of 1394 QZ columns (``evidence/logs/pecbox.log:167``, ``evidence/logs/pecbox.log:170-171``);
* ``0.02`` -- the 2 per cent gate the recorded anchor compares them with
  (``SELF_TEST_BETA_TOL``, ``pecbox_variant.py:102``), which is ~200x the
  recorded 1.022e-4 deviation (``evidence/logs/pecbox.log:172``).  It is a regression gate,
  not a precision claim.

The API is two solvers and one shared result type: :func:`emfit.mode2d.solve_modes`
(sparse, ``eigsh`` shift-invert, ``emfit/mode2d.py:795-804``) and
:func:`emfit.mode2d.solve_modes_mixed` (dense QZ, ``emfit/mode2d.py:1674``),
both returning a :class:`~emfit.mode2d.Mode2D` whose ``candidates`` is the
*complete* spectrum as ``(beta_sq, eps_eff)`` pairs (``emfit/mode2d.py:1197``).
``eps_eff`` is exactly ``beta_sq / k0^2`` (``emfit/mode2d.py:1195``), which is
the quotient every test here asserts on.  The boundary condition is a caller
argument, not a mesh property: a tuple of *node* predicates selects PEC
(``emfit/mode2d.py:539-568``) and an empty tuple is the natural (PMC) condition,
because the geometry enters only through those predicates
(``emfit/mode2d.py:554-555``).
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit import mode2d as m2
from emfit.materials import C0

#: The vacuum box of the recorded anchor -- ``pecbox_variant.py:99-101``.  ``W_BOX``
#: is the broad wall (the half-sine of TE10 lives on it), ``H_BOX`` the narrow one.
#: The tests restate these three from the record rather than from a package
#: constant, because no package constant exists: the anchor is a docstring claim
#: (``emfit/mode2d.py:1020-1022``) with only that script as its executable form.
W_BOX = 0.020             # m, pecbox_variant.py:99 (W_BOX)
H_BOX = 0.0076            # m, pecbox_variant.py:100 (H_BOX)
F_TEST = 10.0e9           # Hz, pecbox_variant.py:101 (F_SELF_TEST)

#: Node counts, not cell counts: 31 x 17 nodes are 30 x 16 cells
#: (``emfit/mode2d.py:287-292``), i.e. cells of 0.667 x 0.475 mm at
#: ``lambda_0 = 29.98 mm``.  Same rows as ``pecbox_variant.py:549-550``.
N_X = 31                  # node columns, pecbox_variant.py:549
N_Y = 17                  # node rows, pecbox_variant.py:550

#: The gate, and the geometry slack the wall predicates use.
BETA_TOL = 0.02           # relative, pecbox_variant.py:102 (SELF_TEST_BETA_TOL)
WALL_TOL = 1e-12          # m, pecbox_variant.py:161 (_WALL_TOL)

#: ``beta^2/k0^2`` of TE10 in a vacuum PEC guide: ``1 - (f_c/f_0)^2`` with
#: ``f_c = C0/(2*W_BOX)`` -- the arithmetic of ``pecbox_variant.py:587``.
#: Evaluates to 0.438278, the value ``evidence/logs/pecbox.log:169`` prints.  The ``1.0``,
#: ``2.0`` and the square are that line's; nothing here is an independent figure.
TE10_BETA_OVER_K0_SQ = 1.0 - (C0 / (2.0 * W_BOX) / F_TEST) ** 2

#: Where the sparse path is asked to look, as a fraction of ``k0^2``.  The
#: eigenvalue it shifts towards is TE10's, 0.4383 ``k0^2`` (``evidence/logs/pecbox.log:171``);
#: 0.40 sits off it because a shift that lands on an eigenvalue makes the
#: factorisation inside ``eigsh`` singular (``emfit/mode2d.py:841-844``) and
#: near it so that the requested modes bracket it (``emfit/mode2d.py:868``).
SIGMA_FRACTION = 0.40

#: How many modes to ask ``eigsh`` for, against the default of 4
#: (``emfit/mode2d.py:803``): six widen the window around the shift without
#: paying for a second factorisation.
SPARSE_MODES = 6


# ---------------------------------------------------------------------------
# the box, and the two things a caller has to build for it
# ---------------------------------------------------------------------------
def _vacuum_box():
    """The recorded anchor's triangulation: 30 x 16 cells over ``W_BOX x H_BOX``.

    Built exactly as ``pecbox_variant.py:549-551`` builds it, so a regression
    here is comparable with the numbers logged there.
    """
    return m2.structured_mesh(
        np.linspace(0.0, W_BOX, N_X),
        np.linspace(0.0, H_BOX, N_Y),
    )


def _pec_walls():
    """Four PEC surfaces, one per wall: the predicates of ``pecbox_variant.py:552-557``.

    ``boundaries`` is a sequence of *node* predicates (``emfit/mode2d.py:542-545``)
    and an edge is PEC only when **both** ends lie on the **same** predicate
    (``emfit/mode2d.py:544-545``), which is what keeps an edge joining two
    different walls free.  An empty tuple instead is the natural (PMC) condition,
    since nothing here knows about walls except through these predicates
    (``emfit/mode2d.py:554-555``).
    """
    return (
        lambda p: np.abs(p[:, 0] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 0] - W_BOX) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - H_BOX) <= WALL_TOL,
    )


def _propagating(res):
    """``beta^2/k0^2`` of every candidate with a finite positive ``beta^2``.

    ``candidates`` is the whole spectrum as ``(beta_sq, eps_eff)`` pairs
    (``emfit/mode2d.py:1197``); a complex eigenvalue carries ``NaN`` on both
    sides of the pair (``emfit/mode2d.py:1147``), so ``isfinite`` plus ``> 0``
    is the same screen the recorded anchor applies to the raw QZ output
    (``pecbox_variant.py:583-586``).  Nothing in the API marks a candidate as
    physical, so this is a *count of eigenvalues*, not a count of modes.
    """
    return [e for (b, e) in res.candidates if np.isfinite(b) and b > 0.0]


def _closest(values, target: float) -> float:
    """The candidate nearest ``target``, or a failure naming the empty set."""
    arr = np.asarray(values, dtype=float)
    assert arr.size > 0, (
        f"no candidate has a finite positive beta^2/k0^2 (target {target:.6f}); "
        "the spectrum came back with nothing above cutoff"
    )
    return float(arr[int(np.argmin(np.abs(arr - target)))])


# ---------------------------------------------------------------------------
# the anchor: TE10 in a plain vacuum PEC box
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_anchor_te10() -> None:
    """TE10 in a 20 x 7.6 mm vacuum PEC box at 10 GHz: ``beta^2/k0^2 = 0.4383``.

    Only one mode propagates in this box at 10 GHz, which is why one number is
    the whole test: ``f_c(TE10) = C0/(2*W_BOX) = 7.4948 GHz``, the next is TE20
    at twice that, 14.99 GHz, and the height puts TE01 at ``C0/(2*H_BOX) =
    19.72 GHz`` -- ``H_BOX < W_BOX/2`` keeps the narrow dimension out of the
    way.  The 30 x 16 mesh puts 30 cells across the broad wall, so the half-sine
    of TE10 is resolved by 30 cells of ``W_BOX/30 = 0.667 mm`` at
    ``lambda_0 = C0/F_TEST = 29.98 mm``; that is the resolution behind the
    recorded 1.022e-4 agreement (``evidence/logs/pecbox.log:172``) and the reason a 2 per cent
    gate is a regression gate rather than a wish.

    The assertion is on the *spectrum*, not on ``res.eps_eff``: the recorded run
    found exactly one positive-real eigenvalue in this box (``evidence/logs/pecbox.log:170``,
    the single value ``evidence/logs/pecbox.log:171``), so on this mesh "nearest candidate"
    and "the mode the solver chose" are the same mode -- but the choice also
    requires a pencil residual below ``_MIXED_RESIDUAL_TOL``
    (``emfit/mode2d.py:150``, ``emfit/mode2d.py:1156-1160``), which nothing here
    has measured.  The failure this gate is built to catch is a missing ``k_q``:
    it leaves the quotient at 1.0 instead of 0.4383 (``emfit/mode2d.py:1022``).
    """
    mesh = _vacuum_box()
    k0 = m2.k0_from_freq(F_TEST)
    res = m2.solve_modes_mixed(mesh, k0, eps_r=1.0, boundaries=_pec_walls())

    got = _closest(_propagating(res), TE10_BETA_OVER_K0_SQ)
    rel = abs(got - TE10_BETA_OVER_K0_SQ) / TE10_BETA_OVER_K0_SQ
    assert rel <= BETA_TOL, (
        f"TE10 in the vacuum PEC box: beta^2/k0^2 = {got:.9f}, analytic "
        f"{TE10_BETA_OVER_K0_SQ:.6f}, relative {rel:.3e} > {BETA_TOL:g} "
        f"(recorded: 0.438322827, rel 1.022e-04, evidence/logs/pecbox.log:171-172); "
        f"{len(_propagating(res))} positive-real candidates, "
        f"{len(res.candidates)} QZ columns, {res.n_pec} PEC edges"
    )


# ---------------------------------------------------------------------------
# the two paths on one mesh
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_sparse_dense_agree() -> None:
    """The sparse and the dense path put TE10 in the same place.

    They solve different pencils.  ``solve_modes`` hands ``eigsh`` the transverse
    pencil ``C = k0^2 M_eps - K_q`` against ``B = M_mu`` (``emfit/mode2d.py:860-868``);
    ``solve_modes_mixed`` forms the dense QZ pencil ``A = k0^2 m_eps - k_q``
    against ``B = m1 - c D c^T`` (``emfit/mode2d.py:1115-1120``), i.e. with the
    longitudinal field already eliminated into ``B``.  Agreement is therefore a
    statement that one mode comes out of two formulations of the same problem --
    not that two code paths do identical arithmetic.

    Tolerance: 2 per cent on the shared quotient, the anchor's own gate
    (``pecbox_variant.py:102``).  The dense path is recorded 1.022e-4 from the
    analytic value (``evidence/logs/pecbox.log:172``); the nearest *different* mode is TE20 at
    ``1 - (14.99/10)^2 = -1.247``, a whole unit away in the same quotient.  So
    2 per cent tolerates a formulation's dispersion error by a factor of ~200
    over the recorded deviation while still separating "same mode" from
    "different mode" by a factor of ~60.
    """
    mesh = _vacuum_box()
    k0 = m2.k0_from_freq(F_TEST)

    dense = m2.solve_modes_mixed(mesh, k0, eps_r=1.0, boundaries=_pec_walls())
    sparse = m2.solve_modes(
        mesh,
        k0,
        SIGMA_FRACTION * k0 * k0,
        eps_r=1.0,
        boundaries=_pec_walls(),
        k=SPARSE_MODES,
    )

    dense_ee = _closest(_propagating(dense), TE10_BETA_OVER_K0_SQ)
    sparse_ee = _closest(_propagating(sparse), TE10_BETA_OVER_K0_SQ)
    rel = abs(dense_ee - sparse_ee) / TE10_BETA_OVER_K0_SQ
    assert rel <= BETA_TOL, (
        f"sparse and dense disagree on TE10: dense beta^2/k0^2 = {dense_ee:.9f} "
        f"({len(dense.candidates)} QZ columns), sparse {sparse_ee:.9f} "
        f"({len(sparse.candidates)} ARPACK columns around sigma = "
        f"{SIGMA_FRACTION:g} k0^2), relative {rel:.3e} > {BETA_TOL:g}"
    )


# ---------------------------------------------------------------------------
# closed against open: how many eigenvalues are above cutoff
# ---------------------------------------------------------------------------
@pytest.mark.xfail(
    reason=(
        "expected the closed (PEC) box to support one propagating mode at 10 GHz "
        "and the open (PMC) box two. The closed half is recorded on this very "
        "mesh and I expect it to hold (evidence/logs/pecbox.log:170, 'N_PROPAGATING = 1', the "
        "single value at evidence/logs/pecbox.log:171). The open half I expect to come out as "
        "1, not 2. Two reasons. (a) The mixed reduction eliminates the "
        "longitudinal field into B = m1 - c D c^T (emfit/mode2d.py:1105-1116, "
        "with h = k_zz - k0^2 m_zz factored once at emfit/mode2d.py:1107), so a "
        "PMC light-line mode -- whose transverse field is identically zero and "
        "whose only component is a constant e_z -- has no eigenvector left in "
        "the reduced pencil at all. (b) With PMC walls H_z, being tangential to "
        "all four walls, must vanish on both, which forces the TE family to a "
        "quarter-wave dependence on both (k_x a = k_y b = pi/2 for the lowest), "
        "putting its lowest member at c/2*sqrt((pi/2a)^2+(pi/2b)^2) = 10.55 GHz, "
        "above this test's 10 GHz; the TM family instead obeys k_x = m pi/a the "
        "way a PEC wall does, so it contributes one TM10 at the same 7.4948 GHz "
        "as the PEC TE10. Either way the count is not the 2 I expected. The "
        "counting rule is also unfiltered: 'propagating' here means finite "
        "beta_sq > 0 over the complete spectrum the dense path returns "
        "(emfit/mode2d.py:966, emfit/mode2d.py:1197), and nothing in the API "
        "says which candidates are physical, so a count is a count of "
        "eigenvalues. Nothing here has been run: this is what the code and the "
        "mode arithmetic say, not a measurement."
    ),
    strict=False,
)
@pytest.mark.slow
def test_closed_vs_open_mode_count() -> None:
    """A closed PEC box supports one propagating mode here, an open PMC box two.

    The two boxes differ by one argument: ``boundaries=_pec_walls()`` eliminates
    every edge whose two ends lie on one wall (``emfit/mode2d.py:544-545``),
    ``boundaries=()`` eliminates nothing and leaves the natural PMC condition
    (``emfit/mode2d.py:554-555``).  Both halves are asserted before anything is
    counted, so a boundary argument that did nothing cannot be mistaken for a
    mode count.

    Expected and unverified in equal measure -- see the ``xfail`` reason for what
    I expect to happen instead, and why the number that comes back is a count of
    eigenvalues rather than of modes.
    """
    mesh = _vacuum_box()
    k0 = m2.k0_from_freq(F_TEST)

    closed = m2.solve_modes_mixed(mesh, k0, eps_r=1.0, boundaries=_pec_walls())
    open_ = m2.solve_modes_mixed(mesh, k0, eps_r=1.0, boundaries=())

    assert closed.n_pec > 0, (
        f"the closed box eliminated no PEC edges (n_pec = {closed.n_pec}); the "
        "wall predicates did nothing and the count below would be the open box's"
    )
    assert open_.n_pec == 0, (
        f"the open box eliminated {open_.n_pec} PEC edges; an empty boundaries "
        "tuple must leave every edge free (emfit/mode2d.py:557-560)"
    )

    n_closed = len(_propagating(closed))
    n_open = len(_propagating(open_))
    assert n_closed == 1, (
        f"closed (PEC) box: {n_closed} candidates with beta^2 > 0, expected 1 "
        f"(TE10 only; TE20 at 14.99 GHz, TE01 at 19.72 GHz); "
        f"beta^2/k0^2 = {_propagating(closed)}"
    )
    assert n_open == 2, (
        f"open (PMC) box: {n_open} candidates with beta^2 > 0, expected 2; "
        f"beta^2/k0^2 = {_propagating(open_)}"
    )
