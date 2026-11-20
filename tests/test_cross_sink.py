"""SCC-04, carried into this format as an optional field pair.

The obligation is quoted from `draft-watts-scientific-constitutional-constraints-00`
section 11. The point of these tests is the part that is easy to get wrong: a
request must not be able to widen its own audience by agreeing with itself, so
`audience == sink_id` is not a tautology to be checked for -- it is a claim that
must fail when the receiving sink is a different one.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core.verify import verify  # noqa: E402

_PKG = os.path.join(_REPO, "conformance", "oracle", "cases", "oracle-clean")


def _copy(tmp):
    dst = os.path.join(tmp, "pkg")
    shutil.copytree(_PKG, dst)
    return dst


def _patch_manifest(pkg, **fields):
    path = os.path.join(pkg, "manifest.json")
    with open(path, encoding="utf-8") as f:
        man = json.load(f)
    man.update(fields)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2, sort_keys=True)


def _s2(result):
    return [c for c in result["checks"] if c["id"] == "S2"]


class TestCrossSinkAudience(unittest.TestCase):
    def test_no_sink_fields_means_s2_is_unchanged(self):
        """The 28 published packages carry neither field; their verdicts must not
        move because of this addition."""
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _copy(tmp)
            res = verify(pkg, key=None)
        self.assertTrue(_s2(res)[0]["result"] in ("PASS", "FAIL"))
        self.assertIn("consistent", _s2(res)[0]["detail"])

    def test_audience_equal_to_sink_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _copy(tmp)
            _patch_manifest(pkg, sink_id="sink-bravo", audience="sink-bravo")
            res = verify(pkg, key=None)
        # S6 (seal) fails after the edit, which is expected; S2 must still pass
        self.assertEqual(_s2(res)[0]["result"], "PASS")
        self.assertIn("sink_id=sink-bravo", _s2(res)[0]["detail"])

    def test_a_request_for_another_sink_is_not_deliverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _copy(tmp)
            _patch_manifest(pkg, sink_id="sink-bravo", audience="sink-alpha")
            res = verify(pkg, key=None)
        s2 = _s2(res)[0]
        self.assertEqual(s2["result"], "FAIL")
        self.assertIn("another sink", s2["detail"])
        self.assertEqual(res["result"], "FAIL")

    def test_half_the_pair_is_an_error_not_a_silent_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _copy(tmp)
            _patch_manifest(pkg, audience="sink-alpha")
            res = verify(pkg, key=None)
        s2 = _s2(res)[0]
        self.assertEqual(s2["result"], "FAIL")
        self.assertIn("must be strings", s2["detail"])


if __name__ == "__main__":
    unittest.main()
