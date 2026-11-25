"""Pins the BID protocol layer against 《星火·链网BID协议》 §4.2 / §4.2.5 / §5 / appendix 1.

Each test names the clause it pins. A test that fails here means the code drifted
from the protocol text, not that the test is fussy.
"""

import pytest

from uibc_core import bid_protocol as B

DID = "did:bid:ef18F9AVK4SQLZPRrPkrVWwp9kbpdXHx"
KEY_ID = DID + "#key-1"


def _doc(**overrides):
    doc = {
        "@context": ["https://w3.org/ns/did/v1"],
        "id": DID,
        "created": "2021-06-24T09:10:09Z",
        "updated": "2021-06-24T09:10:09Z",
        "authentication": [KEY_ID],
        "publicKey": [
            {
                "controller": DID,
                "id": KEY_ID,
                "publicKeyHex": "b06566f76733ae048fda721d47afe8780b572636496c93253db86dc8d54e3f9a",
                "type": "ED25519",
            }
        ],
        "extension": {"ttl": 86400, "type": 105},
    }
    doc.update(overrides)
    return doc


# ---------------------------------------------------------------- §4.2.5 codes
def test_all_eleven_codes_are_named_as_the_protocol_names_them():
    assert len(B.BID_RESPONSE_CODES) == 11
    assert set(B.BID_RESPONSE_CODES) == set(range(11))
    assert B.BID_RESPONSE_CODES[0] == ("success", "ok")
    assert B.BID_RESPONSE_CODES[6][0] == "not found"
    assert B.BID_RESPONSE_CODES[3][0] == "server too busy"
    assert B.BID_RESPONSE_CODES[9][0] == "verify failed"


def test_only_three_and_seven_are_retryable():
    for code, (_name, kind) in B.BID_RESPONSE_CODES.items():
        err = B.BIDResponseError(code, did=DID)
        assert err.retryable == (code in (3, 7)), code
    assert {c for c in range(11) if B.BIDResponseError(c).retryable} == {3, 7}


def test_not_found_codes_are_not_thrown_into_one_bag():
    for code in (6, 8, 10):
        assert B.BIDResponseError(code).not_found, code
    for code in (1, 2, 3, 4, 5, 7, 9):
        assert not B.BIDResponseError(code).not_found, code


def test_an_undocumented_code_still_carries_its_number():
    err = B.BIDResponseError(42, "who knows", DID)
    assert err.code == 42 and "undocumented code" in err.name
    assert not err.retryable and not err.not_found


# ------------------------------------------------------------ §4.2.1 envelope
def test_three_wire_shapes_are_unwrapped():
    doc = _doc()
    assert B.parse_bid_envelope({"errorCode": 0, "data": {"didDocument": doc}}, DID) is doc
    assert B.parse_bid_envelope({"errorCode": 0, "didDocument": doc}, DID) is doc
    assert B.parse_bid_envelope(doc, DID) is doc


def test_non_zero_code_is_raised_with_the_number_not_swallowed():
    with pytest.raises(B.BIDResponseError) as excinfo:
        B.parse_bid_envelope({"errorCode": 6, "message": "no such BID"}, DID)
    assert excinfo.value.code == 6 and excinfo.value.not_found
    assert "no such BID" in str(excinfo.value)


def test_error_code_must_be_an_int():
    for bad in ("0", True, 0.0):
        with pytest.raises(B.BIDResponseError) as excinfo:
            B.parse_bid_envelope({"errorCode": bad, "id": DID}, DID)
        assert excinfo.value.code == -1


def test_a_payload_without_a_document_is_a_document_error():
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_envelope({"errorCode": 0}, DID)
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_envelope(["not", "a", "dict"], DID)


# ------------------------------------------------------------- document model
def test_document_id_must_match_the_request():
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(id="did:bid:efOther"), DID)


def test_duplicate_public_key_ids_are_refused():
    doc = _doc(publicKey=[_doc()["publicKey"][0], dict(_doc()["publicKey"][0])])
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(doc, DID)


def test_authentication_may_not_name_an_undefined_key():
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(authentication=[DID + "#key-9"]), DID)


def test_public_key_controller_must_itself_be_a_bid():
    keys = [dict(_doc()["publicKey"][0], controller="did:web:example.com")]
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(publicKey=keys), DID)


def test_public_key_hex_must_be_hex():
    keys = [dict(_doc()["publicKey"][0], publicKeyHex="zz")]
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(publicKey=keys), DID)


