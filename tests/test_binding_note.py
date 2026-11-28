"""The two projects anchor different objects. This test only holds our own
claim in place: our S16 is defined as "a third-party token covers the package's
head", not "a token covers a payload digest". If someone relaxes that, the
interop story in docs/BINDING.md stops being true and this fails.
"""

import os
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_CHECK = os.path.join(_REPO, "docs", "CHECKS-REFERENCE.md")
_BINDING = os.path.join(_REPO, "docs", "BINDING.md")


def _text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestAnchoringIsBoundToTheHead(unittest.TestCase):
    def test_s16_is_documented_as_covering_the_head(self):
        row = [l for l in _text(_CHECK).splitlines() if l.startswith("| S16")]
        self.assertTrue(row, "S16 row missing from the generated reference")
        self.assertIn("链头", row[0])

    def test_the_binding_note_records_the_measured_numbers(self):
        doc = _text(_BINDING)
        self.assertIn("12 / 12", doc)
        self.assertIn("10 / 13", doc)
        self.assertIn("bad-timestamp", doc)

    def test_the_binding_note_does_not_claim_superiority(self):
        """The honest framing is that both designs hold. A sentence claiming one
        is stricter would make the page an advertisement."""
        doc = _text(_BINDING)
        for word in ("断崖", "全面超越", "明显更强", "比对方严格"):
            self.assertNotIn(word, doc)
        self.assertIn("不能拿来说谁更强", doc)


if __name__ == "__main__":
    unittest.main()
