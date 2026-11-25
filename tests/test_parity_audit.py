"""Two contracts about auditability, one file for brevity.

1. Evidence lines: every point in the competitor table must point at a readable
   line, and a point that comes from an exit code must point into source (not
   into a test), because that is where the exit code lives.
2. D3 bracket: the strict rule may never score higher than the broad one; the
   page must say the number is a bracket, not a single value.
"""

import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "docs", "competitor-parity.json")
EV = os.path.join(ROOT, "docs", "competitor-evidence-lines.json")
EV_PAGE = os.path.join(ROOT, "docs", "COMPETITOR-EVIDENCE-LINES.md")
D3 = os.path.join(ROOT, "docs", "parity-d3-bracket.json")
D3_PAGE = os.path.join(ROOT, "docs", "D3-BRACKET.md")

DIM_SCOPE = {"D1": "test", "D2": "test", "D3": "test", "D4": "code"}


@pytest.fixture(scope="module")
def snap():
    return json.load(open(SNAP, encoding="utf-8"))


@pytest.fixture(scope="module")
def ev():
    return json.load(open(EV, encoding="utf-8"))


@pytest.fixture(scope="module")
def bracket():
    return json.load(open(D3, encoding="utf-8"))


def test_every_point_cites_a_line(ev):
    missing = [(r["repo"], d) for r in ev["rows"] for d, v in r["dims"].items()
               if v and not r["evidence"].get(d)]
    assert not missing, missing


def test_exit_code_points_cite_source_not_tests(ev, snap):
    """D4 is an exit code: its citation must not come from a test file."""
    import re
    test_re = re.compile(r"(^|[\\/])(tests?|spec|__tests__)([\\/]|$)|Test\.java$|test_.*\.py$|"
                         r"\.(test|spec)\.(js|ts|mjs|cjs)$|Tests\.java$")

    def is_test(path):
        return bool(test_re.search(path))

    for row in ev["rows"]:
        if not row["dims"].get("D4"):
            continue
        for e in row["evidence"]["D4"]:
            assert not is_test(e["file"]), (row["repo"], e["file"])


def test_evidence_is_capped_and_traceable(ev, snap):
    for row in ev["rows"]:
        for d, lines in row["evidence"].items():
            assert len(lines) <= ev["per_dim"]
            for e in lines:
                assert e["file"] and e["line"] > 0 and e["text"]
    assert {r["repo"] for r in ev["rows"]} == {r["repo"] for r in snap["repos"] if "error" not in r}


def test_evidence_page_lists_every_scoring_repository(ev):
    page = open(EV_PAGE, encoding="utf-8").read()
    for row in ev["rows"]:
        if sum(row["dims"].values()):
            assert "`%s`" % row["repo"] in page


def test_strict_d3_never_beats_broad(bracket):
    assert bracket["best_strict"] <= bracket["best_broad"]
    for row in bracket["rows"]:
        assert row["D3_strict"] <= row["D3_broad"], row["repo"]
        assert row["score_strict"] <= row["score_broad"], row["repo"]


def test_bracket_change_list_is_exact(bracket):
    changed = {r["repo"] for r in bracket["rows"] if r["D3_broad"] != r["D3_strict"]}
    assert changed == set(bracket["changed"])


def test_bracket_page_says_it_is_a_bracket(bracket):
    page = open(D3_PAGE, encoding="utf-8").read()
    assert "区间" in page
    assert str(bracket["best_broad"]) in page and str(bracket["best_strict"]) in page
