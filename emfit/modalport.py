"""Modal ports for the 3-D FIT solver.

A modal port reads and writes one *mode* of a waveguide cross-section.  It is a
pure projection device: :meth:`ModalPort.amplitude` projects the edge-voltage
vector onto a fixed transverse profile, and :meth:`ModalPort.inject` scatters
that profile back onto the same edges as a soft current source.

What this is, and what it is not
--------------------------------
* ``amplitude`` is **unweighted**.  It is a plain Euclidean inner product over
  the port plane's tangential edges -- no edge length, no dual face area, no
  power normalisation.  The number is *calibration free only in ratios*: a ratio
  of amplitudes of the same mode on the same port is meaningful, an absolute
  value is not, and it is not a power.
* ``inject`` writes a **soft source** on the profile.  It does not terminate the
  guide.  There is no absorbing port in this codebase, so a wave travelling back
  down the line reflects off the port plane (or off whatever PEC or PML the
  caller has there) exactly as it would with no port at all.  ``s11`` measured
  with this class needs a reflection-free time window, not a matched load.

DOF convention of a port plane
------------------------------
Flat edge vectors are three contiguous blocks, ``[ex | ey | ez]``, with the
block offsets ``off_ex = 0``, ``off_ey = n_ex``, ``off_ez = n_ex + n_ey``
(:class:`emfit.operators.CellComplex`), and each block is C order over
``Grid.edge_shape(axis)``.  A plane normal to ``axis`` at node layer ``index``
therefore owns its tangential edges in this order:

* the edges parallel to the first transverse axis (in ``"xyz"`` order): all
  cells along that axis, all point layers along the second;
* then the edges parallel to the second transverse axis: all point layers along
  the first, all cells along the second;

C order inside each family.  ``e_profile`` is 1-D over exactly that list.

``e_profile`` carries the mode's field components along the *positive* axis
directions, i.e. the same sense as the solver's edge voltages, so an edge
voltage vector and a profile of the same mode have a positive inner product.
"""

from __future__ import annotations

import numpy as np

__all__ = ["ModalPort", "s11"]

_AXES = "xyz"


# ---------------------------------------------------------------------------
# plane geometry: which edges lie in a node plane, and where they are
# ---------------------------------------------------------------------------
def _check_axis(axis):
    if axis not in _AXES:
        raise ValueError(f"axis must be one of 'x', 'y', 'z', got {axis!r}")
    return axis


def _cross_axes(axis):
    """The two axes transverse to ``axis``, in ``"xyz"`` order."""
    return tuple(a for a in _AXES if a != axis)


def _edge_index_fn(cc, axis):
    return {"x": cc.idx_ex, "y": cc.idx_ey, "z": cc.idx_ez}[axis]


def _plane_geometry(cc, axis, index):
    """Edge indices, midpoints, directions and lengths of a plane's edges.

    ``axis`` is the plane normal, ``index`` the node layer.  Returns a dict with
    ``edge`` (flat indices, in the order documented in the module docstring),
    ``mid`` ``(n, 3)`` midpoints, ``dir`` ``(n, 3)`` unit directions (exactly one
    nonzero component, ``+1``, i.e. the positive sense of the edge voltage) and
    ``length`` ``(n,)`` primary edge lengths.
    """
    axis = _check_axis(axis)
    grid = cc.grid
    n_layers = grid.nodes(axis)
    index = int(index)
    if not 0 <= index < n_layers:
        raise ValueError(
            f"plane index {index} is not a node layer of axis {axis!r}: "
            f"valid range is 0..{n_layers - 1}")

    u, v = _cross_axes(axis)
    edges, mids, dirs, lens = [], [], [], []
    for par in (u, v):
        oth = v if par == u else u
        n_par = grid.shape[_AXES.index(par)]      # cells along the edge axis
        n_oth = grid.nodes(oth)                   # point layers along the other
        ii, jj = np.meshgrid(np.arange(n_par), np.arange(n_oth), indexing="ij")
        coords = {par: ii, oth: jj, axis: np.full(ii.shape, index, dtype=int)}
        flat = np.asarray(
            _edge_index_fn(cc, par)(coords["x"], coords["y"], coords["z"])
        ).ravel().astype(np.intp)

        mid = np.empty((flat.size, 3), dtype=float)
        dirv = np.zeros((flat.size, 3), dtype=float)
        length = np.ones(flat.size, dtype=float)
        for a in _AXES:
            pa = _AXES.index(a)
            arr = np.asarray(getattr(grid, a), dtype=float)
            if a == par:
                w = np.asarray(grid.widths(a), dtype=float)
                mid[:, pa] = (arr[ii] + 0.5 * w[ii]).ravel()
                length = np.broadcast_to(w[ii], ii.shape).ravel().astype(float)
                dirv[:, pa] = 1.0
            else:
                val = arr[coords[a]]
                mid[:, pa] = np.broadcast_to(val, ii.shape).ravel()
        edges.append(flat)
        mids.append(mid)
        dirs.append(dirv)
        lens.append(length)

    return {
        "edge": np.concatenate(edges),
        "mid": np.vstack(mids),
        "dir": np.vstack(dirs),
        "length": np.concatenate(lens),
    }


