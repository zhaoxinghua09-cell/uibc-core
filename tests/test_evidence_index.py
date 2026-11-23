"""The index is a claim about coverage, so it gets checked like one.

Its first version grepped the auditor for check ids and reported S3 as
uncovered -- the impossible-calendar-date case had been catching S3 all along.
A coverage report that is wrong about coverage is worse than none.
"""

import json
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import build_evidence_index as bei


class TestEvidenceIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = bei.build()
        cls.by_id = {r["id"]: r for r in cls.index["rows"]}

    def test_every_declared_check_appears(self):
        self.assertEqual(len(self.index["rows"]), self.index["check_count"])
        for cid in self.by_id:
            self.assertRegex(cid, r"^S\d+$")

    def test_red_team_is_measured_not_grepped(self):
        self.assertIsNone(self.index["red_team_measurement_error"])

    def test_every_real_check_is_caught_by_at_least_one_attack(self):
        """S0 is the crash fallback, not a check: nothing can be constructed
        to reach it except an input that breaks the verifier itself."""
        gaps = [r["id"] for r in self.index["rows"]
                if r["id"] != "S0" and not r["red_team"]]
        self.assertEqual(gaps, [], "checks with no attack: %s" % gaps)

    def test_every_real_check_has_a_test(self):
        gaps = [r["id"] for r in self.index["rows"]
                if r["id"] != "S0" and not r["tests"]]
        self.assertEqual(gaps, [], "checks with no test: %s" % gaps)

    def test_the_shipped_package_does_not_reach_past_the_seal(self):
        """If this ever changes, the index's 'reached' column stops meaning
        what the page says it means."""
        self.assertEqual(self.index["shipped_package_verdict"], "INCONCLUSIVE")

    def test_json_is_serialisable(self):
        json.dumps(self.index, ensure_ascii=False)

    def test_the_doc_in_the_repo_matches_a_fresh_build(self):
        path = os.path.join(_REPO, "docs", "EVIDENCE-INDEX.md")
        with open(path, encoding="utf-8") as f:
            stored = f.read()
        self.assertEqual(stored, bei.render(self.index),
                         "docs/EVIDENCE-INDEX.md is stale; rerun the tool")

    def test_check_says_what_it_means(self):
        # Measured 2026-11-24: `--check` was not an option at all, so it fell through
        # to "print the page, exit 0" -- a check that passed on a stale file, which
        # is how the 1105-vs-1107 mismatch reached CI. Both directions pinned here.
        import subprocess
        tool = os.path.join(_REPO, "tools", "build_evidence_index.py")
        ok = subprocess.run([sys.executable, tool, "--check"], capture_output=True,
                            text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        bad = subprocess.run([sys.executable, tool, "--no-such-flag"],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2, bad.stdout + bad.stderr)
        self.assertIn("unknown argument", bad.stderr)


if __name__ == "__main__":
    unittest.main()
