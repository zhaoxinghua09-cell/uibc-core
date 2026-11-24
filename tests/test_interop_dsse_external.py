"""The envelope must pass an implementation that is not ours.

Skipped unless securesystemslib is installed (it lives in the `verify` extra), because a
missing third party must not be mistaken for a passing third party.
"""
import base64
import json
import pathlib
import sys

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("securesystemslib")

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "interop"))
import dsse_external_check as ext  # noqa: E402
import intoto_receipt as ir  # noqa: E402

CASE = ROOT / "conformance" / "cases" / "02-a-package-with-its-tree-and-chain-appended" / "evidence" / "chain.json"


def _signed(tmp_path):
    out = tmp_path / "case.dsse.json"
    assert ir.sign(str(CASE), str(out), str(tmp_path / "demo.pem")) == 0
    return out


def test_third_party_accepts_our_envelopes(tmp_path):
    out = _signed(tmp_path)
    good, total, failed = ext.check(str(out))
    assert (good, total, failed) == (2, 2, [])


def test_third_party_rejects_the_tampered_envelope_only(tmp_path):
    out = _signed(tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    body = bytearray(base64.b64decode(doc["envelopes"][0]["payload"]))
    i = body.index(b"chain_length") + len(b"chain_length")
    body[i] = ord("7") if body[i] != ord("7") else ord("8")
    doc["envelopes"][0]["payload"] = base64.b64encode(bytes(body)).decode("ascii")
    doc["tampered_index"] = 0
    bad = tmp_path / "tampered.json"
    bad.write_text(json.dumps(doc), encoding="utf-8")

    good, total, failed = ext.check(str(bad))
    assert failed == [0], failed          # the edited envelope must fail
    assert good == total - 1, (good, total)  # and the untouched one must still pass
