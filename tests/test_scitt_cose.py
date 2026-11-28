"""Contracts for reading aee-scitt-cose/v0.1 Transparent Statements.

These tests build their own statements and their own Merkle tree. That is the
point rather than extra work: a verifier tested only against a corpus someone
else generated cannot tell a shared fault from a shared understanding, and the
profile itself asks an implementer to recompute the root rather than trust the
one it receives. Every case here therefore constructs the fault it names from
bytes, then asserts the reader refuses it by name.

No third-party dependency: the CBOR writer below is the encoder this repository
already uses for its own seals (`uibc_core.cose_min`), with tag support added so
the statement can carry CBOR tag 18.
"""

import hashlib
import json
import sys

import pytest

from uibc_core import cose_min, ed25519, scitt_cose

# --------------------------------------------------------------------------
# A tiny CBOR writer with tags, and helpers that build a Transparent Statement
# --------------------------------------------------------------------------

ISS = "observer.example"
KID = b"aee-observer-1"
TS_ISS = "transparency-service-1"
TS_KID = b"transparency-service-1"


class Tag:
    def __init__(self, number, value):
        self.number = number
        self.value = value


def _head(major, value):
    return cose_min._enc_head(major, value)


def enc(obj):
    if isinstance(obj, Tag):
        return _head(6, obj.number) + enc(obj.value)
    if isinstance(obj, bool):
        return b"\xf5" if obj else b"\xf4"
    if obj is None:
        return b"\xf6"
    if isinstance(obj, int):
        return _head(0, obj) if obj >= 0 else _head(1, -1 - obj)
    if isinstance(obj, bytes):
        return _head(2, len(obj)) + obj
    if isinstance(obj, str):
        raw = obj.encode("utf-8")
        return _head(3, len(raw)) + raw
    if isinstance(obj, (list, tuple)):
        return _head(4, len(obj)) + b"".join(enc(v) for v in obj)
    if isinstance(obj, dict):
        pairs = [(len(kb), kb, enc(v)) for k, v in obj.items() for kb in (enc(k),)]
        pairs.sort(key=lambda t: (t[0], t[1]))
        return _head(5, len(pairs)) + b"".join(kb + vb for _, kb, vb in pairs)
    raise TypeError("cannot encode %r" % (type(obj),))


def _sig_structure(protected, payload):
    return enc(["Signature1", protected, b"", payload])


def leaf_hash(entry):
    return hashlib.sha256(b"\x00" + entry).digest()


def node_hash(left, right):
    return hashlib.sha256(b"\x01" + left + right).digest()


def merkle(leaves):
    """Root and level-ordered internals for a power-of-two tree."""
    level = [leaf_hash(x) for x in leaves]
    while len(level) > 1:
        level = [node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def inclusion_path(leaves, index):
    """RFC 9162 sibling path for a power-of-two tree of `leaves`."""
    level = [leaf_hash(x) for x in leaves]
    path = []
    idx = index
    while len(level) > 1:
        sibling = idx ^ 1
        path.append(level[sibling])
        level = [node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        idx >>= 1
    return path


SUBJECT_DIGEST = "b" * 64


def subject_claim(digest=SUBJECT_DIGEST):
    return "sha256:" + digest


def statement_payload(digest=SUBJECT_DIGEST, result="fail"):
    return json.dumps({
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "run/2026-09-09/photometric-regrade",
                     "digest": {"sha256": digest}}],
        "predicateType": "https://in-toto.io/attestation/adversarial-execution-evidence/v0.7",
        "predicate": {"observation": {"observedAt": "2026-09-09T12:00:00Z",
                                      "source": "host_vmi"},
                      "result": result},
    }).encode("utf-8")


