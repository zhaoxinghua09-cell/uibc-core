"""Value-level checks in the independent verifier (V10).

Regression guard for the two defects found on 2026-11-21:

1. `independent_verifier/iverify.py` had no entry point, so callers that shelled
   out to it read exit code 0 unconditionally and recorded "independent=PASS"
   without a verification having run.
2. V1-V9 were structural: a timestamp with no zone, an impossible date
   (1900-02-29) and an uppercase UUID were all accepted.

Both are now checked here at the API level, which is what the callers use.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from independent_verifier.iverify import independent_verify  # noqa: E402

# A package that is in the repository, not one built on a developer's machine:
# `benchmark/corpus/base` is generated and not tracked, so a clone (and CI)
# has no copy of it. `anchors/001/package` is tracked, has the same three
# fields these checks touch (manifest.created_at, lifecycle events[0]
# .timestamp and .event_id), and is the same example the outsider run uses.
BASE = os.path.join(REPO, "anchors", "001", "package")


def _copy_base():
    tmp = tempfile.mkdtemp(prefix="v10-")
    dst = os.path.join(tmp, "pkg")
    shutil.copytree(BASE, dst)
    return tmp, dst


def _set(path, mutate):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    mutate(doc)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


class ValueLevel(unittest.TestCase):
    def test_clean_package_is_not_rejected_by_v10(self):
        tmp, pkg = _copy_base()
        self.addCleanup(shutil.rmtree, tmp, True)
        rep = independent_verify(pkg)
        self.assertEqual(rep["checks"]["V10"], "PASS", rep)
        self.assertNotEqual(rep["result"], "FAIL")

    def test_timestamp_without_zone_is_rejected(self):
        tmp, pkg = _copy_base()
        self.addCleanup(shutil.rmtree, tmp, True)
        _set(os.path.join(pkg, "lifecycle.json"),
             lambda d: d["events"][0].__setitem__("timestamp", "2026-11-17T05:59:59"))
        rep = independent_verify(pkg)
        self.assertEqual(rep["checks"]["V10"], "FAIL", rep)

    def test_impossible_date_is_rejected(self):
        tmp, pkg = _copy_base()
        self.addCleanup(shutil.rmtree, tmp, True)
        _set(os.path.join(pkg, "manifest.json"),
             lambda d: d.__setitem__("created_at", "1900-02-29T00:00:00Z"))
        rep = independent_verify(pkg)
        self.assertEqual(rep["checks"]["V10"], "FAIL", rep)

    def test_uppercase_uuid_is_rejected(self):
        tmp, pkg = _copy_base()
        self.addCleanup(shutil.rmtree, tmp, True)
        _set(os.path.join(pkg, "lifecycle.json"),
             lambda d: d["events"][0].__setitem__(
                 "event_id", "93E2FFBE-893A-4B13-9A34-5C36D9C8B138"))
        rep = independent_verify(pkg)
        self.assertEqual(rep["checks"]["V10"], "FAIL", rep)


if __name__ == "__main__":
    unittest.main()
