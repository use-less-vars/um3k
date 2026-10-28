"""Analytic s-pol reference roots for the anchor geometry.

Transcription of the reference implementation frozen in
``docs/design/anchor_preregistration.md`` section 2.2 (that document is not
modified here; its numbers are also stored below so a run can check itself).

One scalar transcendental equation in one unknown:

    k1*cot(k1*t) + k2*cot(k2*L2) = 0,   k1^2 = eps_r*k0^2 - beta^2,
                                        k2^2 = k0^2 - beta^2,   L2 = b - t

solved by ``brentq`` on brackets found by a two-resolution sign-change scan.
No finite elements, no matrices, no eigensolver: this is the analytic side of
the comparison, and it is the only numerics the anchor is permitted besides
arithmetic on the betas the live solver returns.
"""

import numpy as np
from scipy.optimize import brentq

# --- geometry A, all exact in binary (section 1) -----------------------
C0 = 299792458.0
B = 2.0 ** -7                 # slab height b = 0.0078125 m
A = B / 8.0                   # box width a = b/8
T = B / 4.0                   # slab thickness t = b/4 (geometry A)
EPS_R = 2.0                   # slab permittivity
F = 3.5 * C0 / (2.0 * B)      # 67153510592.0 Hz
K0 = 2.0 * np.pi * F / C0     # 448*pi rad/m

# --- the frozen document's own numbers (sections 2.4 / 2.6), for checking --
# geometry A roots, beta descending
BETA_REF_DOC = (1637.9985692980779, 1296.2992799512633, 944.6029788248537)
EPS_EFF_DOC = (1.3544758398156966, 0.8483103899760305, 0.45044611773722776)
# section 2.6 self-check, eps_r = 1, n = 1, 2, 3
BETA_EPS1_DOC = (1348.764428360, 1155.012851741, 724.939097545)


def f_disp_terms(beta, t, eps_r=EPS_R, b=B, k0=K0):
    """The two terms of the relation, ``(k1*cot(k1*t), k2*cot(k2*L2))``."""
    L2 = b - t
    d1 = eps_r * k0 * k0 - beta * beta
    d2 = k0 * k0 - beta * beta
    if d1 >= 0.0:
        s1 = np.sqrt(d1)
        t1 = s1 / np.tan(s1 * t)
    else:
        s1 = np.sqrt(-d1)
        t1 = s1 / np.tanh(s1 * t)      # k*cot(k*L) = s*coth(s*L) on that branch
    if d2 >= 0.0:
        s2 = np.sqrt(d2)
        t2 = s2 / np.tan(s2 * L2)
    else:
        s2 = np.sqrt(-d2)
        t2 = s2 / np.tanh(s2 * L2)
    return t1, t2


def f_disp(beta, t, eps_r=EPS_R, b=B, k0=K0):
    """s-pol dispersion value, real for every beta (both branches)."""
    t1, t2 = f_disp_terms(beta, t, eps_r=eps_r, b=b, k0=k0)
    return t1 + t2


def diagnose(beta, t, eps_r=EPS_R, b=B, k0=K0):
    """``(relative residual, term scale)`` at ``beta``.

    The relative residual ``|f| / max(|t1|, |t2|)`` is the measure section 2.4
    quotes; the term scale separates a root from a pole (see ``solve_ref``).
    """
    t1, t2 = f_disp_terms(beta, t, eps_r=eps_r, b=b, k0=k0)
    scale = max(abs(t1), abs(t2))
    if not np.isfinite(scale):
        return float("inf"), float("inf")
    if scale == 0.0:
        return float("inf"), 0.0
    return abs(t1 + t2) / scale, scale


def poles(t, eps_r=EPS_R, b=B, k0=K0):
    """Every beta in (0, sqrt(eps_r)*k0) where f_disp has a simple pole."""
    out, m = [], 1
    while True:
        a = eps_r * k0 * k0 - (m * np.pi / t) ** 2        # sin(k1*t) = 0
        c = k0 * k0 - (m * np.pi / (b - t)) ** 2          # sin(k2*L2) = 0
        if a > 0.0:
            out.append(np.sqrt(a))
        if c > 0.0:
            out.append(np.sqrt(c))
        if a <= 0.0 and c <= 0.0:
            break
        m += 1
    return out


# A candidate root is accepted only if the two terms of the relation are of
# physical size there.  At the genuine roots of sections 2.4 / 2.6 the larger
# term is 8.4e2 .. 7.8e3 (k0 = 1.4e3); at a pole it is O(1/eps) >= 1e15.  1e9 is
# nine decades above the largest term the document quotes and six below the
# pole, so it is not a judgement call.  (The *relative* residual of 2.4 is
# reported as well, but it cannot serve as the test: at eps_r = 1, n = 2 both
# terms are themselves round-off, so a genuine root there has a relative
# residual of order 1.)
ACCEPT_SCALE = 1e9


def solve_ref(t, eps_r=EPS_R, b=B, k0=K0, n_scan=(4000, 8000),
              accept_scale=ACCEPT_SCALE, rejected=None):
    """All roots of f_disp on (0, sqrt(eps_r)*k0), ordered ascending.

    The bracket census is exactly section 2.2(c): the domain is cut at every
    pole and at the kink, each pole-free interval is scanned at two resolutions
    and the counts must agree, then ``brentq`` refines the bracket.

    One addition is unavoidable and is reported, never hidden.  The cut points
    are the *endpoints* of the scan grids, and sin() is not exactly zero there,
    so ``f`` evaluates to about +-1e19 at a pole with a sign decided by
    rounding.  When that sign opposes the interior one, the first or last cell
    of the interval looks like a sign change and brentq converges onto the pole
    itself.  The two-resolution count check cannot see this (the artefact is
    always the end cell, at both resolutions), so every refined root is
    accepted only if the term scale there is below ``accept_scale``: O(1e3) at
    a genuine root, O(1e19) at a pole.  Rejected roots are appended to
    ``rejected`` as ``(beta, relative residual, term scale)`` triples.  Genuine
    roots are unaffected by this test.
    """
    top = np.sqrt(eps_r) * k0
    cuts = sorted(set([0.0, k0, top] + poles(t, eps_r=eps_r, b=b, k0=k0)))
    roots = []
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        if hi <= lo:
            continue
        brackets = []
        for n in n_scan:
            xs = np.linspace(lo, hi, n)
            fs = np.array([f_disp(x, t, eps_r=eps_r, b=b, k0=k0) for x in xs])
            found = [(xs[i], xs[i + 1]) for i in range(n - 1)
                     if fs[i] * fs[i + 1] < 0.0]
            brackets.append(found)
        if len(brackets[0]) != len(brackets[1]):
            raise RuntimeError("scan resolution disagreement on [{0}, {1}]"
                               .format(lo, hi))
        for (lo_b, hi_b) in brackets[0]:
            cand = brentq(f_disp, lo_b, hi_b, args=(t, eps_r, b, k0),
                          xtol=5e-323, rtol=1e-15, maxiter=500)
            rr, scale = diagnose(cand, t, eps_r=eps_r, b=b, k0=k0)
            if scale <= accept_scale:
                roots.append(cand)
            elif rejected is not None:
                rejected.append((cand, rr, scale))
    return sorted(roots)
