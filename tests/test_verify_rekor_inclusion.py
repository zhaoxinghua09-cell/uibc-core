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


# --- checkpoint signature ----------------------------------------------------
# The note format: three text lines each ending in a newline (the signed bytes),
# a blank line, then "— <origin> <base64(4-byte key id ‖ DER signature)>".
# Rekor's log key is ECDSA P-256 with SHA-256. Being able to verify this is the
# difference between "a root appears in a checkpoint" and "the log signed it".


@pytest.fixture(scope="module")
def log_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return key, pem


def signed_checkpoint(key, origin, size, root_b64, key_id=b"\xc0\xd2\x3d\x6a",
                     signer="rekor.sigstore.dev"):
    """A checkpoint in the note format.

    The text's origin line carries the tree id ("rekor.sigstore.dev - <id>"), but the
    signer name on the signature line is the bare origin ("rekor.sigstore.dev") — two
    different first fields, which is why `split_note` parts on the *second* space.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    body = ("%s\n%d\n%s\n" % (origin, size, root_b64)).encode()
    sig = key.sign(body, ec.ECDSA(hashes.SHA256()))
    return "%s\n%d\n%s\n\n\u2014 %s %s\n" % (
        origin, size, root_b64, signer, base64.b64encode(key_id + sig).decode())


def test_checkpoint_signature_verifies(mod, log_key):
    key, pem = log_key
    entry = make_entry(BODIES, 3)
    proof = entry["verification"]["inclusionProof"]
    proof["checkpoint"] = signed_checkpoint(
        key, "rekor.sigstore.dev - 1", len(BODIES), base64.b64encode(bytes.fromhex(proof["rootHash"])).decode())
    out = mod.check_entry(entry, pem)
    assert out["verified"] is True
    assert out["checkpoint"]["signature_verified"] is True
    assert out["checkpoint"]["signature"]["curve"] == "secp256r1"
    assert out["checkpoint"]["signature"]["signers"][0]["key_id"] == "c0d23d6a"


def test_unsigned_checkpoint_is_reported_not_assumed(mod, log_key):
    """Without the log key the tool must not claim a signature it never checked."""
    entry = make_entry(BODIES, 3)
    out = mod.check_entry(entry)
    assert out["checkpoint"]["signature_verified"] is None
    assert out["verified"] is True


def test_a_forged_checkpoint_signature_is_caught(mod, log_key):
    from cryptography.hazmat.primitives.asymmetric import ec
    key, pem = log_key
    other = ec.generate_private_key(ec.SECP256R1())
    entry = make_entry(BODIES, 3)
    proof = entry["verification"]["inclusionProof"]
    proof["checkpoint"] = signed_checkpoint(
        other, "rekor.sigstore.dev - 1", len(BODIES), base64.b64encode(bytes.fromhex(proof["rootHash"])).decode())
    out = mod.check_entry(entry, pem)
    assert out["checkpoint"]["signature_verified"] is False
    assert out["verified"] is False


def test_a_rewritten_tree_size_breaks_the_signature(mod, log_key):
    """The signature covers the size line: claiming a larger tree must not pass."""
    key, pem = log_key
    entry = make_entry(BODIES, 3)
    proof = entry["verification"]["inclusionProof"]
    cp = signed_checkpoint(key, "rekor.sigstore.dev - 1", len(BODIES),
                           base64.b64encode(bytes.fromhex(proof["rootHash"])).decode())
    proof["checkpoint"] = cp.replace("\n%d\n" % len(BODIES), "\n%d\n" % (len(BODIES) + 1))
    out = mod.check_entry(entry, pem)
    assert out["checkpoint"]["signature_verified"] is False
    assert out["verified"] is False


def test_missing_cryptography_is_reported_not_crashed(mod, log_key, monkeypatch):
    """The core is stdlib-only; a stranger without the extra must get a sentence."""
    import sys
    key, pem = log_key
    entry = make_entry(BODIES, 3)
    proof = entry["verification"]["inclusionProof"]
    proof["checkpoint"] = signed_checkpoint(
        key, "rekor.sigstore.dev - 1", len(BODIES), base64.b64encode(bytes.fromhex(proof["rootHash"])).decode())
    # A None in sys.modules is Python's own "this package cannot be imported" marker.
    # Every cached submodule has to go too, or the import resolves from the cache.
    for name in [n for n in list(sys.modules) if n == "cryptography" or n.startswith("cryptography.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "cryptography", None)
    out = mod.check_entry(entry, pem)
    assert out["checkpoint"]["signature_verified"] is None
    assert "uibc-core[verify]" in out["checkpoint"]["signature"]["why"]


# --- consistency between tree sizes ------------------------------------------
# Inclusion says "this leaf is in that tree". Consistency says "that earlier tree
# is a prefix of this later one". Different claims; the portal used to only make
# the first. These tests build MTH and consistency proofs from the RFC 6962
# definition, so the ported fold is checked against an independent construction.


def mth(ls):
    if not ls:
        return hashlib.sha256(b"").digest()
    if len(ls) == 1:
        return ls[0]
    k = 1
    while k * 2 < len(ls):
        k *= 2
    return node(mth(ls[:k]), mth(ls[k:]))


def consistency_proof(m, leaves, complete=True):
    """SUBPROOF(m, D[n], b) from RFC 6962 section 2.1.2.

    The third argument matters: when the earlier tree is not a perfect subtree of
    the later one, the recursion descends into it with b=false and the base case
    then *includes* the earlier tree's own root as one of the nodes. Dropping it
    produces a proof that is one node shorter and that no verifier should accept
    — which is exactly what the fold reports when it is fed one.
    """
    n = len(leaves)
    if m == n:
        return [] if complete else [mth(leaves)]
    k = 1
    while k * 2 < n:
        k *= 2
    if m <= k:
        return consistency_proof(m, leaves[:k], complete) + [mth(leaves[k:])]
    return consistency_proof(m - k, leaves[k:], False) + [mth(leaves[:k])]


LEAVES = [hashlib.sha256(b"\x00" + ("leaf-%d" % i).encode()).digest() for i in range(70)]


@pytest.mark.parametrize("m,n", [(1, 2), (2, 3), (3, 5), (4, 7), (7, 9), (9, 16),
                                (16, 17), (17, 33), (32, 64), (33, 65), (64, 70), (35, 70)])
def test_consistency_holds_for_every_shape(mod, m, n):
    proof = consistency_proof(m, LEAVES[:n])
    folded = mod.root_from_consistency_proof(m, n, proof, mth(LEAVES[:m]))
    assert folded == mth(LEAVES[:n])


def test_a_wrong_earlier_root_is_caught(mod):
    proof = consistency_proof(9, LEAVES[:16])
    bad = bytearray(mth(LEAVES[:9]))
    bad[0] ^= 0xff
    with pytest.raises(ValueError):
        mod.root_from_consistency_proof(9, 16, proof, bytes(bad))


def test_a_truncated_proof_is_caught(mod):
    proof = consistency_proof(9, LEAVES[:16])
    with pytest.raises(ValueError):
        mod.root_from_consistency_proof(9, 16, proof[:-1], mth(LEAVES[:9]))


def test_equal_sizes_need_an_empty_proof(mod):
    assert mod.root_from_consistency_proof(16, 16, [], mth(LEAVES[:16])) == mth(LEAVES[:16])
    with pytest.raises(ValueError):
        mod.root_from_consistency_proof(16, 16, [b"\x00" * 32], mth(LEAVES[:16]))


def test_a_shrinking_tree_is_not_a_consistency_claim(mod):
    with pytest.raises(ValueError):
        mod.root_from_consistency_proof(16, 9, [], mth(LEAVES[:16]))


def test_receipt_checkpoint_text_can_be_used_later(mod, log_key):
    """The receipt must carry its checkpoint text, or a later consistency run
    has nothing signed to compare against."""
    key, pem = log_key
    entry = make_entry(BODIES, 3)
    proof = entry["verification"]["inclusionProof"]
    proof["checkpoint"] = signed_checkpoint(
        key, "rekor.sigstore.dev - 1", len(BODIES), base64.b64encode(bytes.fromhex(proof["rootHash"])).decode())
    out = mod.check_entry(entry, pem)
    assert out["checkpoint"]["text"] == proof["checkpoint"]
