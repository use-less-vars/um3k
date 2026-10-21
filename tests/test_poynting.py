"""The Poynting diagnostic: the pure helper, and the opt-in flag on the study."""

import numpy as np
import pytest

from emfit import studies
from emfit.operators import CellComplex, Grid
from emfit.ports import station_poynting

D = 0.1        # one uniform cell, so every width is D


def _mesh(nx=3, ny=2, nz=2):
    grid = Grid.uniform(nx, ny, nz, nx * D, ny * D, nz * D)
    return grid, CellComplex(grid)


def _travelling_wave(grid, cc, ey=1.0, hz=1.0):
    """A uniform +x-carrying wave: ``E_y = ey`` V/m and ``H_z = hz`` A/m."""
    e = np.zeros(cc.n_edges)
    h = np.zeros(cc.n_faces)
    ey_view = e[cc.off_ey:cc.off_ey + cc.n_ey].reshape(cc.nxn, cc.ny, cc.nzn)
    ey_view[:] = ey * grid.widths("y")[None, :, None]
    fz_view = h[cc.off_fz:cc.off_fz + cc.n_fz].reshape(cc.nx, cc.ny, cc.nzn)
    fz_view[:] = hz * grid.dual_widths("z")[None, None, :]
    return e, h


# --------------------------------------------------------------------------- #
# the helper on its own
# --------------------------------------------------------------------------- #
def test_zero_field_is_zero_flux():
    grid, cc = _mesh()
    sx = station_poynting(np.zeros(cc.n_edges), np.zeros(cc.n_faces), cc, 1)
    assert sx == 0.0


def test_travelling_wave_flux_is_EH_times_area():
    grid, cc = _mesh()
    e, h = _travelling_wave(grid, cc, ey=2.0, hz=3.0)
    area = float(np.sum(grid.widths("y")) * np.sum(grid.dual_widths("z")))
    assert station_poynting(e, h, cc, 1) == pytest.approx(6.0 * area)


def test_flux_changes_sign_with_the_forward_direction():
    grid, cc = _mesh()
    e, h = _travelling_wave(grid, cc)
    forward = station_poynting(e, h, cc, 1)
    backward = station_poynting(e, np.zeros(cc.n_faces) - h, cc, 1)
    assert forward > 0.0
    assert backward == pytest.approx(-forward)


def test_the_EzHy_term_subtracts_its_own_area():
    """``E_z H_y`` is the other half of the integrand, with its own ``dA``."""
    grid, cc = _mesh()
    e = np.zeros(cc.n_edges)
    h = np.zeros(cc.n_faces)
    ez_view = e[cc.off_ez:cc.off_ez + cc.n_ez].reshape(cc.nxn, cc.nyn, cc.nz)
    ez_view[:] = grid.widths("z")[None, None, :]
    fy_view = h[cc.off_fy:cc.off_fy + cc.n_fy].reshape(cc.nx, cc.nyn, cc.nz)
    fy_view[:] = grid.dual_widths("y")[None, :, None]
    area = float(np.sum(grid.dual_widths("y")) * np.sum(grid.widths("z")))
    assert station_poynting(e, h, cc, 1) == pytest.approx(-area)


def test_the_z_slices_measure_their_own_part_of_the_stack():
    grid, cc = _mesh()
    e, h = _travelling_wave(grid, cc)
    whole = station_poynting(e, h, cc, 1)
    first = station_poynting(e, h, cc, 1, z_ey=slice(0, 1), z_ez=slice(0, 1))
    # nzn = nz + 1 = 3 layers, but NOT equal thirds: on a uniform grid the two
    # end dual layers are half cells, so the ratio here is
    # sum(dwz)/dwz[0] = 0.2/0.05 = 4, not 3.  The slice has to carry its own
    # width with it, or a sliced field would be weighted by the whole stack.
    assert whole == pytest.approx(
        float(np.sum(grid.dual_widths("z")) / grid.dual_widths("z")[0]) * first)
    assert first == pytest.approx(float(np.sum(grid.widths("y"))
                                       * grid.dual_widths("z")[0]))


def test_the_end_layers_are_legal_stations():
    grid, cc = _mesh()
    e, h = _travelling_wave(grid, cc)
    inner = station_poynting(e, h, cc, 1)
    for ix in (0, cc.nxn - 1):
        # A single straddling cell means no averaging, and the field is
        # uniform, so the end station reads exactly what an interior one does.
        assert station_poynting(e, h, cc, ix) == pytest.approx(inner)


def test_wrong_shapes_and_bad_stations_are_refused():
    grid, cc = _mesh()
    e, h = _travelling_wave(grid, cc)
    with pytest.raises(ValueError):
        station_poynting(e[:-1], h, cc, 1)
    with pytest.raises(ValueError):
        station_poynting(e, h[:-1], cc, 1)
    with pytest.raises(IndexError):
        station_poynting(e, h, cc, -1)
    with pytest.raises(IndexError):
        station_poynting(e, h, cc, cc.nxn)


# --------------------------------------------------------------------------- #
# the opt-in flag on the study
# --------------------------------------------------------------------------- #
KNOBS = dict(
    n_sub=1,
    n_air=1,
    n_strip=2,
    n_clean=1,
    n_pml=2,
    n_top=0,
    n_ref=1,
    n_line=6,
    x_first=6.4e-3,
    x_last=11.2e-3,
    n_stations=4,
    nsteps=40,
    sink=None,
)


def test_flag_off_keeps_the_fields_none_and_touches_nothing():
    """Off by default: the arrays are ``None`` and the record is unchanged."""
    off = studies.microstrip_wave(**KNOBS)
    on = studies.microstrip_wave(**KNOBS, poynting=True)

    assert off.geometry["poynting"] is False
    for name in ("sx_station", "sx_station_sub", "sx_station_first_half",
                 "sx_station_second_half", "sx_station_sub_first_half",
                 "sx_station_sub_second_half"):
        assert getattr(off, name) is None

    # The diagnostic is read-only: turning it on cannot move a reported number.
    assert np.array_equal(off.v_stations, on.v_stations)
    assert np.array_equal(off.i_stations, on.i_stations)
    assert off.beta == on.beta
    assert off.s21_planes == on.s21_planes
    assert np.array_equal(np.asarray(off.s21), np.asarray(on.s21))


def test_flag_on_reports_a_finite_flux_at_every_station():
    on = studies.microstrip_wave(**KNOBS, poynting=True)
    n = on.geometry["station_cells"]
    for name in ("sx_station", "sx_station_sub", "sx_station_first_half",
                 "sx_station_second_half", "sx_station_sub_first_half",
                 "sx_station_sub_second_half"):
        value = np.asarray(getattr(on, name), dtype=float)
        assert value.shape == (len(n),)
        assert np.all(np.isfinite(value))
    assert on.geometry["poynting"] is True
