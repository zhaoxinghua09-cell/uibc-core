"""The conformance suite has to be able to fail, or it is decoration.

Two things are checked here beyond "the suite runs": that the packages in the
archive are the ones the manifest describes, and that a verifier which refuses
nothing is caught. A suite that a rubber stamp passes is not a suite.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_conformance as rc  # noqa: E402

CONF = os.path.join(_REPO, "conformance")
MANIFEST = os.path.join(CONF, "manifest.json")


def load():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


class TestConformanceSuite(unittest.TestCase):
    def test_manifest_has_cases_and_no_gaps(self):
        man = load()
        self.assertGreaterEqual(len(man["cases"]), 29)
        self.assertEqual(man["skipped"], [])
        for case in man["cases"]:
            self.assertTrue(case["expected_checks"], case["attack"])
            self.assertIn(case["expected_result"], ("FAIL", "INCONCLUSIVE"))

    def test_every_expected_check_is_a_real_check(self):
        from uibc_core.basis import BASIS
        ids = set(BASIS)
        man = load()
        for case in man["cases"]:
            for cid in case["expected_checks"]:
                self.assertIn(cid, ids, case["attack"])

    def test_archive_matches_manifest_digests(self):
        man = load()
        tmp = tempfile.mkdtemp(prefix="uibc-cc-zip-")
        try:
            with zipfile.ZipFile(os.path.join(CONF, man["archive"])) as z:
                z.extractall(tmp)
            for case in man["cases"]:
                pkg = os.path.join(tmp, case["path"])
                self.assertTrue(os.path.isdir(pkg), case["path"])
                self.assertEqual(_digest(pkg), case["sha256"],
                                 "%s: archive drifted from the manifest" % case["path"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_our_verifier_passes_every_case(self):
        res = rc.run_all(rc.our_verifier)
        self.assertEqual(res["passed"], res["cases"])

    def test_a_rubber_stamp_verifier_fails(self):
        """A verifier that refuses nothing must not pass the suite."""
        def always_pass(_pkg):
            return {"result": "PASS", "checks": []}
        res = rc.run_all(always_pass)
        self.assertEqual(res["passed"], 0)

    def test_the_positive_control_is_not_refused(self):
        """Every case is broken; the clean package must still be accepted."""
        got = rc.our_verifier(os.path.join(_REPO, "fixtures", "clean.uibc"))
        self.assertNotEqual(got["result"], "FAIL")


def _digest(pkg):
    import hashlib
    h = hashlib.sha256()
    for root, dirs, files in os.walk(pkg):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, pkg).replace("\\", "/")
            h.update(rel.encode())
            h.update(b"\0")
            with open(full, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


if __name__ == "__main__":
    unittest.main()
