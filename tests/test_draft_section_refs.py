"""Every "Section N" in the drafts must resolve to a heading that exists.

Pinned because a phantom cross-reference is the cheapest thing a reviewer can
find and the most expensive thing to fix: one external review round went to a
sentence citing a "strict mode (Section 6)" that no section defined.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.check_section_refs import check  # noqa: E402

DRAFTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "drafts")


def test_every_draft_reference_resolves():
    names = [n for n in os.listdir(DRAFTS) if n.endswith(".md")]
    assert names, "no drafts found"
    bad = {}
    for n in names:
        missing, _, _ = check(os.path.join(DRAFTS, n))
        if missing:
            bad[n] = missing
    assert not bad, "unresolved references: %r" % bad


def test_01_moved_blocks_are_out_of_the_body():
    text = open(os.path.join(DRAFTS, "draft-zhao-uibc-evidence-chain-01.md"),
                encoding="utf-8").read()
    body = text.split("## Appendix A.")[0]
    for heading in ("## 16.", "## 17.", "### 5.1", "### 5.2"):
        assert heading not in body, heading
