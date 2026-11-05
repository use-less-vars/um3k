# Toolchain install: openEMS + pyvista (2026-11-05)

Two machines are involved. Nothing in this document was installed by the agent:
the vault Dockerfile is not writable from inside a session, and there is no
host-execution tool. Both install paths are specified here and executed by the
operator.

## openEMS cannot be `pip install`ed

- PyPI: `pip index versions openems` -> `ERROR: No matching distribution found` (exit 1).
  Identical for `csxcad`.
- **Trap:** PyPI `pyopenems` 1.8.0 does exist - `py3-none-any`, pure Python - and is a
  *websocket client* (`python -m openems --server-url='ws://localhost:8081' ...`),
  not the solver. `pip install pyopenems` succeeds and buys nothing.
- conda-forge: `api.anaconda.org/package/conda-forge/openems` -> 404;
  `api.anaconda.org/search?name=openems` -> `[]`. Same for `csxcad`.

## The base image tag has to change

The workspace image was built from `python:3.12-slim`, which now resolves to
Debian 13 (trixie).

- `dists/trixie/main/source/Sources.xz` and `dists/trixie/main/binary-amd64/Packages.xz`:
  **0** hits for `Package: openems`, `Package: libcsxcad0`, `Package: python3-openems`.
  The only `openems` string left in the trixie binary index is a `Recommends:` inside
  the `electronics-radio-dev` metapackage. contrib/non-free: 0 as well.
- `dists/bookworm/main/...`: **1** hit each, `openems 0.0.35+git20190103.6a75e98+dfsg.1-3.2`.
- Controls: the same endpoints returned full `stable`/`testing`/`unstable` rows for
  `numpy`, `vtk9` and `xvfb`, so the trixie null result is a real absence, not a broken query.
- `sources.debian.org` and `packages.debian.org` were **unusable** for this: both sit behind a
  Varnish proof-of-work interstitial that returns HTTP 200 with a 3.3 kB "I Challenge Thee"
  page. The PoW was not solved (it is an anti-scraper control); `api.ftp-master.debian.org/madison`
  and direct index streaming were used instead.

Therefore: `FROM python:3.12-slim-bookworm`.

## Two interpreters, deliberately

bookworm's `python3-openems` installs bindings for the distro interpreter (3.11), which is
*not* the image's 3.12. Rather than rebuild the bindings, the two run side by side:

- `/usr/local/bin/python3` (3.12) - emfit.
- `/usr/bin/python3` (3.11) - openEMS / CSXCAD, invoked as a subprocess.
- Interface between them: HDF5 files. Hence `h5py` (3.12 side, pip) and
  `python3-h5py` (3.11 side, apt).

## Activation

1. Copy `docs/infra/Dockerfile.runtime.proposed` over
   `~/.thoughtmachine/workspaces/gentle-wolf-72/Dockerfile`.
2. `requirements.txt` and `pyproject.toml` are already committed (pyvista, h5py).
3. Rebuild the workspace runtime image. `WITH_OPENEMS=1` is the default;
   `--build-arg WITH_OPENEMS=0` omits the reference if the apt path ever breaks, so the
   pyvista half can still land.
4. The build itself asserts the reference: `/usr/bin/python3 -c "import CSXCAD, openEMS"`.

## Verifying the pyvista half

The image has no display. `xvfb` is installed for that reason: render under
`xvfb-run -a`, or call `pyvista.start_xvfb()` before creating a plotter. A GLX error
from `Plotter(off_screen=True)` means the xvfb path was not taken, not that VTK is broken.

## Known costs and open items

- openEMS 0.0.35 dates from 2019. Adequate as an independent cross-check; not a current engine.
- Image growth roughly 600 MB - 1 GB (VTK wheel + openEMS + xvfb + mesa).
- Host-native install is a separate path and is not specified here; the recommended host
  route is a `debian:bookworm-slim` container rather than polluting the host.
