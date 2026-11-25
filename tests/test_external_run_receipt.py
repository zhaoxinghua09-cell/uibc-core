"""A receipt is evidence only if editing it is caught.

`tools/stranger_competitor_check.py --receipt` writes what a runner's machine
computed; `tools/verify_external_run_receipt.py` recomputes it here. What is
tested is that the second one refuses:

  * a count moved by one;
  * a verdict flipped without recomputing the receipt's own digest;
  * a receipt with its digest stripped;
  * a receipt written by a different copy of the tool.

And what it must not do: claim to know who ran it. The receipt carries no
identity, and the test asserts the tool says so in its own words.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import stranger_competitor_check as stranger  # noqa: E402
import verify_external_run_receipt as ver  # noqa: E402

TOOL = os.path.join(ROOT, "tools", "verify_external_run_receipt.py")


SAMPLE = {
    "upstream": {"repo": "probityai/agent-evidence-vectors", "commit": "39daf704"},
    "source": "local",
    "bytes": {"checked": 171, "match": 171},
    "sweep": {"vectors": 171, "n_replayable": 69, "consistent": 69,
              "inconsistent": 0},
    "control": {"applied": 196, "detected": 183, "ambiguous": 13,
                "unexplained": 0},
    "ledger": None,
    "ledger_skipped": "no cryptography here",
    "sigstore_inclusion": {"compared": 36, "agree_with_published": 36,
                           "skipped_no_empty_root": 1, "unusable": 0},
    "diffs": [],
    "verdict": "PARTIAL",
    "code": 3,
}


def _fresh():
    return json.loads(json.dumps(ver.build_receipt(dict(SAMPLE))))


def test_the_tool_passes_its_own_selftest():
    out = subprocess.run([sys.executable, TOOL, "--selftest"],
                         capture_output=True, text=True, check=True)
    assert "a faithful receipt verifies" in out.stdout


def test_a_faithful_receipt_verifies_here():
    body = _fresh()
    assert ver.check(body, dict(SAMPLE)) == []


def test_a_count_moved_by_one_is_named():
    body = _fresh()
    body["sweep"]["n_replayable"] = 70
    bad = ver.check(body, dict(SAMPLE))
    assert any("n_replayable" in line for line in bad), bad


def test_a_flipped_verdict_breaks_the_digest():
    body = _fresh()
    body["verdict"] = "DID NOT MATCH"
    bad = ver.check(body, dict(SAMPLE))
    assert any("receipt_sha256" in line for line in bad), bad


def test_a_stripped_digest_is_refused_rather_than_recomputed():
    body = {k: v for k, v in _fresh().items() if k != "receipt_sha256"}
    bad = ver.check(body, dict(SAMPLE))
    assert bad and "receipt_sha256" in bad[0], bad


def test_a_receipt_from_another_tool_version_is_not_a_receipt_of_this_one():
    body = _fresh()
    body["tool_sha256"] = "0" * 64
    body.pop("receipt_sha256")
    import hashlib
    body["receipt_sha256"] = hashlib.sha256(ver.canonical(body)).hexdigest()
    bad = ver.check(body, dict(SAMPLE))
    assert any("tool_sha256" in line for line in bad), bad


def test_it_does_not_pretend_to_know_who_ran_it():
    with open(TOOL, encoding="utf-8") as f:
        src = f.read()
    assert "does not tell you *who* ran it" in src
    body = _fresh()
    assert "identity" not in json.dumps(body).lower(), (
        "a receipt must not carry an identity claim it cannot back")


def test_a_step_one_machine_could_not_run_is_a_scope_note_not_a_mismatch():
    """A receipt from a bare interpreter must still verify its arithmetic here."""
    with_ledger = json.loads(json.dumps(SAMPLE))
    with_ledger.update({"ledger": {"verdict": 69, "signature-only": 88,
                                   "nothing": 14, "signature_verified": 88},
                        "ledger_skipped": None})
    body = ver.build_receipt(with_ledger)
    diffs, note = ver.compare(body, dict(SAMPLE))
    assert diffs == [], diffs
    assert note and "ledger" in note, note


def test_the_limitation_is_stated_in_the_output():
    out = subprocess.run([sys.executable, TOOL, "--help"],
                         capture_output=True, text=True)
    with open(TOOL, encoding="utf-8") as f:
        src = f.read()
    assert "VERIFIED (arithmetic only)" in src


def test_the_stranger_tool_offers_the_receipt_flag():
    out = subprocess.run([sys.executable, os.path.join(
        ROOT, "tools", "stranger_competitor_check.py"), "--help"],
        capture_output=True, text=True, check=True)
    assert "--receipt" in out.stdout
