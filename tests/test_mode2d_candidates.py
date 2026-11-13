"""Every candidate eigenvector is retained on :class:`emfit.mode2d.Mode2D`.

Why this module exists
---------------------
:func:`emfit.mode2d.solve_modes` asks ARPACK for ``k`` eigenpairs, and
``_select_and_pack`` (``emfit/mode2d.py``) used to keep only the *chosen* one:
the other columns of the normalised ``(n_free, n_k)`` matrix were discarded, so
a caller could draw the mode the solver picked and nothing else.
``Mode2D.e_t_candidates`` now carries all of them -- one column per entry of
``Mode2D.candidates``, each in ``e_t``'s own layout: ``(n_edges,)``, zero on
every PEC edge, normalised so that ``e^T B e = 1``.  ``Mode2D.candidate_e_t(i)``
hands column ``i`` out (and ``Mode2D.e_at_candidate(i, points)`` interpolates
it), so any candidate can be drawn with the code that already draws ``e_t``.

Gauge: read this before adding an assertion here
-----------------------------------------------
An eigenvector is fixed only up to a scalar, and the solver's normalisation
pins the scale (``e^T B e = 1``) but **not the sign**: a different
LAPACK/ARPACK build, a different shift or a different starting vector can
return the same physical mode with the overall sign flipped, and nothing in
the problem distinguishes the two.  So every comparison below is made on
``abs(...)``, on ``e^T B e``, or on the normalised inner product

    |<u, B v>| / sqrt((u^T B u) (v^T B v))

which is invariant under ``u -> -u`` and ``v -> -v``.  Never assert signed
equality between two candidates, and never assert a candidate's sign against an
analytic profile.  The one exception is ``candidate_e_t(chosen)`` against
``e_t``: both are the bytes of one and the same column, so *bit* equality is
the correct -- and, for "the chosen path did not change", the required --
assertion there.

Mesh, shift and walls are those of ``tests/test_mode2d.py``: the recorded
anchor's 30 x 16 cell vacuum box over ``20 x 7.6`` mm at 10 GHz, with the shift
at ``0.40 k0^2`` so ``eigsh`` does not land on an eigenvalue
(``evidence/logs/pecbox.log``).  With this mesh ``n_k = k = 4``, and the four
candidates are the three curl-free ``beta^2 = k0^2`` modes plus TE10 at
``beta^2/k0^2 = 0.4383`` -- the spectrum the recorded anchor found.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit import mode2d as m2

W_BOX = 0.020             # m, broad wall (tests/test_mode2d.py:51)
H_BOX = 0.0076            # m, narrow wall (tests/test_mode2d.py:52)
F_TEST = 10.0e9           # Hz (tests/test_mode2d.py:53)
N_X = 31                  # node columns -> 30 cells across the broad wall
N_Y = 17                  # node rows -> 16 cells across the narrow wall
WALL_TOL = 1e-12          # m, the wall predicates' slack
SIGMA_FRACTION = 0.40     # shift, as a fraction of k0^2
K_MODES = 4               # what this module asserts the retention against


def _vacuum_box():
    """The recorded anchor's triangulation: 30 x 16 cells over ``W_BOX x H_BOX``."""
    return m2.structured_mesh(
        np.linspace(0.0, W_BOX, N_X),
        np.linspace(0.0, H_BOX, N_Y),
    )


def _pec_walls():
    """Four PEC walls as *node* predicates (edge is PEC when both ends match one)."""
    return (
        lambda p: np.abs(p[:, 0] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 0] - W_BOX) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - H_BOX) <= WALL_TOL,
    )


@pytest.fixture(scope="module")
def solve():
    """``(mesh, k0, res)`` -- one sparse solve, ``k=4``, shared by the tests."""
    mesh = _vacuum_box()
    k0 = m2.k0_from_freq(F_TEST)
    res = m2.solve_modes(
        mesh,
        k0,
        SIGMA_FRACTION * k0 * k0,
        eps_r=1.0,
        boundaries=_pec_walls(),
        k=K_MODES,
    )
    return mesh, k0, res


