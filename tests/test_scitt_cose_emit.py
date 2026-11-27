"""Contracts for producing aee-scitt-cose/v0.1 statements.

The reader has its own tests; these are about the other direction. A producer
checked only against itself proves nothing, so nearly every case here runs the
bytes it produced through `uibc_core.scitt_cose.verify_transparent_statement`
and asserts the reader's answer - and, where a fault is being built, that the
reader refuses it by the same name a foreign corpus would be refused by.

Keys are bytes from a counter, not secrets: these tests assert structure, not
confidentiality.
"""

import hashlib
import json
import sys

import pytest

from uibc_core import cli, cose_min, ed25519, scitt_cose, scitt_cose_emit as emit

ISS = "uibc-emit-tests"
TS_ISS = "uibc-emit-tests-log"
ISS_SEED = bytes(range(1, 33))
TS_SEED = bytes(range(101, 133))
KID = b"\x11" * 16
TS_KID = b"\x22" * 16
AT = 1785000000
EXP = 1790000000
NBF = 1780000000


def _pub(seed):
    return ed25519.publickey(seed)


def _payload(subject="subject-1", **kw):
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()
    return emit.build_payload(subject_sha256=digest, **kw)


def _statement(payload, *, receipts=None, detached=False, seed=ISS_SEED, kid=KID,
               exp=EXP, nbf=NBF, observer=None, iss=ISS):
    return emit.build_statement(seed=seed, kid=kid, iss=iss, payload=payload,
                                exp=exp, nbf=nbf, receipts=receipts,
                                detached=detached, observer=observer)


def _vector(statement, payload, *, at=AT, detached=False, kid_hex=None,
            ts_kid=TS_KID, ts_pub=None, issuer_pub=None):
    return emit.build_vector(
        vector_id="t0", statement=statement, payload=payload, verification_time=at,
        issuer_iss=ISS, issuer_kid=bytes.fromhex(kid_hex) if kid_hex else KID,
        issuer_pub=issuer_pub or _pub(ISS_SEED),
        ts_iss=TS_ISS, ts_kid=ts_kid, ts_pub=ts_pub or _pub(TS_SEED),
        detached=detached)


def _tree(n=1, *, detached_index=-1):
    """n statements over one Merkle tree, one receipt each - the emitter's loop."""
    payloads = [_payload("subject-%d" % i) for i in range(n)]
    bare = [_statement(p, detached=(detached_index == i)) for i, p in enumerate(payloads)]
    entries = [emit.entry_bytes(s) for s in bare]
    root = emit.merkle_root(entries)
    carrying = []
    for i, payload in enumerate(payloads):
        receipt = emit.build_receipt(ts_seed=TS_SEED, ts_kid=TS_KID, entry=entries[i],
                                     tree_size=n, leaf_index=i,
                                     path=emit.inclusion_path(entries, i), root=root)
        carrying.append(_statement(payload, receipts=[receipt],
                                   detached=(detached_index == i)))
    return payloads, carrying, entries, root


def _reframe(protected: bytes, uhdr, payload, signature: bytes) -> bytes:
    return b"\xd2" + cose_min.encode([protected, uhdr, payload, signature])


# --------------------------------------------------------------------------
# the happy path, read back
# --------------------------------------------------------------------------

def test_single_statement_reads_back_valid():
    payloads, statements, _, _ = _tree(1)
    verdict = scitt_cose.verify_transparent_statement(_vector(statements[0], payloads[0]))
    assert verdict["verdict"] == "valid", verdict


def test_tree_of_three_each_reads_back_valid():
    payloads, statements, entries, root = _tree(3)
    for payload, statement in zip(payloads, statements):
        assert scitt_cose.verify_transparent_statement(
            _vector(statement, payload))["verdict"] == "valid"
    assert root == emit.merkle_root(entries)


def test_protected_header_is_deterministic():
    statement = _statement(_payload())
    protected = scitt_cose.sign1_from_bytes(statement).protected_bytes
    node = scitt_cose.loads(protected)
    assert scitt_cose._scan_deterministic(protected, node) == ""
    # and the reader's own stage 1 agrees, having seen it as a whole statement
    assert scitt_cose.verify_transparent_statement(
        _vector(statement, _payload()))["codes"] in ([], ["receipts-absent"])


def test_same_inputs_same_bytes():
    payload = _payload()
    assert _statement(payload) == _statement(payload)
    assert _tree(2)[3] == _tree(2)[3]


# --------------------------------------------------------------------------
# detached payloads
# --------------------------------------------------------------------------

def test_detached_statement_needs_the_payload_supplied():
    payloads, statements, _, _ = _tree(1, detached_index=0)
    without = _vector(statements[0], payloads[0], detached=True)
    without["detachedPayload"] = None
    assert "payload-absent" in scitt_cose.verify_transparent_statement(without)["codes"]

    with_payload = _vector(statements[0], payloads[0], detached=True)
    assert scitt_cose.verify_transparent_statement(with_payload)["verdict"] == "valid"


# --------------------------------------------------------------------------
# claims a producer can get wrong
# --------------------------------------------------------------------------

def test_sub_must_equal_what_the_payload_declares():
    payload = _payload()
    with pytest.raises(emit.EmitError):
        emit.build_statement(seed=ISS_SEED, kid=KID, iss=ISS, payload=payload,
                             sub="sha256:" + "0" * 64)


def test_expired_statement_is_refused_by_the_reader():
    payloads, statements, _, _ = _tree(1)
    verdict = scitt_cose.verify_transparent_statement(
        _vector(statements[0], payloads[0], at=EXP + 1))
    assert "statement-expired" in verdict["codes"], verdict


