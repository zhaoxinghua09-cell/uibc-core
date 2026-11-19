#!/usr/bin/env python3
"""Run another project's JSON-nesting vectors against our reader and JCS.

Source vectors: `action-state-group/agent-action-capsule`, `vectors/json-nesting/
cases.json` (40 vector directories there; this is the one whose subject — a
serializer's nesting limit — is checkable with the standard library alone).

Each case gives JSON text, its nesting depth, whether it must be read, and (if
read) the SHA-256 of its RFC 8785 form. We read it with `json.loads`, canonicalize
with `uibc_core.canonical.canonicalize`, and compare.

Usage:
    python tools/crosscheck_aac_json_nesting.py --dir /path/to/vectors/json-nesting
"""

import argparse
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core import canonical  # noqa: E402


def run(dirpath):
    with open(os.path.join(dirpath, "cases.json"), encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = []
    for c in doc["cases"]:
        text, accept = c["json"], c["accept"]
        parsed, error = None, None
        try:
            parsed = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            error = type(exc).__name__
        if parsed is None and error is None:
            error = "no value"
        if parsed is not None:
            try:
                digest = hashlib.sha256(canonical.canonicalize(parsed)).hexdigest()
            except Exception as exc:  # noqa: BLE001
                digest, error = None, type(exc).__name__
        else:
            digest = None
        if accept:
            ok = parsed is not None and digest == c.get("jcs_sha256")
        else:
            ok = parsed is None or digest is None
        rows.append({"id": c["id"], "depth": c["depth"], "must_accept": accept,
                     "we_accepted": digest is not None,
                     "digest_matches": digest == c.get("jcs_sha256") if accept else None,
                     "class_ok": ok, "error": error})
    return rows, sum(0 if r["class_ok"] else 1 for r in rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows, bad = run(a.dir)
    if a.json:
        print(json.dumps({"cases": len(rows), "mismatches": bad, "rows": rows}, indent=2))
    else:
        for r in rows:
            print("%-32s depth=%-4d accept=%-5s we_accepted=%-5s %s"
                  % (r["id"], r["depth"], r["must_accept"], r["we_accepted"],
                     "ok" if r["class_ok"] else "<-- DISAGREES"))
        print("cases: %d  mismatches: %d" % (len(rows), bad))
        print("VERDICT: %s" % ("WE MATCH THEIR NESTING CONTRACT" if bad == 0
                               else "DISAGREEMENT - see rows above"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
