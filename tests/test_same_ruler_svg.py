"""The comparison picture has to be a rendering of the two receipts, not a claim.

A bar chart is the easiest place for a document to lie: nobody re-derives a bar
length by eye. These tests pin it to the two receipts:

  * the SVG rebuilds byte for byte from
    docs/upstream-package/competitor-defects/corpus-sweep-39daf704.json and
    docs/upstream-package/measurements/own-corpus-replay.json;
  * both ratios appear in the picture, taken from those files;
  * the picture says which receipts it came from, so a reader can check it.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "build_same_ruler_svg.py")
SVG = os.path.join(ROOT, "docs", "CORPUS-REPLAYABILITY-SAME-RULER.svg")
THEIRS = os.path.join(ROOT, "docs", "upstream-package", "competitor-defects",
                      "corpus-sweep-39daf704.json")
OURS = os.path.join(ROOT, "docs", "upstream-package", "measurements",
                    "own-corpus-replay.json")
DOC = os.path.join(ROOT, "docs", "COMPETITOR-CORPUS-SWEEP.md")


def _read(path):
    """An sdist carries tools and tests but not docs; skip, not fail."""
    if not os.path.isfile(path):
        pytest.skip("%s is not in this distribution" % os.path.relpath(path, ROOT))
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_the_picture_rebuilds_from_the_two_receipts():
    _read(THEIRS)
    _read(OURS)
    _read(SVG)
    out = subprocess.run([sys.executable, TOOL, "--check"], cwd=ROOT,
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_both_ratios_in_the_picture_come_from_the_receipts():
    theirs = json.loads(_read(THEIRS))
    ours = json.loads(_read(OURS))
    svg = _read(SVG)
    up = "%d / %d (%.0f%%)" % (theirs["totals"]["n_replayable"], theirs["totals"]["vectors"],
                               100.0 * theirs["totals"]["n_replayable"] / theirs["totals"]["vectors"])
    own = "%d / %d (%.0f%%)" % (ours["totals"]["n_replayable"], ours["totals"]["vectors"],
                                100.0 * ours["totals"]["n_replayable"] / ours["totals"]["vectors"])
    assert up in svg
    assert own in svg


def test_the_picture_names_the_files_it_came_from():
    svg = _read(SVG)
    assert "corpus-sweep-39daf704.json" in svg
    assert "own-corpus-replay.json" in svg


def test_the_doc_points_at_the_picture():
    doc = _read(DOC)
    assert "CORPUS-REPLAYABILITY-SAME-RULER.svg" in doc
