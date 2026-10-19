"""Orthogonal grids and their metric quantities.

A :class:`Grid` holds only *metric* information: the node coordinates on the
three axes.  Everything the FIT material matrices need -- primary edge lengths,
primary face areas and dual face areas -- is derived from those coordinates.

Non-uniform spacing is first class.  Because the topological operators in
:mod:`emfit.operators` are metric free, refining part of the domain costs
nothing structurally: only ``M_eps`` and ``M_mu`` change.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["Grid", "CartesianGrid"]


def _axis(name, values):
    a = np.asarray(values, dtype=float)
    if a.ndim != 1:
        raise ValueError(f"{name}: expected a 1-D array, got ndim={a.ndim}")
    if a.size < 2:
        raise ValueError(f"{name}: need at least 2 nodes, got {a.size}")
    if not np.all(np.diff(a) > 0.0):
        raise ValueError(f"{name}: node coordinates must be strictly increasing")
    return a


@dataclass(frozen=True)
class Grid:
    """Orthogonal (possibly non-uniform) grid given by node coordinates.

    Parameters
    ----------
    x, y, z : array_like
        Node coordinates along each axis.  ``len(x) - 1`` cells along x.
    """

    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    periodic: tuple = (False, False, False)

    def __post_init__(self):
        object.__setattr__(self, "x", _axis("x", self.x))
        object.__setattr__(self, "y", _axis("y", self.y))
        object.__setattr__(self, "z", _axis("z", self.z))
        p = tuple(bool(v) for v in self.periodic)
        if len(p) != 3:
            raise ValueError(f"periodic must have 3 entries, got {self.periodic!r}")
        object.__setattr__(self, "periodic", p)

    # ------------------------------------------------------------------
    # periodicity
    # ------------------------------------------------------------------
    def is_periodic(self, axis: str) -> bool:
        """Whether ``axis`` is identified with itself (toroidal topology)."""
        return self.periodic["xyz".index(axis)]

    def nodes(self, axis: str) -> int:
        """Number of primal *point layers* along ``axis``.

        ``n+1`` for a bounded axis, ``n`` for a periodic one: the last node is
        the first node, so it is not a separate entity.
        """
        n = self.shape["xyz".index(axis)]
        return n if self.is_periodic(axis) else n + 1

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    def uniform(cls, nx, ny, nz, lx=1.0, ly=1.0, lz=1.0, origin=(0.0, 0.0, 0.0),
                periodic=(False, False, False)):
        """Shoebox grid with ``nx*ny*nz`` equal cells spanning ``lx*ly*lz``."""
        ox, oy, oz = (float(o) for o in origin)
        return cls(
            np.linspace(ox, ox + float(lx), int(nx) + 1),
            np.linspace(oy, oy + float(ly), int(ny) + 1),
            np.linspace(oz, oz + float(lz), int(nz) + 1),
            periodic=periodic,
        )

    @classmethod
    def nonuniform(cls, x, y, z, periodic=(False, False, False)):
        """Grid from explicit, strictly increasing node coordinate arrays."""
        return cls(x, y, z, periodic=periodic)

    # ------------------------------------------------------------------
    # sizes
    # ------------------------------------------------------------------
    @property
    def shape(self):
        """Number of cells per axis, ``(nx, ny, nz)``."""
        return (self.x.size - 1, self.y.size - 1, self.z.size - 1)

    @property
    def nx(self):
        return self.x.size - 1

    @property
    def ny(self):
        return self.y.size - 1

    @property
    def nz(self):
        return self.z.size - 1

    @property
    def n_cells(self):
        return self.nx * self.ny * self.nz

    @property
    def origin(self):
        return (float(self.x[0]), float(self.y[0]), float(self.z[0]))

    @property
    def extent(self):
        return (
            float(self.x[-1] - self.x[0]),
            float(self.y[-1] - self.y[0]),
            float(self.z[-1] - self.z[0]),
        )

    def __repr__(self):  # pragma: no cover - cosmetic
        return f"Grid(cells={self.shape}, extent={self.extent})"

    # ------------------------------------------------------------------
    # 1-D metric: cell widths and dual (node centred) widths
    # ------------------------------------------------------------------
    def widths(self, axis):
        """Primary cell widths ``dx`` along ``axis``; length ``n``."""
        return np.diff(getattr(self, axis))

    def dual_widths(self, axis):
        """Dual cell widths centred on each *node*; length ``nodes(axis)``.

        Interior nodes use the circumcentric average
        ``(a[i+1] - a[i-1]) / 2``; on a bounded axis the two boundary nodes get
        a half cell, so the dual complex terminates on the domain boundary.
        On a *periodic* axis every node is interior and the averaging wraps, so
        the dual complex closes on itself (no half cells, no terminating faces).
        """
        a = getattr(self, axis)
        if self.is_periodic(axis):
            w = np.diff(a)                       # n_cells widths, n_cells nodes
            return 0.5 * (w + np.roll(w, 1))      # circular circumcentric mean
        w = np.empty(a.size, dtype=float)
        w[1:-1] = 0.5 * (a[2:] - a[:-2])
        w[0] = 0.5 * (a[1] - a[0])
        w[-1] = 0.5 * (a[-1] - a[-2])
        return w

    # ------------------------------------------------------------------
    # array shapes of the primal/dual entities
    # ------------------------------------------------------------------
    def edge_shape(self, axis):
        """Shape of edges parallel to ``axis`` (= shape of their dual face).

        Along ``axis`` the count is the number of cells; transversely it is the
        number of point layers, i.e. ``n + 1`` on a bounded axis and ``n`` on a
        periodic one (the seam node is not duplicated).
        """
        n = self.shape
        nodes = tuple(self.nodes(a) for a in "xyz")
        return tuple(
            n[t] if "xyz"[t] == axis else nodes[t] for t in range(3)
        )

    def face_shape(self, axis):
        """Shape of primal faces orthogonal to ``axis``."""
        n = self.shape
        nodes = tuple(self.nodes(a) for a in "xyz")
        return tuple(
            n[t] if "xyz"[t] != axis else nodes[t] for t in range(3)
        )

    # ------------------------------------------------------------------
    # primary metric: edge length L_i and face area A_f
    # ------------------------------------------------------------------
    def edge_length(self, axis):
        """Length ``L_i`` of every edge parallel to ``axis``.

        Shape is ``edge_shape(axis)``, i.e. the length is the primary cell
        width along ``axis`` broadcast over the transverse directions.
        """
        w = self.widths(axis)
        s = self.edge_shape(axis)
        shaper = {"x": (w.size, 1, 1),
                  "y": (1, w.size, 1),
                  "z": (1, 1, w.size)}[axis]
        return np.broadcast_to(w.reshape(shaper), s)

    def face_area_x(self):
        """Area of primal faces with normal x, shape ``(nx+1, ny, nz)``."""
        return np.broadcast_to(
            self.widths("y")[None, :, None] * self.widths("z")[None, None, :],
            self.face_shape("x"),
        )

    def face_area_y(self):
        """Area of primal faces with normal y, shape ``(nx, ny+1, nz)``."""
        return np.broadcast_to(
            self.widths("x")[:, None, None] * self.widths("z")[None, None, :],
            self.face_shape("y"),
        )

    def face_area_z(self):
        """Area of primal faces with normal z, shape ``(nx, ny, nz+1)``."""
        return np.broadcast_to(
            self.widths("x")[:, None, None] * self.widths("y")[None, :, None],
            self.face_shape("z"),
        )

    # ------------------------------------------------------------------
    # dual metric: dual face area A~_i (crosses the edge)
    # ------------------------------------------------------------------
    def dual_face_area_x(self):
        """Area of the dual face crossed by x-edges, shape ``(nx, ny+1, nz+1)``."""
        return np.broadcast_to(
            np.multiply.outer(self.dual_widths("y"), self.dual_widths("z"))[None, :, :],
            self.edge_shape("x"),
        )

    def dual_face_area_y(self):
        """Area of the dual face crossed by y-edges, shape ``(nx+1, ny, nz+1)``."""
        return np.broadcast_to(
            np.multiply.outer(self.dual_widths("x"), self.dual_widths("z"))[:, None, :],
            self.edge_shape("y"),
        )

    def dual_face_area_z(self):
        """Area of the dual face crossed by z-edges, shape ``(nx+1, ny+1, nz)``."""
        return np.broadcast_to(
            np.multiply.outer(self.dual_widths("x"), self.dual_widths("y"))[:, :, None],
            self.edge_shape("z"),
        )

    # ------------------------------------------------------------------
    def cell_volume(self):
        """Volume of each primal cell, shape ``(nx, ny, nz)``."""
        return (
            self.widths("x")[:, None, None]
            * self.widths("y")[None, :, None]
            * self.widths("z")[None, None, :]
        )


def CartesianGrid(nx, ny, nz, lx=1.0, ly=1.0, lz=1.0, origin=(0.0, 0.0, 0.0)):
    """Convenience constructor for a uniform shoebox grid."""
    return Grid.uniform(nx, ny, nz, lx=lx, ly=ly, lz=lz, origin=origin)
