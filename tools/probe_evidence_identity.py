#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recompute every evidence identity inside a sealed package.

This is the probe behind the MDR Annex II 4(d) row: that clause asks for "the
precise identity of the controlled documents offering evidence" plus a
cross-reference to where each one sits. Here the identity is a sha256 over the
file's bytes and the cross-reference is the relative path in evidence/index.json.

What it checks, and what it therefore does not:
  - every entry's path resolves inside the package (no ../ escape)
  - the file exists
  - sha256(bytes) equals content_hash

It does not check whether the document is good, approved, current, or the right
document for the claim. That is document control, and it stays with the QMS.

    python tools/probe_evidence_identity.py fixtures/clean.uibc
"""
import hashlib
import json
import os
import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.stderr.write("usage: probe_evidence_identity.py <package-dir>\n")
        return 2
    pkg = argv[0]
    index_path = os.path.join(pkg, "evidence", "index.json")
    if not os.path.isfile(index_path):
        print("FAIL no evidence/index.json in %s" % pkg)
        return 1
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    root = os.path.realpath(pkg)
    entries = index.get("entries") or []
    bad = []
    for e in entries:
        eid = e.get("evidence_id", "?")
        rel = e.get("path", "")
        if not rel:
            bad.append((eid, "no path"))
            continue
        fp = os.path.realpath(os.path.join(pkg, "evidence", rel))
        if not (fp == root or fp.startswith(root + os.sep)):
            bad.append((eid, "path escapes the package: %s" % rel))
            continue
        if not os.path.isfile(fp):
            bad.append((eid, "missing file: %s" % rel))
            continue
        with open(fp, "rb") as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
        if actual != e.get("content_hash"):
            bad.append((eid, "digest mismatch: %s" % rel))
    for eid, why in bad:
        print("FAIL %s %s" % (eid, why))
    print("%s %d/%d evidence identities recompute" % (
        "OK" if not bad else "FAIL", len(entries) - len(bad), len(entries)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
