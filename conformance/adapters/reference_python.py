#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Minimum viable adapter: fold per RFC 9162, written from the text.

This exists so that "run our corpus" is one command for anyone who wants to see
the protocol work before writing their own. It imports nothing from uibc_core --
if it did, it would be testing our code against our code, which is what the
standalone checker already does.

stdin (inclusion, kind absent) : {"leaf_input_hex", "leaf_index", "tree_size",
                                   "inclusion_path", "root_true"}
stdin (consistency, kind="consistency") : {"old_size", "new_size", "old_root",
                                   "new_root", "consistency_path"}
stdout : {"reconstructed_root", "result"}  or
         {"reconstructed_old_root", "reconstructed_new_root", "result"}
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


def _split(n):
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def rebuild_consistency(m, n, old_root, path):
    """RFC 6962 2.1.2 recursion read backwards. None when the proof cannot be."""
    if m < 1 or n < m:
        return None
    if m == n:
        return (old_root, old_root) if not path else None

    def walk(a, b, pos, seeded):
        if a == b:
            if seeded:
                return old_root, old_root, pos
            if pos >= len(path):
                return None
            return path[pos], path[pos], pos + 1
        k = _split(b)
        if a <= k:
            res = walk(a, k, pos, seeded)
            if res is None or res[2] >= len(path):
                return None
            return res[0], NODE(res[1], path[res[2]]), res[2] + 1
        res = walk(a - k, b - k, pos, False)
        if res is None or res[2] >= len(path):
            return None
        return NODE(path[res[2]], res[0]), NODE(path[res[2]], res[1]), res[2] + 1

    res = walk(m, n, 0, True)
    if res is None or res[2] != len(path):
        return None
    return res[0], res[1]


def answer_consistency(req):
    old = bytes.fromhex(req["old_root"])
    new = bytes.fromhex(req["new_root"])
    path = [bytes.fromhex(h) for h in req["consistency_path"]]
    rec = rebuild_consistency(req["old_size"], req["new_size"], old, path)
    if rec is None:
        return {"reconstructed_old_root": "", "reconstructed_new_root": "",
                "result": "PROOF_DOES_NOT_VERIFY"}
    ro, rn = rec[0].hex(), rec[1].hex()
    ok = (rec[0] == old and rec[1] == new)
    return {"reconstructed_old_root": ro, "reconstructed_new_root": rn,
            "result": "VALID" if ok else "PROOF_DOES_NOT_VERIFY"}


def answer(req):
    if req.get("kind") == "consistency":
        return answer_consistency(req)
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