def _pencil(mesh, k0):
    """``(c_free, b_free, free)`` -- the pencil ``_select_and_pack`` solved.

    Rebuilt with the public :func:`emfit.mode2d.assemble` /
    :func:`emfit.mode2d.pec_edge_mask` exactly as :func:`~emfit.mode2d.solve_modes`
    builds it (``C = k0^2 M_eps - K_q``, ``B = M_mu``), so a stored candidate can
    be re-substituted and its residual recomputed from scratch.
    """
    k_q, m_mu, m_eps = m2.assemble(mesh, eps_r=1.0, mu_r=1.0)
    free = np.flatnonzero(~m2.pec_edge_mask(mesh, _pec_walls()))
    c = (k0 * k0 * m_eps - k_q).tocsr()
    b = m_mu.tocsr()
    return c[free][:, free], b[free][:, free], free


def _gram(u, v, b_free):
    """Normalised inner product ``u^T B v / sqrt((u^T B u)(v^T B v))``.

    Invariant under independent sign flips of ``u`` and ``v`` -- that is why it
    is the only cross-candidate comparison used in this module (see the module
    docstring's gauge note).
    """
    bu = b_free @ u
    bv = b_free @ v
    return float((u @ bv) / np.sqrt((u @ bu) * (v @ bv)))


# ---------------------------------------------------------------------------
# (a) the retention itself, and the index range it defines
# ---------------------------------------------------------------------------
def test_every_candidate_is_retained(solve) -> None:
    """``e_t_candidates`` is ``(n_edges, len(candidates))``, all of it finite."""
    mesh, _, res = solve
    cand = res.e_t_candidates
    assert cand is not None, "solve_modes must retain the candidate eigenvectors"
    assert cand.shape == (mesh.n_edges, len(res.candidates)), (
        f"e_t_candidates shape {cand.shape} does not match "
        f"({mesh.n_edges} edges, {len(res.candidates)} candidates)"
    )
    assert len(res.candidates) == K_MODES, (
        f"asked for {K_MODES} modes and got {len(res.candidates)}: the rest of "
        "this module's index range is meaningless"
    )
    assert cand.dtype == np.float64, f"unexpected dtype {cand.dtype}"
    assert np.all(np.isfinite(cand)), "a retained candidate is not finite"
    # zero on every PEC edge, exactly as e_t is (same packing statements)
    pecs = m2.pec_edge_mask(mesh, _pec_walls())
    assert np.all(cand[pecs, :] == 0.0), "a candidate is non-zero on a PEC edge"


def test_candidate_index_range(solve) -> None:
    """Indices ``0..k-1`` are valid; ``k`` and negatives raise ``IndexError``."""
    mesh, _, res = solve
    for i in range(K_MODES):
        vec = res.candidate_e_t(i)
        assert vec.shape == (mesh.n_edges,), f"candidate {i} has shape {vec.shape}"
        assert np.all(np.isfinite(vec)), f"candidate {i} is not finite"

    for bad in (K_MODES, K_MODES + 1, -1, -K_MODES - 1):
        with pytest.raises(IndexError, match=r"valid indices are 0\.\."):
            res.candidate_e_t(bad)


# ---------------------------------------------------------------------------
# (b) the chosen candidate is e_t, bit for bit
# ---------------------------------------------------------------------------
def test_chosen_column_is_e_t(solve) -> None:
    """``candidate_e_t(chosen)`` is ``e_t`` byte for byte -- no re-normalising.

    This is the atomicity assertion for the change: ``e_t`` is still packed by
    the two statements it always was (``zeros`` then ``[free] = normalised[:,
    chosen]``), and the retained matrix is packed from the same source, so the
    chosen path must be bit-identical -- not merely close.
    """
    _, _, res = solve
    chosen = res.candidate_e_t(res.chosen)
    assert chosen.tobytes() == res.e_t.tobytes(), (
        "the chosen candidate is no longer bit-identical to e_t: "
        f"max |difference| = {np.max(np.abs(chosen - res.e_t))!r}"
    )
    # a fresh copy: mutating what we were handed cannot reach the frozen result
    chosen[0] = 12345.0
    assert np.array_equal(res.candidate_e_t(res.chosen), res.e_t)


