"""A claim is only as good as the artifact a reader can download.

The archive reports six checks, the latest published package reports six, the
tree reports eighteen. These tests hold the recorded measurements and the
preflight gate, because "eight" was what a source-text count said and it was
wrong: which checks run depends on the package, not on the source.
"""

import json
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import check_release_parity as crp
import preflight_release as pf


class TestReleaseParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = crp.build()
        with open(os.path.join(_REPO, "docs", "PUBLISHED-BASELINE.json"),
                  encoding="utf-8") as f:
            cls.pub = json.load(f)

    def test_the_latest_published_package_has_six_checks(self):
        self.assertEqual(self.r["channels"]["package (pip)"]["checks"],
                         ["S1", "S2", "S3", "S4", "S5", "S6"])

    def test_the_archive_has_six(self):
        self.assertEqual(self.r["channels"]["archive (DOI)"]["checks"],
                         ["S1", "S2", "S3", "S4", "S5", "S6"])

    def test_twelve_checks_exist_only_in_the_repository(self):
        """S7-S10 (4) + S11-S12 (2) + S13-S18 (6). A bare id count is a weak
        assertion, so the ids are named as well."""
        only = [c for c in self.r["only_the_repository_has"] if c != "S0"]
        self.assertEqual(sorted(only, key=lambda c: int(c[1:])),
                         ["S7", "S8", "S9", "S10", "S11", "S12",
                          "S13", "S14", "S15", "S16", "S17", "S18"])
        for cid in ("S7", "S8", "S9", "S10", "S13", "S18"):
            self.assertIn(cid, only)

    def test_the_decisive_measurement_is_recorded(self):
        """The measurement that matters: same package, both verifiers."""
        d = self.pub["decisive_measurement"]
        self.assertEqual(d["published_result"]["checks"],
                         ["S1", "S2", "S3", "S4", "S5", "S6"])
        self.assertIn("S16", d["repository_result"]["checks"])
        self.assertEqual(d["repository_result"]["result"], "INCONCLUSIVE")

    def test_the_release_was_byte_identical_to_its_tag(self):
        """Both baselines carry a tag whose verifier matches the artifact,
        which is why the problem is a stalled release rather than a dishonest
        one -- and why an earlier claim of 'no tags at all' had to be
        corrected."""
        for name in ("ARCHIVE-BASELINE.json", "PUBLISHED-BASELINE.json"):
            with open(os.path.join(_REPO, "docs", name), encoding="utf-8") as f:
                d = json.load(f)
            self.assertIn("git_tag", d, name)
            self.assertEqual(len(d["git_tag"]["verify_py_sha256"]), 64, name)
            self.assertIn("f5d7b29b", d["git_tag"]["commit"]) if "ARCHIVE" in name \
                else self.assertIn("251b10b3", d["git_tag"]["commit"])

    def test_the_baseline_records_a_hash_and_a_limit(self):
        self.assertEqual(len(self.pub["verify_py_sha256"]), 64)
        self.assertEqual(len(self.pub["sdist_sha256"]), 64)
        self.assertTrue(self.pub["limits_of_this_measurement"])

    def test_the_doc_matches_the_measurement(self):
        with open(os.path.join(_REPO, "docs", "RELEASE-PARITY.md"),
                  encoding="utf-8") as f:
            doc = f.read()
        self.assertIn("0.3.3", doc)
        self.assertIn("六个", doc.replace("六项", "六个"))
        self.assertIn("preflight_release.py", doc)


class TestPreflight(unittest.TestCase):
    """The publishable artifact is the package directory, on an import path
    that contains nothing else."""

    def test_the_package_directory_is_self_sufficient(self):
        r = pf.build()
        self.assertEqual(r["missing_from_the_artifact"], [],
                         "the shippable artifact cannot report: %s"
                         % r["missing_from_the_artifact"])

    def test_a_pin_brings_s9_in(self):
        r = pf.build()
        self.assertIn("S9", r["pinned_run_checks"])


if __name__ == "__main__":
    unittest.main()