# ---------------------------------------------------------------------------
# the port
# ---------------------------------------------------------------------------
class ModalPort:
    """One mode on one node plane of a :class:`CellComplex`.

    Parameters
    ----------
    cc : CellComplex
        The cell complex the port lives on.
    axis : {'x', 'y', 'z'}
        Normal of the port plane.
    index : int
        Node layer of the port plane along ``axis``; the plane sits at
        ``getattr(cc.grid, axis)[index]``.
    e_profile : array_like
        The mode's field on the plane's tangential edges, 1-D, in the order
        documented in the module docstring.  Its normalisation does not affect
        :meth:`amplitude` (which divides by ``sum(|e_profile|**2)``); it is the
        amplitude unit of :meth:`inject`.
    beta : float, optional
        Propagation constant of the mode [rad/m]; needed only by
        :meth:`forward_backward`.
    z0 : float, optional
        Modal impedance [ohm], carried for the caller.  Nothing here divides by
        it: :meth:`amplitude` is a field projection, not a power one.
    name : str, optional
        Label.  Kept last so that ``ModalPort(cc, 'x', 3, profile)`` reads as
        the port it is.
    """

    def __init__(self, cc, axis, index, e_profile, beta=None, z0=None, name=""):
        self.cc = cc
        self.axis = _check_axis(axis)
        self.index = int(index)
        geom = _plane_geometry(cc, self.axis, self.index)

        profile = np.asarray(e_profile)
        if profile.ndim != 1:
            raise ValueError(
                "e_profile must be 1-D over the port plane's tangential edges, "
                f"got ndim={profile.ndim}")
        if profile.size != geom["edge"].size:
            raise ValueError(
                f"e_profile has {profile.size} entries but the plane "
                f"{self.axis}={self.index} has {geom['edge'].size} tangential "
                "edges")
        if not np.all(np.isfinite(profile.astype(complex))):
            raise ValueError("e_profile must be finite")
        if not np.any(profile != 0):
            raise ValueError("e_profile is identically zero: there is no mode")

        self.e_profile = profile
        self.beta = None if beta is None else float(beta)
        if self.beta is not None and not np.isfinite(self.beta):
            raise ValueError(f"beta must be finite when given, got {beta!r}")
        self.z0 = None if z0 is None else float(z0)
        if self.z0 is not None and not self.z0 > 0.0:
            raise ValueError(f"z0 must be positive when given, got {z0!r}")
        self.name = str(name)
        self._geom = geom

    # -- construction ----------------------------------------------------
    @classmethod
    def from_profile(cls, cc, axis, index, e_profile, beta=None, z0=None):
        """A port from a hand-built profile on the plane's tangential edges."""
        return cls(cc, axis, index, e_profile, beta=beta, z0=z0)

    @classmethod
    def from_mode2d(cls, mode, cc, axis, index):
        """A port from a :class:`emfit.mode2d.Mode2D`'s ``e_t``.

        The 2-D cross-section mesh must be the *same structured rectangle* as
        the 3-D port plane: built by :func:`emfit.mode2d.structured_mesh`,
        :func:`emfit.mode2d.mesh_from_grid` or :func:`emfit.mode2d.box_mesh`, so
        that it carries ``grid_axes`` with node coordinates equal to the 3-D
        cross-section's.  Every tangential edge of the plane is then matched to
        the collinear axis-aligned 2-D edge by midpoint and length, and the sign
        is taken from that edge's ``(lo, hi)`` global orientation.  The
        triangulation's diagonal edges have no 3-D counterpart and are skipped.

        Raises
        ------
        ValueError
            If the mesh is not a structured rectangle on this cross-section, or
            if any plane edge has no matching axis-aligned 2-D edge.
        """
        axis = _check_axis(axis)
        mesh = mode.mesh
        axes2 = tuple(getattr(mesh, "grid_axes", ()) or ())
        if len(axes2) != 2:
            raise ValueError(
                "from_mode2d needs a 2-D mesh that came from a structured "
                "rectangle (mode2d.structured_mesh / mesh_from_grid / "
                "box_mesh); this mesh has no grid_axes, so it is not the same "
                "structured rectangle as the 3-D cross-section")
        axes2 = (np.asarray(axes2[0], dtype=float),
                 np.asarray(axes2[1], dtype=float))

        geom = _plane_geometry(cc, axis, index)
        u, v = _cross_axes(axis)

        span = float(max(np.ptp(axes2[0]), np.ptp(axes2[1]))) or 1.0
        atol = 1e-12 * span

        chosen = None
        for a1, a2 in ((u, v), (v, u)):
            c1 = np.asarray(getattr(cc.grid, a1), dtype=float)
            c2 = np.asarray(getattr(cc.grid, a2), dtype=float)
            if (c1.size == axes2[0].size and c2.size == axes2[1].size
                    and np.allclose(c1, axes2[0], rtol=0.0, atol=atol)
                    and np.allclose(c2, axes2[1], rtol=0.0, atol=atol)):
                chosen = (a1, a2)
                break
        if chosen is None:
            raise ValueError(
                f"the 2-D mesh's node coordinates do not match the 3-D "
                f"cross-section of axis {axis!r} at plane {index}: the 2-D mesh "
                "is not the same structured rectangle as the 3-D cross-section "
                f"(2-D nodes per axis: {axes2[0].size}, {axes2[1].size}; 3-D "
                f"nodes per axis: "
                f"{tuple(cc.grid.nodes(a) for a in _cross_axes(axis))})")
        a1, a2 = chosen
        p1, p2 = _AXES.index(a1), _AXES.index(a2)

        nodes = np.asarray(mesh.nodes, dtype=float)
        lo = np.asarray(mesh.edges[:, 0], dtype=np.intp)
        hi = np.asarray(mesh.edges[:, 1], dtype=np.intp)
        dp = nodes[hi] - nodes[lo]
        len2 = np.linalg.norm(dp, axis=1)
        mid2 = 0.5 * (nodes[hi] + nodes[lo])
        with np.errstate(invalid="ignore", divide="ignore"):
            unit2 = dp / len2[:, None]

        tol = 1e-9 * span
        buckets = {}
        for e in range(len2.size):
            key = (round(mid2[e, 0] / tol), round(mid2[e, 1] / tol),
                   round(len2[e] / tol))
            buckets.setdefault(key, []).append(e)

        et = np.asarray(mode.e_t)
        profile = np.zeros(geom["edge"].size,
                           dtype=np.result_type(et.dtype, np.float64))
        missing = []
        for k in range(geom["edge"].size):
            key = (round(geom["mid"][k, p1] / tol),
                   round(geom["mid"][k, p2] / tol),
                   round(geom["length"][k] / tol))
            du, dv = geom["dir"][k, p1], geom["dir"][k, p2]
            for e in buckets.get(key, ()):
                dot = unit2[e, 0] * du + unit2[e, 1] * dv
                if dot > 1.0 - 1e-9:          # collinear, same sense
                    profile[k] = et[e]
                    break
                if dot < -1.0 + 1e-9:         # collinear, opposite sense
                    profile[k] = -et[e]
                    break
            else:
                missing.append(k)
        if missing:
            raise ValueError(
                f"{len(missing)} of {geom['edge'].size} tangential edges of the "
                f"plane {axis}={index} have no matching axis-aligned edge in "
                "the 2-D mesh (first at midpoint "
                f"{np.array2string(geom['mid'][missing[0]], precision=6)}): the "
                "2-D mesh is not the same structured rectangle as the 3-D "
                "cross-section")

        beta = getattr(mode, "beta", None)
        beta = None if beta is None or not np.isfinite(beta) else float(beta)
        return cls(cc, axis, index, profile, beta=beta, z0=None)

    # -- projection ------------------------------------------------------
    def amplitude(self, field):
        """Projection of an edge-voltage vector onto the mode, ``complex``.

        ``a = sum(conj(e_profile) * field[plane edges]) / sum(|e_profile|**2)``.

        Unweighted: no metric enters, so this is not a power normalisation and
        the absolute value is meaningless.  It is calibration free only in
        ratios of amplitudes of this same mode on this same port.
        """
        f = np.asarray(field).ravel()
        denom = float(np.sum(np.abs(self.e_profile) ** 2))
        if denom == 0.0:
            raise ValueError("e_profile is identically zero")
        return complex(np.sum(np.conj(self.e_profile) * f[self._geom["edge"]])
                       / denom)

    # -- sourcing --------------------------------------------------------
    def inject(self, strength, shape=None):
        """An ``n_edges`` current vector [A] carrying ``strength * e_profile``.

        The profile is written on the port plane's tangential edges only; every
        other entry is exactly zero.  ``shape`` optionally scales it by a time
        sample: ``inject(1.0, shape=np.sin(2*np.pi*f0*n*dt))``.

        This is a **soft source**, not a matched port terminator: the guide is
        not terminated by it, and there is no absorbing port in this codebase.
        """
        scale = strength if shape is None else strength * shape
        values = np.multiply(scale, self.e_profile)
        values = np.broadcast_to(values, self.e_profile.shape).astype(
            np.result_type(np.asarray(values).dtype, np.float64), copy=True)
        vec = np.zeros(self.cc.n_edges, dtype=values.dtype)
        vec[self._geom["edge"]] = values
        return vec

    # -- two-station decomposition ---------------------------------------
    def forward_backward(self, a1, x1, a2, x2):
        """Split two station amplitudes into forward/backward, at the port plane.

        Solves ``a(x) = af exp(-i beta (x - xp)) + ab exp(+i beta (x - xp))``
        for ``af``, ``ab``, where ``xp = getattr(cc.grid, axis)[index]`` is the
        port plane.  Two stations at different distances are required, and the
        amplitudes must be phasors of the same mode at the same frequency.
        """
        if self.beta is None:
            raise ValueError(
                "forward_backward needs the mode's propagation constant; this "
                "port was built with beta=None")
        xp = float(np.asarray(getattr(self.cc.grid, self.axis))[self.index])
        d1 = float(x1) - xp
        d2 = float(x2) - xp
        if d1 == d2:
            raise ValueError(
                "the two stations must be at different distances from the port "
                f"plane {self.axis}={self.index}, got {d1!r} for both")
        b = float(self.beta)
        mat = np.array([[np.exp(-1j * b * d1), np.exp(+1j * b * d1)],
                        [np.exp(-1j * b * d2), np.exp(+1j * b * d2)]],
                       dtype=complex)
        af, ab = np.linalg.solve(mat, np.array([complex(a1), complex(a2)],
                                               dtype=complex))
        return complex(af), complex(ab)


def s11(port, a_forward, a_backward):
    """Reflection coefficient at the port plane, ``a_backward / a_forward``.

    ``a_forward`` and ``a_backward`` are the two amplitudes
    :meth:`ModalPort.forward_backward` returns, both already referred to the
    port plane, so this ratio needs no further de-embedding.  Undefined for a
    vanishing forward wave, which is raised rather than returned as a silent
    infinity.
    """
    if not isinstance(port, ModalPort):
        raise TypeError(f"port must be a ModalPort, got {type(port).__name__}")
    af = complex(a_forward)
    if af == 0.0:
        raise ValueError("a_forward is zero: s11 is undefined")
    return complex(a_backward) / af
