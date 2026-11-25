#!/usr/bin/env python
"""One command that turns the three probes into a gate.

Each probe answers one question and prints a table. This runs all three, keeps
only the claims a stranger can check, and exits non-zero if any of them broke:

    python tools/mutation_gate.py            # table + GATE OK / GATE FAIL
    python tools/mutation_gate.py --json     # machine output

The gate is deliberately *narrow*: it does not restate every number the probes
print, only the properties that make the numbers mean something - nothing was
swallowed silently, nothing blind outside the reserved bits, no address reuse.
Numbers move as the sample grows; those properties do not.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Ledger:
    def __init__(self):
        self.rows = []

    def check(self, layer, name, ok, detail=""):
        self.rows.append({"layer": layer, "check": name, "ok": bool(ok),
                          "detail": str(detail)[:120]})

    def failed(self):
        return [row for row in self.rows if not row["ok"]]


def document_layer(ledger):
    shapes = _load("mutate_document_shapes")
    rows = shapes.probe()
    summary = shapes.summarise(rows)
    ledger.check("document", "every forbidden shape is refused",
                 summary["caught"] == summary["must_reject"] and summary["must_reject"] >= 20,
                 "%d/%d" % (summary["caught"], summary["must_reject"]))
    ledger.check("document", "nothing forbidden is accepted silently",
                 not summary["silent"], summary["silent"])
    ledger.check("document", "no refusal happens at the wrong layer",
                 not summary["wrong_error"], summary["wrong_error"])
    by_name = {row["mutant"]: row for row in rows}
    cited = all(by_name.get(name, {}).get("outcome") == "rejected"
                and item in by_name.get(name, {}).get("reason", "")
                and "必填" in by_name.get(name, {}).get("reason", "")
                for name, item in (("created deleted", "9.created"),
                                   ("updated deleted", "10.updated")))
    ledger.check("document", "missing created/updated is refused with §4.2.1 item",
                 cited, by_name.get("created deleted", {}).get("reason", "")[:80])
    ledger.check("document", "an unknown top-level field is tolerated",
                 bool(summary["tolerated"])
                 and all(item["outcome"] == "silent" for item in summary["tolerated"]))
    relabel = shapes.type_relabel_is_caught_by_verification()
    ledger.check("document", "relabelled key type is caught by verification",
                 relabel.get("honest_doc_verifies") is True
                 and relabel.get("relabelled_verifies") is False,
                 relabel.get("relabelled_reason", "")[:80])


def binary_layer(ledger):
    binary = _load("mutate_bid_binary")
    result = binary.probe(binary.sample_message())
    total = result["total"]
    ledger.check("binary", "every bit is classified exactly once",
                 result["rejected"] + result["changed"] + len(result["blind"]) == total,
                 "rejected=%d changed=%d blind=%d total=%d"
                 % (result["rejected"], result["changed"], len(result["blind"]), total))
    from uibc_core.bid_binary import _FLAG_BITS, _OPCODE_SHIFT
    used = {bit for _n, bit in _FLAG_BITS} | set(range(_OPCODE_SHIFT, _OPCODE_SHIFT + 4))
    unnamed = {8 + (15 - bit) for bit in range(16) if bit not in used}
    expected = unnamed | set(range(24, 32))
    ledger.check("binary", "the blind set is exactly the reserved header bits",
                 set(result["blind"]) == expected,
                 "blind=%d expected=%d" % (len(result["blind"]), len(expected)))
    ledger.check("binary", "no body bit is blind",
                 [b for b in result["blind"] if b // 8 >= 16] == [])

    from uibc_core import bid_binary as BB
    try:
        BB.decode_document([BB.Unit(0x2100, BB.build_unit(0x2111, b"did:bid:efX#key-1"))])
        refused, why = False, "decoded without complaint"
    except ValueError as exc:
        refused, why = True, str(exc)[:100]
    ledger.check("binary", "a leaf in the wrong container is refused", refused, why)


def address_layer(ledger):
    address = _load("probe_address_binding")
    result = address.probe()
    ledger.check("address", "the fixture address re-derives from its key",
                 result["sample"]["reproduced"] is True, result["sample"]["address"])
    key_side = result["key_to_address"]
    ledger.check("address", "flipping a key bit always moves the address",
                 key_side.get("collisions_with_base") == 0
                 and (key_side.get("char_distance_min") or 0) >= 20,
                 "flips=%s collisions=%s distance=%s..%s"
                 % (key_side.get("bits"), key_side.get("collisions_with_base"),
                    key_side.get("char_distance_min"), key_side.get("char_distance_max")))
    side = result["address_to_key"]
    ledger.check("address", "no single-character substitution is accepted",
                 side.get("accepted") == [] and (side.get("tried") or 0) > 1000,
                 "tried=%s accepted=%s" % (side.get("tried"), len(side.get("accepted") or [])))
    ledger.check("address", "a shorter or longer address never matches",
                 result["length"] and all(v is False for v in result["length"].values()),
                 result["length"])


def run():
    ledger = Ledger()
    document_layer(ledger)
    binary_layer(ledger)
    address_layer(ledger)
    return ledger


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    ledger = run()
    failed = ledger.failed()
    if args.json:
        print(json.dumps({"ok": not failed, "checks": ledger.rows,
                          "failed": [row["check"] for row in failed]},
                         ensure_ascii=False, indent=1))
        return 0 if not failed else 1
    width = max(len(row["check"]) for row in ledger.rows)
    layer_of = {"document": "§4.2.1 文档", "binary": "RFC-011 报文", "address": "did:bid 地址"}
    current = None
    for row in ledger.rows:
        if row["layer"] != current:
            current = row["layer"]
            print("\n%s:" % layer_of[current])
        print("  %-6s %-*s %s" % ("OK" if row["ok"] else "FAIL", width, row["check"],
                                 row["detail"]))
    print("\n%d checks, %d failed" % (len(ledger.rows), len(failed)))
    print("GATE OK" if not failed else "GATE FAIL")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
