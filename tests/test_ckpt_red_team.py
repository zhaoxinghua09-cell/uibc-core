"""The four checks the evidence index found with no attack pointed at them.

S7 (index metadata), S8 (whole-state checkpoint), S9 (out-of-band pin) and S10
(closure declared) were implemented but never attacked. A check with no attack
has not been shown to work, only to exist. These tests hold the attacks in
place, including the one that cannot come from inside a package at all.
"""

import os
import shutil
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

sys.path.insert(0, os.path.join(_REPO, "tools"))
import outsider_audit as oa

PKG = os.path.join(_REPO, "fixtures", "clean.uibc")


class TestCheckpointRedTeam(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_baseline_with_sealed_fields_passes_the_four(self):
        """The attacks are only meaningful if the unmodified package passes."""
        pkg = oa._prepare(PKG, self.tmp)
        oa.build_ckpt(pkg)          # raises if S7/S8/S10 are not PASS
        self.assertTrue(True)

    def test_rewriting_index_metadata_is_caught(self):
        """Content bytes untouched; only the entry's own note changes."""
        stage = oa.run_red_team_ckpt(PKG, "INCONCLUSIVE")
        row = next(r for r in stage["rows"]
                   if r["name"].startswith("rewrite index metadata"))
        self.assertTrue(row["ok"], row)
        self.assertEqual(row["got"], "FAIL")
        self.assertIn("S7", row["failed_checks"])

    def test_a_truncated_log_is_caught(self):
        """The shorter chain is internally valid; the checkpoint is not."""
        stage = oa.run_red_team_ckpt(PKG, "INCONCLUSIVE")
        row = next(r for r in stage["rows"] if r["name"].startswith("truncate"))
        self.assertTrue(row["ok"], row)
        self.assertEqual(row["failed_checks"], ["S8"])

    def test_a_closure_with_five_of_six_is_caught(self):
        stage = oa.run_red_team_ckpt(PKG, "INCONCLUSIVE")
        for name in ("drop engine_build", "declare a closure digest"):
            row = next(r for r in stage["rows"] if r["name"].startswith(name))
            self.assertTrue(row["ok"], row)
            self.assertEqual(row["failed_checks"], ["S10"], name)

    def test_every_ckpt_attack_is_caught(self):
        stage = oa.run_red_team_ckpt(PKG, "INCONCLUSIVE")
        self.assertTrue(stage["ok"])
        self.assertEqual(stage["failed"], [])
        self.assertEqual(stage["count"], 4)

    def test_the_true_head_satisfies_its_own_pin(self):
        stage = oa.run_pinned(PKG, "INCONCLUSIVE")
        control = stage["rows"][0]
        self.assertTrue(control["ok"], control)
        self.assertEqual(control["got"], "PASS")

    def test_a_rolled_back_package_against_the_old_pin_is_caught(self):
        """S9 exists for exactly this and nothing inside the package can do it."""
        stage = oa.run_pinned(PKG, "INCONCLUSIVE")
        attack = stage["rows"][1]
        self.assertTrue(attack["ok"], attack)
        self.assertEqual(attack["got"], "FAIL")
        self.assertEqual(attack["failed_checks"], ["S9"])

    def test_s9_is_absent_without_a_pin(self):
        """No pin, no S9 line: 'unpinned' is not 'pinned and matching'."""
        from uibc_core.verify import verify
        checks = {c["id"] for c in verify(PKG)["checks"]}
        self.assertNotIn("S9", checks)


if __name__ == "__main__":
    unittest.main()
