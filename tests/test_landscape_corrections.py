"""Two claims about the competition were wrong on 2026-11-19. Keep them wrong.

The 2026-11-19 recheck found that:

  * another draft's author states an independent party reproduced 32/32 vectors,
    so "third-party execution" is not this repository's exclusive property;
  * Agent Passport System has a public OpenChain conformance record, so
    "no external organisation has published anything about it" was wrong.

Both corrections are now in LANDSCAPE-2026-11.md section 7. These tests fail if
someone edits them back out, or reintroduces the comparison they retired.
"""

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO, "docs")


def _landscape():
    with open(os.path.join(DOCS, "LANDSCAPE-2026-11.md"), encoding="utf-8") as fh:
        return fh.read()


class TestBothCorrectionsAreStillThere(unittest.TestCase):
    def test_independent_reproduction_by_another_draft(self):
        doc = _landscape()
        self.assertIn("2026-11-19 第三次复核", doc)
        self.assertIn("reproduced 32/32", doc,
                      "the correction that someone else reports an independent "
                      "reproduction has been removed")
        self.assertIn("mailarchive.ietf.org", doc, "the source link is gone")

    def test_external_organisation_record(self):
        doc = _landscape()
        self.assertIn("openchainproject.org", doc)
        self.assertIn("OpenChain", doc)
        self.assertIn("有组织的用户采纳该协议", doc,
                      "the distinction between 'users adopted it' and "
                      "'an organisation published a record about it' was lost")

    def test_it_says_third_party_execution_is_not_exclusive(self):
        doc = _landscape()
        self.assertIn("第三方执行本身已不是我们独占", doc)


class TestTheRetiredComparisonStaysRetired(unittest.TestCase):
    PATTERNS = [
        r"nobody else has (run|executed|reproduced)",
        r"no competitor has (run|executed|reproduced|published)",
        r"only this repository has (been )?(run|executed)",
        r"对手(没有|未)第三方",
        r"对手(没有|未)外部(执行|验证)",
    ]

    # A line that says the claim is wrong is quoting it, not making it. The
    # first run of this test failed on our own heading "不能说..." - which is
    # the check doing its job on the wrong target, so the exemption is explicit.
    EXEMPT = ("不能说", "错误", "已推翻", "收回", "不是我们独占")

    def test_no_claim_that_others_lack_outside_execution(self):
        doc = _landscape()
        for lineno, line in enumerate(doc.splitlines(), 1):
            if any(k in line for k in self.EXEMPT):
                continue
            for pat in self.PATTERNS:
                self.assertIsNone(re.search(pat, line, re.IGNORECASE),
                                  "retired comparison reintroduced at line %d: %s\n  %s"
                                  % (lineno, pat, line.strip()[:120]))


class TestTheOrderOfMagnitudeGapIsRecorded(unittest.TestCase):
    """The most adverse finding in the file must not be quietly dropped.

    2026-11-19, fourth recheck: the other draft's INTEROP.md lists nine
    independent parties, each with a linked public record. This repository has
    one, and it wrote that itself. If this number is edited down, someone is
    making the file look better than the evidence.
    """

    def test_nine_against_one_is_stated(self):
        doc = _landscape()
        self.assertIn("2026-11-19 第四次复核", doc)
        self.assertIn("9", doc)
        self.assertIn("INTEROP.md", doc)
        self.assertIn("A name is not evidence", doc)
        self.assertIn("1**（`docs/external-review/EXTERNAL-NODE-001.md`）", doc)

    def test_it_says_we_are_not_in_their_record(self):
        doc = _landscape()
        self.assertIn("INTEROP.md` 里没有本仓库", doc)

    # Quoting that a phrase is unsupportable is not asserting it. First run
    # tripped on "any '全面超越' wording is refuted by the four facts above".
    EXEMPT = ("推翻", "不能", "不是", "无法", "站不住", "被")

    def test_it_does_not_claim_the_gap_is_closed(self):
        doc = _landscape()
        for lineno, line in enumerate(doc.splitlines(), 1):
            if any(k in line for k in self.EXEMPT):
                continue
            for phrase in ("已经追平", "已超越", "数量级领先", "全面超越"):
                self.assertNotIn(phrase, line,
                                  "line %d claims more than the records show: %s"
                                  % (lineno, line.strip()[:120]))


if __name__ == "__main__":
    unittest.main()
