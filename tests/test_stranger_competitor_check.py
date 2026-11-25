"""The stranger's entry point must stay a comparison, not a promise.

`tools/stranger_competitor_check.py` fetches the upstream corpus, digests all 171
files against the receipt we committed, and re-runs the sweep and the mutation
control against their receipts. Its whole value is that it *fails* when any of
those three disagree, so what is tested here is the failing:

  * altered bytes are named, and a missing file is a different verdict;
  * a count that moves is reported with both numbers rather than rounded;
  * the corpus is found by its tail, not by "some directory with json in it".
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "stranger_competitor_check.py")
DOC = os.path.join(ROOT, "docs", "COMPETITOR-CORPUS-SWEEP.md")
REGISTER = os.path.join(ROOT, "docs", "claims-register.md")


def test_the_tool_passes_its_own_selftest():
    out = subprocess.run([sys.executable, TOOL, "--selftest"],
                         capture_output=True, text=True, check=True)
    assert "selftest: bytes, counts and corpus discovery all behave" in out.stdout


def test_it_offers_the_three_ways_in_and_json_output():
    out = subprocess.run([sys.executable, TOOL, "--help"],
                         capture_output=True, text=True, check=True)
    for flag in ("--dir", "--json", "--selftest"):
        assert flag in out.stdout, flag


def test_the_verifier_is_standard_library_only():
    """A stranger must not need to install anything to check our numbers."""
    with open(TOOL, encoding="utf-8") as f:
        src = f.read()
    # The only imports are stdlib plus our own two tools.
    assert "import sweep_competitor_corpus" in src
    assert "import sweep_mutation_control" in src
    for banned in ("import requests", "import cryptography", "import pytest"):
        assert banned not in src, banned


def test_it_checks_the_bytes_before_it_checks_the_numbers():
    """The order is the whole argument: a count is meaningless if the bytes moved."""
    with open(TOOL, encoding="utf-8") as f:
        src = f.read()
    assert src.index("verify_bytes(corpus") < src.index("sweep.run(corpus)")


def test_a_missing_signature_library_is_not_called_a_mismatch():
    """No cryptography must read as PARTIAL (code 3), never as "our numbers failed".

    Measured on a bare interpreter (`python3 -S`): before this guard the ledger
    step reported 171 rows as differing ones, and the command said DID NOT MATCH -
    blaming our receipt for a library the reader had not installed.
    """
    with open(TOOL, encoding="utf-8") as f:
        src = f.read()
    assert "SignatureLayerUnavailable" in src
    assert "PARTIAL" in src
    assert 'out["code"] = 3' in src
    # The other four steps must still run without that library.
    out = subprocess.run([sys.executable, "-S", TOOL, "--selftest"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_the_doc_and_the_register_both_carry_the_entry_point():
    with open(DOC, encoding="utf-8") as f:
        doc = f.read()
    assert "tools/stranger_competitor_check.py" in doc
    assert "REPRODUCED" in doc
    with open(REGISTER, encoding="utf-8") as f:
        reg = f.read()
    assert "stranger_competitor_check.py" in reg
    assert "REPRODUCED" in reg
