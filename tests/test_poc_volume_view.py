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

@pytest.fixture(scope="module", autouse=True)
def _the_volume_layer_is_on():
    """Opt this module in to the |E| layer it exists to test.

    ``SHOW_VOLUME_LAYER_DEFAULT`` (server/poc_app.py:892) keeps the 3-D |E|
    volume off the page by default: no volume, no cut sheets, no |E| bar and no
    |E| half of the step counter.  Every draw asserted below is an assertion
    ABOUT that layer, so the ONE thing this module needs is the layer turned on
    - the switch's own opt-in clause, monkeypatched for the whole module so it
    also covers the ``scope="module"`` boots.  Not one assertion moves.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(poc_app, "SHOW_VOLUME_LAYER_DEFAULT", True)
        yield


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


class _FakeMapper:
    """The one thing a scalar bar is ever handed: an actor's mapper."""

    def __init__(self):
        self.scalar_range = (0.0, 1.0)


class _FakeActor:
    """An actor stand-in that carries the mapper a bar reads.

    WHY not a bare ``object()``: the bars are placed from the ACTOR's own mapper
    (that is what makes one bar describe one field), so the fake has to carry
    one for the placement to be observable at all.
    """

    def __init__(self):
        self.mapper = _FakeMapper()
        self.visibility = True


class _ScenePlotter:
    """Records what ``_draw_scene`` asks for. No VTK, no GL, no display."""

    def __init__(self):
        self.calls = []
        # Separate from ``calls``: a bar is decoration, and the tests that count
        # draws must not see it as one.
        self.bar_calls = []
        self.scalar_bars = {}

    def add_scalar_bar(self, **kwargs):
        self.bar_calls.append(kwargs)
        self.scalar_bars[kwargs.get("title")] = kwargs.get("mapper")

    def remove_scalar_bar(self, title=None, render=True):
        self.scalar_bars.pop(title, None)

    def clear(self):
        self.calls.append("clear")

    def add_mesh(self, mesh, **kwargs):
        self.calls.append(("add_mesh", kwargs))
        return _FakeActor()

    def add_volume(self, mesh, **kwargs):
        self.calls.append(("add_volume", mesh, kwargs))
        return _FakeActor()

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
    # The bar is NOT made by the volume draw: the same title twice is the same
    # KEY to pyvista, which MERGES - the second frame's range would union with
    # the first's. It is placed once, below, under the |E| title.
    assert kwargs["show_scalar_bar"] is False
    titles = [call["title"] for call in plotter.bar_calls]
    # The title now ALSO states the colour-scale window in force, so it is asked
    # of the function that builds it rather than read off the bare constant.
    expected_title = poc_app._volume_bar_title(poc_app.VOLUME_CLIM_DEFAULT)
    assert titles == [expected_title], (
        f"expected one bar titled {expected_title!r}, got {titles}"
    )
    assert titles[0].startswith("|E| (Log)")
    assert titles[0] != "|Ez| [V/m]"
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

    laid = poc_app._cut_layout(info, j, k)
    # ``build_cut_sheets`` hands back ``(axis, sheet, clim)``: the range is the
    # sheet's own and is pinned by the colour-scale tests further down.
    sheets = {
        axis: sheet
        for axis, sheet, _clim in poc_app.build_cut_sheets(info, laid)
    }

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

    sheets = {
        axis: sheet
        for axis, sheet, _clim in poc_app.build_cut_sheets(info, layout)
    }
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


