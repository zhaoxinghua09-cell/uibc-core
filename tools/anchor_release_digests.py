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


def _detail_line(text):
    """The last line of a child's output, with machine paths reduced to filenames.

    ANCHORS.json is published on the release, so a line like
    `RESULT_JSON=C:\\Users\\ADMINI~1\\AppData\\Local\\Temp\\...\\anchor_freetsa.json`
    leaks a local layout into the artifact and tells a reader nothing they can use.
    Measured 2026-11-20, dry run of the release steps: the value was an absolute path
    that would differ on the CI machine and on every reader's machine.
    """
    body = (text or "").strip()
    line = body.splitlines()[-1] if body else "no output"
    if "=" in line:
        key, value = line.split("=", 1)
        value = value.strip()
        # Windows drive path or POSIX absolute path: publish the name only. Both
        # separators are normalised before the basename, because a Windows path handed
        # to a POSIX `basename` comes back whole — measured in CI on 2026-11-20, where
        # the test for a Windows path failed on Linux for exactly that reason.
        if value.startswith("/") or (len(value) > 2 and value[1] == ":" and value[2] in "\\/"):
            name = value.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            line = "%s=%s" % (key, name)
    return line[:200]


def _json_block(text):
    """The first JSON object in a child's output, or None.

    The stamper prints JSON and then a `status=` line, and on failure prints a
    JSON reason instead of a traceback tail, so the reason is parseable rather
    than being the last line of a stack trace.
    """
    import json as _json
    body = text or ""
    start = body.find("{")
    if start < 0:
        return None
    end = body.rfind("}")
    if end <= start:
        return None
    try:
        value = _json.loads(body[start:end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


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
            status["tsa"] = {"state": "anchored", "detail": _detail_line(out)}
        elif code == 3:
            # 3 means the environment cannot build a request at all (asn1crypto absent).
            # Measured 2026-11-20 in the release workflow, where that had been recorded
            # as `unanchored` with a NameError, which reads like a TSA refusing us.
            status["tsa"] = {"state": "unavailable", "detail": _detail_line(out)}
        else:
            status["tsa"] = {"state": "unanchored", "detail": _detail_line(out)}

        code, out = _run([sys.executable, os.path.join(_HERE, "anchor_ots.py"), "--stamp", path])
        blob = _json_block(out)
        if code == 0:
            calendar = blob.get("calendar") if blob else None
            if isinstance(calendar, str):
                calendar = calendar.replace("https://", "").replace("http://", "").rstrip("/")
            text = out.lower()
            if "pending_calendar" in text or "pending calendar" in text:
                status["ots"] = {"state": "pending_calendar",
                                 "detail": "calendar attestation from %s, not a Bitcoin block"
                                 % (calendar or "an unnamed calendar")}
            else:
                status["ots"] = {"state": "anchored", "detail": _detail_line(out)}
        else:
            reason = (blob or {}).get("reason") or _detail_line(out)
            status["ots"] = {"state": "unavailable", "detail": str(reason)[:200]}

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
