#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What a retention requirement can be shown to need, and what it cannot.

NIST AU-11 asks the organisation to retain audit records for a period it defines,
"to provide support for after-the-fact investigations of security incidents".
Four things a record layer can settle without knowing that period:

  start     the trail carries a readable earliest instant, and timestamps never
            go backwards - so "retained since" is a property of the data, not of
            memory
  no-expiry no expiry, retention or deletion field exists in the manifest,
            identity or lifecycle: the format does not set the period, the
            deployer does. A format that cleaned itself up on a timer would be
            deciding a policy question it was never given
  readable  the package can be parsed from the files alone - no key material, no
            service, no network - which is what an investigator a year later has
  intact    every evidence file still hashes to the digest the index recorded,
            and a tampered package does not (so "we still have the records" is
            not satisfied by merely having files)

What it does not show: how long is long enough. That sentence belongs to the
deployer's records policy; the tool says so rather than implying otherwise.

Exit 0 if all four hold; 1 otherwise.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLEAN = REPO / "fixtures" / "clean.uibc"
TAMPERED = REPO / "fixtures" / "tampered.uibc"

FORBIDDEN = re.compile(r"expir|retention|delet|ttl|purge|autoclean", re.I)


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _keys(node, prefix=""):
    """Every key name in the document, at any depth."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _keys(v, prefix + k + ".")
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item, prefix)


def _instant(text):
    # 3.10's fromisoformat does not accept a trailing Z.
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def check_start(pkg):
    events = _load(pkg / "lifecycle.json").get("events") or []
    if not events:
        return False, "no lifecycle events"
    stamps = [_instant(e["timestamp"]) for e in events]
    for a, b in zip(stamps, stamps[1:]):
        if b < a:
            return False, "timestamps go backwards (%s -> %s)" % (a, b)
    return True, "earliest=%s events=%d monotonic" % (events[0]["timestamp"], len(events))


def check_no_expiry(pkg):
    names = set()
    for rel in ("manifest.json", "identity.json", "lifecycle.json"):
        names.update(_keys(_load(pkg / rel)))
    hits = sorted(n for n in names if FORBIDDEN.search(n))
    if hits:
        return False, "the format sets a period itself: %s" % ", ".join(hits)
    return True, "no expiry/retention/deletion field in manifest, identity or lifecycle"


def check_readable(pkg):
    docs = ["manifest.json", "identity.json", "lifecycle.json", "evidence/index.json"]
    for rel in docs:
        _load(pkg / rel)
    return True, "parsed %d documents with no key material and no network" % len(docs)


def check_intact(pkg):
    """Recompute every evidence digest; report the first disagreement."""
    index = _load(pkg / "evidence" / "index.json").get("entries") or []
    if not index:
        return False, "no evidence entries"
    bad = []
    for e in index:
        path = pkg / "evidence" / e["path"]
        if not path.is_file():
            bad.append("%s missing" % e["path"])
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != e.get("content_hash"):
            bad.append("%s digest mismatch" % e["path"])
    return (not bad), ("%d/%d digests match" % (len(index) - len(bad), len(index))
                       if not bad else "; ".join(bad))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Four checks a retention requirement needs.")
    ap.add_argument("--package", default=str(CLEAN), help="a uibc package to check")
    ap.add_argument("--tampered", default=str(TAMPERED),
                    help="a package whose evidence digests must NOT match")
    args = ap.parse_args(argv)

    clean = Path(args.package)
    failures = 0
    for name, fn in (("start", check_start), ("no-expiry", check_no_expiry),
                     ("readable", check_readable), ("intact", check_intact)):
        ok, detail = fn(clean)
        print("%s %-10s %s" % ("PASS" if ok else "FAIL", name, detail))
        failures += 0 if ok else 1

    # A clean package passing "intact" proves the check runs; it does not prove
    # the check can fail. The tampered fixture is the other half.
    tampered_ok, tampered_detail = check_intact(Path(args.tampered))
    print("%s %-10s tampered: %s" % ("PASS" if not tampered_ok else "FAIL",
                                     "detects", tampered_detail))
    failures += 0 if not tampered_ok else 1

    print("\nretention: the format preserves the trail and does not decide how long; "
          "that period is the deployer's records policy")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