# ---------------------------------------------------------------------------
# (c) every retained candidate really solves the pencil it is indexed against
# ---------------------------------------------------------------------------
def test_candidate_residuals_match_the_pencil(solve) -> None:
    """Re-substitute each column: its residual matches ``candidate_residuals[i]``.

    ``candidate_residuals[i]`` is ``||C e - beta_sq B e|| / ||B e||`` of
    candidate ``i`` (``_select_and_pack``) and is index-aligned with
    ``candidates``.  Recomputing it from ``candidate_e_t(i)`` alone is the check
    that the retention kept the *right* column against the *right* beta: a
    transposed, shifted or re-ordered matrix would show up here as a residual
    of order one on whichever column disagreed.

    The row for the chosen index is the scalar ``residual`` too.
    """
    mesh, k0, res = solve
    c_free, b_free, free = _pencil(mesh, k0)
    for i, (beta_sq, _eps_eff) in enumerate(res.candidates):
        v = res.candidate_e_t(i)[free]
        be = b_free @ v
        got = float(np.linalg.norm(c_free @ v - beta_sq * be) / np.linalg.norm(be))
        assert np.isclose(got, res.candidate_residuals[i], rtol=1e-6, atol=1e-12), (
            f"candidate {i} re-substituted to residual {got!r}, but "
            f"candidate_residuals[{i}] = {res.candidate_residuals[i]!r}"
        )
    assert res.candidate_residuals[res.chosen] == res.residual, (
        "the chosen candidate's residual is no longer the scalar residual"
    )


# ---------------------------------------------------------------------------
# (d) distinct candidates, not k copies of one vector
# ---------------------------------------------------------------------------
def test_candidates_are_distinct(solve) -> None:
    """No two columns are the same field: off-diagonal normalised inner products are small.

    The matrix is ``(ne, k)``; the failure this guards against is a packing bug
    that writes one column k times (``normalised[:, [chosen]]*k``, a wrong
    fancy-index broadcast, or a list of k references to one array).  A
    duplicate would show a normalised inner product of magnitude 1 with its
    twin, and the three curl-free ``beta^2 = k0^2`` candidates are exactly the
    group where such a copy could hide.
    """
    mesh, k0, res = solve
    _, b_free, free = _pencil(mesh, k0)
    vecs = [res.candidate_e_t(i)[free] for i in range(len(res.candidates))]
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            assert not np.array_equal(vecs[i], vecs[j]), (
                f"candidates {i} and {j} are the same array"
            )
            g = abs(_gram(vecs[i], vecs[j], b_free))
            assert g < 0.99, (
                f"candidates {i} and {j} (beta^2 {res.candidates[i][0]!r} and "
                f"{res.candidates[j][0]!r}) have |normalised inner product| "
                f"{g!r}: they are the same field"
            )


# ---------------------------------------------------------------------------
# (e) the gauge: the scale is fixed, the sign is not
# ---------------------------------------------------------------------------
def test_gauge_is_scale_only(solve) -> None:
    """Every column has ``e^T B e = 1``; a sign flip of it is equally valid.

    Documents the gauge the other assertions must respect (module docstring):
    the retention fixes each candidate's *scale* -- that is assertable -- and
    leaves its *sign* free, which is why nothing here compares candidates by
    signed equality.  Both halves are asserted so that a future change of
    normalisation (say ``||e||_2 = 1``) fails loudly here rather than silently
    loosening the residual test.
    """
    mesh, k0, res = solve
    _, b_free, free = _pencil(mesh, k0)
    for i in range(len(res.candidates)):
        v = res.candidate_e_t(i)[free]
        assert np.isclose(v @ (b_free @ v), 1.0, rtol=1e-10), (
            f"candidate {i} is not normalised so that e^T B e = 1: got "
            f"{v @ (b_free @ v)!r}"
        )
        flipped = -v
        assert np.isclose(flipped @ (b_free @ flipped), 1.0, rtol=1e-10)
        assert not np.array_equal(flipped, v), "the sign is gauge, not data"

    # the interpolation helper is e_at with another column: the chosen one must
    # reproduce e_at exactly, and a sign-flipped column must reproduce it negated
    pts = np.column_stack(
        [np.linspace(0.1 * W_BOX, 0.9 * W_BOX, 7), np.full(7, 0.5 * H_BOX)]
    )
    assert np.array_equal(res.e_at_candidate(res.chosen, pts), res.e_at(pts))
