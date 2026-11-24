"""Numbers we publish in docs, checked against the docs beside them.

A register that says "2 entries" above a table of 3 is the smallest possible
integrity failure, and the easiest to ship. These checks are cheap because the
claim and the evidence are in the same file -- which is why the files are
written that way.
"""

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODES = os.path.join(REPO, "docs", "EXTERNAL-NODES.md")
LADDER = os.path.join(REPO, "docs", "AUDIT-ASSURANCE-LADDER.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_external_node_count_matches_the_table():
    text = _read(NODES)
    claimed = int(re.search(r"本表 \*\*(\d+) 条\*\*", text).group(1))
    rows = [ln for ln in text.splitlines()
            if ln.startswith("| 2026-") and ln.count("|") >= 5]
    assert claimed == len(rows), (
        "docs/EXTERNAL-NODES.md claims %d entries but has %d rows"
        % (claimed, len(rows)))


def test_annotated_defect_stays_visible():
    """Node 002's key field does not count as evidence. If that annotation is
    deleted, this register starts claiming more than it has."""
    text = _read(NODES)
    assert "不构成独立评估的证据" in text
    assert "PR #356" in text


def test_ladder_scores_itself_and_says_so():
    text = _read(LADDER)
    assert "自评，不是认证" in text
    assert "**当前档位：AIA-2" in text
    for zero in ("外部文档引用 0", "团体采纳 0", "与本项目无关者独立复现 0"):
        assert zero in text, "the ladder must keep listing the zeros it cannot fix alone"
