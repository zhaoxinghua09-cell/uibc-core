"""S10 attestation closure: declare it, or fail - but never pretend to verify it.

draft-sharif-agent-audit-trail-03 Section 13.6 argues that every component left
outside the attested set is a forgery channel, and lists six: model weights,
tokenizer, chat template, engine build, decoding configuration, numeric
environment. A package cannot prove those digests match what actually ran; it can
only prove the submitter declared all six and that nobody edited the declaration
after sealing. These tests pin exactly that boundary.
"""
import json
import os
import shutil
import tempfile
import unittest

from uibc_core.verify import CLOSURE_FIELDS, verify

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "benchmark", "corpus", "base")
FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "fixtures")


def _copytree(src, dst):
    shutil.copytree(src, dst)


class TestClosure(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="closure-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        _copytree(BASE, self.pkg)

    def _patch(self, closure):
        mp = os.path.join(self.pkg, "manifest.json")
        m = json.load(open(mp, encoding="utf-8"))
        m["closure"] = closure
        json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def test_full_closure_is_reported_pass(self):
        _ = [self._patch({k: "sha256:" + "ab" * 32 for k in CLOSURE_FIELDS})]
        rep = verify(self.pkg)
        ids = {c["id"]: c["result"] for c in rep["checks"]}
        self.assertEqual(ids.get("S10"), "PASS", rep["checks"])

    def test_missing_component_fails(self):
        self._patch({k: "sha256:" + "ab" * 32 for k in CLOSURE_FIELDS[:-1]})
        rep = verify(self.pkg)
        ids = {c["id"]: c["result"] for c in rep["checks"]}
        self.assertEqual(ids.get("S10"), "FAIL")
        self.assertEqual(rep["result"], "FAIL")

    def test_garbage_digest_fails(self):
        good = {k: "sha256:" + "ab" * 32 for k in CLOSURE_FIELDS}
        good["engine_build"] = "not-a-digest"
        self._patch(good)
        rep = verify(self.pkg)
        self.assertEqual({c["id"]: c["result"] for c in rep["checks"]}.get("S10"), "FAIL")

    def test_no_closure_means_no_s10(self):
        rep = verify(self.pkg)
        self.assertNotIn("S10", {c["id"] for c in rep["checks"]})

    def test_declared_closure_does_not_upgrade_trust(self):
        self._patch({k: "sha256:" + "ab" * 32 for k in CLOSURE_FIELDS})
        rep = verify(self.pkg)
        # a declared closure must not be read as provenance: the level still
        # depends on how the key reached the verifier, not on what was declared
        self.assertIn(rep["trust_level"], ("unanchored", "unattested"))


if __name__ == "__main__":
    unittest.main()
