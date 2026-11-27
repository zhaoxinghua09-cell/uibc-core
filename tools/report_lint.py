"""Lint a verify-report JSONL file against the schema that shape belongs to.

Why a separate linter: the schema is a promise to someone outside this
repository. Testing our own output against a schema we wrote and validating
*their* file with the same rules are different jobs, and the second one is what
makes the promise usable. This tool takes any producer's file - ours, a
competitor's, a stranger's - and says which lines do not hold.

No third-party dependency: the schema subset used here is small enough to check
by hand, and a consumer who cannot install `jsonschema` should still be able to
read the rules.

    python tools/report_lint.py runs.jsonl
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(HERE, "interop", "verify-report.schema.json")
COSE_SCHEMA = os.path.join(HERE, "interop", "scitt-cose-report.schema.json")

FORMAT = "uibc-verify-report/1"
COSE_FORMAT = "uibc-scitt-cose-report/1"
COSE_CODE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RESULTS = {"PASS", "FAIL", "INCONCLUSIVE", "ERROR"}
EXITS = {0, 1, 2, 3}
WHEN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
CHECK_ID = re.compile(r"^S[0-9]+$")
REQUIRED = ("format", "vector", "result", "checks_failed", "verifier_id",
            "verifier_version", "when_utc", "exit")
OPTIONAL = ("error",)


def problems(line):
    """Every reason this object is not a report line, in plain words."""
    if not isinstance(line, dict):
        return ["not a JSON object"]
    out = []
    for k in REQUIRED:
        if k not in line:
            out.append("missing %r" % k)
    for k in sorted(set(line) - set(REQUIRED) - set(OPTIONAL)):
        out.append("unknown key %r" % k)
    if out:
        return out
    if line["format"] != FORMAT:
        out.append("format is %r, expected %r" % (line["format"], FORMAT))
    for k in ("vector", "verifier_id", "verifier_version"):
        if not isinstance(line[k], str) or not line[k]:
            out.append("%s must be a non-empty string" % k)
    if line["result"] not in RESULTS:
        out.append("result %r is not one of %s" % (line["result"], sorted(RESULTS)))
    cf = line["checks_failed"]
    if not isinstance(cf, list) or any(not isinstance(c, str) or not CHECK_ID.match(c) for c in cf):
        out.append("checks_failed must be a list of check ids like S4")
    elif line["result"] == "FAIL" and not cf:
        out.append("a FAIL line with no failing check names nothing")
    elif line["result"] != "FAIL" and cf:
        out.append("result %r must not carry failed checks" % line["result"])
    if not isinstance(line["when_utc"], str) or not WHEN.match(line["when_utc"]):
        out.append("when_utc must be YYYY-MM-DDTHH:MM:SSZ")
    if line["exit"] not in EXITS or isinstance(line["exit"], bool):
        out.append("exit must be one of 0, 1, 2, 3")
    elif line["result"] == "ERROR" and line["exit"] != 3:
        out.append("an ERROR line exits 3, not %r" % line["exit"])
    if line["result"] == "ERROR":
        if "error" not in line:
            out.append("an ERROR line must say why")
    elif "error" in line:
        out.append("only an ERROR line carries 'error'")
    if "error" in line:
        e = line["error"]
        if not isinstance(e, str) or not e or len(e) > 300:
            out.append("error must be a string of 1..300 characters")
    return out


COSE_REQUIRED = ("format", "vector", "verdict", "codes", "notes", "verifier_id",
                 "verifier_version", "when_utc", "exit")
COSE_OPTIONAL = ("conforms_to_expected",)


def cose_problems(line):
    """The second shape: what a verifier decided about one Transparent Statement.

    Kept separate from `problems` rather than generalised into it: the two
    shapes answer different questions, and a validator that accepts either
    without saying which rules it applied is the failure mode this file exists
    to catch. The contract is small enough to state: a valid verdict carries no
    codes, a refusal carries at least one and exits 1.
    """
    if not isinstance(line, dict):
        return ["not a JSON object"]
    out = []
    for k in COSE_REQUIRED:
        if k not in line:
            out.append("missing %r" % k)
    for k in sorted(set(line) - set(COSE_REQUIRED) - set(COSE_OPTIONAL)):
        out.append("unknown key %r" % k)
    if out:
        return out
    if line["format"] != COSE_FORMAT:
        out.append("format is %r, expected %r" % (line["format"], COSE_FORMAT))
    for k in ("vector", "verifier_id", "verifier_version"):
        if not isinstance(line[k], str) or not line[k]:
            out.append("%s must be a non-empty string" % k)
    if line["verdict"] not in ("valid", "invalid"):
        out.append("verdict %r is neither 'valid' nor 'invalid'" % (line["verdict"],))
    codes = line["codes"]
    if not isinstance(codes, list) or any(
            not isinstance(c, str) or not COSE_CODE.match(c) for c in codes):
        out.append("codes must be a list of lower-case hyphenated tokens")
    elif line["verdict"] == "invalid" and not codes:
        out.append("an invalid verdict with no code names no ground for the refusal")
    elif line["verdict"] == "valid" and codes:
        out.append("a valid verdict must not carry refusal codes")
    notes = line["notes"]
    if not isinstance(notes, list) or any(not isinstance(n, str) for n in notes):
        out.append("notes must be a list of strings")
    if "conforms_to_expected" in line:
        v = line["conforms_to_expected"]
        if v is not None and not isinstance(v, bool):
            out.append("conforms_to_expected must be true, false or null")
    if not isinstance(line["when_utc"], str) or not WHEN.match(line["when_utc"]):
        out.append("when_utc must be YYYY-MM-DDTHH:MM:SSZ")
    if line["exit"] not in (0, 1) or isinstance(line["exit"], bool):
        out.append("exit must be 0 (valid) or 1 (refused)")
    elif (line["verdict"] == "valid") != (line["exit"] == 0):
        out.append("exit %r does not match verdict %r" % (line["exit"], line["verdict"]))
    return out


def problems_any(line):
    """Validate one line against the shape its `format` field names."""
    if isinstance(line, dict) and line.get("format") == COSE_FORMAT:
        return cose_problems(line)
    return problems(line)


def lint(path):
    bad, total = [], 0
    with open(path, encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            if not raw.strip():
                continue
            total += 1
            try:
                line = json.loads(raw)
            except ValueError as exc:
                bad.append((n, ["not JSON: %s" % exc]))
                continue
            why = problems_any(line)
            if why:
                bad.append((n, why))
    return total, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report")
    ap.add_argument("--schema", default=SCHEMA, help="informational: the rules checked here")
    args = ap.parse_args(argv)
    if not os.path.exists(args.report):
        print("FAIL no such file: %s" % args.report)
        return 3
    total, bad = lint(args.report)
    for n, why in bad[:20]:
        print("line %d: %s" % (n, "; ".join(why)))
    if len(bad) > 20:
        print("... and %d more" % (len(bad) - 20))
    if not total:
        print("FAIL the file holds no report line")
        return 1
    if bad:
        print("\nREPORT LINT FAIL (%d of %d line(s))" % (len(bad), total))
        return 1
    print("REPORT LINT OK: %d line(s), schemas %s and %s"
          % (total, os.path.basename(SCHEMA), os.path.basename(COSE_SCHEMA)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
