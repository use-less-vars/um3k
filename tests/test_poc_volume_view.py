"""The whole-volume |E| view: one cell-centred image, built once per dump.

What is proven here is the PICTURE half of the volume work, and it is a
different kind of claim from the arrow field beside it (tests/test_poc_volume
_arrows.py): ``poc_app._volume_abs_grid`` is called directly with a hand-built
``info`` dict, so a failure points at the layer that failed rather than at a
rendered image nobody can inspect in this image.

The claims, one per test:

* the lattice is the dump's own ``(nx, ny, nz)`` with ``cell_mm`` spacing and the
  origin HALF A CELL in, because the volume's samples are cell CENTRES and not
  the corner of the box;
* ``e_abs`` is exactly ``sqrt(ex**2 + ey**2 + ez**2)`` for every cell, gathered
  by a monkeypatched ``emfit.operators.edge_to_cell_centres``, and its point
  order is FORTRAN (x fastest) - a C-ordered array of the same numbers would
  sample the field at the wrong cells;
* ``clim`` is ``(peak / 1000, peak)`` - 60 dB of the field above its own floor -
  and the call ``_draw_scene`` makes for it carries ``log_scale=True`` and a
  title that is not the plane stack's, so the two scales cannot be confused;
* the grid is MEMOISED on ``info``: the second reader gets the SAME image object
  and the colocation is paid once, which is what makes a per-slider-move redraw
  affordable at all;
* a dump with no volume draws the plane stack this page has always drawn - one
  ``add_volume``, ``scalars="ez_abs"``, ``|Ez| [V/m]`` - and the helper says why
  it drew nothing;
* a plotter that cannot draw a volume costs the VOLUME and nothing else: one
  ``[poc_app] |E| volume not drawn`` line, the outline/axes/board/markers/labels
  still drawn, no exception escaping ``_draw_scene``;
* a volume that is absent, zero everywhere or not finite is refused with a
  reason and never raises - and the reason never quotes a NaN back at the
  operator.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # The same two entries every other poc_app test adds, so `import poc_app`
        # resolves from server/poc_app.py.
        sys.path.insert(0, _p)

# pyvista lives in the repo's own venv in this image (its bin/python is broken,
# the site-packages tree is not). Inert where it is installed normally.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

import poc_app  # noqa: E402  (sys.path above is why this import is not at the top)

#: Sub-millimetre cells keep every coordinate in this file easy to read.
CELL_MM = 0.4


def _raw_info(nx, ny, nz, cell_m=CELL_MM * 1e-3):
    """A loader ``info`` that carries the RAW stash and nothing colocated."""
    return {
        "path": Path("hand-built.npz"),
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "cell_m": cell_m,
        poc_app.VOLUME_RAW_KEY: {
            "e": np.zeros(7),  # never read: the colocation is monkeypatched
            "nx": nx,
            "ny": ny,
            "nz": nz,
        },
    }


def _volume_info(volume, cell_m=CELL_MM * 1e-3):
    """A loader ``info`` that already carries the COLOCATED volume."""
    nx, ny, nz, _ = volume.shape
    return {
        "path": Path("hand-built.npz"),
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "cell_m": cell_m,
        poc_app.VOLUME_KEY: volume,
    }


def _index_volume(nx, ny, nz):
    """Three components whose every sample is distinguishable, x fastest."""
    def axis_component(offset):
        k = np.arange(nz)[None, None, :]
        j = np.arange(ny)[None, :, None]
        i = np.arange(nx)[:, None, None]
        return np.broadcast_to(offset + i + 10.0 * j + 100.0 * k, (nx, ny, nz)).astype(
            float
        )

    return np.stack(
        (axis_component(1.0), axis_component(2.0) / 7.0, axis_component(3.0) / 13.0),
        axis=-1,
    ).astype(float)


def _fake_colocator(calls, arrays):
    """Stand in for ``emfit.operators.edge_to_cell_centres``: count, then answer."""

    def _fake(e, nx, ny, nz):
        calls.append((np.asarray(e).shape, int(nx), int(ny), int(nz)))
        return arrays

    return _fake


# --- (a) the lattice ------------------------------------------------------


def test_the_lattice_is_the_dumps_own_dimensions_and_half_a_cell_in():
    """``(nx, ny, nz)`` x ``cell_mm``, origin at the first CELL CENTRE.

    WHY half a cell and not zero: ``edge_to_cell_centres`` averages every
    component onto a cell CENTRE, so the first sample belongs half a cell in from
    the corner of the box - the same anchor the arrow field is drawn at. An
    origin of 0 would put the whole field half a cell low on every axis, which no
    picture can show and no number here would catch.
    """
    nx, ny, nz = 3, 4, 2
    volume = _index_volume(nx, ny, nz)
    info = _volume_info(volume)

    image, meta = poc_app._volume_abs_grid(info, CELL_MM)

    assert meta["reason"] is None, f"the hand-built volume was refused: {meta}"
    assert image is not None
    assert tuple(image.dimensions) == (nx, ny, nz)
    assert tuple(image.spacing) == (CELL_MM, CELL_MM, CELL_MM)
    assert tuple(image.origin) == (0.5 * CELL_MM, 0.5 * CELL_MM, 0.5 * CELL_MM)
    # One sample per cell, and the count is the grid's product - not the raw
    # vector's length, which counts staggered EDGES and is a different number.
    assert meta["n"] == nx * ny * nz
    assert image.n_points == nx * ny * nz


# --- (b) the values, and their order --------------------------------------


def test_e_abs_is_the_root_sum_of_squares_of_the_three_components(monkeypatch):
    """Through the RAW route: the colocation is called, and its answer is used.

    ``emfit.operators.edge_to_cell_centres`` is monkeypatched, so what is proven
    here is that the helper SUMS THE SQUARES OF THE THREE COMPONENTS it is handed
    and not something else - a single component, a wrong axis, or the components
    of the neighbouring cell.
    """
    import emfit.operators

    nx, ny, nz = 3, 4, 2
    volume = _index_volume(nx, ny, nz)
    ex, ey, ez = volume[..., 0], volume[..., 1], volume[..., 2]
    calls = []
    monkeypatch.setattr(
        emfit.operators,
        "edge_to_cell_centres",
        _fake_colocator(calls, (ex, ey, ez)),
    )
    info = _raw_info(nx, ny, nz)

    image, meta = poc_app._volume_abs_grid(info, CELL_MM)

    assert meta["reason"] is None, f"the hand-built volume was refused: {meta}"
    assert len(calls) == 1, "the colocation was called once and the answer reused"
    expected = np.sqrt(ex * ex + ey * ey + ez * ez)
    got = np.asarray(image.point_data["e_abs"])
    assert got.shape == (nx * ny * nz,)
    assert np.allclose(got, expected.ravel(order="F"), rtol=0.0, atol=1e-12)


def test_the_point_order_is_fortran_so_x_varies_fastest():
    """x fastest, then y, then z: the order ``ImageData`` fills its points in.

    A C-ordered flattening holds the SAME numbers in a different arrangement, so
    a test that only compared the set of values would pass while the picture
    sampled the field at the wrong cells. The two orders are therefore compared
    with each other as well as with the image.
    """
    nx, ny, nz = 3, 4, 2
    ex = _index_volume(nx, ny, nz)[..., 0]
    volume = np.stack((ex, np.zeros_like(ex), np.zeros_like(ex)), axis=-1)
    info = _volume_info(volume)

    image, meta = poc_app._volume_abs_grid(info, CELL_MM)

    assert meta["reason"] is None, f"the hand-built volume was refused: {meta}"
    got = np.asarray(image.point_data["e_abs"])
    fortran = ex.ravel(order="F")
    c_order = ex.ravel(order="C")
    assert not np.array_equal(fortran, c_order), (
        "the fixture cannot tell the two orders apart, so this test proves nothing"
    )
    assert np.array_equal(got, fortran)
    # The first point is the (0, 0, 0) cell and the second is (1, 0, 0): one
    # step along x, not one step along z.
    assert got[0] == ex[0, 0, 0]
    assert got[1] == ex[1, 0, 0]


# --- (c) clim and the drawn call ------------------------------------------


def test_clim_is_sixty_decibels_below_the_peak():
    """``(peak / 1000, peak)``: three decades, measured on the volume itself."""
    nx, ny, nz = 2, 2, 2
    volume = np.zeros((nx, ny, nz, 3))
    volume[..., 0] = 40.0  # |E| == 40 everywhere
    volume[0, 0, 0, 0] = 3.0 * 40.0  # one sample six times the rest: the peak
    info = _volume_info(volume)

    image, meta = poc_app._volume_abs_grid(info, CELL_MM)

    assert meta["reason"] is None
    peak = 120.0
    assert meta["clim"] == (peak / 1000.0, peak)
    assert np.isclose(float(np.max(image.point_data["e_abs"])), peak)


class _ScenePlotter:
    """Records what ``_draw_scene`` asks for. No VTK, no GL, no display."""

    def __init__(self):
        self.calls = []

    def clear(self):
        self.calls.append("clear")

    def add_mesh(self, mesh, **kwargs):
        self.calls.append(("add_mesh", kwargs))
        return object()

    def add_volume(self, mesh, **kwargs):
        self.calls.append(("add_volume", mesh, kwargs))
        return object()

    def add_axes(self, **kwargs):
        self.calls.append("add_axes")

    def add_text(self, text, **kwargs):
        self.calls.append(("add_text", kwargs.get("name")))

    def view_isometric(self):
        self.calls.append("view_isometric")

    def reset_camera(self):
        self.calls.append("reset_camera")

    def volumes(self):
        return [call for call in self.calls if call[0] == "add_volume"]

    def names(self):
        return [call[1] for call in self.calls if call[0] == "add_text"]


class _NoVolumePlotter(_ScenePlotter):
    """A plotter with no ``add_volume`` at all: pyvista older than volumes."""

    def add_volume(self, mesh, **kwargs):  # noqa: D401 - deliberately absent
        raise AssertionError("this plotter is supposed to have no add_volume")


class _VolumeRefusingPlotter(_ScenePlotter):
    """A plotter that HAS ``add_volume`` and refuses every call to it."""

    def add_volume(self, mesh, **kwargs):
        self.calls.append(("add_volume_refused", kwargs))
        raise AttributeError("no volume actor in this plotter")


def _planes(n_st=4):
    """The ``planes`` dict, trimmed to the keys ``_draw_scene`` reads."""
    return {
        "cell_mm": CELL_MM,
        "n_st": n_st,
        "stations_mm": [i * CELL_MM for i in range(n_st)],
        "x_load_mm": 4.0,
        "src_load": "FALLBACK",
        "ix_load": None,
        "x_s11_mm": 0.0,
        "src_s11": "record",
        "x_s21_mm": 1.6,
        "src_s21": "FALLBACK",
        "s21_valid": False,
        "s21_valid_src": "FALLBACK",
        "s21_reason": "no record",
        "slice_index": 0,
    }


def _stub_scene(monkeypatch, sheet_calls=None):
    """Every collaborator of ``_draw_scene`` that is not under test, stubbed.

    ``_draw_scene`` owns the plotter; these stubs own everything else, so a
    failure here points at the volume call and not at the board or the cut
    sheets. The ``build_grid`` stub still hands back an ``outline()``, because
    the plane-stack branch is drawn onto that same grid.
    """
    outline = object()
    monkeypatch.setattr(
        poc_app,
        "build_grid",
        lambda _info, _stations_mm=None: types.SimpleNamespace(outline=lambda: outline),
    )
    monkeypatch.setattr(
        poc_app,
        "_cut_layout",
        lambda _info, j, k, _stations_mm=None: {
            "y_mm": 0.0, "j": 0, "n_j": 1,
            "z_mm": 0.0, "k": 0, "n_k": 1,
        },
    )

    def _sheets(_info, _layout):
        if sheet_calls is not None:
            sheet_calls.append("sheets")
        return []

    monkeypatch.setattr(poc_app, "build_cut_sheets", _sheets)
    monkeypatch.setattr(poc_app, "_vis_geometry", lambda p, i, pl: None)
    monkeypatch.setattr(poc_app, "_add_markers", lambda p, i, pl: None)
    monkeypatch.setattr(poc_app, "_marker_cut_lines", lambda pl, cl, drawn, vm: {})
    monkeypatch.setattr(poc_app, "_marker_text", lambda pl, cuts: "legend")
    monkeypatch.setattr(poc_app, "_station_text", lambda *a, **k: "station")
    return outline


def _drive_volume_scene(monkeypatch, plotter, info, n_st=4):
    """``_draw_scene`` in VOLUME mode against stubs.

    Returns the ``info`` dict the scene was actually handed: ``_draw_scene`` gets
    a copy of the caller's, so the memo it adds lands in the copy and this is how
    a test can see it.
    """
    _stub_scene(monkeypatch)
    passed = dict(info)
    passed.setdefault(
        poc_app.PLANE_KEY, np.ones((n_st, 4, 5), dtype=complex)
    )
    poc_app._draw_scene(plotter, passed, _planes(n_st), "volume", 0)
    return passed


def test_the_scene_draws_the_volume_log_scaled_with_its_own_title(monkeypatch):
    """One ``add_volume``, on ``e_abs``, log-scaled, titled as |E| and not |Ez|.

    WHY the title matters: the FFT normalisation makes the colocated volume
    ~2053x smaller in V/m than the captured |Ez| planes, so a bar titled
    ``|Ez| [V/m]`` over these numbers would be read as the other field's scale.
    WHY log: the field spans tens of decades down into round-off, so a linear bar
    would show the peak and nothing else.
    """
    nx, ny, nz = 3, 4, 2
    volume = _index_volume(nx, ny, nz)
    info = _volume_info(volume)
    plotter = _ScenePlotter()

    passed = _drive_volume_scene(monkeypatch, plotter, info)

    volumes = plotter.volumes()
    assert len(volumes) == 1, (
        f"expected exactly one volume actor, got {[v[2] for v in volumes]}"
    )
    _, mesh, kwargs = volumes[0]
    assert kwargs["scalars"] == "e_abs"
    assert kwargs["cmap"] == "turbo"
    assert kwargs["log_scale"] is True
    peak = float(np.max(np.sqrt(volume[..., 0] ** 2 + volume[..., 1] ** 2 + volume[..., 2] ** 2)))
    # ``approx``: the closed values agree to the last bit or two, and the CLAIM
    # here is the 60 dB ratio, not a floating-point summation order.
    assert kwargs["clim"][0] == pytest.approx(peak / 1000.0, rel=1e-12)
    assert kwargs["clim"][1] == pytest.approx(peak, rel=1e-12)
    title = kwargs["scalar_bar_args"]["title"]
    assert title == "|E| [V/m] (log)"
    assert title != "|Ez| [V/m]"
    # The mesh handed over IS the memoised image, not a second build.
    assert mesh is passed[poc_app.VOLUME_ABS_KEY]["image"]
    assert tuple(mesh.dimensions) == (nx, ny, nz)
    # The old plane stack was NOT drawn as well: two volumes over one slab would
    # occlude each other.
    assert not any(
        call[2]["scalars"] == "ez_abs" for call in volumes
    ), "the plane stack was drawn on top of the |E| volume"


# --- (d) the memo ---------------------------------------------------------


def test_the_grid_is_built_once_and_the_second_reader_gets_the_same_image(
    monkeypatch,
):
    """Two reads, ONE colocation, the SAME object: a redraw is not a rebuild.

    WHY this is not an optimisation detail: ``_redraw_scene`` rebuilds the whole
    scene on every cut or station move, so a per-redraw colocation would be a
    per-move second - and the failure would look like a slow page, never like a
    bug.
    """
    import emfit.operators

    nx, ny, nz = 3, 4, 2
    volume = _index_volume(nx, ny, nz)
    calls = []
    monkeypatch.setattr(
        emfit.operators,
        "edge_to_cell_centres",
        _fake_colocator(calls, (volume[..., 0], volume[..., 1], volume[..., 2])),
    )
    info = _raw_info(nx, ny, nz)

    first, first_meta = poc_app._volume_abs_grid(info, CELL_MM)
    cache = info[poc_app.VOLUME_ABS_KEY]
    second, second_meta = poc_app._volume_abs_grid(info, CELL_MM)

    assert len(calls) == 1, f"the colocation was paid twice: {calls}"
    assert first is second, "the second reader got a different image"
    assert first_meta["clim"] == second_meta["clim"]
    assert second_meta["reason"] is None
    # ADD-ONLY: the entry is one dict, set once and never rewritten.
    assert info[poc_app.VOLUME_ABS_KEY] is cache
    assert set(cache) == {"image", "clim", "n"}


# --- (e) no volume: the picture this page always drew ---------------------


def test_a_dump_with_no_volume_draws_the_plane_stack_it_always_drew(monkeypatch):
    """No ``e_centres`` and no ``e_raw``: one ``|Ez|`` volume, unchanged.

    The helper must SAY why it drew nothing - an operator reading stderr has to
    be able to tell "this dump has no volume" from "the volume path broke".
    """
    info = {"nx": 3, "ny": 4, "nz": 2, "cell_m": CELL_MM * 1e-3}

    image, meta = poc_app._volume_abs_grid(info, CELL_MM)

    assert image is None
    assert meta["reason"] == "no volume in this dump"
    assert meta["clim"] is None
    assert meta["n"] == 0
    # Nothing was cached for a miss: the next reader must try again, and an
    # info dict that gains a volume later must still draw it.
    assert poc_app.VOLUME_ABS_KEY not in info

    plotter = _ScenePlotter()
    _drive_volume_scene(monkeypatch, plotter, info)

    volumes = plotter.volumes()
    assert len(volumes) == 1, f"expected the plane stack alone, got {volumes}"
    _, mesh, kwargs = volumes[0]
    assert kwargs["scalars"] == "ez_abs"
    assert kwargs["cmap"] == "turbo"
    assert kwargs["scalar_bar_args"] == {"title": "|Ez| [V/m]"}
    assert "log_scale" not in kwargs
    # The grid built for the outline is the one the plane stack was drawn on.
    assert mesh is not None


# --- (f) a plotter that cannot draw a volume ------------------------------


def test_a_plotter_without_add_volume_costs_the_volume_and_nothing_else(
    monkeypatch, capsys
):
    """ONE ``|E| volume not drawn`` line; the rest of the scene still happens.

    The exception must not escape: everything drawn after this branch - the
    outline, the axes, the board, the markers and both corner labels - would go
    with it, and ``_redraw_scene`` would swallow the whole picture instead.
    """
    nx, ny, nz = 3, 4, 2
    info = _volume_info(_index_volume(nx, ny, nz))
    plotter = _NoVolumePlotter()

    _drive_volume_scene(monkeypatch, plotter, info)

    err = capsys.readouterr().err
    assert err.count("[poc_app] |E| volume not drawn:") == 1, (
        f"expected one |E| line, got {err!r}"
    )
    # Everything after the volume branch ran, in order.
    assert any(call[0] == "add_mesh" for call in plotter.calls), (
        f"the outline was not drawn: {plotter.calls}"
    )
    assert "add_axes" in plotter.calls
    assert ("add_text", "station_label") in plotter.calls
    assert ("add_text", "marker_legend") in plotter.calls
    assert "view_isometric" in plotter.calls
    assert "reset_camera" in plotter.calls


def test_a_plotter_that_refuses_volumes_falls_back_to_the_plane_stack(
    monkeypatch, capsys
):
    """The fallback is attempted exactly once and its failure is also reported.

    A plotter that HAS ``add_volume`` and raises from it is the case an older
    pyvista or a dead GL context produces: the |E| call fails, the plane stack is
    tried as the fallback, and ITS failure is a second, differently-worded line -
    so a reader can still tell which of the two pictures was refused.
    """
    nx, ny, nz = 3, 4, 2
    info = _volume_info(_index_volume(nx, ny, nz))
    plotter = _VolumeRefusingPlotter()

    _drive_volume_scene(monkeypatch, plotter, info)

    err = capsys.readouterr().err
    assert err.count("[poc_app] |E| volume not drawn:") == 1, (
        f"expected one |E| line, got {err!r}"
    )
    assert err.count("[poc_app] |Ez| volume not drawn:") == 1, (
        f"expected one fallback line, got {err!r}"
    )
    assert "add_axes" in plotter.calls
    assert ("add_text", "marker_legend") in plotter.calls


# --- (g) unusable volumes -------------------------------------------------


@pytest.mark.parametrize(
    "volume, expected_reason",
    [
        (np.zeros((3, 4, 2, 3)), "the volume is zero everywhere"),
        (
            np.full((3, 4, 2, 3), np.nan),
            "the volume has samples that are not finite",
        ),
        (
            np.ones((3, 4, 2, 2)),
            "the volume is not an (nx, ny, nz, 3) array",
        ),
    ],
)
def test_an_unusable_volume_is_refused_with_a_reason_and_never_raises(
    volume, expected_reason
):
    """Absent, zero, non-finite, wrong width: ``(None, reason)``, never a raise.

    WHY the reason must not quote the NaN back: the sentence goes to an
    operator's terminal next to real numbers, and ``nan`` in a message reads as a
    value the field had rather than as a field that was refused.
    """
    info = _volume_info(volume)

    image, meta = poc_app._volume_abs_grid(info, CELL_MM)

    assert image is None
    assert meta["reason"] == expected_reason
    assert meta["clim"] is None
    assert "nan" not in meta["reason"].lower(), (
        f"the refusal quotes a NaN at the operator: {meta['reason']!r}"
    )
    assert poc_app.VOLUME_ABS_KEY not in info, "a refusal must not be cached"


def test_a_raw_stash_with_no_e_vector_is_a_miss_not_a_crash():
    """``e_raw`` present but empty is the same answer as no volume at all."""
    info = {
        "nx": 3,
        "ny": 4,
        "nz": 2,
        "cell_m": CELL_MM * 1e-3,
        poc_app.VOLUME_RAW_KEY: {"e": None, "nx": 3, "ny": 4, "nz": 2},
    }

    image, meta = poc_app._volume_abs_grid(info, CELL_MM)

    assert image is None
    assert meta["reason"] == "no volume in this dump"


def test_a_volume_with_no_grid_is_refused_rather_than_guessed():
    """No ``nx``/``ny``/``nz`` anywhere: refused, because a guess would MOVE it.

    The cell counts are never taken from ``e.size``: the raw vector is staggered,
    so its length counts edges, and deriving a shape from it would draw the field
    on a lattice the solve never used.
    """
    volume = np.ones((2, 2, 2, 3))
    info = {poc_app.VOLUME_KEY: volume, "cell_m": CELL_MM * 1e-3}

    image, meta = poc_app._volume_abs_grid(info, CELL_MM)

    assert image is None
    assert meta["reason"] == "no (nx,ny,nz) for the volume"

    # The record's ``geometry.grid`` is the backup, and it is honoured when the
    # dump's own metadata cannot answer.
    image, meta = poc_app._volume_abs_grid(info, CELL_MM, grid_hint=(2, 2, 2))
    assert meta["reason"] is None, f"the grid hint was ignored: {meta}"
    assert tuple(image.dimensions) == (2, 2, 2)


# --- (h) the y / z cut sliders slice the |E| volume ------------------------
# The sliders used to index the captured plane stack unconditionally, so on a
# dump that carries a colocated volume they cut a DIFFERENT lattice from the one
# the volume beside them is drawn on. These tests pin the retarget: the volume
# when there is one, and the plane stack - byte for byte as before - when there
# is not.

#: The two collaborators under test in the scene test below, captured BEFORE any
#: ``_stub_scene`` replaces them, so the scene test can put the real ones back.
_REAL_CUT_LAYOUT = poc_app._cut_layout
_REAL_BUILD_CUT_SHEETS = poc_app.build_cut_sheets


def test_the_cut_layout_indexes_the_volumes_own_lattice_when_there_is_one():
    """``source == "volume"``: ``(j, k)`` index ``(ny, nz)``, half a cell in.

    WHY half a cell and why the volume's x extent: the volume's samples are cell
    CENTRES, so a cut quoted at ``j * cell`` would name the cell CORNER, half a
    cell upstream of the field the volume draws - and the sheets would span the
    captured slab instead of the volume they are cut from.
    """
    nx, ny, nz = 3, 4, 2
    info = _volume_info(_index_volume(nx, ny, nz))

    layout = poc_app._cut_layout(info)

    assert layout["source"] == "volume"
    assert (layout["n_j"], layout["n_k"]) == (ny, nz)
    # The default is the middle sample of the VOLUME, not of the plane stack.
    assert (layout["j"], layout["k"]) == (ny // 2, nz // 2) == (2, 1)
    assert layout["n_st"] == nx
    assert layout["y_mm"] == pytest.approx((2 + 0.5) * CELL_MM)
    assert layout["z_mm"] == pytest.approx((1 + 0.5) * CELL_MM)
    assert layout["x_lo_mm"] == pytest.approx(0.5 * CELL_MM)
    assert layout["x_hi_mm"] == pytest.approx((nx - 0.5) * CELL_MM)
    assert layout["dx_mm"] == pytest.approx(CELL_MM)
    # The sliders span the volume's samples, not the plane stack's 12 x 5.
    assert poc_app._cut_axis_counts(info, 12, 5) == (ny, nz)


def test_the_cut_label_says_which_grid_its_millimetres_are_on():
    """The volume row APPENDS the grid; the plane row is unchanged to the byte."""
    info = _volume_info(_index_volume(3, 4, 2))

    text = poc_app._cut_text(poc_app._cut_layout(info, 2, 1))

    assert "y = 1.0000 mm" in text, f"the volume cut is not quoted at the cell centre: {text!r}"
    assert "z = 0.6000 mm" in text, text
    assert "|E| volume cells, cell centres" in text, (
        f"the row does not say which lattice the millimetres are on: {text!r}"
    )

    plane_info = {
        "cell_m": CELL_MM * 1e-3,
        poc_app.PLANE_KEY: np.ones((2, 4, 5), dtype=complex),
    }
    plane_text = poc_app._cut_text(poc_app._cut_layout(plane_info, 1, 3))
    assert plane_text == (
        "cut y = 2/4 (y = 0.4000 mm)   cut z = 4/5 (z = 1.2000 mm)   "
        "one sample each, no interpolation"
    ), f"the plane row changed: {plane_text!r}"


def test_the_cut_sheets_are_subsets_of_the_volume_image():
    """One sample thick, cell-centred, carrying ``e_abs`` from the parent image.

    The values are compared against the field itself, so a transposed extent or a
    Fortran/C mix-up is caught rather than a merely well-formed mesh.
    """
    nx, ny, nz = 3, 4, 2
    volume = _index_volume(nx, ny, nz)
    ex, ey, ez = volume[..., 0], volume[..., 1], volume[..., 2]
    e_abs = np.sqrt(ex * ex + ey * ey + ez * ez)
    info = _volume_info(volume)
    j, k = 2, 1

    sheets = dict(poc_app.build_cut_sheets(info, poc_app._cut_layout(info, j, k)))

    assert sorted(sheets) == ["y", "z"]
    y_sheet, z_sheet = sheets["y"], sheets["z"]
    assert tuple(y_sheet.dimensions) == (nx, 1, nz)
    assert tuple(y_sheet.spacing) == pytest.approx((CELL_MM, CELL_MM, CELL_MM))
    assert tuple(y_sheet.origin) == pytest.approx(
        (0.5 * CELL_MM, (j + 0.5) * CELL_MM, 0.5 * CELL_MM)
    )
    assert tuple(z_sheet.dimensions) == (nx, ny, 1)
    assert tuple(z_sheet.origin) == pytest.approx(
        (0.5 * CELL_MM, 0.5 * CELL_MM, (k + 0.5) * CELL_MM)
    )
    for sheet in (y_sheet, z_sheet):
        assert "e_abs" in sheet.point_data.keys(), (
            f"the sheet carries {list(sheet.point_data.keys())}, not the volume's e_abs"
        )
        assert "ez_abs" not in sheet.point_data.keys()
    # x fastest: the y sheet is the (i, k) plane at j, the z sheet the (i, j)
    # plane at k.
    assert np.allclose(
        np.asarray(y_sheet.point_data["e_abs"]), e_abs[:, j, :].ravel(order="F")
    )
    assert np.allclose(
        np.asarray(z_sheet.point_data["e_abs"]), e_abs[:, :, k].ravel(order="F")
    )


def test_a_dump_with_no_volume_keeps_the_plane_stack_sheets():
    """The fallback: ``(n_j, n_k)`` of the PLANE, ``j * cell``, ``ez_abs``.

    The ``nx`` / ``ny`` / ``nz`` keys are present and deliberately WRONG for the
    plane stack (3 x 4 x 2 against a 2 x 4 x 5 plane): the loader publishes them
    beside every dump's raw stash, so a predicate that read them alone would
    retarget the sliders onto a grid that carries no field.
    """
    info = {
        "path": Path("hand-built.npz"),
        "nx": 3,
        "ny": 4,
        "nz": 2,
        "cell_m": CELL_MM * 1e-3,
        poc_app.PLANE_KEY: np.ones((2, 4, 5), dtype=complex),
    }

    layout = poc_app._cut_layout(info, 1, 3)

    assert layout["source"] == "planes", (
        f"the cell-count keys alone retargeted the cuts onto an absent volume: {layout}"
    )
    assert (layout["n_j"], layout["n_k"]) == (4, 5)
    assert (layout["j"], layout["k"]) == (1, 3)
    assert layout["y_mm"] == pytest.approx(1 * CELL_MM), (
        "the plane cut moved off the cell corner it has always been quoted at"
    )
    assert layout["z_mm"] == pytest.approx(3 * CELL_MM)
    assert poc_app._cut_axis_counts(info, 4, 5) == (4, 5)

    sheets = dict(poc_app.build_cut_sheets(info, layout))
    assert tuple(sheets["y"].dimensions) == (2, 1, 5)
    assert tuple(sheets["z"].dimensions) == (2, 4, 1)
    for sheet in sheets.values():
        assert "ez_abs" in sheet.point_data.keys()
        assert "e_abs" not in sheet.point_data.keys()
    assert "volume" not in poc_app._cut_text(layout)


def test_the_cut_sliders_span_the_volumes_own_samples():
    """``max`` is the volume's last cell; the passed plane counts are ignored.

    A slider that cannot reach the last volume cell would let the row report a
    cut that is not where the sheet is actually drawn - and, worse, the clamp in
    ``_on_cut_change`` would refuse a reachable sample.
    """
    info = _volume_info(_index_volume(3, 4, 2))
    calls = []
    widgets = {}

    def _record(name):
        def _call(*args, **kwargs):
            calls.append((name, args, kwargs))

        return _call

    for name in ("VLabel", "VSlider"):
        widgets[name] = _record(name)

    poc_app._emit_cut_sliders(
        [],
        None,
        lambda *a, **k: None,
        widgets,
        types.SimpleNamespace(cut_y=2, cut_z=1),
        12,  # the plane-stack fallback counts, which must NOT be used here
        5,
        info,
    )

    sliders = [kwargs for name, _args, kwargs in calls if name == "VSlider"]
    assert len(sliders) == 2, f"the row built {[c[0] for c in calls]!r}"
    assert (sliders[0]["min"], sliders[0]["max"], sliders[0]["step"]) == (0, 3, 1), (
        f"the y slider does not span the volume's ny = 4 cells: {sliders[0]!r}"
    )
    assert (sliders[1]["min"], sliders[1]["max"], sliders[1]["step"]) == (0, 1, 1), (
        f"the z slider does not span the volume's nz = 2 cells: {sliders[1]!r}"
    )
    assert sliders[0]["v_model"] == ("cut_y", 2)
    assert sliders[1]["v_model"] == ("cut_z", 1)


class _SheetPlotter(_ScenePlotter):
    """``_ScenePlotter`` that also keeps the mesh each ``add_mesh`` was handed."""

    def __init__(self):
        super().__init__()
        self.meshes = []

    def add_mesh(self, mesh, **kwargs):
        self.meshes.append((mesh, kwargs))
        return super().add_mesh(mesh, **kwargs)


def test_the_volume_cut_sheets_are_drawn_on_the_volumes_own_colour_scale(
    monkeypatch,
):
    """Two ``add_mesh`` calls, ``scalars="e_abs"``, log-scaled on the volume's clim.

    WHY the scale matters: the sheets are drawn from the volume's samples, and a
    linear bar over |E| would show the peak and nothing else - while a second bar
    over the same field would be the same numbers twice, hence
    ``show_scalar_bar=False``.

    The real ``_cut_layout`` and ``build_cut_sheets`` are put back after
    ``_stub_scene``: the stubs exist to keep the rest of the scene out of the way,
    not to fake the sheets under test.
    """
    nx, ny, nz = 3, 4, 2
    info = _volume_info(_index_volume(nx, ny, nz))
    plotter = _SheetPlotter()

    _stub_scene(monkeypatch)
    monkeypatch.setattr(poc_app, "_cut_layout", _REAL_CUT_LAYOUT)
    monkeypatch.setattr(poc_app, "build_cut_sheets", _REAL_BUILD_CUT_SHEETS)
    passed = dict(info)
    passed[poc_app.PLANE_KEY] = np.ones((4, 4, 5), dtype=complex)

    poc_app._draw_scene(plotter, passed, _planes(4), "volume", 0)

    cuts = [(mesh, kwargs) for mesh, kwargs in plotter.meshes if "scalars" in kwargs]
    assert len(cuts) == 2, (
        "expected the two cut sheets, got "
        f"{[kwargs.get('scalars') for _m, kwargs in plotter.meshes]}"
    )
    assert [tuple(mesh.dimensions) for mesh, _k in cuts] == [
        (nx, 1, nz),
        (nx, ny, 1),
    ], "the sheets are not the volume's y and z slices"
    clim = passed[poc_app.VOLUME_ABS_KEY]["clim"]
    for mesh, kwargs in cuts:
        assert kwargs["scalars"] == "e_abs", (
            f"a cut sheet was drawn on {kwargs['scalars']!r}, not the volume's field"
        )
        assert kwargs["cmap"] == "turbo"
        assert kwargs["opacity"] == 0.75
        assert kwargs["show_scalar_bar"] is False, (
            "a second colour bar appeared over the same field"
        )
        assert kwargs["log_scale"] is True, (
            "a linear |E| sheet shows the peak and nothing else"
        )
        assert kwargs["clim"] == clim, (
            f"the sheet's range {kwargs['clim']!r} is not the volume's {clim!r}"
        )
        # The sheet is a SUBSET of the volume image: same parent field object
        # values, no second colocation paid.
        assert "e_abs" in mesh.point_data.keys()



# --- (i) the cut sheets are FRAMED ----------------------------------------
# A sheet one sample thick has no flank for the light to fall on, so on its own
# it shows colour with no visible extent: the reader cannot tell where the cut
# stops. The port plane has drawn its own outline for that reason; these tests
# pin that the cuts do the same, from their OWN bounds, with the port plane's
# styling - and that the extra edge costs no draw.


def _port_edge(monkeypatch):
    """The port plane's framing kwargs, read off a DRIVEN port scene.

    WHY derived rather than restated: the cut edges must be the same framing the
    port sheet already draws, and a literal copy of the dict in this file could
    drift away from it without a single test going red.
    """
    plotter = _SheetPlotter()
    _stub_scene(monkeypatch)
    passed = {poc_app.PLANE_KEY: np.ones((4, 4, 5), dtype=complex)}

    poc_app._draw_scene(plotter, passed, _planes(4), "port", 0)

    sheets = [i for i, (_m, k) in enumerate(plotter.meshes) if "scalars" in k]
    assert len(sheets) == 1, (
        "expected the one port sheet, got "
        f"{[k.get('scalars') for _m, k in plotter.meshes]}"
    )
    index = sheets[0]
    assert index + 1 < len(plotter.meshes), (
        "the port sheet is drawn with no edge after it, so there is no styling "
        "to compare the cuts against"
    )
    return plotter.meshes[index + 1][1]


def _volume_scene_meshes(monkeypatch, info):
    """``_draw_scene`` in VOLUME mode, real cut layout and real sheet builder.

    The stubs exist to keep the rest of the scene out of the way, not to fake
    the sheets under test - hence the two collaborators put back after
    ``_stub_scene``. Returns the ordered ``(mesh, kwargs)`` of every ``add_mesh``.
    """
    plotter = _SheetPlotter()
    _stub_scene(monkeypatch)
    monkeypatch.setattr(poc_app, "_cut_layout", _REAL_CUT_LAYOUT)
    monkeypatch.setattr(poc_app, "build_cut_sheets", _REAL_BUILD_CUT_SHEETS)
    passed = dict(info)
    passed.setdefault(poc_app.PLANE_KEY, np.ones((4, 4, 5), dtype=complex))

    poc_app._draw_scene(plotter, passed, _planes(4), "volume", 0)
    return plotter.meshes


def _sheets_and_followers(meshes):
    """Every ``add_mesh`` carrying ``scalars``, with whatever came NEXT.

    "Next" and not "somewhere later": the edge is only framable by the reader if
    it is the call immediately after its own sheet.
    """
    pairs = []
    for index, (mesh, kwargs) in enumerate(meshes):
        if "scalars" not in kwargs:
            continue
        follower = meshes[index + 1] if index + 1 < len(meshes) else None
        pairs.append((mesh, kwargs, follower))
    return pairs


def test_every_cut_sheet_is_framed_with_its_own_outline(monkeypatch):
    """Each volume cut sheet is followed by ITS OWN outline, in the port styling.

    WHY the sheet's own ``outline()``: a rectangle rebuilt here would have to
    restate the origin, the spacing and the sample counts, and could then
    disagree with the field pyvista actually drew - the one failure this page
    cannot show. ``outline()`` is derived from the mesh, so the bounds match by
    construction (measured on this (3,1,2) / (3,4,1) pair: 8 points, 12 line
    cells, bounds equal to the sheet's to single precision - VTK keeps an
    outline's points as float32).

    WHY the port plane's kwargs: that framing is already on screen in the other
    view, and two of them in one page would be an inconsistency a reader has to
    explain. Read off a driven port scene, never restated as literals.
    """
    nx, ny, nz = 3, 4, 2
    info = _volume_info(_index_volume(nx, ny, nz))
    port_kwargs = _port_edge(monkeypatch)

    meshes = _volume_scene_meshes(monkeypatch, info)
    sheets = _sheets_and_followers(meshes)

    assert len(sheets) == 2, (
        "expected the two volume cut sheets, got "
        f"{[k.get('scalars') for _m, k in meshes]}"
    )
    for mesh, kwargs, follower in sheets:
        assert follower is not None, (
            f"the {kwargs['scalars']} cut sheet is drawn with no edge after it: "
            "a one-sample sheet shows colour with no extent"
        )
        edge_mesh, edge_kwargs = follower
        assert edge_kwargs == port_kwargs, (
            f"the cut edge is styled {edge_kwargs!r}, not the port plane's "
            f"{port_kwargs!r}"
        )
        # ``approx``: the sheet's bounds are double precision, the outline's
        # points are float32 (VTK's default point precision), so the two agree
        # to single precision - measured 0.2 vs 0.20000000298023224 on this
        # sub-millimetre cell. The claim is WHICH box is framed, not a bit.
        assert tuple(edge_mesh.bounds) == pytest.approx(
            tuple(mesh.bounds), rel=1e-6
        ), (
            f"the edge frames {tuple(edge_mesh.bounds)}, not the sheet it "
            f"belongs to {tuple(mesh.bounds)}"
        )


def test_the_plane_fallback_cuts_are_framed_the_same_way(monkeypatch):
    """No volume: the two ``ez_abs`` sheets get the same edge, from their own outline.

    WHY every cut and not only the volume ones: thinness is a property of BOTH
    sources - a plane sheet is one captured sample thick too, and it is the
    picture this page drew before the volume existed - so an unframed fallback
    sheet would be exactly the smear the port plane was given an edge to avoid.

    The dump carries ``nx`` / ``ny`` / ``nz`` deliberately WRONG for the plane
    stack (3 x 4 x 2 against a 2 x 4 x 5 plane), as the loader publishes them
    beside every raw stash; the cuts must still be the plane ones.
    """
    port_kwargs = _port_edge(monkeypatch)
    info = {
        "path": Path("hand-built.npz"),
        "nx": 3,
        "ny": 4,
        "nz": 2,
        "cell_m": CELL_MM * 1e-3,
        poc_app.PLANE_KEY: np.ones((2, 4, 5), dtype=complex),
    }

    meshes = _volume_scene_meshes(monkeypatch, info)
    sheets = _sheets_and_followers(meshes)

    assert [kwargs.get("scalars") for _m, kwargs, _f in sheets] == [
        "ez_abs",
        "ez_abs",
    ], f"the cuts are not the plane stack's: {[k for _m, k, _f in sheets]}"
    assert [tuple(mesh.dimensions) for mesh, _k, _f in sheets] == [
        (2, 1, 5),
        (2, 4, 1),
    ], "the sheets are not the plane stack's y and z slices"
    for mesh, kwargs, follower in sheets:
        assert follower is not None, (
            f"the {kwargs['scalars']} fallback sheet is drawn with no edge after it"
        )
        edge_mesh, edge_kwargs = follower
        assert edge_kwargs == port_kwargs, (
            f"the fallback edge is styled {edge_kwargs!r}, not the port plane's "
            f"{port_kwargs!r}"
        )
        # ``approx`` for the same single-precision reason as the volume case.
        assert tuple(edge_mesh.bounds) == pytest.approx(
            tuple(mesh.bounds), rel=1e-6
        ), (
            f"the edge frames {tuple(edge_mesh.bounds)}, not the sheet it "
            f"belongs to {tuple(mesh.bounds)}"
        )


def test_a_cut_redraw_adds_no_render_for_the_edges(monkeypatch):
    """FOUR ``add_mesh`` calls for the cuts: two sheets and two edges, in order.

    WHY the count matters: ``render=False`` on each edge - the keyword the port
    plane already uses - is what keeps an edge from flushing a draw of a picture
    that is still being built, so the common tail's one render is still the only
    draw of a rebuild. That is why ``_CUT_REDRAW_RENDERS`` in
    tests/test_poc_playback.py stays 9 and must never be relaxed to ``>= 1``.

    A count of four also catches the OTHER failure: an edge that quietly stopped
    being drawn would leave two calls and a picture with no extents, and every
    assertion about the edge's styling would still pass on the sheet's.
    """
    nx, ny, nz = 3, 4, 2
    info = _volume_info(_index_volume(nx, ny, nz))

    meshes = _volume_scene_meshes(monkeypatch, info)
    # The cut block is everything before the scene's grid outline, which is the
    # one ``add_mesh`` drawn at line_width 1; the volume itself is an
    # ``add_volume`` and so is not in this list at all.
    cut_calls = []
    for _mesh, kwargs in meshes:
        if kwargs.get("line_width") == 1:
            break
        cut_calls.append(kwargs)

    assert len(cut_calls) == 4, (
        f"the cut block made {len(cut_calls)} add_mesh calls "
        f"({[sorted(k) for k in cut_calls]}), not two sheets and two edges"
    )
    assert ["scalars" in kwargs for kwargs in cut_calls] == [
        True,
        False,
        True,
        False,
    ], (
        "the edges are not each drawn immediately after their own sheet: "
        f"{[sorted(k) for k in cut_calls]}"
    )
    for kwargs in (cut_calls[1], cut_calls[3]):
        assert kwargs["render"] is False, (
            f"the edge renders its own draw ({kwargs!r}): a cut redraw would "
            "then cost more than the one render of a finished scene"
        )



# --- (j) the corner legend names the RIGHT object -------------------------
# The marker reason used to say every off-sheet marker was "outside the captured
# slab". On a dump with a volume that is the wrong object: the sheets span the
# VOLUME's grid, which starts half a cell in and ends half a cell short - there
# is no captured slab in that picture at all.


def test_a_marker_off_the_cut_quotes_the_volumes_grid_not_a_captured_slab():
    """``source == "volume"``: the reason names the grid extent; the plane row is unchanged.

    WHY the noun matters: the sentence sits next to the picture, and "the
    captured slab ends at 3.2 mm" over a volume whose grid ends at 1.0 mm is the
    page lying about the object it just drew. The DECISION is untouched - the
    same ``in_slab`` test and the same half-cell tolerance - so only the words
    differ, and the fallback keeps its own sentence byte for byte because there
    the slab really is the captured one.
    """
    info = _volume_info(_index_volume(3, 4, 2))
    layout = poc_app._cut_layout(info)

    lines = poc_app._marker_cut_relation(_planes(4), layout)

    load = next(line for line in lines if line.startswith("load marker is off"))
    assert "outside the volume's grid extent 0.2000..1.0000 mm" in load, (
        f"the load marker's reason does not quote the volume's own grid: {load!r}"
    )
    assert "captured slab" not in "".join(lines), (
        f"a volume cut still claims a captured slab: {lines!r}"
    )
    assert layout["source"] == "volume"

    plane_info = {
        "path": Path("hand-built.npz"),
        "cell_m": CELL_MM * 1e-3,
        poc_app.PLANE_KEY: np.ones((2, 4, 5), dtype=complex),
    }
    plane_layout = poc_app._cut_layout(plane_info)
    plane_lines = poc_app._marker_cut_relation(_planes(4), plane_layout)

    plane_load = next(
        line for line in plane_lines if line.startswith("load marker is off")
    )
    assert plane_load == (
        "load marker is off both cuts: its x = 4.0000 mm is outside the "
        "captured slab 0.0000..0.4000 mm, so no cut sheet reaches it"
    ), f"the plane row's sentence changed: {plane_load!r}"



# --- (k) no colour range: linear, never a made-up one ---------------------
# ``clim`` is READ from the reader that produced the image. Every path that
# returns no image returns ``clim=None``, and the single path that returns one
# returns ``(peak / 1000, peak)`` - so the key is present exactly when the image
# is. The guard below is the belt on that brace, and it is what stops a future
# refactor from turning a missing range into either a KeyError out of the cut
# block or a fabricated bar.


def test_a_volume_with_no_colour_range_drops_the_log_scale_instead_of_inventing_one(
    monkeypatch,
):
    """``clim is None`` beside a real image: the sheet is drawn LINEAR, unframed.

    WHY linear and not some fallback range: a fabricated clim would put numbers
    on the colour bar that the field never had, which is the kind of lie this
    page refuses - whereas a linear sheet over |E| merely shows less. WHY it must
    not raise: this runs inside the cut block's try, so a KeyError here would
    cost the cuts AND the "cuts drawn" flag the legend reads, over a colour bar.
    """
    info = _volume_info(_index_volume(3, 4, 2))
    image, _meta = poc_app._volume_abs_grid(info, CELL_MM)
    assert image is not None, "the fixture volume did not build"
    monkeypatch.setattr(
        poc_app,
        "_volume_abs_grid",
        lambda *_a, **_k: (image, {"clim": None, "reason": None, "n": 0}),
    )

    meshes = _volume_scene_meshes(monkeypatch, info)
    cuts = [(mesh, kwargs) for mesh, kwargs in meshes if "scalars" in kwargs]

    assert len(cuts) == 2, (
        f"expected the two cut sheets, got {[k.get('scalars') for _m, k in meshes]}"
    )
    for _mesh, kwargs in cuts:
        assert kwargs["scalars"] == "e_abs", (
            f"a sheet dropped off the volume's own field: {kwargs['scalars']!r}"
        )
        assert "log_scale" not in kwargs, (
            "a log scale was applied with no range to apply it over: "
            f"{kwargs!r}"
        )
        assert "clim" not in kwargs, (
            f"a colour range was invented for a volume that had none: {kwargs!r}"
        )

