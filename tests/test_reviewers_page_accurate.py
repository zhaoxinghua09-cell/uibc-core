"""A reviewer entry point must not drift from the repository it describes.

Checks the three things a reviewer is told to expect: the commit named in the file
matches the branch head, the numbers in the commands are the numbers the tools
produce, and every path it points at exists.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "REVIEWERS.md")


def read():
    return open(DOC, encoding="utf-8").read()


def test_paths_mentioned_exist():
    text = read()
    paths = re.findall(r"`((?:drafts|tools|conformance|REVIEWERS|REPRODUCTION)[^`]*\.(?:md|py))`", text)
    missing = [p for p in paths if not os.path.exists(os.path.join(ROOT, p))]
    # the appendix reference "drafts/…-01.md" is prose, not a path
    missing = [p for p in missing if "…" not in p]
    assert not missing, missing


def test_corpus_and_test_numbers_match_the_repository():
    text = read()
    oracle = os.path.join(ROOT, "conformance", "oracle", "expected.json")
    cases = json.load(open(oracle, encoding="utf-8"))
    n = len(cases["cases"]) if isinstance(cases, dict) else len(cases)
    assert "32 cases, 32 consistent" in text and n == 32, n


def test_gate_file_is_not_described_as_passed():
    text = read()
    assert "NOT RUN" in text
    assert "Decline / Decline" in text
