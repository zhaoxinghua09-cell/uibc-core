#!/usr/bin/env python3
"""Check a configuration change record: who proposed it, who decided, what moved.

Three rules are adopted from documents that already said them better than we did,
and each is enforced here rather than restated:

- the disposition comes from a closed set, `declined` carries a reason, and a
  partial adoption must state its residual (probityai, GOVERNANCE.md);
- a change to normative behaviour lands in the specification, the verifier and
  the corpus together, or not at all (emilia, GOVERNANCE.md section 3);
- silence is not agreement: a decision needs a named decider and a timestamp,
  not the absence of objections.

Two more are ours: the proposer cannot be the decider, and the ledger is
append-only — the record's id is the digest of its own body, so editing one row
produces a different id and a chain that no longer links.
"""

import argparse
import base64
import datetime
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

from uibc_core import ed25519  # noqa: E402
from uibc_core.canonical import canonicalize  # noqa: E402

KIND = "uibc-change-v0"
DISPOSITIONS = ("adopted", "adopted-in-part", "declined", "open")
NORMATIVE_LEGS = ("spec", "verifier", "corpus")


def _body(record):
    return {k: v for k, v in record.items() if k not in ("signature", "id")}


def body_id(record):
    return hashlib.sha256(canonicalize(_body(record))).hexdigest()


def signed_bytes(record):
    """The bytes a decision signs: the row including its id, excluding the signature.

    The id is inside what is signed but is computed from the body, so an edit to any
    field breaks the id and an edit to the id breaks the signature; neither can be
    made to pass by rewriting the other.
    """
    return canonicalize({k: v for k, v in record.items() if k != "signature"})


def _t(value, field):
    if not isinstance(value, str) or not value:
        return None, "%s is not a timestamp string" % field
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, "%s is not an ISO 8601 timestamp: %r" % (field, value)
    if parsed.tzinfo is None:
        return None, "%s has no timezone offset" % field
    return parsed, None


def _hex64(v):
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def issue_record(seed, proposed_by, decided_by, disposition, normative=True,
                 legs=None, residual="", settle_with="", reason="",
                 why_not_normative="", previous_id=None, proposed_at=None,
                 decided_at=None):
    proposed_at = proposed_at or "2026-11-20T00:00:00Z"
    decided_at = decided_at or "2026-11-20T01:00:00Z"
    record = {
        "kind": KIND,
        "proposed": {"by": proposed_by[0], "id": proposed_by[1], "at": proposed_at},
        "decision": {"by": decided_by[0], "id": decided_by[1], "at": decided_at,
                     "disposition": disposition},
        "residual": residual,
        "settle_with": settle_with,
        "reason": reason,
        "normative": bool(normative),
        "why_not_normative": why_not_normative,
        "legs": legs or {},
        "previous_id": previous_id,
    }
    record["id"] = body_id(record)
    seed = bytes(seed)
    pub = ed25519.publickey(seed)
    record["signature"] = {
        "alg": "ed25519",
        "key_id": hashlib.sha256(pub).hexdigest()[:16],
        "public_key_b64": base64.b64encode(pub).decode(),
        "signature_b64": base64.b64encode(ed25519.sign(seed, signed_bytes(record))).decode(),
    }
    return record


