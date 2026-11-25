"""did:bid（星火·链网 BID）的标识规则：两个形状，其中一个允许空后缀。

BID 的 ABNF 抄自 teleinfo/CAICT 的 BID Protocol Specification：

    bid-specific-identifier = 0*1(acsn ":") suffix / acsn ":" 0*1(suffix)
    acsn   = 4(ALPHA / DIGIT)
    suffix = (22,42)(ALPHA / DIGIT)

第二支允许 **空后缀**，那是 `did:bid:byol` 那种"侧链解析服务"的形态，不是笔误。
所以这里不能用一个正则糊过去，两种形状必须分开判。

判据边界：注册中心类方法里，`did:bid` 的 `read` 是 HTTP GET，端点由调用方给；
我们绝不默认一个 URL——猜错会给出看起来权威的错误答案。
"""
import pytest

from uibc_core import did_cn, identity_adapter as ia

MAIN = "did:bid:efnVUgqQFfYeu97ABf6sGm3WFtVXHZB2"          # spec 里的官方示例
SUB = "did:bid:AC01:efnVUgqQFfYeu97ABf6sGm3WFtVXHZB2"
BYOL = "did:bid:byol"                                       # 允许空后缀的侧链形态


def test_main_chain_example_from_the_spec_validates():
    method, level, details = did_cn.validate(MAIN)
    assert method == "bid" and level == "registry"
    assert details["shape"] == "main"
    assert details["crypto"] == "Ed25519"      # 'e' 按规范的加密算法表
    assert details["encoding"] == "base58"     # 'f' 按规范的编码表
    assert details["offline_document"] is False


def test_sub_chain_form_and_the_empty_suffix_form_both_validate():
    assert did_cn.validate(SUB)[2]["shape"] == "sub"
    assert did_cn.validate(BYOL)[2]["shape"] == "byol"   # spec 3.1 明列的例外，不硬塞进 ABNF
    # 规范里那支 `acsn ":" 0*1(suffix)` 允许空后缀，但 DID Core 的 method-specific-id
    # 必须由 idchar 结尾，所以 `did:bid:AC01:` 在解析层就被拒。两套 ABNF 在这里不一致，
    # 我们按 DID Core 来（否则会接受一个不是 DID 的字符串），并把这条冲突记在此处。
    import pytest as _pytest
    with _pytest.raises(Exception):
        did_cn.validate("did:bid:AC01:")


@pytest.mark.parametrize("bad", [
    "did:bid:",                      # 没有 identifier
    "did:bid:efshort",               # 后缀不足 22 字符
    "did:bid:AC01:efshort",          # 子链形式的后缀同样要够 22 字符
    "did:bid:AC:efnVUgqQFfYeu97ABf6sGm3WFtVXHZB2",   # AC 码必须 4 位
    "did:bid:a:b:c",                 # 标识内最多一个冒号
    "did:bid:efnVUgqQFfYeu97ABf6sGm3WFtVXHZB2#key-1",  # 片段不属于标识本身
])
def test_shapes_that_do_not_match_the_abnf_are_refused(bad):
    with pytest.raises(Exception) as exc:   # 解析层抛 did.DIDError，规则层抛 IdentifierError
        did_cn.validate(bad)
    assert type(exc.value).__name__ in ("IdentifierError", "DIDError")


def test_no_endpoint_means_unresolved_never_a_guessed_url():
    with pytest.raises(did_cn.RegistryEndpointRequired):
        did_cn.resolve(MAIN)
    assert ia.check(MAIN).state == "UNRESOLVED"


def test_read_returns_the_document_when_the_id_matches():
    doc = {"id": MAIN, "publicKey": [], "authentication": []}

    def fetcher(url, timeout):
        assert url.endswith(MAIN)
        return doc

    assert did_cn.resolve(MAIN, endpoint="https://bif.example", fetcher=fetcher) == doc


def test_read_accepts_the_nested_data_didDocument_envelope():
    doc = {"id": MAIN, "publicKey": [], "authentication": []}

    def fetcher(url, timeout):
        return {"errorCode": 0, "data": {"didDocument": doc}}

    assert did_cn.resolve(MAIN, endpoint="https://bif.example", fetcher=fetcher) == doc


def test_a_document_answering_for_another_id_is_refused():
    def fetcher(url, timeout):
        return {"id": "did:bid:efTtY5Gr73N1cdjeKrx4mA3LGRSrLTeR"}

    with pytest.raises(did_cn.DIDCNError) as exc:
        did_cn.resolve(MAIN, endpoint="https://bif.example", fetcher=fetcher)
    assert "does not match" in str(exc.value)


def test_registry_error_code_is_surfaced_not_swallowed():
    def fetcher(url, timeout):
        return {"errorCode": 404, "message": "not found"}

    with pytest.raises(did_cn.DIDCNError) as exc:
        did_cn.resolve(MAIN, endpoint="https://bif.example", fetcher=fetcher)
    assert "errorCode" in str(exc.value)


def test_matrix_lists_bid_as_a_registry_method():
    row = [r for r in did_cn.matrix() if r["method"] == "did:bid"][0]
    assert row["level"] == "registry"
    assert row["resolution"] == "endpoint required"
    assert "teleinfo-bif/bid" in row["specification"]
