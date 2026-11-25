"""Both probes as contracts: a silent shape, a re-usable address, a dead bit.

The tools print tables for a person and JSON for a harness. These tests pin the
claims so that a regression cannot be reported as "the probe still runs":

- `tools/mutate_document_shapes.py`: every shape the protocol forbids is refused,
  and the one silence the parser does allow (an unknown key type) is caught by the
  verifier instead of being harmless by assumption.
- `tools/probe_address_binding.py`: flipping any key bit moves the address, and no
  single-character substitution of a published address is accepted.
"""

import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHAPES = _load("mutate_document_shapes")
ADDRESS = _load("probe_address_binding")


@pytest.fixture(scope="module")
def shapes():
    rows = SHAPES.probe()
    return rows, SHAPES.summarise(rows)


def test_every_forbidden_shape_is_refused(shapes):
    rows, summary = shapes
    assert summary["must_reject"] >= 20, summary
    assert summary["caught"] == summary["must_reject"], summary["silent"]
    assert summary["silent"] == []
    assert summary["wrong_error"] == []


def test_a_refusal_says_which_rule_was_broken(shapes):
    rows, _summary = shapes
    for row in rows:
        if row["outcome"] == "rejected":
            assert row["reason"], row["mutant"]
            assert "did:bid:" in row["reason"] or "§4.2.1" in row["reason"], row["mutant"]


def test_missing_created_is_a_violation_and_the_message_cites_the_item(shapes):
    """§4.2.1 items 9.created / 10.updated say 必填. Found by deleting the field."""
    rows, _summary = shapes
    by_name = {row["mutant"]: row for row in rows}
    for name, item in (("created deleted", "9.created"), ("updated deleted", "10.updated")):
        row = by_name[name]
        assert row["outcome"] == "rejected", row
        assert item in row["reason"] and "必填" in row["reason"], row["reason"]


def test_an_unknown_field_is_tolerated_because_the_shape_is_extensible(shapes):
    rows, summary = shapes
    assert summary["tolerated"] and all(item["outcome"] == "silent"
                                        for item in summary["tolerated"])


def test_a_relabelled_key_type_is_caught_by_verification_not_by_the_parser():
    result = SHAPES.type_relabel_is_caught_by_verification()
    assert result["honest_doc_verifies"] is True, result
    assert result["relabelled_verifies"] is False, result
    assert "signature" in result["relabelled_reason"].lower(), result


def test_flipping_any_key_bit_moves_the_address():
    result = ADDRESS.key_side()
    assert "error" not in result, result
    assert result["collisions_with_base"] == 0, result
    assert result["char_distance_min"] >= 20, result      # 30-char suffix, avalanche


def test_no_single_character_substitution_is_accepted():
    result = ADDRESS.address_side()
    assert result["tried"] > 1_000, result
    assert result["accepted"] == [], result["accepted"][:3]


def test_truncated_or_padded_addresses_do_not_match():
    result = ADDRESS.length_side()
    assert all(value is False for value in result.values()), result


def test_the_probe_runs_as_a_command_and_reports_the_same_numbers():
    import json
    import subprocess
    import sys

    res = subprocess.run([sys.executable, os.path.join(ROOT, "tools",
                                                       "probe_address_binding.py"), "--json"],
                         capture_output=True, text=True, encoding="utf-8",
                         env=dict(os.environ, PYTHONUTF8="1"), timeout=180)
    assert res.returncode == 0, res.stderr[-200:]
    data = json.loads(res.stdout)
    assert data["sample"]["reproduced"] is True
    assert data["key_to_address"]["collisions_with_base"] == 0
    assert data["address_to_key"]["accepted"] == []
