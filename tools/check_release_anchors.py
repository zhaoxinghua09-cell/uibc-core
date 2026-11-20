#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check the timestamp a release publishes, without trusting the publisher.

The release carries `CORPUS-DIGESTS.txt`, `anchor_freetsa.tsr` and
`anchor_freetsa_ca.pem`. This tool downloads the three anonymously, verifies the
RFC 3161 token offline against the digest file, and says what it found:

    python tools/check_release_anchors.py                 # v0.4.1, over the network
    python tools/check_release_anchors.py --dir DIR       # three files already saved
    python tools/check_release_anchors.py --tag v0.4.1 --manifest ANCHORS.json

Exit codes: 0 the token verifies and its digest is the digest of the published
file; 1 the token is missing, does not verify, or attests a different digest;
3 the check could not be run (network unreachable, or the verifier cannot build).

What this does NOT establish: that FreeTSA is trustworthy, that the bytes were
produced by us, or that the digest list covers every asset. It establishes that
one independent party signed a specific digest at a specific time, and that this
digest is the digest of the file the release serves today.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RELEASE = "https://github.com/zhaoxinghua09-cell/uibc-core/releases/download"
FILES = ("CORPUS-DIGESTS.txt", "anchor_freetsa.tsr", "anchor_freetsa_ca.pem")


def _fetch(url, dest, attempts=3, timeout=45):
    """Download with curl when it exists, urllib otherwise.

    Measured 2026-11-20 on Windows: `curl.exe` fetched all three files while
    `urllib.request` timed out on the same URLs (`WinError 10060`), which made this
    checker report NOT MEASURED on a machine that could reach the release. A check
    that fails because of its own HTTP client is worse than no check, so curl goes
    first and urllib is only the fallback for machines without it.
    """
    curl = shutil.which("curl")
    if curl:
        for _ in range(attempts):
            proc = subprocess.run([curl, "-fsSL", "--max-time", str(timeout), "-o", dest, url],
                                  capture_output=True, text=True)
            if proc.returncode == 0 and os.path.isfile(dest):
                return os.path.getsize(dest)
        last = "curl exited %s" % proc.returncode
    else:
        last = None

    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                body = response.read()
            with open(dest, "wb") as handle:
                handle.write(body)
            return len(body)
        except (urllib.error.URLError, OSError) as exc:
            last = exc
    raise RuntimeError("could not download %s: %s" % (url.rsplit("/", 1)[-1], last))


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def verify_dir(directory, tag="v0.4.1"):
    """Verify the three files in `directory`. Returns (code, lines)."""
    lines = []
    missing = [name for name in FILES if not os.path.isfile(os.path.join(directory, name))]
    if missing:
        return 1, ["missing from %s: %s" % (directory, ", ".join(missing))]

    digest_path = os.path.join(directory, "CORPUS-DIGESTS.txt")
    lines.append("digest file  %s  %s bytes" % (_sha256(digest_path),
                                                os.path.getsize(digest_path)))

    code, out = _verify_token(os.path.join(directory, "anchor_freetsa.tsr"),
                              digest_path,
                              os.path.join(directory, "anchor_freetsa_ca.pem"))
    if code is None:
        return 3, ["could not run the verifier: %s" % out]
    blob = _json_block(out)
    if code != 0 or not blob or not blob.get("verified"):
        problems = (blob or {}).get("problems") or [out.strip().splitlines()[-1][:160]]
        return 1, lines + ["token does not verify: %s" % "; ".join(map(str, problems))]

    info = blob.get("info") or {}
    attested = str(info.get("digest_hex", ""))
    lines.append("token        gen_time %s, serial %s" % (info.get("gen_time"), info.get("serial")))
    lines.append("attested     %s" % attested)
    if attested != _sha256(digest_path):
        return 1, lines + ["token attests a different digest than the published file"]
    lines.append("OK           %s: an independent TSA signed the published digest, and it matches"
                 % tag)
    return 0, lines


def _verify_token(token, data, cabundle):
    try:
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "anchor_tsa.py"),
                               "--verify", token, "--data", data, "--cabundle", cabundle],
                              capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _json_block(text):
    body = text or ""
    start = body.find("{")
    end = body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(body[start:end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", default="v0.4.1")
    ap.add_argument("--dir", help="directory that already holds the three files")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.dir:
        code, lines = verify_dir(args.dir, tag=args.tag)
    else:
        directory = tempfile.mkdtemp(prefix="anchors_")
        base = "%s/%s" % (RELEASE, args.tag)
        try:
            for name in FILES:
                _fetch("%s/%s" % (base, name), os.path.join(directory, name))
        except RuntimeError as exc:
            print("NOT MEASURED - %s" % exc)
            return 3
        code, lines = verify_dir(directory, tag=args.tag)

    if args.json:
        print(json.dumps({"tag": args.tag, "exit": code, "lines": lines}, indent=2))
    else:
        for line in lines:
            print(line)
    print({0: "ACCEPTABLE", 1: "NOT ACCEPTABLE", 3: "NOT MEASURED"}[code])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
