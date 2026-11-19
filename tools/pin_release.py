"""Pin the bytes that PyPI actually serves, and check them again later.

A version number is not a promise about bytes. `uibc-core 0.4.0` can be
re-uploaded, yanked, or served from a mirror that is not the index. So this tool
asks PyPI what it is serving right now, writes that down as a pin, and - with
`--verify` - downloads the artefacts and recomputes the digests to see whether
the pin still holds.

    python3 tools/pin_release.py uibc-core 0.4.0            # write anchors/pins/...
    python3 tools/pin_release.py uibc-core 0.4.0 --verify   # download and recompute

The pin file is plain text so that a human, or `sha256sum -c`, can use it
without this repository:

    <sha256>  <filename>

Exit 0 when every digest matches what PyPI serves; 3 when anything differs.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINS = os.path.join(REPO, "anchors", "pins")


def index(project, version):
    url = "https://pypi.org/pypi/%s/%s/json" % (project, version)
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-release-pin"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def artefacts(meta):
    out = []
    for f in meta.get("urls") or []:
        out.append({
            "filename": f["filename"],
            "sha256": f["digests"]["sha256"],
            "size": f["size"],
            "upload_time": f.get("upload_time_iso_8601") or f.get("upload_time"),
            "url": f["url"],
        })
    return sorted(out, key=lambda x: x["filename"])


def render(project, version, items):
    lines = ["# %s %s - bytes as served by PyPI" % (project, version), ""]
    for it in items:
        lines.append("%s  %s" % (it["sha256"], it["filename"]))
    lines.append("")
    for it in items:
        lines.append("# %s  %d bytes  uploaded %s" % (it["filename"], it["size"], it["upload_time"]))
        lines.append("# %s" % it["url"])
    return "\n".join(lines) + "\n"


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-release-pin"})
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=90) as r, open(dest, "wb") as fh:
        for chunk in iter(lambda: r.read(1 << 16), b""):
            h.update(chunk)
            fh.write(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    project, version = sys.argv[1], sys.argv[2]
    verify = "--verify" in sys.argv

    meta = index(project, version)
    items = artefacts(meta)
    if not items:
        print("no artefacts returned for %s %s" % (project, version))
        return 3

    print("%s %s: %d artefact(s) served" % (project, version, len(items)))
    ok = True
    for it in items:
        print("  %-34s %s  %d bytes" % (it["filename"], it["sha256"][:16], it["size"]))
        if it["size"] == 0:
            ok = False
            print("    ZERO BYTES - the index is serving an empty file")

    if verify:
        tmp = tempfile.mkdtemp(prefix="uibc-pin-")
        for it in items:
            dest = os.path.join(tmp, it["filename"])
            got, size = download(it["url"], dest)
            same = got == it["sha256"] and size == it["size"]
            print("  downloaded %-30s %s (%d bytes) %s"
                  % (it["filename"], got[:16], size, "match" if same else "MISMATCH"))
            ok = ok and same
        if not ok:
            print("VERDICT: MISMATCH - what PyPI served is not what the index declared")
            return 3

    os.makedirs(PINS, exist_ok=True)
    path = os.path.join(PINS, "%s-%s.sha256" % (project, version))
    if verify and os.path.isfile(path):
        pinned = set()
        for line in open(path, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                pinned.add(line.split()[0])
        missing = [i["filename"] for i in items if i["sha256"] not in pinned]
        print("pin file               : anchors/pins/%s-%s.sha256" % (project, version))
        print("still holds            : %s" % ("yes" if not missing else "NO (%s)" % missing))
        ok = ok and not missing
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render(project, version, items))
        print("pin written            : anchors/pins/%s-%s.sha256" % (project, version))

    print("")
    print("VERDICT: %s" % ("OK" if ok else "MISMATCH"))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
