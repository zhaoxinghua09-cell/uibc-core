#!/usr/bin/env python3
"""Check the SCITT crosswalk: where our receipt stands against one vendored draft, field by field.

The draft is `draft-noa-scitt-ai-agent-receipt-00`, vendored under docs/spec-sources and
read from that copy. The crosswalk is a claim about a document, so it is checkable
against that document rather than against memory: every row names a section, and the
tool refuses the three ways such a table lies.

- a `partial` with no `note` or no `cost` — partial-with-nothing reads as comfortable;
- a `have` that names no counterpart field;
- a container or flag that claims interop we do not have: `registered_in_transparency_service`,
  `emits_cose_sign1` and `claims_scitt_conformance` must all be literally false.

Then the documents are scanned for phrases that assert conformance to SCITT, which is
the word that turns a field-by-field comparison into a compatibility claim.

    python3 tools/check_scitt_crosswalk.py          # 0 consistent, 1 overclaim, 3 evidence missing
    python3 tools/check_scitt_crosswalk.py --json
"""

import argparse
import json
import os
import re
import sys

KIND = "uibc-scitt-crosswalk-v0"
STATUSES = ("have", "partial", "absent", "ours_only")
FLAGS_MUST_BE_FALSE = ("registered_in_transparency_service", "emits_cose_sign1",
                       "claims_scitt_conformance")
SCANNED = ("README.md", "docs/RECEIPT-FORMAT.md", "docs/LAB-PROTOCOL.md",
           "docs/COMPETITIVE-STATE.md")
BANNED = (
    "scitt-compatible",
    "scitt compatible",
    "scitt-compliant",
    "scitt compliant",
    "scitt-conformant",
    "conforms to scitt",
    "registered in a scitt transparency service",
)


def check(crosswalk, root):
    reasons, notes = [], []
    if crosswalk.get("kind") != KIND:
        reasons.append("kind is %r, expected %r" % (crosswalk.get("kind"), KIND))

    source = crosswalk.get("source") or {}
    document = source.get("document") or ""
    if not document:
        reasons.append("the crosswalk names no source document")
    elif not os.path.isfile(os.path.join(root, document)):
        reasons.append("the source document %r is not in the repository; a crosswalk against a text "
                       "nobody can read is a memory, not a comparison" % document)

    container = crosswalk.get("container") or {}
    if container.get("interoperable") is not False:
        reasons.append("container.interoperable is %r; there is no COSE/CBOR path here"
                       % container.get("interoperable"))

    flags = crosswalk.get("flags") or {}
    for flag in FLAGS_MUST_BE_FALSE:
        if flags.get(flag) is not False:
            reasons.append("flags.%s is %r; this repository does none of those things and a flag set "
                           "true would be read as a capability" % (flag, flags.get(flag)))

    rows = crosswalk.get("rows") or []
    if not isinstance(rows, list) or len(rows) < 12:
        reasons.append("expected at least 12 rows, found %d" % (len(rows) if isinstance(rows, list) else -1))
    counts = {s: 0 for s in STATUSES}
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        label = row.get("theirs") or "row %d" % (index + 1)
        status = row.get("status")
        if status not in STATUSES:
            reasons.append("%s has status %r, not one of %s" % (label, status, ", ".join(STATUSES)))
            continue
        counts[status] += 1
        if not str(row.get("theirs") or "").strip():
            reasons.append("row %d has no counterpart field named" % (index + 1))
        if status in ("have", "partial", "ours_only") and not str(row.get("ours") or "").strip():
            reasons.append("%s is %r but names nothing of ours" % (label, status))
        if status == "partial" and not str(row.get("note") or "").strip():
            reasons.append("%s is partial with no note; a bare partial reads as close enough" % label)
        if status == "absent" and not str(row.get("cost") or "").strip():
            reasons.append("%s is absent with no stated cost; absent without a price reads as temporary" % label)
        if status == "partial" and "cost" not in row:
            notes.append("%s is partial and states no cost to close" % label)

    if counts["have"] == 0:
        reasons.append("no row is 'have'; a table in which nothing matches should say so in a sentence, "
                       "not in a table of sixteen rows")
    return reasons, {**counts}, notes


def scan(root):
    hits = []
    for rel in SCANNED:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read().lower()
        for phrase in BANNED:
            if phrase in text:
                hits.append((rel, phrase))
    return hits


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--crosswalk", default=os.path.join("docs", "SCITT-CROSSWALK.json"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = os.getcwd()
    with open(args.crosswalk, encoding="utf-8") as fh:
        crosswalk = json.load(fh)

    reasons, counts, notes = check(crosswalk, root)
    hits = scan(root)

    if args.json:
        print(json.dumps({"reasons": reasons, "counts": counts, "notes": notes,
                          "scitt_claims": [{"file": f, "phrase": p} for f, p in hits]}, indent=2))
    else:
        for row in crosswalk.get("rows", []):
            print("%-12s %-44s %s" % (row.get("status"), row.get("theirs", "")[:44], (row.get("note") or "")[:70]))
        print("")
        print("counts: " + ", ".join("%s=%d" % (k, v) for k, v in counts.items()))
        if hits:
            print("OVERCLAIM — a document asserts SCITT conformance")
            for f, p in hits:
                print(" - %s contains %r" % (f, p))
        for reason in reasons:
            print(" - " + reason)
        for note in notes:
            print(" ! " + note)
        if hits:
            print("NOT ACCEPTABLE")
            return 1
        if reasons:
            print("NOT ACCEPTABLE")
            return 3
        print("ACCEPTABLE — %d rows against the vendored draft, no conformance claim in the scanned documents"
              % len(crosswalk.get("rows", [])))
    if hits:
        return 1
    return 3 if reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
