"""The gate as a CI contract - and proof that it is able to fail.

A gate that only ever prints OK is decoration. So this file checks both halves:
the three probes agree today, and a ledger with a false row is reported as failed.
"""

import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_PATH = os.path.join(ROOT, "tools", "mutation_gate.py")


def _gate_module():
    spec = importlib.util.spec_from_file_location("mutation_gate", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report():
    res = subprocess.run([sys.executable, GATE_PATH, "--json"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8",
                         env=dict(os.environ, PYTHONUTF8="1"), timeout=300)
    assert res.returncode == 0, (res.returncode, res.stderr[-300:])
    return json.loads(res.stdout)


def test_the_gate_passes_on_this_tree(report):
    assert report["ok"] is True, report["failed"]
    assert report["failed"] == []


def test_the_gate_covers_all_three_layers(report):
    layers = {row["layer"] for row in report["checks"]}
    assert layers == {"document", "binary", "address"}, layers


def test_the_gate_keeps_every_load_bearing_claim(report):
    names = {row["check"] for row in report["checks"]}
    for expected in ("nothing forbidden is accepted silently",
                     "the blind set is exactly the reserved header bits",
                     "no single-character substitution is accepted"):
        assert expected in names, sorted(names)


def test_the_gate_can_fail():
    """Inject a false row: the ledger must report it, not swallow it."""
    gate = _gate_module()
    ledger = gate.Ledger()
    ledger.check("document", "a deliberately broken claim", False, "detail")
    assert ledger.failed(), "a ledger holding a false row reported success"
    assert ledger.rows[0]["ok"] is False


def test_a_failing_check_names_itself(report):
    gate = _gate_module()
    ledger = gate.run()
    ledger.check("binary", "forced failure for the message", False, "x")
    assert [row["check"] for row in ledger.failed()] == ["forced failure for the message"]
    assert not report["failed"]              # today's real run stays clean