def test_the_volume_cut_sheets_are_drawn_on_their_own_colour_scale(
    monkeypatch,
):
    """Two ``add_mesh`` calls, ``scalars="e_abs"``, log on EACH sheet's own clim.

    WHY each sheet's own range and not the volume's: a cut is a SUBSET of the
    field, so its peak is at most the volume's and can be far below it - painted
    on the volume's range the sheet spends the top of the colour bar on values it
    does not have (measured on the shipped dump at the default cuts: 65.6 V/m on
    the y cut and 8.2 V/m on the z cut against 90.7 V/m in the volume). WHY the
    scale matters at all: |E| spans tens of decades, so a linear sheet would show
    the peak and nothing else - while a second colour bar over the same field
    would be the same numbers twice, hence ``show_scalar_bar=False`` and the
    ranges named in the corner legend instead.

    The real ``_cut_layout`` and ``build_cut_sheets`` are put back after
    ``_stub_scene``: the stubs exist to keep the rest of the scene out of the way,
    not to fake the sheets under test.
    """
    nx, ny, nz = 3, 4, 2
    volume = _index_volume(nx, ny, nz)
    # ONE sample far above the rest, deliberately off BOTH default cuts
    # (j = ny // 2, k = nz // 2) so the volume's range differs from EITHER
    # sheet's: with a monotone fixture every cut could accidentally share the
    # volume's peak and this test could pass on the very bug it is about.
    volume[0, ny - 1, 0, :] = 1000.0
    info = _volume_info(volume)
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
    # The range the volume image itself was drawn on - the one the sheets must
    # NOT be sharing.
    volume_clim = passed[poc_app.VOLUME_ABS_KEY]["clim"]
    assert volume_clim is not None, "the fixture volume built no colour range"
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
        # The sheet is a SUBSET of the volume image: same parent field object
        # values, no second colocation paid.
        assert "e_abs" in mesh.point_data.keys()
        # ...but its RANGE is its own: the bar is capped 60 dB below the SHEET's
        # own peak, read off the array the mesh actually carries.
        own = np.asarray(mesh.point_data["e_abs"], dtype=float)
        peak = float(own.max())
        assert kwargs["clim"] == pytest.approx((peak * 1e-3, peak)), (
            f"the sheet's range {kwargs['clim']!r} is not its own "
            f"{((peak * 1e-3, peak))!r}"
        )
        assert kwargs["clim"] != pytest.approx(volume_clim), (
            f"the sheet was painted on the volume's {volume_clim!r} - the top of "
            "that bar is spent on values the sheet does not have"
        )
    # The spike sits off both cuts, so the volume's own bar must still reach it:
    # sharing one range would have been the only way for these two to agree.
    assert volume_clim == pytest.approx((1732.0508075688772e-3, 1732.0508075688772)), (
        f"the volume's own colour range moved: {volume_clim!r}"
    )



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



# --- (k) no positive sample on a sheet: linear, never a made-up range -----
# ``clim`` is READ off the samples the sheet actually carries, and a sheet whose
# samples are all zero (a cut off the edge of a field that does not reach it)
# has no peak to take 60 dB below. The guard below is the belt on that brace: it
# stops a future refactor from turning "no peak" into either a KeyError out of
# the cut block or a fabricated bar.


def _sheet_with(arrays):
    """A stand-in sheet: ``_cut_sheet_clim`` reads nothing but ``point_data``."""
    return types.SimpleNamespace(point_data=arrays)


def test_cut_sheet_clim_is_none_without_a_finite_positive_sample():
    """No range when there is no peak to take 60 dB below - never a guessed one.

    WHY every one of these returns None and not a made-up ``(0, max)``: the
    numbers end up as the colour bar's own numbers, so a range the samples never
    had is a lie the reader cannot check. ``nan``/``inf`` are here because ONE
    non-finite sample moves a max to inf or NaN and the picture is then wrong
    everywhere, not just there; negatives because a log scale has no place to put
    them; and the missing array because a sheet that carries another field is not
    this function's business.
    """
    cases = {
        "all zero": _sheet_with({"e_abs": np.zeros(4)}),
        "one non-finite": _sheet_with({"e_abs": np.array([np.nan, np.inf, -1.0, 0.0])}),
        "negatives only": _sheet_with({"e_abs": np.array([-3.0, -1.0])}),
        "no e_abs array": _sheet_with({"ez_abs": np.array([1.0, 2.0])}),
        "no point_data": types.SimpleNamespace(point_data=None),
    }

    for label, sheet in cases.items():
        assert poc_app._cut_sheet_clim(sheet, "e_abs") is None, (
            f"{label}: a colour range was invented for a sheet with no peak"
        )


def test_cut_sheet_clim_reads_the_sheets_own_peak():
    """``(peak / 1000, peak)`` off the sheet's own array, ignoring zero and non-finite.

    WHY a real ``ImageData``: it is what ``build_cut_sheets`` hands over, and the
    array it stores is Fortran-ordered, so this is also the proof that the peak is
    read off the values and not off an ordering.
    """
    import pyvista as pv

    sheet = pv.ImageData(dimensions=(4, 1, 1))
    sheet.point_data["e_abs"] = np.array([2.0, 50.0, 0.0, 5.0])

    assert poc_app._cut_sheet_clim(sheet, "e_abs") == (0.05, 50.0)


