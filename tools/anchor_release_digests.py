#!/usr/bin/env python3
"""Sign a release digest list and try to anchor it externally.

Peers publish digest files with a detached signature and two independent
timestamps (a `.ots` calendar proof and an RFC 3161 token). This tool does the
same three things for `CORPUS-DIGESTS.txt`, and refuses to overstate any of them:

    python tools/anchor_release_digests.py sign   --file release/CORPUS-DIGESTS.txt --out-dir release
    python tools/anchor_release_digests.py verify --sig release/CORPUS-DIGESTS.txt.sig
    python tools/anchor_release_digests.py anchor --file release/CORPUS-DIGESTS.txt --out-dir release

What each output means:

* `.sig` — Ed25519 over the exact bytes of the digest file. Verification is offline
  and needs only the public key recorded inside the sidecar.
* `.tsr` — an RFC 3161 token from an independent TSA, if one answered. A token is
  a *second* witness; its absence is recorded as `unanchored`, never as success.
* `.ots` — an OpenTimestamps calendar proof. A pending calendar proof is recorded
  as `pending_calendar`: it is not a Bitcoin anchor, and this tool will not print
  that word for it.

`ANCHORS.json` carries one status per item, so a reader can see which of the three
actually happened instead of trusting a sentence.
"""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _REPO)
sys.path.insert(0, _HERE)

from uibc_core import ed25519  # noqa: E402

SIG_SUFFIX = ".sig"
# The demo seed from the fixtures is public; signing a release with it would prove
# nothing about who signed. Refused rather than warned about.
PUBLIC_SEEDS = {
    "0000000000000000000000000000000000000000000000000000000000000000",
}


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _key_id(pub):
    return hashlib.sha256(pub).hexdigest()[:16]


def sign_file(path, seed, out=None, note=""):
    seed = bytes(seed)
    if len(seed) != 32:
        raise SystemExit("the signing seed must be 32 bytes")
    if seed.hex() in PUBLIC_SEEDS:
        raise SystemExit("refusing to sign with the public demo seed")
    with open(path, "rb") as f:
        message = f.read()
    pub = ed25519.publickey(seed)
    signature = ed25519.sign(seed, message)
    sidecar = {
        "kind": "uibc-detached-signature-v0",
        "alg": "ed25519",
        "file": os.path.basename(path),
        "file_bytes": len(message),
        "file_sha256": hashlib.sha256(message).hexdigest(),
        "key_id": _key_id(pub),
        "public_key_b64": base64.b64encode(pub).decode(),
        "signature_b64": base64.b64encode(signature).decode(),
        "note": note,
    }
    out = out or path + SIG_SUFFIX
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(sidecar, f, indent=2)
        f.write("\n")
    return out, sidecar


def verify_file(sig_path, file_path=None):
    """Return a list of reasons the signature does not hold. Empty means it does."""
    with open(sig_path, encoding="utf-8") as f:
        sidecar = json.load(f)
    target = file_path or os.path.join(os.path.dirname(sig_path), sidecar["file"])
    if not os.path.isfile(target):
        return ["the signed file is not next to the sidecar: %s" % target]
    with open(target, "rb") as f:
        message = f.read()
    reasons = []
    if sidecar.get("kind") != "uibc-detached-signature-v0":
        reasons.append("kind is %r" % sidecar.get("kind"))
    if sidecar.get("alg") != "ed25519":
        reasons.append("alg is %r" % sidecar.get("alg"))
    if hashlib.sha256(message).hexdigest() != sidecar.get("file_sha256"):
        reasons.append("the file no longer hashes to the digest the signature covers")
    if len(message) != sidecar.get("file_bytes"):
        reasons.append("the file is %d bytes, the sidecar records %s"
                       % (len(message), sidecar.get("file_bytes")))
    pub = base64.b64decode(sidecar.get("public_key_b64") or "")
    sig = base64.b64decode(sidecar.get("signature_b64") or "")
    if _key_id(pub) != sidecar.get("key_id"):
        reasons.append("key_id does not match the recorded public key")
    if not ed25519.verify(pub, message, sig):
        reasons.append("the Ed25519 signature does not verify")
    return reasons


def _run(argv, timeout=40):
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)


def anchor(path, out_dir, tsa="freetsa", offline=False):
    """Try TSA and OTS; record what actually happened for each."""
    status = {"file": os.path.basename(path), "file_sha256": _sha256_file(path)}

    if offline:
        status["tsa"] = {"state": "not attempted", "why": "offline requested"}
        status["ots"] = {"state": "not attempted", "why": "offline requested"}
    else:
        code, out = _run([sys.executable, os.path.join(_HERE, "anchor_tsa.py"),
                          "--head-file", path, "--out-dir", out_dir, "--tsa", tsa])
        if code == 0:
            status["tsa"] = {"state": "anchored", "detail": out.strip().splitlines()[-1][:200]}
        else:
            status["tsa"] = {"state": "unanchored",
                             "detail": (out or "no output").strip().splitlines()[-1][:200]}

        code, out = _run([sys.executable, os.path.join(_HERE, "anchor_ots.py"), "--stamp", path])
        if code == 0:
            text = out.lower()
            if "pending_calendar" in text or "pending calendar" in text:
                status["ots"] = {"state": "pending_calendar",
                                 "detail": "a calendar attestation, not a Bitcoin block"}
            else:
                status["ots"] = {"state": "anchored", "detail": out.strip().splitlines()[-1][:200]}
        else:
            status["ots"] = {"state": "unavailable",
                             "detail": (out or "no output").strip().splitlines()[-1][:200]}

    out = os.path.join(out_dir, "ANCHORS.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(status, f, indent=2)
        f.write("\n")
    return out, status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sign")
    s.add_argument("--file", required=True)
    s.add_argument("--out-dir", default=None)
    s.add_argument("--key-hex", default=None, help="32-byte seed in hex; defaults to UIBC_RELEASE_SEED_HEX")
    s.add_argument("--note", default="")

    v = sub.add_parser("verify")
    v.add_argument("--sig", required=True)
    v.add_argument("--file", default=None)

    a = sub.add_parser("anchor")
    a.add_argument("--file", required=True)
    a.add_argument("--out-dir", default=None)
    a.add_argument("--tsa", default="freetsa")
    a.add_argument("--offline", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "sign":
        seed_hex = args.key_hex or os.environ.get("UIBC_RELEASE_SEED_HEX")
        if not seed_hex:
            print("no seed: pass --key-hex or set UIBC_RELEASE_SEED_HEX")
            return 2
        seed = bytes.fromhex(seed_hex.strip())
        out_dir = args.out_dir or os.path.dirname(os.path.abspath(args.file))
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, os.path.basename(args.file) + SIG_SUFFIX)
        path, sidecar = sign_file(args.file, seed, out=out, note=args.note)
        print("signed %s — key %s" % (os.path.basename(args.file), sidecar["key_id"]))
        return 0

    if args.cmd == "verify":
        reasons = verify_file(args.sig, args.file)
        if reasons:
            print("NOT VERIFIED — %d reason(s):" % len(reasons))
            for r in reasons:
                print("  - " + r)
            return 1
        print("VERIFIED — signature over %s holds against the recorded public key"
              % json.load(open(args.sig, encoding="utf-8"))["file"])
        return 0

    out_dir = args.out_dir or os.path.dirname(os.path.abspath(args.file))
    out, status = anchor(args.file, out_dir, tsa=args.tsa, offline=args.offline)
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
