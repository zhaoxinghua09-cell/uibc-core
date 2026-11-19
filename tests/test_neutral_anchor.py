"""One token, several ecosystems.

These tests use a fixture produced on 2026-11-20 by a throwaway local CA and
OpenSSL's `ts` command (see `docs/PROPOSAL-BIND-NEUTRAL-ANCHOR.md`). The CA is
test material: it is committed so the tests need no network and no TSA, and it
carries no authority beyond this repository.
"""

import json
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core import neutral_anchor as na  # noqa: E402

_FIX = os.path.join(_REPO, "tests", "fixtures", "neutral-anchor")


def _load():
    with open(os.path.join(_FIX, "anchor.json"), encoding="utf-8") as f:
        return json.load(f)


class TestNeutralAnchor(unittest.TestCase):
    def test_canonical_bytes_are_reproducible_without_a_library(self):
        subjects = [na.entry("b/1", "00" * 32, "x"), na.entry("a/1", "11" * 32, "y")]
        body = na.canonical_bytes(subjects)
        self.assertTrue(body.startswith(b"[{"))
        self.assertNotIn(b" ", body)
        # keys inside each object are sorted, so the same input always gives the
        # same bytes and an outside verifier can recompute the digest
        again = na.canonical_bytes([dict(reversed(list(s.items()))) for s in subjects])
        self.assertEqual(body, again)

    def test_the_fixture_verifies(self):
        verdict, detail = na.verify(_load(), _FIX)
        self.assertEqual(verdict, "PASS")
        self.assertEqual(len(detail["subjects"]), 2)
        self.assertIn("uibc-checkpoint-head/0.4", detail["subjects"])

    def test_a_changed_digest_is_refused(self):
        env = _load()
        env["subjects"][0]["digest"] = "00" * 32
        env.pop("subject_digest_sha256", None)
        verdict, detail = na.verify(env, _FIX)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("does not cover", detail["why"])

    def test_order_matters(self):
        env = _load()
        env["subjects"] = list(reversed(env["subjects"]))
        env.pop("subject_digest_sha256", None)
        verdict, detail = na.verify(env, _FIX)
        self.assertEqual(verdict, "FAIL")

    def test_a_self_consistent_but_wrong_digest_field_is_caught(self):
        env = _load()
        env["subject_digest_sha256"] = "ab" * 32
        verdict, detail = na.verify(env, _FIX)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("different subject digest", detail["why"])

    def test_missing_material_is_declined_not_passed(self):
        env = _load()
        env["tsr"] = "timestamps/absent.tsr"
        verdict, detail = na.verify(env, _FIX)
        self.assertEqual(verdict, "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
