"""The reader-coverage page must be a rendering of the source, not a paragraph.

Numbers like "18/19" are exactly the kind that drift silently, so the doc is
compared against a fresh render, and the two claims the project leans on (the
reference runs every check; the Node reader's only gap needs an input it does not
hold) are asserted structurally rather than as literals.
"""
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))


def _mod():
    spec = importlib.util.spec_from_file_location(
        "coverage_matrix", os.path.join(REPO, "tools", "coverage_matrix.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_doc_in_the_repo_matches_a_fresh_render():
    cm = _mod()
    stored = open(os.path.join(REPO, "docs", "READER-COVERAGE.md"), encoding="utf-8").read()
    assert stored == cm.render(cm.rows()), "docs/READER-COVERAGE.md is stale; rerun the tool --write"


def test_reference_runs_every_check():
    rs = {r["reader"]: r for r in _mod().rows()}
    assert rs["reference"]["covered"] == 19


def test_the_node_gap_is_an_input_it_does_not_hold():
    rs = {r["reader"]: r for r in _mod().rows()}
    assert rs["node"]["missing"] == [19], rs["node"]["missing"]
    assert "freshness" in rs["node"]["why"]["19"]


def test_independent_reader_reports_ten_outcomes():
    rs = {r["reader"]: r for r in _mod().rows()}
    assert rs["independent"]["outcomes"] == 10
    assert rs["independent"]["covered"] >= 10
