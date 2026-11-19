"""Check that the vendored documents are the documents we say they are.

A clause verified against a local file proves only that the file and the quote agree. It
says nothing about whether the file is the publisher's text - a local edit would pass
every quote check. So each vendored file carries a recorded sha256 and the URL it came
from; this tool re-hashes the local file and, with `--upstream`, re-downloads it and
compares. Offline it checks the local bytes only, and says so.

    python tools/check_sources.py             # local bytes vs recorded hashes
    python tools/check_sources.py --upstream  # also re-download and compare
"""
import hashlib, io, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "docs", "spec-sources")
MANIFEST = os.path.join(SRC, "MANIFEST.json")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main(argv):
    want_upstream = "--upstream" in argv
    manifest = json.load(io.open(MANIFEST, encoding="utf-8"))
    docs = manifest["documents"]
    problems, checked = [], 0

    for doc in docs:
        path = os.path.join(REPO, "docs", "spec-sources", doc["file"])
        if not os.path.isfile(path):
            problems.append((doc["file"], "file missing"))
            continue
        body = io.open(path, "rb").read()
        if len(body) != doc["bytes"]:
            problems.append((doc["file"], "size %d != recorded %d" % (len(body), doc["bytes"])))
        if sha(body) != doc["sha256"]:
            problems.append((doc["file"], "sha256 differs from the manifest"))
        checked += 1
        if want_upstream and "url" in doc:
            try:
                import urllib.request
                req = urllib.request.Request(doc["url"],
                                             headers={"User-Agent": "uibc-core source check"})
                with urllib.request.urlopen(req, timeout=45) as r:
                    fresh = r.read()
                if sha(fresh) != doc["sha256"]:
                    problems.append((doc["file"], "upstream no longer matches the manifest"))
            except Exception as exc:  # noqa: BLE001 - reported as unknown, not as pass
                problems.append((doc["file"], "upstream unreachable: %s" % exc))

    # every clause must point at a document that is in the manifest
    grounds = json.load(io.open(os.path.join(REPO, "conformance", "oracle", "grounds.json"),
                                encoding="utf-8"))["cases"]
    # grounds.json writes paths with forward slashes, so build them the same way
    listed = {"docs/spec-sources/" + d["file"] for d in docs}
    clause_sources = {row["clause_source"] for row in grounds if row.get("clause_source")}
    unlisted = sorted(clause_sources - listed)
    for src in unlisted:
        problems.append((src, "quoted but not described in MANIFEST.json"))

    print("documents in manifest: %d; local bytes verified: %d" % (len(docs), checked))
    print("upstream re-check: %s" % ("done" if want_upstream else "not done (offline mode)"))
    print("clause sources covered by the manifest: %d" % len(clause_sources - set()))
    for name, why in problems:
        print("  PROBLEM: %s - %s" % (name, why))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
