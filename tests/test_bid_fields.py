"""§4.2.2 field-level resolution: the five field endpoints and their shapes.

The shapes are the protocol's, including the asymmetry that `public-keys`
returns an array while `public-keys/{id}` returns a single object.
"""

import pytest

from uibc_core import bid_protocol as B

DID = "did:bid:ef18F9AVK4SQLZPRrPkrVWwp9kbpdXHx"
KEY1 = DID + "#key-1"
KEY2 = DID + "#key-2"
EP = "http://resolver.example"
BARE_HEX = "b9906e1b50e81501369cc777979f8bcf27bd1917d794fa6d5e320b1ccc4f48bb"   # protocol's own example


def fetcher_for(routes, calls=None):
    def fetcher(url, timeout=10):
        if calls is not None:
            calls.append(url)
        for suffix, answer in routes.items():
            if suffix in url:
                return answer
        raise AssertionError("unexpected url %r" % (url,))
    return fetcher


def ok(data):
    return {"errorCode": 0, "message": "success", "data": data}


# --------------------------------------------------------- §4.2.2.1 公钥
def test_all_public_keys_is_a_list():
    data = {"version": "1.0.0", "id": DID, "publicKey": [
        {"id": KEY1, "type": "Ed25519", "controller": DID, "publicKeyHex": BARE_HEX},
        {"id": KEY2, "type": "Ed25519", "controller": DID, "publicKeyHex": "02b97c30" + BARE_HEX[8:]},
    ]}
    keys = B.resolve_public_keys(EP, DID, fetcher=fetcher_for({"/public-keys": ok(data)}))
    assert len(keys) == 2 and keys[0]["id"] == KEY1
    assert "$" not in "".join(keys[0].keys())


def test_one_public_key_is_an_object_not_a_one_item_list():
    data = {"version": "1.0.0", "id": DID,
            "publicKey": {"id": KEY1, "type": "Ed25519", "controller": DID, "publicKeyHex": BARE_HEX}}
    key = B.resolve_public_keys(EP, DID, key_id=KEY1,
                               fetcher=fetcher_for({"/public-keys/": ok(data)}))
    assert key["id"] == KEY1


def test_one_public_key_returned_as_a_list_is_refused():
    """The two shapes are different answers; collapsing them hides a real defect."""
    data = {"version": "1.0.0", "id": DID, "publicKey": [
        {"id": KEY1, "type": "Ed25519", "controller": DID, "publicKeyHex": BARE_HEX}]}
    with pytest.raises(B.BIDDocumentError):
        B.resolve_public_keys(EP, DID, key_id=KEY1, fetcher=fetcher_for({"/public-keys/": ok(data)}))


def test_the_key_id_is_percent_encoded_in_the_path():
    calls = []
    data = {"version": "1.0.0", "id": DID,
            "publicKey": {"id": KEY1, "type": "Ed25519", "controller": DID, "publicKeyHex": BARE_HEX}}
    B.resolve_public_keys(EP, DID, key_id=KEY1, fetcher=fetcher_for({"/public-keys/": ok(data)}, calls))
    assert calls[0].endswith("/public-keys/did%3Abid%3Aef18F9AVK4SQLZPRrPkrVWwp9kbpdXHx%23key-1")


def test_a_key_id_from_another_bid_is_refused():
    data = {"version": "1.0.0", "id": DID,
            "publicKey": {"id": "did:bid:efOther#key-1", "type": "Ed25519", "publicKeyHex": BARE_HEX}}
    with pytest.raises(B.BIDDocumentError):
        B.resolve_public_keys(EP, DID, key_id=KEY1, fetcher=fetcher_for({"/public-keys/": ok(data)}))


# -------------------------------------------------------- §4.2.2.2 属性
def test_attributes_carry_key_and_a_boolean_encrypt():
    data = {"version": "1.0.0", "id": DID,
            "attributes": [{"key": "contract", "encrypt": 1, "format": "text", "value": "did:bid:efX"}]}
    attrs = B.resolve_attributes(EP, DID, fetcher=fetcher_for({"/attributes": ok(data)}))
    assert attrs[0]["key"] == "contract"


def test_an_attribute_without_key_is_refused():
    with pytest.raises(B.BIDDocumentError):
        B.resolve_attributes(EP, DID, fetcher=fetcher_for(
            {"/attributes": ok({"version": "1.0.0", "id": DID, "attributes": [{"value": 1}]})}))


def test_encrypt_outside_zero_one_is_refused():
    with pytest.raises(B.BIDDocumentError):
        B.resolve_attributes(EP, DID, fetcher=fetcher_for(
            {"/attributes": ok({"version": "1.0.0", "id": DID,
                                "attributes": [{"key": "k", "encrypt": 2}]})}))


# ------------------------------------------------------- §4.2.2.3 AC 号
def test_ac_codes_are_four_characters_each():
    data = {"version": "1.0.0", "id": DID, "acsns": ["abcd", "1234"]}
    assert B.resolve_acsns(EP, DID, fetcher=fetcher_for({"/acsns": ok(data)})) == ["abcd", "1234"]


# ----------------------------------------------------- §4.2.2.4 凭证列表
def test_credentials_are_a_list_of_id_type_objects():
    data = {"version": "1.0.0", "id": DID,
            "verifiableCredentials": [{"id": "did:bid:efCred", "type": 202}]}
    creds = B.resolve_credentials(EP, DID, fetcher=fetcher_for({"/verifiableCredentials": ok(data)}))
    assert creds[0]["type"] == 202


# ----------------------------------------------------- §4.2.2.5 服务地址
def test_service_lookup_uses_a_real_query_string_and_matches_the_id():
    calls = []
    sid = DID + "#storage"
    data = {"version": "1.0.0", "id": DID,
            "service": {"id": sid, "type": "DIDStorage", "serviceEndpoint": "https://did.bif.com"}}
    svc = B.resolve_service(EP, DID, sid, fetcher=fetcher_for({"/services?id=": ok(data)}, calls))
    assert svc["serviceEndpoint"] == "https://did.bif.com"
    assert "?" in calls[0] and "？" not in calls[0], "the protocol prints a full-width ？; the wire form is ?"


def test_a_service_reply_about_another_id_is_refused():
    sid = DID + "#storage"
    data = {"version": "1.0.0", "id": DID,
            "service": {"id": DID + "#other", "type": "DIDStorage", "serviceEndpoint": "https://x"}}
    with pytest.raises(B.BIDDocumentError):
        B.resolve_service(EP, DID, sid, fetcher=fetcher_for({"/services?id=": ok(data)}))


# ------------------------------------------------------------- 共同判据
def test_a_field_answer_about_another_bid_is_refused():
    with pytest.raises(B.BIDDocumentError):
        B.resolve_acsns(EP, DID, fetcher=fetcher_for(
            {"/acsns": ok({"version": "1.0.0", "id": "did:bid:efOther", "acsns": []})}))


def test_not_found_is_carried_as_code_six_and_not_retried():
    calls = []
    with pytest.raises(B.BIDResponseError) as excinfo:
        B.resolve_acsns(EP, DID, fetcher=fetcher_for({"/acsns": {"errorCode": 6, "message": "not found"}}, calls))
    assert excinfo.value.code == 6 and excinfo.value.not_found and len(calls) == 1


def test_a_transient_field_answer_is_retried():
    seq = [{"errorCode": 3}, {"errorCode": 0, "data": {"version": "1.0.0", "id": DID, "acsns": ["abcd"]}}]

    def fetcher(url, timeout=10):
        return seq.pop(0)

    assert B.resolve_acsns(EP, DID, fetcher=fetcher) == ["abcd"]
