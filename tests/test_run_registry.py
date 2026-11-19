"""The run register and the objection register must stay honest.

Both files are empty today, and an empty table is easy to fake into a full one
later: add a friendly row, round a figure, drop a refused objection. These tests
hold the parts that make a full row checkable — labels, verbatim quoting, and the
rule that refusals stay published.
"""
import os
import re
import unittest

import yaml

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(*parts):
    with open(os.path.join(_REPO, *parts), encoding="utf-8") as f:
        return f.read()


class TestTheRegistersExistAndSayTheirRules(unittest.TestCase):
    def test_runs_register_exists_and_requires_the_unroundable_figure(self):
        text = _read("docs", "RUNS.md")
        self.assertIn("never rounded", text)
        self.assertIn("archive digest", text)
        self.assertIn("blind", text)
        self.assertIn("directed", text)

    def test_dispositions_register_keeps_refusals(self):
        text = _read("docs", "DISPOSITIONS.md")
        self.assertIn("declined", text)
        self.assertIn("reversal condition", text)
        self.assertIn("never reused", text)

    def test_an_empty_register_says_empty_rather_than_zero(self):
        for name in ("RUNS.md", "DISPOSITIONS.md"):
            text = _read("docs", name)
            self.assertIn("no external", text.lower(),
                          "%s should state that nothing is on record, not imply a result" % name)

    def test_register_rows_are_well_formed_when_they_arrive(self):
        """Every non-placeholder row must carry an id and a link that looks like one."""
        text = _read("docs", "DISPOSITIONS.md")
        for line in text.splitlines():
            if not line.startswith("| D-"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            self.assertRegex(cells[0], r"^D-\d{8}-\d{2}$", "permanent id shape: %r" % cells[0])
            self.assertIn("http", cells[2], "an objection with no link cannot be checked: %r" % line)


class TestTheFormAsksTheQuestionThatChangesTheMeaning(unittest.TestCase):
    def setUp(self):
        self.form = yaml.safe_load(_read(".github", "ISSUE_TEMPLATE", "conformance-receipt.yml"))

    def _field(self, field_id):
        for item in self.form["body"]:
            if item.get("id") == field_id:
                return item
        return None

    def test_blank_and_directed_is_a_required_question(self):
        field = self._field("blind")
        self.assertIsNotNone(field, "the blind/directed axis is what makes a run count as different evidence")
        self.assertTrue(field["validations"]["required"])
        labels = " ".join(o for o in field["attributes"]["options"])
        self.assertIn("blind", labels)
        self.assertIn("directed", labels)

    def test_it_records_which_verifier_produced_the_numbers(self):
        field = self._field("verifier")
        self.assertIsNotNone(field)
        self.assertTrue(field["validations"]["required"])

    def test_the_relation_field_still_decides_the_count(self):
        field = self._field("relation")
        self.assertIsNotNone(field)
        self.assertTrue(field["validations"]["required"])


class TestTheComparisonAgainstTheCompetitorIsWrittenDown(unittest.TestCase):
    def test_the_page_records_that_we_were_behind_here(self):
        text = _read("docs", "COMPETITIVE-STATE.md")
        self.assertIn("probity", text.lower())
        self.assertIn("DISPOSITIONS", text)
        self.assertIn("比我们成熟", text)


if __name__ == "__main__":
    unittest.main()
