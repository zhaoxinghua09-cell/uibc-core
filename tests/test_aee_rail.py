"""Corpus spot-checks for the AEE rail (``uibc_core.aee``).

The full conformance run is the harness in ``agent_evidence_vectors``
(288 vectors, driven externally); this file runs a handful of those same
vectors through the rail in-process so the repo suite carries a live
negative-control sample of the corpus. It skips cleanly when the corpus
package is not installed -- the rail itself is stdlib-only and never
depends on it.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

try:
    import agent_evidence_vectors

    _PKG_DIR = os.path.dirname(os.path.abspath(agent_evidence_vectors.__file__))
    _VECTORS_DIR = os.path.join(_PKG_DIR, "corpora", "vectors")
    _HAVE_CORPUS = os.path.isfile(os.path.join(_VECTORS_DIR, "MANIFEST.json"))
except Exception:
    _HAVE_CORPUS = False
    _VECTORS_DIR = ""

from uibc_core import aee


def _manifest():
    with open(os.path.join(_VECTORS_DIR, "MANIFEST.json"), encoding="utf-8") as f:
        return json.load(f)


def _entries(kind, limit):
    out = []
    for entry in _manifest()["vectors"]:
        if entry.get("kind") == kind:
            out.append(entry)
            if len(out) >= limit:
                break
    return out


def _path(entry):
    return os.path.join(_VECTORS_DIR, entry["file"])


@unittest.skipUnless(_HAVE_CORPUS, "agent_evidence_vectors corpus not installed")
class TestAeeRailCorpus(unittest.TestCase):
    def setUp(self):
        self._saved_env = os.environ.pop(aee.KEY_POLICY_ENV, None)

    def tearDown(self):
        os.environ.pop(aee.KEY_POLICY_ENV, None)
        if self._saved_env is not None:
            os.environ[aee.KEY_POLICY_ENV] = self._saved_env

    def test_accept_vectors_verify_valid_with_expected_result(self):
        for entry in _entries("accept", 4):
            with self.subTest(vector=entry["id"]):
                report = aee.verify_file(_path(entry))
                self.assertEqual(report["verdict"], "valid")
                self.assertEqual(report["result"], entry["expected"]["result"])
                self.assertIn("tiers", report)

    def test_reject_vectors_verify_invalid_with_matching_code(self):
        for entry in _entries("reject", 4):
            with self.subTest(vector=entry["id"]):
                report = aee.verify_file(_path(entry))
                self.assertEqual(report["verdict"], "invalid")
                self.assertTrue(
                    set(entry["expected"]["codes"]) & set(report["codes"]),
                    "no expected code in %r" % (report["codes"],),
                )
                self.assertNotIn("result", report)
                self.assertNotIn("tiers", report)

    def test_indeterminate_family_answers_within_declared_readings(self):
        for entry in _entries("indeterminate", 10):
            with self.subTest(vector=entry["id"]):
                report = aee.verify_file(_path(entry))
                self.assertEqual(report["verdict"], "invalid")
                predicted = set(entry["expected"]["readings"].values())
                self.assertTrue(predicted & set(report["codes"]))

    def test_tiers_follow_the_pinned_key_policy(self):
        from agent_evidence_vectors.run_vectors import PINNED_ROLE, derive_test_keys

        keys = derive_test_keys()
        pinned = keys[PINNED_ROLE]
        policy = {
            "substrateObservationKeys": [
                {"keyid": pinned["keyid"], "publicKeyHex": pinned["public"].hex()}
            ]
        }
        tiered = [
            e
            for e in _manifest()["vectors"]
            if e.get("kind") == "accept" and "tierWithPinnedKey" in e.get("expected", {})
        ]
        self.assertTrue(tiered, "corpus carries tier expectations")
        with tempfile.TemporaryDirectory() as td:
            policy_path = os.path.join(td, "keys.json")
            with open(policy_path, "w", encoding="utf-8") as f:
                json.dump(policy, f)
            for entry in tiered[:3]:
                with self.subTest(vector=entry["id"]):
                    os.environ[aee.KEY_POLICY_ENV] = policy_path
                    with_key = aee.verify_file(_path(entry))
                    self.assertEqual(with_key["tiers"], entry["expected"]["tierWithPinnedKey"])
                    del os.environ[aee.KEY_POLICY_ENV]
                    without_key = aee.verify_file(_path(entry))
                    self.assertEqual(
                        without_key["tiers"], entry["expected"]["tierWithoutKey"]
                    )
                    # Tier derivation never alters the result.
                    self.assertEqual(with_key["result"], without_key["result"])

    def test_module_entrypoint_contract(self):
        entry = _entries("accept", 1)[0]
        proc = subprocess.run(
            [sys.executable, "-m", "uibc_core.aee", _path(entry)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        last = [ln for ln in proc.stdout.splitlines() if ln.strip()][-1]
        report = json.loads(last)
        self.assertEqual(report["verdict"], "valid")


class TestAeeRailFailClosed(unittest.TestCase):
    def test_missing_file_is_invalid_not_an_exception(self):
        report = aee.verify_file("/nonexistent/statement.json")
        self.assertEqual(report["verdict"], "invalid")
        self.assertTrue(report["codes"])

    def test_non_json_bytes_are_statement_malformed(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bad.json")
            with open(path, "wb") as f:
                f.write(b"{not json")
            report = aee.verify_file(path)
        self.assertEqual(report, {"verdict": "invalid", "codes": ["statement-malformed"]})


if __name__ == "__main__":
    unittest.main()
