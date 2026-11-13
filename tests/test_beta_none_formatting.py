"""A beta that is ABSENT, not NaN: the formatters must say so instead of raising.

``beta`` is ``float | None`` all the way down (``emfit/mode2d.py:1290``: a
number exactly when ``beta_sq > 0``, else ``None``, enforced by
``Mode2D.__post_init__``).  The caption path in ``server/poc_app.py``
(``_mode_caption``, fed by a solve that sets ``beta_rad_per_m`` to ``None``
when the solver returned no beta) formats that field with a fixed-point
spec, so a ``None`` there is a ``TypeError`` on a live panel, not a cosmetic
gap.  ``app._fmt`` is the module's own answer to it (``"n/a"``), and
``tools/host/anchor/ladder.py`` has the same helper under the same name
convention (``_fmt_beta`` -> ``"n/m"``).

These tests pin the two formatters and then call the REAL ``_mode_caption``
with a ``None`` beta: the caption must still be produced, must name the
missing beta as missing, and must still print the numbers beside it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries tests/test_poc_mode_picker.py adds, so
        # `import poc_app` resolves from server/poc_app.py
        sys.path.insert(0, _p)


def _ladder():
    """``tools/host/anchor/ladder.py`` imported by path, or skipped."""
    path = REPO_ROOT / "tools" / "host" / "anchor"
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    try:
        import ladder  # noqa: F401  (imported for its side-effect-free defs)
    except Exception as exc:  # pragma: no cover - environment, not behaviour
        pytest.skip(f"tools/host/anchor/ladder.py is not importable here: {exc}")
    return ladder


def _result(beta):
    """The minimum ``_mode_caption`` reads, with ``beta`` the one variable."""
    return {
        "beta_rad_per_m": beta,
        "eps_eff": 3.629512,
        "residual": 1.25e-13,
        "curl_ratio": 4.5e-07,
        "beta_model": 312.1468,
        "delta_vs_model_pct": 0.20,
        "beta_banked": None,
        "delta_vs_banked_pct": None,
        "extent": (4.0e-3, 1.0e-3),
        "n_nodes": 527,
        "n_edges": 1486,
        "seconds": 0.42,
    }


def _mesh():
    """A stand-in mesh: ``_mode_caption`` reads only ``grid_axes``."""
    return SimpleNamespace(
        grid_axes=(np.linspace(0.0, 4.0e-3, 5), np.linspace(0.0, 1.0e-3, 4)))


# --- the formatters ---------------------------------------------------------


def test_fmt_prints_n_a_for_a_missing_number() -> None:
    import poc_app as app

    assert app._fmt(None) == "n/a"
    assert app._fmt(None, 4) == "n/a"


def test_fmt_keeps_the_requested_number_of_places() -> None:
    import poc_app as app

    assert app._fmt(1.23456, 4) == "1.2346"
    assert app._fmt(1.23456) == "1.234560"


def test_ladder_fmt_beta_prints_n_m_for_a_missing_beta() -> None:
    ladder = _ladder()

    assert ladder._fmt_beta(None) == "n/m"
    assert ladder._fmt_beta(311.24570468) == "311.24570468"


# --- the caption that consumes them ----------------------------------------


def test_caption_names_a_missing_beta_instead_of_raising() -> None:
    import poc_app as app

    caption = app._mode_caption(_result(None), _mesh())

    assert "beta = n/a rad/m" in caption
    # the numbers that are present are still printed beside it
    assert "eps_eff = 3.629512" in caption
    assert "residual = 1.25e-13" in caption


def test_caption_still_prints_a_present_beta_to_four_places() -> None:
    import poc_app as app

    caption = app._mode_caption(_result(312.7827646322591), _mesh())

    assert "beta = 312.7828 rad/m" in caption
    assert "n/a" not in caption.split("Compare the three together")[0]
