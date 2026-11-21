#!/usr/bin/env python3
"""Static audit of the AER-1 corpus against the spec text.

Why this tool exists
--------------------
Three claims about "spec vs corpus contradictions" had been written into this
repository's docs from memory. Re-reading the specification and re-scanning
the corpus showed that one of the three was simply wrong, and the other two
needed exact clause references. A claim nobody can re-run is a claim that
rots — so the checks live here, and the prose cites their output.

Deliberately static
-------------------
This does not import the publisher's runner. It reads the corpus and counts
what is there: how many schema-0.4 receipts lack `metadata_hash`, which
vectors carry integer-valued floats and what verdict they expect, and which
receipt files end with a newline. Conclusions belong in the document next to
the numbers, not hidden inside the tool.

Usage
-----
    python3 tools/aer1_spec_audit.py --kit /tmp/aer1_kit
    python3 tools/aer1_spec_audit.py --kit /tmp/aer1_kit --json
"""

import argparse
import glob
import json
import os
import sys


def _load_json(path):
    with open(path, "rb") as stream:
        raw = stream.read()
    try:
        return json.loads(raw), raw
    except ValueError:
        return None, raw


def audit_metadata_hash(kit):
    """How many schema-0.4 receipts omit metadata_hash, and where."""
    base = os.path.join(kit, "base", "test-vectors")
    result = {}
    for subset in ("valid", "invalid", "invalid-profile"):
        directory = os.path.join(base, subset)
        if not os.path.isdir(directory):
            continue
        total_04 = 0
        missing = []
        for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
            doc, _raw = _load_json(path)
            if not isinstance(doc, dict):
                continue
            if doc.get("receipt_schema_version") != "0.4":
                continue
            total_04 += 1
            if "metadata_hash" not in doc:
                missing.append(os.path.basename(path))
        result[subset] = {"schema_0_4": total_04, "missing_metadata_hash": len(missing),
                          "files": missing}
    result["spec_clause"] = {
        "table_1": "Section 3.1 Table 1: metadata_hash marked Cond., "
                   "REQUIRED when receipt_schema_version is 0.4 or later",
        "section_6_step_4": "Section 6 step 4: 'A \"0.4\" receipt without "
                            "metadata_hash MUST fail.'",
    }
    return result


def audit_integer_floats(kit):
    """Vectors that write an integer as a float, and the verdict they expect.

    The interesting split is `seq` (explicitly stated to accept 1.0) versus
    `entry_count` (same wording about integer value, one vector expects 1.0
    to be rejected).
    """
    hits = []
    for path in sorted(glob.glob(os.path.join(kit, "base", "*.json"))):
        doc, _raw = _load_json(path)
        if not isinstance(doc, dict):
            continue
        for index, vector in enumerate(doc.get("vectors", [])):
            if not isinstance(vector, dict):
                continue
            found = []
            commitment = vector.get("commitment")
            if isinstance(commitment, dict):
                value = commitment.get("entry_count")
                if isinstance(value, float) and value == int(value):
                    found.append(("entry_count", value))
            for entry in vector.get("timeline", []) or []:
                if isinstance(entry, dict):
                    value = entry.get("seq")
                    if isinstance(value, float) and value == int(value):
                        found.append(("seq", value))
            if found:
                hits.append({
                    "file": os.path.basename(path),
                    "index": index,
                    "name": vector.get("name"),
                    "expected_verdict": vector.get("expected_verdict"),
                    "fields": [{"field": f, "value": repr(v)} for f, v in found],
                })
    return {"vectors": hits,
            "spec_clause": {
                "seq": "Section 7.2: 1 and 1.0 are equivalent; both accepted; "
                       "a non-integer number such as 1.5 MUST be rejected",
                "entry_count": "Section 7.3: 'a JSON number with an integer value' "
                               "(no sentence about 1.0 equivalence)",
            }}


def audit_trailing_newline(kit):
    """Count receipt files whose raw bytes end with a newline.

    Reported as a fact only: the specification has no trailing-newline clause,
    so a file ending in \\n is not a violation, and this count must not be
    described as one.
    """
    base = os.path.join(kit, "base", "test-vectors")
    result = {"spec_clause": "none: grep for 'trailing' / 'newline' in the "
                              "specification returns no hits"}
    for subset in ("valid", "invalid"):
        directory = os.path.join(base, subset)
        if not os.path.isdir(directory):
            continue
        with_newline = []
        total = 0
        for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
            total += 1
            with open(path, "rb") as stream:
                raw = stream.read()
            if raw.endswith(b"\n"):
                with_newline.append(os.path.basename(path))
        result[subset] = {"files": total, "ending_with_newline": len(with_newline),
                          "examples": with_newline[:5]}
    return result


def audit(kit):
    if not os.path.isdir(kit):
        raise FileNotFoundError("kit directory not found: %s" % kit)
    return {
        "kit": os.path.abspath(kit),
        "findings": [
            {"id": "A", "topic": "metadata_hash", "status": "conflict",
             "detail": audit_metadata_hash(kit)},
            {"id": "B", "topic": "integer-valued floats", "status": "ambiguous",
             "detail": audit_integer_floats(kit)},
            {"id": "C", "topic": "trailing newline", "status": "withdrawn",
             "detail": audit_trailing_newline(kit)},
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kit", required=True, help="AER-1 corpus kit directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = audit(args.kit)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    for finding in report["findings"]:
        detail = finding["detail"]
        print("[%s] %s -> %s" % (finding["id"], finding["topic"], finding["status"]))
        if finding["id"] == "A":
            for subset in ("valid", "invalid", "invalid-profile"):
                if subset in detail:
                    entry = detail[subset]
                    print("    %-16s schema 0.4: %2d, missing metadata_hash: %2d"
                          % (subset, entry["schema_0_4"], entry["missing_metadata_hash"]))
        elif finding["id"] == "B":
            for vector in detail["vectors"]:
                fields = ", ".join("%s=%s" % (f["field"], f["value"]) for f in vector["fields"])
                print("    %-24s [%d] %-26s expect=%-8s %s"
                      % (vector["file"], vector["index"], vector["name"],
                         vector["expected_verdict"], fields))
        elif finding["id"] == "C":
            for subset in ("valid", "invalid"):
                if subset in detail:
                    entry = detail[subset]
                    print("    %-8s %2d files, %2d end with a newline (not a spec violation)"
                          % (subset, entry["files"], entry["ending_with_newline"]))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
