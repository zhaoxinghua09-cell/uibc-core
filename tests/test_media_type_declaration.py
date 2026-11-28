"""S20 — a declared media type must be one this project is willing to repeat.

Measured 2026-11-28: `evidence/index.json` entries carry a `media_type` that
neither S4 (bytes) nor S7 (index metadata digest) covered, and the verifier
never read it. Relabelling an evidence file's media type therefore passed every
check while the index went on declaring something the file was not. S4 still
binds the bytes, so this is not a content-substitution hole; it is a labelling
hole: a reader who decides *how to open* an artefact on the strength of the
declaration could be steered.

The check is deliberately narrow - vocabulary only, no extension guessing -
because a closed list is auditable and an inferred rule is not.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO)

from uibc_core.verify import verify  # noqa: E402

CASE = os.path.join(_REPO, "conformance", "cases", "06-a-package-sealed-with-ed25519")


def _copy_case(tmp):
    pkg = os.path.join(tmp, "pkg")
    shutil.copytree(CASE, pkg)
    return pkg


def _check(report, cid):
    for c in report["checks"]:
        if c["id"] == cid:
            return c
    return None


class TestMediaTypeDeclaration(unittest.TestCase):
    def test_the_shipped_case_passes_s20(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = verify(_copy_case(tmp))
        c = _check(rep, "S20")
        self.assertIsNotNone(c, "S20 must always be reported")
        self.assertEqual(c["result"], "PASS")
        self.assertNotIn("S20", rep.get("failed_checks") or [])

    def test_relabelled_media_type_fails_s20(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _copy_case(tmp)
            idx_path = os.path.join(pkg, "evidence", "index.json")
            with open(idx_path, encoding="utf-8") as fh:
                idx = json.load(fh)
            idx["entries"][0]["media_type"] = "application/x-bogus-media"
            with open(idx_path, "w", encoding="utf-8") as fh:
                json.dump(idx, fh, ensure_ascii=False)
            rep = verify(pkg)
        self.assertEqual(rep["result"], "FAIL")
        self.assertTrue(any(c["id"] == "S20" and c["result"] == "FAIL"
                            for c in rep["checks"]))

    def test_absent_media_type_is_not_a_failure(self):
        # Older packages legitimately omit the field; failing on absence would
        # break verifying anything sealed before 0.3.
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _copy_case(tmp)
            idx_path = os.path.join(pkg, "evidence", "index.json")
            with open(idx_path, encoding="utf-8") as fh:
                idx = json.load(fh)
            idx["entries"][0].pop("media_type", None)
            with open(idx_path, "w", encoding="utf-8") as fh:
                json.dump(idx, fh, ensure_ascii=False)
            rep = verify(pkg)
        c = _check(rep, "S20")
        self.assertEqual(c["result"], "PASS")
        self.assertNotIn("S20", rep.get("failed_checks") or [])

    def test_non_string_media_type_fails_s20(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _copy_case(tmp)
            idx_path = os.path.join(pkg, "evidence", "index.json")
            with open(idx_path, encoding="utf-8") as fh:
                idx = json.load(fh)
            idx["entries"][0]["media_type"] = ["text/plain"]
            with open(idx_path, "w", encoding="utf-8") as fh:
                json.dump(idx, fh, ensure_ascii=False)
            rep = verify(pkg)
        self.assertEqual(_check(rep, "S20")["result"], "FAIL")
        self.assertTrue(any(c["id"] == "S20" and c["result"] == "FAIL"
                            for c in rep["checks"]))


if __name__ == "__main__":
    unittest.main()
