"""The in-toto mapping must sign what it can verify, and refuse everything else.

Skipped when `cryptography` is absent: it lives in the `verify` extra, not the base install.
"""
import base64
import json
import pathlib
import sys

import pytest

pytest.importorskip("cryptography")

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "interop"))
import intoto_receipt as ir  # noqa: E402

CASE = ROOT / "conformance" / "cases" / "02-a-package-with-its-tree-and-chain-appended" / "evidence" / "chain.json"


def _sign(tmp_path):
    key = tmp_path / "demo.pem"
    out = tmp_path / "case.dsse.json"
    assert ir.sign(str(CASE), str(out), str(key)) == 0
    return out


def test_round_trip_verifies(tmp_path):
    out = _sign(tmp_path)
    assert ir.verify(str(CASE), str(out)) == 0


def test_statement_shape(tmp_path):
    doc = json.loads(_sign(tmp_path).read_text(encoding="utf-8"))
    st = json.loads(base64.b64decode(doc["envelopes"][0]["payload"]))
    assert st["_type"] == ir.STATEMENT_TYPE
    assert st["predicateType"] == ir.PREDICATE_TYPE
    assert doc["envelopes"][0]["payloadType"] == ir.PAYLOAD_TYPE


def test_tampered_payload_is_refused(tmp_path):
    out = _sign(tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    body = bytearray(base64.b64decode(doc["envelopes"][0]["payload"]))
    body[body.index(b"chain_length") + len(b"chain_length")] = ord("7")
    doc["envelopes"][0]["payload"] = base64.b64encode(bytes(body)).decode("ascii")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc), encoding="utf-8")
    assert ir.verify(str(CASE), str(bad)) == 3


def test_dropped_envelope_is_refused(tmp_path):
    out = _sign(tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    doc["envelopes"] = doc["envelopes"][:1]
    short = tmp_path / "short.json"
    short.write_text(json.dumps(doc), encoding="utf-8")
    assert ir.verify(str(CASE), str(short)) == 3


def test_wrong_key_is_refused(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    out = _sign(tmp_path)
    other = tmp_path / "other.pub.pem"
    other.write_bytes(Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    assert ir.verify(str(CASE), str(out), str(other)) == 3
