"""Does the index still serve the bytes we pinned on another channel?

Three things have to agree, and any two agreeing is not enough:

  the release asset   what we published as "this is what PyPI serves"
  the index           what PyPI says it serves right now
  the download        the bytes an installer would actually receive

If the asset and the index disagree, the pin is stale or was forged. If the index
and the download disagree, a mirror or a proxy is serving something else. Both
are worth knowing, and neither is visible from inside one channel.

    python3 tools/check_pins.py [project] [version]

Exit 0 when all three agree.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import urllib.request

PROJECT = sys.argv[1] if len(sys.argv) > 1 else "uibc-core"
VERSION = sys.argv[2] if len(sys.argv) > 2 else "0.4.0"
ASSET = "https://github.com/zhaoxinghua09-cell/uibc-core/releases/download/release-pins-%s/uibc-core-%s.sha256" % (VERSION, VERSION)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-pin-audit"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-pin-audit"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def sha256_of(url):
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-pin-audit"})
    h = hashlib.sha256()
    n = 0
    with urllib.request.urlopen(req, timeout=90) as r:
        for c in iter(lambda: r.read(1 << 16), b""):
            h.update(c)
            n += len(c)
    return h.hexdigest(), n


def main():
    print("channel 1 (release asset) : %s" % ASSET)
    pinned = {}
    for line in get_text(ASSET).splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            parts = line.split()
            if len(parts) == 2:
                pinned[parts[1]] = parts[0]

    meta = get_json("https://pypi.org/pypi/%s/%s/json" % (PROJECT, VERSION))
    served = {f["filename"]: f["digests"]["sha256"] for f in meta.get("urls") or []}
    print("channel 2 (PyPI index)    : %d artefact(s)" % len(served))

    ok = True
    for name, digest in sorted(served.items()):
        p = pinned.get(name)
        if p is None:
            print("  %-34s not in the pin file" % name)
            ok = False
            continue
        if p != digest:
            print("  %-34s MISMATCH  pinned %s  index %s" % (name, p[:16], digest[:16]))
            ok = False
            continue
        url = next(f["url"] for f in meta["urls"] if f["filename"] == name)
        got, size = sha256_of(url)
        same = got == digest
        print("  %-34s pinned=index=%s  download=%s (%d bytes) %s"
              % (name, digest[:16], got[:16], size, "ok" if same else "MISMATCH"))
        ok = ok and same

    for name in pinned:
        if name not in served:
            print("  %-34s pinned but no longer served" % name)
            ok = False

    print("")
    print("VERDICT: %s" % ("OK - the pin, the index and the download agree" if ok else "MISMATCH"))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
