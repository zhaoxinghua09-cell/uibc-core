"""The pin file must stay usable by someone who never installs this package."""

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIN = os.path.join(REPO, "anchors", "pins", "uibc-core-0.4.0.sha256")


class TestReleasePin(unittest.TestCase):
    def test_the_pin_exists(self):
        self.assertTrue(os.path.isfile(PIN), "the 0.4.0 pin is gone")

    def test_it_is_plain_sha256sum_format(self):
        with open(PIN, encoding="utf-8") as fh:
            rows = [l for l in fh.read().splitlines() if l.strip() and not l.lstrip().startswith("#")]
        self.assertEqual(len(rows), 2, "expected the wheel and the sdist")
        for row in rows:
            self.assertRegex(row, r"^[0-9a-f]{64}\s{2}\S+$",
                             "not the two-space sha256sum format")
            name = row.split()[-1]
            self.assertTrue(name.startswith("uibc_core-0.4.0"), name)

    def test_the_checker_names_three_sources(self):
        with open(os.path.join(REPO, "tools", "check_pins.py"), encoding="utf-8") as fh:
            src = fh.read()
        for phrase in ("release asset", "PyPI index", "download"):
            self.assertIn(phrase, src, "check_pins.py stopped distinguishing the three sources")
        self.assertRegex(src, r"any two agreeing is not enough|not enough")


if __name__ == "__main__":
    unittest.main()
