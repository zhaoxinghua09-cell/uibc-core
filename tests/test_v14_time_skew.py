"""S12 future-skew bound (draft-marques-asqav-compliance-receipts-01 section 4.1.2).

The clause has two halves and both are tested, because a one-sided rule is easy
to implement backwards:

  * a timestamp more than 300 s ahead of the verifier's clock is rejected;
  * a timestamp in the past is NOT rejected for being old - "historical receipts
    within retention MUST verify on the same path as fresh ones".

The clock is injected rather than slept on, so these tests neither wait nor rot.
"""

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from uibc_core.verify import _semantic_problems, verify

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "fixtures", "clean.uibc")


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FutureSkewUnitTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 17, 9, 0, 0, tzinfo=timezone.utc)

    def _problems(self, when, **kw):
        kw.setdefault("now", self.now)
        return _semantic_problems({"issued_at": _iso(when)}, **kw)

    def test_one_hour_ahead_is_rejected(self):
        p = self._problems(self.now + timedelta(hours=1))
        self.assertTrue(p)
        self.assertIn("in the future", p[0])

    def test_250s_ahead_is_accepted(self):
        self.assertEqual(self._problems(self.now + timedelta(seconds=250)), [])

    def test_350s_ahead_is_rejected(self):
        self.assertTrue(self._problems(self.now + timedelta(seconds=350)))

    def test_past_timestamp_is_not_rejected_on_age(self):
        self.assertEqual(self._problems(self.now - timedelta(days=3650)), [])

    def test_bound_is_configurable(self):
        self.assertEqual(self._problems(self.now + timedelta(seconds=350),
                                        future_skew_s=3600), [])

    def test_no_clock_means_no_skew_check(self):
        # Callers that do not supply a clock keep the pre-v1.1 behaviour; the
        # verifier always supplies one, but the function stays usable in
        # isolation (e.g. by a schema linter with no wall clock).
        self.assertEqual(self._problems(self.now + timedelta(hours=5), now=None), [])


class FutureSkewPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="skew-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        shutil.copytree(BASE, self.pkg)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_package_with_future_stamp_is_flagged_by_s12(self):
        man_path = os.path.join(self.pkg, "manifest.json")
        with open(man_path, "r", encoding="utf-8") as f:
            man = json.load(f)
        future = datetime.now(timezone.utc) + timedelta(hours=6)
        for key in ("created_at", "updated_at", "timestamp", "issued_at"):
            if key in man:
                man[key] = _iso(future)
                break
        else:
            self.skipTest("fixture manifest carries no time key")
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(man, f, ensure_ascii=False)

        rep = verify(self.pkg)
        checks = {c["id"]: c for c in rep["checks"]}
        self.assertIn("S12", checks)
        self.assertEqual(checks["S12"]["result"], "FAIL", checks["S12"])
        self.assertIn("future", checks["S12"]["detail"])


if __name__ == "__main__":
    unittest.main()
