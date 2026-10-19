"""Topological operators of the FIT cell complex.

Every matrix here is *metric free*: entries are only -1, 0 and +1, no length
appears anywhere, and the two discrete identities

    C G = 0        curl(grad) = 0
    S C = 0        div(curl)  = 0

hold exactly in integer arithmetic on any grid, uniform or not.

Unknown ordering (C order flattened)
------------------------------------
EX (nx,ny+1,nz+1) -> EY (nx+1,ny,nz+1) -> EZ (nx+1,ny+1,nz)   [primal edges]
FX (nx+1,ny,nz)   -> FY (nx,ny+1,nz)   -> FZ (nx,ny,nz+1)     [primal faces]

Operator shapes
---------------
``G``  (n_edges, n_nodes)   node potential -> edge voltage
``C``  (n_faces, n_edges)   primal curl, edge voltage -> face flux rate
``S``  (n_cells, n_faces)   cell charge -> outward face flux

Maxwell in FIT notation::

    Faraday:   C e        = -d/dt (M_mu h)
    Ampere:    C_tilde h  =  d/dt (M_eps e) + j

with the dual curl ``C_tilde = C.T``.  The sign of that duality is fixed by
the circulation coefficients below, which were chosen so that ``C G = 0``
holds exactly (checked symbolically on all three face types).
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .grid import Grid

__all__ = ["CellComplex"]


class CellComplex:
    """Primal/dual cell complex of a :class:`~emfit.grid.Grid`."""

    def __init__(self, grid: Grid):
        self.grid = grid
        nx, ny, nz = grid.shape
        self.nx, self.ny, self.nz = nx, ny, nz

        # --- entity counts -------------------------------------------------
        self.n_ex = nx * (ny + 1) * (nz + 1)
        self.n_ey = (nx + 1) * ny * (nz + 1)
        self.n_ez = (nx + 1) * (ny + 1) * nz
        self.n_fx = (nx + 1) * ny * nz
        self.n_fy = nx * (ny + 1) * nz
        self.n_fz = nx * ny * (nz + 1)
        self.n_nodes = (nx + 1) * (ny + 1) * (nz + 1)

        self.n_edges = self.n_ex + self.n_ey + self.n_ez
        self.n_faces = self.n_fx + self.n_fy + self.n_fz
        self.n_cells = nx * ny * nz

        # --- block offsets (start index of each block in the flat vector) ---
        self.off_ex = 0
        self.off_ey = self.n_ex
        self.off_ez = self.n_ex + self.n_ey
        self.off_fx = 0
        self.off_fy = self.n_fx
        self.off_fz = self.n_fx + self.n_fy

        self._cache = {}

    # ------------------------------------------------------------------
    # scalar index helpers (for hand checks and small loops)
    # ------------------------------------------------------------------
    def idx_ex(self, i, j, k):
        return self.off_ex + i * (self.ny + 1) * (self.nz + 1) + j * (self.nz + 1) + k

    def idx_ey(self, i, j, k):
        return self.off_ey + i * self.ny * (self.nz + 1) + j * (self.nz + 1) + k

    def idx_ez(self, i, j, k):
        return self.off_ez + i * (self.ny + 1) * self.nz + j * self.nz + k

    def idx_fx(self, i, j, k):
        return self.off_fx + i * self.ny * self.nz + j * self.nz + k

    def idx_fy(self, i, j, k):
        return self.off_fy + i * (self.ny + 1) * self.nz + j * self.nz + k

    def idx_fz(self, i, j, k):
        return self.off_fz + i * self.ny * (self.nz + 1) + j * (self.nz + 1) + k

    def idx_node(self, i, j, k):
        return i * (self.ny + 1) * (self.nz + 1) + j * (self.nz + 1) + k

    def idx_cell(self, i, j, k):
        return i * self.ny * self.nz + j * self.nz + k

    # ------------------------------------------------------------------
    # vectorised index grids
    # ------------------------------------------------------------------
    def _ig(self, shape):
        return np.indices(shape)

    def _grid_ex(self):
        return self._ig(self.grid.edge_shape("x"))

    def _grid_ey(self):
        return self._ig(self.grid.edge_shape("y"))

    def _grid_ez(self):
        return self._ig(self.grid.edge_shape("z"))

    def _grid_fx(self):
        return self._ig(self.grid.face_shape("x"))

    def _grid_fy(self):
        return self._ig(self.grid.face_shape("y"))

    def _grid_fz(self):
        return self._ig(self.grid.face_shape("z"))

    def _grid_cells(self):
        return self._ig(self.grid.shape)

    # ------------------------------------------------------------------
    # operators
    # ------------------------------------------------------------------
    def gradient(self):
        """``G`` (n_edges, n_nodes): edge voltage = phi[head] - phi[tail]."""
        if "G" in self._cache:
            return self._cache["G"]
        rows, cols, vals = [], [], []
        for axis, idx, ngrid in (
            ("x", self.idx_ex, self._grid_ex),
            ("y", self.idx_ey, self._grid_ey),
            ("z", self.idx_ez, self._grid_ez),
        ):
            i, j, k = (a.ravel() for a in ngrid())
            row = idx(i, j, k)
            head = [i, j, k]
            head["xyz".index(axis)] = head["xyz".index(axis)] + 1
            rows.append(row)
            cols.append(self.idx_node(*head))
            vals.append(np.ones(row.size))
            rows.append(row)
            cols.append(self.idx_node(i, j, k))
            vals.append(-np.ones(row.size))
        G = sp.coo_matrix(
            (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
            shape=(self.n_edges, self.n_nodes),
        ).tocsr()
        self._cache["G"] = G
        return G

    def curl(self):
        """``C`` (n_faces, n_edges): discrete Stokes circulation about each face."""
        if "C" in self._cache:
            return self._cache["C"]
        rows, cols, vals = [], [], []

        def add(r, c, v):
            rows.append(r)
            cols.append(c)
            vals.append(np.full(r.size, float(v)))

        # x-normal faces: right handed circulation about +x in the y-z plane
        i, j, k = (a.ravel() for a in self._grid_fx())
        r = self.idx_fx(i, j, k)
        add(r, self.idx_ey(i, j, k), +1)
        add(r, self.idx_ez(i, j + 1, k), +1)
        add(r, self.idx_ey(i, j, k + 1), -1)
        add(r, self.idx_ez(i, j, k), -1)

        # y-normal faces: right handed circulation about +y in the z-x plane
        i, j, k = (a.ravel() for a in self._grid_fy())
        r = self.idx_fy(i, j, k)
        add(r, self.idx_ez(i, j, k), +1)
        add(r, self.idx_ex(i, j, k + 1), +1)
        add(r, self.idx_ez(i + 1, j, k), -1)
        add(r, self.idx_ex(i, j, k), -1)

        # z-normal faces: right handed circulation about +z in the x-y plane
        i, j, k = (a.ravel() for a in self._grid_fz())
        r = self.idx_fz(i, j, k)
        add(r, self.idx_ex(i, j, k), +1)
        add(r, self.idx_ey(i + 1, j, k), +1)
        add(r, self.idx_ex(i, j + 1, k), -1)
        add(r, self.idx_ey(i, j, k), -1)

        C = sp.coo_matrix(
            (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
            shape=(self.n_faces, self.n_edges),
        ).tocsr()
        self._cache["C"] = C
        return C

    def divergence(self):
        """``S`` (n_cells, n_faces): net outward flux through each cell's faces.

        Row ``c`` sums the six faces of cell ``c`` with the outward normal
        convention (+ face at ``i+1``, - face at ``i``, likewise y and z), so
        ``S b`` is the discrete divergence of the face-flux field ``b``.
        """
        if "S" in self._cache:
            return self._cache["S"]
        i, j, k = (a.ravel() for a in self._grid_cells())
        r = self.idx_cell(i, j, k)
        rows, cols, vals = [], [], []
        for c, v in (
            (self.idx_fx(i + 1, j, k), +1), (self.idx_fx(i, j, k), -1),
            (self.idx_fy(i, j + 1, k), +1), (self.idx_fy(i, j, k), -1),
            (self.idx_fz(i, j, k + 1), +1), (self.idx_fz(i, j, k), -1),
        ):
            rows.append(r)
            cols.append(c)
            vals.append(np.full(r.size, float(v)))
        S = sp.coo_matrix(
            (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
            shape=(self.n_cells, self.n_faces),
        ).tocsr()
        self._cache["S"] = S
        return S

    # ------------------------------------------------------------------
    # duals
    # ------------------------------------------------------------------
    def curl_dual(self):
        """``C_tilde`` (n_edges, n_faces) = ``C.T``: the dual curl (Ampere)."""
        if "C_tilde" not in self._cache:
            self._cache["C_tilde"] = self.curl().T.tocsr()
        return self._cache["C_tilde"]

    def divergence_dual(self):
        """``S_tilde`` (n_faces, n_cells) = ``S.T``: cell charge -> face flux."""
        if "S_tilde" not in self._cache:
            self._cache["S_tilde"] = self.divergence().T.tocsr()
        return self._cache["S_tilde"]

    def curl_e_to_h(self):
        """``C`` applied to edge voltages -- the Faraday ``dH/dt`` operator."""
        return self.curl()

    def curl_h_to_e(self):
        """``C.T`` applied to face fluxes -- the Ampere ``dE/dt`` operator."""
        return self.curl_dual()

    # ------------------------------------------------------------------
    # boundary conditions
    # ------------------------------------------------------------------
    def pec_edge_mask(self, walls=("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")):
        """Edges whose tangential component a PEC wall pins to zero.

        Returns a boolean array of length ``n_edges``; ``True`` means the edge
        is tangential to a PEC wall and its voltage is constrained to zero.
        Selecting all six walls closes the domain into a cavity.
        """
        wallset = set(walls)
        mask = np.zeros(self.n_edges, dtype=bool)
        nx, ny, nz = self.nx, self.ny, self.nz

        i, j, k = self._grid_ex()
        fixed = np.zeros(i.shape, dtype=bool)
        if "ymin" in wallset:
            fixed |= j == 0
        if "ymax" in wallset:
            fixed |= j == ny
        if "zmin" in wallset:
            fixed |= k == 0
        if "zmax" in wallset:
            fixed |= k == nz
        mask[self.idx_ex(i, j, k)] = fixed

        i, j, k = self._grid_ey()
        fixed = np.zeros(i.shape, dtype=bool)
        if "xmin" in wallset:
            fixed |= i == 0
        if "xmax" in wallset:
            fixed |= i == nx
        if "zmin" in wallset:
            fixed |= k == 0
        if "zmax" in wallset:
            fixed |= k == nz
        mask[self.idx_ey(i, j, k)] = fixed

        i, j, k = self._grid_ez()
        fixed = np.zeros(i.shape, dtype=bool)
        if "xmin" in wallset:
            fixed |= i == 0
        if "xmax" in wallset:
            fixed |= i == nx
        if "ymin" in wallset:
            fixed |= j == 0
        if "ymax" in wallset:
            fixed |= j == ny
        mask[self.idx_ez(i, j, k)] = fixed

        return mask

    def __repr__(self):  # pragma: no cover - cosmetic
        return (
            f"CellComplex(cells={self.nx}x{self.ny}x{self.nz}, "
            f"edges={self.n_edges}, faces={self.n_faces})"
        )
