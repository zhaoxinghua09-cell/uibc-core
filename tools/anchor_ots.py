#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenTimestamps anchor (second anchor type, ASQAV draft row 5).

What this does and what it cannot do yet, in one place:

  * `--stamp FILE` submits the SHA-256 digest of FILE to one or more public OTS
    calendars and writes a **detached timestamp file** (the standard `.ots`
    container: magic header, version, digest, timestamp tree). The proof at
    this point contains a **calendar attestation**, not a Bitcoin block
    attestation - the calendar is saying "I have this digest since now",
    which is weaker than a block.
  * `--verify FILE --proof P` parses the container, reports which attestations
    it actually contains, and checks that the digest the proof commits to **is**
    the digest of FILE. It never prints "verified" for a proof whose only
    attestation is a pending calendar: that is the same dishonesty this project
    keeps warning about in the RFC 3161 path.
  * `--upgrade PROOF` asks each calendar named in the proof for the Bitcoin
    attestation. This normally needs hours to days, so it is a separate command
    rather than something a test suite could ever call.
  * `--query FILE --proof P` asks the calendars whether a Bitcoin attestation is
    available yet for that digest, without writing anything.

The Bitcoin block header is NOT fetched or checked here: that needs a chain
source, and pretending otherwise would be the exact "metadata present => valid"
error the draft forbids.

History this file has to keep telling: the proof shipped on 2026-11-17
(`tests/fixtures/anchor/ots_head.ots`) was a **bare timestamp tree** - no magic
header - so the official client refused it ("not a timestamp file") while our
own reader, which fed the proof's own first 32 bytes back in as the digest,
happily listed a pending attestation for a digest nobody had asked about. That
is a proof that cannot be checked by anyone else. `--verify` now compares the
committed digest against the file, and the fixture was re-stamped as a real
container on 2026-11-25 against the same head digest (`4ad23d91…`).
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


def _load(proof_path):
    """Read a detached timestamp file; raises if it is not one.

    `StreamDeserializationContext` is what the official client uses, so a file
    that this function accepts is a file `ots info` also accepts.
    """
    from opentimestamps.core.serialize import StreamDeserializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile

    with open(proof_path, "rb") as f:
        return DetachedTimestampFile.deserialize(StreamDeserializationContext(f))


def stamp(path, calendars=CALENDARS, out=None):
    from opentimestamps.calendar import RemoteCalendar
    from opentimestamps.core.op import OpSHA256
    from opentimestamps.core.serialize import BytesSerializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

    digest = _digest(path)
    dtf = DetachedTimestampFile(OpSHA256(), Timestamp(digest))
    accepted, failed = [], []
    for url in calendars:
        try:
            cal = RemoteCalendar(url)
            got = cal.submit(digest, timeout=30)
        except Exception as e:  # noqa: BLE001 - a dead calendar must not sink the others
            failed.append({"calendar": url, "error": type(e).__name__ + ": " + str(e)[:120]})
            continue
        dtf.timestamp.merge(got)
        accepted.append(url)

    if not accepted:
        raise RuntimeError("no calendar accepted the digest: " +
                           json.dumps(failed, ensure_ascii=False))

    ctx = BytesSerializationContext()
    dtf.serialize(ctx)
    blob = ctx.getbytes()
    out = out or (path + ".ots")
    with open(out, "wb") as f:
        f.write(blob)
    return {"out": out, "digest_sha256": digest.hex(), "bytes": len(blob),
            "calendars_accepted": accepted, "calendars_failed": failed}


def inspect(proof_path):
    """Return the digest the proof commits to plus every attestation in it."""
    dtf = _load(proof_path)
    found = []

    def walk(t, depth=0):
        for att in t.attestations:
            kind = type(att).__name__
            detail = str(getattr(att, "payload", ""))[:60]
            if kind == "BitcoinBlockHeaderAttestation":
                # the height is the whole point of a block attestation; the
                # generic payload field is empty, so report the number instead
                detail = str(getattr(att, "height", ""))
            found.append({"kind": kind, "depth": depth, "detail": detail})
        for _op, child in t.ops.items():
            walk(child, depth + 1)

    walk(dtf.timestamp)
    return dtf.file_digest.hex(), found