def test_a_cut_sheet_with_no_positive_sample_is_drawn_linear_not_on_a_made_up_range(
    monkeypatch,
    capsys,
):
    """A cut with no finite positive sample: drawn LINEAR, with no ``clim``.

    WHY linear and not some fallback range: a fabricated clim would put numbers
    on the colour bar that the field never had, which is the kind of lie this
    page refuses - whereas a linear sheet over zeros merely shows nothing, which
    is the truth. WHY it must not raise: this runs inside the cut block's try, so
    a KeyError here would cost the cuts AND the "cuts drawn" flag the legend
    reads, over a colour bar.

    The volume is NOT all zero (that is refused by the reader outright), but its
    only positive sample sits at the corner, off both default cuts: the image
    builds, and both sheets still come out empty.
    """
    volume = np.zeros((3, 4, 2, 3))
    volume[0, 0, 0, 0] = 1.0
    info = _volume_info(volume)

    meshes = _volume_scene_meshes(monkeypatch, info)
    cuts = [(mesh, kwargs) for mesh, kwargs in meshes if "scalars" in kwargs]

    assert len(cuts) == 2, (
        f"expected the two cut sheets, got {[k.get('scalars') for _m, k in meshes]}"
    )
    for mesh, kwargs in cuts:
        assert kwargs["scalars"] == "e_abs", (
            f"a sheet dropped off the volume's own field: {kwargs['scalars']!r}"
        )
        own = np.asarray(mesh.point_data["e_abs"], dtype=float)
        assert float(own.max()) == 0.0, (
            f"the fixture sheet is not empty, so this test proves nothing: {own!r}"
        )
        assert "log_scale" not in kwargs, (
            "a log scale was applied with no range to apply it over: "
            f"{kwargs!r}"
        )
        assert "clim" not in kwargs, (
            f"a colour range was invented for a sheet that had no peak: {kwargs!r}"
        )
    assert "cut sheets not drawn" not in capsys.readouterr().err, (
        "an empty cut sheet cost the whole cut block"
    )



# --- (l) the range each cut was painted on reaches the READER --------------
# The sheets are drawn on their own 60 dB range with NO colour bar of their own,
# so the corner legend is the only place those numbers exist: without it a dark
# cut and a dim one look the same. The numbers must be the ones the sheets were
# actually painted on - and a sheet that was never on a range (the plane
# fallback) must not be given one beside it.


def _scene_meshes_and_legend(monkeypatch, info):
    """``_draw_scene`` in VOLUME mode: the meshes AND the legend's extra lines.

    ``_volume_scene_meshes`` with the ONE stub replaced: ``_marker_text`` is
    patched LAST (``_stub_scene`` already replaced it, and that one throws the
    lines away) so the second POSITIONAL argument - the extra legend lines
    ``_draw_scene`` appends - is captured instead. Positional and not keyword,
    because that is how the production call passes it: a signature that only
    accepted ``extra_lines=`` would never see the production call at all.
    """
    plotter = _SheetPlotter()
    captured = {}
    _stub_scene(monkeypatch)
    monkeypatch.setattr(poc_app, "_cut_layout", _REAL_CUT_LAYOUT)
    monkeypatch.setattr(poc_app, "build_cut_sheets", _REAL_BUILD_CUT_SHEETS)

    def _capture(_planes_arg, extra_lines=None):
        captured["lines"] = list(extra_lines or [])
        return "legend"

    monkeypatch.setattr(poc_app, "_marker_text", _capture)
    passed = dict(info)
    passed.setdefault(poc_app.PLANE_KEY, np.ones((4, 4, 5), dtype=complex))

    poc_app._draw_scene(plotter, passed, _planes(4), "volume", 0)
    return plotter.meshes, captured.get("lines", [])


