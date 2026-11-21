"""Are the three third-party witnesses we already have still there, and still ours?

This repository has been citing a Zenodo DOI, two Software Heritage identifiers
and a Sigstore Rekor entry. Citations age: a DOI can be withdrawn, a snapshot can
be replaced, a log entry can be a number we typed wrong. So this tool asks each
service, live, and compares what comes back with what the repository claims.

    python3 tools/check_witnesses.py [--json]

What each one proves, and does not:
  Zenodo      the archive exists and holds the file whose SHA-256 we ship
  SWH         software heritage archived this repository at this snapshot
  Rekor       a public transparency log recorded this artifact's digest at time T

None of them proves anybody adopted the format. They prove the artifact exists
and has been seen by a third party - which is a different, and still useful,
claim.

Network access is required; CI does not run this, because a red CI caused by a
third party's outage teaches nobody anything.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

ZENODO_RECORD = 22821835
ZENODO_CONCEPT = 22821834
SWH_SNAPSHOT = "a901225b50ae3fe84f9f878b8c0d6b0399867e64"
SWH_ORIGIN = "819530c8be2adf6da901256ce9fd28063f8f1296"
REKOR_INDEX = 2883389783
ZIP = os.path.join(REPO, "dist", "uibc-core-0.2.1.zip")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "uibc-witness-audit"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def local_md5():
    if not os.path.isfile(ZIP):
        return None
    h = hashlib.md5()
    with open(ZIP, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def local_sha256():
    if not os.path.isfile(ZIP):
        return None
    h = hashlib.sha256()
    with open(ZIP, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def check_zenodo():
    out = {"service": "Zenodo", "ok": False, "detail": []}
    try:
        rec = get("https://zenodo.org/api/records/%d" % ZENODO_RECORD)
    except Exception as e:
        out["detail"].append("unreachable or refused: %s" % str(e)[:90])
        return out
    doi = rec.get("doi") or (rec.get("metadata") or {}).get("doi")
    concept = rec.get("conceptdoi")
    out["detail"].append("record %s exists, created %s" % (rec.get("id"), rec.get("created", "?")[:19]))
    out["detail"].append("version DOI %s / concept DOI %s" % (doi, concept))
    files = rec.get("files") or []
    names = []
    for f in files:
        key = f.get("key") or f.get("filename") or "?"
        ck = (f.get("checksum") or "").replace("md5:", "")
        names.append(key)
        out["detail"].append("file %s  %s" % (key, ("md5:" + ck) if ck else "(no checksum returned)"))
    mine = local_md5()
    if mine:
        out["detail"].append("local dist zip md5 %s" % mine)
        if any((f.get("checksum") or "").replace("md5:", "") == mine for f in files):
            out["detail"].append("the archived file is byte-for-byte the zip in dist/")
            out["ok"] = True
        else:
            out["detail"].append("no archived file matches the local zip")
    else:
        out["ok"] = bool(files)
    if concept and concept != "10.5281/zenodo.%d" % ZENODO_CONCEPT:
        out["detail"].append("concept DOI is %s, the repository claims 10.5281/zenodo.%d"
                             % (concept, ZENODO_CONCEPT))
        out["ok"] = False
    return out


def check_swh():
    out = {"service": "Software Heritage", "ok": False, "detail": []}
    try:
        snap = get("https://archive.softwareheritage.org/api/1/snapshot/%s/" % SWH_SNAPSHOT)
    except Exception as e:
        out["detail"].append("unreachable or refused: %s" % str(e)[:90])
        return out
    head = ((snap.get("branches") or {}).get("HEAD") or {})
    out["detail"].append("snapshot %s resolves, HEAD -> %s" % (snap.get("id", "?")[:12],
                                                               head.get("target", "?")))
    import urllib.parse
    try:
        origin = get("https://archive.softwareheritage.org/api/1/origin/%s/get/"
                     % urllib.parse.quote("https://github.com/zhaoxinghua09-cell/uibc-core", safe=""))
        url = origin.get("url", "")
        out["detail"].append("origin url %s" % url)
        # the ori SWHID is what CITATION.cff cites, so it is what has to match
        blob = json.dumps(origin)
        m = re.search(r"swh:1:ori:[0-9a-f]{40}", blob)
        found = m.group(0) if m else ""
        out["detail"].append("origin SWHID %s (repository claims swh:1:ori:%s)"
                             % (found or "?", SWH_ORIGIN))
        out["ok"] = (found == "swh:1:ori:" + SWH_ORIGIN
                     and url.startswith("https://github.com/zhaoxinghua09-cell/uibc-core"))
    except Exception as e:
        out["detail"].append("origin lookup failed: %s" % str(e)[:90])
    return out


def check_rekor():
    out = {"service": "Sigstore Rekor", "ok": False, "detail": []}
    try:
        entries = get("https://rekor.sigstore.dev/api/v1/log/entries?logIndex=%d" % REKOR_INDEX)
    except Exception as e:
        out["detail"].append("unreachable or refused: %s" % str(e)[:90])
        return out
    if not isinstance(entries, dict) or not entries:
        out["detail"].append("log index %d returned nothing" % REKOR_INDEX)
        return out
    uuid, entry = next(iter(entries.items()))
    import base64
    try:
        body = json.loads(base64.b64decode(entry.get("body", "")))
    except Exception as e:
        out["detail"].append("entry body is not readable: %s" % str(e)[:60])
        return out
    spec = (body.get("spec") or {})
    data = spec.get("data") or {}
    h = (data.get("hash") or {})
    out["detail"].append("entry %s… exists at logIndex %d" % (uuid[:16], entry.get("logIndex", REKOR_INDEX)))
    out["detail"].append("integratedTime %s" % entry.get("integratedTime", "?"))
    digest = h.get("value") if isinstance(h, dict) else None
    if digest:
        out["detail"].append("artifact sha256 %s" % digest)
        mine = local_sha256()
        out["detail"].append("local dist zip sha256 %s" % (mine or "(zip not present)"))
        out["ok"] = (mine == digest) if mine else True
    else:
        out["detail"].append("entry carries no sha256 hash object (kind %s)" % spec.get("kind"))
    return out


def main():
    results = [check_zenodo(), check_swh(), check_rekor()]
    ok_all = all(r["ok"] for r in results)
    if "--json" in sys.argv:
        print(json.dumps({"verdict": "OK" if ok_all else "MISMATCH", "witnesses": results},
                         indent=2, ensure_ascii=False))
    else:
        print("VERDICT: %s" % ("OK" if ok_all else "MISMATCH"))
        for r in results:
            print("  %-20s %s" % (r["service"], "ok" if r["ok"] else "MISMATCH"))
            for d in r["detail"]:
                print("      %s" % d)
        print("")
        print("These three witness the artifact, not adoption. Nobody else has")
        print("implemented this format, and no upstream change has been merged.")
    return 0 if ok_all else 3


if __name__ == "__main__":
    sys.exit(main())
