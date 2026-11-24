"""The interoperability result vocabulary: seven states, and one strict rule.

These tests exist to keep two promises checkable:

1. the seven states are one closed list, shared by code and by the JSON Schema;
2. VERIFIED cannot be produced without evidence, and the absence of evidence
   never masquerades as a pass.
"""

import json
import os

import pytest

from uibc_core import interop_result as ir

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EV = {
    "id": "ev-001",
    "type": "package-evidence-root",
    "issuer": "did:key:z6Mkexampleissuer",
    "digest": "sha256:" + "ab" * 32,
}


def test_seven_states_are_closed_and_match_the_name():
    assert ir.STATES == ("VERIFIED", "INVALID", "REVOKED", "EXPIRED",
                         "INCONCLUSIVE", "UNSUPPORTED", "UNRESOLVED")
    assert len(set(ir.STATES)) == 7


def test_verified_requires_evidence():
    with pytest.raises(ir.ResultError):
        ir.result("VERIFIED", "did:key:z6Mksubject")
    with pytest.raises(ir.ResultError):
        ir.result("VERIFIED", "did:key:z6Mksubject", evidence=[])


def test_verified_with_evidence_is_returned_intact():
    doc = ir.result("VERIFIED", "did:key:z6Mksubject", evidence=[EV])
    assert doc["state"] == "VERIFIED"
    assert doc["evidence"][0]["digest"] == EV["digest"]
    assert ir.is_verified(doc)


def test_malformed_evidence_is_refused():
    with pytest.raises(ir.ResultError):
        ir.result("VERIFIED", "s", evidence=[{"id": "x", "type": "t", "issuer": "i"}])
    with pytest.raises(ir.ResultError):
        ir.result("VERIFIED", "s", evidence=[dict(EV, digest="sha256:ZZ")])
    with pytest.raises(ir.ResultError):
        ir.result("VERIFIED", "s", evidence=[dict(EV, digest="md5:" + "ab" * 32)])


def test_non_verified_states_do_not_need_evidence():
    for state in ("INVALID", "INCONCLUSIVE", "UNSUPPORTED", "UNRESOLVED"):
        doc = ir.result(state, "did:web:example.cn", detail="stated reason")
        assert doc["state"] == state and doc["evidence"] == []


def test_withdrawal_states_must_say_something():
    for state in ("REVOKED", "EXPIRED"):
        with pytest.raises(ir.ResultError):
            ir.result(state, "did:cn:88.100.1")
        doc = ir.result(state, "did:cn:88.100.1", detail="revoked 2026-11-20")
        assert doc["detail"].startswith("revoked")


def test_unknown_state_and_empty_subject_are_refused():
    with pytest.raises(ir.ResultError):
        ir.result("OK", "s")
    with pytest.raises(ir.ResultError):
        ir.result("INVALID", "")


def test_published_schema_file_is_exactly_the_code_document():
    path = os.path.join(REPO, "schemas", "verification-result.schema.json")
    with open(path, encoding="utf-8") as fh:
        on_disk = json.load(fh)
    # No hand-maintained copy: a schema that drifts from the code is a claim
    # about a contract nobody enforces.
    assert on_disk == json.loads(json.dumps(ir.states_document()))


def test_schema_encodes_the_evidence_precondition():
    schema = ir.states_document()
    verified_rule = schema["allOf"][0]
    assert verified_rule["if"]["properties"]["state"]["const"] == "VERIFIED"
    assert verified_rule["then"]["properties"]["evidence"]["minItems"] == 1


def test_digest_helper_matches_the_pattern():
    assert ir._DIGEST_RE.match(ir.digest_of("evidence bytes"))
    assert ir.digest_of("evidence bytes") == ir.digest_of(b"evidence bytes")


# --------------------------------------------------------------------------- #
# mapping our own verifier report onto the vocabulary
# --------------------------------------------------------------------------- #
def _report(result, checks):
    return {"result": result, "subject": "agent-1", "checks": checks,
            "scope": "structure and lifecycle"}


def test_pass_maps_to_verified_only_with_evidence():
    report = _report("PASS", [{"id": "S1", "name": "identity", "result": "PASS"}])
    with pytest.raises(ir.ResultError):
        ir.from_verify_report(report)          # no evidence handed over
    doc = ir.from_verify_report(report, evidence=[EV])
    assert doc["state"] == "VERIFIED" and ir.is_verified(doc)


def test_inconclusive_never_becomes_a_pass():
    report = _report("INCONCLUSIVE",
                     [{"id": "S6", "name": "seal signature",
                       "result": "INCONCLUSIVE", "detail": "unsigned package"}])
    doc = ir.from_verify_report(report, evidence=[EV])
    assert doc["state"] == "INCONCLUSIVE"           # evidence does not lift it
    assert not ir.is_verified(doc)


def test_fail_branches_are_distinguished_not_flattened():
    cases = {
        "REVOKED": {"id": "S7", "name": "revocation", "result": "FAIL"},
        "EXPIRED": {"id": "S8", "name": "validity window", "result": "FAIL"},
        "UNSUPPORTED": {"id": "S3", "name": "did method", "result": "FAIL"},
        "UNRESOLVED": {"id": "S4", "name": "resolve document", "result": "FAIL"},
        "INVALID": {"id": "S5", "name": "evidence root", "result": "FAIL"},
    }
    for expected, check in cases.items():
        doc = ir.from_verify_report(_report("FAIL", [check]))
        assert doc["state"] == expected, (expected, doc)


def test_unknown_report_shape_is_refused():
    with pytest.raises(ir.ResultError):
        ir.from_verify_report({"result": "GREEN"})