def test_also_known_as_type_is_an_int_from_appendix_one():
    ok = B.parse_bid_document(_doc(alsoKnownAs=[{"type": 101, "id": DID}]), DID)
    assert ok.also_known_as[0]["type"] == 101
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(alsoKnownAs=[{"type": "101", "id": DID}]), DID)


def test_unknown_extensible_codes_warn_instead_of_rejecting():
    parsed = B.parse_bid_document(_doc(extension={"ttl": 1, "type": 777}), DID)
    assert any("777" in w for w in parsed.warnings)


def test_ttl_must_be_a_non_negative_int():
    for bad in ("86400", -1, 1.5, True):
        with pytest.raises(B.BIDDocumentError):
            B.parse_bid_document(_doc(extension={"ttl": bad}), DID)


def test_attribute_encrypt_is_zero_or_one():
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(extension={"attributes": [{"key": "k", "value": "v", "encrypt": 2}]}), DID)


def test_sub_chain_service_entry_needs_an_endpoint_and_a_known_transport():
    good = {"id": DID + "#sub", "type": "DIDSubResolver", "protocol": 2,
            "serviceEndpoint": "http://sub.example.com/"}
    assert B.parse_bid_document(_doc(service=[good]), DID).sub_chain_service() == good
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(service=[dict(good, serviceEndpoint=None)]), DID)
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(service=[dict(good, protocol=9)]), DID)


def test_timestamps_are_iso_8601():
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(created="2021-06-24"), DID)


def test_proof_creator_must_be_a_key_of_this_document():
    proof = {"creator": DID + "#key-9", "signatureValue": "3yZe7d"}
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(proof=proof), DID)


def test_proof_signature_must_be_base58():
    proof = {"creator": KEY_ID, "signatureValue": "0OIl-not-base58"}
    with pytest.raises(B.BIDDocumentError):
        B.parse_bid_document(_doc(proof=proof), DID)


def test_ac_code_reads_only_a_four_character_sub_chain_head():
    assert B.BIDDocument(id=DID, raw={}).ac_code is None
    assert B.BIDDocument(id="did:bid:AC01:ef18F9AVK4SQLZPRrPkrVWwp9kbpdXHx", raw={}).ac_code == "AC01"


# ------------------------------------------------------------ DID Core投影
def test_projection_keeps_every_bid_specific_field():
    parsed = B.parse_bid_document(_doc(alsoKnownAs=[{"type": 104, "id": "zid:abc"}]), DID)
    core = parsed.to_did_core()
    assert core["id"] == DID and core["@context"] == ["https://www.w3.org/ns/did/v1"]
    assert core["verificationMethod"][0]["type"] == "Ed25519VerificationKey2020"
    assert core["authentication"] == [KEY_ID]
    assert core["alsoKnownAs"] == ["zid:abc"]
    assert core["extension"]["ttl"] == 86400


# ---------------------------------------------------------------- §5 signing
def test_base58_round_trips_including_leading_zero_bytes():
    for raw in (b"", b"\x00", b"\x00\x00\x01", bytes(range(32)), b"\xff" * 64):
        assert B.base58_decode(B.base58_encode(raw)) == raw
    assert B.base58_encode(b"\x00\x01") == "12"


def test_base58_rejects_a_character_outside_the_alphabet():
    with pytest.raises(B.BIDDocumentError):
        B.base58_decode("abc0")


def test_sign_then_verify_round_trip():
    seed, hexed = B.generate_ed25519_pair()
    doc = _doc(publicKey=[dict(_doc()["publicKey"][0], publicKeyHex=hexed)])
    signed = B.sign_bid_document(doc, seed, KEY_ID)
    ok, reason = B.verify_bid_document(signed, DID)
    assert ok, reason


def test_any_tampered_field_breaks_the_signature():
    seed, hexed = B.generate_ed25519_pair()
    doc = _doc(publicKey=[dict(_doc()["publicKey"][0], publicKeyHex=hexed)])
    signed = B.sign_bid_document(doc, seed, KEY_ID)
    tampered = dict(signed, extension={"ttl": 86401, "type": 105})
    assert B.verify_bid_document(tampered, DID)[0] is False


def test_signing_bytes_are_independent_of_key_order():
    seed, hexed = B.generate_ed25519_pair()
    doc = _doc(publicKey=[dict(_doc()["publicKey"][0], publicKeyHex=hexed)])
    signed = B.sign_bid_document(doc, seed, KEY_ID)
    reordered = {k: signed[k] for k in reversed(list(signed))}
    assert B.verify_bid_document(reordered, DID)[0] is True


