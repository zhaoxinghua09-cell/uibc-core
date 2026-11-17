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
  * verification is offline: the .tsr is checked against the TSA certificate
    chain shipped alongside it, so a later network change cannot rewrite history;
  * if the TSA is unreachable, the run FAILS CLOSED with status `unanchored`
    (exit 2). We never mark a package anchored because we tried.

Usage:
    python tools/anchor_tsa.py --head-file <file> --out-dir <dir> [--tsa open-tsa]
    python tools/anchor_tsa.py --verify <tsr> --data <head-file> --cabundle <pem>
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

from asn1crypto import cms, tsp, x509

TSAS = {
    "open-tsa": {
        "url": "https://tsr.open-tsa.eu",
        "ca": "https://open-tsa.eu/ca.pem",
        "note": "free, open-source RFC 3161, Nürnberg DE",
    },
    "freetsa": {
        "url": "https://freetsa.org/tsr",
        "ca": ["https://freetsa.org/files/tsa.crt",
               "https://freetsa.org/files/cacert.pem"],
        "note": "free, long-running",
    },
}


def build_request(digest: bytes, sha_alg: str = "sha256") -> bytes:
    req = tsp.TimeStampReq({
        "version": "v1",
        "message_imprint": {
            "hash_algorithm": {"algorithm": sha_alg},
            "hashed_message": digest,
        },
        "cert_req": True,
        "nonce": int.from_bytes(hashlib.sha256(digest).digest()[:8], "big"),
    })
    return req.dump()


def parse_response(body: bytes):
    """Return (ok, info, problems). info carries genTime, digest, serial."""
    problems = []
    try:
        resp = tsp.TimeStampResp.load(body)
    except Exception as e:
        return False, {}, ["response is not a TimeStampResp (%s)" % e]

    try:
        status = resp["status"]["status"].native
    except Exception as e:
        return False, {}, ["response has no readable status (%s)" % e]
    if status not in ("granted", "granted_with_mods"):
        fail = resp["status"]["fail_info"]
        text = fail.native if fail else status
        return False, {}, ["TSA refused: %s" % text]

    token = resp["time_stamp_token"]
    try:
        sd = token["content"]
        tst = sd["encap_content_info"]["content"]
        tst = tst.parsed if not isinstance(tst, tsp.TSTInfo) else tst
    except Exception as e:
        return False, {}, ["cannot read TSTInfo from token (%s)" % e]

    digest = tst["message_imprint"]["hashed_message"].native
    gen_time = tst["gen_time"].native
    serial = tst["serial_number"].native
    info = {
        "gen_time": gen_time.isoformat() if hasattr(gen_time, "isoformat") else str(gen_time),
        "digest_hex": digest.hex() if isinstance(digest, bytes) else str(digest),
        "serial": str(serial),
        "policy": tst["policy"].native,
        "tsa": tst["tsa"].native if "tsa" in tst else None,
    }
    return True, info, problems


def verify_token(tsr_bytes: bytes, data_digest: bytes, cabundle_pem: bytes):
    """Offline checks: parse, digest match, signer certificate resolves to the CA."""
    ok, info, problems = parse_response(tsr_bytes)
    if not ok:
        return False, info, problems
    if info["digest_hex"] != data_digest.hex():
        problems.append("token's messageImprint is not the digest we asked about")

    try:
        sd = tsp.TimeStampResp.load(tsr_bytes)["time_stamp_token"]["content"]
        certs = [c.chosen for c in sd["certificates"] if c.name == "certificate"]
    except Exception as e:
        return False, info, problems + ["cannot read certificates (%s)" % e]

    # chain check: at least one shipped cert must be issued by a CA in the bundle
    from cryptography import x509 as cx509
    from cryptography.hazmat.primitives.asymmetric import padding, ec
    from cryptography.hazmat.primitives import hashes

    ca_certs = []
    for chunk in cabundle_pem.split(b"-----END CERTIFICATE-----"):
        if b"-----BEGIN CERTIFICATE-----" in chunk:
            pem = chunk + b"-----END CERTIFICATE-----\n"
            try:
                ca_certs.append(cx509.load_pem_x509_certificate(pem))
            except Exception:
                pass

    signer = None
    for cert in certs:
        try:
            c = cx509.load_der_x509_certificate(cert.dump())
        except Exception:
            continue
        for ca in ca_certs:
            try:
                c.verify_directly_issued_by(ca)
                signer = c
                break
            except Exception:
                continue
        if signer:
            break
    if not signer:
        problems.append("no certificate in the token chains to the supplied CA bundle")

    if signer:
        try:
            sig = sd["signer_infos"][0]
            attrs = sig["signed_attrs"]
            if attrs:
                # CMS signs the SET OF signed attrs, i.e. the same bytes with the
                # [0] IMPLICIT wrapper replaced by SEQUENCE (0xA0 -> 0x31). Signing
                # the wrapped bytes is the single most common way to fail this.
                tbs = attrs.dump()
                if tbs and tbs[0] == 0xA0:
                    tbs = b"\x31" + tbs[1:]
            else:
                tbs = sd["encap_content_info"]["content"].dump()
            signature = sig["signature"].native
            digest_alg = sig["digest_algorithm"]["algorithm"].native
            pub = signer.public_key()
            if digest_alg == "sha256":
                h = hashes.SHA256()
            elif digest_alg == "sha384":
                h = hashes.SHA384()
            elif digest_alg == "sha512":
                h = hashes.SHA512()
            else:
                h = hashes.SHA256()
            key_name = type(pub).__name__
            if "rsa" in key_name.lower():
                pub.verify(signature, tbs, padding.PKCS1v15(), h)
            elif "ed25519" in key_name.lower():
                pub.verify(signature, tbs)
            else:
                pub.verify(signature, tbs, ec.ECDSA(h))
            info["signature_verified"] = True
        except Exception as e:
            problems.append("signature check failed (%s: %s)"
                            % (type(e).__name__, str(e) or "no message"))
            info["signature_verified"] = False

    return (not problems), info, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--head-file", help="file whose digest is anchored")
    ap.add_argument("--out-dir", default="tools/out")
    ap.add_argument("--tsa", default="open-tsa", choices=sorted(TSAS))
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
        ca_urls = cfg["ca"] if isinstance(cfg["ca"], list) else [cfg["ca"]]
        chunks = []
        for u in ca_urls:
            with urllib.request.urlopen(u, timeout=args.timeout) as resp:
                chunks.append(resp.read())
        ca_pem = b"\n".join(chunks)
    except Exception:
        ca_pem = b""
    ca_path = os.path.join(args.out_dir, "anchor_%s_ca.pem" % args.tsa)
    with open(ca_path, "wb") as f:
        f.write(ca_pem)

    ok, info, probs = verify_token(body, digest, ca_pem) if ca_pem else (False, {}, ["CA bundle unavailable"])
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
