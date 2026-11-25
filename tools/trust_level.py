"""Three-state trust ladder, after C2PA's well-formed / valid / trusted.

Our verifier answers one question: is the evidence sufficient? It does not say
whether the signer is someone a given reader trusts. Conflating the two is how
"INCONCLUSIVE" becomes a bucket for two different problems. This tool keeps them
apart:

    well-formed : the package parses and its structure holds (no FAIL on the
                  structure axis); it makes sense as a package at all.
    valid       : the verifier's verdict is PASS with the key supplied.
    trusted     : valid, and the key's fingerprint is in the reader's trust list.

Trust is per-reader: the same package is trusted for one reader and not another,
and that is a policy input, not a property of the bytes.

Usage:
  python tools/trust_level.py --package <dir> --key <hexfile> [--trustlist list.json]
Exit: 0 always (prints the level); 2 harness error.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

STRUCTURE = ["S11", "S1", "S2", "S3", "S4", "S12", "S14", "S7", "S5", "S8"]


def fp(keyfile):
    return "sha256:" + hashlib.sha256(open(keyfile, "rb").read().strip()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--key")
    ap.add_argument("--trustlist")
    a = ap.parse_args()

    cmd = [sys.executable, "-m", "uibc_core.cli", "verify", a.package]
    if a.key:
        cmd += ["--key", a.key]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        doc = json.loads(p.stdout)
    except json.JSONDecodeError:
        print("ERROR: not a package response")
        return 2

    checks = {c["id"]: c["result"] for c in doc.get("checks", [])}
    well_formed = not any(checks.get(i) == "FAIL" for i in STRUCTURE)
    valid = doc.get("result") == "PASS"

    trusted = False
    why = "no trust list supplied"
    listed = False
    if a.trustlist and a.key:
        tl = json.load(open(a.trustlist, encoding="utf-8"))
        listed = fp(a.key) in tl.get("keys", [])
        why = "key in trust list" if listed else "key not in trust list"
    # A key on the list does not make an invalid package trusted: trust is the top
    # rung of a ladder, not a side door.
    trusted = bool(well_formed and valid and listed)

    level = "trusted" if (well_formed and valid and trusted) else ("valid" if (well_formed and valid) else
            ("well-formed" if well_formed else "not well-formed"))
    print(json.dumps({
        "level": level,
        "well_formed": well_formed,
        "valid": valid,
        "trusted": trusted,
        "verdict": doc.get("result"),
        "key_fingerprint": fp(a.key) if a.key else None,
        "reason": why,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
