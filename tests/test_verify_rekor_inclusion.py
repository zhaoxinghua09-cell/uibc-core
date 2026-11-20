# SPDX-License-Identifier: Apache-2.0
"""Tests for tools/verify_rekor_inclusion.py on a synthetic entry.

No real log entry is committed: Rekor's own entry body is third-party content and
its size changes as the log grows. The fixture reproduces the two shapes that
made the portal's "inclusion proof does not verify" claim wrong:

  * the leaf is SHA-256(0x00 ‖ body bytes), not SHA-256(0x00 ‖ SHA-256(body));
  * the proof folds against the proof's own logIndex, not the entry's.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "verify_rekor_inclusion.py")


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("verify_rekor_inclusion", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def node(l, r):
    return hashlib.sha256(b"\x01" + l + r).digest()


def audit_path(leaves, index):
    """RFC 6962 audit path for a leaf, ascending, 0-based index."""
    path, level, idx, n = [], 0, index, len(leaves)
    cur = [leaf for leaf in leaves]
    while n > 1:
        if idx % 2 == 1:
            path.append(cur[idx - 1])
        elif idx + 1 < n:
            path.append(cur[idx + 1])
        if n % 2 == 1:
            cur = [node(cur[i], cur[i + 1]) for i in range(0, n - 1, 2)] + [cur[n - 1]]
        else:
            cur = [node(cur[i], cur[i + 1]) for i in range(0, n, 2)]
        idx //= 2
        n = (n + 1) // 2
        level += 1
    # trim siblings that the fold above never reads for odd sizes
    return [p for p in path if p is not None]


def make_entry(bodies, index, entry_index=None, leaf_mode="body"):
    leaves = [hashlib.sha256(b"\x00" + b).digest() for b in bodies]
    if leaf_mode == "double":
        leaves = [hashlib.sha256(b"\x00" + hashlib.sha256(b).digest()).digest() for b in bodies]
    # tree root by explicit fold of the full set
    def root_of(ls):
        if len(ls) == 1:
            return ls[0]
        k = 1
        while k * 2 < len(ls):
            k *= 2
        return node(root_of(ls[:k]), root_of(ls[k:]))
    r = root_of(leaves)
    # Audit path by iterative folding: at each level the sibling is cur[i ^ 1],
    # except for the last leaf of an odd-width level, which has no sibling there
    # and rises alone (RFC 6962's "no duplication of the last node" rule).
    path, cur, i = [], list(leaves), index
    while len(cur) > 1:
        if len(cur) % 2 == 0:
            path.append(cur[i ^ 1])
            cur = [node(cur[j], cur[j + 1]) for j in range(0, len(cur), 2)]
        else:
            if i != len(cur) - 1:
                path.append(cur[i ^ 1])
            cur = [node(cur[j], cur[j + 1]) for j in range(0, len(cur) - 1, 2)] + [cur[-1]]
            if i == len(leaves) - 1 and i >= len(cur) - 1:
                i = len(cur) - 1
        i //= 2
    return {
        "body": base64.b64encode(bodies[index]).decode(),
        "logIndex": entry_index if entry_index is not None else index,
        "verification": {
            "inclusionProof": {
                "logIndex": index,
                "treeSize": len(bodies),
                "rootHash": r.hex(),
                "hashes": [h.hex() for h in path],
                "checkpoint": "rekor.sigstore.dev - 1\n%d\n%s\n\n— sig" % (
                    len(bodies), base64.b64encode(r).decode()),
            }
        },
    }


BODIES = [json.dumps({"kind": "hashedrekord", "n": i}, separators=(",", ":")).encode()
          for i in range(5)]


def test_correct_leaf_and_index_verify(mod):
    entry = make_entry(BODIES, 3)
    out = mod.check_entry(entry)
    assert out["verified"] is True
    assert out["folds_against"]["proof_log_index"]["match"] is True
    assert out["checkpoint"]["root_equals_proof_root"] is True


def test_double_hashed_leaf_never_verifies(mod):
    """The exact mistake the portal made: hashing the body, then hashing again."""
    entry = make_entry(BODIES, 3, leaf_mode="double")
    out = mod.check_entry(entry)
    assert out["verified"] is False


def test_entry_index_is_not_the_proof_index(mod):
    """When the two indices differ, folding against the entry's index must fail.

    The alternative index has to differ in its low bits: an index that is
    `proof_index + 96` on a size-5 tree folds identically because only the low
    ceil(log2(size)) bits are read. That is the same observation behind the
    ambiguous-tree-size vectors, and it is why this test picks index 2.
    """
    entry = make_entry(BODIES, 3, entry_index=2)
    out = mod.check_entry(entry)
    assert out["verified"] is True
    assert out["folds_against"]["proof_log_index"]["match"] is True
    assert out["folds_against"]["entry_log_index"]["match"] is False


def test_a_tampered_path_is_caught(mod):
    entry = make_entry(BODIES, 2)
    proof = entry["verification"]["inclusionProof"]
    proof["hashes"][0] = "00" * 32
    out = mod.check_entry(entry)
    assert out["verified"] is False


def test_a_dropped_sibling_is_caught(mod):
    entry = make_entry(BODIES, 4)
    entry["verification"]["inclusionProof"]["hashes"] = \
        entry["verification"]["inclusionProof"]["hashes"][:-1]
    out = mod.check_entry(entry)
    assert out["verified"] is False
