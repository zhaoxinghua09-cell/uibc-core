#!/usr/bin/env python3
"""Unpack the pinned Node tarball, with the standard library and nothing else.

The image installs no apt packages: `python:3.13-slim-bookworm` is Debian slim and
does not ship curl, and adding curl would mean adding an unpinned Debian package to
an image whose claim is that its contents are fixed. urllib downloads, hashlib
verifies, tarfile (lzma) unpacks. If the bytes are not the pinned bytes, nothing is
extracted and the build stops.

Reads NODE_TARBALL and NODE_SHA256 from the environment, which the Dockerfile passes
from the ARGs that docker/node.pin owns.
"""

import hashlib
import io
import os
import shutil
import sys
import tarfile
import urllib.request

PREFIX = "/usr/local/lib/nodejs"
LINKS = ("node", "npm", "npx")


def main():
    url = os.environ["NODE_TARBALL"]
    want = os.environ["NODE_SHA256"]
    if len(want) != 64 or any(c not in "0123456789abcdef" for c in want):
        sys.exit(f"NODE_SHA256 is not a 64-hex sha256: {want!r}")

    print(f"node: fetching {url}")
    with urllib.request.urlopen(url, timeout=300) as r:
        data = r.read()
    got = hashlib.sha256(data).hexdigest()
    print(f"node: {len(data)} bytes, sha256 {got}")
    if got != want:
        sys.exit(f"node: sha256 mismatch, refusing to unpack\n  pinned {want}\n  got    {got}")

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as tf:
        members = tf.getmembers()
        tops = {m.name.split("/")[0] for m in members}
        if len(tops) != 1:
            sys.exit(f"node: tarball has {len(tops)} top-level entries, expected one")
        top = tops.pop()
        if not top.startswith("node-v"):
            sys.exit(f"node: unexpected top-level directory {top!r}")
        shutil.rmtree(PREFIX, ignore_errors=True)
        os.makedirs(PREFIX, exist_ok=True)
        tf.extractall(PREFIX)                       # noqa: S202 - pinned bytes, single root

    root = os.path.join(PREFIX, top)
    for name in LINKS:
        src = os.path.join(root, "bin", name)
        dst = os.path.join("/usr/local/bin", name)
        if os.path.exists(src):
            if os.path.lexists(dst):
                os.unlink(dst)
            os.symlink(src, dst)
    print("node:", os.path.join(root, "bin", "node"))


if __name__ == "__main__":
    main()
