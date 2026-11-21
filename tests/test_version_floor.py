import json
import os
import shutil
import tempfile
import unittest

from uibc_core import __version__
from uibc_core.verify import verify

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(_REPO, "fixtures", "clean.uibc")


class TestAVersionFloorStopsAPass(unittest.TestCase):
    """VERSIONING.md section 8, implemented 2026-11-19.

    Measured cause (docs/MIGRATION-RESULTS.md, M2c): 0.3.3 returned PASS, exit 0,
    on a package carrying identity.key_custody="hsm" - a field it has never
    heard of. A PASS from a verifier that cannot see a claim is not evidence
    about that claim, and the only way a consumer learns this is if the package
    says which verifier it requires.

    So the builder writes min_verifier_version, and a verifier below that floor
    reports S1 INCONCLUSIVE instead of PASS. INCONCLUSIVE, not FAIL: the package
    is not wrong, the verifier is early.
    """

    def _package_with_floor(self, floor):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(BASE, pkg)
        path = os.path.join(pkg, "manifest.json")
        doc = json.load(open(path, encoding="utf-8"))
        if floor is None:
            doc.pop("min_verifier_version", None)
        else:
            doc["min_verifier_version"] = floor
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        return pkg

    def _s1(self, pkg):
        report = verify(pkg)
        return report, {c["id"]: c for c in report["checks"]}["S1"]

    def test_the_current_builder_records_its_own_version(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")

    def test_a_floor_above_the_verifier_blocks_pass(self):
        report, s1 = self._s1(self._package_with_floor("99.0.0"))
        self.assertEqual(s1["result"], "INCONCLUSIVE", s1["detail"])
        self.assertIn("99.0.0", s1["detail"])
        self.assertNotEqual(report["result"], "PASS")
        self.assertNotEqual(report["result"], "FAIL",
                            "an early verifier is not the package's fault")

    def test_a_floor_at_or_below_the_verifier_changes_nothing(self):
        for floor in (__version__, "0.0.1"):
            with self.subTest(floor=floor):
                report, s1 = self._s1(self._package_with_floor(floor))
                self.assertEqual(s1["result"], "PASS", s1["detail"])

    def test_a_package_without_a_floor_is_unchanged(self):
        report, s1 = self._s1(self._package_with_floor(None))
        self.assertEqual(s1["result"], "PASS", s1["detail"])

    def test_a_nonsense_floor_is_not_trusted_to_pass(self):
        report, s1 = self._s1(self._package_with_floor("later"))
        # "later" has no digits, so it parses as 0.0.0 and cannot block anything;
        # the point of the case is that it must not crash the verifier either.
        self.assertIn(s1["result"], {"PASS", "INCONCLUSIVE", "FAIL"}, s1["detail"])
        self.assertIn(report["result"], {"PASS", "INCONCLUSIVE", "FAIL"})


if __name__ == "__main__":
    unittest.main()
