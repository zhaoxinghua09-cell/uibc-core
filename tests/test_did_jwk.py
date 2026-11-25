"""did:jwk 的解析：文档就是标识本身，所以两件事必须钉死。

一、**私钥不许出现在标识里**。`d` / `p` / `q` / `k` 这些成员只属于私钥；
   一个 DID 文档如果把它们原样放出来，解析器就成了密钥泄漏的搬运工。
二、**绑定是算术，不是背书**。did:jwk 能到 VERIFIED，是因为公钥字节就在
   标识里、可复算；这与注册中心那类"调用方给端点"的方法不是同一句话。
"""
import base64
import json

import pytest

from uibc_core import did, identity_adapter as ia

ED25519_X = "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"   # 32-byte ed25519 public key, base64url


def _b64url(obj):
    blob = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(blob).decode().rstrip("=")


def test_ed25519_jwk_resolves_to_a_document_with_the_same_id():
    jwk = {"kty": "OKP", "crv": "Ed25519", "x": ED25519_X}
    d = "did:jwk:" + _b64url(jwk)
    doc = did.resolve(d)
    assert doc["id"] == d
    assert doc["verificationMethod"][0]["publicKeyJwk"] == jwk
    key, kid = did.document_ed25519_key(doc)
    assert len(key) == 32 and kid == d + "#0"


def test_resolution_needs_no_network():
    """给一个必然失败的 fetcher：did:jwk 不该碰它，碰了就是设计错了。"""
    def bomb(*_a, **_k):
        raise AssertionError("did:jwk must not fetch anything")

    jwk = {"kty": "OKP", "crv": "Ed25519", "x": ED25519_X}
    assert did.resolve("did:jwk:" + _b64url(jwk), fetcher=bomb)["id"].startswith("did:jwk:")


@pytest.mark.parametrize("member", ["d", "p", "q", "dp", "dq", "qi", "k"])
def test_private_key_members_are_refused_not_published(member):
    jwk = {"kty": "OKP", "crv": "Ed25519", "x": ED25519_X, member: "AAAA"}
    with pytest.raises(did.DIDError) as exc:
        did.resolve("did:jwk:" + _b64url(jwk))
    assert "private key" in str(exc.value)


def test_non_json_and_non_object_segments_are_refused():
    with pytest.raises(did.DIDError):
        did.resolve("did:jwk:bm90LWpzb24")                 # "not-json"
    with pytest.raises(did.DIDError):
        did.resolve("did:jwk:" + _b64url(["kty", "OKP"]))  # array, not object


def test_jwk_without_kty_is_refused():
    with pytest.raises(did.DIDError) as exc:
        did.resolve("did:jwk:" + _b64url({"crv": "Ed25519", "x": ED25519_X}))
    assert "kty" in str(exc.value)


def test_oversized_jwk_is_refused():
    big = {"kty": "OKP", "crv": "Ed25519", "x": ED25519_X, "note": "a" * 5000}
    with pytest.raises(did.DIDError) as exc:
        did.resolve("did:jwk:" + _b64url(big))
    assert "cap" in str(exc.value)


def test_adapter_says_verified_for_ed25519_and_inconclusive_for_other_key_types():
    ed = ia.check("did:jwk:" + _b64url({"kty": "OKP", "crv": "Ed25519", "x": ED25519_X}))
    assert ed.state == "VERIFIED" and len(ed.document_sha256) == 64

    # P-256 的文档照样能解出来，但本仓的 ed25519 提取器读不出它：
    # 这时该说的话是"文档拿到了，键没提取出来"，不是"通过"，也不是"标识错了"。
    p256 = ia.check("did:jwk:" + _b64url({"kty": "EC", "crv": "P-256",
                                          "x": ED25519_X, "y": ED25519_X}))
    assert p256.state == "INCONCLUSIVE"


def test_did_jwk_is_listed_as_supported_and_jwk_is_not():
    assert "jwk" in did.SUPPORTED_METHODS
    with pytest.raises(did.UnsupportedMethod):
        did.resolve("did:ethr:0xabc")
