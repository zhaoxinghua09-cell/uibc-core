#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eQMS contract: records in, verdict out. One file, one schema, no platform.

The pitch needs an interface, not a platform. A device maker's QMS (Greenlight
Guru, Veeva, Arena, Ketryx...) already holds the records; what it cannot do is
hand a third party something that verifies offline. This is that seam:

    python tools/eqms_contract.py --in records.json --out verdict.json

Input (schema uibc.eqms-records/1) - deliberately minimal, so any QMS export can
produce it:

    {"subject": "agent:42",
     "records": [{"origin": "...", "kind": "...", "at": "...", "seq": 1,
                  "payload": {...}, "refs": [...]}, ...]}

Output (schema uibc.eqms-verdict/1):

    {"verdict": "PASS|FAIL|INCONCLUSIVE",
     "findings": [...],                  # codes K1-K8, never prose only
     "counts": {"records": n, "origins": m},
     "scope": "...",                     # the boundary, carried in the output
     "not_claimed": [...]}

Why this is the right shape: a QMS vendor can call it as a step in their change
workflow, and the verdict cites codes their auditor can re-run. What it is NOT:
a QMS, a compliance judgement, or a replacement for any of the above.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from uibc_core.canonical import hash_obj  # noqa: E402
from uibc_core.composition import compose_case  # noqa: E402

SCHEMA_IN = "uibc.eqms-records/1"
SCHEMA_OUT = "uibc.eqms-verdict/1"


def _digest(payload):
    return "sha256:" + hash_obj(payload)


def normalise(raw):
    """Accept a QMS export that omits digests: compute them, never trust them.

    A record that arrives WITH a digest is checked against its payload by K1; a
    record that arrives WITHOUT one is not silently accepted - the digest is
    computed here, which means K1 can no longer catch an edit that happened
    before the export. That limitation is reported, not hidden.
    """
    computed, given = 0, 0
    out = []
    for r in raw:
        rec = dict(r)
        d = _digest(rec.get("payload", {}))
        if rec.get("digest"):
            given += 1
        else:
            rec["digest"] = d
            computed += 1
        out.append(rec)
    return out, {"digests_given": given, "digests_computed": computed}


def run(doc):
    records, audit = normalise(doc.get("records", []))
    report = compose_case(records)
    return {
        "schema": SCHEMA_OUT,
        "subject": doc.get("subject"),
        "verdict": report["verdict"],
        "findings": report["findings"],
        "counts": {"records": len(records), "origins": len(report["origins"])},
        "origins": report["origins"],
        "scope": report["scope"],
        "input_audit": audit,
        "not_claimed": [
            "not a compliance judgement (PCCP/MDR/FDA or otherwise)",
            "does not establish that any producer told the truth",
            "does not establish completeness of the record set",
            "digests computed from this export cannot prove absence of earlier edits",
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args(argv)
    doc = json.load(open(args.inp, encoding="utf-8"))
    if doc.get("schema") not in (None, SCHEMA_IN):
        print("unknown input schema %r" % doc.get("schema"), file=sys.stderr)
        return 2
    verdict = run(doc)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=2)
    print("%-14s records=%d origins=%d codes=%s"
          % (verdict["verdict"], verdict["counts"]["records"],
             verdict["counts"]["origins"],
             ",".join(sorted({f["code"] for f in verdict["findings"]})) or "-"))
    return {"PASS": 0, "FAIL": 1}.get(verdict["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main())
