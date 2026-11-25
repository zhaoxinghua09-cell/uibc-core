"""Cross-implementation check of the BID signing rule (§5).

The Python implementation signs; node - with its own RFC 8785 canonicalizer and
OpenSSL's Ed25519 - must verify. Two different languages, two different
canonicalizers, one answer: this is what "a third party can re-run it" means.
"""

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from uibc_core import bid_protocol as B  # noqa: E402

FIXTURE = REPO / "fixtures" / "bid" / "signed_document.json"
JS = REPO / "tools" / "verify-js" / "bid.mjs"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed; the cross-check cannot run"
)


def _run_js(path):
    proc = subprocess.run(["node", str(JS), str(path)], capture_output=True, text=True, timeout=60)
    return proc.returncode, proc.stdout + proc.stderr


def test_the_committed_fixture_is_still_the_one_python_signs():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ok, reason = B.verify_bid_document(doc)
    assert ok, reason


def test_node_verifies_the_signature_with_its_own_canonicalizer():
    code, out = _run_js(FIXTURE)
    assert code == 0, out
    assert "signature-verified true" in out


def test_both_implementations_compute_the_same_signing_bytes():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mine = hashlib.sha256(B.signing_bytes(doc)).hexdigest()
    code, out = _run_js(FIXTURE)
    assert code == 0, out
    line = [l for l in out.splitlines() if l.startswith("signing-bytes-sha256 ")][0]
    assert line.split()[-1] == mine, "python and node disagree on the canonical bytes"


def test_node_rejects_a_single_field_tampered_document(tmp_path):
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    doc["extension"]["ttl"] = doc["extension"]["ttl"] + 1
    target = tmp_path / "tampered.json"
    target.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    code, out = _run_js(target)
    assert code == 1, out
    assert "signature-verified false" in out
