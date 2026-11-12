"""Pins the driver's DEFAULT S21 extraction plane: ``ix_load + 1`` (DR-43 residual 1).

``evidence/termination/run_build_A.py`` (``build_kwargs``, ``else`` branch at
~line 1830) resolves the far extraction probe to ``ix_load + 1`` when neither
``--s21-plane-index`` nor ``--s21-plane-col`` is given: the plane sits on the
load's own node column plus one, so it reads the element's near field rather
than its cut.  That default is a known systematic, and DR-43 residual 1 records
that NO test in this repository constrained it -- a search of ``tests/`` for
``s21_plane_col`` and ``ix_load + 1`` returned nothing.

This file is a CHARACTERISATION test: it pins the default AS IT IS and neither
endorses nor fixes it.  Whoever changes the default is expected to UPDATE these
assertions (and the driver's comment) in the same commit -- deleting the file
would put the default back in the unconstrained state DR-43 records.

The assertions are behavioural, not textual: the driver module is imported and
``build_kwargs`` is CALLED, so the numbers below are what the driver actually
resolves, not what its source looks like.  The import is cheap because the
module's top-level imports are standard library only (argparse, json, os,
platform, resource, sys, threading, time, datetime, pathlib); numpy and emfit
are imported inside the functions that need them.  No assertion here reads a
written artefact: no checked-in or untracked artefact is demonstrably a
default-plane run, and a hand-built fixture would pin the fixture, not the
driver.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_run_build_a():
    """Import ``evidence/termination/run_build_A.py`` as a module."""
    evidence = Path(__file__).resolve().parents[1] / "evidence" / "termination"
    if str(evidence) not in sys.path:
        sys.path.insert(0, str(evidence))
    import run_build_A

    return run_build_A


def _default_run_a_args(run_build_A, **overrides):
    """The namespace ``main()`` hands ``build_kwargs`` for a default Run A call.

    The parser is built inside ``main()`` and its ``--load-ohm`` default is
    ``None`` (resolved from ``STRUCTURES`` there), so the resolved defaults are
    restated here: load at 20 mm, ``n_line`` the module's own default, 2400
    steps, ``launch`` "lumped", no plane flag.  Only the plane flags are moved
    by the tests below.
    """
    args = SimpleNamespace(
        structure="A",
        out=None,
        load_at_mm=20.0,
        n_line=run_build_A.N_LINE_DEFAULT,
        load_ohm=run_build_A.STRUCTURES["A"]["load_ohm"],
        netlist=None,
        nsteps=2400,
        s21_plane_index=None,
        s21_plane_col=None,
        ms_x_window=None,
        launch="lumped",
        flux_projection=False,
    )
    for name, value in overrides.items():
        setattr(args, name, value)
    return args


def test_no_plane_flag_resolves_the_plane_one_column_past_the_load():
    run_build_A = _load_run_build_a()
    kwargs = run_build_A.build_kwargs(_default_run_a_args(run_build_A))

    # The load column, re-derived the way emfit/studies.py:2727 derives it.
    cell_m = float(kwargs["h"]) / float(kwargs["n_sub"])
    ix_load = int(math.floor(kwargs["loads"][0].position / cell_m + 0.5))
    assert cell_m == pytest.approx(0.4e-3)
    assert ix_load == 50

    # "cut" is what the caller REQUESTED; the default policy replaces the word
    # with a column, and the number that arrives is ix_load + 1.
    assert run_build_A.S21_PLANE == "cut"
    assert isinstance(kwargs["s21_plane"], int)
    assert kwargs["s21_plane"] == ix_load + 1   # the pinned expression
    assert kwargs["s21_plane"] == 51            # and the number it resolves to


def test_an_explicit_plane_index_is_used_verbatim():
    run_build_A = _load_run_build_a()
    kwargs = run_build_A.build_kwargs(
        _default_run_a_args(run_build_A, s21_plane_index=7))

    # Flag given, so the default branch is not reached at all: what arrives is
    # the caller's own column.  The pin above is therefore on the DEFAULT only.
    assert kwargs["s21_plane"] == 7


def test_an_explicit_plane_col_is_used_verbatim():
    run_build_A = _load_run_build_a()
    kwargs = run_build_A.build_kwargs(
        _default_run_a_args(run_build_A, s21_plane_col=53))

    # The same hand-picked column by the other flag (downstream of the load and
    # inside nx = 62, so neither refusal fires).
    assert kwargs["s21_plane"] == 53
