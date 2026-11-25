"""Validate every record in conformance/manifest.json against conformance/case-record.schema.json.

Run from anywhere: paths are resolved from this file's location.
Exit 0 = every record valid; exit 1 = violations printed.

    python3 tools/validate_case_records.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, "conformance", "manifest.json")
SCH = os.path.join(ROOT, "schemas", "case-record.schema.json")


def main():
    cases = json.load(open(MAN, encoding="utf-8"))["cases"]
    schema = json.load(open(SCH, encoding="utf-8"))
    REQ = schema["required"]
    P = schema["properties"]
    errs = []
    for c in cases:
        cid = c.get("id")
        for k in REQ:
            if k not in c:
                errs.append((cid, "missing " + k))
        for k in ("group", "expected_result"):
            if c.get(k) not in P[k]["enum"]:
                errs.append((cid, "%s=%r not in %s" % (k, c.get(k), P[k]["enum"])))
        if "expect" in c and c["expect"] not in P["expect"]["enum"]:
            errs.append((cid, "expect=%r" % c["expect"]))
        if c.get("sha256") and not re.match(P["sha256"]["pattern"], c["sha256"]):
            errs.append((cid, "sha256 not 64 hex"))
        if c.get("group") == "positive":
            if c.get("expect") != "accept":
                errs.append((cid, "positive must expect=accept"))
            if c.get("expected_result") not in ("PASS", "INCONCLUSIVE"):
                errs.append((cid, "positive result %r" % c.get("expected_result")))
        else:
            if c.get("expected_result") != "FAIL":
                errs.append((cid, "mutation result %r" % c.get("expected_result")))
            if not (c.get("expected_checks") or []):
                errs.append((cid, "mutation with no expected_checks"))
        for k, ml in (("attack", 8), ("why", 12), ("path", 3)):
            if len(str(c.get(k) or "")) < ml:
                errs.append((cid, "%s too short" % k))

    print("cases            :", len(cases))
    print("required fields  :", len(REQ))
    print("violations       :", len(errs))
    for e in errs[:10]:
        print("   ", e)

    try:
        import jsonschema
        bad = 0
        for c in cases:
            try:
                jsonschema.validate(c, schema)
            except jsonschema.ValidationError as ex:
                bad += 1
                if bad <= 3:
                    print("   jsonschema:", c.get("id"), ex.message[:140])
        print("jsonschema       : %d passed / %d failed" % (len(cases) - bad, bad))
    except ImportError:
        print("jsonschema       : not installed (hand checks only)")

    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