def upgrade(proof_path, timeout=30):
    """Ask each calendar the proof names whether the commitment is in a block.

    Returns {"upgraded": bool, ...}. The proof is rewritten only when a new
    attestation was actually obtained, so a failed upgrade never silently
    replaces a good pending proof with an empty one.
    """
    from opentimestamps.calendar import RemoteCalendar
    from opentimestamps.core.serialize import BytesSerializationContext

    dtf = _load(proof_path)
    before = inspect(proof_path)[1]
    pending_nodes, calendars = [], set()

    def walk(t):
        for att in t.attestations:
            if type(att).__name__ == "PendingAttestation":
                pending_nodes.append(t)
                uri = getattr(att, "uri", None)
                if uri:
                    calendars.add(uri.rstrip("/"))
                break
        for _op, child in t.ops.items():
            walk(child)

    walk(dtf.timestamp)
    targets = sorted(calendars) or list(CALENDARS)

    upgraded_any, tried = False, []
    for node in pending_nodes:
        for url in targets:
            try:
                got = RemoteCalendar(url).get_timestamp(node.msg, timeout=timeout)
            except Exception as e:  # noqa: BLE001 - calendar down, unknown commitment
                tried.append({"calendar": url, "error": type(e).__name__})
                continue
            if got is not None:
                node.merge(got)
                upgraded_any = True
                tried.append({"calendar": url, "result": "merged"})

    if upgraded_any:
        ctx = BytesSerializationContext()
        dtf.serialize(ctx)
        new_blob = ctx.getbytes()
        with open(proof_path, "wb") as f:
            f.write(new_blob)
    else:
        with open(proof_path, "rb") as f:
            new_blob = f.read()

    kinds = [a["kind"] for a in inspect(proof_path)[1]]
    return {"upgraded": upgraded_any,
            "bitcoin_block": kinds.count("BitcoinBlockHeaderAttestation"),
            "pending_calendar": kinds.count("PendingAttestation"),
            "bytes": len(new_blob),
            "before": [a["kind"] for a in before],
            "after": kinds,
            "calendars_asked": tried}


def verify(file_path, proof_path):
    """Report what the proof says AND whether it is about the file at all."""
    want = _digest(file_path)
    try:
        got_hex, atts = inspect(proof_path)
    except Exception as e:  # noqa: BLE001 - mostly BadMagicError: not a .ots container
        return {"file": file_path, "proof": proof_path,
                "file_digest_sha256": want.hex(),
                "readable": False,
                "error": type(e).__name__,
                "detail": str(e)[:160],
                "attestations": [],
                "bitcoin_block": [],
                "pending_calendar": 0,
                "bound": False}
    block = [a for a in atts if a["kind"] == "BitcoinBlockHeaderAttestation"]
    calendar = [a for a in atts if a["kind"] == "PendingAttestation"]
    return {"file": file_path, "proof": proof_path,
            "file_digest_sha256": want.hex(),
            "proof_digest_sha256": got_hex,
            "readable": True,
            "bound": want.hex() == got_hex,
            "attestations": atts,
            "bitcoin_block": [a["detail"] for a in block],
            "pending_calendar": len(calendar)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", metavar="FILE")
    ap.add_argument("--out", metavar="PROOF", help="where to write the proof")
    ap.add_argument("--verify", metavar="FILE")
    ap.add_argument("--upgrade", metavar="PROOF", help="upgrade an existing .ots proof")
    ap.add_argument("--query", metavar="FILE", help="ask calendars, write nothing")
    ap.add_argument("--proof")
    ap.add_argument("--calendar", action="append", default=None,
                    help="calendar URL; repeatable; default: all three public ones")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    calendars = args.calendar or list(CALENDARS)

    if args.stamp:
        info = stamp(args.stamp, calendars=calendars, out=args.out)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print("status=pending_calendar (no Bitcoin block attestation yet; "
              "the calendar only says it had the digest since now)")
        return 0

    if args.query:
        if not args.proof:
            print("--proof is required with --query")
            return 2
        doc = verify(args.query, args.proof)
        doc.pop("attestations", None)
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        print("status=bitcoin_attested (block header not cross-checked by this command; tools/ots_block_crosscheck.py checks it against two chain sources)"
              if doc["bitcoin_block"] else "status=still_pending_calendar")
        return 0

    if args.upgrade:
        info = upgrade(args.upgrade)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        if info["bitcoin_block"]:
            print("status=bitcoin_attested (block header not cross-checked by this command; tools/ots_block_crosscheck.py checks it against two chain sources)")
        else:
            print("status=still_pending_calendar (upgrade not available yet)")
        return 0

    if args.verify:
        if not args.proof:
            print("--proof is required with --verify")
            return 2
        doc = verify(args.verify, args.proof)
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        if not doc["readable"]:
            print("status=not_a_timestamp_file (the official client refuses this file "
                  "too; nothing in it can be checked)")
            return 4
        if not doc["bound"]:
            print("status=not_bound (the proof commits to a different digest; "
                  "nothing it says applies to this file)")
            return 3
        if doc["bitcoin_block"]:
            print("status=bitcoin_attested (block header not cross-checked by this command; tools/ots_block_crosscheck.py checks it against two chain sources)")
        elif doc["pending_calendar"]:
            print("status=pending_calendar (weaker than a block; not 'verified')")
        else:
            print("status=no_attestation")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
