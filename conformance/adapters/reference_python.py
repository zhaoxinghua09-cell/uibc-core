#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Minimum viable adapter: fold per RFC 9162, written from the text.

This exists so that "run our corpus" is one command for anyone who wants to see
the protocol work before writing their own. It imports nothing from uibc_core --
if it did, it would be testing our code against our code, which is what the
standalone checker already does.

stdin  : {"leaf_input_hex", "leaf_index", "tree_size", "inclusion_path", "root_true"}
stdout : {"reconstructed_root", "result"}
"""
import hashlib
import json
import sys

LEAF = lambda data: hashlib.sha256(b"\x00" + data).digest()
NODE = lambda left, right: hashlib.sha256(b"\x01" + left + right).digest()


def fold(leaf, index, size, path):
    """RFC 9162 inclusion verification. Returns None when no fold is defined."""
    if size <= 0 or index >= size:
        return None
    fn, sn, r = index, size - 1, leaf
    for p in path:
        if fn & 1 or fn == sn:
            r = NODE(p, r)
            while not fn & 1 and fn:
                fn >>= 1
                sn >>= 1
        else:
            r = NODE(r, p)
        fn >>= 1
        sn >>= 1
    return r


def answer(req):
    leaf = LEAF(bytes.fromhex(req["leaf_input_hex"]))
    path = [bytes.fromhex(h) for h in req["inclusion_path"]]
    got = fold(leaf, req["leaf_index"], req["tree_size"], path)
    if got is None:
        return {"reconstructed_root": "", "result": "NO_FOLD_DEFINED"}
    hexed = got.hex()
    if hexed == req["root_true"]:
        # A root match is the algorithm's own statement; how the size ambiguity is
        # classified is a separate question this adapter does not answer.
        return {"reconstructed_root": hexed, "result": "VALID"}
    return {"reconstructed_root": hexed, "result": "PROOF_DOES_NOT_VERIFY"}


def main():
    line = sys.stdin.readline()
    if not line.strip():
        print(json.dumps({"error": "no input"}))
        return 1
    req = json.loads(line)
    print(json.dumps(answer(req)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
