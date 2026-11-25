#!/usr/bin/env python
"""Shape probe: does §4.2.1 reject every document that is actually wrong?

The protocol lists the shapes a document may not have, and the subject has a
handful of tests for them. Hand-picked cases test the cases you thought of. This
tool mutates one thing at a time in a valid document - deletes a field, swaps a
type, points an `authentication` entry at a key nobody defines - and records for
each mutant whether it was refused, refused for the *right* reason, or quietly
accepted.

Output classes per mutant:

  rejected  - BIDDocumentError (the document was refused)
  silent    - accepted; the document parses and nothing was said

`silent` is the interesting column: it is a shape the protocol forbids and the
implementation swallows. Those are listed with the field name, not summarised.

    python tools/mutate_document_shapes.py            # human table
    python tools/mutate_document_shapes.py --json     # machine output
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import bid_protocol as B

DID = "did:bid:ef18F9AVK4SQLZPRrPkrVWwp9kbpdXHx"
KEY_ID = DID + "#key-1"
KEY_HEX = ("b06566f76733ae048fda721d47afe8780b572636496c93253db86dc8d54e3f9a")


def base_document():
    return {
        "@context": ["https://w3.org/ns/did/v1"],
        "id": DID,
        "created": "2021-06-24T09:10:09Z",
        "updated": "2021-06-24T09:10:09Z",
        "authentication": [KEY_ID],
        "publicKey": [
            {"controller": DID, "id": KEY_ID, "publicKeyHex": KEY_HEX,
             "type": "ED25519"},
        ],
        "extension": {"ttl": 86400, "type": 105},
    }


def _with(path, value):
    """Copy the base document and set one dotted path to a value (`None` deletes)."""
    doc = copy.deepcopy(base_document())
    parts = path.split(".")
    node = doc
    for part in parts[:-1]:
        if part.isdigit():
            node = node[int(part)]
        else:
            node = node.setdefault(part, {})
    last = parts[-1]
    if value is DELETE:
        if last.isdigit():
            del node[int(last)]
        else:
            node.pop(last, None)
    elif last.isdigit():
        index = int(last)
        if index >= len(node):
            node.append(value)          # "publicKey.1" on a one-entry list: add a second
        else:
            node[index] = value
    else:
        node[last] = value
    return doc


class _Delete:
    def __repr__(self):
        return "<delete>"


DELETE = _Delete()


def mutants():
    """Every mutant is one edit. `must` says what the protocol requires of it."""
    return [
        # --- identity
        ("id deleted", _with("id", DELETE), "reject"),
        ("id is another BID", _with("id", "did:bid:efNOTthisone000000000000000000"), "reject"),
        ("id is a number", _with("id", 123), "reject"),
        # --- publicKey
        ("publicKey is an object", _with("publicKey", {}), "reject"),
        ("publicKey entry is a string", _with("publicKey.0", "x"), "reject"),
        ("publicKey.id has no #", _with("publicKey.0.id", DID), "reject"),
        ("publicKey.id duplicated", _with("publicKey.1",
                                          {"controller": DID, "id": KEY_ID,
                                           "publicKeyHex": KEY_HEX, "type": "ED25519"}),
         "reject"),
        ("controller is not a BID", _with("publicKey.0.controller", "did:example:123"), "reject"),
        ("publicKeyHex is not hex", _with("publicKey.0.publicKeyHex", "zz" * 35), "reject"),
        ("publicKeyHex is odd-length hex", _with("publicKey.0.publicKeyHex", "b06566f7f"), "reject"),
        # --- authentication
        ("authentication is an object", _with("authentication", {}), "reject"),
        ("authentication names an undefined key", _with("authentication", [DID + "#key-9"]), "reject"),
        ("authentication entry is a number", _with("authentication", [123]), "reject"),
        # --- alsoKnownAs
        ("alsoKnownAs is an object", _with("alsoKnownAs", {}), "reject"),
        ("alsoKnownAs.type is a string", _with("alsoKnownAs", [{"type": "1"}]), "reject"),
        ("alsoKnownAs.type is a bool", _with("alsoKnownAs", [{"type": True}]), "reject"),
        # --- service
        ("service is an object", _with("service", {}), "reject"),
        ("service entry has no id", _with("service", [{"type": "DIDSubResolver"}]), "reject"),
        ("service entry has no type", _with("service", [{"id": "#svc"}]), "reject"),
        ("DIDSubResolver without serviceEndpoint",
         _with("service", [{"id": "#svc", "type": "DIDSubResolver"}]), "reject"),
        # --- extension
        ("extension is a string", _with("extension", "x"), "reject"),
        # --- these are not violations: the protocol is extensible
        ("an unknown top-level field is added", _with("x-unknown", {"a": 1}), "accept"),
        # --- observed, not adjudicated: the text is checked separately before we
        #     claim either "must refuse" or "may accept"
        ("created deleted", _with("created", DELETE), "reject"),
        ("created is not an ISO time", _with("created", "2021/06/24 09:10:09"), "reject"),
        ("updated is a number", _with("updated", 1624525809), "reject"),
        ("updated deleted", _with("updated", DELETE), "reject"),
        ("Ed25519 key is 4 hex chars", _with("publicKey.0.publicKeyHex", "b065"), "observe"),
        ("publicKeyHex deleted", _with("publicKey.0.publicKeyHex", DELETE), "observe"),
        ("key type is RSA", _with("publicKey.0.type", "RSA"), "observe"),
        ("service type is unknown", _with("service", [{"id": "#svc", "type": "X-Unknown",
                                                       "serviceEndpoint": "https://x"}]), "observe"),
        ("alsoKnownAs.type 999 (not in appendix 1)",
         _with("alsoKnownAs", [{"type": 999, "value": "x"}]), "observe"),
    ]


def probe():
    rows = []
    for name, doc, must in mutants():
        try:
            parsed = B.parse_bid_document(doc, DID)
            warnings = list(getattr(parsed, "warnings", []))
            outcome = "warned" if warnings else "silent"
            reason = "; ".join(warnings)
        except B.BIDDocumentError as exc:
            outcome, reason = "rejected", str(exc)
        except Exception as exc:                                  # noqa: BLE001
            outcome, reason = "wrong-error", "%s: %s" % (type(exc).__name__, exc)
        rows.append({"mutant": name, "must": must, "outcome": outcome,
                     "reason": reason[:160]})
    return rows


REASONS = {
    "id deleted": "does not match the request",
    "publicKey is an object": "must be an array",
    "authentication names an undefined key": "no publicKey defines",
    "controller is not a BID": "is not a BID",
}


def summarise(rows):
    must_reject = [r for r in rows if r["must"] == "reject"]
    caught = [r for r in must_reject if r["outcome"] == "rejected"]
    silent = [r for r in must_reject if r["outcome"] in ("silent", "warned")]
    wrong = [r for r in rows if r["outcome"] == "wrong-error"]
    tolerated = [r for r in rows if r["must"] == "accept"]
    observed = [r for r in rows if r["must"] == "observe"]
    return {"total": len(rows), "must_reject": len(must_reject),
            "caught": len(caught), "silent": [r["mutant"] for r in silent],
            "wrong_error": [r["mutant"] for r in wrong],
            "tolerated": [{"mutant": r["mutant"], "outcome": r["outcome"]}
                          for r in tolerated],
            "observed": [{"mutant": r["mutant"], "outcome": r["outcome"],
                          "reason": r["reason"]} for r in observed]}


def type_relabel_is_caught_by_verification():
    """Parsing tolerates an unknown key type (§4.2.1 calls it a string, no list).

    The question the probe must answer is whether that silence is harmless. Sign a
    real document, relabel the same key as RSA, and ask the verifier: if it says
    "verified", the silence at parse time would be a hole.
    """
    from uibc_core import bid_address as AD

    seed, pub_hex = B.generate_ed25519_pair()
    did = AD.derive_did(pub_hex, "Ed25519")["did"]   # derive_did returns parts, not a string
    key_id = did + "#key-1"
    doc = {
        "id": did,
        "created": "2021-06-24T09:10:09Z",
        "updated": "2021-06-24T09:10:09Z",
        "authentication": [key_id],
        "publicKey": [{"controller": did, "id": key_id, "publicKeyHex": pub_hex,
                       "type": "ED25519"}],
    }
    signed = B.sign_bid_document(doc, seed, key_id)
    ok, why = B.verify_bid_document(signed, did)
    relabelled = copy.deepcopy(signed)
    relabelled["publicKey"][0]["type"] = "RSA"
    ok2, why2 = B.verify_bid_document(relabelled, did)
    return {"honest_doc_verifies": ok, "honest_reason": why,
            "relabelled_verifies": ok2, "relabelled_reason": why2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = probe()
    summary = summarise(rows)
    if args.json:
        payload = {"summary": summary, "rows": rows,
                   "type_relabel": type_relabel_is_caught_by_verification()}
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0
    print("document shape probe: %d mutants, %d of them must be refused"
          % (summary["total"], summary["must_reject"]))
    for row in rows:
        mark = {"rejected": "REFUSED ", "silent": "SILENT  ", "warned": "WARNED  ",
                "wrong-error": "WRONG-ERR"}[row["outcome"]]
        print("  %s %-44s %s" % (mark, row["mutant"], row["reason"][:78]))
    print("\n  refused %d / %d required" % (summary["caught"], summary["must_reject"]))
    print("  silent: %s" % (", ".join(summary["silent"]) or "none"))
    print("  wrong exception type: %s" % (", ".join(summary["wrong_error"]) or "none"))
    relabel = type_relabel_is_caught_by_verification()
    print("  key type relabelled ED25519 -> RSA: honest=%s relabelled=%s (%s)"
          % (relabel["honest_doc_verifies"], relabel["relabelled_verifies"],
             relabel["relabelled_reason"][:60]))
    for item in summary["tolerated"]:
        print("  (must tolerate) %s -> %s" % (item["mutant"], item["outcome"]))
    if summary["observed"]:
        print("\n  observed (no verdict yet - the text decides, not this probe):")
        for item in summary["observed"]:
            print("    %-8s %-44s %s" % (item["outcome"], item["mutant"], item["reason"][:60]))
    return 0 if not summary["silent"] and not summary["wrong_error"] else 1


if __name__ == "__main__":
    sys.exit(main())
