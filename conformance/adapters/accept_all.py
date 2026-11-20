#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Negative control: an adapter that refuses nothing.

It answers "VALID" to every vector without computing anything, and reports the
vector's own `root_true` as its "reconstructed root" -- i.e. it cheats in the most
obvious way a verifier can cheat.

Purpose: prove the harness can fail. On the fail-* vectors this must produce root
mismatches, and the harness must report them. If this adapter ever produces
`CONTROL-FAILED`, the harness is accepting anything and no receipt from it is
worth filing. This is the same lesson as the 2026-10-22 `lgd-ci-gate` fix: a check
that cannot fail proves nothing.
"""
import json
import sys


def main():
    line = sys.stdin.readline()
    if not line.strip():
        print(json.dumps({"error": "no input"}))
        return 1
    req = json.loads(line)
    print(json.dumps({
        "reconstructed_root": req.get("root_true", ""),
        "result": "VALID",
        "note": "accept-all control adapter; computes nothing on purpose",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
