#!/usr/bin/env python3
"""External anchor: RFC 3161 timestamp over our checkpoint head (S16).

Why: S13 proves a leaf is inside a tree we built. It cannot prove the tree existed
at a given time - we are the only witness to our own clock. An RFC 3161 token from
an independent TSA is a second witness: it signs "this digest existed at time T"
with a key we do not control. That is the layer arkforge calls its "third
independent witness"; without it, `anchored` means only "pinned somewhere else of
ours".

Design decisions, and what they refuse to do:
  * only the head digest leaves the machine - never evidence, never paths;
  * verification is offline: the .tsr is checked against the CA chain shipped
    alongside it, so a later network change cannot rewrite history;
  * if the TSA is unreachable, the run FAILS CLOSED with status `unanchored`
    (exit 2). We never mark a package anchored because we tried.

The crypto lives in `uibc_core.tsa` so the package verifier can judge an
external token too; this file is only the network-facing CLI.

Usage:
    python tools/anchor_tsa.py --head-file <file> --out-dir <dir> [--tsa freetsa]
    python tools/anchor_tsa.py --verify <tsr> --data <head-file> --cabundle <pem>
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

# Allow `python tools/anchor_tsa.py ...` from the repository root without an install:
# the package directory sits one level above this file.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.tsa import build_request, parse_response, verify_token  # noqa: F401,E402

TSAS = {
    "open-tsa": {
        "url": "https://tsr.open-tsa.eu",
        "ca": ["https://open-tsa.eu/ca.pem"],
        "note": "free, open-source RFC 3161, Nürnberg DE",
    },
    "freetsa": {
        "url": "https://freetsa.org/tsr",
        "ca": ["https://freetsa.org/files/tsa.crt",
               "https://freetsa.org/files/cacert.pem"],
        "note": "free, long-running",
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--head-file", help="file whose digest is anchored")
    ap.add_argument("--out-dir", default="tools/out")
    ap.add_argument("--tsa", default="freetsa", choices=sorted(TSAS))
    ap.add_argument("--verify", help="existing .tsr to verify offline")
    ap.add_argument("--data", help="data file the token should cover")
    ap.add_argument("--cabundle", help="PEM bundle of the TSA's CA")
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    if args.verify:
        if not (args.data and args.cabundle):
            print("--verify needs --data and --cabundle")
            return 2
        tsr = open(args.verify, "rb").read()
        digest = hashlib.sha256(open(args.data, "rb").read()).digest()
        ok, info, probs = verify_token(tsr, digest, open(args.cabundle, "rb").read())
        print(json.dumps({"verified": ok, "info": info, "problems": probs},
                         indent=2, ensure_ascii=False, default=str))
        return 0 if ok else 3

    if not args.head_file:
        print("need --head-file")
        return 2
    os.makedirs(args.out_dir, exist_ok=True)
    raw = open(args.head_file, "rb").read()
    digest = hashlib.sha256(raw).digest()
    cfg = TSAS[args.tsa]

    req = build_request(digest)
    try:
        r = urllib.request.Request(cfg["url"], data=req, method="POST",
                                   headers={"Content-Type": "application/timestamp-query"})
        with urllib.request.urlopen(r, timeout=args.timeout) as resp:
            body = resp.read()
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        print(json.dumps({"status": "unanchored", "reason": "TSA unreachable: %s" % e},
                         ensure_ascii=False))
        return 2

    tsr_path = os.path.join(args.out_dir, "anchor_%s.tsr" % args.tsa)
    with open(tsr_path, "wb") as f:
        f.write(body)
    try:
        chunks = []
        for u in cfg["ca"]:
            with urllib.request.urlopen(u, timeout=args.timeout) as resp:
                chunks.append(resp.read())
        ca_pem = b"\n".join(chunks)
    except Exception:
        ca_pem = b""
    ca_path = os.path.join(args.out_dir, "anchor_%s_ca.pem" % args.tsa)
    with open(ca_path, "wb") as f:
        f.write(ca_pem)

    ok, info, probs = (verify_token(body, digest, ca_pem) if ca_pem
                       else (False, {}, ["CA bundle unavailable"]))
    rec = {
        "status": "anchored" if ok else "unanchored",
        "tsa": args.tsa,
        "head_sha256": digest.hex(),
        "tsr": os.path.basename(tsr_path),
        "tsr_sha256": hashlib.sha256(body).hexdigest(),
        "info": info,
        "problems": probs,
    }
    out = os.path.join(args.out_dir, "anchor_%s.json" % args.tsa)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False, default=str)
    print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))
    print("RESULT_JSON=%s" % out)
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