def statement_bytes(seed, issuer_seed, payload=None, alg=-19, crit=(scitt_cose.LBL_OBSERVER_POSITION,),
                   claims=None, kid=KID, observer=None, detached=False, uhdr_extra=None):
    payload = statement_payload() if payload is None else payload
    claims = claims if claims is not None else {1: ISS, 2: subject_claim()}
    position = observer if observer is not None else {
        "vantage": "host_vmi", "observedFrom": "hypervisor", "reachableByObserved": False}
    protected_map = {
        1: alg,
        2: list(crit) if crit is not None else None,
        3: scitt_cose.CONTENT_TYPE,
        4: kid,
        15: claims,
        16: scitt_cose.TYP,
        scitt_cose.LBL_OBSERVER_POSITION: position,
    }
    protected_map = {k: v for k, v in protected_map.items() if v is not None}
    protected = enc(protected_map)
    sig = ed25519.sign(issuer_seed, _sig_structure(protected, payload))
    uhdr = dict(uhdr_extra or {})
    body = [protected, uhdr, None if detached else payload, sig]
    return enc(Tag(18, body)), payload


def receipt_bytes(entry, ts_seed, tree_leaves, leaf_index, kid=TS_KID, vds=1, alg=-19,
                  vdp=True, proof_type=scitt_cose.PROOF_INCLUSION, claimed_index=None):
    root = merkle(tree_leaves)
    protected = enc({1: alg, 4: kid, 395: vds} if vds is not None else {1: alg, 4: kid})
    uhdr = {}
    if vdp:
        path = inclusion_path(tree_leaves, 0)
        claimed = leaf_index if claimed_index is None else claimed_index
        proof = enc([len(tree_leaves), claimed, path])
        uhdr = {396: {proof_type: [proof]}}
    sig = ed25519.sign(ts_seed, _sig_structure(protected, root))
    return enc(Tag(18, [protected, uhdr, None, sig]))


def transparent(statement, receipts):
    """Attach receipts to a signed statement, keeping the entry bytes intact."""
    data = statement
    # re-encode the same body with receipts in the unprotected bucket
    node = scitt_cose.loads(data)
    body = node.items[0]
    protected = body.items[0].value
    payload_bytes = body.items[2].value      # None where the wire form detaches it
    uhdr = {scitt_cose.LBL_RECEIPTS: list(receipts)}
    sig = body.items[3].value
    return enc(Tag(18, [protected, uhdr, payload_bytes, sig]))


def vector(seed, issuer_seed, ts_seed, **kw):
    """A complete vector input with its trust block, as a corpus ships them."""
    pub = ed25519.publickey(issuer_seed)
    ts_pub = ed25519.publickey(ts_seed)
    st, payload = statement_bytes(seed, issuer_seed, detached=kw.pop("detached", False), **kw)
    return st, payload, {
        "verificationTime": "2026-09-09T12:00:00Z",
        "trust": {
            "issuers": [{"iss": ISS, "kid": KID.hex(),
                         "key": {"kty": "OKP", "crv": "Ed25519", "x": pub.hex()}}],
            "transparencyServices": [{"kid": TS_KID.hex(),
                                      "key": {"kty": "OKP", "crv": "Ed25519", "x": ts_pub.hex()}}],
        },
    }


SEED = b"\x01" * 32
ISSUER = b"\x02" * 32
TS_SEED = b"\x03" * 32


def build(**kw):
    """A valid vector: statement, one receipt over a four-leaf tree, trust block."""
    st, payload, trust = vector(SEED, ISSUER, TS_SEED, **kw)
    leaves = [st, b"other-1", b"other-2", b"other-3"]
    rc = receipt_bytes(st, TS_SEED, leaves, 0)
    return {"transparentStatement": transparent(st, [rc]).hex(),
            "detachedPayload": payload.hex() if kw.get("detached") else None,
            "verificationTime": trust["verificationTime"],
            "trust": trust["trust"]}


def judge(vec, now=None):
    return scitt_cose.verify_transparent_statement(vec, now=now)


# --------------------------------------------------------------------------
# The accept path
# --------------------------------------------------------------------------