def test_a_plane_fallback_cut_is_drawn_linear_and_quotes_no_range(monkeypatch):
    """No volume: the sheets keep ``ez_abs``, go LINEAR, and quote no range.

    WHY the fallback keeps its old picture: the captured |Ez| stack is a different
    field from the colocated |E| volume - the FFT normalisation makes the two
    ~2053x apart in V/m - and it has been drawn linear since the cuts existed, so
    applying a volume's 60 dB range to it would silently rescale one field onto
    the other's numbers. WHY the legend must stay silent too: the range sentence
    is the colour bar's own numbers, and there is no bar here; ``cut colour
    ranges: y cut on a linear bar ...`` beside a linear sheet is the legend
    describing a picture that is not on screen.

    The plane stack is all ones, so every sheet DOES have a finite positive peak
    and ``build_cut_sheets`` hands one back: the guard under test is the one in
    ``_draw_scene``, not an empty array accidentally proving nothing.
    """
    info = {
        "path": Path("hand-built.npz"),
        "cell_m": CELL_MM * 1e-3,
        poc_app.PLANE_KEY: np.ones((4, 4, 5), dtype=complex),
    }

    meshes, legend = _scene_meshes_and_legend(monkeypatch, info)

    cuts = [(mesh, kwargs) for mesh, kwargs in meshes if "scalars" in kwargs]
    assert len(cuts) == 2, (
        "expected the two plane-fallback cut sheets, got "
        f"{[kwargs.get('scalars') for _m, kwargs in meshes]}"
    )
    for mesh, kwargs in cuts:
        assert kwargs["scalars"] == "ez_abs", (
            f"a fallback sheet was drawn on {kwargs['scalars']!r}, not the plane's |Ez|"
        )
        assert "ez_abs" in mesh.point_data.keys(), (
            "the fixture sheet carries no field, so this test proves nothing"
        )
        assert "log_scale" not in kwargs, (
            f"a volume's log scale was applied to a captured |Ez| sheet: {kwargs!r}"
        )
        assert "clim" not in kwargs, (
            "a colour range was applied to a sheet that has never been on one: "
            f"{kwargs!r}"
        )
    assert not [line for line in legend if "cut colour ranges" in line], (
        "the corner legend quoted a colour range for sheets drawn linear: "
        f"{legend!r}"
    )


def test_the_corner_legend_quotes_each_cuts_own_peak(monkeypatch):
    """ONE ``cut colour ranges:`` line, naming each sheet's own peak in V/m.

    WHY the legend and not a second colour bar: two bars over one set of colours
    read as two fields, so the numbers moved into the corner - which makes this
    line the ONLY place a reader can learn what a cut is painted on, and the
    numbers therefore have to be the ones the sheets ACTUALLY got (hence the
    cross-check against the drawn ``clim``, not only against the arrays).

    The peak is taken off the volume grid by hand, on the layout's own ``(j, k)``,
    so a legend that quoted the volume's range - or one sheet's range for both -
    disagrees with it. The fixture volume carries one spike far above the rest,
    deliberately OFF both default cuts, so no cut accidentally shares the
    volume's peak; the two cuts' own peaks differ from each other as well.
    """
    nx, ny, nz = 3, 4, 2
    volume = _index_volume(nx, ny, nz)
    volume[0, ny - 1, 0, :] = 1000.0
    info = _volume_info(volume)
    ex, ey, ez = volume[..., 0], volume[..., 1], volume[..., 2]
    e_abs = np.sqrt(ex * ex + ey * ey + ez * ez)
    layout = _REAL_CUT_LAYOUT(info)
    j, k = layout["j"], layout["k"]
    y_peak = float(e_abs[:, j, :].max())
    z_peak = float(e_abs[:, :, k].max())

    meshes, legend = _scene_meshes_and_legend(monkeypatch, info)

    expected = (
        "cut colour ranges: "
        f"y cut {y_peak * 1e-3:.4g} .. {y_peak:.4g} V/m (log), "
        f"z cut {z_peak * 1e-3:.4g} .. {z_peak:.4g} V/m (log)"
    )
    quoted = [line for line in legend if line.startswith("cut colour ranges:")]
    assert len(quoted) == 1, (
        "expected exactly one colour-range line in the corner legend, got "
        f"{quoted!r} out of {legend!r}"
    )
    assert quoted[0] == expected, (
        f"the legend quotes {quoted[0]!r}, not the cuts' own peaks {expected!r}"
    )
    # ...and those are the numbers the sheets were DRAWN on: a legend that agrees
    # with the arrays while the meshes carry another clim would be worse than no
    # legend at all.
    cuts = [(mesh, kwargs) for mesh, kwargs in meshes if "scalars" in kwargs]
    dims = [tuple(mesh.dimensions) for mesh, _kwargs in cuts]
    assert dims == [(nx, 1, nz), (nx, ny, 1)], (
        f"the drawn sheets are not the y and z cuts: {dims!r}"
    )
    for axis, (mesh, kwargs), peak in zip(("y", "z"), cuts, (y_peak, z_peak)):
        assert kwargs["clim"] == pytest.approx((peak * 1e-3, peak)), (
            f"the {axis} sheet was painted on {kwargs['clim']!r} while the legend "
            f"quotes its own peak {((peak * 1e-3, peak))!r}"
        )
        assert "e_abs" in mesh.point_data.keys(), (
            f"the {axis} sheet carries no |E| field of its own"
        )


