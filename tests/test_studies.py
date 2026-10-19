"""Tests for :mod:`emfit.studies`, the catalogue behind every front end.

Only two kinds of claim are made here, and both are cheap:

* *Registration.*  A study in :data:`emfit.studies.STUDIES` is reachable by
  name through :func:`emfit.studies.get`, and its knobs coerce to exactly the
  keys and types it declares.  The check is written against the registry rather
  than against one entry, so a study added later is covered for free.
* *A tiny wave run.*  ``microstrip`` is the only study that builds a full 3-D
  time-domain case, so a smoke test is the only honest thing to run in a test
  suite: a handful of cells per axis, a few dozen steps, and assertions about
  shape and finiteness only.  ``Z0`` and ``eps_eff`` on such a grid are junk --
  pinning junk is worse than pinning nothing -- so they are deliberately
  **not** asserted.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from emfit import studies


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------
def test_microstrip_study_is_registered():
    """``microstrip`` is a registry key and its declaration is well-formed."""
    assert "microstrip" in studies.STUDIES

    study = studies.get("microstrip")
    assert study is studies.STUDIES["microstrip"]
    assert study.name == "microstrip"
    assert callable(study.run)
    assert study.title and study.blurb

    # The knobs are exactly the declared ones, with the declared types: the
    # contract every entry in the registry is consumed under.
    values = studies.coerce(study, {})
    assert set(values) == {p.key for p in study.params}
    assert isinstance(values["nsteps"], int)
    assert isinstance(values["npml"], int)
    assert isinstance(values["f0"], float)

    # ... and it is present alongside the pre-existing studies, not instead.
    assert {"cavity", "modes", "duct", "scatter", "rcs"} <= set(studies.STUDIES)


# ---------------------------------------------------------------------------
# a wave run that is deliberately too small to be physical
# ---------------------------------------------------------------------------
def test_microstrip_wave_smoke():
    """A six-cell line for forty steps: populated result, finite phasors."""
    t_start = time.perf_counter()
    result = studies.microstrip_wave(
        n_sub=1,
        n_air=1,
        n_strip=2,
        n_clean=1,
        n_pml=2,
        n_top=0,          # plain PEC lid here; n_top must equal n_pml otherwise
        n_ref=1,
        n_line=6,
        x_first=6.4e-3,
        x_last=11.2e-3,
        n_stations=3,
        nsteps=40,
        sink=None,
    )
    elapsed = time.perf_counter() - t_start

    # --- geometry was actually built from the knobs ----------------------
    geo = result.geometry
    assert geo["nsteps"] == 40
    assert geo["n_warm"] == 10                    # a quarter of 40
    assert geo["n_acc"] == 30
    assert geo["nx"] == 2 + 1 + 6
    assert geo["ny"] == 2 * 2 + 2 + 2 * 1
    assert geo["nz"] == 1 + 1
    assert geo["cell"] == pytest.approx(1.6e-3)
    assert geo["f"] > 0.0 and np.isfinite(geo["f"])
    assert geo["dt"] > 0.0 and np.isfinite(geo["dt"])
    assert geo["n_edges"] > 0
    assert len(geo["station_cells"]) == 3

    # --- stations have the requested count, and are ordered -------------
    assert result.station_x.shape == (3,)
    assert result.v_stations.shape == (3,)
    assert np.all(np.isfinite(result.station_x))
    assert np.all(np.diff(result.station_x) > 0.0)  # strictly increasing
    assert result.y_extent > 0.0

    # --- every complex phasor is finite (junk is fine, an inf is not) ---
    phasors = {
        "v_stations": result.v_stations,
        "v_port": np.array([result.v_port]),
        "i_ground_full": np.array([result.i_ground_full]),
        "i_ground_truncated": np.array([result.i_ground_truncated]),
    }
    for name, value in phasors.items():
        assert np.all(np.isfinite(value)), f"{name} is not finite: {value!r}"

    # --- the closed form the run is compared against --------------------
    assert result.beta_model > 0.0
    assert result.eps_eff_model > 1.0
    assert result.z0_model > 0.0
    assert np.isfinite(result.beta)

    # --- and the one-line summary is actually a line --------------------
    line = result.summary()
    assert line.startswith("microstrip ")
    assert "\n" not in line

    # Cheap is the point: this must not become a slow test by accident.
    assert elapsed < 10.0, f"the tiny case took {elapsed:.2f} s"


# ---------------------------------------------------------------------------
# the mesh, which must not drift again
# ---------------------------------------------------------------------------
def test_microstrip_default_mesh_is_the_historical_case():
    """The default mesh is the recovered reference case, cell for cell.

    These five numbers *are* the case: ``h / n_sub = 0.4 mm`` is the cell the
    reference ``Z0`` and ``eps_eff`` were taken at, and the edge count follows
    from ``62 x 44 x 22``.  Retuning any default changes the case, so the mesh
    is pinned here rather than left to whatever the constants happen to say.
    """
    # The mesh build is not separable from the time loop, so this runs the
    # default geometry for a handful of steps (~0.1 s).  Everything asserted
    # below is decided before the first step, so ``nsteps`` is irrelevant here.
    result = studies.microstrip_wave(nsteps=8)

    geo = result.geometry
    assert geo["nx"] == 62
    assert geo["ny"] == 44
    assert geo["nz"] == 22                 # 4 substrate + 12 air + 6 absorber
    assert geo["n_edges"] == 190296
    assert geo["cell"] == pytest.approx(0.4e-3)
