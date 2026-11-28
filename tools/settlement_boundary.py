#!/usr/bin/env python3
"""Read the settlement boundary: what this repository can and cannot prove in a payment dispute.

Two things are checked, and neither is a matter of opinion:

- `we_process_payments` and `we_authorize_charges` must both be literally false. This
  repository has no money movement, no charge authority and no licence to do either.
  A record that flips one of them to true is refused without discussion, because the
  next reader would take it as a capability.
- every answer of `supported` or `partial` must point at a file that exists, and a
  `partial` must name its limit. An answer that points nowhere is a claim with no proof.

Then the documents are scanned for phrases that would read as a payment claim — the
ones that turn "we bind bytes" into "we settle money" without anyone editing a field.

    python3 tools/settlement_boundary.py            # 0 consistent, 1 overclaim, 3 evidence missing
    python3 tools/settlement_boundary.py --json
"""

import argparse
import json
import os

KIND = "uibc-settlement-boundary-v0"
ANSWERS = ("supported", "partial", "not_ours")
SCANNED = ("README.md", "docs/RECEIPT-FORMAT.md", "docs/DELEGATION.md",
           "docs/LAB-PROTOCOL.md", "docs/ADOPTION-MEASUREMENT.md")
BANNED = (
    "guarantees payment",
    "authorizes the charge",
    "authorises the charge",
    "chargeback protection",
    "pci compliant",
    "settles the payment",
    "we settle",
    "payment guarantee",
)


def check(boundary, root):
    """Return (reasons, notes). Reasons mean the boundary does not hold."""
    reasons, notes = [], []
    if boundary.get("kind") != KIND:
        reasons.append("kind is %r, expected %r" % (boundary.get("kind"), KIND))

    for flag in ("we_process_payments", "we_authorize_charges"):
        value = boundary.get(flag)
        if value is not False:
            reasons.append("%s is %r; this repository does not do that, and a boundary that says it might is a claim"
                           % (flag, value))

    questions = boundary.get("questions") or []
    if not isinstance(questions, list) or len(questions) != 6:
        reasons.append("expected six questions, found %d" % (len(questions) if isinstance(questions, list) else -1))
    ids = []
    for index, q in enumerate(questions if isinstance(questions, list) else []):
        qid = q.get("id") or "question %d" % (index + 1)
        ids.append(qid)
        if not str(q.get("question") or "").strip():
            reasons.append("%s has no question text" % qid)
        answer = q.get("answer")
        if answer not in ANSWERS:
            reasons.append("%s answers %r, not one of %s" % (qid, answer, ", ".join(ANSWERS)))
            continue
        if answer in ("supported", "partial"):
            evidence = q.get("evidence") or ""
            if not evidence:
                reasons.append("%s is %r with no evidence file" % (qid, answer))
            elif not os.path.isfile(os.path.join(root, evidence)):
                reasons.append("%s points at %s, which is not in the repository" % (qid, evidence))
            if not str(q.get("proves") or "").strip():
                reasons.append("%s is %r without saying what it proves" % (qid, answer))
        if answer == "partial" and not str(q.get("limit") or "").strip():
            reasons.append("%s is partial with no stated limit; partial without a limit reads as supported" % qid)
        if answer == "not_ours" and not str(q.get("limit") or "").strip():
            notes.append("%s is not ours and gives no reason; a bare absence is easy to read as a gap someone else will fill"
                         % qid)
    if ids and ids != ["Q%d" % i for i in range(1, 7)]:
        reasons.append("question ids are %s; the six questions are a fixed list and renumbering loses the history"
                       % ", ".join(ids))
    return reasons, notes


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
    parser.add_argument("--boundary", default=os.path.join("docs", "SETTLEMENT-BOUNDARY.json"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = os.getcwd()
    with open(args.boundary, encoding="utf-8") as fh:
        boundary = json.load(fh)

    reasons, notes = check(boundary, root)
    hits = scan(root)

    if args.json:
        print(json.dumps({"reasons": reasons, "notes": notes,
                          "payment_phrases": [{"file": f, "phrase": p} for f, p in hits]}, indent=2))
    else:
        for q in boundary.get("questions", []):
            print("%-3s %-11s %s" % (q.get("id"), q.get("answer"), q.get("question")))
            if q.get("limit"):
                print("      limit: " + q["limit"][:150])
        print("")
        if hits:
            print("OVERCLAIM — a document reads as a payment claim")
            for f, p in hits:
                print(" - %s contains %r" % (f, p))
        for reason in reasons:
            print(" - " + reason)
        for note in notes:
            print(" ! " + note)
        if hits or reasons:
            print("NOT ACCEPTABLE")
            return 1 if hits or not reasons else 3
        print("ACCEPTABLE — six questions answered, no payment claim in the scanned documents")
    if hits or reasons:
        return 1 if hits else 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
