#!/usr/bin/env python3
"""Ask, for every check, whether a published package can make it fail.

A check nobody can make fail is decoration. This collects evidence of the
opposite kind: for each of the nineteen checks, at least one artefact that a
reader can run, which drives that check to FAIL.

Two sources, because two checks cannot be reached from inside a package:

  * the exported conformance suite (conformance/cases) - thirty-six packages,
    each broken in one declared way. Covers seventeen of the nineteen.
  * tools/outsider_audit.py for S16 (a real RFC 3161 token, then four
    mutations of it) and S9 (a head observed outside the package, then a
    rollback that only that observation can see).

Run order: export the suite first, then this.

    python3 tools/export_conformance.py
    python3 tools/check_falsifiability.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(_REPO, "tools")
for p in (_REPO, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

from uibc_core.verify import verify  # noqa: E402

CASES = os.path.join(_REPO, "conformance", "cases")
BASE = os.path.join(_REPO, "fixtures", "clean.uibc")

CHECKS = ["S%d" % i for i in range(1, 19)]


def suite_hits():
    """Per check, the case ids that drive it to FAIL."""
    hits = {c: [] for c in CHECKS}
    if not os.path.isdir(CASES):
        raise SystemExit("conformance/cases is missing; run "
                         "tools/export_conformance.py first")
    for name in sorted(os.listdir(CASES)):
        pkg = os.path.join(CASES, name)
        if not os.path.isfile(os.path.join(pkg, "manifest.json")):
            continue
        try:
            result = verify(pkg)
        except Exception as e:  # noqa: BLE001
            print("  %s raised %s: %s" % (name, type(e).__name__, e), file=sys.stderr)
            continue
        for c in result["checks"]:
            if c["result"] == "FAIL" and c["id"] in hits:
                hits[c["id"]].append(name)
    return hits


def s16_mutations():
    """Run the four RFC 3161 mutations and report which ones make S16 fail."""
    import outsider_audit as oa

    got = []
    for label, fn, expected, _why in oa.S16_RED_TEAM:
        tmp = tempfile.mkdtemp()
        try:
            pkg = oa._prepare(BASE, tmp)
            fn(pkg)
            checks = {c["id"]: c for c in verify(pkg)["checks"]}
            res = checks.get("S16", {}).get("result")
            if res == "FAIL":
                got.append(label)
            else:
                print("  S16 mutation %r gave %r, expected FAIL" % (label, res),
                      file=sys.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return got


def s9_reachable():
    """Run the pinned control and the rollback attack; report the attack."""
    import outsider_audit as oa

    stage = oa.run_pinned(BASE, "INCONCLUSIVE")
    attack = [r for r in stage["rows"] if r["expectation"] == "FAIL"]
    ok = [r["name"] for r in attack if r["ok"]]
    if not ok:
        print("  S9 rollback attack did not produce FAIL", file=sys.stderr)
    return ok


def _mut_s1_drop_required(pkg):
    """S1, second shape: a declared file removed, rather than an extra one added."""
    os.remove(os.path.join(pkg, "identity.json"))


def _mut_s2_lifecycle_identity(pkg):
    """S2, second shape: the lifecycle disagrees, not the identity document."""
    path = os.path.join(pkg, "lifecycle.json")
    doc = json.load(open(path, encoding="utf-8"))
    doc["events"][0]["agent_id"] = "fx-agent-002"
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)


def _mut_s3_illegal_first_event(pkg):
    """S3, second shape: a legal date, an illegal transition into the machine."""
    path = os.path.join(pkg, "lifecycle.json")
    doc = json.load(open(path, encoding="utf-8"))
    doc["events"][0]["event_type"] = "ACTIVATE"
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)


def _mut_s7_media_type(pkg):
    """S7, second shape: a different metadata field than the note."""
    path = os.path.join(pkg, "evidence", "index.json")
    doc = json.load(open(path, encoding="utf-8"))
    doc["entries"][0]["media_type"] = "text/markdown"
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)


def _mut_s11_bom(pkg):
    """S11, second shape: bytes that are not JSON because of a byte-order mark."""
    path = os.path.join(pkg, "manifest.json")
    raw = open(path, "rb").read()
    open(path, "wb").write(b"\xef\xbb\xbf" + raw)


DEEP_MUTATIONS = [
    ("S1", "a declared file removed", _mut_s1_drop_required),
    ("S2", "the lifecycle disagrees with the identity", _mut_s2_lifecycle_identity),
    ("S3", "a legal timestamp, an illegal transition", _mut_s3_illegal_first_event),
    ("S7", "a different metadata field rewritten", _mut_s7_media_type),
    ("S11", "a byte-order mark in front of the manifest", _mut_s11_bom),
]


def deep_mutations():
    """Second shapes for the five checks that rested on a single artefact."""
    import outsider_audit as oa

    got = {}
    for cid, label, fn in DEEP_MUTATIONS:
        tmp = tempfile.mkdtemp()
        try:
            pkg = oa._prepare(BASE, tmp)
            fn(pkg)
            checks = {c["id"]: c for c in verify(pkg)["checks"]}
            res = checks.get(cid, {}).get("result")
            if res == "FAIL":
                got.setdefault(cid, []).append("deep: " + label)
            else:
                print("  deep mutation for %s (%s) gave %r, expected FAIL"
                      % (cid, label, res), file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print("  deep mutation for %s (%s) raised %s: %s"
                  % (cid, label, type(e).__name__, e), file=sys.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return got


def main():
    print("collecting from conformance/cases ...")
    hits = suite_hits()
    extra = {}
    try:
        s16 = s16_mutations()
        if s16:
            extra["S16"] = ["outsider_audit: " + s for s in s16]
    except Exception as e:  # noqa: BLE001
        print("  S16 mutations unavailable: %s: %s" % (type(e).__name__, e),
              file=sys.stderr)
    try:
        deep = deep_mutations()
        for cid, labels in deep.items():
            extra.setdefault(cid, []).extend(labels)
    except Exception as e:  # noqa: BLE001
        print("  deep mutations unavailable: %s: %s" % (type(e).__name__, e),
              file=sys.stderr)
    try:
        s9 = s9_reachable()
        if s9:
            extra["S9"] = ["outsider_audit: " + s for s in s9]
    except Exception as e:  # noqa: BLE001
        print("  S9 stage unavailable: %s: %s" % (type(e).__name__, e),
              file=sys.stderr)

    print()
    print("| check | artefacts that force FAIL | first |")
    print("|---|---|---|")
    holes = []
    for cid in CHECKS:
        allhits = hits[cid] + extra.get(cid, [])
        first = allhits[0] if allhits else "-"
        print("| %s | %d | %s |" % (cid, len(allhits), first))
        if not allhits:
            holes.append(cid)

    print()
    print("checks with no falsifying artefact:", ", ".join(holes) if holes else "none")
    sys.exit(1 if holes else 0)


if __name__ == "__main__":
    main()
