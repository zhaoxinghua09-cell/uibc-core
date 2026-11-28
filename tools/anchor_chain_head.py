#!/usr/bin/env python3
"""Anchor a package's Evidence Root to OpenTimestamps calendars.

Why this exists
---------------
A hash chain catches tampering and reordering. It cannot catch truncation:
delete the tail and the remaining chain still verifies. The fix is to commit
the root somewhere the operator cannot rewrite. Every serious competitor
already does this (AAC ships a SCITT anchor client and a digest endpoint;
the AER-1 SDK ships multi-relay Nostr plus OpenTimestamps). uibc-core did
not. This closes that gap with the lowest-dependency backend available.

Why OpenTimestamps rather than Nostr
------------------------------------
The OTS calendar protocol is plain HTTP: `POST /digests` with a 32-byte
digest, and you get back an `.ots` proof. That is the entire wire format,
expressible with urllib. Nostr needs a secp256k1 Schnorr signature, which
means either a compiled dependency or hand-rolled elliptic-curve arithmetic -
the wrong trade for a tool reviewers are expected to run on a laptop.

What a calendar attestation actually proves
-------------------------------------------
Not "this existed at time T", not yet. A calendar accepts the digest and
returns a *pending* attestation; it becomes a Bitcoin commitment only after
`ots upgrade` succeeds, typically about an hour later, and only then does
`ots verify` prove existence at a block height. This tool records the pending
proof and says so. Claiming an anchored timestamp before the upgrade would
be a lie, so the report carries `state: "pending"`.

Why the proof is NOT stored inside the package
----------------------------------------------
Recording an anchor as evidence inside the package changes the package's
content, which changes its Evidence Root - so the root you anchored is no
longer the root the package has. The proof belongs *beside* the package,
and the anchoring record names which root it commits to. That mismatch is
silent and fatal if you get it wrong, so `anchor_chain_head` refuses to
write into the package directory.

Usage
-----
    python3 tools/anchor_chain_head.py --package fixtures/clean.uibc
    python3 tools/anchor_chain_head.py --package fixtures/clean.uibc \\
        --submit --out /tmp/anchors

Dry-run (the default) computes the digest and prints exactly what would be
posted, without touching the network. `--submit` posts it to the calendars.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

CALENDARS = [
    "https://alice.btc.calendar.opentimestamps.org",
    "https://bob.btc.calendar.opentimestamps.org",
    "https://finney.calendar.eternitywall.com",
]

# OpenTimestamps v1 serialized proofs begin with this 16-byte header magic.
# Verified against the reference implementation rather than guessed:
# python-opentimestamps, opentimestamps/core/timestamp.py:276,
# DetachedTimestampFile.HEADER_MAGIC - byte for byte.
OTS_MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"

USER_AGENT = "uibc-core-anchor/0.3.3"


def package_root(package):
    """Read the Evidence Root out of the package manifest. No recomputation:
    the manifest is the package's own claim, and `verify` already checks it."""
    path = os.path.join(package, "manifest.json")
    if not os.path.isfile(path):
        raise FileNotFoundError("manifest.json not found in %s" % package)
    with open(path, encoding="utf-8") as stream:
        manifest = json.load(stream)
    root = manifest.get("evidence_root")
    if not isinstance(root, str) or len(root) != 64:
        raise ValueError("manifest has no 64-hex evidence_root: %r" % (root,))
    try:
        bytes.fromhex(root)
    except ValueError:
        raise ValueError("evidence_root is not hex: %r" % (root,))
    return root.lower()


def digest_bytes(root):
    """The payload posted to a calendar. The root already *is* a SHA-256
    value, so it is sent as-is rather than hashed again - hashing twice
    would still work, but it would obscure what is being committed to."""
    return bytes.fromhex(root)


