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

# The published membership, not a subset: --check compares the tree it finds here
# against docs/TRACKED-FILES.txt, so a .dockerignore that dropped a tracked file
# would fail the run rather than quietly shrink it.
COPY . /repo

CMD ["python", "tools/outsider_rerun.py", "--check"]
