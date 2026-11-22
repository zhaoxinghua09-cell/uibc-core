#!/usr/bin/env python3
"""Write conformance/MANIFEST.sha256 (sha256sum-compatible) over this package.

Why this exists: a downloadable suite is only useful if a stranger can prove
the bytes they got are the bytes we published. `sha256sum -c MANIFEST.sha256`
is the cheapest such proof that every operating system already ships, so the
manifest is written in exactly that format and nothing else.

    python tools/build_conformance_manifest.py            # write
    python tools/build_conformance_manifest.py --check    # verify, exit 1 on drift
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conformance")
OUT_NAME = "MANIFEST.sha256"
SKIP_DIRS = {"__pycache__"}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def entries(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if name == OUT_NAME:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            yield rel, full


def render(root: str) -> str:
    lines = ["%s  %s" % (sha256(full), rel) for rel, full in entries(root)]
    return "\n".join(sorted(lines, key=lambda s: s.split("  ", 1)[1])) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify instead of write")
    a = ap.parse_args()
    out = os.path.join(ROOT, OUT_NAME)
    want = render(ROOT)
    if a.check:
        if not os.path.exists(out):
            print("MANIFEST.sha256 missing; run without --check first")
            return 1
        got = open(out, encoding="utf-8").read()
        if got != want:
            print("MANIFEST.sha256 does not match the tree")
            for line in got.splitlines():
                if line not in want:
                    print("  stale:", line)
            return 1
        print("MANIFEST.sha256 ok: %d files" % len(want.strip().splitlines()))
        return 0
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(want)
    print("wrote %s: %d files" % (out, len(want.strip().splitlines())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
