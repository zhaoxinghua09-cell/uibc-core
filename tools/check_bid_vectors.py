# -*- coding: utf-8 -*-
"""Run the hand-authored BID conformance vectors against any checkout of uibc-core.

    python tools/check_bid_vectors.py --subject .

These vectors are OURS (written from the clause text, 2026-11-25), not Caict's.
The header of vectors/bid-resolution-v1.json says so, and the checker refuses to
print an "authoritative" label. A third party can edit expectations they think
are wrong; that is the point of publishing them as data rather than assertions
buried in test code.
"""
import argparse
import copy
import json
import os
import sys


def load(vectors_path):
    with open(vectors_path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default=".", help="checkout of uibc-core to test")
    ap.add_argument("--vectors", default=None)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    subject = os.path.abspath(args.subject)
    sys.path.insert(0, subject)
    from uibc_core import bid_protocol as B  # noqa: E402

    vectors_path = args.vectors or os.path.join(subject, "vectors", "bid-resolution-v1.json")
    pack = load(vectors_path)
    base = pack["document"]
    did = base["id"]
    fixture_path = os.path.join(subject, "fixtures", "bid", "signed_document.json")

    passed, failed = 0, []
    for case in pack["cases"]:
        cid, kind, exp = case["id"], case["kind"], case["expect"]
        try:
            got = run_case(B, kind, case["input"], base, did, fixture_path)
        except Exception as exc:  # noqa: BLE001
            got = {"raise": type(exc).__name__, "message": str(exc)}
            for attr in ("code", "kind", "retryable"):
                if hasattr(exc, attr):
                    got[attr if attr != "kind" else "kindClass"] = getattr(exc, attr)
        if matches(exp, got, B):
            passed += 1
            print("[PASS] %-4s %-10s %s" % (cid, case["clause"], case["note"]))
        else:
            failed.append((cid, exp, got))
            print("[FAIL] %-4s %-10s %s\n         expect=%s\n         got=%s"
                  % (cid, case["clause"], case["note"], exp, got))
    print("\n%d/%d passed  (%s)" % (passed, len(pack["cases"]), pack["provenance"]["status"][:40]))
    return 1 if failed else 0


def run_case(B, kind, inp, base, did, fixture_path):
    if kind == "envelope":
        payload = copy.deepcopy(inp)
        if payload.get("errorCode") not in (0, None):
            B.parse_bid_envelope(payload, did)   # must raise with the protocol's own code
            return {"ok": True}
        doc = payload["data"]["didDocument"]
        payload["data"]["didDocument"] = copy.deepcopy(base) if doc == "DOC" else doc
        out = B.parse_bid_envelope(payload, did)
        return {"ok": True, "id": out.get("id")}

    if kind == "document":
        doc = copy.deepcopy(base)
        for key, value in (inp.get("override") or {}).items():
            doc[key] = value
        for key, value in (inp.get("mutate") or {}).items():
            doc[key] = value
        parsed = B.parse_bid_document(doc, did)
        return {"ok": True, "warnings": len(parsed.warnings)}

    if kind == "signature":
        doc = json.load(open(fixture_path, encoding="utf-8"))
        for key, value in (inp.get("mutateAfterSigning") or {}).items():
            doc[key] = value
        ok, reason = B.verify_bid_document(doc)
        return {"ok": ok, "reason": reason}

    if kind == "trusted":
        spec = inp["answer"]["document"]
        doc = json.load(open(fixture_path, encoding="utf-8"))
        for key, value in (spec.get("mutateAfterSigning") or {}).items():
            doc[key] = value
        payload = {"errorCode": 0,
                   "data": {"version": "1.0.0", "verify": inp["answer"]["verify"], "didDocument": doc}}

        def f(url, timeout=10):
            return payload

        r = B.resolve_bid_trusted("http://r.example", doc["id"], fetcher=f)
        return {"serverVerify": r.server_verify, "trusted": r.trusted,
                "signatureOk": r.signature_ok, "delegate": r.delegate_state}

    if kind == "field":
        payload = inp["answer"]

        def f(url, timeout=10):
            return payload

        path = inp.get("path", "public-keys")
        if path == "public-keys":
            B.resolve_public_keys("http://r.example", did, key_id=did + "#key-1", fetcher=f)
        else:
            raise AssertionError("unsupported field path %r" % path)
        return {"ok": True}

    raise AssertionError("unknown kind %r" % kind)


def matches(exp, got, B):
    for key, value in exp.items():
        if got.get(key) != value:
            return False
    return True


if __name__ == "__main__":
    sys.exit(main())
