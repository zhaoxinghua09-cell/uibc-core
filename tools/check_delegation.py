#!/usr/bin/env python3
"""Check a delegation record: who authorized whom to run which corpus, until when.

A run receipt says "someone ran it". It does not say the someone was allowed to.
This reads a signed record of that permission and refuses the five ways such a
record is usually worthless: delegating to yourself, a window that has expired
(or is longer than a quarter), a scope wider than the corpus it names, a chain
deeper than one hop, and a signature that does not verify.

Signature is Ed25519 over the canonical JSON of the record minus `signature`,
with the same canonicaliser the receipts use, so the bytes signed are the bytes
anyone else can recompute.
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

KIND = "uibc-delegation-v0"
MAX_WINDOW_DAYS = 90
MAX_RUNS = 100
SIG_ALG = "ed25519"


def _parse_time(value, field):
    if not isinstance(value, str) or not value:
        return None, "%s is not a timestamp string" % field
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, "%s is not an ISO 8601 timestamp: %r" % (field, value)
    if parsed.tzinfo is None:
        return None, "%s has no timezone offset, so it means nothing outside the author's head" % field
    return parsed, None


def _is_hex64(value):
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value)


def _public_key(signature):
    try:
        return base64.b64decode(signature["public_key_b64"])
    except Exception:
        return b""


def signed_bytes(record):
    body = {k: v for k, v in record.items() if k != "signature"}
    return canonicalize(body)


def issue_record(seed, delegator, delegatee, corpus_sha256, not_before, not_after,
                 cases="all", cases_total=0, max_runs=1, nonce=None, directed=False):
    """Build and sign one record. Kept here so tests and the docs use the same bytes."""
    seed = bytes(seed)
    if len(seed) != 32:
        raise ValueError("the signing seed must be 32 bytes")
    nonce = nonce or hashlib.sha256(seed + corpus_sha256.encode()).hexdigest()[:32]
    record = {
        "kind": KIND,
        "delegator": {"name": delegator[0], "id": delegator[1]},
        "delegatee": {"name": delegatee[0], "id": delegatee[1]},
        "scope": {
            "corpus_sha256": corpus_sha256,
            "cases": cases,
            "cases_total": cases_total,
            "max_runs": max_runs,
            "directed": bool(directed),
        },
        "window": {"not_before": not_before, "not_after": not_after},
        "nonce": nonce,
        "chain": {"depth": 1},
    }
    pub = ed25519.publickey(seed)
    signature = ed25519.sign(seed, canonicalize(record))
    record["signature"] = {
        "alg": SIG_ALG,
        "key_id": hashlib.sha256(pub).hexdigest()[:16],
        "public_key_b64": base64.b64encode(pub).decode(),
        "signature_b64": base64.b64encode(signature).decode(),
    }
    return record


def check(record, at=None, receipt=None, delegator_key=None):
    """Return (reasons, notes).

    reasons: the record does not hold. notes: it holds, but something about it is
    not established — today that is always "the identity is unbound" unless the
    caller supplies the delegator's public key, because the key travels inside the
    record and a record that carries its own key attests to nothing but itself.
    """
    reasons = []
    notes = []
    if not isinstance(record, dict):
        return ["the record is not a JSON object"], []
    if record.get("kind") != KIND:
        reasons.append("kind is %r, expected %r" % (record.get("kind"), KIND))

    delegator = record.get("delegator") or {}
    delegatee = record.get("delegatee") or {}
    for who, block in (("delegator", delegator), ("delegatee", delegatee)):
        if not isinstance(block.get("name"), str) or not block.get("name"):
            reasons.append("%s has no name" % who)
        if not isinstance(block.get("id"), str) or not block.get("id"):
            reasons.append("%s has no id" % who)
    did = str(delegator.get("id") or "").strip().lower()
    eid = str(delegatee.get("id") or "").strip().lower()
    if did and eid:
        if did == eid:
            reasons.append("the delegator and the delegatee are the same id: nobody can authorize themselves")
        elif str(delegator.get("name") or "").strip() == str(delegatee.get("name") or "").strip():
            reasons.append("the two sides share a name but not an id; a name is not an identity")

    scope = record.get("scope") or {}
    if not _is_hex64(scope.get("corpus_sha256")):
        reasons.append("scope.corpus_sha256 is not 64 lowercase hex characters")
    cases = scope.get("cases")
    total = scope.get("cases_total")
    if cases == "all":
        if not isinstance(total, int) or total <= 0:
            reasons.append("scope says all cases but cases_total is not a positive integer")
    elif isinstance(cases, list):
        if not cases:
            reasons.append("scope lists no cases and does not say all")
        if not all(isinstance(c, int) and c > 0 for c in cases):
            reasons.append("scope.cases contains something that is not a positive case number")
        if isinstance(total, int) and total > 0 and any(c > total for c in cases if isinstance(c, int)):
            reasons.append("scope names a case beyond cases_total")
        if len(set(cases)) != len(cases):
            reasons.append("scope names a case twice")
    else:
        reasons.append("scope.cases must be \"all\" or a list of case numbers")
    max_runs = scope.get("max_runs")
    if not isinstance(max_runs, int) or not (1 <= max_runs <= MAX_RUNS):
        reasons.append("scope.max_runs must be an integer from 1 to %d" % MAX_RUNS)
    if "directed" not in scope:
        reasons.append("scope.directed is absent; a directed run has to say so")
    if "corpus_name" in scope:
        reasons.append("scope carries a corpus_name; names drift, only the digest is checked")

    window = record.get("window") or {}
    start, err = _parse_time(window.get("not_before"), "window.not_before")
    reasons += [err] if err else []
    end, err = _parse_time(window.get("not_after"), "window.not_after")
    reasons += [err] if err else []
    if start and end:
        if end <= start:
            reasons.append("window.not_after is not after not_before")
        elif (end - start) > datetime.timedelta(days=MAX_WINDOW_DAYS):
            reasons.append("the window is longer than %d days" % MAX_WINDOW_DAYS)
        moment = at or datetime.datetime.now(datetime.timezone.utc)
        if moment < start:
            reasons.append("the window has not opened yet")
        if moment > end:
            reasons.append("the window closed at %s" % window.get("not_after"))

    nonce = record.get("nonce")
    if not isinstance(nonce, str) or len(nonce) < 16:
        reasons.append("nonce is shorter than 16 characters or absent")

    chain = record.get("chain") or {}
    if chain.get("depth") != 1:
        reasons.append("chain.depth is %r; this version allows exactly one hop" % chain.get("depth"))
    for forbidden in ("parent", "issued_by", "redelegated_from", "sub_delegation"):
        if forbidden in record or forbidden in chain:
            reasons.append("the record carries %r, which is a second hop" % forbidden)

    sig = record.get("signature") or {}
    if sig.get("alg") != SIG_ALG:
        reasons.append("signature.alg is %r" % sig.get("alg"))
    else:
        pub = _public_key(sig)
        if hashlib.sha256(pub).hexdigest()[:16] != sig.get("key_id"):
            reasons.append("signature.key_id does not match the recorded public key")
        try:
            sig_bytes = base64.b64decode(sig.get("signature_b64") or "")
        except Exception:
            sig_bytes = b""
        if not sig_bytes:
            reasons.append("signature.signature_b64 is empty")
        elif not ed25519.verify(pub, signed_bytes(record), sig_bytes):
            reasons.append("the Ed25519 signature does not verify over the canonical record")
        if delegator_key:
            if pub != bytes(delegator_key):
                reasons.append("the record is signed with a key that is not the delegator's known key")
            elif not ed25519.verify(bytes(delegator_key), signed_bytes(record), sig_bytes):
                reasons.append("the signature does not verify under the delegator's known key")
        elif not reasons:
            notes.append("identity unbound: the public key travels inside the record, so this proves the "
                         "record was signed by whoever wrote it, not that it was signed by %r — pass the "
                         "delegator's public key to bind it" % (delegator.get("name") or "the delegator"))

    if receipt is not None:
        reasons += _check_against_receipt(record, receipt)
    return reasons, notes


def _check_against_receipt(record, receipt):
    reasons = []
    scope = record.get("scope") or {}
    stored = receipt.get("corpus_sha256") or (receipt.get("corpus") or {}).get("sha256")
    if stored and stored != scope.get("corpus_sha256"):
        reasons.append("the receipt ran a different corpus than the one delegated")
    runner = receipt.get("run_by")
    name = runner.get("name") if isinstance(runner, dict) else runner
    if name and record.get("delegatee", {}).get("name") and \
            str(name).strip() != str(record["delegatee"]["name"]).strip():
        reasons.append("the receipt was produced by %r, not by the delegatee" % name)
    return reasons


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("record", help="the delegation record to check")
    parser.add_argument("--at", help="judge the window at this ISO 8601 time instead of now")
    parser.add_argument("--receipt", help="also check the record against a run receipt")
    parser.add_argument("--delegator-key", help="the delegator's known public key, hex, to bind the identity")
    args = parser.parse_args(argv)

    with open(args.record, encoding="utf-8") as f:
        record = json.load(f)
    at, err = (None, None)
    if args.at:
        at, err = _parse_time(args.at, "--at")
        if err:
            print("NOT ACCEPTABLE")
            print(" - " + err)
            return 1
    receipt = None
    if args.receipt:
        with open(args.receipt, encoding="utf-8") as f:
            receipt = json.load(f)
    key = None
    if args.delegator_key:
        try:
            key = bytes.fromhex(args.delegator_key.strip())
        except ValueError:
            print("NOT ACCEPTABLE")
            print(" - --delegator-key is not hex")
            return 1
    reasons, notes = check(record, at=at, receipt=receipt, delegator_key=key)
    if reasons:
        print("NOT ACCEPTABLE")
        for reason in reasons:
            print(" - " + reason)
        return 1
    scope = record["scope"]
    cases = scope["cases"] if scope["cases"] != "all" else "all %d" % scope["cases_total"]
    verdict = "ACCEPTABLE" if not notes else "ACCEPTABLE WITH A CAVEAT"
    print("%s — %s -> %s, corpus %s…, cases %s, %d run(s), window %s to %s, key %s"
          % (verdict, record["delegator"]["name"], record["delegatee"]["name"],
             scope["corpus_sha256"][:12], cases, scope["max_runs"],
             record["window"]["not_before"], record["window"]["not_after"],
             record["signature"]["key_id"]))
    for note in notes:
        print(" ! " + note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
