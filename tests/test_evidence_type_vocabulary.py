import json
import os
import shutil
import tempfile
import unittest

from uibc_core.verify import verify

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(_REPO, "fixtures", "clean.uibc")


class TestAnUnknownEvidenceTypeIsNotAFailure(unittest.TestCase):
    """Found 2026-11-19 by running the M1 migration vector (0.3.3 -> 0.4.0).

    0.3.3 offered `evidence --type TYPE` as a free-form string: no enum, and no
    vocabulary in its --help. A package sealed by that release therefore
    carries types the current verifier does not know, and the verifier used to
    report them as FAIL - "I checked, and this is wrong".

    That is not available as a verdict. The package cannot violate a rule that
    did not exist when it was sealed, and the verifier has not checked the type
    against anything. The honest result is INCONCLUSIVE, the same asymmetry
    VERSIONING.md already requires for unknown fields.
    """

    def _package_with_type(self, new_type):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(BASE, pkg)
        path = os.path.join(pkg, "evidence", "index.json")
        doc = json.load(open(path, encoding="utf-8"))
        doc["entries"][0]["type"] = new_type
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        return pkg

    def _checks(self, pkg):
        report = verify(pkg)
        return report, {c["id"]: c for c in report["checks"]}

    def test_a_legacy_type_string_is_inconclusive_not_a_failure(self):
        report, checks = self._checks(self._package_with_type("action-log"))
        self.assertEqual(checks["S4"]["result"], "INCONCLUSIVE", checks["S4"]["detail"])
        self.assertIn("action-log", checks["S4"]["detail"])
        self.assertNotEqual(report["result"], "FAIL")
        self.assertNotEqual(report["result"], "PASS",
                            "an entry nobody judged must not land on a top-level PASS")

    def test_a_known_type_still_passes(self):
        report, checks = self._checks(self._package_with_type("ACTION"))
        self.assertEqual(checks["S4"]["result"], "PASS", checks["S4"]["detail"])

    def test_a_hash_mismatch_is_still_a_failure(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(BASE, pkg)
        index = os.path.join(pkg, "evidence", "index.json")
        doc = json.load(open(index, encoding="utf-8"))
        rel = doc["entries"][0]["path"]
        with open(os.path.join(pkg, "evidence", rel), "a", encoding="utf-8") as fh:
            fh.write("\ntampered\n")
        _, checks = self._checks(pkg)
        self.assertEqual(checks["S4"]["result"], "FAIL", checks["S4"]["detail"])


if __name__ == "__main__":
    unittest.main()
