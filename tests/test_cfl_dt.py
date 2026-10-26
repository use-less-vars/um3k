"""``emfit.evolve.cfl_dt``'s keyword-only parameters -- this file exists to keep
the silent-``c`` hazard closed: ``cfl_dt(grid, 0.99)`` used to bind 0.99 to
``c`` and return a time step 3e8 too small, producing a one-step zero-field run
that looks like success.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.evolve import cfl_dt
from emfit.grid import Grid
from emfit.materials import C0


def test_second_positional_argument_is_rejected():
    # The hazard: cfl_dt(grid, 0.99) silently set c = 0.99, giving dt = 2.3e-4 s
    # and a one-step zero-field run that looks like success.
    grid = Grid.uniform(8, 8, 8, 8e-3, 8e-3, 8e-3)
    with pytest.raises(TypeError):
        cfl_dt(grid, 0.99)


def test_safety_is_keyword_only_and_still_works():
    grid = Grid.uniform(8, 8, 8, 8e-3, 8e-3, 8e-3)
    dt = cfl_dt(grid, safety=0.99)
    expect = 0.99 / (C0 * np.sqrt(3.0 / (1e-3 ** 2)))
    assert dt == pytest.approx(expect, rel=1e-12)


def test_c_is_keyword_only_and_still_works():
    grid = Grid.uniform(8, 8, 8, 8e-3, 8e-3, 8e-3)
    dt_c0 = cfl_dt(grid, safety=0.99)
    dt_c2 = cfl_dt(grid, c=2.0 * C0, safety=0.99)
    assert dt_c2 == pytest.approx(0.5 * dt_c0, rel=1e-12)


def test_safety_still_defaults_when_omitted():
    grid = Grid.uniform(8, 8, 8, 8e-3, 8e-3, 8e-3)
    assert cfl_dt(grid) == pytest.approx(cfl_dt(grid, safety=0.99), rel=1e-15)
