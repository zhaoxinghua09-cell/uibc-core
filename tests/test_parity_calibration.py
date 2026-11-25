"""The parity metric has to say how wrong it can be, in numbers.

Five contracts:

1. the snapshot carries a calibration block that matches a fresh re-measure;
2. an empty synthetic repository scores zero - a counter that awards points to
   nothing is not a counter;
3. a repository that only stuffs the keywords into comments scores zero: words
   are not evidence, and the assertion floor is what enforces that;
4. a repository with twelve real rejection assertions does score D1, so the
   floor rejects stuffing without rejecting honesty;
5. the published ceiling is below the best real competitor, and a tampered
   ceiling in the snapshot is caught by --check.
"""

import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    spec = importlib.util.spec_from_file_location(
        "competitor_gate_parity", os.path.join(ROOT, "tools", "competitor_gate_parity.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def parity():
    return _load()


@pytest.fixture()
def snap(parity):
    return json.load(open(parity.SNAPSHOT, encoding="utf-8"))


def test_snapshot_calibration_matches_a_fresh_measure(parity, snap):
    cal = snap["calibration"]
    fresh = parity.calibrate()
    assert {k: cal[k] for k in ("empty", "stuffed", "honest", "ceiling")} == fresh


def test_an_empty_tree_scores_zero(parity):
    assert parity.calibrate()["empty"] == 0


def test_keywords_without_assertions_score_zero(parity):
    assert parity.calibrate()["stuffed"] == 0, (
        "a tree that writes the words in comments and asserts nothing must not score; "
        "otherwise the table ranks text, not testing")


def test_real_assertions_do_score(parity):
    assert parity.calibrate()["honest"] >= 1, (
        "the assertion floor must not be so high that an honest small repository scores zero")


def test_published_ceiling_is_below_the_best_competitor(parity, snap):
    repos = [r for r in snap["repos"] if "error" not in r]
    best = max(sum(r["dims"].values()) for r in repos)
    assert snap["calibration"]["ceiling"] < best, (
        "if keyword stuffing can reach the best competitor's score, the table cannot "
        "rank competitors and the claim has to be cut down")
    doc = open(parity.DOC, encoding="utf-8").read()
    assert f"**{snap['calibration']['ceiling']}/10**" in doc, "doc must publish the measured ceiling"


def test_a_tampered_ceiling_is_caught(parity, snap, capsys):
    snap["calibration"]["ceiling"] = 9
    assert parity.check(snap) == 1
    assert "calibration moved" in capsys.readouterr().out
