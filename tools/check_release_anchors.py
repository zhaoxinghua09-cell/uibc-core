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



PIN = os.path.join(ROOT, "anchors", "pins", "uibc-release-{tag}.json")
REPO = "zhaoxinghua09-cell/uibc-core"


def _live_manifest(tag):
    """name -> sha256 of every asset on the release, read through gh.

    gh is preferred because it answers from the API without downloading 400 KB of
    assets; a machine without gh falls back to hashing what it downloads.
    """
    gh = shutil.which("gh")
    if not gh:
        return None
    proc = subprocess.run([gh, "api", "repos/%s/releases/tags/%s" % (REPO, tag),
                           "--jq", '.assets[] | .name + " " + (.digest // "")'],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return None
    manifest = {}
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].startswith("sha256:"):
            manifest[parts[0]] = parts[1].split(":", 1)[1]
        elif parts:
            manifest[parts[0]] = ""
    return manifest


def check_pin(tag, live, resolve=None):
    """Compare the live release against anchors/pins/uibc-release-<tag>.json.

    Returns (bad, lines, unsure). `unsure` counts assets the page does not report a
    digest for: those are neither a match nor a mismatch until the bytes are hashed.
    A caller that cannot hash them must report the result as unmeasured rather than
    accepting it.
    """
    path = PIN.format(tag=tag)
    if not os.path.isfile(path):
        return None, []
    with open(path, encoding="utf-8") as handle:
        pin = json.load(handle)
    expected = {a["name"]: a["sha256"] for a in pin.get("assets", [])}
    lines, bad, unsure = [], 0, 0
    for name, digest in sorted(expected.items()):
        if name not in live:
            lines.append("missing    %s (pinned, not on the page)" % name)
            bad += 1
        elif not live[name]:
            if resolve is None:
                lines.append("unreported %s: the page reports no digest; not compared" % name)
                unsure += 1
                continue
            try:
                got = resolve(name)
            except Exception as exc:  # the bytes could not be fetched
                lines.append("unsure     %s: %s" % (name, exc))
                unsure += 1
                continue
            if got != digest:
                lines.append("changed    %s: pinned %s…, bytes hash to %s…"
                             % (name, digest[:12], got[:12]))
                bad += 1
            else:
                lines.append("hashed     %s: no digest reported, bytes match the pin" % name)
        elif live[name] != digest:
            lines.append("changed    %s: pinned %s… now %s…" % (name, digest[:12], live[name][:12]))
            bad += 1
    # A pin records the page it froze, so the page's own pin file is legitimately
    # absent from it: make_release_pin lists that name under "excluded". Ignoring the
    # key instead of the convention is what made v0.5.0 report an unpinned asset.
    excluded = set(pin.get("excluded") or [])
    for name in sorted(set(live) - set(expected) - excluded):
        if not live[name]:
            # An asset the pin never saw, whose bytes this check cannot measure.
            lines.append("unpinned   %s is on the page but not in the pin, and reports no digest"
                         % name)
            unsure += 1
            continue
        lines.append("unpinned   %s is on the page but not in the pin" % name)
        bad += 1
    return bad, lines, unsure



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


def _before_freeze(gen_time, frozen_at):
    """True when a claimed signing time precedes the freeze it is supposed to follow.

    Comparing these two strings works because both are UTC timestamps in the same
    shape (YYYY-MM-DDTHH:MM:SS+00:00 / ...Z); a timezone other than UTC would need
    parsing, and the tokens this repository accepts are FreeTSA's, which are UTC.
    """
    if not gen_time or not frozen_at:
        return False
    return gen_time.replace("+00:00", "Z") <= frozen_at.replace("+00:00", "Z")