def test_a_well_formed_transparent_statement_is_valid():
    out = judge(build())
    assert out["verdict"] == "valid"
    assert out["codes"] == []
    assert any("reachableByObserved=False" in n for n in out["notes"])


def test_a_detached_payload_is_reattached_before_the_signature_is_checked():
    out = judge(build(detached=True))
    assert out["verdict"] == "valid"


def test_the_entry_excludes_the_receipts_and_keeps_every_other_byte():
    st, _payload, _trust = vector(SEED, ISSUER, TS_SEED)
    rc = receipt_bytes(st, TS_SEED, [st, b"a", b"b", b"c"], 0)
    tr = transparent(st, [rc])
    assert scitt_cose.sign1_from_bytes(tr).entry_bytes() == st


# --------------------------------------------------------------------------
# One refusal per fault, each constructed rather than described
# --------------------------------------------------------------------------

def test_a_tampered_signature_is_refused():
    vec = build()
    raw = bytearray(bytes.fromhex(vec["transparentStatement"]))
    raw[-3] ^= 0x01
    vec["transparentStatement"] = bytes(raw).hex()
    out = judge(vec)
    assert out["verdict"] == "invalid"
    assert "signature-invalid" in out["codes"]


def test_the_deprecated_polymorphic_identifier_is_refused_by_identifier():
    vec = build(alg=scitt_cose.ALG_EDDSA_DEPRECATED)
    out = judge(vec)
    assert "algorithm-deprecated" in out["codes"]


def test_a_declared_ecdsa_algorithm_over_an_ed25519_signature_is_a_mismatch():
    vec = build(alg=scitt_cose.ALG_ES256_DEPRECATED)
    out = judge(vec)
    assert "algorithm-mismatch" in out["codes"]


def test_a_subject_claim_that_is_not_the_payload_digest_is_refused():
    payload = statement_payload()
    claims = {1: ISS, 2: subject_claim("c" * 64)}
    vec = build(payload=payload, claims=claims)
    assert "subject-digest-mismatch" in judge(vec)["codes"]


def test_an_issuer_claim_that_is_not_the_identity_bound_to_the_key_is_refused():
    claims = {1: "someone.else", 2: subject_claim()}
    vec = build(claims=claims)
    assert "issuer-identity-mismatch" in judge(vec)["codes"]


def test_a_statement_past_its_expiry_is_refused_at_the_instant_it_is_judged():
    claims = {1: ISS, 2: subject_claim(), 4: 1788956000}
    vec = build(claims=claims)
    assert "statement-expired" not in judge(vec)["codes"]
    assert "statement-expired" in judge(vec, now=1789041600)["codes"]


def test_a_receipt_with_no_verifiable_data_proof_is_refused():
    st, _payload, trust = vector(SEED, ISSUER, TS_SEED)
    rc = receipt_bytes(st, TS_SEED, [st, b"a", b"b", b"c"], 0, vdp=False)
    vec = {"transparentStatement": transparent(st, [rc]).hex(), "detachedPayload": None,
           "verificationTime": trust["verificationTime"], "trust": trust["trust"]}
    out = judge(vec)
    assert out["verdict"] == "invalid"
    assert "inclusion-proof-absent" in out["codes"]


def test_a_leaf_index_outside_the_tree_makes_the_proof_unapplicable():
    st, _payload, trust = vector(SEED, ISSUER, TS_SEED)
    leaves = [st, b"a", b"b", b"c"]
    rc = receipt_bytes(st, TS_SEED, leaves, 0, claimed_index=4)   # 4 >= tree_size
    vec = {"transparentStatement": transparent(st, [rc]).hex(), "detachedPayload": None,
           "verificationTime": trust["verificationTime"], "trust": trust["trust"]}
    out = judge(vec)
    assert "inclusion-proof-unapplicable" in out["codes"]


