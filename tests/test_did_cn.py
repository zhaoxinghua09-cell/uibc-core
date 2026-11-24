"""Tests for the six China-registry DID methods (uibc_core/did_cn.py).

Every positive identifier is copied from the published specification; every
negative one is a string the ABNF must reject. No network: registry reads go
through an injected fetcher.
"""

import pytest

from uibc_core import did
from uibc_core import did_cn


# --------------------------------------------------------------------------- #
# did:cn  (CAICT / Astron)  issuer "." industry "." enterprise
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value", [
    "did:cn:88.100.1",          # spec example
    "did:cn:88.100.12345",      # spec create example
    "did:cn:11.12345.9",        # industry at the 5-digit bound
])
def test_cn_accepts_spec_examples(value):
    method, level, details = did_cn.validate(value)
    assert method == "cn"
    assert level == "registry"
    assert details["issuer"] == value.split(":")[2].split(".")[0]


@pytest.mark.parametrize("value", [
    "did:cn:8.100.1",           # issuer must be exactly 2 digits
    "did:cn:88.100",            # no enterprise segment
    "did:cn:88.100.1.2",        # enterprise must be a single numeric run
    "did:cn:88.100.",           # empty enterprise
    "did:cn:88.100000.1",       # industry longer than 5 digits
])
def test_cn_rejects_out_of_grammar(value):
    with pytest.raises(did_cn.IdentifierError):
        did_cn.validate(value)


# --------------------------------------------------------------------------- #
# did:ctid  (anicert)  64 uppercase hex
# --------------------------------------------------------------------------- #
def test_ctid_spec_example_is_identifier_only():
    value = "did:ctid:16D44117484372A2D010BDAA56703E723FB4C5C06CA44105F0C9C5B8020A7073"
    method, level, details = did_cn.validate(value)
    assert method == "ctid" and level == "identifier_only"
    with pytest.raises(did_cn.DIDCNError):
        did_cn.resolve(value)


@pytest.mark.parametrize("value", [
    "did:ctid:16d44117484372a2d010bdaa56703e723fb4c5c06ca44105f0c9c5b8020a7073",  # lowercase
    "did:ctid:16D44117484372A2D010BDAA56703E723FB4C5C06CA44105F0C9C5B8020A707",    # 63 hex
    "did:ctid:16D44117484372A2D010BDAA56703E723FB4C5C06CA44105F0C9C5B8020A7073X",  # non-hex
])
def test_ctid_rejects_case_and_length(value):
    with pytest.raises(did_cn.IdentifierError):
        did_cn.validate(value)


# --------------------------------------------------------------------------- #
# did:ioa / did:cndid  (teleinfo CAICT / TChain)
# --------------------------------------------------------------------------- #
def test_ioa_spec_example_parses_secp256k1():
    value = "did:ioa:sfHBuFa7asqWztQJ3nZUiHtXjSJsyqEp"   # spec example
    method, level, details = did_cn.validate(value)
    assert method == "ioa"
    assert level == "registry"
    assert details["crypto"] == "secp256k1"
    assert details["encoding"] == "base58"
    # the spec does not fix the byte count, so we record and never assert it
    assert len(details["key"]) == 22
    assert did_cn.derivable_document(value) is None


def test_ioa_acsn_only_resolver_did():
    method, level, details = did_cn.validate("did:ioa:tele")
    assert method == "ioa" and details["crypto"] is None  # spec 3.1: acsn-only


def test_cndid_spec_example_is_registry_level_not_offline():
    value = "did:cndid:efnVUgqQFfYeu97ABf6sGm3WFtVXHZB2"  # spec 4.2 example
    method, level, details = did_cn.validate(value)
    assert level == "registry"
    assert details["crypto"].startswith("Ed25519")
    assert len(details["key"]) == 22                      # 30-char base58 body
    # therefore no document can be derived from this identifier alone
    assert did_cn.derivable_document(value) is None
    with pytest.raises(did_cn.RegistryEndpointRequired):
        did.resolve(value)


@pytest.mark.parametrize("value", [
    "did:cndid:abcdef",                            # suffix shorter than 22
    "did:cndid:xfHBuFa7asqWztQJ3nZUiHtXjSJsyqEp",  # algorithm letter not in {z,e,s}
    "did:cndid:szHBuFa7asqWztQJ3nZUiHtXjSJsyqEp",  # encoding letter not in {f,s,t}
    "did:cndid:ef",                                # no key body
])
def test_ioa_cndid_reject_bad_suffix(value):
    with pytest.raises(did_cn.IdentifierError):
        did_cn.validate(value)


# --------------------------------------------------------------------------- #
# did:oan  (OpenAgenet)  did:oan:<5 base58>:<32 base58>
# --------------------------------------------------------------------------- #
def test_oan_spec_example():
    value = "did:oan:2Xr85:7YpQm9Kx2VnRb6Ts3WfHa4Cd5Ej8LgNz"
    method, level, details = did_cn.validate(value)
    assert method == "oan" and level == "identifier_only"
    assert len(value) == 46                                  # spec: canonical length 46
    assert details["routing_code"] == "2Xr85"