def check(record, decider_key=None):
    """Return (reasons, notes) for one record."""
    reasons, notes = [], []
    if not isinstance(record, dict):
        return ["the record is not a JSON object"], []
    if record.get("kind") != KIND:
        reasons.append("kind is %r, expected %r" % (record.get("kind"), KIND))

    prop = record.get("proposed") or {}
    dec = record.get("decision") or {}
    for who, block in (("proposed", prop), ("decision", dec)):
        if not isinstance(block.get("by"), str) or not block.get("by"):
            reasons.append("%s has no name" % who)
        if not isinstance(block.get("id"), str) or not block.get("id"):
            reasons.append("%s has no id" % who)
    if str(prop.get("id") or "").lower() == str(dec.get("id") or "").lower() != "":
        reasons.append("the proposer and the decider are the same party: a change cannot approve itself")

    disposition = dec.get("disposition")
    if disposition not in DISPOSITIONS:
        reasons.append("disposition is %r, not one of %s" % (disposition, ", ".join(DISPOSITIONS)))
    if disposition == "declined" and not str(record.get("reason") or "").strip():
        reasons.append("declined carries no reason; a refusal without a reason is indistinguishable from silence")
    if disposition == "adopted-in-part" and not str(record.get("residual") or "").strip():
        reasons.append("adopted-in-part states no residual; a partial adoption without one absorbs the gap")
    if disposition == "open" and not str(record.get("settle_with") or "").strip():
        reasons.append("open does not say what would settle it, so nothing can close it")

    normative = record.get("normative")
    legs = record.get("legs") or {}
    if normative is True:
        for leg in NORMATIVE_LEGS:
            value = legs.get(leg)
            digest = value.get("sha256") if isinstance(value, dict) else value
            if not _hex64(digest):
                reasons.append("normative change is missing the %s leg; it lands in all three or not at all" % leg)
    elif normative is False:
        if not str(record.get("why_not_normative") or "").strip():
            reasons.append("marked non-normative with no stated reason")
    else:
        reasons.append("normative is %r; a change has to say whether behaviour moved" % normative)
    for leg in legs:
        if leg not in NORMATIVE_LEGS:
            reasons.append("legs carries %r, which is not one of %s" % (leg, ", ".join(NORMATIVE_LEGS)))

    computed = body_id(record)
    if record.get("id") != computed:
        reasons.append("the id is %r but the body hashes to %s; this row was edited after it was recorded"
                       % (record.get("id"), computed))

    prev = record.get("previous_id")
    if prev is not None and not _hex64(prev):
        reasons.append("previous_id is neither null nor a 64-hex id")

    pat, err = _t(prop.get("at"), "proposed.at")
    reasons += [err] if err else []
    dat, err = _t(dec.get("at"), "decision.at")
    reasons += [err] if err else []
    if pat and dat:
        if dat < pat:
            reasons.append("the decision is timestamped before the proposal")
        if (dat - pat) > datetime.timedelta(days=365):
            reasons.append("the decision is more than a year after the proposal; this is a stale yes")

    sig = record.get("signature") or {}
    if sig.get("alg") != "ed25519":
        reasons.append("signature.alg is %r" % sig.get("alg"))
    else:
        try:
            pub = base64.b64decode(sig.get("public_key_b64") or "")
            sig_bytes = base64.b64decode(sig.get("signature_b64") or "")
        except Exception:
            pub, sig_bytes = b"", b""
        if hashlib.sha256(pub).hexdigest()[:16] != sig.get("key_id"):
            reasons.append("signature.key_id does not match the recorded public key")
        if not sig_bytes or not ed25519.verify(pub, signed_bytes(record), sig_bytes):
            reasons.append("the Ed25519 signature does not verify over the canonical record")
        if decider_key:
            if pub != bytes(decider_key):
                reasons.append("the record is signed with a key that is not the decider's known key")
        elif not reasons:
            notes.append("identity unbound: the key travels inside the record, so this proves the record was "
                         "signed by its author, not that %r decided it — pass the decider's key to bind it"
                         % (dec.get("by") or "the decider"))
    return reasons, notes


def check_ledger(records):
    """Append-only check over a list of records, in the order they are published."""
    reasons = []
    seen = {}
    previous = None
    for index, record in enumerate(records, start=1):
        rid = record.get("id")
        if rid in seen:
            reasons.append("row %d repeats id %s (first seen at row %d)" % (index, rid, seen[rid]))
        seen[rid] = index
        if record.get("previous_id") != previous:
            reasons.append("row %d points at previous_id %r, the row before it is %r"
                           % (index, record.get("previous_id"), previous))
        previous = rid
    return reasons


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("record", help="one change record, or a JSON list of them")
    parser.add_argument("--decider-key", help="the decider's known public key, hex")
    args = parser.parse_args(argv)

    with open(args.record, encoding="utf-8") as f:
        payload = json.load(f)
    records = payload if isinstance(payload, list) else [payload]

    key = None
    if args.decider_key:
        try:
            key = bytes.fromhex(args.decider_key.strip())
        except ValueError:
            print("NOT ACCEPTABLE")
            print(" - --decider-key is not hex")
            return 1

    all_reasons, all_notes = [], []
    for index, record in enumerate(records, start=1):
        reasons, notes = check(record, decider_key=key)
        label = "" if len(records) == 1 else "row %d: " % index
        all_reasons += [label + r for r in reasons]
        all_notes += notes
    if len(records) > 1:
        all_reasons += check_ledger(records)

    if all_reasons:
        print("NOT ACCEPTABLE")
        for reason in all_reasons:
            print(" - " + reason)
        return 1
    for record in records:
        dec = record["decision"]
        legs = ", ".join(sorted(record.get("legs") or {})) or "none"
        print("%s — %r by %s, decided by %s at %s, normative %s, legs %s"
              % (record["id"][:12], dec["disposition"], record["proposed"]["by"],
                 dec["by"], dec["at"], record["normative"], legs))
    print("ACCEPTABLE — %d row(s), chain intact, dispositions from the closed set" % len(records))
    for note in all_notes:
        print(" ! " + note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