def test_not_yet_valid_statement_is_refused_by_the_reader():
    payloads, statements, _, _ = _tree(1)
    verdict = scitt_cose.verify_transparent_statement(
        _vector(statements[0], payloads[0], at=NBF - 1))
    assert "statement-not-yet-valid" in verdict["codes"], verdict


def test_unknown_kid_is_refused():
    payloads, statements, _, _ = _tree(1)
    verdict = scitt_cose.verify_transparent_statement(
        _vector(statements[0], payloads[0], kid_hex="ff" * 16))
    assert "issuer-key-unknown" in verdict["codes"], verdict


def test_tampered_payload_breaks_the_signature():
    payloads, statements, _, _ = _tree(1)
    signed = scitt_cose.sign1_from_bytes(statements[0])
    corrupted = _reframe(signed.protected_bytes, signed.uhdr,
                         signed.payload + b"x", signed.signature)
    vector = _vector(statements[0], payloads[0])
    vector["transparentStatement"] = corrupted.hex()
    assert "signature-invalid" in scitt_cose.verify_transparent_statement(vector)["codes"]


# --------------------------------------------------------------------------
# receipts
# --------------------------------------------------------------------------

def test_receipt_issued_about_another_entry_is_refused():
    payloads, _, entries, root = _tree(3)
    # A receipt whose proof addresses leaf 1, attached to leaf 0's statement: the
    # root its own proof yields is the table's, but not this entry's, so the
    # signature over that root cannot verify.
    receipt = emit.build_receipt(ts_seed=TS_SEED, ts_kid=TS_KID, entry=entries[1],
                                 tree_size=3, leaf_index=1,
                                 path=emit.inclusion_path(entries, 1), root=root)
    statement = _statement(payloads[0], receipts=[receipt])
    verdict = scitt_cose.verify_transparent_statement(_vector(statement, payloads[0]))
    assert "receipt-subject-mismatch" in verdict["codes"], verdict


def test_audit_path_lengths_match_the_tree_shape():
    # RFC 9162 2.1.3.2: for three leaves the split is at 2, so leaves 0 and 1
    # carry two siblings each and the odd leaf carries one.
    _, _, three, _ = _tree(3)
    assert [len(emit.inclusion_path(three, i)) for i in range(3)] == [2, 2, 1]
    _, _, four, _ = _tree(4)
    assert [len(emit.inclusion_path(four, i)) for i in range(4)] == [2, 2, 2, 2]


def test_receipt_without_inclusion_proof_is_refused():
    payloads, _, entries, root = _tree(1)
    receipt = emit.build_receipt(ts_seed=TS_SEED, ts_kid=TS_KID, entry=entries[0],
                                 tree_size=1, leaf_index=0, path=[], root=root)
    signed = scitt_cose.sign1_from_bytes(receipt)
    stripped = _reframe(signed.protected_bytes, {}, signed.payload, signed.signature)
    statement = _statement(payloads[0], receipts=[stripped])
    verdict = scitt_cose.verify_transparent_statement(_vector(statement, payloads[0]))
    assert "inclusion-proof-absent" in verdict["codes"], verdict


# --------------------------------------------------------------------------
# observer position
# --------------------------------------------------------------------------

def test_observer_position_is_emitted_critical_and_read_as_a_note():
    payloads, _, _, _ = _tree(1)
    payload = payloads[0]
    observer = {"vantage": "issuer-side", "observedFrom": "uibc-core",
                "reachableByObserved": True}
    # The entry a receipt covers includes the protected header, so the observer
    # position has to be in place before the receipt is issued over the entry.
    bare = _statement(payload, observer=observer)
    entry = emit.entry_bytes(bare)
    receipt = emit.build_receipt(ts_seed=TS_SEED, ts_kid=TS_KID, entry=entry,
                                 tree_size=1, leaf_index=0, path=[],
                                 root=emit.merkle_root([entry]))
    statement = _statement(payload, receipts=[receipt], observer=observer)
    protected = scitt_cose.sign1_from_bytes(statement).protected
    assert protected[scitt_cose.LBL_CRIT] == [scitt_cose.LBL_OBSERVER_POSITION]
    verdict = scitt_cose.verify_transparent_statement(_vector(statement, payload))
    assert verdict["verdict"] == "valid", verdict
    assert any("reachableByObserved is true" in n for n in verdict["notes"]), verdict


# --------------------------------------------------------------------------
# the CLI path: emit, then read the result back in corpus mode
# --------------------------------------------------------------------------

def test_cli_emit_then_corpus_mode(tmp_path, monkeypatch):
    out = tmp_path / "corpus"
    monkeypatch.setattr(sys, "argv", [
        "uibc", "emit-cose", "--out", str(out), "--count", "3",
        "--at", str(AT), "--exp", str(EXP), "--nbf", str(NBF),
        "--seed-hex", ISS_SEED.hex(), "--ts-seed-hex", TS_SEED.hex(),
        "--kid-hex", KID.hex(), "--ts-kid-hex", TS_KID.hex(),
        "--detached-index", "2"])
    with pytest.raises(SystemExit) as emitted:
        cli.main()
    assert emitted.value.code == 0

    manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["accept"] == 3
    assert len(manifest["vectors"]) == 3
    assert len(manifest["treeRoot"]) == 64

    monkeypatch.setattr(sys, "argv", [
        "uibc", "verify-cose", "--manifest", str(out / "MANIFEST.json"),
        "--statements", str(out / "statements"), "--at", str(AT)])
    with pytest.raises(SystemExit) as read_back:
        cli.main()
    assert read_back.value.code == 0