@pytest.mark.parametrize("value", [
    "did:oan:2Xr8:7YpQm9Kx2VnRb6Ts3WfHa4Cd5Ej8LgNz",        # routing 4 chars
    "did:oan:2Xr850:7YpQm9Kx2VnRb6Ts3WfHa4Cd5Ej8LgNz",      # routing 6 chars
    "did:oan:2Xr85:7YpQm9Kx2VnRb6Ts3WfHa4Cd5Ej8LgN",        # suffix 31 chars
    "did:oan:2Xr85:0YpQm9Kx2VnRb6Ts3WfHa4Cd5Ej8LgNz",       # '0' outside base58
])
def test_oan_rejects_out_of_grammar(value):
    with pytest.raises(did_cn.IdentifierError):
        did_cn.validate(value)


# --------------------------------------------------------------------------- #
# did:cndomain  (CNNIC working draft)  lowercase <label.>+.cn[:type:name]
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value", [
    "did:cndomain:example.cn",
    "did:cndomain:sub.example.cn",
    "did:cndomain:example.cn:page:home",
    "did:cndomain:example-1.cn:agent:node-7",
])
def test_cndomain_accepts_lowercase_cn(value):
    method, level, details = did_cn.validate(value)
    assert method == "cndomain" and level == "registry"
    assert details["domain"].endswith(".cn")


@pytest.mark.parametrize("value", [
    "did:cndomain:example.com",          # not a .cn domain
    "did:cndomain:Example.cn",           # uppercase rejected by the draft
    "did:cndomain:example.cn:onlytype",  # object type without object name
    "did:cndomain:.cn",                  # empty label
])
def test_cndomain_rejects_out_of_grammar(value):
    with pytest.raises(did_cn.IdentifierError):
        did_cn.validate(value)


# --------------------------------------------------------------------------- #
# registry resolution: the endpoint is never defaulted
# --------------------------------------------------------------------------- #
def test_registry_method_without_endpoint_refuses():
    with pytest.raises(did_cn.RegistryEndpointRequired):
        did_cn.resolve("did:cn:88.100.1")


def test_cn_uses_get_resolve_shape_from_spec():
    calls = []

    def fetcher(url, timeout):
        calls.append((url, timeout))
        return {"id": "did:cn:88.100.1", "verificationMethod": []}

    doc = did_cn.resolve("did:cn:88.100.1", endpoint="https://registry.example",
                         fetcher=fetcher)
    assert doc["id"] == "did:cn:88.100.1"
    assert calls[0][0] == "https://registry.example/did/resolve/did:cn:88.100.1"


def test_ioa_reads_operation_envelope():
    def fetcher(url, timeout):
        return {"code": 0, "data": {"didDocument": {
            "id": "did:ioa:sfHBuFa7asqWztQJ3nZUiHtXjSJsyqEp"}}}

    doc = did_cn.resolve("did:ioa:sfHBuFa7asqWztQJ3nZUiHtXjSJsyqEp",
                         endpoint="https://chain.example/node", fetcher=fetcher)
    assert doc["id"].startswith("did:ioa:")


def test_registry_document_id_must_match():
    def fetcher(url, timeout):
        return {"id": "did:cn:88.100.2"}

    with pytest.raises(did_cn.DIDCNError):
        did_cn.resolve("did:cn:88.100.1", endpoint="https://registry.example",
                       fetcher=fetcher)


# --------------------------------------------------------------------------- #
# the matrix we publish
# --------------------------------------------------------------------------- #
def test_matrix_covers_the_six_methods_with_honest_levels():
    rows = did_cn.matrix()
    assert {r["method"] for r in rows} == {
        "did:cn", "did:ioa", "did:cndid", "did:ctid", "did:oan", "did:cndomain"}
    by_method = {r["method"]: r for r in rows}
    assert by_method["did:ctid"]["resolution"].startswith("none published")
    assert by_method["did:oan"]["resolution"].startswith("none published")
    assert by_method["did:cndid"]["offline_document_when_key_is_byte_exact"] is True
    assert by_method["did:cndid"]["level"] == "registry"
    assert by_method["did:cn"]["resolution"] == "endpoint required"
    for r in rows:
        assert r["specification"].startswith("https://")


def test_ed25519_suffix_with_full_32_byte_key_is_unreachable_by_the_abnf():
    """A whole Ed25519 key cannot fit the published suffix, and we say so."""
    key = bytes(range(32))
    body = did._b58encode(key)
    value = "did:cndid:ef" + body
    assert len(body) > 40                      # 43-44 chars for 32 bytes
    with pytest.raises(did_cn.IdentifierError):
        did_cn.validate(value)
