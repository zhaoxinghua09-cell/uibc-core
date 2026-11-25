"""Validate every record in conformance/manifest.json against schemas/case-record.schema.json.

    python3 tools/validate_case_records.py             # validate the suite
    python3 tools/validate_case_records.py --self-test # prove the checks can fail

Paths resolve from this file, so it runs from anywhere.
Exit 0 = every record valid (and, under --self-test, every broken record rejected).
"""
import copy
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, "conformance", "manifest.json")
SCH = os.path.join(ROOT, "schemas", "case-record.schema.json")

_cache = {}


def load():
    if "schema" not in _cache:
        _cache["schema"] = json.load(open(SCH, encoding="utf-8"))
        _cache["cases"] = json.load(open(MAN, encoding="utf-8"))["cases"]
    return _cache["schema"], _cache["cases"]


def errors_for(c, schema):
    """All the reasons this record violates the schema, as a list of strings."""
    errs = []
    REQ = schema["required"]
    P = schema["properties"]
    for k in REQ:
        if k not in c:
            errs.append("missing " + k)
    for k in ("group", "expected_result"):
        if c.get(k) not in P[k]["enum"]:
            errs.append("%s=%r not in %s" % (k, c.get(k), P[k]["enum"]))
    if "expect" in c and c["expect"] not in P["expect"]["enum"]:
        errs.append("expect=%r" % c["expect"])
    if c.get("sha256") and not re.match(P["sha256"]["pattern"], c["sha256"]):
        errs.append("sha256 not 64 hex")
    if c.get("group") == "positive":
        if c.get("expect") != "accept":
            errs.append("positive must expect=accept")
        if c.get("expected_result") not in ("PASS", "INCONCLUSIVE"):
            errs.append("positive result %r" % c.get("expected_result"))
    else:
        if c.get("expected_result") != "FAIL":
            errs.append("mutation result %r" % c.get("expected_result"))
        if not (c.get("expected_checks") or []):
            errs.append("mutation with no expected_checks")
    for k, ml in (("attack", 8), ("why", 12), ("path", 3)):
        if len(str(c.get(k) or "")) < ml:
            errs.append("%s too short" % k)
    return errs


def self_test(schema, cases):
    """Four broken records must be rejected, and one good record must not be."""
    good = cases[0]
    mutations = []

    m = copy.deepcopy(good)
    m["sha256"] = m["sha256"][:63]  # one hex digit short
    mutations.append(("sha256 one digit short", m))

    m = copy.deepcopy(good)
    m["group"] = "negative-with-a-typo"
    mutations.append(("unknown group", m))

    m = copy.deepcopy(good)
    m.pop("why", None)
    mutations.append(("missing why", m))

    m = copy.deepcopy(next(x for x in cases if x.get("group") != "positive"))
    m["expected_checks"] = []
    mutations.append(("mutation with no expected_checks", m))

    ok = True
    for name, rec in mutations:
        e = errors_for(rec, schema)
        print("  self-test %-34s -> %s" % (name, ("rejected: " + e[0]) if e else "ACCEPTED (BAD)"))
        if not e:
            ok = False
    if errors_for(good, schema):
        print("  self-test good record rejected (BAD)")
        ok = False
    else:
        print("  self-test %-34s -> accepted (correct)" % "good record")
    return ok


def main(argv):
    schema, cases = load()
    if "--self-test" in argv:
        print("self-test on schemas/case-record.schema.json")
        ok = self_test(schema, cases)
        print("self-test        :", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    errs = []
    for c in cases:
        for e in errors_for(c, schema):
            errs.append((c.get("id"), e))
    print("cases            :", len(cases))
    print("required fields  :", len(schema["required"]))
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
    sys.exit(main(sys.argv[1:]))
