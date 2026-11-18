"""The outsider audit must fail when it should, and pass when it should.

Two failure modes matter more than coverage here:

  - a harness that reports OK because every mutation silently failed to apply
    (that is what happened on the first run of this tool: the shipped index is
    a bare list, our writer assumed {"entries": [...]}, and three mutations
    raised before touching anything);
  - a harness that turns the unsigned baseline into PASS to make the table
    look green.

Both are asserted against, below.
"""

import json
import os
import subprocess
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
_TOOLS = os.path.join(_REPO, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import outsider_audit as oa  # noqa: E402

PKG = os.path.join(_REPO, "fixtures", "clean.uibc")


class TestOutsiderAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = oa.run_all(PKG, kit=None)

    def test_baseline_is_inconclusive_not_pass(self):
        b = self.result["stage_baseline"]
        self.assertEqual(b["got"]["result"], "INCONCLUSIVE",
                         "the fixture is unsigned; PASS here would be a lie")
        self.assertEqual(b["got"]["trust_level"], "unattested")
        self.assertTrue(b["ok"])

    def test_every_attack_is_caught(self):
        rows = self.result["stage_redteam"]["rows"]
        attacks = [r for r in rows if r["kind"] == "attack"]
        self.assertEqual(len(attacks), 11)
        for r in attacks:
            with self.subTest(attack=r["name"]):
                self.assertIsNone(r["mutation_error"],
                                 "a mutation that did not apply proves nothing")
                self.assertTrue(r["ok"], "%s was not caught (got %s)"
                                % (r["name"], r["got"]))

    def test_no_check_may_be_decorative(self):
        """At least one named check must actually fire for every attack."""
        for r in self.result["stage_redteam"]["rows"]:
            if r["kind"] != "attack" or r["expectation"] != "FAIL":
                continue
            with self.subTest(attack=r["name"]):
                self.assertTrue(r["failed_checks"],
                                "%s produced FAIL with no failing check" % r["name"])

    def test_controls_do_not_move_the_verdict(self):
        controls = [r for r in self.result["stage_redteam"]["rows"]
                    if r["kind"] == "control"]
        self.assertEqual(len(controls), 2)
        for r in controls:
            with self.subTest(control=r["name"]):
                self.assertIsNone(r["mutation_error"])
                self.assertTrue(r["ok"], "%s changed the verdict to %s"
                                % (r["name"], r["got"]))
                if r["name"].startswith("reorder"):
                    self.assertEqual(r["got"], "INCONCLUSIVE",
                                     "reordering must not be a forgery: the root "
                                     "commits sorted hashes, not file order")

    def test_the_tree_and_the_chain_are_attacked_too(self):
        """The old red team only attacked a package with no tree and no chain,
        so S13 and S17 never ran. Six new cases build both correctly and break
        one at a time."""
        v11 = self.result["stage_redteam_v11"]
        self.assertEqual(v11["count"], 6)
        self.assertTrue(v11["ok"], "failed: %s" % v11["failed"])
        caught = set()
        for r in v11["rows"]:
            self.assertTrue(r["ok"], "%s -> %s (%s)"
                            % (r["name"], r["got"], r["expectation_note"]))
            caught.update(r["failed_checks"])
        self.assertIn("S13", caught, "the Merkle cases must be caught by S13")
        self.assertIn("S17", caught, "the chain cases must be caught by S17")

    def test_the_untested_tail_is_declared_not_hidden(self):
        """Editing the LAST receipt breaks no existing link, so the package
        cannot catch it. It is listed as a known gap, not as a catch -- and if
        it ever becomes caught, this test says to update the note."""
        gaps = self.result["stage_redteam_v11"]["known_gaps"]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["got"], "INCONCLUSIVE")
        self.assertFalse(gaps[0]["caught"],
                         "this gap is now caught; update the note and the docs")

    def test_skip_is_not_a_pass(self):
        it = self.result["stage_interop"]
        self.assertEqual(it["status"], "SKIPPED")
        self.assertIsNone(it["ok"], "a skipped stage must not count as ok")

    def test_cli_json_is_machine_readable_and_exit_code_is_honest(self):
        p = subprocess.run([sys.executable,
                            os.path.join(_TOOLS, "outsider_audit.py"), "--json"],
                           cwd=_REPO, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr.decode()[-800:])
        out = json.loads(p.stdout)
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage_baseline"]["got"]["result"], "INCONCLUSIVE")
        self.assertEqual(out["stage_interop"]["status"], "SKIPPED")


if __name__ == "__main__":
    unittest.main()
