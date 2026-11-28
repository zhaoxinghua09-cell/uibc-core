# syntax=docker/dockerfile:1
#
# The environment the four outsider steps are re-run in, fixed by digest.
#
# What this fixes: the interpreter and the OS packages under it (from the pinned
# base image) and every third-party module the run imports (four wheels, pinned by
# sha256 in docker/requirements-verify.txt). Nothing else is installed.
#
# What this does not fix: the machine, the kernel, the clock, and the CPU. Two
# runs of this image produce the same pytest report; they are not bit-identical
# container filesystems, because layer timestamps are the build clock. It is a
# pinned *environment*, not a reproducible one - the page next to the claim says
# so in those words.
#
# The base is a name the pin owns: tools/check_base_image_pin.py refuses a build
# whose ARG disagrees with docker/base-image.pin, so editing one without the other
# cannot pass CI.

ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:f0fa218d5b06f9b9235024fa061cde2cb141f726de52134471053d2d9b5324a3
FROM ${PYTHON_IMAGE}

# Determinism-shaped settings: no .pyc written (they would embed mtimes), a fixed
# hash seed (dict order in the JSON the tools emit), UTC, and a locale that sorts
# the same way as the CI runner's.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC

WORKDIR /repo

COPY docker/requirements-verify.txt /tmp/requirements-verify.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements-verify.txt \
    && python -c "import pytest, sys; print('pytest', pytest.__version__, 'on', sys.version.split()[0])"

# The second implementation's interpreter, pinned by tarball digest.
#
# One of the 41 tests shell-outs to `node` and skips itself when node is absent,
# so without this line the image reported "40 passed, 1 skipped" and passed the
# fourth step on a slightly narrower set than the host does. Node is installed from
# the pinned tarball by docker/install-node.py - standard library only, no apt, no
# unpinned Debian package - and the digest is re-checked before anything is
# extracted. Only after that can the container also run the cross-implementation
# digest check (`tools/tree_digest_second_impl.py --check`), which the workflow
# does as a fifth step.
ARG NODE_TARBALL=https://nodejs.org/dist/v26.13.1/node-v26.13.1-linux-x64.tar.xz
ARG NODE_SHA256=5c063e46bab0fbc1c17cc445d7ff129cbdcd0471be6ed83b6ab864f8143bc864

COPY docker/install-node.py /tmp/install-node.py
RUN NODE_TARBALL="${NODE_TARBALL}" NODE_SHA256="${NODE_SHA256}" \
    python /tmp/install-node.py \
    && node --version \
    && node -e "console.log('node reports', process.version, process.arch, process.platform)"

# The published membership, not a subset: --check compares the tree it finds here
# against docs/TRACKED-FILES.txt, so a .dockerignore that dropped a tracked file
# would fail the run rather than quietly shrink it.
COPY . /repo

# Default entry: re-run the four steps here rather than only verify a receipt that
# was sealed elsewhere. `--check` is the other half, and the workflow runs both:
# the same image must be able to reproduce the steps and to agree with the receipt
# that ships in it.
CMD ["python", "tools/outsider_rerun.py", "--run"]
