"""§4.2.4 trusted resolution - the part that must not trust the resolver.

The protocol's own words: trusted resolution verifies "the public key and signature
content" of the document "so that every resolution service passed in recursion is
trustworthy". The failure mode this file guards is a client that reads
`data.verify` and stops: that delegates the check to the party being checked.

Every test drives `resolve_bid_trusted` with an injected fetcher - no network.
"""

import json
import pathlib

import pytest

from uibc_core import bid_protocol as B

REPO = pathlib.Path(__file__).resolve().parent.parent
SIGNED = json.loads((REPO / "fixtures" / "bid" / "signed_document.json").read_text(encoding="utf-8"))
DID = SIGNED["id"]


def fetcher_for(answer, seen=None):
    def f(url, timeout=10):
        if seen is not None:
            seen.append(url)
        return answer(url) if callable(answer) else answer
    return f


def envelope(doc, verify=True):
    return {"errorCode": 0, "message": "success", "data": {"version": "1.0.0", "verify": verify,
                                                           "didDocument": doc}}


def trust(answer, **kwargs):
    return B.resolve_bid_trusted("http://resolver.example", DID, fetcher=fetcher_for(answer), **kwargs)


# ---------------------------------------------------------------- the request
def test_it_asks_the_trusted_endpoint_with_the_literal_query():
    seen = []
    B.resolve_bid_trusted("http://resolver.example", DID, fetcher=fetcher_for(envelope(SIGNED), seen))
    assert seen == ["http://resolver.example/%s?verify=true" % DID], seen
    assert "verify=" in seen[0]


# ------------------------------------------------- server claim vs our own check
def test_server_verify_true_plus_good_signature_is_trusted():
    r = trust(envelope(SIGNED))
    assert r.server_verify is True
    assert r.signature_ok is True
    assert r.delegate_state == "absent"
    assert r.trusted is True and r.fully_trusted is True


def test_server_verify_true_but_broken_signature_is_not_trusted():
    """The whole point: a resolver saying "verified" cannot make a bad document good."""
    tampered = dict(SIGNED)
    tampered["created"] = "2021-06-24T09:10:10Z"  # signed over the old value
    r = trust(envelope(tampered))
    assert r.server_verify is True
    assert r.signature_ok is False
    assert r.trusted is False, r.reason


def test_server_verify_true_without_any_proof_is_not_trusted():
    doc = {k: v for k, v in SIGNED.items() if k != "proof"}
    r = trust(envelope(doc))
    assert r.signature_ok is False and r.trusted is False


def test_server_verify_false_is_an_answer_not_an_exception():
    r = trust(envelope(SIGNED, verify=False))
    assert r.server_verify is False
    assert r.trusted is False
    assert "literal true" in r.reason


def test_string_true_is_rejected_rather_than_coerced():
    payload = {"errorCode": 0, "data": {"verify": "true", "didDocument": SIGNED}}
    with pytest.raises(B.BIDDocumentError):
        trust(payload)


def test_missing_verify_field_is_a_protocol_error():
    payload = {"errorCode": 0, "data": {"didDocument": SIGNED}}
    with pytest.raises(B.BIDDocumentError):
        trust(payload)


def test_error_code_9_from_the_resolver_keeps_its_meaning():
    with pytest.raises(B.BIDResponseError) as ei:
        trust({"errorCode": 9, "message": "verify failed"})
    assert ei.value.code == 9
    assert ei.value.kind == "security"


# --------------------------------------------------------------- delegateSign
def _with_delegate(signer_seed, signer_did="did:bid:efJgt44mNDewKK1VEN454R17cjso3mSG"):
    """A copy of the signed fixture carrying an attestation over its publicKey."""
    signer_key_id = signer_did + "#key-1"
    doc = json.loads(json.dumps(SIGNED))
    sig = B.ed_sign(signer_seed, B.delegate_signing_bytes(doc))
    doc["extension"] = dict(doc["extension"])
    doc["extension"]["delegateSign"] = {"signer": signer_key_id,
                                        "signatureValue": B.base58_encode(sig)}
    doc = B.sign_bid_document(doc, bytes(range(32)), SIGNED["authentication"][0])
    return doc, signer_key_id, "b06566" + B.ed_public_key(signer_seed).hex()


SIGNER_SEED = bytes([0x11] * 32)


def test_delegate_attestation_verifies_against_the_signers_key():
    doc, signer_id, signer_hex = _with_delegate(SIGNER_SEED)
    r = trust(envelope(doc), delegate_key_resolver=lambda kid: signer_hex if kid == signer_id else None)
    assert r.delegate_state == "verified"
    assert r.delegate_signer == signer_id
    assert r.trusted and r.fully_trusted


def test_delegate_present_without_a_resolver_is_unchecked_not_trusted_through():
    doc, _sid, _hex = _with_delegate(SIGNER_SEED)
    r = trust(envelope(doc))
    assert r.delegate_state == "unchecked"
    assert r.trusted is True            # server + document signature still hold
    assert r.fully_trusted is False     # but the attestation was not checked
    assert "NOT verified" in r.reason


def test_delegate_with_a_wrong_key_is_invalid():
    doc, _sid, _hex = _with_delegate(SIGNER_SEED)
    wrong = "b0" + B.ed_public_key(bytes([0x22] * 32)).hex()
    r = trust(envelope(doc), delegate_key_resolver=lambda kid: wrong)
    assert r.delegate_state == "invalid"
    assert r.trusted is False


def test_delegate_signer_must_be_a_bid_key_id():
    doc, _sid, _hex = _with_delegate(SIGNER_SEED)
    doc["extension"]["delegateSign"]["signer"] = "not-a-bid"
    doc = B.sign_bid_document(doc, bytes(range(32)), SIGNED["authentication"][0])
    r = trust(envelope(doc), delegate_key_resolver=lambda kid: _hex)
    assert r.delegate_state == "invalid"


def test_delegate_signature_value_that_is_not_base58_is_invalid():
    doc, signer_id, signer_hex = _with_delegate(SIGNER_SEED)
    doc["extension"]["delegateSign"]["signatureValue"] = "0000!!!"
    doc = B.sign_bid_document(doc, bytes(range(32)), SIGNED["authentication"][0])
    r = trust(envelope(doc), delegate_key_resolver=lambda kid: signer_hex)
    assert r.delegate_state == "invalid"


def test_unresolvable_signer_is_unchecked_not_forged():
    doc, _sid, _hex = _with_delegate(SIGNER_SEED)

    def boom(_kid):
        raise B.BIDResponseError(6, "not found")

    r = trust(envelope(doc), delegate_key_resolver=boom)
    assert r.delegate_state == "unchecked"
    assert "could not be resolved" in r.reason


def test_delegate_bytes_are_jcs_over_the_public_key_array():
    doc, _sid, _hex = _with_delegate(SIGNER_SEED)
    assert B.delegate_signing_bytes(doc) == B.canonicalize(doc["publicKey"])