# --- (m) the same ranges, measured on the shipped solve --------------------
# Every range above is a fixture's. These are the real ones, off the only field
# data in this repo: the numbers the page puts in front of an operator.

#: The shipped Build A artefacts: the dump carries the staggered ``e`` vector, so
#: ``e_raw=True`` is what makes it a volume at all (the colocation is deferred to
#: the first reader, ~0.84 s, and this test is a reader).
NPZ = REPO_ROOT / "evidence" / "termination" / "build_A_50ohm_p51_ghostwave_fields.npz"


def test_on_the_shipped_dump_each_cut_is_quoted_on_its_own_peak():
    """Measured: y cut 65.57 V/m, z cut 8.22 V/m, volume 90.68 V/m - not one range.

    WHY the real dump and not another fixture: a fixture can be built to any
    ratio, so only the solve proves the three ranges genuinely DIFFER - and they
    do, by an order of magnitude between the z cut and the volume. Painted on the
    volume's range the z cut would spend nine tenths of the colour bar on values
    it does not have.

    The sheet's peak is checked twice: against its own array, and against the
    slice I took off the volume image by hand, so a sheet cut from the wrong j or
    k is caught rather than a merely plausible number.
    """
    if not NPZ.is_file():
        pytest.skip(f"field dump absent: {NPZ}")
    info = poc_app.load_dump(NPZ, e_raw=True)
    cell_mm = float(info["cell_m"]) * 1e3
    layout = poc_app._cut_layout(info)
    assert layout["source"] == "volume", (
        f"the shipped dump was cut from the plane stack: {layout['source']!r}"
    )

    image, meta = poc_app._volume_abs_grid(info, cell_mm)
    assert meta["reason"] is None, f"the shipped volume was refused: {meta}"
    volume_clim = meta["clim"]
    nx, ny, nz = (int(v) for v in image.dimensions)
    grid = np.asarray(image.point_data["e_abs"], dtype=float).reshape(
        (nx, ny, nz), order="F"
    )
    peaks = {
        "y": float(grid[:, layout["j"], :].max()),
        "z": float(grid[:, :, layout["k"]].max()),
    }
    assert peaks["y"] != pytest.approx(peaks["z"]), (
        "the two cuts share a peak on this dump, so the test cannot tell their "
        f"ranges apart: {peaks!r}"
    )

    sheets = poc_app.build_cut_sheets(info, layout)
    assert [axis for axis, _s, _c in sheets] == ["y", "z"], (
        f"the cuts are not the y and z sheets: {[a for a, _s, _c in sheets]!r}"
    )
    for axis, sheet, clim in sheets:
        own = float(np.asarray(sheet.point_data["e_abs"], dtype=float).max())
        assert own == pytest.approx(peaks[axis]), (
            f"the {axis} sheet peaks at {own!r}, not at {peaks[axis]!r} where the "
            "volume's own slice does: the cut is not on the sample it reports"
        )
        assert clim == pytest.approx((own * 1e-3, own)), (
            f"the {axis} cut's range {clim!r} is not its own peak "
            f"{((own * 1e-3, own))!r}"
        )
        assert clim != pytest.approx(volume_clim), (
            f"the {axis} cut was given the volume's {volume_clim!r}"
        )



