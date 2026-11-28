"""The reproduction sheet must contain commands that run and outputs that were
seen.

The failure this guards against is a sheet that looks like evidence and is
actually a copy of the table it claims to verify: same numbers, no execution.
So one assertion runs a real claim end to end, and another refuses placeholder
output.
"""
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_reproduce as br  # noqa: E402


class TestReproduceSheet(unittest.TestCase):
    def test_every_claim_has_a_command_and_an_argv(self):
        self.assertGreaterEqual(len(br.CLAIMS), 10)
        for table, what, cmd, argv in br.CLAIMS:
            self.assertTrue(cmd.startswith("python3"), cmd)
            self.assertTrue(argv, what)

    def test_no_claim_is_a_placeholder(self):
        with open(os.path.join(_REPO, "docs", "REPRODUCE.md"), encoding="utf-8") as fh:
            doc = fh.read()
        for junk in ("`{`", "`}`", "(no output)", "TODO"):
            self.assertNotIn(junk, doc, "placeholder output in the sheet: %s" % junk)
        # every claim appears as a row
        self.assertGreaterEqual(doc.count("\n| "), len(br.CLAIMS))

    def test_one_claim_really_executes(self):
        """Not the whole sheet -- one command, and it must produce its figure."""
        table, what, cmd, argv = next(c for c in br.CLAIMS if c[1] == "20 checks")
        out, code = br.run(argv)
        self.assertEqual(code, 0)
        self.assertIn("20", out)

    def test_pickers_read_the_figure_not_the_preamble(self):
        fixture = ('log line\n'
                   '{"n_attacks": 36, "n_caught": 34, "isolated": [1, 2, 3, 4], '
                   '"unreached": []}\n')
        got = br.pick_matrix(fixture, 0)
        self.assertIn("attacks=36", got)
        self.assertIn("isolated=4", got)
        self.assertIn("unreached=0", got)
        self.assertEqual(br.pick_result('{"result": "INCONCLUSIVE"}', 1),
                         "result=INCONCLUSIVE")

    def test_the_sheet_names_what_it_cannot_cover(self):
        rows = [{"table": "x", "what": "y", "command": "python3 -c 1",
                 "output": "z", "exit": 0}]
        doc = br.render(rows)
        self.assertIn("What this sheet does not cover", doc)
        self.assertIn("absence", doc)


if __name__ == "__main__":
    unittest.main()
