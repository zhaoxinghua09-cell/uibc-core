#!/usr/bin/env python3
"""Run their `history-frame` vectors through our RFC 8785 canonicalizer.

Source: `action-state-group/agent-action-capsule`, `vectors/history-frame-v0/
vectors.json`. Each case gives a counting table and a wording pack as JSON
values, the digests the instance lists for them, and a property verdict per
binding (`table_binding`, `pack_binding`).

We compute SHA-256 over our canonical form and check the verdict reproduces:
PASS means our digest equals the listed one, FAIL means it does not. This
tests binding, not the counting rules — the counts are their subject matter,
the digests are ours.
"""

import argparse
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core import canonical  # noqa: E402

PAIRS = (("table", "table_binding"), ("pack", "pack_binding"))


def run(path):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = []
    for c in doc["cases"]:
        ins, listed = c["inputs"], c["inputs"]["listed"]
        props = c["expected"]["properties"]
        for key, prop in PAIRS:
            if key not in ins or prop not in props:
                continue
            digest = hashlib.sha256(canonical.canonicalize(ins[key])).hexdigest()
            we_match = digest == listed.get(key)
            should = props[prop] == "PASS"
            rows.append({"case": c["id"], "property": prop, "we_match": we_match,
                         "expected": props[prop], "agrees": we_match == should})
    return rows, sum(0 if r["agrees"] else 1 for r in rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows, bad = run(a.file)
    if a.json:
        print(json.dumps({"properties": len(rows), "disagreements": bad, "rows": rows}, indent=2))
    else:
        for r in rows:
            print("%-32s %-16s we_match=%-5s expected=%-5s %s"
                  % (r["case"], r["property"], r["we_match"], r["expected"],
                     "ok" if r["agrees"] else "<-- DISAGREES"))
        print("properties: %d  disagreements: %d" % (len(rows), bad))
        print("VERDICT: %s" % ("OUR JCS REPRODUCES THEIR BINDING VERDICTS" if bad == 0
                               else "DISAGREEMENT - see rows above"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
