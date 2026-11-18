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


def anchor_digest(anchor):
    """The four values an RFC 3161 token should cover, canonically.

    A timestamp over the bundle's own bytes would prove the bundle existed;
    what has to be pinned is the *claim* - this agent, this key, this head.
    """
    import hashlib
    from uibc_core.canonical import canonicalize
    core = {k: anchor.get(k) for k in
            ("agent_id", "key_id", "pubkey_b64", "checkpoint_head")}
    return hashlib.sha256(canonicalize(core)).hexdigest()


def _check_tsa(anchor):
    """Judge the optional RFC 3161 block. Offline: token against the CA in the anchor.

    Two modes, and the difference is stated rather than smoothed over:

      covers="anchor_digest"  the token covers the four pinned values, so it
                              proves *this claim* existed at that time
      covers="file"           the token covers whatever data_sha256 names - a
                              release-status file, say - and proves only that
                              some bytes existed; binding is reported as
                              "unbound" for exactly that reason
    """
    import base64
    tsa = anchor.get("tsa")
    if not tsa:
        return {"present": False}
    tok = tsa.get("token_b64")
    cab = tsa.get("cabundle_b64")
    if not tok or not cab:
        return {"present": True, "ok": False, "binding": None,
                "why": "tsa block lacks token_b64 and/or cabundle_b64 - "
                       "an unchecked timestamp is not a timestamp"}
    try:
        tsr = base64.b64decode(tok.encode("ascii"), validate=True)
        cabundle = base64.b64decode(cab.encode("ascii"), validate=True)
    except Exception:
        return {"present": True, "ok": False, "binding": None,
                "why": "tsa token_b64/cabundle_b64 is not valid base64"}
    covers = tsa.get("covers", "anchor_digest")
    if covers == "anchor_digest":
        digest = bytes.fromhex(anchor_digest(anchor))
        binding = "anchor_digest"
    elif covers == "file":
        d = tsa.get("data_sha256") or ""
        if len(d) != 64:
            return {"present": True, "ok": False, "binding": "unbound",
                    "why": "covers=file needs a 64-hex data_sha256"}
        digest = bytes.fromhex(d)
        binding = "unbound"
    else:
        return {"present": True, "ok": False, "binding": covers,
                "why": "unknown tsa.covers %r" % (covers,)}

    from uibc_core.tsa import verify_token
    ok, info, probs = verify_token(tsr, digest, cabundle)
    gen = (info or {}).get("gen_time") if isinstance(info, dict) else None
    return {"present": True, "ok": bool(ok), "binding": binding,
            "gen_time": gen, "why": "; ".join(probs) if probs else ""}


def check_chain_position(anchor, prev):
    """Is this anchor the next one, or a replay of an earlier position?"""
    problems = []
    seq = anchor.get("seq")
    if not isinstance(seq, int) or seq < 1:
        return ["anchor carries no positive integer seq - it cannot be placed "
                "in the line, and an unplaceable anchor can always be replayed"]
    if seq == 1:
        if anchor.get("prev_anchor_digest") is not None:
            problems.append("seq 1 declares a predecessor")
        if prev is not None and prev.get("seq") != 1:
            problems.append("this is the first anchor of the line, but the caller "
                            "already holds seq %s - an older line was handed over"
                            % (prev.get("seq"),))
        return problems
    if prev is None:
        problems.append("seq %d has no predecessor supplied; the anchor names %s... "
                        "and that cannot be checked without it"
                        % (seq, str(anchor.get("prev_anchor_digest"))[:16]))
        return problems
    if not isinstance(prev.get("seq"), int) or prev["seq"] != seq - 1:
        problems.append("seq %d follows a supplied anchor at seq %s" % (seq, prev.get("seq")))
    elif anchor.get("prev_anchor_digest") != anchor_digest(prev):
        problems.append("prev_anchor_digest does not match the supplied predecessor")
    return problems


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

    tsa = _check_tsa(anchor)
    if tsa.get("present") and not tsa.get("ok"):
        reasons.append("tsa: %s" % (tsa.get("why") or "token does not verify"))

    anchored = (v["result"] == "PASS" and v.get("trust_level") == "anchored"
                and not fails and not (tsa.get("present") and not tsa.get("ok")))
    if v["result"] != "PASS" and not fails:
        reasons.append("verification incomplete: %s unresolved"
                       % ", ".join(c["id"] for c in inc))
    return {"anchored": anchored,
            "verdict": "ANCHORED" if anchored else
                       ("FAILED" if fails or (tsa.get("present") and not tsa.get("ok"))
                        else "NOT ANCHORED"),
            "tsa": tsa,
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
    prev_path = None
    if "--prev" in sys.argv:
        prev_path = sys.argv[sys.argv.index("--prev") + 1]
    pkg, anchor = _resolve(args[0], anchor_path)
    prev = _jload(prev_path) if prev_path else None
    r = check(pkg, anchor)
    chain_problems = check_chain_position(anchor, prev) if prev_path else []
    if chain_problems:
        r = dict(r, verdict="FAILED", anchored=False,
                 reasons=list(r.get("reasons", [])) + ["chain: " + p for p in chain_problems])
    if anchor.get("seq") is not None:
        print("seq: %s%s" % (anchor.get("seq"),
                             "" if anchor.get("prev_anchor_digest") is None
                             else "  follows %s..." % anchor["prev_anchor_digest"][:16]))
    print("VERDICT: %s" % r["verdict"])
    if r.get("trust_level"):
        print("trust_level: %s   result: %s" % (r["trust_level"], r["result"]))
    tsa = r.get("tsa") or {}
    if tsa.get("present"):
        print("timestamp: %s (%s)%s" % ("valid" if tsa.get("ok") else "INVALID",
                                        tsa.get("binding") or "?",
                                        (" at " + tsa["gen_time"]) if tsa.get("gen_time") else ""))
    elif tsa is not None:
        print("timestamp: none - the anchor pins a key and a head, not a moment")
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
