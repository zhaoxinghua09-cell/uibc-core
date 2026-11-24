"""The measurement in docs/VERDICT-VOCABULARY-VALUE.md, kept true.

The page prints three numbers and one hash. All four are recomputed here, and
the JSON the tool writes is compared byte for byte with what it wrote last time.
A page that argues from arithmetic has to fail the moment the arithmetic moves.
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, REPO)

import state_collapse as sc  # noqa: E402 - local tool, same boundary

RECORDED = os.path.join(REPO, "docs", "VERDICT-VOCABULARY.json")


def test_seven_loses_nothing():
    m = sc.build()["measured"]["seven"]
    assert m["distinct_outputs"] == 7
    assert m["pairs_kept_apart"] == m["pairs_total"] == 21
    assert len(m["critical_kept"]) == 4 and not m["critical_lost"]


def test_boolean_loses_every_critical_pair():
    m = sc.build()["measured"]["boolean"]
    assert m["distinct_outputs"] == 2
    assert m["pairs_kept_apart"] == 6
    assert len(m["critical_kept"]) == 0
    assert len(m["critical_lost"]) == 4


def test_ladder_keeps_half():
    m = sc.build()["measured"]["ladder"]
    assert m["distinct_outputs"] == 3
    assert m["pairs_kept_apart"] == 14
    assert len(m["critical_kept"]) == 2


def test_recorded_json_matches_a_fresh_build():
    body = sc.build()
    with open(RECORDED, encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert on_disk == body, (
        "docs/VERDICT-VOCABULARY.json is stale: rerun tools/state_collapse.py "
        "and update the page that quotes it")
    assert body["receipt_sha256"] == (
        "9256006ffcc44991e15570e46764163d92894ac3d7c3aceea8d86b215c98b9ef")


def test_mapping_is_labelled_as_a_reading_not_a_system():
    body = sc.build()
    assert "not the systems" in body["caveat"]