# --- (n) the field layer is a function of its ARGUMENTS ---------------------
# The volume and its two cut sheets used to be reachable only through
# ``_draw_scene``, which reads the plane dict, the module keys and the camera
# flag on its way to the same lines. ``_draw_volume_scene`` takes those inputs
# as ARGUMENTS instead: the grid the caller already built, the cut layout it
# already resolved (so the sheets and the corner legend cannot disagree about
# which y / z sample is on screen), the cell size the volume lattice is indexed
# by, and - when the caller has one - the range to pin the volume to. What is
# pinned below is exactly that: the layer draws from the arguments alone, the
# override bites the VOLUME and nothing else, and a caller with no override
# gets byte for byte the picture this page drew before the extraction.

#: Two DIFFERENT sheet ranges, so a shared range cannot pass by coincidence.
_CLIM_Y = (0.25, 250.0)
_CLIM_Z = (0.5, 500.0)


def _forbidden(name):
    """A collaborator that must NOT be reached: the helper takes it as an arg."""

    def _refuse(*_args, **_kwargs):
        raise AssertionError(
            f"{name} was called: the field layer rebuilds what it was handed"
        )

    return _refuse


def _fake_volume_abs_grid(calls, image, clim):
    """Stand in for ``_volume_abs_grid``: record the call, hand back a range."""

    def _fake(info, cell_mm):
        calls.append((info, cell_mm))
        return image, {"clim": clim}

    return _fake


def _fake_cut_sheets(calls, sheets):
    """Stand in for ``build_cut_sheets``: record what it was HANDED."""

    def _fake(info, layout):
        calls.append((info, layout))
        return list(sheets)

    return _fake


def _fake_sheet(marker):
    """A stand-in sheet: the helper reads ``point_data`` and ``outline()``."""
    return types.SimpleNamespace(
        point_data={"e_abs": np.ones(2)}, outline=lambda: f"edge:{marker}"
    )


def _layout():
    """A cut layout the helper must take as GIVEN and never recompute."""
    return {"y_mm": 0.2, "j": 0, "n_j": 4, "z_mm": 0.6, "k": 1, "n_k": 2}


def _two_sheets():
    """The two volume sheets, each on its own range, distinguishable by outline."""
    return [
        ("y", _fake_sheet("y"), _CLIM_Y),
        ("z", _fake_sheet("z"), _CLIM_Z),
    ]


def _sheet_kwargs(plotter):
    """The ``add_mesh`` kwargs of the sheets - the ones that carry ``scalars``."""
    return [kwargs for _mesh, kwargs in plotter.meshes if "scalars" in kwargs]


def test_the_field_layer_is_drawable_from_its_arguments_alone(monkeypatch):
    """No plane dict and no ``_draw_scene``: the helper has everything it needs.

    WHY this is the claim: the extraction is only worth anything if the volume
    view can be drawn by a caller that owns a grid and a cut layout - so the
    three things ``_draw_scene`` supplied from ITS scope (the grid it built, the
    layout it resolved, the cell size it read off the plane dict) are arguments
    here, and the helper must neither rebuild them nor read a plane dict to get
    them. ``build_grid`` is therefore poisoned: a call to it fails this test.
    """
    info = _volume_info(_index_volume(3, 4, 2))
    image = object()
    abs_calls, sheet_calls = [], []
    monkeypatch.setattr(
        poc_app, "_volume_abs_grid", _fake_volume_abs_grid(abs_calls, image, _CLIM_Y)
    )
    monkeypatch.setattr(
        poc_app, "build_cut_sheets", _fake_cut_sheets(sheet_calls, _two_sheets())
    )
    monkeypatch.setattr(poc_app, "build_grid", _forbidden("build_grid"))
    grid = object()
    layout = _layout()
    plotter = _SheetPlotter()

    cuts_drawn, cut_clims = poc_app._draw_volume_scene(
        plotter, info, grid=grid, cut_layout=layout, cell_mm=CELL_MM
    )

    assert poc_app.PLANE_KEY not in info, (
        "the helper read the captured plane stack: the volume view must not need one"
    )
    assert abs_calls == [(info, CELL_MM)], (
        f"the volume was built from {abs_calls!r}, not from (info, cell_mm)"
    )
    assert sheet_calls == [(info, layout)], (
        "the sheets were not built from the layout the caller resolved - a second "
        "resolution is how the sheets and the corner legend start disagreeing"
    )
    _mesh, volume_kwargs = plotter.volumes()[0][1:]
    assert plotter.volumes()[0][1] is image, "the helper drew a volume it did not build"
    assert volume_kwargs["scalars"] == "e_abs"
    assert cuts_drawn is True, f"the helper reported the sheets refused: {cut_clims!r}"
    assert cut_clims == {"y": _CLIM_Y, "z": _CLIM_Z}, (
        f"the ranges it handed back are {cut_clims!r}, not the sheets' own"
    )
    # Each sheet is framed by ITS OWN outline, immediately after it.
    assert [mesh for mesh, kwargs in plotter.meshes if "scalars" not in kwargs] == [
        "edge:y",
        "edge:z",
    ], "a cut sheet was left with no edge of its own"


