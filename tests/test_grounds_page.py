# -*- coding: utf-8 -*-
"""`docs/GROUNDS.md` must be a view of the data, never a second copy of it.

The page exists so a reader can see, without running anything, which sentence
each must-reject case rests on. That only works if the page cannot drift from
`grounds.json`: a stale view is worse than no view, because it looks checked.
"""
import importlib.util
import io
import json
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(REPO, "conformance", "oracle")
DOC = os.path.join(REPO, "docs", "GROUNDS.md")
TOOL = os.path.join(REPO, "tools", "build_grounds_page.py")


def _load_tool():
    if REPO not in __import__("sys").path:
        __import__("sys").path.insert(0, REPO)
    spec = importlib.util.spec_from_file_location("build_grounds_page", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


page = _load_tool()


class TestGroundsPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grounds = json.load(io.open(os.path.join(CORPUS, "grounds.json"),
                                        encoding="utf-8"))["cases"]
        cls.expected = json.load(io.open(os.path.join(CORPUS, "expected.json"),
                                         encoding="utf-8"))["cases"]
        cls.text = io.open(DOC, encoding="utf-8").read()

    def test_the_doc_is_a_fresh_render(self):
        self.assertEqual(self.text, page.render(),
                         "docs/GROUNDS.md is stale; run "
                         "`python tools/build_grounds_page.py > docs/GROUNDS.md`")

    def test_every_must_reject_case_appears_exactly_once(self):
        rejects = [c["case"] for c in self.expected
                   if c["expected_verdict"] == "FAIL"]
        for case in rejects:
            self.assertEqual(self.text.count("| `%s` |" % case), 1,
                             "%s: missing from the page or listed twice" % case)

    def test_the_accept_cases_are_not_filed_as_rejects(self):
        accepts = [c["case"] for c in self.expected if c["kind"] == "accept"]
        for case in accepts:
            self.assertNotIn("| `%s` |" % case, self.text,
                             "%s is a must-accept case and must not get a basis row"
                             % case)

    def test_every_quoted_sentence_is_on_the_page(self):
        quoted = [r for r in self.grounds if r.get("clause_quote")]
        self.assertGreaterEqual(len(quoted), 4, "the quotations are gone")
        for r in quoted:
            self.assertIn(r["clause_quote"].replace("|", "\\|"), self.text,
                          "%s: the quoted sentence is not on the page" % r["case"])

    def test_the_counts_in_the_prose_match_the_data(self):
        rejects = sum(1 for c in self.expected if c["expected_verdict"] == "FAIL")
        accepts = sum(1 for c in self.expected if c["kind"] == "accept")
        self.assertIn("%d must-reject, %d must-accept" % (rejects, accepts), self.text)
        self.assertIn("**%d of them quote the sentence**"
                      % len([r for r in self.grounds if r.get("clause_quote")]),
                      self.text)

    def test_the_page_does_not_claim_what_it_cannot_show(self):
        for phrase in ("断崖", "全面超越", "明显更强"):
            self.assertNotIn(phrase, self.text)


if __name__ == "__main__":
    unittest.main()
