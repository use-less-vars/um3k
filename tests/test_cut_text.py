"""The cut row must not understate how little a y/z cross-section shows.

``poc_app._cut_text`` (server/poc_app.py:9031) is the row under the cut
sliders, and it is PURE: it takes the plain dict ``_cut_layout`` returns and
returns a string.  Nothing is booted, no plotter, no Qt, no dump - which is
also why these tests can pin the row byte for byte instead of substring-hunting
a rendered label.

The claim they defend: a y or z cut has no axis to sample along, so
``build_cut_sheets`` draws exactly ONE of the captured x-planes (the
slice-of-one of ``plane[:, j : j + 1, :]`` / ``plane[:, :, k : k + 1]``).  A row
that says only "one sample each, no interpolation" is true but understates how
little the sheet shows: it never says the sample is one STORED plane, nor how
many were captured.  The row must therefore read "one stored x-plane of N
captured stations".

``n_st`` is the captured station count ONLY on the planes branch
(``n_st, n_j, n_k = plane.shape``); on the volume branch it is the |E| volume's
own ``nx``, a completely different number.  Printing it there would state a
wrong count - the very defect this row is fixing - so the leakage test below
is the one that matters most.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # The same two entries every other poc_app test adds, so
        # `import poc_app` resolves from server/poc_app.py.
        sys.path.insert(0, _p)

# pyvista lives in the repo's own venv in this image (its bin/python is
# broken, the site-packages tree is not). Inert where it is installed
# normally.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

import poc_app  # noqa: E402  (the sys.path block above is why)


#: Every number here is 9-free on purpose: one test asserts that a hardcoded
#: "9" cannot survive, and a stray 9 in a coordinate would mask the failure.
J, N_J, K, N_K = 5, 121, 5, 121
Y_MM, Z_MM = 42.6, 42.6


def _planes(n_st, **over):
    """A planes-branch layout: ``n_st`` is the captured x-plane count."""
    layout = {
        "cell_mm": 0.4,
        "source": "planes",
        "n_st": n_st,
        "n_j": N_J,
        "n_k": N_K,
        "j": J,
        "k": K,
        "y_mm": Y_MM,
        "z_mm": Z_MM,
        "x_lo_mm": 10.4,
        "x_hi_mm": 20.0,
        "dx_mm": 1.2,
    }
    layout.update(over)
    return layout


def _volume(n_st, **over):
    """A volume-branch layout: ``n_st`` is the |E| volume's own ``nx``."""
    layout = _planes(n_st, source="volume", **over)
    return layout


def test_the_planes_row_names_the_stored_plane_and_the_captured_count():
    """Byte for byte: one stored x-plane, out of the N that were captured.

    Written as a literal rather than assembled from the code's own pieces: a
    test that rebuilds the expected string with the same f-strings proves only
    that the f-strings agree with themselves.
    """
    text = poc_app._cut_text(_planes(9))

    assert text == (
        "cut y = 6/121 (y = 42.6000 mm)   "
        "cut z = 6/121 (z = 42.6000 mm)   one sample each   "
        "(one stored x-plane of 9 captured stations, no interpolation)"
    ), f"the cut row changed: {text!r}"


@pytest.mark.parametrize("n_st", [2, 7, 9, 41])
def test_the_count_is_derived_from_n_st_and_not_hardcoded(n_st):
    """The page must not print the shipped dump's 9 over someone else's dump.

    Nine is a property of the Build A capture (nine x-planes, 1.2 mm apart from
    10.4 mm), not a property of this page: a dump with 41 stations has to read
    41.  The ``n_st == 7`` case additionally forbids the digit 9 ANYWHERE in
    the row, which is what catches a later ``f"... of 9 captured stations"``.
    """
    text = poc_app._cut_text(_planes(n_st))

    assert f"of {n_st} captured stations" in text, (
        f"the row does not derive the captured count from n_st={n_st}: {text!r}"
    )
    if n_st == 7:
        assert "9" not in text, (
            "the row still carries a hardcoded 9 where the station count "
            f"belongs: {text!r}"
        )


def test_a_single_captured_station_is_singular():
    """"1 captured station", not "1 captured stations"."""
    text = poc_app._cut_text(_planes(1))

    assert "of 1 captured station," in text, text
    assert "stations" not in text, (
        f"one station is singular, and the row says otherwise: {text!r}"
    )


def test_the_volume_row_never_quotes_the_captured_station_count():
    """The trap: on the volume branch ``n_st`` is the volume's ``nx``.

    ``_cut_layout`` sets ``n_st = n_x`` for a volume, so a station sentence
    that leaked out of the planes branch would print the volume's x cell count
    as though it were the number of captured planes - a wrong number on the
    page, which is worse than the understatement being fixed.
    """
    layout = _volume(3)
    text = poc_app._cut_text(layout)

    assert "|E| volume cells, cell centres" in text, (
        "the volume row does not say which lattice its millimetres are "
        f"on: {text!r}"
    )
    assert "no interpolation" in text, text
    assert "stored x-plane" not in text, (
        f"the planes clause leaked into the volume row: {text!r}"
    )
    assert "captured station" not in text, (
        f"the volume row quotes its nx as a station count: {text!r}"
    )


@pytest.mark.parametrize("missing", [None, 0, -3])
def test_a_planes_row_without_a_usable_count_omits_the_clause(missing):
    """No key (or a nonsense value) drops the clause; it never guesses.

    ``layout['n_st']`` can be absent on a fake layout that predates the key -
    the function's own docstring says so, which is why it reads with ``.get``.
    Printing a guessed count would be the same class of defect as the one being
    fixed, so the row falls back to the plain planes sentence.
    """
    layout = _planes(9)
    layout["n_st"] = missing
    text = poc_app._cut_text(layout)

    assert text.endswith("(one stored x-plane, no interpolation)"), (
        f"the row did not fall back cleanly on n_st={missing!r}: {text!r}"
    )
    assert "captured station" not in text, text


def test_a_planes_row_with_no_n_st_key_omits_the_clause():
    """The key itself is optional; only its absence must not raise."""
    layout = _planes(9)
    del layout["n_st"]

    text = poc_app._cut_text(layout)

    assert text.endswith("(one stored x-plane, no interpolation)"), text
    assert "captured station" not in text, text


@pytest.mark.parametrize(
    "layout",
    [
        _planes(9),
        _planes(1),
        _planes(41),
        _volume(3),
        _volume(41),
    ],
)
def test_both_branches_state_that_nothing_is_interpolated(layout):
    """Neither row resamples, so neither row may drop the disclosure.

    The planes branch draws one stored plane and the volume branch one cell
    layer; "no interpolation" is the one sentence true of both, and it is the
    sentence an operator needs in order to read a 121-sample-wide sheet as the
    single sample it is.
    """
    text = poc_app._cut_text(layout)

    assert "no interpolation" in text, (
        f"the {layout['source']} row lost it: {text!r}"
    )