def test_the_clim_override_pins_the_volume_and_never_the_sheets(monkeypatch):
    """``clim_override`` is the volume's range, passed through as the SAME object.

    WHY identity and not equality: a range quietly rebuilt from the override
    (say ``tuple(clim_override)``, or rounded through the image's dtype) would
    pass an equality test while the number on the bar is no longer the one the
    caller asked for. WHY the sheets are excluded: each sheet was measured on
    the samples it actually holds, and one range over both fields is the lie the
    cut block exists to refuse.
    """
    info = _volume_info(_index_volume(3, 4, 2))
    sentinel = (1.5, 1500.0)
    monkeypatch.setattr(
        poc_app,
        "_volume_abs_grid",
        _fake_volume_abs_grid([], object(), (0.001, 1.0)),
    )
    monkeypatch.setattr(
        poc_app, "build_cut_sheets", _fake_cut_sheets([], _two_sheets())
    )
    plotter = _SheetPlotter()

    cuts_drawn, cut_clims = poc_app._draw_volume_scene(
        plotter,
        info,
        grid=object(),
        cut_layout=_layout(),
        cell_mm=CELL_MM,
        clim_override=sentinel,
    )

    assert cuts_drawn is True
    volume_kwargs = plotter.volumes()[0][2]
    assert volume_kwargs["clim"] is sentinel, (
        f"the volume was drawn on {volume_kwargs['clim']!r}, not the override the "
        "caller pinned - a rebuilt range is a different number"
    )
    sheet_clims = [kwargs["clim"] for kwargs in _sheet_kwargs(plotter)]
    assert sheet_clims == [_CLIM_Y, _CLIM_Z], (
        "the override reached the cut sheets: their own 60 dB ranges were replaced "
        "by a range measured on the whole field"
    )
    assert cut_clims == {"y": _CLIM_Y, "z": _CLIM_Z}


def test_no_override_draws_the_range_the_volume_measured_and_a_bare_fallback(
    monkeypatch,
):
    """Default is byte for byte the old picture: own clim, and NO clim on |Ez|.

    WHY the plane fallback must carry no ``clim`` when the caller pinned
    nothing: it has no range of its own, and inventing one would change the
    picture this page has always drawn for a dump with no colocated volume. WHY
    it DOES take an override: with no range of its own, a caller's range is the
    only one it can be pinned to.
    """
    info = _volume_info(_index_volume(3, 4, 2))
    own_clim = (0.001, 1.0)
    sentinel = (2.0, 2000.0)
    monkeypatch.setattr(poc_app, "build_cut_sheets", _fake_cut_sheets([], []))

    # (1) the |E| volume, no override: the range the helper measured, untouched.
    monkeypatch.setattr(
        poc_app, "_volume_abs_grid", _fake_volume_abs_grid([], object(), own_clim)
    )
    plotter = _SheetPlotter()
    cuts_drawn, cut_clims = poc_app._draw_volume_scene(
        plotter, info, grid=object(), cut_layout=_layout(), cell_mm=CELL_MM
    )
    assert plotter.volumes()[0][2]["clim"] is own_clim, (
        f"with no override the volume was pinned to {plotter.volumes()[0][2]['clim']!r}"
        f" instead of the {own_clim!r} it measured"
    )
    assert (cuts_drawn, cut_clims) == (True, {}), (
        "a scene with no sheets must report no sheets: the legend is built from this"
    )

    # (2) no volume at all, no override: the |Ez| stack, still with NO clim key.
    monkeypatch.setattr(
        poc_app, "_volume_abs_grid", _fake_volume_abs_grid([], None, None)
    )
    plotter = _SheetPlotter()
    poc_app._draw_volume_scene(
        plotter, info, grid="grid", cut_layout=_layout(), cell_mm=CELL_MM
    )
    assert len(plotter.volumes()) == 1
    assert plotter.volumes()[0][1] == "grid", "the fallback was not drawn on the grid"
    fallback = plotter.volumes()[0][2]
    assert fallback["scalars"] == "ez_abs"
    assert "clim" not in fallback, (
        f"the plane fallback invented a range: {fallback['clim']!r}"
    )

    # (3) ...but a caller's override DOES reach it: it has no range of its own.
    plotter = _SheetPlotter()
    poc_app._draw_volume_scene(
        plotter,
        info,
        grid="grid",
        cut_layout=_layout(),
        cell_mm=CELL_MM,
        clim_override=sentinel,
    )
    assert plotter.volumes()[0][2]["clim"] is sentinel, (
        "the override did not reach the only volume on screen"
    )


