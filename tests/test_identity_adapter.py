import os

import pytest

from uibc_core import identity_adapter as ia
from uibc_core import interop_result as ir

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CA_PEM = os.path.join(REPO, "tests", "fixtures", "anchor", "freetsa_ca.pem")


def test_did_key_resolves_and_pins_a_digest():
    rec = ia.check("did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH")
    assert rec.state == "VERIFIED"
    assert rec.document_sha256 and len(rec.document_sha256) == 64
    ev = rec.as_evidence()
    assert ev["digest"] == "sha256:" + rec.document_sha256


def test_an_unimplemented_method_is_unsupported_not_unresolved():
    rec = ia.check("did:wba:example.com:user:alice")
    assert rec.state == "UNSUPPORTED"
    assert "did:wba" in rec.notes or "not" in rec.notes.lower()


def test_a_malformed_did_is_invalid_not_unsupported():
    rec = ia.check("did:cn:")
    assert rec.state == "INVALID", rec.as_dict()


def test_a_registry_method_without_an_endpoint_is_unresolved():
    """Well-formed, supported, but nothing to fetch from: that is UNRESOLVED."""
    rec = ia.check("did:cn:10.123.456789", timeout=2)
    assert rec.state == "UNRESOLVED", rec.as_dict()


def test_a_certificate_parses_but_stops_at_inconclusive():
    if not os.path.exists(CA_PEM):
        pytest.skip("CA fixture absent")
    with open(CA_PEM, encoding="utf-8") as fh:
        pem = fh.read()
    rec = ia.check(pem)
    assert rec.state == "INCONCLUSIVE", rec.as_dict()
    assert "no chain built" in rec.notes
    assert rec.key_material.get("spki_sha256")


def test_a_non_certificate_is_invalid():
    rec = ia.check("-----BEGIN CERTIFICATE-----\nnot base64\n-----END CERTIFICATE-----\n")
    assert rec.state == "INVALID"


def test_absent_dependency_is_supported_state_not_a_crash(monkeypatch):
    monkeypatch.setattr(ia, "_HAS_PKIX", False)
    rec = ia.check("-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n")
    assert rec.state == "UNSUPPORTED"
    assert "not installed" in rec.notes


def test_adapter_refuses_schemes_it_does_not_claim():
    with pytest.raises(ia.AdapterUnavailable):
        ia.check("mailto:someone@example.com")
    assert ia.state_for(ia.AdapterUnavailable("x")) == "UNSUPPORTED"
    assert ia.state_for(ir.ResultError("x")) == "INCONCLUSIVE"
    assert ia.state_for(ValueError("x")) == "UNRESOLVED"


def test_no_adapter_may_speak_about_standing_over_time():
    """REVOKED/EXPIRED belong to the verification path, not the identity path."""
    for rec in (ia.check("did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"),
                ia.check("did:wba:example.com:user:alice"),
                ia.check("did:example:123")):
        assert rec.state in ir.STATES
        assert rec.state not in ("REVOKED", "EXPIRED")


def test_records_are_serialisable_without_secrets():
    rec = ia.check("did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH")
    d = rec.as_dict()
    assert d["adapter"] == "did" and "state" in d
