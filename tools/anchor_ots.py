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


def stamp(path, calendars=CALENDARS, out=None, submit=None):
    """Submit the digest, trying each calendar in turn.

    Measured 2026-11-20: `alice` and `finney` both answered 503 while `bob`
    answered normally. A single hard-coded calendar therefore turns one
    operator's outage into a claim that OpenTimestamps is unavailable,
    which is false. Every attempt is recorded, and the one that answered is
    named in the result, so an absent proof never reads as "nobody could
    have witnessed this".
    """
    digest = _digest(path)
    tried = []
    for calendar in calendars:
        try:
            if submit is None:
                from opentimestamps.calendar import RemoteCalendar
                ts = RemoteCalendar(calendar).submit(digest, timeout=30)
            else:
                ts = submit(calendar, digest)
        except Exception as exc:  # noqa: BLE001 - any calendar failure is data
            tried.append({"calendar": calendar, "error": "%s: %s" % (
                type(exc).__name__, str(exc)[:80])})
            continue
        # Imported only once something answered, so that "nobody answered" stays
        # reportable even where the library itself is missing.
        # The standard container, not a bare tree: measured 2026-11-20, a bare tree
        # is refused by the official client ("is not a timestamp file"), which made
        # the published proof readable only by this repository's own tool.
        from opentimestamps.core.serialize import BytesSerializationContext
        ctx = BytesSerializationContext()
        ts.serialize(ctx)
        blob = ctx.getbytes()
        # Wrap it ourselves, so the container format does not depend on which
        # attributes this version of the library happens to expose.
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ots_container
        blob = ots_container.bare_to_standard(blob, digest)
        out = out or (path + ".ots")
        with open(out, "wb") as f:
            f.write(blob)
        tried.append({"calendar": calendar, "ok": True})
        return {"out": out, "calendar": calendar, "digest_sha256": digest.hex(),
                "bytes": len(blob), "tried": tried}
    raise RuntimeError("no calendar accepted the digest: " + "; ".join(
        "%s (%s)" % (t["calendar"], t["error"]) for t in tried))


def inspect(proof_path, data_path=None):
    """Return a description of every attestation in the proof.

    When `data_path` is given, the proof must answer for *that* file. Until
    2026-11-20 it did not: the initial message was taken from the proof's own
    first 32 bytes, so a proof belonging to a different file walked happily and
    listed its attestations as if they were this file's.
    """
    from opentimestamps.core.serialize import BytesDeserializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

    with open(proof_path, "rb") as f:
        blob = f.read()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ots_container
    if data_path:
        digest = ots_container.digest_of_file(data_path)
        if ots_container.is_standard(blob):
            if not ots_container.binds(blob, digest):
                raise RuntimeError("the proof answers for another digest, not for %s"
                                   % os.path.basename(data_path))
        elif not ots_container.is_standard(blob):
            # A bare tree: it carries no digest, so it can only be attached to one,
            # and attaching it to the wrong file is indistinguishable. Refuse rather
            # than guess when the caller asked for a binding.
            raise RuntimeError("the proof has no standard header, so it cannot be "
                               "bound to %s; re-wrap it with --wrap"
                               % os.path.basename(data_path))
        ctx = BytesDeserializationContext(blob)
        ts = DetachedTimestampFile.deserialize(ctx).timestamp
    else:
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


