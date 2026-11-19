"""Put the anchor and the package back together after they were split apart.

`anchors/001/anchor.json` lives in the repository, next to the package it pins.
That is convenient and it is also the weakest form of an anchor: whoever can
rewrite the package can rewrite the anchor in the same commit.

So the same anchor is also published as a release asset - a different channel.
This tool takes the **anchor from the release** and the **package from the
repository**, reassembles them, and asks the verifier whether the two still
belong together. If they do, the split is real: a change to the package that
forgets the release channel is caught.

    python3 tools/check_channel.py

Exit 0 when the two channels agree and the reassembled bundle verifies.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(REPO, "anchors", "001")
URL = "https://github.com/zhaoxinghua09-cell/uibc-core/releases/download/anchor-001/anchor.json"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-channel-audit"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as fh:
        fh.write(r.read())


def main():
    tmp = tempfile.mkdtemp(prefix="uibc-channel-")
    try:
        remote = os.path.join(tmp, "anchor.json")
        fetch(URL, remote)
        local_path = os.path.join(LOCAL, "anchor.json")

        same = sha256(remote) == sha256(local_path)
        print("anchor from the release : %s" % URL)
        print("repo copy               : anchors/001/anchor.json")
        print("sha256 equal            : %s" % ("yes" if same else "NO"))

        a = json.load(open(remote, encoding="utf-8"))
        print("seq %s  key_id %s  head %s" % (a["seq"], a["key_id"][:16], a["checkpoint_head"][:26]))

        # the package comes from the repository, the anchor comes from the release
        bundle = os.path.join(tmp, "bundle")
        os.makedirs(bundle)
        shutil.copytree(os.path.join(LOCAL, "package"), os.path.join(bundle, "package"))
        shutil.copy(remote, os.path.join(bundle, "anchor.json"))

        r = subprocess.run([sys.executable, "tools/anchor_check.py", bundle],
                           cwd=REPO, capture_output=True, text=True, timeout=180)
        verdict = "ANCHORED" if "ANCHORED" in r.stdout else ("FAIL" if "FAIL" in r.stdout else "?")
        print("reassembled bundle      : %s" % verdict)
        for line in r.stdout.splitlines():
            if line.startswith("result:"):
                print("verifier                : %s" % line.strip())

        ok = same and verdict == "ANCHORED"
        print("")
        print("VERDICT: %s" % ("OK - the package cannot rewrite this anchor" if ok else "MISMATCH"))
        return 0 if ok else 3
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