def test_a_proof_naming_a_non_authentication_key_is_not_accepted():
    seed, hexed = B.generate_ed25519_pair()
    key2 = DID + "#key-2"
    doc = _doc(
        publicKey=[
            dict(_doc()["publicKey"][0], publicKeyHex=hexed),
            {"controller": DID, "id": key2, "publicKeyHex": hexed, "type": "ED25519"},
        ],
        authentication=[KEY_ID],
    )
    signed = B.sign_bid_document(doc, seed, key2)
    ok, reason = B.verify_bid_document(signed, DID)
    assert ok is False and "authentication" in reason


def test_a_sm2_document_is_reported_unverifiable_not_silently_accepted():
    doc = _doc(publicKey=[dict(_doc()["publicKey"][0], type="SM2",
                              publicKeyHex="04" + "ab" * 32)])
    signed = B.sign_bid_document(doc, b"\x01" * 32, KEY_ID)
    ok, reason = B.verify_bid_document(signed, DID)
    assert ok is False and "Ed25519" in reason


# --------------------------------------------------------- §4.2.1 / §4.2.3 解析
def test_transient_codes_are_retried_and_missing_ids_are_not():
    calls = []

    def fetcher(url, timeout=10):
        calls.append(url)
        return {"errorCode": 3 if len(calls) == 1 else 0, "data": {"didDocument": _doc()}}

    parsed = B.resolve_bid("http://resolver.example", DID, fetcher=fetcher)
    assert isinstance(parsed, B.BIDDocument)
    assert len(calls) == 2, "code 3 must be retried exactly once more"
    assert calls[0].endswith("/" + DID), "the URL is {endpoint}/{did} per §4.2.1"


def test_not_found_is_not_retried():
    calls = []

    def fetcher(url, timeout=10):
        calls.append(url)
        return {"errorCode": 6}

    with pytest.raises(B.BIDResponseError) as excinfo:
        B.resolve_bid("http://resolver.example", DID, fetcher=fetcher)
    assert excinfo.value.code == 6 and len(calls) == 1


def test_transient_codes_give_up_after_the_retry_budget():
    def fetcher(url, timeout=10):
        return {"errorCode": 7}

    with pytest.raises(B.BIDResponseError) as excinfo:
        B.resolve_bid("http://resolver.example", DID, fetcher=fetcher, retries=2)
    assert excinfo.value.code == 7


def test_sub_chain_recursion_follows_the_service_entry():
    sub_endpoint = "http://sub.example.com/"
    leaf = _doc()

    def fetcher(url, timeout=10):
        if url.startswith("http://main.example"):
            return {"errorCode": 0, "data": {"didDocument": _doc(
                service=[{"id": DID + "#sub", "type": "DIDSubResolver", "protocol": 2,
                          "serviceEndpoint": sub_endpoint}])}}
        return {"errorCode": 0, "data": {"didDocument": leaf}}

    parsed = B.resolve_bid_chain("http://main.example", DID, fetcher=fetcher)
    assert parsed.raw == leaf and parsed.sub_chain_service() is None


def test_sub_chain_cycle_is_detected_rather_than_looping():
    main = "http://main.example"
    sub = "http://sub.example.com"

    def fetcher(url, timeout=10):
        target = sub if url.startswith(main) else main
        return {"errorCode": 0, "data": {"didDocument": _doc(
            service=[{"id": DID + "#sub", "type": "DIDSubResolver", "protocol": 2,
                      "serviceEndpoint": target}])}}

    with pytest.raises(B.BIDProtocolError) as excinfo:
        B.resolve_bid_chain(main, DID, fetcher=fetcher, max_hops=3)
    assert "cycle" in str(excinfo.value)


def test_sub_chain_hop_budget_terminates_a_long_chain():
    def fetcher(url, timeout=10):
        n = int(url.split("/")[-2])
        return {"errorCode": 0, "data": {"didDocument": _doc(
            service=[{"id": DID + "#sub", "type": "DIDSubResolver", "protocol": 2,
                      "serviceEndpoint": "http://hop.example/%d" % (n + 1)}])}}

    with pytest.raises(B.BIDProtocolError) as excinfo:
        B.resolve_bid_chain("http://hop.example/0", DID, fetcher=fetcher, max_hops=2)
    assert "hops" in str(excinfo.value)


def test_binary_resolution_is_refused_with_the_protocol_code_five():
    with pytest.raises(B.BIDResponseError) as excinfo:
        B.refuse_binary_resolution(DID)
    assert excinfo.value.code == 5
    assert excinfo.value.name == "operation not supported"