def test_a_receipt_about_another_entry_is_refused_as_a_subject_mismatch():
    st, _payload, trust = vector(SEED, ISSUER, TS_SEED)
    other = b"some-other-entry"
    rc = receipt_bytes(st, TS_SEED, [other, b"a", b"b", b"c"], 0)
    vec = {"transparentStatement": transparent(st, [rc]).hex(), "detachedPayload": None,
           "verificationTime": trust["verificationTime"], "trust": trust["trust"]}
    assert "receipt-subject-mismatch" in judge(vec)["codes"]


def test_a_receipt_declaring_an_unregistered_vds_is_refused():
    st, _payload, trust = vector(SEED, ISSUER, TS_SEED)
    rc = receipt_bytes(st, TS_SEED, [st, b"a", b"b", b"c"], 0, vds=0)
    vec = {"transparentStatement": transparent(st, [rc]).hex(), "detachedPayload": None,
           "verificationTime": trust["verificationTime"], "trust": trust["trust"]}
    assert "receipt-vds-unregistered" in judge(vec)["codes"]


def test_cwt_claims_in_both_buckets_are_refused_rather_than_preferred():
    st, payload, trust = vector(SEED, ISSUER, TS_SEED)
    rc = receipt_bytes(st, TS_SEED, [st, b"a", b"b", b"c"], 0)
    node = scitt_cose.loads(st)
    protected = node.items[0].items[0].value
    sig = node.items[0].items[3].value
    tr = enc(Tag(18, [protected,
                      {scitt_cose.LBL_CWT_CLAIMS: {1: "duplicate"},
                       scitt_cose.LBL_RECEIPTS: [rc]},
                      payload, sig]))
    vec = {"transparentStatement": tr.hex(), "detachedPayload": None,
           "verificationTime": trust["verificationTime"], "trust": trust["trust"]}
    assert "cwt-claims-duplicated" in judge(vec)["codes"]


def test_an_observer_position_that_crit_does_not_name_is_refused():
    vec = build(crit=())
    assert "observer-position-not-critical" in judge(vec)["codes"]


def test_crit_naming_a_label_absent_from_the_protected_bucket_is_refused():
    vec = build(crit=(scitt_cose.LBL_OBSERVER_POSITION, 99))
    assert "critical-parameter-unprotected" in judge(vec)["codes"]


def test_a_critical_label_this_profile_does_not_define_is_refused():
    st, payload, trust = vector(SEED, ISSUER, TS_SEED)
    # crit names a label that IS protected but is not the observer position
    vec = build(crit=(scitt_cose.LBL_OBSERVER_POSITION, scitt_cose.LBL_CONTENT_TYPE))
    out = judge(vec)
    assert "critical-parameter-unprocessable" in out["codes"]


def test_a_protected_header_out_of_map_order_is_refused():
    payload = statement_payload()
    claims = {1: ISS, 2: subject_claim()}
    # build the map by hand in the wrong order: label 16 before label 1
    wrong = (b"\xa7"
             + enc(16) + enc(scitt_cose.TYP)
             + enc(1) + enc(-19)
             + enc(3) + enc(scitt_cose.CONTENT_TYPE)
             + enc(4) + enc(KID)
             + enc(15) + enc(claims)
             + enc(2) + enc([scitt_cose.LBL_OBSERVER_POSITION])
             + enc(scitt_cose.LBL_OBSERVER_POSITION)
             + enc({"vantage": "host_vmi", "observedFrom": "hypervisor",
                     "reachableByObserved": False}))
    sig = ed25519.sign(ISSUER, _sig_structure(wrong, payload))
    st = enc(Tag(18, [wrong, {}, payload, sig]))
    pub = ed25519.publickey(ISSUER)
    ts_pub = ed25519.publickey(TS_SEED)
    rc = receipt_bytes(st, TS_SEED, [st, b"a", b"b", b"c"], 0)
    vec = {"transparentStatement": transparent(st, [rc]).hex(), "detachedPayload": None,
           "verificationTime": "2026-09-09T12:00:00Z",
           "trust": {"issuers": [{"iss": ISS, "kid": KID.hex(),
                                  "key": {"kty": "OKP", "crv": "Ed25519", "x": pub.hex()}}],
                     "transparencyServices": [{"kid": TS_KID.hex(),
                                               "key": {"kty": "OKP", "crv": "Ed25519",
                                                       "x": ts_pub.hex()}}]}}
    assert "protected-header-not-deterministic" in judge(vec)["codes"]


