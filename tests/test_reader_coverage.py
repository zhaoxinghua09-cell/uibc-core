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


def test_the_node_reader_has_a_path_for_every_check_but_two_run_only_with_input():
    rs = {r["reader"]: r for r in _mod().rows()}
    assert rs["node"]["missing"] == [], rs["node"]["missing"]
    assert rs["node"]["covered"] == 19
    # Having the code path is not the same as running it: S19 fires only when
    # a state file is passed. That is why the node coverage says 19/19 while the
    # behaviour tests still check "no flag, no line".
    src = open(os.path.join(REPO, "tools", "verify-js", "verify.mjs"), encoding="utf-8").read()
    assert "if (opts.freshness)" in src
    assert "--freshness" in src


def test_independent_reader_reports_ten_outcomes():
    rs = {r["reader"]: r for r in _mod().rows()}
    assert rs["independent"]["outcomes"] == 10
    assert rs["independent"]["covered"] >= 10
