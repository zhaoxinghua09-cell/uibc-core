"""Does the headline survive a looser rule? Offline half of the contract.

The recorded sensitivity run must (a) cover exactly the snapshot's repos, (b) keep
the best competitor's score unchanged under the permissive rule, and (c) be
internally consistent: the only thing the looser rule may change is D1.
"""

import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(ROOT, "docs", "parity-sensitivity.json")
SNAPSHOT = os.path.join(ROOT, "docs", "competitor-parity.json")
DOC = os.path.join(ROOT, "docs", "PARITY-SENSITIVITY.md")


@pytest.fixture(scope="module")
def rec():
    return json.load(open(RECORD, encoding="utf-8"))


@pytest.fixture(scope="module")
def snap():
    return json.load(open(SNAPSHOT, encoding="utf-8"))


def test_record_covers_the_snapshot_exactly(rec, snap):
    want = {r["repo"] for r in snap["repos"] if "error" not in r}
    assert {r["repo"] for r in rec["rows"]} == want


def test_a_looser_rule_does_not_raise_the_best_competitor(rec):
    assert rec["best_window"] == rec["best_strict"], (
        "a permissive rule lets a rival score higher than the published best - "
        "the published headline has to be withdrawn, not the rule relaxed")


def test_only_d1_may_move(rec):
    for r in rec["rows"]:
        assert r["score_window"] - r["score_strict"] == r["D1_window"] - r["D1_strict"], r["repo"]
        assert r["assert_lines_window"] >= r["assert_lines_strict"], r["repo"]


def test_the_window_is_actually_more_permissive(rec):
    assert rec["window"] >= 1
    moved = [r for r in rec["rows"] if r["assert_lines_window"] > r["assert_lines_strict"]]
    assert moved, "a looser rule that changes nothing for anyone is not a sensitivity test"


def test_the_page_states_the_verdict(rec):
    page = open(DOC, encoding="utf-8").read()
    assert "敏感性" in page
    assert "结论不翻" in page or "结论翻车" in page
    assert str(rec["best_window"]) in page