def test_each_cut_sheet_is_drawn_log_on_its_own_axis_range(monkeypatch):
    """The two sheets come back per AXIS, each log-scaled on its own range.

    WHY per axis and not one number: the corner legend names each cut
    ("y cut ... z cut ...") and the range beside each name has to be the range
    that cut was painted on. One range for the pair would put the y cut's peak
    beside the z cut's number and be believed.
    """
    info = _volume_info(_index_volume(3, 4, 2))
    monkeypatch.setattr(
        poc_app, "_volume_abs_grid", _fake_volume_abs_grid([], object(), (0.001, 1.0))
    )
    monkeypatch.setattr(
        poc_app, "build_cut_sheets", _fake_cut_sheets([], _two_sheets())
    )
    plotter = _SheetPlotter()

    cuts_drawn, cut_clims = poc_app._draw_volume_scene(
        plotter, info, grid=object(), cut_layout=_layout(), cell_mm=CELL_MM
    )

    assert cuts_drawn is True
    assert cut_clims == {"y": _CLIM_Y, "z": _CLIM_Z}, (
        f"the ranges are {cut_clims!r}, not one per axis: a legend cannot name them"
    )
    assert _CLIM_Y != _CLIM_Z, "the fixture shares one range, so it proves nothing"
    pairs = zip(_sheet_kwargs(plotter), [_CLIM_Y, _CLIM_Z], strict=True)
    for kwargs, expected in pairs:
        assert kwargs["scalars"] == "e_abs"
        assert kwargs["clim"] == expected, (
            f"a sheet was drawn on {kwargs['clim']!r}, not its own {expected!r}"
        )
        assert kwargs["log_scale"] is True, (
            "a linear |E| sheet shows the peak and nothing else"
        )
        assert kwargs["show_scalar_bar"] is False, (
            "a second colour bar appeared over the same field"
        )


def test_the_volume_and_port_views_both_still_draw_the_board_and_the_markers(
    monkeypatch,
):
    """The delegation must not cost the shared tail in EITHER view.

    WHY this test exists beside the extraction: the field layer is the volume's,
    but the outline, the axes, the board and the marker layer are drawn after
    BOTH branches by ``_draw_scene``. A refactor that moved the field layer - or
    the marker helpers - one level down would quietly drop them from the view
    that no longer runs that code, and a marker with no board under it is the
    picture that started this work.
    """
    drawn = []
    _stub_scene(monkeypatch)
    monkeypatch.setattr(
        poc_app, "_vis_geometry", lambda p, i, pl: drawn.append("board")
    )
    monkeypatch.setattr(
        poc_app, "_add_markers", lambda p, i, pl: drawn.append("markers")
    )

    for mode in ("port", "volume"):
        drawn.clear()
        passed = dict(_volume_info(_index_volume(3, 4, 2)))
        passed[poc_app.PLANE_KEY] = np.ones((4, 4, 5), dtype=complex)
        poc_app._draw_scene(_SheetPlotter(), passed, _planes(4), mode, 0)
        assert drawn == ["board", "markers"], (
            f"the {mode} view drew {drawn!r} - the board and the marker layer are "
            "the shared tail and belong to both views"
        )
