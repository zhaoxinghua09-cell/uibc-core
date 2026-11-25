"""The counts quoted in the README must equal the counts the tools produce.

A number written into a README is a claim like any other. It goes stale the day
a row changes state, and nothing notices unless something compares the two. This
does, using the committed results (the same files `tools/recheck.py` compares
against a fresh run).

Skipped inside an sdist, where `tools/out` is pruned by MANIFEST.in - the same
condition `tests/test_recheck.py` skips on.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "out"
README = ROOT / "README.md"

PATTERN = re.compile(
    r"(\d+)\s+regulatory clauses\s*=\s*(\d+)\s+PARTIAL\s*/\s*(\d+)\s+GAP\s*/\s*(\d+)\s+COVERED")


def _regulated_counts():
    totals = {}
    files = sorted(OUT.glob("crosswalk-*.json"))
    if not files:
        pytest.skip("committed crosswalk results are not shipped inside the sdist")
    for f in files:
        if f.name == "crosswalk-tool-contract.json":
            continue  # a tool contract, not a regulation
        doc = json.loads(f.read_text(encoding="utf-8"))
        for state, n in doc["counts"].items():
            totals[state] = totals.get(state, 0) + n
    return totals


def test_readme_counts_match_the_committed_results():
    totals = _regulated_counts()
    text = README.read_text(encoding="utf-8")
    m = PATTERN.search(text)
    assert m, "the README no longer states the regulated clause counts"
    claimed = {
        "clauses": int(m.group(1)),
        "PARTIAL": int(m.group(2)),
        "GAP": int(m.group(3)),
        "COVERED": int(m.group(4)),
    }
    actual = {
        "clauses": sum(totals.values()),
        "PARTIAL": totals.get("PARTIAL", 0),
        "GAP": totals.get("GAP", 0),
        "COVERED": totals.get("COVERED", 0),
    }
    assert claimed == actual, "README says %s; results say %s" % (claimed, actual)


def test_readme_states_which_two_clauses_are_carried():
    totals = _regulated_counts()
    carried = [f for f in sorted(OUT.glob("crosswalk-*.json"))
               if f.name != "crosswalk-tool-contract.json"
               and any(r["state"] == "COVERED"
                       for r in json.loads(f.read_text(encoding="utf-8"))["rows"])]
    text = README.read_text(encoding="utf-8")
    if totals.get("COVERED", 0) == 2:
        # The README names both, so a reader can check them without the tool.
        assert "21 CFR\n11.70" in text or "21 CFR 11.70" in text
        assert "AU-10" in text
    assert len(carried) >= 1
