"""The counts quoted in the READMEs must equal the counts the tools produce.

A number written into a README is a claim like any other. It goes stale the day
a row changes state, and nothing notices unless something compares the two. This
does, using the committed results (the same files `tools/recheck.py` compares
against a fresh run), and it does it for both entry points: `README.md` and
`README.en.md`. Two files carrying the same sentence drift apart the moment one
is edited alone.

Skipped inside an sdist, where `tools/out` is pruned by MANIFEST.in - the same
condition `tests/test_recheck.py` skips on.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "out"
READMES = [ROOT / "README.md", ROOT / "README.en.md"]

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
    actual = {
        "clauses": sum(totals.values()),
        "PARTIAL": totals.get("PARTIAL", 0),
        "GAP": totals.get("GAP", 0),
        "COVERED": totals.get("COVERED", 0),
    }
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        m = PATTERN.search(text)
        assert m, "%s no longer states the regulated clause counts" % readme.name
        claimed = {
            "clauses": int(m.group(1)),
            "PARTIAL": int(m.group(2)),
            "GAP": int(m.group(3)),
            "COVERED": int(m.group(4)),
        }
        assert claimed == actual, "%s says %s; results say %s" % (readme.name, claimed, actual)


def test_both_readmes_name_the_two_carried_clauses():
    totals = _regulated_counts()
    if totals.get("COVERED", 0) != 2:
        return  # the sentence names the current pair; two is what it is about
    for readme in READMES:
        text = readme.read_text(encoding="utf-8").replace("21 CFR\n11.70", "21 CFR 11.70")
        assert "21 CFR 11.70" in text, readme.name
        assert "AU-10" in text, readme.name
