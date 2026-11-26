"""Offline tests for the AITB open evaluation entry.

Nothing here touches the network: the gates are pure functions of a recorded
response, which is the property that makes the card re-checkable by an outsider.
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.aitb_evaluate import gate1, gate2, gate3, check_report, did_slug, evaluate, method_of

GOOD = {"http": 200, "doc": {"success": True, "code": 0, "data": {
    "summary": {"resolutionStatus": "SUCCESS", "vcVerificationStatus": "SKIPPED",
                "isTrustEstablished": True},
    "identity": {"id": "did:cn:agent:abc", "controller": "did:cn:agent:abc",
                 "publicKeyType": "EcdsaSecp256k1VerificationKey2019",
                 "publicKey": "03" + "ab" * 32, "agentStatus": "RUNNING"},
    "capabilities": {"serviceEndpoint": ["https://ai.example.com/a2a"]},
    "registration": {"registrationNodeDid": "did:bid:agentnode:xyz"}}}}


def test_gate1_good():
    assert all(c["ok"] for c in gate1(GOOD))


def test_gate1_unreachable():
    checks = gate1({"http": 503, "doc": {"_unparsed_head": "busy"}})
    assert checks[0]["ok"] is False and checks[-1]["detail"].startswith("resolutionStatus=")


def test_gate2_good_passes_all():
    checks = gate2(GOOD, "did:cn:agent:abc")
    assert len(checks) == 9 and all(c["ok"] for c in checks)


def test_gate2_catches_short_key():
    bad = json.loads(json.dumps(GOOD))
    bad["doc"]["data"]["identity"]["publicKey"] = "03" + "ab" * 16
    failed = [c["id"] for c in gate2(bad, "did:cn:agent:abc") if not c["ok"]]
    assert failed == ["G2.key_hex_len"]


def test_gate2_catches_id_mismatch_and_trust_contradiction():
    bad = json.loads(json.dumps(GOOD))
    bad["doc"]["data"]["identity"]["id"] = "did:cn:agent:other"
    bad["doc"]["data"]["summary"]["resolutionStatus"] = "FAILED"
    failed = {c["id"] for c in gate2(bad, "did:cn:agent:abc") if not c["ok"]}
    assert failed == {"G2.id_echo", "G2.trust_matches_status"}


def test_gate3_absent_is_missing_not_pass():
    assert gate3(None)[0]["ok"] is None
    assert gate3("https://example.com/x")[0]["ok"] is True


def test_method_parse():
    assert method_of("did:ctid:anicert") == "ctid"
    assert method_of("did:cn:agent:abc") == "cn"
    assert method_of("not-a-did") == ""
    assert method_of("did:web:example.com") == "web"


def test_ctid_is_no_public_endpoint_and_calls_nothing():
    rep = evaluate("did:ctid:anicert")            # no network: the method is routed away
    assert rep["verdict"] == "NO_PUBLIC_ENDPOINT"
    assert rep["counts"]["ran"] == 0
    assert "ctid" in rep["gates"][0]["detail"] or "SDK" in rep["gates"][0]["detail"]


def test_unknown_method_is_named_not_blamed():
    rep = evaluate("did:example:xyz")
    assert rep["verdict"] == "METHOD_NOT_SUPPORTED"
    assert rep["counts"]["ran"] == 0


def test_slug_is_filesystem_safe():
    assert did_slug("did:cn:agent:a/b") == "did_cn_agent_a_b"


def test_example_report_checks_clean():
    rep = os.path.join(os.path.dirname(__file__), "..", "docs", "aitb-example-report.json")
    assert check_report(rep) == []


def test_no_endpoint_example_checks_clean():
    rep = os.path.join(os.path.dirname(__file__), "..", "docs", "aitb-example-no-endpoint.json")
    assert check_report(rep) == []