def submit(calendar, digest, timeout=20):
    """POST one digest to one calendar. Returns (ok, payload_or_error)."""
    url = calendar.rstrip("/") + "/digests"
    request = urllib.request.Request(
        url, data=digest, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return True, body
    except urllib.error.HTTPError as exc:
        return False, "HTTP %d: %s" % (exc.code, exc.read()[:120].decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001 - one calendar must not kill the run
        return False, "%s: %s" % (type(exc).__name__, str(exc)[:120])


def anchor(package, calendars=CALENDARS, out_dir=None, do_submit=False,
           timeout=20):
    """Anchor the package root. Returns a report dict (never raises for
    per-calendar failures; a failed calendar is reported, not fatal)."""
    root = package_root(package)
    payload = digest_bytes(root)
    report = {
        "package": os.path.abspath(package),
        "evidence_root": root,
        "digest_bytes": len(payload),
        "state": "pending" if do_submit else "dry-run",
        "calendars": [],
        "proofs": [],
    }
    if out_dir and os.path.abspath(out_dir).startswith(os.path.abspath(package)):
        raise ValueError("refusing to write proofs inside the package: "
                         "adding files changes the Evidence Root being anchored")

    for calendar in calendars:
        entry = {"calendar": calendar}
        if not do_submit:
            entry.update({"would_post": "/digests", "body_bytes": len(payload),
                          "status": "not submitted (dry-run)"})
            report["calendars"].append(entry)
            continue
        started = time.time()
        ok, result = submit(calendar, payload, timeout=timeout)
        elapsed = round(time.time() - started, 2)
        if not ok:
            entry.update({"status": "failed", "error": result, "seconds": elapsed})
            report["calendars"].append(entry)
            continue
        proof = result
        magic_ok = proof[:len(OTS_MAGIC)] == OTS_MAGIC
        entry.update({"status": "submitted", "proof_bytes": len(proof),
                      "ots_magic": magic_ok, "seconds": elapsed})
        written = None
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            host = calendar.split("//", 1)[1].split("/")[0]
            name = "%s.%s.ots" % (root[:16], host.split(".")[0])
            written = os.path.join(out_dir, name)
            with open(written, "wb") as stream:
                stream.write(proof)
        entry["proof_path"] = written
        report["calendars"].append(entry)
        report["proofs"].append({"calendar": calendar, "path": written,
                                 "bytes": len(proof), "ots_magic": magic_ok})

    if do_submit and out_dir:
        record = os.path.join(out_dir, "anchor-record.json")
        with open(record, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        report["record_path"] = record

    if do_submit:
        failures = [c for c in report["calendars"] if c["status"] == "failed"]
        report["ok"] = not failures
    else:
        report["ok"] = True
    report["next"] = ("run 'ots upgrade <proof>' after ~1h, then 'ots verify <proof>' "
                      "to turn a pending calendar attestation into a Bitcoin commitment")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--package", required=True, help="uibc package directory")
    parser.add_argument("--out", default=None, help="where to write .ots proofs")
    parser.add_argument("--submit", action="store_true",
                        help="actually POST to the calendars (default: dry-run)")
    parser.add_argument("--calendar", action="append", default=None,
                        help="override calendar URL (repeatable)")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args(argv)

    calendars = args.calendar or CALENDARS
    if args.submit and not args.out:
        parser.error("--submit requires --out (proofs must be kept somewhere)")
    try:
        report = anchor(args.package, calendars=calendars, out_dir=args.out,
                        do_submit=args.submit)
    except (FileNotFoundError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("package   : %s" % report["package"])
        print("root      : %s" % report["evidence_root"])
        print("state     : %s" % report["state"])
        for calendar in report["calendars"]:
            host = calendar["calendar"].split("//", 1)[1].split("/")[0]
            print("  %-42s %s" % (host, calendar.get("status")))
            if calendar.get("error"):
                print("    %s" % calendar["error"])
            if calendar.get("proof_path"):
                print("    -> %s (%d bytes, ots_magic=%s)"
                      % (calendar["proof_path"], calendar["proof_bytes"],
                         calendar["ots_magic"]))
        if report["state"] == "dry-run":
            print("\nNothing was posted. Re-run with --submit --out <dir> to anchor.")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
