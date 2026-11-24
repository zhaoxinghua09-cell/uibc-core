#!/usr/bin/env python3
"""Judge our DSSE envelopes with an implementation that is not ours.

A hand-rolled envelope plus a hand-rolled verifier is a pair that can be wrong together.
This checker asks `securesystemslib` (the DSSE implementation underneath in-toto tooling)
whether the signature holds, so "conforms to DSSE" stops being self-declared.

Per-envelope results matter: tampering with one envelope must not be reported as
"the whole file is bad", and must not be reported as "the file is fine" either.

Usage:
    python tools/interop/dsse_external_check.py <envelope.json> [<tampered.json>]
"""
import argparse
import json
import pathlib
import sys

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_public_key

try:
    from securesystemslib.dsse import Envelope
    from securesystemslib.signer import SSlibKey
except ImportError:  # pragma: no cover
    sys.exit("securesystemslib is not installed: pip install 'securesystemslib>=1.6'")


def _key(pem_text, keyid):
    raw = load_pem_public_key(pem_text.encode()).public_bytes(Encoding.Raw, PublicFormat.Raw)
    return SSlibKey(keyid=keyid, keytype="ed25519", scheme="ed25519", keyval={"public": raw.hex()})


def check(path, threshold=1):
    """Return (accepted, total, failed_indexes)."""
    doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    accepted, failed = 0, []
    for i, env in enumerate(doc["envelopes"]):
        sig = env["signatures"][0]
        # Envelope.from_dict consumes the signature mapping, so copy what we still need
        key = _key(doc["public_key_pem"], sig["keyid"])
        env_obj = Envelope.from_dict({"payloadType": env["payloadType"], "payload": env["payload"],
                                      "signatures": [{"keyid": sig["keyid"], "sig": sig["sig"]}]})
        try:
            if env_obj.verify([key], threshold):
                accepted += 1
            else:
                failed.append(i)
        except Exception:
            failed.append(i)
    return accepted, len(doc["envelopes"]), failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("envelope")
    ap.add_argument("tampered", nargs="?", default=None)
    a = ap.parse_args(argv)

    good, total, failed = check(a.envelope)
    print(f"independent DSSE verify (securesystemslib): {good}/{total} envelope(s), failed={failed}")
    rc = 0 if good == total else 3

    if a.tampered:
        bad, btotal, bfailed = check(a.tampered)
        idx = json.loads(pathlib.Path(a.tampered).read_text(encoding="utf-8")).get("tampered_index")
        if idx is None:
            print("refusing to judge: the file does not say which envelope was tampered with")
            return 3
        if idx in bfailed:
            print(f"tampered envelope #{idx}: refused as required "
                  f"(file: {bad}/{btotal} verified, failed={bfailed})")
        else:
            print(f"REFUSE: the independent implementation accepted tampered envelope #{idx}")
            rc = 3
    return rc


if __name__ == "__main__":
    sys.exit(main())
