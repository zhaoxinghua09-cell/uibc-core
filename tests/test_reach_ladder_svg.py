"""The reach-ladder picture must be a rendering of the receipts, not of opinions."""

import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))

import build_reach_ladder_svg as ladder  # noqa: E402


def _load(path):
    if not os.path.exists(path):
        pytest.skip("artefact not built in this checkout: %s" % os.path.basename(path))
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_the_svg_is_a_fresh_render_of_the_two_receipts():
    svg = _load(ladder.SVG)
    with open(ladder.LEDGER, encoding="utf-8") as f:
        ledger = json.load(f)
    with open(ladder.OURS, encoding="utf-8") as f:
        ours = json.load(f)
    assert svg == ladder.render(ledger, ours)


def test_every_segment_length_comes_from_the_receipt():
    svg = _load(ladder.SVG)
    with open(ladder.LEDGER, encoding="utf-8") as f:
        ledger = json.load(f)
    totals = ledger["totals"]
    # 'verdict / total' is printed from the receipt, not typed in.
    assert "%d / %d" % (totals["verdict"], totals["vectors"]) in svg
    for count in (totals["verdict"], totals["signature-only"], totals["nothing"]):
        assert ">%d</text>" % count in svg


def test_the_picture_names_both_receipts_and_the_boundary():
    svg = _load(ladder.SVG)
    assert "corpus-ledger-39daf704.json" in svg
    assert "own-corpus-replay.json" in svg
    # The one sentence that keeps 88 from reading as 157.
    assert "never added to the 69" in svg


def test_a_changed_receipt_changes_the_picture():
    with open(ladder.LEDGER, encoding="utf-8") as f:
        ledger = json.load(f)
    with open(ladder.OURS, encoding="utf-8") as f:
        ours = json.load(f)
    a = ladder.render(ledger, ours)
    moved = json.loads(json.dumps(ledger))
    moved["totals"]["nothing"] += 1
    moved["totals"]["signature-only"] -= 1
    assert ladder.render(moved, ours) != a
