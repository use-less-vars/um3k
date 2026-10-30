"""Regression test for the mode-selection gate in :mod:`tools.host_ladder`.

The defect
----------
``candidates()`` computed and stored a per-pair ``residual``, and
``pick_mode()`` was meant to require ``residual < TOL_RESID`` before a
candidate could be called physical -- but the clause was missing from the
selection predicate.  ``pick_mode`` therefore accepted any candidate whose
residual was merely not ``None``, and on the h = 0.2 mm rung it selected a
junk mode with residual 9.86e-01 as "the fundamental", because junk happened
to carry the largest ``beta^2``.

What these tests pin
--------------------
* a mixed candidate set must select the residual-clean row, not the junk row
  that outranks it on ``beta^2`` (the exact shape of the original defect);
* an all-rejected set must signal "nothing selected" instead of falling
  through to a best-effort pick;
* the diagnostic reason must name the best (smallest) rejected residual and
  the per-guard rejection counts, so the verdict is legible rather than a
  bare "none physical".

The real API is used unchanged: ``pick_mode(rows) -> (best, near)`` with
``best`` a candidate row (or ``None``) and ``near`` the accepted runner-up
list, and ``no_candidate_reason(rows, rec, h_mm) -> str``.  The rows are
built with the same keys ``candidates()`` produces.
"""

from tools.host_ladder import pick_mode, no_candidate_reason, TOL_RESID


def _row(j, beta, residual, imag_rel=1.0e-09, curl_ratio=1.0e-01,
         eps_eff=3.0, guard_imag=True, guard_curl=True, guard_eps=True):
    """One candidate row, keyed exactly like ``candidates()`` output."""
    lam = float(beta) ** 2
    return {
        "j": j,
        "lam": lam,
        "imag_rel": imag_rel,
        "residual": residual,
        "curl_ratio": curl_ratio,
        "eps_eff": eps_eff,
        "beta_sq": lam,
        "beta": float(beta),
        "guard_imag": guard_imag,
        "guard_curl": guard_curl,
        "guard_eps": guard_eps,
    }


def test_mixed_set_selects_clean_row_not_junk_high_beta_sq_row():
    """The junk row has the largest ``beta^2``; the gate must still skip it."""
    rows = [
        # residual 9.86e-01: the junk mode that used to become "the
        # fundamental" purely because it had the largest beta^2.
        _row(j=0, beta=400.0, residual=9.86e-01),
        # converged, but the residual is far above TOL_RESID.
        _row(j=1, beta=412.0, residual=5.0e-03),
        # the real physical mode: clean residual, smallest of the three.
        _row(j=2, beta=389.0, residual=1.2e-13),
    ]
    best, near = pick_mode(rows)

    assert best is not None, "the residual-clean row must be selected"
    assert best["beta"] == 389.0, (
        f"selected beta {best['beta']!r}: the residual gate did not reject "
        f"the junk modes"
    )
    assert best["residual"] == 1.2e-13
    assert best["residual"] < TOL_RESID
    # the runner-up list may only contain rows that cleared the gate too.
    assert all(r["residual"] is not None and r["residual"] < TOL_RESID
               for r in near)


def test_all_rejected_set_selects_nothing():
    """Every residual is >= TOL_RESID, so nothing may be picked."""
    rows = [
        _row(j=0, beta=400.0, residual=9.86e-01),
        _row(j=1, beta=412.0, residual=5.0e-03),
        _row(j=2, beta=389.0, residual=2.0e-03),
    ]
    assert all(r["residual"] >= TOL_RESID for r in rows)

    best, near = pick_mode(rows)

    assert best is None, f"picked {best!r} although no residual cleared the gate"
    # the real API returns an empty runner-up list when nothing was accepted.
    assert near == []


def test_no_candidate_reason_names_best_rejected_residual_and_counts():
    """The reason string must name the best rejected residual and the counts."""
    rows = [
        _row(j=0, beta=400.0, residual=9.86e-01),
        _row(j=1, beta=412.0, residual=5.0e-03),
        _row(j=2, beta=389.0, residual=2.0e-03),
    ]
    best, _near = pick_mode(rows)
    assert best is None

    reason = no_candidate_reason(rows, {}, 0.2)

    # the rung is named
    assert "h = 0.2 mm" in reason
    # the counts and the best (smallest) rejected residual
    assert "all 3 candidates rejected" in reason
    assert "best residual 2.00e-03" in reason
    # per-guard rejections: only the residual gate killed anything here
    assert "per-guard rejections" in reason
    assert "imag 0/3" in reason
    assert "residual 3/3" in reason
    assert "guard(s) rejecting every pair: residual" in reason
    # and the verdict is kept apart from a solver failure
    assert "eigs itself converged (n_conv = 3)" in reason
