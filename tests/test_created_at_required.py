"""`manifest.created_at` is required, and required means judged.

The S12 walker checks a timestamp only when it is present -- that is what makes
it a walker rather than a schema. So the required field itself had no check:
a manifest could carry `created_at: "yesterday"`, or carry no `created_at` at
all, and the package stayed INCONCLUSIVE at worst and PASS at best.

These tests pin both halves of one rule, on the clean fixture: a missing time
and an impossible time fail the same check (S12), and a real time does not.
They also pin the ordering the oracle table depends on: S12 is later than
S1/S4/S5, so nothing here may steal a first failure from an earlier check.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO)

from uibc_core.verify import verify, _rfc3339_ok  # noqa: E402

BASE = os.path.join(_REPO, "fixtures", "clean.uibc")


def _checks_after_manifest_edit(fn):
    """Copy the clean fixture, edit manifest.json, return {check_id: check}."""
    tmp = tempfile.mkdtemp()
    pkg = os.path.join(tmp, "pkg")
    shutil.copytree(BASE, pkg)
    path = os.path.join(pkg, "manifest.json")
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    fn(doc)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    try:
        return {c["id"]: c for c in verify(pkg)["checks"]}
    finally:
        shutil.rmtree(tmp, True)


class TestTheHelperJudgesValues(unittest.TestCase):
    def test_a_real_time_is_a_real_time(self):
        for good in ("2026-11-21T10:00:00Z", "2026-11-21T10:00:00+08:00",
                     "2026-11-21T10:00:00.123456Z", "2024-02-29T00:00:00Z"):
            self.assertTrue(_rfc3339_ok(good), good)

    def test_the_impossible_ones_are_impossible(self):
        for bad in ("", "2026-11-21 10:00:00Z", "2026-11-21T10:00:00",       # shape
                    "2026-13-01T00:00:00Z", "2026-02-30T00:00:00Z",          # calendar
                    "1900-02-29T00:00:00Z", "2026-11-21T10:00:60Z",           # leap second
                    "2026-11-21T10:00:00+15:00", "2026-11-21T10:00:00+14:30",  # offset
                    "2026-11-21t10:00:00z", 20261121, None):
            self.assertFalse(_rfc3339_ok(bad), repr(bad))


class TestTheRequiredFieldIsChecked(unittest.TestCase):
    def test_a_clean_package_still_passes_that_check(self):
        checks = _checks_after_manifest_edit(lambda d: None)
        self.assertEqual(checks["S12"]["result"], "PASS", checks["S12"]["detail"])

    def test_a_missing_created_at_fails_semantics(self):
        checks = _checks_after_manifest_edit(lambda d: d.pop("created_at", None))
        self.assertEqual(checks["S12"]["result"], "FAIL", checks["S12"]["detail"])
        self.assertIn("created_at", checks["S12"]["detail"])

    def test_an_impossible_created_at_fails_semantics(self):
        checks = _checks_after_manifest_edit(
            lambda d: d.__setitem__("created_at", "2026-02-30T00:00:00Z"))
        self.assertEqual(checks["S12"]["result"], "FAIL", checks["S12"]["detail"])
        self.assertIn("created_at", checks["S12"]["detail"])

    def test_a_zone_less_created_at_fails_semantics(self):
        checks = _checks_after_manifest_edit(
            lambda d: d.__setitem__("created_at", "2026-11-21T10:00:00"))
        self.assertEqual(checks["S12"]["result"], "FAIL", checks["S12"]["detail"])

    def test_a_structural_failure_is_still_reported_first(self):
        """S4 owns "was this byte changed?"; this check must not jump the queue.

        The oracle table's first-failure column depends on check order, so an
        S12 rule that fired before S4 would silently rewrite those rows.
        """
        tmp = tempfile.mkdtemp()
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(BASE, pkg)
        try:
            with open(os.path.join(pkg, "evidence", "index.json"), encoding="utf-8") as fh:
                entry = json.load(fh)["entries"][0]["path"]
            with open(os.path.join(pkg, "evidence", entry), "a", encoding="utf-8") as fh:
                fh.write(" ")
            checks = {c["id"]: c for c in verify(pkg)["checks"]}
        finally:
            shutil.rmtree(tmp, True)
        failed = sorted((c["id"] for c in checks.values()
                         if c["result"] == "FAIL" and c["id"][1:].isdigit()),
                        key=lambda i: int(i[1:]))
        self.assertIn("S4", failed, "a changed payload should still fail S4")
        self.assertEqual(failed[0], "S4",
                         "S12 stole the first failure: %s" % failed)


if __name__ == "__main__":
    unittest.main()
