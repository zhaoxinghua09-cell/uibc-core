"""The run register and the objection register must stay honest.

Both files are empty today, and an empty table is easy to fake into a full one
later: add a friendly row, round a figure, drop a refused objection. These tests
hold the parts that make a full row checkable — labels, verbatim quoting, and the
rule that refusals stay published.

The form itself is read as text rather than through a YAML parser: this suite
runs with no third-party packages, and a test that only passes where PyYAML
happens to be installed is a test that silently stops guarding anything.
"""
import os
import re
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(*parts):
    with open(os.path.join(_REPO, *parts), encoding="utf-8") as f:
        return f.read()


def _form_blocks(text):
    """Split the issue form into one string per top-level body item."""
    starts = [m.start() for m in re.finditer(r"^\s{2}- type:", text, re.M)]
    blocks = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(text)
        blocks.append(text[s:e])
    return blocks


def _field(text, field_id):
    for block in _form_blocks(text):
        if re.search(r"^\s+id:\s*%s\s*$" % re.escape(field_id), block, re.M):
            return block
    return None


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
        self.text = _read(".github", "ISSUE_TEMPLATE", "conformance-receipt.yml")

    def test_blind_and_directed_is_a_required_question(self):
        block = _field(self.text, "blind")
        self.assertIsNotNone(block, "the blind/directed axis is what makes a run different evidence")
        self.assertIn("required: true", block)
        self.assertIn("blind", block)
        self.assertIn("directed", block)

    def test_it_records_which_verifier_produced_the_numbers(self):
        block = _field(self.text, "verifier")
        self.assertIsNotNone(block)
        self.assertIn("required: true", block)

    def test_the_relation_field_still_decides_the_count(self):
        block = _field(self.text, "relation")
        self.assertIsNotNone(block)
        self.assertIn("required: true", block)


class TestTheComparisonAgainstTheCompetitorIsWrittenDown(unittest.TestCase):
    def test_the_page_records_that_we_were_behind_here(self):
        text = _read("docs", "COMPETITIVE-STATE.md")
        self.assertIn("probity", text.lower())
        self.assertIn("DISPOSITIONS", text)
        self.assertIn("比我们成熟", text)


if __name__ == "__main__":
    unittest.main()
