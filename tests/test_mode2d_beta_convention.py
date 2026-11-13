"""The ``Mode2D.beta`` convention, and the guard that holds it.

``beta`` is the three-case statement :func:`emfit.mode2d.candidate_records`
already makes about candidates: a number equal to ``sqrt(beta_sq)`` when
``beta_sq > 0`` (propagating), ``None`` when ``beta_sq == 0`` (exactly at
cutoff -- no real propagation constant and no decay either) and ``None`` when
``beta_sq < 0`` (evanescent, ``beta_imag`` carrying the decay constant).  These
tests pin the *convention* rather than a number -- no beta is compared to a
computed constant -- and pin :meth:`emfit.mode2d.Mode2D.__post_init__` as the
thing that refuses a ``(beta, beta_sq)`` pair telling two different stories.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit import mode2d as m2

#: Any positive wavenumber; only its scale reaches ``eps_eff`` here.
K0 = 2.0 * np.pi * 5.8e9 / 299792458.0


def _mesh():
    """A one-cell structured mesh -- the smallest ``Mode2D`` carrier."""
    return m2.structured_mesh(np.array([0.0, 1.0e-3]), np.array([0.0, 1.0e-3]))


def _mode(beta, beta_sq):
    """``Mode2D`` with every field but ``beta``/``beta_sq`` at an inert value."""
    mesh = _mesh()
    return m2.Mode2D(
        freq=5.8e9,
        k0=K0,
        beta=beta,
        beta_sq=beta_sq,
        eps_eff=float(beta_sq / (K0 * K0)),
        residual=0.0,
        candidates=(),
        curl_ratio=None,
        chosen=0,
        sigma=1.0,
        n_dof=1,
        n_pec=1,
        e_t=np.zeros(mesh.n_edges),
        mesh=mesh,
    )


# ---------------------------------------------------------------------------
# (a) beta_sq == 0: exactly at cutoff, so there is no propagation constant
# ---------------------------------------------------------------------------
def test_zero_beta_sq_refuses_a_numeric_beta():
    """At cutoff ``beta`` is not ``0`` and not anything else -- it is ``None``."""
    for beta in (0.0, -0.0, 1.0e-9, -1.0e-9, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="inconsistent beta"):
            _mode(beta, 0.0)


def test_zero_beta_sq_accepts_none():
    """``None`` is the one beta a ``beta_sq == 0`` mode may carry."""
    mode = _mode(None, 0.0)
    assert mode.beta is None
    assert mode.is_propagating is False
    assert mode.beta_imag == 0.0


# ---------------------------------------------------------------------------
# (b) beta_sq < 0: below cutoff, ``beta`` is None and beta_imag carries the rest
# ---------------------------------------------------------------------------
def test_below_cutoff_refuses_a_numeric_beta():
    """The old NaN (and anything else numeric) is refused below cutoff."""
    for beta in (0.0, -0.0, float("nan"), -1.0e3, 1.0e3, float("-inf")):
        with pytest.raises(ValueError, match="inconsistent beta"):
            _mode(beta, -4.0)


def test_below_cutoff_accepts_none():
    """``None`` constructs, and ``beta_imag`` is ``sqrt(-beta_sq)`` exactly."""
    mode = _mode(None, -4.0)
    assert mode.beta is None
    assert mode.is_propagating is False
    assert mode.beta_imag == pytest.approx(float(np.sqrt(4.0)))


# ---------------------------------------------------------------------------
# (c) beta_sq > 0: propagating, so there *is* a number and it must be given
# ---------------------------------------------------------------------------
def test_propagating_accepts_a_numeric_beta():
    """A propagating mode keeps the beta it was given."""
    mode = _mode(5.0, 25.0)
    assert mode.beta == 5.0
    assert mode.is_propagating is True
    assert mode.beta_imag == 0.0


def test_propagating_refuses_none():
    """``None`` on a propagating mode drops the one number the mode has."""
    with pytest.raises(ValueError, match="inconsistent beta"):
        _mode(None, 25.0)


# ---------------------------------------------------------------------------
# the refusal names the pair and both conventions, and rewrites nothing
# ---------------------------------------------------------------------------
def test_refusal_names_both_values_and_both_conventions():
    """The message has to be usable by whoever hit it: values *and* the rule."""
    with pytest.raises(ValueError) as excinfo:
        _mode(0.0, 0.0)
    text = str(excinfo.value)
    assert "beta = 0.0" in text
    assert "beta_sq = 0.0" in text
    assert "beta_sq > 0" in text
    assert "None" in text

    with pytest.raises(ValueError) as excinfo:
        _mode(None, 25.0)
    text = str(excinfo.value)
    assert "beta = None" in text
    assert "beta_sq = 25.0" in text
    assert "sqrt(beta_sq) = 5.0" in text


def test_the_guard_validates_and_does_not_coerce():
    """A number that is merely *wrong* is not rewritten to ``sqrt(beta_sq)``."""
    assert _mode(0.0, 25.0).beta == 0.0


# ---------------------------------------------------------------------------
# (d) all three cases together: the invariant, not three special cases
# ---------------------------------------------------------------------------
def test_no_accepted_mode_is_non_propagating_and_carries_a_beta():
    """Sweep the three ``beta_sq`` cases against every plausible ``beta``.

    This is the statement the guard exists for, and it is causal: no
    ``Mode2D`` that survives construction may be non-propagating while
    carrying a ``beta``, so no consumer can read a propagation constant off a
    mode that does not propagate.  The betas offered include the two the old
    convention emitted -- ``0.0`` at cutoff and ``nan`` below it.
    """
    betas = (None, 0.0, -0.0, 5.0, float("nan"), float("inf"))
    survivors = {}
    for beta_sq in (25.0, 0.0, -4.0):
        kept = []
        for beta in betas:
            try:
                kept.append(_mode(beta, beta_sq).beta)
            except ValueError:
                continue
        survivors[beta_sq] = kept

    # Every non-propagating beta_sq keeps ``None`` and nothing else.
    assert survivors[0.0] == [None]
    assert survivors[-4.0] == [None]
    # A propagating one keeps the numbers and loses the ``None``.
    assert None not in survivors[25.0] and survivors[25.0]

    for beta_sq, kept in survivors.items():
        for beta in kept:
            mode = _mode(beta, beta_sq)
            assert (mode.beta is None) == (not mode.beta_sq > 0.0), mode
            assert mode.is_propagating == (mode.beta is not None), mode
