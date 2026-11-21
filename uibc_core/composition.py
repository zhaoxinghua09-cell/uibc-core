# -*- coding: utf-8 -*-
"""Composition verification: several heterogeneous records -> ONE decidable case.

The gap this fills is quoted, not asserted: `draft-mih-agent-accountability-
conformance-00` walks the IETF AUDIT architecture's work items WI-1..WI-11 and
none of them covers *composition verification* - "how does an auditor decide,
deterministically and testably, that a case assembled from multiple records of
different origins is self-consistent?"

Input is deliberately format-agnostic. A record is the smallest thing any
producer can emit:

    {"origin": "gate-A",           # who produced it
     "kind": "verdict",            # what it is
     "subject": "agent:42",        # what the case is about
     "at": "2026-11-17T06:00:00Z", # when it was produced
     "seq": 1,                     # per-origin position (optional)
     "digest": "sha256:...",       # canonical digest over payload
     "payload": {...},             # whatever the producer says
     "parent": "sha256:...",       # previous record in this origin (optional)
     "refs": ["sha256:...", ...]}  # records in OTHER origins it relies on

Checks K1-K8 are structural and offline. The verdict answers one question only:
**is this assembly self-consistent?** It does not answer whether the agent
behaved correctly, whether any producer told the truth, or whether the case is
complete - and K7 says INCONCLUSIVE rather than PASS when the records do not
actually form one case.
"""
import json
from typing import Any, Dict, List

from .canonical import hash_obj

DECISIONS = ("PASS", "FAIL", "INCONCLUSIVE")


def _digest_of(rec: Dict[str, Any]) -> str:
    return "sha256:" + hash_obj(rec.get("payload", {}))


def _parse_at(value: str) -> str:
    """Timestamps are compared as strings only if they are ISO-8601 Z-normalised;
    anything else is treated as absent rather than guessed at."""
    if not isinstance(value, str) or "T" not in value:
        return ""
    return value


def compose_case(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []

    def fail(code, detail, refs=None):
        findings.append({"code": code, "level": "FAIL", "detail": detail,
                         "records": refs or []})

    def unclear(code, detail, refs=None):
        findings.append({"code": code, "level": "INCONCLUSIVE", "detail": detail,
                         "records": refs or []})

    # K1 self-consistency: the digest must be over the payload as it stands.
    for i, r in enumerate(records):
        if r.get("digest") != _digest_of(r):
            fail("K1", "record %d digest does not match its payload (edited in place)" % i,
                 [r.get("digest")])

    # K6 no duplicate identity: the same record twice is two witnesses, not two facts.
    seen = {}
    for i, r in enumerate(records):
        key = r.get("digest")
        if key in seen:
            fail("K6", "record %d repeats the digest of record %d" % (i, seen[key]),
                 [key])
        seen[key] = i

    # K2 one case is about one subject.
    subjects = {str(r.get("subject")) for r in records if r.get("subject")}
    if len(subjects) > 1:
        fail("K2", "records disagree about the subject: %s" % sorted(subjects))

    # K3 per-origin chain: sequence contiguous, parent links the previous record.
    by_origin: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        by_origin.setdefault(str(r.get("origin")), []).append(r)
    for origin, group in by_origin.items():
        seqs = [r.get("seq") for r in group if isinstance(r.get("seq"), int)]
        if len(seqs) != len(group):
            unclear("K3", "origin %s has records without seq; continuity undecidable" % origin)
            continue
        seqs_sorted = sorted(seqs)
        if seqs_sorted != list(range(seqs_sorted[0], seqs_sorted[0] + len(seqs_sorted))):
            fail("K3", "origin %s has a sequence gap: %s" % (origin, seqs_sorted))
        ordered = sorted(group, key=lambda r: r["seq"])
        for prev, cur in zip(ordered, ordered[1:]):
            if cur.get("parent") and cur["parent"] != prev.get("digest"):
                fail("K3", "origin %s record seq=%s parent does not point at the previous "
                          "record" % (origin, cur["seq"]), [cur.get("digest")])

    # K5 reference closure + K4 cross-origin ordering.
    digest_at = {r.get("digest"): r for r in records}
    for r in records:
        for ref in r.get("refs", []) or []:
            target = digest_at.get(ref)
            if target is None:
                fail("K5", "record from %s refers to a record not present in the case"
                     % r.get("origin"), [ref])
                continue
            own_at, their_at = _parse_at(r.get("at")), _parse_at(target.get("at"))
            if own_at and their_at and own_at < their_at:
                fail("K4", "record from %s is dated before the record it relies on "
                           "(%s < %s)" % (r.get("origin"), own_at, their_at),
                     [r.get("digest"), ref])

    # K6b same (origin, seq) twice.
    pos = {}
    for r in records:
        key = (str(r.get("origin")), r.get("seq"))
        if key in pos:
            fail("K6", "two records claim the same position %s" % (key,))
        pos[key] = True

    # K7 the assembly must actually be a composition: >=2 origins, and no island
    # that neither refers nor is referred to.
    if len(by_origin) < 2:
        unclear("K7", "only %d origin(s): a single-origin record set is not a "
                      "composition and its self-consistency proves nothing extra"
                 % len(by_origin))
    else:
        linked = set()
        for r in records:
            for ref in r.get("refs", []) or []:
                linked.add(ref)
                linked.add(r.get("digest"))
        for origin, group in by_origin.items():
            if group and not any(g.get("digest") in linked for g in group):
                unclear("K7", "origin %s contributes no linked record: the set is "
                              "stacked, not composed" % origin)

    # K8 timestamps must exist for the ordering claim to be made at all.
    if not all(_parse_at(r.get("at")) for r in records):
        unclear("K8", "some records carry no ISO-8601 timestamp; ordering cannot be "
                      "decided for them")

    order = {"FAIL": 0, "INCONCLUSIVE": 1}
    if any(f["level"] == "FAIL" for f in findings):
        verdict = "FAIL"
    elif any(f["level"] == "INCONCLUSIVE" for f in findings):
        verdict = "INCONCLUSIVE"
    else:
        verdict = "PASS"
    del order

    return {
        "verdict": verdict,
        "records": len(records),
        "origins": sorted(by_origin),
        "findings": findings,
        "scope": "structural self-consistency of the assembled case only; does not "
                 "judge behaviour, truthfulness of any producer, or completeness",
    }


def main(argv=None):  # convenience for `python -m uibc_core.composition case.json`
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m uibc_core.composition <case.json>")
        return 2
    doc = json.load(open(argv[0], encoding="utf-8"))
    report = compose_case(doc["records"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return {"PASS": 0, "FAIL": 1}.get(report["verdict"], 2)