def upgrade(proof_path, calendar=CALENDARS[0], timeout=30):
    """Ask the calendar whether the commitment has landed in a Bitcoin block.

    Returns {"upgraded": bool, "attestations": [...], "bytes": n}. The proof is
    rewritten only when a new attestation was actually obtained, so a failed
    upgrade never silently replaces a good pending proof with an empty one.
    """
    from opentimestamps.calendar import RemoteCalendar
    from opentimestamps.core.serialize import (BytesDeserializationContext,
                                               BytesSerializationContext)
    from opentimestamps.core.timestamp import Timestamp

    with open(proof_path, "rb") as f:
        blob = f.read()

    before = inspect(proof_path)
    ts = Timestamp.deserialize(BytesDeserializationContext(blob), blob[:32])
    cal = RemoteCalendar(calendar)

    # Walk to the deepest timestamp and ask for an upgrade at each node that
    # still has only a pending attestation.
    upgraded_any = False
    pending_nodes = []

    def walk(t):
        for att in t.attestations:
            if type(att).__name__ == "PendingAttestation":
                pending_nodes.append(t)
                break
        for _op, child in t.ops.items():
            walk(child)

    walk(ts)

    for node in pending_nodes:
        try:
            got = cal.get_timestamp(node.msg, timeout=timeout)
        except Exception:  # noqa: BLE001 - calendar down, unknown commitment, etc.
            continue
        if got is not None:
            node.merge(got)
            upgraded_any = True

    after = inspect(proof_path)  # re-read is meaningless before write; kept simple below
    if upgraded_any:
        ctx = BytesSerializationContext()
        ts.serialize(ctx)
        new_blob = ctx.getbytes()
        with open(proof_path, "wb") as f:
            f.write(new_blob)
    else:
        new_blob = blob

    kinds = [a["kind"] for a in inspect(proof_path)]
    return {"upgraded": upgraded_any,
            "bitcoin_block": kinds.count("BitcoinBlockHeaderAttestation"),
            "pending_calendar": kinds.count("PendingAttestation"),
            "bytes": len(new_blob),
            "before": [a["kind"] for a in before],
            "after": kinds}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", metavar="FILE")
    ap.add_argument("--verify", metavar="FILE")
    ap.add_argument("--upgrade", metavar="PROOF", help="upgrade an existing .ots proof")
    ap.add_argument("--proof")
    ap.add_argument("--calendar", default=None,
                    help="use this calendar only (default: all three, in order)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--wrap", metavar="BARE_PROOF",
                    help="wrap a bare tree in the standard container: needs --proof and --out")
    ap.add_argument("--out", metavar="FILE", help="where --wrap writes")
    args = ap.parse_args(argv)

    if args.wrap:
        # A bare tree is what the old writer produced. Wrapping changes the container,
        # not the evidence, and needs no calendar -- so it works offline.
        if not (args.proof or args.out):
            print("--wrap needs --data FILE and --out FILE")
            return 2
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ots_container
        blob = open(args.wrap, "rb").read()
        digest = ots_container.digest_of_file(args.proof)
        if not args.out:
            print("--wrap needs --out")
            return 2
        if ots_container.is_standard(blob):
            print("refused: this proof already carries a standard header")
            return 1
        wrapped = ots_container.bare_to_standard(blob, digest)
        open(args.out, "wb").write(wrapped)
        print("wrapped %d bytes -> %d bytes, bound to %s"
              % (len(blob), len(wrapped), os.path.basename(args.proof)))
        if not ots_container.binds(wrapped, digest):
            print("internal error: the wrapper did not produce a bound proof")
            return 3
        return 0

    if args.stamp:
        cal_list = (args.calendar,) if args.calendar else CALENDARS
        try:
            info = stamp(args.stamp, calendars=cal_list)
        except RuntimeError as exc:
            print(json.dumps({"status": "no_calendar_answered",
                              "reason": str(exc)[:400]}, indent=2))
            return 3
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print("status=pending_calendar (no Bitcoin block attestation yet)")
        return 0

    if args.upgrade:
        info = upgrade(args.upgrade, calendar=args.calendar or CALENDARS[0])
        print(json.dumps(info, ensure_ascii=False, indent=2))
        if info["bitcoin_block"]:
            print("status=bitcoin_attested (block header NOT cross-checked here)")
        else:
            print("status=still_pending_calendar (upgrade not available yet)")
        return 0

    if args.verify:
        if not args.proof:
            print("--proof is required with --verify")
            return 2
        atts = inspect(args.proof, args.verify)
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
