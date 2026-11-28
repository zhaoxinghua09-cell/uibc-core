"""A receipt is verified by a second language, not by us.

Why this exists (2026-11-27): every verification claim in this repository was checked
with our own Python. A competitor that shall stay unnamed here publishes Go, Rust and
python-cwt verifiers and states plainly that its receipts are verified outside its own
stack. This test is the smallest honest step in that direction: a Node.js verifier that
imports none of our code re-derives the inclusion root, checks the operator signature,
checks the witness cosignature under its separate domain, and rejects a tampered proof.

Scope, stated so nobody over-reads it: this covers the *receipt* (Merkle fold, two
Ed25519 signatures, domain separation). It does not cover the package semantics
(S1..S12), which remain Python-only.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NODE = shutil.which("node")
SCRIPT = os.path.join(REPO, "verify-node", "verify_receipt.mjs")


def _receipt(tmp_path, size=5, index=2):
    sys.path.insert(0, REPO)
    from uibc_core import translog

    log = translog.new_log()
    for i in range(size):
        translog.append(log, {"case": "parity-%d" % i, "agent_id": "node-check"})

    operator = bytes(range(32))
    witness = bytes(range(32, 64))
    cp = translog.checkpoint(log, operator, "node parity check")
    cosig = translog.cosign(cp, witness)
    proof = translog.inclusion_proof(log, index)

    receipt = {
        "format": "uibc-receipt-v1",
        "issued_at": "2026-11-27T00:00:00Z",
        "log": {
            "format": "uibc-translog-v1",
            "checkpoint": cp,
            "cosignature": cosig,
            "operator_public_key": translog.ed25519_key_id(operator).split(":", 1)[1],
            "witness_public_key": translog.ed25519_key_id(witness).split(":", 1)[1],
        },
        "statement": {"subject": {"evidence_root": log["entries"][index],
                                  "agent_id": "node-check"},
                      "claim": "root was in the log at this checkpoint"},
        "entry": {"index": index, "leaf_digest": log["entries"][index],
                  "inclusion_proof": [p.hex() for p in proof]},
        "notice": "built inside a test; keys are throwaway",
        "self_check": {},
    }
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    return path


@pytest.mark.skipif(NODE is None, reason="node is not installed on this machine")
def test_node_verifies_a_receipt_without_our_code(tmp_path):
    path = _receipt(tmp_path)
    run = subprocess.run([NODE, SCRIPT, str(path)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-400:]
    report = json.loads(run.stdout)
    assert report["format"] == "uibc-receipt-v1"
    assert report["results"]["inclusion_proof"] is True
    assert report["results"]["checkpoint_signature"] is True
    assert report["results"]["witness_cosignature"] is True
    assert report["results"]["domain_separation_attack_rejected"] is True
    assert report["results"]["tampered_proof_rejected"] is True
    assert report["all"] is True