def _download_sha256(tag, name, tmpdir=None):
    """Hash an asset from the bytes the page serves.

    Needed when the API reports no digest for an asset -- which happens for assets
    uploaded before GitHub started computing them, and would happen again if it
    stopped. Treating an unreported digest as a match is how a check goes green
    without measuring anything, so it is resolved by hashing the bytes instead.
    """
    gh = shutil.which("gh")
    if not gh:
        raise RuntimeError("gh unavailable, so the bytes cannot be fetched")
    tmpdir = tmpdir or tempfile.mkdtemp(prefix="uibc_hash_")
    proc = subprocess.run([gh, "release", "download", tag, "-R", REPO,
                           "-p", name, "-D", tmpdir, "--clobber"],
                          capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:200])
    return _sha256(os.path.join(tmpdir, name))


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

    # The token is only one witness. When a signature is also on the page, check it
    # against the key this repository records, because a signature verified with a
    # public key that travels inside the signature proves integrity and nothing about
    # who signed. Measured 2026-11-20: v0.4.1 predates the signing key, so this branch
    # is exercised by the first release after it.
    sig = os.path.join(directory, "CORPUS-DIGESTS.txt.sig")
    pinned = _pinned_key()
    if not os.path.isfile(sig):
        # The page may be frozen without a signature, which is the case for v0.4.1.
        # A signature held in the repository over the digest the page serves still
        # identifies the publisher -- and it does not rewrite the page to say so.
        held = os.path.join(ROOT, "anchors", "attestations", tag, "CORPUS-DIGESTS.txt.sig")
        if not os.path.isfile(held):
            lines.append("signature    none published, none held in the repository; "
                         "not a failure, but nothing identifies the publisher either")
            return 0, lines
        code, out = _verify_sig(held, digest_path)
        if code is None:
            return 3, lines + ["could not run the signature verifier: %s" % out]
        heldblob = _json_block(out)
        if code != 0 or not heldblob:
            return 1, lines + ["the repository-held signature does not verify against the "
                               "published bytes: %s"
                               % (out.strip().splitlines() or [""])[-1][:160]]
        held_key = str(heldblob.get("key_id", ""))
        lines.append("signature    held in the repository (the page itself carries "
                     "UNSIGNED.txt): key_id %s over %s…"
                     % (held_key, str(heldblob.get("file_sha256", ""))[:12]))
        if pinned and held_key != pinned:
            return 1, lines + ["the repository-held signature uses key_id %s, but this "
                               "repository records %s" % (held_key, pinned)]
        if not pinned:
            return 1, lines + ["the repository-held signature verified but no key is "
                               "recorded in anchors/release-signing-key.json"]
        lines.append("publisher    identified by the key recorded in this repository")
        # Who signed, and when. The second question needs a witness that is not us:
        # without a token, "signed after publication" is a sentence, not a fact.
        tok = os.path.join(os.path.dirname(held), "anchor_freetsa.tsr")
        ca = os.path.join(os.path.dirname(held), "anchor_freetsa_ca.pem")
        if not (os.path.isfile(tok) and os.path.isfile(ca)):
            lines.append("signed_at    no timestamp on the signature: the publisher is "
                         "identified, the time is only asserted")
            return 0, lines
        tok_code, tok_out = _verify_token(tok, held, ca)
        if tok_code is None:
            return 3, lines + ["could not run the timestamp verifier: %s" % tok_out]
        tok_blob = _json_block(tok_out)
        if tok_code != 0 or not tok_blob or not tok_blob.get("verified"):
            problems = (tok_blob or {}).get("problems") or ["token does not verify"]
            return 1, lines + ["the timestamp on the signature does not verify: %s"
                               % "; ".join(map(str, problems))]
        info = tok_blob.get("info") or {}
        gen = str(info.get("gen_time", ""))
        lines.append("signed_at    %s, attested by a third party (serial %s)"
                     % (gen, info.get("serial")))
        frozen = None
        pin_path = os.path.join(ROOT, "anchors", "pins", "uibc-release-%s.json" % tag)
        if os.path.isfile(pin_path):
            with open(pin_path, encoding="utf-8") as handle:
                frozen = (json.load(handle) or {}).get("frozen_at")
        if _before_freeze(gen, frozen):
            return 1, lines + ["the signature is timestamped %s, before the page was frozen "
                               "at %s: that is earlier than the claim it supports"
                               % (gen, frozen)]
        if frozen:
            lines.append("order        the signature is later than the freeze (%s), as the "
                         "attestation claims" % frozen)
        return 0, lines
    code, out = _verify_sig(sig, digest_path)
    if code is None:
        return 3, lines + ["could not run the signature verifier: %s" % out]
    sigblob = _json_block(out)
    if code != 0 or not sigblob:
        return 1, lines + ["signature does not verify: %s" % (out.strip().splitlines() or [""])[-1][:160]]
    key_id = str(sigblob.get("key_id", ""))
    lines.append("signature    key_id %s, file_sha256 %s" % (key_id, sigblob.get("file_sha256")))
    if pinned and key_id != pinned:
        return 1, lines + ["signature uses key_id %s, but this repository records %s"
                           % (key_id, pinned)]
    if not pinned:
        return 1, lines + ["the signature verified but no key is recorded in "
                           "anchors/release-signing-key.json, so the signer is unidentified"]
    return 0, lines


