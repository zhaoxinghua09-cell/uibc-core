#!/usr/bin/env python
"""Runnable demo: build an RFC-011 message, then take it apart again.

Every claim this module makes is executed here, in order, and each one prints a
line starting with "OK" or "HARD-FAIL". Exit code 0 means all of them held.

    python tools/demo_bid_binary.py            # default document
    python tools/demo_bid_binary.py --flip     # also show what flipping the flag order does

No network, no fixtures, no server: the point is that a stranger can run one
command and watch the encoder and decoder agree or disagree.
"""
from __future__ import annotations

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import bid_binary as BB


def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


FAILS = []


def check(label, condition, detail=""):
    verdict = "OK" if condition else "HARD-FAIL"
    if not condition:
        FAILS.append(label)
    print("%-10s %-46s %s" % (verdict, label, detail))
    return condition


def hexdump(data, width=16):
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        print("  %04x  %s" % (off, " ".join("%02x" % b for b in chunk)))


def document():
    """A DID document shaped as the RFC-011 unit IDs expect (§5.2.1.1.2)."""
    return {
        "version": "1.0.0",
        "id": "did:bid:ef38VPR182Y4uTkq32fykXjbKBPdQZutH",
        "created": "2021-06-24T09:10:09Z",
        "publicKey": {"id": "did:bid:ef38VPR#key-1", "type": "Ed25519",
                      "controller": "did:bid:ef38VPR",
                      "publicKeyHex": "b9" + "06" * 32},
        "authentication": ["did:bid:ef38VPR#key-1"],
        "service": {"id": "did:bid:ef38VPR#svc", "type": "DIDResolve",
                    "serviceEndpoint": "https://example.invalid/bid"},
        "extension": {"ttl": 86400, "type": 105},
    }


def main():
    _utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--flip", action="store_true", help="also demonstrate the flip")
    ap.add_argument("--transaction-id", type=int, default=0x01020304)
    args = ap.parse_args()

    widths = {"int": 2, "long": 4}
    doc = document()

    print("1) 文档 -> 单元树 -> 字节")
    units = BB.encode_document(doc, integer_widths=widths)
    print("   units=%d  ids=%s" % (len(units), [("0x%04x" % u.id) for u in units]))
    body = BB.encode_units(units)
    message = BB.encode_message(units, args.transaction_id)
    check("body encodes to bytes", len(body) > 0, "%d bytes" % len(body))
    print("   message (%d bytes):" % len(message))
    hexdump(message)

    print("\n2) 字节 -> 文档（同一批字节，反过来读）")
    header, back = BB.decode_message(message, integer_widths=widths)
    print("   version=%d headerLength=%dB flags=%s opcode=%d(%s) rcode=%d(%s)"
          % (header.version, header.header_length, header.flags, header.opcode,
             header.opcode_name, header.reply_code, header.reply_name))
    print("   id=%s ttl=%s port=%s"
          % (back.fields.get("id"), back.integers.get("extension.ttl"),
             back.integers.get("service.port")))
    check("decoded id matches the input", back.fields.get("id") == doc["id"])
    check("no field was deferred", not back.deferred, "deferred=%r" % (back.deferred,))
    check("no unit was unknown", not back.unknown, "unknown=%d" % len(back.unknown))

    print("\n3) 单元层逐字节往返（含故意倒序）")
    shuffled = [BB.Unit(0x2102, b"b"), BB.Unit(0x2101, b"a")]
    raw = BB.encode_units(shuffled)
    check("unit roundtrip keeps the bytes", BB.parse_units(raw) == shuffled, raw.hex())
    check("re-encoding the same units is identical",
          BB.encode_units(BB.parse_units(raw)) == raw)

    print("\n4) 推断是参数：翻转 flag 位序，同一串字节读出不同结果")
    flag_msg = BB.encode_message([], 7, flags={"qr": 1})
    msb = BB.parse_header(flag_msg, flag_bit_order="msb").flags
    lsb = BB.parse_header(flag_msg, flag_bit_order="lsb").flags
    print("   msb=%r" % (msb,))
    print("   lsb=%r" % (lsb,))
    check("msb reads qr=1", msb.get("qr") == 1)
    check("lsb reads qr=0", lsb.get("qr") == 0)
    if args.flip:
        print("   (this is the whole point: the RFC numbers no bit, so both readings are legal)")

    print("\n5) AC 号有两套编号：编码选一套，解码两套都收")
    a = BB.encode_document({"extension": {"acsns": {"acsn": "x", "acsnAddress": "y"}}},
                           acsns_spelling="3610")
    b = BB.encode_document({"extension": {"acsns": {"acsn": "x", "acsnAddress": "y"}}},
                           acsns_spelling="3601")
    check("the two spellings are different bytes", a != b,
          "3610=%s 3601=%s" % (a[0].id == 0x3610, b[0].id == 0x3601))
    check("both decode to the same document",
          BB.decode_document(a).fields == BB.decode_document(b).fields)

    print("\n6) 宽度是硬校验：长度不符就 raise，不读成错数")
    raised = None
    try:
        BB.decode_document([BB.Unit(0x3000, BB.build_unit(0x3200, b"\x00\x00\x00\x05"))],
                           integer_widths={"long": 8})
    except ValueError as exc:
        raised = str(exc)
    check("wrong width raises", bool(raised), (raised or "no raise")[:70])

    print("\n6b) 字段必须坐在它该在的容器里：把 publicKey 改名成文档包装层会被拒")
    try:
        BB.decode_document([BB.Unit(0x2100, BB.build_unit(0x2111, b"did:bid:efX#key-1"))])
        moved = None
    except ValueError as exc:
        moved = str(exc)
    check("a leaf in the wrong container raises", bool(moved), (moved or "no raise")[:70])
    lenient = BB.decode_document([BB.Unit(0x2100, BB.build_unit(0x2111, b"did:bid:efX#key-1"))],
                                 strict_placement=False)
    check("lenient mode records it instead of raising", "publicKey.id" in lenient.misplaced,
          lenient.misplaced.get("publicKey.id", "")[:70])

    print("\n7) 敌意输入：500 组随机字节，只允许 ValueError")
    rng = random.Random(2026)
    other = []
    for _ in range(500):
        data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 48)))
        try:
            BB.decode_message(data)
        except ValueError:
            pass
        except Exception as exc:          # noqa: BLE001 - the point is the type
            other.append(type(exc).__name__)
    check("random bytes only fail as ValueError", not other, "other=%r" % (sorted(set(other))[:4],))

    print("\n6c) 逐位翻转：每翻一位，结构的反应只有三种")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import mutate_bid_binary as MUT
    res = MUT.probe(MUT.sample_message())
    check("every bit is classified once",
          res["rejected"] + res["changed"] + len(res["blind"]) == res["total"],
          "%d bits" % res["total"])
    check("the dead bits are only the reserved ones",
          set(res["blind_fields"]) <= {"flag", "unUsed"},
          "blind=%d in bytes 2/3" % len(res["blind"]))
    print("   rejected=%d changed=%d blind=%d (%.1f%%)"
          % (res["rejected"], res["changed"], len(res["blind"]),
             100.0 * len(res["blind"]) / res["total"]))

    print("\n8) 假设登记表（每条都有缺口与处置，不是散文）")
    for name, item in BB.ASSUMPTIONS.items():
        print("   %-22s [%s] %s" % (name, item["status"], item["choice"]))

    print("\n%s" % ("ALL OK" if not FAILS else "FAILED: %s" % ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
