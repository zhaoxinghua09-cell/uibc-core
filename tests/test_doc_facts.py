"""Published numbers are promises a reviewer will test.

This test is the mechanism that keeps them true: if a test is added and the
README still says the old count, CI goes red here rather than in a stranger's
hands six weeks later.
"""
import os
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_doc_facts as cdf  # noqa: E402


class TestDocFacts(unittest.TestCase):
    def test_a_marked_docs_page_is_actually_checked(self):
        """The marker is a promise; a page that carries it must be scanned."""
        marked = cdf.marked_docs()
        self.assertGreaterEqual(len(marked), 5, marked)
        targets = cdf.all_targets()
        for path in marked:
            self.assertIn(path, targets)
        import tempfile, os, shutil
        tmp = tempfile.mkdtemp()
        try:
            f = os.path.join(tmp, "x.md")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write("<!-- facts: current -->\n\n999 tests\n")
            bad = cdf.check(cdf.measure(), [f])
            self.assertTrue(bad, "a wrong number in a marked page was not caught")
        finally:
            shutil.rmtree(tmp)

    def test_an_unmarked_docs_page_is_left_alone(self):
        """History is not rewritten: only pages that claim to be current are checked."""
        unmarked = [p for p in os.listdir("docs") if p.endswith(".md")
                    and p not in [x.split("/")[-1] for x in cdf.marked_docs()]]
        self.assertTrue(unmarked)
        targets = cdf.all_targets()
        for name in ("REVIEW-LOG.md", "RUN-RECORD-second-machine-20261118.md"):
            self.assertNotIn("docs/" + name, targets)

    def test_every_fact_can_be_measured(self):
        facts = cdf.measure()
        for key in ("tests", "checks", "modules", "attacks", "redteam_attacks", "cases"):
            self.assertIsNotNone(facts.get(key), "%s could not be measured, so a "
                                                "claim about it is unchecked" % key)
        self.assertGreater(facts["tests"], 100)
        self.assertEqual(facts["checks"], 20)

    def test_no_published_number_is_stale(self):
        facts = cdf.measure()
        bad = cdf.check(facts)
        self.assertEqual(bad, [], "\n".join("%s:%d %s claims %d, measured %d"
                                            % (b["file"], b["line"], b["kind"],
                                               b["claimed"], b["actual"]) for b in bad))

    def test_it_catches_a_wrong_number(self):
        """A checker that cannot fail is a formality."""
        path = os.path.join(tempfile.mkdtemp(prefix="docfacts-"), "x.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("the suite runs 12 tests today\n")
        facts = cdf.measure()
        bad = cdf.check(facts, [path])
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["claimed"], 12)

    def test_the_paper_is_checked_too(self):
        """A paper is cited; a stale number there outlives every README."""
        self.assertIn("paper/paper.md", cdf.TARGETS)

    def test_it_does_not_confuse_two_tools_with_the_same_word(self):
        facts = cdf.measure()
        self.assertNotEqual(facts["attacks"], facts["redteam_attacks"],
                            "the two attack counts must stay distinguishable, "
                            "or one of them is being silently checked against "
                            "the other")


if __name__ == "__main__":
    unittest.main()
