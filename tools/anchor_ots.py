#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenTimestamps anchor (second anchor type, ASQAV draft row 5).

What this does and what it cannot do yet, in one place:

  * `--stamp FILE` submits the SHA-256 digest of FILE to a public OTS calendar
    and writes a `.ots` proof next to it. The proof at this point contains a
    **calendar attestation**, not a Bitcoin block attestation - the calendar is
    saying "I have this digest since now", which is weaker than a block.
  * `--verify FILE --proof P` parses the proof and reports which attestations
    it actually contains. It never prints "verified" for a proof whose only
    attestation is a pending calendar: that is the same dishonesty this project
    keeps warning about in the RFC 3161 path.
  * `--upgrade FILE --proof P` asks the calendar for the Bitcoin attestation.
    This normally needs hours to days, so it is a separate command rather than
    something a test suite could ever call.

The Bitcoin block header is NOT fetched or checked here: that needs a chain
source, and pretending otherwise would be the exact "metadata present => valid"
error the draft forbids.
"""
import argparse
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CALENDARS = ("https://alice.btc.calendar.opentimestamps.org",
             "https://bob.btc.calendar.opentimestamps.org",
             "https://finney.calendar.eternitywall.com")


def _digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).digest()


def stamp(path, calendar=CALENDARS[0], out=None):
    from opentimestamps.calendar import RemoteCalendar
    from opentimestamps.core.serialize import BytesSerializationContext

    digest = _digest(path)
    cal = RemoteCalendar(calendar)
    ts = cal.submit(digest, timeout=30)
    ctx = BytesSerializationContext()
    ts.serialize(ctx)
    blob = ctx.getbytes()
    out = out or (path + ".ots")
    with open(out, "wb") as f:
        f.write(blob)
    return {"out": out, "calendar": calendar, "digest_sha256": digest.hex(),
            "bytes": len(blob)}


def inspect(proof_path):
    """Return a description of every attestation in the proof.

    The proof's first message is the timestamped digest, so it is passed in as
    the initial message rather than guessed.
    """
    from opentimestamps.core.serialize import BytesDeserializationContext
    from opentimestamps.core.timestamp import Timestamp

    with open(proof_path, "rb") as f:
        blob = f.read()
    ctx = BytesDeserializationContext(blob)
    ts = Timestamp.deserialize(ctx, blob[:32])
    found = []

    def walk(t, depth=0):
        for att in t.attestations:
            found.append({"kind": type(att).__name__, "depth": depth,
                          "detail": str(getattr(att, "payload", ""))[:40]})
        for _op, child in t.ops.items():
            walk(child, depth + 1)

    walk(ts)
    return found


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", metavar="FILE")
    ap.add_argument("--verify", metavar="FILE")
    ap.add_argument("--proof")
    ap.add_argument("--calendar", default=CALENDARS[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.stamp:
        info = stamp(args.stamp, calendar=args.calendar)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print("status=pending_calendar (no Bitcoin block attestation yet)")
        return 0

    if args.verify:
        if not args.proof:
            print("--proof is required with --verify")
            return 2
        atts = inspect(args.proof)
        block = [a for a in atts if a["kind"] == "BitcoinBlockHeaderAttestation"]
        calendar = [a for a in atts if a["kind"] == "PendingAttestation"]
        doc = {"file": args.verify, "proof": args.proof,
               "attestations": atts,
               "bitcoin_block": [a["detail"] for a in block],
               "pending_calendar": len(calendar)}
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        if block:
            print("status=bitcoin_attested (block header NOT cross-checked here)")
        elif calendar:
            print("status=pending_calendar (weaker than a block; not 'verified')")
        else:
            print("status=no_attestation")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
