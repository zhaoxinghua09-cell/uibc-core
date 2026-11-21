"""S12 semantic strictness: a hash-perfect log can still order nothing.

AER-1's corpus marks these as must-fail; before S12 we hashed such files happily
(the bytes were intact, so S4/S5/S7 all passed). Each case below is a package that
is *internally consistent by construction* except for one value, which is exactly
the shape of forgery a value-level check must catch.
"""
import json
import os
import shutil
import tempfile
import unittest

from uibc_core.verify import verify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "benchmark", "corpus", "base")


def _ids(rep):
    return {c["id"]: c["result"] for c in rep["checks"]}


class TestSemanticStrictness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s12-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        shutil.copytree(BASE, self.pkg)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _edit(self, rel, mutate):
        p = os.path.join(self.pkg, rel)
        doc = json.load(open(p, encoding="utf-8"))
        mutate(doc)
        open(p, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False,
                                                        indent=2))

    def _assert_fails(self, check="S12"):
        rep = verify(self.pkg)
        self.assertEqual(_ids(rep).get(check), "FAIL", rep["checks"])
        self.assertEqual(rep["result"], "FAIL")

    def test_clean_package_passes_s12(self):
        rep = verify(self.pkg)
        self.assertEqual(_ids(rep).get("S12"), "PASS", rep["checks"])

    def test_timestamp_without_timezone_fails(self):
        self._edit("lifecycle.json",
                   lambda d: d["events"][0].__setitem__("timestamp",
                                                       "2026-11-17T05:59:59"))
        self._assert_fails()

    def test_lowercase_t_fails(self):
        self._edit("manifest.json",
                   lambda d: d.__setitem__("created_at", "2026-11-17t05:59:59Z"))
        self._assert_fails()

    def test_feb29_1900_fails(self):
        # 1900 is divisible by 4 but not a leap year: the classic trap.
        self._edit("manifest.json",
                   lambda d: d.__setitem__("created_at", "1900-02-29T00:00:00Z"))
        self._assert_fails()

    def test_leap_second_fails_by_policy(self):
        self._edit("manifest.json",
                   lambda d: d.__setitem__("created_at", "2026-11-17T05:59:60Z"))
        self._assert_fails()

    def test_nil_uuid_fails(self):
        self._edit("lifecycle.json",
                   lambda d: d["events"][0].__setitem__(
                       "event_id", "00000000-0000-0000-0000-000000000000"))
        self._assert_fails()

    def test_uppercase_uuid_fails(self):
        self._edit("lifecycle.json",
                   lambda d: d["events"][0].__setitem__(
                       "event_id", "93E2FFBE-893A-4B13-9A34-5C36D9C8B138"))
        self._assert_fails()

    def test_non_uuid_identifier_is_not_flagged(self):
        # 'mb-agent-001' is legal in our schema; flagging it would be a false
        # positive, and a check that cries wolf gets switched off.
        rep = verify(self.pkg)
        self.assertIn("mb-agent-001", json.dumps(rep))
        self.assertEqual(_ids(rep).get("S12"), "PASS")


if __name__ == "__main__":
    unittest.main()
