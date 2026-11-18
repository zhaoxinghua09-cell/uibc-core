"""Check a bundle against an anchor obtained outside it.

This is the tool a stranger runs. It takes two inputs that are supposed to have
arrived by different routes:

    the bundle   -- whatever the holder has, possibly rewritten
    the anchor   -- public key + checkpoint head, from a release page, a DNS
                    record, a log; anywhere the package cannot reach

and answers one question: **is this the package that publisher signed, in that
state?**

    ANCHORED          both the signature and the state match the anchor
    NOT ANCHORED      verified against the package's own key: proves nothing
                      about who sent it (this is the forgery envelope's row C)
    FAILED            one of the two does not match the anchor

Exit code is 0 only for ANCHORED.

    python3 tools/anchor_check.py BUNDLE_DIR [--anchor PATH]

BUNDLE_DIR may be the directory holding `package/` and `anchor.json`, or the
package directory itself (then --anchor is required). Nothing here trusts the
bundle: the anchor is read from disk only to avoid re-typing a value, and a real
deployment should compare it against the value a human copied from the channel.
"""
from __future__ import annotations

import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from uibc_core.verify import verify  # noqa: E402


def _jload(path):
    return json.load(open(path, encoding="utf-8"))


def _resolve(bundle_dir, anchor_path):
    pkg = os.path.join(bundle_dir, "package")
    if not os.path.isdir(pkg):
        pkg = bundle_dir
    if anchor_path is None:
        anchor_path = os.path.join(bundle_dir, "anchor.json")
    if not os.path.isfile(anchor_path):
        raise SystemExit("no anchor at %s - an anchor read out of the bundle alone "
                         "would prove what the bundle already claims" % anchor_path)
    return pkg, _jload(anchor_path)


def check(pkg, anchor):
    """Return a dict: anchored, verdict, reasons."""
    reasons = []
    pub_b64 = anchor.get("pubkey_b64")
    head = anchor.get("checkpoint_head")
    if not pub_b64 or not head:
        return {"anchored": False, "verdict": "FAILED",
                "reasons": ["anchor carries no pubkey_b64 and/or checkpoint_head"],
                "detail": []}
    try:
        pub = base64.b64decode(pub_b64.encode("ascii"), validate=True)
    except Exception:
        return {"anchored": False, "verdict": "FAILED",
                "reasons": ["anchor pubkey_b64 is not valid base64"],
                "detail": []}
    if len(pub) != 32:
        return {"anchored": False, "verdict": "FAILED",
                "reasons": ["anchor pubkey is not a 32-byte Ed25519 key"],
                "detail": []}

    v = verify(pkg, pubkey=pub, expect_head=head)
    fails = [c for c in v["checks"] if c["result"] == "FAIL"]
    inc = [c for c in v["checks"] if c["result"] == "INCONCLUSIVE"]
    for c in fails:
        reasons.append("%s %s: %s" % (c["id"], c["name"], c.get("detail", "")))

    anchored = (v["result"] == "PASS" and v.get("trust_level") == "anchored"
                and not fails)
    if v["result"] != "PASS" and not fails:
        reasons.append("verification incomplete: %s unresolved"
                       % ", ".join(c["id"] for c in inc))
    return {"anchored": anchored,
            "verdict": "ANCHORED" if anchored else
                       ("FAILED" if fails else "NOT ANCHORED"),
            "trust_level": v.get("trust_level"),
            "result": v["result"],
            "reasons": reasons,
            "detail": [{"id": c["id"], "result": c["result"],
                        "detail": c.get("detail", "")} for c in v["checks"]]}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit("usage: python3 tools/anchor_check.py BUNDLE_DIR [--anchor PATH]")
    anchor_path = None
    if "--anchor" in sys.argv:
        anchor_path = sys.argv[sys.argv.index("--anchor") + 1]
    pkg, anchor = _resolve(args[0], anchor_path)
    r = check(pkg, anchor)
    print("VERDICT: %s" % r["verdict"])
    if r.get("trust_level"):
        print("trust_level: %s   result: %s" % (r["trust_level"], r["result"]))
    for reason in r["reasons"]:
        print("  - %s" % reason)
    if r["verdict"] == "NOT ANCHORED":
        print("")
        print("The package verified against a key it supplied itself. That proves the")
        print("bytes were signed by that key, not that the publisher wrote them.")
        print("Pin the publisher's key and head out of band (see docs/PUBLISHER-IDENTITY.md).")
    return 0 if r["verdict"] == "ANCHORED" else 1


if __name__ == "__main__":
    sys.exit(main())