def _pinned_key():
    """key_id recorded in anchors/release-signing-key.json, or None."""
    path = os.path.join(ROOT, "anchors", "release-signing-key.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return (json.load(handle) or {}).get("key_id") or None


def _verify_sig(sig, data):
    try:
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "anchor_release_digests.py"),
                               "verify", "--sig", sig, "--file", data, "--json"],
                              capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


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


def _newest_pinned_tag():
    """The release this repository pinned most recently, so the default is not frozen.

    Measured 2026-11-20: the default was the string "v0.4.1", so after v0.5.0 was published
    the tool verified the *previous* release and labelled the numbers with its tag.
    """
    pins = os.path.join(ROOT, "anchors", "pins")
    best = None
    for name in sorted(os.listdir(pins)) if os.path.isdir(pins) else []:
        if not (name.startswith("uibc-release-") and name.endswith(".json")):
            continue
        try:
            blob = json.loads(open(os.path.join(pins, name), encoding="utf-8").read())
        except (ValueError, OSError):
            continue
        stamp = blob.get("frozen_at") or blob.get("recorded_at") or ""
        tag = blob.get("tag") or name[len("uibc-release-"):-len(".json")]
        if best is None or stamp > best[0]:
            best = (stamp, tag)
    return best[1] if best else "v0.4.1"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", default=None,
                    help="default: the newest release pin in anchors/pins")
    ap.add_argument("--dir", help="directory that already holds the three files")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-pin", action="store_true",
                    help="skip the comparison against anchors/pins/uibc-release-<tag>.json")
    args = ap.parse_args(argv)
    if args.tag is None:
        args.tag = _newest_pinned_tag()

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

    # The token proves a digest was signed. It does not prove the page still serves
    # those bytes: this workflow rewrote the same tag three times on 2026-11-20, and
    # nothing would have said so. The pin turns that into a comparison.
    if not args.no_pin:
        live = _live_manifest(args.tag)
        if live is None:
            lines.append("pin          not checked: gh unavailable or the release unreadable")
        else:
            bad, plines, unsure = check_pin(
                args.tag, live, resolve=lambda name: _download_sha256(args.tag, name))
            if bad is None:
                lines.append("pin          no pin file for %s; nothing to compare" % args.tag)
            else:
                lines.extend(plines)
                if bad:
                    code = max(code, 1)
                elif unsure:
                    lines.append("pin          %d asset(s) could not be measured; this is not a pass"
                                 % unsure)
                    code = max(code, 3)
                else:
                    lines.append("pin          all %d assets match the pin recorded at freeze"
                                 % len(live))

    # The digest's own Bitcoin anchor, when the repository holds one. The page's
    # proof is a bare tree the official client refuses; this one is a standard
    # container, bound to the very bytes downloaded above.
    held_ots = os.path.join(ROOT, "anchors", "attestations", args.tag,
                            "CORPUS-DIGESTS.txt.ots")
    if os.path.isfile(held_ots):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import ots_container
        data_dir = str(args.dir) if args.dir else directory
        digest = ots_container.digest_of_file(os.path.join(data_dir, "CORPUS-DIGESTS.txt"))
        blob = open(held_ots, "rb").read()
        if not ots_container.binds(blob, digest):
            lines.append("bitcoin      the repository proof does not answer for the published "
                         "digest; refusing it")
            code = max(code, 1)
        else:
            rec = os.path.join(os.path.dirname(held_ots), "BITCOIN-ATTESTATION.json")
            block = None
            if os.path.isfile(rec):
                with open(rec, encoding="utf-8") as handle:
                    block = (json.load(handle) or {}).get("bitcoin") or {}
            # Bound is not the same as proved: until now the block height was
            # printed because a record said so. Walk the proof from the digest
            # through every operation to the merkle root and compare that root
            # with the one the record names, so the claim rests on arithmetic.
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            import ots_merkle
            walked = ots_merkle.verify(held_ots, os.path.join(data_dir, "CORPUS-DIGESTS.txt"),
                                       block)
            for line in walked["lines"]:
                lines.append("ots          " + line)
            if walked["exit"]:
                code = max(code, walked["exit"])

    if args.json:
        print(json.dumps({"tag": args.tag, "exit": code, "lines": lines}, indent=2))
    else:
        for line in lines:
            print(line)
    print({0: "ACCEPTABLE", 1: "NOT ACCEPTABLE", 3: "NOT MEASURED"}[code])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
