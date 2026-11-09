# EXPERIMENTAL REFERENCE SOLVER -- not the main runtime.
#
# This image exists only to prove that a real finite-difference time-domain
# electromagnetic solve executes end to end from Python. Nothing in the EE
# toolchain imports it; nothing here is a physics validation. It is kept as
# reproducible infrastructure so the finding can be re-checked later.
#
# Pinned apt package versions (verified by introspection inside the built image):
#   openems        0.0.35+git20190103.6a75e98+dfsg.1-3.2
#   libcsxcad0 / python3-openems  same upstream source, CSXCAD python bindings 0.6.2
#   python 3.11.2 (Debian bookworm system python3)
#   numpy >= 1.24 -- this is why openEMS/ports.py needs the np.float shim,
#   see the trap list in docker/openems/README.md and docker/openems/smoke_solve.py.
#
# Measured image size: 1.36 GiB (docker image id 87494475c95d, tagged openems:bookworm).
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        openems \
        libcsxcad0 \
        python3-openems \
        python3-h5py \
        python3-numpy \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# The build context is docker/openems (see README.md), so this COPY source is
# context-relative. Building from the repo root instead would require the
# source path docker/openems/build_A_referee.py.
COPY build_A_referee.py /work/