def test_bytes_that_are_not_a_tagged_sign1_are_refused_rather_than_crashing():
    vec = build()
    vec["transparentStatement"] = "00"
    out = judge(vec)
    assert out["verdict"] == "invalid"
    assert "unreadable" in out["codes"]


def test_a_statement_with_no_receipts_is_refused():
    st, payload, trust = vector(SEED, ISSUER, TS_SEED)
    node = scitt_cose.loads(st)
    protected = node.items[0].items[0].value
    sig = node.items[0].items[3].value
    tr = enc(Tag(18, [protected, {}, payload, sig]))
    vec = {"transparentStatement": tr.hex(), "detachedPayload": None,
           "verificationTime": trust["verificationTime"], "trust": trust["trust"]}
    assert "receipts-absent" in judge(vec)["codes"]


# --------------------------------------------------------------------------
# The command line: a corpus in, one conforming verdict per member out
# --------------------------------------------------------------------------

def test_verify_cose_scores_a_two_member_corpus(tmp_path):
    from uibc_core import cli

    good = build()
    bad = build()
    bad["transparentStatement"] = good["transparentStatement"][:-6] + "0000" + good["transparentStatement"][-2:]
    good["transparentStatement"] = good["transparentStatement"]
    statements = tmp_path / "statements"
    statements.mkdir()
    (statements / "vgood.json").write_text(json.dumps(good), encoding="utf-8")
    (statements / "vbad.json").write_text(json.dumps(bad), encoding="utf-8")
    manifest = {
        "profile": scitt_cose.PROFILE,
        "counts": {"accept": 1, "reject": 1, "indeterminate": 0},
        "vectors": [
            {"id": "vgood", "kind": "accept", "file": "statements/vgood.json",
             "expected": {"verdict": "valid"}},
            {"id": "vbad", "kind": "reject", "file": "statements/vbad.json",
             "expected": {"verdict": "invalid", "codes": ["signature-invalid"]}},
        ],
    }
    mpath = tmp_path / "MANIFEST.json"
    mpath.write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "rows.jsonl"
    summary = tmp_path / "score.json"
    argv = ["uibc", "verify-cose", "--manifest", str(mpath),
            "--statements", str(statements), "--report", str(out),
            "--json-out", str(summary)]
    old = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(SystemExit) as exit_info:
            cli.main()
    finally:
        sys.argv = old
    assert exit_info.value.code == 0
    score = json.loads(summary.read_text(encoding="utf-8"))
    assert score["conforming"] == 2
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert sorted(r["verdict"] for r in rows) == ["invalid", "valid"]
    assert all(r["format"] == "uibc-scitt-cose-report/1" for r in rows)
    assert len(rows) == 2
    assert [r["vector"] for r in rows] == ["vgood", "vbad"]
    assert all(r["verifier_id"] for r in rows)


def test_indeterminate_readings_count_a_refusal_as_conforming():
    from uibc_core.cli import _expected_conforms

    readings = {"inclusion-required": "receipt-not-of-inclusion",
                "any-registered-proof": "valid",
                "unsupported-proof-type": "receipt-proof-type-unsupported"}
    assert _expected_conforms({"readings": readings}, "invalid", ["inclusion-proof-absent"]) is True
    assert _expected_conforms({"readings": readings}, "valid", []) is True