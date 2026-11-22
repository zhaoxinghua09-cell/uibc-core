#!/usr/bin/env python3
"""One command a stranger can run on a downloaded conformance package:

  1. every file matches MANIFEST.sha256 (byte-level, no network);
  2. the shipped 0.5.0 archive matches the published pin (name, size, sha256);
  3. coverage.json is consistent with manifest.json (no case names an unknown check);
  4. the suite runs against this repository's verifier and passes.

Steps 1-3 need no network and no account. Step 4 uses only the code in this
checkout, so it also answers "is the suite still green on this machine".

    python tools/check_vector_package.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CONF = os.path.join(ROOT, "conformance")
MANIFEST = os.path.join(CONF, "MANIFEST.sha256")
COVERAGE = os.path.join(CONF, "coverage.json")

# The archive we published, and what a downloader should be able to match.
PINNED_ARCHIVE = {
    "path": "conformance/uibc-conformance-0.5.0.zip",
    "sha256": "ad2b73ccdd8e5606364372350fc35134d8efe897f0382b36dd4ee65af341bfc0",
    "bytes": 231243,
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_manifest() -> list:
    bad = []
    listed = set()
    for line in open(MANIFEST, encoding="utf-8").read().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        full = os.path.join(CONF, rel)
        listed.add(rel)
        if not os.path.exists(full):
            bad.append("missing: " + rel)
        elif sha256(full) != digest:
            bad.append("hash mismatch: " + rel)
    for dirpath, dirnames, filenames in os.walk(CONF):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name == "MANIFEST.sha256":
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), CONF).replace(os.sep, "/")
            if rel not in listed:
                bad.append("unlisted file: " + rel)
    return bad


def check_archive() -> list:
    p = os.path.join(ROOT, PINNED_ARCHIVE["path"].replace("conformance/", ""))
    p = os.path.join(CONF, os.path.basename(PINNED_ARCHIVE["path"]))
    if not os.path.exists(p):
        return ["archive missing: " + PINNED_ARCHIVE["path"]]
    bad = []
    if os.path.getsize(p) != PINNED_ARCHIVE["bytes"]:
        bad.append("archive size %d != pin %d" % (os.path.getsize(p), PINNED_ARCHIVE["bytes"]))
    if sha256(p) != PINNED_ARCHIVE["sha256"]:
        bad.append("archive sha256 does not match the pin")
    return bad


def check_coverage() -> list:
    doc = json.load(open(COVERAGE, encoding="utf-8"))
    manifest = json.load(open(os.path.join(CONF, "manifest.json"), encoding="utf-8"))
    bad = []
    known = {c["id"] for c in doc["checks"]}
    for case in manifest["cases"]:
        for ch in case.get("expected_checks", []):
            if ch not in known:
                bad.append("case %s names unknown check %s" % (case["id"], ch))
    if doc["totals"]["cases"] != len(manifest["cases"]):
        bad.append("coverage totals disagree with manifest case count")
    return bad


def main() -> int:
    failures = []
    for step, fn in (("MANIFEST.sha256", check_manifest),
                     ("archive pin", check_archive),
                     ("coverage.json", check_coverage)):
        bad = fn()
        print("%-18s %s" % (step, "ok" if not bad else "FAIL"))
        for b in bad:
            print("    -", b)
        failures += bad
    print("%-18s running" % "suite", end="", flush=True)
    run = subprocess.run([sys.executable, os.path.join("tools", "run_conformance.py"), "--json"],
                         cwd=ROOT, capture_output=True, text=True)
    try:
        res = json.loads(run.stdout)
        print("\r%-18s %d/%d strict, refused %d/%d" % ("suite", res["passed"], res["cases"],
                                                       res["refused"], res["cases"]))
        if not res["ok"]:
            failures.append("conformance suite did not pass")
    except Exception:
        print("\r%-18s unreadable output" % "suite")
        failures.append("conformance suite output unreadable")

    if failures:
        print("\nRESULT: FAIL (%d)" % len(failures))
        return 1
    print("\nRESULT: OK - download verified offline, archive matches the pin, suite green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
