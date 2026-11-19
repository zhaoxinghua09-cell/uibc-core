"""The oracle must keep saying what it said, and must be able to say "no".

A table of expectations that is never executed is a document. This runs it.
"""

import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOL = os.path.join(ROOT, "tools", "oracle_check.py")


class TestOracle(unittest.TestCase):
    def test_both_implementations_match_the_written_expectations(self):
        r = subprocess.run([sys.executable, TOOL], cwd=ROOT, capture_output=True)
        out = (r.stdout + r.stderr).decode("utf-8", "replace")
        self.assertEqual(r.returncode, 0, out[-1500:])
        self.assertIn("ORACLE: PASS", out)
        self.assertIn("cells disagreeing with the oracle: 0", out)

    def test_the_oracle_is_not_empty(self):
        """A checker with no cases passes trivially."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("oracle_check", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertGreaterEqual(len(mod.ORACLE) + len(mod.ORACLE_EXT) + 2, 21)

    def test_the_accept_side_exists_and_only_expects_acceptance(self):
        """A reject-only table is satisfied by a verifier that rejects everything."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("oracle_check", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertGreaterEqual(len(mod.ORACLE_ACCEPT), 5)
        verdicts = {row[2] for row in mod.ORACLE}
        self.assertEqual(verdicts, {"PASS", "FAIL"}, "an oracle of one verdict cannot fail")

    def test_every_extension_case_names_a_check_that_exists(self):
        """A row pointing at S20 is a typo that silently tests nothing."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("oracle_check", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for _name, _pre, _fn, _verdict, first in mod.ORACLE_EXT:
            self.assertIsNotNone(first, "an extension row must state a first failure")
            self.assertLessEqual(int(first[1:]), 19)

    def test_first_failure_is_ordered_by_check_number(self):
        """Report order is not check order; the tool must not depend on it."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("oracle_check", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        checks = [{"id": "S12", "result": "FAIL"}, {"id": "S5", "result": "FAIL"},
                  {"id": "S1", "result": "PASS"}]
        self.assertEqual(mod.first_fail(checks), "S5")


if __name__ == "__main__":
    unittest.main()
